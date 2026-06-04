"""MCP server tool handlers for paper-compass."""

from __future__ import annotations

import time
from pathlib import Path
from typing import Any, Dict, List, Optional

from paper_compass.env_utils import PROJECT_ROOT
from paper_compass.logging import emit_trace
from paper_compass.mcp_handles import make_paper_handle, parse_paper_handle
from paper_compass.mcp_validation import validate_tool_arguments
from paper_compass.mcp_views import (
    shape_ask_research_result,
    shape_library_matches,
    shape_passage_matches,
)
from paper_compass.passage_reader import get_passage_context
from paper_compass.router import ask_research
from paper_compass.search import (
    DEFAULT_LIBRARY_PATH,
    DEFAULT_TEXT_DIR,
    DEFAULT_VECTORDB_PATH,
    _postprocess_wiki_results,
    get_paper_metadata,
    get_vector_collection_info,
    search_library,
    search_passages,
    vector_search,
)
from paper_compass.types import UnifiedResponse
from paper_compass.wiki_reader import get_wiki_page_section
from paper_compass.wiki_store import commit_save_query_to_wiki, plan_save_query_to_wiki


DEFAULT_WIKI_ROOT = PROJECT_ROOT / "wiki"


def _tool_search_wiki(query: str, limit: int = 5, db_path: str | None = None) -> Dict[str, Any]:
    try:
        db_path = db_path or str(DEFAULT_VECTORDB_PATH)
        if get_vector_collection_info(collection="wiki", db_path=db_path) is None:
            return UnifiedResponse.success(
                tool="search_wiki",
                data={"matches": [], "query_interpretation": "no wiki index found"},
                mode_used="wiki",
                confidence="low",
                next_action="Run build_index --wiki first",
            ).to_dict()

        results = vector_search(query, collection="wiki", k=limit * 2, db_path=db_path)
        results = _postprocess_wiki_results(results)
        matches = [
            {
                "wiki_handle": _make_wiki_handle_from_match(match),
                "page_path": (match.get("metadata") or {}).get("page_path", match["id"]),
                "title": (match.get("metadata") or {}).get("title", match["id"]),
                "page_type": (match.get("metadata") or {}).get("page_type", ""),
                "section": (match.get("metadata") or {}).get("section", ""),
                "snippet": match.get("document", "")[:200],
                "score": match.get("score", 0.0),
            }
            for match in results[:limit]
        ]

        confidence = "high" if matches and matches[0]["score"] > 0.5 else "medium" if matches else "low"
        return UnifiedResponse.success(
            tool="search_wiki",
            data={"matches": matches, "query_interpretation": "semantic wiki search"},
            mode_used="wiki",
            confidence=confidence,
            sources=[{"source_type": "wiki_page", "id": m["page_path"], "title": m["title"]} for m in matches],
        ).to_dict()
    except Exception as e:
        return UnifiedResponse.error("search_wiki", [str(e)]).to_dict()


def _tool_search_library(query: str, filters: Optional[Dict[str, Any]] = None, limit: int = 10) -> Dict[str, Any]:
    try:
        raw_results = search_library(query, filters=filters, limit=limit)
    except Exception as e:
        return UnifiedResponse.error("search_library", [str(e)]).to_dict()

    results = shape_library_matches(raw_results)

    confidence = "high" if results and results[0]["score"] > 3 else "medium" if results else "low"

    return UnifiedResponse.success(
        tool="search_library",
        data={"matches": results, "filters_used": filters or {}},
        mode_used="library",
        confidence=confidence,
        sources=[{"source_type": "pdf_doc", "id": m["doc_id"], "title": m["title"]} for m in results],
        next_action="Use ask_research for deeper analysis" if results else "Try broadening filters or run sync_zotero",
    ).to_dict()


def _tool_ask_research(
    query: str,
    filters: Optional[Dict[str, Any]] = None,
    force_mode: str = "auto",
    max_sources: int = 5,
    db_path: str | None = None,
) -> Dict[str, Any]:
    try:
        result = ask_research(
            query=query,
            force_mode=force_mode,
            filters=filters,
            max_sources=max_sources,
            db_path=db_path or str(DEFAULT_VECTORDB_PATH),
        )
    except Exception as e:
        return UnifiedResponse.error("ask_research", [str(e)]).to_dict()

    mode = result.get("mode_decision", {}).get("actual", "wiki")
    inferred_confidence = _infer_ask_confidence(result)
    return UnifiedResponse.success(
        tool="ask_research",
        data=shape_ask_research_result(result),
        mode_used=mode,
        confidence=inferred_confidence,
        sources=result.get("sources", []),
    ).to_dict()


