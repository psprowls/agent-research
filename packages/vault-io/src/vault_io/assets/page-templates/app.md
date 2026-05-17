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
last_sync_commit:                 # full SHA of the repo commit this page reflects, set by /lattice-wiki:scan
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
One-paragraph description of what the app root contains. Top-level files are listed below as bullets with one-line descriptions; each first-level subdirectory becomes a `### <app-name>/<sub>/` section, and so on down to the depth cutoff (default 4 directory levels — `######` headings). Folders deeper than the cutoff are listed inline as bullets in their parent section. The scanner pre-populates files and folder bullets from `git ls-files`; per-entry descriptions (one line, present tense, what the entry *contains* — not how it's used) are filled in later by the agent.

- `<file>` — TODO

### <app-name>/<sub>/
One-paragraph description of what this subdirectory contains.

- `<file>` — TODO
- `<deeper-dir>/` — TODO (folder bullet for content past the depth cutoff, or anything you don't want a dedicated section for)

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
