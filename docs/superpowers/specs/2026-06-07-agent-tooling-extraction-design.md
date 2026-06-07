# Agent Tooling Extraction Design

Date: 2026-06-07
Status: approved for spec review

## Goal

Extract the proven low-level tooling mechanics from the implemented ingest
`proposal_reasoner` path before building `package_reader` and
`query_orchestrator`.

The shared layer should remove duplicated safe-path handling, catalog/search
helpers, text chunking, graph-tool filtering, and LangChain tool-call loop code
without creating a broad agent runtime.

## Non-Goals

- Do not introduce worker-batch orchestration.
- Do not move proposal-specific prompt or result logic into the shared layer.
- Do not add package-reader section replacement or query evidence validation.
- Do not change CLI, MCP, or ingest behavior.
- Do not introduce a generic trace or planning runtime for all agentic commands.

## Current Behavior

`graph_wiki_core.commands.proposal_reasoner` now owns several utilities that are
not actually proposal-specific:

- bounded markdown reads under `<workspace>/wiki`
- wiki catalog construction for curated pages, entities, sources, and proposals
- simple catalog search over title, summary, slug, and target slug
- deterministic source text chunking
- graph tool allowlisting for `cg_find` and `cg_describe`
- a capped LangChain tool-call loop using `bind_tools`, `ainvoke`, and
  `ToolMessage`

The package-reader and query-orchestrator specs describe similar mechanics. If
implemented independently, those paths would duplicate the same safety and loop
logic.

## Proposed Architecture

Add two small modules in `graph_wiki_core`:

- `graph_wiki_core.agent_tools`
- `graph_wiki_core.agent_loop`

`agent_tools` owns reusable bounded tool and context helpers:

- `read_bounded_wiki_page(wiki, path, max_chars=...)`
- `build_wiki_catalog(wiki, buckets=...)`
- `search_wiki_catalog(catalog, query, kind=None, limit=20)`
- `chunk_text(text, max_chars=..., chunk_chars=...)`
- `filter_graph_tools(graph_tools, allowed_names)`

`agent_loop` owns the generic capped tool-call loop:

- bind tools to a role LLM when needed
- call `ainvoke`
- dispatch returned `tool_calls`
- append `ToolMessage` outputs
- stop on terminal model text or iteration cap
- return structured loop status, final text, and optional error

`proposal_reasoner` remains the role-specific boundary. It keeps its prompt,
context packet, role name, allowed tools, source-page semantics, and
`ProposalReasonerResult`, but delegates generic mechanics to the shared modules.

## Reuse Contract

The extraction must be behavior-preserving for ingest proposals.

`proposal_reasoner` continues to own:

- the `proposal_reasoner` model role selection
- `PROPOSAL_REASONER_SYSTEM`
- the proposal-specific human prompt
- the tool set exposed to that role
- conversion from generic loop result to
  `ProposalReasonerResult(status, analysis, error)`
- current iteration-cap semantics

The shared modules own only mechanics that are already needed by at least two
of the upcoming role-specific paths.

Package-reader should use the shared wiki-read, graph-tool filtering, chunking
where useful, and tool-loop primitives. Its repo file and tree tools remain
package-reader-specific because they are bounded by the entity root and write to
entity-page replacement logic.

Query-orchestrator should use the shared wiki-read, catalog/search,
graph-tool filtering, and low-level tool-loop primitives. Its worker batches,
evidence schema, staleness classification, and `QueryResult` wrapping remain
query-specific.

## Error Handling

The shared loop should convert tool exceptions into string tool outputs rather
than raising through the model loop. Unknown tool calls should also become
string tool outputs.

Iteration-cap behavior should be configurable by the caller but support the
proposal-reasoner contract:

- cap with prior model text: return `ok` plus a cap error note
- cap without prior model text: return `failed` with a cap error

The bounded wiki-read helper should return readable `ERROR:` strings for
invalid paths, missing pages, unsupported file types, and OS errors. It must
never read outside the wiki root.

## Testing

Focused tests should cover:

- catalog construction includes curated pages, entities, sources, and proposals
- bounded wiki reads include title/body, truncate at the configured limit, and
  reject paths outside the wiki root
- catalog search respects kind or bucket filters and result limits
- text chunking keeps full text under budget and splits over-budget text
  deterministically
- graph tool filtering exposes only requested tool names
- the tool loop returns terminal no-tool responses
- the tool loop dispatches one tool call and feeds the result back to the model
- unknown tool calls and tool exceptions become tool-message error strings
- iteration cap with prior text returns `ok` plus a cap error
- iteration cap without prior text returns `failed`
- `proposal_reasoner` tests still pass after refactoring to shared helpers

Scoped verification should use package tests:

```bash
uv run --package graph-wiki-core pytest packages/graph-wiki-core/tests/unit/test_agent_tools.py packages/graph-wiki-core/tests/unit/test_agent_loop.py
uv run --package graph-wiki-core pytest packages/graph-wiki-core/tests/unit/test_proposal_reasoner.py
uv run --package graph-wiki-core pytest packages/graph-wiki-core/tests/unit/test_suggest_pages.py packages/graph-wiki-core/tests/unit/test_commands_ingest.py
uv run --package model-adapter pytest packages/model-adapter/tests/test_loader.py
```

## Deferred

- Worker-batch orchestration shared by query and future multi-worker commands.
- Shared query evidence validation.
- Shared package-reader section replacement.
- Shared trace schema for all agentic command loops.
