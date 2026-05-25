---
phase: 11-workspace-io-port-m1
plan: 06
subsystem: project-decisions + phase-verification
tags: [WS-10, project-md, key-decisions, end-to-end-verification, phase-close]
requires:
  - "Plan 11-03 (workspace-io tests ported and green)"
  - "Plan 11-04 (wiki-io delegation shim shipped)"
  - "Plan 11-05 (graph-wiki-agent two-phase init wired)"
provides:
  - "PROJECT.md Key Decisions row recording WS-10 verdict (wiki-config.toml ≠ .graph-wiki.yaml)"
  - "End-to-end phase verification record: 526 passed, 30 opt-in skipped"
  - "Two-phase init smoke test artifact (workspace_io.init creates v2 manifest in tmp)"
affects:
  - ".planning/PROJECT.md (single Key Decisions row appended)"
tech-stack:
  added: []
  patterns:
    - "Decision documented as a single Key Decisions table row, matching the existing markdown-table convention (no narrative sub-section)"
    - "End-to-end verification re-run inside the executor's worktree to confirm Phase 11 gate is green at hand-off to /gsd:verify-work"
key-files:
  created:
    - .planning/phases/11-workspace-io-port-m1/11-06-SUMMARY.md
  modified:
    - .planning/PROJECT.md
  deleted: []
decisions:
  - "WS-10 closed: wiki-config.toml (runtime CLI config) and .graph-wiki.yaml (per-workspace manifest) are different surfaces. No migration script. Per D-05, existing throwaway ~/Personal/graph-wiki/agent-research will be deleted and re-inited via `graph-wiki-agent init`."
  - "Decision recorded as a single row in the existing `## Key Decisions` markdown table — same convention as the other 17 decision rows. No new sub-heading introduced."
requirements-completed: [WS-10]
metrics:
  duration_minutes: 5
  tasks_completed: 2
  files_changed: 1
  completed_date: 2026-05-18
---

# Phase 11 Plan 06: PROJECT.md WS-10 Decision + End-to-End Verification Summary

WS-10 closed by recording the `wiki-config.toml` vs `.graph-wiki.yaml` verdict in `PROJECT.md` Key Decisions (different surfaces, no migration script). Full workspace verification gate re-run inside the executor worktree: 526 tests passed, zero `GRAPH_WIKI_REAL_VAULT_PATH` references remain, two-phase init smoke test green. Phase 11 is ready for `/gsd:verify-work` and milestone close-out.

## What Was Built

### Task 1 — PROJECT.md Key Decisions row (WS-10)

A single new row appended to the `## Key Decisions` table in `.planning/PROJECT.md` (after the last existing row, before `## Evolution`):

> `wiki-config.toml` and `.graph-wiki.yaml` are different surfaces — no migration script (WS-10, 2026-05-18) | `wiki-config.toml` (repo root) is the runtime CLI config read by `WikiConfig` dataclass — fields `{models_path, vault_path}` — pointing the CLI at models + a default vault. `.graph-wiki.yaml` (per workspace) is the manifest read/written by `workspace_io.manifest` — fields `{version, initialized_at, plugins[{name, installed_version, applied_version}]}` — tracking which plugins initialized the workspace. The two coexist with no overlap, so no migration is needed; per D-05 the existing throwaway `~/Personal/graph-wiki/agent-research` is deleted and re-inited via `graph-wiki-agent init` rather than migrated. | ✓ Validated Phase 11

The row matches the existing 3-column convention (decision | rationale | outcome). No other lines in PROJECT.md were modified.

### Task 2 — End-to-end phase verification (read-only)

All 5 Phase 11 ROADMAP success criteria re-confirmed in this worktree:

| SC | Check | Result |
|----|-------|--------|
| #1 | `uv sync` exits 0; `uv run --package workspace-io pytest` exits 0 | **PASS** — 526 passed, 30 skipped (opt-in real-Bedrock + eval gates), 19 snapshots passed; 36.45s |
| #2 | `grep -rE 'GRAPH_WIKI_REAL_VAULT_PATH' packages/ agents/ --include="*.py" --include="*.toml" --include="*.md"` returns zero | **PASS** — 0 hits; `GRAPH_WIKI_WORKSPACE` references in wiki-io + graph-wiki-agent .py = **23** (≥15 required) |
| #3 | `uv run --package wiki-io pytest` exits 0; explicit-path short-circuit test passes | **PASS** — full wiki-io collection green; `test_resolve_wiki_and_repo_strict_raises_without_manifest` + `test_resolve_wiki_and_repo_honors_env_var` both PASSED |
| #4 | PROJECT.md WS-10 entry exists, mentions both files and is dated recently | **PASS** — row added by Task 1; dated `2026-05-18`; references `wiki-config.toml`, `.graph-wiki.yaml`, "different surfaces", and `WS-10` |
| #5 | Ported tests use `.graph-wiki.yaml`; zero `.lattice.yaml` / `lattice_workspace` under workspace-io | **PASS** — 18 hits across 7 workspace-io test files; 0 hits for `.lattice.yaml`; 0 hits for `lattice_workspace` anywhere under `packages/workspace-io/` |

