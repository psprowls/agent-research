# Source-type consolidation design

**Date:** 2026-06-05
**Status:** Approved (pending implementation)

## Problem

Source pages carry two parallel classification fields that overlap in intent but
diverge in behavior:

- **`source_type`** — path-derived enum produced by
  `wiki_io.ingest_source.guess_source_type`. It is the only classification field
  actually *consumed* downstream: `backlink_index.py:91` renders it as the
  `(spec, 2026-06)` suffix on `## Referenced in wiki` backlink bullets. But the
  **Bedrock core path** (`run_ingest_source`) never writes it to frontmatter — it
  only feeds it to the ingestor LLM as a hint. Only the **plugin path**
  (`build_ingest_brief` → `agents/ingestor.md`) actually stamps `source_type`.
- **`source_kind`** — written only by the core path. LLM-decided, free-form,
  defaults to `"unknown"`. Surfaced in `IngestResult` / CLI echo / MCP response
  but **read by nothing**. It is dead-weight output.

The two fields are redundant. The clean model is a single `source_type`.

## Goals

- Remove `source_kind` entirely (prompt, frontmatter stamping, `IngestResult`,
  CLI echo, MCP response).
- Make the Bedrock core path actually **write** `source_type` to frontmatter,
  closing the gap with the plugin path and feeding `backlink_index`.
- Determine `source_type` by path first, with an LLM content-classification
  fallback for files not under a known `raw/<type>/` folder.
- Keep both delivery surfaces (core + plugin) describing one consistent model.

## Non-goals

- No new enum values. The set is unchanged from what `guess_source_type` already
  emits.
- No migration code. Per `.claude/rules/backward-compatibility.md`, the user
  rebuilds the wiki on schema changes.
- No change to the `doc`-gated drift behavior (`last_sync_commit` / `last_sync_at`
  still key on `source_type: doc`).

## The model

One field, `source_type`, on every Source page. Closed enum (unchanged):

```
spec · article · pr · ticket · transcript · example · doc · note
```

`note` is the catch-all. There is no `unknown` and no `rfc`.

### Determination order

1. **`raw/<type>/` folder → authoritative.** A file under `raw/specs/`,
   `raw/articles/`, `raw/prs/`, `raw/tickets/`, `raw/transcripts/`, or
   `raw/examples/` takes its `source_type` from the path. The LLM's opinion is
   ignored for these — fully deterministic.
2. **Otherwise → LLM classifies from content.** For in-repo docs and loose files,
   the path-guess (`doc` for in-repo, `note` for loose) is a *default*, and the
   ingestor LLM may override it with a more specific enum value based on the
   document's content.
3. **Fallback.** If the LLM returns nothing usable (empty, or a value outside the
   enum), keep the path-guess default — `doc` for in-repo, `note` for loose.
   No path, no repo → `note`.

## Shared constants

Add to `wiki_io.ingest_source`, next to `guess_source_type`, so both surfaces and
`backlink_index` share one source of truth:

- `SOURCE_TYPE_ENUM` — the full closed set
  (`spec, article, pr, ticket, transcript, example, doc, note`).
- `RAW_FOLDER_TYPES` — the authoritative subset produced from a `raw/<type>/`
  folder (`spec, article, pr, ticket, transcript, example`).

## Core path (Bedrock Python)

In `run_ingest_source` (`commands/ingest.py`):

- `source_type = guess_source_type(...)` computed as today (the path-guess).
- The ingestor prompt is reworded: instead of "optionally emit a descriptive
  `source_kind`," the LLM is told to return a `source_type` from the closed enum,
  classifying from content, defaulting to `note` when unsure. The path-guess is
  still passed in as the hint.
- Resolve the final value after the LLM call:

  ```python
  if path_guess in RAW_FOLDER_TYPES:        # spec/article/pr/ticket/transcript/example
      source_type = path_guess              # authoritative; LLM ignored
  else:
      llm_value = fm.get("source_type")      # from parsed ingestor frontmatter
      source_type = llm_value if llm_value in SOURCE_TYPE_ENUM else path_guess
  ```

- Rename body helper `_set_source_kind_in_body` → `_set_source_type_in_body`; it
  stamps `source_type:` into frontmatter. This is the line that makes the core
  path finally *write* the field.
- `_synthesize_frontmatter_block` (no-frontmatter-emitted case) writes
  `source_type` instead of `source_kind`.
- `IngestResult.source_kind` → `IngestResult.source_type`. `frontmatter_parsed`
  is unchanged. CLI echo (`main.py:339,343`) and MCP response field
  (`server.py:328,380`) follow the rename.

Affected prompt fragments: `prompts/ingestor.py` and
`prompts/_fragments/frontmatter_rules.py` (replace the `source_kind` guidance with
the `source_type` enum + content-classification + `note`-fallback rules).

## Plugin-path parity

The plugin path is already LLM-driven and already writes `source_type`; parity is
aligning the instructions to the same enum + `note` fallback + content rule.

- **`agents/ingestor.md`** — the frontmatter spec already requires `source_type`;
  update surrounding guidance to describe the closed enum, the
  `raw/<type>/`-authoritative rule, content-classification for non-folder files,
  and `note` as the catch-all.
- **`skills/graph-wiki/references/wiki-schema.md`** — correct the enum comment
  from `spec | article | pr | ticket | transcript | rfc | doc | example` to
  `spec | article | pr | ticket | transcript | example | doc | note` (drop `rfc`,
  add `note`).
- **`skills/graph-wiki/references/page-formats.md`** and
  **`skills/graph-wiki/references/ingest-workflow.md`** — same enum correction.
- **`scripts/ingest_source.py`** — already prints `brief['source_type']` from
  `build_ingest_brief`; no logic change, inherits the shared constant. The
  `doc`-gated `last_sync_commit` behavior is unaffected.

No `source_kind` exists on the plugin side, so there is nothing to remove there —
this is purely doc-alignment so both surfaces tell the same story.

## Testing

**Unit (wiki-io):**
- Existing `guess_source_type` tests stay green (enum unchanged).
- Add a test pinning `SOURCE_TYPE_ENUM` / `RAW_FOLDER_TYPES` contents.

**Unit (core) — `test_commands_ingest.py`:**
- `raw/specs/x.md` → frontmatter stamped `source_type: spec`, a contrary LLM
  value ignored (determinism).
- In-repo loose doc where the LLM returns `transcript` → stamped `transcript`
  (content override).
- LLM returns empty / out-of-enum garbage → falls back to path-guess (`doc` for
  in-repo, `note` for loose).
- No-frontmatter-emitted case → `_synthesize_frontmatter_block` writes
  `source_type`, not `source_kind`.
- `IngestResult.source_type` populated; `source_kind` attribute is gone.

**Surfaces:**
- `test_wiki_cli.py` and `test_mcp_new_tools.py` — update `source_kind`
  assertions to `source_type`.
- `test_suggest_pages.py` — adjust if it touches the renamed field.

**Snapshots:**
- `test_prompt_snapshots.ambr` — regenerate; the ingestor prompt text changes.

**Backlink consumer:**
- `test_backlink_index.py` already constructs pages with `source_type="spec"`;
  confirms the `(spec, date)` suffix still renders. No change needed — it
  validates the core path now feeds it correctly.

**Manual smoke:** ingest one file from a `raw/specs/` folder and one loose in-repo
`.md`; confirm the written frontmatter has the right `source_type` and no
`source_kind` line.
