# Project Research Summary

**Project:** agent-research — v1.6 Code Graph Ontology Expansion (`graph-io`)
**Domain:** SQLite-backed code-graph store — additive ontology expansion with URI identity, new structural/conceptual node types, and derived edge computation
**Researched:** 2026-05-25
**Confidence:** HIGH

## Executive Summary

v1.6 is a focused, additive extension to `packages/graph-io`. The milestone lands the full ontology spec (ONTOLOGY-SPEC.md) — schema v2, URI identity, new structural and conceptual node types, derived edges, and a `cg` CLI surface for querying them — without touching `graph-wiki-agent`, the plugin, or any other package. The research converged on a clear build order: seven phases (A through G) with explicit dependency gates. The architecture is strictly additive: six new emitter modules plug into the existing `update.py` transaction via flat function calls, no pipeline restructuring.

The recommended approach is to build schema + URI identity first (Phase A), structural node emission second (Phase B), entry points and test suites third (Phase C), domain layer and derived edges fourth (Phase D), query layer fifth (Phase E), CLI surface sixth (Phase F), and brand sweep last (Phase G). URI identity is `TEXT` nullable in v1.6 — `UNIQUE NOT NULL` is deferred to v1.7 after URI generation is validated against real repos. The 9-stage scanner pipeline from spec §9 is also deferred to v1.7; v1.6 uses flat additive calls within the existing transaction boundary.

The principal risks are: (1) `resolve.sweep` silently deleting `Repository` and `Domain` nodes that have `path=NULL` and are only edge sources, not destinations; (2) the URI value landing in `attrs_json` instead of the `uri` column if `_upsert_node` is not updated in Phase A before any emitter is written; (3) test file re-parenting breaking due to call-order inversion in `update.py`; (4) convention-based domain inference producing false-positive domain nodes from `tests/` subdirectories; and (5) `SCHEMA_MISMATCH` exit code (4) remaining unwired in `cli/main.py`. All five risks have specific code-level prevention steps detailed in PITFALLS.md.

---

## Key Findings

### Recommended Stack

The stack additions for v1.6 are minimal. All required capabilities are already present in the workspace: `tomllib` (stdlib) for `pyproject.toml` parsing, `json` (stdlib) for `package.json`, `configparser` (stdlib) for pytest config detection, and `tree-sitter` (already owned by `source-parser`) for AST role flags. The one explicit addition is making `pyyaml>=6.0.3` a direct dependency in `packages/graph-io/pyproject.toml` — it currently arrives only transitively via `python-frontmatter`, and graph-io does not depend on `python-frontmatter` directly.

**Core technologies (new surface in v1.6):**
- `graph_io/uri.py` (new, ~20 LOC): URI composition functions — `repo_uri`, `pkg_uri`, `subpkg_uri`, `file_uri`, `domain_uri`, `entry_point_uri`, `test_suite_uri` — plain f-strings, no URI library
- `pyyaml>=6.0.3` (explicit dep): `yaml.safe_load()` in `graph_io/domains.py` for `domains.yaml` — no round-trip needed, ruamel.yaml/strictyaml rejected
- `tomllib` (stdlib, already imported in `packages.py`): manifest parsing for `[project.scripts]` entry points
- `configparser` (stdlib): pytest.ini / setup.cfg [tool:pytest] detection in `graph_io/detect_tests.py`
- `sqlite3` (stdlib): existing pattern extended — `uri TEXT` column added, no migration library needed; hand-rolled version gate + mandatory full rebuild is the correct and existing architecture

**What NOT to add:** yoyo-migrations, sqlite-utils, rfc3986/yarl/hyperlink, ruamel.yaml, strictyaml, node interop for jest.config parsing, second TOML parser.

### Expected Features

All features map directly to spec §10 example queries. The table stakes / differentiator split below follows that mapping.

