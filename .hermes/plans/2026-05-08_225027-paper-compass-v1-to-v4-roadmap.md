# paper-compass roadmap: from current v1 to reusable public v4

## Goal

Design a medium-term roadmap for `paper-compass` that does not stop at v2, but instead carries the project through roughly v4 as a public, reusable, agent-first academic research infrastructure.

This plan assumes the project should:
- be open-source and reusable by others, not only tailored to one local setup;
- remain CLI / MCP / agent-first;
- explicitly avoid building a dedicated UI unless a later need becomes overwhelming;
- preserve the current core idea: Zotero-backed paper library + wiki knowledge layer + evidence retrieval layer + MCP tools.

## Planning stance

This is a product-and-architecture roadmap, not an implementation patch list.

The central recommendation is:
- do **not** grow by piling on more features first;
- instead, progress by stages:
  1. make current v1 trustworthy;
  2. make v2 reproducible and reusable;
  3. make v3 extensible and research-grade;
  4. make v4 ecosystem-ready and public-project quality.

## Current context

Based on current repository inspection:

### What already exists
- Core modules under `src/miniresearch/`:
  - `config.py`
  - `models.py`
  - `pdf_extract.py`
  - `zotero_sqlite.py`
  - `embedder.py`
  - `vector_store.py`
  - `filters.py`
  - `router.py`
  - `wiki_gen.py`
  - `wiki_store.py`
  - `mcp_server.py`
  - `index_manifest.py`
- Scripts under `scripts/`:
  - `sync_zotero.py`
  - `build_index.py`
  - `ingest_to_wiki.py`
  - `run_mcp_server.py`
- Tests currently pass:
  - `python3 -m pytest tests/ -q`
  - observed: `38 passed`
- Data state already exists locally:
  - `data/zotero-export/library.json`
  - `data/zotero-export/manifest.csv`
  - `wiki/` with hundreds of pages
  - ChromaDB collections for both papers and wiki

### What is already strong
- The layered architecture is directionally correct.
- The project is already beyond a skeleton; it has real pipeline behavior.
- The MCP-facing tool boundary is simple and appropriate for agent use.
- The wiki generation and vector indexing paths have already accumulated practical lessons.

### What is still weak
- MCP contract strictness is not yet strong enough.
- Retrieval quality control is still relatively thin.
- Traceability / auditability is only partial.
- Public-project packaging and dependency completeness are not yet strong.
- Config and project assumptions still lean heavily toward one personal environment.

## Non-goals

These should remain out of scope unless later evidence strongly changes the conclusion:
- dedicated web UI
- desktop app
- multi-user SaaS platform
- heavy workflow orchestration for its own sake
- broad social / sharing layer

A small future CLI dashboard or TUI may be acceptable if genuinely useful, but a UI should not drive architecture.

## Architectural north star

By v4, `paper-compass` should be a reusable local-first academic knowledge system with four stable layers:

1. Source layer
   - Zotero metadata and attachments
   - optionally other library sources later

2. Knowledge compilation layer
   - markdown wiki pages
   - structured page types
   - governed writeback and dedupe

3. Evidence retrieval layer
   - library metadata search
   - paper chunk retrieval
   - citation / evidence extraction
   - reranking and audit trail

4. Agent interface layer
   - stable MCP tools
   - CLI commands
   - reproducible outputs
   - healthcheck / trace / evaluation support

The key design principle:

`paper-compass` should become a reusable research backend, not a one-off personal script collection.

## Recommended roadmap summary

- v1.5: stabilize the current prototype
- v2: make it public-reusable and contract-clean
- v3: make it research-grade in retrieval quality and observability
- v4: make it extensible and ecosystem-ready

---

# v1.5: stabilization layer

## Objective

Convert the current “working prototype” into a trustworthy baseline before any major expansion.

## Why this comes before v2

At the moment, the biggest risks are not lack of features but:
- contract drift;
- retrieval noise;
- incomplete audit trail;
- environment-specific assumptions.

If these are not addressed first, later versions will accumulate technical debt quickly.

## Workstreams

### 1. MCP contract cleanup

#### Goal
Make the MCP layer internally consistent and easier for outside agents / clients to trust.

#### Tasks
1. Align `tools/list` schemas with actual handler signatures.
2. Remove advertised-but-unused parameters.
3. Add missing handler parameters where schema exposure is intentional.
4. Centralize tool schema definitions rather than duplicating them in ad hoc logic.
5. Add explicit contract tests for each tool.

