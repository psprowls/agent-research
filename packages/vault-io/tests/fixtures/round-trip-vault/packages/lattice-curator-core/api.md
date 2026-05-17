---
title: lattice-curator-core — API
category: package
summary: Public API surface — pipeline functions (gate, retrieve, format_brief), config models, source adapters, stage registry, types, and Bedrock/log helpers.
tags: [python, api, langgraph, pydantic]
updated: 2026-05-10
tokens: 2601
---

# lattice-curator-core — API

All names below are re-exported from `lattice_curator_core/__init__.py`. Source of truth: `packages/lattice-curator-core/src/lattice_curator_core/__init__.py:1`.

`VERSION = "0.1.0"` (declared in `__init__.py`; the `pyproject.toml` `version` is `1.0.0` — these are out of sync).

## Public API

### `gate(input: GateInput) -> GateDecision`

Pure tier-1 heuristic gate. No I/O. Returns a structured decision rather than raising. Defined at `packages/lattice-curator-core/src/lattice_curator_core/gate.py:55`.

Decision tree (first match wins):

1. `len(prompt.strip()) < cfg.min_prompt_length` → `fire=False, reason="prompt-too-short"`.
2. `last_fire_at` set and `(now - last_fire_at)/1000 < cfg.debounce_seconds` → `fire=False, reason="debounce"`.
3. `last_skill` set and not stale (`age <= cfg.stale_skill_seconds`) and name maps via `_SKILL_TO_STAGE` → `fire=True, stage=mapped, hint=f"skill:{name}"`.
4. Action verb in prompt (`brainstorm|design|explore|plan|spec|implement|build|refactor|fix|debug|troubleshoot|review`) → `fire=True, stage=<mapped>, hint="action-verb"`.
5. `transcript_tail` non-empty and Jaccard topic-shift `>= cfg.topic_shift_threshold` → `fire=True, stage="generic", hint=f"topic-shift:{shift:.2f}"`.
6. Else → `fire=False, reason="no-signal"`.

Skill-name → stage map (`packages/lattice-curator-core/src/lattice_curator_core/gate.py:21`):

| Skill name | Stage |
|---|---|
| `lattice-workflows:brainstorming`, `:brainstorm` | `brainstorming` |
| `lattice-workflows:writing-plans`, `:write-plan` | `writing-plans` |
| `lattice-workflows:executing-plans`, `:execute-plan`, `:subagent-driven-development` | `execute-plan` |
| `lattice-workflows:systematic-debugging`, `:receiving-code-review` | `debugging` |

### `async retrieve(stage, prompt, transcript_tail, sources, model) -> Brief`

Async LangGraph orchestration at `packages/lattice-curator-core/src/lattice_curator_core/retriever.py:190`. Graph topology:

```
START → build_catalog → pass1_pick →[picks_router]→ load_picks → pass2_brief → END
                                              \→ assemble → END
```

- `build_catalog` — runs `Source.catalog()` for every source concurrently (`asyncio.gather`); deduplicates by `path`.
- `pass1_pick` — formats catalog as `path | description [k=v ...]` lines, asks the model (with `Pass1Schema = {picks, rationale}`) to pick within the stage's `selection_target`. Filters picks against valid catalog paths and trims to `max`.
- `picks_router` — if no picks, jump to `assemble` (empty brief); otherwise continue.
- `load_picks` — `Source.load(path)` for every pick concurrently.
- `pass2_brief` — formats picked content as `=== <path> ===\n<content>` blocks, asks the model (with `Pass2Schema`) for a structured `Brief`. On schema failure, builds a degraded brief that lists picks as see-also entries.
- `assemble` — empty-result terminal node; returns `Brief(summary="No relevant context found.")`.

The `model` argument is duck-typed — anything supporting `.with_structured_output(SchemaCls).ainvoke(prompt)` works. `make_bedrock(config)` returns a `ChatBedrockConverse`; tests can substitute a fake.

`pass1_tokens` and `pass2_tokens` in diagnostics are `len(prompt_text) // 4` rough counts — not [[wiki/concepts/bedrock-langgraph-stack|Bedrock]]-reported usage.

### `format_brief(brief: Brief, mode: Mode) -> str`

Markdown renderer at `packages/lattice-curator-core/src/lattice_curator_core/format.py:4`. Output skeleton:

```markdown
## Curated context (<stage>)

<summary>

### Must know
- **<path>**

  <excerpt>

### See also
- `<path>` — <one_liner>     # mode == "hybrid"
- **<path>** — <one_liner>   # mode == "inline" (also dumps full_content)
  <full_content>
```

`hybrid` keeps See also as raw paths Claude can `Read` on demand. `inline` dumps the file contents directly into the brief.

### `load_config(project_root) -> Config`

`packages/lattice-curator-core/src/lattice_curator_core/config.py:49`. Reads `.lattice-curator.json`; on `FileNotFoundError` / `PermissionError` returns `Config()` (defaults); on parse/validation error, prints a stderr warning and returns defaults.

### `make_bedrock(config) -> ChatBedrockConverse`

`packages/lattice-curator-core/src/lattice_curator_core/bedrock.py:7`.

- Model: `LATTICE_CURATOR_MODEL` env or `config.model`.
- Region: `AWS_DEFAULT_REGION` or `AWS_REGION` env, default `us-east-1`.
- `temperature=0`, `max_tokens=2048`.

