# Pitfalls Research — v1.6 graph-io Ontology Expansion

**Domain:** SQLite code-graph store — additive ontology expansion (schema v2, URI identity, new node/edge types)
**Researched:** 2026-05-25
**Confidence:** HIGH (grounded entirely in the existing codebase + research files; no speculative claims)

---

## Critical Pitfalls

### Pitfall 1: Schema Bump Silently Accepted on Create Path

**What goes wrong:**
`store.connect(db_path, create=True)` calls `schema.apply_schema(conn)` unconditionally, which upserts `schema_version` from `SCHEMA_VERSION`. If a developer bumps `SCHEMA_VERSION = 2` in `schema.py` but the DDL still only has `id, kind, name, path, line, attrs_json` (the `uri` column is missing from `_DDL_STATEMENTS`), `create=True` succeeds and writes `schema_version = 2` but the `uri` column does not exist. Any subsequent `upsert.py` code that tries to write to the `uri` column crashes with `OperationalError: table nodes has no column named uri`. The error message does not mention the schema version — it looks like a query bug, not a migration bug.

**Why it happens:**
The `SCHEMA_VERSION` constant and the `_DDL_STATEMENTS` tuple are separate constructs. Bumping the constant does not automatically force the DDL to be correct. The `CREATE TABLE IF NOT EXISTS` guard means the column is never added to an existing table even if the DDL is later corrected — only fresh databases get the new column.

**How to avoid:**
`test_schema.py` must assert the `uri` column exists in the `nodes` table. Add this test to `test_schema.py` before writing any emitter code:
```python
def test_nodes_table_has_uri_column(conn):
    schema.apply_schema(conn)
    cols = {row[1] for row in conn.execute("PRAGMA table_info(nodes)")}
    assert "uri" in cols
```
Run `schema.apply_schema` + `PRAGMA table_info` as the first test. If the DDL lacks the column the test fails immediately, before any emitter is touched.

**Warning signs:**
`OperationalError: table nodes has no column named uri` during emitter tests; `test_schema_version_is_one()` still passes after bump (because the constant changed but the column assertion is absent).

**Phase to address:** Phase A (Foundation — `schema.py` + `store.py` + `uri.py`). This test must exist before Phase B emitters are written.

---

### Pitfall 2: `store.connect(create=True)` Does Not Version-Check Existing Databases

**What goes wrong:**
`store.connect` in `store.py` (line 57-64) calls `schema.apply_schema(conn)` only when `create=True` AND the file does not previously exist. Looking at the code: when the file *does* exist and `create=True` is passed, the existing code path falls into the `else` branch (`_check_schema_version`). This means a dev who ran `cg update --full` on v1.5, then bumps to v1.6 code, calls `cg update --full` again — and `create=True` is passed — will hit `_check_schema_version`, get `SchemaMismatchError`, and the process exits. That is the intended behavior.

However, the `SCHEMA_MISMATCH` exit code (4) is declared in `exit_codes.py` but described in `README.md` as **"reserved — not yet enforced"**. The `cli/main.py` top-level exception handler may catch `SchemaMismatchError` and exit with code `1` (GENERIC) instead of code `4` if the handler is not wired correctly. A user sees exit code 1, reads the error message (if it surfaces), and the README says exit code 4 is not enforced yet — so they have no reliable automation gate.

**Why it happens:**
The wiring between `SchemaMismatchError` (raised in `store.py`) and the `SCHEMA_MISMATCH = 4` exit code (in `exit_codes.py`) does not exist yet. The README comment was written to flag this; it was never closed.

**How to avoid:**
In `cli/main.py`, add a handler:
```python
except store.SchemaMismatchError as exc:
    print(str(exc), file=sys.stderr)
    sys.exit(exit_codes.SCHEMA_MISMATCH)
```
Add a test in `test_cli_exit_codes.py` that seeds a DB with `schema_version=999`, runs a `cg find` command, and asserts exit code `4`. This closes the README "reserved" comment and validates the full wiring path.

**Warning signs:**
`cg find foo` on a v1.5 DB after v1.6 upgrade exits 1 (GENERIC) instead of 4. The README still says `SCHEMA_MISMATCH` is "not yet enforced" after Phase A lands.

**Phase to address:** Phase A (Foundation). Update README and wire exit-code handler together in one commit so they stay in sync.

---

### Pitfall 3: User Downgrades Back to v1.5 Branch — Their DB Has `schema_version=2`

**What goes wrong:**
A developer working on the v1.6 branch runs `cg update --full`, which writes `schema_version=2` to their `code.db`. They switch back to the `main`/v1.5 branch. Now `SCHEMA_VERSION = 1` in the v1.5 code, but the DB has `schema_version=2`. Every `cg` command fails with `SchemaMismatchError`. The user must delete `code.db` and re-run `cg update --full` on the v1.5 branch.

This is not a bug — full rebuild on version mismatch is the documented contract. But it is a sharp developer experience edge that will happen on every branch switch between v1.5 and v1.6 during development.

**Why it happens:**
Mandatory full-rebuild on schema mismatch is the intentional design. The DB is disposable. But developers forget and get confused by a seemingly broken tool.

