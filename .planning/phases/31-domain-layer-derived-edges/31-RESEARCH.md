# Phase 31: Domain Layer + Derived Edges — Research

**Date:** 2026-05-25
**Status:** Research complete; ready for planning.

## RESEARCH COMPLETE

CONTEXT.md captured 18 implementation decisions (D-01..D-18) and locks the
shape of every node, edge, file, and the orchestration order. This document
records only what the planner needs that is NOT already in CONTEXT.md —
file-by-file confirmation of the integration surface, the Phase 30
back-port plan for the shared import scanner (D-10), and the ROADMAP.md SC#2
amendment dispatch.

---

## 1. Cross-phase coordination with Phase 30 (D-10 back-port status)

**Phase 30 is currently in `planned` state.** Plans `30-01-PLAN.md`,
`30-02-PLAN.md`, and `30-03-PLAN.md` exist but execute-phase has not run.
The import scan logic for `tests` edges lives inline inside
`_emit_tests_edges` of `30-03-PLAN.md` Task 3 — see lines 632–737:

| Item                            | Location in Phase 30                                  |
|---------------------------------|-------------------------------------------------------|
| `_PYTHON_IMPORT_RE`             | Module-private constant in `test_suites.py`           |
| `_JS_IMPORT_RE`                 | Module-private constant in `test_suites.py`           |
| `py_importable_to_pkg` map      | Built once per `emit()` inside `_emit_tests_edges`    |
| `js_name_to_pkg` map            | Built once per `emit()` inside `_emit_tests_edges`    |
| `_build_pkg_index`              | Module-private helper in `test_suites.py`             |
| Relative JS import resolution   | Inline loop over `cand` extensions in test_suites.py  |
| `_owning_package` consumer      | `structural_nodes._owning_package` (hoisted in 30-01) |

**No `import_scan.py` module exists in Phase 30's plans.** Per D-10, Phase 31
MUST either land the refactor or accept duplicated scanners. Plan-checker will
reject the duplication path (multi-source coverage audit), so the refactor is
mandatory.

**Coordination strategy (locked by D-10):** Phase 31 lands the refactor and
back-ports Phase 30's `test_suites.py` in the SAME PR. Because Phase 30 is in
`planned` state (not yet executed), the back-port is a single edit to the
not-yet-executed module — there is no shipped code to migrate, no test
regression risk, and no merge ordering issue. Phase 30's PLAN.md does not
need to be re-spawned; only `test_suites.py` (which Phase 30 will create) gets
edited by Phase 31's wave.

**Execution order locked by D-16:**

```python
# update.py post-Phase-31:
with store.transaction(conn):
    _process_files(conn, repo_root, changed, skip_dirs)
    packages.refresh(conn, repo_root=repo_root, ctx=ctx)
    if full: ...  # Phase 28
    structural_nodes.emit(conn, ...)          # Phase 29
    entry_points.emit(conn, ...)              # Phase 30
    test_suites.emit(conn, ...)               # Phase 30 — uses import_scan after Phase 31 back-port
    domains.emit(conn, ...)                   # Phase 31 — NEW
    resolve.sweep(conn)
    _enforce_strict_tree_invariant(conn)      # Phase 30
    derived_edges.compute(conn, ...)          # Phase 31 — NEW (last)
    _set_metadata(conn, "last_indexed_commit", head)
    _set_metadata(conn, "last_indexed_at", ...)
```

Phase 30 plan `30-05-PLAN.md` does not exist yet in the directory tree; the
update.run wiring task appears to have been folded into 30-03 or deferred. The
Phase 31 update.run edit lands ON TOP of whatever Phase 30 commits. The
planner must write task `read_first` blocks against the post-Phase-30
expected file contents of update.py.

## 2. ROADMAP.md SC#2 amendment (D-15)

`.planning/ROADMAP.md` line 168 currently reads:

> 2. A `domains.yaml` with a cycle (`payments → billing → payments`) causes
>    `domains.emit` to print a warning identifying the cycle and skip all
>    `domain_contains_domain` edges without crashing — `cg update` exits 0

Required wording per D-15:

> 2. A `domains.yaml` with a cycle (`payments → billing → payments`) causes
>    `domains.emit` to print a warning identifying the cycle and skip ONLY
>    the cycle-participating containment edges (keeping the acyclic
>    remainder) without crashing — `cg update` exits 0

Single edit, single line. This MUST land before any verification reads SC#2.
The planner schedules this as a Wave 0 task on the first plan (lowest plan
number — 31-01) so the edit is committed before Wave 1 begins. The plan
contains the exact line as the `<action>` and the acceptance criterion is a
`grep` for the new wording.

