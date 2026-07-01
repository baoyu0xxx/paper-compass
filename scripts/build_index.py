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

from paper_compass.config import resolve_embedding_runtime, resolve_indexing_settings
from paper_compass.embedder import Embedder
from paper_compass.env_utils import load_project_env
from paper_compass.index_health import inspect_index_health
from paper_compass.index_manifest import (
    build_paper_fingerprint,
    compute_text_sha1,
    diff_manifest,
    explain_fingerprint_diff,
    load_manifest,
    save_manifest,
    stable_json_sha256,
    utc_now_iso,
)
from paper_compass.index_planner import plan_paper_index
from paper_compass.pipeline_sync import write_standalone_stage_state
from paper_compass.vector_store import VectorStore


PAPER_CHUNK_SIZE = 1500
PAPER_CHUNK_OVERLAP = 200
PAPER_TEXT_TRUNCATE = 2000
PAPER_CHUNKING_VERSION = f"papers_v1_cs{PAPER_CHUNK_SIZE}_ol{PAPER_CHUNK_OVERLAP}_trunc{PAPER_TEXT_TRUNCATE}"
LARGE_INCREMENTAL_CHANGE_RATIO = 0.30
LARGE_INCREMENTAL_CHANGE_MINIMUM = 3

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


def _load_wiki_page_content(md_file: Path) -> str:
    try:
        return md_file.read_text(encoding="utf-8")
    except Exception:
        return ""


def _build_wiki_page_fingerprint(md_file: Path, wiki_root: Path) -> Dict[str, Any]:
    content = _load_wiki_page_content(md_file)
    body = _strip_yaml_frontmatter(content)
    rel_page_id = md_file.relative_to(wiki_root).as_posix()
    section_count = sum(1 for _ in _iter_wiki_sections(md_file, wiki_root))
    stat = md_file.stat()
    payload = {
        "page_path": rel_page_id,
        "text_sha1": compute_text_sha1(body),
        "section_count": section_count,
        "page_type": _get_wiki_page_type(md_file, wiki_root),
    }
    return {
        "schema_version": 1,
        "page_path": rel_page_id,
        "page_type": payload["page_type"],
        "source": {
            "path": str(md_file),
            "mtime": int(stat.st_mtime),
            "size": stat.st_size,
            "text_sha1": payload["text_sha1"],
        },
        "indexing": {
            "section_count": section_count,
            "content_fingerprint": stable_json_sha256(payload),
        },
        "updated_at": utc_now_iso(),
    }


def _wiki_content_fingerprint(data: Dict[str, Any]) -> str:
    indexing = data.get("indexing") if isinstance(data.get("indexing"), dict) else {}
    return str(indexing.get("content_fingerprint", ""))


def _init_embedder() -> Embedder:
    """Initialize embedder from the unified embedding runtime resolver."""
    load_project_env()
    runtime = resolve_embedding_runtime()

    embedder = Embedder()
    resolved_cloud = runtime.get("resolved_cloud_config")
    local_model_id = runtime.get("local_fallback_model", "bge-base")

    if resolved_cloud:
        provider_name = resolved_cloud.get("provider", "openai")
        embedder.configure_cloud(
            provider=provider_name,
            base_url=resolved_cloud.get("base_url", ""),
            api_key=resolved_cloud.get("api_key", ""),
            model=resolved_cloud.get("model", ""),
            dimension=int(resolved_cloud.get("dimension", 1536)),
        )
        print(
            "  Embedding: cloud "
            f"({runtime.get('resolved_provider')}, {provider_name}, dim={embedder.dimension})"
        )
        return embedder

    embedder.configure_local(local_model_id)
    print(f"  Embedding: local ({local_model_id}, dim={embedder.dimension})")
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
            _paper_chunk_metadata(item),
        )
        chunk_idx += 1


def _paper_chunk_metadata(item: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "item_key": item.get("key", ""),
        "title": item.get("title", ""),
        "year": item.get("year") or 0,
        "authors": ", ".join(item.get("authors", [])),
        "collections": ", ".join(item.get("collections", [])),
        "tags": ", ".join(item.get("tags", [])),
    }


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


def _resolve_failure_report_path(args) -> Path:
    text_dir = Path(args.text_dir)
    log_root = text_dir.parent if text_dir.name.lower() == "texts" else text_dir
    return log_root / "logs" / "pdf_extract_failures.jsonl"


