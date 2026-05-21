---
gsd_state_version: 1.0
milestone: v1.4
milestone_name: Workspace Path Resolution Cleanup
status: completed
stopped_at: Phase 26 context gathered
last_updated: "2026-05-21T18:19:54.311Z"
last_activity: 2026-05-21 -- Phase 26 marked complete
progress:
  total_phases: 5
  completed_phases: 5
  total_plans: 8
  completed_plans: 8
  percent: 100
---

# Project State: deep-agents

**Last updated:** 2026-05-20
**Updated by:** gsd-roadmapper (v1.4 roadmap created)

---

## Project Reference

See: `.planning/PROJECT.md` (updated 2026-05-20 after milestone v1.3 SHIPPED)

**Core Value:** Faithfully reproduce the upstream graph-wiki wiki-maintenance workflows while running entirely on AWS Bedrock with parallel subagents, so the same outcomes can be achieved at meaningfully lower cost than the current Claude-Code-hosted plugin.

**Current Focus:** Phase 26 — plugin-prompt-source-mirror-sync

**North Star:** `graph-wiki-agent query "..."` returns answers as good as today's graph-wiki librarian, on cheaper Bedrock models, faster.

---

## Current Position

Phase: 26 — COMPLETE
Plan: 1 of 4
Status: Phase 26 complete
Last activity: 2026-05-21 -- Completed quick task 260521-kxi: Fix graph-wiki plugin docs to use `uv run python` for shim scripts

Progress bar: `░░░░░░░░░░░░░░░░░░░░` 0% (0/4 phases)

---

## Performance Metrics

| Metric | Value |
|--------|-------|
| Phases total (v1.0) | 5 |
| Phases complete (v1.0) | 5 |
| Phases total (v1.1) | 5 |
| Phases complete (v1.1) | 5 |
| Requirements total (v1.1) | 29 |
| Requirements complete (v1.1) | 29 |
| Plans written (v1.1) | 39 |
| Plans complete (v1.1) | 39 |
| Phases total (v1.2) | 6 |
| Phases complete (v1.2) | 6 |
| Requirements total (v1.2) | 30 |
| Requirements complete (v1.2) | 30 |
| Plans written (v1.2) | 21 |
| Plans complete (v1.2) | 21 |
| Phases total (v1.3) | 5 |
| Phases complete (v1.3) | 5 |
| Requirements total (v1.3) | 19 |
| Requirements complete (v1.3) | 19 |
| Plans written (v1.3) | 25 |
| Plans complete (v1.3) | 25 |
| Phases total (v1.4) | 4 |
| Phases complete (v1.4) | 0 |
| Requirements total (v1.4) | 23 |
| Requirements complete (v1.4) | 0 |

---

## Accumulated Context

### Key Decisions

(Full log lives in `PROJECT.md → Key Decisions`. Decisions affecting v1.4:)

- **Hard rename, no compat** for MCP Pydantic fields (`vault_path` → `workspace_path`) and Typer flags (`--vault` → `--workspace`). DA-CLI integration test updates in the same phase as the schema rename (Phase 23).
- **`.graph-wiki.local.yaml` key** renamed `graph-wiki-directory` → `workspace-directory`. Hard cut; document in release notes only (matches v1.3 Phase 20 `--config` deletion precedent).
- **Scan JSON data field** `vault_path` renamed to `wiki_relative_path` (semantic matches actual usage — it is a relative path under the wiki, not a path to the wiki root). Plugin contract change handled in Phase 23.
- **`divergence/*.py` bare `vault: Path`** renamed to `wiki: Path` — these helpers receive the wiki path, not the workspace. Handled in Phase 24.
- **Wiki path derivation** uses `workspace_io.paths.wiki_dir(workspace_path)` everywhere; no string concatenation by callers.
- **Phase 23 depends on Phase 22** — MCP/CLI external renames must follow internal Python kwarg renames to avoid mid-flight inconsistency.
- **Phases 24 and 25 are independent** — eval-harness sweep and packages-dir fix can proceed in any order relative to each other and do not depend on Phase 22 or 23.

### Roadmap Evolution

- v1.4 roadmap created 2026-05-20: 4 phases, 23 requirements. Phase numbering continues from v1.3 Phase 21.
- Phase 26 added: plugin-prompt-source-mirror-sync

### Active TODOs

- `.planning/todos/pending/2026-05-20-fix-packages-dir-misclassification.md` → Phase 25 (PKGCLS-05)

### Blockers

(None.)

---

## Quick Tasks Completed

