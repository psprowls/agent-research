# Phase 39: Scanner Consumes graph-io — Research

**Researched:** 2026-05-26
**Status:** Research complete; ready for planning.

> Read alongside `39-CONTEXT.md` — this RESEARCH.md does NOT restate decisions D-01..D-08.
> Its job is to surface implementation-level facts the planner needs that are not in CONTEXT.md.

## RESEARCH COMPLETE

---

## 1. Phase 38 Helper Surface — What Phase 39 Calls Into (D-01)

Phase 38's `agents/graph-wiki-agent/src/graph_wiki_agent/commands/graph.py` (HARD DEPENDENCY — not yet merged at plan-write time, verified against Phase 38's 38-01-PLAN.md) exports the following helpers that Phase 39 reuses:

- `_DESCRIBE_DISPATCH: dict[str, tuple[Module, str | None]]` — not needed by Phase 39.
- `_build_namespace(module, *, repo: Path, workspace: Path, **extras) -> argparse.Namespace` — produces the `argparse.Namespace` that cg modules' `run(args)` expects (with `fmt="human"`, `mode="workspace"`, `_module`, `_parser=None`).
- `_capture_run(module, args) -> tuple[int, str, str]` — invokes `module.run(args)` with stdout/stderr redirected to `StringIO()`; returns `(exit_code, stdout, stderr)`. Catches `SystemExit`.
- `_resolve_paths(workspace_arg: str) -> tuple[Path, Path]` — uses `workspace_io.config.resolve(require_manifest=False)`. Returns `(repo_root, workspace)`.
- `graph_app: typer.Typer` — top-level subapp registered at `cli.py` with `app.add_typer(graph_app, name="graph")`.
- `graph_app.command("build")` body — implements: resolve paths, capture cg `ops_update.run(Namespace(repo, workspace, full))`, propagate exit code via `typer.Exit`. Default flags `full=False, trace=False, model=None, workspace=""`.

**Phase 39's call pathway (D-01, D-02):** Phase 39 does NOT call `graph_app.command("build")` as a Typer command (would require `CliRunner`); it imports `from graph_wiki_agent.commands.graph import _build_namespace, _capture_run` and calls `ops_update.run` directly through `_capture_run(ops_update, _build_namespace(ops_update, repo=repo, workspace=wiki, full=False))`. This satisfies D-01 (calls through Phase 38's adapter helpers — single agent-side surface) AND D-02 (no `--trace`, no `--model` — the function receives `full=False` only).

**If Phase 38's helpers are renamed at merge time:** Phase 39's plan references the function names as documented in Phase 38's 38-01-PLAN.md (`_build_namespace`, `_capture_run`). The executor verifies at execute time and adjusts the import if Phase 38 landed with different names. Plan-level pre-condition check (Task 0 / first task): `python -c "from graph_wiki_agent.commands.graph import _build_namespace, _capture_run, ops_update"` exits 0.

---

## 2. cg ops_update Exit-Code Surface (D-07, D-08)

`packages/graph-io/src/graph_io/cli/ops_update.py:15-30` catches these exceptions and maps to exit codes:

| Exception class | Exit code constant | Numeric | Phase 39 disposition |
|-----------------|--------------------|--|----------------------|
| `update.NotInGitRepoError` | `NOT_IN_GIT_REPO` | 5 | HARD ABORT (D-07) |
| `update.UpdateInProgressError` | `UPDATE_IN_PROGRESS` | 6 | HARD ABORT (D-07) |
| `store.SchemaMismatchError` | `SCHEMA_MISMATCH` | 4 | HARD ABORT (D-07) |
| Any other `Exception` | `GENERIC` | 1 | HARD ABORT (D-07) |
| Success | `SUCCESS` | 0 | proceed (D-06: graph guaranteed initialized) |

**Critical finding — D-08 surface gap:** `ops_update.run` does NOT explicitly map any exception to `NOT_INITIALIZED` (3). The `NOT_INITIALIZED` exit code from `exit_codes.py` exists but is emitted by *read-side* cg modules (e.g. `q_describe_package` when `read_only_connect` raises `GraphNotInitializedError`), NOT by `ops_update`. This is by design: `ops_update.run` calls `update.run(repo, workspace, full)` which internally calls `store.connect(create=True)` — it auto-initializes the DB if missing (matches D-06).

