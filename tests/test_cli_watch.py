import argparse
import json
import subprocess
from types import SimpleNamespace

import pytest

from paper_compass.cli import watch


def make_args(*arguments):
    parser = argparse.ArgumentParser()
    watch.add_subcommand_parser(parser.add_subparsers())
    return parser.parse_args(["watch", *arguments])


@pytest.mark.parametrize("exit_code", [0, 1, 2])
def test_once_forwards_resolved_paths_and_exit_code(monkeypatch, tmp_path, exit_code):
    monkeypatch.setattr(watch, "load_project_env", lambda: None)
    monkeypatch.setattr(watch, "resolve_path_settings", lambda **_: SimpleNamespace(
        zotero_storage_path=str(tmp_path / "storage"),
        zotero_sqlite_path=str(tmp_path / "zotero.sqlite"),
    ))
    calls = []
    monkeypatch.setattr(watch.subprocess, "run", lambda command, **kwargs:
                        calls.append(command) or subprocess.CompletedProcess(command, exit_code))
    assert watch.execute_watch(make_args("--once")) == exit_code
    assert calls[0][-4:] == ["--db-source-path", str(tmp_path / "zotero.sqlite"),
                            "--storage-path", str(tmp_path / "storage")]


def test_module_entrypoint_propagates_failure(monkeypatch):
    import runpy
    import paper_compass.cli

    monkeypatch.setattr(paper_compass.cli, "main", lambda: 7)
    with pytest.raises(SystemExit) as error:
        runpy.run_module("paper_compass", run_name="__main__")
    assert error.value.code == 7


def test_sync_stage_uses_utf8(monkeypatch, tmp_path):
    from paper_compass import pipeline_sync

    calls = []
    monkeypatch.setattr(pipeline_sync, "child_creation_flags", lambda: 0x08000000)
    monkeypatch.setattr(pipeline_sync.subprocess, "run", lambda command, **kwargs:
                        calls.append(kwargs) or subprocess.CompletedProcess(command, 0))
    pipeline_sync._run_stage_command(tmp_path, ["python", "script.py"])
    assert calls[0]["env"]["PYTHONIOENCODING"] == "utf-8"
    assert calls[0]["env"]["PYTHONUTF8"] == "1"
    assert calls[0]["creationflags"] == 0x08000000


def test_repair_autostart_reuses_saved_source_and_env(monkeypatch, tmp_path, capsys):
    from paper_compass import watch_service

    saved = {
        "db_path": str(tmp_path / "zotero.sqlite"),
        "storage_path": str(tmp_path / "storage"),
        "env_path": str(tmp_path / ".env"),
    }
    calls = []
    monkeypatch.setattr(watch, "load_project_env", lambda: None)
    monkeypatch.setattr(watch, "resolve_path_settings", lambda **_: SimpleNamespace(compass_root=str(tmp_path)))
    monkeypatch.setattr(watch_service, "load_config", lambda root: saved)
    monkeypatch.setattr(watch_service, "enable", lambda root, **kwargs: calls.append((root, kwargs)))

    assert watch.execute_watch(make_args("--repair-autostart")) == 0
    assert calls == [(tmp_path, {
        "db_path": saved["db_path"],
        "storage_path": saved["storage_path"],
        "env_path": saved["env_path"],
    })]
    assert "refreshed" in capsys.readouterr().out


def _managed_config(tmp_path, **overrides):
    config = {
        "version": 1, "enabled": True, "runtime_root": str(tmp_path),
        "db_path": str(tmp_path / "zotero.sqlite"), "storage_path": str(tmp_path / "storage"),
        "python": str(tmp_path / "python.exe"), "project_root": str(tmp_path),
        "env_path": str(tmp_path / ".env"), "debounce_seconds": 0.25, "reconcile_seconds": 600.0,
    }
    config.update(overrides)
    config_path = tmp_path / "state" / "watch_config.json"
    config_path.parent.mkdir(parents=True, exist_ok=True)
    config_path.write_text(json.dumps(config), encoding="utf-8")
    return config_path


