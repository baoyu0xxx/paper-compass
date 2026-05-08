# paper-compass 检索质量优化方案

> For Hermes: this is a planning document only. Do not implement from this file directly without a separate execution step.

**Goal:**
在不推翻现有 paper-compass 架构的前提下，系统性提高 wiki / hybrid 检索的结果纯度、信息密度、可解释性与可维护性，优先解决 log/index 噪音、frontmatter 命中、page_path 可读性错误，以及 library/pdf 侧旁路召回偏杂的问题；同时把这些噪音页面已经写入当前向量库的对应向量删除，避免“代码修好了但旧脏数据仍在生效”。

**Architecture:**
沿用现有 `wiki -> vector_search -> router -> ask_research` 主链路，不新建独立检索系统。优化分为三层：
1. 索引前清洗：控制哪些 wiki 页面允许进入 collection，以及页面如何切块；
2. 检索时重排：对已召回结果做轻量规则过滤、惩罚和去重；
3. 输出层解释：返回真实页面路径、页面类型、section 信息，便于诊断与后续调参。

**Tech Stack / Scope:**
- Python
- ChromaDB 现有 collection
- 现有 `scripts/build_index.py`、`src/miniresearch/filters.py`、`src/miniresearch/router.py`、`src/miniresearch/mcp_server.py`
- 测试框架：`pytest`

---

## 1. Current context and confirmed problems

基于当前代码与用户的全量测试反馈，已确认如下问题：

### P0: 非知识页被索引进 wiki collection
当前 `scripts/build_index.py` 在 `index_wiki()` 中直接遍历 `wiki_root.rglob("*.md")`，仅排除隐藏文件，不区分页面类型。
这意味着以下文件会进入向量库：
- `wiki/log.md`
- `wiki/index.md`
- 未来其他运维/记录类 markdown

这与用户观测一致：
- `log.md` 已被切成大量 section 并进入向量库
- `index.md` 也被索引
- 导致 query 命中日志而不是真正知识页

### P1: section 0 混入 YAML frontmatter
当前 `index_wiki()` 直接对整个文件内容执行：
- `sections = content.split("\n## ")`
- `text = section[:2000].strip()`

因此 section 0 常常包含：
- YAML frontmatter
- `# 一级标题`
- 少量正文

这会降低 chunk 信息密度，并导致“前言/元数据块”被高频召回。

### P1: `ask_research()` 返回的 `wiki_context.pages_used.page_path` 错填为 chunk id
当前 `src/miniresearch/router.py` 中：
- `page_path` 实际填的是 `w["id"]`
- 正确值应来自 `w["metadata"]["page_path"]`

这不直接损害召回，但显著降低了结果解释性，也妨碍后续误召回诊断。

### P2: library/pdf 侧召回存在“旁路命中”
当前 `ask_research()` 在 hybrid / pdf 模式下：
- 直接 `vector_search(query, collection="papers", k=max_sources)`
- 未与 wiki 侧高置信页面、library metadata 结果做交叉约束
- 未做按 `item_key` 聚合 / 去重 / 限制同一文献 chunk 数

因此较宽 query 时，可能混入语义相近但并非目标文献的 paper chunks。

### P2: 测试覆盖不完整
当前测试集中：
- 有 `tests/test_incremental_index.py`，覆盖增量索引和 wiki reindex 幂等性
- 但尚无针对以下行为的专门测试：
  - wiki 索引排除规则
  - frontmatter stripping
  - router 返回真实 page_path
  - hybrid 结果去噪 / 去重 / 限制规则

---

## 2. Frozen v1 scope

本轮优化的 v1 范围建议冻结为以下五项：

1. wiki 索引时排除噪音页
2. wiki 切块前去掉 YAML frontmatter，并降低 section 0 的元数据污染
3. router / MCP 输出真实 `page_path`
4. hybrid 模式对 pdf/library 结果做轻量重排与去重
5. 建立“可定向删除指定 wiki 向量”的正式能力，并用它删除当前 collection 中已存在的噪音页向量，同时刷新/重建 BM25

### Explicit non-goals for v1

以下内容先不纳入本轮实现：
- 重写为全新的多阶段学习排序器
- 引入 cross-encoder / reranker 模型
- 对整个 wiki 页面体系做重构
- 引入 PaperQA 级深度 PDF 检索
- 新建独立“日志索引”和“知识索引”双库体系

原因：当前暴露的问题主要仍是数据纯度与简单后处理问题，用较轻量的工程改动即可获得较大提升。

