# Plan: Wiki Prompt Customization (v1.2.1)

## Goal

Allow users to select wiki-building prompts by discipline, use a general default, or provide custom prompts. Move the current economics-specific prompts to a discipline preset.

## Current State

- `src/paper_compass/wiki_gen.py` hardcodes 4 prompt files in `__init__`:
  - `prompts/wiki_router.md` — paper type classifier (already field-agnostic)
  - `prompts/wiki_econ_overview.md` — economics-specific overview prompt
  - `prompts/wiki_econ_empirical.md` — economics-specific empirical design prompt
  - `prompts/wiki_ingest.md` — generic fallback (too sparse, ~14 lines)
- `paper-compass init` only configures LLM + embedding endpoints
- No mechanism for prompt selection or customization
- `configs/wiki.yaml` `prompt_files` section references economics prompts but is not actually read by `wiki_gen.py`

## Target State

- **Default prompts** (`prompts/`): General, discipline-agnostic wiki prompts suitable for any researcher
- **Discipline presets** (`prompts/disciplines/{discipline}/`): Each discipline has its own prompt set
  - `economics/` — current economics prompts moved here
  - Future disciplines added via PR
- **Custom path**: Users can point `WIKI_PROMPT` to any directory with their own prompt files
- **`paper-compass init`** adds a Step 3 asking the user to select prompt mode: default / preset (choose discipline) / custom path
- **`wiki_gen.py`** loads prompts based on `WIKI_PROMPT` env var with directory-based resolution

## Step-by-Step Plan

### Step 1: Create default (general) prompt files

Create two new prompt files under `prompts/` that are discipline-agnostic:

**`prompts/wiki_overview.md`** — General academic wiki overview prompt
- Same structure as `wiki_econ_overview.md` but:
  - Remove economics-specific framing ("empirical corporate/labor economics, family firms, causal inference")
  - Replace with general academic framing
  - Keep tag taxonomy but make it broad (add more disciplines: sociology, psychology, medicine, etc. or remove discipline-specific tags and make methods-focused)
  - Remove references to "被解释变量"/"解释变量" etc.

**`prompts/wiki_empirical.md`** — General empirical design prompt
- Same structure as `wiki_econ_empirical.md` but:
  - Remove Chinese economics jargon (CSMAR, CNRDS references)
  - Use general academic terminology instead of econ-specific variable naming
  - Keep the section structure (Data, Identification, Robustness, Mechanism/Heterogeneity)

**Files to create:**
- `prompts/wiki_overview.md`
- `prompts/wiki_empirical.md`

### Step 2: Create discipline directory structure + move economics prompts

```
prompts/
├── wiki_router.md              (already general, stays)
├── wiki_overview.md            (NEW — general default)
├── wiki_empirical.md           (NEW — general default)
├── wiki_ingest.md              (stays as fallback)
├── wiki_query.md               (unchanged)
├── wiki_merge.md               (unchanged)
├── router_classify.md          (unchanged)
├── rag_answer.md               (unchanged)
└── disciplines/
    └── economics/
        ├── wiki_overview.md    (from wiki_econ_overview.md)
        └── wiki_empirical.md   (from wiki_econ_empirical.md)
```

**Actions:**
1. Create `prompts/disciplines/economics/` directory
2. Copy `wiki_econ_overview.md` → `prompts/disciplines/economics/wiki_overview.md`
3. Copy `wiki_econ_empirical.md` → `prompts/disciplines/economics/wiki_empirical.md`
4. Keep `wiki_econ_overview.md` and `wiki_econ_empirical.md` as symlinks or backward-compat aliases (see Step 5)

### Step 3: Add `WIKI_PROMPT` env var support

Define semantics of `WIKI_PROMPT`:
- `default` (or unset/empty): use `prompts/wiki_overview.md` + `prompts/wiki_empirical.md`
- `economics`: use `prompts/disciplines/economics/wiki_overview.md` + `prompts/disciplines/economics/wiki_empirical.md`
- Any absolute or relative path: use `{path}/wiki_overview.md` + `{path}/wiki_empirical.md` (relative paths resolve from project root)
- `router` always uses `prompts/wiki_router.md` regardless of discipline (classification is universal)

**Additional env var (optional but nice):**
- `WIKI_ROUTER_PROMPT` — override the router prompt path (for users who want custom classification logic)

### Step 4: Update `wiki_gen.py` to resolve prompts dynamically

