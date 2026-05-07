# 最小化部署的论文检索系统复用路线规划

> **For Hermes:** Use subagent-driven-development skill to implement this plan task-by-task.

**Goal:** 在尽可能少自研、尽可能简单部署的前提下，基于现有开源项目拼装一套可用的个人论文检索系统：上游连接 Zotero，本地维护一个可查询的 LLM Wiki 作为广度层，必要时再用 PDF RAG 做深度层，并最终通过轻量 MCP 服务暴露给 Hermes 这类 agent 调用。

**Architecture:** 采取“优先复用、少做平台”的策略。系统不自建完整桌面应用，也不一开始做复杂的自动化编译平台，而是优先复用 `llm-wiki-skill` 的 wiki 结构与工作流、借鉴 `llm_wiki` 的 provider/prompt/vector 配置思路、借鉴 `RAG-Assistant-for-Zotero` 的 Zotero 接入与元数据过滤逻辑；深度检索层继续使用 PaperQA 或等价 PDF RAG 后端，外层仅做一个非常薄的 router + MCP 包装。

**Tech Stack:** Python 3.11+, paper-qa>=5, Zotero, Markdown wiki (Obsidian-compatible), OpenAI-compatible LLM API, optional LiteLLM, optional LanceDB/Chroma, MCP server, YAML/JSON config, SQLite/JSONL logs。

---

## 1. 先说结论：这三个项目里哪些值得直接复用

## 1.1 `sdyckjq-lab/llm-wiki-skill`

**最值得直接复用。**

它的定位不是重型应用，而是“给 agent 用的 wiki 工作流技能包”，与当前目标最接近。对于你想要的“尽可能简单部署”，它的价值主要在于：

- 已经整理好了适合 agent 驱动的 wiki 目录结构；
- 已经有 ingest / query / 缓存 / graph / health-check 一套比较成熟的工作流；
- 明确支持 Hermes；
- 所有知识最终落在本地 markdown，天然适合 Obsidian；
- 不需要你从零设计 wiki schema 与 agent 提示流程。

**建议直接复用的部分：**
- wiki 目录结构
- `.wiki-schema.md` / purpose / index / log 这类组织方式
- 缓存思路（SHA256 去重）
- 健康检查思路
- 图谱展示思路（如果你后期需要）
- “知识编译而不是每次临时 RAG”这一工作流

**不建议照单全收的部分：**
- 各类网页/X/公众号/知乎等可选适配器
- 偏展示型的知识图谱前端
- 太重的多来源 ingest 能力

原因：你的当前核心是“论文检索系统”，不是泛互联网知识库工程。第一阶段应只保留 PDF / markdown / query-synthesis 主线。

## 1.2 `nashsu/llm_wiki`

**适合作为“借鉴实现”，不适合作为第一阶段直接整仓复用。**

这个项目是桌面应用，功能很强，包含：
- 两阶段 ingest
- provider 可配置
- vector search
- queue
- graph / community detection
- deep research
- review system
- Electron + React + FastAPI 桌面壳

对于“完整产品”它很有价值；但对于你当前“尽可能简单部署”的目标，它偏重。

**建议借鉴的部分：**
- provider 抽象：支持 OpenAI-compatible endpoint
- prompt 外置化
- 两阶段 ingest 的思路
- 可选 vector search 的设计
- query budget / retrieval pipeline 的思路
- wiki 页面的来源追踪字段

**不建议一开始复用的部分：**
- Electron 桌面壳
- React 前端
- queue / review / graph insights 全套 UI
- deep research 的联网编译流程

原因：这些会显著抬高部署复杂度，但未必对你的最小可用系统有决定性帮助。

## 1.3 `aahepburn/RAG-Assistant-for-Zotero`

**最适合作为“深检索层参考实现”，但不建议直接作为你的主工程底座。**

它的优势在于：
- 明确面向 Zotero；
- 已经验证了“直接读 Zotero 本地数据库 + PDF 索引 + metadata filters”的路线；
- 检索层很成熟，尤其是 hybrid retrieval、reranking、metadata filtering；
- 支持本地/云端模型；
- cited answers + source transparency 对学术研究很有价值。

