---
phase: 20-workspace-manifest-model-config
plan: 01
subsystem: workspace-io
tags: [python, workspace-io, manifest, yaml, schema, pytest, tdd]

# Dependency graph
requires:
  - phase: 11-workspace-io-port-m1
    provides: "workspace_io.manifest read/write skeleton with v2 envelope (version, initialized_at, plugins[], plugin singular block)"
provides:
  - "workspace_io.manifest.write() preserves per-plugin roles[] on round-trip"
  - "workspace_io.read_roles(plugin_name, manifest_path) -> list[dict] public accessor"
  - "workspace-io README documents the per-plugin roles: schema (4 fields + example)"
affects: [20-02, 20-03]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Thin IO accessor returning list[dict] — semantics (validation, defaulting, merge) deferred to loader (model-adapter)"
    - "Conditional payload field on write: empty/absent collapse to no key on disk (no roles: [] artifact)"

key-files:
  created: []
  modified:
    - packages/workspace-io/src/workspace_io/manifest.py
    - packages/workspace-io/src/workspace_io/__init__.py
    - packages/workspace-io/tests/test_manifest.py
    - packages/workspace-io/tests/test_manifest_v2_roundtrip.py
    - packages/workspace-io/README.md

key-decisions:
  - "RoleConfig field set locked at exactly {name, model_id, region, max_tokens, max_concurrency} — mirrors models.toml; no speculative temperature/top_p/stop_sequences fields (loader doesn't read them today)"
  - "IO layer stays semantics-free: read_roles returns plain list[dict], no role-dict validation, no defaulting — those live in model_adapter.loader (Plan 02)"
  - "Empty/absent roles collapse identically on write: no roles: [] artifact for plugins with no overrides"

patterns-established:
  - "TDD RED→GREEN cycle: 6 tests committed failing first (RED), implementation committed second (GREEN)"
  - "Read-only accessor pattern for cross-package data: thin lookup + list[dict] return, no dataclass coupling at IO boundary"

requirements-completed: [WMC-01, WMC-05a]

# Metrics
duration: 20min
completed: 2026-05-19
---

# Phase 20 Plan 01: Workspace Manifest roles[] Round-Trip + read_roles Accessor Summary

**`manifest.write()` now preserves per-plugin `roles[]` round-trip (fixing the silent field-drop bug at lines 69-75), new `workspace_io.read_roles(plugin_name, manifest_path)` public accessor returns the role-dict list (or `[]`), and the workspace-io README documents the schema with a two-role example.**

## Performance

- **Duration:** ~20 min
- **Started:** 2026-05-19
- **Completed:** 2026-05-19
- **Tasks:** 2 (Task 1 TDD: RED + GREEN; Task 2: docs)
- **Files modified:** 5
- **Tests added:** 6 (2 round-trip + 4 accessor)
- **Tests passing:** 576 across the full uv workspace (no regression)

## Accomplishments

- Fixed the per-plugin payload comprehension in `manifest.write()` so `roles[]` survives write → read. Empty list / absent key both produce no `roles:` key on disk.
- Added `read_roles(plugin_name, manifest_path) -> list[dict]` to `manifest.py`. Handles all three empty cases (missing file, absent plugin, plugin without `roles` key) by returning `[]` rather than raising.
- Exported `read_roles` on `workspace_io.__init__.__all__` (alphabetical position respected).
- Added 4 new tests to `test_manifest.py` pinning the `read_roles` contract (named plugin, missing plugin, no roles key, missing manifest).
- Added 2 new tests to `test_manifest_v2_roundtrip.py` pinning the populated- and absent-roles round-trip.
- Rewrote `packages/workspace-io/README.md` (was a 10-line stub): one-sentence purpose, Manifest schema section, Per-plugin `roles:` subsection with field table + copy-pasteable two-role example, "Reading roles programmatically" snippet, original provenance note preserved at the bottom.
- Zero references to deprecated surface (`wiki-config.toml`, `--config`, `CODE_WIKI_CONFIG`) — README reflects the post-deletion world per Plan 03 intent.

## Task Commits

Atomic commits per the project's recent style:

1. **Task 1 RED:** `13bf453` — `test(20-01): add failing tests for roles[] round-trip + read_roles (RED)` — 6 new tests fail on `ImportError: cannot import name 'read_roles'`.
2. **Task 1 GREEN:** `8f674b2` — `feat(20-01): preserve plugins[].roles[] in manifest.write + add read_roles accessor (GREEN)` — implementation lands; all 20 manifest tests pass; full 576-test suite green.
3. **Task 2:** `e4b1c6b` — `docs(20-01): document plugins[].roles[] schema + read_roles in workspace-io README` — README documentation portion of SC#5.

## Files Created/Modified

- `packages/workspace-io/src/workspace_io/manifest.py` — `write()` payload now conditionally carries `roles`; added `read_roles()` function (37 LOC including docstring).
- `packages/workspace-io/src/workspace_io/__init__.py` — added `read_roles` import + `__all__` entry.
- `packages/workspace-io/tests/test_manifest.py` — added 4 `test_read_roles_*` tests + `_v2_with_roles` helper.
- `packages/workspace-io/tests/test_manifest_v2_roundtrip.py` — added `test_v2_roles_roundtrip` + `test_v2_roles_absent_round_trips_cleanly`.
- `packages/workspace-io/README.md` — full rewrite (10 lines → 72 lines).

