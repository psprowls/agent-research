# Phase 44: Scanner-Generated Index - Discussion Log

**Date:** 2026-05-26
**Phase:** 44 — Scanner-Generated Index

This log captures the conversation that produced `44-CONTEXT.md`. For audit / retrospective use only — not consumed by downstream agents.

---

## Gray Area Selection

User selected all four offered areas:

1. New module vs replace `update_index.py`
2. Index file location & schema
3. Domain section composition
4. Curated lanes preservation strategy

---

## Area 1: New module vs replace update_index.py

**Question:** How should `index_generator.py` relate to the existing `update_index.py`?

**Options presented:**
1. New module, both coexist in v1.8
2. New module, deprecate update_index.py at Phase 46  ← chosen
3. New module + carve curated-lane logic into separate module
4. Replace `update_index.py` in-place

**User chose:** Option 2 — new module, deprecate `update_index.py` at Phase 46.

→ Captured as D-01.

---

## Area 2: Index file location & schema

**Question:** What file does `generate_index` write, and what's the section structure?

**Options presented:**
1. `wiki/index.md`, full rewrite
2. `wiki/index.md`, sections with HTML comment markers
3. `wiki/entities/_index.md` only

**User answered (freeform):** "Full rewrite, include entities as you describe above, but also include architecture, adrs, concepts, etc. Bring the old indexing code for these pages into the new index generator. One index. No longer need indexes per page type folder."

→ Strong scope clarification. The single `wiki/index.md` consolidates entity sections (graph-driven) AND all curated-lane sections (frontmatter-scanned). Per-folder `concepts/index.md`, `adrs/index.md`, `sources/index.md`, `architecture/index.md`, `dependencies/index.md` are obsoleted — they stop being maintained in Phase 44 and are deleted in Phase 46 cutover. The legacy `update_index.py`'s curated-lane scan logic is ported into `index_generator.py` (D-11).

→ Captured as D-02, D-03 (section order), and noted as a scope expansion from the ROADMAP's "graph queries directly" wording in the `<domain>` block.

---

## Area 3: Domain section composition

**Question:** How are entities nested under a domain section, and what counts as 'contained'?

**Options presented:**
1. Flat list per kind under each domain
2. Nested tree, packages-first, test_suites/deps under each package  ← chosen (modified)
3. Flat list, only direct `belongs_to_domain`

**User answered (freeform):** "Nested tree, the only things that are in the by-kind section are entities that don't belong under any existing section. I don't see a situation where something should appear more than once, but please correct me if I am wrong. Maybe a test-suite that tests multiple domains or packages directly?"

→ Two decisions consolidated:
   (a) Nested-tree structure (D-05, D-06).
   (b) Single-placement rule — each entity in exactly one section, departing from INDEX-02's "entities appear twice." Multi-domain edge case flagged by user.

**Follow-up question:** When an entity could nest under multiple domains, how do we place it?

**Options presented:**
1. Home = alphabetically-first domain; rest cross-reference
2. Multi-domain entities live in by-kind only  ← chosen
3. Dependencies always in by-kind; packages/test_suites use first-domain rule

**User chose:** Option 2 — multi-domain entities (deps, multi-package test suites, multi-domain packages) all route to `## By Kind`.

→ Captured as D-04.

---

## Area 4: Curated lanes preservation strategy

Given Area 2's consolidation decision, the original framing (preserve per-folder `*/index.md` files) became moot. Reframed to: how are curated-lane sections structured within the consolidated `wiki/index.md`?

**Question:** How are curated-lane sections structured within `wiki/index.md`?

**Options presented:**
1. Top-level sections after Domains and By Kind  ← chosen
2. Grouped under a single `## Knowledge` parent
3. Inline within domain sections where possible

**User chose:** Option 1 — top-level sections. Order: Architecture, ADRs, Concepts, Sources, Work.

→ Captured as D-03 (section order in the file) and D-12 (CURATED_LANES tuple).

**Follow-up question:** How does `generate_index` discover curated-lane pages?

**Options presented:**
1. Frontmatter scan (port from `update_index.py`)
2. Ingest curated lanes into graph as `doc` nodes
3. Frontmatter scan now, plan graph ingestion as v1.9  ← chosen

**User chose:** Option 3.

→ Captured as D-11 (port scan logic into `index_generator.py`) and a deferred-ideas entry for the v1.9 graph ingestion direction.

---

## Wrap-up clarifications (3 micro-decisions)

**Q1: By-Kind sub-heading ordering?**

Options: alphabetical / hierarchy-of-importance / frozenset iteration.

User chose: **Hierarchy of importance** — Packages → Test Suites → Dependencies → Plugins. Hard-coded.

→ D-09.

**Q2: Sub-domain (parent_domain edges) rendering?**

Options: flat with cross-ref / nested under parent.

User chose: **Nested under parent** — sub-domains render as `### Sub-Domain: <name>` inside the parent domain's section, with their own tree.

→ D-07.

**Q3: Empty section behavior?**

Options: omit entirely / always render with `(0)` placeholder.

User chose: **Omit empty sections entirely** — no zero placeholders anywhere.

→ D-08.

---

## Deferred Ideas

Captured in `44-CONTEXT.md` `<deferred>` section. Key ones:

- Ingest curated lanes as graph `doc` nodes (v1.9).
- Per-domain navigation pages (out of scope; entity domain pages already cover this in Phase 43's writer).
- Cross-references for multi-domain entities (rejected; by-kind is the canonical home per D-04).
- Markdown ToC at top of `wiki/index.md` (not in v1.8).

---

## Claude's Discretion

Items left to the planner's judgment (documented in `<decisions>` Claude's discretion block):

- Exact dataclass field types inside `IndexWriteResult`.
- Internal helper signatures (D-21 names are a sketch).
- Whether `_scan_curated_lane` returns dicts or a small dataclass.
- Whether determinism test uses Hypothesis or a seeded permutation (lean: seeded permutation).
- Trailing-newline convention in the rendered file (POSIX: end with `\n`).
- `bytes_written` semantics when unchanged (lean: `0` when unchanged, actual length when changed).

---

*Discussion concluded: 2026-05-26*