**How to avoid:**
Add a one-line note to the `SchemaMismatchError` message: `"run 'cg update --full' to rebuild (safe to delete code.db manually)"`. Update `README.md` exit code table to say `SCHEMA_MISMATCH` is now enforced. No code workaround needed — the design is correct. The documentation fix is the mitigation.

**Warning signs:**
PR review feedback: "all my cg commands broke when I switched back to main." The message is confusing because it says "expected 1, found 2" and the user does not know why their DB has version 2.

**Phase to address:** Phase A. When `SchemaMismatchError` message is finalized, include the delete-and-rebuild advice.

---

### Pitfall 4: `upsert.py` URI Field Is Never Written Because `_upsert_node` Does Not Read `node.attrs["uri"]`

**What goes wrong:**
The architecture plan puts URI generation in emitter modules: they set `node.attrs["uri"] = uri_fn(...)` before calling `upsert.upsert_records`. But `_upsert_node` in `upsert.py` currently writes `attrs_json = _serialize(node.attrs)` into the `attrs_json` column and `line` into the `line` column. It has no special handling for `uri`. After adding the `uri` column to the DDL, if `_upsert_node` is not updated to extract `uri` from `node.attrs` and write it to the `uri` column separately, then: (a) the `uri` column stays NULL for all emitted nodes, and (b) the `uri` value is duplicated inside `attrs_json` — wasting storage and making `SELECT WHERE uri=?` ineffective.

**Why it happens:**
`GraphNode` is defined in `source_parser/projections/graph.py` and does not have a `uri` field — it has only `kind, name, path, line, attrs`. Adding a first-class field to `GraphNode` would require touching source-parser. The tempting shortcut is to bury `uri` in `attrs` and never wire it through to the column.

**How to avoid:**
Two acceptable approaches: (a) extend `GraphNode` with an optional `uri: str | None = None` field in `source_parser/projections/graph.py` — cleanest at source; or (b) keep `uri` in `node.attrs` and make `_upsert_node` pop it out before serializing `attrs_json`:
```python
uri = node.attrs.pop("uri", None)
# write uri to uri column, rest to attrs_json
```
Option (b) avoids touching source-parser. Use option (b) for v1.6 to preserve package boundary. Add a test in `test_upsert.py` asserting that a node with `attrs={"uri": "pkg:org/repo/name", "version": "1.0"}` produces `uri="pkg:org/repo/name"` in the column and `attrs_json` without the `uri` key.

**Warning signs:**
`SELECT uri FROM nodes WHERE kind='package'` returns all NULLs after an update; `SELECT attrs_json FROM nodes WHERE kind='package'` contains `"uri": "pkg:..."` — the value is in the wrong column.

**Phase to address:** Phase A (`upsert.py` extension). Test in `test_upsert.py` must fire before any emitter code is written.

---

### Pitfall 5: `resolve.sweep` Deletes New Structural Nodes Because Their `path IS NULL`

**What goes wrong:**
`resolve.py` (line 50-56) deletes nodes where `path IS NULL AND kind != 'package' AND id NOT IN (SELECT dst FROM edges)`. In v1.6, `Repository` nodes and `Domain` nodes will have `path=NULL` (they have no filesystem path — they are purely logical). If a `Repository` node has no incoming edges from other tables at the time `resolve.sweep` runs, it will be deleted as a "spurious placeholder."

Currently, `physically_contains Repository → Package` edges exist with the Repository as the source (`src`), not the destination (`dst`). The cleanup query only protects nodes that appear as `dst` in some edge. A `Repository` node that is only a `src` and never a `dst` will be silently deleted.

**Why it happens:**
The existing cleanup logic was written for AST-only placeholder nodes (e.g., a function called but not yet parsed — it has `path=NULL` and will have an incoming `calls` edge as `dst`). It does not anticipate structural nodes that are sources of edges but not destinations.

**How to avoid:**
Change the cleanup query to exclude all new structural/conceptual node kinds:
```sql
DELETE FROM nodes WHERE path IS NULL
  AND kind NOT IN ('package', 'repository', 'domain', 'test_suite', 'entry_point')
  AND id NOT IN (SELECT dst FROM edges)
```
Add a test in `test_resolve.py` or `test_structural_nodes.py` that seeds a `Repository` node with `path=NULL` and a `physically_contains` edge from it to a `Package`, runs `resolve.sweep`, and asserts the `Repository` node still exists after the sweep.

**Warning signs:**
After `cg update --full`, `cg describe-repo` returns "not found." `SELECT COUNT(*) FROM nodes WHERE kind='repository'` returns 0 after update.

**Phase to address:** Phase B (Structural Nodes). The `resolve.py` guard must be extended the moment `Repository` nodes are emitted. Add the test to Phase B's success criteria.

---

### Pitfall 6: `test_suites.emit` Re-Parenting Deletes All `physically_contains Package → File` Edges For Test Files, Breaking Incremental Updates

