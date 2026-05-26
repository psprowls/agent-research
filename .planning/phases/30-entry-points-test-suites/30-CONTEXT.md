# Phase 30: Entry Points + Test Suites - Context

**Gathered:** 2026-05-25
**Status:** Ready for planning

<domain>
## Phase Boundary

After Phase 30, two new emitters land in `graph-io`:

1. **`entry_points.emit`** — Reads `pyproject.toml` (`[project.scripts]`, `[project.entry-points.*]`) and `package.json` (`bin`, `main`, `module`, `exports`) for every Package. Emits `EntryPoint` nodes with `kind: executable | library` and `source: <which manifest declaration>`. Wires `declares_entry_point` edges (Package → EntryPoint) and `implemented_by` edges (EntryPoint → File). Path-qualified resolution from the declaring Package's import root, no fallback search.

2. **`test_suites.emit`** — Reads filesystem layout + framework config to emit `TestSuite` nodes. Each immediate subdir of `tests/` becomes one suite; `tests/` itself becomes a suite if it holds test files directly (TEST-02). Package-local `packages/foo/tests/` becomes a suite contained by Package (TEST-03). Re-parents every test file from Phase 29's `physically_contains Repository → File` edge to `physically_contains TestSuite → File` (TEST-04). Derives `tests` edges from imports in test files: `TestSuite → Package` for every imported first-party package, `TestSuite → Repository` when the suite imports from ≥5 packages.

Both emitters slot into `update.run()` between `structural_nodes.emit` (Phase 29) and `resolve.sweep`. The `update.py` call order is enforced two ways: a fixture regression test (SC#3 pitfall test) and an always-on strict-tree invariant check at the end of `update.run`.

**Strictly NOT in this phase:**
- `Domain` nodes, `belongs_to_domain` edges, `TestSuite → Domain` edges → Phase 31
- Derived `references` / `depends_on` edges → Phase 31
- CLI surface (`cg list-entry-points`, `cg list-suites`, `cg find --kind ...`) → Phase 33 (success criteria use them; the query helpers in `queries.py` may land in Phase 32 — Phase 30 ships only emitters + assertions reachable via SQL or existing CLI)
- Brand sweep → Phase 34
- Function/Class node creation — source-parser concern; if a Function node for a callable-syntax entry doesn't exist, `implemented_by` falls back to File (and per D-08 always points at File anyway)

Requirements addressed: ENTRY-01, ENTRY-02, ENTRY-03, ENTRY-04, ENTRY-05, TEST-01, TEST-02, TEST-03, TEST-04, TEST-05, TEST-06, TEST-07.

</domain>

<decisions>
## Implementation Decisions

### `is_test` heuristic amendment (cross-phase fix)

- **D-01:** Phase 29 D-09's filename-based `is_test=true` rule is amended: **a file inside any Python package's import root (the path resolved by Phase 29 D-06: `<pkg.path>/src/<importable>/` or `<pkg.path>/<importable>/`) is `is_test=false` regardless of filename**, even if it matches `test_*.py` / `*_test.py`. For JS/TS: a file inside a Package directory but outside any `tests/` / `__tests__/` subdir is `is_test=false` regardless of filename matching `*.test.*` / `*.spec.*`. The `tests/`-directory branch of D-09 remains authoritative — anything under a `tests/` ancestor is `is_test=true`. The filename branch only fires when the file is NOT inside a package's import root.

- **D-02:** **Risk note for the planner:** Phase 29 is actively executing in the background at the time of this context capture (`is_active=true`). The D-01 amendment MUST land in `packages/graph-io/src/graph_io/structural_nodes.py`. If Phase 29's plan already shipped the old D-09 heuristic by the time Phase 30 starts execution, treat the amendment as a Phase 30 patch to `structural_nodes.py` (one wave, ahead of `test_suites.emit` plan). If Phase 29 is still planning when Phase 30 plans land, fold the amendment into Phase 29's `structural_nodes.emit` plan instead. Either way, no orphan-test-suite scaffolding is needed in `test_suites.emit` — orphan test files in src/ simply don't exist as `is_test=true` after D-01.

### `EntryPoint.implemented_by` semantics (ENTRY-04)

- **D-03:** `implemented_by` ALWAYS points at a `File` node, never at a `Function` / `Class` node — even for Python callable-syntax entries (`pkg.cli:main`) and even when source-parser has produced a `Function` node for that callable. Edge semantics are uniform across all entry kinds.

- **D-04:** The callable name for callable-syntax entries is stored on the `EntryPoint` node as an attribute: `EntryPoint.callable: str | None`. For `graph-wiki-agent = "graph_wiki_agent.cli:main"`, the node has `name="graph-wiki-agent"`, `callable="main"`, and `implemented_by → File(graph_wiki_agent/cli.py)`. For path-only entries (e.g. `package.json "main": "./index.js"`), `callable=NULL`.

- **D-05:** Path-qualified resolution is **strict** — the resolver walks the dotted prefix from the declaring Package's import root (using Phase 29 D-06's layout discovery) and constructs an exact path. No glob fallback. No `name=main` global search across the repo. This is what SC#4 ("path-qualified resolution, not ambiguous `name=main` match") requires.