## 3. graph-io existing surface (read-before-edit)

Module                                         | Lines | Phase 31 touchpoint
-----------------------------------------------|-------|----------------------------------------------
`packages/graph-io/src/graph_io/update.py`     | 268   | Add `domains.emit` + `derived_edges.compute` calls inside the `store.transaction` block (D-16)
`packages/graph-io/src/graph_io/uri.py`        | 58    | Update `domain_uri` to take `ctx` per D-05
`packages/graph-io/src/graph_io/upsert.py`     | 88    | No edit — reuse `_upsert_node` / `_upsert_edge`
`packages/graph-io/src/graph_io/resolve.py`    | 58    | No edit — `sweep()` URI-guard from Phase 29 D-16 already protects Domain nodes (they carry `uri`)
`packages/graph-io/src/graph_io/packages.py`   | (n/a) | Read `Package.name` for D-04 validation
`packages/graph-io/src/graph_io/test_suites.py`| TBD   | Refactor import-scan internals into `import_scan.py` (D-10 back-port) — file is Phase 30's deliverable
`packages/graph-io/src/graph_io/structural_nodes.py` | 566 | No direct edit — `_owning_package` and `_resolve_import_root` already exposed at module level after Phase 30 plan 30-01
`packages/graph-io/pyproject.toml`             | 50    | Add `pyyaml>=6.0` to `[project].dependencies` (D-06)

**Current `domain_uri` in uri.py:**
```python
def domain_uri(name: str) -> str:
    return f"domain:{name}"
```
Mismatch with D-05 (`domain:<repo_org>/<repo_name>/<domain_name>`). Phase 31
amends to `def domain_uri(ctx: RepoContext, name: str) -> str:` returning
`f"domain:{ctx.org}/{ctx.repo}/{name}"`. No callers exist yet — confirmed via
grep, the helper was added but not consumed; safe to break the signature.

```
$ grep -rn "domain_uri" packages/graph-io/src/ packages/graph-io/tests/
packages/graph-io/src/graph_io/uri.py:42:def domain_uri(name: str) -> str:
```
Zero callers. Safe to amend signature.

## 4. Cycle detection algorithm (D-15)

**Algorithm choice:** Tarjan's SCC. Single DFS pass, no graph reversal, ~30
LOC iterative implementation. Kosaraju would require two DFS passes plus
graph reversal (twice the code, no benefit).

Reference implementation skeleton (module-private to `domains.py`):

```python
def _detect_cycles(parent_map: dict[str, str]) -> list[set[str]]:
    """Return SCCs of size > 1 from the (child -> parent) graph.

    parent_map: each key is a domain name; each value is its declared parent.
    Returns a list of SCCs (each as a set of domain names). Singleton SCCs
    (the acyclic case) are NOT returned.
    """
    # Build adjacency: parent_map[d] = p means edge d -> p
    nodes = set(parent_map.keys()) | set(parent_map.values())
    adj = {n: [parent_map[n]] for n in parent_map if parent_map.get(n) is not None}
    for n in nodes:
        adj.setdefault(n, [])

    index = {}
    lowlink = {}
    on_stack = set()
    stack = []
    counter = [0]
    sccs: list[set[str]] = []

    def strongconnect(v):
        index[v] = counter[0]
        lowlink[v] = counter[0]
        counter[0] += 1
        stack.append(v)
        on_stack.add(v)
        for w in adj.get(v, []):
            if w not in index:
                strongconnect(w)
                lowlink[v] = min(lowlink[v], lowlink[w])
            elif w in on_stack:
                lowlink[v] = min(lowlink[v], index[w])
        if lowlink[v] == index[v]:
            component = set()
            while True:
                w = stack.pop()
                on_stack.remove(w)
                component.add(w)
                if w == v:
                    break
            if len(component) > 1:
                sccs.append(component)

    for n in nodes:
        if n not in index:
            strongconnect(n)
    return sccs
```

For the use case (parent-pointer graph, <100 domains in practice), recursive
Tarjan is acceptable — Python's default recursion limit (1000) is far above
any realistic domain tree depth. The planner does NOT need to write the
iterative variant.

**Edge-skipping rule (D-15):** For each SCC of size > 1, identify the set of
edges where BOTH endpoints are in the SCC. Do NOT emit `domain_contains_domain`
edges for those pairs. Emit ALL other containment edges (including those
where only one endpoint is in an SCC — i.e., a domain D pointing INTO a cycle
from outside, but D itself is not part of the cycle).

