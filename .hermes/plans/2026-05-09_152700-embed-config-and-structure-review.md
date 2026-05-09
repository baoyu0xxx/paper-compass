# Plan: Embedding Config Refactor + Project Structure Review

## Goal

两个优化任务：
1. **Embedding 模型配置重构** — README、`.env.example`、`configs/providers.yaml` 和代码中对嵌入模型的配置方式，从"火山引擎多模态硬编码"改为"标准 OpenAI-compatible embed API"为默认范式，模型选择下沉到配置文件
2. **项目结构评审** — 评估 `src/miniresearch/` 扁平结构是否合适，给出调整建议

---

## Task 1: Embedding 配置重构

### 1.1 当前状态 (现状诊断)

**`.env.example`** 的问题：
- 变量名带厂商前缀 `VOLC_EMBED_*`，暗示项目绑定火山引擎
- 示例值直接写死火山引擎多模态端点 `https://ark.cn-beijing.volces.com/api/v3/embeddings/multimodal`
- 模式选择 (`VOLC_EMBED_MODEL=your_endpoint_id`) 放在环境变量层面，混入了基础设施细节

**`configs/providers.yaml`** 的问题：
- `embedding_main` 的 `api_style: openai-compatible` 是正确的，但变量名通过 `base_url_env` / `model_env` 间接引用 `VOLC_EMBED_*` 系列
- 缺少 `provider` 字段（如 `volcengine` / `openai` / `local`），导致代码中硬编码 `provider="volcengine"`

**代码层硬编码** (4处)：
| 文件 | 行 | 硬编码内容 |
|------|-----|-----------|
| `scripts/build_index.py` | 154 | `provider="volcengine"` |
| `src/miniresearch/filters.py` | 266 | `provider="volcengine"` + 直接从 `os.environ` 读 `VOLC_EMBED_*` |
| `src/miniresearch/mcp_server.py` | 42-46 | 同上，直接从 `os.environ` 读 `VOLC_EMBED_*` |
| `src/miniresearch/embedder.py` | 169 | `is_multimodal = "volces" in url or "multimodal" in url` 靠 URL 字符串匹配判断格式 |

**READMe** 的问题：
- 「环境变量」表格中 `VOLC_EMBED_BASE_URL` 描述为"火山引擎多模态嵌入端点"
- 没有说明如何切换到标准 OpenAI embed（如 `text-embedding-3-small`）
- 安装依赖表中写"嵌入服务 API 密钥 | 火山引擎多模态嵌入"

### 1.2 目标状态

参考业界惯例（OpenAI Python SDK、LiteLLM、RAG-Assistant-for-Zotero 等），嵌入配置应该分层：

```
Layer 1: .env — 只有 URL 和 Key（通用变量名，无厂商绑定）
  EMBED_BASE_URL=https://api.openai.com/v1
  EMBED_API_KEY=sk-xxx
  EMBED_MODEL=text-embedding-3-small          ← 可选，默认在 providers.yaml

Layer 2: configs/providers.yaml — 具体模型选择和端点路径
  embedding_main:
    provider: openai                           ← 驱动 embedder.py 里的格式分支
    api_style: openai-compatible
    base_url_env: EMBED_BASE_URL
    api_key_env: EMBED_API_KEY
    model: text-embedding-3-small             ← 默认模型，可被 EMBED_MODEL 覆盖

Layer 3: 代码 — 通过 get_provider_config() 读取，不再硬编码 provider 名
```

支持多个 provider profile，部署者按需选用：
```yaml
# 默认：标准 OpenAI embed
embedding_main:
  provider: openai
  ...

# 可选：火山引擎多模态
embedding_volcengine:
  provider: volcengine
  base_url_env: VOLC_EMBED_BASE_URL
  api_key_env: VOLC_EMBED_API_KEY
  model_env: VOLC_EMBED_MODEL
```

### 1.3 具体变更

#### Step 1: `.env.example` 重写

```
# ── Embedding ────────────────────────────────────────────────────────────
# Standard OpenAI-compatible embedding API (default)
EMBED_BASE_URL=https://api.openai.com/v1
EMBED_API_KEY=your_key_here
# EMBED_MODEL=text-embedding-3-small    # optional — override providers.yaml default

# ── Volcengine multimodal embedding (alternative) ────────────────────────
# VOLC_EMBED_BASE_URL=https://ark.cn-beijing.volces.com/api/v3/embeddings/multimodal
# VOLC_EMBED_API_KEY=your_key_here
# VOLC_EMBED_MODEL=ep-20260420154519-xxxxx
```

变更要点：
- 默认区块改为标准 OpenAI 格式变量名 `EMBED_BASE_URL` / `EMBED_API_KEY`
- 火山引擎降级为注释掉的备选区块
- `EMBED_MODEL` 标记为可选——默认值在 `providers.yaml` 里

