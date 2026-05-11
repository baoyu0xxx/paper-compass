# paper-compass

<div align="center">

**Turn your Zotero library into a dual-engine knowledge base for AI agents — RAG full-text retrieval + LLM wiki knowledge compilation**

[![version](https://img.shields.io/badge/version-1.2.4-5a6e5c?style=flat-square&labelColor=3a3026&color=5a6e5c)](https://github.com/baoyu0xxx/paper-compass)
[![license](https://img.shields.io/badge/license-MIT-7a96a6?style=flat-square&labelColor=3a3026)](LICENSE)
[![python](https://img.shields.io/badge/Python-3.11+-E8D5B5?style=flat-square&labelColor=3a3026&color=E8D5B5)](https://www.python.org/)
[![MCP](https://img.shields.io/badge/protocol-MCP_2024--11--05-8db580?style=flat-square&labelColor=3a3026&color=8db580)](https://spec.modelcontextprotocol.io/)
[![tests](https://img.shields.io/badge/tests-159_passed-d4785c?style=flat-square&labelColor=3a3026&color=d4785c)](https://github.com/baoyu0xxx/paper-compass/actions)

</div>

---

> 📖 **中文版**: [README.md](README.md)

## Why paper-compass

### What existing tools can't do

Academic researchers manage their papers with Zotero every day, but two core pain points remain unsolved:

- **Full-text is not searchable** — Zotero can search titles, authors, and keywords, but the actual content — research questions, data, methods, findings — is scattered across hundreds of PDFs. Writing a literature review becomes "I think I read a paper that said something about this" — relying on memory, or re-reading papers one by one.
- **Knowledge doesn't accumulate** — Understanding and notes from each paper stay in your head. Next time you ask the same question, you have to re-derive everything from the original PDF.

Two excellent open-source projects have emerged recently, each addressing part of this problem:

| | [RAG-Assistant-for-Zotero](https://github.com/aahepburn/RAG-Assistant-for-Zotero) | [llm-wiki-skill](https://github.com/sdyckjq-lab/llm-wiki-skill) | **paper-compass** |
|---|---|---|---|
| Target user | Humans (desktop GUI app) | Agents (skill installation) | **Agents (MCP standard protocol)** |
| Core capability | RAG conversational paper Q&A | LLM wiki knowledge compilation | **RAG retrieval + LLM wiki dual-engine** |
| Search method | Semantic + BM25 + reranking | Vector search | Semantic + BM25 + Chinese bigram + metadata |
| Knowledge persistence | None (dynamically retrieved per query) | Wiki markdown pages | **Wiki markdown + ChromaDB vector index** |
| Protocol standard | Standalone app (no standard API) | Skill files (platform-specific) | **MCP 2024-11-05 (cross-framework)** |
| Incremental indexing | ❌ | N/A | ✅ Manifest-based change detection |
| CLI config | GUI settings | bash install.sh | **`paper-compass init` + `validate`** |
| Chinese optimization | ❌ | Partial | ✅ Word segmentation + economics preset + Volcengine embedding |

### What paper-compass does differently

**It is the only system that combines RAG full-text retrieval with LLM wiki knowledge compilation, designed specifically for AI agents through the MCP standard protocol.**

Three design principles:

- **Agent-first**: All capabilities are exposed through 6 standard MCP tools. Your Hermes Agent or Claude Desktop can call them directly — no need to open a separate GUI application, no copy-pasting, no leaving your agent conversation.
- **Dual-engine**: The RAG engine handles "I can't quite remember what that paper said, find the original text." The Wiki engine handles "What are this paper's core findings and methods?" Two complementary retrieval systems, not mutually exclusive.
- **Inherit the best**: Four core modules — PDF extraction, Zotero SQLite reading, embedding, and vector storage — are adapted from RAG-Assistant-for-Zotero's proven implementations. The LLM wiki methodology draws on Karpathy's llm-wiki philosophy of "compile once, maintain continuously." On top of this, paper-compass adds MCP protocol integration, incremental indexing, Chinese bigram retrieval, discipline-specific wiki prompts, CLI configuration commands, and a formal evaluation benchmark.

### Example use case

Ask your agent directly:

> "What papers do we have about corporate digital transformation? What are the mainstream empirical methods and commonly used proxy variables?"

Your agent searches your own paper library and returns relevant passages with source citations and page numbers — no reliance on generic, unverified web search results.

**The project is specifically optimized for Chinese-language academic research**: Chinese word-segmentation-aware retrieval and scoring, economics discipline preset for wiki generation prompts, and Volcengine multimodal embedding support for better CJK recall.

## Key Features

| Feature | Description |
|---------|-------------|
| 🔌 **6 MCP tools** | `search_wiki`, `search_library`, `search_passages`, `ask_research`, `get_paper_metadata`, `save_to_wiki` — MCP 2024-11-05 protocol, zero-config integration with Hermes Agent and Claude Desktop |
| 📝 **LLM-powered wiki generation** | Each paper auto-generates a structured wiki page (research question, core findings, methods & data, theoretical framework) via a two-pass classifier with customizable prompts (general academic default / economics discipline preset / custom path) |
| 🔍 **Dual-mode passage search** | Dense (semantic vectors) and sparse (BM25 keywords) dual-path retrieval, balancing conceptual relevance and exact term matching |
| 📊 **Incremental indexing** | Manifest-based change detection — only re-index papers that changed, no full rebuilds needed |
| 🇨🇳 **Chinese academic retrieval** | Chinese word-segmentation-aware retrieval and scoring, plus economics-specific wiki prompts for better CJK recall |
| 🔄 **Multi-provider embedding cascade** | Volcengine (2048-dim multimodal), OpenAI-compatible endpoints, local bge-base — three-tier automatic fallback on failure or rate-limiting |
| ⚙️ **CLI configuration commands** | `paper-compass init` for interactive LLM + embedding setup, `paper-compass validate` for one-click connectivity check, with `$ENV_VAR` reference syntax |
| 🎯 **Wiki prompt customization** | `WIKI_PROMPT` env var to switch between general academic default (`default`), economics preset (`economics`), or a custom prompt directory — discipline-tailored wiki generation |

## Quick Start

### Option A: Agent Prompt Deployment (Recommended)

Copy the following prompt to your AI agent — it will handle the full paper-compass setup automatically:

<details>
<summary>👋 Copy this prompt to your agent</summary>

> Please deploy paper-compass under `$HOME/projects/` (create the directory if it doesn't exist). Follow these steps:
>
> 1. Clone the repo: `git clone https://github.com/baoyu0xxx/paper-compass.git` into `$HOME/projects/paper-compass`
> 2. Install dependencies: `cd $HOME/projects/paper-compass && pip install -e .`
> 3. Run `paper-compass init` for interactive LLM and Embedding API configuration using the credentials you know
> 4. Run `paper-compass validate` to verify connectivity
> 5. Export your Zotero SQLite database path as `ZOTERO_SQLITE_PATH` env var, then run `python scripts/sync_zotero.py --extract-text`
> 6. Run `python scripts/build_index.py --library data/zotero-export/library.json --full-rebuild`
> 7. (Optional) Run `python scripts/ingest_to_wiki.py --limit 3 --workers 1` to test wiki generation
> 8. Run `python scripts/healthcheck.py --smoke` to verify all subsystems
> 9. Finally, add the MCP config to your current agent framework (command: `python3`, args: `["scripts/run_mcp_server.py", "--mcp"]`, cwd: `$HOME/projects/paper-compass`)
>
> Confirm each step before proceeding to the next.

</details>

For more capable agents, a one-liner suffices:

```text
Please clone https://github.com/baoyu0xxx/paper-compass.git, install dependencies, run paper-compass init for interactive config, verify the setup, then sync my Zotero library.
```

### Option B: From Source

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
# → auto-discovery order: explicit --db-path > ZOTERO_SQLITE_PATH > default Zotero dirs > backup dirs
# → data/zotero-export/library.json + data/texts/*.txt

#    If the database and storage/ are not siblings:
#    python scripts/sync_zotero.py --db-path /path/to/zotero.sqlite --storage-path /path/to/storage --extract-text

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

## Updating

### Automatic Update (Recommended)

```bash
# Check for available updates
paper-compass update --check

# Update to the latest version
paper-compass update

# Update to a specific version
paper-compass update --version v1.2.4

# Simulate an update (preview changes only)
paper-compass update --dry-run
```

`paper-compass update` automatically:
- Fetches the latest code and switches to the target version
- Reinstalls Python dependencies
- Detects breaking changes (new required env vars, config format changes) and warns you
- Runs `paper-compass validate` to verify API connectivity
- Runs a quick test smoke check

### Manual Update

If automatic update is unavailable (offline, no git, etc.):

```bash
git fetch origin --tags
git checkout v1.2.4          # or git pull origin main
pip install -e .
paper-compass validate        # verify config still works
python3 -m pytest tests/ -x   # ensure tests pass
```

### Upgrade Notes

<details>
<summary>Cross-version upgrade notes (click to expand)</summary>

> ⚠️ **Cross-version upgrades** (e.g. v1.1.x → v1.2.x) may involve config format changes and new env vars.
>
> - `.env` is gitignored — upgrades will never overwrite your private config
> - Watch for ⚠ warnings in terminal output after upgrade — you may need to add new env vars
> - If `validate` fails after upgrade, run `paper-compass init --force` to regenerate `.env`
> - Backup before upgrading: `cp .env .env.backup`

</details>

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

Once installed, the `paper-compass` CLI command is available (see CLI Commands section).

## Configuration

### Interactive Setup (Recommended)

```bash
paper-compass init
```

Step through prompts to configure your LLM (wiki generation) and Embedding provider's Base URL, API Key, and model name, followed by wiki prompt style selection. API keys support `$ENV_VAR` syntax to reference existing environment variables (e.g. `$OPENAI_API_KEY`).

```bash
# Non-interactive mode (for scripted deployment)
paper-compass init \
  --llm-args base_url=https://api.openai.com/v1,model=gpt-4o \
  --embed-args api_style=volcengine,model=doubao-embedding-vision-250615 \
  --wiki-prompt economics

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
| `WIKI_PROMPT` | No | Wiki prompt style: `default` (general academic), `economics` (economics preset), or custom path |


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

### Wiki Prompt Selection

During `paper-compass init`, after configuring LLM and embedding providers, you'll be prompted to choose a wiki prompt style.

**Three modes:**

| Mode | WIKI_PROMPT | Description |
|------|-------------|-------------|
| Default (General Academic) | `default` | General-purpose academic prompts for all disciplines (new in v1.2.1) |
| Discipline Preset | `economics` etc. | Prompts optimized for specific disciplines (currently built-in: economics) |
| Custom Path | `/path/to/prompts` | Use your own prompt files |

**Switching prompts:** Edit the `WIKI_PROMPT` variable in `.env`:

```env
# Use general academic prompts (all disciplines)
WIKI_PROMPT=default

# Use economics discipline preset
WIKI_PROMPT=economics

# Use custom prompts
WIKI_PROMPT=/home/user/my-prompts
```

**Two-pass generation architecture:** Wiki generation uses a "classify → generate" two-pass architecture:
1. **Pass 1 (Classification)**: LLM classifies the paper as empirical / theoretical / review / descriptive
2. **Pass 2 (Generation)**: Based on classification, combines `wiki_overview.md` + `wiki_empirical.md` (empirical papers) or `wiki_overview.md` only (non-empirical)

**Contributing discipline presets:** Pull requests for additional discipline presets are welcome. Create `wiki_overview.md` and `wiki_empirical.md` under `prompts/disciplines/<discipline>/`. See the economics preset for reference on the two-pass classification + qualitative assessment design.

**Designing custom prompts:** For fully custom prompt logic (including classifiers), using an AI agent is recommended. Ensure your custom directory includes `wiki_overview.md`; `wiki_empirical.md` is optional. The classifier `wiki_router.md` is shared across all modes from `prompts/`.

### Embedding Provider Switching & Cascade Fallback

Embedding supports a **cascade fallback** mechanism:
1. **Primary:** `embedding_main` (OpenAI-compatible, `EMBED_BASE_URL` + `EMBED_API_KEY`)
2. **Fallback:** `embedding_volcengine` (Volcengine multimodal, `VOLC_EMBED_*` variables) — [Volcengine Quick Start Guide](https://www.volcengine.com/docs/82379/1399008?lang=zh)
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
- `configs/wiki.yaml` — Wiki generation parameters

## Usage

### CLI Commands

After installation, use the `paper-compass` command directly:

```bash
# Interactive setup for LLM and embedding providers
paper-compass init

# Check for and apply updates
paper-compass update

# Validate configuration and API connectivity
paper-compass validate
```

Detailed help:

```bash
paper-compass init --help
paper-compass update --help
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
│   ├── wiki_gen.py          # Two-pass LLM wiki generation + prompt resolution
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
├── prompts/                # Wiki generation prompts
│   ├── wiki_overview.md    # General academic default prompt (v1.2.1)
│   ├── wiki_empirical.md   # General academic default prompt — empirical design (v1.2.1)
│   ├── wiki_router.md      # Paper type classifier
│   ├── wiki_econ_overview.md   # [Migration stub] → disciplines/economics/
│   ├── wiki_econ_empirical.md  # [Migration stub] → disciplines/economics/
│   └── disciplines/        # Discipline-specific prompt presets
│       └── economics/      # Economics-specific prompts
├── eval/                   # 12-query evaluation benchmark
├── wiki/                   # LLM-generated knowledge base
├── data/                   # Generated data (vectordb, texts, zotero-export)
├── tests/                  # pytest test suite (159 tests, all passing)
└── pyproject.toml          # Project metadata + dependencies
```

## Development

### Running Tests

```bash
pip install -e ".[dev]"
python3 -m pytest tests/ -v         # run all tests (159)
python3 -m pytest tests/ -x         # stop on first failure
python3 -m pytest tests/test_cli_arg_utils.py -v  # CLI argument parsing tests
python3 -m pytest tests/test_cli_configure.py -v  # Configuration command tests
python3 -m pytest tests/test_incremental_index.py -v  # incremental indexing tests
python3 -m pytest tests/test_wiki_prompt_resolution.py -v  # Wiki prompt resolution tests
```

### Running Evaluation

```bash
python eval/run_eval.py             # all 12 queries
python eval/run_eval.py -v          # verbose output
python eval/run_eval.py --mode strict  # strict key matching
```

## Inheritance & Innovation

paper-compass is not built from scratch. It stands on the shoulders of two excellent open-source projects:

### Inherited from [RAG-Assistant-for-Zotero](https://github.com/aahepburn/RAG-Assistant-for-Zotero)

Four core modules are adapted from RAG-Assistant-for-Zotero's proven implementations:

| Source Module | Adapted As | Purpose |
|---------------|------------|---------|
| `backend/pdf.py` | `pdf_extract.py` | PyMuPDF text extraction with pdfplumber fallback |
| `backend/zotero_dbase.py` | `zotero_sqlite.py` | Zotero SQLite reader with path resolution |
| `backend/embed_utils.py` | `embedder.py` | Multi-provider embedding (local + cloud) |
| `backend/vector_db.py` | `vector_store.py` | ChromaDB wrapper with BM25 hybrid search |

### Inspired by [llm-wiki-skill](https://github.com/sdyckjq-lab/llm-wiki-skill)

The LLM wiki philosophy of "compile once, maintain continuously" draws on Karpathy's llm-wiki methodology. The `save_to_wiki` MCP tool design also references its "conversation crystallization" concept — turning valuable agent conversations into permanent knowledge base pages.

### paper-compass original capabilities

Built on top of these foundations, paper-compass adds the following original designs:

- **MCP protocol integration**: 6 standard MCP tools following MCP 2024-11-05, compatible with any MCP-enabled agent framework
- **Incremental indexing**: Manifest-based change detection (text_sha1 + chunking_version + embedding_model_id), more precise than upstream's "new papers only" approach
- **Chinese academic retrieval**: Chinese word-segmentation-aware retrieval, economics discipline-specific wiki prompts
- **CLI configuration commands**: `paper-compass init` + `validate`, using lm-eval-harness `key=value` argument style
- **Wiki prompt customization system**: `WIKI_PROMPT` env var + discipline preset directories for discipline-tailored wiki generation
- **Multi-provider embedding cascade**: Three-tier automatic fallback (OpenAI → Volcengine → local bge-base), no code changes required
- **Formal evaluation benchmark**: 12-query retrieval quality evaluation with recall@K scoring and strict/relaxed modes
- **$ENV_VAR reference syntax**: API keys can reference existing environment variables, no plain-text secrets in `.env`

## Compatibility Note

paper-compass has been primarily tested on **Windows WSL (Ubuntu)** with Hermes Agent, with partial testing on **macOS**. It should work on both platforms. **Windows native** is expected to work as well, though not fully tested.

## Acknowledgments

- DeepSeek — Affordable tokens
- Hermes Agent

## Contributing

Contributions are welcome. Please open an issue for major changes.

## License

MIT
