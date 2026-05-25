# Code Graph + Wiki Ontology — Initial Spec

**Status:** Draft for review
**Scope:** Python and JS/TS projects (monorepo and single-repo)
**Goal:** Replace the current package/app/domain extraction approach with a more flexible ontology that cleanly separates physical layout from logical/conceptual grouping, supports cross-cutting concerns, and scales to multiple repositories.

---

## 1. Motivation and Problems with the Current Approach

The current implementation extracts packages, apps, and feature domains (collections of packages) and stores each under a dedicated wiki directory. Cross-references are supported, but several decisions have created friction:

- Packages that belong to a domain are stored *under* the domain's wiki folder, conflating "where wiki content lives" with "what the package belongs to."
- A package can only belong to one domain in the current model, which doesn't fit shared/utility packages.
- The scanner is constrained by directory conventions, which limits how flexibly it can be applied to repos with different layouts.
- There is no clean way to represent cross-cutting dependencies (e.g., a logger used by many domains).

The new design addresses these by separating physical containment from logical/curated grouping, and by deriving cross-cutting relationships from the import graph rather than authoring them by hand.

---

## 2. Core Design Principles

1. **Separate physical containment (tree) from domain membership (DAG).** Physical layout is mechanical and derived from disk. Domain membership is interpretive and may be many-to-many.
2. **Domains are first-class nodes**, not tags. They can own documentation, owners, ADRs, and have edges to other domains.
3. **Repositories are first-class nodes** to support cross-repo queries and per-repo metadata.
4. **Identity by URI, not path.** Wiki content is keyed by stable entity ID; on-disk wiki layout is incidental and produced by the renderer.
5. **Additive, not replacing.** Layer new structural and domain nodes on top of the existing AST graph. Existing function/class/method nodes and edges stay as-is.
6. **Derive what can be derived.** Curated edges are kept minimal; transitive and import-derived relationships are computed, not stored, to prevent drift.
7. **The scan is a pipeline.** Physical extraction, AST parsing, import resolution, domain assignment, and wiki rendering are separate stages.

---

## 3. Node Types

### Structural (physical) nodes

| Node | Description |
|------|-------------|
| `Repository` | A source repository. Carries repo-level metadata (URL, default branch, owner, etc.). |
| `Package` | A unit of distribution with a manifest (`package.json`, `pyproject.toml`, `setup.py`, etc.). Versioned, has a public API. |
| `SubPackage` | **Python-only.** A nested importable grouping inside a package (a directory with `__init__.py` below the package root). JS/TS scans do not produce `SubPackage` nodes — directory paths live as attributes on `File`. |
| `File` | A single source file. In both Python and JS/TS, a file *is* a module in the language's own terminology, so `File` is the universal module-level node. |

#### `File` attributes (role flags)

Rather than splitting `File` into separate `Module`/`Script` node types, role is represented as attributes on the `File` node. This honestly handles hybrid cases (e.g., a Python file with both library exports and a `__main__` block) and avoids fuzzy classification rules dictating the type system.

| Attribute | Meaning | Detection signals |
|---|---|---|
| `is_importable` | File exposes importable symbols. | Has exports / public symbols; absence of script-only patterns. |
| `is_executable` | File is intended to be run directly. | Shebang line, `if __name__ == "__main__":` block, declared in a manifest entry point, conventional placement (`bin/`, `scripts/`). |
| `has_main` | File has a `__main__` / top-level entry block. | Python `if __name__ == "__main__":`; JS files invoked as `node entry.js`. |
| `is_test` | Test file. | Path patterns (`tests/`, `__tests__/`, `*.test.ts`, `test_*.py`), framework imports. |
| `is_config` | Configuration file (Python `conftest.py`, JS config files, etc.). | Filename and content heuristics. |
| `is_generated` | Generated/vendored code. | Common markers, manifest declarations, conventional paths. |
| `is_type_only` | Type definitions only (e.g., `.d.ts`). | Extension and content. |