**Must have (table stakes — P1, directly from §10):**
- Schema v2 + URI identity — foundation for all new nodes; `SCHEMA_VERSION` bump to 2, `uri TEXT` nullable column + index
- `cg list-entry-points <pkg> [--kind executable|library]` — "What can I run from this package?" / "What does this package export?"
- `cg list-suites` — discovery primitive
- `cg what-tests <package>` — "What tests cover this package?" (suite-level)
- `cg list-domains` + `cg describe-domain <name>` — domain discovery + inspection
- `cg domain-refs <name>` — "What does the Billing domain depend on (outside of itself)?"
- `cg domain-deps <name>` — "Does Billing depend on Auth?"
- Derived edge computation (`references`, `depends_on`) on `cg update` — backing store for all domain queries
- Extensions to existing commands: `cg describe-package` (+ domains, entry points, suites), `cg describe-path` (+ File role flags), `cg status` (+ repo URI), `cg find` (+ new node kinds)
- Brand sweep: README + CLI strings (`lattice-graph-core` -> `graph-wiki`, `~/.lattice/graph/code.db` -> canonical path)

**Should have (differentiators — P2, complete §10 coverage):**
- `cg list-scripts` — union of `EntryPoint kind:executable` + `File is_executable:true`
- `cg what-tests <domain>` (domain variant) — "What integration tests touch the Billing domain?"
- `cg cross-cutting` — packages with zero `belongs_to_domain` edges, ranked by `references` count
- `cg describe-repo`, `cg list-packages` — structural completeness

**Defer to v1.7+:**
- `cg domain-callers` — recursive `physically_contains` + `calls` join; HIGH complexity
- File-level `tests` edges in `cg what-tests` — best-effort/advisory per spec §4.3
- `cg update --domains-only` flag — requires pipeline stage decomposition (v1.7)
- Wiki render commands, agent integration helpers, `tagged_with` mechanism, cross-repo domains

### Architecture Approach

v1.6 plugs in additively: six new emitter modules added, `update.py` gains six flat function calls inside the existing `store.transaction` block. The call order is non-negotiable and enforced by data dependencies.

**Enforced call order in `update.py`:**
`_process_files` -> `packages.refresh` -> `entry_points.emit` -> `structural_nodes.emit` -> `test_suites.emit` -> `domains.emit` -> stale-node cleanup -> `resolve.sweep` -> `derived_edges.compute` -> `_set_metadata`

**Major components:**

1. **`schema.py` + `store.py` + `upsert.py` + `uri.py` (Phase A)** — schema v2 DDL, `SCHEMA_MISMATCH` exit code wired, `_upsert_node` pops `uri` from `node.attrs` to write to `uri` column (not `attrs_json`)
2. **`structural_nodes.py` (Phase B)** — `Repository`, `SubPackage`, `File`-with-role-flags, `physically_contains` strict-tree; `resolve.py` guard extended to exclude `repository`, `domain`, `test_suite`, `entry_point` from placeholder cleanup
3. **`entry_points.py` + `test_suites.py` + `detect_tests.py` (Phase C)** — `packages.refresh` returns manifest data (no double I/O); test file re-parenting from Package to TestSuite containment
4. **`domains.py` + `derived_edges.py` (Phase D)** — `yaml.safe_load()` for `domains.yaml`; convention inference with `tests/` exclusion; cycle detection; `derived_edges.compute` after `resolve.sweep`; gated on `domains.yaml` existence
5. **`queries.py` extensions (Phase E)** — new query functions for all new node/edge types
6. **13 new CLI modules (Phase F)** — thin wrappers registered in `cli/main.py`
7. **Brand sweep (Phase G)** — README + CLI description + `LATTICE_GRAPH_LOCK_TIMEOUT_MS` deprecation alias

### Critical Pitfalls

Top five from PITFALLS.md, in priority order:

1. **`resolve.sweep` deletes `Repository`/`Domain` nodes** (`path=NULL`, only edge sources not destinations) — extend cleanup SQL `kind NOT IN` guard to include `('repository', 'domain', 'test_suite', 'entry_point')`; add Phase B test that Repository node survives sweep (PITFALL 5)
2. **URI lands in `attrs_json` instead of `uri` column** — `_upsert_node` must pop `uri` from `node.attrs` before serializing; `test_upsert.py` assertion must exist before Phase B begins (PITFALL 4)
3. **`SCHEMA_MISMATCH` exit code (4) not wired** — `cli/main.py` needs `except store.SchemaMismatchError` -> `sys.exit(exit_codes.SCHEMA_MISMATCH)`; README "reserved — not yet enforced" removed in same commit (PITFALL 2)
4. **Call-order inversion in `update.py`** — `test_suites.emit` must run after `packages.refresh`; `derived_edges.compute` must run after `resolve.sweep`; enforce with comment block above call sequence and a test asserting test files have exactly one `physically_contains` edge (PITFALL 6)
5. **Domain inference classifies `tests/` subdirectories as domain candidates** — hardcode skip list including `tests`, `packages`, `libs`, `apps`, `shared`, `common`, `src`, `dist`, `build`; Phase D test asserts no `Domain(billing)` created from `tests/billing/` directory (PITFALL 10)

