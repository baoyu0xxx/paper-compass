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


def test_run_sync_pipeline_dry_run_reports_commands_without_creating_state(tmp_path, monkeypatch):
    from paper_compass import pipeline_sync
    from paper_compass.pipeline_sync import SyncOptions, run_sync_pipeline

    monkeypatch.setattr(pipeline_sync, "inspect_index_health", lambda path: _report(severity="ok", summary="healthy"))

    result = run_sync_pipeline(
        SyncOptions(
            project_root=tmp_path,
            db_path=tmp_path / "data" / "vectordb",
            dry_run=True,
        )
    )

    assert result.status == "dry_run"
    assert result.planned_commands
    assert result.planned_commands[0][1].endswith("scripts/sync_zotero.py")
    assert result.health_summary == "ok: healthy"
    assert not (tmp_path / "data" / "state" / "sync.lock").exists()
    assert not (tmp_path / "data" / "state" / "last_sync.json").exists()


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
    assert payload["run_id"]
    assert payload["updated_at"]
    assert payload["started_at"]
    assert payload["started_at"] <= payload["updated_at"]


def test_run_sync_pipeline_preserves_started_at_across_stage_updates(tmp_path, monkeypatch):
    from paper_compass import pipeline_sync
    from paper_compass.pipeline_sync import SyncOptions, run_sync_pipeline

    timestamps = iter(
        [
            "2026-06-23T01:00:00Z",
            "2026-06-23T01:00:01Z",
            "2026-06-23T01:00:02Z",
            "2026-06-23T01:00:03Z",
            "2026-06-23T01:00:04Z",
            "2026-06-23T01:00:05Z",
            "2026-06-23T01:00:06Z",
            "2026-06-23T01:00:07Z",
            ]
    )
    monkeypatch.setattr(pipeline_sync, "_utc_now_iso", lambda: next(timestamps))
    monkeypatch.setattr(pipeline_sync, "inspect_index_health", lambda path: _report())
    monkeypatch.setattr(pipeline_sync, "_run_stage_command", lambda *args, **kwargs: None)

    run_sync_pipeline(
        SyncOptions(
            project_root=tmp_path,
            db_path=tmp_path / "vectordb",
            skip_wiki_ingest=True,
            skip_wiki_index=True,
        )
    )

    payload = json.loads((tmp_path / "data" / "state" / "last_sync.json").read_text(encoding="utf-8"))
    assert payload["started_at"] == "2026-06-23T01:00:01Z"
    assert payload["updated_at"] == "2026-06-23T01:00:06Z"
    assert payload["finished_at"] == "2026-06-23T01:00:05Z"


def test_run_sync_pipeline_remembers_last_successful_zotero_source_after_success(tmp_path, monkeypatch):
    from paper_compass import pipeline_sync
    from paper_compass.pipeline_sync import SyncOptions, run_sync_pipeline

    monkeypatch.setattr(pipeline_sync, "inspect_index_health", lambda path: _report())
    monkeypatch.setattr(pipeline_sync, "_run_stage_command", lambda *args, **kwargs: None)

    result = run_sync_pipeline(
        SyncOptions(
            project_root=tmp_path,
            db_path=tmp_path / "vectordb",
            db_source_path="D:/zotero_backup/zotero.sqlite",
            storage_path="D:/zotero_backup/storage",
            skip_wiki_ingest=True,
            skip_wiki_index=True,
        )
    )

    source_state_path = tmp_path / "data" / "state" / "source_config.json"
    assert result.status == "ok"
    assert source_state_path.exists()
    payload = json.loads(source_state_path.read_text(encoding="utf-8"))
    assert payload["zotero"]["db_path"] == "D:/zotero_backup/zotero.sqlite"
    assert payload["zotero"]["storage_path"] == "D:/zotero_backup/storage"
    assert payload["zotero"]["source_kind"] == "explicit"
    assert payload["zotero"]["is_live_candidate"] is False


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


