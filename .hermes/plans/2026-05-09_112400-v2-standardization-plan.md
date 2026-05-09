# paper-compass v2 标准化 & 公开化计划

**创建时间**: 2026-05-09 11:24
**当前版本**: v1.5（52 tests passed）
**目标版本**: v2.0
**原则**: v2 = 硬化而非膨胀（quality/governance hardening, NOT feature sprawl）

---

## 一、目标定位

将 paper-compass 从"个人研究原型/MVP"升级为：
1. **检索能力规范化**：检索接口行为可预期、可验证、可审计
2. **MCP 服务标准化**：符合 MCP 协议规范，第三方可安装、可配置、可部署
3. **公开化就绪**：README 完善、依赖声明完整、配置文件模板化、安装流程文档化

---

## 二、现状评估

### 2.1 已完成的 v1.5 硬化（基础）
| 模块 | 状态 | 说明 |
|------|------|------|
| MCP contract 集中化 | ✅ 完成 | `mcp_contracts.py` — `tools/list` 与 handler 参数对齐 |
| Trace 日志 | ✅ 完成 | `logging.py` — JSONL 事件记录（默认关闭） |
| `search_library` exact-match tier | ✅ 完成 | key/doi/title 精确匹配优先排序 |
| Wiki 检索后处理 | ✅ 完成 | log.md/index.md 排除、sec0 惩罚、页面去重 |
| PDF 结果去重 | ✅ 完成 | `_dedupe_pdf_chunks_by_item` |
| Wiki 增量索引 | ✅ 完成 | manifest-based fingerprint, new/changed/unchanged/deleted |
| Wiki 并发生成 | ✅ 完成 | ThreadPoolExecutor(max_workers=10) |
| `.env` 加载专项 | ✅ 完成 | `env_utils.py` — 无条件覆盖、缺失/目录安全 no-op |
| 测试覆盖 | ✅ 52 passed | 7 测试文件，含 contract/protocol/retrieval/logging/env |

### 2.2 当前 5 个 MCP 工具
| 工具 | 能力 | 成熟度 |
|------|------|--------|
| `search_wiki` | 语义向量搜索 wiki 知识页 | ✅ 可用 |
| `search_library` | 关键词 + exact-match 搜索论文元数据 | ✅ 可用 |
| `ask_research` | 路由器：wiki → escalate → PDF 证据拼接 | ⚠️ MVP |
| `get_paper_metadata` | 按 key/DOI/标题 查单篇论文 | ✅ 可用 |
| `save_to_wiki` | 写回 wiki 页面 | ✅ 可用 |

### 2.3 缺失的关键功能
- ❌ **无可直接检索原文段落+论文标题的工具**（这是本次用户明确要求的功能）
- ❌ 无 healthcheck 脚本
- ❌ 无 evaluation benchmark
- ❌ 无 `search_passages` 类型的 concordance 检索
- ❌ `pyproject.toml` 依赖声明不完整（缺 chromadb/pymupdf/pdfplumber/rank_bm25/sentence_transformers）
- ❌ README 仍偏内部用途描述，缺少安装/配置/部署指南
- ❌ 无任何安装脚本（setup.py / CLI entry point 未暴露）
- ❌ 无 `.env.example` 模板

---

## 三、v2 任务拆解

### P0 — 新增核心检索工具（本次最高优先级）

#### P0.1 新增 `search_passages` MCP 工具

**目标**: 用户输入关键词/简要表达 → 返回匹配的原文段落 + 论文标题等元信息。

**需求定义**:
- 输入：`query`（关键词或短语），可选 `limit`、`filters`（collection/tag/year 等）
- 输出：`matches` 列表，每项包含：
  - `doc_id`：论文 Zotero key
  - `title`：论文标题
  - `authors`：作者
  - `year`：年份
  - `passage`：匹配的**原文段落**（完整段落，非截断 snippet）
  - `page_num`：页码（如有）
  - `score`：相关性分数
  - `collection`：论文所属合集
  - `tags`：论文标签

**实施路径**:
```
检索入口:
  search_passages(query) →
    1. vector_search(collection="papers") → PDF 分块语义匹配
    2. 或：直接对 data/texts/*.txt 做全文关键词搜索（BM25 / ripgrep）
    3. 匹配结果关联 library.json → 获取 title/authors/year 等元数据
    4. 返回原始段落（200-500 字符，以自然段落边界为截断）
```

