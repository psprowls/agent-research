# Phase 28: Schema v2 + URI Foundation - Context

**Gathered:** 2026-05-25
**Status:** Ready for planning

<domain>
## Phase Boundary

The `graph-io` store speaks schema v2. Every future emitter (Phases 29-31) has a `uri TEXT` nullable column on `nodes` to write to. Schema mismatches exit cleanly with code 4. URI composition is centralized in `graph_io/uri.py` with a `RepoContext` carrier and ships with all 7 helpers + unit tests. `update.run()` derives `(org, repo)` from `git remote` and threads `RepoContext` to `packages.refresh`, which writes `pkg_uri(ctx, name)` on Package nodes — proving the column path is wired end-to-end through `_upsert_node`.

**Strictly NOT in this phase:** Repository / SubPackage / File / EntryPoint / TestSuite / Domain emission; `resolve.sweep` guard extension; structural containment tree; derived edges; AST role flags; CLI surface additions; brand sweep. Those are Phases 29-34.

</domain>

<decisions>
## Implementation Decisions

### Schema migration / upgrade flow

- **D-01:** `cg update --full` against an existing schema-v1 `code.db` detects the version mismatch inside `update.run()` (after `_head()` succeeds, before `store.connect(create=True)`), unlinks `code.db` plus `code.db-wal` and `code.db-shm` siblings, then reopens with `create=True` and rebuilds from `_all_tracked(repo_root)`. A single line is logged to stderr: `Schema v1 detected — rebuilding code.db at schema v2.` No partial-state risk; no in-place `DROP TABLE` dance.
- **D-02:** `cli/main.py` wraps every non-`--full` command path that opens a connection (e.g., `cg update`, `cg find`, `cg status`, `cg describe-*`) with `except store.SchemaMismatchError as e:`. Handler prints to stderr: `error: graph schema is v1 but this build expects v2. Run \`cg update --full\` to rebuild.` and calls `sys.exit(exit_codes.SCHEMA_MISMATCH)` (= 4). No Python traceback in user-facing output. Satisfies SCHEMA-02.

### `(org, repo)` derivation

- **D-03:** `uri.py` exposes `parse_remote_url(url: str) -> tuple[str, str] | None` that handles **two** shapes only:
  - SSH: `git@HOST:ORG/REPO[.git]` (e.g., `git@github.com:pat/agent-research.git`)
  - HTTPS: `https://HOST/ORG/REPO[.git]` (e.g., `https://github.com/pat/agent-research`)
  - The `.git` suffix is stripped if present.
  - GitLab subgroups (multi-segment paths), `git://`, `file://`, and any other shape return `None` and fall through to local fallback. Subgroups are deferred to v1.7 per ONTOLOGY-SPEC §11 open questions.
- **D-04:** Remote-resolution chain: try `git remote get-url origin` only. If the command exits non-zero, or returns a URL that `parse_remote_url` cannot parse, fall back to local mode. Do not probe other remote names (`upstream`, `fork`, etc.) — keeps the path simple and avoids ambiguity.
- **D-05:** Local-only fallback yields `RepoContext(org="local", repo=repo_root.name)` — URIs render as `repo:local/myproject`, `pkg:local/myproject/auth-service`. The literal string `"local"` is the sentinel; no underscore prefix.

### URI helper API shape

- **D-06:** `graph_io/uri.py` defines a `RepoContext` dataclass with two `str` fields: `org` and `repo`. Frozen, hashable. All repo-scoped helpers take `ctx: RepoContext` as their first argument. The one exception is `domain_uri(name)`, which is repo-agnostic in v1.6 (Domain identity is the bare name, not `org/repo/name`).
- **D-07:** Helper signatures (locked):
  - `repo_uri(ctx: RepoContext) -> str` → `repo:org/repo`
  - `pkg_uri(ctx, name: str) -> str` → `pkg:org/repo/name`
  - `subpkg_uri(ctx, pkg_name: str, dotted_path: str) -> str` → `subpkg:org/repo/pkg_name/dotted.path` — dotted Python import path, NOT slash-separated FS path. e.g. `subpkg:local/agent-research/graph-io/graph_io.cli`.
  - `file_uri(ctx, rel_path: str) -> str` → `file:org/repo/rel/path/to/file.py` (forward slashes; rel_path is relative to repo root)
  - `entry_point_uri(ctx, pkg_name: str, ep_name: str) -> str` → `entry_point:org/repo/pkg_name/ep_name`
  - `test_suite_uri(ctx, suite_name: str) -> str` → `test_suite:org/repo/suite_name`
  - `domain_uri(name: str) -> str` → `domain:name` (NO ctx)
- **D-08:** All 7 helpers + `RepoContext` + `parse_remote_url` ship in Phase 28 with full unit coverage in `tests/test_uri.py` (~30-40 LOC). Phase 29+ imports them without churn. Satisfies SCHEMA-03 / success criterion #3.

### Phase 28 scope discipline

