# 基于 PaperQA + LLM Wiki + Zotero + MCP 的多层论文检索系统完整规划清单

> **Archive note (current behavior wins):** 这是历史规划文档，用于保留当时的设计思路，不代表当前仓库的推荐入口或最新实现语义。当前日常“完整增量更新”应以 `paper-compass sync` 为标准入口；`scripts/pc-index-incremental.sh` 现在只是该完整 sync 语义的便捷包装，不应再被理解为 papers-only 增量索引。

> **For Hermes:** Use subagent-driven-development skill to implement this plan task-by-task.

**Goal:** 规划一套面向个人学术研究的多层论文检索系统：以 Zotero 作为上游文献源，以 LLM Wiki 作为广度检索与知识沉淀层，以 PaperQA/PDF RAG 作为深度检索层，并通过 MCP 服务把这些能力暴露给 Hermes 这类 agent，自主完成“检索—筛选—追问—总结—沉淀”的研究辅助流程。

**Architecture:** 采用“源数据层 → 知识编译层 → 深度证据层 → 路由编排层 → MCP 工具层 → 可选沉淀层”的多层架构。对广度搜索、概念回忆、已有知识复用，优先命中 LLM Wiki；对需要细节、原文证据、表述核对、方法机制、脚注限定、样本构造等问题，自动升级到“LLM Wiki + PDF RAG”联合检索。系统初期以本地单用户、CLI/agent 优先为原则，后续再扩展 UI 与自动化。

**Tech Stack:** Python 3.11+, paper-qa>=5, LiteLLM / OpenAI-compatible API provider, Zotero, Markdown wiki (Obsidian-compatible), MCP server, JSON/YAML config, manifest.csv, 可选 SQLite/JSONL 日志，必要时可接入本地 embedding / 外部向量库。

---

## 一、总目标与设计原则

### 1.1 系统目标

该系统需要同时满足四个目标：

1. 对“我大概记得这个主题，但想快速回忆已有认识”的问题，提供低成本、快速、结构化的广度检索。
2. 对“我需要回到原始文献，确认某个细节、定义、样本、方法或结论”的问题，提供更深一层、带原文证据的检索与问答。
3. 让 agent 可以像调用普通工具一样，自主调用文献检索、聚合、比较和知识沉淀能力。
4. 在使用过程中逐渐形成一个可复用、可积累、可人工修订的个人研究知识库，而不是每次都从零检索。

### 1.2 核心设计原则

- 分层，不混层：wiki 层负责广度知识，PDF RAG 层负责细节证据，不用一个系统承担所有职责。
- 先可用，再完美：一期先实现较稳妥的单用户本地版本，不先追求复杂平台化。
- Zotero 是 source of truth：文献条目、附件、标签、collection 以 Zotero 为准。
- Agent-first but human-auditable：既要让 agent 可调用，也要让人工能够检查检索过程和来源。
- 可替换模型后端：LLM 与 embedding 供应商不能绑死，必须支持 OpenAI-compatible 自定义网关。
- Prompt 可配置：尤其是 LLM Wiki 构建 prompt、总结 prompt、路由 prompt、回答 prompt 都应外置。
- 广度与深度分路：先判定问题类型，再决定是否升级到 PDF 级深检索。

---

## 二、你新增要求对应的正式技术路线

## 2.1 多层检索路线

你提出的核心要求应被正式固定为：

### 层 1：广度检索层（LLM Wiki only）
适用问题：
- 回忆某个主题的大体框架
- 查找某个概念、作者、方法、领域争议的已有整理
- 需要较快响应，但不要求立刻回到 PDF 细节
- 需要复用过去已经整理过的知识，而不是每次重新阅读原文

返回特点：
- 响应快
- 成本较低
- 答案结构较清晰
- 可能不覆盖最新未入库文献
- 适合作为 first-pass retrieval

### 层 2：深度检索层（LLM Wiki + PDF RAG）
适用问题：
- 需要确认某篇文献的原始表述
- 需要核对识别策略、变量定义、样本区间、稳健性、机制识别等具体细节
- 需要跨多篇论文做证据级比较
- 需要生成带明确引用依据的回答
- 用户或 agent 判断“wiki 结论还不够，需要追溯证据”

