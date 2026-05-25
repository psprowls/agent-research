---
phase: 14
plan: "03"
subsystem: plugins/graph-wiki
tags: [plugin-port, graph-wiki, workspace-io, wiki-io, brand-rebrand]
dependency_graph:
  requires: [14-01, 14-02]
  provides: [plugins/graph-wiki scaffold, workspace_io plugin block validation, shim scripts]
  affects: [plugins/graph-wiki, packages/workspace-io, .brand-grep-allow]
tech_stack:
  added: []
  patterns: [SO-02 shim template, SO-04 _config.py, D-02 strict-raises manifest validation]
key_files:
  created:
    - plugins/graph-wiki/.claude-plugin/plugin.json
    - plugins/graph-wiki/CLAUDE.md
    - plugins/graph-wiki/README.md
    - plugins/graph-wiki/commands/init.md
    - plugins/graph-wiki/commands/scan.md
    - plugins/graph-wiki/commands/ingest.md
    - plugins/graph-wiki/commands/query.md
    - plugins/graph-wiki/commands/lint.md
    - plugins/graph-wiki/commands/log.md
    - plugins/graph-wiki/agents/ingestor.md
    - plugins/graph-wiki/agents/librarian.md
    - plugins/graph-wiki/agents/linter.md
    - plugins/graph-wiki/agents/scanner.md
    - plugins/graph-wiki/skills/graph-wiki/SKILL.md
    - plugins/graph-wiki/skills/graph-wiki/README.md
    - plugins/graph-wiki/skills/graph-wiki/references/ (12 files)
    - plugins/graph-wiki/skills/graph-wiki/scripts/_config.py
    - plugins/graph-wiki/skills/graph-wiki/scripts/init_vault.py
    - plugins/graph-wiki/skills/graph-wiki/scripts/scan_monorepo.py
    - plugins/graph-wiki/skills/graph-wiki/scripts/ingest_source.py
    - plugins/graph-wiki/skills/graph-wiki/scripts/lint_wiki.py
    - plugins/graph-wiki/skills/graph-wiki/scripts/wiki_search.py
    - plugins/graph-wiki/skills/graph-wiki/scripts/detect_containers.py
  modified:
    - packages/workspace-io/src/workspace_io/manifest.py
    - packages/workspace-io/tests/test_manifest.py
    - packages/workspace-io/tests/test_manifest_v2_roundtrip.py
    - .brand-grep-allow
decisions:
  - "SO-04: _config.py reads workspace_io.manifest instead of raw JSON; uses plugin.backend_overrides[cmd] -> plugin.backend_default -> 'claude' resolution order with except Exception fallback"
  - "SO-02: shim bedrock branch uses subprocess.run(['graph-wiki-agent', cmd] + sys.argv[1:], check=True) — no agent imports, no vendor/, no shell=True"
  - "C-01: no archive.md, regen-index.md, or status.md in commands/ — work-layer not ported in v1.2"
  - "lint.md reshape: dropped Pass 1b work lifecycle lint and Work lint section from Pass 3 report"
  - "D-04 README: fresh-write with 6 sections — not a rebrand of upstream README"
  - "Provenance refs in README files allowlisted in .brand-grep-allow (lattice-wiki as upstream origin)"
metrics:
  duration: "~2h 30m"
  completed: "2026-05-18"
  tasks_completed: 5
  files_created: 34
  files_modified: 4
---

# Phase 14 Plan 03: graph-wiki Plugin Port Summary

Plugin scaffold + workspace_io manifest extension completed through Task 3.5 (brand-gate sweep). SC#4 manual smoke checkpoint (Task 3.6) awaiting Pat to run `/graph-wiki:query` and paste transcript.

## What Was Built

**workspace_io manifest extension (Task 3.1):** Extended `manifest.read()` with strict-raises `[plugin]` block validation (D-02/SO-03 pattern). Fills default when missing, raises `RuntimeError` on unknown keys, invalid backends, or non-dict value. Added 5 new tests. Fixed pre-existing `test_v2_write_then_read` which expected no `plugin` key (Rule 1 auto-fix).

