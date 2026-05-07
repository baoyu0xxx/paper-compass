# Current architecture summary

Project direction has been narrowed to a lightweight 5-layer stack:

1. Zotero source layer
- PDF root: /mnt/d/zotero_backup
- SQLite metadata DB: /mnt/d/zotero_backup/zotero_readonly.sqlite

2. Sync layer
- Directory scan is the fallback truth for file existence
- sqlite is the preferred metadata source for titles, creators, collections, tags, and attachment mapping
- outputs:
  - data/zotero-export/manifest.csv
  - data/zotero-export/library.json

3. Wiki breadth layer
- local markdown wiki
- curated ingest only
- Mimo API for generation/query summarization
- shared embedding provider for wiki semantic search

4. PaperQA depth layer
- full-PDF indexing and retrieval
- embedding provider expected to be a domestic online service (e.g. Volcengine)
- retrieval should support collection/tag/author/year filters

5. MCP layer
- tools:
  - search_wiki
  - search_library
  - ask_research
  - get_paper_metadata
  - save_to_wiki

Design principle:
- reuse existing patterns, write only thin glue
- avoid GUI and heavyweight app shells
- keep provider configuration split by role
