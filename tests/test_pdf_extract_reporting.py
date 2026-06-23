from __future__ import annotations

import importlib.util
import json
from pathlib import Path
from types import SimpleNamespace


def _load_sync_zotero_module():
    script = Path(__file__).resolve().parents[1] / "scripts" / "sync_zotero.py"
    spec = importlib.util.spec_from_file_location("paper_compass_sync_zotero", script)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


class _FakeLibrary:
    def __init__(self, items):
        self._items = items

    def get_all_items_with_pdfs(self):
        return self._items

    def close(self):
        return None


def _fake_source(tmp_path):
    db_path = tmp_path / "zotero.sqlite"
    db_path.write_text("sqlite", encoding="utf-8")
    storage = tmp_path / "storage"
    storage.mkdir(exist_ok=True)
    return SimpleNamespace(
        db_path=db_path,
        storage_path=storage,
        source_kind="explicit",
        tried=[],
        is_live_candidate=False,
    )


def test_sync_zotero_writes_report_for_empty_extracted_text(monkeypatch, tmp_path):
    module = _load_sync_zotero_module()
    source = _fake_source(tmp_path)
    pdf_path = tmp_path / "paper.pdf"
    pdf_path.write_text("pdf", encoding="utf-8")
    items = [{"key": "A1", "title": "Paper", "pdf_path": str(pdf_path), "date": "2024"}]

    monkeypatch.setattr(module, "resolve_zotero_source", lambda **kwargs: source)
    monkeypatch.setattr(
        module,
        "prepare_zotero_database_for_read",
        lambda *args, **kwargs: SimpleNamespace(
            read_db_path=source.db_path,
            original_db_path=source.db_path,
            used_snapshot=False,
            snapshot_path=None,
        ),
    )
    monkeypatch.setattr(module, "ZoteroLibrary", lambda *args, **kwargs: _FakeLibrary(items))

    class FakeExtractor:
        def __init__(self, filepath):
            self.filepath = filepath

        def extract_all_text(self):
            return ""

    monkeypatch.setattr(module, "PDFExtractor", FakeExtractor)
    monkeypatch.setattr(
        "sys.argv",
        [
            "sync_zotero.py",
            "--extract-text",
            "--out-dir",
            str(tmp_path / "data" / "zotero-export"),
            "--text-dir",
            str(tmp_path / "data" / "texts"),
        ],
    )

    module.main()

    report_path = tmp_path / "data" / "logs" / "pdf_extract_failures.jsonl"
    assert report_path.exists()
    payload = json.loads(report_path.read_text(encoding="utf-8").splitlines()[0])
    assert payload["stage"] == "sync_zotero"
    assert payload["key"] == "A1"
    assert payload["reason"] == "empty text"


def test_sync_zotero_writes_report_for_extract_exception(monkeypatch, tmp_path):
    module = _load_sync_zotero_module()
    source = _fake_source(tmp_path)
    pdf_path = tmp_path / "paper.pdf"
    pdf_path.write_text("pdf", encoding="utf-8")
    items = [{"key": "A1", "title": "Paper", "pdf_path": str(pdf_path), "date": "2024"}]

    monkeypatch.setattr(module, "resolve_zotero_source", lambda **kwargs: source)
    monkeypatch.setattr(
        module,
        "prepare_zotero_database_for_read",
        lambda *args, **kwargs: SimpleNamespace(
            read_db_path=source.db_path,
            original_db_path=source.db_path,
            used_snapshot=False,
            snapshot_path=None,
        ),
    )
    monkeypatch.setattr(module, "ZoteroLibrary", lambda *args, **kwargs: _FakeLibrary(items))

    class FakeExtractor:
        def __init__(self, filepath):
            self.filepath = filepath

        def extract_all_text(self):
            raise RuntimeError("boom")

    monkeypatch.setattr(module, "PDFExtractor", FakeExtractor)
    monkeypatch.setattr(
        "sys.argv",
        [
            "sync_zotero.py",
            "--extract-text",
            "--out-dir",
            str(tmp_path / "data" / "zotero-export"),
            "--text-dir",
            str(tmp_path / "data" / "texts"),
        ],
    )

    module.main()

    report_path = tmp_path / "data" / "logs" / "pdf_extract_failures.jsonl"
    assert report_path.exists()
    payload = json.loads(report_path.read_text(encoding="utf-8").splitlines()[0])
    assert payload["stage"] == "sync_zotero"
    assert payload["key"] == "A1"
    assert payload["reason"] == "extract error"
    assert payload["exception"] == "boom"
