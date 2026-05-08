#!/usr/bin/env python3
"""
Automated LLM wiki generation for paper-compass.

Extracts text from PDFs, calls LLM to generate wiki pages,
and saves to the wiki/ directory.

Usage:
    # Generate wiki pages for all papers
    python scripts/ingest_to_wiki.py --library data/zotero-export/library.json

    # Generate for a single paper by key
    python scripts/ingest_to_wiki.py --library data/zotero-export/library.json --key ABC123

    # Dry-run (print what would be generated, don't save)
    python scripts/ingest_to_wiki.py --library data/zotero-export/library.json --dry-run --limit 2
"""

import argparse
import json
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from miniresearch.wiki_gen import WikiGenerator
from miniresearch.pdf_extract import PDFExtractor


def _load_env():
    env_path = Path(__file__).resolve().parent.parent / ".env"
    if env_path.exists():
        for line in env_path.read_text().splitlines():
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                key, _, val = line.partition("=")
                if val and not os.environ.get(key.strip()):
                    os.environ[key.strip()] = val.strip()


def main():
    _load_env()

    parser = argparse.ArgumentParser(description="Auto-generate wiki pages from Zotero PDFs")
    parser.add_argument("--library", default="data/zotero-export/library.json")
    parser.add_argument("--key", help="Process a single item by Zotero key")
    parser.add_argument("--limit", type=int, default=0, help="Max papers to process (0=all)")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--wiki-root", default="./wiki")
    parser.add_argument("--max-chars", type=int, default=8000, help="Max chars from PDF to send to LLM")
    args = parser.parse_args()

    library_path = Path(args.library)
    if not library_path.exists():
        print(f"ERROR: library.json not found: {library_path}")
        print("Run sync_zotero.py --extract-text first.")
        sys.exit(1)

    with open(library_path, "r", encoding="utf-8") as f:
        items = json.load(f)

    if args.key:
        items = [i for i in items if i.get("key") == args.key]
        if not items:
            print(f"ERROR: No item found with key: {args.key}")
            sys.exit(1)

    if args.limit > 0:
        items = items[:args.limit]

    generator = WikiGenerator()
    generated = 0
    skipped = 0
    errors = 0

    for item in items:
        pdf_path = item.get("pdf_path", "")
        title = item.get("title", "")
        key = item.get("key", "")

        if not pdf_path or not Path(pdf_path).exists():
            print(f"  SKIP [{key}]: PDF not found")
            skipped += 1
            continue

        print(f"  Processing [{key}]: {title[:80]}...")

        try:
            extractor = PDFExtractor(pdf_path)
            paper_text = extractor.extract_all_text()
        except Exception as e:
            print(f"    ERROR extracting text: {e}")
            errors += 1
            continue

        if not paper_text.strip():
            print(f"    SKIP: no extractable text")
            skipped += 1
            continue

        if not args.dry_run:
            try:
                result = generator.generate(
                    title=title,
                    paper_text=paper_text,
                    metadata=item,
                    max_input_chars=args.max_chars,
                )
            except Exception as e:
                print(f"    ERROR calling LLM: {e}")
                errors += 1
                continue

            # Save to wiki
            from miniresearch.wiki_store import save_query_to_wiki

            save_result = save_query_to_wiki(
                title=result["title"],
                content=result["content"],
                target_type=result.get("target_type", "topics"),
                source_refs=[f"zotero:{key}", pdf_path],
                confidence=result.get("confidence", "medium"),
                tags=result.get("tags", []),
                wiki_root=args.wiki_root,
            )
            print(f"    SAVED: {save_result['page_path']}")
        else:
            print(f"    [DRY-RUN] Would generate wiki page")

        generated += 1

    print(f"\n── Wiki Generation Report ──")
    print(f"  Generated: {generated}")
    print(f"  Skipped:   {skipped}")
    print(f"  Errors:    {errors}")


if __name__ == "__main__":
    main()
