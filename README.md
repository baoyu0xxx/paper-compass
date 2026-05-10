# paper-compass · 论文罗盘

<div align="center">

**将你的 Zotero 论文库变成 AI Agent 可直接检索的知识库**

[![version](https://img.shields.io/badge/version-1.2.4-5a6e5c?style=flat-square&labelColor=3a3026&color=5a6e5c)](https://github.com/baoyu0xxx/paper-compass)
![license](https://img.shields.io/badge/license-MIT-7a96a6?style=flat-square&labelColor=3a3026)
[![python](https://img.shields.io/badge/Python-3.11+-E8D5B5?style=flat-square&labelColor=3a3026&color=E8D5B5)](https://www.python.org/)
![MCP](https://img.shields.io/badge/protocol-MCP_2024--11--05-8db580?style=flat-square&labelColor=3a3026&color=8db580)

</div>

---

> 📖 **English version**: [README.en.md](README.en.md)

## 为什么选择 paper-compass

### 已有工具做不到的事情

学术研究者每天都在用 Zotero 管理论文，但两个核心痛点始终没有解决：

- **正文不可检索**——Zotero 可以搜标题、作者、关键词，但 PDF 正文里的研究问题、数据、方法、发现仍然散落在成百上千个文件中。写文献综述时找不到"我好像读过某篇论文说了某个观点"——只能靠记忆，或者一篇篇重新翻。
- **知识无法沉淀**——每篇论文读完后，理解和笔记留在脑子里。下次问同一个问题时，还得从原始 PDF 重新推导。

### paper-compass 的设计思路

paper-compass 将 RAG 原文检索与 LLM wiki 知识编译结合起来，通过 MCP 标准协议为 AI Agent 提供个人学术知识库访问能力。

三个设计原则：

- **Agent-first**：所有能力通过 6 个 MCP 工具暴露，你的 Hermes Agent 或 Claude Desktop 可以直接调用——不需要打开一个 GUI 应用、不需要复制粘贴、不需要离开你的 Agent 对话窗口。
- **双引擎**：RAG 引擎负责"我记不清那篇论文具体说了什么，帮我找原文"；Wiki 引擎负责"这篇论文的核心发现和方法是什么"——两套检索体系互补，而不是互斥。
- **继承最优**：PDF 提取、Zotero SQLite 读取、嵌入、向量存储 4 个核心模块继承自 RAG-Assistant-for-Zotero 的经过验证的实现；LLM wiki 方法论借鉴 Karpathy llm-wiki 的"编译一次、持续维护"理念。在这之上，paper-compass 增加了 MCP 协议集成、增量索引、中文分词检索、学科预设提示词、CLI 配置命令、形式化评估基准等独有的能力。

### 典型场景

你可以直接在 Agent 对话中问：

> "我之前收集过哪些关于家族企业代际传承对劳动力雇佣结构影响的文献？核心发现是什么？用了什么数据和识别策略？"

Agent 会在你的论文库中定位相关段落，返回带来源和页码的引用——而不是依赖互联网上不相关或质量不明的搜索结果。

**项目对中文学术研究做了专门优化**：中文分词感知的检索与评分、经济学学科预设的 wiki 生成提示词、以及对火山引擎多模态嵌入服务的适配，确保中文学术文献也能获得较好的检索效果。

## 核心能力

| 能力 | 说明 |
|------|------|
| 🔌 **6 个 MCP 工具** | `search_wiki`、`search_library`、`search_passages`、`ask_research`、`get_paper_metadata`、`save_to_wiki`——遵循 MCP 2024-11-05 协议，零配置接入 Hermes Agent 和 Claude Desktop |
| 📝 **LLM 知识页面生成** | 每篇论文自动生成结构化 wiki 页面（研究问题、核心发现、方法与数据、理论框架），两阶段分类器 + 可定制提示词（通用学术默认 / 经济学学科预设 / 自定义路径） |
| 🔍 **双模式段落检索** | 语义向量（dense）和 BM25 关键词（sparse）双路径并行，兼顾概念相似性和精确术语匹配 |
| 📊 **增量索引** | 基于指纹清单（manifest）的变更检测，新增或修改论文后只更新变化的部分，无需全量重建 |
| 🇨🇳 **中文学术检索增强** | 中文分词感知的检索与评分，经济学专属 wiki 提示词，改善中文学术文献的召回效果 |
| 🔄 **多提供方嵌入级联** | 火山引擎（2048 维多模态）、OpenAI 兼容端点、本地 bge-base 三级自动回退，任一层级故障或限流自动降级 |
| ⚙️ **CLI 配置命令** | `paper-compass init` 交互式配置 LLM 和嵌入服务，`paper-compass validate` 一键验证连通性，支持 `$ENV_VAR` 引用语法 |
| 🎯 **Wiki 提示词定制** | `WIKI_PROMPT` 环境变量一键切换：通用学术默认 (`default`)、经济学预设 (`economics`)、或自定义提示词路径——支持按学科定制 wiki 页面生成风格 |

## 快速开始

```bash
# 1. 克隆仓库
git clone https://github.com/baoyu0xxx/paper-compass.git
cd paper-compass
pip install -e .

# 2. 配置环境变量 — 交互式（推荐）
paper-compass init

#    或手动编辑：
#    cp .env.example .env
#    编辑 .env — 填写 LLM 和嵌入服务的 API 密钥

# 3. 验证配置连通性
paper-compass validate

# 4. 准备数据
python scripts/sync_zotero.py --extract-text
# → 自动按以下顺序探索：显式 --db-path > ZOTERO_SQLITE_PATH > 默认 Zotero 目录 > 备份目录
# → data/zotero-export/library.json + data/texts/*.txt

#    若数据库与 storage/ 不在同一目录：
#    python scripts/sync_zotero.py --db-path /path/to/zotero.sqlite --storage-path /path/to/storage --extract-text

# 5. 构建检索索引
python scripts/build_index.py --library data/zotero-export/library.json --full-rebuild

# 6. 生成 wiki 页面（可选，约 400 篇论文需 5 小时）
nohup python scripts/ingest_to_wiki.py --skip-existing > data/logs/wiki_gen.log 2>&1 &
# 完成后：
python scripts/build_index.py --wiki

# 7. 验证
python scripts/healthcheck.py --smoke
python eval/run_eval.py -v
```

## 更新

### 自动更新（推荐）

```bash
# 检查是否有新版本可用
paper-compass update --check

# 更新到最新版本
paper-compass update

# 更新到指定版本
paper-compass update --version v1.2.4

# 模拟更新（查看变更但不执行）
paper-compass update --dry-run
```

`paper-compass update` 会自动：
- 拉取最新代码并切换到目标版本
- 重新安装 Python 依赖
- 检测断点变更（新增的必填环境变量、配置格式变化等）并给出提示
- 运行 `paper-compass validate` 验证配置连通性
- 运行测试冒烟检查

### 手动更新

如果你无法使用自动更新（离线、git 不可用等），可以手动操作：

```bash
git fetch origin --tags
git checkout v1.2.4          # 或 git pull origin main
pip install -e .
paper-compass validate        # 验证配置仍然有效
python3 -m pytest tests/ -x   # 确保测试通过
```

### 升级注意事项

> ⚠️ **跨版本升级**（如 v1.1.x → v1.2.x）可能涉及配置格式变更和环境变量调整。
>
> - `.env` 文件不会被自动修改——它是 gitignored 的，升级不会覆盖你的私有配置
> - 升级后请注意终端输出的 ⚠ 提示，检查是否需要添加新的环境变量
> - 如果升级后 `validate` 失败，运行 `paper-compass init --force` 重新生成 `.env`
> - 建议升级前备份：`cp .env .env.backup`

### 版本锁定

生产环境建议锁定到特定 tag 以确保稳定性：

```bash
paper-compass update --version v1.2.4
```

锁定后 `paper-compass update` 不会自动升级。要恢复跟随最新版本：

```bash
git checkout main
paper-compass update
```

## 安装

### 环境依赖

| 要求 | 说明 |
|------|------|
| Python ≥ 3.11 | 使用 `python3 --version` 检查 |
| Zotero 论文库 | 可选 — 支持使用预提取的文本文件 |
| LLM API 密钥 | Wiki 生成需要 OpenAI 兼容端点（`LLM_BASE_URL` + `LLM_API_KEY`） |
| 嵌入服务 API 密钥 | 支持 OpenAI-compatible 及火山引擎多模态嵌入 |

### 从源码安装

```bash
git clone https://github.com/baoyu0xxx/paper-compass.git
cd paper-compass
pip install -e .           # 核心依赖
pip install -e ".[dev]"    # 含 pytest，用于测试
pip install -e ".[paperqa]" # 含 PaperQA5 集成（可选）
```

安装后即可使用 `paper-compass` CLI 命令（见下方 CLI 命令章节）。

## 配置

### 交互式配置（推荐）

```bash
paper-compass init
```

按提示逐步填写 LLM（Wiki 生成）和 Embedding 服务的 Base URL、API Key 和模型名称，最后选择 wiki 提示词风格。API Key 支持 `$ENV_VAR` 语法，可直接引用已有环境变量（如 `$OPENAI_API_KEY`）。

```bash
# 非交互式模式（用于脚本化部署）
paper-compass init \
  --llm-args base_url=https://api.openai.com/v1,model=gpt-4o \
  --embed-args api_style=volcengine,model=doubao-embedding-vision-250615 \
  --wiki-prompt economics

# 覆盖已有 .env
paper-compass init --force
```

### 环境变量

将 `.env.example` 复制为 `.env` 并填写，或使用 `paper-compass init` 自动生成：

| 变量 | 是否必须 | 说明 |
|------|----------|------|
| `LLM_BASE_URL` | 是 | LLM API 基础 URL |
| `LLM_API_KEY` | 是 | LLM API 密钥（支持 `$ENV_VAR` 引用） |
| `LLM_MODEL` | 否 | 模型名称（可选，默认见 `providers.yaml`） |
| `EMBED_BASE_URL` | 是* | 嵌入 API 基础 URL（OpenAI-compatible） |
| `EMBED_API_KEY` | 是* | 嵌入 API 密钥 |
| `EMBED_MODEL` | 否 | 嵌入模型名称（可选，默认见 `providers.yaml`） |
| `VOLC_EMBED_BASE_URL` | 否 | 火山引擎多模态嵌入端点（备选方案） |
| `VOLC_EMBED_API_KEY` | 否 | 火山引擎 API 密钥 |
| `VOLC_EMBED_MODEL` | 否 | 火山引擎嵌入模型端点 ID |
| `WIKI_PROMPT` | 否 | Wiki 提示词风格：`default`（通用学术）、`economics`（经济学预设）、或自定义路径 |
| `PAPERQA_BASE_URL` | 可选 | PaperQA5 全文 RAG 端点 |
| `PAPERQA_API_KEY` | 可选 | PaperQA5 API 密钥 |
| `PAPERQA_MODEL` | 可选 | PaperQA5 模型名称 |

> \* EMBED 和 VOLC_EMBED 至少配置一组。

### $ENV_VAR 引用语法

API 密钥支持 `$ENV_VAR` 引用语法，无需在 `.env` 中存储明文密钥：

```env
# 直接用已有环境变量
LLM_API_KEY=$OPENAI_API_KEY
EMBED_API_KEY=$MY_EMBED_KEY
VOLC_EMBED_API_KEY=$VOLC_API_KEY
```

运行时由 `config.py` 的 `_resolve_env_value()` 自动解析。如引用的环境变量未设置，则保留 `$VAR` 原文。

### 验证配置连通性

```bash
paper-compass validate
```

输出示例：
```
  ✓ dotenv: OK
  ✓ llm: OK (model: gpt-4o, 1.2s, response: 15 chars)
  ✓ embed: OK (model: text-embedding-3-small, dim=1536, 0.8s)
```

### Wiki 提示词选择

`paper-compass init` 会在配置完 LLM 和嵌入服务后，引导你选择 wiki 页面生成的提示词风格。

**三种模式：**

| 模式 | WIKI_PROMPT | 说明 |
|------|-------------|------|
| 默认（通用学术） | `default` | 适用于各学科的通用学术提示词（v1.2.1 新增） |
| 学科预设 | `economics` 等 | 针对特定学科优化的提示词（当前内置：经济学） |
| 自定义路径 | `/path/to/prompts` | 使用自己编写的提示词文件 |

**切换提示词：** 编辑 `.env` 中的 `WIKI_PROMPT` 变量即可：

```env
# 使用默认通用学术提示词（适用于各学科）
WIKI_PROMPT=default

# 使用经济学学科提示词
WIKI_PROMPT=economics

# 使用自定义提示词
WIKI_PROMPT=/home/user/my-prompts
```

**两阶段生成架构：** wiki 生成采用「分类 → 生成」两阶段架构：
1. **Pass 1（分类）**：LLM 将论文分类为 empirical / theoretical / review / descriptive
2. **Pass 2（生成）**：根据分类结果，组合 `wiki_overview.md` + `wiki_empirical.md`（实证论文）或仅 `wiki_overview.md`（非实证论文）

**贡献学科预设：** 欢迎通过 pull request 贡献其他学科的提示词。在 `prompts/disciplines/<学科名>/` 下创建 `wiki_overview.md` 和 `wiki_empirical.md` 即可。提示词设计可参考经济学预设的两阶段分类 + 定性评估方案。

**设计自定义提示词：** 如需完全自定义提示词逻辑（包括分类器），建议使用 AI Agent 辅助设计。确保自定义目录下包含 `wiki_overview.md`，可选 `wiki_empirical.md`。分类器 `wiki_router.md` 对所有模式统一使用 `prompts/` 下的版本。

### 嵌入提供方切换与级联回退

嵌入服务支持 **级联回退** 机制：
1. **首选** `embedding_main`（OpenAI-compatible，`EMBED_BASE_URL` + `EMBED_API_KEY`）
2. **回退** `embedding_volcengine`（火山引擎多模态，`VOLC_EMBED_*` 系列变量）
3. **最终回退** 本地 `bge-base` 模型（无需 API）

只需配置对应环境变量即可自动启用各级回退，无需修改 YAML 配置。

如需固定使用某一提供方，在 `configs/providers.yaml` 中修改 `roles.pdf_embedding` 和 `roles.wiki_embedding` 指向目标提供方：

```yaml
roles:
  pdf_embedding: embedding_volcengine   # 固定使用火山引擎
  wiki_embedding: embedding_volcengine
```

### 提供方配置

LLM 模型、Chroma 集合命名、MCP 跟踪等高级配置位于 `configs/` 目录下：

- `configs/providers.yaml` — LLM 和嵌入提供方设置
- `configs/paths.yaml` — 存储路径
- `configs/mcp.yaml` — MCP 服务行为与日志
- `configs/wiki.yaml` — Wiki 生成参数

## 使用方法

### CLI 命令

安装后可通过 `paper-compass` 命令直接调用：

```bash
# 交互式配置 LLM 和嵌入服务
paper-compass init

# 验证配置与 API 连通性
paper-compass validate
```

详细用法：

```bash
paper-compass init --help
paper-compass validate --help
```

### CLI 脚本

| 脚本 | 用途 | 关键参数 |
|------|------|----------|
| `scripts/sync_zotero.py` | Zotero SQLite → library.json + 文本提取 | `--extract-text` |
| `scripts/build_index.py` | 构建 ChromaDB 向量索引（论文 + wiki） | `--full-rebuild`、`--incremental`、`--prune-deleted`、`--wiki` |
| `scripts/ingest_to_wiki.py` | 批量 LLM wiki 生成 | `--skip-existing`、`--workers 10`、`--limit N` |
| `scripts/run_mcp_server.py` | MCP 服务（stdio / 工具调用 / 交互模式） | `--mcp`、`--tool <name> --query "..."` |
| `scripts/healthcheck.py` | 子系统健康检查 | `--smoke`（含 API 连通性探测） |

#### 构建索引

```bash
# 全量重建（清空并重新嵌入所有论文）
python scripts/build_index.py --library data/zotero-export/library.json --full-rebuild

# 增量更新（仅更新有变化的论文）
python scripts/build_index.py --library data/zotero-export/library.json --incremental

# 索引 wiki 页面
python scripts/build_index.py --wiki --wiki-root ./wiki
```

#### 生成 Wiki 页面

```bash
# 处理所有未生成的页面（10 个并发 worker）
python scripts/ingest_to_wiki.py --skip-existing --workers 10

# 先试 3 篇
python scripts/ingest_to_wiki.py --limit 3 --workers 1

# 中断后继续运行
python scripts/ingest_to_wiki.py --skip-existing --workers 10
```

### MCP 集成

#### 配置 Hermes Agent

在 `config.yaml` 中添加：

```yaml
mcp:
  servers:
    paper-compass:
      command: python3
      args: ["scripts/run_mcp_server.py", "--mcp"]
      cwd: "/path/to/paper-compass"
```

#### 配置 Claude Desktop

```json
{
  "mcpServers": {
    "paper-compass": {
      "command": "python3",
      "args": ["scripts/run_mcp_server.py", "--mcp"],
      "cwd": "/path/to/paper-compass"
    }
  }
}
```

#### CLI 工具模式

```bash
python scripts/run_mcp_server.py --tool search_wiki --query "家族企业代际传承"
python scripts/run_mcp_server.py --tool search_library --query "作者姓名"
python scripts/run_mcp_server.py --tool search_passages --query "具体段落内容"
python scripts/run_mcp_server.py --tool ask_research --query "研究问题"
python scripts/run_mcp_server.py --tool get_paper_metadata --key ZOTERO_KEY
```

## 架构

### 流水线

```
Zotero SQLite + PDF
  → sync_zotero.py → library.json + data/texts/*.txt
  → build_index.py → ChromaDB 向量集合（论文 + wiki）
  → ingest_to_wiki.py → LLM → wiki/papers/*.md
  → build_index.py --wiki → ChromaDB wiki 集合
  → run_mcp_server.py → 6 个 MCP 工具暴露给 AI Agent
```

### MCP 工具

| 工具 | 描述 | 检索模式 |
|------|------|----------|
| `search_wiki` | 在 LLM 生成的 wiki 知识页面中进行语义搜索 | 向量 |
| `search_library` | 关键词 + 中文分词 + 模糊匹配，搜索论文元数据 | 文本 |
| `search_passages` | 双模式搜索原始论文文本块 | 向量 + BM25 |
| `ask_research` | 多层路由：wiki → 传递到 PDF 证据 | 混合 |
| `get_paper_metadata` | 按 key、DOI 或标题查找单篇论文 | 精确 |
| `save_to_wiki` | 将 LLM 生成的内容写回 wiki | — |

### 项目结构

```
paper-compass/
├── src/paper_compass/       # 核心库（15 个模块）
│   ├── cli/                 # CLI 命令（init, validate）
│   │   ├── __init__.py      # 主入口 paper-compass
│   │   ├── arg_utils.py     # key=value 参数解析（源自 lm-eval-harness）
│   │   ├── configure.py     # paper-compass init 配置命令
│   │   └── validate.py      # paper-compass validate 连通性验证
│   ├── search.py            # search_library、search_passages、向量搜索
│   ├── router.py            # ask_research 多层路由
│   ├── mcp_server.py        # MCP 工具处理与分发
│   ├── mcp_contracts.py     # 工具 schema 定义（唯一数据源）
│   ├── vector_store.py      # ChromaDB 封装 + BM25 混合搜索
│   ├── embedder.py          # 多提供方嵌入（OpenAI、火山引擎、本地模型，级联回退）
│   ├── wiki_gen.py          # 两阶段 LLM wiki 生成 + 提示词解析
│   ├── wiki_store.py        # 线程安全的 wiki 写回
│   ├── env_utils.py         # .env 加载（始终覆盖过期值）
│   ├── config.py            # YAML 配置加载与 $ENV_VAR 解析
│   ├── types.py             # 响应数据类
│   ├── index_manifest.py    # 基于指纹的增量索引
│   ├── logging.py           # JSONL 跟踪日志
│   ├── pdf_extract.py       # PyMuPDF + pdfplumber 文本提取
│   └── zotero_sqlite.py     # Zotero SQLite 读取
├── scripts/                # CLI 入口（5 个脚本）
├── configs/                # YAML 配置模板
├── prompts/                # Wiki 生成提示词
│   ├── wiki_overview.md    # 通用学术默认提示词（v1.2.1）
│   ├── wiki_empirical.md   # 通用学术默认提示词 - 实证设计（v1.2.1）
│   ├── wiki_router.md      # 论文类型分类器
│   ├── wiki_econ_overview.md   # [迁移存根] → disciplines/economics/
│   ├── wiki_econ_empirical.md  # [迁移存根] → disciplines/economics/
│   └── disciplines/        # 学科预设提示词
│       └── economics/      # 经济学专属提示词
├── eval/                   # 12 查询评估基准
├── wiki/                   # LLM 生成的知识库
├── data/                   # 生成数据（vectordb、texts、zotero-export）
├── tests/                  # pytest 测试套件（159 个测试，全部通过）
└── pyproject.toml          # 项目元数据与依赖
```

## 开发与调试

<details>
<summary>点击展开测试与评估命令</summary>

### 运行测试

```bash
pip install -e ".[dev]"
python3 -m pytest tests/ -v         # 运行所有测试
python3 -m pytest tests/ -x         # 遇错即停
```

### 运行评估

```bash
python eval/run_eval.py             # 全部 12 个查询
python eval/run_eval.py -v          # 详细输出
python eval/run_eval.py --mode strict  # 严格键匹配模式
```

</details>

## 继承与创新

paper-compass 不是一个从零开始的项目。它站在两个优秀开源项目的肩膀上：

### 继承自 [RAG-Assistant-for-Zotero](https://github.com/aahepburn/RAG-Assistant-for-Zotero)

以下 4 个核心模块适配自 RAG-Assistant-for-Zotero 的经过验证的实现：

| 源模块 | 适配为 | 用途 |
|--------|--------|------|
| `backend/pdf.py` | `pdf_extract.py` | PyMuPDF 文本提取（pdfplumber 备用） |
| `backend/zotero_dbase.py` | `zotero_sqlite.py` | Zotero SQLite 读取与路径解析 |
| `backend/embed_utils.py` | `embedder.py` | 多提供方嵌入（本地 + 云端） |
| `backend/vector_db.py` | `vector_store.py` | ChromaDB 封装 + BM25 混合搜索 |

### 借鉴自 [llm-wiki-skill](https://github.com/sdyckjq-lab/llm-wiki-skill)

LLM wiki 的知识"编译一次、持续维护"理念借鉴了 Karpathy llm-wiki 方法论。`save_to_wiki` MCP 工具的设计也参考了其"对话结晶化"思路——将有价值的 Agent 对话内容沉淀为知识库页面。

### paper-compass 独有的能力

在继承的基础上，paper-compass 增加了以下原创设计：

- **MCP 协议集成**：6 个标准 MCP 工具，遵循 MCP 2024-11-05 协议，可接入任意支持 MCP 的 Agent 框架
- **增量索引**：基于指纹清单（text_sha1 + chunking_version + embedding_model_id）的变更检测，比上游的"只检测新论文"更精确
- **中文学术检索**：中文分词感知的检索算法、经济学学科专属 wiki 提示词
- **CLI 配置命令**：`paper-compass init` + `validate`，采用 lm-eval-harness 的 `key=value` 参数风格
- **Wiki 提示词定制系统**：`WIKI_PROMPT` 环境变量 + 学科预设目录，支持按学科定制 wiki 页面生成风格
- **多提供方嵌入级联**：三级自动回退（OpenAI → 火山引擎 → 本地 bge-base），无需修改代码
- **形式化评估基准**：12 查询检索质量评估，含 recall@K 评分和严格/宽松模式
- **$ENV_VAR 引用语法**：API 密钥支持引用已有环境变量，无需明文存储

## 参与贡献

欢迎贡献。如有重大修改，请先提 issue 讨论，再提交 pull request。

## 许可证

MIT
