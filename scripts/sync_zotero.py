#!/usr/bin/env python3
"""
Zotero sync for paper-compass — reads SQLite, extracts PDF text, outputs library.json.

Usage:
    python scripts/sync_zotero.py
        [--db-path /path/to/zotero.sqlite]
        [--storage-path /path/to/storage]
        [--out-dir ./data/zotero-export]
        [--extract-text]          # also extract and cache PDF text
        [--text-dir ./data/texts]
"""

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from paper_compass.document_extract import extract_document
from paper_compass.pipeline_sync import write_standalone_stage_state
from paper_compass.zotero_paths import ZoteroSourceNotFoundError, resolve_zotero_source
from paper_compass.zotero_snapshot import cleanup_sqlite_snapshots, prepare_zotero_database_for_read
from paper_compass.source_scanner import normalize_storage_items, scan_storage
from paper_compass.zotero_sqlite import ZoteroLibrary


def _failure_report_path(out_dir: Path) -> Path:
    return out_dir.parent / "logs" / "pdf_extract_failures.jsonl"


def _append_failure_report(report_path: Path, *, stage: str, key: str, pdf_path: str, reason: str, exception: str = "") -> None:
    report_path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "stage": stage,
        "key": key,
        "pdf_path": pdf_path,
        "reason": reason,
    }
    if exception:
        payload["exception"] = exception
    with report_path.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(payload, ensure_ascii=False) + "\n")


