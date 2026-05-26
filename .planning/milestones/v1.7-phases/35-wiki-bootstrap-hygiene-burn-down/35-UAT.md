---
status: complete
phase: 35-wiki-bootstrap-hygiene-burn-down
source:
  - .planning/phases/35-wiki-bootstrap-hygiene-burn-down/35-01-SUMMARY.md
  - .planning/phases/35-wiki-bootstrap-hygiene-burn-down/35-02-SUMMARY.md
started: "2026-05-26T22:00:00Z"
updated: "2026-05-26T22:30:00Z"
---

## Current Test

[testing complete]

## Tests

### 1. Bootstrap CLI lists --interactive flag
expected: Running `uv run --package graph-wiki-agent graph-wiki-agent bootstrap --help` shows `--interactive` in the option list, positioned between `--repo` and `--json`. All existing flags still appear. (HYGIENE-11)
result: pass

### 2. --interactive flag is wired through to init_wiki
expected: Calling `run_init(..., interactive=False)` results in `non_interactive=True` being passed to `init_wiki` (default silent-skip); calling with `interactive=True` results in `non_interactive=False` (prompts on ambiguous rows). Unit tests in `agents/graph-wiki-agent/tests/unit/test_cli_bootstrap.py` cover both paths. (HYGIENE-11)
result: pass

### 3. Self-healing uv re-exec works outside the workspace
expected: Invoking the `graph-wiki-agent` CLI when `wiki_io` is not importable triggers `_ensure_uv_workspace()` (cli.py:16) to walk up directories looking for `packages/wiki-io/pyproject.toml` and re-exec under `uv run --project <pkg_dir>`. The `GRAPH_WIKI_BOOTSTRAP_REEXEC=1` env var prevents infinite re-exec. (HYGIENE-09)
result: skipped
reason: user-skipped (requires specific shell setup outside venv)

### 4. Package overview wikilinks use canonical [[wiki/{CONTAINER}/{SLUG}/...]] form
expected: After bootstrapping a fresh wiki, the rendered package `overview.md` sub-page wikilinks (concepts, sources, adrs, architecture, testing) all use the `[[wiki/{{CONTAINER_DIR}}/{{PACKAGE_SLUG}}/...]]` form rather than bare slugs. (HYGIENE-01, HYGIENE-03)
result: pass

### 5. Section index stubs created on init
expected: After bootstrapping a fresh wiki, the four SECTION_INDEX_STUBS (`concepts`, `sources`, `adrs`, `architecture`) each get a stub index page emitted by `init_vault.py`. (HYGIENE-02, HYGIENE-12)
result: pass

### 6. AGENT_RESEARCH_ROOT references in plugins (no bare python invocations)
expected: `plugins/graph-wiki/agents/{ingestor,librarian,linter,scanner}.md` and `plugins/graph-wiki/skills/graph-wiki/README.md` all reference `AGENT_RESEARCH_ROOT`; no bare `python plugins/...` shell-out template remains. (HYGIENE-10)
result: pass

### 7. Bootstrap-and-lint regression test passes
expected: Running `uv run --package wiki-io pytest packages/wiki-io/tests/test_bootstrap_e2e_no_broken_links.py -v` exits 0 with 1 passed in <100ms. The test bootstraps a wiki into `tmp_path`, writes stub sub-pages, and asserts zero broken wikilinks from package/app/plugin overview pages. (HYGIENE-14)
result: pass

### 8. Full test suites green
expected: `uv run --package wiki-io pytest packages/wiki-io/tests/ -x` reports 152 passed, 1 skipped. `uv run --package graph-wiki-agent pytest agents/graph-wiki-agent/tests/ -x` reports 220 passed, 6 skipped. No regressions.
result: pass

## Summary

total: 8
passed: 7
issues: 0
pending: 0
skipped: 1

## Gaps

[none yet]
