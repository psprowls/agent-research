# Phase 21: Rename code-wiki-agent → graph-wiki-agent — Pattern Map

**Mapped:** 2026-05-19
**Files analyzed:** ~308 hit-bearing files (from `grep -rEl 'code-wiki-agent|code_wiki_agent|code-wiki-mcp|code_wiki_mcp'`), grouped into 9 role classes
**Analogs found:** 9 / 9 (every class has a direct Phase 12 precedent)
**Direct precedent:** Phase 12 (`.planning/milestones/v1.2-phases/12-drift-backport-ecosystem-rebrand-m2/`) — same shape (sweep + grep-gate), same tooling (`scripts/check-brand.sh` + `.brand-grep-allow`), same atomic-commit cadence (SQ-02 + SQ-03)

---

## File Classification

Phase 21 does not "create new files" in the classical sense — the work is overwhelmingly **rename + grep-sweep + manifest edit**. The single net-new artifact is the `.brand-grep-allow` extension entries (and any new helper if discretion calls for it). Every other "modified file" maps cleanly to one of the role classes below.

| Role Class | Data Flow | Representative File(s) | Phase 12 Analog | Match Quality |
|------------|-----------|------------------------|-----------------|---------------|
| `dir-move-git-mv` | filesystem move | `agents/code-wiki-agent/` → `agents/graph-wiki-agent/`; `src/code_wiki_agent/` → `src/graph_wiki_agent/`; `src/code_wiki_mcp/` → `src/graph_wiki_mcp/` | Phase 12 had **no analog** — Phase 12 swept content but did NOT rename a package directory. This is a **net-new technique for this codebase** (see "No Analog" section). | **no analog** |
| `pyproject-manifest` | declarative-config | `agents/code-wiki-agent/pyproject.toml` (`name`, `[project.scripts]`) + root `uv.lock` regenerate | Phase 12 plan 03 Task 1 (manifest-adjacent edits in `packages/vault-io/`) | **partial** — Phase 12 didn't rename a `name =` field but touched neighboring config |
| `python-module-sweep` | text-substitute | All `*.py` under `agents/code-wiki-agent/src/` + `agents/code-wiki-agent/tests/` — imports, identifiers (`CodeWikiAgentError` → `GraphWikiAgentError`), string literals, log/print messages | Phase 12 plan 03 Task 2 (rebrand `agents/code-wiki-agent/src/code_wiki_agent/`) | **exact** |
| `plugin-shellout-script` | subprocess invocation | `plugins/graph-wiki/skills/graph-wiki/scripts/{scan_monorepo,init_vault,ingest_source,lint_wiki,wiki_search}.py` (5 files; literal `["code-wiki-agent", "<cmd>"]`) | Phase 12 plan 03 Task 2 (covered `plugins/` placeholder); actual plugin shellouts were authored in Phase 14 | **role-match** — text-sweep mechanic identical; surface didn't exist in Phase 12 |
| `trace-dir-reference` | path-string | `.code-wiki/traces/` → `.graph-wiki/traces/` references in `agents/code-wiki-agent/src/`, `agents/code-wiki-agent/tests/`, `packages/eval-harness/`, `packages/subagent-runtime/`, `packages/prompt-sources/`, `docs/trace-schema.md`, `.planning/PROJECT.md` | Phase 12 plan 03 Task 1 (path-fragment sweep across packages/) | **exact** |
| `repo-doc` | prose | Root `README.md`, root `CLAUDE.md` | Phase 12 plan 03 Task 4 (`CLAUDE.md` rebrand of live prose) | **exact** |
| `plugin-doc` | prose | `plugins/graph-wiki/{README.md,CLAUDE.md}`, `plugins/graph-wiki/skills/graph-wiki/README.md`, `plugins/graph-wiki/.claude-plugin/plugin.json` | Phase 12 plan 03 Task 2 (allowlisted Phase 14 plugin docs); plugin docs were authored in Phase 14 | **role-match** |
| `planning-doc-sweep` | prose, bulk | All 188 `.planning/` files (STATE.md, ROADMAP.md, REQUIREMENTS.md, PROJECT.md, prior-phase CONTEXT/PLAN/VERIFICATION/SUMMARY, milestones/v1.0..v1.2 archives, RETROSPECTIVE.md, intel/stack.json, sketches, threads/archive) | Phase 12 plan 03 Task 4 (live planning surface only — Phase 12 explicitly **skipped** historical archives per R-03; **Phase 21 D-05 overrides R-03 and sweeps everything**) | **role-match with documented divergence** |
| `skill-doc-sweep` | prose | `.claude/skills/spike-findings-deep-agents/SKILL.md` + active reference files under `.claude/skills/spike-findings-deep-agents/references/*.md` (leaving `.planning/spikes/00{1,2}/sources/**/*.md` verbatim per D-07) | Phase 12 plan 03 Task 4 (skill/doc prose sweep with historical-preservation carveout) | **exact** |
| `brand-grep-gate-extension` | shell-script + allowlist | `scripts/check-brand.sh` regex extension, `.brand-grep-allow` additions | Phase 12 plan 04 Task 1 (initial authoring of the same files) | **exact** — same files, same tool, same allowlist format |
| `top-level-integration-gate-test` | test-file | `tests/test_integration_gate.py` (CLI/console-script invocations) | Phase 12 plan 03 Task 1 (test-file string sweep with disambiguation rule) | **exact** |

