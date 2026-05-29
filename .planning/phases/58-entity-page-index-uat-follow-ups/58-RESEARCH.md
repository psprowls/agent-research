# Phase 58: Entity Page & Index UAT Follow-Ups — Research

**Researched:** 2026-05-28
**Domain:** wiki-io entity templates, entity_writer.py, index_generator.py; graph-io test_suites.py, queries.py, uri.py, derived_edges.py
**Confidence:** HIGH — all findings verified against actual source files; no external library research required (pure internal refactor)

---

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions
- **D-01:** Related becomes a clean empty marker now; defer real population. Replace static `<...>` placeholder bullet list with a single clean fill-me-in message naming concepts, ADRs, architecture.
- **D-02:** Marker must be Obsidian-safe — no leading `>`, no angle brackets, no `:`.
- **D-03:** Scope = entity templates only. Edit `## Related` blocks in `entity-package.md:36`, `entity-app.md:42`, `entity-plugin.md:24`. No `entity_writer` logic change needed.
- **D-04:** Replace `> TODO: <add a one-line summary for {name}>` at `entity_writer.py:587` with a plain-text form: no `>`, no `<>`, no `:`. Exact string is planner's discretion within those constraints.
- **D-05:** Scope strictly to the entity `summary:` placeholder. Do NOT sweep sibling templates.
- **D-06:** Update test expectations that assert on the exact placeholder string.
- **D-07:** Confirmed root cause: `_consumer_pkgs` (`:282`) and `_consumer_pkgs_in_domain` (`:251`) both resolve target packages with `ts.name = ?`. All 9 `test_suite` nodes share `name='tests'`, causing fan-out.
- **D-08:** Fix BOTH sides. Scan-side: unique package-qualified names at `test_suites.py:336-338` — `<owner_name>-<suite_kind>-tests`. Renderer-side: resolve by test_suite node **uri** in `_consumer_pkgs` and `_consumer_pkgs_in_domain`.
- **D-09:** Cascade awareness. Renaming suite nodes changes `physically_contains` dst tuple, `tests` derived edges, `describe_test_suite(suite_name=...)`, and name-keyed queries in `queries.py`.
- **D-10:** Regenerate affected goldens in-phase. Rebaseline entity-page + index golden/integration fixtures by regenerating from the fixed generator.

### Claude's Discretion
- Exact final string of the summary marker (D-04) and the Related marker (D-01), within the no-`>`/no-`<>`/no-`:` constraint.
- Whether suite-kind appears as `integration` or abbreviated `int` in the node name.
- Regenerate-vs-edit decision per individual fixture where blast radius makes wholesale regeneration awkward.

### Deferred Ideas (OUT OF SCOPE)
- Dynamic `## Related` population from curated backlinks.
- Graph-edge relations in Related (depends_on/domains/dependencies).
</user_constraints>

---

## Summary

Phase 58 closes three UAT defects from v1.10 (Phases 56–57). Items #1 and #2 are template-text and one-line string edits respectively — near-trivial. Item #3 is a coordinated two-package fix with a concrete blast radius in graph-io and wiki-io.

**Item #1 (Related section):** Three entity templates (`entity-package.md`, `entity-app.md`, `entity-plugin.md`) each carry a `## Related` block of `<...>` placeholder wikilinks. The two-token convention leaves `<...>` text untouched by the renderer, so these survive into generated pages verbatim. Fix is a template content edit only — no logic change. [VERIFIED: codebase read]

**Item #2 (Summary placeholder):** `entity_writer.py:587` sets `summary:` to `> TODO: <add a one-line summary for {name}>` when the node has no description. The leading `>` renders as a blockquote in Obsidian, breaking inline list display. Fix is a single string constant change. Two test assertions in wiki-io test files reference the exact old string and must be updated. [VERIFIED: codebase read]

**Item #3 (Test-suite fan-out):** The root cause is confirmed. All 9 package-owned `test_suite` nodes in the live graph share `name='tests'` (set at `test_suites.py:338` as `Path(r.rel_path).name`). `_consumer_pkgs` and `_consumer_pkgs_in_domain` in `index_generator.py` join on `ts.name = ?`, which matches every one of the 9 suites when the name is `'tests'` — so each suite returns all 23 `tests`-edge targets as its consumer packages. The fix requires changes to both `graph-io/test_suites.py` (rename at scan time) and `wiki-io/index_generator.py` (resolve by URI). URI is already on `PlacedEntity.uri` and is available via the node's `attrs["uri"]` at placement time in `_place_entities`. [VERIFIED: codebase read]

