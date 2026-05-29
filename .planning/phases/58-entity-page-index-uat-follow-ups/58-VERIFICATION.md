---
phase: 58-entity-page-index-uat-follow-ups
verified: 2026-05-28T00:00:00Z
status: human_needed
score: 3/3 must-haves verified
overrides_applied: 0
human_verification:
  - test: "Open a regenerated entity page in Obsidian and confirm the summary: bullet renders inline (not as a blockquote) and the ## Related section shows as plain prose text"
    expected: "Both items render as ordinary Markdown prose — no blockquote, no broken angle-bracket fragments"
    why_human: "True Obsidian rendering fidelity is a runtime concern; automated tests assert the string constraints (no >/</: characters) that are the root cause, not visual pixels"
---

# Phase 58: Entity Page & Index UAT Follow-Ups Verification Report

**Phase Goal:** The three wiki-io defects/enhancements surfaced during v1.10 UAT (Phases 56-57) are resolved — entity `## Related` sections show a clean Obsidian-safe fill-me-in marker (dynamic population from curated backlinks deferred per CONTEXT D-01), summary placeholders render cleanly in Obsidian, and each package nests only the test suites that actually test it (resolution keys on test_suite node id/uri rather than the shared `name`).
**Verified:** 2026-05-28
**Status:** human_needed (all automated checks pass; one Obsidian visual render check deferred to human)
**Re-verification:** No — initial verification

---

## Goal Achievement

### Observable Truths

| # | Truth | Status | Evidence |
|---|-------|--------|----------|
| 1 | Generated entity pages contain no `<...>` placeholder links in `## Related`; the section shows a clean Obsidian-safe marker naming concepts/ADRs/architecture | VERIFIED | All three templates (`entity-package.md:37`, `entity-app.md:43`, `entity-plugin.md:25`) contain `No related concept, ADR, or architecture pages yet.` — no `<`, no `>`, no `:` on the Related body line |
| 2 | The empty-description `summary:` placeholder has no leading `>`, no `<...>`, no `:` | VERIFIED | `entity_writer.py:587` reads `fm["summary"] = description or f"TODO add a one-line summary for {node.name}"` — confirmed clean; test assertion at `test_entity_writer.py:482` updated to `"TODO add a one-line summary for x"`; 44 entity_writer tests pass |
| 3 | In the generated index `## By Kind`, each package nests only its own test suite(s); resolution keys on `test_suite` node URI; no two test_suite nodes share a name | VERIFIED | `index_generator.py` has 0 `ts.name = ?` and 3 `ts.uri = ?`; `_place_entities` passes `entity_uri=uri` to `_consumer_pkgs`; `test_suites.py` emits `f"{r.owner_name}-{kind_attr}-tests"` at all 4 mutation points; SC#3b uniqueness guard and fan-out regression guard both pass; 842 wiki-io + graph-io tests pass |

**Score:** 3/3 truths verified

---

### Required Artifacts

| Artifact | Expected | Status | Details |
|----------|----------|--------|---------|
| `packages/wiki-io/src/wiki_io/assets/page-templates/entity-package.md` | Clean `## Related` marker | VERIFIED | Line 37: `No related concept, ADR, or architecture pages yet.` |
| `packages/wiki-io/src/wiki_io/assets/page-templates/entity-app.md` | Clean `## Related` marker | VERIFIED | Line 43: same clean marker |
| `packages/wiki-io/src/wiki_io/assets/page-templates/entity-plugin.md` | Clean `## Related` marker | VERIFIED | Line 25: same clean marker |
| `packages/wiki-io/src/wiki_io/entity_writer.py` | Obsidian-safe summary placeholder | VERIFIED | Line 587: `f"TODO add a one-line summary for {node.name}"` — no `/>/</:`; tests green |
| `packages/wiki-io/src/wiki_io/index_generator.py` | URI-keyed consumer resolution in all three queries | VERIFIED | `grep -c 'ts.uri = ?'` returns 3; `grep 'ts.name = ?'` returns nothing |
| `packages/graph-io/src/graph_io/test_suites.py` | Package-qualified suite naming at all four mutation points | VERIFIED | Lines 342, 391, 454 use `f"{r.owner_name}-{kind_attr}-tests"`; no `Path(r.rel_path).name` remains for package-owned suites |

