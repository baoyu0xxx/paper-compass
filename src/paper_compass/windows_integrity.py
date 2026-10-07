"""Windows runtime-directory integrity helpers."""

from __future__ import annotations

import os
import subprocess
from pathlib import Path

_LOW_INTEGRITY_SID = "S-1-16-4096"


def default_runtime_root() -> Path:
    return Path.home() / ".paper-compass"


def is_low_integrity_process() -> bool:
    """Return whether the current Windows token has Low mandatory integrity."""
    if os.name != "nt":
        return False
    try:
        result = subprocess.run(
            ["whoami", "/groups"],
            check=False,
            capture_output=True,
            text=False,
        )
    except OSError:
        return False
    output = result.stdout.decode("utf-8", errors="replace")
    return _LOW_INTEGRITY_SID in output


def _is_default_root(root: Path) -> bool:
    try:
        return root.expanduser().resolve(strict=False) == default_runtime_root().resolve(strict=False)
    except OSError:
        return False


def set_low_integrity_runtime_root(root: str | Path) -> None:
    """Allow Low Integrity descendants to write the dedicated runtime root.

    This intentionally accepts only ``%USERPROFILE%\\.paper-compass``. The
    caller must handle ``RuntimeError`` because a Low Integrity process may be
    unable to change the label on a directory created by a higher-integrity
    process.
    """
    if os.name != "nt" or not is_low_integrity_process():
        return
    target = Path(root).expanduser().resolve(strict=False)
    if not _is_default_root(target):
        raise RuntimeError(
            "refusing to set Low Integrity on a non-default runtime root: "
            f"{target}"
        )
    target.mkdir(parents=True, exist_ok=True)
    result = subprocess.run(
        ["icacls", str(target), "/setintegritylevel", "(OI)(CI)L"],
        check=False,
        capture_output=True,
        text=False,
    )
    if result.returncode:
        details = result.stderr.decode("utf-8", errors="replace").strip()
        if not details:
            details = result.stdout.decode("utf-8", errors="replace").strip()
        raise RuntimeError(
            "the current Low Integrity process cannot grant Low Integrity write "
            f"access to {target}. Run this once from a Medium Integrity shell:\n"
            f'icacls "{target}" /setintegritylevel (OI)(CI)L\n'
            f"{details}".strip()
        )


def prepare_runtime_temp(db_path: str | Path) -> None:
    """Route SQLite temp files into the writable runtime root when needed."""
    if os.name != "nt" or not is_low_integrity_process():
        return
    root = default_runtime_root().resolve(strict=False)
    database = Path(db_path).expanduser().resolve(strict=False)
    try:
        database.relative_to(root)
    except ValueError:
        return
    temp_root = root / "tmp"
    temp_root.mkdir(parents=True, exist_ok=True)
    for name in ("TEMP", "TMP", "SQLITE_TMPDIR"):
        os.environ[name] = str(temp_root)


def ensure_runtime_root_integrity(root: str | Path) -> None:
    """Best-effort initialization hook for the default runtime root."""
    set_low_integrity_runtime_root(root)
