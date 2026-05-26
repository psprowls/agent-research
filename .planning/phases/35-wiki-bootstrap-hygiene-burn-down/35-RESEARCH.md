# Phase 35 Research: Wiki & Bootstrap Hygiene Burn-Down

**Research date:** 2026-05-26
**Researcher:** plan-phase orchestrator (acting as researcher)
**Status:** Ready for planning

## Objective

Determine the minimal, surgical implementation strategy for the 14 HYGIENE
requirements (HYGIENE-01..14) given that *substantial portions of the underlying
quick-task implementation already landed in prior phases*. Identify what is still
pending, what can be verified-and-closed, and where the regression fence (D-02
bootstrap-and-lint test) belongs.

## Domain Map

The phase touches three sub-systems:

1. **Wiki template/scanner stack** (`packages/wiki-io/`) — overview templates,
   `init_vault`, `scan_monorepo`, `lint_wiki`. HYGIENE-01..06 and HYGIENE-07
   (the four lint-driven fixes from `260521-gc0`) live here.
2. **Workspace IO** (`packages/workspace-io/`) — `init.py` (HYGIENE-08) and
   `config.py:resolve()` (HYGIENE-07's W1 piece).
3. **Bootstrap entrypoint + plugin docs** (`agents/graph-wiki-agent/src/graph_wiki_agent/cli.py`,
   `plugins/graph-wiki/agents/*.md`, `plugins/graph-wiki/skills/graph-wiki/`).
   HYGIENE-09..12 live here. HYGIENE-13..14 are verification artifacts.

## Current-State Audit (CRITICAL — drives plan sizing)

I verified the actual codebase state before scoping. **Most HYGIENE items are
already implemented from prior quick-task work** that was committed before the
v1.7 milestone began. The phase is largely a **verification + small-delta**
exercise, not a 14-task implementation push.

### Already implemented (verify-only):

| HYGIENE | Evidence in codebase |
|---|---|
| HYGIENE-01 | Templates `package/overview.md`, `app/overview.md`, `plugin/overview.md` already emit `[[wiki/{{CONTAINER_DIR}}/{{PACKAGE_SLUG}}/...]]`-prefixed wikilinks (lines 39-43 each). `package/context.md` and `domain/overview.md` use `[[wiki/...]]` prefix throughout. |
| HYGIENE-02 | `init_vault.py:55` defines `SECTION_INDEX_STUBS = {concepts, sources, adrs, architecture}` and emits stubs at lines 209-217. |
| HYGIENE-03 | `{{CONTAINER_DIR}}` already present in all three overview templates. `scanner.md` lines 48-50 document the derivation rule (parent folder of the page → `packages`/`agents`/`plugins`/`apps`). |
| HYGIENE-04 | `260523-he3-PLAN.md` evidence: `build_file_map()` rewritten to per-major-folder tables; templates updated; lint parser updated. |
| HYGIENE-05 | `testing.md` exists in all three template directories: `assets/page-templates/{package,app,plugin}/testing.md`. |
| HYGIENE-06 | `_wiki_relative_path_for` in `scan_monorepo.py` returns `overview.md` (not `<name>.md`) for all three branches (lines 630, 633, 635). |
| HYGIENE-07 | `workspace_io.config.resolve()` honors `repo-directory:` via `_repo_directory_override` (line 47-63); applied in both env-var branch (line 93) and discovery branch (line 109). `SCHEMA_FILENAMES = {"CLAUDE.md", "AGENTS.md"}` in `lint_wiki.py:62`, exclusion at lines 97 and 160. `update_tokens.py` has `_is_unsupported_model_error()` + `tokens: null` stamping (lines 44-58, 142-176). |
| HYGIENE-08 | `workspace_io/init.py:50` already does `data.setdefault("plugins", [])` before the `next()` lookup. |
| HYGIENE-10 | `plugins/graph-wiki/` docs reference `uv run --project "$AGENT_RESEARCH_ROOT" python ...`; bare `python plugins/...` invocations are absent (grep audit clean). |
| HYGIENE-12 | Same `SECTION_INDEX_STUBS` block in `init_vault.py` covers this — the pending todo `2026-05-21-bootstrap-should-stub-empty-category-index-files.md` is already satisfied by code that landed under the HYGIENE-02 footprint. |

### Still requires net-new work:

| HYGIENE | Gap |
|---|---|
| HYGIENE-09 | `agents/graph-wiki-agent/src/graph_wiki_agent/cli.py:bootstrap` (line 437) does NOT have self-healing `uv` re-exec via `Path(__file__).resolve()`. The existing `_uv_reexec.py` shim from quick `260521-mfm` lives under `plugins/graph-wiki/skills/graph-wiki/scripts/` and is wired into the 6 plugin shim scripts — but NOT into the `graph-wiki-agent` CLI entrypoint (which is the v1.3+ replacement for the shim scripts). Phase 35 must port the re-exec helper (or equivalent in-place check) into the agent CLI's `bootstrap` command, ensure it uses `Path(__file__).resolve()` (not `sys.argv[0]`), and uses a loop-prevention env var (`GRAPH_WIKI_BOOTSTRAP_REEXEC` or reuse `GRAPH_WIKI_SHIM_REEXEC`). |
| HYGIENE-11 | `cli.py:bootstrap` has no `--interactive` Typer flag (verified). The underlying machinery already exists: `wiki_io.init_vault.init_wiki()` accepts `non_interactive: bool` and `_resolve_pinned_containers()` (line 97) honors it. The work is wiring a new Typer option through `bootstrap()` → `run_init(interactive=...)` → `init_wiki(non_interactive=not interactive)`. Default OFF (`--interactive` absent ⇒ non_interactive=True, preserving today's silent-skip default). |
| HYGIENE-13 | `agents/graph-wiki-agent/tests/unit/test_cli_help.py` already exists with `NO_COLOR=1 TERM=dumb COLUMNS=200` env injection. Per D-04: verify 3/3 pass + add inline comment at the env-injection site linking back to `260521-ans`. |
| HYGIENE-14 | Per D-02/D-03: net-new automated test that bootstraps a sandbox into `tmp_path`, runs scan, runs `lint_wiki`, asserts zero broken wikilinks across `package`/`app`/`plugin` containers. Test lives in `packages/wiki-io/tests/test_bootstrap_e2e_no_broken_links.py` (planner picks final filename). This single test replaces the manual `/graph-wiki:query` transcript called for in the original SC#5. |

### Risk: Phase 14 SC#4 manual smoke transcript

The roadmap SC#5 references "manual `/graph-wiki:query` plugin smoke transcript
captured". D-03 in CONTEXT.md supersedes this with the automated test (D-02).
DISCUSSION-LOG.md records the swap. Plan B (verify-and-close) must document the
swap in the SUMMARY so future auditors can trace why HYGIENE-14 closed via a
pytest fixture rather than a manual transcript.

## Validation Architecture (Nyquist Dimension 8)

The bootstrap-and-lint regression test (D-02) IS the phase's primary validation
surface. It exercises:

- **`init_vault.init_wiki()`** — fresh bootstrap into `tmp_path` with at least
  one container of each of the three categories (`package`, `app`, `plugin`).
  The fixture must mock or stub the LLM scanner path; we want template-
  resolution-level validation, not LLM behavior. Use `wiki_io.layout_io`'s
  `ensure_subpage` / `ensure_domain_page` primitives directly, or use
  `init_vault.render_template()` on the three overview templates with the
  expected substitution dict.
- **`wiki_io.lint_wiki.scan()`** — invoked against the populated `tmp_path`
  vault; assert `report["broken_wikilinks"]` (or equivalent — confirm via
  reading the scan return shape) is zero.
- **All three container types** — single bootstrap call, three lint assertions,
  per CONTEXT.md specifics block.

Coverage matches:
- HYGIENE-01 (wikilinks prefixed `wiki/`)
- HYGIENE-02 (section index stubs exist)
- HYGIENE-03 (CONTAINER_DIR substitutes correctly for non-`packages/`)
- HYGIENE-06 (overview.md is the filename)
- HYGIENE-12 (category index stubs exist)

A second smaller test focused on `cli.py:bootstrap` exercise covers HYGIENE-09
(re-exec invocation succeeds from outside `uv run`) and HYGIENE-11
(`--interactive --help` shows the flag).

## Approach Decisions

1. **Two-plan split, sequenced.** Locked by CONTEXT.md D-01. Plan A does all
   edits (HYGIENE-01..12). Plan B is verify-and-close (HYGIENE-13..14). Plan B
   does NOT start until Plan A merges.

2. **Plan A internal ordering (planner discretion per CONTEXT.md D-01 line 51).**
   Group by surface area:
   - Wave 1 (independent): wiki-io templates / init_vault / lint / scan
     verification spot-checks (HYGIENE-01..06, HYGIENE-12 — mostly status
     audits since already implemented); workspace-io defensive heals
     (HYGIENE-07/08 — already implemented, audit-only); plugin doc shim audit
     (HYGIENE-10 — already implemented, audit-only).
   - Wave 2 (cli.py edits): HYGIENE-09 re-exec wiring + HYGIENE-11 `--interactive`
     flag. These both modify `cli.py` and `commands/init.py`, so single plan task
     handles both to avoid double-touching the same files.
   - Wave 3 (todo file moves): move both pending todos to `resolved/` after the
     code edits land (per CONTEXT.md decisions block).

3. **Plan B is purely verification.**
   - Run `test_cli_help.py` → confirm 3/3 pass. Paste output into DISCUSSION-LOG
     (HYGIENE-13).
   - Add inline comment to the env-injection block in `test_cli_help.py` per D-04.
   - Write `test_bootstrap_e2e_no_broken_links.py` (HYGIENE-14 closure artifact).
   - Note the D-03 swap in SUMMARY.

4. **Re-use the existing `_uv_reexec.py` for HYGIENE-09.** The helper at
   `plugins/graph-wiki/skills/graph-wiki/scripts/_uv_reexec.py` already
   implements walk-up-to-`packages/wiki-io/pyproject.toml`, loop guard via
   env var, and `os.execvpe`. The cleanest path is to:
   - Either copy/adapt that logic into `agents/graph-wiki-agent/src/graph_wiki_agent/cli.py`
     as a top-of-module `_ensure_uv()` call.
   - Or import the helper. **Constraint:** the helper is in a `plugins/` path
     not on the agent's import surface; copying ~30 lines is simpler than
     reorganizing the package layout. **Planner decision: copy + adapt
     in-place inside `cli.py`** (small, surgical, no new module needed).
   - Use `Path(__file__).resolve()` as the start point for the walk-up
     (per HYGIENE-09 explicit requirement; mirrors the existing shim).
   - Env-var guard: `GRAPH_WIKI_BOOTSTRAP_REEXEC=1` (distinct name from the
     plugin-shim guard so each can be set independently in tests).

## Anti-Patterns (do NOT do)

- **Do NOT introduce a `CONTAINER_DIRS` constant in wiki-io** — explicitly
  rejected in CONTEXT.md deferred. The filesystem-derived approach (D-05) is
  sufficient.
- **Do NOT extract a `NO_COLOR/TERM/COLUMNS` pytest fixture** — rejected in
  CONTEXT.md deferred. Just a comment.
- **Do NOT capture a manual `/graph-wiki:query` smoke transcript** — superseded
  by D-03; the automated test is the closure artifact.
- **Do NOT re-implement broken-wikilink resolution** in the new test — call
  `wiki_io.lint_wiki.scan()` and assert on its output (CONTEXT.md code_context
  line 101).
- **Do NOT modify `_wiki_relative_path_for`, `_load_existing_pages`, scanner
  routing, or template substitution sites that already work.** The audit
  confirms they're in place — only touch them if a verification reveals a
  regression.

## Files Reference Map (canonical refs for planner)

Same set as CONTEXT.md canonical_refs section — see CONTEXT.md for the full
list. The planner does not need to re-derive these.

## Open Questions for Planner

None remain. CONTEXT.md D-01..D-05 lock the structure; CONTEXT.md
"Claude's Discretion" leaves only filename + per-task ordering decisions
to the planner, both of which are mechanical.

## RESEARCH COMPLETE

- Phase: 35
- Research artifact: this file
- Net-new code: ~3 files (HYGIENE-09 re-exec block in `cli.py`,
  HYGIENE-11 flag wiring in `cli.py` + `commands/init.py`, HYGIENE-14 new
  pytest test file).
- Net-new doc: 1 comment in `test_cli_help.py` (HYGIENE-13).
- Verify-and-close: 10 HYGIENE items via the new automated test + audit
  evidence in Plan B SUMMARY.
- Recommended structure: 2 plans, sequenced (Plan A → Plan B), per
  CONTEXT.md D-01.

---

*Phase: 35-wiki-bootstrap-hygiene-burn-down*
*Research completed: 2026-05-26*