---

## 3. Proposed approach

### Layer A: 索引准入控制（最高优先级）
在 `index_wiki()` 中显式定义“可索引页面白名单”或“不可索引页面黑名单”。

注意：仅修改未来索引规则并不够。由于 `log.md`、`index.md` 的 chunks 已经进入当前 collection，本轮还需要把现存脏向量从当前向量库中删除；否则即便新代码不再写入这些页面，旧 collection 仍会继续把它们召回。

推荐 v1 规则：
- 默认排除根目录下：`log.md`、`index.md`
- 默认排除目录：`wiki/queries/`（可配置，默认先排除）
- 仅索引知识页目录：
  - `wiki/papers/`
  - `wiki/topics/`
  - `wiki/methods/`
  - `wiki/comparisons/`

两种实现方案比较：

方案 A：黑名单排除
- 优点：改动小
- 缺点：以后新增 `notes.md`、`tmp.md` 等仍可能漏进来

方案 B：白名单目录准入
- 优点：更稳，长期可维护性更好
- 缺点：如果未来新增合法目录，需要同步更新名单

建议：v1 采用“白名单目录 + 显式黑名单文件”的混合规则。

### Layer B: 切块前结构清洗
在 wiki 索引阶段增加一个页面预处理函数，负责：
1. 识别并剥离 YAML frontmatter
2. 保留 markdown 标题结构
3. 以 `## ` 为主分节，但确保 section 0 不再含 frontmatter
4. 为 metadata 显式记录：
   - `page_path`
   - `page_type`
   - `title`
   - `section`
   - 可选 `section_heading`

建议新增语义：
- 如果正文在去 frontmatter 后只剩一级标题 + 极短内容，可对 section 0 施加更高最小长度阈值
- 或在召回重排时对 `section == 0` 给予轻微惩罚，而不是完全删除

### Layer C: 检索后轻量重排
在 `vector_search()` 或 `ask_research()` 层增加结果后处理，不改底层 Chroma 查询接口。

wiki 侧建议加入：
- 对 `page_type in {log, index}` 结果直接丢弃（双保险，即使旧库未重建时也有效）
- 对 `section == 0` 给予轻微惩罚系数，例如 `score *= 0.92`
- 对同一页面的多 section 命中做 page-level 去重或限流
  - 例如每页最多保留 2 个 section

pdf 侧建议加入：
- 同一 `item_key` 最多保留前 1-2 个 chunk
- 当 library metadata 已有高分精确匹配时，对不在该候选集中的 pdf chunk 降权
- 当 query 含中文题名、明确作者、明确实体名时，提高 lexical overlap 权重

### Layer D: 输出解释层修正
统一把以下字段透出到返回结果：
- 真实 `page_path`
- `page_type`
- `section`
- 可能的话附带 `section_heading`

这样可直接回答：
- 为什么这个结果被召回？
- 是哪一类页面？
- 是否只是 frontmatter / section 0 命中？

### Layer E: 当前向量库脏数据清理
对已经污染当前 collection 的 wiki 向量做一次显式清理，而不是仅依赖“下次全量重建时自然覆盖”。

这里需要明确一个设计原则：
- 如果系统当前不能删除指定页面对应的向量，那么这不是“操作受限”的小问题，而是向量库更新设计本身不完整；
- 对 wiki 这类会持续增删改的知识库，必须具备“按页面/按路径/按前缀定向删除向量”的正式能力；
- 因此，本轮不应把“全量清空后重建”当作主方案。全量重建只能作为灾备或一次性修复手段，不能代替正确的数据生命周期管理。

推荐 v1 清理策略：
- 为 `VectorStore` 增加 wiki-page 级删除 helper，例如按 `page_path` 或 `page_path` 前缀删除 chunk ids
- 至少支持删除：
  - `wiki/log.md`
  - `wiki/index.md`
  - 可选 `wiki/queries/**`
- 删除后重建 BM25，避免关键词索引继续保留旧语料状态
- 将该能力视为后续 wiki 更新、页面撤回、页面重命名、误写入回滚的基础设施

实现上可分两步：
- 路线 A（主方案）：补齐定向删除能力，再删除现有噪音页向量，并在需要时补充重建受影响页面
- 路线 B（仅灾备/兜底）：直接全量清空 wiki collection，再按新规则重建

两条路线比较：
- 路线 A
  - 优点：设计正确，后续遇到局部删除需求时可直接处理
  - 优点：适合真实知识库维护场景，不会每次都诉诸全量重建
  - 缺点：需要补一个按 `page_path` 删除的能力，并补测试
