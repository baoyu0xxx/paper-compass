"""Runtime Zotero SQLite snapshot helpers.

These snapshots are short-lived read copies created for safe reads from live
Zotero profiles. They are not a replacement for Zotero's official zotero.sqlite
and should not be treated as a long-lived source such as zotero_readonly.sqlite.
"""

from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
import time

from paper_compass.zotero_paths import ZoteroSourceResolution


@dataclass(frozen=True)
class PreparedZoteroDatabase:
    read_db_path: Path
    original_db_path: Path
    used_snapshot: bool
    snapshot_path: Path | None
    reason: str


def create_sqlite_snapshot(src: Path, snapshot_dir: Path) -> Path:
    snapshot_dir.mkdir(parents=True, exist_ok=True)
    ts = datetime.now().strftime("%Y%m%d-%H%M%S")
    dst = snapshot_dir / f"zotero.{ts}.sqlite"
    with sqlite3.connect(f"file:{src}?mode=ro", uri=True) as source:
        with sqlite3.connect(dst) as target:
            source.backup(target)
    return dst


def prepare_zotero_database_for_read(
    source: ZoteroSourceResolution,
    *,
    snapshot_policy: str = "auto",
    snapshot_dir: Path,
    allow_live_zotero_read: bool = False,
) -> PreparedZoteroDatabase:
    if snapshot_policy not in {"auto", "always", "never"}:
        raise ValueError("snapshot_policy must be auto, always, or never")

    should_snapshot = snapshot_policy == "always" or (
        snapshot_policy == "auto" and source.is_live_candidate
    )
    if should_snapshot:
        snapshot = create_sqlite_snapshot(source.db_path, snapshot_dir)
        return PreparedZoteroDatabase(
            read_db_path=snapshot,
            original_db_path=source.db_path,
            used_snapshot=True,
            snapshot_path=snapshot,
            reason="snapshot",
        )

    if source.is_live_candidate and snapshot_policy == "never" and not allow_live_zotero_read:
        raise RuntimeError(
            "Refusing to read live Zotero database directly; pass --allow-live-zotero-read to override"
        )

    return PreparedZoteroDatabase(
        read_db_path=source.db_path,
        original_db_path=source.db_path,
        used_snapshot=False,
        snapshot_path=None,
        reason="direct",
    )


@dataclass(frozen=True)
class SnapshotCleanupResult:
    scanned_count: int
    deleted_count: int
    deleted_paths: list[Path]
    dry_run: bool


def cleanup_sqlite_snapshots(
    snapshot_dir: Path,
    *,
    keep: int = 5,
    max_age_days: int = 0,
    dry_run: bool = False,
) -> SnapshotCleanupResult:
    if keep < 0:
        raise ValueError("keep must be >= 0")
    if max_age_days < 0:
        raise ValueError("max_age_days must be >= 0")
    if not snapshot_dir.exists() or not snapshot_dir.is_dir():
        return SnapshotCleanupResult(0, 0, [], dry_run)

    candidates = sorted(
        snapshot_dir.glob("zotero.*.sqlite"),
        key=lambda path: path.stat().st_mtime,
        reverse=True,
    )

    to_delete: list[Path] = []
    if keep == 0:
        to_delete.extend(candidates)
    elif len(candidates) > keep:
        to_delete.extend(candidates[keep:])

    if max_age_days:
        cutoff = time.time() - max_age_days * 86400
        for path in candidates:
            if path.stat().st_mtime < cutoff and path not in to_delete:
                to_delete.append(path)

    if not dry_run:
        for path in to_delete:
            path.unlink(missing_ok=True)

    return SnapshotCleanupResult(
        scanned_count=len(candidates),
        deleted_count=len(to_delete),
        deleted_paths=to_delete,
        dry_run=dry_run,
    )
