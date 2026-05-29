---
status: complete
phase: 55-dependency-classification-fix
source: [55-01-SUMMARY.md, 55-02-SUMMARY.md]
started: 2026-05-29T00:45:00Z
updated: 2026-05-29T00:50:00Z
---

## Current Test

[testing complete]

## Tests

### 1. CLASS-01 — no dependency node for workspace packages
expected: After `cg update`, no `dependency` node exists for any workspace package/app name; external deps still resolve.
result: pass
note: Live on real repo graph — `describe-dependency wiki-io|graph-io|subagent-runtime` → "dependency not found"; `describe-dependency boto3` resolves.

### 2. CLASS-02 — depends_on_package edges exist
expected: Internal package→package usage emits a `depends_on_package` edge between the two package/app nodes.
result: pass
note: `cg status` edge_counts shows `depends_on_package: 12` on the live repo graph (distinct from Domain→Domain `depends_on`).

### 3. SC#3 — describe-package surfaces internal deps both directions
expected: `cg describe-package <name>` shows internal dependencies (outgoing) and internal dependents (incoming).
result: pass
note: wiki-io → deps=[workspace-io], dependents=[graph-wiki-agent]; model-adapter → dependents=[eval-harness, graph-wiki-agent, subagent-runtime]. Rendered in JSON + human format.

## Summary

total: 3
passed: 3
issues: 0
pending: 0
skipped: 0

## Gaps

[none]

## Notes

Verified against a freshly-built live graph (`cg update` on this workspace) — not just unit tests. This graph also seeds Phase 57's previously-skipped `test_snapshot_against_agent_research`. Targeted suites also green: test_packages.py (40), test_queries.py + test_cli_describe.py (103).
