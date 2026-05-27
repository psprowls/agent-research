---
phase: 45
phase_slug: scanner-integration
researched: 2026-05-27
status: complete
---

# Phase 45 Research — Scanner Integration

> Grounded in code that exists today (Phases 42 + 43 landed; Phase 44 is planned, executor not yet run). Where Phase 45 depends on Phase 44 surfaces (`wiki_io.index_generator.generate_index`), the contract from `.planning/phases/44-scanner-generated-index/44-CONTEXT.md` is treated as authoritative — Phase 44's executor will deliver that surface in parallel with Phase 45 plan execution.

## RESEARCH COMPLETE

## 1. Code surface that Phase 45 must modify

### 1.1 `agents/graph-wiki-agent/src/graph_wiki_agent/commands/scan.py` (671 LOC)

Single-file location for Steps 1–13 of `run_scan`. Key entry points:

- `ScanResult` (lines 178–195) — current dataclass: `added/updated/deleted/renamed/errors/state_gate`. All string lists are workspace-name keyed. Must gain Phase 45 URI-keyed fields per D-15.
- `build_stub_prompt(pkg, no_file_map, repo_root)` (lines 203–257) — template for the new `build_entity_narrative_prompt`. Returns plain string; uses workspace dict shape. NOT modified by Phase 45 (still used for any non-entity scanner calls — none in v1.8, but the helper stays).
- `_add_stale_tag(page_path)` (lines 265–295) — idempotent stale-tag inject. Used in Step 11. Stays unchanged per D-09.
- `run_scan(workspace_path, no_file_map, max_depth, repo_path, model_override)` (lines 303–671) — the wiring target.

Steps inside `run_scan` that change in Phase 45:
- **Step 5** (line 514): `existing = _load_existing_pages(wiki)` — return shape becomes `ExistingPages` dataclass (D-11).
- **Step 7** (line 520): `diff = compute_diff(workspaces, existing)` — `compute_diff` continues operating on `existing.legacy` only (D-12).
- **Step 9** (lines 530–570): currently a single scanner fan-out. Becomes:
  - **Step 9a** — `conn`-driven call to `write_entities(conn, wiki, ADMITTED_KINDS_V18)`. Conn is already open at line 433 and closed in `finally` at line 669. No new lifecycle needed.
  - **Step 9b** — narrator fan-out via `SubagentPool.run_all` only for URIs in `result.needs_narrative`. New prompt builder + new `narrator` role.
- **Step 10** (lines 572–602): the legacy `for pkg, llm_body in fan_result.successes` loop that writes `wiki / vault_page_rel = packages/<name>/<name>.md` is **removed** (D-08, hard cutover). Step 10 becomes: iterate narrator successes and call `entity_writer.inject_narrative(page_path, prose)` for each. Errors from narrator failures land in `entity_errors` (partial-success per D-21 of Phase 43).
- **Step 11** (lines 604–636): existing stale-tag loop preserved (D-09). It naturally no-ops in v1.8 because `diff["deleted"]` only contains non-entity legacy-layout names.
- **Step 12** (lines 638–643): currently `regenerate_dependencies_index(wiki, workspaces)` + `update_index(wiki)`. Phase 45 adds `index_generator.generate_index(conn, wiki)` BEFORE the `update_index(wiki)` call. Order per D-01: `generate_index` first; `update_index` second. Both inside the `try: conn` block while conn is still open. `update_index`'s `wiki/index.md` write is removed in this phase (see §1.4).

### 1.2 `packages/wiki-io/src/wiki_io/entity_writer.py` (607 LOC)

Phase 43 surface already in place. Phase 45 adds ONE helper:

- `inject_narrative(page_path: Path, prose: str) -> None` (D-07). Reads the entity page; locates the `## Narrative` H2; replaces body up to the next H2 (or EOF) with `prose`; writes back atomically. Idempotent — subsequent calls overwrite prior narrative.

