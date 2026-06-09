# Ingest Workflow

The detailed flow the LLM follows when the user runs `/graph-wiki:ingest <path>` or dispatches the `graph-wiki:ingestor` sub-agent.

Sources in a graph-wiki are one of: **spec**, **article**, **PR summary**, **ticket**, **transcript**, **RFC**, **design doc**, or an **in-repo doc** (a `.md` that lives in the repo, passed by repo-relative path). The ingest flow is the same for all — only the summary template's framing changes.

## Source locations

Sources live in two places:

- **`<workspace>/raw/<...>`** — clipped articles, specs, PRs, transcripts you've staged. File contents are never edited; after a successful ingest the source is moved to `raw/_archived/<same relative path>`, so `raw/` (outside `_archived/`) only holds un-ingested material. Owned by `workspace_io`.
- **`<repo>/<...>.md`** (in-repo design docs) — any `.md` that resolves under the repo but outside the wiki. Pass the repo-relative path straight to `/graph-wiki:ingest`; `ingest_source.py` detects it as an in-repo doc (`in_repo_doc`). The summary records `source_path` (repo-relative) and `last_sync_commit` so `/graph-wiki:lint` flags staleness when the file changes. The doc itself stays in the repo — the wiki does not duplicate it.

## Inputs

- Path to a source file. Either inside `raw/` or repo-relative for in-repo docs. If the file is somewhere else (e.g. `~/Downloads/`), prompt the user to stage it under `raw/` first.
- The current state of `<workspace>/wiki/` (especially `index.md`, relevant `entities/`, `concepts/`)

## Step-by-step

### 1. Prepare the brief

Run `python scripts/ingest_source.py --source <path> --json` to get (wiki and repo discovered automatically via `workspace_io`):
- title guess
- word count
- preview (first 1200 chars)
- source_type guess (spec / article / pr / ticket / transcript / example / doc / note — raw/<type>/ folders are authoritative; in-repo docs default to `doc`, loose files to `note`)
- suggested summary-page path (`<workspace>/wiki/sources/<YYYY-MM>-<slug>.md`)
- whether a summary page already exists (→ **merge mode**)
- `last_sync_commit`, `in_repo_doc` flag, and `state_gate` (`allowed`, `reason`, `head_commit`) — use `state_gate.allowed` to decide whether to write drift-detection frontmatter; use `state_gate.head_commit` as the value for `last_sync_commit`
- `entity_match` — `{ uri: <str|null>, entity_filename: <str|null> }` — the best-matching entity from `entities/` for this source (used to populate `entity_uri:` frontmatter); null when no match is found

### 2. Read the source

Use the Read tool on the source directly. For PDFs, use Read's PDF support. For images in `raw/assets/`, inspect them if the LLM has vision.

### 3. Discuss with the user

Before writing anything, tell the user:
- Title, authors, date, source type
- 2-3 sentence TL;DR
- Key claims (bulleted, 3-7 items)
- **Which code entities and concepts this source touches** — bulleted `[[entities/...]]` wikilinks
- Any **contradictions** with existing pages or with current code
- Whether this source proposes a decision worth capturing as an ADR

**Wait for user to confirm or redirect.** The user is in the loop — the ingestor proposes, the user approves.

### 4. Create / merge the source summary page

Path: `<workspace>/wiki/sources/<YYYY-MM>-<slug>.md`. Use the **source summary** template from `references/page-formats.md`. Required frontmatter: `title`, `category: source`, `summary`, `source_path`, `source_type`, `ingested`, `updated`.

For in-repo docs (`source_type: doc`), also set `last_sync_commit` (`state_gate.head_commit`) and `last_sync_at` (today) — but only when `state_gate.allowed` is true (working tree clean and HEAD on `main`). Otherwise omit both fields and warn the user that drift detection won't apply until the next clean-on-main ingest. `/graph-wiki:lint` uses these fields to flag drift on subsequent runs.

**Merge mode** (summary page already exists): append a new `## Re-ingest <date>` section at the bottom with what changed. Do not overwrite the original summary. Bump `last_sync_commit` to the new HEAD so drift detection resets (gate: clean tree on main).

### 5. Link the code entities (never edit entity pages)

