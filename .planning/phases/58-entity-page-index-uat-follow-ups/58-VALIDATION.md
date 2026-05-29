---
phase: 58
slug: entity-page-index-uat-follow-ups
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-05-28
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
| SC#1 — Related marker | Generated entity pages contain a clean Obsidian-safe Related marker; no `<...>` survives | unit (template render) | `uv run --package wiki-io pytest packages/wiki-io/tests/ -k related -x` | ⚠️ assertion to add | ⬜ pending |
| SC#2 — Summary placeholder | Empty-description `summary:` placeholder has no leading `>`, no `<...>`, no `:` | unit | `uv run --package wiki-io pytest packages/wiki-io/tests/test_entity_writer.py -x` | ✅ (needs update, `test_entity_writer.py:482`) | ⬜ pending |
| SC#3 — Per-package suite nesting | In index `## By Kind`, each package nests only its own suite(s); resolution keys on `test_suite` uri | unit + snapshot | `uv run --package wiki-io pytest packages/wiki-io/tests/test_index_generator.py -x` | ⚠️ fan-out regression guard to add | ⬜ pending |
| SC#3b — Unique suite names | No two `test_suite` nodes share a name: `SELECT name,COUNT(*) FROM nodes WHERE kind='test_suite' GROUP BY name HAVING COUNT(*)>1` → 0 rows | integration | `uv run --package graph-io pytest packages/graph-io/tests/test_test_suites.py -x` | ✅ (assertions need update, `test_test_suites.py:126`) | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

- [ ] `packages/wiki-io/tests/test_index_generator.py` — add a fan-out regression guard: when multiple suites share a name but have distinct URIs, `_consumer_pkgs` / `_consumer_pkgs_in_domain` return distinct per-suite results (proves the uri-keyed fix)
- [ ] `packages/graph-io/tests/test_test_suites.py` — update name-based assertions (`:126`) to the new package-qualified names; confirm the repository-owned suite case (`:111`, `("tests","tests")`) stays unchanged
- [ ] `packages/wiki-io/tests/test_entity_writer.py` — update the exact-string assertion at `:482` for the new summary placeholder (D-06)

*Framework is already installed — no install task needed.*

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| Obsidian inline rendering of summary + Related | SC#1, SC#2 | True rendering fidelity is an Obsidian-runtime concern; automated tests assert the marker-string constraints (no `>`/`<...>`/`:`) that are the root cause, not pixels | Open a regenerated entity page in Obsidian; confirm the `summary:` bullet and following list items render, and the `## Related` marker shows as plain text |

*The string-constraint assertions are automated; only visual confirmation in Obsidian is manual.*

---

## Validation Sign-Off

- [ ] All tasks have `<automated>` verify or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references
- [ ] No watch-mode flags
- [ ] Feedback latency < 60s
- [ ] `nyquist_compliant: true` set in frontmatter

**Approval:** pending
