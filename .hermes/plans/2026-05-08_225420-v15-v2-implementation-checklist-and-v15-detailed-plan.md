# paper-compass v1.5 + v2 implementation checklist and detailed v1.5 plan

> **For Hermes:** Use subagent-driven-development skill to implement this plan task-by-task.

**Goal:** Produce an actionable near-term roadmap for `paper-compass`, with (1) a complete implementation checklist covering v1.5 and v2, and (2) a detailed execution plan for v1.5 that can directly drive implementation.

**Architecture:** Treat current `paper-compass` as an already-working v1 prototype and improve it in two stages. v1.5 focuses on trustworthiness, contract cleanliness, reproducibility, and auditability. v2 focuses on public reusability, diagnostics, governance, and a stable user-facing CLI/MCP experience. No dedicated UI is planned.

**Tech Stack:** Python 3.11+, YAML config, markdown wiki, ChromaDB, local scripts/CLI, MCP stdio server, pytest.

---

## 1. Scope and planning assumptions

### Confirmed product direction
- The project should become public and reusable.
- Planning should extend beyond a narrow v2 framing, but implementation should start with v1.5 and v2.
- The project should remain CLI / agent / MCP first.
- A dedicated UI is intentionally out of scope.

### Current state assumed from repo inspection
- Core retrieval pipeline already exists under `src/miniresearch/`.
- End-to-end scripts already exist under `scripts/`.
- Tests already pass on the current machine.
- The system is already useful locally, but still carries personal-environment assumptions.

### Strategic principle
Do not expand feature surface first. First make the current system:
1. contract-clean,
2. auditable,
3. reproducible,
4. reusable by outsiders.

---

## 2. Version intent

## v1.5 intent
Stabilize the current prototype so it is trustworthy enough to serve as the base for public reuse.

## v2 intent
Turn the stabilized local system into a public, reusable open-source backend for individual researchers and technically capable lab users.

---

## 3. Complete implementation checklist for v1.5 + v2

This section is the high-level implementation checklist. The detailed execution plan for v1.5 begins in Section 4.

# v1.5 implementation checklist

## Track A — MCP contract and protocol cleanup
- [ ] Inventory every exposed MCP tool schema in `scripts/run_mcp_server.py`
- [ ] Inventory every actual handler signature in `src/miniresearch/mcp_server.py`
- [ ] List all schema/handler mismatches
- [ ] Decide for each mismatch: remove schema field vs implement support
- [ ] Centralize tool contract definitions in one location
- [ ] Make `tools/list` derive from centralized contract definitions
- [ ] Ensure `handle_tool()` only filters against real supported parameters
- [ ] Normalize error envelopes for unknown tools, missing args, and backend failures
- [ ] Add MCP contract tests for each tool
- [ ] Add protocol smoke tests for `tools/list` and `tools/call`
- [ ] Write public contract documentation

## Track B — Retrieval relevance cleanup
- [ ] Review current `search_library()` ranking logic
- [ ] Introduce exact-match tiering for Zotero key, DOI, and normalized title
- [ ] Add stronger title weighting and structured field weighting
- [ ] Prevent weak token overlap from dominating results
- [ ] Review `ask_research()` flow for noisy metadata candidates
- [ ] Separate candidate paper retrieval from evidence retrieval
- [ ] Prune low-quality library matches before answer assembly
- [ ] Add regression tests for representative noisy queries
- [ ] Add query-specific smoke notes for manual verification

## Track C — Traceability and audit baseline
- [ ] Define trace record schema
- [ ] Add lightweight trace logging module
- [ ] Log tool name, query, route choice, collections used, source ids, provider/model ids
- [ ] Add trace write path configuration
- [ ] Ensure trace logging can be disabled by config
- [ ] Add unit tests for trace emission
- [ ] Add docs for reading and interpreting trace logs

## Track D — Public reproducibility baseline
- [ ] Audit imports used by runtime code versus declared dependencies
- [ ] Expand `pyproject.toml` dependency list
- [ ] Add `.env.example`
- [ ] Review `configs/*.yaml` for personal hardcoding
- [ ] Move environment-specific assumptions into documented config fields
- [ ] Update `README.md` with setup instructions
- [ ] Add a clean-install smoke path for outside users

