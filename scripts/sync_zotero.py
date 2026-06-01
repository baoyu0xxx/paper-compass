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

from paper_compass.pdf_extract import PDFExtractor
from paper_compass.zotero_paths import ZoteroSourceNotFoundError, resolve_zotero_source
from paper_compass.zotero_snapshot import cleanup_sqlite_snapshots, prepare_zotero_database_for_read
from paper_compass.zotero_sqlite import ZoteroLibrary


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
    parser.add_argument(
        "--allow-live-zotero-read",
        action="store_true",
        help="Allow direct reads from a live Zotero sqlite when snapshotting is disabled",
    )
    args = parser.parse_args()

    try:
        source = resolve_zotero_source(
            db_path=args.db_path,
            storage_path=args.storage_path,
        )
    except ZoteroSourceNotFoundError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        sys.exit(1)

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
    lib = ZoteroLibrary(str(prepared.read_db_path), storage_path=str(source.storage_path))
    items = lib.get_all_items_with_pdfs()
    lib.close()

    cleanup = cleanup_sqlite_snapshots(
        Path(args.snapshot_dir),
        keep=args.snapshot_keep,
        max_age_days=args.snapshot_max_age_days,
    )
    if cleanup.scanned_count:
        print(f"  Snapshot cleanup: scanned={cleanup.scanned_count}, deleted={cleanup.deleted_count}")

    print(f"  Found {len(items)} items with PDFs")

    if not items:
        print("WARNING: No items with PDFs found.")
        sys.exit(0)

    # ── Enrich: extract text if requested ──
    missing_pdf = 0
    extracted = 0

    for item in items:
        pdf_path = item.get("pdf_path", "")
        existing_text = text_dir / f"{item['key']}.txt"
        if existing_text.exists():
            item["text_file"] = str(existing_text)
        if not pdf_path or not Path(pdf_path).exists():
            missing_pdf += 1
            continue

        if args.extract_text:
            try:
                extractor = PDFExtractor(pdf_path)
                full_text = extractor.extract_all_text()
                if full_text.strip():
                    text_file = text_dir / f"{item['key']}.txt"
                    text_file.write_text(full_text, encoding="utf-8")
                    item["text_file"] = str(text_file)
                    extracted += 1
            except Exception as e:
                print(f"  WARNING: text extraction failed for {item['key']}: {e}", file=sys.stderr)

        # Add derived fields
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
    print(f"  Total items:           {len(items)}")
    print(f"  Missing PDF files:     {missing_pdf}")
    print(f"  Unique tags:           {len(tags_set)}")
    print(f"  Unique collections:    {len(collections_set)}")
    if args.extract_text:
        print(f"  Texts extracted:       {extracted}")
    print(f"  Output:                {library_path}")
    print("Sync complete.")


if __name__ == "__main__":
    main()
