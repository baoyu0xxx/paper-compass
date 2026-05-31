from __future__ import annotations

import json
from dataclasses import dataclass, field
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
    manifest_only_keys: dict[str, list[str]] = field(default_factory=dict)
    store_only_keys: dict[str, list[str]] = field(default_factory=dict)


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
    data = collection.get(limit=count, include=["metadatas"])
    keys: set[str] = set()
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
        manifest_only_keys=manifest_only_keys,
        store_only_keys=store_only_keys,
    )
