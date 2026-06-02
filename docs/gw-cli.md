# Graph Wiki CLI

`graph-wiki-cli` exposes one unified Typer entry point: `gw`.

## Installation

Install command

```bash
  cd /Users/pat/Personal/agent-research
  uv tool install --force --editable ./packages/graph-wiki-cli --with click
```

  That's it. gw now lives at ~/.local/bin/gw (already on your PATH) and you can run it from any directory:

```bash
  gw version          # gw 0.1.0
  gw --help
  gw scan --workspace /path/to/repo/graph-wiki
  gw version          # gw 0.1.0
  gw --help
  gw scan --workspace /path/to/repo/graph-wiki
  gw graph status --repo /path/to/repo --mode test

  What each flag does / why
  gw version          # gw 0.1.0
  gw --help
  gw scan --workspace /path/to/repo/graph-wiki
  gw --help
  gw scan --workspace /path/to/repo/graph-wiki
  gw graph status --repo /path/to/repo --mode test
```

### What each flag does / why

  - --editable — installs the CLI pointing at your repo source (packages/graph-wiki-cli/src/...). Code edits to gw take effect immediately, no
  reinstall. uv automatically resolved all seven local workspace members (graph-wiki-core, graph-io, wiki-io, workspace-io, model-adapter,
  subagent-runtime, source-parser) from local paths — none are on PyPI.
  - --with click — required workaround. uv tool install ignores uv.lock and resolves fresh, so it pulled typer 0.26.5; click didn't get installed
  into the isolated tool env, and cli.py imports click directly. Without this flag gw crashes with ModuleNotFoundError: No module named 'click'.
  - --force — only needed because my first attempt (without --with click) already created the tool; it overwrites it. On a clean machine you can
  drop --force.

### Two real caveats

  1. Editable + global means the repo path is load-bearing. If you move or delete /Users/pat/Personal/agent-research, gw will break. To uninstall:
  uv tool uninstall graph-wiki-cli.
  2. The --with click is a band-aid for a packaging bug. cli.py:13 imports click directly but no pyproject.toml in the workspace declares it as a
  dependency — it's been riding on typer's transitive click, which the lockfile happens to pin but a fresh resolve dropped. The proper fix is adding
  click to packages/graph-wiki-cli/pyproject.toml dependencies. That's a one-line repo change — want me to do it (via your GSD workflow, per
  CLAUDE.md), so future installs don't need the workaround?

```bash
uv run --package graph-wiki-cli gw --help
```

## Top-level commands

- `help` — show human or JSON help.
- `version` — print the installed `graph-wiki-cli` version.
- `bootstrap` — initialize a wiki vault structure.
- `scan` — scan a repository and create/update wiki stubs.
- `trace` — render a Graph Wiki JSONL trace file.
- `graph` — code-graph operations.
- `wiki` — wiki-maintenance operations (see below).

## Code graph commands

Code graph commands live under the `gw graph ...` namespace. There is no standalone
`cg` or `gwgraph` executable.

Common examples:

```bash
uv run --package graph-wiki-cli gw graph update --full --repo /path/to/repo --mode test
uv run --package graph-wiki-cli gw graph status --repo /path/to/repo --mode test
uv run --package graph-wiki-cli gw graph find --name SomeSymbol --repo /path/to/repo --mode test
uv run --package graph-wiki-cli gw graph describe-package graph-io --repo /path/to/repo --mode test
```

Available `gw graph` subcommands:

- `update`
- `sync-wiki`
- `status`
- `dump`
- `find`
- `callers`
- `callees`
- `imports`
- `imported-by`
- `exports`
- `exported-by`
- `describe-app`
- `describe-builtin`
- `describe-dependency`
- `describe-package`
- `describe-path`
- `describe-plugin`
- `describe-repo`
- `describe-suite`
- `describe-domain`
- `describe-entry-point`
- `list-apps`
- `list-builtins`
- `list-packages`
- `list-entry-points`
- `list-scripts`
- `list-suites`
- `list-domains`
- `what-tests`
- `domain-clusters`
- `domain-refs`
- `domain-deps`
- `cross-cutting`

Use `gw graph <subcommand> --help` for command-specific options.

## Wiki commands

Wiki-maintenance commands live under the `gw wiki ...` namespace.

Available `gw wiki` subcommands:

- `query` — query the wiki with hybrid search and librarian fan-out.
- `log` — append a timestamped wiki log entry.
- `lint` — run mechanical and semantic wiki checks.
- `ingest source` — ingest a source file into the wiki.
- `ingest work-item` — file a structured work item into the wiki.

Common examples:

```bash
uv run --package graph-wiki-cli gw wiki query "Where is auth documented?" --top-k 5
uv run --package graph-wiki-cli gw wiki lint --workspace /path/to/repo/graph-wiki
uv run --package graph-wiki-cli gw wiki ingest source docs/example.md --workspace /path/to/repo/graph-wiki
```

Use `gw wiki <subcommand> --help` for command-specific options.