---

### Key Link Verification

| From | To | Via | Status | Details |
|------|----|-----|--------|---------|
| `entity_writer.py:587` | `fm['summary']` placeholder | f-string assignment when description empty | WIRED | `fm["summary"] = description or f"TODO add a one-line summary for {node.name}"` — correct production path |
| `_place_entities` | `_consumer_pkgs(entity_uri=uri)` | `uri = node.attrs.get("uri") or ""` at line 369 | WIRED | `_place_entities:380-381` passes `entity_uri=uri` for `kind == "test_suite"` |
| `_place_entities` | `_compute_qualifying_domains(uri=uri)` | same `uri` variable | WIRED | Line 371 passes `uri=uri` |
| `test_suites.py emit` → `physically_contains edge dst` → `re-parent DB lookup` → `_emit_tests_edges` | Consistent qualified suite name | `f"{r.owner_name}-{kind_attr}-tests"` | WIRED | All four mutation points confirmed; test_test_suites.py: 22 tests pass |

---

### Data-Flow Trace (Level 4)

| Artifact | Data Variable | Source | Produces Real Data | Status |
|----------|---------------|--------|--------------------|--------|
| `entity_writer.py` summary | `fm["summary"]` | `node.attrs.get("description")` or fallback f-string | Yes — either real description or clean TODO marker; never empty | FLOWING |
| `index_generator.py` consumer resolution | `parent_pkgs` | `_consumer_pkgs(conn, kind=kind, entity_uri=uri)` → SQL `ts.uri = ?` → `tests` edges in DB | Yes — queries live DB via `ts.uri` parameter (unique stable key); no static empty return | FLOWING |
| `test_suites.py` suite name | `suite_name` | `f"{r.owner_name}-{kind_attr}-tests"` from `r.owner_name` (real package name) + `_classify_suite_kind(r.rel_path, ...)` | Yes — derived from real filesystem paths; no static fallback | FLOWING |

---

### Behavioral Spot-Checks

| Behavior | Command | Result | Status |
|----------|---------|--------|--------|
| entity_writer tests pass with new summary placeholder | `uv run --package wiki-io pytest packages/wiki-io/tests/test_entity_writer.py -x -q` | 44 passed in 1.37s | PASS |
| index_generator tests pass with URI-keyed resolution | `uv run --package wiki-io pytest packages/wiki-io/tests/test_index_generator.py -x -q` | 54 passed, 1 skipped (no live graph) in 0.20s | PASS |
| test_suites uniqueness guard passes | `uv run --package graph-io pytest packages/graph-io/tests/test_test_suites.py -x -q` | 22 passed in 1.63s | PASS |
| Fan-out regression guard proves per-suite isolation | `uv run --package wiki-io pytest packages/wiki-io/tests/test_index_generator.py -x -k fanout` | Covered within the 54 passed above | PASS |
| Full cross-package suite green | `uv run pytest packages/wiki-io/tests/ packages/graph-io/tests/ -x -q` | 842 passed, 3 skipped, 2 xfailed in 83.29s | PASS |

---

### Probe Execution

No `scripts/*/tests/probe-*.sh` files declared or found for this phase.

---

### Requirements Coverage

No formal requirement IDs are mapped to phase 58 in REQUIREMENTS.md. Contract is the three ROADMAP success criteria + CONTEXT.md decisions D-01..D-10. All three success criteria verified above.

**D-01 through D-10 compliance check:**

