---
title: lattice-work
category: package
summary: Bug / tech-debt / feature lifecycle plugin — lifecycle lint and sidecar generation for the unified work/ namespace.
status: active
package_path: plugins/lattice-work
package_type: plugin
domain:
language: Python
depends_on: []
tags: [plugin, work-tracker, consumer]
updated: 2026-05-11
last_sync_commit: 1e59687bc06b8b89b7480d866e3dab882a2381b6
last_sync_at: 2026-05-11
workflow_hints:
  brainstorming: [context.md]
  planning:      [api.md, patterns.md]
  debugging:     [api.md, work.md]
tokens: 1653
---

# lattice-work

## Purpose

A consumer plugin that adds bug / tech-debt / feature / initiative / spike tracking on top of the [[wiki/plugins/lattice-wiki/lattice-wiki]] vault. Work items live as markdown under `<workspace>/work/*.md`. This plugin owns lifecycle lint, sidecar `work-index.json` generation, planner-facing slash commands, and `lattice-workflows` consumption. The dependency direction is one-way: `lattice-work` → `lattice-wiki`, never reversed.

## File map

Plugin root: manifest, contributor guidance, commands, library, scripts, skill, and tests.

- `CLAUDE.md` — Claude Code guidance for contributors working inside this plugin
- `README.md` — User-facing plugin overview and setup instructions

### lattice-work/.claude-plugin/

- `plugin.json` — Claude Code plugin manifest (name, version, slash command declarations)

### lattice-work/commands/

Slash-command markdown files — each delegates to the corresponding script in `scripts/`.

- `archive.md` — Defines `/lattice-work:archive`: moves terminal-status items to `<workspace>/work/archived/`
- `lint.md` — Defines `/lattice-work:lint`: runs the 19 work_layer lifecycle lint rules
- `regen-index.md` — Defines `/lattice-work:regen-index`: regenerates `<workspace>/work-index.json` from current work items
- `status.md` — Defines `/lattice-work:status`: emits a one-screen rollup of counts plus in-flight and stuck items

### lattice-work/lib/

Pure-function library modules — no I/O at import time; all side effects are handled by `scripts/`.

- `__init__.py` — Package marker
- `archive.py` — Computes archive eligibility and builds an `ArchivePlan` (actions + skipped) from a list of work items
- `frontmatter.py` — stdlib-only YAML frontmatter parser for the subset of YAML used in work-item files
- `lifecycle_lint.py` — Implements the 19 lifecycle lint rules that run against `<workspace>/work/*.md` and the sidecar
- `plan_table.py` — Parses the `## Plan` markdown table from a work-item body into typed `PlanRow` objects
- `sidecar.py` — Builds and loads `<workspace>/work-index.json`; defines enum values for status, kind, severity, and blast_radius

### lattice-work/scripts/

CLI entry points — thin wrappers that parse arguments, call `lib/`, emit output, and exit with standardized codes.

- `__init__.py` — Package marker
- `archive_resolved.py` — CLI for `/lattice-work:archive`; moves terminal-status items to `<workspace>/work/archived/` and regenerates the sidecar
- `lint_work_layer.py` — CLI for `/lattice-work:lint`; runs the 19 lifecycle rules and reports findings grouped by severity
- `regenerate_work_index.py` — Canonical cross-plugin entry point that walks `<workspace>/work/*.md` and writes `<workspace>/work-index.json`
- `status_rollup.py` — CLI for `/lattice-work:status`; reads the sidecar and prints count breakdowns plus in-flight and stuck items

### lattice-work/skills/lattice-work/

- `SKILL.md` — Planner-facing skill: how to interpret lint output, trigger regen, archive items, and reason about the 7-state lifecycle

#### lattice-work/skills/lattice-work/references/

- `lifecycle-rules.md` — Full catalog of the 19 lifecycle lint rules: trigger conditions, rationale, and remedies
- `sidecar-schema.md` — Authoritative schema reference for `<workspace>/work-index.json` including field types and the freshness contract

### lattice-work/tests/

stdlib `unittest` test suite covering all library modules and script CLIs.

- `__init__.py` — Package marker
- `test_archive.py` — Unit tests for `lib/archive.py` (eligibility logic and plan building)
- `test_archive_script.py` — Unit tests for `scripts/archive_resolved.py` (CLI behaviour, dry-run, targeted mode)
- `test_frontmatter.py` — Unit tests for `lib/frontmatter.py` (inline lists, multiline lists, edge cases)
- `test_lifecycle_lint.py` — Unit tests for `lib/lifecycle_lint.py` (each of the 19 rules)
- `test_lint_script.py` — Unit tests for `scripts/lint_work_layer.py` (CLI output and exit codes)
- `test_plan_table.py` — Unit tests for `lib/plan_table.py` (table extraction and column matching)
- `test_regenerate_script.py` — Unit tests for `scripts/regenerate_work_index.py` (vault resolution, item reading, atomic write)
- `test_sidecar.py` — Unit tests for `lib/sidecar.py` (build, serialize, load, and staleness detection)
- `test_smoke.py` — End-to-end smoke tests that run the full pipeline against fixture vaults
- `test_status_script.py` — Unit tests for `scripts/status_rollup.py` (stuck-item detection, human and JSON output)

#### lattice-work/tests/fixtures/

Minimal fake vaults used by the test suite; each fixture represents a distinct scenario.

- `archive-vault/` — Terminal-status work items eligible for archiving
- `empty-vault/` — Empty `work/` directory for zero-item edge-case tests
- `happy-path-vault/` — Well-formed work items and stub source packages for baseline passing tests
- `lint-violations-vault/` — Intentionally malformed work items that trigger every lint rule
- `stale-sidecar-vault/` — Work items newer than the existing sidecar to test staleness detection

## Sub-pages

- [[wiki/plugins/lattice-work/api]]      — slash commands, cross-plugin entry point, lifecycle lint rules, sidecar schema
- [[wiki/plugins/lattice-work/patterns]] — key patterns, repository layout, downstream consumers, recorded cons
- [[wiki/plugins/lattice-work/work]]     — bugs, tech debt, features, open questions
- [[wiki/plugins/lattice-work/context]]  — concepts, decisions, ingested sources

## Lint split with lattice-wiki

Lifecycle lint (the 19 `work_layer` rules covering enum validity, state-conditional required fields, plan-table parsing, sidecar freshness, etc.) remains owned by this plugin. **Base structural lint** (frontmatter parses, staleness, duplicate titles) for `work/**` runs inside [[wiki/plugins/lattice-wiki/lattice-wiki]]'s `lint_wiki.py` — which now walks `<workspace>/` and discovers `work/**` as a sibling of `wiki/**` per [[wiki/sources/2026-05-workspace-relative-wikilinks-linter-and-content-rewrite]]. Work pages carry an `is_work` flag that exempts them from orphan detection (work items legitimately have no inbound wiki backlinks); see [[wiki/adrs/0015-workspace-root-wikilink-form]].
