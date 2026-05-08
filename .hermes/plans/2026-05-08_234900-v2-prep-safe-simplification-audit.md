# paper-compass v2 前的安全简化计划

> For Hermes: this is a planning-only artifact. If later entering execution, prefer small, reviewable refactors with behavior-preserving tests after each step.

Goal
- 在进入 v2 构建前，对当前 v1.5 代码做一轮“保守型简化”：清理明显重复的判断、重复的辅助逻辑与可抽取的共用代码，同时尽量不改变对外行为、数据流与现有检索/索引语义。

Current context / assumptions
- Active repo: `/mnt/d/pyproject/paper-compass`
- Current branch / base commit inspected: `main @ 4c644ab`
- 当前仓库已有一批未提交修改，因此本轮计划应按“最小行为面”推进，避免大范围重写。
- 已做只读检查的重点文件：
  - `src/miniresearch/mcp_server.py`
  - `src/miniresearch/router.py`
  - `src/miniresearch/filters.py`
  - `src/miniresearch/vector_store.py`
  - `scripts/build_index.py`
  - `src/miniresearch/mcp_contracts.py`
  - 相关测试文件
- 外部子审查结果（只读）显示：若聚焦重复逻辑与冗余判断，可优先从 env 加载、索引批处理、MCP 参数校验、BM25 失效处理、结果去重 helper 几处下手。
- 相关 targeted tests 在只读审查中曾跑通：
  - `python3 -m pytest tests/test_incremental_index.py tests/test_mcp_backend.py tests/test_mcp_contract.py tests/test_wiki_retrieval_quality.py -q`
  - 结果记录为 33 passed

Why now
- 当前代码已经具备 v1.5 基本能力，但部分实现存在“双份真相”或重复流程。
- 若直接进入 v2，新功能很可能继续叠加在这些重复层之上，后续维护成本会较快上升。
- 这轮简化的目标不是“重构得更漂亮”，而是先降低后续 v2 叠加时的摩擦。

Proposed approach
- 采用“低风险、强可验证、一次只动一类重复逻辑”的顺序推进。
- 每一类简化都遵循：
  1. 先补测试或确认现有测试覆盖该行为
  2. 再抽取/合并重复逻辑
  3. 立即跑对应最小测试集
  4. 通过后再进入下一类
- 暂不处理收益小、风险高的“深层重写”（如 router 回答组装的整体范式调整、wiki 生成解析器的大改）。

---

## Phase 0: 建立简化边界

Objective
- 先明确“这轮可以动什么、不动什么”，避免简化演变成 v2 提前开发。

Files
- Review only:
  - `src/miniresearch/mcp_server.py`
  - `src/miniresearch/filters.py`
  - `src/miniresearch/vector_store.py`
  - `scripts/build_index.py`
  - `src/miniresearch/wiki_store.py`
  - `tests/test_incremental_index.py`
  - `tests/test_mcp_backend.py`
  - `tests/test_mcp_contract.py`
  - `tests/test_wiki_retrieval_quality.py`

Plan steps
1. 列出本轮允许的改动类型：重复 helper 抽取、重复判断合并、测试辅助代码复用、无行为变化的命名/结构整理。
2. 列出本轮明确非目标：
   - 不改变检索策略语义
   - 不改变向量库 schema
   - 不引入新 provider / 新 router 模式
   - 不做大规模目录搬迁
3. 记录每个候选点对应的“保护测试”。

Validation
- 人工检查计划边界是否清晰。
- 后续每一阶段都必须能映射到至少一个现有测试文件或新增最小测试。

---

## Phase 1: 合并重复的 `.env` 加载逻辑

Objective
- 去掉多处几乎相同的 `_load_env()` 实现，保留“始终覆盖 os.environ”的既有正确语义。

High-confidence candidate
- 重复位置：
  - `src/miniresearch/filters.py:29`
  - `scripts/build_index.py:143`
  - `scripts/ingest_to_wiki.py`（审查已确认也有近似实现）

Likely change shape
- 新增一个共享 helper（例如放在 `src/miniresearch/...` 公共模块中）
- 脚本与库代码都调用它
- 保留当前路径解析语义，不因抽取而改变 repo root 的定位方式

