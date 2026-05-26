---
phase: 39
slug: scanner-consumes-graph-io
status: draft
nyquist_compliant: true
wave_0_complete: true
created: 2026-05-26
---

# Phase 39 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest 8.x + pytest-asyncio (asyncio_mode=auto) |
| **Config file** | `agents/graph-wiki-agent/pyproject.toml` `[tool.pytest.ini_options]` |
| **Quick run command** | `uv run --package graph-wiki-agent pytest agents/graph-wiki-agent/tests/unit/test_scan_graph_integration.py -q` |
| **Full suite command** | `uv run --package graph-wiki-agent pytest agents/graph-wiki-agent/tests/ -q --ignore=agents/graph-wiki-agent/tests/integration` |
| **Estimated runtime** | quick ~5s, full ~30s (excluding `integration` marker which is skipped by default) |

---

## Sampling Rate

- **After every task commit:** Run quick command above (scoped to the just-committed task with `-k <pattern>`).
- **After every plan wave:** Run `uv run --package graph-wiki-agent pytest agents/graph-wiki-agent/tests/ -q --ignore=agents/graph-wiki-agent/tests/integration` (excludes `integration` marker).
- **Before `/gsd:verify-work`:** Full suite + integration suite (`pytest -m integration`) + Phase 35 regression test (`uv run --package wiki-io pytest packages/wiki-io/tests/test_bootstrap_e2e_no_broken_links.py -q`).
- **Max feedback latency:** 30 seconds.

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Threat Ref | Secure Behavior | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|------------|-----------------|-----------|-------------------|-------------|--------|
| 39-01-01 | 01 | 1 | SCANNER-01 | — | Phase 38 helpers `_build_namespace`, `_capture_run`, `ops_update` importable from `graph_wiki_agent.commands.graph` | unit | `uv run --package graph-wiki-agent python -c "from graph_wiki_agent.commands.graph import _build_namespace, _capture_run, ops_update; print('ok')"` | ❌ W0 (pre-condition gate) | ⬜ pending |
| 39-01-02 | 01 | 1 | SCANNER-01 | — | `run_scan()` calls `cg update` via `_capture_run(ops_update, _build_namespace(...))` BEFORE subagent fan-out; scan log contains `cg update complete: exit_code=0` | unit | `pytest agents/graph-wiki-agent/tests/unit/test_scan_graph_integration.py::test_cg_update_dispatched_before_fanout -q` | ❌ W0 | ⬜ pending |
| 39-01-03 | 01 | 1 | SCANNER-02 | — | After successful `cg update`, decoration step adds `pkg["uri"]` (from graph `attrs["uri"]`) and `pkg["domain"]` (from `belongs_to_domain` edge) to every workspace whose unscoped name matches a graph package node | unit | `pytest agents/graph-wiki-agent/tests/unit/test_scan_graph_integration.py::test_decoration_adds_uri_and_domain -q` | ❌ W0 | ⬜ pending |
| 39-01-04 | 01 | 1 | SCANNER-02 | — | `_wiki_relative_path_for` recomputation: when graph `domain` differs from filesystem `domain`, `pkg["wiki_relative_path"]` is recomputed to `domains/<graph_domain>/packages/<name>/overview.md` | unit | `pytest agents/graph-wiki-agent/tests/unit/test_scan_graph_integration.py::test_slug_recomputed_on_domain_change -q` | ❌ W0 | ⬜ pending |
| 39-01-05 | 01 | 1 | SCANNER-02 (D-07) | — | When `ops_update.run` returns a non-success, non-init exit code (NOT_IN_GIT_REPO=5, UPDATE_IN_PROGRESS=6, SCHEMA_MISMATCH=4, or GENERIC=1 with non-init stderr), `run_scan` raises `ScanAbortedError` BEFORE opening conn or fan-out | unit | `pytest agents/graph-wiki-agent/tests/unit/test_scan_graph_integration.py::test_hard_abort_on_runtime_failure -q` | ❌ W0 | ⬜ pending |
| 39-01-06 | 01 | 1 | SCANNER-02 (D-08) | — | When `ops_update.run` returns GENERIC=1 with stderr matching an init-failure pattern (Permission denied / Errno 13 / Errno 28 / Errno 30 / Read-only filesystem / No space left), `run_scan` emits exactly one stderr line `[NOT_INITIALIZED fallback: graph could not be initialized (<reason>); using path-based slugs]` and proceeds without graph decoration | unit | `pytest agents/graph-wiki-agent/tests/unit/test_scan_graph_integration.py::test_graceful_fallback_on_init_failure -q` | ❌ W0 | ⬜ pending |
| 39-01-07 | 01 | 1 | SCANNER-02 (D-05) | — | Single `read_only_connect` opened after successful update; closed in `finally` even on mid-fan-out exception | unit | `pytest agents/graph-wiki-agent/tests/unit/test_scan_graph_integration.py::test_conn_closed_on_exception -q` | ❌ W0 | ⬜ pending |
| 39-01-08 | 01 | 1 | SCANNER-01, SCANNER-02 | — | End-to-end integration: `run_scan(fixture_workspace)` with no pre-existing graph creates `.graph-wiki/graph/code.db`, populates URI-derived slugs, and resulting vault pages live at `packages/<name>/overview.md` per graph URI | integration | `pytest agents/graph-wiki-agent/tests/integration/test_scan_graph_end_to_end.py -q -m integration` | ❌ W0 | ⬜ pending |
| 39-01-09 | 01 | 1 | SCANNER-03 | — | Phase 35 HYGIENE-14 bootstrap test still passes (regression guard for unchanged wiki-io behavior) | regression | `uv run --package wiki-io pytest packages/wiki-io/tests/test_bootstrap_e2e_no_broken_links.py -q` | ✅ W0 (exists from Phase 35) | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

- [ ] `agents/graph-wiki-agent/tests/unit/test_scan_graph_integration.py` — new file with stubs for SCANNER-01, SCANNER-02 (created in Task 2 — TDD)
- [ ] `agents/graph-wiki-agent/tests/integration/test_scan_graph_end_to_end.py` — new file for SCANNER-01 + SCANNER-02 end-to-end (created in Task 4)
- [ ] `agents/graph-wiki-agent/tests/conftest.py` — verify existing `seeded_graph_conn` fixture from Phase 37 is reusable; add a `tmp_workspace_with_repo` fixture if Phase 37's fixture is insufficient (decided at execute time after reading conftest)

*Existing infrastructure: Phase 37 added the `seeded_graph_conn` fixture; Phase 39 reuses it for the decoration tests. The bootstrap regression test already exists from Phase 35.*

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| (none) | — | All Phase 39 behaviors are automated via the table above. SC#3 is satisfied by the existing Phase 35 automated bootstrap test. | — |

*All phase behaviors have automated verification.*

---

## Validation Sign-Off

- [x] All tasks have `<automated>` verify or Wave 0 dependencies
- [x] Sampling continuity: no 3 consecutive tasks without automated verify
- [x] Wave 0 covers all MISSING references (test files marked ❌ W0)
- [x] No watch-mode flags
- [x] Feedback latency < 30s
- [x] `nyquist_compliant: true` set in frontmatter

**Approval:** pending (gsd-plan-checker review)
