# Phase 48 Research: `graph propose-domains`

**Researched:** 2026-05-27
**Goal:** Verify code surfaces and resolve open questions before planning.

## Scope of Research

CONTEXT.md (D-01 .. D-25) is exhaustive. Research only needs to verify:

1. Phase 47's actual `compute_clusters` surface matches the design contract.
2. PROPOSE-05 isolation guard state — does any code already touch `domains.proposed.yaml`?
3. Existing `graph_app` Typer registration pattern (file location + decorator form).
4. `make_llm` signature (does it accept `model_override`?).
5. `SubagentPool.run_all` shape (how cost trace records are produced).
6. `domains.yaml` loader location and parent-edge extraction shape.
7. `build_file_map` helper location.

## Findings

### F-1: Phase 47 `compute_clusters` surface (confirms D-23)

File: `packages/graph-io/src/graph_io/cluster.py`

Public API (frozen dataclasses + entry function):

```python
@dataclass(frozen=True)
class Cluster:
    id: int
    name: str
    members: tuple[str, ...]
    size: int

@dataclass(frozen=True)
class CrossCuttingHub:
    name: str
    imported_by_count: int
    imported_by_fraction: float
    connects_clusters: tuple[int, ...]

@dataclass(frozen=True)
class ClusterResult:
    hub_threshold: float
    n_packages_total: int
    degenerate_warning: str | None
    clusters: tuple[Cluster, ...]
    cross_cutting: tuple[CrossCuttingHub, ...]

def compute_clusters(
    conn: sqlite3.Connection,
    *,
    hub_threshold: float = 0.5,
) -> ClusterResult: ...
```

**Implications for Phase 48:**
- D-23 in-process call is valid: `from graph_io.cluster import compute_clusters`.
- D-03 hubs-used annotation: iterate `result.cross_cutting`; for each `CrossCuttingHub`, the `connects_clusters` tuple lists cluster ids that this hub bridges. The mapping `cluster_id -> [hubs_used]` is built by inverting that relation once per pass.
- D-07 cross-cutting mechanical domain: source `result.cross_cutting` directly; emit `[h.name for h in result.cross_cutting]`.
- The conn comes from `graph_io.store` (open the same way scanner does).

### F-2: PROPOSE-05 isolation guard state (RESOLVED — no edit needed)

File: `packages/graph-io/src/graph_io/domains.py`

`_load_domains_yaml(repo_root)` reads `repo_root / "domains.yaml"` by **literal filename**. Nothing else in `graph_io/` references the string `domains.proposed.yaml` or any `.proposed.yaml` suffix.

Grep confirmation (run as research evidence):
```
grep -rn "domains.proposed\|.proposed.yaml\|proposed_domains" packages/graph-io/src/graph_io/
# (no matches)
```

**Implication:** No allowlist edit is needed. PROPOSE-05 isolation is structurally guaranteed by `_load_domains_yaml`'s exact-filename match. Phase 48 only needs the **acceptance test** (D-18) to prove this stays true under future refactors. No code edit to `graph-io`.

### F-3: `graph_app` Typer registration pattern

File: `agents/graph-wiki-agent/src/graph_wiki_agent/commands/graph.py`

```python
graph_app = typer.Typer(
    name="graph",
    help="Code graph operations (build/describe/query) via in-process cg dispatch.",
    no_args_is_help=True,
)

@graph_app.command(name="build")
def graph_build_cmd(...) -> None: ...

@graph_app.command(name="query")
def graph_query_cmd(...) -> None: ...
```

**Implication for Phase 48:** Add `@graph_app.command(name="propose-domains")` in `commands/graph.py` or, per CONTEXT.md D-22/D-24, factor the body into a new module `commands/propose_domains.py` and register the command from there (preferred — keeps `graph.py` from growing further).

### F-4: `make_llm` signature

File: `packages/model-adapter/src/model_adapter/loader.py`

```python
def make_llm(role: str, *, model_override: str | None = None, ...) -> _GuardedChatBedrockConverse: ...
def load_role_config(role: str) -> dict: ...
```

(`load_role_config` returns `model_id`, `region`, `max_tokens`, `max_concurrency`.)

**Implication:** D-21 `--model` flag wires through `model_adapter.make_llm("domain-proposer", model_override=model)`. The role itself must exist in `models.toml` first (D-19).

### F-5: `SubagentPool.run_all` shape