**Therefore D-08's "NOT_INITIALIZED-class init failure" cannot arrive from `ops_update.run` itself.** The graceful-fallback branch is reachable only when:
- The `update.run` internal call fails to create `code.db` due to a *filesystem* issue (parent dir not writable, disk full, parent path is a non-directory).
- These manifest as `OSError`/`PermissionError`/`FileExistsError` and fall under `ops_update.run`'s generic `except Exception` → `GENERIC` (1) branch.

**Practical mapping for Phase 39:** Distinguish init-failure (graceful fallback) from runtime-failure (hard abort) by examining the captured stderr from `_capture_run`. If `exit_code == exit_codes.GENERIC` AND stderr matches a permission/disk pattern (specifically: contains any of `"Permission denied"`, `"Read-only file system"`, `"No space left on device"`, `"Errno 13"`, `"Errno 28"`, `"Errno 30"`), classify as init-failure → fallback path. Otherwise: hard-abort.

The substring-match approach is acceptable for v1.7 (CONTEXT.md D-08 explicitly approves stderr-substring grep as a fallback when exit-code granularity is insufficient). The list is conservative; new patterns can be added without API churn. This is the "brittle but acceptable" path called out in CONTEXT.md.

**Alternative not chosen:** Adding a granular exit code to `ops_update.run` was considered (CONTEXT.md D-08 says "planner adds a granular exit code … if the surface conflates"). Rejected for Phase 39 because (a) it bifurcates the graph-io surface with a code that only makes sense for `ops_update`, not the read-side modules; (b) the runtime/init distinction is fundamentally about *why* the OS rejected the write — stderr is the natural channel for that detail; (c) v1.7 scope is the scanner, not the cg API.

---

## 3. URI → Slug Derivation: Graph Schema Reality (D-03, D-04)

The graph stores the URI on each `kind:package` node via `nodes.attrs_json` (see `packages/graph-io/src/graph_io/packages.py:113-118`):

```python
attrs={
    "version": info["version"],
    "dependencies": info["dependencies"],
    "language": info["language"],
    "uri": pkg_uri(ctx, info["name"]),   # e.g. "pkg:org/repo/graph-io"
}
```

`queries.list_packages(conn)` returns `list[NodeRecord]` with `.name`, `.path`, `.attrs` (dict — already JSON-decoded). One DB round trip retrieves every package's name + path + URI.

**`is_app` is NOT in the graph attrs.** Search across `packages/graph-io/src/` for `is_app` returns zero matches. The graph schema does not model "app vs library" — Phase 28 ONTOLOGY-SPEC treats apps as packages. The `pkg["type"] == "app"` distinction in `wiki_io/scan_monorepo.py:629` is FILESYSTEM-derived via `_infer_package_type()` (dirname contains `app`/`web`/`expo`, OR package.json has a `start` script).

**`domain` IS in the graph** but as an edge, not an attr. Domains are emitted as `kind:domain` nodes with `belongs_to_domain` edges (Package → Domain). `queries.describe_package(conn, name=<pkg>)` returns a `PackageDescription` with `.domains: list[str]`. To batch-fetch all package→domain mappings in one query, the planner has two options:

- **Option A (extra query):** Call `describe_package` per workspace. N round trips; rejected — D-04 requests batch.
- **Option B (single SQL):** New helper or inline SQL: `SELECT p.name, d.name FROM nodes p JOIN edges e ON e.src = p.id AND e.kind='belongs_to_domain' JOIN nodes d ON e.dst = d.id WHERE p.kind='package'` — returns `(pkg_name, domain_name)` pairs. Build dict on agent side.

**Recommendation:** Option B, but inline in the agent (not a new `graph_io.queries` helper). Phase 39 does not need to expand the public queries surface for one local join. The decoration code lives in `commands/scan.py` (D-04: kept inline). Future phases can promote the SQL to a public `queries.list_package_domains(conn)` helper if reused.

**Final routing decisions for Phase 39:**
- `pkg["uri"]` ← from graph (`NodeRecord.attrs["uri"]`).
- `pkg["domain"]` ← from graph (`belongs_to_domain` edge join). OVERWRITES the filesystem-derived `pkg["domain"]` from `_discover_from_pinned` (when present, graph wins; when absent in graph but present from filesystem, keep filesystem value as a fallback for plugins/non-standard layouts).
- `pkg["type"]` (app vs library) ← NOT overwritten. Graph doesn't carry this. Filesystem heuristic remains authoritative (CONTEXT.md D-03 "plugin fallback" path).
- `_wiki_relative_path_for(pkg, vault_dir)` reads `pkg["type"]` and `pkg["domain"]` UNCHANGED. The function signature does not change. Behavior preserved when graph fields are absent (NOT_INITIALIZED fallback / pre-Phase-38 scenarios).

