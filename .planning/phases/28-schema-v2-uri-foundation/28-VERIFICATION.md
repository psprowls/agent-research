---
phase: 28
verified: 2026-05-25T00:00:00Z
status: gaps_found
score: 4/5 must-haves verified
requirements_covered: SCHEMA-01, SCHEMA-02, SCHEMA-03, SCHEMA-04, SCHEMA-05
test_count: 141
test_failures: 0
overrides_applied: 0
gaps:
  - truth: "URI composition is fully unit-tested before any emitter is built (SC#3 + D-03 + D-08)"
    status: partial
    reason: "parse_remote_url SSH regex violates D-03 by accepting GitLab subgroups (multi-segment paths). Confirmed live in repo: `parse_remote_url('git@gitlab.com:group/sub/repo.git')` returns `('group', 'sub/repo')` instead of `None`. This produces a malformed 4-segment pkg URI (`pkg:group/sub/repo/name`) that violates the D-07 shape contract. The HTTPS regex correctly rejects subgroups; the SSH parametrize list has no subgroup case (IN-02), which is what allowed CR-01 through the D-08 'full unit coverage' gate. Phase 29+ emitters consume these URIs as opaque identifiers — the malformed shape is silent until a downstream consumer parses it."
    artifacts:
      - path: "packages/graph-io/src/graph_io/uri.py"
        issue: "Line 43: `_SSH_REMOTE_RE = re.compile(r'^git@[^:]+:([^/]+)/(.+?)(?:\\.git)?$')` — the `.+?` second group accepts `/` characters, allowing subgroup paths through"
      - path: "packages/graph-io/tests/test_uri.py"
        issue: "Lines 69-82: parametrize list covers HTTPS subgroup → None but has no SSH subgroup case"
    missing:
      - "Tighten SSH regex: `_SSH_REMOTE_RE = re.compile(r'^git@[^:]+:([^/]+)/([^/]+?)(?:\\.git)?$')` (mirror HTTPS pattern's bounded `[^/]+?` second group)"
      - "Add SSH subgroup negative cases to `test_parse_remote_url` parametrize: `('git@gitlab.com:group/sub/repo.git', None)` and `('git@gitlab.com:group/sub/repo', None)`"
---

# Phase 28: Schema v2 + URI Foundation Verification Report

**Phase Goal:** The `graph-io` store speaks schema v2 — every new emitter has a `uri` column to write to, schema mismatches exit cleanly with code 4, and URI composition is tested before any emitter is built.

**Verified:** 2026-05-25
**Status:** gaps_found
**Score:** 4/5 must-haves verified
**Re-verification:** No — initial verification

## Goal Achievement

### Success-Criteria Checklist (ROADMAP contract)

| # | Success Criterion | Status | Evidence |
|---|-------------------|--------|----------|
| 1 | `cg update --full` against schema-v1 detects mismatch, rebuilds at v2, exits 0 | VERIFIED | `update.py:211-219` probes schema_version pre-connect; under `--full` prints `"Schema v1 detected — rebuilding code.db at schema v2."` to stderr (line 215-218) and calls `_unlink_db_files(db_path)` (line 219). Verified by `test_store.py::test_update_full_rebuilds_v1_db_to_v2` (lines 112-142) — passes |
| 2 | Non-`--full` commands exit with code 4 + friendly stderr message on a v1 DB | VERIFIED | `update.py:220-221` raises `store.SchemaMismatchError(found=found, expected=schema.SCHEMA_VERSION)` on non-`--full` path; `cli/ops_update.py:24-26` catches it and returns `exit_codes.SCHEMA_MISMATCH` (= 4). Verified by `test_cli_exit_codes.py::test_cg_update_on_v1_db_exits_schema_mismatch` and `::test_exit_4_schema_mismatch` (11 subcommand check) |
| 3 | `graph_io/uri.py` ships with RepoContext + 7 helpers + parse_remote_url, fully unit-tested | **PARTIAL** | All 7 helpers + RepoContext present (`uri.py:9-54`); 17 collected test cases (`test_uri.py`). **GAP: parse_remote_url SSH regex accepts GitLab subgroups (CR-01), violating D-03. Unit coverage missing the SSH subgroup case (IN-02).** |
| 4 | After `cg update --full`, every Package node has a non-NULL `uri` column derived from `pkg_uri(ctx, name)` | VERIFIED | `packages.py:124`: `"uri": pkg_uri(ctx, info["name"])` in the Package node attrs dict. `_upsert_node` (upsert.py:48-59) pops uri and writes to column. Verified by `test_packages.py::test_refresh_writes_pkg_uri_on_package_nodes` |
| 5 | `_upsert_node` writes URI to the dedicated `uri` column, NOT into `attrs_json` (PITFALL 4 locked) | VERIFIED | `upsert.py:50-51` copies attrs and pops uri BEFORE serialize; INSERT (line 42) and UPDATE (line 55) SQL both write the dedicated `uri` column. D-12 sentinel `test_upsert.py::test_upsert_uri_lands_in_column` (line 107) verifies absence from attrs_json |

