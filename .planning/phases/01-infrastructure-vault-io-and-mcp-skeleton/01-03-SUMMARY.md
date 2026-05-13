---
phase: 01-infrastructure-vault-io-and-mcp-skeleton
plan: 03
subsystem: vault-io
tags: [python, frontmatter, layout-io, round-trip, tiktoken, lint, monorepo-scan]

# Dependency graph
requires:
  - phase: 01-infrastructure-vault-io-and-mcp-skeleton (plan 01)
    provides: cores/vault-io package skeleton + workspace pyproject + pytest wiring
provides:
  - All vault-io modules ported with import surgery clean (verbatim or adapted per plan)
  - VAULT-04 round-trip golden gate green against 148-page committed real-vault fixture
  - VAULT-05 truncated-frontmatter guard preserved verbatim (skip + stderr + unchanged bytes)
  - VAULT-06 _is_placeholder_target relocated to lint/common.py (sits next to WIKILINK_RE)
  - VAULT-07 surface check — every ported module importable; detect_containers smoke green
  - layout_io.write_layout proven byte-stable via VAULT-02 smoke test (idempotent + read→write round-trip)
  - _workspace.resolve_wiki_and_repo raises actionable RuntimeError on missing config (D-09)
  - git_state.py ported (Rule 2 deviation — required so scan_monorepo's lazy imports satisfy import-surgery rule)
affects: [phase-02-subagent-fan-out, phase-03-query-vertical-slice, phase-05-remaining-commands]

# Tech tracking
tech-stack:
  added: []  # no new deps; ports use python-frontmatter (already in pyproject) + tiktoken (already in pyproject) + stdlib
  patterns:
    - "Import surgery rule: lattice_wiki_core.X → vault_io.X, drop _version_check"
    - "Hand-rolled YAML emitter for layout block (stdlib-only, byte-stable, no PyYAML)"
    - "Raw-string write path for frontmatter (never frontmatter.dumps; preserves vault byte-shape)"
    - "Truncated-frontmatter guard: parts = raw.split('---', 2); if len(parts) < 3: skip+stderr"
    - "Sentinel HTML comments preserved verbatim across the port (<!-- lattice-wiki:layout:start -->)"
    - "Workspace resolver raises on misconfig instead of falling back silently (D-09 actionable-error)"

key-files:
  created:
    - cores/vault-io/src/vault_io/layout_io.py
    - cores/vault-io/src/vault_io/update_tokens.py
    - cores/vault-io/src/vault_io/_workspace.py
    - cores/vault-io/src/vault_io/detect_containers.py
    - cores/vault-io/src/vault_io/append_log.py
    - cores/vault-io/src/vault_io/update_index.py
    - cores/vault-io/src/vault_io/graph_analyzer.py
    - cores/vault-io/src/vault_io/scan_monorepo.py
    - cores/vault-io/src/vault_io/init_vault.py
    - cores/vault-io/src/vault_io/git_state.py
    - cores/vault-io/src/vault_io/lint/__init__.py
    - cores/vault-io/src/vault_io/lint/common.py
    - cores/vault-io/tests/conftest.py
    - cores/vault-io/tests/fixtures/round-trip-vault/ (148 .md pages + .templates + .gitignore)
    - cores/vault-io/tests/test_round_trip.py
    - cores/vault-io/tests/test_truncated_frontmatter.py
    - cores/vault-io/tests/test_wikilink_predicate.py
    - cores/vault-io/tests/test_layout_io_smoke.py
    - cores/vault-io/tests/test_ports_importable.py
  modified:
    - cores/vault-io/src/vault_io/__init__.py (re-exports read_layout, write_layout, resolve_wiki_and_repo)

key-decisions:
  - "Ported git_state.py as well (Rule 2): scan_monorepo's lazy imports of lattice_wiki_core.git_state would have either left lattice_wiki_core references in src/ (failing the import-surgery acceptance criterion) or broken Phase 5 functionality. Porting the small stdlib-only file is cleaner than either alternative."
  - "Plan task 2 mentioned update_page signature as `update_page(path, enc, *, dry_run=False)` (kwarg-only). The verbatim source signature is `update_page(path, enc, dry_run=False)` (positional default). Kept the source signature — verbatim port rule wins. Tests call with dry_run as kwarg, which works either way."
  - "init_vault.py: dropped `from lattice_wiki_core import __version__` and the workspace_init() call site; replaced with TODO Phase 5 comment per plan §init_vault.py adaptation."

patterns-established:
  - "vault-io as the canonical write boundary: any write to a vault page must route through update_tokens.update_page / layout_io.write_layout (no exceptions). VAULT-04 round-trip gate enforces this."
  - "Round-trip fixture committed verbatim from real vault (148 pages, no sanitization per D-05). Env override CODE_WIKI_REAL_VAULT_PATH lets future tests opt into Pat's live vault."
  - "lint/common.py is the home for wikilink regex + placeholder predicate. Phase 5 lint commands import from this single module."

requirements-completed: [VAULT-01, VAULT-02, VAULT-03, VAULT-04, VAULT-05, VAULT-06, VAULT-07]

# Metrics
duration: ~20min
completed: 2026-05-13
---

# Phase 1 Plan 03: Vault IO Port + Round-Trip Golden Gate Summary

**11 lattice-wiki-core modules ported into cores/vault-io with import surgery clean, plus git_state for full surface compliance; VAULT-04 round-trip gate green on the 148-page committed real-vault fixture.**

## Performance

- **Duration:** ~20 minutes
- **Completed:** 2026-05-13T17:35:36Z
- **Tasks:** 3 of 3 (autonomous, no checkpoints)
- **Files created:** 19 (12 src modules incl. `lint/__init__.py` + git_state.py; 6 test files; 1 fixture tree of 148+ pages)
- **Files modified:** 1 (`vault_io/__init__.py`)

## Accomplishments

- **VAULT-04 round-trip golden gate is GREEN.** Reading every fixture page with python-frontmatter and re-writing via `update_vault` produces a byte-identical second pass (verified by sha256 tree-hash equality and `git diff --no-index`). This gate locks in vault byte-stability for every Phase 5 command that touches writes.
- All 11 ported modules (layout_io, update_tokens, _workspace, detect_containers, append_log, update_index, graph_analyzer, scan_monorepo, init_vault, lint/common, plus the Rule-2 git_state addition) live under `cores/vault-io/src/vault_io/` with `from lattice_wiki_core.*` references removed and replaced with `from vault_io.*` where applicable.
- Layout block emitter proven byte-stable (VAULT-02): repeated `write_layout` produces identical bytes; read→write round-trip is idempotent; `vault_dir: null` is emitted correctly.
- `_is_placeholder_target` relocated to `lint/common.py` (VAULT-06): four-case predicate suite green.
- `_workspace.resolve_wiki_and_repo` raises actionable `RuntimeError` when neither arg nor `CODE_WIKI_REAL_VAULT_PATH` is provided (D-09).

## Task Commits

1. **Task 1: Commit real-vault fixture + Wave-0 blocking tests** — `e52af19` (test)
2. **Task 2: Port all vault-io modules with import surgery** — `38dd327` (feat)
3. **Task 3: Layout-IO byte-stability + ports-importable smoke** — `3993acd` (test)

_No Plan-metadata commit yet — orchestrator owns shared writes in worktree mode._

## Ported Modules (one line per module)

| Module | Port Type |
|---|---|
| `layout_io.py` | verbatim port (docstring header only: "lattice-wiki" → "vault-io"); sentinel strings preserved |
| `update_tokens.py` | verbatim port + import surgery; truncated-frontmatter guard + raw-string write path preserved exactly |
| `detect_containers.py` | verbatim port + import surgery |
| `append_log.py` | verbatim port + import surgery (also dropped check_for_updates call) |
| `update_index.py` | verbatim port + import surgery |
| `graph_analyzer.py` | verbatim port + import surgery |
| `scan_monorepo.py` | verbatim port + import surgery; lazy imports rewired to vault_io.git_state and vault_io.detect_containers |
| `init_vault.py` | adapted port; workspace_init() removed (TODO Phase 5); `__version__` import dropped; lattice_wiki_core imports rewritten |
| `_workspace.py` | adapted port; raises RuntimeError on misconfig; no lattice-workspace fallback |
| `lint/common.py` | verbatim port + relocated `_is_placeholder_target` from upstream lint_wiki.py |
| `git_state.py` | added (Rule 2 deviation — see below) |

## Round-Trip Fixture

- **Path:** `cores/vault-io/tests/fixtures/round-trip-vault/`
- **Source:** `/Users/pat/Personal/lattice/lattice/wiki/` copied verbatim (no sanitization per D-05)
- **Page count:** 148 `.md` files
- **Round-trip test runtime:** **<1 second** (well under the plan's 10-30s expectation; the suite is small)

## Test Suite Output (last 30 lines, `uv run --package vault-io pytest -v`)

```
============================= test session starts ==============================
platform darwin -- Python 3.11.15, pytest-9.0.3, pluggy-1.6.0
cachedir: .pytest_cache
rootdir: /Users/pat/Personal/deep-agents/.claude/worktrees/agent-a7801010914a861c0
configfile: pyproject.toml
plugins: syrupy-5.1.0, asyncio-1.3.0, langsmith-0.8.3, anyio-4.13.0
asyncio: mode=Mode.STRICT, ...
collecting ... collected 15 items

agents/code-wiki-agent/tests/unit/test_cli_help.py::test_cli_help_exits_zero PASSED [  6%]
cores/vault-io/tests/test_layout_io_smoke.py::test_write_layout_is_byte_stable PASSED [ 13%]
cores/vault-io/tests/test_layout_io_smoke.py::test_write_layout_replaces_existing_block PASSED [ 20%]
cores/vault-io/tests/test_layout_io_smoke.py::test_write_layout_handles_null_vault_dir PASSED [ 26%]
cores/vault-io/tests/test_ports_importable.py::test_all_ports_importable PASSED [ 33%]
cores/vault-io/tests/test_ports_importable.py::test_detect_containers_smoke PASSED [ 40%]
cores/vault-io/tests/test_ports_importable.py::test_resolve_wiki_and_repo_raises_on_no_config PASSED [ 46%]
cores/vault-io/tests/test_ports_importable.py::test_resolve_wiki_and_repo_honors_env_var PASSED [ 53%]
cores/vault-io/tests/test_round_trip.py::test_round_trip_all_fixture_pages PASSED [ 60%]
cores/vault-io/tests/test_truncated_frontmatter.py::test_update_page_skips_truncated_frontmatter PASSED [ 66%]
cores/vault-io/tests/test_truncated_frontmatter.py::test_truncated_frontmatter_emits_stderr_warning PASSED [ 73%]
cores/vault-io/tests/test_wikilink_predicate.py::IsPlaceholderTargetTest::test_detects_angle_brackets_as_placeholder PASSED [ 80%]
cores/vault-io/tests/test_wikilink_predicate.py::IsPlaceholderTargetTest::test_detects_ellipsis_as_placeholder PASSED [ 86%]
cores/vault-io/tests/test_wikilink_predicate.py::IsPlaceholderTargetTest::test_rejects_empty_and_simple_targets PASSED [ 93%]
cores/vault-io/tests/test_wikilink_predicate.py::IsPlaceholderTargetTest::test_rejects_normal_wiki_links PASSED [100%]

============================== 15 passed in 0.40s ==============================
```

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 2 - Missing critical functionality] Ported `git_state.py`**
- **Found during:** Task 2 (porting `scan_monorepo.py`)
- **Issue:** `scan_monorepo.py` has lazy `from lattice_wiki_core.git_state import ...` inside `attach_changed_files()` and `compute_state_gate()`. The plan's import-surgery rule says to replace `lattice_wiki_core.X` with `vault_io.X` — but `git_state` was not on the plan's port list. Two bad options: (a) leave the `lattice_wiki_core` reference, failing the acceptance criterion `! grep -rn 'lattice_wiki_core' cores/vault-io/src/`; (b) replace prefix to `vault_io.git_state` but never port the module, breaking Phase 5's `scan` command at runtime when those lazy paths fire.
- **Fix:** Ported `git_state.py` verbatim (stdlib-only, 72 lines). No surface changes, no behavior changes.
- **Files modified:** Added `cores/vault-io/src/vault_io/git_state.py`.
- **Commit:** `38dd327`

**2. [Rule 1 - Bug] Removed `lattice_wiki_core` / `lattice_workspace` references from docstrings**
- **Found during:** Task 2 verification
- **Issue:** After import surgery, ported docstrings/comments still mentioned `lattice_wiki_core.init_vault`, `lattice_workspace.init`, and `frontmatter.dumps()`. The acceptance grep (`! grep -rn 'lattice_wiki_core\|lattice_workspace' cores/vault-io/src/`) treats these as failures because it's a literal substring check, not an import check.
- **Fix:** Reworded the docstrings to "the upstream source" / "the YAML serializer" without losing the historical pointer.
- **Files modified:** `init_vault.py`, `lint/common.py`, `update_tokens.py`.
- **Commit:** Same as port commit `38dd327` (fix applied before commit).

### Plan-Spec Adjustments

**3. [Spec-deviation] Kept verbatim `update_page` signature (positional `dry_run`)**
- **Plan said:** `update_page(path: Path, enc, *, dry_run: bool=False)` (kwarg-only after `*`)
- **Source has:** `update_page(path: Path, enc, dry_run: bool=False)` (positional with default)
- **Resolution:** Kept the source signature — Plan task 2's action explicitly says "VERBATIM" and preserves signatures. Tests call with `dry_run=False` as a kwarg, which works under either signature. No risk of breakage.

## Known Stubs

- `vault_io.init_vault.init_wiki` has a `TODO Phase 5: workspace init (lattice-workspace equivalent)` comment marking where the dropped `workspace_init()` call would resume. This is an intentional, planned stub per the plan; Phase 5 will reintroduce the workspace bootstrap. Tracked for future plans, not a Phase 1 blocker.
- `vault_io.git_state.is_clean_main` requires `main` branch — that is verbatim source behavior and unrelated to deep-agents needs. Phase 5 may need to relax this; out of scope here.

## Threat Flags

None — no new network endpoints, auth paths, file access patterns, or schema changes at trust boundaries. All writes still route through the existing vault-write boundary (`update_tokens.update_page` and `layout_io.write_layout`), which is what the threat model already covers (T-1-06 round-trip mitigation is the VAULT-04 test, now green).

## Self-Check: PASSED

- ✅ `cores/vault-io/src/vault_io/layout_io.py` — exists, contains `def write_layout` and `<!-- lattice-wiki:layout:start -->`
- ✅ `cores/vault-io/src/vault_io/update_tokens.py` — exists, contains `no closing frontmatter fence` and `raw.split("---", 2)`
- ✅ `cores/vault-io/src/vault_io/_workspace.py` — exists, contains `CODE_WIKI_REAL_VAULT_PATH` and `raise RuntimeError`
- ✅ `cores/vault-io/src/vault_io/lint/common.py` — exists, contains `def _is_placeholder_target` and `WIKILINK_RE`
- ✅ `cores/vault-io/tests/fixtures/round-trip-vault/` — 148 `.md` files (≥100)
- ✅ All ported modules listed in `files_modified` exist
- ✅ Commits `e52af19`, `38dd327`, `3993acd` all present in `git log`
- ✅ `! grep -rn 'lattice_wiki_core\|lattice_workspace' cores/vault-io/src/` — clean
- ✅ `! grep -rn 'frontmatter\.dumps' cores/vault-io/src/` — clean
- ✅ `uv run --package vault-io pytest -x -q` — 15 passed
