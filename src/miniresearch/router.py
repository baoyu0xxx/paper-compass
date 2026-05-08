"""
Router module for paper-compass.

Decides retrieval strategy (wiki vs papers vs hybrid) and executes queries.

Uses ChromaDB vector search for wiki + PDF chunks, with keyword fallback.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from miniresearch.models import ModeDecision


# Keywords that trigger PDF escalation
_DETAIL_TRIGGERS = [
    "exact wording", "page", "evidence", "citation",
    "variable definition", "identification strategy",
    "sample construction", "robustness check",
    "summary statistics", "regression table",
    "coefficient", "standard error", "p-value",
    "specification", "robustness", "placebo",
    "mechanism", "heterogeneity",
]


def _should_escalate(query: str, wiki_count: int, wiki_top_score: float) -> ModeDecision:
    query_lower = query.lower()
    triggers = [t for t in _DETAIL_TRIGGERS if t in query_lower]

    if triggers:
        return ModeDecision(requested="auto", actual="hybrid",
                           reason=f"Detail triggers: {', '.join(triggers)}")
    if wiki_count == 0:
        return ModeDecision(requested="auto", actual="pdf",
                           reason="No wiki matches")
    if wiki_top_score < 0.3:
        return ModeDecision(requested="auto", actual="hybrid",
                           reason="Wiki matches have low relevance")
    return ModeDecision(requested="auto", actual="wiki",
                       reason="Wiki provides adequate coverage")


def ask_research(
    query: str,
    wiki_root: str = "./wiki",
    library_path: str = "data/zotero-export/library.json",
    force_mode: str = "auto",
    filters: Optional[Dict[str, Any]] = None,
    max_sources: int = 5,
    db_path: str = "data/vectordb",
) -> Dict[str, Any]:
    """Multi-layer research query with auto-routing.

    1. Search wiki vector store
    2. Search library metadata
    3. If escalation needed, search PDF chunks vector store
    4. Merge and return
    """

    # Step 1: Wiki search
    from miniresearch.filters import vector_search
    wiki_results = vector_search(query, collection="wiki", k=5, db_path=db_path)
    wiki_top_score = wiki_results[0]["score"] if wiki_results else 0.0

    # Step 2: Decide mode
    if force_mode in ("wiki", "pdf", "hybrid"):
        mode = ModeDecision(requested=force_mode, actual=force_mode,
                           reason=f"Forced to {force_mode}")
    else:
        mode = _should_escalate(query, len(wiki_results), wiki_top_score)

    # Step 3: Library metadata search
    from miniresearch.filters import search_library
    lib_results = search_library(query, library_path=library_path, filters=filters, limit=max_sources)

    # Step 4: PDF chunk search if escalation
    pdf_chunks = []
    if mode.actual in ("pdf", "hybrid"):
        pdf_chunks = vector_search(query, collection="papers", k=max_sources, db_path=db_path)

    # Step 5: Assemble answer
    parts = []
    sources: List[Dict[str, str]] = []

    if wiki_results:
        parts.append("[Wiki knowledge]")
        for w in wiki_results[:3]:
            meta = w.get("metadata", {})
            parts.append(f"- {meta.get('title', w['id'])}: {w['document'][:200]}...")
            sources.append({"source_type": "wiki_page", "id": w["id"],
                          "title": meta.get("title", w["id"])})

    if lib_results:
        parts.append("\n[Library matches]")
        for m in lib_results[:5]:
            parts.append(f"- {m['title']} ({m.get('year', 'n.d.')}) [{m['doc_id']}]")

    if pdf_chunks:
        parts.append("\n[PDF evidence]")
        for p in pdf_chunks[:5]:
            meta = p.get("metadata", {})
            parts.append(f"- [{meta.get('title', '?')}] p.{meta.get('page_num', '?')}: {p['document'][:200]}...")
            sources.append({"source_type": "pdf_doc", "id": meta.get("item_key", p["id"]),
                          "title": meta.get("title", "")})

    answer = "\n".join(parts) if parts else "No relevant information found."

    confidence = "low"
    if mode.actual == "wiki" and wiki_top_score > 0.5:
        confidence = "medium"
    elif mode.actual in ("pdf", "hybrid") and (pdf_chunks or lib_results):
        confidence = "medium"

    return {
        "answer": answer,
        "mode_decision": {
            "requested": mode.requested,
            "actual": mode.actual,
            "reason": mode.reason,
        },
        "wiki_context": {
            "pages_used": [{"title": w.get("metadata", {}).get("title", ""),
                           "page_path": w["id"]} for w in wiki_results[:3]],
        },
        "pdf_context": {
            "docs_used": [{"doc_id": m["doc_id"], "title": m["title"],
                          "year": m.get("year")} for m in lib_results[:5]],
            "evidence_snippets": [{"doc_id": p.get("metadata", {}).get("item_key", ""),
                                  "snippet": p["document"][:300]}
                                 for p in pdf_chunks[:5]],
        },
        "suggested_writeback": {
            "recommended": confidence != "low" and len(lib_results) > 1,
            "target_type": "queries",
        },
    }
