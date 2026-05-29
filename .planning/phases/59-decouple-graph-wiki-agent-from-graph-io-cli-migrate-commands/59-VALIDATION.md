---
phase: 59
slug: decouple-graph-wiki-agent-from-graph-io-cli-migrate-commands
status: approved
nyquist_compliant: true
wave_0_complete: false
created: 2026-05-29
---

# Phase 59 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest ≥8.3 + syrupy 5.1.0 (both already in workspace dev deps) |
| **Config file** | `agents/graph-wiki-agent/pyproject.toml` + `packages/graph-io` pyproject (`[tool.pytest.ini_options]`) |
| **Quick run command** | `uv run --package graph-wiki-agent pytest tests/unit/test_commands_graph.py -x` |
| **Full suite command** | `uv run --package graph-wiki-agent pytest` |
| **cg regression command** | `uv run --package graph-io pytest tests/test_cli_format.py tests/test_cli_describe.py tests/test_cli_describe_entry_point.py tests/test_cli_exit_codes.py tests/test_cli_anti_regression.py -x` |
| **Estimated runtime** | ~30-60 seconds (full agent suite); seeded fixtures are session-scoped |

---

## Sampling Rate

- **After every task commit:** `uv run --package graph-wiki-agent pytest tests/unit/test_commands_graph.py -x && uv run --package graph-io pytest tests/test_cli_format.py -x`
- **After every plan wave:** full agent suite + cg describe/exit-code/anti-regression suites
- **Before `/gsd:verify-work`:** both packages' relevant suites green + SC#1 grep clean
- **Max feedback latency:** ~60s

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Threat Ref | Secure Behavior | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|------------|-----------------|-----------|-------------------|-------------|--------|
| 59-01-01 | 01 | 1 | SC-03 (D-01/D-02) | T-59-01 | byte-identical render output preserved | unit + import | `uv run --package graph-io pytest tests/test_cli_format.py -x` | ✅ test_cli_format.py | ⬜ pending |
| 59-01-02 | 01 | 1 | SC-03 (D-02/D-03) | T-59-01/02 | cg describe/find output byte-identical | regression | `uv run --package graph-io pytest tests/test_cli_describe.py tests/test_cli_describe_entry_point.py tests/test_cli_exit_codes.py tests/test_cli_anti_regression.py -x` | ✅ (existing) | ⬜ pending |
| 59-02-01 | 02 | 2 | SC-01/SC-02 (D-04..D-07) | T-59-03/04/05 | no cli import; parameterized SQL; exit-code contract incl AMBIGUOUS(7) | static grep + import | `grep -nE "graph_io\.cli\|^import argparse\|_build_namespace\|_capture_run\|redirect_stdout" agents/graph-wiki-agent/src/graph_wiki_agent/commands/graph.py \|\| echo CLEAN; uv run --package graph-wiki-agent python -c "from graph_wiki_agent.commands import graph"` | ❌ W0 (Plan 03 tests) | ⬜ pending |
| 59-02-02 | 02 | 2 | SC-01 | T-59-05 | second cli importer removed | static grep + import | `grep -rn "graph_io.cli" agents/graph-wiki-agent/src/ \|\| echo CLEAN; uv run --package graph-wiki-agent python -c "from graph_wiki_agent.graph_tools import build_graph_tools"` | n/a | ⬜ pending |
| 59-03-01 | 03 | 3 | SC-03 (D-09) | T-59-06 | additive fixture; seeded_graph_conn untouched | fixture + regression | `uv run --package graph-wiki-agent pytest tests/unit/test_graph_tools.py -x` | ✅ conftest.py | ⬜ pending |
| 59-03-02 | 03 | 3 | SC-03 (D-08) | T-59-07 | byte-identical snapshots + exit-code branches | snapshot + unit | `uv run --package graph-wiki-agent pytest tests/unit/test_commands_graph.py -x` | ❌ W0 (this task creates) | ⬜ pending |
| 59-03-03 | 03 | 3 | SC-04 | — | full suite green + SC#1 grep clean | integration | `uv run --package graph-wiki-agent pytest` | ✅ | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

Wave 0 work is folded into Plan 03 (the test rebuild runs after the Plan 02 migration it verifies):

- [ ] `agents/graph-wiki-agent/tests/conftest.py` — add `seeded_graph_workspace` session fixture (Plan 03 Task 1)
- [ ] `agents/graph-wiki-agent/tests/unit/test_commands_graph.py` — full replacement: keep 4 shape tests, replace 7 mock tests with real-DB snapshot + exception-based exit-code tests (Plan 03 Task 2)
- [ ] `agents/graph-wiki-agent/tests/unit/__snapshots__/test_commands_graph.ambr` — generate baseline via `--snapshot-update` (Plan 03 Task 2)

No framework install needed — pytest + syrupy already present.

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| — | — | — | — |

All phase behaviors have automated verification (static grep for SC#1/SC#2; syrupy snapshots + exit-code asserts for SC#3; full-suite run for SC#4).

---

## Validation Sign-Off

- [x] All tasks have `<automated>` verify or Wave 0 dependencies
- [x] Sampling continuity: no 3 consecutive tasks without automated verify
- [x] Wave 0 covers all MISSING references (fixture + test rebuild + snapshot baseline in Plan 03)
- [x] No watch-mode flags
- [x] Feedback latency < 60s
- [x] `nyquist_compliant: true` set in frontmatter

**Approval:** approved 2026-05-29
