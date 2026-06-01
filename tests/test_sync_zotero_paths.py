from pathlib import Path

import pytest

from paper_compass.zotero_paths import (
    DEFAULT_BACKUP_ROOTS,
    resolve_zotero_source,
    ZoteroSourceNotFoundError,
)


def _touch(path: Path, content: str = "") -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")
    return path


def _make_zotero_dir(root: Path, *, readonly: bool = False, writable: bool = True, storage: bool = True) -> Path:
    if readonly:
        _touch(root / "zotero_readonly.sqlite", "readonly")
    if writable:
        _touch(root / "zotero.sqlite", "writable")
    if storage:
        (root / "storage").mkdir(parents=True, exist_ok=True)
    return root


def test_default_backup_roots_empty_for_portable_distribution():
    assert DEFAULT_BACKUP_ROOTS == []


def test_explicit_db_path_wins_over_auto_candidates(tmp_path):
    explicit_root = _make_zotero_dir(tmp_path / "explicit", writable=True, storage=True)
    backup_root = _make_zotero_dir(tmp_path / "backup", readonly=True, storage=True)

    resolved = resolve_zotero_source(
        db_path=str(explicit_root / "zotero.sqlite"),
        backup_roots=[backup_root],
        default_roots=[],
    )

    assert resolved.db_path == explicit_root / "zotero.sqlite"
    assert resolved.storage_path == explicit_root / "storage"
    assert resolved.source_kind == "explicit"
    assert resolved.is_live_candidate is True


def test_env_path_used_when_no_explicit_db_path(tmp_path, monkeypatch):
    env_root = _make_zotero_dir(tmp_path / "env", writable=True, storage=True)
    monkeypatch.setenv("ZOTERO_SQLITE_PATH", str(env_root / "zotero.sqlite"))

    resolved = resolve_zotero_source(default_roots=[], backup_roots=[])

    assert resolved.db_path == env_root / "zotero.sqlite"
    assert resolved.storage_path == env_root / "storage"
    assert resolved.source_kind == "env"


def test_default_root_uses_official_sqlite_over_backup_root(tmp_path):
    default_root = _make_zotero_dir(tmp_path / "default", readonly=True, writable=True, storage=True)
    backup_root = _make_zotero_dir(tmp_path / "backup", readonly=True, writable=True, storage=True)

    resolved = resolve_zotero_source(
        default_roots=[default_root],
        backup_roots=[backup_root],
    )

    assert resolved.db_path == default_root / "zotero.sqlite"
    assert resolved.source_kind == "default"
    assert resolved.is_live_candidate is True


def test_backup_root_used_when_default_root_missing(tmp_path):
    default_root = tmp_path / "default-missing"
    backup_root = _make_zotero_dir(tmp_path / "backup", readonly=True, writable=True, storage=True)

    resolved = resolve_zotero_source(
        default_roots=[default_root],
        backup_roots=[backup_root],
    )

    assert resolved.db_path == backup_root / "zotero.sqlite"
    assert resolved.storage_path == backup_root / "storage"
    assert resolved.source_kind == "backup"
    assert resolved.is_live_candidate is False


def test_backup_root_env_used_when_present(tmp_path, monkeypatch):
    backup_root = _make_zotero_dir(tmp_path / "env-backup", readonly=True, writable=True, storage=True)
    monkeypatch.setenv("ZOTERO_BACKUP_ROOT", str(backup_root))

    resolved = resolve_zotero_source(default_roots=[])

    assert resolved.db_path == backup_root / "zotero.sqlite"
    assert resolved.storage_path == backup_root / "storage"
    assert resolved.source_kind == "backup"


def test_official_sqlite_preferred_over_legacy_readonly_sqlite(tmp_path):
    root = _make_zotero_dir(tmp_path / "zotero", readonly=True, writable=True, storage=True)

    resolved = resolve_zotero_source(default_roots=[root], backup_roots=[])

    assert resolved.db_path == root / "zotero.sqlite"


def test_legacy_readonly_sqlite_is_not_auto_discovered(tmp_path):
    root = _make_zotero_dir(tmp_path / "zotero", readonly=True, writable=False, storage=True)

    with pytest.raises(ZoteroSourceNotFoundError) as exc_info:
        resolve_zotero_source(default_roots=[root], backup_roots=[])

    assert any("zotero.sqlite" in attempt.path for attempt in exc_info.value.tried)
    assert not any("zotero_readonly.sqlite" in attempt.path for attempt in exc_info.value.tried)


