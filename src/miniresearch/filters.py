"""
Search and filter layer for paper-compass.

Provides search_library (metadata + vector) and get_paper_metadata.
Uses ChromaDB vector_store + library.json metadata.
"""

from __future__ import annotations

import json
import os
import re
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

from miniresearch.env_utils import load_project_env


# ── library.json access ──────────────────────────────────────────────────────

def _load_library(library_path: str = "data/zotero-export/library.json") -> List[Dict[str, Any]]:
    path = Path(library_path)
    if not path.exists():
        return []
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


# ── search_library ───────────────────────────────────────────────────────────

def _normalize_text(text: str) -> str:
    text = (text or "").lower().strip()
    text = re.sub(r"[^\w\s]", " ", text)
    text = re.sub(r"\s+", " ", text)
    return text


def search_library(
    query: str,
    library_path: str = "data/zotero-export/library.json",
    filters: Optional[Dict[str, Any]] = None,
    limit: int = 10,
) -> List[Dict[str, Any]]:
    """Search the paper library by exact-match tiers + weighted metadata matching."""
    records = _load_library(library_path)
    if not records:
        return []

    if filters is None:
        filters = {}

    ql = query.lower().strip()
    q_norm = _normalize_text(query)

    scored: List[tuple] = []
    for rec in records:
        if not _passes_filters(rec, filters):
            continue

        title = rec.get("title", "")
        title_norm = _normalize_text(title)
        doi = (rec.get("doi", "") or "").lower().strip()
        key = (rec.get("key", "") or "").lower().strip()

        tier_bonus = 0.0
        if ql and ql == key:
            tier_bonus += 200.0
        if ql and doi and ql == doi:
            tier_bonus += 180.0
        if q_norm and q_norm == title_norm:
            tier_bonus += 120.0
        elif q_norm and q_norm in title_norm:
            tier_bonus += 50.0

        weighted = 0.0
        weighted += _score(ql, title) * 6
        weighted += _score(ql, ", ".join(rec.get("authors", []))) * 2
        weighted += _score(ql, rec.get("journal", "")) * 2
        weighted += _score(ql, ", ".join(rec.get("collections", []))) * 1.5
        weighted += _score(ql, ", ".join(rec.get("tags", []))) * 1.5

        score = tier_bonus + weighted
        if score > 0:
            scored.append((score, rec))

    scored.sort(key=lambda x: x[0], reverse=True)
    results = scored[:limit]

    return [
        {
            "doc_id": rec.get("key", ""),
            "title": rec.get("title", ""),
            "authors": rec.get("authors", []),
            "year": rec.get("year"),
            "doi": rec.get("doi", ""),
            "journal": "",
            "collections": rec.get("collections", []),
            "tags": rec.get("tags", []),
            "pdf_path": rec.get("pdf_path", ""),
            "metadata_source": "sqlite",
            "score": round(s, 2),
        }
        for s, rec in results
    ]


def _score(query: str, text: str) -> float:
    if not query or not text:
        return 0.0
    return sum(text.lower().count(t) for t in query.lower().split())


def _passes_filters(rec: Dict[str, Any], filters: Dict[str, Any]) -> bool:
    """Check metadata filters (collection, tag, author, year range)."""
    if "collections" in filters and filters["collections"]:
        rec_cols = set(c.lower() for c in rec.get("collections", []))
        filt_cols = set(c.lower() for c in filters["collections"])
        if not rec_cols & filt_cols:
            return False

    if "tags" in filters and filters["tags"]:
        rec_tags = set(t.lower() for t in rec.get("tags", []))
        filt_tags = set(t.lower() for t in filters["tags"])
        if not rec_tags & filt_tags:
            return False

    if "authors" in filters and filters["authors"]:
        rec_auth = set(a.lower() for a in rec.get("authors", []))
        filt_auth = set(a.lower() for a in filters["authors"])
        if not rec_auth & filt_auth:
            return False

    year = rec.get("year")
    if year is not None:
        if "year_from" in filters and filters["year_from"] is not None:
            if year < filters["year_from"]:
                return False
        if "year_to" in filters and filters["year_to"] is not None:
            if year > filters["year_to"]:
                return False

    return True


# ── get_paper_metadata ───────────────────────────────────────────────────────

def get_paper_metadata(
    id_or_doi: str,
    library_path: str = "data/zotero-export/library.json",
) -> Optional[Dict[str, Any]]:
    """Look up a single paper by Zotero key, doc_id, or DOI."""
    records = _load_library(library_path)
    if not records:
        return None

    normalized = id_or_doi.strip()

    for rec in records:
        if rec.get("key") == normalized:
            return rec
        if rec.get("doi", "").strip().lower() == normalized.lower():
            return rec
        if rec.get("title", "").strip().lower() == normalized.lower():
            return rec

    return None


# ── vector search (if store available) ───────────────────────────────────────

