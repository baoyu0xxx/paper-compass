"""
Search and filter layer for paper-compass.

Provides search_library (metadata + vector) and get_paper_metadata.
Uses ChromaDB vector_store + library.json metadata.
"""

from __future__ import annotations

import json
import os
import re
import threading
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

from paper_compass.env_utils import PROJECT_ROOT, load_project_env
from paper_compass.config import load_all_configs, get_provider_config

DEFAULT_LIBRARY_PATH = PROJECT_ROOT / "data" / "zotero-export" / "library.json"
DEFAULT_TEXT_DIR = PROJECT_ROOT / "data" / "texts"
DEFAULT_VECTORDB_PATH = PROJECT_ROOT / "data" / "vectordb"


def _resolved_path(path: str | None, default: Path) -> str:
    return str(Path(path)) if path else str(default)

# ── Shared PersistentClient singleton ────────────────────────────────────────
# Avoids creating multiple PersistentClient instances for the same db_path,
# which is both slower (double segment load) and error-prone per ChromaDB docs.

_client: Any = None
_client_path: Optional[str] = None
_lock = threading.Lock()


def _get_client(db_path: str) -> Any:
    """Return a shared ChromaDB PersistentClient for *db_path*.

    All callers in this module share one instance so that HNSW segment
    data loaded by ``get_vector_collection_info`` stays warm for
    ``vector_search`` / ``VectorStore``.
    """
    global _client, _client_path
    with _lock:
        if _client is None or _client_path != db_path:
            import chromadb as _cdb
            from chromadb.config import Settings as _CSet
            # Ensure .env is loaded before the first client creation so
            # that any env-dependent ChromaDB settings are respected.
            load_project_env()
            _client = _cdb.PersistentClient(
                path=db_path, settings=_CSet(anonymized_telemetry=False)
            )
            _client_path = db_path
        return _client


# ── library.json access ──────────────────────────────────────────────────────

def _load_library(library_path: str | None = None) -> List[Dict[str, Any]]:
    path = Path(_resolved_path(library_path, DEFAULT_LIBRARY_PATH))
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
    library_path: str | None = None,
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
        weighted += _score(ql, rec.get("abstract", "")) * 2  # abstract scoring

        # Fuzzy title match bonus
        fuzzy_bonus = _fuzzy_title_match(q_norm, title_norm)
        weighted += fuzzy_bonus

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
    text_lower = text.lower()
    ql = query.lower()
    # Standard word-based scoring
    word_score = sum(text_lower.count(t) for t in ql.split())
    # Chinese: also try bigram matching for multi-char Chinese queries
    cjk_score = _score_chinese_bigrams(ql, text_lower)
    return max(word_score, cjk_score)


def _score_chinese_bigrams(query_lower: str, text_lower: str) -> float:
    """Score Chinese text by matching overlapping bigrams.

    For a Chinese query like "代际收入流动", generates:
        ["代际", "际收", "收入", "入流", "流动"]
    and counts how many appear in the target text.
    """
    # Detect if query has significant CJK content
    cjk_chars = sum(1 for c in query_lower if '\u4e00' <= c <= '\u9fff')
    if cjk_chars < 2:
        return 0.0
    # Build bigrams
    bigrams = []
    for i in range(len(query_lower) - 1):
        c1, c2 = query_lower[i], query_lower[i + 1]
        if '\u4e00' <= c1 <= '\u9fff' and '\u4e00' <= c2 <= '\u9fff':
            bigrams.append(c1 + c2)
    if not bigrams:
        return 0.0
    hits = sum(1 for bg in bigrams if bg in text_lower)
    return hits * 1.5  # weight per bigram hit


def _fuzzy_title_match(query_norm: str, title_norm: str) -> float:
    """Compute fuzzy match score between query and title.

    Returns a bonus (0–30) for near-exact matches.
    """
    if len(query_norm) < 4 or len(title_norm) < 4:
        return 0.0
    from difflib import SequenceMatcher
    ratio = SequenceMatcher(None, query_norm, title_norm).ratio()
    if ratio >= 0.95:
        return 30.0
    if ratio >= 0.85:
        return 15.0
    if ratio >= 0.70:
        return 5.0
    return 0.0


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
    library_path: str | None = None,
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

