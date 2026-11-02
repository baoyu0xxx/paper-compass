import sqlite3
from pathlib import Path

import pytest

from paper_compass import sqlite_readonly, watch_service


def _make_library(tmp_path):
    """Create a minimal Zotero-shaped library plus its storage directory."""
    db = tmp_path / "zotero.sqlite"
    connection = sqlite3.connect(db)
    connection.execute("PRAGMA journal_mode=DELETE")
    connection.execute("CREATE TABLE items (itemID INTEGER PRIMARY KEY)")
    connection.commit()
    connection.close()
    storage = tmp_path / "storage"
    storage.mkdir()
    return db, storage


def _track_connections(monkeypatch):
    created = []
    real_connect = sqlite_readonly.connect_readonly

    def tracking(*args, **kwargs):
        connection = real_connect(*args, **kwargs)
        created.append(connection)
        return connection

    monkeypatch.setattr(sqlite_readonly, "connect_readonly", tracking)
    return created


def test_confirmation_validates_existing_source_without_creating_it(tmp_path):
    with pytest.raises(ValueError):
        watch_service.confirm_source(tmp_path / "missing.sqlite", tmp_path / "missing-storage")
    assert not (tmp_path / "missing-storage").exists()


def test_confirm_source_rejects_a_database_that_is_not_a_zotero_library(tmp_path):
    db = tmp_path / "zotero.sqlite"
    sqlite3.connect(db).close()
    storage = tmp_path / "storage"
    storage.mkdir()
    with pytest.raises(ValueError, match="items table missing"):
        watch_service.confirm_source(db, storage)


def test_confirm_source_closes_every_connection(tmp_path, monkeypatch):
    db, storage = _make_library(tmp_path)
    created = _track_connections(monkeypatch)

    for _ in range(5):
        watch_service.confirm_source(db, storage)

    assert len(created) == 5
    for connection in created:
        with pytest.raises(sqlite3.ProgrammingError):
            connection.execute("SELECT 1")


def test_confirm_source_accepts_a_library_zotero_has_locked(tmp_path):
    db, storage = _make_library(tmp_path)
    holder = sqlite3.connect(db, timeout=0)
    try:
        holder.execute("BEGIN EXCLUSIVE")
        assert watch_service.confirm_source(db, storage, timeout=0.2) == (
            str(db.resolve()),
            str(storage.resolve()),
        )
    finally:
        holder.close()


def test_confirm_source_paths_never_opens_the_database(tmp_path, monkeypatch):
    db, storage = _make_library(tmp_path)
    monkeypatch.setattr(
        sqlite_readonly,
        "connect_readonly",
        lambda *args, **kwargs: pytest.fail("the managed watcher must not open the live database"),
    )

    assert watch_service.confirm_source_paths(db, storage) == (str(db.resolve()), str(storage.resolve()))
    with pytest.raises(ValueError):
        watch_service.confirm_source_paths(db, tmp_path / "missing-storage")


def test_watch_config_keeps_opt_out_separate_from_success_state(tmp_path):
    config = watch_service.save_choice(tmp_path, enabled=False, db_path="db", storage_path="storage")
    assert config["enabled"] is False
    assert watch_service.load_config(tmp_path)["decision"] == "declined"
    assert not (tmp_path / "state" / "source_config.json").exists()


def test_single_instance_lock_releases_on_exit(tmp_path):
    with watch_service.instance_lock(tmp_path):
        with pytest.raises(watch_service.WatchAlreadyRunning):
            with watch_service.instance_lock(tmp_path):
                pass
    with watch_service.instance_lock(tmp_path):
        pass


def test_status_does_not_register_or_write(tmp_path, monkeypatch):
    monkeypatch.setattr(watch_service.watch_autostart, "inspect", lambda c: {"registered": False, "running": False})
    status = watch_service.status(tmp_path)
    assert status["enabled"] is False
    assert status["marked"] is False
    assert not (tmp_path / "state").exists()


def test_status_surfaces_the_download_mark(tmp_path, monkeypatch):
    watch_service.save_choice(tmp_path, enabled=False, db_path="db", storage_path="storage")
    monkeypatch.setattr(watch_service.watch_autostart, "inspect", lambda c: {"registered": False, "running": False, "marked": True})
    assert watch_service.status(tmp_path)["marked"] is True


def test_warning_names_the_files_that_keep_the_download_mark(capsys):
    watch_service._warn_remaining_marks([Path("C:/venv/Scripts/pythonw.exe")])
    error = capsys.readouterr().err
    assert "pythonw.exe" in error
    assert "Unblock-File" in error


def test_warning_is_silent_when_no_mark_remains(capsys):
    watch_service._warn_remaining_marks([])
    assert capsys.readouterr().err == ""