**What goes wrong:**
The spec requires test files to be re-parented from `Package → physically_contains → File` to `TestSuite → physically_contains → File`. The implementation deletes the `Package → File` edge and inserts a `TestSuite → File` edge. On a full rebuild this works cleanly. On an incremental update (`cg update` without `--full`), only changed files are re-processed. If a test file is unchanged between runs, `_process_files` does not re-upsert it. `packages.refresh` re-emits `Package → contains → File` edges for all files under the package prefix (including unchanged test files — see `_file_nodes_under` in `packages.py`). If `test_suites.emit` runs after `packages.refresh` and deletes the test containment edges and creates suite-containment edges, the result is correct. But if someone adds `test_suites.emit` before `packages.refresh`, test files get re-parented to suites and then immediately re-parented back to the package by `packages.refresh`.

**Why it happens:**
Call order in `update.py` matters. The architecture spec correctly says `test_suites.emit` runs after `packages.refresh`, but this ordering constraint is implicit and fragile under refactoring.

**How to avoid:**
Document the ordering constraint with a comment in `update.py` directly above the call sequence. Add a test in `test_suites.py` that (a) runs `packages.refresh` then `test_suites.emit` and (b) asserts that after both calls, test files have exactly one `physically_contains` edge (from `TestSuite`, not from `Package`). This test will fail if the order is inverted. The stale-node cleanup block in `update.py` (which currently deletes `kind != 'package' AND path IS NOT NULL AND path NOT IN (tracked_paths)`) should also exclude `TestSuite → File` edges from deletion on incremental runs.

**Warning signs:**
`cg describe-package auth` shows test files in its file list (they should be excluded post-v1.6). `SELECT kind, name FROM nodes WHERE kind='test_suite'` returns suites but `SELECT * FROM edges WHERE kind='physically_contains'` shows suites have no file children.

**Phase to address:** Phase C (EntryPoint + TestSuite). The ordering test must be part of Phase C acceptance criteria.

---

## Moderate Pitfalls

### Pitfall 7: URI Collisions for Packages With the Same Name in Different Repos

**What goes wrong:**
`pkg_uri(org, repo, pkg_name)` produces `pkg:org/repo/name`. Two different packages named `auth` in two different repos get different URIs because `repo` differs. But within a single multi-package repo, if two packages somehow share a `name` field in their `pyproject.toml` (e.g., both declare `name = "utils"`), they collide on URI. The `uri` column is not declared `UNIQUE` in v1.6, so no constraint fires — the second package silently overwrites the first package's URI in the `nodes` row (depending on upsert behavior), or they get separate rows with the same URI value.

**Why it happens:**
Package names in Python are not enforced to be unique within a monorepo at the language level. Two packages in `packages/auth/utils/` and `packages/billing/utils/` can both declare `name = "utils"` in their pyproject.toml. The current `(kind, name, path)` identity in `upsert.py` keeps them separate (different `path`), but the URI `pkg:org/repo/utils` would be the same for both.

**How to avoid:**
In `uri.py`, `pkg_uri` must incorporate the package's path relative to repo root, not just its name: `f"pkg:{org}/{repo}/{rel_path}"` where `rel_path` is the relative directory of the manifest (already available in `packages.py` as `rel_prefix`). This is already implied by the architecture spec but must be explicitly verified. Add a test in `test_uri.py` with two packages in the same repo: assert their URIs differ even if their names are the same.

**Warning signs:**
`cg list-packages` shows only one `utils` package when two exist. `SELECT uri, COUNT(*) FROM nodes WHERE kind='package' GROUP BY uri HAVING COUNT(*) > 1` returns rows.

**Phase to address:** Phase A (uri.py design). Fix in `uri.py` before any emitter generates package URIs.

---

### Pitfall 8: `EntryPoint.implemented_by` Edge Points to a Non-Existent Function Node When Module:Callable Is Used

**What goes wrong:**
Python entry points like `auth.cli:main` mean the callable `main` in module `auth.cli`. The `implemented_by` edge from `EntryPoint → Function` requires a `Function` node named `main` with `path = "src/auth/cli.py"` to exist in the DB. If `_process_files` has not yet parsed `cli.py` (e.g., in a partial update where `cli.py` did not change), the `Function` node may not exist. `entry_points.emit` would create a placeholder node for `main` with `path=None` and emit an `implemented_by` edge pointing at it.

`resolve.sweep` then tries to resolve the placeholder by looking for a node with `kind='function', name='main', path IS NOT NULL`. If there are multiple functions named `main` across different files, the resolution is `ambiguous` — the edge ends up pointing at the wrong file.

**Why it happens:**
The callable resolution problem exists for any cross-file edge (it is exactly what `resolve.sweep` is built for). But `main` is a common function name, making the ambiguity scenario likely.

**How to avoid:**
When parsing `module:callable` in `entry_points.py`, qualify the target: use `path` directly rather than `name`-only resolution. The module `auth.cli` can be converted to a path (`src/auth/cli.py`) by looking up the package's root path and applying Python's module-to-path mapping. If the Function node is found by `(kind='function', name='main', path='src/auth/cli.py')` the edge is unambiguous. If path resolution fails, fall back to a `File`-level `implemented_by` edge (less precise but not wrong). Add a test in `test_entry_points.py` with two packages that both have a function named `main`; verify the `implemented_by` edge targets the correct file, not both.

**Warning signs:**
`cg list-entry-points auth` shows `implemented_by: billing/cli.py:main` (wrong package). `SELECT attrs_json FROM edges WHERE kind='implemented_by'` shows `resolution: ambiguous`.

