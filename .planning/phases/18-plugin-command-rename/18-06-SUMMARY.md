---
phase: 18-plugin-command-rename
plan: 06
subsystem: tooling/brand-gate
tags: [brand-gate, ci-enforcement, cmd-rename, hard-cut, phase-18-final]
requires: [18-01, 18-02, 18-03, 18-04, 18-05]
provides: [brand-gate-cmd-enforcement]
affects: [scripts/check-brand.sh, .brand-grep-allow]
tech_added: []
patterns_used: [grep-vF-allowlist, word-boundary-regex, stash-push-stash-drop-non-destructive-revert]
key_files_created:
  - .planning/todos/resolved/2026-05-19-rename-graph-wiki-init-command-to-init-wiki.md (via git mv R100)
  - .planning/phases/18-plugin-command-rename/18-06-SUMMARY.md (this file)
key_files_modified:
  - scripts/check-brand.sh (+30 lines — CHECK 2 + CHECK 3 added)
  - .brand-grep-allow (+10 lines — Phase 18 section: 2 surgical exemptions)
  - docs/cancellation.md (Rule 1: missed-sweep fix — wiki_init → wiki_bootstrap)
  - .planning/intel/apis.json (Rule 1: missed-sweep — MCP entry renamed)
  - .planning/intel/files.json (Rule 1: missed-sweep — exports list updated)
  - .planning/milestones/v1.2-phases/16-carry-forward-debt-cleanup/16-CONTEXT.md (Rule 1: missed-sweep)
  - .planning/phases/17-vault-io-bug-fixes/17-CONTEXT.md (Rule 1: missed-sweep)
decisions:
  - "Two surgical allowlist exemptions only — `.planning/phases/18-plugin-command-rename/` and `.planning/todos/resolved/<folded-todo>` — no parent-directory wildcards (T-18-18 mitigation)"
  - "Revised plan stash-push + stash-drop for CHECK 3 RED revert (NOT git checkout --) to avoid silent wipe of unrelated cli.py edits per plan-checker WARNING 2"
  - "Rule-1 missed-sweep fixes folded into the same commit rather than deferred — five files contained stale `wiki_init` references missed by 18-04/18-05 that CHECK 2 would have failed on"
metrics:
  duration_min: ~15
  commits: 1
  files_changed: 8
  tasks_completed: 4
  completed_date: 2026-05-19
---

# Phase 18 Plan 06: Brand-Gate Enforcement + Folded Todo Summary

Extended `scripts/check-brand.sh` with two new checks (`graph-wiki:init|wiki_init` regex + `def init(` in cli.py) so CI fails on any reintroduction of the renamed `/graph-wiki:bootstrap` surface; folded the resolved todo into `.planning/todos/resolved/` via `git mv`. Closes the brand-gate-enforcement portion of CMD-03 and completes Phase 18 D-06 step 6.

## What Built

### scripts/check-brand.sh — 2 new checks appended after the existing BRAND-04 lattice block

**CHECK 2 — CMD-rename pattern**
- Regex: `graph-wiki:init\b|\bwiki_init\b`
- Scope: `packages/ agents/ plugins/ .planning/ scripts/ docs/ README.md CLAUDE.md`
- Filters through `.brand-grep-allow` with the existing BSD-grep blank-line workaround
- `--exclude-dir=__pycache__ --exclude='*.pyc'` preserved
- Failure message: `BRAND-CMD FAIL: ${COUNT2} unallowlisted hits for graph-wiki:init|wiki_init`

**CHECK 3 — Typer subcommand regression guard**
- Regex: `^\s*def init\(`
- Scope: ONLY `agents/code-wiki-agent/src/code_wiki_agent/cli.py`
- No allowlist filter (the file has zero matches post-rename)
- `2>/dev/null` swallows missing-file noise
- Failure message: `BRAND-CMD-CLI FAIL: def init( reintroduced in agents/code-wiki-agent/src/code_wiki_agent/cli.py`

**Tail message** updated from `BRAND-04 OK: zero unallowlisted hits` to `BRAND-04 OK: zero unallowlisted hits (BRAND-04 lattice + BRAND-CMD graph-wiki:init|wiki_init + BRAND-CMD-CLI def init( all clean)` — preserves `OK` literal and exit 0.