---

## 4. Workspace ↔ Graph Node Join Key (D-04)

`discover_workspaces` returns dicts keyed conceptually by `name`. The graph stores packages by `name` too. The join key is the *unscoped* package name (per `wiki_io.scan_monorepo.unscope` — strips npm scope `@scope/name` → `name`).

**Edge case:** a monorepo can have multiple workspaces with the same unscoped name (e.g. `@scope-a/utils` and `@scope-b/utils` both unscope to `utils`). Today's scanner uses `unscope(w["name"])` as the dict key (`commands/scan.py:318: ws_by_name = {unscope(w["name"]): w for w in workspaces}`) — accepts the collision. Phase 39 follows the same convention: the decoration step joins on `unscope(w["name"]) == NodeRecord.name`. Collision behavior is unchanged from today.

**If a workspace is discovered but missing from the graph:** D-08-adjacent (CONTEXT.md "Deferred Ideas — Per-workspace fallback") explicitly defers this case. Phase 39's decoration step LEAVES `pkg["uri"]` / `pkg["domain"]` absent for unmatched workspaces; `_wiki_relative_path_for` reads `pkg.get("domain")` (None-safe) and `pkg.get("type")` (still set from filesystem) — routing degrades to today's filesystem-only behavior for that workspace. No error, no log line per CONTEXT.md.

---

## 5. Connection Lifetime (D-05) — Mirror Phase 37

Phase 37 D-03 / Plan 02 Task 1 established the pattern at `agents/graph-wiki-agent/src/graph_wiki_agent/commands/query.py` (the librarian command). Confirmed shape:

```python
from graph_io.store import read_only_connect, GraphNotInitializedError
from workspace_io.paths import graph_dir

conn = None
try:
    try:
        conn = read_only_connect(graph_dir(wiki) / "code.db")
    except GraphNotInitializedError:
        conn = None  # fallback path
    # ... use conn (or skip if None) ...
finally:
    if conn is not None:
        conn.close()
```

Phase 39 reuses this exact pattern. ONE `read_only_connect` call at the top of `run_scan` (after `cg update` returns SUCCESS); ONE `finally` block at function exit. No per-workspace opens (Pitfall 4).

**Sequencing note:** the connection is opened AFTER `ops_update.run` succeeds. D-06 guarantees `code.db` exists after a successful update on fresh workspaces (`update.run` calls `store.connect(create=True)` internally).

---

## 6. Where to Place Code in `run_scan` (D-04)

Current `run_scan` pipeline (lines 226-456) has 14 numbered steps. Phase 39 inserts:

| Insertion point | New step | Description |
|-----------------|----------|-------------|
| Top of function body, before any cg/conn work | Step 0a (try open) | Compute `wiki, repo` early (already step 1); compute `graph_db_path = graph_dir(wiki) / "code.db"`; wrap remaining body in `try`/`finally` for conn close. |
| After step 1 (resolve_wiki_and_repo), BEFORE step 3 (discover_workspaces) | Step 1.5 (cg update) | Call `_capture_run(ops_update, _build_namespace(ops_update, repo=repo, workspace=wiki, full=False))`. Branch on result (success / init-failure / hard-fail). Emit scan-log line per SC#1. |
| After successful cg update | Step 1.6 (open read-only conn) | `conn = read_only_connect(graph_dir(wiki) / "code.db")`. On `GraphNotInitializedError` (defensive — should not occur after a successful update): set `conn = None` and emit the NOT_INITIALIZED fallback log line. |
| After step 3 (`discover_workspaces`), BEFORE step 4 (file_map build) | Step 3.5 (decoration) | If `conn is not None`: run a single SQL query to fetch `(name, attrs_json, domain_name)` for all packages; decorate each workspace dict with `pkg["uri"]`, `pkg["domain"]`. Plugins/unmatched workspaces are silently skipped (NodeRecord-name miss). |
| `finally` block at function exit | Step 15 (conn close) | `if conn is not None: conn.close()`. |

The existing step 7 `_wiki_relative_path_for` calls (which run inside `discover_workspaces`) read `pkg["type"]` and `pkg["domain"]` UNCHANGED. **Key implication:** `discover_workspaces` is invoked BEFORE the decoration step, but `wiki_relative_path` is computed INSIDE `discover_workspaces`. The decoration therefore CANNOT affect `wiki_relative_path` unless we (a) call `discover_workspaces`, (b) decorate, (c) recompute `wiki_relative_path`.

