---
title: "ADR-0001: my-utils is stdlib-only (no third-party dependencies)"
category: adr
summary: Use only Python stdlib in my-utils to enable zero-install usage in any Python 3.11+ environment.
adr_id: "0001"
status: accepted
decision_date: 2026-05-14
deciders: [Pat]
supersedes:
superseded_by:
tags: [python, stdlib, dependencies]
updated: 2026-05-14
tokens: 198
---

# ADR-0001: my-utils is stdlib-only

**Status:** accepted (2026-05-14)

## Context

`my-utils` provides utility helpers used across multiple projects. Adding third-party
dependencies (e.g. `more-itertools`, `attrs`) would require consumers to manage virtual
environments, complicating use in scripts and CI pipelines.

## Decision

`my-utils` declares `dependencies = []` in `pyproject.toml`. All implementations use
only Python 3.11+ stdlib. If a feature genuinely requires a third-party library, it is
split into a separate optional package (`my-utils-extras`).

## Consequences

**Positive:**
- Zero install friction — `pip install my-utils` (or `uv add my-utils`) pulls nothing extra
- Works in any Python 3.11+ environment including restricted CI images
- Simpler dependency graph for consumers

**Negative:**
- Some algorithms require more code than if `more-itertools` were available
- Performance-critical paths cannot use Cython-backed libraries without the extras split

## Impact

- [[wiki/packages/my-utils/my-utils]] — declares `dependencies = []`
- [[wiki/packages/my-utils/api]] — all functions implemented in stdlib only
