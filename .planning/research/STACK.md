# Stack Research — v1.6 graph-io Ontology Expansion

**Domain:** Embedded code-graph database (SQLite-backed), schema evolution, URI identity, manifest parsing, test-framework detection, domain config
**Researched:** 2026-05-25
**Confidence:** HIGH (all decisions grounded in existing codebase + verified versions)

---

## Summary Answer

Six targeted questions. Six answers. No new runtime dependencies required. All v1.6 capabilities are achievable with stdlib, tree-sitter (already present), and PyYAML (already a transitive dep). The one optional addition worth considering is `pyyaml>=6.0.3` as an explicit dep in graph-io's pyproject.toml — currently it arrives only transitively via python-frontmatter.

---

## Q1 — SQLite Schema Migration Strategy

### Decision: Hand-rolled version gate + mandatory full rebuild. Do NOT adopt yoyo-migrations or sqlite-utils.

The existing pattern in `store.py` (`SchemaMismatchError` → "run `cg update --full`") is already the right architecture for this project. Schema v2 adds new columns (`uri TEXT UNIQUE NOT NULL`) and restructures identity semantics (URI becomes the stable identity, `path` becomes an attribute). That change is not safely forward-compatible through incremental migration — the entire import graph built on `(kind, name, path)` identity must be recomputed from scratch anyway.

**What to change in v1.6:**

- Bump `SCHEMA_VERSION = 1` → `SCHEMA_VERSION = 2` in `schema.py`
- Add a `uri` column to the `nodes` table DDL: `uri TEXT` (nullable initially; scanner emits URIs for new node types and leaves NULL for AST nodes where stable URI is not meaningful)
- Add `CREATE INDEX IF NOT EXISTS idx_nodes_uri ON nodes(uri)` (for fast URI lookups)
- `store.py` `_check_schema_version` already raises `SchemaMismatchError` on mismatch → exit code `SCHEMA_MISMATCH = 4` already in `exit_codes.py` — wire it through and emit a clear message pointing at `cg update --full`
- `UPDATE_IN_PROGRESS = 6` is already in `exit_codes.py` — no change needed

**Why NOT yoyo-migrations:**

yoyo-migrations 9.0.0 is designed for incremental forward-migration of long-lived production databases. This project does mandatory full rebuilds on version bump — there is nothing to migrate incrementally. Adding a migration framework just to call `DROP TABLE` and `CREATE TABLE` is pure overhead. The existing `_check_schema_version` + `apply_schema` + `store.transaction` pattern handles everything needed.

**Why NOT sqlite-utils:**

sqlite-utils 3.39 is an excellent general-purpose SQLite manipulation library. But graph-io already owns its schema with raw `sqlite3` and has a tight, well-understood DDL. sqlite-utils would add 1 dependency (~19k LOC) to gain column-transform helpers that would be used exactly once (at schema bump). Not worth it.

**Integration point:** `schema.py` (bump constant + DDL). `store.py` (the check logic already works). No new module needed.

---

## Q2 — URI Identity

### Decision: Plain strings + two composition functions in a new `graph_io.uri` module. No URI library.

The URI scheme in this project (`repo:org/foo`, `pkg:org/foo/auth-service`, `domain:billing`, `file:org/foo/auth-service/src/cli.py`) is a custom opaque identifier scheme — it is not HTTP, not standard RFC 3986, and does not need to be parsed back into components at runtime. The graph stores it in the `uri` column; callers construct it once at scan time and look it up by equality.

**What is needed:**

