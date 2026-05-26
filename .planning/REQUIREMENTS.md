# Requirements: agent-research — Milestone v1.6 (Code Graph Ontology Expansion)

**Defined:** 2026-05-25
**Core Value:** Faithfully reproduce the graph-wiki plugin's wiki-maintenance workflows while running entirely on AWS Bedrock with parallel subagents, so the same outcomes can be achieved at meaningfully lower cost than the current Claude-Code-hosted plugin.

**Milestone Goal:** Land the full ontology spec (`.planning/research/ONTOLOGY-SPEC.md`) inside `graph-io` — schema v2, URI identity, all new node + edge types, additive scanner extensions, brand sweep — so v1.7 can integrate graph-io into `graph-wiki-agent` and redesign the wiki on top of it. Plugin and existing wiki scripts stay functional and untouched.

**Source-of-truth design doc:** `.planning/research/ONTOLOGY-SPEC.md`
**Research synthesis:** `.planning/research/SUMMARY.md`

---

## v1.6 Requirements

Requirements for this milestone. Each maps to a roadmap phase.

### Schema v2 + URI Identity Foundation

- [x] **SCHEMA-01**: `cg update --full` on a schema-v1 database upgrades to schema v2, rebuilding nodes + edges with URIs populated and producing a consistent v2 store
- [x] **SCHEMA-02**: `cg update` (incremental) against a v1.5 database raises `SCHEMA_MISMATCH` (exit code 4) with a clear message instructing the user to run `cg update --full`
- [x] **SCHEMA-03**: `graph_io.uri` exposes composition helpers (`repo_uri`, `pkg_uri`, `subpkg_uri`, `file_uri`, `domain_uri`, `entry_point_uri`, `test_suite_uri`) producing stable URI-style IDs (`pkg:org/foo/auth-service`, `repo:org/foo`, `domain:billing`)
- [x] **SCHEMA-04**: URIs are persisted on a dedicated `uri TEXT` column on the `nodes` table (not inside `attrs_json`); URI column is nullable in v1.6 — AST nodes (functions, classes, methods) have NULL URI
- [x] **SCHEMA-05**: `cg update --full` is idempotent — running twice on the same git state produces a byte-identical `code.db`

### Structural Nodes + Containment Tree

- [ ] **STRUCT-01**: Scanner emits one `Repository` node per scanned repo, carrying URL/default-branch/owner attrs derived from `git remote` and `git config` when available
- [ ] **STRUCT-02**: Scanner emits `SubPackage` nodes (Python-only) for each `__init__.py`-containing subdirectory below a package root; JS/TS scans do NOT emit `SubPackage` nodes (directory paths live as attributes on `File` per spec §3)
- [ ] **STRUCT-03**: `File` nodes carry role-flag attrs `is_importable`, `is_executable`, `has_main`, `is_test`, `is_config`, `is_generated`, `is_type_only` — flags are independent booleans (a file can be both `is_importable` and `is_executable`)
- [ ] **STRUCT-04**: `physically_contains` edges form a strict tree — each node has exactly ONE structural parent (Repository → Package → [Python: SubPackage* → File | JS/TS: File]); test files are NOT under Package containment (they live under TestSuite)
- [ ] **STRUCT-05**: Generic container folders (`packages/`, `libs/`, `tests/`, `apps/`, `shared/`, `common/`) are NEVER emitted as nodes — their paths exist only as attributes on the nodes they contain
- [ ] **STRUCT-06**: `resolve.sweep` cleanup excludes the new node kinds (`repository`, `domain`, `test_suite`, `entry_point`) from `path=NULL` deletion — prevents silent loss of structural/conceptual nodes that have no source-file path

### Entry Points

