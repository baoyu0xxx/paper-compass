from __future__ import annotations

import sqlite3
from pathlib import Path
from unittest import mock


def test_sqlite_readonly_uri_can_enable_immutable(tmp_path):
    from paper_compass.sqlite_readonly import sqlite_readonly_uri

    uri = sqlite_readonly_uri(tmp_path / "zotero.sqlite", immutable=True)

    assert "mode=ro" in uri
    assert "immutable=1" in uri


def test_connect_readonly_passes_timeout_and_busy_timeout(monkeypatch, tmp_path):
    from paper_compass.sqlite_readonly import connect_readonly

    calls: dict[str, object] = {}

    class FakeConnection:
        def __init__(self):
            self.isolation_level = ""
            self.executed: list[str] = []

        def execute(self, sql: str):
            self.executed.append(sql)
            return None

    fake_conn = FakeConnection()

    def fake_connect(path_arg, *, uri: bool, check_same_thread: bool, timeout: float):
        calls["uri"] = uri
        calls["check_same_thread"] = check_same_thread
        calls["timeout"] = timeout
        calls["path"] = str(path_arg)
        return fake_conn

    monkeypatch.setattr(sqlite3, "connect", fake_connect)

    conn = connect_readonly(tmp_path / "zotero.sqlite", immutable=True, timeout=12.5)

    assert conn is fake_conn
    assert calls["timeout"] == 12.5
    assert calls["check_same_thread"] is True
    assert "immutable=1" in str(calls["path"])
    assert fake_conn.executed == ["PRAGMA query_only=ON", "PRAGMA busy_timeout=12500"]
    assert fake_conn.isolation_level is None