**Score:** 4/5 — SC#3 PARTIAL due to CR-01 (D-03 violation).

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
| 9 | `parse_remote_url` correctly rejects HTTPS GitLab subgroups, git://, file://, garbage | VERIFIED | `test_uri.py:69-82` parametrize cases all green |
| 10 | `parse_remote_url` correctly rejects SSH GitLab subgroups per D-03 | **FAILED** | **CR-01 confirmed live: `parse_remote_url('git@gitlab.com:group/sub/repo.git')` returns `('group', 'sub/repo')` — D-03 violated** |
| 11 | `cg update --full` is idempotent (SCHEMA-05) | VERIFIED (with caveat) | Structural equivalence proven by `test_update_full_twice_produces_byte_identical_db`. **Caveat:** ROADMAP SC#4 wording says "byte-identical" but implementation asserts structural equivalence due to intentional `last_indexed_at` wall-clock metadata write. Plan 05 SUMMARY documents this deviation as the semantically-meaningful invariant SCHEMA-05 cares about — accepted as documented |

### Required Artifacts

| Artifact | Expected | Status | Details |
|----------|----------|--------|---------|
| `packages/graph-io/src/graph_io/schema.py` | SCHEMA_VERSION=2, uri column, idx_nodes_uri | VERIFIED | All present (lines 12, 23, 28) |
| `packages/graph-io/src/graph_io/uri.py` | RepoContext + 7 helpers + parse_remote_url | VERIFIED (existence); SSH regex contract violated | All 9 exports present; SSH regex bug |
| `packages/graph-io/src/graph_io/upsert.py` | Uri column write path | VERIFIED | dict-copy + pop + column write on INSERT & UPDATE |
| `packages/graph-io/src/graph_io/update.py` | v1→v2 unlink+rebuild + ctx derivation + threading | VERIFIED | 3 new helpers, all wired |
| `packages/graph-io/src/graph_io/packages.py` | refresh accepts ctx; writes pkg_uri | VERIFIED | Required `ctx: RepoContext` kw arg, pkg_uri in attrs |
| `packages/graph-io/src/graph_io/cli/ops_update.py` | SchemaMismatchError handler before generic Exception | VERIFIED | Handler positioned at lines 24-26, before line 27 Exception catch |
| `packages/graph-io/tests/test_uri.py` | Full helper + parse_remote_url coverage | VERIFIED (existence); subgroup-SSH parametrize missing | 17 collected cases; IN-02 gap |
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
| `update.run` | `(org, repo)` | `parse_remote_url(_git(['remote','get-url','origin']))` | WIRED | `update.py:141-157` `_derive_repo_context` → `update.py:207` |
| `_upsert_node` | `nodes.uri` column | pop attrs → INSERT/UPDATE | WIRED | `upsert.py:50-59` |
| `ops_update.run` | `exit_codes.SCHEMA_MISMATCH` | `except store.SchemaMismatchError` | WIRED | `cli/ops_update.py:24-26`, positioned before generic Exception |
| `update.run` | `store.SchemaMismatchError(found=, expected=)` | raised on non-`--full` v1 | WIRED | `update.py:220-221`; kwargs verified against `store.py:20` |

### Data-Flow Trace (Level 4)

