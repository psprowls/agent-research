---
gsd_state_version: 1.0
milestone: v1.6
milestone_name: TBD
status: Awaiting milestone scoping
stopped_at: v1.5 archived (retroactive close, audit skipped)
last_updated: "2026-05-25T22:41:58.504Z"
last_activity: 2026-05-25 — v1.5 archived; v1.6 ready for /gsd-new-milestone
progress:
  total_phases: 0
  completed_phases: 0
  total_plans: 0
  completed_plans: 0
  percent: 0
---

# Project State: agent-research

**Last updated:** 2026-05-20
**Updated by:** gsd-roadmapper (v1.4 roadmap created)

---

## Project Reference

See: `.planning/PROJECT.md` (updated 2026-05-20 after milestone v1.3 SHIPPED)

**Core Value:** Faithfully reproduce the upstream graph-wiki wiki-maintenance workflows while running entirely on AWS Bedrock with parallel subagents, so the same outcomes can be achieved at meaningfully lower cost than the current Claude-Code-hosted plugin.

**Current Focus:** v1.6 scoping (next: `/gsd-new-milestone`). Likely first phase: wire `graph-io` queries + `source-parser` spans into the scanner/librarian for code-aware grounding.

**North Star:** `graph-wiki-agent query "..."` returns answers as good as today's graph-wiki librarian, on cheaper Bedrock models, faster.

---

## Current Position

Phase: Milestone v1.5 complete
Plan: —
Status: Awaiting next milestone
Last activity: 2026-05-25 — Milestone v1.5 completed and archived

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
| Phases total (v1.4) | 5 |
| Phases complete (v1.4) | 5 |
| Requirements total (v1.4) | 23 |
| Requirements complete (v1.4) | 23 |
| Plans written (v1.4) | 8 |
| Plans complete (v1.4) | 8 |
| Phases total (v1.5) | 1 |
| Phases complete (v1.5) | 1 |
| Requirements total (v1.5) | 7 |
| Requirements complete (v1.5) | 7 |
| Plans written (v1.5) | 0 (retro) |
| Plans complete (v1.5) | 0 (retro) |

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
| 260521-kxi-fix-graph-wiki-plugin-docs-use-uv-run-py | Fix graph-wiki plugin docs to use `uv run --project "$AGENT_RESEARCH_ROOT" python` for shim scripts (`wiki_io` is a workspace package; bare `python` failed every `/graph-wiki:*` invocation with `ModuleNotFoundError`); 11 doc files, 26 invocation lines, plus stale "Standard library only" claim corrected in SKILL.md | (this commit) |
| 260521-lj3-workspace-io-tolerate-missing-plugins | Make `workspace_io.init.init()` heal a sparse `.graph-wiki.yaml` (`version: 2` but missing `plugins` key) via `data.setdefault("plugins", [])` instead of raising `KeyError`; unblocks `/graph-wiki:bootstrap` after a provisional manifest is seeded to satisfy the `resolve_wiki_and_repo()` chicken-and-egg in `detect_containers.py`; +1 production line, +1 regression test | 01cc109 |
| 260521-mfm-add-self-healing-uv-re-exec-to-graph-wik | Add self-healing uv re-exec to graph-wiki plugin shim scripts: new `_uv_reexec.ensure()` helper that walks up to find `packages/wiki-io/pyproject.toml` and re-execs under `uv run --project` when `wiki_io` isn't importable; wired into 6 shims; `GRAPH_WIKI_SHIM_REEXEC=1` guard prevents loops; bare `python <shim>.py` now Just Works | 9484187 |
| 260523-he3-revise-file-map-format-on-package-app-ov | Revise file-map format on package/app overview templates from heading+bullets to markdown-tables-per-major-folder: rewrite `build_file_map()` to emit H2 + per-major-folder H3 sections with `Path \| Kind \| Description` tables; rewrite `parse_section_entries()` as single in-process table parser with graceful no-op fallback for legacy old-format pages on disk; update package/app templates + round-trip fixture templates; rewrite page-formats.md spec + worked examples; update scanner.md emission + unfilled-template detection rule (table-row Description cells, with legacy-bullets-also-qualify clause); 17 new tests, full wiki-io suite 127 passed; SCN-003 unchanged (substring `## File map` still matches) | (this commit) |
| 260523-i35-add-testing-md-subpage-to-app-package-an | Add `testing.md` subpage to app/package/plugin directory templates: 5 new templates (`package/testing.md`, `app/{overview,testing}.md`, `plugin/{overview,testing}.md`), flat `app.md` removed, `package/overview.md` Sub-pages list gains `testing`; new `_is_test_path()` deterministic split rule (paths under `tests/`/`__tests__/`/`test/`/`spec/` OR test-config basenames: pytest.ini, conftest.py, tox.ini, jest.config.\*, vitest.config.\*, playwright.config.\*, cypress.config.\*, mocha.config.\*, .mocharc\*, karma.conf\*, ava.config.\*); new paired `build_file_maps()` API returns `(prod_block, test_block)`; legacy `build_file_map()` rewired as prod-only wrapper; `scan_monorepo.main()` populates both `file_map` and `file_map_testing`; `update_index.SUBPAGE_STEMS` includes `testing`; page-formats.md gets split-rule section + Testing sub-page worked example; scanner.md + scan-workflow.md describe two-block emission; +164 test lines (6 unit + 7 integration), 142 wiki-io tests pass | 683e00f |
| 260523-iws-rename-overview-pages | Rename wiki overview pages from `<dir-name>.md` to `overview.md` everywhere; wiki-io scanner + detection (`_wiki_relative_path_for`, `_load_existing_pages`), `ensure_domain_page` write path, `lint_wiki.py` overview detection, eval-harness citation resolvers, lint.py wikilink resolver; plugin scanner.md + scan-workflow.md + SKILL.md + README.md + lint-workflow.md + wiki-schema.md + page_categories prompt fragment; 7 live wiki pages via `git mv` in separate wiki repo, 29 files with wikilink rewrites; round-trip vault fixture 12 overview files renamed; iCloud Obsidian mirror synced (8 files removed/copied); locked decision: no `<dir>/<dir>.md` fallback; wiki-io 142 passed, graph-wiki-agent 650 passed | (this commit) |

