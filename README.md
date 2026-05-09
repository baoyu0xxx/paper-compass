# paper-compass

<div align="center">

**个人学术论文检索与知识导航基础设施**

[![Python](https://img.shields.io/badge/Python-3.11+-blue.svg)](https://www.python.org/)
[![License](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)
[![Version](https://img.shields.io/badge/version-1.0.1-blue.svg)](https://github.com/baoyu0xxx/paper-compass)

</div>

---

> 📖 **English version**: [README.en.md](README.en.md)

## 项目简介

paper-compass 将你的 Zotero 论文库转变为 AI Agent **可查询的知识基础设施**。它连接了"Zotero 里有几百篇论文"和"AI Agent 能用自然语言查找相关段落和证据"之间的空白。

**工作流**: Zotero PDF → LLM 自动生成结构化知识页面（wiki）→ 向量嵌入 → 6 个 MCP 工具供 AI 集成。

paper-compass 特别针对中国学术研究者的需求进行了优化：支持中文学术文献的检索（含中文分词匹配），提供实证经济学方向的领域化 wiki 生成提示词，并适配了火山引擎等多模态嵌入服务。

## 核心能力

- **6 个 MCP 工具** — `search_wiki`、`search_library`、`search_passages`、`ask_research`、`get_paper_metadata`、`save_to_wiki` — 遵循 MCP 协议标准（`2024-11-05`），具备完整的 `initialize` 握手
- **LLM 驱动的 wiki 生成** — 从 PDF 中自动生成结构化知识页面，采用两阶段分类器 + 实证经济学专用提示词
- **双模式段落检索** — 语义向量 + BM25 关键词全文搜索，覆盖原始论文分块
- **增量索引** — 基于指纹清单的变更检测，避免对未修改论文重复嵌入
- **中文检索优化** — 支持中文分词匹配，改善中文学术文献的召回效果
- **多提供方嵌入** — 火山引擎（2048 维多模态）、OpenAI 兼容端点、或本地 SentenceTransformers

## 快速开始

```bash
# 1. 克隆仓库
git clone https://github.com/baoyu0xxx/paper-compass.git
cd paper-compass
pip install -e .

# 2. 配置环境变量
cp .env.example .env
# 编辑 .env — 填写 LLM 和火山引擎嵌入的 API 密钥

# 3. 准备数据
python scripts/sync_zotero.py --extract-text
# → data/zotero-export/library.json + data/texts/*.txt

# 4. 构建检索索引
python scripts/build_index.py --library data/zotero-export/library.json --full-rebuild

# 5. 生成 wiki 页面（可选，约 400 篇论文需 5 小时）
nohup python scripts/ingest_to_wiki.py --skip-existing > data/logs/wiki_gen.log 2>&1 &
# 完成后：
python scripts/build_index.py --wiki

# 6. 验证
python scripts/healthcheck.py --smoke
python eval/run_eval.py -v
```

## 安装

### 环境依赖

| 要求 | 说明 |
|------|------|
| Python ≥ 3.11 | 使用 `python3 --version` 检查 |
| Zotero 论文库 | 可选 — 支持使用预提取的文本文件 |
| LLM API 密钥 | Wiki 生成需要 OpenAI 兼容端点（`LLM_BASE_URL` + `LLM_API_KEY`） |
| 嵌入服务 API 密钥 | 火山引擎多模态嵌入（`VOLC_EMBED_*` 系列变量），或本地模型 |

### 从源码安装

```bash
git clone https://github.com/baoyu0xxx/paper-compass.git
cd paper-compass
pip install -e .           # 核心依赖
pip install -e ".[dev]"    # 含 pytest，用于测试
pip install -e ".[paperqa]" # 含 PaperQA5 集成（可选）
```

## 配置

### 环境变量

将 `.env.example` 复制为 `.env` 并填写：

| 变量 | 是否必须 | 说明 |
|------|----------|------|
| `LLM_BASE_URL` | 是 | LLM API 基础 URL |
| `LLM_API_KEY` | 是 | LLM API 密钥 |
| `VOLC_EMBED_BASE_URL` | 是 | 火山引擎多模态嵌入端点 |
| `VOLC_EMBED_API_KEY` | 是 | 火山引擎 API 密钥 |
| `VOLC_EMBED_MODEL` | 是 | 嵌入模型端点 ID（如 `ep-20260420154519-xxxxx`） |
| `PAPERQA_BASE_URL` | 可选 | PaperQA5 全文 RAG 端点 |
| `PAPERQA_API_KEY` | 可选 | PaperQA5 API 密钥 |
| `PAPERQA_MODEL` | 可选 | PaperQA5 模型名称 |

### 提供方配置

LLM 模型、chroma 集合命名、MCP 跟踪等高级配置位于 `configs/` 目录下：

- `configs/providers.yaml` — LLM 和嵌入提供方设置
- `configs/paths.yaml` — 存储路径
- `configs/mcp.yaml` — MCP 服务行为与日志

## 使用方法

### CLI 工具

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
├── src/miniresearch/       # 核心库（13 个模块）
│   ├── filters.py          # search_library、search_passages、向量搜索
│   ├── router.py           # ask_research 多层路由
│   ├── mcp_server.py       # MCP 工具处理与分发
│   ├── mcp_contracts.py    # 工具 schema 定义（唯一数据源）
│   ├── vector_store.py     # ChromaDB 封装 + BM25 混合搜索
│   ├── embedder.py         # 多提供方嵌入（火山引擎、本地模型）
│   ├── wiki_gen.py         # 两阶段 LLM wiki 生成
│   ├── wiki_store.py       # 线程安全的 wiki 写回
│   ├── env_utils.py        # .env 加载（始终覆盖过期值）
│   ├── config.py           # YAML 配置加载与 env 变量解析
│   ├── models.py           # 响应数据类
│   ├── index_manifest.py   # 基于指纹的增量索引
│   ├── logging.py          # JSONL 跟踪日志
│   ├── pdf_extract.py      # PyMuPDF + pdfplumber 文本提取
│   └── zotero_sqlite.py    # Zotero SQLite 读取
├── scripts/                # CLI 入口（5 个脚本）
├── configs/                # YAML 配置模板
├── eval/                   # 12 查询评估基准
├── wiki/                   # LLM 生成的知识库
├── data/                   # 生成数据（vectordb、texts、zotero-export）
├── tests/                  # pytest 测试套件
└── pyproject.toml          # 项目元数据与依赖
```

## 开发

### 运行测试

```bash
pip install -e ".[dev]"
python3 -m pytest tests/ -v         # 运行所有测试
python3 -m pytest tests/ -x         # 遇错即停
python3 -m pytest tests/test_incremental_index.py -v  # 增量索引测试
```

### 运行评估

```bash
python eval/run_eval.py             # 全部 12 个查询
python eval/run_eval.py -v          # 详细输出
python eval/run_eval.py --mode strict  # 严格键匹配模式
```

## 参考来源

paper-compass 从 [RAG-Assistant-for-Zotero](https://github.com/aahepburn/RAG-Assistant-for-Zotero) 中适配了经过验证的模块：

| 源模块 | 适配为 | 用途 |
|--------|--------|------|
| `backend/pdf.py` | `pdf_extract.py` | PyMuPDF 文本提取（pdfplumber 备用） |
| `backend/zotero_dbase.py` | `zotero_sqlite.py` | Zotero SQLite 读取与路径解析 |
| `backend/embed_utils.py` | `embedder.py` | 多提供方嵌入（本地 + 云端） |
| `backend/vector_db.py` | `vector_store.py` | ChromaDB 封装 + BM25 混合搜索 |

主要差异：paper-compass 增加了 LLM 驱动的 wiki 生成、MCP 协议集成、基于指纹的增量索引、中文分词感知搜索，以及形式化的评估基准。

## 参与贡献

欢迎贡献。如有重大修改，请先提 issue 讨论，再提交 pull request。

## 许可证

MIT