**建议借鉴或抽取的部分：**
- Zotero 本地数据库路径与元数据同步逻辑
- metadata filtering 维度：year / tags / collections / authors / item types
- deep retrieval pipeline 的结构
- evidence panel / source transparency 的数据结构
- profile/workspace 思路（如果后期扩展）

**不建议第一阶段直接复用的部分：**
- Electron 桌面应用壳
- 前后端分离 UI
- Chroma/前端聊天系统整套工程

原因：如果你只是想让 agent 可调用，桌面 UI 不是刚需。它更像“可参考的 Zotero-RAG 产品”，而不是最适合直接改造成 MCP 的薄后端。

---

## 2. 最小化方案的总体判断

如果目标是“尽量简单部署”，最优方案不是把三者拼成一个大一统平台，而是：

### 方案主线
1. 用 `llm-wiki-skill` 作为广度层的主骨架；
2. 用一个很薄的 Zotero 导出/同步脚本，给 wiki 和 RAG 共用；
3. 用 PaperQA 作为 PDF 深检索层；
4. 借鉴 `RAG-Assistant-for-Zotero` 的 metadata filter 设计；
5. 借鉴 `llm_wiki` 的 provider/prompt 配置方式；
6. 最后只写一个轻量 MCP server，把这些能力暴露出去。

### 也就是说：
- 不自研完整 wiki 系统；
- 不自研完整桌面 RAG app；
- 不自研复杂前端；
- 只自研三块薄胶水：
  - Zotero → 中间层
  - Query Router
  - MCP 包装层

这是复杂度最低、同时保留后续扩展性的路线。

---

## 3. 建议冻结的“最小系统边界”

为避免项目继续膨胀，建议一期只做以下功能：

## 3.1 必做
- 从 Zotero 获取本地 PDF 与核心元数据
- 维护一个本地 markdown wiki
- 支持 wiki-only 广度检索
- 支持 PDF 深度检索（至少对指定子库/collection）
- 支持一个轻量 router：判断是否升级到 PDF RAG
- 支持 MCP tools：search / ask / metadata / route

## 3.2 暂不做
- 自定义桌面 UI
- 自动 graph insights
- review system
- 多用户 profile 管理
- 全网 deep research 自动抓取
- 复杂 vector DB 服务化
- 全库自动增量编译到极致

这个边界很重要。否则很容易不自觉地把 `llm_wiki` 或 `RAG-Assistant-for-Zotero` 的重型特性一并搬进来。

---

## 4. 推荐的模块复用映射

## 4.1 广度层：优先复用 `llm-wiki-skill`

### 直接采用
- markdown wiki 结构
- index/log/purpose/schema 机制
- 原始材料与 wiki 分层
- query 结果可回写 wiki 的工作流
- cache / health-check 设计

### 需要最小改造
- 将“知识源”聚焦到 Zotero 导出的 PDF 摘要、文献问答结果、手工笔记
- 新增适合论文领域的 page types，例如：
  - `papers/`
  - `authors/`
  - `methods/`
  - `topics/`
  - `queries/`
  - `comparisons/`
- 在 schema 中加入学术字段：
  - authors
  - year
  - journal
  - doi
  - collections
  - tags
  - confidence

### 一期建议删减
- 先不接网页、X、公众号适配器
- 先不做图谱 HTML 生成
- 先不做复杂多来源 ingest

## 4.2 Provider/Prompt 层：借鉴 `llm_wiki`

### 应复用的设计思想
- 所有 LLM 相关能力统一走 provider 配置
- 支持 OpenAI-compatible endpoint
- prompt 文件全部外置
- ingest / merge / query / route 使用不同 prompt 文件

### 一期应实现的最小配置项
- `provider.base_url`
- `provider.api_key_env`
- `provider.model`
- `provider.temperature`
- `provider.timeout`
- `provider.max_tokens`

### 一期应外置的 prompts
- `prompts/wiki_ingest.md`
- `prompts/wiki_merge.md`
- `prompts/wiki_query.md`
- `prompts/router_classify.md`
- `prompts/rag_answer.md`