File: `packages/subagent-runtime/src/subagent_runtime/pool.py`

```python
pool = SubagentPool(trace_dir=Path(".graph-wiki/traces"))

result: FanOutResult = await pool.run_all(
    items=[...],
    task=async_callable,                      # async (item) -> TaskResult
    role="domain-proposer",
    model_id="...",                           # for trace records
    max_concurrency=N,
)
# result.successes : list[(item, value)]
# result.errors    : list[FanOutError]
```

The pool calls `subagent_runtime.trace_io.write_trace_record(...)` internally for each task (extracting `usage_metadata` from `TaskResult.response`). **Phase 48 does NOT need to roll its own trace writer for the per-cluster LLM calls** — the pool handles D-20 cost records automatically as long as the task returns `TaskResult(value=..., response=resp)` where `resp` is the langchain-aws AIMessage.

### F-6: `domains.yaml` loader + parent edges

File: `packages/graph-io/src/graph_io/domains.py`

`_load_domains_yaml` is **module-private** (leading underscore). Phase 48 needs the same `domains.yaml` parsed for (a) parent-edge cycle baseline (D-10) and (b) existing domain names for the LLM prompt (D-04).

**Decision (Claude discretion):** Phase 48 reads `domains.yaml` directly with `yaml.safe_load` rather than importing the private helper. Keeps the dependency direction clean (graph-wiki-agent imports graph-io's *public* surface only). One additional ~10 LOC helper in `propose_domains.py`:

```python
def _load_existing_domains(workspace_root: Path) -> dict[str, dict]:
    """Parse domains.yaml from workspace_root; return {} if absent."""
    path = workspace_root / "domains.yaml"
    if not path.exists():
        return {}
    with path.open("r", encoding="utf-8") as f:
        data = yaml.safe_load(f) or {}
    return data.get("domains", {}) if isinstance(data, dict) else {}
```

Existing edges: `[(child_name, info["parent"]) for child_name, info in domains.items() if info.get("parent")]`.

### F-7: `build_file_map` helper location

File: `packages/wiki-io/src/wiki_io/...`

Grep:
```
grep -rn "def build_file_map" packages/wiki-io/src/
```

Phase 45 scanner uses `build_file_map(pkg_dir)` returning a multi-line tree string. The exact public path will be confirmed at implementation time; per F-6 logic, Phase 48 imports `from wiki_io import build_file_map` (or whatever its public re-export is). If `build_file_map` is internal to scanner, Phase 48 inlines a 10-line equivalent using `os.walk` + `pathlib`.

### F-8: Existing `graph build` `_write_trace_record` reuse

File: `agents/graph-wiki-agent/src/graph_wiki_agent/commands/graph.py`

`_write_trace_record(trace_path, event, command, args_dict, exit_code, duration_ms, *, model_id=None, extra=None)`

Phase 48 reuses this for the **command-level** trace event (`event="graph_propose_domains_start"` / `"graph_propose_domains_complete"`). The **per-cluster LLM cost records** are written by `SubagentPool` (F-5) — not by `_write_trace_record`. CONTEXT.md D-20 says "reuses `_write_trace_record`" — clarified here as command-level only.

## Validation Architecture

Phase 48's verification strategy spans three test classes:

### Layer 1 — Unit tests (`tests/test_propose_domains.py`)
- **Tool-schema parsing**: stub `ChatBedrockConverse` returns a canned tool-call → assert `ProposedDomain` is constructed correctly.
- **Cycle detection** (D-10, D-12): synthetic edge sets including pure-proposed cycles, mixed proposed+existing cycles, no-cycle case. Determinism check (run twice; byte-identical output).
- **Grounding** (D-09): proposal includes 3 packages, only 2 in `valid_packages` → assert third is stripped + stderr warning + accumulated in `stripped_unknown_packages`.
- **Cross-cutting builder** (D-07): given `ClusterResult.cross_cutting`, assert single `ProposedDomain` with name=`cross-cutting`, llm_origin=`cross_cutting`, confidence=1.0.
- **YAML schema** (D-14): write + reload; assert top-level key is `proposed_domains:` not `domains:`; `metadata:` block present with all expected fields.
- **Empty cross-cutting** (D-25 discretion): when `cross_cutting=()`, no `cross-cutting` domain is emitted.

### Layer 2 — Integration: PROPOSE-05 isolation (`tests/integration/test_propose_domains_isolation.py`)
- Seed workspace with `domains.yaml` declaring `core: {packages: [foo]}`.
- Ingest packages `foo`, `bar`, `baz` via `cg update`.
- Write `domains.proposed.yaml` declaring `data: {packages: [bar, baz]}` (manually, not via the LLM).
- Run `cg update` again.
- Query `belongs_to_domain` edges in the graph.
- **Assert:** only `foo -> core` exists; `bar -> data` and `baz -> data` are absent.
- **Belt-and-suspenders:** include a unique fake package name in `domains.proposed.yaml`; assert it never appears in any graph edge.

### Layer 3 — Integration: end-to-end (`tests/integration/test_propose_domains_e2e.py`)
- Stub LLM (no Bedrock credentials in CI) returns deterministic tool-call responses per cluster.
- Run `graph propose-domains --workspace <fixture>`.
- Assert: `<workspace>/domains.proposed.yaml` exists; schema valid; `metadata.total_cost_usd` is the sum of stub-reported costs; trace JSONL written to `.graph-wiki/traces/`.
- **Live-LLM variant** behind an env-flag gate (`GRAPH_WIKI_LIVE_BEDROCK=1`) for periodic real-credential smoke testing — not run in CI.

### Determinism / Nyquist
- Cycle-stripping algorithm is deterministic (sort `proposed_edges` lexicographically before DFS; strip the lexicographically-first edge on any cycle). Asserted by running twice on same input.
- YAML output uses `yaml.safe_dump(..., sort_keys=True, default_flow_style=False)`. Asserted by byte-comparing two writes of the same `ProposeResult`.
- LLM nondeterminism is acceptable per D-16; tests stub the LLM to remove it from the assertion surface.

## Pitfall Watch

- **Pitfall 7 (LLM hallucination):** Mitigated by D-05 tool-use schema (structurally cannot return unparseable text) + D-09 grounding (strips hallucinated package names).
- **Pitfall 8 (auto-apply):** Mitigated by D-14 `proposed_domains:` key (schema-level differentiation) + F-2 (the loader literally looks for `domains.yaml` only) + Layer 2 isolation test (proves no regression).
- **Hub list in cluster prompt vs in cluster packages:** Per D-03, hubs are in `## Cross-cutting hubs this cluster uses` context section only — they MUST NOT appear in `<pkg-N>: <summary>` bullet list for the cluster. Caught in unit test by asserting hub names do not appear in `ProposedDomain.packages` for non-cross-cutting domains.
- **`SubagentPool` partial-success:** A bad LLM call returns into `result.errors`. Phase 48 surfaces those in `ProposeResult.llm_failures` AND in `metadata.llm_failures` in the YAML. Test: stub one cluster to raise; assert the rest still produce proposals + `llm_failures` lists the failed cluster id.

## Open Questions (resolved during planning)

1. ~~Does `packages.refresh` need an exclusion edit for `domains.proposed.yaml`?~~ → **No** (F-2).
2. ~~Is `build_file_map` re-exported from `wiki_io`?~~ → Confirm at impl time; fallback to inline equivalent if internal.
3. Should the YAML banner comment be required? → Yes (D-25 discretion); first line of `domains.proposed.yaml` is:
   ```
   # Generated by graph-wiki-agent graph propose-domains. Review before promoting to domains.yaml.
   ```

## Files Phase 48 Will Touch

**New:**
- `agents/graph-wiki-agent/src/graph_wiki_agent/commands/propose_domains.py`
- `agents/graph-wiki-agent/tests/test_propose_domains.py`
- `agents/graph-wiki-agent/tests/integration/test_propose_domains_isolation.py`
- `agents/graph-wiki-agent/tests/integration/test_propose_domains_e2e.py`

**Edited:**
- `packages/model-adapter/src/model_adapter/models.toml` — add `[roles.domain-proposer]`.
- `agents/graph-wiki-agent/src/graph_wiki_agent/commands/graph.py` — register `propose-domains` subcommand (one-line `graph_app.add_typer(...)` or `@graph_app.command(...)` import from the new module).

**Read-only:**
- `packages/graph-io/src/graph_io/cluster.py` (import `compute_clusters`, dataclasses).
- `packages/graph-io/src/graph_io/queries.py` (import `list_packages`).
- `packages/wiki-io/...` (import `build_file_map`).
- `<workspace>/domains.yaml` (parse existing domains).

## RESEARCH COMPLETE
