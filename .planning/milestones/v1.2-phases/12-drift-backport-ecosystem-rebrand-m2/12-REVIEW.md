---
phase: 12-drift-backport-ecosystem-rebrand-m2
reviewed: 2026-05-18T00:00:00Z
depth: standard
files_reviewed: 30
files_reviewed_list:
  - .brand-grep-allow
  - .gitignore
  - CLAUDE.md
  - agents/code-wiki-agent/src/code_wiki_agent/commands/lint.py
  - agents/code-wiki-agent/src/code_wiki_agent/commands/scan.py
  - agents/code-wiki-agent/src/code_wiki_agent/prompts/_fragments/architecture_overview.py
  - agents/code-wiki-agent/tests/prompts/__snapshots__/test_prompt_snapshots.ambr
  - agents/code-wiki-agent/tests/prompts/test_project_context.py
  - agents/code-wiki-agent/tests/prompts/test_prompt_snapshots.py
  - packages/vault-io/DRIFT-DECISIONS-RAW.md
  - packages/vault-io/DRIFT-DECISIONS.md
  - packages/vault-io/src/vault_io/append_log.py
  - packages/vault-io/src/vault_io/assets/AGENTS.md.template
  - packages/vault-io/src/vault_io/assets/CLAUDE.md.template
  - packages/vault-io/src/vault_io/assets/cursorrules.template
  - packages/vault-io/src/vault_io/assets/index.md.template
  - packages/vault-io/src/vault_io/assets/log.md.template
  - packages/vault-io/src/vault_io/assets/page-templates/app.md
  - packages/vault-io/src/vault_io/assets/page-templates/package.md
  - packages/vault-io/src/vault_io/assets/page-templates/source.md
  - packages/vault-io/src/vault_io/git_state.py
  - packages/vault-io/src/vault_io/init_vault.py
  - packages/vault-io/src/vault_io/layout_io.py
  - packages/vault-io/src/vault_io/lint/container.py
  - packages/vault-io/src/vault_io/lint/dependency.py
  - packages/vault-io/src/vault_io/scan_monorepo.py
  - packages/vault-io/src/vault_io/update_index.py
  - packages/vault-io/src/vault_io/update_tokens.py
  - plugins/.gitkeep
  - scripts/check-brand.sh
  - scripts/drift-diff.sh
findings:
  critical: 1
  warning: 5
  info: 3
  total: 9
status: issues_found
---

# Phase 12: Code Review Report

**Reviewed:** 2026-05-18
**Depth:** standard
**Files Reviewed:** 30
**Status:** issues_found

## Summary

Phase 12 is overwhelmingly a documentation + mechanical-rename exercise (lattice → graph-wiki) plus two net-new shell scripts (`drift-diff.sh`, `check-brand.sh`) and one allowlist (`.brand-grep-allow`). The mechanical rename across the 20+ Python sources and asset templates landed cleanly — no stale imports, broken symbols, or dangling identifiers in the reviewed code paths. Drift-decision docs match the raw diff dump and assign defensible verdicts. Test snapshots and project-context tests have been regenerated and contain only `graph-wiki:layout:*` sentinels.

However, **the BRAND-04 grep gate is silently neutered**: blank lines in `.brand-grep-allow` cause BSD `grep -vF -f` to invert-match every line, so the gate has been giving a false "OK" since landing. Verified locally — see CR-01 below. This is the single blocker. The remaining findings are quality-tier: a portability hazard in `drift-diff.sh`, a behavioral break against existing upstream vaults via the layout-sentinel rename, and a small redundancy in how comments are passed to `grep -vF`.

## Critical Issues

### CR-01: BRAND-04 grep gate is a no-op on macOS — blank lines in allowlist match every input line

**File:** `scripts/check-brand.sh:25-27` (in concert with `.brand-grep-allow`)

**Issue:** `.brand-grep-allow` contains 14 blank lines (lines 16, 22, 30, 36, 52, 57, 64, 72, 78, 83, 88, 96, 110, 119, etc. — grep counts 14 total). When this file is passed to `grep -vF -f .brand-grep-allow`, BSD grep (the macOS default — verified with `/usr/bin/grep` on this machine) treats an empty pattern as **matching every line**. Combined with `-v`, this **excludes every line** of input, so `HITS` is unconditionally empty and the gate always reports "BRAND-04 OK".

Proof, run on the working tree at the time of review:

