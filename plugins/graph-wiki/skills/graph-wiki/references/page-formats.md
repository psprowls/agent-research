# Page Formats

Every wiki page has the same skeleton: YAML frontmatter + a section structure that matches its category. Below are the canonical formats. Templates live in `assets/page-templates/`. The full enum and per-category frontmatter spec lives in `wiki-schema.md`.

## File map convention (apps and packages)

App and package pages have a `## File map - <name>` section composed of one H3 subsection per major folder, each containing a markdown table. Rules:

- The H2 heading carries the package or app name: `## File map - <name>`, followed by a one-line overview paragraph.
- Files at the workspace root live in a synthetic `### <name>/` H3 section directly under the H2 — uniform shape, no special-cased root.
- Each depth-1 subdirectory gets its own H3 section whose heading is the full path from the workspace root with a trailing slash (e.g. `### <name>/<sub>/`).
- Under each H3: a one-sentence paragraph describing the directory, then a markdown table with columns `Path | Kind | Description`. `Path` is relative to that section's root (e.g. `middleware/auth.ts` inside `### <name>/src/`). `Kind` is `file` or `dir`. `Description` starts as `— TODO` and is filled in by the agent later.
- Nested files (depth ≥ 2) flatten into rows inside their depth-1 parent's table. Directories deeper than the cutoff (default `max_depth=4`) are listed as `dir` rows in their depth-1 parent's table instead of getting their own section.
- The scanner pre-populates the tables via `git ls-files` (so `.gitignore` is respected) with `— TODO` Description placeholders. Per-row descriptions are filled in by the agent on a later pass.
- `/graph-wiki:lint`'s file-map drift check flags rows whose Path is no longer on disk; new files showing up on disk do not fail lint, since `dir`-row summarization is allowed.
- **Legacy heading+bullet pages on disk** (pre-2026-05) are parsed gracefully: directory entries from H3 headers are still extracted, but file-row entries are dropped. The next scan re-emits the block in the new table format when the page still shows the unfilled-template signature.
- **Prod vs testing split:** the overview page's File map shows only **prod source + prod config**. Test files (any component named `tests/`, `__tests__/`, `test/`, or `spec/`), test config (`pytest.ini`, `tox.ini`, `conftest.py`, `jest.config.*`, `vitest.config.*`, `playwright.config.*`, `cypress.config.*`, `mocha.config.*`/`.mocharc.*`, `karma.conf.*`, `ava.config.*`), and test fixtures (typically under `tests/fixtures/`) live on the companion `testing.md` sub-page. The classification is implemented by `_is_test_path()` in `packages/vault-io/src/vault_io/scan_monorepo.py` — that helper is the single source of truth.
- **Fixtures at non-test paths:** workspaces that put fixtures outside a `tests/`-prefixed path (e.g. a root-level `fixtures/` directory used at runtime too) are classified as prod by the scanner. Document them by hand in `testing.md`'s `## Fixtures` section if they are test-only.

## Testing sub-page (apps, packages, plugins)

Each app, package, and plugin overview has a companion `testing.md` sub-page that owns the test surface — analogous to how `api.md` owns the public interface. The page is created from the `testing.md` template by the scanner the first time a workspace is stubbed, and is populated by the scanner's `file_map_testing` block on subsequent scans.

