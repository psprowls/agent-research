---
phase: "06-prompt-content-port-divergence-eval"
plan: "01"
subsystem: "cores/prompt-sources"
tags: [prompt-port, vendoring, source-of-truth, lattice-wiki]
dependency_graph:
  requires: []
  provides:
    - "cores/prompt-sources/SKILL.md"
    - "cores/prompt-sources/agents/librarian.md"
    - "cores/prompt-sources/agents/ingestor.md"
    - "cores/prompt-sources/agents/linter.md"
    - "cores/prompt-sources/agents/scanner.md"
    - "cores/prompt-sources/references/"
    - "cores/prompt-sources/SOURCE-COMMIT"
  affects:
    - "pyproject.toml (workspace exclude added)"
    - "06-03 through 06-07 (fragment files reference these paths in provenance headers)"
tech_stack:
  added: []
  patterns:
    - "uv workspace exclude to prevent bare content directories from being treated as members"
key_files:
  created:
    - "cores/prompt-sources/SKILL.md"
    - "cores/prompt-sources/agents/librarian.md"
    - "cores/prompt-sources/agents/ingestor.md"
    - "cores/prompt-sources/agents/linter.md"
    - "cores/prompt-sources/agents/scanner.md"
    - "cores/prompt-sources/references/cross-tool-setup.md"
    - "cores/prompt-sources/references/detection-workflow.md"
    - "cores/prompt-sources/references/ingest-workflow.md"
    - "cores/prompt-sources/references/lint-workflow.md"
    - "cores/prompt-sources/references/monorepo-principles.md"
    - "cores/prompt-sources/references/obsidian-setup.md"
    - "cores/prompt-sources/references/page-formats.md"
    - "cores/prompt-sources/references/query-workflow.md"
    - "cores/prompt-sources/references/scan-workflow.md"
    - "cores/prompt-sources/references/wiki-schema.md"
    - "cores/prompt-sources/SOURCE-COMMIT"
  modified:
    - "pyproject.toml (added exclude = ['cores/prompt-sources'] to [tool.uv.workspace])"
decisions:
  - "Added uv workspace exclude for cores/prompt-sources to prevent bare content directory from causing uv sync failure (auto-fix: RESEARCH Pitfall 3 required no pyproject.toml, but uv glob still picks up the directory without a pyproject.toml — the real fix is exclude)"
metrics:
  duration: "~2 minutes"
  completed: "2026-05-15T19:40:18Z"
  tasks_completed: 1
  tasks_total: 1
  files_created: 17
  files_modified: 1
---

# Phase 06 Plan 01: Vendor Lattice-Wiki Canonical Sources Summary

Verbatim copy of lattice-wiki SKILL.md, 4 per-role agent files, and references/ from the sibling lattice repo into `cores/prompt-sources/` at upstream SHA ef05d991 — plus workspace exclude fix so uv treats the bare content directory correctly.

## What Was Built

`cores/prompt-sources/` is now the in-repo source-of-truth for lattice-wiki's canonical prompt content. All 5 principal files are byte-identical to the lattice checkout at commit `ef05d991a9ab1ea12b1bc7ebc1fb20ba70074030`. The `SOURCE-COMMIT` marker records the full upstream SHA for use in `# Source-commit:` headers in every prompt fragment written in plans 06-03 through 06-07.

The vendored directory intentionally has no `pyproject.toml`, `__init__.py`, or any Python file. It is documentation, not importable code.

## Tasks

| # | Task | Commit | Status |
|---|------|--------|--------|
| 1 | Vendor lattice-wiki canonical sources into cores/prompt-sources/ | a95a86d | Done |

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking] uv workspace glob picks up cores/prompt-sources/ even without pyproject.toml**

- **Found during:** Task 1 — `uv sync` after copying files
- **Issue:** The plan specified "Do NOT create a pyproject.toml" as the fix for RESEARCH Pitfall 3, but uv's `members = ["cores/*"]` glob matches any directory under `cores/`, not just directories containing `pyproject.toml`. The error was: `Workspace member .../cores/prompt-sources is missing a pyproject.toml (matches: cores/*)`.
- **Fix:** Added `exclude = ["cores/prompt-sources"]` to the `[tool.uv.workspace]` section of the workspace root `pyproject.toml`. This is the correct uv mechanism for excluding a directory from a wildcard member glob.
- **Files modified:** `pyproject.toml`
- **Commit:** a95a86d (included in the same commit as the vendored files)
- **Impact:** None on downstream plans — the exclusion is transparent; `cores/prompt-sources/` is still accessible for provenance reference by fragment files.

## Verification

All acceptance criteria confirmed:

- All 5 vendored .md files exist under `cores/prompt-sources/` and are byte-identical to lattice sources (verified via `diff -q`)
- `cores/prompt-sources/SOURCE-COMMIT` contains the full 40-char upstream lattice commit SHA: `ef05d991a9ab1ea12b1bc7ebc1fb20ba70074030`
- No `pyproject.toml`, `__init__.py`, or any Python file under `cores/prompt-sources/`
- `uv sync` completes without error (17 workspace packages resolved correctly)
- `cores/prompt-sources/references/` exists with all 10 reference files from the lattice skills directory

## Known Stubs

None. The vendored content is verbatim source material, not stub code.

## Threat Flags

No new threat surface introduced. The vendored files are static text committed to git; no network fetch, no runtime execution path. Threat model T-06-01 (tampering via vendored content) and T-06-02 (workspace collision) are both mitigated per plan.

## Self-Check

- [x] `cores/prompt-sources/SKILL.md` — FOUND
- [x] `cores/prompt-sources/agents/librarian.md` — FOUND
- [x] `cores/prompt-sources/agents/ingestor.md` — FOUND
- [x] `cores/prompt-sources/agents/linter.md` — FOUND
- [x] `cores/prompt-sources/agents/scanner.md` — FOUND
- [x] `cores/prompt-sources/SOURCE-COMMIT` — FOUND
- [x] `cores/prompt-sources/references/` — FOUND (10 files)
- [x] commit a95a86d — FOUND in git log
- [x] uv sync — PASSES

## Self-Check: PASSED