Flags are not mutually exclusive. A file can be `is_importable: true` and `is_executable: true` simultaneously — that's a real and common case, not a contradiction to resolve.

### Code-level nodes (existing — unchanged)

`Function`, `Class`, `Method`, etc. — retained from the current AST graph.

### Conceptual/curated nodes

| Node | Description |
|------|-------------|
| `Domain` | A logical grouping of packages representing a feature area, bounded context, or architectural concern (e.g., Billing, Auth, Location). |
| `EntryPoint` | A named, declared entry point from a package manifest. Covers both executable entry points (`pyproject.toml [project.scripts]`, `package.json "bin"`) and library entry points (`package.json "main"`/`"module"`/`"exports"`). An `EntryPoint` has a name distinct from its implementing file's path and represents what the package advertises as usable from outside. |
| `TestSuite` | A collection of test files grouped by location and/or framework configuration, with a derived semantic target (the package, domain, or repository it tests). A package can have 0, N test suites (e.g., unit, integration, e2e). A suite contains test files; tests are *not* directly contained by the `Package` even when they live inside the package directory on disk. |

#### `TestSuite` attributes

| Attribute | Meaning |
|---|---|
| `name` | Suite identifier (often derived from directory name: `unit`, `integration`, `e2e`). |
| `framework` | Detected test framework (`pytest`, `jest`, `vitest`, `mocha`, etc.). |
| `kind` | Best-effort classification: `unit`, `integration`, `e2e`, `contract`, `unknown`. Derived from naming, config, and import breadth. |

#### `EntryPoint` attributes

| Attribute | Meaning |
|---|---|
| `name` | The advertised name (e.g., `mytool`, `.` for default export). |
| `kind` | `executable` (CLI/bin entry) or `library` (importable entry). |
| `source` | Which manifest declaration produced it (`pyproject.scripts`, `package.json.bin`, `package.json.exports`, etc.). |

Only *declared* entry points become `EntryPoint` nodes. Files that happen to be executable by convention (a shebang script in `scripts/`) are captured via `File.is_executable`, not by inventing an `EntryPoint`.

### Explicitly *not* nodes

- Generic container folders like `packages/`, `libs/`, `apps/`, `shared/`, `common/`. These are workspace conventions, not meaningful entities. A package node carries its filesystem path as an attribute; the containing directory itself is not a node.
- Repo-root `tests/` directories. Same treatment as `packages/` — a `tests/` directory is a workspace-level container, not a node. Its immediate subdirectories (or itself, if it holds test files directly) become `TestSuite` nodes.
- JS/TS intermediate directories inside a package. JS/TS has no language-level concept of sub-packages; directory groupings inside a package are organizational, not structural. They live as path attributes on `File` and are reconstructed at query/render time via path-prefix queries if needed.
- Undeclared "scripts" as a separate type. Executable convention-files are `File` nodes with `is_executable: true`.
- A distinct `Test` node type for test files. Test files are `File` nodes with `is_test: true`; the `TestSuite` node provides the organizational grouping and the `tests` edge carries the semantic relationship.

---

## 4. Edge Types

Edges are grouped by purpose. Curated edges are authored by humans (or heuristics with human review). Derived edges are computed by the scanner from other edges.

### 4.1 Structural edges (tree, derived from filesystem)

| Edge | From → To | Notes |
|------|-----------|-------|
| `physically_contains` | `Repository → Package` | A repo contains the packages declared in its workspace. |
| `physically_contains` | `Package → SubPackage` | **Python only.** A package contains its top-level sub-packages. |
| `physically_contains` | `SubPackage → SubPackage` | **Python only.** Nested sub-packages. |
| `physically_contains` | `SubPackage → File` | **Python only.** Files within a sub-package. |
| `physically_contains` | `Package → File` | Files directly under a package (always for JS/TS; for Python, files at the package root). |
| `physically_contains` | `Package → TestSuite` | When test files live inside the package directory. Test files are then under the suite, not directly under the package. |
| `physically_contains` | `Repository → TestSuite` | When test files live outside any package directory (e.g., repo-root `tests/integration/`). |
| `physically_contains` | `TestSuite → File` | Test files (and supporting fixtures/helpers) belong to the suite. |

