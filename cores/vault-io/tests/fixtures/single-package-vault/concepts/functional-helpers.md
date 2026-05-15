---
title: Functional Helpers Pattern
category: concept
summary: The pipe/compose/partial_apply pattern for building data-transformation pipelines from small, composable functions.
tags: [python, functional, design-pattern]
updated: 2026-05-14
tokens: 178
---

# Functional Helpers Pattern

## Overview

`my-utils` provides three primitives for building pipelines of pure functions:

| Function | Direction | Example |
|---|---|---|
| `pipe(f, g, h)` | Left-to-right | `pipe(parse, validate, render)(raw)` |
| `compose(h, g, f)` | Right-to-left | `compose(render, validate, parse)(raw)` |
| `partial_apply(fn, **kw)` | N/A | `partial_apply(validate_schema, schema=MY_SCHEMA)` |

## Why this pattern

- **Testability** — each step is a pure function; mock any step individually
- **Readability** — the data-flow direction is explicit and linear
- **Reuse** — steps compose freely across different pipelines

## Where it appears

- [[wiki/packages/my-utils/api]] — `pipe`, `compose`, `partial_apply` function signatures
- [[wiki/packages/my-utils/my-utils]] — package overview and file map