For each code entity (package, app, domain, dependency) the source touches, add a `[[entities/<prefix>_<name>]]` wikilink under the source summary's `## Touches` section. Entity pages are scanner-owned and live under `entities/` — **do not edit them**. The scanner regenerates each entity's `## Referenced in wiki` section from these forward-links on the next `/graph-wiki:scan`. Set the source page's `entity_uri:` frontmatter to the primary/canonical entity's URI from `entity_match.uri` in the brief (or `null` if none).

### 6. Update / create concept pages

For each cross-cutting concept mentioned:
- If a page exists: update `## Key claims` or `## Used in`; add to `## Sources`
- If not: create a stub concept page with the minimum (definition, one cited claim, link back to this source)

### 7. ADR capture (if applicable)

If the source represents or proposes a decision, ask the user:

> _This source looks like a decision. Should I create an ADR at `<workspace>/wiki/adrs/<NNNN>-<slug>.md`?_

If yes:
- Get the next ADR number (scan existing `adrs/*.md` for highest `adr_id`)
- Create the ADR using the template
- Link from the source page and from touched concept/architecture pages

### 8. Flag contradictions explicitly

If the source contradicts an existing wiki page OR current code, add a callout to BOTH the wiki page and (if code) note the code path:

```markdown
> ⚠️ **Contradiction** — [[sources/2026-04-auth-migration-spec]] claims
> `session.session_id` is preserved, but `packages/common-context-node-ts/src/globalContext.ts:23`
> defines it as required. Unresolved as of 2026-04-20.
```

Log contradictions in `log.md` with `op: note`.

### 9. Update architecture (optional)

If the source meaningfully shifts an `architecture/` page's thesis, revise the "Thesis" paragraph and append a dated entry under "How this synthesis has changed". Don't rewrite history; append.

### 10. Update `index.md`

If you edited wiki pages manually, edit the relevant category sections inline. Command-layer ingest/scan flows update indexes automatically.
If you wrote guidance pages manually, also refresh `guidance/index.md` and the affected `guidance/<topic>/index.md` (match the existing auto-generated bullet format).

### 11. Append to `log.md`

Append a `## [YYYY-MM-DD] ingest | <title>` entry with the touched pages.

### 12. Archive the raw source
If the source lives under `<workspace>/raw/` (and not already under `raw/_archived/`), `mkdir -p` the mirrored `_archived` parent and `mv` the source there (`raw/specs/x.md` → `raw/_archived/specs/x.md`). Skill directories move wholesale; a bare `SKILL.md` directly in a kind folder moves alone. Replace an existing destination (re-ingest semantics). Sources outside `raw/` are never touched. A failed move is a warning, not a failed ingest.

### 13. Report back to the user

Summary the user sees in chat:
- Source summary page created/updated
- Pages touched (bulleted wikilinks so the user can click through)
- Contradictions flagged (if any)
- ADRs created (if any)
- Suggested next sources to pursue (related PRs, follow-up specs)

## Source-type-specific notes

### Specs / RFCs / design docs
- Likely to produce an ADR. Always ask.
- Expect heavy updates to domain/architecture pages.

### PR summaries
- Source type `pr`. Include the PR URL in `source_path` or a `pr_url` frontmatter field.
- Add `[[entities/<prefix>_<name>]]` links under `## Touches` for every package the PR modified.
- If the PR implements an ADR, link both ways.

### Articles (clipped with Obsidian Web Clipper)
- Often produce concept pages, not ADRs.
- May touch no packages if purely informational.
- Good source of comparison material — file as `concepts/<a>-vs-<b>.md`.

### Tickets
- Usually light ingest — a short source summary plus `[[entities/...]]` links for the relevant package/domain entities.
- Multiple related tickets may roll up into a single `sources/` page.

### Transcripts
- Extract decisions (→ ADRs), action items, and technical context.
- Attribute claims to speakers where possible.

### In-repo docs (source_type: doc)
- An in-repo `.md` passed by repo-relative path; the file lives in the repo, not in `raw/`. Not auto-surfaced — point `/graph-wiki:ingest` at it directly.
- `source_path` is repo-relative (e.g. `docs/architecture.md`). The doc stays canonical — the wiki summary doesn't duplicate it; it cross-references concepts, packages, ADRs, etc. inferred from the doc's content.
- When `state_gate.allowed` is true, set `last_sync_commit` to `state_gate.head_commit` and `last_sync_at` to today; `/graph-wiki:lint` uses these to flag drift on subsequent runs. Otherwise omit both fields and warn the user that drift detection won't apply until the next clean-on-main ingest.
- Often produce concept pages, architecture revisions, or ADRs depending on the doc's content. Treat them like specs/RFCs by default.