def get_vector_collection_info(
    collection: str = "papers",
    db_path: str | None = None,
) -> Optional[Dict[str, Any]]:
    """Return metadata for the first matching Chroma collection.

    Uses the module-level shared ``PersistentClient`` so that HNSW
    segment data stays warm for subsequent ``vector_search`` calls.
    """
    db_path = _resolved_path(db_path, DEFAULT_VECTORDB_PATH)
    db_dir = Path(db_path)
    if not db_dir.exists():
        return None

    client = _get_client(db_path)
    collections = client.list_collections()
    matching = [c for c in collections if c.name.startswith(collection + "_")]
    if not matching:
        return None

    chosen = None
    dimension = 2048
    model_id = ""

    for candidate in matching:
        metadata = candidate.metadata or {}
        try:
            sample = candidate.get(limit=1, include=["embeddings"])
        except Exception:
            sample = None
        embeddings = sample.get("embeddings") if sample is not None else None
        first_embedding = None
        if embeddings is not None and len(embeddings) > 0:
            first_embedding = embeddings[0]
        if first_embedding is None:
            continue

        chosen = candidate
        model_id = str(metadata.get("embedding_model", "") or "")
        dimension = len(first_embedding)
        break

    if chosen is None:
        chosen = matching[0]
        metadata = chosen.metadata or {}
        model_id = str(metadata.get("embedding_model", "") or "")
        dimension = _infer_dimension_for_model(model_id, fallback=dimension)

    return {
        "name": chosen.name,
        "model_id": model_id,
        "dimension": dimension,
    }


def _infer_dimension_for_model(model_id: str, fallback: int = 2048) -> int:
    """Best-effort dimension inference when Chroma cannot return sample embeddings."""
    from paper_compass.embedder import Embedder

    if not model_id:
        return fallback

    embedder = Embedder()
    try:
        return int(embedder.configure_local(model_id))
    except KeyError:
        pass

    provider_name, sep, model_name = model_id.partition(":")
    if not sep or not provider_name or not model_name:
        return fallback

    load_project_env()
    configs = load_all_configs()
    for provider_key in ["embedding_main", "embedding_volcengine"]:
        try:
            cfg = get_provider_config(provider_key, configs)
        except KeyError:
            continue
        if cfg.get("provider", "openai") != provider_name:
            continue
        if cfg.get("model", "") != model_name:
            continue
        try:
            return int(cfg.get("dimension", fallback))
        except (TypeError, ValueError):
            return fallback

    return fallback


def _configure_embedder_for_collection(model_id: str, dimension: int):
    """Configure an embedder that exactly matches a stored collection."""
    from paper_compass.embedder import Embedder

    embedder = Embedder()

    try:
        embedder.configure_local(model_id)
        return embedder
    except KeyError:
        pass

    provider_name, sep, model_name = model_id.partition(":")
    if not sep or not provider_name or not model_name:
        raise RuntimeError(
            f"Indexed collection uses unsupported embedding model '{model_id}'. "
            "Rebuild the index with a configured local or cloud model."
        )

    load_project_env()
    configs = load_all_configs()

    matched_cfg: Optional[Dict[str, Any]] = None
    for provider_key in ["embedding_main", "embedding_volcengine"]:
        try:
            cfg = get_provider_config(provider_key, configs)
        except KeyError:
            continue
        if cfg.get("provider", "openai") != provider_name:
            continue
        if cfg.get("model", "") != model_name:
            continue
        if not cfg.get("base_url") or not cfg.get("api_key"):
            raise RuntimeError(
                f"Embedding provider '{provider_key}' matches indexed model '{model_id}' but is incomplete."
            )
        matched_cfg = cfg
        break

    if matched_cfg is None:
        raise RuntimeError(
            f"No configured embedding provider matches indexed model '{model_id}'. "
            "Update the embedding config or rebuild the index."
        )

    embedder.configure_cloud(
        provider_name,
        matched_cfg.get("base_url", ""),
        matched_cfg.get("api_key", ""),
        matched_cfg.get("model", ""),
        dimension,
    )
    if embedder.model_id != model_id:
        raise RuntimeError(
            f"Query embedder resolved to '{embedder.model_id}', but the collection expects '{model_id}'. "
            "Rebuild the index or fix the embedding configuration."
        )
    return embedder


