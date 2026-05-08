"""
MCP server for paper-compass — exposes 5 tools over the new architecture.

Tools (unchanged API, new backends):
  1. search_wiki      — vector search over ChromaDB wiki collection
  2. search_library   — keyword + metadata filter search
  3. ask_research     — auto-routed wiki → PDF/hybrid retrieval
  4. get_paper_metadata — single paper lookup by key/DOI
  5. save_to_wiki     — write LLM-generated content to wiki
"""

from __future__ import annotations

import os
from typing import Any, Dict, List, Optional

from miniresearch.models import UnifiedResponse
from miniresearch.filters import search_library, get_paper_metadata, vector_search
from miniresearch.router import ask_research
from miniresearch.wiki_store import save_query_to_wiki


def _tool_search_wiki(
    query: str,
    limit: int = 5,
    db_path: str = "data/vectordb",
) -> Dict[str, Any]:
    try:
        from miniresearch.embedder import Embedder
        import chromadb as _cdb
        from chromadb.config import Settings as _CSet

        _client = _cdb.PersistentClient(path=db_path, settings=_CSet(anonymized_telemetry=False))
        cols = _client.list_collections()
        wiki_col = next((c for c in cols if c.name.startswith("wiki_")), None)
        if not wiki_col:
            return UnifiedResponse.success(
                tool="search_wiki", data={"matches": [], "query_interpretation": "no wiki index found"},
                mode_used="wiki", confidence="low", next_action="Run build_index --wiki first"
            ).to_dict()
        
        model_meta = wiki_col.metadata.get("embedding_model", "volcengine:unknown")
        _sample = wiki_col.get(limit=1, include=["embeddings"])
        dim = 2048
        if _sample and _sample.get("embeddings") is not None and len(_sample["embeddings"]) > 0:
            dim = len(_sample["embeddings"][0])

        embedder = Embedder()
        embedder.configure_cloud("volcengine",
            os.environ.get("VOLC_EMBED_BASE_URL", ""),
            os.environ.get("VOLC_EMBED_API_KEY", ""),
            os.environ.get("VOLC_EMBED_MODEL", ""), dim)
        q_emb = embedder.embed_single(query)

        # Use the same client for search (don't create a second one)
        results = wiki_col.query(query_embeddings=[q_emb], n_results=limit,
                                 include=["documents", "metadatas", "distances"])

        matches = [
            {
                "page_path": (results["metadatas"][0][i] or {}).get("page_path", results["ids"][0][i]),
                "title": (results["metadatas"][0][i] or {}).get("title", results["ids"][0][i]),
                "snippet": results["documents"][0][i][:200],
                "score": round(1.0 / (1.0 + results["distances"][0][i]), 4),
            }
            for i in range(len(results["ids"][0]))
        ]

        confidence = "high" if matches and matches[0]["score"] > 0.5 else "medium" if matches else "low"
        return UnifiedResponse.success(
            tool="search_wiki", data={"matches": matches, "query_interpretation": "semantic wiki search"},
            mode_used="wiki", confidence=confidence,
            sources=[{"source_type":"wiki_page","id":m["page_path"],"title":m["title"]} for m in matches],
        ).to_dict()
    except Exception as e:
        return UnifiedResponse.error("search_wiki", [str(e)]).to_dict()


def _tool_search_library(
    query: str,
    filters: Optional[Dict[str, Any]] = None,
    limit: int = 10,
) -> Dict[str, Any]:
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
) -> Dict[str, Any]:
    try:
        result = ask_research(query=query, force_mode=force_mode, filters=filters, max_sources=max_sources)
    except Exception as e:
        return UnifiedResponse.error("ask_research", [str(e)]).to_dict()

    mode = result.get("mode_decision", {}).get("actual", "wiki")
    return UnifiedResponse.success(
        tool="ask_research",
        data=result,
        mode_used=mode,
        confidence="medium",
        sources=[],  # populated inside result
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
) -> Dict[str, Any]:
    try:
        result = save_query_to_wiki(
            title=title, content=content, target_type=target_type,
            source_refs=source_refs or [], confidence=confidence,
            tags=tags or [],
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


# ── dispatcher ────────────────────────────────────────────────────────────────

_HANDLERS = {
    "search_wiki": _tool_search_wiki,
    "search_library": _tool_search_library,
    "ask_research": _tool_ask_research,
    "get_paper_metadata": _tool_get_paper_metadata,
    "save_to_wiki": _tool_save_to_wiki,
}


def handle_tool(tool_name: str, params: Dict[str, Any]) -> Dict[str, Any]:
    handler = _HANDLERS.get(tool_name)
    if handler is None:
        return UnifiedResponse.error(tool_name, [f"Unknown tool. Available: {list(_HANDLERS.keys())}"]).to_dict()

    import inspect
    sig = inspect.signature(handler)
    accepted = set(sig.parameters.keys())
    filtered = {k: v for k, v in params.items() if k in accepted}
    return handler(**filtered)