def _append_failure_report(report_path: Path, *, stage: str, key: str, pdf_path: str, reason: str, exception: str = "") -> None:
    report_path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "stage": stage,
        "key": key,
        "pdf_path": pdf_path,
        "reason": reason,
        "timestamp": utc_now_iso(),
    }
    if exception:
        payload["exception"] = exception
    with report_path.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(payload, ensure_ascii=False) + "\n")


def _prepare_index_inputs(items: List[Dict[str, Any]], args, embedder_model_id: str) -> tuple[Dict[str, Dict[str, Any]], Dict[str, str], List[str], Dict[str, Any]]:
    fingerprints: Dict[str, Dict[str, Any]] = {}
    full_texts: Dict[str, str] = {}
    skipped: List[str] = []
    failure_counts: Dict[str, int] = {}
    report_path = _resolve_failure_report_path(args)

    def record_failure(*, key: str, pdf_path: str, reason: str, exception: str = "") -> None:
        skipped.append(f"{key}: {reason}")
        failure_counts[reason] = failure_counts.get(reason, 0) + 1
        if not _get_bool_arg(args, "dry_run"):
            _append_failure_report(
                report_path,
                stage="build_index",
                key=key,
                pdf_path=pdf_path,
                reason=reason,
                exception=exception,
            )

    for item in items:
        key = item.get("key", "")
        pdf_path = item.get("pdf_path", "")
        if not key:
            skipped.append("missing key")
            continue

        # Allow indexing from text_file alone (no PDF required).
        # PDF is only needed for on-the-fly extraction when text_file is missing.
        text_file = item.get("text_file", "")
        has_text = text_file and Path(text_file).exists()
        has_pdf = pdf_path and Path(pdf_path).exists()

        if not has_text and not has_pdf:
            record_failure(key=key, pdf_path=pdf_path, reason="missing text file and PDF")
            continue

        try:
            full_text = _load_paper_text(item, extract_text=args.extract_text)
        except Exception as exc:
            record_failure(key=key, pdf_path=pdf_path, reason="extract error", exception=str(exc))
            continue
        if not full_text.strip():
            record_failure(key=key, pdf_path=pdf_path, reason="missing text")
            continue

        chunk_count = sum(1 for _ in _iter_paper_chunks(full_text, item))
        if chunk_count == 0:
            record_failure(key=key, pdf_path=pdf_path, reason="no valid chunks")
            continue

        full_texts[key] = full_text
        fingerprints[key] = build_paper_fingerprint(
            item=item,
            full_text=full_text,
            chunking_version=PAPER_CHUNKING_VERSION,
            embedding_model_id=embedder_model_id,
            chunk_count=chunk_count,
        )

    return fingerprints, full_texts, skipped, {
        "counts": failure_counts,
        "report_path": str(report_path) if failure_counts else "",
    }


def _get_bool_arg(args: Any, name: str, default: bool = False) -> bool:
    return bool(getattr(args, name, default))


def _large_incremental_keys(
    new_keys: list[str],
    changed_keys: list[str],
    current_count: int,
    *,
    minimum: int = LARGE_INCREMENTAL_CHANGE_MINIMUM,
    ratio: float = LARGE_INCREMENTAL_CHANGE_RATIO,
) -> list[str]:
    if current_count == 0:
        return []
    risky = sorted(set(new_keys) | set(changed_keys))
    if len(risky) < minimum:
        return []
    if len(risky) / current_count < ratio:
        return []
    return risky


def _abort_large_incremental(risky_keys: list[str], current_count: int) -> None:
    print("ERROR: incremental paper index would rewrite a large share of the library.")
    print(f"Detected: {len(risky_keys)}/{current_count} papers require fresh embeddings.")
    print("This may indicate manifest drift or a near-full rebuild under --incremental.")
    print("Use --allow-large-incremental only after reviewing the diff, or run an explicit full rebuild.")
    print(f"Sample keys: {', '.join(risky_keys[:10])}")
    sys.exit(3)


