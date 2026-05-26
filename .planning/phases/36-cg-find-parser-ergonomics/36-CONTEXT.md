# Phase 36: `cg find` Parser Ergonomics - Context

**Gathered:** 2026-05-26
**Status:** Ready for planning

<domain>
## Phase Boundary

Migrate `cg find` from positional-first form (`cg find <name> [--kind KIND]`) to named-flag form (`--name`, `--kind`, `--in-package`), add `--in-package` as a brand-new filter dimension, surface a clear parse error when the old positional form is used, and update all internal call sites in `packages/graph-io/tests/` in the same commit so nothing silently breaks.

Out of scope: any new librarian tool wiring (Phase 37); any other `cg` subcommand parser changes; query-layer refactors beyond what's needed to support `--in-package`; broader exit-code policy revisions.

</domain>

<decisions>
## Implementation Decisions

### Flag Combination & Required-Filter Rule
- **D-01: At least one filter is required.** `cg find` with no flags errors with "cg find requires at least one of --name, --kind, --in-package" via `parser.error()` (exit 2). Preserves the existing `queries.find()` invariant (rejects `name is None and kind is None`).
  - **Why:** Cheapest implementation, preserves current safety against runaway list-all queries on big graphs, and keeps a clean mental model — "you must filter."
- **D-02: Multiple flags combine via AND (intersect).** `--name foo --kind class --in-package graph-io` returns only nodes matching all three. Matches the existing 2-filter (`name` + `kind`) AND behavior in `queries.find()`.
  - **Why:** Predictable for tool use — the librarian (Phase 37) will compose filters expecting narrowing semantics, not widening.

### Validation Layer
- **D-03: `--kind` validation lives at argparse layer.** `add_argument("--kind", choices=sorted(_VALID_KINDS))` so argparse rejects invalid kinds at parse time with a clean message + list of valid kinds. Exit 2 (parse error). `queries.find()`'s existing `ValueError` for invalid kind stays as defense-in-depth (still reachable from non-CLI callers like the Phase 37 librarian tools), but should not be reachable from CLI under this design.
  - **Why:** Honors SC#2 ("never exit code 2 for arg-parse error" applies only when valid flags are supplied — invalid `--kind` IS a parse error). Cleaner error message via argparse; no duplicated string formatting.

### Parse Error UX for Old Positional Form
- **D-04: Argparse's default error is sufficient.** Old form `cg find foo.py` triggers argparse's `unrecognized arguments: foo.py` message and exits 2. No custom pre-parse hook, no helpful "use --name instead" message.
  - **Why:** Cheap; meets SC#3's bar ("clear human-readable parse error"). Sub-millisecond implementation cost. If usage friction shows up post-merge we can revisit.
  - **What it does NOT do:** Does not detect the positional value or suggest `--name foo.py` / `--kind <value>`. No smart suggestions.

### Help Text Style
- **D-05: Per-flag `help=` strings, no epilog.** Each of `--name`, `--kind`, `--in-package` gets a one-line `help=` describing what it filters and that filters combine via AND. No `epilog=` examples section.
  - **Why:** Matches the rest of `cg`'s subcommand help style — consistency over discoverability. The 3 flag names already describe the surface; humans who need examples can read the phase plan / SPEC.

### `--in-package` Semantics
- **D-06: Match against short package name.** `--in-package graph-io` matches all nodes whose container package's short name is `graph-io` (the last segment of `pkg:org/repo/graph-io`). Not the full URI; not a filesystem path segment.
  - **Why:** Most ergonomic for hand typing at the CLI; the URI is the right primitive at the tool/query layer (Phase 37) but the wrong primitive at the human CLI surface. Planner: SQL likely joins nodes → containing package row on `package_uri`, then matches package's `name` column.
- **D-07: Unknown-package behavior is silent zero-result, exit 1.** `--in-package nonexistent` returns no rows with the same UX as "filter matched zero nodes" — exit 1, no special warning. Do NOT distinguish "package does not exist in graph" from "package exists but has no matching children."
  - **Why:** Simplest mental model — `--in-package` is a filter, not a lookup. Avoids a special-case branch in the query layer. Aligns with how `--name foo` (no match) already behaves.
