# S02: CLI package extraction — Research

**Date:** 2026-05-31

## Summary

S02 owns active requirement R003: the CLI package must expose only the `gw` entrypoint. It supports R001/R006/R007 by making the package split real, keeping CLI tests package-local, and proving subprocess launchability. S01 already established the core import surface (`graph_wiki_core.commands`), so the CLI extraction should be a presentation move: create `packages/graph-wiki-cli`, move `cli.py` into `graph_wiki_cli`, depend on `graph-wiki-core`, and change the console script from `graph-wiki-agent` to `gw` without adding an old alias.

The current CLI surface is still in `agents/graph-wiki-agent/src/graph_wiki_agent/cli.py`. It already imports command implementation from `graph_wiki_core.commands`, which is the correct post-S01 dependency direction. The risky parts are not command logic; they are metadata/entrypoint renaming, bootstrap/help text still saying `graph-wiki-agent`, package-local test relocation, and tests that monkeypatch/import `graph_wiki_agent.cli` or spawn `uv run --package graph-wiki-agent graph-wiki-agent ...`.

Recommended depth is targeted: the implementation pattern is local and established by S01, but the blast radius spans package metadata, subprocess tests, and bootstrap wording. No new external docs are needed; installed skills relevant to this slice are `uv-package-manager` for workspace/package metadata and `python-testing-patterns` for pytest relocation. Memory findings confirm that presentation packages must consume `graph_wiki_core.commands` directly and must not add `graph_wiki_agent` compatibility shims.

## Recommendation

Create `packages/graph-wiki-cli` as a focused Typer package with namespace `graph_wiki_cli` and a single script:

```toml
[project.scripts]
gw = "graph_wiki_cli.cli:app"
```

Move/copy the existing CLI module to `packages/graph-wiki-cli/src/graph_wiki_cli/cli.py`, then update CLI-owned literals from `graph-wiki-agent` to `gw` where they describe the command/package. Keep role/config/plugin identity strings as `graph-wiki-agent` only where they refer to `.graph-wiki.yaml` plugin identity; that broader distinction is mostly S04, but S02 should not introduce new stale command help. Do not leave `graph-wiki-agent` as a script alias and do not provide `graph_wiki_agent.cli` import shims.

For test migration, move only CLI presentation tests into `packages/graph-wiki-cli/tests`; leave core command/prompt tests in core and MCP tests for S03. Update imports from `graph_wiki_agent.cli` to `graph_wiki_cli.cli`, monkeypatch targets to `graph_wiki_cli.cli.<name>`, metadata/version assertions to `graph-wiki-cli` or `gw` as appropriate, and subprocess invocations to `uv run --package graph-wiki-cli gw ...`. The first proof should be `gw --help` and `gw query --help`, because they prove package metadata, script exposure, Typer importability, and command registration before deeper command behavior tests run.

## Implementation Landscape

### Key Files

- `agents/graph-wiki-agent/src/graph_wiki_agent/cli.py` — current Typer app. Move to `packages/graph-wiki-cli/src/graph_wiki_cli/cli.py`; keep imports from `graph_wiki_core.commands.*`; rename app `name`, help banner, `version()` metadata lookup/output, and bootstrap comments/re-exec wording from old command/package to `gw`/`graph-wiki-cli` where command-facing.
- `agents/graph-wiki-agent/pyproject.toml` — currently declares both scripts and all presentation deps. S02 should stop relying on it for CLI; S05 may delete the whole package after S03/S04, but S02 can either leave it temporary without CLI ownership or remove `graph-wiki-agent` script once downstream tests are moved. Do not add a `graph-wiki-agent` alias elsewhere.
- `packages/graph-wiki-cli/pyproject.toml` — new package metadata. Dependencies should include `graph-wiki-core`, `graph-io` if directly imported for `exit_codes`, and `typer>=0.25.1`. Use `uv_build>=0.11.14,<0.12` and `[tool.uv.sources] graph-wiki-core = { workspace = true }` plus other direct workspace deps.
- `pyproject.toml` — root workspace already includes `packages/*` and `agents/*`; S05 removes `agents/*`. S02 can rely on `packages/*` picking up the new CLI package.
- `packages/graph-wiki-core/pyproject.toml` — current core still includes `typer>=0.25.1`; this is likely because `graph_wiki_core.commands.graph` exposes a Typer sub-app imported by CLI. Do not blindly remove Typer from core during S02 unless `graph_app` is redesigned; dependency slimming can be deferred.
- `agents/graph-wiki-agent/tests/unit/test_cli_help.py` — CLI subprocess help tests. Move to `packages/graph-wiki-cli/tests/unit/test_cli_help.py`, preserve `_PLAIN_HELP_ENV`, change package/script to `graph-wiki-cli`/`gw`, assert `gw` rather than `graph-wiki-agent` in help.
- `agents/graph-wiki-agent/tests/unit/test_cli_query.py` — CLI query help/import/CliRunner tests. Move/update imports, monkeypatch paths, and subprocess calls. `_make_query_result()` should import `QueryResult` from `graph_wiki_core.commands.query`, not an old presentation namespace.
- `agents/graph-wiki-agent/tests/unit/test_cli_bootstrap.py`, `test_trace_viewer.py`, `test_commands_bootstrap.py`, `test_commands_graph.py`, and any tests importing `graph_wiki_agent.cli` or spawning `graph-wiki-agent` — likely CLI-owned; move/update to `graph_wiki_cli.cli` and `gw` where they validate presentation behavior.
- `agents/graph-wiki-agent/tests/conftest.py` — contains old command references; inspect when relocating tests so package-local fixtures do not preserve stale CLI assumptions.