- [x] **ENTRY-01**: Scanner emits `EntryPoint` nodes from `pyproject.toml [project.scripts]` and `[project.entry-points]` declarations
- [x] **ENTRY-02**: Scanner emits `EntryPoint` nodes from `package.json` `bin`, `main`, `module`, and `exports` declarations (with recursive walk over conditional `exports` per STACK.md)
- [x] **ENTRY-03**: `EntryPoint.kind` is `executable` (CLI/bin entries) or `library` (importable entries); `EntryPoint.source` identifies which manifest declaration produced it (e.g., `pyproject.scripts`, `package.json.bin`, `package.json.exports`)
- [x] **ENTRY-04**: `declares_entry_point` edges connect Package → EntryPoint; `implemented_by` edges connect EntryPoint → File for path-only entries, or EntryPoint → Function/Class for callable-syntax entries (`pkg.cli:main`)
- [x] **ENTRY-05**: Convention-based executable files (shebang scripts in `scripts/`, etc.) are captured via `File.is_executable: true` — they do NOT produce `EntryPoint` nodes (per spec §3 "Explicitly not nodes")

### Test Suites

- [x] **TEST-01**: Scanner emits `TestSuite` nodes from filesystem layout + framework config (pytest.ini, pyproject.toml [tool.pytest], setup.cfg [tool:pytest], jest.config.{js,ts,mjs,cjs}, vitest.config.{js,ts}, mocha config variants)
- [x] **TEST-02**: Repo-root `tests/` is NOT a node — each immediate subdirectory of `tests/` becomes a `TestSuite`; if `tests/` contains test files directly (no subdirs), `tests/` itself becomes one suite contained by Repository
- [x] **TEST-03**: Package-local test directories (`packages/auth/tests/`) become `TestSuite` nodes contained by their Package; test files within are under the suite, not directly under the Package
- [x] **TEST-04**: Test files are re-parented from Package containment to TestSuite containment — `Package physically_contains` subtree NEVER includes test files
- [x] **TEST-05**: `TestSuite.kind` is best-effort-classified as `unit`, `integration`, `e2e`, `contract`, or `unknown` from naming + config; directory names (`integration/`, `e2e/`) inform `kind` but do NOT determine suite targets
- [x] **TEST-06**: Suite-level `tests` edges are derived from imports in the suite's test files: `TestSuite → Package` (one or many), `TestSuite → Domain` (when the suite touches a whole domain), or `TestSuite → Repository` (whole-system suites)
- [x] **TEST-07**: TestSuites are flat — there is NO `TestSuite → TestSuite` hierarchy even when on-disk layout suggests one (`tests/integration/auth/`)

### Domains (explicit-config-only)

- [x] **DOMAIN-01**: Scanner emits `Domain` nodes from a `domains.yaml` file at the repository root (format documented in graph-io README)
- [ ] **DOMAIN-02**: `belongs_to_domain` edges connect Package → Domain; a package may belong to 0..N domains — zero-domain packages are intentional (cross-cutting utilities), multi-domain membership is supported
- [x] **DOMAIN-03**: `domain_contains_domain` edges form a tree (one parent per domain); cycle detection during scan raises a clear error identifying the cycle
- [ ] **DOMAIN-04**: Missing `domains.yaml` is NOT an error — all packages show as zero-domain (cross-cutting); zero-domain is the default behavior
- [ ] **DOMAIN-05**: Domain assignment in v1.6 is EXPLICIT-CONFIG-ONLY — convention-based folder-name inference, import-graph clustering, and LLM-proposed groupings are deferred to v1.7+ (decision logged 2026-05-25)

### Derived Edges

- [x] **DERIVED-01**: `references` edges (Domain → Package) are computed when a package in domain D imports a package P that does NOT belong to D; carries `usage_count` attr (number of distinct packages in D that import P)
- [x] **DERIVED-02**: `depends_on` edges (Domain → Domain) are computed when a package in domain A imports a package belonging to domain B
- [ ] **DERIVED-03**: Derived edges are recomputed on every `cg update` (after `resolve.sweep` completes) and persisted to the `edges` table — query-time reads are cheap and do not recompute
- [ ] **DERIVED-04**: Transitive domain membership for nested domains is NOT stored — queries walk `domain_contains_domain` at read time per spec §6

### Source-Parser AST Extensions

