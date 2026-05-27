# Phase 43: Entity Writer - Context

**Gathered:** 2026-05-26
**Status:** Ready for planning

<domain>
## Phase Boundary

Phase 43 has **two waves**:

**Wave 1 — graph-io kind extension.** Add `dependency` and `plugin` as first-class graph kinds in `graph_io._VALID_KINDS`, with ingestion, queries, and tests:
- `dependency` nodes ingested from each workspace member's `pyproject.toml` (`[project.dependencies]` + `[dependency-groups]`); one node per `(ecosystem, name)` tuple; `used_by` edges to consumer packages.
- `plugin` nodes ingested from `.graph-wiki.yaml` `plugins[]` array (workspace-io already parses this manifest in v1.2/v1.3).
- New query helpers: `describe_dependency`, `list_dependencies`, `describe_plugin`, `list_plugins`. Existing query patterns (per `queries.py::describe_package`) are the template.

**Wave 2 — wiki-io entity writer.** Implement `write_entities(conn, wiki_root, admitted_kinds)` per the roadmap goal:
- Create entity pages for nodes that don't have one yet (from kind-specific template under `wiki_io/assets/page-templates/entity-<kind>.md`).
- Merge scanner-owned frontmatter keys on existing pages; preserve all human-authored keys (Phase 42 D-06..D-09 contract).
- Hard-delete entity pages whose URIs no longer exist in the graph; append every deletion to `.graph-wiki/deletions.log`.
- Acquire `.graph-wiki/scan.lock` on entry; release in a finally block including exception paths.
- Return `EntityWriteResult` with per-state URI lists + needs_narrative set + per-page errors.

**`package_family` is deferred to v1.9.** v1.8 callers pass `ADMITTED_KINDS_V18 = {repository, domain, package, test_suite, dependency, plugin}` (six of the seven from Phase 42's frozenset). Phase 42's `package_family_uri` builder + `entity-package-family.md` template remain in the codebase as "ready for v1.9" — dormant in v1.8. This is a deliberate scope reduction (driven by `package_family` being a curation concept without a clear ingestion source) and is documented as such in STATE.md.

**Phase 46 ripple:** the cutover phase will NOT remove `wiki/package-family/` in v1.8 (no entity pages exist to replace it). Document this in CONTEXT.md when Phase 46 is discussed.

**Not in scope (Phase 43):**
- LLM narrative generation under `## Narrative` (Phase 45)
- Scanner pipeline wiring (`run_scan` Steps 9a/9b/11/12 — Phase 45)
- Index generation (Phase 44)
- Inbound link rewriting (Phase 46)

</domain>

<decisions>
## Implementation Decisions

### Wave 1 — graph-io extension (the architectural piece)

- **D-01:** **Add `dependency` and `plugin` to `graph_io._VALID_KINDS`** in Phase 43, alongside the existing 10 kinds. The frozenset becomes `{function, class, method, file, package, repository, subpackage, entry_point, test_suite, domain, dependency, plugin}`. Test in `packages/graph-io/tests/test_queries.py` asserts both new values are valid.
- **D-02:** **`dependency` ingestion source = workspace pyproject.toml.** For each workspace member discovered by `packages.py`, parse `[project.dependencies]` + every `[dependency-groups].<group>` list. Emit one `dependency` node per distinct `(ecosystem, name)` tuple — ecosystem defaults to `pypi` (only Python today; the field exists so future stacks can be admitted without reshuffling). Emit `used_by` edge: `consumer_package -[used_by]-> dependency`. Versions captured in node `attrs` as `versions_in_use: list[str]` (multiple workspace members may pin different versions).
- **D-03:** **`plugin` ingestion source = `.graph-wiki.yaml` `plugins[]` array.** Use workspace-io's existing manifest parser. Emit one `plugin` node per array entry; node `name` is the plugin name (e.g., `graph-wiki`). `ecosystem` attr stores the plugin host (`claude-code` for now). Plugin nodes have no inbound edges in v1.8 (plugins aren't "used by" packages in the import sense); they're entities for documentation, not graph reasoning.
- **D-04:** **URI shape matches Phase 42's D-04 lock:** `dependency:<ecosystem>/<name>` (e.g., `dependency:pypi/boto3`), `plugin:<name>` (e.g., `plugin:graph-wiki`). The URI builders added to `graph_io/uri.py` in Phase 42 (`dependency_uri`, `plugin_uri`) are now backed by real graph nodes.
- **D-05:** **New query helpers in `graph_io/queries.py`:**
  - `describe_dependency(conn, *, ecosystem: str, name: str) -> DependencyDescription | None`
  - `list_dependencies(conn) -> list[NodeRecord]`
  - `describe_plugin(conn, *, name: str) -> PluginDescription | None`
  - `list_plugins(conn) -> list[NodeRecord]`
  - Plus `DependencyDescription` and `PluginDescription` dataclasses paralleling existing `PackageDescription` shape.
