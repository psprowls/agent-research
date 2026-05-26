# Phase 36: `cg find` Parser Ergonomics - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md — this log preserves the alternatives considered.

**Date:** 2026-05-26
**Phase:** 36-cg-find-parser-ergonomics
**Areas discussed:** At-least-one-flag rule, Parse error UX, `--in-package` semantics, Migration cut-over

---

## At-least-one-flag rule

### Q1: Bare `cg find` (no flags) — what happens?

| Option | Description | Selected |
|--------|-------------|----------|
| Error: require ≥1 filter | Print error 'cg find requires at least one of --name, --kind, --in-package', exit 2. Preserves current `queries.find()` invariant. | ✓ |
| List all (no filter) | Return every node, capped at e.g. 200. Useful for exploration; requires new query branch + cap. | |
| Print help and exit 0 | Friendly but unusual (most CLIs exit non-zero on missing args). | |

**User's choice:** Error: require ≥1 filter (Recommended)
**Notes:** Matches existing query-layer invariant; cheapest implementation.

### Q2: Multi-flag combination semantics

| Option | Description | Selected |
|--------|-------------|----------|
| AND (intersect) | Returns only nodes matching ALL supplied filters. Matches current `name AND kind` behavior. | ✓ |
| OR (union) | Returns nodes matching ANY filter. Doubles row-count risk; conflicts with current behavior. | |
| Mixed (--in-package as scope) | `--in-package` always intersects; `--name`/`--kind` AND together. Same outcome as AND for most cases. | |

**User's choice:** AND (intersect) (Recommended)
**Notes:** Predictable for tool use (Phase 37 librarian) — narrowing semantics.

### Q3: Where `--kind` value validation lives

| Option | Description | Selected |
|--------|-------------|----------|
| argparse `choices=_VALID_KINDS` | Argparse rejects invalid kinds at parse time. Exit 2. `queries.find()` ValueError stays as defense in depth. | ✓ |
| Query layer only (status quo) | Keep validation in `queries.find()`; CLI must catch ValueError. More duplication later. | |
| Both, with argparse owning message | argparse choices + queries.find() ValueError both active. Bullet-proof but redundant. | |

**User's choice:** argparse `choices=_VALID_KINDS` (Recommended)
**Notes:** Honors SC#2; cleaner error message.

---

## Parse error UX

### Q1: Old positional form (`cg find foo.py`) error

| Option | Description | Selected |
|--------|-------------|----------|
| Custom helpful message | Detect positional, print 'positional form removed; use --name. Example: cg find --name foo.py'. Exit 2. | |
| Argparse default error | Let argparse say 'unrecognized arguments: foo.py', exit 2. Cheap; meets SC#3. | ✓ |
| Custom + suggest --kind | Same as custom, plus if positional matches a valid kind, suggest `--kind`. Speculative. | |

**User's choice:** Argparse default error
**Notes:** Sufficient by SC#3's bar; minimal implementation cost. Can revisit if friction.

### Q2: Exit code for missing-filter error

| Option | Description | Selected |
|--------|-------------|----------|
| Exit 2 (parse error class) | Same as argparse missing-required-args. Implementation: `parser.error(…)`. | ✓ |
| Exit 1 (logic / not-found class) | Mixes signal with not-found case; scripts can't distinguish. | |
| New dedicated exit code (e.g. 5) | Most precise but adds new code callers must learn. | |

**User's choice:** Exit 2 (parse error class) (Recommended)
**Notes:** `parser.error()` routes to 2 automatically — zero new code.

### Q3: Help text richness for `cg find --help`

| Option | Description | Selected |
|--------|-------------|----------|
| Per-flag help strings, no epilog | Each flag gets a one-line `help=`. Matches rest of `cg`'s subcommand style. | ✓ |
| Add epilog with 2-3 examples | Epilog with example invocations. More discoverable, breaks `cg` consistency. | |
| Minimal (no help text) | Skip help= entirely. Discouraged. | |

**User's choice:** Per-flag help strings, no epilog (Recommended)
**Notes:** Consistency over discoverability.

---

## `--in-package` semantics

### Q1: What does `--in-package` match against?