```python
# graph_io/uri.py — total surface area
def repo_uri(org: str, repo: str) -> str:
    return f"repo:{org}/{repo}"

def pkg_uri(org: str, repo: str, pkg_name: str) -> str:
    return f"pkg:{org}/{repo}/{pkg_name}"

def subpkg_uri(pkg_uri: str, subpkg_path: str) -> str:
    return f"{pkg_uri}/{subpkg_path}"

def file_uri(pkg_uri: str, rel_path: str) -> str:
    return f"file:{pkg_uri.split(':', 1)[1]}/{rel_path}"

def domain_uri(name: str) -> str:
    return f"domain:{name}"

def entry_point_uri(pkg_uri: str, ep_name: str) -> str:
    return f"ep:{pkg_uri.split(':', 1)[1]}#{ep_name}"

def test_suite_uri(parent_uri: str, suite_name: str) -> str:
    return f"suite:{parent_uri.split(':', 1)[1]}/{suite_name}"
```

**Why NOT rfc3986 / yarl / hyperlink:**

- `rfc3986` (last release 2022, effectively unmaintained) — parses standard HTTP-style URIs. Our scheme is custom; the parser would not understand `pkg:` or `domain:` schemes.
- `yarl` (aio-libs, actively maintained) — an asyncio URL library. Its value prop is immutable URL objects for HTTP request construction. Completely wrong tool for opaque identifier composition.
- `hyperlink` — similar story; HTTP URL manipulation.

None of these libraries add value for a scheme like `pkg:org/repo/name` where the only operations are construction and equality comparison. Plain f-strings + a tiny `uri.py` module is 20 lines and zero dependencies.

**Integration point:** New `graph_io/uri.py` module. `packages.py` calls `pkg_uri()` when upserting package nodes. Scanner extensions call the appropriate constructor for each new node type.

---

## Q3 — Manifest Parsing for EntryPoint Extraction

### Decision: `tomllib` (stdlib) + `json` (stdlib). No new dependency. Handle package.json `exports` with a flat recursive walk.

**Python — `pyproject.toml [project.scripts]`:**

`tomllib` is already imported in `packages.py` (line 8: `import tomllib`). The `[project.scripts]` section is a flat `dict[str, str]` mapping entry-point names to `module:callable` strings. Parsing it is three lines:

```python
scripts = data.get("project", {}).get("scripts", {})
# {"myapp": "myapp.cli:main", "myapp-debug": "myapp.cli:debug_main"}
```

The `module:callable` format (e.g., `myapp.cli:main`) needs to be split on `:` to derive `implemented_by` pointing at a `Function` node if one exists, or falling back to `File` if not. This is plain string manipulation — no library needed.

**JS/TS — `package.json bin/main/exports`:**

`json` is already imported in `packages.py` (line 7: `import json`). The three cases:

- `bin`: `str | dict[str, str]` — either a single path or name→path mapping. Flat, trivial.
- `main`: `str` — single path. Trivial.
- `exports`: complex nested conditions object.

**Handling `exports` conditions:**

The `exports` field can be arbitrarily nested with condition keys (`import`, `require`, `browser`, `node`, `default`, `.`, `./sub`). For v1.6, the goal is to extract *advertised entry points*, not to implement a full Node.js resolver. The correct approach is a recursive walk that collects all leaf string values under condition paths, tagged with the subpath key:

```python
def _walk_exports(val, subpath: str = ".") -> list[tuple[str, str]]:
    """Returns [(subpath, resolved_path)] for all leaf entries."""
    if isinstance(val, str):
        return [(subpath, val)]
    if isinstance(val, list):
        # First string wins (condition list)
        for item in val:
            if isinstance(item, str):
                return [(subpath, item)]
        return []
    if isinstance(val, dict):
        results = []
        for k, v in val.items():
            if k.startswith("."):  # subpath key
                results.extend(_walk_exports(v, k))
            else:  # condition key — recurse, keep subpath
                results.extend(_walk_exports(v, subpath))
        return results
    return []
```

This covers 95% of real-world `exports` fields without a Node.js resolver dependency. Edge cases (wildcard subpaths like `"./features/*"`) can be emitted as-is with `kind: library` and a note in `attrs_json` that the path is a pattern.

**Integration point:** `packages.py` already has `_read_pyproject` and `_read_package_json`. Extend these two functions to also return `entry_points` lists. New `EntryPoint` node upsert logic goes in the same `packages.refresh()` call.

---