**Resolution:** Two paths:

- **A. Mutate `pkg["wiki_relative_path"]` after decoration.** After step 3.5, re-run `_wiki_relative_path_for(pkg, vault_dir=pkg.pop("_container_vault_dir_phase39", None))` per workspace IF `pkg["domain"]` changed (graph-derived domain replaced filesystem). Cleaner but `discover_workspaces` already pops `_container_vault_dir` (line 608), so we'd need to either (i) reintroduce vault_dir tracking or (ii) accept that vault_dir info is gone by step 3.5.

- **B. Pre-compute graph data, then call decorate before `discover_workspaces`.** Reverse the order: `cg update` → open conn → query graph for all package URIs+domains into a side table → call `discover_workspaces` → decorate inside the same pass `discover_workspaces` makes (before `_wiki_relative_path_for` runs). This requires a hook into `discover_workspaces`. CONTEXT.md D-04 explicitly says "`discover_workspaces` / `_wiki_relative_path_for` UNCHANGED" — rules out modifying `discover_workspaces`.

- **C. Recompute `wiki_relative_path` after decoration without involving vault_dir.** After step 3.5, iterate workspaces; for any pkg with a graph-derived `pkg["domain"]` that differs from the pre-decoration value, recompute `pkg["wiki_relative_path"] = _wiki_relative_path_for(pkg, vault_dir=None)`. Lose the `vault_dir` override for these. Acceptable: domain-mapped workspaces never hit the `vault_dir` branch anyway (they hit `domains/<d>/packages/<n>/overview.md` per the routing function).

**Decision (planner):** Path C. Domain-routed workspaces don't need `vault_dir` because the routing function returns `domains/<d>/packages/<n>/overview.md` without consulting `vault_dir`. Apps and plain library workspaces — whose routing DOES use `vault_dir` — are not affected by graph decoration (graph doesn't carry `is_app`; plain libraries without a domain keep their filesystem-derived domain `None`). So path C touches only the subset where vault_dir is structurally unused.

Concretely:
```python
# After step 3 (discover_workspaces) — step 3.5 begins:
if conn is not None:
    pkg_records = {r.name: r for r in queries.list_packages(conn)}
    domain_map = _query_package_domains(conn)  # local helper, single SQL
    for w in workspaces:
        key = unscope(w["name"])
        if key in pkg_records:
            uri = pkg_records[key].attrs.get("uri")
            if uri:
                w["uri"] = uri
        if key in domain_map:
            graph_domain = domain_map[key]
            if graph_domain and w.get("domain") != graph_domain:
                w["domain"] = graph_domain
                # Recompute slug only when domain changed
                w["wiki_relative_path"] = _wiki_relative_path_for(w, vault_dir=None)
```

This satisfies D-04 ("`_wiki_relative_path_for` stays unchanged") AND preserves D-03 routing.

---

## 7. SC#1 Log Line Format and Channel (D-08)

CONTEXT.md SC#1 says the `cg update` call "is visible in the scan log output." The scan already calls `append_log(wiki, "scan", "<msg>", ...)` at function end. Phase 39 adds two new `append_log` entries plus the NOT_INITIALIZED stderr line:

| Event | Channel | Format |
|-------|---------|--------|
| Pre-scan `cg update` started | scan log | `append_log(wiki, "scan", "cg update (incremental)", ...)` |
| Pre-scan `cg update` succeeded | scan log | `append_log(wiki, "scan", "cg update complete: exit_code=0", ...)` |
| Pre-scan `cg update` failed (hard abort, D-07) | scan log + stderr | log line `cg update failed: exit_code=<N>` AND stderr line `[scan aborted: cg update failed (<reason>)]`. Then raise. |
| Pre-scan `cg update` failed (init-only, D-08 fallback) | scan log + stderr | log line `NOT_INITIALIZED fallback: <reason>` AND stderr line `[NOT_INITIALIZED fallback: graph could not be initialized (<reason>); using path-based slugs]` |
| Decoration step ran | scan log | `append_log(wiki, "scan", f"graph decoration: {n_decorated}/{n_workspaces} workspaces", ...)` |

The stderr line for D-08 matches CONTEXT.md "specifics" verbatim. The scan log entries provide an auditable trail visible in `.graph-wiki/log.md`.