**Phase to address:** Phase C (entry_points.py). Path-qualified lookup must be the default strategy.

---

### Pitfall 9: `domains.yaml` Package Name Refers to Package `name` Field, Not Directory Name

**What goes wrong:**
`domains.yaml` lists packages by name (e.g., `packages: [auth-service]`). In `domains.py`, `belongs_to_domain` edges are wired by looking up nodes with `kind='package', name='auth-service'`. But the directory on disk may be `packages/auth/` with `pyproject.toml` declaring `name = "auth"` — not `auth-service`. A developer writing `domains.yaml` who looks at the directory structure and types the directory name will get a silent no-match: no error is raised (by design — `domains.py` warns and skips unknown package names). The domain looks empty when queried.

**Why it happens:**
The package `name` field in `pyproject.toml` and the directory name often differ in real monorepos. `domains.yaml` requires the `name` field value, not the directory name, but this is not obvious to a new user.

**How to avoid:**
`domains.emit` must print a warning to stderr for each unresolved package name, including the list of known package names as a hint:
```
warning: domains.yaml: package 'auth-service' not found; known packages: auth, billing, utils
```
Add a test in `test_domains.py` that verifies this warning fires for an unknown name. Document the convention in README (package name = `pyproject.toml [project].name`, not directory name).

**Warning signs:**
`cg list-domains` shows a domain with 0 packages. No error was raised. Developer checks `domains.yaml` and it looks correct.

**Phase to address:** Phase D (domains.py). Warning message is part of Phase D's acceptance criteria.

---

### Pitfall 10: Convention-Based Domain Inference Classifies `tests/` Subdirectories as Domain Candidates

**What goes wrong:**
Convention-based domain inference (spec §9 strategy 2) treats top-level named folders as domain candidates and skips generic folders (`packages/`, `libs/`, `shared/`). But the skip list must also exclude `tests/` (and its immediate subdirectories). A repo with `tests/billing/` at the root would produce a spurious `Domain(billing)` node from convention inference if `tests/` is not explicitly excluded. Worse, the inference would also produce `Domain(integration)` from `tests/integration/` — a common layout pattern.

**Why it happens:**
The spec says "generic containers (`packages/`, `libs/`, `tests/`) explicitly NOT modeled," but the implementation of convention inference must explicitly enumerate which folder names to skip. It is easy to include the exclusion logic for `packages/` and forget `tests/`.

**How to avoid:**
In `domains.py` convention inference, hardcode the skip list to include at minimum: `packages`, `libs`, `apps`, `shared`, `common`, `tests`, `src`, `dist`, `build`. Add a test in `test_domains.py` that scans a repo with a `tests/billing/` directory (no `domains.yaml`) and asserts that no `Domain(billing)` node is created via convention inference.

**Warning signs:**
`cg list-domains` shows domains named `integration`, `e2e`, `unit`, `fixtures` — all derived from test directory names.

**Phase to address:** Phase D (domains.py). Test for false-positive inference must be in Phase D.

---

### Pitfall 11: Derived Edge Computation (`references`, `depends_on`) Runs on Every `cg update` — Even When No Import Graph Changed

**What goes wrong:**
`derived_edges.compute(conn)` clears all existing `references` and `depends_on` edges and recomputes them from scratch on every `cg update`. For a large repo with 200 packages and thousands of import edges, this join (`imports × belongs_to_domain`) runs on every incremental update even if only one unrelated Python file changed. The computation may be slow enough to noticeably degrade incremental update time.

**Why it happens:**
Re-running derived edges unconditionally is the simplest correct approach. The architectural alternative (stage-selective re-runs) is explicitly deferred to v1.7.

**How to avoid:**
For v1.6: add a metadata key `last_domain_config_hash` that stores a hash of `domains.yaml` content. `derived_edges.compute` compares the current hash with the stored hash; if they match AND the import graph has not changed (no new `imports` edges since last run), skip recomputation. This requires tracking whether `_process_files` produced any import-edge changes — non-trivial. A simpler v1.6 mitigation: run `derived_edges.compute` conditionally only if `domains.yaml` exists (skip entirely if no domains are configured). Add a benchmark test in `test_derived_edges.py` against a 50-package seed DB to establish a performance baseline.

**Warning signs:**
`cg update` on a 200-package repo takes >5s for incremental changes. Profiling shows `derived_edges.compute` is the bottleneck.

**Phase to address:** Phase D. Add the domains.yaml existence gate as a baseline optimization. Document the v1.7 re-run optimization as a known limitation.

---

### Pitfall 12: Brand Sweep Renames `LATTICE_GRAPH_LOCK_TIMEOUT_MS` and Breaks Existing User Automation

**What goes wrong:**
`update.py` line 130 reads `os.environ.get("LATTICE_GRAPH_LOCK_TIMEOUT_MS")`. The brand sweep in Phase G renames this to `GRAPH_WIKI_LOCK_TIMEOUT_MS`. Any user (or CI script) that currently sets `LATTICE_GRAPH_LOCK_TIMEOUT_MS` gets silent fallback to the 30-second default without knowing their configuration was ignored.

