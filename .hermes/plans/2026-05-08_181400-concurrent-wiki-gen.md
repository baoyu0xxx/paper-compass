# Concurrent Wiki Generation

**Goal**: 把串行 wiki 生成（~50s/篇，400 篇 ≈ 5.5h）改为并发（10-20x 提速 → ~20-30min），在 Mimo RPM 100 / TPM 10M 限速内跑满。

**Status**: 计划阶段，待实施。

---

## 1. 当前架构分析

```
ingest_to_wiki.py (for item in items)
  ├── classify() → _call() → urllib.request (Pass1, ~5s, ~100 tokens)
  ├── generate() → _call() → urllib.request (Pass2, ~25-45s, ~2400 tokens)
  └── save_query_to_wiki() → write .md + update index.md + append log.md
```

瓶颈：单线程串行，API 等待时间占 95%+。Mimo 限速基本空闲（实际 2.4/100 RPM，3K/10M TPM）。

## 2. 耦合点

| 调用方 | 被调模块 | 方法 | 线程安全性 |
|--------|----------|------|-----------|
| `ingest_to_wiki.py` | `wiki_gen.WikiGenerator` | `generate()` / `classify()` | ✅ 线程安全（只读实例状态，urllib 每请求独立连接） |
| `ingest_to_wiki.py` | `wiki_store.save_query_to_wiki` | `save_query_to_wiki()` | ⚠️ 部分不安全：`.md` 写入安全（不同文件），`index.md` 写入和 `log.md` append 存在竞态 |
| `mcp_server.py` | `wiki_store.save_query_to_wiki` | `save_query_to_wiki()` | MCP 交互式单写，与批量后台不重叠 |

## 3. 并发模型选择

**ThreadPoolExecutor** — I/O 密集型（API 调用），Python 线程天然适合。

备选考虑：
- `asyncio` + `aiohttp`：需替换 `urllib.request`，改动面大，收益不明显（线程在 I/O 等待时释放 GIL 已足够）
- `ProcessPoolExecutor`：进程开销大，且 `WikiGenerator` 实例不可跨进程序列化

**并发度**：`max_workers=10`——保守估计 10 papers 同时进行。每个 paper 两次 API 调用（classify + generate），最多 20 个活跃请求，远低于 RPM 100。

## 4. 改造计划

### 4.1 `wiki_gen.py` — 增加重试逻辑

在 `_call()` 方法中增加 429 和 5xx 重试：

```python
def _call(self, ..., max_retries: int = 3) -> str:
    for attempt in range(max_retries):
        try:
            resp = urllib.request.urlopen(req, timeout=180)
            ...
        except urllib.error.HTTPError as e:
            if e.code == 429 and attempt < max_retries - 1:
                time.sleep(2 ** attempt)  # 1s, 2s, 4s
                continue
            raise
```

**影响面**：仅 `_call()` 方法，不影响外部接口。

### 4.2 `wiki_store.py` — 线程安全改造

问题：`save_query_to_wiki()` 内部调用 `_update_index()` 和 `_update_log()`，多个线程同时读写 `index.md` 和 `log.md` 可能产生竞态。

方案：模块级 `threading.Lock` 保护 index 和 log 操作。

```python
import threading

_index_lock = threading.Lock()
_log_lock = threading.Lock()

def save_query_to_wiki(...):
    # page .md 写入 — 无锁（不同文件，安全）
    page_path.write_text(full_content, encoding="utf-8")
    
    # index.md 更新 — 加锁
    with _index_lock:
        index_updated = _update_index(...)
    
    # log.md 更新 — 加锁
    with _log_lock:
        log_updated = _update_log(...)
```

**影响面**：仅 `save_query_to_wiki()` 内部，对外接口不变。`mcp_server.py` 调用不受影响（锁在单写场景下零竞争）。

### 4.3 `ingest_to_wiki.py` — 并发主循环

重构主循环：

```python
from concurrent.futures import ThreadPoolExecutor, as_completed
import threading

def process_one(item, generator, args):
    """处理单篇论文，返回结果字典。线程安全。"""
    key = item.get("key", "")
    # ... 原有逻辑：检查 PDF、提取文本、generate、save
    return {"key": key, "status": "ok"|"skip"|"error", ...}

def main():
    # 1. 加载 library，预过滤
    items = load_and_filter(args)  # 去掉无 PDF、已有 wiki 的
    
    # 2. 并发处理
    generator = WikiGenerator()
    counter = {"done": 0, "skip": 0, "error": 0}
    lock = threading.Lock()
    
    with ThreadPoolExecutor(max_workers=10) as executor:
        futures = {
            executor.submit(process_one, item, generator, args): item
            for item in items
        }
        for future in as_completed(futures):
            result = future.result()
            with lock:
                counter["done"] += 1
                print(f"[{counter['done']}/{len(items)}] {result['key']} {result['status']}")
```

