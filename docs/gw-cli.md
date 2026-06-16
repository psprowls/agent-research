# Graph Wiki CLI

`graph-wiki-cli` exposes one unified Typer entry point: `gw`.

## Installation

Install `gw` globally as an editable uv tool:

```bash
cd /Users/pat/Personal/agent-research
uv tool install --force --editable ./packages/graph-wiki-cli
```

`gw` then lives at `~/.local/bin/gw` (already on PATH) and runs from any directory:

```bash
gw version                                   # gw 0.1.1
gw --help
gw scan --workspace /path/to/repo/graph-wiki
gw graph status --repo /path/to/repo --mode test
```

### What the flags do

- `--editable` — points the installed CLI at your repo source
  (`packages/graph-wiki-cli/src/...`), so edits to `gw` take effect immediately
  with no reinstall. uv resolves all local workspace members (`graph-wiki-core`,
  `graph-io`, `wiki-io`, `work-io`, `subagent-runtime`, and their transitive
  workspace deps) from local paths — none are on PyPI.
- `--force` — overwrites an existing install. Drop it on a clean machine.

### Caveat

Editable + global means the repo path is load-bearing: if you move or delete
`/Users/pat/Personal/agent-research`, `gw` breaks. Uninstall with
`uv tool uninstall graph-wiki-cli`.

If you'd rather not install globally, run it package-scoped from the repo:

```bash
gw --help
```

## Global flags

These live on the root `gw` callback and may be passed before any command:

- `-v` / `--verbose` — stream a live execution log to **stderr** (`-v` = INFO,
  `-vv` = DEBUG). stderr only — stdout stays clean, so
  `gw -v query ... --json | jq` still works. Independent of a command's own
  `--quiet`. Example: `gw -vv scan`.
- `--install-completion` — install shell completion for the current shell.
- `--show-completion` — print the completion script to copy/customize.

### Common command flags (convention, not global)

Two flags recur on almost every command but are **per-command**, not root-global:

- `--json` — emit the command's result dataclass as JSON instead of human text.
  (On `gw graph`, the equivalent is the sub-app flag `--fmt json` — see below.)
- `--workspace PATH` — point the command at a specific workspace. Resolution
  details and when it is optional are in the next section.

Many mutating commands also accept `--dry-run` (plan/report without writing):
`scan` has no dry-run, but `wiki archive`, `wiki propagate-drift`, `tokens`,
and `work archive` do.

## Workspace & repo resolution (when `--workspace` / `--repo` are needed)

The **repo** is the source code being documented; the **workspace** is a separate
sibling directory holding generated artifacts (`<workspace>/wiki/`, `raw/`,
`.graph-wiki/code.db`). Most commands need to find one or both.

**The common case needs no flags.** When you run `gw` from inside a repository that
has already been bootstrapped (its `.graph-wiki.local.yaml` pins the workspace, and
that workspace contains a `.graph-wiki.yaml` manifest), both the repo and the
workspace resolve automatically — `gw scan`, `gw wiki lint`, `gw work status`, etc.
all just work without `--workspace` or `--repo`. The flags below are only for
running from outside such a repo, pointing at a different workspace, or operating on
a vault that isn't bootstrapped yet.

### Non-graph commands (`scan`, `bootstrap`, all `gw wiki ...`, all `gw work ...`)

These take `--workspace`. Resolution precedence (`wiki_io._workspace.resolve_wiki_and_repo`
→ `workspace_io.config.resolve`):

1. **`--workspace PATH`** flag, if given — short-circuits everything else.
2. **`GRAPH_WIKI_WORKSPACE`** env var, if set.
3. **Discovery from the current directory** — walk up from cwd for `.git` to find
   the repo, then read that repo's `.graph-wiki.local.yaml` `workspace-directory:`
   key; if unset, default to `<repo>/graph-wiki`.

In all cases the resolved workspace must contain a `.graph-wiki.yaml` manifest, or
the command errors with `No .graph-wiki.yaml found in <ws>. Run: gw bootstrap`.

