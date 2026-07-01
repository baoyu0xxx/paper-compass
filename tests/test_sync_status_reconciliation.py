from __future__ import annotations

import json
from pathlib import Path


def test_read_sync_status_marks_running_without_lock_as_stale(monkeypatch, tmp_path):
    from paper_compass.cli import status as status_module
    from paper_compass.pipeline_sync import LockStatus

    state_dir = tmp_path / "data" / "state"
    state_dir.mkdir(parents=True, exist_ok=True)
    last_sync = state_dir / "last_sync.json"
    last_sync.write_text(
        json.dumps(
            {
                "run_id": "20260623-000001-1111",
                "started_at": "2026-06-23T00:00:01Z",
                "updated_at": "2026-06-23T00:00:30Z",
                "finished_at": None,
                "status": "running",
                "stage": "sync_zotero",
                "planned_stages": ["sync_zotero", "index_papers"],
                "completed_stages": [],
                "error": "",
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    source_config = state_dir / "source_config.json"
    source_config.write_text(json.dumps({"zotero": {}}, ensure_ascii=False), encoding="utf-8")

    monkeypatch.setattr(status_module, "PROJECT_ROOT", tmp_path)
    monkeypatch.setattr(
        status_module,
        "inspect_sync_lock",
        lambda project_root: LockStatus(
            path=state_dir / "sync.lock",
            exists=False,
            stale=False,
            reason="",
            pid=None,
            started_at=None,
            payload=None,
        ),
    )

    sync = status_module._read_sync_status()

    assert sync["last_sync"]["status"] == "stale"
    assert sync["last_sync"]["stage"] == "sync_zotero"
    assert sync["lock"]["exists"] is False
    assert sync["lock"]["stale"] is True
    assert sync["lock"]["reason"] == "missing lock for running last_sync state"


def test_read_sync_status_marks_running_with_stale_lock_as_stale(monkeypatch, tmp_path):
    from paper_compass.cli import status as status_module
    from paper_compass.pipeline_sync import LockStatus

    state_dir = tmp_path / "data" / "state"
    state_dir.mkdir(parents=True, exist_ok=True)
    (state_dir / "last_sync.json").write_text(
        json.dumps(
            {
                "run_id": "20260623-000001-1111",
                "started_at": "2026-06-23T00:00:01Z",
                "updated_at": "2026-06-23T00:00:30Z",
                "finished_at": None,
                "status": "running",
                "stage": "index_papers",
                "planned_stages": ["sync_zotero", "index_papers"],
                "completed_stages": ["sync_zotero"],
                "error": "",
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    (state_dir / "source_config.json").write_text(json.dumps({"zotero": {}}, ensure_ascii=False), encoding="utf-8")

    monkeypatch.setattr(status_module, "PROJECT_ROOT", tmp_path)
    monkeypatch.setattr(
        status_module,
        "inspect_sync_lock",
        lambda project_root: LockStatus(
            path=state_dir / "sync.lock",
            exists=True,
            stale=True,
            reason="pid not running",
            pid=1234,
            started_at="2026-06-23T00:00:00Z",
            payload={"pid": 1234},
        ),
    )

    sync = status_module._read_sync_status()

    assert sync["last_sync"]["status"] == "stale"
    assert sync["lock"]["stale"] is True
    assert sync["lock"]["reason"] == "pid not running"
