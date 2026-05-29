---
status: complete
phase: 57-index-generation-polish
source: [57-01-SUMMARY.md]
started: 2026-05-29T01:06:48Z
updated: 2026-05-29T01:45:00Z
---

## Current Test

[testing complete]

## Tests

### 1. Apps grouped separately, before Packages
expected: `## By Kind` has a `### Apps` group rendered before `### Packages`; apps (graph-io, graph-wiki-agent) appear under Apps
result: pass

### 2. Piped entity wikilinks everywhere
expected: every entity link is the piped form `[[wiki/entities/<stem>|<display name>]]` — readers see the clean name, not the raw stem
result: pass

### 3. Inline summaries on entity bullets
expected: each entity bullet shows `— <summary>` pulled from the entity page's own frontmatter (e.g. graph-io shows its real one-liner; deps still on placeholder show their `> TODO:` text); bullets with empty summaries show no trailing dash
result: pass
note: "Behavior matches (inline summary rendered from entity-page frontmatter). Separate non-blocking issue: the `> TODO: <...>` placeholder format breaks Obsidian rendering (blockquote + unclosed HTML tag). Tracked as todo 2026-05-29-fix-entity-summary-placeholder-breaks-obsidian-rendering (entity_writer.py:587, Phase 56 origin)."

### 4. Test suites nest under packages, no flat group
expected: there is NO standalone `### Test Suites` group; instead each package/app carries a nested `Test Suites` sub-list under it
result: pass
note: "IDX-04 structure correct (nested, no flat group). Separate non-blocking issue: all 9 test suites nest under every package (name-keyed resolution; all suites named `tests`). Tracked as todo 2026-05-29-test-suites-fan-out-under-every-package-in-index (index_generator.py:282)."

### 5. Dependencies vs Internal dependencies split
expected: each package shows two distinct nested sub-lists — `Dependencies` (external libs) and `Internal dependencies` (workspace package→package), never merged into one list
result: pass

## Summary

total: 5
passed: 5
issues: 0
pending: 0
skipped: 0
blocked: 0

## Gaps

[none yet]
