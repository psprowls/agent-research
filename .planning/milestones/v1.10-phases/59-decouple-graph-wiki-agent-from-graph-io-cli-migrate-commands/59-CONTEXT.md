# Phase 59: Decouple graph-wiki-agent from `graph_io.cli` - Context

**Gathered:** 2026-05-29
**Status:** Ready for planning

<domain>
## Phase Boundary

`graph-wiki-agent` consumes only the typed `graph_io` library API — **no module under `agents/graph-wiki-agent/` imports `graph_io.cli`**. Migrate `commands/graph.py` off the in-process `graph_io.cli.*.run(argparse.Namespace)` + captured-stdout shim (the `_build_namespace` / `_capture_run` pattern, decisions D-06/D-07) onto typed functions: `graph_io.queries.*`, `graph_io.update.run`, `graph_io.store.read_only_connect`.

`graph.py` is the **only** agent consumer needing migration — `scan.py` and `propose_domains.py` already use the typed API (confirmed by grep). The eight cg modules wrapped today: `ops_update` (→ `graph build`), six `q_describe_*` (→ `graph describe <kind>`), and `q_find` (→ `graph query`).

**Out of scope:** deciding whether to keep the `cg` CLI as a human-facing debug surface — deferred to a later decision. (This phase keeps cg fully working; the formatter-promotion below makes cg and the agent *share* rendering, which is compatible with keeping cg.)

</domain>

<decisions>
## Implementation Decisions

