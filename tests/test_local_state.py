from __future__ import annotations

import json


def test_save_and_load_last_successful_zotero_source(tmp_path):
    from paper_compass.local_state import (
        load_last_successful_zotero_source,
        save_last_successful_zotero_source,
    )

    state_path = tmp_path / "data" / "state" / "source_config.json"
    save_last_successful_zotero_source(
        state_path,
        db_path="D:/zotero_backup/zotero.sqlite",
        storage_path="D:/zotero_backup/storage",
        source_kind="explicit",
        is_live_candidate=False,
        last_success_at="2026-06-23T01:30:00Z",
    )

    payload = json.loads(state_path.read_text(encoding="utf-8"))
    assert payload["zotero"]["db_path"] == "D:/zotero_backup/zotero.sqlite"
    assert payload["zotero"]["storage_path"] == "D:/zotero_backup/storage"

    loaded = load_last_successful_zotero_source(state_path)
    assert loaded == {
        "zotero_sqlite_path": "D:/zotero_backup/zotero.sqlite",
        "zotero_storage_path": "D:/zotero_backup/storage",
    }


def test_load_last_successful_zotero_source_returns_empty_for_missing_file(tmp_path):
    from paper_compass.local_state import load_last_successful_zotero_source

    assert load_last_successful_zotero_source(tmp_path / "missing.json") == {}


def test_load_last_successful_zotero_source_returns_empty_for_invalid_json(tmp_path):
    from paper_compass.local_state import load_last_successful_zotero_source

    state_path = tmp_path / "data" / "state" / "source_config.json"
    state_path.parent.mkdir(parents=True, exist_ok=True)
    state_path.write_text("not-json", encoding="utf-8")

    assert load_last_successful_zotero_source(state_path) == {}
