---
title: <package-name>
category: package
summary: <one-line summary — what this package does>
status: active                    # active | planned — `planned` exempts the page from code-drift orphan checks
package_path: <path-relative-to-repo-root>
package_type: library            # library | service | tool
domain:                           # owning domain slug, or empty for top-level/shared packages
language: typescript              # typescript | python | rust | go | …
depends_on: []
tags: []
sources: 0
updated: <YYYY-MM-DD>
last_sync_commit:                 # full SHA of the repo commit this page reflects, set by /lattice-wiki:scan
last_sync_at:                     # YYYY-MM-DD when sync state was recorded
---

# <package-name>

## Purpose
One paragraph: what this package does, who uses it, why it exists.

## Public API
Main exports and when to use them. Link code with backticked paths (`path:line`).

- `exportName(args)` — `<relative/path/to/source>:<line>` — short description

## File map - <package-name>
One-paragraph description of what the package root contains. Top-level files are listed below as bullets with one-line descriptions; each first-level subdirectory becomes a `### <package-name>/<sub>/` section, and so on down to the depth cutoff (default 4 directory levels — `######` headings). Folders deeper than the cutoff are listed inline as bullets in their parent section. The scanner pre-populates files and folder bullets from `git ls-files`; per-entry descriptions (one line, present tense, what the entry *contains* — not how it's used) are filled in later by the agent.

- `<file>` — TODO

### <package-name>/<sub>/
One-paragraph description of what this subdirectory contains.

- `<file>` — TODO
- `<deeper-dir>/` — TODO (folder bullet for content past the depth cutoff, or anything you don't want a dedicated section for)

## Key patterns
- Pattern 1
- Pattern 2

## Used by
- [[packages/<other-package>]]

## Belongs to domain
- [[domains/<domain>]]

## Related concepts
- [[concepts/<concept>]]

## Decisions
- [[adrs/<id>-<slug>]]

## Dependencies (external)
- [[dependencies/<lib>]]

## Appears in sources
- [[sources/<source>]]

## Open questions
- …
