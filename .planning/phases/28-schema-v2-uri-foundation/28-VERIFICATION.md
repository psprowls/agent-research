---
phase: 28
verified: 2026-05-25T00:00:00Z
re_verified: 2026-05-25T19:30:00Z
status: passed
score: 5/5 must-haves verified
requirements_covered: SCHEMA-01, SCHEMA-02, SCHEMA-03, SCHEMA-04, SCHEMA-05
test_count: 143
test_failures: 0
overrides_applied: 0
re_verification:
  previous_status: gaps_found
  previous_score: 4/5
  gaps_closed:
    - "URI composition is fully unit-tested before any emitter is built (SC#3 + D-03 + D-08) — CR-01 / IN-02 closed by commit 162c089"
  gaps_remaining: []
  regressions: []
---

# Phase 28: Schema v2 + URI Foundation Verification Report

**Phase Goal:** The `graph-io` store speaks schema v2 — every new emitter has a `uri` column to write to, schema mismatches exit cleanly with code 4, and URI composition is tested before any emitter is built.

**Verified:** 2026-05-25 (initial)
**Re-verified:** 2026-05-25 (after CR-01 fix in commit `162c089`)
**Status:** passed
**Score:** 5/5 must-haves verified
**Re-verification:** Yes — gap CR-01 closed; all SCs now PASS

## Goal Achievement

### Success-Criteria Checklist (ROADMAP contract)

| # | Success Criterion | Status | Evidence |
|---|-------------------|--------|----------|
| 1 | `cg update --full` against schema-v1 detects mismatch, rebuilds at v2, exits 0 | VERIFIED | `update.py:211-219` probes schema_version pre-connect; under `--full` prints `"Schema v1 detected — rebuilding code.db at schema v2."` to stderr (line 215-218) and calls `_unlink_db_files(db_path)` (line 219). Verified by `test_store.py::test_update_full_rebuilds_v1_db_to_v2` (lines 112-142) — passes |
| 2 | Non-`--full` commands exit with code 4 + friendly stderr message on a v1 DB | VERIFIED | `update.py:220-221` raises `store.SchemaMismatchError(found=found, expected=schema.SCHEMA_VERSION)` on non-`--full` path; `cli/ops_update.py:24-26` catches it and returns `exit_codes.SCHEMA_MISMATCH` (= 4). Verified by `test_cli_exit_codes.py::test_cg_update_on_v1_db_exits_schema_mismatch` and `::test_exit_4_schema_mismatch` (11 subcommand check) |
| 3 | `graph_io/uri.py` ships with RepoContext + 7 helpers + parse_remote_url, fully unit-tested | **VERIFIED** | All 7 helpers + RepoContext present (`uri.py:9-54`); **19 collected parse_remote_url cases (was 17). CR-01 closed by commit `162c089`: `uri.py:43` SSH regex tightened from `(.+?)` to `([^/]+?)` (mirrors HTTPS branch). IN-02 closed by `test_uri.py:78-79` adding two SSH subgroup → None cases. Live re-check: `parse_remote_url('git@gitlab.com:group/sub/repo.git')` now returns `None`** |
| 4 | After `cg update --full`, every Package node has a non-NULL `uri` column derived from `pkg_uri(ctx, name)` | VERIFIED | `packages.py:124`: `"uri": pkg_uri(ctx, info["name"])` in the Package node attrs dict. `_upsert_node` (upsert.py:48-59) pops uri and writes to column. Verified by `test_packages.py::test_refresh_writes_pkg_uri_on_package_nodes` |
| 5 | `_upsert_node` writes URI to the dedicated `uri` column, NOT into `attrs_json` (PITFALL 4 locked) | VERIFIED | `upsert.py:50-51` copies attrs and pops uri BEFORE serialize; INSERT (line 42) and UPDATE (line 55) SQL both write the dedicated `uri` column. D-12 sentinel `test_upsert.py::test_upsert_uri_lands_in_column` (line 107) verifies absence from attrs_json |

**Score:** 5/5 — all ROADMAP success criteria PASS.

### Observable Truths

