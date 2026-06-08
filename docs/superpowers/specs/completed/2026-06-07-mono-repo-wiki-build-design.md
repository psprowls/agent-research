# Design: build a usable mono-repo wiki (eval prerequisite)

**Date:** 2026-06-07
**Status:** approved (brainstorm) → ready for implementation plan
**Relationship:** prerequisite sub-project for
[`2026-06-07-cc-eval-wiki-design.md`](./2026-06-07-cc-eval-wiki-design.md) ("step zero").
The eval consumes the frozen wiki this sub-project produces.
**Execution model:** this is a **migration spec + runbook**. The work is executed by the
user (or a separate Claude session), not by the brainstorming session. The spec therefore
states exact rules, gates, and checklists precise enough for another session to follow.

## Problem

The cc-eval three-arm eval (`base` / `injected` / `plugin`) needs an accurate mono-repo
wiki, frozen at `baseline_sha: 551f7ed8b9c0b4f51a4000302548e24284729652`, with:
- a healthy **entity graph** (scanner-generated entity pages), and
- a comprehensive **curated knowledge layer** (concepts / ADRs / architecture / sources /
  work) — because the eval's discriminators, especially `impossible-without-wiki`, depend
  on prescriptive/tribal knowledge a scan does not manufacture.

## Current state (verified 2026-06-07)

| Layer | State |
|---|---|
| Entity graph | **Done & healthy.** Live workspace `~/Personal/mono-repo/graph-wiki/`; `repo:psprowls/mono-repo`; 254 entity pages (48 package, 3 app, 25 test_suite, 177 dependency, 1 repository); graph DB 5122 nodes, 85.8% with path (pathless = legitimate `unresolved_symbol` externals). Scenario-relevant pages present: `pkg_common-ui-shadcn-ts`, `pkg_timeline-domain-ts`, `app_web-next-ts`. |
| Scan errors | 3 package-reader failures the user fixes manually: `personal-turborepo` (missing graph path), `@psprowls/location-data-node-ts` (empty response), `@psprowls/shared-aws-node-ts` (iteration cap 50). |
| Curated layer | **Absent** in the live workspace (only empty category `index.md`). |
| Source for curated layer | **Comprehensive, version-compatible backup** at `~/Personal/archive/mono-repo-workspace-backup/` — 97 curated pages (29 concepts, 12 ADRs, 2 architecture, 10 sources, 44 work) + a `raw/` dir, describing **mono-repo** (correct repo), generated at a compatible schema version. |

### Parser status (resolves a prior risk)

The TS/TSX parser gaps that earlier notes flagged are **fixed on `develop`**: `grammars.py`
registers the `tsx` grammar and `.tsx` routes to it; arrow-function consts are emitted
(`_generic.py` `_arrow_consts_in`); import edges resolve (`projections/graph.py`). The
85.8% path coverage on a TS/TSX monorepo confirms the entity graph is high-fidelity. **No
parser work is in scope.**

## Goals

- Migrate the backup's curated pages into the live workspace under the **current schema**.
- Make the wiki internally consistent (links resolve, backlinks regenerate, lint clean).
- Guarantee the **scenario-relevant subset is accurate at `551f7ed8`**.
- Freeze the result as the eval's immutable artifact.

## Non-goals

- Fixing the parser (already fixed).
- Authoring net-new knowledge beyond small gap-fills where a scenario needs a convention
  the backup doesn't already cover.
- Rebuilding the entity graph from scratch (it's done; only a re-scan to refresh backlinks
  after import is needed).