| Quick ID | Description | Commit |
|----------|-------------|--------|
| 260520-bgd-close-out-v1-3-deferred-items | Close out v1.3 deferred items: commit untracked archive files, backfill audit-open status for k9t+lf1, resolve stale open_questions in Phase 18 + 20 CONTEXT | (this commit) |
| 260521-ans-typer-help-ansi-strip | Fix 5 unit-test failures from ANSI escapes in Typer `--help` output: set `NO_COLOR=1`/`TERM=dumb`/`COLUMNS=200` on subprocess calls in test_cli_help.py, test_cli_query.py, test_trace_viewer.py | (this commit) |
| 260521-gc0-tackle-four-lint-driven-fixes | Four lint-driven fixes from /graph-wiki:lint: W1 honor `repo-directory:` in workspace manifest, W5 path-qualified wikilinks in package/domain overview templates, F1 exclude CLAUDE.md/AGENTS.md from lint enumeration, F2 write `tokens: null` on unsupported-model CountTokens ValidationException | (this commit) |
| 260521-hfr-patch-graph-wiki-scanner-wikilink-emissi | Patch graph-wiki scanner wikilink emission and add index stubs for empty sections: extend W5 fix to `package/context.md` + `domain/overview.md` templates, seed `concepts/sources/adrs/architecture/index.md` stubs in `init_wiki` (parity with `dependencies/index.md`) | (this commit) |
| 260521-i26-add-container-dir-template-variable-for- | Add `{{CONTAINER_DIR}}` template variable to `package/overview.md` so sub-page wikilinks resolve for packages in non-`packages/` containers (`agents/`, `plugins/`, `apps/`); document the new variable in `scanner.md`; live-wiki lint drops to 0 broken links / 0 orphans | (this commit) |
| 260521-kxi-fix-graph-wiki-plugin-docs-use-uv-run-py | Fix graph-wiki plugin docs to use `uv run --project "$DEEP_AGENTS_ROOT" python` for shim scripts (`vault_io` is a workspace package; bare `python` failed every `/graph-wiki:*` invocation with `ModuleNotFoundError`); 11 doc files, 26 invocation lines, plus stale "Standard library only" claim corrected in SKILL.md | (this commit) |

---

## Deferred Items

Items carried forward from v1.3 close — NOT in v1.4 scope:

| Category | Item | Status |
|----------|------|--------|
| nyquist | 0/5 v1.1 + 0/6 v1.2 + 0/5 v1.3 phases compliant | deferred to v1.5 (decision: retro-validate vs. disable toggle) |
| uat_gap | Phase 14 SC#4 plugin smoke transcript | deferred to v1.5 (capture as regression artifact later) |
| uat_gap | Phase 18 SC#3 manual UAT (type `/init`, confirm native CLAUDE.md fires) | closed 2026-05-20 — user confirmed inline during v1.3 execution |
| slug_fix | `librarian.py:21` `_SLUG_ONLY_RE` parity fix | deferred to v1.5 (not load-bearing) |

---

## Session Continuity

**Last session:** 2026-05-21T16:49:38.314Z
**Stopped at:** Phase 26 context gathered
**Resume file:** .planning/phases/26-plugin-prompt-source-mirror-sync/26-CONTEXT.md

**Critical context for next session:**

- v1.4 phases: 22 (internal Python API rename), 23 (MCP/CLI/docs external rename — depends on 22), 24 (eval-harness rename — independent), 25 (packages-dir misclassification fix — independent)
- Phase 22 touches: `packages/vault-io/src/vault_io/_workspace.py`, all 6 `commands/run_*.py`, CLI + MCP server call sites, ~20 test files with mock setups, `packages/workspace-io/src/workspace_io/config.py` (key rename + `resolve_workspace` promotion)
- Phase 23 touches: `agents/graph-wiki-agent/src/graph_wiki_mcp/server.py` (6 Pydantic models), `agents/graph-wiki-agent/src/graph_wiki_agent/cli.py` (7 flags + new `--repo`), `packages/vault-io/src/vault_io/scan_monorepo.py` (data field rename), `plugins/graph-wiki/` docs, integration test, brand-gate extension
- Phase 24 touches: `packages/eval-harness/src/eval_harness/{sweep,baseline,structural}.py` + `divergence/*.py` + their tests + `eval/README.md`
- Phase 25 touches: `packages/vault-io/src/vault_io/detect_containers.py`, `plugins/graph-wiki/skills/graph-wiki/scripts/detect_containers.py`, `agents/graph-wiki-agent/src/graph_wiki_agent/commands/init.py`, unit test + todo file move
- vault-io write path: always goes through `packages/vault-io/layout_io.py` — do not introduce `yaml.dump`
- MCP stdout discipline (`_StdoutGuard`) is non-negotiable for any new MCP tools
- models.toml defaults: Qwen3-32B fan-out + Qwen3-80B synthesis (v1.1 Phase 7)

---

*State initialized: 2026-05-13*
*v1.1 roadmap: 2026-05-15 — shipped 2026-05-17*
*v1.2 roadmap: 2026-05-17 — shipped 2026-05-19*
*v1.3 roadmap: 2026-05-19 — shipped 2026-05-20*
*v1.4 roadmap: 2026-05-20*
