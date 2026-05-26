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

---

## HYGIENE-13 Closure: test_cli_help.py 3/3 verified passing

**Date:** 2026-05-26
**Per:** Phase 35 CONTEXT.md D-04 — "Verify + add inline regression guard comment"

Pytest output (verbatim, captured at Plan B Task 1 verification step):

```
============================= test session starts ==============================
platform darwin -- Python 3.11.15, pytest-9.0.3, pluggy-1.6.0 -- /Users/pat/Personal/agent-research/.venv/bin/python
cachedir: .pytest_cache
rootdir: /Users/pat/Personal/agent-research/agents/graph-wiki-agent
configfile: pyproject.toml
plugins: repeat-0.9.4, rerunfailures-16.2, syrupy-5.1.0, xdist-3.8.0, harvest-1.10.5, deepeval-4.0.2, asyncio-1.3.0, langsmith-0.8.3, evals-0.3.4, anyio-4.13.0
asyncio: mode=Mode.AUTO, debug=False, asyncio_default_fixture_loop_scope=None, asyncio_default_test_loop_scope=function
collecting ... collected 3 items

agents/graph-wiki-agent/tests/unit/test_cli_help.py::test_cli_help_exits_zero PASSED [ 33%]
agents/graph-wiki-agent/tests/unit/test_cli_help.py::test_cli_help_lists_bootstrap_subcommand PASSED [ 66%]
agents/graph-wiki-agent/tests/unit/test_cli_help.py::test_cli_help_init_subcommand_removed PASSED [100%]Running teardown with pytest sessionfinish...


============================== 3 passed in 1.76s ===============================
```

Inline comment added at `agents/graph-wiki-agent/tests/unit/test_cli_help.py`
above `_PLAIN_HELP_ENV` references `260521-ans` per D-04 specifics. Future
maintainers refactoring CLI test infrastructure can grep `260521-ans` to find
the original incident context in `.planning/quick/260521-ans-typer-help-ansi-strip/`.

**Closure status:** HYGIENE-13 closed as already-resolved at Phase 35 scoping
(not re-implemented). The 260521-ans pattern (`NO_COLOR=1 TERM=dumb COLUMNS=200`)
is load-bearing infrastructure and is now documented as such inline.

---

## HYGIENE-14 Closure: D-03 supersedes manual transcript

**Date:** 2026-05-26
**Per:** Phase 35 CONTEXT.md D-02 (automated-only verification) and D-03
(HYGIENE-14 closes via the automated test).

The roadmap's original wording (Phase 35 SC#5 / Phase 14 SC#4) called for a
manual `/graph-wiki:query` plugin smoke transcript as the regression artifact.
Phase 35 scoping decision D-03 superseded this with an automated pytest
fixture that bootstraps a sandbox workspace into `tmp_path`, renders all three
container-type overview templates, runs `wiki_io.lint_wiki.scan()`, and asserts
zero broken wikilinks. Rationale (verbatim from D-03 / CONTEXT.md):

> A test that runs on every CI is strictly stronger evidence than a one-time
> manual transcript.

**Closure artifact:** `packages/wiki-io/tests/test_bootstrap_e2e_no_broken_links.py`
— exists, passes (1/1), and is the live regression fence catching any future
template / scanner / lint drift that would break
`[[wiki/<container>/...]]` link resolution.

**Impact on Phase 39 SC#3:** Phase 39's wording about "the Phase 14 SC#4
manual `/graph-wiki:query` plugin smoke transcript is captured (or confirmed
already captured from Phase 35)" is satisfied by referencing this automated
test as the captured artifact. Future Phase 39 planning can cite
`packages/wiki-io/tests/test_bootstrap_e2e_no_broken_links.py` rather than
re-running a manual smoke.

**If the user later wants a one-time human-eye smoke** (e.g. before a v1.7
release): per CONTEXT.md deferred section, capture it as a freestanding
artifact, NOT as Phase 35 HYGIENE-14 closure evidence (which is now this test).
