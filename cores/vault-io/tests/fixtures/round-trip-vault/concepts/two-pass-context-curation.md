---
title: Two-pass context curation
category: concept
summary: Gate-then-pick-then-brief pipeline that turns a knowledge directory plus a user prompt into a small, task-specific markdown brief — Pass 1 sees only catalog frontmatter to keep token cost low, Pass 2 sees full text of the chosen picks plus prompt + transcript tail to compose the brief.
tags: [pattern, rag, context-curation, lattice-curator, langgraph, bedrock]
sources: 1
updated: 2026-05-09
tokens: 1382
---

# Two-pass context curation

## Definition

A retrieval pattern that decomposes "build a relevance-filtered context bundle" into three explicit phases:

1. **Gate** (no LLM) — pure-function decision over `(prompt, transcriptTail, lastFireAt, lastSkill)` returning `{fire, stage, hint}`. Most turns end here.
2. **Pass 1 — pick** (cheap LLM, catalog-only) — given a flat catalog of `{path, title, description, tags}` rows derived from frontmatter, the model returns `{ picks: string[], rationale: string }` bounded by a stage-specific `selectionTarget`.
3. **Pass 2 — brief** (cheap LLM, full text of picks) — given the full text of the picked files plus the prompt and a transcript tail, the model returns a structured `Brief` (`mustKnow`, `seeAlso`, `summary`).

The pipeline is wired as a [LangGraph](https://langchain-ai.github.io/langgraphjs/) `StateGraph` with nodes `buildCatalog → pass1Pick → loadPicks → pass2Brief → assemble`. Edges are linear today; modeled as a graph so fallback nodes (e.g. retry on empty picks) can be added without rewriting the controller.

## Motivation

Single-pass retrieval over a markdown vault has two pathologies:

- **Catalog-only retrieval** misses content-level relevance — frontmatter often understates how much a page actually applies.
- **Full-content retrieval** explodes Pass 1 token cost — the model has to chew on every page to decide which to use.

Splitting the decision lets each LLM call see the *minimum* it needs: Pass 1 reads frontmatter only (cheap), Pass 2 reads full text of `~3–8` picks only (focused). The cheap gate up front means Pass 1 only fires on turns where curation is likely to help.

## Shape

```
gate(prompt, transcriptTail, lastSkill, lastFireAt) ──► no-fire (most turns)
                            │
                            ▼
              ┌─── buildCatalog(sources) ──── flat catalog
              │           │
              │           ▼
              │   pass1Pick(stage prompt + catalog + user prompt)
              │           │
              │           ▼ {picks: [paths], rationale}
              │   loadPicks(picks)  → full text from disk
              │           │
              │           ▼
              │   pass2Brief(stage prompt + full text + prompt + transcriptTail)
              │           │
              │           ▼ Brief {mustKnow, seeAlso, summary}
              │
              └── assemble: attach diagnostics → format(brief, mode) → inject
```

Three load-bearing pieces:

- **Stage-aware prompts** — `brainstorming`, `writing-plans`, `execute-plan`, `debugging`, `generic`. Each defines a `selectionTarget: { min, max }` enforced both in the prompt copy and in the Zod schema validating Pass 1 output (with retry on violation).
- **Structured output via Zod** — `pass1Pick` returns `{ picks: string[], rationale: string }`; `pass2Brief` returns the `Brief` (minus diagnostics). Failure to satisfy the schema is a recoverable error, not a hard fail.
- **Two output modes** — `format(brief, mode)` renders either `hybrid` (must-know excerpts inline + see-also list with paths Claude can `Read`) or `inline` (everything expanded). Same `Brief`, two verbosities — A/B-able from config.

## Token economics

| Phase | Inputs | Output |
|---|---|---|
| Gate | none (pure heuristic) | `{fire, stage}` |
| Pass 1 | catalog (one line per page; ~50 entries → ~1KB) + prompt | ~3–8 path strings |
| Pass 2 | full text of picks (~3–8 KB) + prompt + transcript tail (~8KB cap) | structured `Brief` (~2KB) |

Latency budget targets: gate <50ms, both Bedrock hops 1–3s combined. The hook is `async: false`, so the curator blocks the turn — anything past ~5s feels bad.

## Used in

- [[wiki/packages/lattice-curator-core/lattice-curator-core]] — implements the pipeline as `gate.ts` + `retriever.ts` + `stages/` + `format.ts`. Bedrock-hosted small model (`ChatBedrockConverse`) provides the LLM calls.
- [[wiki/plugins/lattice-curator/lattice-curator]] — wires the pipeline behind a `UserPromptSubmit` hook (gated path) and an MCP `context.fetch` tool (always fires; gate skipped).

## Related patterns

- [[wiki/concepts/curator-source-interface]] — the `Source` adapter that produces the flat catalog feeding Pass 1.
- knowledge-skills-pattern — adjacent observation that subagents need explicit knowledge direction; the curator generalizes the fix to top-level Claude Code turns.
- wiki-cites-graph-not-duplicates — the wiki points to other surfaces rather than absorbing them; the curator does the inverse for read-time, pulling pointed-to content into one bounded brief.

## Sources

- 2026-05-context-curation-agent-design — full design pass; introduces the gate/pass1/pass2/brief shape, stage-aware prompts, hybrid vs inline output, fail-silent contract.

## Open questions / gotchas

- **Empty picks** — if Pass 1 returns zero picks, current spec falls through; a fallback retrieval node is the obvious next graph edit.
- **Pass 2 transcript awareness** — Pass 2 sees the transcript tail to avoid recommending things already loaded; Pass 1 deliberately does not, to keep its cost low.
- **Selection-target retry** — Zod-violation retries cost an extra Pass 1 round-trip; in practice the prompt copy + bound is enough to keep this rare.
