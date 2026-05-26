# Phase 31: Domain Layer + Derived Edges - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md — this log preserves the alternatives considered.

**Date:** 2026-05-25
**Phase:** 31-domain-layer-derived-edges
**Areas discussed:** domains.yaml schema, Derived edge compute strategy, TestSuite→Domain edges, Cycle recovery + emit placement

---

## domains.yaml schema

### Q1: YAML shape for declaring domains, packages, nesting

| Option | Description | Selected |
|--------|-------------|----------|
| Flat map with explicit parent | Top-level keys are domain names; each has packages: list and optional parent: ref | ✓ |
| Nested via subdomains list | Top-level domain has packages: + subdomains: containing nested domain objects | |
| Flat map with parent: list (multi-parent) | parent: accepts a list; rejected by DOMAIN-03 | |
| Two-section: domains: + hierarchy: | Explicit separation of domain decl from parent-child rels | |

**User's choice:** Flat map with explicit parent.
**Notes:** D-01 in CONTEXT.md.

### Q2: Multi-domain membership expression

| Option | Description | Selected |
|--------|-------------|----------|
| Each domain lists its packages; same package name appears in multiple domains | Aggregate across domain entries; natural for flat-map shape | ✓ |
| Forbid multi-listing; require domains: list on package side | Splits config across two sections | |
| Allow multi-listing + emit warning | Log on double-membership | |

**User's choice:** Each domain lists its packages; same package name appears in multiple domains.
**Notes:** D-02 in CONTEXT.md.

### Q3: Extra Domain attrs

| Option | Description | Selected |
|--------|-------------|----------|
| Allow optional description and owner, ignore unknown keys | Forward-compatible; warning on unknown | ✓ |
| Strict: only packages + parent | Schema violation on extra keys (exit 4) | |
| Allow arbitrary attrs (Domain.attrs_json) | Maximum flexibility; typo risk | |

**User's choice:** Allow optional description and owner, ignore unknown keys.
**Notes:** D-01 in CONTEXT.md.

### Q4: File location flexibility

| Option | Description | Selected |
|--------|-------------|----------|
| Repo root only, fixed path | Always <repo_root>/domains.yaml; no flag, no env | ✓ |
| Repo root + GRAPH_WIKI_DOMAINS_CONFIG env override | Env-based override for tests | |
| Multiple search paths | repo root, .planning/, .config/ probe | |

**User's choice:** Repo root only, fixed path.
**Notes:** D-03 in CONTEXT.md.

---

## Derived edge compute strategy

### Q1: Recompute strategy

| Option | Description | Selected |
|--------|-------------|----------|
| Delete-all-then-recompute, single tx | Cleanest, trivially idempotent | ✓ |
| Incremental diff | Faster but complex; correctness risk | |
| Build in-memory, then upsert with delete-stale pass | Two passes, less wipe footprint | |

**User's choice:** Delete-all-then-recompute, single tx.
**Notes:** D-17 in CONTEXT.md.

### Q2: usage_count semantics — direct or transitive

| Option | Description | Selected |
|--------|-------------|----------|
| Direct members only | Aligns with DERIVED-04 (no transitive storage) | ✓ |
| Include subdomain members (transitive) | Loses DERIVED-04 unless stored separately | |
| Both direct + transitive count | Doubles storage; conflicts with DERIVED-04 | |

**User's choice:** Direct members only.
**Notes:** D-07 in CONTEXT.md.

### Q3: depends_on edge shape

| Option | Description | Selected |
|--------|-------------|----------|
| One edge per (A,B), with usage_count attr | Mirror references shape | ✓ |
| One edge per (A,B), no attrs | Loses coupling-strength signal | |
| Multiple edges per (A,B) annotated with importing_package | Most granular; storage cost | |

**User's choice:** One edge per (A,B) with usage_count attr.
**Notes:** D-09 in CONTEXT.md.

### Q4: Import scanner — shared or dedicated

| Option | Description | Selected |
|--------|-------------|----------|
| Shared scanner module, called from both | Refactor Phase 30's scanner; one source of truth | ✓ |
| Dedicated scanner in derived_edges.compute | Duplicates Phase 30 logic; drift risk | |
| Compute from existing tests edges + fresh package-import scan | Hybrid | |

**User's choice:** Shared scanner module, called from both.
**Notes:** D-10 in CONTEXT.md (with Phase 30 back-port risk note).

### Q5: Test files in derived edges

| Option | Description | Selected |
|--------|-------------|----------|
| Exclude test files — derived edges from production code only | Cleaner coupling semantics | ✓ |
| Include test files | Over-counts coupling | |
| Annotate edges with source (prod vs test) | Doubles edge count | |

