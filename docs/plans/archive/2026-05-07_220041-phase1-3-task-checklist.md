# Phase 1–3 的逐任务执行清单

> **For Hermes:** Use subagent-driven-development skill to implement this plan task-by-task.

**Goal:** 把“最小化论文检索系统”的前 3 个阶段拆成真正可执行的逐任务清单。重点是快速形成最小闭环：仓库骨架 → Zotero 固定目录同步 → 最小 wiki 层。这里默认 PDF 根目录为 `D:\zotero_backup`（WSL: `/mnt/d/zotero_backup`）。

**Architecture:** 以最小闭环为原则，Phase 1 建仓库与配置，Phase 2 打通固定目录同步，Phase 3 建立最小 wiki 层。每个任务尽量小、可验证、可独立完成。

**Tech Stack:** Python 3.11+, YAML, markdown wiki, optional pandas, paper-qa later, pytest.

---

# Phase 1：最小仓库骨架与配置

### Task 1.1：创建项目根目录与基础文件

**Objective:** 建立最小仓库骨架。

**Files:**
- Create: `README.md`
- Create: `pyproject.toml`
- Create: `.gitignore`
- Create: `.env.example`

**Step 1: 写 README 初稿**
内容至少包括：
- 项目目标
- 一期范围
- 固定 PDF 根目录 `/mnt/d/zotero_backup`
- 主要组件：wiki / RAG / MCP

**Step 2: 写 pyproject.toml 初稿**
先只放最小依赖：
- pyyaml
- pydantic
- pytest
- paper-qa（后续 Phase 4 用，但现在可先声明）

**Step 3: 写 .gitignore**
忽略：
- `.env`
- `.venv/`
- `.pqa/`
- `data/logs/*`

**Step 4: 写 .env.example**
至少包含：
- `OPENAI_API_KEY=`
- `OPENAI_BASE_URL=`
- `ZOTERO_PDF_ROOT=/mnt/d/zotero_backup`
- `WIKI_PATH=./wiki`

**Step 5: 验证**
检查根目录文件齐全。

---

### Task 1.2：创建目录结构

**Objective:** 建立最小目录树。

**Files:**
- Create: `configs/`
- Create: `prompts/`
- Create: `docs/`
- Create: `data/zotero-export/`
- Create: `data/logs/`
- Create: `wiki/`
- Create: `scripts/`
- Create: `src/miniresearch/`
- Create: `tests/`

**Step 1:** 创建目录  
**Step 2:** 在必要空目录放 `.gitkeep`  
**Step 3:** 验证目录树与规划一致

---

### Task 1.3：建立配置文件骨架

**Objective:** 固定配置入口。

**Files:**
- Create: `configs/providers.yaml`
- Create: `configs/paths.yaml`
- Create: `configs/wiki.yaml`
- Create: `configs/rag.yaml`
- Create: `configs/mcp.yaml`

**Step 1: 写 providers.yaml**
至少包含一个 OpenAI-compatible provider。

**Step 2: 写 paths.yaml**
把 `/mnt/d/zotero_backup` 固定写入 `zotero_pdf_root`。

**Step 3: 写 wiki.yaml**
设置 `ingest_mode: curated`。

**Step 4: 写 rag.yaml**
设置 `paper_directory: /mnt/d/zotero_backup`。

**Step 5: 写 mcp.yaml**
列出最小 5 个工具。

**Step 6: 验证**
确保所有 YAML 文件能被解析。

---

### Task 1.4：建立 prompt 文件骨架

**Objective:** 固定 prompt 外置机制。

**Files:**
- Create: `prompts/wiki_ingest.md`
- Create: `prompts/wiki_query.md`
- Create: `prompts/router_classify.md`
- Create: `prompts/rag_answer.md`

**Step 1:** 为每个 prompt 写标题和用途说明  
**Step 2:** 留出可后续细化的模板骨架  
**Step 3:** 验证路径与配置可对应

---

### Task 1.5：建立配置加载模块

**Objective:** 让后续模块都能统一读取配置。

**Files:**
- Create: `src/miniresearch/config.py`
- Create: `tests/test_config.py`

**Step 1: 写 failing test**
测试能否读取 YAML 文件并返回路径配置。