#### Likely files
- `scripts/run_mcp_server.py`
- `src/miniresearch/mcp_server.py`
- `src/miniresearch/models.py`
- `tests/test_mcp_backend.py`
- new: `tests/test_mcp_contract.py`
- new: `docs/mcp/tool-contracts.md`

#### Desired outcome
A clean statement of: “these are the supported inputs, these are the outputs, and they match code.”

### 2. Retrieval relevance cleanup

#### Goal
Reduce obviously irrelevant results in `search_library` and `ask_research`.

#### Tasks
1. Split metadata matching into tiers:
   - exact key / DOI / title match;
   - normalized title match;
   - structured metadata match;
   - fallback token scoring.
2. Add stronger weighting and exact-match shortcuts.
3. Add result pruning before answer assembly.
4. Make `ask_research` distinguish:
   - candidate paper selection;
   - evidence snippet retrieval;
   - final synthesis.
5. Add regression tests for known noisy queries.

#### Likely files
- `src/miniresearch/filters.py`
- `src/miniresearch/router.py`
- `tests/test_retrieval_quality.py`
- `tests/test_router_behavior.py`

### 3. Trace and audit baseline

#### Goal
Move from “trace_id exists in response” to “query path is reconstructable”.

#### Tasks
1. Add lightweight trace logging for each tool call.
2. Log:
   - timestamp
   - tool name
   - query
   - route decision
   - collection used
   - returned source ids
   - provider / model identifiers
3. Keep output local-first in JSONL.
4. Make logging optional but enabled by config.

#### Likely files
- new: `src/miniresearch/logging.py`
- `src/miniresearch/mcp_server.py`
- `src/miniresearch/router.py`
- new: `data/logs/query-trace.jsonl` (runtime artifact)
- `configs/mcp.yaml`
- `tests/test_logging.py`

### 4. Public reproducibility baseline

#### Goal
Make the repo installable and understandable outside the original environment.

#### Tasks
1. Complete dependency declaration in `pyproject.toml`.
2. Add installation instructions for required Python and system dependencies.
3. Add `.env.example` and a minimal public-safe config path.
4. Document local-only assumptions and overridable paths.

#### Likely files
- `pyproject.toml`
- `README.md`
- new: `.env.example`
- `configs/*.yaml`

## v1.5 acceptance criteria

- MCP tool schemas and handlers are aligned.
- Known noisy queries are meaningfully improved.
- Each tool invocation can emit a minimal trace record.
- A new user can set up the project from documentation with fewer hidden assumptions.

---

# v2: reusable public release

## Objective

Turn `paper-compass` from a personal research backend into a reusable open-source toolkit that other academics can adopt with moderate effort.

## Product definition for v2

A user should be able to:
- point the project at their Zotero backup / SQLite / attachment root;
- build library and wiki indexes;
- run MCP tools locally;
- inspect traces and health status;
- understand how to extend prompts and providers.

## Core theme

v2 is about **reusability**, not maximal feature breadth.

## Workstreams

### 1. Source abstraction beyond one local machine

#### Goal
Remove hardcoded reliance on one specific filesystem layout.

#### Tasks
1. Formalize path resolution through config only.
2. Define a source adapter boundary:
   - Zotero SQLite + attachments as the first-class adapter.
3. Keep room for future adapters without implementing too many now.
4. Validate missing-path and partial-data cases gracefully.

#### Likely files
- `src/miniresearch/config.py`
- `src/miniresearch/zotero_sqlite.py`
- `scripts/sync_zotero.py`
- `configs/paths.yaml`
- `tests/test_source_config.py`

### 2. CLI surface for non-Hermes users

#### Goal
Ensure the project is usable even without direct Hermes integration.

#### Tasks
1. Normalize script interfaces and help messages.
2. Introduce a coherent CLI entry strategy, either:
   - keep `scripts/*.py` but standardize them, or
   - move toward a package CLI entry point later.
3. Document common workflows:
   - sync
   - wiki ingest
   - index build
   - run MCP server
   - smoke-test search

#### Likely files
- `scripts/sync_zotero.py`
- `scripts/ingest_to_wiki.py`
- `scripts/build_index.py`
- `scripts/run_mcp_server.py`
- `README.md`
- new: `docs/workflows/*.md`

### 3. Healthcheck and diagnostics

#### Goal
Make failures diagnosable by ordinary users.

#### Tasks
1. Build a `healthcheck.py` command.
2. Check:
   - config readability
   - required env vars
   - provider reachability
   - manifest / library integrity
   - vector collection presence
   - MCP readiness
