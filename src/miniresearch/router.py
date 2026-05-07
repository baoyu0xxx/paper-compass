"""
Router module for paper-compass.

Decides whether a research query should be answered from wiki (breadth)
or escalated to PDF retrieval (depth), then executes accordingly.

The router encapsulates the logic described in the router_classify prompt:
- Default: wiki first
- Upgrade to PDF when detail-level evidence is needed
"""

from typing import Any, Dict, List, Optional

from miniresearch.models import ModeDecision, UnifiedResponse
from miniresearch.wiki_query import answer_from_wiki, search_wiki_pages
from miniresearch.filters import search_library


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


def _should_escalate_to_pdf(
    query: str,
    wiki_confidence: str,
    wiki_match_count: int,
) -> ModeDecision:
    """Determine whether to escalate to PDF retrieval.

    Returns a ModeDecision explaining the choice.
    """
    query_lower = query.lower()

    # Explicit trigger words?
    triggers_hit = [t for t in _DETAIL_TRIGGERS if t in query_lower]

    if triggers_hit:
        return ModeDecision(
            requested="auto",
            actual="hybrid",
            reason=(
                f"Query contains detail-level triggers: {', '.join(triggers_hit)}"
            ),
        )

    # Wiki confidence insufficient?
    if wiki_confidence == "low" and wiki_match_count == 0:
        return ModeDecision(
            requested="auto",
            actual="pdf",
            reason="Wiki has no relevant matches; escalating to PDF retrieval",
        )

    if wiki_confidence == "low":
        return ModeDecision(
            requested="auto",
            actual="hybrid",
            reason="Wiki confidence is low; supplementing with PDF retrieval",
        )

    # Default: wiki is sufficient
    return ModeDecision(
        requested="auto",
        actual="wiki",
        reason="Wiki provides adequate breadth coverage for this query",
    )


def ask_research(
    query: str,
    wiki_root: str = "./wiki",
    library_path: str = "data/zotero-export/library.json",
    force_mode: str = "auto",
    filters: Optional[Dict[str, Any]] = None,
    max_sources: int = 5,
) -> Dict[str, Any]:
    """Answer a research question using the appropriate retrieval layer.

    This is the main entry point for the ask_research tool.
    It:
      1. Searches wiki for existing knowledge
      2. Decides whether to escalate to PDF/library search
      3. Returns a unified answer with mode decision and sources

    Args:
        query: The research question.
        wiki_root: Path to the wiki directory.
        library_path: Path to library.json.
        force_mode: 'auto', 'wiki', 'pdf', or 'hybrid'.
        filters: Optional collection/tag/author/year filters.
        max_sources: Max sources to return.

    Returns:
        Dict suitable for serialization as UnifiedResponse data.
    """
    warnings: List[str] = []

    # Step 1: Always search wiki
    wiki_pages = search_wiki_pages(query, wiki_root=wiki_root, limit=5)
    wiki_answer = answer_from_wiki(query, wiki_root=wiki_root, max_pages=3)

    # Step 2: Decide mode
    if force_mode in ("wiki", "pdf", "hybrid"):
        mode_decision = ModeDecision(
            requested=force_mode,
            actual=force_mode,
            reason=f"Mode forced to {force_mode} by caller",
        )
    else:
        mode_decision = _should_escalate_to_pdf(
            query,
            wiki_answer["confidence"],
            len(wiki_pages),
        )

    # Step 3: Execute based on mode
    pdf_context = {
        "docs_used": [],
        "evidence_snippets": [],
    }

    if mode_decision.actual in ("pdf", "hybrid"):
        try:
            lib_results = search_library(
                query, library_path=library_path, filters=filters, limit=max_sources
            )
            if lib_results:
                pdf_context["docs_used"] = [
                    {
                        "doc_id": m.doc_id,
                        "title": m.title,
                        "year": m.year,
                    }
                    for m in lib_results
                ]
        except Exception as e:
            warnings.append(f"Library search failed: {e}")

    # Step 4: Assemble answer
    answer_parts = []

    if mode_decision.actual in ("wiki", "hybrid"):
        answer_parts.append(f"[Wiki context]\n{wiki_answer['answer_text']}")

    if mode_decision.actual in ("pdf", "hybrid") and pdf_context["docs_used"]:
        docs_list = "\n".join(
            f"- {d['title']} ({d.get('year', 'n.d.')}) [doc_id: {d['doc_id']}]"
            for d in pdf_context["docs_used"]
        )
        answer_parts.append(
            f"\n[Library matches]\nThe following papers may be relevant:\n{docs_list}"
        )
    elif mode_decision.actual == "pdf" and not pdf_context["docs_used"]:
        warnings.append(
            "PDF retrieval requested but no library matches found. "
            "Ensure library.json has been generated via sync_zotero."
        )

    answer = "\n".join(answer_parts) if answer_parts else wiki_answer["answer_text"]

    # Determine confidence
    confidence = wiki_answer.get("confidence", "low")
    if mode_decision.actual == "hybrid" and pdf_context["docs_used"]:
        confidence = "medium"
    elif mode_decision.actual == "pdf" and pdf_context["docs_used"]:
        confidence = "medium"

    # Suggest writeback?
    suggested_writeback = {
        "recommended": confidence != "low" and len(pdf_context["docs_used"]) > 1,
        "target_type": "queries",
        "reason": (
            "Multi-source synthesis with reuse value"
            if len(pdf_context["docs_used"]) > 1
            else ""
        ),
    }

    return {
        "answer": answer,
        "mode_decision": {
            "requested": mode_decision.requested,
            "actual": mode_decision.actual,
            "reason": mode_decision.reason,
        },
        "wiki_context": {
            "pages_used": wiki_answer.get("pages_used", []),
            "summary": wiki_answer.get("answer_text", ""),
        },
        "pdf_context": pdf_context,
        "suggested_writeback": suggested_writeback,
    }