## Track E — Repo hygiene for public release preparation
- [ ] Decide what private/local data paths remain in repo docs
- [ ] Clarify sample-data vs private-data story in docs
- [ ] Add initial docs structure for public readers
- [ ] Ensure all public docs describe CLI/MCP workflows, not UI workflows

## v1.5 exit criteria
- [ ] MCP tool contracts and handlers match
- [ ] Retrieval quality is improved on at least a small benchmark set
- [ ] Trace logging works end-to-end
- [ ] Repo setup is substantially reproducible outside the original machine
- [ ] Public-facing documentation exists for setup and core workflows

---

# v2 implementation checklist

## Track F — Source abstraction and environment portability
- [ ] Normalize path resolution through config rather than repo-specific assumptions
- [ ] Make `sync_zotero.py` robust to missing/alternate roots
- [ ] Validate partial source states gracefully
- [ ] Document source adapter assumptions explicitly
- [ ] Define a minimal source abstraction boundary without over-generalizing

## Track G — Stable CLI workflows for non-Hermes users
- [ ] Normalize argument conventions across all scripts
- [ ] Standardize `--help` descriptions and usage examples
- [ ] Decide whether to keep `scripts/*.py` as the primary CLI surface or add a package entrypoint
- [ ] Document canonical workflows:
  - [ ] sync Zotero
  - [ ] build index
  - [ ] ingest wiki
  - [ ] run MCP server
  - [ ] run smoke queries
- [ ] Add examples for sample-data mode if available

## Track H — Healthcheck and diagnostics
- [ ] Implement `scripts/healthcheck.py`
- [ ] Check config readability
- [ ] Check required env vars
- [ ] Check provider settings presence
- [ ] Check manifest and library file readability
- [ ] Check vector collection presence and counts
- [ ] Check MCP readiness
- [ ] Return machine-readable and human-readable output
- [ ] Add tests for healthy and unhealthy states

## Track I — Wiki governance and writeback policy
- [ ] Write `wiki-writeback-policy.md`
- [ ] Define save thresholds for `queries`, `topics`, `methods`, `comparisons`
- [ ] Distinguish durable knowledge pages from ephemeral query artifacts
- [ ] Add duplicate-topic / near-duplicate logic
- [ ] Add tests for writeback policy enforcement
- [ ] Add tests for topic dedupe heuristics

## Track J — Evaluation harness v1
- [ ] Create `eval/questions.md`
- [ ] Create `eval/gold-notes.md`
- [ ] Create a small, representative benchmark set
- [ ] Add a scriptable evaluation runner or structured manual workflow
- [ ] Tag benchmark questions by type
- [ ] Use benchmark set for retrieval regressions and routing regressions

## Track K — Public documentation and sample fixtures
- [ ] Reorganize docs into architecture / workflows / MCP / evaluation
- [ ] Provide sample fixtures that do not depend on private corpora
- [ ] Document demo flow for outside users
- [ ] Explain limitations of sample mode vs real-library mode

## v2 exit criteria
- [ ] Outside users can install and configure the project with documentation
- [ ] Healthcheck catches common failures
- [ ] Core CLI/MCP workflows are documented and stable
- [ ] Writeback is governed rather than ad hoc
- [ ] A usable evaluation set exists
- [ ] The project feels intentionally public-facing, not merely personal-and-shared

---

## 4. Detailed v1.5 execution plan

# v1.5 detailed plan

## v1.5 objective

Turn the current prototype into a trustworthy baseline suitable for public hardening.

### What v1.5 must accomplish
1. Make MCP contracts honest and stable.
2. Improve obvious retrieval noise.
3. Introduce traceability.
4. Make the repo much easier to reproduce externally.

### What v1.5 should not attempt
- full source-adapter framework
- broad plugin architecture
- advanced LLM routing sophistication
- dedicated UI
- multi-user support
- large repo renaming unless absolutely necessary

---

## 5. v1.5 workstreams, order, and dependency structure

### Recommended order
1. Contract cleanup first
2. Trace schema second
3. Retrieval cleanup third
4. Reproducibility and docs fourth
5. Final validation pass fifth

### Why this order
- Contract cleanup reduces ambiguity before additional behavior is added.
- Trace schema should be settled early so later changes are observable.
- Retrieval cleanup benefits from having traces available.
- Docs should reflect stabilized behavior rather than shifting assumptions.

---

## 6. Detailed v1.5 tasks