```
$ /usr/bin/grep -rEl 'lattice|LATTICE|lattice_workspace|lattice_wiki_core' \
    packages/ agents/ plugins/ .planning/ CLAUDE.md 2>/dev/null | wc -l
     290
$ /usr/bin/grep -rEl 'lattice|...' ... | /usr/bin/grep -vF -f .brand-grep-allow | wc -l
       0          # ← every hit excluded, regardless of allowlist content
$ /usr/bin/grep -rEl 'lattice|...' ... \
    | /usr/bin/grep -vF -f <(/usr/bin/grep -vE '^#|^$' .brand-grep-allow) | wc -l
      18          # ← what the gate WOULD report if blanks/comments were stripped
```

So a future regression that, e.g., adds a fresh `from lattice_wiki_core import ...` to `packages/vault-io/src/vault_io/_workspace.py` would not be caught — the gate would still print "BRAND-04 OK: zero unallowlisted hits". The 18 hits that surface after stripping blanks are all `__pycache__/*.pyc` files (compiled bytecode containing the literal `lattice` strings from `.brand-grep-allow` allowlisted-by-rationale sources), which a clean CI checkout won't have, masking the bug there too.

The comment in `.brand-grep-allow:3-5` asserts "Lines starting with `#` are comments and are ignored by `grep -vF -f` (no line in `grep -rEl` output starts with `#`...)". That reasoning is correct for `#`-prefixed lines, but it does not address blank lines — and BSD's empty-pattern semantics are the actual failure mode.

**Fix:** Strip blank and comment lines from the allowlist before passing to `grep -vF`. Two equivalent options; the first is the smallest diff:

```bash
# scripts/check-brand.sh
HITS=$(grep -rEl 'lattice|LATTICE|lattice_workspace|lattice_wiki_core' \
    packages/ agents/ plugins/ .planning/ CLAUDE.md 2>/dev/null \
    | grep -vF -f <(grep -vE '^[[:space:]]*(#|$)' "$ALLOWLIST") || true)
```

Or, equivalently, materialize a cleaned list and re-use it:

```bash
ALLOW_PATTERNS=$(mktemp)
trap 'rm -f "$ALLOW_PATTERNS"' EXIT
grep -vE '^[[:space:]]*(#|$)' "$ALLOWLIST" > "$ALLOW_PATTERNS"
HITS=$(grep -rEl '...' packages/ agents/ ... | grep -vF -f "$ALLOW_PATTERNS" || true)
```

After applying the fix, also add an assertion test or a sanity run in CI (e.g., insert a deliberate unallowlisted `lattice` token into a throwaway file, run `check-brand.sh`, assert non-zero exit, then remove the file). Otherwise this class of bug — the gate that fails open — will recur silently.

## Warnings

### WR-01: drift-diff.sh hardcodes `/Users/pat/Personal/lattice` — non-portable

**File:** `scripts/drift-diff.sh:18`

**Issue:** `UPSTREAM_REPO=/Users/pat/Personal/lattice` is the absolute path to the upstream repo on the author's machine. The script's `set -euo pipefail` plus the "FATAL: upstream repo not found at $UPSTREAM_REPO" guard at line 51-54 means the failure is loud — but any other operator (a second contributor, CI, a future Pat on a different host) cannot run the regeneration command documented in the file header and in `DRIFT-DECISIONS.md` §Re-sync. Phase 12 plan-meta calls out re-sync re-runs as a real future use case ("re-runnable cheaply by future phases (13, 14, 16) and by any future re-sync between vault-io and upstream lattice-wiki-core" — `scripts/check-brand.sh:10-11`).

**Fix:** Allow an environment override at the top of the script:

```bash
UPSTREAM_REPO="${UPSTREAM_REPO:-/Users/pat/Personal/lattice}"
```

Then the existing "FATAL: upstream repo not found" guard still catches operators who didn't set the var. Update `DRIFT-DECISIONS.md:45` Re-sync protocol accordingly:

```
UPSTREAM_REPO=/path/to/lattice bash scripts/drift-diff.sh > packages/vault-io/DRIFT-DECISIONS-RAW.md
```

### WR-02: Layout sentinel rename breaks `read_layout()` for existing upstream lattice-wiki vaults

**File:** `packages/vault-io/src/vault_io/layout_io.py:32-33` (in concert with `CLAUDE.md` §Constraints)

**Issue:** `layout_io.py` previously read/wrote layout blocks delimited by `<!-- lattice-wiki:layout:start -->` / `<!-- lattice-wiki:layout:end -->`. Phase 12 renamed both sentinels to `<!-- graph-wiki:layout:start -->` / `<!-- graph-wiki:layout:end -->`. The compiled regex `_BLOCK_RE` (line 35-38) anchors on the new strings exactly; there is no legacy fallback.

