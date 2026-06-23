# paper-compass v1.4.1 Release Notes

Date: 2026-06-23

## Summary

v1.4.1 focuses on incremental-sync hardening, wiki writeback collision handling, and operator-facing diagnostics.

## Highlights

### 1. Key-aware wiki writeback and slug conflict recovery

`scripts/ingest_to_wiki.py` and `src/paper_compass/wiki_store.py` now support safer wiki page upserts:

- `--wiki-upsert-mode create_unique`
- `--wiki-upsert-mode replace_if_same_key`
- `--wiki-upsert-mode replace_if_same_slug`

Recommended default for repeated ingestion is:

```bash
python scripts/ingest_to_wiki.py --skip-existing --wiki-upsert-mode create_unique
```

Behavior changes:

- same slug + different Zotero key no longer has to fail immediately
- same slug + different key can emit `YYYY-MM-DD-slug-key.md`
- same key pages can be replaced in place when explicitly requested
- duplicate slug pages record `duplicate_slug` / `conflict_paths` in frontmatter for later inspection

### 2. Explainable incremental dry-run

`scripts/build_index.py` now supports:

- `--explain-changes`
- `--sample-size N`

Example:

```bash
python scripts/build_index.py \
  --library data/zotero-export/library.json \
  --incremental \
  --dry-run \
  --explain-changes \
  --sample-size 5
```

Dry-run output now distinguishes:

- new papers
- content-changed papers
- metadata-only changes
- path-only changes
- missing vectors to repair

It also reports top metadata-only reasons, such as:

- `tags changed`
- `collections changed`
- `title changed`

Normalization was hardened so that:

- tag order drift no longer creates unnecessary metadata churn
- collection order drift no longer creates unnecessary metadata churn
- author order is still treated as meaningful metadata

### 3. Structured PDF extraction failure reporting

Both Zotero sync and paper indexing now emit structured failure reports to:

```text
data/logs/pdf_extract_failures.jsonl
```

Typical reasons include:

- `empty text`
- `extract error`
- `missing text`
- `no valid chunks`
- `missing text file and PDF`

This makes recovery easier after partial or noisy runs.

## Recovery guidance

### If `paper-compass sync --dry-run` shows unexpectedly large metadata churn

1. rerun with local explanation only:

```bash
python scripts/build_index.py \
  --library data/zotero-export/library.json \
  --incremental \
  --dry-run \
  --explain-changes \
  --sample-size 10
```

2. inspect top reasons before allowing any embedding-heavy run
3. if the change is mostly metadata-only, do **not** assume it requires a full rebuild

### If wiki generation hits title collisions

Prefer:

```bash
python scripts/ingest_to_wiki.py --skip-existing --wiki-upsert-mode create_unique
```

If you need to replace the same paper's existing page:

```bash
python scripts/ingest_to_wiki.py --wiki-upsert-mode replace_if_same_key
```

### If PDF extraction partially fails

Check:

```bash
cat data/logs/pdf_extract_failures.jsonl
```

Use the recorded `key`, `pdf_path`, and `reason` to decide whether to:

- restore a missing PDF
- regenerate text extraction
- rebuild only the affected paper set

### If sync state looks stuck

Use:

```bash
paper-compass status --json
paper-compass sync --force-unlock
```

`paper-compass status` now exposes sync lock state, stale detection, last sync timestamps, and the last successful Zotero source.

## Verification performed

The release work included real regression coverage for:

```bash
python -m pytest tests/test_wiki_store.py tests/test_ingest_to_wiki.py tests/test_pdf_extract_reporting.py tests/test_index_manifest_v2.py tests/test_index_planner.py tests/test_incremental_index.py -q
```

and CLI smoke checks for:

```bash
PYTHONPATH=src python scripts/build_index.py --help
PYTHONPATH=src python scripts/ingest_to_wiki.py --help
```