Implementation notes from existing code:
- Templates ship a `## Narrative` heading per Phase 42 D-16. Verified in `packages/wiki-io/src/wiki_io/assets/page-templates/entity-*.md` (Phase 42 scaffold).
- Atomic write pattern: `tmp = page_path.with_suffix('.md.tmp'); tmp.write_text(new); os.replace(tmp, page_path)` (consistent with Phase 44 D-16).
- Read raw bytes / split on the H2 marker rather than going through `python-frontmatter` (lean: raw bytes — frontmatter is preserved verbatim since we only touch the body). Per CONTEXT.md Claude's-Discretion note.
- Edge cases:
  - Page missing `## Narrative` heading → log warning, no write (defensive — should never happen on entity-template pages).
  - Multiple `## Narrative` headings → replace the first; subsequent ones are user-authored and untouched (defensive — should never happen).
  - Prose contains a literal `## ` line at column 0 → caller's responsibility (narrator prompt forbids it).
  - Empty prose ("") → write an empty body section, no error.

### 1.3 `packages/wiki-io/src/wiki_io/scan_monorepo.py` — `_load_existing_pages` (line 829)

Current return: `dict[str, dict]` keyed by workspace name (`pages[name] = {wiki_relative_path, package_path, category, last_sync_commit}`). Walks `wiki/apps/`, `wiki/packages/`, layout-pinned containers, `wiki/domains/<domain>/packages/`.

Phase 45 extension (D-11): return a `ExistingPages` dataclass with two sub-dicts:
```python
@dataclass(frozen=True)
class ExistingPages:
    legacy: dict[str, dict]   # workspace-name → existing shape (UNCHANGED)
    entities: dict[str, dict] # URI → {path: Path, frontmatter: dict}
```

Implementation notes:
- Add a new `_collect_entities(wiki)` helper that walks `wiki/entities/*.md`, parses frontmatter, extracts `uri`, builds `entities[uri] = {path, frontmatter}`.
- Skip `wiki/entities/_index.md` (consistent with `entity_writer.write_entities` deletion sweep at line 569).
- Use `frontmatter.load(page_path)` (the project already depends on `python-frontmatter`).
- If `uri` is missing in frontmatter (corrupt page) → skip that page, no error.
- All existing callers of `_load_existing_pages` need to update:
  - `commands/scan.py::run_scan` line 514 — uses `existing` everywhere; rewrite to `existing.legacy` for legacy uses.
  - `commands/scan.py::run_scan` line 606 — `existing.get(pkg_name)` in stale-tag loop → `existing.legacy.get(pkg_name)`.
  - `commands/scan.py::run_scan` line 623 — `existing.get(old_name)` → `existing.legacy.get(old_name)`.
  - `scan_monorepo.py::main()` line 1397 — uses `existing` as input to `attach_changed_files` and `compute_diff`. Rewrite to `existing.legacy`.
  - `scan_monorepo.py::attach_changed_files(workspaces, existing, repo)` line 972 — change signature to accept `dict` (the `.legacy` view passed in).

The cleanest change: keep `_load_existing_pages` returning the dataclass, and `compute_diff` + `attach_changed_files` continue to accept a plain dict. Callers pass `existing.legacy` to those two functions. Three call sites updated total (the two in `scan.py` + the one in `scan_monorepo.py::main`).

### 1.4 `packages/wiki-io/src/wiki_io/update_index.py` — surgical change (D-02)

Phase 45 removes the `wiki/index.md` write inside `update_index(wiki)`. Specifically:
- Library entry point `update_index(wiki)` (line 289): delete lines 300–302 (the `content = render_index(...); index_path.write_text(...)` block). The `render_index` call can stay only if needed elsewhere; the simplest change is to delete those three lines outright.
- CLI entry point `main()` (line 321): same surgery — delete lines 335 (the `render_index` call), 362–370 (the `index_path.write_text` block and its error handler).
- The category sub-index logic (lines 303–318 in library + lines 372–411 in CLI) is preserved exactly.
- `render_index()` and `infer_title()` become unused. Remove `render_index()` and the `MAIN_INDEX_CATEGORIES` constant if a quick `grep -r render_index` confirms no other callers. (One-line check via `rg "render_index" agents packages plugins`.)

Lean per CONTEXT.md Claude's-Discretion: drop the `wiki/index.md` block unconditionally rather than gating with a parameter. Keeps `update_index.py` purely a sub-index writer.

### 1.5 `packages/model-adapter/src/model_adapter/models.toml` — new `narrator` role

Add a new `[roles.narrator]` section after `[roles.scanner]`. Initial config per D-06: same model as `scanner` for v1.8.