### Frontmatter
- `title: <name> — tests`
- `category: <package|app|plugin>` (matches the parent overview's category — the testing page is a sub-page of the same workspace, not its own taxonomy bucket)
- `parent: <name>` — descriptive, points back to the overview slug
- `status`, `updated`, `sources`, `tokens` — same semantics as overview

### Sections
- `## Purpose` — one paragraph: what this suite covers, which frameworks, how to invoke
- `## How to run` — bullet list of commands (primary, secondary like smoke/e2e)
- `## File map - <name>` — same table format as the overview, but the rows are scoped to test files + test config + fixtures (see split rule above). The block uses the same `## File map - <name>` H2 heading text as the overview; the page identity comes from the file path, not the heading.
- `## Test conventions` — naming, structure, mocks, fixtures
- `## Fixtures` — bullet list of fixture paths and what each represents
- `## Coverage` — target threshold, measurement method, report location
- `## Open questions`

### Example worked output (testing.md for common-aws-node-ts)

```markdown
# common-aws-node-ts — tests

## Purpose
Integration tests for the handler factories, exercised against a local DynamoDB and SNS stack via testcontainers.

## How to run
- `pnpm -F common-aws-node-ts test` — primary jest run
- `pnpm -F common-aws-node-ts test:e2e` — e2e suite (requires Docker)

## File map - common-aws-node-ts

### common-aws-node-ts/
Root: test config.

| Path | Kind | Description |
|---|---|---|
| `jest.config.ts` | file | jest config (ts-jest preset, coverage thresholds) |

### common-aws-node-ts/tests/
Integration tests + fixtures.

| Path | Kind | Description |
|---|---|---|
| `handlers.test.ts` | file | integration tests for the handler factories |
| `fixtures/` | dir | golden request/response bodies + signed JWTs |

## Test conventions
- Each handler has a `<handler>.test.ts` next to the integration suite.
- Mocks live under `tests/mocks/` and follow the `mock<Service>.ts` naming pattern.

## Fixtures
- `tests/fixtures/` — golden request/response bodies; refresh via `pnpm refresh-fixtures` when contracts change.

## Coverage
- Target: 80% statements, 70% branches. Measured by `jest --coverage`. Report at `coverage/index.html`.

## Open questions
- Whether to roll the e2e suite into the default `test` script once CI Docker support lands.
```

## 1. App page

One per application workspace — web app, mobile app, CLI, desktop client. Apps consume domain code (via `packages/`); they are the top-level composition layer.

```markdown
---
title: web-next-ts
category: app
summary: Next.js 15 web application — dashboard and admin surfaces
status: active                                # active | planned — `planned` exempts the page from code-drift orphan checks
app_path: apps/web-next-ts
platform: web                                 # web | ios | android | mobile | desktop | cli
framework: nextjs                             # nextjs | expo | vite | remix | sveltekit | tauri | electron | cli
language: typescript
entry_points: [app/(dashboard)/page.tsx, app/api/auth/route.ts]
consumes_domains: [auth, timeline, healthkit]
depends_on: [@psprowls/shared-ui-react-ts, @psprowls/shared-domain-ts]
deployment: vercel
tags: [web, nextjs]
sources: 2
updated: 2026-04-20
last_sync_commit:                             # full SHA of the repo commit this page reflects, set by /graph-wiki:scan
last_sync_at:                                 # YYYY-MM-DD when sync state was recorded
---

# web-next-ts

## Purpose
One paragraph: what this app is, who uses it, on what platform.

## Platform & runtime
- **Platform:** Web (evergreen browsers)
- **Framework:** Next.js 15 (App Router, Server Components)
- **Node target:** 22.x
- **Deployment:** Vercel — see [[architecture/deployment]]

## Entry points
- `app/(dashboard)/page.tsx` — main dashboard
- `app/api/auth/[...nextauth]/route.ts` — NextAuth handler
- `middleware.ts` — auth gate

## Routes / screens
| Route | Purpose | Auth |
|---|---|---|
| `/` | landing | public |
| `/dashboard` | main UI | required |
| `/admin/*` | admin | role:admin |

## Provider chain
`SafeAreaProvider` → `SessionProvider` (NextAuth) → `QueryClientProvider` (TanStack) → `AppSettingsProvider`
Source: `app/providers.tsx:12`

## File map - web-next-ts
The Next.js app's root: build config, the auth middleware, and the top-level source directories.

### web-next-ts/
Root: workspace manifest, Next.js build config, and the auth middleware.

| Path | Kind | Description |
|---|---|---|
| `package.json` | file | workspace manifest |
| `next.config.mjs` | file | Next.js build config |
| `middleware.ts` | file | auth gate; redirects unauthenticated users |

### web-next-ts/app/
App Router routes, layouts, and the top-level provider chain.

| Path | Kind | Description |
|---|---|---|
| `providers.tsx` | file | top-level provider chain |
| `(dashboard)/` | dir | dashboard route group |
| `admin/` | dir | admin surfaces (role:admin gated) |
| `api/` | dir | API route handlers (NextAuth, etc.) |

### web-next-ts/components/
App-specific UI (forms, charts, layouts) not promoted to a shared package.

| Path | Kind | Description |
|---|---|---|
| (rows omitted in example — populated by scanner) | | |

### web-next-ts/lib/
Local adapters: env, feature flags, small helpers that don't warrant a shared package yet.

| Path | Kind | Description |
|---|---|---|
| (rows omitted in example — populated by scanner) | | |

## Domains consumed
- [[domains/auth]] — session, sign-in
- [[domains/timeline]] — feed page
- [[domains/healthkit]] — health dashboard

## Packages used
- [[packages/shared-ui-react-ts]] — components
- [[packages/shared-domain-ts]] — typed API client
- [[packages/timeline-domain-ts]]

## Key dependencies
- [[dependencies/react]] — 19.0
- [[dependencies/next]] — 15.x
- [[dependencies/tanstack-react-query]]
- [[dependencies/zustand]] — client state

## Build & deployment
- `pnpm build --filter=web-next-ts`
- Deployed on push to main via Vercel

## Decisions
- [[adrs/0010-zustand-for-client-state]]
- [[adrs/0011-react-19-on-web-only]]

## Issues
- [[work/2026-03-12-nextjs-barrel-client-directive]]

## Roadmap
- [[work/admin-read-only-mode]] — feature target 2026-Q2

## Appears in sources
- [[sources/2026-02-react-19-migration-pr]]
- [[sources/2026-03-admin-ui-spec]]

## Open questions
- …
```

`last_sync_commit` (40-char SHA) and `last_sync_at` (YYYY-MM-DD) record the repo commit this page was last verified against. `/graph-wiki:scan` writes both when run with a clean working tree on `main`. `/graph-wiki:lint` compares HEAD against `last_sync_commit` to flag packages whose source has changed since the last review.

## 2. Package page

One per workspace library/service. Most common page type after apps.

```markdown
---
title: common-aws-node-ts
category: package
summary: Lambda handler factories, middleware pipeline, and AWS SDK client wrappers
status: active                                # active | planned — `planned` exempts the page from code-drift orphan checks
package_path: packages/common-aws-node-ts
package_type: library
language: typescript
depends_on: [@psprowls/common-context-node-ts]
tags: [aws, lambda, middleware]
sources: 2
updated: 2026-04-20
last_sync_commit:                             # full SHA of the repo commit this page reflects, set by /graph-wiki:scan
last_sync_at:                                 # YYYY-MM-DD when sync state was recorded
manifests:                                    # optional — set by /graph-wiki:scan for `package-family` containers
  # Multi-variant packages (e.g. HubSpot UI extensions with both a private
  # and public app variant, or a sample with nested src/app/extensions/ and
  # src/app/app.functions/ manifests). Each entry records one detected
  # manifest file. Omitted entirely for ordinary single-manifest packages.
  # - path: references/.../charts-example/private/src/app/extensions/package.json
  #   name: charts
  #   language: javascript
  #   ecosystem: npm
---

# common-aws-node-ts

## Purpose
One paragraph: what this package does, who uses it, why it exists.

## Public API
Main exports and when to use them. Link code with backticked paths.

- `createBaseApiHandler(config)` — `src/handlers/baseApiHandler.ts:15` — public endpoints, no auth
- `createBaseAuthorizedApiHandler(config)` — `src/handlers/baseApiHandler.ts:47` — with Cognito JWT auth
- `withGlobalContext<P, B, R>(event, ctx, handler)` — wraps route handlers, parses body

## File map - common-aws-node-ts
The package root: workspace manifest, README, and the `src/` and `tests/` trees.

### common-aws-node-ts/
Root: workspace manifest and README.

| Path | Kind | Description |
|---|---|---|
| `package.json` | file | workspace manifest |
| `README.md` | file | package readme |

### common-aws-node-ts/src/
TypeScript source. `index.ts` re-exports the public handler factories; the rest is split into handlers, middlewares, and pre-configured clients.

| Path | Kind | Description |
|---|---|---|
| `index.ts` | file | re-exports public handler factories |
| `handlers/baseApiHandler.ts` | file | public + authorized handler factories |
| `handlers/withGlobalContext.ts` | file | body parsing + AsyncLocalStorage wrapper |
| `middleware/authProvider.ts` | file | Cognito JWT auth middleware |
| `middleware/eventBodyDeserializer.ts` | file | JSON body parser |
| `middleware/globalContextProvider.ts` | file | AsyncLocalStorage seeder |
| `middleware/httpRouteHandler.ts` | file | route dispatcher |
| `clients/` | dir | pre-configured AWS SDK clients (DynamoDB, S3, SNS) used across handlers |

### common-aws-node-ts/tests/
Integration tests for the handler factories.

| Path | Kind | Description |
|---|---|---|
| `handlers.test.ts` | file | integration tests for the handler factories |

## Key patterns
- Middleware pipeline order: `globalContextProvider` → `eventBodyDeserializer` → `authProvider` → `httpRouteHandler`
- Handlers receive `IGlobalContext` from `AsyncLocalStorage`

## Used by
- [[packages/location-aws-node-ts]]
- [[packages/healthkit-aws-node-ts]]
- [[packages/timeline-aws-node-ts]]
- (full list from `scan_monorepo.py` import graph)

## Belongs to domain
- [[domains/aws-infrastructure]]

## Related concepts
- [[concepts/global-context]]
- [[concepts/lambda-handler-pattern]]

## Decisions
- [[adrs/0008-middleware-pipeline]]
- [[adrs/0012-move-to-esm]]

## Appears in sources
- [[sources/2026-04-auth-migration-spec]] — mentions `authProvider` middleware

## Open questions
- Should we extract the middleware to a separate package?
```

`last_sync_commit` (40-char SHA) and `last_sync_at` (YYYY-MM-DD) record the repo commit this page was last verified against. `/graph-wiki:scan` writes both when run with a clean working tree on `main`. `/graph-wiki:lint` compares HEAD against `last_sync_commit` to flag packages whose source has changed since the last review.

## 3. Domain page

A feature area that spans multiple packages.

```markdown
---
title: Auth
category: domain
summary: Authentication across mobile, web, and Lambda — Cognito + JWT session management
packages: [shared-aws-node-ts, shared-native-ts, shared-domain-ts]
tags: [auth, cognito, jwt]
sources: 3
updated: 2026-04-20
---

# Auth

## Scope
One paragraph: what this domain covers, boundaries with adjacent domains.

## Packages in this domain
- [[packages/shared-aws-node-ts]] — Cognito integration, JWT validation middleware
- [[packages/shared-native-ts]] — `AuthProvider` React Native context
- [[packages/shared-domain-ts]] — shared API client with auth header injection

## Key flows
- **Login** — `shared-native-ts/src/auth/login.ts` → Cognito → JWT → stored in SecureStore
- **Request auth** — `shared-domain-ts/src/client.ts` → attaches Bearer token → Lambda middleware validates
- **Refresh** — (describe)

## Concepts
- [[concepts/cognito-jwt-validation]]
- [[concepts/global-context]] — how `session.user_id` propagates

## Decisions
- [[adrs/0003-cognito-over-auth0]]
- [[adrs/0014-jwt-sessions]] — current session approach

## Sources
- [[sources/2026-04-auth-migration-spec]]
- [[sources/2026-02-cognito-evaluation]]

## Contrasts / alternatives
- [[concepts/cognito-vs-auth0]]

## Open questions
- Biometric refresh flow is under-documented.
- Multi-tenant support: not yet scoped.
```

## 4. Concept page

A cross-cutting technical pattern, convention, or idea used across packages.

```markdown
---
title: GlobalContext
category: concept
summary: Request-scoped context via AsyncLocalStorage providing config, database, logger, session
tags: [context, middleware, patterns]
sources: 2
updated: 2026-04-20
---

# GlobalContext

## Definition
Precise, one-paragraph definition. The canonical form used across the codebase.

## Motivation
Why this pattern exists. What problem it solves vs. passing context explicitly.

## Shape
```typescript
interface IGlobalContext {
  config: IConfigurationManager;
  database: IDatabaseManager;
  logger: ILogger;
  session: SessionInfo;
}
```
From `packages/common-context-node-ts/src/globalContext.ts`.

## Used in
- [[packages/common-aws-node-ts]] — injects via middleware
- [[packages/common-context-node-ts]] — defines the interface
- All `*-data-node-ts` packages — scope queries by `session.user_id`

## Related patterns
- [[concepts/middleware-pipeline]]
- [[concepts/repository-pattern]]

## Sources
- [[sources/2025-12-context-refactor-spec]]

## Open questions / gotchas
- Default `session.user_id` is `ObjectId(0)` — tests must call `updateSession()` before DB operations.
- ⚠️ Contradiction: `[[packages/shared-aws-node-ts]]` assumes `session.session_id` always populated, but `[[sources/auth-migration-spec]]` says pre-login requests have null.
```

## 4a. Concept page — pattern variant

A pattern is a prescriptive concept ("when to apply this, what to watch out for") rather than a descriptive one ("what this is in our codebase"). Naming convention only — no new `category` and no new `kind:` discriminator on concepts. Mirrors how comparison pages work today (`<a>-vs-<b>.md`).

Filename: `concepts/<topic>-pattern.md`. The `-pattern` suffix is the discriminator.

```markdown
---
title: "Suspense-driven query loading"
category: concept
summary: Pattern for loading data with React Suspense boundaries instead of isLoading flags
tags: [pattern, react, suspense, data-fetching]
sources: 1
updated: 2026-05-04
---

# Suspense-driven query loading

## Definition
One-paragraph definition of the pattern, in its general form (not tied to this codebase).

## When to apply (Forces)
- Bulleted list of conditions/forces that make this pattern a good fit.
- Each bullet is a constraint or pressure the pattern resolves.

## Solution
The shape of the pattern. Code sketch is fine; keep it minimal and language-agnostic where possible.

## Tradeoffs
**Positive:** …
**Negative:** …

## Example sources
- [[sources/2026-05-tanstack-suspense-example]] — minimal Expo demo.
- [[sources/2026-04-react-19-suspense-blog]] — conceptual write-up.

## Where this could apply in the codebase
- [[packages/web-next-ts]] — current isLoading-flag pattern in dashboard queries.
- [[packages/app-expo-ts]] — same.

## Related patterns
- [[concepts/error-boundary-pattern]]
- [[concepts/global-context]]

## Open questions
- …
```

Notes:
- The `pattern` tag is recommended so the index can group these pages; not enforced.
- Body sections are recommended, not lint-enforced. Lint nudges (info-level) for naming/tag mismatch only.

## 5. Source summary page

One per ingested source (article, spec, PR, transcript, ticket). Summarized **once**; other pages cite it.

```markdown
---
title: "Auth Migration Spec"
category: source
summary: Move from opaque session tokens to JWTs; driven by compliance, affects 4 packages
source_path: raw/specs/auth-migration.md
source_type: spec
source_date: 2026-04-01
last_sync_commit:                # set only for in-repo docs (source_type: doc) — full SHA at last ingest, used by /graph-wiki:lint to detect changes
last_sync_at:                    # YYYY-MM-DD when sync state was recorded
authors: [@psprowls]
ingested: 2026-04-20
updated: 2026-04-20
---

# Auth Migration Spec

## TL;DR
Two sentences max. What the source proposes / argues / reports.

## Key claims
1. Session tokens stored in `sessions` collection must be retired by 2026-Q3 for compliance.
2. New approach: short-lived JWTs signed by Cognito, validated in `authProvider` middleware.
3. `session.user_id` contract preserved; `session.session_id` becomes JWT `sub`.

## Proposed changes
- `packages/shared-aws-node-ts` — new `jwtAuthProvider` middleware
- `packages/shared-native-ts` — refresh token handling
- `packages/shared-domain-ts` — header injection from Cognito SDK

## Evidence / rationale
- Legal flagged current storage pattern (file cited: `docs/compliance-2026Q1.pdf`)
- Prototype in `packages/shared-aws-node-ts/src/auth/__prototype__.ts`

## Surprises / contradictions
- Spec claims `session.session_id` unchanged, but see `[[concepts/global-context]]` — field shape differs.

## Touches
- [[packages/shared-aws-node-ts]]
- [[packages/shared-native-ts]]
- [[packages/shared-domain-ts]]
- [[domains/auth]]
- [[concepts/global-context]]

## Decisions triggered
- [[adrs/0014-jwt-sessions]] — accepted

## Where it's cited in this wiki
- [[concepts/global-context]]
- [[domains/auth]]
- [[adrs/0014-jwt-sessions]]
```

`last_sync_commit` (40-char SHA) and `last_sync_at` (YYYY-MM-DD) record the repo commit this page was last verified against. `/graph-wiki:ingest` writes both when re-ingesting an in-repo doc (`source_type: doc`) with a clean working tree on `main`. `/graph-wiki:lint` compares HEAD against `last_sync_commit` to flag source files that have changed since the last ingest.

## 6. Architecture page

High-level synthesis that draws on many packages, domains, and sources.

```markdown
---
title: Request Flow
category: architecture
summary: End-to-end path of an authenticated API request from client through Lambda to MongoDB
packages: [shared-domain-ts, shared-aws-node-ts, common-context-node-ts, *-data-node-ts]
tags: [architecture, request-flow]
sources: 4
updated: 2026-04-20
---

# Request Flow

## Thesis
Two-three sentences capturing the current understanding of how requests flow through the system. Revised as new sources / ADRs arrive.

## Layers

1. **Client** — React Native (`[[packages/app-expo-ts]]`) or Next.js (`[[packages/web-next-ts]]`) uses `[[packages/shared-domain-ts]]` client
2. **API Gateway / Lambda** — routes to `*-aws-node-ts` handlers; middleware pipeline establishes `[[concepts/global-context]]`
3. **Data layer** — handlers delegate to `*-data-node-ts` repositories scoped by `session.user_id`
4. **MongoDB** — per-domain database via `IDatabaseManager.getDatabase(name)`

## Diagrams
- See `raw/assets/request-flow.svg` (from `[[sources/2025-12-architecture-overview]]`)

## Key packages
- [[packages/shared-domain-ts]] — client
- [[packages/shared-aws-node-ts]] — auth
- [[packages/common-aws-node-ts]] — middleware base
- [[packages/common-context-node-ts]] — context
- [[packages/activities-data-node-ts]] — repo base classes

## Key concepts
- [[concepts/global-context]]
- [[concepts/middleware-pipeline]]
- [[concepts/repository-pattern]]

## Decisions shaping this
- [[adrs/0005-lambda-per-endpoint]]
- [[adrs/0008-middleware-pipeline]]
- [[adrs/0014-jwt-sessions]]

## How this synthesis has changed
- **2026-04-20** — added JWT flow from `[[sources/2026-04-auth-migration-spec]]`
- **2025-12-15** — initial write-up
```

## 7. ADR page

A dated, citable decision. Classic MADR-lite format.

```markdown
---
title: "ADR-0014: JWT Sessions"
category: adr
adr_id: 0014
status: accepted
decision_date: 2026-04-18
deciders: [@psprowls]
supersedes: 0007
superseded_by: null
tags: [auth, sessions]
updated: 2026-04-20
---

# ADR-0014: JWT Sessions

**Status:** accepted (2026-04-18)
**Supersedes:** [[adrs/0007-opaque-session-tokens]]

## Context
Compliance flagged the current session-token storage pattern. See [[sources/2026-04-auth-migration-spec]] for full context.

## Decision
Adopt short-lived JWTs signed by Cognito. Validation in middleware; refresh on the client.

## Consequences

**Positive:**
- Meets compliance requirements (no server-side session storage)
- Simpler horizontal scaling

**Negative:**
- Token revocation becomes harder (accepted trade-off)
- Client-side refresh logic must be correct

## Alternatives considered
- Rotate opaque tokens with short TTL (rejected: still server-side)
- Auth0 (rejected: see [[concepts/cognito-vs-auth0]])

## Impact
- [[packages/shared-aws-node-ts]] — middleware change
- [[packages/shared-native-ts]] — refresh logic
- [[packages/shared-domain-ts]] — header injection
- [[domains/auth]] — overall flow

## Follow-ups
- Roll out to staging 2026-05
- Deprecate opaque tokens 2026-Q3
```

## 8. Dependency page

The auto-generated `dependencies/index.md` covers every dep the monorepo touches. Detail pages are opt-in for the load-bearing / quirky / actively-migrated ones. Three shapes via `kind:` — `package`, `package-family`, `service`. Example below shows `kind: package`; see `wiki-schema.md` for the family and service variants.

```markdown
---
title: React
category: dependency
kind: package
package_name: react
ecosystem: npm
family: ""
versions_in_use: ["19.0.0", "18.3.1"]
used_by: [web-next-ts, app-expo-ts, shared-ui-react-ts, shared-ui-native-ts]
upstream_url: https://react.dev
load_bearing: true
quirks: []
tags: [frontend, ui]
updated: 2026-04-20
---

# React

## What it is
One paragraph: what this library does, why we use it, which surfaces.

## Versions in use
| Version | Used in | Notes |
|---|---|---|
| 19.0.0 | [[packages/web-next-ts]], [[packages/shared-ui-react-ts]] | Migrated 2026-Q1 |
| 18.3.1 | [[packages/app-expo-ts]], [[packages/shared-ui-native-ts]] | Pinned by RN 0.76 |

## Used by
- [[packages/web-next-ts]]
- [[packages/app-expo-ts]]
- [[packages/shared-ui-react-ts]]
- [[packages/shared-ui-native-ts]]

## Key patterns in this repo
- Functional components only; no class components.
- Suspense + Server Components in `[[packages/web-next-ts]]` (Next 15 App Router).
- `use client` directive boundaries — see [[concepts/nextjs-client-boundary]].

## Gotchas / workarounds
- ⚠️ React 19 `useEffect` runs twice in dev (Strict Mode) — see [[work/2026-02-08-double-mount-in-dev]].
- Expo pins React 18; can't bump until RN catches up.

## Upgrade history
- **2026-02** — bumped web surfaces to 19.0. See [[sources/2026-02-react-19-migration-pr]].
- **2025-09** — initial adoption of concurrent features.

## Decisions
- [[adrs/0011-react-19-on-web-only]]

## Related
- [[dependencies/react-native]]
- [[concepts/server-state-vs-client-state]]
- [[work/rn-0-77-upgrade]]
```

## 9. Work page

Unified namespace for everything "to do, doing, or done" — bugs, tech debt, test gaps, security/perf items, features, initiatives, spikes. `kind:` discriminates; a single 7-state lifecycle covers all. The committed plan lives in a `## Plan` markdown table. Slugs are `<YYYY-MM-DD>-<short-slug>.md` for date-of-filing-meaningful items and `<short-slug>.md` for evergreen feature/initiative items.

`graph-wiki` owns the schema, template, folder, lifecycle lint, and `<workspace>/work/.work-index.json` sidecar.

> **Note:** The work-layer subsystem (archive, regen-index, status commands) is not ported in graph-wiki v1.2. This note applies when/if work-layer support is added in a future version.

Bug-shaped example (`kind: bug`):

```markdown
---
title: MONGO_DATABASE hardcoded to dev-pat-location in CDK
category: work
kind: bug
summary: cdk/location-service.ts:50 sets MONGO_DATABASE to a literal "dev-pat-location" — any prod deploy lands on the dev database.
status: open
severity: medium
effort: small
blast_radius: package
affects:
  - packages/location-aws-node-ts
opened: 2026-04-21
updated: 2026-05-03
tags: [location, infrastructure, configuration, mongodb]
---

# MONGO_DATABASE hardcoded to dev-pat-location in CDK

## Summary
The CDK deploy script for `location-aws-node-ts` sets `MONGO_DATABASE` to the literal string `dev-pat-location`. Any prod deploy lands on the dev database.

## Options considered
- Stage-prefix the database name from the existing `STAGE` variable in the same block.
- Move the DB name into env-vars-per-stage in `cdk.json` (overkill; one variable).

## Plan

| Action | Done when | Rationale |
|---|---|---|
| Stage-prefix the database name in CDK | `location-service.ts` has no literal `dev-pat-location` | Matches `STAGE` already in the same block |
| Drop the legacy adapter fallback | `legacyContextAdapter.ts` no longer falls back | Dead code once env var always set |

## Notes / log
- **2026-04-21** — filed; reproduced on dev deploy.
```

Feature-shaped example (`kind: feature`):

```markdown
---
title: Cloud LLM provider via AWS Bedrock
category: work
kind: feature
summary: Add Bedrock as a third provider behind getChatModel() so the agent can run against open-weight cloud-hosted models.
status: accepted
effort: large
blast_radius: system
target: 2026-Q2
owner: pat
affects:
  - src/llm/provider.ts
  - src/llm/bedrock.ts
  - src/config.ts
opened: 2026-05-02
updated: 2026-05-03
tags: [roadmap, llm, cloud, aws, bedrock]
---

# Cloud LLM provider via AWS Bedrock

## Summary
Add Bedrock to the provider seam so the agent can run against open-weight cloud-hosted models alongside the existing local and OpenAI providers.

## Plan

| Action | Done when | Rationale |
|---|---|---|
| Add `bedrock.ts` adapter to the provider seam | `getChatModel("bedrock-…")` returns a working client | Plug-in shape mirrors existing providers |
| Wire stage config | `BEDROCK_REGION` and `BEDROCK_MODEL` honored | Matches existing `OPENAI_*` shape |
| End-to-end smoke test against a small Bedrock model | One round-trip query returns a non-error completion | Catches IAM/credentials misconfig early |

## Notes / log
- **2026-05-03** — accepted after spike on IAM permissions.
```

Severity is allowed for `bug | security | perf | tech-debt | test-gap` and disallowed for `feature | initiative | spike`. State-conditional fields (`resolved_in`, `mitigation`, `superseded_by`, `rationale`) are populated only in their corresponding state. See `wiki-schema.md` for the full taxonomy and lifecycle.
