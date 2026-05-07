# API Integration Notes

Verified 2026-05-08 during small-sample testing.

## Mimo LLM (Wiki Generation)

- Base URL: `https://token-plan-cn.xiaomimimo.com/v1`
- Model: `mimo-v2.5-pro`
- API style: OpenAI-compatible chat completions
- Endpoint: `{base_url}/chat/completions`
- Auth: Bearer token (env: `XIAOMI_API_KEY`)
- Verified: generates structured wiki pages with frontmatter, academic tone

## Volcengine Embedding (Doubao)

- Base URL: `https://ark.cn-beijing.volces.com/api/v3/embeddings/multimodal`
- Model: `ep-20260420154519-9w64q` → `doubao-embedding-vision-250615`
- API style: Multimodal embedding (text + image)
- **Required input format**: `{"model": "...", "input": [{"type": "text", "text": "..."}]}`
- Auth: Bearer token (env: `VOLC_EMBED_API_KEY`)
- Embedding dimension: 1024 (from sample test)
- Environment variables:
  - `VOLC_EMBED_BASE_URL` — full endpoint URL
  - `VOLC_EMBED_API_KEY` — API key
  - `VOLC_EMBED_MODEL` — model endpoint ID

## PaperQA Answer Provider

- Uses same Mimo endpoint as wiki generation
- Base URL: `https://token-plan-cn.xiaomimimo.com/v1`
- Model: configurable via `PAPERQA_MODEL` env
- Auth: `PAPERQA_API_KEY` (env)

## Notes

- The multimodal embedding endpoint requires `input[].type` = `"text"` and `input[].text` fields
- Standard OpenAI-compatible format (`{"input": ["text"]}`) returns 400 on this endpoint
- Doubao embedding model auto-maps from endpoint ID to `doubao-embedding-vision-250615`
