# Phase 50: App Reclassification (graph-io) - Context

**Gathered:** 2026-05-27
**Status:** Ready for planning

<domain>
## Phase Boundary

Add `App` as a first-class graph kind in `graph-io` (separate from `Package`, not just an attribute flag), emitted by the scanner when manifest signals indicate the directory is an application rather than a library. Signals: Python `[project.scripts]` non-empty (→ `cli`), JS `bin` (→ `cli`), `next` dependency (→ `nextjs`), `expo` dependency (→ `expo`), `vite` dependency + `index.html` at package root (→ `spa`). Includes `app_kind` attribute, lossless `app_signals` list, documented precedence, URI rewrite (`pkg:` ↔ `app:`), and `cg list-apps` / `cg describe-app` CLI surfaces.

In scope: scanner classification module, URI/kind/edge schema flip, in-place row mutation when `kind` flips, CLI surfaces, `_VALID_KINDS` admission.
Out of scope: wiki-io consumer flip (deferred to Phase 52), wikilink rewrites in the vault (deferred to Phase 53), `package_family` removal (Phase 51), and any wiki rendering changes triggered by App nodes (Phase 52+).

</domain>

<decisions>
## Implementation Decisions

### Signal precedence and `app_kind` derivation
- **D-01:** **Lossless signal recording.** `attrs_json.app_signals` is the sorted list of every matched signal (e.g., `["cli", "nextjs"]`). `attrs_json.app_kind` is the *derived primary*: the most-specific framework signal if any framework matched (`nextjs > expo > spa`), otherwise `cli`. Frameworks are mutually exclusive in practice; alphabetical-stable tiebreak (`nextjs > expo > spa`) handles the theoretical multi-framework case.
- **D-02:** Signal mapping is fixed:
  - Python `[project.scripts]` non-empty → signal `cli`
  - JS `package.json bin` (string or object, non-empty) → signal `cli`
  - JS `package.json dependencies.next` present → signal `nextjs`
  - JS `package.json dependencies.expo` present → signal `expo`
  - JS `package.json dependencies.vite` present AND `index.html` at package root → signal `spa`
