---
name: paper-compass
description: "Use the local paper-compass MCP knowledge base to search a Zotero paper library, retrieve original PDF passages, read compiled wiki sections, answer research questions with traceable evidence, and preview or commit research notes. Trigger for paper-compass, Zotero library search, local paper retrieval, PDF evidence, academic literature synthesis, or paper wiki updates."
metadata:
  category: research
  platforms: [windows, linux, macos]
  project: paper-compass
  repository: https://github.com/baoyu0xxx/paper-compass
---

# paper-compass

Use this skill when the user wants to search or synthesize papers already managed by the local `paper-compass` service. It is a local Zotero-to-RAG/wiki system, not a substitute for external literature discovery. Keep the distinction between metadata, compiled wiki knowledge, and verbatim PDF evidence explicit.

## Core workflow

1. Identify the task before calling tools:
   - Find candidate papers: `search_library`.
   - Find exact original evidence: `search_passages`, then `get_passage_context`.
   - Read a compiled explanation or topic page: `ask_research`, then `get_wiki_page_section` when a `wiki_handle` is returned.
   - Answer a broad research question: `ask_research` with `force_mode=auto`.
   - Inspect one known paper: `get_paper_metadata`.
2. Start broad, then drill down. Preserve returned `paper_handle`, `passage_handle`, and `wiki_handle`; use them for readback instead of reconstructing identifiers from titles.
3. For claims about exact wording, page location, variable definitions, identification strategy, sample construction, coefficients, standard errors, robustness, mechanisms, or heterogeneity, require PDF passage evidence. Prefer `search_passages` with `search_mode=hybrid` when terminology and concepts both matter.
4. For a synthesized answer, report which mode was used (`wiki`, `pdf`, or `hybrid`), distinguish compiled interpretation from source text, and attach the returned sources/evidence digest to the claims they support.
5. If no relevant result is returned, say that the local corpus did not provide evidence. Do not fill gaps with invented citations, numbers, paper details, or conclusions. Use external literature skills only when the user also asks for papers outside the local corpus.
6. `search_wiki` is an advanced troubleshooting/direct-wiki-search entrypoint, not the default tool for broad research questions.

## Tool selection

### Candidate discovery

Call `search_library` with a natural-language query. Add `filters` only when the user specifies them:

```json
{"authors":["Author Name"],"collections":["Collection"],"tags":["tag"],"year_from":2020,"year_to":2025}
```

Use `limit` to control result count. Treat returned scores as ranking signals, not proof of relevance. Follow strong candidates with `get_paper_metadata` if full metadata is needed.

### Original passage evidence

Call `search_passages` with:

- `search_mode=semantic` for conceptual similarity;
- `search_mode=keyword` for exact terms, variable names, acronyms, and Chinese phrases;
- `search_mode=hybrid` for a balanced search.

Then call `get_passage_context` on the selected `passage_handle`. Use `window=paragraph` by default; use `section` or `page` when the surrounding argument matters. Quote or paraphrase only what the returned passage supports, and retain `page_num` when present.

### Wiki knowledge and synthesis

Use `ask_research` for broad questions. `force_mode=auto` is the default; use `force_mode=wiki` for compiled knowledge only, `force_mode=pdf` when source evidence is required, and `force_mode=hybrid` when both are needed. `max_sources` should match the requested breadth.

The answer is a retrieval result, not an automatically verified scholarly conclusion. Check the `mode_decision`, `confidence`, `sources`, and `evidence_digest`. Read cited wiki content with `get_wiki_page_section` before relying on a specific section.

### Wiki writeback

Use `save_to_wiki` only for a curated note or synthesis that the user wants retained:

1. Supply a precise `title`, evidence-grounded `content`, and `source_refs` containing returned handles or source identifiers.
2. First call it as a preview (`dry_run=true`, or omit write flags). Inspect `would_write`, conflicts, target path, linked pages, and index-update preview.
3. Commit only after the user requests persistence or approves the preview. The commit call must explicitly set `dry_run=false` and `commit=true`; setting only `commit=true` conflicts with the default dry-run.
4. Never silently overwrite an existing page; choose the appropriate `upsert_mode` and explain the choice.

## Incremental indexing

For maintenance requests, use `index_incremental` with its default `dry_run=true` first. Review changed/added/deleted counts, embedding work, warnings, and the deletion plan before applying. `prune_deleted=true` removes deleted documents from the index; use `explain_changes=true` with a small `sample_size` when metadata-only churn looks unexpectedly large. Set `allow_large_incremental=true` only after reviewing that explanation. This tool updates the paper index; it does not extract Zotero data, generate wiki pages, or build the wiki index.

## Full synchronization

Prefer `paper-compass sync --dry-run` for an end-to-end preview. After review, the normal sync runs Zotero extraction, incremental paper indexing, wiki generation, and wiki indexing. Never modify the original Zotero SQLite database. If configuration or data is missing, report the concrete prerequisite (`.env`, library JSON, text directory, vector index, or wiki index) and stop at the non-destructive diagnostic step. If vectordb health checks report journal/WAL/manifest corruption, stop writes and follow the repository's rebuild/backup guidance.

## Diagnostics

Use this short order for setup or runtime failures: `paper-compass status` → `paper-compass validate` → `paper-compass-healthcheck --smoke`. For no-result searches, distinguish an empty/stale corpus or missing index from a poor query; for Chinese or exact terminology, retry with `keyword` or `hybrid`. For stale sync locks or extraction failures, inspect status and the failure report before retrying; do not force-unlock or rebuild blindly.

## Response discipline

- State whether a result comes from library metadata, compiled wiki text, or original PDF text.
- Cite local evidence using the exact returned title, document id, page number, and handle where available.
- Separate observed source content from interpretation and from assumptions.
- Do not claim that the whole library was searched unless the tool response supports that scope.
- Mention low confidence, missing indexes, stale synchronization, extraction failures, or conflicting sources instead of hiding them.
- For Chinese or mixed Chinese-English queries, preserve the user's original terms and try keyword or hybrid mode if semantic retrieval misses terminology.

## Runtime notes

The canonical installed entrypoint is `paper-compass-mcp --mcp`; the repository-local compatibility entrypoint is `python scripts/run_mcp_server.py --mcp`. Common project-relative defaults are:

- library: `data/zotero-export/library.json`
- extracted text: `data/texts/`
- vector database: `data/vectordb/`
- wiki: `wiki/`

Use `paper-compass validate` and `paper-compass status` for diagnostics. Do not expose API keys or copy `.env` contents into responses.