**Channel choice:** Use Python `sys.stderr.write(...)` directly for the one-shot D-08 line (matches Phase 37 D-04 librarian pattern — `[graph unavailable: ...]` is sys.stderr.write in `commands/query.py`). `append_log` is for the persistent scan log.

---

## 8. SC#3 Status — Already Satisfied by Phase 35 (CONTEXT confirms)

CONTEXT.md Canonical References explicitly maps SC#3 → Phase 35's `packages/wiki-io/tests/test_bootstrap_e2e_no_broken_links.py`. Phase 39 plan should:

- Cite the test path in `must_haves.truths` as a reference (not as a new artifact).
- Add NO new manual transcript task.
- Note in SUMMARY.md that SC#3 satisfaction is by reference, not by new artifact.

Verify at execute time: `test -f packages/wiki-io/tests/test_bootstrap_e2e_no_broken_links.py && uv run --package wiki-io pytest packages/wiki-io/tests/test_bootstrap_e2e_no_broken_links.py -q` exits 0.

---

## 9. Testing Strategy

Three layers of tests:

### Unit tests (fast, mocked cg + mocked conn)

`agents/graph-wiki-agent/tests/unit/test_scan_graph_integration.py` (NEW). Use `unittest.mock.patch.object(scan_module.ops_update, "run", ...)` to short-circuit `cg update`, then verify:

- `cg update succeeded` → conn opened → decoration applied → workspaces have `pkg["uri"]`.
- `cg update returned NOT_IN_GIT_REPO (5)` → hard abort, no conn opened, scan does not proceed past step 1.5.
- `cg update returned GENERIC (1) with stderr "Permission denied"` → D-08 fallback path; conn NOT opened; scan proceeds; stderr line emitted exactly once with the prescribed format; workspaces have NO `pkg["uri"]`.
- `cg update returned GENERIC (1) with stderr "some other runtime error"` → D-07 hard abort.
- Connection is closed in `finally` even when `run_scan` raises mid-fan-out (patch the scanner pool to raise).

### Integration test (real cg, real conn, fixture monorepo)

`agents/graph-wiki-agent/tests/integration/test_scan_graph_end_to_end.py` (NEW, marker `integration`). Uses a fixture monorepo (existing `packages/graph-io/tests/fixtures/sample_monorepo/` is a candidate; planner verifies fixture has both `packages/` and a domain). Steps:

1. Run `run_scan(workspace_path=fixture)` with no pre-existing graph.
2. Assert `.graph-wiki/graph/code.db` exists after the scan.
3. Assert the scan log contains `cg update complete: exit_code=0`.
4. Assert one of the workspaces in the resulting `ScanResult.added` lives at the graph-URI-derived path (e.g. `packages/<name>/overview.md`).

Run with `pytest -m integration`; excluded from quick suite.

### Regression test (SC#3, by reference)

`packages/wiki-io/tests/test_bootstrap_e2e_no_broken_links.py` — already exists from Phase 35. Phase 39 verifies it still passes (no changes to wiki-io expected).

---

## 10. Files to Modify / Create

| File | Action | Reason |
|------|--------|--------|
| `agents/graph-wiki-agent/src/graph_wiki_agent/commands/scan.py` | MODIFY | Insert steps 0a, 1.5, 1.6, 3.5, finally close. ~80 LOC net addition. |
| `agents/graph-wiki-agent/tests/unit/test_scan_graph_integration.py` | CREATE | Unit tests for the new branches. |
| `agents/graph-wiki-agent/tests/integration/test_scan_graph_end_to_end.py` | CREATE | End-to-end fixture test (marker `integration`). |
| `agents/graph-wiki-agent/pyproject.toml` | VERIFY | Confirm `graph-io` already listed (added in Phase 37). No change expected. |

No changes to `packages/wiki-io/`. No changes to `packages/graph-io/`. No changes to `commands/graph.py` (Phase 38 owns it).

---

## 11. Risk Surface

