"""Smoke tests for package-resident console entry modules."""

from __future__ import annotations

import importlib
import tomllib
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
PYPROJECT = REPO_ROOT / "pyproject.toml"


def test_healthcheck_entry_module_imports():
    module = importlib.import_module("paper_compass.healthcheck")
    assert callable(module.main)


def test_mcp_console_script_points_to_shared_entrypoint():
    data = tomllib.loads(PYPROJECT.read_text(encoding="utf-8"))
    scripts = data["project"]["scripts"]

    assert scripts["paper-compass-mcp"] == "paper_compass.mcp_entrypoint:main"


def test_mcp_entry_module_imports():
    module = importlib.import_module("paper_compass.mcp_entrypoint")
    assert callable(module.main)


def test_legacy_mcp_cli_module_remains_importable_for_stale_wrappers():
    module = importlib.import_module("paper_compass.mcp_cli")
    assert callable(module.main)