Secondary watch items: `SCHEMA_VERSION` bumped but `_DDL_STATEMENTS` not updated (add `test_nodes_table_has_uri_column` as first Phase A test — PITFALL 1); `domains.yaml` package names vs. directory names (print known-packages hint in warning — PITFALL 9); `LATTICE_GRAPH_LOCK_TIMEOUT_MS` env var silently ignored after brand sweep (deprecation fallback in `update.py` — PITFALL 12).

---

## Implications for Roadmap

Phase numbering continues from Phase 27. v1.6 starts at Phase 28.

### Phase A (28): Schema + URI Foundation

**Rationale:** Hard prerequisite for every other phase. No emitter can write to a `uri` column that does not exist. `SCHEMA_MISMATCH` exit code wiring is a correctness fix that must land before any user-visible schema change.
**Delivers:** `SCHEMA_VERSION = 2`, `uri TEXT` nullable column + `idx_nodes_uri` index, `_upsert_node` URI extraction, `SCHEMA_MISMATCH` exit code 4 wired, `graph_io/uri.py` with all URI composition functions, `SchemaMismatchError` message updated, `test_schema_version_is_one` sentinel renamed to `test_schema_version_is_two`
**Addresses:** Schema v2 + URI identity (all P1 table stakes depend on this)
**Avoids:** Pitfalls 1, 2, 3, 4, 13
**Research flag:** None needed — existing codebase pattern is clear; STACK.md and PITFALLS.md have exact code snippets

### Phase B (29): Structural Nodes

**Rationale:** Depends on Phase A. Repository and File-with-role-flags form the physical containment tree that TestSuite re-parenting in Phase C requires.
**Delivers:** `structural_nodes.py` with `Repository`, `SubPackage`, `File`-with-role-flags + `physically_contains` strict-tree; `resolve.py` guard extended; `source_parser/parsers/python.py` gains `_has_main_block` + `_has_importable_symbols`; `update.py` gains `structural_nodes.emit` call + `_apply_ast_role_flags` post-pass
**Addresses:** Structural nodes (spec §3); File role flags; `physically_contains` tree
**Avoids:** Pitfall 5 (resolve.sweep deletion guard), Pitfall 18 (longest-prefix-wins)
**Research flag:** None needed — flag detection methods and module boundary fully specified in ARCHITECTURE.md + STACK.md

### Phase C (30): EntryPoint + TestSuite

**Rationale:** Depends on Phase B. TestSuite re-parenting requires Package containment edges from structural_nodes.emit to exist first.
**Delivers:** `detect_tests.py`, `entry_points.py`, `test_suites.py`; `packages.py` extended to return manifest data; `update.py` gains two new emit calls with documented ordering constraint
**Addresses:** EntryPoint nodes (spec §3); TestSuite nodes (spec §3 + §7 layout patterns 1-5); entry point P1 CLI features
**Avoids:** Pitfall 6 (call-order test), Pitfall 8 (path-qualified `implemented_by` resolution), Pitfall 16 (conftest.py not treated as framework config), Pitfall 19 (fixture isolation)
**Research flag:** None needed — `_walk_exports` recursive walker and PYTEST_CONFIGS detection specified in STACK.md

### Phase D (31): Domain Layer + Derived Edges