**涉及文件**:
- `src/miniresearch/mcp_contracts.py` — 新增 contract
- `src/miniresearch/filters.py` — 新增 `search_passages()` 函数
- `src/miniresearch/mcp_server.py` — 新增 `_tool_search_passages()` handler
- `tests/test_passage_search.py` — 新增测试
- `configs/mcp.yaml` — 工具列表更新

**技术方案**（2 条路径，建议双模式）：

**路径 A — 向量语义匹配（推荐默认）**:
- 对 PDF chunks ChromaDB（`papers_*` collection）做 `vector_search`
- 每个 chunk 返回时附带其 `item_key` → 查 library.json 获取元数据
- 返回的 passage 是整个 chunk 文本（原 `documents` 字段），不做截断
- 优势：语义匹配，模糊表达也能找到相关内容

**路径 B — 全文关键词匹配（补充模式）**:
- 对 `data/texts/*.txt` 目录做关键词检索
- 使用 Python `re` 或 `ripgrep` 查找包含 query 中关键词的段落
- 按匹配密度排序
- 优势：精确匹配，不会漏掉关键词出现但语义向量不接近的内容

**建议实现**：工具默认走路径 A（向量语义），通过 `search_mode` 参数支持 `"semantic" | "keyword" | "hybrid"`。

#### P0.2 增强 `ask_research` → 返回原文段落引用

**问题**: 当前 `ask_research` 返回拼接摘要文本，不包含原文段落引用。
**改进**: `pdf_context.evidence_snippets` 已包含 snippet（300 字符），改为返回完整段落，并确保每个 snippet 附带论文标题和页码。

---

### P1 — MCP 服务标准化（必做）

#### P1.1 补齐依赖声明
**文件**: `pyproject.toml`

当前缺失的运行时依赖：
```toml
dependencies = [
    "pyyaml>=6.0",
    "pydantic>=2.7",
    "paper-qa>=5",
    "pytest>=8.0",
    # v2 新增
    "chromadb>=0.4.0",
    "pymupdf>=1.22.0",
    "pdfplumber>=0.7.0",
    "rank-bm25>=0.2.0",
    "sentence-transformers>=2.2.0",
]
```

#### P1.2 MCP 协议对齐检查
**当前状态**: v1.5 已做 contract 集中化，`tools/list` 与 handler 参数已对齐。
**v2 需要**:
- [x] ~~contract 集中化~~（已完成）
- [ ] 检查 `tools/call` 响应格式是否符合 MCP spec `CallToolResult`（`content: [{type: "text", text: "..."}]`）
- [ ] 错误响应使用标准 MCP error codes（非自定义 envelope）
- [ ] stdio 模式支持 `initialize` → `initialized` 握手、`notifications/initialized`
- [ ] 编写 MCP Inspector 兼容性验证脚本

**涉及文件**:
- `scripts/run_mcp_server.py`
- `src/miniresearch/mcp_server.py`
- `tests/test_mcp_protocol.py`（扩展）

#### P1.3 Healthcheck 脚本
**新建**: `scripts/healthcheck.py`

功能：
1. 检查 `.env` 是否存在并加载成功
2. 检查 `data/zotero-export/library.json` 存在且非空
3. 检查 ChromaDB 目录存在并列出 collections
4. 检查 `wiki/` 目录存在
5. 检查 embedding provider 连通性（可选 `--smoke`）
6. 输出状态报告：所有子系统 OK/ERROR

```bash
python3 scripts/healthcheck.py         # 基础检查
python3 scripts/healthcheck.py --smoke  # 含 API 连通性
```

#### P1.4 `.env.example` 模板
**新建**: `.env.example`

```bash
# paper-compass environment variables
# Copy to .env and fill in your values

# Mimo LLM (wiki generation)
MIMO_BASE_URL=https://token-plan-cn.xiaomimimo.com/v1
XIAOMI_API_KEY=your_key_here

# Volcengine embedding
VOLC_EMBED_BASE_URL=https://ark.cn-beijing.volces.com/api/v3/embeddings/multimodal
VOLC_EMBED_API_KEY=your_key_here
VOLC_EMBED_MODEL=your_endpoint_id

# PaperQA (optional)
PAPERQA_BASE_URL=
PAPERQA_API_KEY=
PAPERQA_MODEL=
```

---

### P2 — 检索质量治理 & Evaluation（应做）

