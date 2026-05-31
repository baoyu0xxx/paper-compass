"""Shared test utilities for paper-compass tests."""

import importlib.util
import json
from pathlib import Path
from types import SimpleNamespace


# ── Fake embedder (for tests that don't need real embeddings) ────

class FakeEmbedder:
    def __init__(self, model_id: str = "fake:model"):
        self.model_id = model_id
        self.dimension = 1

    def embed(self, texts, batch_size=32):
        return [[float(len(text))] for text in texts]

    def embed_single(self, text):
        return [float(len(text))]


# ── Fake vector store (in-memory dict) ────────────────────────────

class FakeStore:
    def __init__(self, collection_name="papers_fake-model"):
        self.collection_name = collection_name
        self.docs: dict[str, dict] = {}
        self.bm25_rebuilt = 0

    def add_chunks(self, ids, documents, metadatas=None, embeddings=None, mode="add"):
        metadatas = metadatas or [{} for _ in ids]
        embeddings = embeddings or [[0.0] for _ in ids]
        for doc_id, doc, meta, emb in zip(ids, documents, metadatas, embeddings):
            if mode != "upsert" and doc_id in self.docs:
                raise ValueError(f"duplicate id: {doc_id}")
            self.docs[doc_id] = {
                "document": doc,
                "metadata": meta,
                "embedding": emb,
            }

    def upsert_chunks(self, ids, documents, metadatas=None, embeddings=None):
        self.add_chunks(ids, documents, metadatas, embeddings, mode="upsert")

    def get_chunk_ids_for_item(self, item_key):
        return [
            doc_id
            for doc_id, payload in self.docs.items()
            if payload["metadata"].get("item_key") == item_key
        ]

    def get_indexed_item_keys(self):
        return {
            str(payload["metadata"].get("item_key"))
            for payload in self.docs.values()
            if payload["metadata"].get("item_key")
        }

    def delete_item(self, item_key):
        ids = self.get_chunk_ids_for_item(item_key)
        for doc_id in ids:
            self.docs.pop(doc_id, None)
        return len(ids)

    def clear(self):
        self.docs.clear()

    def build_bm25(self, force=False):
        self.bm25_rebuilt += 1

    def count(self):
        return len(self.docs)


# ── Shared module loader ─────────────────────────────────────────

BUILD_INDEX_SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "build_index.py"


def load_build_index():
    spec = importlib.util.spec_from_file_location(
        "paper_compass_build_index", BUILD_INDEX_SCRIPT
    )
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


# ── Shared data factories ────────────────────────────────────────

def write_fake_library(path: Path):
    """Write a default 3-paper library.json for testing."""
    records = [
        {
            "key": "ABC123",
            "title": "Family Firm Succession and Labor Structure",
            "authors": ["Zhang Wei"],
            "year": 2024,
            "doi": "10.1000/family.001",
            "collections": ["family_firm"],
            "tags": ["DID", "labor"],
            "pdf_path": "a.pdf",
        },
        {
            "key": "DEF456",
            "title": "Family Business and Employment Dynamics",
            "authors": ["Chen Yu"],
            "year": 2023,
            "doi": "10.1000/family.002",
            "collections": ["family_firm"],
            "tags": ["employment"],
            "pdf_path": "c.pdf",
        },
        {
            "key": "XYZ999",
            "title": "General Corporate Governance Notes",
            "authors": ["Li Ming"],
            "year": 2020,
            "doi": "10.1000/other.999",
            "collections": ["governance"],
            "tags": ["governance"],
            "pdf_path": "b.pdf",
        },
    ]
    path.write_text(json.dumps(records, ensure_ascii=False), encoding="utf-8")
