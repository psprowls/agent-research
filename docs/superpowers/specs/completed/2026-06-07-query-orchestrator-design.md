# Query Orchestrator Design

Date: 2026-06-07
Status: implemented

## Goal

Make agentic query orchestration the default `gw query` behavior.

The new query path adds a `query_orchestrator` role that plans retrieval,
selects worker batches, inspects evidence, resolves stale wiki claims against
source code where possible, and writes the final answer itself.

The current query primitives remain valuable and should be reused:

- BM25 plus embedding retrieval stays as the initial candidate generator.
- `librarian` stays a vault-page excerpt worker.
- `code_reader` stays the source-reading worker, but receives explicit targets
  and a structured evidence contract from orchestrated query.
- `synthesizer` remains available for legacy or fallback paths, but the new
  orchestrator owns final-answer synthesis.
- graph tools help with planning and target discovery. Final answer evidence
  must come from wiki or code evidence.

The old query pipeline should remain reachable as an internal legacy/fallback
helper and test seam, but it is no longer the default CLI or MCP behavior.

## Non-Goals

- Do not replace the BM25 or embedding indexes.
- Do not give the orchestrator direct repo-file read tools in v1.
- Do not make graph rows final answer evidence by themselves.
- Do not introduce shared worker-batch or final-answer orchestration runtime in
  this pass. The low-level `agent_tools` and `agent_loop` helpers from
  `2026-06-07-agent-tooling-extraction-design.md` should be reused.
- Do not remove existing query guardrails or trace records.

## Current Behavior

`run_query()` currently performs a fixed pipeline:

1. Resolve the wiki.
2. Build the search index if needed.
3. Run BM25 and embedding search.
4. Fuse candidates with RRF.
5. Fan out `librarian` calls over the top pages.
6. Synthesize an answer from useful librarian excerpts.
7. Fall back to `code_reader` only when no useful vault excerpts exist.
8. Apply citation guardrails and write query traces.

The librarian already has a bounded graph-tool loop, but it receives one page at
a time. That makes it a good page reader, not a strong search planner. It also
means code reading only happens after vault failure, even when a stale wiki page
should be treated as a clue that needs source verification.

## Proposed Architecture

Add a focused `graph_wiki_core.commands.query_orchestrator` module, modeled
after the role-specific boundary used by `proposal_reasoner`.

The module should build on the shared low-level agent tooling extraction rather
than duplicating bounded wiki reads, catalog search, graph-tool filtering, or
basic LangChain tool-call loop mechanics. Query-specific planning, worker
batches, evidence validation, and `QueryResult` compatibility stay local to
`commands.query_orchestrator`.

The module owns:

- orchestrator context construction
- direct planning tools
- worker batch schema
- parallel worker dispatch helpers
- iterative orchestration loop
- structured output parsing and validation
- staleness-aware evidence classification

`run_query()` remains the public entry point. It should keep workspace
resolution, index bootstrap, initial retrieval, guardrails, and compatibility
wrapping into `QueryResult`, but delegate the agentic query work to the new
module.

## Model Role

Add a distinct `query_orchestrator` role to `model_adapter/models.toml`.

Initial default:

- model: `moonshotai.kimi-k2.5`
- region: `us-east-1`
- max tokens: `4096`
- max concurrency: `1`, because one orchestrator owns a whole query

This role is separate from `librarian`, `code_reader`, and `synthesizer`:

- `librarian`: extracts relevant passages from selected wiki pages
- `code_reader`: reads source files for source-backed evidence
- `query_orchestrator`: plans, chooses workers, validates sufficiency, and
  writes the final answer

## Pipeline

The default query flow becomes:

1. Resolve workspace, wiki, and repo as today.
2. Ensure BM25 and embedding indexes exist as today.
3. Run current BM25 plus embedding retrieval and RRF fusion to produce initial
   top candidates and `search_scores`.
4. Build an orchestrator context packet with:
   - user query
   - initial search candidates with paths, scores, and bounded excerpts or
     summaries
   - lightweight wiki catalog/search access
   - graph availability and graph planning tools when initialized and non-empty
   - repo root and source-read constraints
   - worker capability descriptions
   - answer and evidence JSON contract
5. Run an iterative orchestration loop capped at five worker-batch iterations.
6. During each iteration, the orchestrator can use direct planning tools.
7. If more evidence is needed, the orchestrator emits a worker batch plan for
   `librarian` and/or `code_reader`.
