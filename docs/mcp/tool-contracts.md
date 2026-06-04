# MCP tool contracts (v2)

Single source of truth: `src/paper_compass/mcp_contracts.py`

This document describes the **public MCP discovery surface** plus the boundary between advanced tools and local-only wrapper parameters. For CLI usage examples, treat `paper-compass-mcp --tool ...` as the preferred package entrypoint. Canonical MCP client configuration should point at the managed-runtime console script (`.venv/.../paper-compass-mcp`); `python scripts/run_mcp_server.py --tool ...` remains only as a repo-local compatibility shim that delegates to the same shared `mcp_entrypoint.main()`.

## Public tools exposed by `tools/list`

These are the tools returned by default MCP discovery. They define the public schema that an MCP client sees when it calls `tools/list`.

- `search_library(query, filters?, limit=10)`
- `search_passages(query, search_mode="semantic", filters?, limit=10)`
- `ask_research(query, force_mode="auto", filters?, max_sources=5)`
- `get_paper_metadata(paper_handle? | id_or_doi?)`
- `get_passage_context(passage_handle, window="paragraph", max_chars=2000)`
- `get_wiki_page_section(wiki_handle, include_frontmatter=false)`
- `save_to_wiki(title, content, target_type="queries", confidence="medium", source_refs?, tags?, dry_run=true, commit=false, upsert_mode="create")`

## Advanced/internal tool

- `search_wiki(query, limit=5)`
  - kept for direct wiki-index probing and diagnostics
  - hidden from default MCP `tools/list`
  - still callable by local CLI / internal workflows, e.g. `paper-compass-mcp --tool search_wiki ...`

## Hidden internal-only parameters

These parameters are accepted by local callers such as the shared CLI/wrapper layer, but are intentionally omitted from the public MCP schema to reduce tool-selection noise. This is why some README CLI examples may still show `--db-path` or `--wiki-root` even though those knobs do not appear in MCP `tools/list`.

- `search_wiki.db_path`
- `search_passages.db_path`
- `search_passages.text_dir`
- `search_passages.library_path`
- `ask_research.db_path`
- `save_to_wiki.wiki_root`

## CLI entrypoints

- Preferred package entrypoint: `paper-compass-mcp --tool ...`
- Canonical MCP client config: point `command` at the managed-runtime console script (`.venv/.../paper-compass-mcp`) and pass `--mcp`
- Repo-local compatibility shim: `python scripts/run_mcp_server.py --tool ...`
- Both delegate to the same shared `src/paper_compass/mcp_entrypoint.py`

## Response-shape principles

- `search_library` returns compact candidate rows anchored by `paper_handle`
- `search_passages` returns compact candidate rows anchored by `passage_handle` + `snippet`
- `ask_research` returns `answer` + `mode_decision` + `evidence_digest`; detailed wiki/PDF payloads are deferred to drill-down tools
- `save_to_wiki` defaults to preview mode; callers must set `commit=true` to write to disk

## Error envelope

- `ok: false`
- `tool`
- `trace_id`
- `warnings`
- `next_suggested_action`

## Discovery

- MCP `tools/list` returns contracts directly from `mcp_contracts.py`
- default discovery returns public tools only
- advanced tools remain callable by name for internal/local workflows
