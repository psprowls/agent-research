---
title: workspace-io
category: package
summary: Workspace bootstrap, manifest IO, and config resolution for the graph-wiki ecosystem.
status: active
package_path: packages/workspace-io
package_type: library
language: python
exports: []
depends_on: []
depended_on_by: 0
tags: []
sources: 0
updated: 2026-05-18
tokens: 0
last_sync_commit:
last_sync_at:
workflow_hints:
  brainstorming: [context.md]
  planning:      [api.md, patterns.md]
  debugging:     [api.md, work.md]
---

# workspace-io

## Purpose
Workspace bootstrap, manifest IO, and config resolution for the graph-wiki ecosystem.

## File map - workspace-io
TODO — describe what this directory contains.

- `pyproject.toml` — TODO
- `README.md` — TODO

### workspace-io/src/
TODO — describe what this directory contains.


#### workspace-io/src/workspace_io/
TODO — describe what this directory contains.

- `__init__.py` — TODO
- `_local_config.py` — TODO
- `config.py` — TODO
- `init.py` — TODO
- `manifest.py` — TODO
- `paths.py` — TODO
- `render.py` — TODO
- `versions.py` — TODO

##### workspace-io/src/workspace_io/assets/
TODO — describe what this directory contains.

- `CLAUDE.md.template` — TODO

### workspace-io/tests/
TODO — describe what this directory contains.

- `.gitkeep` — TODO
- `test_config.py` — TODO
- `test_init.py` — TODO
- `test_init_bumps_version.py` — TODO
- `test_init_records_version.py` — TODO
- `test_local_config.py` — TODO
- `test_manifest.py` — TODO
- `test_manifest_v2_roundtrip.py` — TODO
- `test_paths.py` — TODO
- `test_pending_updates.py` — TODO
- `test_render.py` — TODO
- `test_warn_if_stale.py` — TODO

## Sub-pages
- [[api]]      — public API, exports, CLI subcommands
- [[patterns]] — key patterns and conventions
- [[work]]     — bugs, tech debt, features, open questions
- [[context]]  — concepts, decisions, ADRs, sources