def vector_search(
    query: str,
    collection: str = "papers",
    k: int = 10,
    db_path: str | None = None,
) -> List[Dict[str, Any]]:
    """Semantic vector search using ChromaDB.

    Auto-detects embedding model and dimension from existing collections.
    """
    from paper_compass.vector_store import VectorStore

    load_project_env()

    db_path = _resolved_path(db_path, DEFAULT_VECTORDB_PATH)
    info = get_vector_collection_info(collection=collection, db_path=db_path)
    if info is None:
        return []

    model_id = info["model_id"]
    actual_dim = int(info["dimension"])
    embedder = _configure_embedder_for_collection(model_id, actual_dim)
    store = VectorStore(
        db_path=db_path,
        collection_name=collection,
        embedding_model_id=model_id,
        chroma_client=_get_client(db_path),
    )
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


# ── search_passages ──────────────────────────────────────────────────────────

def search_passages(
    query: str,
    search_mode: str = "semantic",
    limit: int = 10,
    filters: Optional[Dict[str, Any]] = None,
    db_path: str | None = None,
    text_dir: str | None = None,
    library_path: str | None = None,
) -> List[Dict[str, Any]]:
    """Search for original passages matching a keyword or brief expression.

    Returns matched **original text paragraphs** enriched with paper metadata
    (title, authors, year, etc.).

    Two search modes:
    - ``"semantic"`` (default): vector search over ChromaDB papers collection.
    - ``"keyword"``: full-text keyword search over data/texts/*.txt.
    - ``"hybrid"``: both, merged and deduplicated.

    Args:
        query: Keyword or short phrase to search for.
        search_mode: ``"semantic"`` | ``"keyword"`` | ``"hybrid"``.
        limit: Maximum number of results.
        filters: Optional metadata filters (collections, tags, authors, year_from,
                 year_to).  Only ``"semantic"`` / ``"hybrid"`` honours ChromaDB-side
                 filters; ``"keyword"`` does client-side post-filtering.
        db_path: Path to ChromaDB directory (semantic mode).
        text_dir: Directory containing extracted .txt files (keyword mode).
        library_path: Path to library.json for metadata enrichment.

    Returns:
        List of passage results, each containing:
          - doc_id, title, authors, year, doi
          - passage (original text paragraph)
          - score, search_mode, match_type
    """
    db_path = _resolved_path(db_path, DEFAULT_VECTORDB_PATH)
    text_dir = _resolved_path(text_dir, DEFAULT_TEXT_DIR)
    library_path = _resolved_path(library_path, DEFAULT_LIBRARY_PATH)
    results: List[Dict[str, Any]] = []

    if search_mode in ("semantic", "hybrid"):
        pdf_chunks = vector_search(query, collection="papers", k=limit * 2, db_path=db_path)
        deduped = _dedupe_pdf_chunks_by_item(pdf_chunks, max_per_item=2)
        for chunk in deduped:
            results.append({
                "doc_id": chunk.get("metadata", {}).get("item_key", ""),
                "title": chunk.get("metadata", {}).get("title", ""),
                "passage": chunk.get("document", ""),
                "score": chunk.get("score", 0.0),
                "page_num": chunk.get("metadata", {}).get("page_num"),
                "search_mode": "semantic",
                "match_type": "vector",
            })

    if search_mode in ("keyword", "hybrid"):
        kw_results = _keyword_search_passages(query, text_dir, limit * 2)
        for kw in kw_results:
            kw["search_mode"] = "keyword"
            kw["match_type"] = "fulltext"
            # Avoid exact duplicates already in results
            dup = False
            for r in results:
                if r.get("doc_id") == kw.get("doc_id") and r.get("passage", "")[:80] == kw.get("passage", "")[:80]:
                    dup = True
                    break
            if not dup:
                results.append(kw)

    # Enrich with library metadata and apply filters
    library = _load_library(library_path)
    lib_by_key = {rec.get("key", ""): rec for rec in library}

    enriched: List[Dict[str, Any]] = []
    for r in results:
        rec = lib_by_key.get(r.get("doc_id", ""), {})
        enriched.append({
            "doc_id": r.get("doc_id", "") or rec.get("key", ""),
            "title": r.get("title") or rec.get("title", ""),
            "authors": rec.get("authors", []),
            "year": rec.get("year"),
            "doi": rec.get("doi", ""),
            "passage": r["passage"],
            "page_num": r.get("page_num"),
            "score": r.get("score", 0.0),
            "search_mode": r.get("search_mode", ""),
            "match_type": r.get("match_type", ""),
            "collections": rec.get("collections", []),
            "tags": rec.get("tags", []),
        })

    # Client-side filtering
    if filters:
        enriched = [e for e in enriched if _passes_enriched_filters(e, filters)]

    # Sort by score descending, take top limit
    enriched.sort(key=lambda x: x["score"], reverse=True)
    enriched = enriched[:limit]

    return enriched


