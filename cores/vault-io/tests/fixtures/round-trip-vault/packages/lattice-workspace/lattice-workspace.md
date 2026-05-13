---
title: lattice-workspace
category: package
summary: Python library (`pyyaml` only) that resolves the lattice workspace directory, reads/writes the v2 `.lattice.yaml` manifest with per-plugin version tracking, exposes typed path accessors, idempotently initializes the workspace, and signals plugin staleness via `warn_if_stale`.
status: active
package_path: packages/lattice-workspace
package_type: library
domain:
language: Python
depends_on: []
tags: [python, workspace, config, manifest, versioning, pyyaml]
updated: 2026-05-11
last_sync_commit: c2a5068
last_sync_at: 2026-05-10
workflow_hints:
  brainstorming: [context.md]
  planning:      [api.md, patterns.md]
  debugging:     [api.md, work.md]
tokens: 1632
---

# lattice-workspace

## Purpose

`lattice-workspace` is the shared config and path layer for the lattice ecosystem. It answers two questions every consumer plugin needs to answer the same way: "where does this repo's lattice workspace live?" and "what subdirectories live inside it?". Discovery walks up from `cwd` to the nearest `.git`, then consults `<repo>/.lattice.local.yaml` for an optional `lattice-directory` override (defaulting to `<repo>/lattice/`). Path accessors (`wiki_dir`, `work_dir`, `knowledge_dir`, `raw_dir`, `graph_dir`, `manifest_path`) compose paths beneath that workspace without doing I/O. `init()` bootstraps the workspace idempotently — creating the directory, writing `.lattice.yaml` (v2 format with per-plugin version tracking), recording the calling plugin + version, and ensuring `.lattice.local.yaml` is gitignored. `warn_if_stale(workspace, plugin, version)` compares the installed version against the `applied_version` stored in the manifest and signals when a plugin has been updated but not yet applied. YAML parsing now uses PyYAML (`yaml.safe_load` / `yaml.safe_dump`); manifest v1 files (bare string plugin lists) are coerced to v2 in memory on read.

## File map - lattice-workspace

Stdlib-only Python package; standard `src/`-layout, hatchling build, pytest tests.

- `pyproject.toml` — package metadata; declares `dependencies = []`; hatchling wheel target points at `src/lattice_workspace`.

### lattice-workspace/src/lattice_workspace/

- `__init__.py` — top-level surface; re-exports `LatticeConfig`, `resolve`, `init`, `warn_if_stale`, `PendingUpdate`.
- `_local_config.py` — internal flat YAML reader for `.lattice.local.yaml`. Strips inline `# …` comments and surrounding quotes; tolerant of malformed lines.
- `config.py` — discovery + `LatticeConfig` dataclass. `resolve()` walks up from `cwd` to find `.git`, then consults `.lattice.local.yaml` for `lattice-directory` (default `<repo>/lattice`). Also exposes a `python -m lattice_workspace.config` CLI that prints the resolved workspace.
- `init.py` — idempotent bootstrap: `mkdir`, optional `git init`, manifest write (v2), work-schema write, `.gitignore` append. `init(repo_root, *, plugin, version, workspace)` now takes a `version` param; stores `{name, installed_version, applied_version}` per plugin entry. Used by every plugin's `init` slash-command.
- `manifest.py` — PyYAML-backed reader/writer for `.lattice.yaml` v2. `read()` coerces v1 (bare string list) → v2 (dict list) in memory without touching disk. Plugin entries are `{name: str, installed_version: str|null, applied_version: str|null}`. PyYAML parses bare dates as `datetime.date`; `read()` normalizes to `str`.
- `paths.py` — six pure path accessors: `manifest_path`, `wiki_dir`, `raw_dir`, `work_dir`, `knowledge_dir`, `graph_dir`. No I/O.
- `render.py` — renders the workspace-level `CLAUDE.md` from `assets/CLAUDE.md.template` + the `.lattice.yaml` manifest. Updated to iterate plugin entries as dicts (`entry["name"]`). Called by `init()` to keep the workspace doc in sync.
- `schema.py` — embeds the work-item `.schema.md` (frontmatter spec). Idempotent `write_schema(work_dir)`.
- `versions.py` — **new in v0.3.0.** `warn_if_stale(workspace, plugin, version) -> bool`: returns `True` when the stored `applied_version` exists and differs from `version`; writes `installed_version=version` on the entry (applied_version left untouched). `pending_updates(workspace) -> list[PendingUpdate]`: pure read; returns all plugins where `installed_version != applied_version`. `PendingUpdate` is a frozen dataclass `(plugin, applied_version, installed_version)`.

#### lattice-workspace/src/lattice_workspace/assets/

- `CLAUDE.md.template` — workspace-level `CLAUDE.md` template rendered by `render.py` on every `init()` call.

### lattice-workspace/tests/

Pytest suite. One file per module, behavioral tests (idempotency, gitignore handling, override resolution, malformed-line tolerance).

- `test_config.py` — `resolve()` discovery + `LATTICE_DIRECTORY_KEY` overrides (relative, absolute, `~`-expansion).
- `test_init.py` — idempotent init, external-workspace `git init`, `.gitignore` append; v2 plugin dict assertions.
- `test_init_bumps_version.py` — verifies `installed_version` and `applied_version` are written correctly on first init and subsequent bumps.
- `test_init_records_version.py` — verifies the version stored in the manifest matches what `init()` was called with.
- `test_local_config.py` — `_local_config.read()` parsing edge cases.
- `test_manifest.py` — `.lattice.yaml` v2 round-trip + plugin list semantics; v1→v2 coercion.
- `test_manifest_v1_read.py` — v1 manifest coercion to v2 in memory.
- `test_manifest_v2_roundtrip.py` — v2 manifest write/read round-trip.
- `test_paths.py` — path composition.
- `test_pending_updates.py` — `pending_updates()` returns correct list when versions diverge.
- `test_render.py` — plugin block rendering with dict-style entries.
- `test_schema.py` — `write_schema()` idempotency.
- `test_warn_if_stale.py` — `warn_if_stale()` gate logic (no-op when absent/equal; write + return True when diverged).

## Sub-pages

- [[wiki/packages/lattice-workspace/api]]      — public API, config schema, path accessors, init flags
- [[wiki/packages/lattice-workspace/patterns]] — discovery walk-up, `.lattice.local.yaml` override, manifest format, work-schema sharing
- [[wiki/packages/lattice-workspace/work]]     — bugs, gaps, migration TODOs surfaced from the code
- [[wiki/packages/lattice-workspace/context]]  — concepts, ADRs, history, why this package exists

## Sources

- [[wiki/sources/2026-05-per-plugin-version-tracking-in-lattice-yaml]] — the design spec for v2 manifest, `warn_if_stale`, `pending_updates`, the `version=` kwarg on `init()`, and the PyYAML swap. Shipped in v0.3.0.