**Why it happens:**
Env var renames are silent — no `KeyError` fires when the old name is unset. The user set the variable weeks ago, brand sweep lands, their timeout configuration silently stops working.

**How to avoid:**
In `update.py`, read both names with deprecation fallback:
```python
raw = os.environ.get("GRAPH_WIKI_LOCK_TIMEOUT_MS") or os.environ.get("LATTICE_GRAPH_LOCK_TIMEOUT_MS")
if os.environ.get("LATTICE_GRAPH_LOCK_TIMEOUT_MS") and not os.environ.get("GRAPH_WIKI_LOCK_TIMEOUT_MS"):
    print("warning: LATTICE_GRAPH_LOCK_TIMEOUT_MS is deprecated; use GRAPH_WIKI_LOCK_TIMEOUT_MS", file=sys.stderr)
```
Add both names to `.brand-grep-allow` (the old name is intentionally preserved as a deprecated alias). The brand grep gate will otherwise flag the old name in `update.py`.

**Warning signs:**
Brand grep gate flags `LATTICE_GRAPH_LOCK_TIMEOUT_MS` in `update.py` after Phase G and the implementer removes it without adding the deprecation fallback.

**Phase to address:** Phase G (Brand Sweep). The deprecation-fallback pattern must be part of the brand sweep commit.

---

### Pitfall 13: `test_schema_version_is_one()` Test Name Becomes Wrong — But CI Still Passes

**What goes wrong:**
`test_schema.py` line 57 has `def test_schema_version_is_one(): assert schema.SCHEMA_VERSION == 1`. After Phase A bumps `SCHEMA_VERSION = 2`, this test fails. This is a good, expected failure — it should be caught in Phase A. But if the test is simply deleted rather than updated to `test_schema_version_is_two()`, future engineers lose the sentinel that prevents accidental double-bumps.

**Why it happens:**
A failing test with the wrong name is tempting to delete rather than rename. "The version is 2 now, that test is obsolete" — but the test's purpose was to assert the exact version, not "is it one." Deleting it silently removes a guard.

**How to avoid:**
Update the test to `assert schema.SCHEMA_VERSION == 2`. Update the test name to `test_schema_version_is_two`. Keep the test — it remains a meaningful sentinel.

**Warning signs:**
Phase A commit diff shows `test_schema_version_is_one` being deleted rather than updated.

**Phase to address:** Phase A. Review checklist for Phase A must include "version sentinel test updated, not deleted."

---

### Pitfall 14: `conftest.py` `conn` Fixture Uses In-Memory DB Without Schema — New Tests That Call `upsert_records` With `uri` Column Will Fail

**What goes wrong:**
`packages/graph-io/conftest.py` defines a `conn` fixture as `sqlite3.connect(":memory:")` with `PRAGMA foreign_keys = ON` but without `schema.apply_schema(conn)`. After Phase A adds the `uri` column to the DDL, any test using the root `conftest.py` `conn` fixture that tries to write a `uri` column will fail with `OperationalError: table nodes has no column named uri` — but only for code paths that explicitly write to `uri`. Tests using `GraphNode.attrs["uri"]` passing through the normal `upsert.upsert_records` call will fail silently (the `uri` key stays in `attrs_json` because the upsert code never reaches the `uri` column on a schema-less in-memory DB).

**Why it happens:**
The root `conftest.py` fixture intentionally skips `apply_schema` — it is a bare SQLite connection used to test the schema module itself. Tests in `test_packages.py` and `test_upsert.py` define their own local `conn` fixtures that call `store.connect(db, create=True)` (which does apply the schema). The two fixture shapes coexist. New test modules that import the root `conn` without noticing it is schema-less will get unexpected failures.

**How to avoid:**
Add a docstring to `conftest.py` fixture explicitly: `"""Bare in-memory conn, NO schema applied. Use store.connect(tmp_path/'code.db', create=True) when schema is needed."""` New test modules for Phase B+ (structural_nodes, entry_points, test_suites, domains, derived_edges) must all use `store.connect(db, create=True)` fixtures, not the root `conn`. Enforce this in code review: grep for `def conn(` in new test files and verify they call `store.connect`.

**Warning signs:**
A new test like `test_structural_nodes.py` imports `conn` from conftest, calls `structural_nodes.emit(conn, ...)`, gets `OperationalError: no such table: nodes`.

**Phase to address:** Phase B. The warning must be in the fixture as a comment before the first structural-node test is written.

---

## Minor Pitfalls

### Pitfall 15: `package.json exports` Wildcard Subpaths Produce Misleading `EntryPoint` Nodes

**What goes wrong:**
Some `package.json exports` fields use wildcard patterns: `"./features/*": "./dist/features/*.js"`. The custom `_walk_exports` recursive walker in `packages.py` (as designed in STACK.md) emits `EntryPoint` nodes for every leaf string it finds. Wildcard patterns are leaf strings — they produce an `EntryPoint` node with `name="./features/*"` and `source="./dist/features/*.js"`. This is a valid representation but can confuse users who see a literal `*` in entry point names.

