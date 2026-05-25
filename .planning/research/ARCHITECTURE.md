# Architecture Research — v1.6 graph-io Ontology Integration

**Domain:** Code-graph SQLite package — additive ontology expansion
**Researched:** 2026-05-25
**Confidence:** HIGH (grounded entirely in the existing codebase + ONTOLOGY-SPEC.md + STACK.md + FEATURES.md)

---

## System Overview

The existing graph-io architecture has a clean, stable shape. v1.6 plugs into it additively without restructuring the orchestration layer.

```
┌─────────────────────────────────────────────────────────────────────┐
│                          cg CLI  (cli/)                             │
│  ops_update  ops_status  ops_dump  q_describe_*  q_find  ...       │
│  NEW: q_describe_repo  q_list_domains  q_list_entry_points          │
│       q_describe_domain  q_describe_suite  q_what_tests             │
│       q_list_suites  q_list_scripts  q_domain_refs  q_domain_deps   │
│       q_cross_cutting  q_list_packages  q_domain_tree               │
├─────────────────────────────────────────────────────────────────────┤
│                     Orchestrator  (update.py)                       │
│  git diff → _process_files → packages.refresh                       │
│  NEW CALLS (additive, after packages.refresh):                      │
│    structural_nodes.emit  →  entry_points.emit                      │
│    test_suites.emit       →  domains.emit                           │
│    derived_edges.compute                                            │
│  → resolve.sweep → _set_metadata                                    │
├─────────────────────────────────────────────────────────────────────┤
│                  Emitter / Scanner modules                          │
│  packages.py (extended)   NEW: structural_nodes.py                  │
│  NEW: entry_points.py         test_suites.py    detect_tests.py     │
│  NEW: domains.py              derived_edges.py                      │
│  NEW: uri.py                                                        │
├─────────────────────────────────────────────────────────────────────┤
│                    Write layer  (upsert.py — extended)              │
│  upsert_records(conn, GraphRecords)  [URI field added to upsert]    │
├─────────────────────────────────────────────────────────────────────┤
│               Read layer  (queries.py — extended)                   │
│  find / callers / callees / imports / describe_package / ...        │
│  NEW: describe_repo / list_domains / describe_domain                │
│  NEW: list_entry_points / list_suites / describe_suite              │
│  NEW: what_tests / domain_refs / domain_deps / cross_cutting        │
├─────────────────────────────────────────────────────────────────────┤
│              Store + Schema  (store.py / schema.py)                 │
│  SCHEMA_VERSION 1 → 2                                               │
│  nodes: +uri TEXT column + idx_nodes_uri index                      │
│  edges / metadata: unchanged                                        │
│  store.connect / read_only_connect: unchanged                       │
│  SchemaMismatchError + SCHEMA_MISMATCH exit code: wire up           │
└─────────────────────────────────────────────────────────────────────┘
```

---

## Component Boundaries

### Existing modules and what changes

| Module | v1.5 Responsibility | v1.6 Change |
|--------|---------------------|-------------|
| `schema.py` | DDL + `SCHEMA_VERSION = 1` | Bump to 2; add `uri TEXT` column + `idx_nodes_uri` index |
| `store.py` | connect / read-only / transaction | Wire `SCHEMA_MISMATCH` exit code through `_check_schema_version`; no structural change |
| `upsert.py` | `upsert_records` — inserts nodes/edges by `(kind, name, path)` key | Add `uri` field to `_upsert_node` and `_insert_node`; ON CONFLICT update includes `uri` |
| `packages.py` | `refresh()` — discovers manifests, upserts package nodes + contains edges | Extend `_read_pyproject` / `_read_package_json` to return `entry_points`; the entry-point upsert moves to `entry_points.py` (packages.py hands off the data) |
| `resolve.py` | Post-upsert sweep: resolve placeholder-dst edges | Unchanged; placeholder nodes for new node types resolve via the same `(kind, name, path IS NULL)` join |
| `update.py` | Orchestrator: git diff → parse → upsert → resolve → metadata | Additive call sites only — see "Scanner additive integration" below |
| `queries.py` | find / callers / callees / imports / describe_package / describe_path / imported_by / exports / exported_by | New query functions appended to the same module (or a second `queries_v2.py` if the file gets large) |
| `sync_wiki.py` | Package → wiki_page documents edges | Unchanged; existing code is isolated and not affected by schema v2 |
| `_ignore.py` | Default + .cgignore skip set | Unchanged |
| `exit_codes.py` | `SCHEMA_MISMATCH = 4`, `UPDATE_IN_PROGRESS = 6` already declared | Wire `SCHEMA_MISMATCH` in store.py; wire `UPDATE_IN_PROGRESS` in update.py (replace existing GENERIC fallback for locked DB) |
| `cli/main.py` | Argparse dispatch + subcommand registry | Register new CLI modules; update description string (brand sweep) |

### New modules to create