- [ ] **SPARSER-01**: `source-parser` Python parser populates `_has_main_block` (detects `if __name__ == "__main__":`) and `_has_importable_symbols` (detects presence of public top-level definitions) on file-level `SourceNode.attrs`
- [ ] **SPARSER-02**: `graph-io` reads these source-parser attrs to refine `File.has_main` and `File.is_importable` role flags; other role flags (`is_test`, `is_config`, `is_generated`, `is_type_only`) remain path-heuristic-only in graph-io

### Query Layer Extensions

- [ ] **QUERY-01**: `find` extended to accept new node kinds (`repository`, `subpackage`, `entry_point`, `test_suite`, `domain`)
- [ ] **QUERY-02**: `describe_package` output extended with: domains the package belongs to, entry points it declares, test suites that target it
- [ ] **QUERY-03**: `describe_path` output extended with File role flags for file-kind nodes
- [ ] **QUERY-04**: New read-only query helpers shipped: `describe_repository`, `describe_domain`, `describe_entry_point`, `describe_test_suite`, `domain_references`, `domain_depends_on`, `cross_cutting_packages`, `tests_for_package`, `tests_for_domain`, `entry_points_for_package`, `list_repositories`, `list_packages`, `list_entry_points`, `list_test_suites`, `list_domains`, `list_scripts`

### `cg` CLI Surface

- [ ] **CLI-01**: `cg describe-repo` describes the current repository (URI, default branch, owner, packages contained)
- [ ] **CLI-02**: `cg list-packages` lists all `Package` nodes in the DB
- [ ] **CLI-03**: `cg list-entry-points <pkg> [--kind executable|library]` lists entry points declared by a package
- [ ] **CLI-04**: `cg list-scripts` returns the union of declared EntryPoints with `kind:executable` and Files with `is_executable: true` (spec §10 query "What scripts exist in this repo?")
- [ ] **CLI-05**: `cg list-suites` lists all `TestSuite` nodes
- [ ] **CLI-06**: `cg describe-suite <name>` describes a TestSuite (kind, framework, files contained, packages tested)
- [ ] **CLI-07**: `cg what-tests <package>` returns TestSuite nodes that test a package (via suite-level `tests` edges)
- [ ] **CLI-08**: `cg what-tests <domain>` returns TestSuite nodes that test a domain (via `TestSuite → Domain` edges OR via `TestSuite → Package` where the package `belongs_to_domain`) — spec §10 "What integration tests touch the Billing domain?"
- [ ] **CLI-09**: `cg list-domains` lists all `Domain` nodes
- [ ] **CLI-10**: `cg describe-domain <name>` describes a domain (packages, sub-domains, references, depends-on)
- [ ] **CLI-11**: `cg domain-refs <name>` shows packages referenced by a domain with usage counts (spec §10 "What does the Billing domain depend on outside of itself?")
- [ ] **CLI-12**: `cg domain-deps <name>` shows domains that a domain depends on
- [ ] **CLI-13**: `cg cross-cutting` shows packages with zero `belongs_to_domain` edges, ranked by incoming `references` count (spec §10 "Which utility packages are most widely used?")
- [ ] **CLI-14**: `cg status` extended to surface the repository URI alongside the existing staleness check

### Brand Sweep (graph-io only)

- [ ] **BRAND-01**: `packages/graph-io/README.md` rebranded — `lattice-graph-core` → graph-wiki phrasing; `~/.lattice/graph/code.db` → canonical graph-wiki path (resolved via `workspace_io.paths.graph_dir`)
- [ ] **BRAND-02**: All `cg` CLI description/help strings use graph-wiki branding; no surviving `lattice` references in any user-facing string emitted by graph-io
- [ ] **BRAND-03**: `LATTICE_GRAPH_LOCK_TIMEOUT_MS` env var renamed to `GRAPH_WIKI_LOCK_TIMEOUT_MS` (or workspace-consistent name); deprecation alias preserves backward compat for one milestone with a deprecation warning
- [ ] **BRAND-04**: Sweep scope is LIMITED to `packages/graph-io/` and its consumers — does NOT touch `plugins/graph-wiki/`, `packages/wiki-io/`, or any other package; explicitly NOT touching `_SKIP_REPO_PREFIXES = ("lattice/",)` in `packages.py` (functional behavior, not brand text, per PITFALLS.md)

---