- Any change to `claude-code-evals` code (that's the consumer spec).

## The migration (the core work)

### 1. Import curated pages

Copy from `~/Personal/archive/mono-repo-workspace-backup/wiki/` into
`~/Personal/mono-repo/graph-wiki/wiki/`: the `concepts/`, `adrs/`, `architecture/`,
`sources/`, `work/` page sets, and the `raw/` ingest sources. **Do not** overwrite the
freshly scanned `entities/` pages. Preserve each category's `index.md` convention.

### 2. Migrate wikilinks (the fiddly part — scripted, with a report)

The old wiki had **no** `packages/` / `apps/` / `domains/` / `entities/` folders; curated
pages reference code entities by **bare slug** (`[[location-aws-node-ts]]`, `[[timeline]]`,
`[[activities-data-node-ts]]`). The current schema uses a single `entities/` folder with
**prefixed filenames** (`pkg_`, `app_`, `domain_`, `dep_`, `unit_tests_`).

Rewrite rules:
- **Code-entity links** → `[[entities/<prefix>_<name>]]`, resolved against the *actual*
  filenames in `~/Personal/mono-repo/graph-wiki/wiki/entities/`. Build the resolution
  table by listing that dir; match the bare slug to exactly one entity file.
- **Concept / ADR / work / architecture / source links** (e.g. `[[global-context]]`,
  `[[0001-adopt-llm-maintained-wiki]]`, `[[2026-04-domain-device]]`) → **pass through
  unchanged** (their target pages are imported in step 1).
- **Preserve** any `[[target#anchor]]` and `[[target|alias]]` suffixes.

**No silent drops.** Emit a report of:
- bare slugs that match **zero** entity files (broken — needs manual decision), and
- bare slugs that match **more than one** (ambiguous, e.g. `timeline` →
  `domain_timeline` vs `pkg_timeline-domain-ts`) — needs manual disambiguation.

### 3. Conform frontmatter / templates

Backup frontmatter is `title / category / summary / tags / sources / updated` — close to
current. Adjust only where the current curated-page template differs. The `@handle` YAML
trap (`authors: [@psprowls]` → invalid YAML → silent backlink loss) is **confirmed absent**
in the backup; if any quoted/unquoted handle appears during conform, quote it.

### 4. Re-scan + lint

- **Re-scan** the workspace so entity pages' `## Referenced in wiki` backlinks regenerate
  against the imported curated pages (backlinks are scanner-derived from wikilinks).
- Run **`/graph-wiki:lint`**; fix broken links, orphans, missing frontmatter, duplicate
  titles, and format drift until clean (or until only intentional items remain, logged).

### 5. Verify scenario-relevant subset at `551f7ed8`

The pages the eval's verdicts depend on must be accurate at the pinned commit. At minimum:
- the **api-client** convention (the backup's `concepts/shared-api-client.md` plus whatever
  states "use the sanctioned domain client, not raw axios"),
- the **design-tokens** convention (semantic color tokens + `cva` variant pattern + `cn`),
- the **impossible-without-wiki** decision source (a real ADR/concept capturing a tribal
  decision the code itself doesn't disambiguate — chosen from the imported set).

Bulk staleness elsewhere in the 97 pages is acceptable (even realistic for the `plugin`
arm). Only the scenario subset is gated. Where a needed convention isn't covered by the
backup, hand-author a single minimal concept/ADR page (gap-fill).

### 6. Freeze in place

The working dir `~/Personal/mono-repo/graph-wiki/` **is** the frozen artifact, pinned via a
git commit/tag; the eval references that ref. **Open item to resolve at freeze time:**
confirm whether `mono-repo/graph-wiki/` is tracked by mono-repo's git (then it's a mono-repo
commit/tag) or should be its own git repo (then init + tag there). The eval's step zero
records the exact frozen ref.

## Success criteria

- All 97 backup curated pages present in the live workspace under the current schema.
- Wikilink migration run; **zero** unresolved/ambiguous links remain (all either rewritten
  or manually resolved); the report is empty or every entry is dispositioned.
- Re-scan completed; entity pages show regenerated `## Referenced in wiki` backlinks.
- `/graph-wiki:lint` clean (or residual items logged as intentional).
- Scenario-relevant subset verified accurate at `551f7ed8`.
- The 3 package-reader error pages resolved.
- Workspace frozen at a recorded git ref; eval's step-zero updated to point at it.

## Risks / watch-items

- **Ambiguous bare-slug links** (`timeline`, `shared`, `reference`) — the resolution report
  exists precisely to surface these; resolve by hand against intended entity.
- **Schema drift** between backup and current template — the user judges it "close"; the
  conform step + lint catch the rest.
- **Re-scan overwriting curated content** — only scanner-owned sections regenerate; curated
  `concepts/adrs/...` pages and human-owned entity sections are preserved (per the
  ownership model in `.claude/rules/backward-compatibility.md`). Verify after re-scan.

## Deferred / out of scope

- Parser work (fixed).
- Net-new knowledge authoring beyond scenario gap-fills.
- The eval harness code changes (consumer spec).