## 4.3 深检索层：PaperQA + 借鉴 `RAG-Assistant-for-Zotero`

### 为什么继续用 PaperQA
- 它对 scientific literature 的定位更贴合你的目标；
- 可以较快跑通带引文的 PDF 问答；
- 比直接改一个桌面 app 更轻；
- 更适合作为 MCP 后端。

### 需要从 `RAG-Assistant-for-Zotero` 借鉴的内容
- 直接从 Zotero 同步 metadata 的字段设计
- metadata filter 的 query 接口
- broad vs focused query 的上下文控制思路
- source transparency 输出结构

### 一期不建议照搬的部分
- Chroma + cross-encoder + Electron 整套技术栈
- 对话 UI
- 多 profile 系统

原因：这些会让最小方案变得不“最小”。

---

## 5. 最简实现架构

建议把最终系统压缩为 5 个模块。

```text
[1] Zotero Sync Layer
    ├─ 读 zotero.sqlite / 或导出文件
    ├─ 产出 manifest.csv + library.json
    └─ 统一附件路径

[2] Wiki Layer (reuse llm-wiki-skill style)
    ├─ 维护 markdown wiki
    ├─ 查询已有概念/主题页
    └─ 可选择性写回高价值结果

[3] PDF RAG Layer (PaperQA)
    ├─ 对导出 PDF 建索引
    ├─ 支持 collection/topic 过滤
    └─ 输出 citations/evidence

[4] Router Layer
    ├─ 默认先查 wiki
    ├─ 命中细节型问题时升级到 PDF RAG
    └─ 合并最终回答

[5] MCP Layer
    ├─ search_wiki
    ├─ search_library
    ├─ ask_research
    ├─ get_paper_metadata
    └─ save_to_wiki
```

除这 5 个模块之外，尽量不再增加新的系统部件。

---

## 6. 详细实现路线（按最小复杂度排序）

## Phase 0：做减法，先冻结不用做的东西

### Task 0.1：冻结“一期最小能力”

**Objective:** 防止项目继续膨胀。

**Files:**
- Create: `docs/scope-minimal.md`

**明确写入：**
- 不做桌面前端
- 不做图谱前端
- 不做复杂联网抓取
- 不做多用户
- 不做复杂增量编排

### Task 0.2：确定以“复用 + 薄胶水”为主

**Objective:** 统一技术路线。

**Files:**
- Create: `docs/reuse-strategy.md`

**建议写清：**
- wiki 骨架复用 `llm-wiki-skill`
- provider/prompt 设计借鉴 `llm_wiki`
- zotero metadata 逻辑借鉴 `RAG-Assistant-for-Zotero`
- PDF 问答后端用 PaperQA

---

## Phase 1：仓库骨架与配置体系

### Task 1.1：创建最小仓库结构

**Objective:** 只建立最少必要目录。

**Files:**
- Create: `README.md`
- Create: `pyproject.toml`
- Create: `.env.example`
- Create: `configs/`
- Create: `prompts/`
- Create: `scripts/`
- Create: `src/miniresearch/`
- Create: `tests/`
- Create: `wiki/`
- Create: `data/zotero-export/`

### Task 1.2：建立统一配置

**Objective:** 避免每一层各自维护独立配置。

**Files:**
- Create: `configs/providers.yaml`
- Create: `configs/paths.yaml`
- Create: `configs/wiki.yaml`
- Create: `configs/rag.yaml`
- Create: `configs/mcp.yaml`

**必要字段：**
- OpenAI-compatible base_url
- api_key_env
- model
- wiki_path
- zotero_db_path
- attachment_root
- paper_directory
- allowed_collections

### Task 1.3：建立 prompt 文件

**Objective:** 固定 LLM 行为入口。

**Files:**
- Create: `prompts/wiki_ingest.md`
- Create: `prompts/wiki_query.md`
- Create: `prompts/router_classify.md`
- Create: `prompts/rag_answer.md`

---

## Phase 2：最薄的 Zotero 接入层

这是整个最小方案里最值得尽早做的部分。

