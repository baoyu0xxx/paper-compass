# paper-compass 增量索引方案 Implementation Plan

> **For Hermes:** Use subagent-driven-development skill to implement this plan task-by-task.

**Goal:** 在尽量复用 `RAG-Assistant-for-Zotero` 现有思路和代码结构的前提下，为 `paper-compass` 设计并落地一个可重复运行、可识别新增/变更/删除论文的增量索引方案。

**Architecture:** 采用“复用上游增量判定骨架 + 为本项目补足变更检测”的最小可用方案。具体上，直接复用上游 `get_indexed_item_ids()` / `delete_item()` 这类 Chroma 辅助能力与“先枚举已索引对象、再筛选新增对象”的流程；同时针对 `paper-compass` 当前以 `key` 和 `text_file` 为主的数据形态，增加一个本地 `manifest` 来判断“内容是否变化”，避免仅能处理新增、无法处理更新的问题。

**Tech Stack:** Python 3.11, ChromaDB, 本地 JSON manifest, pytest

---

## 1. 当前代码与上游项目的关键结论

### 1.1 `RAG-Assistant-for-Zotero` 已实现了什么

基于本地参考代码 `/mnt/d/pyproject/.ref-inspect/RAG-Assistant-for-Zotero`，上游已经实现了一套“有限增量”机制：

1. `backend/interface.py`
   - `start_indexing(incremental: bool = True)` 支持增量/全量两种入口。
   - `_index_library_incremental_worker()` 的核心逻辑是：
     - 先从 Zotero 取全部 `item_id`
     - 再从 Chroma 取 `get_indexed_item_ids()`
     - 用集合差 `all_item_ids - indexed_ids` 找出“新论文”
     - 只对这些新论文做抽取、切块、embedding、写入

2. `backend/vector_db.py`
   - 有现成的可复用辅助方法：
     - `get_indexed_item_ids()`：读取整个 collection 的 metadata，汇总已索引 `item_id`
     - `item_exists(item_id)`：判断单篇是否已索引
     - `delete_item(item_id)`：删除某篇文献的全部 chunks
   - 这些方法与 `paper-compass` 的需求高度同构，只是主键从 `item_id` 换成 `item_key` 更合适。

3. `backend/metadata_migration.py`
   - 证明了上游已经使用过 `collection.update(...)` 做原地 metadata 更新。
   - 这说明其设计并不排斥“增量修补”，只是主索引流程仍然是 append-first。

### 1.2 `RAG-Assistant-for-Zotero` 没有解决什么

上游的增量索引仍然有明显局限：

1. 只能识别“新增”，不能可靠识别“已存在但 PDF/文本内容变了”
   - 因为它只比较 `item_id` 是否已存在。
   - 若同一篇论文的 PDF 更新、文本抽取改了、chunk 数变了，旧索引不会自动替换。

2. 不能自动处理“删除”
   - Zotero 里删掉的 item，向量库里旧 chunks 仍会残留，除非手动清理。

3. 仍然使用 `collection.add(...)`
   - 这使它本质上仍是 append-only。
   - 一旦对已存在 chunk_id 重跑，容易触发重复 ID 异常。

### 1.3 `paper-compass` 当前状态

当前项目 `/mnt/d/pyproject/paper-compass` 的索引代码还没有增量能力：

1. `src/miniresearch/vector_store.py`
   - `add_chunks()` 仍调用 `self.collection.add(...)`
   - 无 `upsert`、无按论文删除、无获取已索引主键集合的方法

2. `scripts/build_index.py`
   - 没有 `--incremental` / `--full-rebuild` / `--prune-deleted` 等参数
   - 直接遍历 `library.json` 全量切块并写入
   - papers 使用的 metadata 已包含 `item_key`，这是一个很好的复用锚点

3. `scripts/sync_zotero.py`
   - 已生成 `library.json`
   - 已在 `--extract-text` 时生成 `data/texts/{key}.txt`
   - 但没有记录文本指纹、抽取时间、pdf mtime、pdf size 等增量判定信息

4. 测试
   - 当前测试主要是 `tests/test_mcp_backend.py` 和 `tests/test_config.py`
   - 没有覆盖向量库增量行为的测试

---

## 2. 设计原则

### 2.1 复用优先分类

#### 直接复用

