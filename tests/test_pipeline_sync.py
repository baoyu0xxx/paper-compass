from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace

import pytest


def _report(severity="ok", summary="ok", recommended_action="none"):
    return SimpleNamespace(
        severity=severity,
        summary=summary,
        recommended_action=recommended_action,
    )


def test_run_sync_pipeline_dry_run_reports_all_stages(tmp_path):
    from paper_compass.pipeline_sync import SyncOptions, run_sync_pipeline

    result = run_sync_pipeline(
        SyncOptions(
            project_root=tmp_path,
            db_path=tmp_path / "vectordb",
            dry_run=True,
        )
    )

    assert result.status == "dry_run"
    assert result.completed_stages == []
    assert result.planned_stages == [
        "sync_zotero",
        "index_papers",
        "ingest_wiki",
        "index_wiki",
    ]


def test_run_sync_pipeline_aborts_on_corrupted_vectordb(tmp_path, monkeypatch):
    from paper_compass import pipeline_sync
    from paper_compass.pipeline_sync import SyncOptions, VectordbHealthError

    monkeypatch.setattr(
        pipeline_sync,
        "inspect_index_health",
        lambda path: _report(
            severity="corrupted",
            summary="metadata segment broken",
            recommended_action="paper-compass sync --rebuild papers --backup-corrupted-db",
        ),
    )

    with pytest.raises(VectordbHealthError, match="metadata segment broken"):
        pipeline_sync.run_sync_pipeline(
            SyncOptions(project_root=tmp_path, db_path=tmp_path / "vectordb")
        )


def test_run_sync_pipeline_backs_up_corrupted_db_when_rebuild_requested(tmp_path, monkeypatch):
    from paper_compass import pipeline_sync
    from paper_compass.pipeline_sync import SyncOptions, run_sync_pipeline

    db_path = tmp_path / "vectordb"
    db_path.mkdir()
    (db_path / "chroma.sqlite3").write_text("broken", encoding="utf-8")

    monkeypatch.setattr(
        pipeline_sync,
        "inspect_index_health",
        lambda path: _report(
            severity="corrupted",
            summary="metadata segment broken",
            recommended_action="rebuild",
        ),
    )
    monkeypatch.setattr(pipeline_sync, "_run_stage_command", lambda *args, **kwargs: None)

    result = run_sync_pipeline(
        SyncOptions(
            project_root=tmp_path,
            db_path=db_path,
            rebuild="papers",
            backup_corrupted_db=True,
            skip_wiki_ingest=True,
            skip_wiki_index=True,
        )
    )

    assert result.status == "ok"
    backups = list(tmp_path.glob("vectordb.bak.*"))
    assert len(backups) == 1
    assert result.completed_stages == ["sync_zotero", "index_papers"]


def test_run_sync_pipeline_writes_state_file(tmp_path, monkeypatch):
    from paper_compass import pipeline_sync
    from paper_compass.pipeline_sync import SyncOptions, run_sync_pipeline

    monkeypatch.setattr(pipeline_sync, "inspect_index_health", lambda path: _report())
    monkeypatch.setattr(pipeline_sync, "_run_stage_command", lambda *args, **kwargs: None)

    result = run_sync_pipeline(
        SyncOptions(
            project_root=tmp_path,
            db_path=tmp_path / "vectordb",
            skip_wiki_ingest=True,
            skip_wiki_index=True,
        )
    )

    state_path = tmp_path / "data" / "state" / "last_sync.json"
    assert result.status == "ok"
    assert state_path.exists()
    payload = json.loads(state_path.read_text(encoding="utf-8"))
    assert payload["status"] == "ok"
    assert payload["stage"] == "completed"
    assert payload["planned_stages"] == ["sync_zotero", "index_papers"]
    assert payload["completed_stages"] == ["sync_zotero", "index_papers"]


def test_run_sync_pipeline_creates_and_removes_lock(tmp_path, monkeypatch):
    from paper_compass import pipeline_sync
    from paper_compass.pipeline_sync import SyncOptions, run_sync_pipeline

    monkeypatch.setattr(pipeline_sync, "inspect_index_health", lambda path: _report())
    monkeypatch.setattr(pipeline_sync, "_run_stage_command", lambda *args, **kwargs: None)

    lock_path = tmp_path / "data" / "state" / "sync.lock"
    result = run_sync_pipeline(
        SyncOptions(
            project_root=tmp_path,
            db_path=tmp_path / "vectordb",
            skip_wiki_ingest=True,
            skip_wiki_index=True,
        )
    )

    assert result.status == "ok"
    assert not lock_path.exists()
