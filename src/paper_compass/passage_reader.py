"""Readback helpers for passage context expansion."""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any, Dict, List

from paper_compass.mcp_handles import parse_passage_handle
from paper_compass.search import DEFAULT_LIBRARY_PATH, DEFAULT_TEXT_DIR, search_passages

_VALID_WINDOWS = {"match_only", "paragraph", "section", "page"}


def _load_library_record(doc_id: str, library_path: str) -> Dict[str, Any]:
    """Best-effort lookup of a library record by doc_id/key."""
    try:
        data = json.loads(Path(library_path).read_text(encoding="utf-8"))
    except Exception:
        return {}

    if isinstance(data, list):
        records = data
    elif isinstance(data, dict):
        if doc_id in data and isinstance(data[doc_id], dict):
            return data[doc_id]
        records = data.get("items") or data.get("records") or data.get("papers") or []
    else:
        records = []

    for record in records:
        if not isinstance(record, dict):
            continue
        if record.get("key") == doc_id or record.get("doc_id") == doc_id or record.get("id") == doc_id:
            return record
    return {}


def _paragraphs_for_doc(doc_id: str, text_dir: str) -> List[str]:
    txt_path = Path(text_dir) / f"{doc_id}.txt"
    if not txt_path.exists():
        raise ValueError(f"Could not resolve passage handle for doc_id {doc_id}: missing text file {txt_path}")

    text = txt_path.read_text(encoding="utf-8", errors="replace")
    paragraphs: List[str] = []
    for paragraph in re.split(r"\n\s*\n", text):
        paragraph = paragraph.strip()
        if len(paragraph) < 30:
            continue
        paragraphs.append(paragraph)
    return paragraphs


def _resolve_keyword_text_passage(
    passage_handle: str,
    *,
    doc_id: str,
    ordinal: int,
    page_num: int | None,
    window: str,
    max_chars: int,
    text_dir: str,
    library_path: str,
) -> Dict[str, Any]:
    paragraphs = _paragraphs_for_doc(doc_id, text_dir)
    if ordinal < 0 or ordinal >= len(paragraphs):
        raise ValueError(
            f"Could not resolve passage handle {passage_handle}: "
            f"ordinal {ordinal} is out of range for {len(paragraphs)} paragraph(s)"
        )

    # Plain extracted .txt files do not retain section/page boundaries; for now
    # section/page windows safely degrade to the resolved paragraph.
    text = paragraphs[ordinal]
    if window == "match_only":
        text = text[: min(max_chars, 400)]
    else:
        text = text[:max_chars]

    record = _load_library_record(doc_id, library_path)
    return {
        "paper_handle": f"paper:{doc_id}",
        "passage_handle": passage_handle,
        "title": record.get("title", ""),
        "page_num": page_num,
        "context_window": window,
        "text": text,
    }


def get_passage_context(
    passage_handle: str,
    window: str = "paragraph",
    max_chars: int = 2000,
    *,
    text_dir: str | None = None,
    library_path: str | None = None,
) -> Dict[str, Any]:
    if window not in _VALID_WINDOWS:
        raise ValueError(f"Invalid context window: {window}")

    parsed = parse_passage_handle(passage_handle)
    mode = parsed.search_mode if parsed.search_mode in {"semantic", "keyword", "hybrid"} else "hybrid"
    text_dir = text_dir or str(DEFAULT_TEXT_DIR)
    library_path = library_path or str(DEFAULT_LIBRARY_PATH)

    if parsed.search_mode == "keyword":
        return _resolve_keyword_text_passage(
            passage_handle,
            doc_id=parsed.doc_id,
            ordinal=parsed.ordinal,
            page_num=parsed.page_num,
            window=window,
            max_chars=max_chars,
            text_dir=text_dir,
            library_path=library_path,
        )

    results: List[Dict[str, Any]] = search_passages(
        parsed.doc_id,
        search_mode=mode,
        limit=max(parsed.ordinal + 3, 5),
        text_dir=text_dir,
        library_path=library_path,
    )
    candidates = [r for r in results if r.get("doc_id") == parsed.doc_id]
    if parsed.page_num is not None:
        page_filtered = [r for r in candidates if r.get("page_num") == parsed.page_num]
        if page_filtered:
            candidates = page_filtered

    if not candidates:
        raise ValueError(f"Could not resolve passage handle: {passage_handle}")

    index = min(parsed.ordinal, len(candidates) - 1)
    match = candidates[index]
    text = (match.get("passage") or "")[:max_chars]
    if window == "match_only":
        text = text[: min(max_chars, 400)]

    return {
        "paper_handle": f"paper:{match.get('doc_id', '')}",
        "passage_handle": passage_handle,
        "title": match.get("title", ""),
        "page_num": match.get("page_num"),
        "context_window": window,
        "text": text,
    }
