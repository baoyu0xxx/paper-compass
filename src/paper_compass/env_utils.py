"""Environment loading helpers for project scripts and library code."""

from __future__ import annotations

import os
from pathlib import Path

from paper_compass.resources import is_source_checkout, project_root


PROJECT_ROOT = project_root()
DEFAULT_ENV_PATH = (
    PROJECT_ROOT / ".env"
    if is_source_checkout(PROJECT_ROOT)
    else Path(os.environ.get("PAPER_COMPASS_ROOT") or Path.home() / ".paper-compass").expanduser() / ".env"
)


def load_project_env(env_path: str | Path | None = None) -> bool:
    """Load .env values into os.environ, always overwriting stale values.

    Returns True when the env file exists and was processed, else False.
    """
    if env_path is None:
        env_path = os.environ.get("PAPER_COMPASS_ENV_PATH") or DEFAULT_ENV_PATH
    path = Path(env_path).expanduser()
    if not path.exists() or not path.is_file():
        return False

    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except OSError:
        return False

    for line in lines:
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            key, _, val = line.partition("=")
            key = key.strip()
            os.environ[key] = val.strip()
    return True
