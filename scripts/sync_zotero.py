#!/usr/bin/env python3
"""
Zotero sync for paper-compass — reads SQLite, extracts PDF text, outputs library.json.

Usage:
    python scripts/sync_zotero.py
        [--db-path /mnt/d/zotero_backup/zotero_readonly.sqlite]
        [--out-dir ./data/zotero-export]
        [--extract-text]          # also extract and cache PDF text
        [--text-dir ./data/texts]
"""

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from paper_compass.zotero_sqlite import ZoteroLibrary
from paper_compass.pdf_extract import PDFExtractor


def main():
    parser = argparse.ArgumentParser(description="Sync Zotero metadata and PDFs for paper-compass")
    parser.add_argument("--db-path", default="/mnt/d/zotero_backup/zotero_readonly.sqlite")
    parser.add_argument("--out-dir", default="./data/zotero-export")
    parser.add_argument("--extract-text", action="store_true", help="Extract and cache PDF full text")
    parser.add_argument("--text-dir", default="./data/texts")
    args = parser.parse_args()

    db_path = Path(args.db_path)
    if not db_path.exists():
        print(f"ERROR: Zotero database not found: {db_path}", file=sys.stderr)
        sys.exit(1)

    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    text_dir = Path(args.text_dir)
    if args.extract_text:
        text_dir.mkdir(parents=True, exist_ok=True)

    # ── Read from Zotero SQLite ──
    print(f"Reading Zotero database: {db_path}")
    lib = ZoteroLibrary(str(db_path))
    items = lib.get_all_items_with_pdfs()
    lib.close()

    print(f"  Found {len(items)} items with PDFs")

    if not items:
        print("WARNING: No items with PDFs found.")
        sys.exit(0)

    # ── Enrich: extract text if requested ──
    missing_pdf = 0
    extracted = 0

    for item in items:
        pdf_path = item.get("pdf_path", "")
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
