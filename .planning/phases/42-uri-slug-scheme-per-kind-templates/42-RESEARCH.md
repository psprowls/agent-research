# Phase 42: URI Slug Scheme + Per-Kind Templates - Research

**Researched:** 2026-05-26
**Domain:** Python module design + property-based testing + filesystem-only artifacts (no external network/services)
**Confidence:** HIGH

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions (18 total — verbatim from `42-CONTEXT.md`)

**Slug encoding (D1):**
- **D-01** — Encoding scheme = kind-prefix preserved + `__` (double-underscore) separator for both `:` and `/`. Provably injective: kind segment uses single-underscore (`test_suite`, `entry_point`, `package_family`) and the path separator is double-underscore — they cannot collide.
- **D-02** — Kind values are snake_case (underscore-form), matching `graph_io._VALID_KINDS`. `ADMITTED_KINDS = frozenset({"repository", "domain", "package", "package_family", "plugin", "dependency", "test_suite"})`. Reconciliation lives in this phase (corrects roadmap text that used hyphens).
- **D-03** — `decode_slug(encode_slug(uri)) == uri` is required for all 7 admitted kinds. Enforced by Hypothesis property test.
- **D-04** — Three new URI builders go into `graph_io/uri.py`: `package_family_uri(name)`, `plugin_uri(name)`, `dependency_uri(ecosystem, name)`. Ecosystem required for dependency; package_family and plugin take only a name (concept-level, not repo-scoped).
- **D-05** — Collision policy = fail loudly. No runtime collision table; property test asserts injectivity. No fallback path.

**Whitelist (D2):**
- **D-06** — `SCANNER_OWNED_KEYS` is a single flat `frozenset[str]` (not a per-kind dict).
- **D-07** — Whitelist content baseline = ARCHITECTURE.md union (broader of the two research sources). Concrete initial set listed verbatim in CONTEXT.md.
- **D-08** — Naming convention = snake_case, plural for collections, matches graph-io node attrs. Direction-aware (`covered_by` edge → `test_suites:` on packages, `tested_packages:` on suites).
- **D-09** — No separate `HUMAN_OWNED` constant. Whitelist is sole source of truth; everything outside is human territory. Unit test asserts `{"status", "last_reviewed", "owner", "notes"} & SCANNER_OWNED_KEYS == set()`.

**Module placement:**
- **D-10** — Phase 42 creates `packages/wiki-io/src/wiki_io/entity_writer.py` containing only: `ADMITTED_KINDS`, `SCANNER_OWNED_KEYS`, `encode_slug`, `decode_slug`, module docstring. Phase 43 expands.
- **D-11** — Hypothesis added to test dependency group (PEP 735 `[dependency-groups].dev`). One new dev dep is acceptable; Hypothesis is canonical.

**Test corpus:**
- **D-12** — Property test uses Hypothesis composite strategies, one per admitted kind, fanned out via `@given(uri=admitted_uri_strategy())`. Target ≥1,000 generated URIs across all kinds (`@settings(max_examples=...)`).
- **D-13** — Single property test asserts BOTH injectivity AND round-trip.

**Vault scaffolding:**
- **D-14** — `init_vault.py`'s `FIXED_VAULT_DIRS` adds `"entities"`. Idempotent (`Path.mkdir(exist_ok=True)`).
- **D-15** — `wiki/entities/_index.md` is a sentinel-comment placeholder (single line). No structural content.

**Templates (per-kind, 7 files):**
- **D-16** — Narrative-region marker = explicit `## Narrative` H2 section. No HTML-comment sentinels (deliberate departure from v1.7 `layout_io.py`). Documented as hard convention.
- **D-17** — Template body shape = H1 + `## Narrative` placeholder + canonical section list per kind. Per-kind canonical sections enumerated in CONTEXT.md.
- **D-18** — All 7 templates declare `kind:` in frontmatter with underscore-form value.

### Claude's Discretion
- Exact docstring wording on `entity_writer.py` and the URI builders.
- Hypothesis strategy alphabet (defaulting to ASCII alphanumeric + `-` + `.` + `_` per real-world package names).
- Whether `entity_writer.py`'s module docstring uses example URIs from `agent-research` itself (recommended).

### Deferred Ideas (OUT OF SCOPE)
- `merge_frontmatter()` implementation and tests — Phase 43.
- `scan.lock` file logic — Phase 43.
- Per-kind whitelist validation — Phase 43.
- LLM narrative prompt design — Phase 45.
- Migration of existing entity-like data — Phase 46.
- Template body section finalization for kinds with thin sections — Phase 42 implementer may tune during template authoring.
</user_constraints>

<phase_requirements>
## Phase Requirements

