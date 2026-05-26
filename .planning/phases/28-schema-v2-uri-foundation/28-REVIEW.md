---
phase: 28
status: issues_found
depth: standard
files_reviewed: 13
files_reviewed_list:
  - packages/graph-io/src/graph_io/schema.py
  - packages/graph-io/src/graph_io/upsert.py
  - packages/graph-io/src/graph_io/cli/ops_update.py
  - packages/graph-io/src/graph_io/update.py
  - packages/graph-io/src/graph_io/packages.py
  - packages/graph-io/src/graph_io/uri.py
  - packages/graph-io/tests/test_schema.py
  - packages/graph-io/tests/test_uri.py
  - packages/graph-io/tests/test_upsert.py
  - packages/graph-io/tests/test_cli_exit_codes.py
  - packages/graph-io/tests/test_store.py
  - packages/graph-io/tests/test_packages.py
  - packages/graph-io/tests/test_update_idempotent.py
findings:
  critical: 1
  warning: 3
  info: 2
  total: 6
---

# Phase 28: Code Review Report

**Reviewed:** 2026-05-25
**Depth:** standard
**Files Reviewed:** 13
**Status:** issues_found

## Summary

Phase 28 lands schema v2 + URI foundation cleanly along most axes: the `uri` column write path in `_upsert_node` is correct (PITFALL 4 closed via `dict()` copy + `pop` before `_serialize`), `SchemaMismatchError` is wired through every CLI module that opens a connection (handler ordering in `ops_update.py` is correct — `NotInGitRepoError` → `UpdateInProgressError` → `SchemaMismatchError` → `Exception`), `ctx` is derived once at `update.run` and threaded into `packages.refresh` without re-derivation downstream, and the planning-stage xfail marker from Plan 04 was removed in Plan 05 as documented. No TODO/FIXME/HACK markers remain, and no Bedrock/secret-handling surface was touched.

The one BLOCKER is a **silent violation of D-03** in `parse_remote_url`: the SSH regex accepts multi-segment paths and returns `(org, "sub/repo")` for GitLab-subgroup SSH URLs, producing malformed `pkg:` URIs with an embedded slash. The HTTPS regex correctly rejects subgroups (test coverage exists for HTTPS-only); the SSH branch has no parametrized subgroup case and the bug slipped through. Three WARNINGs cover migration-helper fragility, narrow exception catching in repo-context derivation, and a missing structural guard in the "v1 DB" test fixture. Two INFO items flag stale documentation.

## Findings Table

| ID | Severity | File:Line | Issue |
|----|----------|-----------|-------|
| CR-01 | Critical | `uri.py:43` | SSH `parse_remote_url` regex accepts subgroups, violating D-03 — yields malformed pkg URIs |
| WR-01 | Warning | `update.py:188-190` | `_unlink_db_files` hardcodes `code.db-wal`/`code.db-shm` filenames instead of deriving from `db_path` |
| WR-02 | Warning | `update.py:149-152` | `_derive_repo_context` only catches `NotInGitRepoError` — a missing `git` binary raises `FileNotFoundError` and crashes update |
| WR-03 | Warning | `tests/test_store.py:95-109` | `_seed_v1_db` fakes a v1 DB by rewriting only the metadata row — the on-disk table DDL is still v2 (has `uri` column), so the test does not exercise a true v1 schema shape |
| IN-01 | Info | `tests/test_cli_exit_codes.py:152-156` | Docstring claims "Plan 28-05 will add the actual probe inside update.run" — Plan 28-05 has already shipped that probe; documentation is stale |
| IN-02 | Info | `tests/test_uri.py:69-82` | `parse_remote_url` parametrization is missing an SSH-subgroup case (e.g., `git@gitlab.com:group/sub/repo.git`) — would catch CR-01 |

---

## Critical Issues

### CR-01: SSH `parse_remote_url` regex accepts GitLab subgroups, violating D-03

**File:** `packages/graph-io/src/graph_io/uri.py:43`

**Issue:**
The SSH regex is `^git@[^:]+:([^/]+)/(.+?)(?:\.git)?$`. The second capture group uses `.+?` (lazy any-character), which happily matches paths containing `/`. CONTEXT.md **D-03** is explicit:

> GitLab subgroups (multi-segment paths), `git://`, `file://`, and any other shape return `None` and fall through to local fallback.

Confirmed in a 1-line repro:

```
>>> parse_remote_url("git@gitlab.com:group/sub/repo.git")
('group', 'sub/repo')                       # expected: None
>>> parse_remote_url("git@gitlab.com:group/sub/repo")
('group', 'sub/repo')                       # expected: None
```