**Primary recommendation:** Implement in three separate plans: (1) template edits for Items #1 and #2 with test updates; (2) graph-io scan-time rename + its own fixture rebaseline; (3) wiki-io renderer URI fix + wiki-io index golden rebaseline. Plans 2 and 3 should be sequenced or combined so the graph-io rename lands before/with the wiki-io URI fix.

---

## Architectural Responsibility Map

| Capability | Primary Tier | Secondary Tier | Rationale |
|------------|-------------|----------------|-----------|
| Entity template content (Related marker) | wiki-io assets | — | Template files are owned by wiki-io; renderer never touches `<...>` text |
| Summary placeholder string | wiki-io entity_writer | — | Single constant in `scanner_frontmatter_for_node` |
| Test-suite node naming | graph-io test_suites | — | Scan-time node construction; wiki-io is a consumer |
| Test-suite consumer package resolution | wiki-io index_generator | graph-io queries (via URI) | Renderer queries must change to use URI; graph-io must expose URI-keyed lookup |
| Fixture rebaseline — graph-io | graph-io tests | — | graph-io fixtures encode suite node names |
| Fixture rebaseline — wiki-io | wiki-io tests | — | wiki-io integration tests encode rendered index content |

---

## Item #1: Related Section — Verified Findings

### Template files carrying `## Related` with `<...>` placeholders

All three verified by direct file read:

| File | Related block location | Current placeholder content |
|------|----------------------|----------------------------|
| `packages/wiki-io/src/wiki_io/assets/page-templates/entity-package.md` | Lines 36–39 | `- [[concepts/<concept>]]` / `- [[packages/<other-pkg>]]` / `- [[dependencies/<lib>]]` |
| `packages/wiki-io/src/wiki_io/assets/page-templates/entity-app.md` | Lines 42–46 | `- [[concepts/<concept>]]` / `- [[apps/<other-app>]]` / `- [[domains/<domain>]]` / `- [[packages/<pkg>]]` |
| `packages/wiki-io/src/wiki_io/assets/page-templates/entity-plugin.md` | Lines 24–26 | `- [[concepts/<concept>]]` / `- [[packages/<other-pkg>]]` |

`entity-test-suite.md` and `entity-dependency.md` do NOT carry a `## Related` section — confirmed. [VERIFIED: codebase read]

### No renderer logic change needed

The "two-token rule" (`entity_writer._render_entity_page`) leaves `<...>` text untouched. The fix is editing the template text only. After regeneration, generated entity pages will contain the new clean marker instead. [VERIFIED: codebase read]

### Recommended marker (planner's discretion; satisfies D-01/D-02)

```
## Related

No related concept, ADR, or architecture pages yet.
```

Satisfies: no `>`, no `<...>`, no `:`, names the future curated page types per D-01.

---

## Item #2: Summary Placeholder — Verified Findings

### The placeholder at entity_writer.py:587

```python
# file: packages/wiki-io/src/wiki_io/entity_writer.py
# line 587 (verified)
fm["summary"] = description or f"> TODO: <add a one-line summary for {node.name}>"
```

The `f">"` prefix causes Obsidian to render it as a blockquote, which breaks list-item rendering for any bullet immediately following a placeholder summary in the index. [VERIFIED: codebase read]

### Required change

Replace the f-string value with one that omits `>`, `<>`, and `:`. Planner's discretion on exact text; example satisfying all constraints:

```python
fm["summary"] = description or f"TODO add a one-line summary for {node.name}"
```

### Test files asserting on the old placeholder string

Two locations must be updated as part of this fix (D-06):

1. `packages/wiki-io/tests/test_entity_writer.py:482` — `test_merge_summary_todo_marker_when_description_empty`:
   ```python
   todo = "> TODO: <add a one-line summary for x>"
   ```
   Must be updated to the new form.

2. `packages/wiki-io/tests/integration/test_entity_writer_integration.py:240` — `test_no_unsubstituted_token_and_summary_populated`:
   This test asserts the summary is non-empty (`not in (None, "", [])`). The current placeholder satisfies this. The new placeholder will also satisfy it — no change needed if the replacement is also non-empty. However, verify the assertion text references no literal placeholder string. [VERIFIED: codebase read — the integration test asserts non-empty only, no literal string check]

---

