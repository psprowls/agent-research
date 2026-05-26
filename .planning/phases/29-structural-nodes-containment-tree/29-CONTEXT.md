# Phase 29: Structural Nodes + Containment Tree - Context

**Gathered:** 2026-05-26
**Status:** Ready for planning

<domain>
## Phase Boundary

After Phase 29, `cg update --full` produces a strict physical containment tree rooted at exactly one `Repository` node per repo, with Python `SubPackage` nodes for every `__init__.py`-containing subdirectory, `File` nodes carrying role-flag attrs (`is_test`, `is_config`, `is_generated`, `is_type_only`, `is_executable`, plus `has_main` / `is_importable` refined from source-parser), and a `resolve.sweep` that distinguishes structural nodes from orphaned AST nodes by URI presence. Test files are emitted as `File` nodes with `is_test=true` but parked under `Repository` containment (NOT Package) — Phase 30 re-parents them to `TestSuite` nodes.

**Strictly NOT in this phase:**
- TestSuite emission and `tests` edges → Phase 30
- EntryPoint emission from manifests → Phase 30
- Domain nodes, `belongs_to_domain` edges → Phase 31
- Derived edges (`references`, `depends_on`) → Phase 31
- CLI surface additions (`cg describe-repo`, `cg list-packages`, etc.) → Phase 33
- Brand sweep / `LATTICE_*` env alias → Phase 34

Requirements addressed: STRUCT-01, STRUCT-02, STRUCT-03, STRUCT-04, STRUCT-05, STRUCT-06, SPARSER-01, SPARSER-02.

</domain>

<decisions>
## Implementation Decisions

### Repository node (STRUCT-01)

- **D-01:** Exactly one `Repository` node per repo, emitted at the head of `structural_nodes.emit(conn, repo_root, ctx, skip_dirs)`. Five attrs only:
  - `uri` — `repo_uri(ctx)` → `repo:org/repo`
  - `name` — `ctx.repo` (parsed from remote URL or `repo_root.name` in local mode)
  - `owner` — `ctx.org` (parsed from remote URL or the literal `"local"`)
  - `url` — raw `git remote get-url origin` output in remote mode; `str(repo_root.absolute())` in local-fallback mode
  - `default_branch` — `git symbolic-ref --short refs/remotes/origin/HEAD` (strip `origin/` prefix) in remote mode; `git symbolic-ref --short HEAD` in local mode. On detached HEAD: `NULL`.
