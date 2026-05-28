---
title: <Test Suite Name>
uri: <test-suite-uri>
kind: test_suite
graph_name: <graph-name>
last_scan_at: <YYYY-MM-DD>
tested_packages: []
suite_kind: ""
file_count: 0
updated: <YYYY-MM-DD>
---

# {{test_suite_name}}

## Narrative
_(scanner will populate on next scan)_

## Coverage notes
- What this suite exercises, what it deliberately excludes.

## Gotchas
- Fixture quirks, slow paths, flaky-test history, or special invocation rules.

## Purpose
One paragraph: what this package's test suite covers, what frameworks it uses, and how to run it.

## How to run
- `<command>` — describe the primary test command
- `<command>` — describe any secondary commands (smoke, integration, e2e)

## File map - {{PACKAGE_SLUG}}
TODO — overview of this package's test tree.

### {{PACKAGE_SLUG}}/
TODO — describe what this directory contains.

| Path | Kind | Description |
|---|---|---|
| `<file>` | file | — TODO |

## Test conventions
- Naming, structure, mocks, fixtures — anything specific to how tests are organized here.

## Fixtures
- `<path>` — describe what fixture data this represents and how it's used.

## Coverage
- Target coverage threshold (if any), how it's measured, where the report lives.

## Open questions
- …
