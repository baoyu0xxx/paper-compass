import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from helpers import FakeEmbedder, FakeStore, load_build_index
from paper_compass.index_manifest import compute_text_sha1, diff_manifest


def test_load_manifest_missing_path_returns_independent_items_dicts(tmp_path):
    from paper_compass.index_manifest import load_manifest

    first = load_manifest(str(tmp_path / "missing-a.json"))
    second = load_manifest(str(tmp_path / "missing-b.json"))

    first["items"]["A"] = {"text_sha1": "a"}

    assert second["items"] == {}


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
    library_path.write_text(
        json.dumps(items, ensure_ascii=False, indent=2), encoding="utf-8"
    )
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
        dry_run=False,
        allow_large_incremental=False,
        explain_changes=False,
        sample_size=5,
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
    module = load_build_index()
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
    module = load_build_index()
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
    assert all(
        payload["metadata"].get("item_key") == "A1"
        for payload in store.docs.values()
    )


def test_incremental_prune_deleted_removes_chunks(tmp_path):
    module = load_build_index()
    item_a = make_paper(tmp_path, "A1", "a" * 2200)
    item_b = make_paper(tmp_path, "B2", "b" * 2200)
    library_path = write_library(tmp_path, [item_a, item_b])
    store = FakeStore()
    embedder = FakeEmbedder()

    module.index_papers(
        make_args(tmp_path, library_path), embedder=embedder, store=store
    )
    pruned_library = write_library(tmp_path, [item_a])
    summary = module.index_papers(
        make_args(tmp_path, pruned_library, prune_deleted=True),
        embedder=embedder,
        store=store,
    )

    assert summary["deleted"] == 1
    assert summary["deleted_chunks"] > 0
    assert not any(
        payload["metadata"].get("item_key") == "B2"
        for payload in store.docs.values()
    )


def test_incremental_repairs_manifest_entry_missing_from_store(tmp_path):
    module = load_build_index()
    item_a = make_paper(tmp_path, "A1", "a" * 2200)
    item_b = make_paper(tmp_path, "B2", "b" * 2200)
    library_path = write_library(tmp_path, [item_a, item_b])
    args = make_args(tmp_path, library_path)
    store = FakeStore()
    embedder = FakeEmbedder()

    module.index_papers(args, embedder=embedder, store=store)
    deleted = store.delete_item("B2")
    assert deleted > 0

    summary = module.index_papers(args, embedder=embedder, store=store)

    assert summary["indexed_papers"] == 1
    assert summary["missing_vectors"] == 1
    assert summary["unchanged"] == 1
    assert store.get_chunk_ids_for_item("B2")


def test_incremental_refuses_large_changed_set_without_override(tmp_path):
    module = load_build_index()
    items = [make_paper(tmp_path, f"P{i}", chr(97 + i) * 2200) for i in range(4)]
    library_path = write_library(tmp_path, items)
    args = make_args(tmp_path, library_path)
    store = FakeStore()
    embedder = FakeEmbedder()

    module.index_papers(args, embedder=embedder, store=store)
    for item in items:
        Path(item["text_file"]).write_text("changed " * 400, encoding="utf-8")

    with pytest.raises(SystemExit) as exc:
        module.index_papers(args, embedder=embedder, store=store)

    assert exc.value.code == 3


def test_incremental_large_guard_uses_configured_thresholds(tmp_path, monkeypatch):
    from paper_compass.config import IndexingSettings

    module = load_build_index()
    items = [make_paper(tmp_path, f"P{i}", chr(97 + i) * 2200) for i in range(4)]
    library_path = write_library(tmp_path, items)
    args = make_args(tmp_path, library_path)
    store = FakeStore()
    embedder = FakeEmbedder()

    module.index_papers(args, embedder=embedder, store=store)
    for item in items:
        Path(item["text_file"]).write_text("changed " * 400, encoding="utf-8")
    monkeypatch.setattr(
        module,
        "resolve_indexing_settings",
        lambda: IndexingSettings(large_incremental_change_ratio=1.0, large_incremental_change_minimum=99),
    )

    summary = module.index_papers(args, embedder=embedder, store=store)

    assert summary["changed"] == 4
    assert summary["indexed_papers"] == 4


