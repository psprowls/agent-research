# Ingest Workflow

The detailed flow the LLM follows when the user runs `/graph-wiki:ingest <path>` or dispatches the `graph-wiki:ingestor` sub-agent.

Sources in a graph-wiki are one of: **spec**, **article**, **PR summary**, **ticket**, **transcript**, **RFC**, **design doc**, or an **in-repo doc** surfaced by `/graph-wiki:scan`. The ingest flow is the same for all — only the summary template's framing changes.

## Source locations

Sources live in two places:

- **`<workspace>/raw/<...>`** — clipped articles, specs, PRs, transcripts you've staged. Immutable; the LLM never edits. Owned by `workspace_io`.
- **`<repo>/<docs-container>/<...>.md`** — in-repo design docs. `/graph-wiki:scan` lists these as ingest candidates; pass the repo-relative path straight to `/graph-wiki:ingest`. The summary records `source_path` (repo-relative) and `last_sync_commit` so `/graph-wiki:lint` flags staleness when the file changes. The doc itself stays in the repo — the wiki does not duplicate it.

## Inputs

- Path to a source file. Either inside `raw/` or repo-relative for in-repo docs. If the file is somewhere else (e.g. `~/Downloads/`), prompt the user to stage it under `raw/` first.
- The current state of `<workspace>/wiki/` (especially `index.md`, relevant `packages/`, `domains/`, `concepts/`)

## Step-by-step

### 1. Prepare the brief

Run `python scripts/ingest_source.py --source <path> --json` to get (wiki and repo discovered automatically via `workspace_io`):
- title guess
- word count
- preview (first 1200 chars)
- source_type guess (spec / article / pr / ticket / transcript / doc)
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

Either:
- Run `python scripts/update_index.py` to regenerate the entire index from frontmatter, OR
- Edit the relevant category sections inline (faster for small ingests).

### 11. Append to `log.md`

Run:
```bash
python scripts/append_log.py --op ingest \
    --title "<title>" --detail "<touched pages>"
```

### 12. Report back to the user

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
- Surfaced by `/graph-wiki:scan` for any pinned `docs` container; the `.md` lives in the repo, not in `raw/`.
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

## Future formats

Today, `/graph-wiki:scan` only surfaces `.md` files inside docs containers. Other formats are deferred:

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