| Decision | Status | Evidence |
|----------|--------|----------|
| D-01: Clean empty marker now; defer real population | SATISFIED | Templates have clean text marker, no graph-edge query built |
| D-02: Marker must be Obsidian-safe (no `>`, `<`, `:`) | SATISFIED | `No related concept, ADR, or architecture pages yet.` — all constraints met |
| D-03: Scope = entity templates only | SATISFIED | Only `entity-package.md`, `entity-app.md`, `entity-plugin.md` modified; `entity-test-suite.md` and `entity-dependency.md` untouched |
| D-04: Plain-text, Obsidian-safe summary marker | SATISFIED | `TODO add a one-line summary for {node.name}` — no `>`, `<`, `:` |
| D-05: Scope strictly to entity `summary:` placeholder | SATISFIED | One line changed in `entity_writer.py:587`; sibling templates not swept |
| D-06: Update test expectations for old placeholder | SATISFIED | `test_entity_writer.py:482` updated from old to new string |
| D-07: Confirmed root cause in `_consumer_pkgs` | SATISFIED | Root cause was `ts.name = ?`; fix is `ts.uri = ?` as D-08 requires |
| D-08: Fix BOTH sides (scan-side + renderer-side) | SATISFIED | `test_suites.py` (4 mutation points) + `index_generator.py` (3 queries) both fixed |
| D-09: Cascade awareness | SATISFIED | Repository-owned suites unchanged (keep `rel_path` name); all four mutation points use consistent qualified name |
| D-10: Regenerate affected goldens in-phase | PARTIALLY SATISFIED | Hand-built fixture tests rebaselined; live-graph syrupy snapshot deferred (no live graph in execution env) — documented in 58-03-SUMMARY.md as intended deferral with fan-out guard as standing proof |

---

### Anti-Patterns Found

No `TBD`, `FIXME`, or `XXX` markers found in any phase-modified file.

No empty return stubs found in production paths.

| Finding | Severity | Assessment |
|---------|----------|------------|
| WR-01 (REVIEW): Same-package dual test directories could yield duplicate suite names | WARNING (advisory) | The SC#3b guard test only seeds one dir per package; WR-02 collision is unexercised by current repo. URI-keyed index resolution is safe regardless since URIs are always unique. Known/advisory, not a phase blocker. |
| WR-02 (REVIEW): `describe_test_suite` still name-keyed (`entity_writer.py:619`) | WARNING (advisory) | This callsite was not part of the SC#3 fix scope (which was exclusively the index_generator consumer resolution queries). The REVIEW correctly notes this as the same class of fragility eliminated elsewhere, but the WR-01 dual-dir collision that would cause it to fail is unexercised. Pre-existing issue, not introduced this phase. |
| IN-02 (REVIEW): `_consumer_pkgs_in_domain` has no production caller | INFO | Pre-existing dead code; exported in `__all__` at line 915; exercised only by the fan-out regression guard. Not introduced this phase. |
| Snapshot rebaseline deferred | INFO | `test_snapshot_against_agent_research` was skipped (not failed) — no live graph in execution environment. Fan-out regression guard serves as standing automated proof per plan's acceptance criteria. |

---

### Human Verification Required

#### 1. Obsidian visual rendering of summary and Related marker

**Test:** Regenerate one or more entity pages (`cg update --full` then open a package entity page in Obsidian)
**Expected:** The `summary:` value renders inline in the index bullet (not as a blockquote fragment), and the `## Related` section shows `No related concept, ADR, or architecture pages yet.` as plain prose text — no spurious blockquote, no broken fragments
**Why human:** Obsidian rendering fidelity is a runtime concern that cannot be verified by string-constraint grep. The automated tests assert the absence of the characters that caused the original rendering breakage (`>`, `<`, `:` in the summary placeholder) and the absence of `<...>` in the Related block, but visual confirmation in Obsidian is the final proof the defect is user-visibly resolved.

---

### Gaps Summary

No blocking gaps. All three success criteria are verified in the codebase. The two REVIEW warnings (WR-01, WR-02) are advisory — they describe unexercised edge cases not triggered by the current repository shape, and both were known before phase completion.

The only open item is the Obsidian visual render check, which was explicitly listed as a manual-only verification in the VALIDATION.md and cannot be performed programmatically.

---

_Verified: 2026-05-28_
_Verifier: Claude (gsd-verifier)_
