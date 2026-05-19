# Query Workflow

The flow the LLM follows when the user runs `/graph-wiki:query <question>` or dispatches the `graph-wiki:librarian` sub-agent.

## Core principle

**Read `index.md` first, then drill in.** Do NOT grep the entire wiki or the codebase on every query — the index is there precisely so you don't have to. For code-level details the wiki doesn't cover, fall back to reading the code directly.

## Step-by-step

### 1. Read `index.md`

The index is the catalog. Scan it and pick the 3-10 pages most likely to contain the answer. A good monorepo query usually pulls across categories:

- `architecture/` for the big picture
- `packages/` for specific package surface area
- `domains/` for feature-area context
- `concepts/` for cross-cutting patterns
- `dependencies/` for "how do we use X library" questions
- `work/` for "why does X fail / what's planned / what's in progress"
- `adrs/` for "why did we do it this way"
- `sources/` for evidence and original context

### 2. Read the picked pages

Read them in full. They're short, curated, and already cross-referenced.

### 3. Follow wikilinks opportunistically

If a read page points to another clearly relevant page, follow it. Stop when you have enough.

### 4. Fall back to search or the code

If the index doesn't surface the right page:

```bash
python ${CLAUDE_PLUGIN_ROOT}/skills/graph-wiki/scripts/wiki_search.py --query "<terms>" --limit 5
```

If the wiki doesn't cover the topic at all, read the **code directly** — the wiki is not authoritative for code-level specifics. In that case, flag the gap: "The wiki doesn't document X. I read `<file>` to answer; want me to file a concept/package page?"

### 5. Synthesize the answer

Format:
- **Direct answer** — 1-3 sentences
- **Supporting detail** — organized thematically
- **Inline citations** — mix of:
  - wiki page wikilinks: `[[packages/xxx]]`, `[[sources/yyy]]`
  - code paths with line numbers: `` `packages/foo/src/bar.ts:42` ``
- **Related pages** — 3-5 wikilinks at the end

### 6. Offer to file the answer back

**Every good answer is a candidate wiki page.** At the end of the answer, ask:

> _Should I file this as a new page? Suggested location:
> `<workspace>/wiki/concepts/<slug>.md` or `<workspace>/wiki/architecture/<slug>.md` — or I can append to [[existing-page]]._

If yes:
- Pick the right category:
  - "how does X work" → `concepts/` or `architecture/`
  - "A vs B" → `concepts/<a>-vs-<b>.md`
  - "why did we decide X" → `adrs/` (only if it's capturing a real past decision)
  - "what's planned for X / why does X fail / workaround for Y" → `work/` (`kind:` discriminates)
- Use the appropriate template
- Add frontmatter with `category`, `summary`, `updated`
- Update `<workspace>/wiki/index.md`
- Append to `log.md`:
  ```bash
  python ${CLAUDE_PLUGIN_ROOT}/skills/graph-wiki/scripts/append_log.py --op create \
      --title "<question>" --detail "filed query response to <path>"
  ```

## Output formats

Not every query wants a markdown answer. Offer the user:

- **Markdown page** (default) — filed back as a wiki page
- **Dependency list / usage table** — for "who uses X" questions, derived from package frontmatter + scan data
- **Comparison table** — for "A vs B"
- **Marp slide deck** — via `python ${CLAUDE_PLUGIN_ROOT}/skills/graph-wiki/scripts/export_marp.py` on the synthesis page
- **Chart (matplotlib)** — for data-driven questions; save to `<workspace>/wiki/assets/charts/`

## Anti-patterns

- Do not grep the entire repo on every query — use the index, then drill into the wiki, then to code only if needed
- Do not answer without citations — every claim must link to a wiki page or code path
- Do not create a new page for a trivial one-off question — only file back substantive answers worth keeping
- Do not invent content not in the wiki or code — if you don't know, say so and suggest a source to ingest or a concept page to create
- Do not skip the `log.md` entry when filing an answer back
