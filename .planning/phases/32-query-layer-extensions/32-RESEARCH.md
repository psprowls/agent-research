# Phase 32: Query Layer Extensions — Research

**Date:** 2026-05-25
**Status:** Research complete; ready for planning.

## RESEARCH COMPLETE

CONTEXT.md captured 19 implementation decisions (D-01..D-19). This document
records only what the planner needs that is NOT already in CONTEXT.md —
a definitive correction of the schema/casing assumptions, file-by-file
landing surfaces, the cross-phase ordering with Phase 31, the test fixture
audit result, and the Nyquist validation strategy.

---

## 1. CRITICAL CORRECTION — schema column names and node-kind casing

CONTEXT.md `<specifics>` shows SQL drafts (D-07, D-09 UNION, D-12) that use
two shapes which **do not match the live schema or the emitter output**:

| CONTEXT.md draft       | Actual shape (from `schema.py` + emitters)        |
|------------------------|---------------------------------------------------|
| `edges.parent_id`      | `edges.src`                                       |
| `edges.child_id`       | `edges.dst`                                       |
| `kind = 'Domain'`      | `kind = 'domain'`                                 |
| `kind = 'Package'`     | `kind = 'package'`                                |
| `kind = 'TestSuite'`   | `kind = 'test_suite'`                             |
| `kind = 'EntryPoint'`  | `kind = 'entry_point'`                            |
| `kind = 'Repository'`  | `kind = 'repository'`                             |
| `kind = 'File'`        | `kind = 'file'`                                   |
| `kind = 'SubPackage'`  | `kind = 'subpackage'`                             |

The lowercase form is **load-bearing**. Phase 29 `structural_nodes.py`
line 286 writes `kind="repository"`, line 414 writes `kind="subpackage"`,
line 527 writes `kind="file"`. Phase 30 plans write `kind="test_suite"`
and `kind="entry_point"`. Phase 31 plans write `kind="domain"` and the
edge kinds `belongs_to_domain`, `domain_contains_domain`, `references`,
`depends_on`, `tests`.

CONTEXT.md D-19 lists the `find` allow-list with capitalised kinds — those
MUST be lowercase in the implementation. CONTEXT.md D-07 / D-09 SQL drafts
MUST be transliterated to `src`/`dst` with lowercase kinds before they
ship.

**Verification:** `packages/graph-io/src/graph_io/schema.py` lines 14–46.
**Live cross-check:** `packages/graph-io/src/graph_io/queries.py` line 9 —
the existing `_RESOLVED_FILTER` constant uses `e.attrs_json` (lowercase
column) consistent with this shape.

CONTEXT.md remains the design source of truth. Phase 32 implementations
must reflect the lowercase / `src`/`dst` reality in actual SQL. This
research note is the place where that translation is recorded.

---

## 2. Phase 31 emit-side dependency surface

Phase 32 helpers query the post-Phase-31 graph. Phase 31 is in active
planning (per Phase 32 CONTEXT.md header note); its CONTEXT.md decisions
are stable enough to plan against. The Phase 32 query layer reads:

| Node kind         | Emitted by              | Attrs Phase 32 reads                                     |
|-------------------|-------------------------|----------------------------------------------------------|
| `repository`      | Phase 29 (`structural_nodes.emit`) | `uri`, `owner`, `url`, `default_branch`     |
| `package`         | Phase 27 `packages.emit` | `uri`, `language`, `version`                            |
| `subpackage`      | Phase 29 `structural_nodes.emit` | `uri`                                            |
| `file`            | Phase 29 `structural_nodes.emit` | 7 role flags (D-05), `uri`, `language`           |
| `entry_point`     | Phase 30 `entry_points.emit` | `uri`, `kind`, `callable`, `source`, `is_wildcard` (P30 D-07/D-08) |
| `test_suite`      | Phase 30 `test_suites.emit` | `uri`, `suite_kind`                                  |
| `domain`          | Phase 31 `domains.emit` | `uri`, `description`, `owner`                            |