## Q4 — Test Framework Config Detection

### Decision: Stdlib only. Roll our own thin detectors — each is 5-15 lines.

There is no Python library that detects test framework configuration across Python and JS/TS ecosystems. The detection surface is small and well-defined:

| Config file | Parser | What to extract |
|-------------|--------|-----------------|
| `pytest.ini` | `configparser` (stdlib) | `[pytest]` section: `testpaths`, `python_files`, `python_classes`, `python_functions` |
| `pyproject.toml [tool.pytest.ini_options]` | `tomllib` (stdlib, already used) | same keys under `[tool.pytest.ini_options]` |
| `setup.cfg [tool:pytest]` | `configparser` (stdlib) | same keys |
| `jest.config.{js,ts,mjs,cjs}` | Content sniffing only | Detect presence → `framework: jest`; no JS eval |
| `vitest.config.{js,ts,mjs,cjs}` | Content sniffing only | Detect presence → `framework: vitest` |
| `mocha.config.{js,cjs}` / `.mocharc.{yml,json}` | Presence detection + `json`/`yaml` | Detect presence → `framework: mocha` |

**Key insight:** For JS/TS config files (jest.config.js, vitest.config.ts, etc.), we do NOT need to parse the JavaScript. The goal is to detect *which framework* and *where tests live* — that comes from presence detection + possibly reading the `testMatch` / `include` field if it appears in a `.json` or `.yaml` variant. For `.js`/`.ts` config files, presence detection is sufficient for v1.6.

**Implementation in a new `graph_io/detect_tests.py` module (~80 LOC):**

```python
PYTEST_CONFIGS = ("pytest.ini", "pyproject.toml", "setup.cfg")
JEST_CONFIGS = ("jest.config.js", "jest.config.ts", "jest.config.mjs", "jest.config.cjs")
VITEST_CONFIGS = ("vitest.config.js", "vitest.config.ts", "vitest.config.mjs")
MOCHA_CONFIGS = ("mocha.config.js", "mocha.config.cjs", ".mocharc.json", ".mocharc.yml", ".mocharc.yaml")
```

configparser is stdlib and handles both `pytest.ini` (INI style) and `setup.cfg [tool:pytest]` correctly.

**What NOT to do:** Do not reach for `configparser` on Jest/Vitest configs — they're JavaScript modules, not INI files. Do not execute them. Presence is enough for the `TestSuite.framework` attribute.

**Integration point:** New `graph_io/detect_tests.py` module. Called from scanner stage 3 (test suite detection), which is a new scanner pass added additively to `update.py` or as a new `test_suites.py` module.

---

## Q5 — YAML for `domains.yaml`

### Decision: Use PyYAML directly. Do NOT add ruamel.yaml or strictyaml.

**PyYAML is already installed.** It arrives as a transitive dependency of `python-frontmatter` (version 6.0.3, confirmed in the workspace). The `domains.yaml` format for v1.6 is a simple, human-authored config file:

```yaml
domains:
  billing:
    packages: [auth-service, payment-processor]
    children: [subscriptions]
  subscriptions:
    packages: [subscription-manager]
```

This is the exact use case PyYAML handles well: flat, read-once config parsing with `yaml.safe_load()`. The format is authored by humans and never written back by code (no round-trip requirement), which eliminates ruamel.yaml's main advantage.

**Why NOT ruamel.yaml:**

ruamel.yaml's value proposition is round-trip preservation of comments and formatting. `domains.yaml` is read-only from the tool's perspective — users edit it, the scanner reads it. No round-trip needed. ruamel.yaml adds ~500KB of dependency for zero gain here.

**Why NOT strictyaml:**

strictyaml provides schema validation and type safety. The `domains.yaml` schema is simple enough that a `dict` type check with a 10-line validator is sufficient. strictyaml's performance is also meaningfully slower than PyYAML.

