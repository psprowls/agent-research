---
phase: 35
plan: 01
type: execute
status: complete
date: 2026-05-26
requirements:
  - HYGIENE-01
  - HYGIENE-02
  - HYGIENE-03
  - HYGIENE-04
  - HYGIENE-05
  - HYGIENE-06
  - HYGIENE-07
  - HYGIENE-08
  - HYGIENE-09
  - HYGIENE-10
  - HYGIENE-11
  - HYGIENE-12
files_changed:
  - agents/graph-wiki-agent/src/graph_wiki_agent/cli.py
  - agents/graph-wiki-agent/src/graph_wiki_agent/commands/init.py
  - agents/graph-wiki-agent/tests/unit/test_cli_bootstrap.py
  - .planning/todos/pending/2026-05-21-bootstrap-interactive-flag.md
  - .planning/todos/pending/2026-05-21-bootstrap-should-stub-empty-category-index-files.md
---

# Plan 01 — Wiki & Bootstrap Hygiene (HYGIENE-09 + HYGIENE-11 net-new)

## Summary

Closed the net-new portion of Phase 35's HYGIENE burn-down:

- **HYGIENE-09** — Added `_ensure_uv_workspace()` self-healing `uv` re-exec
  helper at the top of `agents/graph-wiki-agent/src/graph_wiki_agent/cli.py`.
- **HYGIENE-11** — Added `--interactive` Typer flag to the `bootstrap` command
  and threaded the boolean through `run_init` → `init_wiki` as
  `non_interactive=not interactive`.

HYGIENE-01..08, HYGIENE-10, HYGIENE-12 are closed as **verified-in-place** —
already implemented during prior quick-task commits per the RESEARCH.md audit
table. Grep-based spot checks (recorded below) confirm each line of evidence.

Both pending bootstrap todos are moved from `.planning/todos/pending/` to
`.planning/todos/resolved/` via `git mv` (history preserved).

## HYGIENE-09 implementation detail

`_ensure_uv_workspace()` is defined at `cli.py:16` and invoked at module top
level at `cli.py:62`, BEFORE the `from graph_wiki_agent.commands.init import
run_init` line at `cli.py:64`. Helper:

- Probes `import wiki_io` first (no-op if already importable).
- On ImportError/ModuleNotFoundError, walks up from
  `Path(__file__).resolve().parent` looking for
  `<ancestor>/packages/wiki-io/pyproject.toml`. Stops at filesystem root via
  `candidate == candidate.parent`.
- On a hit, re-execs the current process under
  `os.execvpe("uv", ["uv", "run", "--project", <pkg_dir>, "python",
  sys.argv[0], *sys.argv[1:]], new_env)` with
  `GRAPH_WIKI_BOOTSTRAP_REEXEC=1` env-var guard so a second re-exec cannot fire.

Mirrors the shape of `plugins/graph-wiki/skills/graph-wiki/scripts/_uv_reexec.py`
but uses a distinct env-var name (`GRAPH_WIKI_BOOTSTRAP_REEXEC`, not
`GRAPH_WIKI_SHIM_REEXEC`) so each subsystem's guard is independent.

## HYGIENE-11 implementation detail

`bootstrap` Typer command in `cli.py` exposes `--interactive` between `--repo`
and `--json`. The Typer body calls `run_init(..., interactive=interactive,
...)`. `commands/init.py:run_init` accepts `interactive: bool = False` (placed
after `force`, before the Path kwargs) and passes
`non_interactive=not interactive` to `init_wiki`. Default `interactive=False`
preserves current behaviour (silent-skip ambiguous container rows).

### mcp/server.py:219 audit

The MCP wrapper at `agents/graph-wiki-agent/src/graph_wiki_agent/mcp/server.py:219`
calls `run_init(topic=..., tool=..., force=..., workspace_path=...)` — all
keyword arguments. The new `interactive: bool = False` default preserves
existing MCP behaviour exactly. **No edit required** in `mcp/server.py`.

## Audit for verified-in-place HYGIENE items

Spot checks confirming each item is already implemented (grep evidence
captured at execution time):

