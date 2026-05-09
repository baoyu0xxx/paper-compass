"""MCP server tool handlers for paper-compass."""

from __future__ import annotations

import os
import time
from typing import Any, Dict, List, Optional

from miniresearch.filters import get_paper_metadata, search_library, search_passages
from miniresearch.logging import emit_trace
from miniresearch.mcp_contracts import accepted_params, required_params
from miniresearch.models import UnifiedResponse
from miniresearch.router import ask_research
from miniresearch.wiki_store import save_query_to_wiki


def _tool_search_wiki(query: str, limit: int = 5, db_path: str = "data/vectordb") -> Dict[str, Any]:
    try:
        from miniresearch.embedder import Embedder
        import chromadb as _cdb
        from chromadb.config import Settings as _CSet

        _client = _cdb.PersistentClient(path=db_path, settings=_CSet(anonymized_telemetry=False))
        cols = _client.list_collections()
        wiki_col = next((c for c in cols if c.name.startswith("wiki_")), None)
        if not wiki_col:
            return UnifiedResponse.success(
                tool="search_wiki",
                data={"matches": [], "query_interpretation": "no wiki index found"},
                mode_used="wiki",
                confidence="low",
                next_action="Run build_index --wiki first",
            ).to_dict()

        sample = wiki_col.get(limit=1, include=["embeddings"])
        dim = 2048
        embeddings = sample.get("embeddings") if sample is not None else None
        if embeddings is not None and len(embeddings) > 0 and embeddings[0] is not None:
            dim = len(embeddings[0])

        embedder = Embedder()
        embedder.configure_cloud(
            "volcengine",
            os.environ.get("VOLC_EMBED_BASE_URL", ""),
            os.environ.get("VOLC_EMBED_API_KEY", ""),
            os.environ.get("VOLC_EMBED_MODEL", ""),
            dim,
        )
        q_emb = embedder.embed_single(query)

        results = wiki_col.query(
            query_embeddings=[q_emb],
            n_results=limit,
            include=["documents", "metadatas", "distances"],
        )

        matches = [
            {
                "page_path": (results["metadatas"][0][i] or {}).get("page_path", results["ids"][0][i]),
                "title": (results["metadatas"][0][i] or {}).get("title", results["ids"][0][i]),
                "page_type": (results["metadatas"][0][i] or {}).get("page_type", ""),
                "section": (results["metadatas"][0][i] or {}).get("section", ""),
                "snippet": results["documents"][0][i][:200],
                "score": round(1.0 / (1.0 + results["distances"][0][i]), 4),
            }
            for i in range(len(results["ids"][0]))
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
        results = search_library(query, filters=filters, limit=limit)
    except Exception as e:
        return UnifiedResponse.error("search_library", [str(e)]).to_dict()

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
    db_path: str = "data/vectordb",
) -> Dict[str, Any]:
    try:
        result = ask_research(
            query=query,
            force_mode=force_mode,
            filters=filters,
            max_sources=max_sources,
            db_path=db_path,
        )
    except Exception as e:
        return UnifiedResponse.error("ask_research", [str(e)]).to_dict()

    mode = result.get("mode_decision", {}).get("actual", "wiki")
    return UnifiedResponse.success(
        tool="ask_research",
        data=result,
        mode_used=mode,
        confidence="medium",
        sources=result.get("sources", []),
    ).to_dict()


def _tool_get_paper_metadata(id_or_doi: str) -> Dict[str, Any]:
    try:
        paper = get_paper_metadata(id_or_doi)
    except Exception as e:
        return UnifiedResponse.error("get_paper_metadata", [str(e)]).to_dict()

    if paper is None:
        return UnifiedResponse.error(
            "get_paper_metadata",
            [f"No paper found for: {id_or_doi}"],
            "Try search_library first or run sync_zotero",
        ).to_dict()

    return UnifiedResponse.success(
        tool="get_paper_metadata",
        data={
            "paper": {
                "doc_id": paper.get("key", ""),
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
        sources=[{"source_type": "pdf_doc", "id": paper.get("key", ""), "title": paper.get("title", "")}],
    ).to_dict()


def _tool_save_to_wiki(
    title: str,
    content: str,
    target_type: str = "queries",
    source_refs: Optional[List[str]] = None,
    confidence: str = "medium",
    tags: Optional[List[str]] = None,
    wiki_root: str = "./wiki",
) -> Dict[str, Any]:
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
        return UnifiedResponse.error("save_to_wiki", [str(e)]).to_dict()

    return UnifiedResponse.success(
        tool="save_to_wiki",
        data=result,
        mode_used="writeback",
        confidence=confidence,
        sources=[{"source_type": "wiki_page", "id": result["page_path"], "title": title}],
    ).to_dict()


def _tool_search_passages(
    query: str,
    search_mode: str = "semantic",
    limit: int = 10,
    filters: Optional[Dict[str, Any]] = None,
    db_path: str = "data/vectordb",
    text_dir: str = "data/texts",
    library_path: str = "data/zotero-export/library.json",
) -> Dict[str, Any]:
    try:
        results = search_passages(
            query=query,
            search_mode=search_mode,
            limit=limit,
            filters=filters,
            db_path=db_path,
            text_dir=text_dir,
            library_path=library_path,
        )
    except Exception as e:
        return UnifiedResponse.error("search_passages", [str(e)]).to_dict()

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
        next_action="Use ask_research for deeper analysis" if results else "Try broadening keywords or switch to hybrid mode",
    ).to_dict()


_HANDLERS = {
    "search_wiki": _tool_search_wiki,
    "search_library": _tool_search_library,
    "ask_research": _tool_ask_research,
    "get_paper_metadata": _tool_get_paper_metadata,
    "save_to_wiki": _tool_save_to_wiki,
    "search_passages": _tool_search_passages,
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

    allowed = set(accepted_params(tool_name))
    filtered = {k: v for k, v in params.items() if k in allowed}

    missing_required = [param for param in required_params(tool_name) if param not in filtered]

    if missing_required:
        response = UnifiedResponse.error(
            tool_name,
            [f"Missing required parameters: {', '.join(missing_required)}"],
            "Check tools/list inputSchema.required",
        ).to_dict()
        emit_trace({"tool": tool_name, "ok": False, "warnings": response.get("warnings", []), "error_type": "missing_required"})
        return response

    started = time.time()
    response = handler(**filtered)
    elapsed_ms = int((time.time() - started) * 1000)

    emit_trace(
        {
            "tool": tool_name,
            "ok": response.get("ok", False),
            "trace_id": response.get("trace_id", ""),
            "query": filtered.get("query", ""),
            "mode_used": response.get("mode_used", ""),
            "source_ids": [s.get("id", "") for s in response.get("sources", [])],
            "warnings": response.get("warnings", []),
            "elapsed_ms": elapsed_ms,
        }
    )
    return response
