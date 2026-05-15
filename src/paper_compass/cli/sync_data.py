"""paper-compass sync subcommand.

One-command data sync for Zotero metadata, paper index, wiki generation, and wiki index.
"""

from __future__ import annotations

import argparse

from paper_compass.pipeline_sync import SyncOptions, VectordbHealthError, run_sync_pipeline
from paper_compass.env_utils import PROJECT_ROOT


def add_subcommand_parser(subparsers: argparse._SubParsersAction) -> None:
    parser = subparsers.add_parser(
        "sync",
        help="Run incremental data sync for Zotero, vector index, and wiki",
        description="Execute the paper-compass data sync pipeline with health checks and rebuild controls.",
    )
    parser.add_argument("--db-path", default="data/vectordb", help="Path to ChromaDB persistent directory")
    parser.add_argument("--db-source-path", default="", help="Explicit path to zotero.sqlite or zotero_readonly.sqlite")
    parser.add_argument("--storage-path", default="", help="Explicit path to Zotero storage directory")
    parser.add_argument("--library", default="data/zotero-export/library.json", help="Path to library.json")
    parser.add_argument("--wiki-root", default="./wiki", help="Wiki root directory")
    parser.add_argument("--workers", type=int, default=10, help="Worker count for wiki generation")
    parser.add_argument("--skip-zotero-sync", action="store_true", help="Skip sync_zotero stage")
    parser.add_argument("--skip-paper-index", action="store_true", help="Skip paper index stage")
    parser.add_argument("--skip-wiki-ingest", action="store_true", help="Skip wiki generation stage")
    parser.add_argument("--skip-wiki-index", action="store_true", help="Skip wiki vector index stage")
    parser.add_argument("--rebuild", choices=["none", "papers", "wiki", "all"], default="none", help="Rebuild scope when recovery is required")
    parser.add_argument("--backup-corrupted-db", action="store_true", help="Backup corrupted vectordb before rebuild")
    parser.add_argument("--dry-run", action="store_true", help="Show planned stages without running commands")
    parser.set_defaults(func=execute_sync)


def execute_sync(args: argparse.Namespace) -> int:
    try:
        result = run_sync_pipeline(
            SyncOptions(
                project_root=PROJECT_ROOT,
                db_path=PROJECT_ROOT / args.db_path,
                db_source_path=args.db_source_path or None,
                storage_path=args.storage_path or None,
                library_path=args.library,
                wiki_root=args.wiki_root,
                workers=args.workers,
                dry_run=args.dry_run,
                rebuild=args.rebuild,
                backup_corrupted_db=args.backup_corrupted_db,
                skip_zotero_sync=args.skip_zotero_sync,
                skip_paper_index=args.skip_paper_index,
                skip_wiki_ingest=args.skip_wiki_ingest,
                skip_wiki_index=args.skip_wiki_index,
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
    planned = getattr(result, "planned_stages", None)
    if not isinstance(planned, (list, tuple)):
        planned = []
    completed = getattr(result, "completed_stages", None)
    if not isinstance(completed, (list, tuple)):
        completed = []
    print(f"  planned stages: {', '.join(planned) if planned else '(none)'}")
    print(f"  completed stages: {', '.join(completed) if completed else '(none)'}")
    print(f"  state file: {getattr(result, 'state_path', '(unknown)')}")
    print(f"  summary: {getattr(result, 'summary', '')}")
    return 0