### .brand-grep-allow — 2 surgical exemptions (Phase 18 section appended)

| Path fragment | Rationale |
|---|---|
| `.planning/phases/18-plugin-command-rename/` | Phase 18 meta — quoted documentation of the rename direction (CONTEXT.md, DISCUSSION-LOG.md). |
| `.planning/todos/resolved/2026-05-19-rename-graph-wiki-init-command-to-init-wiki.md` | Folded todo filename slug retains the older "init-wiki" rename direction; content unchanged for traceability. |

No parent-directory wildcards. No `.planning/phases/` or `.planning/todos/` blanket entries.

### Folded todo moved via git mv

- `R100 .planning/todos/pending/2026-05-19-rename-graph-wiki-init-command-to-init-wiki.md → .planning/todos/resolved/2026-05-19-rename-graph-wiki-init-command-to-init-wiki.md`
- `similarity index 100%` — content byte-identical, filename slug retained per 18-CONTEXT.md "Folded Todos" decision.

### Rule-1 missed-sweep fixes (5 files)

CHECK 2 surfaced five files that contained stale `wiki_init` references missed by earlier plans 18-04 (active-source sweep) and 18-05 (historical sweep). Per Rule 1 (auto-fix bugs — outdated content created by missed-sweep), they were updated in this commit rather than deferred:

| File | Edit |
|------|------|
| `docs/cancellation.md:204` | "Tools without fan-out: \`wiki_log\` and **`wiki_init`**" → **`wiki_bootstrap`** |
| `.planning/intel/apis.json:146-148` | `"mcp: wiki_init"` entry + `"path": "wiki_init"` → `wiki_bootstrap` |
| `.planning/intel/files.json:601` | server.py exports list: `wiki_init` → `wiki_bootstrap` |
| `.planning/milestones/v1.2-phases/16-carry-forward-debt-cleanup/16-CONTEXT.md:160` | MCP surface listing `(wiki_init/scan/...)` → `(wiki_bootstrap/scan/...)` |
| `.planning/phases/17-vault-io-bug-fixes/17-CONTEXT.md:158` | MCP surface listing same edit as above |

## Red-then-Green Sanity Transcript (Task 3)

**Constraint:** the pre-existing BRAND-04 (lattice) CHECK 1 still fails on 78 unallowlisted hits left over from prior plans (all in `.planning/milestones/v1.2-phases/` and `.planning/phases/21-...` — out of scope per orchestrator context: "BRAND-04 references may still fail — that's Phase 21's scope, NOT this plan's concern"). CHECK 1 fails first and blocks the live full-gate from reaching CHECK 2/3. The sanity check was therefore performed by running the exact CHECK 2/3 grep invocations in isolation (same regex, same scope, same allowlist filter as the gate uses).

### CHECK 2 sanity (graph-wiki:init|wiki_init)

```
=== RED: inject /graph-wiki:init into scripts/_brand_gate_test.tmp ===
Hits: scripts/_brand_gate_test.tmp
BRAND-CMD FAIL: 1 unallowlisted hits
RED exit (expect 1): 1

=== GREEN: remove temp file ===
GREEN exit (expect 0): 0
```

### CHECK 3 sanity (def init( in cli.py)

```
=== Step 4a — clean tree precondition ===
git status --porcelain agents/.../cli.py: (empty) → proceed.

=== Step 4b — inject `def init(): pass` at end of cli.py ===
Tail of cli.py:
    app()
def init(): pass

=== Step 4c — CHECK 3 grep ===
630:def init(): pass
BRAND-CMD-CLI FAIL: def init( reintroduced
RED exit (expect 1): 1

=== Step 4d — revert via stash push + stash drop (NOT checkout --) ===
Saved working directory and index state On worktree-agent-...: phase18-06-task3-red-injection
stash push RC: 0
Dropped refs/stash@{0} (8dadcdf...)
stash drop RC: 0

=== Step 4e — confirm clean ===
git status --porcelain cli.py: (empty)
def init( count: 0

=== Step 4f — CHECK 3 grep ===
GREEN: no hits
```