## Workstream 1 — MCP contract cleanup

### Task 1.1: Inventory all current tool contracts

**Objective:** Create a precise map of what MCP claims to expose versus what the backend actually supports.

**Files:**
- Read: `scripts/run_mcp_server.py`
- Read: `src/miniresearch/mcp_server.py`
- Read: `src/miniresearch/models.py`
- Create/Modify later: `docs/mcp/tool-contracts.md`
- Test later: `tests/test_mcp_contract.py`

**Substeps:**
1. List each tool emitted by `tools/list`.
2. Record each input field in the emitted schema.
3. Record the actual Python handler signature for each tool.
4. Record any hidden accepted params added by CLI mode.
5. Produce a mismatch table.

**Expected output artifact:**
A mismatch matrix such as:
- tool name
- schema field
- implemented? yes/no
- keep/remove/implement decision

### Task 1.2: Choose the single source of truth for tool contracts

**Objective:** Prevent future drift by centralizing tool schema definitions.

**Files:**
- Modify: `src/miniresearch/mcp_server.py`
- Modify: `scripts/run_mcp_server.py`
- Possible create: `src/miniresearch/mcp_contracts.py`
- Test: `tests/test_mcp_contract.py`

**Decision recommendation:**
Use a single module to define:
- tool name
- description
- argument schema
- optional validation metadata

Then have:
- `tools/list` derive from this source
- `handle_tool()` validate/filter against the same source

**Design note:**
Do not overbuild a framework; a simple Python dict or dataclass registry is sufficient.

### Task 1.3: Resolve schema/implementation mismatches

**Objective:** Make every exposed field either truly supported or no longer exposed.

**Files:**
- Modify: `scripts/run_mcp_server.py`
- Modify: `src/miniresearch/mcp_server.py`
- Test: `tests/test_mcp_contract.py`
- Test: `tests/test_mcp_backend.py`

**Substeps:**
1. Remove parameters that are not intended for support.
2. Add handler support only where the field is genuinely useful.
3. Ensure CLI parameter parsing maps cleanly onto tool handler inputs.
4. Normalize behavior between CLI mode and MCP mode.

**Key examples to review:**
- `search_wiki.page_types`
- `search_wiki.return_snippets`
- `save_to_wiki.wiki_root`
- any field present in CLI but absent in handler signature

### Task 1.4: Normalize error behavior

**Objective:** Ensure tool failures are machine-readable and consistent.

**Files:**
- Modify: `src/miniresearch/mcp_server.py`
- Modify: `src/miniresearch/models.py`
- Test: `tests/test_mcp_backend.py`
- Create/Modify: `tests/test_mcp_errors.py`

**Substeps:**
1. Define consistent handling for unknown tool names.
2. Define handling for bad/missing arguments.
3. Define handling for backend errors.
4. Ensure error envelopes always include:
   - `ok=false`
   - `tool`
   - `trace_id`
   - `warnings`
   - optional next action

### Task 1.5: Add contract and protocol tests

**Objective:** Lock behavior so future changes do not silently reintroduce drift.

**Files:**
- Create: `tests/test_mcp_contract.py`
- Create: `tests/test_mcp_protocol.py`
- Modify: `tests/test_mcp_backend.py`

**Test coverage to include:**
- `tools/list` returns expected tool names
- required fields exist for each tool
- no unsupported fields are emitted
- handler accepts expected parameters only
- `tools/call` can invoke each tool through the stdio layer
- error envelopes stay normalized

### Task 1.6: Document the MCP contract

**Objective:** Make public usage possible without code archaeology.

**Files:**
- Create: `docs/mcp/tool-contracts.md`
- Modify: `README.md`

**Doc sections:**
- tool summary table
- input/output examples
- error semantics
- CLI mode vs MCP mode notes
- known limitations of the current stdio implementation

---

## Workstream 2 — Traceability baseline

### Task 2.1: Define the trace schema

**Objective:** Decide exactly what a trace record must contain before logging code is added.

**Files:**
- Create: `docs/architecture/trace-schema.md`
- Modify later: `src/miniresearch/logging.py`
- Modify later: `configs/mcp.yaml`

**Recommended fields:**
- timestamp
- trace_id
- tool
- query or operation summary
- force_mode if present
- route decision
- collections queried
- returned source ids
- provider / model identifiers used
- warnings count
- elapsed time if easy to capture

