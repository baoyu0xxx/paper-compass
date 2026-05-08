"""
Search and filter layer for paper-compass.

Provides search_library (metadata + vector) and get_paper_metadata.
Uses ChromaDB vector_store + library.json metadata.
"""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any, Dict, List, Optional

from miniresearch.models import LibraryMatch, PaperDetail


# ── library.json access ──────────────────────────────────────────────────────

def _load_library(library_path: str = "data/zotero-export/library.json") -> List[Dict[str, Any]]:
    path = Path(library_path)
    if not path.exists():
        return []
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def _load_env():
    env_path = Path(__file__).resolve().parent.parent.parent / ".env"
    if env_path.exists():
        for line in env_path.read_text().splitlines():
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                key, _, val = line.partition("=")
                if val and not os.environ.get(key.strip()):
                    os.environ[key.strip()] = val.strip()


# ── search_library ───────────────────────────────────────────────────────────

def search_library(
    query: str,
    library_path: str = "data/zotero-export/library.json",
    filters: Optional[Dict[str, Any]] = None,
    limit: int = 10,
) -> List[Dict[str, Any]]:
    """Search the paper library by keyword + metadata filters.

    Falls back to in-memory text matching if vector store is unavailable.
    """
    records = _load_library(library_path)
    if not records:
        return []

    if filters is None:
        filters = {}

    # Text scoring
    scored: List[tuple] = []

    for rec in records:
        if not _passes_filters(rec, filters):
            continue

        score = 0.0
        ql = query.lower()
        score += _score(ql, rec.get("title", "")) * 3
        score += _score(ql, ", ".join(rec.get("authors", [])))
        score += _score(ql, rec.get("journal", ""))
        score += _score(ql, ", ".join(rec.get("collections", []))) * 2
        score += _score(ql, ", ".join(rec.get("tags", []))) * 2
        scored.append((score, rec))

    scored.sort(key=lambda x: x[0], reverse=True)
    positive = [(s, r) for s, r in scored if s > 0]
    results = positive[:limit] if positive else []

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

    Args:
        query: Search query.
        collection: 'papers' or 'wiki'.
        k: Number of results.
        db_path: ChromaDB directory.

    Returns:
        List of result dicts with id, document, metadata, score.
    """
    try:
        from miniresearch.embedder import Embedder
        from miniresearch.vector_store import VectorStore

        _load_env()

        embedder = Embedder()
        # Try to auto-detect model from existing collection
        try:
            import chromadb
            client = chromadb.PersistentClient(path=db_path)
            cols = client.list_collections()
            matching = [c for c in cols if c.name.startswith(collection)]
            if matching:
                # Use first matching collection's model
                store = VectorStore(db_path=db_path, collection_name=collection,
                                   embedding_model_id="volcengine:doubao-embedding-vision-250615")
                embedder.configure_cloud(
                    provider="volcengine",
                    base_url=os.environ.get("VOLC_EMBED_BASE_URL", ""),
                    api_key=os.environ.get("VOLC_EMBED_API_KEY", ""),
                    model=os.environ.get("VOLC_EMBED_MODEL", ""),
                    dimension=1024,
                )
            else:
                return []
        except Exception:
            return []

        query_emb = embedder.embed_single(query)
        results = store.search(query_emb, k=k)

        formatted = []
        for i, chunk_id in enumerate(results["ids"]):
            formatted.append({
                "id": chunk_id,
                "document": results["documents"][i],
                "metadata": results["metadatas"][i] if results["metadatas"] else {},
                "distance": results["distances"][i],
                "score": round(1.0 / (1.0 + results["distances"][i]), 4),
            })
        return formatted

    except Exception:
        return []
