     1|# API Integration Notes
     2|
     3|Verified 2026-05-08 during small-sample testing.
     4|
     5|## Mimo LLM (Wiki Generation)
     6|
     7|- Base URL: `https://token-plan-cn.xiaomimimo.com/v1`
     8|- Model: `mimo-v2.5-pro`
     9|- API style: OpenAI-compatible chat completions
    10|- Endpoint: `{base_url}/chat/completions`
    11|- Auth: Bearer token (env: `LLM_API_KEY`)
    12|- Verified: generates structured wiki pages with frontmatter, academic tone
    13|
    14|## Volcengine Embedding (Doubao)
    15|
    16|- Base URL: `https://ark.cn-beijing.volces.com/api/v3/embeddings/multimodal`
    17|- Model: `ep-20260420154519-9w64q` → `doubao-embedding-vision-250615`
    18|- API style: Multimodal embedding (text + image)
    19|- **Required input format**: `{"model": "...", "input": [{"type": "text", "text": "..."}]}`
    20|- Auth: Bearer token (env: `VOLC_EMBED_API_KEY`)
    21|- Embedding dimension: 1024 (from sample test)
    22|- Environment variables:
    23|  - `VOLC_EMBED_BASE_URL` — full endpoint URL
    24|  - `VOLC_EMBED_API_KEY` — API key
    25|  - `VOLC_EMBED_MODEL` — model endpoint ID
    26|
    27|## PaperQA Answer Provider
    28|
    29|- Uses same Mimo endpoint as wiki generation
    30|- Base URL: `https://token-plan-cn.xiaomimimo.com/v1`
    31|- Model: configurable via `PAPERQA_MODEL` env
    32|- Auth: `PAPERQA_API_KEY` (env)
    33|
    34|## Notes
    35|
    36|- The multimodal embedding endpoint requires `input[].type` = `"text"` and `input[].text` fields
    37|- Standard OpenAI-compatible format (`{"input": ["text"]}`) returns 400 on this endpoint
    38|- Doubao embedding model auto-maps from endpoint ID to `doubao-embedding-vision-250615`
    39|