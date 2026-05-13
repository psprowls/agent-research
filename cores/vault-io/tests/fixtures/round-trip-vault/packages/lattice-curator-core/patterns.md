---
title: lattice-curator-core — Patterns
category: package
summary: The gate → retrieve → format pipeline, stage-aware curation, source adapter contract, Bedrock test seam, and fail-silent posture.
tags: [python, patterns, langgraph, rag]
updated: 2026-05-10
tokens: 1766
---

# lattice-curator-core — Patterns

## Key patterns

### The pipeline (gate → retrieve → format)

Three pure functions composed by the consuming surface (a Claude Code hook, the MCP server, an eval harness):

```
prompt + transcript_tail + state + config
        │
        ▼
   gate()  ──── fire=False ────► return (no-op, log "gate_only")
        │
        ▼ fire=True, stage, hint
   retrieve(stage, prompt, transcript_tail, sources, model)
        │
        ▼ Brief
   format_brief(brief, mode)  ──► markdown string for stdout
```

The package never decides where the brief goes. The hook prints it to stdout (Claude Code injects stdout from `UserPromptSubmit` hooks back into the turn). The MCP server returns it as a tool result. CI tests assert on the string.

### Stage-aware curation

Five stages live in `packages/lattice-curator-core/src/lattice_curator_core/stages/`. Each is a `StageDef` with:

- A `selection_target {min, max}` — Pass 1 budget for catalog picks.
- A `pass1_prompt` — instructs the model how to triage the catalog for this stage.
- A `pass2_prompt` — instructs the model how to summarize picked content for this stage.

| Stage | min | max | Pass 1 prompt emphasis |
|---|---|---|---|
| `brainstorming` | 4 | 8 | "prior decisions, related concepts, anti-patterns, ADRs" |
| `writing-plans` | 3 | 6 | "package boundaries, file maps, test conventions, integration contracts, style rules" |
| `execute-plan` | 2 | 5 | "the specific package overview, immediately relevant rules, files named in the prompt" |
| `debugging` | 3 | 6 | "prior incidents, gotcha rules, ADRs about the affected area, similar past fixes" |
| `generic` | 3 | 6 | "most relevant" (no opinion) |

Stage selection is part of the gate's job. Routing comes from three signals (in order): an explicit recent `lattice-workflows:*` skill marker, an action verb in the prompt (`brainstorm|design|plan|implement|fix|debug|review|...`), then a topic-shift Jaccard score on `transcript_tail`. See `packages/lattice-curator-core/src/lattice_curator_core/gate.py:55`.

### Two-pass retrieval as a LangGraph

`retriever.py` builds a module-level singleton `StateGraph`:

```
START → build_catalog → pass1_pick →[picks_router]→ load_picks → pass2_brief → END
                                              \→ assemble (empty) → END
```

Why a graph rather than two serial `await`s:

1. **Conditional routing** — the `picks_router` short-circuits the load + Pass 2 cost when Pass 1 returns nothing.
2. **Parallelism inside nodes** — `build_catalog` and `load_picks` use `asyncio.gather` over the source list and the picks list.
3. **Future fallback nodes** — retry-on-empty, budget-exhausted, multi-model fallback drop in as new nodes without rewriting the controller.

Pass 1 sees only frontmatter (cheap). Pass 2 sees the full text of the picks (expensive). Both calls use Pydantic structured output via LangChain's `with_structured_output(SchemaCls)`. Pass 2 schema failures fall through to a degraded brief that lists the picks as see-also entries — never raises.

### Source adapter contract

The `Source` Protocol (`packages/lattice-curator-core/src/lattice_curator_core/sources/types.py:21`) is two async methods:

```python
class Source(Protocol):
    name: str
    async def catalog(self) -> list[CatalogEntry]: ...
    async def load(self, path: str) -> str: ...
```

`CatalogEntry`: `source`, `path`, `title`, `description`, `tags: dict`. The retriever sees only this shape; new knowledge surfaces drop in as new files under `sources/`.

Two surfaces ship:

- **Wiki** — Obsidian-style vault. `description:` frontmatter required; `kind` from frontmatter becomes the only tag. Used to expose [[wiki/plugins/lattice-wiki/lattice-wiki]] vault content.
- **Experts** — directory of `<domain>/*.md` rules. `description:` and `impact:` frontmatter; the top-level subfolder becomes `domain`, with `_shared` mapped to `shared`. Used to expose the bundled rule library and the per-project `lattice/knowledge/` seeded by [[wiki/plugins/lattice-curator/lattice-curator]]'s `/curator:init` command.

Catalog dedup is by `path` (first-write-wins) at `retriever.py:57` — sources earlier in the list shadow later ones.

### [[wiki/concepts/bedrock-langgraph-stack|Bedrock]] as a test seam

`make_bedrock(config)` returns a `ChatBedrockConverse`. The retriever takes `model` as a positional argument and only depends on `model.with_structured_output(SchemaCls).ainvoke(text)`. Tests inject any object satisfying that contract — no network needed. Live runs read `LATTICE_CURATOR_MODEL`, `AWS_DEFAULT_REGION` / `AWS_REGION` from env. Default model: `us.anthropic.claude-haiku-4-5-20251001-v1:0`.

### Fail-silent posture

The package never raises out of `retrieve()`:

- Pass 1 model error → `picks = []` → `assemble` builds an empty brief (`summary="No relevant context found."`).
- Pass 2 model error → degraded brief with picks as see-also entries.
- Catalog walk errors → that source's entries are skipped with a stderr warning; retrieval proceeds with whatever else loaded.

This is deliberate: the consuming hook treats absence-of-brief as normal. A misbehaving curator must not block the user's prompt.

The corollary is the JSONL fire log (`append_fire`) — every fire writes a structured record with `outcome` (`gate_only | ok | pass1_timeout | ...`), token counts, picks, mode. Drift, regressions, and prompt-size creep are observable from the log without reading code.

## Conventions

- **One module, one purpose.** Each file in `lattice_curator_core/` has a single responsibility — `gate.py` is pure logic with no I/O, `retriever.py` owns the LangGraph wiring, `format.py` owns rendering.
- **Inject dependencies.** `retrieve()` takes `sources` and `model` as arguments. No global state beyond the compiled `StateGraph` singleton.
- **Fail silently, log loudly.** Errors inside the pipeline write to stderr and the JSONL fire log; they never propagate to the caller.
- **New stages = new files.** Add a stage by creating `stages/<name>.py` and registering it in `stages/__init__.py._REGISTRY`. No other changes required.
- **New sources = new files.** Add a knowledge surface by creating `sources/<name>.py` implementing the `Source` Protocol. No retriever changes required.
- **Tests inject fakes.** Any object satisfying `.with_structured_output(SchemaCls).ainvoke(text)` is a valid model. Tests never touch Bedrock.

## See also

- [[wiki/packages/lattice-curator-core/api]] — the function and type contracts the patterns rely on
- [[wiki/packages/lattice-curator-core/context]] — the why behind the boundary and the stack
- [[wiki/concepts/two-pass-context-curation]] — the algorithm written up as a concept page
- [[wiki/concepts/curator-source-interface]] — the adapter protocol