- 路线 B
  - 优点：一次性操作简单
  - 缺点：不能解决“以后如何删除指定向量”的根本问题
  - 缺点：一旦再次出现局部脏数据，系统仍然不具备定向维护能力

建议：
- v1 主线应改为“先补定向删除能力，再清理当前脏向量”；
- 全量重建只保留为最后兜底方案，而不是推荐默认方案。

---

## 4. File-by-file change map

### 必改文件

1. `scripts/build_index.py`
- 为 `index_wiki()` 增加页面准入规则
- 增加 frontmatter stripping / section parsing helper
- 写入更完整 metadata：`page_path`, `page_type`, `section`, `title`, 可选 `section_heading`
- 可选：增加 CLI 参数，支持显式控制是否索引 queries
- 明确 wiki collection 的清理路径：全量清空后重建，或在支持定向删除后先删脏向量再重建

2. `src/miniresearch/filters.py`
- 修复 `_load_env()`：改为无条件覆盖 `os.environ`
- 在 `vector_search()` 结果中保留更完整 metadata
- 增加 wiki search 结果后处理：噪音页过滤、section 0 轻惩罚、page-level 去重
- 可选：增加 pdf 结果聚合 / item-level 限制辅助函数

3. `src/miniresearch/router.py`
- 修正 `wiki_context.pages_used.page_path`
- hybrid 模式下对 wiki / library / pdf 结果做更稳健的合并
- 避免把 library top-k 与 pdf top-k 简单并列暴露而不做约束

4. `src/miniresearch/mcp_server.py`
- `search_wiki` 输出结构同步真实 `page_path`
- 统一暴露新增 metadata，便于前端或调用方观察检索命中来源
- 检查 truth-value 判断，避免与 embedding array 相关的类似问题重复出现

5. `src/miniresearch/vector_store.py`
- 必须新增 wiki-page 级定向删除 helper
- 推荐至少提供：
  - 按精确 `page_path` 删除
  - 按 `page_path` 前缀删除（用于 `queries/` 这类目录级清理）
  - 返回删除 chunk 数，便于验证
- 删除后确保 BM25 状态失效并重建
- 如有必要，可补一个按 metadata 条件收集 chunk ids 的通用 helper，作为后续局部更新基础设施

### 建议新增测试文件

6. `tests/test_wiki_retrieval_quality.py`
建议集中覆盖：
- `log.md` / `index.md` 不被索引
- `queries/` 是否按预期排除或纳入
- frontmatter 会被剥离
- `section 0` 文本不含 YAML 块
- router 返回真实 `page_path`
- wiki 结果 page-level 去重
- hybrid / pdf 结果 item-level 去重

### 可选新增参考文档

6. `references/retrieval-quality-optimization.md`
记录：
- 设计动机
- 规则解释
- 为什么 v1 先不做 cross-encoder
- 后续可以如何演进到可学习排序

---

## 5. Step-by-step implementation plan

## Phase 1: 先修最确定、收益最大的 P0/P1

### Task 1: 为 wiki indexing 增加页面准入规则
**Objective:** 防止 `log.md` / `index.md` / 非知识页进入 wiki collection，并为旧脏向量清理提供明确目标集合。

**Files:**
- Modify: `scripts/build_index.py`
- Test: `tests/test_wiki_retrieval_quality.py`

**Planned changes:**
- 新增 `_should_index_wiki_page(md_file, wiki_root)` helper
- 规则至少覆盖：
  - 排除 `wiki/log.md`
  - 排除 `wiki/index.md`
  - 默认排除 `wiki/queries/**`
  - 仅纳入白名单目录中的 markdown

**Validation target:**
- 构造临时 wiki 目录，包含 `papers/a.md`、`topics/b.md`、`log.md`、`index.md`、`queries/q.md`
- 索引后断言仅知识页相关 chunks 进入 store

### Task 2: 加入 frontmatter stripping 和结构化切块
**Objective:** 减少 section 0 元数据噪音，提高 chunk 信息密度。

**Files:**
- Modify: `scripts/build_index.py`
- Test: `tests/test_wiki_retrieval_quality.py`

**Planned changes:**
- 新增 `_split_frontmatter()` 或 `_strip_frontmatter()` helper
- 新增 `_iter_wiki_sections()` helper，返回结构化 section rows
- metadata 中新增：
  - `page_type`
  - `section`
  - `page_path`
  - `title`
  - 可选 `section_heading`