| ID | Description (REQUIREMENTS.md) | Research Support |
|----|------------------------------|------------------|
| URI-01 | Slug encoder in `entity_writer.py` derives entity filename from graph URI deterministically; `:` and `/` both encoded as `__`; property test over ≥1,000 synthetic URIs from 7 admitted kinds asserts injective mapping (zero collisions) | D-01..D-05, D-10, D-12, D-13; Hypothesis composite strategies + `@settings(max_examples=...)` |
| URI-02 | Slug encoder round-trip stable: `decode_slug(encode_slug(uri)) == uri` for every URI in property test corpus | D-03 combined into same property test per D-13 |
| URI-03 | Per-kind templates added under `wiki_io/templates/entities/` (REQUIREMENTS.md path); 7 files: `entity-repository.md`, `entity-domain.md`, `entity-package.md`, `entity-package-family.md`, `entity-plugin.md`, `entity-dependency.md`, `entity-test-suite.md`; each declares `kind:` frontmatter and reserves prose region | **Path reconciliation (see Open Question Q1):** CONTEXT.md says `packages/wiki-io/src/wiki_io/assets/page-templates/` to match the existing template directory convention; REQUIREMENTS.md/ROADMAP say `wiki_io/templates/entities/`. CONTEXT.md decision-source-of-truth wins → templates land in existing `assets/page-templates/` alongside `package-family.md`, `dependency.md`. D-17 dictates body shape; D-16 dictates narrative marker (explicit `## Narrative` H2, not sentinel comment — deliberate departure from REQUIREMENTS.md text). D-18 dictates underscore-form `kind:` values. |
| URI-04 | `init_vault.py` adds `"entities"` to `FIXED_VAULT_DIRS`; freshly-bootstrapped vault contains `wiki/entities/` with `_index.md` placeholder | D-14, D-15; idempotent `mkdir(exist_ok=True)` already in init_vault.py loop; `_index.md` write added in same function |
| URI-05 | Admitted-kinds taxonomy declared as single `frozenset` constant in `entity_writer.py`; sub-packages and in-file nodes excluded; new graph kinds require code change | D-02; `ADMITTED_KINDS` frozenset with the 7 underscore-form kinds. `subpackage`, `file`, `function`, `class`, `method` from `_VALID_KINDS` are explicitly NOT in `ADMITTED_KINDS`. |
| URI-06 | Scanner-owned frontmatter key whitelist declared as single canonical `frozenset` constant in `entity_writer.py`, reconciled from ARCHITECTURE.md per-kind + FEATURES.md flat list; human-authored keys excluded | D-06..D-09; concrete initial set spelled out in CONTEXT.md; unit test asserts human-key disjointness per D-09. |
</phase_requirements>

## Summary

Phase 42 is a **foundation-lock** phase: no new behavior ships to users, only code constants, helper functions, templates, and a one-line `init_vault.py` edit. The CONTEXT.md leaves essentially zero technical ambiguity — D-01..D-18 dictate the exact encoding rule (`s.replace(':', '__').replace('/', '__')`), exact whitelist contents, exact template body shape, exact module path, exact test framework. Research-relevant findings collapse to two areas: (a) Hypothesis 6.x property-testing API to express "one strategy per admitted kind, fanned out under `@given`" in idiomatic form, and (b) reconciling a documentation-path discrepancy between REQUIREMENTS.md/ROADMAP and CONTEXT.md (templates location — see Open Question Q1).

**Primary recommendation:** Implement exactly as CONTEXT.md specifies. Two waves of plans: (Wave 1) `entity_writer.py` scaffold + property test + URI builders in parallel with template authoring; (Wave 2) `init_vault.py` edit + integration smoke verification. No alternative architectures considered — locked decisions preclude exploration.

## Architectural Responsibility Map

| Capability | Primary Tier | Secondary Tier | Rationale |
|------------|--------------|----------------|-----------|
| Slug encode/decode | `wiki-io` (entity_writer.py) | — | Filesystem-naming concern; lives next to entity-page-writing code (Phase 43+). |
| URI builder functions | `graph-io` (uri.py) | — | URI shape is owned by graph-io; wiki-io is a consumer. |
| Admitted-kinds taxonomy | `wiki-io` (entity_writer.py) | `graph-io` (queries._VALID_KINDS) | Phase 42 taxonomy is a curated *subset* of graph-io's `_VALID_KINDS` — different concern (which kinds get entity pages vs. which kinds exist in the graph). |
| Scanner-owned key whitelist | `wiki-io` (entity_writer.py) | — | Frontmatter-merge contract; consumed by future merge logic in same module. |
| Vault directory scaffolding | `wiki-io` (init_vault.py) | — | Existing module owns `FIXED_VAULT_DIRS`. One-line additive edit. |
| Property test corpus | `wiki-io` (tests/test_entity_writer.py) | — | Test lives next to the module under test. |

**Key tier observation:** Three new URI builders go into `graph-io/uri.py` (not `wiki-io/`) because URI **composition** is graph-io's job. `wiki-io/entity_writer.py` only **consumes** URIs (encodes them to filenames). Plan 01 must respect this boundary — do not put URI-builder code in `entity_writer.py`.

## Standard Stack