**When you can omit `--workspace`:** if `GRAPH_WIKI_WORKSPACE` is exported, or if
you run from inside a repo whose `.graph-wiki.local.yaml` pins the workspace (this
repo's setup). Otherwise pass `--workspace` explicitly. `--repo` exists only on
`bootstrap` (to override the cwd walk-up when creating a brand-new vault).

### Graph commands (`gw graph ...`)

The `gw graph` sub-app does **not** use `--workspace`. Its group-level flags
(below) resolve the workspace *from the repo*:

- `--repo PATH` — repo root. **Defaults to the current directory**, so it is
  optional only when you run from the repo root; otherwise pass it explicitly.
- `--mode workspace|test` — `workspace` (default) requires a `.graph-wiki.yaml`
  manifest in the resolved workspace; `test` skips that requirement. Use
  `--mode test` for graph operations that don't need a wiki manifest.
- `--fmt human|json` — output format (the graph analogue of `--json`).

`GRAPH_WIKI_WORKSPACE`, if set, still wins inside the resolver even for graph
commands. Note: because graph derives the repo from cwd/`--repo`, running graph
build/update from the *workspace* directory (not the repo) fails with
`ambiguous argument HEAD` — always pass `--repo <repo>` for those.

---

## Top-level commands

### `gw version`

Print the installed `graph-wiki-cli` version and exit. No arguments or flags.

### `gw help [COMMAND ...]`

Show help for the root app or a nested command path, optionally as machine-readable
JSON.

- Argument: `COMMAND ...` (optional) — command path to describe, e.g.
  `gw help graph describe`.
- `--json` — emit the help entry (usage, arguments, options, subcommands) as JSON.

### `gw bootstrap`

Bootstrap a wiki vault structure (creates `wiki/` plus `raw/` and `work/` siblings).

- `--topic TEXT` **(required)** — short description of the repository.
- `--tool TEXT` **(required)** — schema file(s) to install: `claude-code`, `codex`,
  `cursor`, `all`, ….
- `--force` — overwrite a non-empty target directory.
- `--workspace PATH` — target workspace (default: `GRAPH_WIKI_WORKSPACE` / discovery).
- `--repo PATH` — override the repo root (default: cwd walk-up).
- `--interactive` — accepted for compatibility; has no effect.
- `--json` — emit `InitResult` as JSON.

### `gw scan`

Build the code graph and write one page per graph entity into `wiki/entities/`.

- `--workspace PATH` — workspace to scan (default: `GRAPH_WIKI_WORKSPACE` / discovery).
- `--no-file-map` — skip per-package file-map generation.
- `--max-depth INT` (default `3`) — max directory depth for file-map headers.
- `--no-narrate` — skip the narrator/file-describer fan-out (structural-only, no
  Bedrock required).
- `--propagate-drift` — after narration, propose curated-page updates for changed
  entities (M4 drift producer).
- `--json` — emit `ScanResult` as JSON.
- `--emit-worklist PATH` — emit the commit-gated worklist JSON to `PATH` and exit.
- `--apply-worklist PATH` — apply a results JSON from `PATH`.
- `--worklist-path PATH` — worklist JSON for `--apply-worklist` (default: sibling
  `worklist.json`).
- `--short-head TEXT` — stamp value (short HEAD sha) for `--apply-worklist`.

Exit code `3` indicates per-entity errors occurred during the scan.

### `gw query <query_text>`

Query the wiki with agentic retrieval over wiki and code evidence.

- Argument: `<query_text>` **(required)** — the question.
- `--top-k INT` (default `5`, range 3–10) — pages to drill into.
- `--quiet` — suppress progress output (headless mode).
- `--no-state-gate` — no-op; query is read-only.
- plus `--workspace`, `--json`.

### `gw ingest <path>`

Ingest a source file into the wiki via the ingestor LLM. **This is a single
command, not a group** — work items are filed via `gw work file`, not here.

- Argument: `<path>` **(required)** — source file to ingest.
- plus `--workspace`, `--json`.

### `gw log`

Append a timestamped event to the wiki `log.md`.

- `--op TEXT` **(required)** — operation type: `scan`/`ingest`/`lint`/`create`/
  `update`/`delete`/`note`/`query`.
- `--title TEXT` **(required)** — short title for the entry.
- `--detail TEXT` — optional extended detail text.
- plus `--workspace`, `--json`.

### `gw tokens`

Stamp `tokens: <count>` frontmatter across the wiki via Bedrock CountTokens.

- `--dry-run` — count without writing the `tokens` field.
- `--model-id TEXT` (default `anthropic.claude-3-5-haiku-20241022-v1:0`) — Bedrock
  model ID for token counting.
- `--region TEXT` (default `us-east-1`) — AWS region for Bedrock.
- plus `--workspace`, `--json`.

### `gw trace <file>`

Render a JSONL trace file as a human-readable timeline plus a token/cost summary.

- Argument: `<file>` **(required)** — path to the JSONL trace file.
- `--expand` — disable consecutive-same-role collapsing; render every record as a
  full line.

## `gw graph` — code graph commands

Group-level flags `--repo`, `--mode`, `--fmt` apply to **every** subcommand below
(see [Graph commands](#graph-commands-gw-graph-) for their semantics). Pass them
on the group: `gw graph --repo /path --mode test status`.

Examples:

```bash
gw graph --repo /path/to/repo --mode test update --full
gw graph --repo /path/to/repo --mode test status
gw graph --repo /path/to/repo --mode test find --name SomeSymbol
gw graph --repo /path/to/repo describe graph-io --kind package
```

### `gw graph update`

Refresh the code graph (incremental by default).

- `--full` — full rebuild from scratch (needed after classification-logic changes).

### `gw graph sync-wiki`

Link package nodes to their wiki overview pages. No subcommand-local flags.

### `gw graph status`

Print schema version, indexed commit, and node/edge counts. No subcommand-local flags.

### `gw graph dump`

Emit raw SQLite contents for debugging. No subcommand-local flags.

### `gw graph find`

Find graph nodes. At least one filter is required.

- `--name TEXT` — filter by node name.
- `--kind TEXT` — filter by node kind.
- `--in-package TEXT` — filter by containing package.

### `gw graph callers <name>` / `gw graph callees <name>`

Show callers of / callees of a symbol.

- Argument: `<name>` **(required)** — symbol name.
- `--depth INT` (default `3`) — traversal depth.

### `gw graph imports <path>`

Show imports for a path. Argument: `<path>` **(required)**. No flags.

### `gw graph imported-by <path>`

Show files that import a path.

- Argument: `<path>` **(required)**.
- `--symbol TEXT` — restrict to importers of a specific symbol.
- `--depth INT` (default `1`) — traversal depth.

### `gw graph exports <path>`

Show exports from a path. Argument: `<path>` **(required)**. No flags.

### `gw graph exported-by <name>`

Show files exporting a symbol. Argument: `<name>` **(required)**. No flags.

### `gw graph describe [selector]`

Describe a graph entity. Kind is inferred from the selector when `--kind` is omitted.

- Argument: `[selector]` (optional) — entity name or path.
- `--kind` / `-k` — one of `package`, `app`, `domain`, `suite`, `dependency`,
  `agent-plugin`, `entry-point`, `builtin`, `path`, `repo`.
- `--ecosystem TEXT` — dependency ecosystem (use with `--kind dependency`).

Inference when `--kind` is omitted:

- no selector → `repo`
- selector starting with `builtin:` → `builtin`
- a name matching exactly one entity → that kind; if the kind is `dependency` and
  `--ecosystem` is omitted, the ecosystem is auto-resolved from the graph
- a name matching more than one kind → error (exit `7`); pass `--kind`
- a dependency name present in more than one ecosystem → error (exit `7`); pass `--ecosystem`
- otherwise → treated as a `path`

### `gw graph list`

List graph entities of a given kind.

- `--kind` / `-k` **(required)** — one of `apps`, `builtins`, `packages`,
  `scripts`, `suites`, `domains`.

### `gw graph list-entry-points <package>`

List entry points declared by a package.

- Argument: `<package>` **(required)**.
- `--kind TEXT` — `executable` or `library` (filter).

### `gw graph what-tests <name>`

Show tests for a package or domain.

- Argument: `<name>` **(required)**.
- `--kind TEXT` — `package` or `domain` (target kind).

### `gw graph domain-clusters`

Compute domain clusters over package references.

- `--hub-threshold FLOAT` (default `0.5`) — hub-detection threshold.

### `gw graph domain-refs <name>` / `gw graph domain-deps <name>`

Show package references for a domain / outgoing domain dependencies.

- Argument: `<name>` **(required)** — domain name.

### `gw graph cross-cutting`

Show cross-cutting packages. No subcommand-local flags.

## `gw wiki` — wiki-maintenance commands

Every `gw wiki` subcommand accepts `--workspace` and `--json` (see
[Common command flags](#common-command-flags-convention-not-global)); only the
distinctive flags are called out below.

### `gw wiki lint`

Run a mechanical + semantic lint pass over the wiki and report findings.

- `--stale-days INT` (default `90`) — days before a page is flagged stale.
- `--log-gap-days INT` (default `14`) — days before a log gap is flagged.
- plus `--workspace`, `--json`.

### `gw wiki ack-drift <entity>`

Acknowledge (clear) human-section drift flags on an entity page without editing
its prose.

- Argument: `<entity>` **(required)** — entity uri/stem.
- plus `--workspace`, `--json`.

### `gw wiki proposals`

List curated-page proposals from the ledger (defaults to open ones).

- `--status TEXT` (default `proposed`) — `proposed`/`approved`/`rejected`/
  `created`/`all`.
- `--kind TEXT` — `concept`/`adr`/`architecture` (default: all kinds).
- plus `--workspace`, `--json`.

### `gw wiki proposal approve <proposal_id>` / `gw wiki proposal reject <proposal_id>`

Approve (flip status to `approved`) or reject (flip to `rejected`, preserved so it
is not re-proposed) a single proposal.

- Argument: `<proposal_id>` **(required)**.
- plus `--workspace`, `--json`.

### `gw wiki propagate-drift`

Propose curated-page updates for entities whose code changed (M4 drift producer).

- `--only TEXT` — restrict to one entity (uri/stem) or curated page (slug).
- `--dry-run` — judge + report without writing notes or stamping anchors.
- plus `--workspace`, `--json`.

### `gw wiki archive [slugs ...]`

Archive terminal adrs/concepts/proposals pages into `<dir>/_archive/` (sweep when
no slugs given, otherwise targeted).

- Argument: `[slugs ...]` (optional) — specific page slugs.
- `--dry-run` — show the plan without moving files.
- plus `--workspace`, `--json`.

## `gw work` — work-item lifecycle commands

Every `gw work` subcommand accepts `--workspace` and `--json`; only distinctive
flags are called out below.

### `gw work file`

File a new work item into the wiki.

- `--title TEXT` **(required)** — work-item title.
- `--kind TEXT` **(required)** — `bug`/`tech-debt`/`test-gap`/`security`/`perf`/
  `feature`/`initiative`/`spike`.
- `--summary TEXT` **(required)** — one-line summary (≤100 chars).
- `--status TEXT` (default `open`) — `open`/`accepted`/`in-progress`/`done`/
  `wont-fix`/`deferred`.
- `--affects TEXT` — comma-separated paths or package names.
- `--severity TEXT` — `bug`/`security`/`perf` (blank for feature/initiative/spike).
- `--effort TEXT` — `xtra-small`/`small`/`medium`/`large`/`xtra-large`.
- `--blast-radius TEXT` — `file`/`package`/`domain`/`system`.
- `--target TEXT` — `YYYY-QN` or `YYYY-MM`.
- `--owner TEXT` — owner handle.
- `--tags TEXT` — comma-separated tags.
- plus `--workspace`, `--json`.

### `gw work lint`

Run lifecycle lint over all work items. Flags: `--workspace`, `--json`.

### `gw work status`

Show a work-item status rollup. Flags: `--workspace`, `--json`.

### `gw work regen-index`

Rebuild `work-index.json` from `wiki/work/*.md`. Flags: `--workspace`, `--json`.

### `gw work archive [slugs ...]`

Archive terminal work items (sweep when no slugs, otherwise targeted).

- Argument: `[slugs ...]` (optional).
- `--dry-run` — show the plan without moving files.
- plus `--workspace`, `--json`.

### `gw work next <slug>`

Compute the next workflow action for a work item (read-only).

- Argument: `<slug>` **(required)**.
- plus `--workspace`, `--json`.

### `gw work advance <slug>`

Apply the routing table's next transition for a work item (the single mutation
point).

- Argument: `<slug>` **(required)**.
- `--effort TEXT` — `xtra-small`/`small`/`medium`/`large`/`xtra-large`.
- `--owner TEXT` — owner handle.
- `--resolved-in TEXT` — PR/commit reference.
- plus `--workspace`, `--json`.

---

Use `gw help <command path>` or `gw <command> --help` for the authoritative,
always-current option list.