3. Return human-readable diagnostics and machine-readable status.

#### Likely files
- new: `scripts/healthcheck.py`
- `src/miniresearch/config.py`
- `src/miniresearch/vector_store.py`
- `src/miniresearch/mcp_server.py`
- `tests/test_healthcheck.py`

### 4. Writeback governance

#### Goal
Prevent the wiki from degenerating into an ungoverned dump.

#### Tasks
1. Define writeback policy.
2. Separate page classes clearly:
   - `papers`
   - `topics`
   - `methods`
   - `comparisons`
   - `queries`
3. Add rules for when a query result is worth saving.
4. Add duplicate-topic / near-duplicate detection heuristics.

#### Likely files
- `src/miniresearch/wiki_store.py`
- new: `src/miniresearch/wiki_linker.py`
- `configs/wiki.yaml`
- new: `docs/architecture/wiki-writeback-policy.md`
- `tests/test_wiki_writeback.py`
- `tests/test_wiki_dedupe.py`

### 5. Evaluation harness v1

#### Goal
Create a repeatable way to tell whether the system is getting better.

#### Tasks
1. Build a small benchmark set from realistic academic queries.
2. Cover categories such as:
   - concept recall
   - method comparison
   - source verification
   - variable / sample definition
   - multi-paper synthesis
3. Store expected notes / qualitative gold references.
4. Run benchmark manually or via script after major retrieval changes.

#### Likely files
- new: `eval/questions.md`
- new: `eval/gold-notes.md`
- new: `scripts/run_eval.py`
- `tests/` for harness integrity if needed

## v2 acceptance criteria

- Project can be installed and run by an outside user with documented setup.
- Healthcheck exists and catches common setup failures.
- MCP tool contracts are stable and documented.
- Wiki writeback has explicit governance.
- A small evaluation set exists and is usable.

---

# v3: research-grade retrieval and synthesis

## Objective

Upgrade from “usable retrieval stack” to “trustworthy academic assistant backend”.

## Core theme

v3 should prioritize answer quality, evidence discipline, and observability.

This is the stage where `paper-compass` starts becoming genuinely differentiated.

## Workstreams

### 1. Two-stage retrieval and reranking

#### Goal
Improve relevance for both library selection and evidence extraction.

#### Tasks
1. Make retrieval explicitly multi-stage:
   - candidate retrieval
   - reranking
   - evidence selection
2. Add reranking heuristics first; add model-based reranking only if needed.
3. Separate “paper ranking” from “chunk ranking”.
4. Support exact-title, DOI, and citation-oriented lookups strongly.

#### Likely files
- `src/miniresearch/filters.py`
- `src/miniresearch/router.py`
- new: `src/miniresearch/rerank.py`
- `tests/test_rerank.py`
- `tests/test_retrieval_quality.py`

### 2. Evidence-aware answer synthesis

#### Goal
Ensure answers distinguish summary from source-grounded evidence.

#### Tasks
1. Refactor `ask_research` into clearer phases:
   - retrieve wiki context
   - retrieve candidate papers
   - extract evidence snippets
   - synthesize answer
2. Mark evidence provenance explicitly in outputs.
3. Add stronger page / chunk hints and normalized citations.
4. Distinguish:
   - wiki-derived synthesis
   - paper-derived evidence
   - uncertainty / missing evidence

#### Likely files
- `src/miniresearch/router.py`
- new: `src/miniresearch/synthesis.py`
- `prompts/rag_answer.md`
- `tests/test_synthesis.py`

### 3. Query taxonomy and routing upgrade

#### Goal
Make routing more explicit and explainable.

#### Tasks
1. Formalize query taxonomy:
   - recall queries
   - entity lookup queries
   - evidence verification queries
   - comparative synthesis queries
   - open exploration queries
2. Keep rule routing as the default baseline.
3. Add optional classifier-assisted routing only as a pluggable enhancement.
4. Log route decisions for audit.

#### Likely files
- `src/miniresearch/router.py`
- `prompts/router_classify.md`
- new: `docs/architecture/query-taxonomy.md`
- `tests/test_router_rules.py`
- `tests/test_router_classifier.py`

### 4. Observability and experiment tracking

#### Goal
Make retrieval changes measurable over time.

#### Tasks
1. Version prompts used in generation / answer synthesis.
2. Log provider / prompt / route / index metadata in traces.
3. Add simple comparative evaluation runs:
   - before / after retrieval changes
   - alternative prompt variants
