"""Tests for the FTS5 full-text index repair path and the repair-fts CLI."""

from __future__ import annotations

import argparse
import io
import json
import sqlite3
import sys
from pathlib import Path
from unittest import mock

import pytest

FTS_DDL = (
    "CREATE VIRTUAL TABLE embedding_fulltext_search USING fts5(string_value, tokenize='trigram')"
)


def _make_db(path: Path, *, rows: int = 12, fts: bool = True) -> Path:
    path.mkdir(parents=True)
    sqlite_path = path / "chroma.sqlite3"
    with sqlite3.connect(sqlite_path) as connection:
        connection.execute("CREATE TABLE collections (id TEXT PRIMARY KEY, name TEXT NOT NULL)")
        connection.execute("INSERT INTO collections VALUES ('c1', 'papers_test')")
        if fts:
            connection.execute(FTS_DDL)
            connection.executemany(
                "INSERT INTO embedding_fulltext_search(rowid, string_value) VALUES (?, ?)",
                [(index, f"paper {index} about family firms and succession") for index in range(1, rows + 1)],
            )
        connection.commit()
    return sqlite_path


def _corrupt(sqlite_path: Path) -> None:
    with sqlite3.connect(sqlite_path) as connection:
        connection.execute("DELETE FROM embedding_fulltext_search_docsize")
        connection.commit()


def _quick_problems(sqlite_path: Path) -> list[str]:
    with sqlite3.connect(sqlite_path) as connection:
        return [str(row[0]) for row in connection.execute("PRAGMA quick_check") if row[0] != "ok"]


def _cli_args(argv: list[str]) -> argparse.Namespace:
    from paper_compass.cli.repair_fts import add_subcommand_parser

    parser = argparse.ArgumentParser(prog="paper-compass")
    subparsers = parser.add_subparsers(dest="command")
    add_subcommand_parser(subparsers)
    return subparsers.choices["repair-fts"].parse_args(argv)


class TestRepairFulltextIndex:
    def test_rebuilds_corrupted_index_without_touching_rows(self, tmp_path):
        from paper_compass.index_health import repair_fulltext_index

        sqlite_path = _make_db(tmp_path / "db")
        _corrupt(sqlite_path)
        assert "malformed inverted index" in _quick_problems(sqlite_path)[0]

        report = repair_fulltext_index(tmp_path / "db")

        assert report.ok is True
        assert report.repaired is True
        assert report.corrupted_tables == ["embedding_fulltext_search"]
        assert report.after == []
        assert _quick_problems(sqlite_path) == []
        with sqlite3.connect(sqlite_path) as connection:
            assert connection.execute("SELECT COUNT(*) FROM embedding_fulltext_search").fetchone()[0] == 12
            match = connection.execute(
                "SELECT rowid FROM embedding_fulltext_search "
                "WHERE embedding_fulltext_search MATCH 'family' LIMIT 1"
            ).fetchone()
            assert match is not None

    def test_is_a_noop_for_a_healthy_index(self, tmp_path):
        from paper_compass.index_health import repair_fulltext_index

        _make_db(tmp_path / "db")

        report = repair_fulltext_index(tmp_path / "db")

        assert report.ok is True
        assert report.repaired is False
        assert report.before == []
        assert "healthy" in report.message
        assert report.backup_path == ""

    def test_dry_run_does_not_repair(self, tmp_path):
        from paper_compass.index_health import repair_fulltext_index

        sqlite_path = _make_db(tmp_path / "db")
        _corrupt(sqlite_path)

        report = repair_fulltext_index(tmp_path / "db", dry_run=True)

        assert report.ok is False
        assert report.repaired is False
        assert "Dry run" in report.message
        assert _quick_problems(sqlite_path)

    def test_creates_a_backup_when_requested(self, tmp_path):
        from paper_compass.index_health import repair_fulltext_index

        sqlite_path = _make_db(tmp_path / "db")
        _corrupt(sqlite_path)
        original_size = sqlite_path.stat().st_size

        report = repair_fulltext_index(tmp_path / "db", backup=True)

        assert report.ok is True
        backup = Path(report.backup_path)
        assert backup.is_file()
        assert backup.stat().st_size == original_size
        assert _quick_problems(backup), "backup keeps the pre-repair state"
        assert report.repaired is True

    def test_missing_database_raises(self, tmp_path):
        from paper_compass.index_health import FulltextRepairError, repair_fulltext_index

        with pytest.raises(FulltextRepairError, match="Chroma database not found"):
            repair_fulltext_index(tmp_path / "missing")

    def test_database_without_fts_index_is_reported_as_healthy(self, tmp_path):
        from paper_compass.index_health import repair_fulltext_index

        _make_db(tmp_path / "db", fts=False)

        report = repair_fulltext_index(tmp_path / "db")

        assert report.ok is True
        assert report.repaired is False
        assert report.fulltext_tables == []
        assert "No FTS5 table" in report.message

    def test_non_fts_sqlite_problems_are_not_claimed_as_repaired(self, tmp_path, monkeypatch):
        from paper_compass import index_health

        _make_db(tmp_path / "db")
        monkeypatch.setattr(index_health, "_quick_check", lambda connection: ["database disk image is malformed"])

        with pytest.raises(index_health.FulltextRepairError, match="not FTS-related"):
            index_health.repair_fulltext_index(tmp_path / "db")

    def test_health_recommendation_points_to_repair_fts(self, tmp_path, monkeypatch):
        from paper_compass import index_health

        sqlite_path = _make_db(tmp_path / "db")
        _corrupt(sqlite_path)

        class DummyClient:
            def __init__(self, *args, **kwargs):
                pass

            def list_collections(self):
                return []

        monkeypatch.setattr(index_health, "_create_persistent_client", DummyClient)

        report = index_health.inspect_index_health(tmp_path / "db")

        assert report.severity == "corrupted"
        assert "repair-fts" in report.recommended_action


