"""
Vector store module for paper-compass.

Adapted from RAG-Assistant-for-Zotero backend/vector_db.py.
Wraps ChromaDB with manual embedding injection (no default embedding function).

Supports:
  - Persistent local storage
  - Semantic search with optional metadata filters
  - Per-model collection names (avoids dimension conflicts)
  - BM25 hybrid retrieval option
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any, Dict, List, Optional, Set


class VectorStore:
    """Persistent vector store backed by ChromaDB.

    Each embedding model gets its own ChromaDB collection to prevent dimension
    mismatches. Embeddings MUST be pre-computed — this store does not auto-embed.

    Args:
        db_path: Directory for ChromaDB persistent storage.
        collection_name: Base collection name (model ID is appended).
        embedding_model_id: Identifier for the embedding model used
                           (e.g. 'bge-base', 'volcengine:doubao-vision').
    """

    def __init__(
        self,
        db_path: str,
        collection_name: str = "papercompass",
        embedding_model_id: str = "bge-base",
    ):
        import chromadb
        from chromadb.config import Settings

        self.db_path = db_path
        self.embedding_model_id = embedding_model_id
        safe_id = embedding_model_id.replace(":", "-").replace("/", "-")
        self.collection_name = f"{collection_name}_{safe_id}"

        os.makedirs(self.db_path, exist_ok=True)
        self.chroma_client = chromadb.PersistentClient(
            path=self.db_path, settings=Settings(anonymized_telemetry=False)
        )
        self.collection = self.chroma_client.get_or_create_collection(
            name=self.collection_name,
            metadata={
                "hnsw:space": "cosine",
                "embedding_model": embedding_model_id,
            },
        )

        # BM25 index (lazy)
        self._bm25_index: Any = None
        self._bm25_corpus: List[str] = []
        self._bm25_ids: List[str] = []

    # ── write ─────────────────────────────────────────────────────────────

    def add_chunks(
        self,
        ids: List[str],
        documents: List[str],
        metadatas: Optional[List[Dict[str, Any]]] = None,
        embeddings: Optional[List[List[float]]] = None,
        mode: str = "add",
    ) -> None:
        """Add document chunks with pre-computed embeddings.

        Args:
            ids: Unique chunk IDs.
            documents: Text content of each chunk.
            metadatas: Optional metadata dicts (year, tags, collections, etc.).
            embeddings: Pre-computed embedding vectors. Required.
            mode: 'add' for strict append, 'upsert' for idempotent update-or-insert.
        """
        method = self.collection.upsert if mode == "upsert" else self.collection.add
        method(
            ids=ids,
            documents=documents,
            metadatas=metadatas,
            embeddings=embeddings,
        )

    def upsert_chunks(
        self,
        ids: List[str],
        documents: List[str],
        metadatas: Optional[List[Dict[str, Any]]] = None,
        embeddings: Optional[List[List[float]]] = None,
    ) -> None:
        """Insert new chunks or update existing chunks in-place."""
        self.add_chunks(
            ids=ids,
            documents=documents,
            metadatas=metadatas,
            embeddings=embeddings,
            mode="upsert",
        )

    # ── search ────────────────────────────────────────────────────────────

    def search(
        self,
        query_embedding: List[float],
        k: int = 10,
        where: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Semantic search with pre-computed query embedding.

        Args:
            query_embedding: The pre-computed embedding vector for the query.
            k: Number of results.
            where: Optional ChromaDB where clause for metadata filtering.

        Returns:
            Dict with keys: ids, documents, metadatas, distances.
        """
        results = self.collection.query(
            query_embeddings=[query_embedding],
            n_results=k,
            where=where,
            include=["documents", "metadatas", "distances"],
        )

        return {
            "ids": results["ids"][0] if results["ids"] else [],
            "documents": results["documents"][0] if results["documents"] else [],
            "metadatas": results["metadatas"][0] if results["metadatas"] else [],
            "distances": results["distances"][0] if results["distances"] else [],
        }

    def hybrid_search(
        self,
        query_text: str,
        query_embedding: List[float],
        k: int = 10,
        where: Optional[Dict[str, Any]] = None,
        bm25_weight: float = 0.3,
    ) -> List[Dict[str, Any]]:
        """Combined semantic + BM25 keyword search.

        Args:
            query_text: Raw text for BM25 scoring.
            query_embedding: Pre-computed embedding for semantic search.
            k: Number of results.
            where: Optional metadata filter.
            bm25_weight: Weight for BM25 component (0 = pure semantic, 1 = pure keyword).

        Returns:
            List of result dicts sorted by combined score.
        """
        semantic = self.search(query_embedding, k=k * 2, where=where)

        if bm25_weight <= 0 or not self._bm25_index:
            # Pure semantic
            return _format_results(semantic)[:k]

        # BM25 scoring
        self._ensure_bm25()
        bm25_scores = self._bm25_index.get_scores(query_text.split())

        # Combine scores
        combined: List[Dict[str, Any]] = []
        for i, chunk_id in enumerate(semantic["ids"]):
            sem_score = 1.0 / (1.0 + semantic["distances"][i])  # convert distance to similarity
            bm25 = bm25_scores.get(chunk_id, 0.0)
            combined_score = (1 - bm25_weight) * sem_score + bm25_weight * bm25

            combined.append({
                "id": chunk_id,
                "document": semantic["documents"][i],
                "metadata": semantic["metadatas"][i] if semantic["metadatas"] else {},
                "distance": semantic["distances"][i],
                "score": combined_score,
            })

        combined.sort(key=lambda x: x["score"], reverse=True)
        return combined[:k]

    # ── management ────────────────────────────────────────────────────────

    def count(self) -> int:
        """Return total number of chunks in the collection."""
        return self.collection.count()

    def _invalidate_bm25(self) -> None:
        """Drop cached BM25 state after any collection mutation."""
        self._bm25_index = None
        self._bm25_corpus = []
        self._bm25_ids = []

    def clear(self) -> None:
        """Delete all chunks in the collection."""
        if self.count() > 0:
            all_ids = self.collection.get()["ids"]
            if all_ids:
                self.collection.delete(ids=all_ids)
        self._invalidate_bm25()

    def get_indexed_item_keys(self) -> Set[str]:
        """Return all unique paper item keys present in the collection metadata."""
        total_count = self.count()
        if total_count == 0:
            return set()

        all_data = self.collection.get(limit=total_count, include=["metadatas"])
        item_keys: Set[str] = set()
        for metadata in all_data.get("metadatas", []) or []:
            if metadata and metadata.get("item_key"):
                item_keys.add(str(metadata["item_key"]))
        return item_keys

    def get_chunk_ids_for_item(self, item_key: str) -> List[str]:
        """Return all chunk IDs belonging to one paper item."""
        total_count = self.count()
        if total_count == 0:
            return []

        results = self.collection.get(
            where={"item_key": str(item_key)},
            limit=total_count,
        )
        return results.get("ids", []) or []

    def delete_item(self, item_key: str) -> int:
        """Delete all chunks belonging to one paper item key."""
        chunk_ids = self.get_chunk_ids_for_item(item_key)
        if not chunk_ids:
            return 0
        self.collection.delete(ids=chunk_ids)
        self._invalidate_bm25()
        return len(chunk_ids)

    # ── wiki page deletion ────────────────────────────────────────────────────

    def delete_by_page_path(self, page_path: str) -> int:
        """Delete all chunks whose metadata 'page_path' matches exactly.

        Returns the number of chunks deleted. Invalidates the BM25 index
        so the next search rebuilds it from scratch.
        """
        chunk_ids = self.get_chunk_ids_by_metadata_where({"page_path": page_path})
        if not chunk_ids:
            return 0
        self.collection.delete(ids=chunk_ids)
        self._invalidate_bm25()
        return len(chunk_ids)

    def delete_by_page_path_prefix(self, prefix: str) -> int:
        """Delete all chunks whose metadata 'page_path' starts with a given prefix.

        Useful for directory-level cleanup, e.g. delete_by_page_path_prefix('wiki/queries/').
        Returns the number of chunks deleted.
        """
        total_count = self.count()
        if total_count == 0:
            return 0

        all_data = self.collection.get(limit=total_count, include=["metadatas"])
        to_delete: List[str] = []
        for i, _id in enumerate(all_data.get("ids", []) or []):
            meta = (all_data.get("metadatas", []) or [])[i] if i < len(all_data.get("metadatas", []) or []) else {}
            page_path = (meta or {}).get("page_path", "")
            if page_path.startswith(prefix):
                to_delete.append(_id)

        if not to_delete:
            return 0
        self.collection.delete(ids=to_delete)
        self._invalidate_bm25()
        return len(to_delete)

    def get_chunk_ids_by_metadata_where(self, where: Dict[str, str]) -> List[str]:
        """Collect all chunk IDs matching an exact metadata filter.

        Useful for inspection or deletion by metadata fields like page_path.
        """
        total_count = self.count()
        if total_count == 0:
            return []

        # ChromaDB $contains filter works for substring — but for exact match
        # we iterate and filter. Limit to total to get all.
        all_data = self.collection.get(limit=total_count, include=["metadatas"])
        matched: List[str] = []
        for i, _id in enumerate(all_data.get("ids", []) or []):
            meta = (all_data.get("metadatas", []) or [])[i] if i < len(all_data.get("metadatas", []) or []) else {}
            if all(meta.get(k) == v for k, v in where.items()):
                matched.append(_id)
        return matched

    def build_bm25(self, force: bool = False) -> None:
        """Build or rebuild the BM25 keyword index from current collection."""
        if not force and self._bm25_index is not None:
            return

        try:
            from rank_bm25 import BM25Okapi

            all_data = self.collection.get(include=["documents"])
            self._bm25_ids = all_data.get("ids", [])
            corpus = all_data.get("documents", [])
            self._bm25_corpus = [doc.split() for doc in corpus]
            self._bm25_index = BM25Okapi(self._bm25_corpus, self._bm25_ids)
        except Exception:
            # BM25 is optional — graceful degradation
            self._bm25_index = None
            self._bm25_ids = []

    def _ensure_bm25(self) -> None:
        if self._bm25_index is None:
            self.build_bm25()


# ── helpers ───────────────────────────────────────────────────────────────────


def _format_results(semantic: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Convert ChromaDB semantic results to a list of formatted dicts."""
    results: List[Dict[str, Any]] = []
    for i, chunk_id in enumerate(semantic["ids"]):
        results.append({
            "id": chunk_id,
            "document": semantic["documents"][i],
            "metadata": semantic["metadatas"][i] if semantic["metadatas"] else {},
            "distance": semantic["distances"][i],
            "score": 1.0 / (1.0 + semantic["distances"][i]),
        })
    return results