**Validation target:**
- 含 YAML frontmatter 的测试页被切块后，section 0 文本不含 `---`、`title:` 等 YAML 内容
- 总 section 数稳定，可重复索引

### Task 3: 修正 `_load_env()` 的覆盖逻辑
**Objective:** 避免 filters / ad-hoc retrieval 读取到脏环境变量而连到错误 collection 或错误 embedding 配置。

**Files:**
- Modify: `src/miniresearch/filters.py`
- Test: 可放入 `tests/test_config.py` 或 `tests/test_wiki_retrieval_quality.py`

**Planned changes:**
- 将：
  - `if val and not os.environ.get(key.strip()): ...`
- 改为：
  - `if val: os.environ[key.strip()] = val.strip()`

**Reason:**
这一点与你在项目中已确认的 `.env` 覆盖原则保持一致，避免检索验证阶段读取错误 provider/model。

### Task 3b: 先补 wiki 向量的定向删除能力，再清理当前噪音向量
**Objective:** 先让系统具备“删除指定 wiki 页面对应向量”的正式能力，再用这项能力把 `log.md` / `index.md` / 可选 `queries` 对应 chunks 清掉；避免把全量重建误当成长期维护方案。

**Files:**
- Modify: `src/miniresearch/vector_store.py`
- Modify: `scripts/build_index.py`
- Test: `tests/test_wiki_retrieval_quality.py`

**Planned changes:**
- 在 `VectorStore` 中新增 wiki 定向删除 helper，至少支持：
  - 按精确 `page_path` 删除
  - 按 `page_path` 前缀删除
  - 返回删除 chunk 数
- 删除后显式使 BM25 失效，并重建 BM25
- 在 `build_index.py` 或配套维护入口中接入该能力，用于清理当前 collection 中的历史噪音页向量
- 全量重建只保留为兜底方案，不作为默认修复路径

**Validation target:**
- 构造混合 collection：同时含合法知识页和 `log.md` / `index.md` / `queries` chunks
- 定向删除后：
  - 噪音页 chunks 数降为 0
  - 合法知识页 chunks 仍保留
  - BM25 可正常重建
- 查询结果中不再出现被删除页面

---

## Phase 2: 修正输出可解释性与基础重排

### Task 4: router 返回真实 `page_path`
**Objective:** 让 `wiki_context.pages_used` 可直接定位真实文件。

**Files:**
- Modify: `src/miniresearch/router.py`
- Test: `tests/test_wiki_retrieval_quality.py`

**Planned changes:**
- 将 `page_path: w["id"]` 改为优先读取 `w["metadata"]["page_path"]`
- 若 metadata 缺失，再退回 chunk id
- 建议同步返回 `section`、`page_type`

**Validation target:**
- mock `vector_search()` 返回 metadata 后，`ask_research()` 输出中的 `page_path` 等于真实文件路径，而非 `papers__xxx.md_s2`

### Task 5: 在 wiki 检索结果中增加双保险过滤与轻量重排
**Objective:** 即使用户暂未重建 wiki collection，也能降低历史噪音对结果的污染。

**Files:**
- Modify: `src/miniresearch/filters.py`
- Possibly modify: `src/miniresearch/mcp_server.py`
- Test: `tests/test_wiki_retrieval_quality.py`

**Planned changes:**
- 为 `vector_search(collection="wiki")` 增加后处理 helper，例如 `_postprocess_wiki_results()`
- 规则：
  - 若 `page_path` 命中 `log.md` / `index.md`，直接过滤
  - 对 `section == 0` 施加轻惩罚
  - 对同页多 chunk 命中做去重或限额

**Tradeoff:**
- 这是规则法，不是学习排序；但工程风险小、收益较确定。

---

## Phase 3: 优化 hybrid / pdf 旁路召回

### Task 6: 对 pdf chunk 结果做 item-level 聚合与限流
**Objective:** 减少单一 query 中混入过多“语义相近但非目标文献”的 chunks。

**Files:**
- Modify: `src/miniresearch/filters.py`
- Modify: `src/miniresearch/router.py`
- Test: `tests/test_wiki_retrieval_quality.py`

**Planned changes:**
- 新增 `_dedupe_pdf_chunks_by_item()` helper
- 同一 `item_key` 最多保留前 1-2 个 chunk
- 当 library metadata 有高分命中时：
  - 以 library top candidate 的 `doc_id` 作为软约束
  - 不强制过滤，但可对候选集外结果降权

