---
phase: 45
slug: scanner-integration
status: draft
nyquist_compliant: true
wave_0_complete: true
created: 2026-05-27
---

# Phase 45 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest 8.x + pytest-asyncio 1.3.x + syrupy 5.x |
| **Config file** | `pyproject.toml` per package (existing) |
| **Quick run command** | `uv run --package graph-wiki-agent pytest agents/graph-wiki-agent/tests -x` |
| **Full suite command** | `uv run pytest` (root, all workspace members) |
| **Estimated runtime** | ~45 seconds quick, ~3 minutes full |

---

## Sampling Rate

- **After every task commit:** Run `uv run --package <pkg> pytest tests/ -x -k <area>`
- **After every plan wave:** Run quick suite for the changed packages
- **Before `/gsd:verify-work`:** Full suite green, including the plugin smoke regression
- **Max feedback latency:** ~10 seconds for a focused unit test, ~45 seconds for the agent test suite

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Secure Behavior | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|-----------------|-----------|-------------------|-------------|--------|
| 45-01-01 | 01 | 1 | SCANINT-02 | narrator role isolated from scanner config | unit | `uv run --package model-adapter pytest packages/model-adapter/tests -k narrator` | ❌ W0 | ⬜ pending |
| 45-01-02 | 01 | 1 | SCANINT-02 | inject_narrative replaces only the Narrative body | unit | `uv run --package wiki-io pytest packages/wiki-io/tests/test_inject_narrative.py` | ❌ W0 | ⬜ pending |
| 45-01-03 | 01 | 1 | SCANINT-04 | update_index no longer writes wiki/index.md | unit | `uv run --package wiki-io pytest packages/wiki-io/tests/test_update_index_surgical.py` | ❌ W0 | ⬜ pending |
| 45-01-04 | 01 | 1 | SCANINT-04 | REQUIREMENTS.md SCANINT-04 text updated | grep | `grep -q "produce per-folder" .planning/REQUIREMENTS.md` | N/A | ⬜ pending |
| 45-01-05 | 01 | 1 | SCANINT-02 | scanner_frontmatter_for_node re-exported | unit | `uv run --package wiki-io pytest packages/wiki-io/tests/test_entity_writer.py -k scanner_frontmatter` | ✅ | ⬜ pending |
| 45-02-01 | 02 | 1 | SCANINT-05 | ExistingPages dataclass with legacy + entities sub-dicts | unit | `uv run --package wiki-io pytest packages/wiki-io/tests/test_load_existing_pages.py` | ❌ W0 | ⬜ pending |
| 45-02-02 | 02 | 1 | SCANINT-05 | _load_existing_pages walks wiki/entities/ by URI | unit | `uv run --package wiki-io pytest packages/wiki-io/tests/test_load_existing_pages.py -k entities` | ❌ W0 | ⬜ pending |
| 45-02-03 | 02 | 1 | SCANINT-05 | compute_diff continues to operate on legacy only | unit | `uv run --package wiki-io pytest packages/wiki-io/tests/test_scan_monorepo.py -k compute_diff` | ✅ | ⬜ pending |
| 45-02-04 | 02 | 1 | SCANINT-06 | scan_monorepo.main() callers pass .legacy | unit | `uv run --package wiki-io pytest packages/wiki-io/tests/test_scan_monorepo.py` | ✅ | ⬜ pending |
| 45-03-01 | 03 | 2 | SCANINT-01, SCANINT-02 | build_entity_narrative_prompt emits prose-only system instructions | unit | `uv run --package graph-wiki-agent pytest agents/graph-wiki-agent/tests/unit/test_entity_narrative_prompt.py` | ❌ W0 | ⬜ pending |
| 45-03-02 | 03 | 2 | SCANINT-01 | run_scan calls write_entities then narrator fan-out (gated on needs_narrative) | integration | `uv run --package graph-wiki-agent pytest agents/graph-wiki-agent/tests/integration/test_scan_entity_integration.py -k step_9` | ❌ W0 | ⬜ pending |
| 45-03-03 | 03 | 2 | SCANINT-01 | run_scan ScanResult shape includes entities_* fields | unit | `uv run --package graph-wiki-agent pytest agents/graph-wiki-agent/tests/unit/test_scan_result_shape.py` | ❌ W0 | ⬜ pending |
| 45-03-04 | 03 | 2 | SCANINT-03 | Step 11 leaves entity hard-deletes to write_entities; legacy stale-tag unchanged | integration | `uv run --package graph-wiki-agent pytest agents/graph-wiki-agent/tests/integration/test_scan_entity_integration.py -k deletion` | ❌ W0 | ⬜ pending |
| 45-03-05 | 03 | 2 | SCANINT-04 | Step 12 dual-call: generate_index then update_index | integration | `uv run --package graph-wiki-agent pytest agents/graph-wiki-agent/tests/integration/test_scan_entity_integration.py -k step_12` | ❌ W0 | ⬜ pending |
| 45-03-06 | 03 | 2 | SCANINT-02 | LLM-generated content on entity pages is prose-only (frontmatter untouched) | integration | `uv run --package graph-wiki-agent pytest agents/graph-wiki-agent/tests/integration/test_scan_entity_integration.py -k prose_only` | ❌ W0 | ⬜ pending |
| 45-03-07 | 03 | 2 | SCANINT-06 | Plugin smoke regression: legacy scan_monorepo path unchanged | integration | `uv run --package wiki-io pytest packages/wiki-io/tests/test_scan_monorepo.py` | ✅ | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

Each plan creates its own Wave 0 test file (no pre-plan Wave 0 wave needed — pytest is already present and configured). The files listed below as `❌ W0` are created in the same task that adds the production code; the executor writes them empty/failing first, then makes them pass.

- [ ] `packages/wiki-io/tests/test_inject_narrative.py` — Plan 01
- [ ] `packages/wiki-io/tests/test_update_index_surgical.py` — Plan 01
- [ ] `packages/model-adapter/tests/test_narrator_role.py` (or extend existing) — Plan 01
- [ ] `packages/wiki-io/tests/test_load_existing_pages.py` (or extend `test_scan_monorepo.py`) — Plan 02
- [ ] `agents/graph-wiki-agent/tests/unit/test_entity_narrative_prompt.py` — Plan 03
- [ ] `agents/graph-wiki-agent/tests/unit/test_scan_result_shape.py` — Plan 03
- [ ] `agents/graph-wiki-agent/tests/integration/test_scan_entity_integration.py` — Plan 03

*Existing infrastructure (`pytest`, `pytest-asyncio`, `syrupy`) covers all framework needs — no new dev dependencies.*

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| Narrator prompt quality on real entity pages | SCANINT-02 (qualitative) | Bedrock cost + no oracle for prose quality in v1.8 | Run `graph-wiki-agent scan` against the live `agent-research` vault; eyeball 3 entity pages for prose coherence; compare narrator output across a `pkg`, a `domain`, and a `dependency` |

*All structural / contract behaviors have automated verification.*

---

## Validation Sign-Off

- [x] All tasks have automated verify or Wave 0 dependencies
- [x] Sampling continuity: no 3 consecutive tasks without automated verify
- [x] Wave 0 covers all MISSING references
- [x] No watch-mode flags
- [x] Feedback latency < 60s
- [x] `nyquist_compliant: true` set in frontmatter

**Approval:** pending
