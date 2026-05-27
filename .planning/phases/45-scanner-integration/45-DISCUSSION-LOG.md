# Phase 45: Scanner Integration - Discussion Log

**Date:** 2026-05-27
**Phase:** 45 — Scanner Integration

This log captures the conversation that produced `45-CONTEXT.md`. For audit / retrospective use only — not consumed by downstream agents.

---

## Pre-discussion analysis surfaced a conflict

Before presenting gray areas, codebase analysis revealed a direct conflict between:
- **SCANINT-04** (REQUIREMENTS.md): "Step 12 calls `index_generator.generate_index` for the entity portion of the index; curated-lane index sections continue to flow through existing `update_index.py` path"
- **Phase 44 CONTEXT.md D-02**: "ONE index, no per-folder `*/index.md` sub-indexes; `update_index.py` deprecated → deleted in Phase 46 cutover"

The conflict was elevated to the user as Area 1.

## Gray Area Selection

User selected all four offered areas:

1. SCANINT-04 vs Phase 44 D-02 conflict
2. Coexistence: entity pages vs legacy package pages during Phase 45
3. Step 9 scanner fan-out: needs_narrative gating + prompt rewrite
4. Step 11 deletion branching + plugin smoke test (SCANINT-06)

---

## Area 1: SCANINT-04 vs Phase 44 D-02 conflict

**Question:** How do we resolve the conflict?

**Options presented:**
1. Phase 44 D-02 wins; rewrite SCANINT-04 — drop `update_index.py` entirely
2. Coexistence during Phase 45, deprecation at Phase 46
3. Keep `update_index.py` for sub-indexes only, drop its `wiki/index.md` write  ← chosen

**User chose:** Option 3.

→ Captured as D-01 (Step 12 dual-call shape), D-02 (surgical `update_index.py` change), D-03 (SCANINT-04 rewrite).

**Follow-up question:** Given per-folder sub-indexes survive, what's `wiki/index.md`'s content for curated lanes?

**Options presented:**
1. Full listing in `wiki/index.md` AND per-folder sub-index file  ← chosen
2. Link-summary only in `wiki/index.md`
3. Full curated listing in `wiki/index.md`, no per-folder sub-index

**User chose:** Option 1 — both wiki/index.md (full curated listings) AND per-folder sub-indexes survive. Two views of the same data. Phase 44 D-02's `wiki/index.md` shape stays valid; the per-folder retention is a Phase 45 revision of Phase 44 D-02's "Phase 46 deletes per-folder files."

→ Captured in `<domain>` block as Phase 44 D-02 partial supersedence; D-01/D-02 reflect the resulting wiring.

---

## Area 2: Coexistence — entity pages vs legacy package pages during Phase 45

**Question:** During Phase 45 (before Phase 46 cutover), what files exist after a scan?

**Options presented:**
1. Both: entity pages + legacy package pages
2. Entities only; Step 10 rewired  ← chosen
3. Entity-only behind a feature flag

**User chose:** Option 2 — hard cutover at Phase 45. Legacy `wiki/packages/<name>/<name>.md` writes removed. Only entity pages produced. Stale legacy pages from prior scans linger until Phase 46 cutover deletes them.

→ Captured as D-08.

---

## Area 3: Step 9 scanner fan-out — needs_narrative gating + prompt rewrite

**Question:** How does Step 9 produce entity-page narrative — new prompt, or branch existing?

**Options presented:**
1. New `build_entity_narrative_prompt` + new scanner role  ← chosen
2. Modify `build_stub_prompt` to support entity-page mode
3. Two-pass: scanner produces full page, then strip frontmatter before write

**User chose:** Option 1 — separate prompt + separate role.

→ Captured as D-04 (Step 9 split), D-05 (new prompt builder), D-06 (new `narrator` role).

**Follow-up question:** How does the LLM narrator output land in entity pages?

