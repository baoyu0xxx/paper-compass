     1|# paper-compass v2.0.0 独立部署测试报告
     2|
     3|> 日期：2026-05-09
     4|> 测试方式：从 GitHub 克隆仓库到独立目录，完整模拟他人首次部署场景
     5|
     6|---
     7|
     8|## 一、仓库状态
     9|
    10|仓库 `baoyu0xxx/paper-compass` 已设为公开。  
    11|测试所基于版本：`v2.0.0`（commit `145e9bb`）
    12|
    13|---
    14|
    15|## 二、发现的问题
    16|
    17|### 问题1 [已修复] — 本地 commit 未推送至 GitHub
    18|
    19|**现象**：克隆得到的代码仅为初始骨架（commit `18468e6`），不含任何 v2.0.0 实现。  
    20|**影响**：任何人克隆后只能得到一个空壳，无法运行任何流水线脚本。  
    21|**根因**：本地 23 个 commit 均未推送到远程。  
    22|**处理**：已推送 `main` 分支，克隆后可得完整 v2.0.0 代码。
    23|
    24|### 问题2 [基础设施/待改进] — build_index.py 要求 PDF 文件必须可达
    25|
    26|**现象**：`_prepare_index_inputs()` 中第一个检查是：
    27|
    28|```python
    29|pdf_path = item.get("pdf_path", "")
    30|if not pdf_path or not Path(pdf_path).exists():
    31|    skipped.append(f"{key}: missing PDF")
    32|    continue
    33|```
    34|
    35|即使 `text_file` 已存在且可读，PDF 路径不可达仍会导致该篇被跳过。  
    36|**影响**：对"从他人处获取文本文件但无 PDF"的分发场景不友好。  
    37|**建议**：在 PDF 不可用但 text_file 存在时自动降级。
    38|
    39|### 问题3 [已知/优雅降级] — BM25 multiprocessing 在 WSL 下报错
    40|
    41|**现象**：
    42|
    43|```
    44|Exception ignored in: <function Pool.__del__ at ...>
    45|OSError: [Errno 9] Bad file descriptor
    46|```
    47|
    48|**根因**：`rank_bm25.BM25Okapi` 使用 `multiprocessing.Pool`，在 WSL 环境下清理时失败。  
    49|**处理**：`vector_store.py` 已捕获该异常 → `_bm25_index = None`，纯向量检索不受影响。
    50|
    51|### 问题4 [文档-代码一致性] — search_passages 仅存在于完整 v2.0.0
    52|
    53|**现象**：SKILL.md 描述 v2.0.0 有 6 个 MCP 工具（含 `search_passages`），但初始骨架版本只有 5 个。  
    54|**状态**：推送完整代码后回归一致，6 工具齐全。
    55|
    56|### 问题5 [测试预期行为] — eval 套件依赖于全量数据
    57|
    58|**现象**：在仅有 3 篇测试文献的库上运行 `eval/run_eval.py`，仅有 3/12 查询通过（命中家族企业主题的）。  
    59|**说明**：eval queries 引用了全量 417 篇文献中的特定 key（如 MWWFY69B、V5MD3AYW 等），小样本集下不命中是预期行为，非系统缺陷。
    60|
    61|---
    62|
    63|## 三、流水线测试结果
    64|
    65|### 3.1 测试环境
    66|
    67|| 项目 | 值 |
    68||------|-----|
    69|| 测试目录 | 独立 clone（`git clone` 到独立目录） |
    70|| 测试文献 | 3 篇中文家族企业传承主题 |
    71|| 运行工作目录 | 项目根目录 |
    72|| Embedding provider | 火山引擎 Doubao embedding vision（dim=2048） |
    73|| Wiki LLM | Mimo v2.5-pro |
    74|
    75|### 3.2 各阶段结果
    76|
    77|| 阶段 | 命令 | 结果 | 关键指标 |
    78||------|------|------|----------|
    79|| 文献向量化 | `build_index.py --full-rebuild` | ✅ | 3 篇 → 85 chunks / 85 vectors |
    80|| Wiki 生成 | `ingest_to_wiki.py --limit 3 --workers 1` | ✅ | 3 篇全部 OK / 2.3 min / 1.3 篇/min |
    81|| Wiki 向量化 | `build_index.py --wiki` | ✅ | 41 sections / 41 vectors |
    82|| Healthcheck | `healthcheck.py --smoke` | ✅ | 7 项检查全部通过 |
    83|
    84|### 3.3 MCP 工具测试
    85|
    86|| 工具 | 查询 | 结果 | 说明 |
    87||------|------|------|------|
    88|| `search_wiki` | "家族企业代际传承" | ✅ | 最高分 0.70，命中"扶上马送一程" |
    89|| `search_library` | "家族企业" | ✅ | 3 篇全部返回，元数据完整 |
    90|| `search_passages` | "家族企业代际传承" | ✅ | 返回详细段落原文，含作者信息 |
    91|| `ask_research` | "家族企业代际传承对员工的影响" | ✅ | wiki 模式，引用 3 篇 wiki 页 + 3 篇 PDF 证据 |
    92|
    93|---
    94|
    95|## 四、标准部署流程（供他人参考）
    96|
    97|```bash
    98|# 1. 克隆
    99|git clone https://github.com/baoyu0xxx/paper-compass.git
   100|cd paper-compass
   101|
   102|# 2. 配置
   103|cp .env.example .env
   104|# 编辑 .env，填入 LLM_BASE_URL、LLM_API_KEY、VOLC_EMBED_* 等
   105|
   106|# 3. 准备数据
   107|# 需要准备 library.json（含 key, title, pdf_path, text_file 等字段）
   108|# 及对应的 PDF / text 文件
   109|# 详见 scripts/sync_zotero.py
   110|
   111|# 4. 文献向量化
   112|python3 scripts/build_index.py --library data/zotero-export/library.json --full-rebuild
   113|
   114|# 5. Wiki 生成（长任务，可选）
   115|python3 scripts/ingest_to_wiki.py --skip-existing --workers 10
   116|
   117|# 6. Wiki 向量化
   118|python3 scripts/build_index.py --wiki --wiki-root ./wiki
   119|
   120|# 7. 验证
   121|python3 scripts/healthcheck.py --smoke
   122|
   123|# 8. 运行检索测试
   124|python3 scripts/run_mcp_server.py --tool search_wiki --query "research question"
   125|python3 scripts/run_mcp_server.py --tool search_library --query "author name"
   126|python3 scripts/run_mcp_server.py --tool search_passages --query "specific passage"
   127|python3 scripts/run_mcp_server.py --tool ask_research --query "research question"
   128|
   129|# 9. 运行 Eval（需要全量数据）
   130|python3 eval/run_eval.py
   131|```
   132|
   133|---
   134|
   135|## 五、测试文件清理
   136|
   137|测试使用的独立克隆目录（`/mnt/d/paper/test-clone/`）已在完成测试后删除。
   138|