The round-trip fixture vault at `packages/vault-io/tests/fixtures/round-trip-vault/CLAUDE.md:161,196` still uses the old `<!-- lattice-wiki:layout:start -->` sentinel pair (deliberately, per the R-01 allowlist entry). `read_layout()` against that file now returns `None` — silently. Cross-check with `CLAUDE.md` §Constraints:

> **Format compatibility**: must read existing upstream lattice-wiki vaults without modification — preserve frontmatter schema, layout block format, wikilink/citation conventions

The new sentinel format breaks that constraint for any vault that was originally bootstrapped by upstream lattice-wiki. Downstream symptoms in scan/lint paths:
- `scan_monorepo._load_existing_pages` (line 643-655): `read_layout()` returns None → the `for c in layout.get(...)` branch is skipped → custom-pinned containers are invisible → diffing degrades to apps/+packages/ only.
- `lint/container.py:33-35`: emits the user-facing string "no layout block found in CLAUDE.md (run /graph-wiki:bootstrap)" for what is in fact a perfectly valid upstream vault.
- `scan_monorepo.discover_workspaces(..., pinned_containers=None)` (when called from the rebranded CLI) falls back to heuristic walk; for a vault whose pinned-container shape diverges from the default, this silently misclassifies workspaces.

This may be the intended hard-break — Phase 12 is the rebrand phase and the project explicitly chose to drop the lattice identifier — but the change is not called out in `DRIFT-DECISIONS.md` and contradicts the standing project-constraint in `CLAUDE.md`. If the break is intentional, at minimum update `CLAUDE.md` §Constraints to reflect the new posture; if not, accept both sentinel forms on read while writing only the new one.

**Fix:** Two options.

(a) **Accept both formats on read.** Smallest diff; preserves the format-compat constraint for read-only paths.

```python
# packages/vault-io/src/vault_io/layout_io.py
LAYOUT_START = "<!-- graph-wiki:layout:start -->"
LAYOUT_END = "<!-- graph-wiki:layout:end -->"
_LEGACY_LAYOUT_START = "<!-- lattice-wiki:layout:start -->"
_LEGACY_LAYOUT_END = "<!-- lattice-wiki:layout:end -->"

_BLOCK_RE = re.compile(
    r"(?:" + re.escape(LAYOUT_START) + "|" + re.escape(_LEGACY_LAYOUT_START) + r")"
    r"\s*\n```yaml\s*\n(.*?)\n```\s*\n"
    r"(?:" + re.escape(LAYOUT_END) + "|" + re.escape(_LEGACY_LAYOUT_END) + r")",
    re.DOTALL,
)
```

`write_layout()` keeps emitting the new format only, so any subsequent write migrates the vault.

(b) **Accept the break and document it.** Update `CLAUDE.md` §Constraints to add an explicit "lattice-wiki vaults must be migrated to the graph-wiki sentinel pair before use" caveat, and add a one-shot migration helper or a clear `read_layout` warning that names the legacy sentinel.

### WR-03: `.brand-grep-allow` comment lines passed as `grep -vF` patterns are wasteful and fragile

**File:** `.brand-grep-allow` (consumed by `scripts/check-brand.sh:27`)

**Issue:** The file-header comment (lines 1-15, 17-19, 24-27, etc.) explains the allowlist semantics in prose. Those comment lines are passed verbatim to `grep -vF -f` as fixed-string patterns. The author's reasoning at `.brand-grep-allow:4-5` is correct that `#`-prefixed lines can't match `grep -rEl` filename output, but the design relies on a content-dependent invariant: a future edit that introduces a path-fragment-like substring inside a comment line (e.g. someone writes `# example: packages/vault-io/foo.py`) would silently broaden the allowlist. Couple this with CR-01 and the gate's correctness depends on two implicit invariants holding simultaneously.

**Fix:** The fix to CR-01 (filter blanks AND comments before passing to `grep -vF`) resolves this finding as well. With `grep -vE '^[[:space:]]*(#|$)'` applied first, comment content is no longer a pattern and the invariant collapses to "every effective pattern is the rationale-attached path fragment on its own line."

### WR-04: `_mechanical_pass` comment claim about upstream `LINTED_TOPS` is stale

**File:** `agents/code-wiki-agent/src/code_wiki_agent/commands/lint.py:58-63`

**Issue:** The comment says

