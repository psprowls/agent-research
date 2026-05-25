---
phase: 21-rename-code-wiki-agent-to-graph-wiki-agent-update-all-code-r
plan: 05
subsystem: planning-docs + brand-gate
tags: [rename, refactor, rebrand, planning-doc-sweep, brand-grep-gate-extension, phase-final-gate]
requires:
  - 21-04 (cross-package + env vars + trace-dir rebrand; whole-repo pytest -m "not integration" green)
provides:
  - .planning/ historical sweep complete (D-05 override of R-03) — STATE/ROADMAP/REQUIREMENTS/PROJECT/RETROSPECTIVE/MILESTONES + 17/20 phase docs + threads + v1.0/v1.1/v1.2 milestone archives + sketches/ + sweep/ + research/ + spike READMEs+MANIFEST+CONVENTIONS+WRAP-UP
  - .claude/skills/spike-findings-agent-research/{SKILL.md,references/**} swept (D-07 active-refs inclusion)
  - repo + plugin docs swept (README.md, CLAUDE.md, plugins/graph-wiki/{README,CLAUDE}.md, skills/graph-wiki/README.md, .claude-plugin/plugin.json)
  - scripts/check-brand.sh extended with code-wiki-agent / code_wiki_agent / code-wiki-mcp / code_wiki_mcp regex (D-12 single-gate extension)
  - .brand-grep-allow Phase 21 section authored with three sub-categories (renamed-path mirrors + Phase-21 carve-outs + pre-existing-lattice narrow allowlists); every entry SP-6-compliant
  - SP-2 two-stage final gate green: GATE_RC=0 + TEST_RC=0 (583 passed, 32 skipped)
  - Phase 21 goal SC#5 satisfied — full-repo grep for the four code-wiki-* slugs returns zero unallowlisted hits
affects:
  - .planning/ (188 files swept across Tasks 1+2+3; 175+ updated, balance had zero hits)
  - .claude/skills/spike-findings-agent-research/ (SKILL.md + 1 active reference)
  - README.md, CLAUDE.md, plugins/graph-wiki/** (docs)
  - scripts/check-brand.sh, .brand-grep-allow
tech-stack:
  added: []
  patterns:
    - "Read-once-then-sed sweep with `while IFS= read -r f; do sed -i ''` (mirrors 21-04 Task 3 pattern; handles spaces/newlines in paths)"
    - "Six-pattern atomic sed: code-wiki-agent / code-wiki-mcp / code_wiki_agent / code_wiki_mcp / CODE_WIKI_ / .code-wiki/ → graph-* equivalents"
    - "Phase-21 allowlist additions stratified into three sub-categories (mirror-of-stale / Phase-21-specific / pre-existing-lattice-narrow) with per-entry `# rationale:` comments (SP-6)"
    - "SP-1 PIPESTATUS pytest gate after each Tasks 1-3 sub-commit (non-integration only); SP-2 two-stage final gate (full pytest) in Task 4"
key-files:
  created:
    - .planning/phases/21-.../21-05-SUMMARY.md
  modified:
    - "14 files in Task 1 (live planning + repo+plugin docs + spike-findings skill) — commit 9610ef0"
    - "21 files in Task 2 (Phase 17 + Phase 20 phase docs + threads) — commit 8e20dd9"
    - "172 files in Task 3 (historical archives v1.0/v1.1/v1.2 + sketches *.md + sweep + research + spike READMEs+meta) — commit ee40a15"
    - "2 files in Task 4 (scripts/check-brand.sh, .brand-grep-allow) — commit 161a1cd"
decisions:
  - "Task 3 D-07-analog discretion: `.planning/sketches/00{1,2,3}/index.html` excluded from the sed sweep (plan scope was `.planning/sketches/**/*.md`, html files are static design mockups quoting `agents/code-wiki-agent` paths verbatim as rendered `/graph-wiki:refresh` output examples). Same class as 21-04's D-07-analog call for `.claude/skills/sketch-findings-agent-research/sources/`. Both directly allowlisted in Task 4."
  - "Task 4 Karpathy-§3 (Surgical Changes) call: stale Phase 12 allowlist entries (lines 125/173/175 of .brand-grep-allow, pointing to old `agents/code-wiki-agent/...` paths that no longer exist) left UNTOUCHED per M4 discipline. Equivalent renamed-path entries (`agents/graph-wiki-agent/...`) added to the Phase 21 section under sub-category (a) — same surface, dual coverage."
  - "Task 4 Rule-3 (Blocking) fix: `scripts/check-brand.sh` line 69 referenced the stale CLI path `agents/code-wiki-agent/src/code_wiki_agent/cli.py` — this is CHECK 3's regression guard against `def init(` reintroduction. The file no longer exists at that path, so the guard had silently become a no-op. Surgically updated to `agents/graph-wiki-agent/src/graph_wiki_agent/cli.py` so CHECK 3 stays effective. This is Phase 21's own brand-gate script, missed by 21-04's cross-package sweep because B1's `--exclude-dir=graph-wiki` excluded the wiki dir but the gate's own path lookups were never touched by sed-style rebrands."
  - "Task 4 sub-category (c): added narrow allowlists for pre-existing lattice surface that would have failed even before the Phase 21 rename — `.planning/milestones/v1.2-` (REQUIREMENTS/ROADMAP/v1.2-phases/**), `.planning/phases/17-`, `.planning/phases/20-`, plus two test files (`packages/eval-harness/tests/test_scanner_regression.py`, `packages/wiki-io/tests/test_scan_companion_fold.py`). These are pre-existing `lattice` / `lattice-curator-core` references in the same R-03/Provenance class as existing Phase 12 entries; R-03 only listed `v1.0-` / `v1.1-` archive prefixes so v1.2 + Phase 17/20 + the two test files were never covered. Narrow path-fragment entries per the prompt guidance: 'EXCLUDE only via narrow allowlist entries — don't broaden to mask unrelated regressions.' Documented as out-of-scope for Phase 21."
metrics:
  duration_min: ~20
  completed: 2026-05-19
---

# Phase 21 Plan 05: Final Layer — Planning Sweep + Brand-Gate Extension Summary

D-09 layer 5 (final). Four atomic sub-commits closing out the 188-file `.planning/`
historical sweep (D-05 override of R-03), the live repo/plugin doc sweep, the
spike-findings skill sweep (D-07 inclusion), the `scripts/check-brand.sh`
regex extension (D-12 single-gate), the `.brand-grep-allow` Phase 21 section
(D-13 tight allowlist with SP-6 `# rationale:` per entry), and the SP-2
two-stage final gate (GATE_RC=0 + TEST_RC=0).

## Four Sub-commits

| # | Hash | Subject | Files | Insertions/Deletions |
|---|------|---------|-------|----------------------|
| 1 | `9610ef0` | docs(21): rebrand code-wiki-agent in live planning + repo/plugin docs + skill | 14 | 99 / 99 |
| 2 | `8e20dd9` | docs(21): rebrand code-wiki-agent in current-milestone phase docs | 21 | 323 / 323 |
| 3 | `ee40a15` | docs(21): rebrand code-wiki-agent in historical archives (D-05 override of R-03) | 172 | 2694 / 2694 |
| 4 | `161a1cd` | chore(21): extend brand grep-gate for code-wiki-agent → graph-wiki-agent | 2 | 84 / 3 |

All four landed on branch `worktree-agent-a0c6c04b5b14cf237`. Total: 209 files
across the four commits (count of unique paths; some files touched only once).

## Surgical-Changes Verification (per commit)

### Commit 1 — `9610ef0` (Task 1)

```
$ git show --stat 9610ef0 --format=
 .claude/skills/spike-findings-agent-research/SKILL.md                  |  2 +-
 .claude/skills/spike-findings-agent-research/references/subagent-context-injection.md |  6 ++--
 .planning/MILESTONES.md                                             |  4 +-
 .planning/PROJECT.md                                                | 26 +++++++--------
 .planning/REQUIREMENTS.md                                           |  8 ++---
 .planning/RETROSPECTIVE.md                                          |  2 +-
 .planning/ROADMAP.md                                                | 14 ++++----
 .planning/STATE.md                                                  | 14 ++++----
 CLAUDE.md                                                           | 12 +++----
 README.md                                                           |  6 ++--
 plugins/graph-wiki/.claude-plugin/plugin.json                       |  4 +-
 plugins/graph-wiki/CLAUDE.md                                        |  8 ++---
 plugins/graph-wiki/README.md                                        |  8 ++---
 plugins/graph-wiki/skills/graph-wiki/README.md                      |  2 +-
 14 files changed, 99 insertions(+), 99 deletions(-)
```

Touches exactly the 14 files listed in plan Task 1 `<files>`. No `.planning/`
leakage outside the top-level docs; no spike-source / wiki-content leakage.

### Commit 2 — `8e20dd9` (Task 2)

```
$ git show --stat 8e20dd9 --format= | tail -5
 .../20-CONTEXT.md                                  |  18 +-
 .../20-PLAN-CHECK-RESPONSE.md                      |   4 +-
 .../20-VERIFICATION.md                             |  74 ++++----
 .planning/threads/next-milestone-planning.md       |  18 +-
 21 files changed, 323 insertions(+), 323 deletions(-)
```

Touches Phase 17 dir (9 files) + Phase 20 dir (11 files) + threads (1 file) =
21. **Zero leakage into the Phase 21 own dir** (verified via `git show --stat
HEAD --format= | grep '.planning/phases/21-'` → no output). `.planning/intel/
stack.json` was in plan scope but had zero hits at scope-grep time, so not
touched.

### Commit 3 — `ee40a15` (Task 3)

```
$ git show --stat ee40a15 --format= | tail -5
 .planning/spikes/MANIFEST.md                       |   2 +-
 .planning/sweep/STORY.md                           |   8 +-
 172 files changed, 2694 insertions(+), 2694 deletions(-)
```

Touches 172 `.md` files across `.planning/milestones/v1.0-*`, `.planning/
milestones/v1.1-phases/**`, `.planning/milestones/v1.2-phases/**`,
`.planning/sketches/**/*.md`, `.planning/sweep/`, `.planning/research/`,
`.planning/spikes/{MANIFEST,CONVENTIONS,WRAP-UP-SUMMARY}.md`, and
`.planning/spikes/00{1,2}/README.md`.

**D-07 enforcement verified:** `git show --stat HEAD --format= | grep -E
'.planning/spikes/00[12].*/sources/'` → no output. Raw spike sources at
`.planning/spikes/001-subagent-context-audit/sources/` and `.planning/
spikes/002-lattice-drift-inventory/sources/` are untouched.

**D-07-analog discretion verified:** `git show --stat HEAD --format= | grep
'\.html$'` → no output. The three `.planning/sketches/00{1,2,3}/index.html`
files are untouched (plan scope was `*.md`; html files are static sketch
mockups, allowlisted in Task 4).

### Commit 4 — `161a1cd` (Task 4)

```
$ git show --stat 161a1cd --format=
 .brand-grep-allow      | 78 ++++++++++++++++++++++++++++++++++++++++++++++++++
 scripts/check-brand.sh |  9 ++++--
 2 files changed, 84 insertions(+), 3 deletions(-)
```

Touches exactly the 2 files listed in plan Task 4 `<files>`. M4 deletion-guard
verified: `git diff HEAD~1 HEAD -- .brand-grep-allow | grep -E '^-[^-]' |
grep -v 'Phase 21'` → no output. No pre-existing Phase 12 lines were
modified or deleted.

## Final SP-2 Two-Stage Gate Output

```
$ bash scripts/check-brand.sh
BRAND-04 OK: zero unallowlisted hits (BRAND-04 lattice + BRAND-CMD graph-wiki:init|wiki_init + BRAND-CMD-CLI def init( all clean)
$ echo $?
0   # GATE_RC=0

$ uv run pytest 2>&1 | tail -3
--------------------------- snapshot report summary ----------------------------
19 snapshots passed.
================== 583 passed, 32 skipped in 76.36s (0:01:16) ==================
# PYTEST_RC=0 (via PIPESTATUS, GATE_RC=0 + TEST_RC=0)
```

**Both stages green: GATE_RC=0 + TEST_RC=0.** 583 passed (up from 21-04's
582 because the pytest run was the FULL suite, not `-m "not integration"`,
adding `tests/test_integration_gate.py`'s meta-test which now passes against
the renamed `agents/graph-wiki-agent/tests/integration/` files).

## Final-Residual Grep (proves zero unallowlisted hits)

```
$ grep -rE 'code-wiki-agent|code_wiki_agent|code-wiki-mcp|code_wiki_mcp' \
    packages/ agents/ plugins/ .planning/ CLAUDE.md README.md 2>/dev/null \
    | grep -vF -f <(grep -vE '^[[:space:]]*(#|$)' .brand-grep-allow)
(zero output)
```

Phase 21 goal SC#5 satisfied.

## Phase 21 Allowlist Section (inline, for audit)

Three sub-categories, every entry SP-6-compliant (`# rationale:` per line):

```
# Phase 21 — `code-wiki-agent` rename to `graph-wiki-agent`. Per D-13, the
# allowlist stays tight: only entries that would actively break things if
# rewritten. Most historical references are eliminated by the .planning/
# sweep (D-05 override of R-03), not allowlisted. Two categories:
#  (a) renamed-path mirrors of stale Phase 12 entries (...);
#  (b) Phase 21-specific carry-forward classes (D-06 OOS wiki content,
#      D-07 raw spike sources, Phase 21 self-allowlist, D-07-analog sketch
#      mockups, runtime artifact dirs).
#  (c) Pre-existing lattice surface in v1.2 milestones archive + Phase
#      17/20 docs + a couple of test files — narrow allowlists per the
#      prompt guidance "EXCLUDE only via narrow allowlist entries — don't
#      broaden to mask unrelated regressions". (...)

# (a) Renamed-path mirrors of stale Phase 12 allowlist entries
agents/graph-wiki-agent/src/graph_wiki_agent/commands/query.py
agents/graph-wiki-agent/tests/commands/test_lint_parity.py
agents/graph-wiki-agent/tests/prompts/test_provenance.py

# (b) Phase 21-specific carry-forward classes.
graph-wiki/wiki/
.planning/spikes/001-subagent-context-audit/sources/
.planning/spikes/002-lattice-drift-inventory/sources/
.planning/phases/21-rename-code-wiki-agent-to-graph-wiki-agent-update-all-code-r/
.claude/skills/sketch-findings-agent-research/sources/
.planning/sketches/001-refresh-sweep-output/index.html
.planning/sketches/002-refresh-result-block/index.html
.planning/sketches/003-refresh-diff-doc/index.html
.planning/intel/files.json
.planning/intel/deps.json
.planning/intel/apis.json
.planning/intel/arch.md
agents/graph-wiki-agent/test-out/

# (c) Pre-existing lattice surface uncovered by R-03 — narrow allowlists.
.planning/milestones/v1.2-REQUIREMENTS.md
.planning/milestones/v1.2-ROADMAP.md
.planning/milestones/v1.2-phases/11-workspace-io-port-m1/
.planning/milestones/v1.2-phases/12-drift-backport-ecosystem-rebrand-m2/
.planning/milestones/v1.2-phases/13-plugin-spec-m3a/
.planning/milestones/v1.2-phases/14-plugin-port-m3b/
.planning/milestones/v1.2-phases/15-wiki-self-update/
.planning/milestones/v1.2-phases/16-carry-forward-debt-cleanup/
.planning/phases/17-wiki-io-bug-fixes/
.planning/phases/20-workspace-manifest-model-config/
packages/wiki-io/tests/test_scan_companion_fold.py
packages/eval-harness/tests/test_scanner_regression.py
```

## Discretion Notes

### Phase 21 own dir allowlisted vs. swept

The Phase 21 phase dir `.planning/phases/21-rename-code-wiki-agent-to-graph-
wiki-agent-update-all-code-r/` is **allowlisted, not swept**. Mirrors Phase
12's self-allowlist pattern (`.brand-grep-allow` line 75). Rationale: this
dir documents the rename itself and naturally references both `code-wiki-
agent` and `graph-wiki-agent` side-by-side in CONTEXT, PATTERNS, PLAN,
SUMMARY, DISCUSSION-LOG, and per-task PLAN/SUMMARY files. Rewriting it
would erase the historical record of what was renamed.

### Spike sources NOT swept (D-07)

`.planning/spikes/001-subagent-context-audit/sources/` and `.planning/spikes/
002-lattice-drift-inventory/sources/` are untouched. Per D-07: raw spike
material captured at spike-time, kept verbatim as historical evidence.

### Phase 12 lattice allowlist entries UNTOUCHED

The 212-line `.brand-grep-allow` file's first 213 lines (Phase 12 R-01 / R-02
/ R-03 / R-04 + plan-03 carry-forward + Phase 11/13/14/18 self-allowlists)
are byte-identical to pre-Phase-21 state. Phase 21 ADDS lines 213-292 (Phase
21 section); zero lines were modified or deleted from earlier sections. M4
deletion-guard run after Task 4 commit returned zero output.

### D-07-analog sketch mockup exclusions

Two analog classes were treated the same way as D-07 spike sources:

- `.claude/skills/sketch-findings-agent-research/sources/*/index.html` — per
  21-04 SUMMARY's forward pointer. Historical HTML snapshots that quote
  prior commit messages containing `CODE_WIKI_CONFIG`.
- `.planning/sketches/00{1,2,3}/index.html` — Plan 21-05 Task 3 discretion.
  Static sketch mockups quoting `agents/code-wiki-agent` paths verbatim as
  rendered `/graph-wiki:refresh` output examples. Plan scope was `*.md`.

Both directly allowlisted in the Phase 21 section under sub-category (b).

### Pre-existing lattice surface (sub-category c)

The brand gate's regex extension surfaced 75 pre-existing lattice hits in
files never covered by Phase 12's R-03 entries. Categories: v1.2 milestone
archive (R-03 only listed `v1.0-`/`v1.1-` prefixes; v1.2 was archived later
without an allowlist update), Phase 17 + 20 docs (post-R-03 phase work), and
two test files (`test_scan_companion_fold.py`, `test_scanner_regression.py`)
that reference upstream `lattice-curator-core` as Provenance.

Per the prompt guidance — "If the BRAND-04 check has pre-existing failures
that aren't from `code-wiki-agent` ... document them as out-of-scope and
EXCLUDE only via narrow allowlist entries — don't broaden to mask unrelated
regressions" — added 12 narrow allowlist entries (dir-paths and individual
files, not broad wildcards). All same R-03 / Provenance class as Phase 12.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 — Blocking] Fixed stale CLI path in `scripts/check-brand.sh` CHECK 3**

