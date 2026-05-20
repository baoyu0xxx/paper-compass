"""Tests for shell wrapper scripts in scripts/."""

from __future__ import annotations

import os
import stat
import subprocess
from pathlib import Path

import pytest


REPO_ROOT = Path(__file__).resolve().parents[1]
SCRIPTS_DIR = REPO_ROOT / "scripts"


@pytest.fixture
def fake_python(tmp_path: Path) -> Path:
    script = tmp_path / "fake-python.sh"
    script.write_text(
        "#!/usr/bin/env bash\n"
        "printf '%s\n' \"$0\" \"$@\"\n",
        encoding="utf-8",
    )
    script.chmod(script.stat().st_mode | stat.S_IEXEC)
    return script


@pytest.fixture
def fake_mcp_cmd(tmp_path: Path) -> Path:
    script = tmp_path / "paper-compass-mcp"
    script.write_text(
        "#!/usr/bin/env bash\n"
        "printf '%s\n' \"$0\" \"$@\"\n",
        encoding="utf-8",
    )
    script.chmod(script.stat().st_mode | stat.S_IEXEC)
    return script


@pytest.fixture
def broken_mcp_cmd(tmp_path: Path) -> Path:
    script = tmp_path / "paper-compass-mcp"
    script.write_text(
        "#!/usr/bin/env bash\n"
        "echo 'broken mcp entrypoint' >&2\n"
        "exit 1\n",
        encoding="utf-8",
    )
    script.chmod(script.stat().st_mode | stat.S_IEXEC)
    return script


def _run_script(script_name: str, *args: str, env: dict[str, str] | None = None) -> subprocess.CompletedProcess[str]:
    merged_env = os.environ.copy()
    if env:
        merged_env.update(env)
    return subprocess.run(
        ["bash", str(SCRIPTS_DIR / script_name), *args],
        cwd=REPO_ROOT,
        env=merged_env,
        text=True,
        capture_output=True,
        check=False,
    )


@pytest.mark.parametrize(
    ("script_name", "extra_args", "expected_args"),
    [
        (
            "pc-index-full.sh",
            ["--manifest-path", "tmp/manifest.json"],
            [
                "scripts/build_index.py",
                "--library",
                "data/zotero-export/library.json",
                "--db-path",
                "data/vectordb",
                "--full-rebuild",
                "--manifest-path",
                "tmp/manifest.json",
            ],
        ),
        (
            "pc-index-incremental.sh",
            ["--manifest-path", "tmp/manifest.json"],
            [
                "scripts/build_index.py",
                "--library",
                "data/zotero-export/library.json",
                "--db-path",
                "data/vectordb",
                "--incremental",
                "--prune-deleted",
                "--manifest-path",
                "tmp/manifest.json",
            ],
        ),
        (
            "pc-wiki-build.sh",
            ["--limit", "2"],
            [
                "scripts/ingest_to_wiki.py",
                "--library",
                "data/zotero-export/library.json",
                "--wiki-root",
                "./wiki",
                "--skip-existing",
                "--workers",
                "10",
                "--limit",
                "2",
            ],
        ),
        (
            "pc-wiki-index.sh",
            ["--manifest-path", "tmp/wiki-manifest.json"],
            [
                "scripts/build_index.py",
                "--wiki",
                "--db-path",
                "data/vectordb",
                "--wiki-root",
                "./wiki",
                "--manifest-path",
                "tmp/wiki-manifest.json",
            ],
        ),
    ],
)
def test_wrapper_scripts_forward_expected_defaults_and_args(
    fake_python: Path,
    script_name: str,
    extra_args: list[str],
    expected_args: list[str],
):
    result = _run_script(
        script_name,
        *extra_args,
        env={
            "PAPER_COMPASS_ROOT": str(REPO_ROOT),
            "PAPER_COMPASS_PYTHON": str(fake_python),
        },
    )

    assert result.returncode == 0, result.stderr
    lines = result.stdout.strip().splitlines()
    assert lines[0] == str(fake_python)
    assert lines[1:] == expected_args


def test_run_mcp_prefers_package_command_when_available(fake_mcp_cmd: Path):
    result = _run_script(
        "run_mcp.sh",
        "--inspect",
        env={
            "PAPER_COMPASS_ROOT": str(REPO_ROOT),
            "PATH": f"{fake_mcp_cmd.parent}:{os.environ['PATH']}",
        },
    )

    assert result.returncode == 0, result.stderr
    lines = result.stdout.strip().splitlines()
    assert lines[0] == str(fake_mcp_cmd)
    assert lines[1:] == ["--mcp", "--inspect"]


def test_run_mcp_falls_back_to_python_script(fake_python: Path):
    result = _run_script(
        "run_mcp.sh",
        "--inspect",
        env={
            "PAPER_COMPASS_ROOT": str(REPO_ROOT),
            "PAPER_COMPASS_PYTHON": str(fake_python),
            "PATH": "/usr/bin:/bin",
        },
    )

    assert result.returncode == 0, result.stderr
    lines = result.stdout.strip().splitlines()
    assert lines[0] == str(fake_python)
    assert lines[1:] == ["scripts/run_mcp_server.py", "--mcp", "--inspect"]


def test_run_mcp_falls_back_when_package_command_is_broken(
    fake_python: Path,
    broken_mcp_cmd: Path,
):
    result = _run_script(
        "run_mcp.sh",
        "--inspect",
        env={
            "PAPER_COMPASS_ROOT": str(REPO_ROOT),
            "PAPER_COMPASS_PYTHON": str(fake_python),
            "PATH": f"{broken_mcp_cmd.parent}:/usr/bin:/bin",
        },
    )

    assert result.returncode == 0, result.stderr
    lines = result.stdout.strip().splitlines()
    assert lines[0] == str(fake_python)
    assert lines[1:] == ["scripts/run_mcp_server.py", "--mcp", "--inspect"]


def test_wiki_ingest_bg_reports_log_path_and_creates_log_dir(fake_python: Path):
    result = _run_script(
        "pc-wiki-ingest-bg.sh",
        "--limit",
        "1",
        env={
            "PAPER_COMPASS_ROOT": str(REPO_ROOT),
            "PAPER_COMPASS_PYTHON": str(fake_python),
        },
    )

    assert result.returncode == 0, result.stderr
    assert "wiki background job started" in result.stdout.lower()
    assert "data/logs/wiki_gen.log" in result.stdout
    assert (REPO_ROOT / "data" / "logs").exists()
