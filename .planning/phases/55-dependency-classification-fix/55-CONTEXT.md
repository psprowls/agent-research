# Phase 55: Dependency Classification Fix - Context

**Gathered:** 2026-05-28
**Status:** Ready for planning

<domain>
## Phase Boundary

Stop the `graph-io` scanner from double-classifying a workspace package: a name that is already a workspace `package`/`app` node must never also be emitted as a `dependency` node. The internal package→package relationship is instead represented as a dedicated `depends_on_package` graph edge, which surfaces in `cg describe-package` and (downstream) IDX-05 nesting.

Two requirements:
- **CLASS-01** — Suppress the `dependency` node for any dependency name that matches a workspace package/app (no `dep_graph-io.md` for `graph-io` when it's a workspace package).
- **CLASS-02** — Represent the internal package→package usage as a graph edge so the relationship still surfaces. **Note:** this phase intentionally amends CLASS-02's "represented as a `depends_on` edge" wording — see D-04/D-05 below.

Goal state: after a full `cg update`, no dependency node exists for any workspace-package name; an internal dependency is a `depends_on_package` edge between the two package/app nodes; and `cg describe-package <name>` shows both internal dependencies and dependents.
</domain>

<decisions>
## Implementation Decisions

### Name matching (CLASS-01 — what gets suppressed)
- **D-01:** Build the workspace-package-name set **once** from `_discover_manifests()` (the set of all manifest `info["name"]` values discovered during `packages.refresh()`). This set is already derivable at the point where dependency nodes are emitted (`packages.py:215-254`).
- **D-02:** Match using **normalization**: lowercase both sides and treat `-` / `_` as equivalent (PEP 503-style), so `graph-io` (dep string) matches `graph_io` (importable) and the workspace name regardless of separator/case. A bare exact-string match was rejected — it would leave the bug partially unfixed on the hyphen/underscore mismatch.
- **D-03:** Matching is **cross-ecosystem** (suppress on normalized name match regardless of ecosystem). Rationale: this is currently a Python-only `uv` workspace, so a cross-ecosystem name collision (a JS package accidentally suppressing a same-named pypi dep) is effectively impossible. Chosen for simplicity over ecosystem-scoping. **Revisit if** a real JS/non-Python workspace package is ever added — at that point ecosystem-scoped matching becomes the safer rule.

### Edge representation (CLASS-02 — intentional scope amendment)
- **D-04:** Introduce a **new, distinct edge kind: `depends_on_package`** for the internal package→package relationship. Direction: **src = the consumer** (the package whose manifest declares the dependency), **dst = the internal package being depended on**.
- **D-05:** **This intentionally amends locked scope.** `REQUIREMENTS.md:54` states "no new node/edge kinds beyond the `depends_on` edge reuse in CLASS-02," and CLASS-02 is worded as "represented as a `depends_on` edge." The reuse option (kind=`depends_on`, distinguished from the existing Domain→Domain `depends_on` by node IDs) was the no-scope-change path and is technically clean — storage already separates the rows. Pat chose a distinct kind anyway for **query ergonomics / readability**. **Action required:** update CLASS-02 and the `REQUIREMENTS.md:54` "no new edge kinds" line (via `/gsd-phase` or a direct REQUIREMENTS edit) so the requirement and CONTEXT stay in sync; otherwise the verifier will flag a mismatch.
- **D-06:** Edge derivation source is the **manifest declaration** — emit `depends_on_package` from the same `[project.dependencies]` / `[dependency-groups]` parse where the `dependency` node is suppressed (`packages.py:215-274`). One source of truth, co-located with the fix. `import_scan` resolution was rejected as the driver (separate code path; SC#2 says "import relationship" but the manifest declaration is the dependency-of-record). Declared-but-not-yet-imported internal deps still produce an edge, which is acceptable.

### used_by edge handling
- **D-07:** **Keep the `used_by` edge and retarget its `dst`** from the (now-suppressed) `dependency` node to the existing package/app node (`packages.py:259-272`, currently `dst=("dependency", dep_name, None)`). The `depends_on_package` edge is emitted **in addition**. This yields two same-direction edges (consumer→internal package) for one relationship — **intentional redundancy**: `used_by` stays the *universal* "consumer uses X" relationship (uniform across external deps and internal packages), while `depends_on_package` carries the package-level semantic that IDX-05 nesting and `describe-package` consume. Planner must ensure the retargeted `used_by` dst resolves to the real package/app node id (use stored kind, like the Phase 50 D-04 `references`-edge fix at `derived_edges.py:148-153`).

### describe-package surfacing (SC#3)
- **D-08:** `cg describe-package <name>` must surface **both directions** of `depends_on_package`:
  - **internal dependencies** — outgoing edges (workspace packages this package depends on)
  - **internal dependents** — incoming edges (workspace packages that depend on this one)
  SC#3's literal wording ("shows internal dependents") makes the incoming direction mandatory; the outgoing direction is the natural complement and was explicitly requested.

### Claude's Discretion
- Exact normalization helper (reuse/extend any existing name-normalization used by `import_scan._build_importable_maps`, which already does `.replace('-', '_')`, vs. a small local PEP 503 normalizer) — planner's call, as long as D-02 semantics hold.
- Exact `describe_package()` output shape/labels for the two new sections, consistent with the existing query output.
- Whether to add a `usage_count` (or similar) attr on `depends_on_package` mirroring the Domain `depends_on` — optional; not required by any SC.

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Requirements & scope (note the D-05 amendment)
- `.planning/REQUIREMENTS.md` §CLASS-01/CLASS-02 (lines ~20-21) and the "no new edge kinds" scope line (~54) — **must be updated** per D-05 to reflect the new `depends_on_package` edge kind.
- `.planning/ROADMAP.md` §"Phase 55: Dependency Classification Fix" — goal + 3 success criteria.

### graph-io classification & emission (the code being changed)
- `packages/graph-io/src/graph_io/packages.py:129-274` — `refresh()`: manifest discovery, package/app node emission (148-213), dependency-node accumulation (215-235) and emission (236-254), `used_by` edge emission (255-274). **This is where CLASS-01 suppression + the `depends_on_package` edge + the `used_by` retarget all live (D-01, D-04, D-06, D-07).**
- `packages/graph-io/src/graph_io/packages.py:102-118` — `_discover_manifests()`: source of the workspace-package-name set (D-01).
- `packages/graph-io/src/graph_io/classification.py:25-83` — `classify()`: how a manifest becomes a `package` vs `app` node (context for D-07 stored-kind resolution).
- `packages/graph-io/src/graph_io/uri.py:54-55` — `dependency_uri()`: dependency node URI composition (context for what's being suppressed).

### Edge kind precedent & schema
- `packages/graph-io/src/graph_io/derived_edges.py:30,144-163` — existing `_DEPENDS_ON_KIND = "depends_on"` (Domain→Domain) and the `references`-edge `tgt_kind = pkg_key_to_kind.get(...)` pattern (the Phase 50 D-04 stored-kind fix) — **the model for resolving the retargeted `used_by`/new edge dst to the real package node (D-07).**
- `packages/graph-io/src/graph_io/queries.py:9-29` — node-kind list; `NodeRecord` (56-62). Confirm whether `depends_on_package` needs registration anywhere (edge kinds are free-text in the `edges.kind` column, so likely no schema migration).
- `packages/graph-io/src/graph_io/schema.py:14-46` — `nodes` / `edges` table structure (edges keyed by `(src, dst, kind)`).

### CLI surfaces
- `packages/graph-io/src/graph_io/update.py:232-324` (esp. line ~275 `packages.refresh(...)`) — where classification runs during `cg update`.
- `packages/graph-io/src/graph_io/cli/q_describe_package.py:19-44` + `queries.describe_package()` — where SC#3 / D-08 surfacing is implemented.
- `packages/graph-io/src/graph_io/import_scan.py:45-109,169-174` — import resolution + the existing `SELECT name, path, attrs_json FROM nodes WHERE kind IN ('package','app')` workspace-name query (reference only; NOT the chosen edge driver per D-06).

### Conventions
- `packages/graph-io/CLAUDE.md` — read-only queries via `store.read_only_connect()`; all updates in one transaction (`store.transaction()`); stderr=errors / stdout=JSON; stable exit codes (`exit_codes.py`).
- `.claude/rules/backward-compatibility.md` — entity content can be deleted/regenerated at will; user rebuilds the graph on migration, so no migration shim is needed for the suppressed nodes / new edge kind.

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- `_discover_manifests()` (`packages.py:102-118`) already yields every workspace manifest — the workspace-name set for D-01 is a one-line comprehension over it, available before dependency emission.
- The Phase 50 D-04 `references`-edge fix (`derived_edges.py:148-153`) is a ready pattern for resolving an edge `dst` to the **actual stored node kind** (package vs app) — directly reusable for the `used_by` retarget (D-07) and the new `depends_on_package` dst.
- Name normalization already exists informally in `import_scan._build_importable_maps` (`.replace('-', '_')`) — extend or mirror it for D-02.

### Established Patterns
- Edge kinds are free-text in the `edges.kind` TEXT column keyed by `(src, dst, kind)` — adding `depends_on_package` needs **no schema migration**; a Domain→Domain `depends_on` and a Package→Package `depends_on_package` are already distinct rows.
- `used_by` edges are deduped per `(consumer_name, dep_name)` (`packages.py:260-264`) — preserve that dedupe when retargeting.

### Integration Points
- `cg update` → `update.run()` → `packages.refresh()` (`update.py:~275`) is the single entry where suppression + both edges are produced.
- `cg describe-package` → `queries.describe_package()` is where D-08 (both-direction surfacing) is wired.
- **Downstream:** Phase 57 IDX-05 nesting and the index generator must target `depends_on_package` (not the Domain `depends_on`). Flag this in Phase 57 planning.

</code_context>

<specifics>
## Specific Ideas

- Pat values self-documenting code (carried from Phase 54's marker-justification preference) — the `depends_on_package` emission and the `used_by` retarget should carry brief inline comments explaining the intentional two-edge redundancy (D-07) so a future reader doesn't "clean it up."
- SC#1's `dep_graph-io.md` example is the canonical regression check: after `cg update`, no dependency entity page/node exists for any workspace-package name.

</specifics>

<deferred>
## Deferred Ideas

- **Ecosystem-scoped matching** — deferred per D-03; only becomes necessary if a non-Python (e.g. JS) workspace package is added. Not in scope now.
- **`usage_count`/weight attr on `depends_on_package`** — optional, not required by any SC; left to planner discretion (D-04 discretion note).
- **IDX-05 nesting + index generator consuming `depends_on_package`** — belongs to Phase 57, not this phase. Captured here only as a downstream dependency to flag.

None of these expand Phase 55 scope.

</deferred>

---

*Phase: 55-dependency-classification-fix*
*Context gathered: 2026-05-28*