def test_explicit_legacy_readonly_sqlite_still_supported(tmp_path):
    root = _make_zotero_dir(tmp_path / "zotero", readonly=True, writable=False, storage=True)

    resolved = resolve_zotero_source(
        db_path=str(root / "zotero_readonly.sqlite"),
        default_roots=[],
        backup_roots=[],
    )

    assert resolved.db_path == root / "zotero_readonly.sqlite"
    assert resolved.source_kind == "explicit"


def test_explicit_storage_path_overrides_default_storage(tmp_path):
    root = _make_zotero_dir(tmp_path / "zotero", readonly=True, storage=True)
    custom_storage = tmp_path / "custom-storage"
    custom_storage.mkdir(parents=True, exist_ok=True)

    resolved = resolve_zotero_source(
        db_path=str(root / "zotero_readonly.sqlite"),
        storage_path=str(custom_storage),
        default_roots=[],
        backup_roots=[],
    )

    assert resolved.db_path == root / "zotero_readonly.sqlite"
    assert resolved.storage_path == custom_storage
    assert resolved.source_kind == "explicit"


def test_storage_env_path_is_used_when_explicit_storage_missing(tmp_path, monkeypatch):
    root = _make_zotero_dir(tmp_path / "zotero", readonly=True, storage=False)
    custom_storage = tmp_path / "env-storage"
    custom_storage.mkdir(parents=True, exist_ok=True)
    monkeypatch.setenv("ZOTERO_STORAGE_PATH", str(custom_storage))

    resolved = resolve_zotero_source(
        db_path=str(root / "zotero_readonly.sqlite"),
        default_roots=[],
        backup_roots=[],
    )

    assert resolved.db_path == root / "zotero_readonly.sqlite"
    assert resolved.storage_path == custom_storage
    assert resolved.source_kind == "explicit"


def test_explicit_db_path_must_be_a_file(tmp_path):
    invalid_db = tmp_path / "not-a-file.sqlite"
    invalid_db.mkdir(parents=True, exist_ok=True)
    (tmp_path / "storage").mkdir(parents=True, exist_ok=True)

    with pytest.raises(ZoteroSourceNotFoundError) as exc_info:
        resolve_zotero_source(
            db_path=str(invalid_db),
            default_roots=[],
            backup_roots=[],
        )

    assert "not a file" in str(exc_info.value)


def test_invalid_env_db_path_falls_through_to_default_candidates(tmp_path, monkeypatch):
    invalid_env_db = tmp_path / "broken.sqlite"
    invalid_env_db.mkdir(parents=True, exist_ok=True)
    good_default_root = _make_zotero_dir(tmp_path / "default", readonly=True, writable=True, storage=True)
    monkeypatch.setenv("ZOTERO_SQLITE_PATH", str(invalid_env_db))

    resolved = resolve_zotero_source(default_roots=[good_default_root], backup_roots=[])

    assert resolved.db_path == good_default_root / "zotero.sqlite"
    assert any("not a file" in attempt.reason for attempt in resolved.tried)


def test_empty_default_sqlite_falls_through_to_backup_root(tmp_path):
    empty_default = tmp_path / "default"
    empty_default.mkdir(parents=True, exist_ok=True)
    (empty_default / "zotero.sqlite").write_bytes(b"")
    (empty_default / "storage").mkdir(parents=True, exist_ok=True)
    backup_root = _make_zotero_dir(tmp_path / "backup", readonly=True, writable=True, storage=True)

    resolved = resolve_zotero_source(
        default_roots=[empty_default],
        backup_roots=[backup_root],
    )

    assert resolved.db_path == backup_root / "zotero.sqlite"
    assert any("database file is empty" in attempt.reason for attempt in resolved.tried)


def test_incomplete_default_root_falls_back_to_backup_root(tmp_path):
    broken_default = _make_zotero_dir(tmp_path / "default", readonly=True, storage=False)
    backup_root = _make_zotero_dir(tmp_path / "backup", readonly=True, writable=True, storage=True)

    resolved = resolve_zotero_source(
        default_roots=[broken_default],
        backup_roots=[backup_root],
    )

    assert resolved.db_path == backup_root / "zotero.sqlite"
    assert any("storage directory not found" in attempt.reason for attempt in resolved.tried)


def test_error_includes_tried_candidates_and_manual_override_hint(tmp_path):
    missing_root = tmp_path / "missing"

    with pytest.raises(ZoteroSourceNotFoundError) as exc_info:
        resolve_zotero_source(default_roots=[missing_root], backup_roots=[])

    err = exc_info.value
    assert err.tried
    assert any("zotero.sqlite" in attempt.path for attempt in err.tried)
    assert not any("zotero_readonly.sqlite" in attempt.path for attempt in err.tried)
    message = str(err)
    assert "--db-path" in message
    assert "--storage-path" in message
