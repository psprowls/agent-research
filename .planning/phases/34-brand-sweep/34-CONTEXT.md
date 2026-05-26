# Phase 34: Brand Sweep - Context

**Gathered:** 2026-05-25
**Revised:** 2026-05-26 — single-user repo, no backwards compatibility required. The deprecation
alias + warning machinery for `LATTICE_GRAPH_LOCK_TIMEOUT_MS` is dropped; `_SKIP_REPO_PREFIXES`
(which targeted a `lattice/` vendor directory that does not exist in this repo) is deleted along
with its test. `.brand-grep-allow` ships with broader-codebase carve-outs only (workspace_io
package, ported-from comments, historical planning docs); zero Phase-34-specific entries.

**Status:** Ready for planning

<domain>
## Phase Boundary

After Phase 34, all `lattice` brand text inside `packages/graph-io/` is gone — no deprecation
window, no allowlist entry for graph-io itself. The sweep covers:

1. **README.md** — first-line title → `# graph-io`; second-line tagline → `Code-graph backend for graph-wiki. Owns:`; path reference `~/.lattice/graph/code.db` → prose pointing at `workspace_io.paths.graph_dir()` per SC#2; the `plugins/lattice-graph/` reference is rebranded to `plugins/graph-wiki/`.
2. **cli/main.py:45** — argparse `description="lattice code graph CLI"` → `description="graph-wiki code graph CLI"` (SC#1).
3. **update.py:153-160** — `_default_lock_timeout()` is a straight rename: reads `GRAPH_WIKI_LOCK_TIMEOUT_MS` only. No alias, no warning, no precedence logic. Per D-09 (revised) this collapses to the original 6-line shape with just the env-var name swapped.
4. **packages.py:17,27** — `_SKIP_REPO_PREFIXES = ("lattice/",)` and the `rel.startswith(p)` check in `_should_skip` are **deleted**. Per D-16 (revised) the agent-research repo has no `lattice/` directory and the `.cgignore` mechanism covers any user-driven exclusion. The test `test_refresh_skips_lattice_dir_manifests` (test_packages.py lines 112-126) is deleted with it.
5. **`.brand-grep-allow`** — created at repo root with carve-outs for legitimate uses elsewhere in the codebase (workspace_io package itself, source-parser/eval-harness ported-from comments, wiki-io test fixture vault that references the original lattice-* package names, .planning/ historical docs, CLAUDE.md). **Zero entries for packages/graph-io/** — the sweep eliminates every match there.
6. **Test files** — comprehensive rebrand of brand text in `test_sync_wiki.py`, `test_packages.py`, `test_cli_sync_wiki.py`, `test_cli_exit_codes.py`. No carve-outs. test_packages.py loses the `test_refresh_skips_lattice_dir_manifests` test entirely (covered by the packages.py deletion in D-16).
7. **Env var test refactor** — `test_cli_exit_codes.py:130` updated to set `GRAPH_WIKI_LOCK_TIMEOUT_MS=200` (single-string replacement).
8. **`scripts/check-brand.sh`** — unchanged. Phase 34 only adds the `.brand-grep-allow` file.

**Strictly NOT in this phase:**
- Any file outside `packages/graph-io/` (including `plugins/graph-wiki/`, `packages/wiki-io/`, `agents/graph-wiki-agent/`). BRAND-04 limits scope.
- Refactoring the `check-brand.sh` regex itself (e.g. dropping `workspace_io` from the regex). That regex looks aggressive but its current shape is what the v1.6 brand sweep accepts; revisit in a later milestone if the allowlist size becomes a maintenance burden.
- A README full rewrite — Phase 34 is surgical, not a full README rewrite.

Requirements addressed: BRAND-01, BRAND-02, BRAND-03, BRAND-04.

</domain>

<decisions>
## Implementation Decisions

### README.md rebrand (BRAND-01)

- **D-01:** **First-line title**: `# graph-io`. Terse, matches the Python package directory name (`packages/graph-io/`), grep-friendly (`head -1 packages/graph-io/README.md` returns the package name). Predictable for `cat`/`head` workflows.

- **D-02:** **Second-line tagline**: `Code-graph backend for graph-wiki. Owns:` (literal text, no link). The current second line `Code-graph core for the [lattice](../../README.md) ecosystem. Owns:` has a relative link `../../README.md` that would point at a `graph-wiki` README that doesn't exist in this monorepo at that path — strip the link entirely. "backend" is a more concrete description than "core" or "ecosystem".

- **D-03:** **Path reference rebrand**: replace `~/.lattice/graph/code.db` with prose: `The code graph DB lives at \`<paths.graph_dir(workspace)>/code.db\` — see \`workspace_io.paths\` for the workspace-mode-aware resolution rule.` No hardcoded path; reference the helper directly.

- **D-04:** **Other README lattice references** (e.g. `plugins/lattice-graph/` on line 12): rebrand to `plugins/graph-wiki/` per RESEARCH F-04. After Phase 34, the README contains **zero** lattice/LATTICE references.

### `cli/main.py` argparse description (BRAND-02)

- **D-05:** **Replace** `description="lattice code graph CLI"` with `description="graph-wiki code graph CLI"`. Single-character-precision edit. SC#1 verification: `cg --help` output should contain "graph-wiki" and NOT contain "lattice".

### Env var rename (BRAND-03) — REVISED 2026-05-26

- **D-06:** **Target name**: `GRAPH_WIKI_LOCK_TIMEOUT_MS`. Single-user repo; no backwards-compat alias.

- **D-07 (revised):** **No precedence logic.** The function reads only `GRAPH_WIKI_LOCK_TIMEOUT_MS`. If `LATTICE_GRAPH_LOCK_TIMEOUT_MS` is set in the user's environment, it is silently ignored (the same way any other unknown env var would be).

- **D-08 (revised):** **No deprecation warning.** No stderr output. The old env var name is gone from the codebase; there is no deprecation contract to preserve.

- **D-09 (revised):** **`_default_lock_timeout()` straight rename**:
  ```python
  def _default_lock_timeout() -> int:
      raw = os.environ.get("GRAPH_WIKI_LOCK_TIMEOUT_MS")
      if raw is None:
          return 30_000
      try:
          return max(0, int(raw))
      except ValueError:
          return 30_000
  ```
  Six lines, identical shape to the pre-Phase-34 function. Only the env var name changes.

- **D-10 (revised):** **No deprecation timeline.** There is no alias to remove later. v1.7 and beyond can ignore the env-var rename entirely.

### Test file scope (BRAND-02 ambiguity) — REVISED 2026-05-26

- **D-11 (revised):** **Comprehensive rebrand of all `lattice`/`LATTICE` references** in the four test files (`test_sync_wiki.py`, `test_packages.py`, `test_cli_sync_wiki.py`, `test_cli_exit_codes.py`). No carve-outs. After Phase 34, `grep -E 'lattice|LATTICE' packages/graph-io/tests/` returns zero hits.

- **D-12 (revised):** **Test file decision rubric for the planner**:
  | File | Action |
  |------|--------|
  | `test_sync_wiki.py` | Rename fixture path `tmp_path / "lattice"` → `tmp_path / "graph-wiki"`; rename `.lattice.yaml` → `.graph-wiki.yaml` |
  | `test_packages.py` | **Delete** `test_refresh_skips_lattice_dir_manifests` (lines 112-126). The function being tested (`_SKIP_REPO_PREFIXES`) is deleted by D-16. |
  | `test_cli_sync_wiki.py` | Rename `lattice/.lattice.yaml` fixture key → `graph-wiki/.graph-wiki.yaml` (two occurrences) |
  | `test_cli_exit_codes.py` | Rename env var literal on line 130: `"LATTICE_GRAPH_LOCK_TIMEOUT_MS": "200"` → `"GRAPH_WIKI_LOCK_TIMEOUT_MS": "200"` |

### Env var test refactor (SC#3) — REVISED 2026-05-26

- **D-13:** **Existing env var test refactor**: `test_cli_exit_codes.py:130` sets the new var name. The test continues to assert the lock-timeout-respected behavior (200ms timeout, `elapsed_ms < 5000`).

- **D-14 (revised):** **No manual deprecation scenarios.** SC#3's old "three scenarios at phase-verify time" content is dropped. There is nothing to verify manually — the env var is just renamed.

### `.brand-grep-allow` entries (BRAND-04 / SC#4) — REVISED 2026-05-26

- **D-15 (revised):** **No Phase-34-specific entries.** No deprecated alias to allowlist; no `_SKIP_REPO_PREFIXES` to allowlist (it is deleted, not preserved).

- **D-16 (revised):** **Delete `_SKIP_REPO_PREFIXES` rather than allowlist it.** The `packages.py:17` tuple targets a `lattice/` vendor directory that does not exist in this repo (verified: `ls /Users/pat/Personal/agent-research/` shows no `lattice/`). The `.cgignore` mechanism covers any user-driven directory exclusions. Delete the constant, delete the `rel.startswith(p)` check in `_should_skip` (line 27), and delete the test `test_refresh_skips_lattice_dir_manifests`.

- **D-17:** **No edits to `check-brand.sh`**. The script is well-tested (CR-01, WR-03 already addressed); Phase 34 only adds the allowlist file. The script's regex includes `workspace_io|lattice_wiki_core|...` which still triggers on legitimate code elsewhere in the repo (the `workspace_io` package itself, ported-from comments in source-parser/eval-harness, fixture vaults in wiki-io). The minimal allowlist below covers those.

- **D-19 (new):** **Minimal `.brand-grep-allow` content.** Entries are file-path substrings (matched by `grep -vF -f` against `grep -rEl` output):
  ```
  # workspace_io package directory — the package is literally named workspace_io
  packages/workspace-io/

  # Ported-from comments referencing the original lattice-* packages
  packages/source-parser/
  packages/eval-harness/

  # Wiki test fixture vault — round-trip-vault preserves the historical lattice-* layout
  packages/wiki-io/

  # Cross-package imports of workspace_io
  packages/model-adapter/
  agents/graph-wiki-agent/
  plugins/graph-wiki/

  # Historical milestone documentation references the original lattice provenance
  .planning/

  # CLAUDE.md references workspace_io as the canonical package name
  CLAUDE.md
  ```
  Zero entries under `packages/graph-io/` — the sweep eliminates every match there. The planner runs `bash scripts/check-brand.sh` post-sweep with this allowlist to confirm exit 0.

### Verification flow — REVISED 2026-05-26

- **D-18 (revised):** **Phase 34 SC verification order** (planner builds this into VERIFICATION.md):
  1. SC#1: `cg --help` output check (string match: contains "graph-wiki", NOT contains "lattice")
  2. SC#2: `head -1 packages/graph-io/README.md` = `# graph-io`; grep README for `~/.lattice/graph/code.db` returns no matches; grep README for any `lattice` returns no matches.
  3. SC#3: `grep -qF 'GRAPH_WIKI_LOCK_TIMEOUT_MS' packages/graph-io/src/graph_io/update.py` AND `! grep -qF 'LATTICE_GRAPH_LOCK_TIMEOUT_MS' packages/graph-io/` AND `test_cli_exit_codes.py` test passes with the renamed env var. All automated — no manual scenarios.
  4. SC#4: `bash scripts/check-brand.sh` exits 0; `packages/graph-io/` is grep-clean of `lattice|LATTICE`.

### Claude's Discretion

- Whether to factor a helper for the (now trivially small) env-var read in update.py — D-09 keeps the inline shape; no abstraction needed.
- Whether to keep the `_should_skip` function in `packages.py` after dropping the rel-path check, or inline it into the caller. D-16 keeps the function and just deletes the lattice-prefix branch — the `_ignore.should_skip(...)` delegation still has a single caller.
- `.brand-grep-allow` entry ordering and comment style — D-19 prototype is a starting point; planner can tighten or expand as long as `check-brand.sh` exits 0 post-sweep and `packages/graph-io/` is grep-clean.
- Order of edits in the plan waves — Wave 1 still creates the allowlist; Waves 2 are independent edits (README + fixtures, CLI description + packages.py deletion + test_packages.py edits, env var rename); Wave 3 is verification.

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### v1.6 research
- `.planning/research/PITFALLS.md` — historical note about `_SKIP_REPO_PREFIXES` being functional. Revised D-16 supersedes this: the function is dead-weight in this repo, deleted not preserved.

### Requirements + roadmap
- `.planning/REQUIREMENTS.md` — BRAND-01..04 (lines 98–101); pending-phase mapping lines 237–240
- `.planning/ROADMAP.md` — Phase 34 block + SC#1–4. Phase 34's goal and SC#3 were revised to drop the deprecation contract.

### Existing graph-io code (in-scope for editing)
- `packages/graph-io/README.md` — first 3 lines + line 12 are the primary edit target.
- `packages/graph-io/src/graph_io/cli/main.py:45` — argparse `description="lattice code graph CLI"`; D-05 edits.
- `packages/graph-io/src/graph_io/update.py:153-160` (function `_default_lock_timeout`) — D-09 (revised) straight rename.
- `packages/graph-io/src/graph_io/packages.py:17,20-27` — D-16 (revised) deletes `_SKIP_REPO_PREFIXES` and the rel-prefix check in `_should_skip`.

### Test files (in-scope per D-11)
- `packages/graph-io/tests/test_sync_wiki.py`
- `packages/graph-io/tests/test_packages.py` — D-12 (revised) deletes `test_refresh_skips_lattice_dir_manifests`
- `packages/graph-io/tests/test_cli_sync_wiki.py`
- `packages/graph-io/tests/test_cli_exit_codes.py`

### Brand sweep infrastructure (existing)
- `scripts/check-brand.sh` — the BRAND-04 gate. Already well-developed. Phase 34 does NOT modify this script.
- `.brand-grep-allow` at repo root — created by Plan 34-01 with the broader-codebase carve-outs from D-19.

### Existing rebranding precedents
- Phase v1.2 / v1.3 milestones — performed the original lattice → graph-wiki sweep across `agents/`, `plugins/`, `wiki-io/`. Phase 34 finishes the work in `packages/graph-io/`.

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- **`scripts/check-brand.sh`** — already handles multiple brand-pattern checks. Phase 34 uses it as the BRAND-04 gate without modification.
- **`.brand-grep-allow`** format and conventions — established by prior brand sweeps. Comment lines via `#`; blank lines ignored; substring matching via `grep -vF` against file paths.
- **`os.environ.get(...)` pattern** — preserved in D-09's straight-rename refactor.

### Established Patterns
- **Surgical brand sweeps**: edit only brand text, preserve functional code. After this revision, the only functional code touched is `_SKIP_REPO_PREFIXES` — which we are deliberately deleting because it has no callers in this repo's filesystem layout.
- **Allowlist scoped to legitimate uses, not deprecation windows** — entries cover code that should not be rewritten (workspace_io package name, ported-from comments).

### Integration Points
- **D-05 (cli/main.py description) ↔ Phase 33** — Phase 33 expanded `_SUBCOMMANDS` dict but didn't touch the parser description string. Independent.
- **D-09 (update.py) ↔ Phase 29's update.py edits** — Phase 29 shipped changes to `update.run()` ordering. The `_default_lock_timeout()` function is independent of `run()`'s orchestration. No conflict.
- **D-16 (packages.py deletion) ↔ Phase 29's containment-tree work** — Phase 29 reads manifests via `packages.refresh()`. Deleting `_SKIP_REPO_PREFIXES` only widens the set of manifests scanned; if a `lattice/` directory ever appears in this repo, its manifests would now be scanned (which is correct behavior — `.cgignore` is the right knob for user-driven exclusion).
- **D-11..D-12 test edits ↔ Phase 30/31 test additions** — Phase 30 added `test_call_order_pitfall`, Phase 31 added cycle + derived-edge tests. None overlap with the four files Phase 34 edits. Independent.

</code_context>

<specifics>
## Specific Ideas

- D-01..D-04 README diff prototype:
  ```diff
  -# lattice-graph-core
  +# graph-io

  -Code-graph core for the [lattice](../../README.md) ecosystem. Owns:
  +Code-graph backend for graph-wiki. Owns:

  -- SQLite schema + store at `<repo>/.lattice/graph/code.db`
  +- SQLite schema + store at `<paths.graph_dir(workspace)>/code.db` (see `workspace_io.paths` for workspace-mode-aware resolution)

  -The Claude Code plugin shell lives separately at `plugins/lattice-graph/`.
  +The Claude Code plugin shell lives separately at `plugins/graph-wiki/`.
  ```

- D-05 cli/main.py diff:
  ```diff
  -    parser = argparse.ArgumentParser(prog="cg", description="lattice code graph CLI")
  +    parser = argparse.ArgumentParser(prog="cg", description="graph-wiki code graph CLI")
  ```

- D-09 (revised) update.py diff:
  ```diff
   def _default_lock_timeout() -> int:
  -    raw = os.environ.get("LATTICE_GRAPH_LOCK_TIMEOUT_MS")
  +    raw = os.environ.get("GRAPH_WIKI_LOCK_TIMEOUT_MS")
       if raw is None:
           return 30_000
       try:
           return max(0, int(raw))
       except ValueError:
           return 30_000
  ```
  No `import sys` change. No alias. No warning.

- D-16 (revised) packages.py diff:
  ```diff
  -_SKIP_REPO_PREFIXES = ("lattice/",)
  -
  -
   def _should_skip(manifest_path: Path, repo_root: Path, skip_dirs: frozenset[str]) -> bool:
       if _ignore.should_skip(str(manifest_path), skip_dirs):
           return True
  -    try:
  -        rel = manifest_path.relative_to(repo_root).as_posix()
  -    except ValueError:
  -        return False
  -    return any(rel.startswith(p) for p in _SKIP_REPO_PREFIXES)
  +    return False
  ```
  After this edit, `_should_skip` only delegates to `_ignore.should_skip`. Caller in `refresh()` is unchanged.

- D-12 (revised) test_packages.py diff:
  ```diff
  -def test_refresh_skips_lattice_dir_manifests(tmp_path: Path, conn: sqlite3.Connection) -> None:
  -    lattice_pkg = tmp_path / "lattice" / "some-tool"
  -    lattice_pkg.mkdir(parents=True)
  -    (lattice_pkg / "pyproject.toml").write_text('[project]\nname = "tool"\nversion = "0.0.0"\n')
  -
  -    real_pkg = tmp_path / "packages" / "real"
  -    real_pkg.mkdir(parents=True)
  -    (real_pkg / "pyproject.toml").write_text('[project]\nname = "real"\nversion = "0.1.0"\n')
  -
  -    packages.refresh(conn, repo_root=tmp_path, ctx=_CTX)
  -
  -    names = {row[0] for row in conn.execute("SELECT name FROM nodes WHERE kind='package'").fetchall()}
  -    assert "real" in names
  -    assert "tool" not in names
  -
  -
   def test_refresh_skips_cgignore_manifests(tmp_path: Path, conn: sqlite3.Connection) -> None:
  ```

- D-18 (revised) SC verification commands the planner inlines into VERIFICATION.md:
  ```bash
  # SC#1
  uv run cg --help | grep -q 'graph-wiki'
  ! uv run cg --help | grep -q 'lattice'

  # SC#2
  test "$(head -1 packages/graph-io/README.md)" = '# graph-io'
  ! grep -qE 'lattice|LATTICE' packages/graph-io/README.md

  # SC#3
  grep -qF 'GRAPH_WIKI_LOCK_TIMEOUT_MS' packages/graph-io/src/graph_io/update.py
  ! grep -rqF 'LATTICE_GRAPH_LOCK_TIMEOUT_MS' packages/graph-io/
  uv run --package graph-io pytest packages/graph-io/tests/test_cli_exit_codes.py -q

  # SC#4
  bash scripts/check-brand.sh
  ! grep -rEl --exclude-dir=__pycache__ --exclude='*.pyc' 'lattice|LATTICE' packages/graph-io/
  ```

- Pre-sweep snapshot for planner's safety: `bash scripts/check-brand.sh > /tmp/preflight.txt 2>&1 || true`. After sweep, re-run; expect exit 0.

</specifics>

<deferred>
## Deferred Ideas

- **Trim the `check-brand.sh` regex** — `workspace_io|lattice_wiki_core` is overly broad given workspace_io is the current canonical name. A future phase could narrow the regex and shrink `.brand-grep-allow`. Out of scope for Phase 34.
- **README full rewrite** — a comprehensive README modernization (architecture diagrams, getting-started, API reference) is its own future phase.
- **Brand sweep of `plugins/graph-wiki/` or `agents/graph-wiki-agent/`** — explicitly out of scope per BRAND-04. Prior phases handled those.
- **Migration guide / CHANGELOG entry** — irrelevant: single user, no migration needed.
- **`cg` CLI version bump tied to brand sweep** — semver-style version in `pyproject.toml`. Not in Phase 34 scope.

</deferred>

---

*Phase: 34-brand-sweep*
*Context gathered: 2026-05-25; revised 2026-05-26 to drop backwards compat*