**Principle:**
Keep v1.5 trace records lightweight and append-only.

### Task 2.2: Add a lightweight logging module

**Objective:** Create one place for trace emission logic.

**Files:**
- Create: `src/miniresearch/logging.py`
- Modify: `src/miniresearch/mcp_server.py`
- Modify: `src/miniresearch/router.py`
- Test: `tests/test_logging.py`

**Implementation direction:**
A small helper should:
- accept a trace dict,
- ensure serialization safety,
- append JSONL to a configured path,
- fail safely if logging is disabled or path is missing.

### Task 2.3: Emit traces from tool entrypoints

**Objective:** Ensure every MCP/CLI tool path can leave an audit trail.

**Files:**
- Modify: `src/miniresearch/mcp_server.py`
- Modify: `src/miniresearch/router.py`
- Test: `tests/test_logging.py`

**Substeps:**
1. Emit a trace on success.
2. Emit a trace on error where possible.
3. Include route decision from `ask_research()`.
4. Include source ids returned by retrieval.

### Task 2.4: Add config controls for logging

**Objective:** Make trace logging configurable rather than hardwired.

**Files:**
- Modify: `configs/mcp.yaml`
- Modify: `src/miniresearch/config.py`
- Test: `tests/test_config.py`
- Test: `tests/test_logging.py`

**Suggested config knobs:**
- enabled
- path
- include_query_text
- include_source_ids

### Task 2.5: Document trace usage

**Objective:** Make the feature useful to public users and future maintainers.

**Files:**
- Create: `docs/workflows/trace-inspection.md`
- Modify: `README.md`

**Doc topics:**
- where traces are written
- how to inspect them
- how to disable or relocate them
- what is and is not guaranteed in v1.5

---

## Workstream 3 — Retrieval relevance cleanup

### Task 3.1: Map the current ranking logic

**Objective:** Understand exactly why noisy results appear today.

**Files:**
- Read: `src/miniresearch/filters.py`
- Read: `src/miniresearch/router.py`
- Create later: `tests/test_retrieval_quality.py`

**Substeps:**
1. Identify scoring contributions in `search_library()`.
2. Identify where candidate results are pruned, if anywhere.
3. Identify how `ask_research()` combines wiki, library, and PDF evidence.
4. Write down known failure patterns.

### Task 3.2: Add exact-match and normalized-match tiers

**Objective:** Make obviously correct metadata hits rank above generic token overlap.

**Files:**
- Modify: `src/miniresearch/filters.py`
- Test: `tests/test_retrieval_quality.py`

**Recommended ranking tiers:**
1. exact key match
2. exact DOI match
3. exact normalized title match
4. strong title containment / overlap
5. weighted metadata token overlap

**Implementation note:**
Use a simple, explicit ranking system first; avoid premature complexity.

### Task 3.3: Improve metadata weighting and pruning

**Objective:** Reduce weakly related candidate papers.

**Files:**
- Modify: `src/miniresearch/filters.py`
- Modify: `src/miniresearch/router.py`
- Test: `tests/test_retrieval_quality.py`
- Test: `tests/test_router_behavior.py`

**Substeps:**
1. Review weighting for title vs tags vs authors vs collections.
2. Introduce a minimum relevance threshold or candidate cap logic.
3. Prevent noisy metadata lists from being blindly shown in final answers.

### Task 3.4: Separate candidate retrieval from answer assembly

**Objective:** Stop `ask_research()` from acting like a simple concatenator.

**Files:**
- Modify: `src/miniresearch/router.py`
- Possible create: `src/miniresearch/synthesis_helpers.py`
- Test: `tests/test_router_behavior.py`

**Recommended internal phases:**
1. wiki retrieval
2. library candidate selection
3. PDF evidence retrieval
4. result pruning
5. answer assembly

### Task 3.5: Build retrieval regression tests

**Objective:** Preserve improvements and prevent backsliding.

**Files:**
- Create: `tests/test_retrieval_quality.py`
- Create: `tests/test_router_behavior.py`

**Suggested cases:**
- exact title query
- DOI query
- method query with expected canonical paper
- query known to previously return irrelevant metadata candidates
- evidence-style question that should trigger hybrid mode

### Task 3.6: Add manual verification notes

**Objective:** Create a small human-auditable set of queries for smoke checking.

