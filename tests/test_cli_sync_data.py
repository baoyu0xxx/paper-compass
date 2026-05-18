"""Tests for paper-compass sync CLI subcommand."""

from __future__ import annotations

import io
import sys
from unittest import mock

import pytest

from paper_compass.pipeline_sync import SyncResult


class TestSyncCliArgParsing:
    def test_subcommand_registered(self):
        from paper_compass.cli import main

        with mock.patch.object(sys, "argv", ["paper-compass", "sync", "--help"]):
            with mock.patch("sys.stdout", io.StringIO()) as fake_out:
                with pytest.raises(SystemExit) as exc_info:
                    main()
                assert exc_info.value.code == 0
                output = fake_out.getvalue()
                assert "--skip-zotero-sync" in output
                assert "--rebuild" in output
                assert "--dry-run" in output
                assert "--backup-corrupted-db" in output

    def test_rebuild_choices_and_defaults(self):
        parser = _make_parser()
        args = parser.parse_args(["--rebuild", "papers", "--dry-run"])
        assert args.rebuild == "papers"
        assert args.dry_run is True
        assert args.skip_zotero_sync is False

    def test_skip_flags(self):
        parser = _make_parser()
        args = parser.parse_args([
            "--skip-zotero-sync",
            "--skip-paper-index",
            "--skip-wiki-ingest",
            "--skip-wiki-index",
        ])
        assert args.skip_zotero_sync is True
        assert args.skip_paper_index is True
        assert args.skip_wiki_ingest is True
        assert args.skip_wiki_index is True


class TestSyncExecute:
    def test_execute_sync_returns_zero_on_success(self):
        from paper_compass.cli import sync_data

        args = _make_parser().parse_args(["--dry-run"])
        result = SyncResult(
            status="dry_run",
            summary="planned",
            planned_stages=["sync_zotero", "index_papers"],
            completed_stages=[],
            state_path="/tmp/last_sync.json",
        )
        with mock.patch.object(sync_data, "run_sync_pipeline", return_value=result) as mocked:
            with mock.patch("sys.stdout", io.StringIO()) as fake_out:
                rc = sync_data.execute_sync(args)

        assert rc == 0
        called_options = mocked.call_args.args[0]
        assert called_options.project_root == sync_data.PROJECT_ROOT
        assert called_options.db_path == sync_data.PROJECT_ROOT / "data/vectordb"
        assert called_options.db_source_path is None
        assert called_options.storage_path is None
        assert called_options.dry_run is True
        assert called_options.rebuild == "none"
        output = fake_out.getvalue()
        assert "sync status: dry_run" in output
        assert "planned stages: sync_zotero, index_papers" in output
        assert "completed stages: (none)" in output
        assert "state file: /tmp/last_sync.json" in output
        assert "summary: planned" in output

    def test_execute_sync_returns_one_on_health_error(self):
        from paper_compass.cli import sync_data
        from paper_compass.pipeline_sync import VectordbHealthError

        args = _make_parser().parse_args([])
        with mock.patch.object(sync_data, "run_sync_pipeline", side_effect=VectordbHealthError("broken")):
            with mock.patch("sys.stdout", io.StringIO()) as fake_out:
                rc = sync_data.execute_sync(args)
                assert rc == 1
                assert "broken" in fake_out.getvalue()

    def test_execute_sync_returns_one_on_runtime_error(self):
        from paper_compass.cli import sync_data

        args = _make_parser().parse_args([])
        with mock.patch.object(sync_data, "run_sync_pipeline", side_effect=RuntimeError("oops")):
            with mock.patch("sys.stdout", io.StringIO()) as fake_out:
                rc = sync_data.execute_sync(args)
                assert rc == 1
                assert "oops" in fake_out.getvalue()


def _make_parser():
    import argparse
    from paper_compass.cli.sync_data import add_subcommand_parser

    parser = argparse.ArgumentParser(prog="paper-compass")
    subparsers = parser.add_subparsers(dest="command")
    add_subcommand_parser(subparsers)
    return subparsers.choices["sync"]