| New Module | Responsibility | Depends On |
|------------|---------------|------------|
| `uri.py` | URI composition functions — `repo_uri`, `pkg_uri`, `subpkg_uri`, `file_uri`, `domain_uri`, `entry_point_uri`, `test_suite_uri` | stdlib only |
| `structural_nodes.py` | FS walk emitting `Repository`, `SubPackage`, `File`-with-role-flags + `physically_contains` edges | `uri.py`, `upsert.py`, `_ignore.py` |
| `entry_points.py` | Consumes entry-point data from `packages.py`, emits `EntryPoint` nodes + `declares_entry_point` / `implemented_by` edges | `uri.py`, `upsert.py`, `packages.py` (data only) |
| `test_suites.py` | Emits `TestSuite` nodes + `physically_contains TestSuite → File` + `tests` edges; re-parents test files from package containment | `uri.py`, `upsert.py`, `detect_tests.py`, `_ignore.py` |
| `detect_tests.py` | Framework config detection (pytest.ini, pyproject.toml [tool.pytest], jest.config.*, vitest.config.*); pure data, no DB access | stdlib (`configparser`, `tomllib`) |
| `domains.py` | `load_domains(path: Path)` using `yaml.safe_load()`; `DomainConfig` / `DomainEntry` dataclasses; emits `Domain` nodes + `belongs_to_domain` + `domain_contains_domain` edges | `uri.py`, `upsert.py`, PyYAML |
| `derived_edges.py` | Computes `references` (Domain → Package) and `depends_on` (Domain → Domain) from import graph + domain membership; re-runnable | `upsert.py`, raw `sqlite3` reads |

### New CLI modules to create (in `cli/`)

| New CLI Module | Command Surfaces |
|----------------|-----------------|
| `q_describe_repo.py` | `cg describe-repo` |
| `q_list_packages.py` | `cg list-packages` |
| `q_list_domains.py` | `cg list-domains` |
| `q_describe_domain.py` | `cg describe-domain <name>` |
| `q_domain_refs.py` | `cg domain-refs <name>` |
| `q_domain_deps.py` | `cg domain-deps <name>` |
| `q_domain_tree.py` | `cg domain-tree` |
| `q_cross_cutting.py` | `cg cross-cutting` |
| `q_list_entry_points.py` | `cg list-entry-points <package> [--kind executable\|library]` |
| `q_list_scripts.py` | `cg list-scripts` (UNION: EntryPoint kind:executable + File is_executable:true) |
| `q_list_suites.py` | `cg list-suites` |
| `q_describe_suite.py` | `cg describe-suite <name>` |
| `q_what_tests.py` | `cg what-tests <target>` (package, domain, or path variant) |

---

## Scanner Additive Integration

The critical constraint: `update.py`'s orchestration flow is NOT restructured. The nine-stage pipeline from spec §9 is v1.7. v1.6 adds new emit calls at two points in the existing flow.

### Existing `update.py` flow (unchanged skeleton)

```python
def run(repo_root, *, workspace, full, lock_timeout_ms):
    head = _head(repo_root)
    skip_dirs = _ignore.load_skip_dirs(repo_root)
    conn = store.connect(db_path, create=True, ...)
    with store.transaction(conn):
        _process_files(conn, repo_root, changed, skip_dirs)  # AST parse + upsert
        packages.refresh(conn, repo_root=repo_root)          # manifest → package nodes
        # ... stale-node cleanup ...
        resolve.sweep(conn)                                   # cross-file edge resolution
        _set_metadata(conn, "last_indexed_commit", head)
```

### v1.6 additive call sites in `update.py`

```python
with store.transaction(conn):
    _process_files(conn, repo_root, changed, skip_dirs)   # UNCHANGED

    packages.refresh(conn, repo_root=repo_root)           # UNCHANGED — also returns entry_point data
    entry_points.emit(conn, repo_root=repo_root)          # NEW — reads manifests, emits EntryPoint nodes

    structural_nodes.emit(conn, repo_root=repo_root,      # NEW — Repository + SubPackage + File role flags
                          skip_dirs=skip_dirs)            #       + physically_contains tree

    test_suites.emit(conn, repo_root=repo_root,           # NEW — TestSuite nodes + re-parenting
                     skip_dirs=skip_dirs)

    domains.emit(conn, repo_root=repo_root)               # NEW — Domain nodes + belongs_to_domain
                                                          #       (reads domains.yaml; no-op if absent)

    derived_edges.compute(conn)                           # NEW — references + depends_on edges
                                                          #       (re-runnable; clears + recomputes)

    # ... stale-node cleanup (existing, unchanged) ...
    resolve.sweep(conn)                                   # UNCHANGED
    _set_metadata(conn, "last_indexed_commit", head)      # UNCHANGED
```

**Why this position for each call:**

- `entry_points.emit` immediately after `packages.refresh`: manifests are re-read (same `_discover_manifests` walk) but this is idempotent; it extends the same manifest data to emit `EntryPoint` nodes. Placed here rather than inside `packages.refresh` to preserve `packages.py` as the single-responsibility manifest reader.

- `structural_nodes.emit` after `packages.refresh`: package paths must exist in the DB first so `physically_contains` edges from Repository → Package can reference real node IDs. The FS walk in `structural_nodes.py` is separate from the AST parse in `_process_files`.