def _tool_get_paper_metadata(
    id_or_doi: str | None = None,
    paper_handle: str | None = None,
) -> Dict[str, Any]:
    try:
        lookup_value = _resolve_paper_lookup_value(id_or_doi=id_or_doi, paper_handle=paper_handle)
        paper = get_paper_metadata(lookup_value)
    except Exception as e:
        return UnifiedResponse.error("get_paper_metadata", [str(e)]).to_dict()

    if paper is None:
        query_value = paper_handle or id_or_doi or ""
        return UnifiedResponse.error(
            "get_paper_metadata",
            [f"No paper found for: {query_value}"],
            "Try search_library first or run sync_zotero",
        ).to_dict()

    doc_id = paper.get("key", "")
    return UnifiedResponse.success(
        tool="get_paper_metadata",
        data={
            "paper": {
                "paper_handle": make_paper_handle(doc_id) if doc_id else "",
                "doc_id": doc_id,
                "title": paper.get("title", ""),
                "authors": paper.get("authors", []),
                "year": paper.get("year"),
                "collections": paper.get("collections", []),
                "tags": paper.get("tags", []),
                "pdf_path": paper.get("pdf_path", ""),
                "metadata_source": "sqlite",
            }
        },
        mode_used="library",
        confidence="high",
        sources=[{"source_type": "pdf_doc", "id": doc_id, "title": paper.get("title", "")}],
    ).to_dict()


def _tool_get_passage_context(
    passage_handle: str,
    window: str = "paragraph",
    max_chars: int = 2000,
) -> Dict[str, Any]:
    try:
        result = get_passage_context(
            passage_handle,
            window=window,
            max_chars=max_chars,
            text_dir=str(DEFAULT_TEXT_DIR),
            library_path=str(DEFAULT_LIBRARY_PATH),
        )
    except Exception as e:
        return UnifiedResponse.error("get_passage_context", [str(e)]).to_dict()

    return UnifiedResponse.success(
        tool="get_passage_context",
        data=result,
        mode_used="readback",
        confidence="high",
        sources=[
            {
                "source_type": "pdf_doc",
                "id": result.get("paper_handle", "").replace("paper:", ""),
                "title": result.get("title", ""),
            }
        ],
    ).to_dict()


def _tool_get_wiki_page_section(
    wiki_handle: str,
    include_frontmatter: bool = False,
) -> Dict[str, Any]:
    try:
        result = get_wiki_page_section(wiki_handle, include_frontmatter=include_frontmatter)
    except Exception as e:
        return UnifiedResponse.error("get_wiki_page_section", [str(e)]).to_dict()

    return UnifiedResponse.success(
        tool="get_wiki_page_section",
        data=result,
        mode_used="wiki",
        confidence="high",
        sources=[
            {
                "source_type": "wiki_page",
                "id": result.get("page_path", ""),
                "title": result.get("title", ""),
            }
        ],
    ).to_dict()


def _tool_save_to_wiki(
    title: str,
    content: str,
    target_type: str = "queries",
    source_refs: Optional[List[str]] = None,
    confidence: str = "medium",
    tags: Optional[List[str]] = None,
    dry_run: bool = True,
    commit: bool = False,
    upsert_mode: str = "create",
    wiki_root: str | None = None,
) -> Dict[str, Any]:
    try:
        if dry_run and commit:
            raise ValueError("Invalid writeback mode: dry_run=true cannot be combined with commit=true")

        plan = plan_save_query_to_wiki(
            title=title,
            content=content,
            target_type=target_type,
            source_refs=source_refs or [],
            confidence=confidence,
            tags=tags or [],
            wiki_root=wiki_root or str(DEFAULT_WIKI_ROOT),
        )

        if not commit:
            preview = {
                "dry_run": True,
                "would_write": plan["would_write"],
                "page_path": plan["page_path"],
                "slug": plan["slug"],
                "conflict": plan["conflict"],
                "conflict_paths": plan["conflict_paths"],
                "index_update_preview": plan["index_update_preview"],
                "log_update_preview": plan["log_update_preview"],
                "linked_pages": plan["linked_pages"],
            }
            return UnifiedResponse.success(
                tool="save_to_wiki",
                data=preview,
                mode_used="writeback",
                confidence=confidence,
                warnings=["Preview only — set commit=true to write to disk."],
            ).to_dict()

        result = commit_save_query_to_wiki(plan, upsert_mode=upsert_mode)
    except Exception as e:
        return UnifiedResponse.error("save_to_wiki", [str(e)]).to_dict()

    return UnifiedResponse.success(
        tool="save_to_wiki",
        data={"dry_run": False, **result},
        mode_used="writeback",
        confidence=confidence,
        sources=[{"source_type": "wiki_page", "id": result["page_path"], "title": title}],
    ).to_dict()


