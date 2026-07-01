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


class _RecordingLibrary:
    last_call = None

    def __init__(self, db_path, storage_path=None, *, immutable=False, timeout=30.0):
        type(self).last_call = {
            "db_path": db_path,
            "storage_path": storage_path,
            "immutable": immutable,
            "timeout": timeout,
        }
        self._items = [{"key": "A1", "title": "Paper", "pdf_path": "", "date": "2024"}]

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
            use_immutable=False,
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
            use_immutable=False,
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


def test_sync_zotero_passes_immutable_flag_from_prepared_db(monkeypatch, tmp_path):
    module = _load_sync_zotero_module()
    source = _fake_source(tmp_path)
    prepared_path = tmp_path / "prepared.sqlite"
    prepared_path.write_text("sqlite", encoding="utf-8")

    monkeypatch.setattr(module, "resolve_zotero_source", lambda **kwargs: source)
    monkeypatch.setattr(
        module,
        "prepare_zotero_database_for_read",
        lambda *args, **kwargs: SimpleNamespace(
            read_db_path=prepared_path,
            original_db_path=source.db_path,
            used_snapshot=False,
            snapshot_path=None,
            use_immutable=True,
        ),
    )
    monkeypatch.setattr(module, "ZoteroLibrary", _RecordingLibrary)
    monkeypatch.setattr(
        "sys.argv",
        [
            "sync_zotero.py",
            "--out-dir",
            str(tmp_path / "data" / "zotero-export"),
            "--text-dir",
            str(tmp_path / "data" / "texts"),
        ],
    )

    module.main()

    assert _RecordingLibrary.last_call is not None
    assert _RecordingLibrary.last_call["db_path"] == str(prepared_path)
    assert _RecordingLibrary.last_call["storage_path"] == str(source.storage_path)
    assert _RecordingLibrary.last_call["immutable"] is True


def test_sync_zotero_reuses_nonempty_cached_text_by_default(monkeypatch, tmp_path):
    module = _load_sync_zotero_module()
    source = _fake_source(tmp_path)
    pdf_path = tmp_path / "paper.pdf"
    pdf_path.write_text("pdf", encoding="utf-8")
    text_dir = tmp_path / "data" / "texts"
    text_dir.mkdir(parents=True, exist_ok=True)
    cached = text_dir / "A1.txt"
    cached.write_text("cached text", encoding="utf-8")
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
            use_immutable=False,
        ),
    )
    monkeypatch.setattr(module, "ZoteroLibrary", lambda *args, **kwargs: _FakeLibrary(items))

    class FakeExtractor:
        def __init__(self, filepath):
            raise AssertionError("extractor should not be constructed when cached text is reused")

    monkeypatch.setattr(module, "PDFExtractor", FakeExtractor)
    monkeypatch.setattr(
        "sys.argv",
        [
            "sync_zotero.py",
            "--extract-text",
            "--out-dir",
            str(tmp_path / "data" / "zotero-export"),
            "--text-dir",
            str(text_dir),
        ],
    )

    module.main()

    payload = json.loads((tmp_path / "data" / "zotero-export" / "library.json").read_text(encoding="utf-8"))
    assert payload[0]["text_file"] == str(cached)


def test_sync_zotero_force_reextract_text_ignores_cached_text(monkeypatch, tmp_path):
    module = _load_sync_zotero_module()
    source = _fake_source(tmp_path)
    pdf_path = tmp_path / "paper.pdf"
    pdf_path.write_text("pdf", encoding="utf-8")
    text_dir = tmp_path / "data" / "texts"
    text_dir.mkdir(parents=True, exist_ok=True)
    cached = text_dir / "A1.txt"
    cached.write_text("old cached text", encoding="utf-8")
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
            use_immutable=False,
        ),
    )
    monkeypatch.setattr(module, "ZoteroLibrary", lambda *args, **kwargs: _FakeLibrary(items))

    class FakeExtractor:
        def __init__(self, filepath):
            self.filepath = filepath

        def extract_all_text(self):
            return "fresh extracted text"

    monkeypatch.setattr(module, "PDFExtractor", FakeExtractor)
    monkeypatch.setattr(
        "sys.argv",
        [
            "sync_zotero.py",
            "--extract-text",
            "--force-reextract-text",
            "--out-dir",
            str(tmp_path / "data" / "zotero-export"),
            "--text-dir",
            str(text_dir),
        ],
    )

    module.main()

    assert cached.read_text(encoding="utf-8") == "fresh extracted text"
