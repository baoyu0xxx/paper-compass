# Zotero 同步层详细设计

> **For Hermes:** Use subagent-driven-development skill to implement this plan task-by-task.

**Goal:** 在“文献 PDF 都保存在 `D:\zotero_backup`（WSL: `/mnt/d/zotero_backup`）”的前提下，设计一个尽可能简单、稳定、可维护的 Zotero 同步层。该同步层不追求完整复制 Zotero 全能力，而只负责为 wiki 广度层和 PDF 深检索层提供统一、干净的中间数据。

**Architecture:** 一期将 Zotero 同步层收缩为“固定目录扫描 + 可选 metadata 关联 + 统一导出”的三步流程。换言之，不直接依赖复杂的 Zotero 内部表结构，不尝试复刻 Zotero 本体，只产出两个核心文件：`manifest.csv` 与 `library.json`。

**Tech Stack:** Python 3.11+, pathlib, csv/json, optional pandas, optional sqlite3（后续可扩展），固定 PDF 根目录 `/mnt/d/zotero_backup`。

---

## 1. 设计前提

用户已明确：当前文献都保存在固定目录 `D:\zotero_backup`，即 WSL 路径 `/mnt/d/zotero_backup`。

这意味着一期可以采用更简单的设计：
- 先把该目录当作权威 PDF 根目录；
- 先不把 Zotero 数据库直连设为前置条件；
- 先以“能稳定找到文献文件”为核心目标；
- metadata 采用“有则增强、无则降级”的策略。

这个前提显著降低了系统复杂度。

---

## 2. 同步层目标

同步层只需要完成四件事：

1. 扫描 `/mnt/d/zotero_backup` 下所有可用 PDF；
2. 为每个 PDF 生成一个基础记录；
3. 如果存在补充 metadata，则把 metadata 合并进记录；
4. 输出下游统一中间层文件：
   - `data/zotero-export/manifest.csv`
   - `data/zotero-export/library.json`

同步层不负责：
- 问答；
- wiki 写作；
- 向量索引；
- 复杂 Zotero GUI 交互；
- 修改 Zotero 本身数据。

---

## 3. 一期的三种输入层次

为保持简单，同时保留扩展性，建议同步层支持 3 级输入能力。

## 3.1 Level 1：仅固定目录扫描（必须支持）

**输入：** `/mnt/d/zotero_backup/**/*.pdf`

**输出内容：**
- 文件路径
- 文件名
- 相对路径
- 文件大小
- 修改时间
- 哈希值（可选，一期推荐加）

**适用：**
- 没有现成导出的 metadata 文件；
- 只想先让 RAG 跑起来；
- 先做样本验证。

## 3.2 Level 2：目录扫描 + 外部 metadata 文件（一期推荐）

**输入：**
- `/mnt/d/zotero_backup/**/*.pdf`
- 手工或 Zotero 导出的 metadata 文件（CSV / JSON / BibTeX 转换结果）

**输出增强：**
- title
- authors
- year
- doi
- journal
- tags
- collections

**适用：**
- 想保留较好的过滤能力；
- 不想一开始直连 sqlite。

## 3.3 Level 3：目录扫描 + Zotero sqlite 直读（二期可选）

**输入：**
- `/mnt/d/zotero_backup/**/*.pdf`
- Zotero 本地数据库 `zotero.sqlite`

**输出增强：**
- 更完整的 item metadata
- collection 结构
- tags
- attachment 关联

**适用：**
- 后续要做更自动化的 collection 级同步；
- 需要更高质量 metadata。

**建议：** 一期先不做。

---

## 4. 一期推荐方案

### 结论
一期推荐采用：

**固定目录扫描 + 可选 metadata 文件合并**

而不是直接读 `zotero.sqlite`。

### 原因
1. 实现更简单；
2. 更容易调试；
3. 不耦合 Zotero 内部表结构；
4. 便于未来迁移到别的文献目录组织方式；
5. 已足够支持最小版本的 wiki + PaperQA + MCP。

