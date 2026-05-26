---
plan_id: "34-05"
phase: 34
wave: 3
depends_on: ["34-01", "34-02", "34-03", "34-04"]
files_modified:
  - .planning/phases/34-brand-sweep/34-VERIFICATION.md
autonomous: true
requirements:
  - BRAND-01
  - BRAND-02
  - BRAND-03
  - BRAND-04
must_haves:
  truths:
    - "scripts/check-brand.sh exits 0 on the post-sweep tree (SC#4)"
    - "VERIFICATION.md captures the four SC checks in the order D-18 specifies"
    - "VERIFICATION.md contains the three manual SC#3 scenarios from D-14 (no automated test covers the deprecation path)"
    - "Every BRAND-01..BRAND-04 requirement has at least one verification step bound to it"
    - "Full graph-io pytest suite passes"
  goal_check: |
    bash scripts/check-brand.sh && \
    uv run --package graph-io pytest packages/graph-io -q && \
    test -f .planning/phases/34-brand-sweep/34-VERIFICATION.md && \
    grep -qF 'SC#1' .planning/phases/34-brand-sweep/34-VERIFICATION.md && \
    grep -qF 'SC#2' .planning/phases/34-brand-sweep/34-VERIFICATION.md && \
    grep -qF 'SC#3' .planning/phases/34-brand-sweep/34-VERIFICATION.md && \
    grep -qF 'SC#4' .planning/phases/34-brand-sweep/34-VERIFICATION.md
---

# Plan 34-05: Verification — gate + manual scenarios + VERIFICATION.md

<objective>
Wave-3 verification plan. Runs after the four sweep plans (34-01 prep + 34-02/03/04 edits) so the
tree is in its final state. Produces `34-VERIFICATION.md` capturing:

- The four SC checks from CONTEXT.md D-18 (in the order it specifies).
- The three manual SC#3 scenarios from D-14 (the deprecation-warning paths that have no
  automated test, by D-14's deliberate decision).
- A pass/fail journal entry the operator fills in by running the commands.