### 核心判断
与其从一开始把 Zotero 导出做得很复杂，不如先只实现：
- 读取 Zotero 本地数据库或现成导出
- 找到 PDF 路径
- 同步必要 metadata
- 生成 manifest.csv 与 library.json

### Task 2.1：决定 Zotero 接入方式

**Objective:** 选定一期到底是“读 sqlite”还是“读导出结果”。

**推荐：**
- 如果你希望省步骤、贴近 `RAG-Assistant-for-Zotero`：优先读本地 `zotero.sqlite`
- 如果你更重视稳妥和可移植：优先读 Zotero 导出文件 + 附件目录

**建议的一期默认：**
先读导出文件；后续再加 sqlite 直读。

原因：
- 更容易调试；
- 不直接耦合 Zotero 内部表结构；
- 对 MCP 服务更稳定。

### Task 2.2：实现最小同步脚本

**Objective:** 产出统一中间层。

**Files:**
- Create: `scripts/sync_zotero.py`
- Create: `src/miniresearch/zotero.py`
- Test: `tests/test_zotero_sync.py`

**输出：**
- `data/zotero-export/library.json`
- `data/zotero-export/manifest.csv`

**manifest 最小字段：**
- `file_location`
- `title`
- `doi`

**library.json 建议字段：**
- `zotero_key`
- `title`
- `authors`
- `year`
- `journal`
- `doi`
- `collections`
- `tags`
- `pdf_path`

### Task 2.3：实现 collection 过滤

**Objective:** 为后续最小深检索控制语料范围。

**Files:**
- Modify: `src/miniresearch/zotero.py`
- Test: `tests/test_collection_filter.py`

原因：如果不先做 collection 过滤，后续任何 PDF RAG 都容易全库过重。

---

## Phase 3：最小 Wiki 层

### 路线判断
这里不建议自己重新发明一个 wiki 系统，而是：
- 目录结构尽量向 `llm-wiki-skill` 靠齐；
- 只实现论文场景最少需要的 ingest/query/writeback；
- 不做它那些非论文主线的适配器。

### Task 3.1：初始化 wiki 结构

**Objective:** 建一个论文场景的轻量 wiki。

**Files:**
- Create: `wiki/index.md`
- Create: `wiki/log.md`
- Create: `wiki/purpose.md`
- Create: `wiki/.wiki-schema.md`
- Create: `wiki/raw/pdfs/`
- Create: `wiki/topics/`
- Create: `wiki/papers/`
- Create: `wiki/methods/`
- Create: `wiki/queries/`
- Create: `wiki/comparisons/`

### Task 3.2：实现最小 wiki ingest

**Objective:** 不是全自动编译全库，而是只把选定 collection 或 query 结果写入 wiki。

**Files:**
- Create: `scripts/ingest_to_wiki.py`
- Create: `src/miniresearch/wiki_ingest.py`
- Test: `tests/test_wiki_ingest.py`

**一期 ingest 来源仅限：**
- PaperQA 查询结果
- 人工选定的论文摘要/笔记
- 手工粘贴内容

也就是说，一期先不要做“自动遍历整个 PDF 库并全面编译 wiki”。

### Task 3.3：实现 wiki 查询

**Objective:** 支撑广度层。

**Files:**
- Create: `src/miniresearch/wiki_query.py`
- Test: `tests/test_wiki_query.py`

**建议能力：**
- filename/content search
- topic lookup
- page summary answer
- query result 保存回 wiki

---

## Phase 4：最小 PDF 深检索层

### Task 4.1：PaperQA 样本跑通

**Objective:** 先只在一个 collection 或 20–50 篇样本文献上验证。

**Files:**
- Create: `scripts/build_index.py`
- Create: `scripts/ask_pdf.py`
- Create: `src/miniresearch/rag.py`
- Test: `tests/test_rag_config.py`

### Task 4.2：做 metadata filter 包装

**Objective:** 借鉴 `RAG-Assistant-for-Zotero` 的过滤思路，但不复刻其整套后端。

**Files:**
- Modify: `src/miniresearch/rag.py`
- Create: `src/miniresearch/filters.py`
- Test: `tests/test_filters.py`

