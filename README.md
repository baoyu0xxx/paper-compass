# paper-compass

个人学术论文检索与知识导航基础设施。

目标：
- 读取 /mnt/d/zotero_backup 下的 Zotero 文献与附件
- 用 zotero_readonly.sqlite + 目录扫描生成统一中间层
- 用 PaperQA 做 PDF 深度检索
- 用本地 markdown wiki 做广度检索与知识沉淀
- 通过 MCP tools 暴露给 Hermes 等 agent 使用

当前设计重点：
1. Zotero 数据源
   - PDF 根目录：`/mnt/d/zotero_backup`
   - 只读数据库：`/mnt/d/zotero_backup/zotero_readonly.sqlite`
   - 目录扫描作为兜底，sqlite 作为 metadata 增强主线

2. Provider 分层
   - Wiki 生成模型：Mimo API
   - PDF / Wiki embedding：国内在线 embedding 服务（预留火山云）
   - PaperQA 负责 PDF 级索引与检索

3. Hermes 专用 profile
   - Profile 名称：`papercompass`（原名 `zoteroragmcp`，2026-05-08 重命名）
   - 已设置项目 cwd 到本仓库

目录说明：
- `configs/`：项目配置样例
- `docs/plans/`：整理后的规划文档
- `scripts/`：后续 CLI 入口
- `src/miniresearch/`：后续实现代码
- `wiki/`：本地知识库
- `data/zotero-export/`：manifest/library 输出目录

当前状态：
- 本地 git 仓库已初始化
- 项目骨架已建立
- 规划文档已整理入仓库
- GitHub 远程仓库创建待认证后完成

v1.5 已完成的关键优化（进行中迭代）：
- MCP 工具契约集中到 `src/miniresearch/mcp_contracts.py`，`tools/list` 与 handler 参数统一
- `save_to_wiki` 支持显式 `wiki_root` 参数
- MCP 错误响应统一为 `ok/tool/trace_id/warnings/next_suggested_action`
- 新增轻量 trace 日志（JSONL）：`src/miniresearch/logging.py` + `configs/mcp.yaml` 的 `mcp.trace`
- `search_library` 增加 exact-match tier（key/doi/title）与加权排序，降低弱匹配噪声

相关文档：
- `docs/mcp/tool-contracts.md`
- `docs/workflows/trace-inspection.md`