**User's choice:** Exclude test files.
**Notes:** D-11 in CONTEXT.md.

---

## TestSuite→Domain edges

### Q1: Trigger rule

| Option | Description | Selected |
|--------|-------------|----------|
| Suite→Domain when suite→Package edges all land in same domain | Captures spec intent (suite tests a domain) | ✓ |
| Suite→Domain when ≥1 package in domain D and zero outside D | Aggressive; loses integration/e2e signal | |
| Suite→Domain by kind: only for kind in {integration, e2e} | Naming-heuristic dependent | |
| Combined: kind AND all-in-one-domain | Belt-and-suspenders; might emit zero | |

**User's choice:** Suite→Domain when suite→Package edges all land in same domain.
**Notes:** D-12 in CONTEXT.md (≥2 packages required).

### Q2: Multi-domain suites

| Option | Description | Selected |
|--------|-------------|----------|
| All Package edges + Repository edge — no Domain edge | Phase 30 multi-Package edges already capture cross-cutting | ✓ |
| Emit TestSuite→Domain for each spanned domain | Over-counts | |
| Emit TestSuite→Domain for majority domain only | Heuristic; drops signal | |

**User's choice:** All Package edges + Repository edge — no Domain edge.
**Notes:** D-13 in CONTEXT.md.

### Q3: Where derivation lives

| Option | Description | Selected |
|--------|-------------|----------|
| Inside derived_edges.compute | Single transaction; uniform delete-then-recompute | ✓ |
| Separate pass in test_suites.emit | Back-port to Phase 30 module | |
| Separate test_suite_domain_edges.emit module | Most explicit; most boilerplate | |

**User's choice:** Inside derived_edges.compute.
**Notes:** D-14 in CONTEXT.md.

---

## Cycle recovery + emit placement

### Q1: Cycle skip — literal or surgical

| Option | Description | Selected |
|--------|-------------|----------|
| Literal: skip ALL domain_contains_domain edges | Matches SC#2 wording verbatim | |
| Surgical: skip only edges participating in cycles | More forgiving; preserves acyclic remainder | ✓ |
| Skip cycle component only (SCC>1) | Middle ground | |

**User's choice:** Surgical: skip only edges participating in cycles.
**Notes:** Deviates from SC#2 wording — see next question.

### Q2: Reconciling with SC#2

| Option | Description | Selected |
|--------|-------------|----------|
| Update SC#2 wording in ROADMAP.md | Amend SC to match the surgical preference | ✓ |
| Keep SC#2 as written, narrow to cycle-only SCC | Defensible interpretation | |
| Use literal 'skip ALL' to match SC#2 | Override the surgical choice | |

**User's choice:** Update SC#2 wording in ROADMAP.md.
**Notes:** D-15 in CONTEXT.md — planner Wave 0 task to edit ROADMAP.md SC#2 wording.

### Q3: Call order placement

| Option | Description | Selected |
|--------|-------------|----------|
| domains.emit before resolve.sweep, derived_edges.compute after invariant check | Domain nodes participate in sweep (URI-guarded); derived runs last per DERIVED-03 | ✓ |
| domains.emit + derived_edges.compute both after invariant check | Symmetrical Phase 31 isolation | |
| Both before resolve.sweep + invariant check | Couples to Phase 29 invariants | |

**User's choice:** domains.emit before resolve.sweep, derived_edges.compute after invariant check.
**Notes:** D-16 in CONTEXT.md.

### Q4: Unknown-package warning format

| Option | Description | Selected |
|--------|-------------|----------|
| Full list, sorted | Print all known package names alphabetically | ✓ |
| Suggest-only via fuzzy match | Levenshtein-based top-3 | |
| Count + first N + 'see cg list-packages' | Defers to a Phase 33 CLI | |

**User's choice:** Full list, sorted.
**Notes:** D-04 in CONTEXT.md.

---

## Claude's Discretion

- Domain.uri exact format
- Whether Phase 31 lands a thin `cg list-domains` shim or defers to Phase 33
- SCC algorithm specifics (Tarjan recommended; ~30 LOC)
- Whether `import_scan` lives in `graph-io` or a separate shared package
- `Domain.attrs_json` shape (description, owner, unknown-keys residue)

## Deferred Ideas

- Convention-based domain inference (DOMAIN-05 defers to v1.7+)
- Transitive subdomain edge bubbling at compute time
- `tagged_with` mechanism
- Cross-repo Domain support
- `Domain.owner` as structured ref (Team node)
- Per-package import-graph caching
- Wildcard package matching in domains.yaml
- Reverse-direction domains: list on packages
- Edge attrs `usage_count_transitive`