**Rationale:** Depends on Phase A+B. Domain nodes require package nodes (B) and URI support (A). Derived edges depend on resolved imports so `derived_edges.compute` goes after `resolve.sweep`.
**Delivers:** `domains.py` with `load_domains()`, `DomainConfig`/`DomainEntry` dataclasses, convention inference with exclusion list, cycle detection; `derived_edges.py`; `update.py` gains `domains.emit` + `derived_edges.compute` calls
**Addresses:** Domain nodes (spec §3); `belongs_to_domain` + `domain_contains_domain` + `references` + `depends_on` edges (spec §4.4 + §4.5); `domains.yaml` format
**Avoids:** Pitfall 10 (tests/ false-positive), Pitfall 17 (cycle detection), Pitfall 9 (package name warning), Pitfall 11 (performance gate)
**Research flag:** None needed — DomainConfig dataclass and inference strategies fully specified in ARCHITECTURE.md

### Phase E (32): Query Layer Extension

**Rationale:** All emitters must have run before query layer validation is meaningful. Phase E is entirely read-side.
**Delivers:** New query functions in `queries.py`: `describe_repo`, `list_domains`, `describe_domain`, `list_entry_points`, `list_suites`, `describe_suite`, `what_tests`, `domain_refs`, `domain_deps`, `cross_cutting`, `list_packages`; extensions to `describe_package` and `describe_path`
**Addresses:** All §10 example queries except `domain-callers` (deferred to v1.7)
**Research flag:** Needs spike — `WITH RECURSIVE` SQL for domain hierarchy traversal in `describe_domain` / `what_tests --domain` needs validation against the actual SQLite schema. Confirm SQLite 3.35+ `WITH RECURSIVE` handles `domain_contains_domain` traversal combined with `belongs_to_domain` collection correctly. Also verify the UNION query shape for `list_scripts`.

### Phase F (33): CLI Extension

**Rationale:** Depends on Phase E. CLI modules are thin wrappers around query functions.
**Delivers:** 13 new `cli/q_*.py` modules; `cli/main.py` updated to register new subcommands
**Addresses:** CLI surface for all P1 and P2 features
**Research flag:** None needed — uniform thin-wrapper pattern across existing 13 CLI modules

### Phase G (34): Brand Sweep

**Rationale:** Zero code dependencies — deferred to last to avoid merge conflicts with substantive changes. Brand grep gate validates completion.
**Delivers:** `packages/graph-io/README.md` updated; `cli/main.py` description string updated; `LATTICE_GRAPH_LOCK_TIMEOUT_MS` deprecation alias in `update.py`; `.brand-grep-allow` updated for deprecated env var name
**Avoids:** Pitfall 12 (silent env var breakage)
**Research flag:** None needed — targets enumerated in ARCHITECTURE.md; existing check-brand.sh validates

### Phase Ordering Rationale

- URI column must exist before any emitter writes a URI (A blocks all)
- Package containment edges must exist before test suite re-parenting (B blocks C)
- Package nodes must exist before domain assignment (B blocks D)
- All emitters must have run before query layer validation is meaningful (A+B+C+D block E)
- Query functions must exist before CLI modules wrap them (E blocks F)
- Brand sweep has no blockers (G runs last for safety)

The call order inside `update.py` is non-negotiable: `_process_files` -> `packages.refresh` -> `entry_points.emit` -> `structural_nodes.emit` -> `test_suites.emit` -> `domains.emit` -> stale-node cleanup -> `resolve.sweep` -> `derived_edges.compute` -> `_set_metadata`. Enforce with a comment block above the sequence and a test asserting test files have exactly one `physically_contains` edge post-update.

### Research Flags

Phases needing deeper investigation:
- **Phase E (Query Layer):** `WITH RECURSIVE` domain traversal SQL needs a spike. Also: UNION query for `list_scripts` and multi-join for `what_tests --domain`.
- **Phase C (TestSuite incremental re-parenting):** Interaction between incremental `cg update` and test suite re-parenting needs explicit test coverage confirming stale-node cleanup does not delete freshly re-parented `TestSuite -> File` edges.

Phases with well-documented patterns (skip deeper research):
- **Phase A:** Schema DDL, upsert extension, exit code wiring — exact code snippets in STACK.md and PITFALLS.md
- **Phase B:** FS walk pattern established in `_ignore.py`; resolve.sweep guard SQL specified with exact SQL in PITFALLS.md
- **Phase D:** `yaml.safe_load` trivial; DomainConfig specified; cycle detection is standard DFS
- **Phase F:** Uniform thin-wrapper pattern across existing 13 CLI modules
- **Phase G:** Fully enumerated targets; existing grep gate validates

