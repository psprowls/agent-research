# Phase 43: Entity Writer - Research

**Researched:** 2026-05-26
**Domain:** Python module design + SQLite graph queries + filesystem reconciliation + POSIX advisory locks + property-based testing
**Confidence:** HIGH

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions (23 total — verbatim from `43-CONTEXT.md`)

**Wave 1 — graph-io kind extension:**
- **D-01** — Add `dependency` and `plugin` to `graph_io._VALID_KINDS`. Frozenset becomes 12 kinds.
- **D-02** — `dependency` ingestion source = workspace pyproject.toml `[project.dependencies]` + `[dependency-groups]`. One node per `(ecosystem, name)`, ecosystem defaults to `pypi`. Emit `used_by` edge `consumer_package -[used_by]-> dependency`. Versions captured as `versions_in_use: list[str]`.
- **D-03** — `plugin` ingestion source = `.graph-wiki.yaml` `plugins[]` array via existing workspace-io parser. One node per entry; `ecosystem` attr stores plugin host (`claude-code`). No inbound edges in v1.8.
- **D-04** — URI shape: `dependency:<ecosystem>/<name>`, `plugin:<name>`. Backed by Phase 42's `dependency_uri`/`plugin_uri` builders.
- **D-05** — New query helpers: `describe_dependency`, `list_dependencies`, `describe_plugin`, `list_plugins` + `DependencyDescription`/`PluginDescription` dataclasses.
- **D-06** — `cg describe dependency <name>` and `cg describe plugin <name>` subcommands (mechanical). May slip if scope-tight.
- **D-07** — `package_family` deferred to v1.9; not in `ADMITTED_KINDS_V18`.

**Wave 2 — entity_writer.write_entities semantics:**
- **D-08** — Signature: `write_entities(conn: sqlite3.Connection, wiki_root: Path, admitted_kinds: frozenset[str]) -> EntityWriteResult`. v1.8 callers pass `ADMITTED_KINDS_V18 = ADMITTED_KINDS - {"package_family"}`. No direct pyproject parsing.
- **D-09** — `EntityWriteResult` and `EntityWriteError` shapes locked verbatim in CONTEXT.md (lists per state + per-page errors).
- **D-10** — `needs_narrative` triggers: page just CREATED OR any value in `STRUCTURAL_KEYS` subset changed. `STRUCTURAL_KEYS ⊂ SCANNER_OWNED_KEYS`; defined as 10 keys.
- **D-11** — Change detection: load existing via `python-frontmatter`, compare structural-keys via Python equality; collections sorted+deduped before compare.
- **D-12** — Merge semantics for scanner-owned keys = full replacement. No set-union for whitelist keys.
- **D-13** — Non-scanner keys preserved verbatim and in original encountered order.
- **D-14** — Deterministic frontmatter key ordering on write: `uri`, `kind`, scanner keys alphabetical (non-empty only), then human keys in encountered order. Collection values sorted lexically + deduped.
- **D-15** — Write-if-changed guard: render to string buffer; if `existing_bytes == new_bytes`, count as `unchanged` and skip write.

**Hard-delete + audit log:**
- **D-16** — Unconditional hard-delete; recovery via `git log --follow` + `git show <sha>:<path>`.
- **D-17** — `deletions.log` = JSONL at `.graph-wiki/deletions.log`. Schema with timestamp/uri/slug/path/kind/body_was_empty. ISO-8601 UTC.
- **D-18** — Rotation: at 10 MB rename to `.log.1` (overwrite prior); two-file scheme.

**Concurrency + atomicity:**
- **D-19** — `scan.lock` via `fcntl.flock` with `LOCK_EX | LOCK_NB` at `.graph-wiki/scan.lock`. Acquire first; release in try/finally. Raise `WriteLockHeldError` on contention. POSIX-only.
- **D-20** — Lock granularity = whole `write_entities` call (not per-page).
- **D-21** — Partial-failure isolation: catch per-page exceptions into `EntityWriteResult.errors`; continue with the rest.

**Module structure:**
- **D-22** — All wave-2 code in `packages/wiki-io/src/wiki_io/entity_writer.py`, alongside Phase 42's constants. Module additions enumerated in CONTEXT.md (8 helpers + classes + public write_entities).
- **D-23** — No new wiki-io dependencies (python-frontmatter, fcntl, json, pathlib all already present or stdlib).

### Folded Todo
`2026-05-26-fix-scanner-treats-import-root-as-subpackage.md` — graph-io subpackage emission bug. Folded into Wave 1 because Wave 1 already modifies `graph_io/structural_nodes.py`. Wave 1 acceptance gets: "subpackage nodes only emit for directories BELOW the import root."

### Claude's Discretion
- Exact dataclass field types (list/tuple/frozenset for collections in `EntityWriteResult`).
- `EntityWriteError.exception` stores `repr()` (recommended) vs full traceback.
- Whether `_acquire_scan_lock` is exposed publicly (recommended yes — for tests with mock workspaces).
- Whether `cg describe dependency`/`cg describe plugin` ship in Phase 43 or slip.
- Exact YAML emitter config for deterministic ordering.
- File mode for writes (`0o644` per v1.7 convention).

### Deferred Ideas (OUT OF SCOPE — Phase 43)
- LLM narrative generation under `## Narrative` (Phase 45).
- Scanner pipeline wiring `run_scan` Steps 9a/9b/11/12 (Phase 45).
- Index generation (Phase 44).
- Inbound link rewriting (Phase 46).
- `package_family` kind/ingestion/template (v1.9 — Phase 42 dormant artifacts remain).
- Cross-repo dependency dedup (v1.9).
- Plugin transitive deps / plugin-as-edge (v1.9).
- `status: stale` for non-entity pages (Phase 45 retains existing behavior).
- Frontmatter inline-comment preservation across merges (python-frontmatter limitation; accepted).
- Stale-lock recovery beyond fcntl auto-release.
- Per-kind whitelist enforcement at runtime.