- **D-09:** Phase 28 **does** include the minimal `packages.py` edit needed to satisfy success criterion #1: after a `cg update --full` rebuild, `SELECT uri FROM nodes WHERE kind='package'` returns non-NULL values for every Package node. The edit: `packages.refresh(conn, repo_root, ctx)` gains a `ctx: RepoContext` parameter; each Package node it upserts carries `attrs["uri"] = pkg_uri(ctx, pkg_name)`.
- **D-10:** `_upsert_node` in `upsert.py` is extended to pop `attrs["uri"]` (if present) and write it to the `uri` column, NOT into `attrs_json`. This is the PITFALL 4 lock — covered by `tests/test_upsert.py::test_upsert_uri_lands_in_column` before any emitter work in Phase 29.
- **D-11:** `update.run()` derives `(org, repo)` once, constructs `RepoContext`, and threads it into `packages.refresh(conn, repo_root=repo_root, ctx=ctx)`. Phase 29 extends the same `ctx` thread to `structural_nodes.emit(conn, repo_root, ctx)`. The foundation work — git remote parsing, RepoContext construction, ctx threading — belongs in the foundation phase. Phase 29 should not have to revisit `update.run()` to introduce ctx for the first time.

### Test sentinels (must be green before Phase 29 starts)

- **D-12:** Three sentinel tests are mandatory exit criteria for Phase 28:
  1. `tests/test_schema.py::test_schema_version_is_two` — rename of existing `test_schema_version_is_one`
  2. `tests/test_schema.py::test_nodes_table_has_uri_column` — new
  3. `tests/test_upsert.py::test_upsert_uri_lands_in_column` — new
  Additionally: `tests/test_uri.py` covers each of the 7 helpers and `parse_remote_url` for SSH + HTTPS + unparseable input. `tests/test_store.py` covers the v1→v2 unlink+rebuild path via a fixture that pre-creates a v1 DB.

### Claude's Discretion

