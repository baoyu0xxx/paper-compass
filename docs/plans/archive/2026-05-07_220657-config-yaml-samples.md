# 配置文件完整样例内容（providers.yaml / paths.yaml / rag.yaml / wiki.yaml / mcp.yaml）

> **For Hermes:** Use subagent-driven-development skill to implement this plan task-by-task.

**Goal:** 给最小化论文检索系统提供一套可以直接作为起点的 YAML 配置样例，覆盖 provider、路径、RAG、wiki 和 MCP 五个核心配置文件。该样例以“PDF 固定保存在 `D:\zotero_backup`（WSL: `/mnt/d/zotero_backup`）”为前提，优先服务于最小可用版本。

**Architecture:** 配置采用“集中路径配置 + 单主 provider + 明确默认行为”的最小策略。所有与本机强绑定的路径都集中在 `paths.yaml`；所有模型与 API 供应商配置集中在 `providers.yaml`；RAG、wiki、MCP 分别控制各自的行为参数，不相互污染。

**Tech Stack:** YAML, Python 3.11+, OpenAI-compatible API, PaperQA, Markdown wiki, MCP server。

---

## 1. 设计原则

1. 一期只保留一个主 provider，避免多模型路由复杂化。
2. 所有固定路径统一放到 `paths.yaml`。
3. `rag.yaml` 只描述深检索行为，不直接承载路径细节。
4. `wiki.yaml` 只控制广度层和写回策略。
5. `mcp.yaml` 只控制工具暴露与输出约束。
6. 所有密钥都不写死在 YAML，而是通过 `.env` 中的环境变量传入。

---

## 2. `configs/providers.yaml` 完整样例

```yaml
version: 1

default_provider: main

providers:
  main:
    api_style: openai-compatible
    base_url_env: OPENAI_BASE_URL
    api_key_env: OPENAI_API_KEY
    model: gpt-4.1-mini
    temperature: 0.1
    max_tokens: 4000
    timeout_seconds: 120
    extra_headers: {}

llm_roles:
  wiki_ingest: main
  wiki_query: main
  router_classify: main
  rag_answer: main
```

### 字段说明
- `default_provider`: 默认 provider 名称。
- `api_style`: 当前建议固定为 `openai-compatible`。
- `base_url_env`: 从环境变量读取 base URL。
- `api_key_env`: 从环境变量读取 API key。
- `model`: 当前默认模型。
- `temperature`: 一期建议维持较低温度。
- `llm_roles`: 为后续按角色切换模型预留，但一期仍可都指向 `main`。

### 一期建议
- 保持单 provider。
- 暂不引入 `fast` / `cheap` / `reasoning` 多档 provider。

---

## 3. `configs/paths.yaml` 完整样例

```yaml
version: 1

paths:
  zotero_pdf_root: /mnt/d/zotero_backup
  export_dir: ./data/zotero-export
  manifest_path: ./data/zotero-export/manifest.csv
  library_json_path: ./data/zotero-export/library.json
  metadata_input_path: ./data/input/zotero_metadata.csv

  wiki_root: ./wiki
  wiki_index_path: ./wiki/index.md
  wiki_log_path: ./wiki/log.md
  wiki_purpose_path: ./wiki/purpose.md
  wiki_schema_path: ./wiki/.wiki-schema.md

  prompts_dir: ./prompts
  log_dir: ./data/logs
  query_trace_path: ./data/logs/query-trace.jsonl

  pqa_home: ./.pqa
  temp_dir: ./tmp
```

### 字段说明
- `zotero_pdf_root`: 当前最关键的固定目录。
- `metadata_input_path`: 若你后续提供 Zotero 导出的 CSV/JSON，可从这里读入。
- `wiki_root`: 本地 wiki 根目录。
- `pqa_home`: PaperQA 索引与缓存目录。
- `temp_dir`: 临时文件目录，可选。

### 一期建议
- `zotero_pdf_root` 固定写死为 `/mnt/d/zotero_backup`。
- 其他路径保持项目相对路径，方便迁移与备份。

---

## 4. `configs/rag.yaml` 完整样例

