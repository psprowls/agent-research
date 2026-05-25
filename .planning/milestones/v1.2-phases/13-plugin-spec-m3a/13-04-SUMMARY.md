---
phase: 13-plugin-spec-m3a
plan: "04"
subsystem: plugin-spec
tags: [spec, plugin, contract-index, shell-out-pattern, cross-cutting]
dependency_graph:
  requires: []
  provides:
    - .planning/spec/13-plugin-contract/CONTRACT-INDEX.md
    - .planning/spec/13-plugin-contract/SHELL-OUT-PATTERN.md
  affects:
    - .planning/spec/13-plugin-contract/init.md
    - .planning/spec/13-plugin-contract/scan.md
    - .planning/spec/13-plugin-contract/ingest.md
    - .planning/spec/13-plugin-contract/lint.md
    - .planning/spec/13-plugin-contract/query.md
    - .planning/spec/13-plugin-contract/log.md
tech_stack:
  added: []
  patterns:
    - Single-table verdict index for multi-command plugin contract
    - Cross-cutting decisions doc with per-section anchors (SO-NN)
key_files:
  created:
    - .planning/spec/13-plugin-contract/CONTRACT-INDEX.md
    - .planning/spec/13-plugin-contract/SHELL-OUT-PATTERN.md
  modified: []
decisions:
  - CONTRACT-INDEX.md uses 9-row verdict table (rename/reshape/drop) as single auditable Phase 14 entry point
  - SHELL-OUT-PATTERN.md bundles shell-out shape + agent rename map in one file (not split) per executor discretion
  - Upstream shim vendor/ sys.path injection dropped; uv run --project handles venv resolution
metrics:
  duration_minutes: 3
  completed_date: "2026-05-18"
  tasks_completed: 2
  files_created: 2
  files_modified: 0
---

# Phase 13 Plan 04: Cross-Cutting Spec Docs Summary

**One-liner:** Two cross-cutting spec docs anchoring the Phase 13 plugin contract: 9-row verdict table (CONTRACT-INDEX.md) and SO-01..SO-04 shell-out pattern + agent/skill rename map (SHELL-OUT-PATTERN.md).

## Tasks Completed

| Task | Name | Commit | Files |
|------|------|--------|-------|
| 1 | Author CONTRACT-INDEX.md | 860511e | `.planning/spec/13-plugin-contract/CONTRACT-INDEX.md` |
| 2 | Author SHELL-OUT-PATTERN.md | e114411 | `.planning/spec/13-plugin-contract/SHELL-OUT-PATTERN.md` |

## What Was Built

### CONTRACT-INDEX.md

The single auditable summary of the Phase 13 plugin contract. Contains:

- **Verdict vocabulary** (C-02): `rename`, `reshape`, `drop`, `defer` — defined once here so per-command files can reference without repetition
- **9-row command verdict table**: one row per upstream `/lattice-wiki:*` command, with verdict, target script path, target Python module, per-command spec link, and one-line rationale
  - 6 ported (rename or reshape): init, scan, ingest, lint, query, log
  - 3 dropped: archive, regen-index, status (work-layer, out of v1.2 scope per C-01)
- **Resulting plugin surface**: 6 files in `plugins/graph-wiki/commands/`, 0 for dropped commands
- **Phase 14 prerequisite ports** (VP-01): `wiki_io.lint_wiki` (~508 LOC) and `wiki_io.wiki_search` (~194 LOC) must land before `/lint` and `/query` shims can shell out

### SHELL-OUT-PATTERN.md

Cross-cutting decisions home, referenced by all per-command spec files via `§SO-NN` anchors:

- **SO-01**: `uv run --project "$AGENT_RESEARCH_ROOT" python3 "${CLAUDE_PLUGIN_ROOT}/skills/graph-wiki/scripts/<x>.py" "$@"` — the single required user config is one env var in shell rc
- **SO-02**: Shim template (Python fenced block) showing `wiki_io.<module>` import + bedrock subprocess branch — two changes from upstream: import source and bedrock dispatch mechanism
- **SO-03**: `plugin:` block in `.graph-wiki.yaml` with `backend_default: claude` and per-command `backend_overrides`; default-when-missing is `claude` everywhere
- **SO-04**: `_config.py` helper at `plugins/graph-wiki/skills/graph-wiki/scripts/_config.py` exposing `backend_for(cmd, repo=None) -> Literal["claude", "bedrock"]`
- **PD-01..PD-03**: Plugin discovery requirements (`$AGENT_RESEARCH_ROOT`, `$CLAUDE_PLUGIN_ROOT`, `uv`)
- **Agent/skill rename map**: 4 agent files (names stay, prose rebranded), skill dir wholesale rename `lattice-wiki/` → `graph-wiki/`, 12 reference docs inventory, `plugin.json` id rename

## Deviations from Plan

None — plan executed exactly as written. The one area of executor discretion invoked (CONTEXT.md "Claude's Discretion"): SHELL-OUT-PATTERN.md was kept as a single file (shell-out shape + rename map bundled) rather than split, because the combined file is reasonable in length (160 lines) and the plan explicitly listed bundling as an option.

## Self-Check: PASSED

**Files created:**

- FOUND: `.planning/spec/13-plugin-contract/CONTRACT-INDEX.md`
- FOUND: `.planning/spec/13-plugin-contract/SHELL-OUT-PATTERN.md`

**Commits:**

- FOUND: `860511e` — docs(13-04): author CONTRACT-INDEX.md verdict summary
- FOUND: `e114411` — docs(13-04): author SHELL-OUT-PATTERN.md cross-cutting decisions