def _tool_search_passages(
    query: str,
    search_mode: str = "semantic",
    limit: int = 10,
    filters: Optional[Dict[str, Any]] = None,
    db_path: str | None = None,
    text_dir: str | None = None,
    library_path: str | None = None,
) -> Dict[str, Any]:
    try:
        raw_results = search_passages(
            query=query,
            search_mode=search_mode,
            limit=limit,
            filters=filters,
            db_path=db_path or str(DEFAULT_VECTORDB_PATH),
            text_dir=text_dir or str(DEFAULT_TEXT_DIR),
            library_path=library_path or str(DEFAULT_LIBRARY_PATH),
        )
    except Exception as e:
        return UnifiedResponse.error("search_passages", [str(e)]).to_dict()

    results = shape_passage_matches(raw_results)

    confidence = "high" if results and results[0]["score"] > 0.5 else "medium" if results else "low"
    return UnifiedResponse.success(
        tool="search_passages",
        data={
            "matches": results,
            "search_mode_used": search_mode,
            "query_interpretation": f"{search_mode} passage search",
        },
        mode_used=search_mode,
        confidence=confidence,
        sources=[{"source_type": "pdf_doc", "id": m["doc_id"], "title": m["title"]} for m in results],
        next_action="Use get_passage_context to inspect a specific hit in more detail" if results else "Try broadening keywords or switch to hybrid mode",
    ).to_dict()


_HANDLERS = {
    "search_wiki": _tool_search_wiki,
    "ask_research": _tool_ask_research,
    "search_library": _tool_search_library,
    "search_passages": _tool_search_passages,
    "get_paper_metadata": _tool_get_paper_metadata,
    "get_passage_context": _tool_get_passage_context,
    "get_wiki_page_section": _tool_get_wiki_page_section,
    "save_to_wiki": _tool_save_to_wiki,
}


def handle_tool(tool_name: str, params: Dict[str, Any]) -> Dict[str, Any]:
    handler = _HANDLERS.get(tool_name)
    if handler is None:
        response = UnifiedResponse.error(
            tool_name,
            [f"Unknown tool. Available: {list(_HANDLERS.keys())}"],
            "Call tools/list to discover supported tools",
        ).to_dict()
        emit_trace({"tool": tool_name, "ok": False, "warnings": response.get("warnings", []), "error_type": "unknown_tool"})
        return response

    validation_errors = validate_tool_arguments(tool_name, params)
    if validation_errors:
        response = UnifiedResponse.error(
            tool_name,
            validation_errors,
            "Check tools/list inputSchema",
        ).to_dict()
        emit_trace({"tool": tool_name, "ok": False, "warnings": response.get("warnings", []), "error_type": "invalid_params"})
        return response

    started = time.time()
    response = handler(**params)
    elapsed_ms = int((time.time() - started) * 1000)

    emit_trace(
        {
            "tool": tool_name,
            "ok": response.get("ok", False),
            "trace_id": response.get("trace_id", ""),
            "query": params.get("query", ""),
            "mode_used": response.get("mode_used", ""),
            "source_ids": [s.get("id", "") for s in response.get("sources", [])],
            "warnings": response.get("warnings", []),
            "elapsed_ms": elapsed_ms,
        }
    )
    return response


def _resolve_paper_lookup_value(id_or_doi: str | None, paper_handle: str | None) -> str:
    if paper_handle:
        return parse_paper_handle(paper_handle).doc_id
    if id_or_doi:
        return id_or_doi
    raise ValueError("Exactly one of 'paper_handle' or 'id_or_doi' is required")


def _make_passage_handle(doc_id: str, page_num: int | None, search_mode: str, ordinal: int) -> str:
    page_part = f"p{page_num}" if page_num is not None else "p?"
    return f"passage:{doc_id}:{page_part}:{search_mode}:{ordinal}"


def _make_wiki_handle_from_match(match: Dict[str, Any]) -> str:
    meta = match.get("metadata") or {}
    page_path = meta.get("page_path", match.get("id", ""))
    section = meta.get("section")
    if section in (None, ""):
        return f"wiki:{page_path}"
    return f"wiki:{page_path}#section={section}"


def _infer_ask_confidence(result: Dict[str, Any]) -> str:
    mode = result.get("mode_decision", {}).get("actual", "wiki")
    wiki_pages = len(result.get("wiki_context", {}).get("pages_used", []))
    pdf_evidence = len(result.get("pdf_context", {}).get("evidence_snippets", []))
    docs_used = len(result.get("pdf_context", {}).get("docs_used", []))
    if mode == "wiki" and wiki_pages >= 2:
        return "high"
    if mode in {"pdf", "hybrid"} and (pdf_evidence or docs_used):
        return "medium"
    return "low"