def _run_managed(monkeypatch, tmp_path, config_path, *, child=None, zotero=False):
    from unittest.mock import MagicMock

    from paper_compass import watch_service

    monkeypatch.setattr(watch, "load_project_env", lambda *_: None)
    monkeypatch.setattr(watch, "child_creation_flags", lambda: 0x08000000)
    monkeypatch.setattr(watch.watch_service, "confirm_source_paths", lambda *_, **__: None)
    monkeypatch.setattr(watch, "zotero_running", lambda: zotero)

    def run_watch(root, db, callback, **kwargs):
        callback({"__startup__"})
        watch_service.stop_path(tmp_path).touch()

    monkeypatch.setattr(watch, "run_watch", run_watch)
    if child is None:
        child = MagicMock()
        child.stdout = []
        child.wait.return_value = 0
    child.__enter__.return_value = child
    popen = MagicMock(return_value=child)
    monkeypatch.setattr(watch.subprocess, "Popen", popen)
    assert watch._managed(str(config_path)) == 0
    return popen


def _runtime_state(tmp_path):
    return json.loads((tmp_path / "state" / "watch_runtime.json").read_text(encoding="utf-8"))


def _watch_log(tmp_path):
    return (tmp_path / "logs" / "watch.log").read_text(encoding="utf-8")


def test_managed_sync_child_is_spawned_without_a_console(monkeypatch, tmp_path):
    popen = _run_managed(monkeypatch, tmp_path, _managed_config(tmp_path))
    assert popen.call_args.kwargs["creationflags"] == 0x08000000
    assert popen.call_args.kwargs["stdin"] is subprocess.DEVNULL


def test_managed_watcher_defers_sync_while_zotero_runs(monkeypatch, tmp_path):
    config_path = _managed_config(tmp_path)
    popen = _run_managed(monkeypatch, tmp_path, config_path, zotero=True)

    assert popen.call_count == 0
    assert _runtime_state(tmp_path)["last_error"] == ""
    assert "deferring this sync round" in _watch_log(tmp_path)


def test_managed_watcher_honours_the_gate_opt_out(monkeypatch, tmp_path):
    config_path = _managed_config(tmp_path, skip_while_zotero_running=False)
    popen = _run_managed(monkeypatch, tmp_path, config_path, zotero=True)

    assert popen.call_count > 0


def test_locked_database_sync_is_reported_as_a_deferral(monkeypatch, tmp_path):
    from unittest.mock import MagicMock

    child = MagicMock()
    child.stdout = ["  ERROR: Cannot read Zotero database: database is locked\n"]
    child.wait.return_value = 1
    config_path = _managed_config(tmp_path)
    _run_managed(monkeypatch, tmp_path, config_path, child=child)

    assert _runtime_state(tmp_path)["last_error"] == ""
    log = _watch_log(tmp_path)
    assert "Sync deferred: the Zotero database was locked" in log
    assert "Sync failed with exit code 1" not in log


def test_failed_sync_still_records_an_error(monkeypatch, tmp_path):
    from unittest.mock import MagicMock

    child = MagicMock()
    child.stdout = ["  some unrelated failure\n"]
    child.wait.return_value = 1
    config_path = _managed_config(tmp_path)
    _run_managed(monkeypatch, tmp_path, config_path, child=child)

    assert _runtime_state(tmp_path)["last_error"] == "Sync failed with exit code 1"
    assert "Sync failed with exit code 1" in _watch_log(tmp_path)


def test_continuous_watch_survives_failed_sync(monkeypatch, tmp_path):
    monkeypatch.setattr(watch, "load_project_env", lambda: None)
    monkeypatch.setattr(watch, "resolve_path_settings", lambda **_: SimpleNamespace(
        compass_root=str(tmp_path),
        zotero_storage_path=str(tmp_path / "storage"), zotero_sqlite_path=""))
    calls = []
    monkeypatch.setattr(watch.subprocess, "run", lambda command, **kwargs:
                        calls.append(command) or subprocess.CompletedProcess(command, 1))
    def run_watch(root, db, callback, **kwargs):
        callback({"A"})
        callback({"B"})
    monkeypatch.setattr(watch, "run_watch", run_watch)
    assert watch.execute_watch(make_args()) == 0
    assert len(calls) == 2
