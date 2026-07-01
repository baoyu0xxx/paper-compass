from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

from helpers import FakeEmbedder, FakeStore, load_build_index


class FakeWikiStore(FakeStore):
    def get_chunk_ids_for_page(self, page_path: str):
        return [
            doc_id
            for doc_id, payload in self.docs.items()
            if payload["metadata"].get("page_path") == page_path
        ]

    def delete_by_page_path(self, page_path: str) -> int:
        ids = self.get_chunk_ids_for_page(page_path)
        for doc_id in ids:
            self.docs.pop(doc_id, None)
        return len(ids)


def write_wiki_page(wiki_root: Path, relative_path: str, content: str) -> Path:
    path = wiki_root / relative_path
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")
    return path


def make_wiki_args(tmp_path: Path, **overrides):
    defaults = dict(
        library=str(tmp_path / "library.json"),
        db_path=str(tmp_path / "vectordb"),
        text_dir=str(tmp_path),
        extract_text=False,
        wiki=True,
        wiki_root=str(tmp_path / "wiki"),
        incremental=False,
        full_rebuild=False,
        prune_deleted=False,
        manifest_path=str(tmp_path / "wiki.manifest.json"),
        dry_run=False,
        allow_large_incremental=False,
        explain_changes=False,
        sample_size=5,
    )
    defaults.update(overrides)
    return SimpleNamespace(**defaults)


def test_wiki_second_run_skips_unchanged_pages(tmp_path):
    module = load_build_index()
    wiki_root = tmp_path / "wiki"
    write_wiki_page(wiki_root, "papers/a.md", "# A\n\nhello")
    args = make_wiki_args(tmp_path)
    store = FakeWikiStore(collection_name="wiki_fake-model")
    embedder = FakeEmbedder()

    first = module.index_wiki(args, embedder=embedder, store=store)
    first_calls = embedder.embed_calls
    second = module.index_wiki(args, embedder=embedder, store=store)

    assert first["indexed_sections"] == 1
    assert second["indexed_sections"] == 0
    assert embedder.embed_calls == first_calls


def test_wiki_incremental_reindexes_only_changed_page(tmp_path):
    module = load_build_index()
    wiki_root = tmp_path / "wiki"
    page_a = write_wiki_page(wiki_root, "papers/a.md", "# A\n\nhello")
    page_b = write_wiki_page(wiki_root, "topics/b.md", "# B\n\nworld")
    args = make_wiki_args(tmp_path)
    store = FakeWikiStore(collection_name="wiki_fake-model")
    embedder = FakeEmbedder()

    module.index_wiki(args, embedder=embedder, store=store)
    first_calls = embedder.embed_calls
    page_a.write_text("# A\n\nhello changed", encoding="utf-8")

    summary = module.index_wiki(args, embedder=embedder, store=store)

    assert summary["indexed_sections"] == 1
    assert embedder.embed_calls == first_calls + 1
    assert any(
        payload["metadata"].get("page_path") == str(page_b)
        for payload in store.docs.values()
    )
    assert any(
        payload["metadata"].get("page_path") == str(page_a)
        and "hello changed" in payload["document"]
        for payload in store.docs.values()
    )


def test_wiki_incremental_prunes_deleted_page(tmp_path):
    module = load_build_index()
    wiki_root = tmp_path / "wiki"
    page_a = write_wiki_page(wiki_root, "papers/a.md", "# A\n\nhello")
    page_b = write_wiki_page(wiki_root, "papers/b.md", "# B\n\nworld")
    args = make_wiki_args(tmp_path)
    store = FakeWikiStore(collection_name="wiki_fake-model")
    embedder = FakeEmbedder()

    module.index_wiki(args, embedder=embedder, store=store)
    page_b.unlink()

    summary = module.index_wiki(args, embedder=embedder, store=store)

    assert summary["indexed_sections"] == 0
    assert summary["deleted_sections"] == 1
    assert not any(
        payload["metadata"].get("page_path") == str(page_b)
        for payload in store.docs.values()
    )
    assert any(
        payload["metadata"].get("page_path") == str(page_a)
        for payload in store.docs.values()
    )


def test_wiki_dry_run_reports_incremental_plan_without_writing(tmp_path):
    module = load_build_index()
    wiki_root = tmp_path / "wiki"
    write_wiki_page(wiki_root, "papers/a.md", "# A\n\nhello")
    args = make_wiki_args(tmp_path, dry_run=True)
    store = FakeWikiStore(collection_name="wiki_fake-model")
    embedder = FakeEmbedder()

    summary = module.index_wiki(args, embedder=embedder, store=store)

    assert summary["new_pages"] == 1
    assert summary["indexed_sections"] == 0
    assert embedder.embed_calls == 0
    assert store.count() == 0
    assert not Path(args.manifest_path).exists()
