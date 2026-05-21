# Wiki Schema

The wiki sits inside a graph-wiki workspace alongside other workspace-level directories. The LLM must respect the boundaries.

## Layout

The wiki lives at `<workspace>/wiki/`. The workspace is resolved via `workspace_io` (defaults to `<repo>/graph-wiki/`; override with `.graph-wiki.yaml`'s workspace path key). The Obsidian vault opens at `<workspace>/`, so `raw/` (immutable sources) and `work/` (work tracker) sit at the workspace root as siblings of `wiki/` — both owned by `workspace_io`, not by this plugin.

```
<repo>/graph-wiki/               # workspace; Obsidian vault opens here
├── .graph-wiki.yaml             # workspace manifest (owned by workspace_io)
├── CLAUDE.md                    # workspace-level schema (owned by workspace_io)
├── raw/                         # IMMUTABLE ingested sources (owned by workspace_io)
│   ├── articles/*.md            # Obsidian Web Clipper output
│   ├── specs/*.md               # design docs, RFCs
│   ├── prs/*.md                 # PR descriptions and review notes
│   ├── tickets/*.md             # issue exports
│   ├── transcripts/*.md         # meeting and design-session notes
│   └── assets/                  # images referenced by sources
├── work/                        # unified bugs, tech debt, features, initiatives, spikes
│   └── archived/                # terminal-status items aged past archive threshold
├── knowledge/                   # other plugin-managed knowledge stores
└── wiki/                        # this plugin's curated knowledge base
    ├── index.md                 # content catalog — updated every ingest/scan
    ├── log.md                   # append-only timeline
    ├── apps/                    # [conditional] one folder per application workspace
    │   └── <app>/               # e.g. apps/web-next-ts/
    │       └── <app>.md         #   the app overview (category: app)
    ├── packages/                # [conditional] cross-domain library/service packages
    │   └── <pkg>/               # e.g. packages/common-aws-node-ts/
    │       └── <pkg>.md         #   the package overview (category: package)
    ├── domains/                 # [conditional] feature areas across packages
    │   └── <domain>/
    │       ├── <domain>.md      #   the domain overview (category: domain)
    │       ├── details.md       #   concepts, dependencies, decisions, sources, contrasts
    │       └── packages/        #   the domain's workspace packages
    │           └── <pkg>/
    │               └── <pkg>.md
    ├── concepts/                # cross-cutting technical concepts (and `<a>-vs-<b>.md` comparisons)
    ├── dependencies/            # external libraries — index.md auto-generated; detail pages opt-in
    ├── sources/                 # one summary page per ingested source
    ├── architecture/            # high-level syntheses
    ├── adrs/                    # architecture decision records
    ├── .templates/              # page templates (reference only, not indexed)
    ├── CLAUDE.md                # wiki schema file for Claude Code
    ├── AGENTS.md                # same schema for Codex/Cursor/Antigravity
    └── .cursorrules             # (optional) legacy Cursor
```

`apps/`, `packages/`, and `domains/` are **conditional containers** — `init_vault.py` creates them only when the detector classifies a top-level directory as an app, package, or domain. A single-package repo has none of these (the repo *is* the package); its module/area pages live at the wiki root or under `concepts/`. A library-only monorepo has `packages/` but not `apps/`. The pinned set is recorded under `containers:` in `<workspace>/wiki/CLAUDE.md` and `<workspace>/wiki/AGENTS.md`.

The `package-family` classification adds no new top-level container — its pages land wherever the row's `vault_dir:` points (commonly under `domains/<d>/packages/`). A `package-family` row may also use a slashed `source:` path (e.g. `references/hubspot/hubspot-ui-extensions`); the source dir need not be a top-level repo entry.

## Iron rules

1. **The code is the source of truth.** If the wiki disagrees with the code, update the wiki — never the other way around.
2. **`<workspace>/raw/` is immutable.** The LLM reads from `raw/` but never writes to it. Never rename, never delete, never edit.
3. **All wiki writes go under `<workspace>/wiki/`.** Work items go to `<workspace>/work/` (owned by `workspace_io`). No exceptions.
4. **Every scan or ingest updates ≥3 files:** the touched page(s), `index.md`, `log.md`. A typical ingest touches 5-15.
5. **Every wiki page carries YAML frontmatter.** Without frontmatter, `update_index.py` and `lint_wiki.py` can't see it.

## Required page frontmatter

```yaml
---
title: common-aws-node-ts
category: package            # see enum below
summary: Lambda handlers, middleware, and AWS SDK client wrappers shared across all -aws-node-ts packages
tags: [aws, lambda, middleware]
sources: 2                   # optional — number of sources referencing this page
updated: 2026-04-20
---
```

Allowed `category` values: `app`, `package`, `domain`, `concept`, `dependency`, `work`, `source`, `architecture`, `adr`.

## Category-specific frontmatter

### App pages

```yaml
---
title: web-next-ts
category: app
summary: Next.js 15 web application — dashboard and admin surfaces
app_path: apps/web-next-ts                    # relative to repo root
platform: web                                 # web | ios | android | mobile | desktop | cli
framework: nextjs                             # nextjs | expo | vite | remix | sveltekit | tauri | electron | cli
language: typescript
entry_points: [app/(dashboard)/page.tsx, app/api/auth/route.ts]
consumes_domains: [auth, timeline, healthkit]
depends_on: [@psprowls/shared-ui-react-ts, @psprowls/shared-domain-ts, ...]
deployment: vercel                            # vercel | aws-amplify | cloudflare | app-store | self-hosted | …
tags: [web, nextjs]
sources: 0
updated: 2026-04-20
last_sync_commit:                             # full SHA of the repo commit this page reflects, set by /graph-wiki:scan
last_sync_at:                                 # YYYY-MM-DD when sync state was recorded
---
```

`last_sync_commit` (40-char SHA) and `last_sync_at` (YYYY-MM-DD) record the repo commit this page was last verified against. `/graph-wiki:scan` writes both when run with a clean working tree on `main`. `/graph-wiki:lint` compares HEAD against `last_sync_commit` to flag packages whose source has changed since the last review.

### Package pages

```yaml
---
title: common-aws-node-ts
category: package
summary: Lambda handler factories and middleware pipeline
package_path: packages/common-aws-node-ts    # relative to repo root
package_type: library                         # library | service | tool
language: typescript                          # typescript | python | rust | go | …
depends_on: [@psprowls/common-context-node-ts, ...]
tags: [aws, lambda]
sources: 0
updated: 2026-04-20
last_sync_commit:                             # full SHA of the repo commit this page reflects, set by /graph-wiki:scan
last_sync_at:                                 # YYYY-MM-DD when sync state was recorded
---
```

`last_sync_commit` and `last_sync_at` work the same as on app pages.

Hand-maintained `exports:` and `depended_on_by:` were dropped 2026-05-03; the package page's hand-written prose and `## Public API` section carry the exports narrative instead.

Note: `package_type: app` is retired — apps live in `<workspace>/wiki/apps/` with `category: app`. Services (long-running Lambda stacks, background workers) stay under `<workspace>/wiki/packages/` with `package_type: service`.

### Domain pages

```yaml
---
title: HealthKit
category: domain
summary: HealthKit data ingestion, normalization, and timeline integration
packages: [healthkit-aws-node-ts, healthkit-events-node-ts, healthkit-data-node-ts]
tags: [healthkit, ingestion]
sources: 0
updated: 2026-04-20
---
```

Conditional container — `init_vault.py` creates `<workspace>/wiki/domains/` only when the detector classifies a top-level repo directory as `domain`. Many repos don't have a literal `domains/` folder on disk; a domain may be a wiki-only construct expressed through naming convention (e.g. all `healthkit-*` packages). In that case the domain page still lives at `domains/<slug>/<slug>.md` in the wiki even though the underlying workspaces sit under `<repo>/packages/`. Single-package and library-only repos typically have no domain pages.

`packages:` lists the workspace packages owned by the domain. The page template's body sections (`## Scope`, `## Packages in this domain`, `## Linked packages from other domains`, `## Key flows`) capture what a frontmatter list can't.

### Concept pages

```yaml
---
title: Global Context
category: concept
summary: Per-request context object threaded through every Lambda handler
tags: [middleware, request-handling]
sources: 0
updated: 2026-04-20
---
```

Concepts are cross-cutting technical patterns — naming conventions, middleware shapes, contracts that span packages. A concept page is a one-paragraph definition, where the pattern appears in the code, and links to packages, dependencies, ADRs, and sources that motivate it. Comparisons live here too: `concepts/<a>-vs-<b>.md` for two-way, `concepts/<topic>-options.md` for n-way.

### Dependency pages

`kind:` discriminates three shapes. The auto-generated `dependencies/index.md` covers every dep; detail pages are opt-in for the load-bearing ones. The existence of a detail page *is* the load-bearing signal — `load_bearing: true` is recorded explicitly so lint can catch detail pages that should have been deleted.

**`kind: package`** (e.g., `dependencies/react.md`):

```yaml
---
title: React
category: dependency
kind: package
package_name: react
ecosystem: npm                  # npm | pypi | cargo | go | brew | system
family: ""                      # back-pointer if member of a package-family — empty otherwise
versions_in_use: ["19.0.0", "18.3.1"]
used_by: [web-next-ts, app-expo-ts]
upstream_url: https://react.dev
load_bearing: true
quirks: []
tags: [frontend, ui]
updated: 2026-04-20
---
```

**`kind: package-family`** (e.g., `dependencies/tailwind.md`):

```yaml
---
title: Tailwind CSS
category: dependency
kind: package-family
family_name: tailwind
members:                        # packages shipped under the family's brand
  - tailwindcss
  - "@tailwindcss/typography"
co_required:                    # tooling that travels with the family in practice
  - autoprefixer
  - postcss
load_bearing: true
upstream_url: https://tailwindcss.com
tags: [frontend, css]
updated: 2026-05-03
---
```

**`kind: service`** (e.g., `dependencies/mongodb-atlas.md`):

```yaml
---
title: MongoDB Atlas
category: dependency
kind: service
service_name: MongoDB Atlas
provider: mongodb-atlas         # aws | gcp | azure | mongodb-atlas | cloudflare | github | …
used_by: [location-aws-node-ts, healthkit-aws-node-ts]
upstream_url: https://www.mongodb.com/atlas
load_bearing: true
quirks: [region-locked-us-west-2]
tags: [database, infra]
updated: 2026-04-20
---
```

Field divergences:

- `package` uses `ecosystem:`; `service` uses `provider:`; `package-family` has neither (those live on the members).
- `versions_in_use` applies only to `package`. Services aren't versioned the same way.
- `package-family` uses `members:` and `co_required:` lists. Lint existence-checks members against scanned manifests.

### Work pages

Unified namespace replacing `issues/` + `roadmap/`. `category: work`. `kind:` discriminates between bug-shaped and feature-shaped items; a single status lifecycle covers both. Slugs follow `<YYYY-MM-DD>-<short-slug>.md` for items where date-of-filing matters (most bugs and spikes); `<short-slug>.md` for evergreen feature/initiative items.

```yaml
---
title: <Title>
category: work
kind: bug                       # bug | tech-debt | test-gap | security | perf | feature | initiative | spike
summary: <one-line>
status: open                    # open | accepted | in-progress | mitigated | resolved | wontfix | superseded
severity: medium                # bug | security | perf — leave blank for feature/initiative/spike
effort: small                   # trivial | small | medium | large
blast_radius: package           # file | package | domain | system
affects:
  - packages/location-aws-node-ts
target: 2026-Q2                 # feature | initiative — optional otherwise
owner: pat                      # populate when in-progress
opened: 2026-04-21
updated: 2026-05-03
related_tickets: []
related_prs: []
resolved_in: ""                 # required when resolved
superseded_by: ""               # required when superseded
mitigation: ""                  # required when mitigated
rationale: ""                   # required when wontfix
tags: [location, infrastructure]
---
```

The committed plan does **not** live in frontmatter — it's a markdown table under `## Plan` in the body. See [Body-table conventions](#body-table-conventions) below.

The lifecycle lint rules (`accepted-without-plan`, `stuck-open`, `done-when-missing`, etc.) and the `<workspace>/work/.work-index.json` sidecar generator live in **`graph-wiki`** (work_layer group). `workspace_io` creates the `work/` directory. See `references/lint-workflow.md` for what lives where.

> **Note:** The work-layer subsystem is not ported in graph-wiki v1.2. This note applies when/if work-layer support is added in a future version.

#### The `work/archived/` sub-namespace

Items that have reached a terminal status (`resolved`, `wontfix`,
`superseded`) and aged past the archive threshold may be moved to
`<workspace>/work/archived/<slug>.md`. They retain their full schema —
same frontmatter, same body convention, same wiki-page semantics —
but are excluded from:

- base structural lint (`/graph-wiki:lint`)
- the work-tracker sidecar (`<workspace>/work/.work-index.json`)
- consumer commands that read the sidecar

Items under `archived/` must already be in a terminal status; the
archive command (`/graph-wiki:archive`) enforces this on entry.
Restoring is a `git mv` from `archived/` back to `work/` plus
`/graph-wiki:regen-index`.

### Source pages

```yaml
---
title: "Auth Migration Spec"
category: source
summary: Spec for moving from session tokens to JWTs; addresses compliance flags
source_path: raw/specs/auth-migration.md   # raw/<...> for staged sources, repo-relative (e.g. docs/auth.md) for in-repo docs
source_type: spec                # spec | article | pr | ticket | transcript | rfc | doc | example
source_date: 2026-04-01
last_sync_commit:                # set only for in-repo docs (source_type: doc) — full SHA at last ingest, used by /graph-wiki:lint to detect changes
last_sync_at:                    # YYYY-MM-DD when sync state was recorded
authors: [@psprowls]
ingested: 2026-04-20
updated: 2026-04-20
---
```

In-repo docs (those surfaced by `/graph-wiki:scan` from a pinned `docs` container) use `source_type: doc`, set `source_path` to the repo-relative path, and record `last_sync_commit` and `last_sync_at`. PDF/DOCX/etc. are deferred — only `.md` is auto-surfaced today.

### Architecture pages

```yaml
---
title: Request flow
category: architecture
summary: How a request flows from edge → API → domain → datastore
packages: [web-next-ts, common-aws-node-ts, location-aws-node-ts]
tags: [architecture, request-flow]
sources: 0
updated: 2026-04-20
---
```

High-level syntheses — the layers, components, and flows that span multiple packages or domains. The `## Thesis` body section is the load-bearing part; the rest (layers, diagrams, key concepts, decisions) supports the thesis and rotates as the codebase changes. `packages:` lists the workspaces the synthesis reasons about so lint can flag when a referenced package goes away.

### ADR pages

```yaml
---
title: "ADR-0012: Move to ESM"
category: adr
adr_id: 0012
status: accepted                 # proposed | accepted | deprecated | superseded
decision_date: 2026-02-14
deciders: [@psprowls]
supersedes: null                 # ADR ID this replaces, if any
superseded_by: null              # ADR ID that replaces this, if any
tags: [build-system, modules]
updated: 2026-04-20
---
```

## Naming conventions

- **Filenames:** `kebab-case.md` — lowercase, hyphens, no spaces
- **Apps, packages, and domains live in folders.** The overview file inside each folder shares the folder's name (e.g. `apps/web-next-ts/web-next-ts.md`). Other content for that workspace can live alongside the overview file inside the same folder.
- **Apps:** `apps/<app-name>/<app-name>.md` — workspace name verbatim.
- **Packages (cross-domain):** `packages/<package-name>/<package-name>.md` — use the workspace name verbatim. For scoped names (`@psprowls/common-aws-node-ts`), drop the scope in the folder/file name but keep it in `title` frontmatter.
- **Domain-scoped packages:** `domains/<domain-slug>/packages/<package-name>/<package-name>.md` — same naming rule as cross-domain packages.
- **Domains:** `domains/<domain-slug>/<domain-slug>.md` — overview lives inside the domain folder.
- **Concepts:** `concepts/<concept-slug>.md` — e.g. `concepts/global-context.md`. Comparisons live here too: `concepts/<a>-vs-<b>.md` for two-way, `concepts/<topic>-options.md` for n-way.
- **Sources:** `sources/<YYYY-MM>-<short-slug>.md` — e.g. `sources/2026-04-auth-migration-spec.md`
- **ADRs:** `adrs/<NNNN>-<slug>.md` — e.g. `adrs/0012-move-to-esm.md`. Zero-padded ID, monotonically increasing.
- **Architecture:** `architecture/<topic>.md` — e.g. `architecture/request-flow.md`
- **Dependencies:** `dependencies/<package-name>.md` — use the registry name (`react.md`, `react-native-maps.md`). For scoped npm packages, replace `/` with `__` (`@tanstack__react-query.md`). Family pages use the family slug (`dependencies/tailwind.md`). Service pages use a slug derived from the service name (`dependencies/mongodb-atlas.md`).
- **Work:** `work/<YYYY-MM-DD>-<slug>.md` for date-of-filing-meaningful items (most bugs, most spikes); `work/<slug>.md` for evergreen feature/initiative items.

## Taxonomies

The categorical vocabularies that frontmatter fields draw from. These apply across multiple categories (mainly `work`); per-category enums (e.g. ADR `status`, dependency `kind`) live with the category above.

### `kind` (work)

Eight values, two origins:

| Kind | Origin | Typical shape |
|---|---|---|
| `bug` | discovered | symptom + root cause + fix |
| `tech-debt` | discovered | suboptimal pattern + refactor target |
| `test-gap` | discovered | missing coverage + test plan |
| `security` | discovered | exposure + remediation |
| `perf` | discovered or measured | regression + budget + fix |
| `feature` | intended | user-driven capability + scope |
| `initiative` | intended | multi-feature effort spanning weeks/quarters |
| `spike` | intended | time-boxed exploration with a question |

Schema/structure problems are `kind: bug` + `tag: data-model`. Wiki↔code drift filed by lint is `kind: tech-debt` + `tag: doc-drift`. Lifecycle and required fields are identical to the underlying kind; the discriminating live in tags rather than spawning new kinds.

### `kind` (dependency)

Three values: `package | package-family | service`. Frontmatter shape diverges per kind — see [Dependency pages](#dependency-pages) above.

### Severity (work)

Values: `low | medium | high | critical`.

| Bucket | Kinds | Lint |
|---|---|---|
| Common | `bug`, `security`, `perf` | severity expected, not enforced |
| Possible | `tech-debt`, `test-gap` | severity allowed when known |
| Disallowed | `feature`, `initiative`, `spike` | `severity-on-non-bug` (info) |

### Effort (work)

| Value | Anchor |
|---|---|
| `trivial` | minutes — one-line change, no test, no review needed |
| `small` | hours — single file, tests, single PR |
| `medium` | days — multiple files, possibly cross-package, single PR |
| `large` | weeks — multiple PRs, possibly an initiative |

Anchors are advisory. Missing field = unknown; no `unknown` value.

### Blast radius (work)

`file | package | domain | system`. **Practical impact, not source-code locality** — a one-line change to a shared library used by every domain is `system` even though the source is in one package.

### Per-kind field applicability (work)

| Field | Required for | Allowed for | Disallowed for |
|---|---|---|---|
| `severity` | none | `bug`, `security`, `perf`, `tech-debt`, `test-gap` | `feature`, `initiative`, `spike` |
| `target` | none | all kinds — only meaningful for `feature`, `initiative` | — |
| `owner` | none | all kinds — populated when `in-progress` | — |
| `effort` | none | all kinds | — |
| `blast_radius` | none | all kinds | — |

State-conditional fields (`resolved_in`, `mitigation`, `superseded_by`, `rationale`) are populated only in their corresponding state. Lint enforces.

### Status lifecycle (work)

Seven states. Replaces the two pre-existing enums (`open|investigating|mitigated|resolved|wontfix` and `proposed|planned|in-progress|done|cancelled`).

| State | Meaning | Required fields |
|---|---|---|
| `open` | filed; no committed plan | — |
| `accepted` | plan committed; `## Plan` table populated; ready to start | `## Plan` non-empty |
| `in-progress` | someone is implementing | `pr` or `branch` reference |
| `mitigated` | symptom hidden, root cause persists (mostly bug/security/perf) | `mitigation` |
| `resolved` | done | `resolved_in` |
| `wontfix` | closed without action | `rationale` |
| `superseded` | replaced by another work item | `superseded_by` |

Transitions are mostly forward; `accepted → open` (back) is allowed when a plan is invalidated by new evidence.

## Body-table conventions

Three categories use markdown tables in the body for structured rows. Header rows are exact; lint's table parser is strict.

### `## Plan` (work)

```markdown
## Plan

| Action | Done when | Rationale |
|---|---|---|
| Stage-prefix the database name in CDK | `location-service.ts` has no literal `dev-pat-location` | Matches `STAGE` already in the same block |
```

- Header row exact: `| Action | Done when | Rationale |`.
- One row per step. Order is significant.
- `Done when` is required (lint `warn`) for `kind: feature` and `kind: initiative`; optional otherwise.
- Pipes inside cell content escape as `\|`.
- File paths and `path:line` references in the `Action` cell are checked for existence by lint; line numbers are advisory.

## Auto-rendered sections

Sections regenerated mechanically on `graph-wiki:scan`. Marker-bounded so manual content elsewhere on the page survives untouched.

### `dependencies/index.md`

Regenerated by `scan_monorepo.py`. Marker contract:

```markdown
<!-- auto:dependencies-index generated:<ISO> -->
(table rendered by scan)
<!-- /auto:dependencies-index -->
```

Walks parsed manifests and merges hand-maintained service rows from `<workspace>/wiki/dependencies/services.yaml`. Manual notes can sit outside the marked region.

## Linking

Use Obsidian wikilinks. Three forms:

```
[[packages/common-aws-node-ts]]                             # folder shorthand — resolves to packages/common-aws-node-ts/common-aws-node-ts.md
[[packages/common-aws-node-ts|the AWS helpers package]]     # custom display
[[common-aws-node-ts]]                                      # stem — resolves if unique
```

For apps, packages, and domains, prefer the folder-shorthand form `[[<container>/<name>]]`. The linter aliases that to the file inside the folder, so you almost never need to write the doubled path. Stem links also work and are preferred when the name is unambiguous. Use full paths only for non-folder pages (concepts, sources, ADRs, etc.) or when disambiguating between a cross-domain package and a domain-scoped one with the same name (e.g. `[[domains/auth/packages/jwt-helpers]]`).

Code references — when citing actual code — use a plain code reference (Obsidian won't wikilink them but it's searchable):

```
See `packages/common-aws-node-ts/src/handlers/baseApiHandler.ts:42`
```

## Cross-reference rules

- **Every package mentioned on a domain or architecture page must be a wikilink** to `packages/<name>`.
- **Every domain mentioned on a package page** (the domain it belongs to or interacts with) must be a wikilink.
- **Every ADR referenced in package/domain/architecture must be a wikilink** to `adrs/<id>-<slug>`.
- **Every claim on a package/domain page cites** either a source page (`[[sources/xxx]]`) or a code path (backticked, with file:line).
- **Contradictions get flagged inline** with a `> ⚠️ Contradiction:` callout naming the conflicting sources or code paths.
- **Architecture pages link back to every package, domain, and ADR they draw on.**

## Index discipline

`<workspace>/wiki/index.md` is regenerated, not hand-edited. Either:

- Run `uv run --project "$DEEP_AGENTS_ROOT" python ${CLAUDE_PLUGIN_ROOT}/skills/graph-wiki/scripts/update_index.py` after every scan/ingest, OR
- Have the LLM rewrite the relevant section inline for small edits.

The index groups pages by category, alphabetized by title. Each entry is one line with a wikilink, summary, and optional metadata.

## Log discipline

`<workspace>/wiki/log.md` is append-only. Every entry starts with a standardized header so `grep "^## \[" log.md | tail -5` returns the last 5 entries.

```
## [2026-04-20] scan | detected 3 new packages
Added packages/timeline-data-node-ts, packages/timeline-domain-ts,
packages/timeline-native-ts. No renames or deletions.

## [2026-04-20] ingest | Auth Migration Spec
Added sources/2026-04-auth-migration-spec.md. Updated concepts/global-context,
domains/auth, packages/shared-aws-node-ts, packages/shared-native-ts,
architecture/request-flow, adrs/0014-jwt-sessions (new). Flagged contradiction
with concepts/global-context on session shape.
```

Valid ops: `scan`, `ingest`, `query`, `lint`, `create`, `update`, `delete`, `note`.
