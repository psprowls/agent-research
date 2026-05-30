---
phase: quick-260530-iqo
plan: 01
type: execute
wave: 1
depends_on: []
files_modified:
  - packages/graph-io/src/graph_io/schema.py
  - packages/graph-io/src/graph_io/update.py
  - packages/graph-io/tests/test_update_full.py
autonomous: true
requirements: [IQO-01]

must_haves:
  truths:
    - "Re-running `update.run()` at an unchanged git HEAD forces a full rebuild when DERIVER_VERSION changed"
    - "A stale derived value (e.g. an app_kind) gets refreshed by the forced rebuild without any source file or commit change"
    - "When DERIVER_VERSION is unchanged, the incremental short-circuit at the same HEAD still returns early (no behavior regression)"
    - "The graph DB stores the deriver_version it was last built with"
  artifacts:
    - path: "packages/graph-io/src/graph_io/schema.py"
      provides: "DERIVER_VERSION constant"
      contains: "DERIVER_VERSION"
    - path: "packages/graph-io/src/graph_io/update.py"
      provides: "deriver-version mismatch → force full rebuild + write deriver_version metadata"
      contains: "deriver_version"
    - path: "packages/graph-io/tests/test_update_full.py"
      provides: "test proving a DERIVER_VERSION bump forces a full rebuild at unchanged HEAD"
  key_links:
    - from: "packages/graph-io/src/graph_io/update.py"
      to: "schema.DERIVER_VERSION"
      via: "compare stored metadata.deriver_version against current constant before short-circuit"
      pattern: "schema\\.DERIVER_VERSION"
    - from: "packages/graph-io/src/graph_io/update.py"
      to: "metadata.deriver_version"
      via: "_set_metadata at end of transaction"
      pattern: "deriver_version"
---