返回特点：
- 速度相对较慢
- 成本较高
- 对原文更敏感
- 能提供更高粒度的 evidence

### 路由原则
- 默认先查 wiki。
- 当问题命中以下特征时，升级到 PDF RAG：
  - 包含“具体如何定义/如何测量/样本如何构造/哪一页/原文怎么说/识别策略是什么/某篇文章是否提到”等细节型表达；
  - wiki 页面缺失该主题；
  - wiki 页面标注低置信度或待核实；
  - 用户明确要求“回到原文”；
  - agent 在第一轮回答时置信度不足。

这意味着系统里必须有一个明确的 query router，而不是把所有请求都直接送到 PaperQA。

## 2.2 LLM Wiki 初期构建路线

你提出的第二点应被固定为以下技术要求：

### 要求 A：支持自定义 LLM 供应商
- 必须支持 OpenAI-compatible 请求格式。
- 不应把 LLM Wiki 构建流程绑定到单一官方 OpenAI endpoint。
- 应允许通过 `base_url + api_key + model name` 的方式切换供应商。
- 最好兼容 LiteLLM 统一抽象，便于后续接入不同模型。

### 要求 B：支持自定义 Wiki 构建 Prompt
至少应支持外置配置以下 prompt：
- source ingestion prompt
- concept extraction prompt
- entity extraction prompt
- page merge/update prompt
- contradiction detection prompt
- query filing prompt
- summary style prompt

### 要求 C：Wiki 编译逻辑要与业务域一致
由于你的目标是论文检索系统，wiki 的页面模板不能只是泛用 markdown 页面，而应贴合“研究问题—方法—识别—证据—争议—来源”这类学术结构。

### 初期建议
- 不必一开始追求完全自动编译全库。
- 先做半自动 compile：先从一批选定 collection 或 query 结果开始。
- wiki 构建优先处理高价值领域主题，而不是全库平铺。

---

## 三、系统总架构

建议采用如下逻辑层次：

```text
Zotero / PDF Library
        ↓
Export & Normalize Layer
        ↓
┌───────────────────────────────┐
│ Layer A: LLM Wiki Knowledge   │  ← 广度检索、概念回忆、主题导航
└───────────────────────────────┘
        ↓ (必要时升级)
┌───────────────────────────────┐
│ Layer B: PaperQA / PDF RAG    │  ← 原文证据、细节核对、深度问答
└───────────────────────────────┘
        ↓
Query Router / Orchestrator
        ↓
MCP Server Tools
        ↓
Hermes / Other Agents / CLI
        ↓
Optional Write-back to Wiki / Logs / Query Archive
```

每一层职责如下：

### 3.1 源数据层
- Zotero 条目
- Zotero 附件 PDF
- Zotero 标签与 collections
- 可选 notes / highlights

### 3.2 导出规范化层
- 生成本地附件目录
- 生成 manifest.csv
- 生成 library.json / metadata cache
- 做文件去重、路径标准化、缺失字段标记

### 3.3 LLM Wiki 层
- 生成概念页、作者页、主题页、比较页、查询页
- 存放已沉淀知识
- 作为广度检索第一站

### 3.4 PDF RAG 层
- 对本地 PDF 建索引
- 回答细节型问题
- 返回 citations / evidence chunks

### 3.5 路由编排层
- 判定 query 类型
- 决定只查 wiki 还是 wiki + PDF RAG
- 决定是否触发写回 wiki
- 记录 query trace

### 3.6 MCP 工具层
- 把检索、问答、元数据、索引刷新、知识沉淀等能力工具化
- 面向 agent 暴露稳定 schema

---

## 四、关键模块规划

## 4.1 模块 A：Zotero 导出与规范化

**目标：** 从 Zotero 稳定导出文献元数据与 PDF 附件，形成下游统一输入。

### 主要职责
- 读取 Zotero 条目元数据
- 提取 PDF 附件路径
- 导出集合（collections）与 tags
- 生成 `manifest.csv`
- 生成 `library.json`
- 记录缺 DOI / 缺 PDF / 重复项

### 建议输出字段
最小 manifest 字段：
- `file_location`
- `title`
- `doi`

建议增强字段：
- `authors`
- `year`
- `journal`
- `abstract`
- `zotero_key`
- `collections`
- `tags`
- `language`
- `added_date`
- `modified_date`

