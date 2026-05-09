# paper-compass

Personal academic paper retrieval and knowledge navigation infrastructure.

## What is it?

paper-compass is a personal research knowledge system that:
- Reads your Zotero library (SQLite + PDF attachments)
- Generates structured markdown wiki pages from each paper (via LLM)
- Creates vector embeddings for semantic search (via Volcengine or any OpenAI-compatible API)
- Exposes 6 MCP (Model Context Protocol) tools for AI agents to query your research library

It bridges the gap between "I have 400+ papers in Zotero" and "I can ask my AI agent to find relevant passages and evidence."

## Quick Start

### 1. Install

```bash
git clone <repo-url> paper-compass
cd paper-compass
pip install -e .
# With optional PaperQA support:
# pip install -e ".[paperqa]"
# With dev tools:
# pip install -e ".[dev]"
```

### 2. Configure

```bash
cp .env.example .env
# Edit .env with your API keys:
#   XIAOMI_API_KEY  — for wiki generation (Mimo LLM)
#   VOLC_EMBED_*    — for embedding (Volcengine)
```

### 3. Prepare data

```bash
# Option A: If you have Zotero data already exported
# (library.json + data/texts/*.txt already exist)

# Option B: From Zotero SQLite
python scripts/sync_zotero.py   # → data/zotero-export/library.json + data/texts/
```

### 4. Build search index

```bash
python scripts/build_index.py              # build ChromaDB index for paper PDFs
python scripts/build_index.py --wiki       # build ChromaDB index for wiki pages
```

### 5. Generate wiki pages (optional, ~5h for 400 papers)

```bash
nohup python scripts/ingest_to_wiki.py --skip-existing > data/logs/wiki_gen.log 2>&1 &
```

### 6. Verify

```bash
python scripts/healthcheck.py              # basic checks
python scripts/healthcheck.py --smoke      # + API connectivity
python eval/run_eval.py -v                 # run evaluation benchmark
```

## MCP Tools

paper-compass exposes 6 tools via MCP stdio transport:

| Tool | Description |
|------|-------------|
| `search_wiki` | Semantic search over markdown wiki knowledge pages |
| `search_library` | Keyword + exact-match search over paper metadata (title, author, doi, collections, tags) |
| `search_passages` | ***New in v2*** — Search original text paragraphs with paper metadata. Dual-mode: semantic (vector) + keyword (full-text) |
| `ask_research` | Multi-layer router: wiki → escalate to PDF evidence → assembled answer |
| `get_paper_metadata` | Look up a single paper by Zotero key, DOI, or title |
| `save_to_wiki` | Write LLM-generated content back to the wiki |

### Using with Hermes Agent

Add to your Hermes `config.yaml`:

```yaml
mcp:
  servers:
    paper-compass:
      command: python3
      args: ["scripts/run_mcp_server.py", "--mcp"]
      cwd: "/path/to/paper-compass"
```

### Using with Claude Desktop

```json
{
  "mcpServers": {
    "paper-compass": {
      "command": "python3",
      "args": ["scripts/run_mcp_server.py", "--mcp"],
      "cwd": "/path/to/paper-compass"
    }
  }
}
```

## Project Structure

```
paper-compass/
├── src/miniresearch/       # Core library
│   ├── filters.py          # search_library, search_passages, vector_search
│   ├── router.py           # ask_research multi-layer routing
│   ├── mcp_server.py       # MCP tool handlers + dispatch
│   ├── mcp_contracts.py    # Single source of truth for tool schemas
│   ├── vector_store.py     # ChromaDB wrapper with BM25 hybrid
│   ├── embedder.py         # Embedding providers (Volcengine, local)
│   ├── wiki_gen.py         # LLM wiki page generation
│   ├── wiki_store.py       # Wiki writeback management
│   ├── logging.py          # JSONL trace logging
│   ├── env_utils.py        # .env loader (always overwrites)
│   └── models.py           # Dataclasses: UnifiedResponse, ModeDecision
├── scripts/                # CLI entry points
│   ├── sync_zotero.py      # Zotero SQLite → library.json + text extraction
│   ├── build_index.py      # Build ChromaDB vector index (papers + wiki)
│   ├── ingest_to_wiki.py   # Batch wiki generation (LLM-powered)
│   ├── run_mcp_server.py   # MCP server (stdio + CLI tool mode + interactive)
│   └── healthcheck.py      # Subsystem health verification
├── configs/                # YAML configuration templates
├── eval/                   # Evaluation benchmark suite
├── wiki/                   # Markdown knowledge base (406+ papers, topics, methods)
├── data/                   # Generated data (zotero-export, vectordb, texts, traces)
├── tests/                  # 66 tests (pytest)
├── .env.example            # Environment variable template
└── pyproject.toml          # Python project metadata + dependencies
```

## Requirements

- Python ≥ 3.11
- Zotero library with PDF attachments
- API keys for:
  - LLM (wiki generation): Mimo API or any OpenAI-compatible endpoint
  - Embedding: Volcengine multimodal embedding or any OpenAI-compatible endpoint

## Current Status

**v2.0.0** — Quality-hardened, publicly deployable release.

- 66 pytest tests (all green)
- 6 MCP tools with proper protocol initialization handshake
- Full evaluation benchmark (12/12 queries passing)
- Healthcheck script for subsystem verification
- Chinese bigram-aware search for improved CJK retrieval
- Fuzzy title matching for near-exact queries
- Dual-mode passage search (semantic vector + keyword full-text)

## Prior Art & Architecture

paper-compass adapts proven modules from [RAG-Assistant-for-Zotero](https://github.com/aahepburn/RAG-Assistant-for-Zotero):
- PDF extraction (PyMuPDF + pdfplumber fallback)
- Zotero SQLite reader with attachment path resolution
- ChromaDB vector storage with BM25 hybrid search
- Multi-provider embedding (local models + cloud APIs)

## License

MIT
