---
title: my-utils
category: package
summary: Pure-Python utility library providing functional helpers, data validation, and text processing primitives.
status: active
package_path: .
package_type: library
domain:
language: Python
depends_on: []
tags: [python, utilities, stdlib]
sources: 0
updated: 2026-05-14
tokens: 312
---

# my-utils

## Purpose

`my-utils` is a pure-Python (stdlib-only) utility library providing three groups of helpers:

- **Functional helpers** — `pipe()`, `compose()`, `partial_apply()` for function composition
- **Data validation** — `validate_schema()`, `coerce_types()` for dict schema enforcement
- **Text processing** — `slugify()`, `truncate()`, `word_count()` for string manipulation

No third-party dependencies. Requires Python 3.11+.

## File map

- `pyproject.toml` — hatchling build config; `name = my-utils`, `requires-python = ">=3.11"`, `dependencies = []`
- `src/my_utils/__init__.py` — exports all public symbols
- `src/my_utils/functional.py` — pipe, compose, partial_apply
- `src/my_utils/validation.py` — validate_schema, coerce_types
- `src/my_utils/text.py` — slugify, truncate, word_count
- `tests/` — pytest suite; 100% stdlib

## Sub-pages

- [[wiki/packages/my-utils/api]] — public API reference
- [[wiki/concepts/functional-helpers]] — concept: the functional-helpers pattern used here
- [[wiki/adrs/0001-pure-python]] — ADR: why stdlib-only
