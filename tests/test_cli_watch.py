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


def test_managed_sync_child_is_spawned_without_a_console(monkeypatch, tmp_path):
    from unittest.mock import MagicMock

    from paper_compass import watch_service

    config_path = tmp_path / "state" / "watch_config.json"
    config_path.parent.mkdir(parents=True, exist_ok=True)
    config_path.write_text(json.dumps({
        "version": 1, "enabled": True, "runtime_root": str(tmp_path),
        "db_path": str(tmp_path / "zotero.sqlite"), "storage_path": str(tmp_path / "storage"),
        "python": str(tmp_path / "python.exe"), "project_root": str(tmp_path),
        "env_path": str(tmp_path / ".env"), "debounce_seconds": 0.25, "reconcile_seconds": 600.0,
    }), encoding="utf-8")
    monkeypatch.setattr(watch, "load_project_env", lambda *_: None)
    monkeypatch.setattr(watch, "child_creation_flags", lambda: 0x08000000)
    monkeypatch.setattr(watch.watch_service, "confirm_source", lambda *_, **__: None)
    def run_watch(root, db, callback, **kwargs):
        callback({"__startup__"})
        watch_service.stop_path(tmp_path).touch()
    monkeypatch.setattr(watch, "run_watch", run_watch)
    child = MagicMock()
    child.__enter__.return_value = child
    child.wait.return_value = 0
    popen = MagicMock(return_value=child)
    monkeypatch.setattr(watch.subprocess, "Popen", popen)
    assert watch._managed(str(config_path)) == 0
    assert popen.call_args.kwargs["creationflags"] == 0x08000000
    assert popen.call_args.kwargs["stdin"] is subprocess.DEVNULL


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