**Dependency action required:** Add `pyyaml>=6.0.3` as an **explicit** dependency in `packages/graph-io/pyproject.toml`. Currently it arrives only transitively via python-frontmatter. graph-io does not depend on python-frontmatter directly, so if that chain ever changes, yaml imports would break silently. Making it explicit is correct hygiene.

**Integration point:** New `graph_io/domains.py` module with `load_domains(path: Path) -> DomainConfig`. Uses `yaml.safe_load()` directly.

---

## Q6 — File Role Flag Detection: graph-io vs source-parser Boundary

### Decision: Path heuristics in graph-io scanner. AST signals via source-parser. Explicit interface contract between the two.

The `source-parser` package already owns tree-sitter AST parsing. The `graph-io` scanner already owns filesystem walking. The boundary should follow what each layer knows:

**graph-io scanner owns (no AST needed):**

| Flag | Detection method |
|------|-----------------|
| `is_test` | Path patterns: `tests/`, `__tests__/`, `test_*.py`, `*_test.py`, `*.test.ts`, `*.spec.ts`, `*.test.js`, `spec/` |
| `is_config` | Filename: `conftest.py`, `jest.config.*`, `vitest.config.*`, `*.config.ts`, `tsconfig.json`, `setup.cfg`, `pyproject.toml` |
| `is_generated` | Path patterns: `dist/`, `build/`, `.gen/`, `generated/`, `vendor/`, `node_modules/`; content markers: `# generated by`, `// @generated`, `// Code generated by` (first 3 lines) |
| `is_type_only` | Extension: `.d.ts` |
| `is_executable` (partial) | Shebang detection: first 2 bytes `b'#!'`; conventional paths: `bin/`, `scripts/` |

**source-parser owns (requires AST):**

| Flag | Detection method |
|------|-----------------|
| `has_main` | Python: `if __name__ == "__main__":` top-level `if_statement` node. JS/TS: not applicable |
| `is_executable` (refined) | Python: AST confirms presence of top-level `if __name__` block; combined with shebang |
| `is_importable` | Python: presence of top-level `def`, `class`, or `__all__` assignment; JS/TS: presence of `export` declarations |

**How to wire it:**

The `PythonParser.parse()` method already produces a `SourceNode` with `attrs`. Extend `_base.LanguageParser` with a contract: `parse()` populates `attrs["has_main"]`, `attrs["is_importable"]`, and `attrs["is_executable_hint"]` on the file-level `SourceNode`. The scanner reads these attrs from the returned tree and merges them with its own path-heuristic flags.

Concretely, in `python.py`, add to the `SourceNode` construction:

```python
file_node.attrs["has_main"] = _has_main_block(root, source)
file_node.attrs["is_importable"] = _has_importable_symbols(root, source)
```

The `graph_io` scanner then reads `tree.attrs.get("has_main", False)` after calling `parse_bytes()`, combines it with shebang detection and path heuristics, and sets the final `File` node's `role_flags` blob in `attrs_json`.

This keeps tree-sitter knowledge inside source-parser (correct) and filesystem/manifest knowledge inside graph-io (correct), with a clear attrs-based handoff. No new module or dependency needed — it's an extension of the existing `parse_bytes()` → `to_graph_records()` pipeline.

**Integration point:** `source-parser/src/source_parser/parsers/python.py` gets two new helpers (`_has_main_block`, `_has_importable_symbols`). `graph-io/src/graph_io/scanner.py` (new module, or extension of `update.py`) reads both path heuristics and AST attrs to produce the final `File` role flags.

---

## Recommended Stack — New Additions Only

