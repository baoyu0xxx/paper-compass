"""Packaging and installed-usage metadata checks."""

from __future__ import annotations

import tomllib
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]


def _load_pyproject() -> dict:
    return tomllib.loads((PROJECT_ROOT / "pyproject.toml").read_text(encoding="utf-8"))


def test_project_metadata_includes_release_fields():
    project = _load_pyproject()["project"]

    assert project["readme"] == "README.md"
    assert project["authors"]
    assert project["classifiers"]
    assert project["urls"]["Homepage"].startswith("https://")
    assert project["urls"]["Repository"].startswith("https://")


def test_console_scripts_point_to_package_modules():
    scripts = _load_pyproject()["project"]["scripts"]

    assert scripts["paper-compass"] == "paper_compass.cli:main"
    assert scripts["paper-compass-healthcheck"].startswith("paper_compass.")
    assert scripts["paper-compass-mcp"].startswith("paper_compass.")
    assert not scripts["paper-compass-healthcheck"].startswith("scripts.")
    assert not scripts["paper-compass-mcp"].startswith("scripts.")