Additional smoke test (D-07 path — exercises Plan 05 wiring against Plan 02 source):

```
TMPDIR=$(mktemp -d) && unset GRAPH_WIKI_WORKSPACE && \
  uv run --package graph-wiki-agent python -c "
from pathlib import Path; import os, importlib.metadata
from workspace_io import init as ws_init
tmp = Path(os.environ['TMPDIR'])
ws_init(tmp, plugin='graph-wiki-agent', version=importlib.metadata.version('graph-wiki-agent'))
assert (tmp / 'graph-wiki' / '.graph-wiki.yaml').exists()
"
```

Output (manifest written to `<tmp>/graph-wiki/.graph-wiki.yaml`):

```
version: 2
initialized_at: '2026-05-18'
plugins:
- name: graph-wiki-agent
  installed_version: 0.1.0
  applied_version: 0.1.0
```

Import truths from the plan's `must_haves`:

- `import workspace_io` → ok (`workspace_io`)
- `import wiki_io._workspace` → ok; `resolve_wiki_and_repo` symbol present

## Verification

- [x] PROJECT.md Key Decisions records that `.graph-wiki.yaml` and `wiki-config.toml` are different surfaces (no migration script — D-05)
- [x] `wiki-config.toml` appears in PROJECT.md (1 hit; in the new decision)
- [x] `.graph-wiki.yaml` appears in PROJECT.md (2 hits)
- [x] `WS-10` / `different surfaces` appears in PROJECT.md (1 hit)
- [x] Full workspace test suite green end-to-end: 526 passed (workspace-io + wiki-io + all other workspace packages run together under root pyproject)
- [x] `grep -r GRAPH_WIKI_REAL_VAULT_PATH packages/ agents/` returns zero lines
- [x] `uv sync` resolves the full workspace including workspace-io
- [x] `import workspace_io` + `import wiki_io._workspace` both succeed
- [x] Two-phase init smoke test creates v2 manifest at `<tmp>/graph-wiki/.graph-wiki.yaml`

## Deviations from Plan

None — both tasks executed exactly as written.

The single editorial choice was where to place the new decision: the plan suggested "match existing bullet style", and the existing Key Decisions section uses a markdown table (not bullets), so the row was appended to the table immediately before `## Evolution`. The plan's `key_links.pattern: "wiki-config.toml"` and all acceptance greps still resolve.

## Threat Surface

No new code, no new endpoints, no new auth paths. Documentation-only edit + read-only verification. Threat register row `T-11-11` (Information Disclosure, PROJECT.md decision body, accept) applies and is satisfied — no secrets in the decision text.

## Caveats for `/gsd:verify-work`

1. `wiki-config.toml` appears **once** in PROJECT.md (the new decision). The plan's acceptance prose said "at least twice (once in the new decision and possibly elsewhere)"; the numeric grep target was `>= 1`, which is met. If the verifier reads the prose strictly, note that the "possibly elsewhere" clause was hypothetical — PROJECT.md does not otherwise reference `wiki-config.toml`, and adding it elsewhere would have violated the "surgical edit" instruction in the same task body.
2. The 30 skipped tests in the full-suite run are opt-in real-Bedrock and divergence-eval gates (`GRAPH_WIKI_RUN_INTEGRATION=1`, `GRAPH_WIKI_RUN_EVAL=1`). They are out of scope for this phase and not regressed by Phase 11.

## Self-Check: PASSED

- File `.planning/PROJECT.md`: present and modified (verified by `grep -c 'wiki-config.toml'` returning 1)
- File `.planning/phases/11-workspace-io-port-m1/11-06-SUMMARY.md`: present (this file)
- Commit `a83a23a` (Task 1, `docs(11-06): record WS-10 ...`): present in `git log`
