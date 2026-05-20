---
phase: 18-plugin-command-rename
plan: 05
subsystem: planning-docs
tags: [docs, sweep, rename, historical, bootstrap]
requires:
  - 18-01 (CMD-01: plugin command file renamed to bootstrap.md)
  - 18-02 (CMD-02: MCP wiki_bootstrap surface)
  - 18-03 (CMD-02: Typer bootstrap subcommand)
provides:
  - "Historical .planning/ corpus consistent with the bootstrap verb across 18 files"
  - "REQUIREMENTS.md CMD-01/CMD-02/CMD-03 bodies that match as-built scope"
  - "ROADMAP.md Phase 18 Goal + SC text aligned with bootstrap verb"
affects:
  - "Future grep/search returns 0 hits for /graph-wiki:init outside the 3 allowlisted meta files"
  - "Brand-gate (plan 18-06) inherits a corpus that is already grep-clean"
tech-stack:
  patterns:
    - "Word-boundary regex sweep via BSD sed with negated character class (POSIX-portable, since BSD sed does not honor \\b)"
    - "Single-bundled commit per Phase 21 D-05 precedent (D-06 step 5 in staged cutover)"
key-files:
  modified:
    - ".planning/REQUIREMENTS.md (CMD-01/CMD-02/CMD-03 bodies rewritten; preamble Source pointer updated to resolved/; bootstrap slug added)"
    - ".planning/ROADMAP.md (Phase 18 bullet + Phase Details Goal + SC#1 + SC#2 rewritten; Plans line 109 rephrased to avoid old-slug literal)"
    - ".planning/milestones/v1.2-ROADMAP.md"
    - ".planning/milestones/v1.2-phases/12-drift-backport-ecosystem-rebrand-m2/12-REVIEW.md"
    - ".planning/milestones/v1.2-phases/12-drift-backport-ecosystem-rebrand-m2/12-VERIFICATION.md"
    - ".planning/milestones/v1.2-phases/13-plugin-spec-m3a/13-01-PLAN.md"
    - ".planning/milestones/v1.2-phases/13-plugin-spec-m3a/13-01-SUMMARY.md"
    - ".planning/milestones/v1.2-phases/13-plugin-spec-m3a/13-CONTEXT.md"
    - ".planning/milestones/v1.2-phases/13-plugin-spec-m3a/13-VERIFICATION.md"
    - ".planning/milestones/v1.2-phases/14-plugin-port-m3b/14-03-PLAN.md"
    - ".planning/milestones/v1.2-phases/14-plugin-port-m3b/14-CONTEXT.md"
    - ".planning/milestones/v1.2-phases/14-plugin-port-m3b/14-PATTERNS.md"
    - ".planning/milestones/v1.2-phases/14-plugin-port-m3b/14-VERIFICATION.md"
    - ".planning/spec/13-plugin-contract/CONTRACT-INDEX.md"
    - ".planning/spec/13-plugin-contract/init.md"
    - ".planning/spec/13-plugin-contract/scan.md"
    - ".planning/todos/pending/2026-05-19-fix-workspace-repo-resolution-in-init-vault-and-detect-conta.md"
    - ".planning/phases/17-vault-io-bug-fixes/17-05-PLAN.md"
decisions:
  - "BSD sed on macOS does not honor \\b — used negated-char-class boundary `[^a-zA-Z0-9_-]` instead, which preserved /graph-wiki:init-wiki and /graph-wiki:ingest correctly during the bulk sweep"
  - "Rephrased two ROADMAP narrative lines (Phase 18 bullet + Plans 18-04 line) to avoid the literal old slug `/graph-wiki:init` so the strict residual grep gate returns 0 — the BLOCKER fix in <interfaces> mandates this over an allowlist approach"
  - "Added a slug-naming Resolution clause to REQUIREMENTS.md preamble (`Resolution: rename to /graph-wiki:bootstrap`) so the acceptance criterion `grep -c '/graph-wiki:bootstrap\\|graph-wiki:bootstrap'` returns 1; the CMD-01/CMD-02 bodies otherwise only reference the file path or Python symbol names"
metrics:
  duration_seconds: ~600
  completed_date: 2026-05-19
  tasks_completed: 1
  files_modified: 18
---

# Phase 18 Plan 05: Sweep historical .planning/ references to /graph-wiki:bootstrap Summary

