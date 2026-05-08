# Retrieval regression question set (v1 baseline)

Use this set for repeated pre/post comparison when changing retrieval/routing.

## Metadata exactness
- Q01: Exact Zotero key lookup for a known item
- Q02: Exact DOI lookup for a known item
- Q03: Exact title lookup for a known item

## Metadata robustness
- Q04: Partial title lookup with 1-2 omitted words
- Q05: Author + topic mixed query (e.g., "AuthorX labor structure")
- Q06: Collection-constrained query (with filters.collections)

## Wiki semantic retrieval
- Q07: Concept/topic query expected to hit wiki/topics
- Q08: Method query expected to hit wiki/methods
- Q09: Paper summary query expected to hit wiki/papers

## Routing behavior
- Q10: Broad conceptual query (expect wiki or hybrid)
- Q11: Detail/evidence query with trigger words (expect hybrid/pdf)
- Q12: Low-wiki-relevance query (expect hybrid/pdf fallback)

## Noise/guardrail
- Q13: Query likely to match operational logs (ensure log/index not surfaced)
- Q14: Query with common high-frequency words only (check weak-match suppression)

## Suggested recording template
- Query ID:
- Query text:
- Expected top-1 source type:
- Expected mode:
- Observed top-3:
- Observed mode:
- Pass/Fail:
- Notes:
