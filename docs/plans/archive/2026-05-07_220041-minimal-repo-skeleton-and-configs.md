# 最小仓库骨架 + 配置文件清单

> **For Hermes:** Use subagent-driven-development skill to implement this plan task-by-task.

**Goal:** 在“文献附件统一位于 `D:\zotero_backup`（WSL: `/mnt/d/zotero_backup`）”这一前提下，定义一套尽可能轻量、可快速落地的论文检索系统仓库骨架与配置文件清单，使系统能够以最小复杂度支持：Zotero 固定目录接入、wiki 广度检索、PaperQA 深度检索、以及 MCP 调用。

**Architecture:** 仓库只保留 4 类核心内容：配置、轻量脚本、薄封装源码、本地 wiki/导出数据目录。原则上不引入前端、数据库服务、复杂部署编排。配置采用 `configs/*.yaml + .env` 的双层组织：路径与行为配置写在 YAML，密钥与本地差异写在 `.env`。

**Tech Stack:** Python 3.11+, paper-qa>=5, OpenAI-compatible API, YAML, Markdown wiki, optional sqlite/json, MCP server。

---

## 1. 设计原则

### 1.1 一期目标
- 支持从固定目录 `/mnt/d/zotero_backup` 读取 PDF。
- 支持生成最小 `manifest.csv` 与 `library.json`。
- 支持一个本地 markdown wiki。
- 支持一个轻量深检索脚本。
- 支持一个轻量 MCP server。

### 1.2 不纳入一期的内容
- 桌面前端
- Electron / React
- 独立数据库服务
- 分布式向量库
- 自动全库 wiki 编译
- 多用户 profile

### 1.3 仓库原则
- 配置集中，不分散在代码中。
- Prompt 外置。
- 脚本尽量可直接运行。
- 数据目录与代码目录清楚分离。
- wiki 可直接被 Obsidian 打开。

---

## 2. 建议仓库结构

```text
mini-paper-research/
├── README.md
├── pyproject.toml
├── .env.example
├── .gitignore
├── configs/
│   ├── providers.yaml
│   ├── paths.yaml
│   ├── wiki.yaml
│   ├── rag.yaml
│   └── mcp.yaml
├── prompts/
│   ├── wiki_ingest.md
│   ├── wiki_query.md
│   ├── router_classify.md
│   └── rag_answer.md
├── docs/
│   ├── scope-minimal.md
│   ├── reuse-strategy.md
│   └── mcp-tools.md
├── data/
│   ├── zotero-export/
│   │   ├── manifest.csv
│   │   └── library.json
│   └── logs/
│       └── query-trace.jsonl
├── wiki/
│   ├── index.md
│   ├── log.md
│   ├── purpose.md
│   ├── .wiki-schema.md
│   ├── raw/
│   ├── papers/
│   ├── topics/
│   ├── methods/
│   ├── queries/
│   └── comparisons/
├── scripts/
│   ├── sync_zotero.py
│   ├── ingest_to_wiki.py
│   ├── build_index.py
│   ├── ask_pdf.py
│   └── run_mcp_server.py
├── src/
│   └── miniresearch/
│       ├── __init__.py
│       ├── config.py
│       ├── models.py
│       ├── zotero.py
│       ├── wiki_ingest.py
│       ├── wiki_query.py
│       ├── rag.py
│       ├── filters.py
│       ├── router.py
│       └── mcp_server.py
└── tests/
    ├── test_config.py
    ├── test_zotero_sync.py
    ├── test_wiki_query.py
    ├── test_filters.py
    ├── test_router.py
    └── test_mcp_server.py
```

---

## 3. 核心文件说明

## 3.1 根目录文件

### `README.md`
**用途：** 项目总说明、安装、运行入口。  
**必须包含：**
- 系统目标
- 依赖安装
- `.env` 配置
- 首次同步 Zotero
- 首次建索引
- 运行 MCP server 的命令

### `pyproject.toml`
**用途：** Python 依赖与包管理。  
**建议依赖：**
- pyyaml
- pydantic
- paper-qa
- pandas（如果处理 csv 更方便）
- fastmcp 或等价 MCP 包（视实现而定）
- pytest

### `.env.example`
**用途：** 提供本地密钥与路径模板。  
**至少包含：**
- `OPENAI_API_KEY=` 或自定义 key env
- `OPENAI_BASE_URL=`
- `ZOTERO_PDF_ROOT=/mnt/d/zotero_backup`
- `WIKI_PATH=./wiki`
- `PQA_HOME=./.pqa`

### `.gitignore`
**应忽略：**
- `.env`
- `.venv/`
- `.pqa/`
- `data/logs/*.jsonl`
- 可选的缓存文件

---

## 4. 配置文件清单

## 4.1 `configs/providers.yaml`

**职责：** 统一管理所有 LLM 提供方配置。

**建议结构：**
```yaml
default_provider: main
providers:
  main:
    api_style: openai-compatible
    base_url_env: OPENAI_BASE_URL
    api_key_env: OPENAI_API_KEY
    model: gpt-4.1-mini
    temperature: 0.1
    timeout: 120
    max_tokens: 4000
```

**说明：**
- 一期只保留 1 个主 provider 即可。
- 后续若要扩展多个模型，可加 `wiki_provider`、`rag_provider` 字段，但一期不必复杂化。

## 4.2 `configs/paths.yaml`

**职责：** 集中管理路径。

**建议结构：**
```yaml
paths:
  zotero_pdf_root: /mnt/d/zotero_backup
  export_dir: ./data/zotero-export
  manifest_path: ./data/zotero-export/manifest.csv
  library_json_path: ./data/zotero-export/library.json
  wiki_path: ./wiki
  pqa_home: ./.pqa
  log_dir: ./data/logs
```

