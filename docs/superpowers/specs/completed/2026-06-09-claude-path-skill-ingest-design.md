# Claude-path skill ingest → guidance pages

**Date:** 2026-06-09
**Status:** Approved — ready for implementation plan
**Scope:** Teach the Claude Code plugin (agent) ingest path to recognize a skill and break it into guidance pages, reaching parity with the already-built Bedrock path.

## Problem

The Bedrock ingest path (`graph-wiki-core/commands/ingest.py::run_ingest_source`) already
detects a skill anchor, calls `gather_skill_sources`, and runs a two-pass
**planner → synthesizer** (real `make_llm` calls) that writes
`wiki/guidance/<topic>/<slug>.md` pages.

The **Claude plugin path** has zero skill awareness. The plugin shim
(`plugins/graph-wiki/skills/graph-wiki/scripts/ingest_source.py`) builds a *brief* that the
`ingestor` agent acts on — code preps, the agent reasons and writes. But the brief builders
in `packages/wiki-io/src/wiki_io/ingest_source.py` (`build_ingest_brief` /
`build_folder_ingest_brief`) don't know about skills. Point the plugin ingest at a skill
directory today and it falls into the generic folder brief (file list + representative file),
so the agent writes one ordinary source page — no guidance chunking.

This spec brings the Claude path to parity, in the Claude path's idiom.

## Idiom (the constraint that shapes everything)

The Claude path's philosophy: **Python preps a brief, the agent does the reasoning and
writing** — unlike Bedrock, where Python makes the LLM calls. So the chunking intelligence
lives in the agent, guided by a reference doc; Python only gathers the skill and emits a
manifest. **No new LLM-call machinery is added to the plugin path.**

## Data flow

```
/graph-wiki:ingest <skill-dir>
  → ingest_source.py shim
      resolve_skill_anchor(src)  ──not a skill──▶  existing file/folder brief (unchanged)
            │ is a skill
            ▼
      build_skill_ingest_brief(anchor, wiki, repo, workspace_root)   ← NEW, in wiki_io
            │  (reuses gather_skill_sources + _build_entity_match + compute_state_gate)
            ▼
      JSON manifest brief  ──▶  ingestor agent Reads included_files, chunks, writes pages
                                  per references/ingest-workflow.md (NEW skill section)
```

The agent runs the script with `--json`, reads the manifest, then **Reads the
`included_files` itself** before writing — exactly as the current flow Reads sources directly.

## Components

### 1. `build_skill_ingest_brief` (new, `packages/wiki-io/src/wiki_io/ingest_source.py`)

Pure / Bedrock-free, consistent with the sibling builders. Reuses `gather_skill_sources`,
`_build_entity_match`, and `compute_state_gate`.

Signature:

```python
def build_skill_ingest_brief(
    anchor: Path, wiki: Path, repo: Path, workspace_root: Path
) -> dict: ...
```

Returns:

```json
{
  "is_skill": true,
  "source_path": "<skill_dir>",
  "title": "<bundle.title or derived>",
  "source_type": "skill",
  "slug": "<slug>",
  "suggested_summary_path": "sources/<YYYY-MM>-<slug>.md",
  "merge_mode": false,
  "guidance_dir": "guidance/",
  "included_files": ["SKILL.md", "references/advanced.md"],
  "excluded_files": ["scripts/helpers.py"],
  "scripts_dominant": false,
  "warnings": [],
  "entity_match": {"uri": null, "entity_filename": null},
  "state_gate": {"allowed": true, "reason": null, "head_commit": "..."}
}
```

Notes:
- `title` falls back to `slugify`-of-stem the same way `build_ingest_brief` does when the
  bundle has no title.
- `slug = slugify(title)`.
- `suggested_summary_path` uses the same `YYYY-MM`-prefixed `sources/` convention as
  `build_ingest_brief`. `merge_mode` is `(wiki / suggested).exists()`.
- `warnings` carries `"scripts_dominant"` when `bundle.scripts_dominant` is true (a skill
  that is mostly non-markdown scripts is a weak guidance candidate — the agent surfaces this).
- `included_files` / `excluded_files` are `bundle.included_files` / `bundle.excluded_files`
  verbatim (skill_dir-relative POSIX, transitive-link-resolved order).

### 2. Shim routing (`plugins/graph-wiki/skills/graph-wiki/scripts/ingest_source.py`)