8. Local code runs requested worker tasks in parallel with `SubagentPool`,
   respecting each role's configured `max_concurrency`.
9. Worker results are summarized and fed back into the orchestrator.
10. The orchestrator finalizes once evidence is sufficient or the five-batch cap
    is reached.
11. Local code validates the final JSON, builds `QueryResult`, applies existing
    guardrails, and writes query traces.

When the batch cap is reached without enough evidence, the orchestrator must
produce a supported partial answer plus explicit gaps. It must not invent the
missing claims.

## Direct Planning Tools

The orchestrator can use bounded tools for planning:

- `search_wiki(query, kind?, top_k?)`: find candidate wiki pages. This can reuse
  current BM25 plus embedding search where practical, or a bounded catalog
  search from `agent_tools` when a full query-index pass is not appropriate.
- `read_wiki_page(path)`: bounded markdown read under `<workspace>/wiki`, using
  the shared wiki-read helper.
- `cg_find`: existing graph grounding tool when the graph DB is available.
- `cg_describe`: existing graph grounding tool when the graph DB is available.
- `list_worker_capabilities()`: optional static tool describing valid worker
  task shapes and limits.

The orchestrator does not get direct repo-file reads in v1. Source evidence goes
through `code_reader` so source reads keep their own prompt, bounds, trace role,
and output contract.

If the graph DB is missing, uninitialized, or empty, graph tools are omitted and
the orchestrator context says graph tools are unavailable.

## Worker Batches

The orchestrator can request parallel batches containing `librarian` and
`code_reader` tasks.

Librarian task shape:

```json
{
  "worker": "librarian",
  "page_path": "entities/package/foo.md",
  "query_focus": "How Foo exposes its public API",
  "expected_evidence": "API ownership and citations"
}
```

Code-reader task shape:

```json
{
  "worker": "code_reader",
  "target_paths_or_hints": ["packages/foo/src", "packages/foo/pyproject.toml"],
  "query_focus": "Verify Foo public entry points and runtime behavior",
  "expected_evidence": "path:line-backed source excerpts"
}
```

The existing `librarian` sentinel `NO_RELEVANT_CONTENT` remains valid for
backward compatibility. Orchestrated calls should prefer structured evidence
entries where possible.

The existing `code_reader` role should be adapted, not replaced, in v1. It keeps
its model config and role identity, but gains an orchestrated prompt branch that
accepts explicit target paths or hints and returns structured evidence entries.
If later evals show that query source reading needs independent model tuning,
the role can be split into a dedicated `query_code_reader`.

## Staleness-Aware Evidence

The orchestrator treats stale wiki content as retrieval context, not automatically
trusted final evidence.

V1 recognizes four staleness signals:

- `drift_review` frontmatter entries
- source-backed entity pages whose `last_updated_commit` does not match current
  HEAD
- TODO or sparse placeholder pages
- degraded ingest/proposal status frontmatter, when present

Every wiki evidence candidate receives a freshness classification:

- `fresh`
- `stale`
- `unknown`

When a relevant claim appears only on stale wiki evidence, the orchestrator
should first try to resolve it through `code_reader` or fresher linked wiki
evidence. Code evidence becomes preferred final evidence for stale
source-backed claims.

If no fresh or code verification is available, the final answer may include the
stale claim only when it is explicitly labeled in the answer and represented in
`gaps`.

Structured evidence entries must include `freshness` and `staleness_reason` for
wiki evidence. The answer-evidence map must not silently support a claim with
stale-only evidence.

## Output Contract

The orchestrator returns one JSON object:

```json
{
  "answer_markdown": "Markdown final answer.",
  "citations": ["entities/package/foo.md"],
  "evidence": [
    {
      "id": "E1",
      "source_type": "wiki",
      "path": "entities/package/foo.md",
      "freshness": "fresh",
      "staleness_reason": null,
      "excerpt": "Relevant wiki excerpt.",
      "line_refs": []
    },
    {
      "id": "E2",
      "source_type": "code",
      "path": "packages/foo/src/bar.py",
      "freshness": "fresh",
      "staleness_reason": null,
      "excerpt": "Relevant source excerpt.",
      "line_refs": ["packages/foo/src/bar.py:42"]
    }
  ],
  "answer_evidence_map": [
    {
      "claim": "Foo owns bar routing.",
      "evidence_ids": ["E1", "E2"]
    }
  ],
  "worker_plan": [],
  "worker_results": [],
  "gaps": [
    {
      "question": "Whether Foo still handles legacy mode.",
      "reason": "Only stale wiki evidence was found and code did not verify it."
    }
  ],
  "confidence": "high"
}
```