**How to avoid:**
In `_walk_exports`, detect wildcard subpath keys (those containing `*`) and tag them in `attrs_json` with `"is_wildcard": true`. Do not suppress them — they are real declarations — but annotate them so CLI output can say "pattern" instead of a specific entry point name. Add a test with a `package.json` containing a wildcard exports pattern.

**Phase to address:** Phase C (entry_points.py).

---

### Pitfall 16: `TestSuite` Detection Finds `conftest.py` — An `is_config: true` File — And Incorrectly Classifies It as a Test Framework Config

**What goes wrong:**
`conftest.py` is a pytest framework config file. The `detect_tests.py` module detects test framework config from filenames. `conftest.py` is not a framework config file in the sense of `pytest.ini` or `pyproject.toml [tool.pytest]` — it is a fixture-definition file that happens to influence test collection. If `detect_tests.py` treats `conftest.py` as a pytest framework config marker, it may produce incorrect `TestSuite.framework = "pytest"` attributions for directories that only contain `conftest.py` but no actual test files.

**How to avoid:**
`detect_tests.py` framework detection should look for `pytest.ini`, `pyproject.toml [tool.pytest.ini_options]`, and `setup.cfg [tool:pytest]` as suite boundary markers. `conftest.py` should not be in the detection list — it is a fixture file, not a suite config. Add a test where a directory has only `conftest.py` and no `test_*.py` files; assert no `TestSuite` node is emitted for that directory.

**Phase to address:** Phase C (detect_tests.py).

---

### Pitfall 17: `domain_contains_domain` Cycle Produces Infinite Loop in `derived_edges.compute`

**What goes wrong:**
If `domains.yaml` declares:
```yaml
domains:
  payments:
    subdomains: [billing]
  billing:
    subdomains: [payments]
```
Then `domain_contains_domain` edges form a cycle. `derived_edges.compute`, if it uses recursive CTE to walk the domain hierarchy, will loop infinitely (SQLite does support `WITH RECURSIVE` but it does not automatically detect cycles in user data).

**How to avoid:**
`domains.emit` must validate the domain hierarchy for cycles before emitting `domain_contains_domain` edges. A simple DFS with a visited set is sufficient. If a cycle is detected, raise a `ValueError` with the cycle path and skip all `domain_contains_domain` edges (emit domain nodes and `belongs_to_domain` edges but not the hierarchy). Add a test in `test_domains.py` that supplies a cyclic `domains.yaml` and asserts a warning is printed and no `domain_contains_domain` edges are emitted.

**Phase to address:** Phase D (domains.py). Cycle detection must be part of the `load_domains` or `domains.emit` validation.

---

### Pitfall 18: `physically_contains` Tree Invariant Broken When Two Packages Both Claim the Same File

**What goes wrong:**
The spec requires each node to have exactly one structural parent (strict tree). But `packages.refresh` already creates `contains` edges (note: `kind='contains'`, not `kind='physically_contains'`) from every package to every file under its directory prefix, including files under sub-packages. A file at `packages/auth/src/auth/utils/helpers.py` will get `contains` edges from the root package (`auth`) AND from any sub-package node that contains it. This is the existing behavior (the spec notes this explicitly in `packages.py` docstring: "a file inside a sub-package will have edges from BOTH the sub-package and the root package").

In v1.6, `structural_nodes.emit` introduces `physically_contains` as the new strict-tree edge kind. If `physically_contains` also allows multiple parents (by following the same prefix-match logic), the strict-tree invariant is violated.

**How to avoid:**
`physically_contains` must be emitted with longest-prefix-wins semantics: a file is physically contained by its deepest structural ancestor only. In `structural_nodes.py`, when emitting `physically_contains Package → File` edges, only emit to the innermost package (the one whose `rel_prefix` is longest). The existing `contains` edge from `packages.py` (multi-parent) stays as-is for backward compatibility — it is a different edge kind. Add a test asserting that each File node has at most one incoming `physically_contains` edge.

**Phase to address:** Phase B (structural_nodes.py). This invariant must be tested from day one.

---

### Pitfall 19: Test Fixtures Containing `pyproject.toml` Are Discovered by `packages.refresh` During Tests

**What goes wrong:**
Test fixtures that create mini-repos with `pyproject.toml` files inside `tmp_path` are not a problem for most tests — each test gets its own `tmp_path`. However, if any test uses the actual `packages/graph-io/` directory (e.g., running `packages.refresh(conn, repo_root=Path("."))` in a test), `_discover_manifests` will find the real `packages/graph-io/pyproject.toml` and every other workspace package, polluting the test DB.

Separately: fixture mini-repos that write `pyproject.toml` directly into `tmp_path/pyproject.toml` (repo root) will be discovered as a root-package manifest. If the test is for `EntryPoint` parsing, this is intentional. But if the test is for `TestSuite` detection and the `pyproject.toml` incidentally contains `[tool.pytest]`, `detect_tests.py` will find pytest config at the root — which may be the intended behavior, but is surprising if the developer forgot to add `[tool.pytest]` to the fixture manifest.

**How to avoid:**
All fixtures that need a manifest for one purpose should explicitly write only the sections they need and nothing else. Standard fixture pattern: always use `tmp_path` (never `Path(".")`) as repo_root. Add a CI rule (ruff or custom grep) that flags any test using `repo_root=Path(".")`.