No residue: `scripts/_brand_gate_test.tmp` deleted; `cli.py` byte-for-byte restored.

## Final Gate Output

```
$ bash scripts/check-brand.sh
[...78 BRAND-04 lattice hits — pre-existing, out of scope...]
BRAND-04 FAIL: 78 unallowlisted hits
exit code: 1
```

The new CHECK 2 + CHECK 3 are proven correct via isolated invocation (above). The full-gate exit code is non-zero because of pre-existing CHECK 1 (lattice) residue, which the parallel_execution context explicitly defers: "BRAND-04 `code-wiki-agent` references may still fail — that's Phase 21's scope, NOT this plan's concern."

For the post-Phase-21 future state (or anyone wanting to verify CHECK 2/3 standalone), the isolated invocation is:

```bash
# CHECK 2:
grep -rEl --exclude-dir=__pycache__ --exclude='*.pyc' \
    'graph-wiki:init\b|\bwiki_init\b' \
    packages/ agents/ plugins/ .planning/ scripts/ docs/ README.md CLAUDE.md 2>/dev/null \
    | grep -vF -f <(grep -vE '^[[:space:]]*(#|$)' .brand-grep-allow) || echo "(no hits — GREEN)"

# CHECK 3:
grep -nE '^\s*def init\(' agents/code-wiki-agent/src/code_wiki_agent/cli.py 2>/dev/null || echo "(no hits — GREEN)"
```

Both return `(no hits — GREEN)` on this commit.

## Per-Commit Gate

```
$ uv run --package code-wiki-agent pytest agents/code-wiki-agent/tests/ -m "not integration" -q
212 passed, 1 skipped, 5 deselected in 20.79s
```

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Missed-sweep bug] `docs/cancellation.md` references `wiki_init`**
- **Found during:** Task 3 (red-then-green sanity setup)
- **Issue:** `docs/cancellation.md:204` referenced the old MCP tool name `wiki_init`. Phase 18 plan 18-04 (active-source sweep) and 18-05 (historical `.planning/` sweep) both missed `docs/`. CHECK 2's scope includes `docs/`, so without this fix CHECK 2 would have failed on the green baseline.
- **Fix:** `wiki_init` → `wiki_bootstrap`.
- **Commit:** 97b0b44

**2. [Rule 1 - Missed-sweep bug] `.planning/intel/apis.json` + `files.json` reference `wiki_init`**
- **Found during:** Task 3 (red-then-green sanity setup)
- **Issue:** Research intel files (machine-generated artifacts from earlier planning phases) carried stale MCP API names. Same root cause as #1: 18-04/18-05 missed `.planning/intel/`.
- **Fix:** `wiki_init` → `wiki_bootstrap` in both files (API entry + exports list).
- **Commit:** 97b0b44

**3. [Rule 1 - Missed-sweep bug] `16-CONTEXT.md` + `17-CONTEXT.md` MCP surface listing**
- **Found during:** Task 3 (red-then-green sanity setup)
- **Issue:** Phase 16 (archived under v1.2-phases) and Phase 17 (still active) CONTEXT.md "Integration Points" sections both listed `(wiki_init/scan/ingest/query/lint/log)` as the MCP tool surface. Per Phase 18 D-03 (sweep all `.planning/`), these should have been updated.
- **Fix:** `wiki_init` → `wiki_bootstrap` in both files.
- **Commit:** 97b0b44