### Build Order

1. Create `packages/graph-wiki-cli` metadata and package skeleton (`src/graph_wiki_cli/__init__.py`, moved `cli.py`). This gives `uv run --package graph-wiki-cli gw --help` a target.
2. Update CLI literals and metadata lookups: `app = typer.Typer(name="gw", help="gw: ...")`; `version()` should use `importlib.metadata.version("graph-wiki-cli")` and print `gw <version>` or `graph-wiki-cli <version>` consistently. Keep the `_ensure_uv_workspace()` logic if still needed, but revise comments and any uv re-exec target carefully; the existing helper re-execs through `packages/wiki-io`, which may be suspicious but should not be casually rewritten unless tests cover it.
3. Move/update CLI tests. Start with help/query tests as the smallest subprocess proof; then move trace/bootstrap/graph subcommand tests that import the Typer app.
4. Run `uv sync` to update lockfile/workspace scripts, then run targeted CLI tests and help commands.
5. Add a lightweight boundary test in CLI tests: package exposes `gw`, does not expose `graph-wiki-agent`, imports `graph_wiki_cli.cli`, and does not depend on `graph_wiki_agent` namespace.

### Natural Seams

- Package metadata + entrypoint creation is independent of most test relocation.
- CLI source namespace/literal rename is one seam; command implementation imports should remain stable as `graph_wiki_core.commands`.
- Test relocation can be batched by behavior: help/subprocess tests first, CliRunner monkeypatch tests second, trace/bootstrap/graph command presentation tests third.
- S04 owns plugin shim/doc rewiring, so S02 should not spend time editing `plugins/graph-wiki/skills/graph-wiki/scripts/*.py` except to avoid breaking tests it moves.

### Constraints and Watch-outs

- No old alias: `graph-wiki-agent = ...` must not be added to `graph-wiki-cli`.
- No old namespace shim: tests should fail if `graph_wiki_agent.cli` is required by active CLI tests.
- The app currently imports `graph_io.exit_codes` directly. If `graph-wiki-cli` imports this directly, list `graph-io` as a direct dependency/source; do not rely on transitive `graph-wiki-core` dependencies for direct imports.
- Some current tests labeled command tests may now belong in core because they validate command implementation, not CLI presentation. Do not move core-facing tests back into CLI just because they previously lived under the agent package.
- Help tests depend on `NO_COLOR`, `TERM=dumb`, and `COLUMNS=200`; keep this environment to avoid Rich ANSI false negatives.
- Package version lookup will fail if it still asks for `graph-wiki-agent` after the new package is run as `graph-wiki-cli`.

### Verification

Recommended targeted verification for S02:

```bash
uv sync
uv run --package graph-wiki-cli python -c "import graph_wiki_cli.cli as c; print(c.app.info.name)"
NO_COLOR=1 TERM=dumb COLUMNS=200 uv run --package graph-wiki-cli gw --help
NO_COLOR=1 TERM=dumb COLUMNS=200 uv run --package graph-wiki-cli gw query --help
uv run --package graph-wiki-cli python -m pytest packages/graph-wiki-cli/tests
rg -n "graph_wiki_agent|graph-wiki-agent" packages/graph-wiki-cli
```

The final `rg` should have no active CLI package hits unless a historical comment is explicitly accepted; for this slice, command-facing help, imports, scripts, and assertions should all be current.

## Skill Discovery

- Installed and directly relevant: `uv-package-manager` (workspace metadata, scripts, `uv run --package`) and `python-testing-patterns` (pytest relocation and subprocess/CliRunner tests).
- Typer is the main library in play, but it is already used locally and the existing implementation/tests are the source of truth; no external skill search was needed for slice research.