| Edge kind                | Emitted by              | Attrs Phase 32 reads                  |
|--------------------------|-------------------------|---------------------------------------|
| `physically_contains`    | Phase 29                | (none beyond resolution)              |
| `contains`               | Phase 27/older          | (none)                                |
| `imports`                | source-parser           | resolution                            |
| `calls`                  | source-parser           | resolution                            |
| `exports`                | source-parser           | resolution                            |
| `declares_entry_point`   | Phase 30                | (none)                                |
| `implemented_by`         | Phase 30                | (none)                                |
| `tests` (TestSuite→Package)| Phase 30              | (none)                                |
| `tests` (TestSuite→Domain) | Phase 31 derived      | (none — single-domain only per P31 D-12) |
| `belongs_to_domain`      | Phase 31 (Package→Domain)| (none)                                |
| `domain_contains_domain` | Phase 31                | (none — acyclic per P31 D-15)         |
| `references`             | Phase 31 derived        | `usage_count` (Phase 31 D-18, in attrs_json) |
| `depends_on`             | Phase 31 derived        | `usage_count` (Phase 31 D-18, in attrs_json) |

### Test execution gating (carry-over from manager notes)

Phase 32 plans can be **written** from Phase 31 CONTEXT.md alone. Phase 32
tests cannot **run green** until Phase 31 ships — specifically, the
session-scoped `seeded_db` fixture (D-14) runs `cg update --full` which
invokes `domains.emit` and `derived_edges.compute`. Plans MUST surface
this in the `must_haves.truths` block so reviewers know SC#4 is gated on
Phase 31 ship date.

---

## 3. Fixture audit — `tests/fixtures/sample_monorepo/`

Filesystem inspection on 2026-05-25 yielded:

| File                                              | Present | Phase that ships it           |
|---------------------------------------------------|---------|-------------------------------|
| `pyproject.toml` (root)                           | yes     | Phase 27/29                   |
| `packages/mypkg/pyproject.toml`                   | yes     | Phase 27/29                   |
| `packages/mypkg/tests/test_foo.py`                | yes     | Phase 29/30                   |
| `packages/mypkg/scripts/run.sh`                   | yes     | Phase 29 (anti-test surface)  |
| `packages/jspkg/package.json`                     | yes     | Phase 29/30                   |
| `packages/jspkg/index.js`                         | yes     | Phase 29/30                   |
| `packages/jspkg/types.d.ts`                       | yes     | Phase 29 (is_type_only)       |
| `packages/jspkg/gen/data.gen.ts`                  | yes     | Phase 29 (is_generated)       |
| `tests/integration/test_top.py`                   | yes     | Phase 29/30 (multi-pkg suite) |
| `domains.yaml`                                    | **MISSING** — Phase 31 will land it | Phase 31 D-03 |

Mapped against CONTEXT.md D-15 checklist:

- [ ] ≥2 Domains with parent-child (e.g. `financial → billing`) — **TODO**, depends on Phase 31's `domains.yaml`
- [ ] ≥1 cross-cutting Package (zero `belongs_to_domain` edges, referenced from multiple domains) — **TODO**, depends on Phase 31 `domains.yaml` + derived `references`
- [ ] ≥1 EntryPoint with non-NULL `callable` — likely present once Phase 30 runs (mypkg/pyproject.toml `[project.scripts]` — needs `cg update --full` verification)
- [ ] ≥1 wildcard `exports` EntryPoint (is_wildcard=true) — Phase 30 plans add `package.json.exports` walking; need to verify `jspkg/package.json` declares an `exports` block with `*`
- [ ] ≥1 single-domain TestSuite (Phase 31 D-12 direct edge) — depends on `domains.yaml` membership
- [ ] ≥1 multi-domain TestSuite (Phase 31 D-13 inferred edge) — depends on `domains.yaml`

**Planning consequence:** Phase 32 plans MUST include a Wave 0 task that
audits the fixture after Phase 31 ships and back-fills any missing
domains / packages / suites needed for the D-15 checklist. The task can
be a no-op if Phase 31's planner already added them. The audit is
mechanical: run `cg update --full` against a tmp copy, then run six
`SELECT COUNT(*)` queries from the checklist and assert each is ≥ the
required count.

---

## 4. Helper landing surface — file-by-file

All new helpers land in
`packages/graph-io/src/graph_io/queries.py` alongside the existing
`find`, `describe_package`, `describe_path`, `callers`, `callees`,
`imports`, `imported_by`, `exports`, `exported_by` helpers.

### 4.1. Dataclass additions (top of queries.py, near existing
`PackageDescription` / `PathDescription` / `NodeRecord` definitions):

