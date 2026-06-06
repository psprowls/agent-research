# Configurable state gate — design

**Date:** 2026-06-06
**Status:** Approved (brainstorm) — ready for implementation plan

## Problem

The git "state gate" decides whether a scan/ingest run is allowed to stamp
`last_updated_commit` provenance (the anchor that gates commit-driven narrative
refresh). Today the gate is hardcoded: `is_clean_main(repo)` in
`packages/wiki-io/src/wiki_io/git_state.py:52` requires HEAD to be on `main`
**and** the working tree to be clean.

After the 2026-06-05 git-history restructure, `develop` is the trunk branch, so
the gate now reports `allowed: false → "branch is 'develop', not 'main'"` on
every run, silently suppressing all narrative-provenance stamping on trunk.

There is also a vestigial `WikiConfig.state_gate_enabled` in
`packages/graph-wiki-core/src/graph_wiki_core/config.py` — TOML-based, wired to
nothing since Phase 20 (the `--config` pathway was removed in WMC-03). The
**entire `graph_wiki_core/config.py` module** (`WikiConfig`, `load_config`,
`get_config`, `_active_config`) is dead: it is imported only by its own
`tests/unit/test_config.py` and not exported from the package `__init__`. To
avoid two competing `state_gate_enabled` notions, this work removes the module
wholesale (see §4). The live, separate `workspace_io.config.GraphWikiConfig` is
unrelated and untouched.

## Goal

Make the gate configurable per-workspace in `<workspace>/.graph-wiki.yaml`:

1. Disable the gate entirely (writes always allowed).
2. When enabled, configure which branch(es) permit stamping.

Absent config preserves today's behavior (`enabled: true`, `branches: [main]`).

## Schema

A dedicated top-level `state_gate:` block in `.graph-wiki.yaml`, mirroring the
existing `plugin:` block pattern:

```yaml
state_gate:
  enabled: true        # default: true
  branches:            # default: [main]; any listed branch passes the gate
    - main
    - develop
```

- `enabled` — bool. `false` ⇒ the gate always allows (bypasses both the branch
  check and the clean-tree check).
- `branches` — non-empty list of branch names. When enabled, stamping is allowed
  iff HEAD is on one of these branches **and** the working tree is clean.
- A scalar `branch: main` is coerced to `["main"]` for ergonomics.

## Design

### 1. Config read & schema validation — `packages/workspace-io`

`.graph-wiki.yaml` is already parsed by `workspace_io.manifest.read()`, which
normalizes the optional `plugin:` block and injects defaults. Follow that exact
precedent:

- **`manifest.read()`** gains normalization for an optional top-level
  `state_gate` block. It always returns
  `{"enabled": bool, "branches": [str, ...]}`, defaulting to
  `{"enabled": True, "branches": ["main"]}` when the block is absent.
  Validation (same style as the existing plugin-block errors, raising
  `RuntimeError` with the file path):
  - `state_gate` must be a mapping.
  - `enabled`, when present, must be a bool.
  - `branches`, when present, must be a non-empty list of strings; a scalar
    string is coerced to a one-element list.
  - Unknown keys inside the block raise (mirrors `_KNOWN_PLUGIN_KEYS`).
- **`manifest.read_state_gate(manifest_path) -> tuple[bool, list[str]]`** — a
  thin typed accessor mirroring the existing `read_roles()`, returning
  `(enabled, branches)`.