**一期支持的过滤字段：**
- collections
- tags
- year range
- authors

### Task 4.3：统一 evidence 输出结构

**Objective:** 为 MCP 和 router 提供稳定上游。

**Files:**
- Create: `src/miniresearch/models.py`
- Test: `tests/test_evidence_schema.py`

**统一输出建议：**
- answer
- citations
- evidence_snippets
- source_docs
- retrieval_mode
- filters_used
- confidence

---

## Phase 5：最轻的 Router

这是整个多层检索的关键，但必须做得很薄。

### Task 5.1：先做规则路由器

**Objective:** 不先上复杂分类模型。

**Files:**
- Create: `src/miniresearch/router.py`
- Test: `tests/test_router.py`

**默认规则：**
- 先查 wiki
- 若 query 含以下模式，则升级 PDF RAG：
  - “原文怎么说”
  - “哪一页”
  - “样本如何构造”
  - “机制变量如何定义”
  - “识别策略”
  - “稳健性检验”
  - “具体哪篇文章提出”
- 若 wiki 无命中，也升级 PDF RAG

### Task 5.2：实现 hybrid answer merge

**Objective:** 把 wiki 已有认识与 PDF 证据合并。

**Files:**
- Modify: `src/miniresearch/router.py`
- Test: `tests/test_hybrid_merge.py`

**建议回答模板：**
1. 已有 wiki 认识
2. 原文补充证据
3. 最终综合回答
4. 建议是否写回 wiki

---

## Phase 6：最小 MCP 服务

### Task 6.1：定义最小 tool 集合

**Objective:** 不超过 5 个工具。

**Files:**
- Create: `docs/mcp-tools.md`

**一期建议只做：**
- `search_wiki(query, limit)`
- `search_library(query, filters, limit)`
- `ask_research(query, filters=None, force_mode=None)`
- `get_paper_metadata(id_or_doi)`
- `save_to_wiki(answer_payload, target_type)`

### Task 6.2：实现 MCP server

**Objective:** 做一个很薄的 agent 接口层。

**Files:**
- Create: `scripts/run_mcp_server.py`
- Create: `src/miniresearch/mcp_server.py`
- Test: `tests/test_mcp_server.py`

### Task 6.3：输出 agent-friendly 结构

**Objective:** 便于 Hermes 等 agent 自主串联调用。

**Files:**
- Modify: `src/miniresearch/mcp_server.py`
- Test: `tests/test_mcp_payloads.py`

**每个 tool 最好统一返回：**
- `ok`
- `mode_used`
- `data`
- `sources`
- `confidence`
- `next_suggested_action`

---

## 7. 必要技术细节：如何真正“简化”项目

## 7.1 不要一开始做自动全库 wiki 编译

这是最重要的减法。

初期 wiki 的价值主要来自：
- 已回答过的高价值 query
- 你亲自选定的重要论文/主题
- 与当前研究直接相关的专题页

而不是把整个 Zotero 一次性全编译。

## 7.2 深检索默认只对“子库/collection”开放

这是第二个关键减法。

如果默认全库深搜：
- 成本更高；
- 噪声更大；
- 索引更慢；
- 调试更困难。

建议一期默认：
- 先针对某个研究专题 collection 建索引；
- 之后再扩到全库。

## 7.3 Provider 抽象只做一套

不要 wiki 一套 provider、PaperQA 一套 provider、router 一套 provider。

建议统一用：
- 一个 `providers.yaml`
- 一个 `load_provider_config()`
- 所有 OpenAI-compatible 调用共用同一层抽象

## 7.4 日志要极简但不能没有

一期建议只记录一个 `query-trace.jsonl`，包含：
- timestamp
- query
- mode_used
- filters_used
- wiki_hits
- pdf_hits
- answer_summary
- saved_to_wiki

## 7.5 测试重点不是覆盖率，而是链路稳定性

重点测：
- Zotero 同步是否稳定
- manifest 是否有效
- wiki 查询是否能命中
- router 是否正确升级
- MCP 输出 schema 是否稳定

---

