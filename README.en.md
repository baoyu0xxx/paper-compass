# paper-compass

<div align="center">

**Turn your Zotero library into a dual-engine knowledge base for AI agents — RAG full-text retrieval + LLM wiki knowledge compilation**

[![version](https://img.shields.io/badge/version-1.4.1-5a6e5c?style=flat-square&labelColor=3a3026&color=5a6e5c)](https://github.com/baoyu0xxx/paper-compass)
![license](https://img.shields.io/badge/license-MIT-7a96a6?style=flat-square&labelColor=3a3026)
[![python](https://img.shields.io/badge/Python-3.12+-E8D5B5?style=flat-square&labelColor=3a3026&color=E8D5B5)](https://www.python.org/)
![MCP](https://img.shields.io/badge/protocol-MCP_2024--11--05-8db580?style=flat-square&labelColor=3a3026&color=8db580)

</div>

---

> 📖 **中文版**: [README.md](README.md)

## Overview

AI agents face a recurring problem when working with academic literature: reading full papers directly consumes a large number of tokens, while retrieval efficiency is often low. In single-paper conversational Q&A, long passages from the original text often need to be passed back and forth repeatedly, but the results are still not always satisfactory.

Among existing approaches, RAG retrieval is good at locating specific passages in the original text, while llm-wiki (Karpathy's idea of "compile knowledge once, maintain it continuously") uses an LLM to turn paper content into structured knowledge pages. But the two are rarely combined effectively in agent workflows: some systems only do vector retrieval, others only do knowledge compilation, and many of the attempts that combine both still offer limited agent support. Overall, what is missing is a practical agent-oriented literature workflow that treats the two as complementary.

**paper-compass is designed to fill that gap**: it turns a Zotero library into a knowledge base that AI agents can query directly, combining RAG full-text retrieval with LLM wiki knowledge compilation to address two common problems in academic literature work:

1. **Full-text content is not directly searchable** — beyond titles and keywords, research designs, empirical methods, and core findings inside PDFs are hard to locate quickly
2. **Reading notes do not accumulate well** — what you have read becomes fuzzy over time, and the next time you need it you often have to reopen the paper and read again

### Features

- **Agent-first**: all capabilities are exposed through MCP tools, so AI agents can call them directly — no GUI, no copy-pasting, no leaving the conversation
- **Dual-engine retrieval**: RAG (original-text retrieval, for "what exactly did that paper say?") and Wiki (knowledge compilation, for "what are this paper's methods and findings?") complement each other
- **LLM wiki knowledge compilation**: paper content is "compiled" into structured knowledge pages and maintained over time, following the llm-wiki idea of "generate once, reuse many times," reducing repeated token consumption in later conversations
- **Inheritance and extension**: core modules such as PDF extraction, embeddings, and vector storage adapt proven open-source implementations, while adding MCP integration, incremental indexing, and Chinese academic retrieval support

### Typical scenario

Ask directly in an agent conversation:

> "What papers do we have on corporate digital transformation? What are the mainstream research methods, and what proxy variables are commonly used?"

The agent locates relevant passages in your paper library and returns quoted evidence with source citations and page numbers.

## Core Capabilities

| Feature | Description |
|---------|-------------|
| 🔌 **MCP toolset** | 7 public MCP tools — `search_library`, `search_passages`, `ask_research`, `get_paper_metadata`, `get_passage_context`, `get_wiki_page_section`, `save_to_wiki` — plus `search_wiki` as an advanced probing entrypoint, following MCP 2024-11-05 |
| 📝 **LLM wiki generation** | Automatically generates structured knowledge pages for papers (research question, core findings, methods and data, theoretical framework) with a two-stage classifier and customizable prompts |
| 🔍 **Dual-mode passage retrieval** | Dense semantic vectors and BM25 keyword retrieval run in parallel, balancing conceptual similarity and exact-term matching |
| 📊 **Incremental indexing** | Manifest-based change detection updates only added or modified papers instead of rebuilding everything |
| 🇨🇳 **Chinese academic support** | Chinese segmentation-aware retrieval and scoring, plus economics preset wiki prompts for Chinese-language research |
| 🔄 **Embedding cascade fallback** | OpenAI-compatible (`EMBED_*`) → Volcengine (`VOLC_EMBED_*`) → local model (`bge-base` by default, configurable via `LOCAL_EMBED_MODEL`) |

## Quick Start

### Option A: Install from GitHub Release (Recommended)

The recommended path is to install the published wheel from GitHub Release directly:

```bash
python3 -m pip install \
  https://github.com/baoyu0xxx/paper-compass/releases/download/v1.4.1/paper_compass-1.4.1-py3-none-any.whl

# Interactive setup
paper-compass init

# Verify configuration and API connectivity
paper-compass validate

# Incrementally sync Zotero / index / wiki data
paper-compass sync \
  --db-source-path /path/to/zotero.sqlite \
  --storage-path /path/to/storage
```

If you prefer a manual deployment or a development environment install, use "From Source (Developers)" below.

### Option B: Agent Prompt Deployment

Copy the following prompt to your AI agent — it will handle the full paper-compass setup automatically:

<details>
<summary>👋 Copy this prompt to your agent</summary>

> Please deploy paper-compass under `$HOME/projects/` (create the directory if it doesn't exist). Follow these steps:
>
> 1. Clone the repo: `git clone https://github.com/baoyu0xxx/paper-compass.git` into `$HOME/projects/paper-compass`
> 2. Bootstrap the repo-local managed runtime: `cd $HOME/projects/paper-compass && python3 scripts/bootstrap_runtime.py`
> 3. Activate `.venv` (Windows: `.venv\\Scripts\\activate`; POSIX: `source .venv/bin/activate`), then run `paper-compass init` for interactive LLM and Embedding API configuration
> 4. Run `paper-compass validate` to verify connectivity
> 5. Export your Zotero SQLite database path as `ZOTERO_SQLITE_PATH` env var, then run `python scripts/sync_zotero.py --extract-text`
> 6. Run `python scripts/build_index.py --library data/zotero-export/library.json --full-rebuild`
> 7. (Optional) Run `python scripts/ingest_to_wiki.py --limit 3 --workers 1` to test wiki generation
> 8. Run `paper-compass-healthcheck --smoke` to verify all subsystems
> 9. Finally, add the MCP config to your current agent framework (for Hermes, point `command` directly at the repo-local `.venv` `paper-compass-mcp` console script and pass `--mcp`; do not keep using legacy WSL `/mnt/d/...` paths or a system Python)
>
> Confirm each step before proceeding to the next.

</details>

For more capable agents, a one-line instruction is also enough:

```text
Please clone https://github.com/baoyu0xxx/paper-compass.git, bootstrap the repo-local .venv, run paper-compass init for interactive configuration, verify the setup, and sync my Zotero library.
```

### Option C: From Source (Developers)

```bash
# 1. Clone the repository
git clone https://github.com/baoyu0xxx/paper-compass.git
cd paper-compass
python3 scripts/bootstrap_runtime.py

# 2. Activate the repo-local .venv (choose one)
# Windows:
# .venv\\Scripts\\activate
# POSIX:
# source .venv/bin/activate

# 3. Configure environment variables — interactive (recommended)
paper-compass init

#    Or edit manually:
#    cp .env.example .env
#    Edit .env — fill in the API keys for the LLM and embedding provider

# 4. Verify configuration connectivity
paper-compass validate

# 5. Prepare data
python scripts/sync_zotero.py --extract-text
# → auto-discovery order: explicit --db-path > ZOTERO_SQLITE_PATH > default Zotero dirs > backup dirs
# → data/zotero-export/library.json + data/texts/*.txt

Auto-discovery only selects Zotero's official `zotero.sqlite`. The legacy `zotero_readonly.sqlite` filename is not auto-discovered because long-lived manual snapshots can become stale. It remains accepted only when explicitly passed via `--db-source-path` / `--db-path` for short-term compatibility. When auto-discovery resolves a default Zotero profile, `--snapshot-db auto` creates a runtime SQLite snapshot under `data/state/zotero-snapshots/` and reads that snapshot instead of directly reading the live Zotero profile.

#    If the database and storage/ are not in the same directory:
#    python scripts/sync_zotero.py --db-path /path/to/zotero.sqlite --storage-path /path/to/storage --extract-text

# 6. Routine incremental data sync (recommended)
paper-compass sync \
  --db-source-path /path/to/zotero.sqlite \
  --storage-path /path/to/storage
# → runs Zotero sync, incremental paper indexing, incremental wiki generation, and wiki indexing in sequence
# → writes data/state/last_sync.json automatically
# → blocks writes and suggests a rebuild if vectordb is dirty or corrupted

# 7. Run individual stages manually (only when you need finer control)
scripts/pc-index-full.sh
scripts/pc-index-incremental.sh
scripts/pc-wiki-build.sh --limit 3
scripts/pc-wiki-index.sh

# 8. Long-running wiki generation (optional; hundreds of papers often take hours)
scripts/pc-wiki-ingest-bg.sh
# View logs:
tail -f data/logs/wiki_gen.log

# 9. Verify
paper-compass-healthcheck --smoke
python eval/run_eval.py -v
```

These `scripts/pc-*.sh` wrappers are intentionally thin: they pin repo root, provide sane default paths, and reduce long-command typing errors.
If you prefer direct Python entrypoints, `scripts/build_index.py` and `scripts/ingest_to_wiki.py` remain supported.

Starting with v1.4.0, installed `paper-compass-mcp` and `paper-compass-healthcheck` entrypoints point directly to package-resident implementations. The historical packaged `scripts.*` compatibility shims have been removed; use the current console scripts or the repository `scripts/` files directly.

## Updating

Distinguish three kinds of updates:

- `python3 -m pip install <GitHub Release wheel URL>`: install or switch to a specific published version
- `paper-compass update`: update a git-clone installation of the repository code
- `paper-compass sync`: update Zotero / text / vector index / wiki data

### Release Upgrade (Recommended)

If you installed paper-compass from GitHub Release, point pip directly to the target wheel URL:

```bash
python3 -m pip install --upgrade \
  https://github.com/baoyu0xxx/paper-compass/releases/download/v1.4.1/paper_compass-1.4.1-py3-none-any.whl
```

To install another published version later, replace the version in the URL accordingly. Published releases can be listed with:

```bash
gh release list --repo baoyu0xxx/paper-compass --limit 10
```

### Data Incremental Update (Recommended)

```bash
# Standard incremental update
paper-compass sync \
  --db-source-path /path/to/zotero.sqlite \
  --storage-path /path/to/storage

# Preview stages only
paper-compass sync --dry-run

# If the last run left vectordb in a dirty state, rebuild papers with backup
paper-compass sync \
  --rebuild papers \
  --backup-corrupted-db \
  --db-source-path /path/to/zotero.sqlite \
  --storage-path /path/to/storage
```

`paper-compass sync` will:
- check `data/vectordb/` for journal / WAL / manifest corruption before writing
- run `sync_zotero.py` → `build_index.py --incremental --prune-deleted` → `ingest_to_wiki.py --skip-existing` → `build_index.py --wiki`
- write `data/state/last_sync.json` to record the latest run status
- stop writes and suggest a rebuild if vector-store corruption is detected

If you only want one stage manually, use the shell wrappers from the repo:

```bash
# full papers index rebuild
scripts/pc-index-full.sh

# incremental papers index
scripts/pc-index-incremental.sh

# wiki generation in foreground
scripts/pc-wiki-build.sh --limit 3

# wiki generation in background
scripts/pc-wiki-ingest-bg.sh

# wiki vector index
scripts/pc-wiki-index.sh
```

These wrappers are stage-level convenience commands only; append extra arguments when needed and pass them through to the underlying Python scripts.

### Automatic Code Update (git-clone installs only)

```bash
# Check whether a new version is available
paper-compass update --check

# Update to the latest version
paper-compass update

# Update to a specific version
paper-compass update --version v1.4.1

# Simulate an update (preview without executing)
paper-compass update --dry-run
```

`paper-compass update` automatically:
- fetches the latest code and switches to the target version
- syncs the repo-local `.venv` so editable installs and dependencies follow the checked-out code
- detects breaking changes (new required env vars, config-format changes, etc.) and warns you
- runs `paper-compass validate` to verify API connectivity
- runs a smoke-test check

If you installed paper-compass from a GitHub Release wheel instead of a git clone, `paper-compass update` does not apply; use `pip install --upgrade` with the corresponding release URL instead.

### Manual Update

If automatic update is unavailable, you can update manually:

```bash
git fetch origin --tags
git checkout v1.4.1         # or git pull origin main
python3 scripts/bootstrap_runtime.py
paper-compass validate        # verify that the configuration still works
python3 -m pytest tests/ -x   # ensure tests pass
```

### Upgrade Notes

<details>
<summary>Cross-version upgrade notes (click to expand)</summary>

> ⚠️ **Cross-version upgrades** (for example, v1.1.x → v1.2.x) may involve configuration-format changes and environment-variable adjustments.
>
> - The `.env` file is gitignored, so upgrades will not overwrite private configuration
> - After upgrading, pay attention to ⚠ warnings in terminal output and check whether new environment variables need to be added
> - If `validate` fails after upgrade, run `paper-compass init --force` to regenerate `.env`
> - It is recommended to back up before upgrading: `cp .env .env.backup`

</details>

## Installation

The three main paths have already been introduced in Quick Start: Release install, Agent prompt deployment, and source installation. This section collects installation requirements and follow-up notes after installation.

### Prerequisites

| Requirement | Notes |
|-------------|-------|
| Python ≥ 3.12 | Check with `python3 --version` |
| Zotero library | Optional — pre-extracted text files are also supported |
| LLM API key | Wiki generation requires an OpenAI-compatible endpoint (`LLM_BASE_URL` + `LLM_API_KEY`) |
| Embedding API key | OpenAI-compatible and Volcengine multimodal embedding are supported |

### Available commands after installation

```bash
paper-compass --help
paper-compass init
paper-compass search --help
paper-compass status
paper-compass validate
paper-compass-healthcheck --help
paper-compass-mcp --help
```

## Configuration

### Environment Variables

Copy `.env.example` to `.env` and fill in your values, or use `paper-compass init` to generate it automatically:

| Variable | Required | Description |
|----------|----------|-------------|
| `LLM_BASE_URL` | Yes | LLM API base URL |
| `LLM_API_KEY` | Yes | LLM API key (supports `$ENV_VAR` reference) |
| `LLM_MODEL` | No | Model name (optional, defaults are defined in `providers.yaml`) |
| `EMBED_BASE_URL` | Yes* | Embedding API base URL (OpenAI-compatible) |
| `EMBED_API_KEY` | Yes* | Embedding API key |
| `EMBED_MODEL` | No | Embedding model name (optional, defaults are defined in `providers.yaml`) |
| `VOLC_EMBED_BASE_URL` | No | Volcengine multimodal embedding endpoint (alternative) |
| `VOLC_EMBED_API_KEY` | No | Volcengine API key |
| `VOLC_EMBED_MODEL` | No | Volcengine embedding model endpoint ID |
| `LOCAL_EMBED_MODEL` | No | Local embedding fallback model: `bge-base` (default), `specter`, or `minilm` |
| `WIKI_PROMPT` | No | Wiki prompt style: `default` (general academic), `economics` (economics preset), or a custom path |

> * If you configure a cloud embedding provider, you must provide the corresponding API settings. If no cloud provider is configured, the system falls back to `LOCAL_EMBED_MODEL` (default: `bge-base`).

#### $ENV_VAR Reference Syntax

API keys support `$ENV_VAR` reference syntax, so you do not need to store plain-text secrets in `.env`:

```env
LLM_API_KEY=$OPENAI_API_KEY
EMBED_API_KEY=$MY_EMBED_KEY
VOLC_EMBED_API_KEY=$VOLC_API_KEY
```

At runtime, these are resolved by `_resolve_env_value()` in `config.py`. If the referenced environment variable is not set, the literal `$VAR` string is preserved.

### Verify Configuration Connectivity

```bash
paper-compass validate
```

Example output:

```text
  config: llm=openai | https://api.openai.com/v1 | gpt-4o
  config: embedding_role=embedding | source=shared | selected=embedding_main | active=embedding_main
  config: embedding_candidates=embedding_main -> embedding_volcengine -> local (bge-base)
  ✓ dotenv: OK
  ✓ llm: OK (model: gpt-4o, 1.2s, response: 15 chars)
  ✓ embed: OK (provider: embedding_main, model: text-embedding-3-small, dim=1536, 0.8s)
```

`paper-compass validate` now prints the resolved embedding runtime explicitly: the shared role, the selected cloud provider, the candidate chain, and the local fallback that will be used when no cloud provider is configured. This keeps CLI output aligned with the actual runtime semantics used by `build_index.py`.

### Wiki Prompt Selection

`paper-compass init` guides you to choose a wiki prompt style after configuring the LLM and embedding providers.

**Three modes:**

| Mode | WIKI_PROMPT | Description |
|------|-------------|-------------|
| Default (general academic) | `default` | General academic prompts suitable for different disciplines |
| Discipline preset | `economics`, etc. | Prompts optimized for specific disciplines (currently: economics) |
| Custom path | `/path/to/prompts` | Use your own prompt files |

To switch prompts later, edit `WIKI_PROMPT` in `.env`:

```env
WIKI_PROMPT=default       # default general academic prompts
WIKI_PROMPT=economics     # economics discipline prompts
WIKI_PROMPT=/home/user/my-prompts  # custom prompts
```

<details>
<summary>Click to view wiki-generation architecture and custom prompt details</summary>

**Two-stage generation architecture:** wiki generation follows a "classify → generate" workflow:
1. **Pass 1 (classification)**: the LLM classifies a paper as empirical / theoretical / review / descriptive
2. **Pass 2 (generation)**: depending on the classification, it combines `wiki_overview.md` + `wiki_empirical.md` (empirical papers) or uses only `wiki_overview.md` (non-empirical papers)

**Contributing discipline presets:** contributions of prompts for other disciplines are welcome. Create `wiki_overview.md` and `wiki_empirical.md` under `prompts/disciplines/<discipline>/` and submit a pull request.

**Custom prompts:** make sure your custom directory contains `wiki_overview.md`, and optionally `wiki_empirical.md`. The classifier `wiki_router.md` is shared across all modes from the main `prompts/` directory.

If some prompt files are missing, the system no longer drifts into implicit fallback silently. The runtime now marks the prompt bundle as `degraded`, and `paper-compass status` reports both the missing state and the fallback reason explicitly.

</details>

### Embedding Provider Switching and Cascade Fallback

The embedding layer supports **cascade fallback**:
1. **Primary** `embedding_main` (OpenAI-compatible, `EMBED_BASE_URL` + `EMBED_API_KEY`)
2. **Fallback** `embedding_volcengine` (Volcengine multimodal, `VOLC_EMBED_*`) — [Volcengine quick-start guide](https://www.volcengine.com/docs/82379/1399008?lang=zh)
3. **Final fallback** local `bge-base` model (no API required)

Configure the relevant environment variables to enable the cascade automatically. `paper-compass validate` reports the local fallback path explicitly when no cloud embedding provider is configured, and `paper-compass status` shows the same embedding runtime view (shared role, selected provider, active provider, candidate chain, and resolved provider registry) so the CLI no longer drifts from the real runtime behavior.

If you want to pin a cloud provider, point the single shared embedding role in `configs/providers.yaml` to that provider:

```yaml
roles:
  embedding: embedding_volcengine   # papers and wiki share the same embedding provider
```

The legacy split embedding-role surface has been removed from default configs. Paper chunks and wiki chunks must remain in the same embedding space, so the config now exposes one shared `roles.embedding` entry.

### Advanced Configuration

LLM model choices, Chroma collection naming, MCP tracing, and related settings are stored in `configs/`. See the comments inside:

- `configs/providers.yaml`
- `configs/paths.yaml`
- `configs/mcp.yaml`
- `configs/wiki.yaml`

## Usage

### CLI Commands

After installation, the `paper-compass` command is available directly:

```bash
# Interactive configuration of the LLM and embedding provider
paper-compass init

# Unified local retrieval entrypoint (v1.4.0 was smoke-tested on a local library with 417 records and 406 wiki pages)
paper-compass search wiki --query "family-firm succession" --limit 3
# → returns relevant wiki pages such as intergenerational succession and family-firm diversification/risk-taking

paper-compass search library --query "family-firm succession" --limit 5
# → returns matching records from the local library.json metadata

paper-compass search passages --query "family-firm succession labor structure" --search-mode hybrid --limit 3
# → combines full-text keyword/BM25 retrieval with semantic vector passages

paper-compass search ask --query "How does family-firm succession affect labor structure?" --force-mode hybrid --max-sources 3
# → assembles wiki, library, and PDF evidence into a sourced retrieval result

# Inspect resolved configuration / data / vectordb state
paper-compass status
# → includes embedding role / active provider / cascade, plus whether the wiki prompt bundle is degraded
# → also includes sync.last_sync / sync.lock / last_successful_zotero_source for sync diagnostics

# One-command sync for Zotero / vector index / wiki data
paper-compass sync --db-source-path /path/to/zotero.sqlite --storage-path /path/to/storage

# Code update
paper-compass update

# Verify configuration and API connectivity
paper-compass validate
```

For full usage details:

```bash
paper-compass init --help
paper-compass search --help
paper-compass status --help
paper-compass sync --help
paper-compass update --help
paper-compass validate --help
```

### CLI Scripts

| Script | Purpose | Key arguments |
|--------|---------|---------------|
| `scripts/sync_zotero.py` | Zotero SQLite → `library.json` + text extraction | `--extract-text`; failure report at `data/logs/pdf_extract_failures.jsonl` |
| `scripts/build_index.py` | Build ChromaDB vector indexes (papers + wiki) | `--full-rebuild`, `--incremental`, `--prune-deleted`, `--wiki`, `--dry-run --explain-changes --sample-size N` |
| `scripts/ingest_to_wiki.py` | Batch LLM wiki generation | `--skip-existing`, `--workers 10`, `--limit N`, `--wiki-upsert-mode` |
| `scripts/run_mcp_server.py` | MCP repo-local compatibility shim (delegates to `paper_compass.mcp_entrypoint:main`) | `--mcp`, `--tool <name> --query "..."` |
| `scripts/healthcheck.py` | Subsystem health check | `--smoke` |

#### Build Indexes

```bash
# Full rebuild (clear and re-embed all papers)
python scripts/build_index.py --library data/zotero-export/library.json --full-rebuild

# Incremental update (only update changed papers)
python scripts/build_index.py --library data/zotero-export/library.json --incremental

# Dry-run locally and explain metadata-only / path-only changes before embedding
python scripts/build_index.py \
  --library data/zotero-export/library.json \
  --incremental \
  --dry-run \
  --explain-changes \
  --sample-size 5

# Index wiki pages
python scripts/build_index.py --wiki --wiki-root ./wiki
```

`--explain-changes` reports top metadata-only reasons (for example `tags changed` or `collections changed`) and, with `--sample-size`, provides sampled diffs before any embedding-heavy run.

#### Generate Wiki Pages

```bash
# Process all pages that have not yet been generated (10 concurrent workers)
python scripts/ingest_to_wiki.py --skip-existing --workers 10

# Prefer key-aware unique writeback when titles may collide
python scripts/ingest_to_wiki.py --skip-existing --workers 10 --wiki-upsert-mode create_unique

# Try 3 papers first
python scripts/ingest_to_wiki.py --limit 3 --workers 1

# Resume after interruption
python scripts/ingest_to_wiki.py --skip-existing --workers 10
```

`--wiki-upsert-mode` supports:
- `create`: fail on same-slug conflicts
- `create_unique`: same slug + different Zotero key becomes `YYYY-MM-DD-slug-key.md`
- `replace_if_same_key`: overwrite only when the existing page belongs to the same Zotero key
- `replace_if_same_slug`: overwrite by slug directly (use only when intentional)

### Recovery and diagnostics

```bash
# Inspect sync state, stale lock detection, and the last successful Zotero source
paper-compass status --json

# Remove a leftover sync.lock without running stages yet
paper-compass sync --force-unlock

# Review structured PDF extraction / chunk-preparation failures
cat data/logs/pdf_extract_failures.jsonl
```

When `paper-compass sync --dry-run` or `build_index.py --dry-run` shows unexpectedly large metadata-only churn, prefer `--explain-changes` first instead of immediately allowing a large embedding run.

### MCP Integration

#### Configure Hermes Agent

Point the `paper-compass` MCP server directly at the repo-local managed `.venv` **console script** in `config.yaml`:

```yaml
mcp_servers:
  paper-compass:
    command: /path/to/paper-compass/.venv/bin/paper-compass-mcp
    args: ["--mcp"]
    connect_timeout: 60
    timeout: 120
```

Before configuring MCP, run `python3 scripts/bootstrap_runtime.py` once. `paper-compass-mcp --mcp` now explicitly checks that the current interpreter is the repository-local `.venv`; if it still points at a system Python, it fails fast instead of silently falling back.

#### Configure Claude Desktop

```json
{
  "mcpServers": {
    "paper-compass": {
      "command": "D:\\pyproject\\paper-compass\\.venv\\Scripts\\paper-compass-mcp.exe",
      "args": ["--mcp"]
    }
  }
}
```

If you run on POSIX / WSL instead, replace those paths with the corresponding `.venv/bin/paper-compass-mcp`.

#### CLI Tool Mode

Prefer the package entrypoint `paper-compass-mcp --tool ...` for local CLI usage. It shares the same `mcp_entrypoint` logic as the compatibility wrapper `python scripts/run_mcp_server.py --tool ...`; the package entrypoint is the recommended form, while the script wrapper is kept for older workflows.

```bash
# Common public workflow
paper-compass-mcp --tool search_library --query "author name"
paper-compass-mcp --tool search_passages --query "specific passage content" --search-mode keyword
paper-compass-mcp --tool ask_research --query "research question" --max-sources 7 --db-path data/vectordb

# Handle-first / drill-down workflow
paper-compass-mcp --tool search_passages --query "specific passage content" --search-mode hybrid --db-path data/vectordb --text-dir data/texts --library-path data/zotero-export/library.json
paper-compass-mcp --tool get_passage_context --passage-handle passage:ABC123:p12:hybrid:0 --window section
paper-compass-mcp --tool get_wiki_page_section --wiki-handle wiki:wiki/topics/family-succession.md#section=mechanism
paper-compass-mcp --tool get_paper_metadata --paper-handle paper:ZOTERO_KEY

# Two-phase writeback: preview first, then commit
paper-compass-mcp --tool save_to_wiki --title "Research note" --content "Draft content" --dry-run
paper-compass-mcp --tool save_to_wiki --title "Research note" --content "Draft content" --commit

# Advanced / diagnostic use: probe the wiki index directly (not exposed in default MCP tools/list)
paper-compass-mcp --tool search_wiki --query "family business succession"

# Compatibility wrapper (non-preferred, but delegates to the same main)
python scripts/run_mcp_server.py --tool search_passages --query "specific passage content" --search-mode keyword
```

#### NumPy 2.x Compatibility

v1.2.5 fixed a deprecated `np.NaN` alias usage in the search path, avoiding errors such as:

```text
`np.NaN` was removed in the NumPy 2.0 release. Use `np.nan` instead.
```

If you see this kind of error when calling search tools through an agent or MCP subprocess, upgrading to v1.2.5+ is sufficient.

## Architecture

### Pipeline

```text
Zotero SQLite + PDF
  → sync_zotero.py → library.json + data/texts/*.txt
  → build_index.py → ChromaDB vector collections (papers + wiki)
  → ingest_to_wiki.py → LLM → wiki/papers/*.md
  → build_index.py --wiki → ChromaDB wiki collection
  → paper-compass-mcp (canonical) / run_mcp_server.py (repo-local shim) → expose 7 public MCP tools + 1 advanced wiki probing entrypoint to AI agents
```

### MCP Tools

| Tool | Description | Retrieval mode |
|------|-------------|----------------|
| `search_library` | Returns compact paper candidates (`paper_handle` + minimal metadata) and serves as the default paper discovery entrypoint | text |
| `search_passages` | Returns compact evidence candidates (`passage_handle` + snippet) for later expansion | vector + BM25 |
| `ask_research` | Default research QA entrypoint; returns an answer plus `evidence_digest` for follow-up drill-down | hybrid |
| `get_passage_context` | Expands a `passage_handle` into longer local context | exact readback |
| `get_wiki_page_section` | Reads the full wiki page or section addressed by a `wiki_handle` | exact readback |
| `get_paper_metadata` | Looks up a single paper by `paper_handle`, key, DOI, or exact title | exact |
| `save_to_wiki` | Preview first (dry-run by default), then write with `commit=true` | — |
| `search_wiki` (advanced) | Probes the wiki semantic index directly; callable from local CLI but hidden from default MCP `tools/list` | vector |

### Project Structure

```text
paper-compass/
├── src/paper_compass/       # core library
│   ├── cli/                 # CLI commands (init, sync, update, validate)
│   │   ├── __init__.py      # main entry point: paper-compass
│   │   ├── configure.py     # paper-compass init
│   │   ├── sync_data.py     # paper-compass sync
│   │   ├── update.py        # paper-compass update
│   │   └── validate.py      # paper-compass validate
│   ├── search.py            # search_library, search_passages, vector search
│   ├── router.py            # multi-layer routing for ask_research
│   ├── mcp_server.py        # MCP tool handling and dispatch
│   ├── mcp_contracts.py     # tool schema definitions
│   ├── vector_store.py      # ChromaDB wrapper + BM25 hybrid search
│   ├── embedder.py          # multi-provider embedding with fallback
│   ├── wiki_gen.py          # two-stage LLM wiki generation + prompt resolution
│   ├── wiki_store.py        # thread-safe wiki writeback
│   ├── env_utils.py         # .env loading (always overwrite stale values)
│   ├── config.py            # YAML config loading + $ENV_VAR resolution
│   ├── types.py             # response dataclasses
│   ├── index_manifest.py    # fingerprint-based incremental indexing
│   ├── index_health.py      # vectordb health checks and corruption detection
│   ├── logging.py           # JSONL trace logging
│   ├── pipeline_sync.py     # one-command data-sync orchestration
│   ├── pdf_extract.py       # PyMuPDF + pdfplumber text extraction
│   └── zotero_sqlite.py     # Zotero SQLite reading
├── scripts/                 # CLI entry points and standalone scripts
├── configs/                 # YAML config templates
├── prompts/                 # wiki-generation prompts
├── eval/                    # retrieval evaluation benchmark
├── wiki/                    # generated knowledge base
├── data/                    # generated data (vectordb, texts, zotero-export)
├── tests/                   # pytest suite
└── pyproject.toml           # project metadata and dependencies
```

## Development and Debugging

<details>
<summary>Click to expand test and evaluation commands</summary>

### Run tests

```bash
python3 scripts/bootstrap_runtime.py

# Windows:
.venv/Scripts/python.exe -m pytest tests/ -v
.venv/Scripts/python.exe -m pytest tests/ -x

# POSIX:
.venv/bin/python -m pytest tests/ -v
.venv/bin/python -m pytest tests/ -x
```

### Run evaluation

```bash
python eval/run_eval.py
python eval/run_eval.py -v
python eval/run_eval.py --mode strict
```

</details>

## References and Acknowledgments

paper-compass builds on the following open-source projects:

- [RAG-Assistant-for-Zotero](https://github.com/aahepburn/RAG-Assistant-for-Zotero) — PDF extraction, Zotero reading, embedding, and vector storage modules are adapted from this project
- [llm-wiki](https://github.com/karpathy/llm-wiki) (Andrej Karpathy) — the methodology of "compile knowledge once, maintain it continuously"

Major additions on top of those foundations:
- MCP protocol integration (7 public tools + 1 advanced `search_wiki` entrypoint, MCP 2024-11-05)
- Incremental indexing (fingerprint-based change detection)
- Chinese academic retrieval adaptation and discipline-specific prompt presets
- Multi-provider embedding cascade fallback
- CLI configuration commands (`init` + `validate`)
- Formal evaluation benchmark (12-query retrieval-quality evaluation)

## Changelog

| Version | Date | Notes |
|---------|------|-------|
| v1.4.1 | 2026-06-23 | **Incremental sync hardening, stage 2** — wiki writeback is now key-aware (`--wiki-upsert-mode`); incremental dry-run can explain metadata-only churn via `--explain-changes --sample-size N`; both `sync_zotero.py` and `build_index.py` write structured failures to `data/logs/pdf_extract_failures.jsonl`; `paper-compass status` and `sync --force-unlock` provide clearer recovery guidance |
| v1.4.0 | 2026-06-03 | **Repo-local managed runtime + fail-fast MCP startup** — added `scripts/bootstrap_runtime.py` and `src/paper_compass/runtime_env.py` to manage a repository-local `.venv`; wired runtime status into `paper-compass init / update / status / healthcheck`; made MCP entrypoints and shell wrappers validate the interpreter explicitly and fail fast on misconfiguration; raised the Python baseline to `>=3.12`; updated README and MCP configuration guidance to the managed-runtime model |
| v1.2.7 | 2026-05-15 | **Data sync command + vectordb health guard** — added `paper-compass sync`, integrating `sync_zotero.py`, incremental paper indexing, incremental wiki generation, and wiki vectorization into one command; added `data/state/last_sync.json` and `data/state/sync.lock`; checks journal/WAL/manifest/readability before writes; supports `--rebuild {papers,wiki,all}` and `--backup-corrupted-db` recovery paths |
| v1.2.6 | 2026-05-13 | **MCP cold-start optimization** — removed `clear_system_cache()`-triggered double loading; introduced a shared `PersistentClient`; prewarms wiki and paper collections after MCP handshake |

## Compatibility

paper-compass has been tested most thoroughly under **Windows WSL (Ubuntu)** with Hermes Agent, and partially on **macOS**. It is expected to work on both platforms. **Native Windows** is also expected to work, but has not yet been tested thoroughly.

## Contributing

Contributions are welcome. For major changes, please open an issue first to discuss the proposed changes before submitting a pull request.

## Thanks

- DeepSeek — affordable tokens
- Hermes Agent

## License

MIT