| Option | Description | Selected |
|--------|-------------|----------|
| Short package name | `--in-package graph-io` matches packages named `graph-io`. Most ergonomic. | ✓ |
| Full package URI | `--in-package pkg:org/repo/graph-io`. Unambiguous for tools but verbose. | |
| Either — prefix URI, fall back to name | Multi-mode; risk of ambiguous matches. | |
| Filesystem path segment | `--in-package packages/graph-io`. Couples to filesystem layout. | |

**User's choice:** Short package name (Recommended)
**Notes:** Right primitive for CLI surface; URI stays for tool layer.

### Q2: Unknown-package behavior

| Option | Description | Selected |
|--------|-------------|----------|
| Exit 1 with 'no matches' | Treat as zero-result filter. Simplest mental model. | ✓ |
| Exit 1 with explicit warning | Print stderr warning before empty results. Friendlier for typos but special-case branch. | |
| Exit 2 (invalid argument) | Validate package existence at parse-adjacent layer. Strictest. | |

**User's choice:** Exit 1 with 'no matches' (Recommended)
**Notes:** `--in-package` is a filter, not a lookup.

### Q3: Match style for package name

| Option | Description | Selected |
|--------|-------------|----------|
| Exact match, case-sensitive | Aligns with `--name` semantics; predictable. | |
| Exact match, case-insensitive | `Graph-IO` matches `graph-io`. Friendlier hand-typing. | ✓ |
| Substring / prefix match | Powerful but unpredictable; conflicts with Phase 37 determinism needs. | |

**User's choice:** Exact match, case-insensitive
**Notes:** Costs a `LOWER()` or pre-normalize; preserves determinism for Phase 37.

### Q4: Row cap for unbounded queries

| Option | Description | Selected |
|--------|-------------|----------|
| Hard cap at 50 rows + truncation notice | Matches Phase 37 LIBTOOLS-02. Single source of truth. | ✓ |
| Higher cap (200) at CLI, 50 at tool layer | Different defaults per surface. | |
| No cap | Trust user to pipe to `head`. Risks dumping thousands of rows. | |

**User's choice:** Hard cap at 50 rows + truncation notice (Recommended)
**Notes:** Sets the convention that flows into Phase 37 — symmetric semantics.

---

## Migration cut-over

### Q1: Transition strategy

| Option | Description | Selected |
|--------|-------------|----------|
| Hard cut, single commit | Parser + all test call sites updated atomically. Aligns with Pitfall 5. | ✓ |
| Soft deprecation for one milestone | Accept positional with stderr warning. But SC#3 says "parse error" — warning isn't a parse error. | |
| Two-commit cut | Parser commit, then tests commit. Each commit passes CI; old form silently works in commit 1. | |

**User's choice:** Hard cut, single commit (Recommended)
**Notes:** Aligns with Pitfall 5; mirrors phase goal language exactly.

### Q2: Regression test for old positional form

| Option | Description | Selected |
|--------|-------------|----------|
| Add anti-regression test | Test in `test_cli_anti_regression.py` asserts `cg find foo.py` exits non-zero. Cheap guard. | ✓ |
| Skip — trust type-check / lint | If positional comes back, all named-flag tests still pass. | |
| Add to `test_cli_exit_codes.py` instead | Same test, different file. Arguably better home. | |

**User's choice:** Add anti-regression test (Recommended)
**Notes:** Without a guard, a future refactor could quietly restore positional form and existing tests would still pass.

---

## Claude's Discretion

- Exact SQL form for the `--in-package` filter (planner: read schema + queries.py)
- Whether to expose `_VALID_KINDS` to argparse via direct import or a small accessor
- Exact wording of the `parser.error()` message for D-01 (just name all three flags)
- Whether the row cap (D-09) lives in `q_find.py`, `queries.find()`, or `_format.render()`

## Deferred Ideas

- Custom helpful message for old positional form — revisit if post-merge user friction.
- Smart kind-detection for old positional — speculative; revisit only if argparse default proves insufficient.
- `--in-package` substring / prefix matching — out of scope for v1.7; would warrant a separate flag/command.
- Per-surface row cap (CLI vs tool layer) — rejected for Phase 36/37 consistency.
- Soft deprecation of positional form — rejected; SC#3 mandates a parse error.
