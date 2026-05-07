"""
MCP server for paper-compass.

Exposes 5 tools to agent consumers (Hermes, etc.):
  1. search_wiki      — breadth retrieval from markdown wiki
  2. search_library   — metadata-level paper search
  3. ask_research     — multi-layer answering with auto-routing
  4. get_paper_metadata — single paper detail lookup
  5. save_to_wiki     — write curated results back to wiki

All tools return the UnifiedResponse envelope schema.
"""

from typing import Any, Dict, List, Optional

from miniresearch.config import load_all_configs
from miniresearch.filters import search_library, get_paper_metadata
from miniresearch.wiki_query import search_wiki_pages, answer_from_wiki
from miniresearch.wiki_ingest import save_query_to_wiki
from miniresearch.router import ask_research
from miniresearch.models import UnifiedResponse


# ── config loading ────────────────────────────────────────────────────────────

def _load_project_config() -> Dict[str, Any]:
    """Load project config (paths, wiki, rag, mcp, providers).

    Returns empty dict on failure to be resilient.
    """
    try:
        return load_all_configs("configs")
    except Exception:
        return {}


# ── Tool 1: search_wiki ──────────────────────────────────────────────────────

def _tool_search_wiki(
    query: str,
    limit: int = 5,
    page_types: Optional[List[str]] = None,
    return_snippets: bool = True,
) -> Dict[str, Any]:
    cfg = _load_project_config()
    wiki_root = (
        cfg.get("paths", {}).get("paths", {}).get("wiki_root", "./wiki")
    )

    try:
        results = search_wiki_pages(
            query,
            wiki_root=wiki_root,
            limit=limit,
            page_types=page_types,
            return_snippets=return_snippets,
        )
    except Exception as e:
        return UnifiedResponse.error(
            tool="search_wiki",
            warnings=[f"search_wiki failed: {e}"],
        ).to_dict()

    matches = [
        {
            "page_path": r["page_path"],
            "title": r["title"],
            "page_type": r.get("page_type", ""),
            "summary": r.get("summary", ""),
            "snippet": r.get("snippet", ""),
            "score": r["score"],
        }
        for r in results
    ]

    confidence = "high" if matches and matches[0]["score"] > 5 else "medium" if matches else "low"

    next_action = ""
    if not matches:
        next_action = "Try search_library or ask_research to expand the search"
    elif confidence == "low":
        next_action = "Consider ask_research for deeper PDF retrieval"

    return UnifiedResponse.success(
        tool="search_wiki",
        data={
            "matches": matches,
            "query_interpretation": "broad wiki lookup",
        },
        mode_used="wiki",
        confidence=confidence,
        sources=[{"source_type": "wiki_page", "id": m["page_path"], "title": m["title"]} for m in matches],
        next_action=next_action,
    ).to_dict()


# ── Tool 2: search_library ────────────────────────────────────────────────────

def _tool_search_library(
    query: str,
    filters: Optional[Dict[str, Any]] = None,
    limit: int = 10,
    sort_by: str = "relevance",
) -> Dict[str, Any]:
    cfg = _load_project_config()
    library_path = (
        cfg.get("paths", {}).get("paths", {}).get("library_json_path", "data/zotero-export/library.json")
    )

    try:
        results = search_library(
            query,
            library_path=library_path,
            filters=filters,
            limit=limit,
        )
    except Exception as e:
        return UnifiedResponse.error(
            tool="search_library",
            warnings=[f"search_library failed: {e}"],
            next_action="Run sync_zotero to generate library.json",
        ).to_dict()

    matches = [
        {
            "doc_id": m.doc_id,
            "title": m.title,
            "authors": m.authors,
            "year": m.year,
            "doi": m.doi,
            "collections": m.collections,
            "tags": m.tags,
            "pdf_path": m.pdf_path,
            "score": m.score,
        }
        for m in results
    ]

    confidence = "high" if matches and matches[0]["score"] > 3 else "medium" if matches else "low"
    next_action = (
        "Use ask_research for deeper analysis of these results"
        if matches else
        "Try broadening filters or running sync_zotero first"
    )

    return UnifiedResponse.success(
        tool="search_library",
        data={
            "matches": matches,
            "filters_used": filters or {},
        },
        mode_used="library",
        confidence=confidence,
        sources=[
            {"source_type": "pdf_doc", "id": m["doc_id"], "title": m["title"]}
            for m in matches
        ],
        next_action=next_action,
    ).to_dict()


# ── Tool 3: ask_research ──────────────────────────────────────────────────────

