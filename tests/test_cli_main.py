"""Tests for the top-level paper-compass CLI entrypoint."""

from __future__ import annotations

import pytest

from paper_compass import __version__ as cli_version
from paper_compass.cli import main


def test_main_prints_version_and_exits(capsys, monkeypatch):
    monkeypatch.setattr("sys.argv", ["paper-compass", "--version"])

    with pytest.raises(SystemExit) as exc_info:
        main()

    assert exc_info.value.code == 0
    captured = capsys.readouterr()
    assert captured.out.strip() == cli_version
    assert captured.err == ""
