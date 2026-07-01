# AGENTS.md — Deploying paper-compass

This document guides an AI agent (Claude Code, Codex, Hermes, etc.) through deploying `paper-compass` from a fresh clone to a working MCP service.

## Project Summary

`paper-compass` is a personal academic paper retrieval infrastructure. It takes a Zotero PDF library, generates structured wiki pages via LLM, builds vector search indices, and exposes 6 MCP tools for AI agent consumption.

**Tech stack**: Python ≥3.11, ChromaDB, PyMuPDF, Volcengine/OpenAI-compatible embeddings with local fallback, OpenAI-compatible LLM endpoint.

## Step-by-Step Deployment

### 1. Clone and install

```bash
git clone https://github.com/baoyu0xxx/paper-compass.git
cd paper-compass
pip install -e .
pip install -e ".[dev]"   # for tests
```

Once installed, the `paper-compass` CLI is available (see step 2). High-frequency commands now include `paper-compass search ...` for local retrieval and `paper-compass status` for runtime inspection.

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

The LLM endpoint must be OpenAI-compatible (chat/completions format). Model is configured via the `LLM_MODEL` env var in `.env` (no hardcoded fallback — missing model raises an error).

Embedding defaults to standard OpenAI-compatible format (`text-embedding-3-small`). To use Volcengine, set `VOLC_EMBED_*` variables instead. The runtime cascade is `EMBED_*` → `VOLC_EMBED_*` → local fallback (`bge-base` by default, override with `LOCAL_EMBED_MODEL`).

**Option C — Non-interactive (scripted):**

```bash
paper-compass init \
  --llm-args base_url=https://api.openai.com/v1,model=gpt-4o \
  --embed-args api_style=volcengine,model=doubao-embedding-vision-250615
```

### 3. Verify configuration

```bash
paper-compass validate
```

Should show all green (✓) for dotenv, llm, and embed checks.

### 4. Prepare data

**Option A — from Zotero SQLite:**

The `sync_zotero.py` script reads Zotero's SQLite database through a read-only SQLite URI (`mode=ro`) with `PRAGMA query_only=ON`. Resolution order is: explicit `--db-path` → `ZOTERO_SQLITE_PATH` → default Zotero data directories → optional backup roots (for example `ZOTERO_BACKUP_ROOT` if configured). Auto-discovery only selects Zotero's official `zotero.sqlite`; legacy `zotero_readonly.sqlite` is accepted only when explicitly passed via `--db-path` / `--db-source-path`. You can override the inferred `storage/` path with `--storage-path`.

```bash
python scripts/sync_zotero.py --extract-text
```

This produces `data/zotero-export/library.json` and `data/texts/*.txt`.

When auto-discovery resolves a default Zotero profile, `--snapshot-db auto` creates a runtime SQLite snapshot under `data/state/zotero-snapshots/` and reads that snapshot instead of directly reading the live Zotero profile. Explicit backup/env paths are treated as non-live unless configured otherwise. This does not write to or modify the original Zotero SQLite database. Use `python scripts/sync_zotero.py --dry-run` to inspect the resolved database, storage directory, and snapshot policy before syncing.

If the SQLite file is not found automatically, you can specify it explicitly:
```bash
python scripts/sync_zotero.py --db-path /path/to/zotero.sqlite --extract-text
```

If the SQLite file and `storage/` directory are not siblings, override both:
```bash
python scripts/sync_zotero.py \
  --db-path /path/to/zotero.sqlite \
  --storage-path /path/to/storage \
  --extract-text
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

### 5. 日常数据同步（推荐）

推荐优先使用一键命令，而不是手工串多个脚本：

```bash
paper-compass sync \
  --db-source-path /path/to/zotero.sqlite \
  --storage-path /path/to/storage