def _keyword_search_passages(
    query: str,
    text_dir: str | None = None,
    limit: int = 20,
) -> List[Dict[str, Any]]:
    """Full-text keyword search over extracted .txt files.

    Splits each file into paragraphs (blank-line-separated blocks), scores
    them by keyword occurrence density, and returns the top matches.
    """
    from pathlib import Path
    import re

    txt_root = Path(_resolved_path(text_dir, DEFAULT_TEXT_DIR))
    if not txt_root.exists():
        return []

    keywords = [kw.lower() for kw in re.split(r"\s+", query.strip()) if kw]
    if not keywords:
        return []

    scored: List[tuple] = []

    for txt_path in txt_root.glob("*.txt"):
        try:
            text = txt_path.read_text(encoding="utf-8", errors="replace")
        except Exception:
            continue

        # Derive a rough doc_id from filename (e.g. "ABC123.txt" -> "ABC123")
        doc_id = txt_path.stem

        # Split into paragraphs (blank line boundaries)
        paragraphs = re.split(r"\n\s*\n", text)
        for para in paragraphs:
            para = para.strip()
            if len(para) < 30:  # skip very short fragments
                continue
            para_lower = para.lower()
            # Count distinct keywords found
            hits = sum(1 for kw in keywords if kw in para_lower)
            if hits == 0:
                continue
            # Density score: hits per 100 chars
            density = hits / max(len(para), 1) * 100
            scored.append((density + hits, doc_id, para[:800]))

    scored.sort(key=lambda x: x[0], reverse=True)
    results = []
    seen = set()
    for _, doc_id, passage in scored:
        # Dedupe by (doc_id, passage_prefix)
        dedup_key = (doc_id, passage[:120])
        if dedup_key in seen:
            continue
        seen.add(dedup_key)
        results.append({
            "doc_id": doc_id,
            "title": "",
            "passage": passage,
            "score": round(_, 4),
            "page_num": None,
        })
        if len(results) >= limit:
            break

    return results


def _passes_enriched_filters(result: Dict[str, Any], filters: Dict[str, Any]) -> bool:
    """Check metadata filters against an already-enriched passage result."""
    if "collections" in filters and filters["collections"]:
        rec_cols = set(c.lower() for c in result.get("collections", []))
        filt_cols = set(c.lower() for c in filters["collections"])
        if not rec_cols & filt_cols:
            return False

    if "tags" in filters and filters["tags"]:
        rec_tags = set(t.lower() for t in result.get("tags", []))
        filt_tags = set(t.lower() for t in filters["tags"])
        if not rec_tags & filt_tags:
            return False

    if "authors" in filters and filters["authors"]:
        rec_auth = set(a.lower() for a in result.get("authors", []))
        filt_auth = set(a.lower() for a in filters["authors"])
        if not rec_auth & filt_auth:
            return False

    year = result.get("year")
    if year is not None:
        if "year_from" in filters and filters["year_from"] is not None:
            if year < filters["year_from"]:
                return False
        if "year_to" in filters and filters["year_to"] is not None:
            if year > filters["year_to"]:
                return False

    return True


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
