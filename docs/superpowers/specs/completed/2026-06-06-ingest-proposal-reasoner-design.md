# Ingest Proposal Reasoner Design

Date: 2026-06-06
Status: approved for implementation planning

## Goal

Improve Bedrock `gw wiki ingest source` so it behaves more like the Claude plugin's thoughtful ingest flow while remaining non-interactive. The command should still write a Source page automatically, but proposal pages become the asynchronous review surface for follow-up concept, ADR, and architecture work.

The first implementation uses `moonshotai.kimi-k2.5` for all three roles:

- `ingestor`
- `proposal_reasoner`
- `extractor`

Kimi K2 Thinking and Bedrock Mantle support are deferred. The current Bedrock runtime path already supports K2.5 tool calling through LangChain in this repo; Mantle would add a second provider path and should wait until the K2.5 version is working.

## Current Behavior

`run_ingest_source()` writes a Source page through one `ingestor` LLM call, then runs a best-effort `extractor` pass. The extractor currently sees the just-written Source page plus a shallow index of existing `concepts/`, `adrs/`, and `architecture/` pages. It writes proposal ledger notes under `wiki/proposals/`.

The current context is too thin:

- the ingestor prompt truncates raw source text to `PREVIEW_CHARS`
- the extractor prompt truncates the Source page to `EXTRACT_PREVIEW_CHARS`
- the extractor has no tool access
- the extractor sees no entity catalog, source catalog, existing proposal catalog, or graph details
- proposal notes contain only origin/rationale text, not enough review context

## Proposed Pipeline

Keep ingest non-interactive:

1. `ingestor` writes or updates the Source page under `wiki/sources/`.
2. `proposal_reasoner` receives rich context and bounded tools, then produces up to 10 candidate proposal analyses.
3. `extractor` normalizes the reasoner output into strict YAML, selects at most 5 ledger proposals, and writes proposal notes.
4. `update_index()` and `append_log()` run as they do today.

The proposal phase is best-effort. If the reasoner or extractor fails, the Source page remains written and the failure is recorded in Source frontmatter.

This keeps responsibilities separate:

- `ingestor`: summarize the source and create the canonical Source page
- `proposal_reasoner`: reason about what follow-up pages are warranted
- `extractor`: enforce proposal schema, rank/select the top 5, and feed the ledger

## Reasoner Context

The reasoner starts with a structured context packet:

- full raw document text when it fits a configured input budget
- if over budget, a deterministic chunk map plus tool access to chunks
- the just-written Source page path and content
- curated wiki catalog for `concepts`, `adrs`, `architecture`, and existing `sources`
- entity catalog from `entities/`, including kind, title, URI, and summary or narrative excerpt when present
- existing proposal catalog, including open and decided proposals
- graph match details from ingest: `entity_uri`, entity filename, source path, and source type

This gives the model a clear view of what already exists before it proposes new pages.

## Tool Surface

The reasoner can use a bounded tool loop. Initial tools:

- `read_wiki_page(path)`: bounded read under `<workspace>/wiki`
- `search_wiki_catalog(query, kind?)`: title/summary search over the prepared catalog
- `read_source_chunk(index)`: read a deterministic chunk of an over-budget raw source
- `cg_find`: reuse the existing graph tool when the graph DB is available
- `cg_describe`: reuse the existing graph tool when the graph DB is available

Bounds:

- max 5 tool-call iterations
- max 10 reasoner candidates
- max 5 extractor-selected ledger proposals

If the graph DB is unavailable, graph tools are omitted and the reasoner prompt says graph tools are unavailable.

## Whole-Document Handling

The preferred path is to provide the entire raw document to the model. For sources that fit the configured budget, the reasoner receives the whole text.

For oversized sources, the command should not blindly overflow model context. It should:

1. include a source chunk map in the prompt
2. include the Source page summary
3. expose `read_source_chunk(index)` so the reasoner can inspect high-value chunks

The first implementation can use a conservative character/token estimate based on existing `wiki_io.update_tokens.count_tokens()` where available, with a fallback character budget.