**说明：**
- 用户已给出固定 PDF 根目录，因此这里不再设计复杂的 Zotero 附件定位策略。
- 路径配置集中，后续部署时最容易维护。

## 4.3 `configs/wiki.yaml`

**职责：** 控制 wiki 行为。

**建议结构：**
```yaml
wiki:
  ingest_mode: curated
  auto_writeback: false
  page_types:
    - papers
    - topics
    - methods
    - queries
    - comparisons
  max_related_links: 5
  default_confidence: medium
```

**说明：**
- `ingest_mode: curated` 表示一期不自动全库编译，只写入精选内容或 query 结果。

## 4.4 `configs/rag.yaml`

**职责：** 控制 PDF 深检索层。

**建议结构：**
```yaml
rag:
  backend: paperqa
  paper_directory: /mnt/d/zotero_backup
  manifest_path: ./data/zotero-export/manifest.csv
  default_collection_scope: null
  answer_max_sources: 5
  evidence_k: 8
  temperature: 0.0
  enable_filters:
    - collections
    - tags
    - year
    - authors
```

**说明：**
- 一期默认直接把固定目录作为 paper directory。
- collection 过滤逻辑在中间层做，而不强行依赖 PaperQA 本身理解 Zotero 结构。

## 4.5 `configs/mcp.yaml`

**职责：** 控制 MCP 工具暴露与返回格式。

**建议结构：**
```yaml
mcp:
  server_name: mini-paper-research
  tools:
    - search_wiki
    - search_library
    - ask_research
    - get_paper_metadata
    - save_to_wiki
  include_trace_id: true
  include_confidence: true
  max_result_items: 10
```

---

## 5. Prompt 文件清单

### `prompts/wiki_ingest.md`
用于把高价值 query 或论文摘要写入 wiki。

### `prompts/wiki_query.md`
用于对 wiki 页面进行广度层回答。

### `prompts/router_classify.md`
用于后续若要从规则路由升级到轻量 LLM 路由时使用。

### `prompts/rag_answer.md`
用于控制 PDF RAG 最终回答风格，尤其是引用、谨慎措辞、证据呈现方式。

---

## 6. docs 文档清单

### `docs/scope-minimal.md`
写清一期不做什么，防止项目膨胀。

### `docs/reuse-strategy.md`
写清：
- 复用 `llm-wiki-skill` 哪些部分
- 借鉴 `llm_wiki` 哪些思想
- 借鉴 `RAG-Assistant-for-Zotero` 哪些检索与过滤逻辑

### `docs/mcp-tools.md`
写清工具说明、参数、输出。

---

## 7. data 目录说明

## 7.1 `data/zotero-export/`
保存从固定 PDF 目录扫描和整理出来的中间层文件：
- `manifest.csv`
- `library.json`

## 7.2 `data/logs/`
保存：
- `query-trace.jsonl`

一期不建议上来就引入 SQLite。先用 JSON/CSV/JSONL 即可。

---

## 8. wiki 目录最小要求

### `wiki/index.md`
内容索引。

### `wiki/log.md`
操作日志。

### `wiki/purpose.md`
当前研究关注的问题与方向。

### `wiki/.wiki-schema.md`
页面规范与 frontmatter 规则。

### 子目录
- `papers/`：重要论文页
- `topics/`：主题页
- `methods/`：方法页
- `queries/`：保存的问答页
- `comparisons/`：对比分析页

---

## 9. scripts 目录最小职责

### `scripts/sync_zotero.py`
从 `/mnt/d/zotero_backup` 扫描 PDF，生成中间层。

### `scripts/ingest_to_wiki.py`
把精选结果或 query 结果写入 wiki。

### `scripts/build_index.py`
建立 PaperQA 索引。

### `scripts/ask_pdf.py`
直接测试 PDF 深检索。

### `scripts/run_mcp_server.py`
启动 MCP server。

---

## 10. src 目录最小模块边界

### `config.py`
读取 YAML + `.env`。

### `models.py`
统一定义：PaperRecord、QueryResult、EvidenceSnippet、ToolResponse。

### `zotero.py`
负责固定目录扫描、metadata 映射、manifest 输出。

### `wiki_ingest.py`
负责写 wiki 页面。

### `wiki_query.py`
负责 wiki 搜索与广度回答。

### `rag.py`
负责调用 PaperQA。

### `filters.py`
负责把 year/tags/collections/authors 过滤条件应用到候选文献。

### `router.py`
负责选择 wiki-only 还是 wiki+pdf。

### `mcp_server.py`
负责暴露 MCP 工具。

---

## 11. 最小化部署建议

为保持系统简单，建议：
- 不把 Zotero 数据库读写纳入一期。
- 只把 `/mnt/d/zotero_backup` 视为固定 PDF 仓库。
- metadata 如有需要，可先来自人工导出文件或后续补充。
- 先以“PDF 可扫描 + 最小 metadata”跑通；再逐步增强。

这比一开始直连复杂 Zotero 内部数据库更稳妥。

---

## 12. 验证清单

在仓库骨架阶段完成后，应能验证：
- 所有配置文件路径清楚；
- `.env.example` 可直接填写；
- wiki 目录能直接初始化；
- `sync_zotero.py` 有明确输入输出路径；
- `run_mcp_server.py` 有固定配置入口。

---

## 13. 下一步建议

在这份子文档之后，最应该先落实的是：
1. Zotero 同步层详细设计；
2. MCP tools schema；
3. Phase 1–3 执行清单。

因为它们会直接决定：这个“最小仓库骨架”是否真能低成本落地。  