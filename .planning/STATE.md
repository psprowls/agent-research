---
gsd_state_version: 1.0
milestone: v1.8
milestone_name: Wiki Entity Restructure
status: completed
stopped_at: Phase 48 context gathered
last_updated: "2026-05-27T15:19:25.406Z"
last_activity: 2026-05-27 -- Phase 45 marked complete
progress:
  total_phases: 7
  completed_phases: 5
  total_plans: 17
  completed_plans: 14
  percent: 71
---

# Project State: agent-research

**Last updated:** 2026-05-26 — v1.8 roadmap created (Phases 42-48)
**Updated by:** gsd-roadmapper

---

## Project Reference

See: `.planning/PROJECT.md`

**Core Value:** Faithfully reproduce the graph-wiki plugin's wiki-maintenance workflows while running entirely on AWS Bedrock with parallel subagents, at meaningfully lower cost than the current Claude-Code-hosted plugin.

**Current Focus:** Phase 47 — cg-domain-clusters

---

## Phase 43 — Completed (2026-05-27)

- `wiki_io.entity_writer.write_entities` shipped (Plans 43-01, 43-02, 43-03). Single public entry point; acquires `.graph-wiki/scan.lock` on entry, per-kind create/merge/hard-delete sweep, byte-stable write-if-changed, returns `EntityWriteResult` with `needs_narrative` for the Phase 45 LLM gate.
- All ENTITY-01..05 implemented (verified by 6 integration tests under `packages/wiki-io/tests/integration/test_entity_writer_integration.py` against a real synthetic workspace).
- **`package_family` deferred to v1.9** — `ADMITTED_KINDS_V18 = ADMITTED_KINDS - {"package_family"}`. Phase 42's `package_family_uri` builder + `entity-package-family.md` template remain in the codebase but are dormant in v1.8. Phase 46 cutover will NOT remove `wiki/package-family/` (no entity replacements exist yet).
- **Folded todo resolved:** `2026-05-26-fix-scanner-treats-import-root-as-subpackage.md` moved to `.planning/todos/resolved/`. `structural_nodes._walk_subpackages` no longer yields the import root itself; subpackage node count rebaselined where applicable (six tests in `test_structural_nodes.py` updated; two new regression tests added).
- **Pitfall guards activated (verified by integration tests):**
  - Pitfall 2 (frontmatter merge collision) — `merge_frontmatter` + `status: deprecated` preservation test.
  - Pitfall 3 (hard-delete losing edits) — `.graph-wiki/deletions.log` JSONL audit log with `body_was_empty` flag + 10MB two-file rotation policy.
  - Pitfall 9 (concurrent scan race) — `fcntl.flock(LOCK_EX | LOCK_NB)` non-blocking lock at `.graph-wiki/scan.lock`; verified `<500ms` LOCK_NB fail-fast.
- **graph-io side effect (unblocks Phase 44):** `_row_to_node` + `_list_by_kind` now project the `nodes.uri` column back into `NodeRecord.attrs` so downstream callers can read URI uniformly from `node.attrs["uri"]`. This also resolves the Phase 44 BLOCKER noted below (Phase 43 commits are now on disk — graph-io has `list_dependencies` / `list_plugins` / `describe_dependency` / `describe_plugin`).

---

## Phase 44 — Completed (2026-05-27)

- `wiki_io.index_generator.generate_index(conn, wiki_root)` shipped (Plans 44-01, 44-02). New 640-line module producing `wiki/index.md` from graph queries (placement under domains via D-04 single-placement rule, by-kind fallback) and curated-lane filesystem scans (architecture / adrs / concepts / sources / work). Atomic write-if-changed via `os.replace`.
- All INDEX-01..05 implemented (49 active tests + 1 conditionally-skipped snapshot in `packages/wiki-io/tests/test_index_generator.py`). Determinism (Pitfall 5 mitigation) verified via permuted-insertion test; write-if-changed verified by mtime-unchanged assertion on second invocation.
- **Scope expansion (INDEX-05 reinterpreted):** Single `wiki/index.md` now consolidates the four curated lane sections + Work; per-folder `wiki/<lane>/index.md` files become obsolete and will be deleted in Phase 46 cutover. The plan documents this expansion against the original "preserve per-folder sub-indexes" wording.
- **INDEX-02 reinterpreted by D-04:** entities appear ONCE — under their single qualifying domain, OR in `## By Kind` when qualifying domains are 0 or >=2. The original "twice" wording is superseded by the single-placement decision in CONTEXT.md D-04.
- **`CURATED_LANES` correction:** module constant uses bare lane names (`"architecture"`) rather than wiki-rooted (`"wiki/architecture"`) per the path-derivation note in 44-01-PLAN — `wiki_root` IS the wiki directory, so the bare name is the correct relative path.
- **`update_index.py` and `packages/wiki-io/pyproject.toml` byte-identical** to pre-Phase-44 state (D-01, D-22 — Phase 46 deletes `update_index.py`, not Phase 44).
- Full wiki-io suite green: 1288 passed, 35 skipped (snapshot deferred until live `.graph-wiki/graph.db` exists post-Phase-45).