def test_run_sync_pipeline_rejects_active_lock(tmp_path, monkeypatch):
    from paper_compass import pipeline_sync
    from paper_compass.pipeline_sync import SyncOptions, run_sync_pipeline

    monkeypatch.setattr(pipeline_sync, "inspect_index_health", lambda path: _report())
    lock_path = tmp_path / "data" / "state" / "sync.lock"
    lock_path.parent.mkdir(parents=True, exist_ok=True)
    lock_path.write_text(
        json.dumps(
            {
                "pid": 9999,
                "started_at": "2026-06-23T01:00:00Z",
                "process_start_time": 123.0,
            }
        ),
        encoding="utf-8",
    )
    monkeypatch.setattr(pipeline_sync, "_process_is_active", lambda pid, process_start_time=None: True)

    with pytest.raises(RuntimeError, match="appears active"):
        run_sync_pipeline(
            SyncOptions(
                project_root=tmp_path,
                db_path=tmp_path / "vectordb",
                skip_wiki_ingest=True,
                skip_wiki_index=True,
            )
        )


def test_run_sync_pipeline_removes_stale_lock_and_continues(tmp_path, monkeypatch):
    from paper_compass import pipeline_sync
    from paper_compass.pipeline_sync import SyncOptions, run_sync_pipeline

    monkeypatch.setattr(pipeline_sync, "inspect_index_health", lambda path: _report())
    monkeypatch.setattr(pipeline_sync, "_run_stage_command", lambda *args, **kwargs: None)
    monkeypatch.setattr(pipeline_sync, "_process_is_active", lambda pid, process_start_time=None: False)

    lock_path = tmp_path / "data" / "state" / "sync.lock"
    lock_path.parent.mkdir(parents=True, exist_ok=True)
    lock_path.write_text(
        json.dumps(
            {
                "pid": 9999,
                "started_at": "2026-06-23T01:00:00Z",
                "process_start_time": 123.0,
            }
        ),
        encoding="utf-8",
    )

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


def test_run_sync_pipeline_force_unlock_removes_lock_and_exits(tmp_path, monkeypatch):
    from paper_compass import pipeline_sync
    from paper_compass.pipeline_sync import SyncOptions, run_sync_pipeline

    monkeypatch.setattr(pipeline_sync, "inspect_index_health", lambda path: _report())
    lock_path = tmp_path / "data" / "state" / "sync.lock"
    lock_path.parent.mkdir(parents=True, exist_ok=True)
    lock_path.write_text(json.dumps({"pid": 9999, "started_at": "2026-06-23T01:00:00Z"}), encoding="utf-8")
    monkeypatch.setattr(pipeline_sync, "_process_is_active", lambda pid, process_start_time=None: False)

    result = run_sync_pipeline(
        SyncOptions(
            project_root=tmp_path,
            db_path=tmp_path / "vectordb",
            force_unlock=True,
        )
    )

    assert result.status == "unlocked"
    assert result.planned_stages == []
    assert result.completed_stages == []
    assert not lock_path.exists()


def test_build_stage_command_passes_snapshot_flags(tmp_path):
    from paper_compass.pipeline_sync import SyncOptions, _build_stage_command

    options = SyncOptions(
        project_root=tmp_path,
        db_path=tmp_path / "vectordb",
        db_source_path="/tmp/zotero.sqlite",
        storage_path="/tmp/storage",
        snapshot_db="always",
        snapshot_dir="data/state/zotero-snapshots",
        allow_live_zotero_read=True,
    )

    command = _build_stage_command(options, "sync_zotero")

    assert "--snapshot-db" in command
    assert command[command.index("--snapshot-db") + 1] == "always"
    assert "--snapshot-dir" in command
    assert command[command.index("--snapshot-dir") + 1] == "data/state/zotero-snapshots"
    assert "--snapshot-keep" in command
    assert command[command.index("--snapshot-keep") + 1] == "5"
    assert "--snapshot-max-age-days" in command
    assert command[command.index("--snapshot-max-age-days") + 1] == "0"
    assert "--allow-live-zotero-read" in command


def test_build_stage_command_adds_sync_zotero_dry_run_flag(tmp_path):
    from paper_compass.pipeline_sync import SyncOptions, _build_stage_command

    options = SyncOptions(
        project_root=tmp_path,
        db_path=tmp_path / "data" / "vectordb",
        dry_run=True,
    )

    command = _build_stage_command(options, "sync_zotero")

    assert "--dry-run" in command


def test_build_stage_command_adds_paper_index_dry_run_flag(tmp_path):
    from paper_compass.pipeline_sync import SyncOptions, _build_stage_command

    options = SyncOptions(
        project_root=tmp_path,
        db_path=tmp_path / "data" / "vectordb",
        dry_run=True,
    )

    command = _build_stage_command(options, "index_papers")

    assert "--dry-run" in command