### Code examples (source_type: example)
- Source location: `raw/examples/`. The path passed to `/graph-wiki:ingest` may resolve to a single file or a folder; folder mode is the headline new capability and produces a single source summary (not one per file).
- `ingest_source.py` returns a folder brief (file listing, total size, language guesses, representative-file preview) when `--source` resolves to a directory under `raw/examples/`. Single files behave as today, with `source_type: example`. Caps: warn at >50 files or any file >200 KB; hard error at >200 files (almost certainly the wrong directory).
- `last_sync_commit` and `last_sync_at` are disallowed in frontmatter — examples are external; drift detection does not apply. The state-gate is a no-op for `source_type: example` in the brief output.
- **Step 3 (Discuss)** for examples covers: TL;DR, what patterns the example demonstrates, key takeaways, which existing concept pages map to those patterns, and which code entities the user wants to flag under `## Where this could apply`.
- **Step 5 (Link code entities)** for examples: add `[[entities/<prefix>_<name>]]` wikilinks under `## Touches` for the relevant entities. Do **not** edit entity pages. The scanner owns them and backfills `## Referenced in wiki`.
- **Step 6 (Update / create concept pages)** gains an explicit ask: "Does this example demonstrate a reusable pattern? If so, propose `concepts/<topic>-pattern.md`." Pattern pages use the body template in `page-formats.md` Section 4a; the `pattern` tag is recommended. Wait for user confirmation before creating.
- **Step 7 (ADR capture)** is suppressed by default for examples — examples don't represent decisions in this codebase. The ingestor may still propose an ADR if the example concretely motivates a decision the user is making *now*, but the default ask is skipped.
- **Step 8 (Contradictions)** still runs — an example can contradict an existing concept page's claim (e.g. "we said pattern X is bad but this example uses it well"). Flag both ways.
- The source summary uses `page-formats.md` Section 5a (example variant): no `## Key claims`, no `## Proposed changes`; instead `Origin / What's in it / Patterns demonstrated / Key takeaways / Where this could apply / Caveats / Related`.
- Each `[[entities/<prefix>_<name>]]` bullet under `## Where this could apply` on the source page is forward-linked; the scanner derives the reciprocal `## Referenced in wiki` backlink on entity pages automatically. Concept and architecture pages keep manual reciprocity (add `## Inspirations` bullets there by hand). `/graph-wiki:lint` cross-checks concept-page reciprocity and warns on drift.
- Frontmatter contract: see `wiki-schema.md` for `origin_url`, `origin_repo`, `license`, `attribution` (`origin_url` or `origin_repo` should be set; lint warns if both are empty).

## Skill → guidance pages

When the brief carries `is_skill: true`, this source is an agent **skill** (behavioral
guidance for an AI coding agent). Route it to this flow instead of the single
source-summary flow above: a skill is broken into one or more **guidance pages** under
`wiki/guidance/<topic>/<slug>.md`, plus one source page that links to them.

### Detection

The brief from `ingest_source.py --json` carries `is_skill: true`, `source_type: skill`,
`included_files` (skill-dir-relative markdown — `SKILL.md` first, then transitively-linked
companions in link order), `excluded_files` (non-markdown files under the skill dir),
`scripts_dominant`, and a `warnings` list. **Read the `included_files` yourself** (Read
tool, skill-dir-relative) before chunking — the brief is a manifest, not the content.

If `scripts_dominant` is true (or `warnings` contains `"scripts_dominant"`), the skill is
mostly non-markdown scripts — a weak guidance candidate. Surface this to the user and ask
whether to proceed before writing pages.

### Chunking rules

Choose the chunking from the content (mirrors the Bedrock skill planner):

- **Rules / atomic directives** — a skill that is a list of independent "do X" / "never Y"
  rules: write ONE guidance page per rule.
- **How-to / instructional flow** — a single coherent procedure or technique: write ONE
  guidance page for the whole skill.
- **Never split tightly-coupled steps** across pages. When in doubt, prefer fewer, larger
  pages over many fragments.
