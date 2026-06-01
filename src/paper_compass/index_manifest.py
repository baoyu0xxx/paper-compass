"""Helpers for incremental index manifests."""

from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterable


EMPTY_MANIFEST = {
    "collection_name": "",
    "embedding_model_id": "",
    "chunking_version": "",
    "items": {},
}


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def load_manifest(path: str) -> Dict[str, Any]:
    manifest_path = Path(path)
    if not manifest_path.exists():
        return {
            "collection_name": "",
            "embedding_model_id": "",
            "chunking_version": "",
            "items": {},
        }

    data = json.loads(manifest_path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError(f"Manifest must be a JSON object: {manifest_path}")

    merged = {
        "collection_name": "",
        "embedding_model_id": "",
        "chunking_version": "",
        "items": {},
    }
    merged.update(data)
    if not isinstance(merged.get("items"), dict):
        raise ValueError(f"Manifest 'items' must be an object: {manifest_path}")
    return merged


def save_manifest(path: str, data: Dict[str, Any]) -> None:
    manifest_path = Path(path)
    manifest_path.parent.mkdir(parents=True, exist_ok=True)
    manifest_path.write_text(
        json.dumps(data, ensure_ascii=False, indent=2, sort_keys=True),
        encoding="utf-8",
    )


def compute_text_sha1(text: str) -> str:
    return hashlib.sha1(text.encode("utf-8")).hexdigest()


def build_paper_fingerprint(
    item: Dict[str, Any],
    full_text: str,
    chunking_version: str,
    embedding_model_id: str,
    chunk_count: int | None = None,
) -> Dict[str, Any]:
    pdf_path = item.get("pdf_path", "") or ""
    pdf_mtime = None
    if pdf_path:
        pdf_file = Path(pdf_path)
        if pdf_file.exists():
            pdf_mtime = int(pdf_file.stat().st_mtime)

    return {
        "item_key": item.get("key", ""),
        "pdf_path": pdf_path,
        "text_file": item.get("text_file", "") or "",
        "text_sha1": compute_text_sha1(full_text),
        "text_size": len(full_text),
        "pdf_mtime": pdf_mtime,
        "chunking_version": chunking_version,
        "embedding_model_id": embedding_model_id,
        "chunk_count": chunk_count,
        "updated_at": utc_now_iso(),
    }


def _fingerprint_core(data: Dict[str, Any]) -> Dict[str, Any]:
    core = dict(data)
    core.pop("updated_at", None)
    core.pop("pdf_path", None)
    core.pop("text_file", None)
    core.pop("pdf_mtime", None)
    return core


def diff_manifest(current_items: Dict[str, Dict[str, Any]], manifest_items: Dict[str, Dict[str, Any]]) -> Dict[str, list[str]]:
    current_keys = set(current_items.keys())
    manifest_keys = set(manifest_items.keys())

    new_keys = sorted(current_keys - manifest_keys)
    deleted_keys = sorted(manifest_keys - current_keys)
    unchanged_keys = []
    changed_keys = []

    for key in sorted(current_keys & manifest_keys):
        current = _fingerprint_core(current_items[key])
        previous = _fingerprint_core(manifest_items[key])
        if current == previous:
            unchanged_keys.append(key)
        else:
            changed_keys.append(key)

    return {
        "new": new_keys,
        "changed": changed_keys,
        "unchanged": unchanged_keys,
        "deleted": deleted_keys,
    }


def split_manifest_vs_store(
    current_items: Dict[str, Dict[str, Any]],
    manifest_items: Dict[str, Dict[str, Any]],
    store_item_keys: Iterable[str],
) -> Dict[str, list[str]]:
    """Compare current library, manifest, and actual vector-store keys.

    Returns a normalized diff for incremental repair:
    - new: in current library but not in manifest
    - changed: in both current and manifest, but fingerprint differs
    - unchanged: in current and manifest, fingerprints equal, and present in store
    - deleted: in manifest but not current library
    - missing_in_store: in current+manifest but absent from store
    - orphan_in_store: in store but absent from current library
    """

    manifest_diff = diff_manifest(current_items, manifest_items)
    store_keys = {str(key) for key in store_item_keys if key}
    current_keys = set(current_items.keys())
    manifest_keys = set(manifest_items.keys())

    missing_in_store = sorted((current_keys & manifest_keys) - store_keys)
    orphan_in_store = sorted(store_keys - current_keys)
    unchanged = sorted(set(manifest_diff["unchanged"]) - set(missing_in_store))

    return {
        "new": manifest_diff["new"],
        "changed": manifest_diff["changed"],
        "unchanged": unchanged,
        "deleted": manifest_diff["deleted"],
        "missing_in_store": missing_in_store,
        "orphan_in_store": orphan_in_store,
    }