1. 上游 `backend/vector_db.py` 的思路
   - `get_indexed_item_ids()`
   - `item_exists()`
   - `delete_item()`

2. 上游 `backend/interface.py` 的增量判定骨架
   - “先列出现有索引主键，再与当前库做集合比较”的流程

3. 上游 `backend/metadata_migration.py` 的局部更新思路
   - 证明 Chroma collection 支持后续 `update` / `delete + re-add` 型维护

#### 借鉴设计但不整套搬运

1. “后台线程 + 状态进度条”
   - 这是上游 UI/API 服务的需要
   - `paper-compass` 当前是脚本型流水线，不必先引入线程化调度

2. 直接沿用 `item_id`
   - 本项目已有稳定的 Zotero `key` 和文本缓存文件名 `{key}.txt`
   - 应优先以 `key` 作为增量索引主键，而不是回退到 `item_id`

#### v1 不采用

1. 复杂的 chunk 级 diff
   - 会显著增加复杂度
   - 当前完全没有必要逐 chunk 对比内容差异

2. 增量 BM25 更新
   - 现有 BM25 构建就是全量 rebuild
   - v1 可以接受“向量增量 + BM25 末尾全量重建一次”

3. 自动跨 embedding model 迁移
   - 当前 collection 本来就按模型隔离命名
   - 模型变更时直接视为新 collection，不做兼容层

### 2.2 Frozen v1 scope

v1 只解决以下问题：

1. 新增论文：自动索引
2. 已有论文但文本内容变化：自动删除旧 chunks 后重建
3. 已删除论文：可选清理 collection 中残留 chunks
4. wiki collection：至少做到 `upsert` 级别幂等；是否做 manifest 追踪可延后

### 2.3 非目标

1. 不做 chunk 级最小差量更新
2. 不做异步任务队列
3. 不做 GUI/API 侧 indexing status
4. 不在 v1 里引入额外数据库；manifest 用 JSON 文件即可

---

## 3. 建议的目标方案

## 3.1 papers 索引：主键、判定、动作

### 主键