The HTTPS branch (`[^/]+?` for the repo group) correctly rejects subgroups, and `test_uri.py` parametrization covers `"https://gitlab.com/group/subgroup/repo" -> None`. The SSH branch has **no** corresponding subgroup test case, so the bug slipped through the D-08 unit-coverage gate.

Downstream consequence: when a user clones via SSH from a GitLab subgroup, `_derive_repo_context` accepts the parse, returns `RepoContext(org="group", repo="sub/repo")`, and `packages.refresh` then writes `attrs["uri"] = pkg_uri(ctx, name)` = `"pkg:group/sub/repo/name"` — a string with **four** path segments after the scheme instead of the three required by D-07 (`pkg:org/repo/name`). That URI lands in the `uri` column of every Package node and will be queried/joined by Phase 29-31 emitters as an opaque identifier; the malformed shape is silent until a downstream consumer parses it.

This violates D-03, breaks the D-07 URI shape contract, and is a foundation-level defect (Phase 29 builds on these URIs).

**Fix:**
Mirror the HTTPS branch's bounded character class for the repo group in the SSH regex:

```python
# uri.py
_SSH_REMOTE_RE = re.compile(r"^git@[^:]+:([^/]+)/([^/]+?)(?:\.git)?$")
```

Then extend `test_uri.py::test_parse_remote_url` parametrization with the missing cases (these also close IN-02):

```python
("git@gitlab.com:group/sub/repo.git", None),
("git@gitlab.com:group/sub/repo", None),
```

Verify: `uv run --package graph-io pytest packages/graph-io/tests/test_uri.py -x` should still pass with the tightened regex and the two new cases.

---

## Warnings

### WR-01: `_unlink_db_files` hardcodes WAL/SHM sibling filenames

**File:** `packages/graph-io/src/graph_io/update.py:183-190`

**Issue:**
```python
def _unlink_db_files(db_path: Path) -> None:
    db_path.unlink(missing_ok=True)
    (db_path.parent / "code.db-wal").unlink(missing_ok=True)
    (db_path.parent / "code.db-shm").unlink(missing_ok=True)
```

The function takes `db_path` as a parameter but the WAL/SHM sibling names are hardcoded literals. If the caller ever passes a `db_path` whose stem isn't `code.db` (test fixtures, future renames, the Phase 34 brand sweep, multi-DB scenarios), the function silently leaves stale WAL/SHM siblings on disk. SQLite's WAL recovery on next open could replay obsolete pages over a freshly-rebuilt v2 schema — exactly the partial-state risk D-01 was written to eliminate.

This is latent (current sole caller in `update.run` uses `db_path = graph_dir(workspace) / "code.db"`), but the function signature accepts an arbitrary `Path` and the docstring acknowledges the coupling rather than guarding against it.

**Fix:**
Derive sibling names from `db_path`:

```python
def _unlink_db_files(db_path: Path) -> None:
    db_path.unlink(missing_ok=True)
    for suffix in ("-wal", "-shm"):
        db_path.with_name(db_path.name + suffix).unlink(missing_ok=True)
```

No new test needed — existing `test_update_full_rebuilds_v1_db_to_v2` exercises the path.

### WR-02: `_derive_repo_context` does not catch `FileNotFoundError` for a missing `git` binary

**File:** `packages/graph-io/src/graph_io/update.py:141-157`

**Issue:**
```python
try:
    remote_url = _git(["remote", "get-url", "origin"], cwd=repo_root).strip()
except NotInGitRepoError:
    return RepoContext(org="local", repo=repo_root.name)
```

`_git` calls `subprocess.run(["git", ...])`. On systems without `git` on `PATH` (CI minimal containers, test sandboxes), `subprocess.run` raises `FileNotFoundError`, not `NotInGitRepoError`. The current except clause won't catch it, so `update.run` crashes with a bare `FileNotFoundError` → routed by `ops_update.py`'s generic `except Exception` → exit code 1 instead of the documented local fallback (D-05) or the documented `NOT_IN_GIT_REPO=5`.

Note that `_head(repo_root)` is called BEFORE `_derive_repo_context` and would also raise `FileNotFoundError` for the same reason — but `_head` is older code and out of phase scope. The new code introduced in Phase 28 still inherits the brittleness.

D-04 explicitly says fall back on "any failure" of `git remote get-url origin`. The current catch is narrower than D-04 promises.

**Fix:**
Broaden the catch to include the OS-level failure mode:

```python
try:
    remote_url = _git(["remote", "get-url", "origin"], cwd=repo_root).strip()
except (NotInGitRepoError, FileNotFoundError):
    return RepoContext(org="local", repo=repo_root.name)
```

This matches D-05's intent. Optionally fix `_head` similarly — but that is out of phase scope; flag only.

### WR-03: `_seed_v1_db` does not produce a structurally-v1 DB

**File:** `packages/graph-io/tests/test_store.py:95-109`

