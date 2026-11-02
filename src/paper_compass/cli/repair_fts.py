"""paper-compass repair-fts subcommand.

Rebuild a corrupted ChromaDB FTS5 full-text index in place (no re-embedding).
"""

from __future__ import annotations

import argparse
import json
from dataclasses import asdict
from pathlib import Path

from paper_compass.config import resolve_path_settings
from paper_compass.env_utils import PROJECT_ROOT
from paper_compass.index_health import FulltextRepairError, repair_fulltext_index


def add_subcommand_parser(subparsers: argparse._SubParsersAction) -> None:
    parser = subparsers.add_parser(
        "repair-fts",
        help="Rebuild a corrupted FTS5 full-text index in ChromaDB without re-embedding",
        description=(
            "Repair the ChromaDB full-text index when SQLite reports "
            "\"malformed inverted index for FTS5 table\". The index is rebuilt from the "
            "stored text, so embeddings, metadata, and collections are left untouched."
        ),
    )
    parser.add_argument(
        "--db-path",
        default="",
        help="Path to the ChromaDB persistent directory (defaults to the configured vectordb path)",
    )
    parser.add_argument(
        "--backup",
        action="store_true",
        help="Copy chroma.sqlite3 next to itself (chroma.sqlite3.bak-<timestamp>) before repairing",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Report the full-text index state without modifying the database",
    )
    parser.add_argument("--json", action="store_true", help="Print the repair report as JSON")
    parser.set_defaults(func=execute_repair_fts)


def _resolve_vectordb_path(explicit: str) -> Path:
    settings = resolve_path_settings(overrides={"vectordb_path": explicit})
    path = Path(settings.vectordb_path)
    return path if path.is_absolute() else PROJECT_ROOT / path


def execute_repair_fts(args: argparse.Namespace) -> int:
    db_path = _resolve_vectordb_path(args.db_path)
    try:
        report = repair_fulltext_index(db_path, dry_run=args.dry_run, backup=args.backup)
    except FulltextRepairError as exc:
        print(f"\n  ERROR: {exc}")
        return 1

    if args.json:
        print(json.dumps(asdict(report), ensure_ascii=False, indent=2))
        return 0 if report.ok else 1

    print(f"  full-text database: {report.sqlite_path}")
    print(f"  tables: {', '.join(report.fulltext_tables) if report.fulltext_tables else '(none)'}")
    if report.corrupted_tables:
        print(f"  corrupted tables: {', '.join(report.corrupted_tables)}")
    if report.before:
        print(f"  quick_check before: {'; '.join(report.before)}")
    else:
        print("  quick_check before: ok")
    if report.repaired:
        print("  repaired: yes")
        print(f"  quick_check after: {'; '.join(report.after) if report.after else 'ok'}")
    if report.backup_path:
        print(f"  backup: {report.backup_path}")
    print(f"  result: {report.message}")
    return 0 if report.ok else 1
