from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any


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


def _create_persistent_client(path: str):
    import chromadb
    from chromadb.config import Settings

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


def inspect_index_health(db_path: str | Path) -> IndexHealthReport:
    db_root = Path(db_path)
    has_journal = (db_root / "chroma.sqlite3-journal").exists()
    has_wal = (db_root / "chroma.sqlite3-wal").exists()
    has_shm = (db_root / "chroma.sqlite3-shm").exists()

    manifest_files, manifest_errors = _check_manifest_files(db_root)

    chroma_openable = True
    collection_counts: dict[str, int] = {}
    chroma_error = ""
    try:
        client = _create_persistent_client(str(db_root))
        collections = client.list_collections()
        for collection in collections:
            collection_counts[collection.name] = int(collection.count())
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

    if manifest_errors:
        severity = "corrupted"
        problems.extend(manifest_errors)
        recommendation = (
            "Manifest state is invalid. Backup data/vectordb and rebuild the affected index via "
            "paper-compass sync --rebuild papers --backup-corrupted-db."
        )

    if not chroma_openable:
        severity = "corrupted"
        problems.append(f"ChromaDB open failed: {chroma_error}")
        recommendation = (
            "Chroma persistent state appears corrupted. Backup data/vectordb and rebuild via "
            "paper-compass sync --rebuild papers --backup-corrupted-db (or --rebuild all if wiki is also affected)."
        )

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
    )