**Issue:**
```python
def _seed_v1_db(repo_root: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    ws = resolve_workspace(repo_root, require_manifest=False).workspace
    db_path = graph_dir(ws) / "code.db"
    monkeypatch.setattr(schema, "SCHEMA_VERSION", 1)
    conn = store.connect(db_path, create=True)
    conn.close()
    monkeypatch.undo()
```

The monkeypatch only replaces the integer `SCHEMA_VERSION`. `apply_schema` then runs the **current v2 `_DDL_STATEMENTS` tuple** — which already includes the `uri` column and `idx_nodes_uri` index — and inserts `('schema_version', '1')` into metadata. The resulting on-disk DB has:
- v2 schema shape (`nodes` table has `uri`, the `idx_nodes_uri` index exists)
- v1 metadata row (`schema_version = '1'`)

This is a structurally-broken artifact: no real v1 DB ever had the `uri` column. The test passes because the rebuild path is purely "read version → unlink → recreate", and the rebuilt DB is freshly v2, so the v1-shaped DDL never gets exercised. The test happens to validate the bytes-on-disk migration *outcome* but does not exercise what would happen against a *real* v1 DB on a long-lived dev workstation that updated through this phase boundary.

Since the migration strategy is **unlink+rebuild** (no in-place ALTER TABLE), the DDL shape of the v1 DB technically doesn't matter to the rebuild — but the test claims in the docstring to seed "a real v1 DB on disk" and the fixture name `_seed_v1_db` implies stronger semantics than it delivers. If a future plan ever attempts an in-place migration shortcut, this fixture would mask the failure.

**Fix:**
Either (a) tighten the docstring to make the fakery explicit:

```python
def _seed_v1_db(repo_root: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Create a code.db with v2 DDL but a v1 metadata.schema_version row.

    NOTE: This is structurally a v2 DB; only the version row is rewritten.
    Adequate for testing the unlink+rebuild path (which never reads the
    table schema before unlinking) but not for in-place-migration tests.
    """
```

Or (b) write the v1 DDL inline (a hand-coded `CREATE TABLE nodes` without `uri`) so the fixture is true to its name. Option (a) is the lower-cost fix and matches the unlink-rebuild migration strategy that D-01 locks. Option (b) is required if Phase 29+ ever revisits in-place migration.

---

## Info

### IN-01: Stale docstring on `test_cg_update_on_v1_db_exits_schema_mismatch`

**File:** `packages/graph-io/tests/test_cli_exit_codes.py:152-156`

**Issue:**
```python
"""...
The handler is wired defensively in Plan 28-04. Plan 28-05 will add the actual
probe inside update.run that raises SchemaMismatchError on the non-`--full`
path. Until then, we simulate that raise via monkeypatch to validate the CLI
handler's routing.
"""
```

Plan 28-05 has shipped that probe (`update.py:212-221` raises `store.SchemaMismatchError(found=, expected=schema.SCHEMA_VERSION)` on the non-`--full` path against a v1 DB). The docstring's "Plan 28-05 will add" is now historically false; the monkeypatch still works (the test exercises the CLI handler in isolation regardless of whether `update.run` has the real probe), but the rationale is stale.

A separate lower-level test (`test_store.py::test_update_incremental_on_v1_db_raises_schema_mismatch`) now covers the real probe path. The monkeypatched test could either be kept as a focused CLI-handler unit test or replaced with a real subprocess invocation now that the path is live.

**Fix:**
Update the docstring to reflect post-28-05 reality:

```python
"""`cg update` (no --full) on a v1 DB exits 4 with `cg update --full` in stderr.

This test isolates the CLI handler's routing by monkeypatching update.run
to raise SchemaMismatchError directly. The real probe (added in Plan 28-05)
is covered separately by test_update_incremental_on_v1_db_raises_schema_mismatch
in test_store.py.
"""
```

### IN-02: `parse_remote_url` parametrization missing SSH-subgroup case

**File:** `packages/graph-io/tests/test_uri.py:69-82`

**Issue:**
The parametrization covers:
- HTTPS subgroup → `None` (good)
- `git://...` → `None`
- `file:///tmp/x` → `None`
- garbage → `None`
- SSH with/without `.git`
- HTTPS with/without `.git` and trailing slash

But there is no SSH-subgroup negative case. Per CR-01, the SSH regex silently accepts subgroups; the missing test is what allowed the bug through D-08's "full unit coverage" gate.

**Fix:**
Bundle with the CR-01 fix. After tightening the SSH regex, add:

```python
("git@gitlab.com:group/sub/repo.git", None),
("git@gitlab.com:group/sub/repo", None),
```

to the parametrize list.

---

_Reviewed: 2026-05-25_
_Reviewer: Claude (gsd-code-reviewer)_
_Depth: standard_