- **Found during:** Task 4 pre-edit Read of `scripts/check-brand.sh`.
- **Issue:** Line 69 used `agents/code-wiki-agent/src/code_wiki_agent/cli.py`
  as the grep target for CHECK 3 (regression guard against `def init(`
  reintroduction). After Phase 21 renamed the dir to `graph-wiki-agent`,
  the file no longer existed at the old path → `grep -n ... 2>/dev/null
  || true` returned empty → CHECK 3 silently became a no-op for any
  future regression. Pre-existed plan 21-05 (created by 21-01 dir rename;
  not caught by 21-02/03/04 sweeps because `check-brand.sh` is in Phase
  12's own self-allowlist and contains the `code-wiki-agent` brand string
  itself, so it would have been a false-positive target for the four-slug
  sed).
- **Fix:** Updated to `agents/graph-wiki-agent/src/graph_wiki_agent/cli.py`
  (2-line edit: the grep target + the FAIL message). Folded into the Task
  4 commit.
- **Verification:** `bash -n scripts/check-brand.sh` passes; `bash scripts/
  check-brand.sh` exits 0; the new path resolves (`ls agents/graph-wiki-
  agent/src/graph_wiki_agent/cli.py` → file exists).
- **Files modified:** `scripts/check-brand.sh`
- **Commit:** `161a1cd` (folded into Task 4 commit).

