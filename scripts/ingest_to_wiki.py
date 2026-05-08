#!/usr/bin/env python3
"""
Automated LLM wiki generation for paper-compass.

Extracts text from PDFs, calls LLM to generate wiki pages,
and saves to the wiki/ directory.

Usage:
    # Generate wiki pages for all papers (skip existing)
    python scripts/ingest_to_wiki.py --skip-existing

    # Batch process first 50 papers
    python scripts/ingest_to_wiki.py --limit 50 --skip-existing

    # Generate for a single paper by key
    python scripts/ingest_to_wiki.py --key ABC123

    # Dry-run
    python scripts/ingest_to_wiki.py --dry-run --limit 2
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


def _has_wiki_page(key: str, wiki_root: str) -> bool:
    """Check if a wiki page already exists for this Zotero key.

    Looks for files in wiki/papers/ whose frontmatter sources contain zotero:KEY.
    Also checks text files in data/texts/ for quick lookup.
    """
    papers_dir = Path(wiki_root) / "papers"
    if not papers_dir.exists():
        return False

    # Check existing wiki pages for zotero:KEY reference
    for md_file in papers_dir.glob("*.md"):
        try:
            content = md_file.read_text(encoding="utf-8")
            if f"zotero:{key}" in content:
                return True
        except Exception:
            continue
    return False


def main():
    _load_env()

    parser = argparse.ArgumentParser(description="Auto-generate wiki pages from Zotero PDFs")
    parser.add_argument("--library", default="data/zotero-export/library.json")
    parser.add_argument("--key", help="Process a single item by Zotero key")
    parser.add_argument("--limit", type=int, default=0, help="Max papers to process (0=all)")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--skip-existing", action="store_true",
                        help="Skip papers that already have a wiki page")
    parser.add_argument("--wiki-root", default="./wiki")
    parser.add_argument("--max-chars", type=int, default=12000,
                        help="Max chars from PDF to send to LLM")
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

    total = len(items)
    if args.limit > 0:
        items = items[:args.limit]

    generator = WikiGenerator()
    generated = 0
    skipped = 0
    pre_existing = 0
    errors = 0

    for i, item in enumerate(items):
        key = item.get("key", "")
        title = item.get("title", "")
        pdf_path = item.get("pdf_path", "")

        # Progress header
        print(f"\n[{i+1}/{len(items)}] [{key}] {title[:70]}...")

        # Skip if PDF missing
        if not pdf_path or not Path(pdf_path).exists():
            print(f"  SKIP: PDF not found")
            skipped += 1
            continue

        # Skip if already exists
        if args.skip_existing and _has_wiki_page(key, args.wiki_root):
            print(f"  SKIP: wiki page already exists")
            pre_existing += 1
            continue

        # Extract text
        text_file = Path("data/texts") / f"{key}.txt"
        if text_file.exists():
            paper_text = text_file.read_text(encoding="utf-8")
        else:
            try:
                extractor = PDFExtractor(pdf_path)
                paper_text = extractor.extract_all_text()
            except Exception as e:
                print(f"  ERROR extracting text: {e}")
                errors += 1
                continue

        if not paper_text.strip():
            print(f"  SKIP: no extractable text")
            skipped += 1
            continue

        if args.dry_run:
            print(f"  [DRY-RUN] Would generate wiki page")
            continue

        # Generate wiki page
        try:
            result = generator.generate(title, paper_text, item,
                                        max_input_chars=args.max_chars)
        except Exception as e:
            print(f"  ERROR calling LLM: {e}")
            errors += 1
            continue

        # Save to wiki
        from miniresearch.wiki_store import save_query_to_wiki

        try:
            save_result = save_query_to_wiki(
                title=result["title"],
                content=result["content"],
                target_type=result.get("target_type", "papers"),
                source_refs=[f"zotero:{key}", pdf_path],
                confidence=result.get("confidence", "medium"),
                tags=result.get("tags", []),
                wiki_root=args.wiki_root,
            )
            print(f"  SAVED: {Path(save_result['page_path']).name}")
        except Exception as e:
            print(f"  ERROR saving: {e}")
            errors += 1
            continue

        generated += 1

    # Summary
    print(f"\n{'='*55}")
    print(f"Wiki Generation Report")
    print(f"{'='*55}")
    print(f"  Total in scope:     {len(items)}")
    print(f"  Generated:          {generated}")
    print(f"  Pre-existing:       {pre_existing}")
    print(f"  Skipped (no PDF):   {skipped}")
    print(f"  Errors:             {errors}")
    print(f"{'='*55}")


if __name__ == "__main__":
    main()