- Extract reusable TECHNICAL knowledge; drop skill-harness scaffolding (activation phrases,
  tool-call mechanics, meta-instructions about being a skill).
- Preserve content verbatim where practical — the goal is smaller, targetable chunks, not
  rewrites.
- Infer `topic` from the skill's DOMAIN, not its filename (a React Native skill →
  `react-native`; a brainstorming skill → `brainstorming`). `topic` is a short kebab-case
  slug and becomes the folder under `wiki/guidance/`.

### Guidance page frontmatter (inline schema — no template file needed)

Each guidance page begins with this frontmatter block, then the body. Emit exactly these
keys:

```yaml
---
title: <human-readable page title>
category: guidance          # FIXED — always this literal value
summary: <one-line summary for the wiki spine>
topic: <kebab-case domain slug — the folder under guidance/>
applies_when: <when this guidance applies, one line>
triggers:                   # all sub-keys optional; emit empty lists when no signal
  globs: []
  keywords: []
  entities: []              # [[entities/...]] targets, or []
tags: []                    # optional coarse tags
impact: high                # critical | high | medium | low (lowercase)
source: "[[sources/<YYYY-MM>-<slug>]]"   # the skill's source page (see below)
updated: <today, YYYY-MM-DD>
tokens: 0
---
```

`category` MUST be the literal `guidance`. `impact` MUST be lowercase and one of
critical/high/medium/low. Use the `suggested_summary_path` from the brief (minus the
`sources/` prefix and `.md` suffix) as the `source:` target.

Body sections:

1. `# <title>`
2. `## Guidance` — the prescriptive content: how to do it correctly and why. No padding, no
   restating the title.
3. `## Incorrect` / `## Correct` — optional code examples, only when they sharpen the point.
4. `## Applies to` — ONLY when `triggers.entities` is non-empty: one `- [[entities/...]]`
   bullet per entity. Omit the section entirely when there are no entities.

### Targets

Write each page to `<workspace>/wiki/guidance/<topic>/<slug>.md`. `<topic>` is the
kebab-case domain folder; `<slug>` is a kebab-case stem derived from the page title. Create
the topic folder if it doesn't exist. On re-ingest, overwrite the page in place.

### Source page

Write one source page at the brief's `suggested_summary_path`
(`<workspace>/wiki/sources/<YYYY-MM>-<slug>.md`) with `source_type: skill`:

- `## Summary` — one or two sentences: the skill was ingested into N guidance page(s).
- `## Generates` — a bullet list of `[[guidance/<topic>/<slug>]]` wikilinks, one per
  guidance page written.
- `## Excluded` — only when the brief's `excluded_files` is non-empty: a bullet list of the
  non-markdown files (as `` `path` ``) that were not ingested.

This matches the Bedrock source-page shape (`## Summary`, `## Generates`, `## Excluded`).

### Entity backlinks

`## Applies to` `[[entities/...]]` links **do** produce entity backlinks: `guidance` is in
the scanner's preserved-wiki-dirs list, so the next `/graph-wiki:scan` derives the reciprocal
`## Referenced in wiki` entry on each linked entity page from these forward links (the nested
`guidance/<topic>/<slug>` slug is rendered correctly). Write the links — the scanner backfills
the reciprocity, just as it does for source-page `## Touches` links.

## Future formats

Today, in-repo doc ingest is limited to `.md` files passed by path. Other formats are deferred:

- **`.pdf`** — needs a parser (or rely on the LLM's PDF Read support).
- **`.docx` / `.odt`** — needs a parser.
- **`.html` / `.htm`** — `ingest_source.py` already handles these for `raw/` inputs; the scanner doesn't auto-surface them yet.
- **`.txt` / `.rst` / other markup** — same pattern; supported via direct `/graph-wiki:ingest <path>`, not auto-surfaced.

Manual ingest (passing the path to `/graph-wiki:ingest` directly) works today for any format `ingest_source.py` understands. The scanner's auto-discovery is intentionally md-only until the broader format support lands.

## After-ingest tips

- **Big ingest?** Run `python scripts/lint_wiki.py` to check for new orphans or broken links.
- **New ADR?** Run `/graph-wiki:lint` to check the ADR chain (supersedes / superseded_by).
- **Graph check?** Run `python scripts/graph_analyzer.py` to see if the new page is well-connected.
- **Open Obsidian graph view** — the user should see the new page attached to the relevant cluster.
