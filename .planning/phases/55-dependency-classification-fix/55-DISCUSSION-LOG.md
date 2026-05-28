# Phase 55: Dependency Classification Fix - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md — this log preserves the alternatives considered.

**Date:** 2026-05-28
**Phase:** 55-dependency-classification-fix
**Areas discussed:** Name-matching strategy, depends_on edge kind reuse, Edge derivation source, used_by cleanup + describe-package

---

## Name-matching strategy

| Option | Description | Selected |
|--------|-------------|----------|
| Normalized + ecosystem-scoped | Normalize both sides, suppress only within same ecosystem | |
| Normalized, cross-ecosystem | Normalize (lowercase + `-`/`_` collapse), suppress on name match regardless of ecosystem | ✓ |
| Exact string match | Suppress only on exact name equality | |

**User's choice:** Normalized, cross-ecosystem
**Notes:** Currently a Python-only `uv` workspace, so cross-ecosystem name collisions are effectively impossible — simpler rule is safe. Workspace-name set built once from `_discover_manifests()`. Ecosystem-scoping deferred until a non-Python workspace package is ever added.

---

## depends_on edge kind reuse

| Option | Description | Selected |
|--------|-------------|----------|
| Reuse depends_on, distinguish by node kind | Emit kind=`depends_on`; storage separates from Domain→Domain via node IDs | |
| Reuse depends_on + a `scope` attr | Same kind, tag attrs with scope=package/domain | |
| New distinct edge kind | Introduce a separate edge kind | ✓ |

**User's choice:** New distinct edge kind → follow-up confirmed "New kind — update the requirement" → named `depends_on_package`
**Notes:** This was surfaced as a conflict: a new kind contradicts the locked CLASS-02 wording and `REQUIREMENTS.md:54` ("no new edge kinds"). Pat confirmed the override and accepted that CLASS-02/REQUIREMENTS.md must be updated to match. Reuse was noted as technically clean (storage already separates rows); the distinct kind was chosen for query ergonomics/readability. Edge direction: src = consumer, dst = internal package depended on.

### Edge-name sub-decision
| Option | Description | Selected |
|--------|-------------|----------|
| package_depends_on | Explicit, namespaced | |
| depends_on_package | Reads as "A depends_on_package B" | ✓ |
| internal_dependency | Names the concept, diverges from depends_on vocab | |

---

## Edge derivation source

| Option | Description | Selected |
|--------|-------------|----------|
| Manifest declaration | Emit from the `[project.dependencies]` parse where the node is suppressed | ✓ |
| import_scan resolution | Derive from resolved internal imports | |
| Both (manifest ∪ imports) | Emit if either signal present | |

**User's choice:** Manifest declaration
**Notes:** Co-located with the node suppression in `packages.py` — one source of truth. Consumer = the declaring package. Declared-but-not-imported internal deps still produce an edge, accepted.

---

## used_by cleanup + describe-package

### used_by handling
| Option | Description | Selected |
|--------|-------------|----------|
| Replace with depends_on_package | Don't emit used_by for suppressed internal dep | |
| Keep used_by, retarget to package node | Point used_by at package/app node, plus emit depends_on_package | ✓ |
| You decide | Defer to planning | |

**User's choice:** Keep used_by, retarget to package node
**Notes:** Two same-direction edges for one relationship — intentional redundancy. `used_by` stays the universal "consumer uses X" edge (uniform with external deps); `depends_on_package` carries the package-level semantic for IDX-05 / describe-package. Preserve existing per-`(consumer, dep)` dedupe; resolve retargeted dst to real stored node kind.

### describe-package surfacing (SC#3)
| Option | Description | Selected |
|--------|-------------|----------|
| Both directions | Show internal dependencies (outgoing) AND dependents (incoming) | ✓ |
| Dependents only | Show only incoming (literal SC#3 wording) | |
| You decide | Defer to planning | |

**User's choice:** Both directions
**Notes:** SC#3 mandates incoming ("internal dependents"); outgoing added as the natural complement.

---

## Claude's Discretion

- Exact normalization helper (reuse/extend `import_scan` normalization vs. a local PEP 503 normalizer).
- `describe_package()` output shape/labels for the two new sections.
- Whether to add a `usage_count`/weight attr on `depends_on_package`.

## Deferred Ideas

- Ecosystem-scoped matching — only if a non-Python workspace package is added.
- `usage_count`/weight attr on `depends_on_package` — optional, no SC requires it.
- IDX-05 nesting + index generator consuming `depends_on_package` — Phase 57 work; flagged as downstream dependency.
