# Phase 30: Entry Points + Test Suites — Research

**Date:** 2026-05-25
**Status:** Research complete; ready for planning.

## RESEARCH COMPLETE

CONTEXT.md captured 21 implementation decisions (D-01..D-21). This document
records only what the planner needs that is NOT already in CONTEXT.md —
namely, file-by-file confirmation of the integration surface, manifest-parsing
strategy, and the cross-phase coordination plan with Phase 29.

---

## 1. Cross-phase coordination with Phase 29 (D-01/D-02 amendment status)

**Phase 29 is partially shipped** at the time of Phase 30 planning:

| Commit | Plan | Files | Status |
|--------|------|-------|--------|
| `4d95d07` | 29-01 (SPARSER-01) | source-parser attrs | Shipped |
| `fbd4124` | 29-02 (resolve.sweep uri-guard) | resolve.py | Shipped |
| `fc0474d` | 29-03 (structural_nodes.emit + role flags) | structural_nodes.py | **Shipped — already contains `_is_test_path` (D-09)** |
| (uncommitted in working tree) | 29-04 (update.run wiring + sample_monorepo fixture + STRUCT-04 invariant test) | update.py, tests/fixtures/sample_monorepo/, tests/test_structural_nodes.py | In-flight in sibling agent worktree |

**Implication for Phase 30 (resolving D-02's risk note):**

- D-01 amendment lands as a **Phase 30 hotfix to `structural_nodes.py`** —
  Plan 30-01. The current `_is_test_path` in `structural_nodes.py:122-132`
  is filename-OR-directory; we need filename-AND-not-inside-package-import-root.
- D-19/D-20 (always-on strict-tree invariant at end of `update.run`) and D-21
  (insert `entry_points.emit` + `test_suites.emit` between `structural_nodes.emit`
  and `resolve.sweep`) are unambiguously Phase 30 work — Phase 29 only wires
  the single `structural_nodes.emit` call and adds a **test-only** invariant
  assertion against the fixture. The always-on runtime check is new.
- The sample_monorepo fixture from Phase 29-04 must exist before Phase 30
  plans 30-02 / 30-03 / 30-04 / 30-05 run — Phase 30 EXTENDS the fixture
  (D-19(a) adds `packages/mypkg/tests/test_foo.py`, `tests/integration/test_top.py`,
  `jspkg/__tests__/index.test.js`).

**Execution order:** Phase 30 cannot start execute-phase until Phase 29 is
marked complete (i.e., 29-04 lands). The planner does not need to model this —
`gsd-execute-phase` for Phase 30 will simply fail at the fixture-extension
task if `sample_monorepo/` does not exist on disk. The planner DOES need to
write task `read_first` blocks against the post-Phase-29 expected file paths.

## 2. Integration points in `update.py` (D-21)

Current state (Phase 29-03 + uncommitted 29-04 edits):

```python
# packages/graph-io/src/graph_io/update.py:234-258
with store.transaction(conn):
    _process_files(conn, repo_root, changed, skip_dirs)
    packages.refresh(conn, repo_root=repo_root, ctx=ctx)
    if full:
        # ... full-rebuild DELETE ...
    from graph_io import structural_nodes  # noqa: PLC0415
    structural_nodes.emit(conn, repo_root=repo_root, ctx=ctx, skip_dirs=skip_dirs)
    resolve.sweep(conn)
    _set_metadata(conn, "last_indexed_commit", head)
    _set_metadata(conn, "last_indexed_at", _dt.datetime.now(_dt.UTC).isoformat())
```

Phase 30 edits (Plan 30-05):

```python
with store.transaction(conn):
    _process_files(conn, repo_root, changed, skip_dirs)
    packages.refresh(conn, repo_root=repo_root, ctx=ctx)
    if full:
        # ... full-rebuild DELETE ...
    from graph_io import entry_points, structural_nodes, test_suites  # noqa: PLC0415
    structural_nodes.emit(conn, repo_root=repo_root, ctx=ctx, skip_dirs=skip_dirs)
    entry_points.emit(conn, repo_root=repo_root, ctx=ctx, skip_dirs=skip_dirs)
    test_suites.emit(conn, repo_root=repo_root, ctx=ctx, skip_dirs=skip_dirs)
    resolve.sweep(conn)
    _enforce_strict_tree_invariant(conn)  # D-19(b)
    _set_metadata(conn, "last_indexed_commit", head)
    _set_metadata(conn, "last_indexed_at", _dt.datetime.now(_dt.UTC).isoformat())
```

`_enforce_strict_tree_invariant` is a new module-private function in `update.py`,
co-located with the other update-orchestration helpers. The implementation is
the literal SQL from CONTEXT.md §specifics — one `SELECT child_id, COUNT(*)`
with `GROUP BY child_id HAVING n > 1` against `kind='physically_contains'`,
raising `StrictTreeInvariantError` (also defined in `update.py`, alongside
`NotInGitRepoError` / `UpdateInProgressError`) when rows are returned.

`_enforce_strict_tree_invariant` runs INSIDE the same `with store.transaction(conn):`
block but AFTER `resolve.sweep`. Raising inside the transaction triggers
rollback (matching the existing `_set_metadata` behavior on exception) — the
on-disk DB is left in the pre-`cg update` state. Exit code is non-zero via
the CLI's uncaught-exception path (no special handling needed in the CLI
layer for v1.6).