def _tool_ask_research(
    query: str,
    filters: Optional[Dict[str, Any]] = None,
    force_mode: str = "auto",
    save_candidate: bool = False,
    max_sources: int = 5,
) -> Dict[str, Any]:
    cfg = _load_project_config()
    paths = cfg.get("paths", {}).get("paths", {})
    wiki_root = paths.get("wiki_root", "./wiki")
    library_path = paths.get("library_json_path", "data/zotero-export/library.json")

    try:
        result = ask_research(
            query=query,
            wiki_root=wiki_root,
            library_path=library_path,
            force_mode=force_mode,
            filters=filters,
            max_sources=max_sources,
        )
    except Exception as e:
        return UnifiedResponse.error(
            tool="ask_research",
            warnings=[f"ask_research failed: {e}"],
        ).to_dict()

    mode = result.get("mode_decision", {}).get("actual", "wiki")
    confidence = "medium"
    if mode == "hybrid" and result.get("pdf_context", {}).get("docs_used"):
        confidence = "medium"

    # Sources from wiki + pdf
    sources = []
    for p in result.get("wiki_context", {}).get("pages_used", []):
        sources.append(
            {"source_type": "wiki_page", "id": p.get("page_path", ""), "title": p.get("title", "")}
        )
    for d in result.get("pdf_context", {}).get("docs_used", []):
        sources.append(
            {"source_type": "pdf_doc", "id": d.get("doc_id", ""), "title": d.get("title", "")}
        )

    next_action = ""
    wb = result.get("suggested_writeback", {})
    if wb.get("recommended") and save_candidate:
        next_action = f"Consider save_to_wiki with type={wb.get('target_type', 'queries')}"

    return UnifiedResponse.success(
        tool="ask_research",
        data=result,
        mode_used=mode,
        confidence=confidence,
        sources=sources,
        next_action=next_action,
    ).to_dict()


# ── Tool 4: get_paper_metadata ────────────────────────────────────────────────

def _tool_get_paper_metadata(
    id_or_doi: str,
) -> Dict[str, Any]:
    cfg = _load_project_config()
    library_path = (
        cfg.get("paths", {}).get("paths", {}).get("library_json_path", "data/zotero-export/library.json")
    )

    try:
        paper = get_paper_metadata(id_or_doi, library_path=library_path)
    except Exception as e:
        return UnifiedResponse.error(
            tool="get_paper_metadata",
            warnings=[f"get_paper_metadata failed: {e}"],
        ).to_dict()

    if paper is None:
        return UnifiedResponse.error(
            tool="get_paper_metadata",
            warnings=[f"No paper found for: {id_or_doi}"],
            next_action="Try search_library to find the paper first, or run sync_zotero",
        ).to_dict()

    return UnifiedResponse.success(
        tool="get_paper_metadata",
        data={
            "paper": {
                "doc_id": paper.doc_id,
                "title": paper.title,
                "authors": paper.authors,
                "year": paper.year,
                "journal": paper.journal,
                "doi": paper.doi,
                "collections": paper.collections,
                "tags": paper.tags,
                "pdf_path": paper.pdf_path,
                "metadata_source": paper.metadata_source,
            }
        },
        mode_used="library",
        confidence="high" if paper.metadata_source != "scan_only" else "medium",
        sources=[
            {"source_type": "pdf_doc", "id": paper.doc_id, "title": paper.title}
        ],
        next_action="Use ask_research to analyze this paper in depth",
    ).to_dict()


# ── Tool 5: save_to_wiki ──────────────────────────────────────────────────────

def _tool_save_to_wiki(
    title: str,
    content: str,
    target_type: str = "queries",
    source_refs: Optional[List[str]] = None,
    confidence: str = "medium",
    tags: Optional[List[str]] = None,
) -> Dict[str, Any]:
    cfg = _load_project_config()
    wiki_root = (
        cfg.get("paths", {}).get("paths", {}).get("wiki_root", "./wiki")
    )

    try:
        result = save_query_to_wiki(
            title=title,
            content=content,
            target_type=target_type,
            source_refs=source_refs or [],
            confidence=confidence,
            tags=tags or [],
            wiki_root=wiki_root,
        )
    except Exception as e:
        return UnifiedResponse.error(
            tool="save_to_wiki",
            warnings=[f"save_to_wiki failed: {e}"],
        ).to_dict()

    return UnifiedResponse.success(
        tool="save_to_wiki",
        data={
            "page_path": result["page_path"],
            "created": result["created"],
            "linked_pages": result["linked_pages"],
            "log_updated": result["log_updated"],
            "index_updated": result["index_updated"],
        },
        mode_used="writeback",
        confidence=confidence,
        sources=[
            {"source_type": "wiki_page", "id": result["page_path"], "title": title}
        ],
    ).to_dict()


# ── Tool router ───────────────────────────────────────────────────────────────

def handle_tool(
    tool_name: str,
    params: Dict[str, Any],
) -> Dict[str, Any]:
    """Dispatch an MCP tool call to the correct handler.

    Args:
        tool_name: One of the 5 MCP tool names.
        params: Tool-specific parameters dict.

    Returns:
        UnifiedResponse as a dict.
    """
    handlers = {
        "search_wiki": _tool_search_wiki,
        "search_library": _tool_search_library,
        "ask_research": _tool_ask_research,
        "get_paper_metadata": _tool_get_paper_metadata,
        "save_to_wiki": _tool_save_to_wiki,
    }

    handler = handlers.get(tool_name)
    if handler is None:
        return UnifiedResponse.error(
            tool=tool_name,
            warnings=[f"Unknown tool: {tool_name}. Available: {list(handlers.keys())}"],
        ).to_dict()

    # Filter params to only those the handler accepts
    import inspect
    sig = inspect.signature(handler)
    accepted = set(sig.parameters.keys())
    filtered = {k: v for k, v in params.items() if k in accepted}

    return handler(**filtered)
