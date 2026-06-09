# Design: the `guidance` feature & `guidance-io` package (base slice)

**Date:** 2026-06-08
**Status:** approved (base slice — name + frontmatter + package shape)
**Scope:** This spec covers *only* what to call the feature, its frontmatter schema, and
the base package skeleton. The importer (agent-skill → guidance synthesis), the
search/retrieval, the curator/injection step, the sidecar index, and lint rules are
**explicitly deferred** to follow-up specs.

## Background

We are adding the ability to import **agent skills** and reuse the technical knowledge
inside them. Rather than compiling that knowledge into new skills (the approach taken by
the `lattice-experts` experiment at `~/Personal/archive/experiments/lattice-experts/rules`,
where `rules/<domain>/<id>.md` files were compiled into role skills via static
`compose: {domain, impact}` filters), we will **curate the most task-relevant bits at
task time and inject them into context**.

The two models differ in their selection mechanism:

- **lattice-experts:** *static* — a build step filtered rules by `{domain, impact}` and
  compiled matches into each skill's body.
- **guidance (this design):** *dynamic* — at task time a curator searches the library,
  ranks bits by relevance to the task, and injects the winners.

That difference drives the frontmatter: dynamic curation rewards an explicit, machine- and
LLM-legible relevance signal on every page.

## Naming

The feature is **`guidance`**. The same word is the wiki folder, the `category:` value,
and the package name (`guidance-io`).

Rejected alternatives:
- `knowledge` — accurate but too broad; the entire wiki is knowledge, so it is a weak
  discriminator against `concepts`/`sources`.
- `rules` — implies hard enforcement (these are advisory context, not enforced) and
  collides conceptually with `.claude/rules/`.
- `practices` — viable, slightly more normative in tone than `guidance`.

`guidance` is prescriptive ("how to do X correctly"), cleanly distinct from the existing
**`concepts`** category (which is *descriptive* — what a pattern *is*), and does not
collide with agent `skills` (the import source) or `.claude/rules/`.

## Placement & nature

- **Category:** `guidance`, a new page type alongside `source`, `concept`, `work`, `adr`.
- **Location:** `<workspace>/wiki/guidance/<topic>/<slug>.md` — flat-within-topic,
  mirroring lattice's `rules/<domain>/<id>.md` layout.
- **Authorship:** pages are *synthesized* from imported agent skills (future task), not
  hand-written. Because a machine fills the frontmatter, richer frontmatter is cheap — this
  is the core reason the schema can carry both a prose and a structured relevance signal
  without an authoring-burden penalty.

## Frontmatter schema

```yaml
---
title: Use a List Virtualizer for Any List
category: guidance                # spine — fixed value
summary: Use a virtualizer (FlashList/LegendList) instead of ScrollView for lists.
topic: react-native               # taxonomy axis + folder name
applies_when: Rendering any scrollable list in React Native, even a short one.
triggers:                         # structured pre-filter — block + all keys optional
  globs: ['**/*.tsx']
  keywords: [ScrollView, FlatList, list, virtualization]
  entities: ['[[entities/pkg_...]]']   # graph hook — curate by code the task touches
tags: [performance, lists]
impact: high                      # critical | high | medium | low
source: vercel-labs/agent-skills/skills/react-native-skills   # provenance
updated: 2026-06-08
tokens: 0
---
```

### Field reference

| key | required | role |
|---|---|---|
| `title` | ✓ | wiki spine |
| `category` | ✓ | wiki spine — fixed value `guidance` |
| `summary` | ✓ | wiki spine — one-line; also a relevance signal |
| `topic` | ✓ | taxonomy axis; also the folder name under `wiki/guidance/` |
| `applies_when` | ✓ | one-sentence prose trigger; what the LLM curator ranks against |
| `impact` | ✓ | enum `critical \| high \| medium \| low`; ranking tiebreak + context-budget |
| `updated` | ✓ | wiki spine |
| `tokens` | ✓ | wiki spine |
| `triggers.globs` | optional | file globs for cheap deterministic pre-filter |
| `triggers.keywords` | optional | keywords for cheap deterministic pre-filter |
| `triggers.entities` | optional | `[[entities/...]]` URIs — ties guidance into the code graph |
| `tags` | optional | coarse free-form filter |
| `source` | optional | provenance — which imported skill/repo the bit came from |

### Design rationale: two relevance axes, not one choice

Selection has two separable jobs, and the schema serves both:

1. **Pre-filter (cheap, no LLM):** narrow the library to a candidate set. Served by
   `topic`, `tags`, and the structured `triggers` block (`globs`, `keywords`, `entities`).
2. **Rank/select (the LLM curator):** pick and justify winners from candidates. Served by
   `summary` + `applies_when` (prose the model judges relevance against), with `impact` as
   a tiebreak.

Carrying both a structured `triggers` block *and* a prose `applies_when` is deliberate:
frontmatter is data, not retrieval logic, so this pre-commits to no particular search
architecture. The future search task uses whichever signal it wants. Authoring cost is nil
because pages are synthesized.

### `impact` values

Lowercased to match this repo's YAML-enum convention (cf. `work.md`'s `status`/`kind`
enums), unlike lattice-experts' uppercase `CRITICAL|HIGH|MEDIUM|LOW`.

## Base package: `guidance-io`

Mirrors `work-io` (the closest precedent — a distinct page-family with its own `-io`
package and lifecycle helpers).

- **`pyproject.toml`** — `name = "guidance-io"`, `requires-python = ">=3.11"`, deps
  `workspace-io` + `pyyaml>=6.0` (add `wiki-io` only if we reuse its frontmatter
  primitives), `build-backend = "uv_build"`, the workspace source pin, and the standard
  pytest stanza (`testpaths = ["tests"]`, `asyncio_mode = "auto"`, `integration` marker).
  Register the member in the root workspace.
- **`src/guidance_io/frontmatter.py`** — `parse(text) -> (fm, body)` and `emit(fm) -> str`
  (copy `work_io.frontmatter`'s implementations verbatim — they are page-type-agnostic),
  plus `validate(fm)` enforcing: required keys present, `category == "guidance"`, `impact`
  in the enum, `topic` non-empty, and `triggers` (when present) is a mapping whose
  `globs`/`keywords`/`entities` are lists.
- **`src/guidance_io/paths.py`** — resolve `wiki/guidance/<topic>/<slug>.md`, slugify a
  title to `<slug>`, and list pages by topic.
- **`src/guidance_io/__init__.py`**

## Template & the one graph touch

- Add **`wiki-io/assets/page-templates/guidance.md`** — the frontmatter above plus a
  minimal body: `## Guidance` (the prose bit), optional `## Incorrect` / `## Correct`
  examples (carried over from the lattice rule body shape), and a `## Applies to` section
  that mirrors `triggers.entities` as `[[entities/...]]` wikilinks.
- The `## Applies to` body mirror is load-bearing: it is how the **existing backlink index**
  gives each referenced entity page a `## Referenced in wiki` backlink from guidance *for
  free*. This is the same frontmatter-key-plus-body-mirror pattern that work pages
  (`affects`) and the M3 suggestion step (`suggested_pages` → `## Suggested pages`) already
  use, so it composes with machinery that exists today.

## Deferred (named only so the schema leaves room)

- The importer: agent-skill → synthesized guidance pages.
- Search/retrieval over the guidance library.
- The curator/injection step that selects winners and writes them into task context.
- A `guidance-index.json` sidecar (analogous to `work-index.json`) for fast pre-filtering.
- Lint rules validating guidance frontmatter and topic taxonomy.

These will each get their own spec → plan → implementation cycle.