</user_constraints>

<phase_requirements>
## Phase Requirements

| ID | Description (REQUIREMENTS.md) | Research Support |
|----|------------------------------|------------------|
| ENTITY-01 | `wiki_io/entity_writer.py::write_entities(conn, wiki_root, admitted_kinds)` queries graph for all admitted nodes; creates new entity pages from per-kind templates with URI-derived slug; populates whitelisted relation frontmatter from graph edges | D-08, D-22; uses `graph_io.queries.list_*` + `describe_*` for graph reads; template loaded via `importlib.resources` (existing `assets/page-templates/` convention from Phase 42 Plan 02); `encode_slug` from Phase 42 produces filename. |
| ENTITY-02 | Merge semantics preserve human-authored frontmatter keys verbatim; scanner only writes whitelisted keys; merge test: write a page with `status: deprecated`, run `write_entities`, assert `status: deprecated` preserved | D-12, D-13; `merge_frontmatter(existing, scanner_update)` is a pure function — easy to unit-test in isolation + Hypothesis property test. |
| ENTITY-03 | Hard-delete reconciliation: when graph node no longer present but entity page exists, delete the page; append-log every deletion to `.graph-wiki/deletions.log` (path, URI, timestamp) for forensic recovery | D-16, D-17, D-18; deletion set = {existing_files_on_disk} − {currently_admitted_uris}; JSONL append (open mode `"a"`); rotation check before append. |
| ENTITY-04 | `write_entities` returns `EntityWriteResult(created, updated, deleted, needs_narrative)` where `needs_narrative` is set of URIs requiring LLM prose generation (new + structurally-changed) | D-09, D-10, D-11; `EntityWriteResult` dataclass with `unchanged` and `errors` extensions over the REQUIREMENTS shape. |
| ENTITY-05 | Workspace-scoped lock file (`.graph-wiki/scan.lock`) prevents concurrent `write_entities` calls; acquires on entry, releases on exit (including exception paths) | D-19, D-20, D-21; `fcntl.flock(LOCK_EX \| LOCK_NB)`; `@contextmanager` decorator preferred. |

</phase_requirements>

## Summary

Phase 43 is a **medium-complexity implementation phase** with one clean architectural split:
- **Wave 1 (graph-io kind extension):** Add `dependency` + `plugin` to the graph; mechanical ingestion code mirroring `packages.refresh` pattern; new query helpers mirroring `describe_package`. Also folds in a small subpackage emission bug fix. Independently testable.
- **Wave 2 (wiki-io `write_entities`):** ~400-500 LOC of new code in `entity_writer.py` covering create/merge/delete + scan.lock + deletions.log. Composed of small pure helpers that compose into one public function. Heavily unit-testable; Hypothesis property tests for `merge_frontmatter` + `encode_slug` interaction; integration tests via a fixture graph + temp wiki.

**Parallelization opportunity (CONTEXT.md §Specifics):** Wave 2 can run with mocked graph queries (`MockGraphConn` returning canned `NodeRecord`/`DependencyDescription` objects). Unification happens in a wave-2 integration test that runs against a real wave-1-ingested fixture graph. This means Plan 02 (entity_writer + tests) does NOT block on Plan 01 (graph-io extension) for its inner-loop dev work.

**Primary recommendation:** Three plans (`43-01` graph-io extension wave, `43-02` entity_writer module + unit tests wave, `43-03` integration tests + optional `cg` CLI subcommands as the synthesis wave). See **Plan Outline** below.

**Architectural risks:** Two notable ones, both addressed by locked decisions:
1. *Frontmatter merge correctness* (Pitfall 2 in research baseline) — mitigated by D-12 (full replacement of scanner keys), D-13 (verbatim human-key preservation), D-14 (deterministic ordering), and Hypothesis property tests at `merge_frontmatter` level.
2. *Concurrent scan races* (Pitfall 9) — mitigated by D-19's `fcntl.flock` non-blocking lock with `WriteLockHeldError`; the test that spawns a second `write_entities` while the first holds the lock is mechanically simple (subprocess or threaded helper holding the lock).

## Architectural Responsibility Map

| Capability | Primary Tier | Secondary Tier | Rationale |
|------------|--------------|----------------|-----------|
| Add `dependency`/`plugin` to admitted kinds | `graph-io` (`queries._VALID_KINDS`) | — | Kind validation is graph-io's concern; consumers (wiki-io) read via queries. |
| Ingest pyproject deps → `dependency` nodes | `graph-io` (`packages.refresh`) | `graph-io` (`structural_nodes.py`) | `packages.py` already parses pyproject.toml — extend in-place; emit nodes + `used_by` edges. |
| Ingest `.graph-wiki.yaml` plugins → `plugin` nodes | `graph-io` (new `_emit_plugin_nodes` helper) | `workspace-io.manifest.read` | Use existing manifest parser; emit graph nodes. |
| `describe_dependency` / `describe_plugin` / `list_*` | `graph-io` (`queries.py`) | — | Mirrors `describe_package`/`list_packages` shape. |
| `cg describe dependency`/`cg describe plugin` | `graph-io` (`cli/`) | — | Discretionary (D-06) — Plan 03 scope decision. |
| Sub-package emission bug fix (folded todo) | `graph-io` (`structural_nodes.py::_walk_subpackages` or `_resolve_import_root` boundary) | — | Surgical fix in Wave 1's existing diff. |
| `write_entities` orchestrator | `wiki-io` (`entity_writer.py`) | — | Composes graph queries + slug + merge + filesystem writes. |
| `merge_frontmatter` pure function | `wiki-io` (`entity_writer.py`) | — | Easy to test in isolation; no I/O. |
| `_render_entity_page` (template + frontmatter → str) | `wiki-io` (`entity_writer.py`) | `python-frontmatter` | Uses `frontmatter.dumps`. |
| `_detect_structural_change` | `wiki-io` (`entity_writer.py`) | — | Pure compare on STRUCTURAL_KEYS subset; sort+dedupe collections. |
| `_acquire_scan_lock` (context manager) | `wiki-io` (`entity_writer.py`) | `fcntl` (stdlib) | POSIX-only; documented in error. |
| `_append_deletion` + `_rotate_deletions_log` | `wiki-io` (`entity_writer.py`) | `json` (stdlib) | JSONL append; rotation is plain `Path.rename`. |
| Hard-delete loop | `wiki-io` (`entity_writer.py`) | — | Set difference: on-disk URIs vs. admitted graph URIs. |
| Integration test fixture (real graph + temp wiki) | `wiki-io` (`tests/test_entity_writer_integration.py`) | `graph-io` (write side via Wave 1) | Verifies wave-1 + wave-2 round-trip on `agent-research` itself. |

