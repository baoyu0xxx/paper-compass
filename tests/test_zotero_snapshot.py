from __future__ import annotations

import hashlib
import sqlite3
from pathlib import Path

import pytest

from paper_compass.zotero_paths import ZoteroSourceResolution, ZoteroPathAttempt


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