---

## Confidence Assessment

| Area | Confidence | Notes |
|------|------------|-------|
| Stack | HIGH | All decisions grounded in existing codebase with file:line references; pyyaml only new dep, already transitively installed |
| Features | HIGH | Directly mapped from spec §10; anti-features justified against spec §11 and PROJECT.md deferral list |
| Architecture | HIGH | Grounded entirely in existing graph-io source with file:line references; call order and module boundaries verified |
| Pitfalls | HIGH | 8 of 14 pitfalls cite specific file:line locations; all prevention steps have associated test assertions |

**Overall confidence:** HIGH

### Gaps to Address

Requirement-time decisions needed before phases can be fully planned:

- **`packages.refresh` return type change** — cleanest double-I/O fix is returning `list[tuple[Path, dict]]` for `entry_points.emit`; confirm no current callers break before Phase C planning
- **`pkg_uri` uses `rel_path` not `pkg_name`** — prevents URI collisions in repos with two packages named `utils`; verify exact `pkg_uri` signature in `uri.py` before Phase A closes (PITFALL 7)
- **`derived_edges.compute` performance budget** — establish acceptance criterion (e.g., `cg update` incremental in <3s on 100-package repo) as Phase D acceptance criteria
- **`uri TEXT` nullable documented as intentional** — add code comment in Phase A that `UNIQUE NOT NULL` is deliberately deferred to v1.7; prevents future maintainer confusion

---

## Sources

### Primary (HIGH confidence — directly reviewed source files)

- `packages/graph-io/src/graph_io/schema.py` — `SCHEMA_VERSION = 1`, `_DDL_STATEMENTS` DDL
- `packages/graph-io/src/graph_io/store.py` — `SchemaMismatchError`, `_check_schema_version`, connect logic
- `packages/graph-io/src/graph_io/upsert.py` — `_upsert_node`, `NodeKey(kind, name, path)` identity pattern
- `packages/graph-io/src/graph_io/resolve.py` — placeholder-node deletion query (line 50-56)
- `packages/graph-io/src/graph_io/update.py` — existing orchestration flow, `LATTICE_GRAPH_LOCK_TIMEOUT_MS` line 130
- `packages/graph-io/src/graph_io/packages.py` — `_discover_manifests`, `refresh`, existing stdlib imports
- `packages/graph-io/src/graph_io/exit_codes.py` — `SCHEMA_MISMATCH = 4`, `UPDATE_IN_PROGRESS = 6`
- `packages/graph-io/README.md` — `SCHEMA_MISMATCH = 4` marked "reserved — not yet enforced"; brand sweep targets
- `packages/graph-io/src/graph_io/cli/main.py` — 13 existing subcommands, `lattice code graph CLI` description
- `packages/source-parser/src/source_parser/projections/graph.py` — `GraphNode.attrs` handoff point
- `packages/graph-io/conftest.py` — bare `sqlite3.connect(":memory:")` fixture (no schema applied)
- `packages/graph-io/tests/test_schema.py` — `test_schema_version_is_one()` sentinel

### Primary (HIGH confidence — spec and planning documents)

- `.planning/research/ONTOLOGY-SPEC.md` — authoritative node types, edge types, scanner pipeline, example queries
- `.planning/PROJECT.md` — v1.6 milestone scope, deferred items, phase numbering continuation at 28
- `.planning/research/STACK.md` — library decisions, version compatibility, code snippets
- `.planning/research/FEATURES.md` — §10 query-to-command coverage matrix, anti-features
- `.planning/research/ARCHITECTURE.md` — module map, build order, call sequence, data flow, anti-patterns
- `.planning/research/PITFALLS.md` — 14 pitfalls with file:line citations, prevention steps, phase assignments

### Secondary (MEDIUM confidence — version verification)

- PyPI: `PyYAML` 6.0.3 — confirmed latest stable; released 2024-12-16
- `uv pip list` — confirmed PyYAML 6.0.3, tree-sitter 0.25.2 installed in workspace

---

*Research completed: 2026-05-25*
*Ready for roadmap: yes*
