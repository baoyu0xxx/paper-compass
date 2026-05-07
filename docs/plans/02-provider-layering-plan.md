# Provider layering plan

Generation and embedding should be configured separately.

1. Wiki generation provider
- base_url: https://token-plan-cn.xiaomimimo.com/v1
- model: MiMo-V2.5-Pro
- role usage:
  - wiki ingest
  - wiki merge/update
  - wiki query summarization
  - optional router classification

2. Embedding provider
- target: domestic online embedding service (e.g. Volcengine)
- role usage:
  - PaperQA indexing/retrieval embeddings
  - wiki page semantic embeddings

3. Optional PaperQA answer provider
- may be same as wiki provider or separate
- keep configurable by role rather than hard-coding one provider for everything

Why split them:
- generation and embedding APIs often differ in price, speed, and compatibility
- wiki and PDF layers can share one embedding backend to reduce maintenance
- prompt tuning should affect generation only, not vectorization

Configuration impact:
- providers.yaml uses named roles
- rag.yaml points to pdf_embedding + paperqa_answer
- wiki.yaml points to wiki_ingest/wiki_query + wiki_embedding
