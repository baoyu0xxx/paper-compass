# AGENTS.md — Deploying paper-compass

This document guides an AI agent (Claude Code, Codex, Hermes, etc.) through deploying `paper-compass` from a fresh clone to a working MCP service.

## Project Summary

`paper-compass` is a personal academic paper retrieval infrastructure. It takes a Zotero PDF library, generates structured wiki pages via LLM, builds vector search indices, and exposes 6 MCP tools for AI agent consumption.

**Tech stack**: Python ≥3.11, ChromaDB, PyMuPDF, Volcengine embeddings, OpenAI-compatible LLM endpoint.

## Step-by-Step Deployment

### 1. Clone and install

```bash
git clone https://github.com/baoyu0xxx/paper-compass.git
cd paper-compass
pip install -e .
pip install -e ".[dev]"   # for tests
```

Once installed, the `paper-compass` CLI is available (see step 2).

### 2. Configure environment

**Option A — Interactive (recommended):**

```bash
paper-compass init
```

Step through prompts to configure LLM, embedding endpoints, and wiki prompt style. API keys support `$ENV_VAR` syntax (e.g. enter `$OPENAI_API_KEY` to reference an existing env var).

Wiki prompt selection (Step 3) offers:
- Default (通用): general-purpose academic prompts for any discipline
- Economics (经济学): specialized prompts for empirical economics
- Custom path: your own prompt files

**Option B — Manual `.env` edit:**

```bash
cp .env.example .env
```

Edit `.env` and fill in:

```env
LLM_BASE_URL=<your LLM endpoint>
LLM_API_KEY=<your API key>           # or $OPENAI_API_KEY
# LLM_MODEL=gpt-4o                   # optional, overrides providers.yaml default
EMBED_BASE_URL=<your embedding endpoint>
EMBED_API_KEY=<your embedding API key>  # or $MY_EMBED_KEY
# EMBED_MODEL=text-embedding-3-small  # optional
```

The LLM endpoint must be OpenAI-compatible (chat/completions format). Model defaults to `mimo-v2.5-pro` (configurable in `configs/providers.yaml`).

Embedding defaults to standard OpenAI-compatible format (`text-embedding-3-small`). To use Volcengine, set `VOLC_EMBED_*` variables instead (the system cascades automatically: main → volcengine → local `bge-base`).

**Option C — Non-interactive (scripted):**

```bash
paper-compass init \
  --llm-args base_url=https://api.openai.com/v1,model=gpt-4o \
  --embed-args api_style=volcengine,model=ep-20260420154519-9w64q
```

### 3. Verify configuration

```bash
paper-compass validate
```

Should show all green (✓) for dotenv, llm, and embed checks.

### 4. Prepare data

**Option A — from Zotero SQLite:**

The `sync_zotero.py` script reads Zotero's SQLite database directly. It looks for `zotero.sqlite` in default Zotero data locations:

```bash
python scripts/sync_zotero.py --extract-text
```

This produces `data/zotero-export/library.json` and `data/texts/*.txt`.

If the SQLite file is not found automatically, you can specify it:
```bash
python scripts/sync_zotero.py --db-path /path/to/zotero.sqlite --extract-text
```

**Option B — from pre-extracted data:**

If you have prepared data from another source:
- Place `library.json` at `data/zotero-export/library.json`
- Place text files at `data/texts/`
- Place PDFs at `data/pdfs/` (optional if text files are available)

The `library.json` format: a JSON array of objects with at minimum:
```json
{
  "key": "ZOTERO_ITEM_KEY",
  "title": "Paper Title",
  "authors": ["Author 1", "Author 2"],
  "year": 2023,
  "pdf_path": "data/pdfs/paper.pdf",
  "text_file": "data/texts/ZOTERO_ITEM_KEY.txt"
}
```

### 5. Build search index

```bash
python scripts/build_index.py --library data/zotero-export/library.json --full-rebuild
```

This creates ChromaDB collections under `data/vectordb/`.

**Pitfall**: If `build_index.py` skips papers with "missing PDF" even when text files exist, check that:
1. `text_file` paths in `library.json` are valid
2. You have the latest code (v1.0.1+ fixed the PDF-first check)

### 6. Generate wiki pages (optional but recommended)

```bash
# Test with 3 papers first
python scripts/ingest_to_wiki.py --limit 3 --workers 1

# Full run (400 papers ~5h, safe to interrupt and resume)
nohup python scripts/ingest_to_wiki.py --skip-existing --workers 10 > data/logs/wiki_gen.log 2>&1 &
```