def _print_paper_index_plan(summary: Dict[str, Any], process_keys: list[str]) -> None:
    print()
    print("── Paper Index Plan ──")
    print(f"  New papers:                 {summary['new']}")
    print(f"  Content changed:            {summary['content_changed']}")
    print(f"  Metadata-only changed:      {summary['metadata_only']}")
    print(f"  Path-only changed:          {summary['path_only']}")
    print(f"  Missing vectors to repair:  {summary['missing_vectors']}")
    print(f"  Deleted papers:             {summary['deleted']}")
    print(f"  Embedding-required papers:  {summary['embedding_required']}")
    print(f"  Estimated chunks to embed:  {summary['estimated_chunks_to_embed']}")
    print(f"  Skipped papers:             {summary['skipped']}")
    print(f"  Manifest:                   {summary['manifest_path']}")
    if process_keys:
        print(f"  Sample embedding keys:      {', '.join(process_keys[:10])}")
    reason_counts = summary.get("metadata_reason_counts") or {}
    if reason_counts:
        print()
        print("  Top metadata-only reasons:")
        for reason, count in sorted(reason_counts.items(), key=lambda item: (-item[1], item[0])):
            print(f"    {reason}: {count}")
    samples = summary.get("metadata_reason_samples") or []
    if samples:
        print()
        print("  Sample metadata-only diffs:")
        for sample in samples:
            print(f"    {sample['key']}")
            for reason in sample.get("reasons", []):
                print(f"      {reason}")


def _store_item_keys_or_abort(store: Any) -> set[str]:
    try:
        return set(store.get_indexed_item_keys())
    except Exception as exc:
        print("ERROR: unable to inspect existing vector-store item keys before incremental indexing.")
        print(f"Detected: {exc}")
        print("Recommended action: inspect healthcheck output, then rebuild papers with a vectordb backup if needed.")
        sys.exit(2)


def _validate_processed_keys_present(store: Any, process_keys: list[str]) -> None:
    if not process_keys:
        return
    try:
        indexed_keys = set(store.get_indexed_item_keys())
    except Exception as exc:
        print("ERROR: unable to verify vector-store state after indexing.")
        print(f"Detected: {exc}")
        sys.exit(2)

    missing = sorted(set(process_keys) - indexed_keys)
    if missing:
        print("ERROR: vector-store verification failed after indexing.")
        print(f"Missing item keys after write: {', '.join(missing[:10])}")
        print("Manifest was not saved as complete; rerun after inspecting/rebuilding vectordb.")
        sys.exit(2)