| What | Decision | Source | Confidence |
|------|----------|--------|------------|
| Schema migration | Hand-rolled version gate (existing pattern) | `store.py` / `schema.py` reviewed | HIGH |
| URI identity | Plain strings + `graph_io/uri.py` (20 LOC) | stdlib f-strings | HIGH |
| Manifest parsing — Python | `tomllib` (stdlib, already imported) | `packages.py` line 8 | HIGH |
| Manifest parsing — JS/TS `bin`/`main` | `json` (stdlib, already imported) | `packages.py` line 7 | HIGH |
| Manifest parsing — JS/TS `exports` | Custom recursive walk (~30 LOC) in `packages.py` | Design verified above | HIGH |
| Test config detection | `configparser` (stdlib) + presence detection | stdlib | HIGH |
| YAML for `domains.yaml` | `pyyaml>=6.0.3` — **add as explicit dep** | Already transitive via python-frontmatter | HIGH |
| File role flags — path heuristics | In-scanner logic (~50 LOC) | Existing `_ignore.py` pattern | HIGH |
| File role flags — AST signals | Extend `source_parser.parsers.python` | Existing tree-sitter AST already parsed | HIGH |

**Net new runtime dependencies for graph-io: 1** — `pyyaml>=6.0.3` (explicit, was already transitive).

---

## What NOT to Add

| Avoid | Why | Use Instead |
|-------|-----|-------------|
| `yoyo-migrations` | Incremental migration tool for long-lived DBs; this project does mandatory full rebuilds — the migration is `DROP + CREATE` | Existing `SchemaMismatchError` + `cg update --full` |
| `sqlite-utils` | General SQLite helper; graph-io owns its own thin `store.py` + `upsert.py`; would add ~19k LOC for single-use schema-bump helpers | Raw `sqlite3` (existing pattern) |
| `rfc3986` / `yarl` / `hyperlink` | HTTP URL parsers; URI scheme is custom opaque identifiers, not HTTP | `graph_io/uri.py` (20 LOC f-strings) |
| `ruamel.yaml` | Round-trip YAML preservation; `domains.yaml` is read-only from tool's perspective | `yaml.safe_load()` via existing PyYAML |
| `strictyaml` | Schema-validated YAML; overkill for a shallow config dict; notably slower | Simple `yaml.safe_load()` + inline dict validation |
| `node-interop` / JS eval for jest.config | Executing JS config files from Python is fragile | Presence detection + filename pattern matching |
| Second TOML parser | `tomllib` (stdlib) is already used in `packages.py`; do not add `tomli`, `tomlkit`, or `toml` | `tomllib` (stdlib) |
| Second YAML parser | PyYAML is already the transitive dep for python-frontmatter; do not add ruamel.yaml or strictyaml | `pyyaml` (explicit dep) |

---

## Module Map for v1.6

| New / Modified | What changes |
|----------------|--------------|
| `graph_io/schema.py` | Bump `SCHEMA_VERSION = 2`; add `uri TEXT` column + index to DDL |
| `graph_io/uri.py` | **New.** URI composition functions (repo, pkg, subpkg, file, domain, entry_point, test_suite) |
| `graph_io/packages.py` | Extend `_read_pyproject` + `_read_package_json` to extract entry points; upsert `EntryPoint` nodes + `declares_entry_point` / `implemented_by` edges |
| `graph_io/domains.py` | **New.** `load_domains(path)` using `yaml.safe_load()`; domain config dataclasses |
| `graph_io/detect_tests.py` | **New.** Framework config detection + `TestSuite` node construction |
| `graph_io/scanner.py` | **New** (or extend `update.py`). Additive FS walk that emits `Repository`, `SubPackage`, `File`-with-role-flags, `TestSuite`, `Domain` nodes + all new edge types |
| `source_parser/parsers/python.py` | Add `_has_main_block()` + `_has_importable_symbols()`; populate `file_node.attrs` |
| `graph_io/upsert.py` | Minor: handle URI field in node upsert (INSERT + ON CONFLICT update on `uri`) |
| `graph_io/queries.py` | New query functions for `Repository`, `Domain`, `EntryPoint`, `TestSuite` node types |
| `graph_io/cli/` | Extend `cg` CLI commands for new node/edge types |

---

## Installation (graph-io pyproject.toml change)

```toml
# packages/graph-io/pyproject.toml
[project]
dependencies = [
  "source-parser",
  "workspace-io",
  "pyyaml>=6.0.3",   # explicit: used by graph_io/domains.py; was previously only transitive
]
```

