# Wiki page-template conformance audit — 2026-08-02

Read-only audit of how far the graph-wiki vault's live pages diverge from the 16 page
templates this repo ships, plus the defects and open decisions that fell out of it.

The vault audited is the one attached to this repo, at
`~/Personal/workspaces/agent-research/wiki/` (paths below are relative to that vault
root; code paths are relative to this repo). 409 non-archived pages, snapshot
2026-08-02 morning. Counts have since moved — another session added pages while this
was being written — so treat the percentages as a dated sample, not a live number.

Two companion pages live in the vault itself:

- `wiki/concepts/wiki-page-section-schema.md` — the contract: every template
  catalogued by its H2 content sections.
- `wiki/concepts/page-template-conformance-audit.md` — the full audit with all nine
  findings. This doc is the actionable extract.

## Where the templates come from

```
packages/wiki-io/src/wiki_io/assets/page-templates/   → 14 (entity-*, concept*, adr, source, proposal, index)
packages/work-io/src/work_io/assets/work.md           → work tracker
packages/work-io/src/work_io/assets/bodies/*.md       → 9 per-kind work bodies
packages/guidance-io/src/guidance_io/assets/guidance.md
                                                      ↓ registered in one place
packages/graph-wiki-core/src/graph_wiki_core/page_kind_templates.py:25
                                                      ↓ copied by wiki_io/init_vault.py:191
<workspace>/wiki/.templates/                          → live, reference-only copy
```

## Headline result

Conformance tracks **who writes the page**, not author discipline:

| Category | Pages | Conformant | Who writes the body |
|---|---:|---:|---|
| `proposals/` | 33 | **33 (100 %)** | rendered from `origins[]` |
| `entities/` | 52 | **52 (100 %)** | scanner + gated prose refresh |
| `work/` | 12 | 6 of 9 items | template picked mechanically by `kind:` |
| `adrs/` | 39 | 23 (59 %) full set; 39 core three | model, one template |
| `sources/` | 161 | 119 (74 %) | model, one template |
| `guidance/` | 83 | 30 (36 %) full set | imported from external skills |
| `concepts/` | 29 | 10 (34 %) | model, three templates, free choice |

Rendered bodies are exact. Mechanically-selected templates are near-exact. Everything
that asks a model to *recall* a section list degrades, and degrades further the more
templates it has to choose between. Only one heading-level lint rule exists in the
system — `check_scanner_heading`
(`packages/graph-wiki-core/src/graph_wiki_core/commands/lint_mechanical.py:226`),
guarding deterministic entity headings — and
`plugins/graph-wiki/skills/graph-wiki/references/page-formats.md:268` states outright
that body sections are recommended, not enforced. The divergence is an accurate read
of the design, not a violation of it.

## Defects — verified, unfixed

### D1 · `source_type` enum is contradictory

Three-way disagreement:

- `packages/wiki-io/src/wiki_io/assets/page-templates/source.md` declares
  `spec | article | pr | ticket | transcript | rfc | doc`
- `plugins/graph-wiki/skills/graph-wiki/references/page-formats.md:280` declares
  `spec | article | pr | ticket | transcript | example | doc | note`
- 20 live pages use `skill`, which appears in neither

The two declarations disagree with each other independently of `skill` (`rfc` vs.
`example`/`note`), so one was edited without the other. Eight declared values between
them; the vault uses exactly two (`spec` ×141, `skill` ×20).

**Fix:** pick one authority, add `skill`, drop the zero-instance values. Small.

### D2 · A deterministic entity heading on a curated page

`wiki/concepts/backlink-index.md` (`kind: concept`) carries `## Referenced in wiki` —
a heading in `DETERMINISTIC_SECTIONS`
(`packages/wiki-io/src/wiki_io/entity_writer.py:545`). That section is regenerated
every scan **on entity pages**; on a curated page nothing regenerates it, so it reads
as maintained while silently rotting.

**Fix:** delete the section. Trivial.

### D3 · Three work items have no `## Plan` table

- `wiki/work/2026-06-23-code-drift-check-reports-0-packages…` (`kind: bug`) — written
  in an RCA shape (Summary · Resolution · Symptom · Root cause · Suggested fix) where
  `bodies/bug.md` prescribes Steps to reproduce · Expected vs actual · Plan · Notes / log