Each node has **exactly one** structural parent — this is a strict tree. JS/TS trees are shallower (no `SubPackage` layer); Python trees can be arbitrarily deep. Test files belong to a `TestSuite` regardless of whether the suite lives inside the package or alongside it — this is what keeps `Package physically_contains` clean of test content.

### 4.2 Entry point edges (declared)

| Edge | From → To | Notes |
|------|-----------|-------|
| `declares_entry_point` | `Package → EntryPoint` | A package advertises this entry point in its manifest. |
| `implemented_by` | `EntryPoint → File` | The file that implements the entry point. May also point to a `Function`/`Class` for finer-grained entry points (e.g., `pkg.cli:main`). |

### 4.3 Test edges

| Edge | From → To | Notes |
|------|-----------|-------|
| `tests` | `TestSuite → Package` | **Primary semantic edge.** The suite tests this package. Derived from imports in the suite's test files. A suite can have multiple `tests` edges. |
| `tests` | `TestSuite → Domain` | An integration/e2e suite that exercises a domain end-to-end rather than a single package. Derived. |
| `tests` | `TestSuite → Repository` | A whole-system suite (smoke, e2e against the entire repo). Derived. |
| `tests` | `File → File` | A test file targets a specific source file. *Derived, best-effort* — from imports + filename conventions (`test_foo.py` → `foo.py`, `foo.test.ts` → `foo.ts`). |
| `tests` | `Function → Function` | A test function targets a specific source function. *Derived, best-effort* — from naming conventions and the call graph. |

The `TestSuite → Package/Domain/Repository` edges are the strong ones used for high-level queries ("what tests cover billing?"). The file-level and function-level `tests` edges are guidance for finer-grained navigation and should be treated as advisory.

### 4.4 Domain edges (DAG, curated)

| Edge | From → To | Notes |
|------|-----------|-------|
| `belongs_to_domain` | `Package → Domain` | A package may belong to 0..N domains. Authored or inferred + confirmed. |
| `domain_contains_domain` | `Domain → Domain` | Sub-domain relationship (e.g., Payments contains Billing). Tree by default. |

A package with zero `belongs_to_domain` edges is intentional, not an error — these are the cross-cutting/shared packages.

### 4.5 Reference edges (derived from imports + domain membership)

| Edge | From → To | Notes |
|------|-----------|-------|
| `references` | `Domain → Package` | A package in domain D imports package P, and P does not belong to D. Computed. Annotated with usage count (how many packages in D import P). |
| `depends_on` | `Domain → Domain` | A package in domain A imports a package belonging to domain B. Computed. |

These edges lift cross-cutting and inter-domain relationships up to the domain level so they're queryable without re-walking the full import graph each time.

### 4.6 Code edges (existing — unchanged)

`imports`, `exports`, `imported_by`, `calls`, `callees`, `contains`, `defines`, `re-exports`, etc. — retained from the current AST graph. These operate on code-level nodes.

---

## 5. Why a DAG for Domain Membership

A tree forces every package to have exactly one domain, which breaks down for shared/utility packages and for monorepo packages that span domains. A DAG allows:

- A package to belong to multiple domains when it genuinely does.
- A package to belong to no domain (cross-cutting utilities like `logger`, `date-utils`).
- Domains to nest (Payments contains Billing and Subscriptions) without forcing transitive membership to be stored.

**No "Shared" or "Common" domain.** The instinct to put utility packages into a `Shared` domain is rejected: it collapses a real distinction (genuinely cross-cutting vs. domain-internal), encourages over-classification, and recreates the bucket problem. Cross-cutting packages have zero `belongs_to_domain` edges, and their usage is surfaced through derived `references` edges. If categorical labels are needed for utility packages (e.g., distinguishing `logger` from `internal-sdk`), use a lightweight `tagged_with` mechanism — not domain membership.