| # | Truth | Status | Evidence |
|---|-------|--------|----------|
| 1 | `SCHEMA_VERSION = 2` and nodes table has `uri TEXT` column with `idx_nodes_uri` index | VERIFIED | `schema.py:12, 23, 28` — all three present; no UNIQUE constraint |
| 2 | `apply_schema` is idempotent at v2 | VERIFIED | `schema.py:54-61` uses `INSERT ... ON CONFLICT(key) DO UPDATE`; `test_schema.py::test_apply_schema_is_idempotent` passes |
| 3 | `_upsert_node` pops uri from a COPY of attrs (does not mutate caller's dict) | VERIFIED | `upsert.py:50` `attrs_for_json = dict(node.attrs)` before pop |
| 4 | `cg update` (incremental) on v1 DB exits 4 with `cg update --full` in stderr, no traceback | VERIFIED | `test_cli_exit_codes.py::test_cg_update_on_v1_db_exits_schema_mismatch` |
| 5 | `cg find` (and other read commands) on v1 DB still exit 4 (regression preserved) | VERIFIED | `test_cli_exit_codes.py::test_exit_4_schema_mismatch` covers 11 subcommands |
| 6 | `cg update --full` on v1 DB exits 0 (Plan-04 xfail removed) | VERIFIED | `test_cli_exit_codes.py::test_cg_update_full_on_v1_db_does_not_exit_4_from_ops_update_handler` (line 192-203) — no xfail decorator; `grep xfail` returns 0 matches |
| 7 | `update.run` derives RepoContext once and threads it to `packages.refresh` | VERIFIED | `update.py:207` derives ctx; `update.py:236` `packages.refresh(conn, repo_root=repo_root, ctx=ctx)` |
| 8 | `packages.refresh` writes `pkg_uri(ctx, name)` on every Package node | VERIFIED | `packages.py:124` |
| 9 | `parse_remote_url` correctly rejects HTTPS GitLab subgroups, git://, file://, garbage | VERIFIED | `test_uri.py:77` (HTTPS subgroup); `:80-82` (git://, file://, garbage) — all green |
| 10 | `parse_remote_url` correctly rejects SSH GitLab subgroups per D-03 | **VERIFIED** | **CR-01 closed by `162c089`. `uri.py:43` now `^git@[^:]+:([^/]+)/([^/]+?)(?:\.git)?$`. Live re-check `parse_remote_url('git@gitlab.com:group/sub/repo.git')` → `None`. Locked by `test_uri.py:78-79`: `("git@gitlab.com:group/subgroup/repo.git", None)` and `("git@gitlab.com:group/subgroup/repo", None)`** |
| 11 | `cg update --full` is idempotent (SCHEMA-05) | VERIFIED (with documented deviation) | Structural equivalence proven by `test_update_full_twice_produces_byte_identical_db`. **Documented deviation:** ROADMAP SC#4 wording says "byte-identical" but implementation asserts structural equivalence due to intentional `last_indexed_at` wall-clock metadata write. Plan 05 SUMMARY documents this as the semantically-meaningful invariant SCHEMA-05 cares about — accepted as documented |

### Required Artifacts

| Artifact | Expected | Status | Details |
|----------|----------|--------|---------|
| `packages/graph-io/src/graph_io/schema.py` | SCHEMA_VERSION=2, uri column, idx_nodes_uri | VERIFIED | All present (lines 12, 23, 28) |
| `packages/graph-io/src/graph_io/uri.py` | RepoContext + 7 helpers + parse_remote_url | VERIFIED | All 9 exports present; SSH regex bounded to single-segment repo (line 43) per D-03 |
| `packages/graph-io/src/graph_io/upsert.py` | Uri column write path | VERIFIED | dict-copy + pop + column write on INSERT & UPDATE |
| `packages/graph-io/src/graph_io/update.py` | v1→v2 unlink+rebuild + ctx derivation + threading | VERIFIED | 3 new helpers, all wired |
| `packages/graph-io/src/graph_io/packages.py` | refresh accepts ctx; writes pkg_uri | VERIFIED | Required `ctx: RepoContext` kw arg, pkg_uri in attrs |
| `packages/graph-io/src/graph_io/cli/ops_update.py` | SchemaMismatchError handler before generic Exception | VERIFIED | Handler positioned at lines 24-26, before line 27 Exception catch |
| `packages/graph-io/tests/test_uri.py` | Full helper + parse_remote_url coverage including SSH subgroup negatives | VERIFIED | 19 parametrize cases (was 17); SSH subgroup negatives at lines 78-79 |
| `packages/graph-io/tests/test_schema.py` | D-12 sentinels #1 + #2 | VERIFIED | `test_schema_version_is_two` (line 58); `test_nodes_table_has_uri_column` (line 62) |
| `packages/graph-io/tests/test_upsert.py` | D-12 sentinel #3 | VERIFIED | `test_upsert_uri_lands_in_column` (line 107) |
| `packages/graph-io/tests/test_store.py` | v1→v2 rebuild test | VERIFIED | `test_update_full_rebuilds_v1_db_to_v2` + `test_update_incremental_on_v1_db_raises_schema_mismatch` |
| `packages/graph-io/tests/test_update_idempotent.py` | Idempotency proof for SCHEMA-05 | VERIFIED (structural, not byte) | `test_update_full_twice_produces_byte_identical_db` |
| `packages/graph-io/tests/test_cli_exit_codes.py` | cg update + cg find on v1 → exit 4; --full → 0 | VERIFIED | All three Plan-04 tests + Plan-05 xfail removal |

### Key Link Verification

| From | To | Via | Status | Details |
|------|----|----|--------|---------|
| `update.run` | `packages.refresh` | `ctx=ctx` keyword | WIRED | `update.py:236`: `packages.refresh(conn, repo_root=repo_root, ctx=ctx)` |
| `packages.refresh` | `pkg_uri` | call in node construction | WIRED | `packages.py:124`: `"uri": pkg_uri(ctx, info["name"])` |
| `update.run` | `(org, repo)` | `parse_remote_url(_git(['remote','get-url','origin']))` | WIRED | `update.py:141-157` `_derive_repo_context` → `update.py:207`; SSH branch now D-03-compliant |
| `_upsert_node` | `nodes.uri` column | pop attrs → INSERT/UPDATE | WIRED | `upsert.py:50-59` |
| `ops_update.run` | `exit_codes.SCHEMA_MISMATCH` | `except store.SchemaMismatchError` | WIRED | `cli/ops_update.py:24-26`, positioned before generic Exception |
| `update.run` | `store.SchemaMismatchError(found=, expected=)` | raised on non-`--full` v1 | WIRED | `update.py:220-221`; kwargs verified against `store.py:20` |

### Data-Flow Trace (Level 4)

| Artifact | Data Variable | Source | Produces Real Data | Status |
|----------|--------------|--------|--------------------|--------|
| Package node `uri` column | `attrs["uri"]` | `pkg_uri(ctx, info["name"])` where `ctx` derives from real `git remote get-url origin` (or `local/<repo_root.name>` fallback) | YES — real (org, repo) for the agent-research repo; falls back to local sentinel correctly; SSH-subgroup remotes now correctly fall through to the local sentinel | FLOWING |
| Schema-version probe value | `found` | `_read_schema_version_or_none(db_path)` reads real `metadata.schema_version` via read-only sqlite URI | YES — verified by `_seed_v1_db` sanity assert (test_store.py:104-108) | FLOWING |

### Behavioral Spot-Checks

| Behavior | Command | Result | Status |
|----------|---------|--------|--------|
| All helpers import + pkg_uri composes | `uv run --package graph-io python -c "from graph_io.uri import RepoContext, pkg_uri; print(pkg_uri(RepoContext('org','repo'), 'name'))"` | `pkg:org/repo/name` | PASS |
| Full graph-io test suite | `uv run --package graph-io pytest packages/graph-io/tests/` | **143 passed in 9.73s** | PASS |
| CR-01 closed (SSH subgroup → None) | `uv run --package graph-io python -c "from graph_io.uri import parse_remote_url; print(parse_remote_url('git@gitlab.com:group/sub/repo.git'))"` | `None` (was `('group', 'sub/repo')` before fix) | **PASS — D-03 honored** |
| CR-01 closed (no-suffix variant) | `... parse_remote_url('git@gitlab.com:group/sub/repo'))` | `None` | **PASS** |
| No regression on canonical SSH | `... parse_remote_url('git@github.com:pat/agent-research.git'))` | `('pat', 'agent-research')` | PASS |
| D-12 sentinel #1 | `pytest test_schema.py::test_schema_version_is_two` | passes | PASS |
| D-12 sentinel #2 | `pytest test_schema.py::test_nodes_table_has_uri_column` | passes | PASS |
| D-12 sentinel #3 | `pytest test_upsert.py::test_upsert_uri_lands_in_column` | passes | PASS |
| xfail marker removed | `grep -n xfail packages/graph-io/tests/test_cli_exit_codes.py` | no matches | PASS |

### Probe Execution

| Probe | Command | Result | Status |
|-------|---------|--------|--------|
| No conventional `scripts/*/tests/probe-*.sh` declared | — | N/A | SKIPPED (no probe scripts referenced by PLAN/SUMMARY) |

### Requirements Coverage

| Requirement | Source Plan | Description | Status | Evidence |
|-------------|-------------|-------------|--------|----------|
| SCHEMA-01 | 28-01, 28-05 | `cg update --full` on v1 upgrades to v2, rebuilds nodes+edges with URIs populated | SATISFIED | schema.py v2 DDL + update.py unlink+rebuild + packages.refresh writes pkg_uri |
| SCHEMA-02 | 28-04 | `cg update` (incremental) on v1.5 raises SCHEMA_MISMATCH (exit 4) with `cg update --full` instruction | SATISFIED | update.py:220-221 raises; ops_update.py:24-26 routes; test_cli_exit_codes.py covers |
| SCHEMA-03 | 28-02 | `graph_io.uri` exposes 7 composition helpers + stable URI shapes | **SATISFIED** | All helpers ship; URI shapes correct; **parse_remote_url SSH branch now honors D-03 (CR-01 closed by `162c089`)** |
| SCHEMA-04 | 28-01, 28-03 | URIs persisted on dedicated `uri TEXT` column (not in attrs_json); nullable | SATISFIED | schema.py:23 + upsert.py pop-and-bind to column; test_upsert.py D-12 sentinel |
| SCHEMA-05 | 28-05 | `cg update --full` is idempotent — twice on same git state → byte-identical code.db | SATISFIED (with documented deviation) | Structural equivalence asserted; byte-identity precluded by intentional `last_indexed_at` metadata write — Plan 05 SUMMARY documents the decision and justifies structural equality as the semantic invariant |

**No orphaned requirements.** All five SCHEMA-* requirements are claimed by plans in this phase, and all are addressed in code.

### Anti-Patterns Found

Re-scanned all 6 modified source files plus 6 test files (including post-fix `uri.py` and `test_uri.py`). Results:

| File | Line | Pattern | Severity | Impact |
|------|------|---------|----------|--------|
| (none) | — | TBD/FIXME/XXX/TODO/HACK/PLACEHOLDER | — | Zero debt markers in any Phase 28 file (including post-fix files) |

**Plan-05 known deviations (acknowledged in 28-05-SUMMARY.md), unchanged from initial verification:**
- Structural-equivalence test for SCHEMA-05 byte-identity (Info — documented decision; accepted as documented deviation)
- `LATTICE_GRAPH_LOCK_TIMEOUT_MS` untouched (Info — explicitly Phase 34 scope)
- T-28-05-03 concurrent --full race accepted as residual risk (Info)

**Code-review findings inherited from 28-REVIEW.md, updated dispositions:**

| ID | Severity | File:Line | Disposition after re-verification |
|----|----------|-----------|------------------------------------|
| CR-01 | BLOCKER | `uri.py:43` | **CLOSED** — fix landed in commit `162c089`; SSH regex bounded to single-segment repo; SC#3 now PASS |
| IN-02 | Info | `test_uri.py` parametrize | **CLOSED** — two SSH subgroup negative cases added (lines 78-79); 19 cases collected |
| WR-01 | Warning | `update.py:188-190` | Open advisory — latent (no caller currently passes non-`code.db` path); flag for next phase |
| WR-02 | Warning | `update.py:149-152` | Open advisory — latent (missing `git` binary edge case); D-04 says "any failure" — actual catch narrower |
| WR-03 | Warning | `test_store.py:95-109` | Open advisory — test fixture seeds v2-shape DDL with v1 metadata; adequate for current unlink+rebuild strategy but not for hypothetical in-place migration tests |
| IN-01 | Info | `test_cli_exit_codes.py:152-156` | Open advisory — stale docstring (Plan-05 has shipped the real probe); test still valid as CLI-handler unit test |

### Gaps Summary

**No gaps remaining.** All five ROADMAP success criteria PASS:
- The CR-01 blocker (D-03 violation in SSH regex) is closed by `162c089` — verified live and via the new parametrize cases.
- IN-02 (missing SSH subgroup parametrize) is closed by the two cases added at `test_uri.py:78-79`.
- SC#5 byte-identity deviation remains as an acknowledged, documented design decision in `28-05-SUMMARY.md`; structural equivalence is the semantic invariant SCHEMA-05 cares about. Accepted.

### Follow-Up (Advisory — NOT blocking Phase 29)

Carry these forward into the next phase's planning context:

- **WR-01**: Derive WAL/SHM sibling names from `db_path.name` in `_unlink_db_files` (defensive — current sole caller is safe).
- **WR-02**: Broaden `_derive_repo_context` catch to `(NotInGitRepoError, FileNotFoundError)` per D-04's "any failure" wording.
- **WR-03**: Tighten `test_store.py:95-109` fixture docstring to reflect that it seeds v2-shape DDL with v1 metadata for the unlink+rebuild path (not in-place migration).
- **IN-01**: Refresh stale docstring in `test_cli_exit_codes.py:152-156` to acknowledge that the real Plan-05 probe has shipped; this test remains a valid CLI-handler unit.

### Test Summary

```
uv run --package graph-io pytest packages/graph-io/tests/
============================= 143 passed in 9.73s ==============================
```

| Test File | Tests Passing |
|-----------|---------------|
| test_cli_exit_codes.py | 10 (including 3 Plan-04 additions + 1 Plan-05 xfail removal) |
| test_packages.py | 8 (includes new `test_refresh_writes_pkg_uri_on_package_nodes`) |
| test_schema.py | 6 (includes D-12 sentinels #1, #2) |
| test_store.py | 8 (includes Plan-05 `test_update_full_rebuilds_v1_db_to_v2` + `test_update_incremental_on_v1_db_raises_schema_mismatch`) |
| test_update_idempotent.py | 2 (includes Plan-05 `test_update_full_twice_produces_byte_identical_db`) |
| test_upsert.py | 8 (includes D-12 sentinel #3 + 2 regression guards) |
| test_uri.py | **19 parametrize cases + 8 single-helper tests** (was 17 parametrize cases pre-fix; +2 SSH subgroup negatives at lines 78-79) |
| (other unchanged files) | 82 |
| **Total** | **143 passed, 0 failed, 0 xfailed** (was 141 pre-fix) |

---

## Resolution Log

| Timestamp | Event |
|-----------|-------|
| 2026-05-25 (initial) | Verification ran on Phase 28 SUMMARYs and codebase. 4/5 SCs PASS; SC#3 PARTIAL due to CR-01 (SSH regex accepts GitLab subgroups, violating D-03). Status: `gaps_found`. |
| 2026-05-25 (fix) | Inline fix landed as commit `162c089` — `fix(28-CR-01): bound SSH remote regex to single-segment repo (D-03)`. Two-line change to `uri.py:43` (regex tightened to `([^/]+?)`) + two new parametrize cases at `test_uri.py:78-79` for SSH subgroup → None contract. |
| 2026-05-25 (re-verify) | Re-verification confirmed: live `parse_remote_url('git@gitlab.com:group/sub/repo.git')` returns `None`; canonical `git@github.com:pat/agent-research.git` still parses correctly; full suite is **143 passed, 0 failed** (was 141 + 2 new cases). SC#3 promoted to PASS. CR-01 and IN-02 closed. No regressions. Status: `passed`. |

_Verified: 2026-05-25_
_Re-verified: 2026-05-25 (post-fix)_
_Verifier: Claude (gsd-verifier)_