---

## 5. 输出数据结构设计

## 5.1 `manifest.csv`

这是给 PaperQA 等深检索层使用的最小文件。

### 必备字段
- `file_location`
- `title`
- `doi`

### 推荐字段
- `authors`
- `year`
- `journal`
- `collections`
- `tags`

### 示例
```csv
file_location,title,doi,authors,year,journal,collections,tags
subdir/a.pdf,Family Succession and Labor Adjustment,10.1234/abc,"Zhang;Li",2022,Journal of X,"family_firm;labor","did;china"
```

### 规则
- `file_location` 一律相对 `zotero_pdf_root`。
- 缺失字段允许为空，但不能破坏 CSV 结构。
- authors/tags/collections 建议统一用分号分隔。

## 5.2 `library.json`

这是给 wiki、router、MCP 使用的 richer schema。

### 每条记录建议字段
```json
{
  "doc_id": "sha1-or-stable-id",
  "title": "...",
  "pdf_path": "/mnt/d/zotero_backup/subdir/a.pdf",
  "relative_path": "subdir/a.pdf",
  "file_name": "a.pdf",
  "file_size": 1234567,
  "modified_at": "2026-05-01T12:00:00",
  "sha256": "...",
  "doi": "...",
  "authors": ["...", "..."],
  "year": 2022,
  "journal": "...",
  "collections": ["family_firm", "did"],
  "tags": ["china", "labor"],
  "metadata_source": "scan_only | external_csv | sqlite"
}
```

### 设计原则
- 即使无 title/doi，也至少保留文件级记录；
- `metadata_source` 用于后续判断记录质量；
- `doc_id` 应稳定，建议基于 `relative_path` 或 `sha256` 生成。

---

## 6. 同步流程设计

## Step 1：扫描 PDF 文件

**输入：** `/mnt/d/zotero_backup`

**逻辑：**
- 递归查找所有 `.pdf`
- 过滤大小为 0 或不可读文件
- 记录相对路径、文件大小、mtime
- 可选计算 sha256

**输出：** 文件记录列表

**注意：**
- 若目录很大，sha256 可做成可选模式；
- 一期默认建议开启 sha256，因为后续增量更新更稳。

## Step 2：加载可选 metadata 文件

**支持格式建议：**
- CSV
- JSON

**最低要求：**
- 能通过文件名、相对路径或 title 映射到 PDF

**优先匹配策略建议：**
1. relative_path 精确匹配
2. file_name 精确匹配
3. 规范化 file_name 匹配
4. title 模糊匹配（仅在必要时启用）

## Step 3：合并 metadata

**规则：**
- 扫描记录是基础；
- metadata 文件只做补充，不覆盖有效路径信息；
- 若 metadata 冲突，优先保留路径稳定性并输出 warning。

## Step 4：生成 `manifest.csv`

**逻辑：**
- 只保留 PaperQA 需要的字段；
- 对缺失 `title` 的记录，可降级用去扩展名文件名；
- 对缺失 `doi` 的记录，留空即可。

## Step 5：生成 `library.json`

**逻辑：**
- 保留全部 richer metadata；
- 标记 `metadata_source`；
- 便于后续 MCP 查询和 wiki 写回。

## Step 6：输出同步报告

建议额外输出一个简短 report：
- 总 PDF 数
- 成功记录数
- 无 metadata 数
- 重复文件名数
- 缺失 title 数
- 缺失 doi 数
- 失败路径数

这个报告可以打印到终端，也可以写日志。

---

## 7. 匹配与清洗策略

## 7.1 文件名规范化

建议对文件名做以下规范化用于匹配：
- 小写
- 去扩展名
- 连字符/下划线/空格统一化
- 连续空格折叠

## 7.2 title 兜底策略

