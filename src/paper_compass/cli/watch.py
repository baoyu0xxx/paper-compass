"""paper-compass watch subcommand."""

from __future__ import annotations

import argparse
import subprocess
import sys
import threading
from pathlib import Path

from paper_compass.config import resolve_path_settings
from paper_compass.env_utils import PROJECT_ROOT, load_project_env
from paper_compass.watcher import run_watch


def add_subcommand_parser(subparsers: argparse._SubParsersAction) -> None:
    parser = subparsers.add_parser(
        "watch",
        help="Watch Zotero storage and trigger incremental sync",
        description="Passively watch Zotero storage and coalesce changes into sync runs.",
    )
    parser.add_argument("--storage-path", default="", help="Zotero storage directory")
    parser.add_argument("--sqlite-path", default="", help="Zotero SQLite database path")
    parser.add_argument("--debounce-seconds", type=float, default=3.0)
    parser.add_argument("--reconcile-seconds", type=float, default=600.0)
    parser.add_argument("--once", action="store_true", help="Run one reconciliation sync and exit")
    parser.set_defaults(func=execute_watch)


def execute_watch(args: argparse.Namespace) -> int:
    load_project_env()
    settings = resolve_path_settings(
        overrides={
            "zotero_storage_path": args.storage_path,
            "zotero_sqlite_path": args.sqlite_path,
        }
    )
    storage_path = settings.zotero_storage_path
    sqlite_path = settings.zotero_sqlite_path
    if not storage_path:
        print("watch requires PAPER_COMPASS_ZOTERO_ROOT or --storage-path")
        return 2

    def sync(_events: set[str]) -> None:
        result = subprocess.run(
            [sys.executable, "-m", "paper_compass", "sync"],
            cwd=str(PROJECT_ROOT),
            check=False,
        )
        if result.returncode:
            print(f"watch sync failed with exit code {result.returncode}", file=sys.stderr)

    if args.once:
        sync({"__reconcile__"})
        return 0

    try:
        run_watch(
            storage_path,
            sqlite_path or None,
            sync,
            debounce_seconds=max(0.25, args.debounce_seconds),
            reconcile_seconds=max(30.0, args.reconcile_seconds),
        )
    except KeyboardInterrupt:
        return 0
    return 0