- **D-06:** **`cg` CLI gets two new subcommands** in this phase (small ergonomic add): `cg describe dependency <name>` and `cg describe plugin <name>`. Mechanical — same pattern as existing `cg describe package`. Skip if it's the difference between Phase 43 fitting in one milestone slot or not; not load-bearing for entity writer.
- **D-07:** **`package_family` deferred to v1.9.** Phase 42's `package_family_uri` builder remains; the `entity-package-family.md` template remains; `package_family` is NOT in v1.8 `_VALID_KINDS`. STATE.md updated with this scope note.

### Wave 2 — write_entities semantics

- **D-08:** **Signature: `write_entities(conn: sqlite3.Connection, wiki_root: Path, admitted_kinds: frozenset[str]) -> EntityWriteResult`.** v1.8 callers pass `ADMITTED_KINDS_V18 = ADMITTED_KINDS - {"package_family"}`. The function does NOT call into pyproject parsing directly — that's already done by wave 1's graph ingestion, so `conn` is sufficient.
- **D-09:** **`EntityWriteResult` shape:** lists of URIs per state + per-page errors.
  ```python
  @dataclass(frozen=True)
  class EntityWriteError:
      uri: str
      slug: str
      exception: str  # repr of the caught exception

  @dataclass(frozen=True)
  class EntityWriteResult:
      created: list[str]          # URIs of newly-created pages
      updated: list[str]          # URIs of pages where frontmatter changed
      deleted: list[str]          # URIs hard-deleted this run
      unchanged: list[str]        # URIs where write-if-changed skipped the write
      needs_narrative: set[str]   # URIs entering the Phase 45 LLM fan-out
      errors: list[EntityWriteError]  # per-page failures (partial-success semantics)
  ```
  `errors` enables partial-success: one bad page doesn't abort the whole pass.

- **D-10:** **`needs_narrative` trigger conditions:**
  1. Page was just CREATED (no prior file existed on disk).
  2. Any value in the curated `STRUCTURAL_KEYS` subset changed compared to existing frontmatter.
  
  `STRUCTURAL_KEYS: frozenset[str]` is a new constant in `entity_writer.py`:
  ```python
  STRUCTURAL_KEYS = frozenset({
      "domains", "depends_on", "test_suites", "entry_points",
      "parent_domain", "sub_domains", "packages",
      "tested_packages", "members", "used_by",
  })
  ```
  
  Cosmetic keys (`last_scan_at`, `graph_name`, `file_count`, `language`, `version`, `suite_kind`, `ecosystem`, `versions_in_use`, `package_count`) do NOT trigger re-narration even though they're scanner-owned. STRUCTURAL_KEYS ⊂ SCANNER_OWNED_KEYS.

- **D-11:** **Change detection mechanic:** before writing each entity page, load the existing file (if any) via `python-frontmatter`, extract values for STRUCTURAL_KEYS, compute new values from graph queries, compare via Python equality on parsed YAML values. Collection comparisons: sort + dedupe both sides before comparing (so [foo, bar] == [bar, foo]). Adds one extra frontmatter parse per existing entity — negligible at vault scale (<200 pages).