- Exact wording of stderr messages (Decisions 1, 2) — Claude may fine-tune for clarity but must include `cg update --full` directive and the `SCHEMA_MISMATCH` exit code semantic.
- Index naming (e.g., `idx_nodes_uri`) — Claude picks consistent with existing `idx_nodes_kind_name` / `idx_nodes_path` convention.
- Whether `parse_remote_url` returns `tuple[str, str] | None` or raises — Claude picks; `Optional` is fine, but if exceptions read cleaner at the callsite that's also acceptable. Outcome (graceful fall-through to local) is what matters.

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Source-of-truth ontology spec
- `.planning/research/ONTOLOGY-SPEC.md` — full ontology spec (Pat's brainstorm, copied from `/Users/pat/Downloads/code-graph-ontology-spec_2.md`). Phase 28 lands the §2 (Identity & URIs) and §8 (Schema/exit codes) foundation only.

### v1.6 research (all five are mandatory)
- `.planning/research/SUMMARY.md` — executive summary; Phase A section starts at line 100 ("Implications for Roadmap"). Reads first.
- `.planning/research/ARCHITECTURE.md` §"URI Identity Layer" + §"Phase A: Foundation" + §"source-parser Boundary" (the last is informational for Phase 29; not needed for 28 implementation).
- `.planning/research/PITFALLS.md` — pitfalls 1, 2, 4 are Phase 28's responsibility to prevent (SCHEMA_VERSION bumped but DDL not updated; SCHEMA_MISMATCH unwired; URI lands in attrs_json). Pitfall 5 (resolve.sweep deletes Repository/Domain) is Phase 29 — note for context only.
- `.planning/research/STACK.md` — confirms no new deps for Phase 28 (`sqlite3` + stdlib only; `pyyaml` is a Phase 31 add).
- `.planning/research/FEATURES.md` — feature inventory; Phase 28 has no user-facing CLI surface adds.

### Requirements + roadmap
- `.planning/REQUIREMENTS.md` — SCHEMA-01 through SCHEMA-05 (lines for `## SCHEMA` section). These are the 5 requirements Phase 28 closes.
- `.planning/ROADMAP.md` "Phase 28: Schema v2 + URI Foundation" block — Success Criteria 1-5 are non-negotiable acceptance bar.
- `.planning/PROJECT.md` "Current Milestone: v1.6 Code Graph Ontology Expansion" — milestone-level context (graph-io-only milestone; plugin and graph-wiki-agent untouched).

### Existing graph-io code (read before editing)
- `packages/graph-io/src/graph_io/schema.py` — `SCHEMA_VERSION` and `_DDL_STATEMENTS` live here. Bump + add `uri TEXT` column + `idx_nodes_uri` index.
- `packages/graph-io/src/graph_io/store.py` — `SchemaMismatchError`, `_check_schema_version`, `connect()`, `read_only_connect()`. Error class already exists; only `cli/main.py` wiring is new.
- `packages/graph-io/src/graph_io/upsert.py` — `_upsert_node`, `_insert_node`. Pop `uri` from `attrs` and write to column.
- `packages/graph-io/src/graph_io/update.py` — `run()` is the orchestrator; add `(org, repo)` derivation + `RepoContext` construction + threading to `packages.refresh`. Note the existing `_default_lock_timeout()` reads `LATTICE_GRAPH_LOCK_TIMEOUT_MS` — out of scope for Phase 28; deprecation alias is Phase 34.
- `packages/graph-io/src/graph_io/packages.py` — extend `refresh()` to accept `ctx: RepoContext` and write `pkg_uri(ctx, name)` on each Package node.
- `packages/graph-io/src/graph_io/exit_codes.py` — `SCHEMA_MISMATCH = 4` already defined.
- `packages/graph-io/src/graph_io/cli/main.py` — add `SchemaMismatchError` handler with friendly stderr message + `sys.exit(SCHEMA_MISMATCH)`.
- `packages/graph-io/tests/test_schema.py`, `test_store.py`, `test_upsert.py` — existing tests to extend with sentinels.

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- `store.SchemaMismatchError` already exists with a clean message — no need to redesign; just wire into CLI.
- `store.apply_schema` is idempotent (`CREATE TABLE IF NOT EXISTS` + metadata upsert) — safe to call after unlink+reopen.
- `upsert._upsert_node` already serializes attrs via `_serialize(attrs)` — pop `uri` BEFORE calling `_serialize` to keep the column separate from `attrs_json`.
- `update._git`, `_head`, `_all_tracked`, `_diff` helpers — `_git(["remote", "get-url", "origin"], cwd=repo_root)` is the right primitive for D-04. Returns stdout; raises `NotInGitRepoError` on non-zero exit, which is the natural fall-through trigger.
- `exit_codes.SCHEMA_MISMATCH = 4` and `UPDATE_IN_PROGRESS = 6` are already declared; no constant churn.

### Established Patterns
- Hand-rolled SQLite version gate + mandatory full rebuild is the existing graph-io pattern (per `schema.py` module docstring: "Bumping SCHEMA_VERSION forces a full rebuild via `cg update --full`"). Phase 28 extends, doesn't change, the pattern.
- All DDL is in `_DDL_STATEMENTS` tuple in `schema.py`. Add the `uri TEXT` column to the `CREATE TABLE nodes` statement and an `idx_nodes_uri` index to the tuple. Both `CREATE TABLE IF NOT EXISTS` and `CREATE INDEX IF NOT EXISTS` are idempotent — no migration code needed.
- Custom exception classes raised from low-level modules (`store.SchemaMismatchError`, `store.GraphNotInitializedError`, `update.NotInGitRepoError`, `update.UpdateInProgressError`) and caught in `cli/main.py` for exit-code translation — Phase 28 wires `SchemaMismatchError` to this pattern.

### Integration Points
- `update.run()` is the only writer entry point. v1→v2 unlink+rebuild happens here, before `store.connect(create=True)`.
- `cli/main.py` is the only place `SchemaMismatchError` should be caught — keeps the error-to-exit-code translation in one layer.
- `packages.refresh` is the only Package writer — adding ctx here propagates correctly.

</code_context>

<specifics>
## Specific Ideas

- `RepoContext` is a `@dataclass(frozen=True)` for hashability and immutability — keeps it safe to pass through async fanouts in later phases without aliasing risk (even though Phase 28 itself is sync).
- The stderr message for v1→v2 rebuild should NOT use rich/color — graph-io has no colorization elsewhere; plain `print(..., file=sys.stderr)` matches the existing style.
- `parse_remote_url` regexes (suggested, not locked):
  - SSH: `^git@[^:]+:([^/]+)/(.+?)(?:\.git)?$`
  - HTTPS: `^https?://[^/]+/([^/]+)/(.+?)(?:\.git)?/?$`
  Returning `None` for non-matches; the caller logs and falls back to local.

</specifics>

<deferred>
## Deferred Ideas

- **GitLab subgroup support** (`group/subgroup/repo` URLs) — defer to v1.7. Add when a real repo demands it; currently this monorepo and Pat's other repos are all flat GitHub paths.
- **`UNIQUE` constraint on `uri`** — explicitly deferred to v1.7 per research; revisit after URI generation is validated against real repos in Phase 29-31.
- **AST node URIs** (functions / classes / methods) — out of v1.6 scope. `uri` column is nullable for exactly this reason.
- **`UPDATE_IN_PROGRESS` exit code (6) wiring** in `cli/main.py` — already covered by existing `UpdateInProgressError` in `update.py`. If `cli/main.py` doesn't already catch it (check during planning), add a sibling handler alongside the new `SchemaMismatchError` handler — but this is a 2-line fix, not a separate gray area.
- **`LATTICE_GRAPH_LOCK_TIMEOUT_MS` deprecation alias** → Phase 34 (Brand Sweep). Phase 28 does not touch the env var name.

</deferred>

---

*Phase: 28-schema-v2-uri-foundation*
*Context gathered: 2026-05-25*
