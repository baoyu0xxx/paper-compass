"""Presentation-layer shapers for MCP tool responses."""

from __future__ import annotations

from typing import Any, Dict, List

from paper_compass.mcp_handles import make_paper_handle, make_passage_handle, make_wiki_handle


def shape_library_matches(raw_results: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    shaped: List[Dict[str, Any]] = []
    for item in raw_results:
        doc_id = item.get("doc_id", "")
        shaped.append(
            {
                "paper_handle": make_paper_handle(doc_id) if doc_id else "",
                "doc_id": doc_id,
                "title": item.get("title", ""),
                "year": item.get("year"),
                "authors": item.get("authors", []),
                "score": item.get("score", 0.0),
            }
        )
    return shaped


def shape_passage_matches(raw_results: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    shaped: List[Dict[str, Any]] = []
    for idx, item in enumerate(raw_results):
        doc_id = item.get("doc_id", "")
        page_num = item.get("page_num")
        search_mode = item.get("search_mode", "") or "semantic"
        handle_ordinal = item.get("paragraph_index") if search_mode == "keyword" else idx
        if handle_ordinal is None:
            handle_ordinal = idx
        snippet = (item.get("passage") or "")[:240]
        shaped.append(
            {
                "passage_handle": make_passage_handle(doc_id, page_num, search_mode, int(handle_ordinal)),
                "paper_handle": make_paper_handle(doc_id) if doc_id else "",
                "doc_id": doc_id,
                "title": item.get("title", ""),
                "page_num": page_num,
                "score": item.get("score", 0.0),
                "search_mode": search_mode,
                "match_type": item.get("match_type", ""),
                "snippet": snippet,
            }
        )
    return shaped


def shape_ask_research_result(result: Dict[str, Any]) -> Dict[str, Any]:
    evidence_digest: List[Dict[str, Any]] = []

    for page in result.get("wiki_context", {}).get("pages_used", []):
        page_path = page.get("page_path", "")
        section = page.get("section")
        evidence_digest.append(
            {
                "source_type": "wiki_page",
                "wiki_handle": make_wiki_handle(page_path, section),
                "title": page.get("title", ""),
                "page_path": page_path,
                "section": section,
            }
        )

    for idx, snippet in enumerate(result.get("pdf_context", {}).get("evidence_snippets", [])):
        doc_id = snippet.get("doc_id", "")
        page_num = snippet.get("page_num")
        evidence_digest.append(
            {
                "source_type": "pdf_doc",
                "paper_handle": make_paper_handle(doc_id) if doc_id else "",
                "passage_handle": make_passage_handle(doc_id, page_num, "pdf", idx),
                "title": snippet.get("title", ""),
                "page_num": page_num,
            }
        )

    shaped = {
        "answer": result.get("answer", ""),
        "mode_decision": result.get("mode_decision", {}),
        "evidence_digest": evidence_digest,
    }

    follow_up_hints = []
    if any(item.get("source_type") == "pdf_doc" for item in evidence_digest):
        follow_up_hints.append("Use get_passage_context to inspect a cited passage in full context")
    if any(item.get("source_type") == "wiki_page" for item in evidence_digest):
        follow_up_hints.append("Use get_wiki_page_section to read the cited wiki section")
    if follow_up_hints:
        shaped["follow_up_hints"] = follow_up_hints

    return shaped
