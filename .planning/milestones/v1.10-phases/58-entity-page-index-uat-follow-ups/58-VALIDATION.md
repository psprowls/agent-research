---
phase: 58
slug: entity-page-index-uat-follow-ups
status: validated
nyquist_compliant: true
wave_0_complete: true
created: 2026-05-28
validated: 2026-05-29
---

# Phase 58 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest ≥8.3 (pytest-asyncio 1.3.0, syrupy 5.1.0) |
| **Config file** | `packages/graph-io/pyproject.toml` + `packages/wiki-io/pyproject.toml` `[tool.pytest.ini_options]` |
| **Quick run command** | `uv run --package wiki-io pytest packages/wiki-io/tests/ -x -q` (or `--package graph-io` for graph-io changes) |
| **Full suite command** | `uv run pytest -x -q` |
| **Estimated runtime** | ~60 seconds |

---

## Sampling Rate

- **After every task commit:** Run the per-package quick command for the package touched
- **After every plan wave:** Run `uv run pytest -x -q` (full suite — Item #3 spans two packages)
- **Before `/gsd:verify-work`:** Full suite must be green
- **Max feedback latency:** 60 seconds

---

## Per-Task Verification Map

> Task IDs are assigned during planning; rows below map each success criterion to its
> automated proof. The planner threads these into per-task `<acceptance_criteria>`.

| Criterion | Behavior | Test Type | Automated Command | File Exists | Status |
|-----------|----------|-----------|-------------------|-------------|--------|
| SC#1 — Related marker | Generated entity pages contain a clean Obsidian-safe Related marker; no `<...>` survives | unit (template render) | `uv run --package wiki-io pytest packages/wiki-io/tests/test_entity_templates.py -k related -x` | ✅ `test_entity_templates.py::test_related_block_is_obsidian_safe:172` | ✅ green |
| SC#2 — Summary placeholder | Empty-description `summary:` placeholder has no leading `>`, no `<...>`, no `:` | unit | `uv run --package wiki-io pytest packages/wiki-io/tests/test_entity_writer.py::test_merge_summary_todo_marker_when_description_empty -x` | ✅ `test_entity_writer.py::test_merge_summary_todo_marker_when_description_empty:478` | ✅ green |
| SC#3 — Per-package suite nesting | In index `## By Kind`, each package nests only its own suite(s); resolution keys on `test_suite` uri | unit + snapshot | `uv run --package wiki-io pytest packages/wiki-io/tests/test_index_generator.py::test_consumer_pkgs_fanout_regression_guard -x` | ✅ `test_index_generator.py::test_consumer_pkgs_fanout_regression_guard:1210` | ✅ green |
| SC#3b — Unique suite names | No two `test_suite` nodes share a name: `SELECT name,COUNT(*) FROM nodes WHERE kind='test_suite' GROUP BY name HAVING COUNT(*)>1` → 0 rows | integration | `uv run --package graph-io pytest packages/graph-io/tests/test_test_suites.py::test_suite_names_unique_after_multi_package_emit -x` | ✅ `test_test_suites.py::test_suite_names_unique_after_multi_package_emit:719` | ✅ green |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

- [x] `packages/wiki-io/tests/test_index_generator.py` — fan-out regression guard added: `test_consumer_pkgs_fanout_regression_guard:1210` proves `_consumer_pkgs` / `_consumer_pkgs_in_domain` return distinct per-suite results (uri-keyed fix) — Plan 03
- [x] `packages/graph-io/tests/test_test_suites.py` — name-based assertions updated to package-qualified names (`:126`); repository-owned suite case (`:111`, `("tests","tests")`) unchanged; uniqueness guard `test_suite_names_unique_after_multi_package_emit:719` added — Plan 02
- [x] `packages/wiki-io/tests/test_entity_writer.py` — exact-string assertion updated for new summary placeholder (`test_merge_summary_todo_marker_when_description_empty:478`, D-06) — Plan 01
- [x] `packages/wiki-io/tests/test_entity_templates.py` — SC#1 regression guard added: `test_related_block_is_obsidian_safe:172` asserts the three entity templates' `## Related` block has no `<`, no leading `>`, no `:` — added during validation audit (was a grep-only exec gate)

*Framework is already installed — no install task needed.*

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| Obsidian inline rendering of summary + Related | SC#1, SC#2 | True rendering fidelity is an Obsidian-runtime concern; automated tests assert the marker-string constraints (no `>`/`<...>`/`:`) that are the root cause, not pixels | Open a regenerated entity page in Obsidian; confirm the `summary:` bullet and following list items render, and the `## Related` marker shows as plain text |

*The string-constraint assertions are automated; only visual confirmation in Obsidian is manual.*

---

## Validation Sign-Off

- [x] All tasks have `<automated>` verify or Wave 0 dependencies
- [x] Sampling continuity: no 3 consecutive tasks without automated verify
- [x] Wave 0 covers all MISSING references
- [x] No watch-mode flags
- [x] Feedback latency < 60s
- [x] `nyquist_compliant: true` set in frontmatter

**Approval:** validated 2026-05-29 — all 4 success criteria have green automated tests

---

## Validation Audit 2026-05-29

| Metric | Count |
|--------|-------|
| Gaps found | 1 |
| Resolved | 1 |
| Escalated | 0 |

**Gap:** SC#1 (`## Related` block Obsidian-safety) was enforced only by a one-time `grep` gate at execution (58-01-PLAN Task 1), with no committed pytest regression test. SC#2 / SC#3 / SC#3b were already covered green by tests written during Plans 01–03.

**Resolution:** Added `test_related_block_is_obsidian_safe` (parametrized over entity templates, skips those with no `## Related`) to `packages/wiki-io/tests/test_entity_templates.py`. Asserts no `<`, no leading `>`, no `:` on any Related-block body line — catches the v1.10 defect class without hardcoding the marker wording. 3 passed, 4 skipped. Phase is now Nyquist-compliant.