### 技术要点
- 附件路径必须相对稳定。
- 对不同导出方式（Better BibTeX / 官方导出 / Web API）留适配层。
- 需要支持子 collection 过滤导出，便于构建专题子库。

## 4.2 模块 B：LLM Wiki 编译与查询

**目标：** 形成一个可复用的知识层，支撑快速广度检索。

### 页面类型建议
- `entities/authors/*.md`
- `entities/journals/*.md`
- `concepts/*.md`
- `topics/*.md`
- `comparisons/*.md`
- `queries/*.md`
- `methods/*.md`
- `datasets/*.md`

### 页面内容建议
对于研究型 wiki 页面，建议包含：
- 定义/核心问题
- 相关论文
- 代表性观点
- 主要方法/识别策略
- 争议与分歧
- 与你当前研究主题的关系
- 来源与更新时间

### 供应商配置要求
需要外置配置：
- `provider.base_url`
- `provider.api_key_env`
- `provider.model`
- `provider.timeout`
- `provider.max_tokens`
- `provider.temperature`

### Prompt 配置要求
至少外置以下文件：
- `prompts/wiki_ingest_system.md`
- `prompts/wiki_ingest_user.md`
- `prompts/wiki_merge.md`
- `prompts/wiki_contradiction_check.md`
- `prompts/wiki_query_summarize.md`
- `prompts/wiki_page_template.md`

### 初期实现方式
- 优先用“项目内自研轻编译流程”或参考相关项目实现一层 wrapper。
- 重点不是追求 fancy pipeline，而是确保：
  1. 输入稳定；
  2. prompt 可配；
  3. provider 可换；
  4. 页面结构可控；
  5. 可以增量更新。

## 4.3 模块 C：PaperQA / PDF RAG 深检索

**目标：** 对需要证据追溯的问题做深度检索。

### 主要职责
- 基于本地 PDF 目录建索引
- 基于 query 返回 evidence chunks
- 生成带引文的答案
- 支持按 collection / topic / tag 缩小检索范围

### 应固定的关键配置
- `paper_directory`
- `llm`
- `summary_llm`
- `embedding`
- `answer.evidence_k`
- `answer.answer_max_sources`
- `temperature`
- rate limits

### 深检索适用任务
- 原文如何界定处理组和对照组
- 机制变量如何构造
- 稳健性检验有哪些
- 文中是否明确说明了样本剔除规则
- 作者对因果识别的措辞是否谨慎

## 4.4 模块 D：Query Router

**目标：** 自动判定走广度层还是深度层。

### 路由输入
- 用户 query
- agent 当前任务上下文
- wiki 命中情况
- query 分类结果
- 可选历史 query 记录

### 路由输出
- `wiki_only`
- `wiki_then_pdf`
- `pdf_only`（仅少数特殊场景）
- `needs_clarification`

### 路由策略建议
第一版不必太复杂，可采用“规则 + 小模型判别”混合：
- 规则先判断显性细节词
- 小模型进一步判断是否需要 evidence grounding

### 路由结果需记录
- 为什么升级到 PDF RAG
- 命中了哪些规则
- 使用了哪些 source

## 4.5 模块 E：MCP Server

**目标:** 给 Hermes 等 agent 提供结构化文献检索工具。

### 必备 tools
1. `search_wiki`
2. `search_library`
3. `get_paper_metadata`
4. `ask_wiki`
5. `ask_corpus`
6. `route_query`
7. `build_or_refresh_index`
8. `export_collection`
9. `save_answer_to_wiki`
10. `list_topics_or_collections`

### 推荐扩展 tools
11. `compare_papers`
12. `find_papers_by_method`
13. `find_papers_by_dataset`
14. `trace_claim_to_sources`
15. `list_recent_ingestions`

### 输出风格要求
所有 tool 输出都应：
- 尽量结构化（JSON-friendly）
- 附带 `confidence` 或 `retrieval_mode`
- 附带 `source_type`（wiki / pdf / hybrid）
- 附带 `trace_id` 便于日志追踪

## 4.6 模块 F：写回与沉淀层

**目标：** 选择性将高价值结果沉淀到 wiki，而非每次默认入库。