#### Step 2: `configs/providers.yaml` 重构

```yaml
providers:
  embedding_main:
    provider: openai                    # ← 新增：驱动代码分支
    api_style: openai-compatible
    base_url_env: EMBED_BASE_URL
    api_key_env: EMBED_API_KEY
    model: text-embedding-3-small       # ← 默认模型，可被 EMBED_MODEL env 覆盖
    model_env: EMBED_MODEL              # ← 可选：环境变量覆盖 model
    timeout_seconds: 120

  embedding_volcengine:                 # ← 新增：火山的备选 profile
    provider: volcengine
    api_style: openai-compatible
    base_url_env: VOLC_EMBED_BASE_URL
    api_key_env: VOLC_EMBED_API_KEY
    model_env: VOLC_EMBED_MODEL
    timeout_seconds: 120
```

- 新增 `provider` 字段（`openai` / `volcengine` / `local`），替代代码中硬编码的字符串
- `model` 和 `model_env` 可共存：`model` 是默认值，`model_env` 存在时覆盖
- `config.py::get_provider_config()` 的 `model_env` 解析逻辑已支持（line 118-127）

#### Step 3: `README.md` 更新

变更「环境变量」表格（line 89-99）：
```
| 变量 | 是否必须 | 说明 |
|------|----------|------|
| EMBED_BASE_URL | 是 | 嵌入 API 基础 URL（OpenAI-compatible） |
| EMBED_API_KEY | 是 | 嵌入 API 密钥 |
| EMBED_MODEL | 否 | 嵌入模型名称（可选，默认见 providers.yaml） |
| VOLC_EMBED_BASE_URL | 否 | 火山引擎多模态嵌入端点（备选方案） |
| VOLC_EMBED_API_KEY | 否 | 火山引擎 API 密钥 |
| VOLC_EMBED_MODEL | 否 | 火山引擎嵌入模型端点 ID |
```

变更「安装 > 环境依赖」表格（line 67-72）：
- "嵌入服务 API 密钥 | 火山引擎多模态嵌入" → "嵌入服务 API 密钥 | 支持 OpenAI-compatible 及火山引擎多模态"

在 README 的「配置」节增加一段说明：
```markdown
### 嵌入提供方切换

默认使用标准 OpenAI-compatible 嵌入 API。如需切换提供方：

1. **OpenAI**: 在 `.env` 中设置 `EMBED_BASE_URL` 和 `EMBED_API_KEY`
2. **火山引擎**: 在 `.env` 中设置 `VOLC_EMBED_*` 系列变量，然后修改 `configs/providers.yaml` 中 `roles.pdf_embedding` 和 `roles.wiki_embedding` 指向 `embedding_volcengine`
3. **本地模型**: 无需 API，`build_index.py` 会自动回退到 `bge-base`
```

同时更新 AGENTS.md Step 2 的 env 填写示例，反映新的变量名。

#### Step 4: 代码中消除硬编码 `provider="volcengine"`

共 4 处需要改：

**`scripts/build_index.py:_init_embedder()`** (line 144-166):
```python
# Before:
provider = get_provider_config("embedding_main", configs)
embedder.configure_cloud(
    provider="volcengine",     # ← 硬编码
    ...
)

# After:
provider_cfg = get_provider_config("embedding_main", configs)
provider_name = provider_cfg.get("provider", "openai")   # ← 从配置读取
embedder.configure_cloud(
    provider=provider_name,
    base_url=provider_cfg.get("base_url", ""),
    api_key=provider_cfg.get("api_key", ""),
    model=provider_cfg.get("model", ""),
    dimension=2048,
)
```

**`src/miniresearch/filters.py:vector_search()`** (line 265-270):
- 改为通过 `get_provider_config("embedding_main")` 读取，不再直接从 `os.environ` 取 `VOLC_EMBED_*`
- 前调 `load_project_env()` 确保 `.env` 已加载

**`src/miniresearch/mcp_server.py:_tool_search_wiki()`** (line 41-48):
- 同上，改为通过 `get_provider_config()` 读取

**`src/miniresearch/embedder.py:_embed_cloud()`** (line 169):
```python
# Before:
is_multimodal = "volces" in cfg.get("base_url", "") or "multimodal" in cfg.get("base_url", "")

# After:
is_multimodal = cfg.get("provider") == "volcengine"
```
`configure_cloud()` 中 `_cloud_config` 字典需保存 `provider` 字段。

#### Step 5: `config.py::get_provider_config()` 微调