**Key tier observation:** `wiki-io.entity_writer` calls `graph_io.queries.*` and `graph_io.uri.*` but does NOT import from `graph_io.packages` / `graph_io.structural_nodes` directly — graph reads are mediated through the read-only `queries` surface. This keeps `entity_writer` testable with a mock connection.

## Standard Stack

### Core
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| Python | ≥3.11 | Runtime | CLAUDE.md floor. |
| `sqlite3` | stdlib | Read-only graph queries via `mode=ro` URIs | Existing pattern in `graph_io.queries`. |
| `python-frontmatter` | ≥1.1 | Round-trip parse/dump of entity-page YAML frontmatter | Already a `wiki-io` dependency (update_tokens.py); D-23. |
| `fcntl` | stdlib | POSIX advisory file lock for `scan.lock` | D-19; no new dep. |
| `json` | stdlib | `deletions.log` JSONL writes | D-17; no new dep. |
| `pathlib` | stdlib | Filesystem paths | Existing convention across wiki-io. |
| `dataclasses` | stdlib | `EntityWriteResult`, `EntityWriteError`, `DependencyDescription`, `PluginDescription` | Existing pattern in `queries.py`. |
| `contextlib.contextmanager` | stdlib | `_acquire_scan_lock` ergonomic wrapping | D-19 implementation. |

### Supporting (test-time only)
| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| `pytest` | ≥8.3 | Runner | All tests. |
| `hypothesis` | ≥6.116 | Property tests for `merge_frontmatter`, `_detect_structural_change` | Already added in Phase 42 Plan 01. |
| `tmp_path` fixture | pytest stdlib | Isolated wiki dirs for write tests | Standard. |
| `tomllib` | stdlib (≥3.11) | Used by `packages.py` for pyproject parsing | Already imported. |
| `yaml` | from `pyyaml`, transitively | `.graph-wiki.yaml` parsing | Already used by `workspace_io.manifest`. |

### What NOT to Use
| Library | Why Excluded |
|---------|--------------|
| `portalocker` / `filelock` (PyPI) | Adds dep; `fcntl.flock` covers POSIX-only requirement (D-19) without new packaging surface. |
| `ruamel.yaml` | python-frontmatter wraps PyYAML; D-23 forbids new deps; comment-preservation is explicitly out-of-scope (deferred). |
| `aiofiles` / async I/O | Phase 43 is sync (D-08); LLM fan-out in Phase 45 is async, not this phase. |
| `sqlalchemy` / ORM | `sqlite3` raw queries match `graph_io.queries` convention. |
| Custom YAML dumper (e.g. `yaml.SafeDumper` subclass) | python-frontmatter's `dumps` is sufficient when paired with manual key-ordering in the dict before dump (D-14). |
| Lock-on-vault-root (`wiki/.scan.lock`) | D-19 specifies `.graph-wiki/scan.lock` — workspace-scoped, not wiki-scoped (matches existing `.graph-wiki/` trace dir convention). |

## Solutions Catalog

### Solution 1: Wave-1 ingestion via in-place `packages.refresh` extension
- **Approach:** Add a second pass inside `graph_io.packages.refresh` (after the existing `package` node emission loop) that reads `[project.dependencies]` + `[dependency-groups].<group>` lists per discovered manifest, dedupes `(ecosystem, name)` across the workspace, emits one `dependency` node per pair, and emits a `used_by` edge from each consumer `package` node to the `dependency`.
- **Strengths:** Single discovery pass — no second `rglob("pyproject.toml")`. Co-located with existing dependency-list extraction (`info["dependencies"]` in `_read_pyproject`). Existing dep-list comprehension in `_read_pyproject` becomes the input; just need to parse PEP 508 strings to extract bare name (e.g. `boto3>=1.38` → `boto3`).
- **Weaknesses:** `packages.refresh` becomes ~50 LOC longer (currently 132); pushes near a soft "module too long" line. Mitigation: extract a `_emit_dependency_nodes(conn, consumer_pkg_key, dep_strings, ctx)` helper.
- **Use when:** Default. Aligns with CONTEXT.md §Integration Points "packages.py ingestion is the wave-1 plug-in point."

