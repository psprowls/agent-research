# Graph Wiki CLI

`graph-wiki-cli` exposes one unified Typer entry point: `gw`.

```bash
uv run --package graph-wiki-cli gw --help
```

## Top-level commands

- `help` — show human or JSON help.
- `version` — print the installed `graph-wiki-cli` version.
- `trace` — render a Graph Wiki JSONL trace file.
- `bootstrap` — initialize a wiki vault structure.
- `scan` — scan a repository and create/update wiki stubs.
- `ingest source` — ingest a source file into the wiki.
- `ingest work-item` — file a structured work item into the wiki.
- `query` — query the wiki with hybrid search and librarian fan-out.
- `log` — append a timestamped wiki log entry.
- `lint` — run mechanical and semantic wiki checks.
- `migrate-vault` — migrate an existing vault layout.
- `graph` — code-graph operations.

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
