# Changelog

All notable changes to paper-compass are documented here.

## [Unreleased]

### Added

- `paper-compass repair-fts` rebuilds a corrupted ChromaDB FTS5 full-text index in place, without re-embedding any paper or rebuilding the vector collections; it supports `--dry-run`, `--json`, and `--backup`. The vectordb health check now points to this command when `PRAGMA quick_check` reports a malformed FTS5 inverted index.

### Fixed

- The managed watcher no longer keeps Zotero from starting: it stopped leaking read-only SQLite connections to the live Zotero database on every loop iteration and every sync (`confirm_source`, snapshot creation, and the vectordb health check all relied on `with sqlite3.connect(...)`, which only commits and never closes). Read-only opens now go through `read_only()`, the watcher only checks that the source paths exist, and each sync reads a snapshot instead.
- The managed watcher defers a sync round while a Zotero client process is running (`skip_while_zotero_running`, default on) instead of repeatedly failing with `database is locked`; a sync that still hits the lock is reported as a deferral rather than a failure, so `last_error` no longer sticks.
- `paper-compass init` / `watch --enable-autostart` no longer refuse a Zotero database that Zotero currently holds locked; the library check is skipped while the database cannot be inspected, and a wrong database then fails in the next sync.
- Windows login no longer shows the "无法验证发布者 / 打开文件 - 安全警告" dialog for the managed watcher: enabling or repairing autostart now clears the Mark-of-the-Web (`Zone.Identifier`) from the managed interpreter and the virtual environment's executables, and the managed runtime bootstrap does the same after creating or updating `.venv`.
- `paper-compass watch --autostart-status` reports `"marked"` so a downloaded interpreter is visible before the next login; `--repair-autostart` is an idempotent recovery path when the mark cannot be removed automatically.

## [1.5.0] - 2026-10-07

### Added

- Explicit embedding provider selection with `EMBED_PROVIDER=aliyun` or `EMBED_PROVIDER=volcengine`.
- Alibaba Cloud Bailian Qwen configuration using the OpenAI-compatible `EMBED_*` variables.
- Provider-aware `paper-compass init`, `validate`, and `status` behavior.
- Windows runtime isolation and watcher documentation for `%USERPROFILE%\\.paper-compass`.

### Changed

- Alibaba Cloud Bailian and Volcengine are separate selectable providers sharing one embedding role for papers and wiki content.
- An explicitly selected cloud provider no longer silently falls through to another cloud provider; unavailable cloud configuration falls back to the local embedding model.
- Qwen embedding batches are limited to 20 inputs and the validated default dimension is 1024.
- Chroma metadata reads are paginated to avoid SQLite `too many SQL variables` failures.
- Updated the packaged skill, deployment guide, README files, environment template, and migration guidance.

### Fixed

- Windows UTF-8 watcher output and low-integrity runtime/temp handling.
- Provider/model identity checks that could otherwise allow incompatible paper and wiki vector spaces.
- Runtime status and validation reporting for configured and active embedding providers.

### Verification

- Full test suite: 383 passed.
- Active Qwen paper collection: 33,708 vectors.
- Active Qwen wiki collection: 3,099 vectors.
- Active index health: ok.
- Release assets: `paper_compass-1.5.0-py3-none-any.whl` and `paper_compass-1.5.0.tar.gz`.

### Migration Notes

- Set `EMBED_PROVIDER` explicitly in `.env`.
- Configure only the selected provider's endpoint, model, and API key variables.
- Run a full paper and wiki rebuild after changing provider, model, or dimension.
- Do not commit API keys, Zotero source data, runtime vector databases, or generated runtime data.

## [1.4.1]

See [docs/release-notes-v1.4.1.md](docs/release-notes-v1.4.1.md).
