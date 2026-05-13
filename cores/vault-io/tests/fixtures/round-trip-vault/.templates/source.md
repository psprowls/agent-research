---
title: "<Source Title>"
category: source
summary: <one-line summary>
source_path: raw/<path-to-source>           # raw/<...> for ingested clips, or a repo-relative path for in-repo docs (e.g. docs/architecture.md)
source_type: spec                # spec | article | pr | ticket | transcript | rfc | doc
source_date: <YYYY-MM or YYYY-MM-DD>
last_sync_commit:                # set only for in-repo docs (source_type: doc) — full SHA at last ingest, used by /lattice-wiki:lint to detect changes
last_sync_at:                    # YYYY-MM-DD when sync state was recorded
authors: []
ingested: <YYYY-MM-DD>
updated: <YYYY-MM-DD>
---

# <Source Title>

## TL;DR
Two sentences max. What the source proposes / argues / reports.

## Key claims
1. Claim with page/section pointer if applicable
2. ...

## Proposed changes (if applicable)
- `packages/<pkg>` — ...

## Evidence / rationale
- …

## Surprises / contradictions
- Where this source conflicts with [[concepts/<concept>]] or code at `<path>:<line>`.

## Touches
- [[packages/<pkg>]]
- [[domains/<domain>]]
- [[concepts/<concept>]]

## Decisions triggered
- [[adrs/<id>-<slug>]]

## Where it's cited in this wiki
- [[packages/<pkg>]]
- [[domains/<domain>]]
