---
phase: 49
slug: builtin-kind-graph-io
status: draft
nyquist_compliant: true
wave_0_complete: false
created: 2026-05-27
---

# Phase 49 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest ≥8.3 + pytest-asyncio 1.3.0 (project default per CLAUDE.md §8) |
| **Config file** | `packages/graph-io/pyproject.toml` (pytest config inline) + `packages/graph-io/tests/conftest.py` |
| **Quick run command** | `uv run --package graph-io pytest tests/test_builtins.py -x` |
| **Full suite command** | `uv run --package graph-io pytest tests/ -x` |
| **Estimated runtime** | Quick: ~3-5s. Full graph-io suite: ~30-60s. |

---

## Sampling Rate

- **After every task commit:** Run quick command (target file for the task plus `tests/test_builtins.py`)
- **After every plan wave:** Run full suite command
- **Before `/gsd:verify-work`:** Full suite must be green: `uv run pytest packages/graph-io/tests/ packages/wiki-io/tests/test_entity_templates.py -x`
- **Max feedback latency:** < 60 seconds

---

## Per-Task Verification Map

> Task IDs follow `{phase}-{plan}-{task}` pattern. Plans/tasks are finalized by the planner; this map enumerates the verification rows the planner MUST register against each task. Update Task ID column once PLAN.md files are written.

| Task ID | Plan | Wave | Requirement | Threat Ref | Secure Behavior | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|------------|-----------------|-----------|-------------------|-------------|--------|
| 49-01-01 | 01 | 1 | BUILTIN-04 (schema) | — | `"builtin"` admitted in `_VALID_KINDS`; `dependency_uri`-shape `builtin_uri` returns `builtin:<lang>/<name>` | unit | `uv run --package graph-io pytest tests/test_queries.py::test_valid_kinds_includes_builtin tests/test_uri.py::test_builtin_uri_shape -x` | ❌ W0 (test_uri.py may not exist; add or fold into test_queries.py) | ⬜ pending |
| 49-01-02 | 01 | 1 | D-16 / SC#5 | — | `"builtin" not in wiki_io.entity_writer.ADMITTED_KINDS`; ADMITTED_KINDS docstring annotates the exclusion | unit | `uv run --package wiki-io pytest tests/test_entity_templates.py -x` | ✅ (bijection test already exists) | ⬜ pending |
| 49-02-01 | 02 | 1 | BUILTIN-01 (python emit) | T-49-01 (subprocess injection — N/A: literal argv) | `sys.stdlib_module_names` lookup produces `builtin:python/<name>` nodes for `pathlib`, `os`, `sys`, etc. | unit | `uv run --package graph-io pytest tests/test_builtins.py::test_python_stdlib_emits_builtin_nodes -x` | ❌ W0 | ⬜ pending |
| 49-02-02 | 02 | 1 | BUILTIN-02 + BUILTIN-03 (node emit + classification) | T-49-01 | `node -e` harvest → cache; `fs`/`node:fs`/`node:fs/promises` collapse to one `builtin:javascript/fs` node; `express` stays as `dependency` | unit + integration | `uv run --package graph-io pytest tests/test_builtins.py::test_node_stdlib_emits_builtin_nodes tests/test_builtins.py::test_node_dependency_vs_builtin_classification tests/test_builtins.py::test_node_spec_normalization -x` | ❌ W0 | ⬜ pending |
| 49-02-03 | 02 | 1 | BUILTIN-04 | — | Each Builtin node has `language`, `module_name`, `uri` in attrs | unit | `uv run --package graph-io pytest tests/test_builtins.py::test_builtin_node_attrs_and_uri -x` | ❌ W0 | ⬜ pending |
| 49-02-04 | 02 | 1 | BUILTIN-05 | — | One `used_by` edge per (package, builtin); `attrs_json.imported_symbols` is sorted union across files | unit | `uv run --package graph-io pytest tests/test_builtins.py::test_used_by_edge_dedup_and_symbol_union -x` | ❌ W0 | ⬜ pending |
| 49-02-05 | 02 | 1 | Idempotency | — | Running emit twice on the same input produces identical node + edge set | unit | `uv run --package graph-io pytest tests/test_builtins.py::test_emit_is_idempotent -x` | ❌ W0 | ⬜ pending |
| 49-02-06 | 02 | 1 | D-02 / Cache | T-49-02 (cache write outside workspace — N/A: path composed from `graph_dir`) | First scan writes `<workspace>/.graph/cache/node-builtins-<major>.json`; second scan reuses; differing major triggers re-harvest | unit | `uv run --package graph-io pytest tests/test_builtins.py::test_node_builtins_cache_lifecycle -x` | ❌ W0 | ⬜ pending |
| 49-02-07 | 02 | 1 | D-03 / Silent skip | T-49-03 (DoS via slow node — mitigated by `timeout=5`) | When `node` is missing AND cache file is absent AND no JS files were scanned: no error, no Builtin-JS nodes emitted, exit code 0 | unit | `uv run --package graph-io pytest tests/test_builtins.py::test_silent_skip_when_node_missing -x` | ❌ W0 | ⬜ pending |
| 49-03-01 | 03 | 2 | BUILTIN-06 (queries) | — | `queries.list_builtins(conn)` returns alphabetically-sorted Builtin `NodeRecord`s; `queries.describe_builtin(conn, language, module_name)` returns `BuiltinDescription` or `None` | unit | `uv run --package graph-io pytest tests/test_queries.py::test_list_builtins_alphabetical tests/test_queries.py::test_describe_builtin_returns_description tests/test_queries.py::test_describe_builtin_returns_none_when_missing -x` | ❌ W0 (extend existing test_queries.py) | ⬜ pending |
| 49-03-02 | 03 | 2 | BUILTIN-06 (CLI list) | — | `cg list-builtins` prints names line-per-line (human); JSON mode returns `[{kind, name, ...}, ...]`; exit 0; not-initialized returns exit 3 | CLI integration | `uv run --package graph-io pytest tests/test_cli_smoke.py::test_cg_list_builtins_smoke tests/test_cli_smoke.py::test_cg_list_builtins_json tests/test_cli_exit_codes.py::test_cg_list_builtins_not_initialized -x` | ❌ W0 (extend existing test_cli_*.py) | ⬜ pending |
| 49-03-03 | 03 | 2 | BUILTIN-06 (CLI describe) | — | `cg describe-builtin builtin:python/pathlib` prints `language: python`, `module_name: pathlib`, `used_by: ...`; JSON mode returns `BuiltinDescription` shape; missing URI exits with code 1 + stderr error | CLI integration | `uv run --package graph-io pytest tests/test_cli_describe.py::test_cg_describe_builtin_smoke tests/test_cli_describe.py::test_cg_describe_builtin_not_found tests/test_cli_describe.py::test_cg_describe_builtin_json -x` | ❌ W0 | ⬜ pending |
| 49-03-04 | 03 | 2 | End-to-end | — | `cg update` on a fixture repo (one Python pkg importing `pathlib`+`os`; one JS pkg importing `fs`+`express`) produces 2 Python Builtin nodes, 1 JS Builtin node, `express` as `dependency`, and matching `used_by` edges; second `cg update` is a no-op (no diff) | integration | `uv run --package graph-io pytest tests/integration/test_e2e_builtins.py -x` | ❌ W0 | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