If the wiki needs a landing page for cross-cutting concerns, that's a **view** computed at render time ("packages with no domain, grouped by usage breadth"), not a stored domain node.

---

## 6. Nested Domains — Semantics

- **Parent membership is implicit, not stored.** If a package belongs to Billing and Billing is under Payments, queries treat the package as part of Payments by walking down through `domain_contains_domain`. The edge is not duplicated.
- **Domain hierarchy is a tree.** A domain has one parent domain (or none). If a sub-domain seems to need two parents, that's a sign one of those relationships is really a cross-cutting concern and belongs as a tag or as a derived dependency edge — not as a structural parent.
- **Derived edges bubble up.** If a package in Billing references `logger`, then Payments also references `logger`. Computed on read.

---

## 7. Test Suite Layout and Detection

Test code organization varies widely across projects. The ontology handles this through a small set of rules that work uniformly across the common patterns.

### Layout patterns the scanner must handle

1. **Single-package repo, tests at root.** One package, `tests/` at repo root tests it. One `TestSuite`, contained by the Repository, with `tests → Package`.
2. **Monorepo with mirrored test layout.** `tests/auth/`, `tests/billing/` — each subdirectory tests the corresponding package. N `TestSuite` nodes, each contained by the Repository, each with `tests → Package`.
3. **Monorepo with cross-cutting integration tests.** `tests/integration/`, `tests/e2e/` — suites that exercise multiple packages or the whole system. `TestSuite` nodes with multiple `tests` edges, or `tests → Domain` / `tests → Repository`.
4. **Package-local tests.** `packages/auth/tests/` — tests live inside the package directory. `TestSuite` contained by the Package, `tests → Package`.
5. **Mixed.** Most mature monorepos combine #2/#4 (per-package unit tests) with #3 (repo-root integration tests).

### Rules for the scanner

- **Repo-root `tests/` is a container, not a node.** Same treatment as `packages/` and `libs/`.
- **Each immediate subdirectory of `tests/` becomes a `TestSuite`.** If `tests/` holds test files directly (no subdirectory grouping), `tests/` itself becomes a single suite.
- **Suite targets (`tests` edges) are derived from imports**, not from directory naming. A suite that imports from one package gets one `tests → Package` edge; a suite that imports from many gets many edges (or a coarser `tests → Domain` / `tests → Repository` edge).
- **Directory naming is at best a tiebreaker.** Names like `integration/`, `e2e/`, `system/`, `smoke/` inform the suite's `kind` attribute but do not determine its targets.
- **Explicit test framework config overrides convention.** `pytest.ini`, `pyproject.toml [tool.pytest]`, `jest.config.js`, etc. are read when present and used to identify suite boundaries authoritatively.
- **No `TestSuite` nesting.** Even when nested directory structures suggest hierarchy (`tests/integration/auth/`), the scanner emits flat suites. "Integration" lives on the suite's `kind` attribute or as a tag, not as a parent node. This is consistent with the broader principle of not inventing structure the filesystem doesn't formalize.

### What ends up where

- A package's `physically_contains` subtree is its production code — never test files. Test files live under a `TestSuite`, which is a separate node even when the suite physically lives inside the package directory.
- The `tests` edge carries the semantic relationship regardless of physical layout. Queries about "tests for this package" should traverse `tests` edges, not physical containment.

---

## 8. Identity and Wiki Layout

- Every node has a stable URI-style ID (e.g., `repo:org/foo`, `pkg:org/foo/auth-service`, `domain:billing`).
- Wiki content is keyed by ID, not by filesystem location.
- The wiki renderer is responsible for producing whatever on-disk layout makes sense (flat by ID, organized by domain, organized by repo — multiple views are possible from the same source).
- Moving a package between domains is a single edge change, not a filesystem rename.

---

## 9. Scanner Pipeline

The scan is decomposed into independent stages so domain assignment can be re-run without re-parsing code.

