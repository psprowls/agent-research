# Phase 42: URI Slug Scheme + Per-Kind Templates - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md — this log preserves the alternatives considered.

**Date:** 2026-05-26
**Phase:** 42-uri-slug-scheme-per-kind-templates
**Areas discussed:** Slug encoding details, Module placement + test corpus, Whitelist shape + reconciliation, Template prose-sentinel format

---

## Slug encoding details

### Q1 — Encoding scheme

| Option | Description | Selected |
|--------|-------------|----------|
| Keep kind prefix + `__` separator | `pkg:agent-research/graph-io` → `pkg__agent-research__graph-io.md`. Both `:` and `/` encode as `__`. Kind visible in filename. Matches STATE.md latest convention. Provably injective. | ✓ |
| Strip kind prefix, use `--` | FEATURES.md original variant. Kind only in frontmatter. Cross-kind collision risk. | |
| Use just bare name | ARCHITECTURE.md variant. `graph-io.md`. Shortest, but high collision risk per PITFALLS.md. | |

**User's choice:** Keep kind prefix + `__` separator (Recommended).
**Notes:** Aligns with STATE.md / SUMMARY.md / PITFALLS.md consensus.

### Q2 — Decode round-trip for kinds without URI builders

| Option | Description | Selected |
|--------|-------------|----------|
| Phase 42 adds missing builders to `graph_io/uri.py` | Add `package_family_uri`, `plugin_uri`, `dependency_uri`. Centralizes URI composition. ~15 LOC scope creep into graph-io. | ✓ |
| Slug layer maintains its own kind table | URI construction logic for the four missing kinds lives in `entity_writer.py`. Zero changes to graph-io but minor duplication. | |
| Defer the three URI builders to Phase 43 | Phase 42 only tests 4/7 kinds. Defeats design-lock purpose. | |

**User's choice:** Phase 42 adds the missing URI builders to `graph_io/uri.py` (Recommended).
**Notes:** —

### Q3 — URI shape for the three new builders + kind-naming reconciliation

| Option | Description | Selected |
|--------|-------------|----------|
| Underscore kinds, ecosystem-namespaced | `package_family:aws`, `plugin:graph-wiki`, `dependency:pypi/boto3`. Align v1.8 ADMITTED_KINDS to graph-io underscore form. | ✓ |
| Hyphen kinds, ecosystem-namespaced | Keep hyphens (`package-family:aws`). Wiki kinds diverge from graph-io. | |
| Bare names only (no ecosystem) | `dependency:boto3`. Future ecosystem collision risk. | |

**User's choice:** Underscore kinds, ecosystem-namespaced (Recommended).
**Notes:** This implies a milestone-wide convention update — roadmap text that uses hyphens (`test-suite`, `package-family`) becomes lossy synonyms; canonical form is underscore.

### Q4 — Collision policy

| Option | Description | Selected |
|--------|-------------|----------|
| Fail loudly — raise on collision | Pure encoder, no runtime collision table. Hypothesis test catches regressions. | ✓ |
| Hash-suffix fallback | `-<sha256(uri)[:6]>` on detected collision. Runtime state in a pure function. | |
| Defer to Phase 43 | Leaves contract incomplete. | |

**User's choice:** Fail loudly — raise on collision (Recommended).
**Notes:** —

---

## Module placement + test corpus

### Q5 — Module location for constants + slug helpers

| Option | Description | Selected |
|--------|-------------|----------|
| Create `entity_writer.py` with constants + slug helpers in Phase 42 | Matches roadmap criterion #5 verbatim. Phase 43 expands the same module. | ✓ |
| Separate `slug.py` + `entity_kinds.py`, imported by `entity_writer.py` later | Cleaner boundaries; needs interpreting roadmap as "re-exported from entity_writer.py". | |
| Put it all in `wiki_io/__init__.py` for now | Smallest footprint; later move causes Phase 43 churn. | |

**User's choice:** Create `entity_writer.py` with constants + slug helpers (Recommended).
**Notes:** —

### Q6 — Test corpus generation

| Option | Description | Selected |
|--------|-------------|----------|
| Hypothesis strategies driving the URI builders | Composite strategies per kind, ~150 URIs/kind, automatic shrinking on failure. New dev dep. | ✓ |
| Hand-crafted corpus + parametrize | Deterministic but less coverage than randomized property testing. | |
| Synthetic loop in conftest, no Hypothesis | Loses Hypothesis shrinking-on-failure. | |

**User's choice:** Hypothesis strategies driving the URI builders (Recommended).
**Notes:** Hypothesis added to `packages/wiki-io`'s `[dependency-groups].dev` per PEP 735 / CLAUDE.md §1.

### Q7 — `wiki/entities/_index.md` content

| Option | Description | Selected |
|--------|-------------|----------|
| Sentinel-only placeholder | Single-line HTML comment pointing to `../index.md`. Folder visible in Obsidian, no maintenance. | ✓ |
| Auto-generated mini-index | Redundant with Phase 44's `wiki/index.md`. | |
| Empty file with `.gitkeep` semantics | Zero-byte file; no hint about why it exists. | |

**User's choice:** Sentinel-only placeholder (Recommended).
**Notes:** —