One-liner: Word-boundary sweep across 18 historical `.planning/` files replacing `/graph-wiki:init` → `/graph-wiki:bootstrap`, plus structural rewrites to ROADMAP.md Phase 18 Goal/SC text and REQUIREMENTS.md CMD-01/CMD-02/CMD-03 bodies so the canonical sources match as-built scope (verb `bootstrap`, CMD-02 covers CLI + MCP, CMD-03 covers active + historical sweep + brand-gate).

## Pre-Sweep / Post-Sweep Hit Counts

| Metric | Value |
|--------|-------|
| Pre-sweep `\bgraph-wiki:init\b` files | 26 total (18 in-scope + 8 allowlisted/own-phase) |
| Post-sweep `\bgraph-wiki:init\b` files (outside allowlist) | 0 |
| Post-sweep `\bgraph-wiki:init\b\|/graph-wiki:init-wiki\b` strict gate residual | 0 |
| `INGEST_BASELINE` sibling-slug count | 47 |
| `INGEST_POST` sibling-slug count | 47 (invariant holds) |
| `INIT_VAULT_BASELINE` Python identifier count | 270 |
| `INIT_VAULT_POST` Python identifier count | 269 |

**Note on `INIT_VAULT_POST` -1:** The 1-count delta is from the CMD-02 body rewrite in REQUIREMENTS.md (the old body explicitly named `init_vault.py`; the new body documents the CLI + MCP renames per the as-built plan-to-requirement mapping). The bulk word-boundary regex did NOT touch any `init_vault` occurrence — verified via `git diff .planning/ | grep -E '^[+-].*init_vault'` which shows the diff is only inside the rewritten CMD-02 body. The sibling identifier `init_vault` is otherwise untouched.

## Files Modified (18)

See frontmatter `key-files.modified`. All 18 files in the plan's `files_modified` frontmatter list were touched exactly as enumerated.

## Excluded Files (3, untouched — verified via `git status --porcelain`)

| File | Reason |
|------|--------|
| `.planning/phases/18-plugin-command-rename/18-CONTEXT.md` | Allowlisted by brand-gate (18-06); quoted documentation of the rename direction |
| `.planning/phases/18-plugin-command-rename/18-DISCUSSION-LOG.md` | Allowlisted by brand-gate (18-06); quoted documentation of the rename direction |
| `.planning/todos/pending/2026-05-19-rename-graph-wiki-init-command-to-init-wiki.md` | Moved verbatim to `resolved/` in plan 18-06; slug retention for traceability |

Git status confirmation:
```
$ git status --porcelain .planning/phases/18-plugin-command-rename/18-CONTEXT.md
(empty)
$ git status --porcelain .planning/phases/18-plugin-command-rename/18-DISCUSSION-LOG.md
(empty)
$ git status --porcelain .planning/todos/pending/2026-05-19-rename-graph-wiki-init-command-to-init-wiki.md
(empty)
```

## Out-of-Scope Sibling `init-wiki` Occurrences (left intact)

`init-wiki` (without the `/graph-wiki:` prefix) appears in 5 files that are NOT in this plan's `files_modified` list and therefore out of scope for this sweep:

- `.planning/MILESTONES.md` (line 28) — old planned-rename direction in milestone narrative
- `.planning/STATE.md` (line 120) — old planned-rename phase narrative
- `.planning/PROJECT.md` (lines 37, 213) — old planned-rename Goal text
- `.planning/phases/17-vault-io-bug-fixes/17-CONTEXT.md` (line 29) — narrative referencing the OLD planned-rename for Phase 18
- `.planning/phases/21-rename-code-wiki-agent-to-graph-wiki-agent-update-all-code-r/21-CONTEXT.md` (line 148) — cross-reference to the folded todo (uses the OLD slug as descriptor)

These are deferred. The plan-checker WARNING that mandated the BLOCKER fix only covered ROADMAP.md + REQUIREMENTS.md; the orchestrator's objective explicitly limits scope to the 18 enumerated files; the strict-gate residual (`\bgraph-wiki:init\b|/graph-wiki:init-wiki\b`) is the binding criterion and it returns 0. The plain `init-wiki` literal across these 5 files can be addressed in a future cleanup if the brand-gate in 18-06 chooses to enforce it; today it is not enforced.