### 建议入库条件
- 回答至少涉及 2 篇以上关键文献
- 主题具有后续复用价值
- 回答形成了较稳定的概念、方法、比较或综述结构
- 人工或 agent 判定“值得保存”

### 入库类型
- query 页
- concept 页
- comparison 页
- topic synthesis 页

---

## 五、完整实施阶段规划

## Phase 0：需求冻结与预研设计

### Task 0.1：冻结系统边界
**Objective:** 明确一期只做本地单用户 agent-first 系统，不做复杂平台化。

**Files:**
- Create: `docs/architecture/scope.md`
- Create: `docs/architecture/use-cases.md`

**应明确：**
- 用户类型：你自己 + 可被 agent 调用
- 优先接口：CLI/MCP
- 非目标：多人协作、复杂权限、前端重 UI

### Task 0.2：整理核心 use cases
**Objective:** 把未来常见任务抽象成若干标准检索场景。

**Files:**
- Modify: `docs/architecture/use-cases.md`

**至少覆盖场景：**
- 快速回忆某个研究主题
- 查某类方法的代表论文
- 追溯某篇文章的细节表述
- 比较两类识别策略
- 对某一 topic 自动生成综述草稿
- 把高价值结果写入 wiki

### Task 0.3：冻结多层检索策略
**Objective:** 正式确定“广度查 wiki，深度查 wiki + pdf”的路由原则。

**Files:**
- Create: `docs/architecture/retrieval-routing.md`

**验证：**
- 每类 query 都能映射到明确 retrieval mode。

---

## Phase 1：仓库与配置骨架

### Task 1.1：初始化仓库结构
**Objective:** 创建最小可扩展代码骨架。

**Files:**
- Create: `README.md`
- Create: `pyproject.toml`
- Create: `.gitignore`
- Create: `.env.example`
- Create: `configs/`
- Create: `scripts/`
- Create: `src/paper_research_assistant/`
- Create: `tests/`
- Create: `docs/`
- Create: `prompts/`

### Task 1.2：外置基础配置
**Objective:** 把 provider、paths、retrieval、wiki、mcp 配置外置。

**Files:**
- Create: `configs/providers.yaml`
- Create: `configs/paths.yaml`
- Create: `configs/retrieval.yaml`
- Create: `configs/wiki.yaml`
- Create: `configs/mcp.yaml`
- Create: `configs/paperqa.default.json`

**重点：**
- provider 必须支持 OpenAI-compatible base_url
- wiki prompts 路径必须可配置
- paperqa settings 必须尽量固定，避免索引漂移

### Task 1.3：建立 prompt 目录规范
**Objective:** 让 LLM 行为可替换、可版本化。

**Files:**
- Create: `prompts/wiki_ingest_system.md`
- Create: `prompts/wiki_ingest_user.md`
- Create: `prompts/wiki_merge.md`
- Create: `prompts/wiki_query.md`
- Create: `prompts/router_classify.md`
- Create: `prompts/rag_answer.md`
- Create: `prompts/comparison_synthesis.md`

**验证：**
- 所有核心 prompt 都不硬编码在 Python 文件里。

---

## Phase 2：Zotero 导出桥接层

### Task 2.1：确定 Zotero 导出方案
**Objective:** 在 Better BibTeX、官方导出、API 之间选定一期方案。

**Files:**
- Create: `docs/architecture/zotero-export.md`

**建议优先顺序：**
1. 本地导出 + 附件目录扫描
2. collection-aware 导出
3. 后续再考虑 API 增量同步

### Task 2.2：实现导出脚本
**Objective:** 导出统一元数据中间层。

**Files:**
- Create: `scripts/export_zotero.py`
- Create: `src/paper_research_assistant/zotero/exporter.py`
- Test: `tests/test_exporter.py`

### Task 2.3：生成与校验 manifest
**Objective:** 生成 PaperQA 可消费的 `manifest.csv`。

**Files:**
- Create: `scripts/normalize_manifest.py`
- Create: `src/paper_research_assistant/zotero/manifest.py`
- Test: `tests/test_manifest.py`

### Task 2.4：建立样本文库
**Objective:** 从 Zotero 中选出 20–50 篇代表性论文做回归测试集。