4. Build small scripts to summarize trace patterns and failure cases.

#### Likely files
- `src/miniresearch/logging.py`
- new: `scripts/analyze_traces.py`
- new: `docs/evaluation/usage-notes.md`
- `eval/`

### 5. Better public packaging and fixtures

#### Goal
Help outside users evaluate the project without your private full library.

#### Tasks
1. Provide small synthetic or public-safe sample fixtures.
2. Add sample wiki pages and sample library records.
3. Make test and demo workflows runnable without private data.

#### Likely files
- `data/zotero-export/library_sample.json`
- new: `tests/fixtures/`
- `README.md`
- new: `docs/demo.md`

## v3 acceptance criteria

- Retrieval quality is measurably better on the evaluation set.
- `ask_research` outputs are more evidence-aware and auditable.
- Routing behavior is documented and inspectable.
- Outside users can run meaningful demos without private corpora.

---

# v4: extensible ecosystem-ready backend

## Objective

Make `paper-compass` not just reusable, but extensible enough to serve as a serious backend for personal or lab-scale academic knowledge workflows.

## Core theme

v4 is where the project becomes stable enough that others can build on top of it, while still avoiding unnecessary product sprawl.

## Workstreams

### 1. Adapter architecture for new sources

#### Goal
Allow future expansion beyond one Zotero ingestion model without destabilizing the project.

#### Tasks
1. Formalize interfaces for:
   - source adapters
   - embedding backends
   - retrieval strategies
   - writeback policies
2. Keep Zotero as the reference implementation.
3. Add one additional source adapter only if it clarifies the abstraction.

#### Likely files
- new: `src/miniresearch/interfaces.py`
- refactors across:
  - `zotero_sqlite.py`
  - `embedder.py`
  - `router.py`
  - `wiki_store.py`

### 2. Stable CLI / package API surface

#### Goal
Offer public users a stable entry surface.

#### Tasks
1. Expose package-level CLI entry points.
2. Define supported commands and deprecation policy.
3. Separate internal experimental modules from public interfaces.

#### Likely files
- `pyproject.toml`
- new: `src/miniresearch/cli.py`
- `README.md`
- new: `docs/public-api.md`

### 3. MCP maturity upgrade

#### Goal
Make MCP support something others can rely on, not just a local stub.

#### Tasks
1. Strengthen initialization and protocol behavior.
2. Normalize tool error handling and machine-readable failure semantics.
3. Add MCP-specific integration tests.
4. Document expected client interoperability constraints.

#### Likely files
- `scripts/run_mcp_server.py`
- `src/miniresearch/mcp_server.py`
- new: `tests/test_mcp_protocol.py`
- new: `docs/mcp/interop.md`

### 4. Knowledge maintenance and lifecycle tools

#### Goal
Support long-term maintenance of a growing wiki and index corpus.

#### Tasks
1. Add maintenance commands for:
   - orphaned wiki pages
   - stale vector state
   - duplicate topic pages
   - outdated traces / logs cleanup
2. Add reports for collection drift and indexing drift.
3. Keep cleanup operations explicit and auditable.

#### Likely files
- new: `scripts/maintenance.py`
- `src/miniresearch/vector_store.py`
- `src/miniresearch/wiki_store.py`
- `src/miniresearch/index_manifest.py`
- `tests/test_maintenance.py`

### 5. Documentation and contributor experience

#### Goal
Make the public repo understandable and sustainable.

#### Tasks
1. Reorganize docs into:
   - getting started
   - architecture
   - workflows
   - MCP usage
   - evaluation
   - maintenance
2. Add contribution guidelines.
3. Add issue templates / roadmap notes if desired.
4. Make explicit what is opinionated versus extensible.

#### Likely files
- `README.md`
- new: `docs/`
- new: `CONTRIBUTING.md`
- new: `ROADMAP.md`

## v4 acceptance criteria

- Public interfaces are clearer and more stable.
- MCP support is materially stronger.
- The repo is contributor-friendly.
- The architecture can accept limited extensions without major rewrites.

---

# Recommended sequencing by priority

## Highest priority now

1. MCP contract cleanup
2. Retrieval relevance cleanup
3. Trace logging baseline
4. Dependency / setup reproducibility
5. Healthcheck

## Next tier

6. Wiki writeback governance
7. Evaluation harness
8. Evidence-aware answer synthesis
9. Query taxonomy and routing formalization

## Later tier