- **D-06:** When strict resolution misses (manifest declares a callable pointing at a file that doesn't exist), emit the `EntryPoint` node anyway with `implemented_by=NULL` and print a warning identifying the offending manifest + entry name. The broken declaration is itself useful signal — a future `cg find-stale-entry-points` query can find them. Do NOT skip the EntryPoint and do NOT exit non-zero.

### `package.json` `exports` walk (ENTRY-02)

- **D-07:** Recursive walk over `exports` produces **one `EntryPoint` per string-valued leaf**, all with `kind: library` and `source: package.json.exports`. The export key path becomes the `name` (e.g. `"./submodule"` → `EntryPoint.name = "./submodule"`).
  - Conditional exports (`{"import": "./esm.js", "require": "./cjs.js"}`) produce two `EntryPoint` nodes sharing the same export key but pointing at different files, distinguished by an `EntryPoint.condition: str | None` attr (`"import"`, `"require"`, `"default"`, etc.).
  - Wildcard patterns (`"./*": "./src/*.js"`) emit ONE `EntryPoint` with `is_wildcard=true`, `implemented_by=NULL`, and the pattern stored in `EntryPoint.path_pattern`. Concrete file resolution is deferred (no glob-expansion in Phase 30; defer to v1.7 if a query needs it).

- **D-08:** `package.json` `"bin"` produces `EntryPoint` nodes with `kind: executable`, `source: package.json.bin`. String form (`"bin": "./cli.js"`) produces one EntryPoint named after the package; object form (`{"foo": "./foo.js"}`) produces one per key. `"main"` and `"module"` are single library entries with `name` set to the field name (`"main"`, `"module"`); `source` distinguishes which field.

### `TestSuite → Package` edge derivation (TEST-06)

- **D-09:** Derive `tests` edges from imports in every File node contained by the TestSuite. For each first-party package imported by any test file in the suite, emit one `TestSuite → Package` edge. **All matching packages get edges** — no top-N filtering, no import-count threshold. If a suite tests 5 packages, it gets 5 edges. Predictable, no tuning knobs.

- **D-10:** First-party package matching is map-driven. Build `{importable_name: Package}` at the start of `test_suites.emit` from existing Package nodes (using Phase 29 D-06's layout-discovery rules — Package `graph-io` → importable `graph_io`). For each Python `from X.Y.Z import ...` or `import X.Y.Z`, take the top-level module name `X` and look it up in the map. Unknown names (stdlib, third-party PyPI packages) are silently ignored — no warning, no edge.

- **D-11:** JS/TS imports use the same map-driven approach against `Package.name` (from `package.json`):
  - Bare specifiers (`import ... from 'pkg-name'` / `require('pkg-name')`) are looked up directly in the Package-name map.
  - Relative imports (`./foo`, `../src/bar.ts`) are resolved against the importing file's directory to a target File path; the target's containing Package (via `physically_contains` ancestry) supplies the edge target.
  - Same silent-skip-on-miss semantics as D-10.

### `TestSuite → Repository` edges (whole-system suites)

- **D-12:** When a suite imports from **≥5 first-party packages** (count of distinct Package matches in D-10/D-11 import scan), emit an additional `TestSuite → Repository` edge alongside the per-package edges. The Package edges are NOT suppressed — both edge sets coexist so that `cg find --kind test-suite --target package=billing` still returns this suite AND `cg find --kind test-suite --target repository` finds it too. K=5 is a starting heuristic; the planner can expose it as a constant in `test_suites.py` if it needs tuning later.

- **D-13:** `TestSuite → Domain` edges are **NOT emitted in Phase 30** — Domain nodes don't exist until Phase 31. Phase 31's responsibility is to add the `TestSuite → Domain` edge derivation after `domains.emit` runs.

### Test file re-parenting strategy (TEST-04)

- **D-14:** Re-parenting is **delete-then-insert, atomic per file, wrapped in a single transaction**. Pseudocode:
  ```python
  with conn:  # single tx for the whole emit
      for test_file in test_files:
          suite = assign_suite(test_file)  # returns TestSuite node id
          conn.execute("DELETE FROM edges WHERE kind=? AND child_id=?",
                       ("physically_contains", test_file.id))
          conn.execute("INSERT INTO edges (kind, parent_id, child_id) VALUES (?,?,?)",
                       ("physically_contains", suite.id, test_file.id))
  ```
  No mid-transaction state where a file has 2 parents — the DELETE clears whatever existed (Phase 29's `Repository → File` edge, OR a prior run's `TestSuite → File` edge for idempotency on re-runs). Re-running `cg update` produces identical edges (idempotent).

- **D-15:** Suite assignment for a test file (`assign_suite(test_file)`):
  1. If `test_file.path` is inside a Package's `tests/` subdir → suite is the TestSuite contained by that Package.
  2. Else if `test_file.path` is inside repo-root `tests/<subdir>/` → suite is the TestSuite for `<subdir>`.
  3. Else if `test_file.path` is inside repo-root `tests/` (flat, no subdirs) → suite is the single `tests/` suite contained by Repository.
  4. Else (test file outside any known `tests/` ancestor) → cannot happen after D-01 amendment; if it does, log error and skip re-parenting (leave Phase 29's `Repository → File` edge in place).

### `TestSuite` node emission (TEST-01, TEST-02, TEST-03, TEST-05, TEST-07)

- **D-16:** TestSuites are flat — no `TestSuite → TestSuite` nesting (TEST-07). `tests/integration/auth/` produces ONE `TestSuite` named `integration/auth` (or just `auth`? planner picks naming convention consistent with existing emit-node naming — recommend `<top-level-tests-subdir>` for repo-root suites and `tests` for package-local suites).
- **D-17:** `TestSuite.kind` classification (TEST-05) is Claude's discretion. Recommended heuristics in priority order: directory name contains `integration` → `integration`; `e2e` or `system` → `e2e`; `contract` or filenames matching `*_spec.{ts,js,py}` → `contract`; filenames matching `test_*.py` / `*_test.{py,js,ts}` / `*.test.{js,ts}` → `unit`; otherwise `unknown`. Conservative — mark `unknown` when in doubt.
- **D-18:** Framework config (pytest.ini, jest.config.*, etc.) contributes minimally in Phase 30 — only to discover **additional test root directories** beyond the conventional `tests/` (e.g. pytest `testpaths = ["spec"]` makes `spec/` a TestSuite root too). Config does NOT override suite naming or kind. If config can't be parsed (malformed), log warning and fall back to filesystem-only detection.

### SC#3: call-order pitfall enforcement

- **D-19:** Two enforcement mechanisms ship together:
  - **(a) Fixture regression test** at `packages/graph-io/tests/test_test_suites.py::test_call_order_pitfall`. Extends Phase 29 D-22's `tests/fixtures/sample_monorepo/` with `tests/integration/test_top.py` and `packages/mypkg/tests/test_foo.py`. Runs `cg update --full` on the fixture, asserts: every File node with `is_test=true` has exactly one `physically_contains` edge AND that edge's parent is a `TestSuite` node (NOT Repository, NOT Package, NOT SubPackage).
  - **(b) Always-on strict-tree runtime check** at the end of `update.run`, after all emitters and `resolve.sweep`:
    ```python
    rows = conn.execute(
        "SELECT child_id, COUNT(*) AS n FROM edges WHERE kind='physically_contains' "
        "GROUP BY child_id HAVING n > 1"
    ).fetchall()
    if rows:
        raise StrictTreeInvariantError(offending_child_ids=[r[0] for r in rows])
    ```
    Always on. `cg update` exits non-zero on violation. Query is cheap (one GROUP BY on a column that should be indexed).

- **D-20:** `StrictTreeInvariantError` is a new exception in `packages/graph-io/src/graph_io/_errors.py` (or wherever existing graph-io exceptions live). The error message includes the count of offending nodes and a hint: `"physically_contains tree invariant violated for N node(s). Likely cause: an emitter inserted a duplicate parent edge, or test re-parenting failed to delete the prior edge. Offending child node ids: [...]"`. Useful in CI.

### `update.run()` orchestration

- **D-21:** Two new emit calls inserted in `update.run()` after `structural_nodes.emit(...)` (Phase 29 D-23), before `resolve.sweep(...)`:
  ```python
  structural_nodes.emit(conn, repo_root=repo_root, ctx=ctx, skip_dirs=skip_dirs)
  entry_points.emit(conn, repo_root=repo_root, ctx=ctx, skip_dirs=skip_dirs)
  test_suites.emit(conn, repo_root=repo_root, ctx=ctx, skip_dirs=skip_dirs)
  resolve.sweep(conn)
  _enforce_strict_tree_invariant(conn)  # D-19(b)
  ```
  `entry_points.emit` before `test_suites.emit` is the canonical order (matches the ROADMAP requirement-ordering of ENTRY-* before TEST-*); the two are dependency-independent so the order is interchangeable but should be deterministic.

### Claude's Discretion

- Exact TestSuite node naming convention (`tests/integration` vs `integration` vs `repo:tests:integration`) — planner picks consistent with Phase 29's URI naming (`uri.testsuite_uri(...)` helper to be added).
- Framework config parser depth — Phase 30 only needs `testpaths` discovery (and the JS equivalent in `jest.config.*`). Other config keys are ignored. Planner can choose to use stdlib `tomllib` + `json` for config parsing (no new deps).
- `EntryPoint.name` shape for `[project.entry-points."console_scripts"]` (modern PEP 621 form) vs `[project.scripts]` — treat both as `kind: executable`; `source` distinguishes (`pyproject.scripts` vs `pyproject.entry-points.console_scripts`).
- Whether to emit `Repository → TestSuite` `physically_contains` edges in addition to `Package → TestSuite` for package-local suites (TEST-03 says suite is "contained by their Package", so NO — Package is the sole structural parent for package-local suites; Repository is the parent only for repo-root suites). The strict-tree invariant in D-19(b) enforces this.

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Source-of-truth ontology spec
- `.planning/research/ONTOLOGY-SPEC.md` §3 (Node kinds — EntryPoint, TestSuite definitions and attributes), §4 (Edges — declares_entry_point, implemented_by, physically_contains TestSuite branch, tests edges), §6 (Test suite emission rules, §"Pitfall: containment-tree call order"), §9 (Scanner pipeline — manifest parse, test suite detection, test target derivation)

### v1.6 research (mandatory)
- `.planning/research/ARCHITECTURE.md` — confirms `entry_points.emit` and `test_suites.emit` land in `packages/graph-io/src/graph_io/` as additive emitters in `update.run()`
- `.planning/research/PITFALLS.md` — the call-order pitfall is the SC#3 backbone (D-19); read the warning that motivates the fixture test
- `.planning/research/STACK.md` — confirms `tomllib` (stdlib, 3.11+) and `json` (stdlib) are sufficient for manifest + framework-config parsing; no new deps
- `.planning/research/FEATURES.md` — Phase 30 ships NO new CLI surface; success-criteria CLI invocations (`cg list-entry-points`, `cg list-suites`) ride on Phase 33

### Phase 28 prior context
- `.planning/phases/28-schema-v2-uri-foundation/28-CONTEXT.md` — D-04/D-05/D-07/D-11 (RepoContext derivation + ctx threading pattern); D-10 (URI in column, not attrs_json) — entry_points + test_suites both write URIs via the same path

### Phase 29 prior context
- `.planning/phases/29-structural-nodes-containment-tree/29-CONTEXT.md` — D-06 (import-root discovery for SubPackage walks; D-05/D-10 here reuse it for entry-point dotted-path resolution); D-09 (the `is_test` heuristic that D-01 here amends); D-13/D-14 (containment tree shape, test files parked under Repository pre-Phase-30); D-16 (resolve.sweep uri-guard, still must not delete Repository/SubPackage/TestSuite/EntryPoint); D-18 (per-Package `language` attr drives JS/TS vs Python branch); D-22 (sample_monorepo fixture, extend it here); D-23 (`update.run()` emitter insertion pattern)

### Requirements + roadmap
- `.planning/REQUIREMENTS.md` — ENTRY-01..05 (lines 36–40), TEST-01..07 (lines 44–50); see also lines 198–209 for the pending-phase mapping
- `.planning/ROADMAP.md` — Phase 30 block: goal + 5 success criteria are non-negotiable

### Existing graph-io code (read before editing)
- `packages/graph-io/src/graph_io/update.py` — `run()` orchestration; D-21 inserts two new emit calls + strict-tree invariant check at the end
- `packages/graph-io/src/graph_io/structural_nodes.py` (Phase 29 deliverable) — D-01 amendment lands in the `is_test` heuristic implementation (location depends on whether Phase 29 has shipped it yet)
- `packages/graph-io/src/graph_io/packages.py` — `Package.language` (lines 44, 63) drives D-11's Python-vs-JS import-scan branch
- `packages/graph-io/src/graph_io/upsert.py` — `_upsert_node` (Phase 28 D-10) used for EntryPoint and TestSuite node writes; no changes needed
- `packages/graph-io/src/graph_io/resolve.py` — `sweep()` (Phase 29 D-16); after Phase 30, EntryPoint and TestSuite nodes carry non-null URIs so the existing uri-guard already protects them — verify, don't re-edit
- `packages/graph-io/src/graph_io/_ignore.py` — `should_skip()` reused for both new emitters' FS walks
- `packages/graph-io/src/graph_io/uri.py` — add `entry_point_uri(...)` and `testsuite_uri(...)` helpers consistent with Phase 28 `pkg_uri` / Phase 29 `subpkg_uri` shape

### Source-parser (cross-package, read-only here)
- `packages/source-parser/src/source_parser/` — Phase 30 reads (but does not modify) the `SourceNode.attrs` produced by source-parser for Python files. The `implemented_by` resolution (D-05) needs file existence at the resolved path; source-parser's role is upstream of that

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- **`update.run()` emitter insertion pattern** (Phase 29 D-23) — both new emitters slot in identically: `module.emit(conn, repo_root=..., ctx=..., skip_dirs=...)`
- **`_upsert_node`** with `uri` pop-to-column (Phase 28 D-10) — directly used for both EntryPoint and TestSuite node writes
- **`packages.refresh` Package.language attr** (`packages.py:44`, `packages.py:63`) — D-11 reads this to branch Python vs JS import-scan
- **Phase 29 D-06 `_resolve_import_root(pkg_path, importable_name)`** — D-05 reuses this exactly for entry-point dotted-path resolution
- **`tests/fixtures/sample_monorepo/`** (Phase 29 D-22) — D-19(a) extends this fixture; do NOT create a new fixture
- **`_ignore.should_skip`** — reuse for both emitters' FS walks
- **`uri.repo_uri / pkg_uri / subpkg_uri / file_uri`** — add `entry_point_uri` and `testsuite_uri` to `uri.py` following the same shape

### Established Patterns
- **Additive emitters in `update.run`** — never replace existing behavior; insert new emit calls between existing ones (ARCHITECTURE.md doctrine)
- **Module-private constants** at the top of each emitter file for heuristic allow-lists / regex patterns (structural_nodes.py pattern from Phase 29)
- **`with conn:` transaction blocks** wrap the whole emit per Phase 29's structural_nodes.emit — re-parent must be inside one tx (D-14)
- **Fixture tests use `_run_cli` helper + tmp_path-copied fixture** — the call-order pitfall test (D-19a) follows this pattern

### Integration Points
- **`update.run` is the only writer entry point** — single insertion site for both new emit calls (D-21)
- **`structural_nodes.emit` must run BEFORE `entry_points.emit` and `test_suites.emit`** — both new emitters depend on File nodes existing (implemented_by edge target, test file re-parenting source)
- **`resolve.sweep` must run AFTER both new emitters** — it could otherwise delete the Repository→File edges for test files that have not yet been re-parented. Phase 29's URI-guard (D-16) protects EntryPoint and TestSuite nodes from being swept (both carry URIs)
- **Source-parser SPARSER-* attrs** are read but not written by Phase 30 (D-03's File-only `implemented_by` decision means we don't need a Function node to exist)

</code_context>

<specifics>
## Specific Ideas

- D-19(b) invariant query (cheap, runs once per `cg update`):
  ```sql
  SELECT child_id, COUNT(*) AS n
  FROM edges
  WHERE kind = 'physically_contains'
  GROUP BY child_id
  HAVING n > 1
  ```
  Expect zero rows. Any rows → `StrictTreeInvariantError`.

- D-14 idempotency check: re-running `cg update --full` on the fixture should produce **byte-identical** edge sets for `physically_contains` and `tests` edges. Useful test to add alongside D-19(a).

- D-17 directory name → kind mapping (suggested order, planner can adjust):
  | Directory contains | Filename pattern | TestSuite.kind |
  |---|---|---|
  | `integration` | any | `integration` |
  | `e2e` or `system` | any | `e2e` |
  | `contract` | any | `contract` |
  | (none) | `*_spec.{ts,js,py}` | `contract` |
  | (none) | `test_*.py` / `*_test.{py,js,ts}` / `*.test.{js,ts}` | `unit` |
  | (none) | (none) | `unknown` |

- D-12 K=5 threshold should be a module-private constant in `test_suites.py` (e.g. `_REPOSITORY_EDGE_THRESHOLD = 5`) so it's tunable without scattering magic numbers.

- D-19(a) fixture extension to `tests/fixtures/sample_monorepo/`:
  ```
  packages/mypkg/tests/test_foo.py        # package-local suite (TestSuite contained by Package)
  tests/integration/test_top.py           # repo-root suite (TestSuite contained by Repository)
  jspkg/__tests__/index.test.js           # JS package-local suite
  ```
  Assertions in `test_call_order_pitfall`:
  - Every `is_test=true` File has exactly one `physically_contains` parent
  - Every such parent is a `TestSuite` node
  - `cg describe-package mypkg` returns the package but its `physically_contains` subtree excludes `test_foo.py`
  - The `integration` suite has `TestSuite.kind = 'integration'`
  - Re-running `cg update --full` produces identical edge counts (idempotency)

- D-07 wildcard handling: `package.json` like `{"exports": {"./features/*": "./src/features/*.js"}}` produces ONE EntryPoint with `name="./features/*"`, `kind="library"`, `is_wildcard=true`, `path_pattern="./src/features/*.js"`, `implemented_by=NULL`. A future v1.7 feature could expand wildcards by globbing the FS at emit time.

</specifics>

<deferred>
## Deferred Ideas

- **Function/Class as `implemented_by` target** — D-03 locked File-only. If a future query needs callable-level navigation (`cg describe-entry-point graph-wiki-agent --to-function`), revisit; the `EntryPoint.callable` attr (D-04) carries the data needed to resolve at query time.
- **Wildcard `exports` expansion** — D-07 defers to v1.7. Add when a real package.json with wildcards lands and a user query (e.g. `cg list-entry-points jspkg`) needs concrete-file resolution.
- **Top-N filtering / threshold tuning on `tests` edges** — D-09 emits all matching packages. If a query surface gets noisy (suite tests 20 packages because it imports `logging`), revisit; the K=5 threshold for `TestSuite → Repository` is one knob we already have.
- **`TestSuite → Domain` edges** — Phase 31's responsibility (after `domains.emit`). Phase 30 emits only `TestSuite → Package` and `TestSuite → Repository`.
- **PyPI metadata resolution for first-party vs third-party** — current map-driven approach (D-10) silently skips unknown top-level imports. If a real test file imports a renamed package, we miss the edge with no warning. Considered "warn on unknown imports" and rejected — too noisy for v1.6.
- **Stale entry-point query** — D-06 emits EntryPoint nodes with `implemented_by=NULL` for broken manifest declarations. A `cg find-stale-entry-points` CLI query would surface these; defer to Phase 33 if Pat wants it, or v1.7.
- **Function-level `tests` edges** (ONTOLOGY-SPEC.md §4 mentions these as "advisory") — Phase 30 ships only `TestSuite → Package/Repository`. File-level and Function-level `tests` edges are deferred to a later phase or v1.7.
- **Framework-config-driven kind override** — currently config only contributes additional test roots (D-18). A future feature could read `[tool.pytest] markers` or `jest.config testEnvironment` to set `TestSuite.kind` more precisely.

</deferred>

---

*Phase: 30-entry-points-test-suites*
*Context gathered: 2026-05-25*
