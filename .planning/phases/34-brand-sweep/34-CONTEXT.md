# Phase 34: Brand Sweep - Context

**Gathered:** 2026-05-25
**Status:** Ready for planning

<domain>
## Phase Boundary

After Phase 34, all USER-VISIBLE `lattice` brand text inside `packages/graph-io/` is replaced with graph-wiki phrasing across:

1. **README.md** — first-line title → `# graph-io`; second-line tagline → `Code-graph backend for graph-wiki. Owns:`; path reference `~/.lattice/graph/code.db` → prose pointing at `workspace_io.paths.graph_dir()` per SC#2.
2. **cli/main.py:45** — argparse `description="lattice code graph CLI"` → `description="graph-wiki code graph CLI"` (or planner-chosen graph-wiki variant; SC#1 requires `cg --help` to contain "graph-wiki" and NOT contain "lattice" in user-visible strings).
3. **update.py:154** — `_default_lock_timeout()` rewritten per D-09: reads new `GRAPH_WIKI_LOCK_TIMEOUT_MS` first, falls back to deprecated `LATTICE_GRAPH_LOCK_TIMEOUT_MS` with stderr warning, both-set case warns + new wins. Old env var still respected to preserve backwards compat for one milestone.
4. **`.brand-grep-allow`** — entry for `LATTICE_GRAPH_LOCK_TIMEOUT_MS` (intentional deprecated alias in update.py). Existing entry for `_SKIP_REPO_PREFIXES = ('lattice/',)` in packages.py should already exist (functional behavior — verify; add if absent).
5. **Test files** — comprehensive rebrand of brand text in `test_sync_wiki.py`, `test_packages.py`, `test_cli_sync_wiki.py`, `test_cli_exit_codes.py` per D-11, with explicit carve-outs for tests asserting functional `_SKIP_REPO_PREFIXES = ('lattice/',)` behavior (those keep `lattice/` test data per BRAND-04).
6. **Env var test refactor** — existing test reading `LATTICE_GRAPH_LOCK_TIMEOUT_MS` is updated to read `GRAPH_WIKI_LOCK_TIMEOUT_MS` per D-13. SC#3's deprecation-warning behavior is verified manually at phase-verify time per D-14 — NO automated test covers the deprecation path.
7. **`scripts/check-brand.sh` BRAND-04 gate** — exits 0 on the post-sweep tree per SC#4. The script ALREADY exists at repo root (verified). Phase 34 adds .brand-grep-allow entries; does NOT modify check-brand.sh.

**Strictly NOT in this phase:**
- `_SKIP_REPO_PREFIXES = ("lattice/",)` in `packages.py:17` — FUNCTIONAL behavior (skip filter for a specific upstream repo namespace), NOT brand text. BRAND-04 explicitly excludes this from rewriting. PITFALLS.md documents the trap.
- Any file outside `packages/graph-io/` (including `plugins/graph-wiki/`, `packages/wiki-io/`, `agents/graph-wiki-agent/`). BRAND-04 limits scope.
- Other potential `LATTICE_*` env vars — `_default_lock_timeout()` is the only one in graph-io (verified via grep). No other env-var renames in this phase.
- `cg --help` subcommand listing — that's Phase 33's surface; Phase 34 only edits the top-level argparse description string.
- Removing the LATTICE_GRAPH_LOCK_TIMEOUT_MS deprecated alias — v1.7 milestone work (one-milestone backward-compat window per BRAND-03).
- README sections beyond first 3 lines if they don't contain `lattice` references — Phase 34 is surgical, not a full README rewrite.

Requirements addressed: BRAND-01, BRAND-02, BRAND-03, BRAND-04.

</domain>

<decisions>
## Implementation Decisions

### README.md rebrand (BRAND-01)

- **D-01:** **First-line title**: `# graph-io`. Terse, matches the Python package directory name (`packages/graph-io/`), grep-friendly (`head -1 packages/graph-io/README.md` returns the package name). Predictable for `cat`/`head` workflows. Diverges from SC#2's parenthetical alternative `# graph-wiki code graph` — the simpler form was preferred.

- **D-02:** **Second-line tagline**: `Code-graph backend for graph-wiki. Owns:` (literal text, no link). The current second line `Code-graph core for the [lattice](../../README.md) ecosystem. Owns:` has a relative link `../../README.md` that would point at a `graph-wiki` README that doesn't exist in this monorepo at that path — strip the link entirely. "backend" is a more concrete description than "core" or "ecosystem".

- **D-03:** **Path reference rebrand**: replace `~/.lattice/graph/code.db` with prose: `The code graph DB lives at \`<paths.graph_dir(workspace)>/code.db\` — see \`workspace_io.paths\` for the workspace-mode-aware resolution rule.` No hardcoded path; reference the helper directly. Aligns with SC#2's literal wording ("canonical path via `workspace_io.paths.graph_dir()`").

- **D-04:** **Other README lattice references** (if any beyond the first 3 lines): Claude's discretion. Apply the same patterns: rebrand brand text, leave functional behavior text alone. Most likely scope: 1-2 sentences.

### `cli/main.py` argparse description (BRAND-02)

- **D-05:** **Replace** `description="lattice code graph CLI"` with `description="graph-wiki code graph CLI"`. Single-character-precision edit. SC#1 verification: `cg --help` output should contain "graph-wiki" and NOT contain "lattice".

### Env var rename (BRAND-03)

- **D-06:** **Target name**: `GRAPH_WIKI_LOCK_TIMEOUT_MS` per SC#3 literal. Not `GRAPH_IO_LOCK_TIMEOUT_MS` (which would be more package-scoped); the SC fixes the new name.

- **D-07:** **Precedence when BOTH env vars are set**:
  - `GRAPH_WIKI_LOCK_TIMEOUT_MS` (new) wins.
  - `LATTICE_GRAPH_LOCK_TIMEOUT_MS` (old) is IGNORED for value purposes.
  - stderr warning fires: `"warning: LATTICE_GRAPH_LOCK_TIMEOUT_MS is deprecated and ignored; using GRAPH_WIKI_LOCK_TIMEOUT_MS=<value>."`. Single line.
  - Encourages migration without breaking environments that have the old name set during transition.

- **D-08:** **Deprecation warning (old set, new not set)**:
  - stderr: `"warning: LATTICE_GRAPH_LOCK_TIMEOUT_MS is deprecated, use GRAPH_WIKI_LOCK_TIMEOUT_MS instead (value=<old_value> still respected)"`. Single line, includes the new var name and the parsed value.
  - Value is respected (timeout still applied).
  - **No suppression mechanism in v1.6** — every `cg` invocation that reads the deprecated var prints the warning. `cg` is short-lived; one warning per shell-command is acceptable noise.

- **D-09:** **`_default_lock_timeout()` refactor**:
  ```python
  def _default_lock_timeout() -> int:
      new = os.environ.get("GRAPH_WIKI_LOCK_TIMEOUT_MS")
      old = os.environ.get("LATTICE_GRAPH_LOCK_TIMEOUT_MS")
      if new is not None and old is not None:
          print(
              f"warning: LATTICE_GRAPH_LOCK_TIMEOUT_MS is deprecated and "
              f"ignored; using GRAPH_WIKI_LOCK_TIMEOUT_MS={new}",
              file=sys.stderr,
          )
          raw = new
      elif new is not None:
          raw = new
      elif old is not None:
          print(
              f"warning: LATTICE_GRAPH_LOCK_TIMEOUT_MS is deprecated, "
              f"use GRAPH_WIKI_LOCK_TIMEOUT_MS instead (value={old} still respected)",
              file=sys.stderr,
          )
          raw = old
      else:
          return 30_000
      try:
          return max(0, int(raw))
      except ValueError:
          return 30_000
  ```
  Sequential branch tree; no helper abstraction (only one env var renamed in v1.6 — premature to factor a `_resolve_env_alias` helper). `sys` import needs to be added at the top of `update.py` if not already imported (existing module uses `os.environ.get`; check imports).

- **D-10:** **Deprecation timeline**: The `LATTICE_GRAPH_LOCK_TIMEOUT_MS` alias is kept through v1.7 (next milestone) per BRAND-03 ("preserves backward compat for one milestone with a deprecation warning"). Removal happens in v1.8 or later. Phase 34 ships the alias + warning; it does NOT ship the removal.

### Test file scope (BRAND-02 ambiguity)

- **D-11:** **Comprehensive rebrand of brand text** in the four test files (`test_sync_wiki.py`, `test_packages.py`, `test_cli_sync_wiki.py`, `test_cli_exit_codes.py`). Scope:
  - Test descriptions, docstrings, comments that mention "lattice" as a brand → rebrand to "graph-wiki".
  - Test fixture data and string literals that test BRAND TEXT in production code (e.g. `assert "lattice code graph CLI" in result.stderr`) → update to `"graph-wiki code graph CLI"` to match the new production string (otherwise the test fails after Phase 34 ships).
  - **Carve-out**: Tests asserting `_SKIP_REPO_PREFIXES = ("lattice/",)` functional behavior — keep `"lattice/"` strings AS-IS. These exercise BRAND-04-excluded functional code. The planner inspects each test method:
    - If the test ASSERTS that `lattice/foo` (or similar) is filtered/skipped by `_SKIP_REPO_PREFIXES`, the literal `"lattice/foo"` MUST stay (functional contract).
    - If the test casually mentions `lattice` in a description but asserts something unrelated to `_SKIP_REPO_PREFIXES`, rebrand the description and replace lattice fixture data with `graph-wiki/foo` or similar non-loaded test input.

- **D-12:** **Test file decision rubric for the planner**:
  | File | Action |
  |------|--------|
  | `test_sync_wiki.py` | Rebrand brand text in comments/docstrings; preserve any wiki-sync fixture paths that exercise the lattice/ prefix |
  | `test_packages.py` | Rebrand brand text; PRESERVE `_SKIP_REPO_PREFIXES` test that asserts `lattice/` filtering (functional, BRAND-04 carve-out) |
  | `test_cli_sync_wiki.py` | Rebrand any assertion against the cli description; preserve sync-wiki fixture data |
  | `test_cli_exit_codes.py` | Rebrand brand-text mentions; exit-code asserts are functional, unchanged |

  Planner reads each file before editing; the rubric is guidance, not exhaustive.

### Env var test refactor (SC#3)

- **D-13:** **Existing env var test refactor**: tests that currently set `LATTICE_GRAPH_LOCK_TIMEOUT_MS` and assert the value is respected get updated to set `GRAPH_WIKI_LOCK_TIMEOUT_MS` instead. The test continues to assert the timeout-respect behavior but with the new var name. Single-string-replacement edit per test.

- **D-14:** **NO automated test for the deprecation-warning behavior**. SC#3's deprecation-warning + value-still-respected branch is verified MANUALLY at phase-verify time. Manual verification steps (planner adds to VERIFICATION.md):
  1. `unset GRAPH_WIKI_LOCK_TIMEOUT_MS; LATTICE_GRAPH_LOCK_TIMEOUT_MS=5000 cg update` → assert stderr contains "deprecated" and "GRAPH_WIKI_LOCK_TIMEOUT_MS" and update completes with the 5000ms timeout applied.
  2. `LATTICE_GRAPH_LOCK_TIMEOUT_MS=5000 GRAPH_WIKI_LOCK_TIMEOUT_MS=2000 cg update` → assert stderr contains "deprecated and ignored" and "using GRAPH_WIKI_LOCK_TIMEOUT_MS=2000".
  3. `GRAPH_WIKI_LOCK_TIMEOUT_MS=5000 cg update` → assert no warning on stderr (silent acceptance).

  **Risk note for planner**: this is a deliberate test-coverage gap per user decision. A future refactor of `_default_lock_timeout()` could silently regress the deprecation contract without CI noticing. Trade-off accepted.

### `.brand-grep-allow` entries (BRAND-04 / SC#4)

- **D-15:** **New entry for `LATTICE_GRAPH_LOCK_TIMEOUT_MS`**: add a substring pattern to `.brand-grep-allow` covering the single line in `update.py` that reads the deprecated env var. Format (matches existing allowlist convention from `check-brand.sh`'s `grep -vF -f`): one substring per line, supports `#` comments. Recommended entry:
  ```
  # Phase 34 BRAND-03: deprecated env var alias kept for one-milestone backward compat (D-10)
  LATTICE_GRAPH_LOCK_TIMEOUT_MS
  ```
  The `grep -vF` operates on substring match against file paths AND content fragments — so this entry covers any line/file containing the literal string. Verify behavior with `bash scripts/check-brand.sh` post-sweep.

- **D-16:** **Existing entry for `_SKIP_REPO_PREFIXES = ('lattice/',)` in packages.py**: VERIFY it exists in `.brand-grep-allow`. If absent, ADD an entry:
  ```
  # BRAND-04 carve-out: functional behavior (per PITFALLS.md), not brand text
  packages/graph-io/src/graph_io/packages.py
  ```
  (Path-based entry — `check-brand.sh` uses `grep -vF` so file path substrings match.) Planner does a `bash scripts/check-brand.sh` dry run BEFORE making any edits to discover the baseline allowlist state, then ADDS the minimum new entries needed.

- **D-17:** **No edits to `check-brand.sh`**. The script is well-tested (CR-01, WR-03 already addressed); Phase 34 only adds allowlist entries.

### Verification flow

- **D-18:** **Phase 34 SC verification order** (planner builds this into VERIFICATION.md):
  1. SC#1: `cg --help` output check (string match: contains "graph-wiki", NOT contains "lattice")
  2. SC#2: `head -1 packages/graph-io/README.md` = `# graph-io`; grep README for `~/.lattice/graph/code.db` returns no matches.
  3. SC#3: three manual env var scenarios per D-14.
  4. SC#4: `bash scripts/check-brand.sh` exits 0; `grep -c LATTICE_GRAPH_LOCK_TIMEOUT_MS .brand-grep-allow` ≥ 1.

### Claude's Discretion

- Exact wording of stderr deprecation warnings (D-07/D-08 prototypes are starting points; planner can tweak for grammar/clarity).
- Removal of `[lattice](../../README.md)` markdown link in D-02 — if the README has OTHER `[lattice]` markdown links (probably not, but check), apply the same strip-link-keep-prose rule.
- Whether the warning includes "Removed in v1.7" timeline hint — D-08 doesn't include it for brevity; planner can add if useful, max one line.
- `.brand-grep-allow` entry SHAPE — D-15 picks substring, D-16 picks path. Planner verifies which form check-brand.sh actually filters on (it's `grep -vF -f`, which is substring against the OUTPUT of the first grep, which is `grep -rEl` returning file paths). So entries should be file-path substrings primarily. Adjust if needed.
- Order of edits in the plan waves — D-09 update.py + D-13 test update should land together (commit-atomically: code + test); D-01..D-04 README is a separate commit; D-05 cli/main.py is a third; D-15/D-16 allowlist edits land first as a "prep" wave so check-brand.sh wouldn't fail mid-sweep.

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### v1.6 research
- `.planning/research/PITFALLS.md` — Pitfall about `_SKIP_REPO_PREFIXES = ('lattice/',)` being FUNCTIONAL, not brand. D-11/D-12/D-16 honor this carve-out.

### Requirements + roadmap
- `.planning/REQUIREMENTS.md` — BRAND-01..04 (lines 98–101); pending-phase mapping lines 237–240
- `.planning/ROADMAP.md` — Phase 34 block + SC#1–4. SC#3 is the deprecation-warning verification driver; SC#4 is the .brand-grep-allow + check-brand.sh gate.

### Existing graph-io code (in-scope for editing)
- `packages/graph-io/README.md` — first 3 lines are the primary edit target; lines 1-3 are `# lattice-graph-core` / blank / `Code-graph core for the [lattice](../../README.md) ecosystem. Owns:`
- `packages/graph-io/src/graph_io/cli/main.py:45` — argparse `description="lattice code graph CLI"`; D-05 edits
- `packages/graph-io/src/graph_io/update.py:154` (function `_default_lock_timeout`, body around lines 153-160) — D-09 refactor lands here
- `packages/graph-io/src/graph_io/packages.py:17` (`_SKIP_REPO_PREFIXES = ("lattice/",)`) — DO NOT EDIT, allowlist instead (D-16)

### Test files (in-scope per D-11/D-12)
- `packages/graph-io/tests/test_sync_wiki.py`
- `packages/graph-io/tests/test_packages.py` — carve-out for `_SKIP_REPO_PREFIXES` tests
- `packages/graph-io/tests/test_cli_sync_wiki.py`
- `packages/graph-io/tests/test_cli_exit_codes.py`

### Brand sweep infrastructure (existing)
- `scripts/check-brand.sh` — the BRAND-04 gate. Already well-developed (handles CR-01 blank-line bug, WR-03 comment patterns, 6 CHECK passes for various rename concerns from prior phases). Phase 34 does NOT modify this script.
- `.brand-grep-allow` at repo root — allowlist file. check-brand.sh requires it to exist (exits 2 if missing). Planner verifies existence and current entries via `cat .brand-grep-allow` before editing.

### Existing rebranding precedents
- Phase v1.2 / v1.3 milestones (per scripts/check-brand.sh comments) — performed the original lattice → graph-wiki sweep across `agents/`, `plugins/`, `wiki-io/`. Phase 34 finishes the work in `packages/graph-io/` which was deliberately deferred to avoid merge conflicts with v1.6's other phases.

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- **`scripts/check-brand.sh`** — already handles 6 brand-pattern checks. Phase 34 uses it as the BRAND-04 gate without modification.
- **`.brand-grep-allow`** format and conventions — established by prior brand sweeps. Comment lines via `#`; blank lines ignored; substring matching via `grep -vF`.
- **`os.environ.get(...)` pattern** — existing `_default_lock_timeout()` already uses this; D-09 extends with two env var reads.

### Established Patterns
- **One-milestone deprecation window** for renamed env vars (BRAND-03 wording) — Phase 34 ships the alias, v1.7 removes.
- **stderr for warnings, exit 0** — deprecation is not a failure; the run completes with the value respected.
- **Surgical brand sweeps**: edit only brand text, preserve functional code (PITFALLS.md lesson from prior phases).
- **Allowlist entries before code edits** — add `.brand-grep-allow` entries first so check-brand.sh doesn't fail during mid-sweep test runs.

### Integration Points
- **D-05 (cli/main.py description) ↔ Phase 33** — Phase 33 expanded `_SUBCOMMANDS` dict but didn't touch the parser description string. Phase 34 changes ONLY that string. Independent edit, no merge risk if Phase 33 still in flight at execute time.
- **D-09 (update.py) ↔ Phase 29's update.py edits** — Phase 29 shipped changes to `update.run()` ordering (D-23). The `_default_lock_timeout()` function is independent of `run()`'s orchestration. No conflict.
- **D-11..D-12 test edits ↔ Phase 30/31 test additions** — Phase 30 added `test_call_order_pitfall`, Phase 31 added cycle + derived-edge tests. None overlap with the four files Phase 34 edits. Independent.
- **No conflict with Phase 33 cli/main.py edits** — Phase 33 modifies `_SUBCOMMANDS` dict (line ~28-42) and adds 12 new subcommand modules. Phase 34 edits line 45 (parser description). Disjoint.

</code_context>

<specifics>
## Specific Ideas

- D-01..D-03 README diff prototype:
  ```diff
  -# lattice-graph-core
  +# graph-io

  -Code-graph core for the [lattice](../../README.md) ecosystem. Owns:
  +Code-graph backend for graph-wiki. Owns:
  ```
  And replace `~/.lattice/graph/code.db` references (likely 1-2 occurrences) with prose:
  ```diff
  -The code graph database is stored at ~/.lattice/graph/code.db.
  +The code graph database lives at `<paths.graph_dir(workspace)>/code.db` —
  +see `workspace_io.paths` for the workspace-mode-aware resolution rule.
  ```

- D-05 cli/main.py diff:
  ```diff
  -    parser = argparse.ArgumentParser(prog="cg", description="lattice code graph CLI")
  +    parser = argparse.ArgumentParser(prog="cg", description="graph-wiki code graph CLI")
  ```

- D-09 update.py diff:
  ```diff
  -import os
  +import os
  +import sys

   ...
   def _default_lock_timeout() -> int:
  -    raw = os.environ.get("LATTICE_GRAPH_LOCK_TIMEOUT_MS")
  -    if raw is None:
  -        return 30_000
  -    try:
  -        return max(0, int(raw))
  -    except ValueError:
  -        return 30_000
  +    new = os.environ.get("GRAPH_WIKI_LOCK_TIMEOUT_MS")
  +    old = os.environ.get("LATTICE_GRAPH_LOCK_TIMEOUT_MS")
  +    if new is not None and old is not None:
  +        print(
  +            f"warning: LATTICE_GRAPH_LOCK_TIMEOUT_MS is deprecated and "
  +            f"ignored; using GRAPH_WIKI_LOCK_TIMEOUT_MS={new}",
  +            file=sys.stderr,
  +        )
  +        raw = new
  +    elif new is not None:
  +        raw = new
  +    elif old is not None:
  +        print(
  +            f"warning: LATTICE_GRAPH_LOCK_TIMEOUT_MS is deprecated, "
  +            f"use GRAPH_WIKI_LOCK_TIMEOUT_MS instead (value={old} still respected)",
  +            file=sys.stderr,
  +        )
  +        raw = old
  +    else:
  +        return 30_000
  +    try:
  +        return max(0, int(raw))
  +    except ValueError:
  +        return 30_000
  ```

- D-15 .brand-grep-allow entry:
  ```
  # Phase 34 BRAND-03: LATTICE_GRAPH_LOCK_TIMEOUT_MS deprecated env var alias (D-10).
  # Removed in v1.7+.
  LATTICE_GRAPH_LOCK_TIMEOUT_MS
  ```

- D-18 SC verification commands the planner inlines into VERIFICATION.md:
  ```bash
  # SC#1
  uv run cg --help | grep -q 'graph-wiki'
  ! uv run cg --help | grep -q 'lattice'

  # SC#2
  test "$(head -1 packages/graph-io/README.md)" = '# graph-io'
  ! grep -q '~/.lattice/graph/code.db' packages/graph-io/README.md

  # SC#3 (manual): three env var scenarios per D-14

  # SC#4
  bash scripts/check-brand.sh
  grep -q 'LATTICE_GRAPH_LOCK_TIMEOUT_MS' .brand-grep-allow
  ```

- Pre-sweep snapshot for planner's safety: `bash scripts/check-brand.sh > /tmp/preflight.txt 2>&1 || true; echo "Baseline hits: $(wc -l < /tmp/preflight.txt)"`. After sweep, re-run; expect zero hits.

</specifics>

<deferred>
## Deferred Ideas

- **Removal of LATTICE_GRAPH_LOCK_TIMEOUT_MS alias** — v1.7 milestone. Phase 34 ships the alias + warning; v1.7 (or later) removes.
- **GRAPH_WIKI_SUPPRESS_DEPRECATION env var** — could quiet the warning for users who can't migrate. Not in v1.6 scope.
- **Generalised env-var-rename helper** — `_resolve_env_alias(new, old)` style abstraction. Premature for one rename; revisit if v1.7+ adds more env var renames.
- **README full rewrite** — Phase 34 is a brand sweep; a comprehensive README modernization (architecture diagrams, getting-started, API reference) is its own future phase.
- **Automated deprecation-warning test** — D-14 explicitly skips; coverage gap accepted. Could land in v1.7 alongside the removal.
- **Brand sweep of `plugins/graph-wiki/` or `agents/graph-wiki-agent/`** — explicitly out of scope per BRAND-04. Prior phases handled those.
- **Migration guide / CHANGELOG entry** — could document the env var rename for users upgrading from v1.5 to v1.6+. Phase 34 doesn't ship docs beyond README edits.
- **`cg` CLI version bump tied to brand sweep** — semver-style version in `pyproject.toml`. Not in Phase 34 scope.

</deferred>

---

*Phase: 34-brand-sweep*
*Context gathered: 2026-05-25*
