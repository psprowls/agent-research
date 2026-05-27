---
phase: 45-scanner-integration
plan: 01
subsystem: scanner-integration
tags: [bedrock, models.toml, entity-writer, update_index, narrator, inject_narrative]

requires:
  - phase: 43-entity-writer
    provides: write_entities, EntityWriteResult, _scanner_frontmatter_for_node (now renamed)
  - phase: 44-scanner-generated-index
    provides: generate_index (consumed by Plan 03 Step 12)

provides:
  - "[roles.narrator] entry in packaged models.toml — make_llm('narrator') returns a guarded ChatBedrockConverse"
  - "inject_narrative(page_path, prose) — idempotent atomic body-region replacer for `## Narrative` H2"
  - "scanner_frontmatter_for_node — un-underscored public name for Plan 03 import"
  - "update_index surgical change — wiki/index.md write removed; per-folder sub-indexes preserved"
  - "SCANINT-04 rewritten to the dual-writer wording from CONTEXT.md D-03"

affects: [45-02, 45-03, 46-inbound-link-migration-cutover]

tech-stack:
  added: []
  patterns:
    - "Atomic file rewrite via temp-file + os.replace inside entity_writer"
    - "Module-level logger via logging.getLogger(__name__) in entity_writer"

key-files:
  created:
    - packages/model-adapter/tests/test_narrator_role.py
    - packages/wiki-io/tests/test_inject_narrative.py
    - packages/wiki-io/tests/test_update_index_surgical.py
  modified:
    - packages/model-adapter/src/model_adapter/models.toml
    - packages/wiki-io/src/wiki_io/entity_writer.py
    - packages/wiki-io/src/wiki_io/update_index.py
    - .planning/REQUIREMENTS.md

key-decisions:
  - "Kept render_index and MAIN_INDEX_CATEGORIES as dead-but-importable in update_index.py (test_ports_importable.py asserts the import surface — removing them would break the smoke test). Only the wiki/index.md write block was deleted."
  - "Two commits for Plan 01: surgical update_index change (8664882) isolated from the rest of Plan 01 to keep blame small per plan §objective."

patterns-established:
  - "inject_narrative idempotency: prose.strip() + fixed wrapper '\\n{prose}\\n\\n' produces byte-identical output on repeated calls"
  - "Heading anchor regex: '^## Narrative[ \\t]*\\n' in MULTILINE mode to avoid matching '### Narrative' or '## Narrative Foo'"

requirements-completed:
  - SCANINT-02
  - SCANINT-04

duration: ~12min
completed: 2026-05-27
---

# Plan 45-01: Narrator role + inject_narrative + update_index surgical change Summary

**Wave 1 foundation shipped: narrator Bedrock role, idempotent `inject_narrative` helper, surgical removal of wiki/index.md from update_index, and the SCANINT-04 dual-writer rewrite — all four pieces Plan 03 depends on.**

## Performance

- **Duration:** ~12 minutes
- **Started:** 2026-05-27T14:47Z
- **Completed:** 2026-05-27T14:53Z
- **Tasks:** 5
- **Files modified:** 7 (4 src + 3 new tests + REQUIREMENTS.md)

## Accomplishments

- New `[roles.narrator]` block in packaged models.toml — same model as scanner for v1.8 (haiku-4-5), max_tokens=600 (prose only).
- `wiki_io.entity_writer.inject_narrative(page_path, prose)` — atomic body-region replacer for the `## Narrative` H2; idempotent under repeated calls (10 unit tests).
- `_scanner_frontmatter_for_node` renamed to `scanner_frontmatter_for_node` so Plan 03 can import it without reaching for a private name.
- `wiki_io.update_index.update_index(wiki)` no longer writes `wiki/index.md`; per-folder sub-indexes (`concepts/index.md`, `adrs/index.md`, etc.) preserved (4 unit tests).
- `.planning/REQUIREMENTS.md` SCANINT-04 rewritten to the exact wording from CONTEXT.md D-03 (dual-writer Step 12).

## Task Commits

1. **Task 1: Add `narrator` role to models.toml** — `5245596` (feat)
2. **Task 2: Rename `_scanner_frontmatter_for_node`** — `fe3b618` (refactor)
3. **Task 3: Add `inject_narrative` to entity_writer** — `2a30c8e` (feat)
4. **Task 4: Surgical removal of `wiki/index.md` write** — `8664882` (refactor)
5. **Task 5: Rewrite SCANINT-04** — `b372466` (docs)

## Files Created/Modified

- `packages/model-adapter/src/model_adapter/models.toml` — added `[roles.narrator]` block
- `packages/model-adapter/tests/test_narrator_role.py` — 3 new tests
- `packages/wiki-io/src/wiki_io/entity_writer.py` — renamed helper, added `inject_narrative` + logger
- `packages/wiki-io/tests/test_inject_narrative.py` — 10 new tests
- `packages/wiki-io/src/wiki_io/update_index.py` — removed `wiki/index.md` write from both library and CLI entries
- `packages/wiki-io/tests/test_update_index_surgical.py` — 4 new tests
- `.planning/REQUIREMENTS.md` — SCANINT-04 wording rewritten

## Decisions Made

- Followed plan with one minor judgment call: kept `render_index` and `MAIN_INDEX_CATEGORIES` exported (dead-but-importable) because `test_ports_importable.py` asserts `render_index` is callable. The plan explicitly allowed this branch ("If any external caller exists, leave the function in place and only delete the write block").

## Deviations from Plan

None — plan executed exactly as written. Two minor wording differences in CLI output strings (dry-run message and final `[ok]` line) match the plan's intent without copying its example string verbatim.

## Issues Encountered

None.

## Self-Check: PASSED

Verified at end of plan:

```text
uv run --package model-adapter pytest packages/model-adapter/tests/test_narrator_role.py -x  → 3 passed
uv run --package wiki-io pytest packages/wiki-io/tests/test_inject_narrative.py -x           → 10 passed
uv run --package wiki-io pytest packages/wiki-io/tests/test_update_index_surgical.py -x      → 4 passed
uv run --package wiki-io pytest packages/wiki-io/tests/test_entity_writer.py -x              → 45 passed (no regression after rename + new helper)
uv run --package wiki-io pytest packages/wiki-io/tests/test_scan_monorepo.py -x              → 29 passed (SCANINT-06 plugin smoke green)
uv run python -c "from wiki_io.entity_writer import inject_narrative, scanner_frontmatter_for_node; print('ok')"
uv run python -c "from model_adapter.loader import load_role_config; print(load_role_config('narrator'))"
```

## Next Phase Readiness

All four Plan 01 dependencies ready for Plan 03:

- `make_llm("narrator")` returns a working LLM (no KeyError).
- `inject_narrative(page_path, prose)` is importable and idempotent.
- `scanner_frontmatter_for_node` (public name) is importable.
- `update_index(wiki)` is safe to call from Step 12 after `generate_index(conn, wiki)` — they no longer fight over `wiki/index.md`.

Plan 02 (Wave 1 sibling) runs in parallel; Plan 03 (Wave 2) wires everything together.

---
*Phase: 45-scanner-integration*
*Completed: 2026-05-27*
