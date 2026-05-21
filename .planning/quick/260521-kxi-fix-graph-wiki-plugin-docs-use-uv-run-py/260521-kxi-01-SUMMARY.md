---
phase: 260521-kxi
plan: 01
subsystem: plugins/graph-wiki
tags: [docs, plugin, uv-workspace, vault_io]
requires: []
provides:
  - "All graph-wiki plugin docs invoke bundled shims via `uv run --project \"$DEEP_AGENTS_ROOT\" python …` so `vault_io` resolves"
  - "SKILL.md Python-tools preamble accurately describes the shim model (in-workspace `vault_io` import, not stdlib-only)"
affects:
  - plugins/graph-wiki/agents/librarian.md
  - plugins/graph-wiki/agents/ingestor.md
  - plugins/graph-wiki/agents/linter.md
  - plugins/graph-wiki/agents/scanner.md
  - plugins/graph-wiki/commands/bootstrap.md
  - plugins/graph-wiki/skills/graph-wiki/README.md
  - plugins/graph-wiki/skills/graph-wiki/SKILL.md
  - plugins/graph-wiki/skills/graph-wiki/references/wiki-schema.md
  - plugins/graph-wiki/skills/graph-wiki/references/scan-workflow.md
  - plugins/graph-wiki/skills/graph-wiki/references/cross-tool-setup.md
  - plugins/graph-wiki/skills/graph-wiki/references/query-workflow.md
tech_stack:
  added: []
  patterns:
    - "`uv run --project \"$DEEP_AGENTS_ROOT\" python ${CLAUDE_PLUGIN_ROOT}/skills/graph-wiki/scripts/<tool>.py` as the canonical bundled-shim invocation across all plugin docs"
key_files:
  created:
    - .planning/quick/260521-kxi-fix-graph-wiki-plugin-docs-use-uv-run-py/260521-kxi-01-SUMMARY.md
  modified:
    - plugins/graph-wiki/agents/librarian.md
    - plugins/graph-wiki/agents/ingestor.md
    - plugins/graph-wiki/agents/linter.md
    - plugins/graph-wiki/agents/scanner.md
    - plugins/graph-wiki/commands/bootstrap.md
    - plugins/graph-wiki/skills/graph-wiki/README.md
    - plugins/graph-wiki/skills/graph-wiki/SKILL.md
    - plugins/graph-wiki/skills/graph-wiki/references/wiki-schema.md
    - plugins/graph-wiki/skills/graph-wiki/references/scan-workflow.md
    - plugins/graph-wiki/skills/graph-wiki/references/cross-tool-setup.md
    - plugins/graph-wiki/skills/graph-wiki/references/query-workflow.md
key_decisions:
  - "Use `uv run --project \"$DEEP_AGENTS_ROOT\"` (not bare `uv run`) so script invocations resolve the workspace regardless of the caller's cwd — matches the iron rule already in `plugins/graph-wiki/CLAUDE.md` line 23"
  - "Replace stale `Standard library only (via vault_io)` claim in SKILL.md with prose that accurately describes the shim-imports-`vault_io` model"
  - "Leave `commands/bootstrap.md:83` untouched — it is a path reference in a `## Script` bullet, not an invocation"
metrics:
  duration: "~5 minutes"
  completed_at: "2026-05-21"
  tasks_completed: 2
  files_modified: 11
  files_created: 1
---

# Phase 260521-kxi Plan 01: Fix graph-wiki plugin docs (use `uv run --project`) Summary

**One-liner:** Every documented `python ${CLAUDE_PLUGIN_ROOT}/skills/graph-wiki/scripts/<tool>.py` invocation across the 11 graph-wiki plugin doc files now runs via `uv run --project "$DEEP_AGENTS_ROOT" python …`, matching the shim model the plugin's own CLAUDE.md already mandates, so `vault_io` resolves on a fresh install.

## What changed

26 invocation lines across 11 plugin doc files rewritten in place, plus one stale prose sentence in `SKILL.md` corrected. Zero shim scripts modified. Zero behavior changes — this is purely a docs accuracy fix.

The shims under `plugins/graph-wiki/skills/graph-wiki/scripts/` are thin `from vault_io.<tool> import main` wrappers; `vault_io` is a `uv` workspace member (`packages/vault-io/`) and is only importable inside the uv-managed venv. Bare `python …shims…` therefore fails with `ModuleNotFoundError: No module named 'vault_io'`. The fix is to invoke through the workspace.

`--project "$DEEP_AGENTS_ROOT"` (not bare `uv run`) is required because users running slash commands have an arbitrary cwd. `DEEP_AGENTS_ROOT` is already documented as a prerequisite in the plugin README.

## Tasks completed

| # | Task | Commit | Files |
|---|------|--------|-------|
| 1 | Replace bare-python invocations with `uv run --project "$DEEP_AGENTS_ROOT"` across 11 plugin doc files | 5a0ff22 | 11 files modified (26 invocation lines) |
| 2 | Correct stale `Standard library only (via vault_io)` claim in SKILL.md Python-tools section | 36f4d56 | plugins/graph-wiki/skills/graph-wiki/SKILL.md |

## Verification

All three plan success criteria pass:

1. **Grep filter empty.** `grep -rn 'python \${CLAUDE_PLUGIN_ROOT}/skills/graph-wiki/scripts/' plugins/graph-wiki/ | grep -v 'uv run --project' | grep -v 'commands/bootstrap.md:83'` → empty. Every match is now prefixed; the lone path-reference bullet at `commands/bootstrap.md:83` is the documented exception.
2. **Shims untouched.** `git diff --stat c2706e3..HEAD -- plugins/graph-wiki/skills/graph-wiki/scripts/` → empty.
3. **End-to-end invocation works.** Ran `uv run --project "$DEEP_AGENTS_ROOT" python ${CLAUDE_PLUGIN_ROOT}/skills/graph-wiki/scripts/detect_containers.py --help` from `/tmp` with `DEEP_AGENTS_ROOT` and `CLAUDE_PLUGIN_ROOT` set. Printed argparse `--help` text from `vault_io.detect_containers` — no `ModuleNotFoundError`.

## Deviations from plan

None — plan executed exactly as written.

## Self-Check: PASSED

- File `.planning/quick/260521-kxi-fix-graph-wiki-plugin-docs-use-uv-run-py/260521-kxi-01-SUMMARY.md`: FOUND (this file)
- Commit `5a0ff22`: FOUND
- Commit `36f4d56`: FOUND
- All 11 modified doc paths verified via `git diff --stat`: FOUND
- Zero modifications under `plugins/graph-wiki/skills/graph-wiki/scripts/`: VERIFIED