def main():
    parser = argparse.ArgumentParser(description="Sync Zotero metadata and PDFs for paper-compass")
    parser.add_argument(
        "--db-path",
        default=None,
        help=(
            "Explicit path to zotero.sqlite. Legacy zotero_readonly.sqlite is accepted "
            "only when explicitly supplied. Overrides auto-discovery."
        ),
    )
    parser.add_argument(
        "--storage-path",
        default=None,
        help="Explicit path to Zotero storage/ directory. Overrides the default sibling storage path.",
    )
    parser.add_argument("--out-dir", default="./data/zotero-export")
    parser.add_argument("--extract-text", action="store_true", help="Extract and cache PDF full text")
    parser.add_argument(
        "--force-reextract-text",
        action="store_true",
        help="Re-extract PDF text even when a non-empty cached text file already exists",
    )
    parser.add_argument("--text-dir", default="./data/texts")
    parser.add_argument(
        "--snapshot-db",
        choices=["auto", "always", "never"],
        default="auto",
        help="Whether to snapshot the Zotero sqlite before reading (default: auto)",
    )
    parser.add_argument(
        "--snapshot-dir",
        default="data/state/zotero-snapshots",
        help="Directory for temporary sqlite snapshots when reading live Zotero databases",
    )
    parser.add_argument("--snapshot-keep", type=int, default=5, help="Number of runtime Zotero sqlite snapshots to keep")
    parser.add_argument("--snapshot-max-age-days", type=int, default=0, help="Delete runtime snapshots older than N days; 0 disables age-based cleanup")
    parser.add_argument("--dry-run", action="store_true", help="Resolve Zotero paths and read policy without creating outputs or reading SQLite")
    parser.add_argument(
        "--allow-live-zotero-read",
        action="store_true",
        help="Allow direct reads from a live Zotero sqlite when snapshotting is disabled",
    )
    args = parser.parse_args()
    project_root = Path(__file__).resolve().parent.parent

    try:
        source = resolve_zotero_source(
            db_path=args.db_path,
            storage_path=args.storage_path,
        )
    except ZoteroSourceNotFoundError as exc:
        write_standalone_stage_state(project_root, stage="sync_zotero", status="failed", error=str(exc))
        print(f"ERROR: {exc}", file=sys.stderr)
        sys.exit(1)

    if args.dry_run:
        print()
        print("── Zotero Source Plan ──")
        print(f"  Database:     {source.db_path}")
        print(f"  Storage:      {source.storage_path}")
        print(f"  Source:       {source.source_kind}")
        print(f"  Live DB:      {'yes' if source.is_live_candidate else 'no'}")
        print(f"  Read policy:  snapshot-db={args.snapshot_db}")
        print(f"  Tried:        {len(source.tried)} candidates")
        write_standalone_stage_state(project_root, stage="sync_zotero", status="dry_run", dry_run=True)
        return

    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    text_dir = Path(args.text_dir)
    if args.extract_text:
        text_dir.mkdir(parents=True, exist_ok=True)

    # ── Read from Zotero SQLite ──
    print(f"Reading Zotero database: {source.db_path}")
    print(f"  Storage directory: {source.storage_path}")
    print(f"  Discovery source:  {source.source_kind}")
    print("  Read mode:         SQLite read-only URI")
    prepared = prepare_zotero_database_for_read(
        source,
        snapshot_policy=args.snapshot_db,
        snapshot_dir=Path(args.snapshot_dir),
        allow_live_zotero_read=args.allow_live_zotero_read,
    )
    print(f"  Read database:     {prepared.read_db_path}")
    if prepared.used_snapshot:
        print(f"  Snapshot source:   {prepared.original_db_path}")
    lib = ZoteroLibrary(
        str(prepared.read_db_path),
        storage_path=str(source.storage_path),
        immutable=prepared.use_immutable,
    )
    metadata_items = lib.get_all_items_with_pdfs()
    lib.close()

    cleanup = cleanup_sqlite_snapshots(
        Path(args.snapshot_dir),
        keep=args.snapshot_keep,
        max_age_days=args.snapshot_max_age_days,
    )
    if cleanup.scanned_count:
        print(f"  Snapshot cleanup: scanned={cleanup.scanned_count}, deleted={cleanup.deleted_count}")

    candidates = scan_storage(source.storage_path)
    items = normalize_storage_items(source.storage_path, metadata_items)
    normalized_keys = {str(item.get("key", "")) for item in items}
    for legacy in metadata_items:
        key = str(legacy.get("key", ""))
        pdf_path = str(legacy.get("pdf_path", "") or "")
        if key and key not in normalized_keys and (pdf_path or legacy.get("text_file")):
            item = dict(legacy)
            item["source_kind"] = "pdf" if pdf_path else "text"
            item["source_path"] = pdf_path or str(legacy.get("text_file", ""))
            item["cache_path"] = ""
            item["skipped_reason"] = ""
            items.append(item)
    skipped_missing_content = sum(1 for candidate in candidates if candidate.source_kind == "unavailable")
    print(f"  Storage candidates: {len(candidates)}")
    print(f"  Usable content sources: {len(items)}")

    if not items:
        print("WARNING: No usable cache or PDF sources found.")
        library_path = out_dir / "library.json"
        library_path.write_text("[]", encoding="utf-8")
        write_standalone_stage_state(project_root, stage="sync_zotero", status="ok")
        return

    # ── Enrich: reuse Zotero cache, or extract PDF fallback ──
    extracted = 0
    reused_text = 0
    reused_cache = 0
    failure_counts: dict[str, int] = {}
    report_path = _failure_report_path(out_dir)

    for item in items:
        key = item["key"]
        source_kind = item.get("source_kind", "")
        source_path = Path(item.get("source_path", "")) if item.get("source_path") else None
        pdf_path = item.get("pdf_path", "")
        if source_kind == "ft_cache" and source_path and source_path.exists():
            item["text_file"] = str(source_path)
            reused_cache += 1
        elif source_kind == "pdf" and pdf_path and Path(pdf_path).exists():
            existing_text = text_dir / f"{key}.txt"
            existing_text_usable = False
            if existing_text.exists():
                try:
                    existing_text_usable = bool(existing_text.read_text(encoding="utf-8").strip())
                except Exception:
                    existing_text_usable = False
            if existing_text_usable and not args.force_reextract_text:
                item["text_file"] = str(existing_text)
                reused_text += 1
            elif args.extract_text:
                try:
                    full_text = extract_document(pdf_path).text
                    if full_text.strip():
                        text_file = text_dir / f"{key}.txt"
                        text_file.write_text(full_text, encoding="utf-8")
                        item["text_file"] = str(text_file)
                        extracted += 1
                    else:
                        failure_counts["empty text"] = failure_counts.get("empty text", 0) + 1
                        _append_failure_report(report_path, stage="sync_zotero", key=key, pdf_path=pdf_path, reason="empty text")
                except Exception as exc:
                    print(f"  WARNING: text extraction failed for {key}: {exc}", file=sys.stderr)
                    failure_counts["extract error"] = failure_counts.get("extract error", 0) + 1
                    _append_failure_report(
                        report_path,
                        stage="sync_zotero",
                        key=key,
                        pdf_path=pdf_path,
                        reason="extract error",
                        exception=str(exc),
                    )

        date_str = item.get("date", "")
        item["year"] = int(date_str[:4]) if date_str and date_str[:4].isdigit() else None

    # ── Output library.json ──
    library_path = out_dir / "library.json"
    with open(library_path, "w", encoding="utf-8") as f:
        json.dump(items, f, ensure_ascii=False, indent=2)

    # ── Report ──
    tags_set = set()
    collections_set = set()
    for item in items:
        for t in item.get("tags", []):
            if t:
                tags_set.add(t)
        for c in item.get("collections", []):
            if c:
                collections_set.add(c)

    print()
    print("── Sync Report ──")
    print(f"  Storage candidates:   {len(candidates)}")
    print(f"  Usable content:       {len(items)}")
    print(f"  Missing cache and PDF:{skipped_missing_content:4d}")
    print(f"  Unique tags:          {len(tags_set)}")
    print(f"  Unique collections:   {len(collections_set)}")
    if args.extract_text:
        print(f"  Cache texts reused:   {reused_cache}")
        print(f"  PDF texts reused:     {reused_text}")
        print(f"  PDF texts extracted:  {extracted}")
        if failure_counts:
            print(f"  PDF text warnings:     {sum(failure_counts.values())}")
            for reason, count in sorted(failure_counts.items()):
                print(f"    {reason}: {count}")
            print(f"  Failure report:        {report_path}")
    print(f"  Output:                {library_path}")
    print("Sync complete.")
    write_standalone_stage_state(project_root, stage="sync_zotero", status="ok")


if __name__ == "__main__":
    main()