```python
@dataclass(frozen=True)
class RepoDescription:
    name: str
    uri: str
    owner: str | None
    url: str | None
    default_branch: str | None
    package_count: int


@dataclass(frozen=True)
class DomainDescription:
    name: str
    uri: str
    parent: str | None
    description: str | None


@dataclass(frozen=True)
class EntryPointDescription:
    name: str
    uri: str
    kind: str                       # "executable" | "library"
    callable: str | None
    implemented_by_path: str | None
    source: str                     # "pyproject.scripts" | ... see P30 D-07/D-08


@dataclass(frozen=True)
class SuiteDescription:
    name: str
    uri: str
    kind: str                       # suite_kind from P30 (unit | integration | e2e)
    file_count: int
```

### 4.2. Extension to `PackageDescription` (in-place, D-01):

```python
@dataclass(frozen=True)
class PackageDescription:
    name: str
    language: str
    version: str
    files: list[str]
    counts: dict[str, int]
    domains: list[str] = field(default_factory=list)                            # NEW
    entry_points: list[EntryPointDescription] = field(default_factory=list)    # NEW
    test_suites: list[SuiteDescription] = field(default_factory=list)          # NEW
```

`from dataclasses import dataclass, field` import line is added at the top
of queries.py (currently `from dataclasses import dataclass`).

### 4.3. Extension to `PathDescription` (in-place, D-05):

```python
@dataclass(frozen=True)
class PathDescription:
    path: str
    children: list[NodeRecord]
    imports: list[NodeRecord]
    role_flags: dict[str, bool] | None = None     # NEW
```

`role_flags` is `None` for non-File resolved nodes (Repository / Package /
SubPackage / Domain), else exactly 7 keys: `is_importable`, `has_main`,
`is_test`, `is_config`, `is_generated`, `is_type_only`, `is_executable`.

### 4.4. `find` signature extension (D-19):

Add allow-list of lowercase kinds. The current signature is unchanged
externally — the validation is internal:

```python
_VALID_KINDS = frozenset({
    "function", "class", "method", "file",
    "package", "repository", "subpackage",
    "entry_point", "test_suite", "domain",
})

def find(conn, *, name=None, kind=None):
    if kind is not None and kind not in _VALID_KINDS:
        raise ValueError(f"unknown kind {kind!r}; valid: {sorted(_VALID_KINDS)}")
    ...
```

Note: existing `find` requires `name`; QUERY-01 SC#1 calls `cg find --kind
repository` with no `--name`. The signature MUST be amended to accept
`name=None` (returning all rows matching `kind`). The existing logic
branches on `kind is None`; the new branch is `name is None`. Add a single
new branch and document the no-`name` semantics.

### 4.5. The 16 new helpers — signatures only (full SQL in PLAN.md):

```python
def describe_repository(conn) -> RepoDescription | None: ...
def describe_domain(conn, name: str) -> DomainDescription | None: ...
def describe_entry_point(conn, package_name: str, entry_name: str) -> EntryPointDescription | None: ...
def describe_test_suite(conn, suite_name: str) -> SuiteDescription | None: ...

def list_repositories(conn) -> list[NodeRecord]: ...
def list_packages(conn) -> list[NodeRecord]: ...
def list_entry_points(conn) -> list[NodeRecord]: ...
def list_test_suites(conn) -> list[NodeRecord]: ...
def list_domains(conn) -> list[NodeRecord]: ...
def list_scripts(conn) -> list[NodeRecord]: ...

def entry_points_for_package(conn, package_name: str) -> list[EntryPointDescription]: ...
def tests_for_package(conn, package_name: str) -> list[SuiteDescription]: ...

