---
title: "lattice-wiki-core: three wiki bug fixes"
category: source
summary: Bundled design spec for three independent lattice-wiki-core bugs — index taxonomy (work leak + invisible More section), lint --json null drift fields, and CLAUDE.md.template's unconditional AGENTS.md claim. All three shipped.
source_path: lattice/specs/2026-05-09-lattice-wiki-core-wiki-bugs-design.md
source_type: spec
source_date: 2026-05-09
authors: []
ingested: 2026-05-09
updated: 2026-05-09
tags: [lattice-wiki-core, bugs, lint, index, init]
tokens: 1455
---

# lattice-wiki-core: three wiki bug fixes

## TL;DR

A bundled implementation spec for three small, independent bugs in [[wiki/packages/lattice-wiki-core/lattice-wiki-core]]. All changes are confined to that package and the already-generated `lattice/wiki/CLAUDE.md`. Each bug ships with a focused test addition, and all three corresponding work items are now `status: resolved`.

## Key claims

1. **Bug 1 — index taxonomy.** `update_index.SUBPAGE_STEMS` must include `"work"` so that `packages/*/work.md` files don't leak into the `## Package` count (was 24 instead of 12). `CATEGORY_INDEX_FILES` gains a `"dependency"` entry. The `## More` loop always renders five categories — `architecture`, `source`, `concept`, `adr`, `dependency` — even at 0 pages, so they don't go invisible. `work` stays conditional (it's a workspace namespace, not a browsing entrypoint). See `packages/lattice-wiki-core/src/lattice_wiki_core/update_index.py:57` (`SUBPAGE_STEMS`) and `update_index.py:174` (`_ALWAYS_IN_MORE`).
2. **Bug 2 — lint `--json` null drift fields.** Five drift fields (`code_drift`, `container_drift`, `source_sync_drift`, `file_map_drift`, `package_sync_drift`) were initialized to `None` before conditional checks. `json.dumps(..., default=list)` does NOT coerce explicit `None` to `[]`, so callers couldn't distinguish "check skipped (no `repo_path`)" from "check ran clean". Fix: a module-level sentinel `_SKIPPED: dict = {"skipped": True}` initializes each field; `print_report()` and downstream callers test `isinstance(val, dict) and val.get("skipped")`. See `packages/lattice-wiki-core/src/lattice_wiki_core/lint_wiki.py:55` (sentinel) and `lint_wiki.py:168, 223-225, 231` (initializations).
3. **Bug 3 — CLAUDE.md.template AGENTS.md claim.** Line 6 of `CLAUDE.md.template` claimed "A parallel `AGENTS.md` exists for Codex/Cursor/Antigravity" unconditionally, but `init_vault.init_wiki` only writes `AGENTS.md` when `--tool` is `codex|cursor|antigravity|opencode|gemini-cli|all`. Default `claude-code` init left an inaccurate claim in the generated file. Fix (option a): remove the sentence entirely; no template variable added. See `packages/lattice-wiki-core/src/assets/CLAUDE.md.template:6`.
4. **Tests added.** `test_update_index_categories.py` (new), `test_lint_json_drift.py` (new), and one assertion in `test_init_vault_dirs.py`. All listed in the v0.3.0 entry of [[wiki/packages/lattice-wiki-core/lattice-wiki-core#File map]] under `tests/`.
5. **Acceptance criteria** (from spec): `pytest packages/lattice-wiki-core/` passes; `index.md` shows `## Package (12)` with `## More` always listing architecture/concepts/sources/adrs/dependencies; `lint_wiki.py --json` with no repo emits `{"skipped": true}` not `null`; live `lattice/wiki/CLAUDE.md` and the template no longer mention `AGENTS.md`; all three work items closed.

## Proposed changes (as shipped)

- `packages/lattice-wiki-core/src/lattice_wiki_core/update_index.py` — `SUBPAGE_STEMS` += `"work"`; `CATEGORY_INDEX_FILES` += `"dependency"`; new `_ALWAYS_IN_MORE` set.
- `packages/lattice-wiki-core/src/lattice_wiki_core/lint_wiki.py` — `_SKIPPED` sentinel; five field inits switched; `print_report()` guards rewritten.
- `packages/lattice-wiki-core/src/assets/CLAUDE.md.template:6` — sentence removed.
- `lattice/wiki/CLAUDE.md` — same one-line fix applied to the live generated file.
- `lattice/wiki/index.md` — regenerated.

## Surprises / contradictions

- None against the code. The spec matches the shipped implementation exactly (verified `update_index.py:57, 174`, `lint_wiki.py:55, 168, 223-231, 315-365`, and `CLAUDE.md.template:6`).
- ==Wiki drift surfaced during ingest:== `[[wiki/packages/lattice-wiki-core/api]]` listed `SUBPAGE_STEMS = {"api", "patterns", "issues", "context", "flows"}` — pre-fix value. Updated as part of this ingest to add `"work"` so the wiki agrees with the code.

## Touches

- [[wiki/packages/lattice-wiki-core/lattice-wiki-core]]
- [[wiki/packages/lattice-wiki-core/api]]
- [[wiki/packages/lattice-wiki-core/patterns]]
- [[wiki/packages/lattice-wiki-core/work]]
- [[wiki/packages/lattice-wiki-core/context]]

## Decisions triggered

None — these are bug fixes. The `_SKIPPED = {"skipped": True}` sentinel is a small JSON-schema choice scoped to one module; it doesn't warrant an ADR.

## Related work items

- [[work/2026-05-09-fix-index-taxonomy-and-top-level-sections]] — resolved
- [[work/2026-05-09-lint-json-drift-fields-emit-null]] — resolved
- [[work/2026-05-09-remove-agents-md-claim-from-claude-md-template]] — resolved

## Where it's cited in this wiki

- [[wiki/packages/lattice-wiki-core/lattice-wiki-core]]
- [[wiki/packages/lattice-wiki-core/api]]
- [[wiki/packages/lattice-wiki-core/patterns]]
- [[wiki/packages/lattice-wiki-core/work]]
- [[wiki/packages/lattice-wiki-core/context]]
