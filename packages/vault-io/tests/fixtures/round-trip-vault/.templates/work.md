---
title: <Work item title>
category: work
kind: bug                        # bug | tech-debt | test-gap | security | perf | feature | initiative | spike
summary: <one-line — symptom for bug-shaped, capability for feature-shaped>
status: open                     # open | accepted | in-progress | mitigated | resolved | wontfix | superseded
severity:                        # bug | security | perf — leave blank for feature/initiative/spike
effort:                          # trivial | small | medium | large
blast_radius:                    # file | package | domain | system
affects: []                      # paths or packages this work touches
target:                          # YYYY-QN | YYYY-MM — meaningful for feature/initiative
owner:                           # populate when in-progress
opened: <YYYY-MM-DD>
updated: <YYYY-MM-DD>
related_tickets: []
related_prs: []
resolved_in:                     # commit/PR/release ref — required when resolved
superseded_by:                   # required when superseded
mitigation:                      # required when mitigated
rationale:                       # required when wontfix
tags: []
---

# <Work item title>

## Summary
One paragraph: what this is. For bug-shaped items, the symptom and where it shows. For feature-shaped items, the capability being added.

## Options considered
Earlier-stage thinking. Multiple approaches weighed; tradeoffs surfaced. Drop or trim once the plan is committed.

- Option A — …
- Option B — …

## Plan

| Action | Done when | Rationale |
|---|---|---|
| | | |

> Header row exact: `\| Action \| Done when \| Rationale \|`. One row per step; order is significant. Escape pipes in cell content as `\\|`. `Done when` is required for `kind: feature` and `kind: initiative`; optional otherwise.

## Notes / log
- **<YYYY-MM-DD>** — note
