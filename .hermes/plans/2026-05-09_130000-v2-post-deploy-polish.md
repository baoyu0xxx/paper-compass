# paper-compass v2.0.0 部署后优化与发布计划

> 日期：2026-05-09 | 模式：Plan | 仓库：baoyu0xxx/paper-compass

---

## 目标

基于 2.0 部署测试报告反馈，完成代码修正、README 重写、提交推送、最终可部署性验证。

---

## 当前上下文

### 仓库状态
- 仓库：`https://github.com/baoyu0xxx/paper-compass`（公开）
- 分支：`main`，HEAD 在 `145e9bb`（v2.0.0）
- 本地干净（仅有未跟踪文件 `docs/deployment-test-report-2026-05-09.md`）
- 66 个 pytest 测试全部通过

### 部署测试报告关键发现
| # | 问题 | 状态 |
|---|------|------|
| 1 | 本地 23 个 commit 未推送 → clone 得不到完整代码 | ✅ 已推送 |
| 2 | `build_index.py` 要求 PDF 文件必须可达，即使 `text_file` 已存在 | ❌ 待改进 |
| 3 | BM25 multiprocessing WSL 下报错 | ⚠️ 已优雅降级 |
| 4 | SKILL.md 与代码工具数不一致（搜索阶段） | ✅ 已一致 |
| 5 | eval 套件需要全量数据 | ℹ️ 预期行为 |

### 已确认无缺陷
- `env_utils.py`：`load_project_env()` 无条件覆盖 `os.environ`（正确实现）
- `vector_store.py`：`add_chunks()` 支持 `mode="add"` / `mode="upsert"` 双模式
- `.env.example`：已存在且内容完整，含所有必需变量

---

## 计划步骤

### Step 1：代码修正（部署测试报告 #2）

**文件**：`scripts/build_index.py`

**修改**：在 `_prepare_index_inputs()` 中增加 PDF 不可用时的 text_file 降级逻辑。

当前逻辑：
```python
pdf_path = item.get("pdf_path", "")
if not pdf_path or not Path(pdf_path).exists():
    skipped.append(f"{key}: missing PDF")
    continue
```

目标逻辑：
```python
# 1. 优先使用 PDF（可用于提取文本）
# 2. PDF 不可达但 text_file 存在 → 降级为纯文本模式（传 None 作为 pdf_path）
# 3. 两者均不可达 → 跳过
```

同时检查 chunking 路径 (`_iter_chunks`) 是否支持 `pdf_path=None`（当已使用 text_file 时不应再进行 PDF 切分）。

### Step 2：README.md 重写

**参考项目**：
- `RAG-Assistant-for-Zotero` — 结构清晰，分区明确，安装/配置/使用/技术细节分离
- `paper-qa` — 学术项目标杆，API 文档风格
- MCP server 项目典型结构 — 聚焦集成说明

**新 README 结构**：

```
# paper-compass
> Personal academic paper retrieval & knowledge navigation infrastructure

[badges: version, python, license, tests]

## What is paper-compass?
（一段话概述：Zotero → wiki → vector → MCP 的完整链路）

## Key Features
- 6 MCP tools for AI agent integration
- LLM-powered wiki page generation
- Semantic + keyword dual search
- Incremental indexing support
- Chinese bigram-aware retrieval
- 66 tests, healthcheck, eval benchmark

## Quick Start（5 分钟体验）
（精简 6 步：clone → install → config → data → build → verify）
附终端录制或代码块演示

## Installation
### Prerequisites
- Python ≥ 3.11
- Zotero library (optional — can use pre-extracted texts)
- API keys for LLM + Embedding providers

### pip install
### From source

## Configuration
### Environment Variables（表格形式，含类型和是否必需）
### Provider Setup（LLM / Embedding / PaperQA）

## Usage
### CLI Tools（各脚本用途 + 常用命令）
### MCP Integration
  - Hermes Agent config.yaml 示例
  - Claude Desktop 配置示例
### Evaluation（eval/run_eval.py）

## Architecture
### Pipeline Overview（ASCII 流程图）
### MCP Tools 详解（表格）
### Project Structure（树形图）

## Development
### Running Tests
### Adding a New Embedding Provider
### Contributing

## Prior Art
（对 RAG-Assistant-for-Zotero 的致谢 + 差异说明）

## License
```

**写作风格**：
- 英语为主（面向 GitHub 公开仓库的国际受众），关键术语保留中文
- 每个代码块保证可复制粘贴运行
- 重点突出"对 Hermes/Claude Desktop 用户的 MCP 集成价值"

### Step 3：提交与推送

```bash
cd /mnt/d/pyproject/paper-compass
git add scripts/build_index.py README.md docs/
git commit -m "v2.0.0 post-deploy: PDF fallback + README overhaul"
git push origin main
```

注意：确保 `docs/deployment-test-report-2026-05-09.md` 也被加入（如用户希望公开测试报告）。

### Step 4：最终部署可行性测试

模拟全新用户视角：
1. 从 GitHub 克隆到独立临时目录
2. `pip install -e .` 验证依赖安装无报错
3. `cp .env.example .env` + 填入测试 API key
4. 准备最小测试数据集（3 篇文献的 library.json + 对应 text 文件）
5. 运行完整流水线：
   - `build_index.py --full-rebuild` → 验证向量索引
   - `ingest_to_wiki.py --limit 3 --workers 1` → 验证 wiki 生成
   - `build_index.py --wiki` → 验证 wiki 向量化
   - `healthcheck.py --smoke` → 验证 7 项检查
   - 4 个 MCP 工具逐个测试
6. `pytest tests/` → 66 测试全绿
7. 清理测试目录

### Step 5（按需）：检查是否遗漏

- [ ] README 中 `git clone` URL 是否指向正确仓库
- [ ] 是否有未被 `.gitignore` 覆盖的大文件（如 chroma.sqlite3）
- [ ] `pyproject.toml` 依赖是否完整（`pip install -e .` 不会失败）

---

## 涉及文件

| 文件 | 操作 | 说明 |
|------|------|------|
| `scripts/build_index.py` | 修改 | PDF 降级到 text_file 逻辑 |
| `README.md` | 重写 | 全面改版 |
| `docs/deployment-test-report-2026-05-09.md` | 不变 | 已存在，提交即可 |

---

## 验证标准

- [ ] `build_index.py` 在仅有 text_file 无 PDF 时不跳过文献
- [ ] README 结构完整、命令可复制、MCP 集成示例可工作
- [ ] `git push` 后 GitHub 页面显示新版 README
- [ ] 独立克隆后完整流水线跑通（3 篇文献）
- [ ] `pytest` 全绿（独立克隆环境下）

---

## 风险与待确认

- **Step 1 中文文本 chunking 降级**：需确认 `_iter_chunks` 在 pdf_path=None 时使用 text_file。若不支持则需要修改 chunking 路径，可能影响 chunk 质量（无 PDF 意味着无页面号信息）。
- **README 篇幅控制**：参考项目 README ~280 行，新版控制在 200-300 行，避免过长。
- **最终测试的 API 消耗**：需要 Mimo LLM（3 篇 wiki）× ~50s + 火山 embedding（2 次索引），约 3-5 分钟。
