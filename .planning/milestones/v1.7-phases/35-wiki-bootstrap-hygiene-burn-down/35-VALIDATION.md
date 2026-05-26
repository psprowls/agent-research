---
phase: 35
slug: wiki-bootstrap-hygiene-burn-down
status: draft
nyquist_compliant: true
wave_0_complete: false
created: 2026-05-26
---

# Phase 35 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest 8.x + pytest-asyncio 1.3.0 |
| **Config file** | `pyproject.toml` (per-package) — `asyncio_mode = "auto"` |
| **Quick run command** | `uv run --package graph-wiki-agent pytest agents/graph-wiki-agent/tests/unit/test_cli_bootstrap.py agents/graph-wiki-agent/tests/unit/test_cli_help.py -x` |
| **Full suite command** | `uv run --package wiki-io pytest packages/wiki-io/tests/ && uv run --package graph-wiki-agent pytest agents/graph-wiki-agent/tests/` |
| **Estimated runtime** | ~30 s (quick) / ~3-5 min (full) |

---

## Sampling Rate

- **After every task commit:** Run the quick command for the package touched by the task.
- **After every plan wave:** Run the full suite command for both packages.
- **Before `/gsd:verify-work`:** Full suite must be green.
- **Max feedback latency:** 60 seconds for the quick command.

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Threat Ref | Secure Behavior | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|------------|-----------------|-----------|-------------------|-------------|--------|
| 35-01-01 | 01 | 1 | HYGIENE-09 | — | self-healing uv re-exec uses `Path(__file__).resolve()` + `GRAPH_WIKI_BOOTSTRAP_REEXEC` loop guard | grep + smoke | `grep -q "_ensure_uv_workspace" agents/graph-wiki-agent/src/graph_wiki_agent/cli.py && uv run --package graph-wiki-agent graph-wiki-agent --help` | ✅ | ⬜ pending |
| 35-01-02 | 01 | 1 | HYGIENE-11 | — | --interactive flag default OFF preserves silent-skip behavior | integration | `NO_COLOR=1 TERM=dumb COLUMNS=200 uv run --package graph-wiki-agent graph-wiki-agent bootstrap --help \| grep -- "--interactive"` | ✅ | ⬜ pending |
| 35-01-03 | 01 | 1 | HYGIENE-11 | — | run_init forwards `non_interactive=not interactive` to init_wiki | unit | `uv run --package graph-wiki-agent pytest agents/graph-wiki-agent/tests/unit/test_cli_bootstrap.py -x -v` | ✅ | ⬜ pending |
| 35-01-04 | 01 | 1 | HYGIENE-11, HYGIENE-12 | — | both pending bootstrap todos moved to resolved/ (git mv preserves history) | filesystem | `test -f .planning/todos/resolved/2026-05-21-bootstrap-interactive-flag.md && test -f .planning/todos/resolved/2026-05-21-bootstrap-should-stub-empty-category-index-files.md` | ✅ | ⬜ pending |
| 35-01-05 | 01 | 1 | HYGIENE-01..12 (regression) | — | no cross-test regressions in wiki-io or graph-wiki-agent | full-suite | `uv run --package graph-wiki-agent pytest agents/graph-wiki-agent/tests/ -x && uv run --package wiki-io pytest packages/wiki-io/tests/ -x` | ✅ | ⬜ pending |
| 35-02-01 | 02 | 2 | HYGIENE-13 | — | NO_COLOR=1 TERM=dumb COLUMNS=200 documented as load-bearing (260521-ans traceback handle) | grep + unit | `grep -q "260521-ans" agents/graph-wiki-agent/tests/unit/test_cli_help.py && uv run --package graph-wiki-agent pytest agents/graph-wiki-agent/tests/unit/test_cli_help.py -x -v` | ✅ | ⬜ pending |
| 35-02-02 | 02 | 2 | HYGIENE-14 | — | bootstrap-then-scan-then-lint with package/app/plugin containers produces zero broken wikilinks | end-to-end | `uv run --package wiki-io pytest packages/wiki-io/tests/test_bootstrap_e2e_no_broken_links.py -x -v` | ✅ | ⬜ pending |
| 35-02-03 | 02 | 2 | HYGIENE-13, HYGIENE-14 | — | DISCUSSION-LOG.md records closure evidence (pytest stdout paste) + D-03 swap rationale | grep | `grep -q "HYGIENE-13 Closure\|HYGIENE-14 Closure" .planning/phases/35-wiki-bootstrap-hygiene-burn-down/35-DISCUSSION-LOG.md` | ✅ | ⬜ pending |
| 35-02-04 | 02 | 2 | regression | — | full wiki-io + graph-wiki-agent suites still pass with the new test file + comment edit | full-suite | `uv run --package wiki-io pytest packages/wiki-io/tests/ -x && uv run --package graph-wiki-agent pytest agents/graph-wiki-agent/tests/ -x` | ✅ | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