### Solution 2: Wave-1 ingestion via new sibling module `graph_io/dependencies.py`
- **Approach:** Mirror the shape of `packages.py` with a new module that runs after `packages.refresh` in `update.py`, reads the same manifests, and emits dependency-only nodes/edges.
- **Strengths:** Stronger module-boundary; future ecosystems (e.g. `npm`) get their own ingestion module.
- **Weaknesses:** Two manifest discovery passes; duplicated `_discover_manifests` logic; one more module to wire into `update.py`. Premature factoring for v1.8 (one ecosystem only).
- **Use when:** When npm/cargo support lands (v1.9+). Defer for now per CONTEXT.md §Integration Points.

**Verdict:** Solution 1.

### Solution 3: Plugin ingestion via small helper in `structural_nodes.emit`
- **Approach:** At the tail of `structural_nodes.emit`, after all File/SubPackage emission, call `workspace_io.manifest.read(workspace_path / ".graph-wiki.yaml")` and emit one `plugin` node per `plugins[]` entry. No edges in v1.8 (D-03).
- **Strengths:** Single phase orchestrator (`update.py`) doesn't need to learn about plugins; co-located with other workspace-scoped emission.
- **Weaknesses:** Coupling — `structural_nodes` becomes aware of `.graph-wiki.yaml`. Currently it only consumes git + filesystem.
- **Use when:** Only if D-03's "no inbound edges" stays true. Acceptable for v1.8; revisit if plugins ever participate in edges.

### Solution 4: Plugin ingestion via dedicated `graph_io/plugins.py`
- **Approach:** New module ~30 LOC; called from `update.py` after `structural_nodes.emit`.
- **Strengths:** Cleanest tier boundary; `structural_nodes.py` stays git/filesystem-only.
- **Weaknesses:** One more module + one more wire-up in `update.py`. Modest.
- **Use when:** Default for v1.8. Slight preference over Solution 3 for module hygiene.

**Verdict:** Solution 4. Tiny module, cleaner boundary, easy to test.

### Solution 5: `write_entities` orchestrator — single function with inline helpers
- **Approach:** One ~150-LOC `write_entities` function that performs lock acquire → query → per-URI process → deletion sweep → log writes → return result, with all helpers inlined as local functions.
- **Strengths:** Single read entry point; tightly scoped helpers.
- **Weaknesses:** Hard to unit-test the inner helpers; one giant function is brittle.

### Solution 6: `write_entities` orchestrator — composition of module-level helpers
- **Approach:** Module-level helpers (`merge_frontmatter`, `_render_entity_page`, `_detect_structural_change`, `_append_deletion`, `_rotate_deletions_log`, `_acquire_scan_lock`) each tested independently; `write_entities` is a thin orchestrator (~80 LOC) that wires them together.
- **Strengths:** Each helper unit-tested in isolation with no fixture setup; matches CONTEXT.md D-22's explicit helper enumeration.
- **Weaknesses:** Slightly more LOC overall; minor.

**Verdict:** Solution 6. CONTEXT.md D-22 explicitly enumerates the helpers — this is the locked decomposition.

### Solution 7: Lock semantics — `fcntl.flock` (D-19)
- **Approach:** Open `.graph-wiki/scan.lock` for write, call `fcntl.flock(fd, LOCK_EX | LOCK_NB)`. On `BlockingIOError`, raise `WriteLockHeldError`. Release on `fcntl.flock(fd, LOCK_UN)` in `finally` (and implicitly on fd close).
- **Strengths:** Stdlib; auto-releases on process death (kernel-managed); non-blocking variant fails fast on contention (matches D-19 "raise immediately").
- **Weaknesses:** POSIX-only — Windows is not supported by the rest of the stack (per CLAUDE.md / project README), so this is fine.

### Solution 8: Lock semantics — sentinel-file with PID check
- **Approach:** Check for `.graph-wiki/scan.lock`; if present, read PID and check if alive; if not, take over.
- **Strengths:** Cross-platform.
- **Weaknesses:** Race-prone (TOCTOU); requires stale-lock cleanup logic; adds complexity for no v1.8 benefit.

**Verdict:** Solution 7 (matches D-19).

### Solution 9: Deletion-log rotation — size check before write
- **Approach:** Inside `_append_deletion`: `if path.stat().st_size >= MAX_BYTES: _rotate(...)` then append.
- **Strengths:** Simple; no background thread; idempotent.
- **Weaknesses:** Adds a `stat()` per append (cheap; deletions rare).

### Solution 10: Deletion-log rotation — append-then-check
- **Approach:** Append unconditionally; check size at end of run; rotate if needed.
- **Strengths:** Slightly fewer syscalls.
- **Weaknesses:** A run that adds 5 GB of deletions (hypothetical) would not rotate mid-run.

