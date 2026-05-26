# Phase 39: Scanner Consumes graph-io - Context

**Gathered:** 2026-05-26
**Status:** Ready for planning (gated on Phase 38 merge — see D-01)

<domain>
## Phase Boundary

Wire the scanner to use graph-io as the source of truth for what gets scanned and where vault pages land. `run_scan()` calls `cg update` (incremental) through Phase 38's `graph build` pathway BEFORE subagent fan-out, then derives each workspace's vault page slug from its graph URI + attrs (`is_app`, `domain`) instead of inferring from the filesystem-discovered `pkg` dict. When the graph CAN'T be initialized (write-permission / disk-full case only), the scanner falls back to today's path-based logic with a clearly labeled `NOT_INITIALIZED fallback` stderr line. General `cg update` runtime failures (SQLite lock, malformed repo, crash) hard-abort the scan.

Out of scope: refactoring `discover_workspaces` semantics; URI-keyed wiki redesign / flat-by-ID views (deferred to v1.8 per REQUIREMENTS.md "Future Requirements"); orphaned-page reconciliation on package rename (deferred to v1.8); plugin (`plugins/graph-wiki/`) wiring to graph-io (deferred to v1.8); ingestor integration with graph-io (Phase 40); migration of existing `apps/`/`domains/` vault pages (left in place — same layout policy as today).

</domain>

<decisions>
## Implementation Decisions

### Cross-Phase Sequencing (HARD DEPENDENCY)

