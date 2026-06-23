"""paper-compass sync subcommand.

One-command data sync for Zotero metadata, paper index, wiki generation, and wiki index.
"""

from __future__ import annotations

import argparse
import shlex

from paper_compass.config import resolve_path_settings
from paper_compass.env_utils import PROJECT_ROOT
from paper_compass.local_state import load_last_successful_zotero_source, source_config_path
from paper_compass.pipeline_sync import SyncOptions, VectordbHealthError, run_sync_pipeline


def add_subcommand_parser(subparsers: argparse._SubParsersAction) -> None:
    parser = subparsers.add_parser(
        "sync",
        help="Run incremental data sync for Zotero, vector index, and wiki",
        description="Execute the paper-compass data sync pipeline with health checks and rebuild controls.",
    )
    parser.add_argument("--db-path", default="", help="Path to ChromaDB persistent directory")
    parser.add_argument(
        "--db-source-path",
        default="",
        help="Explicit path to zotero.sqlite. Legacy zotero_readonly.sqlite is not auto-discovered.",
    )
    parser.add_argument("--storage-path", default="", help="Explicit path to Zotero storage directory")
    parser.add_argument(
        "--snapshot-db",
        choices=["auto", "always", "never"],
        default="auto",
        help="Whether to snapshot the Zotero sqlite before reading",
    )
    parser.add_argument(
        "--snapshot-dir",
        default="data/state/zotero-snapshots",
        help="Directory for temporary Zotero sqlite snapshots",
    )
    parser.add_argument(
        "--snapshot-keep",
        type=int,
        default=5,
        help="Number of runtime Zotero sqlite snapshots to keep",
    )
    parser.add_argument(
        "--snapshot-max-age-days",
        type=int,
        default=0,
        help="Delete runtime snapshots older than N days; 0 disables age-based cleanup",
    )
    parser.add_argument(
        "--allow-live-zotero-read",
        action="store_true",
        help="Allow direct reads from a live Zotero sqlite when snapshotting is disabled",
    )
    parser.add_argument("--library", default="", help="Path to library.json")
    parser.add_argument("--wiki-root", default="", help="Wiki root directory")
    parser.add_argument("--workers", type=int, default=10, help="Worker count for wiki generation")
    parser.add_argument("--skip-zotero-sync", action="store_true", help="Skip sync_zotero stage")
    parser.add_argument("--skip-paper-index", action="store_true", help="Skip paper index stage")
    parser.add_argument("--skip-wiki-ingest", action="store_true", help="Skip wiki generation stage")
    parser.add_argument("--skip-wiki-index", action="store_true", help="Skip wiki vector index stage")
    parser.add_argument(
        "--rebuild",
        choices=["none", "papers", "wiki", "all"],
        default="none",
        help="Rebuild scope when recovery is required",
    )
    parser.add_argument(
        "--backup-corrupted-db",
        action="store_true",
        help="Backup corrupted vectordb before rebuild",
    )
    parser.add_argument(
        "--lock-timeout-minutes",
        type=int,
        default=360,
        help="Treat an abandoned sync lock older than this as stale",
    )
    parser.add_argument(
        "--force-unlock",
        action="store_true",
        help="Remove the current sync.lock and exit without running sync stages",
    )
    parser.add_argument("--dry-run", action="store_true", help="Show planned stages without running commands")
    parser.set_defaults(func=execute_sync)


def execute_sync(args: argparse.Namespace) -> int:
    local_paths = load_last_successful_zotero_source(source_config_path(PROJECT_ROOT))
    path_settings = resolve_path_settings(
        overrides={
            "library_json_path": args.library,
            "wiki_root": args.wiki_root,
            "vectordb_path": args.db_path,
            "zotero_sqlite_path": args.db_source_path,
            "zotero_storage_path": args.storage_path,
        },
        local_paths=local_paths,
    )
    try:
        result = run_sync_pipeline(
            SyncOptions(
                project_root=PROJECT_ROOT,
                db_path=PROJECT_ROOT / path_settings.vectordb_path,
                db_source_path=path_settings.zotero_sqlite_path or None,
                storage_path=path_settings.zotero_storage_path or None,
                snapshot_db=args.snapshot_db,
                snapshot_dir=args.snapshot_dir,
                snapshot_keep=args.snapshot_keep,
                snapshot_max_age_days=args.snapshot_max_age_days,
                allow_live_zotero_read=args.allow_live_zotero_read,
                library_path=path_settings.library_json_path,
                wiki_root=path_settings.wiki_root,
                workers=args.workers,
                dry_run=args.dry_run,
                rebuild=args.rebuild,
                backup_corrupted_db=args.backup_corrupted_db,
                skip_zotero_sync=args.skip_zotero_sync,
                skip_paper_index=args.skip_paper_index,
                skip_wiki_ingest=args.skip_wiki_ingest,
                skip_wiki_index=args.skip_wiki_index,
                lock_timeout_minutes=args.lock_timeout_minutes,
                force_unlock=args.force_unlock,
            )
        )
    except VectordbHealthError as exc:
        print(f"\n  ✗ {exc}")
        return 1
    except RuntimeError as exc:
        print(f"\n  ✗ {exc}")
        return 1

    print()
    print(f"  sync status: {result.status}")
    print(
        f"  planned stages: {', '.join(result.planned_stages) if result.planned_stages else '(none)'}"
    )
    print(
        f"  completed stages: {', '.join(result.completed_stages) if result.completed_stages else '(none)'}"
    )
    print(f"  state file: {result.state_path}")
    if result.health_summary:
        print(f"  health preflight: {result.health_summary}")
    if result.planned_commands:
        print("  planned commands:")
        for command in result.planned_commands:
            print(f"    {shlex.join(command)}")
    print(f"  summary: {result.summary}")
    return 0
