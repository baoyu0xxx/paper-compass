from types import SimpleNamespace

import numpy as np

from paper_compass.search import get_vector_collection_info


class _FakeCollection:
    def __init__(self, name, metadata, embeddings):
        self.name = name
        self.metadata = metadata
        self._embeddings = embeddings

    def get(self, limit=1, include=None):
        return {"embeddings": self._embeddings}


class _FakeClient:
    def __init__(self, collections):
        self._collections = collections

    def list_collections(self):
        return self._collections

    def clear_system_cache(self):
        pass


def test_get_vector_collection_info_handles_numpy_embeddings(monkeypatch, tmp_path):
    empty = _FakeCollection(
        name="wiki_old-model",
        metadata={"embedding_model": "old-model"},
        embeddings=np.array([]),
    )
    populated = _FakeCollection(
        name="wiki_new-model",
        metadata={"embedding_model": "volcengine:good-model"},
        embeddings=np.array([[1.0, 2.0, 3.0]]),
    )

    fake_module = SimpleNamespace(
        PersistentClient=lambda path, settings: _FakeClient([empty, populated])
    )
    fake_settings = SimpleNamespace(anonymized_telemetry=False)

    monkeypatch.setitem(__import__("sys").modules, "chromadb", fake_module)
    monkeypatch.setitem(
        __import__("sys").modules,
        "chromadb.config",
        SimpleNamespace(Settings=lambda anonymized_telemetry=False: fake_settings),
    )

    db_dir = tmp_path / "vectordb"
    db_dir.mkdir()

    info = get_vector_collection_info(collection="wiki", db_path=str(db_dir))

    assert info == {
        "name": "wiki_new-model",
        "model_id": "volcengine:good-model",
        "dimension": 3,
    }


def test_get_vector_collection_info_falls_back_when_only_empty_collections(monkeypatch, tmp_path):
    empty = _FakeCollection(
        name="papers_empty-model",
        metadata={"embedding_model": "volcengine:empty-model"},
        embeddings=np.array([]),
    )

    fake_module = SimpleNamespace(
        PersistentClient=lambda path, settings: _FakeClient([empty])
    )
    fake_settings = SimpleNamespace(anonymized_telemetry=False)

    monkeypatch.setitem(__import__("sys").modules, "chromadb", fake_module)
    monkeypatch.setitem(
        __import__("sys").modules,
        "chromadb.config",
        SimpleNamespace(Settings=lambda anonymized_telemetry=False: fake_settings),
    )

    db_dir = tmp_path / "vectordb"
    db_dir.mkdir()

    info = get_vector_collection_info(collection="papers", db_path=str(db_dir))

    assert info == {
        "name": "papers_empty-model",
        "model_id": "volcengine:empty-model",
        "dimension": 2048,
    }
