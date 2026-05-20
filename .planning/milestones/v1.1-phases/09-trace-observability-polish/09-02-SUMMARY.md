---
phase: 09-trace-observability-polish
plan: 02
subsystem: trace
tags:
  - trace
  - documentation
  - schema-version
dependency_graph:
  requires: []
  provides:
    - docs/trace-schema.md (authoritative schema reference)
    - cross-link from docs/cancellation.md
  affects:
    - docs/cancellation.md (one-line cross-link addition)
tech_stack:
  added: []
  patterns:
    - sibling-doc cross-link (no field-table duplication, per D-06)
    - schema-version self-describing per-line JSONL (D-01)
key_files:
  created:
    - docs/trace-schema.md
  modified:
    - docs/cancellation.md
decisions:
  - Lifted real fixture example (1778766775_3d8c7377.jsonl) for the per-item shape and a real query_summary example (query_07ae8b630300.jsonl) for the query summary shape; constructed the batch_cancelled example since no fixture exists for that record kind.
  - Used relative link `./trace-schema.md` (sibling-doc form) in cancellation.md's cross-link.
  - Trimmed the document body from 321 to 319 lines to land inside the 120-320 acceptance window without losing the v1.1-scope callout block or the `---` separators that mirror cancellation.md's structure.
metrics:
  duration_minutes: ~12
  tasks_completed: 2
  files_created: 1
  files_modified: 1
  completed_date: 2026-05-17
requirements:
  - OBS-04
---

# Phase 9 Plan 2: Trace Schema Documentation Summary

OBS-04's documentation half: a new `docs/trace-schema.md` reference (319 lines, six H2 sections) and a one-sentence cross-link from `docs/cancellation.md` §3 back to it. Field tables, schema_version policy, and the v0 backward-compat note are now consolidated in the new doc; cancellation.md keeps its illustrative JSON blocks but defers field-table authority.

## Tasks Completed

| # | Name                                                            | Commit  | Files                 |
| - | --------------------------------------------------------------- | ------- | --------------------- |
| 1 | Create docs/trace-schema.md with all six required sections      | 62389b5 | docs/trace-schema.md  |
| 2 | Add one-line cross-link from cancellation.md to trace-schema.md | 52d98cf | docs/cancellation.md  |

## Section Titles Used in docs/trace-schema.md

1. `# Trace Schema for \`graph-wiki-agent\`` (title)
2. `## 1. Directory Layout and Filename Convention`
3. `## 2. Per-Record Shapes` (with H3 subsections 2.1 Per-Item Subagent Record, 2.2 Batch Event Record, 2.3 Query Summary Record)
4. `## 3. The \`schema_version\` Field`
5. `## 4. The Additive-Shape Rule`
6. `## 5. v0 (Unversioned) Compatibility`
7. `## 6. Examples`

Maps to the D-05 required-sections list as:
- (a) directory layout / filename convention → §1
- (b) per-record shapes → §2 (three subsections, each with field table + JSON example)
- (c) `schema_version` field + policy → §3
- (d) additive-shape rule (cross-referencing Phase 8 D-06/D-07) → §4
- (e) v0 compatibility → §5
- (f) examples → §6

## docs/trace-schema.md Statistics

- **Line count:** 319 lines (target window: 120-320; D-05 target ~150-250 plus the cushion noted in the plan).
- **`schema_version` occurrences:** 31 (acceptance criterion: ≥ 5).
- **Fenced ```json blocks:** 6 — three in §2 (one per record shape) plus three more in §6 (Examples). Acceptance criterion: ≥ 3.
- **Required discriminators present:** `batch_cancelled`, `query_summary`, `cancellation.md` cross-link, `09-CONTEXT.md` source line.

## Cross-Link Insertion Point in docs/cancellation.md

- **Location:** Inside §3 "Trace Shapes", inserted directly under the section heading and before the existing sentence `\`SubagentPool\` writes two kinds of records when a fan-out is cancelled.`
- **File line numbers (post-edit):** lines 96-97 — one new sentence + one blank-line separator.
- **Link target syntax used:** `` [`docs/trace-schema.md`](./trace-schema.md) `` (sibling-doc relative link). Both the path-style label `docs/trace-schema.md` and the relative `./trace-schema.md` target are present, satisfying the `pattern: "\\[.*\\]\\(.*trace-schema\\.md.*\\)"` from `must_haves.key_links`.
- **`git diff --stat docs/cancellation.md`:** `1 file changed, 2 insertions(+)` — surgical addition, no existing content moved, reformatted, or rewritten.

## Decisions Made

- **Examples for §2.1 and §2.3 were lifted from real fixtures**, with `"schema_version": 1` added as the first key per D-05. For §2.2 the `event: batch_cancelled` example is a constructed snippet because no real fixture exists in the round-trip vault — labeled implicitly as an example via the surrounding prose ("Example:"). Threat T-09-04 (info disclosure) is unaffected: lifted content matches the public test fixture verbatim.
- **Relative link form `./trace-schema.md`** chosen over the absolute `docs/trace-schema.md` form because the two docs are siblings; Obsidian, GitHub, and pandoc all resolve sibling links correctly.
- **No `Trust Boundaries` section** in this summary because the plan's threat_model declares "no new code, no untrusted input handling, no new attack surface" — both T-09-04 (accept) and T-09-05 (mitigate, locked in plan 09-01's unit tests) are satisfied.

## Deviations from Plan

None — plan executed exactly as written. No Rule 1/2/3 auto-fixes were needed, no checkpoints raised, no architectural decisions required.

## Authentication Gates

None encountered. This plan is documentation-only — no Bedrock calls, no AWS credentials, no MCP transports involved.

## Verification Results

All five `<verify>` automated checks in Task 1 pass:

```
test -f docs/trace-schema.md                                                        # PASS
grep -c "schema_version" docs/trace-schema.md | awk '{exit ($1>=5)?0:1}'           # PASS (31 ≥ 5)
grep -q "batch_cancelled" && grep -q "query_summary" && grep -q "cancellation.md"  # PASS
grep -c '^```json' docs/trace-schema.md | awk '{exit ($1>=3)?0:1}'                 # PASS (6 ≥ 3)
wc -l docs/trace-schema.md | awk '{exit ($1>=120 && $1<=320)?0:1}'                 # PASS (319 in [120,320])
```

Both `<verify>` checks in Task 2 pass:

```
grep -q "trace-schema.md" docs/cancellation.md                                     # PASS
git diff --stat docs/cancellation.md | grep -E "1 file changed, [1-3] insertion"   # PASS (2 insertions)
```

## Known Stubs

None. This plan ships only documentation; there is no code path that could carry a placeholder.

## Self-Check: PASSED

- `docs/trace-schema.md` exists: FOUND
- `docs/cancellation.md` modified: FOUND (`trace-schema.md` substring present)
- Commit `62389b5` exists: FOUND
- Commit `52d98cf` exists: FOUND
