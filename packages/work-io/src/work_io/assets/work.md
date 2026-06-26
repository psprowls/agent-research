---
title: <Work item title>
category: work
kind: bug                        # bug | tech-debt | test-gap | security | perf | feature | initiative | spike
summary: <one-line — symptom for bug-shaped, capability for feature-shaped>
status: open                     # open | accepted | in-progress | mitigated | resolved | wontfix | superseded
severity:                        # bug | security | perf — leave blank for feature/initiative/spike
effort:                          # xs | s | m | l | xl
blast_radius:                    # file | package | domain | system
affects: []                      # paths or packages this work touches
target:                          # YYYY-QN | YYYY-MM — meaningful for feature/initiative
owner:                           # populate when in-progress
opened: <YYYY-MM-DD>
updated: <YYYY-MM-DD>
tokens: 0
related_tickets: []
related_prs: []
resolved_in:                     # commit/PR/release ref — required when resolved
superseded_by:                   # required when superseded
mitigation:                      # required when mitigated
rationale:                       # required when wontfix
tags: []
phase:                          # design | plan | execute | finish | done
spec_doc: relative path from <workspace> to the spec doc written in design phase
plan_doc: relative path from <workspace> to the plan doc written in plan phase
---

# <Work item title>

## Summary
One paragraph: what this is. For bug-shaped items, the symptom and where it shows. For feature-shaped items, the capability being added.

## Notes / log
- **<YYYY-MM-DD>** — note