## 3. Manifest parsing strategy (ENTRY-01, ENTRY-02)

Stack notes (already confirmed in `.planning/research/STACK.md`):

- Python: `tomllib` (stdlib, 3.11+) — no new deps.
- JS/TS: `json` (stdlib).
- Both already used elsewhere in `graph-io` (`packages.refresh` reads
  `pyproject.toml` and `package.json`; see `packages.py`).

### `pyproject.toml` shape (ENTRY-01)

```toml
[project.scripts]
graph-wiki-agent = "graph_wiki_agent.cli:main"
graph-wiki-mcp   = "graph_wiki_agent.mcp:main"

# Or the modern PEP 621 form (D-21 / D-22):
[project.entry-points."console_scripts"]
foo = "foo_pkg.cli:run"

# Library plugin entry points:
[project.entry-points."myapp.plugins"]
my_plugin = "my_plugin.entry:Plugin"
```

Phase 30 reads:
- `[project.scripts]` — `kind=executable`, `source=pyproject.scripts`,
  callable always present (PEP 621 mandates `module:func` form).
- `[project.entry-points."<group>"]` — `kind=executable` for `console_scripts`;
  `kind=library` for everything else. `source=pyproject.entry-points.<group>`.
  Value form is identical (`module:callable`).

### `package.json` shape (ENTRY-02)

```jsonc
{
  "main":    "./index.js",              // library, source: package.json.main
  "module":  "./index.mjs",             // library, source: package.json.module
  "bin":     "./cli.js",                // executable, name=<package.name>
  // OR object form:
  "bin": { "foo-cli": "./foo.js" },     // executable, one per key

  "exports": {                          // library, recursive walk, D-07
    ".": "./index.js",
    "./submodule": "./sub.js",
    "./conditional": {
      "import":  "./esm.js",            // EntryPoint.condition="import"
      "require": "./cjs.js"             // EntryPoint.condition="require"
    },
    "./*": "./src/*.js"                 // is_wildcard=true, implemented_by=NULL
  }
}
```

`exports` recursion algorithm: depth-first walk. At each node:
- If value is string → leaf EntryPoint, `name=<key path>`, `condition=NULL`
  if key is at root, else `condition=<last key in path>` when key matches
  a known condition (`import`, `require`, `default`, `node`, `browser`,
  `types`).
- If value is object → recurse, building `name` from the path of "./"-keys
  and `condition` from the last condition-key encountered.
- If value contains `*` → `is_wildcard=true`, `path_pattern=value`,
  `implemented_by=NULL`.

Conditional-export key set (the keys NOT prefixed with `./`):
`{"import", "require", "default", "node", "browser", "types", "deno", "worker"}`
— any string from this set inside `exports` is a condition, not a sub-path.

## 4. `implemented_by` strict resolution (D-05, ENTRY-04)

For Python `module:callable` entries:
1. Look up the declaring `Package` row (the pyproject.toml that contained
   the entry).
2. Apply Phase 29 D-06 `_resolve_import_root(pkg_dir, importable)` to get
   `<pkg_dir>/src/<importable>/` or `<pkg_dir>/<importable>/`.
3. Walk the dotted prefix: `graph_wiki_agent.cli` → `<import_root>/cli.py`.
   `graph_wiki_agent.subpkg.thing:f` → `<import_root>/subpkg/thing.py`.
4. If the file exists on disk → emit `implemented_by → File(<that path>)`.
5. If not → emit `EntryPoint` with `implemented_by=NULL` and print warning
   (D-06).

For JS/TS path-only entries (`package.json` "main", "bin", "exports" leaves):
1. The manifest value IS the relative path. Resolve against the Package
   directory.
