"""Zotero storage scanning and content-source normalization."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable


@dataclass(frozen=True)
class StorageCandidate:
    key: str
    directory: Path
    cache_path: Path | None
    pdf_path: Path | None
    source_kind: str
    source_path: Path | None
    skipped_reason: str = ""


def _nonempty_text(path: Path) -> bool:
    try:
        return bool(path.read_text(encoding="utf-8").strip())
    except (OSError, UnicodeError):
        return False


def _first_pdf(directory: Path) -> Path | None:
    pdfs = sorted(
        path
        for path in directory.rglob("*.pdf")
        if path.is_file() and not path.name.lower().endswith(".compare.pdf")
    )
    return pdfs[0] if pdfs else None


def scan_storage(storage_root: str | Path) -> list[StorageCandidate]:
    """Scan Zotero storage folders without reading PDFs unless necessary."""
    root = Path(storage_root)
    if not root.exists():
        return []

    candidates: list[StorageCandidate] = []
    for directory in sorted(path for path in root.iterdir() if path.is_dir()):
        cache = directory / ".zotero-ft-cache"
        cache_path = cache if cache.is_file() else None
        pdf_path = _first_pdf(directory)
        has_compare_pdf = any(
            path.is_file() and path.name.lower().endswith(".compare.pdf")
            for path in directory.rglob("*.pdf")
        )
        if pdf_path is None and has_compare_pdf:
            candidates.append(StorageCandidate(
                key=directory.name,
                directory=directory,
                cache_path=cache_path,
                pdf_path=None,
                source_kind="unavailable",
                source_path=None,
                skipped_reason="comparison PDF only",
            ))
        elif cache_path is not None and _nonempty_text(cache_path):
            candidates.append(StorageCandidate(
                key=directory.name,
                directory=directory,
                cache_path=cache_path,
                pdf_path=pdf_path,
                source_kind="ft_cache",
                source_path=cache_path,
            ))
        elif pdf_path is not None:
            candidates.append(StorageCandidate(
                key=directory.name,
                directory=directory,
                cache_path=cache_path,
                pdf_path=pdf_path,
                source_kind="pdf",
                source_path=pdf_path,
            ))
        else:
            candidates.append(StorageCandidate(
                key=directory.name,
                directory=directory,
                cache_path=cache_path,
                pdf_path=None,
                source_kind="unavailable",
                source_path=None,
                skipped_reason="missing cache and PDF",
            ))
    return candidates


def _metadata_by_key(metadata_items: Iterable[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    result: dict[str, dict[str, Any]] = {}
    for item in metadata_items:
        for key in (item.get("key", ""), item.get("attachment_key", "")):
            if key:
                result.setdefault(str(key), dict(item))
    return result


def _fallback_title(candidate: StorageCandidate) -> str:
    if candidate.cache_path is not None:
        try:
            for line in candidate.cache_path.read_text(encoding="utf-8").splitlines():
                if line.strip():
                    return line.strip()[:300]
        except (OSError, UnicodeError):
            pass
    return candidate.pdf_path.stem if candidate.pdf_path else candidate.key


def normalize_storage_items(
    storage_root: str | Path,
    metadata_items: Iterable[dict[str, Any]],
) -> list[dict[str, Any]]:
    """Join storage content truth with optional Zotero metadata.

    Only records with usable text sources are returned. Cache text is always
    preferred over PDF text; PDF-only records are marked for extraction by the
    caller.
    """
    metadata = _metadata_by_key(metadata_items)
    normalized: list[dict[str, Any]] = []
    for candidate in scan_storage(storage_root):
        if candidate.source_kind == "unavailable":
            continue
        item = dict(metadata.get(candidate.key, {}))
        if not item and candidate.pdf_path is not None:
            item = dict(metadata.get(candidate.pdf_path.parent.name, {}))
        parent_key = str(item.get("key", "") or "")
        item.setdefault("item_id", "")
        item["key"] = parent_key or candidate.key
        item["attachment_key"] = candidate.key
        item["title"] = item.get("title") or _fallback_title(candidate)
        item.setdefault("date", "")
        item.setdefault("authors", [])
        item.setdefault("tags", [])
        item.setdefault("collections", [])
        item.setdefault("item_type", "journalArticle")
        item["pdf_path"] = str(candidate.pdf_path or item.get("pdf_path", "") or "")
        item["source_kind"] = candidate.source_kind
        item["source_path"] = str(candidate.source_path or "")
        item["cache_path"] = str(candidate.cache_path or "")
        item["skipped_reason"] = ""
        item["metadata_source"] = "sqlite" if candidate.key in metadata else "scan"
        normalized.append(item)

    # One paper can have multiple Zotero attachment folders. Keep one canonical
    # record, preferring SQLite metadata and cached text over scan-only/PDF data.
    deduplicated: dict[str, dict[str, Any]] = {}
    for item in normalized:
        key = str(item.get("key", "") or item.get("attachment_key", ""))
        existing = deduplicated.get(key)
        if existing is None or (
            item.get("metadata_source") == "sqlite",
            item.get("source_kind") == "ft_cache",
        ) > (
            existing.get("metadata_source") == "sqlite",
            existing.get("source_kind") == "ft_cache",
        ):
            deduplicated[key] = item
    return list(deduplicated.values())
