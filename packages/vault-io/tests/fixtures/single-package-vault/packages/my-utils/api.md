---
title: my-utils — API
category: package
summary: Public functions exported by my-utils.
updated: 2026-05-14
tokens: 198
---

# my-utils — API

## Functional helpers

`src/my_utils/functional.py`

- `pipe(*fns)` — compose functions left-to-right; `pipe(f, g)(x)` == `g(f(x))`
- `compose(*fns)` — compose functions right-to-left; `compose(f, g)(x)` == `f(g(x))`
- `partial_apply(fn, **kwargs)` — return a new callable with `kwargs` pre-bound

## Data validation

`src/my_utils/validation.py`

- `validate_schema(data, schema) -> list[str]` — return a list of field-level errors; empty list means valid
- `coerce_types(data, schema) -> dict` — cast fields to declared types in-place; raises `TypeError` on uncoerceable values

Schema format: `{field_name: type_or_validator}` where validator is `callable(value) -> bool`.

## Text processing

`src/my_utils/text.py`

- `slugify(text) -> str` — lowercase, replace non-alphanumeric with `-`, strip leading/trailing `-`
- `truncate(text, max_chars, suffix="…") -> str` — truncate at word boundary; append suffix
- `word_count(text) -> int` — split on whitespace, count non-empty tokens
