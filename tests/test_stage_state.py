from __future__ import annotations

import json
from pathlib import Path


def test_write_standalone_stage_state_records_ok(tmp_path, monkeypatch):
    from paper_compass import pipeline_sync

    timestamps = iter(
        [
            "2026-06-23T03:00:00Z",
            "2026-06-23T03:00:01Z",
            "2026-06-23T03:00:02Z",
        ]
    )
    monkeypatch.setattr(pipeline_sync, "_utc_now_iso", lambda: next(timestamps))
    monkeypatch.delenv("PAPER_COMPASS_SYNC_PARENT", raising=False)

    state_path = pipeline_sync.write_standalone_stage_state(
        tmp_path,
        stage="index_wiki",
        status="ok",
        dry_run=False,
    )

    payload = json.loads(Path(state_path).read_text(encoding="utf-8"))
    assert payload["status"] == "ok"
    assert payload["stage"] == "completed"
    assert payload["planned_stages"] == ["index_wiki"]
    assert payload["completed_stages"] == ["index_wiki"]
    assert payload["finished_at"] == "2026-06-23T03:00:01Z"
    assert payload["updated_at"] == "2026-06-23T03:00:02Z"
    assert payload["started_at"] == "2026-06-23T03:00:00Z"
    assert payload["run_id"].startswith("manual-index_wiki-")


def test_write_standalone_stage_state_skips_when_parent_sync_env_present(tmp_path, monkeypatch):
    from paper_compass import pipeline_sync

    monkeypatch.setenv("PAPER_COMPASS_SYNC_PARENT", "1")

    state_path = pipeline_sync.write_standalone_stage_state(
        tmp_path,
        stage="index_papers",
        status="ok",
    )

    assert state_path is None
    assert not (tmp_path / "data" / "state" / "last_sync.json").exists()
