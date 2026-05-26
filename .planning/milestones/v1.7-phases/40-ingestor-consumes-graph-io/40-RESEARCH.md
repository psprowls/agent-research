---
phase: 40
slug: ingestor-consumes-graph-io
gathered: 2026-05-26
status: Ready for planning
---

# Phase 40 — Ingestor Consumes graph-io: Technical Research

## 1. Scope Recap

Wire `run_ingest_source()` to consult graph-io for canonical entity existence BEFORE making ingest-routing decisions. Decisions D-01..D-08 are locked in `40-CONTEXT.md`. This research answers the open implementation questions the planner needs to write a deterministic PLAN.md.

## 2. NOT_INITIALIZED Error Path (D-01, D-02)

### 2.1 Source of the exit code

`packages/graph-io/src/graph_io/exit_codes.py` defines:

```python
SUCCESS = 0
GENERIC = 1
STALE = 2
NOT_INITIALIZED = 3
SCHEMA_MISMATCH = 4
NOT_IN_GIT_REPO = 5
UPDATE_IN_PROGRESS = 6
AMBIGUOUS = 7
```

Phase 40 imports `from graph_io import exit_codes` and uses `exit_codes.NOT_INITIALIZED` (the integer `3`).

### 2.2 Where the error trips in run_ingest_source

