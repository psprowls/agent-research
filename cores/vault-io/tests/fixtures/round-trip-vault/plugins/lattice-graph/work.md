---
title: lattice-graph (plugin) — Work
category: package
summary: Status, open follow-ons, and known code-drift items for the lattice-graph plugin.
updated: 2026-05-09
tokens: 1252
---

# lattice-graph (plugin) — Work

## Bugs

### Wrong path in slash-command guards

The five query slash commands (`find.md`, `callers.md`, `callees.md`, `imports.md`, `describe.md`) guard their invocations with:

```bash
test -d lattice/.graph || { echo "No code graph found. Run /lattice-graph:init first."; exit 1; }
```

(`plugins/lattice-graph/commands/find.md:9` and siblings.)

The actual graph location is `<repo>/lattice/.graph/code.db` per ADR-0001-sqlite-primary-store-for-code-graph, ADR-0011-single-workspace-root, [[wiki/concepts/per-repo-layout]], and `packages/lattice-graph-core/README.md:5`. The guard checks for `lattice/.graph` — now the correct base directory under the new single-workspace layout. The bug is cosmetic: when no graph exists, `cg` itself returns exit code 3 (`NOT_INITIALIZED`) and the user sees a downstream error rather than the friendly "Run init first" message. A small tightening to `test -f lattice/.graph/code.db` would add explicitness.

> [!info] Contradiction resolved by ADR-0011
> The guard (`test -d lattice/.graph`) was originally wrong — it checked `lattice/.graph` while the documented path was `.lattice/graph/`. ADR-0011-single-workspace-root moved the graph to `<repo>/lattice/.graph/code.db`, so the guard now checks the correct directory.

## Tech debt

### `init.md` placeholders not yet verified at install time

`commands/init.md` runs `uv tool install "git+{{REPO_URL}}@{{VERSION}}#subdirectory=packages/lattice-graph-core"`. The `{{REPO_URL}}` and `{{VERSION}}` placeholders look like marketplace-install-time substitutions but the substitution surface is undocumented. Worth verifying these resolve correctly in the published plugin distribution.

### `describe-package` / `describe-path` collapsed to `describe`

The architecture spec lists `cg_describe_package` and `cg_describe_path` as separate MCP tools, with `cg_describe_type` as a third. The shipped CLI / slash command collapses package and path into a single `describe` subcommand that disambiguates by argument shape; `describe-type` is deferred to v1.1 (needs an `extends`/`inherits` edge kind not in v1 schema). Not a contradiction with the v1 design — the plugin design spec §11 explicitly defers `describe-type`. The two-tool split (`cg_describe_package` / `cg_describe_path`) returns when the MCP adapter lands.

## Features

### [[work/2026-05-06-lattice-code-graph-wire-exit-codes-4-and-6]] — open, small

Two of the seven declared `cg` exit codes never fire today:

- **`4` `SCHEMA_MISMATCH`** — needs `store.py` to raise on `metadata.schema_version != schema.SCHEMA_VERSION` and `cli/ops_status.py` (and each `cli/q_*.py`) to map it to exit 4. v1 only knows version 1 so the check is a no-op against the current corpus; lands as guard-rail for the v2 schema bump.
- **`6` `UPDATE_IN_PROGRESS`** — needs `update.py` to detect SQLite `OperationalError: database is locked` and retry with backoff before raising `UpdateInProgressError`. Today, concurrent `cg update` invocations surface as exit `1` (`GENERIC`) via the SQLite write-lock.

Lives in the core package; surfaces through this plugin's slash commands and SessionStart hook.

### [[work/2026-05-06-lattice-code-graph-packages-refresh-affected-dirs]] — open, small

Performance: `packages.refresh` does a full `repo_root.rglob` for `pyproject.toml` and `package.json` on every non-idle `cg update`. The design spec called for an `affected_dirs` parameter that scopes the manifest scan to dirs touched by the diff. v1 ships without it because `lattice` is small enough that the walk costs a few ms; on a real monorepo (10k+ files, 100+ packages) the cost compounds. Optimization for v1.x. Lives in the core package; surfaces through this plugin via `cg update` latency.

## Open questions

### [[work/2026-05-06-lattice-code-graph-session-start-hook-integration-test]] — open, small

`hooks/session-start.py` depends on three contracts (`cg --fmt json status` exit code `2` = stale, JSON shape `last_indexed_commit` / `head`, `CLAUDE_PROJECT_DIR` env var). All three are unit-tested in pieces inside `lattice-graph-core`; nothing executes the hook script end-to-end. A rename of any contract would silently break the highest-leverage UX feature in v1.

- **C# beyond v1.1** — what's the cadence for additional languages once the `LanguageParser` interface has been used at scale?
- **Bootstrapping** — does this plugin self-host graph-derived summaries in its own wiki page once wiki-graph integration ships?
- **C# `kind: namespace` shape** — lean is yes-kind, which bumps `schema_version`. Resolved at v1.1 implementation time.
- **`uv tool install` vs `uv sync`** — `init.md` uses the former (which installs `cg` globally per user); the README implies the latter (which installs `cg` per workspace). Worth picking one canonical install path or documenting both.
