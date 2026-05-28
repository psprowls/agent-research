# Phase 49: Builtin Kind (graph-io) - Context

**Gathered:** 2026-05-27
**Status:** Ready for planning

<domain>
## Phase Boundary

Add a `Builtin` node kind to `graph-io` so Python and Node.js stdlib imports stop showing up as unresolved Symbol/Function nodes. New URI scheme `builtin:<language>/<module_name>`, dedup-friendly `used_by` edges from packages, and two new CLI surfaces (`cg list-builtins`, `cg describe-builtin`). Builtin pages are explicitly NOT rendered to the wiki (excluded from `wiki_io.entity_writer.ADMITTED_KINDS`).

In scope: scanner classification, URI/kind/edge schema, CLI surfaces, incremental update behavior.
Out of scope: App reclassification (Phase 50), `package_family` removal (Phase 51), wiki filename slimdown (Phases 52-53), and any wiki rendering of Builtin nodes (deferred — `ADMITTED_KINDS` excludes builtin in Phase 51 cleanup).

</domain>

<decisions>
## Implementation Decisions

### Stdlib list source & versioning
- **D-01:** Use **runtime introspection** for both languages.
  - Python: `sys.stdlib_module_names` (3.10+; project floor is 3.11, so always available).
  - Node: shell out to `node -e 'console.log(JSON.stringify(require("module").builtinModules))'`.
- **D-02:** Cache the Node builtin list to disk on first successful invocation. Location: `<workspace>/.graph/cache/node-builtins-<major>.json` (next to the graph DB). Keyed by Node major version. Invalidate by re-running `node -e` when the file is missing or `node --version` reports a different major.
- **D-03:** When `node` is not on PATH, the cache file is missing, and no JS files were scanned: skip silently. The JS resolver still distinguishes bare names from path imports; bare names just don't get reclassified as Builtin. (Same effective behavior as today.)
- **D-04:** Scanner runtime is the source of truth for Python stdlib classification. Accept drift across Python versions (e.g., if scanner is on 3.12, the removed-in-3.12 `distutils` won't classify as Builtin and will fall through as unresolved — matches today's behavior). No `requires-python` parsing; no historical-superset union.

### Submodule granularity
- **D-05:** **Top-level only.** `from os.path import join` → `builtin:python/os`. One Builtin node per top-level stdlib module. Mirrors how `dependency` nodes work today (one per package, not per submodule).
- **D-06:** Node: collapse `require('fs')`, `import 'node:fs'`, and `import 'node:fs/promises'` all to the same `builtin:javascript/fs` node. Strip the `node:` prefix, drop the subpath. Symmetric with the Python decision.

### Symbol-level imports
- **D-07:** Module-level edges only — no per-symbol Function/Symbol nodes for stdlib calls. `from os import getenv` produces a `used_by` edge to `builtin:python/os`, not a Function node for `getenv`.
- **D-08:** Edge carries an `imported_symbols` attr on `attrs_json` — the sorted union of all named imports seen across the package. Edge shape: `{src: package_id, dst: builtin_id, kind: "used_by", attrs_json: {"imported_symbols": ["environ", "getenv"]}}`.
- **D-09:** **One edge per (package, builtin)** — file-level granularity is NOT preserved. 30 import statements across 12 files in the same package collapse to one edge. Matches the existing dependency-edge dedup pattern in `packages/graph-io/src/graph_io/packages.py:203-208`.

### Schema version & migration
- **D-10:** **Do NOT bump `SCHEMA_VERSION`.** Currently 2 (`packages/graph-io/src/graph_io/schema.py:12`); stays at 2 for Phase 49. The DDL is unchanged — kinds are text strings, not enum-constrained at the SQL layer, so adding `"builtin"` to `_VALID_KINDS` is a Python-side change only. An incremental `cg update` on a pre-v1.9 graph will simply emit Builtin nodes alongside any pre-existing unresolved Symbols.
- **D-11:** Do not retroactively clean up pre-v1.9 unresolved Symbol nodes for stdlib calls. They linger until the user opts into `cg update --full`. The Phase 49 ship note tells the user to run `cg update --full` once after upgrading. Cheapest path; consistent with "single dev, full rebuild is fast".

