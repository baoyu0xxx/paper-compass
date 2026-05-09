# Plan: LLM & Embedding Model Selection Configuration for paper-compass

## Goal

After installing paper-compass (`pip install -e .`), users need a structured way to configure:
1. **LLM provider** (for wiki generation) — base_url, api_key, model
2. **Embedding provider** (for vector indexing) — format selection (OpenAI-compatible vs Volcengine), url, key, model

API keys should support reading from environment variables (not just literal values in `.env`).

## Design Principle: Follow lm-eval-harness

The EleutherAI lm-evaluation-harness handles model configuration with a clean, tested design that paper-compass should adapt:

| lm-eval pattern | paper-compass adaptation |
|---|---|
| `--model_args key=value,key=value` | `--llm-args base_url=...,model=...` / `--embed-args api_style=openai,base_url=...` |
| `MergeDictAction` / `key_val_to_dict()` | Reuse same pattern in `cli/arg_utils.py` |
| `handle_cli_value_string()` auto-type detection (bool/int/float/str) | Reuse — though paper-compass values are mostly strings |
| Model registry via `@register_model` | NOT needed — paper-compass only has 2 model types (LLM chat, embedding) |
| Env var convention (OPENAI_API_KEY) | **Key innovation**: `api_key` can be `$ENV_VAR_NAME` — resolved at runtime, not stored literally |
| No TUI — all CLI arg driven | Support both interactive (new user) and non-interactive (scripted) modes |

## Proposed Approach

Create a **self-contained CLI module** under `src/paper_compass/cli/` with:

### Module Structure

```
src/paper_compass/cli/
├── __init__.py        # Unified CLI entry point (argparse)
├── configure.py       # `init` / `configure` subcommand
├── arg_utils.py       # key=value parsing (ported from lm-eval pattern)
└── validate.py        # Validate connectivity (ping LLM API, test embedding)
```

### `paper-compass init` — Interactive Mode

```
$ paper-compass init

┌─ Step 1: LLM (Wiki Generation) ─────────────────────────┐
│ Base URL [https://api.openai.com/v1]:                    │
│ API key (or $ENV_VAR name) [$OPENAI_API_KEY]:            │
│ Model [gpt-4o]: mimo-v2.5-pro                            │
└──────────────────────────────────────────────────────────┘

┌─ Step 2: Embedding ─────────────────────────────────────┐
│ API style: [1] OpenAI-compatible  [2] Volcengine  [1]:  │
│                                                          │
│ (OpenAI path)                                            │
│ Base URL [https://api.openai.com/v1]:                    │
│ API key (or $ENV_VAR name) [$OPENAI_API_KEY]:            │
│ Model [text-embedding-3-small]:                          │
│                                                          │
│ (Volcengine path)                                        │
│ Base URL [https://ark.cn-beijing.volces.com/...]:        │
│ API key (or $ENV_VAR name) [$VOLC_API_KEY]:              │
│ Endpoint ID [ep-20260420154519-9w64q]:                   │
└──────────────────────────────────────────────────────────┘

Written to .env (overwrite? Y/n)
✓ paper-compass configured. Run `paper-compass validate` to test.
```

Key behaviors:
- Default values shown in `[brackets]` — Enter accepts default
- **API key as env var**: If user enters `$OPENAI_API_KEY`, `.env` stores `LLM_API_KEY=$OPENAI_API_KEY` — resolved at runtime by `load_project_env()` then `get_provider_config()` reads `os.environ`
- If user enters a literal key, `.env` stores it literally
- Embedding api_style selection determines which env vars are written

### `paper-compass init --llm-args` — Non-Interactive Mode (lm-eval style)

```
# lm-eval style:
paper-compass init \
  --llm-args base_url=https://api.xxx.com/v1,model=mimo-v2.5-pro,api_key=$MY_KEY \
  --embed-args api_style=volcengine,base_url=https://...,model=ep-...,api_key=$VOLC_KEY
```