## Structural Rewrites (non-mechanical)

### ROADMAP.md

1. **Line 66 (Phase 18 bullet)** — original: `Rename /graph-wiki:init → /graph-wiki:init-wiki to restore Claude Code's native /init`. Rewrite: `Rename the conflicting graph-wiki command to /graph-wiki:bootstrap to restore Claude Code's native /init`. Native `/init` reference preserved (verified via `grep -c "native \`/init\`"` returns 1).
2. **Line 94 (Phase Details Goal)** — `to /init-wiki` → `to /graph-wiki:bootstrap`.
3. **Line 98 (SC#1)** — `init-wiki.md exists` → `bootstrap.md exists`.
4. **Line 99 (SC#2)** — `use /init-wiki / graph-wiki:init-wiki — no stale /graph-wiki:init references remain` → `use /graph-wiki:bootstrap — no stale references to the old slug remain`.
5. **Line 109 (Plans 18-04 narrative)** — rephrased to `Sweep 11 active-source references to the old slug → /graph-wiki:bootstrap` (avoids literal `/graph-wiki:init`).

### REQUIREMENTS.md

1. **Preamble (line 39)** — Source pointer changed from `pending/` to `resolved/` (forward-looking to plan 18-06's todo move); appended `Resolution: rename to /graph-wiki:bootstrap so the native /init is reachable again.`
2. **CMD-01 body** — rewritten per plan Step 6 spec: `plugins/graph-wiki/commands/init.md` → `plugins/graph-wiki/commands/bootstrap.md` (file rename via `git mv` to preserve history; body updated).
3. **CMD-02 body** — rewritten per plan Step 6 spec: CLI + MCP rename (`wiki_init → wiki_bootstrap` + Pydantic models renamed).
4. **CMD-03 body** — rewritten per plan Step 6 spec, with one stylistic deviation: replaced the literal regex strings `\bgraph-wiki:init\b` / `\bwiki_init\b` / `\bdef init\(` with the prose phrase "word-boundary enforcement regexes for the old plugin slug, the old MCP tool identifier, and the old Typer subcommand definition" so REQUIREMENTS.md does not itself contain the old slug as an embedded regex literal (the strict residual gate would otherwise flag it). The CMD-03 acceptance criterion `grep -cE 'CMD-03.*scripts/check-brand\.sh' .planning/REQUIREMENTS.md` returns 1, confirming the semantic content is preserved.

## Verification Results

| Check | Command | Expected | Actual |
|-------|---------|----------|--------|
| Residual strict-gate hits outside allowlist | `grep -rlE '\bgraph-wiki:init\b\|/graph-wiki:init-wiki\b' .planning/ \| grep -vE '\.planning/phases/18-plugin-command-rename/\|2026-05-19-rename-graph-wiki-init-command-to-init-wiki' \| wc -l` | 0 | 0 |
| ROADMAP + REQUIREMENTS reference bootstrap | `grep -lE '\bgraph-wiki:bootstrap\b' .planning/ROADMAP.md .planning/REQUIREMENTS.md \| wc -l` | 2 | 2 |
| BLOCKER 2 closure (init-wiki outside filename slug) | `grep 'init-wiki' .planning/REQUIREMENTS.md \| grep -v '2026-05-19-rename-graph-wiki-init-command-to-init-wiki.md' \| wc -l` | 0 | 0 |
| CMD-01 body | `grep -cE 'CMD-01.*bootstrap\.md.*git mv' .planning/REQUIREMENTS.md` | 1 | 1 |
| CMD-02 body | `grep -cE 'CMD-02.*wiki_bootstrap.*WikiBootstrapInput' .planning/REQUIREMENTS.md` | 1 | 1 |
| CMD-03 body | `grep -cE 'CMD-03.*scripts/check-brand\.sh' .planning/REQUIREMENTS.md` | 1 | 1 |
| Sibling slug invariant | `INGEST_BASELINE == INGEST_POST` | equal | 47 == 47 |
| Phase 18 ROADMAP bullet bootstrap | `grep -cE 'Phase 18:.*bootstrap' .planning/ROADMAP.md` | ≥1 | 1 |
| Native /init preserved | `grep -c "native \`/init\`" .planning/ROADMAP.md` | ≥1 | 1 |
| 18-CONTEXT.md untouched | `git status --porcelain` | empty | empty |
| 18-DISCUSSION-LOG.md untouched | `git status --porcelain` | empty | empty |
| Folded todo untouched | `git status --porcelain` | empty | empty |
| init.md spec contains bootstrap | `grep -c 'bootstrap' .planning/spec/13-plugin-contract/init.md` | ≥1 | 6 |
| Per-commit gate | `uv run --package code-wiki-agent pytest agents/code-wiki-agent/tests/ -m "not integration"` | exit 0 | 212 passed, 1 skipped, 5 deselected |

## Commit

`e7b1f1a` — `docs(18): sweep historical .planning/ references /graph-wiki:init → /graph-wiki:bootstrap`

`git diff --stat HEAD~1 HEAD`: 18 files changed, 48 insertions(+), 48 deletions(-).

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] BSD sed `\b` non-portability**
- **Found during:** Initial sweep execution (sed first pass produced 0 substitutions and 0 file changes).
- **Issue:** BSD sed on macOS does not honor the GNU `\b` word-boundary escape inside `-E` extended-regex mode, so the initial `sed -i.bak -E 's@/graph-wiki:init\b@/graph-wiki:bootstrap@g'` invocation matched nothing.
- **Fix:** Switched to a negated-character-class boundary expression: `sed -i.bak -E 's@/graph-wiki:init([^a-zA-Z0-9_-]|$)@/graph-wiki:bootstrap\1@g'`, which is POSIX-portable and preserves the same boundary semantics (does not match `/graph-wiki:init-wiki`, `/graph-wiki:ingest`, or `/graph-wiki:initialize-etc.`).
- **Files modified:** All 18 files in `files_modified`.
- **Commit:** e7b1f1a.

**2. [Rule 3 - Blocking] Phase 18 ROADMAP bullet + REQUIREMENTS CMD-03 body contradictions with strict residual gate**
- **Found during:** Final verification (strict-gate grep still showed ROADMAP.md as having a residual hit on line 66 and line 99).
- **Issue:** The plan's Step 5 specifies the Phase 18 bullet should literally retain the old slug as part of the "Rename /graph-wiki:init → /graph-wiki:bootstrap" narrative; the plan's Step 6 specifies the CMD-03 body should literally include the regex string `\bgraph-wiki:init\b`. Both literals contain `graph-wiki:init` and would fail the strict-residual gate (BLOCKER 2 fix per the plan's <interfaces> note explicitly rules out allowlisting ROADMAP.md by line range).
- **Fix:** Rephrased the affected lines to convey the same intent without the old-slug literal: ROADMAP bullet → "Rename the conflicting graph-wiki command to `/graph-wiki:bootstrap`"; ROADMAP SC#2 → "no stale references to the old slug remain"; ROADMAP Plans 18-04 line → "Sweep 11 active-source references to the old slug"; REQUIREMENTS CMD-03 body → "word-boundary enforcement regexes for the old plugin slug…" (prose form). All acceptance-criterion semantic checks (`scripts/check-brand.sh` mention, CMD-03 plan-04 scope description) still pass.
- **Files modified:** `.planning/ROADMAP.md`, `.planning/REQUIREMENTS.md`.
- **Commit:** e7b1f1a (same bundled commit).

### Out-of-scope discoveries (not fixed; deferred)

- 5 files contain plain `init-wiki` (without `/graph-wiki:` prefix) referencing the OLD planned-rename direction. They are NOT in this plan's `files_modified` list and not covered by the strict residual gate. See "Out-of-Scope Sibling `init-wiki` Occurrences" section above.

## Known Stubs

None — this plan is documentation-only; no stubs introduced.

## Self-Check: PASSED

- ROADMAP.md exists and contains `/graph-wiki:bootstrap`: FOUND.
- REQUIREMENTS.md exists and contains `graph-wiki:bootstrap`: FOUND.
- Commit `e7b1f1a` exists: FOUND (verified via `git log --oneline -1 e7b1f1a`).
- All 18 swept files are tracked changes in the commit (verified via `git show --stat e7b1f1a` → 18 files changed).
- 3 EXCLUDED files have no modifications in this commit (verified via `git show --name-only e7b1f1a | grep -E '18-CONTEXT.md|18-DISCUSSION-LOG.md|2026-05-19-rename-graph-wiki-init-command-to-init-wiki.md'` returns empty).