def index_papers(args, embedder: Any | None = None, store: VectorStore | None = None) -> Dict[str, Any]:
    """Index PDF text chunks into ChromaDB with incremental support."""
    library_path = Path(args.library)
    if not library_path.exists():
        print(f"ERROR: library.json not found: {library_path}")
        print("Run sync_zotero.py --extract-text first.")
        sys.exit(1)

    health = inspect_index_health(args.db_path)
    if health.severity in {"warning", "corrupted"}:
        can_incrementally_repair = (
            args.incremental
            and health.severity == "warning"
            and (getattr(health, "manifest_only_keys", {}) or getattr(health, "store_only_keys", {}))
            and not (health.has_journal or health.has_wal or health.has_shm)
        )
        if not can_incrementally_repair:
            label = "corrupted state" if health.severity == "corrupted" else "requires attention"
            print(f"ERROR: vectordb {label}: {args.db_path}")
            print(f"Detected: {health.summary}")
            print(f"Recommended action: {health.recommended_action}")
            sys.exit(2)
        print(f"WARNING: vectordb manifest/store mismatch will be repaired incrementally: {health.summary}")

    items = json.loads(library_path.read_text(encoding="utf-8"))

    embedder = embedder or _init_embedder()
    store = store or VectorStore(
        db_path=args.db_path,
        collection_name="papers",
        embedding_model_id=embedder.model_id,
    )
    manifest_path = _resolve_manifest_path(args, store)

    dry_run = _get_bool_arg(args, "dry_run")
    if args.full_rebuild:
        if not dry_run:
            store.clear()
        manifest = {
            "collection_name": store.collection_name,
            "embedding_model_id": embedder.model_id,
            "chunking_version": PAPER_CHUNKING_VERSION,
            "schema_version": 2,
            "items": {},
        }
    else:
        manifest = load_manifest(manifest_path)
        manifest["collection_name"] = store.collection_name
        manifest["embedding_model_id"] = embedder.model_id
        manifest["chunking_version"] = PAPER_CHUNKING_VERSION
        manifest["schema_version"] = 2
        manifest.setdefault("items", {})

    current_items, full_texts, skipped, failure_report = _prepare_index_inputs(items, args, embedder.model_id)
    manifest_items = manifest.get("items", {})
    missing_vector_keys: list[str] = []
    orphan_vector_keys: list[str] = []
    metadata_only_keys: list[str] = []
    path_only_keys: list[str] = []

    if args.full_rebuild:
        process_keys = sorted(current_items.keys())
        changed_keys: List[str] = []
        deleted_keys: List[str] = []
        unchanged_keys: List[str] = []
        new_keys = process_keys
        repair_keys: list[str] = []
        orphan_delete_keys: list[str] = []
    elif args.incremental:
        store_item_keys = _store_item_keys_or_abort(store)
        plan = plan_paper_index(
            current_items,
            manifest_items,
            store_item_keys,
            prune_deleted=args.prune_deleted,
        )
        new_keys = plan.new
        changed_keys = plan.content_changed
        metadata_only_keys = plan.metadata_only
        path_only_keys = plan.path_only
        missing_vector_keys = plan.missing_in_store
        orphan_vector_keys = plan.orphan_in_store
        repair_keys = sorted(set(changed_keys) | set(missing_vector_keys))
        process_keys = plan.process_keys
        deleted_keys = plan.deleted if args.prune_deleted else []
        orphan_delete_keys = orphan_vector_keys if args.prune_deleted else []
        unchanged_keys = plan.unchanged
        indexing_settings = resolve_indexing_settings()
        risky = _large_incremental_keys(
            new_keys,
            sorted(set(changed_keys) | set(missing_vector_keys)),
            len(current_items),
            minimum=indexing_settings.large_incremental_change_minimum,
            ratio=indexing_settings.large_incremental_change_ratio,
        )
        if (
            manifest_items
            and risky
            and indexing_settings.require_dry_run_for_large_incremental
            and not _get_bool_arg(args, "allow_large_incremental")
        ):
            _abort_large_incremental(risky, len(current_items))
    else:
        diff = diff_manifest(current_items, manifest_items)
        process_keys = sorted(current_items.keys())
        changed_keys = sorted(set(diff["changed"]) | set(diff["unchanged"]))
        deleted_keys = []
        unchanged_keys = []
        new_keys = diff["new"]
        repair_keys = changed_keys
        orphan_delete_keys = []

    metadata_reason_counts: Dict[str, int] = {}
    metadata_reason_samples: List[Dict[str, Any]] = []
    if metadata_only_keys:
        sample_size = max(0, int(getattr(args, "sample_size", 5) or 0))
        include_samples = _get_bool_arg(args, "explain_changes") and sample_size > 0
        for key in metadata_only_keys:
            explanation = explain_fingerprint_diff(current_items[key], manifest_items[key])
            for reason in explanation["reasons"]:
                metadata_reason_counts[reason] = metadata_reason_counts.get(reason, 0) + 1
            if include_samples and len(metadata_reason_samples) < sample_size:
                metadata_reason_samples.append({
                    "key": key,
                    "reasons": explanation["reasons"],
                    "details": explanation["details"],
                })

    summary = {
        "dry_run": dry_run,
        "new": len(new_keys),
        "changed": len(changed_keys),
        "content_changed": len(changed_keys),
        "metadata_only": len(metadata_only_keys),
        "path_only": len(path_only_keys),
        "unchanged": len(unchanged_keys),
        "deleted": len(set(deleted_keys) | set(orphan_delete_keys)),
        "missing_vectors": len(missing_vector_keys),
        "orphan_vectors": len(orphan_vector_keys),
        "embedding_required": len(process_keys),
        "estimated_chunks_to_embed": sum(current_items[key].get("indexing", {}).get("chunk_count") or 0 for key in process_keys),
        "skipped": len(skipped),
        "indexed_papers": 0,
        "indexed_chunks": 0,
        "metadata_updated_chunks": 0,
        "deleted_chunks": 0,
        "manifest_path": manifest_path,
        "collection": store.collection_name,
        "metadata_reason_counts": metadata_reason_counts,
        "metadata_reason_samples": metadata_reason_samples,
        "failure_reason_counts": failure_report["counts"],
        "failure_report_path": failure_report["report_path"],
    }

    if dry_run:
        _print_paper_index_plan(summary, process_keys)
        return summary

    if args.prune_deleted:
        for key in sorted(set(deleted_keys) | set(orphan_delete_keys)):
            deleted = store.delete_item(key)
            summary["deleted_chunks"] += deleted
            manifest["items"].pop(key, None)

    item_by_key = {item.get("key"): item for item in items}
    for key in sorted(set(metadata_only_keys) | set(path_only_keys)):
        manifest["items"][key] = current_items[key]
        if key in metadata_only_keys:
            updated = store.update_item_metadata(key, _paper_chunk_metadata(item_by_key[key]))
            summary["metadata_updated_chunks"] += updated

    for key in process_keys:
        item = item_by_key[key]
        full_text = full_texts[key]
        if args.full_rebuild or key in repair_keys:
            summary["deleted_chunks"] += store.delete_item(key)

        chunk_count = _index_single_paper(store, embedder, item, full_text)
        if chunk_count == 0:
            continue
        summary["indexed_papers"] += 1
        summary["indexed_chunks"] += chunk_count
        manifest["items"][key] = current_items[key]

    _validate_processed_keys_present(store, process_keys)

    if args.full_rebuild:
        manifest["items"] = {key: current_items[key] for key in process_keys}

    save_manifest(manifest_path, manifest)
    bm25_result = store.build_bm25(force=True)

    print()
    print("── Paper Index Summary ──")
    print(f"  New papers:            {summary['new']}")
    print(f"  Changed papers:        {summary['changed']}")
    print(f"  Unchanged papers:      {summary['unchanged']}")
    print(f"  Missing vectors fixed: {summary['missing_vectors']}")
    print(f"  Orphan vectors found:  {summary['orphan_vectors']}")
    print(f"  Deleted papers pruned: {summary['deleted']}")
    print(f"  Skipped papers:        {summary['skipped']}")
    print(f"  Indexed papers:        {summary['indexed_papers']}")
    print(f"  Indexed chunks:        {summary['indexed_chunks']}")
    print(f"  Deleted chunks:        {summary['deleted_chunks']}")
    bm25_available = getattr(bm25_result, "available", None)
    if bm25_available is True:
        print(f"  BM25:                  OK ({bm25_result.indexed_documents} documents)")
    elif bm25_available is False:
        print(f"  BM25:                  WARN ({bm25_result.reason}; semantic search still available)")
    else:
        print("  BM25:                  OK (status unavailable from store backend)")
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
    manifest_path = _resolve_manifest_path(args, store)
    manifest = load_manifest(manifest_path)
    manifest_items = manifest.get("items", {})
    dry_run = _get_bool_arg(args, "dry_run")

    batch_size = 32
    chunk_ids: List[str] = []
    chunk_texts: List[str] = []
    chunk_metas: List[Dict[str, Any]] = []
    excluded_count = 0
    current_items: Dict[str, Dict[str, Any]] = {}
    page_files: Dict[str, Path] = {}

    for md_file in sorted(wiki_root.rglob("*.md")):
        if md_file.name.startswith("."):
            continue
        if not _should_index_wiki_page(md_file, wiki_root):
            excluded_count += 1
            continue
        rel_page_id = md_file.relative_to(wiki_root).as_posix()
        page_files[rel_page_id] = md_file
        current_items[rel_page_id] = _build_wiki_page_fingerprint(md_file, wiki_root)

    new_pages = sorted(set(current_items) - set(manifest_items))
    deleted_pages = sorted(set(manifest_items) - set(current_items))
    changed_pages = sorted(
        key
        for key in (set(current_items) & set(manifest_items))
        if _wiki_content_fingerprint(current_items[key]) != _wiki_content_fingerprint(manifest_items[key])
    )
    unchanged_pages = sorted(
        key
        for key in (set(current_items) & set(manifest_items))
        if _wiki_content_fingerprint(current_items[key]) == _wiki_content_fingerprint(manifest_items[key])
    )
    process_pages = sorted(set(new_pages) | set(changed_pages))

    summary = {
        "indexed_sections": 0,
        "deleted_sections": 0,
        "new_pages": len(new_pages),
        "changed_pages": len(changed_pages),
        "unchanged_pages": len(unchanged_pages),
        "deleted_pages": len(deleted_pages),
        "manifest_path": manifest_path,
        "collection": store.collection_name,
    }

    if dry_run:
        estimated_sections = sum(current_items[key].get("indexing", {}).get("section_count", 0) for key in process_pages)
        print()
        print("── Wiki Index Plan ──")
        print(f"  New pages:             {summary['new_pages']}")
        print(f"  Changed pages:         {summary['changed_pages']}")
        print(f"  Unchanged pages:       {summary['unchanged_pages']}")
        print(f"  Deleted pages:         {summary['deleted_pages']}")
        print(f"  Sections to index:     {estimated_sections}")
        print(f"  Manifest:              {manifest_path}")
        return summary

    for rel_page_id in deleted_pages:
        source_path = manifest_items.get(rel_page_id, {}).get("source", {}).get("path", str(wiki_root / rel_page_id))
        summary["deleted_sections"] += store.delete_by_page_path(source_path)
        manifest_items.pop(rel_page_id, None)

    for rel_page_id in process_pages:
        md_file = page_files[rel_page_id]
        if rel_page_id in changed_pages:
            summary["deleted_sections"] += store.delete_by_page_path(str(md_file))
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
    summary["indexed_sections"] = pages_indexed

    for rel_page_id in process_pages:
        manifest_items[rel_page_id] = current_items[rel_page_id]

    manifest.update(
        {
            "collection_name": store.collection_name,
            "embedding_model_id": embedder.model_id,
            "chunking_version": "wiki_v1_sections",
            "items": manifest_items,
        }
    )
    save_manifest(manifest_path, manifest)

    bm25_result = store.build_bm25(force=True)
    print()
    print("── Wiki Index Summary ──")
    print(f"  Wiki sections indexed: {pages_indexed}")
    print(f"  Deleted wiki sections: {summary['deleted_sections']}")
    print(f"  New pages:             {summary['new_pages']}")
    print(f"  Changed pages:         {summary['changed_pages']}")
    print(f"  Unchanged pages:       {summary['unchanged_pages']}")
    print(f"  Deleted pages:         {summary['deleted_pages']}")
    if excluded_count:
        print(f"  Excluded files:         {excluded_count} (log.md, index.md, non-knowledge dirs)")
    bm25_available = getattr(bm25_result, "available", None)
    if bm25_available is True:
        print(f"  BM25:                  OK ({bm25_result.indexed_documents} documents)")
    elif bm25_available is False:
        print(f"  BM25:                  WARN ({bm25_result.reason}; semantic search still available)")
    else:
        print("  BM25:                  OK (status unavailable from store backend)")
    print(f"  Manifest:              {manifest_path}")
    print(f"  Collection:            {store.collection_name} ({store.count()} vectors)")
    return summary


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
    parser.add_argument(
        "--allow-large-incremental",
        action="store_true",
        help="Allow incremental runs that would rewrite a large share of papers",
    )
    parser.add_argument("--manifest-path", default="", help="Optional override for the incremental manifest path")
    parser.add_argument("--dry-run", action="store_true", help="Plan paper index changes without embedding or writing")
    parser.add_argument("--explain-changes", action="store_true", help="Show metadata-only change reasons during dry-run")
    parser.add_argument("--sample-size", type=int, default=5, help="Max metadata-only samples to show in dry-run explanations")
    return parser


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()
    project_root = Path(__file__).resolve().parent.parent

    if args.incremental and args.full_rebuild:
        parser.error("--incremental and --full-rebuild cannot be used together")
    if args.wiki and (args.incremental or args.full_rebuild or args.prune_deleted or args.extract_text or args.allow_large_incremental):
        print("WARNING: paper-only flags are ignored in --wiki mode")

    stage_name = "index_wiki" if args.wiki else "index_papers"
    try:
        if args.wiki:
            index_wiki(args)
        else:
            index_papers(args)
        write_standalone_stage_state(project_root, stage=stage_name, status="dry_run" if args.dry_run else "ok", dry_run=bool(args.dry_run))
    except Exception as exc:
        write_standalone_stage_state(project_root, stage=stage_name, status="failed", error=str(exc))
        raise


if __name__ == "__main__":
    main()
