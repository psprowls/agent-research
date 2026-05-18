# graph-wiki Plugin Contract — Index

This is the single auditable summary of the Phase 13 contract. Phase 14's executor reads this file to scan the entire contract surface before beginning the plugin port. The foundational reframe established in Phase 13: the ported graph-wiki plugin runs on Claude Code inference (per P-01) — it is **not** a wrapper around `code-wiki-agent`. For the cross-cutting invocation shape (env vars, shim template, backend selector, agent rename map), see [SHELL-OUT-PATTERN.md](SHELL-OUT-PATTERN.md).

## Verdict vocabulary

Per C-02, verdict terms are defined as follows:

- `rename` = byte-for-byte text swap of upstream slash and module references (e.g., `/lattice-wiki:init` → `/graph-wiki:init`, `lattice_wiki_core` → `vault_io`)
- `reshape` = command behavior changes beyond a pure rename (e.g., `/lint` loses the work-layer pass 1b that ran against `work/` items)
- `drop` = no port; no file ships in `plugins/graph-wiki/commands/` for this command
- `defer` = port the markdown but disable execution until a later phase (unused in v1.2; documented for future phases where work-layer commands may be reconsidered)

## Command verdict table

| # | Upstream command | Verdict | Target script | Target Python module | Per-command spec | One-line rationale |
|---|---|---|---|---|---|---|
| 1 | `/lattice-wiki:init` | rename | `skills/graph-wiki/scripts/init_vault.py` | `vault_io.init_vault.main` + `vault_io.detect_containers.main` (pre-step) | [init.md](init.md) | Direct mapping; detection sub-step preserved verbatim. |
| 2 | `/lattice-wiki:scan` | rename | `skills/graph-wiki/scripts/scan_monorepo.py` | `vault_io.scan_monorepo.main` | [scan.md](scan.md) | Direct mapping; clean-tree-on-main gate preserved. |
| 3 | `/lattice-wiki:ingest` | rename | `skills/graph-wiki/scripts/ingest_source.py` | `vault_io.ingest_source.main` | [ingest.md](ingest.md) | source-ingest only; work-item ingest dropped per C-01. |
| 4 | `/lattice-wiki:lint` | reshape | `skills/graph-wiki/scripts/lint_wiki.py` | `vault_io.lint_wiki.main` (VP-01 prereq) + `vault_io.graph_analyzer.main` | [lint.md](lint.md) | Mechanical pass 1 + semantic pass 2 preserved; work-lint pass 1b dropped per C-01. |
| 5 | `/lattice-wiki:query` | rename | `skills/graph-wiki/scripts/wiki_search.py` (BM25 fallback only) | `vault_io.wiki_search.main` (VP-01 prereq) | [query.md](query.md) | LLM-driven (Claude Code inference per P-01); only BM25 fallback shells out. |
| 6 | `/lattice-wiki:log` | rename | — (no script) | — | [log.md](log.md) | Prose-only; mirrors upstream which has no script. |
| 7 | `/lattice-wiki:archive` | drop | — | — | — | Work-layer out of v1.2 scope per C-01 and PROJECT.md. |
| 8 | `/lattice-wiki:regen-index` | drop | — | — | — | Work-layer out of v1.2 scope per C-01 and PROJECT.md. |
| 9 | `/lattice-wiki:status` | drop | — | — | — | Work-layer out of v1.2 scope per C-01 and PROJECT.md. |

All target script paths shown above are relative to `plugins/graph-wiki/`. Scripts for the `claude` backend call the listed Python module via `uv run --project "$DEEP_AGENTS_ROOT"` (see [SHELL-OUT-PATTERN.md §SO-01](SHELL-OUT-PATTERN.md#so-01-uv-run-invocation-with-deep_agents_root)).

## Resulting plugin command surface

- **6 ported commands** under `plugins/graph-wiki/commands/`: `init`, `scan`, `ingest`, `lint`, `query`, `log`
- **3 dropped**: no `.md` files for `archive`, `regen-index`, or `status` — they do not appear in `/graph-wiki:` autocomplete
- **Total**: 6 files in `plugins/graph-wiki/commands/`

## Phase 14 prerequisite ports

These two modules must be ported into `vault-io` **before** their respective plugin shims are written:

- **`vault_io.lint_wiki`** — port ~508 LOC from `lattice_wiki_core/lint_wiki.py` into `packages/vault-io/src/vault_io/lint_wiki.py` (Phase 14 Plan 1). Required before the `/graph-wiki:lint` shim can shell out to `lint_wiki.main`. (VP-01)
- **`vault_io.wiki_search`** — port ~194 LOC from `lattice_wiki_core/wiki_search.py` into `packages/vault-io/src/vault_io/wiki_search.py` (Phase 14 Plan 2). Required before `/graph-wiki:query`'s BM25 fallback path works. (VP-01)

Both ports follow the Phase 12 SR-01 rubric: bug fixes, helper extractions, and behavior-preserving refactors come over verbatim. Both must clear the `scripts/check-brand.sh` brand gate (renaming `lattice` → `graph-wiki` in identifiers and prose during the port). (VP-03)

## See also

- [SHELL-OUT-PATTERN.md](SHELL-OUT-PATTERN.md) — Cross-cutting invocation shape (SO-01..SO-04), env var requirements, shim template, backend selector `_config.py`, and agent/skill rename map
- [.planning/phases/13-plugin-spec-m3a/13-CONTEXT.md](../../phases/13-plugin-spec-m3a/13-CONTEXT.md) — Source-of-truth decisions document; contains the full decision log (P-01..P-03, C-01..C-02, SO-01..SO-04, SP-01..SP-05, VP-01..VP-04, PD-01..PD-03)