- **D-03:** **No App = no `app_signals` / `app_kind`.** Packages with zero matched signals stay `kind='package'` and carry neither attribute. No false-positive reclassification (satisfies APP-03 / success criterion #5).

### Pipeline placement
- **D-04:** **New module: `packages/graph-io/src/graph_io/classification.py`.** Exports a pure function `classify(manifest_dict, pkg_dir: Path) → tuple[str, str | None, list[str]]` returning `(kind, app_kind, app_signals)` where `kind ∈ {"package","app"}`. Called inline from the `_discover_manifests` loop in `packages.refresh` (`packages.py:135`). The loop emits `kind='app'` or `kind='package'` directly — no two-phase reclassify pass, no SQL UPDATE of `kind`.
- **D-05:** **`index.html` check uses direct filesystem access** — `(pkg_dir / "index.html").exists()` — not a graph query against `kind='file'` nodes. Rationale: pkg_dir is already in scope inside the loop, the check is cheap, and it keeps `classification.py` free of any `sqlite3.Connection` parameter so it stays purely testable.

### URI rewrite + inbound edge handling on kind-flip
- **D-06:** **In-place UPDATE of `kind` on the existing row** when classification flips between `package` and `app` across `cg update` runs. In the manifest loop, before calling `upsert.upsert_records`, look up both `(package, name, path)` and `(app, name, path)`. If the "other-kind" row exists and the new classification differs from it, issue an `UPDATE nodes SET kind=?, uri=?, attrs_json=? WHERE id=?` against that existing row. This preserves the row's `id` and therefore every inbound edge FK (`used_by`, `contains`, `belongs_to_domain`, etc.) — no edge rewrite needed.
- **D-07:** **URI prefix flips with `kind`.** App nodes carry `app:org/repo/<name>` URIs; Package nodes carry `pkg:org/repo/<name>`. The `app_uri(ctx, name)` builder is a new one-line function in `uri.py` mirroring `pkg_uri`. Both URIs share the `org/repo/<name>` tail so identity remains queryable across the flip.
- **D-08:** **Wikilink rewrites in the vault are deferred entirely to Phase 53 cutover.** Phase 50 ships graph-io changes only. No wiki-io writes; no `*-MIGRATION.md` log artifact in this phase. The Phase 53 work will read App nodes from the graph and rewrite `[[pkg_X]]` → `[[app_X]]` references as part of the broader filename-cutover sweep.

### CLI surfaces
- **D-09:** `cg list-apps` mirrors `cg list-packages` exactly — same JSON-vs-text flag, same row shape plus an `app_kind` column. Mirrors the Phase 49 D-12 pattern.
- **D-10:** `cg describe-app <uri>` mirrors `cg describe-package <uri>` exactly — same JOIN-back-to-edges output plus `app_kind` and `app_signals` fields surfaced in the JSON. Mirrors the Phase 49 D-13 pattern.
- **D-11:** Both new handlers live in `packages/graph-io/src/graph_io/cli/` next to `list-packages` / `describe-package`. Same `read_only_connect()` pattern; same exit codes.

### Schema admission and validation
- **D-12:** **Do NOT bump `SCHEMA_VERSION`.** Same rationale as Phase 49 D-10 — kinds are text strings, the SQL layer doesn't enforce the set. Stays at 2. Add `"app"` to `_VALID_KINDS` in `packages/graph-io/src/graph_io/queries.py:9`.
- **D-13:** **`app_kind` values live in `attrs_json`** (no new column). Per-kind detail follows the existing convention (Phase 49 D-15).

### wiki-io scope boundary
- **D-14:** **wiki-io is untouched in Phase 50.** `wiki_io/scan_monorepo.py:_infer_package_type` (path-substring heuristic) stays in place; no `wiki_io → graph_io` graph lookup added. The flip to read App nodes from the graph lands naturally in Phase 52 (Wiki Filename Slimdown — Core) when `entity_writer` is being reworked anyway.

### Claude's Discretion
- Whether to add `_VALID_APP_KINDS = frozenset({"cli","nextjs","expo","spa"})` in `queries.py` as a Python-side gate for `app_kind` values. Pro: catches typos at write time. Con: adds friction when a new framework is added later. Planner picks; default to **yes, with a clear unit test** so the gate is greppable.
- Exact `attrs_json` shape for `app_signals` — the decision specifies a sorted list of strings; whether to also carry a `signals_detail` sub-object (e.g., per-signal source manifest path or version constraint) is left to the planner. Default: just the sorted list, mirroring the minimal-attrs convention from Phase 49 D-08.
- Whether the existing-row lookup in D-06 issues a separate `SELECT` per manifest or a single batched lookup before the loop. Pure performance choice; either is correct. Default: per-manifest SELECT for code-locality with the upsert call.
- Whether `cg describe-app` surfaces matched-but-not-primary `app_signals` always or only behind `--verbose`. Default: always — the field is small (≤4 strings) and JSON consumers can ignore it.

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Requirements & roadmap
- `.planning/REQUIREMENTS.md` — Milestone v1.9 requirements APP-01 through APP-06 (lines 21-26).
- `.planning/ROADMAP.md` §Phase 50 — goal, success criteria (5 items), dependency on Phase 49.

### Schema, kind admission, URI builders
- `packages/graph-io/src/graph_io/schema.py:12` — `SCHEMA_VERSION = 2` (stays at 2; see D-12).
- `packages/graph-io/src/graph_io/queries.py:9` — `_VALID_KINDS` frozenset; add `"app"` here.
- `packages/graph-io/src/graph_io/uri.py:19` — existing `pkg_uri(ctx, name)`. New `app_uri(ctx, name)` follows the same shape (D-07).

### Node identity + upsert semantics (critical for D-06 in-place UPDATE)
- `packages/graph-io/src/graph_io/upsert.py:18-50` — `_node_id(conn, key)` lookup by `(kind, name, path)`, `_insert_node`, `_upsert_node`. The classification module's "other-kind lookup" must use these same key conventions.
- `packages/graph-io/src/graph_io/upsert.py:75-79` — edge upsert uses `ON CONFLICT(src, dst, kind) DO UPDATE` — inbound edge FKs survive because we keep the same row id during the kind flip.

### Manifest scan loop (where classification slots in)
- `packages/graph-io/src/graph_io/packages.py:90-106` — `_discover_manifests` returns `(pkg_dir, info_dict)` tuples. Both `pkg_dir` and `info` are exactly what `classification.classify(info, pkg_dir)` needs.
- `packages/graph-io/src/graph_io/packages.py:135-152` — the emit loop where `kind="package"` is currently hard-coded; this is the point where the dispatch happens.
- `packages/graph-io/src/graph_io/packages.py:45-87` — `_read_pyproject` / `_read_package_json` return shape. Note: `_read_package_json` currently flattens `dependencies` to a sorted name list and discards the version map; `next`/`expo`/`vite` detection only needs presence, so no change needed there.

### Existing entry-point reader (sanity check for signal detection)
- `packages/graph-io/src/graph_io/entry_points.py:152-160` — `[project.scripts]` parsing pattern (we re-read the same field for the `cli` signal; the entry-point emitter still runs separately and produces EntryPoint nodes regardless of classification).
- `packages/graph-io/src/graph_io/entry_points.py:352-369` — `package.json bin` (string OR dict) handling pattern.

### Update pipeline order (confirms file nodes exist before `packages.refresh`)
- `packages/graph-io/src/graph_io/update.py:273-275` — `_process_files` runs BEFORE `packages.refresh`. If we ever wanted graph-based `index.html` detection, file nodes would be available — but D-05 chose filesystem-direct.

### Read-only query layer (describe-app mirror target)
- `packages/graph-io/src/graph_io/queries.py:328-395` — `describe_package` pattern (and related `package_*` queries). `describe_app` mirrors this shape.
- `packages/graph-io/src/graph_io/queries.py:468-475` — `list_packages` count + iteration pattern; `list_apps` mirrors.

### CLI surface
- `packages/graph-io/src/graph_io/cli/` — locate `list-packages` and `describe-package` handlers (Phase 49 plans will produce `list-builtins`/`describe-builtin` next to them; `list-apps`/`describe-app` go in the same neighborhood).

### Phase 49 carry-forward (must read for consistency)
- `.planning/phases/49-builtin-kind-graph-io/49-CONTEXT.md` — D-10 (no SCHEMA_VERSION bump), D-12/D-13 (CLI mirror pattern), D-14 (`_VALID_KINDS` admission style), D-15 (`attrs_json` for per-kind detail).

### Conventions
- `packages/graph-io/CLAUDE.md` — read-only queries via `store.read_only_connect()`; updates inside one transaction via `store.transaction()`; errors → stderr, JSON → stdout; exit codes stable from `exit_codes.py`.

### wiki-io boundary (read-only context for Phase 50; the consumer flip is deferred)
- `packages/wiki-io/src/wiki_io/scan_monorepo.py:210-211` and `:254`, `:630` — current path-substring heuristic `_infer_package_type`. Phase 50 does NOT touch this; documenting its location for the Phase 52 planner.

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- **Manifest reader return shape** (`packages.py:45-87`) — both `_read_pyproject` and `_read_package_json` already produce a normalized info dict carrying `dependencies` (sorted list) and `language`. `classify()` consumes this dict directly; for Python it also needs the raw `[project.scripts]` table, which is currently parsed inside `entry_points._extract_py_entries` but not surfaced on `info`. The planner can either (a) extend `_read_pyproject` to add `scripts_present: bool` to the returned info, or (b) re-parse the toml inside `classification.classify` for that one field. (a) is the cleaner choice given (b) duplicates IO.
- **`upsert._node_id(conn, key)`** — the by-key lookup the in-place UPDATE pattern (D-06) needs. Same function works for the "other-kind" probe; just call it twice with `(package, name, path)` and `(app, name, path)`.
- **`pkg_uri` builder template** — `app_uri` is a one-line copy.
- **`describe_package` query** — directly applicable to `describe_app`.

### Established Patterns
- **Kinds are text strings; admission gated Python-side in `_VALID_KINDS`.** Adding `"app"` is a one-line change. Schema stays at v2 (Phase 49 D-10 carry-forward).
- **Per-kind detail in `attrs_json`.** `app_kind` and `app_signals` are attrs_json keys, not columns (Phase 49 D-15 carry-forward).
- **Idempotent re-runs via `INSERT … ON CONFLICT DO UPDATE`.** The D-06 in-place UPDATE for kind flips is a small explicit deviation — the classification loop checks for the "other-kind" row before letting the standard upsert path run.
- **CLI handlers mirror their analog handler shape exactly** (Phase 49 D-12/D-13 carry-forward).

### Integration Points
- New file: `packages/graph-io/src/graph_io/classification.py` — exports `classify(manifest_dict, pkg_dir) → (kind, app_kind, app_signals)`. Pure; testable without a DB.
- `packages/graph-io/src/graph_io/uri.py` — add `app_uri(ctx, name)`.
- `packages/graph-io/src/graph_io/queries.py:9` — `_VALID_KINDS` gets `"app"`; optionally add `_VALID_APP_KINDS` frozenset (Claude's Discretion).
- `packages/graph-io/src/graph_io/packages.py:135-152` — manifest emit loop: call `classify()`, branch the `kind`/`uri`/`attrs` dict, run the in-place-kind-flip check (D-06) before `upsert_records`.
- `packages/graph-io/src/graph_io/packages.py:45-87` — `_read_pyproject` likely grows a `scripts_present` field to feed classification cleanly.
- `packages/graph-io/src/graph_io/queries.py` — add `list_apps()` and `describe_app()` mirroring the package equivalents.
- `packages/graph-io/src/graph_io/cli/` — add `list-apps` and `describe-app` command handlers.

</code_context>

<specifics>
## Specific Ideas

- The signal-precedence decision is intentionally lossless (`app_signals` is the full sorted list, `app_kind` is the derived primary) so a future query like "all packages that use Next.js *and* expose a CLI" remains answerable without re-parsing manifests.
- The in-place UPDATE pattern for kind flips (D-06) was preferred over insert+rewrite-edges because it preserves the node's row id and therefore every inbound edge FK without touching the edges table — the upsert/edge pattern stays untouched, and the change is fully reversible across `cg update` runs.
- CLI shape mirrors `list-packages` / `describe-package` exactly so anyone fluent in the package commands picks up app commands for free — consistent with Phase 49 D-12/D-13.

</specifics>

<deferred>
## Deferred Ideas

- **wiki-io consumer flip** — replacing `_infer_package_type` heuristic with a graph lookup against App nodes. Deferred to Phase 52 (Wiki Filename Slimdown — Core) where `entity_writer` is being reworked anyway.
- **Wikilink rewrites in the vault** (`[[pkg_X]]` → `[[app_X]]` and entity-page filename moves). Deferred to Phase 53 (Wiki Filename Cutover); Phase 53 will read App nodes from the graph as its source of truth.
- **`_VALID_APP_KINDS` enforcement** — currently in Claude's Discretion. Could be either added as a `frozenset` gate now (caught typos) or left loose (lower friction for new frameworks). Planner picks for Phase 50; can be revisited if drift becomes a problem.
- **Per-signal metadata** (e.g., which manifest field actually triggered the `cli` signal, or which dependency version pinned `next`). `app_signals` records the signal names only; richer per-signal detail can land as an attrs_json extension later if a use case appears.
- **Additional app frameworks** beyond `cli|nextjs|expo|spa` (e.g., `remix`, `astro`, `nuxt`, FastAPI server detection). Not requested in v1.9. Adding one is a one-line change to `classification.py` + (optionally) `_VALID_APP_KINDS`.
- **Cross-language CLI signals beyond `[project.scripts]` / `bin`** (e.g., a Python `__main__.py` shebang or a `Makefile run` target). Out of scope; signal set is fixed by APP-01.

</deferred>

---

*Phase: 50-App Reclassification (graph-io)*
*Context gathered: 2026-05-27*