| Artifact | Data Variable | Source | Produces Real Data | Status |
|----------|--------------|--------|--------------------|--------|
| Package node `uri` column | `attrs["uri"]` | `pkg_uri(ctx, info["name"])` where `ctx` derives from real `git remote get-url origin` (or `local/<repo_root.name>` fallback) | YES — real (org, repo) for the agent-research repo; falls back to local sentinel correctly | FLOWING |
| Schema-version probe value | `found` | `_read_schema_version_or_none(db_path)` reads real `metadata.schema_version` via read-only sqlite URI | YES — verified by `_seed_v1_db` sanity assert (test_store.py:104-108) | FLOWING |

### Behavioral Spot-Checks

| Behavior | Command | Result | Status |
|----------|---------|--------|--------|
| All helpers import + pkg_uri composes | `uv run --package graph-io python -c "from graph_io.uri import RepoContext, pkg_uri; print(pkg_uri(RepoContext('org','repo'), 'name'))"` | `pkg:org/repo/name` | PASS |
| Full graph-io test suite | `uv run --package graph-io pytest packages/graph-io/tests/ -x` | 141 passed in 9.76s | PASS |
| CR-01 reproduction | `uv run --package graph-io python -c "from graph_io.uri import parse_remote_url; print(parse_remote_url('git@gitlab.com:group/sub/repo.git'))"` | `('group', 'sub/repo')` (expected: `None`) | **FAIL** — D-03 violated |
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
| SCHEMA-03 | 28-02 | `graph_io.uri` exposes 7 composition helpers + stable URI shapes | SATISFIED w/ caveat | All helpers ship; URI shapes correct; **but parse_remote_url SSH branch violates D-03 for GitLab subgroups (see gap)** |
| SCHEMA-04 | 28-01, 28-03 | URIs persisted on dedicated `uri TEXT` column (not in attrs_json); nullable | SATISFIED | schema.py:23 + upsert.py pop-and-bind to column; test_upsert.py D-12 sentinel |
| SCHEMA-05 | 28-05 | `cg update --full` is idempotent — twice on same git state → byte-identical code.db | SATISFIED (with documented deviation) | Structural equivalence asserted; byte-identity precluded by intentional `last_indexed_at` metadata write — Plan 05 SUMMARY documents the decision and justifies structural equality as the semantic invariant |

**No orphaned requirements.** All five SCHEMA-* requirements are claimed by plans in this phase, and all are addressed in code.

### Anti-Patterns Found

Scanned all 6 modified source files plus 6 test files. Results:

| File | Line | Pattern | Severity | Impact |
|------|------|---------|----------|--------|
| (none) | — | TBD/FIXME/XXX/TODO/HACK/PLACEHOLDER | — | Zero debt markers in any Phase 28 file |

**Plan-05 known deviations (acknowledged in 28-05-SUMMARY.md):**
- Structural-equivalence test for SCHEMA-05 byte-identity (Info — documented decision)
- `LATTICE_GRAPH_LOCK_TIMEOUT_MS` untouched (Info — explicitly Phase 34 scope)
- T-28-05-03 concurrent --full race accepted as residual risk (Info)

**Code-review findings inherited from 28-REVIEW.md:**

| ID | Severity | File:Line | Disposition in this verification |
|----|----------|-----------|----------------------------------|
| CR-01 | BLOCKER | `uri.py:43` | **Treated as gap** — D-03 violation; SC#3 "fully unit-tested" partial |
| WR-01 | Warning | `update.py:188-190` | Latent (no caller currently passes non-`code.db` path); flag for follow-up |
| WR-02 | Warning | `update.py:149-152` | Latent (missing `git` binary edge case); D-04 says "any failure" — actual catch narrower |
| WR-03 | Warning | `test_store.py:95-109` | Test fixture seeds v2-shape DDL with v1 metadata; adequate for current unlink+rebuild strategy but not for hypothetical in-place migration tests |
| IN-01 | Info | `test_cli_exit_codes.py:152-156` | Stale docstring (Plan-05 has shipped the real probe); test still valid as CLI-handler unit test |
| IN-02 | Info | `test_uri.py:69-82` | Missing SSH subgroup parametrize case — root cause of CR-01 slipping through |

### Gaps Summary

**One gap blocks the phase verdict: CR-01 (D-03 violation in parse_remote_url SSH regex).**

