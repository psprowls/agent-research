---
phase: 11-workspace-io-port-m1
plan: 02
subsystem: workspace
tags: [port, rebrand, lattice-workspace, graph-wiki]
requires:
  - workspace-io package skeleton (from Plan 01)
provides:
  - workspace_io.config.GraphWikiConfig dataclass + resolve(cwd)
  - workspace_io.config._find_repo_root, _resolve_workspace
  - workspace_io.manifest.read/write for .graph-wiki.yaml (v2-only)
  - workspace_io.paths.{manifest_path,wiki_dir,raw_dir,work_dir,knowledge_dir,graph_dir}
  - workspace_io.init(repo_root, plugin, version, workspace) idempotent bootstrap
  - workspace_io.render.render_workspace_claude_md + AUTO_START/AUTO_END markers
  - workspace_io.versions.{PendingUpdate, warn_if_stale, pending_updates}
  - workspace_io._local_config.read for .graph-wiki.local.yaml
  - workspace_io/assets/CLAUDE.md.template (packaged inside wheel)
  - Public re-export surface from workspace_io.__init__
affects:
  - packages/workspace-io/src/workspace_io/__init__.py (re-exports added)
  - packages/workspace-io/src/workspace_io/assets/.gitkeep (deleted; template took its place)
tech-stack:
  added: []
  patterns:
    - "from __future__ import annotations (every module)"
    - "yaml.safe_load(text) or {} (manifest read whitespace-only guard)"
    - "Path(__file__).resolve().parent / 'assets' / 'CLAUDE.md.template' (asset path resolution; works in editable + wheel)"
    - "dataclass(frozen=True) for GraphWikiConfig and PendingUpdate"
    - "Bespoke line parser in _local_config (no PyYAML; preserves Pitfall #2 mitigation)"
key-files:
  created:
    - packages/workspace-io/src/workspace_io/config.py
    - packages/workspace-io/src/workspace_io/manifest.py
    - packages/workspace-io/src/workspace_io/paths.py
    - packages/workspace-io/src/workspace_io/_local_config.py
    - packages/workspace-io/src/workspace_io/versions.py
    - packages/workspace-io/src/workspace_io/init.py
    - packages/workspace-io/src/workspace_io/render.py
    - packages/workspace-io/src/workspace_io/assets/CLAUDE.md.template
  modified:
    - packages/workspace-io/src/workspace_io/__init__.py
  deleted:
    - packages/workspace-io/src/workspace_io/assets/.gitkeep
decisions:
  - "D-03 implemented: config.resolve() raises RuntimeError naming 'graph-wiki-agent init' when no .graph-wiki.yaml ancestor is found (strict-manifest; env-override branch bypasses the check)"
  - "D-06 implemented: schema.py NOT ported; write_schema call dropped from init.py"
  - "D-09 implemented: paths.py ported verbatim with all 6 helpers (manifest_path, wiki_dir, raw_dir, work_dir, knowledge_dir, graph_dir)"
  - "D-11 implemented: .graph-wiki.yaml v2 schema preserved {version, initialized_at, plugins[{name, installed_version, applied_version}]}"
  - "D-12 implemented: init records graph-wiki-agent plugin with installed_version == applied_version"
  - "D-14 implemented: manifest.read() raises RuntimeError on v1 format; _coerce() dropped"
  - "D-15 implemented: _find_repo_root walks up for .git from cwd; fallback to workspace.parent in resolve()"
  - "D-16 implemented: LOCAL_CONFIG_FILENAME = '.graph-wiki.local.yaml'; LATTICE_DIRECTORY_KEY = 'graph-wiki-directory'; _GITIGNORE_ENTRY = '.graph-wiki.local.yaml'"
  - "Pitfall #2 mitigated: _local_config.py ported verbatim with no yaml import (bespoke parser preserved)"
  - "Pitfall #3 mitigated: AUTO_START/AUTO_END marker strings in render.py exactly match assets/CLAUDE.md.template ('<!-- workspace-io:auto:plugins:start -->' / '...:end -->')"
  - "_PLUGIN_POINTERS rebranded to {'graph-wiki-agent': 'see [`wiki/CLAUDE.md`](wiki/CLAUDE.md)'} (Open Question #1 — Claude's Discretion answer)"
metrics:
  duration_minutes: 8
  tasks_completed: 3
  files_changed: 9
  completed_date: 2026-05-18
---

# Phase 11 Plan 02: workspace-io Source Port Summary

Ported 8 source modules from `lattice-workspace` to `workspace_io` with the graph-wiki rebrand and the four locked behavioral divergences (D-03 strict manifest, D-06 schema drop, D-14 v1-raises, D-16 file/key rename). The full public surface — `GraphWikiConfig`, `init`, `resolve`, `PendingUpdate`, `pending_updates`, `warn_if_stale` — imports cleanly under `uv run --package workspace-io`, and the CLAUDE.md template ships inside the wheel.