**Singleton self-loop edge case:** `payments.parent = payments` produces an
SCC of size 1 that IS a cycle. Tarjan as written returns `len(component) > 1`
SCCs only. Handle separately: any domain whose `parent` equals its own name is
a self-loop — log a warning, skip the edge, still emit the Domain node.

## 5. YAML parsing strategy (D-06)

PyYAML 6.0+ ships in `workspace-io` already; add to `graph-io` dependencies.

**Parse contract:**

```python
import yaml

def _load_domains_yaml(repo_root: Path) -> dict | None:
    """Return parsed domains.yaml content, or None if missing.

    Raises ValueError on parse error (caller catches and exits 4).
    """
    path = repo_root / "domains.yaml"
    if not path.exists():
        return None
    try:
        with path.open("r", encoding="utf-8") as f:
            data = yaml.safe_load(f) or {}
    except yaml.YAMLError as exc:
        raise ValueError(f"domains.yaml: YAML parse error: {exc}") from exc
    if not isinstance(data, dict):
        raise ValueError(
            f"domains.yaml: top-level must be a mapping, got {type(data).__name__}"
        )
    return data
```

**Per-domain validation:** Inside `domains.emit`:

```python
KNOWN_KEYS = {"packages", "parent", "description", "owner"}

for dom_name, dom_attrs in data.items():
    if not isinstance(dom_attrs, dict):
        log.warning(
            "domains.yaml: domain '%s' must be a mapping, got %s — skipping",
            dom_name, type(dom_attrs).__name__,
        )
        continue
    pkgs = dom_attrs.get("packages")
    if pkgs is None:
        log.warning("domains.yaml: domain '%s' missing required 'packages:' field — skipping", dom_name)
        continue
    if not isinstance(pkgs, list):
        log.warning("domains.yaml: domain '%s' has non-list 'packages:' field — skipping", dom_name)
        continue
    unknown = set(dom_attrs.keys()) - KNOWN_KEYS
    for key in sorted(unknown):
        log.warning("domains.yaml: domain '%s' has unknown key '%s' — ignored", dom_name, key)
    # ... emit Domain node, belongs_to_domain edges, queue parent edge ...
```

Per D-04, unknown PACKAGE names (not unknown keys) print a warning with the
full alphabetised list of known packages. Use a single SELECT against the
`packages` table at the top of `emit()`.

## 6. `references` / `depends_on` / `TestSuite → Domain` derivation strategy

CONTEXT.md `<specifics>` ships the pseudocode for both single-traversal
compute (`_compute_references_and_depends_on`) and the `TestSuite → Domain`
compute (`_compute_testsuite_domain`). The planner can lift the pseudocode
verbatim into the plan's `<action>` block.

**Single transaction (D-17):**

```python
def compute(conn, ctx) -> None:
    with conn:  # atomic — implicit commit on success, rollback on exception
        conn.execute("DELETE FROM edges WHERE kind IN ('references', 'depends_on')")
        conn.execute(
            "DELETE FROM edges WHERE kind='tests' AND dst IN "
            "(SELECT id FROM nodes WHERE kind='domain')"
        )
        _compute_references_and_depends_on(conn, ctx)
        _compute_testsuite_domain(conn, ctx)
```

NOTE: CONTEXT.md D-17 pseudocode uses `child_id`; the actual schema column is
`dst`. The planner must use `dst`, not `child_id`. Cross-checked against
`upsert.py` line 77 — schema is `edges(src, dst, kind, attrs_json)`.

**Shared import scan call sites (D-10):**

```python
# packages/graph-io/src/graph_io/import_scan.py
def scan_package_imports(
    conn,
    repo_root: Path,
    pkg_name: str,
    pkg_rel: str | None,
    *,
    include_test_files: bool = False,
) -> set[tuple[str, str | None]]:
    """Return distinct (pkg_name, pkg_rel) tuples for first-party packages
    imported by files inside `pkg_name`. include_test_files toggles whether
    File rows with is_test=true participate in the scan."""
```

The function takes a `conn`, queries `File` rows scoped to the Package
(`path LIKE '<pkg_rel>/%'`), filters on `is_test` per the kwarg, reads file
contents from disk, runs the same `_PYTHON_IMPORT_RE` / `_JS_IMPORT_RE`
regexes Phase 30 specifies, and returns the resolved Package set.

Phase 30's `test_suites._emit_tests_edges` becomes a thin wrapper that calls
`import_scan.scan_package_imports` per file (or per suite — the function may
need a per-file variant; the planner decides).

## 7. Test fixture strategy