- `test_suites.emit` after `structural_nodes.emit`: test suite re-parenting deletes `physically_contains Package → File` edges for test files and inserts `physically_contains TestSuite → File` edges instead. File nodes must exist (created by `_process_files`) and package containment edges must exist (created by `packages.refresh`) before re-parenting can happen.

- `domains.emit` after `structural_nodes.emit`: domain convention-based inference (strategy 2 from spec §9 — top-level folder names) needs the package list. Explicit config (`domains.yaml`) is path-based but needs package nodes to exist so `belongs_to_domain` edges can reference real IDs.

- `derived_edges.compute` last (before `resolve.sweep`): depends on `belongs_to_domain` edges (from `domains.emit`) and `imports` edges (from `_process_files` + `resolve.sweep`). Running derived edges before `resolve.sweep` means some `imports` edges are still unresolved — this is acceptable in v1.6 since `derived_edges.compute` already filters on `resolution != 'unresolved'` when building the import set. Alternatively, move `derived_edges.compute` after `resolve.sweep` — that's the safer order and is recommended.

**Revised safer order** (move derived edges after resolve):

```python
    _process_files(...)          # AST parse
    packages.refresh(...)        # package nodes
    entry_points.emit(...)       # EntryPoint nodes
    structural_nodes.emit(...)   # Repository + SubPackage + File role flags
    test_suites.emit(...)        # TestSuite nodes + re-parenting
    domains.emit(...)            # Domain nodes + belongs_to_domain
    # stale-node cleanup (existing)
    resolve.sweep(conn)          # cross-file edge resolution  ← UNCHANGED position
    derived_edges.compute(conn)  # references + depends_on  ← AFTER resolve, so imports are resolved
    _set_metadata(...)           # UNCHANGED
```

This order is clean, additive, and preserves the existing `resolve.sweep` position.

---

## URI Identity Migration

### Schema change

`schema.py` adds one column and one index to the `nodes` DDL:

```sql
CREATE TABLE IF NOT EXISTS nodes (
    id          INTEGER PRIMARY KEY,
    kind        TEXT NOT NULL,
    name        TEXT NOT NULL,
    path        TEXT,
    line        INTEGER,
    uri         TEXT,               -- NEW: stable URI identity; NULL for AST nodes
    attrs_json  TEXT
)

CREATE INDEX IF NOT EXISTS idx_nodes_uri ON nodes(uri)
```

`uri` is nullable. AST nodes (functions, classes, methods) do not receive URIs in v1.6 — stable URI identity is meaningful only at the structural/conceptual level (Repository, Package, SubPackage, File, EntryPoint, TestSuite, Domain). This avoids a full-graph URI backfill problem that would be expensive and provides no query benefit.

### URI generation point

URIs are generated at upsert time inside the emitter modules, not at scan-time in source-parser. The emitter constructs the URI before calling `upsert.upsert_records`, populating `GraphNode.attrs["uri"]`. The `_upsert_node` function in `upsert.py` reads `node.attrs.get("uri")` and writes it to the `uri` column.

Specifically:
- `structural_nodes.py` generates `file_uri(...)` for every File node, `repo_uri(...)` for the Repository node, `subpkg_uri(...)` for SubPackage nodes.
- `packages.py` generates `pkg_uri(...)` for Package nodes (the single change inside `packages.py`).
- `entry_points.py` generates `entry_point_uri(...)` for EntryPoint nodes.
- `test_suites.py` generates `test_suite_uri(...)` for TestSuite nodes.
- `domains.py` generates `domain_uri(...)` for Domain nodes.

The URI for a Package node requires knowing the `(org, repo)` prefix. In v1.6 (single-repo scope), the repo origin is derived from `git remote get-url origin` at `update.run()` time, parsed into `(org, repo)` components, and passed down through the emitter call chain. If the remote is missing (local-only repo), fall back to the directory name as `org=local, repo=<dirname>`.

### Uniqueness

`uri` is NOT declared `UNIQUE` in v1.6. The reason: `ON CONFLICT` for URI collisions requires careful thought about which record wins, and adding a UNIQUE constraint after a full rebuild forces all existing data to be collision-free before the constraint can be applied. In v1.6, uniqueness is enforced at the emitter level (each emitter generates URIs deterministically from stable inputs; no two nodes of the same type should get the same URI). Add `UNIQUE NOT NULL` in v1.7 once the URI generation is validated against real repos.

### Existing edges get URIs for their endpoints

Existing AST edges (`calls`, `imports`, `contains`) reference nodes by `INTEGER id`. Those nodes do not get URIs in v1.6 for AST-level nodes (functions, classes). This is correct and expected — the `uri` column is a supplemental stable identity for the structural/conceptual layer; the INTEGER primary key remains the join key for all edge lookups. No migration of existing edges is required.

---

## source-parser Boundary

### What source-parser populates on its SourceNode

The parser boundary follows what each layer knows. source-parser knows the AST; graph-io knows the filesystem and manifests.

