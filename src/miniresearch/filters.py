"""
Metadata filter module for paper-compass.

Provides filtering and ranking over library.json records
for the search_library and get_paper_metadata MCP tools.
"""

import json
import re
from pathlib import Path
from typing import Any, Dict, List, Optional

from miniresearch.models import LibraryMatch, PaperDetail


def load_library(library_path: str = "data/zotero-export/library.json") -> List[Dict[str, Any]]:
    """Load the library.json file.

    Returns:
        List of paper records from library.json.
    """
    path = Path(library_path)
    if not path.exists():
        return []

    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)

    if isinstance(data, list):
        return data
    return []


def _score_text(query: str, text: str) -> float:
    """Simple relevance score: count of query term matches."""
    if not query or not text:
        return 0.0
    query_lower = query.lower()
    text_lower = text.lower()
    score = 0.0
    for term in query_lower.split():
        score += text_lower.count(term)
    return score


def search_library(
    query: str,
    library_path: str = "data/zotero-export/library.json",
    filters: Optional[Dict[str, Any]] = None,
    limit: int = 10,
) -> List[LibraryMatch]:
    """Search library.json by query + metadata filters.

    Args:
        query: Search query string.
        library_path: Path to library.json.
        filters: Optional metadata filters:
            - collections: List[str]
            - tags: List[str]
            - authors: List[str]
            - year_from: int
            - year_to: int
        limit: Max results.

    Returns:
        List of LibraryMatch objects sorted by relevance.
    """
    records = load_library(library_path)
    if not records:
        return []

    if filters is None:
        filters = {}

    matches: List[tuple] = []  # (score, record)

    for rec in records:
        # Apply metadata filters
        if not _passes_filters(rec, filters):
            continue

        # Score relevance
        score = 0.0
        score += _score_text(query, rec.get("title", "")) * 3
        score += _score_text(query, " ".join(rec.get("authors", [])))
        score += _score_text(query, rec.get("journal", ""))
        score += _score_text(query, rec.get("doi", ""))
        score += _score_text(query, " ".join(rec.get("collections", []))) * 2
        score += _score_text(query, " ".join(rec.get("tags", []))) * 2

        matches.append((score, rec))

    # Sort descending by score
    matches.sort(key=lambda x: x[0], reverse=True)

    # Take top N with any positive score, or top N if all zero
    positive = [(s, r) for s, r in matches if s > 0]
    if not positive and query.strip():
        # Return empty if there's a query but no match
        return []

    results = positive if positive else matches
    results = results[:limit]

    return [
        LibraryMatch(
            doc_id=rec.get("doc_id", ""),
            title=rec.get("title", ""),
            authors=rec.get("authors", []),
            year=rec.get("year"),
            doi=rec.get("doi", ""),
            journal=rec.get("journal", ""),
            collections=rec.get("collections", []),
            tags=rec.get("tags", []),
            pdf_path=rec.get("pdf_path", ""),
            metadata_source=rec.get("metadata_source", ""),
            score=score,
        )
        for score, rec in results
    ]


def _passes_filters(rec: Dict[str, Any], filters: Dict[str, Any]) -> bool:
    """Check if a record passes all metadata filters."""
    # Collection filter (any match)
    if "collections" in filters and filters["collections"]:
        rec_cols = set(c.lower() for c in rec.get("collections", []))
        filter_cols = set(c.lower() for c in filters["collections"])
        if not rec_cols & filter_cols:
            return False

    # Tag filter (any match)
    if "tags" in filters and filters["tags"]:
        rec_tags = set(t.lower() for t in rec.get("tags", []))
        filter_tags = set(t.lower() for t in filters["tags"])
        if not rec_tags & filter_tags:
            return False

    # Author filter (any match)
    if "authors" in filters and filters["authors"]:
        rec_authors = set(a.lower() for a in rec.get("authors", []))
        filter_authors = set(a.lower() for a in filters["authors"])
        if not rec_authors & filter_authors:
            return False

    # Year range
    year = rec.get("year")
    if year is not None:
        if "year_from" in filters and filters["year_from"] is not None:
            if year < filters["year_from"]:
                return False
        if "year_to" in filters and filters["year_to"] is not None:
            if year > filters["year_to"]:
                return False

    return True


def get_paper_metadata(
    id_or_doi: str,
    library_path: str = "data/zotero-export/library.json",
) -> Optional[PaperDetail]:
    """Look up a single paper by doc_id or DOI.

    Args:
        id_or_doi: doc_id, DOI, or exact title.
        library_path: Path to library.json.

    Returns:
        PaperDetail if found, else None.
    """
    records = load_library(library_path)
    if not records:
        return None

    normalized = id_or_doi.strip()

    for rec in records:
        # Match by doc_id
        if rec.get("doc_id") == normalized:
            return _to_paper_detail(rec)
        # Match by DOI
        if rec.get("doi", "").strip().lower() == normalized.lower():
            return _to_paper_detail(rec)
        # Match by exact title
        if rec.get("title", "").strip().lower() == normalized.lower():
            return _to_paper_detail(rec)

    return None


def _to_paper_detail(rec: Dict[str, Any]) -> PaperDetail:
    return PaperDetail(
        doc_id=rec.get("doc_id", ""),
        title=rec.get("title", ""),
        authors=rec.get("authors", []),
        year=rec.get("year"),
        journal=rec.get("journal", ""),
        doi=rec.get("doi", ""),
        collections=rec.get("collections", []),
        tags=rec.get("tags", []),
        pdf_path=rec.get("pdf_path", ""),
        metadata_source=rec.get("metadata_source", ""),
    )