The phase goal says "URI composition is tested before any emitter is built." The implementation ships all 7 helpers and `parse_remote_url` with 17 collected test cases — but the test parametrization has a hole (no SSH subgroup case, IN-02), and behind that hole sits a real contract violation (CR-01): the SSH regex `^git@[^:]+:([^/]+)/(.+?)(?:\.git)?$` uses an unbounded second group that accepts multi-segment paths. This produces malformed URIs with 4 path segments after the scheme (`pkg:group/sub/repo/name`) instead of the locked 3 (`pkg:org/repo/name` per D-07), and the malformation is silent until a downstream consumer parses the URI.

For agent-research specifically (flat GitHub path `pat/agent-research`), CR-01 has zero observable runtime effect. The fix is also small and local — 1-line regex tightening + 2-line test addition (~5 minutes' work). But CR-01 ships a defect into the foundation layer that every Phase 29-31 emitter will consume, and D-08 explicitly promised "full unit coverage" as the Phase 28 exit criterion. I'm calling this a gap rather than waving through.

**SC#5 byte-identity deviation is NOT a gap.** It's an acknowledged, documented design choice in 28-05-SUMMARY.md, and the structural-equivalence assertion captures the semantically-meaningful guarantee SCHEMA-05 cares about. The only way to recover pure byte-identity would be to remove the intentional `last_indexed_at` wall-clock metadata write, which is explicitly out of Phase 28 scope. Accepting per Plan 05 author's decision.

**WR-01/WR-02/WR-03/IN-01 are NOT gaps.** They are latent risks or cosmetic documentation issues that don't block the phase goal. Surface as recommended follow-up.

### Recommended Next Steps

**To close the gap (5-minute fix):**

1. In `packages/graph-io/src/graph_io/uri.py:43`, change:
   ```python
   _SSH_REMOTE_RE = re.compile(r"^git@[^:]+:([^/]+)/(.+?)(?:\.git)?$")
   ```
   to:
   ```python
   _SSH_REMOTE_RE = re.compile(r"^git@[^:]+:([^/]+)/([^/]+?)(?:\.git)?$")
   ```
2. In `packages/graph-io/tests/test_uri.py:69-82` parametrize list, add:
   ```python
   ("git@gitlab.com:group/sub/repo.git", None),
   ("git@gitlab.com:group/sub/repo", None),
   ```
3. Run `uv run --package graph-io pytest packages/graph-io/tests/test_uri.py -x` to confirm 19 cases collected, all green.
4. Re-run `/gsd:verify-work 28` (or equivalent) — gap should close to `passed`.

**Optional follow-up (NOT blocking Phase 29):**

- WR-01: Derive WAL/SHM sibling names from `db_path.name` in `_unlink_db_files` (defensive — current sole caller is safe).
- WR-02: Broaden `_derive_repo_context` catch to `(NotInGitRepoError, FileNotFoundError)` per D-04's "any failure" wording.
- WR-03/IN-01: Tighten docstrings in test helpers to reflect post-28-05 reality.

### Test Summary

```
uv run --package graph-io pytest packages/graph-io/tests/ -x
============================= 141 passed in 9.76s ==============================
```

| Test File | Tests Passing |
|-----------|---------------|
| test_cli_exit_codes.py | 10 (including 3 Plan-04 additions + 1 Plan-05 xfail removal) |
| test_packages.py | 8 (includes new `test_refresh_writes_pkg_uri_on_package_nodes`) |
| test_schema.py | 6 (includes D-12 sentinels #1, #2) |
| test_store.py | 8 (includes Plan-05 `test_update_full_rebuilds_v1_db_to_v2` + `test_update_incremental_on_v1_db_raises_schema_mismatch`) |
| test_update_idempotent.py | 2 (includes Plan-05 `test_update_full_twice_produces_byte_identical_db`) |
| test_upsert.py | 8 (includes D-12 sentinel #3 + 2 regression guards) |
| test_uri.py | 17 cases (9 functions; parametrized parse_remote_url contributes 9) |
| (other unchanged files) | 82 |
| **Total** | **141 passed, 0 failed, 0 xfailed** |

---

_Verified: 2026-05-25_
_Verifier: Claude (gsd-verifier)_
