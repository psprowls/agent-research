# Phase 32: Query Layer Extensions - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md — this log preserves the alternatives considered.

**Date:** 2026-05-25
**Phase:** 32-query-layer-extensions
**Areas discussed:** Helper output shape, Bubble-up at query time, cross_cutting_packages definition, Test fixture strategy

---

## Helper output shape

### Q1: Extend PackageDescription strategy

| Option | Description | Selected |
|--------|-------------|----------|
| Extend in place with three new fields | domains, entry_points, test_suites; default empty list for backwards compat | ✓ |
| Subclass PackageDescriptionV2 | Inheritance for new fields | |
| Return separate sidecar object | describe_package + describe_package_extended | |

**User's choice:** Extend in place with three new fields.
**Notes:** D-01 in CONTEXT.md.

### Q2: New dataclass verbosity

| Option | Description | Selected |
|--------|-------------|----------|
| Minimal: name + uri + 1-2 key fields | Lightweight nested types; drill via describe_* | ✓ |
| Verbose: every attr + computed counts | Maximum data per call; query bloat | |
| Two-tier: minimal in describe_package; verbose in describe_<thing> | Composable | |

**User's choice:** Minimal: name + uri + 1-2 key fields.
**Notes:** D-02 in CONTEXT.md.

### Q3: PathDescription role_flags shape

| Option | Description | Selected |
|--------|-------------|----------|
| Add role_flags: dict[str, bool] \| None | Dict with 7 keys; None for non-File nodes | ✓ |
| Add RoleFlags dataclass | Type-safe wrapper | |
| Pack into existing NodeRecord.attrs | Doesn't match SC#3 'role_flags block' | |

**User's choice:** Add role_flags: dict[str, bool] | None.
**Notes:** D-05 in CONTEXT.md.

---

## Bubble-up at query time

### Q1: Which helpers walk hierarchy

| Option | Description | Selected |
|--------|-------------|----------|
| tests_for_domain + domain_references + domain_depends_on | The three obvious bubble candidates | ✓ |
| All helpers bubble where applicable | describe_domain also aggregates subdomain counts | |
| Only tests_for_domain walks; references/depends_on stay direct | Minimal bubble-up | |
| Two helpers per type (direct + transitive) | Explicit API; doubles helper count | |

**User's choice:** tests_for_domain + domain_references + domain_depends_on.
**Notes:** D-06 in CONTEXT.md.

### Q2: Walk implementation

| Option | Description | Selected |
|--------|-------------|----------|
| SQLite recursive CTE | Single round-trip; idiomatic | ✓ |
| Python-side BFS/DFS | More flexible, slower | |
| Materialised closure table | Trade store for query speed | |

**User's choice:** SQLite recursive CTE.
**Notes:** D-07 in CONTEXT.md.

### Q3: Cross-cutting suite inference (Phase 31 D-13 multi-domain suites)

| Option | Description | Selected |
|--------|-------------|----------|
| Yes — query-time inference (UNION direct edges + package-join) | Captures cross-cutting suites that lack the Domain edge | ✓ |
| No — only direct TestSuite→Domain edges | Strict; lossy | |
| Direct + single-package suites in D | Middle ground | |

**User's choice:** Yes — query-time inference.
**Notes:** D-09 in CONTEXT.md.

---

## cross_cutting_packages definition

### Q1: Definition strictness

| Option | Description | Selected |
|--------|-------------|----------|
| Strictly zero belongs_to_domain edges | Matches ontology spec §11.4 verbatim | ✓ |
| Zero OR low (<=1) | Looser | |
| Configurable threshold | Parameterised | |

**User's choice:** Strictly zero belongs_to_domain edges.
**Notes:** D-10 in CONTEXT.md.

### Q2: Ranking metric

| Option | Description | Selected |
|--------|-------------|----------|
| Distinct-domain count | Matches spec literal | |
| Sum of usage_count across incoming references | 'How heavily depended on' rather than 'how broadly' | ✓ |
| Tuple: (distinct_domains, total_usage_count) | Both metrics, primary on distinct | |
| Return both metrics; caller chooses | Most flexible | |

**User's choice:** Sum of usage_count across incoming references edges.
**Notes:** D-11 in CONTEXT.md. **Deliberate divergence from ontology spec §11.4 wording** (which says 'distinct domains'). User preferred 'heavily depended on' weighting. Captured in D-11 note — no spec amendment needed since this is a query-layer rendering choice.

### Q3: Output shape

| Option | Description | Selected |
|--------|-------------|----------|
| list[tuple[PackageDescription, int]] sorted desc | One call, full Package data + score | ✓ |
| list[str] sorted desc | Names only; two-call drill-in | |
| list[CrossCuttingScore] with name + score + distinct + packages_using | Dedicated dataclass | |

**User's choice:** list[tuple[PackageDescription, int]] sorted desc.
**Notes:** D-12 in CONTEXT.md.

---

## Test fixture strategy

### Q1: Fixture pattern

| Option | Description | Selected |
|--------|-------------|----------|
| One shared seeded fixture per test module | Fast, consistent, readable | ✓ |
| Per-helper seeded fixtures | Isolated; slow setup; duplication | |
| Use sample_monorepo + run cg update --full | Realistic; couples failures across phases | |
| Hybrid: shared + targeted edge cases | Most thorough; more setup | |

**User's choice:** One shared seeded fixture per test module.
**Notes:** D-13 in CONTEXT.md (combined with later choices into a hybrid: shared happy-path + targeted edge cases).

### Q2: Seed method

| Option | Description | Selected |
|--------|-------------|----------|
| Raw SQL inserts | Decoupled from emitter behavior; fast | |
| Call emitters against synthetic mini-repo | Realistic; couples to emitter correctness | ✓ |
| Pre-built golden DB file in repo | Fastest load; binary fixture pain | |

**User's choice:** Call emitters against synthetic mini-repo.
**Notes:** D-14 in CONTEXT.md. SC#4 says 'before Phase 33 begins' — emitter-driven seed is fine.

### Q3: Fixture reuse vs dedicated

| Option | Description | Selected |
|--------|-------------|----------|
| Reuse sample_monorepo, extend with domains.yaml | One canonical fixture across phases | |
| Dedicated tests/fixtures/queries_sample/ | Isolated; tunable independently | |
| Both: reuse for happy path + targeted for edge cases | Most coverage; more files | ✓ |

**User's choice:** Both: reuse sample_monorepo for happy path + targeted fixtures for edge cases (empty DB, cycle, etc.).
**Notes:** D-13 + D-15 in CONTEXT.md.

### Q4: Pytest scope

| Option | Description | Selected |
|--------|-------------|----------|
| Session-scoped, read-only | Build once per session; fast CI | ✓ |
| Function-scoped | Fresh DB per test; slow | |
| Module-scoped | Per-file DB | |

**User's choice:** Session-scoped, read-only.
**Notes:** D-14 in CONTEXT.md.

---

## Claude's Discretion

- Exact SQL strings (JOIN order, sub-select strategy)
- list_* sort order beyond alphabetical
- Whether to inline the recursive-descendants CTE per helper or extract a helper function
- Internal helper functions vs module-private constants for shared SQL fragments
- entry_points_for_package ordering (executable first vs pure alphabetical)
- list_scripts deduplication strategy (union with dedup vs explicit annotation)

## Deferred Ideas

- CLI subcommands → Phase 33
- Pagination for list_* and bubble-up queries
- Query result caching
- Materialised closure tables for domain hierarchy
- JSON output mode in CLI
- tests_for_domain inferred-mode toggle
- Streaming results for very-large queries
- Cross-language symbol resolution in describe_path