**Step 2: 运行测试验证失败**
Run: `pytest tests/test_config.py -v`
Expected: FAIL

**Step 3: 写最小实现**
实现 `load_yaml_config()` 与 `load_all_configs()`。

**Step 4: 运行测试验证通过**
Run: `pytest tests/test_config.py -v`
Expected: PASS

---

# Phase 2：Zotero 固定目录同步层

### Task 2.1：实现 PDF 目录扫描

**Objective:** 从 `/mnt/d/zotero_backup` 递归发现 PDF。

**Files:**
- Create: `src/miniresearch/zotero.py`
- Create: `tests/test_zotero_sync.py`

**Step 1: 写 failing test**
测试给定样本目录时，能正确找出 PDF 文件。

**Step 2: 运行测试验证失败**
Run: `pytest tests/test_zotero_sync.py::test_scan_pdf_root -v`
Expected: FAIL

**Step 3: 写最小实现**
实现 `scan_pdf_root(pdf_root)`。

**Step 4: 再跑测试**
Expected: PASS

---

### Task 2.2：为扫描结果建立基础记录

**Objective:** 让每个 PDF 都有统一基础字段。

**Files:**
- Modify: `src/miniresearch/zotero.py`
- Modify: `tests/test_zotero_sync.py`

**基础字段：**
- pdf_path
- relative_path
- file_name
- file_size
- modified_at

**Step 1:** 写 failing test  
**Step 2:** 实现 `build_base_record()`  
**Step 3:** 跑测试通过

---

### Task 2.3：增加 sha256（可默认开启）

**Objective:** 为后续增量与稳定 doc_id 做准备。

**Files:**
- Modify: `src/miniresearch/zotero.py`
- Modify: `tests/test_zotero_sync.py`

**Step 1:** 写 failing test  
**Step 2:** 实现 `compute_sha256()`  
**Step 3:** 测试通过

---

### Task 2.4：支持加载外部 metadata 文件

**Objective:** 支持 CSV/JSON metadata 增强。

**Files:**
- Modify: `src/miniresearch/zotero.py`
- Modify: `tests/test_zotero_sync.py`

**Step 1:** 写 failing test，验证 metadata 文件可加载  
**Step 2:** 实现 `load_external_metadata()`  
**Step 3:** 测试通过

---

### Task 2.5：实现 metadata 合并

**Objective:** 把路径扫描结果与 metadata 合并。

**Files:**
- Modify: `src/miniresearch/zotero.py`
- Modify: `tests/test_zotero_sync.py`

**Step 1:** 写 failing test，验证按 relative_path 或 file_name 匹配  
**Step 2:** 实现 `merge_records()`  
**Step 3:** 测试通过

---

### Task 2.6：输出 manifest.csv

**Objective:** 生成 PaperQA 可消费的最小输入文件。

**Files:**
- Modify: `src/miniresearch/zotero.py`
- Create: `tests/test_manifest_output.py`

**Step 1:** 写 failing test  
**Step 2:** 实现 `write_manifest_csv()`  
**Step 3:** 测试通过

**验证字段：**
- file_location
- title
- doi

---

### Task 2.7：输出 library.json

**Objective:** 生成 richer metadata 文件。

**Files:**
- Modify: `src/miniresearch/zotero.py`
- Modify: `tests/test_zotero_sync.py`

**Step 1:** 写 failing test  
**Step 2:** 实现 `write_library_json()`  
**Step 3:** 测试通过

---

### Task 2.8：实现最小 CLI 入口

**Objective:** 让同步层可以直接从命令行运行。

**Files:**
- Create: `scripts/sync_zotero.py`
- Create: `tests/test_sync_script_args.py`

**Step 1:** 写 failing test 验证参数解析  
**Step 2:** 实现脚本参数：
- `--pdf-root`
- `--metadata`
- `--out-dir`

**Step 3:** 测试通过

---

### Task 2.9：增加同步摘要输出

**Objective:** 输出新增/缺失/警告统计。

**Files:**
- Modify: `src/miniresearch/zotero.py`
- Modify: `scripts/sync_zotero.py`

**输出建议：**
- total pdfs
- merged metadata count
- missing title count
- missing doi count
- duplicate warnings

**验证：**
- 运行脚本后能看到清晰 summary

