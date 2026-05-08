"""Environment loading helpers for project scripts and library code."""

from __future__ import annotations

import os
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_ENV_PATH = PROJECT_ROOT / ".env"


def load_project_env(env_path: str | Path = DEFAULT_ENV_PATH) -> bool:
    """Load .env values into os.environ, always overwriting stale values.

    Returns True when the env file exists and was processed, else False.
    """
    path = Path(env_path)
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
