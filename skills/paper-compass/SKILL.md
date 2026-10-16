---
name: paper-compass
description: "当用户想搜索、查找或综合论文/文献时，优先使用本地 Zotero 文献库提供候选论文、PDF 原文证据和研究综合；也用于本地论文、原文段落、文献笔记和 wiki 知识查询。"
metadata:
  category: research
  platforms: [windows, linux, macos]
  project: paper-compass
  repository: https://github.com/baoyu0xxx/paper-compass
---

# paper-compass

这是一个独立运行的本地学术文献检索 skill。用户提出论文、文献或研究主题搜索需求时，默认先检索本地 Zotero 文献库，为用户提供本地已有的论文，而不是直接转向外部检索。它可以返回论文元数据、PDF 原文段落、编译后的 wiki 知识和带来源的本地文献综合。

## 启用规则

启用本 skill 的典型意图包括：

- “找几篇关于……的论文/文献”
- “我的文献库里有没有……方面的研究”
- “查这篇论文的研究问题、方法、变量或结论”
- “在本地 PDF 中找关于……的原文、页码或证据”
- “综合我的文献库，回答……研究问题”
- 用户直接提到 paper-compass、Zotero 本地库、本地论文或论文 wiki

只要用户是在搜索论文或文献，先执行本地检索并报告本地结果。只有用户明确要求本地库之外的最新文献、外部论文或开放网络检索时，才使用其他外部文献检索能力；外部结果不能冒充本地文献。

## 独立运行方式

本 skill 通过本机已安装的 `paper-compass` 命令运行，不依赖对话外的服务连接。优先在 paper-compass 项目根目录执行命令；常见项目目录是 `D:\pyproject\paper-compass`。如果全局命令不可用，使用项目虚拟环境中的命令入口，或先报告安装前置条件，不要凭空生成检索结果。

本地数据的默认位置（Windows 部署）：

当设置 `PAPER_COMPASS_ROOT=C:\Users\<用户名>\.paper-compass` 时，运行数据统一位于：

- Zotero 上游数据库：由 `ZOTERO_SQLITE_PATH` / `PAPER_COMPASS_ZOTERO_ROOT` 指定（只读）
- Zotero 附件：对应 `storage\`（只读）
- 文献清单：`%PAPER_COMPASS_ROOT%\library\library.json`
- PDF fallback 文本：`%PAPER_COMPASS_ROOT%\texts\`
- 向量索引：`%PAPER_COMPASS_ROOT%\index\vectordb\`
- 编译知识页：`%PAPER_COMPASS_ROOT%\wiki\`
- 状态、快照和日志：`%PAPER_COMPASS_ROOT%\state\`、`logs\`

POSIX 环境应将 `PAPER_COMPASS_ROOT` 指向当前用户可写目录。不要把运行数据写入 Zotero 原始目录或源码仓库。

内容源优先级固定为 `.zotero-ft-cache` > PDF 提取 > 跳过；cache 可用时不会重复解析 PDF。

命令输出优先使用 `--json`，这样可以稳定读取结果中的标题、文档 id、页码、片段句柄和 wiki 句柄。

## Embedding provider 选择

阿里云百炼和火山引擎是两个独立可选的默认云 provider，使用同一个 shared embedding role。通过环境变量选择：

```env
EMBED_PROVIDER=aliyun
# 或 EMBED_PROVIDER=volcengine
```

- `aliyun`：使用 `EMBED_BASE_URL`、`EMBED_API_KEY`、`EMBED_MODEL`；Qwen 兼容接口通常返回 1024 维向量。
- `volcengine`：使用 `VOLC_EMBED_BASE_URL`、`VOLC_EMBED_API_KEY`、`VOLC_EMBED_MODEL`。
- 未配置所选云 provider 时才回退本地模型；不会把另一套云向量空间静默混用。
- 更换 provider、模型或向量维度后，必须使用独立 staging 目录做 full rebuild，验证 collection、维度、health 和检索后再切换活动 `index\\vectordb`。
- 不要在 skill、日志、回答或 release asset 中暴露 API key。


### 1. 搜索本地论文

用户想找候选论文、某主题的本地文献或某作者的论文时，执行：

```bash
paper-compass search --json library --query "用户的原始查询" --limit 10
```

用户指定作者、年份、标签或 collection 时，追加对应过滤条件：

```bash
paper-compass search --json library --query "family firm succession" --filter-authors "Author Name" --filter-year-from 2020 --filter-year-to 2025 --limit 10
```

结果中的 score 只是排序信号，不是相关性证明。保留并复用返回的 `doc_id`；需要完整元数据时，再通过项目已有的本地论文元数据入口读取，不要根据标题猜测文件标识。

### 2. 查找 PDF 原文证据

用户询问原文措辞、页码、研究设计、变量定义、识别策略、样本构造、系数、标准误、稳健性、机制或异质性时，优先使用混合段落检索：

```bash
paper-compass search --json passages --query "用户的原始查询" --search-mode hybrid --limit 10
```

如果用户查的是精确术语、变量名、缩写或中文短语，可改用 `--search-mode keyword`；如果只需要概念召回，可用 `semantic`。从结果中选取 `passage_handle` 后回读上下文：

```bash
paper-compass search --json passage-context \
  --passage-handle "返回的 passage_handle" \
  --window paragraph \
  --max-chars 2000