| ID | File / line | Evidence |
|----|-------------|----------|
| HYGIENE-01 | `packages/wiki-io/src/wiki_io/assets/page-templates/package/overview.md:39-43` | All five sub-page wikilinks use `[[wiki/{{CONTAINER_DIR}}/{{PACKAGE_SLUG}}/...]]` form |
| HYGIENE-02 | `packages/wiki-io/src/wiki_io/init_vault.py:55, :209` | `SECTION_INDEX_STUBS = {concepts, sources, adrs, architecture}` defined; emitted in init loop |
| HYGIENE-03 | `packages/wiki-io/src/wiki_io/assets/page-templates/{package,app,plugin}/overview.md` | `{{CONTAINER_DIR}}` token present in all three overview templates |
| HYGIENE-04 | `packages/wiki-io/src/wiki_io/scan_monorepo.py:518` (`build_file_maps`) | Per-major-folder file-map builder present |
| HYGIENE-05 | `packages/wiki-io/src/wiki_io/assets/page-templates/{package,app,plugin}/testing.md` | All three `testing.md` files exist |
| HYGIENE-06 | `packages/wiki-io/src/wiki_io/scan_monorepo.py:617-619` | `apps/<name>/overview.md`, `domains/<d>/packages/<name>/overview.md`, `<vault_dir>/<name>/overview.md` |
| HYGIENE-07 | `packages/workspace-io/src/workspace_io/config.py:47` (`_repo_directory_override`); `packages/wiki-io/src/wiki_io/lint_wiki.py:62` (`SCHEMA_FILENAMES = {"CLAUDE.md", "AGENTS.md"}`, exclusion at :97, :160) | `repo-directory:` honored; CLAUDE.md/AGENTS.md excluded from lint |
| HYGIENE-08 | `packages/workspace-io/src/workspace_io/init.py:50` | `data.setdefault("plugins", [])` present |
| HYGIENE-10 | `plugins/graph-wiki/agents/{ingestor,librarian,linter,scanner}.md`, `plugins/graph-wiki/skills/graph-wiki/README.md` | All contain `AGENT_RESEARCH_ROOT` references; bare `python plugins/...` absent (grep clean) |
| HYGIENE-12 | Same `SECTION_INDEX_STUBS` block in `init_vault.py:55` | The pending todo `bootstrap-should-stub-empty-category-index-files` is satisfied by the same code that closes HYGIENE-02 |

## Tests

- New file: `agents/graph-wiki-agent/tests/unit/test_cli_bootstrap.py`
  - `test_bootstrap_help_lists_interactive_flag` — exercises real CLI via
    `subprocess.run` with NO_COLOR/TERM/COLUMNS env injection; asserts
    `--interactive` is listed and all existing flags survive.
  - `test_run_init_forwards_interactive_flag[False-True]` —
    `interactive=False ⇒ non_interactive=True` (default behaviour preserved).
  - `test_run_init_forwards_interactive_flag[True-False]` —
    `interactive=True ⇒ non_interactive=False`.
  - **All 3 tests PASS.**

Full suite verification (Task 5 gate):

- `uv run --package graph-wiki-agent pytest agents/graph-wiki-agent/tests/ -x` —
  **220 passed, 6 skipped** (integration tests gated on
  `GRAPH_WIKI_RUN_INTEGRATION`).
- `uv run --package wiki-io pytest packages/wiki-io/tests/ -x` —
  **151 passed, 1 skipped**.

No regressions introduced.

## Commits

- `7eb73cd` feat(35-01): HYGIENE-09 — self-healing uv re-exec at cli.py top
- `2f3387d` feat(35-01): HYGIENE-11 — --interactive flag threaded through bootstrap
- `1ad347d` test(35-01): HYGIENE-11 — unit tests for --interactive flag wiring
- `1c2a93b` chore(35-01): move closed bootstrap todos to resolved/

## Deviations

None. All edits stayed inside the declared `files_modified` set; no
adjacent-code refactoring; no fixture extractions; surgical-change rule
honored.

## Hand-off to Plan 02

Plan B (verify-and-close, wave 2) inherits:
- The HYGIENE-01..12 audit table above as the closure evidence to reference.
- A clean baseline (both test suites green) for the new
  `test_bootstrap_e2e_no_broken_links.py` regression test.
- `test_cli_help.py` 3/3 currently passing — Plan B Task 1 just adds the
  load-bearing comment and pastes the verbatim pytest output into
  35-DISCUSSION-LOG.md.
