from __future__ import annotations

import importlib.util
from pathlib import Path
from types import SimpleNamespace


SCRIPT_PATH = Path(__file__).resolve().parents[1] / "scripts" / "bootstrap_runtime.py"


def _load_script_module():
    spec = importlib.util.spec_from_file_location("bootstrap_runtime", SCRIPT_PATH)
    module = importlib.util.module_from_spec(spec)
    assert spec is not None and spec.loader is not None
    spec.loader.exec_module(module)
    return module


def test_bootstrap_runtime_invokes_ensure_and_prints_managed_python(monkeypatch, capsys, tmp_path):
    module = _load_script_module()

    managed_python = tmp_path / ".venv" / "Scripts" / "python.exe"
    state = SimpleNamespace(managed_python=managed_python, status="active")

    captured = {}

    def fake_ensure(*, project_root, bootstrap_python=None, with_dev=True):
        captured["project_root"] = project_root
        captured["bootstrap_python"] = bootstrap_python
        captured["with_dev"] = with_dev
        return state

    monkeypatch.setattr(module, "ensure_managed_runtime", fake_ensure)
    monkeypatch.setattr(
        "sys.argv",
        ["bootstrap_runtime.py", "--python", str(tmp_path / "bootstrap.exe"), "--without-dev"],
    )

    rc = module.main()

    assert rc == 0
    assert captured["bootstrap_python"] == tmp_path / "bootstrap.exe"
    assert captured["with_dev"] is False
    out = capsys.readouterr().out
    assert str(managed_python) in out
    assert "paper-compass init" in out