def test_incremental_large_changed_set_can_be_explicitly_allowed(tmp_path):
    module = load_build_index()
    items = [make_paper(tmp_path, f"P{i}", chr(97 + i) * 2200) for i in range(4)]
    library_path = write_library(tmp_path, items)
    args = make_args(tmp_path, library_path, allow_large_incremental=True)
    store = FakeStore()
    embedder = FakeEmbedder()

    module.index_papers(args, embedder=embedder, store=store)
    for item in items:
        Path(item["text_file"]).write_text("changed " * 400, encoding="utf-8")

    summary = module.index_papers(args, embedder=embedder, store=store)

    assert summary["changed"] == 4
    assert summary["indexed_papers"] == 4


def test_incremental_metadata_only_updates_chunk_metadata_without_embedding(tmp_path):
    module = load_build_index()
    item = make_paper(tmp_path, "A1", "a" * 2200)
    library_path = write_library(tmp_path, [item])
    args = make_args(tmp_path, library_path)
    store = FakeStore()
    embedder = FakeEmbedder()

    first = module.index_papers(args, embedder=embedder, store=store)
    calls_after_first = embedder.embed_calls
    updated_item = {**item, "title": "Updated Title", "tags": ["updated"]}
    library_path.write_text(json.dumps([updated_item], ensure_ascii=False, indent=2), encoding="utf-8")
    second = module.index_papers(args, embedder=embedder, store=store)

    assert first["indexed_papers"] == 1
    assert second["metadata_only"] == 1
    assert second["indexed_papers"] == 0
    assert embedder.embed_calls == calls_after_first
    assert all(payload["metadata"]["title"] == "Updated Title" for payload in store.docs.values())


def test_incremental_dry_run_does_not_write_manifest_or_vectors(tmp_path):
    module = load_build_index()
    item = make_paper(tmp_path, "A1", "a" * 2200)
    library_path = write_library(tmp_path, [item])
    manifest_path = tmp_path / "manifest.json"
    args = make_args(tmp_path, library_path, dry_run=True, manifest_path=str(manifest_path))
    store = FakeStore()
    embedder = FakeEmbedder()

    summary = module.index_papers(args, embedder=embedder, store=store)

    assert summary["dry_run"] is True
    assert summary["embedding_required"] == 1
    assert embedder.embed_calls == 0
    assert store.count() == 0
    assert not manifest_path.exists()


def test_incremental_dry_run_exposes_metadata_change_reasons(tmp_path):
    module = load_build_index()
    item = make_paper(tmp_path, "A1", "a" * 2200)
    library_path = write_library(tmp_path, [item])
    store = FakeStore()
    embedder = FakeEmbedder()

    module.index_papers(make_args(tmp_path, library_path), embedder=embedder, store=store)
    updated_item = {**item, "tags": ["updated"]}
    library_path.write_text(json.dumps([updated_item], ensure_ascii=False, indent=2), encoding="utf-8")

    summary = module.index_papers(
        make_args(tmp_path, library_path, dry_run=True, explain_changes=True, sample_size=5),
        embedder=embedder,
        store=store,
    )

    assert summary["metadata_only"] == 1
    assert summary["metadata_reason_counts"]["tags changed"] == 1
    assert summary["metadata_reason_samples"][0]["key"] == "A1"


def test_index_papers_reports_missing_text_failures(tmp_path):
    module = load_build_index()
    item = make_paper(tmp_path, "A1", "a" * 2200)
    Path(item["text_file"]).write_text("", encoding="utf-8")
    library_path = write_library(tmp_path, [item])

    module.index_papers(
        make_args(tmp_path, library_path),
        embedder=FakeEmbedder(),
        store=FakeStore(),
    )

    report_path = tmp_path / "logs" / "pdf_extract_failures.jsonl"
    assert report_path.exists()
    payload = json.loads(report_path.read_text(encoding="utf-8").splitlines()[0])
    assert payload["stage"] == "build_index"
    assert payload["key"] == "A1"
    assert payload["reason"] == "missing text"


def test_wiki_reindex_is_idempotent(tmp_path):
    module = load_build_index()
    wiki_root = tmp_path / "wiki"
    papers_dir = wiki_root / "papers"
    papers_dir.mkdir(parents=True)
    page = papers_dir / "sample.md"
    page.write_text("# Title\n## Section\nBody one", encoding="utf-8")

    args = make_args(
        tmp_path,
        tmp_path / "unused.json",
        wiki=True,
        wiki_root=str(wiki_root),
        incremental=False,
    )
    store = FakeStore(collection_name="wiki_fake-model")
    embedder = FakeEmbedder()

    first = module.index_wiki(args, embedder=embedder, store=store)
    page.write_text(
        "# Title\n## Section\nBody two updated", encoding="utf-8"
    )
    second = module.index_wiki(args, embedder=embedder, store=store)

    assert first["indexed_sections"] == second["indexed_sections"]
    assert store.count() == first["indexed_sections"]
    assert any(
        "updated" in payload["document"] for payload in store.docs.values()
    )


