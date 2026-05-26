---
phase: 36
slug: cg-find-parser-ergonomics
status: draft
nyquist_compliant: true
wave_0_complete: true
created: 2026-05-26
---

# Phase 36 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest 8.x (workspace-installed via `uv`) |
| **Config file** | `packages/graph-io/pyproject.toml` (`[tool.pytest.ini_options]`) |
| **Quick run command** | `uv run --package graph-io pytest packages/graph-io/tests/test_cli_smoke.py packages/graph-io/tests/test_cli_anti_regression.py -q` |
| **Full suite command** | `uv run --package graph-io pytest -q` |
| **Estimated runtime** | ~25-35 seconds full suite; ~5-8 seconds quick |

---

## Sampling Rate

- **After every task commit:** Run quick command (focused CLI tests for q_find changes)
- **After every plan wave:** Run full suite (catches cross-test regressions and any forgotten positional caller)
- **Before final commit:** Full suite must be green AND `git grep -n '\["find", "[^-]' packages/graph-io/tests/` must return zero hits (proves D-10 hard-cut is complete)
- **Max feedback latency:** 35 seconds

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Decision Refs | Expected Behavior | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|---------------|-------------------|-----------|-------------------|-------------|--------|
| 36-01-01 | 01 | 1 | CGFIND-01, CGFIND-02 | D-01..D-06, D-08 | `cg find --name X --kind Y --in-package Z` accepts named flags, AND-combines, errors on no filters, kind validated via argparse choices | unit + CLI | `uv run --package graph-io pytest packages/graph-io/tests/test_queries.py::test_find_in_package -q` | ✅ existing | ⬜ pending |
| 36-01-02 | 01 | 1 | CGFIND-02 | D-07, D-09 | `cg find --in-package zzz` exits 1 with zero rows; 50-row cap with truncation notice on stderr | unit + CLI | `uv run --package graph-io pytest packages/graph-io/tests/test_cli_smoke.py::test_find_in_package_unknown packages/graph-io/tests/test_cli_format.py::test_render_caps_at_50 -q` | ✅ existing | ⬜ pending |
| 36-01-03 | 01 | 1 | CGFIND-03 | D-10, D-11 | All positional `["find", "X"]` test sites migrated to `["find", "--name", "X"]`; new anti-regression asserts old form errors | CLI grep + pytest | `! git grep -nE '\["find", "[a-zA-Z]' packages/graph-io/tests/ && uv run --package graph-io pytest packages/graph-io/tests/test_cli_anti_regression.py::test_find_positional_form_errors -q` | ✅ existing | ⬜ pending |
| 36-01-04 | 01 | 1 | CGFIND-01, CGFIND-02, CGFIND-03 | All | Full test suite green after migration commit | pytest | `uv run --package graph-io pytest -q` | ✅ existing | ⬜ pending |

---

## Wave 0 Requirements

- [x] `packages/graph-io/tests/test_cli_smoke.py` — exists; add 6 new test functions
- [x] `packages/graph-io/tests/test_cli_anti_regression.py` — exists; add D-11 test
- [x] `packages/graph-io/tests/test_queries.py` — exists; add `test_find_in_package*` tests
- [x] `packages/graph-io/tests/test_cli_format.py` — exists; add `test_render_caps_at_50` (or new test_format file if cap lives in `_format.py` — planner: consolidate with existing file)
- [x] `pytest`, `subprocess`, `pathlib` — already imported and used across tests

*Existing infrastructure covers all phase requirements — no Wave 0 scaffolding needed.*

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| Per-flag `help=` strings render cleanly in `cg find --help` | D-05 | Style judgement, low ROI for assertion | `uv run --package graph-io python -m graph_io.cli.main find --help` — check three flags listed with one-line descriptions |
| Truncation notice cosmetics (exact wording, line position) | D-09 | Subjective formatting | Seed a >50-node graph and run `cg find --in-package <root>` — verify trailer line reads "... showing 50 of N (truncated)" or similar |

---

## Validation Sign-Off

- [x] All tasks have `<automated>` verify or Wave 0 dependencies
- [x] Sampling continuity: every task's acceptance criterion includes a pytest command
- [x] Wave 0 covers all MISSING references (no missing references — all test files exist)
- [x] No watch-mode flags (`-x`, `--lf`, `--pdb`) used in CI commands
- [x] Feedback latency < 35s
- [x] `nyquist_compliant: true` set in frontmatter

**Approval:** approved 2026-05-26 (auto-mode plan-phase)