**Files:**
- Create: `data/samples/README.md`
- Create: `data/samples/sample_manifest.csv`

**验证：**
- 覆盖英文、中文、缺 DOI、多个 collection 的混合样本。

---

## Phase 3：LLM Wiki 最小可用版

### Task 3.1：初始化 wiki 骨架
**Objective:** 创建 wiki 目录结构和 schema。

**Files:**
- Create: `wiki/SCHEMA.md`
- Create: `wiki/index.md`
- Create: `wiki/log.md`
- Create: `wiki/entities/`
- Create: `wiki/concepts/`
- Create: `wiki/topics/`
- Create: `wiki/comparisons/`
- Create: `wiki/queries/`
- Create: `wiki/raw/`

### Task 3.2：实现 provider 抽象
**Objective:** 让 wiki 编译过程支持自定义 OpenAI-compatible provider。

**Files:**
- Create: `src/paper_research_assistant/wiki/providers.py`
- Create: `src/paper_research_assistant/config.py`
- Test: `tests/test_wiki_provider_config.py`

**验证重点：**
- 可通过配置切换 base_url / api key / model
- 不改业务代码即可切换供应商

### Task 3.3：实现 prompt-driven wiki compile
**Objective:** 用外置 prompt 驱动 ingest / merge / update。

**Files:**
- Create: `src/paper_research_assistant/wiki/compiler.py`
- Create: `src/paper_research_assistant/wiki/templates.py`
- Test: `tests/test_wiki_compiler.py`

**验证重点：**
- prompt 文件变更后，编译逻辑可随之调整
- 页面模板可控

### Task 3.4：实现 wiki 查询接口
**Objective:** 为广度层提供 search / ask 能力。

**Files:**
- Create: `src/paper_research_assistant/wiki/search.py`
- Create: `src/paper_research_assistant/wiki/query.py`
- Test: `tests/test_wiki_query.py`

**建议功能：**
- filename / content search
- tag/topic search
- page summary answer
- confidence 标记

---

## Phase 4：PaperQA 深检索层

### Task 4.1：跑通样本文库 PaperQA CLI
**Objective:** 在真实样本文库上验证可用性。

**Files:**
- Modify: `README.md`
- Create: `docs/evaluation/paperqa-spike.md`

### Task 4.2：封装 Python API
**Objective:** 提供可被 MCP server 调用的统一接口。

**Files:**
- Create: `src/paper_research_assistant/retrieval/paperqa_client.py`
- Create: `scripts/build_index.py`
- Create: `scripts/ask_papers.py`
- Test: `tests/test_paperqa_client.py`

### Task 4.3：实现子库/过滤检索
**Objective:** 支持按 collection、tags、topic、年份范围缩小语料范围。

**Files:**
- Modify: `src/paper_research_assistant/retrieval/paperqa_client.py`
- Test: `tests/test_retrieval_filters.py`

### Task 4.4：记录 evidence 与 trace
**Objective:** 让深检索结果可审计。

**Files:**
- Create: `src/paper_research_assistant/retrieval/tracing.py`
- Create: `tests/test_tracing.py`

---

## Phase 5：多层路由器

### Task 5.1：定义 query 分类标准
**Objective:** 明确哪些问题属于 wiki-only，哪些需要升级。

**Files:**
- Create: `docs/architecture/query-taxonomy.md`
- Create: `tests/test_router_rules.py`

### Task 5.2：实现规则路由器
**Objective:** 先用显式规则完成第一版 routing。

**Files:**
- Create: `src/paper_research_assistant/router/rules.py`
- Create: `src/paper_research_assistant/router/models.py`
- Test: `tests/test_router_rules.py`

### Task 5.3：实现混合路由器
**Objective:** 在规则之上加入小模型判断或 prompt 分类。

**Files:**
- Create: `src/paper_research_assistant/router/classifier.py`
- Modify: `prompts/router_classify.md`
- Test: `tests/test_router_classifier.py`

### Task 5.4：实现联合回答器
**Objective:** 当需要深检索时，先读 wiki，再补充 PDF evidence，形成联合回答。

**Files:**
- Create: `src/paper_research_assistant/router/orchestrator.py`
- Test: `tests/test_orchestrator.py`

