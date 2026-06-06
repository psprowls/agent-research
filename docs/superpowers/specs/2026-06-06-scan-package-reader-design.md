# Scan Package Reader Design

Date: 2026-06-06
Status: approved for spec review

## Goal

Expand Bedrock-backed `gw scan` so narrated scans can initialize source-backed
entity pages beyond scanner-owned prose and file-map descriptions. The new pass
fills human-owned sections that still contain TODO placeholder text on
`package`, `app`, `agent_plugin`, and `test_suite` entity pages.

The pass is placeholder-only. Any human-owned section with real content is
skipped, even when the entity is commit-dirty. Existing drift flagging and
proposal flows remain responsible for later maintenance of curated human prose.

## Non-Goals

- Do not rewrite or refresh already-filled human-owned sections.
- Do not target `repository`, `domain`, or `dependency` pages in v1.
- Do not create proposal ledger notes for simple TODO initialization.
- Do not change the Claude plugin structural scan path; `--no-narrate` remains
  Bedrock-free.
- Do not broaden scan into cross-vault synthesis. The reader stays focused on
  the source-backed entity page being initialized.

## Current Behavior

`run_scan()` already separates entity rendering into several passes:

1. `write_entities()` renders graph-derived entity pages and preserves
   human-owned sections.
2. Narrator fan-out fills the scanner-owned `## Narrative` section.
3. File-map injection renders scanner-owned file maps.
4. Code-reader fan-out fills remaining file-map `— TODO` description rows.
5. The scan stamps `last_updated_commit` when refreshed prose or file-map
   descriptions are complete.
6. Human-section drift flagging compares curated human sections against the
   refreshed scanner-owned ground truth.

Entity templates also seed human-owned sections such as `## Purpose`,
`## Public API`, app runtime sections, agent-plugin `## How it fits together`,
and test-suite conventions. These sections are preserved across rescans, but
their TODO placeholders are not currently initialized by Bedrock scan.

## Proposed Pipeline

Add a post-file-map package-reader pass inside `run_scan()` when `narrate=True`.
The pass runs after file-map descriptions are filled and before
`last_updated_commit` stamping, drift flagging, and optional drift propagation.

The pass:

1. Collects entity pages whose kind is `package`, `app`, `agent_plugin`, or
   `test_suite`.
2. Reads each page and identifies human-owned H2 sections whose body is still
   TODO-like.
3. Dispatches one `package_reader` task per entity page with at least one TODO
   human section.
4. Provides entity metadata, current page content, requested headings, file-map
   context when present, graph details when available, and bounded source tools.
5. Parses structured JSON replacements keyed by exact H2 heading.
6. Applies a replacement only when the current on-disk section still has a
   TODO-like body for that exact heading.
7. Records successful fills so they participate in the existing
   `last_updated_commit` stamp gate.

This keeps ownership local and deterministic. The model proposes markdown for
requested sections, while local code decides whether writing that markdown is
allowed.

## Target Entity Kinds

The v1 target set is source-backed entity pages:

- `package`
- `app`
- `agent_plugin`
- `test_suite`

These kinds have concrete roots in the repo and templates with actionable TODO
human sections. `repository`, `domain`, and `dependency` pages are deferred
because their useful human sections require broader synthesis or external
package-manager context rather than entity-local source reading.

## Model Role

Add a distinct `package_reader` role to `model_adapter/models.toml`.

Initial default:

- model: `moonshotai.kimi-k2.5`
- region: `us-east-1`
- max tokens: larger than `narrator` and file-map describer, because the role
  writes multi-section markdown
- max concurrency: lower than cheap scan roles to keep source-reading fan-out
  controlled

The role must remain separate from `code_reader`. `code_reader` has two existing
contracts: query fallback with source quoting, and scan-side file-map
description filling. `package_reader` is a broader page-initialization role with
a different prompt, tool surface, and JSON result schema.

## Context And Tools

Each package-reader task starts with a structured context packet:

- entity URI, kind, name, graph path, language, and relevant frontmatter
- current entity page content
- exact requested H2 headings and their current TODO bodies
- the refreshed `## Narrative` section when present
- the refreshed `## File map` section when present
- graph description or graph match details when the graph DB is available
- the entity root path that bounds repository reads

The model can use a bounded tool loop. Initial tools:

- `read_repo_file(path)`: read a repo-relative file under the entity root, with
  path traversal protection and a byte cap
- `list_repo_tree(path)`: list a shallow repo-relative tree under the entity
  root, with path traversal protection and an entry cap
- `cg_find`: existing graph grounding tool when the graph DB is available
- `cg_describe`: existing graph grounding tool when the graph DB is available
- `read_wiki_page(path)`: bounded read under `<workspace>/wiki`, intended for
  nearby entity pages only

The v1 tool surface intentionally excludes broad wiki search. The job is to
fill placeholders on this entity from source-backed context, not discover new
cross-vault architecture.

Tool-loop bounds:

- max 5 tool-call iterations
- per-file byte cap, with truncated reads clearly marked
- per-tree entry cap
- no reads outside the repo root, outside the entity root for repo tools, or
  outside `<workspace>/wiki` for wiki tools

