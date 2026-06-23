from __future__ import annotations

import hashlib
import sqlite3
from pathlib import Path

import pytest

from paper_compass.zotero_paths import ZoteroPathAttempt, ZoteroSourceResolution


def _make_sqlite(path: Path) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(path)
    conn.execute("CREATE TABLE items (id INTEGER PRIMARY KEY, title TEXT)")
    conn.execute("INSERT INTO items (title) VALUES ('paper')")
    conn.commit()
    conn.close()
    return path


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def test_create_sqlite_snapshot_does_not_modify_source(tmp_path):
    from paper_compass.zotero_snapshot import create_sqlite_snapshot

    source = _make_sqlite(tmp_path / "live" / "zotero.sqlite")
    before_hash = _sha256(source)
    before_size = source.stat().st_size

    snapshot = create_sqlite_snapshot(source, tmp_path / "snapshots")

    assert snapshot.exists()
    assert snapshot != source
    assert _sha256(source) == before_hash
    assert source.stat().st_size == before_size


def test_prepare_zotero_database_for_live_source_uses_snapshot(tmp_path):
    from paper_compass.zotero_snapshot import prepare_zotero_database_for_read

    source_db = _make_sqlite(tmp_path / "live" / "zotero.sqlite")
    source = ZoteroSourceResolution(
        db_path=source_db,
        storage_path=tmp_path / "live" / "storage",
        source_kind="default",
        tried=[ZoteroPathAttempt(path=str(source_db), reason="ok")],
        is_live_candidate=True,
    )

    prepared = prepare_zotero_database_for_read(
        source,
        snapshot_policy="auto",
        snapshot_dir=tmp_path / "data" / "state" / "zotero-snapshots",
    )

    assert prepared.used_snapshot is True
    assert prepared.read_db_path != source_db
    assert prepared.snapshot_path is not None
    assert prepared.snapshot_path.exists()


def test_prepare_zotero_database_for_backup_source_uses_direct_read(tmp_path):
    from paper_compass.zotero_snapshot import prepare_zotero_database_for_read

    source_db = _make_sqlite(tmp_path / "backup" / "zotero.sqlite")
    source = ZoteroSourceResolution(
        db_path=source_db,
        storage_path=tmp_path / "backup" / "storage",
        source_kind="backup",
        tried=[ZoteroPathAttempt(path=str(source_db), reason="ok")],
        is_live_candidate=False,
    )

    prepared = prepare_zotero_database_for_read(
        source,
        snapshot_policy="auto",
        snapshot_dir=tmp_path / "data" / "state" / "zotero-snapshots",
    )

    assert prepared.used_snapshot is False
    assert prepared.read_db_path == source_db
    assert prepared.snapshot_path is None


def test_prepare_zotero_database_refuses_live_direct_read_without_override(tmp_path):
    from paper_compass.zotero_snapshot import prepare_zotero_database_for_read

    source_db = _make_sqlite(tmp_path / "live" / "zotero.sqlite")
    source = ZoteroSourceResolution(
        db_path=source_db,
        storage_path=tmp_path / "live" / "storage",
        source_kind="default",
        tried=[ZoteroPathAttempt(path=str(source_db), reason="ok")],
        is_live_candidate=True,
    )

    with pytest.raises(RuntimeError, match="allow-live-zotero-read"):
        prepare_zotero_database_for_read(
            source,
            snapshot_policy="never",
            snapshot_dir=tmp_path / "data" / "state" / "zotero-snapshots",
            allow_live_zotero_read=False,
        )


def test_prepare_zotero_database_reports_locked_snapshot_context(tmp_path, monkeypatch):
    from paper_compass import zotero_snapshot
    from paper_compass.zotero_snapshot import prepare_zotero_database_for_read

    source_db = _make_sqlite(tmp_path / "live" / "zotero.sqlite")
    journal = source_db.with_name(source_db.name + "-journal")
    journal.write_text("busy", encoding="utf-8")
    source = ZoteroSourceResolution(
        db_path=source_db,
        storage_path=tmp_path / "live" / "storage",
        source_kind="default",
        tried=[ZoteroPathAttempt(path=str(source_db), reason="ok")],
        is_live_candidate=True,
    )

    def fake_snapshot(src: Path, snapshot_dir: Path, *, timeout: float = 30.0) -> Path:
        raise sqlite3.OperationalError("database is locked")

    monkeypatch.setattr(zotero_snapshot, "create_sqlite_snapshot", fake_snapshot)

    with pytest.raises(RuntimeError, match="database is locked") as exc_info:
        prepare_zotero_database_for_read(
            source,
            snapshot_policy="always",
            snapshot_dir=tmp_path / "data" / "state" / "zotero-snapshots",
            sqlite_timeout=15.0,
        )

    message = str(exc_info.value)
    assert "zotero.sqlite-journal" in message
    assert "snapshot-db never" in message
    assert "sqlite-timeout 15.0" in message


def test_cleanup_sqlite_snapshots_keeps_newest_n(tmp_path):
    from paper_compass.zotero_snapshot import cleanup_sqlite_snapshots

    snapshot_dir = tmp_path / "snapshots"
    snapshot_dir.mkdir()
    files = []
    for idx in range(4):
        path = snapshot_dir / f"zotero.20260521-180{idx}00.sqlite"
        path.write_text(str(idx), encoding="utf-8")
        import os

        os.utime(path, (idx, idx))
        files.append(path)

    result = cleanup_sqlite_snapshots(snapshot_dir, keep=2, max_age_days=0, dry_run=False)

    assert result.scanned_count == 4
    assert result.deleted_count == 2
    assert files[0].exists() is False
    assert files[1].exists() is False
    assert files[2].exists() is True
    assert files[3].exists() is True


def test_cleanup_sqlite_snapshots_dry_run_does_not_delete(tmp_path):
    from paper_compass.zotero_snapshot import cleanup_sqlite_snapshots

    snapshot_dir = tmp_path / "snapshots"
    snapshot_dir.mkdir()
    old = snapshot_dir / "zotero.20260521-180000.sqlite"
    old.write_text("old", encoding="utf-8")

    result = cleanup_sqlite_snapshots(snapshot_dir, keep=0, max_age_days=0, dry_run=True)

    assert result.scanned_count == 1
    assert result.deleted_count == 1
    assert old.exists() is True
