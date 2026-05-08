# MCP tool contracts (v1.5)

Single source of truth: `src/miniresearch/mcp_contracts.py`

Tools:
- `search_wiki(query, limit=5, db_path="data/vectordb")`
- `search_library(query, filters?, limit=10)`
- `ask_research(query, force_mode="auto", filters?, max_sources=5, db_path="data/vectordb")`
- `get_paper_metadata(id_or_doi)`
- `save_to_wiki(title, content, target_type="queries", confidence="medium", source_refs?, tags?, wiki_root="./wiki")`

Error envelope:
- `ok: false`
- `tool`
- `trace_id`
- `warnings`
- `next_suggested_action`

Discovery:
- MCP `tools/list` returns these contracts directly from `mcp_contracts.py`.