**Current** (hardcoded in `__init__`):
```python
self._router_prompt = self._load("prompts/wiki_router.md")
self._overview_prompt = self._load("prompts/wiki_econ_overview.md")
self._empirical_prompt = self._load("prompts/wiki_econ_empirical.md")
self._fallback_prompt = self._load("prompts/wiki_ingest.md")
```

**New** (resolve based on WIKI_PROMPT):
```python
def _resolve_prompt_dir(self) -> str:
    """Resolve the prompt directory from WIKI_PROMPT env var."""
    wiki_prompt = os.environ.get("WIKI_PROMPT", "default").strip()
    if wiki_prompt == "default":
        return "prompts"  # default prompts live alongside router
    elif wiki_prompt in self._available_disciplines():
        return f"prompts/disciplines/{wiki_prompt}"
    else:
        # Custom path
        return wiki_prompt

def _available_disciplines(self) -> list[str]:
    """Discover discipline directories under prompts/disciplines/."""
    disciplines_dir = Path("prompts/disciplines")
    if not disciplines_dir.exists():
        return []
    return [
        d.name for d in disciplines_dir.iterdir()
        if d.is_dir() and (d / "wiki_overview.md").exists()
    ]
```

Then in `__init__`:
```python
prompt_dir = self._resolve_prompt_dir()
self._router_prompt = self._load("prompts/wiki_router.md")
self._overview_prompt = self._load(f"{prompt_dir}/wiki_overview.md")
self._empirical_prompt = self._load(f"{prompt_dir}/wiki_empirical.md")
self._fallback_prompt = self._load("prompts/wiki_ingest.md")
```

### Step 5: Backward compatibility

Keep the old `wiki_econ_overview.md` and `wiki_econ_empirical.md` in `prompts/` temporarily for users who upgrade without changing config. Options:

**Option A (preferred):** Keep the old files in place but make them thin wrappers that explain the migration:
```
# This file has been moved to prompts/disciplines/economics/wiki_overview.md
# as part of the v1.2.1 prompt customization feature.
# Set WIKI_PROMPT=economics in your .env or run `paper-compass init` to update.
```

**Option B:** Symlink them to the discipline directory (messy on Windows, fragile in git)

**Option C:** Just move them and add a clear migration note in the changelog/README

Recommend **Option A** — keep old files as migration stubs for one version, remove in v1.3.0. Add a deprecation warning log in `wiki_gen.py` if it detects the old econ files are being used directly.

### Step 6: Update `paper-compass init` to prompt for wiki prompt selection

Add Step 3 after LLM + embedding config in `_interactive_*` flow:

```
  ┌─ Step 3: Wiki Prompt Style ─────────────────────────────────────┐

  Wiki prompts control how LLMs generate structured knowledge pages
  from your papers. Choose a prompt style:

    1) Default (通用) — General-purpose academic prompts, suitable
       for any discipline

    2) Preset: Economics (经济学) — Specialized prompts for empirical
       economics papers (DID, IV, RDD, mechanism analysis, etc.)

    3) Custom path — Use your own prompt files

  Choose [1]:
```

**Implementation in `configure.py`:**
- Add `_interactive_wiki_prompt()` function
- Call it after `_interactive_embedding()` in `execute_init()`
- Write `WIKI_PROMPT` to `.env`
- Handle non-interactive mode: support `--wiki-prompt default|economics|/path/to/prompts`

**Non-interactive CLI addition:**
```
paper-compass init --wiki-prompt economics
paper-compass init --wiki-prompt /home/user/my-prompts
```

### Step 7: Update `configs/wiki.yaml`

Update the `prompt_files` section to reflect the new structure:
```yaml
prompt_files:
  router: prompts/wiki_router.md
  ingest: prompts/wiki_ingest.md
  query: prompts/wiki_query.md
  merge: prompts/wiki_merge.md
  # wiki_overview and wiki_empirical are resolved dynamically
  # based on WIKI_PROMPT env var (default|economics|custom_path)
```

Add a new section documenting the prompt selection:
```yaml
wiki_prompt:
  mode: env  # resolved from WIKI_PROMPT env var
  options:
    - default
    - economics
    - custom_path
```

### Step 8: Update tests

**New test file: `tests/test_wiki_prompt_resolution.py`**
- Test `_resolve_prompt_dir()` with `WIKI_PROMPT=default`
- Test `_resolve_prompt_dir()` with `WIKI_PROMPT=economics`
- Test `_resolve_prompt_dir()` with custom path
- Test `_available_disciplines()` discovers economics directory
- Test fallback when discipline directory doesn't have required files