This keeps all manifest-schema knowledge in `workspace_io` (the "manifest +
config IO" layer) and gate *semantics* out of it.

### 2. Gate logic & threading — `packages/wiki-io`

- **`git_state.py`**: generalize `is_clean_main(repo)` →
  **`is_clean_on_branches(repo, branches: list[str]) -> tuple[bool, str]`**.
  Same clean-tree logic; the branch check becomes `branch not in branches`, with
  reason `"branch is {branch!r}, not in {branches}"`. Only one caller, so no
  compatibility shim is kept.
- **`scan_monorepo.py`**: **`compute_state_gate(repo, workspace=None)`**:
  - `workspace is None` → defaults `(enabled=True, branches=["main"])`,
    preserving current behavior for any caller/test passing only `repo`.
  - else read config via
    `manifest.read_state_gate(workspace / ".graph-wiki.yaml")`.
  - `enabled is False` →
    `{"allowed": True, "reason": "state gate disabled in .graph-wiki.yaml", "head_commit": head_commit(repo)}`.
  - `enabled is True` → `is_clean_on_branches(repo, branches)`, wrapped into the
    existing `{allowed, reason, head_commit}` dict.
- **Callers** pass the workspace they already hold:
  `packages/graph-wiki-core/src/graph_wiki_core/commands/scan.py` (~line 902)
  and `packages/wiki-io/src/wiki_io/ingest_source.py` (~lines 256, 307). Exact
  local variable names / line numbers confirmed at implementation time (a
  pyright-fixes branch is merging concurrently and may shift lines, but not these
  surfaces).

### 3. Bootstrap seeding — confirm location at implementation time

The `plugin:` block carries inline comments, so it is seeded by the init
template (not `manifest.write()`, which is lossy and reconstructs the payload
from scratch). Add a commented `state_gate:` block to that same template so the
option is discoverable:

```yaml
state_gate:           # gate that guards last_updated_commit narrative stamping
  enabled: true       # set false to disable the gate entirely
  branches:           # branches on which stamping is allowed (clean tree also required)
    - main
```

Confirm whether the seed lives in `init.py` / `init_vault.py` during
implementation.

### 4. Remove the dead `graph_wiki_core/config.py` module

The legacy TOML config module is fully unused (imported only by its own test,
not exported from `__init__`, no production importers). Removing it eliminates
the confusing second `state_gate_enabled` that this feature would otherwise sit
next to.

- Delete `packages/graph-wiki-core/src/graph_wiki_core/config.py`.
- Delete `packages/graph-wiki-core/tests/unit/test_config.py`.
- Verify the package still imports and its suite is green after removal (no
  lingering references — confirmed: the only `graph_wiki_core.config` importers
  are in `test_config.py`).

## Testing (TDD, per-package)

- **`workspace-io`** — `read_state_gate` / `read()` normalization:
  - defaults when block absent (`True`, `["main"]`)
  - explicit `enabled` + `branches`
  - scalar `branch:` coerced to a one-element list
  - validation errors: non-bool `enabled`; empty `branches`; non-string list
    item; non-mapping `state_gate`; unknown key in block.
- **`wiki-io`** — `is_clean_on_branches`:
  - allowed branch + clean tree → `(True, "")`
  - HEAD on a non-listed branch → `(False, reason)`
  - dirty working tree on an allowed branch → `(False, "working tree is dirty")`
  - multi-branch list where HEAD matches a non-first entry → `(True, "")`
- **`wiki-io`** — `compute_state_gate`:
  - `enabled: false` → `allowed: True` regardless of branch / dirtiness
  - `enabled: true` honors `branches`
  - `workspace=None` keeps the `["main"]` default (backward compat)
- Update any existing test referencing `is_clean_main` directly.
- Delete `test_config.py` along with the dead module (§4); confirm the
  `graph-wiki-core` suite stays green.

## Docs

- README / `.graph-wiki.yaml` schema reference: document the `state_gate:` block
  alongside the `plugin:` block.
- `plugins/graph-wiki/skills/graph-wiki/references/scan-workflow.md`: note the
  gate is configurable.

## Non-goals / conventions

- **No migration.** Per repo convention (pre-v2.0, single developer), manifest
  changes are additive; an absent `state_gate` block defaults to today's
  behavior, so nothing on disk needs rewriting.
- `manifest.write()` losiness for hand-edited blocks (`plugin:`, `state_gate:`)
  is a pre-existing wart and not addressed here.
