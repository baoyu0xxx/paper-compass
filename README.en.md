# paper-compass

<div align="center">

**Personal academic paper retrieval & knowledge navigation infrastructure**

[![Python](https://img.shields.io/badge/Python-3.11+-blue.svg)](https://www.python.org/)
[![License](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)
[![Version](https://img.shields.io/badge/version-1.2.0-blue.svg)](https://github.com/baoyu0xxx/paper-compass)

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
- **Multi-provider embedding** — Volcengine (2048-dim multimodal), OpenAI-compatible, or local SentenceTransformers — with cascade fallback

## Quick Start

```bash
# 1. Clone
git clone https://github.com/baoyu0xxx/paper-compass.git
cd paper-compass
pip install -e .

# 2. Configure — interactive (recommended)
paper-compass init

#    Or manually:
#    cp .env.example .env
#    Edit .env — fill in your API keys (LLM + embedding)

# 3. Verify configuration connectivity
paper-compass validate

# 4. Prepare data
python scripts/sync_zotero.py --extract-text
# → data/zotero-export/library.json + data/texts/*.txt

# 5. Build search index
python scripts/build_index.py --library data/zotero-export/library.json --full-rebuild

# 6. Generate wiki pages (optional, ~5h for 400 papers)
nohup python scripts/ingest_to_wiki.py --skip-existing > data/logs/wiki_gen.log 2>&1 &
# After completion:
python scripts/build_index.py --wiki

# 7. Verify
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
| Embedding API key | OpenAI-compatible or Volcengine multimodal, or local models |

### From Source

```bash
git clone https://github.com/baoyu0xxx/paper-compass.git
cd paper-compass
pip install -e .          # core dependencies
pip install -e ".[dev]"   # + pytest for testing
pip install -e ".[paperqa]"  # + PaperQA5 integration (optional)
```

Once installed, the `paper-compass` CLI command is available (see CLI Commands section below).

## Configuration

### Interactive Setup (Recommended)

```bash
paper-compass init
```

Step through the prompts to configure your LLM (wiki generation) and Embedding service's Base URL, API Key, and model name. API keys support `$ENV_VAR` syntax to reference existing environment variables (e.g. `$OPENAI_API_KEY`).

```bash
# Non-interactive mode (for scripted deployment)
paper-compass init \
  --llm-args base_url=https://api.openai.com/v1,model=gpt-4o \
  --embed-args api_style=volcengine,model=ep-20260420154519-9w64q

# Overwrite existing .env
paper-compass init --force
```

### Environment Variables

Copy `.env.example` to `.env` and fill in your values, or use `paper-compass init` to generate automatically:

| Variable | Required | Description |
|----------|----------|-------------|
| `LLM_BASE_URL` | Yes | LLM API base URL for wiki generation |
| `LLM_API_KEY` | Yes | LLM API key (supports `$ENV_VAR` reference) |
| `LLM_MODEL` | No | Model name (optional, defaults in `providers.yaml`) |
| `EMBED_BASE_URL` | Yes* | Embedding API base URL (OpenAI-compatible) |
| `EMBED_API_KEY` | Yes* | Embedding API key |
| `EMBED_MODEL` | No | Embedding model name (optional, defaults in `providers.yaml`) |
| `VOLC_EMBED_BASE_URL` | No | Volcengine multimodal embedding endpoint (alternative) |
| `VOLC_EMBED_API_KEY` | No | Volcengine API key |
| `VOLC_EMBED_MODEL` | No | Volcengine embedding model endpoint ID |
| `PAPERQA_BASE_URL` | Optional | PaperQA5 endpoint for full PDF RAG |
| `PAPERQA_API_KEY` | Optional | PaperQA5 API key |
| `PAPERQA_MODEL` | Optional | PaperQA5 model name |

> \* At least one of EMBED or VOLC_EMBED must be configured.

### $ENV_VAR Reference Syntax

API keys support `$ENV_VAR` syntax, so you never need to store plain-text secrets in `.env`:

```env
# Reference existing environment variables directly
LLM_API_KEY=$OPENAI_API_KEY
EMBED_API_KEY=$MY_EMBED_KEY
VOLC_EMBED_API_KEY=$VOLC_API_KEY
```

Resolved at runtime by `config.py`'s `_resolve_env_value()`. If the referenced env var is unset, the `$VAR` literal is preserved.

### Verify Configuration Connectivity

```bash
paper-compass validate
```

Example output:
```
  ✓ dotenv: OK
  ✓ llm: OK (model: gpt-4o, 1.2s, response: 15 chars)
  ✓ embed: OK (model: text-embedding-3-small, dim=1536, 0.8s)
```

### Embedding Provider Switching & Cascade Fallback

Embedding supports a **cascade fallback** mechanism:
1. **Primary:** `embedding_main` (OpenAI-compatible, `EMBED_BASE_URL` + `EMBED_API_KEY`)
2. **Fallback:** `embedding_volcengine` (Volcengine multimodal, `VOLC_EMBED_*` variables)
3. **Final fallback:** Local `bge-base` model (no API key needed)

Just configure the corresponding environment variables to enable each fallback level — no YAML editing required.

To pin a specific provider, modify `roles.pdf_embedding` and `roles.wiki_embedding` in `configs/providers.yaml`:

```yaml
roles:
  pdf_embedding: embedding_volcengine   # pin to Volcengine
  wiki_embedding: embedding_volcengine
```

### Provider Configuration

Advanced settings (LLM model, Chroma collection naming, MCP tracing) are in YAML configs under `configs/`:

- `configs/providers.yaml` — LLM + embedding provider settings
- `configs/paths.yaml` — storage paths
- `configs/mcp.yaml` — MCP server behavior + tracing

## Usage

### CLI Commands

After installation, use the `paper-compass` command directly:

```bash
# Interactive setup for LLM and embedding providers
paper-compass init

# Validate configuration and API connectivity
paper-compass validate
```

Detailed help:

```bash
paper-compass init --help
paper-compass validate --help
```

### CLI Scripts

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
python scripts/run_mcp_server.py --tool search_wiki --query "family firm succession"
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
├── src/paper_compass/       # Core library (15 modules)
│   ├── cli/                 # CLI commands (init, validate)
│   │   ├── __init__.py      # Main entry: paper-compass
│   │   ├── arg_utils.py     # key=value argument parsing (from lm-eval-harness)
│   │   ├── configure.py     # paper-compass init command
│   │   └── validate.py      # paper-compass validate command
│   ├── search.py            # search_library, search_passages, vector search
│   ├── router.py            # ask_research multi-layer routing
│   ├── mcp_server.py        # MCP tool handlers + dispatch
│   ├── mcp_contracts.py     # Tool schema definitions (single source of truth)
│   ├── vector_store.py      # ChromaDB wrapper + BM25 hybrid search
│   ├── embedder.py          # Multi-provider embedding with cascade fallback
│   ├── wiki_gen.py          # Two-pass LLM wiki generation
│   ├── wiki_store.py        # Thread-safe wiki writeback
│   ├── env_utils.py         # .env loader (always overwrites stale values)
│   ├── config.py            # YAML config loader with $ENV_VAR resolution
│   ├── types.py             # Dataclasses for responses
│   ├── index_manifest.py    # Fingerprint-based incremental indexing
│   ├── logging.py           # JSONL trace logging
│   ├── pdf_extract.py       # PyMuPDF + pdfplumber text extraction
│   └── zotero_sqlite.py     # Zotero SQLite reader
├── scripts/                # CLI entry points (5 scripts)
├── configs/                # YAML configuration templates
├── eval/                   # 12-query evaluation benchmark
├── wiki/                   # LLM-generated knowledge base
├── data/                   # Generated data (vectordb, texts, zotero-export)
├── tests/                  # pytest test suite (102 tests, all passing)
└── pyproject.toml          # Project metadata + dependencies
```

## Development

### Running Tests

```bash
pip install -e ".[dev]"
python3 -m pytest tests/ -v         # run all tests (102)
python3 -m pytest tests/ -x         # stop on first failure
python3 -m pytest tests/test_cli_arg_utils.py -v  # CLI argument parsing tests
python3 -m pytest tests/test_cli_configure.py -v  # Configuration command tests
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

Key differences: paper-compass adds LLM-powered wiki generation, MCP protocol integration, CLI configuration commands (`init`/`validate`), `$ENV_VAR` reference syntax, embedding provider cascade fallback, manifest-based incremental indexing, Chinese bigram-aware search, and a formal evaluation benchmark.

## Contributing

Contributions are welcome. Please open an issue to discuss significant changes before submitting a pull request.

## License

MIT