def tests_for_domain(conn, domain_name: str) -> list[SuiteDescription]: ...
def domain_references(conn, domain_name: str) -> list[tuple[str, int, int]]: ...  # (pkg_name, total_usage_count, distinct_domain_count)
def domain_depends_on(conn, domain_name: str) -> list[tuple[str, int]]: ...        # (domain_name, total_usage_count)
def cross_cutting_packages(conn) -> list[tuple[PackageDescription, int]]: ...      # (pkg_desc, score)
```

Counted: 4 `describe_*`, 6 `list_*`, 2 `*_for_package`, 4 domain helpers =
**16 helpers**. Matches CONTEXT.md `<domain>` paragraph 4.

### 4.6. Module-private SQL constant (D-07 reuse pattern):

A single new module-private constant `_DOMAIN_DESCENDANTS_CTE` (string
fragment) is shared by `tests_for_domain`, `domain_references`,
`domain_depends_on`. The CTE is inlined into each of the three helpers'
SQL with string formatting; the constant just holds the canonical text so
the three callers stay identical. Pattern matches the existing
`_RESOLVED_FILTER` constant at line 9 of queries.py.

### 4.7. Tests land in `packages/graph-io/tests/test_queries.py`.

The file already exists (per the directory listing). New tests are added
alongside the existing ones. The new `seeded_db` session-scoped fixture
lands in `packages/graph-io/tests/conftest.py` (also already exists per
the directory listing). Targeted-edge-case fixtures use raw
`_upsert_node` / `_upsert_edge` inserts inside individual test functions
— no shared fixture for them (D-13 hybrid).

---

## 5. The 9 SC#4 helpers vs the 16 total helpers

ROADMAP.md SC#4 names **9** helpers explicitly:

`describe_repository`, `describe_domain`, `list_entry_points`,
`list_suites`, `describe_suite`, `what_tests`, `domain_refs`,
`domain_deps`, `cross_cutting_packages`.

These map to **CONTEXT.md naming** (the source of truth):

| SC#4 name (ROADMAP)        | Helper name (CONTEXT.md)          |
|----------------------------|-----------------------------------|
| `describe_repository`      | `describe_repository`             |
| `describe_domain`          | `describe_domain`                 |
| `list_entry_points`        | `list_entry_points`               |
| `list_suites`              | `list_test_suites`                |
| `describe_suite`           | `describe_test_suite`             |
| `what_tests`               | `tests_for_package` (the "what tests this package" query) |
| `domain_refs`              | `domain_references`               |
| `domain_deps`              | `domain_depends_on`               |
| `cross_cutting_packages`   | `cross_cutting_packages`          |

CONTEXT.md names win (they are spec-aligned). ROADMAP.md SC#4 wording
slightly disagrees in 3 places (`list_suites` vs `list_test_suites`,
`describe_suite` vs `describe_test_suite`, `what_tests` vs
`tests_for_package`) — these are **naming-only differences**, not scope
differences. The planner SHOULD use CONTEXT.md names in the
implementation and reference both names in test docstrings so a future
reader looking up SC#4 by name finds the right function.

The remaining 7 helpers (`describe_entry_point`,
`list_repositories`, `list_packages`, `list_domains`, `list_scripts`,
`entry_points_for_package`, `tests_for_domain`) are required by QUERY-04
(CONTEXT.md `<domain>` paragraph 4 lists all 16) but not explicitly named
in SC#4. They must still be implemented to satisfy QUERY-04. Their unit
tests are part of the same test module.

---

## 6. Wave decomposition strategy

Phase 32 has natural three-wave structure:

- **Wave 0**: dataclass extensions + `find` allow-list (no DB reads, no
  cross-helper deps; everything else depends on the new types being
  importable). Also includes fixture audit (post-Phase-31). Single plan,
  small.

- **Wave 1**: per-kind `describe_*` and `list_*` helpers (parallel-safe;
  no helper depends on another in this wave). The four `describe_*`
  helpers and the six `list_*` helpers are independent. Also includes
  `describe_package` and `describe_path` extensions (independent of the
  new helpers). Single plan, medium-sized.

- **Wave 2**: bubble-up CTE helpers + `cross_cutting_packages` +
  `tests_for_package` + `entry_points_for_package`. These compose existing
  Wave 1 helpers and use the recursive CTE. They are the bulk of the
  testing surface. Single plan, large.

Three-plan decomposition keeps each plan in the 8–15 task range. A 2-plan
(merge Wave 1 + Wave 2) or 4-plan (split Wave 1 by describe vs list)
decomposition is also viable; the planner picks based on per-plan
context-budget feel. CONTEXT.md does not mandate the split.

The cross-cutting test_queries.py file lives across all waves — each plan
appends its own test functions; no plan rewrites the file from scratch.
The `seeded_db` conftest fixture lands in Wave 0 because all Wave 1+
tests use it.

---

## 7. Read-only connection enforcement (D-16)

Every helper signature is `helper(conn, ...)`. The conftest fixture opens
the connection with `mode=ro`:

```python
sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)
```

This is the existing queries.py pattern. The Phase 32 helpers MUST NOT
issue any INSERT / UPDATE / DELETE / CREATE / DROP statements. Enforcement
is by code review only — no runtime check (per D-16). Targeted-edge-case
fixtures that use `_upsert_node` / `_upsert_edge` open a **separate**
read-write connection just for the seed insertion, then re-open in `ro`
mode for the helper call. This is the pattern Phase 29/30 test suites
already use.

---

## 8. cross_cutting_packages — D-11 spec divergence

CONTEXT.md D-11 explicitly states: ranking is by **SUM(usage_count)**,
not by **COUNT(DISTINCT domain)**. The ontology spec §11.4 reads
"ranked by incoming references count from distinct domains" — the user
chose "how heavily depended on" over "how broadly depended on" at
context-gathering time.

This is a **query-layer rendering choice**, NOT a spec amendment. Phase
32 must NOT edit `.planning/research/ONTOLOGY-SPEC.md`. The divergence
is noted in CONTEXT.md `<decisions>` D-11 and recorded again here for
the planner.

Both numbers are computable from the same SQL — the planner may include
the distinct-domain count as a third column in the return shape (D-12
specifies `list[tuple[PackageDescription, int]]`; that's 2-tuple already
— if the third metric is wanted, change to 3-tuple). Recommendation:
return the 2-tuple per D-12, store the rank metric only. A future flag
can switch metrics without a signature break (add `metric='usage' |
'distinct_domains'` kwarg).

---

## 9. Validation Architecture (Nyquist Dimension 8)

Phase 32 ships a read-only query API. The dimensions that matter:

### 9.1. Schema validation (D-01, D-05, D-19)
- Dataclass field types match the schema exactly: `domains: list[str]` is
  a list of domain names (not URIs, not Description objects); `role_flags
  : dict[str, bool] | None` has exactly 7 keys when populated.
- Verified by: type-level assertions in unit tests, plus a single
  parameterised test that walks every helper's return type and asserts
  the field set is exactly the declared set.

### 9.2. Backwards compatibility validation (D-01)
- All pre-v1.6 callers of `describe_package` get empty lists for the new
  fields (default_factory=list). No exception, no key error.
- Verified by: a regression test that constructs a graph with NO
  domains.yaml and NO Phase 30/31 emitters run, then calls
  `describe_package` and asserts the new fields are empty lists.

### 9.3. Semantic correctness validation (D-06, D-07, D-08, D-09)
- The CTE walks `domain_contains_domain` in the correct direction
  (parent → child via `src → dst`).
- `tests_for_domain` UNION returns each suite exactly once when the suite
  matches both the direct edge and the indirect Package join branches.
- `cross_cutting_packages` ranking is stable under ties (ORDER BY score
  DESC, name ASC).
- Verified by: targeted-edge-case fixtures with hand-crafted DBs.

### 9.4. Cycle protection (D-07, Phase 31 D-15)
- CTE termination is guaranteed by Phase 31's acyclic invariant. Phase 32
  test SHOULD include a paranoid cycle test: insert a manual
  `domain_contains_domain` cycle via `_upsert_edge` (bypassing Phase 31's
  invariant), call `tests_for_domain`, assert the query terminates within
  a wall-clock timeout (e.g. 5 seconds) and returns SOMETHING (not an
  infinite-loop hang). This is a defence-in-depth test against future
  emitter bugs.

### 9.5. Empty-DB validation
- Every helper returns `None` (for `describe_*`) or `[]` (for `list_*`
  and the bubble-up helpers) on an empty DB. No KeyError, no
  IndexError, no IntegrityError. This is the "graceful degradation"
  contract from D-03.

### 9.6. Per-kind exhaustiveness (D-19)
- `find(kind=k)` returns results for k in each of the 10 kinds, raises
  ValueError for unknown kinds. Parameterised test.

### 9.7. Cross-emitter integration validation (SC#1, SC#2, SC#3)
- Three `cg`-CLI-like surrogate tests (no actual CLI — Phase 33 ships the
  CLI; these are Python-call-level surrogates):
  - SC#1 surrogate: call `find(conn, kind=k)` for each new kind, assert
    non-empty result against `seeded_db`.
  - SC#2 surrogate: call `describe_package(conn, name='mypkg')` against
    `seeded_db`, assert `domains`, `entry_points`, `test_suites` fields
    are populated (not just present-with-empty-default).
  - SC#3 surrogate: call `describe_path(conn,
    path='packages/mypkg/src/...')` against `seeded_db`, assert
    `role_flags` is a dict with exactly the 7 keys.

### 9.8. Read-only enforcement (D-16)
- Single negative test: open the seeded_db conn in `ro` mode, call each
  new helper, assert no `sqlite3.OperationalError` is raised. (Helpers
  that accidentally include a write would error against the ro conn.)

---

## 10. Open questions / planner discretion

All resolved in CONTEXT.md `<decisions>` `### Claude's Discretion`. No
additional ambiguities surfaced during research.

