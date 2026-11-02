from __future__ import annotations

import json
import re
import shutil
import sqlite3
from typing import Any
from dataclasses import dataclass, field
from pathlib import Path
from paper_compass.windows_integrity import prepare_runtime_temp


@dataclass
class IndexHealthReport:
    ok: bool
    db_path: str
    has_journal: bool
    has_wal: bool
    has_shm: bool
    manifest_files: list[str]
    chroma_openable: bool
    collection_counts: dict[str, int]
    severity: str
    summary: str
    recommended_action: str
    manifest_only_keys: dict[str, list[str]] = field(default_factory=dict)
    store_only_keys: dict[str, list[str]] = field(default_factory=dict)


def _create_persistent_client(path: str):
    import chromadb
    from chromadb.config import Settings

    prepare_runtime_temp(path)
    return chromadb.PersistentClient(path=path, settings=Settings(anonymized_telemetry=False))


def _check_manifest_files(db_path: Path) -> tuple[list[str], list[str]]:
    manifest_files = sorted(p.name for p in db_path.glob("*.manifest.json")) if db_path.exists() else []
    manifest_errors: list[str] = []
    for name in manifest_files:
        try:
            payload = json.loads((db_path / name).read_text(encoding="utf-8"))
            if not isinstance(payload, dict):
                manifest_errors.append(f"manifest is not a JSON object: {name}")
        except Exception as exc:
            manifest_errors.append(f"manifest unreadable: {name} ({exc})")
    return manifest_files, manifest_errors


def _paper_manifest_key_map(db_path: Path, manifest_files: list[str]) -> dict[str, set[str]]:
    result: dict[str, set[str]] = {}
    for name in manifest_files:
        if not name.startswith("papers_"):
            continue
        try:
            payload = json.loads((db_path / name).read_text(encoding="utf-8"))
        except Exception:
            continue
        items = payload.get("items", {}) if isinstance(payload, dict) else {}
        if isinstance(items, dict):
            result[name[: -len(".manifest.json")]] = {str(key) for key in items.keys() if key}
    return result


def _collection_item_keys(collection: Any, count: int) -> set[str]:
    if count <= 0 or not hasattr(collection, "get"):
        return set()
    keys: set[str] = set()
    page_size = 500
    for offset in range(0, count, page_size):
        if offset:
            data = collection.get(
                limit=min(page_size, count - offset),
                offset=offset,
                include=["metadatas"],
            )
        else:
            data = collection.get(limit=min(page_size, count), include=["metadatas"])
        for metadata in data.get("metadatas", []) or []:
            if metadata and metadata.get("item_key"):
                keys.add(str(metadata["item_key"]))
    return keys