class TestRepairFtsCli:
    def test_subcommand_is_registered(self):
        from paper_compass.cli import main

        with mock.patch.object(sys, "argv", ["paper-compass", "--help"]):
            with mock.patch("sys.stdout", io.StringIO()) as output:
                with pytest.raises(SystemExit) as exc_info:
                    main()
        assert exc_info.value.code == 0
        assert "repair-fts" in output.getvalue()

    def test_help_lists_repair_options(self):
        from paper_compass.cli import main

        with mock.patch.object(sys, "argv", ["paper-compass", "repair-fts", "--help"]):
            with mock.patch("sys.stdout", io.StringIO()) as output:
                with pytest.raises(SystemExit) as exc_info:
                    main()
        assert exc_info.value.code == 0
        text = output.getvalue()
        assert "--db-path" in text
        assert "--backup" in text
        assert "--dry-run" in text
        assert "--json" in text

    def test_execute_reports_healthy_index(self, tmp_path):
        from paper_compass.cli.repair_fts import execute_repair_fts

        _make_db(tmp_path / "db")
        args = _cli_args(["--db-path", str(tmp_path / "db")])

        with mock.patch("sys.stdout", io.StringIO()) as output:
            assert execute_repair_fts(args) == 0
        assert "healthy" in output.getvalue()

    def test_execute_repairs_corrupted_index(self, tmp_path):
        from paper_compass.cli.repair_fts import execute_repair_fts

        sqlite_path = _make_db(tmp_path / "db")
        _corrupt(sqlite_path)
        args = _cli_args(["--db-path", str(tmp_path / "db")])

        with mock.patch("sys.stdout", io.StringIO()) as output:
            assert execute_repair_fts(args) == 0
        assert "repaired: yes" in output.getvalue()
        assert _quick_problems(sqlite_path) == []

    def test_execute_dry_run_returns_nonzero_for_corruption(self, tmp_path):
        from paper_compass.cli.repair_fts import execute_repair_fts

        sqlite_path = _make_db(tmp_path / "db")
        _corrupt(sqlite_path)
        args = _cli_args(["--db-path", str(tmp_path / "db"), "--dry-run"])

        with mock.patch("sys.stdout", io.StringIO()) as output:
            assert execute_repair_fts(args) == 1
        assert "Dry run" in output.getvalue()
        assert _quick_problems(sqlite_path)

    def test_execute_returns_error_for_missing_database(self, tmp_path):
        from paper_compass.cli.repair_fts import execute_repair_fts

        args = _cli_args(["--db-path", str(tmp_path / "missing")])

        with mock.patch("sys.stdout", io.StringIO()) as output:
            assert execute_repair_fts(args) == 1
        assert "ERROR" in output.getvalue()

    def test_execute_json_reports_fields(self, tmp_path):
        from paper_compass.cli.repair_fts import execute_repair_fts

        _make_db(tmp_path / "db")
        args = _cli_args(["--db-path", str(tmp_path / "db"), "--json"])

        with mock.patch("sys.stdout", io.StringIO()) as output:
            assert execute_repair_fts(args) == 0
        payload = json.loads(output.getvalue())
        assert payload["ok"] is True
        assert payload["fulltext_tables"] == ["embedding_fulltext_search"]