---

## Deferred Items

### Acknowledged at v1.4 close (2026-05-25 — minimal close, audit skipped)

| Category | Item | Status |
|----------|------|--------|
| quick_task | 260521-gc0-tackle-four-lint-driven-fixes-w1-repo-di | missing — landed in commit but no SUMMARY tracked |
| quick_task | 260521-hfr-patch-graph-wiki-scanner-wikilink-emissi | missing — landed in commit but no SUMMARY tracked |
| quick_task | 260521-i26-add-container-dir-template-variable-for- | missing — landed in commit but no SUMMARY tracked |
| quick_task | 260521-kxi-fix-graph-wiki-plugin-docs-use-uv-run-py | missing — landed in commit but no SUMMARY tracked |
| quick_task | 260521-lj3-workspace-io-tolerate-missing-plugins | missing — landed in commit but no SUMMARY tracked |
| quick_task | 260521-mfm-add-self-healing-uv-re-exec-to-graph-wik | missing — landed in commit but no SUMMARY tracked |
| quick_task | 260523-he3-revise-file-map-format-on-package-app-ov | missing — landed in commit but no SUMMARY tracked |
| quick_task | 260523-i35-add-testing-md-subpage-to-app-package-an | missing — landed in commit but no SUMMARY tracked |
| quick_task | 260523-iws-rename-overview-pages | missing — landed in commit but no SUMMARY tracked |
| todo | 2026-05-21-bootstrap-interactive-flag | pending — not in v1.4 scope |
| todo | 2026-05-21-bootstrap-should-stub-empty-category-index-files | pending — not in v1.4 scope |

### Carried forward from v1.3 close — NOT addressed in v1.4

| Category | Item | Status |
|----------|------|--------|
| nyquist | 0/5 v1.1 + 0/6 v1.2 + 0/5 v1.3 + 0/5 v1.4 phases compliant | deferred to v1.5 (decision: retro-validate vs. disable toggle) |
| uat_gap | Phase 14 SC#4 plugin smoke transcript | deferred to v1.5 (capture as regression artifact later) |
| slug_fix | `librarian.py:21` `_SLUG_ONLY_RE` parity fix | deferred to v1.5 (not load-bearing) |

### Closed inline

| Category | Item | Status |
|----------|------|--------|
| uat_gap | Phase 18 SC#3 manual UAT (type `/init`, confirm native CLAUDE.md fires) | closed 2026-05-20 — user confirmed inline during v1.3 execution |

---

## Session Continuity

**Last session:** 2026-05-25T22:16:00.000Z
**Stopped at:** v1.5 retroactively closed (Phase 27 SUMMARY.md authored)
**Resume file:** .planning/phases/27-post-v1.4-foundation-changes/27-SUMMARY.md

**Critical context for next session:**

- v1.4 phases: 22 (internal Python API rename), 23 (MCP/CLI/docs external rename — depends on 22), 24 (eval-harness rename — independent), 25 (packages-dir misclassification fix — independent)
- Phase 22 touches: `packages/wiki-io/src/wiki_io/_workspace.py`, all 6 `commands/run_*.py`, CLI + MCP server call sites, ~20 test files with mock setups, `packages/workspace-io/src/workspace_io/config.py` (key rename + `resolve_workspace` promotion)
- Phase 23 touches: `agents/graph-wiki-agent/src/graph_wiki_mcp/server.py` (6 Pydantic models), `agents/graph-wiki-agent/src/graph_wiki_agent/cli.py` (7 flags + new `--repo`), `packages/wiki-io/src/wiki_io/scan_monorepo.py` (data field rename), `plugins/graph-wiki/` docs, integration test, brand-gate extension
- Phase 24 touches: `packages/eval-harness/src/eval_harness/{sweep,baseline,structural}.py` + `divergence/*.py` + their tests + `eval/README.md`
- Phase 25 touches: `packages/wiki-io/src/wiki_io/detect_containers.py`, `plugins/graph-wiki/skills/graph-wiki/scripts/detect_containers.py`, `agents/graph-wiki-agent/src/graph_wiki_agent/commands/init.py`, unit test + todo file move
- wiki-io write path: always goes through `packages/wiki-io/layout_io.py` — do not introduce `yaml.dump`
- MCP stdout discipline (`_StdoutGuard`) is non-negotiable for any new MCP tools
- models.toml defaults: Qwen3-32B fan-out + Qwen3-80B synthesis (v1.1 Phase 7)

---

*State initialized: 2026-05-13*
*v1.1 roadmap: 2026-05-15 — shipped 2026-05-17*
*v1.2 roadmap: 2026-05-17 — shipped 2026-05-19*
*v1.3 roadmap: 2026-05-19 — shipped 2026-05-20*
*v1.4 roadmap: 2026-05-20 — shipped 2026-05-25 (minimal close, audit skipped)*
*v1.5 milestone created retroactively: 2026-05-25 — Phase 27 SUMMARY.md is the canonical artifact*

## Operator Next Steps

- Start the next milestone with /gsd-new-milestone