**Files:**
- Create: `docs/evaluation/v15-smoke-queries.md`

**Suggested format:**
- query
- expected top paper(s)
- expected route mode
- expected failure modes to watch for

---

## Workstream 4 — Reproducibility and public setup baseline

### Task 4.1: Audit runtime dependencies

**Objective:** Ensure package metadata matches actual runtime needs.

**Files:**
- Modify: `pyproject.toml`
- Optional create/modify: `requirements-dev.txt`
- Test via clean install process later

**Substeps:**
1. Compare imports in runtime modules against declared dependencies.
2. Add missing runtime dependencies.
3. Separate optional vs required dependencies if necessary.
4. Keep dependency policy simple and documented.

### Task 4.2: Add `.env.example`

**Objective:** Make environment setup discoverable.

**Files:**
- Create: `.env.example`
- Modify: `README.md`

**Include placeholders for:**
- wiki generation provider
- embedding provider
- optional paperqa provider if retained in config
- path-related environment overrides only if actually supported

### Task 4.3: Review and clean config assumptions

**Objective:** Move personal machine assumptions out of the implied default story.

**Files:**
- Modify: `configs/paths.yaml`
- Modify: `configs/providers.yaml`
- Modify: `configs/wiki.yaml`
- Modify: `configs/rag.yaml`
- Modify: `src/miniresearch/config.py`
- Test: `tests/test_config.py`

**Substeps:**
1. Distinguish sample/default values from personal values.
2. Clarify required versus optional config fields.
3. Ensure path resolution logic is documented and testable.

### Task 4.4: Rewrite setup and workflow docs

**Objective:** Make public onboarding realistic.

**Files:**
- Modify: `README.md`
- Create: `docs/workflows/setup.md`
- Create: `docs/workflows/indexing.md`
- Create: `docs/workflows/mcp-usage.md`

**README should cover:**
- what the project is
- who it is for
- what it is not
- minimal setup
- common workflows
- current limitations

### Task 4.5: Add a clean-environment smoke checklist

**Objective:** Ensure public setup instructions are testable.

**Files:**
- Create: `docs/workflows/clean-setup-checklist.md`

**Checklist should include:**
- create environment
- install dependencies
- prepare config
- run sync
- run build index
- run MCP server
- perform one smoke query

---

## Workstream 5 — v1.5 final validation and release gate

### Task 5.1: Run full automated test suite

**Objective:** Verify stabilization work did not regress the existing system.

**Likely commands later during execution:**
- `python3 -m pytest tests/ -v`
- targeted MCP contract tests
- targeted retrieval quality tests
- targeted logging tests

### Task 5.2: Run manual smoke scenarios

**Objective:** Confirm that automated tests match actual usage.

**Manual scenarios:**
1. `search_library` exact title query
2. `search_wiki` semantic query
3. `ask_research` detail/evidence query
4. `save_to_wiki` valid writeback path
5. MCP stdio `tools/list`
6. MCP stdio `tools/call`

### Task 5.3: Confirm public-readiness minimum bar

**Objective:** Decide whether v1.5 is done.

**Questions to answer:**
- Can a technical outside user understand the project from docs?
- Are MCP contracts stable enough to depend on?
- Are retrieval results noticeably less noisy?
- Can traces explain what the system just did?
- Are the main environment assumptions explicit rather than hidden?

---

## 7. Files likely to change during v1.5

### Core code
- `src/miniresearch/mcp_server.py`
- `src/miniresearch/models.py`
- `src/miniresearch/router.py`
- `src/miniresearch/filters.py`
- `src/miniresearch/config.py`
- new: `src/miniresearch/logging.py`
- possible new: `src/miniresearch/mcp_contracts.py`

### Scripts
- `scripts/run_mcp_server.py`

### Config
- `configs/mcp.yaml`
- `configs/providers.yaml`
- `configs/paths.yaml`
- `configs/rag.yaml`
- `configs/wiki.yaml`

### Tests
- `tests/test_mcp_backend.py`
- new: `tests/test_mcp_contract.py`
- new: `tests/test_mcp_protocol.py`
- new: `tests/test_logging.py`
- new: `tests/test_retrieval_quality.py`
- new: `tests/test_router_behavior.py`
- `tests/test_config.py`