```yaml
version: 1

rag:
  backend: paperqa
  enabled: true

  paper_directory_from: paths.zotero_pdf_root
  manifest_path_from: paths.manifest_path
  pqa_home_from: paths.pqa_home

  default_mode: filtered
  default_collection_scope: null
  allow_full_library_query: false

  answer:
    max_sources: 5
    evidence_k: 8
    answer_length: concise_with_citations
    temperature: 0.0

  filters:
    enabled: true
    allowed_fields:
      - collections
      - tags
      - authors
      - year
    default_limit: 10

  indexing:
    auto_reuse_existing_index: true
    rebuild_on_manifest_change: false
    chunk_size: null

  output:
    include_evidence_snippets: true
    include_page_hints: true
    include_doc_metadata: true
    max_snippets: 8
```

### 字段说明
- `paper_directory_from`: 指向 `paths.yaml` 中的 PDF 根目录。
- `manifest_path_from`: 指向同步层导出的 `manifest.csv`。
- `allow_full_library_query: false`: 防止一期默认全库深搜。
- `filters.allowed_fields`: 一期只开放 4 个过滤维度。
- `include_page_hints`: 若后端能返回页码/页段提示，则保留。

### 一期建议
- 默认深检索应尽量鼓励带 filter。
- 不主动开放“无过滤全库大范围检索”。

---

## 5. `configs/wiki.yaml` 完整样例

```yaml
version: 1

wiki:
  enabled: true
  ingest_mode: curated
  auto_writeback: false
  allow_manual_writeback: true

  page_types:
    - papers
    - topics
    - methods
    - queries
    - comparisons

  query:
    default_limit: 5
    return_snippets: true
    max_summary_pages: 3

  writeback:
    default_target_type: queries
    require_sources: true
    require_confidence: true
    update_index: true
    update_log: true

  frontmatter:
    required_fields:
      - title
      - created
      - updated
      - type
      - tags
      - sources
      - confidence

  confidence_defaults:
    query_writeback: medium
    topic_synthesis: medium
    single_source_note: low
```

### 字段说明
- `ingest_mode: curated`: 一期不自动全库编译 wiki。
- `auto_writeback: false`: 防止知识库污染。
- `max_summary_pages: 3`: wiki-only 回答时最多聚合若干页面。
- `frontmatter.required_fields`: 固定写回格式。

### 一期建议
- wiki 主要来源于：高价值 query、重点主题、人工指定内容。
- 不建议把所有文献自动写成 wiki 页面。

---

## 6. `configs/mcp.yaml` 完整样例

```yaml
version: 1

mcp:
  server_name: mini-paper-research
  enabled: true

  tools:
    - search_wiki
    - search_library
    - ask_research
    - get_paper_metadata
    - save_to_wiki

  response:
    include_trace_id: true
    include_confidence: true
    include_sources: true
    include_next_suggested_action: true
    max_result_items: 10

  routing:
    default_mode: auto
    allow_force_mode: true
    upgrade_to_pdf_when:
      - detail_request
      - source_verification_request
      - wiki_no_match
      - wiki_low_confidence

  safety:
    allow_writeback_tool: true
    require_nonempty_title_for_writeback: true
```

### 字段说明
- `tools`: 一期最小工具集。
- `routing.upgrade_to_pdf_when`: 定义升级深检索的条件。
- `allow_force_mode`: 允许 agent 或用户显式要求 `wiki/pdf/hybrid`。
- `require_nonempty_title_for_writeback`: 保证写回页面最基本可读性。

### 一期建议
- 保持工具数量稳定，不要继续扩展。
- 尽量让 `ask_research` 承担大部分路由复杂性。

---

## 7. 配套 `.env.example` 建议内容

虽然你这次只要求 YAML，但为了让这些配置真正可落地，建议 `.env.example` 至少包含：

```dotenv
OPENAI_BASE_URL=https://your-openai-compatible-endpoint/v1
OPENAI_API_KEY=your_api_key_here
ZOTERO_PDF_ROOT=/mnt/d/zotero_backup
WIKI_PATH=./wiki
PQA_HOME=./.pqa
```

