---
name: paper-compass-bootstrap
description: "安装、配置并启动 paper-compass 的跨平台部署流程"
metadata:
  category: deployment
  platforms: [windows, linux, macos]
  project: paper-compass
---

# paper-compass Bootstrap

## 安装

在源码目录创建虚拟环境并安装：

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -e ".[dev]"
```

Linux/macOS 使用 `.venv/bin/python` 和 `.venv/bin/pip`。

## 配置运行目录

运行数据与源码分离。Windows 示例：

```powershell
$env:PAPER_COMPASS_ROOT='C:\Users\28055\.paper-compass'
$env:PAPER_COMPASS_ZOTERO_ROOT='D:\zotero_backup'
$env:ZOTERO_SQLITE_PATH='D:\zotero_backup\zotero.sqlite'
$env:ZOTERO_STORAGE_PATH='D:\zotero_backup\storage'
```

`zotero.sqlite` 和 `storage` 只读。`C:\Users\28055\.paper-compass` 保存 library、PDF fallback 文本、wiki、向量库、manifest、快照和日志。

## 首次同步

先预览：

```powershell
paper-compass sync --dry-run
```

确认路径和变更计划后执行：

```powershell
paper-compass sync
paper-compass status
```

文本选择顺序为 `.zotero-ft-cache`、PDF 提取、跳过。cache 可用时不会解析 PDF。

## 启动监控

前台运行：

```powershell
paper-compass watch --debounce-seconds 3 --reconcile-seconds 600
```

一次校准：

```powershell
paper-compass watch --once
```

生产环境可将前台命令注册到 Windows Task Scheduler，并使用登录用户的虚拟环境 Python。不要把 API key 写入任务参数；通过 `.env` 或系统环境变量注入。

## 故障处理

- 权限错误：为当前用户授予 `C:\Users\28055\.paper-compass` 的写权限后重试。
- SQLite locked：使用默认 snapshot 策略，或先关闭 Zotero。
- 向量库损坏：先运行 `paper-compass status`，再使用带备份的受控 rebuild。
- watcher 重复触发：提高 debounce；它会通过 reconciliation 修复漏事件。
- 内容缺失：检查 storage 条目是否含非空 `.zotero-ft-cache` 或 PDF。

卸载 watcher 只需停止 Task Scheduler 任务；不会删除 Zotero 原始文件。删除 `.papercompass` 前先备份其 wiki、manifest 和向量库。