**Phase to address:** Phase C onward. Establish this convention when the first entry-point/test-suite fixtures are written.

---

## Technical Debt Patterns

| Shortcut | Immediate Benefit | Long-term Cost | When Acceptable |
|----------|-------------------|----------------|-----------------|
| `uri TEXT` nullable instead of `UNIQUE NOT NULL` | Avoid full URI backfill for AST nodes in v1.6 | v1.7 must enforce uniqueness; if emitters produce URI collisions they will be invisible until v1.7 constraint lands | Acceptable in v1.6 only — document the v1.7 upgrade path explicitly |
| Convention-based domain inference without validation | No `domains.yaml` needed to start | False-positive domains (from `tests/` subdirs) pollute domain graph | Acceptable with the `tests/` exclusion list in place |
| `derived_edges.compute` runs on every update | Simplest correct behavior | Slow on large repos; wasted CPU when domains are static | Acceptable in v1.6 since the only consumer is a single developer on a personal repo |
| `packages.refresh` returns `None`, entry_points re-reads manifests | Avoids changing `packages.refresh` signature | Double I/O on every update — manifests read twice | Never acceptable for large repos; resolve in Phase C by having `packages.refresh` return manifest data |
| `is_test` flag on `File` nodes not cross-referenced with TestSuite membership | Simpler path detection | File.is_test and TestSuite membership can diverge (a file marked `is_test` but not assigned to any suite) | Acceptable in v1.6 — add consistency check query in v1.7 |

---

## Integration Gotchas

| Integration | Common Mistake | Correct Approach |
|-------------|----------------|------------------|
| `packages.refresh` → `entry_points.emit` | `entry_points.emit` calls `_discover_manifests` independently (double I/O) | `packages.refresh` returns manifest data; `entry_points.emit(conn, manifest_data=...)` consumes it |
| `structural_nodes.emit` → `test_suites.emit` | `test_suites.emit` runs before `packages.refresh`, so Package nodes don't exist yet when re-parenting | Always: `_process_files` → `packages.refresh` → `entry_points.emit` → `structural_nodes.emit` → `test_suites.emit` → `domains.emit` → `resolve.sweep` → `derived_edges.compute` |
| `domains.emit` → `derived_edges.compute` | `derived_edges.compute` runs before `resolve.sweep`, so some `imports` edges are still unresolved | Move `derived_edges.compute` to after `resolve.sweep` (already noted in ARCHITECTURE.md as the safer order) |
| `source_parser` → `graph_io` | URI generation placed in `to_graph_records()` inside source-parser | URIs belong in graph-io emitters (source-parser lacks repo/org context); never generate URIs in source-parser |
| `domains.yaml` → `workspace_io` | Moving `load_domains` into `workspace_io` for "centralized config" | `domains.yaml` is a code-graph artifact; it belongs in `graph_io/domains.py`, not workspace-io |

---

## Performance Traps

| Trap | Symptoms | Prevention | When It Breaks |
|------|----------|------------|----------------|
| `derived_edges.compute` join on every incremental update | `cg update` slow on unchanged repos | Gate on `domains.yaml` existence; skip if absent | ~50+ packages with full import graph |
| `packages.refresh` `_file_nodes_under` uses `LIKE prefix%` on unindexed `path` column | Slow package scan on large repos | `idx_nodes_path` already exists — verify it is used in EXPLAIN QUERY PLAN | >10,000 file nodes |
| `structural_nodes.emit` does a full FS walk independent of `_process_files` | Double filesystem walk per update | Cache walk results in `update.py` local dict; pass to both functions | Large monorepos with >5,000 files |
| `test_suites.emit` queries `physically_contains Package → File` edges to find test files, then deletes and re-inserts them on every update | Constant edge churn for unchanged repos | Add a hash or timestamp check: skip re-parenting if test file set has not changed | Any incremental update after first full build |

---

## "Looks Done But Isn't" Checklist

- [ ] **Schema v2:** `uri` column is in DDL, `SCHEMA_VERSION == 2`, `idx_nodes_uri` index exists, `SchemaMismatchError` exits with code 4 (not 1), README exit-code table updated — verify all five together
- [ ] **URI identity:** `_upsert_node` extracts `uri` from `node.attrs` and writes to the `uri` column (not just to `attrs_json`) — verify with `SELECT uri FROM nodes WHERE kind='package'` after update
- [ ] **Repository node persistence:** `Repository` nodes survive `resolve.sweep` (they have `path=NULL` but are only sources of edges, not destinations) — verify with `SELECT COUNT(*) FROM nodes WHERE kind='repository'` post-sweep
- [ ] **Test file re-parenting:** After `cg update --full`, test files appear under `TestSuite` in `physically_contains` edges and do NOT appear directly under their `Package` — verify with `cg describe-package <name>` showing no test files
- [ ] **Domain convention inference skips `tests/`:** `cg list-domains` on a repo with `tests/billing/` does not show a `billing` domain (unless `domains.yaml` explicitly declares it)
- [ ] **Brand sweep complete:** `cg --help` shows "graph-wiki code graph CLI", not "lattice code graph CLI"; `~/.lattice/graph/code.db` path reference removed from README
- [ ] **`LATTICE_GRAPH_LOCK_TIMEOUT_MS` deprecation alias:** Old env var still works with a deprecation warning; new env var works silently — test both
- [ ] **Domain cycle detection:** A cyclic `domains.yaml` prints a warning and skips `domain_contains_domain` edges without crashing