Files likely to change
- Modify:
  - `src/miniresearch/filters.py`
  - `scripts/build_index.py`
  - `scripts/ingest_to_wiki.py`
- Create or modify:
  - `src/miniresearch/<shared_env_module>.py`（具体名称执行时确定）
- Test:
  - 可新增 `tests/test_env_loading.py`，或并入现有相关测试文件

Exact verification targets
- `python3 -m pytest tests/test_incremental_index.py -q`
- `python3 -m pytest tests/test_wiki_retrieval_quality.py -q`
- 如新增 env 单测：`python3 -m pytest tests/test_env_loading.py -q`

Key assertions to preserve
- `.env` 中的值会覆盖已有脏环境变量
- 缺失 `.env` 时为 no-op
- 注释、空行不会破坏解析

Risk / caveat
- 这里最容易出问题的是路径解析，而不是逻辑本身；抽取时不能把脚本调用场景和库调用场景混成一个错误的相对路径基准。

---

## Phase 2: 抽取索引阶段共同的“批量 embed + 写入”流程

Objective
- 去掉 `scripts/build_index.py` 中 papers/wiki 两条路径的重复 batch 流程，但保留二者不同的写入语义。

High-confidence candidate
- 重复流程：
  - 累积 `chunk_ids/chunk_texts/chunk_metas`
  - 按 32 切 batch
  - `embedder.embed(batch_texts)`
  - 写入 store
- 当前位置：
  - `_index_single_paper()`
  - `index_wiki()`

Files likely to change
- Modify:
  - `scripts/build_index.py`
- Test:
  - `tests/test_incremental_index.py`
  - `tests/test_wiki_retrieval_quality.py`

Required behavioral split
- papers 路径：保持 `add` 语义，仍依赖 changed/full-rebuild 前的 delete
- wiki 路径：保持 `upsert` 语义，继续支持幂等重建

Step-by-step plan
1. 先把“批量写入”的共同接口设计成只抽取 batch 处理，不碰上游 chunk 生成逻辑。
2. 让 helper 通过参数决定写入模式（add/upsert），不要在 helper 内写死业务分支。
3. 保留当前 progress 输出节奏，避免影响长任务可观测性。
4. 跑 paper 与 wiki 相关测试，确认 chunk 数与行为未变。

Exact verification targets
- `python3 -m pytest tests/test_incremental_index.py -q`
- `python3 -m pytest tests/test_wiki_retrieval_quality.py -q`

Risk / caveat
- 这里不应顺手重写 chunk 组织逻辑；否则“简化”容易变成“重新设计索引管线”。

---

## Phase 3: 消除 MCP 参数校验中的“双份真相”

Objective
- 让 `required` 参数约束真正以 `mcp_contracts.py` 为单一来源，移除 `handle_tool()` 中按 tool 名字手写的重复判断链。

High-confidence candidate
- 当前重复：
  - `src/miniresearch/mcp_contracts.py` 已声明 `inputSchema.required`
  - `src/miniresearch/mcp_server.py:214-226` 又手写了一遍 required 校验

Files likely to change
- Modify:
  - `src/miniresearch/mcp_server.py`
  - `src/miniresearch/mcp_contracts.py`（可能仅增加读取 helper）
- Test:
  - `tests/test_mcp_contract.py`
  - `tests/test_mcp_backend.py`

Step-by-step plan
1. 在 contract 层提供读取 required 字段的 helper。
2. `handle_tool()` 只消费 schema，不再按 tool 名称写 if-chain。
3. 保持当前 normalized error payload 与 trace emission 行为不变。
4. 为“contract required 改动后 handler 自动跟随”补一条测试。

Exact verification targets
- `python3 -m pytest tests/test_mcp_contract.py -q`
- `python3 -m pytest tests/test_mcp_backend.py -q`

Risk / caveat
- 风险不在功能本身，而在错误消息格式；如果错误结构变了，现有 MCP 使用方可能受影响。

---

## Phase 4: 抽取 VectorStore 的 BM25 失效逻辑

Objective
- 去掉 mutating 操作后重复出现的 BM25 cache reset 代码块。

High-confidence candidate
- 重复位置：
  - `clear()`
  - `delete_item()`
  - `delete_by_page_path()`
  - `delete_by_page_path_prefix()`
