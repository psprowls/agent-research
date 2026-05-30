---
phase: quick-260530-jc1
plan: 01
type: execute
wave: 1
depends_on: []
files_modified:
  - agents/graph-wiki-agent/src/graph_wiki_agent/commands/query.py
  - agents/graph-wiki-agent/tests/unit/test_query_graph_tools_wiring.py
  - .planning/debug/sweep-judge-signal-collapse.md
autonomous: true
requirements:
  - LIBTOOLS-04
  - D-07
  - D-08

must_haves:
  truths:
    - "run_query with an empty-but-schema-valid graph DB does NOT bind graph tools to the librarian LLM"
    - "run_query with an empty-but-schema-valid graph DB applies _LIBRARIAN_FALLBACK_ADDENDUM to the system prompt"
    - "run_query with an empty-but-schema-valid graph DB emits _GRAPH_UNAVAILABLE_STDERR to stderr"
    - "Existing wiring tests remain green"
  artifacts:
    - path: "agents/graph-wiki-agent/src/graph_wiki_agent/commands/query.py"
      provides: "Empty-DB guard in graph-connection block"
      contains: "SELECT COUNT(*) FROM nodes"
    - path: "agents/graph-wiki-agent/tests/unit/test_query_graph_tools_wiring.py"
      provides: "Regression test: empty DB → no tool binding"
      contains: "test_empty_graph_db_skips_tools"
    - path: ".planning/debug/sweep-judge-signal-collapse.md"
      provides: "Resolution block filled, status set to resolved"
      contains: "status: resolved"
  key_links:
    - from: "agents/graph-wiki-agent/src/graph_wiki_agent/commands/query.py"
      to: "graph_io.schema (nodes table)"
      via: "conn.execute('SELECT COUNT(*) FROM nodes')"
      pattern: "SELECT COUNT.*FROM nodes"
---

<objective>
Fix the sweep judge-signal collapse caused by empty-but-schema-valid `code.db` files
causing `run_query` to bind graph tools that query an empty DB.

Purpose: Restore pre-e42ae87 behavior — when the graph DB exists but has zero nodes,
treat it as uninitialized (no tools bound, fallback addendum applied). This unblocks
the cost-frontier sweep from producing CODE_FALLBACK_DISCLAIMER answers on 232/~350
sweep cells.

Output: Patched `query.py`, one new regression test, debug doc marked resolved.
</objective>

<execution_context>
@/Users/pat/.claude/get-shit-done/workflows/execute-plan.md
@/Users/pat/.claude/get-shit-done/templates/summary.md
</execution_context>

<context>
@/Users/pat/Personal/agent-research/.planning/debug/sweep-judge-signal-collapse.md
@/Users/pat/Personal/agent-research/agents/graph-wiki-agent/src/graph_wiki_agent/commands/query.py
@/Users/pat/Personal/agent-research/agents/graph-wiki-agent/tests/unit/test_query_graph_tools_wiring.py
</context>

<tasks>

<task type="auto">
  <name>Task 1: Guard empty-DB in run_query graph-connection block</name>
  <files>agents/graph-wiki-agent/src/graph_wiki_agent/commands/query.py</files>
  <action>
In the graph-connection block (~lines 945-952), the current code is:

    try:
        conn = read_only_connect(db_path)
        graph_tools = build_graph_tools(conn)
    except GraphNotInitializedError:
        sys.stderr.write(_GRAPH_UNAVAILABLE_STDERR + "\n")
        addendum = _LIBRARIAN_FALLBACK_ADDENDUM
        # graph_tools stays []; conn stays None.

After `conn = read_only_connect(db_path)` succeeds, insert a node-count check BEFORE
calling `build_graph_tools`. If `conn.execute("SELECT COUNT(*) FROM nodes").fetchone()[0]`
is 0, apply the same treatment as the `GraphNotInitializedError` branch:
- Write `_GRAPH_UNAVAILABLE_STDERR + "\n"` to stderr
- Set `addendum = _LIBRARIAN_FALLBACK_ADDENDUM`
- Close conn: `conn.close(); conn = None`
- Do NOT call `build_graph_tools` — `graph_tools` stays `[]`

The final try-block should read:

    try:
        conn = read_only_connect(db_path)
        if conn.execute("SELECT COUNT(*) FROM nodes").fetchone()[0] == 0:
            sys.stderr.write(_GRAPH_UNAVAILABLE_STDERR + "\n")
            addendum = _LIBRARIAN_FALLBACK_ADDENDUM
            conn.close()
            conn = None
        else:
            graph_tools = build_graph_tools(conn)
    except GraphNotInitializedError:
        sys.stderr.write(_GRAPH_UNAVAILABLE_STDERR + "\n")
        addendum = _LIBRARIAN_FALLBACK_ADDENDUM
        # graph_tools stays []; conn stays None.

No other changes to query.py. Table name `nodes` is confirmed from
`graph_io/schema.py` line 16: `CREATE TABLE IF NOT EXISTS nodes (...)`.
  </action>
  <verify>
    <automated>cd /Users/pat/Personal/agent-research && grep -n "SELECT COUNT.*FROM nodes" agents/graph-wiki-agent/src/graph_wiki_agent/commands/query.py</automated>
  </verify>
  <done>The guard line `conn.execute("SELECT COUNT(*) FROM nodes").fetchone()[0] == 0` appears in query.py within the graph-connection try-block, with `build_graph_tools` only called in the `else` branch.</done>
</task>

