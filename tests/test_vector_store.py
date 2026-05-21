"""Tests for the vector store BM25 and cache behavior."""

from __future__ import annotations

from types import SimpleNamespace

import pytest

from paper_compass.vector_store import VectorStore


class DummyCollection:
    def __init__(self, ids=None, documents=None):
        self.ids = ids or []
        self.documents = documents or []
        self.add_calls = 0
        self.upsert_calls = 0

    def get(self, include=None, limit=None, where=None):
        include = include or []
        if include == ["documents"]:
            return {"ids": self.ids, "documents": self.documents}
        if include == ["metadatas"]:
            return {"ids": self.ids, "metadatas": [{} for _ in self.ids]}
        return {"ids": self.ids, "documents": self.documents, "metadatas": [{} for _ in self.ids]}

    def add(self, **kwargs):
        self.add_calls += 1

    def upsert(self, **kwargs):
        self.upsert_calls += 1

    def query(self, **kwargs):
        return {
            "ids": [["a", "b"]],
            "documents": [["doc a", "doc b"]],
            "metadatas": [[{"chunk": 1}, {"chunk": 2}]],
            "distances": [[0.2, 0.5]],
        }

    def count(self):
        return len(self.ids)


def test_add_chunks_invalidates_bm25(monkeypatch):
    store = object.__new__(VectorStore)
    store.collection = DummyCollection()
    store._bm25_index = object()
    store._bm25_corpus = ["old"]
    store._bm25_ids = ["old"]

    store.add_chunks(["id1"], ["text1"], metadatas=[{}], embeddings=[[0.1]])

    assert store._bm25_index is None
    assert store._bm25_corpus == []
    assert store._bm25_ids == []


def test_build_bm25_uses_corpus_only(monkeypatch):
    class FakeBM25:
        def __init__(self, corpus):
            self.corpus = corpus

        def get_scores(self, tokens):
            return [0.1 for _ in self.corpus]

    monkeypatch.setitem(
        __import__("sys").modules,
        "rank_bm25",
        SimpleNamespace(BM25Okapi=FakeBM25),
    )

    store = object.__new__(VectorStore)
    store.collection = DummyCollection(ids=["a", "b"], documents=["alpha beta", "gamma delta"])
    store._bm25_index = None
    store._bm25_corpus = []
    store._bm25_ids = []

    store.build_bm25(force=True)

    assert isinstance(store._bm25_index, FakeBM25)
    assert store._bm25_index.corpus == [["alpha", "beta"], ["gamma", "delta"]]
    assert store._bm25_ids == ["a", "b"]


def test_hybrid_search_orders_by_combined_score(monkeypatch):
    class FakeBM25:
        def __init__(self, corpus):
            self.corpus = corpus

        def get_scores(self, tokens):
            return [0.1, 1.0]

    monkeypatch.setitem(
        __import__("sys").modules,
        "rank_bm25",
        SimpleNamespace(BM25Okapi=FakeBM25),
    )

    store = object.__new__(VectorStore)
    store.collection = DummyCollection(ids=["a", "b"], documents=["alpha beta", "gamma delta"])
    store._bm25_index = FakeBM25([["alpha"], ["gamma"]])
    store._bm25_corpus = [["alpha"], ["gamma"]]
    store._bm25_ids = ["a", "b"]

    def fake_search(query_embedding, k=10, where=None):
        return {
            "ids": ["a", "b"],
            "documents": ["doc a", "doc b"],
            "metadatas": [{}, {}],
            "distances": [0.1, 0.2],
        }

    store.search = fake_search

    results = store.hybrid_search("gamma", [0.1], k=2, bm25_weight=0.5)

    assert [r["id"] for r in results] == ["b", "a"]


def test_build_bm25_reports_missing_dependency(monkeypatch):
    import builtins

    original_import = builtins.__import__

    def fake_import(name, *args, **kwargs):
        if name == "rank_bm25":
            raise ImportError("No module named 'rank_bm25'")
        return original_import(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", fake_import)

    store = object.__new__(VectorStore)
    store.collection = DummyCollection(ids=["a"], documents=["alpha beta"])
    store._bm25_index = None
    store._bm25_corpus = []
    store._bm25_ids = []

    result = store.build_bm25(force=True)

    assert result.available is False
    assert "rank_bm25" in result.reason