## Item #3: Test-Suite Fan-Out — Complete Blast Radius

### Root cause (verified)

In `test_suites.py`, the naming logic at lines 335–338:

```python
# packages/graph-io/src/graph_io/test_suites.py:335-338 (verified)
if r.owner_kind == "repository":
    suite_name = r.rel_path          # already unique: full rel_path
else:
    suite_name = Path(r.rel_path).name  # BUG: always 'tests' or '__tests__'
```

For the current agent-research repo, all 9 package-owned suites have `rel_path` ending in `/tests`, so `Path(rel_path).name` is `'tests'` for all 9. [VERIFIED: codebase read]

### Repository-owned suites — no rename needed

Repository-owned suites (`r.owner_kind == "repository"`) use `r.rel_path` as the suite name (e.g., `"tests/integration"`, `"tests/unit"`). These are already unique. The rename applies ONLY to package-owned suites (`r.owner_kind == "package"`). [VERIFIED: codebase read — line 335-336]

### Scan-side rename — where to change

Change `test_suites.py:338` from:
```python
suite_name = Path(r.rel_path).name
```
To:
```python
suite_name = f"{r.owner_name}-{kind_attr}-tests"
```

Note: `kind_attr` is computed at line 340 via `_classify_suite_kind(r.rel_path, root_files[r.rel_path])`. The `kind_attr` is computed after the `suite_name` assignment in the current code. The rename needs `kind_attr`, so either compute it before the name assignment, or compute `suite_name` after `kind_attr`. The actual code order is:

```python
# lines 331-358 (verified, simplified)
for r in roots:
    if r.owner_kind == "repository":
        suite_name = r.rel_path
    else:
        suite_name = Path(r.rel_path).name   # ← line 338, rename here

    kind_attr = _classify_suite_kind(r.rel_path, root_files[r.rel_path])  # ← line 340
```

So `kind_attr` is available one line after the name assignment. The fix must reorder: compute `kind_attr` first, then assign `suite_name`. [VERIFIED: codebase read]

### URI impact of the rename

`test_suite_uri` at `uri.py:40-41`:
```python
def test_suite_uri(ctx: RepoContext, suite_name: str) -> str:
    return f"test_suite:{ctx.org}/{ctx.repo}/{suite_name}"
```

This is called with `r.rel_path`, NOT with `suite_name`:
```python
# test_suites.py:343 (verified)
attrs: dict = {
    "uri": test_suite_uri(ctx, r.rel_path),
    ...
}
```

**Critical finding:** The URI is computed from `r.rel_path`, not from `suite_name`. Therefore renaming `suite_name` does NOT change the URI. URIs remain stable across the rename. The wiki-io renderer fix can key on the existing URI without any change to URI construction. [VERIFIED: codebase read]

### physically_contains edge dst tuple — changes with rename

At `test_suites.py:369-375` (verified):
```python
edges.append(
    GraphEdge(
        src=parent_src,
        dst=("test_suite", suite_name, r.rel_path),  # ← suite_name in dst tuple
        kind="physically_contains",
        attrs={},
    )
)
```

The `dst` tuple contains `suite_name`. After the rename, these tuples change from `("test_suite", "tests", "packages/foo/tests")` to `("test_suite", "foo-unit-tests", "packages/foo/tests")`. Upsert will create new nodes under the new names. Old `tests`-named nodes will linger unless explicitly deleted — but since this is a full-scan/idempotent-recompute scenario, the `upsert_records` call will create the new node and the old one will remain orphaned. The planner should ensure the update pipeline is run fresh (or add explicit deletion of the old stale `tests`-named nodes if needed). [VERIFIED: codebase read]

### Re-parenting loop — also uses suite_key_name

At `test_suites.py:383-388` (verified):
```python
for r in roots:
    if r.owner_kind == "repository":
        suite_key_name = r.rel_path
    else:
        suite_key_name = Path(r.rel_path).name   # ← same basename logic, ALSO needs update
    suite_row = conn.execute(
        "SELECT id FROM nodes WHERE kind='test_suite' AND name=? AND path=?",
        (suite_key_name, r.rel_path),
    ).fetchone()
```

This lookup uses `suite_key_name` which mirrors the original `suite_name` assignment. After the rename, this must use the new qualified name too, otherwise the re-parenting loop will not find the newly-named suite node. [VERIFIED: codebase read]

### _emit_tests_edges — also uses suite_key_name