### Output formatting (the keystone decision)
- **D-01:** The cg cli modules currently OWN the human-readable formatting — describe formatting is inline f-strings duplicated across the 6 `q_describe_*` modules, while `q_find` already shares `graph_io.cli._format.render`. Since SC#1 forbids importing `graph_io.cli` and SC#3 requires unchanged output, **promote the rendering into a public `graph_io` module** (out of `graph_io.cli`, e.g. `graph_io.render` / `graph_io.format`) imported by both the agent and cg. The agent imports this public formatter; it does **not** import `graph_io.cli`.
- **D-02:** Promotion goes the full distance — **true single source of truth**. Move `_format.render` (and its helpers `_to_dict`/importer-batch handling) to the public module AND extract the 6 inline describe formatters into it, then **refactor the cg cli modules to consume the public formatter too**. No duplicated/drift-prone formatting. This intentionally touches `graph_io.cli` modules and their tests/snapshots; cg's own tests are the guard that cg output stays byte-identical after the refactor.
- **D-03:** Output fidelity bar is **byte-identical** (human format only — the agent always uses `fmt="human"`; cg additionally supports `fmt="json"`, which the promoted formatter must still support for cg's sake). SC#3 ("behavior unchanged") is held to the strict bar.

### Error handling & exit-code mapping
- **D-04:** Reproduce the cg exit-code contract exactly via a **shared connect+map helper in the agent**: one helper opens `read_only_connect(graph_dir(workspace)/"code.db")`, catches `graph_io.store` exceptions, and maps them to `graph_io.exit_codes` values — reused by all 6 describe commands and `graph query`. Mirrors the existing `scan.py` typed-consumer pattern (`scan.py:542` `read_only_connect(...)` + `except GraphNotInitializedError`).
- **D-05:** Exit-code mapping to preserve (source of truth = `graph_io.exit_codes`): `GraphNotInitializedError → NOT_INITIALIZED (3)`, `SchemaMismatchError → SCHEMA_MISMATCH (4)`, describe not-found → `GENERIC (1)`, find `--in-package` no-match → `GENERIC (1)` (the D-07 quirk in `q_find.py` — distinct from name/kind zero-result which stays `SUCCESS`), success → `SUCCESS (0)`. The Typer layer keeps raising `typer.Exit(code=...)` with these codes.
- **D-06:** `graph build` migrates to `graph_io.update.run(repo_root, *, workspace=..., full=...)` which returns `None` and **raises** on error (vs. the old `ops_update.run` returning an int). Wrap it separately with its own exception→exit-code mapping. Preserve the existing `--model` behavior (recorded in trace, NOT invoked; stderr note "not invoked in v1.7") and the no-LLM cost-omission. Note: the typed `update.run` does not surface a distinct NOT_INITIALIZED exit path the way some expected (see memory: "graph-io ops_update lacks distinct NOT_INITIALIZED exit code") — researcher should confirm what `update.run` raises and map accordingly.

### Trace records (preserve unchanged)
- **D-07:** Keep the Phase 9 OBS-04 trace schema exactly: `schema_version = 1` (do NOT bump), same `event` values (`graph_build_start/complete`, `graph_describe`, `graph_query`), same honest-omission of cost fields on proxy commands (D-03 of the original graph.py docstring), same per-invocation JSONL path under `<workspace>/.graph-wiki/traces/`. `exit_code` written to the trace now comes from the agent's own mapping (D-05) rather than a cg-returned int.

### Testing strategy (verifies SC#3)
- **D-08:** Replace the existing `test_commands_graph.py` tests — they mock cg-module dispatch and assert the `argparse.Namespace` shape, i.e. they test the exact mechanism being deleted. New tests **seed a real graph DB and snapshot the human output + exit codes** for each subcommand.
- **D-09:** Reuse the existing session-scoped `seeded_graph_conn` fixture (`agents/graph-wiki-agent/tests/conftest.py:95`) which builds a real `code.db` from `packages/graph-io/tests/fixtures/sample_monorepo` via `update.run(..., full=True)`. The graph commands resolve their own workspace from `GRAPH_WIKI_WORKSPACE` + `graph_dir(workspace)/code.db`, so the tests should **point `GRAPH_WIKI_WORKSPACE` at the seeded repo** (the fixture builds a real on-disk workspace, not just a conn) so each subcommand opens the same DB. Snapshot via syrupy (already in the stack). Error/exit-code branches that are awkward to provoke with a real DB (not-initialized, schema-mismatch) may stay mock-based.

### Claude's Discretion
- Exact public module name/location for the promoted formatter (`graph_io.render` vs `graph_io.format` vs other) — planner/researcher choose; constraint is "public, not under `graph_io.cli`".
- Internal structure of the shared connect+map helper (where it lives in the agent package, signature).
- Which describe error branches use snapshot-vs-mock per D-09.

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Migration target (the module being changed)
- `agents/graph-wiki-agent/src/graph_wiki_agent/commands/graph.py` — the only agent module importing `graph_io.cli`; contains the `_build_namespace`/`_capture_run` shim to remove and the D-01..D-09 docstring decisions to preserve (trace schema, `--model` behavior, describe subapp shape, kebab↔snake dispatch).

### Typed library API (the migration destination)
- `packages/graph-io/src/graph_io/queries.py` — typed query functions + dataclasses (`describe_package`, `describe_path`, `describe_repository`, `describe_domain`, `describe_entry_point`, `describe_test_suite`, `find`); all take an open `sqlite3.Connection`.
- `packages/graph-io/src/graph_io/update.py` §`run` (line 232) — `run(repo_root, *, workspace=None, full=False, lock_timeout_ms=None) -> None`; raises on error.
- `packages/graph-io/src/graph_io/store.py` — `read_only_connect` (line 68), `connect` (line 41), `GraphNotInitializedError` (line 13), `SchemaMismatchError`.
- `packages/graph-io/src/graph_io/exit_codes.py` — stable exit-code constants (the contract to preserve, D-05).

### Formatting to promote (currently under graph_io.cli — must move out)
- `packages/graph-io/src/graph_io/cli/_format.py` — `render(...)` + `_to_dict`/importer-batch helpers used by `q_find`; promote to a public module.
- `packages/graph-io/src/graph_io/cli/q_describe_package.py` (and the 5 sibling `q_describe_*.py`) — inline human/JSON formatting to extract into the public formatter and have these modules call.
- `packages/graph-io/src/graph_io/cli/q_find.py` — current `find` query+format+exit-code reference (incl. the `--in-package` no-match → exit 1 quirk, D-05).

### Existing typed-consumer pattern to mirror
- `agents/graph-wiki-agent/src/graph_wiki_agent/commands/scan.py` (esp. ~line 542 `read_only_connect(graph_dir(wiki.parent)/"code.db")` + `except GraphNotInitializedError`) — the established way an agent command opens the typed graph and handles init errors.

### Tests
- `agents/graph-wiki-agent/tests/unit/test_commands_graph.py` — the tests to replace (mock cg dispatch + Namespace assertions).
- `agents/graph-wiki-agent/tests/conftest.py:95` — `seeded_graph_conn` fixture (and the `sample_monorepo` resolver above it) to reuse for D-09.
- `packages/graph-io/tests/conftest.py:17` — sibling `seeded_db` fixture pattern (`update.run(..., full=True)` over `sample_monorepo`).

### Phase definition
- `.planning/ROADMAP.md` §"Phase 59" (line 299) — goal, out-of-scope note, 4 success criteria.

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- **`seeded_graph_conn` fixture** (`tests/conftest.py:95`): session-scoped real `code.db` over `sample_monorepo`; the substrate for D-08/D-09 snapshot tests. Point `GRAPH_WIKI_WORKSPACE` at its seeded repo so commands hit the same DB.
- **`scan.py` typed-consumer pattern**: copy-able shape for connect + error handling + exit-code translation (D-04).
- **`graph_io.cli._format.render`**: already a shared formatter for `find` — half the promotion work (D-02) is relocating this; the other half is extracting the 6 inline describe formatters.
- **`graph_io.exit_codes`**: the canonical exit-code constants — no new codes invented; map onto these (D-05).

### Established Patterns
- The agent's `graph describe` is a Typer subapp with 6 sub-sub-commands; kebab-case CLI names map to snake_case dispatch keys (D-08/D-09 of graph.py docstring). Preserve.
- Commands resolve `(repo_root, workspace)` via `workspace_io.config.resolve` from `--workspace` arg or `GRAPH_WIKI_WORKSPACE` env (`_resolve_paths` in graph.py). The typed path uses `workspace_io.paths.graph_dir(workspace)/"code.db"`.
- cg cli modules follow: `read_only_connect` → typed query → `None`/error guard → format/print → return `exit_codes.*`. After D-02 the format step becomes a public-formatter call shared with the agent.

### Integration Points
- New public `graph_io` formatter module consumed by BOTH cg cli modules and the agent's `graph.py` (D-01/D-02).
- New shared connect+map helper inside the agent package, consumed by all describe + query commands (D-04).
- cg's own test suite (`packages/graph-io/tests/`) becomes the guard that the formatter refactor leaves cg output byte-identical.

</code_context>

<specifics>
## Specific Ideas

- Hold SC#3 to **byte-identical** output, not merely "informationally equivalent" (D-03) — the user explicitly rejected the agent-owns-new-format option.
- Single source of truth over minimal blast radius (D-02) — the user explicitly chose to refactor cg too rather than leave it untouched and duplicate.

</specifics>

<deferred>
## Deferred Ideas

- Whether to keep the `cg` CLI as a human-facing debug surface (carried from the ROADMAP out-of-scope note) — later decision.

### Reviewed Todos (not folded)
- **Populate entity-page `## Related` section from graph edges** (`2026-05-28-...`) — wiki-io entity-page work, unrelated to `commands/graph.py` decoupling. Matched on generic keyword overlap only.
- **Fix entity summary placeholder breaks Obsidian rendering** (`2026-05-29-...`) — wiki-io entity-rendering bug; out of scope.
- **Test suites fan out under every package in wiki index** (`2026-05-29-...`) — index-generation behavior; out of scope.

</deferred>

---

*Phase: 59-decouple-graph-wiki-agent-from-graph-io-cli-migrate-commands*
*Context gathered: 2026-05-29*
