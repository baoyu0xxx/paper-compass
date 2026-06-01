from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest

from paper_compass.zotero_sqlite import ZoteroLibrary


def _make_minimal_sqlite(path: Path) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(path)
    conn.execute("CREATE TABLE marker (id INTEGER PRIMARY KEY)")
    conn.commit()
    conn.close()
    return path


def test_zotero_library_opens_database_in_read_only_mode(tmp_path):
    db_path = _make_minimal_sqlite(tmp_path / "zotero.sqlite")
    storage_path = tmp_path / "storage"
    storage_path.mkdir()

    lib = ZoteroLibrary(str(db_path), storage_path=str(storage_path))
    try:
        conn = lib._get_connection()
        with pytest.raises(sqlite3.OperationalError, match="readonly|read-only|write"):
            conn.execute("CREATE TABLE should_fail (id INTEGER)")
    finally:
        lib.close()

    assert sqlite3.connect(db_path).execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name='should_fail'"
    ).fetchone() is None


def test_zotero_library_exposes_all_items_method(monkeypatch):
    lib = ZoteroLibrary("dummy.sqlite", storage_path="dummy-storage")

    called = {}

    def fake_query_items(pdf_only: bool):
        called["pdf_only"] = pdf_only
        return [{"key": "A1"}]

    monkeypatch.setattr(lib, "_query_items", fake_query_items)

    result = lib.get_all_items()

    assert result == [{"key": "A1"}]
    assert called["pdf_only"] is False


def test_zotero_library_pdf_only_helper_preserved(monkeypatch):
    lib = ZoteroLibrary("dummy.sqlite", storage_path="dummy-storage")

    called = {}

    def fake_query_items(pdf_only: bool):
        called["pdf_only"] = pdf_only
        return [{"key": "B2"}]

    monkeypatch.setattr(lib, "_query_items", fake_query_items)

    result = lib.get_all_items_with_pdfs()

    assert result == [{"key": "B2"}]
    assert called["pdf_only"] is True
