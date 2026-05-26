---
plan_id: "34-01"
phase: 34
wave: 1
depends_on: []
files_modified:
  - .brand-grep-allow
autonomous: true
requirements:
  - BRAND-04
must_haves:
  truths:
    - ".brand-grep-allow exists at repo root with exactly the 3 path-substring entries from RESEARCH F-08"
    - "bash scripts/check-brand.sh exit code is no longer 2 (the 'allowlist missing' state)"
    - "Allowlist entries are file-path substrings (per RESEARCH F-08), not content substrings"
    - "D-15: entry for the deprecated LATTICE_GRAPH_LOCK_TIMEOUT_MS alias is added (covers update.py via path substring)"
    - "D-16: entry for the _SKIP_REPO_PREFIXES functional carve-out is added (covers packages.py via path substring)"
    - "D-17: scripts/check-brand.sh is NOT modified (the script is already well-tested across CR-01 and WR-03)"
  goal_check: |
    test -f .brand-grep-allow && \
    grep -q '^packages/graph-io/src/graph_io/update.py$' .brand-grep-allow && \
    grep -q '^packages/graph-io/src/graph_io/packages.py$' .brand-grep-allow && \
    grep -q '^packages/graph-io/tests/test_packages.py$' .brand-grep-allow
---

# Plan 34-01: Create `.brand-grep-allow` (prep)

<objective>
Create the `.brand-grep-allow` file at repo root with three path-substring entries that cover the
functional carve-outs Phase 34 introduces. This plan runs FIRST (Wave 1) so the BRAND-04 grep gate
does not fail mid-sweep when Waves 2 / 3 trigger any post-edit checks.

CONTEXT.md D-15: and D-16: specified the entries; RESEARCH.md F-01 + F-08 corrected the form
(file-path substrings only — `check-brand.sh` allowlists paths, not content). Per D-17: this
plan does NOT modify `scripts/check-brand.sh`; the script is already well-tested and Phase 34
only contributes allowlist entries.
</objective>

<tasks>

<task id="34-01-T1">
<title>Create .brand-grep-allow with exactly three path-substring entries</title>
<read_first>
  - scripts/check-brand.sh (verify the `grep -vF -f` invocation semantics — entries are matched against file paths, not content)
  - .planning/phases/34-brand-sweep/34-RESEARCH.md (F-01, F-08 — allowlist contract + final content)
  - .planning/phases/34-brand-sweep/34-CONTEXT.md (D-15: new env-var alias entry; D-16: packages.py functional-carve-out entry; D-17: do NOT modify check-brand.sh)
</read_first>
<action>
Write a new file at `.brand-grep-allow` (repo root, not inside any package) containing exactly the
following lines, in this order, with `#` comments and one blank line between groups:

```
# Phase 34 BRAND-03: deprecated env var alias kept for one-milestone backward compat (D-10, D-15)
packages/graph-io/src/graph_io/update.py

# BRAND-04 carve-out: functional _SKIP_REPO_PREFIXES filter (per PITFALLS.md, D-16)
packages/graph-io/src/graph_io/packages.py

# BRAND-04 carve-out: functional test of the lattice/ skip filter (D-12)
packages/graph-io/tests/test_packages.py
```

Do NOT edit `scripts/check-brand.sh` (per D-17: the script is already well-tested across CR-01
and WR-03; Phase 34 contributes only the allowlist). Do NOT add any other entries — only the
three above (the env-var alias entry per D-15:, the packages.py functional-carve-out per D-16:,
and the test_packages.py carve-out introduced by RESEARCH F-06).
File ends with a trailing newline.
</action>
<acceptance_criteria>
  - File exists: `test -f .brand-grep-allow`
  - Contains the three path entries (exact match, anchored regex):
    - `grep -qE '^packages/graph-io/src/graph_io/update\.py$' .brand-grep-allow`
    - `grep -qE '^packages/graph-io/src/graph_io/packages\.py$' .brand-grep-allow`
    - `grep -qE '^packages/graph-io/tests/test_packages\.py$' .brand-grep-allow`
  - Contains all three comment headers (exit 0): `grep -q 'Phase 34 BRAND-03' .brand-grep-allow && grep -q 'BRAND-04 carve-out' .brand-grep-allow`
  - `scripts/check-brand.sh` was NOT modified: `git diff --name-only scripts/check-brand.sh | wc -l` outputs `0`
  - Running `bash scripts/check-brand.sh` does NOT print `BRAND-04 FAIL: .brand-grep-allow not found at repo root` (it may still fail with non-zero exit for unrelated hits at this stage — that is expected and resolved by Waves 2-3)
</acceptance_criteria>
</task>

</tasks>

<verification>
After this plan completes, the post-condition is:
- `.brand-grep-allow` exists with three path-substring entries covering Phase 34's intentional carve-outs.
- `bash scripts/check-brand.sh` no longer exits with code 2 ("allowlist missing"); it will likely
  still exit non-zero because Waves 2-3 haven't run yet, but the gate is now *runnable*.
- Subsequent plans can safely run the gate between their edits without false-positive failures
  caused by the missing-allowlist condition.

No tests run for this plan. The allowlist file is verified by the acceptance criteria above.
</verification>