**Rationale for Rule-1 invocation:** Per the executor deviation rules, Rule 1 covers "outdated documentation / stale references created by prior plans" — these files would have caused CHECK 2 to fail GREEN baseline, blocking Phase 18 from completing. Fixing them in this commit is correct over (a) deferring them (would prevent the gate from going green) or (b) allowlisting them (would broaden exemptions beyond the plan's "narrow" spirit).

### Plan Adherence

- **Task 1 acceptance criteria:** all 9 assertions pass.
- **Task 2 acceptance criteria:** all 5 assertions pass.
- **Task 3 acceptance criteria:** red-then-green observed for both CHECK 2 and CHECK 3; no residue in working tree. Final `bash scripts/check-brand.sh` exit 0 assertion deferred to post-Phase-21 (lattice CHECK 1 still pre-failing — explicitly flagged by orchestrator parallel_execution as out-of-scope).
- **Task 4 acceptance criteria:** all 9 assertions pass — file moved, R100 rename, allowlist routed correctly, single commit, body identical.

## Threat Model Compliance

| Threat ID | Mitigation evidence |
|---|---|
| T-18-18 (over-broad allowlist) | Two path-fragment entries only; both have `# rationale:` comments; no parent-directory wildcards (`grep -cE '^\.planning/phases/$\|^\.planning/todos/$' .brand-grep-allow` = 0). |
| T-18-19 (false positives) | Word-boundary regexes (`\b`) prevent `wiki_bootstrap` / `init_vault` from matching. Red-then-green sanity proves CHECK 2/3 tight enough for green baseline (modulo the lattice CHECK 1 out-of-scope). |
| T-18-20 (folded todo body edited) | `git log --name-status` shows `R100` — `similarity index 100%`. Body byte-identical. |
| T-18-21 (no audit trail) | Brand-gate failure messages name the specific files via `grep -rEl` output (CHECK 2) and `grep -nE` with line number (CHECK 3). |
| T-18-22 (--no-verify bypass) | Out of scope per plan; not actionable in this commit. |

## Files Created / Modified

**Created:**
- `.planning/todos/resolved/2026-05-19-rename-graph-wiki-init-command-to-init-wiki.md` (via `git mv` R100)
- `.planning/phases/18-plugin-command-rename/18-06-SUMMARY.md` (this file)

**Modified:**
- `scripts/check-brand.sh` (+30 lines, -2 lines net: CHECK 2 + CHECK 3 + updated OK message)
- `.brand-grep-allow` (+10 lines: Phase 18 section appended)
- `docs/cancellation.md` (1 line: Rule 1 — wiki_init → wiki_bootstrap)
- `.planning/intel/apis.json` (2 lines: Rule 1 — MCP entry renamed)
- `.planning/intel/files.json` (1 line: Rule 1 — exports list)
- `.planning/milestones/v1.2-phases/16-carry-forward-debt-cleanup/16-CONTEXT.md` (1 line: Rule 1)
- `.planning/phases/17-vault-io-bug-fixes/17-CONTEXT.md` (1 line: Rule 1)

**Renamed via git mv (R100):**
- `.planning/todos/pending/...init-wiki.md` → `.planning/todos/resolved/...init-wiki.md`

## Commit

`97b0b44` — chore(18-06): extend brand-gate to enforce /graph-wiki:bootstrap rename; fold todo

## Phase 18 Closure

All three Phase 18 success criteria (per 18-CONTEXT.md D-07):

- **SC#1:** `plugins/graph-wiki/commands/init.md` non-existent + `bootstrap.md` exists — satisfied by plan 18-01.
- **SC#2 (bootstrap surface):** zero hits of `graph-wiki:init\b`, `\bwiki_init\b`, `def init\b` in cli.py across active-source scope — satisfied by plans 18-01..18-05 + this plan's Rule-1 missed-sweep fixes; enforced going forward by CHECK 2 + CHECK 3 added in this plan.
- **SC#3 (Claude Code native `/init` reachable):** manual smoke test deferred to verifier / UAT pass per plan.

Brand-gate-enforcement portion of CMD-03 closed.

## Self-Check: PASSED

Files verified to exist:
- `scripts/check-brand.sh` — FOUND (modified)
- `.brand-grep-allow` — FOUND (modified)
- `.planning/todos/resolved/2026-05-19-rename-graph-wiki-init-command-to-init-wiki.md` — FOUND (renamed in)
- `.planning/todos/pending/2026-05-19-rename-graph-wiki-init-command-to-init-wiki.md` — ABSENT (renamed out, expected)
- `.planning/phases/18-plugin-command-rename/18-06-SUMMARY.md` — FOUND (this file)

Commit verified:
- `97b0b44` — FOUND in `git log`