**source-parser adds to file-level `SourceNode.attrs`:**

| Attr key | Detection method | Location |
|----------|-----------------|----------|
| `has_main` | Python: `if __name__ == "__main__":` top-level `if_statement` node | `source_parser/parsers/python.py` |
| `is_importable` | Python: presence of top-level `def`, `class`, or `__all__`; JS/TS: presence of `export` declarations | `python.py` and the JS/TS parser |
| `is_executable_hint` | Python: AST confirms `if __name__` block is present (same as `has_main`); combined with shebang in graph-io | `python.py` |

These attrs flow through `to_graph_records()` into `GraphNode.attrs` unchanged. The scanner in graph-io reads them from `tree.attrs` after the `parse_bytes()` call and merges them with path heuristics.

**graph-io scanner owns (no AST needed):**

| Flag | Detection | Source |
|------|-----------|--------|
| `is_test` | Path patterns: `tests/`, `__tests__/`, `test_*.py`, `*_test.py`, `*.test.ts`, `*.spec.ts` | `structural_nodes.py` |
| `is_config` | Filename: `conftest.py`, `jest.config.*`, `vitest.config.*`, `tsconfig.json`, `setup.cfg` | `structural_nodes.py` |
| `is_generated` | Path patterns: `dist/`, `build/`, `.gen/`, `generated/`; content markers in first 3 lines (`# generated by`, `// @generated`) | `structural_nodes.py` |
| `is_type_only` | Extension: `.d.ts` | `structural_nodes.py` |
| `is_executable` | Shebang (`first 2 bytes == b'#!'`); conventional paths `bin/`, `scripts/`; merged with `is_executable_hint` from AST | `structural_nodes.py` |

**Handoff pattern:**

```python
# in update.py _process_files (existing), attrs now include AST signals:
tree = parse_bytes(source, path=Path(rel), package=None)
records = to_graph_records(tree)
# tree.attrs["has_main"], tree.attrs["is_importable"] now available
# structural_nodes.py reads tree.attrs to merge with path heuristics

# in structural_nodes.emit, per-file role flag computation:
def _file_role_flags(rel: str, tree_attrs: dict) -> dict[str, bool]:
    return {
        "is_test": _path_is_test(rel),
        "is_config": _path_is_config(rel),
        "is_generated": _path_is_generated(rel),
        "is_type_only": rel.endswith(".d.ts"),
        "is_executable": _has_shebang(rel) or _in_bin_dir(rel) or tree_attrs.get("is_executable_hint", False),
        "is_importable": tree_attrs.get("is_importable", False),
        "has_main": tree_attrs.get("has_main", False),
    }
```

The challenge: `structural_nodes.emit` currently does a separate FS walk. To get AST attrs without double-parsing, `_process_files` should cache the `tree.attrs` per file path in a local dict, which `structural_nodes.emit` consumes. Alternatively (simpler for v1.6): `structural_nodes.emit` computes path-heuristic flags only (which covers 5 of 7 flags), and a post-pass in `_process_files` updates `has_main` and `is_importable` from the already-parsed tree. The simpler approach avoids cross-module state passing and is the right call for v1.6.

**Recommended v1.6 implementation:** `structural_nodes.emit` sets path-heuristic flags only. A second small function in `update.py` — `_apply_ast_role_flags(conn, repo_root, changed, skip_dirs)` — runs after `_process_files` and updates `attrs_json` on file nodes that have `has_main` or `is_importable` from the AST. This is a targeted UPDATE, not a full re-parse, and keeps the modules clean.

---

## `domains.yaml` Reader

### Location

`graph_io/domains.py` is the right home, not `workspace-io`. The domains.yaml config is code-graph-specific — it declares how packages in a repository map to logical domains. It is not a workspace manifest (which is `.graph-wiki.yaml` in workspace-io). `workspace-io` owns workspace bootstrapping; `graph-io` owns graph-specific config.

### When read

`domains.emit(conn, repo_root=repo_root)` reads `domains.yaml` from `repo_root / "domains.yaml"` each time `cg update` runs. No caching is needed — the file is read once per update invocation, and updates are not frequent enough to make reading a 1KB YAML file a bottleneck.

### Error handling

| Condition | Behavior |
|-----------|---------|
| `domains.yaml` absent | No-op. Convention-based inference (top-level named folders) runs. No error. |
| `domains.yaml` present but malformed YAML | `yaml.YAMLError` caught; warning printed to stderr with file path; convention-based inference runs as fallback. No exception raised to the caller. |
| `domains.yaml` references a package name not in the DB | Warning printed to stderr per unknown name; `belongs_to_domain` edge for that name is silently skipped (package may not be indexed yet if only changed files were processed). |
| `domains.yaml` references a non-existent sub-domain | Same treatment: warning + skip. |

### DomainConfig schema (in `domains.py`)

```python
@dataclass
class DomainEntry:
    name: str
    description: str = ""
    packages: list[str] = field(default_factory=list)
    parent: str | None = None          # parent domain name for domain_contains_domain
    subdomains: list[str] = field(default_factory=list)  # alternative to parent field

@dataclass
class DomainConfig:
    domains: dict[str, DomainEntry]    # keyed by domain name

def load_domains(path: Path) -> DomainConfig | None:
    """Returns None if path does not exist. Raises ValueError on schema error."""
```