**2. [Rule 4 → Resolved-by-Discretion] Stale Phase 12 allowlist entries kept untouched; renamed-path equivalents added in Phase 21 section**

- **Found during:** Task 4 first gate run.
- **Issue:** Three Phase 12 allowlist entries (lines 125, 173, 175 of
  `.brand-grep-allow`) point to `agents/code-wiki-agent/...` paths that
  no longer exist after the Phase 21 dir rename. The same files now live
  at `agents/graph-wiki-agent/...` and their lattice/Provenance references
  re-surfaced as gate hits.
- **Rule 4 trigger consideration:** Architecturally, the cleanest fix would
  rewrite the Phase 12 lines to the new paths. But the plan's M4 deletion-
  guard check explicitly asserts no Phase 12 lines are deleted from this
  commit, and Karpathy §3 (Surgical Changes) says "Don't 'improve' adjacent
  code [...] If you notice unrelated dead code, mention it — don't delete
  it."
- **Resolution (Discretion):** Left the three Phase 12 lines UNTOUCHED; added
  three renamed-path mirror entries in the Phase 21 section sub-category (a),
  each with a `# rationale:` comment naming which Phase 12 line it mirrors
  and which R-class it inherits. Dual coverage; M4 happy; gate works. Future
  maintainer can collapse the duplicates in a separate cleanup commit.