### CLI surfaces
- **D-12:** `cg list-builtins` mirrors `cg list-dependencies` (output shape, JSON-vs-text flag).
- **D-13:** `cg describe-builtin <uri>` mirrors `cg describe-dependency <uri>` (shows packages that use it via `used_by` edge count; surfaces `language` and `module_name` attrs).

### Locked by upstream (not discussed)
- **D-14:** Add `"builtin"` to `_VALID_KINDS` in `packages/graph-io/src/graph_io/queries.py:9`.
- **D-15:** Builtin nodes carry `language` (`python` | `javascript`) and `module_name` (e.g., `pathlib`, `fs`) attributes — both required, both inspectable via `cg describe-builtin`.
- **D-16:** Builtin is excluded from `wiki_io.entity_writer.ADMITTED_KINDS` (no wiki page rendering). Confirm exclusion already exists or add the exclusion annotation in this phase per BUILTIN-06 success criterion #5.

### Claude's Discretion
- Exact `attrs_json` schema for the `imported_symbols` attr (e.g., key name `imported_symbols` vs `symbols`; whether to also include a `usage_count` integer alongside the list).
- Implementation point in the scanner pipeline (likely `derived_edges.compute` or alongside it in `packages.py`, mirroring the dependency-emission pattern) — planner can pick.
- Import-scanner regex extension to capture named imports — current `_PYTHON_IMPORT_RE` and `_JS_IMPORT_RE` (`packages/graph-io/src/graph_io/import_scan.py:20-23`) only capture the module spec, not the symbols after `import`. Planner decides whether to extend the regex or switch the Python path to AST parsing.
- Whether `node -e` invocation goes through `subprocess.run` directly or behind a small `_node_runtime.py` helper (likely the latter for testability).

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Requirements & roadmap
- `.planning/REQUIREMENTS.md` — Milestone v1.9 requirements (BUILTIN-01 through BUILTIN-06 plus full scope context).
- `.planning/ROADMAP.md` §Phase 49 — goal, success criteria, dependencies.

### Schema & kind admission
- `packages/graph-io/src/graph_io/schema.py:12` — `SCHEMA_VERSION = 2` (stays at 2; see D-10).
- `packages/graph-io/src/graph_io/queries.py:9` — `_VALID_KINDS` frozenset; add `"builtin"` here.

### URI builders
- `packages/graph-io/src/graph_io/uri.py` — existing `dependency_uri`, `pkg_uri`, etc. New `builtin_uri(language, module_name)` follows the same pattern.

### Edge emission pattern to mirror
- `packages/graph-io/src/graph_io/packages.py:132-220` — dependency ingestion: how `used_by` edges are accumulated per `(consumer, dep)`, deduped, and emitted. The Builtin emission should mirror this structure.

### Import scanning
- `packages/graph-io/src/graph_io/import_scan.py:20-23` — `_PYTHON_IMPORT_RE` and `_JS_IMPORT_RE`. Currently capture module spec only; may need extension to capture named imports per D-08.
- `packages/graph-io/src/graph_io/import_scan.py:45-66` — `_build_importable_maps`, the existing pkg-prefix index that import resolution uses today.

### Read-only query layer
- `packages/graph-io/src/graph_io/queries.py:563-595` — `describe_dependency` pattern; describe-builtin mirrors this.

### CLI surface
- `packages/graph-io/src/graph_io/cli/` — locate `list-dependencies` and `describe-dependency` handlers; `list-builtins` and `describe-builtin` follow the same template.

### Conventions
- `packages/graph-io/CLAUDE.md` — read-only queries via `store.read_only_connect()`; updates inside one transaction via `store.transaction()`; errors → stderr, JSON → stdout; exit codes stable from `exit_codes.py`.