- **D-02:** Local-fallback mode (no parseable origin remote) STILL emits a `Repository` node. STRUCT-01 says exactly one Repository per repo, and the structural tree must always have a root. `url` carrying the absolute filesystem path is the local-mode disambiguator; consumers know `org == "local"` ⇒ `url` is FS-not-network.
- **D-03:** Repository has `path IS NULL` and is the unique root of `physically_contains` edges. All Package nodes get `physically_contains Repository → Package` in this phase (in addition to whatever containment edges existed pre-29; if the existing scheme already had something else, REPLACE with `physically_contains Repository → Package` so STRUCT-04's single-parent invariant holds).

### SubPackage emission (STRUCT-02)

- **D-04:** `SubPackage` nodes are emitted ONLY for `__init__.py`-containing subdirectories. PEP 420 namespace packages (subdirs with `.py` files but no `__init__.py`) are NOT emitted in v1.6 — defer to v1.7. Matches literal STRUCT-02 wording.
- **D-05:** Walk depth is unlimited — every `__init__.py` below a Package's import root produces a SubPackage. No depth cap.
- **D-06:** Per-Package import-root discovery uses Package's existing `path` attr plus a standard src-layout probe:
  1. If `<pkg.path>/src/<importable>/__init__.py` exists, the import root is `<pkg.path>/src/<importable>`.
  2. Else if `<pkg.path>/<importable>/__init__.py` exists (flat layout), the import root is `<pkg.path>/<importable>`.
  3. Else single-file or no-subpackages — emit no SubPackage nodes for this Package.

  `<importable>` is derived from the Package's manifest name with `-` → `_` (e.g. Package `graph-io` ⇒ importable `graph_io`). Planner should write a helper `_resolve_import_root(pkg_path, importable_name) -> Path | None`.
- **D-07:** SubPackage `dotted_path` is the full Python import path from the package's import root (including the top-level module name). Example: `packages/graph-io/src/graph_io/cli/__init__.py` ⇒ pkg_name=`graph-io`, dotted_path=`graph_io.cli`, uri=`subpkg:local/agent-research/graph-io/graph_io.cli`. Matches D-07 (Phase 28) example.
- **D-08:** Each SubPackage's `physically_contains` parent is the deepest enclosing SubPackage OR the Package if it sits directly under the import root. The top-level SubPackage (`graph_io/__init__.py` ⇒ `graph_io`) is contained by Package, not by Repository.

### File role-flag heuristics (STRUCT-03)

`structural_nodes.emit` consumes source-parser attrs (SPARSER-01) for `has_main` / `is_importable`. The other five flags are pure path/content heuristics in graph-io:

- **D-09:** `is_test` is true if ANY of:
  - the file path traverses a directory named `tests/`, `__tests__/`, or `test/` at any depth, OR
  - the filename matches `test_*.py`, `*_test.py`, `*.test.{js,ts,tsx,jsx}`, or `*.spec.{js,ts,tsx,jsx}`.
- **D-10:** `is_config` is true if the filename matches a curated allow-list (constant in `structural_nodes.py`):
  - Python ecosystem: `pyproject.toml`, `setup.cfg`, `setup.py`, `tox.ini`, `pytest.ini`, `mypy.ini`, `.flake8`, `ruff.toml`, `uv.toml`
  - JS/TS ecosystem: `package.json`, `tsconfig*.json`, `*.config.{js,ts,mjs,cjs}` (vite/jest/vitest/webpack/rollup/tailwind/eslint/postcss), `.eslintrc*`, `.prettierrc*`, `babel.config.*`
  - Other: `Cargo.toml`, `go.mod`, `Makefile`, `Justfile`, `.editorconfig`
  - Planner can adjust this list — finality is "covers the common Python + JS/TS configs in this monorepo".
- **D-11:** `is_generated` and `is_type_only` use filename pattern + content header scan:
  - `is_generated` filename patterns: `*_pb2.py`, `*_pb2_grpc.py`, `*.pb.go`, `*.gen.{ts,go}`, `*.generated.{ts,go}`, files inside any directory named `__generated__/` or `generated/`.
  - `is_generated` content marker scan: open file, read first 20 lines, set `is_generated=true` if any line contains `@generated`, `Code generated by`, or `DO NOT EDIT` (case-sensitive on `@generated`, case-insensitive on the other two). Skip content scan if the file is over 1 MB (no-op).
  - `is_type_only`: filename ends in `.d.ts` or `.pyi`. No content scan.
- **D-12:** `is_executable` is true if ANY of:
  - the file has the OS executable bit set (`os.access(path, os.X_OK)`), OR
  - the first line of the file starts with `#!` (shebang). Open + read first line for files with extensions `.py`, `.sh`, `.bash`, `.zsh`, `.js`, `.ts`, `.rb`, `.pl`, OR for files with no extension.

### Containment tree shape & test placement (STRUCT-04 / STRUCT-05)

- **D-13:** `physically_contains` edges form the strict tree:
  - Repository → Package (always)
  - Python: Package → SubPackage → [SubPackage → ...] → File
  - JS/TS: Package → File (no SubPackage layer)
  - Python files at Package level (e.g. `setup.py`, root `conftest.py`) are contained by Package directly, not by any SubPackage.
  - Manifest-level files (e.g. `pyproject.toml`, `package.json`) are contained by Package directly.
- **D-14:** Test files emit as `File` nodes with `is_test=true` and are contained by `Repository` in Phase 29 (NOT by Package, NOT by SubPackage). Phase 30 deletes the `physically_contains Repository → File` edge for each test file and inserts `physically_contains TestSuite → File`. STRUCT-04's "exactly one structural parent" invariant holds at both phase boundaries.
- **D-15:** Generic container directories (`packages/`, `libs/`, `tests/`, `apps/`, `shared/`, `common/`) are NEVER emitted as nodes (STRUCT-05). Their existence is implicit in the `path` attrs of the nodes they contain.

### `resolve.sweep` guard (STRUCT-06)

- **D-16:** `resolve.sweep` updates its deletion predicate from `WHERE path IS NULL` to `WHERE path IS NULL AND uri IS NULL`. Structural nodes (Repository, Domain, TestSuite, EntryPoint, and any future structural kinds) always carry a non-null `uri`; orphaned AST nodes (functions, classes, methods left behind when a source file is deleted) never have a `uri`. This is a one-line change in `resolve.py` and is self-maintaining — adding a new structural kind in v1.7 requires no edit to the sweep query.
- **D-17:** The sentinel regression test for STRUCT-06: pre-create a v2 DB with one Repository node (`path=NULL`, `uri='repo:test/x'`) plus one orphan AST node (`path=NULL`, `uri=NULL`), call `resolve.sweep(conn)`, assert the Repository node still exists and the orphan AST node is gone.

### JS/TS branch detection (STRUCT-02)

- **D-18:** `structural_nodes.emit` decides per-Package whether to walk for SubPackages by querying the Package node's `language` attr (set by `packages.refresh` — see `packages.py:44` and `packages.py:63`). Only `language == "python"` triggers the SubPackage walk. Any other language (`javascript`, future additions) emits Files directly under Package with no SubPackage layer.

### Source-parser coordination (SPARSER-01 / SPARSER-02)

- **D-19:** SPARSER-01 lands in `packages/source-parser/` — adds `_has_main_block` (detects `if __name__ == "__main__":`) and `_has_importable_symbols` (detects public top-level defs) to `SourceNode.attrs` at file scope. This is a graph-io-adjacent package edit and MUST land before the graph-io reads in D-20 are wired.
- **D-20:** `structural_nodes.emit` reads `_has_main_block` and `_has_importable_symbols` from each Python File's SourceNode attrs and writes `has_main` and `is_importable` on the corresponding File node. JS/TS files default `has_main=false`, `is_importable=true` (every JS/TS module is importable).
- **D-21:** Planner should sequence so SPARSER-01 ships in an earlier wave than `structural_nodes.emit`'s consumption — likely Wave 1 (source-parser change in parallel with a structural_nodes scaffolding plan), Wave 2 (structural_nodes.emit consuming SPARSER attrs).

### Test fixture for STRUCT-04 invariant

- **D-22:** STRUCT-04 strict-tree invariant test lives in `tests/test_structural_nodes.py::test_physically_contains_is_strict_tree`. Uses a synthetic mini-repo fixture under `tests/fixtures/sample_monorepo/` containing:
  - One Python src-layout package with two `__init__.py`-containing subdirs (one at depth 1, one at depth 2)
  - One JS package with a `package.json`
  - A `tests/` subdir with two test files
  - One `.d.ts` file, one `_pb2.py` file (heuristic coverage)

  The fixture is hand-curated, ~10-15 small files. Test runs `cg update --full` on the fixture (via existing `_run_cli` helper), then SQL-aggregates `physically_contains` edges and asserts `COUNT(*) > 1 GROUP BY child_id` returns zero rows. A second assertion verifies `cg describe-package <pkg> physically_contains` subtree contains zero `is_test=true` files. A third asserts the single Repository node exists with the expected URI.

### `update.py` orchestration

- **D-23:** New emit call inserted in `update.run()` after `packages.refresh(...)`, before `resolve.sweep(...)`:
  ```python
  structural_nodes.emit(conn, repo_root=repo_root, ctx=ctx, skip_dirs=skip_dirs)
  ```
  The `ctx: RepoContext` thread already established in Phase 28 (D-11) extends here. No changes to call ordering for other steps.

### Claude's Discretion

- Exact wording of `is_generated` content-marker regex (case sensitivity, line cap) — Claude may adjust if it surfaces false positives during planning.
- Naming of the import-root helper (`_resolve_import_root` vs `_find_package_root`) — Claude picks consistent with packages.py / structural_nodes.py module-internal conventions.
- File-fixture exact layout under `tests/fixtures/sample_monorepo/` — Claude shapes to cover D-22's heuristic coverage list; can add cases (e.g. an executable shebang script, a generated.{ts,go} file) if useful.

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Source-of-truth ontology spec
- `.planning/research/ONTOLOGY-SPEC.md` §3 (Node kinds), §4 (Edges), §9 (Scanner pipeline)

### v1.6 research (mandatory)
- `.planning/research/ARCHITECTURE.md` §"Scanner Additive Integration" (`structural_nodes.emit` call site), §"Source-Parser AST Extension" — confirms SPARSER-01 lands in source-parser, not graph-io
- `.planning/research/PITFALLS.md` — Pitfall 5 (`resolve.sweep` deletes Repository/Domain) is the centerpiece risk Phase 29 prevents via D-16; Pitfall 6 (path-heuristic role-flag drift) speaks to D-09/D-12
- `.planning/research/STACK.md` — confirms no new deps for Phase 29 (`os.access`, stdlib AST, `_ignore.py` walker already exist)
- `.planning/research/FEATURES.md` — Phase 29 has no user-facing CLI surface adds; query surfaces ship in Phase 32-33

### Phase 28 prior context
- `.planning/phases/28-schema-v2-uri-foundation/28-CONTEXT.md` — D-04/D-05/D-07/D-11 (RepoContext derivation + ctx threading); D-10 (URI lands in column, not attrs_json)

### Requirements + roadmap
- `.planning/REQUIREMENTS.md` — STRUCT-01..06 + SPARSER-01..02 (lines 25-32, 69-70)
- `.planning/ROADMAP.md` — Phase 29 block; success criteria #1-5 are non-negotiable

### Existing graph-io code (read before editing)
- `packages/graph-io/src/graph_io/update.py` — `run()` orchestration; `_git`, `_head`, `_all_tracked` helpers; insertion point for `structural_nodes.emit`
- `packages/graph-io/src/graph_io/packages.py` — `refresh()` writes `language: "python"` (line 44) / `"javascript"` (line 63) on each Package node; D-18 reads this
- `packages/graph-io/src/graph_io/upsert.py` — `_upsert_node` already pops `uri` to column (Phase 28 D-10); `structural_nodes.emit` writes via this path
- `packages/graph-io/src/graph_io/resolve.py` — `sweep()` deletion query; D-16 edits the WHERE clause
- `packages/graph-io/src/graph_io/_ignore.py` — `should_skip()` for the FS walk; reuse
- `packages/graph-io/src/graph_io/uri.py` — `repo_uri`, `subpkg_uri`, `file_uri` helpers (Phase 28 lands)

### Source-parser (cross-package)
- `packages/source-parser/src/source_parser/` — SPARSER-01 lives here; locate the Python parse pass that produces `SourceNode.attrs` at file scope

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- `update._git`, `_head`, `_all_tracked`, `_diff` — D-01's `default_branch` derivation reuses `_git(["symbolic-ref", "--short", "refs/remotes/origin/HEAD"], cwd=repo_root)` and strips the `origin/` prefix.
- `packages.refresh` already populates `language` on Package node attrs — D-18 reads this without new schema.
- `_ignore.should_skip` and the existing `skip_dirs` set — pass through to `structural_nodes.emit` for the FS walk. Matches the pattern `packages.refresh` already uses.
- `uri.repo_uri`, `uri.pkg_uri`, `uri.subpkg_uri`, `uri.file_uri` — Phase 28 ships these; D-01/D-06/D-07/D-13/D-14 use them.
- `_upsert_node` pop-uri-to-column path — Phase 28 D-10 covers this; no additional plumbing.
- `resolve.sweep` deletion query lives in a single SQL statement in `resolve.py` — D-16 is a one-line edit.

### Established Patterns
- New emitters slot into `update.run()` as `module.emit(conn, repo_root=..., ctx=..., skip_dirs=...)` calls between `packages.refresh` and `resolve.sweep`. Matches research's "additive integration" doctrine in ARCHITECTURE.md §"Scanner Additive Integration".
- Test fixtures live under `tests/fixtures/`; test cases construct expected graphs via `_run_cli` on a tmp_path-copied fixture. Mirrors `test_store.py` v1-DB fixture pattern (Phase 28 D-12).
- Role-flag heuristics are kept as module-private constants (allow-lists, regexes) at the top of `structural_nodes.py`. Planner should consolidate D-09 through D-12's patterns there.

### Integration Points
- `update.run()` is the only writer entry point — single insertion site for `structural_nodes.emit`.
- `resolve.sweep` runs AFTER `structural_nodes.emit` (ordering established in Phase 28 D-11 thread); D-16's WHERE-clause edit must NOT delete the newly-emitted Repository/SubPackage nodes.
- Source-parser SPARSER-01 attrs flow through the existing AST pass — graph-io reads them when emitting File nodes; no IPC boundary, just attrs.

</code_context>

<specifics>
## Specific Ideas

- D-01's `default_branch` query: `_git(["symbolic-ref", "--short", "refs/remotes/origin/HEAD"])` returns `origin/main` (or whatever); strip the `origin/` prefix. If the symref isn't set (fresh clone, no origin), fall back to `_git(["symbolic-ref", "--short", "HEAD"])`. Detached HEAD ⇒ NULL.
- D-10 (`is_config`) allow-list should be a single `frozenset[str]` for exact-match filenames + a list of `fnmatch` patterns for the `*.config.{ext}` family. Two-tier match keeps the common-case fast.
- D-11 content-marker scan should use `errors="ignore"` on file open to tolerate binaries that slipped past `_ignore.should_skip` — never let one weird file crash the walk.
- D-22 fixture layout suggestion (Claude can adjust):
  ```
  tests/fixtures/sample_monorepo/
    pyproject.toml                          # root manifest (workspace? skip)
    packages/
      mypkg/
        pyproject.toml
        src/mypkg/__init__.py
        src/mypkg/foo.py
        src/mypkg/sub/__init__.py
        src/mypkg/sub/bar.py
        src/mypkg/sub/deep/__init__.py
        src/mypkg/sub/deep/baz.py
        tests/test_foo.py
      jspkg/
        package.json
        index.js
        types.d.ts
        gen/data.gen.ts
    tests/
      integration/test_top.py
  ```

</specifics>

<deferred>
## Deferred Ideas

- **PEP 420 namespace package support** — defer to v1.7 (D-04). Add when a real repo without `__init__.py` boundaries lands and a user query needs it.
- **`is_executable` for non-extension files via mime sniff** — current D-12 covers shebang + exec bit, which together cover the common case. If we hit a real Windows-on-WSL case with neither signal, revisit.
- **Cross-Package "what depends on what" structural edges** — Package-level dependency edges are the responsibility of derived edges (Phase 31). Phase 29 stops at `physically_contains`.
- **Smoke test on the agent-research repo itself** — STRUCT-04 invariant is fixture-tested per D-22. A second smoke test running `cg update --full` against `.` could be added in Phase 33 (CLI surface) when `cg describe-repo` lands.
- **Symlink handling in the FS walk** — assume no symlinks for now; if a real repo grows them, _ignore.py can be extended.

</deferred>

---

*Phase: 29-structural-nodes-containment-tree*
*Context gathered: 2026-05-26*