- **D-08: Case-insensitive exact match.** `--in-package Graph-IO`, `--in-package graph-io`, `--in-package GRAPH-IO` all match the package literally named `graph-io`. Not substring; not prefix.
  - **Why:** Friendlier for hand typing without introducing the unpredictability of substring matching (which would conflict with Phase 37's need for deterministic librarian-tool semantics). Exact match keeps results stable; case-insensitivity costs a `LOWER()` or pre-normalize on both sides.
- **D-09: Hard cap at 50 rows + truncation notice.** Unbounded queries like `cg find --in-package graph-io` (returns every node in the package) cap at 50 rows with a "showing 50 of N" trailer. Applies to all output formats — JSON and human.
  - **Why:** Establishes the cap convention that Phase 37 (LIBTOOLS-02) will mirror at the librarian-tool layer. Single source of truth for "what is a safe row count to ship to an LLM or a terminal." Keeps `cg` CLI and librarian tools behaviorally consistent.

### Migration & Test-Caller Update
- **D-10: Hard cut, single commit.** Parser change + all positional test call sites in `packages/graph-io/tests/` updated atomically in one commit. Old form errors immediately; no transitional window.
  - **Why:** Aligns with Pitfall 5 (STATE.md) — "grep all callers and fix in same commit." Mirrors the phase goal language ("produces a clear parse error rather than silent wrong behavior") exactly. The CLI has no documented external callers outside tests (grep-confirmed: only `q_find.py` and a `resolve.py` comment reference `cg find` in repo source; wiki-io fixture docs are snapshot data, not real consumers).
  - **Test call sites identified (planner: re-grep before edits, list non-exhaustive):**
    - `packages/graph-io/tests/test_smoke.py:23` (subcommand string list)
    - `packages/graph-io/tests/test_cli_anti_regression.py:84,104,118` (`find` invocation + expected-arg lists)
    - `packages/graph-io/tests/test_e2e.py:35` (positional `find alpha`)
    - `packages/graph-io/tests/test_cli_exit_codes.py:108,204` (positional `find x` / `find foo`)
    - `packages/graph-io/tests/test_cli_smoke.py:43,49,91` (positional `find alpha [--kind …]`)
- **D-11: Anti-regression test in `test_cli_anti_regression.py`.** Add a new test asserting `cg find foo.py` (positional) exits non-zero with a stderr error message. Cheap insurance against someone re-adding the positional `add_argument` later. Filename chosen because the file already exists for exactly this class of guard.
  - **Why:** Honors the phase's "no silent wrong behavior" spirit. Without a guard, a future refactor could quietly restore the positional form and all existing tests would still pass (they'd use named flags).

