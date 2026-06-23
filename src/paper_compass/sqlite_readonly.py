from __future__ import annotations

import sqlite3
from pathlib import Path
from urllib.parse import quote


def sqlite_readonly_uri(path: str | Path, *, immutable: bool = False) -> str:
    resolved = Path(path).expanduser().resolve()
    normalized = resolved.as_posix()
    uri = "file:" + quote(normalized, safe="/:@") + "?mode=ro"
    if immutable:
        uri += "&immutable=1"
    return uri


def connect_readonly(
    path: str | Path,
    *,
    immutable: bool = False,
    timeout: float = 30.0,
) -> sqlite3.Connection:
    conn = sqlite3.connect(
        sqlite_readonly_uri(path, immutable=immutable),
        uri=True,
        check_same_thread=True,
        timeout=timeout,
    )
    conn.isolation_level = None
    conn.execute("PRAGMA query_only=ON")
    conn.execute(f"PRAGMA busy_timeout={int(timeout * 1000)}")
    return conn