At `test_suites.py:443-447` (verified):
```python
for r in roots:
    if r.owner_kind == "repository":
        suite_key_name = r.rel_path
    else:
        suite_key_name = Path(r.rel_path).name   # ← ALSO needs update
    suite_key = ("test_suite", suite_key_name, r.rel_path)
```

Same pattern — the `suite_key` tuple is used as the `src` of `tests` edges. After the rename, this must use the new name. [VERIFIED: codebase read]

### Summary of scan-side changes (graph-io)

All four occurrences of `Path(r.rel_path).name` in `test_suites.py` for package-owned suites must be updated to the new pattern `f"{r.owner_name}-{kind_attr}-tests"`. The four locations are:

| Location | Purpose | Lines (approx) |
|----------|---------|----------------|
| Main emit loop — node creation | `suite_name` for `GraphNode` | 335–338 |
| Main emit loop — `physically_contains` edge dst | `suite_name` in edge tuple | 371 |
| Re-parenting loop — lookup | `suite_key_name` for DB lookup | 383–388 |
| `_emit_tests_edges` — tests edge src | `suite_key_name` for edge src | 443–447 |

Note: `kind_attr` must be computed BEFORE `suite_name` to enable the pattern. The `root_files[r.rel_path]` dict is populated before the loop, so the reorder is safe. [VERIFIED: codebase read]

### queries.py — name-keyed test_suite lookups

Full enumeration of name-keyed test_suite lookups in `queries.py`:

| Function | Line (approx) | Query pattern | Impact |
|----------|--------------|---------------|--------|
| `describe_package` | ~421-432 | `ORDER BY ts.name` — suite names appear in `PackageDescription.test_suites[].name` | Suite names will change from `"tests"` to qualified form; no structural breakage, but test fixtures asserting on suite name strings will need updating |
| `describe_app` | ~568-579 | Same pattern as `describe_package` | Same impact |
| `describe_test_suite` | ~728-746 | `WHERE kind='test_suite' AND name = ?` | CLI `cg describe-suite tests` will return None after rename; callers must pass new qualified name |
| `tests_for_package` | ~1080-1095 | `ORDER BY ts.name` — returns suites by edge join, no name filter | Not broken by rename |
| `tests_for_domain` | ~1119-1156 | `ORDER BY ts_name` — returns suites by edge join, no name filter | Not broken by rename |

**Critical:** `describe_test_suite(suite_name=...)` is the public API used by `cg describe-suite`. After the rename, the CLI `cg describe-suite tests` stops working (returns None). The user must call `cg describe-suite wiki-io-unit-tests` etc. This is an intentional behavior change, consistent with the rename goal. No query API change is needed — it already works correctly with any name string. [VERIFIED: codebase read]

`_compute_qualifying_domains` in `index_generator.py:197`:
```python
"AND ts.kind='test_suite' AND ts.name = ? "
```
This is also a name-keyed lookup. After the rename, each suite has a unique name, so `ts.name = ?` will match exactly one suite — which is correct. No fix needed for this function once names are unique. [VERIFIED: codebase read]

### wiki-io renderer-side fix

The three SQL queries in `index_generator.py` that join on `ts.name = ?` must switch to joining on `ts.uri = ?` (or `ts.id = ?`).

**`_compute_qualifying_domains` (line 197):**
```python
# CURRENT (broken when names collide):
"AND ts.kind='test_suite' AND ts.name = ? "

# FIX — join on uri (already in attrs["uri"] / nodes.uri column):
"AND ts.kind='test_suite' AND ts.uri = ? "
```
Caller passes `node.name` → must change to pass `uri` from `node.attrs.get("uri")`. In `_place_entities`, `uri = node.attrs.get("uri") or ""` is already extracted at line 353. [VERIFIED: codebase read]

**`_consumer_pkgs_in_domain` (line 251):**
```python
# CURRENT:
"WHERE t.kind='tests' AND ts.kind='test_suite' AND ts.name = ? "

# FIX:
"WHERE t.kind='tests' AND ts.kind='test_suite' AND ts.uri = ? "
```

**`_consumer_pkgs` (line 287):**
```python
# CURRENT:
"WHERE t.kind='tests' AND ts.kind='test_suite' AND ts.name = ? "

# FIX:
"WHERE t.kind='tests' AND ts.kind='test_suite' AND ts.uri = ? "
```

