---
status: complete
phase: 58-entity-page-index-uat-follow-ups
source: [58-01-SUMMARY.md, 58-02-SUMMARY.md, 58-03-SUMMARY.md, 58-VERIFICATION.md]
started: 2026-05-29T00:00:00Z
updated: 2026-05-29T00:00:00Z
---

## Current Test

[testing complete]

## Tests

### 1. Entity page `## Related` shows a clean marker (no `<...>`)
expected: In a generated entity page, the `## Related` section reads "No related concept, ADR, or architecture pages yet." as plain prose — no `<...>` placeholder links, no leading `>`.
result: pass

### 2. Empty-summary placeholder renders cleanly in Obsidian
expected: For an entity with no description, the `summary:` placeholder reads "TODO add a one-line summary for {name}" (no leading `>`, no `<...>`, no `:`). Opened in Obsidian, the summary bullet and any list items after it render as ordinary prose — NOT a blockquote, no broken angle-bracket fragment swallowing following lines.
result: pass

### 3. Index `## By Kind` nests only each package's own test suites
expected: In the generated index `## By Kind` section, each package/app nests only the test suite(s) that actually test it — not the same nine `tests`-named suites repeated under every package. Suite entries appear package-qualified (e.g. `wiki-io-unit-tests`, `graph-io-integration-tests`).
result: pass

## Summary

total: 3
passed: 3
issues: 0
pending: 0
skipped: 0

## Gaps

[none yet]