- **Files modified:** `.brand-grep-allow` (Phase 21 section additions only)
- **Commit:** `161a1cd`

**3. [Rule 4 → Resolved-by-Discretion] Pre-existing lattice surface in v1.2 milestones / Phase 17 / Phase 20 / two test files allowlisted narrowly**

- **Found during:** Task 4 first gate run.
- **Issue:** 75 of 93 gate hits were pure `lattice` matches (no `code-wiki-*`),
  in files never covered by Phase 12's R-03 because R-03 listed only the
  `v1.0-` and `v1.1-` archive prefixes. The v1.2 milestone archive (created
  by Phase 16 when v1.2 was archived to `milestones/v1.2-phases/`), Phase
  17, Phase 20, and two test files (`test_scan_companion_fold.py`,
  `test_scanner_regression.py`) were never added to the allowlist.
- **Per prompt guidance:** "EXCLUDE only via narrow allowlist entries — don't
  broaden to mask unrelated regressions." Documented as out-of-scope for
  Phase 21.
- **Resolution:** Added 12 narrow allowlist entries (path-fragment per dir +
  per-file for the two test files) in Phase 21 section sub-category (c).
  Did NOT broaden to `.planning/milestones/` (which would also catch v1.0/
  v1.1 already-allowlisted entries — harmless but adds noise). Did NOT
  modify R-03's existing entries.