2. Strip leading `./`, normalize.
3. If the file exists → `implemented_by → File(<that path>)`.
4. If not → `implemented_by=NULL` + warning.

**Anti-pattern (forbidden by D-05):** `SELECT id FROM nodes WHERE kind='file'
AND name='main.py' LIMIT 1` — globally ambiguous. Always resolve from the
declaring Package's import root.

## 5. TestSuite emission strategy (TEST-01..07)

### Test root discovery

1. **Conventional roots (always scanned):**
   - Repo-root `tests/`
   - Package-local `<pkg.path>/tests/`
   - JS package-local `<pkg.path>/__tests__/` (alternate convention)

2. **Config-discovered roots (D-18):**
   - `pyproject.toml [tool.pytest.ini_options] testpaths = ["spec"]` →
     add `spec/` (relative to the pyproject.toml's parent).
   - `pytest.ini [pytest] testpaths = ...` — same shape.
   - `jest.config.{js,ts,mjs,cjs,cjs}` `testMatch` / `roots` — D-18 narrows
     to ONLY `roots` (testMatch is glob-based, harder to map to directories).
     Parse the config as JSON/JS; if parsing fails (CJS/ESM exports), skip
     silently and rely on conventional roots.
   - `vitest.config.*` — same as jest.

3. **Per-Package containment determination:**
   - A discovered test root is **package-local** if its path is inside any
     Package's directory (and not inside a `tests/` directory that belongs
     to a sibling/parent Package — deepest Package wins, mirroring
     `_owning_package` in `structural_nodes.py`).
   - Otherwise it is **repo-root** (contained by Repository).

### Suite naming (D-16, Claude's discretion)

Pick **directory-relative naming** for predictability:
- Repo-root `tests/integration/` → `TestSuite.name = "tests/integration"`.
- Repo-root `tests/` (flat) → `TestSuite.name = "tests"`.
- Package-local `packages/mypkg/tests/` → `TestSuite.name = "tests"` with
  `path = "packages/mypkg/tests"` (the path discriminates).
- JS `__tests__/` → `TestSuite.name = "__tests__"` with the path discriminator.