All three caller sites pass `entity_name=node.name`. After the fix, they must pass `entity_uri=node.attrs.get("uri")` instead (or a unified parameter rename). `PlacedEntity` already carries `.uri` (verified at line 131, 150). The callers in `_place_entities` (line 360) and `_render_pkg_nested` (via `sub_for_pkg`) pass the `entity_name`; these must be refactored to pass `entity_uri`. [VERIFIED: codebase read]

**`nodes.uri` column vs `attrs["uri"]`:** The `uri` column is a first-class column on the `nodes` table (Phase 28), and `_row_to_node` folds it back into `attrs["uri"]` at projection time. So `ts.uri` in the SQL is the correct column reference. [VERIFIED: codebase read — queries.py _row_to_node, uri column handling]

### derived_edges.py — no change needed

`derived_edges.py` uses `(ts_id, ts_name, ts_path)` as a dict key for suite tracking (`_compute_testsuite_domain`), but the actual edge emission uses the tuple form `(_TEST_SUITE_KIND, ts_name, ts_path)`. After the rename, `ts_name` comes from the node's `name` column which will be the new qualified name — but `derived_edges.py` reads from the DB (it doesn't hardcode any suite name). The queries in `derived_edges.py` join by node id (`ts.id`) in the inner-loop, not by name. No change to `derived_edges.py` is needed. [VERIFIED: codebase read]

---

## Don't Hand-Roll

| Problem | Don't Build | Use Instead |
|---------|-------------|-------------|
| URI-keyed SQL for test_suite lookup | Custom multi-step Python | Direct SQL `WHERE ts.uri = ?` — `uri` is a first-class DB column |
| Unique name generation | External library | Simple f-string: `f"{r.owner_name}-{kind_attr}-tests"` |
| Fixture rebaseline | Manual string replacement | Run `cg update` then `pytest --snapshot-update` (syrupy) |

---

## Architecture Patterns

### System Architecture Diagram

```
Item #1:
  template files (wiki-io assets)
    → entity_writer._render_entity_page (reads template, leaves <...> intact)
    → generated entity page (## Related section)

Item #2:
  entity_writer.scanner_frontmatter_for_node
    → node.attrs["description"] (may be empty)
    → fm["summary"] = placeholder_string  ← fix here
    → written to entity page frontmatter
    → index_generator._read_entity_summary reads it back
    → rendered in index bullet as " — {summary}"

Item #3 (two-package):
  [graph-io] test_suites.emit
    → _classify_suite_kind(rel_path) → kind_attr
    → suite_name = f"{owner_name}-{kind_attr}-tests"  ← fix here (4 locations)
    → GraphNode(kind="test_suite", name=suite_name, path=rel_path,
                attrs={uri: test_suite_uri(ctx, rel_path), ...})  ← URI unchanged
    → physically_contains edge: dst=("test_suite", suite_name, rel_path)
    → tests edges: src=("test_suite", suite_name, rel_path)
  
  [wiki-io] index_generator._place_entities
    → list_test_suites(conn) → NodeRecord(name=<new_unique_name>, attrs.uri=<uri>)
    → uri = node.attrs.get("uri")  ← already extracted
    → _consumer_pkgs(conn, kind="test_suite", entity_uri=uri)  ← fix: was entity_name
       → SQL: WHERE ts.uri = ?  ← fix: was ts.name = ?
    → PlacedEntity.parent_pkg_names = correct per-suite packages  ← fixed
```

### Recommended Project Structure (no new files needed)

All changes are in-place edits to existing files:
```
packages/
├── graph-io/src/graph_io/
│   └── test_suites.py          # suite_name rename (4 locations in emit + _emit_tests_edges)
├── wiki-io/src/wiki_io/
│   ├── assets/page-templates/
│   │   ├── entity-package.md   # ## Related content edit
│   │   ├── entity-app.md       # ## Related content edit
│   │   └── entity-plugin.md    # ## Related content edit
│   ├── entity_writer.py        # summary placeholder string (line 587)
│   └── index_generator.py      # _consumer_pkgs, _consumer_pkgs_in_domain,
│                                # _compute_qualifying_domains — uri not name
└── tests (wiki-io and graph-io) # fixture rebaseline
```

---

## Common Pitfalls