- **Files modified:** `.brand-grep-allow` (Phase 21 section additions only)
- **Commit:** `161a1cd`

### Skipped/Deferred Items

**1. `.planning/intel/{files,deps,apis}.json` + `arch.md` allowlisted, not swept**

- **Surface:** 4 files in `.planning/intel/` containing `code-wiki-agent` /
  `agents/code-wiki-agent/...` path references (auto-generated intel data
  with timestamps).
- **Rationale:** Plan 21-05 `<files>` listed `.planning/intel/stack.json`
  only (which had zero hits). The other 4 intel files are auto-generated
  by a `/graphify`-style intel-refresh pipeline outside the rename's
  immediate scope. Allowlisting (not sweeping) means the next intel-refresh
  run will heal the names organically.
- **Treatment:** 4 entries in Phase 21 section sub-category (b), with a
  `# rationale:` noting they're auto-generated.

**2. `.planning/sketches/00{1,2,3}/index.html` allowlisted, not swept (D-07-analog)**

- **Surface:** 3 static sketch html mockups, two of which contain literal
  `agents/code-wiki-agent` path references as rendered `/graph-wiki:refresh`
  output examples (`001-refresh-sweep-output/index.html`, `002-refresh-
  result-block/index.html`).
- **Rationale:** Plan scope was `.planning/sketches/**/*.md`, not `*.html`.
  Same class as 21-04's D-07-analog call for `.claude/skills/sketch-
  findings-agent-research/sources/*.html` (static design artifacts; rewriting
  corrupts them as historical mockups).
- **Treatment:** 3 entries in Phase 21 section sub-category (b), each
  with a `# rationale:` naming the D-07-analog discretion.

**3. `graph-wiki/wiki/` content untouched (D-06 OOS)**

- The wiki vault content is healed by next `/graph-wiki:scan` run.
- Verified zero leakage: `git show --stat <each-SHA> --format= | grep
  'graph-wiki/wiki/'` → no output for any of the 4 commits.

**4. `graph-wiki/{.graph-wiki.yaml,CLAUDE.md}` runtime drift unstaged**

- Same pattern as 21-04 SUMMARY §"Runtime workspace-io drift". `uv sync` in
  Task 1's gate stage produced editable-install workspace registration
  diffs in these files. Out of scope for this plan; left as unstaged.
- Operator can resolve out-of-band (or let workspace-io idempotently
  re-emit on next workspace boot).

## Auth Gates

None encountered. Pure local sed-style refactor + script edits.

## Known Stubs

None. Pure rename / brand-grep extension; no placeholder values introduced.

## Threat Flags

None.

## Phase 21 — Plan-by-Plan Completion (all 5 plans done)

| Plan | Status | SC# Satisfied | Hash(es) |
|------|--------|---------------|----------|
| 21-01 | done | SC#1 (dir rename, git history preserved) | (see 21-01-SUMMARY.md) |
| 21-02 | done | SC#3 partial (console scripts work post-rename) | (see 21-02-SUMMARY.md) |
| 21-03 | done | SC#2 (Python pkgs + imports + agent-pkg pytest green) | (see 21-03-SUMMARY.md) |
| 21-04 | done | SC#3 (whole-repo pytest -m "not integration" green) + SC#4 (plugin shellouts + .graph-wiki/ trace dir) | ef29545 / 4e92b20 / 7005600 / 05df828 |
| **21-05** | **done** | **SC#5 (brand-grep extended; allowlist updated; zero unallowlisted hits) + whole-repo full pytest green (583 passed)** | **9610ef0 / 8e20dd9 / ee40a15 / 161a1cd** |

Phase 21 is complete on branch `worktree-agent-a0c6c04b5b14cf237`. The
merge of this branch (or equivalent `rename-21` branch when surfaced to
the operator) into `main` is an operator-scoped decision per D-08, OUTSIDE
Phase 21's boundary.

## Pointer Forward — Phase 19 (next in v1.3 execution queue)

Per ROADMAP.md, Phase 19 (code review burndown) is next in the v1.3 execution
queue. Phase 19 was reordered to the end of v1.3 (commit 1472526) precisely
because it depends on Phase 21's rename being shipped — the code-review
burndown will reference module/symbol names that only stabilized after
Phase 21. Once Phase 21 merges (operator decision), Phase 19 unblocks.

## Self-Check: PASSED

```
$ for sha in 9610ef0 8e20dd9 ee40a15 161a1cd; do
    git log --oneline | grep -q "^$sha" && echo "FOUND: $sha" || echo "MISSING: $sha"
  done
FOUND: 9610ef0
FOUND: 8e20dd9
FOUND: ee40a15
FOUND: 161a1cd

$ [ -f .planning/phases/21-rename-code-wiki-agent-to-graph-wiki-agent-update-all-code-r/21-05-SUMMARY.md ] && echo FOUND
FOUND

$ bash scripts/check-brand.sh && echo "GATE OK"
BRAND-04 OK: zero unallowlisted hits (BRAND-04 lattice + BRAND-CMD graph-wiki:init|wiki_init + BRAND-CMD-CLI def init( all clean)
GATE OK
```

- All 4 commits present in `git log`.
- SUMMARY.md exists at the expected path.
- Brand gate exits 0 (GATE_RC=0).
- Full pytest exit 0 (583 passed, 32 skipped) — TEST_RC=0.
- Zero unallowlisted hits on the final-residual full-repo grep.
- No leakage into `.planning/spikes/00{1,2}/sources/` (D-07).
- No leakage into `graph-wiki/wiki/` (D-06).
- M4 deletion-guard: zero Phase 12 allowlist entries removed.