---

## Whitelist shape + reconciliation

### Q8 — Whitelist shape

| Option | Description | Selected |
|--------|-------------|----------|
| Single flat frozenset | Matches roadmap criterion #5. Simple merge invariant: any key in the set is overwritable. | ✓ |
| Per-kind mapping (dict[str, frozenset]) | Stricter invariant; deviates from roadmap text. | |
| Flat frozenset + separate `KIND_EXPECTED_KEYS` for docs/lint | Best of both worlds at cost of two constants. | |

**User's choice:** Single flat frozenset (Recommended).
**Notes:** —

### Q9 — Whitelist content baseline

| Option | Description | Selected |
|--------|-------------|----------|
| ARCHITECTURE.md union (~17 keys) | Broader: edges + node-attrs. Captures `language`, `version`, `file_count`, `ecosystem`. | ✓ |
| FEATURES.md flat list (~9 keys) | Edges-only baseline. Leaves derived fields to humans. | |
| Roadmap-criterion minimal set | Defers reconciliation; smallest blast radius. | |

**User's choice:** ARCHITECTURE.md union (Recommended).
**Notes:** Phase 43 may add fields as graph queries are wired in; Phase 42 locks the shape and the principle.

### Q10 — Key naming convention

| Option | Description | Selected |
|--------|-------------|----------|
| Snake_case, plural for collections, matches graph-io node attrs | `domains: [...]`, `test_suites: [...]`. Direction-aware (`test_suites` on packages, `tested_packages` on suites). | ✓ |
| Use edge names verbatim | `belongs_to_domain: [foo]` reads oddly. FEATURES.md's earlier convention. | |
| Decide name-by-name in Phase 43 | Templates created in Phase 42 would have placeholder names; intra-milestone churn. | |

**User's choice:** Snake_case, plural for collections (Recommended).
**Notes:** —

### Q11 — Explicit excluded set

| Option | Description | Selected |
|--------|-------------|----------|
| Only the whitelist; no separate excluded set | Single source of truth. Examples in module docstring. | ✓ |
| Both whitelist + explicit `HUMAN_OWNED_HINT_KEYS` | Extra constant to maintain; redundant for runtime. | |
| No explicit list — rely on whitelist test | Test asserts canonical human keys absent. | |

**User's choice:** Only the whitelist; no separate excluded set (Recommended).
**Notes:** A unit test asserts `{"status", "last_reviewed", "owner", "notes"} & SCANNER_OWNED_KEYS == set()` to catch drift.

---

## Template prose-sentinel format

### Q12 — Narrative-region marker

| Option | Description | Selected |
|--------|-------------|----------|
| HTML comment sentinels | `<!-- narrative:begin -->` / `<!-- narrative:end -->`. Mirrors v1.7 `layout_io.py` precedent. | |
| Explicit `## Narrative` H2 section | Cleaner rendered output. LLM targets region under H2, stops at next H2. | ✓ |
| No sentinel — frontmatter-only contract | Simplest but `needs_narrative` overwrite semantics become ambiguous. | |

**User's choice:** Explicit H2 section convention.
**Notes:** Deliberate departure from v1.7 sentinel precedent — trades that consistency for cleaner rendered Markdown. H2 boundary is documented as a hard convention in `entity_writer.py` module docstring.

### Q13 — H2 heading text

| Option | Description | Selected |
|--------|-------------|----------|
| `## Narrative` | Unambiguous label; matches research vocabulary. | ✓ |
| `## Overview` | Reads naturally; risks collision with v1.4 `overview.md` convention. | |
| Per-kind heading (`## About this <kind>`) | Different heading per template; more complexity in writer. | |

**User's choice:** `## Narrative` (Recommended).
**Notes:** —

### Q14 — Template body content

| Option | Description | Selected |
|--------|-------------|----------|
| H1 + Narrative placeholder + canonical section list per kind | Mirrors existing single-file templates (`package-family.md`, `dependency.md`). Provides authoring guidance. | ✓ |
| Minimal — frontmatter + H1 + `## Narrative` only | Sparse pages; no guidance per kind. | |
| Defer body design to Phase 43 | Defeats Phase 42's design-lock framing. | |

**User's choice:** H1 + Narrative placeholder + canonical section list per kind (Recommended).
**Notes:** Per-kind section drafts are in CONTEXT.md D-17 — implementer may tune during template authoring.

---

## Claude's Discretion

- Exact docstring wording on `entity_writer.py` and the new URI builders.
- Hypothesis strategy alphabet (defaulting to ASCII alphanumeric + `-` + `.` + `_`).
- Whether the module docstring uses example URIs from `agent-research` itself.
- Per-kind canonical section lists in D-17 — initial draft; implementer may tune.

## Deferred Ideas

- `merge_frontmatter()` implementation — Phase 43.
- `scan.lock` acquisition logic — Phase 43.
- Per-kind whitelist validation at runtime — Phase 43 if needed.
- LLM narrative prompt design — Phase 45.
- Migration of old `wiki/packages/*` data — Phase 46.
- Todo `fix-scanner-treats-import-root-as-subpackage` (score 0.2) — graph-io scanner bug; may slot into Phase 45 or v1.9.