---

## Build Order (Phase Dependency Chain)

The phases must respect the dependency chain below. Each item is the smallest atomic unit that can be built and tested independently.

```
Phase A: Foundation (blocking — everything else depends on this)
  ├── schema.py: SCHEMA_VERSION 1 → 2, add uri column + index
  ├── store.py: wire SCHEMA_MISMATCH + UPDATE_IN_PROGRESS exit codes
  ├── upsert.py: add uri field to _upsert_node / _insert_node
  └── uri.py: new — all URI composition functions
      Tests: test_schema.py (extend), test_store.py (extend), test_upsert.py (extend), test_uri.py (new)

Phase B: Structural Nodes (depends on A)
  ├── structural_nodes.py: new — Repository + SubPackage + File-with-role-flags + physically_contains
  ├── source_parser/parsers/python.py: add has_main + is_importable attrs
  └── update.py: add structural_nodes.emit call + _apply_ast_role_flags helper
      Tests: test_structural_nodes.py (new), test_source_parser_role_flags.py (new)

Phase C: EntryPoint + TestSuite (depends on A + B)
  ├── detect_tests.py: new — framework config detection
  ├── entry_points.py: new — EntryPoint nodes + declares_entry_point / implemented_by edges
  ├── test_suites.py: new — TestSuite nodes + re-parenting
  ├── packages.py: extend _read_pyproject + _read_package_json to return entry_points
  └── update.py: add entry_points.emit + test_suites.emit calls
      Tests: test_detect_tests.py (new), test_entry_points.py (new), test_suites.py (new)

Phase D: Domain Layer (depends on A + B + C for full derived-edge accuracy)
  ├── domains.py: new — load_domains + Domain node emit + belongs_to_domain + domain_contains_domain
  ├── derived_edges.py: new — references + depends_on computation
  └── update.py: add domains.emit + derived_edges.compute calls
      Tests: test_domains.py (new), test_derived_edges.py (new)

Phase E: Query Layer Extension (depends on A + B + C + D)
  ├── queries.py: add describe_repo / list_domains / describe_domain / list_entry_points
  │              list_suites / describe_suite / what_tests / domain_refs / domain_deps
  │              cross_cutting / list_packages
  └── Extend existing: describe_package (+ domains, entry points, suites) / describe_path (+ role flags)
      Tests: test_queries.py (extend with new query functions)

Phase F: CLI Extension (depends on E)
  ├── New CLI modules: q_describe_repo, q_list_packages, q_list_domains, q_describe_domain,
  │   q_domain_refs, q_domain_deps, q_domain_tree, q_cross_cutting, q_list_entry_points,
  │   q_list_scripts, q_list_suites, q_describe_suite, q_what_tests
  └── cli/main.py: register new subcommands; update description string
      Tests: test_cli_smoke.py (extend), new per-command smoke tests

Phase G: Brand Sweep (independent — can run in parallel with any phase, no code deps)
  ├── README.md: "lattice-graph-core" → "graph-wiki code graph", path refs updated
  └── cli/main.py description string: "lattice code graph CLI" → "graph-wiki code graph CLI"
      Tests: brand grep gate (existing check-brand.sh)
```