**Options presented:**
1. Scanner returns prose; scan.py inserts between H2 markers
2. Helper in entity_writer: `inject_narrative(page_path, prose)`  ← chosen
3. Narrator writes the page directly

**User chose:** Option 2 — `entity_writer.inject_narrative` helper. Page-format knowledge stays in entity_writer.py (consistent with Phase 42 D-16's "## Narrative H2 convention").

→ Captured as D-07.

---

## Area 4: Step 11 deletion split + plugin smoke test (SCANINT-06)

Two questions presented together.

**Q1 — Step 11 deletion split:**

Options:
1. Implicit: entity-managed names are in graph; curated lane names are not  ← chosen
2. Explicit: scan.py computes `deleted_entities` and `deleted_curated` separately

**User chose:** Option 1 — implicit split via `write_entities`. Step 11's stale-tag loop becomes nearly a no-op for v1.8 since most kinds are entity-managed.

→ Captured as D-09, D-10.

**Q2 — Plugin smoke test:**

Options:
1. Plugin stays on legacy layout; its scan produces wiki/packages/* only  ← chosen
2. Plugin gets upgraded in Phase 45 to also produce entity pages
3. Plugin smoke test rewritten to assert layout-agnostic behavior

**User chose:** Option 1 — plugin scan_monorepo.py NOT modified in Phase 45. Two independent code paths during transition.

→ Captured as D-13, D-14.

---

## Wrap-up clarification

**Question:** SCANINT-05: how does `_load_existing_pages` / `compute_diff` handle `wiki/entities/` by URI?

**Options presented:**
1. Separate entity-path: existing[uri] = {path, frontmatter}; legacy unchanged  ← chosen
2. Single dict keyed by stable identifier (URI for entities, name for legacy)
3. Phase 45 only adds entity URI lookup; legacy keying untouched

**User chose:** Option 1 — `ExistingPages` dataclass with two sub-dicts (entities by URI, legacy by name). `compute_diff` consumes both but doesn't compute entity diffs (those are owned by `write_entities`).

→ Captured as D-11, D-12.

---

## Notable Cross-Phase Consequences

- **Phase 44 D-02 partial supersedence.** Phase 45 D-02 reverses the Phase 46 deletion of `update_index.py` and per-folder sub-indexes. Phase 44 CONTEXT.md is NOT edited (immutable history); the supersedence is recorded in Phase 45 CONTEXT.md `<domain>` block and `<decisions>` D-02. Phase 46 CONTEXT.md (when discussed) must read both.
- **SCANINT-04 requirements text needs updating.** D-03 specifies the new wording; the Phase 45 plan must include a task to edit REQUIREMENTS.md.
- **`ScanResult` shape expansion.** D-15 adds URI-keyed entity fields. Any downstream consumer (CLI summary code, telemetry) that reads `added`/`updated` must also read `entities_*`. Search for `ScanResult.added` callers as part of Phase 45 planning.

---

## Deferred Ideas

Captured in `45-CONTEXT.md` `<deferred>` section. Key items:

- Plugin upgrade to entity layout — post-Phase-46 or v1.9.
- Narrator prompt tuning + cheaper-model exploration — v1.9.
- `compute_diff` graph-aware unification — v1.9.
- `update_index.py` eventual retirement — beyond v1.8.

---

## Claude's Discretion

Items left to the planner's judgment (documented in `<decisions>` Claude's discretion block):

- Narrator `models.toml` config (model_id, max_tokens, max_concurrency).
- Narrator error-handling policy (lean: partial-success, accumulate in `entity_errors`).
- CLI summary line format.
- `update_index.py` surgical edit shape (lean: drop the wiki/index.md write block unconditionally, not a flag).
- Exact narrator prompt wording.
- `inject_narrative` implementation (raw bytes vs `python-frontmatter`).
- File-map sourcing for non-`package` kinds in narrator prompt.

---

*Discussion concluded: 2026-05-27*