```

这个命令会顺序执行：
1. `sync_zotero.py --extract-text`
2. `build_index.py --incremental --prune-deleted`
3. `ingest_to_wiki.py --skip-existing`
4. `build_index.py --wiki`

并额外提供：
- `paper-compass sync --dry-run` 预览同步命令与论文索引差异；其中 Zotero 阶段只解析路径，不创建输出目录或读取 SQLite
- 如需解释 dry-run 中为什么出现大量 metadata-only 变化，可单独运行 `python scripts/build_index.py --library data/zotero-export/library.json --incremental --dry-run --explain-changes --sample-size 5`
- 论文增量索引以 PDF/文本内容 fingerprint 为核心，metadata-only / path-only 变化只更新元数据或 manifest，不触发重嵌入
- `data/vectordb/` 健康检查（journal / wal / manifest / Chroma 可读性）
- `data/state/last_sync.json` 状态记录
- 损坏时阻断写入并给出恢复建议
- `--rebuild papers|wiki|all` + `--backup-corrupted-db` 恢复路径
- 若 `status` 显示 sync lock 卡住，可先用 `paper-compass status --json` 查看 `sync.lock` / `last_sync`，再按需执行 `paper-compass sync --force-unlock`

### 6. 手动执行各阶段（仅在需要细粒度控制时）

```bash
scripts/pc-index-full.sh
# 完整增量更新便捷包装（实际转发到 `paper-compass sync`）
scripts/pc-index-incremental.sh
```

`scripts/pc-index-full.sh` 仍是 papers 全量重建；`scripts/pc-index-incremental.sh` 已改为完整增量更新入口，会刷新快照并继续推进 papers/wiki 各阶段同步。

如果只是单独补 wiki 页面或重建 wiki 向量索引，可优先用：

```bash
scripts/pc-wiki-build.sh --limit 3
scripts/pc-wiki-index.sh
```

这些 shell 只负责：固定 repo root、补默认路径、透传附加参数；其中 `scripts/pc-index-incremental.sh` 代表完整 `sync` 语义，
不要在 agent 操作里把它们当成新的复杂参数层。

**Pitfall**: If `build_index.py` skips papers with "missing PDF" even when text files exist, check that:
1. `text_file` paths in `library.json` are valid
2. You have the latest code (v1.0.1+ fixed the PDF-first check)

If text extraction or chunk preparation partially fails, inspect:

```bash
cat data/logs/pdf_extract_failures.jsonl
```

该报告会记录 `sync_zotero.py` / `build_index.py` 遇到的 `empty text`、`extract error`、`missing text`、`no valid chunks` 等失败项。

### 6. Generate wiki pages (optional but recommended)

```bash
# Test with 3 papers first
python scripts/ingest_to_wiki.py --limit 3 --workers 1

# Prefer key-aware unique writeback when titles may collide
python scripts/ingest_to_wiki.py --skip-existing --wiki-upsert-mode create_unique

# Full run (400 papers ~5h, safe to interrupt and resume)
scripts/pc-wiki-ingest-bg.sh
```

`--wiki-upsert-mode` 支持：
- `create`：遇到同 slug 冲突时报错
- `create_unique`：同 slug 不同 Zotero key 自动写成 `YYYY-MM-DD-slug-key.md`
- `replace_if_same_key`：仅覆盖同一 Zotero key 的已有页面
- `replace_if_same_slug`：按 slug 直接覆盖（仅在明确需要时使用）

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
scripts/run_mcp.sh
```

`run_mcp_server.py` is now a **repo-local compatibility shim**: it inserts the repo's `src/` directory into `sys.path` and then delegates to the shared `paper_compass.mcp_entrypoint.main`. The canonical installed/runtime entrypoint is `paper-compass-mcp --mcp`.

如果要绕过 shell 直接调底层 shim，也仍可使用 `python scripts/run_mcp_server.py --mcp`。

**Test individual tools:**
```bash
paper-compass search wiki --query "家族企业"
paper-compass search library --query "succession"
paper-compass search passages --query "劳动力结构" --search-mode hybrid
paper-compass search ask --query "家族企业代际传承对劳动力结构的影响"
paper-compass status

# 首选 MCP CLI 入口
paper-compass-mcp --tool search_passages --query "劳动力结构" --search-mode keyword --db-path data/vectordb --text-dir data/texts --library-path data/zotero-export/library.json

# 兼容旧脚本入口（与 paper-compass-mcp 共享同一 mcp_entrypoint.main）
python scripts/run_mcp_server.py --tool ask_research --query "家族企业代际传承对劳动力结构的影响" --max-sources 7 --db-path data/vectordb
```

### 9. Configure AI agent clients

**Hermes Agent** (`config.yaml`):
```yaml
mcp_servers:
  paper-compass:
    command: /absolute/path/to/paper-compass/.venv/bin/paper-compass-mcp
    args: ["--mcp"]
    connect_timeout: 60
    timeout: 120
```

