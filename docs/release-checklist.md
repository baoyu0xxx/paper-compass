# paper-compass Release Checklist

Use this checklist before publishing a new `paper-compass` version. The goal is to keep code, docs, tests, tags, and release assets aligned.

## Preflight

```bash
rtk git status --short
rtk python3 scripts/bootstrap_runtime.py
rtk python3 -m paper_compass --help
rtk python3 -m paper_compass sync --help
rtk python3 scripts/healthcheck.py --deps-only
```

## Targeted tests

```bash
rtk pytest tests/test_healthcheck.py tests/test_zotero_snapshot.py tests/test_sync_zotero_paths.py tests/test_pipeline_sync.py tests/test_cli_sync_data.py tests/test_cli_status.py tests/test_incremental_index.py tests/test_index_manifest_v2.py tests/test_pdf_extract_reporting.py tests/test_wiki_store.py tests/test_ingest_to_wiki.py -q
rtk pytest tests/test_config.py tests/test_packaged_configs_sync.py tests/test_packaging_metadata.py tests/test_console_scripts.py -q
```

## Full tests

```bash
rtk pytest tests/ -q
```

## Docs consistency

```bash
rtk grep -e "zotero_readonly.sqlite over zotero.sqlite\|prefers zotero_readonly" README.md README.en.md AGENTS.md
rtk grep -e "pdf_embedding\|wiki_embedding\|PAPERQA_\|paperqa_answer" README.md README.en.md AGENTS.md configs src/paper_compass/configs tests
rtk grep -e "--wiki-upsert-mode\|--explain-changes\|pdf_extract_failures.jsonl" README.md README.en.md AGENTS.md docs/release-notes-v1.4.1.md
rtk grep -e "v1.4.1\|1.4.1" README.md README.en.md pyproject.toml docs/release-notes-v1.4.1.md
```

Expected:

- No docs should say auto-discovery prefers `zotero_readonly.sqlite`.
- Default docs/configs should not expose legacy split embedding roles or `PAPERQA_*` provider settings.
- New release docs should mention `--wiki-upsert-mode`, `--explain-changes`, and `data/logs/pdf_extract_failures.jsonl` consistently.
- Version mentions should match the tag and published release asset.

## Release asset verification

Before hardcoding a wheel URL in README files, verify the GitHub Release exists:

```bash
rtk gh release list --repo baoyu0xxx/paper-compass --limit 10
rtk git tag --list "v*"
```

Do not point installation examples at an unpublished versioned asset URL.

## Non-goals during release cleanup

- Do not commit generated runtime data such as `data/state/`, `data/vectordb/`, `wiki/log.md`, or `wiki/index.md` unless the release explicitly intends to ship generated knowledge-base content.
- Do not publish a GitHub Release from a dirty working tree.
- Do not reintroduce legacy `pdf_embedding` / `wiki_embedding` split roles in default configs.
