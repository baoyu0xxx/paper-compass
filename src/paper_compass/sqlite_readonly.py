from __future__ import annotations

import sqlite3
from contextlib import contextmanager
from pathlib import Path
from typing import Iterator
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
    conn.execute("PRAGMA temp_store=MEMORY")
    conn.execute(f"PRAGMA busy_timeout={int(timeout * 1000)}")
    return conn


@contextmanager
def read_only(
    path: str | Path,
    *,
    immutable: bool = False,
    timeout: float = 30.0,
) -> Iterator[sqlite3.Connection]:
    """Open a read-only connection and always close it.

    ``with sqlite3.connect(...)`` looks like it closes the connection but only
    commits or rolls back, which leaks the file handles. A leaked read-only
    handle on a live Zotero database keeps Zotero from starting, so every
    read-only open must go through this context manager.
    """
    connection = connect_readonly(path, immutable=immutable, timeout=timeout)
    try:
        yield connection
    finally:
        connection.close()