def vector_search(
    query: str,
    collection: str = "papers",
    k: int = 10,
    db_path: str = "data/vectordb",
) -> List[Dict[str, Any]]:
    """Semantic vector search using ChromaDB.

    Auto-detects embedding model and dimension from existing collections.
    """
    from miniresearch.embedder import Embedder
    from miniresearch.vector_store import VectorStore
    import chromadb as _cdb
    from chromadb.config import Settings as _CSet

    load_project_env()

    db_dir = Path(db_path)
    if not db_dir.exists():
        return []

    # Discover collections via ChromaDB API (same Settings as VectorStore)
    _client = _cdb.PersistentClient(path=db_path, settings=_CSet(anonymized_telemetry=False))
    try:
        cols = _client.list_collections()
        matching = [c for c in cols if c.name.startswith(collection + "_")]
        if not matching:
            return []

        # Get model_id from collection metadata
        meta = matching[0].metadata
        model_id = meta.get("embedding_model", "volcengine:unknown")

        # Detect vector dimension
        _sample = matching[0].get(limit=1, include=["embeddings"])
        actual_dim = 2048
        embeddings = _sample.get("embeddings") if _sample is not None else None
        if embeddings is not None and len(embeddings) > 0 and embeddings[0] is not None:
            actual_dim = len(embeddings[0])
    finally:
        _client.clear_system_cache()

    embedder = Embedder()
    embedder.configure_cloud("volcengine",
        os.environ.get("VOLC_EMBED_BASE_URL", ""),
        os.environ.get("VOLC_EMBED_API_KEY", ""),
        os.environ.get("VOLC_EMBED_MODEL", ""),
        actual_dim)

    store = VectorStore(db_path=db_path, collection_name=collection,
                       embedding_model_id=model_id)
    query_emb = embedder.embed_single(query)
    results = store.search(query_emb, k=k)

    formatted = []
    for i, chunk_id in enumerate(results["ids"]):
        meta = results["metadatas"][i] if results["metadatas"] else {}
        formatted.append({
            "id": chunk_id,
            "document": results["documents"][i],
            "metadata": meta,
            "distance": results["distances"][i],
            "score": round(1.0 / (1.0 + results["distances"][i]), 4),
        })
    return formatted


def _cap_results_per_group(
    results: List[Dict[str, Any]],
    max_per_group: int,
    group_key_fn: Callable[[Dict[str, Any]], Optional[str]],
) -> List[Dict[str, Any]]:
    """Keep top-scoring results while capping entries per logical group."""
    group_count: Dict[str, int] = {}
    deduped: List[Dict[str, Any]] = []
    for result in sorted(results, key=lambda x: x["score"], reverse=True):
        group_key = group_key_fn(result)
        if not group_key:
            deduped.append(result)
            continue
        if group_count.get(group_key, 0) >= max_per_group:
            continue
        group_count[group_key] = group_count.get(group_key, 0) + 1
        deduped.append(result)

    deduped.sort(key=lambda x: x["score"], reverse=True)
    return deduped


def _postprocess_wiki_results(results: List[Dict[str, Any]], max_per_page: int = 2,
                               section_0_penalty: float = 0.92) -> List[Dict[str, Any]]:
    """Post-process wiki search results to reduce noise.

    Applies:
    1. Drop chunks from excluded pages (log.md, index.md) — safety net
       even if the vector DB still contains old data.
    2. Light penalty for section 0 (frontmatter contamination).
    3. Page-level dedup: at most max_per_page sections per page.

    Args:
        results: Raw results from vector_search().
        max_per_page: Max chunk count per wiki page.
        section_0_penalty: Score multiplier for section == 0.

    Returns:
        Filtered and re-ranked results.
    """
    # 1. Drop known-noise pages
    filtered = [
        r for r in results
        if r.get("metadata", {}).get("page_path", "").split("/")[-1] not in {"log.md", "index.md"}
    ]

    # 2. Apply section 0 penalty
    for r in filtered:
        section = r.get("metadata", {}).get("section")
        if section == 0 or section == "0":
            r["score"] = r["score"] * section_0_penalty

    # 3. Page-level dedup: limit sections per page
    return _cap_results_per_group(
        filtered,
        max_per_group=max_per_page,
        group_key_fn=lambda r: r.get("metadata", {}).get("page_path", r["id"]),
    )


def _dedupe_pdf_chunks_by_item(results: List[Dict[str, Any]],
                                max_per_item: int = 2) -> List[Dict[str, Any]]:
    """Deduplicate PDF chunk results by item_key.

    At most max_per_item chunks per paper item are retained, keeping
    the highest-scoring ones. This prevents a single paper from flooding
    the result list.

    Args:
        results: Raw results from vector_search() on papers collection.
        max_per_item: Max chunk count per paper item.

    Returns:
        Deduplicated, score-sorted results.
    """
    return _cap_results_per_group(
        results,
        max_per_group=max_per_item,
        group_key_fn=lambda r: r.get("metadata", {}).get("item_key") or None,
    )