### Claude's Discretion
- Exact SQL form for the `--in-package` filter (likely a JOIN against the package URI / containment edge, but specific schema details are planner's call after reading current `queries.find()` and the v1.6 schema).
- Whether to expose `_VALID_KINDS` to argparse via direct import or a small accessor — planner picks based on existing import structure.
- Exact wording of the `parser.error()` message for D-01 — planner picks; just make it name all three flags.
- Whether the row cap (D-09) lives in `q_find.py`, `queries.find()`, or `_format.render()` — planner picks based on what surface is most reusable for Phase 37.

### Folded Todos
None. The todo-match scan surfaced two bootstrap todos as low-confidence keyword matches (score 0.6), both already folded into Phase 35 (HYGIENE-11, HYGIENE-12). Neither relates to `cg find` — not folded into Phase 36.

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Phase Scope & Requirements
- `.planning/REQUIREMENTS.md` (CGFIND-01..03 section) — three locked requirements
- `.planning/ROADMAP.md` (Phase 36 section) — goal + 3 concrete success criteria (SC#1: named-flag form works; SC#2: never exit 2 when valid flags supplied; SC#3: positional form errors clearly + all test callers updated in same commit)
- `.planning/STATE.md` (Pitfall 5) — "grep all positional callers in `packages/graph-io/tests/`, fix in same commit"

### CLI Layer Being Edited
- `packages/graph-io/src/graph_io/cli/q_find.py` — the parser; `add_arguments()` is the swap site (lines 14-16 currently: positional `name` + `--kind`). `run()` body adapts to read `args.name` / `args.kind` / `args.in_package`.
- `packages/graph-io/src/graph_io/queries.py:166` — `find(conn, *, name, kind)` signature; needs `in_package: str | None = None` added and SQL extended to filter by containing package's short name (case-insensitive exact match).
- `packages/graph-io/src/graph_io/cli/_format.py` — `render(records, fmt=…)` is where the 50-row cap + truncation notice lands (D-09; planner: decide if cap belongs here, in `queries.find()`, or in `q_find.py`).
- `packages/graph-io/src/graph_io/exit_codes.py` — existing exit-code constants (SUCCESS=0, NOT_INITIALIZED, SCHEMA_MISMATCH); confirm no new code needed (exit 2 is argparse's built-in via `parser.error()`).

### Test Call Sites (Hard-Cut Migration Targets)
- `packages/graph-io/tests/test_smoke.py` — line 23 subcommand inventory + any positional invocations
- `packages/graph-io/tests/test_cli_anti_regression.py` — lines 84, 104, 118 + add new anti-regression test (D-11)
- `packages/graph-io/tests/test_e2e.py` — line 35: `_cg(["--fmt", "json", "find", "alpha"], …)`
- `packages/graph-io/tests/test_cli_exit_codes.py` — lines 108 (`["find", "x"]`), 204 (`_cg(["find", "foo"], …)`)
- `packages/graph-io/tests/test_cli_smoke.py` — lines 43, 49, 91 (various positional `find …` forms)
- Planner: re-grep `"find"` across `packages/graph-io/tests/` before edits — the list above is from the discuss-phase scout and may not be exhaustive after Phase 35 merges (which touches some test infrastructure).

### Prior Discuss/Plan Context (Read for Coupling Awareness)
- `.planning/phases/35-wiki-bootstrap-hygiene-burn-down/35-CONTEXT.md` — Phase 35 must merge before Phase 36 (Pitfall 3; hygiene-first ordering). Phase 35 doesn't touch `cg find` parser, so no file conflicts expected, but plan AFTER Phase 35's branch merges to avoid rebase pain.

### Phase 37 Coupling
- The cap (D-09) and case-insensitive-exact-match (D-08) decisions deliberately set precedent for Phase 37 LIBTOOLS-02 (`_format.render(records, fmt="human")` with 50-row hard cap + truncation notice). Phase 37's librarian tools will wrap `queries.find()` and inherit its `--in-package` behavior; keep semantics symmetric.

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- `_VALID_KINDS` set in `queries.py` — already provides the canonical list of valid kind values; argparse can consume it directly via `choices=sorted(_VALID_KINDS)`. No new validation logic to write.
- `queries.find(conn, *, name, kind)` is already keyword-only — minimal signature surgery to add `in_package` (just add a third keyword + extend the SQL `WHERE` clause; existing `ValueError` for "neither name nor kind" extends to "neither name nor kind nor in_package").
- `_format.render(records, fmt=…)` already centralizes output formatting — the row cap + truncation notice (D-09) plugs in cleanly here if planner picks that surface.
- `exit_codes.SUCCESS` (and the existing exit-code module) — no new codes needed; D-01/D-04 use argparse's built-in exit 2 via `parser.error()`.

### Established Patterns
- argparse-driven sub-parsers throughout `packages/graph-io/src/graph_io/cli/*` (one file per subcommand, `add_arguments(parser)` + `run(args)` shape) — Phase 36 follows the existing convention exactly.
- `test_cli_anti_regression.py` already exists as the home for "this old form must error" guards — D-11's new test slots in without inventing a new test file.
- `_cg(args, repo_dir)` helper in tests/*.py (subprocess invocation of the `cg` CLI) — used by every test call site that needs updating. Mechanical sed-style rewrite from `["find", "alpha"]` to `["find", "--name", "alpha"]` is the migration shape.

### Integration Points
- Parser → query layer: `q_find.py`'s `run()` passes `args.name` / `args.kind` / `args.in_package` to `queries.find()` as keyword args. The argparse → query boundary is the single substitution point.
- Query layer → format layer: `queries.find()` returns `list[NodeRecord]` to `_format.render()`. If the row cap lives in `_format.render()` (D-09), it sees all rows but emits only 50 — sample-efficient for big results.
- CLI exit codes: SC#1/SC#2 require exit 0 (found) / exit 1 (not-found) / exit 2 (parse error) ladder. Current `q_find.py` always returns `SUCCESS` regardless of row count — planner: verify whether to return exit 1 on zero-row result, or whether the existing behavior is intentional (likely needs updating to match SC#1/SC#2).

</code_context>

<specifics>
## Specific Ideas

- `D-11`'s anti-regression test should assert both (a) non-zero exit, AND (b) stderr contains "unrecognized arguments" (or whatever argparse emits) — not just exit code, so it catches future refactors that might silently start accepting positional args again with a different exit code.
- For `D-10`'s migration, mechanical search-and-replace in tests is: `["find", "X"]` → `["find", "--name", "X"]`; `["find", "X", "--kind", "Y"]` → `["find", "--name", "X", "--kind", "Y"]`. The `_cg` helper signature doesn't change.
- `--in-package` argparse `help=` text suggestion: `"Filter results to nodes contained in the named package (case-insensitive exact match)."` — surfaces D-08 inline.

</specifics>

<deferred>
## Deferred Ideas

- **Custom helpful message for old positional form** — Considered in Parse Error UX discussion; rejected for v1.7 in favor of argparse default (D-04). Revisit if post-merge user feedback shows usage friction (e.g. someone re-runs `cg find foo` from muscle memory and bounces off the cryptic argparse message). Cheap to add later as a `parser.error()` override.
- **Smart kind-detection for old positional** — Considered ("if positional value matches a valid kind, suggest --kind"); rejected as speculative. Revisit only if argparse-default proves insufficient in practice.
- **`--in-package` substring / prefix matching** — Considered for D-08; rejected for determinism. If a future phase needs fuzzy package discovery, add a separate `cg find --in-package-like` or `cg search --package <pattern>` rather than overloading the existing flag.
- **Per-surface row cap (CLI vs tool layer)** — Considered as alternative to D-09 (e.g. CLI cap at 200, tool layer at 50). Rejected for consistency between Phase 36 and Phase 37 LIBTOOLS-02. Revisit if Phase 37 actually wants a different threshold.
- **Soft deprecation of positional form for one milestone** — Considered as a migration option; rejected because SC#3 mandates a parse error (a warning isn't a parse error) and would require an SC change. Phase 36 is hard-cut.

</deferred>

---

*Phase: 36-cg-find-parser-ergonomics*
*Context gathered: 2026-05-26*
