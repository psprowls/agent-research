# Phase 48: `graph propose-domains` - Context

**Gathered:** 2026-05-27
**Status:** Ready for planning

<domain>
## Phase Boundary

Add an LLM-proposal layer on top of Phase 47's `cg domain-clusters`. The new `graph-wiki-agent graph propose-domains` Typer subcommand:

1. Runs `cg domain-clusters` internally (subprocess or in-process call) to get a `ClusterResult`.
2. Loads per-package describe context (name + summary + file_map) for each cluster's members.
3. Fans out one LLM call per cluster via `SubagentPool` using a `propose_domain` tool-use schema (Bedrock Converse).
4. Aggregates results into a `proposed_domains:` structure.
5. Adds a mechanical `cross-cutting` proposed domain containing Phase 47's hub list (no LLM call for this one).
6. Grounds: strips any proposed package name not in `graph_io.queries.list_packages` with a logged warning.
7. Cycle-detects: builds the union of proposed `parent` edges + existing `domains.yaml` parent edges, strips proposed edges that introduce cycles.
8. Writes `domains.proposed.yaml` (top-level key `proposed_domains:`) to the workspace root.
9. Writes per-LLM-call cost records to `.graph-wiki/traces/` matching the v1.7 trace schema.

**Code surface added:**
- `agents/graph-wiki-agent/src/graph_wiki_agent/commands/propose_domains.py` — new module containing the Typer command + orchestration logic.
- `agents/graph-wiki-agent/models.toml` (or wherever roles are defined) — new `domain-proposer` role (separate from `scanner` and `narrator` to allow independent tuning).
- `agents/graph-wiki-agent/src/graph_wiki_agent/commands/graph.py` — register `propose-domains` subcommand under the existing `graph_app` Typer subapp (small edit; mirrors `graph build`, `graph describe ...` registrations).
- `agents/graph-wiki-agent/tests/test_propose_domains.py` — unit + integration tests including PROPOSE-05 isolation guard.

**Code surface NOT modified:**
- `packages/graph-io/` — read-only consumer (uses `list_packages`, `cg domain-clusters` CLI). NO schema changes.
- `packages/graph-io/src/graph_io/packages.py::refresh` — the allowlist that excludes `domains.proposed.yaml` per PROPOSE-05 is verified to already do this OR the planner adds it as a tiny edit if needed. (Research must confirm.)
- `domains.yaml` — existing authoritative config is read-only input.

**Independence from 42-46.** Phase 48 lives in agents/graph-wiki-agent. Its only hard runtime dependency is Phase 47 (`cg domain-clusters`). Can ship as soon as Phase 47 lands; doesn't block on the wiki-entity-restructure work.

**Not in scope (Phase 48):**
- Auto-applying proposals to `domains.yaml` — explicitly rejected by PROPOSE-04 schema differentiation.
- Iterative refinement loop with user (interactive review TUI) — single-shot proposal only; user reviews + edits + renames file to `domains.yaml` manually.
- Multi-shot LLM with chain-of-thought / self-critique — single tool-use call per cluster.
- Updating existing `domains.yaml` proposals already on disk — `domains.proposed.yaml` is overwritten on each invocation.
- v1.9 work: package_family proposals, sub-domain hierarchy proposals beyond a single parent edge.

</domain>

<decisions>
## Implementation Decisions

### Fan-out + LLM input

