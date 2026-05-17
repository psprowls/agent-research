---
title: "ADR-0005: SourceTree as the sole domain model for lattice-source-parser"
category: adr
summary: A single span-bearing intermediate (SourceNode + Reference + Span) is the only domain object the package exports; all consumer outputs are pure projections on top of it. No subclassing by language; symbol kind is a string tag.
adr_id: "0005"
status: accepted
decision_date: 2026-05-07
deciders: [Patrick Sprowls]
supersedes:
superseded_by:
tags: [adr, lattice-source-parser, source-tree, domain-model, projections]
updated: 2026-05-07
tokens: 560
---

# ADR-0005: SourceTree as the sole domain model for lattice-source-parser

**Status:** accepted (2026-05-07)

## Context

[[wiki/packages/lattice-source-parser/lattice-source-parser]] needs a domain shape that supports multiple consumer projections (graph records, chunks, embeddings) across multiple languages (Python, JavaScript, TypeScript at v1; more later). Two candidate shapes were considered: per-language subclass hierarchies (`PythonFunction`, `TypeScriptInterface`, etc.), or a single span-bearing tree with string-tagged kinds.

Per-language subclassing leaks each language's assumptions into the shared API and forces every consumer to handle N type variants. A single intermediate keeps the consumer surface flat.

## Decision

A single span-bearing intermediate (`SourceNode` + `Reference` + `Span`) is the **sole domain model** the package exports. All consumer outputs (graph records, chunks, embeddings, future projections) are **pure projections on top of it**. No subclassing by language. **Symbol kind is a string tag** (`"function"`, `"class"`, `"interface"`, etc.), not a class hierarchy. Per-language detail lives in `attrs` dicts on the node.

## Consequences

- Adding a language is an additive change — a new `parsers/<lang>.py` plus extension entries in the registry. No domain-model surgery.
- Adding a projection is an additive change — a new `projections/<name>.py`. Existing projections are unaffected.
- Consumers handle one shape regardless of language; downstream code (graph upsert, chunkers, RAG indexers) stays simple.
- Per-language nuance moves into `attrs` dicts; consumers that need that nuance must do dict access rather than typed attribute access. Acceptable tradeoff — typed access would have required the subclass hierarchy this ADR rejects.

## Related

- [[wiki/packages/lattice-source-parser/lattice-source-parser]]
- [[wiki/concepts/source-tree-model]]
- [[wiki/adrs/0006-source-parser-sibling-package]]
