# graph-wiki Plugin → `entities/` Parity (Slices 2 & 3) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Finish bringing the `plugins/graph-wiki` plugin to the single-`entities/`-folder layout that Slice 1 shipped for `scan`: rewrite the remaining command/agent/reference docs to the `entities/` vocabulary (Slice 2), and make the Claude-hosted `lint` recognize entity pages instead of the legacy `packages/<name>/` layout so it runs clean on an `entities/` wiki (Slice 3). Also strip the now-removed `obsidian-markdown` skill's dangling references.

**Architecture:** Two independent parts in one document.
- **Part A — Slice 2 (docs only).** Bootstrap mechanics already emit `entities/` (Slice 1 wired `wiki_io.init_vault`), so this is a pure documentation sweep across `bootstrap.md`, `query.md`, `log.md`, `query-workflow.md`, the `librarian` agent, `SKILL.md`, both READMEs, and the plugin tree — replacing apps/packages/domains page-folder vocabulary with the `entities/` vocabulary defined in Appendix A of the Slice 1 plan. It also removes every reference to the deleted `obsidian-markdown` skill.
- **Part B — Slice 3 (lint code + docs, TDD).** The Claude lint shim calls `wiki_io.lint_wiki.main()`. Its `scan()` has three checks that break on entity pages: the inline `code_drift` check (filters on the `category` frontmatter key + a `packages/<slug>/` path shape that entity pages don't have), `missing_frontmatter`/`missing_tokens` (require `category`/`tokens` that entity pages dropped in favor of `kind`/`uri`), and `lint/container.py`'s `FIXED_DIRS` (lists `apps`/`packages`/`domains` but not `entities`, so the `entities/` dir is flagged as an orphan). We make all three entity-aware while preserving legacy recognition, then update the `linter` agent and `lint-workflow.md`. The dead-but-harmless no-op checks on entity pages (`package_sync`, `file_map`, `domain`, `workflow_hints`) are left as-is (out of scope — see Orientation).

**Tech Stack:** Python 3.11+, `uv` workspace, `pytest` (`asyncio_mode = auto`), `python-frontmatter`. Code changes land in `packages/wiki-io/`; doc changes land in the `plugins/graph-wiki/` tree. No plugin shim or `graph-wiki-cli`/`graph-wiki-core` change is needed (the lint fix is entirely inside `wiki_io.lint_wiki` + `wiki_io.lint.container`, which the Claude lint shim already invokes).

---

## Orientation — read before starting

**Scope decisions already made (do not re-litigate):**
- **Slice 3 = "entity-aware lint."** Fix the three real false-positive sources only: `code_drift`, `missing_frontmatter`/`missing_tokens`, and `container.FIXED_DIRS`. The checks that become silent no-ops on entity pages (`package_sync`, `file_map`, `domain`, `workflow_hints` in `packages/wiki-io/src/wiki_io/lint/`) are **left untouched** — they don't produce false positives, only dead coverage, and rewiring them is explicitly out of scope. Do not modify them.
- **`obsidian-markdown` skill was removed from the plugin.** Every reference to it is now dangling and must be removed (Tasks A4, A5, A7, B4). Do not try to read or edit the skill itself — it no longer exists in this repo.

**Legacy recognition stays.** Two existing lint tests (`test_code_drift_recognizes_overview_md`, `test_code_drift_recognizes_legacy_pkg_pkg_md` at `packages/wiki-io/tests/test_lint_wiki.py:156-211`) assert the legacy `packages/<slug>/overview.md` and `<slug>/<slug>.md` pages are still recognized. The Slice 3 edits **add** entity recognition alongside the legacy path logic; they must not break those two tests. Per `.claude/rules/backward-compatibility.md` we *could* delete legacy support, but keeping it is ~4 lines and avoids touching working tests — keep it.

**The lint fix needs no shim change.** `plugins/graph-wiki/skills/graph-wiki/scripts/lint_wiki.py` (Claude branch) already calls `wiki_io.lint_wiki.main()`; the Bedrock branch shells out to `gw wiki lint`. All Slice 3 code lives in `packages/wiki-io/`, so the shim and its argv-contract test (`test_plugin_bedrock_shims.py`) are unaffected.

**Entity frontmatter contract** (source of truth: `packages/wiki-io/src/wiki_io/entity_writer.py` + the `entity-*.md` templates under `packages/wiki-io/src/wiki_io/assets/page-templates/`). Entity pages carry `title`, `uri`, `kind` (one of `ADMITTED_KINDS`), `graph_name`, `last_scan_at`, `updated`, plus per-kind edge keys. They do **not** carry `category`, `summary` (fill-when-empty, often absent), or `tokens`. `package`/`app` entity URIs look like `pkg:org/repo/<name>` / `app:org/repo/<name>`; the workspace slug is the final `/`-segment.

**`ADMITTED_KINDS`** (`entity_writer.py:60-70`): `repository`, `domain`, `package`, `app`, `agent_plugin`, `dependency`, `test_suite`. Filename prefixes: `repo_`, `domain_`, `pkg_`, `app_`, `agent-plugin_`, `dep_`, suite-kind-aware (`unit_tests_`/`int_tests_`/… fallback `tests_`).

**Canonical vocabulary:** Appendix A of `docs/superpowers/plans/2026-06-02-graph-wiki-plugin-entities-parity-slice1.md` is the single source of truth for kinds/prefixes/filenames/frontmatter. The Slice 2 doc edits below reference it; when a doc edit needs the full table, copy it from there.

**Test runner (from repo root):**
```bash
uv run pytest packages/wiki-io/                                  # whole wiki-io suite
uv run pytest packages/wiki-io/tests/test_lint_wiki.py -v        # lint tests
```

**Doc verification has no unit tests** — Part A tasks verify with targeted `grep` sweeps (provided per task) plus a spot-read.

---

## File Structure

| File | Part | Change | Responsibility |
|---|---|---|---|
| `plugins/graph-wiki/commands/bootstrap.md` | A | Edit | Subdir list, "What it creates" tree, next-steps, replace stale "Sub-page templates" section |
| `plugins/graph-wiki/commands/log.md` | A | Edit | Example-output filenames → `entities/` |
| `plugins/graph-wiki/commands/query.md` | A | Edit | Drill-in category list → `entities/` |
| `plugins/graph-wiki/skills/graph-wiki/references/query-workflow.md` | A | Edit | Index drill-in categories + citation forms → `entities/` |
| `plugins/graph-wiki/agents/librarian.md` | A | Edit | Category list → `entities/`; drop obsidian-markdown |
| `plugins/graph-wiki/skills/graph-wiki/SKILL.md` | A | Edit | Architecture tree, ops, page-category table, iron rule 4, scripts/commands wording; drop obsidian-markdown |
| `plugins/graph-wiki/skills/graph-wiki/README.md` | A | Edit | Page-category examples + tree → `entities/` |
| `plugins/graph-wiki/README.md` | A | Edit | Scan-row wording → entity pages |
| `plugins/graph-wiki/agents/scanner.md` | A | Edit | Drop obsidian-markdown (frontmatter + rule) |
| `plugins/graph-wiki/agents/ingestor.md` | A | Edit | Drop obsidian-markdown (frontmatter + rule) |
| `plugins/graph-wiki/CLAUDE.md` | A | Edit | Drop obsidian-markdown from tree diagram |
| `packages/wiki-io/src/wiki_io/lint_wiki.py` | B | Modify | Entity-aware `code_drift`; entity-aware `missing_frontmatter`/`missing_tokens` |
| `packages/wiki-io/src/wiki_io/lint/container.py` | B | Modify | Add `entities` to `FIXED_DIRS` |
| `packages/wiki-io/tests/test_lint_wiki.py` | B | Extend | New tests: entity code-drift, entity frontmatter, container FIXED_DIRS |
| `plugins/graph-wiki/agents/linter.md` | B | Edit | Vault↔code spot-check + report + actions → `entities/`; drop obsidian-markdown |
| `plugins/graph-wiki/skills/graph-wiki/references/lint-workflow.md` | B | Edit | Check descriptions + Pass-2 vault↔code → `entities/` |

---

# Part A — Slice 2: docs sweep + obsidian-markdown removal

## Task A1: `bootstrap.md` → `entities/` layout

**Files:**
- Edit: `plugins/graph-wiki/commands/bootstrap.md`

The container-detection section (lines 28-42) is unchanged — detection still runs to scope the graph build / pin the layout block. Only the layout *description*, the "What it creates" tree, the next-step, and the now-fully-stale "Sub-page templates" section change.

- [ ] **Step 1: Fix the subdir list (line 10)**

Replace:
```
The wiki contains `index.md`, `log.md`, and curated subdirs (`adrs/`, `architecture/`, `concepts/`, `dependencies/`, `sources/`, `.templates/`, plus conditional `apps/`, `packages/`, `domains/`) directly — there is no inner vault directory. `raw/` and `work/` are owned by `workspace_io` and live at the workspace root as siblings of `wiki/`.
```
with:
```
The wiki contains `index.md`, `log.md`, and curated subdirs (`entities/`, `adrs/`, `architecture/`, `concepts/`, `dependencies/`, `sources/`, `.templates/`) directly — there is no inner vault directory. `entities/` holds one graph-derived page per admitted entity (repository, domain, package, app, agent_plugin, dependency, test_suite); there are no separate `apps/`/`packages/`/`domains/` page folders. `raw/` and `work/` are owned by `workspace_io` and live at the workspace root as siblings of `wiki/`.
```

- [ ] **Step 2: Fix the "What it creates" tree (lines 46-58)**

Replace the fenced tree block:
```
<workspace>/wiki/               # e.g. <repo>/graph-wiki/wiki/
├── index.md
├── log.md
├── packages/ domains/ apps/    # conditional, based on detected containers
├── concepts/ dependencies/
├── sources/ architecture/ adrs/
├── .templates/                 # page templates for reference
├── CLAUDE.md                   # if --tool claude-code or all
├── AGENTS.md                   # if --tool codex|cursor|antigravity|opencode|gemini-cli|all
├── .cursorrules                # if --tool cursor or all
└── .gitignore
```
with:
```
<workspace>/wiki/               # e.g. <repo>/graph-wiki/wiki/
├── index.md
├── log.md
├── entities/                   # one page per admitted entity (seeded with .gitkeep until scanned)
├── concepts/ dependencies/
├── sources/ architecture/ adrs/
├── .templates/                 # page templates for reference
├── CLAUDE.md                   # if --tool claude-code or all
├── AGENTS.md                   # if --tool codex|cursor|antigravity|opencode|gemini-cli|all
├── .cursorrules                # if --tool cursor or all
└── .gitignore
```

- [ ] **Step 3: Fix the next-step (line 66)**

Replace:
```
2. Run `/graph-wiki:scan` to populate `<workspace>/wiki/packages/` (one folder per package) from workspace manifests
```
with:
```
2. Run `/graph-wiki:scan` to populate `<workspace>/wiki/entities/` (one page per admitted entity) from the code graph
```

- [ ] **Step 4: Replace the stale "Sub-page templates" section (lines 69-79)**

The `.templates/package/` sub-page model (`overview.md`/`api.md`/`patterns.md`/`work.md`/`context.md`, `ensure_package_pages()`, `ensure_subpage()`) was removed in Slice 1. The shipped templates are now per-entity-kind + curated-page templates. Replace the entire section — from the `## Sub-page templates` header through the `ensure_subpage()` paragraph (lines 69-79) — with:

````markdown
## Page templates

After init, `<workspace>/wiki/.templates/` holds the templates the scanner and ingest/query flows use as reference (copied from `packages/wiki-io/src/wiki_io/assets/page-templates/`):

- **Per-entity-kind:** `entity-repository.md`, `entity-domain.md`, `entity-package.md`, `entity-app.md`, `entity-agent-plugin.md`, `entity-dependency.md`, `entity-test-suite.md` — the scanner renders one `entities/` page per admitted entity from these.
- **Curated pages:** `concept.md`, `concept-pattern.md`, `source.md`, `adr.md`, `architecture.md`, `dependency.md`, `work.md`, plus `index.md`.

Entity pages are written by `/graph-wiki:scan` from the code graph (see `references/scan-workflow.md`); the curated-page templates are used by `/graph-wiki:ingest` and `/graph-wiki:query` when filing new concept/source/ADR/architecture pages.
````

- [ ] **Step 5: Verify**

Run:
```bash
grep -nE "packages/ domains/ apps/|wiki/packages/|conditional|ensure_package_pages|ensure_subpage|Sub-page templates|\.templates/package" plugins/graph-wiki/commands/bootstrap.md
```
Expected: no matches. Spot-read lines 44-90.

- [ ] **Step 6: Commit**

```bash
git add plugins/graph-wiki/commands/bootstrap.md
git commit -m "docs(plugin): bootstrap command describes entities/ layout

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

---

## Task A2: `log.md` + `query.md` → `entities/` vocabulary

**Files:**
- Edit: `plugins/graph-wiki/commands/log.md`
- Edit: `plugins/graph-wiki/commands/query.md`

- [ ] **Step 1: Fix the `log.md` example output (lines 52-58)**

Replace:
```
## [2026-04-20] ingest | Auth Migration Spec
Added sources/2026-04-auth-migration-spec.md. Updated concepts/global-context,
domains/auth, packages/shared-aws-node-ts, adrs/0014-jwt-sessions (new).

## [2026-04-19] scan | detected 3 new packages
Added packages/timeline-native-ts, packages/timeline-data-node-ts, packages/timeline-domain-ts.
```
with:
```
## [2026-04-20] ingest | Auth Migration Spec
Added sources/2026-04-auth-migration-spec.md. Updated concepts/global-context,
entities/domain_auth, entities/pkg_shared-aws-node-ts, adrs/0014-jwt-sessions (new).

## [2026-04-19] scan | detected 3 new packages
Added entities/pkg_timeline-native-ts, entities/pkg_timeline-data-node-ts, entities/pkg_timeline-domain-ts.
```

- [ ] **Step 2: Fix the `query.md` drill-in line (line 25)**

Replace:
```
2. **Drill-in** — 3-10 pages across categories (architecture + packages + concepts + sources + adrs + work)
```
with:
```
2. **Drill-in** — 3-10 pages across categories (architecture + entities + concepts + sources + adrs + work)
```

- [ ] **Step 3: Verify**

Run:
```bash
grep -nE "packages/timeline|packages/shared|domains/auth|packages \+ concepts" plugins/graph-wiki/commands/log.md plugins/graph-wiki/commands/query.md
```
Expected: no matches.

- [ ] **Step 4: Commit**

```bash
git add plugins/graph-wiki/commands/log.md plugins/graph-wiki/commands/query.md
git commit -m "docs(plugin): log + query command examples use entities/ paths

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

---

## Task A3: `query-workflow.md` → `entities/` categories + citation forms

**Files:**
- Edit: `plugins/graph-wiki/skills/graph-wiki/references/query-workflow.md`

The "file the answer back" flow (lines 52-72) creates **new concept/architecture/ADR** pages, which still use the `category` frontmatter and live outside `entities/` — leave those untouched. Only the index drill-in category list and the package/domain citation examples change.

- [ ] **Step 1: Fix the drill-in category list (lines 15-22)**

Replace:
```
- `architecture/` for the big picture
- `packages/` for specific package surface area
- `domains/` for feature-area context
- `concepts/` for cross-cutting patterns
- `dependencies/` for "how do we use X library" questions
- `work/` for "why does X fail / what's planned / what's in progress"
- `adrs/` for "why did we do it this way"
- `sources/` for evidence and original context
```
with:
```
- `architecture/` for the big picture
- `entities/` for specific package/app surface area (`pkg_*`, `app_*`) and feature-area context (`domain_*`)
- `concepts/` for cross-cutting patterns
- `dependencies/` for "how do we use X library" questions (the auto-rendered index; `entities/dep_*` for detail)
- `work/` for "why does X fail / what's planned / what's in progress"
- `adrs/` for "why did we do it this way"
- `sources/` for evidence and original context
```

- [ ] **Step 2: Fix the citation-form examples (lines 47-49)**

Replace:
```
  - wiki page wikilinks: `[[packages/xxx]]`, `[[sources/yyy]]`
  - code paths with line numbers: `` `packages/foo/src/bar.ts:42` ``
```
with:
```
  - wiki page wikilinks: `[[entities/pkg_xxx]]`, `[[sources/yyy]]`
  - code paths with line numbers: `` `packages/foo/src/bar.ts:42` ``
```

(The second line is a *code path*, not a wiki path — it correctly references repo source, so it stays.)

- [ ] **Step 3: Verify**

Run:
```bash
grep -nE "\`packages/\` for|\`domains/\` for|\[\[packages/xxx\]\]" plugins/graph-wiki/skills/graph-wiki/references/query-workflow.md
```
Expected: no matches.

- [ ] **Step 4: Commit**

```bash
git add plugins/graph-wiki/skills/graph-wiki/references/query-workflow.md
git commit -m "docs(plugin): query-workflow drills into entities/ + cites entities paths

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

---

## Task A4: `librarian.md` → `entities/` + drop obsidian-markdown

**Files:**
- Edit: `plugins/graph-wiki/agents/librarian.md`

- [ ] **Step 1: Drop `obsidian-markdown` from the skills frontmatter (line 4)**

Replace:
```
skills: [graph-wiki, obsidian-markdown]
```
with:
```
skills: [graph-wiki]
```

- [ ] **Step 2: Fix the index-first category list (lines 33-41)**

Replace:
```
- `architecture/` big picture
- `packages/` package-specific surface area
- `domains/` feature-area context
- `concepts/` cross-cutting patterns
- `dependencies/` external-library questions
- `issues/` bug / tech-debt questions
- `roadmap/` planned / in-progress questions
- `adrs/` "why did we do it this way"
- `sources/` evidence and original context
```
with:
```
- `architecture/` big picture
- `entities/` package/app surface area (`pkg_*`, `app_*`) and feature-area context (`domain_*`)
- `concepts/` cross-cutting patterns
- `dependencies/` external-library questions (`entities/dep_*` for detail)
- `work/` bug / tech-debt / planned / in-progress questions
- `adrs/` "why did we do it this way"
- `sources/` evidence and original context
```

(`issues/`/`roadmap/` were legacy folders folded into `work/` — fold them here too.)

- [ ] **Step 3: Remove the obsidian-markdown rule (line 74)**

Delete this bullet entirely:
```
- **Invoke the `obsidian-markdown` skill** before filing an answer back as a new page — synthesized answers, related-page lists, and any new concept/architecture/comparison page must use Obsidian syntax (`[[wikilinks]]`, callouts, valid YAML frontmatter, embeds where appropriate).
```

(The vault is still an Obsidian vault; the other rules already require `[[wikilinks]]` and valid frontmatter, so no replacement is needed.)

- [ ] **Step 4: Verify**

Run:
```bash
grep -nE "obsidian-markdown|\`packages/\`|\`domains/\`|\`issues/\`|\`roadmap/\`" plugins/graph-wiki/agents/librarian.md
```
Expected: no matches.

- [ ] **Step 5: Commit**

```bash
git add plugins/graph-wiki/agents/librarian.md
git commit -m "docs(plugin): librarian agent reads entities/; drop obsidian-markdown ref

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

---

## Task A5: `SKILL.md` → `entities/` + drop obsidian-markdown

**Files:**
- Edit: `plugins/graph-wiki/skills/graph-wiki/SKILL.md`

This file has the most touch points. Apply each edit below.

- [ ] **Step 1: Architecture tree — the three conditional folder lines (lines 54-56)**

Replace:
```
    ├── apps/<app>/             # [conditional] One folder per application workspace (web, mobile, CLI); overview lives at apps/<app>/overview.md
    ├── packages/<pkg>/         # [conditional] One folder per library/service workspace package; overview at packages/<pkg>/overview.md
    ├── domains/<domain>/       # [conditional] One folder per cross-package feature area; overview at domains/<domain>/overview.md (domain-scoped packages live under domains/<domain>/packages/<pkg>/overview.md)
```
with:
```
    ├── entities/               # One graph-derived page per admitted entity (pkg_*, app_*, domain_*, dep_*, repo_*, agent-plugin_*, *_tests_*)
```

- [ ] **Step 2: Replace the "conditional" paragraph (line 67)**

Replace:
```
`apps/`, `packages/`, and `domains/` are **conditional** — the detector creates them only when the repo has matching containers. A single-package repo has none of these; its workspace pages live at the wiki root (or under `concepts/` / `architecture/` for cross-cutting topics). A library-only monorepo has `packages/` but no `apps/`. Pinned containers are recorded in `<workspace>/wiki/CLAUDE.md` and `<workspace>/wiki/AGENTS.md`.
```
with:
```
Every workspace package, app, and domain — plus the repository, external dependencies, and test suites — is rendered as a single page under `entities/`, named `<prefix>_<name>[__hex].md` (prefixes: `repo_`, `domain_`, `pkg_`, `app_`, `agent-plugin_`, `dep_`, suite-kind-aware `unit_tests_`/`int_tests_`). There are no separate `apps/`/`packages/`/`domains/` page folders. Container *detection* still pins the layout block (used to scope the graph build) and is recorded in `<workspace>/wiki/CLAUDE.md` and `<workspace>/wiki/AGENTS.md`; it no longer creates page folders.
```

- [ ] **Step 3: Scan op description (line 73)**

Replace:
```
1. **Scan** — walk the repo, detect packages/apps/workspaces, propose stub `packages/*.md` pages, and surface in-repo `.md` docs as ingest candidates. See `references/scan-workflow.md`.
```
with:
```
1. **Scan** — build the code graph and render one page per admitted entity into `entities/` (structural-only: `## Narrative` placeholder + `— TODO` file-map rows). See `references/scan-workflow.md`.
```

- [ ] **Step 4: Quick-start comment (line 88)**

Replace:
```
# 2. Scan the repo to create stub pages for every package
```
with:
```
# 2. Scan the repo to render one entities/ page per admitted entity
```

- [ ] **Step 5: Slash-command table row (line 106)**

Replace:
```
| `/graph-wiki:scan` | Walk the repo, detect packages/apps/workspaces, create/update stub package pages |
```
with:
```
| `/graph-wiki:scan` | Build the code graph; create/update/delete one `entities/` page per admitted entity |
```

- [ ] **Step 6: Sub-agent table row (line 116)**

Replace:
```
| `graph-wiki:scanner` | Walk the repo, detect packages, propose or update stub package pages |
```
with:
```
| `graph-wiki:scanner` | Build the code graph; write/update/delete one `entities/` page per admitted entity |
```

- [ ] **Step 7: `scan_monorepo.py` / `lint_wiki.py` script rows (lines 128, 131)**

Replace:
```
| `scan_monorepo.py` | Walk the repo, detect `package.json` / `pyproject.toml` / `Cargo.toml` / `go.mod` workspaces; emit a diff of missing/renamed/deleted package pages |
```
with:
```
| `scan_monorepo.py` | Build the code graph and write/update/delete one page per admitted entity into `entities/` (in-process `run_scan(narrate=False)`) |
```

Replace:
```
| `lint_wiki.py` | Orphans, broken links, stale pages, missing frontmatter, log gap, **+ code-drift** (packages on disk vs. in vault) |
```
with:
```
| `lint_wiki.py` | Orphans, broken links, stale pages, missing frontmatter, log gap, **+ code-drift** (entity pages on disk vs. in `entities/`) |
```

- [ ] **Step 8: Page-categories table Directory column (lines 144-146)**

Replace:
```
| `app` | One application workspace (web, mobile, CLI) — platform, entry points, domains consumed, deployment | `<workspace>/wiki/apps/<app>/overview.md` |
| `package` | One library/service workspace — what it exports, who depends on it, key patterns | `<workspace>/wiki/packages/<pkg>/overview.md` |
| `domain` | A feature area spanning multiple packages (e.g. "auth", "healthkit", "billing") | `<workspace>/wiki/domains/<domain>/overview.md` |
```
with:
```
| `app` | One application workspace (web, mobile, CLI) — platform, entry points, domains consumed, deployment | `<workspace>/wiki/entities/app_<name>.md` |
| `package` | One library/service workspace — what it exports, who depends on it, key patterns | `<workspace>/wiki/entities/pkg_<name>.md` |
| `domain` | A feature area spanning multiple packages (e.g. "auth", "healthkit", "billing") | `<workspace>/wiki/entities/domain_<name>.md` |
```

- [ ] **Step 9: Remove the obsidian-markdown "Related skills" bullet (line 166)**

Delete this bullet entirely:
```
- **`obsidian-markdown`** — bundled with this plugin. Covers Obsidian-specific syntax (wikilinks, embeds, callouts, properties, comments, highlights). The four sub-agents (`graph-wiki:scanner`, `graph-wiki:ingestor`, `graph-wiki:linter`, `graph-wiki:librarian`) invoke it whenever they create, edit, or verify a vault page so the output renders correctly in Obsidian.
```

- [ ] **Step 10: Soften iron rule 4 for entity pages (line 196)**

Replace:
```
4. **Every vault page has YAML frontmatter** with `title`, `category`, `summary`, `updated`.
```
with:
```
4. **Every vault page has YAML frontmatter.** Curated pages (concept/source/adr/architecture/dependency/work) carry `title`, `category`, `summary`, `updated`; graph-derived `entities/` pages carry `title`, `uri`, `kind`, `updated` (the scanner owns their frontmatter).
```

- [ ] **Step 11: Verify**

Run:
```bash
grep -nE "obsidian-markdown|apps/<app>/|packages/<pkg>/|domains/<domain>/|stub package|conditional" plugins/graph-wiki/skills/graph-wiki/SKILL.md
```
Expected: no matches. Spot-read the architecture tree (around line 51-65) and the page-categories table.

- [ ] **Step 12: Commit**

```bash
git add plugins/graph-wiki/skills/graph-wiki/SKILL.md
git commit -m "docs(plugin): SKILL.md to entities/ vocabulary; drop obsidian-markdown ref

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

---

## Task A6: `README.md` (skill + plugin root) → `entities/`

**Files:**
- Edit: `plugins/graph-wiki/skills/graph-wiki/README.md`
- Edit: `plugins/graph-wiki/README.md`

- [ ] **Step 1: skills README — page-category examples (lines 60-62)**

Replace:
```
| `app` | `<workspace>/wiki/apps/web-next-ts/web-next-ts.md` — Next.js app: platform, routes, domains consumed, deployment |
| `package` | `<workspace>/wiki/packages/common-aws-node-ts/common-aws-node-ts.md` — Lambda handlers, middleware, exports |
| `domain` | `<workspace>/wiki/domains/auth/auth.md` — cross-package feature area (auth spans cognito + native + shared) |
```
with:
```
| `app` | `<workspace>/wiki/entities/app_web-next-ts.md` — Next.js app: platform, routes, domains consumed, deployment |
| `package` | `<workspace>/wiki/entities/pkg_common-aws-node-ts.md` — Lambda handlers, middleware, exports |
| `domain` | `<workspace>/wiki/entities/domain_auth.md` — cross-package feature area (auth spans cognito + native + shared) |
```

- [ ] **Step 2: skills README — architecture tree (lines 102-104)**

Replace:
```
    ├── apps/<app>/            # one folder per application workspace; overview at apps/<app>/overview.md
    ├── packages/<pkg>/        # one folder per library/service workspace; overview at packages/<pkg>/overview.md
    ├── domains/<domain>/      # one folder per cross-package feature area; overview at domains/<domain>/overview.md
```
with:
```
    ├── entities/              # one graph-derived page per admitted entity (pkg_*, app_*, domain_*, dep_*, repo_*, *_tests_*)
```

- [ ] **Step 3: skills README — "Scan" operation bullet (line 118)**

Replace:
```
- **Scan** — walk the repo (`package.json`, `pnpm-workspace.yaml`, `pyproject.toml`, `Cargo.toml`, `go.mod`), propose/update stub `packages/*.md` pages, flag renames/deletions for human review
```
with:
```
- **Scan** — build the code graph from the repo (`package.json`, `pnpm-workspace.yaml`, `pyproject.toml`, `Cargo.toml`, `go.mod`) and write/update/delete one `entities/` page per admitted entity; surface deletions for human review
```

- [ ] **Step 4: skills README — quick-start scan comment (line 41)**

Replace:
```
# 3. Scan the repo — creates a stub page for every workspace package (or for the single package, if not a monorepo)
```
with:
```
# 3. Scan the repo — renders one entities/ page per admitted entity (package, app, domain, dependency, …)
```

- [ ] **Step 5: plugin root README — scan-row wording (line 73)**

Replace:
```
| `/graph-wiki:scan` | Walk the repo; create/update package and app stub pages; surface doc candidates |
```
with:
```
| `/graph-wiki:scan` | Build the code graph; create/update/delete one `entities/` page per admitted entity |
```

- [ ] **Step 6: Verify**

Run:
```bash
grep -nE "apps/<app>/|packages/<pkg>/|domains/<domain>/|wiki/apps/|wiki/packages/|wiki/domains/|stub page|stub pages" plugins/graph-wiki/README.md plugins/graph-wiki/skills/graph-wiki/README.md
```
Expected: no matches.

- [ ] **Step 7: Commit**

```bash
git add plugins/graph-wiki/README.md plugins/graph-wiki/skills/graph-wiki/README.md
git commit -m "docs(plugin): READMEs describe entities/ layout

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

---

## Task A7: Strip obsidian-markdown from the remaining files

**Files:**
- Edit: `plugins/graph-wiki/agents/scanner.md`
- Edit: `plugins/graph-wiki/agents/ingestor.md`
- Edit: `plugins/graph-wiki/CLAUDE.md`

Librarian (A4) and linter (B4) drop their own refs; SKILL.md dropped its "Related skills" bullet (A5). This task clears the rest.

- [ ] **Step 1: `scanner.md` frontmatter (line 4)**

Replace:
```
skills: [graph-wiki, obsidian-markdown]
```
with:
```
skills: [graph-wiki]
```

- [ ] **Step 2: `scanner.md` rule (line 59)**

The rule currently reads:
```
- **Invoke the `obsidian-markdown` skill** if you hand-edit any entity page (you normally won't — the script owns them). Scanner-owned frontmatter keys are replaced every scan; human keys (`status`, `last_reviewed`, `owner`, `notes`) and a non-empty `summary` are preserved.
```
Replace with (drop the skill invocation, keep the frontmatter-preservation guidance):
```
- **If you hand-edit any entity page** (you normally won't — the script owns them), preserve human keys. Scanner-owned frontmatter keys are replaced every scan; human keys (`status`, `last_reviewed`, `owner`, `notes`) and a non-empty `summary` are preserved.
```

- [ ] **Step 3: `ingestor.md` frontmatter (line 4)**

Replace:
```
skills: [graph-wiki, obsidian-markdown]
```
with:
```
skills: [graph-wiki]
```

- [ ] **Step 4: `ingestor.md` rule (line 95)**

The rule currently reads:
```
- **Invoke the `obsidian-markdown` skill** before writing the source summary or editing any vault page — the vault is an Obsidian vault, so use wikilinks (`[[Note]]`), embeds (`![[file]]`), callouts (`> [!warning]`), proper YAML frontmatter, and `==highlight==` syntax. Plain Markdown links between vault pages are wrong; use wikilinks so Obsidian tracks renames.
```
Replace with (drop the skill invocation, keep the Obsidian-syntax guidance):
```
- **Use Obsidian syntax** when writing the source summary or editing any vault page — the vault is an Obsidian vault, so use wikilinks (`[[Note]]`), embeds (`![[file]]`), callouts (`> [!warning]`), proper YAML frontmatter, and `==highlight==` syntax. Plain Markdown links between vault pages are wrong; use wikilinks so Obsidian tracks renames.
```

- [ ] **Step 5: `CLAUDE.md` tree diagram (the `skills/` block near the top)**

In the "What lives here" tree, remove the `obsidian-markdown` line. Replace:
```
├── skills/
│   ├── graph-wiki/           # maintainer skill: SKILL.md + references/ + scripts/
│   └── obsidian-markdown/    # formatting reference invoked when writing vault pages
```
with:
```
├── skills/
│   └── graph-wiki/           # maintainer skill: SKILL.md + references/ + scripts/
```

- [ ] **Step 6: Repo-wide verification — no obsidian-markdown refs remain**

Run:
```bash
grep -rn "obsidian-markdown" plugins/graph-wiki
```
Expected: **no matches anywhere** in the plugin tree.

(Note: `references/obsidian-setup.md` and the `obsidian` tag / "Obsidian" prose refer to the Obsidian *app*, not the removed *skill* — those are correct and stay. This grep is specifically for the hyphenated skill name.)

- [ ] **Step 7: Commit**

```bash
git add plugins/graph-wiki/agents/scanner.md plugins/graph-wiki/agents/ingestor.md plugins/graph-wiki/CLAUDE.md
git commit -m "docs(plugin): remove dangling obsidian-markdown skill references

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

---

## Task A8: Slice 2 doc-sweep verification

**Files:** none (verification only)

- [ ] **Step 1: No stale page-routing vocabulary in Slice-2-owned docs**

Run:
```bash
grep -rnE "wiki/(apps|packages|domains)/|apps/<app>|packages/<pkg>|domains/<domain>|overview\.md|stub package|stub pages" \
  plugins/graph-wiki/commands/bootstrap.md \
  plugins/graph-wiki/commands/query.md \
  plugins/graph-wiki/commands/log.md \
  plugins/graph-wiki/agents/librarian.md \
  plugins/graph-wiki/skills/graph-wiki/SKILL.md \
  plugins/graph-wiki/skills/graph-wiki/README.md \
  plugins/graph-wiki/README.md \
  plugins/graph-wiki/skills/graph-wiki/references/query-workflow.md
```
Expected: no matches. (Slice-1-owned docs — `scan-workflow.md`, `detection-workflow.md`, `wiki-schema.md`, `page-formats.md`, `monorepo-principles.md` — are NOT in this list; do not re-edit them here. `ingest-workflow.md`/`ingestor.md` page-routing belongs to the deferred Slice 4.)

- [ ] **Step 2: No obsidian-markdown skill references anywhere**

Run:
```bash
grep -rn "obsidian-markdown" plugins/graph-wiki
```
Expected: no matches.

- [ ] **Step 3: No new commit (verification only — fix-forward if a grep fails)**

If either grep returns matches, fix them under the appropriate task above and re-run.

---

# Part B — Slice 3: entity-aware lint

## Task B1: `code_drift` recognizes entity pages

**Files:**
- Modify: `packages/wiki-io/src/wiki_io/lint_wiki.py`
- Test: `packages/wiki-io/tests/test_lint_wiki.py` (extend)

The inline `code_drift` check (lint_wiki.py:238-313) finds package/app vault pages by filtering on `category in ("package","app")` and a `packages/<slug>/` path shape. Entity pages have neither `category` (they use `kind`) nor that path (they live at `entities/pkg_<name>.md`), so on an `entities/` wiki the check reports `packages_in_vault: 0` and every package as `missing_in_vault`. Add entity recognition alongside the legacy logic.

- [ ] **Step 1: Write the failing test**

Append to `packages/wiki-io/tests/test_lint_wiki.py`:

```python
def test_code_drift_recognizes_entity_pages(tmp_path: Path, monkeypatch) -> None:
    """Code-drift must match entities/ pages (kind: package, uri: pkg:org/repo/<name>)
    against on-disk workspace slugs — the new single-entities-folder layout."""
    from wiki_io import lint_wiki as lw

    workspace = tmp_path / "workspace"
    workspace.mkdir()
    wiki = workspace / "wiki"
    (wiki / "entities").mkdir(parents=True)
    (wiki / "entities" / "pkg_alpha.md").write_text(
        "---\ntitle: alpha\nuri: pkg:org/repo/alpha\nkind: package\n"
        "graph_name: alpha\nupdated: 2099-01-01\n---\n\n## Narrative\n_(scanner will populate on next scan)_\n",
        encoding="utf-8",
    )

    monkeypatch.setattr(lw, "_scan_discover", lambda repo, pinned_containers=None: [{"name": "alpha"}])

    result = lw.scan(wiki, stale_days=90, log_gap_days=14, repo_path=tmp_path / "repo")
    cd = result["code_drift"]

    assert cd["packages_on_disk"] == 1
    assert cd["packages_in_vault"] == 1
    assert cd["missing_in_vault"] == []
    assert cd["orphaned_in_vault"] == []
```

- [ ] **Step 2: Run to verify it fails**

Run: `uv run pytest packages/wiki-io/tests/test_lint_wiki.py::test_code_drift_recognizes_entity_pages -v`
Expected: FAIL — `packages_in_vault == 0` and `missing_in_vault == ["alpha"]` (entity page not recognized).

- [ ] **Step 3: Add an entity-slug helper and fold it into the drift computation**

In `lint_wiki.py`, inside `scan()`, the legacy `_pkg_slug` helper is defined at lines 255-265. **Immediately after** that function (after its `return None` on line 265, before the `vault_pkg_pages = {...}` comprehension on line 267), add:

```python
            def _entity_pkg_slug(fm: dict) -> str | None:
                """Slug for a graph-derived entities/ page (kind: package|app).

                The workspace slug is the final path segment of the entity URI
                (``pkg:org/repo/alpha`` -> ``alpha``), unscoped to match disk
                names the same way legacy pages are compared.
                """
                if fm.get("kind") not in ("package", "app"):
                    return None
                uri = (fm.get("uri") or "").strip()
                if not uri:
                    return None
                tail = uri.rsplit("/", 1)[-1].rsplit(":", 1)[-1]
                return _unscope(tail) if tail else None
```

Then replace the `vault_pkg_pages` comprehension (lines 267-271):

```python
            vault_pkg_pages = {
                k: p
                for k, p in pages.items()
                if p["fm"].get("category") in ("package", "app") and _pkg_slug(k) is not None
            }
            vault_names = {_pkg_slug(k) for k in vault_pkg_pages}
```

with a combined legacy+entity form:

```python
            def _slug_for(k: str, p: dict) -> str | None:
                """Resolve a vault page's package slug: legacy path-shorthand
                first, then the entity-page (kind+uri) form."""
                if p["fm"].get("category") in ("package", "app"):
                    return _pkg_slug(k)
                return _entity_pkg_slug(p["fm"])

            vault_pkg_pages = {k: p for k, p in pages.items() if _slug_for(k, p) is not None}
            vault_names = {_slug_for(k, p) for k, p in vault_pkg_pages.items()}
```

Finally, update the `planned_names` line (line 278) to use the same combined slug resolver:

```python
            planned_names = {_pkg_slug(k) for k, p in vault_pkg_pages.items() if p["fm"].get("status") == "planned"}
```

becomes:

```python
            planned_names = {_slug_for(k, p) for k, p in vault_pkg_pages.items() if p["fm"].get("status") == "planned"}
```

(The `exports_drift` loop at lines 289-310 uses `_pkg_slug(k)` and `continue`s when it is `None`; entity pages return `None` there and are skipped — correct, since entity pages carry no `exports` frontmatter. Leave that loop unchanged.)

- [ ] **Step 4: Run the new test to verify it passes**

Run: `uv run pytest packages/wiki-io/tests/test_lint_wiki.py::test_code_drift_recognizes_entity_pages -v`
Expected: PASS.

- [ ] **Step 5: Run the legacy code-drift tests — no regression**

Run:
```bash
uv run pytest packages/wiki-io/tests/test_lint_wiki.py::test_code_drift_recognizes_overview_md \
              packages/wiki-io/tests/test_lint_wiki.py::test_code_drift_recognizes_legacy_pkg_pkg_md -v
```
Expected: both PASS (legacy pages still resolve via `_pkg_slug`).

- [ ] **Step 6: Commit**

```bash
git add packages/wiki-io/src/wiki_io/lint_wiki.py packages/wiki-io/tests/test_lint_wiki.py
git commit -m "fix(lint): code-drift recognizes entities/ package and app pages

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

---

## Task B2: `missing_frontmatter` / `missing_tokens` are entity-aware

**Files:**
- Modify: `packages/wiki-io/src/wiki_io/lint_wiki.py`
- Test: `packages/wiki-io/tests/test_lint_wiki.py` (extend)

The frontmatter check (lint_wiki.py:210-214) requires `{title, category, summary}` and a `tokens` field for every linted page. Entity pages carry `title`/`uri`/`kind`/`updated` but no `category`, `summary`, or `tokens` — so on an `entities/` wiki every entity page is flagged `missing_frontmatter` *and* `missing_tokens`. Branch the check on whether the page is an entity page.

- [ ] **Step 1: Write the failing test**

Append to `packages/wiki-io/tests/test_lint_wiki.py`:

```python
def test_entity_pages_use_entity_frontmatter_contract(tmp_path: Path, monkeypatch) -> None:
    """A well-formed entities/ page (title/uri/kind/updated, no category/tokens)
    must NOT be flagged for missing_frontmatter or missing_tokens; a curated
    page still must carry title/category/summary/tokens."""
    from wiki_io import lint_wiki as lw

    workspace = tmp_path / "workspace"
    workspace.mkdir()
    wiki = workspace / "wiki"
    (wiki / "entities").mkdir(parents=True)
    (wiki / "entities" / "pkg_alpha.md").write_text(
        "---\ntitle: alpha\nuri: pkg:org/repo/alpha\nkind: package\n"
        "graph_name: alpha\nupdated: 2099-01-01\n---\n\n## Narrative\n_(scanner will populate on next scan)_\n",
        encoding="utf-8",
    )
    # A curated concept page that IS missing summary + tokens — still flagged.
    (wiki / "concepts").mkdir(parents=True)
    (wiki / "concepts" / "bad.md").write_text(
        "---\ntitle: Bad\ncategory: concept\nupdated: 2099-01-01\n---\n\nBody.\n",
        encoding="utf-8",
    )

    monkeypatch.setattr(lw, "_scan_discover", lambda repo, pinned_containers=None: [{"name": "alpha"}])

    result = lw.scan(wiki, stale_days=90, log_gap_days=14, repo_path=tmp_path / "repo")

    assert "entities/pkg_alpha" not in result["missing_frontmatter"]
    assert "entities/pkg_alpha" not in result["missing_tokens"]
    # The curated page is still held to the curated contract.
    assert "concepts/bad" in result["missing_frontmatter"]
    assert "concepts/bad" in result["missing_tokens"]
```

- [ ] **Step 2: Run to verify it fails**

Run: `uv run pytest packages/wiki-io/tests/test_lint_wiki.py::test_entity_pages_use_entity_frontmatter_contract -v`
Expected: FAIL — `entities/pkg_alpha` appears in both `missing_frontmatter` and `missing_tokens`.

- [ ] **Step 3: Import `ADMITTED_KINDS`**

In `lint_wiki.py`, add the import alongside the other `wiki_io` imports. After line 39 (`from wiki_io.layout_io import read_layout`), add:

```python
from wiki_io.entity_writer import ADMITTED_KINDS
```

- [ ] **Step 4: Branch the frontmatter/tokens check on entity-ness**

Replace the body of the per-page loop at lines 207-214:

```python
        fm = page["fm"]
        title = fm.get("title") or Path(key).name
        titles[title].append(key)
        required = {"title", "category", "summary"}
        if not required.issubset(fm.keys()):
            missing_fm.append(key)
        if "tokens" not in fm:
            missing_tokens.append(key)
```

with:

```python
        fm = page["fm"]
        title = fm.get("title") or Path(key).name
        titles[title].append(key)
        if fm.get("kind") in ADMITTED_KINDS:
            # Graph-derived entities/ pages use the entity frontmatter contract:
            # title/uri/kind are scanner-owned; they carry no category/summary/tokens.
            if not {"title", "uri", "kind"}.issubset(fm.keys()):
                missing_fm.append(key)
        else:
            required = {"title", "category", "summary"}
            if not required.issubset(fm.keys()):
                missing_fm.append(key)
            if "tokens" not in fm:
                missing_tokens.append(key)
```

(`duplicate_titles` and the `stale` `updated:` check below this block are unchanged — they apply to both page kinds.)

- [ ] **Step 5: Run to verify it passes**

Run: `uv run pytest packages/wiki-io/tests/test_lint_wiki.py::test_entity_pages_use_entity_frontmatter_contract -v`
Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add packages/wiki-io/src/wiki_io/lint_wiki.py packages/wiki-io/tests/test_lint_wiki.py
git commit -m "fix(lint): entities/ pages use entity frontmatter contract (no category/tokens)

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

---

## Task B3: `container.py` `FIXED_DIRS` includes `entities`

**Files:**
- Modify: `packages/wiki-io/src/wiki_io/lint/container.py`
- Test: `packages/wiki-io/tests/test_lint_wiki.py` (extend)

`container.check()` (container.py:30-62) walks the vault root and flags any dir not in `FIXED_DIRS`, not pinned, and not in `LEGACY_DIRS` as an "orphan vault dir". `FIXED_DIRS` (lines 11-23) lists `apps`/`packages`/`domains` but **not** `entities`, so the new `entities/` folder is reported as an orphan on every lint run.

- [ ] **Step 1: Write the failing test**

Append to `packages/wiki-io/tests/test_lint_wiki.py`:

```python
def test_container_fixed_dirs_includes_entities() -> None:
    """The single entities/ folder must be a recognized fixed vault dir so
    container drift never reports it as an orphan."""
    from wiki_io.lint.container import FIXED_DIRS

    assert "entities" in FIXED_DIRS
```

- [ ] **Step 2: Run to verify it fails**

Run: `uv run pytest packages/wiki-io/tests/test_lint_wiki.py::test_container_fixed_dirs_includes_entities -v`
Expected: FAIL — `assert "entities" in FIXED_DIRS` (it isn't yet).

- [ ] **Step 3: Add `entities` to `FIXED_DIRS`**

In `container.py`, the set at lines 11-23 currently is:

```python
FIXED_DIRS = {
    "concepts",
    "architecture",
    "adrs",
    "sources",
    "dependencies",
    "work",
    ".templates",
    "apps",
    "packages",
    "domains",
    ".obsidian",
}
```

Add `"entities",` as the first entry:

```python
FIXED_DIRS = {
    "entities",
    "concepts",
    "architecture",
    "adrs",
    "sources",
    "dependencies",
    "work",
    ".templates",
    "apps",
    "packages",
    "domains",
    ".obsidian",
}
```

(Leave `apps`/`packages`/`domains` in place — they're now legacy page folders that should not exist, but tolerating them here is harmless and avoids touching the container tests. Migrating them to `LEGACY_DIRS` is out of scope.)

- [ ] **Step 4: Run to verify it passes**

Run: `uv run pytest packages/wiki-io/tests/test_lint_wiki.py::test_container_fixed_dirs_includes_entities -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add packages/wiki-io/src/wiki_io/lint/container.py packages/wiki-io/tests/test_lint_wiki.py
git commit -m "fix(lint): container drift treats entities/ as a fixed vault dir

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

---

## Task B4: `linter.md` → `entities/` + drop obsidian-markdown

**Files:**
- Edit: `plugins/graph-wiki/agents/linter.md`

- [ ] **Step 1: Drop `obsidian-markdown` from the skills frontmatter (line 4)**

Replace:
```
skills: [graph-wiki, obsidian-markdown]
```
with:
```
skills: [graph-wiki]
```

- [ ] **Step 2: Fix the vault↔code spot-check (line 49)**

Replace:
```
- **Contradictions (vault↔code)** — spot-check recently-touched `packages/<name>/overview.md` pages against current code
```
with:
```
- **Contradictions (vault↔code)** — spot-check recently-touched `entities/pkg_<name>.md` / `entities/app_<name>.md` pages against current code
```

- [ ] **Step 3: Fix the suggested-actions block (lines 82-84)**

Replace:
```
2. Archive or delete `<workspace>/wiki/packages/<old-pkg>/`
3. Re-read `packages/<pkg>/src/index.ts`; update vault exports frontmatter
```
with:
```
2. Re-run `/graph-wiki:scan` — it deletes the entity page for `<old-pkg>` automatically when its graph node is gone
3. Re-run `/graph-wiki:scan` to refresh `entities/pkg_<pkg>.md` graph-derived frontmatter from current code
```

- [ ] **Step 4: Remove the obsidian-markdown rule (line 100)**

Delete this bullet entirely:
```
- **Invoke the `obsidian-markdown` skill** during the semantic pass — verify pages use valid Obsidian syntax (wikilinks instead of plain Markdown links between vault pages, well-formed callouts, properties in frontmatter rather than inline, embeds via `![[...]]`). Flag pages that mix Markdown links with `.md` targets, malformed callouts, or properties duplicated between frontmatter and body.
```
and replace it with a non-skill version that keeps the semantic-pass intent:
```
- **Check Obsidian syntax** during the semantic pass — flag pages that use plain Markdown links to `.md` targets instead of `[[wikilinks]]`, malformed callouts, or properties duplicated between frontmatter and body.
```

- [ ] **Step 5: Verify**

Run:
```bash
grep -nE "obsidian-markdown|packages/<name>/overview\.md|wiki/packages/<old-pkg>|packages/<pkg>/src/index\.ts" plugins/graph-wiki/agents/linter.md
```
Expected: no matches.

- [ ] **Step 6: Commit**

```bash
git add plugins/graph-wiki/agents/linter.md
git commit -m "docs(plugin): linter agent reasons over entities/; drop obsidian-markdown ref

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

---

## Task B5: `lint-workflow.md` → `entities/`

**Files:**
- Edit: `plugins/graph-wiki/skills/graph-wiki/references/lint-workflow.md`

- [ ] **Step 1: Fix the missing-frontmatter + code-drift descriptions (lines 26, 29)**

Replace:
```
- **Missing frontmatter** — pages lacking `title`, `category`, or `summary`
```
with:
```
- **Missing frontmatter** — curated pages lacking `title`/`category`/`summary`; `entities/` pages lacking `title`/`uri`/`kind` (entity pages use the scanner-owned frontmatter contract, not `category`/`tokens`)
```

Replace:
```
- **Code drift** (monorepo-specific) — packages on disk vs. in vault. Pages declaring `status: planned` in frontmatter are excluded from `orphaned_in_vault` and surfaced separately under `planned_in_vault`, so deliberately seeded plugin/package pages don't drown the signal.
```
with:
```
- **Code drift** (monorepo-specific) — packages/apps on disk vs. `entities/` pages in the vault (matched by entity `kind` + `uri`; legacy `packages/<slug>/` pages still recognized). Pages declaring `status: planned` in frontmatter are excluded from `orphaned_in_vault` and surfaced separately under `planned_in_vault`, so deliberately seeded pages don't drown the signal.
```

- [ ] **Step 2: Add `entities` to the container-drift description (line 30)**

Replace:
```
- **`container_drift`** (`lint/container.py`) — pinned vault dirs vs. disk; orphan vault dirs. Tolerates legacy `issues/`, `roadmap/`, `comparisons/` with a hint pointing at the §2 migrators.
```
with:
```
- **`container_drift`** (`lint/container.py`) — pinned vault dirs vs. disk; orphan vault dirs. `entities/` is a recognized fixed dir. Tolerates legacy `issues/`, `roadmap/`, `comparisons/` with a hint pointing at the §2 migrators.
```

- [ ] **Step 3: Note the entity-page no-op on `package_sync` / `domain` (lines 32, 34)**

Replace:
```
- **`package_sync` drift** (`lint/package_sync.py`) — same shape against `package_path` / `app_path`. Pages with no `last_sync_commit` are flagged as "never synced".
```
with:
```
- **`package_sync` drift** (`lint/package_sync.py`) — same shape against `package_path` / `app_path` on legacy/ingest-tracked pages. Graph-derived `entities/` pages don't carry `last_sync_commit`, so code drift (above) is the entity-layout freshness signal; re-run `/graph-wiki:scan` to refresh them.
```

Replace:
```
- **`domain` placement** (`lint/domain.py`) — package pages whose vault location disagrees with their `domain:` frontmatter.
```
with:
```
- **`domain` placement** (`lint/domain.py`) — legacy package pages whose vault location disagrees with their `domain:` frontmatter. `entities/` pages all live in one folder, so this check only applies to legacy layouts.
```

- [ ] **Step 4: Fix the Pass-2 vault↔code spot-check (lines 73-75)**

Replace:
```
### B. Contradictions between vault and code

For each recently-touched `packages/<name>/overview.md` page, spot-check the hand-written prose against the actual `package.json` and `src/index.ts`.
```
with:
```
### B. Contradictions between vault and code

For each recently-touched `entities/pkg_<name>.md` / `entities/app_<name>.md` page, spot-check the `## Narrative` prose and `## Public API` claims against the actual `package.json` and `src/index.ts`.
```

- [ ] **Step 5: Verify**

Run:
```bash
grep -nE "packages/<name>/overview\.md|package_path. / .app_path. Pages with no|lacking .title., .category., or .summary" plugins/graph-wiki/skills/graph-wiki/references/lint-workflow.md
```
Expected: no matches.

- [ ] **Step 6: Commit**

```bash
git add plugins/graph-wiki/skills/graph-wiki/references/lint-workflow.md
git commit -m "docs(plugin): lint-workflow describes entity-aware checks

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

---

## Task B6: Slice 3 verification

**Files:** none (verification only)

- [ ] **Step 1: Full wiki-io lint suite**

Run: `uv run pytest packages/wiki-io/tests/test_lint_wiki.py -v`
Expected: all PASS — the three new tests (`test_code_drift_recognizes_entity_pages`, `test_entity_pages_use_entity_frontmatter_contract`, `test_container_fixed_dirs_includes_entities`) and the two legacy code-drift tests (`test_code_drift_recognizes_overview_md`, `test_code_drift_recognizes_legacy_pkg_pkg_md`) all green.

- [ ] **Step 2: Full wiki-io suite — no regressions**

Run: `uv run pytest packages/wiki-io/ -q`
Expected: all green. Pay attention to any container/lint sub-module tests (the `FIXED_DIRS` change and the `ADMITTED_KINDS` import are the only cross-cutting edits).

- [ ] **Step 3: Bedrock-shim argv contract unaffected**

Run: `uv run --package graph-wiki-cli python -m pytest packages/graph-wiki-cli/tests/unit/test_plugin_bedrock_shims.py -v`
Expected: PASS (Slice 3 touched no shim; the lint shim's `gw wiki lint` mapping is unchanged).

- [ ] **Step 4: Manual smoke — lint runs clean on an entities/ wiki**

On a fixture workspace that has been scanned to `entities/` (use `fixtures/single-package/` or `fixtures/mono-shaped/` per `packages/wiki-io/tests/helpers.py`; bootstrap + `gw scan --no-narrate` from Slice 1, or hand-seed an `entities/pkg_*.md`), run:
```bash
uv run --project "$PWD" python plugins/graph-wiki/skills/graph-wiki/scripts/lint_wiki.py
```
Expected: `code drift` reports the packages as present (not all missing); no `missing frontmatter` / `missing tokens` flood for entity pages; no `orphan vault dir 'entities'`. Record the observed counts in the task notes.

- [ ] **Step 5: No commit (verification only)**

Only commit if Steps 1-4 surfaced a fix.

---

## Appendix — Entities vocabulary (pointer)

The canonical kind/prefix/filename/frontmatter table lives in **Appendix A of `docs/superpowers/plans/2026-06-02-graph-wiki-plugin-entities-parity-slice1.md`**. Authoritative code: `packages/wiki-io/src/wiki_io/entity_writer.py` (`ADMITTED_KINDS`, `short_filename`, `SCANNER_OWNED_KEYS`), `packages/wiki-io/src/wiki_io/init_vault.py` (`FIXED_VAULT_DIRS`), and `packages/wiki-io/src/wiki_io/assets/page-templates/entity-*.md`. When a doc edit needs the full table, copy it from the Slice 1 appendix.

---

## Self-Review notes (author)

- **Slice 2 roadmap coverage** (spec line 100 — "bootstrap + query + log + reference sweep + obsidian-markdown skill"): bootstrap (A1), query+log commands (A2), query-workflow + librarian reference/agent (A3, A4), SKILL.md + both READMEs (A5, A6). The `obsidian-markdown` skill sub-item is replaced by **removal of its dangling references** (A4, A5, A7, B4) per the user's "I removed it from the plugin" + "strip all refs" decision. Slice-1-owned reference docs (`scan-workflow`, `detection-workflow`, `wiki-schema`, `page-formats`, `monorepo-principles`) are intentionally NOT re-edited; `ingest-workflow`/`ingestor` page-routing is deferred to Slice 4.
- **Slice 3 roadmap coverage** (spec line 101 — "fix the code-drift check … update the linter agent + lint-workflow.md"): code-drift (B1) in `wiki_io.lint_wiki` (the module the plugin's lint shim invokes), linter agent (B4), lint-workflow.md (B5). **Expanded** per the "entity-aware lint" decision to also fix `missing_frontmatter`/`missing_tokens` (B2) and `container.FIXED_DIRS` (B3) — the two other real false-positive sources on an `entities/` wiki, without which "lint → entities/" parity is incomplete.
- **Out-of-scope honored:** no change to `package_sync`/`file_map`/`domain`/`workflow_hints` lint sub-modules (silent no-ops on entity pages, not false positives); no shim or `graph-wiki-cli`/`graph-wiki-core` change (lint fix is wholly in `wiki_io`); legacy `packages/<slug>/` recognition preserved so the two existing code-drift tests stay green; no change to `entity_writer`/`init_vault`/templates.
- **Type/name consistency:** new helpers `_entity_pkg_slug(fm)` and `_slug_for(k, p)` are nested in `scan()` next to the existing `_pkg_slug(key)`; `_unscope` is the module-level import already at lint_wiki.py:33; `ADMITTED_KINDS` imported from `wiki_io.entity_writer`. Test page keys (`entities/pkg_alpha`, `concepts/bad`) match the `.md`-stripped `key` form scan() builds (lint_wiki.py:102). `FIXED_DIRS` is the real symbol name in `lint/container.py`.
- **Placeholder scan:** every code/test step shows complete code; every doc step shows verbatim old→new text; every verification step gives an exact command + expected result.
