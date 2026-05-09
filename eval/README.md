# paper-compass Evaluation Benchmark

## Usage

```bash
# Run all queries
python eval/run_eval.py

# Filter by mode
python eval/run_eval.py --mode search_library

# Verbose output
python eval/run_eval.py -v
```

## Query Categories

| Category | Examples | Expected |
|----------|----------|----------|
| Exact key | `MWWFY69B` | Direct Zotero key lookup |
| English title | `competition in two sided markets` | Substring match + fuzzy |
| Chinese title | `代际收入流动` | Bigram-aware CJK matching |
| Multi-keyword | `延迟退休 代际收入` | Combined keyword search |
| Author | `chetty` | Author field scoring |
| Collection | `家族企业 继承` | Collections + tags filtering |
| Passage search | `代际收入流动 机制` | Full-text paragraph search |

## Adding Queries

Edit `eval/queries.yaml`:

```yaml
queries:
  - query: "your search query"
    expected_keys: ["KEY1", "KEY2"]     # optional — Zotero keys that MUST appear
    min_expected: 2                      # minimum results in top-10
    mode: search_library                 # search_library | search_passages
    tolerance: strict                    # strict | relaxed
```

- `tolerance: strict` — all `expected_keys` must appear in results
- `tolerance: relaxed` — at least `min_expected` results in top-10
- `min_expected` without `expected_keys` — check total result count ≥ min_expected