**Threat refs:**
- T-49-01 — Subprocess argument injection via `node -e`. **Mitigation:** hardcoded literal argv; nothing from user input or scanned files flows into `subprocess.run`. Verified by inspection.
- T-49-02 — Cache file written outside workspace via symlink/traversal. **Mitigation:** path is composed from `graph_dir(workspace)`; no untrusted segments. Verified by inspection.
- T-49-03 — Slow `node` subprocess hangs the scanner. **Mitigation:** `timeout=5` on every `subprocess.run`; failure path → D-03 silent skip.

---

## Wave 0 Requirements

Pre-flight files / fixtures that MUST exist before per-task tests can pass:

- [ ] `packages/graph-io/tests/test_builtins.py` — new file, covers all `builtins.py` unit tests
- [ ] `packages/graph-io/tests/integration/test_e2e_builtins.py` — new file, end-to-end fixture with Python + JS package, verifies Builtin emission via the full `cg update` pipeline
- [ ] (Optional) `packages/graph-io/tests/test_uri.py` — if a dedicated URI test module is preferred; otherwise extend `tests/test_queries.py` with `test_builtin_uri_shape`

**Already in place (no Wave 0 work):**
- pytest framework + workspace plumbing (`uv run --package graph-io pytest`)
- Existing fixture patterns (`conftest.py`, `_git_repo.py`, `tests/integration/` directory)
- `tests/test_queries.py` (extend with Builtin describe/list rows)
- `tests/test_cli_describe.py` (extend with Builtin CLI rows)
- `tests/test_cli_smoke.py` (extend with `cg list-builtins`)
- `tests/test_cli_exit_codes.py` (extend with `cg list-builtins` / `cg describe-builtin` not-initialized)
- `packages/wiki-io/tests/test_entity_templates.py` (bijection invariant already defends `ADMITTED_KINDS`)

Framework install: not needed — `uv` workspace already pulls pytest into the lockfile.

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| `cg update --full` ship-note: pre-v1.9 unresolved Symbol cleanup | D-11 | One-time post-upgrade behavior; documented in ROADMAP / ship note. Automated test would require building a pre-v1.9 graph fixture. | After phase ship, on a real workspace with a pre-v1.9 graph: run `cg update --full` and verify unresolved Symbol nodes for stdlib calls are cleared (count drops to 0 for known stdlib modules). |

*All other phase behaviors have automated verification (see Per-Task Verification Map).*

---

## Validation Sign-Off

- [ ] All tasks have automated verify or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify (verified — every plan task above has a command)
- [ ] Wave 0 covers all MISSING references
- [ ] No watch-mode flags (all commands use `-x` for fail-fast, no `--watch`)
- [ ] Feedback latency < 60s
- [ ] `nyquist_compliant: true` set in frontmatter

**Approval:** pending
</content>
</invoke>