### Docs
- `README.md`
- new: `docs/mcp/tool-contracts.md`
- new: `docs/architecture/trace-schema.md`
- new: `docs/workflows/setup.md`
- new: `docs/workflows/indexing.md`
- new: `docs/workflows/mcp-usage.md`
- new: `docs/workflows/trace-inspection.md`
- new: `docs/workflows/clean-setup-checklist.md`
- new: `docs/evaluation/v15-smoke-queries.md`
- create later in v2: `docs/architecture/wiki-writeback-policy.md`

### Root-level public setup artifacts
- `pyproject.toml`
- new: `.env.example`

---

## 8. Test and validation plan

## Automated validation

### Existing suite to keep green
- `python3 -m pytest tests/ -v`

### New test groups to add
- MCP contract tests
- MCP protocol smoke tests
- trace logging tests
- retrieval ranking regression tests
- router behavior regression tests
- config and setup-related tests where feasible

## Manual validation

### MCP validation
- run stdio server and inspect `tools/list`
- call each tool once through the same interface
- verify error envelope for a bad tool name

### Retrieval validation
- exact title query returns intended paper first
- DOI lookup works
- detail question triggers expected route mode
- noisy broad query does not produce absurd top candidates

### Trace validation
- successful tool call writes a trace
- route decision appears for `ask_research`
- returned source ids are recorded

### Setup validation
- public docs are sufficient to describe a clean install
- `.env.example` and config docs are consistent

---

## 9. Risks, tradeoffs, and design cautions

### Risk 1: Over-designing the MCP layer
If contract cleanup becomes a mini-framework project, v1.5 will slow down.

**Mitigation:**
Use a simple single-source-of-truth registry, not a heavy abstraction.

### Risk 2: Retrieval “improvement” without measurable checks
If ranking changes are made without regression cases, quality may shift unpredictably.

**Mitigation:**
Add targeted query-based regression tests and smoke notes.

### Risk 3: Trace logging leaks too much by default
Publicly reusable software should not casually assume users want all query text persisted.

**Mitigation:**
Make logging configurable and document what is stored.

### Risk 4: Public docs drift from actual behavior
If docs are written too early, they may immediately go stale.

**Mitigation:**
Write or update docs after each stabilized workstream, not before.

### Risk 5: Attempting too much “publicization” in v1.5
v1.5 should not try to solve every downstream packaging concern.

**Mitigation:**
Keep the goal modest: trustworthy baseline, not full ecosystem maturity.

---

## 10. Open questions before execution

1. For v1.5, should trace logging include full query text by default, or should that default to off for privacy reasons?
2. Should `save_to_wiki` support custom `wiki_root` in the public contract, or should that remain an internal/test-only concern?
3. Do you want `paperqa` to remain in the near-term public story for v1.5/v2, or should docs present current deep retrieval primarily as the existing vector/evidence stack?
4. Should `queries/` be documented as durable knowledge, semi-ephemeral outputs, or both depending on policy?
5. Do you want v2 to target only individual technical users, or also small-lab reproducibility from the first public release?

---

## 11. Immediate execution recommendation

If starting implementation next, the most sensible first batch is:

### Batch 1
1. Task 1.1 inventory current tool contracts
2. Task 1.2 choose single contract source
3. Task 1.3 resolve mismatches
4. Task 1.5 add MCP contract tests
5. Task 1.6 write MCP contract docs

### Batch 2
6. Task 2.1 define trace schema
7. Task 2.2 add logging module
8. Task 2.3 emit traces from tools
9. Task 2.4 add config controls
10. Task 2.5 document trace usage

### Batch 3
11. Task 3.1 map current ranking logic
12. Task 3.2 add exact-match tiers
13. Task 3.3 improve weighting and pruning
14. Task 3.5 add retrieval regressions
15. Task 3.6 add manual smoke notes

### Batch 4
16. Task 4.1 audit dependencies
17. Task 4.2 add `.env.example`
18. Task 4.3 clean config assumptions
19. Task 4.4 rewrite setup docs
20. Task 4.5 add clean-setup checklist

---

## 12. Final recommendation

The correct near-term strategy is not to enlarge the project, but to harden it.

v1.5 should make `paper-compass` honest, inspectable, and reproducible.
v2 should make it publicly reusable without introducing UI-driven sprawl.

That sequencing best matches your stated priorities:
- public and reusable,
- academically trustworthy,
- MCP/agent-first,
- no dedicated UI.
