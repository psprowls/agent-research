---
phase: 28-schema-v2-uri-foundation
plan: 02
subsystem: graph-io
tags: [uri, schema-v2, foundation, leaf-module]
requires: []
provides:
  - graph_io.uri.RepoContext
  - graph_io.uri.repo_uri
  - graph_io.uri.pkg_uri
  - graph_io.uri.subpkg_uri
  - graph_io.uri.file_uri
  - graph_io.uri.entry_point_uri
  - graph_io.uri.test_suite_uri
  - graph_io.uri.domain_uri
  - graph_io.uri.parse_remote_url
affects: []
tech_stack:
  added: []
  patterns:
    - frozen-dataclass-as-context-carrier
    - module-scope-compiled-regex
    - leaf-module-discipline
key_files:
  created:
    - packages/graph-io/src/graph_io/uri.py
    - packages/graph-io/tests/test_uri.py
  modified: []
decisions:
  - "Implementation honors CONTEXT.md D-07: pkg_uri signature is (ctx: RepoContext, name: str), NOT the 3-arg (org, repo, name) form shown in ROADMAP Success Criterion #3. D-07 is the lock; ROADMAP smoke command is stale."
  - "parse_remote_url HTTPS regex uses [^/]+? for the repo group (NOT .+?) so multi-segment GitLab subgroup paths fall through to None — D-03 lock."
  - "test_suite_uri is imported under alias _test_suite_uri in test_uri.py because its name starts with test_ and pytest would otherwise collect the helper itself as a test function (Rule 1 fix)."
metrics:
  duration: "~10 minutes"
  completed: "2026-05-25"
  tasks: 2
  files_created: 2
  files_modified: 0
---

# Phase 28 Plan 02: URI Composition Surface Summary

Ships `graph_io.uri` — a frozen `RepoContext` dataclass plus all 7 URI helpers and `parse_remote_url` — as a leaf module with full unit coverage, locking the URI shape Phases 29-31 will consume.

## What Was Built

- **`packages/graph-io/src/graph_io/uri.py`** (54 lines) — Frozen `RepoContext(org, repo)` dataclass, the 7 D-07-locked helpers (`repo_uri`, `pkg_uri`, `subpkg_uri`, `file_uri`, `entry_point_uri`, `test_suite_uri`, `domain_uri`), and `parse_remote_url` for git remote → `(org, repo)` extraction. Stdlib-only (`dataclasses`, `re`); zero graph-io-internal imports.
- **`packages/graph-io/tests/test_uri.py`** (79 lines, 9 test functions, 17 collected cases) — Full unit coverage per D-08: every helper, the `RepoContext` frozen+hashable invariant, the dotted-vs-slash discipline lock for `subpkg_uri`, and parametrized coverage of all `parse_remote_url` shapes (SSH+HTTPS with/without `.git`, trailing slash, GitLab subgroup → None, garbage → None).

## ROADMAP vs CONTEXT.md Discrepancy (called out per <output>)

**ROADMAP Success Criterion #3** shows the smoke command:

```bash
python -c "from graph_io.uri import pkg_uri; print(pkg_uri('org','repo','name'))"
```

This is the **3-arg form** `pkg_uri(org, repo, name)`. CONTEXT.md **D-07 locks** the signature as `pkg_uri(ctx: RepoContext, name: str)` — a **2-arg form** taking a `RepoContext` carrier.

**Implementation honors CONTEXT.md D-07.** The locked decision is the source of truth; ROADMAP's smoke command is stale (predates the D-06 RepoContext carrier decision). The adapted smoke command — also documented in the plan's `must_haves.truths` — is:

```bash
uv run --package graph-io python -c "from graph_io.uri import RepoContext, pkg_uri; print(pkg_uri(RepoContext('org','repo'), 'name'))"
```

Output: `pkg:org/repo/name`. Verified.

## Verification

```
$ uv run --package graph-io pytest packages/graph-io/tests/test_uri.py -x
======================== 17 passed in 0.01s ========================
```

All acceptance criteria satisfied:
- `@dataclass(frozen=True)` decorator present
- `def domain_uri(name` (no ctx) signature present
- `def pkg_uri(ctx` signature present
- `def parse_remote_url` signature present
- Smoke import command exits 0
- `RepoContext` is dataclass + hashable
- `def test_` count = 9 (≥9 required)
- Collected case count = 17 (≥13 required)
- `graph_io.cli` token present (dotted-path lock test)

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] `test_suite_uri` collides with pytest test-function name prefix**
- **Found during:** Task 2 (running the expanded test file)
- **Issue:** Pytest collected the imported `test_suite_uri` helper from `graph_io.uri` as a test function inside `test_uri.py`, attempting to inject a fixture named `ctx` and failing setup. Renaming the helper is not an option — D-07 locks the name.
- **Fix:** Import the helper under an alias: `from graph_io.uri import test_suite_uri as _test_suite_uri`. The dedicated test function `test_test_suite_uri` then calls `_test_suite_uri(...)`. The alias is module-private (leading underscore) so pytest skips it during collection.
- **Files modified:** `packages/graph-io/tests/test_uri.py`
- **Commit:** `b0cbdf9`

No other deviations. No architectural changes. No authentication gates.

## Known Stubs

None. Every exported symbol is fully implemented and tested.

## Threat Surface Scan

No new surface introduced beyond the plan's `<threat_model>`. `parse_remote_url` is the only externally-fed function; both regexes use bounded character classes with no nested quantifiers (mitigates `T-28-02-01` ReDoS per plan). No network, no filesystem, no subprocess.

## Self-Check: PASSED

- FOUND: `packages/graph-io/src/graph_io/uri.py`
- FOUND: `packages/graph-io/tests/test_uri.py`
- FOUND commit: `76442b4` (test RED)
- FOUND commit: `ae051af` (feat GREEN)
- FOUND commit: `b0cbdf9` (test expanded)

## TDD Gate Compliance

- RED commit: `76442b4` — `test(28-02): add failing smoke test for graph_io.uri module`
- GREEN commit: `ae051af` — `feat(28-02): implement graph_io.uri with RepoContext + 7 helpers + parse_remote_url`
- REFACTOR: not needed (implementation was minimal from inception)
- All three gates land in the expected order.