- `wiki/work/2026-06-11-add-release-command…` (`kind: feature`) — also uses `## Notes`
  instead of `## Notes / log`
- `wiki/work/2026-06-12-add-batch-ingestion…` (`kind: feature`)

The `## Plan` table is the machine-read surface `gw work next` / `gw work advance`
route on, so these three cannot be advanced through the pipeline.

**Fix:** backfill the three-column table (`| Action | Done when | Rationale |`,
header row exact). Small, per item.

### D4 · `vault_wikilink`'s single-emitter guarantee has live bypasses

`packages/wiki-io/src/wiki_io/wikilinks.py`'s module docstring claims every producer
of vault wikilinks — including rendered prompt examples — routes through the helper.
Three do not:

- `prompts/ingestor.py:51` — hand-writes `[[entities/…]]` as a literal string
- `prompts/synthesizer.py:11` — same
- `packages/wiki-io/src/wiki_io/backlink_index.py:106` (`_format_bullet`) — f-strings
  `- [[{category}/{slug}]]`, bypassing the `wiki/`-prefix `ValueError` guard entirely

The third generates real vault content, so the guard that is supposed to make a
retired link form impossible does not cover one of the emitters that writes pages.

**Fix:** route the emitters through the helper, or correct the docstring so it stops
asserting a guarantee the code does not provide.

### D5 · Curated `path:line` citations drift silently, and nothing checks them

Re-verifying citations against source on three concept pages found roughly **60 % of
line references stale**:

| Page | Stale | Examples |
|---|---:|---|
| `concepts/preserve-then-overwrite-merge.md` | 4 of 6 | `_merge_preserved_sections` 597→598; merge call site 701-702→694-695; render call 1080-1084→1073-1078; byte-compare 1087-1100→1080-1093 |
| `concepts/vault-wikilink-form.md` | 5 | `index_generator.py` 898/925→853/880; `update_index.py` 240→244, 253/258→257/262; `_entity_wikilink` 671→591 |
| `concepts/code-change-gate.md` | 3 | `subagent-driven-development/SKILL.md` 42-44→44-46; `test-driven-development/SKILL.md` :19→:16-18 |

One drift was substantive, not positional: `code-change-gate` described the gate as
"a note before the Iron Law" in `test-driven-development/SKILL.md` when it is a full
`## Code-Change Gate` section at `:16`, with the Iron Law separately at `:35`.

**These corrections were not retained** — see "Trial adoption, reverted" below — so
every drift listed is still on disk.

The mechanical lint registry (`lint_mechanical.py:227-249`) carries `code_drift`,
`file_map_drift`, `package_sync_drift`, and `source_path_drift`. Every one verifies
that a referenced **file** still exists. None resolves a backticked `` `path:line` ``
to check the line still holds the symbol the page claims. Iron rule 6 of the vault's
own CLAUDE.md is "every claim cites" — citations are the mechanism by which 229
curated pages earn trust, and they decay unobserved.

**Fix:** a script. Resolve every `` `path:line` `` in `concepts/` and `adrs/`; flag
those whose file is gone, and those whose cited symbol no longer appears within ±N
lines. Highest leverage item in this document.

## Open decisions

### DEC1 · What to do with `kind: pattern`

`concept-pattern.md` has **zero adopters**. Its five unique sections
(`## When to apply (Forces)`, `## Solution`, `## Tradeoffs`, `## Example sources`,
`## Where this could apply in the codebase`) occur nowhere in the vault. All three
`kind: pattern` pages are authored with the plain `concept.md` section set.

**Trial adoption, reverted.** On 2026-08-02 all three pages were rewritten onto the
template, one agent per page, then reverted the same day (`git checkout HEAD --`);
the vault is unchanged. The trial is worth recording because it tested the *template*
rather than the pages. Three agents working independently reported the same two
frictions:

- `## Definition` must be codebase-agnostic — the template's own text says "in its
  general form, not tied to this codebase" — but all three subjects are mechanisms
  shipped here. Each rewrite opened with a de-specified statement and pushed the
  concrete detail into `## Solution`, leaving the page thinner at the top.