---

## Recovery Strategies

| Pitfall | Recovery Cost | Recovery Steps |
|---------|---------------|----------------|
| Schema column missing after bump | LOW | Delete `code.db`, run `cg update --full`. DB is disposable by design. |
| `Repository` nodes deleted by `resolve.sweep` | LOW | Fix `resolve.py` guard, run `cg update --full` to rebuild. |
| URI values in `attrs_json` instead of `uri` column | MEDIUM | Fix `_upsert_node`, delete `code.db`, run `cg update --full`. All URIs must be regenerated from scratch. |
| Test re-parenting order bug (test files still under Package) | LOW | Fix call order in `update.py`, run `cg update --full`. No data migration needed. |
| Domain convention inference created false domains | LOW | Delete false domain nodes manually or run `cg update --full` after fixing the exclusion list. |
| Domain hierarchy cycle crashes `derived_edges.compute` | LOW | Add cycle detection in `domains.py`, fix `domains.yaml`, run `cg update`. |
| `LATTICE_GRAPH_LOCK_TIMEOUT_MS` silently ignored after brand sweep | LOW | Add deprecation alias in `update.py`. User must re-export the new var name. |

---

## Pitfall-to-Phase Mapping

| Pitfall | Prevention Phase | Verification |
|---------|------------------|--------------|
| Schema bump without column assertion | Phase A | `test_nodes_table_has_uri_column` in `test_schema.py` — must pass before Phase B begins |
| `SCHEMA_MISMATCH` exit code not wired | Phase A | `test_cli_exit_codes.py` seeds v999 DB, runs `cg find`, asserts exit 4 |
| URI in `attrs_json` not in `uri` column | Phase A | `test_upsert.py` asserts `uri` column populated, `attrs_json` does not contain `"uri"` key |
| Repository node deleted by resolve.sweep | Phase B | `test_resolve.py` asserts Repository node survives sweep |
| Test file re-parenting order bug | Phase C | `test_suites.py` asserts test files have exactly one `physically_contains` edge post-sweep |
| `implemented_by` ambiguous resolution | Phase C | `test_entry_points.py` two-package scenario with `main` in both |
| Convention inference false positives | Phase D | `test_domains.py` asserts no domain created from `tests/` subdirs |
| Domain cycle crash | Phase D | `test_domains.py` cyclic YAML produces warning, no crash |
| Package name vs. directory name in domains.yaml | Phase D | `test_domains.py` asserts warning fires for unknown package name |
| Brand sweep breaks `LATTICE_GRAPH_LOCK_TIMEOUT_MS` | Phase G | `test_update.py` asserts old env var still works with deprecation warning |
| Test fixtures with `pyproject.toml` pollute real scan | Phase C+ | CI lint rule: no `repo_root=Path(".")` in test files |

---

## Sources

- `packages/graph-io/src/graph_io/schema.py` — `SCHEMA_VERSION = 1`, `_DDL_STATEMENTS` (no `uri` column yet)
- `packages/graph-io/src/graph_io/store.py` — `SchemaMismatchError`, `_check_schema_version`, `connect` create-path logic
- `packages/graph-io/src/graph_io/upsert.py` — `_upsert_node`, `_serialize`, `NodeKey` identity pattern
- `packages/graph-io/src/graph_io/resolve.py` — placeholder-node deletion logic (line 50-56); `path IS NULL AND kind != 'package'` guard
- `packages/graph-io/src/graph_io/update.py` — `LATTICE_GRAPH_LOCK_TIMEOUT_MS` (line 130), call sequence in `run()`
- `packages/graph-io/src/graph_io/packages.py` — `_discover_manifests`, `refresh`, `_SKIP_REPO_PREFIXES`
- `packages/graph-io/README.md` — `SCHEMA_MISMATCH = 4` marked "reserved — not yet enforced"
- `packages/graph-io/conftest.py` — bare `sqlite3.connect(":memory:")` fixture without schema
- `packages/graph-io/tests/test_schema.py` — `test_schema_version_is_one()` sentinel
- `packages/graph-io/tests/test_packages.py` — fixture patterns, `store.connect(db, create=True)` vs bare conn
- `packages/graph-io/tests/_git_repo.py` — git-backed fixture pattern
- `packages/graph-io/tests/test_e2e.py` — end-to-end pipeline structure
- `.planning/research/ONTOLOGY-SPEC.md` — §7 TestSuite layout, §9 scanner pipeline, §4 edge types
- `.planning/research/ARCHITECTURE.md` — call order analysis, emitter boundary decisions, resolve.sweep concern noted
- `.planning/research/STACK.md` — `_walk_exports` wildcard handling, `conftest.py` detection false positive

---
*Pitfalls research for: graph-io v1.6 ontology expansion (schema v2, URI identity, structural/conceptual nodes, derived edges)*
*Researched: 2026-05-25*