Monitor progress:
```bash
tail -5 data/logs/wiki_gen.log
ls wiki/papers/*.md | wc -l
```

After generation completes, index the wiki:
```bash
python scripts/build_index.py --wiki --wiki-root ./wiki
```

### 7. Verify deployment

```bash
python scripts/healthcheck.py --smoke
python eval/run_eval.py -v
```

All 12 evaluation queries should pass. Healthcheck should show green across all subsystems (deps, env, library, vectordb, wiki, MCP contracts).

### 8. Run the MCP server

**As a standalone MCP server (stdio mode):**
```bash
python scripts/run_mcp_server.py --mcp
```

**Test individual tools:**
```bash
python scripts/run_mcp_server.py --tool search_wiki --query "家族企业"
python scripts/run_mcp_server.py --tool search_library --query "succession"
python scripts/run_mcp_server.py --tool ask_research --query "家族企业代际传承对劳动力结构的影响"
```

### 9. Configure AI agent clients

**Hermes Agent** (`config.yaml`):
```yaml
mcp:
  servers:
    paper-compass:
      command: python3
      args: ["scripts/run_mcp_server.py", "--mcp"]
      cwd: "/absolute/path/to/paper-compass"
```

**Claude Desktop** (`claude_desktop_config.json`):
```json
{
  "mcpServers": {
    "paper-compass": {
      "command": "python3",
      "args": ["scripts/run_mcp_server.py", "--mcp"],
      "cwd": "/absolute/path/to/paper-compass"
    }
  }
}
```

## Common Pitfalls

| Pitfall | Symptom | Fix |
|---------|---------|-----|
| `.env` not loaded | API calls fail with "unknown URL" | Ensure `.env` exists in project root |
| Stale env vars | LLM API gets garbage URL | `unset LLM_BASE_URL LLM_API_KEY EMBED_BASE_URL EMBED_API_KEY` and re-run |
| WSL + BM25 | `multiprocessing` error | Graceful degradation — vector search still works |
| Volcengine format error | 400 on embedding | Must use `{"input": [{"type": "text", "text": "..."}]}` format |
| Wiki chunk ID collision | Fewer vectors than sections | Same-stem pages in different wiki subdirs |
| `build_index.py` skips papers | "missing PDF" | Ensure text file paths are correct |
| ChromaDB dual-client | Weird errors | Never create 2 PersistentClient for same path |
| Shell env var pollution | API call uses wrong URL | `unset MIMO_BASE_URL` etc. before running |
| $ENV_VAR not resolved | "unauthorized" errors | Ensure the referenced env var is actually set in your shell |

## Running Tests

```bash
python3 -m pytest tests/ -v
```

All 102 tests must pass. If `test_env_utils.py` fails, check that the `.env` file has `LLM_BASE_URL` and `LLM_API_KEY` (not the old `MIMO_BASE_URL`/`XIAOMI_API_KEY`).

New test files:
- `tests/test_cli_arg_utils.py` — key=value parsing
- `tests/test_cli_configure.py` — interactive + non-interactive init
- `tests/test_config.py` — $ENV_VAR resolution

## Dependencies

All declared in `pyproject.toml`:
- **Runtime**: pyyaml, chromadb, pymupdf, pdfplumber, rank-bm25, sentence-transformers
- **Dev**: pytest
- **Optional**: paper-qa (for PaperQA5 full PDF RAG)

## Key Files

| File | Purpose |
|------|---------|
| `.env.example` | Environment variable template |
| `configs/providers.yaml` | LLM + embedding provider settings |
| `configs/mcp.yaml` | MCP server configuration |
| `pyproject.toml` | Project metadata, version, dependencies |
| `src/paper_compass/cli/__init__.py` | CLI entry point (`paper-compass`) |
| `src/paper_compass/cli/configure.py` | `paper-compass init` command |
| `src/paper_compass/cli/validate.py` | `paper-compass validate` command |
| `src/paper_compass/config.py` | Config loader with `$ENV_VAR` resolution |
| `src/paper_compass/env_utils.py` | `.env` loader (always overwrites stale values) |
| `scripts/sync_zotero.py` | Zotero → library.json + text extraction |
| `scripts/build_index.py` | ChromaDB index builder |
| `scripts/ingest_to_wiki.py` | Batch wiki generator |
| `scripts/run_mcp_server.py` | MCP server entry point |
| `scripts/healthcheck.py` | Health verification |
| `eval/run_eval.py` | Evaluation benchmark runner |