要点：
- `WikiGenerator` 实例共享给所有 worker（线程安全）
- 预过滤在并发前完成（`--skip-existing` 检查保持串行，避免重复创建 wiki）
- 计数器用 `threading.Lock` 保护
- `--skip-existing` 的预检查逻辑不变（在并发前 scan `wiki/papers/`）

### 4.4 `--skip-existing` 并发安全性

⚠️ **关键**：必须在提交线程池前完成所有 `_has_wiki_page()` 检查。不能在 worker 内部检查，否则两个 worker 可能同时判断同一篇"不存在"并都生成。

当前 `_has_wiki_page()` 扫描 `wiki/papers/*.md` 文件内容 — 这是 O(n×m) 的开销。对于 400 篇论文扫描 75 个已有文件，开销可忽略（毫秒级）。但为了保险，改为：

```python
# 预加载已有 wiki keys → set
def _load_existing_keys(wiki_root: str) -> set:
    import re
    keys = set()
    papers_dir = Path(wiki_root) / "papers"
    if papers_dir.exists():
        for md_file in papers_dir.glob("*.md"):
            text = md_file.read_text(encoding="utf-8")
            for m in re.finditer(r'zotero:([A-Z0-9]+)', text):
                keys.add(m.group(1))
    return keys
```

一次扫描 → set → O(1) 查找。

## 5. 改动文件清单

| 文件 | 改动类型 | 说明 |
|------|----------|------|
| `src/miniresearch/wiki_gen.py` | 微调 | `_call()` 增加 429 重试 |
| `src/miniresearch/wiki_store.py` | 微调 | `save_query_to_wiki()` 加锁保护 index/log |
| `scripts/ingest_to_wiki.py` | 重写主循环 | ThreadPoolExecutor + 预过滤优化 |

**不改动**：`wiki_gen.generate()`、`wiki_gen.classify()`、`mcp_server.py`、`config.py`、prompts。

## 6. 测试计划

### 6.1 小样本测试（10 篇）

```bash
cd /mnt/d/pyproject/paper-compass
python3 scripts/ingest_to_wiki.py --skip-existing --limit 10
```

验证：
- 10 篇全部正确生成
- 无竞态错误（index.md 不重复、log.md 不乱序）
- 速率显著提升（预期 ~5-8 篇同时进行，总时间 ~1-2 分钟而非 8 分钟）
- 已有 wiki 正确跳过

### 6.2 回归

```bash
python3 -m pytest tests/ -v
```

### 6.3 压力检查

- 确认没有 Mimo 429 返回（若有，观察重试是否生效）
- 确认 RPM 远低于 100

## 7. 预期效果

| 指标 | 串行 | 并发 10 workers |
|------|------|----------------|
| 单篇耗时 | ~50s | ~50s（无变化） |
| 有效吞吐 | 1.2 篇/min | ~12 篇/min |
| 400 篇耗时 | ~5.5h | ~30-35 min |
| RPM 峰值 | ~2.4 | ~24（20 活跃请求/分钟级） |
| TPM | ~3K | ~30K（0.3% of 10M） |

## 8. 风险与缓解

| 风险 | 概率 | 缓解 |
|------|------|------|
| Mimo 并发连接限制（非 RPM，是同时连接数） | 低 | 先从 10 workers 开始，观察 429 频率；必要时降到 5 |
| `index.md` 格式因并发写入损坏 | 低 | Lock 保护；index.md 是简单列表追加，不是结构化重写 |
| 内存占用 10 篇 PDF 文本同时在内存 | 低 | 每篇文本 ~10K chars，10 篇 ~1MB，可忽略 |
| 日志乱序 | 中 | Lock 保护 log.md 写入；但进度打印到 stdout 可能交错，这是可接受的 |

## 9. 非目标（本次不做）

- 不做 `asyncio` 全异步改造（改动面大，收益不明显）
- 不做断点续传改进（`--skip-existing` 已足够）
- 不做 API 调用合并（classify + generate 是两阶段，无法合并）
- 不做 MCP server 并发改造（当前交互式单写不构成瓶颈）
