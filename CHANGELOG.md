# Changelog

All notable changes to paper-compass are documented here.

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
