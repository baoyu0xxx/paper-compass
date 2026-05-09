# paper-compass

<div align="center">

**Personal academic paper retrieval & knowledge navigation infrastructure**

[![Python](https://img.shields.io/badge/Python-3.11+-blue.svg)](https://www.python.org/)
[![License](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)
[![Version](https://img.shields.io/badge/version-1.0.1-blue.svg)](https://github.com/baoyu0xxx/paper-compass)

</div>

---

> 📖 **中文版**: [README.md](README.md)

## What is paper-compass?

paper-compass turns your Zotero library into a **queryable knowledge infrastructure** for AI agents. It bridges the gap between "I have hundreds of papers in Zotero" and "my AI agent can find relevant passages and evidence by asking in natural language."

**The pipeline**: Zotero PDFs → LLM-generated structured wiki pages → vector embeddings → 6 MCP tools for AI integration.

## Key Features

- **6 MCP tools** — `search_wiki`, `search_library`, `search_passages`, `ask_research`, `get_paper_metadata`, `save_to_wiki` — standard MCP protocol (`2024-11-05`) with proper initialize handshake
- **LLM-powered wiki generation** — auto-generates structured knowledge pages from PDFs (two-pass classifier + empirical-economics-aware prompts)
- **Dual-mode passage search** — semantic vector + BM25 keyword full-text search over original paper chunks
- **Incremental indexing** — manifest-based change detection avoids re-embedding unchanged papers
- **Chinese bigram-aware retrieval** — improved CJK recall for Chinese-language academic literature
- **Multi-provider embedding** — Volcengine (2048-dim multimodal), OpenAI-compatible, or local SentenceTransformers

## Quick Start

```bash
# 1. Clone
git clone https://github.com/baoyu0xxx/paper-compass.git
cd paper-compass
pip install -e .

# 2. Configure
cp .env.example .env
# Edit .env — fill in your API keys (LLM + Volcengine embedding)

# 3. Prepare data
python scripts/sync_zotero.py --extract-text
# → data/zotero-export/library.json + data/texts/*.txt

# 4. Build search index
python scripts/build_index.py --library data/zotero-export/library.json --full-rebuild

# 5. Generate wiki pages (optional, ~5h for 400 papers)
nohup python scripts/ingest_to_wiki.py --skip-existing > data/logs/wiki_gen.log 2>&1 &
# After completion:
python scripts/build_index.py --wiki

# 6. Verify
python scripts/healthcheck.py --smoke
python eval/run_eval.py -v
```

## Installation

### Prerequisites

| Requirement | Notes |
|-------------|-------|
| Python ≥ 3.11 | Check with `python3 --version` |
| Zotero library | Optional — works with pre-extracted text files |
| LLM API key | Wiki generation via OpenAI-compatible endpoint (`LLM_BASE_URL` + `LLM_API_KEY`) |
| Embedding API key | Volcengine multimodal (`VOLC_EMBED_BASE_URL` + `VOLC_EMBED_API_KEY` + `VOLC_EMBED_MODEL`) or local models |

### From Source

```bash
git clone https://github.com/baoyu0xxx/paper-compass.git
cd paper-compass
pip install -e .          # core dependencies
pip install -e ".[dev]"   # + pytest for testing
pip install -e ".[paperqa]"  # + PaperQA5 integration (optional)
```

## Configuration

### Environment Variables

Copy `.env.example` to `.env` and fill in your values:

| Variable | Required | Description |
|----------|----------|-------------|
| `LLM_BASE_URL` | Yes | LLM API base URL for wiki generation |
| `LLM_API_KEY` | Yes | LLM API key |
| `VOLC_EMBED_BASE_URL` | Yes | Volcengine multimodal embedding endpoint |
| `VOLC_EMBED_API_KEY` | Yes | Volcengine API key |
| `VOLC_EMBED_MODEL` | Yes | Embedding model endpoint ID (e.g., `ep-20260420154519-xxxxx`) |
| `PAPERQA_BASE_URL` | Optional | PaperQA5 endpoint for full PDF RAG |
| `PAPERQA_API_KEY` | Optional | PaperQA5 API key |
| `PAPERQA_MODEL` | Optional | PaperQA5 model name |

### Provider Configuration

Advanced settings (LLM model, collection naming, MCP tracing) are in YAML configs under `configs/`:

- `configs/providers.yaml` — LLM + embedding provider settings
- `configs/paths.yaml` — storage paths
- `configs/mcp.yaml` — MCP server behavior + tracing

## Usage

### CLI Tools

| Script | Purpose | Key Flags |
|--------|---------|-----------|
| `scripts/sync_zotero.py` | Zotero SQLite → library.json + text extraction | `--extract-text` |
| `scripts/build_index.py` | Build ChromaDB vector index (papers + wiki) | `--full-rebuild`, `--incremental`, `--prune-deleted`, `--wiki` |
| `scripts/ingest_to_wiki.py` | Batch wiki generation via LLM | `--skip-existing`, `--workers 10`, `--limit N` |
| `scripts/run_mcp_server.py` | MCP server (stdio + tool-call + interactive) | `--mcp`, `--tool <name> --query "..."` |
| `scripts/healthcheck.py` | Subsystem health verification | `--smoke` (API connectivity) |

#### Build Index

```bash
# Full rebuild (clear and re-embed all papers)
python scripts/build_index.py --library data/zotero-export/library.json --full-rebuild

# Incremental (only changed/new papers)
python scripts/build_index.py --library data/zotero-export/library.json --incremental

# Index wiki pages
python scripts/build_index.py --wiki --wiki-root ./wiki
```

#### Generate Wiki Pages

```bash
# Process all ungenerated pages (10 concurrent workers)
python scripts/ingest_to_wiki.py --skip-existing --workers 10

# Test with 3 papers
python scripts/ingest_to_wiki.py --limit 3 --workers 1

# Resume interrupted run
python scripts/ingest_to_wiki.py --skip-existing --workers 10
```

### MCP Integration

#### With Hermes Agent

Add to `config.yaml`:

```yaml
mcp:
  servers:
    paper-compass:
      command: python3
      args: ["scripts/run_mcp_server.py", "--mcp"]
      cwd: "/path/to/paper-compass"
```

#### With Claude Desktop

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

#### CLI Tool Mode

```bash
python scripts/run_mcp_server.py --tool search_wiki --query "家族企业代际传承"
python scripts/run_mcp_server.py --tool search_library --query "author name"
python scripts/run_mcp_server.py --tool search_passages --query "specific passage"
python scripts/run_mcp_server.py --tool ask_research --query "research question"
python scripts/run_mcp_server.py --tool get_paper_metadata --key YOUR_ZOTERO_KEY
```

## Architecture

### Pipeline

```
Zotero SQLite + PDFs
  → sync_zotero.py → library.json + data/texts/*.txt
  → build_index.py → ChromaDB vector collections (papers + wiki)
  → ingest_to_wiki.py → LLM → wiki/papers/*.md
  → build_index.py --wiki → ChromaDB wiki collection
  → run_mcp_server.py → 6 MCP tools exposed to AI agents
```

### MCP Tools

| Tool | Description | Search Mode |
|------|-------------|-------------|
| `search_wiki` | Semantic search over LLM-generated wiki knowledge pages | Vector |
| `search_library` | Keyword + Chinese bigram + fuzzy metadata search | Text |
| `search_passages` | Dual-mode search over original paper text blocks | Vector + BM25 |
| `ask_research` | Multi-layer router: wiki → escalate to PDF evidence | Hybrid |
| `get_paper_metadata` | Look up a single paper by key, DOI, or title | Exact |
| `save_to_wiki` | Write LLM-generated content back to the wiki | — |

### Project Structure

```
paper-compass/
├── src/miniresearch/       # Core library (13 modules)
│   ├── filters.py          # search_library, search_passages, vector_search
│   ├── router.py           # ask_research multi-layer routing
│   ├── mcp_server.py       # MCP tool handlers + dispatch
│   ├── mcp_contracts.py    # Tool schema definitions (single source of truth)
│   ├── vector_store.py     # ChromaDB wrapper + BM25 hybrid search
│   ├── embedder.py         # Multi-provider embedding (Volcengine, local)
│   ├── wiki_gen.py         # Two-pass LLM wiki generation
│   ├── wiki_store.py       # Thread-safe wiki writeback
│   ├── env_utils.py        # .env loader (always overwrites stale values)
│   ├── config.py           # YAML config loader with env var resolution
│   ├── models.py           # Dataclasses for responses
│   ├── index_manifest.py   # Fingerprint-based incremental indexing
│   ├── logging.py          # JSONL trace logging
│   ├── pdf_extract.py      # PyMuPDF + pdfplumber text extraction
│   └── zotero_sqlite.py    # Zotero SQLite reader
├── scripts/                # CLI entry points (5 scripts)
├── configs/                # YAML configuration templates
├── eval/                   # 12-query evaluation benchmark
├── wiki/                   # LLM-generated knowledge base
├── data/                   # Generated data (vectordb, texts, zotero-export)
├── tests/                  # pytest test suite
└── pyproject.toml          # Project metadata + dependencies
```

## Development

### Running Tests

```bash
pip install -e ".[dev]"
python3 -m pytest tests/ -v         # run all tests
python3 -m pytest tests/ -x         # stop on first failure
python3 -m pytest tests/test_incremental_index.py -v  # incremental indexing tests
```

### Running Evaluation

```bash
python eval/run_eval.py             # all 12 queries
python eval/run_eval.py -v          # verbose output
python eval/run_eval.py --mode strict  # strict key matching
```

## Prior Art

paper-compass adapts proven modules from [RAG-Assistant-for-Zotero](https://github.com/aahepburn/RAG-Assistant-for-Zotero):

| Source Module | Adapted As | Purpose |
|---------------|------------|---------|
| `backend/pdf.py` | `pdf_extract.py` | PyMuPDF text extraction with pdfplumber fallback |
| `backend/zotero_dbase.py` | `zotero_sqlite.py` | Zotero SQLite reader with path resolution |
| `backend/embed_utils.py` | `embedder.py` | Multi-provider embedding (local + cloud) |
| `backend/vector_db.py` | `vector_store.py` | ChromaDB wrapper with BM25 hybrid search |

Key differences: paper-compass adds LLM-powered wiki generation, MCP protocol integration, manifest-based incremental indexing, Chinese bigram-aware search, and a formal evaluation benchmark.

## Contributing

Contributions are welcome. Please open an issue to discuss significant changes before submitting a pull request.

## License

MIT