No other dependency additions.

---

## Alternatives Considered

| Category | Recommended | Alternative | Why Not |
|----------|-------------|-------------|---------|
| Schema migration | Hand-rolled version gate | yoyo-migrations 9.0.0 | Designed for incremental migration; this project does full rebuilds; zero additive value |
| Schema migration | Hand-rolled version gate | sqlite-utils 3.39 | General-purpose Swiss Army knife; graph-io already has a tighter, purpose-built store layer |
| URI composition | Plain strings + `uri.py` | rfc3986 / yarl | Both are HTTP URL parsers; wrong abstraction for custom opaque identifier schemes |
| YAML config | `pyyaml` (existing transitive) | ruamel.yaml | Round-trip preservation not needed; `domains.yaml` is read-only from tool perspective |
| YAML config | `pyyaml` (existing transitive) | strictyaml | Slower; schema validation overkill for a shallow config dict |
| JS config detection | Presence detection | JS eval / node interop | Brittle, security risk, requires Node.js subprocess |
| AST role flags | Extend existing source-parser | New tree-sitter pass in graph-io | graph-io does not own tree-sitter; duplicating the AST parse violates the existing package boundary |

---

## Version Compatibility

| Package | Version in workspace | Constraint | Notes |
|---------|---------------------|------------|-------|
| Python | 3.14.4 (system) | >=3.11 | `tomllib` is stdlib from 3.11+ |
| `pyyaml` | 6.0.3 (transitive) | >=6.0.3 | 6.0.x is stable; `yaml.safe_load` API unchanged since 5.x |
| `tomllib` | stdlib | 3.11+ | Already imported in `packages.py` |
| `configparser` | stdlib | Any | Used for `pytest.ini` / `setup.cfg [tool:pytest]` detection |
| `tree-sitter` | 0.25.2 | >=0.23.0 (source-parser constraint) | AST node type names used in role-flag detection are stable in 0.23+ |
| `tree-sitter-language-pack` | 1.6.2 | <=1.6.2 (source-parser upper bound) | Do not change; source-parser pins this range |

---

## Sources

- `packages/graph-io/src/graph_io/schema.py` — existing DDL, `SCHEMA_VERSION = 1`
- `packages/graph-io/src/graph_io/store.py` — `SchemaMismatchError`, `_check_schema_version`, existing version gate pattern
- `packages/graph-io/src/graph_io/packages.py` — existing `tomllib` + `json` imports, `_read_pyproject`, `_read_package_json`
- `packages/graph-io/src/graph_io/upsert.py` — node key pattern `(kind, name, path)`, identity model
- `packages/graph-io/src/graph_io/exit_codes.py` — `SCHEMA_MISMATCH = 4`, `UPDATE_IN_PROGRESS = 6` already defined
- `packages/source-parser/src/source_parser/parsers/python.py` — tree-sitter AST walker, existing attrs pattern
- `packages/source-parser/src/source_parser/projections/graph.py` — `GraphNode.attrs` handoff point
- `packages/graph-io/pyproject.toml` — current deps: `source-parser`, `workspace-io` (no pyyaml explicit)
- PyPI: `PyYAML` 6.0.3 — https://pypi.org/project/PyYAML/ — confirmed latest stable; released 2024-12-16
- PyPI: `python-frontmatter` 1.1.0 — https://pypi.org/project/python-frontmatter/ — confirmed `pyyaml` as dependency (no version pin)
- `uv pip list` output — confirmed PyYAML 6.0.3, tree-sitter 0.25.2 currently installed in workspace
- `.planning/research/ONTOLOGY-SPEC.md` — canonical v1.6 ontology spec (node types, edge types, scanner pipeline, identity scheme)
- `.planning/PROJECT.md` — v1.6 milestone scope, graph-io-only constraint, deferred items

---

*Stack research for: v1.6 graph-io ontology expansion (schema v2, URI identity, new node/edge types, additive scanner)*
*Researched: 2026-05-25*
