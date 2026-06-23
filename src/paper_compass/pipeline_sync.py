from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Sequence

from paper_compass.index_health import inspect_index_health
from paper_compass.local_state import save_last_successful_zotero_source, source_config_path


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
    lock_timeout_minutes: int = 360
    force_unlock: bool = False


@dataclass
class SyncResult:
    status: str
    summary: str
    planned_stages: list[str]
    completed_stages: list[str]
    state_path: str
    planned_commands: list[list[str]] | None = None
    health_summary: str = ""


@dataclass(frozen=True)
class LockStatus:
    path: Path
    exists: bool
    stale: bool
    reason: str
    pid: int | None = None
    started_at: str | None = None
    payload: dict[str, Any] | None = None


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


def _read_json(path: Path) -> dict[str, Any]:
    if not path.exists() or not path.is_file():
        return {}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}
    return payload if isinstance(payload, dict) else {}


def _write_state(
    state_path: Path,
    *,
    run_id: str,
    started_at: str,
    status: str,
    stage: str,
    planned_stages: list[str],
    completed_stages: list[str],
    error: str = "",
    finished_at: str | None = None,
    updated_at: str | None = None,
) -> None:
    _write_json(
        state_path,
        {
            "run_id": run_id,
            "started_at": started_at,
            "updated_at": updated_at or _utc_now_iso(),
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
        if options.dry_run:
            cmd.append("--dry-run")
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
        if options.dry_run:
            cmd.append("--dry-run")
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


def _process_is_active(pid: int | None, process_start_time: float | None = None) -> bool:
    return pid == os.getpid()


def inspect_sync_lock(project_root: Path, *, timeout_minutes: int = 360) -> LockStatus:
    lock = _lock_path(project_root)
    if not lock.exists():
        return LockStatus(path=lock, exists=False, stale=False, reason="")

    payload = _read_json(lock)
    if not payload:
        return LockStatus(path=lock, exists=True, stale=True, reason="invalid lock payload", payload={})

    pid_raw = payload.get("pid")
    pid = int(pid_raw) if isinstance(pid_raw, int) or (isinstance(pid_raw, str) and str(pid_raw).isdigit()) else None
    process_start_time = payload.get("process_start_time")
    started_at = str(payload.get("started_at", "") or "") or None

    if pid is None:
        return LockStatus(path=lock, exists=True, stale=True, reason="missing pid", payload=payload)

    if _process_is_active(pid, process_start_time):
        return LockStatus(path=lock, exists=True, stale=False, reason="pid active", pid=pid, started_at=started_at, payload=payload)

    return LockStatus(path=lock, exists=True, stale=True, reason="pid not running", pid=pid, started_at=started_at, payload=payload)


def _remove_lock(path: Path) -> None:
    if path.exists():
        path.unlink()


def _acquire_lock(project_root: Path, *, timeout_minutes: int = 360) -> Path:
    lock = _lock_path(project_root)
    lock.parent.mkdir(parents=True, exist_ok=True)
    status = inspect_sync_lock(project_root, timeout_minutes=timeout_minutes)
    if status.exists and not status.stale:
        raise RuntimeError(f"sync lock already exists and appears active: {status.path} ({status.reason})")
    if status.exists and status.stale:
        _remove_lock(status.path)
    payload = {
        "pid": os.getpid(),
        "started_at": _utc_now_iso(),
        "process_start_time": 0.0,
        "command": "paper-compass sync",
    }
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

    if options.force_unlock:
        status = inspect_sync_lock(options.project_root, timeout_minutes=options.lock_timeout_minutes)
        if status.exists:
            _remove_lock(status.path)
            return SyncResult(
                status="unlocked",
                summary=f"Removed {'stale' if status.stale else 'existing'} sync lock.",
                planned_stages=[],
                completed_stages=[],
                state_path=str(state_path),
            )
        return SyncResult(
            status="unlocked",
            summary="No sync lock present.",
            planned_stages=[],
            completed_stages=[],
            state_path=str(state_path),
        )

    report = inspect_index_health(options.db_path)
    if report.severity in {"warning", "corrupted"}:
        if options.rebuild in {"papers", "all"} and options.backup_corrupted_db:
            _backup_vectordb(options.db_path)
        else:
            raise VectordbHealthError(f"{report.summary}\n{report.recommended_action}")

    run_id = f"{datetime.now().strftime('%Y%m%d-%H%M%S')}-{os.getpid()}"
    lock = _acquire_lock(options.project_root, timeout_minutes=options.lock_timeout_minutes)
    completed_stages: list[str] = []
    started_at = _utc_now_iso()
    _write_state(
        state_path,
        run_id=run_id,
        started_at=started_at,
        status="running",
        stage=planned[0] if planned else "completed",
        planned_stages=planned,
        completed_stages=completed_stages,
    )

    try:
        for stage in planned:
            _write_state(
                state_path,
                run_id=run_id,
                started_at=started_at,
                status="running",
                stage=stage,
                planned_stages=planned,
                completed_stages=completed_stages,
            )
            command = _build_stage_command(options, stage)
            _run_stage_command(options.project_root, command)
            completed_stages.append(stage)

        finished_at = _utc_now_iso()
        _write_state(
            state_path,
            run_id=run_id,
            started_at=started_at,
            status="ok",
            stage="completed",
            planned_stages=planned,
            completed_stages=completed_stages,
            finished_at=finished_at,
            updated_at=_utc_now_iso(),
        )
        if options.db_source_path and options.storage_path:
            save_last_successful_zotero_source(
                source_config_path(options.project_root),
                db_path=options.db_source_path,
                storage_path=options.storage_path,
                source_kind="explicit",
                is_live_candidate=False,
                last_success_at=_utc_now_iso(),
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
            run_id=run_id,
            started_at=started_at,
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