def inspect_index_health(db_path: str | Path) -> IndexHealthReport:
    db_root = Path(db_path)
    has_journal = (db_root / "chroma.sqlite3-journal").exists()
    has_wal = (db_root / "chroma.sqlite3-wal").exists()
    has_shm = (db_root / "chroma.sqlite3-shm").exists()

    manifest_files, manifest_errors = _check_manifest_files(db_root)

    chroma_openable = True
    collection_counts: dict[str, int] = {}
    manifest_only_keys: dict[str, list[str]] = {}
    store_only_keys: dict[str, list[str]] = {}
    chroma_error = ""
    sqlite_errors: list[str] = []
    sqlite_path = db_root / "chroma.sqlite3"
    if sqlite_path.exists():
        try:
            with sqlite3.connect(sqlite_path.resolve().as_uri() + "?mode=ro", uri=True) as connection:
                sqlite_errors = [str(row[0]) for row in connection.execute("PRAGMA quick_check") if row[0] != "ok"]
        except sqlite3.Error as exc:
            sqlite_errors = [str(exc)]
        try:
            client = _create_persistent_client(str(db_root))
            collections = client.list_collections()
            manifest_key_map = _paper_manifest_key_map(db_root, manifest_files)
            for collection in collections:
                count = int(collection.count())
                collection_counts[collection.name] = count
                if collection.name.startswith("papers_") and collection.name in manifest_key_map:
                    store_keys = _collection_item_keys(collection, count)
                    manifest_keys = manifest_key_map[collection.name]
                    only_manifest = sorted(manifest_keys - store_keys)
                    only_store = sorted(store_keys - manifest_keys)
                    if only_manifest:
                        manifest_only_keys[collection.name] = only_manifest
                    if only_store:
                        store_only_keys[collection.name] = only_store
        except Exception as exc:
            chroma_openable = False
            chroma_error = str(exc)

    severity = "ok"
    problems: list[str] = []
    recommendation = "No action needed. Incremental sync can proceed."

    if has_journal or has_wal or has_shm:
        severity = "warning"
        leftovers = []
        if has_journal:
            leftovers.append("journal")
        if has_wal:
            leftovers.append("wal")
        if has_shm:
            leftovers.append("shm")
        problems.append(f"sqlite transient files present: {', '.join(leftovers)}")
        recommendation = (
            "Inspect the last interrupted run before writing again. If Chroma still behaves abnormally, "
            "backup the database and rebuild via paper-compass sync --rebuild papers --backup-corrupted-db."
        )

    if manifest_only_keys or store_only_keys:
        if severity == "ok":
            severity = "warning"
        mismatch_parts = []
        for collection, keys in manifest_only_keys.items():
            mismatch_parts.append(f"{collection}: manifest-only={len(keys)}")
        for collection, keys in store_only_keys.items():
            mismatch_parts.append(f"{collection}: store-only={len(keys)}")
        problems.append(f"manifest/store mismatch ({', '.join(mismatch_parts)})")
        recommendation = (
            "Incremental index state is inconsistent. Rerun paper indexing to repair missing vectors, "
            "or rebuild via paper-compass sync --rebuild papers --backup-corrupted-db if Chroma is unhealthy."
        )

    if manifest_errors:
        severity = "corrupted"
        problems.extend(manifest_errors)
        recommendation = (
            "Manifest state is invalid. Backup data/vectordb and rebuild the affected index via "
            "paper-compass sync --rebuild papers --backup-corrupted-db."
        )

    if not chroma_openable:
        if "unable to open database file" in chroma_error.lower():
            severity = "blocked"
            problems.append(f"ChromaDB unavailable: {chroma_error}")
            recommendation = (
                "The Python SQLite/Chroma runtime cannot open a writable database file. "
                "Verify SQLite file creation and Windows security policy before rebuilding the index."
            )
        else:
            severity = "corrupted"
            problems.append(f"ChromaDB open failed: {chroma_error}")
            recommendation = (
                "Chroma persistent state appears corrupted. Backup data/vectordb and rebuild via "
                "paper-compass sync --rebuild papers --backup-corrupted-db (or --rebuild all if wiki is also affected)."
            )

    if sqlite_errors:
        severity = "corrupted"
        problems.append(f"SQLite integrity check failed: {'; '.join(sqlite_errors)}")
        if _looks_like_fulltext_problem(sqlite_errors):
            recommendation = (
                "Run 'paper-compass repair-fts' to rebuild the full-text index in place "
                "(no re-embedding, add --backup to keep a copy); only fall back to "
                "paper-compass sync --rebuild papers --backup-corrupted-db if that repair fails."
            )
        else:
            recommendation = "Back up the complete vectordb before repairing SQLite or rebuilding papers and wiki."

    if not problems:
        problems.append("vectordb health looks normal")

    return IndexHealthReport(
        ok=severity == "ok",
        db_path=str(db_root),
        has_journal=has_journal,
        has_wal=has_wal,
        has_shm=has_shm,
        manifest_files=manifest_files,
        chroma_openable=chroma_openable,
        collection_counts=collection_counts,
        severity=severity,
        summary="; ".join(problems),
        recommended_action=recommendation,
        manifest_only_keys=manifest_only_keys,
        store_only_keys=store_only_keys,
    )


_FULLTEXT_PROBLEM_MARKERS = ("fts5", "inverted index", "fulltext")

_FTS_TABLE_PATTERNS = (
    re.compile(r"FTS5 table (?:main\.)?([A-Za-z0-9_]+)", re.IGNORECASE),
    re.compile(r'from table "([A-Za-z0-9_]+)"', re.IGNORECASE),
)

_REBUILD_SQL = 'INSERT INTO "{table}"("{table}") VALUES(\'rebuild\')'


def _looks_like_fulltext_problem(problems: list[str]) -> bool:
    return any(
        marker in problem.lower()
        for problem in problems
        for marker in _FULLTEXT_PROBLEM_MARKERS
    )


@dataclass
class FulltextRepairReport:
    ok: bool
    db_path: str
    sqlite_path: str
    fulltext_tables: list[str]
    corrupted_tables: list[str]
    before: list[str]
    after: list[str]
    repaired: bool
    backup_path: str
    message: str


class FulltextRepairError(RuntimeError):
    """Raised when the Chroma full-text index cannot be inspected or repaired."""


def _sqlite_path_for(db_path: str | Path) -> Path:
    root = Path(db_path)
    sqlite_path = root / "chroma.sqlite3"
    if not sqlite_path.is_file():
        raise FulltextRepairError(
            f"Chroma database not found: {sqlite_path}. "
            "Pass the directory that contains chroma.sqlite3 via --db-path."
        )
    return sqlite_path