## Proposal Page Format

Proposal notes remain under `wiki/proposals/` and keep frontmatter as the machine contract:

- `kind`
- `mode`
- `target_slug`
- `title`
- `status`
- `origins`
- optional `rank`
- optional `confidence`

The body becomes a richer review artifact while `status: proposed`:

```markdown
<!-- Body regenerated from origins[] while status: proposed. Do not edit here;
     approve via `gw wiki proposal approve <kind>-<target_slug>`. -->

## Suggested Action

...

## Evidence From Source

...

## Existing Pages Considered

...

## Reasoning Summary

...

## Potential Conflicts

...

## Implementation Notes

...

## Origins

**ingest · [[sources/example]]**
...
```

When a proposal is approved, rejected, or created, existing behavior still applies: producer upserts must not overwrite the human-decided note.

## Source Frontmatter Status

Every Source page written by `run_ingest_source()` gets a `proposal_status` frontmatter block after the proposal pipeline completes.

Successful run:

```yaml
proposal_status:
  reasoner: ok
  extractor: ok
  proposals: 3
  updated: 2026-06-06
```

Degraded run:

```yaml
proposal_status:
  reasoner: failed
  extractor: skipped
  proposals: 0
  updated: 2026-06-06
  error: proposal_reasoner returned non-text content
```

Allowed status values:

- `reasoner`: `ok`, `failed`, `skipped`
- `extractor`: `ok`, `failed`, `skipped`
- `proposals`: integer count written to `wiki/proposals/`
- `updated`: ingest date
- `error`: short sanitized message only when degraded

A later successful re-ingest overwrites the degraded block with the new successful status.

## Result Shape

`IngestResult` should expose proposal pipeline state explicitly. Existing `suggested_pages` can remain for compatibility, but implementation should add clearer fields or an equivalent structured status:

- `proposal_reasoner_status`
- `proposal_extractor_status`
- `proposal_error`
- `suggested_pages`

CLI and MCP surfaces should continue showing the proposals written by the run. They should also expose degraded proposal status when either phase fails.

## Error Handling

The proposal pipeline must never roll back the Source page. Failure behavior:

- reasoner failure: extractor is skipped, zero proposals are written, Source frontmatter records degraded status
- extractor failure or parse miss: zero proposals are written, Source frontmatter records degraded status
- tool-call iteration cap: reasoner finalizes from available context if possible; if no valid reasoner output exists, mark reasoner failed
- missing graph DB: omit graph tools and continue
- invalid individual proposal candidate: extractor drops it and can still write other valid proposals

Error strings written to frontmatter must be short and sanitized so frontmatter remains readable and stable.

## Testing

Focused tests should cover:

- model config contains `ingestor`, `proposal_reasoner`, and `extractor` on `moonshotai.kimi-k2.5`
- `proposal_reasoner` receives full source text when under budget
- oversized source creates chunks and exposes `read_source_chunk`
- reasoner tool loop handles one tool call and bounded iteration cap
- extractor selects at most 5 proposals from up to 10 candidates
- richer proposal body renders expected sections
- decided proposal notes are not overwritten by re-ingest
- Source frontmatter records `proposal_status` on success
- Source frontmatter records degraded status on reasoner failure
- Source frontmatter records degraded status on extractor failure
- graph-unavailable path omits graph tools and still completes

Scoped verification should use package tests:

```bash
uv run --package graph-wiki-core pytest packages/graph-wiki-core/tests/unit/test_commands_ingest.py
uv run --package wiki-io pytest packages/wiki-io/tests/test_proposals.py
uv run --package model-adapter pytest packages/model-adapter/tests/test_loader.py
```

## Deferred

- Kimi K2 Thinking model support for `proposal_reasoner`
- Bedrock Mantle OpenAI-compatible provider path
- streaming reasoning traces in proposal pages
- automatic creation of approved proposals
- deeper vault retrieval beyond bounded catalog search and page reads
