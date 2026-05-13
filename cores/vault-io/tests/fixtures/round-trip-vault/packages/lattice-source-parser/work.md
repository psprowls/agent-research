---
title: lattice-source-parser — Work
category: package
summary: Open questions and known failure modes for lattice-source-parser
updated: 2026-05-09
tokens: 351
---

# lattice-source-parser — Work

## Bugs

(none known)

## Tech debt

- `tests/update_fixtures.py` — parked as "deferred" for v1; pull forward if first-cut fixture writing demands it.
- Resolve the unittest-vs-pytest contradiction: the repo-level `CLAUDE.md` declares the `packages/` convention as "`pytest` for tests," while the original design spec deliberately used stdlib `unittest`. As the first inhabitant of `packages/`, this package sets a precedent. Decision belongs to the user — flagging only.

## Features

- Additional languages beyond Python/JS/TS — C# at v1.1; cadence for further languages (Rust, Go, Java, Kotlin, Swift) TBD per real-consumer demand.
- Chunking / token-counting projection — deferred until a real chunking consumer appears (RAG indexer, eval harness).
- Cross-file resolution as a built-in package feature — currently a plugin-side post-pass; may be pulled into the package if multiple consumers need it.
- PyPI publishing — deferred until the API stabilizes post-v1.

## Open questions

- What is the right cadence for adding new language parsers beyond v1.1 C#? Demand-driven vs. scheduled?
- Should `tests/update_fixtures.py` ship in v1, or remain a dev-only tool outside the distributed package?
- Unittest vs. pytest: which test runner should `packages/` standardize on? (See tech debt above.)