**联合回答建议结构：**
- wiki 层已有认识
- pdf 层新增/核实证据
- 最终综合回答
- 主要来源列表
- 是否建议写回 wiki

---

## Phase 6：MCP 服务实现

### Task 6.1：定义 MCP tool contract
**Objective:** 明确每个 tool 的输入输出 schema。

**Files:**
- Create: `docs/mcp/tool-contracts.md`
- Create: `configs/mcp-tools.yaml`

### Task 6.2：实现最小 MCP server
**Objective:** 暴露核心检索工具。

**Files:**
- Create: `scripts/run_mcp_server.py`
- Create: `src/paper_research_assistant/mcp/server.py`
- Create: `src/paper_research_assistant/mcp/tools.py`
- Test: `tests/test_mcp_tools.py`

### Task 6.3：接入路由器与检索层
**Objective:** 让 MCP tools 不是直接调用单一后端，而是走统一编排层。

**Files:**
- Modify: `src/paper_research_assistant/mcp/tools.py`
- Modify: `src/paper_research_assistant/router/orchestrator.py`

### Task 6.4：补充 agent-friendly 输出
**Objective:** 提高 tool 输出的可组合性。

**Files:**
- Modify: `src/paper_research_assistant/mcp/tools.py`
- Test: `tests/test_mcp_output_schema.py`

**至少输出：**
- `mode_used`
- `confidence`
- `sources`
- `trace_id`
- `next_actions`

---

## Phase 7：知识沉淀与写回机制

### Task 7.1：定义写回门槛
**Objective:** 防止 wiki 污染。

**Files:**
- Create: `docs/architecture/wiki-writeback-policy.md`

### Task 7.2：实现 query result → wiki page
**Objective:** 选择性把高价值结果沉淀为 markdown 页面。

**Files:**
- Create: `src/paper_research_assistant/wiki/writer.py`
- Create: `scripts/save_to_wiki.py`
- Test: `tests/test_wiki_writer.py`

### Task 7.3：实现 topic merge / dedupe
**Objective:** 避免同义主题被拆成多个页面。

**Files:**
- Create: `src/paper_research_assistant/wiki/linker.py`
- Test: `tests/test_wiki_dedupe.py`

---

## Phase 8：评估、日志与运维

### Task 8.1：建立评估集
**Objective:** 用真实研究问题评估系统效果。

**Files:**
- Create: `eval/questions.md`
- Create: `eval/gold-notes.md`

**建议问题类别：**
- 概念解释
- 方法比较
- 原文核对
- 样本/变量/机制细节
- 多文献综合

### Task 8.2：建立日志与 trace 系统
**Objective:** 记录检索流程，支持调试与复盘。

**Files:**
- Create: `data/logs/query-trace.jsonl`
- Create: `src/paper_research_assistant/logging.py`
- Test: `tests/test_logging.py`

### Task 8.3：建立健康检查
**Objective:** 确保长期维护可行。

**Files:**
- Create: `scripts/healthcheck.py`
- Test: `tests/test_healthcheck.py`

**检查项：**
- provider 配置有效性
- manifest 完整性
- PDF 路径有效性
- wiki 索引完整性
- paperqa settings 漂移
- MCP server readiness

---

## 六、文件结构建议（完整形态）