- **D-01: Pre-scan `cg update` invocation goes through Phase 38's `graph build` pathway.** `run_scan()` calls the helper Phase 38 introduces (`graph-wiki-agent`'s in-process `ops_update.run` adapter from Phase 38 commands/graph.py), NOT a direct `graph_io.cli.ops_update.run` import. Single agent-side surface for "invoke a graph update."
  - **Why:** Consistency wins — surface should not bifurcate. Future agent-side knobs (timing instrumentation, error policy, model-override) live in one place rather than two.
  - **Sequencing constraint:** Phase 38 MUST merge before Phase 39 implementation can start. The Phase 38 planner blocked on its first run (runtime didn't expose Task tool to spawn the GSD subagents the workflow expects) — a re-spawn is needed. If Phase 38 slips, Phase 39's planner must be aware that the called-into helper from Phase 38 may not exist yet.
  - **What it does NOT do:** Does not block Phase 39 *planning* — the planner can write `39-01-PLAN.md` referencing the Phase 38 helper by its planned name; the executor checks that the helper exists at execute time.

- **D-02: Pass-through flags from `run_scan` to Phase 38 helper: `full=False`, `trace=False`, `model=None`.** Scanner produces its own logs and traces; it should NOT auto-emit a `.graph-wiki/traces/<timestamp>-graph-build.jsonl` on every scan. Users who want a traced graph update run `graph-wiki-agent graph build --trace` separately.
  - **Why:** Avoids cluttering `.graph-wiki/traces/` with one record per scan. Trace remains an explicit-opt-in flag, not a side-effect of `run_scan`.

### URI → Slug Mapping

- **D-03: Slug derivation = last URI segment + graph node attrs for routing prefix.** For a workspace with URI `pkg:org/repo/<name>`:
  - Strip `pkg:org/repo/` prefix → `<name>`.
  - Look up the graph node's attrs (`is_app: bool`, `domain: str | None` — verify exact attr names against the v1.6 schema at plan time).
  - Pick the routing prefix:
    - `attrs.is_app` true → `apps/<name>/overview.md`
    - `attrs.domain` set → `domains/<domain>/packages/<name>/overview.md`
    - else → `<vault_dir or "packages">/<name>/overview.md` (preserving today's `_wiki_relative_path_for` vault_dir fallback)
  - **Why:** Preserves existing vault layout — apps/ and domains/ pages continue to live where they live today. Sources the inputs from the graph (D-04 decorates with `pkg["uri"]`/`pkg["is_app"]`/`pkg["domain"]`) instead of inferring from the filesystem; the routing function itself stays untouched.
  - **Plugin / non-`packages/` container handling:** Existing `vault_dir` from CLAUDE.md layout block continues to apply for plugins/agents/etc. (Phase 35 HYGIENE-03 wired `{{CONTAINER_DIR}}` for these). If the graph attrs don't cover the plugin case (e.g. plugins not marked `is_app` but live under `plugins/`), planner falls back to the existing `vault_dir` derivation. Verify at plan time.

### Code Location & Connection Lifetime

- **D-04: Agent-side decoration in `run_scan()`.** Open a read-only graph connection in `run_scan()` AFTER the pre-scan `cg update` returns successfully. For each discovered workspace, query the graph for its URI + attrs (or perform a single batch query and join in-memory). Decorate each `pkg` dict with `pkg["uri"]`, `pkg["is_app"]`, `pkg["domain"]`. Then call `discover_workspaces` / `_wiki_relative_path_for` UNCHANGED — they read the decorated dict instead of inferring from the filesystem.
  - **Why:** Minimal blast radius. wiki-io stays graph-unaware (no new dependency from `packages/wiki-io/` to `packages/graph-io/`). Tests in wiki-io don't need a seeded graph fixture. `_wiki_relative_path_for`'s routing logic stays where it lives.
  - **What it does NOT do:** Does not refactor `_wiki_relative_path_for(pkg, vault_dir)` to take a `conn` arg. Does not introduce a new `commands/scan_uri_helpers.py` module (kept inline in `commands/scan.py` for v1.7; can be extracted later if it grows).

- **D-05: Single read-only connection opened at scan entry, closed in `finally`.** Mirrors Phase 37 D-03 connection lifetime — `graph_io.store.read_only_connect()` once after pre-scan update succeeds, captured by the decoration helper closure, closed in a `finally` block when `run_scan` returns (success OR exception). Honors Pitfall 4 (no per-call SQLite open).
  - **Why:** Symmetric with Phase 37; eliminates per-workspace conn cost; matches established pattern.

### Fallback Strategy & Log Line Shape

- **D-06: Pre-scan `cg update` auto-creates graph DB on fresh workspaces.** Normal flow: Phase 38's helper calls `ops_update.run` which handles fresh init (creates `.graph-wiki/graph/code.db` if missing). After this call, the graph is guaranteed to exist for the rest of `run_scan`.
  - **Why:** First-time scanner users shouldn't need to manually run `cg update` before their first scan. The graph follows the wiki — both are created on demand.

- **D-07: General `cg update` runtime failure → hard abort the scan.** If `ops_update.run` returns a non-success, non-NOT_INITIALIZED exit code (SQLite lock contention, malformed repo state, runtime crash, etc.), `run_scan` raises a structured exception (or returns a `ScanResult` with a top-level error). The scan does NOT continue with stale or absent graph data.
  - **Why:** Stricter than SC#2's literal "graceful fallback" wording, but justified: a malformed graph state is more dangerous than no graph (silent wrong slugs). The graceful-fallback case is narrowed to D-08.
  - **Exit / error shape:** Planner picks; suggest mirroring Phase 38's exit-code surfacing (`typer.Exit(code=N)` from CLI; structured error from `run_scan` API).

- **D-08: ONLY NOT_INITIALIZED-class init failure triggers graceful path-based fallback with the SC#2 log line.** If `ops_update.run` reports that the graph CAN'T be initialized (e.g. `graph_dir` is not writable, disk full, parent dir missing — verify exit-code surface against `graph_io.exit_codes`), `run_scan` does NOT abort. Instead:
  - Skip the read-only connection open.
  - Skip the decoration step — workspaces flow through with the today path-based slug inference.
  - Emit exactly one stderr line BEFORE any subagent fan-out begins: `[NOT_INITIALIZED fallback: graph could not be initialized (<reason>); using path-based slugs]`.
  - Continue the scan to completion.
  - **Why:** Satisfies SC#2 narrowly. "Can't initialize" is a permission/disk issue, not a data-correctness issue — graceful is correct. "Update failed at runtime" is a data-correctness risk — hard abort is correct (D-07).
  - **Verifying scope:** Planner: read `graph_io.exit_codes` to identify which exit code signals "could not initialize." If the exit-code surface conflates init-failure with runtime-failure, planner adds a granular exit code or distinguishes via a different signal (stderr substring grep is acceptable but brittle).

### Claude's Discretion

- Exact graph node attribute names (`is_app` vs `kind=app` enum vs other shape) — planner verifies against the v1.6 schema at plan time.
- Batch query vs per-workspace lookup for the decoration step (D-04) — planner picks based on `graph_io.queries` surface; suggest one query that joins all package nodes' name + attrs in a single SELECT to avoid N round trips.
- Plugin / non-`packages/` container slug fallback details (D-03 says preserve existing `vault_dir` logic; planner verifies the graph carries enough info to drive this OR falls back cleanly).
- Where the `[NOT_INITIALIZED fallback: …]` line is written — planner picks stderr (recommended) vs scan log file. Stderr is cheapest; one-shot per scan; greppable from CI.
- Whether to add a `--no-graph-update` flag to `graph-wiki-agent scan` for advanced users who want to skip the pre-scan `cg update` (e.g. CI scenarios where the graph is built separately). Planner picks; if added, it bypasses D-06/D-07/D-08 entirely and falls straight to path-based slugs.

### Folded Todos

None. No todos match Phase 39's scanner scope.

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Phase Scope & Requirements
- `.planning/REQUIREMENTS.md` (SCANNER-01..03 section) — three locked requirements
- `.planning/ROADMAP.md` (Phase 39 section) — phase goal + 3 success criteria (SC#1 `cg update` before fan-out; SC#2 URI-derived slugs + NOT_INITIALIZED fallback log line; SC#3 plugin smoke test captured — SUPERSEDED by Phase 35 HYGIENE-14 / D-02 automated bootstrap+lint test)
- `.planning/STATE.md` (Pitfall 4) — single-conn open per command entry; no per-call SQLite opens

### Cross-Phase Coupling (READ BEFORE PLANNING)
- `.planning/phases/38-graph-wiki-agent-graph-subcommand/38-CONTEXT.md` — D-06 in-process import + D-07 manual-Namespace pattern that Phase 39 calls into. **HARD DEPENDENCY:** Phase 38 MUST merge before Phase 39 implementation.
- `.planning/phases/37-librarian-grounding-tools/37-CONTEXT.md` — D-03 connection-lifetime pattern that Phase 39 D-05 mirrors.
- `.planning/phases/35-wiki-bootstrap-hygiene-burn-down/35-CONTEXT.md` — D-02/D-03 automated bootstrap+lint test at `packages/wiki-io/tests/test_bootstrap_e2e_no_broken_links.py` IS the SC#3 captured artifact for Phase 39. Phase 39 does NOT need to capture a separate manual transcript; planner cites this test in the plan + SUMMARY.

### Target Files (Modified)
- `agents/graph-wiki-agent/src/graph_wiki_agent/commands/scan.py` (lines ~222-456) — `run_scan` gains:
  - Call to Phase 38's `graph build` helper at command entry (D-01/D-02)
  - Read-only conn open after successful update (D-05)
  - Decoration step that adds `pkg["uri"]`/`pkg["is_app"]`/`pkg["domain"]` to each workspace dict (D-04)
  - `finally` block to close the conn (D-05)
  - Error policy: hard-abort on general `cg update` failure (D-07); graceful fallback + log line on init-failure (D-08)
- `packages/wiki-io/src/wiki_io/scan_monorepo.py:613` — `_wiki_relative_path_for(pkg, vault_dir)` STAYS UNCHANGED in source. Routing logic reads from the decorated dict; behavior preserved when `pkg["uri"]`/`pkg["is_app"]`/`pkg["domain"]` are absent (NOT_INITIALIZED fallback path; D-08).

### Read-Only References (Don't Edit)
- `packages/wiki-io/src/wiki_io/scan_monorepo.py:613-635` — current `_wiki_relative_path_for` routing logic (template for the routing inputs the decoration step must satisfy)
- `packages/wiki-io/src/wiki_io/scan_monorepo.py:598-611` — current `discover_workspaces` (consumer of the decorated dict in `run_scan`'s step 3)
- `agents/graph-wiki-agent/src/graph_wiki_agent/commands/scan.py:222-456` — current `run_scan` (modification site)
- `packages/graph-io/src/graph_io/queries.py` — query layer; the decoration step uses one of `find` / `list_packages` / a new helper to fetch URI + attrs in batch
- `packages/graph-io/src/graph_io/store.py` — `read_only_connect()` + `GraphNotInitializedError` for D-05/D-08
- `packages/graph-io/src/graph_io/exit_codes.py` — NOT_INITIALIZED exit code value; planner verifies the granularity for D-08
- `packages/workspace-io/src/workspace_io/paths.py` — `graph_dir(workspace)` for resolving the DB path
- `agents/graph-wiki-agent/src/graph_wiki_agent/commands/graph.py` — Phase 38's in-process call adapter; D-01 calls into this. **Verify exists at plan time.**

### Phase 35 HYGIENE-14 Artifact (SC#3 satisfaction)
- `packages/wiki-io/tests/test_bootstrap_e2e_no_broken_links.py` — automated bootstrap+lint regression test from Phase 35 Plan B Task 2. Phase 39 SC#3 is satisfied by this test (no separate manual transcript needed).

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- `_wiki_relative_path_for(pkg, vault_dir)` at `wiki_io/scan_monorepo.py:613` — current routing logic. Reads `pkg["name"]`/`pkg["type"]`/`pkg["domain"]` from the discovered dict. D-04's decoration adds `pkg["uri"]`/`pkg["is_app"]`/`pkg["domain"]` from the graph; the routing function stays the same (`is_app` already exists semantically as `pkg.get("type") == "app"` — verify the conversion at plan time).
- `read_only_connect()` + `GraphNotInitializedError` from Phase 37 — exact connection management pattern Phase 39 mirrors.
- Phase 38's `commands/graph.py` in-process adapter (when Phase 38 lands) — D-01 calls into this. Planner: re-verify the function signature exists at plan-execute time.
- Existing scan log infrastructure (`append_log` calls at the end of `run_scan`) — D-08's stderr line is separate from the scan log; planner picks if any of the new state (cg update outcome, decoration outcome, fallback decision) should also appear in the scan log.

### Established Patterns
- `run_scan` already has a 14-step pipeline (`commands/scan.py:226-456`); Phase 39 adds:
  - A new step 1.5: `cg update` invocation (between resolve_wiki_and_repo and discover_workspaces)
  - A new step 4.5: graph decoration (between file_map and _load_existing_pages)
  - A new step 0 (try/finally wrap): conn open + close
- Phase 37 D-03 / D-04 (NOT_INITIALIZED fallback in librarian): bind no tools + addendum + stderr line. Phase 39 mirrors the stderr-line pattern (D-08), differs on the action (path-based slug fallback vs no-tools librarian).
- Exit-code-driven branching in `run_scan` is already in place (state_gate result feeds into post-processing); D-07/D-08 add another branch on `ops_update.run` exit code.

### Integration Points
- Scanner discovery → graph URI lookup: D-04 decoration is the join point. Single-query batch lookup (recommended) joins workspace `name` → graph node `name` (or URI suffix match).
- Pre-scan `cg update` → decoration step: serial dependency. D-05 conn opens AFTER successful update.
- Decoration step → `_wiki_relative_path_for`: dict-mediated, no API surface change in wiki-io. D-04 keeps wiki-io graph-unaware.
- `run_scan` error policy → caller error policy: D-07 hard-abort vs D-08 graceful means callers (CLI `scan` command, MCP `wiki_scan` tool) see two distinct outcomes. Planner ensures both paths surface correctly.

</code_context>

<specifics>
## Specific Ideas

- D-08's exact log line: `[NOT_INITIALIZED fallback: graph could not be initialized (<reason>); using path-based slugs]`. `<reason>` is the stringified `GraphNotInitializedError` message (e.g. "permission denied: .graph-wiki/graph/code.db"). One line; stderr; before any other scan output.
- D-04's batch query suggestion: `queries.list_packages(conn)` returns all `kind=package` node records. Join in-memory: `workspaces` dict keyed by `name` → records dict keyed by URI's last segment → merged. One DB round trip.
- D-03's `is_app` / `domain` attribute names: the v1.6 schema (per Phase 28 ONTOLOGY-SPEC and Phase 31 Domain Layer) likely uses `attrs.is_app` (boolean) and a separate `domain` edge relation, not an attribute. Planner: read `packages/graph-io/src/graph_io/queries.py` `describe_package` to see what's actually surfaced.
- D-01 fallback path if Phase 38 has NOT merged at Phase 39 plan-write time: planner can write the plan referencing `from graph_wiki_agent.commands.graph import update_graph` (or whatever Phase 38 picks) and add a Plan-level pre-condition check that fails fast with a clear "Phase 38 helper missing — check Phase 38 status" message.

</specifics>

<deferred>
## Deferred Ideas

- **In-process direct call to `graph_io.cli.ops_update.run` (bypassing Phase 38's adapter)** — Considered (D-01 alternative); rejected for surface consistency. Phase 39 deliberately accepts the hard dependency on Phase 38.
- **Subprocess `cg update`** — Considered; rejected; same reasons as Phase 38 D-06 (no PATH dep; programmatic error capture).
- **Deep change to `wiki_io.scan_monorepo._wiki_relative_path_for`** — Considered (D-04 alternative). Rejected because wiki-io should not gain a graph-io dependency for a routing concern that the scanner can decorate at the boundary.
- **Per-workspace fallback when graph IS initialized but a workspace is missing from it** — Not folded into D-08. If this scenario emerges in practice (scanner discovers a brand-new package after `cg update` runs), planner adds a per-workspace path-based fallback with a similar `[missing in graph: <name>; using path-based slug]` line. Out of scope for v1.7 unless the planner finds existing test coverage for it.
- **Retry on transient `cg update` failure** — Considered; rejected for simplicity. Add only if SQLite lock contention becomes a real production issue.
- **`graph-wiki-agent scan --no-graph-update` flag** — Listed in Claude's Discretion; planner picks. Useful for CI scenarios; mild scope expansion.
- **URI-keyed wiki redesign (flat-by-ID / by-domain / by-repo views)** — Future Requirement per REQUIREMENTS.md. Phase 39 explicitly preserves today's layout; v1.8 is the right place for the redesign.
- **Migration of existing apps/ and domains/ vault pages to a flat layout** — Considered briefly; rejected for v1.7. Layout change belongs in a dedicated phase.
- **Orphaned-page reconciliation on package rename** — Deferred to v1.8 per REQUIREMENTS.md "Future Requirements." Phase 40 (Ingestor) will document the limitation in code comments.
- **Phase 39 also touches `plugins/graph-wiki/` end-to-end smoke** — Already covered by Phase 35 HYGIENE-14 / D-02 automated test. SC#3 satisfied by reference.

</deferred>

---

*Phase: 39-scanner-consumes-graph-io*
*Context gathered: 2026-05-26*