### Wiki admission
- (Phase 51 will clean this up further) `wiki_io.entity_writer.ADMITTED_KINDS` — confirm `builtin` is excluded; this phase's success criterion #5 explicitly requires the exclusion annotation. Locate the file at planning time.

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- **`packages.py` dependency-emission code path** (`graph-io/src/graph_io/packages.py:132-220`): the entire dedup-and-emit pattern for `used_by` edges is reusable structurally. Builtin emission can sit next to dependency emission and share the accumulator shape.
- **`uri.py` builder pattern**: `dependency_uri(ecosystem, name)` is a one-line pure function. `builtin_uri(language, module_name)` follows the same shape.
- **`describe_dependency` read path** (`queries.py:563-595`): the JOIN-back-to-package query and the `NodeRecord` dataclass shape are directly applicable to describe-builtin.
- **`store.read_only_connect()` / `store.transaction()`**: existing helpers that all reads/writes funnel through. No new transaction infrastructure needed.

### Established Patterns
- **Node-kind admission lives in `queries.py` `_VALID_KINDS`**, not in `schema.py`. The SQL layer is text-flexible; Python-side validation is the gatekeeper. Adding `"builtin"` is a one-line change.
- **`used_by` edges are deduped per `(src, dst)`** in `packages.py` via the `(consumer_name, consumer_rel_path, dep_name)` accumulator. The accumulator key collapses to `(consumer_name, dep_name)` at emit time — Builtin can use the same shape.
- **JSON-everything in `attrs_json`**: per-kind detail (e.g., `imported_symbols`) lives in `attrs_json` blobs, not new columns. Schema stays at v2.
- **Errors → stderr, JSON → stdout** (`packages/graph-io/CLAUDE.md`). The "no Node binary, no JS files scanned → silent skip" decision (D-03) respects this — no false-alarm stderr noise.
- **Idempotent re-runs**: `cg update` is idempotent by virtue of `INSERT … ON CONFLICT DO UPDATE` patterns. Builtin emission should preserve this; one edge per (package, builtin) per the dedup decision (D-09) means the union of `imported_symbols` is the merge target on re-emission.

### Integration Points
- `_VALID_KINDS` in `queries.py` — add `"builtin"`.
- `uri.py` — add `builtin_uri(language, module_name)`.
- `packages.py` (or a new sibling module): builtin classification during the same scan pass that emits dependency edges. Both need the import scan results.
- `import_scan.py` — extend regex / parser to capture named imports if D-08's `imported_symbols` is to be populated at scan time.
- New CLI handlers in `packages/graph-io/src/graph_io/cli/` for `list-builtins` and `describe-builtin`.
- `wiki_io.entity_writer.ADMITTED_KINDS` — confirm `builtin` is excluded.

</code_context>

<specifics>
## Specific Ideas

- Cache path uses the existing `.graph/` directory convention (next to the SQLite DB) rather than `$XDG_CACHE_HOME` — keeps the workspace self-contained and lets `cg update --full` semantics naturally clear it.
- Mirror the dependency CLI shape exactly (`list-dependencies` / `describe-dependency` → `list-builtins` / `describe-builtin`) — no new flag shapes, no new output schemas. Discoverability is automatic for anyone who has used the dependency commands.
- Symbol-level Function nodes for stdlib were explicitly rejected (D-07) because stdlib has thousands of functions and even sparse usage would substantially inflate the node table.

</specifics>

<deferred>
## Deferred Ideas

- **Pre-v1.9 unresolved Symbol cleanup**: not done in this phase; user runs `cg update --full` if they want a clean state. Could become its own one-shot migration command later if it turns out the lingering Symbols cause real query noise.
- **Per-Python-version stdlib correctness**: the union-with-historical-superset and `requires-python`-driven snapshot options were rejected (D-04). Revisit only if scanner-vs-target version drift turns out to produce noticeable misclassification in this repo.
- **In-repo committed Node-builtins snapshot**: rejected in favor of per-workspace runtime caching (D-02). Reconsider if CI environments without Node become common — current personal-project context doesn't require it.
- **Function nodes under Builtin parents**: rejected for v1.9 (D-07). If we later need per-function dependency analysis on stdlib calls, this is the natural place to introduce it — but only on demand.

</deferred>

---

*Phase: 49-Builtin Kind (graph-io)*
*Context gathered: 2026-05-27*
