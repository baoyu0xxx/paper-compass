import importlib.util
import json
from pathlib import Path
from types import SimpleNamespace

from miniresearch.index_manifest import compute_text_sha1, diff_manifest


SCRIPT_PATH = Path(__file__).resolve().parents[1] / "scripts" / "build_index.py"


class FakeEmbedder:
    def __init__(self, model_id: str = "fake:model"):
        self.model_id = model_id
        self.dimension = 1

    def embed(self, texts, batch_size=32):
        return [[float(len(text))] for text in texts]

    def embed_single(self, text):
        return [float(len(text))]


class FakeStore:
    def __init__(self, collection_name="papers_fake-model"):
        self.collection_name = collection_name
        self.docs = {}
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
        return [doc_id for doc_id, payload in self.docs.items() if payload["metadata"].get("item_key") == item_key]

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


def load_build_index_module():
    spec = importlib.util.spec_from_file_location("paper_compass_build_index", SCRIPT_PATH)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def make_paper(tmp_path: Path, key: str, text: str):
    pdf_path = tmp_path / f"{key}.pdf"
    pdf_path.write_text("pdf placeholder", encoding="utf-8")
    text_path = tmp_path / f"{key}.txt"
    text_path.write_text(text, encoding="utf-8")
    return {
        "key": key,
        "title": f"Title {key}",
        "year": 2020,
        "authors": ["A"],
        "collections": ["C"],
        "tags": ["T"],
        "pdf_path": str(pdf_path),
        "text_file": str(text_path),
    }


def write_library(tmp_path: Path, items):
    library_path = tmp_path / "library.json"
    library_path.write_text(json.dumps(items, ensure_ascii=False, indent=2), encoding="utf-8")
    return library_path


def make_args(tmp_path: Path, library_path: Path, **overrides):
    defaults = dict(
        library=str(library_path),
        db_path=str(tmp_path / "vectordb"),
        text_dir=str(tmp_path),
        extract_text=False,
        wiki=False,
        wiki_root=str(tmp_path / "wiki"),
        incremental=True,
        full_rebuild=False,
        prune_deleted=False,
        manifest_path=str(tmp_path / "manifest.json"),
    )
    defaults.update(overrides)
    return SimpleNamespace(**defaults)


def test_diff_manifest_detects_new_changed_unchanged_deleted():
    current = {
        "A": {"text_sha1": compute_text_sha1("aaa"), "chunk_count": 1},
        "B": {"text_sha1": compute_text_sha1("bbb-new"), "chunk_count": 2},
    }
    previous = {
        "B": {"text_sha1": compute_text_sha1("bbb-old"), "chunk_count": 2},
        "C": {"text_sha1": compute_text_sha1("ccc"), "chunk_count": 1},
        "A": {"text_sha1": compute_text_sha1("aaa"), "chunk_count": 1},
    }

    result = diff_manifest(current, previous)
    assert result == {
        "new": [],
        "changed": ["B"],
        "unchanged": ["A"],
        "deleted": ["C"],
    }


def test_incremental_second_run_skips_unchanged_items(tmp_path):
    module = load_build_index_module()
    item_a = make_paper(tmp_path, "A1", "x" * 2200)
    item_b = make_paper(tmp_path, "B2", "y" * 2400)
    library_path = write_library(tmp_path, [item_a, item_b])
    args = make_args(tmp_path, library_path)
    store = FakeStore()
    embedder = FakeEmbedder()

    first = module.index_papers(args, embedder=embedder, store=store)
    second = module.index_papers(args, embedder=embedder, store=store)

    assert first["indexed_papers"] == 2
    assert first["new"] == 2
    assert second["indexed_papers"] == 0
    assert second["unchanged"] == 2
    assert store.count() > 0


def test_incremental_detects_changed_text_and_replaces_chunks(tmp_path):
    module = load_build_index_module()
    item = make_paper(tmp_path, "A1", "a" * 2200)
    library_path = write_library(tmp_path, [item])
    args = make_args(tmp_path, library_path)
    store = FakeStore()
    embedder = FakeEmbedder()

    first = module.index_papers(args, embedder=embedder, store=store)
    original_count = store.count()
    Path(item["text_file"]).write_text("b" * 5200, encoding="utf-8")
    second = module.index_papers(args, embedder=embedder, store=store)

    assert first["indexed_papers"] == 1
    assert second["changed"] == 1
    assert second["deleted_chunks"] > 0
    assert store.count() != original_count
    assert all(payload["metadata"].get("item_key") == "A1" for payload in store.docs.values())


def test_incremental_prune_deleted_removes_chunks(tmp_path):
    module = load_build_index_module()
    item_a = make_paper(tmp_path, "A1", "a" * 2200)
    item_b = make_paper(tmp_path, "B2", "b" * 2200)
    library_path = write_library(tmp_path, [item_a, item_b])
    store = FakeStore()
    embedder = FakeEmbedder()

    module.index_papers(make_args(tmp_path, library_path), embedder=embedder, store=store)
    pruned_library = write_library(tmp_path, [item_a])
    summary = module.index_papers(
        make_args(tmp_path, pruned_library, prune_deleted=True),
        embedder=embedder,
        store=store,
    )

    assert summary["deleted"] == 1
    assert summary["deleted_chunks"] > 0
    assert not any(payload["metadata"].get("item_key") == "B2" for payload in store.docs.values())


def test_wiki_reindex_is_idempotent(tmp_path):
    module = load_build_index_module()
    wiki_root = tmp_path / "wiki"
    papers_dir = wiki_root / "papers"
    papers_dir.mkdir(parents=True)
    page = papers_dir / "sample.md"
    page.write_text("# Title\n## Section\nBody one", encoding="utf-8")

    args = make_args(tmp_path, tmp_path / "unused.json", wiki=True, wiki_root=str(wiki_root), incremental=False)
    store = FakeStore(collection_name="wiki_fake-model")
    embedder = FakeEmbedder()

    first = module.index_wiki(args, embedder=embedder, store=store)
    page.write_text("# Title\n## Section\nBody two updated", encoding="utf-8")
    second = module.index_wiki(args, embedder=embedder, store=store)

    assert first["indexed_sections"] == second["indexed_sections"]
    assert store.count() == first["indexed_sections"]
    assert any("updated" in payload["document"] for payload in store.docs.values())