- 当前重复内容均为 `_bm25_index/_bm25_corpus/_bm25_ids` 三项重置

Files likely to change
- Modify:
  - `src/miniresearch/vector_store.py`
- Test:
  - `tests/test_wiki_retrieval_quality.py`
  - 如需要新增 `tests/test_vector_store.py`

Step-by-step plan
1. 提供私有 helper（如 `_invalidate_bm25()`）。
2. 所有 mutating delete/clear 路径统一调用该 helper。
3. 检查是否有其他写路径也应统一触发失效逻辑。

Exact verification targets
- `python3 -m pytest tests/test_wiki_retrieval_quality.py -q`
- 如新增单测：`python3 -m pytest tests/test_vector_store.py -q`

Risk / caveat
- 风险较低，但要注意未来新增 mutator 也必须接入这个 helper，避免产生新分叉。

---

## Phase 5: 只抽取“按 group 限流”的共用后处理，不合并业务规则

Objective
- 在 `filters.py` 中仅抽取共通的“按 key 保留 top-k”模式，不把 wiki 与 PDF 的业务逻辑硬揉在一起。

High-confidence candidate
- 结构相似函数：
  - `_postprocess_wiki_results()`
  - `_dedupe_pdf_chunks_by_item()`
- 共通部分：
  - 先按 score 排序
  - 每个 group 只保留若干条
  - 结果再按 score 排序
- 不共通部分：
  - wiki 需要排除噪音页、section 0 penalty
  - PDF 允许无 `item_key` 条目直接穿透

Files likely to change
- Modify:
  - `src/miniresearch/filters.py`
- Test:
  - `tests/test_wiki_retrieval_quality.py`
  - 如有必要新增更小粒度的 helper 单测

Step-by-step plan
1. 先抽取中性 helper，例如“score-sorted results capped by group key”。
2. 保持 wiki 预处理与 PDF 特例逻辑留在各自函数外层。
3. 只减少结构性重复，不改变任何 score 规则。

Exact verification targets
- `python3 -m pytest tests/test_wiki_retrieval_quality.py -q`

Risk / caveat
- 这里最容易“过抽象”；如果 helper 需要承载太多 wiki 特例，宁可不合并。

---

## Phase 6: 评估 `_tool_search_wiki()` 与 `vector_search()` 的复用边界

Objective
- 这是本轮最值得做、但也相对更应克制的一项：尝试只复用“底层检索准备逻辑”，不改 MCP 返回结构。

Observation
- `src/miniresearch/mcp_server.py::_tool_search_wiki()` 与 `src/miniresearch/filters.py::vector_search()` 都在重复做：
  - collection discovery
  - sample embedding dimension probe
  - embedder 初始化
  - query 执行
  - score 转换
- 但二者输出形状不同，`_tool_search_wiki()` 还负责 snippet 与 response envelope。

Files likely to change
- Modify:
  - `src/miniresearch/mcp_server.py`
  - `src/miniresearch/filters.py`
  - 可能涉及 `src/miniresearch/vector_store.py`
- Test:
  - `tests/test_mcp_backend.py`
  - `tests/test_wiki_retrieval_quality.py`

Plan steps
1. 先判断是否能仅抽取“collection + embedder discovery / query helper”。
2. 若无法在不增加复杂度的前提下复用，则暂缓，不把它纳入本轮必须项。
3. 若可复用，确保 MCP 层仍单独负责字段整形：`page_path/title/page_type/section/snippet/score`。

Exact verification targets
- `python3 -m pytest tests/test_mcp_backend.py -q`
- `python3 -m pytest tests/test_wiki_retrieval_quality.py -q`

Risk / caveat
- 这是本轮候选中相对更容易引入回归的一项。建议把它放在后面，前几项都稳定后再决定是否执行。

---

## Phase 7: 清理低风险死参数与测试样板重复

Objective
- 收尾处理收益较小但噪音明显的点。

Candidate A: 未使用参数
- `src/miniresearch/wiki_store.py::_generate_filename(title, target_type)` 中 `target_type` 疑似未使用。
- 若确认确为死参数，可删除或加注释说明其保留原因。