**Claude Desktop** (`claude_desktop_config.json`):
```json
{
  "mcpServers": {
    "paper-compass": {
      "command": "/absolute/path/to/paper-compass/.venv/bin/paper-compass-mcp",
      "args": ["--mcp"]
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
| NumPy 2.x alias removal | MCP tool call fails with `np.NaN was removed in the NumPy 2.0 release` | Upgrade to v1.2.5+; search code now uses `np.nan` |
| Wiki chunk ID collision | Fewer vectors than sections | Same-stem pages in different wiki subdirs |
| `build_index.py` skips papers | "missing PDF" | Ensure text file paths are correct |
| Metadata-only churn in dry-run | `--dry-run` shows many metadata-only papers | Re-run `build_index.py --incremental --dry-run --explain-changes --sample-size 5` before allowing any embedding-heavy run |
| Wiki title collision during ingest | `save:` / slug conflict errors during `ingest_to_wiki.py` | Prefer `--wiki-upsert-mode create_unique`; use `replace_if_same_key` only when replacing the same paper |
| Partial PDF extraction failures | Some papers silently miss text / chunks | Inspect `data/logs/pdf_extract_failures.jsonl` for `empty text`, `extract error`, `missing text`, `no valid chunks` |
| ChromaDB dual-client | Weird errors | Never create 2 PersistentClient for same path |
| Mac: multiple Python installs | `pip3 show pkg` says "not found" but `python3` can import it | Always use `python3 -m pip install ...` and `python3 -m pip show ...` instead of bare `pip` / `pip3` |
| Shell env var pollution | API call uses wrong URL | `unset LLM_BASE_URL LLM_API_KEY EMBED_BASE_URL EMBED_API_KEY VOLC_EMBED_BASE_URL VOLC_EMBED_API_KEY` before running |
| $ENV_VAR not resolved | "unauthorized" errors | Ensure the referenced env var is actually set in your shell |

Before publishing a new version, follow `docs/release-checklist.md` to keep code, docs, tests, tags, and release assets aligned.

## Running Tests

```bash
python3 -m pytest tests/ -v
```

Run targeted regression first when touching search / MCP entrypoints:

```bash
python3 -m pytest tests/test_search_numpy_compat.py -q
```

New test files:
- `tests/test_cli_arg_utils.py` — key=value parsing
- `tests/test_cli_configure.py` — interactive + non-interactive init
- `tests/test_cli_update.py` — update command tests
- `tests/test_config.py` — $ENV_VAR resolution
- `tests/test_wiki_store.py` — key-aware wiki slug / upsert behavior
- `tests/test_ingest_to_wiki.py` — wiki ingest parameter pass-through
- `tests/test_index_manifest_v2.py` — metadata diff normalization + explain helpers
- `tests/test_incremental_index.py` — incremental dry-run explanations + failure reporting
- `tests/test_pdf_extract_reporting.py` — structured PDF extraction failure reports

## Dependencies

All declared in `pyproject.toml`:
- **Runtime**: pyyaml, chromadb, pymupdf, rank-bm25
- **Optional**: sentence-transformers (`local-embed`), pdfplumber (`pdf-fallback`)
- **Dev**: pytest

## Key Files

| File | Purpose |
|------|---------|
| `.env.example` | Environment variable template |
| `configs/providers.yaml` | LLM + embedding provider settings |
| `configs/mcp.yaml` | MCP server configuration |
| `pyproject.toml` | Project metadata, version, dependencies |
| `src/paper_compass/cli/__init__.py` | CLI entry point (`paper-compass`) |
| `src/paper_compass/cli/configure.py` | `paper-compass init` command |
| `src/paper_compass/cli/update.py` | `paper-compass update` command |
| `src/paper_compass/cli/validate.py` | `paper-compass validate` command |
| `src/paper_compass/config.py` | Config loader with `$ENV_VAR` resolution |
| `src/paper_compass/env_utils.py` | `.env` loader (always overwrites stale values) |
| `scripts/sync_zotero.py` | Zotero → library.json + text extraction |
| `scripts/build_index.py` | ChromaDB index builder |
| `scripts/ingest_to_wiki.py` | Batch wiki generator |
| `scripts/run_mcp_server.py` | MCP repo-local compatibility shim |
| `scripts/healthcheck.py` | Health verification |
| `eval/run_eval.py` | Evaluation benchmark runner |