- **D-12:** **Merge semantics for scanner-owned keys = full replacement.** When graph says `depends_on: [foo, baz]` and existing page says `depends_on: [foo, bar]`, the new value is `[foo, baz]` verbatim. No set-union, no human-add preservation for scanner-owned keys. The whitelist contract is the gate: scanner owns the key ⇒ scanner's view wins.

- **D-13:** **Non-scanner keys preserved verbatim and in original order.** When merging, parse existing frontmatter, retain every key not in SCANNER_OWNED_KEYS exactly as-is. Their relative position is preserved within the human-section of the file.

- **D-14:** **Deterministic frontmatter key ordering on write:**
  1. `uri` first (always present, required key)
  2. `kind` second
  3. Remaining SCANNER_OWNED_KEYS in alphabetical order (filtered to keys with non-empty values — empty lists / None are omitted to keep frontmatter compact)
  4. Non-whitelisted human keys in their original encountered order (preserved across merges)
  
  Collection values inside frontmatter are sorted lexically and deduped before write. The combination ensures byte-identical YAML across runs when graph state is unchanged.

- **D-15:** **Write-if-changed guard on every entity page.** For each page: render new content to a string buffer; if the file already exists and `existing_bytes == new_bytes`, count it as `unchanged` and SKIP the write. Pre-req: deterministic key ordering (D-14) makes the equality check reliable. Cost: one extra read per entity — negligible.

### Hard-delete + audit log

- **D-16:** **Unconditional hard-delete** when a graph node disappears (no body-content check). Justification: STATE.md locks hard-delete-with-log; PROJECT.md states vault is disposable. Recovery via `git log --follow` + `git show <sha>:<path>`. The deletions.log surfaces what was lost without forcing the user to scan history.

- **D-17:** **`deletions.log` = JSONL at `.graph-wiki/deletions.log`.** Schema (one JSON object per line, append-only):
  ```json
  {"timestamp": "2026-05-27T03:14:21Z", "uri": "pkg:agent-research/foo", "slug": "pkg__agent-research__foo", "path": "wiki/entities/pkg__agent-research__foo.md", "kind": "package", "body_was_empty": true}
  ```
  `body_was_empty` is true when the page body (after stripping the H1 + `## Narrative` placeholder template default) had no human-authored content. Surfaces the destructive cases in audits without preventing delete. Timestamp is ISO-8601 UTC.

- **D-18:** **Rotation policy:** when `.graph-wiki/deletions.log` reaches 10 MB, rename to `deletions.log.1` (overwriting any prior `.log.1`) and start fresh. Two-file scheme; no further rotation. Implementation lives inside `write_entities` (or a small helper) — checks file size before write, rotates if needed. ~10 LOC.

### Concurrency + atomicity

- **D-19:** **`scan.lock` via `fcntl.flock` with `LOCK_EX | LOCK_NB`.** Path: `.graph-wiki/scan.lock`. Acquire as the FIRST action of `write_entities`; release in a try/finally including exception paths. On contention: raise `WriteLockHeldError("another scan in progress for this workspace: <path>")`. POSIX-only (macOS + Linux); Windows is not supported by the rest of the stack so this is fine. ~15 LOC, stdlib only.

- **D-20:** **Lock granularity = whole `write_entities` call.** Not per-page. The pass is short (deterministic, no LLM in this phase). Per-page locking would only be needed if multiple scanners ran in interleaved-write mode, which isn't a v1.8 workload.

- **D-21:** **Partial-failure isolation:** if one page write fails (frontmatter parse error on an existing page, disk error, etc.), catch the exception, append to `EntityWriteResult.errors`, and continue with the rest. The lock is held throughout — failed pages don't release it early. Final return is partial-success if `errors` is non-empty; scanner caller decides how to surface it.

### Module structure