```toml
[roles.narrator]
# Phase 45 D-06: prose-only narrative generation for entity pages.
# Initial config: same as scanner for v1.8; eval-driven refinement is v1.9.
model_id        = "us.anthropic.claude-haiku-4-5-20251001-v1:0"
region          = "us-east-1"
max_tokens      = 600   # narratives are short (~3-5 paragraphs); cap conservatively
max_concurrency = 10
```

`max_tokens` is set lower than scanner (500 → 600 here) because narrator emits ONLY prose. Scanner emits full page markdown (frontmatter + headings + body), so its 500-token budget is tight. Narrator's 600-token budget is generous for prose-only output.

Both `make_llm("narrator")` (the runtime call) and `load_role_config("narrator")` (used by scan.py to read `max_concurrency`) read from this single source.

NOTE: There is a STUB `models.toml` at `packages/model-adapter/models.toml` that explicitly says "this file is not loaded in production. Edit packages/model-adapter/src/model_adapter/models.toml." Phase 45 edits ONLY the in-package file.

### 1.6 `.planning/REQUIREMENTS.md` — SCANINT-04 rewrite

Current SCANINT-04 (line 44):
> Step 12 calls `index_generator.generate_index` for the entity portion of the index; curated-lane index sections continue to flow through existing `update_index.py` path

New SCANINT-04 per D-03:
> Step 12 calls `index_generator.generate_index` to produce `wiki/index.md` (graph-entity sections + full curated-lane listings, per Phase 44 D-02/D-11/D-12) AND `update_index.update_index(wiki)` to produce per-folder `*/index.md` sub-indexes only. The `update_index` module's prior `wiki/index.md` write is removed.

## 2. Dependencies on Phase 44 (delivered in parallel)

Phase 45 must import and call `wiki_io.index_generator.generate_index(conn, wiki_root) -> IndexWriteResult`. That module does NOT yet exist on disk at planning time. Per Phase 44 D-18, the contract is:

```python
@dataclass(frozen=True)
class IndexWriteResult:
    path: Path
    bytes_written: int    # 0 if unchanged
    changed: bool         # True if write occurred
    entity_count: int
    curated_count: int
    domain_count: int
    by_kind_count: int
```

Phase 45 only NEEDS the `path` field for any post-call logging. Anything else is optional. Plan 03 should:
- Import `wiki_io.index_generator` at module top (will fail with ImportError until Phase 44 lands — that's expected and is the integration signal).
- Use `result = index_generator.generate_index(conn, wiki)` in Step 12. Do not destructure fields beyond `path` and `changed` (small surface = less coupling).
- Optionally log `result.changed` and `result.bytes_written` if Phase 44 lands them.

If Phase 44 hasn't landed by the time Phase 45 execution starts, Plan 03 will produce an executable scaffold that imports a missing module — Phase 44 unblocks it.

## 3. Plugin smoke test contract (SCANINT-06)

The "plugin smoke test" is `packages/wiki-io/tests/test_scan_monorepo.py`, which exercises `wiki_io.scan_monorepo` directly. The plugin (`plugins/graph-wiki/skills/graph-wiki/scripts/scan_monorepo.py`) is a shim that dispatches to `wiki_io.scan_monorepo.main()` in the "claude" backend.

Critical: `wiki_io.scan_monorepo.main()` does NOT call `update_index()` directly (verified via grep — only `regenerate_dependencies_index` runs at line 1408). So Phase 45's surgical `update_index.py` change does NOT affect the plugin smoke path.

The two coupling points to verify after the changes land:
1. `scan_monorepo.main()` line 1397 still produces a working `existing` value. With the dataclass return shape, the line becomes `existing = _load_existing_pages(wiki).legacy if wiki.exists() else {}`.
2. `attach_changed_files(workspaces, existing, repo)` line 1399 — pass `.legacy` directly.

Both updates are local and add up to one-line changes; the smoke test exercises the public behavior of `main()` and should pass as-is once those two call sites are updated.

## 4. Narrator prompt design (`build_entity_narrative_prompt`)

Spec from CONTEXT.md D-05: prose only (no frontmatter, no H1). System prompt explicitly bans frontmatter.

Sketched shape (≈80–120 LOC, mirroring `build_stub_prompt`):

```python
def build_entity_narrative_prompt(
    entity_node,            # the graph NodeRecord
    kind: str,              # "package" | "domain" | ...
    file_map_text: str,     # "" for non-package kinds
    relations: dict,        # {depends_on, test_suites, ...} from scanner_frontmatter
) -> tuple[str, str]:
    """Return (system_message, human_message) for the narrator LLM."""
    system = (
        "You write the narrative body of a graph-derived wiki entity page. "
        "Output ONLY prose: no YAML frontmatter, no H1, no H2 headings, no fenced code blocks "
        "unless the prose specifically describes code. Your output will be injected between "
        "the page's `## Narrative` heading and the next H2 — write only what belongs there.\n\n"
        "Tone: factual, concise, technical. Length: 2-4 short paragraphs. Cite the entity's "
        "relations naturally (e.g. 'It depends on `pkg:foo`...'); do not enumerate them in a list."
    )
    lines = [
        f"Entity URI: {entity_node.uri}",
        f"Kind: {kind}",
        f"Name: {entity_node.name}",
    ]
    if relations.get("depends_on"):
        lines.append(f"Depends on: {', '.join(relations['depends_on'])}")
    if relations.get("test_suites"):
        lines.append(f"Test suites: {', '.join(relations['test_suites'])}")
    # ... similar for domains, parent_domain, packages, used_by, members, etc.
    if file_map_text:
        lines.append("")
        lines.append("File listing (for reference; do NOT include this in your output):")
        lines.append(file_map_text[:1500])
    lines.append("")
    lines.append("Write the narrative body for this page (prose only).")
    return system, "\n".join(lines)