The planner has discretion on:
- Whether to inline the recursive CTE in each of the 3 bubble-up
  helpers, or extract to a `_DOMAIN_DESCENDANTS_CTE` constant +
  string-format. **Recommendation: extract to constant** — three
  callers is exactly the threshold where DRY pays off.
- `list_scripts` deduplication strategy (UNION ALL + dedup-by-node-id
  vs explicit annotation). **Recommendation: UNION DISTINCT** — simpler
  shape, Phase 33 SC#4 confirms this is the expected behavior.
- Test fixture choice per assertion (session-scoped seeded_db vs
  targeted per-test). **Recommendation:** seeded_db for "happy path
  observable shape" tests; targeted for empty-DB, cycle, single-domain,
  zero-domain edge cases.

---

## Validation Architecture (Nyquist Dimension 8)

The validation surface for Phase 32 is the set of unit tests under
`packages/graph-io/tests/test_queries.py`, exercising every public helper
against (a) the session-scoped seeded `sample_monorepo` fixture and (b)
targeted edge-case fixtures (empty DB, cycle, single-domain,
zero-domain).

**Coverage matrix:**

| Helper                       | Happy-path test | Empty-DB test | Edge-case test                                |
|------------------------------|-----------------|---------------|-----------------------------------------------|
| `find` (extended)            | per-kind        | yes           | unknown-kind ValueError                       |
| `describe_package` (extended)| `mypkg`         | yes           | package with no domain (cross-cutting)        |
| `describe_path` (extended)   | a File path     | yes           | non-File path (Repository / Package)          |
| `describe_repository`        | yes             | None          | —                                             |
| `describe_domain`            | `billing`       | None          | unknown name                                  |
| `describe_entry_point`       | `mypkg:cli`     | None          | unknown package, unknown name                 |
| `describe_test_suite`        | `test_top`      | None          | unknown name                                  |
| `list_repositories`          | yes             | `[]`          | —                                             |
| `list_packages`              | yes             | `[]`          | —                                             |
| `list_entry_points`          | yes             | `[]`          | —                                             |
| `list_test_suites`           | yes             | `[]`          | —                                             |
| `list_domains`               | yes             | `[]`          | —                                             |
| `list_scripts`               | yes             | `[]`          | EntryPoint + is_executable file dedup         |
| `entry_points_for_package`   | `mypkg`         | `[]`          | package with no entry points                  |
| `tests_for_package`          | `mypkg`         | `[]`          | package with no tests                         |
| `tests_for_domain`           | `billing`       | `[]`          | both direct + inferred branches, cycle-safety |
| `domain_references`          | `financial`     | `[]`          | parent domain bubbles up child references     |
| `domain_depends_on`          | `financial`     | `[]`          | self-loop excluded                            |
| `cross_cutting_packages`     | yes             | `[]`          | ranking stability (tie-break alphabetical)    |

Each row maps to at least one test function. Total test count: ≈30
(some rows have 2–3 tests).

**Test execution gate:** Tests run under `uv run --package graph-io
pytest packages/graph-io/tests/test_queries.py -v`. The session-scoped
seeded_db fixture runs `cg update --full` once; subsequent test invocations
reuse the same SQLite file under `mode=ro`. Total wall-clock budget for
the whole test module: ≤30 s on a developer laptop (the only expensive
operation is the one-time `cg update --full`).

**Cross-phase dependency:** Tests can be **WRITTEN** from Phase 31
CONTEXT.md alone, but can only **PASS GREEN** after Phase 31's emitters
(`domains.emit`, `derived_edges.compute`, plus the `domains.yaml`
fixture extension) have shipped. The Phase 32 planner MUST surface this
in plan `must_haves.truths` so the verifier knows when SC#4 is
expected to pass.

---

*Phase: 32-query-layer-extensions*
*Research completed: 2026-05-25*