```text
paper-research-assistant/
├── README.md
├── pyproject.toml
├── .env.example
├── .gitignore
├── configs/
│   ├── providers.yaml
│   ├── paths.yaml
│   ├── retrieval.yaml
│   ├── wiki.yaml
│   ├── mcp.yaml
│   ├── mcp-tools.yaml
│   └── paperqa.default.json
├── prompts/
│   ├── wiki_ingest_system.md
│   ├── wiki_ingest_user.md
│   ├── wiki_merge.md
│   ├── wiki_query.md
│   ├── router_classify.md
│   ├── rag_answer.md
│   └── comparison_synthesis.md
├── docs/
│   ├── architecture/
│   │   ├── scope.md
│   │   ├── use-cases.md
│   │   ├── retrieval-routing.md
│   │   ├── query-taxonomy.md
│   │   ├── zotero-export.md
│   │   └── wiki-writeback-policy.md
│   ├── mcp/
│   │   └── tool-contracts.md
│   └── evaluation/
│       └── paperqa-spike.md
├── data/
│   ├── zotero-export/
│   │   ├── manifest.csv
│   │   ├── library.json
│   │   └── attachments/
│   ├── logs/
│   │   └── query-trace.jsonl
│   └── samples/
├── wiki/
│   ├── SCHEMA.md
│   ├── index.md
│   ├── log.md
│   ├── raw/
│   ├── entities/
│   ├── concepts/
│   ├── topics/
│   ├── comparisons/
│   └── queries/
├── scripts/
│   ├── export_zotero.py
│   ├── normalize_manifest.py
│   ├── build_index.py
│   ├── ask_papers.py
│   ├── save_to_wiki.py
│   ├── healthcheck.py
│   └── run_mcp_server.py
├── src/
│   └── paper_research_assistant/
│       ├── __init__.py
│       ├── config.py
│       ├── logging.py
│       ├── zotero/
│       │   ├── exporter.py
│       │   └── manifest.py
│       ├── wiki/
│       │   ├── providers.py
│       │   ├── compiler.py
│       │   ├── query.py
│       │   ├── search.py
│       │   ├── writer.py
│       │   ├── linker.py
│       │   └── templates.py
│       ├── retrieval/
│       │   ├── paperqa_client.py
│       │   └── tracing.py
│       ├── router/
│       │   ├── models.py
│       │   ├── rules.py
│       │   ├── classifier.py
│       │   └── orchestrator.py
│       └── mcp/
│           ├── server.py
│           └── tools.py
├── tests/
│   ├── test_exporter.py
│   ├── test_manifest.py
│   ├── test_wiki_provider_config.py
│   ├── test_wiki_compiler.py
│   ├── test_wiki_query.py
│   ├── test_paperqa_client.py
│   ├── test_retrieval_filters.py
│   ├── test_router_rules.py
│   ├── test_router_classifier.py
│   ├── test_orchestrator.py
│   ├── test_mcp_tools.py
│   ├── test_mcp_output_schema.py
│   ├── test_wiki_writer.py
│   ├── test_wiki_dedupe.py
│   ├── test_logging.py
│   └── test_healthcheck.py
└── eval/
    ├── questions.md
    └── gold-notes.md
```

---

## 七、技术细节补充（我建议你预先纳入）

## 7.1 Prompt 版本管理
- 每次重要 prompt 修改都应可追踪。
- prompt 最好单独保存并在日志中记录版本号。
- 查询结果可关联“使用了哪个 prompt 版本”。

## 7.2 Provider 抽象不要只做给 wiki
- wiki provider、router classifier、comparison synthesis 最好共用统一 LLM provider abstraction。
- 避免后续每个模块都有一套独立 provider 配置。

## 7.3 检索范围控制
- 对深检索，必须支持限定 collection / tag / year / author。
- 否则全库 RAG 在文献规模扩大后成本与噪声都会上升。

## 7.4 Query Trace 很重要
建议每次查询都记录：
- 原始 query
- 路由模式
- wiki 命中页
- pdf 命中论文
- 主要 evidence
- 用到的模型
- 用到的 prompt 版本
- 是否写回 wiki

## 7.5 对中文语料的单独验证
- 中文论文页面结构可能不规则。
- 若存在扫描 PDF，可能需要 OCR 预处理。
- 中英文混合检索时，embedding 模型选择要单独评估。

## 7.6 增量更新机制
- Zotero 导出不应每次全量重做。
- wiki compile 也不应每次重建全部页面。
- 建议保留 `modified_date`、file hash、zotero key 作为增量依据。

## 7.7 “检索”和“写作辅助”要分开
- 当前系统核心是 retrieval infrastructure。
- 不建议一开始把论文综述自动写作也做成主线功能。
- 但可以在后期作为依赖该系统的上层能力。

---

## 八、测试与验证计划

## 8.1 功能验证
- Zotero 导出是否稳定
- manifest 是否正确
- wiki 是否能完成初始 ingest
- PaperQA 是否能对样本文库回答真实问题
- router 是否能正确升级深检索
- MCP tools 是否可被 agent 自主调用

## 8.2 质量验证
重点看：
- 广度检索是否真的更快
- 深度检索是否真的补足细节
- 联合回答是否比单一 wiki / 单一 PDF RAG 更有用
- wiki 是否真的带来知识复用，而不是制造冗余

