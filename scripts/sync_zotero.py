#!/usr/bin/env python3
"""
Zotero sync CLI for paper-compass.

Scans PDFs from a fixed directory, optionally merges external metadata,
and outputs manifest.csv + library.json.

Usage:
    python scripts/sync_zotero.py --pdf-root /mnt/d/zotero_backup \\
        [--metadata ./data/input/zotero_metadata.csv] \\
        [--out-dir ./data/zotero-export] \\
        [--no-sha]
"""

import argparse
import sys
from pathlib import Path

# Ensure src/ is on path when running from project root
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from miniresearch.zotero import (
    scan_pdf_root,
    build_base_record,
    load_external_metadata,
    merge_records,
    write_manifest_csv,
    write_library_json,
    generate_sync_report,
)


def main():
    parser = argparse.ArgumentParser(
        description="Sync Zotero PDFs and metadata for paper-compass"
    )
    parser.add_argument(
        "--pdf-root",
        required=True,
        help="Root directory containing Zotero PDFs (e.g. /mnt/d/zotero_backup)",
    )
    parser.add_argument(
        "--metadata",
        default=None,
        help="Optional metadata file (CSV or JSON) for enriching PDF records",
    )
    parser.add_argument(
        "--out-dir",
        default="./data/zotero-export",
        help="Output directory for manifest.csv and library.json (default: ./data/zotero-export)",
    )
    parser.add_argument(
        "--no-sha",
        action="store_true",
        help="Skip SHA-256 computation (faster on large directories)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print report only, do not write output files",
    )

    args = parser.parse_args()

    # Validate inputs
    pdf_root = args.pdf_root
    if not Path(pdf_root).exists():
        print(f"ERROR: PDF root directory not found: {pdf_root}", file=sys.stderr)
        sys.exit(1)

    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    # Step 1: Scan PDFs
    print(f"Scanning PDFs from: {pdf_root} ...")
    try:
        pdfs = scan_pdf_root(pdf_root)
    except FileNotFoundError as e:
        print(f"ERROR: {e}", file=sys.stderr)
        sys.exit(1)

    print(f"  Found {len(pdfs)} PDFs")

    if not pdfs:
        print("WARNING: No PDFs found. Nothing to do.")
        sys.exit(0)

    # Step 2: Build base records
    base_records = [build_base_record(p, pdf_root) for p in pdfs]

    # Step 3: Load optional metadata
    meta_records = None
    if args.metadata:
        try:
            meta_records = load_external_metadata(args.metadata)
            print(f"  Loaded {len(meta_records)} metadata records")
        except (FileNotFoundError, ValueError) as e:
            print(f"WARNING: Could not load metadata: {e}")

    # Step 4: Merge
    records = merge_records(
        base_records, meta_records, compute_sha=not args.no_sha
    )

    # Step 5: Generate report
    report = generate_sync_report(records)
    print()
    print("── Sync Report ──")
    print(f"  Total PDFs:           {report['total_pdfs']}")
    print(f"  With metadata:        {report['with_metadata']}")
    print(f"  Scan only:            {report['scan_only']}")
    print(f"  Missing title:        {report['missing_title']}")
    print(f"  Missing DOI:          {report['missing_doi']}")
    print(f"  Missing authors:      {report['missing_authors']}")
    print(f"  Duplicate filenames:  {report['duplicate_filenames']}")

    if args.dry_run:
        print("\n[Dry run — no files written]")
        sys.exit(0)

    # Step 6: Write outputs
    manifest_path = out_dir / "manifest.csv"
    library_path = out_dir / "library.json"

    n_manifest = write_manifest_csv(records, str(manifest_path))
    n_library = write_library_json(records, str(library_path))

    print(f"\n  Wrote {n_manifest} records to {manifest_path}")
    print(f"  Wrote {n_library} records to {library_path}")
    print("Sync complete.")


if __name__ == "__main__":
    main()
