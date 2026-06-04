"""Readback helpers for passage context expansion."""

from __future__ import annotations

from typing import Any, Dict, List

from paper_compass.mcp_handles import parse_passage_handle
from paper_compass.search import DEFAULT_LIBRARY_PATH, DEFAULT_TEXT_DIR, search_passages


def get_passage_context(
    passage_handle: str,
    window: str = "paragraph",
    max_chars: int = 2000,
    *,
    text_dir: str | None = None,
    library_path: str | None = None,
) -> Dict[str, Any]:
    parsed = parse_passage_handle(passage_handle)
    mode = parsed.search_mode if parsed.search_mode in {"semantic", "keyword", "hybrid"} else "hybrid"
    text_dir = text_dir or str(DEFAULT_TEXT_DIR)
    library_path = library_path or str(DEFAULT_LIBRARY_PATH)

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
