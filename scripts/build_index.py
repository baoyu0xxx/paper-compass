#!/usr/bin/env python3
"""
Build embeddings and vector index for paper-compass.

Usage:
    # Incremental paper indexing
    python scripts/build_index.py --library data/zotero-export/library.json --incremental

    # Full rebuild for papers
    python scripts/build_index.py --library data/zotero-export/library.json --full-rebuild

    # Index wiki pages idempotently
    python scripts/build_index.py --wiki --wiki-root ./wiki
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path
from typing import Any, Dict, Iterable, List, Tuple

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from paper_compass.config import get_provider_config, load_all_configs
from paper_compass.embedder import Embedder
from paper_compass.env_utils import load_project_env
from paper_compass.index_manifest import (
    build_paper_fingerprint,
    diff_manifest,
    load_manifest,
    save_manifest,
)
from paper_compass.vector_store import VectorStore


PAPER_CHUNK_SIZE = 1500
PAPER_CHUNK_OVERLAP = 200
PAPER_TEXT_TRUNCATE = 2000
PAPER_CHUNKING_VERSION = f"papers_v1_cs{PAPER_CHUNK_SIZE}_ol{PAPER_CHUNK_OVERLAP}_trunc{PAPER_TEXT_TRUNCATE}"

# Wiki indexing: allowed directories and excluded files
_ALLOWED_WIKI_DIRS = {"papers", "topics", "methods", "comparisons"}
_EXCLUDED_WIKI_FILES = {"log.md", "index.md"}


def _should_index_wiki_page(md_file: Path, wiki_root: Path) -> bool:
    """Determine whether a wiki markdown file should be included in the vector index.

    Excludes non-knowledge pages: log.md, index.md, and files outside
    the allowed subdirectories (papers, topics, methods, comparisons).
    """
    if md_file.name in _EXCLUDED_WIKI_FILES:
        return False
    try:
        rel = md_file.relative_to(wiki_root)
    except ValueError:
        return False
    # Must be inside one of the allowed directories
    if len(rel.parts) >= 2 and rel.parts[0] in _ALLOWED_WIKI_DIRS:
        return True
    return False


def _get_wiki_page_type(md_file: Path, wiki_root: Path) -> str:
    """Extract the wiki page type (e.g. 'papers', 'topics') from the relative path."""
    try:
        rel = md_file.relative_to(wiki_root)
        return rel.parts[0] if len(rel.parts) >= 2 else "unknown"
    except ValueError:
        return "unknown"


def _strip_yaml_frontmatter(content: str) -> str:
    """Strip YAML frontmatter from markdown content.

    Returns the body after the closing ---, stripped of leading/trailing whitespace.
    If no valid frontmatter is found, returns the original content.
    """
    stripped = content.lstrip()
    if stripped.startswith("---"):
        # Find the closing ---
        end = stripped.find("---", 3)
        if end != -1:
            return stripped[end + 3:].strip()
    return stripped


def _iter_wiki_sections(md_file: Path, wiki_root: Path) -> Iterable[Tuple[str, str, Dict[str, Any]]]:
    """Iterate over structured sections of a wiki markdown page.

    Yields (chunk_id, text, metadata) tuples for each section.
    Strips YAML frontmatter before chunking.
    """
    try:
        content = md_file.read_text(encoding="utf-8")
    except Exception:
        return

    body = _strip_yaml_frontmatter(content)
    if not body:
        return

    rel_page_id = md_file.relative_to(wiki_root).as_posix()
    page_type = _get_wiki_page_type(md_file, wiki_root)
    title = md_file.stem

    # Split by ## headings (markdown section headers)
    sections = body.split("\n## ")
    for i, section_text in enumerate(sections):
        text = section_text[:2000].strip()
        if not text:
            continue

        # Extract section heading from the first line of section 0 (which may
        # start with a single #), or from ## -headed sections.
        heading = ""
        if i == 0:
            # Section 0: usually starts with "# Title" from frontmatter-stripped content
            first_line = text.split("\n")[0] if "\n" in text else text
            if first_line.startswith("#"):
                heading = first_line.lstrip("#").strip()
        else:
            # Section N: text starts with the heading (since we split on "## ")
            heading = text.split("\n")[0] if "\n" in text else text

        # Build chunk ID with page-type prefix for collision safety
        chunk_dir_prefix = page_type
        chunk_id = f"{chunk_dir_prefix}__{md_file.stem}_s{i}"

        metadata = {
            "page_path": str(md_file),
            "page_type": page_type,
            "title": title,
            "section": i,
            "section_heading": heading,
        }

        yield chunk_id, text, metadata


def _init_embedder() -> Embedder:
    """Initialize embedder from project config + env.

    Tries providers in cascade: embedding_main → embedding_volcengine → local.
    """
    load_project_env()
    configs = load_all_configs("configs")

    embedder = Embedder()

    # Try configured providers in order
    for provider_key in ["embedding_main", "embedding_volcengine"]:
        try:
            provider_cfg = get_provider_config(provider_key, configs)
            base_url = provider_cfg.get("base_url", "")
            api_key = provider_cfg.get("api_key", "")
            if not base_url or not api_key:
                continue
            provider_name = provider_cfg.get("provider", "openai")
            embedder.configure_cloud(
                provider=provider_name,
                base_url=base_url,
                api_key=api_key,
                model=provider_cfg.get("model", ""),
                dimension=2048,
            )
            print(f"  Embedding: cloud ({provider_name}, dim={embedder.dimension})")
            return embedder
        except Exception:
            continue

    # Fallback to local
    embedder.configure_local("bge-base")
    print(f"  Embedding: local (bge-base, dim={embedder.dimension})")
    return embedder


def _default_manifest_path(db_path: str, collection_name: str) -> str:
    return str(Path(db_path) / f"{collection_name}.manifest.json")


def _resolve_manifest_path(args, store: VectorStore) -> str:
    if args.manifest_path:
        return args.manifest_path
    return _default_manifest_path(args.db_path, store.collection_name)


def _load_paper_text(item: Dict[str, Any], extract_text: bool = False) -> str:
    text_file = item.get("text_file", "")
    if text_file and Path(text_file).exists():
        return Path(text_file).read_text(encoding="utf-8")

    if extract_text:
        from paper_compass.pdf_extract import PDFExtractor

        pdf_path = item.get("pdf_path", "")
        if pdf_path and Path(pdf_path).exists():
            return PDFExtractor(pdf_path).extract_all_text()

    return ""


def _iter_paper_chunks(full_text: str, item: Dict[str, Any]) -> Iterable[Tuple[str, str, Dict[str, Any]]]:
    key = item.get("key", "")
    chunk_idx = 0
    step = PAPER_CHUNK_SIZE - PAPER_CHUNK_OVERLAP
    for pos in range(0, len(full_text), step):
        chunk_text = full_text[pos : pos + PAPER_CHUNK_SIZE].strip()
        if len(chunk_text) < 50:
            continue
        yield (
            f"{key}_c{chunk_idx}",
            chunk_text[:PAPER_TEXT_TRUNCATE],
            {
                "item_key": key,
                "title": item.get("title", ""),
                "year": item.get("year"),
                "authors": ", ".join(item.get("authors", [])),
                "collections": ", ".join(item.get("collections", [])),
                "tags": ", ".join(item.get("tags", [])),
            },
        )
        chunk_idx += 1


def _write_index_batches(
    store: VectorStore,
    embedder: Any,
    chunk_ids: List[str],
    chunk_texts: List[str],
    chunk_metas: List[Dict[str, Any]],
    *,
    write_mode: str,
    batch_size: int = 32,
    progress_every: int | None = None,
    progress_label: str = "Indexed chunks",
) -> int:
    """Embed chunk batches and write them to the vector store."""
    if not chunk_texts:
        return 0

    write_fn = store.upsert_chunks if write_mode == "upsert" else store.add_chunks
    total = len(chunk_texts)
    for start in range(0, total, batch_size):
        batch_ids = chunk_ids[start : start + batch_size]
        batch_texts = chunk_texts[start : start + batch_size]
        batch_metas = chunk_metas[start : start + batch_size]
        embeddings = embedder.embed(batch_texts)
        write_fn(batch_ids, batch_texts, batch_metas, embeddings)

        if progress_every:
            done = min(start + batch_size, total)
            if done % progress_every == 0 or done == total:
                print(f"  {progress_label}: {done}/{total}")

    return total


def _index_single_paper(store: VectorStore, embedder: Any, item: Dict[str, Any], full_text: str) -> int:
    chunk_ids: List[str] = []
    chunk_texts: List[str] = []
    chunk_metas: List[Dict[str, Any]] = []

    for chunk_id, chunk_text, chunk_meta in _iter_paper_chunks(full_text, item):
        chunk_ids.append(chunk_id)
        chunk_texts.append(chunk_text)
        chunk_metas.append(chunk_meta)

    return _write_index_batches(
        store,
        embedder,
        chunk_ids,
        chunk_texts,
        chunk_metas,
        write_mode="add",
    )


def _prepare_index_inputs(items: List[Dict[str, Any]], args, embedder_model_id: str) -> tuple[Dict[str, Dict[str, Any]], Dict[str, str], List[str]]:
    fingerprints: Dict[str, Dict[str, Any]] = {}
    full_texts: Dict[str, str] = {}
    skipped: List[str] = []

    for item in items:
        key = item.get("key", "")
        if not key:
            skipped.append("missing key")
            continue

        # Allow indexing from text_file alone (no PDF required).
        # PDF is only needed for on-the-fly extraction when text_file is missing.
        text_file = item.get("text_file", "")
        pdf_path = item.get("pdf_path", "")
        has_text = text_file and Path(text_file).exists()
        has_pdf = pdf_path and Path(pdf_path).exists()

        if not has_text and not has_pdf:
            skipped.append(f"{key}: missing text file and PDF")
            continue

        full_text = _load_paper_text(item, extract_text=args.extract_text)
        if not full_text.strip():
            skipped.append(f"{key}: missing text")
            continue

        chunk_count = sum(1 for _ in _iter_paper_chunks(full_text, item))
        if chunk_count == 0:
            skipped.append(f"{key}: no valid chunks")
            continue

        full_texts[key] = full_text
        fingerprints[key] = build_paper_fingerprint(
            item=item,
            full_text=full_text,
            chunking_version=PAPER_CHUNKING_VERSION,
            embedding_model_id=embedder_model_id,
            chunk_count=chunk_count,
        )

    return fingerprints, full_texts, skipped


def index_papers(args, embedder: Any | None = None, store: VectorStore | None = None) -> Dict[str, Any]:
    """Index PDF text chunks into ChromaDB with incremental support."""
    library_path = Path(args.library)
    if not library_path.exists():
        print(f"ERROR: library.json not found: {library_path}")
        print("Run sync_zotero.py --extract-text first.")
        sys.exit(1)

    items = json.loads(library_path.read_text(encoding="utf-8"))

    embedder = embedder or _init_embedder()
    store = store or VectorStore(
        db_path=args.db_path,
        collection_name="papers",
        embedding_model_id=embedder.model_id,
    )
    manifest_path = _resolve_manifest_path(args, store)

    if args.full_rebuild:
        store.clear()
        manifest = {
            "collection_name": store.collection_name,
            "embedding_model_id": embedder.model_id,
            "chunking_version": PAPER_CHUNKING_VERSION,
            "items": {},
        }
    else:
        manifest = load_manifest(manifest_path)
        manifest["collection_name"] = store.collection_name
        manifest["embedding_model_id"] = embedder.model_id
        manifest["chunking_version"] = PAPER_CHUNKING_VERSION
        manifest.setdefault("items", {})

    current_items, full_texts, skipped = _prepare_index_inputs(items, args, embedder.model_id)
    diff = diff_manifest(current_items, manifest.get("items", {}))

    if args.full_rebuild:
        process_keys = sorted(current_items.keys())
        changed_keys: List[str] = []
        deleted_keys: List[str] = []
        unchanged_keys: List[str] = []
        new_keys = process_keys
    elif args.incremental:
        process_keys = diff["new"] + diff["changed"]
        changed_keys = diff["changed"]
        deleted_keys = diff["deleted"] if args.prune_deleted else []
        unchanged_keys = diff["unchanged"]
        new_keys = diff["new"]
    else:
        process_keys = sorted(current_items.keys())
        changed_keys = sorted(set(diff["changed"]) | set(diff["unchanged"]))
        deleted_keys = []
        unchanged_keys = []
        new_keys = diff["new"]

    summary = {
        "new": len(new_keys),
        "changed": len(changed_keys),
        "unchanged": len(unchanged_keys),
        "deleted": len(deleted_keys),
        "skipped": len(skipped),
        "indexed_papers": 0,
        "indexed_chunks": 0,
        "deleted_chunks": 0,
        "manifest_path": manifest_path,
        "collection": store.collection_name,
    }

    if args.prune_deleted:
        for key in deleted_keys:
            deleted = store.delete_item(key)
            summary["deleted_chunks"] += deleted
            manifest["items"].pop(key, None)

    for key in process_keys:
        item = next(item for item in items if item.get("key") == key)
        full_text = full_texts[key]
        if args.full_rebuild or key in changed_keys:
            summary["deleted_chunks"] += store.delete_item(key)

        chunk_count = _index_single_paper(store, embedder, item, full_text)
        if chunk_count == 0:
            continue
        summary["indexed_papers"] += 1
        summary["indexed_chunks"] += chunk_count
        manifest["items"][key] = current_items[key]

    if args.full_rebuild:
        manifest["items"] = {key: current_items[key] for key in process_keys}

    save_manifest(manifest_path, manifest)
    store.build_bm25(force=True)

    print()
    print("── Paper Index Summary ──")
    print(f"  New papers:            {summary['new']}")
    print(f"  Changed papers:        {summary['changed']}")
    print(f"  Unchanged papers:      {summary['unchanged']}")
    print(f"  Deleted papers pruned: {summary['deleted']}")
    print(f"  Skipped papers:        {summary['skipped']}")
    print(f"  Indexed papers:        {summary['indexed_papers']}")
    print(f"  Indexed chunks:        {summary['indexed_chunks']}")
    print(f"  Deleted chunks:        {summary['deleted_chunks']}")
    print(f"  Manifest:              {manifest_path}")
    print(f"  Collection:            {store.collection_name} ({store.count()} vectors)")

    if skipped:
        print("  Skip samples:")
        for reason in skipped[:10]:
            print(f"    - {reason}")
        if len(skipped) > 10:
            print(f"    ... and {len(skipped) - 10} more")

    return summary


def index_wiki(args, embedder: Any | None = None, store: VectorStore | None = None) -> Dict[str, Any]:
    """Index wiki markdown pages into ChromaDB idempotently.

    Uses _should_index_wiki_page() to exclude non-knowledge pages (log.md,
    index.md, queries/), and _iter_wiki_sections() for frontmatter-stripped,
    structured chunking with rich metadata.
    """
    wiki_root = Path(args.wiki_root)
    if not wiki_root.exists():
        print(f"ERROR: Wiki root not found: {wiki_root}")
        sys.exit(1)

    embedder = embedder or _init_embedder()
    store = store or VectorStore(
        db_path=args.db_path,
        collection_name="wiki",
        embedding_model_id=embedder.model_id,
    )

    batch_size = 32
    chunk_ids: List[str] = []
    chunk_texts: List[str] = []
    chunk_metas: List[Dict[str, Any]] = []
    excluded_count = 0

    for md_file in sorted(wiki_root.rglob("*.md")):
        if md_file.name.startswith("."):
            continue
        if not _should_index_wiki_page(md_file, wiki_root):
            excluded_count += 1
            continue

        for chunk_id, text, metadata in _iter_wiki_sections(md_file, wiki_root):
            chunk_ids.append(chunk_id)
            chunk_texts.append(text)
            chunk_metas.append(metadata)

    pages_indexed = _write_index_batches(
        store,
        embedder,
        chunk_ids,
        chunk_texts,
        chunk_metas,
        write_mode="upsert",
        batch_size=batch_size,
        progress_every=320,
        progress_label="Indexed wiki sections",
    )

    store.build_bm25(force=True)
    print()
    print("── Wiki Index Summary ──")
    print(f"  Wiki sections indexed: {pages_indexed}")
    if excluded_count:
        print(f"  Excluded files:         {excluded_count} (log.md, index.md, non-knowledge dirs)")
    print(f"  Collection:            {store.collection_name} ({store.count()} vectors)")
    return {"indexed_sections": pages_indexed, "collection": store.collection_name}


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Build vector index for paper-compass")
    parser.add_argument("--library", default="data/zotero-export/library.json")
    parser.add_argument("--db-path", default="./data/vectordb")
    parser.add_argument("--text-dir", default="./data/texts")
    parser.add_argument("--extract-text", action="store_true")
    parser.add_argument("--wiki", action="store_true", help="Index wiki pages instead of papers")
    parser.add_argument("--wiki-root", default="./wiki")
    parser.add_argument("--incremental", action="store_true", help="Only index new or changed papers")
    parser.add_argument("--full-rebuild", action="store_true", help="Clear the paper collection and rebuild all paper vectors")
    parser.add_argument("--prune-deleted", action="store_true", help="Delete vectors for papers no longer present in library.json")
    parser.add_argument("--manifest-path", default="", help="Optional override for the incremental manifest path")
    return parser


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()

    if args.incremental and args.full_rebuild:
        parser.error("--incremental and --full-rebuild cannot be used together")
    if args.wiki and (args.incremental or args.full_rebuild or args.prune_deleted or args.extract_text):
        print("WARNING: paper-only flags are ignored in --wiki mode")

    if args.wiki:
        index_wiki(args)
    else:
        index_papers(args)


if __name__ == "__main__":
    main()
