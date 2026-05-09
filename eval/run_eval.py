#!/usr/bin/env python3
"""paper-compass evaluation runner.

Usage:
    python3 eval/run_eval.py                        # run all queries
    python3 eval/run_eval.py --mode search_library  # filter by mode
    python3 eval/run_eval.py --verbose              # show per-query details
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any, Dict, List

import yaml

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "src"))

# Pre-load .env before importing miniresearch modules
from miniresearch.env_utils import load_project_env
load_project_env()


def load_queries(path: str = "eval/queries.yaml") -> List[Dict[str, Any]]:
    with open(PROJECT_ROOT / path, "r", encoding="utf-8") as f:
        data = yaml.safe_load(f)
    return data.get("queries", [])


def run_search_library(query: str, limit: int = 10) -> List[str]:
    from miniresearch.filters import search_library
    results = search_library(query, limit=limit)
    return [r["doc_id"] for r in results]


def run_search_passages(query: str, limit: int = 10) -> List[str]:
    from miniresearch.filters import search_passages
    results = search_passages(query, search_mode="keyword", limit=limit)
    seen = set()
    unique = []
    for r in results:
        did = r["doc_id"]
        if did and did not in seen:
            seen.add(did)
            unique.append(did)
    return unique


RUNNERS = {
    "search_library": run_search_library,
    "search_passages": run_search_passages,
}


def evaluate_query(q: Dict[str, Any]) -> Dict[str, Any]:
    mode = q.get("mode", "search_library")
    runner = RUNNERS.get(mode)
    if runner is None:
        return {"query": q["query"], "mode": mode, "error": f"Unknown mode: {mode}"}

    result_ids = runner(q["query"])
    expected = set(q.get("expected_keys", []))
    found = set(result_ids)
    hits = expected & found
    min_expected = q.get("min_expected", 1)
    tolerance = q.get("tolerance", "relaxed")

    if tolerance == "strict":
        passed = expected.issubset(found)
        reason = "all expected keys found" if passed else f"missing: {expected - found}"
    else:
        # relaxed: if expected_keys is provided, check hits; else check total count
        if expected:
            passed = len(hits) >= min_expected
            reason = f"{len(hits)}/{len(expected)} expected found (min={min_expected})"
        else:
            passed = len(found) >= min_expected
            reason = f"{len(found)} total results (min={min_expected})"

    return {
        "query": q["query"],
        "mode": mode,
        "passed": passed,
        "hits": sorted(hits),
        "expected": sorted(expected),
        "found": result_ids[:10],
        "reason": reason,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="paper-compass evaluation runner")
    parser.add_argument("--mode", help="Filter queries by mode")
    parser.add_argument("--verbose", "-v", action="store_true", help="Show per-query details")
    args = parser.parse_args()

    queries = load_queries()
    if args.mode:
        queries = [q for q in queries if q.get("mode") == args.mode]

    if not queries:
        print("No queries to evaluate.")
        return 0

    results = []
    for q in queries:
        result = evaluate_query(q)
        results.append(result)
        if args.verbose:
            status = "✓" if result["passed"] else "✗"
            print(f"  {status} {result['query'][:60]}")
            print(f"      mode={result['mode']}, {result['reason']}")
            if result["found"]:
                print(f"      top-3: {result['found'][:3]}")
            print()

    passed = sum(1 for r in results if r["passed"])
    total = len(results)

    print(f"\n{'='*50}")
    print(f"Evaluation: {passed}/{total} passed ({passed/total*100:.0f}%)")
    print(f"{'='*50}")

    # Show failures
    failures = [r for r in results if not r["passed"]]
    if failures:
        print(f"\nFailures ({len(failures)}):")
        for r in failures:
            print(f"  ✗ [{r['mode']}] {r['query'][:60]}: {r['reason']}")

    return 0 if passed == total else 1


if __name__ == "__main__":
    sys.exit(main())
