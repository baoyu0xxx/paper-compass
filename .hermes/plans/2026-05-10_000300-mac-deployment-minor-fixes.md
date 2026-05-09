# Minor Improvements: Mac Deployment Resilience

## Goal

Based on the deployment failure analysis of `moyemnjkwkexns` (Mac, Hermes API Server), implement 3 minor improvements to make paper-compass more resilient when deployed by AI agents on Mac with Python 3.13.

## Change 1: Add `__main__.py` for `python3 -m paper_compass`

### Context
Agent tried `python3 -m paper_compass.cli init --llm-args ...` and got `ModuleNotFoundError`. The correct invocation is `paper-compass init` (pip entry point), but there's no reason `python3 -m paper_compass` shouldn't also work as a fallback.

### Approach
Create `src/paper_compass/__main__.py` that delegates to `cli.main()`.

### File to change
- `src/paper_compass/__main__.py` (new file)

### Content
```python
"""Allow `python3 -m paper_compass` as CLI entry point."""
from paper_compass.cli import main

main()
```

### Validation
```bash
cd /mnt/d/pyproject/paper-compass
python3 -m paper_compass --help                          # should show help
python3 -m paper_compass validate --help                  # should show validate help
python3 -m paper_compass init --help                      # should show init help
```

---

## Change 2: AGENTS.md — Mac-specific pitfall entry

### Context
On Mac, `pip3` may point to a different Python than `python3` (Homebrew vs Framework vs system Python). The agent ran `pip3 show chromadb` → "not found" while `python3 -c "import chromadb"` worked fine. This wasted ~6 messages of debugging.

### Approach
Add one row to the "Common Pitfalls" table in AGENTS.md.

### File to change
- `AGENTS.md` (one table row addition)

### Content to add

In the "Common Pitfalls" table, insert this row (alphabetically by "Pitfall" column):

| Mac: multiple Python installations | `pip3 show <pkg>` says "not found" but `python3` can import it | Always use `python3 -m pip install ...` and `python3 -m pip show ...` instead of bare `pip3`/`pip` |

### Validation
```bash
cd /mnt/d/pyproject/paper-compass
grep -c "multiple Python" AGENTS.md    # should return 1
```

---

## Change 3: `embedder.py` — friendly HTTP error messages

### Context
In the deployment session, `build_index.py` crashed with a raw traceback that went through `ThreadPoolExecutor` internals (`concurrent/futures/_base.py`). The agent and user both saw an opaque stack trace instead of a clear "HTTP 403: check your API key / model ID" message.

### Approach
Wrap the `urllib.request.urlopen` call in `_embed_cloud()` to catch `HTTPError` and convert it to a clear `RuntimeError` with status code and response body, before it propagates through the `ThreadPoolExecutor` chain.

### Files to change
- `src/paper_compass/embedder.py`

### Current code (around line 170-180, `_embed_cloud`)

The relevant section sends one text per request via `ThreadPoolExecutor`. The HTTP call itself is inside a helper function submitted to the executor. The exception re-raises through `f.result()`. We need to catch `HTTPError` in that inner function.

### Specific change

Locate the inner function submitted to `executor.submit()` inside `_embed_cloud()`. It currently does something like:

```python
def _call(text):
    data = json.dumps({"model": ..., "input": ...}).encode()
    req = urllib.request.Request(url, data=data, headers=..., method="POST")
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return json.loads(resp.read().decode("utf-8"))
```

Wrap `urlopen` in try/except for `urllib.error.HTTPError`:

```python
def _call(text):
    data = json.dumps({"model": ..., "input": ...}).encode()
    req = urllib.request.Request(url, data=data, headers=..., method="POST")
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        body = e.read().decode("utf-8", errors="replace")[:500]
        raise RuntimeError(
            f"Embedding API error (HTTP {e.code}): {body}"
        ) from e
```

### Why this works

1. `HTTPError` is caught in the inner function (inside the executor thread)
2. A `RuntimeError` is raised instead, with a clear message
3. `concurrent.futures` wraps any exception raised in a worker thread as `self._exception`
4. `f.result()` re-raises the wrapped `RuntimeError`
5. The caller (`build_index.py` or wherever `embedder.embed()` is used) now gets a message like:
   `Embedding API error (HTTP 403): {"error":{"message":"..."}}`
   instead of the raw `concurrent/futures/_base.py` traceback

### Validation

```bash
cd /mnt/d/pyproject/paper-compass
python3 -m pytest tests/ -v -q   # expect 118 passed (no regression)
# Manual: embedder is covered by existing tests; HTTP mocks may not exist
```

---

## Summary of changes

| # | File | Type | Risk | Lines changed |
|---|------|------|------|--------------|
| 1 | `src/paper_compass/__main__.py` | New | None | +3 |
| 2 | `AGENTS.md` | Edit | None | +1 table row |
| 3 | `src/paper_compass/embedder.py` | Edit | Low (narrow try/except, no behavior change on success) | ~5 |

## Risks and Tradeoffs

- **Change 3** (`embedder.py`): The `HTTPError` catch converts the exception type from `HTTPError` to `RuntimeError`. Any existing code that does `except urllib.error.HTTPError` around `embedder.embed()` calls would be broken. A search shows no such code exists — `build_index.py` and `ingest_to_wiki.py` do not catch HTTP-specific exceptions from the embedder. Low risk.
- **Change 1** (`__main__.py`): Minimal — just imports and calls the existing entry point. No risk.
- **Change 2** (AGENTS.md): Documentation only. No risk.

## Order of execution

1. AGENTS.md (simplest, doc only)
2. `__main__.py` (new file, trivial)
3. `embedder.py` (needs careful look at the exact `_embed_cloud` code structure)
4. Run full test suite
