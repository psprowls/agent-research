---
title: lattice-work (plugin) — Patterns
category: package
summary: Key patterns, repository layout, downstream consumers, and recorded cons for lattice-work
updated: 2026-05-09
tokens: 1326
---

# lattice-work (plugin) — Patterns

## Key patterns

- **Data lives in the workspace work/ directory** — work items are markdown files; `lattice-work` reads/writes through `<workspace>/work/` alongside the vault `lattice-wiki` owns. See [[wiki/concepts/lattice-work-namespace-schema]] for the schema-vs-tooling cut.
- **Hard one-way dependency** — `lattice-work` depends on `lattice-wiki` for vault layout and schema. `lattice-wiki` does not know about `lattice-work`. This is the only hard dep in the lattice ecosystem. Enforced at runtime: every command starts with a check for `<workspace>/work/`; if absent, exit 4 with a message naming `/lattice-wiki:init`.
- **Sidecar generation** — `work-index.json` is a regenerable, deterministic index over `<workspace>/work/*.md`. Committed to git; lives in `<workspace>/` so it is human-visible alongside the data it summarizes. Items ordered by `opened:` desc then `slug` for ties; dict keys emitted in fixed order; counts always include all enum values (zeroed if empty); state-conditional fields included as `null` when absent. `vault_commit` from `git -C <repo> rev-parse HEAD`; `generated_at` ISO-8601 UTC. Freshness contract: any `items[*].updated > generated_at` implies stale. See `## Sidecar schema` in [[wiki/plugins/lattice-work/api]].
- **Lifecycle lint, not structural lint** — work-tracker runs the 19 lifecycle rules (`accepted-without-plan`, `stuck-open`, `done-when-missing`, `archive-eligible`, …); base structural lint stays in `lattice-wiki`. See `## Lifecycle lint rules` in [[wiki/plugins/lattice-work/api]].
- **Schema NOT owned here** — the `category: work` enum, frontmatter field set, 7-state lifecycle, 8-value `kind` enum, `## Plan` body convention, required-when-state fields, the `<workspace>/work/archived/` sub-namespace documentation, and migration helpers all live in [[wiki/plugins/lattice-wiki/lattice-wiki]]. Work-tracker is downstream consumer of the shape.
- **Subprocess, not import, for cross-plugin invocation** — peers spawn `${LATTICE_WORK_ROOT}/scripts/regenerate_work_index.py --vault <path> --quiet`. No Python imports across plugin boundaries. Called by `lattice-wiki`'s `ingest_work_item.py`, `lattice-workflows`'s `:file-work-item`, and workflows' status-transition skill.
- **Stdlib-only Python** — no third-party deps. Custom YAML frontmatter parser (no PyYAML); stdlib `unittest` for tests (no pytest). Same constraint as `lattice-wiki`.
- **Pure `lib/`, thin `scripts/`, command-as-shell** — `lib/` has no I/O at import or call time; `scripts/` parse args → call `lib/` → emit JSON or human output → exit code; `commands/` markdown subprocesses into `scripts/` (the actual logic never lives in command markdown).
- **Archive is a location, not a state** — terminal-status items move into `<workspace>/work/archived/` via `:archive`, but keep their `resolved` / `wontfix` / `superseded` frontmatter. No 8th status. Archive eligibility is measured against `updated:` (no `closed_at:` field). Restore in v1 is a manual `git mv` + `:regen-index` recipe.

## Conventions

### Repository layout (v1)

```
plugins/lattice-work/
├── .claude-plugin/plugin.json       # exports LATTICE_WORK_ROOT
├── commands/                        # /lattice-work:lint | :regen-index | :status | :archive
├── lib/                             # pure functions, no I/O at import time
│   ├── frontmatter.py               # YAML frontmatter parser (stdlib, no PyYAML)
│   ├── plan_table.py                # ## Plan body-table parser
│   ├── lifecycle_lint.py            # 19 lifecycle lint rules
│   ├── sidecar.py                   # work-index.json builder + loader
│   └── archive.py                   # is_archive_eligible / plan_archive (pure)
├── scripts/                         # thin CLI entry points
│   ├── regenerate_work_index.py     # cross-plugin entry point; --quiet for callers
│   ├── lint_work_layer.py           # called by :lint
│   ├── status_rollup.py             # called by :status
│   └── archive_resolved.py          # called by :archive — performs git mv (falls back to os.rename); subprocesses regen-index after
├── skills/lattice-work/
│   ├── SKILL.md                     # ~150 lines, planner-facing
│   └── references/
│       ├── lifecycle-rules.md       # 19 rules with rationale + remedy
│       └── sidecar-schema.md        # schema_version 1 reference
└── tests/                           # stdlib unittest
    ├── fixtures/                    # empty-vault, happy-path-vault, lint-violations-vault, stale-sidecar-vault, archive-vault
    └── test_*.py
```

### Recorded cons

| Con | Mitigation |
|---|---|
| Schema coupling across plugins | Lockstep version bumps; document dep in both READMEs; compatibility matrix |
| No hard plugin-dep field in `marketplace.json` | Runtime check at startup for `<workspace>/work/`; helpful error pointing at `/lattice-wiki:init` |
| Two plugins for the planning slice | Acceptable cost for cadence/optionality; documented in install guide |
| Lint surface fragmented (`/lattice-wiki:lint` + `/lattice-work:lint`) | Documented as convention; `/lint-all` meta-command if it becomes friction |