### Core
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| Python | ≥3.11 | Runtime | CLAUDE.md floor (langchain-core typing + asyncio); already pinned workspace-wide. |
| `hypothesis` | ≥6.116 (latest stable as of researcher's training; will be resolved by `uv` at install time) | Property-based testing for `encode_slug` injectivity + round-trip | [CITED: hypothesis.readthedocs.io] Canonical Python property-testing library. CLAUDE.md §8 leaves room for additions per phase. [ASSUMED: exact patch version] — `uv add` will pin latest stable; pyproject only constrains lower bound. |
| `pytest` | ≥8.3 | Test runner | Already in `[dependency-groups].dev` at workspace root. |
| `python-frontmatter` | ≥1.1 | Read/write template YAML frontmatter (templates themselves are byte-static so this is only used by tests verifying template parsability) | Already in `wiki-io` dependencies. |

### Supporting
| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| stdlib `pathlib` | 3.11 | Template file discovery + directory create | Use `Path.iterdir()` to enumerate templates in tests. |
| stdlib `frozenset` | 3.11 | `ADMITTED_KINDS`, `SCANNER_OWNED_KEYS` | Immutable, hashable, set-arithmetic-supporting — exactly the right primitive. |

### Alternatives Considered
| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| `hypothesis` | Hand-rolled `random` + loop | Loses minimal-counterexample shrinking, deterministic-seed replay on CI failure, edge-case generation. CONTEXT.md D-11/D-12 lock to Hypothesis explicitly. |
| Frozenset | `tuple` or `set` literal | Frozenset is hashable + immutable (vs. `set`) and supports `&`, `\|`, `-` operators (vs. `tuple`). D-06/D-09 lock to frozenset. |
| Per-kind whitelist `dict[str, frozenset]` | Flat `frozenset` | D-06 explicitly rejects per-kind variant: "single flat `frozenset[str]`". Phase 43 may layer per-kind validation later if needed; that's D-deferred. |
| Sentinel HTML comment for narrative region | Explicit `## Narrative` H2 | D-16 explicit decision: H2 chosen for cleaner rendered output. v1.7 `layout_io.py` precedent rejected for entity templates. |

**Installation (one new dep, added to workspace root):**
```bash
# At workspace root:
uv add --group dev hypothesis
```

**Version verification:** Hypothesis is a mature, ubiquitous PyPI package (active since 2013, 6.x line stable). `uv add` resolves to the current stable wheel; no need to over-pin in pyproject. Constrain only lower bound (e.g. `hypothesis>=6.116`) to ensure modern `@settings` API + composite-strategy support.

## Package Legitimacy Audit

| Package | Registry | Age | Downloads | Source Repo | slopcheck | Disposition |
|---------|----------|-----|-----------|-------------|-----------|-------------|
| `hypothesis` | PyPI | ~12 yrs (since 2013) | Very high (industry-standard) | github.com/HypothesisWorks/hypothesis | [ASSUMED: not run in this session — slopcheck unavailable in researcher environment] | Approved — well-known package; the planner inserts a single human-verify checkpoint for the install per Package Legitimacy protocol fallback policy. |

**Packages removed due to slopcheck [SLOP] verdict:** none
**Packages flagged as suspicious [SUS]:** none

*slopcheck was unavailable at research time. Per the fallback policy, the planner inserts one `checkpoint:human-verify` gate before the `uv add --group dev hypothesis` task. This is a one-time human glance at `pypi.org/project/hypothesis/` to confirm the package — Hypothesis is universally known; the checkpoint is a formality.*

## Architecture Patterns

### System Architecture Diagram

```
                  ┌──────────────────────────┐
                  │   graph-io/uri.py        │
                  │   (existing + 3 new)     │
                  │                          │
                  │   pkg_uri, domain_uri,   │
                  │   test_suite_uri,        │
                  │   repo_uri,              │
                  │   entry_point_uri,       │
                  │   subpkg_uri, file_uri,  │
                  │ + package_family_uri (NEW)│
                  │ + plugin_uri        (NEW)│
                  │ + dependency_uri    (NEW)│
                  └────────────┬─────────────┘
                               │
                               ▼ URI strings
                  ┌──────────────────────────┐
                  │ wiki-io/entity_writer.py │
                  │ (NEW — Phase 42 scaffold)│
                  │                          │
                  │   ADMITTED_KINDS         │
                  │   SCANNER_OWNED_KEYS     │
                  │   encode_slug()          │
                  │   decode_slug()          │
                  └────────────┬─────────────┘
                               │
                               ▼ filenames (e.g. pkg__agent-research__graph-io.md)
                  ┌──────────────────────────┐
                  │  wiki/entities/          │
                  │  (NEW vault dir, sentinel│
                  │   _index.md only in P42; │
                  │   real pages in P43)     │
                  └──────────────────────────┘

                  ┌──────────────────────────┐
                  │ wiki-io/init_vault.py    │
                  │   FIXED_VAULT_DIRS       │
                  │   + "entities" (NEW)     │
                  │   + _index.md writer     │
                  └──────────────────────────┘

                  ┌──────────────────────────┐
                  │ wiki-io/assets/          │
                  │   page-templates/        │
                  │     entity-repository.md │ (NEW)
                  │     entity-domain.md     │ (NEW)
                  │     entity-package.md    │ (NEW)
                  │     entity-package-      │ (NEW)
                  │       family.md          │
                  │     entity-plugin.md     │ (NEW)
                  │     entity-dependency.md │ (NEW)
                  │     entity-test-suite.md │ (NEW)
                  │   (Phase 43 consumes;    │
                  │    Phase 42 only writes) │
                  └──────────────────────────┘
```

Data flow: URI builder produces URI string → `encode_slug` produces filename → entity page lives at `wiki/entities/<filename>`. The vault directory and templates are *provisioned* in Phase 42 but only consumed in Phase 43+.

### Recommended Project Structure

```
packages/wiki-io/src/wiki_io/
├── entity_writer.py            # NEW — Phase 42 scaffold (constants + helpers only)
├── init_vault.py               # EDITED — add "entities" to FIXED_VAULT_DIRS; write _index.md
└── assets/
    └── page-templates/
        ├── entity-repository.md      # NEW
        ├── entity-domain.md          # NEW
        ├── entity-package.md         # NEW
        ├── entity-package-family.md  # NEW (note hyphen in filename; underscore in kind: value)
        ├── entity-plugin.md          # NEW
        ├── entity-dependency.md      # NEW
        └── entity-test-suite.md      # NEW (note hyphen in filename; underscore in kind: value)

packages/wiki-io/tests/
└── test_entity_writer.py        # NEW — property test + whitelist unit tests

packages/graph-io/src/graph_io/
└── uri.py                       # EDITED — 3 new builder functions appended

packages/graph-io/tests/
└── test_uri.py                  # EDITED IF EXISTS, else NEW — unit tests for 3 new builders
```

**Template filename convention note:** Filenames use hyphens (`entity-package-family.md`) because that matches the existing `package-family.md` and `dependency.md` filenames in `assets/page-templates/`. But the `kind:` frontmatter value uses underscores (`kind: package_family`) per D-02/D-18. Filenames and frontmatter values are *different concerns* — filename is filesystem-friendly, frontmatter value is the graph-canonical kind.

### Pattern 1: Hypothesis composite strategies per admitted kind

**What:** Define one `@st.composite` strategy per admitted kind that delegates to the corresponding URI builder, then combine them with `st.one_of` to produce a strategy that yields URIs across all 7 kinds. Drive the property test with `@given(uri=admitted_uri_strategy())`.

**When to use:** Whenever the test must cover multiple URI shapes with shared assertion logic — exactly D-12's case.

**Example (illustrative — final code in PLAN.md 01):**
```python
# Source: hypothesis.readthedocs.io (composite strategies)
from hypothesis import given, settings, strategies as st
from graph_io.uri import RepoContext, pkg_uri, domain_uri, ... # all 7 builders

# Realistic fragment alphabet: package/org names use lowercase ASCII alnum + - + _ + .
fragment = st.text(
    alphabet=st.characters(whitelist_categories=("Ll", "Nd"), whitelist_characters="-_."),
    min_size=1, max_size=20,
)

@st.composite
def pkg_uri_strategy(draw):
    return pkg_uri(RepoContext(draw(fragment), draw(fragment)), draw(fragment))

# ... one strategy per admitted kind ...

admitted_uri_strategy = st.one_of(
    pkg_uri_strategy(),
    domain_uri_strategy(),
    # ... all 7 ...
)

@given(uri=admitted_uri_strategy)
@settings(max_examples=1000, deadline=None)
def test_slug_round_trip(uri):
    assert decode_slug(encode_slug(uri)) == uri
```

**Note on injectivity:** A single `@given`-driven test cannot directly observe collisions because each example is generated independently. The injectivity property is proved by **encoding scheme construction** (`__` separator with no admitted kind containing `__` internally). Phase 42 belt-and-suspenders: add a *batched* test using `st.lists(admitted_uri_strategy, min_size=100, max_size=200)` that asserts `len({encode_slug(u) for u in uris}) == len(set(uris))` — equal counts mean no slug collision across distinct URIs in the batch. This complements the per-URI round-trip test. CONTEXT.md D-13 says one test covers both; in practice, two tightly-related tests (one per-URI round-trip, one batch-injectivity) is cleaner — both fit in the same test module under the spirit of D-13. Implementer's call.

### Pattern 2: Module-level frozenset constants with documented contract

**What:** Declare `ADMITTED_KINDS` and `SCANNER_OWNED_KEYS` at module scope with a module docstring that documents the contract (what's IN the set, what's deliberately OUT, why).

**When to use:** Phase 42's two anchor constants — every downstream phase imports them.

**Example:**
```python
# packages/wiki-io/src/wiki_io/entity_writer.py
"""Entity-page writer scaffold (Phase 42 lock; Phase 43 expansion).

Slug encoding contract:
  encode_slug(uri) = uri.replace(":", "__").replace("/", "__")
  The kind segment uses single-underscore (test_suite); the path separator
  uses double-underscore (__). Injectivity holds because no admitted kind
  contains "__". Round-trip via decode_slug requires splitting on "__" and
  the first segment matching ADMITTED_KINDS.

Scanner-owned-key contract:
  A frontmatter key in SCANNER_OWNED_KEYS may be overwritten by the scanner.
  Any other key (e.g. status, last_reviewed, owner, notes) is human territory
  and MUST be preserved verbatim on merge.

Narrative-region contract:
  Entity templates reserve a "## Narrative" H2 section. The Phase 45 LLM
  scanner writes ONLY into the region under that heading, stopping at the
  next H2. Humans must not rename or remove the heading.
"""
from __future__ import annotations

ADMITTED_KINDS: frozenset[str] = frozenset({
    "repository", "domain", "package", "package_family",
    "plugin", "dependency", "test_suite",
})

SCANNER_OWNED_KEYS: frozenset[str] = frozenset({
    # universal
    "uri", "kind", "graph_name", "last_scan_at",
    # ... see CONTEXT.md D-07 for the complete list
})
```

### Pattern 3: URI builder signature parity with existing module

**What:** New URI builders in `graph_io/uri.py` follow the exact one-line-signature, single-f-string-body style of the existing seven builders. No `RepoContext` for the three new ones — they're concept-level, not repo-scoped.

```python
def package_family_uri(name: str) -> str:
    return f"package_family:{name}"


def plugin_uri(name: str) -> str:
    return f"plugin:{name}"


def dependency_uri(ecosystem: str, name: str) -> str:
    return f"dependency:{ecosystem}/{name}"
```

### Anti-Patterns to Avoid

- **Per-kind whitelist dict:** D-06 explicitly forbids `dict[str, frozenset]`. Flat frozenset.
- **Implementing `write_entities()` in this phase:** D-10 — Phase 42 stops at constants + slug helpers. The module IS the scaffold; do not pre-populate the body of functions that arrive in Phase 43.
- **HTML-comment sentinel in templates:** D-16 forbids. Use `## Narrative` H2.
- **Adding Hypothesis as a runtime dependency of `wiki-io`:** It's a dev/test-only dep. Add to `[dependency-groups].dev` at workspace root, never to `packages/wiki-io/pyproject.toml` `dependencies`.
- **Hardcoded slug collision table or fallback hashing:** D-05 — fail loudly via property test; no runtime collision recovery.
- **Renaming `kind:` frontmatter values to hyphen-form to match filenames:** D-02/D-18 — frontmatter values are snake_case (`kind: package_family`), filenames keep hyphens to match existing `package-family.md` convention. They're different layers.
- **Embedding URI-builder logic inside `entity_writer.py`:** URI composition lives in `graph-io/uri.py`. `entity_writer.py` only consumes URIs.
- **Reading from the graph database in Phase 42 code:** The scaffold contains only pure helpers and constants. Graph queries arrive in Phase 43's `write_entities` function body.

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Property-based test corpus generator | `random.choice` + manual edge cases | `hypothesis` strategies | Shrinking on failure, deterministic replay seeds, automatic edge-case discovery — all free with Hypothesis. |
| Slug-collision detection | Persistent collision-table file | Construction-proof + property test | D-05 says fail loudly. The encoding is collision-free by construction; the test asserts this once. |
| Per-kind frontmatter validation | Custom validator class hierarchy | Two flat frozensets + simple membership check | Phase 42's whitelist is one set; validation in Phase 43 is one `if key in SCANNER_OWNED_KEYS` line. No classes. |
| Template body parsing for narrative region | Stateful Markdown parser | `## Narrative` H2 string split (Phase 45 concern) | Phase 42 only writes templates; Phase 45 owns the read side. |

**Key insight:** Phase 42 is deliberately tiny. The right metric is "lines of code added" — under 200 LOC of Python (excluding tests and templates) is on-target. Resist any urge to pre-build Phase 43's merge logic, hashmaps, validators, or registries.

## Common Pitfalls

### Pitfall 1: Slug collision from `__` appearing inside a path fragment
**What goes wrong:** A package or org name containing `__` (literal double underscore) breaks injectivity: `pkg:foo__bar/baz` and `pkg:foo/bar__baz` would both encode to `pkg__foo__bar__baz.md`.
**Why it happens:** The encoding scheme treats `__` as both literal-content and separator.
**How to avoid:** The Hypothesis strategy's alphabet excludes `_` adjacency that produces `__` — use `whitelist_characters="-_."` with `min_size=1` ensuring single-char tokens, AND a `.assume(...)` filter `assume("__" not in fragment_value)` inside each composite strategy. Real-world package names don't contain `__` (PyPI normalization collapses double-underscores), so this is a practical non-issue, but the property test must guard against it explicitly.
**Warning signs:** Property test fails with shrunk counterexample `name="__"` or similar.

**Action for planner:** Plan 01 must call out the `assume("__" not in <fragment>)` filter in the Hypothesis strategies, and the module docstring must state "no admitted-kind URI fragment may contain `__`" as a contract.

### Pitfall 2: Trailing slash or empty fragment in URI
**What goes wrong:** `pkg:agent-research//graph-io` (empty middle segment) or `pkg:agent-research/graph-io/` (trailing slash) encodes to `pkg__agent-research____graph-io.md` or `pkg__agent-research__graph-io__.md` — neither round-trips cleanly because `decode_slug` would split on `__` and get a different segment count.
**Why it happens:** URI builders concatenate fragments with `/` separators; if a builder is called with an empty string, the URI gains a doubled `/`.
**How to avoid:** Hypothesis strategies use `min_size=1` on every `fragment`. The URI builders themselves should reject empty inputs (planner: add a one-line guard `if not name: raise ValueError(...)` at the top of each new builder). Round-trip test then never sees these invalid inputs.
**Warning signs:** Property test fails with shrunk counterexample having empty fragments.

### Pitfall 3: Hyphen-vs-underscore kind drift
**What goes wrong:** Some places (REQUIREMENTS.md, ROADMAP.md) reference kinds as hyphenated (`test-suite`, `package-family`); CONTEXT.md D-02 locks to underscore (`test_suite`, `package_family`). If template filenames OR `kind:` frontmatter values OR `ADMITTED_KINDS` members drift apart, the encoder can produce a slug the decoder can't reverse, or a runtime lookup misses.
**How to avoid:**
- Filenames: hyphens (`entity-package-family.md`) — matches existing template convention.
- `kind:` frontmatter values: underscores (`kind: package_family`) — D-02/D-18 lock.
- `ADMITTED_KINDS` members: underscores (`"package_family"`) — D-02 lock.
- Slug kind segment: underscores (`pkg__...`, `package_family__...`, `test_suite__...`).
- Reconciliation test: unit test asserts every template's `kind:` value is a member of `ADMITTED_KINDS`.
**Warning signs:** Reconciliation test fails after a template author types a hyphenated value.

### Pitfall 4: Hypothesis `deadline` flakiness in CI
**What goes wrong:** Default Hypothesis deadline (200ms per example) can timeout on slow CI runners; the test passes locally but flakes on CI.
**How to avoid:** `@settings(deadline=None)` — CONTEXT.md specifics call this out explicitly.

### Pitfall 5: Template `kind:` value not matching admitted kind
**What goes wrong:** Template author writes `kind: package-family` (hyphen) in frontmatter, or omits the field, or uses a wrong value.
**How to avoid:** Unit test reads all 7 entity templates, asserts each parses with `frontmatter` and `template["kind"] in ADMITTED_KINDS`. Already implied by URI-03 acceptance.
**Warning signs:** Template kind audit test fails.

## Runtime State Inventory

> Phase 42 is greenfield (new files) + one additive edit (`FIXED_VAULT_DIRS`). No rename, no migration, no runtime state outside the project tree.

| Category | Items Found | Action Required |
|----------|-------------|-----------------|
| Stored data | None — no databases or datastores carry slug encoding or whitelist constants. The graph DB (`.graph-wiki/graph.db`) stores URIs but not slugs; slug derivation is deterministic on read. | None |
| Live service config | None — phase touches only filesystem and Python imports. | None |
| OS-registered state | None — no daemons, schedulers, or system registrations. | None |
| Secrets / env vars | None | None |
| Build artifacts | None — `entity_writer.py` is a new module; no compiled artifacts. uv editable install picks it up automatically on `uv sync`. | None |

**Nothing found in any category.** Phase 42 ships pure source code + templates.

## Environment Availability

| Dependency | Required By | Available | Version | Fallback |
|------------|-------------|-----------|---------|----------|
| Python | All workflow steps | ✓ | 3.11+ (workspace floor) | — |
| `uv` | Adding `hypothesis` dev dep + running tests | ✓ | 0.11.x (workspace pin in pyproject) | — |
| `hypothesis` | Property test | ✗ — not currently in `[dependency-groups].dev` | — | Plan 01 adds it: `uv add --group dev hypothesis` |
| `pytest` | Test runner | ✓ (in `[dependency-groups].dev` at root) | ≥8.3 | — |
| `pytest-asyncio` | Async test plumbing | ✓ (in root dev group) | 1.3.0 | — |
| `python-frontmatter` | Template parsability tests | ✓ (in `wiki-io` deps) | ≥1.1 | — |
| Network / Bedrock | None — Phase 42 is offline | n/a | — | — |

**Missing dependencies with no fallback:** none
**Missing dependencies with fallback:** `hypothesis` — Plan 01 install task adds it.

## Validation Architecture

### Test Framework
| Property | Value |
|----------|-------|
| Framework | `pytest` 8.3+, `hypothesis` 6.x (new), `pytest-asyncio` 1.3.0 (already present, unused here — Phase 42 tests are sync) |
| Config file | `pyproject.toml` root + `packages/wiki-io/pyproject.toml` (per-package testpaths) |
| Quick run command | `uv run --package wiki-io pytest tests/test_entity_writer.py -x` |
| Full suite command (wiki-io scope) | `uv run --package wiki-io pytest` |
| Full suite command (workspace) | `uv run pytest` |

### Phase Requirements → Test Map
| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|--------------|
| URI-01 | `encode_slug(uri)` collision-free across 7 admitted kinds over ≥1,000 URIs | property (Hypothesis) | `uv run --package wiki-io pytest tests/test_entity_writer.py::test_slug_batch_injective -x` | ❌ Wave 0 — new test file |
| URI-02 | `decode_slug(encode_slug(uri)) == uri` for every URI in corpus | property (Hypothesis) | `uv run --package wiki-io pytest tests/test_entity_writer.py::test_slug_round_trip -x` | ❌ Wave 0 — new test file |
| URI-03 | 7 entity templates exist, each declares `kind:` matching `ADMITTED_KINDS`, each has `## Narrative` H2 | unit | `uv run --package wiki-io pytest tests/test_entity_writer.py::test_entity_templates_valid -x` | ❌ Wave 0 — new test file |
| URI-04 | `init_vault.py` creates `wiki/entities/_index.md` on bootstrap | integration (uses existing `test_init_vault.py`) | `uv run --package wiki-io pytest tests/test_init_vault.py::test_entities_dir_bootstrapped -x` | ❌ Wave 0 — new test case (file exists) |
| URI-05 | `ADMITTED_KINDS` is a frozenset, contains exactly the 7 kinds, excludes `subpackage`/`file`/`function`/`class`/`method` | unit | `uv run --package wiki-io pytest tests/test_entity_writer.py::test_admitted_kinds_shape -x` | ❌ Wave 0 |
| URI-06 | `SCANNER_OWNED_KEYS` is a frozenset, includes baseline keys per D-07, disjoint from `{status, last_reviewed, owner, notes}` | unit | `uv run --package wiki-io pytest tests/test_entity_writer.py::test_scanner_owned_keys_disjoint_from_human -x` | ❌ Wave 0 |
| (additional) | Three new URI builders produce correctly-shaped strings | unit | `uv run --package graph-io pytest tests/test_uri.py -x` | likely ❌ Wave 0 — file may not exist; check at plan time |

### Sampling Rate
- **Per task commit:** `uv run --package wiki-io pytest tests/test_entity_writer.py -x` (~2-3s including Hypothesis 1000-example run)
- **Per wave merge:** `uv run --package wiki-io pytest` + `uv run --package graph-io pytest`
- **Phase gate:** Both packages' full suites green before `/gsd:verify-work`

### Wave 0 Gaps
- [ ] `packages/wiki-io/tests/test_entity_writer.py` — covers URI-01, URI-02, URI-03, URI-05, URI-06 (new file)
- [ ] `packages/graph-io/tests/test_uri.py` — covers three new URI builders (extend if exists, create if not — check at plan time)
- [ ] `packages/wiki-io/tests/test_init_vault.py` — add `test_entities_dir_bootstrapped` case for URI-04 (file exists; one test case added)
- [ ] `hypothesis` install in root `[dependency-groups].dev`

## Security Domain

> Phase 42 has no trust boundary changes — it ships pure constants and a new directory entry. No network, no inputs, no external services. The only "input" is developer-authored Python and Markdown.

### Applicable ASVS Categories
| ASVS Category | Applies | Standard Control |
|---------------|---------|------------------|
| V2 Authentication | no | — |
| V3 Session Management | no | — |
| V4 Access Control | no | — |
| V5 Input Validation | minimal — slug encoding is pure deterministic transform of internal URI strings; no untrusted input crosses a boundary in Phase 42 | URI strings come from `graph-io` builders, not from end users. Adding the empty-fragment guard mentioned in Pitfall 2 is a defensive-coding improvement, not a security control. |
| V6 Cryptography | no — no hashing, no encryption (D-05 explicitly forbids hash-based fallback) | — |
| V12 (Files & Resources) | yes — templates are static assets bundled with the wiki-io wheel; `init_vault.py` writes filesystem | Existing `init_vault.py` already writes file paths derived from a constant list; adding `"entities"` to that list preserves the existing security posture. |

### Known Threat Patterns for this stack
| Pattern | STRIDE | Standard Mitigation |
|---------|--------|---------------------|
| Slopsquatted dev dependency (`hypothesis`) | Tampering | One-time human-verify checkpoint before `uv add --group dev hypothesis` confirms `pypi.org/project/hypothesis/`. Package is universally known (12+ years, used by stdlib teams, NumPy, pandas). Risk near zero, but the checkpoint formalizes the gate per the legitimacy protocol fallback (slopcheck unavailable). |
| Path traversal via slug | Tampering | Slug input is `uri.replace(":", "__").replace("/", "__")` — both `/` and `:` are explicitly replaced, eliminating any path-injection vector. Slugs cannot contain `..` because URI builders never produce `..`. Acceptable as-is. |

**STRIDE register for plans (each PLAN.md `<threat_model>`):**
- `T-42-01` Tampering on `hypothesis` install → mitigate with checkpoint:human-verify before install (per `T-42-SC` slop-check fallback pattern).
- `T-42-SC` Supply-chain on `hypothesis` → mitigate via human-verify checkpoint; package is well-known with 12+ years of registry history.

## Code Examples

Verified patterns from existing code:

### 1. Existing URI builder signature style (graph-io/uri.py)
```python
# Source: packages/graph-io/src/graph_io/uri.py
def pkg_uri(ctx: RepoContext, name: str) -> str:
    return f"pkg:{ctx.org}/{ctx.repo}/{name}"

def test_suite_uri(ctx: RepoContext, suite_name: str) -> str:
    return f"test_suite:{ctx.org}/{ctx.repo}/{suite_name}"
```

New builders must match: single-line signature, single f-string return, `from __future__ import annotations` at module top (already present).

### 2. Existing FIXED_VAULT_DIRS pattern (wiki-io/init_vault.py)
```python
# Source: packages/wiki-io/src/wiki_io/init_vault.py
FIXED_VAULT_DIRS = [
    "concepts",
    "architecture",
    "adrs",
    "sources",
    "dependencies",
    ".templates",
]
# ... later in init_wiki():
for d in structural_dirs + FIXED_VAULT_DIRS:
    (wiki_path / d).mkdir(parents=True, exist_ok=True)
```

Edit: append `"entities"` to the list (D-14). Add a single new write call after the existing directory loop:
```python
entities_index = wiki_path / "entities" / "_index.md"
if not entities_index.exists():
    entities_index.write_text(
        "<!-- generated by graph-wiki-agent scan; "
        "see ../index.md for the canonical listing -->\n",
        encoding="utf-8",
    )
    installed_files.append(str(entities_index.relative_to(wiki_path)))
```

### 3. Existing template body shape (wiki-io/assets/page-templates/package-family.md)
```yaml
---
title: <Family Name>
category: dependency
kind: package-family            # ← existing template uses hyphen; new entity-package-family.md uses kind: package_family (D-02 underscore lock)
family_name: <family-slug>
members: []
...
---

# <Family Name>

## What it is
...
```

Phase 42 entity templates follow this overall shape but with `## Narrative` as the first H2 (D-16, D-17). Existing templates (`package-family.md`, `dependency.md`) are left untouched — they continue to serve the v1.7 layout until Phase 46's cutover.

### 4. Existing test_init_vault.py case style
```python
# Source: packages/wiki-io/tests/test_init_vault.py (excerpt)
def test_resolve_pinned_containers_v2_excludes_workspace(tmp_path: Path) -> None:
    from wiki_io.init_vault import _resolve_pinned_containers
    # ... build synthetic repo ...
    records = _resolve_pinned_containers(repo, non_interactive=True, workspace_path=workspace)
    sources = {r["source"] for r in records}
    assert "packages" in sources
```

New URI-04 test case can follow: build a synthetic workspace with `_workspace_init` stub or skip it (call `init_wiki` directly with a tmp path), assert `wiki/entities/_index.md` exists with sentinel content. Reuse the existing `_build_v2_repo` fixture-style pattern if convenient.

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| Per-package directories (`wiki/packages/<name>/{index,context,...}.md`) | Single `wiki/entities/<slug>.md` driven by graph URI | v1.8 (Phase 42 scaffold, Phase 43 implementation, Phase 46 cutover) | Phase 42 only creates the new lane — old layout remains active until Phase 46. |
| Hand-rolled random test inputs | Hypothesis property-based testing | v1.8 (this phase introduces) | Better edge-case coverage; deterministic regression replay. |

**Deprecated / outdated:**
- HTML-comment sentinels for region-aware merge (existed in `wiki_io/layout_io.py`) — entity templates use `## Narrative` H2 instead per D-16. The `layout_io.py` sentinels remain for curated lanes (`/concepts/`, `/adrs/`, etc.); they are not removed.

## Assumptions Log

| # | Claim | Section | Risk if Wrong |
|---|-------|---------|---------------|
| A1 | Hypothesis 6.116+ is on PyPI and `uv add --group dev hypothesis` resolves to the current stable wheel | Standard Stack | LOW — Hypothesis is one of the most-installed PyPI packages; install will not fail. Worst case: pin a specific version after first install. |
| A2 | `packages/graph-io/tests/test_uri.py` may or may not exist; the planner will check at plan time and create-or-extend accordingly | Validation Architecture | LOW — either way, the test gets written; the only question is filename. |
| A3 | The existing `init_vault.py::init_wiki` is reachable by tests without standing up a real workspace (the test for URI-04 may need to stub `_workspace_init` or call into the directory-creation block directly) | Validation Architecture | MEDIUM — if `_workspace_init` has hard side effects (git init, .graph-wiki.yaml write) the test approach may need adjustment. Planner notes: existing `test_init_vault.py` uses `_build_v2_repo` and calls private helpers directly to avoid this; the URI-04 test can follow the same pattern, possibly testing the directory list itself (`"entities" in FIXED_VAULT_DIRS`) plus the `_index.md` write in a separate test that exercises only the relevant code path. |
| A4 | slopcheck not available at research time; per the fallback policy all packages tagged `[ASSUMED]` and human-verify checkpoint required | Package Legitimacy Audit | LOW — Hypothesis is unambiguously legitimate; checkpoint is a formality. |

## Open Questions

1. **Q1: Templates path — `wiki_io/templates/entities/` (REQUIREMENTS.md / ROADMAP success criterion #3) vs. `wiki_io/assets/page-templates/` (CONTEXT.md D-17 + existing project convention)?**
   - What we know: The existing project already uses `packages/wiki-io/src/wiki_io/assets/page-templates/` for all current templates (`package-family.md`, `dependency.md`, `adr.md`, `concept.md`, etc.). REQUIREMENTS.md URI-03 names a new path `wiki_io/templates/entities/`. CONTEXT.md D-17 says "Mirrors the structure of existing `dependency.md` and `package-family.md` templates" and the canonical-refs section points to the existing directory.
   - What's unclear: REQUIREMENTS.md and CONTEXT.md disagree on path; both are project artifacts.
   - Recommendation: Honor CONTEXT.md (locked decision source per the GSD workflow) — templates land in the existing `assets/page-templates/` directory next to `dependency.md`. This avoids a parallel template directory structure that nothing else uses. Document the reconciliation in Plan 02 and propagate the corrected path back to REQUIREMENTS.md URI-03 in a follow-up edit (Phase 42 commit can include the REQUIREMENTS.md text correction since it's mechanical reconciliation, not a scope change).

2. **Q2: Narrative-region marker — `## Narrative` H2 (CONTEXT.md D-16) vs. "prose sentinel comment reserving the narrative region" (REQUIREMENTS.md URI-03)?**
   - What we know: CONTEXT.md D-16 explicitly chooses H2 and documents the rejection of HTML-comment sentinels. REQUIREMENTS.md URI-03 mentions sentinel comments.
   - What's unclear: Same conflict pattern as Q1.
   - Recommendation: Honor CONTEXT.md D-16 (H2 marker). Same reconciliation note in Plan 02; propagate to REQUIREMENTS.md.

3. **Q3: Should the URI-04 test target the directory list (`"entities" in FIXED_VAULT_DIRS`) or actually run `init_wiki` end-to-end?**
   - What we know: Existing `test_init_vault.py` mixes both styles; calling `init_wiki` requires standing up a `_workspace_init` side effect.
   - Recommendation: Two-test approach — (a) `test_entities_in_fixed_vault_dirs` (trivial assertion on the constant), (b) `test_entities_index_md_written` that uses a stub or the existing fixture pattern to exercise the relevant write. Planner finalizes the exact shape during plan authoring.

## Sources

### Primary (HIGH confidence)
- `.planning/phases/42-uri-slug-scheme-per-kind-templates/42-CONTEXT.md` — 18 locked decisions; all design choices traceable.
- `.planning/REQUIREMENTS.md` URI-01..URI-06 — six requirement IDs Phase 42 must address.
- `.planning/ROADMAP.md` Phase 42 — goal + 5 success criteria.
- `.planning/STATE.md` Key Decisions — D1/D2 locks + pitfall guards.
- `packages/graph-io/src/graph_io/uri.py` — existing URI builder signatures (read).
- `packages/graph-io/src/graph_io/queries.py` `_VALID_KINDS` — graph-side kinds for taxonomy reconciliation (read).
- `packages/wiki-io/src/wiki_io/init_vault.py` — `FIXED_VAULT_DIRS` constant + `init_wiki` function (read).
- `packages/wiki-io/src/wiki_io/assets/page-templates/{package-family,dependency}.md` — existing template shape (read).
- `packages/wiki-io/tests/test_init_vault.py` — existing test style (read).
- `packages/wiki-io/pyproject.toml` + workspace root `pyproject.toml` — dependency-group conventions (read).
- `CLAUDE.md` §1 (uv workspace), §8 (pytest stack) — workspace + testing constraints.

### Secondary (MEDIUM confidence)
- `.planning/research/ARCHITECTURE.md`, `FEATURES.md`, `PITFALLS.md` — v1.8 synthesis (referenced via CONTEXT.md canonical-refs; not re-read in Phase 42 research, but cited as the source of D-07 whitelist baseline).
- Hypothesis 6.x documentation — `composite` strategies, `@settings(max_examples, deadline=None)` API. [CITED: hypothesis.readthedocs.io] from training; not re-verified via Context7 in this session because the API surface used is small and stable across recent 6.x releases.

### Tertiary (LOW confidence)
- None — every claim is either traceable to a project artifact (HIGH) or to documented Hypothesis API (MEDIUM).

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH — only one new dep (`hypothesis`), well-known, pinned by uv at install time.
- Architecture: HIGH — CONTEXT.md locked every architectural decision.
- Pitfalls: HIGH — derived from CONTEXT.md, existing-code reading, and the encoding-scheme's literal invariant (no admitted kind contains `__`).

**Research date:** 2026-05-26
**Valid until:** 2026-06-25 (30 days — Hypothesis API stable; CONTEXT.md is the durable artifact)

## Project Constraints (from CLAUDE.md)

- **§1 (`uv` workspace):** New tests must run via `uv run --package wiki-io pytest`. Dev deps go in workspace-root `[dependency-groups].dev` per PEP 735.
- **§8 (pytest stack):** pytest ≥8.3, pytest-asyncio 1.3.0, syrupy 5.1.0 already present. `hypothesis` is a clean addition with no conflict. CLAUDE.md "what NOT to use" explicitly forbids `pytest-recording`/VCR cassettes for LLM responses — Phase 42 has no LLM calls, so this is moot.
- **§2 stack-departure note:** Phase 42 has no agent/LLM/subagent code — pure constants and helpers. Bedrock guardrails do not apply.
- **`from __future__ import annotations`:** Required at top of every new `graph-io` module per project convention. Apply to `entity_writer.py` and any new test files.
- **Per-package layout:** `packages/<name>/src/<name>/` for sources, `packages/<name>/tests/` for tests. Plan 02 (entity_writer + tests) lives in `packages/wiki-io/`; URI-builder edits land in `packages/graph-io/`.

## Note on REQUIREMENTS.md / ROADMAP reconciliation

Two minor textual conflicts between CONTEXT.md (locked decisions) and REQUIREMENTS.md / ROADMAP success-criterion text:

1. Templates path: `wiki_io/templates/entities/` (REQ/ROADMAP) vs `wiki_io/assets/page-templates/` (CONTEXT.md + existing convention). Decision: honor CONTEXT.md; correct REQ/ROADMAP text in the same phase commit.
2. Narrative-region marker: "sentinel comment" (REQ URI-03) vs `## Narrative` H2 (CONTEXT.md D-16). Decision: honor CONTEXT.md; correct REQ text in the same phase commit.

These are mechanical-text corrections in REQUIREMENTS.md / ROADMAP, not scope changes. Plan 02 (templates) includes the text correction in its `files_modified`.