<objective>
`cg update` is incremental and git-diff-gated: when source files and HEAD are unchanged but DERIVATION LOGIC (e.g. `classify()`) changed, the existing graph keeps stale derived values until a forced full rebuild. This silently breaks the "ship a graph-io derivation fix → re-scan → see no change" workflow (discovered in quick task 260530-gqp: the electron fix didn't take effect on re-scan).

Fix it with a deriver version stamp: a single `DERIVER_VERSION` constant stored in graph metadata. On `update.run()`, if the stored stamp differs from the current code's stamp, force a full rebuild automatically — no human memory required.

Purpose: derivation-logic changes propagate to existing graphs without anyone remembering to pass `--full`.
Output: `DERIVER_VERSION` constant, mismatch-detection + metadata write in `update.run()`, and a test proving the forced rebuild.
</objective>

<execution_context>
@$HOME/.claude/get-shit-done/workflows/execute-plan.md
@$HOME/.claude/get-shit-done/templates/summary.md
</execution_context>

<context>
@.planning/STATE.md
@.planning/quick/260530-iqo-force-graph-rebuild-when-derivation-logi/../../todos/pending/2026-05-30-force-graph-rebuild-when-derivation-logic-changes.md

@packages/graph-io/src/graph_io/update.py
@packages/graph-io/src/graph_io/schema.py
@packages/graph-io/src/graph_io/classification.py
@packages/graph-io/tests/test_update_full.py
@packages/graph-io/tests/_git_repo.py

<interfaces>
<!-- Existing helpers in update.py the executor must reuse — do NOT reimplement. -->

From packages/graph-io/src/graph_io/update.py:
```python
def _get_metadata(conn, key: str) -> str | None        # reads metadata.value or None
def _set_metadata(conn, key: str, value: str) -> None   # upsert into metadata
def run(repo_root, *, workspace=None, full=False, lock_timeout_ms=None) -> None
```

Relevant run() body landmarks (line numbers approximate, current at plan time):
- :268  `prev = _get_metadata(conn, "last_indexed_commit")`
- :269  `changed = _changed_files(repo_root, full=full, prev=prev)`
- :270  `if not changed and prev == head and not full: return`   ← the short-circuit to bypass
- :312  `_set_metadata(conn, "last_indexed_commit", head)`        ← write deriver_version near here

From packages/graph-io/src/graph_io/schema.py:
```python
SCHEMA_VERSION = 2   # bumping this already forces a rebuild; DERIVER_VERSION is the new sibling
```
</interfaces>
</context>

<tasks>

<task type="auto" tdd="true">
  <name>Task 1: Add DERIVER_VERSION stamp and force full rebuild on mismatch</name>
  <files>packages/graph-io/src/graph_io/schema.py, packages/graph-io/src/graph_io/update.py</files>
  <behavior>
    - Existing graph built at DERIVER_VERSION=N; current code DERIVER_VERSION=N+1; unchanged HEAD/files → update.run treats run as full (rebuild), refreshing derived values.
    - Existing graph built at DERIVER_VERSION=N; current code DERIVER_VERSION=N; unchanged HEAD/files → short-circuit still returns early (no rebuild).
    - After any successful run, metadata.deriver_version == str(current DERIVER_VERSION).
    - Fresh DB (prev is None): no spurious "deriver version changed" stderr hint — bootstrap path already rebuilds; mismatch detection must not fire its message when prev is None.
  </behavior>
  <action>
    In schema.py: add `DERIVER_VERSION = 1` directly below `SCHEMA_VERSION` with a one-line docstring/comment stating it is bumped whenever any node/edge/attr DERIVATION logic changes (e.g. `classification.classify`, app_kind precedence, derived-edge rules) so existing graphs auto-rebuild. Mirror the existing SCHEMA_VERSION comment style.

    In update.py `run()`: after `prev = _get_metadata(conn, "last_indexed_commit")` (currently :268) and before `_changed_files` (:269), read `stored_deriver = _get_metadata(conn, "deriver_version")`. If `prev is not None` (an existing graph) and `stored_deriver != str(schema.DERIVER_VERSION)`, set `full = True` and print a one-line stderr hint via `print(..., file=sys.stderr)` like: "Deriver logic changed (deriver_version {stored} → {current}) — forcing full rebuild." Reassigning the `full` parameter before `_changed_files`/short-circuit/`if full:` re-delete block means the existing full-rebuild path is reused as-is — do NOT duplicate rebuild logic. Use `sys` (already imported) and `schema` (already imported).

    Still in the transaction, near `_set_metadata(conn, "last_indexed_commit", head)` (:312), add `_set_metadata(conn, "deriver_version", str(schema.DERIVER_VERSION))`. This persists the stamp on every successful run (both full and incremental), so a graph built before this feature gets stamped on its next run.

    Surgical scope (Karpathy): touch ONLY these two files plus the test in Task 2. Do NOT edit upsert.py, _ignore.py, structural_nodes.py, classification.py, or any graph-wiki-agent file — concurrent sibling tasks own those. classification.py is referenced only as the canonical example of derivation logic in the DERIVER_VERSION comment; do not modify it.
  </action>
  <verify>
    <automated>cd /Users/pat/Personal/agent-research && uv run --package graph-io pytest packages/graph-io/tests/test_update_incremental.py packages/graph-io/tests/test_update_full.py -q</automated>
  </verify>
  <done>schema.py exports DERIVER_VERSION; update.run forces full when stored deriver_version differs from current (only when prev is not None) and writes deriver_version metadata on every successful run; existing incremental + full tests stay green.</done>
</task>

<task type="auto">
  <name>Task 2: Test — deriver version bump forces rebuild at unchanged HEAD</name>
  <files>packages/graph-io/tests/test_update_full.py</files>
  <action>
    Add a test to test_update_full.py proving a DERIVER_VERSION bump forces a full rebuild even when git HEAD and files are unchanged. Use `monkeypatch` (pytest fixture) and the existing `init_repo` / `write_and_commit` / `_open_ro` helpers already in the file.

    Test shape (`test_deriver_version_bump_forces_rebuild`):
    1. `init_repo` + `write_and_commit` a tiny repo (one .py file with a known function), then `update.run(tmp_path, full=True)`.
    2. Open the DB read-only, assert `metadata.deriver_version == str(schema.DERIVER_VERSION)` (import `from graph_io import schema`). Capture current HEAD.
    3. Simulate a deriver-logic change by stamping the stored value back: open a writable connection to code.db and UPDATE metadata SET value='0' WHERE key='deriver_version' (an older stamp), commit, close. (Equivalent to having built the graph with an older deriver.) Do NOT change any source file or make a new commit — HEAD stays identical.
    4. Mutate a derived value directly in the DB so we can prove the rebuild overwrites it: pick the function node and UPDATE its name to a sentinel like 'STALE_SENTINEL' (or delete the function node entirely). This stands in for a stale derived value that only a rebuild would correct.
    5. Call `update.run(tmp_path, full=False)` again — same HEAD, no file changes. Assert the sentinel/staleness is gone (the real function name is back, function node re-derived), AND `metadata.deriver_version == str(schema.DERIVER_VERSION)` again.

    Add a companion negative test (`test_unchanged_deriver_version_still_short_circuits`): after a clean `update.run(full=True)`, mutate a function node name to a sentinel, then `update.run(full=False)` at unchanged HEAD with deriver_version untouched — assert the sentinel is STILL present (short-circuit returned early, no rebuild). This guards against the mismatch check firing when it should not.

    Keep both tests minimal and aligned with the file's existing style (module-level `_open_ro`, direct sqlite asserts). Writable connection for the UPDATE steps: `sqlite3.connect(graph_dir(resolve_workspace(tmp_path, False).workspace) / 'code.db')`.
  </action>
  <verify>
    <automated>cd /Users/pat/Personal/agent-research && uv run --package graph-io pytest packages/graph-io/tests/test_update_full.py -q -k "deriver_version"</automated>
  </verify>
  <done>Both new tests pass: a deriver_version bump forces a rebuild at unchanged HEAD (sentinel cleared), and an unchanged deriver_version still short-circuits (sentinel preserved).</done>
</task>

</tasks>

<verification>
Full package test suite stays green (no regression from reassigning `full` or the extra metadata write):

```
cd /Users/pat/Personal/agent-research && uv run --package graph-io pytest packages/graph-io/tests/ -q
```
</verification>

<success_criteria>
- `schema.DERIVER_VERSION` exists with a comment documenting when to bump it.
- `update.run()` forces a full rebuild when the stored `deriver_version` differs from the current constant (existing graphs only — `prev is not None`), reusing the existing full-rebuild path with no duplicated logic.
- `update.run()` persists `deriver_version` to metadata on every successful run.
- New tests prove: (a) a version bump rebuilds at unchanged HEAD, (b) an unchanged version still short-circuits.
- No files touched outside schema.py, update.py, and test_update_full.py.
- Full graph-io test suite passes.
</success_criteria>

<output>
Create `.planning/quick/260530-iqo-force-graph-rebuild-when-derivation-logi/260530-iqo-SUMMARY.md` when done.
</output>