```

需要更大论证范围时，将 `--window` 改为 `section` 或 `page`。引用或转述只能依据返回文本，并保留标题、`doc_id` 和 `page_num`（若有）。

### 3. 综合本地文献

用户要求概括本地文献、比较研究结论或回答宽泛研究问题时，执行：

```bash
paper-compass search --json ask --query "用户的研究问题" --force-mode auto --max-sources 5
```

模式选择：

- `auto`：让本地检索根据问题选择 wiki、PDF 或混合结果
- `wiki`：优先使用编译后的知识页，适合快速了解研究框架
- `pdf`：优先使用 PDF 检索，适合需要原文依据的问题
- `hybrid`：同时需要知识概括和原文证据时使用

检查返回的 `mode_decision`、`confidence`、`sources` 和 `evidence_digest`。回答时明确区分编译内容、PDF 原文和自己的解释。

### 4. 回读 wiki 内容

如果综合结果提供 `wiki_handle`，用句柄回读具体知识页或章节：

```bash
paper-compass search --json wiki-section \
  --wiki-handle "返回的 wiki_handle"
```

不要根据标题或路径自行拼接句柄。直接搜索 wiki 只用于排查或明确要求，不是宽泛研究问题的默认入口。

## 结果与证据纪律

- 明确标注结果来自文献元数据、编译后的 wiki，还是 PDF 原文。
- 对本地证据使用准确的标题、`doc_id`、页码和句柄；不要只给模糊标题。
- 保留用户原始中文或中英混合术语；无结果时可用 `keyword` 或 `hybrid` 重试一次。
- 不要把排序分数当作事实，也不要把检索摘要扩写成原文没有支持的结论。
- 如果本地库没有相关结果，明确说“本地文献库未找到支持证据”，不要编造论文、数字、结论或引用。
- 不要声称搜索了整个文献库，除非命令输出明确支持这一范围。
- 若结果为空、置信度低、索引缺失或数据可能过期，应在回答中说明具体限制。

### 被动监控与自动增量同步

`pip install` 本身不会提示配置或注册后台任务。`paper-compass init` 先确认 Zotero 数据库与 storage 路径，再询问自动更新 `[y/N]`（默认不启用），并警告云端嵌入/wiki 生成可能产生 API 费用；Zotero 数据库和附件始终只读。Agent 不得替用户静默同意。

```bash
paper-compass init --db-source-path /path/to/zotero.sqlite --storage-path /path/to/storage --enable-auto-update
# 显式不启用：paper-compass init --disable-auto-update
paper-compass watch --enable-autostart --sqlite-path /path/to/zotero.sqlite --storage-path /path/to/storage
paper-compass watch --autostart-status
paper-compass watch --disable-autostart
```

自动启动仅针对当前用户登录：Windows HKCU Run（无崩溃自动重启）、Linux systemd user、macOS LaunchAgent；不需要密码、管理员权限或 Linux linger，也不保证未登录时运行。配置在 `runtime/state/watch_config.json`，轮转日志在 `runtime/logs/watch.log`（`runtime` 是实际运行目录）。更换数据源/storage 后须重新启用；移动或重建解释器/虚拟环境后先禁用再启用。源码部署沿用项目现有 `.env`，wheel 默认使用 `~/.paper-compass/.env`，`PAPER_COMPASS_ENV_PATH` 可覆盖路径；保留已有配置。

验证范围：尚未进行 Linux/macOS 原生测试；Windows 当前用户登录流程尚未经过重启验证。

完成一次 dry-run 后，可启动前台 watcher：

```powershell
$env:PAPER_COMPASS_ROOT='C:\Users\<用户名>\.paper-compass'
$env:PAPER_COMPASS_ZOTERO_ROOT='D:\zotero_backup'
$env:PYTHONUTF8='1'
paper-compass watch --debounce-seconds 3 --reconcile-seconds 600
```

watcher 会合并 Zotero storage 的新增、修改、删除事件，在 debounce 后运行一次同步，并定期 reconciliation 修复漏事件。`paper-compass watch --once` 用于一次手工校准。删除 storage 内容后，下一次同步会从 library、论文向量和对应生成 wiki 中清理该 key；原始 Zotero 数据库不会被写入。

若运行目录不可写，选择当前用户可写的 `PAPER_COMPASS_ROOT`；不要要求管理员权限，也不要把运行数据写入 Zotero 原始目录或源码仓库。

## 维护与诊断

维护请求先做预览或只读检查。常用诊断顺序：

```bash
paper-compass status
paper-compass validate
paper-compass-healthcheck --smoke
```

需要更新论文索引时，先执行默认 dry-run 的增量索引入口并检查新增、变更、删除和嵌入数量；确认后再应用。需要同步 Zotero、提取文本、生成 wiki 和重建索引时，优先使用：

```bash
paper-compass sync --dry-run
```

确认预览后才执行实际同步。同步不得修改原始 Zotero SQLite 数据库；检测到索引 journal/WAL/manifest 损坏时停止写入，先按诊断输出处理，不要强制解锁或盲目重建。

## 笔记写回

只有用户明确要求保存研究笔记或更新 wiki 时才写入。先生成预览，检查目标路径、冲突、关联来源和索引更新计划；得到明确确认后再提交。不得静默覆盖已有页面，必须选择合适的唯一创建或明确替换策略，并保留来源句柄。

## 故障处理

- `paper-compass` 命令不存在：确认当前目录、虚拟环境和安装状态，再报告缺少的前置条件。
- 没有结果：先区分空文献库/过期索引与查询词不匹配，再用 `keyword` 或 `hybrid` 重试。
- 配置或索引缺失：执行只读诊断并报告缺少的具体文件或目录。
- 文本提取失败：报告失败项和日志位置，不用标题或摘要替代 PDF 证据。
- 不要暴露环境变量中的密钥或把配置文件中的密钥复制到回答中。