`model` 和 `model_env` 共存逻辑：
```python
# 先取默认 model，再被 model_env 覆盖（如果 env 变量存在且非空）
model_value = provider.get("model", "")
if "model_env" in provider:
    env_name = provider.pop("model_env")
    env_value = os.environ.get(env_name, "")
    if env_value:
        model_value = env_value
provider["model"] = model_value
```

当前代码逻辑（line 118-127）在 `model_env` 存在时 `pop` 掉它，但如果 env 变量为空会丢失 `provider.get("model")` 的默认值。需要补这个兜底。

#### Step 6: 更新测试

- `tests/test_config.py` — 增加 `model_env` 覆盖默认 `model` 的测试用例
- `tests/test_env_utils.py` — 确认新变量名在测试 fixtures 中
- 全量回归 `python3 -m pytest tests/ -v`

### 1.4 不变更范围

- 不改变火山引擎多模态的特殊 payload 格式（`{"input": [{"type": "text", "text": "..."}]}`）——该逻辑由 `provider: volcengine` 驱动
- 不改变 `embedder.py` 的 `configure_cloud()` 签名——只是 `provider` 参数值从硬编码变成配置驱动
- 不删除对 `VOLC_EMBED_*` 环境变量的支持——作为备选 provider 保留

### 1.5 影响面

| 文件 | 变更类型 | 风险 |
|------|----------|------|
| `.env.example` | 重写 | 低 — 无代码依赖 |
| `configs/providers.yaml` | 新增字段 | 低 — 向后兼容 |
| `README.md` | 更新表格+新增段落 | 低 |
| `AGENTS.md` | 更新 env 示例 | 低 |
| `scripts/build_index.py` | 改 3 行 | 中 — 需回归测试 |
| `src/miniresearch/filters.py` | 重构 provider 读取 | 中 — 需回归测试 |
| `src/miniresearch/mcp_server.py` | 重构 provider 读取 | 中 — 需回归测试 |
| `src/miniresearch/embedder.py` | 改 1 行条件 | 低 |
| `src/miniresearch/config.py` | 补 model/model_env 兜底逻辑 | 低 |
| `tests/test_config.py` | 新增用例 | 低 |

预计总变更量：~80 行（含注释和文档），风险可控。

---

## Task 2: 项目结构评审

### 2.1 当前结构

```
src/miniresearch/          # 15 个模块，全扁平
├── __init__.py
├── filters.py             # 检索/搜索
├── router.py              # 路由
├── mcp_server.py          # MCP 服务
├── mcp_contracts.py       # MCP 契约
├── vector_store.py        # ChromaDB 封装
├── embedder.py            # 嵌入抽象
├── wiki_gen.py            # Wiki 生成
├── wiki_store.py          # Wiki 存储
├── env_utils.py           # 环境变量加载
├── config.py              # YAML 配置加载
├── models.py              # 数据类
├── index_manifest.py      # 增量索引
├── logging.py             # 日志
├── pdf_extract.py         # PDF 提取
└── zotero_sqlite.py       # Zotero SQLite
```

### 2.2 评估

**当前结构的优点**：
- 简单直接，`from miniresearch.xxx import ...` 路径短
- 15 个模块不算多，扁平结构仍然可管理
- 无需处理子包 `__init__.py` 的重导出

**当前结构的问题**：
1. **概念分层模糊** — 基础设施（`config`, `env_utils`, `logging`, `models`）、数据适配（`pdf_extract`, `zotero_sqlite`）、向量层（`embedder`, `vector_store`, `index_manifest`）、检索层（`filters`, `router`）、Wiki 层（`wiki_gen`, `wiki_store`）、MCP 层（`mcp_server`, `mcp_contracts`）全部混在一起
2. **命名缺乏一致性** — `filters.py` 实际做检索而非过滤，`models.py` 是 dataclasses 而非 ORM
3. **未来扩展性** — 如果后续增加 RAG 层、更多 provider、前端，扁平结构会迅速膨胀
4. **`miniresearch` 这个包名本身有误导性** — 听起来像一个自包含的检索库，但实际上包含了 embedding、wiki 生成、MCP 服务、PDF 提取、Zotero 适配等完整管线

### 2.3 推荐方案

**不推荐一次性大重构。推荐渐进式、低风险调整：**

#### Phase A (本次执行): 包名修正 + 最小文件重组

**A1. 包名 `miniresearch` → `paper_compass`**

原因：
- `miniresearch` 名不副实——项目已远超"mini research"
- Python 社区惯例：包名应反映项目名（PEP 423）
- 使 import 路径直观：`from paper_compass.filters import search_library`

变更：
- `src/miniresearch/` → `src/paper_compass/`
- `pyproject.toml` 中的 `pythonpath` 无需改动（仍然是 `src`）
- 所有 `from miniresearch.xxx` → `from paper_compass.xxx`
- tests/ 中的 import 同步更新