---

## Pattern Assignments

### Class: `dir-move-git-mv`

**Analog:** none in this repo. Phase 12 swept content within stable directories. Phase 11 (`11-workspace-io-port-m1`) introduced a new package but did not move an existing one.

**Pattern to apply (per CONTEXT.md D-09 layer 1 + D-08 worktree):**
1. Create worktree: `git worktree add ../deep-agents-rename rename-21`.
2. Inside the worktree, the three moves are independent and can be batched into ONE commit (D-09 layer 1):
   ```bash
   git mv agents/code-wiki-agent agents/graph-wiki-agent
   git mv agents/graph-wiki-agent/src/code_wiki_agent agents/graph-wiki-agent/src/graph_wiki_agent
   git mv agents/graph-wiki-agent/src/code_wiki_mcp agents/graph-wiki-agent/src/graph_wiki_mcp
   ```
   `git mv` (not `mv` + `git add`) is mandatory — preserves blame/history per CONTEXT.md §"Established Patterns".
3. Commit subject suggestion (planner's discretion per D-09): `refactor: git mv code-wiki-agent → graph-wiki-agent (dir + src modules)`.
4. **Per-commit gate (D-11):** at this layer the codebase is **broken** — imports still say `code_wiki_agent`. Per-commit gate is `uv sync` only (NOT pytest, which will fail). Planner must call this out explicitly in the layer-1 PLAN: pytest-green starts at layer 3, not layer 1. This is the one place Phase 12's SQ-03 "green per commit" rule must be relaxed; D-11 already anticipates this (`or equivalent scope`).

**Why a separate commit:** matches D-09's layered cadence; the `git mv` is recoverable on its own, and tangling it with import sweeps obscures which line moved vs. which line changed.

---

### Class: `pyproject-manifest`

**Analog:** Phase 12 plan 03 Task 1 (lines 87-122) — sweep mechanic for a small, structured edit followed by `uv run pytest`.

**Pattern to apply (D-09 layer 2):**

Edit `agents/graph-wiki-agent/pyproject.toml` (already moved by layer 1):

```toml
[project]
name = "graph-wiki-agent"     # was: "code-wiki-agent"

[project.scripts]
graph-wiki-agent = "graph_wiki_agent.cli:app"      # was: code-wiki-agent / code_wiki_agent.cli
graph-wiki-mcp   = "graph_wiki_mcp.server:main"    # was: code-wiki-mcp / code_wiki_mcp.server
```

Note: the `[project.scripts]` value-side rewrites assume layer 3 will rename the Python modules. If layer 2 lands before layer 3, the script targets point at non-existent modules — that is OK because the per-commit gate at layer 2 is just `uv sync` (regenerates the lockfile + installs the renamed package); `uv run pytest` is not required to pass until layer 3 (D-11 "or equivalent scope").

Then regenerate the lockfile:
```bash
uv sync
git add ../uv.lock agents/graph-wiki-agent/pyproject.toml
```

Commit subject suggestion: `refactor: rename package + console scripts to graph-wiki-agent`.

**Phase 12 excerpt — gate-as-`uv run pytest`-pipe-safe pattern** (plan 03 Task 1 verify block, line 113):

```bash
uv run pytest 2>&1 | tail -5
PYTEST_RC=${PIPESTATUS[0]}
test "$PYTEST_RC" -eq 0 || { echo "PYTEST FAILED rc=$PYTEST_RC"; exit 1; }
```

Phase 21 planner MUST copy this `PIPESTATUS[0]` idiom verbatim for every layer-3-onward gate — `| tail -5` masks the pytest exit code, and a silent green gate is exactly the failure mode SQ-03 was authored to prevent.

---

### Class: `python-module-sweep`

**Analog:** Phase 12 plan 03 Task 2 (lines 124-151) — exact same surface (`agents/code-wiki-agent/src/`), exact same mechanic (string sweep + identifier rename + pytest gate per commit).

**Pattern to apply (D-09 layer 3 — the "main event"):**

1. Pre-edit grep to discover surface:
   ```bash
   grep -rE 'code-wiki-agent|code_wiki_agent|code-wiki-mcp|code_wiki_mcp' \
     agents/graph-wiki-agent/src/ agents/graph-wiki-agent/tests/
   ```
2. Three substitution classes (apply in any order within the layer):
   - **Snake imports:** `from code_wiki_agent.X` → `from graph_wiki_agent.X`; `from code_wiki_mcp.X` → `from graph_wiki_mcp.X`; `import code_wiki_agent` → `import graph_wiki_agent`.
   - **Kebab user-facing strings:** `"code-wiki-agent ..."` in print/log/error/CLI-help/exception-message → `"graph-wiki-agent ..."`. **Touch tracebacks per D-03** ("consistency over churn-avoidance").
   - **Internal identifiers (D-03):** `CodeWikiAgentError` → `GraphWikiAgentError`; any class/func/var starting with `CodeWiki` gets renamed. Pre-locate with:
     ```bash
     grep -rE 'CodeWiki[A-Z][A-Za-z]*' agents/graph-wiki-agent/src/ agents/graph-wiki-agent/tests/
     ```
3. Trace-dir path sweep (folds in `trace-dir-reference` class for files inside the agent — see that class for the cross-cutting full sweep).
4. Verify test filenames per D-02 specifics:
   ```bash
   find agents/graph-wiki-agent/tests -name '*code_wiki*' -o -name '*code-wiki*'
   ```
   Spot-check during context-gathering suggested empty output (tests are behavior-named). Planner must confirm; if any matches, rename in this commit.
5. Gate per SQ-03 idiom (above). If red, **revert the commit** (`git reset --hard HEAD~1`), don't "fix forward" — that's the explicit Phase 12 rule (plan 03 line 70: "no 'fix forward' — revert and retry").

Commit subject suggestion: `refactor: rebrand code-wiki-agent → graph-wiki-agent in agents/graph-wiki-agent`.

**Phase 12 excerpt — disambiguation rule** (plan 03 Task 2 `<action>`, lines 131-137). The Phase 12 mechanic for deciding whether to rebrand a string vs. allowlist it as historical applies almost verbatim to Phase 21 — except Phase 21's defaults are inverted (Phase 12 default: rebrand unless historical-provenance; Phase 21 default: rebrand always, because `code-wiki-agent` was never an upstream brand — it was always an internal name).

---

### Class: `plugin-shellout-script`

**Analog:** Phase 12 plan 03 Task 2 mechanic, but Phase 14 authored these specific files. The files are mechanically simple (one literal per file).

**Pattern to apply (D-09 layer 4):**

Five files, identical shape, one literal each:

| File | Literal to rewrite |
|------|---------------------|
| `plugins/graph-wiki/skills/graph-wiki/scripts/scan_monorepo.py` | `["code-wiki-agent", "scan"]` → `["graph-wiki-agent", "scan"]` |
| `plugins/graph-wiki/skills/graph-wiki/scripts/init_vault.py` | `["code-wiki-agent", "init"]` → `["graph-wiki-agent", "init"]` |
| `plugins/graph-wiki/skills/graph-wiki/scripts/ingest_source.py` | `["code-wiki-agent", "ingest"]` → `["graph-wiki-agent", "ingest"]` |
| `plugins/graph-wiki/skills/graph-wiki/scripts/lint_wiki.py` | `["code-wiki-agent", "lint"]` → `["graph-wiki-agent", "lint"]` |
| `plugins/graph-wiki/skills/graph-wiki/scripts/wiki_search.py` | `["code-wiki-agent", "query"]` → `["graph-wiki-agent", "query"]` |

Each file's module docstring (`"""Plugin shim for X — dispatches to vault_io (claude) or code-wiki-agent (bedrock)."""`) also gets the `code-wiki-agent` → `graph-wiki-agent` substitution.

Gate per SQ-03 idiom. Commit subject: `refactor: update plugin shellouts to graph-wiki-agent`.

---

### Class: `trace-dir-reference`

**Analog:** Phase 12 plan 03 Task 1 (path-fragment sweep across packages/). Same pattern, narrower surface.

**Pattern to apply (folded into layers 3 or 4 by planner discretion; recommend separate commit for revertability):**

Files containing `.code-wiki/` (full list from pre-mapping grep):

```
agents/code-wiki-agent/tests/test_ingest_trace_unit.py
agents/code-wiki-agent/tests/unit/test_query_code_fallback.py
agents/code-wiki-agent/tests/unit/test_query_summary_schema_version.py
agents/code-wiki-agent/tests/unit/test_query_search.py
agents/code-wiki-agent/tests/integration/test_mcp_cancel.py
agents/code-wiki-agent/src/code_wiki_agent/prompts/code_reader.py
agents/code-wiki-agent/src/code_wiki_agent/commands/query.py
packages/eval-harness/tests/test_isolation.py
packages/eval-harness/src/eval_harness/isolation.py
packages/eval-harness/src/eval_harness/divergence/code_reader.py
packages/prompt-sources/agents/code_reader.md
packages/subagent-runtime/src/subagent_runtime/pool.py
docs/trace-schema.md
.planning/PROJECT.md
graph-wiki/wiki/packages/vault-io/vault-io.md   # OUT OF SCOPE per D-06
```

All `.code-wiki/` → `.graph-wiki/` (kebab-case path fragment). The `graph-wiki/wiki/` entry is explicitly out of scope per D-06 — planner must add an exception in the sweep script or filter `--exclude-dir=graph-wiki/wiki`.

D-04 acknowledges existing local trace history orphans (ephemeral debug output, uncommitted).

Commit subject suggestion: `refactor: rename .code-wiki/ trace dir → .graph-wiki/`.

---

### Class: `repo-doc` + `plugin-doc`

**Analog:** Phase 12 plan 03 Task 4 (live prose rebrand). Same mechanic; Phase 21 has no historical-prose carveout for these files because `code-wiki-agent` is the internal name being retired, not an upstream brand being preserved.

**Pattern to apply (D-09 layer 5):**

Files:
- `README.md` (repo root)
- `CLAUDE.md` (repo root) — note: this file is also `.brand-grep-allow`ed for `lattice` references; Phase 21 sweep adds `code-wiki-agent` rewrites but **must not** strip the existing lattice prose
- `plugins/graph-wiki/README.md`
- `plugins/graph-wiki/CLAUDE.md`
- `plugins/graph-wiki/skills/graph-wiki/README.md`
- `plugins/graph-wiki/.claude-plugin/plugin.json`

**Phase 12 excerpt — surgical-edits discipline** (plan 03 Task 4 `<action>`, line 195): "Use editorial judgment — when in doubt, leave the historical reference verbatim and record it in `12-03-carry-forward-refs.md`." Phase 21 inverts this: when in doubt, **rebrand** (per D-13: "the goal of sweeping all 188 `.planning/` files is to *eliminate* most refs so the allowlist stays short"). Carry-forward is the exception.

---

### Class: `planning-doc-sweep`

**Analog:** Phase 12 plan 03 Task 4 — but with documented divergence. Phase 12 explicitly **skipped** historical archives (R-03); Phase 21 D-05 explicitly **overrides** that and sweeps all 188 files.

**Pattern to apply (D-09 layer 5, planner may split into sub-commits):**

The 188-file scope is too large for a single commit to inspect cleanly. Recommend the planner split into 3 sub-commits to preserve per-sub-commit revertability:

1. **Live planning surface** — `.planning/{STATE,ROADMAP,REQUIREMENTS,PROJECT,RETROSPECTIVE,MILESTONES}.md`, `.planning/intel/stack.json`, `.planning/threads/`.
2. **Current-milestone phase docs** — `.planning/phases/{17,20,21}/**/*.md`.
3. **Historical archives** — `.planning/milestones/v1.{0,1,2}-phases/**/*.md`, `.planning/sketches/**`, `.planning/sweep/**`, `.planning/research/**`, `.planning/spikes/00{1,2}/README.md` and `.claude/skills/spike-findings-deep-agents/{SKILL.md,references/*.md}` (the `skill-doc-sweep` class folds here). **Excluded per D-07:** `.planning/spikes/00{1,2}/sources/**/*.md` (raw spike sources stay verbatim).

For each sub-commit:
- Grep first to scope: `grep -rEl 'code-wiki-agent|code_wiki_agent|code-wiki-mcp|code_wiki_mcp' <subscope>`.
- `sed -i ''` substitution is acceptable here because all four search terms are unambiguous (no false-positive risk — they don't appear inside other tokens). Phase 12 plan 03 did not use `sed` because `lattice` was a substring of other tokens; Phase 21 has a cleaner pattern. Planner may script the sweep.
- Per-commit gate is `bash scripts/check-brand.sh` (which by layer 5 includes the new patterns — see `brand-grep-gate-extension` class); `uv run pytest` should already be trivially green since these are doc-only.

Commit subject pattern: `docs: rebrand code-wiki-agent → graph-wiki-agent in .planning/<subscope>`.

---

### Class: `brand-grep-gate-extension`

**Analog:** Phase 12 plan 04 Task 1 (lines 58-148) — direct precedent; same two files; same allowlist format.

**Pattern to apply (D-09 layer 5; lands AFTER planning sweep so the gate's first run is meaningful):**

**Edit `scripts/check-brand.sh`** (lines 37-40 currently):

```bash
# Before:
HITS=$(grep -rEl --exclude-dir=__pycache__ --exclude='*.pyc' \
    'lattice|LATTICE|lattice_workspace|lattice_wiki_core' \
    packages/ agents/ plugins/ .planning/ CLAUDE.md 2>/dev/null \
    | grep -vF -f <(grep -vE '^[[:space:]]*(#|$)' "$ALLOWLIST") || true)

# After (extend the regex with the four new patterns per D-12):
HITS=$(grep -rEl --exclude-dir=__pycache__ --exclude='*.pyc' \
    'lattice|LATTICE|lattice_workspace|lattice_wiki_core|code-wiki-agent|code_wiki_agent|code-wiki-mcp|code_wiki_mcp' \
    packages/ agents/ plugins/ .planning/ CLAUDE.md 2>/dev/null \
    | grep -vF -f <(grep -vE '^[[:space:]]*(#|$)' "$ALLOWLIST") || true)
```

Update the failure-message label too — `BRAND-04 FAIL` is still meaningful (single gate per D-12), but the heredoc comment block at the top of the script (lines 3-12) should add a Phase 21 note: "Per Phase 21 §D-12: extended to also catch `code-wiki-agent`/`code_wiki_agent`/`code-wiki-mcp`/`code_wiki_mcp` after the rename to `graph-wiki-agent`."

**Edit `.brand-grep-allow`** — add a new section per D-13 (tight allowlist):

```
# ---------------------------------------------------------------------------
# Phase 21 — `code-wiki-agent` rename to `graph-wiki-agent`. Per D-13, the
# allowlist stays tight: only entries that would actively break things if
# rewritten. Most historical references are eliminated by the 188-file sweep,
# not allowlisted.
# ---------------------------------------------------------------------------
# rationale: scripts/check-brand.sh contains 'code-wiki-agent' / 'code_wiki_agent'
# / 'code-wiki-mcp' / 'code_wiki_mcp' as grep patterns themselves.
scripts/check-brand.sh
# rationale: .brand-grep-allow self-allowlists these literals as pattern documentation.
.brand-grep-allow
# rationale: graph-wiki/wiki/ is out of scope (D-06) — healed by next /graph-wiki:scan run.
graph-wiki/wiki/
# rationale: raw spike sources stay verbatim per D-07.
.planning/spikes/001-subagent-context-audit/sources/
.planning/spikes/002-lattice-drift-inventory/sources/
# rationale: pytest runtime artifacts embed renamed test node IDs as substrings.
.pytest_cache/v/cache/nodeids
# rationale: agents/code-wiki-agent/test-out — gitignored test output dir; tolerate stale.
agents/graph-wiki-agent/test-out/
```

Planner adds carry-forward refs (any unavoidable references discovered during the sweep) following the Phase 12 idiom (Phase 12 plan 04 Task 2 `<action>`, lines 168-173): if the gate fails with hits, **stop**, evaluate each hit, allowlist only if rewriting would break something, otherwise complete the rebrand.

**Phase 12 excerpt — staged final verification with separate exit codes** (plan 04 Task 2 verify block, line 187). Copy this idiom for the Phase 21 final gate:

```bash
bash scripts/check-brand.sh
GATE_RC=$?
test "$GATE_RC" -eq 0 || { echo "GATE FAILED rc=$GATE_RC"; exit "$GATE_RC"; }
uv run pytest 2>&1 | tail -5
TEST_RC=${PIPESTATUS[0]}
test "$TEST_RC" -eq 0 || { echo "TESTS FAILED rc=$TEST_RC"; exit "$TEST_RC"; }
```

Commit subject suggestion: `chore: extend brand grep-gate for code-wiki-agent → graph-wiki-agent (Phase 21)`.

---

### Class: `top-level-integration-gate-test`

**Analog:** Phase 12 plan 03 Task 1 disambiguation rule (`packages/vault-io/tests/`).

**Pattern to apply (folded into layer 3 or 4 by planner discretion):**

`tests/test_integration_gate.py` — `grep -nE 'code-wiki-agent|code_wiki_agent|code-wiki-mcp|code_wiki_mcp'` to scope. This file likely invokes console scripts; after layer 2 `pyproject.toml` rename, the console-script invocations in this file MUST also be renamed for the test to pass.

Same gate; if Phase 21 splits this into its own commit: `test: update integration gate for graph-wiki-agent console scripts`.

---

## Shared Patterns

### SP-1: Per-commit `uv run pytest` gate with PIPESTATUS idiom (SQ-03)
**Source:** Phase 12 plan 03 Task 1 verify block (lines 113).
**Apply to:** Every layer-3-onward commit (CONTEXT D-11).

```bash
uv run pytest 2>&1 | tail -5
PYTEST_RC=${PIPESTATUS[0]}
test "$PYTEST_RC" -eq 0 || { echo "PYTEST FAILED rc=$PYTEST_RC"; exit 1; }
```

**Critical:** `| tail -5` without `PIPESTATUS[0]` silently masks pytest failures. Phase 12 added this to the verify block specifically because checker W4 caught the masking risk; Phase 21 inherits the fix.

### SP-2: `bash scripts/check-brand.sh` as second-stage gate
**Source:** Phase 12 plan 04 Task 2 verify block (line 187).
**Apply to:** Final commit of layer 5 (after the planning sweep + gate extension lands together).

Stage the gate run independently of pytest with named exit-code capture so the failure mode is unambiguous.

### SP-3: "No fix-forward" revert rule
**Source:** Phase 12 plan 03 `<objective>` line 70.
**Apply to:** Every per-commit gate failure.

If `uv run pytest` is red after a commit: `git reset --hard HEAD~1`, diagnose, retry. Do not stack a fix commit on top of a broken one. CONTEXT.md D-11 inherits this implicitly.

### SP-4: Worktree containment (D-08)
**Source:** No Phase 12 analog (Phase 12 worked in-place). Phase 21 user-explicit hard constraint.
**Apply to:** Entire Phase 21 lifecycle.

```bash
git worktree add ../deep-agents-rename rename-21
cd ../deep-agents-rename
# ...all phase work happens here...
```

Main checkout stays usable for parallel work. Planner treats this as the entry-step of layer 1, before any `git mv`.

### SP-5: `git mv` over `mv` + `git add`
**Source:** CONTEXT §"Established Patterns" + universal git convention.
**Apply to:** All layer-1 directory moves.

Preserves blame/history. If accidentally done with plain `mv`, recover via `git checkout HEAD -- <oldpath>` and redo with `git mv`.

### SP-6: Tight allowlist discipline (D-13)
**Source:** Phase 12 R-04 + Phase 21 D-13 explicit reaffirmation.
**Apply to:** Every entry added to `.brand-grep-allow` during the sweep.

Adding to the allowlist is the exception; the rebrand is the rule. Each new entry MUST carry a one-line rationale comment naming the class (`# rationale: ...`). Phase 12's `.brand-grep-allow` (read earlier; lines 17-202) is the format template.

---

## No Analog Found

| File / class | Reason |
|--------------|--------|
| `dir-move-git-mv` (3 `git mv` operations) | Phase 12 swept content but never moved a package directory. This is a net-new mechanic for this codebase. Pattern source is git convention + CONTEXT.md §"Established Patterns", not a prior phase. Planner authors the steps from first principles; verification is `uv sync && find agents/graph-wiki-agent -type f \| head -5` (proves the move happened); pytest is **deferred to layer 3** (D-11 "or equivalent scope"). |
| Multi-sub-commit planning sweep (188 files) | Phase 12 swept only the live planning surface (R-03 carveout). The 188-file scope of Phase 21 D-05 is a step-change in scale. Planner authors the 3-way sub-commit split (live / current-milestone / archives) per the recommendation above. |

---

## Metadata

**Analog search scope:**
- `.planning/milestones/v1.2-phases/12-drift-backport-ecosystem-rebrand-m2/` (Phase 12 — primary precedent)
- `scripts/check-brand.sh`, `.brand-grep-allow` (live infrastructure)
- `agents/code-wiki-agent/{pyproject.toml,src,tests}` (rename surface inventory)
- `plugins/graph-wiki/skills/graph-wiki/scripts/` (plugin shellout inventory)
- `grep -rEl 'code-wiki-agent|code_wiki_agent|code-wiki-mcp|code_wiki_mcp' /Users/pat/Personal/deep-agents` (full rename surface; 308 hits)
- `grep -rEl '\.code-wiki/' ...` (trace-dir reference inventory; 15 hits)

**Files scanned (direct Read):** 5
- `.planning/phases/21-.../21-CONTEXT.md`
- `.planning/milestones/v1.2-phases/12-.../12-03-rebrand-sweep-PLAN.md`
- `.planning/milestones/v1.2-phases/12-.../12-04-grep-gate-and-verification-PLAN.md`
- `scripts/check-brand.sh`
- `.brand-grep-allow`

**Pattern extraction date:** 2026-05-19
