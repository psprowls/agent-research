# Phase 35: Wiki & Bootstrap Hygiene Burn-Down - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md — this log preserves the alternatives considered.

**Date:** 2026-05-26
**Phase:** 35-wiki-bootstrap-hygiene-burn-down
**Areas discussed:** Plan grouping & merge sequencing, Wiki-bootstrap verification approach, HYGIENE-13 closure evidence, Container template handling (HYGIENE-03)

---

## Plan grouping & merge sequencing

| Option | Description | Selected |
|--------|-------------|----------|
| Themed plans (3-4 plans) | Group by file domain: templates / workspace-io / bootstrap / verify-only. Each theme = one wave. | |
| One plan, atomic tasks | Single PLAN.md with 14 atomic tasks. Easiest 1:1 against REQUIREMENTS.md; one PR; largest review surface. | |
| Two plans: implement + verify | Plan A = HYGIENE-01..12 (edits). Plan B = HYGIENE-13..14 (verify-don't-implement + transcript). | ✓ |
| Let planner decide | Don't prescribe; let `/gsd:plan-phase` choose. | |

**User's choice:** Two plans: implement + verify
**Notes:** Forces verification to happen as a deliberate evidence-gathering step after edits land, rather than rubber-stamped alongside implementation tasks. Plan B does not start until Plan A merges.

---

## Wiki-bootstrap verification approach

| Option | Description | Selected |
|--------|-------------|----------|
| Automated fixture + manual smoke | Pytest fixture bootstraps tmp_path, runs scan + lint, asserts zero broken links; PLUS one-time manual `/graph-wiki:query` transcript for HYGIENE-14. | |
| Manual smoke only | Bootstrap by hand, paste output. Fast; relies on human re-running. | |
| Automated only | Just the pytest fixture across all 3 container types. Skip the manual transcript (close HYGIENE-14 with the test). | ✓ |
| Snapshot test | Syrupy snapshot of bootstrapped wiki tree + lint output. Strongest fence; highest maintenance. | |

**User's choice:** Automated only
**Notes:** A regression test that runs on every CI is strictly stronger evidence than a one-time manual transcript. Eliminates the manual-capture toil that has historically been deferred phase-to-phase. Triggered a follow-up question about HYGIENE-14's roadmap wording (next section).

---

## HYGIENE-14 closure under automated-only verification

| Option | Description | Selected |
|--------|-------------|----------|
| Redefine: test = transcript | Treat the automated bootstrap+scan+lint test as HYGIENE-14's regression artifact; note supersession in DISCUSSION-LOG. | ✓ |
| Still capture manual transcript | Test as primary; also run `/graph-wiki:query` once at phase close and commit transcript. ~10 min of manual work. | |
| Defer manual transcript to Phase 39 | Phase 39 SC#3 already permits "or confirmed already captured from Phase 35"; punt manual capture to Phase 39. | |

**User's choice:** Redefine: test = transcript
**Notes:** Roadmap's HYGIENE-14 wording is explicitly superseded — the automated test from D-02 IS the regression artifact. Phase 39 SC#3's "or confirmed already captured from Phase 35" wording still holds: Phase 39 can reference this test rather than re-running a smoke.

---

## HYGIENE-13 closure evidence

| Option | Description | Selected |
|--------|-------------|----------|
| Verify + add regression guard | Run tests, paste output, AND add comment in `test_cli_help.py` linking to `260521-ans` explaining `NO_COLOR=1 TERM=dumb COLUMNS=200` is load-bearing. | ✓ |
| Verify only | Run tests, paste output, close. Trust existing tests as the guard. | |
| Verify + extract helper | Run tests + extract env-injection into a named pytest fixture. More refactor; reusable if other CLI tests need it. | |

**User's choice:** Verify + add regression guard
**Notes:** A future maintainer refactoring test setup needs to see WHY the env injection exists. Cheapest insurance against silent regression. Does not extract a fixture or refactor — comment only.

---

## Container template handling (HYGIENE-03)

| Option | Description | Selected |
|--------|-------------|----------|
| Hardcoded mapping in scanner | Scanner has a dict `{packages: packages, agents: agents, plugins: plugins}`. Simple; new types = scanner edit. | |
| Derive from filesystem path | Scanner infers `CONTAINER_DIR` from first path segment of discovered container. Zero config; new types just work. | ✓ |
| Workspace manifest entry | Container dirs explicit in manifest (`plugins[].container_dirs`). Highest ceremony; per-workspace override. | |
| Constant in wiki-io | `CONTAINER_DIRS` constant in wiki-io as single source of truth; scanner + renderer both read from it. | |

**User's choice:** Derive from filesystem path
**Notes:** Matches the scanner's existing discovery model (scanner already knows where it found each container). Surgical — no new constant, no manifest schema change, no scanner dict.

---

## Claude's Discretion

- Exact test name and file path for the automated bootstrap fixture from D-02
- Per-task ordering within Plan A (templates / workspace-io / bootstrap are independent)
- Implementation approach for HYGIENE-09 "test from a tmp working directory" (tmp_path vs real CLI invocation)

## Deferred Ideas

- `CONTAINER_DIRS` single-source-of-truth constant in wiki-io (revisit if a future phase needs to enumerate container dirs outside the scanner)
- Workspace-manifest-driven container dirs (revisit if/when per-workspace customization is needed)
- One-time manual `/graph-wiki:query` smoke transcript (capture as freestanding artifact for a v1.7 release if desired; NOT as HYGIENE-14 closure)
- Extracting `NO_COLOR/TERM/COLUMNS` into a pytest fixture (revisit if other CLI test files need the same env injection)