#### P2.1 建立 evaluation benchmark
**新建**: `eval/` 目录

结构：
```
eval/
  ├── queries.yaml          # 基准查询集（中英文混合，覆盖不同检索场景）
  ├── expected_results.yaml # 预期结果（paper key 白名单）
  ├── run_eval.py           # 评测脚本
  └── README.md             # 评测说明
```

评测指标：
- Recall@K：预期论文是否在 top-K 结果中
- MRR：第一个相关结果的倒数排名
- 通过率：≥70% 查询找到预期论文

#### P2.2 `search_library` 检索增强
**当前缺陷**: 纯关键词计数评分，对语义相近但用词不同的查询效果差。
**改进方案**:
- 引入 query expansion（同义词/中英对照）
- 对 `title` 做 fuzzy matching（`rapidfuzz` 或 `thefuzz`）
- 对中文查询做分词后评分（而非逐字 `count`）
- 可选：使用 `sentence-transformers` 对 library 元数据做轻量级向量检索

#### P2.3 Wiki 检索评估
- 建立 wiki query 评估集（含 20-30 个典型学术查询）
- 检测结果是否包含 log.md/index.md 噪声（回归测试）
- 检测 section 0 是否被适当惩罚

---

### P3 — 文档与可部署性（公开化就绪）

#### P3.1 README 重写
**状态**: 当前 README 偏内部备注风格。
**需要**:
- 项目简介 + 适用场景
- 安装步骤（`pip install -e .`）
- 环境配置（`.env.example`）
- 数据准备（Zotero SQLite → sync → index → wiki）
- 启动 MCP 服务
- MCP client 配置示例（Hermes、Claude Desktop 等）
- 工具说明 & API 参考

#### P3.2 安装入口
- 在 `pyproject.toml` 中添加 `[project.scripts]` 入口点
- 确保 `pip install -e .` 后可直接使用 CLI 命令

#### P3.3 清理工作
- 移除陈旧规划文件中的过时引用
- 统一版本号到 `2.0.0`
- Tag v2.0 release

---

## 四、执行顺序

```
Phase 1 (本次): P0.1 search_passages 实现 → P0.2 ask_research 增强
Phase 2:       P1.1 依赖补齐 → P1.4 .env.example → P1.3 healthcheck
Phase 3:       P1.2 MCP 协议对齐 → P2.1 evaluation benchmark
Phase 4:       P2.2 search_library 增强 → P2.3 wiki eval
Phase 5:       P3.1 README → P3.2 entry point → P3.3 清理 & tag
```

每阶段独立可交付，不互相阻塞。

---

## 五、风险与未决问题

1. **search_passages 全文检索模式**：是否需要引入 `ripgrep` 或纯 Python `re` 即可？纯 Python 对大文本集可能较慢。建议先用 Python re + 文件缓存，性能瓶颈出现后再换 rg。

2. **MCP 协议兼容性**：当前 Minimal JSON-RPC stub 与完整 MCP spec 的差距有多大？需要对着 spec 做一次 gap analysis。已有 `test_mcp_protocol.py` 提供了基础 stdio smoke test。

3. **双语检索质量**：中文查询的检索质量是已知短板（`search_library` 的 `_score` 函数对中文是逐字 count），v2 是否引入中文分词（jieba）还是放在 P2 作为增强？建议 P0 的 `search_passages` 默认走向量语义模式绕过此问题，中文分词增强放到 P2.2。

4. **PaperQA 集成状态**：`pyproject.toml` 声明了 `paper-qa>=5`，但 `rag.yaml` 描述的 PaperQA 后端并未在运行时代码中实际接入（`ask_research` 用的是 `vector_search` + `search_library`）。v2 是否补齐 PaperQA 接入，还是移除未实现的 rag 配置？建议：暂不移除配置，但 README 标注为 experimental/planned。

---

## 六、验证标准

v2 完成的判断标准：
- [ ] `search_passages` 可用，输入"家族企业继承"能返回原文段落+论文标题
- [ ] MCP 协议 smoke test 通过（`tools/list` + `tools/call`）
- [ ] `python3 -m pytest tests/ -v` 全部通过
- [ ] `python3 scripts/healthcheck.py` 返回全绿
- [ ] `pip install -e .` 在新 venv 中可完成安装
- [ ] `.env.example` → `.env` → 配置后可运行完整流程
- [ ] README 他人可按步骤复现