```

Per CONTEXT.md Claude's-Discretion: prompt wording is not load-bearing for v1.8 — needs viable v1, refinement is v1.9.

The narrator fan-out callback in `scan.py` follows the existing `generate_stub` pattern (lines 553–562):

```python
async def generate_narrative(uri_to_node_kind: tuple[str, Any, str]) -> TaskResult:
    uri, node, kind = uri_to_node_kind
    relations = _scanner_frontmatter_for_node(conn, kind, node)  # reuse existing helper
    file_map = ws_by_name.get(node.name, {}).get("file_map", "") if kind == "package" else ""
    system, human = build_entity_narrative_prompt(node, kind, file_map, relations)
    msgs = [SystemMessage(content=system), HumanMessage(content=human)]
    resp = await narrator_llm.ainvoke(msgs)
    return TaskResult(value=resp.content, response=resp)
```

A subtle point: `_scanner_frontmatter_for_node` is currently a private helper in `entity_writer.py`. Phase 45 needs it from `scan.py`. Options:
- (a) Re-export from `entity_writer.__all__` or remove the leading underscore. Cleanest.
- (b) Inline a local "build relations dict" in `scan.py`. Duplicate logic — avoid.
- (c) Re-query the graph from `scan.py` (`describe_package(conn, name=...)` etc.). Adds an extra round-trip per narrator call — avoid.

**Lean: option (a)** — rename `_scanner_frontmatter_for_node` → `scanner_frontmatter_for_node` in `entity_writer.py`, update its three internal callers, and import it from `scan.py`. One mechanical rename. Plan 01 covers this rename.

## 5. Step 9b URI → node lookup

`write_entities` returns `EntityWriteResult.needs_narrative: set[str]` (URIs only). Step 9b needs to translate URIs back into graph NodeRecords plus kind to drive the narrator prompt.

Two approaches:
- (a) Re-list every kind via `_kind_list_fns()` and filter to needs_narrative URIs. One round trip per kind, ~5 round trips. Simple, no new query.
- (b) Add `EntityWriteResult.needs_narrative_nodes: list[tuple[uri, kind, node]]` to Phase 43. Touches Phase 43's contract — out of scope for Phase 45.

**Lean: option (a)** — Step 9b iterates kinds (using the same `_kind_list_fns` helper, imported from `entity_writer`), filters each kind's nodes by `uri in result.needs_narrative`, accumulates a list of `(uri, kind, node)` tuples. ~10 lines in `scan.py`. No Phase 43 contract churn.

## 6. ScanResult shape (D-15)

Adds 5 new URI-keyed fields alongside the legacy name-keyed ones. Final shape:

```python
@dataclass
class ScanResult:
    added: list[str] = field(default_factory=list)          # legacy names
    updated: list[str] = field(default_factory=list)
    deleted: list[str] = field(default_factory=list)
    renamed: list[list[str]] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)
    state_gate: dict = field(default_factory=dict)
    # New in Phase 45:
    entities_created: list[str] = field(default_factory=list)     # URIs
    entities_updated: list[str] = field(default_factory=list)
    entities_deleted: list[str] = field(default_factory=list)
    entities_narrated: list[str] = field(default_factory=list)
    entity_errors: list[str] = field(default_factory=list)