> Ported verbatim from lint_wiki.py (line 59 — note: upstream uses {"wiki", "work"}, …)

but the local set defined on line 63 is `{"wiki", "work", "concepts", "packages", "apps", "domains", "adrs"}` and the body on line 142 further unions `{wiki.name}`. The "ported verbatim from lint_wiki.py" framing is inaccurate — the divergence is intentional (the rationale follows in the same comment) but the wording reads as if the constant matches upstream. After the lattice → graph-wiki rebrand this is a place a future reader will look for the source-of-truth justification, so the wording should be tightened. Low priority.

**Fix:** Change "Ported verbatim from lint_wiki.py" to "Adapted from lint_wiki.py" or "Diverges from lint_wiki.py — see rationale below."

### WR-05: `scripts/drift-diff.sh` re-runs the date command with implicit GNU/BSD compatibility assumption

**File:** `scripts/drift-diff.sh:66`

**Issue:** `DIFF_TIMESTAMP=$(date -u +%Y-%m-%dT%H:%M:%SZ)` works on both BSD (macOS) and GNU coreutils because both honor `-u` and the strftime format. This isn't a bug today, but the script is otherwise scrupulous about portability guards (`set -euo pipefail`, explicit SHA-equality checks, `diff` rc handling). Worth one-line documenting the implicit cross-platform expectation so a future contributor doesn't reach for `date --rfc-3339=seconds` (GNU-only) or BSD-specific flags.

**Fix:** Optional one-liner comment near line 66:

```bash
# `-u` and the strftime format work uniformly on BSD (macOS) + GNU coreutils.
DIFF_TIMESTAMP=$(date -u +%Y-%m-%dT%H:%M:%SZ)
```

## Info

### IN-01: `init_vault.py` references workspace bootstrap that doesn't exist yet

**File:** `packages/vault-io/src/vault_io/init_vault.py:154-158, 163-165`

**Issue:** The docstring says "Phase 5 will provide a workspace-bootstrap equivalent" but lines 163-165 actively create `<workspace>/raw/` and `<workspace>/work/`, which is the rebranded workspace-bootstrap behavior. The docstring is out-of-date relative to the implementation. Not a behavioral bug — just stale prose. Not introduced by phase 12 (the rename) but surfaced by reading the rebranded file. Leave-as-is is fine.

**Fix:** Optional; consider updating the docstring on a later sweep:

```python
"""Bootstrap a Code Wiki at `wiki_path`.

Creates the wiki directory and seeds it with starter templates. Also creates
sibling `raw/` and `work/` directories under `<workspace>/` — those used to
belong to a separate workspace.init() helper upstream; here they're inlined.
"""
```

### IN-02: `lint/container.py` "run /graph-wiki:bootstrap" suggestion will mislead users on missing layout

**File:** `packages/vault-io/src/vault_io/lint/container.py:35`

**Issue:** When `read_layout()` returns None (covered by WR-02), the returned string is `"no layout block found in CLAUDE.md (run /graph-wiki:bootstrap)"`. There is no `/graph-wiki:bootstrap` slash-command in this repo today — `init_vault.py` is a Python module invoked via `code-wiki-agent init` (per its argparse `main()` at line 282-315). The slash-command vocabulary is forward-looking (Phase 14 plugin port per `plugins/.gitkeep`), but until the plugin lands, the suggested remediation does not work.

**Fix:** Pick a more accurate suggestion until the plugin ships. Either:

```python
return ["no layout block found in CLAUDE.md (run `code-wiki-agent init`)"]
```

or the language-neutral "run init to rebuild the layout block." Low priority.

### IN-03: `_dt.date.fromtimestamp` on `scan_monorepo.py:834` ignores timezone

**File:** `packages/vault-io/src/vault_io/scan_monorepo.py:834`

**Issue:** `mtime` is computed from local-system time via `_dt.date.fromtimestamp(md.stat().st_mtime)`. The rest of the codebase prefers UTC (e.g., `drift-diff.sh` line 66, `scan_monorepo.py:1047`). This is pre-existing (predates phase 12 by inspection of the upstream commit referenced in `DRIFT-DECISIONS.md`), so it's strictly out-of-scope for this review. Noting it once so the next person to touch this codepath doesn't have to re-derive it.

**Fix:** Out of scope for phase 12. If touched later, prefer `_dt.datetime.fromtimestamp(md.stat().st_mtime, tz=_dt.timezone.utc).date().isoformat()`.

---

_Reviewed: 2026-05-18_
_Reviewer: Claude (gsd-code-reviewer)_
_Depth: standard_
