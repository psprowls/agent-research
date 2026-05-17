---
title: lattice-graph (plugin) — Patterns
category: package
summary: Thin-shell-to-`cg`, single-writer SQLite, explicit update lifecycle, staleness banner — the load-bearing patterns shaping how this plugin and its core package interact.
updated: 2026-05-09
tokens: 1664
---

# lattice-graph (plugin) — Patterns

## Key patterns

### Thin shell to `cg`

The plugin contains no Python logic. Every slash command body shells to the `cg` console-script provided by [[wiki/packages/lattice-graph-core/lattice-graph-core]] via that package's `[project.scripts]` entry point. `uv sync` (or `uv tool install` from `/lattice-graph:init`) puts `cg` on `PATH`.

```markdown
# commands/update.md
cg update {{args}}
```

Concretely:

- No Python imports cross the plugin boundary (`plugins/lattice-graph/CLAUDE.md`).
- Tests for any plugin-visible behavior live in the core package, not here. The plugin tree has no `tests/` directory.
- `pyproject.toml` declares `lattice-graph-core` as a workspace dep; that's the only Python-level coupling.

This matches the [[wiki/concepts/plugin-deployment-shapes]] shape F split: a Python library + a Claude Code plugin shell. v1 ships only the CLI adapter; the MCP adapter slips to v1.1 per ADR-0007-cli-first-code-graph. The pattern is mirrored by [[wiki/packages/lattice-source-parser/lattice-source-parser]], which established the package-precedent the design spec cites.

### Explicit update lifecycle (no magic)

Per ADR-0002-explicit-graph-update-lifecycle: the graph never silently re-parses behind the user's back. Three plausible auto-update strategies were rejected:

1. Auto-update at session start — surprise factor (a 30 s blocking parse is jarring), branch-switch ambiguity, failure-handling.
2. Filesystem watcher — cross-platform burden, fights git on branch switches, wrong cadence.
3. Trigger from git hooks — couples graph updates to git plumbing the user might not want during a long debugging session.

Instead, updates are user-initiated:

- `/lattice-graph:update` runs `cg update` (incremental: git-diff-driven inside a single SQLite transaction).
- `/lattice-graph:update --full` rebuilds from scratch.
- The SessionStart hook checks staleness and prints a banner. **It never invokes `cg update`.**

`cg update` indexes HEAD, not the working tree. Two reasons: `last_indexed_commit` is meaningless if the index includes uncommitted state, and it matches the parser's expectations (one file → one commit-stable tree). The SessionStart banner is silent about uncommitted changes by design.

See [[wiki/concepts/explicit-not-magic-update-lifecycle]] for the full principle.

### Staleness detection via SessionStart hook

`hooks/session-start.py` is the canonical example of a "surface, don't act" hook. It calls `cg --fmt json status`, keys off exit code 2 for stale, and prints a one-line banner only when stale. Silent when fresh; silent when `cg` is not installed; silent on JSON parse errors. Always returns 0.

Pattern shape:

```python
result = subprocess.run(["cg", "--repo", repo, "--fmt", "json", "status"], ...)
if result.returncode == 2:
    data = json.loads(result.stdout)
    print(f"[lattice-graph] graph is stale (last indexed: {data['last_indexed_commit'][:7]}; HEAD: {data['head'][:7]}). Run /lattice-graph:update to refresh.")
return 0
```

Three load-bearing contracts the hook depends on:

- `cg status` exit code `2` means stale.
- `cg --fmt json status` returns top-level keys `last_indexed_commit` and `head`.
- `CLAUDE_PROJECT_DIR` env var is the repo root (`os.getcwd()` fallback).

These contracts are not currently exercised end-to-end — see [[work/2026-05-06-lattice-code-graph-session-start-hook-integration-test]]. A rename of any one would silently break the highest-leverage UX feature in v1.

### Single-writer `code.db`

Per ADR-0008-single-writer-code-db: `cg update` is the only writer to `<repo>/lattice/.graph/code.db`. All other consumers — slash commands, the future MCP server, [[wiki/plugins/lattice-wiki/lattice-wiki]] integration, the `prefer-graph-over-grep` skill — open the database in `mode=ro`.

Enforced structurally, not by convention:

- The writer takes a SQLite write-lock for the duration of `update`.
- Concurrent writers will (per design) return exit code 6 (`UPDATE_IN_PROGRESS`). Today, exit code 6 is reserved — concurrent updates currently surface as exit 1 via SQLite contention. See [[work/2026-05-06-lattice-code-graph-wire-exit-codes-4-and-6]].
- Readers run in WAL mode; they never block updates and updates never block them.

Consequences:

- Concurrency is trivial to reason about — N readers, at most one writer, mediated by the OS-level write-lock SQLite already implements.
- Any future writer must go through `cg update` (or a sibling subcommand under the same lock discipline).
- Read paths can be opened without write-intent flags everywhere.

### Command composition (`update` → `status` → `dump`)

The three operations form a closed loop:

1. **`update`** writes the graph (incrementally or `--full`). Atomically advances `metadata.last_indexed_commit` to HEAD.
2. **`status`** is the read-only freshness check. Returns exit 2 if stale; the SessionStart hook keys off this.
3. **`dump`** emits raw SQLite contents for debugging or sharing — does not need a fresh graph, just an existing one.

The five query commands (`find`, `callers`, `callees`, `imports`, `describe`) are all read-only point lookups + bounded traversals over the same DB. They never invoke `update` and don't depend on freshness directly — they return whatever's in the graph. Stale freshness is the SessionStart banner's responsibility.

## Conventions

- **Logic in core, not here** — `plugins/lattice-graph/CLAUDE.md` codifies this; the plugin tree has no Python logic and no `tests/` directory.
- **Tree-sitter grammars as binary deps** — the plugin transitively pulls `tree-sitter` + `tree-sitter-language-pack` through [[wiki/packages/lattice-source-parser/lattice-source-parser]]. This breaks the pure-stdlib invariant locally but is isolated to this stack so [[wiki/plugins/lattice-wiki/lattice-wiki]] keeps its pure-stdlib promise.
- **Per-repo data tier** — see [[wiki/concepts/per-repo-data-vs-global-tooling-tier]]. The graph DB lives at `<repo>/lattice/.graph/code.db` per ADR-0011-single-workspace-root and [[wiki/concepts/per-repo-layout]].
- **Shape F** in the [[wiki/concepts/plugin-deployment-shapes]] decision matrix — Python library + plugin shell. v1 = partial F (CLI adapter only); v1.1 fills in the MCP adapter.
- **Consumers** — [[wiki/plugins/lattice-wiki/lattice-wiki]] runs `cg describe` / `cg find` for citation verification with filesystem fallback. The `prefer-graph-over-grep` skill in [[wiki/plugins/lattice-workflows/lattice-workflows]] substitutes `cg_callers` / `cg_callees` / `cg_find` / `cg_describe_package` for grep where applicable. Tools, scripts, CI, and agents can also use `cg` directly on `PATH`.