**Heuristic suggestion:**
- 若 query 命中标题词、作者名、中文实体词较多，则提高 lexical prior
- 若 query 是方法/机制细节类，则允许保留更多语义相近 chunk

### Task 7: 调整 `ask_research()` 的合并逻辑
**Objective:** 让 hybrid 输出更像“wiki 为主、pdf 为证据”，而不是三个独立结果堆叠。

**Files:**
- Modify: `src/miniresearch/router.py`
- Test: `tests/test_wiki_retrieval_quality.py`

**Planned changes:**
- 先取 wiki 高分页作为主题锚点
- 再从 library/pdf 中补充证据
- 输出时分清：
  - `wiki_context.pages_used`
  - `pdf_context.docs_used`
  - `pdf_context.evidence_snippets`
- 避免 library top-k 和 pdf top-k 都机械截断到 5 后直接拼接

---

## Phase 4: 回归测试与验收基准

### Task 8: 增补检索质量测试
**Objective:** 为本轮优化建立可重复回归的最小测试基线。

**Files:**
- Create: `tests/test_wiki_retrieval_quality.py`

**Suggested test cases:**
1. `test_index_wiki_excludes_log_index_and_queries_by_default`
2. `test_index_wiki_strips_yaml_frontmatter_before_chunking`
3. `test_ask_research_returns_real_page_path_not_chunk_id`
4. `test_vector_search_filters_noise_pages_even_before_rebuild`
5. `test_vector_search_limits_duplicate_sections_from_same_page`
6. `test_hybrid_pdf_results_are_deduped_by_item_key`
7. `test_vector_store_can_delete_wiki_chunks_by_exact_page_path`
8. `test_vector_store_can_delete_wiki_chunks_by_page_path_prefix`
9. `test_wiki_noise_vectors_are_deleted_from_current_collection_without_removing_valid_pages`

### Task 9: 建立人工验收 query 集
**Objective:** 用固定 query 对比优化前后效果，而不是只看单次偶然命中。

**Files:**
- Optional create: `references/retrieval-quality-optimization.md`
- Optional create: `tmp/retrieval_eval_queries.md` 或其他非正式记录文件

**Recommended query set:**
- 精确题名类：如具体中文题名 / 明确术语组合
- 方法细节类：DiD、识别策略、样本构造、稳健性检验
- 实体类：企业传承、职业经理人、企业家后代
- 综述类：某主题的机制、异质性、研究脉络

**Acceptance criteria:**
- wiki top-3 中不再出现 `log.md` / `index.md`
- `pages_used.page_path` 返回真实文件路径
- section 0 的 YAML frontmatter 不再成为高频高位命中
- hybrid 下 PDF 侧结果混入无关文献的比例有所下降

---

## 6. Recommended implementation order

建议按以下顺序执行：

1. `scripts/build_index.py`：排除噪音页
2. `scripts/build_index.py`：frontmatter stripping + 结构化切块
3. `src/miniresearch/filters.py`：修 `_load_env()`
4. `src/miniresearch/vector_store.py`：先补 wiki 向量定向删除能力
5. 用该能力清理当前 wiki collection 中的历史噪音向量
6. `src/miniresearch/router.py`：修真实 `page_path`
7. `src/miniresearch/filters.py`：wiki 结果后处理
8. `src/miniresearch/router.py` + `filters.py`：pdf/hybrid 去重与轻量重排
9. 新增完整测试
10. 用固定 query 集做人工验收

原因：
- 前 6 步属于确定性修复，风险低、收益高；
- 第 4-5 步不是附属清理，而是补足向量库生命周期管理能力；
- 后 2 步属于质量增强，需要在前面“输入更干净、脏数据可控”后再做，效果更容易判断。

---

## 7. Tests and verification

### Unit / integration tests
建议最终运行：
- `python3 -m pytest tests/test_incremental_index.py -v`
- `python3 -m pytest tests/test_mcp_backend.py -v`
- `python3 -m pytest tests/test_wiki_retrieval_quality.py -v`
- `python3 -m pytest tests/ -v`

### Reindex validation
在实现完成后，需要至少做一次 wiki collection 重建验证：
- 确认新 collection 中不再包含 `log.md` / `index.md`
- 确认 metadata 带有真实 `page_path`
- 确认 section 数变化符合预期
- 但更关键的是：确认系统已经具备“按指定 `page_path` / 前缀定向删除向量”的正式能力，而不是只能靠重建掩盖问题