- **D-01:** **Per-cluster fan-out via `SubagentPool`.** One LLM call per cluster from `ClusterResult.clusters`. Concurrency-bounded; partial-success on per-cluster failure (one bad cluster doesn't abort the whole pass). Cost scales linearly with cluster count (~3–10 calls at v1.8 vault scale).

- **D-02:** **Per-package context = name + summary + file_map.** For each package in a cluster, the LLM prompt includes:
  - Package name (e.g., `graph-io`).
  - One-line summary from the package's wiki frontmatter (`summary:` field) OR the first sentence of the package's wiki page; OR `<no summary available>` if neither exists.
  - File map (`build_file_map(pkg_dir)` from `wiki_io` — same helper the scanner uses for stub generation).
  
  Approximate token cost: 500–1500 per package. A cluster of 5 packages → ~5,000 token prompt. Well within Bedrock Claude limits.

- **D-03:** **Cluster prompt also includes 'hubs used' annotation.** From Phase 47's `CrossCuttingHub.connects_clusters`: enumerate the hubs whose `connects_clusters` includes the current cluster's id; list them in a `## Cross-cutting hubs this cluster uses` section. Hubs are NOT in the cluster's `packages` list — they're context for naming/description signal. (Hubs are aggregated separately into the `cross-cutting` domain per D-05.)

- **D-04:** **Domain-proposal prompt skeleton (planner refines wording):**
  ```
  You are proposing a name and description for a candidate domain in a Python monorepo.
  
  The domain candidate contains these packages:
  
  - <pkg-1>: <summary>
    File map:
    <file_map>
  
  - <pkg-2>: ...
  
  Cross-cutting hubs this cluster uses:
  - pytest (imported by 86% of packages)
  - click (imported by 57% of packages)
  
  Optionally, you may propose a parent domain (one of: <existing_domain_names>).
  
  Use the propose_domain tool to return your proposal.
  ```
  `<existing_domain_names>` lists domain names from the existing `domains.yaml` (so the LLM can pick a parent from real options, not hallucinate).

### LLM output schema

- **D-05:** **Bedrock tool-use with strict JSON schema.** Define a `propose_domain` tool:
  ```python
  TOOL_SCHEMA = {
      "name": "propose_domain",
      "description": "Propose a name, parent, and description for the candidate domain.",
      "input_schema": {
          "type": "object",
          "properties": {
              "name": {"type": "string", "description": "lowercase, kebab-case, 1-3 words"},
              "packages": {
                  "type": "array",
                  "items": {"type": "string"},
                  "description": "subset of input packages that belong to this proposed domain (may exclude some if they don't fit)"
              },
              "parent": {"type": ["string", "null"], "description": "name of parent domain from <existing_domain_names>, or null"},
              "description": {"type": "string", "description": "one-sentence description (~15-25 words)"},
              "confidence": {"type": "number", "description": "0.0-1.0 self-rated confidence"}
          },
          "required": ["name", "packages", "description", "confidence"]
      }
  }
  ```
  langchain-aws's `ChatBedrockConverse.bind_tools([tool])` returns a runnable that forces the LLM to call the tool. Parsed via `response.tool_calls[0]["args"]`. Zero parse-failure risk.

- **D-06:** **Aggregation into `ProposedDomains` dataclass:**
  ```python
  @dataclass(frozen=True)
  class ProposedDomain:
      name: str
      packages: tuple[str, ...]    # sorted
      parent: str | None
      description: str
      confidence: float
      llm_origin: str              # "fan_out" or "cross_cutting"
  
  @dataclass(frozen=True)
  class ProposeResult:
      proposed_domains: tuple[ProposedDomain, ...]  # sorted by name
      stripped_unknown_packages: tuple[str, ...]    # PROPOSE-02 strips
      stripped_cycle_edges: tuple[tuple[str, str], ...]  # PROPOSE-03 strips (child, parent)
      llm_failures: tuple[str, ...]                  # cluster ids whose LLM call failed
      total_cost_usd: float                          # PROPOSE-06 aggregated cost
  ```

### Cross-cutting hub treatment

- **D-07:** **Mechanical `cross-cutting` proposed domain.** Phase 48 builds this entry without an LLM call:
  ```yaml
  cross-cutting:
    packages: [click, pytest, ...]  # from ClusterResult.cross_cutting
    description: "Cross-cutting utility packages imported by multiple domains. Generated mechanically from cg domain-clusters hub detection."
    parent: null
    confidence: 1.0  # mechanical, not LLM-derived
  ```
  Origin in `ProposedDomain.llm_origin = "cross_cutting"`.

- **D-08:** **Name `cross-cutting` is fixed.** Not configurable. Chosen for accuracy (matches Phase 47 terminology) and clarity for downstream human review.

### Grounding + cycle detection

- **D-09:** **Grounding = validate against `list_packages` only.** Before writing `domains.proposed.yaml`:
  1. Load `valid_packages = set(node.name for node in list_packages(conn))`.
  2. For each `ProposedDomain.packages`, filter to only packages in `valid_packages`.
  3. Removed package names accumulate in `ProposeResult.stripped_unknown_packages`.
  4. Log to stderr: `warning: stripping unknown package '<name>' proposed for domain '<domain_name>' — not in list_packages output`.
  
  An LLM may propose packages already in `domains.yaml` (existing-domain members). Those are NOT stripped — the user reviews `domains.proposed.yaml` and decides whether the LLM's suggested move is good. No code-level conflict resolution.

- **D-10:** **Cycle detection scope = proposed + existing `domains.yaml` parent edges unioned.**
  1. Load existing `domains.yaml`; build `existing_edges = [(child, parent) for child, info in domains.items() if info.get('parent')]`.
  2. Build `proposed_edges = [(d.name, d.parent) for d in proposed_domains if d.parent]`.
  3. Build directed graph: `all_edges = existing_edges + proposed_edges`.
  4. Run DFS with grey/black coloring (no networkx dep): visit each node, mark grey on entry, mark black on exit; an edge to a grey node = back-edge = cycle.
  5. When a cycle is detected, identify the FIRST proposed edge on the cycle path (existing edges are immune) and strip it from `proposed_edges`. Restart cycle check.
  6. Repeat until no cycles. Stripped edges accumulate in `ProposeResult.stripped_cycle_edges`.
  7. Log to stderr per stripped edge: `warning: stripping cycle-introducing parent edge: '<child>' -> '<parent>'`.

- **D-11:** **Existing-edge immunity rationale.** `domains.yaml` is the authoritative config; if it contains a cycle, that's a pre-existing bug and not Phase 48's problem. Phase 48 only refuses to introduce NEW cycles via its proposals.

- **D-12:** **Cycle-detection algorithm = iterative DFS** (not recursive — Python's recursion limit caps at ~1000; domain hierarchies are tiny but iterative DFS is the safer pattern). ~40 LOC including the strip-and-restart loop.

### Output file shape (PROPOSE-04)

- **D-13:** **File path = `<workspace>/domains.proposed.yaml`.** Same directory as `domains.yaml`. Workspace root (the directory containing `.graph-wiki.yaml`).

- **D-14:** **Top-level YAML key = `proposed_domains:`.** Differentiates from `domains:` (the structure used inside domains.yaml) — schema-level prevention of accidental parsing as authoritative. Format:
  ```yaml
  proposed_domains:
    cross-cutting:
      packages: [click, pytest]
      description: "Cross-cutting utility packages imported by multiple domains."
      parent: null
      confidence: 1.0
      llm_origin: cross_cutting
    graph-io:
      packages: [graph-io, wiki-io, model-adapter]
      description: "Graph ingestion and wiki I/O packages."
      parent: null
      confidence: 0.85
      llm_origin: fan_out
    ...
  metadata:
    generated_at: 2026-05-27T18:00:00Z
    cluster_command: "cg domain-clusters --hub-threshold 0.5"
    model: claude-3-5-sonnet-20241022
    total_cost_usd: 0.034
    stripped_unknown_packages: [foo, bar]
    stripped_cycle_edges:
      - [child-domain, parent-domain]
    llm_failures: []
  ```
  `metadata:` block surfaces costs + warnings without contaminating the proposal data.

- **D-15:** **YAML write via `yaml.safe_dump(data, sort_keys=True, default_flow_style=False)`.** Deterministic output. `sort_keys=True` so proposed domains sort alphabetically by name (matches `ProposeResult.proposed_domains` already sorted). Inline lists for `packages:` arrays (use `default_flow_style=None` for hybrid emission, or coerce specific fields to flow style).

- **D-16:** **Overwrite on each invocation.** No append, no merge. The user is expected to review and either (a) discard, (b) cherry-pick into `domains.yaml`, or (c) rename the whole file. Idempotency from the LLM-call angle is not guaranteed (LLM is nondeterministic) — running twice may produce different proposed names. That's acceptable for a human-review artifact.

### Isolation guard (PROPOSE-05)

- **D-17:** **`graph_io.packages.refresh` allowlist verification.** Phase 48 plan includes a Research step that confirms the current allowlist in `packages.refresh` excludes `domains.proposed.yaml` — either by explicit allowlist (only specific filenames considered) or via a `.proposed.yaml` suffix exclusion pattern. If not already excluded, Phase 48 adds the exclusion as a small edit. (Research confirms the exact form.)

- **D-18:** **Isolation test (PROPOSE-05 acceptance).** End-to-end test:
  1. Initialize a fresh workspace; run `cg update`.
  2. Run `graph propose-domains`; verify `domains.proposed.yaml` is written.
  3. Run `cg update` again.
  4. Run `cg list-domains` (or query the graph for `belongs_to_domain` edges).
  5. Assert: zero domain edges from `domains.proposed.yaml` exist in the graph. Only edges from `domains.yaml` (the authoritative file) are present.
  
  Belt-and-suspenders: also test by-content (write a `proposed_domains:` block with a unique fake package name; assert that name never appears in `belongs_to_domain` edges after re-ingestion).

### LLM role + cost tracking (PROPOSE-06)

- **D-19:** **New `domain-proposer` role in models.toml.** Distinct from `scanner` and `narrator` so:
  - Cost can be tracked per role in traces.
  - Model can be tuned independently (e.g., use a stronger model for proposal, cheaper for narrator).
  - `--model` flag (PROPOSE-06) routes through `model_adapter.make_llm("domain-proposer", model_override=...)`.
  
  Initial config: same model as `scanner` for v1.8; revisit in v1.9 eval.

- **D-20:** **Cost record per LLM call written to `.graph-wiki/traces/<timestamp>-propose-domains.jsonl`.** One JSON line per cluster call + one for any retry. Schema mirrors v1.7 trace shape (existing pattern in `commands/graph.py::_write_trace_record`):
  ```json
  {
    "command": "graph propose-domains",
    "role": "domain-proposer",
    "model": "claude-3-5-sonnet-20241022",
    "cluster_id": 0,
    "cluster_name": "graph-io",
    "timestamp": "...",
    "input_tokens": 4823,
    "output_tokens": 187,
    "cost_usd": 0.0192,
    "tool_call": {"name": "propose_domain", "args": {...}}
  }
  ```
  Aggregated `total_cost_usd` in `ProposeResult` is the sum of per-call costs. Surfaced in the `metadata:` block of `domains.proposed.yaml` (D-14).

- **D-21:** **`--model` flag passed through to `make_llm`.** CLI signature:
  ```python
  @graph_app.command(name="propose-domains")
  def propose_domains_cmd(
      workspace: str = typer.Option(...),
      hub_threshold: float = typer.Option(0.5),
      model: Optional[str] = typer.Option(None, "--model"),
  ) -> None:
      ...
  ```
  `--hub-threshold` is forwarded to `cg domain-clusters`. `--model` is forwarded to `make_llm("domain-proposer", model_override=model)`.

### CLI integration

- **D-22:** **Subcommand registration in `commands/graph.py`.** Add `@graph_app.command(name="propose-domains")` decorator + handler function alongside existing `graph build`, `graph describe ...` commands. Mirrors `q_cross_cutting.py`-style error handling (`GraphNotInitializedError`, `SchemaMismatchError` → standard exit codes).

- **D-23:** **Invoke `cg domain-clusters` in-process, not subprocess.** Import `graph_io.cluster.compute_clusters` directly. Avoids subprocess overhead and stdout-parsing fragility. The JSON output format defined by Phase 47 is the IPC contract on disk; in-process call returns `ClusterResult` directly. Cleaner integration.

### Module structure

- **D-24:** **`propose_domains.py` contents:**
  - Public Typer command function (registered in `graph.py`).
  - Dataclasses: `ProposedDomain`, `ProposeResult` (D-06).
  - Tool schema: `_PROPOSE_DOMAIN_TOOL` (D-05).
  - Async fan-out helper: `_propose_for_cluster(cluster, context_loader, llm, existing_domains) -> ProposedDomain | None`.
  - Cycle detection: `_strip_cycle_edges(proposed_edges, existing_edges) -> tuple[edges_kept, edges_stripped]`.
  - Grounding: `_strip_unknown_packages(proposed_domains, valid_packages) -> tuple[domains_filtered, stripped_names]`.
  - YAML writer: `_write_proposed_yaml(result, output_path, metadata)`.
  - Cross-cutting builder: `_build_cross_cutting_domain(cross_cutting_hubs) -> ProposedDomain`.
  - Trace writer: reuses `commands/graph.py::_write_trace_record` (passes through `role="domain-proposer"`).

- **D-25:** **No new third-party dependencies.** `yaml.safe_dump` (already in use), `langchain-aws` tool-use (already in use), `dataclasses` (stdlib), `pathlib` (stdlib). `model_adapter`, `subagent_runtime` already workspace members.

### Claude's discretion

- Exact prompt wording for `propose_domain` (D-04 is a sketch; planner iterates).
- Whether to retry an LLM call on transient errors (lean: yes, up to 2 retries via SubagentPool's existing retry config).
- Whether `confidence` from LLM is exposed in YAML (lean: yes; useful signal for human review).
- Whether to include cluster `id` from Phase 47 in the YAML output (lean: no; the cluster id is an internal Phase-47 detail).
- Whether to support a `--no-trace` flag (lean: no; traces are cheap and always useful).
- Whether to write the YAML with a banner comment (`# Generated by graph-wiki-agent graph propose-domains. Review before promoting to domains.yaml.`) — lean: yes.
- Whether `_build_cross_cutting_domain` produces a domain even when `cross_cutting` is empty (lean: skip if empty).
- Whether grounding strips a whole domain when ALL its packages are stripped (lean: yes; empty domain is meaningless).

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Direct predecessor
- `.planning/phases/47-cg-domain-clusters/47-CONTEXT.md` — `ClusterResult` shape (D-07). Phase 48's input contract. Treat the JSON schema as a contract: Phase 48 imports `compute_clusters` directly (D-23) rather than parsing JSON, but the dataclass field names + types are the same.
- `.planning/phases/47-cg-domain-clusters/47-01-PLAN.md` / `47-02-PLAN.md` / `47-03-PLAN.md` — Phase 47's implementation plans; Phase 48's research must verify Phase 47's actual code shape matches CONTEXT.md's design (re-check at planning time if Phase 47 has executed).

### Milestone-level
- `.planning/REQUIREMENTS.md` §PROPOSE — PROPOSE-01..PROPOSE-06.
- `.planning/ROADMAP.md` Phase 48 — Goal + 5 success criteria.
- `.planning/STATE.md` — Pitfall 7 (LLM hallucination — addressed by D-05 tool-use + D-09 grounding), Pitfall 8 (auto-apply — addressed by D-14 schema differentiation + D-17/D-18 isolation guard).

### Existing code (must be read by planner/researcher)
- `agents/graph-wiki-agent/src/graph_wiki_agent/commands/graph.py` — `graph_app` Typer subapp + `_write_trace_record` + existing `graph build` / `graph describe ...` patterns. Phase 48 adds `propose-domains` here.
- `agents/graph-wiki-agent/src/graph_wiki_agent/commands/scan.py` — Reference for `SubagentPool` usage, `make_llm` calls, trace writing. Phase 48 mirrors the same shape with role `domain-proposer`.
- `packages/model-adapter/src/model_adapter/loader.py` — `make_llm(role, model_override=...)` signature. Verify the `model_override` parameter name and shape.
- `packages/subagent-runtime/src/subagent_runtime/pool.py` — `SubagentPool.run_all` shape. Reused for Phase 48's per-cluster fan-out.
- `packages/graph-io/src/graph_io/cluster.py` (post-Phase 47) — `compute_clusters`, `ClusterResult`, `Cluster`, `CrossCuttingHub`. Phase 48 imports directly (D-23).
- `packages/graph-io/src/graph_io/queries.py::list_packages` — Source for grounding validation set (D-09).
- `packages/graph-io/src/graph_io/packages.py::refresh` — PROPOSE-05 isolation guard verification target. Research must confirm allowlist + add exclusion if needed.
- `packages/wiki-io/src/wiki_io/...` — `build_file_map` helper (used by scanner for stub generation). Phase 48 reuses for D-02 per-package context.
- `domains.yaml` shape — `packages/graph-io/tests/fixtures/sample_monorepo/domains.yaml` is a working example.
- `.graph-wiki/traces/` v1.7 trace JSONL schema — Phase 16 / Phase 22 (per intel docs) for the trace record format. Phase 48 matches it.

### Research baseline
- `.planning/research/ARCHITECTURE.md` §graph-wiki-agent commands.
- `.planning/research/PITFALLS.md` Pitfall 7 (LLM hallucination — addressed by D-05 + D-09), Pitfall 8 (auto-apply — addressed by D-14 + D-17 + D-18).
- `.planning/research/FEATURES.md` §F10 (LLM domain proposal) if present.

### Tests (where new Phase 48 tests land)
- `agents/graph-wiki-agent/tests/test_propose_domains.py` (new) — unit tests for grounding, cycle detection, cross-cutting domain construction, YAML schema, tool-use parsing.
- `agents/graph-wiki-agent/tests/integration/test_propose_domains_isolation.py` (new) — PROPOSE-05 isolation acceptance.
- `agents/graph-wiki-agent/tests/integration/test_propose_domains_e2e.py` (new) — end-to-end run against agent-research itself (with mocked LLM responses to keep CI cheap; live-LLM variant gated on env flag).

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- **`graph_app` Typer subapp in `commands/graph.py`** — established pattern for `graph <subcommand>`. `@graph_app.command(name="propose-domains")` slots Phase 48 in naturally.
- **`commands/graph.py::_write_trace_record`** — trace-writing infrastructure; Phase 48 reuses by passing `command="graph propose-domains"` and `role="domain-proposer"`.
- **`commands/scan.py::SubagentPool` usage** — fan-out + concurrency + per-item error isolation. Same pattern for D-01.
- **`model_adapter.make_llm(role)`** — LLM construction with role-tier config. New `domain-proposer` role added; rest of the wiring exists.
- **`langchain-aws.ChatBedrockConverse.bind_tools([tool_schema])`** — tool-use API. Returns a runnable; LLM response includes `tool_calls` list. D-05 uses this directly.
- **`graph_io.queries.list_packages`** — already returns `list[NodeRecord]`; grounding set is `{n.name for n in records}`.
- **`graph_io.cluster.compute_clusters`** (post-Phase 47) — direct import, no subprocess.
- **`wiki_io.build_file_map`** (or equivalent) — reused for D-02 per-package context. Same helper the scanner uses.

### Established Patterns
- **CLAUDE.md §2 — `make_llm(role)` + `subagent_runtime.SubagentPool`.** Phase 48 follows the same composition pattern as scanner.
- **CLAUDE.md §8 — pytest + pytest-asyncio.** Phase 48 LLM calls are async (Bedrock Converse `ainvoke`); tests use the project's async conventions.
- **Frozen dataclasses with tuple collection fields** — Phase 43/44/45/47 precedent. `ProposedDomain` / `ProposeResult` follow the same shape.
- **Cost tracking via `response.usage_metadata`** — Phase 16-02 established this; trace records include the metadata. Phase 48 reuses without modification.
- **JSONL trace files in `.graph-wiki/traces/<timestamp>-<command>.jsonl`** — Phase 22 trace convention.

### Integration Points
- **In-process invocation of `compute_clusters` (D-23)** — Phase 48 does NOT shell out to `cg domain-clusters`. Imports the function. Avoids subprocess + stdout-parsing fragility.
- **`SubagentPool` retry config** — current scanner uses up to 2 retries on transient failures; Phase 48 inherits this.
- **Workspace root resolution via `workspace_io.paths`** — Phase 48 uses the same helpers as `cg` subcommands.
- **`domains.yaml` parser** — Phase 48 needs to LOAD existing `domains.yaml` to (a) extract parent edges for cycle check (D-10), (b) pass existing domain names as parent options to the LLM (D-04). Research confirms which module owns this parser (likely `graph_io.packages` or a sibling).

</code_context>

<specifics>
## Specific Ideas

- **Tool-use mock for tests.** Pytest fixture provides a stub `ChatBedrockConverse` whose `bind_tools` returns a runnable that immediately produces a canned tool-call response. Lets unit tests run without Bedrock credentials.
- **PROPOSE-05 acceptance test (D-18):** seed a workspace with `domains.yaml` (one domain `core: {packages: [foo]}`) and ingested packages `foo`, `bar`, `baz`. Write a `domains.proposed.yaml` that proposes `bar` and `baz` in a new domain `data`. Run `cg update`. Query `belongs_to_domain` edges. Assert ONLY `foo → core` exists; `bar → data` and `baz → data` are NOT present.
- **Cycle-detection unit test (D-10/D-12):** fixture proposed_edges `[(a, b), (b, c), (c, a)]` (cycle). Run strip. Assert one edge is removed (deterministic — first edge in cycle path is the one stripped). Run again on same input → byte-identical output (determinism).
- **Cycle with existing domains.yaml:** fixture existing_edges `[(a, b)]`, proposed_edges `[(b, a)]`. Run strip. Assert `(b, a)` is stripped (existing immune per D-11). Restart cycle check on remaining edges → no cycle.
- **Grounding test (D-09):** LLM proposes `bar`, `baz`, and `made_up`. `list_packages` returns `bar`, `baz` only. Assert: result contains `bar, baz`; `made_up` accumulates in `stripped_unknown_packages`; stderr has the warning line.
- **Cross-cutting domain construction (D-07):** fixture `cross_cutting = [click, pytest]`. Assert one ProposedDomain with name='cross-cutting', packages=('click', 'pytest'), confidence=1.0, llm_origin='cross_cutting'.
- **Cost aggregation:** mock 3 LLM calls returning input_tokens / output_tokens / cost per call. Assert `result.total_cost_usd` is the sum.
- **`--model` override:** invoke command with `--model bedrock-claude-haiku`. Assert the trace record has `model: bedrock-claude-haiku`.
- **Integration test against agent-research itself (with mocked LLM):** full pipeline; mock LLM to deterministic responses; assert `domains.proposed.yaml` is created, schema valid, isolation test passes.

</specifics>

<deferred>
## Deferred Ideas

- **Iterative refinement loop with self-critique** — LLM proposes, then critiques its own proposal, then revises. Higher quality at higher cost. Not in v1.8.
- **Interactive review TUI (`graph propose-domains --review`)** — text UI for the user to accept/reject each proposed domain inline. Not in v1.8; user reviews YAML manually.
- **Cross-cluster coherence pass** — after per-cluster fan-out, a final LLM call reviews ALL proposals together for consistency (naming conventions, parent suggestions). Hybrid strategy mentioned in Area 1 discussion; rejected for v1.8 (added LLM cost).
- **Confidence thresholding** — auto-skip proposals below a `--min-confidence` threshold. User can grep the YAML themselves; not in v1.8 CLI.
- **Domain merge suggestions** — LLM may suggest "these two clusters should be the same domain." Not in v1.8 schema; planner discretion to emit as a comment in YAML.
- **`graph adopt-proposed` command** — semi-automated promotion of `domains.proposed.yaml` to `domains.yaml`. Out of scope; user does it manually (a `cp` or merge).
- **package_family proposals** — Phase 42 dormant template / Phase 43 deferred. Phase 48 doesn't propose package_family entries. v1.9.
- **Sub-domain hierarchy beyond single parent** — proposed schema only supports `parent: <name>` (single parent). Multi-parent or graph hierarchies — v1.9 if needed.
- **Reading from `--cluster-snapshot FILE`** — pass a saved cluster JSON file instead of recomputing. Useful for repeated experimentation. v1.9.
- **Eval scaffolding for proposal quality** — deepeval-based eval comparing LLM proposals against a ground-truth domains.yaml. v1.9 separate phase.

</deferred>

---

*Phase: 48-`graph propose-domains`*
*Context gathered: 2026-05-27*
