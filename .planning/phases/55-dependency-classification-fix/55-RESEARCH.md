# Phase 55: Dependency Classification Fix — Research

**Researched:** 2026-05-28
**Phase goal:** Workspace packages are never double-classified as both a `package`/`app` node and a `dependency` node in the same repo.
**Requirements:** CLASS-01, CLASS-02

This phase is a focused fix inside a single package (`graph-io`). The decisions are
fully locked in `55-CONTEXT.md` (D-01 through D-08). Research here grounds those
decisions in the actual code so the planner can write concrete, line-anchored tasks.

---

## The bug, in code

`packages/graph-io/src/graph_io/packages.py::refresh()` does two passes over the workspace:

1. **First pass (per manifest, lines 148–235):** emits the `package`/`app` node for each
   workspace manifest, then — for Python manifests only — extracts every declared
   dependency string, accumulates it into `dep_acc` keyed by `(ecosystem, name)`, and
   records a `(consumer_name, consumer_rel_path, consumer_kind, dep_name)` tuple in
   `used_by_pairs`. **The accumulation does not exclude names that are themselves
   workspace packages** — so `graph-io` (a workspace package consumed by other workspace
   members) lands in `dep_acc` exactly like `boto3` would.
2. **Second pass (lines 237–274):** materializes one `dependency` node per `(ecosystem, name)`
   in `dep_acc`, plus one `used_by` edge per deduped `(consumer_name, dep_name)` pair, with
   `dst=("dependency", dep_name, None)`.

Result: a workspace package name like `graph-io` produces BOTH a `package` node (first
pass) AND a `dependency` node (second pass), and downstream a `dep_graph-io.md` entity
page. That double-classification is the bug CLASS-01 targets.

## Where each decision lands

| Decision | Code site | What changes |
|----------|-----------|--------------|
| **D-01** workspace-name set built once from `_discover_manifests()` | `packages.py:148` loop / build a `set` of normalized `info["name"]` before/while iterating | The `for pkg_dir, info in _discover_manifests(...)` loop already visits every manifest; collect the names. Because suppression happens in the *first* pass (where deps are accumulated), the full set must be known before that accumulation runs — so build it from a pre-pass over `_discover_manifests()` (cheap; it returns a list, already materialized at line 148). |
| **D-02** normalized match (lowercase, `-`/`_` equivalent) | new local helper or reuse of `import_scan` `.replace("-", "_")` | `_extract_dep_name()` (packages.py:23–38) already lowercases. Normalize by additionally collapsing `-`/`_`. The workspace-name set must be normalized the SAME way. |
| **D-03** cross-ecosystem match (no ecosystem scoping) | the suppression check | Match purely on normalized name; ignore ecosystem. Safe because the repo is a Python-only `uv` workspace today. |
| **D-04** new edge kind `depends_on_package`, `src=consumer`, `dst=internal package` | second-pass edge emission `packages.py:259–272` (or first-pass accumulation) | Add a new edge-kind constant; no schema migration (edge kinds are free-text in `edges.kind`). |
| **D-06** edge derived from the manifest declaration | same accumulation point as the suppressed dep (`packages.py:218–235`) | When a declared dep name matches a workspace package, instead of (or in addition to) the dependency accumulation, record an internal package→package relationship for edge emission. |
| **D-07** keep `used_by`, retarget its `dst` to the real package/app node + emit `depends_on_package` too | `packages.py:259–272` | The retargeted `used_by` dst must resolve to the actual stored kind (`package` vs `app`) of the internal target — mirror the Phase 50 D-04 pattern in `derived_edges.py:148–153` (`tgt_kind = pkg_key_to_kind.get(...)`). |
| **D-08** `describe_package` surfaces both internal dependencies (outgoing) and internal dependents (incoming) | `queries.py::describe_package()` (364–440) + `PackageDescription` (115–144) + CLI `cli/q_describe_package.py` | Add two new query blocks + two new dataclass fields; surface in JSON (always) and text output. |

## Resolving the edge `dst` to the real package node (D-07 mechanism)

The established pattern is in `derived_edges.py:144–156`: build a `pkg_key_to_kind` map and
look up `tgt_kind = pkg_key_to_kind.get(tgt_key, _PACKAGE_KIND)` so the edge `dst` tuple uses
the correct stored kind (`package` or `app`). In `packages.refresh()` the equivalent
information is already available: the first-pass loop computes `new_kind` per manifest, so a
`name -> (kind, rel_path)` map of workspace packages can be built in the same pre-pass that
builds the D-01 name set. The internal-dependency edge `dst` then uses that stored kind/path
rather than the dependency-node tuple `("dependency", dep_name, None)`.

Note: `used_by` is currently deduped per `(consumer_name, dep_name)` via `seen_edges`
(`packages.py:260–264`). That dedupe MUST be preserved for both the retargeted `used_by` and
the new `depends_on_package` edge.

## describe_package surfacing (D-08 / SC#3)