- **D-22:** **All wave-2 code lives in `packages/wiki-io/src/wiki_io/entity_writer.py`** alongside Phase 42's constants and slug helpers. New additions to the module:
  - `STRUCTURAL_KEYS: frozenset[str]`
  - `class EntityWriteError`, `class EntityWriteResult`
  - `class WriteLockHeldError(Exception)`
  - `def merge_frontmatter(existing: dict, scanner_update: dict) -> dict`
  - `def _render_entity_page(template_path: Path, frontmatter: dict) -> str`
  - `def _detect_structural_change(existing_fm: dict, new_fm: dict) -> bool`
  - `def _rotate_deletions_log(path: Path, max_bytes: int = 10_000_000) -> None`
  - `def _append_deletion(log_path: Path, record: dict) -> None`
  - `@contextmanager def _acquire_scan_lock(workspace_root: Path)` (using fcntl.flock)
  - `def write_entities(conn, wiki_root, admitted_kinds) -> EntityWriteResult`
- **D-23:** **No new wiki-io dependencies.** python-frontmatter, fcntl (stdlib), json (stdlib), pathlib (stdlib) cover everything.

### Folded Todos

- **`2026-05-26-fix-scanner-treats-import-root-as-subpackage.md` (score 0.6) — FOLDED into Wave 1 work.** This is a graph-io scanner bug that emits spurious subpackage nodes for package import roots. Wave 1 is doing surgical work in `graph_io/structural_nodes.py` anyway (the file the todo's fix targets) to add dependency/plugin ingestion. Folding the fix in: (a) batches the test-snapshot re-baselining; (b) prevents the bug from producing extraneous subpackage URIs that downstream phases would have to filter out. Wave 1 acceptance criterion adds: "subpackage nodes only emit for directories BELOW the import root."

### Claude's Discretion

- Exact dataclass field types (list vs tuple vs frozenset for collections inside EntityWriteResult — implementer's call within Python conventions).
- Whether `EntityWriteError.exception` stores the full traceback or `repr()`. Lean toward repr for log compactness; tests assert specific exception types not traceback strings.
- Whether `_acquire_scan_lock` is exposed publicly (probably yes, for testing with mock workspaces).
- Whether `cg describe dependency` / `cg describe plugin` ship in Phase 43 or slip to a follow-up (D-06).
- Exact YAML emitter config for deterministic ordering (custom Dumper class vs sort_keys + post-processing).
- File mode for writes (`0o644` is the v1.7 convention; preserved).

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Phase 42 outputs (Phase 43's direct predecessors)
- `.planning/phases/42-uri-slug-scheme-per-kind-templates/42-CONTEXT.md` — All 18 design-lock decisions. SCANNER_OWNED_KEYS shape, slug encoding, template format, ADMITTED_KINDS values
- `packages/wiki-io/src/wiki_io/entity_writer.py` (created in Phase 42) — Constants + slug helpers; Phase 43 extends this module
- `packages/wiki-io/src/wiki_io/assets/page-templates/entity-*.md` (7 templates from Phase 42) — Template source for `_render_entity_page`; entity-package-family.md is created but dormant in v1.8
- `packages/graph-io/src/graph_io/uri.py` — Existing + Phase-42-added URI builders; `dependency_uri` and `plugin_uri` now back real graph nodes

### Milestone-level
- `.planning/REQUIREMENTS.md` §ENTITY — ENTITY-01..ENTITY-05 (Phase 43's five requirements). ENTITY-04 specifies `EntityWriteResult` shape; ENTITY-05 specifies scan.lock
- `.planning/ROADMAP.md` Phase 43 — Goal + 5 success criteria (write_entities behavior, merge test, deletion log, EntityWriteResult, scan.lock)
- `.planning/STATE.md` — Hard-delete-with-log policy, active pitfall guards (Pitfalls 2/3/9 are Phase 43's domain)

### Research baseline
- `.planning/research/ARCHITECTURE.md` §New Files Map (`entity_writer.py`), §Modified Files Map, §Anti-Patterns 1/2/4 — confirms graph_io.queries is the source for graph-backed kinds
- `.planning/research/PITFALLS.md` Pitfall 2 (frontmatter key collision — addressed by D-12..D-15), Pitfall 3 (hard-delete losing edits — addressed by D-16 + D-17), Pitfall 9 (concurrent scan race — addressed by D-19..D-21)
- `.planning/research/FEATURES.md` §F4 (scanner relation frontmatter), §F6 (hard-delete reconciliation)

### Existing code (must be read by planner/researcher)
- `packages/graph-io/src/graph_io/queries.py` §`_VALID_KINDS`, §`describe_package`, §`describe_test_suite`, §`describe_domain`, §`list_packages`, §`list_domains` — query patterns for wave-1 additions (`describe_dependency`, `list_dependencies`, `describe_plugin`, `list_plugins`)
- `packages/graph-io/src/graph_io/packages.py` — workspace member discovery + pyproject.toml parsing (already exists; wave-1 dependency ingestion plugs in here)
- `packages/graph-io/src/graph_io/structural_nodes.py` — node emission; wave-1 adds `_emit_dependency_nodes` + `_emit_plugin_nodes` helpers; ALSO folds the import-root subpackage bug fix
- `packages/workspace-io/src/workspace_io/manifest.py` (or equivalent) — `.graph-wiki.yaml` `plugins[]` parser used by wave-1 plugin ingestion
- `packages/wiki-io/src/wiki_io/append_log.py` — Reference pattern for log writes (entity deletions log is JSONL, NOT this format — but the path/conventions are similar)
- `packages/wiki-io/src/wiki_io/update_tokens.py` — Reference for python-frontmatter round-trip patterns (`frontmatter.loads`, `frontmatter.dumps`)

### Todos folded into this phase
- `.planning/todos/pending/2026-05-26-fix-scanner-treats-import-root-as-subpackage.md` — Bug fix folded into Wave 1; will be moved to `.planning/todos/resolved/` after Phase 43 execution

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- **`graph_io.queries.describe_package`:** Template for `describe_dependency` / `describe_plugin`. Returns a `PackageDescription` dataclass; wave 1 creates parallel `DependencyDescription` / `PluginDescription` shapes.
- **`graph_io.packages` (workspace member discovery):** Already walks the monorepo, parses pyproject.toml, extracts dependencies into a structured form. Wave 1's dependency ingestion calls existing helpers and emits new edges; no fresh parser needed.
- **`workspace_io` manifest parser:** Reads `.graph-wiki.yaml`. The `plugins[]` array is already accessible; wave 1 calls this then emits `plugin` nodes — no new YAML reading.
- **`python-frontmatter`:** Already a wiki-io dependency (per CLAUDE.md §7 and `update_tokens.py` import). Used for round-trip frontmatter parse + dump.
- **`fcntl`:** stdlib. No new dep for scan.lock.

### Established Patterns
- **CLAUDE.md §2 — Direct `langchain_aws` usage; no agent framework.** Not relevant to Phase 43 (no LLM in this phase) but worth noting that wave-2 has zero LLM dependencies.
- **CLAUDE.md §8 — pytest + pytest-asyncio + syrupy.** Phase 43 tests are sync (write_entities is sync; the LLM fan-out in Phase 45 is async). Hypothesis (added in Phase 42) is reused for new graph-io property tests on the merge function.
- **`_VALID_KINDS` is a frozenset, validated in `list_packages` and similar functions** (queries.py:184–189). Wave 1 extends this and adds matching error-path tests.
- **v1.7 trace JSONL convention** (per `.planning/intel/arch.md` §Conventions): one JSON object per line, schema_version, ISO timestamps. `deletions.log` mirrors this (D-17).

### Integration Points
- **`packages.py` ingestion is the wave-1 plug-in point** for dependency nodes. No `scan.py` changes needed in Phase 43 — that's Phase 45.
- **`structural_nodes.py::_emit_subpackages`** (or its equivalent) is where the folded subpackage bug fix lands. The import-root-as-subpackage issue is fixed before Phase 43's graph fixtures are re-baselined for the new kinds.
- **`workspace_io` plugin parser** is the wave-1 plug-in point for plugin nodes.
- **`wiki/entities/` directory** (created in Phase 42 via init_vault.py) is the write target. `write_entities` is the only code that writes there.
- **No scanner integration in Phase 43** — write_entities is testable in isolation against a fixture graph. Phase 45 wires it into `run_scan`.

</code_context>

<specifics>
## Specific Ideas

- **Wave 1 / wave 2 can run in PARALLEL if wave 2 mocks the graph queries.** Planner should consider creating two task chains: (1) graph-io extension end-to-end with its own tests; (2) entity_writer code against a `MockGraphConn` fixture that returns canned graph responses. They unify at integration-test time (e.g., a wave-2 test that runs against a real wave-1-ingested fixture).
- **Hypothesis property tests for merge_frontmatter:** generate random (existing_fm, scanner_update) pairs, assert (a) every key not in SCANNER_OWNED_KEYS is preserved verbatim, (b) every key in SCANNER_OWNED_KEYS takes scanner's value, (c) ordering rules in D-14 hold.
- **Integration test on `agent-research` itself:** the v1.7 graph already exists. Wave 1 ingestion runs against it; entity pages are written into a temp wiki; assert that every workspace member has a `pkg__agent-research__<name>.md` entity page, every dep (boto3, langchain-aws, etc.) has a `dependency__pypi__<name>.md` entity page, and the plugin from `.graph-wiki.yaml` has a `plugin__graph-wiki.md` page.
- **Merge test from ROADMAP success criterion #2:** write a page with `status: deprecated`, run `write_entities`, assert `status: deprecated` is preserved. This is the explicit Pitfall-2 guard.
- **Concurrent-scan test from ROADMAP success criterion #5:** spawn a second `write_entities` while one is holding the lock; assert second one raises `WriteLockHeldError` immediately (no wait).
- **Deletion test from ROADMAP success criterion #3:** create a fixture graph + entity page; remove the node from the graph; re-run write_entities; assert the page is gone AND `.graph-wiki/deletions.log` has a record with the correct URI, slug, path, kind, timestamp.

</specifics>

<deferred>
## Deferred Ideas

- **`cg describe dependency` / `cg describe plugin` CLI subcommands (D-06)** — listed as Claude's discretion; if Phase 43 scope is already tight, defer to a follow-up small phase or roll into Phase 44/45.
- **`package_family` kind, ingestion, and entity pages** — v1.9. Phase 42's template + URI builder stay dormant. Curation source TBD (curated families.yaml? imports-derived?).
- **Cross-repo dependency deduplication** — v1.9. v1.8 has one repo (`agent-research`); ecosystem-namespaced URIs already prevent collision across future repos.
- **Plugin transitive dependencies / plugin-as-graph-edge to consumer packages** — v1.9. v1.8 plugins are doc-only.
- **`status: stale` for non-entity wiki pages (curated lanes)** — Phase 45 retains existing stale-tag behavior for non-entity pages. Phase 43 only touches entity pages.
- **Frontmatter-comment-preservation across merges** — python-frontmatter loses inline YAML comments on round-trip. Acceptable trade-off in v1.8 (no human comments expected on scanner-owned keys); revisit if it becomes a problem.
- **Lock-file recovery on stale-lock conditions** — fcntl.flock releases the file lock automatically when the process exits, so stale locks shouldn't happen. If they do (e.g., kernel bug), the user `rm`s `.graph-wiki/scan.lock` manually. Document in the error message.
- **Per-kind whitelist enforcement at runtime** — Phase 42 D-09 left this as a Phase 43 option; not adopted in this CONTEXT — Phase 43 uses the flat whitelist + structural-key subset for narrative trigger only. A kind-restricted whitelist would add complexity without preventing any real bug.

### Reviewed Todos (not folded)

(None remaining — the one candidate was folded into Wave 1, see Decisions section.)

</deferred>

---

*Phase: 43-Entity Writer*
*Context gathered: 2026-05-26*