The ingestor opens graph-io directly via `read_only_connect()` (NOT through `ops_update.run` — that is Phase 39's pattern). The detection is therefore exception-based, not exit-code-based:

```python
from graph_io.store import GraphNotInitializedError, read_only_connect
from workspace_io.paths import graph_dir

db_path = graph_dir(workspace_path) / "code.db"
try:
    conn = read_only_connect(db_path)
except GraphNotInitializedError:
    sys.stderr.write(
        "error: graph-io not initialized for this workspace. "
        "Run 'graph-wiki-agent graph build' (or 'cg update') to initialize, then retry.\n"
    )
    raise typer.Exit(code=exit_codes.NOT_INITIALIZED)
```

The error path NEVER reaches the LLM call. This is the deliberate inverse of Phase 39's scanner behavior (Phase 39 D-08 emits a fallback log line and proceeds; Phase 40 exits with code 3).

### 2.3 Surface boundaries

- **CLI surface** (`cli.py:ingest_source`, line 565): the Typer `ingest_source` command currently catches `(RuntimeError, ValueError)` and re-raises as `typer.Exit(code=1)`. Phase 40 needs the NOT_INITIALIZED exit code to bypass this generic-1 path. Two options:
  1. **Raise inside `run_ingest_source`** with a new structured exception (e.g. `IngestorGraphNotInitializedError`); the CLI catches it specifically and exits with code 3.
  2. **Detect in the CLI layer** by importing `GraphNotInitializedError` and catching it explicitly before the generic handler. Simpler; no new exception class.

   **Recommendation:** option (1). The exit code is a contract from `run_ingest_source`, not a CLI quirk. MCP callers (next bullet) also need to observe the condition.

- **MCP surface** (`mcp/server.py:wiki_ingest`, line 336): currently re-raises non-success as `RuntimeError(f"ingest failed: {e}")`. The MCP host (DeepAgents CLI) sees a structured error; Phase 40 may either:
  1. Surface NOT_INITIALIZED as a distinct field in `WikiIngestOutput` (additive schema change), OR
  2. Let the existing `RuntimeError` chain handle it — the message already names the condition.

   **Recommendation:** option (2) for v1.7. Surfacing in the schema is a Phase 40 stretch that does not need to ship now. Document the deferral.

### 2.4 Connection lifetime

Mirror Phase 37 D-03 / Phase 39 D-05: open `read_only_connect()` once at command entry, close in `finally`. Per-call SQLite open is forbidden (STATE.md Pitfall 4).

## 3. Path-First, Name-Fallback Lookup (D-03)

### 3.1 Path lookup primitive

`graph_io.queries.describe_path(conn, path=<path>)` returns a `PathDescription | None`. The `path` argument is the file path as stored in the `file` kind's `path` column.

**Critical:** `describe_path` returns a `PathDescription` (with children/imports/role_flags) for the FILE itself, not for the package that contains it. The URI of a file node lives in `attrs_json` (not on `PathDescription`). For Phase 40's purposes, what we want is:

- If source is `agents/graph-wiki-agent/src/graph_wiki_agent/commands/scan.py` → look up the PACKAGE that contains that file; URI is `pkg:org/repo/graph-wiki-agent`.
- If source is a markdown ABOUT the package (e.g. `docs/graph-wiki-agent.md`) → no `file` node exists for that path (only source files are in the graph). Fall through to name lookup.

This means **the path lookup needs to be two queries**:
1. First: query for a `kind='file'` node with matching `path`. If found, the path-lookup target is the containing `package` node (resolved by joining `edges WHERE kind='contains'`).
2. Alternatively, query for a `kind='package'` node where the source path is one of its files.

**Recommendation:** use a single SQL query joining `nodes (file)` → `edges (contains)` → `nodes (package)`. Encapsulate this as a private helper in `commands/ingest.py`:

```python
def _lookup_entity_by_path(conn, repo_root: Path, source_path: Path) -> tuple[str, str, dict] | None:
    """Return (uri, name, attrs) for the package/file's canonical entity, or None.

    Tries (in order):
      1. The package that CONTAINS the file at `source_path` (most useful — slugs to package overview).
      2. The file itself if it lives at the package root (e.g. README, setup.py).

    Returns the first match's (uri, name, attrs) or None if neither matches.
    """
    try:
        rel = source_path.resolve().relative_to(repo_root.resolve()).as_posix()
    except ValueError:
        return None
    # SQL: find the package containing this file
    row = conn.execute(
        "SELECT p.name, p.attrs_json "
        "FROM nodes f "
        "JOIN edges e ON e.dst = f.id AND e.kind='contains' "
        "JOIN nodes p ON e.src = p.id "
        "WHERE f.kind='file' AND f.path = ? AND p.kind='package' "
        "LIMIT 1",
        (rel,),
    ).fetchone()
    if row is None:
        return None
    name, attrs_json = row
    attrs = json.loads(attrs_json) if attrs_json else {}
    uri = attrs.get("uri")
    if not uri:
        return None
    return uri, name, attrs
```

**Threat mitigation:** `source_path.resolve().relative_to(repo_root.resolve())` raises `ValueError` if the source is outside the repo — handled by returning `None` (fall through to name lookup).

### 3.2 Name lookup primitive

`graph_io.queries.find(conn, name=<title>)` returns `list[NodeRecord]`. For Phase 40:

```python
matches = queries.find(conn, name=name_guess)
# Returns nodes of any kind whose name matches exactly.
```

**Tie-breaking (D-03 multi-match rule, per CONTEXT specifics):** if `len(matches) > 1`, log a single stderr line:

```
[ingest: name '<n>' matches multiple graph nodes (<URI1>, <URI2>, ...); falling back to LLM-guessed slug]
```

…and treat as the no-match path (D-05). This is the simplest deterministic rule that doesn't require ordering matches arbitrarily.

**Filter to "interesting" kinds:** name lookups should likely restrict to entity-bearing kinds (`package`, `class`, `function`, `domain`, etc.) — NOT `file` (file names are too noisy: `__init__.py` collides everywhere). Recommend:

```python
_ENTITY_KINDS = frozenset({"package", "class", "function", "method", "domain"})
matches = [m for m in queries.find(conn, name=name_guess) if m.kind in _ENTITY_KINDS]
```

Pick the URI from `matches[0].attrs["uri"]` (or alternatively `matches[0]` directly if `attrs` carries `uri`).

### 3.3 What "name" to pass

The ingestor's name-lookup input is the LLM-guessed title OR the source filename stem (the existing `title_guess` variable at `ingest.py:406`). For consistency, use `title_guess` (which has already been computed before the LLM call).

## 4. URI → Slug Derivation (D-04)

### 4.1 Phase 39's helper situation

Phase 39 does **NOT** extract a shared URI → slug helper. Its slug-derivation is encapsulated in `wiki_io.scan_monorepo._wiki_relative_path_for(pkg, vault_dir)` which takes a **decorated package dict** (with `pkg["uri"]`, `pkg["is_app"]`, `pkg["domain"]`) and returns a vault-relative path like `domains/<d>/packages/<n>/overview.md`.

This helper:
- Lives in `packages/wiki-io/src/wiki_io/scan_monorepo.py:613`.
- Takes a **dict-shaped input**, not a URI string.
- Returns a **full relative path** (`packages/<n>/overview.md`), not just a slug.
- Routes by `pkg["type"] == "app"`, `pkg.get("domain")`, or default `packages/`.

For Phase 40, the ingestor's path-lookup `_lookup_entity_by_path` already returns `(uri, name, attrs)`. The ingestor needs a **slug** (the canonical filename stem) — not a full vault path. The page_type routing is independently chosen by the LLM (`_route_target_path` consumes `page_type` separately).

### 4.2 Recommended approach: extract a small shared helper

Per CONTEXT D-04: "prefer a shared utility ... so both scanner and ingestor stay in lockstep. If Phase 39 hasn't extracted a helper, Phase 40's planner picks: (a) extract one as part of this phase, (b) duplicate with a TODO to consolidate later. Suggest (a)."

**Recommendation: option (a) — extract.**

The minimal helper Phase 40 needs is `slug_from_uri(uri: str) -> str`: take a URI like `pkg:org/repo/graph-io` and return the last segment `graph-io` (which becomes the slug). The page-type routing in `_route_target_path(wiki, page_type, slug)` already lives in `commands/ingest.py` and handles the prefix.

Place the helper in **`agents/graph-wiki-agent/src/graph_wiki_agent/uri_slug.py`** (new module — single-purpose). Both Phase 40 (now) and a future Phase 39 refactor can call it:

```python
# agents/graph-wiki-agent/src/graph_wiki_agent/uri_slug.py
"""URI → slug derivation (Phase 39/40 shared invariant).

The graph is the source of truth for the canonical slug of an entity-backed
wiki page. Both the scanner (Phase 39) and the ingestor (Phase 40) consult
the graph and derive the slug by stripping everything but the URI's last
segment.

The page-type routing prefix (`apps/`, `domains/<d>/packages/`, `packages/`)
is chosen by `commands/ingest._route_target_path` from `page_type` + slug.
This module returns only the slug — keeping responsibilities split.
"""
from __future__ import annotations


def slug_from_uri(uri: str) -> str:
    """Return the last URI segment as the canonical slug.

    Examples:
        pkg:org/repo/graph-io        -> "graph-io"
        pkg:org/repo/sub/graph-io    -> "graph-io"
        cls:graph_io.store.GraphNotInitializedError
                                     -> "GraphNotInitializedError"

    The slug is returned verbatim (no extra slugify pass). Callers that
    want filename-safe output may pass through `wiki_io.ingest_source.slugify`
    afterward; today's URIs from `packages.refresh` are already filename-safe.
    """
    if not uri:
        raise ValueError("uri must be non-empty")
    # URI shape: scheme:authority/segment/.../tail OR scheme:tail
    tail = uri.rsplit("/", 1)[-1]
    tail = tail.rsplit(":", 1)[-1]  # handle scheme-only URIs (cls:Name)
    if not tail:
        raise ValueError(f"could not derive slug from uri: {uri!r}")
    return tail
```

**Why this minimal scope:** Phase 39 D-03 says "last URI segment + graph node attrs for routing prefix." Phase 40's existing `_route_target_path` ALREADY handles the prefix. So the only shared piece is the URI-tail extraction. Keep it small; extract more only if Phase 39 grows a need.

**Phase 39 coupling:** Phase 39 does not call `slug_from_uri` today (it uses `_wiki_relative_path_for` with a dict). A future refactor MAY route Phase 39 through this helper too, but Phase 40 does not block on that. Document the future-consolidation intent in a docstring or `# TODO(Phase 39 refactor):` comment if useful.

### 4.3 Re-slugify for filename safety

`wiki_io.ingest_source.slugify` already exists and is applied to the LLM-guessed slug (`ingest.py:485`). For the canonical URI-derived slug, recommend NOT re-slugifying: the URI was generated by `packages.refresh` and is already filename-safe per the schema invariants. Re-slugifying would be defensive but could lossy-transform legitimate URI tails (e.g. dots in `class.method` style URIs). Recommend pass-through; document the assumption.

If conservative, you can apply `slugify` defensively — it's idempotent for already-safe strings.

## 5. Frontmatter Write (D-05, D-06)

### 5.1 Position of the field

Per CONTEXT specifics: "add `entity_uri` immediately after `target_slug` in the page frontmatter."

The existing `_rewrite_target_slug_in_body` function rewrites the `target_slug:` line in the LLM output's frontmatter. Phase 40 extends it (or adds a sibling function) to ALSO write `entity_uri`. Two design choices:

1. **Extend `_rewrite_target_slug_in_body` to take an optional `entity_uri` arg.** Pros: one pass over the frontmatter; reuses the YAML-aware parsing. Cons: function name doesn't match what it does anymore.
2. **Add a sibling `_set_entity_uri_in_body(text, entity_uri)`** that operates on the same frontmatter block. Pros: single responsibility per function. Cons: two passes.

**Recommendation:** option (2). Keep `_rewrite_target_slug_in_body` unchanged. Add `_set_entity_uri_in_body(text, entity_uri: str | None)` that:
- Finds the frontmatter block (same algorithm as `_rewrite_target_slug_in_body`).
- Removes any existing `entity_uri:` line.
- Inserts `entity_uri: <value>` immediately after the `target_slug:` line, or as the last line of the frontmatter block if `target_slug:` is absent.
- Accepts `entity_uri=None` → emits `entity_uri: null` (D-05).

### 5.2 Existing pages with no entity_uri field

Per CONTEXT Claude's Discretion: "Suggest: write the field on every successful ingest (overwrites stale values)." Adopt this — the ingestor always writes the field, with value `null` when no graph match.

## 6. IngestResult Dataclass Update

CONTEXT code_context suggests adding `entity_uri: str | None = None` to `IngestResult`. This is a low-risk additive change:

```python
@dataclass
class IngestResult:
    status: str
    page_path: str
    slug: str
    title: str
    page_type: str
    source_path: str
    cross_refs_updated: int
    entity_uri: str | None = None  # Phase 40: canonical entity URI, None for free-form sources
```

All existing callers construct `IngestResult` with positional args (e.g. `IngestResult(status="ok", ...)`)— adding a field with a default value at the end is non-breaking.

**MCP surface:** `WikiIngestOutput` (Pydantic) currently mirrors the IngestResult fields. Mirror the change: add `entity_uri: str | None = None`. Test snapshot updates expected.

## 7. URI-Drift Documentation (D-07, D-08)

### 7.1 Code comment placement

Per CONTEXT specifics, the code comment goes "near the graph-lookup site" in `commands/ingest.py`. Suggested text:

```python
# URI-drift limitation (INGESTOR-03 / Phase 40):
#
# When a package is renamed in the source repo, the `entity_uri` recorded in
# existing ingested pages becomes orphaned — it still points at the old URI
# even though the graph now uses the new one. Phase 40 does NOT automatically
# migrate orphaned URIs; this is tracked as a v1.8 reconciliation item.
#
# Surfaces: grep -r "entity_uri: pkg:" wiki/ will find all entity-backed pages;
# a v1.8 tool may parse + reconcile against the live graph.
```

Place this comment just above the `_lookup_entity_by_path` call site inside `run_ingest_source`.

### 7.2 Plan-level section

PLAN.md gets a dedicated `## v1.8 Reconciliation` section that re-states the limitation in milestone-planning language (one paragraph, no v1.8 design speculation).

## 8. Connection Lifetime (Claude's Discretion → confirmed)

Open `read_only_connect(graph_dir(workspace) / "code.db")` once, immediately after `resolve_wiki_and_repo`. Wrap the entire pipeline in `try` / `finally`; close the conn in `finally`. This mirrors Phase 37 D-03 / Phase 39 D-05 exactly.

## 9. run_ingest_work_item — Out of Scope (Claude's Discretion → confirmed)

`run_ingest_work_item` accepts user-authored frontmatter + body and files into `<workspace>/work/`. Work items are NOT derived from source files — they are tickets/notes that bypass the source-type guessing pipeline entirely. There is no entity-existence question to ask the graph; the work item's identity is its own slug.

**Decision: leave `run_ingest_work_item` unchanged.** Document the rationale in the plan.

## 10. MCP wiki_ingest Tool Surface (Claude's Discretion)

Per CONTEXT, surfacing `entity_uri` in `WikiIngestOutput` is "natural; planner picks whether to include in this phase or defer."

**Recommendation: include in this phase.** It's a one-line additive change to a Pydantic model and matches the IngestResult dataclass change. Skipping it would create a brief observability gap. Snapshot tests for the MCP schema (`test_mcp_schema_forbid_extra.py`, etc.) will require updates.

## 11. Test Strategy

CONTEXT specifies a minimum:
- One test: path-matching source → slug-override + `entity_uri: pkg:...` frontmatter written.
- One test: no match → LLM-guessed slug + `entity_uri: null` frontmatter.

Recommended expansion (still tight):

| Test | Asserts |
|------|---------|
| `test_run_ingest_source_not_initialized_exits_with_code_3` | When graph DB is missing, the CLI command exits with code 3 AND stderr contains the D-02 message |
| `test_run_ingest_source_path_match_overrides_slug` | When source path matches a graph package's file, the LLM-guessed slug is replaced with the URI-tail; frontmatter `entity_uri:` contains the matched URI |
| `test_run_ingest_source_name_fallback_overrides_slug` | When the path lookup misses but the LLM-guessed title matches a graph node by name, the URI-derived slug is used; frontmatter `entity_uri:` set |
| `test_run_ingest_source_no_match_writes_null_entity_uri` | No path nor name match → LLM-guessed slug used; frontmatter `entity_uri: null` |
| `test_run_ingest_source_multi_match_falls_back_to_no_match` | Name lookup returns ≥2 matches → stderr warning emitted; behavior == no-match (slug = LLM-guessed, `entity_uri: null`) |
| `test_run_ingest_source_closes_conn_on_exception` | Patch `make_llm` to raise; verify the read-only conn `.close()` is called |
| `test_slug_from_uri_unit` | Unit test for the new helper across happy/error inputs |
| `test_set_entity_uri_in_body_unit` | Unit test the frontmatter rewriter — placement after `target_slug:`, null handling, idempotence |

### 11.1 Fixtures

Reuse `seeded_graph_conn` (already in `agents/graph-wiki-agent/tests/conftest.py`) and the cross-package `sample_monorepo` fixture for graph-side seeding. For path-match tests, copy the seeded DB to the test workspace's `.graph/code.db` so `read_only_connect()` finds it.

### 11.2 LLM mocking

Existing pattern in `test_commands_ingest.py`:

```python
with (
    patch("graph_wiki_agent.commands.ingest.resolve_wiki_and_repo") as mock_resolve,
    patch("graph_wiki_agent.commands.ingest.make_llm") as mock_make_llm,
    patch("graph_wiki_agent.commands.ingest.update_index") as mock_update_index,
    patch("graph_wiki_agent.commands.ingest.append_log") as mock_append_log,
):
    mock_resolve.return_value = (wiki, tmp_path)
    fake_llm = MagicMock()
    fake_llm.ainvoke = AsyncMock(return_value=MagicMock(content=fake_llm_response))
    mock_make_llm.return_value = fake_llm
    result = await run_ingest_source(source_file, wiki)
```

Carry forward this pattern. Add a fixture to seed a tiny graph DB at `<workspace>/.graph/code.db` so the conn open succeeds.

## 12. Validation Architecture

Per Nyquist Dimension 8 — the phase's behavioral truth statements must be testable at the appropriate sampling rate. For Phase 40:

| Behavioral truth | Test type | Sampling |
|------------------|-----------|----------|
| Missing graph DB → exit code 3 + stderr message | Unit (CLI-level + run-level) | 1 (deterministic) |
| Path-match overrides slug + writes URI frontmatter | Unit | 1 |
| Name-fallback overrides slug + writes URI frontmatter | Unit | 1 |
| No match → LLM slug + null frontmatter | Unit | 1 |
| Multi-match → stderr warning + no-match path | Unit | 1 |
| Conn closed on exception | Unit | 1 |
| `entity_uri` frontmatter placed after `target_slug:` | Unit (rewriter) | 3+ (with/without target_slug, with null) |

These are deterministic over fixture DBs — no LLM call sampling needed (LLM is mocked). Phase 40 produces no Bedrock-cost-sensitive behavior; eval-harness coverage is not required for this phase.

## 13. Open Questions Resolved

| Question | Resolution |
|----------|------------|
| Where does the URI → slug helper live? | New module `agents/graph-wiki-agent/src/graph_wiki_agent/uri_slug.py`. Single function `slug_from_uri`. |
| Does `run_ingest_work_item` need graph consultation? | No. It bypasses source-type detection entirely. Out of scope. |
| Does MCP `wiki_ingest` surface `entity_uri`? | Yes — additive one-line change to `WikiIngestOutput`. |
| What happens when path is outside the repo? | `relative_to` raises `ValueError` → return None → fall through to name lookup. |
| What if URI in attrs_json is empty/missing? | Treat as no match — fall through. |
| Re-slugify the URI-derived slug? | No (pass-through). URIs are already filename-safe by schema invariant. Document the assumption. |

## 14. Files Touched (Estimate)

| File | Type | Lines (est) |
|------|------|-------------|
| `agents/graph-wiki-agent/src/graph_wiki_agent/uri_slug.py` | NEW | ~30 |
| `agents/graph-wiki-agent/src/graph_wiki_agent/commands/ingest.py` | MODIFIED | ~80 added (lookup helper, conn open, override logic, frontmatter writer, error path) |
| `agents/graph-wiki-agent/src/graph_wiki_agent/cli.py` | MODIFIED | ~5 (catch `IngestorGraphNotInitializedError`, exit code 3) |
| `agents/graph-wiki-agent/src/graph_wiki_agent/mcp/server.py` | MODIFIED | ~1 (add `entity_uri` to `WikiIngestOutput`) |
| `agents/graph-wiki-agent/tests/unit/test_commands_ingest.py` | MODIFIED | ~150 (add 5+ new tests) |
| `agents/graph-wiki-agent/tests/unit/test_uri_slug.py` | NEW | ~30 |
| `agents/graph-wiki-agent/tests/unit/__snapshots__/*` | MODIFIED | snapshot updates for MCP schema |

## 15. Risks

| Risk | Mitigation |
|------|------------|
| Phase 39 has not merged when Phase 40 executes; the URI-slug helper coupling is forward-only | Phase 40 creates `uri_slug.py` standalone — no dependency on Phase 39 source. Phase 39 can adopt it later. |
| `graph_dir()` returns `.graph/` but some older artifacts use `.graph-wiki/graph/` | Confirmed: `workspace_io.paths.graph_dir` returns `<workspace>/.graph`. All graph-io CLI commands resolve `code.db` as `graph_dir(workspace) / "code.db"`. Phase 40 uses the same. |
| Snapshot test failures from `WikiIngestOutput` schema change | Update snapshots; verify the change is additive (existing fields unchanged). |
| `_lookup_entity_by_path` SQL relies on `path` column matching the file path verbatim — case sensitivity, relative vs absolute | Always resolve `source_path` to absolute then take `.relative_to(repo_root)` and `.as_posix()`. The graph stores POSIX-relative paths from repo root (verify in Phase 30+ schema docs). |
| URI in `attrs_json` may be absent for some node kinds | Helper returns `None` on missing URI; falls through to name lookup or no-match path. |

## 16. References

- `agents/graph-wiki-agent/src/graph_wiki_agent/commands/ingest.py:369-533` — modification site
- `agents/graph-wiki-agent/src/graph_wiki_agent/commands/ingest.py:54-79` — `IngestResult` dataclass
- `agents/graph-wiki-agent/src/graph_wiki_agent/commands/ingest.py:93-148` — `_route_target_path` + `_rewrite_target_slug_in_body`
- `packages/graph-io/src/graph_io/exit_codes.py:8` — `NOT_INITIALIZED = 3`
- `packages/graph-io/src/graph_io/store.py:13-15,68-81` — `GraphNotInitializedError` + `read_only_connect`
- `packages/graph-io/src/graph_io/queries.py:166-225` — `find()` primitive
- `packages/graph-io/src/graph_io/queries.py:369-414` — `describe_path()` (returns file children, not package)
- `packages/workspace-io/src/workspace_io/paths.py:31` — `graph_dir`
- `agents/graph-wiki-agent/tests/conftest.py:96` — `seeded_graph_conn` fixture
- `agents/graph-wiki-agent/tests/unit/test_commands_ingest.py` — existing ingest test patterns

## RESEARCH COMPLETE

Phase 40 implementation is unambiguous. Key resolved items:
- NOT_INITIALIZED via `GraphNotInitializedError` catch → exit code 3 (D-01/D-02).
- Path lookup: SQL join `file → contains → package`; name fallback: `queries.find` filtered to entity kinds (D-03).
- New module `uri_slug.py` with `slug_from_uri(uri)` — minimal shared helper Phase 39 can adopt later (D-04).
- Frontmatter write: new `_set_entity_uri_in_body` rewriter, placed after `target_slug:` (D-05/D-06).
- IngestResult + WikiIngestOutput gain `entity_uri: str | None = None`.
- URI-drift code comment + plan section as locked (D-07/D-08).