### `append_fire(entry, path, opts?)`

`packages/lattice-curator-core/src/lattice_curator_core/log.py:45`.

- Default `max_bytes = 10 MB`, `max_rotations = 3`.
- Rotates `<path>` → `<path>.1`, bumping `.1 → .2`, `.2 → .3`; drops `.3`.
- Writes one JSON object per line via `entry.model_dump(by_alias=True)` (camelCase keys on disk).

### `seed_knowledge(dest, *, overwrite=False) -> list[Path]`

`packages/lattice-curator-core/src/lattice_curator_core/seed.py:20`. Recursively copies `.md` files from the bundled `knowledge/` resources tree into `dest`. Idempotent — preserves existing files unless `overwrite=True`. Returns the list of paths it actually wrote.

### `wiki_source(vault_dir) -> Source`

`packages/lattice-curator-core/src/lattice_curator_core/sources/wiki.py:45`. `name = "wiki"`. Walks `<vault_dir>/**/*.md`. Skips files whose frontmatter lacks a `description: <str>` field. Tags entries `{"kind": <frontmatter.kind | "page">}`.

### `experts_source(rules_dir) -> Source`

`packages/lattice-curator-core/src/lattice_curator_core/sources/experts.py:55`. `name = "experts"`. Same walk + filter. Tags entries `{"domain": <top-level-subfolder | "shared">, "impact": <frontmatter.impact | "unknown">}`.

## Configuration

### `Config` (Pydantic)

Loaded from `<project_root>/.lattice-curator.json`. Defined at `packages/lattice-curator-core/src/lattice_curator_core/config.py:37`.

| Field | Default |
|---|---|
| `sources.wiki.enabled` | `True` |
| `sources.wiki.vault_dir` | `"wiki"` |
| `sources.experts.enabled` | `True` |
| `sources.experts.rules_dir` | `"lattice/knowledge"` |
| `model` | `"us.anthropic.claude-haiku-4-5-20251001-v1:0"` |
| `mode` | `"hybrid"` |
| `gate.min_prompt_length` | `40` |
| `gate.debounce_seconds` | `30` |
| `gate.topic_shift_threshold` | `0.4` |
| `gate.stale_skill_seconds` | `1800` |
| `budgets.pass1_timeout_ms` | `4000` |
| `budgets.pass2_timeout_ms` | `5000` |
| `budgets.minute_budget_seconds` | `30` |

Note: `budgets.*` are declared but not currently enforced anywhere in the source — `pass1_timeout_ms` / `pass2_timeout_ms` are not wired into the LangGraph nodes, and `minute_budget_seconds` is not consulted by the hook or MCP server.

## Types

All defined in `packages/lattice-curator-core/src/lattice_curator_core/types.py`.

```python
Stage = Literal["brainstorming", "writing-plans", "execute-plan", "debugging", "generic"]
Mode  = Literal["hybrid", "inline"]
```

| Class | Fields |
|---|---|
| `GateConfig` (Pydantic) | `min_prompt_length=40`, `debounce_seconds=30`, `topic_shift_threshold=0.4`, `stale_skill_seconds=1800` (camelCase aliases on the wire) |
| `SkillMarker` (Pydantic) | `name: str`, `at: int` (epoch ms) |
| `GateInput` (Pydantic) | `prompt`, `transcript_tail`, `now`, `last_fire_at?`, `last_skill?`, `config?` |
| `GateDecision` (Pydantic) | `fire: bool`, `reason: str`, `stage: Stage = "generic"`, `hint: str` |
| `BriefExcerpt` (dataclass) | `path`, `excerpt` |
| `BriefSeeAlso` (dataclass) | `path`, `one_liner`, `full_content?` |
| `Brief` (dataclass) | `stage`, `summary`, `must_know`, `see_also`, `diagnostics` |
| `FireEntry` | `ts`, `stage`, `gate: dict`, `model`, `picks`, `pass1_tokens`, `pass2_tokens`, `brief_bytes`, `mode`, `outcome`, `transcript_tail_hash` |

## Stages

`StageDef` dataclass (`packages/lattice-curator-core/src/lattice_curator_core/stages/brainstorming.py:6`):

```python
@dataclass
class StageDef:
    name: str
    selection_target: dict  # {"min": int, "max": int}
    pass1_prompt: str
    pass2_prompt: str
```

`get_stage(name) -> StageDef` (`packages/lattice-curator-core/src/lattice_curator_core/stages/__init__.py:18`) — falls back to `generic` for unknown names.

| Stage | min | max | Pass 1 emphasis |
|---|---|---|---|
| `brainstorming` | 4 | 8 | prior decisions, related concepts, anti-patterns, ADRs |
| `writing-plans` | 3 | 6 | package boundaries, file maps, test conventions, contracts |
| `execute-plan` | 2 | 5 | the specific package overview + immediately relevant rules + cited files |
| `debugging` | 3 | 6 | prior incidents, gotcha rules, ADRs about the affected area, similar past fixes |
| `generic` | 3 | 6 | most relevant entries (untyped) |

## See also

- [[wiki/packages/lattice-curator-core/patterns]] — the gate → retrieve → format pipeline narrative
- [[wiki/packages/lattice-curator-core/context]] — concepts, decisions, why the boundary is shaped this way
- [[wiki/plugins/lattice-curator/lattice-curator]] — how the plugin wraps these primitives in hooks + MCP