| Risk | Likelihood | Mitigation |
|------|-----------|------------|
| Phase 38 helper names differ at merge time | MEDIUM | Plan Task 0 (pre-condition import check) — fail fast with a clear "Phase 38 helper missing" message. Plan tasks 1-5 import the documented names; executor updates if Phase 38 lands different. |
| `pkg_uri` format changes in future graph-io | LOW | Phase 39 reads `attrs["uri"]` verbatim — no parsing. Format change would not break Phase 39 unless URI suffix (the unscoped name) drifts from `NodeRecord.name`. |
| stderr-substring grep for init-failure misfires | MEDIUM | False positive: a runtime error whose stderr coincidentally contains "Permission denied" would graceful-fallback instead of hard-aborting. Conservative pattern list (see §2) limits this. False negative (init failure on an unusual filesystem) would hard-abort — safe-side. Document in SUMMARY.md so future phases can promote to a granular exit code. |
| Decoration step doubles scan runtime on huge monorepos | LOW | One SQL query for `list_packages` (~ms) + one SQL query for domain join (~ms). Negligible vs LLM fan-out. |
| `cg update` blocks for minutes on first run of a large repo | LOW (acceptable) | Existing `cg update` performance. Phase 39 does not optimize. Users who need to skip can run `graph-wiki-agent scan` after a separate `cg update`; Phase 39 does not add a `--no-graph-update` flag (CONTEXT.md "Claude's Discretion" — declined). |
| Existing scanner tests break due to graph requirement | HIGH if not handled | All existing scan tests are filesystem-only fixtures with no `.graph-wiki/graph/code.db`. Phase 39 must either (a) seed a graph in each test, or (b) ensure the NOT_INITIALIZED fallback path is robust enough that existing tests pass without modification. The init-failure path leaves the scanner functioning; existing tests pass. Verify in Task 5. |

---

## 12. Validation Architecture

**Per-task automated verification:**

| Task | Verification command | Latency |
|------|----------------------|---------|
| 1 | `uv run --package graph-wiki-agent python -c "from graph_wiki_agent.commands.graph import _build_namespace, _capture_run, ops_update; print('ok')"` | <2s |
| 2 | `uv run --package graph-wiki-agent pytest agents/graph-wiki-agent/tests/unit/test_scan_graph_integration.py -q -k cg_update_dispatch` | <5s |
| 3 | `uv run --package graph-wiki-agent pytest agents/graph-wiki-agent/tests/unit/test_scan_graph_integration.py -q -k decoration` | <5s |
| 4 | `uv run --package graph-wiki-agent pytest agents/graph-wiki-agent/tests/unit/test_scan_graph_integration.py -q -k fallback` | <5s |
| 5 | `uv run --package graph-wiki-agent pytest agents/graph-wiki-agent/tests/ -q --ignore=agents/graph-wiki-agent/tests/integration` | <30s |
| 6 | `uv run --package graph-wiki-agent pytest agents/graph-wiki-agent/tests/integration/test_scan_graph_end_to_end.py -q -m integration` | <60s |

**Sampling rate:**
- After every task commit: run that task's verify command.
- After Wave 1: run the unit test full suite (Task 5's command).
- Before `/gsd:verify-work`: run the integration test (Task 6's command) plus `uv run --package wiki-io pytest packages/wiki-io/tests/test_bootstrap_e2e_no_broken_links.py -q` (SC#3 regression).

---

## 13. Sources

- `agents/graph-wiki-agent/src/graph_wiki_agent/commands/scan.py:226-456` — current `run_scan` pipeline (modification site).
- `agents/graph-wiki-agent/src/graph_wiki_agent/commands/query.py` (Phase 37 librarian) — connection-lifetime pattern (D-05 mirror).
- `packages/graph-io/src/graph_io/cli/ops_update.py:1-30` — exit-code surface for `cg update`.
- `packages/graph-io/src/graph_io/exit_codes.py` — exit-code constants.
- `packages/graph-io/src/graph_io/store.py` — `read_only_connect`, `GraphNotInitializedError`.
- `packages/graph-io/src/graph_io/packages.py:88-132` — `attrs["uri"]` shape; `pkg_uri` composition.
- `packages/graph-io/src/graph_io/queries.py:166-225` (`find`), `536-538` (`list_packages`), `290-366` (`describe_package`).
- `packages/wiki-io/src/wiki_io/scan_monorepo.py:613-635` — `_wiki_relative_path_for` routing (stays unchanged).
- `.planning/phases/38-graph-wiki-agent-graph-subcommand/38-01-PLAN.md` — Phase 38 helper signatures (`_build_namespace`, `_capture_run`).
- `.planning/phases/37-librarian-grounding-tools/37-02-PLAN.md` — D-03/D-04 fallback pattern Phase 39 mirrors.
- `.planning/phases/35-wiki-bootstrap-hygiene-burn-down/35-CONTEXT.md` — SC#3 regression test reference.

---

*Phase: 39-scanner-consumes-graph-io*
*Research completed: 2026-05-26*