def test_index_papers_refuses_corrupted_vectordb(tmp_path, monkeypatch, capsys):
    module = load_build_index()
    item = make_paper(tmp_path, "A1", "a" * 2200)
    library_path = write_library(tmp_path, [item])
    args = make_args(tmp_path, library_path)

    class Report:
        severity = "corrupted"
        summary = "metadata segment broken"
        recommended_action = "paper-compass sync --rebuild papers --backup-corrupted-db"

    monkeypatch.setattr(module, "inspect_index_health", lambda path: Report())

    with pytest.raises(SystemExit) as exc:
        module.index_papers(args, embedder=FakeEmbedder(), store=FakeStore())

    assert exc.value.code == 2
    output = capsys.readouterr().out
    assert "corrupted" in output.lower()
    assert "metadata segment broken" in output
    assert "paper-compass sync --rebuild papers" in output


def test_index_papers_refuses_warning_vectordb(tmp_path, monkeypatch, capsys):
    module = load_build_index()
    item = make_paper(tmp_path, "A1", "a" * 2200)
    library_path = write_library(tmp_path, [item])
    args = make_args(tmp_path, library_path)

    class Report:
        severity = "warning"
        summary = "sqlite transient files present: journal"
        recommended_action = "inspect and rebuild if needed"

    monkeypatch.setattr(module, "inspect_index_health", lambda path: Report())

    with pytest.raises(SystemExit) as exc:
        module.index_papers(args, embedder=FakeEmbedder(), store=FakeStore())

    assert exc.value.code == 2
    output = capsys.readouterr().out
    assert "vectordb requires attention" in output.lower()
    assert "journal" in output.lower()


def test_diff_manifest_ignores_path_and_mtime_drift_when_text_is_unchanged():
    current = {
        "A": {
            "item_key": "A",
            "pdf_path": "/mnt/d/papers/A.pdf",
            "text_file": "/mnt/d/texts/A.txt",
            "text_sha1": compute_text_sha1("same text"),
            "text_size": len("same text"),
            "pdf_mtime": 200,
            "chunking_version": "v1",
            "embedding_model_id": "m1",
            "chunk_count": 2,
            "updated_at": "2026-06-01T00:00:00Z",
        }
    }
    previous = {
        "A": {
            "item_key": "A",
            "pdf_path": r"D:\\papers\\A.pdf",
            "text_file": "",
            "text_sha1": compute_text_sha1("same text"),
            "text_size": len("same text"),
            "pdf_mtime": 100,
            "chunking_version": "v1",
            "embedding_model_id": "m1",
            "chunk_count": 2,
            "updated_at": "2026-05-01T00:00:00Z",
        }
    }

    result = diff_manifest(current, previous)

    assert result == {
        "new": [],
        "changed": [],
        "unchanged": ["A"],
        "deleted": [],
    }


def test_diff_manifest_still_detects_real_text_change():
    current = {
        "A": {
            "item_key": "A",
            "pdf_path": "/mnt/d/papers/A.pdf",
            "text_file": "/mnt/d/texts/A.txt",
            "text_sha1": compute_text_sha1("new text"),
            "text_size": len("new text"),
            "pdf_mtime": 200,
            "chunking_version": "v1",
            "embedding_model_id": "m1",
            "chunk_count": 2,
            "updated_at": "2026-06-01T00:00:00Z",
        }
    }
    previous = {
        "A": {
            "item_key": "A",
            "pdf_path": r"D:\\papers\\A.pdf",
            "text_file": "",
            "text_sha1": compute_text_sha1("old text"),
            "text_size": len("old text"),
            "pdf_mtime": 100,
            "chunking_version": "v1",
            "embedding_model_id": "m1",
            "chunk_count": 2,
            "updated_at": "2026-05-01T00:00:00Z",
        }
    }

    result = diff_manifest(current, previous)

    assert result == {
        "new": [],
        "changed": ["A"],
        "unchanged": [],
        "deleted": [],
    }