- collection 内单 chunk 主键继续使用：`{key}_c{index}``
- 单篇论文主键使用 metadata 字段：`item_key`

这与当前 `build_index.py` 已写入的 metadata 一致，复用成本最低。

### 增量判定来源

对每篇论文生成一个 source fingerprint，推荐字段：

- `key`
- `pdf_path`
- `text_file`
- `text_sha1`
- `text_size`
- `pdf_mtime`（若 PDF 存在）
- `chunking_version`（例如 `papers_v1_cs1500_ol200_trunc2000`）
- `embedding_model_id`

其中最核心的是：
- `text_sha1`
- `chunking_version`
- `embedding_model_id`

只要这三者之一变化，就应触发该篇论文重建。

### manifest 存储

建议在 `data/vectordb/` 下按 collection 保存 manifest，例如：

- `data/vectordb/papers_<safe_model_id>.manifest.json`
- `data/vectordb/wiki_<safe_model_id>.manifest.json`

manifest 结构建议：

```json
{
  "collection_name": "papers_volcengine-ep-20260420154519-9w64q",
  "embedding_model_id": "volcengine:ep-20260420154519-9w64q",
  "chunking_version": "papers_v1_cs1500_ol200_trunc2000",
  "items": {
    "DDB85DWJ": {
      "text_sha1": "...",
      "text_size": 123456,
      "pdf_path": "/abs/path/file.pdf",
      "pdf_mtime": 1711111111,
      "chunk_count": 57,
      "updated_at": "2026-05-08T19:22:21Z"
    }
  }
}
```

### 动作规则

对当前 `library.json` 中每篇 paper：

1. 若 `key` 不在 manifest 中
   - 视为 `new`
   - 直接索引并写入 manifest

2. 若 `key` 在 manifest 中，但 `text_sha1` / `chunking_version` / `embedding_model_id` 任一变化
   - 视为 `changed`
   - 先删除该 `item_key` 的全部旧 chunks
   - 再重建并更新 manifest

3. 若 `key` 在 manifest 中且 fingerprint 未变化
   - 视为 `unchanged`
   - 跳过

4. 若 manifest 中有 key，但 `library.json` 已不存在
   - 若启用 `--prune-deleted`
     - 删除该 key 在 collection 中的旧 chunks
     - 从 manifest 移除
   - 否则只报告，不动数据

这比上游“只比较是否已存在 item_id”更适合本项目。

---

## 3.2 wiki 索引：v1 先做幂等，再决定是否追踪变化

wiki collection 的最小可用方案：

1. 将 `vector_store.py.add_chunks()` 改为支持 `upsert=True`
2. `build_index.py --wiki` 默认对 `chunk_id = {md_file.stem}_s{i}` 做 upsert
3. 这样重复运行 wiki 索引不会因重复 ID 崩溃

wiki v1 可以不立刻做 manifest，原因：

1. section 切分粒度较粗，重跑成本相对低
2. `md_file` 本身已经是派生产物
3. 先解决 papers 增量是主收益点

但若要补齐，也建议后续用：
- `page_path`
- `file_mtime`
- `content_sha1`
作为 wiki fingerprint。

---

## 4. 代码层方案

### Task 1: 为 `VectorStore` 增加可复用的增量管理方法

**Objective:** 把上游 `vector_db.py` 中与增量相关的方法迁移到 `paper-compass` 的 `VectorStore`，但以 `item_key` 为中心。

**Files:**
- Modify: `src/miniresearch/vector_store.py`
- Test: `tests/test_incremental_index.py`

**Planned changes:**

1. 保留现有 `add_chunks()` 接口，但增加可选参数，例如：
   - `mode: Literal["add", "upsert"] = "add"`
   - 或拆成 `add_chunks()` / `upsert_chunks()`

2. 新增方法：
   - `get_indexed_item_keys() -> set[str]`
   - `delete_item(item_key: str) -> int`
   - `get_chunk_ids_for_item(item_key: str) -> list[str]`

3. 实现方式尽量直接复用上游逻辑：
   - 上游 `get_indexed_item_ids()` 改为读取 metadata 里的 `item_key`
   - 上游 `delete_item()` 改为 `where={"item_key": item_key}` 查询后批量删除

**Verification:**

- 单测覆盖：
  - 空库返回空集合
  - 插入两篇 paper 后，`get_indexed_item_keys()` 返回两个 key
  - `delete_item()` 仅删除对应论文 chunks，不影响其他论文

---

### Task 2: 新增 manifest 帮助层

**Objective:** 为 `build_index.py` 提供独立的 fingerprint 读写能力，避免把判定逻辑全部堆在脚本里。

**Files:**
- Create: `src/miniresearch/index_manifest.py`
- Test: `tests/test_incremental_index.py`

**Planned changes:**

1. 新建一个轻量模块，提供：
   - `load_manifest(path) -> dict`
   - `save_manifest(path, data) -> None`
   - `compute_text_sha1(text: str) -> str`
   - `build_paper_fingerprint(item, full_text, chunking_version, embedding_model_id) -> dict`
   - `diff_manifest(current_items, manifest_items) -> {new, changed, unchanged, deleted}`

2. 设计要求：
   - 纯标准库实现（`json`, `hashlib`, `datetime`, `pathlib`）
   - manifest 缺失时自动视为空
   - 内容不合法时给出明确异常

**Verification:**

- 单测覆盖：
  - manifest 缺失时返回空结构
  - 相同文本 hash 稳定
  - 文本变化后 hash 变化
  - manifest diff 能正确区分 new / changed / unchanged / deleted

---

### Task 3: 扩展 `build_index.py` 参数与增量入口

**Objective:** 为 papers 索引增加显式的增量模式与删除清理模式。

**Files:**
- Modify: `scripts/build_index.py`
- Test: `tests/test_incremental_index.py`

**Planned changes:**

1. 新增 CLI 参数：
   - `--incremental`：仅处理 new/changed
   - `--full-rebuild`：先清空 collection，再全量索引
   - `--prune-deleted`：在增量模式下删除 manifest 里存在但当前库不存在的论文
   - `--manifest-path`：可选覆盖 manifest 位置

2. 行为约束：
   - `--incremental` 与 `--full-rebuild` 互斥
   - 默认建议改为：papers 走 `--incremental` 更安全；若保持兼容，也可默认仍走全量、增量需显式开启

3. 先在脚本里构造：
   - `current_items_by_key`
   - `manifest_items`
   - `diff_result`

4. 输出 summary：
   - new / changed / unchanged / deleted 计数
   - added_chunks / deleted_chunks / final_vector_count

**Verification:**

- 命令级验证：
  - 第一次 `--incremental`：应索引全部 paper
  - 第二次不变重跑：应 0 papers rebuilt
  - 修改某一个 `data/texts/{key}.txt` 后重跑：应只重建该 key

---

### Task 4: 实现 papers 的“删旧后重建”流程

**Objective:** 用最小复杂度保证变更论文不会残留旧 chunks。

**Files:**
- Modify: `scripts/build_index.py`
- Modify: `src/miniresearch/vector_store.py`
- Test: `tests/test_incremental_index.py`

**Planned changes:**

1. 对 `changed` 项：
   - 调 `store.delete_item(key)`
   - 再重新 chunk / embed / add or upsert

2. 对 `new` 项：
   - 直接 add 或 upsert

3. 对 `unchanged` 项：
   - 完全跳过，不生成 embedding

4. 对 `deleted` 项（仅 `--prune-deleted`）：
   - 调 `store.delete_item(key)`
   - manifest 删除对应条目

**Tradeoff:**

- 这里不做 chunk 级最小更新，而是按 paper 粒度重建。
- 好处是逻辑简单、结果稳定、易测试。
- 成本是修改单篇 paper 时会重算该篇全部 chunks，但对当前项目规模是可以接受的。

---

### Task 5: 把 wiki 索引改成幂等 upsert

**Objective:** 先解决重复运行 `build_index.py --wiki` 的稳定性问题。

**Files:**
- Modify: `src/miniresearch/vector_store.py`
- Modify: `scripts/build_index.py`
- Test: `tests/test_incremental_index.py`

**Planned changes:**

1. 对 wiki 索引路径使用 `upsert`
2. 保持 chunk_id 规则不变：`{md_file.stem}_s{i}`
3. 允许后续在需要时再为 wiki 单独追加 manifest

**Verification:**

- 同一份 wiki 目录连续跑两次，不应报重复 ID 错误
- 修改某一页 markdown 后重跑，应成功覆盖原 section 向量

---

### Task 6: 修复 `build_index.py._load_env()` 的覆盖逻辑

**Objective:** 顺手修掉已知的 stale env poisoning 风险，避免增量索引实现后仍被环境变量污染干扰。

**Files:**
- Modify: `scripts/build_index.py`
- Test: `tests/test_incremental_index.py` 或新增轻量单测

**Planned changes:**

1. 当前代码：

```python
if val and not os.environ.get(key.strip()):
    os.environ[key.strip()] = val.strip()