<task type="auto" tdd="true">
  <name>Task 2: Add regression test — empty DB skips tool binding</name>
  <files>agents/graph-wiki-agent/tests/unit/test_query_graph_tools_wiring.py</files>
  <behavior>
    - Test: `test_empty_graph_db_skips_tools` — when `read_only_connect` returns a
      real sqlite3 connection to a schema-valid but empty DB, `run_query` must not
      call `bind_tools` on the librarian LLM and must apply `_LIBRARIAN_FALLBACK_ADDENDUM`
      to the SystemMessage. Stderr must contain `_GRAPH_UNAVAILABLE_STDERR` exactly once.
    - The DB is created by calling `graph_io.schema.apply_schema(conn)` on an
      in-memory sqlite3 connection (same provisioning path as EvalWorktree via
      `store.connect(db_path, create=True)`), which leaves a valid but empty `nodes`
      table. Use `tmp_path` to write a real file-backed DB if in-memory won't survive
      `read_only_connect`'s `PRAGMA locking_mode=NORMAL` — see existing
      `test_single_connection_open_close` for the `_fake_open` pattern.
  </behavior>
  <action>
Add `test_empty_graph_db_skips_tools` to `test_query_graph_tools_wiring.py` immediately
after `test_not_initialized_fallback`. Mirror the structure of `test_not_initialized_fallback`
exactly — same `_patches` helper, same `ExitStack`, same `_mock_llm_for` wiring, same
`_fake_run_all` to drive `drill_page`.

Difference from `test_not_initialized_fallback`:
- Do NOT patch `read_only_connect` to raise. Instead, use `_fake_open` (like
  `test_single_connection_open_close`) that returns a real sqlite3 connection to a
  file-backed empty-but-schema-valid DB. Create this DB in tmp_path:

    import sqlite3 as _sqlite3
    from graph_io import schema as _schema
    db_file = tmp_path / "code.db"
    with _sqlite3.connect(str(db_file)) as _c:
        _schema.apply_schema(_c)
    # db_file now exists with the nodes/edges/metadata tables, zero rows in nodes.

  Then `_fake_open` returns `_sqlite3.connect(str(db_file), check_same_thread=False)`.

- Do NOT patch `build_graph_tools` — it should never be reached (the guard fires first).

Assertions (identical to `test_not_initialized_fallback`):
1. `capsys.readouterr().err.count(_GRAPH_UNAVAILABLE_STDERR) == 1`
2. `librarian_llm.bind_tools.call_count == 0`
3. `_LIBRARIAN_FALLBACK_ADDENDUM.strip() in sys_msg.content` (SystemMessage from ainvoke)
  </action>
  <verify>
    <automated>cd /Users/pat/Personal/agent-research && uv run --package graph-wiki-agent pytest agents/graph-wiki-agent/tests/unit/test_query_graph_tools_wiring.py -x -q 2>&1 | tail -15</automated>
  </verify>
  <done>All tests in `test_query_graph_tools_wiring.py` pass, including the new `test_empty_graph_db_skips_tools`. `bind_tools` call count is 0 for the empty-DB case.</done>
</task>

<task type="auto">
  <name>Task 3: Mark debug doc resolved</name>
  <files>.planning/debug/sweep-judge-signal-collapse.md</files>
  <action>
The `## Resolution` section is already written in the debug doc (it was pre-filled
during analysis). Two changes required:

1. Update frontmatter: change `status: root_cause_found` to `status: resolved`.
2. Append to the `## Resolution` section a `**Verification:**` paragraph and
   `**Files changed:**` list confirming the fix landed:

    **Verification:** `test_empty_graph_db_skips_tools` passes — empty-schema-valid
    DB no longer causes tool binding. All existing wiring tests remain green.

    **Files changed:**
    - `agents/graph-wiki-agent/src/graph_wiki_agent/commands/query.py` — empty-DB
      guard in graph-connection try-block (~line 946)
    - `agents/graph-wiki-agent/tests/unit/test_query_graph_tools_wiring.py` —
      `test_empty_graph_db_skips_tools` regression test

No other changes to the file. Preserve all existing content exactly.
  </action>
  <verify>
    <automated>cd /Users/pat/Personal/agent-research && grep -v '^#' .planning/debug/sweep-judge-signal-collapse.md | grep -c "status: resolved"</automated>
  </verify>
  <done>Frontmatter `status` is `resolved` and the Resolution section contains a Verification paragraph and Files changed list.</done>
</task>

</tasks>

<threat_model>
## Trust Boundaries

| Boundary | Description |
|----------|-------------|
| filesystem → sqlite3 | DB file read from workspace path controlled by eval harness |

## STRIDE Threat Register

| Threat ID | Category | Component | Disposition | Mitigation |
|-----------|----------|-----------|-------------|------------|
| T-jc1-01 | Tampering | `SELECT COUNT(*) FROM nodes` | accept | Query is read-only; `read_only_connect` enforces `PRAGMA query_only=ON`; no injection vector (no user input in SQL) |
</threat_model>

<verification>
Run the full wiring test module to confirm all tests (including the new one) pass:

    cd /Users/pat/Personal/agent-research
    uv run --package graph-wiki-agent pytest agents/graph-wiki-agent/tests/unit/test_query_graph_tools_wiring.py -v

All 6+ tests should pass. The new test `test_empty_graph_db_skips_tools` must be among them.
</verification>

<success_criteria>
- `agents/graph-wiki-agent/tests/unit/test_query_graph_tools_wiring.py::test_empty_graph_db_skips_tools` passes
- All pre-existing tests in `test_query_graph_tools_wiring.py` remain green
- `query.py` contains `SELECT COUNT(*) FROM nodes` in the graph-connection block
- `sweep-judge-signal-collapse.md` frontmatter shows `status: resolved`
- Commit message ends with `Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>`
</success_criteria>

<output>
Create `.planning/quick/260530-jc1-fix-empty-db-graph-tool-binding/SUMMARY.md` when done.
</output>
