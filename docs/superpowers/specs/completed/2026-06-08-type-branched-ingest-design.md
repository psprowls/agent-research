# Design: Type-Branched Ingest (`gw wiki ingest`)

**Date:** 2026-06-08
**Status:** approved
**Scope:** Adds a dispatcher to `run_ingest_source()` so each `source_type` can run
custom prompts and output logic. The first concrete branch is `skill`, which performs a
two-pass synthesis to write `guidance` pages directly. All other types continue on the
existing (default) path. Future branches (`pr`, `plan`, etc.) slot in without touching
the default path.

**Depends on:** `2026-06-08-guidance-package-design.md` (guidance frontmatter schema,
`guidance-io` base package, page template).

---

## Background

`gw wiki ingest` currently runs a single generic LLM call for every source type and
routes every result to `sources/`. The `source_type` field is descriptive only — it has
no effect on prompts or output behavior. As the wiki grows to handle richer source
material (agent skills, PRs, plans), a one-size-fits-all prompt produces mediocre results:
skills contain structured behavioral rules that need to be exploded into individual
guidance pages; PRs contain decision context that is better extracted as ADRs; plans
are better treated as ADR mines.

This design adds a dispatcher so each type can branch without disturbing the others.

---

## Architecture

### Dispatcher

`run_ingest_source()` already detects `source_type` early (step 4 of 13). After that
detection, control passes to a branch function. Both branches return an intermediate
`_IngestBranchResult` (internal typed dict or dataclass) that the shared tail consumes.

```
run_ingest_source()
  ├── [unchanged] resolve paths, graph, extract text, detect source_type
  ├── dispatch:
  │    ├── "skill"  → _run_skill_branch(text, source_path, source_type, ...)
  │    └── default  → _run_default_branch(text, source_path, source_type, ...)
  └── _run_common_tail(branch_result, ...)
       ├── slug write + wikilink resolve
       ├── entity forward-link
       ├── update_index(wiki)
       └── append_log(wiki, ...)
```

Both branch functions return a dict of fields the common tail needs: at minimum
`target_slug`, `page_body`, `frontmatter_dict`, `entity_uri`, `guidance_pages_written`.
The tail writes the source page, resolves wikilinks, updates the index, and appends the
log — behavior that is identical for all branches.

The source page is **always** written by the common tail — both branches produce one.
The `skill` branch additionally writes guidance pages before handing off to the tail.

### IngestResult extension

`IngestResult` (in `ingest.py`) gains one new field:

```python
guidance_pages_written: list[str] = field(default_factory=list)
```

Paths (workspace-relative) of guidance pages created or updated by the skill branch.
Empty list for all other branches.

---

## Source Type Extension

`wiki-io/src/wiki_io/ingest_source.py`:

```python
SOURCE_TYPE_ENUM = frozenset({
    "spec", "article", "pr", "ticket", "transcript",
    "example", "doc", "note", "skill",   # ← added
})

RAW_FOLDER_TYPES = frozenset({
    "spec", "article", "pr", "ticket", "transcript",
    "example", "skill",                  # ← added
})
```

Adding `skill` to `RAW_FOLDER_TYPES` makes `raw/skill/` authoritative — the same way
`raw/spec/` works today. Files outside `raw/skill/` that look like skills are still
classified by LLM inference.

---

## Skill Branch — Two-Pass Flow

### Pass 1: Planner (single LLM call, `skill_planner` role)

Input: full skill text + project context.

The planner decides the chunking strategy from the content:
- **Rules / atomic directives** → one guidance page per rule
- **How-to / instructional flows** → one guidance page for the whole skill

Output: a YAML list of chunk plan entries. Each entry contains all fields needed to
synthesize the final page without re-reading the source:

```yaml
- title: "Use a List Virtualizer for Any List"
  slug: use-list-virtualizer
  topic: react-native            # → wiki/guidance/<topic>/
  summary: "One-line summary for wiki spine."
  applies_when: "Rendering any scrollable list in React Native."
  impact: high                   # critical | high | medium | low
  triggers:
    globs: ['**/*.tsx']
    keywords: [FlatList, ScrollView]
    entities: []
  content: |
    Full extracted/paraphrased body for this guidance chunk. ...
```

The planner infers `topic` from the skill's domain (e.g., a brainstorming skill →
`topic: brainstorming`), not from the filename.