Bedrock branch is **untouched** — `gw wiki ingest source` already handles skills end to end.

Claude branch: after resolving `source_path`, compute the anchor on the resolved path
(`resolve_skill_anchor(_source_for_branch(source_path, repo))`). Route order:

1. anchor is non-None → `build_skill_ingest_brief(...)` → skill-aware output
2. else resolved path `is_dir()` → existing `build_folder_ingest_brief(...)`
3. else → existing `build_ingest_brief(...)`

Skill detection must come **before** the `is_dir()` check (a skill is a directory).

Human-readable (non-`--json`) skill output prints: title, source type, `N included / M
excluded files`, the `scripts_dominant` warning when present, the suggested source path, the
target `guidance/` dir, and the entity match when one resolved.

### 3. `references/ingest-workflow.md` — new "Skill → guidance pages" section

The agent-facing chunking spec. A faithful port of the Bedrock `skill_planner` /
`skill_synthesizer` system-prompt rules, so both paths agree on what guidance pages look like.

- **Detection:** the brief carries `is_skill: true`; route to this section instead of the
  normal single-source-summary flow.
- **Chunking rules:**
  - Atomic directives / rules → one guidance page each.
  - A how-to / instructional flow → one guidance page for the whole skill.
  - Never split tightly-coupled steps across pages.
  - Prefer fewer, larger pages. Preserve content verbatim where practical — the goal is
    smaller, targetable chunks, not rewrites.
- **Inline guidance frontmatter schema** (so the agent needs no vault template file):
  `title`, `category: guidance` (fixed), `summary`, `topic` (kebab folder slug),
  `applies_when`, `triggers: {globs, keywords, entities}`, `tags`, `impact`
  (critical|high|medium|low), `source`, `updated` (YYYY-MM-DD, today), `tokens` (0).
  Body sections: `## Guidance`, `## Incorrect`, `## Correct`, `## Applies to`.
- **Targets:** write each page to `wiki/guidance/<topic>/<slug>.md`. Set the guidance page's
  `source:` to the skill's source page (`[[sources/<YYYY-MM>-<slug>]]`).
- **Source page:** `source_type: skill`, with `## Summary`, `## Generates` (wikilinks to each
  written guidance page), and `## Excluded` (the non-`.md` files, when any) — matching the
  Bedrock source-page shape.
- **Known-gap note:** `## Applies to` `[[entities/...]]` links do **not** yet produce entity
  backlinks (`guidance` is absent from `backlink_index._PRESERVED_WIKI_DIRS`). The agent
  still writes the links; the backlink wiring is a separate, out-of-scope change.

### 4. Markdown touch-ups

- `plugins/graph-wiki/agents/ingestor.md` — add a skill branch note: a skill source routes to
  guidance pages under `wiki/guidance/`, not a single source summary; point at the new
  reference-doc section.
- `plugins/graph-wiki/commands/ingest.md` — add a skill row to the source-types table and a
  one-line mention in "What happens".

### 5. Tests (`packages/wiki-io/tests/`)

Unit tests for `build_skill_ingest_brief`:
- skill **directory** (contains `SKILL.md`) → `is_skill: true`, correct included/excluded.
- bare **`SKILL.md` file** path → resolves to the same brief.
- `scripts_dominant` true → `warnings` contains `"scripts_dominant"`.
- excluded-files capture (non-`.md` under the dir).
- a **non-skill** path → builder is not invoked; existing folder/file builders still own it
  (assert via the shim routing, or a direct `resolve_skill_anchor` returns `None`).

Use the existing `tmp_repo` / `write_file` helpers in `packages/wiki-io/tests/helpers.py`.

## Out of scope (explicit)

- **Backlink-wiring fix** for guidance `## Applies to` links — pre-existing, affects both
  paths equally, fixed as its own focused change.
- **Code-driven / two-pass synthesis** on the Claude path — the agent does the chunking; we
  do not port the Bedrock planner/synthesizer into the plugin path.
- The Bedrock path and `gw wiki ingest source` — unchanged.

## Verification

- `uv run pytest packages/wiki-io/` green, including the new `build_skill_ingest_brief` tests.
- Manual: `ingest_source.py --source <a-real-skill-dir> --json` emits a skill brief with the
  expected `included_files` / `excluded_files`.
- `uv run ruff check packages/wiki-io/ plugins/graph-wiki/` clean on touched files.
