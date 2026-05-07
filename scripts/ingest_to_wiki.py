#!/usr/bin/env python3
"""
Manual wiki ingest CLI for paper-compass.

Write curated research results into the local markdown wiki.

Usage:
    python scripts/ingest_to_wiki.py \\
        --title "DID Identification" \\
        --content "Key findings..." \\
        --type queries \\
        [--source wiki/topics/did.md] \\
        [--tag did] \\
        [--confidence medium] \\
        [--wiki-root ./wiki]
"""

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from miniresearch.wiki_ingest import save_query_to_wiki


def main():
    parser = argparse.ArgumentParser(
        description="Ingest curated content into paper-compass wiki"
    )
    parser.add_argument("--title", required=True, help="Page title")
    parser.add_argument("--content", required=True, help="Markdown content")
    parser.add_argument(
        "--type",
        dest="target_type",
        default="queries",
        choices=["queries", "topics", "methods", "comparisons"],
        help="Page type (default: queries)",
    )
    parser.add_argument(
        "--source",
        action="append",
        dest="sources",
        default=[],
        help="Source reference (can repeat)",
    )
    parser.add_argument(
        "--tag",
        action="append",
        dest="tags",
        default=[],
        help="Tag (can repeat)",
    )
    parser.add_argument(
        "--confidence",
        default="medium",
        choices=["high", "medium", "low"],
        help="Confidence level (default: medium)",
    )
    parser.add_argument(
        "--wiki-root",
        default="./wiki",
        help="Wiki root directory (default: ./wiki)",
    )

    args = parser.parse_args()

    if not args.target_type:
        args.target_type = "queries"

    result = save_query_to_wiki(
        title=args.title,
        content=args.content,
        target_type=args.target_type,
        source_refs=args.sources,
        confidence=args.confidence,
        tags=args.tags,
        wiki_root=args.wiki_root,
    )

    print(f"Page created: {result['page_path']}")
    print(f"Index updated: {result['index_updated']}")
    print(f"Log updated:   {result['log_updated']}")
    print(f"Linked pages:  {result['linked_pages']}")


if __name__ == "__main__":
    main()
