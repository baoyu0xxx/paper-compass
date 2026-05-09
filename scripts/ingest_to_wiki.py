#!/usr/bin/env python3
"""
Automated LLM wiki generation for paper-compass — concurrent edition.

Extracts text from PDFs, calls LLM to generate wiki pages,
and saves to the wiki/ directory.  Uses ThreadPoolExecutor for
~10× throughput vs the old serial loop.

Usage:
    # Generate wiki pages for all papers (skip existing)
    python scripts/ingest_to_wiki.py --skip-existing

    # Batch process first 50 papers
    python scripts/ingest_to_wiki.py --limit 50 --skip-existing

    # Generate for a single paper by key
    python scripts/ingest_to_wiki.py --key ABC123

    # Dry-run
    python scripts/ingest_to_wiki.py --dry-run --limit 2

    # Tune concurrency (default: 10)
    python scripts/ingest_to_wiki.py --skip-existing --workers 15
"""

import argparse
import json
import re
import sys
import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from paper_compass.env_utils import load_project_env
from paper_compass.wiki_gen import WikiGenerator
from paper_compass.wiki_store import save_query_to_wiki


# ── pre-filtering ───────────────────────────────────────────────────────

def _load_existing_keys(wiki_root: str) -> set:
    """One-shot scan of wiki/papers/ to find all covered Zotero keys."""
    keys: set = set()
    papers_dir = Path(wiki_root) / "papers"
    if not papers_dir.exists():
        return keys
    for md_file in papers_dir.glob("*.md"):
        try:
            text = md_file.read_text(encoding="utf-8")
            for m in re.finditer(r'zotero:([A-Z0-9]+)', text):
                keys.add(m.group(1))
        except Exception:
            continue
    return keys


# ── per-paper worker ────────────────────────────────────────────────────

def _process_one(
    item: dict,
    generator: WikiGenerator,
    args: argparse.Namespace,
) -> dict:
    """Generate and save a wiki page for one paper.  Thread-safe.

    Returns a status dict: {key, status, detail}.
    """
    key = item.get("key", "")
    title = item.get("title", "")

    # --- PDF check ---
    pdf_path = item.get("pdf_path", "")
    if not pdf_path or not Path(pdf_path).exists():
        return {"key": key, "status": "skip", "detail": "PDF not found"}

    # --- text extraction ---
    text_file = Path("data/texts") / f"{key}.txt"
    if text_file.exists():
        paper_text = text_file.read_text(encoding="utf-8")
    else:
        try:
            from paper_compass.pdf_extract import PDFExtractor
            extractor = PDFExtractor(pdf_path)
            paper_text = extractor.extract_all_text()
        except Exception as e:
            return {"key": key, "status": "error", "detail": f"text: {e}"}

    if not paper_text.strip():
        return {"key": key, "status": "skip", "detail": "no extractable text"}

    # --- LLM generation ---
    try:
        result = generator.generate(
            title, paper_text, item,
            max_input_chars=args.max_chars,
        )
    except Exception as e:
        return {"key": key, "status": "error", "detail": f"LLM: {e}"}

    # --- save ---
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
        return {
            "key": key,
            "status": "ok",
            "detail": Path(save_result["page_path"]).name,
        }
    except Exception as e:
        return {"key": key, "status": "error", "detail": f"save: {e}"}


# ── main ────────────────────────────────────────────────────────────────

def main() -> None:
    load_project_env()

    parser = argparse.ArgumentParser(
        description="Auto-generate wiki pages from Zotero PDFs (concurrent)"
    )
    parser.add_argument("--library", default="data/zotero-export/library.json")
    parser.add_argument("--key", help="Process a single item by Zotero key")
    parser.add_argument("--limit", type=int, default=0, help="Max papers to process (0=all)")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--skip-existing", action="store_true",
                        help="Skip papers that already have a wiki page")
    parser.add_argument("--wiki-root", default="./wiki")
    parser.add_argument("--max-chars", type=int, default=12000,
                        help="Max chars from PDF to send to LLM")
    parser.add_argument("--workers", type=int, default=10,
                        help="Number of concurrent workers (default: 10)")
    args = parser.parse_args()

    # ── load library ──
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

    # ── pre-filter ──
    if args.skip_existing:
        existing = _load_existing_keys(args.wiki_root)
        print(f"Pre-existing wiki keys: {len(existing)}")

    work_items = []
    pre_existing = 0
    skipped_no_pdf = 0
    for item in items:
        key = item.get("key", "")
        pdf_path = item.get("pdf_path", "")
        if not pdf_path or not Path(pdf_path).exists():
            skipped_no_pdf += 1
            continue
        if args.skip_existing and key in existing:
            pre_existing += 1
            continue
        work_items.append(item)

    if args.limit > 0:
        work_items = work_items[:args.limit]

    total = len(work_items)
    print(f"Papers to process: {total}  "
          f"(pre-existing: {pre_existing}, no-PDF: {skipped_no_pdf})")

    if total == 0:
        print("Nothing to do.")
        return

    if args.dry_run:
        print(f"[DRY-RUN] Would generate wiki pages for {total} papers")
        for item in work_items[:5]:
            print(f"  - {item.get('title','')[:80]}")
        if total > 5:
            print(f"  ... and {total-5} more")
        return

    # ── concurrent processing ──
    generator = WikiGenerator()
    counter_lock = threading.Lock()
    stats = {"done": 0, "ok": 0, "skip": 0, "error": 0}
    t0 = time.time()

    print(f"\nStarting concurrent generation ({args.workers} workers)...\n")

    with ThreadPoolExecutor(max_workers=args.workers) as executor:
        futures = {
            executor.submit(_process_one, item, generator, args): item
            for item in work_items
        }
        for future in as_completed(futures):
            result = future.result()
            with counter_lock:
                stats["done"] += 1
                if result["status"] == "ok":
                    stats["ok"] += 1
                elif result["status"] == "skip":
                    stats["skip"] += 1
                else:
                    stats["error"] += 1

                elapsed = time.time() - t0
                rate = stats["done"] / elapsed * 60 if elapsed > 0 else 0
                eta = (total - stats["done"]) / rate * 60 if rate > 0 else 0

                marker = {"ok": "✓", "skip": "⊘", "error": "✗"}.get(
                    result["status"], "?"
                )
                print(
                    f"[{stats['done']}/{total}] {marker} "
                    f"{result['key']}  {result['detail'][:60]}"
                    f"  ({rate:.1f}/min, ETA {eta/60:.1f}m)"
                )

    # ── summary ──
    elapsed_min = (time.time() - t0) / 60
    print(f"\n{'='*55}")
    print(f"Wiki Generation Report")
    print(f"{'='*55}")
    print(f"  Papers processed:   {stats['done']}")
    print(f"  Generated (OK):     {stats['ok']}")
    print(f"  Skipped:            {stats['skip']}")
    print(f"  Errors:             {stats['error']}")
    print(f"  Wall time:          {elapsed_min:.1f} min")
    print(f"  Throughput:         {stats['done']/elapsed_min:.1f} papers/min"
          if elapsed_min > 0 else "")
    print(f"{'='*55}")


if __name__ == "__main__":
    main()