说明：
- `OPENAI_BASE_URL` 与 `OPENAI_API_KEY` 对应 `providers.yaml`。
- `ZOTERO_PDF_ROOT` 与 `WIKI_PATH` 即使已经在 YAML 中写了，也可保留一份供后续脚本覆盖。

---

## 8. 配置加载约定建议

后续实现代码时，建议遵守以下约定：

1. `paths.yaml` 最先加载。
2. `providers.yaml` 第二个加载。
3. `rag.yaml / wiki.yaml / mcp.yaml` 再加载。
4. 支持 `*_from: paths.xxx` 这种轻量引用解析。
5. 最终在 Python 中形成一个统一的 `AppConfig` 对象。

这样做的好处是：
- 配置职责清楚；
- 路径统一；
- 后续改目录时不需要在多个文件重复编辑。

---

## 9. 当前配置安排总结

在当前设计下，整体配置安排已经比较清晰：

### 9.1 数据入口
- 统一 PDF 根目录：`/mnt/d/zotero_backup`
- 中间层输出：`manifest.csv` + `library.json`

### 9.2 广度层
- 使用本地 wiki
- 不自动全库编译
- 只保存高价值结果

### 9.3 深度层
- 使用 PaperQA
- 默认不允许无过滤全库大搜
- 主要支持带 collections/tags/authors/year 的范围控制

### 9.4 Agent 工具层
- 保持 5 个工具
- `ask_research` 是主入口
- 输出统一包含 mode / confidence / sources / trace_id

### 9.5 模型与 API 层
- 单一 OpenAI-compatible provider
- Prompt 外置
- 所有密钥走环境变量

---

## 10. 现在是否可以开始执行

从“规划完整度”看，已经比较接近可以开工的状态。当前已经具备：

1. 主方案文档
2. 最小化复用路线文档
3. 仓库骨架与配置清单文档
4. Zotero 同步层详细设计
5. MCP tools schema 详细设计
6. Phase 1–3 的逐任务执行清单
7. 本份 YAML 配置样例

因此，如果你认可以下三点，就已经可以进入执行阶段：

### 可以开工的前提 1
你接受一期按“固定目录 `/mnt/d/zotero_backup` 扫描 PDF”为主，而不是先深度耦合 Zotero 内部数据库。

### 可以开工的前提 2
你接受一期的 wiki 采用 `curated` 模式，即：
- 不自动编译全库
- 只写入高价值 query 或选定主题

### 可以开工的前提 3
你接受一期的深检索默认偏保守：
- 支持 PDF RAG
- 但默认不鼓励全库无过滤大范围检索

如果这三点你都接受，那么我认为已经可以开始执行了。

---

## 11. 我对当前设计安排的简明汇报

我把当前系统压缩成了一个尽量轻的 5 层结构：

1. 固定目录 PDF 层
- 直接读取 `/mnt/d/zotero_backup`

2. Zotero 同步层
- 扫描 PDF
- 合并可选 metadata
- 产出 `manifest.csv` 和 `library.json`

3. Wiki 广度层
- 本地 markdown wiki
- 保存高价值 query / topic / method / comparison

4. PaperQA 深度层
- 只在必要时做 PDF 级问答
- 默认配合 filters 使用

5. MCP 工具层
- 用 5 个工具暴露给 agent
- `ask_research` 负责主要路由

这个安排的特点是：
- 复杂度较低；
- 没有前端负担；
- 可以很快得到一个 agent 可用的版本；
- 后续要增强时，也有扩展位。

---

## 12. 下一步建议

如果你确认可以开工，最合理的第一步执行顺序是：

1. 建仓库骨架
2. 写 5 个 YAML 配置文件
3. 实现 `config.py`
4. 实现 `sync_zotero.py + zotero.py`
5. 先跑出 `manifest.csv` 与 `library.json`

也就是说，真正的第一阶段不是做 RAG，而是先把“固定目录 → 中间层”打通。只要这一步打通，后面的 wiki、PaperQA、MCP 都能较顺畅接上。  