## Future Requirements

Deferred to v1.7+ (or later) — tracked but not in v1.6 roadmap.

### Agent Integration (PRIMARY v1.7 focus)

- **AGENT-01**: `graph-wiki-agent` librarian gains a code-graph tool that queries graph-io during query workflow (e.g., "what calls X", "what implements entry point Y")
- **AGENT-02**: Scanner / ingestor consume graph-io as source of truth for the package/file tree instead of re-walking the filesystem
- **AGENT-03**: New top-level `graph-wiki-agent graph {build|describe|query}` command wraps `cg` semantics for agent use

### Wiki Redesign on graph-io

- **WIKI-01**: Wiki content keyed by stable URI rather than filesystem location
- **WIKI-02**: Wiki renderer produces multiple views (flat-by-ID, by-domain, by-repo) from the same graph
- **WIKI-03**: Moving a package between domains is a single edge change, not a filesystem rename

### Scanner Pipeline Restructure

- **PIPELINE-01**: Split scanner into 9-stage pipeline per spec §9 (FS walk → manifest parse → test detect → AST parse → import resolve → test target derive → domain assign → derived edges → wiki render); enables `cg update --domains-only` (re-run stages 7-8 without AST re-parse)

### Advanced Domain Assignment

- **DOMAIN-CONV-01**: Convention-based inference from top-level named folders (billing/, location/) with generic-container exclusion list
- **DOMAIN-CLUSTER-01**: Import-graph clustering for domain suggestions
- **DOMAIN-LLM-01**: LLM-proposed groupings for human review

### Advisory Test Edges

- **TEST-FILE-01**: File-level `tests` edges (`test_foo.py → foo.py`, `foo.test.ts → foo.ts`) — derived best-effort from imports + filename conventions
- **TEST-FUNC-01**: Function-level `tests` edges from naming conventions + call graph

### Open Questions from Spec §11

- **OPEN-01**: `tagged_with` mechanism for utility-package categorization
- **OPEN-02**: Cross-repo domain scope — single Domain node spanning multiple repos
- **OPEN-03**: `domains.yaml` location strategy in multi-repo setups
- **OPEN-04**: Role-flag confidence metadata
- **OPEN-05**: Test suite consolidation threshold
- **OPEN-06**: `is_test_support` flag for fixtures/helpers vs test definitions

### URI Constraint Tightening

- **URI-CONSTRAINT-01**: `uri` column becomes `UNIQUE NOT NULL`; all node kinds (including AST nodes) carry URIs

### Carry-forward debt (NOT v1.6 scope)

- Nyquist compliance retroactive decision (0/21+ phases)
- Phase 14 SC#4 plugin smoke transcript
- `librarian.py:21` `_SLUG_ONLY_RE` parity fix
- 9 untracked quick tasks + 2 pending bootstrap todos (`2026-05-21-bootstrap-interactive-flag`, `2026-05-21-bootstrap-should-stub-empty-category-index-files`)

---

## Out of Scope

Explicitly excluded from v1.6.

| Feature | Reason |
|---------|--------|
| Agent integration (`graph-wiki-agent` consuming graph-io) | Primary v1.7 focus — landing the full ontology in graph-io is already a heavy surface; a focused milestone is cleaner |
| Wiki redesign on graph-io | Companion to agent integration in v1.7 |
| 9-stage scanner pipeline restructure (spec §9) | Additive extensions chosen for v1.6; pipeline split becomes load-bearing only when domain-overlay re-runs are needed |
| Convention-based domain inference | User decision 2026-05-25 — explicit `domains.yaml` only in v1.6; convention inference deferred to v1.7+ |
| File-level / function-level `tests` edges | Suite-level edges are the strong ones (spec §4.3); advisory file/function edges deferred to v1.7 |
| `cg domain-callers` (cross-domain function-level join) | HIGH complexity (recursive `physically_contains` + `calls` join); deferred to v1.7 per FEATURES.md |
| `cg update --domains-only` flag | Requires pipeline stage decomposition (v1.7) |
| URI `UNIQUE NOT NULL` constraint | URI column is nullable in v1.6 — tightening deferred to v1.7 after coverage is validated against real repos |
| `tagged_with` mechanism | Spec §11 open question — deferred to v1.7+ |
| Cross-repo domain support | Spec §11 open question — deferred to v1.7+ |
| Touching `plugins/graph-wiki/` or `wiki-io` | Plugin and existing wiki scripts must stay functional; v1.6 is graph-io-only |
| Custom TUI / non-Bedrock providers / nested subagents / vault format migration / public PyPI release / file watchers | Per PROJECT.md "Out of Scope" — deferred past v1.x to v2.0+ |

