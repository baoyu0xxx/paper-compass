"""
Unified embedding abstraction for paper-compass.

Adapted from RAG-Assistant-for-Zotero backend/embed_utils.py + embedding_providers/.

Supports:
  - Local models via sentence_transformers (bge-base, specter, minilm)
  - Cloud providers via OpenAI-compatible API (Volcengine, etc.)
  - Automatic dimension tracking per model
"""

from __future__ import annotations

import hashlib
import logging
import os
import threading
import time
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)

# ── local model registry (from RAG) ──────────────────────────────────────────

_LOCAL_MODELS: Dict[str, Dict[str, Any]] = {
    "bge-base": {
        "name": "BAAI/bge-base-en-v1.5",
        "dimension": 768,
        "local": True,
    },
    "specter": {
        "name": "allenai/specter",
        "dimension": 768,
        "local": True,
    },
    "minilm": {
        "name": "all-MiniLM-L6-v2",
        "dimension": 384,
        "local": True,
    },
}


class Embedder:
    """Unified embedding interface supporting local and cloud models.

    Usage:
        embedder = Embedder()
        # Cloud mode (OpenAI-compatible)
        embedder.configure_cloud(
            provider="openai",
            base_url="https://ark.cn-beijing.volces.com/api/v3/embeddings/multimodal",
            api_key="...",
            model="doubao-embedding-vision-250615",
            dimension=1024,
        )
        vectors = embedder.embed(["text1", "text2"])

        # Local mode
        embedder.configure_local("bge-base")
        vectors = embedder.embed(["text1", "text2"])
    """

    def __init__(self):
        self._mode: str = "local"  # "local" or "cloud"
        self._model_id: str = "bge-base"
        self._dimension: int = 768
        self._cloud_config: Dict[str, Any] = {}
        self._local_model: Any = None
        self._lock = threading.Lock()

    # ── configuration ─────────────────────────────────────────────────────

    def configure_local(self, model_id: str = "bge-base") -> int:
        """Use a local sentence_transformers model.

        Returns the embedding dimension.
        """
        if model_id not in _LOCAL_MODELS:
            raise KeyError(
                f"Unknown local model '{model_id}'. Available: {list(_LOCAL_MODELS.keys())}"
            )
        info = _LOCAL_MODELS[model_id]
        with self._lock:
            self._mode = "local"
            self._model_id = model_id
            self._dimension = info["dimension"]
            self._local_model = None  # lazy load
            self._cloud_config = {}
        return self._dimension

    def configure_cloud(
        self,
        provider: str,
        base_url: str,
        api_key: str,
        model: str,
        dimension: int = 1024,
    ) -> int:
        """Use a cloud OpenAI-compatible embedding provider.

        Returns the embedding dimension.
        """
        with self._lock:
            self._mode = "cloud"
            self._model_id = f"{provider}:{model}"
            self._dimension = dimension
            self._cloud_config = {
                "provider": provider,
                "base_url": base_url.rstrip("/"),
                "api_key": api_key,
                "model": model,
            }
            self._local_model = None
        return self._dimension

    @property
    def dimension(self) -> int:
        return self._dimension

    @property
    def model_id(self) -> str:
        return self._model_id

    # ── embedding ─────────────────────────────────────────────────────────

    def embed(self, texts: List[str], batch_size: int = 32) -> List[List[float]]:
        """Embed a list of texts.

        Args:
            texts: List of input strings.
            batch_size: Batch size for cloud API calls.

        Returns:
            List of embedding vectors.
        """
        if not texts:
            return []

        if self._mode == "local":
            return self._embed_local(texts)
        else:
            return self._embed_cloud(texts, batch_size)

    def embed_single(self, text: str) -> List[float]:
        """Embed a single text. Convenience wrapper."""
        return self.embed([text])[0]

    # ── internal ──────────────────────────────────────────────────────────

    def _load_local_model(self) -> Any:
        import sentence_transformers
        model_name = _LOCAL_MODELS[self._model_id]["name"]
        return sentence_transformers.SentenceTransformer(model_name)

    def _embed_local(self, texts: List[str]) -> List[List[float]]:
        with self._lock:
            if self._local_model is None:
                self._local_model = self._load_local_model()
            model = self._local_model
        embeddings = model.encode(texts, normalize_embeddings=True)
        return embeddings.tolist()

    def _embed_cloud(self, texts: List[str], batch_size: int) -> List[List[float]]:
        cfg = self._cloud_config
        all_vectors: List[List[float]] = []

        # Volcengine multimodal only supports 1 text per request
        is_multimodal = "volces" in cfg.get("base_url", "") or "multimodal" in cfg.get("base_url", "")
        if is_multimodal:
            for text in texts:
                vectors = self._call_cloud_api([text], cfg)
                all_vectors.extend(vectors)
        else:
            for i in range(0, len(texts), batch_size):
                batch = texts[i : i + batch_size]
                vectors = self._call_cloud_api(batch, cfg)
                all_vectors.extend(vectors)

        return all_vectors

    def _call_cloud_api(
        self, texts: List[str], cfg: Dict[str, Any], max_retries: int = 5
    ) -> List[List[float]]:
        import urllib.request
        import json

        url = cfg["base_url"]
        model = cfg["model"]
        api_key = cfg["api_key"]

        # Volcengine multimodal format
        if "volces" in url or "multimodal" in url:
            payload = json.dumps({
                "model": model,
                "input": [{"type": "text", "text": t} for t in texts],
            }).encode("utf-8")
        else:
            payload = json.dumps({
                "model": model,
                "input": texts,
            }).encode("utf-8")

        last_error = None
        for attempt in range(max_retries):
            try:
                req = urllib.request.Request(
                    url,
                    data=payload,
                    headers={
                        "Content-Type": "application/json",
                        "Authorization": f"Bearer {api_key}",
                    },
                    method="POST",
                )
                with urllib.request.urlopen(req, timeout=120) as resp:
                    result = json.loads(resp.read().decode("utf-8"))
                    return self._parse_embedding_response(result)
            except Exception as e:
                last_error = e
                if attempt < max_retries - 1:
                    time.sleep(2 ** attempt)
                continue

        raise RuntimeError(
            f"Cloud embedding failed after {max_retries} retries: {last_error}"
        )

    def _parse_embedding_response(self, result: Dict[str, Any]) -> List[List[float]]:
        """Parse response from OpenAI-compatible or Volcengine format."""
        data = result.get("data")
        if data is None:
            raise RuntimeError(f"Embedding API returned no 'data' field: {list(result.keys())}")

        # Volcengine returns data as a dict with embedding
        if isinstance(data, dict):
            emb = data.get("embedding")
            if emb is not None:
                return [emb]

        # Standard: list of {embedding: [...]}
        if isinstance(data, list) and data:
            return [item["embedding"] for item in data]

        raise RuntimeError(f"Unexpected embedding response format: {type(data)}")


# ── convenience ───────────────────────────────────────────────────────────────


def hash_text(text: str) -> str:
    """Stable content hash for dedup/cache keys."""
    return hashlib.sha256(text.encode("utf-8")).hexdigest()[:16]