Also runs the BRAND-04 grep gate (SC#4) and the full graph-io pytest suite to confirm no
regressions before phase-verify can mark Phase 34 complete.
</objective>

<tasks>

<task id="34-05-T1">
<title>Write VERIFICATION.md with SC#1..SC#4 checks and the three manual SC#3 scenarios</title>
<read_first>
  - .planning/phases/34-brand-sweep/34-CONTEXT.md (D-14, D-18, §specifics — the exact verification commands)
  - .planning/phases/34-brand-sweep/34-RESEARCH.md (F-08 — allowlist semantics; F-09 — pre-flight notes)
  - .planning/ROADMAP.md (Phase 34 Success Criteria block — confirm SC literal text)
</read_first>
<action>
Create `.planning/phases/34-brand-sweep/34-VERIFICATION.md` with the following content. The file
captures the four success criteria, their automated commands, and the three manual env-var
scenarios. Use this exact body (operator fills in pass/fail later at phase-verify time):

```markdown
# Phase 34: Brand Sweep — Verification

**Status:** Pending operator execution
**Order:** Run sections in the order they appear (D-18).

## SC#1 — `cg --help` brand check (BRAND-02)

Goal: `cg --help` output contains "graph-wiki" and does NOT contain "lattice" in any
user-visible string.

```bash
uv run cg --help | grep -qF 'graph-wiki'                 # must exit 0
uv run cg --help | grep -ciF 'lattice'                   # must output 0
```

Result: [ ] PASS  [ ] FAIL  Notes: __________________________

## SC#2 — README.md brand check (BRAND-01)

Goal: first line is `# graph-io`; the hardcoded `~/.lattice/graph/code.db` path is gone.

```bash
test "$(head -1 packages/graph-io/README.md)" = '# graph-io'                 # must exit 0
! grep -qF '~/.lattice/graph/code.db' packages/graph-io/README.md            # must exit 0
grep -qF 'paths.graph_dir(workspace)' packages/graph-io/README.md            # must exit 0 (per D-03)
```

Result: [ ] PASS  [ ] FAIL  Notes: __________________________

## SC#3 — Env var deprecation contract (BRAND-03)

**MANUAL** — three scenarios per D-14. There is no automated test for the deprecation paths;
this section is the only verification of D-07 and D-08 behavior.

Pre-flight: `unset LATTICE_GRAPH_LOCK_TIMEOUT_MS GRAPH_WIKI_LOCK_TIMEOUT_MS`. Stand inside a
small git repo with a code.db (or use any repo where `cg update` is a valid no-op).

### Scenario A: only the deprecated var is set

```bash
unset GRAPH_WIKI_LOCK_TIMEOUT_MS
LATTICE_GRAPH_LOCK_TIMEOUT_MS=5000 cg update 2>&1 | tee /tmp/sc3a.txt
```

Expect on stderr (capture from `/tmp/sc3a.txt`):
- Contains the substring `LATTICE_GRAPH_LOCK_TIMEOUT_MS is deprecated`
- Contains the substring `GRAPH_WIKI_LOCK_TIMEOUT_MS`
- Contains the substring `value=5000`
- `cg update` completes (exit 0 or any non-error exit; the warning does not abort the run)

Result: [ ] PASS  [ ] FAIL  Notes: __________________________

### Scenario B: both env vars set — new wins, old ignored

```bash
LATTICE_GRAPH_LOCK_TIMEOUT_MS=5000 GRAPH_WIKI_LOCK_TIMEOUT_MS=2000 cg update 2>&1 | tee /tmp/sc3b.txt
```

Expect on stderr (capture from `/tmp/sc3b.txt`):
- Contains the substring `deprecated and ignored`
- Contains the substring `using GRAPH_WIKI_LOCK_TIMEOUT_MS=2000`

Result: [ ] PASS  [ ] FAIL  Notes: __________________________

### Scenario C: only the new env var set — silent acceptance

```bash
unset LATTICE_GRAPH_LOCK_TIMEOUT_MS
GRAPH_WIKI_LOCK_TIMEOUT_MS=5000 cg update 2>&1 | tee /tmp/sc3c.txt
```

Expect on stderr (capture from `/tmp/sc3c.txt`):
- Does NOT contain the substring `deprecated`
- Does NOT contain the substring `warning:`
- `cg update` completes normally

Result: [ ] PASS  [ ] FAIL  Notes: __________________________

## SC#4 — Brand grep gate + allowlist content (BRAND-04)

Goal: `scripts/check-brand.sh` exits 0; the deprecated env var alias is covered by an entry
in `.brand-grep-allow`.

```bash
bash scripts/check-brand.sh                                                  # must exit 0
test -f .brand-grep-allow                                                    # must exit 0
grep -qF 'packages/graph-io/src/graph_io/update.py' .brand-grep-allow        # must exit 0 (env-var carve-out)
grep -qF 'packages/graph-io/src/graph_io/packages.py' .brand-grep-allow      # must exit 0 (_SKIP_REPO_PREFIXES carve-out)
grep -qF 'packages/graph-io/tests/test_packages.py' .brand-grep-allow        # must exit 0 (test_refresh_skips_lattice_dir_manifests carve-out)
```

**Note on allowlist form (RESEARCH F-08):** entries are file-path substrings (matched against
`grep -rEl` output), not content substrings. The roadmap SC text uses
`LATTICE_GRAPH_LOCK_TIMEOUT_MS in update.py is covered by a .brand-grep-allow entry` — that
coverage is satisfied by the `packages/graph-io/src/graph_io/update.py` path entry above; the
literal env-var string itself does not appear in the allowlist file.

Result: [ ] PASS  [ ] FAIL  Notes: __________________________

## Regression check — full graph-io test suite

```bash
uv run --package graph-io pytest packages/graph-io -q                        # must exit 0
```

Result: [ ] PASS  [ ] FAIL  Notes: __________________________

## Sign-off

When all six sections above are PASS, mark Phase 34 ready for phase-verify. The three SC#3
scenarios are the only operator-driven steps; the rest are runnable in a single shell session.
```

Do NOT inline pass/fail markers — leave them blank (`[ ]`) for the operator to fill at verify
time. Do NOT add extra scenarios; D-14 lists exactly three.
</action>
<acceptance_criteria>
  - File exists: `test -f .planning/phases/34-brand-sweep/34-VERIFICATION.md`
  - Contains all four SC headers (one per SC):
    - `grep -qE '^## SC#1' .planning/phases/34-brand-sweep/34-VERIFICATION.md`
    - `grep -qE '^## SC#2' .planning/phases/34-brand-sweep/34-VERIFICATION.md`
    - `grep -qE '^## SC#3' .planning/phases/34-brand-sweep/34-VERIFICATION.md`
    - `grep -qE '^## SC#4' .planning/phases/34-brand-sweep/34-VERIFICATION.md`
  - Contains all three SC#3 scenarios:
    - `grep -qF 'Scenario A: only the deprecated var is set' .planning/phases/34-brand-sweep/34-VERIFICATION.md`
    - `grep -qF 'Scenario B: both env vars set' .planning/phases/34-brand-sweep/34-VERIFICATION.md`
    - `grep -qF 'Scenario C: only the new env var set' .planning/phases/34-brand-sweep/34-VERIFICATION.md`
  - Contains the regression-check section: `grep -qF 'uv run --package graph-io pytest' .planning/phases/34-brand-sweep/34-VERIFICATION.md`
</acceptance_criteria>
</task>

<task id="34-05-T2">
<title>Run the BRAND-04 grep gate + full test suite + assert post-sweep cleanliness</title>
<read_first>
  - .brand-grep-allow (final post-sweep state; created by Plan 34-01)
  - scripts/check-brand.sh (read once to confirm the invocation contract)
  - .planning/phases/34-brand-sweep/34-VERIFICATION.md (the SC checks just written by T1)
</read_first>
<action>
Run the following commands in order and capture exit codes. This task is the automated portion
of verification (SC#1, SC#2, SC#4 + regression). SC#3 stays manual per D-14 and is handled by
the operator using VERIFICATION.md at phase-verify time — DO NOT attempt to automate SC#3.

```bash
# SC#1
uv run cg --help | grep -qF 'graph-wiki'
uv run cg --help | grep -ciF 'lattice'  # must report 0

# SC#2
test "$(head -1 packages/graph-io/README.md)" = '# graph-io'
! grep -qF '~/.lattice/graph/code.db' packages/graph-io/README.md
grep -qF 'paths.graph_dir(workspace)' packages/graph-io/README.md

# SC#4
bash scripts/check-brand.sh
grep -qF 'packages/graph-io/src/graph_io/update.py' .brand-grep-allow
grep -qF 'packages/graph-io/src/graph_io/packages.py' .brand-grep-allow
grep -qF 'packages/graph-io/tests/test_packages.py' .brand-grep-allow

# Regression
uv run --package graph-io pytest packages/graph-io -q
```

If any of these commands exits non-zero (or the lattice-count check is non-zero), STOP and
report the failure — the phase cannot ship. If all pass, this task succeeds and the operator
takes over for the three manual SC#3 scenarios.
</action>
<acceptance_criteria>
  - `uv run cg --help 2>&1 | grep -qF 'graph-wiki'` exits 0
  - `uv run cg --help 2>&1 | grep -ciF 'lattice'` outputs `0`
  - `head -1 packages/graph-io/README.md` outputs exactly `# graph-io`
  - `! grep -qF '~/.lattice/graph/code.db' packages/graph-io/README.md` exits 0
  - `grep -qF 'paths.graph_dir(workspace)' packages/graph-io/README.md` exits 0
  - `bash scripts/check-brand.sh` exits 0 (no unallowlisted hits across `packages/`, `agents/`, `plugins/`, `.planning/`, `CLAUDE.md`)
  - All three allowlist entries are present (three separate `grep -qF` checks per the action block)
  - `uv run --package graph-io pytest packages/graph-io -q` exits 0
</acceptance_criteria>
</task>

</tasks>

<verification>
This plan IS the verification plan; success means:

1. `.planning/phases/34-brand-sweep/34-VERIFICATION.md` exists and is fully populated with the
   four SC sections, the three manual SC#3 scenarios from D-14, and the regression-check
   section.
2. The full automated check from T2 passes: `cg --help` is rebranded; README is rebranded;
   `bash scripts/check-brand.sh` exits 0; the full pytest suite passes.
3. The three SC#3 manual scenarios are pending operator execution at phase-verify time. They
   are NOT attempted here (D-14 explicitly skips automated coverage of the deprecation path).

After this plan completes, Phase 34 is in the "ready for /gsd:verify-phase 34" state.
</verification>
