from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Sequence

from paper_compass.index_health import inspect_index_health


class VectordbHealthError(RuntimeError):
    pass


@dataclass
class SyncOptions:
    project_root: Path
    db_path: Path
    db_source_path: str | None = None
    storage_path: str | None = None
    snapshot_db: str = "auto"
    snapshot_dir: str = "data/state/zotero-snapshots"
    snapshot_keep: int = 5
    snapshot_max_age_days: int = 0
    allow_live_zotero_read: bool = False
    library_path: str = "data/zotero-export/library.json"
    wiki_root: str = "./wiki"
    workers: int = 10
    dry_run: bool = False
    rebuild: str = "none"
    backup_corrupted_db: bool = False
    skip_zotero_sync: bool = False
    skip_paper_index: bool = False
    skip_wiki_ingest: bool = False
    skip_wiki_index: bool = False


@dataclass
class SyncResult:
    status: str
    summary: str
    planned_stages: list[str]
    completed_stages: list[str]
    state_path: str
    planned_commands: list[list[str]] | None = None
    health_summary: str = ""


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _timestamp_slug() -> str:
    return datetime.now().strftime("%Y%m%d-%H%M%S")


def _state_dir(project_root: Path) -> Path:
    return project_root / "data" / "state"


def _state_path(project_root: Path) -> Path:
    return _state_dir(project_root) / "last_sync.json"


def _lock_path(project_root: Path) -> Path:
    return _state_dir(project_root) / "sync.lock"


def _write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def _write_state(
    state_path: Path,
    *,
    status: str,
    stage: str,
    planned_stages: list[str],
    completed_stages: list[str],
    error: str = "",
    finished_at: str | None = None,
) -> None:
    _write_json(
        state_path,
        {
            "started_at": _utc_now_iso(),
            "finished_at": finished_at,
            "status": status,
            "stage": stage,
            "planned_stages": planned_stages,
            "completed_stages": completed_stages,
            "error": error,
        },
    )


def _backup_vectordb(db_path: Path) -> Path | None:
    if not db_path.exists():
        return None
    backup_path = db_path.parent / f"{db_path.name}.bak.{_timestamp_slug()}"
    shutil.move(str(db_path), str(backup_path))
    db_path.mkdir(parents=True, exist_ok=True)
    return backup_path


def _script_path(project_root: Path, script_name: str) -> str:
    return (project_root / "scripts" / script_name).as_posix()


def _build_stage_command(options: SyncOptions, stage: str) -> list[str]:
    project_root = options.project_root
    python = sys.executable
    if stage == "sync_zotero":
        cmd = [python, _script_path(project_root, "sync_zotero.py")]
        if options.db_source_path:
            cmd += ["--db-path", options.db_source_path]
        if options.storage_path:
            cmd += ["--storage-path", options.storage_path]
        cmd += [
            "--extract-text",
            "--snapshot-db",
            options.snapshot_db,
            "--snapshot-dir",
            options.snapshot_dir,
            "--snapshot-keep",
            str(options.snapshot_keep),
            "--snapshot-max-age-days",
            str(options.snapshot_max_age_days),
        ]
        if options.allow_live_zotero_read:
            cmd.append("--allow-live-zotero-read")
        return cmd
    if stage == "index_papers":
        cmd = [
            python,
            _script_path(project_root, "build_index.py"),
            "--library",
            options.library_path,
            "--db-path",
            str(options.db_path),
        ]
        if options.rebuild in {"papers", "all"}:
            cmd.append("--full-rebuild")
        else:
            cmd += ["--incremental", "--prune-deleted"]
        return cmd
    if stage == "ingest_wiki":
        cmd = [
            python,
            _script_path(project_root, "ingest_to_wiki.py"),
            "--library",
            options.library_path,
            "--wiki-root",
            options.wiki_root,
            "--skip-existing",
            "--workers",
            str(options.workers),
        ]
        return cmd
    if stage == "index_wiki":
        cmd = [
            python,
            _script_path(project_root, "build_index.py"),
            "--wiki",
            "--db-path",
            str(options.db_path),
            "--wiki-root",
            options.wiki_root,
        ]
        return cmd
    raise ValueError(f"Unknown stage: {stage}")


def _run_stage_command(project_root: Path, command: Sequence[str]) -> None:
    completed = subprocess.run(list(command), cwd=str(project_root), text=True)
    if completed.returncode != 0:
        raise RuntimeError(f"Command failed with exit code {completed.returncode}: {' '.join(command)}")


def _planned_stages(options: SyncOptions) -> list[str]:
    stages: list[str] = []
    if not options.skip_zotero_sync:
        stages.append("sync_zotero")
    if not options.skip_paper_index:
        stages.append("index_papers")
    if not options.skip_wiki_ingest:
        stages.append("ingest_wiki")
    if not options.skip_wiki_index:
        stages.append("index_wiki")
    return stages


def _acquire_lock(project_root: Path) -> Path:
    lock = _lock_path(project_root)
    lock.parent.mkdir(parents=True, exist_ok=True)
    if lock.exists():
        raise RuntimeError(f"sync lock already exists: {lock}")
    payload = {"pid": os.getpid(), "started_at": _utc_now_iso()}
    _write_json(lock, payload)
    return lock


def _release_lock(lock_path: Path) -> None:
    if lock_path.exists():
        lock_path.unlink()


def run_sync_pipeline(options: SyncOptions) -> SyncResult:
    planned = _planned_stages(options)
    state_path = _state_path(options.project_root)

    if options.dry_run:
        try:
            report = inspect_index_health(options.db_path)
            health_summary = f"{report.severity}: {report.summary}"
        except Exception as exc:
            health_summary = f"error: {exc}"
        return SyncResult(
            status="dry_run",
            summary="Dry run only; no commands executed.",
            planned_stages=planned,
            completed_stages=[],
            state_path=str(state_path),
            planned_commands=[_build_stage_command(options, stage) for stage in planned],
            health_summary=health_summary,
        )

    report = inspect_index_health(options.db_path)
    if report.severity in {"warning", "corrupted"}:
        if options.rebuild in {"papers", "all"} and options.backup_corrupted_db:
            _backup_vectordb(options.db_path)
        else:
            raise VectordbHealthError(f"{report.summary}\n{report.recommended_action}")

    lock = _acquire_lock(options.project_root)
    completed_stages: list[str] = []
    _write_state(
        state_path,
        status="running",
        stage=planned[0] if planned else "completed",
        planned_stages=planned,
        completed_stages=completed_stages,
    )

    try:
        for stage in planned:
            _write_state(
                state_path,
                status="running",
                stage=stage,
                planned_stages=planned,
                completed_stages=completed_stages,
            )
            command = _build_stage_command(options, stage)
            _run_stage_command(options.project_root, command)
            completed_stages.append(stage)

        _write_state(
            state_path,
            status="ok",
            stage="completed",
            planned_stages=planned,
            completed_stages=completed_stages,
            finished_at=_utc_now_iso(),
        )
        return SyncResult(
            status="ok",
            summary="Sync completed successfully.",
            planned_stages=planned,
            completed_stages=completed_stages,
            state_path=str(state_path),
        )
    except Exception as exc:
        _write_state(
            state_path,
            status="failed",
            stage=completed_stages[-1] if completed_stages else (planned[0] if planned else "completed"),
            planned_stages=planned,
            completed_stages=completed_stages,
            error=str(exc),
            finished_at=_utc_now_iso(),
        )
        raise
    finally:
        _release_lock(lock)