Both `--llm-args` and `--embed-args` accept comma-separated `key=value` pairs, parsed by the same `key_val_to_dict()` pattern from lm-eval.

### `paper-compass validate`

```
$ paper-compass validate
  ✓ LLM connection OK (model: mimo-v2.5-pro, 0.8s)
  ✓ Embedding connection OK (model: ep-..., dim=2048)
  ✓ .env file valid (all required vars present)
```

## Files That Change

| File | Change |
|---|---|
| `src/paper_compass/cli/__init__.py` | **New** — top-level CLI dispatcher |
| `src/paper_compass/cli/configure.py` | **New** — interactive + non-interactive `init` subcommand |
| `src/paper_compass/cli/arg_utils.py` | **New** — `key_val_to_dict()`, `MergeDictAction`, `handle_cli_value_string()` (from lm-eval) |
| `src/paper_compass/cli/validate.py` | **New** — connectivity validation |
| `pyproject.toml` | Add `paper-compass = "paper_compass.cli:main"` entry point |
| `.env.example` | Update — clearer comments showing `$ENV_VAR` syntax |
| `configs/providers.yaml` | Minor — confirm env var resolution path works with `$LLM_API_KEY` prefix |

## Key Design Decisions

### 1. `$ENV_VAR` prefix convention for api_key

Inspired by lm-eval's LiteLLM integration (which reads `OPENAI_API_KEY` from env directly). But paper-compass can't assume a fixed env var name per provider — the user may have many keys.

**Solution**: `.env` value `LLM_API_KEY=$OPENAI_API_KEY` → `load_project_env()` stores `"$OPENAI_API_KEY"` literally → `get_provider_config()` detects `$` prefix → resolves `os.environ["OPENAI_API_KEY"]`. This is a one-line change in `config.py`.

### 2. Interactive fallback order

1. If `--llm-args` / `--embed-args` provided → non-interactive mode
2. If `.env` already exists with valid values → skip (prompt to overwrite)
3. Otherwise → interactive prompts with smart defaults

### 3. Embedding format selection

The current system relies on two separate provider configs (`embedding_main` vs `embedding_volcengine`) with a cascade. The `init` command writes the correct set of env vars based on user choice:

- **OpenAI**: `EMBED_BASE_URL`, `EMBED_API_KEY`, `EMBED_MODEL`
- **Volcengine**: `VOLC_EMBED_BASE_URL`, `VOLC_EMBED_API_KEY`, `VOLC_EMBED_MODEL`

The provider cascade in `config.py` + `embedder.py` resolves which is available at runtime.

### 4. Backward compatibility

Existing `.env` files remain valid. The `init` command only overwrites with explicit `-f`/`--force` or user confirmation.

## Risks & Tradeoffs

| Risk | Mitigation |
|---|---|
| User stores plaintext API key in `.env` | Document `$ENV_VAR` pattern prominently; default prompt suggests `$ENV_NAME` |
| Volcengine vs OpenAI embedding confusing | Clear branching in interactive prompts; `--embed-args api_style=openai\|volcengine` disambiguates in non-interactive |
| Breaking existing `.env` | Never overwrite without confirmation or `--force` |
| Adding a CLI dependency | Use only stdlib (`argparse`, `os`, `pathlib`) — no new deps |

## Validation / Tests

- `tests/test_cli_arg_utils.py` — test `key_val_to_dict()` with various inputs
- `tests/test_cli_configure.py` — test `.env` generation with mock inputs
- `tests/test_config.py` — update to verify `$ENV_VAR` resolution in `get_provider_config()`
- Manual: `paper-compass init` → verify `.env` written correctly → `paper-compass validate` → connection OK

## Open Questions

1. Should `paper-compass init` validate connectivity as part of the interactive flow (i.e. ping after each step), or keep `validate` as a separate command?
2. Should the model name for LLM have sensible defaults per known base URLs (e.g. if `api.openai.com` → default to `gpt-4o`)?