Candidate B: 测试辅助重复
- `tests/test_incremental_index.py` 与 `tests/test_wiki_retrieval_quality.py` 中存在近似的 fake embedder / fake store / args helper。
- 可抽到共享 test helper，降低后续维护成本。

Files likely to change
- Modify:
  - `src/miniresearch/wiki_store.py`
  - `tests/test_incremental_index.py`
  - `tests/test_wiki_retrieval_quality.py`
- Create:
  - `tests/helpers/...`（若执行时认为值得）

Exact verification targets
- `python3 -m pytest tests/test_incremental_index.py tests/test_wiki_retrieval_quality.py -q`

Risk / caveat
- 这部分不是进入 v2 的阻塞项；若前面阶段已达到“足够干净”，可以延后。

---

## Prioritized execution order

P0（优先做）
1. Phase 1: 统一 `.env` loader
2. Phase 3: MCP schema-driven required validation
3. Phase 4: VectorStore BM25 invalidation helper

P1（建议做）
4. Phase 2: build_index 批量 embed/write helper
5. Phase 5: filters 中 group-cap helper

P2（可选做）
6. Phase 6: `_tool_search_wiki()` 与 `vector_search()` 底层复用
7. Phase 7: 死参数与测试脚手架清理

Files most likely to change overall
- `/mnt/d/pyproject/paper-compass/src/miniresearch/filters.py`
- `/mnt/d/pyproject/paper-compass/src/miniresearch/mcp_server.py`
- `/mnt/d/pyproject/paper-compass/src/miniresearch/mcp_contracts.py`
- `/mnt/d/pyproject/paper-compass/src/miniresearch/vector_store.py`
- `/mnt/d/pyproject/paper-compass/scripts/build_index.py`
- `/mnt/d/pyproject/paper-compass/scripts/ingest_to_wiki.py`
- `/mnt/d/pyproject/paper-compass/src/miniresearch/wiki_store.py`
- `/mnt/d/pyproject/paper-compass/tests/test_incremental_index.py`
- `/mnt/d/pyproject/paper-compass/tests/test_mcp_backend.py`
- `/mnt/d/pyproject/paper-compass/tests/test_mcp_contract.py`
- `/mnt/d/pyproject/paper-compass/tests/test_wiki_retrieval_quality.py`

Recommended validation matrix
- Fast targeted suite after each phase:
  - `python3 -m pytest tests/test_incremental_index.py -q`
  - `python3 -m pytest tests/test_mcp_contract.py -q`
  - `python3 -m pytest tests/test_mcp_backend.py -q`
  - `python3 -m pytest tests/test_wiki_retrieval_quality.py -q`
- Broader integration check at the end:
  - `python3 -m pytest tests/test_incremental_index.py tests/test_mcp_backend.py tests/test_mcp_contract.py tests/test_wiki_retrieval_quality.py -q`
- If all targeted simplifications land cleanly, then run:
  - `python3 -m pytest tests/ -v`

Non-goals
- 不在本轮把 `ask_research()` 改造成更强的答案综合器
- 不改 wiki 向量 schema / Chroma collection 设计
- 不做 v2 feature 开发（例如新检索器、新评测框架、新路由层）
- 不碰 deep-zotero-opt 相关替换策略

Risks / tradeoffs
- 优点：先清理重复逻辑，后续 v2 叠加更稳，测试维护成本也较低。
- 代价：短期内会有少量“代码搬家但行为不变”的工作，产出较偏基础设施，不直接带来新功能。
- 主要风险：
  - env loader 抽取时误改路径基准
  - MCP 参数校验重构时改变错误结构
  - 过度抽象 helper，反而降低可读性

Open questions
1. 本轮是否只做 P0，还是希望我把 P1 也纳入同一波执行？
2. 对于 Phase 6（MCP wiki search 与 vector_search 复用），你的偏好是“能不动就不动”，还是希望我顺手尽量压缩重复？
3. 当前工作区已有未提交修改；执行时是否需要我先按阶段拆成更细的 patch 计划，避免与现有改动混在一起？

Suggested next step
- 若你认可这份路线，下一步最稳妥的是先执行 P0 三项，并在每一项后立即跑对应 targeted tests；通过后再决定是否进入 P1。