Wave 0 for Phase 35 is **deliberately empty** — the phase is a hygiene burn-down,
not a new-feature surface. The test files already exist for HYGIENE-13
(`test_cli_help.py`) and are net-new for HYGIENE-14
(`test_bootstrap_e2e_no_broken_links.py`, written by Plan B Task 2).

No fixture scaffolding is required beyond what each plan task creates inline.

- [ ] **(Wave 0 marker — N/A for this phase)** — Phase 35 has no Wave 0 prerequisite tests.

---

## Validation Coverage Map (per HYGIENE requirement)

| HYGIENE | Closure Evidence | Test Surface |
|---|---|---|
| HYGIENE-01 | Existing templates already emit `[[wiki/{{CONTAINER_DIR}}/{{PACKAGE_SLUG}}/...]]`; verified by Plan B's `test_bootstrap_e2e_no_broken_links.py` (broken-link count = 0 ⇒ link format is correct) | bootstrap-and-lint regression test |
| HYGIENE-02 | `init_vault.SECTION_INDEX_STUBS` already in place (line 55); verified by Plan B's regression test (lint resolves `[[wiki/<category>/index]]`) | bootstrap-and-lint regression test |
| HYGIENE-03 | `{{CONTAINER_DIR}}` already in all three templates; scanner.md already documents the derivation rule; verified by Plan B's regression test rendering all three container types | bootstrap-and-lint regression test |
| HYGIENE-04 | `260523-he3` quick task landed file-map table format; tests under `test_lint_modules.py` + `test_scan_monorepo.py` already cover. Plan A audits this as already-done. | existing `test_lint_modules.py` (already green) |
| HYGIENE-05 | `testing.md` template files already shipped in all three category template dirs. Plan A audits as already-done. | filesystem check (`ls packages/wiki-io/src/wiki_io/assets/page-templates/*/testing.md`) |
| HYGIENE-06 | `scan_monorepo._wiki_relative_path_for` already returns `overview.md`. Plan A audits as already-done; regression test exercises overview rendering. | bootstrap-and-lint regression test |
| HYGIENE-07 | `workspace_io.config.resolve()` + `_repo_directory_override` already in place; `lint_wiki.SCHEMA_FILENAMES` + `update_tokens` `tokens: null` already in place. Plan A audits as already-done. | existing `test_config.py` / `test_lint_wiki.py` / `test_update_tokens.py` (already green) |
| HYGIENE-08 | `workspace_io/init.py:50` already has `data.setdefault("plugins", [])`. Plan A audits as already-done. | existing `test_init.py:test_init_tolerates_existing_manifest_without_plugins_key` (already green) |
| HYGIENE-09 | Plan A Task 1 adds `_ensure_uv_workspace()` to cli.py | grep verification + `--help` smoke |
| HYGIENE-10 | `plugins/graph-wiki/` docs already use `uv run --project "$AGENT_RESEARCH_ROOT" python ...` shim form. Plan A audits as already-done. | grep verification (no bare `python plugins/...` invocations) |
| HYGIENE-11 | Plan A Tasks 2-3 add `--interactive` Typer flag + thread through run_init + unit test | `test_cli_bootstrap.py` (Plan A Task 3) |
| HYGIENE-12 | `init_vault.SECTION_INDEX_STUBS` already in place — same code as HYGIENE-02. Plan A Task 4 moves the pending todo to `resolved/`. | bootstrap-and-lint regression test |
| HYGIENE-13 | Plan B Task 1 adds the load-bearing comment + Task 3 captures pytest stdout in DISCUSSION-LOG | `test_cli_help.py` 3/3 (already green; just verified + documented) |
| HYGIENE-14 | Plan B Task 2 writes the bootstrap-and-lint regression test | `test_bootstrap_e2e_no_broken_links.py` (new) |

---

## Nyquist Dimensions

| Dimension | Coverage |
|---|---|
| **D1: Specification clarity** | CONTEXT.md D-01..D-05 lock the structure; RESEARCH.md audit table identifies already-done items vs net-new work. |
| **D2: Decomposition** | Two plans, sequenced (Plan A → Plan B per CONTEXT.md D-01). Wave 1 = code edits, Wave 2 = verify-and-close. |
| **D3: Dependency tracking** | Plan B `depends_on: ["35-01"]`. ROADMAP.md "Depends on: Phase 34". |
| **D4: Acceptance criteria** | Every task carries an `<acceptance_criteria>` block with grep + pytest + filesystem assertions. |
| **D5: Test surface mapping** | Per-Task Verification Map above maps each task ID to its test type, command, and HYGIENE requirement. |
| **D6: Threat model** | No security-relevant changes (no auth, no IO at trust boundary). Threat Ref column intentionally `—` throughout. |
| **D7: Observability** | Plan B Task 3 captures pytest stdout in DISCUSSION-LOG.md as the closure artifact. SUMMARY templates require post-execution evidence. |
| **D8: Validation strategy** | This document. The regression test (HYGIENE-14) is the live fence against future template / scanner / lint drift. |

---

*Validation strategy created: 2026-05-26*
*Phase: 35-wiki-bootstrap-hygiene-burn-down*
