---
phase: 57
slug: index-generation-polish
status: draft
nyquist_compliant: true
wave_0_complete: true
created: 2026-05-28
---

# Phase 57 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest (wiki-io package) + syrupy snapshot |
| **Config file** | `packages/wiki-io/tests/conftest.py` (existing `make_index_fixture_graph` factory) |
| **Quick run command** | `uv run --package wiki-io pytest packages/wiki-io/tests/test_index_generator.py -q` |
| **Snapshot update** | `uv run --package wiki-io pytest packages/wiki-io/tests/test_index_generator.py -q --snapshot-update` |
| **Full suite command** | `uv run --package wiki-io pytest` |
| **Estimated runtime** | ~10 seconds (quick); ~30s (full) |

---

## Sampling Rate

- **After every task commit:** Run the quick command (single test file touched by every task)
- **After the plan wave:** Run `uv run --package wiki-io pytest`
- **Before `/gsd:verify-work`:** Full suite green AND syrupy snapshot regenerated/committed
- **Max feedback latency:** 10 seconds

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Threat Ref | Secure Behavior | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|------------|-----------------|-----------|-------------------|-------------|--------|
| 57-01-01 | 01 | 1 | IDX-05 | — | N/A | unit | `uv run --package graph-io pytest packages/graph-io/tests/test_queries.py -q` | ✅ | ⬜ pending |
| 57-01-02 | 01 | 1 | IDX-01, IDX-02, IDX-03, IDX-04, IDX-05 | — | N/A | unit | `uv run --package wiki-io pytest packages/wiki-io/tests/test_index_generator.py -q` | ✅ | ⬜ pending |
| 57-01-03 | 01 | 1 | IDX-01..IDX-05 | — | N/A | unit + snapshot | `uv run --package wiki-io pytest packages/wiki-io/tests/test_index_generator.py -q` | ✅ | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

*Existing infrastructure covers all phase requirements. `test_index_generator.py` exists with the `make_index_fixture_graph` factory (in-memory graph from declarative spec — supports `app` nodes and `depends_on_package` edges, schema has no kind CHECK), `_write_curated_page` helper (frontmatter writer), and a syrupy snapshot harness. `test_queries.py` exists in graph-io with the `upsert.upsert_records` seeding pattern for the new query function.*

---

## Manual-Only Verifications

*All phase behaviors have automated verification. The syrupy snapshot against the live `.graph-wiki/graph.db` is automated but only meaningful after Phase 56 lands (see execution-gate note in PLAN.md) — regenerate the snapshot at that point.*

---

## Validation Sign-Off

- [x] All tasks have `<automated>` verify or Wave 0 dependencies
- [x] Sampling continuity: no 3 consecutive tasks without automated verify
- [x] Wave 0 covers all MISSING references (none missing)
- [x] No watch-mode flags
- [x] Feedback latency < 10s
- [x] `nyquist_compliant: true` set in frontmatter

**Approval:** approved 2026-05-28