**plugins/graph-wiki scaffold (Task 3.2):** Full rebrand port of upstream lattice-wiki plugin. 34 files created across `.claude-plugin/`, `commands/`, `agents/`, `skills/graph-wiki/`. All 12 reference docs written with brand-swap applied. `lint.md` reshaped per C-01: dropped `### Pass 1b — Work lifecycle lint` and `## Work lint` from Pass 3 report. `lifecycle-rules.md` and `sidecar-schema.md` carry upstream-only notes since work-layer not ported in v1.2. SKILL.md lists 6 commands (no archive/regen-index/status).

**_config.py + 6 shim scripts (Task 3.3):** SO-04 `_config.py` reads `.graph-wiki.yaml` via `workspace_io.manifest.read()` with three-level resolution and `except Exception: return "claude"` tolerance. Six shims (init_vault, scan_monorepo, ingest_source, lint_wiki, wiki_search, detect_containers) follow SO-02 pattern: `from wiki_io.<module> import main as _core_main` in claude branch, `subprocess.run(["graph-wiki-agent", cmd] + sys.argv[1:], check=True)` in bedrock branch. No `vendor/`, no `shell=True`.

**README.md (Task 3.4):** Fresh-write with exactly 6 sections (D-04): What this plugin is, Setup, [plugin] block syntax, Commands, Not ported, See also. Explicitly documents the dual Claude/Bedrock surfaces, plugin block YAML validation rules, and lists the 3 work-layer commands not ported in v1.2.

**Brand-gate sweep (Task 3.5):** `bash scripts/check-brand.sh` passes. The only lattice tokens in plugins/graph-wiki/ are intentional provenance references in README files ("Ported from the upstream `lattice-wiki` plugin"). These were added to `.brand-grep-allow` with rationale notes.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Fixed test_v2_write_then_read after manifest.py extension**
- **Found during:** Task 3.1
- **Issue:** Pre-existing test did `assert result == data` where `data` had no `plugin` key, but `read()` now auto-populates the plugin default `{"backend_default": "claude", "backend_overrides": {}}`.
- **Fix:** Changed assertion to `expected = dict(data, plugin={"backend_default": "claude", "backend_overrides": {}})` and assert against that.
- **Files modified:** `packages/workspace-io/tests/test_manifest_v2_roundtrip.py`
- **Commit:** 63860bd

**2. [Rule 2 - Missing critical functionality] Added provenance entries to .brand-grep-allow**
- **Found during:** Task 3.5
- **Issue:** `scripts/check-brand.sh` failed on two README files containing "lattice-wiki" as intentional upstream-origin references.
- **Fix:** Added both files to `.brand-grep-allow` with Provenance/Upstream-reference rationale.
- **Files modified:** `.brand-grep-allow`
- **Commit:** b6c3669

## Pending: SC#4 Manual Smoke (Task 3.6)

Task 3.6 is the manual smoke checkpoint. Pat must:
1. Reload Claude Code (or restart to pick up the newly installed plugin)
2. Run `/graph-wiki:query "what is this plugin"` (or any query) in a repo that has `graph-wiki` installed
3. Paste the transcript into `.planning/phases/14-plugin-port-m3b/14-VERIFICATION.md`

The continuation agent will verify the transcript confirms the command resolves, SKILL.md loads, and the query workflow runs without "command not found" errors.

## Known Stubs

None — all scripts are functional shims (either delegate to wiki_io or shell out to graph-wiki-agent). The wiki workflow content is in the reference docs which are complete.

## Threat Flags

None — no new network endpoints, auth paths, or trust-boundary schema changes introduced. The `[plugin]` block in `.graph-wiki.yaml` is config-only, validated on read.

## Self-Check: PASSED

Commits verified:
- 63860bd — feat(14-03): extend workspace_io.manifest
- 79df269 — feat(14-03): scaffold plugins/graph-wiki
- cd4182a — feat(14-03): add _config.py + 6 shim scripts
- b74dc3b — docs(14-03): fresh-write README
- b6c3669 — chore(14-03): extend .brand-grep-allow

Key files verified present:
- plugins/graph-wiki/.claude-plugin/plugin.json ✓
- plugins/graph-wiki/README.md ✓
- plugins/graph-wiki/skills/graph-wiki/SKILL.md ✓
- plugins/graph-wiki/skills/graph-wiki/scripts/_config.py ✓
- `ls plugins/graph-wiki/skills/graph-wiki/references/ | wc -l` → 12 ✓
- BRAND-04 gate: PASSED ✓