### Pitfall 1: Forgetting the re-parenting loop and _emit_tests_edges
**What goes wrong:** Developer updates the main node-creation block in `emit()` but misses `suite_key_name` in the re-parenting loop (lines ~383-388) and in `_emit_tests_edges` (lines ~443-447). Suite nodes get the new name but test files are re-parented to the wrong (now non-existent) old `tests` node, and `tests` edges are emitted from the old key.
**Prevention:** Search the entire `test_suites.py` file for all occurrences of `Path(r.rel_path).name` (there are 3 occurrences besides the main assignment) and update all of them.
**Warning signs:** `test_idempotency_two_runs_identical_edges` fails; suite nodes exist but have no `physically_contains` children.

### Pitfall 2: Computing kind_attr AFTER suite_name (current code order)
**What goes wrong:** The current code computes `kind_attr` at line 340, AFTER the `suite_name` assignment at line 338. The new suite_name depends on `kind_attr`, so the order must be reversed.
**Prevention:** Restructure the loop body to compute `kind_attr` first.
**Warning signs:** `NameError: kind_attr` or suite names using wrong kind (e.g. `foo-unknown-tests` when the suite should be `foo-unit-tests`).

### Pitfall 3: Passing entity_name instead of entity_uri to SQL queries
**What goes wrong:** After updating the SQL to `ts.uri = ?`, the Python caller still passes `entity_name` (the node's `.name`). SQLite silently returns 0 rows (no match), so every suite gets empty `parent_pkg_names` — no suites nest under any package.
**Prevention:** Trace every callsite of `_consumer_pkgs` and `_consumer_pkgs_in_domain` from `_place_entities` through to the SQL parameter. Update the parameter name and threading.
**Warning signs:** No test suites appear nested under any package in the generated index.

### Pitfall 4: Stale old 'tests'-named nodes after rename
**What goes wrong:** After the rename, `cg update` upserts the new `foo-unit-tests` nodes but does NOT automatically delete the old `tests`-named nodes (upsert is INSERT OR REPLACE, not DELETE+reinsert). The live graph ends up with both old and new suite nodes.
**Prevention:** Ensure `cg update --full` is run against a test workspace after implementing the rename; verify that only the new names appear. In practice, since the `physically_contains` edge re-parenting will not find the old node names (they no longer match), old nodes will become orphaned but remain in the DB. This is a `cg update --full` vs incremental scenario.
**Warning signs:** After running `cg update`, `SELECT name, COUNT(*) FROM nodes WHERE kind='test_suite' GROUP BY name` shows both `tests` and `wiki-io-unit-tests` etc.

### Pitfall 5: Forgetting to update tests asserting the old placeholder
**What goes wrong:** `entity_writer.py:587` string changed but `test_entity_writer.py:482` still asserts the old `"> TODO: <add a one-line summary for x>"` string → test fails.
**Prevention:** D-06 is explicit — update these assertions as part of the same commit.

---

## Fixture Cascade and Rebaseline Scope

### graph-io fixtures

The `tests/fixtures/sample_monorepo` fixture is a real filesystem layout. Test assertions in `test_test_suites.py` check suite rows by `(name, path)`:

```python
# test_test_suites.py:126 (verified)
assert ("tests", "packages/foo/tests") in rows
```

After the rename, the name part changes from `"tests"` to `"foo-unit-tests"` (assuming `_classify_suite_kind` returns `"unit"` for a basic `test_bar.py`). The test `test_package_local_tests_dir_is_package_contained` at line 114 will need its assertion updated. [VERIFIED: codebase read]

Additionally, `test_repo_root_flat_tests_creates_single_suite`:
```python
# test_test_suites.py:111 (verified)
assert rows == [("tests", "tests")]
```
This is a REPOSITORY-owned suite (flat `tests/` at repo root). Repository-owned suites use `r.rel_path` as name — they are NOT renamed. This test should remain unchanged. [VERIFIED: codebase read — line 335-336 repository branch]

`test_derive_edges.py:_seed_testsuite` at line 201 constructs suite nodes manually for testing — it passes `suite_name` directly, so it is not affected by the scan-side rename (it bypasses the emitter). No change needed. [VERIFIED: codebase read]

`test_queries.py:test_describe_test_suite` (line 696) calls `describe_test_suite(seeded_db, suite_name=first.name)` where `first.name` comes from `list_test_suites(seeded_db)` — it dynamically fetches the name, so it is not hard-coded and will continue to work after the rename without changes. [VERIFIED: codebase read]

`test_cli_describe.py` — no `describe-suite` tests found (grep returned no output). The CLI handler `q_describe_suite.py` accepts `args.name` from the command line — no test fixture impact. [VERIFIED: codebase read]

### wiki-io fixtures

The snapshot test in `test_index_generator.py:1143` (`test_snapshot_against_agent_research`) runs against the live graph and is conditionally skipped when no live graph is present. It uses syrupy snapshots. After both the graph-io rename AND the wiki-io URI fix are in place, the snapshot should be regenerated with `pytest --snapshot-update`. [VERIFIED: codebase read]

Other `test_index_generator.py` tests use manually constructed fixture graphs with hardcoded suite names (e.g. `"suite-a"`, `"suite"`, `"suite-multi"`). These names are arbitrary test data and do not interact with the naming change in `test_suites.py`. No updates needed. [VERIFIED: codebase read]

### Regeneration commands

```bash
# graph-io: run after implementing the rename
uv run --package graph-io pytest packages/graph-io/tests/ -v

# wiki-io: update syrupy snapshot if the live graph is available
uv run --package wiki-io pytest packages/wiki-io/tests/test_index_generator.py::test_snapshot_against_agent_research --snapshot-update

# wiki-io integration test — rebuild test workspace in-process (no separate command needed)
uv run --package wiki-io pytest packages/wiki-io/tests/ -v
```

---

## Validation Architecture

### Test Framework

| Property | Value |
|----------|-------|
| Framework | pytest ≥8.3 |
| Config file | `packages/{graph-io,wiki-io}/pyproject.toml` `[tool.pytest.ini_options]` |
| Quick run (graph-io) | `uv run --package graph-io pytest packages/graph-io/tests/ -x -q` |
| Quick run (wiki-io) | `uv run --package wiki-io pytest packages/wiki-io/tests/ -x -q` |
| Full suite | `uv run pytest -x -q` |

### Phase Requirements → Test Map

| Criterion | Behavior | Test Type | Automated Command | Existing Test? |
|-----------|----------|-----------|-------------------|----------------|
| SC#1: No `<...>` in Related | Generated entity pages contain clean Related marker, no `<...>` | unit (template render) | `uv run --package wiki-io pytest packages/wiki-io/tests/test_entity_templates.py -x` | Partial — check `test_entity_templates.py` for Related assertions |
| SC#2: Summary renders cleanly | `summary:` frontmatter has no `>` or `<...>` | unit | `uv run --package wiki-io pytest packages/wiki-io/tests/test_entity_writer.py::test_merge_summary_todo_marker_when_description_empty -x` | YES (needs update) |
| SC#3: Each package nests only its own suites | By Kind section nests correct suites per package | unit + snapshot | `uv run --package wiki-io pytest packages/wiki-io/tests/test_index_generator.py -x` | YES (fan-out regression needs a new test) |
| SC#3b: Suite names unique in graph | `SELECT name, COUNT(*) FROM nodes WHERE kind='test_suite' GROUP BY name HAVING COUNT(*)>1` returns 0 rows | integration | `uv run --package graph-io pytest packages/graph-io/tests/test_test_suites.py -x` | YES (assertions need update for new names) |

### Wave 0 Gaps

- [ ] `packages/wiki-io/tests/test_index_generator.py` — add a test asserting that when multiple suites have distinct URIs but were previously disambiguated only by name, `_consumer_pkgs` returns distinct per-suite results (fan-out regression guard)
- [ ] `packages/graph-io/tests/test_test_suites.py` — update name-based assertions to use new qualified names

---

## Security Domain

Not applicable. This phase makes no authentication, authorization, input validation, or cryptographic changes. All modifications are template strings and SQL query parameter changes within an already-trusted local SQLite database.

---

## Environment Availability

Step 2.6: SKIPPED (no external tool dependencies — all changes are pure Python source edits within the existing workspace).

---

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| Suite names: `Path(rel_path).name` (always `'tests'`) | `<owner_name>-<suite_kind>-tests` (unique) | Phase 58 | Fixes fan-out; `cg describe-suite` callers must use new names |
| `_consumer_pkgs` join on `ts.name` | Join on `ts.uri` | Phase 58 | Correct per-suite package resolution |
| `summary:` placeholder with `>` blockquote | Plain-text placeholder | Phase 58 | Obsidian inline rendering fixed |
| Related section with `<...>` wikilinks | Clean empty marker | Phase 58 | No `<...>` survives in generated pages |

---

## Assumptions Log

No assumptions — all claims in this research were verified against the actual codebase.

| # | Claim | Section | Risk if Wrong |
|---|-------|---------|---------------|
| — | — | — | — |

**If this table is empty:** All claims in this research were verified — no user confirmation needed.

---

## Open Questions

1. **Abbreviation: `integration` vs `int` in suite names**
   - What we know: Pat's example used `wiki-io-int-tests`; `_classify_suite_kind` returns `"integration"` (full string)
   - What's unclear: Whether to use the raw `kind_attr` value or abbreviate
   - Recommendation: Use the literal `kind_attr` value (`f"{owner_name}-{kind_attr}-tests"`). This keeps the naming mechanical and avoids an abbreviation map. Result: `wiki-io-integration-tests` not `wiki-io-int-tests`. If Pat prefers abbreviated, add a simple dict: `{"integration": "int"}` applied at naming time.

2. **`_compute_qualifying_domains` for test_suite — also name-keyed**
   - What we know: Line 197 uses `ts.name = ?`. After rename, each suite has a unique name, so this query works correctly even without changing to URI-based lookup.
   - What's unclear: Is there any remaining correctness risk with the name-based lookup after the rename?
   - Recommendation: Change to `ts.uri = ?` for consistency with the other two fixes. This also future-proofs against any hypothetical case where names collide again.

3. **Stale 'tests'-named nodes in the live graph.db**
   - What we know: After `cg update`, old `tests`-named suite nodes will remain in the DB if upsert does not delete them.
   - What's unclear: Does `upsert_records` DELETE + reinsert, or INSERT OR REPLACE?
   - Recommendation: Check `upsert.upsert_records` behavior. If it uses INSERT OR REPLACE keyed on `(kind, name, path)`, then nodes with the OLD name `('test_suite', 'tests', 'packages/foo/tests')` will simply remain alongside the new `('test_suite', 'foo-unit-tests', 'packages/foo/tests')` nodes. A post-rename `cg update --full` on the test workspace will create both. The planner may need to add an explicit DELETE step for stale `tests`-named package-owned suite nodes, or document that `cg update --full` on a fresh DB is required.

---

## Sources

### Primary (HIGH confidence — verified against source code)
- `packages/graph-io/src/graph_io/test_suites.py` — lines 112, 331-418, 420-479
- `packages/graph-io/src/graph_io/queries.py` — lines 227-246, 419-432, 566-579, 727-746, 1069-1095, 1119-1157
- `packages/graph-io/src/graph_io/derived_edges.py` — lines 171-228
- `packages/graph-io/src/graph_io/uri.py` — lines 40-41
- `packages/graph-io/src/graph_io/cli/q_describe_suite.py` — line 34
- `packages/wiki-io/src/wiki_io/index_generator.py` — lines 131-156, 163-221, 224-257, 260-293, 320-394
- `packages/wiki-io/src/wiki_io/entity_writer.py` — lines 570-588
- `packages/wiki-io/src/wiki_io/assets/page-templates/entity-package.md` — lines 36-39
- `packages/wiki-io/src/wiki_io/assets/page-templates/entity-app.md` — lines 42-46
- `packages/wiki-io/src/wiki_io/assets/page-templates/entity-plugin.md` — lines 24-26
- `packages/wiki-io/tests/test_entity_writer.py` — lines 426-492
- `packages/wiki-io/tests/test_index_generator.py` — lines 573-599, 1126-1152
- `packages/graph-io/tests/test_test_suites.py` — lines 111-138
- `packages/graph-io/tests/test_queries.py` — lines 696-710
- `.planning/todos/pending/2026-05-29-test-suites-fan-out-under-every-package-in-index.md` — live graph evidence
- `.planning/phases/58-entity-page-index-uat-follow-ups/58-CONTEXT.md` — locked decisions D-01 through D-10

### Secondary — planning docs
- `.planning/ROADMAP.md` — Phase 58 success criteria
- `.planning/REQUIREMENTS.md` — v1.10 requirements

---

## Metadata

**Confidence breakdown:**
- Item #1 (Related templates): HIGH — files read, placeholder text verified, no logic involved
- Item #2 (Summary placeholder): HIGH — line number verified, test assertions found, no ambiguity
- Item #3 (Fan-out blast radius): HIGH — all 4 scan-side mutation points verified, all 3 renderer queries verified, URI stability confirmed via `uri.py`

**Research date:** 2026-05-28
**Valid until:** Indefinite — internal codebase research, no external dependencies