Allowed `source_type` values for final answer evidence:

- `wiki`
- `code`

Graph observations can appear in worker planning and trace metadata, but not as
final answer evidence.

Allowed `confidence` values:

- `high`
- `medium`
- `low`

## Validation

Local validation must enforce:

- `answer_markdown` is non-empty markdown text
- evidence IDs are unique
- mapped evidence IDs exist
- final answer evidence uses only `wiki` or `code`
- graph evidence does not appear in `evidence`
- stale-only claim support has a matching `gaps` entry or explicit uncertainty
  note in `answer_markdown`
- citations still pass existing unresolved-wikilink guardrails

Invalid JSON or schema failure degrades to a clear insufficient-evidence answer
with gaps. It must not fall through to fabricated synthesis.

## Error Handling

The query path is best-effort but evidence-strict.

Failure behavior:

- graph unavailable: omit graph tools and continue
- one worker failure: record the failed worker result and continue if other
  evidence exists
- all workers empty: return an insufficient-evidence answer with gaps
- orchestration cap reached: answer only with supported evidence plus gaps
- invalid orchestrator JSON: return a degraded insufficient-evidence answer
- Bedrock/model failure: fall back to the legacy query path only if that path can
  preserve evidence rules; otherwise return a degraded insufficient-evidence
  answer

Error strings in user-facing answers and trace summaries should be short and
sanitized.

## QueryResult Compatibility

`QueryResult.answer` should expose `answer_markdown`.

`QueryResult.citations` should be derived from the final answer markdown as
today, plus any validated citation list that remains compatible with existing
guardrails.

`QueryResult.pages_drilled` should count successful worker reads that returned
useful evidence, not merely initial search candidates.

`QueryResult.search_scores` should continue reporting the initial RRF candidate
scores so existing evals and callers can compare retrieval behavior.

Richer orchestrator metadata should be written to traces rather than added to
`QueryResult` in v1, unless an implementation plan identifies a low-risk
backward-compatible field.

## Testing

Focused tests should cover:

- `query_orchestrator` role exists in model config and uses
  `moonshotai.kimi-k2.5`.
- default `run_query()` routes through the orchestrator path.
- initial BM25/embedding candidates are passed into orchestrator context.
- direct planning tools are bounded to the wiki and graph surfaces.
- direct planning tools reuse shared bounded wiki-read, catalog search,
  graph-tool filtering, and tool-loop helpers.
- graph tools are omitted when graph DB is unavailable or empty.
- graph observations cannot become final answer evidence.
- librarian and code-reader worker batches run through `SubagentPool` in
  parallel.
- the orchestration loop stops at the five-batch cap.
- structured JSON validation accepts valid output and rejects malformed output.
- stale detection recognizes `drift_review`.
- stale detection recognizes `last_updated_commit` mismatches against current
  HEAD.
- stale detection recognizes TODO or sparse placeholder pages.
- stale detection recognizes degraded ingest/proposal status.
- stale wiki claims trigger code-reader verification when possible.
- stale-only evidence produces explicit gaps.
- invalid orchestrator output degrades safely.
- existing unresolved-wikilink guardrails still run.
- the legacy query helper remains covered by existing query tests.

Scoped verification should use package tests:

```bash
uv run --package graph-wiki-core pytest packages/graph-wiki-core/tests/unit/test_agent_tools.py packages/graph-wiki-core/tests/unit/test_agent_loop.py
uv run --package model-adapter pytest packages/model-adapter/tests/test_loader.py
uv run --package graph-wiki-core pytest packages/graph-wiki-core/tests/test_query_graph_tools.py
uv run --package graph-wiki-core pytest packages/graph-wiki-core/tests/test_query_code_fallback.py
uv run --package graph-wiki-core pytest packages/graph-wiki-core/tests/test_command_overrides.py
```

## Deferred

- Dedicated `query_code_reader` role.
- Shared worker-batch orchestration runtime for query and future multi-worker
  commands.
- Graph facts as first-class final answer evidence with their own citation
  semantics.
- Streaming intermediate query plans to CLI/MCP users.
- New `QueryResult` fields for structured evidence.