Phase 29's `tests/fixtures/sample_monorepo/` ships with `packages/mypkg/`,
`packages/jspkg/`, and `tests/integration/`. Phase 30 extends it. Phase 31
adds a `domains.yaml` to the SAME fixture root:

```yaml
# tests/fixtures/sample_monorepo/domains.yaml
core:
  packages: [mypkg]
  description: "Core domain"
web:
  packages: [jspkg]
  parent: presentation
presentation:
  packages: []
  description: "Top-level UI"
```

Plus a SECOND fixture directory with a cycle for SC#2 testing:

```
tests/fixtures/sample_monorepo_cycle/
  └── domains.yaml         # payments.parent = billing; billing.parent = payments
  └── (otherwise identical to sample_monorepo)
```

The simplest path is to copy `sample_monorepo` into `sample_monorepo_cycle`
(or use a fixture-builder that lays out the files programmatically in
`tmp_path`). Phase 29 / Phase 30 tests use the on-disk `sample_monorepo`
directly; following that convention, Phase 31 adds a sibling directory.

Alternative: use `tmp_path` + `shutil.copytree(sample_monorepo, tmp_path)` +
overwrite `domains.yaml` with cycle content. This keeps the on-disk fixture
small and avoids duplicating package source. Recommended for the cycle test.

## 8. Test coverage targets

Per CONTEXT.md `<specifics>` D-15 prototypes plus SC#1..5:

| Test                                                    | Source SC / D  |
|---------------------------------------------------------|----------------|
| Missing `domains.yaml` → zero Domain nodes, exit 0      | SC#1, DOMAIN-04|
| Valid `domains.yaml` → Domain node count + belongs_to_domain count match | SC#1, DOMAIN-01, DOMAIN-02 |
| Multi-domain membership: package in 2 domains → 2 edges | D-02, DOMAIN-02|
| Cycle of length 2 → warning, acyclic remainder preserved| SC#2, DOMAIN-03|
| Cycle of length 3 → warning, only intra-SCC edges skipped| SC#2, DOMAIN-03|
| Self-loop (parent = self) → warning, edge skipped, node emitted | DOMAIN-03 |
| Orphan parent (points at non-existent domain) → warning, containment edge skipped, Domain node still emitted | D-15 derivation |
| Unknown package name → warning with sorted known-package list | SC#4, D-04 |
| Missing required `packages:` field → warning, domain skipped, no crash | D-06 derivation |
| Non-list `packages:` → warning, domain skipped | D-06 derivation |
| Unknown top-level key → warning, key ignored, domain still emitted | D-01 |
| `references` count > 0 after cross-domain imports       | SC#3, DERIVED-01|
| `depends_on` count > 0 after cross-domain imports       | SC#3, DERIVED-02|
| Idempotency: `cg update` twice → no duplicate derived edges | SC#3, DERIVED-03, D-17 |
| `tests` (TestSuite → Domain) emitted when all suite's packages are in one Domain | D-12 |
| `tests` (TestSuite → Domain) NOT emitted when suite spans multiple Domains | D-13 |
| `tests` (TestSuite → Domain) NOT emitted for single-Package suites | D-12 |
| YAML parse error → exit 4 with clear message            | D-06 |
| `tests/billing/` at root (no domains.yaml) → no Domain('billing') node | SC#5 (convention-inference anti-test) |
| `import_scan.scan_package_imports` with `include_test_files=True` returns test imports | D-10 contract |
| `import_scan.scan_package_imports` with `include_test_files=False` excludes test imports | D-11 |

Tests live under `packages/graph-io/tests/`. New files: `test_domains.py`,
`test_derived_edges.py`, `test_import_scan.py`. Existing
`test_test_suites.py` (Phase 30 deliverable) gets two new tests asserting the
shared helper is used.

## 9. Validation Architecture (Nyquist Dimension 8)

For Nyquist-style validation:

- **Behavioral validation:** Each SC#1–5 has a dedicated test that asserts
  the user-visible behavior (exit code, edge count, warning text). Tests live
  in `tests/test_domains.py` and `tests/test_derived_edges.py`.
- **Structural validation:** Each new edge kind (`references`, `depends_on`,
  `belongs_to_domain`, `domain_contains_domain`, `tests` Domain-targeted) has
  an SQL-level assertion against schema (`edges` table with expected `kind`
  values and `attrs_json` shape).