- `## Where this could apply in the codebase` presumes the pattern is *not yet
  applied*. For a mechanism with one implementation and one caller, the only honest
  content is "where it is applied."

Both share a root: the template is shaped for a catalogued pattern you might adopt,
while every `kind: pattern` page here documents a shipped mechanism. It is not unused
because authors forgot it — it does not describe what these pages are.

**Options:** fold `kind: pattern` onto `concept.md` (recommended); retire the
template; or leave as-is. Wiring it up is the option the trial argued against.

### DEC2 · Template the skill-import source shape

20 pages with `source_type: skill` share **no heading with `source.md` at all** —
every one uses `## Summary` + `## Generates` (the latter recording which `guidance/`
pages the import produced). A coherent second shape that was never written down.

**Options:** add a `source-skill.md` sibling template, or accept it as untemplated.
Note this is the mirror image of DEC1 — there, a template with no pages; here, a
shape with no template.

### DEC3 · Name the ADR provenance section

`## Context` / `## Decision` / `## Consequences` appear on 39/39 ADRs. The tail does
not: `## Alternatives considered` 31/39, `## Impact` 29/39, `## Follow-ups` 27/39,
and the misses cluster (ADRs 0018, 0019, 0020, 0023, 0024, 0027, 0036, 0037 each drop
all three together — a consistent lightweight shape).

`adr.md` has no provenance section, so twelve ADRs invented one under four names:
`## Source` (0018, 0020, 0026, 0039), `## Sources` (0032, 0033, 0034), `## Related`
(0019, 0023, 0024), `## References` (0013, 0014).

**Options:** `## Sources` matches the concept templates; `## Source` matches the
plurality of actual usage. Either beats leaving it unnamed.

### DEC4 · The structural lever

The pattern across all findings: conformance is high exactly where no model has to
*remember* a section list. The durable fix is not more lint — it is moving categories
from "model recalls the section set" to "authoring path selects and injects it," the
way `gw work file` already does by `kind:`. A lint rule only reports drift after the
fact.

This is a larger change than DEC1–DEC3 and worth deciding on before spending effort
on the smaller template fixes, since it would subsume several of them.

## Needs a human check

Two skills reach code edits with no code-change-gate reference —
`plugins/graph-wiki/skills/systematic-debugging/SKILL.md` and
`plugins/graph-wiki/skills/receiving-code-review/SKILL.md` — and the gate's design
source does not list them among its deliberate exclusions. Surfaced by grep during
the DEC1 trial, **not** verified against the design record. May well be intentional.

## Closed — no action recommended

- **Entity and proposal pages are exact.** 52/52 and 33/33 carry their template's H2
  set with no missing or extra section. Entity pages are also fully populated: zero
  `> TODO:` placeholders, zero `_(scanner will populate…)_` stubs, zero `— TODO`
  file-map rows, zero `needs_narrative` flags. This closes the backlog ADR-0038
  recorded as open (28 entities flagged with sticky placeholders when it was filed).
  The two-class merge is doing what `concepts/section-ownership-model.md` claims.
- **Architecture pages have effectively no shape** — 18 pages retain 1 to 7 of the
  template's 9 sections (median 4), `## Diagrams` at 0/18, `## Layers / Components`
  at 1/18, and roughly 60 distinct one-off headings between them. Recommend leaving
  alone: these are genuinely bespoke syntheses and the one-off headings usually
  describe the content better than the template would.
- **Guidance bodies are optional by construction.** `## Guidance` is on 83/83;
  `## Correct` 64, `## Incorrect` 37, `## Applies to` 30. Imported wholesale from
  external skills, many of which state a rule with no anti-pattern to contrast. The
  `## Applies to` gap matters less than it looks — injection ranks on the
  `triggers.entities` frontmatter key, not the body section.
- **`entity-domain.md` has zero instances.** No `domain` entity is admitted in this
  workspace, so that row of the schema is untested against real content.

## Minor

`wiki/.templates/` drifts from the packaged assets: the vault copies of `adr.md` and
`concept*.md` lack the `last_updated_commit` and `content_hash` keys the packaged
versions carry. The vault copy is only refreshed by a bootstrap, so this affects
fresh vaults rather than existing pages (which get the keys stamped anyway).