## Decisions Made

- **Field set is exactly {name, model_id, region, max_tokens, max_concurrency}.** Locked against the loader's actual consumption today; matches `models.toml` per-role shape; mirrors the live `graph-wiki/.graph-wiki.yaml` example.
- **`read_roles` returns plain `list[dict]`.** Keeps the IO layer stable across future role-field additions; downstream `RoleConfig` dataclass binding belongs in the loader (Plan 02).
- **Empty/absent roles unified on write.** A plugin with `roles: []` or no `roles` key both produce no `roles:` key on disk — avoids writing semantically empty `roles: []` artifacts.

## Deviations from Plan

None. The plan executed exactly as written: 2 tasks, 6 tests, 3 source files modified, 1 README rewrite, 3 atomic commits (TDD RED/GREEN for Task 1 + docs for Task 2). All 8 acceptance-criteria grep gates pass; full suite stays green at 576/576.

## Issues Encountered

None.

## User Setup Required

None — pure source/test/docs change inside `packages/workspace-io/`.

## TDD Gate Compliance

- **RED gate:** `13bf453` — `test(20-01): add failing tests for roles[] round-trip + read_roles (RED)` — 6 new tests fail with `ImportError: cannot import name 'read_roles'`.
- **GREEN gate:** `8f674b2` — `feat(20-01): preserve plugins[].roles[] in manifest.write + add read_roles accessor (GREEN)` — all 20 manifest-suite tests pass; 576-test full uv workspace suite stays green.
- **REFACTOR gate:** not required — implementation was already minimal (Karpathy §2).

## Self-Check

Files modified (verified via `git log --stat e4b1c6b ^b364559`):
- `packages/workspace-io/src/workspace_io/manifest.py` — VERIFIED MODIFIED (commit `8f674b2`)
- `packages/workspace-io/src/workspace_io/__init__.py` — VERIFIED MODIFIED (commit `8f674b2`)
- `packages/workspace-io/tests/test_manifest.py` — VERIFIED MODIFIED (commit `13bf453`)
- `packages/workspace-io/tests/test_manifest_v2_roundtrip.py` — VERIFIED MODIFIED (commit `13bf453`)
- `packages/workspace-io/README.md` — VERIFIED MODIFIED (commit `e4b1c6b`)

Commits verified via `git log --oneline -5`:
- `e4b1c6b` — FOUND
- `8f674b2` — FOUND
- `13bf453` — FOUND

Acceptance-criteria grep gates (re-run post-commit):
- `grep -n '"roles"' packages/workspace-io/src/workspace_io/manifest.py | grep -v '^#'` → 3 matches (≥2 required) — PASS
- `grep -n 'def read_roles' packages/workspace-io/src/workspace_io/manifest.py` → 1 match — PASS
- `grep -n 'read_roles' packages/workspace-io/src/workspace_io/__init__.py | grep -v '^#'` → 2 matches (≥2 required) — PASS
- `grep -c '^def test_v2_roles_roundtrip' packages/workspace-io/tests/test_manifest_v2_roundtrip.py` → 1 — PASS
- `grep -c '^def test_v2_roles_absent_round_trips_cleanly' packages/workspace-io/tests/test_manifest_v2_roundtrip.py` → 1 — PASS
- `grep -c '^def test_read_roles_' packages/workspace-io/tests/test_manifest.py` → 4 (≥4 required) — PASS
- `grep -c '^## ' packages/workspace-io/README.md` → 2 (≥2 required) — PASS
- `grep -nE 'model_id|max_concurrency|max_tokens' packages/workspace-io/README.md` → 9 matches (≥3 required) — PASS
- `grep -c 'read_roles' packages/workspace-io/README.md` → 3 (≥1 required) — PASS
- `grep -c 'wiki-config.toml\|--config\|CODE_WIKI_CONFIG' packages/workspace-io/README.md` → 0 (must be 0) — PASS
- `uv run --package workspace-io pytest -x` → `576 passed, 32 skipped` — PASS
- `uv run --package workspace-io python -c "from workspace_io import read_roles; print('OK')"` → `OK` — PASS

## Self-Check: PASSED

## Known Stubs

None. `read_roles` is intentionally a thin lookup; the validation / defaulting / merge work it stops short of is owned by `model_adapter.loader` in Plan 02 (documented in the docstring and the README).

## Threat Flags

None — no new network endpoints, auth paths, or trust boundaries. The change is read/write of an already-trusted on-disk YAML file under the workspace root that the user owns.

## Next Phase Readiness

- Plan 02 (`model-adapter.loader` workspace-aware override) can now call `from workspace_io import read_roles` and receive a `list[dict]` shaped exactly like `models.toml`'s per-role table.
- Plan 03 (deletion sweep of `--config` / `CODE_WIKI_CONFIG` / `models_path`) has no surface area changes here — workspace-io README already reflects the post-deletion world.

---
*Phase: 20-workspace-manifest-model-config*
*Completed: 2026-05-19*