影响面：所有 `.py` 文件中的 `from miniresearch` import 行 + `__init__.py`

**A2. 从 15 个文件合并/重命名 3 个文件**

| 文件 | 变更 | 原因 |
|------|------|------|
| `filters.py` → `search.py` | 重命名 | `filters` 名不副实——实际是 search_library + search_passages + vector_search |
| `models.py` → `types.py` | 重命名 | 避免与 ML 模型混淆，明确是 dataclasses |
| `embedder.py` + `vector_store.py` | 保持 | 已清晰 |

**A3. 不引入子包**

15 个模块（重命名后仍是 15 个）扁平结构是合理的。不建议拆成 5-6 个子包，因为：
- 模块间相互引用频繁（如 `mcp_server.py` import `filters`, `router`, `embedder`, `vector_store`, `wiki_store`, `mcp_contracts`, `logging`）
- 拆子包会让 import 路径更长且需处理循环依赖
- 当前模块数量在 Python 项目的"舒适区"内

#### Phase B (可选，待用户决定): 子包拆分

如果用户认为有必要，可在 Phase A 之后进一步：

```
src/paper_compass/
├── core/           # 基础设施
│   ├── config.py
│   ├── env.py      # env_utils
│   ├── logging.py
│   └── types.py    # models → types
├── ingest/         # 数据适配
│   ├── pdf.py      # pdf_extract
│   └── zotero.py   # zotero_sqlite
├── vector/         # 嵌入/向量
│   ├── embedder.py
│   ├── store.py    # vector_store
│   └── manifest.py # index_manifest
├── search/         # 检索
│   ├── library.py  # filters → search_library
│   ├── passages.py # filters → search_passages
│   └── router.py
├── wiki/           # Wiki
│   ├── gen.py
│   └── store.py
└── mcp/            # MCP 服务
    ├── contracts.py
    └── server.py
```

这会更清晰但 import 路径变长（`from paper_compass.vector.embedder import Embedder`）。**不建议本次执行**，除非用户明确要求。

### 2.4 本次执行范围（Task 2）

仅执行 **Phase A**：
1. `src/miniresearch/` → `src/paper_compass/`
2. `filters.py` → `search.py`
3. `models.py` → `types.py`
4. 全量 import 路径更新
5. `tests/` 中 import 同步更新
6. `pyproject.toml`、`README.md`、`AGENTS.md`、技能文档中的路径引用更新
7. 全量测试回归

### 2.5 影响面

| 文件 | 变更类型 | 风险 |
|------|----------|------|
| `src/miniresearch/*` → `src/paper_compass/*` | 目录重命名 | 低 — git mv 保留历史 |
| ~20+ 个 `.py` 文件 | import 路径更新 | 中 — 需全量回归 |
| `filters.py` → `search.py` | 文件重命名 | 低 |
| `models.py` → `types.py` | 文件重命名 | 低 |
| `README.md` | 更新路径引用 | 低 |
| `AGENTS.md` | 更新路径引用 | 低 |
| `paper-compass-dev` 技能 | 更新模块映射表 | 低 |
| `pyproject.toml` | 无需改动 | 无 |

---

## 执行顺序

```
Task 1 (Embedding config refactor)
  Step 1: .env.example 重写
  Step 2: configs/providers.yaml 重构
  Step 3: config.py model/model_env 兜底
  Step 4: embedder.py is_multimodal → provider 驱动
  Step 5: build_index.py / filters.py / mcp_server.py 消除硬编码
  Step 6: 测试更新 + 全量回归
  Step 7: README.md + AGENTS.md 更新

Task 2 (Project structure)
  Step 1: git mv src/miniresearch src/paper_compass
  Step 2: git mv filters.py search.py, models.py types.py
  Step 3: 全量 import 路径替换
  Step 4: __init__.py 更新
  Step 5: 文档更新（README, AGENTS.md, 技能）
  Step 6: 全量测试回归
```

建议先执行 Task 1，通过测试后再执行 Task 2，避免两个变更叠加导致问题难以定位。

---

## 验证标准

- [ ] `.env.example` 默认示例为标准 OpenAI embed 格式
- [ ] `EMBED_BASE_URL` + `EMBED_API_KEY` 即可驱动默认嵌入流程
- [ ] `VOLC_EMBED_*` 变量仍作为备选方案可用
- [ ] `python scripts/build_index.py --full-rebuild` 正常运行
- [ ] `python eval/run_eval.py -v` 12/12 通过
- [ ] `python3 -m pytest tests/ -v` 全量通过
- [ ] `from paper_compass.search import search_library` 可正常 import
- [ ] `from paper_compass.types import WikiMatch` 可正常 import
- [ ] 无残留的 `from miniresearch` import
- [ ] Git history 保留（通过 `git mv`）