**Update existing: `tests/test_cli_configure.py`**
- Add test for `--wiki-prompt` arg parsing
- Add test for non-interactive wiki prompt selection
- Verify `WIKI_PROMPT` gets written to `.env`

**Update existing: `tests/test_config.py`**
- Verify `WIKI_PROMPT` is recognized as a known env var

### Step 9: Update README.md

- Update version badge to 1.2.1
- Add section "Wiki 提示词选择" explaining:
  - Three modes: default, discipline presets, custom
  - How to switch after init: edit `WIKI_PROMPT` in `.env`
  - Preset economics details
  - How to contribute new discipline presets (PR welcome)
  - Mention the two-pass architecture (classify → generate) and that users can design their own classification logic

### Step 10: Bump version to 1.2.1

Update `pyproject.toml`: `version = "1.2.1"`

## Files to Change

| File | Action | Description |
|------|--------|-------------|
| `prompts/wiki_overview.md` | **Create** | General default overview prompt |
| `prompts/wiki_empirical.md` | **Create** | General default empirical prompt |
| `prompts/disciplines/economics/wiki_overview.md` | **Create** | Economics overview prompt (from wiki_econ_overview.md) |
| `prompts/disciplines/economics/wiki_empirical.md` | **Create** | Economics empirical prompt (from wiki_econ_empirical.md) |
| `prompts/wiki_econ_overview.md` | **Modify** | Replace with migration stub (keep for backward compat) |
| `prompts/wiki_econ_empirical.md` | **Modify** | Replace with migration stub (keep for backward compat) |
| `src/paper_compass/wiki_gen.py` | **Modify** | Add `_resolve_prompt_dir()`, `_available_disciplines()`, dynamic prompt loading |
| `src/paper_compass/cli/configure.py` | **Modify** | Add `_interactive_wiki_prompt()`, `--wiki-prompt` arg, write `WIKI_PROMPT` to `.env` |
| `src/paper_compass/cli/arg_utils.py` | **Modify** | If `--wiki-prompt` needs special parsing (likely not — it's a single string) |
| `configs/wiki.yaml` | **Modify** | Update `prompt_files` section, add `wiki_prompt` section |
| `src/paper_compass/config.py` | **Modify** | Add `WIKI_PROMPT` to known env vars if needed |
| `pyproject.toml` | **Modify** | Bump version to 1.2.1 |
| `tests/test_wiki_prompt_resolution.py` | **Create** | New tests for prompt resolution logic |
| `tests/test_cli_configure.py` | **Modify** | Add wiki prompt selection tests |
| `README.md` | **Modify** | Add wiki prompt selection docs, update version |
| `AGENTS.md` | **Modify** | Update init step description to mention prompt selection |

## Tests / Validation

1. **Unit tests**: `test_wiki_prompt_resolution.py` — 6-8 tests covering all resolution paths
2. **CLI tests**: Non-interactive init with `--wiki-prompt` flag
3. **Integration**: Run `paper-compass init` interactively, verify `.env` contains `WIKI_PROMPT`
4. **Existing tests**: All 102 existing tests must continue to pass
5. **Smoke test**: Generate a wiki page with each prompt mode, verify output structure

## Risks & Tradeoffs

| Risk | Mitigation |
|------|------------|
| Default prompts too generic → wiki quality drops for econ users | Economics preset is one `WIKI_PROMPT=economics` away; README clearly documents this |
| Custom prompt users forget required sections → broken wiki output | `wiki_gen.py` should validate that `wiki_overview.md` and `wiki_empirical.md` exist in the chosen directory; log clear error if missing |
| Old scripts that hardcode `wiki_econ_overview.md` break | Keep migration stubs in place for one version; add deprecation warning |
| Discipline directory discovery fragile on some filesystems | Use `Path.iterdir()` with try/except; graceful degradation to default |

## Open Questions

1. **Should `wiki_router.md` also be discipline-customizable?** The current router (classify as empirical/theoretical/review/descriptive) is already general enough. I'd keep it unified for now and only add `WIKI_ROUTER_PROMPT` as an optional escape hatch if needed.
2. **Should the economics discipline directory also have its own `wiki_router.md`?** Not needed — classification logic is the same across disciplines. If someone wants economics-specific classification (e.g. further sub-classifying empirical into DID/IV/RDD), that's a separate feature.
3. **Where should the custom prompt path be relative to?** `.env`-relative or project-root-relative? Recommend: if the path starts with `/` or `.\` or `~/`, use as-is; otherwise resolve relative to the project root (where `.env` lives).
