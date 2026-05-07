# MCP Tools Schema 详细设计

> **For Hermes:** Use subagent-driven-development skill to implement this plan task-by-task.

**Goal:** 为最小化论文检索系统定义一套适合 agent 调用的 MCP tools schema。设计目标不是做一个大而全的 API，而是在尽量少的工具数量下，覆盖最核心的研究动作：查 wiki、查文献库、做多层问答、取单篇元数据、把高价值结果写回 wiki。

**Architecture:** MCP 层只暴露薄工具，不直接暴露底层实现细节。工具按“广度检索 → 深度检索 → 写回沉淀”的路径组织。统一要求：输入结构化、输出结构化、包含 mode/source/confidence/trace_id，便于 Hermes 等 agent 自主编排。

**Tech Stack:** MCP server, JSON-serializable payloads, local Python backend, wiki + library.json + PaperQA.

---

## 1. 设计原则

### 1.1 工具数量尽量少
一期建议只暴露 5 个工具：
1. `search_wiki`
2. `search_library`
3. `ask_research`
4. `get_paper_metadata`
5. `save_to_wiki`

### 1.2 工具边界清楚
- `search_*` 只负责检索候选；
- `ask_research` 负责多层路由与联合回答；
- `get_paper_metadata` 负责单篇结构化信息；
- `save_to_wiki` 负责沉淀。

### 1.3 输出必须适合 agent 消费
每个 tool 返回内容都不应只是自由文本，而应有稳定字段。

### 1.4 不让 agent 背负实现细节
agent 不应关心底层是 PaperQA 还是 markdown search，只需要看到：
- 用了什么 mode
- 来源是什么
- 可信度如何
- 下一步建议做什么

---

## 2. 全局返回 schema

建议所有工具统一返回如下外层结构：

```json
{
  "ok": true,
  "tool": "search_wiki",
  "trace_id": "uuid-or-timestamp-id",
  "mode_used": "wiki | pdf | hybrid | writeback",
  "confidence": "high | medium | low",
  "data": {...},
  "sources": [...],
  "warnings": [],
  "next_suggested_action": "optional string"
}
```

### 字段说明
- `ok`: 是否成功
- `tool`: 当前工具名
- `trace_id`: 用于日志追踪
- `mode_used`: 当前使用了哪种检索/处理模式
- `confidence`: 当前结果的粗粒度置信度
- `data`: 主要结果对象
- `sources`: 来源列表
- `warnings`: 警告信息
- `next_suggested_action`: 建议 agent 下一步做什么

---

## 3. Tool 1：`search_wiki`

## 3.1 用途
在本地 wiki 中做广度检索，适用于：
- 回忆某主题的已有知识
- 查已有主题页/方法页/比较页
- 给后续深检索提供起点

## 3.2 输入 schema
```json
{
  "query": "string",
  "limit": 5,
  "page_types": ["topics", "methods", "queries", "comparisons"],
  "return_snippets": true
}
```

### 字段说明
- `query`: 检索词或问题
- `limit`: 返回条数，默认 5
- `page_types`: 可选限制页面类别
- `return_snippets`: 是否返回摘要片段

## 3.3 输出 schema
```json
{
  "matches": [
    {
      "page_path": "wiki/topics/did.md",
      "title": "Difference-in-Differences",
      "page_type": "topics",
      "summary": "...",
      "snippet": "...",
      "score": 0.84
    }
  ],
  "query_interpretation": "broad wiki lookup"
}
```

## 3.4 sources 字段
对 `search_wiki`，sources 建议返回命中的 wiki 页面路径列表。

## 3.5 next action 建议
- 若匹配很弱：建议 `ask_research` 或 `search_library`
- 若匹配很强：建议先读相关主题页

---

## 4. Tool 2：`search_library`

## 4.1 用途
在导出的文献元数据层中搜索候选文献，而不是直接生成最终答案。

适用于：
- 找某主题有哪些论文
- 找某作者/年份/collection/tag 下的论文
- 为 `ask_research` 缩小候选范围

## 4.2 输入 schema
```json
{
  "query": "string",
  "filters": {
    "collections": ["family_firm"],
    "tags": ["did"],
    "authors": ["Zhang"],
    "year_from": 2018,
    "year_to": 2024
  },
  "limit": 10,
  "sort_by": "relevance"
}
```

## 4.3 输出 schema
```json
{
  "matches": [
    {
      "doc_id": "...",
      "title": "...",
      "authors": ["..."],
      "year": 2022,
      "doi": "...",
      "collections": ["..."],
      "tags": ["..."],
      "pdf_path": "/mnt/d/zotero_backup/...pdf",
      "score": 0.79
    }
  ],
  "filters_used": {
    "collections": ["family_firm"]
  }
}
```

## 4.4 设计说明
- 这是 metadata 层搜索，不必调用全文 RAG。
- 一期可用简单关键词 + metadata filter 即可。
- 若后续要增强，可加入 embedding 或 BM25。

## 4.5 next action 建议
- 若找到候选文献：建议 `ask_research`
- 若候选太多：建议缩窄 filters

---

## 5. Tool 3：`ask_research`

这是最核心的工具。

## 5.1 用途
对研究问题进行多层问答：
- 默认先查 wiki
- 必要时升级到 PDF 深检索
- 返回联合回答

## 5.2 输入 schema
```json
{
  "query": "string",
  "filters": {
    "collections": ["family_firm"],
    "tags": ["did"]
  },
  "force_mode": "auto | wiki | pdf | hybrid",
  "save_candidate": false,
  "max_sources": 5
}
```