---

## Current Position

Phase: 45 — COMPLETE
Plan: Not started
Status: Phase 45 complete
Last activity: 2026-05-27 -- Phase 45 marked complete

Progress: [████████░░] 75%

---

## Performance Metrics

| Metric | Value |
|--------|-------|
| Phases total (v1.0–v1.7) | 41 |
| Phases complete (v1.0–v1.7) | 41 |
| Plans written (v1.0–v1.7) | 150 |
| v1.8 phases planned | 7 |
| v1.8 requirements | 32 |

---

## Accumulated Context

### Key Decisions (v1.8 scoping)

- **D1 lock: URI slug encoding uses `__` as separator** — `pkg:agent-research/graph-io` → `pkg__agent-research__graph-io.md`; `:` and `/` both encode as `__`; encoding is injective and must be property-tested before any entity page is written
- **D2 lock: scanner-owned whitelist is a `frozenset` constant in `entity_writer.py`** — reconcile ARCHITECTURE.md per-kind breakdown + FEATURES.md flat list at Phase 42; human-authored keys (`status`, `last_reviewed`, `owner`, `notes`) explicitly excluded
- **Hard-delete with append-log** — entity pages for disappeared graph nodes are deleted on next scan; every deletion logged to `.graph-wiki/deletions.log`; vault is disposable per PROJECT.md
- **Phases 47-48 are independent** — `cg domain-clusters` (Phase 47) and `graph propose-domains` (Phase 48) touch only `graph-io/` and `commands/graph.py`; can proceed in parallel with Phases 42-46 or slip to v1.9 with zero rework cost
- **Phase 42 must complete before any entity-writing code runs** — the slug scheme and whitelist are the load-bearing contracts that cascade across all downstream phases

### Active Pitfall Guards (encode in plans)

- Pitfall 1 (slug collision): property test over 1,000 URIs from all 7 admitted kinds must pass before entity writer is wired into any scan path
- Pitfall 2 (frontmatter key collision): whitelist merge enforced at write time; merge test (human `status: deprecated` survives entity update) required in Phase 43 acceptance criteria
- Pitfall 3 (hard-delete losing human edits): deletion policy is hard-delete-with-log; policy must be stated explicitly in Phase 43 plan
- Pitfall 4 (migration regex over-matching): Markdown-aware tokenizer required; code-block exclusion test in Phase 46 acceptance criteria
- Pitfall 5 (index churn): determinism test + write-if-changed guard required in Phase 44
- Pitfall 6 (degenerate clusters): hub-exclusion preprocessing + degenerate-cluster warning in Phase 47 initial implementation, not v1.9
- Pitfalls 7-8 (LLM hallucination + auto-apply): grounding check + isolation test required in Phase 48 same commit
- Pitfall 9 (concurrent scan race): scan.lock in Phase 43
- Pitfall 10 (migration re-run artifacts): idempotency guard in Phase 46

### Pending Todos

None — fresh milestone start.

### Blockers

None — Phase 43 has landed (`list_dependencies`, `list_plugins`, `describe_dependency`, `describe_plugin` exist; `_VALID_KINDS` extended; `nodes.uri` projected into `NodeRecord.attrs["uri"]` uniformly across all `list_*`/`describe_*` callers). Phase 44 execution proceeding.

---

## Deferred Items

Carried forward from prior milestone closes:

| Category | Item | Status |
|----------|------|--------|
| nyquist | 0/28+ v1.1-v1.6 phases produced VALIDATION.md | decision pending (retro-validate vs. disable toggle) |
| slug_fix | `librarian.py:21` `_SLUG_ONLY_RE` parity fix | not load-bearing; deferred past v1.8 |
| audit | v1.6-MILESTONE-AUDIT.md not produced | acknowledged at v1.6 close |

---

## Session Continuity

Last session: 2026-05-27T15:14:57.624Z
Stopped at: Phase 48 context gathered

**Next action:** `/gsd:plan-phase 42` to plan the URI Slug Scheme + Per-Kind Templates phase.

---

*State initialized: 2026-05-13*
*v1.7 archived: 2026-05-26 — 7 phases (35-41), 10 plans, 27 requirements*
*v1.8 roadmap created: 2026-05-26 — 7 phases (42-48), 32 requirements*