## What Was Built

- `config.py` — `GraphWikiConfig` frozen dataclass + `resolve(cwd)` with `GRAPH_WIKI_WORKSPACE` env-override branch and the new D-03 strict-manifest check on the cwd-discovery branch (env branch deliberately bypasses the check so tests can use it pre-init). `_find_repo_root` and `_resolve_workspace` kept; `_main()` preserved for `python -m workspace_io.config`.
- `manifest.py` — v2-only `read()` (raises `RuntimeError` mentioning "version: 2" on v1; `_coerce()` dropped per D-14) and `write()` ported verbatim. `yaml.safe_load(...) or {}` guard preserved; PyYAML date-to-str normalization preserved.
- `paths.py` — verbatim port with the single `.lattice.yaml` → `.graph-wiki.yaml` swap. All six helpers retained.
- `_local_config.py` — verbatim port (no yaml import; bespoke line parser). Only docstring filename reference updated.
- `versions.py` — verbatim port; imports retargeted to `workspace_io.*`. `PendingUpdate`, `warn_if_stale`, `pending_updates` exported.
- `init.py` — idempotent bootstrap; default workspace `repo_root / "graph-wiki"`; `_GITIGNORE_ENTRY = ".graph-wiki.local.yaml"`. `write_schema` import and call removed (D-06). Plugin entry written with `installed_version == applied_version == version` (D-12).
- `render.py` — `AUTO_START`/`AUTO_END` renamed to `workspace-io:auto:plugins:{start,end}` (Pitfall #3). `_PLUGIN_POINTERS` reset to `{"graph-wiki-agent": "see [`wiki/CLAUDE.md`](wiki/CLAUDE.md)"}` (Open Question #1). All helpers (`_render_plugin_list`, `_render_full_template`, `_refresh_auto_block`, `render_workspace_claude_md`) ported verbatim modulo imports.
- `assets/CLAUDE.md.template` — prose rebrand (`# Graph-Wiki Workspace`, `graph-wiki-agent` owner, `.graph-wiki.yaml` / `.graph-wiki.local.yaml`, `graph-wiki-directory:`). Marker strings exactly match `render.py` (Pitfall #3 fix).
- `__init__.py` — replaced docstring-only stub with the full re-export block (`GraphWikiConfig, PendingUpdate, init, pending_updates, resolve, warn_if_stale`).

## Verification Results

All Task 1 acceptance criteria pass (recorded inline above): `class GraphWikiConfig`=1, `graph-wiki-agent init`=1, lattice refs=0, `_coerce`=0, v1-raises regex=2, paths `.graph-wiki.yaml`=1 / `.lattice.yaml`=0, `yaml` in `_local_config`=0, versions exports=3.

All Task 2 acceptance criteria pass: schema refs in `init.py`=0, `"graph-wiki"` literal=1, `"lattice"` literal=0, `.graph-wiki.local.yaml`=3, `workspace-io:auto:plugins` in `render.py`=4, lattice marker/plugin refs in `render.py`=0, `graph-wiki-agent` pointer=1, template marker start=1, template lattice markers=0. Public surface importable; `render._TEMPLATE_PATH.exists()` returns True.

All Task 3 sanity checks pass:

1. **D-03 strict** — `resolve("/tmp")` with `GRAPH_WIKI_WORKSPACE` unset raises `RuntimeError` containing `"graph-wiki-agent init"`.
2. **D-14 v1-raises** — `manifest.read()` on a `version: 1` file raises `RuntimeError`.
3. **D-04/D-09 paths** — `manifest_path("/tmp").name == ".graph-wiki.yaml"`; `wiki_dir("/tmp").name == "wiki"`.
4. **Render markers** — `render.AUTO_START == "<!-- workspace-io:auto:plugins:start -->"`, `AUTO_END` matches, `_PLUGIN_POINTERS` contains `"graph-wiki-agent"`.
5. **Asset template** — `_TEMPLATE_PATH` exists, body contains `workspace-io:auto:plugins:start`, no `lattice-workspace:auto` substring.
6. **Init idempotent + D-11/D-12** — `init()` called twice in a fresh tmpdir produces a v2 manifest with one `graph-wiki-agent` plugin entry where both versions equal `"0.1.0"`; `.gitignore` ends with `.graph-wiki.local.yaml`.

Final grep: `grep -rE 'LATTICE_WORKSPACE|LatticeConfig|lattice_workspace\.' packages/workspace-io/src/workspace_io/ --include="*.py"` returns zero matches.

## Commits

| Task | Commit  | Description                                                                  |
| ---- | ------- | ---------------------------------------------------------------------------- |
| 1    | e565988 | feat(11-02): port pure modules to workspace_io with rebrand                  |
| 2    | 6eda997 | feat(11-02): port init/render/asset and wire workspace_io public surface     |

(Task 3 is sanity-check only with no source changes; verification is folded into Tasks 1 and 2.)

## Decisions Made

1. **`_PLUGIN_POINTERS` populated with a single `graph-wiki-agent` entry pointing to `wiki/CLAUDE.md`** (RESEARCH.md Open Question #1, Claude's Discretion). All lattice plugin entries (`lattice-wiki`, `lattice-graph`, `lattice-curator`, `lattice-knowledge`, `lattice-workflows`) were dropped — no need to carry them through the rebrand.
2. **D-06 schema-drop comment kept literal-token-free.** The plan's acceptance grep `grep -cE 'write_schema|from.*schema'` flags any occurrence — the explanatory comment now says "work-layer schema bootstrap intentionally not ported" so the grep cleanly reports `0` without losing the human-readable rationale.
3. **`assets/.gitkeep` removed** in the same commit as `CLAUDE.md.template`. The placeholder was created in Plan 01 to keep the empty directory in git; it's redundant now.

## Deviations from Plan

None — plan executed exactly as written. The only minor adjustment (Decision #2 above) was the wording of one comment in `init.py` to make the literal-string grep clean while preserving the D-06 rationale; this is well within the plan's `<action>` description ("Drop `from lattice_workspace.schema import write_schema` import" and "Drop the `write_schema(...)` call") and changes no behavior.

## Threat Flags

None introduced. The threat register in the plan (`T-11-02` env tampering, `T-11-03` YAML parsing, `T-11-04` manifest write) is honored by the ported source:

- `T-11-02` mitigated — `Path(env).expanduser().resolve()` preserved in `config.py:62`.
- `T-11-03` mitigated — `yaml.safe_load(...) or {}` in `manifest.read()`; v1 format raises rather than silently coercing (D-14).
- `T-11-04` mitigated — `path.parent.mkdir(parents=True, exist_ok=True)` only creates dirs under the caller-supplied manifest path.
- `T-11-05` accepted — CLAUDE.md template ships inside the wheel; same risk profile as lattice source.
- `T-11-SC` accepted — no new packages installed (only stdlib + already-resolved `pyyaml` from Plan 01).

## Requirements Satisfied

- **WS-02** — `workspace_io.config.resolve()` walks up `.git`, honors `GRAPH_WIKI_WORKSPACE`, raises strict on missing manifest.
- **WS-03** — `workspace_io.manifest.read/write` operate on `.graph-wiki.yaml`; v1 raises per D-14.
- **WS-04** — `workspace_io.init` bootstraps workspace (dir + git init + manifest write + CLAUDE.md render + gitignore entry). Wiring into `graph-wiki-agent init` is Plan 05.
- **WS-05** — `paths.py`, `render.py`, `versions.py`, `_local_config.py`, `assets/CLAUDE.md.template` all ported.
- **WS-06** — `schema.py` verified work-layer-only and dropped (verdict recorded in Plan 11-RESEARCH; Plan 02 implements the drop).
- **WS-07** — `GRAPH_WIKI_WORKSPACE` is the only env var honored in `config.py`; `GraphWikiConfig` is the only dataclass name; no `LATTICE_WORKSPACE` / `LatticeConfig` / `lattice_workspace.` references survive (final grep).

## Phase 11 Success Criterion Progress

- **SC #1 (uv sync resolves workspace-io and tests pass)** — source side advanced. Tests are ported in Plan 03.
- **SC #2 (wiki-io delegates to workspace_io)** — unblocked. The public surface `GraphWikiConfig`, `resolve`, `paths.wiki_dir`, `_find_repo_root` all exist and import cleanly, ready for Plan 04's wiki-io delegation rewrite.

## Next Plan

Plan 03 ports the lattice-workspace test suite to `packages/workspace-io/tests/` with rebrand + the D-14 v1-test rewrite + the D-06 schema-test drop + the new strict-resolve test. The source ports here are confirmed working via the six in-process sanity checks, so test failures in Plan 03 will indicate test-logic issues, not stale source.

## Self-Check: PASSED

- Created files verified on disk:
  - FOUND: packages/workspace-io/src/workspace_io/config.py
  - FOUND: packages/workspace-io/src/workspace_io/manifest.py
  - FOUND: packages/workspace-io/src/workspace_io/paths.py
  - FOUND: packages/workspace-io/src/workspace_io/_local_config.py
  - FOUND: packages/workspace-io/src/workspace_io/versions.py
  - FOUND: packages/workspace-io/src/workspace_io/init.py
  - FOUND: packages/workspace-io/src/workspace_io/render.py
  - FOUND: packages/workspace-io/src/workspace_io/assets/CLAUDE.md.template
- Commits verified in git log:
  - FOUND: e565988 (Task 1)
  - FOUND: 6eda997 (Task 2)
