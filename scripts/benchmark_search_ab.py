#!/usr/bin/env python3
"""A/B benchmark for MCP search hot paths.

A reproduces the pre-cache implementation; B calls the current cached helpers.
The benchmark intentionally excludes Chroma/network embeddings and measures the
file-backed paths changed in the MCP optimization.
"""
from __future__ import annotations

import argparse
import json
import re
import statistics
import tempfile
import time
import tracemalloc
from pathlib import Path
from typing import Callable

from paper_compass import search
from paper_compass.tokenization import tokenize_for_sparse_search


def _baseline_load_library(path: str) -> list[dict]:
    with open(path, "r", encoding="utf-8") as fh:
        return json.load(fh)


def _baseline_keyword_search(query: str, text_dir: str, limit: int = 20) -> list[dict]:
    keywords = tokenize_for_sparse_search(query)
    scored: list[tuple] = []
    for txt_path in Path(text_dir).glob("*.txt"):
        try:
            text = txt_path.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        paragraphs = re.split(r"\n\s*\n", text)
        paragraph_index = 0
        for para in paragraphs:
            para = para.strip()
            if len(para) < 30:
                continue
            tokens = set(tokenize_for_sparse_search(para))
            hits = sum(1 for kw in keywords if kw in tokens or kw in para.lower())
            if hits:
                scored.append((hits / max(len(para), 1) * 100 + hits, txt_path.stem, para[:800], paragraph_index))
            paragraph_index += 1
    scored.sort(key=lambda row: row[0], reverse=True)
    return [{"doc_id": row[1], "passage": row[2], "score": row[0], "paragraph_index": row[3]} for row in scored[:limit]]


def _make_fixture(root: Path, files: int, paragraphs: int) -> tuple[Path, Path]:
    text_dir = root / "texts"
    text_dir.mkdir()
    records = []
    paragraph = (
        "This paper studies family firm succession and labor structure using a "
        "large panel of listed firms. The empirical results examine employment "
        "composition, productivity, and economic development."
    )
    for idx in range(files):
        key = f"ITEM{idx:05d}"
        records.append({"key": key, "title": f"Family firm paper {idx}", "year": 2020 + idx % 5, "authors": ["Author"]})
        (text_dir / f"{key}.txt").write_text("\n\n".join([paragraph] * paragraphs), encoding="utf-8")
    library = root / "library.json"
    library.write_text(json.dumps(records), encoding="utf-8")
    return library, text_dir


def _measure(fn: Callable[[], object], repeats: int) -> dict[str, float]:
    times = []
    peaks = []
    for _ in range(repeats):
        tracemalloc.start()
        started = time.perf_counter()
        value = fn()
        elapsed = (time.perf_counter() - started) * 1000
        _, peak = tracemalloc.get_traced_memory()
        tracemalloc.stop()
        times.append(elapsed)
        peaks.append(peak / 1024 / 1024)
    return {
        "median_ms": statistics.median(times),
        "p95_ms": sorted(times)[max(0, int(len(times) * 0.95) - 1)],
        "peak_mib_median": statistics.median(peaks),
        "result_count": len(value),
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--files", type=int, default=200)
    parser.add_argument("--paragraphs", type=int, default=8)
    parser.add_argument("--repeats", type=int, default=8)
    args = parser.parse_args()

    with tempfile.TemporaryDirectory(prefix="paper-compass-ab-") as tmp:
        library, text_dir = _make_fixture(Path(tmp), args.files, args.paragraphs)
        query = "family firm succession labor structure"

        baseline_library = _measure(lambda: _baseline_load_library(str(library)), args.repeats)
        search._library_cache.clear()
        optimized_library = _measure(lambda: search._load_library(str(library)), args.repeats)

        baseline_keyword = _measure(lambda: _baseline_keyword_search(query, str(text_dir)), args.repeats)
        search._keyword_cache.clear()
        # Warm-cache behavior is the MCP resident-process case.
        search._keyword_search_passages(query, str(text_dir))
        optimized_keyword = _measure(lambda: search._keyword_search_passages(query, str(text_dir)), args.repeats)

        payload = {
            "fixture": {"files": args.files, "paragraphs_per_file": args.paragraphs, "repeats": args.repeats},
            "baseline": {"library_load": baseline_library, "keyword_search": baseline_keyword},
            "optimized": {"library_load": optimized_library, "keyword_search_warm": optimized_keyword},
        }
        for key in ("library_load", "keyword_search"):
            old = payload["baseline"][key]["median_ms"]
            new_key = "keyword_search_warm" if key == "keyword_search" else key
            new = payload["optimized"][new_key]["median_ms"]
            payload["optimized"][new_key]["speedup_x"] = old / new if new else None
        print(json.dumps(payload, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