---

## Traceability

Which phases cover which requirements. Filled in during roadmap creation.

| Requirement | Phase | Status |
|-------------|-------|--------|
| SCHEMA-01 | Phase 28 | Complete |
| SCHEMA-02 | Phase 28 | Complete |
| SCHEMA-03 | Phase 28 | Complete |
| SCHEMA-04 | Phase 28 | Complete |
| SCHEMA-05 | Phase 28 | Complete |
| STRUCT-01 | Phase 29 | Pending |
| STRUCT-02 | Phase 29 | Pending |
| STRUCT-03 | Phase 29 | Pending |
| STRUCT-04 | Phase 29 | Pending |
| STRUCT-05 | Phase 29 | Pending |
| STRUCT-06 | Phase 29 | Pending |
| SPARSER-01 | Phase 29 | Pending |
| SPARSER-02 | Phase 29 | Pending |
| ENTRY-01 | Phase 30 | Complete |
| ENTRY-02 | Phase 30 | Complete |
| ENTRY-03 | Phase 30 | Complete |
| ENTRY-04 | Phase 30 | Complete |
| ENTRY-05 | Phase 30 | Complete |
| TEST-01 | Phase 30 | Complete |
| TEST-02 | Phase 30 | Complete |
| TEST-03 | Phase 30 | Complete |
| TEST-04 | Phase 30 | Complete |
| TEST-05 | Phase 30 | Complete |
| TEST-06 | Phase 30 | Complete |
| TEST-07 | Phase 30 | Complete |
| DOMAIN-01 | Phase 31 | Complete |
| DOMAIN-02 | Phase 31 | Pending |
| DOMAIN-03 | Phase 31 | Complete |
| DOMAIN-04 | Phase 31 | Pending |
| DOMAIN-05 | Phase 31 | Pending |
| DERIVED-01 | Phase 31 | Complete |
| DERIVED-02 | Phase 31 | Complete |
| DERIVED-03 | Phase 31 | Pending |
| DERIVED-04 | Phase 31 | Pending |
| QUERY-01 | Phase 32 | Pending |
| QUERY-02 | Phase 32 | Pending |
| QUERY-03 | Phase 32 | Pending |
| QUERY-04 | Phase 32 | Pending |
| CLI-01 | Phase 33 | Pending |
| CLI-02 | Phase 33 | Pending |
| CLI-03 | Phase 33 | Pending |
| CLI-04 | Phase 33 | Pending |
| CLI-05 | Phase 33 | Pending |
| CLI-06 | Phase 33 | Pending |
| CLI-07 | Phase 33 | Pending |
| CLI-08 | Phase 33 | Pending |
| CLI-09 | Phase 33 | Pending |
| CLI-10 | Phase 33 | Pending |
| CLI-11 | Phase 33 | Pending |
| CLI-12 | Phase 33 | Pending |
| CLI-13 | Phase 33 | Pending |
| CLI-14 | Phase 33 | Pending |
| BRAND-01 | Phase 34 | Pending |
| BRAND-02 | Phase 34 | Pending |
| BRAND-03 | Phase 34 | Pending |
| BRAND-04 | Phase 34 | Pending |

**Coverage:**
- v1.6 requirements: 56 total
- Mapped to phases: 56 ✓
- Unmapped: 0 ✓

---
*Requirements defined: 2026-05-25*
*Traceability filled: 2026-05-25 (gsd-roadmapper)*
*Source-of-truth design: `.planning/research/ONTOLOGY-SPEC.md`*
*Research synthesis: `.planning/research/SUMMARY.md`*