### 字段说明
- `query`: 用户问题
- `filters`: 可选文献范围限制
- `force_mode`: 默认 auto；必要时人工强制 wiki/pdf/hybrid
- `save_candidate`: 是否提示该结果适合写回 wiki
- `max_sources`: 最多引用来源数

## 5.3 输出 schema
```json
{
  "answer": "最终回答文本",
  "mode_decision": {
    "requested": "auto",
    "actual": "hybrid",
    "reason": "query asks for methodology detail and wiki confidence is insufficient"
  },
  "wiki_context": {
    "pages_used": [
      {"page_path": "wiki/topics/did.md", "title": "Difference-in-Differences"}
    ],
    "summary": "wiki 层已有认识..."
  },
  "pdf_context": {
    "docs_used": [
      {"doc_id": "...", "title": "...", "year": 2022}
    ],
    "evidence_snippets": [
      {
        "doc_id": "...",
        "citation": "Author (2022)",
        "snippet": "...",
        "page_hint": "p.12"
      }
    ]
  },
  "suggested_writeback": {
    "recommended": true,
    "target_type": "queries",
    "reason": "multi-paper synthesis with reuse value"
  }
}
```

## 5.4 这是为什么要做成一个工具
原因是 agent 最常见需求不是“我只想搜 wiki”，而是“帮我回答这个研究问题”。

把路由逻辑封装进 `ask_research`，可以显著降低 agent 使用复杂度。

## 5.5 mode_decision 设计要求
必须显式告诉 agent：
- 最终用了什么模式
- 为什么用了这个模式

否则 agent 很难决定下一步是否继续追问或写回 wiki。

---

## 6. Tool 4：`get_paper_metadata`

## 6.1 用途
返回单篇论文的结构化信息，用于：
- agent 在搜索后进一步确认文献信息
- 后续构造引用、比较、筛选

## 6.2 输入 schema
```json
{
  "id_or_doi": "string"
}
```

### 允许输入
- `doc_id`
- DOI
- title 精确匹配（一期可选）

## 6.3 输出 schema
```json
{
  "paper": {
    "doc_id": "...",
    "title": "...",
    "authors": ["..."],
    "year": 2022,
    "journal": "...",
    "doi": "...",
    "collections": ["..."],
    "tags": ["..."],
    "pdf_path": "/mnt/d/zotero_backup/...pdf",
    "metadata_source": "external_csv"
  }
}
```

## 6.4 next action 建议
- 若 metadata 完整：建议 `ask_research`
- 若 metadata 较弱：建议用户补充 metadata 来源

---

## 7. Tool 5：`save_to_wiki`

## 7.1 用途
把高价值结果沉淀到 wiki，而不是自动写一切。

## 7.2 输入 schema
```json
{
  "title": "string",
  "content": "string",
  "target_type": "queries | topics | methods | comparisons",
  "source_refs": ["wiki/topics/did.md", "doc_id:abc123"],
  "confidence": "medium"
}
```

## 7.3 输出 schema
```json
{
  "page_path": "wiki/queries/2026-05-07-did-identification.md",
  "created": true,
  "linked_pages": ["wiki/topics/did.md"],
  "log_updated": true,
  "index_updated": true
}
```

## 7.4 写回原则
- 不应默认自动调用；
- 一般由 agent 在判断“结果值得保留”时再调用；
- 只沉淀高价值综合结果。

---

## 8. 统一的 sources 结构建议

所有工具都应尽量返回统一的 source item：

```json
{
  "source_type": "wiki_page | pdf_doc | evidence_snippet",
  "id": "...",
  "title": "...",
  "path": "optional",
  "citation": "optional"
}
```

这样有利于 agent 在不同工具返回之间做统一处理。

---

## 9. 错误返回建议

建议统一错误格式：

```json
{
  "ok": false,
  "tool": "ask_research",
  "trace_id": "...",
  "mode_used": "hybrid",
  "confidence": "low",
  "data": null,
  "sources": [],
  "warnings": ["PaperQA index not found"],
  "next_suggested_action": "Run build_index first"
}
```

---

## 10. 一期不建议暴露的工具

为保持简单，一期不建议增加：
- `build_or_refresh_index`
- `list_collections`
- `trace_claim_to_sources`
- `compare_papers`
- `deep_research`

这些以后都可以补，但最小版不需要。

---

## 11. 验证标准

MCP schema 设计完成后，应满足：
- agent 可仅靠 5 个工具完成主要检索流程；
- 返回结构足够稳定，可串联；
- `ask_research` 能隐藏大部分底层路由复杂度；
- `search_library` 与 `get_paper_metadata` 能支撑较细粒度的检索与筛选；
- `save_to_wiki` 能承接高价值结果沉淀。

---

## 12. 实施顺序建议

建议按以下顺序实现：
1. `get_paper_metadata`
2. `search_library`
3. `search_wiki`
4. `ask_research`
5. `save_to_wiki`

原因是：
- 先把底层查询能力做稳；
- 再做最复杂的联合问答工具；
- 最后再做写回功能。

---

## 13. 结论

对于最小化论文检索系统，MCP 层最重要的不是“工具多”，而是“工具少但边界清楚”。

因此，一期应坚持：
- 5 个工具足够；
- `ask_research` 负责多层逻辑；
- 其余工具负责支撑和沉淀；
- 统一返回 schema，保证 agent 调用稳定。  