## 8. 推荐的最终目录结构（最小版）

```text
mini-paper-research/
├── README.md
├── pyproject.toml
├── .env.example
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
│   └── zotero-export/
│       ├── manifest.csv
│       └── library.json
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
│       ├── models.py
│       ├── zotero.py
│       ├── wiki_ingest.py
│       ├── wiki_query.py
│       ├── rag.py
│       ├── filters.py
│       ├── router.py
│       └── mcp_server.py
└── tests/
    ├── test_zotero_sync.py
    ├── test_collection_filter.py
    ├── test_wiki_ingest.py
    ├── test_wiki_query.py
    ├── test_rag_config.py
    ├── test_filters.py
    ├── test_router.py
    ├── test_hybrid_merge.py
    ├── test_evidence_schema.py
    ├── test_mcp_server.py
    └── test_mcp_payloads.py
```

---

## 9. 明确的项目取舍建议

如果你的目标是“尽快落地一个真正能用的系统”，我建议明确做以下取舍：

### 应该直接复用
- `llm-wiki-skill` 的 wiki 组织方式与工作流主线
- `llm_wiki` 的 provider/prompt/config 设计思想
- `RAG-Assistant-for-Zotero` 的 Zotero metadata / filter 设计思想

### 不应该直接整仓复用
- `llm_wiki` 的桌面 UI
- `RAG-Assistant-for-Zotero` 的 Electron/React/FastAPI 整体工程

### 应该自己实现的薄层
- Zotero 同步胶水层
- Router
- MCP server

### 应该继续使用现成后端
- PDF 深检索：PaperQA

这基本就是“最小复杂度”的最优拆法。

---

## 10. 风险与规避

### 风险 1：过度复用导致系统反而更重
**表现：** 想省事，结果把两个桌面应用架构都搬进来。  
**规避：** 只复用结构和思路，不复用 UI 壳。

### 风险 2：wiki 过早自动化全编译
**表现：** 一上来就全库 ingest，质量不稳且成本高。  
**规避：** 先做选定子库 + query 写回。

### 风险 3：Zotero 直读太耦合
**表现：** 内部表结构或附件路径让同步逻辑脆弱。  
**规避：** 一期先导出文件路线，二期再加 sqlite 直读。

### 风险 4：MCP tools 过多
**表现：** 工具太多，agent 反而不容易稳定使用。  
**规避：** 一期只做 5 个工具。

### 风险 5：深检索默认全库
**表现：** 性能差、费用高。  
**规避：** 默认 collection / topic 范围。

---

## 11. 推荐的执行顺序（真正最省力的顺序）

1. 先写 `scope-minimal.md` 和 `reuse-strategy.md`
2. 搭最小仓库与配置
3. 实现 Zotero 同步脚本
4. 建一个轻量 wiki 骨架
5. 用样本文库跑通 PaperQA
6. 做规则版 router
7. 做最小 MCP server
8. 最后再补 wiki 写回与 prompt 优化

这是最稳妥、也最符合“尽量简单部署”的路线。

---

## 12. 完成定义（最小可用版）

当以下条件满足时，可以认为最小系统已完成：

- 能从 Zotero 导出或同步一个专题子库；
- 能维护一个本地 markdown wiki；
- agent 能先查 wiki，再在需要时升级到 PDF 深检索；
- MCP server 至少暴露 4–5 个稳定工具；
- 整个系统无需桌面 UI 也能运行；
- 新增论文进入子库后，可以较低成本更新。

---

## 13. 最后给你的路线建议

如果你的首要目标是“尽快做成一个能用、又不太重的版本”，我建议把方案收缩成一句话：

**用 `llm-wiki-skill` 做广度层骨架，用 PaperQA 做深度层，用一个很薄的 Zotero 同步层和 MCP 层把它们粘起来；只借鉴 `llm_wiki` 和 `RAG-Assistant-for-Zotero` 的设计，不直接继承它们的重型工程。**

这条路线最符合：
- 尽可能简单部署
- 尽量少写新系统
- 保留 Zotero、wiki、PDF RAG、agent 调用四个核心目标
- 后续仍有扩展空间