URI shape (Phase 28's `test_suite_uri`): `test_suite:{org}/{repo}/{suite_name}`
where `suite_name` is the path (suite identity is location-based). Update
`uri.test_suite_uri` to take a `path` argument if not already shaped that way
(it currently takes `suite_name: str`, which the planner can pass `path` into
— stable identity across runs).

### `tests` edge derivation (D-09..D-12)

For each test file in a suite:
1. Parse imports (regex-based, no AST needed — keep it cheap):
   - Python: `^\s*(?:from|import)\s+([\w\.]+)` — extract the top-level module
     (`X` from `X.Y.Z`).
   - JS/TS: `from\s+['"]([^'"]+)['"]` and `require\(['"]([^'"]+)['"]\)` —
     extract the bare specifier (no relative paths for the bare-spec branch;
     relative paths handled separately via `_owning_package` lookup).
2. Build `{importable_name → Package}` map once at start of `test_suites.emit`:
   - Python: `Package(name="graph-io")` has importable `graph_io`. Derive
     from `pkg_name.replace("-", "_")` PLUS read `_resolve_import_root`'s
     existence to confirm the importable exists.
   - JS/TS: use `Package.name` from `package.json` directly.
3. For each import:
   - Bare spec → map lookup → emit `TestSuite → Package` if found.
   - Relative spec → resolve against importing file's dir → use
     `structural_nodes._owning_package` against the resolved path → emit
     `TestSuite → Package` for the owning Package.
4. Deduplicate per (suite_id, package_id) pair — one edge per pair regardless
   of import count.
5. If `len(distinct_packages) >= _REPOSITORY_EDGE_THRESHOLD` (=5) → emit
   one additional `TestSuite → Repository` edge.

## 6. Test file re-parenting (D-14, D-15, TEST-04)

The DELETE-then-INSERT pattern in CONTEXT.md D-14 is the correct shape, but
must target the `edges` table with the right column names. Confirmed against
`packages/graph-io/src/graph_io/schema.py`:

```sql
CREATE TABLE edges (
  id INTEGER PRIMARY KEY,
  src INTEGER NOT NULL,          -- parent node id
  dst INTEGER NOT NULL,          -- child node id
  kind TEXT NOT NULL,
  attrs_json TEXT,
  UNIQUE (src, dst, kind)
);
```

The actual delete-then-insert uses `src`/`dst` not `parent_id`/`child_id`:

```python
with conn:
    for test_file in test_files:
        suite_id = suite_node_ids[assign_suite(test_file)]
        file_id  = test_file_node_ids[test_file]
        conn.execute(
            "DELETE FROM edges WHERE kind = 'physically_contains' AND dst = ?",
            (file_id,),
        )
        conn.execute(
            "INSERT INTO edges (src, dst, kind, attrs_json) "
            "VALUES (?, ?, 'physically_contains', NULL)",
            (suite_id, file_id),
        )
```

The whole emit is already inside `update.run`'s `with store.transaction(conn):`
block (Phase 29 D-21 wiring), so the inner `with conn:` from the CONTEXT D-14
pseudocode is redundant — drop it. Re-parenting is atomic per the outer tx.

`assign_suite(test_file)` follows D-15's 4-rule cascade; the "else" branch
(rule 4) cannot happen after D-01 amendment because no test file will exist
outside a `tests/` ancestor.

## 7. Existing-code reuse map

| Reuse | Source | Used by Phase 30 |
|---|---|---|
| `_upsert_node` URI extraction | `upsert.py:48-59` | EntryPoint + TestSuite node writes |
| `_resolve_import_root` | `structural_nodes.py:208-216` | `implemented_by` path resolution (D-05) |
| `_owning_package` (currently inner func) | `structural_nodes.py:362-368` | Test root containment lookup, relative-import package resolution |
| `_ignore.should_skip` | `_ignore.py` | Manifest scan + test-root scan |
| `_tracked_files` | `structural_nodes.py:199-205` | (Optional) consistency check for fixture-based fallback |
| `uri.entry_point_uri` / `uri.test_suite_uri` | `uri.py:31-36` | Both already present from Phase 28 |
| `tests/fixtures/sample_monorepo/` | Phase 29-04 deliverable | Extended by Plan 30-04 |
| `_run_cli` test helper | `tests/conftest.py` (existing) | Fixture-driven CLI tests |

**Helper hoisting required:** `_owning_package` is currently a closure inside
`structural_nodes.emit`. Plan 30-02 will need it; the cleanest solution is
to hoist it to a module-private top-level function — Plan 30-01 covers this
hoist as part of the `is_test` amendment work since they touch the same file
and adjacent regions.

## 8. Anti-regression coverage (SC#5)

SC#5: `cg describe-package graph-io` continues to return a result and exit 0.

Risk: adding two new emitters that fail mid-emit (e.g., on a malformed
`exports` object) would roll back the whole `cg update` transaction and
leave the DB in pre-Phase-30 state — but `cg describe-package graph-io`
would still work on the old data. The real risk is if the new emitters
WRITE bad data that corrupts later queries.

Mitigation:
- Emitter functions catch and log per-file/per-manifest errors instead of
  propagating, so a malformed `package.json` somewhere in the repo doesn't
  kill the whole `cg update`. **One exception:** schema-level errors (e.g.,
  trying to insert a NULL into a NOT NULL column) propagate and crash —
  those indicate a bug, not bad user data.
- A regression test in `tests/test_queries.py` (or wherever
  `cg describe-package` is exercised) confirms exit code 0 on the
  agent-research repo's own `graph-io` package after Phase 30 emitters run.

## 9. Out-of-scope clarifications

Re-confirming from CONTEXT.md `<domain>` strict-not-in-phase:

- **No CLI surface in Phase 30.** Success criteria mention `cg list-entry-points`
  and `cg list-suites`, but those are Phase 33. Phase 30 SC#1 / SC#2
  ("`cg list-entry-points graph-wiki-agent` returns...") are validated via
  SQL queries against the test DB, not via CLI invocation.
  - The fixture test in Plan 30-04 / 30-05 uses `conn.execute(...)` directly
    on the post-`cg update --full` DB.
- **No Function/Class `implemented_by`** — File-only (D-03), callable name
  stored on `EntryPoint.callable` (D-04).
- **No Domain edges** — TEST-06's `TestSuite → Domain` is deferred to
  Phase 31. Phase 30 emits only `TestSuite → Package` and
  `TestSuite → Repository`.

---

## Validation Architecture

Not applicable for Phase 30 — Nyquist validation isn't ratified for this
project (no prior phase has shipped a VALIDATION.md). The fixture test
in Plan 30-04 + the always-on runtime invariant in Plan 30-05 cover the
"call order" pitfall directly. Dimension-8 dimensional validation can be
revisited once Phase 33's CLI lands and the integration test surface grows.

---

*Phase: 30-entry-points-test-suites*
*Research dated: 2026-05-25*