### Retrieval acceptance validation
用一组固定 query 比较优化前后：
- Top-k 是否仍被日志页污染
- 中文实体 query 是否更稳定命中知识页
- 方法细节 query 的 top wiki chunk 是否信息密度更高
- hybrid 中无关 PDF 旁路是否减少

---

## 8. Risks and tradeoffs

### Risk 1: 排除 `queries/` 可能损失部分有价值的总结页
这是真实 tradeoff。
建议 v1 先默认排除 `queries/`，因为当前用户反馈表明“纯度问题”比“召回不足”更突出。
后续可改成：
- 默认不索引 queries
- 提供 CLI 参数 `--include-queries`
- 或单独建 query collection

### Risk 2: 仅靠规则重排不能完全解决语义近邻误召回
是的，但当前问题更像数据清洁和简单后处理不足，而不是必须上复杂 reranker。
建议先做规则法，再观察是否仍有明显误召回残留。

### Risk 3: section 0 惩罚过强可能压掉真实高质量摘要
因此不建议直接删掉 section 0。
更稳妥的做法是：
- 先去 frontmatter
- 再轻惩罚，而不是硬过滤

### Risk 4: 旧 collection 不重建时，索引修复不会自动生效
因此需要“双保险”：
- 新索引逻辑修复输入
- 检索后处理先过滤历史噪音
- 更重要的是，补齐定向删除能力，真正移除历史脏向量

### Risk 5: 如果把“全量重建”当成默认修复路径，会掩盖向量生命周期设计缺陷
这是你这次特别指出的核心问题。
若系统不能删除指定页面的向量，则后续任何局部回滚、页面撤回、目录重构、误写入修复都会变得脆弱。
因此 v1 必须把“可定向删除”纳入正式能力，而不是作为可选增强项。

---

## 9. Open questions

1. `wiki/queries/` 是否应彻底排除，还是仅在 `ask_research()` 中降权？
2. `index.md` 是否完全不应索引，还是保留在单独 collection 更合适？
3. `section 0` 的最优策略是“轻惩罚”还是“仅当文本过短时过滤”？
4. hybrid 中 library metadata 是否应参与最终排序分数，而不仅是展示？
5. 是否需要把“页面类型”写进 frontmatter 之外的 vector metadata，作为长期稳定特征？

---

## 10. Practical recommendation

如果目标是“尽快把检索纯度拉回可用水平”，建议分两轮：

### Round 1: 快速止噪
- 排除 `log.md` / `index.md` / 默认排除 `queries/`
- strip frontmatter
- 修 `page_path`
- 先补定向删除能力，再清理当前 wiki collection 中对应的历史噪音向量
- wiki 检索后处理双保险

这轮预计就能显著减少你已经观察到的主要噪音。

### Round 2: 提高 hybrid 质量
- pdf chunk 按 `item_key` 聚合
- library metadata 引入软约束
- 调整 hybrid merge 逻辑
- 建立固定 query 验收集

这轮更偏“质量打磨”，适合在 Round 1 验证后继续推进。

---

## 11. Likely files to change

- `/mnt/d/pyproject/paper-compass/scripts/build_index.py`
- `/mnt/d/pyproject/paper-compass/src/miniresearch/filters.py`
- `/mnt/d/pyproject/paper-compass/src/miniresearch/router.py`
- `/mnt/d/pyproject/paper-compass/src/miniresearch/mcp_server.py`
- `/mnt/d/pyproject/paper-compass/src/miniresearch/vector_store.py`
- `/mnt/d/pyproject/paper-compass/tests/test_wiki_retrieval_quality.py`
- 可选：`/mnt/d/pyproject/paper-compass/references/retrieval-quality-optimization.md`

---

## 12. Definition of done

当满足以下条件时，可认为本轮优化基本完成：

1. 新 wiki index 不再收录 `log.md` / `index.md`，并默认不收录 `queries/`
2. section 0 不再包含 YAML frontmatter
3. `ask_research()` 和 `search_wiki` 返回真实 `page_path`
4. 系统已具备按指定 `page_path` / 前缀定向删除 wiki 向量的正式能力
5. 当前向量库中历史写入的 `log.md` / `index.md` 对应向量已通过该能力被实际删除
6. wiki top-k 结果不再被日志页污染
7. hybrid 中 pdf 侧无关文献混入现象有所减少
8. 有新增测试覆盖上述关键行为
9. 用固定 query 集做过一次优化前后对比验收