---

# Phase 3：最小 Wiki 层

### Task 3.1：初始化 wiki 基础文件

**Objective:** 建立论文导向的最小 wiki。

**Files:**
- Create: `wiki/index.md`
- Create: `wiki/log.md`
- Create: `wiki/purpose.md`
- Create: `wiki/.wiki-schema.md`
- Create: `wiki/papers/`
- Create: `wiki/topics/`
- Create: `wiki/methods/`
- Create: `wiki/queries/`
- Create: `wiki/comparisons/`

**Step 1:** 创建文件与目录  
**Step 2:** 写最小模板内容  
**Step 3:** 验证结构完整

---

### Task 3.2：定义 wiki 页面 frontmatter 规范

**Objective:** 固定写回格式。

**Files:**
- Modify: `wiki/.wiki-schema.md`
- Create: `docs/wiki-frontmatter.md`

**建议字段：**
- title
- created
- updated
- type
- tags
- sources
- confidence

---

### Task 3.3：实现最小 wiki 查询模块

**Objective:** 支撑广度层检索。

**Files:**
- Create: `src/miniresearch/wiki_query.py`
- Create: `tests/test_wiki_query.py`

**Step 1:** 写 failing test，验证按关键词查页面  
**Step 2:** 实现 `search_wiki_pages()`  
**Step 3:** 测试通过

---

### Task 3.4：实现 wiki 摘要回答

**Objective:** 基于命中页面做简单广度回答。

**Files:**
- Modify: `src/miniresearch/wiki_query.py`
- Modify: `tests/test_wiki_query.py`

**Step 1:** 写 failing test  
**Step 2:** 实现 `answer_from_wiki()`  
**Step 3:** 测试通过

---

### Task 3.5：实现最小写回模块

**Objective:** 把高价值结果写入 queries 或 topics。

**Files:**
- Create: `src/miniresearch/wiki_ingest.py`
- Create: `tests/test_wiki_ingest.py`

**Step 1:** 写 failing test  
**Step 2:** 实现 `save_query_to_wiki()`  
**Step 3:** 测试通过

---

### Task 3.6：实现 index/log 更新

**Objective:** 每次写回后更新 wiki 导航。

**Files:**
- Modify: `src/miniresearch/wiki_ingest.py`
- Modify: `tests/test_wiki_ingest.py`

**Step 1:** 写 failing test  
**Step 2:** 实现更新 `index.md` / `log.md` 逻辑  
**Step 3:** 测试通过

---

### Task 3.7：建立最小 CLI 写回入口

**Objective:** 支持手工把结果写入 wiki。

**Files:**
- Create: `scripts/ingest_to_wiki.py`
- Create: `tests/test_ingest_script_args.py`

**Step 1:** 写 failing test  
**Step 2:** 实现 CLI 参数解析  
**Step 3:** 测试通过

---

# Phase 1–3 完成后的联合验证

### 验证 1：项目骨架正确
Run: 检查目录树与配置文件
Expected: 所有基础文件存在

### 验证 2：同步层可用
Run:
```bash
python scripts/sync_zotero.py --pdf-root /mnt/d/zotero_backup --out-dir ./data/zotero-export
```
Expected:
- 生成 `manifest.csv`
- 生成 `library.json`
- 打印 summary

### 验证 3：wiki 可初始化并可写回
Run:
- 手工放入一个测试 query 结果
- 通过 `ingest_to_wiki.py` 写入
Expected:
- 新页面创建成功
- `index.md` 更新
- `log.md` 更新

### 验证 4：广度层可检索
Run: 针对 wiki 页面做关键词搜索
Expected:
- 返回命中页面与摘要

---

# 建议的阶段收尾文档

当 Phase 1–3 完成后，应补充：
- `docs/phase1-3-retrospective.md`
- 记录遇到的 metadata 质量问题
- 记录 `/mnt/d/zotero_backup` 目录组织特点
- 记录哪些字段最常缺失

---

# 下一阶段入口

完成这三阶段后，下一步才适合进入：
- Phase 4：PaperQA 深检索
- Phase 5：Router
- Phase 6：MCP server

这能保证：在真正做多层问答和 agent 工具之前，固定目录同步与 wiki 广度层已经比较稳。  