```

Populate from `EntityWriteResult` and from the narrator `FanOutResult`:
- `entities_created = sorted(write_result.created)`
- `entities_updated = sorted(write_result.updated)`
- `entities_deleted = sorted(write_result.deleted)`
- `entities_narrated = sorted(uri for uri, prose in narrator_result.successes)` (after `inject_narrative` succeeds)
- `entity_errors = [repr(e) for e in write_result.errors] + [f'{narrator_uri}: {err.exception}' for err in narrator_result.errors]`

Test surface: snapshot the dataclass shape (syrupy or simple equality) to lock the contract for downstream consumers.

## 7. CLI summary line (D-16, Claude's discretion)

Step 13 currently emits:
```
scan complete: +{n_added} ~{n_updated} -{n_deleted}
```

Phase 45 emits two parallel counters:
```
scan complete: legacy +{n_added} ~{n_updated} -{n_deleted}  |  entities +{n_ec} ~{n_eu} -{n_ed}  (narrated: {n_n} of {n_needs_narrative})
```

Where `n_needs_narrative = len(write_result.needs_narrative)` and `n_n = len(entities_narrated)`. Logs via the existing `append_log` mechanism.

## 8. Validation Architecture (Nyquist)

### Dimension 1 — Specification-level test coverage

| Decision | Test |
|---|---|
| D-01 (Step 12 dual-call order) | `test_scan_step_12_calls_generate_then_update`: mock both functions; assert call order |
| D-02 (`update_index.py` surgical) | `test_update_index_no_longer_writes_wiki_index_md`: existing wiki/index.md is untouched after `update_index(wiki)` |
| D-04 (Step 9 split) | `test_run_scan_calls_write_entities_first`: mock `write_entities` + scanner pool; assert `write_entities` called once before any narrator dispatch |
| D-05/D-07 (narrator prompt + inject) | `test_inject_narrative_replaces_body_only`: page with non-Narrative H2 sections, frontmatter, and a Narrative section — assert only the Narrative section body changes |
| D-08 (legacy write removed) | `test_run_scan_writes_no_packages_pages`: end-to-end fixture; assert no `wiki/packages/<name>/<name>.md` files created in a fresh vault |
| D-11 (`ExistingPages` dataclass) | `test_load_existing_pages_returns_dataclass`: assert return type + sub-dict keys + URI-keyed entries for `wiki/entities/*.md` |
| D-12 (`compute_diff` legacy-only) | `test_compute_diff_ignores_entity_pages`: fixture with both layouts; assert `compute_diff` output names only the legacy pages |
| D-15 (ScanResult shape) | `test_scan_result_includes_entity_fields`: snapshot the dataclass via syrupy |
| D-17 (lock inheritance) | (covered by Phase 43 lock tests — no new test) |
| Plugin smoke (SCANINT-06) | run `pytest packages/wiki-io/tests/test_scan_monorepo.py` AFTER all changes — must pass unmodified |

### Dimension 2 — End-to-end integration

- `test_scan_integration_creates_entity_pages` — build fixture sqlite graph with 3 packages + 1 domain; run `run_scan`; assert `wiki/entities/pkg__*.md` and `wiki/entities/domain__*.md` exist; assert each has injected narrative content (not the unmodified template body).
- `test_scan_integration_narrator_gates_on_unchanged` — run scan twice against same graph; assert second run's `entities_narrated` is empty (no needs_narrative URIs).
- `test_scan_integration_two_writer_index_path` — verify `wiki/index.md` exists (from `generate_index`) AND `wiki/concepts/index.md` exists (from `update_index`).
- `test_plugin_smoke_legacy_layout_unchanged` — run `wiki_io.scan_monorepo.main()` against a legacy fixture vault; assert legacy `packages/<name>/<name>.md` is produced and no entity-page directory is touched.

### Dimension 3 — Concurrency

- Phase 43's `WriteLockHeldError` test covers concurrent-scan abort. Phase 45 inherits unchanged. No new test.

### Dimension 4 — Failure modes

- `test_narrator_failure_isolates_to_entity_errors` — mock narrator to raise for one URI; assert other URIs are narrated; assert `ScanResult.entity_errors` includes the failed URI.
- `test_inject_narrative_missing_narrative_heading` — fixture page without `## Narrative`; assert no write and a warning log.
- `test_write_entities_failure_aborts_step_9b` — if `write_entities` raises (lock contention), assert Step 9b is never reached; `ScanResult.errors` carries the cause.

### Dimension 5 — Determinism

- `inject_narrative` against the same page+prose pair twice → identical bytes both times (idempotent).
- `ScanResult.entities_*` lists are sorted (matches `EntityWriteResult` convention).

## 9. Pitfalls and edge cases (PITFALLS targets)

1. **Conn lifecycle.** `conn` opens at line 433 inside the `try:` and closes in `finally` at line 669. Phase 45's Step 9a/12 calls must stay inside the `try` so they have a valid conn. Plan 03 must NOT reorder these blocks outside the `try`.

2. **Lock surface.** `write_entities` acquires the lock internally (D-17). `generate_index` is lock-agnostic (Phase 44 D-20). `update_index` does not need the lock either (it's a pure file writer). The lock release happens BEFORE Step 9b (narrator fan-out), which is correct — narrator does not touch the entity pages directly; only `inject_narrative` does, and that's after the LLM call returns. If we wanted to lock-protect `inject_narrative`, we'd need to re-acquire the lock; Phase 45 explicitly defers that complexity (CONTEXT.md does not require it).

3. **`needs_narrative` empty set.** If no URIs need narration (e.g., second scan with no changes), the narrator pool must be skipped. Plan 03 guard: `if not narrator_items: skip pool.run_all`. The pool would otherwise do an empty `gather` — harmless but a `pool.run_all([], ...)` would still allocate a trace file and a semaphore. Skip explicitly.

4. **Conn passed to `_scanner_frontmatter_for_node`.** Helper takes `conn` as first arg. Step 9b's callback closure must capture `conn` from the enclosing scope. Standard Python closure; no issue.

5. **`narrator` role missing from models.toml.** `make_llm("narrator")` raises `KeyError` at runtime. Plan 01 adds the role; Plan 03 calls `make_llm`. The two plans must merge before any scan runs against the new code.

6. **`existing.legacy` rename.** Three callers of `_load_existing_pages` exist in production code paths; missing one breaks the scan. Plan 02 must enumerate all callers and update them in the same commit as the return-type change.

7. **Plugin smoke test path independence.** The plugin's scan does NOT call `update_index`, so the surgical change is safe for SCANINT-06. Plan 03 must run the plugin smoke test as a post-change verification (CI gate).

8. **Phase 44 `generate_index` not yet on disk.** Plan 03 will produce code that imports `wiki_io.index_generator`, which fails until Phase 44 lands. This is the intended integration signal — the scan code is "ready" the moment Phase 44 lands the module.

## Validation Architecture

(Per gsd-plan-phase's Nyquist gate — this section triggers VALIDATION.md generation.)

The Phase 45 test pyramid:
- Unit tests for `inject_narrative` (atomic write, marker detection, idempotency).
- Unit tests for `ExistingPages` + extended `_load_existing_pages` (URI keying, missing-uri skip).
- Unit tests for `build_entity_narrative_prompt` (no frontmatter, no H1 — assert on output string content).
- Unit tests for `ScanResult` shape (snapshot).
- Integration tests for `run_scan` end-to-end against a fixture sqlite graph (entity pages, dual-writer index, narrator gating, narrator failure isolation).
- Regression test: `pytest packages/wiki-io/tests/test_scan_monorepo.py` must pass unchanged (SCANINT-06).
- Determinism: `inject_narrative` idempotency snapshot.
