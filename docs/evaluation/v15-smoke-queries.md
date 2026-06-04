# v1.5 smoke queries (manual regression)

Purpose: quick human checks after ranking/router/contract changes.

## A. library precision (metadata)

1) Query: `ABC123` (or a known real Zotero key)
- Expectation: exact key item appears at rank 1.
- Failure signal: key match missing or appears behind weak token overlaps.

2) Query: exact DOI (e.g. `10.xxxx/xxxx`)
- Expectation: exact DOI item appears at rank 1.
- Failure signal: unrelated title-only matches outrank DOI exact match.

3) Query: exact title (normalized lowercase acceptable)
- Expectation: target paper appears at rank 1.
- Failure signal: partial token overlap outranks exact title.

## B. wiki semantic retrieval

4) Query: a known topic page title/phrase
- Expectation: top results are wiki knowledge pages, not log/index artifacts.
- Failure signal: `wiki/log.md` or `wiki/index.md` appears in top results.

## C. ask_research routing

5) Query: broad conceptual question
- Expectation: mode often `wiki` or `hybrid`, answer includes wiki context.

6) Query: evidence-demanding question (`coefficient`, `p-value`, `table`, `identification strategy`)
- Expectation: mode should escalate to `hybrid` or `pdf`.

## D. writeback contract

7) Tool: `save_to_wiki` with explicit `wiki_root`
- Preview expectation: with `dry_run=true`, response only returns preview metadata and does not write files.
- Commit expectation: with `commit=true` and `dry_run=false`, page is created under the provided `wiki_root`.
- Failure signal: path always falls back to default `./wiki`, or preview mode already mutates disk.

## E. MCP protocol

8) JSON-RPC `tools/list` then `tools/call(search_library)`
- Expectation: `tools/list` returns only the public toolset, schema matches actual handler params, and call returns UnifiedResponse envelope with `trace_id`.
- Failure signal: `search_wiki` or infra-only knobs (`db_path`, `wiki_root`, etc.) leak into the default public schema.
