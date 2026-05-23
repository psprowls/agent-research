---
title: <app-name>
category: app
summary: <one-line summary — what this app is and for whom>
status: active                    # active | planned — `planned` exempts the page from code-drift orphan checks
app_path: <path-relative-to-repo-root>
platform: web                    # web | ios | android | mobile | desktop | cli
framework:                        # nextjs | expo | vite | remix | sveltekit | tauri | electron | cli
language: typescript
entry_points: []
consumes_domains: []
depends_on: []
deployment:
tags: []
sources: 0
updated: <YYYY-MM-DD>
tokens: 0
last_sync_commit:                 # full SHA of the repo commit this page reflects, set by /graph-wiki:scan
last_sync_at:                     # YYYY-MM-DD when sync state was recorded
---

# <app-name>

## Purpose
One paragraph: what this app is, who uses it, on what platform.

## Platform & runtime
- **Platform:** …
- **Framework:** …
- **Runtime target:** …
- **Deployment:** …

## Entry points
- `<relative/path/to/entry>:<line>` — description

## Routes / screens
| Route | Purpose | Auth |
|---|---|---|
| | | |

## Provider chain
Describe the top-level provider nesting. Reference the file that defines it.

## File map - <app-name>
One-paragraph description of what the app root contains.

Each first-level subdirectory becomes a `### <app-name>/<sub>/` section with a markdown table. Tests, test config, and fixtures live on the companion [[wiki/{{CONTAINER_DIR}}/{{APP_SLUG}}/testing|testing]] sub-page — they are intentionally excluded from this section. Nested files flatten into their depth-1 parent's table; directories deeper than the depth cutoff (default 4) appear as `dir` rows in their parent's table. The scanner pre-populates these tables from `git ls-files`; per-row Description cells start as `— TODO` and are filled in later by the agent.

### <app-name>/
TODO — describe what this directory contains.

| Path | Kind | Description |
|---|---|---|
| `<file>` | file | — TODO |
| `<deeper-dir>/` | dir | — TODO |

### <app-name>/<sub>/
TODO — describe what this directory contains.

| Path | Kind | Description |
|---|---|---|
| `<file>` | file | — TODO |

## Domains consumed
- [[domains/<domain>]]

## Packages used
- [[packages/<pkg>]]

## Key dependencies
- [[dependencies/<lib>]]

## Build & deployment
- Build command
- Deployment process

## Decisions
- [[adrs/<id>-<slug>]]

## Work
- [[work/<YYYY-MM-DD>-<slug>]]

## Appears in sources
- [[sources/<source>]]

## Open questions
- …

## Sub-pages
- [[wiki/{{CONTAINER_DIR}}/{{APP_SLUG}}/testing|testing]] — test suite, fixtures, coverage