- **Property validation:** Idempotency (SC#3) is asserted by running
  `derived_edges.compute` twice in the same test and snapshotting the
  `edges` rows.
- **Boundary validation:** Cycle detection (SC#2), zero-domain mode
  (DOMAIN-04), self-loop, orphan parent, unknown keys, unknown packages —
  each is a boundary case with a dedicated test.
- **Regression validation:** Phase 29 / Phase 30 tests must continue to pass.
  The back-port edit to `test_suites.py` is the highest regression risk;
  Plan 31-02 (the refactor) runs the existing `test_test_suites.py` suite as
  its acceptance gate.

## 10. Open questions for the planner

1. **Should Phase 31 land a thin `cg list-domains` shim?** D-Claude's
   Discretion in CONTEXT.md. Recommendation: NO — SC#1's `cg list-domains`
   verification can be done via raw SQL in the test (`SELECT * FROM nodes
   WHERE kind='domain'`). The CLI surface is fully Phase 33's territory.
   This keeps Phase 31 scope minimal.

2. **Does the back-port refactor edit Phase 30's plan files?** NO. Phase 30
   plans stay as written; only the (not-yet-executed) `test_suites.py`
   module is edited by Phase 31's Wave 1 plan. When execute-phase runs
   Phase 30, it creates `test_suites.py` per the inline pseudocode; Phase 31
   then refactors that module to call `import_scan.scan_package_imports`.
   No PLAN.md churn.

3. **Order of Wave 0 / Wave 1 / Wave 2:** The locked structure is:
   - **Wave 0**: ROADMAP.md SC#2 amendment + pyproject.toml PyYAML dep + uri.py `domain_uri` signature update (single small plan, all prerequisite single-file edits).
   - **Wave 1**: Either `import_scan.py` extraction + back-port OR `domains.emit` — they have no inter-dependency. Run in parallel as two separate plans.
   - **Wave 2**: `derived_edges.compute` (depends on `import_scan.py` AND `domains.emit`) + `update.run` wiring + fixture additions + tests.

   Recommend collapsing tests into the implementation plans (TDD-style) rather than a separate test plan — each plan ships with its own test file.

## 11. Risk summary

| Risk                                                        | Severity | Mitigation                                       |
|-------------------------------------------------------------|----------|--------------------------------------------------|
| Phase 30 execute-phase runs concurrently with Phase 31 plan | LOW      | Phase 31's update.run edit checks file shape; back-port edit is conditional on Phase 30 file existing |
| `domain_uri` signature change breaks future callers         | NONE     | Zero callers exist today (grep verified §3)      |
| Tarjan recursion depth on degenerate domain tree            | LOW      | Realistic max depth ~5; Python default limit 1000 |
| YAML parse exit 4 collides with Phase 28 exit code          | NONE     | Phase 28 exit 4 is schema-mismatch; same code is semantically "user fixable config error" — intentional reuse |
| Back-port edit breaks Phase 30 test suite                   | MEDIUM   | Plan 31-02 includes full `test_test_suites.py` run as acceptance gate; matching public behavior is the contract |
| `cg update` second-run idempotency fails on derived edges   | LOW      | D-17 delete-then-recompute pattern is unconditionally idempotent |
| Multi-domain suite incorrectly emits Domain edge            | LOW      | D-13 anti-test in test_derived_edges.py          |
| Orphan parent crashes Tarjan                                | NONE     | `parent_map` only contains domains with declared parents; orphan parents are filtered at parse time |

## 12. Files-modified summary (orientation for the planner)

| Plan slot         | Files                                                                                            |
|-------------------|--------------------------------------------------------------------------------------------------|
| 31-01 (Wave 0)    | `.planning/ROADMAP.md`, `packages/graph-io/pyproject.toml`, `packages/graph-io/src/graph_io/uri.py` |
| 31-02 (Wave 1)    | `packages/graph-io/src/graph_io/import_scan.py` (NEW), `packages/graph-io/src/graph_io/test_suites.py` (back-port), `packages/graph-io/tests/test_import_scan.py` (NEW) |
| 31-03 (Wave 1)    | `packages/graph-io/src/graph_io/domains.py` (NEW), `packages/graph-io/tests/test_domains.py` (NEW), `packages/graph-io/tests/fixtures/sample_monorepo/domains.yaml` (NEW) |
| 31-04 (Wave 2)    | `packages/graph-io/src/graph_io/derived_edges.py` (NEW), `packages/graph-io/src/graph_io/update.py` (edit), `packages/graph-io/tests/test_derived_edges.py` (NEW), test fixture extension |

Four plans, two waves (plus Wave 0 single-file housekeeping). Total LOC
estimate: ~600 new (`domains.py` ~150, `derived_edges.py` ~150,
`import_scan.py` ~80, tests ~200, fixture YAML <30).