**Key dependency facts:**
- Phase A is a hard prerequisite for all other phases. No new node can be safely upserted without URI support in the schema.
- Phase B must precede Phase C because TestSuite re-parenting requires `physically_contains` edges from packages to files (created by structural_nodes.emit) to exist before they can be rewritten.
- Phase D can start after Phase A + B (Domain nodes themselves don't depend on EntryPoint or TestSuite). However, `derived_edges.compute` produces more complete results if it runs after Phase C, because test-suite imports inform which packages a suite targets, and that in turn informs domain-level `tests` edges. For v1.6, running D after C is the safe order.
- Phase E requires all emitters to have run at least once so the query layer can be validated against real data.
- Phase F requires Phase E for query functions to exist.
- Phase G has zero code dependencies — it can be done in a 10-minute PR anytime.

---

## Test Architecture

### Existing test modules to extend

| Existing Test Module | What to Add |
|----------------------|-------------|
| `test_schema.py` | Assert `SCHEMA_VERSION == 2`; assert `uri` column present; assert `idx_nodes_uri` index present |
| `test_store.py` | Test that `SchemaMismatchError` now raises exit code `SCHEMA_MISMATCH = 4` (wire-through test); test that `UPDATE_IN_PROGRESS = 6` replaces old GENERIC path |
| `test_upsert.py` | Test that nodes upserted with a `uri` in attrs have `uri` column populated; test round-trip |
| `test_packages.py` | Extend `test_refresh_pyproject` to verify entry-point data returned from `_read_pyproject`; `test_refresh_package_json` similarly for `bin`/`main`/`exports` |
| `test_queries.py` | Extend with new query function tests: `describe_repo`, `list_domains`, `describe_domain`, `list_entry_points`, `list_suites`, `describe_suite`, `what_tests`, `domain_refs`, `domain_deps`, `cross_cutting` |
| `test_cli_smoke.py` | Add smoke invocations for each new CLI subcommand (exit 0 against a seeded DB) |
| `test_e2e.py` | Add an e2e scenario with `domains.yaml` present; verify domain nodes + derived edges appear |

### New test modules to create

| New Test Module | What it tests | Key Fixtures |
|-----------------|---------------|--------------|
| `test_uri.py` | All `uri.py` composition functions; round-trip stability; determinism | Pure unit tests, no DB fixture needed |
| `test_structural_nodes.py` | `structural_nodes.emit` against a multi-package mini-repo; verify Repository node, SubPackage nodes, File role flags, physically_contains tree structure | `tmp_path` + `conn` fixture; git repo not required (no git diff involved) |
| `test_detect_tests.py` | `detect_tests.py` framework detection; pytest.ini, pyproject.toml [tool.pytest], jest.config.js presence, vitest detection | Pure filesystem fixtures in `tmp_path`; no DB needed |
| `test_entry_points.py` | `entry_points.emit` against repos with `pyproject.toml [project.scripts]` and `package.json bin/main/exports`; verify EntryPoint nodes + declares_entry_point + implemented_by edges | `tmp_path` + `conn` + seed package nodes |
| `test_suites.py` | `test_suites.emit` against each layout pattern from spec §7 (single-package with root tests, monorepo with mirrored layout, package-local tests, mixed); verify TestSuite nodes, re-parented containment, `tests` edges | `tmp_path` + `conn` + seeded file nodes + seed package nodes |
| `test_domains.py` | `domains.py` `load_domains` with valid/invalid/absent YAML; `domains.emit` with explicit config + convention-based inference; verify Domain nodes + belongs_to_domain + domain_contains_domain edges | `tmp_path` + `conn` + seeded package nodes |
| `test_derived_edges.py` | `derived_edges.compute` against a DB with known imports + domain membership; verify `references` edges with correct usage_count; verify `depends_on` edges | `tmp_path` + `conn` with seeded full graph including imports + domain edges |
| `test_source_parser_role_flags.py` | `has_main` and `is_importable` populated in `SourceNode.attrs` by the Python parser; verify via `parse_bytes` + `to_graph_records` | Small Python source fixtures as bytes |

### Mini-repo fixture pattern for new tests

The existing `_git_repo.py` + `write_and_commit` pattern works for update-flow tests. For tests that don't need git history (pure emitter tests), a simpler pattern is sufficient:

```python
# conftest.py addition (or per-test fixture)
@pytest.fixture
def multi_pkg_repo(tmp_path: Path) -> Path:
    """A two-package Python monorepo with tests at root + package-local tests."""
    (tmp_path / "packages" / "auth" / "src" / "auth").mkdir(parents=True)
    (tmp_path / "packages" / "billing" / "src" / "billing").mkdir(parents=True)
    (tmp_path / "packages" / "auth" / "pyproject.toml").write_text(
        '[project]\nname = "auth"\nversion = "0.1.0"\n[project.scripts]\nauth-cli = "auth.cli:main"\n'
    )
    (tmp_path / "packages" / "billing" / "pyproject.toml").write_text(
        '[project]\nname = "billing"\nversion = "0.1.0"\n'
    )
    (tmp_path / "tests" / "integration").mkdir(parents=True)
    (tmp_path / "tests" / "integration" / "test_flow.py").write_text("import auth\nimport billing\n")
    (tmp_path / "packages" / "auth" / "tests").mkdir()
    (tmp_path / "packages" / "auth" / "tests" / "test_auth.py").write_text("import auth\n")
    (tmp_path / "domains.yaml").write_text(
        "domains:\n  payments:\n    packages: [billing]\n  identity:\n    packages: [auth]\n"
    )
    return tmp_path
```

This fixture covers layout patterns 2 (mirrored), 4 (package-local), and gives a `domains.yaml` for domain tests — all in one reusable fixture.

---

## Brand Sweep Scope

The brand sweep is strictly contained to `packages/graph-io/`. The boundary is defined by what has `lattice` references that are not in the allow-list:

### In scope (change these)

| Location | Current text | Target text |
|----------|-------------|-------------|
| `packages/graph-io/README.md` line 1 | `# lattice-graph-core` | `# graph-io` (or `# graph-wiki code graph`) |
| `packages/graph-io/README.md` line 4 | `~/.lattice/graph/code.db` | canonical graph-wiki path per `workspace_io.paths.graph_dir()` |
| `packages/graph-io/src/graph_io/cli/main.py` line 46 | `description="lattice code graph CLI"` | `description="graph-wiki code graph CLI"` |
| `packages/graph-io/src/graph_io/update.py` line 132 | `os.environ.get("LATTICE_GRAPH_LOCK_TIMEOUT_MS")` | `os.environ.get("GRAPH_WIKI_LOCK_TIMEOUT_MS")` — or add an alias that reads both |
| `packages/graph-io/src/graph_io/packages.py` line 16 | `_SKIP_REPO_PREFIXES = ("lattice/",)` | `_SKIP_REPO_PREFIXES = ("lattice/",)` — **leave this** (it is a path skip rule for repos named `lattice/`; this is a functional behavior, not brand text; changing it would alter which directories get skipped) |

### Out of scope (do NOT change these)

| Location | Reason to leave alone |
|----------|----------------------|
| `plugins/graph-wiki/` | Plugin milestone boundary; plugin code does not reference graph-io brand text |
| `packages/wiki-io/` | Separate package; no lattice-graph-core references in wiki-io |
| `packages/source-parser/` | Projection module header says "aligned to lattice-graph's SQLite schema" — this is a comment, not a brand name; leave for v1.7 when source-parser gets a separate milestone |
| `packages/graph-io/src/graph_io/packages.py` `_SKIP_REPO_PREFIXES` | Functional behavior: skips manifests under a `lattice/` directory path prefix. Changing this would break real skip behavior for repos that have a `lattice/` subdirectory. Rename only if there is a concrete reason. |
| `.brand-grep-allow` entries for historical references | Already in the allow-list; no change needed |

The `LATTICE_GRAPH_LOCK_TIMEOUT_MS` env var name (in `update.py`) is the one debatable case. Changing it is a breaking change for anyone using that env var. Safe approach: read both `GRAPH_WIKI_LOCK_TIMEOUT_MS` (new) and `LATTICE_GRAPH_LOCK_TIMEOUT_MS` (old fallback) with a deprecation warning on the old name. Add the old name to `.brand-grep-allow`.

---

## Anti-Patterns

### Anti-Pattern 1: Restructuring update.py into pipeline stages

**What it looks like:** Splitting `update.py` into Stage1, Stage2, ..., Stage8 classes or modules with explicit inter-stage handoffs to match spec §9.

**Why wrong for v1.6:** This is the v1.7 work explicitly deferred in PROJECT.md. The additive call pattern (`emit_1(); emit_2(); emit_3()`) within the existing `store.transaction` block achieves the same functional result without the refactor cost. The domain-overlay re-run optimization (running only stages 7-8 without re-parsing AST) is the motivating reason to restructure, and that use case is not in v1.6 scope.

**Correct approach:** Add flat function calls in `update.py`'s `run()` function, each delegating to a focused module. Keep the existing transaction boundary.

### Anti-Pattern 2: Putting URI generation in source-parser

**What it looks like:** Having `to_graph_records()` in `source_parser/projections/graph.py` generate URI values for GraphNode objects.

**Why wrong:** source-parser doesn't know the repository org/name, package hierarchy, or workspace layout. Those are graph-io's context. The `uri.py` module must live in graph-io where `(org, repo, pkg)` context is available.

**Correct approach:** Emitter modules in graph-io call `uri.py` functions with full context before calling `upsert.upsert_records`. The `GraphNode.attrs` dict carries the URI down to the upsert layer.

### Anti-Pattern 3: Putting DomainConfig in workspace-io

**What it looks like:** Moving `domains.yaml` loading into `workspace_io.config` or a new `workspace_io.domains` module.

**Why wrong:** `domains.yaml` is a code-graph artifact, not a workspace manifest. workspace-io owns `.graph-wiki.yaml` (workspace bootstrapping, plugin version tracking). graph-io owns domain assignment config. Mixing these creates an unwanted dependency: workspace-io would need to know about graph-io's domain ontology.

**Correct approach:** `graph_io/domains.py` owns `load_domains(path)`. The path is derived from `repo_root / "domains.yaml"`, passed down from `update.py`.

### Anti-Pattern 4: Adding UNIQUE NOT NULL to `uri` in v1.6

**What it looks like:** Declaring `uri TEXT UNIQUE NOT NULL` in the nodes DDL, requiring all existing nodes to have URIs.

**Why wrong:** AST nodes (functions, classes) don't have stable URIs in v1.6 — requiring NOT NULL would either force URI generation for every AST node (expensive, semantically questionable) or break existing `_process_files` upserts that don't populate `uri`.

**Correct approach:** `uri TEXT` (nullable) in v1.6. UNIQUE constraint added in v1.7 after URI coverage is complete and validated.

### Anti-Pattern 5: Calling `_discover_manifests` a third time for entry points

**What it looks like:** `entry_points.py` does its own full `repo_root.rglob("pyproject.toml")` scan independent of `packages.py`.

**Why wrong:** `packages.refresh` already scans manifests. A second full scan doubles I/O for no benefit.

**Correct approach:** Either (a) `packages.refresh` returns the manifest data it already parsed and `entry_points.emit` consumes that data, or (b) both `packages.py` and `entry_points.py` call a shared `_discover_manifests` function that is already cached as a module-level concern. Option (a) is cleaner — `packages.refresh` returns `list[tuple[Path, dict]]` and `entry_points.emit(conn, manifest_data)` receives it. The caller in `update.py` is then:

```python
manifest_data = packages.refresh(conn, repo_root=repo_root)
entry_points.emit(conn, manifest_data=manifest_data)
```

---

## Data Flow

### `cg update --full` flow with all v1.6 additions

```
cg update --full
    │
    ▼
update.run(repo_root)
    │
    ├── _head(repo_root)                         → head commit SHA
    ├── _ignore.load_skip_dirs(repo_root)        → skip_dirs frozenset
    ├── store.connect(db_path, create=True)      → conn  [schema v2 applied on create]
    │
    └── store.transaction(conn):
            │
            ├── _process_files(conn, ...)        → AST nodes + calls/imports/contains edges
            │
            ├── manifest_data = packages.refresh(conn, repo_root)
            │                                    → Package nodes + old contains edges
            │
            ├── entry_points.emit(conn, manifest_data)
            │                                    → EntryPoint nodes + declares_entry_point
            │                                       + implemented_by edges
            │
            ├── structural_nodes.emit(conn, repo_root, skip_dirs)
            │                                    → Repository node + SubPackage nodes
            │                                       + File nodes with role flags
            │                                       + physically_contains tree edges
            │
            ├── test_suites.emit(conn, repo_root, skip_dirs)
            │                                    → TestSuite nodes
            │                                       + re-parented physically_contains edges
            │                                       + tests edges (suite → package/domain/repo)
            │
            ├── domains.emit(conn, repo_root)
            │     ├── load_domains(repo_root / "domains.yaml")  → DomainConfig | None
            │     └──                                           → Domain nodes
            │                                                      + belongs_to_domain edges
            │                                                      + domain_contains_domain edges
            │
            ├── [stale-node cleanup — existing, unchanged]
            │
            ├── resolve.sweep(conn)              → placeholder edges resolved
            │
            ├── derived_edges.compute(conn)
            │     ├── clear existing references + depends_on edges
            │     ├── walk imports edges filtered by domain membership
            │     └──                           → references edges (Domain → Package)
            │                                      + depends_on edges (Domain → Domain)
            │
            └── _set_metadata(conn, "last_indexed_commit", head)
```

### Query flow (read-only)

```
cg describe-domain billing
    │
    ▼
cli/q_describe_domain.run(args)
    │
    ├── store.read_only_connect(db_path)          → conn (schema v2 check)
    │
    ├── queries.describe_domain(conn, name="billing")
    │     ├── SELECT uri, attrs_json FROM nodes WHERE kind='domain' AND name='billing'
    │     ├── SELECT pkg.name FROM edges + nodes WHERE kind='belongs_to_domain' AND dst=billing.id
    │     ├── SELECT sub.name FROM edges + nodes WHERE kind='domain_contains_domain' AND src=billing.id
    │     ├── SELECT ref.* FROM edges WHERE kind='references' AND src=billing.id
    │     └── SELECT dep.* FROM edges WHERE kind='depends_on' AND src=billing.id
    │
    └── _format.render(result) → stdout
```

---

## Sources

- `packages/graph-io/src/graph_io/schema.py` — existing DDL, current column set
- `packages/graph-io/src/graph_io/update.py` — existing orchestration flow, transaction boundary, call sites
- `packages/graph-io/src/graph_io/upsert.py` — `(kind, name, path)` identity model, `_upsert_node` signature
- `packages/graph-io/src/graph_io/packages.py` — `_discover_manifests`, `refresh`, manifest scan pattern
- `packages/graph-io/src/graph_io/resolve.py` — sweep logic, placeholder-node cleanup
- `packages/graph-io/src/graph_io/queries.py` — existing query functions, `NodeRecord` dataclass pattern
- `packages/graph-io/src/graph_io/store.py` — `SchemaMismatchError`, `_check_schema_version`, `read_only_connect`
- `packages/graph-io/src/graph_io/cli/main.py` — subcommand registry, `lattice` brand text locations
- `packages/graph-io/src/graph_io/exit_codes.py` — `SCHEMA_MISMATCH = 4`, `UPDATE_IN_PROGRESS = 6`
- `packages/graph-io/src/graph_io/sync_wiki.py` — isolation from v1.6 changes confirmed
- `packages/graph-io/src/graph_io/_ignore.py` — `DEFAULT_SKIP_DIRS`, `should_skip` API consumed by new scanners
- `packages/source-parser/src/source_parser/projections/graph.py` — `GraphNode.attrs` handoff point
- `packages/workspace-io/src/workspace_io/paths.py` — `graph_dir()` — canonical DB location
- `.planning/research/ONTOLOGY-SPEC.md` — node types, edge types, scanner pipeline, identity scheme
- `.planning/research/STACK.md` — library decisions, URI module design, test framework detection approach
- `.planning/research/FEATURES.md` — CLI surface decisions, anti-features, §10 query coverage
- `.planning/PROJECT.md` — v1.6 scope, v1.7 deferral list, pipeline restructure explicitly deferred

---
*Architecture research for: graph-io v1.6 ontology expansion (schema v2, URI identity, new node/edge types, additive scanner integration)*
*Researched: 2026-05-25*