### Pass 2: Synthesis (one LLM call per chunk, `skill_synthesizer` role)

Parallelized via `SubagentPool` (same pattern used by `scan` narration).

Each call receives one plan entry and emits a complete guidance page: frontmatter per
the guidance-io schema + `## Guidance` body + optional `## Applies to` section
(populated when `triggers.entities` is non-empty). Pages are validated via
`guidance_io.frontmatter.validate()` before writing.

Written to: `wiki/guidance/<topic>/<slug>.md` (via `guidance_io.paths`). If the page
already exists it is **overwritten** — re-ingesting a skill regenerates its guidance
pages, same as re-scanning regenerates entity pages.

### Error handling

If the planner call fails or emits unparseable YAML, the skill branch logs the error
and falls back to the default branch for that ingest (source page still written, no
guidance pages produced, `guidance_pages_written` empty). Same best-effort pattern used
by the existing suggest phase.

### Source page reference

After both passes, the source page body includes a `## Generates` section listing
wikilinks to each written guidance page, e.g.:
`[[guidance/brainstorming/explore-before-implementing]]`. This makes the
skill→guidance provenance traceable from the sources vault.

---

## Prompt Architecture

Three prompt locations:

| File | Role | Used by |
|---|---|---|
| `prompts/ingestor.py` | Default ingestor system prompt | Default branch (unchanged) |
| `prompts/skill_planner.py` | Skill planner system prompt | Skill branch, Pass 1 |
| `prompts/skill_synthesizer.py` | Skill synthesizer system prompt | Skill branch, Pass 2 |

**`prompts/skill_planner.py`** instructs the LLM to:
- Treat the source as agent behavioral guidance, not generic documentation
- Identify natural chunk boundaries (rule = separate page, instructional = whole)
- Infer `topic` from the skill's domain
- Emit a valid YAML list matching the chunk plan schema
- Never emit more than one page for tightly coupled instructions

**`prompts/skill_synthesizer.py`** instructs the LLM to:
- Produce one complete guidance page from one plan entry
- Emit valid frontmatter per the guidance-io schema (`category: guidance` is fixed)
- Write a focused `## Guidance` body — no padding, no restating the title
- Add `## Applies to` only when `triggers.entities` is non-empty
- Begin the response with `---` (no markdown code fence)

The existing `prompts/ingestor.py` is **unchanged** — it already handles all non-skill
types correctly via the `_SOURCE_LANDING` and `_INGESTOR_RULES` fragments.

Future branch prompts follow the same pattern: one file per new role, composed from
`_fragments/` where appropriate.

---

## Suggestion Phase Branching

The suggestion phase (`run_suggest_phase()`) is **skipped for `skill` ingest** — guidance
pages are written directly in Pass 2, so there is nothing to propose to the ledger.

For future type customization, `run_suggest_phase()` gains an optional `allowed_kinds`
parameter (defaults to the current full set `{"concept", "adr", "architecture"}`):

```python
def run_suggest_phase(..., allowed_kinds: frozenset[str] | None = None) -> ...:
    kinds = allowed_kinds if allowed_kinds is not None else SUGGESTION_KINDS
    ...
```

| source_type | suggestion behavior |
|---|---|
| `skill` | skipped — guidance pages written directly |
| `pr` | `run_suggest_phase()` with full kinds (future branch) |
| `plan` | `run_suggest_phase()` with `allowed_kinds={"adr"}` (future branch) |
| default | `run_suggest_phase()` with full kinds (unchanged) |

---

## Default Branch

The default branch is the current `run_ingest_source()` logic, extracted without
modification into `_run_default_branch()`. No behavioral change.

---

## Future Branches

Adding a new branch requires:
1. A new `elif source_type == "<type>":` in the dispatcher
2. A new `_run_<type>_branch()` function
3. One or more new prompt files under `prompts/`

The default and common-tail paths are not touched. The `allowed_kinds` parameter on
`run_suggest_phase()` covers suggestion filtering without a separate branch.

---

## Out of Scope

- The guidance-io package itself (covered by `2026-06-08-guidance-package-design.md`)
- Guidance search, retrieval, and context injection (future specs)
- `guidance-index.json` sidecar
- Lint rules for guidance frontmatter
- Full `pr` and `plan` branch implementations (named only for extensibility context)