1. **Filesystem walk.** Discover repositories, packages (by manifest), Python sub-packages (by `__init__.py`), and files. Build the physical containment tree. Detect `File` role flags (executable, test, config, generated, type-only) from path conventions, shebangs, and content sniffing. Output: structural nodes and `physically_contains` edges.
2. **Manifest parse.** Read package manifests for declared entry points (`pyproject.toml [project.scripts]`, `package.json "bin"`/`"main"`/`"exports"`) and test framework config (`pytest.ini`, `pyproject.toml [tool.pytest]`, `jest.config.js`, etc.). Output: `EntryPoint` nodes and `declares_entry_point` / `implemented_by` edges.
3. **Test suite detection.** Identify `TestSuite` nodes from filesystem layout and framework config (see §7). Re-parent test files from their direct package containment to the suite. Output: `TestSuite` nodes, suite-level `physically_contains` edges, and re-parented test `File` nodes.
4. **AST parse.** Walk source files; extract functions, classes, methods, etc. Refine `File` role flags using AST signals (e.g., presence of `if __name__ == "__main__":`). Output: code-level nodes and `defines`/`exports` edges.
5. **Import resolution.** Resolve imports across packages. Output: `imports`/`imported_by` edges and call-graph edges.
6. **Test target derivation.** From the imports of files in each `TestSuite`, derive `tests` edges to packages, domains, or the repository. Apply best-effort file-level and function-level `tests` edges using naming conventions. Output: `tests` edges.
7. **Domain assignment (overlay).** Read domain config and apply heuristics. Output: `belongs_to_domain` and `domain_contains_domain` edges. Re-runnable without touching stages 1–6.
8. **Derived edge computation.** Compute `references` and `depends_on` from the import graph + domain membership. Output: derived edges with usage annotations.
9. **Wiki render.** Project the unified graph into wiki pages. Multiple views possible.

### Domain inference strategies (for stage 7)

Domain assignment is additive and can come from multiple sources, in priority order:

1. **Explicit config** — a `domains.yaml` (or similar) declaring packages and sub-domains. Most predictable.
2. **Convention** — top-level folder names in a monorepo, with named folders (e.g., `billing/`, `location/`) treated as domain candidates and generic folders (`packages/`, `libs/`, `shared/`) ignored.
3. **Import-graph clustering** — packages that mostly import each other are likely a domain. Useful for suggestions.
4. **LLM-proposed groupings** — initial suggestions for human review.
5. **Manual overrides** — always win.

v1 should support explicit config + convention. Leave hooks for the others.

---

## 10. Example Queries Enabled