## 8.3 成本验证
需要单独记录：
- wiki compile 成本
- 单次 wiki-only query 成本
- 单次 hybrid query 成本
- 首次建索引与增量更新耗时

## 8.4 Agent 使用验证
建议设计 5–10 个真实 agent 任务，检查其是否能：
- 自己决定先查 wiki 还是升级深检索
- 组合使用 search / metadata / compare / save-to-wiki 工具
- 在输出中正确区分“已有知识”和“原文证据”

---

## 九、主要风险与对策

### 风险 1：LLM Wiki 质量不稳定
**表现：** 页面风格飘忽、抽取字段不一致、总结过度。  
**对策：** prompt 外置、模板固定、人工抽检、限制初期自动入库范围。

### 风险 2：路由过度复杂
**表现：** 一开始就上太复杂的智能路由，难以调试。  
**对策：** 第一版先规则路由，再逐步引入模型分类。

### 风险 3：Zotero 桥接层成为瓶颈
**表现：** 附件路径、元数据清洗、collection 同步不稳定。  
**对策：** 先用样本文库做扎实，再扩全库。

### 风险 4：全库深检索成本较高
**表现：** PaperQA 对大库响应慢、费用上升。  
**对策：** 强制支持 collection / topic 子集检索，避免默认全库深搜。

### 风险 5：wiki 污染
**表现：** 每次 query 都写入 wiki，知识库迅速失去可读性。  
**对策：** 单独制定 write-back policy，只保留高价值内容。

### 风险 6：中文 PDF 兼容问题
**表现：** 解析不稳、抽取不全、检索效果下降。  
**对策：** 中文样本单独建评估集，必要时补 OCR 流程。

---

## 十、推荐实施顺序（最小风险路径）

推荐按以下顺序推进：

1. 冻结用例、路由原则和系统边界。
2. 建仓库骨架、配置体系、prompt 目录。
3. 打通 Zotero → manifest 样本导出。
4. 建立最小 wiki 骨架与 provider 抽象。
5. 验证 PaperQA 在样本文库上的深检索能力。
6. 先做规则版 router。
7. 再做最小 MCP server。
8. 最后接写回 wiki 与增量更新。

这个顺序的优点是：
- 先验证两层检索都能工作；
- 在引入 MCP 前先把后端能力做扎实；
- 减少“协议先行但底层不稳”的风险。

---

## 十一、当前最值得确认的开放问题

以下问题会影响后续实现细节，建议你之后回答：

1. 你的一期更偏向“只给自己本地使用”，还是“从一开始就强约束为 agent 基础设施”？
2. 你的 Zotero 附件目前是否已经大部分落地到本地文件，而不是仅云端同步引用？
3. 你最常用的 query 语言是中文、英文，还是中英混合？
4. 你是否希望 wiki 直接作为 Obsidian vault 使用？
5. 你是否希望深检索默认仅在某个 collection 范围内进行，而不是整个库？
6. 你对 provider 抽象更偏向：
   - A. 统一走 LiteLLM
   - B. 统一走 OpenAI-compatible 原生 client
   - C. 两者兼容
7. 你是否希望未来把 Zotero notes / highlights 也纳入 wiki 编译源？

---

## 十二、完成定义（完整规划阶段）

当以下条件满足时，可以认为“完整规划阶段”完成：

- 已明确多层检索策略及路由原则；
- 已明确 LLM Wiki 的 provider 抽象与 prompt 可配置要求；
- 已明确 MCP 工具清单和大致 schema；
- 已明确仓库结构、模块边界、实施阶段和测试计划；
- 已能据此进入实际实现阶段，而无需再大范围返工架构。

---

## 十三、后续执行建议

在这份完整规划之后，若进入下一步，最合理的动作顺序是：

1. 再写一份“Phase 0–2 的超细执行清单”；或
2. 直接进入执行模式，先搭仓库骨架 + 配置 + Zotero 样本导出 + wiki provider 抽象。

如果只选一个起点，建议优先：
- 仓库骨架
- providers/prompt 配置体系
- Zotero 样本文库导出
- PaperQA 样本验证

这四项会最快暴露真正的技术瓶颈。