`describe_package()` (queries.py:364) currently filters strictly on `kind='package'` and returns
a `PackageDescription` with `files / counts / domains / entry_points / test_suites`. SC#3's
literal wording is "`cg describe-package <name>` shows internal dependents", so the INCOMING
direction (`depends_on_package` where `dst = this package`) is mandatory; D-08 adds the OUTGOING
direction (`src = this package`) as the natural complement. Both are simple self-joins on the
`edges` table filtered by `kind='depends_on_package'`, mirroring the existing `domains`/`used_by`
JOIN style already in the function. The CLI text output (`q_describe_package.py:39–43`) currently
prints only name/language/version/files/counts in text mode; the two new lists should be added to
the JSON `dataclasses.asdict(desc)` output (automatic) and to the text output for human readers.

## Schema / registration

Edge kinds are free-text in the `edges.kind` TEXT column keyed by `(src, dst, kind)`
(`schema.py:14–46`); a Domain→Domain `depends_on` row and a Package→Package
`depends_on_package` row are already distinct rows. **No schema migration is required.**
`queries.py` node-kind constants are about *node* kinds, not edge kinds; `depends_on_package`
is an edge kind, so nothing needs registration there. Per
`.claude/rules/backward-compatibility.md`, the user rebuilds the graph on any data change, so
no migration shim is needed for the now-suppressed dependency nodes or the new edge kind.

## Existing test patterns to mirror

`tests/test_packages.py` is the home for emission tests:
- `test_dependency_ingestion_from_workspace` (189) seeds two manifests in `tmp_path`, calls
  `packages.refresh(conn, repo_root=tmp_path, ctx=_CTX)`, then asserts on `nodes WHERE
  kind='dependency'` and `used_by` edge counts. This is the exact harness for CLASS-01 (assert
  NO `dependency` row for a workspace name) and CLASS-02 (assert a `depends_on_package` edge and
  a retargeted `used_by` edge whose `dst` is the `package`/`app` node).
- `test_used_by_edge_dedupes_per_consumer` (236) is the dedupe-preservation guard.
- `conn` fixture (20) and `_seed_file_node` (27) are the shared helpers.

`describe_package` query tests live in `tests/test_queries.py`; CLI text/JSON output tests in
`tests/test_cli_describe.py`.

## Validation Architecture

| Aspect | Approach |
|--------|----------|
| **Framework** | pytest (graph-io package), run via `uv run --package graph-io pytest` from repo root or `pytest tests/ -v` from the package root. |
| **Primary signal (CLASS-01)** | New unit test in `test_packages.py`: after `refresh()` over a workspace where one package declares another workspace package as a dependency, `SELECT COUNT(*) FROM nodes WHERE kind='dependency' AND name=<workspace-name>` returns 0. Fully deterministic (local sqlite + tmp_path). |
| **Primary signal (CLASS-02 edge)** | New unit test: a `depends_on_package` edge exists with `src`=consumer package/app node and `dst`=the internal package/app node (resolved to its stored kind); and the `used_by` edge for that same pair now points at the package/app node, not a `dependency` node. |
| **Primary signal (CLASS-02 / SC#3 surfacing)** | New query test in `test_queries.py` (+ CLI test in `test_cli_describe.py`): `describe_package(name=<internal-pkg>)` returns its internal dependents (incoming) and internal dependencies (outgoing). |
| **Regression guards** | (a) external deps (e.g. `boto3`, `pytest`) STILL produce a `dependency` node + `used_by` edge — suppression is name-scoped, not blanket; (b) `used_by` dedupe per `(consumer, dep)` is preserved; (c) full graph-io suite green: `uv run --package graph-io pytest`. |
| **Feedback latency** | graph-io unit suite is local sqlite, < ~20s; quick `test_packages.py` run is a few seconds. |
| **Manual-only** | None — every behavior is automatable against an in-memory/tmp_path sqlite graph. |

## Risks & landmines

- **Suppression must not be blanket.** Only names that match a workspace package are
  suppressed; `boto3`/`pytest` etc. must keep their `dependency` node. The regression test
  for external deps guards this.
- **Build the name set before the dep-accumulation pass.** Because dep accumulation happens in
  the first per-manifest loop, the full workspace-name set must already be known when that loop
  runs. `_discover_manifests()` returns a fully materialized list, so a cheap pre-pass over it
  (before the main loop) is the clean place to build both the normalized name set (D-01/D-02)
  and the `name -> (kind, rel_path)` map for D-07 dst resolution.
- **Edge `dst` stored-kind resolution.** A consumer may depend on a workspace member that is an
  `app` rather than a `package`. The retargeted `used_by` and the new `depends_on_package` dst
  must use the target's actual stored kind (mirror `derived_edges.py:148–153`), or the edge will
  dangle.
- **Two same-direction edges are intentional (D-07).** `used_by` (universal "consumer uses X")
  and `depends_on_package` (package-level semantic) both point consumer→internal package. Add a
  brief inline comment so a future reader does not "clean up" the redundancy (Pat's
  self-documenting-code preference).
- **`describe_package` is package-only.** It filters `kind='package'`; the SC#3 example uses
  `describe-package`, so surfacing belongs in `describe_package`. (`describe_app` mirroring is
  out of scope — no SC requires it; left to discretion if trivial, but not required.)

## RESEARCH COMPLETE

All decisions are grounded in concrete code sites. No open questions block planning.
