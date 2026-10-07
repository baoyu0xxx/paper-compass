# paper-compass v1.5.0 Release Notes

Date: 2026-10-07

## Summary

v1.5.0 makes cloud embedding selection explicit and hardens the Windows runtime used for reliable Zotero synchronization and indexing.

## Highlights

### Selectable embedding providers

Alibaba Cloud Bailian Qwen and Volcengine are now explicit choices:

```env
EMBED_PROVIDER=aliyun
# or
EMBED_PROVIDER=volcengine
```

Alibaba Cloud Bailian uses the OpenAI-compatible `EMBED_*` variables. Volcengine uses `VOLC_EMBED_*`. The selected provider is used for both paper and wiki indexing; if it is unavailable, the runtime falls back to the configured local model rather than silently mixing cloud embedding spaces.

Changing provider or embedding model requires a full rebuild because Chroma collections are tied to the embedding model identity and dimension.

### Qwen indexing and Chroma reliability

- Qwen embedding responses are validated at 1024 dimensions.
- Cloud embedding batches are limited to 20 inputs for the Alibaba-compatible endpoint.
- Large Chroma metadata reads are paginated to avoid SQLite `too many SQL variables` failures.
- Paper and wiki collections record provider/model identity in their collection names and manifests.

### Windows runtime isolation

Low-integrity runtime writes, SQLite temporary files, Chroma state, and generated data remain under `%USERPROFILE%\\.paper-compass`. The original Zotero SQLite database and storage directory are read-only sources.

### Watcher and skill updates

The packaged paper-compass skill now documents the current runtime root, explicit provider selection, staged index rebuild/rotation, watcher reconciliation, failure reports, and provider-switch rebuild requirements.

## Migration

1. Copy `.env.example` to `.env` and set `EMBED_PROVIDER`.
2. Configure the selected provider's endpoint, key, and model variables.
3. Run `paper-compass validate`.
4. Run a full paper and wiki rebuild when changing provider or model.
5. Run `paper-compass status --json` and a search smoke test before removing any rollback index.

No API keys, Zotero source data, generated library data, or runtime vector databases are included in the release assets.

## Verification

- Full test suite: 383 passed.
- Active Qwen paper collection: 33,708 vectors.
- Active Qwen wiki collection: 3,099 vectors.
- Final watcher reconciliation: completed successfully.
- Active index health: ok.