```

2. 应改为无条件覆盖：

```python
if val:
    os.environ[key.strip()] = val.strip()
```

**Reason:** 这与项目里已经确认过的 `.env` 优先级约定一致。

---

### Task 7: 增加针对增量索引的测试夹具

**Objective:** 用临时目录 + 小样本文本，验证增量行为，而不依赖真实 Zotero/Volcengine。

**Files:**
- Create: `tests/test_incremental_index.py`

**Planned test strategy:**

1. 用 fake/stub embeddings 替代真实 embedder
   - 返回固定长度向量，例如 `[0.1, 0.2, 0.3]`

2. 用临时 `library.json` + `data/texts/*.txt` 构造最小数据集

3. 覆盖场景：
   - `test_full_then_incremental_no_change`
   - `test_incremental_detects_changed_text_and_replaces_chunks`
   - `test_incremental_detects_new_item`
   - `test_prune_deleted_removes_chunks`
   - `test_wiki_reindex_is_idempotent`

4. 若脚本函数不易单测，优先把判定逻辑下沉到可导入函数中，再测试函数，不直接用 subprocess 测 CLI

---

## 5. 具体文件变更清单

### 必改

- `src/miniresearch/vector_store.py`
- `scripts/build_index.py`

### 建议新增

- `src/miniresearch/index_manifest.py`
- `tests/test_incremental_index.py`

### 可选补充

- `scripts/sync_zotero.py`
  - 如果后续希望把 `pdf_mtime` 或 `text_sha1` 提前写入 `library.json`，可在这里补字段
  - 但不是 v1 必要条件，因为 `build_index.py` 已经会读取 text 内容

---

## 6. 测试与验证方案

### 自动化测试

在仓库根目录 `/mnt/d/pyproject/paper-compass` 下运行：

```bash
python3 -m pytest tests/test_incremental_index.py -v
python3 -m pytest tests/ -v
```

### 手工验证

#### 场景 A：首次增量索引

```bash
python3 scripts/build_index.py --library data/zotero-export/library.json --incremental
```

预期：
- 全部论文被视为 `new`
- 建立 manifest
- 输出最终 chunk 数

#### 场景 B：无变化重跑

再次运行相同命令。

预期：
- 大部分论文为 `unchanged`
- 不发生重复 embedding
- 不发生重复 ID 错误

#### 场景 C：单篇文本变化

手动修改一个 `data/texts/{key}.txt` 的内容后重跑。

预期：
- 仅该篇被判定为 `changed`
- 先删除旧 chunks，再写入新 chunks
- collection 总量与 chunk_count 变化合理

#### 场景 D：删除论文

从 `library.json` 中移除某个 key，然后运行：

```bash
python3 scripts/build_index.py --library data/zotero-export/library.json --incremental --prune-deleted
```

预期：
- 该 key 对应 chunks 从 collection 中删除
- manifest 同步移除

#### 场景 E：wiki 重跑

```bash
python3 scripts/build_index.py --wiki --wiki-root ./wiki
python3 scripts/build_index.py --wiki --wiki-root ./wiki
```

预期：
- 第二次不会报 duplicate ID
- 若 markdown 修改，upsert 后内容可更新

---

## 7. 风险、权衡与开放问题

### 风险 1：Chroma metadata where 的兼容性

- 当前 papers metadata 已写 `item_key`，这是好事。
- 但需确认 Chroma 对字符串 `where={"item_key": key}` 的过滤稳定可用。
- 若不稳，可回退为：先 `collection.get(include=['metadatas'])`，再在 Python 侧筛出 ids 删除。

### 风险 2：manifest 与真实 collection 不一致

可能场景：
- 程序在写完部分向量后中断，manifest 尚未落盘
- manifest 被人工删除

应对：
- manifest 保存放在单篇成功写入之后
- 若发现 manifest 缺失但 collection 非空，允许继续扫描并重建 manifest，或至少给出警告

### 风险 3：chunking 参数调整会引发大面积重建

这是预期行为，不是 bug。

解决方式：
- 将 chunking 参数编码进 `chunking_version`
- 参数变化时自动判定为 `changed`

### 风险 4：wiki section 序号变化导致旧 section 残留

若页面结构大改，旧的 `{stem}_s{i}` 可能仍残留。

v1 方案：
- 先接受这一局限，只解决重复运行不报错
- 若后续要彻底解决，可增加“按 page_path 先删后写”的 wiki 重建模式

### 开放问题 1：默认模式是否改成 incremental

有两个选择：

1. 保守兼容：默认仍全量，用户显式加 `--incremental`
2. 以生产可用为先：默认 incremental，`--full-rebuild` 显式触发全量

建议：先做选项兼容，再由用户决定默认值。

### 开放问题 2：是否把 `upsert` 作为 papers 默认写入方式

建议：
- `changed` 项仍采取“delete item -> re-add”作为主路径，语义最清晰
- `upsert` 可作为 wiki 路径和额外保险，而不是 papers 唯一策略

原因：
- 如果 chunk 数减少，仅 `upsert` 无法清除旧尾部 chunks
- paper 粒度 delete+rebuild 更稳妥

---

## 8. 推荐实施顺序

1. 先改 `VectorStore`，迁移上游增量辅助方法
2. 再新增 manifest 模块
3. 再重构 `build_index.py` 的 papers 增量路径
4. 再加 wiki upsert
5. 最后补测试和手工验证

这个顺序的好处是：
- 先把复用层搭好
- 再做脚本编排
- 最后才处理外围幂等和回归

---

## 9. 最终建议

最值得优先落地的是一个“简单但完整”的 v1：

1. papers：
   - 复用上游 `get_indexed_item_ids()` / `delete_item()` 思路
   - 改造成 `item_key` 版本
   - 引入 manifest 做 changed/new/deleted 判定
   - changed 采用“删旧后重建”

2. wiki：
   - 先做 `upsert` 幂等

3. BM25：
   - 每次增量任务结束后全量 rebuild 一次

这个方案相对克制，但已经能明显优于上游只支持“新增论文”的增量能力，也与 `paper-compass` 当前脚本式 pipeline 最契合。
