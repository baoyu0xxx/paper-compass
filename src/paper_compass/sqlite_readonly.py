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


def connect_readonly(path: str | Path, *, immutable: bool = False) -> sqlite3.Connection:
    conn = sqlite3.connect(
        sqlite_readonly_uri(path, immutable=immutable),
        uri=True,
        check_same_thread=True,
    )
    conn.isolation_level = None
    conn.execute("PRAGMA query_only=ON")
    return conn
