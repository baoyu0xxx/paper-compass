"""Smoke tests for package-resident console entry modules."""

from __future__ import annotations

import importlib


def test_healthcheck_entry_module_imports():
    module = importlib.import_module("paper_compass.healthcheck")
    assert callable(module.main)


def test_mcp_entry_module_imports():
    module = importlib.import_module("paper_compass.mcp_cli")
    assert callable(module.main)
