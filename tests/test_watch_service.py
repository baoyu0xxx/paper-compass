from pathlib import Path

import pytest

from paper_compass import watch_service


def test_confirmation_validates_existing_source_without_creating_it(tmp_path):
    with pytest.raises(ValueError):
        watch_service.confirm_source(tmp_path / "missing.sqlite", tmp_path / "missing-storage")
    assert not (tmp_path / "missing-storage").exists()


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
    assert watch_service.status(tmp_path)["enabled"] is False
    assert not (tmp_path / "state").exists()