def _connect_sqlite(path: Path, *, readonly: bool) -> sqlite3.Connection:
    mode = "ro" if readonly else "rw"
    return sqlite3.connect(f"{path.resolve().as_uri()}?mode={mode}", uri=True, timeout=30)


def _fulltext_tables(connection: sqlite3.Connection) -> list[str]:
    rows = connection.execute(
        "SELECT name, sql FROM sqlite_master WHERE type = 'table' AND sql IS NOT NULL"
    ).fetchall()
    tables = []
    for name, ddl in rows:
        lowered = str(ddl).lower()
        if "virtual table" in lowered and "fts5" in lowered:
            tables.append(str(name))
    return sorted(tables)


def _quick_check(connection: sqlite3.Connection) -> list[str]:
    return [str(row[0]) for row in connection.execute("PRAGMA quick_check") if str(row[0]) != "ok"]


def _corrupted_fulltext_tables(problems: list[str], tables: list[str]) -> list[str]:
    if not _looks_like_fulltext_problem(problems):
        return []
    named: list[str] = []
    for problem in problems:
        for pattern in _FTS_TABLE_PATTERNS:
            match = pattern.search(problem)
            if match and match.group(1) not in named:
                named.append(match.group(1))
    if named:
        return [table for table in tables if table in named]
    return list(tables)


def _backup_sqlite(sqlite_path: Path) -> Path:
    from datetime import datetime, timezone

    timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    backup_path = sqlite_path.with_name(f"{sqlite_path.name}.bak-{timestamp}")
    shutil.copy2(sqlite_path, backup_path)
    for suffix in ("-wal", "-shm"):
        sidecar = sqlite_path.with_name(sqlite_path.name + suffix)
        if sidecar.is_file():
            shutil.copy2(sidecar, backup_path.with_name(backup_path.name + suffix))
    return backup_path


def repair_fulltext_index(
    db_path: str | Path,
    *,
    dry_run: bool = False,
    backup: bool = False,
) -> FulltextRepairReport:
    """Rebuild Chroma's FTS5 full-text index in place without re-embedding.

    ``PRAGMA quick_check`` reports "malformed inverted index" when FTS5's
    shadow tables disagree with the content table.  Because Chroma keeps the
    indexed text inside the FTS5 table itself, SQLite's ``rebuild`` command can
    recreate the inverted index from that content; embeddings are untouched.
    """
    sqlite_path = _sqlite_path_for(db_path)
    connection = _connect_sqlite(sqlite_path, readonly=True)
    try:
        tables = _fulltext_tables(connection)
        before = _quick_check(connection)
    finally:
        connection.close()

    corrupted = _corrupted_fulltext_tables(before, tables)

    def report(ok: bool, after: list[str], repaired: bool, backup_path: Path | None, message: str) -> FulltextRepairReport:
        return FulltextRepairReport(
            ok=ok,
            db_path=str(db_path),
            sqlite_path=str(sqlite_path),
            fulltext_tables=tables,
            corrupted_tables=corrupted,
            before=before,
            after=after,
            repaired=repaired,
            backup_path=str(backup_path) if backup_path else "",
            message=message,
        )

    if not tables:
        return report(
            not before,
            before,
            False,
            None,
            "No FTS5 table found; this database does not use a full-text index.",
        )
    if not before:
        return report(True, [], False, None, "Full-text index is healthy; nothing to repair.")
    if not corrupted:
        raise FulltextRepairError(
            "SQLite reports problems that are not FTS-related: " + "; ".join(before)
        )
    if dry_run:
        return report(
            False,
            before,
            False,
            None,
            "Dry run: would rebuild " + ", ".join(corrupted) + " (no changes written).",
        )

    backup_path = _backup_sqlite(sqlite_path) if backup else None
    connection = _connect_sqlite(sqlite_path, readonly=False)
    try:
        try:
            connection.execute("BEGIN IMMEDIATE")
            for table in corrupted:
                connection.execute(_REBUILD_SQL.format(table=table))
            connection.commit()
        except sqlite3.Error as exc:
            connection.rollback()
            raise FulltextRepairError(f"failed to rebuild full-text index: {exc}") from exc
        if connection.execute("PRAGMA journal_mode").fetchone()[0].lower() == "wal":
            connection.execute("PRAGMA wal_checkpoint(TRUNCATE)")
    finally:
        connection.close()

    connection = _connect_sqlite(sqlite_path, readonly=True)
    try:
        after = _quick_check(connection)
    finally:
        connection.close()
    if after:
        return report(
            False,
            after,
            True,
            backup_path,
            "Rebuilt the full-text index but SQLite still reports: " + "; ".join(after),
        )
    return report(
        True,
        after,
        True,
        backup_path,
        "Rebuilt the full-text index in place; no re-embedding was needed.",
    )