**Verdict:** Solution 9 (matches D-18's "checks file size before write, rotates if needed").

## Implementation Patterns

### Pattern A: `merge_frontmatter` pure function
```python
SCANNER_OWNED_KEYS: frozenset[str] = frozenset({...})  # from Phase 42

def merge_frontmatter(existing: dict, scanner_update: dict) -> dict:
    """Return a new dict: scanner-owned keys = full replacement (D-12);
    other keys preserved verbatim and in original encountered order (D-13)."""
    out: dict = {}
    # Always-first keys per D-14:
    out["uri"] = scanner_update.get("uri", existing.get("uri"))
    out["kind"] = scanner_update.get("kind", existing.get("kind"))
    # Scanner-owned keys (alphabetical, non-empty only):
    for key in sorted(SCANNER_OWNED_KEYS - {"uri", "kind"}):
        if key in scanner_update and scanner_update[key] not in (None, [], {}, ""):
            out[key] = _sort_dedupe(scanner_update[key]) if isinstance(scanner_update[key], list) else scanner_update[key]
    # Human keys in original encountered order:
    for key, val in existing.items():
        if key not in SCANNER_OWNED_KEYS and key not in out:
            out[key] = val
    return out
```
Property test: `(arb_existing, arb_scanner) → merge_frontmatter` preserves every non-whitelist key from `arb_existing` and takes every whitelist key from `arb_scanner`.

### Pattern B: `_acquire_scan_lock` context manager
```python
@contextmanager
def _acquire_scan_lock(workspace_root: Path) -> Iterator[None]:
    lock_path = workspace_root / ".graph-wiki" / "scan.lock"
    lock_path.parent.mkdir(parents=True, exist_ok=True)
    fd = os.open(lock_path, os.O_WRONLY | os.O_CREAT, 0o644)
    try:
        try:
            fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError as exc:
            raise WriteLockHeldError(
                f"another scan in progress for this workspace: {workspace_root}"
            ) from exc
        try:
            yield
        finally:
            fcntl.flock(fd, fcntl.LOCK_UN)
    finally:
        os.close(fd)
```

### Pattern C: Deletion sweep
```python
# Per admitted_kinds, collect URIs from graph:
admitted_uris: set[str] = set()
if "package" in admitted_kinds:
    for node in queries.list_packages(conn):
        admitted_uris.add(node.attrs.get("uri") or pkg_uri(ctx, node.name))
# ... same for each kind in admitted_kinds

# Inventory on disk:
on_disk: dict[str, Path] = {}
for page_path in (wiki_root / "entities").glob("*.md"):
    post = frontmatter.load(page_path)
    uri = post.metadata.get("uri")
    if uri:
        on_disk[uri] = page_path

# Deletion set:
to_delete = {u: p for u, p in on_disk.items() if u not in admitted_uris}
for uri, path in to_delete.items():
    body_was_empty = _is_body_empty(path)
    _append_deletion(log_path, {
        "timestamp": datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z"),
        "uri": uri,
        "slug": path.stem,
        "path": str(path.relative_to(workspace_root)),
        "kind": _infer_kind(uri),
        "body_was_empty": body_was_empty,
    })
    path.unlink()
```

### Pattern D: Structural-key change detection
```python
STRUCTURAL_KEYS = frozenset({
    "domains", "depends_on", "test_suites", "entry_points",
    "parent_domain", "sub_domains", "packages",
    "tested_packages", "members", "used_by",
})

def _detect_structural_change(existing_fm: dict, new_fm: dict) -> bool:
    for key in STRUCTURAL_KEYS:
        old = existing_fm.get(key)
        new = new_fm.get(key)
        if isinstance(old, list) and isinstance(new, list):
            if sorted(set(old)) != sorted(set(new)):
                return True
        elif old != new:
            return True
    return False
```

### Pattern E: `_render_entity_page` (template + frontmatter → string)
```python
def _render_entity_page(template_path: Path, frontmatter_dict: dict) -> str:
    template = frontmatter.load(template_path)
    template.metadata = frontmatter_dict
    return frontmatter.dumps(template) + "\n"
```
Note: `frontmatter.dumps` will sort_keys unless we override. To preserve D-14 ordering, dump the YAML separately or pass `sort_keys=False` to the underlying yaml handler. Concrete: subclass `frontmatter.YAMLHandler` to set `default_flow_style=False, sort_keys=False`, OR construct the YAML block manually with the ordered dict.

## Validation Architecture

Per Nyquist Dimension 8 — what evidence proves Phase 43 is correct beyond green tests?

### Behavioral assertions (ROADMAP success criteria, mapped to test cases)

| SC# | Roadmap criterion | Test type | Test name |
|-----|-------------------|-----------|-----------|
| 1   | Fixture graph → one entity page per admitted node, with correct relation frontmatter | Integration | `test_write_entities_round_trip_on_agent_research` |
| 2   | `status: deprecated` survives subsequent `write_entities` (merge test) | Unit + integration | `test_merge_preserves_human_authored_status` |
| 3   | Disappeared graph node → page deleted + JSONL log entry with all required fields | Integration | `test_hard_delete_logs_to_deletions_log` |
| 4   | Returns `EntityWriteResult(created, updated, deleted, needs_narrative)` with correct sets | Unit + integration | `test_entity_write_result_shape_and_needs_narrative` |
| 5   | Second concurrent `write_entities` raises `WriteLockHeldError` immediately | Integration (threaded or 2-conn) | `test_scan_lock_blocks_concurrent_writes` |

### Property tests (Hypothesis)

| Property | Generator | Assertion |
|----------|-----------|-----------|
| Merge preserves non-whitelist keys | `(arb_existing_fm, arb_scanner_fm)` where `arb_existing_fm` includes both whitelist and human keys | `merge_frontmatter(e, s)` contains every key from `e` not in `SCANNER_OWNED_KEYS`, with original value |
| Merge takes whitelist keys from scanner | same | `merge_frontmatter(e, s)[k] == s[k]` for `k in SCANNER_OWNED_KEYS ∩ s.keys()` |
| Deterministic key ordering | same | First two keys of merged dict are `uri`, `kind`; scanner keys are alphabetical; human keys preserve encountered order |
| Structural change detection | `(existing, new)` with random STRUCTURAL_KEYS values | True iff at least one structural key value differs (with list sort-dedupe) |

### Deterministic-output regression test

Run `write_entities` twice on the same fixture graph + same temp wiki. Second run should produce zero `created` and zero `updated` (all `unchanged`). Asserts D-14 byte-stability of the YAML output.

### Negative-path tests (per-page error isolation, D-21)

Inject a malformed existing page (broken YAML frontmatter); assert it lands in `EntityWriteResult.errors` with the right URI and the rest of the pages are still processed. Lock is held throughout.

### Graph-io extension tests (Wave 1)

| Aspect | Test |
|--------|------|
| `_VALID_KINDS` includes both new kinds | `test_valid_kinds_includes_dependency_plugin` |
| `_read_pyproject` extracts dep names from PEP 508 | `test_pep_508_name_extraction` |
| `packages.refresh` emits `dependency` nodes + `used_by` edges | `test_dependency_ingestion_from_workspace` |
| `plugins.emit` reads `.graph-wiki.yaml`, emits one node per plugin | `test_plugin_ingestion_from_manifest` |
| `describe_dependency` / `list_dependencies` shape | `test_describe_dependency_returns_dependency_description` |
| `describe_plugin` / `list_plugins` shape | `test_describe_plugin_returns_plugin_description` |
| Folded subpackage bug: no subpackage emitted at import root | `test_no_subpackage_node_at_import_root` |

### Operational sanity (run-against-agent-research)

CONTEXT.md §Specifics calls for an integration test on `agent-research` itself:
- Run wave-1 ingestion → assert every workspace member appears as a `pkg:` node, every dep (boto3, langchain-aws, pyyaml, …) appears as a `dependency:pypi/` node, the plugin from `.graph-wiki.yaml` appears as a `plugin:` node.
- Run wave-2 `write_entities` into a temp wiki dir → assert one entity page per admitted node, with kind-specific frontmatter populated, idempotent on second run, `needs_narrative` non-empty on first run and empty on second run.

## Risks & Pitfalls

### Risk 1: Frontmatter merge silently loses comments
- **What:** `python-frontmatter` (which uses PyYAML internally) does not preserve inline `# comment` lines on round-trip.
- **Impact:** A human who writes `status: deprecated  # because of CVE-2024-xxxx` loses the comment on first merge.
- **Mitigation:** Documented and accepted per CONTEXT.md §Deferred ("Frontmatter-comment-preservation across merges"). Vault is disposable; recovery is `git log --follow`.
- **Test:** None — accepted behavior.

### Risk 2: PEP 508 parsing for dep names
- **What:** `[project.dependencies]` entries are full PEP 508 strings: `"boto3>=1.38"`, `"langchain-aws[bedrock]>=1.4.6"`, `"foo; python_version >= '3.11'"`.
- **Impact:** Naive `split()` produces wrong names; collisions across normalized variants.
- **Mitigation:** Use `packaging.requirements.Requirement` from `packaging` (transitively present via `uv` / `pip` infrastructure). Alternative: regex `^[A-Za-z0-9_.-]+` to extract the leading name. Simplest: `re.match(r"^[A-Za-z0-9_.-]+", s).group(0).lower()` — handles bare names and bracketed extras.
- **Test:** Unit test on edge cases (`boto3>=1.38`, `langchain-aws[bedrock]`, `foo; python_version >= '3.11'`, `git+https://...#egg=mypkg`).
- **Decision needed in plan:** which extractor. Recommend: regex (no new dep, covers v1.8 cases).

### Risk 3: PyYAML emits collections in inconsistent order
- **What:** `yaml.safe_dump` defaults sort keys alphabetically (helpful for D-14) but quirks: bool emission style, multiline scalars, etc.
- **Impact:** Two runs with identical input could emit semantically-equivalent but byte-different YAML, defeating D-15 write-if-changed.
- **Mitigation:** Lock the dump config: `yaml.safe_dump(data, sort_keys=False, default_flow_style=False, allow_unicode=True, width=10_000)`. Width prevents line-folding. `sort_keys=False` because we manually order per D-14. Verify with the determinism regression test (two consecutive runs produce zero diffs).

### Risk 4: `frontmatter.dumps()` strips body whitespace
- **What:** `frontmatter.dumps(post)` may normalize trailing newlines.
- **Impact:** Idempotency violation: first write produces "...\n\n", second write of identical data produces "...\n", triggering `updated` instead of `unchanged`.
- **Mitigation:** Always append `"\n"` to `frontmatter.dumps()` output, and ensure the template body is stored without trailing whitespace. Equality check is on full bytes.
- **Test:** Determinism regression test (above) catches this.

### Risk 5: Mock graph connection drifts from real schema
- **What:** Wave-2 unit tests using `MockGraphConn` could pass while real graph behavior differs.
- **Impact:** Integration test caught a bug that unit tests should have caught.
- **Mitigation:** Wave 1 lands first (graph extension + tests pass) → Wave 2 integration test runs against a real wave-1-built graph. Don't lean solely on `MockGraphConn`.
- **Test:** The integration test in `test_entity_writer_integration.py` is the safety net.

### Risk 6: `fcntl.flock` does not protect against non-`flock`-using readers/writers
- **What:** `flock` is advisory; nothing prevents `os.unlink` or another writer that doesn't acquire the lock.
- **Impact:** Two co-resident scanners both using `write_entities` are protected (they both call `_acquire_scan_lock`). A user-script doing `rm wiki/entities/*` is not.
- **Mitigation:** Accept. The contract is "concurrent `write_entities` calls fail loudly" (D-19), not "no out-of-band tampering possible."

### Risk 7: `deletions.log` rotation race
- **What:** Rotation reads `stat().st_size`, then renames, then appends. A second process between the stat and rename could lose the rotated content. (Theoretical — the scan.lock prevents this.)
- **Impact:** Theoretical only; scan.lock is the practical guarantee.
- **Mitigation:** Rotation happens INSIDE `write_entities` which holds the scan.lock. No additional locking needed.

### Risk 8: ChatBedrockConverse pseudo-async (NOT APPLICABLE)
- **What:** Phase 43 is sync; no LLM calls.
- **Impact:** None.
- **Mitigation:** Phase 45 problem, not ours.

### Risk 9: `_walk_subpackages` import-root bug (folded todo)
- **What:** Current code emits a `subpackage` node for the import root itself (e.g., `graph_io` package emits a `subpackage:graph_io` at its `__init__.py`-bearing import root).
- **Impact:** Wave 2 entity-writer would consume noisy subpackage URIs if v1.9 ever admits `subpackage` as an entity kind. v1.8 deals with it now because Wave 1 is already touching the file and rebaselining snapshots.
- **Mitigation:** Modify `_walk_subpackages` (or insert a filter) so the yielded set excludes `import_root` itself; only directories strictly under the import root count.
- **Test:** `test_no_subpackage_node_at_import_root` — fixture package with importable `__init__.py` and one nested `__init__.py`; assert exactly one `subpackage` node (the nested one) emitted, not two.

## Plan Outline

Recommended **three plans, two waves**:

### Wave 1 (parallel) — graph-io kind extension

**Plan 43-01: graph-io dependency + plugin ingestion + folded subpackage fix**
- **Wave:** 1
- **Depends on:** Phase 42's plans (entity_writer scaffold + URI builders) — implicit; Phase 43 starts after Phase 42 ships.
- **Files modified:**
  - `packages/graph-io/src/graph_io/queries.py` (add `dependency`, `plugin` to `_VALID_KINDS`; add `DependencyDescription`, `PluginDescription` dataclasses; add `describe_dependency`, `list_dependencies`, `describe_plugin`, `list_plugins`)
  - `packages/graph-io/src/graph_io/packages.py` (extend `refresh` to emit `dependency` nodes + `used_by` edges from pyproject deps; add `_extract_dep_name` helper)
  - `packages/graph-io/src/graph_io/plugins.py` (NEW — `emit(conn, *, workspace_root, ctx)` reads `.graph-wiki.yaml`, emits `plugin` nodes)
  - `packages/graph-io/src/graph_io/structural_nodes.py` (folded subpackage import-root bug fix)
  - `packages/graph-io/src/graph_io/update.py` (wire `plugins.emit` into the update pipeline)
  - `packages/graph-io/tests/test_queries.py` (kinds, describe_*, list_*)
  - `packages/graph-io/tests/test_packages.py` (dependency ingestion + PEP 508 name extraction)
  - `packages/graph-io/tests/test_plugins.py` (NEW)
  - `packages/graph-io/tests/test_structural_nodes.py` (subpackage import-root regression test)
- **Requirements addressed:** Indirect for ENTITY-01 (provides graph data). Direct: none of ENTITY-01..05 (those are wiki-io).
- **Truths:** `_VALID_KINDS` contains 12 kinds. `describe_dependency(conn, ecosystem='pypi', name='boto3')` returns `DependencyDescription`. `list_plugins(conn)` returns at least one entry on the `agent-research` workspace. `subpackage` count after `update` on a fixture package does NOT include the import root.

**Plan 43-02: wiki-io entity_writer.py module + unit tests (mocked graph)**
- **Wave:** 1 (parallel-safe; uses `MockGraphConn`)
- **Depends on:** Phase 42 Plan 01 (entity_writer scaffold with `ADMITTED_KINDS`, `SCANNER_OWNED_KEYS`, `encode_slug`, `decode_slug`).
- **Files modified:**
  - `packages/wiki-io/src/wiki_io/entity_writer.py` (add `STRUCTURAL_KEYS`, `EntityWriteError`, `EntityWriteResult`, `WriteLockHeldError`, `merge_frontmatter`, `_render_entity_page`, `_detect_structural_change`, `_rotate_deletions_log`, `_append_deletion`, `_acquire_scan_lock`, `write_entities`, `ADMITTED_KINDS_V18`)
  - `packages/wiki-io/tests/test_entity_writer.py` (unit tests + Hypothesis property tests)
  - `packages/wiki-io/tests/conftest.py` (`MockGraphConn` fixture if not already present)
- **Requirements addressed:** ENTITY-01, ENTITY-02, ENTITY-04, ENTITY-05 (ENTITY-03 partially — log writing logic; full delete sweep verified by integration in Plan 03).
- **Truths:** `from wiki_io.entity_writer import write_entities, EntityWriteResult, WriteLockHeldError, merge_frontmatter, STRUCTURAL_KEYS, ADMITTED_KINDS_V18` succeeds. `merge_frontmatter(existing={"status": "deprecated"}, scanner_update={"uri": "pkg:...", "kind": "package", "domains": ["a"]})` preserves `status`. Property test (`@given`) ≥1000 examples passes. `_acquire_scan_lock` raises `WriteLockHeldError` when invoked twice on the same path. Workspace tests run green: `uv run --package wiki-io pytest tests/test_entity_writer.py -x` exits 0.

### Wave 2 — integration + optional CLI

**Plan 43-03: integration tests (wave-1 + wave-2 round-trip) + optional `cg` subcommands + REQUIREMENTS/STATE update**
- **Wave:** 2
- **Depends on:** 43-01, 43-02
- **Files modified:**
  - `packages/wiki-io/tests/integration/test_entity_writer_integration.py` (NEW — fixture-graph + temp-wiki round-trip; deletion test; concurrent-lock test; determinism regression)
  - `packages/graph-io/src/graph_io/cli/q_describe.py` or similar (NEW subcommands `cg describe dependency`, `cg describe plugin` — D-06; SCOPE-OPTIONAL, may slip)
  - `packages/graph-io/tests/test_cli_describe.py` (covers new subcommands if shipped)
  - `.planning/REQUIREMENTS.md` (ENTITY-01..05 → status: completed via traceability section)
  - `.planning/STATE.md` (record Phase 43 completion + note `package_family` deferral + folded-todo resolution)
  - `.planning/todos/pending/2026-05-26-fix-scanner-treats-import-root-as-subpackage.md` → move to `resolved/`
  - `.planning/ROADMAP.md` (Phase 43 success criteria check-off)
- **Requirements addressed:** ENTITY-01, ENTITY-02, ENTITY-03, ENTITY-04, ENTITY-05 (full integration coverage).
- **Truths:** Integration test against `agent-research` workspace itself: every workspace package has a `pkg:` entity page; every dep has a `dependency:pypi/` page; plugin from `.graph-wiki.yaml` has a `plugin:` page. Determinism test: two consecutive runs on the same graph produce zero `updated`. Concurrent-lock test: second `write_entities` raises `WriteLockHeldError` immediately (within 100 ms). Deletion test: removing a node from a fixture graph then re-running deletes the page and adds an entry to `.graph-wiki/deletions.log` with all 6 schema fields.

## Open Questions

| Q | Description | Recommendation |
|---|-------------|----------------|
| Q1 | Dep-name extraction: `packaging.requirements.Requirement` (industry standard, but adds a transitive dep visibility) vs. regex (no dep, covers v1.8 cases) | Regex per D-23 ("no new wiki-io dependencies"). graph-io can still use it — but `packaging` may be transitively present via `pip`/`uv`; check before importing. If absent, regex covers all observed cases in `agent-research`. |
| Q2 | `_render_entity_page` YAML dump: customize PyYAML SafeDumper (cleaner) vs. manually order keys before `frontmatter.dumps` (simpler) | Manually order in dict; use `frontmatter.dumps(post, sort_keys=False)` if supported; otherwise manual YAML emit. Pure function, no subclass needed. |
| Q3 | `cg describe dependency`/`cg describe plugin` ship in Phase 43 or slip? | Ship in Plan 43-03 as a stretch. Mechanical (≤80 LOC + tests). If 43-03 exceeds context budget, defer to Phase 45 as a 1-pointer follow-up. |
| Q4 | Should `_acquire_scan_lock` test use `subprocess` or `threading`? | `threading` — simpler; `fcntl.flock` is process-level on POSIX but same fd test in threads also raises if we open two fds. CONTEXT.md leaves to implementer. Recommend: two `os.open` fds in the same process via threads → second `flock(LOCK_EX | LOCK_NB)` should raise BlockingIOError → wrapped as `WriteLockHeldError`. |
| Q5 | `_infer_kind(uri)` for deletion log — parse the URI scheme prefix (before `:`)? Or look up from existing frontmatter before delete? | Read frontmatter before unlink (we already do it for `body_was_empty`); use `post.metadata["kind"]` if present, else fall back to URI prefix split. |
| Q6 | `body_was_empty` detection: strip the template default (`## Narrative\n\n*To be generated...*\n`) before checking? | Yes — D-17 says "page body (after stripping the H1 + `## Narrative` placeholder template default) had no human-authored content." Implement as: parse with frontmatter, drop trailing whitespace from body, compare against the rendered-template default for that kind. If equal or empty → `body_was_empty = true`. |

## Sources

- `.planning/phases/43-entity-writer/43-CONTEXT.md` — All 23 locked decisions
- `.planning/phases/42-uri-slug-scheme-per-kind-templates/42-CONTEXT.md` — Phase 42 design locks (ADMITTED_KINDS, SCANNER_OWNED_KEYS, slug encoding)
- `.planning/phases/42-uri-slug-scheme-per-kind-templates/42-01-PLAN.md` — entity_writer scaffold contract (imported symbols for Phase 43)
- `.planning/phases/42-uri-slug-scheme-per-kind-templates/42-02-PLAN.md` — URI builders + template files contract
- `.planning/REQUIREMENTS.md` §ENTITY — ENTITY-01..05
- `.planning/ROADMAP.md` §Phase 43 — Goal + 5 success criteria
- `.planning/STATE.md` — Hard-delete-with-log policy; Pitfalls 2/3/9
- `.planning/research/ARCHITECTURE.md`, `.planning/research/PITFALLS.md`, `.planning/research/FEATURES.md` — milestone-level research baseline
- `packages/graph-io/src/graph_io/queries.py` — `_VALID_KINDS`, `describe_package`, `list_packages` (templates for new helpers)
- `packages/graph-io/src/graph_io/packages.py` — `refresh()` (Wave 1 extension point)
- `packages/graph-io/src/graph_io/structural_nodes.py` — `_walk_subpackages` (folded bug-fix site)
- `packages/graph-io/src/graph_io/uri.py` — Phase 42 URI builders (consumed; `pkg_uri`, `dependency_uri`, `plugin_uri`)
- `packages/graph-io/src/graph_io/upsert.py` — `upsert_records` pattern (used by ingestion code)
- `packages/workspace-io/src/workspace_io/manifest.py` — `read()` for `.graph-wiki.yaml` `plugins[]` array
- `packages/wiki-io/src/wiki_io/update_tokens.py` — `python-frontmatter` round-trip pattern (read with `frontmatter.loads`, write with raw string assembly)
- `packages/wiki-io/src/wiki_io/append_log.py` — Reference for log-file append patterns (deletions.log is JSONL, not this format — but path conventions match)
- `packages/wiki-io/pyproject.toml` — Confirms `python-frontmatter>=1.1` already a dep; no new wiki-io deps (D-23)
- `CLAUDE.md` §2 (no agent framework), §8 (pytest/syrupy/Hypothesis), §3 (Bedrock-only — not applicable Phase 43)
- Python stdlib docs — `fcntl.flock` flags `LOCK_EX`/`LOCK_NB`/`LOCK_UN`; `os.open` flags; `contextlib.contextmanager`

## RESEARCH COMPLETE