- "What packages are in the Billing domain (including sub-domains)?" → walk `domain_contains_domain` down from Billing, then collect packages via `belongs_to_domain`.
- "What does the Billing domain depend on (outside of itself)?" → read `Domain references Package` edges from Billing.
- "Does Billing depend on Auth?" → check `Domain depends_on Domain` from Billing to Auth.
- "What functions in the Auth domain call into the Billing domain?" → join `belongs_to_domain`, `physically_contains` (transitively), and `calls`.
- "Which utility packages are most widely used?" → packages with zero `belongs_to_domain` edges, ranked by count of incoming `references` edges from distinct domains.
- "What can I run from this package?" → query `EntryPoint` nodes with `kind: executable` declared by the package.
- "What does this package export?" → query `EntryPoint` nodes with `kind: library` declared by the package.
- "What scripts exist in this repo (declared or conventional)?" → union of `EntryPoint` nodes with `kind: executable` and `File` nodes with `is_executable: true`.
- "What tests cover this package?" → `TestSuite` nodes with `tests → Package`, then their contained `File` nodes.
- "What integration tests touch the Billing domain?" → `TestSuite` nodes with `tests → Domain(Billing)` *or* with multiple `tests → Package` edges where the packages belong to Billing.
- "Give me the production code surface of this package, excluding tests." → `physically_contains` subtree of the Package, which by construction does not include test files (they're under `TestSuite`).

---

## 11. Open Questions for Review

1. **Manifest detection edge cases.** Python projects without a `pyproject.toml`/`setup.py` (legacy or script-style repos): is the repo root treated as a single implicit package, or do we require a manifest? Recommendation: require a manifest, fall back to `__init__.py` at a workspace root with a flag indicating it's a synthetic package.
2. **Tagging.** Is a `tagged_with` mechanism in scope for v1, or deferred? It's lightweight and would help categorize utility packages without abusing domain membership.
3. **Cross-repo domains.** Should a single `Domain` node be allowed to contain packages from multiple repositories? This is a strong reason to keep `Repository` and `Domain` as independent first-class nodes — confirm this is the desired behavior.
4. **Storage and re-render strategy.** What's the persistence layer for the graph (in-memory, SQLite, a graph DB)? This affects how cheap derived-edge recomputation is, and therefore how aggressive we can be about deriving vs. storing.
5. **Versioning of domain config.** Domain assignment is curated; it should probably live in version control alongside code. Where does `domains.yaml` live in a multi-repo setup?
6. **Entry point granularity.** Python entry points can target a specific callable (`pkg.cli:main`), not just a file. Should `EntryPoint.implemented_by` point at `Function`/`Class` nodes in that case, or always resolve to a `File` with the callable as a separate attribute? Recommendation: allow either, with `implemented_by` polymorphic over `File` and `Function`/`Class`.
7. **Role flag detection confidence.** Some flags (e.g., `is_executable` from a shebang) are high-confidence; others (e.g., `is_generated` from heuristic markers) are not. Should flags carry confidence/source metadata, or are boolean values sufficient for v1?
8. **Test suite consolidation threshold.** When a repo-root `tests/` has many subdirectories with overlapping import patterns, should the scanner emit one `TestSuite` per subdirectory (current rule) or attempt to consolidate based on framework config? The current rule is predictable; consolidation could reduce node count for projects with deeply nested test layouts.
9. **Test fixtures and helpers.** Files under a `TestSuite` that aren't themselves test definitions (fixtures, helpers, factories) — are they `is_test: true`, a separate flag like `is_test_support: true`, or just `File` nodes with no role flag set? Recommendation: `is_test: true` covers anything under a `TestSuite`; introduce `is_test_support` later only if a real query needs the distinction.

---

## 12. Summary of Decisions

| Decision | Choice |
|---|---|
| Physical layout representation | Strict tree, derived from filesystem |
| Domain membership representation | DAG, curated (config + heuristics) |
| Domain as node or tag | First-class node |
| Repository as node or attribute | First-class node |
| Universal file-level node | `File` (matches both languages' use of "module" for a file) |
| Python intermediate grouping | `SubPackage` node, Python-only |
| JS/TS intermediate grouping | Not modeled as a node; lives as path attribute on `File` |
| Library vs. script distinction | Role flags on `File` (not separate node types) |
| Declared entry points | First-class `EntryPoint` node, per manifest declaration |
| Undeclared executable files | `File` with `is_executable: true`, no `EntryPoint` node |
| Test grouping | First-class `TestSuite` node; test files contained by suite, not package |
| Test/source semantic relationship | `tests` edge at suite, file, and function levels (file/function are best-effort) |
| Test node type | None — test files are `File` with `is_test: true` |
| Repo-root `tests/` | Container, not a node; immediate subdirectories become `TestSuite` nodes |
| Test suite targets | Derived from imports, not directory naming |
| Test suite nesting | Flat — no `TestSuite → TestSuite` hierarchy |
| Shared/utility packages | Zero `belongs_to_domain` edges; no "Shared" domain |
| Generic container folders (`packages/`, `libs/`) | Not modeled as nodes |
| Cross-cutting usage representation | Derived `Domain references Package` edge |
| Inter-domain dependency representation | Derived `Domain depends_on Domain` edge |
| Nested domains | Tree of domains; transitive membership computed, not stored |
| Wiki content identity | Stable URI; on-disk layout is a render artifact |
| Existing AST graph | Retained; new nodes/edges layered on top |
| Scan architecture | Pipeline with domain assignment as a separable overlay stage |

---

*End of draft. Review, revise, and use as the starting point for development planning.*
