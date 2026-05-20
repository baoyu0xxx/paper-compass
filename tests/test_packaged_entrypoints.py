from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

import pytest


REPO_ROOT = Path(__file__).resolve().parents[1]
SRC_ROOT = REPO_ROOT / "src"


@pytest.mark.parametrize(
    ("module_name", "symbol_name"),
    [
        ("scripts.run_mcp_server", "main"),
        ("scripts.healthcheck", "main"),
    ],
)
def test_legacy_console_entrypoint_modules_are_importable_from_installed_src_layout(
    tmp_path: Path,
    module_name: str,
    symbol_name: str,
):
    env = os.environ.copy()
    env["PYTHONPATH"] = str(SRC_ROOT)

    code = (
        f"from {module_name} import {symbol_name}\n"
        f"print(callable({symbol_name}))\n"
    )

    result = subprocess.run(
        [sys.executable, "-c", code],
        cwd=tmp_path,
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 0, result.stderr
    assert result.stdout.strip() == "True"