10. Public CLI surface refinement
11. Adapter interfaces
12. MCP protocol maturity work
13. Maintenance and contributor tooling

## Explicit depriorities

- dedicated UI
- multi-user features
- cloud platformization
- feature growth without evaluation coverage

---

# Suggested repository evolution

## Keep
- `src/miniresearch/`
- `scripts/`
- `configs/`
- `prompts/`
- `wiki/`
- `data/`
- `tests/`

## Add over time
- `docs/mcp/`
- `docs/architecture/`
- `docs/workflows/`
- `docs/evaluation/`
- `eval/`
- `tests/fixtures/`

## Important structural principle

Avoid prematurely over-modularizing.

A moderate refactor to clarify interfaces is good.
A full framework-like redesign too early would likely slow the project without improving research usefulness.

---

# Risks and tradeoffs

## 1. Over-generalizing too early

Because the project is now becoming public-facing, there is a temptation to design for every imaginable use case.

Risk:
- the architecture becomes abstract before its needs are proven.

Response:
- keep Zotero + markdown wiki + local vector store as the reference center;
- abstract only where repeated pressure already exists.

## 2. Chasing retrieval sophistication before observability

Risk:
- you add reranking / classifiers / deeper synthesis but still cannot explain failures.

Response:
- trace and evaluation should precede major retrieval sophistication.

## 3. Public reuse versus personal research speed

Risk:
- making the project public-ready slows immediate research utility.

Response:
- keep a dual lens:
  - v1.5 / v2 improve public reproducibility;
  - do not discard practical project-specific optimizations that are cleanly configurable.

## 4. No UI by design

This is a sensible choice for now.

Tradeoff:
- some outside users may find setup less approachable.

Why the decision still seems correct:
- the real bottlenecks are retrieval quality, traceability, and reusability, not visual interaction;
- UI would likely absorb effort without solving the core academic-quality issues.

---

# Open questions to resolve before implementation

## Product / scope questions
1. Should v2 aim for “single-user public reusable” only, or also “small lab reusable”?
2. Should `paper-compass` remain tightly Zotero-centered, or explicitly brand itself as source-extensible from v4 onward?
3. Is the primary public audience:
   - individual researchers,
   - AI-agent builders,
   - or research labs?

## Retrieval questions
4. Do you want PaperQA to become a hard dependency for the deep-evidence layer, or only one optional backend?
5. Should reranking stay heuristic-first for reproducibility, or can it depend on an external model service?

## Governance questions
6. How strict should wiki writeback be by default?
7. Should `queries/` remain a normal wiki area, or be treated as semi-ephemeral artifacts?

## Packaging questions
8. Do you want to preserve the current `miniresearch` package name, or rename toward a more public-facing package structure before release?
9. How much private-environment residue is acceptable before the first public release?

---

# Concrete first implementation tranche after this plan

If starting immediately, the most sensible first tranche is:

## tranche A
1. MCP contract alignment
2. add contract tests
3. add trace logging skeleton
4. add healthcheck skeleton
5. complete dependency declaration and setup docs

## tranche B
6. improve `search_library` ranking
7. clean up `ask_research` evidence assembly
8. add retrieval regression tests
9. define wiki writeback policy

## tranche C
10. build small evaluation set
11. add trace analysis tooling
12. improve public docs and sample fixtures

This sequencing keeps work close to the current codebase while laying the foundation for v2-v4 growth.

---

# Validation strategy across versions

## For v1.5
- run full test suite
- add MCP contract tests
- add trace logging tests
- manual smoke tests for each tool

## For v2
- fresh-environment setup test
- healthcheck pass
- end-to-end workflow doc tested from clean state
- sample-data demo works

## For v3
- benchmark queries compared before/after
- evidence quality inspection on representative questions
- route decision logging verified

## For v4
- public API / CLI stability check
- MCP integration tests
- maintenance workflow tests
- contributor docs usability review

---

# Final recommendation

The right roadmap is not “v2 only” and not “feature sprawl”.

The most defensible long-term path is:
- v1.5: stabilize
- v2: public reusable
- v3: research-grade quality
- v4: extensible ecosystem-ready backend

Given your stated priorities, the project should optimize for:
1. public reusability;
2. academic trustworthiness;
3. agent-first interfaces;
4. no dedicated UI.

If forced to summarize in one sentence:

`paper-compass` should evolve into a reusable, auditable, MCP-native academic retrieval backend, rather than a UI product or a feature-heavy personal script bundle.