If the graph DB is unavailable, graph tools are omitted and the prompt states
that graph tools are unavailable.

## Output Contract

The model returns one JSON object:

```json
{
  "sections": [
    {
      "heading": "Purpose",
      "replacement_markdown": "One paragraph..."
    },
    {
      "heading": "Public API",
      "replacement_markdown": "- `module.fn()` - `src/module.py:12` - purpose"
    }
  ]
}
```

Rules:

- `heading` must match one of the requested H2 headings without the leading
  `##`.
- `replacement_markdown` is the body of the H2 section only; it must not include
  the H2 heading.
- The model may omit any section it cannot support.
- The model must not return headings that were not requested.
- The model should cite concrete code with backticked `path:line` references
  where useful.
- The model must not include page frontmatter, scanner-owned sections, or whole
  page rewrites.

Local parsing drops invalid entries, non-requested headings, empty replacement
bodies, and replacements that still look like TODO placeholders.

## TODO Detection And Replacement

Add `wiki_io` helpers that reuse the existing H2 splitting and scanner-owned
heading rules:

- enumerate human-owned H2 sections
- identify TODO-like section bodies
- replace a specific H2 body only when the current body is still TODO-like

A TODO-like human section is any human-owned H2 whose body is empty or contains
only placeholder guidance, including the existing `> TODO: ...`, `TODO ...`, or
`— TODO` template shapes. Scanner-owned sections (`## Narrative`, `## File map`,
`## Referenced in wiki`) are excluded. Scanner-data sections on
`agent_plugin` pages (`## Commands`, `## Agents`, `## Skills`, `## Scripts`,
`## Hooks`, `## MCP servers`) are also excluded because they are
template-authoritative graph projections.

The writer must re-read the page immediately before applying replacements. This
prevents stale model output from overwriting a section that changed while the
model was running.

## Stamping And Drift

Successful package-reader fills join the existing `last_updated_commit` stamp
reason. A page can advance its anchor to the current HEAD when:

- it received good narrator prose, or
- it had file-map rows re-described, or
- it had at least one human TODO section filled by `package_reader`,

and it has no remaining file-map TODO rows.

This preserves the existing refill gate while allowing freshly initialized
human sections to be considered current with the scan that produced them. Drift
flagging then runs after stamping and sees the initialized sections in their
final on-disk form.

When package-reader changes a human-owned section, any stale `drift_review`
frontmatter entries for that page must be cleared if they no longer match the
current section body. The existing drift clear behavior already treats a section
hash mismatch as resolved; the package-reader pass must preserve that invariant
by running before drift cleanup and by not leaving obsolete drift frontmatter on
a page whose TODO section was just replaced.

No new provenance key is required in v1. `last_updated_commit` continues to mean
the entity page was refreshed by the scan's Bedrock-backed entity-maintenance
passes at that commit.

## Error Handling

The package-reader pass is best-effort and must never abort scan.

Failure behavior:

- Bedrock stack unavailable: skip package-reader, as with other narrated-only
  scan passes.
- Task failure for one entity: leave that page's TODO sections unchanged and
  continue.
- Invalid JSON or schema mismatch: report an entity-specific error and apply
  nothing for that entity.
- Replacement for a non-requested heading: ignore it.
- Replacement for a heading that is no longer TODO-like on disk: skip it.
- Empty, unsupported, or still-placeholder replacement: skip that section.
- Tool-loop iteration cap: use final valid JSON when available; otherwise leave
  the page unchanged.

Errors should be added to `ScanResult.entity_errors` and summarized in the scan
log in the same partial-success style as narrator and file-describer errors.

## Testing

Focused tests should cover:

- `package_reader` role exists in model config and uses
  `moonshotai.kimi-k2.5`.
- Human TODO section detection excludes scanner-owned and scanner-data sections.
- Exact-section replacement fills TODO bodies and skips non-TODO bodies.
- `run_scan(narrate=True)` dispatches package-reader for `package`, `app`,
  `agent_plugin`, and `test_suite` pages with TODO human sections.
- `run_scan(narrate=False)` never imports or dispatches the package-reader path.
- Invalid JSON and failed package-reader tasks leave TODO sections unchanged and
  report errors.
- Successful package-reader fills join the existing stamp reason so
  `last_updated_commit` can advance when file-map TODO rows are clear.
- Successful package-reader fills invalidate stale `drift_review` frontmatter
  entries whose stored section hash no longer matches the changed section body.
- A no-op rescan skips package-reader once human TODO sections have real
  content.
- Tool context refuses reads outside the repo and outside the entity root.

Scoped verification:

```bash
uv run --package model-adapter pytest packages/model-adapter/tests/test_loader.py
uv run --package wiki-io pytest packages/wiki-io/tests/test_entity_human_sections.py
uv run --package graph-wiki-core pytest packages/graph-wiki-core/tests/unit/test_package_reader.py packages/graph-wiki-core/tests/unit/test_commands_scan.py
```

## Deferred

- Updating already-filled human-owned sections.
- Proposal-ledger review for package-reader findings.
- Broad wiki search or cross-vault retrieval.
- `repository`, `domain`, and `dependency` entity-page initialization.
- Eval-driven model selection for `package_reader`.
