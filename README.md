# paper-compass · 论文罗盘

<div align="center">

**将 Zotero 论文库转化为 AI Agent 可直接检索的双引擎知识库（RAG 原文检索 + LLM Wiki 知识编译）**

[![version](https://img.shields.io/badge/version-1.3.0-5a6e5c?style=flat-square&labelColor=3a3026&color=5a6e5c)](https://github.com/baoyu0xxx/paper-compass)
![license](https://img.shields.io/badge/license-MIT-7a96a6?style=flat-square&labelColor=3a3026)
[![python](https://img.shields.io/badge/Python-3.11+-E8D5B5?style=flat-square&labelColor=3a3026&color=E8D5B5)](https://www.python.org/)
![MCP](https://img.shields.io/badge/protocol-MCP_2024--11--05-8db580?style=flat-square&labelColor=3a3026&color=8db580)

</div>

---

> 📖 **English version**: [README.en.md](README.en.md)

## 概述

当前 AI Agent 在阅读学术文献时面临一个困境：直接读取全文会导致较大的 Token 消耗且检索效率不高；单篇论文的对话式问答往往需要反复传递大段原文，效果却未必理想。

已有方案中，RAG 检索擅长定位原文中的具体段落，llm-wiki（Karpathy 提出的"知识编译一次、持续维护"理念）则通过 LLM 将论文内容提炼为结构化的知识页面。但二者在 Agent 工作流中缺乏有效的结合——要么只做向量检索，要么只做知识编译，能找到的结合二者的项目又多缺少更好的agent支持。总体而言，缺少一个能快捷使用的、将二者互补的agent文献检索方案。

**paper-compass 的设计出发点正是填补这一空白**：将 Zotero 论文库转化为 AI Agent 可直接检索的知识库，通过 RAG 原文检索与 LLM wiki 知识编译两种方式互补，解决学术文献管理中的两个常见问题：

1. **正文内容不可检索** — 标题和关键词之外，PDF 中的研究设计、实证方法、核心发现无法被快速定位
2. **阅读笔记无法沉淀** — 读过的论文内容随时间模糊，再次需要时需重新翻阅全文

### 特点

- **Agent-first**：所有功能通过 MCP 工具暴露，AI Agent 可直接调用——无需打开 GUI、复制粘贴、离开对话窗口
- **双引擎检索**：RAG（原文定位，用于"那篇论文具体说了什么"）与 Wiki（知识编译，用于"这篇论文的方法和发现是什么"）互补
- **LLM Wiki 知识编译**：将论文内容"编译"为结构化的知识页面并持续维护，类似 llm-wiki 的"一次生成、多次复用"思路，避免每次对话都重复消耗 Token
- **继承与扩展**：PDF 提取、嵌入、向量存储等核心模块继承自开源实现，在此之上增加 MCP 集成、增量索引、中文学术适配等能力

### 典型场景

在 Agent 对话中直接问：

> "有哪些关于企业数字化转型研究的文献？主流的研究方法有哪些？常用的代理变量是什么？"

Agent 在论文库中定位相关段落，返回带来源和页码的引用。

## 核心能力

| 能力 | 说明 |
|------|------|
| 🔌 **MCP 工具集** | 6 个标准 MCP 工具：`search_wiki`、`search_library`、`search_passages`、`ask_research`、`get_paper_metadata`、`save_to_wiki`，遵循 MCP 2024-11-05 协议 |
| 📝 **LLM wiki 生成** | 自动为论文生成结构化知识页面（研究问题、核心发现、方法与数据、理论框架），两阶段分类器 + 可定制提示词 |
| 🔍 **双模式段落检索** | 语义向量（dense）和 BM25 关键词（sparse）并行，兼顾概念相似性与精确术语匹配 |
| 📊 **增量索引** | 基于指纹清单（manifest）的变更检测，新增或修改论文后只更新变化部分，无需全量重建 |
| 🇨🇳 **中文学术支持** | 中文分词感知的检索与评分，经济学预设 wiki 提示词，适配中文学术文献 |
| 🔄 **嵌入级联回退** | OpenAI-compatible (`EMBED_*`) → 火山引擎 (`VOLC_EMBED_*`) → 本地模型（默认 `bge-base`，可用 `LOCAL_EMBED_MODEL` 改为 `specter` / `minilm`） |

## 快速开始

### 方式一：通过 GitHub Release 安装（推荐）

当前推荐直接从 GitHub Release 安装已发布的 wheel：

```bash
python3 -m pip install \
  https://github.com/baoyu0xxx/paper-compass/releases/download/v1.3.0/paper_compass-1.3.0-py3-none-any.whl

# 交互式配置
paper-compass init

# 验证配置与 API 连通性
paper-compass validate

# 增量同步 Zotero / 索引 / wiki 数据
paper-compass sync \
  --db-source-path /path/to/zotero.sqlite \
  --storage-path /path/to/storage
```

如果你更倾向于手工部署或开发环境安装，可使用下方“从源码安装（开发）”方式。

### 方式二：Agent 提示词部署

将以下提示词复制给你的 AI Agent，它将自动完成 paper-compass 的完整部署：

<details>
<summary>👋 复制这段提示词给你的 Agent</summary>

> 请帮忙在 `$HOME/projects/` 下部署 paper-compass（若目录不存在则创建）。执行以下步骤：
>
> 1. 克隆仓库：`git clone https://github.com/baoyu0xxx/paper-compass.git` 到 `$HOME/projects/paper-compass`
> 2. 安装依赖：`cd $HOME/projects/paper-compass && pip install -e .`
> 3. 运行 `paper-compass init`，使用你已知的 LLM 和 Embedding API 配置信息进行交互式配置
> 4. 运行 `paper-compass validate` 验证连通性
> 5. 将你的 Zotero SQLite 数据库路径导出到 `ZOTERO_SQLITE_PATH` 环境变量，然后运行 `python scripts/sync_zotero.py --extract-text`
> 6. 运行 `python scripts/build_index.py --library data/zotero-export/library.json --full-rebuild`
> 7. （可选）运行 `python scripts/ingest_to_wiki.py --limit 3 --workers 1` 测试 wiki 生成
> 8. 运行 `python scripts/healthcheck.py --smoke` 验证所有子系统
> 9. 最后将 MCP 配置添加到当前对话框架的配置中（Hermes 推荐使用绝对脚本路径，并显式设置 `PYTHONPATH=$HOME/projects/paper-compass/src`）
>
> 每一步完成后确认结果再继续下一步。

</details>

根据 Agent 能力不同，也可以简化为一句话指令：

```text
请帮我克隆 https://github.com/baoyu0xxx/paper-compass.git，安装依赖后运行 paper-compass init 做交互式配置，完成后验证安装并同步我的 Zotero 论文库。
```

### 方式三：从源码安装（开发）

```bash
# 1. 克隆仓库
git clone https://github.com/baoyu0xxx/paper-compass.git
cd paper-compass
python3 -m pip install -e .

# 2. 配置环境变量 — 交互式（推荐）
paper-compass init

#    或手动编辑：
#    cp .env.example .env
#    编辑 .env — 填写 LLM 和嵌入服务的 API 密钥

# 3. 验证配置连通性
paper-compass validate

# 4. 准备数据
python scripts/sync_zotero.py --extract-text
# → 自动按以下顺序探索：显式 --db-path > ZOTERO_SQLITE_PATH > 默认 Zotero 目录 > 可选备份目录（如配置了 ZOTERO_BACKUP_ROOT）
# → data/zotero-export/library.json + data/texts/*.txt

自动发现只会选择 Zotero 官方数据库文件 `zotero.sqlite`。旧的 `zotero_readonly.sqlite` 不再自动发现，因为长期手动快照可能变成过期副本；如确需短期兼容，可通过 `--db-source-path` / `--db-path` 显式指定。当自动发现命中默认 Zotero profile 时，`--snapshot-db auto` 会在 `data/state/zotero-snapshots/` 下创建运行时 SQLite 快照，并读取该快照而不是直接读取 live Zotero profile。

#    若数据库与 storage/ 不在同一目录：
#    python scripts/sync_zotero.py --db-path /path/to/zotero.sqlite --storage-path /path/to/storage --extract-text

# 5. 日常数据增量更新（推荐）
paper-compass sync \
  --db-source-path /path/to/zotero.sqlite \
  --storage-path /path/to/storage
# → 顺序执行 Zotero 同步、论文增量索引、wiki 增量生成、wiki 索引
# → 自动写入 data/state/last_sync.json
# → 若检测到 vectordb 脏状态，会阻断并给出 rebuild 建议

# 6. 手动执行单个阶段（仅在需要细粒度控制时）
scripts/pc-index-full.sh
scripts/pc-index-incremental.sh
scripts/pc-wiki-build.sh --limit 3
scripts/pc-wiki-index.sh

# 7. wiki 长任务（可选，数百篇论文通常需数小时）
scripts/pc-wiki-ingest-bg.sh
# 查看日志：
tail -f data/logs/wiki_gen.log

# 8. 验证
paper-compass-healthcheck --smoke
python eval/run_eval.py -v
```

这些 `scripts/pc-*.sh` 都是薄包装：负责固定 repo root、补默认路径、减少长命令手输错误；
如果你更偏好直接调 Python 脚本，也仍然可以继续使用 `scripts/build_index.py` / `scripts/ingest_to_wiki.py`。

自 v1.3.0 起，安装态 `paper-compass-mcp` 与 `paper-compass-healthcheck` 入口已直接指向包内实现；历史打包用的 `scripts.*` 兼容层已移除，请使用当前 console script 或仓库内 `scripts/` 文件。

## 更新

注意区分三类“更新”：

- `python3 -m pip install <GitHub Release wheel URL>`：安装或切换到指定发布版本
- `paper-compass update`：更新 git clone 安装的仓库代码版本
- `paper-compass sync`：更新 Zotero / 文本 / 向量库 / wiki 数据

### Release 安装包升级（推荐）

如果你是通过 GitHub Release 安装的，建议直接指定目标 wheel URL：

```bash
python3 -m pip install --upgrade \
  https://github.com/baoyu0xxx/paper-compass/releases/download/v1.3.0/paper_compass-1.3.0-py3-none-any.whl
```

如需安装其他已发布版本，可将上面 URL 中的版本号替换为对应 release。发布版本列表可用：

```bash
gh release list --repo baoyu0xxx/paper-compass --limit 10
```

### 数据增量更新（推荐）

```bash
# 标准增量更新
paper-compass sync \
  --db-source-path /path/to/zotero.sqlite \
  --storage-path /path/to/storage

# 仅预览将执行哪些阶段
paper-compass sync --dry-run

# 若上次异常退出导致 vectordb 脏状态，可带备份重建 papers 索引
paper-compass sync \
  --rebuild papers \
  --backup-corrupted-db \
  --db-source-path /path/to/zotero.sqlite \
  --storage-path /path/to/storage
```

`paper-compass sync` 会：
- 在写入前检查 `data/vectordb/` 是否存在 journal / WAL / manifest 损坏等异常状态
- 顺序执行 `sync_zotero.py` → `build_index.py --incremental --prune-deleted` → `ingest_to_wiki.py --skip-existing` → `build_index.py --wiki`
- 写入 `data/state/last_sync.json` 记录最近一次运行状态
- 在检测到向量库损坏时停止写入，并给出 rebuild 建议

如果你只想手动执行某一个阶段，可使用仓库内 shell 包装：

```bash
# papers 全量索引
scripts/pc-index-full.sh

# papers 增量索引
scripts/pc-index-incremental.sh

# wiki 页面生成（前台）
scripts/pc-wiki-build.sh --limit 3

# wiki 页面生成（后台）
scripts/pc-wiki-ingest-bg.sh

# wiki 向量索引
scripts/pc-wiki-index.sh
```

这些 shell 只做阶段级 convenience wrapper，不负责重写底层参数逻辑；如需特殊参数，可直接继续在命令末尾追加传给底层脚本。

### 自动更新代码（仅适用于 git clone 安装）

```bash
# 检查是否有新版本可用
paper-compass update --check

# 更新到最新版本
paper-compass update

# 更新到指定版本
paper-compass update --version v1.3.0

# 模拟更新（查看变更但不执行）
paper-compass update --dry-run
```

`paper-compass update` 会自动：
- 拉取最新代码并切换到目标版本
- 重新安装 Python 依赖
- 检测断点变更（新增的必填环境变量、配置格式变化等）并给出提示
- 运行 `paper-compass validate` 验证配置连通性
- 运行测试冒烟检查

如果你不是通过 `git clone` 安装，而是通过 GitHub Release wheel 安装，`paper-compass update` 不适用；请改用对应 release URL 的 `pip install --upgrade`。

### 手动更新

如果无法使用自动更新，可手动操作：

```bash
git fetch origin --tags
git checkout v1.3.0         # 或 git pull origin main
pip install -e .
paper-compass validate        # 验证配置仍然可用
python3 -m pytest tests/ -x   # 确认测试通过
```

### 升级注意事项

<details>
<summary>跨版本升级注意事项（点击展开）</summary>

> ⚠️ **跨版本升级**（如 v1.1.x → v1.2.x）可能涉及配置格式变更和环境变量调整。
>
> - `.env` 文件不会被自动修改——它是 gitignored 的，升级不会覆盖私有配置
> - 升级后注意终端输出的 ⚠ 提示，检查是否需要添加新的环境变量
> - 如果升级后 `validate` 失败，运行 `paper-compass init --force` 重新生成 `.env`
> - 建议升级前备份：`cp .env .env.backup`

</details>

## 安装

前面的“快速开始”已经给出三种主路径：Release 安装、Agent 提示词部署、源码安装。这里集中列出安装要求与安装后的补充说明。

### 环境要求

| 要求 | 说明 |
|------|------|
| Python ≥ 3.11 | 使用 `python3 --version` 检查 |
| Zotero 论文库 | 可选 — 支持使用预提取的文本文件 |
| LLM API 密钥 | Wiki 生成需要 OpenAI 兼容端点（`LLM_BASE_URL` + `LLM_API_KEY`） |
| 嵌入服务 API 密钥 | 支持 OpenAI-compatible 及火山引擎多模态嵌入 |

### 安装后可用命令

```bash
paper-compass --help
paper-compass init
paper-compass search --help
paper-compass status
paper-compass validate
paper-compass-healthcheck --help
paper-compass-mcp --help
```

## 配置

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
| `LOCAL_EMBED_MODEL` | 否 | 本地 embedding fallback 模型：`bge-base`（默认）/ `specter` / `minilm` |
| `WIKI_PROMPT` | 否 | Wiki 提示词风格：`default`（通用学术）、`economics`（经济学预设）、或自定义路径 |


> \* 若配置了云端 embedding provider，则需提供对应的 API 信息；若未配置云端 provider，系统会回退到 `LOCAL_EMBED_MODEL`（默认 `bge-base`）。

#### $ENV_VAR 引用语法

API 密钥支持 `$ENV_VAR` 引用语法，无需在 `.env` 中存储明文密钥：

```env
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
  config: llm=openai | https://api.openai.com/v1 | gpt-4o
  config: embedding_role=embedding | source=shared | selected=embedding_main | active=embedding_main
  config: embedding_candidates=embedding_main -> embedding_volcengine -> local (bge-base)
  ✓ dotenv: OK
  ✓ llm: OK (model: gpt-4o, 1.2s, response: 15 chars)
  ✓ embed: OK (provider: embedding_main, model: text-embedding-3-small, dim=1536, 0.8s)
```

`paper-compass validate` 现在会显式打印解析后的 embedding 运行时信息：共享 role、当前选中的 cloud provider、候选链路，以及在没有任何云端 provider 时将回退到的本地模型。这样 CLI 展示与 `build_index.py` 的真实运行时语义保持一致。

### Wiki 提示词选择

`paper-compass init` 会在配置完 LLM 和嵌入服务后，引导选择 wiki 页面生成的提示词风格。

**三种模式：**

| 模式 | WIKI_PROMPT | 说明 |
|------|-------------|------|
| 默认（通用学术） | `default` | 适用于各学科的通用学术提示词（v1.2.1 新增） |
| 学科预设 | `economics` 等 | 针对特定学科优化的提示词（当前内置：经济学） |
| 自定义路径 | `/path/to/prompts` | 使用自己编写的提示词文件 |

切换提示词：编辑 `.env` 中的 `WIKI_PROMPT` 变量：

```env
WIKI_PROMPT=default       # 默认通用学术提示词
WIKI_PROMPT=economics     # 经济学学科提示词
WIKI_PROMPT=/home/user/my-prompts  # 自定义提示词
```

<details>
<summary>点击查看 wiki 生成架构与自定义提示词说明</summary>

**两阶段生成架构：** wiki 生成采用「分类 → 生成」两阶段架构：
1. **Pass 1（分类）**：LLM 将论文分类为 empirical / theoretical / review / descriptive
2. **Pass 2（生成）**：根据分类结果，组合 `wiki_overview.md` + `wiki_empirical.md`（实证论文）或仅 `wiki_overview.md`（非实证论文）

**贡献学科预设：** 欢迎通过 pull request 贡献其他学科的提示词。在 `prompts/disciplines/<学科名>/` 下创建 `wiki_overview.md` 和 `wiki_empirical.md` 即可。

**自定义提示词：** 确保自定义目录下包含 `wiki_overview.md`，可选 `wiki_empirical.md`。分类器 `wiki_router.md` 对所有模式统一使用 `prompts/` 下的版本。

如果某些 prompt 文件缺失，系统不会再默默漂移到隐式 fallback。当前运行时会把 prompt bundle 标记为 `degraded`，并在 `paper-compass status` 中显式展示缺失状态与 fallback 原因。

</details>

### 嵌入提供方切换与级联回退

嵌入服务支持**级联回退**机制：
1. **首选** `embedding_main`（OpenAI-compatible，`EMBED_BASE_URL` + `EMBED_API_KEY`）
2. **回退** `embedding_volcengine`（火山引擎多模态，`VOLC_EMBED_*` 系列变量）— [火山引擎快速入门指南](https://www.volcengine.com/docs/82379/1399008?lang=zh)
3. **最终回退** 本地模型（默认 `bge-base`，可通过 `LOCAL_EMBED_MODEL` 设为 `specter` 或 `minilm`）

`paper-compass validate` 在没有任何云端嵌入 provider 时，会显式报告将使用本地 fallback；实际构建索引时，`build_index.py` 也会按同一顺序执行。`paper-compass status` 也会展示相同的 embedding runtime 视图，包括 shared role、selected provider、active provider、候选链路与已解析的 provider registry，避免 CLI 展示与真实运行时漂移。

配置对应环境变量即可自动启用各级回退。如需固定使用某一提供方，可在 `configs/providers.yaml` 中把唯一的共享嵌入角色改到目标 provider，例如：

```yaml
roles:
  embedding: embedding_volcengine   # 论文与 wiki 共用同一个 embedding provider
```

默认配置已移除旧版拆分式 embedding 入口。论文索引与 wiki 索引必须处于同一 embedding 空间，因此配置层只使用一个共享的 `roles.embedding`。
### 高级配置

`config.py` 会优先从当前工作目录 / 仓库根目录的 `configs/` 读取配置，并在安装包场景下回退到 `src/paper_compass/configs/` 中的打包资源。也因此，仓库里会同时看到两套同名 YAML（例如两个 `mcp.yaml`）：

- `configs/`：开发态直跑脚本时使用
- `src/paper_compass/configs/`：打包安装后作为 package data 使用

这两套文件应保持完全一致；项目测试会对它们做同步校验，避免再次发生配置漂移。

LLM 模型、Chroma 集合命名、MCP 跟踪等配置位于 `configs/` 目录下，详见各文件内注释：

- `configs/providers.yaml`
- `configs/paths.yaml`
- `configs/mcp.yaml`
- `configs/wiki.yaml`

## 使用方法

### CLI 命令

安装后可通过 `paper-compass` 命令直接调用：

```bash
# 交互式配置 LLM 和嵌入服务
paper-compass init

# 本地检索统一入口（v1.3.0 发布前已用本地 417 条文献、406 个 wiki 页面实测）
paper-compass search wiki --query "家族企业代际传承" --limit 3
# → 返回“代际传承与家族企业多元化经营”“代际传承对家族企业风险承担的影响”等 wiki 页面

paper-compass search library --query "家族企业代际传承" --limit 5
# → 返回“家族企业代际传承与数字化转型”等本地 library.json 记录

paper-compass search passages --query "家族企业代际传承 劳动力结构" --search-mode hybrid --limit 3
# → 同时检索原文关键词/BM25 与语义向量片段

paper-compass search ask --query "家族企业代际传承对劳动力结构有什么影响" --force-mode hybrid --max-sources 3
# → 汇总 wiki、library 和 PDF evidence，输出带来源的检索结果

# 查看当前解析后的配置 / 数据 / 向量库状态
paper-compass status
# → 包括 embedding role / active provider / cascade，以及 wiki prompt bundle 是否 degraded

# 一键执行 Zotero / 向量库 / wiki 数据同步
paper-compass sync --db-source-path /path/to/zotero.sqlite --storage-path /path/to/storage

# 代码升级
paper-compass update

# 验证配置与 API 连通性
paper-compass validate
```

详细用法：

```bash
paper-compass init --help
paper-compass search --help
paper-compass status --help
paper-compass sync --help
paper-compass update --help
paper-compass validate --help
```

### CLI 脚本

| 脚本 | 用途 | 关键参数 |
|------|------|----------|
| `scripts/sync_zotero.py` | Zotero SQLite → library.json + 文本提取 | `--extract-text` |
| `scripts/build_index.py` | 构建 ChromaDB 向量索引（论文 + wiki） | `--full-rebuild`、`--incremental`、`--prune-deleted`、`--wiki` |
| `scripts/ingest_to_wiki.py` | 批量 LLM wiki 生成 | `--skip-existing`、`--workers 10`、`--limit N` |
| `scripts/run_mcp_server.py` | MCP 服务（stdio / 工具调用 / 交互模式） | `--mcp`、`--tool <name> --query "..."` |
| `scripts/healthcheck.py` | 子系统健康检查 | `--deps-only`、`--smoke`（含 API 连通性探测） |

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
mcp_servers:
  paper-compass:
    command: python3
    args: ["/path/to/paper-compass/scripts/run_mcp_server.py", "--mcp"]
    env:
      PYTHONPATH: "/path/to/paper-compass/src"
    connect_timeout: 60
    timeout: 120
```

`scripts/run_mcp_server.py` 现在会在启动时主动把仓库内 `src/` 加入 `sys.path`，以减少 editable install 与脚本直跑之间的差异；但在 MCP 客户端侧显式补 `PYTHONPATH`，通常仍然更稳。

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
paper-compass-mcp --tool search_wiki --query "家族企业代际传承"
paper-compass-mcp --tool search_library --query "作者姓名"
paper-compass-mcp --tool search_passages --query "具体段落内容" --search-mode keyword
paper-compass-mcp --tool search_passages --query "具体段落内容" --search-mode hybrid --db-path data/vectordb --text-dir data/texts --library-path data/zotero-export/library.json
paper-compass-mcp --tool ask_research --query "研究问题" --max-sources 7 --db-path data/vectordb
paper-compass-mcp --tool get_paper_metadata --id-or-doi ZOTERO_KEY

# 兼容原脚本入口
python scripts/run_mcp_server.py --tool search_passages --query "具体段落内容" --search-mode keyword
```

#### 与 NumPy 2.x 的兼容性

v1.2.5 修复了搜索路径里对已废弃别名 `np.NaN` 的引用，避免在 NumPy 2.x 环境下通过 MCP 调用搜索工具时出现：

```text
`np.NaN` was removed in the NumPy 2.0 release. Use `np.nan` instead.
```

如果你在 Agent / MCP 子进程里见到这类报错，升级到 v1.2.5+ 即可。

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
├── src/paper_compass/       # 核心库
│   ├── cli/                 # CLI 命令（init, sync, update, validate）
│   │   ├── __init__.py      # 主入口 paper-compass
│   │   ├── configure.py     # paper-compass init 配置命令
│   │   ├── sync_data.py     # paper-compass sync 数据同步命令
│   │   ├── update.py        # paper-compass update 代码升级命令
│   │   └── validate.py      # paper-compass validate 连通性验证
│   ├── search.py            # search_library、search_passages、向量搜索
│   ├── router.py            # ask_research 多层路由
│   ├── mcp_server.py        # MCP 工具处理与分发
│   ├── mcp_contracts.py     # 工具 schema 定义（唯一数据源）
│   ├── vector_store.py      # ChromaDB 封装 + BM25 混合搜索
│   ├── embedder.py          # 多提供方嵌入（级联回退）
│   ├── wiki_gen.py          # 两阶段 LLM wiki 生成 + 提示词解析
│   ├── wiki_store.py        # 线程安全的 wiki 写回
│   ├── env_utils.py         # .env 加载（始终覆盖过期值）
│   ├── config.py            # YAML 配置加载与 $ENV_VAR 解析
│   ├── types.py             # 响应数据类
│   ├── index_manifest.py    # 基于指纹的增量索引
│   ├── index_health.py      # vectordb 健康检查与损坏检测
│   ├── logging.py           # JSONL 跟踪日志
│   ├── pipeline_sync.py     # 一键数据同步流水线编排
│   ├── pdf_extract.py       # PyMuPDF + pdfplumber 文本提取
│   └── zotero_sqlite.py     # Zotero SQLite 读取
├── scripts/                # CLI 入口与独立脚本
├── configs/                # YAML 配置模板
├── prompts/                # Wiki 生成提示词
│   ├── wiki_overview.md    # 通用学术默认提示词（v1.2.1）
│   ├── wiki_empirical.md   # 通用学术默认提示词 - 实证设计（v1.2.1）
│   ├── wiki_router.md      # 论文类型分类器
│   ├── wiki_econ_overview.md   # [迁移存根] → disciplines/economics/
│   ├── wiki_econ_empirical.md  # [迁移存根] → disciplines/economics/
│   └── disciplines/        # 学科预设提示词
│       └── economics/      # 经济学专属提示词
├── eval/                   # 检索质量评估基准
├── wiki/                   # LLM 生成的知识库
├── data/                   # 生成数据（vectordb、texts、zotero-export）
├── tests/                  # pytest 测试套件
└── pyproject.toml          # 项目元数据与依赖
```

发布新版本前，请按 `docs/release-checklist.md` 检查代码、文档、测试、tag 与 release asset 是否一致。

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

## 参考与借鉴

paper-compass 基于以下开源项目构建：

- [RAG-Assistant-for-Zotero](https://github.com/aahepburn/RAG-Assistant-for-Zotero) — PDF 提取、Zotero 读取、嵌入、向量存储模块均适配自此项目
- [llm-wiki](https://github.com/karpathy/llm-wiki)（Andrej Karpathy） — wiki 知识"编译一次、持续维护"的方法论

在继承基础上新增的主要功能：
- MCP 协议集成（6 个标准工具，遵循 MCP 2024-11-05 协议）
- 增量索引（基于指纹的变更检测）
- 中文学术检索适配与学科预设提示词
- 多提供方嵌入级联回退
- CLI 配置命令（`init` + `validate`）
- 形式化评估基准（12 查询检索质量评估）

## 更新历史

| 版本 | 日期 | 内容 |
|------|------|------|
| v1.2.7 | 2026-05-15 | **数据同步命令 + vectordb 健康守卫** — 新增 `paper-compass sync`，将 `sync_zotero.py`、论文增量索引、wiki 增量生成与 wiki 向量化整合为一条命令；新增 `data/state/last_sync.json` 与 `data/state/sync.lock` 记录运行状态并阻止重叠执行；在写入前检测 Chroma journal/WAL/manifest/可读性，发现脏状态或损坏时阻断增量写入，并支持 `--rebuild {papers,wiki,all}` 与 `--backup-corrupted-db` 恢复路径。 |
| v1.2.6 | 2026-05-13 | **MCP cold-start 优化** — 消除 ChromaDB `clear_system_cache()` 导致的段文件二次加载；全局共享 `PersistentClient` 实例避免双 client 问题；MCP 握手后后台预加载 wiki 和 papers 集合。首次语义检索工具调用从 22-50s 降至 16-29s，MCP 模式下预加载后亚秒级响应。 |

## 兼容性说明

paper-compass 主要在 **Windows WSL（Ubuntu）** 环境中通过 Hermes Agent 进行了较为充分的测试，在 **macOS** 上进行过部分测试。当前应能在这两个平台上正常运行。**Windows 原生环境** 预计也可运行，但未经充分测试。

## 参与贡献

欢迎贡献。如有重大修改，请先提 issue 讨论，再提交 pull request。

## 鸣谢

- DeepSeek — 提供物美价廉的 Token
- Hermes Agent

## 许可证

MIT
