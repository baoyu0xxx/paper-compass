# API Integration Notes

Verified 2026-05-09 during v1.2.0 deployment testing.

## Quick Config (CLI)

```bash
paper-compass init       # interactive setup
paper-compass validate   # test connectivity
```

## LLM (Wiki Generation)

- Base URL: configured via `LLM_BASE_URL` (any OpenAI-compatible endpoint)
- Model: `deepseek-v4-flash` (default in `providers.yaml`; override via `LLM_MODEL` env var)
- API style: OpenAI-compatible chat completions
- Endpoint: `{base_url}/chat/completions`
- Auth: Bearer token (env: `LLM_API_KEY`, supports `$ENV_VAR` syntax e.g. `$OPENAI_API_KEY`)
- Verified: generates structured wiki pages with frontmatter, academic tone

## Volcengine Embedding (Doubao)

- Base URL: `https://ark.cn-beijing.volces.com/api/v3/embeddings/multimodal`
- Model: `doubao-embedding-vision-250615` (or your custom endpoint ID)
- API style: Multimodal embedding (text + image)
- **Required input format**: `{"model": "...", "input": [{"type": "text", "text": "..."}]}`
- Auth: Bearer token (env: `VOLC_EMBED_API_KEY`, supports `$ENV_VAR` syntax e.g. `$VOLC_API_KEY`)
- Embedding dimension: 1024 (from sample test)
- Environment variables:
  - `VOLC_EMBED_BASE_URL` — full endpoint URL
  - `VOLC_EMBED_API_KEY` — API key
  - `VOLC_EMBED_MODEL` — model endpoint ID

## PaperQA Answer Provider

- Uses the same LLM endpoint as wiki generation
- Base URL: configured via `PAPERQA_BASE_URL`
- Model: configurable via `PAPERQA_MODEL` env (default: `gpt-4o`)
- Auth: `PAPERQA_API_KEY` (env, supports `$ENV_VAR` syntax)

## Provider Cascade (Embedding)

Embedding tries providers in order until one succeeds:
1. `embedding_main` (OpenAI-compatible, `EMBED_*` env vars)
2. `embedding_volcengine` (Volcengine, `VOLC_EMBED_*` env vars)
3. Local `bge-base` (no API key needed)

Configured in `configs/providers.yaml`; roles `pdf_embedding` and `wiki_embedding` control which provider to target.

## $ENV_VAR Reference Syntax

API keys in `.env` can reference existing environment variables:

```env
LLM_API_KEY=$OPENAI_API_KEY
EMBED_API_KEY=$MY_EMBED_KEY
VOLC_EMBED_API_KEY=$VOLC_API_KEY
```

Resolved at runtime by `config.py`'s `_resolve_env_value()`. If the referenced env var is not set, the `$VAR` literal is used as fallback.

## Notes

- The multimodal embedding endpoint requires `input[].type` = `"text"` and `input[].text` fields
- Standard OpenAI-compatible format (`{"input": ["text"]}`) returns 400 on this endpoint
- Doubao embedding model auto-maps from endpoint ID to `doubao-embedding-vision-250615`
- Shell env var pollution (stale `MIMO_BASE_URL` from old session) can break API calls — run `unset MIMO_BASE_URL` before troubleshooting
