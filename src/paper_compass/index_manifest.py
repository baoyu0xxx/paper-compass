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


def compute_file_sha256(path: str | Path, chunk_size: int = 1024 * 1024) -> str:
    digest = hashlib.sha256()
    with Path(path).open("rb") as fh:
        for chunk in iter(lambda: fh.read(chunk_size), b""):
            digest.update(chunk)
    return digest.hexdigest()


def stable_json_sha256(payload: Dict[str, Any]) -> str:
    encoded = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(encoded.encode("utf-8")).hexdigest()


def _normalize_string_list(values: list[Any]) -> list[str]:
    normalized = []
    for value in values:
        text = str(value or "").strip()
        if text:
            normalized.append(text)
    return normalized


def _normalize_people_list(values: list[Any]) -> list[str]:
    return _normalize_string_list(values)


def _normalized_metadata(item: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "title": item.get("title", "") or "",
        "year": item.get("year") or 0,
        "authors": _normalize_people_list(list(item.get("authors", []) or [])),
        "collections": sorted(_normalize_string_list(list(item.get("collections", []) or []))),
        "tags": sorted(_normalize_string_list(list(item.get("tags", []) or []))),
    }


def build_paper_fingerprint(
    item: Dict[str, Any],
    full_text: str,
    chunking_version: str,
    embedding_model_id: str,
    chunk_count: int | None = None,
) -> Dict[str, Any]:
    pdf_path = item.get("pdf_path", "") or ""
    text_file = item.get("text_file", "") or ""
    text_sha1 = compute_text_sha1(full_text)
    pdf_sha256 = ""
    pdf_size = None
    pdf_mtime = None
    content_source = "text"
    if pdf_path:
        pdf_file = Path(pdf_path)
        if pdf_file.exists():
            stat = pdf_file.stat()
            pdf_mtime = int(stat.st_mtime)
            pdf_size = stat.st_size
            pdf_sha256 = compute_file_sha256(pdf_file)
            content_source = "pdf"

    content_payload = {
        "content_source": content_source,
        "pdf_sha256": pdf_sha256 if content_source == "pdf" else "",
        "text_sha1": text_sha1 if content_source == "text" else "",
        "chunking_version": chunking_version,
        "chunk_count": chunk_count,
    }
    metadata_payload = _normalized_metadata(item)

    return {
        "schema_version": 2,
        "item_key": item.get("key", ""),
        "source": {
            "content_source": content_source,
            "pdf_path": pdf_path,
            "pdf_sha256": pdf_sha256,
            "pdf_size": pdf_size,
            "pdf_mtime": pdf_mtime,
            "text_file": text_file,
            "text_sha1": text_sha1,
            "text_size": len(full_text),
        },
        "indexing": {
            "chunking_version": chunking_version,
            "embedding_model_id": embedding_model_id,
            "chunk_count": chunk_count,
            "content_fingerprint": stable_json_sha256(content_payload),
        },
        "metadata": {
            **metadata_payload,
            "metadata_fingerprint": stable_json_sha256(metadata_payload),
        },
        "updated_at": utc_now_iso(),
    }


def _fingerprint_core(data: Dict[str, Any]) -> Dict[str, Any]:
    core = dict(data)
    core.pop("updated_at", None)
    core.pop("pdf_path", None)
    core.pop("text_file", None)
    core.pop("pdf_mtime", None)
    return core


def _content_fingerprint(data: Dict[str, Any]) -> str:
    indexing = data.get("indexing")
    if isinstance(indexing, dict) and indexing.get("content_fingerprint"):
        return str(indexing["content_fingerprint"])
    payload = {
        "content_source": "text",
        "pdf_sha256": "",
        "text_sha1": data.get("text_sha1", ""),
        "chunking_version": data.get("chunking_version", ""),
        "chunk_count": data.get("chunk_count"),
    }
    return stable_json_sha256(payload)


def _metadata_fingerprint(data: Dict[str, Any]) -> str:
    metadata = data.get("metadata")
    if isinstance(metadata, dict) and metadata.get("metadata_fingerprint"):
        return str(metadata["metadata_fingerprint"])
    return ""


def _path_fingerprint(data: Dict[str, Any]) -> str:
    source = data.get("source") if isinstance(data.get("source"), dict) else data
    payload = {
        "pdf_path": source.get("pdf_path", "") or "",
        "text_file": source.get("text_file", "") or "",
        "pdf_mtime": source.get("pdf_mtime"),
    }
    return stable_json_sha256(payload)


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


def _legacy_content_matches(current: Dict[str, Any], previous: Dict[str, Any]) -> bool:
    if isinstance(previous.get("indexing"), dict):
        return False
    current_source = current.get("source") if isinstance(current.get("source"), dict) else {}
    current_indexing = current.get("indexing") if isinstance(current.get("indexing"), dict) else {}
    return (
        bool(previous.get("text_sha1"))
        and previous.get("text_sha1") == current_source.get("text_sha1")
        and previous.get("chunking_version") == current_indexing.get("chunking_version")
        and previous.get("chunk_count") == current_indexing.get("chunk_count")
    )


def _content_matches(current: Dict[str, Any], previous: Dict[str, Any]) -> bool:
    return _content_fingerprint(current) == _content_fingerprint(previous) or _legacy_content_matches(current, previous)


def explain_fingerprint_diff(current: Dict[str, Any], previous: Dict[str, Any]) -> Dict[str, Any]:
    current_meta = current.get("metadata") if isinstance(current.get("metadata"), dict) else {}
    previous_meta = previous.get("metadata") if isinstance(previous.get("metadata"), dict) else {}
    reasons: list[str] = []
    details: Dict[str, Dict[str, Any]] = {}
    for field in ("title", "year", "authors", "collections", "tags"):
        before = previous_meta.get(field)
        after = current_meta.get(field)
        if before != after:
            reason = f"{field} changed"
            reasons.append(reason)
            details[field] = {"before": before, "after": after}
    return {"reasons": reasons, "details": details}


def diff_manifest_v2(current_items: Dict[str, Dict[str, Any]], manifest_items: Dict[str, Dict[str, Any]]) -> Dict[str, list[str]]:
    current_keys = set(current_items.keys())
    manifest_keys = set(manifest_items.keys())
    new_keys = sorted(current_keys - manifest_keys)
    deleted_keys = sorted(manifest_keys - current_keys)
    content_changed: list[str] = []
    metadata_only: list[str] = []
    path_only: list[str] = []
    unchanged: list[str] = []

    for key in sorted(current_keys & manifest_keys):
        current = current_items[key]
        previous = manifest_items[key]
        if not _content_matches(current, previous):
            content_changed.append(key)
        elif _metadata_fingerprint(current) != _metadata_fingerprint(previous):
            metadata_only.append(key)
        elif _path_fingerprint(current) != _path_fingerprint(previous):
            path_only.append(key)
        else:
            unchanged.append(key)

    requires_embedding = sorted(set(new_keys) | set(content_changed))
    return {
        "new": new_keys,
        "content_changed": content_changed,
        "metadata_only": metadata_only,
        "path_only": path_only,
        "unchanged": unchanged,
        "deleted": deleted_keys,
        "requires_embedding": requires_embedding,
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