若 metadata 缺 title：
- 使用文件名去扩展名作为临时 title；
- 但需在 `library.json` 中标记低质量来源。

## 7.3 authors 清洗
- 若输入是字符串，统一切分为数组；
- 内部存储用数组；
- 写 `manifest.csv` 时用 `;` 连接。

## 7.4 collections 与 tags
- 内部统一用数组；
- 输出 csv 时用 `;` 分隔；
- 空值统一为 `[]` 或空字符串，不混用奇怪占位符。

---

## 8. 增量更新建议

尽管一期要简单，但仍建议设计基本增量机制。

### 建议依据
- `relative_path`
- `modified_at`
- `file_size`
- `sha256`

### 最小策略
- 若文件路径不存在于上次输出中，则视为新增；
- 若路径存在但 mtime 或 size 变化，则视为更新；
- 若记录不再存在，则视为删除。

### 一期建议
- 先不做复杂 diff 数据库；
- 每次重写完整 `manifest.csv` 与 `library.json` 即可；
- 但在控制台显示新增/删除/更新计数。

---

## 9. 与下游模块的接口约定

## 9.1 给 PaperQA
输入：`manifest.csv + zotero_pdf_root`

需求：
- `file_location` 相对路径稳定
- title 不为空更好
- doi 有则更好

## 9.2 给 Wiki
输入：`library.json`

需求：
- authors/year/journal/collections/tags 可用
- 能基于 `doc_id` 回溯原 PDF

## 9.3 给 MCP
输入：`library.json`

需求：
- 支持按 doi/title/authors/collections/tags 检索
- 返回结构化 metadata

---

## 10. 建议的模块与文件

### `scripts/sync_zotero.py`
命令行入口。

### `src/miniresearch/zotero.py`
核心逻辑，建议至少包含：
- `scan_pdf_root()`
- `load_external_metadata()`
- `merge_records()`
- `build_manifest_rows()`
- `write_manifest_csv()`
- `write_library_json()`

### `tests/test_zotero_sync.py`
重点测试：
- 目录扫描
- metadata 合并
- csv 输出
- 空字段容错

### `tests/test_collection_filter.py`
测试 collections/tags 清洗与过滤。

---

## 11. 失败场景与处理

### 场景 1：PDF 根目录不存在
- 直接报错并退出。

### 场景 2：PDF 文件不可读
- 跳过并记录 warning。

### 场景 3：metadata 文件缺字段
- 尽量降级处理，缺失字段留空。

### 场景 4：多个 metadata 记录映射到同一个 PDF
- 记录冲突 warning；
- 一期可保留第一条并输出日志。

### 场景 5：title/doi 全缺失
- 仍保留记录，但只适合作为最低限度 RAG 输入。

---

## 12. 最小命令接口建议

建议脚本支持：

```bash
python scripts/sync_zotero.py \
  --pdf-root /mnt/d/zotero_backup \
  --metadata ./data/input/zotero_export.csv \
  --out-dir ./data/zotero-export
```

也应支持：

```bash
python scripts/sync_zotero.py \
  --pdf-root /mnt/d/zotero_backup \
  --out-dir ./data/zotero-export
```

即无 metadata 时也能运行。

---

## 13. 验证标准

该同步层完成后，应能验证：
- `/mnt/d/zotero_backup` 中的 PDF 被稳定扫描到；
- `manifest.csv` 可被 PaperQA 使用；
- `library.json` 能支撑 metadata 查询；
- 缺 metadata 的记录不会导致整体失败；
- 增量运行时至少能给出新增/更新/删除计数。

---

## 14. 实施建议

如果只做最小可用版，最优顺序是：
1. 先实现目录扫描；
2. 再实现 metadata 文件加载；
3. 再实现 manifest/library 输出；
4. 最后再加增量报告与清洗规则。

这样能最快让固定目录 `/mnt/d/zotero_backup` 真正进入整个系统。  