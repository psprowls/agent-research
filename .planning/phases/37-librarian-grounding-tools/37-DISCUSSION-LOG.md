# Phase 37: Librarian Grounding Tools - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md — this log preserves the alternatives considered.

**Date:** 2026-05-26
**Phase:** 37-librarian-grounding-tools
**Areas discussed:** Tool naming + arg shape, CountTokens budget overflow behavior, NOT_INITIALIZED fallback UX, The 5 tools (THE scoping decision)

---

## Tool naming + arg shape

### Q1: Tool naming convention

| Option | Description | Selected |
|--------|-------------|----------|
| `graph_*` prefix | Parallel to existing `wiki_*` MCP prefix. Single graph-ops namespace. | |
| `cg_*` prefix (mirror CLI) | Direct correspondence to `cg <subcommand>` mental model. | ✓ |
| Bare verb / no prefix | Shortest schema; collision risk with other tools. | |

**User's choice:** `cg_*` prefix (mirror CLI)
**Notes:** Tool == CLI subcommand mental model.

### Q2: `describe`-family multiplexing

| Option | Description | Selected |
|--------|-------------|----------|
| Single `cg_describe(kind, identifier)` | One tool, enum kind. Costs 1 slot for 6 query functions. | ✓ |
| Separate per-kind describe tools | Sharper schemas; blows the ≤5 budget. | |
| Two tools split: identity vs. structure | name-keyed vs path-keyed describe. Costs 2 slots. | |

**User's choice:** Single `cg_describe(kind, identifier)` (Recommended)
**Notes:** Preserves slot budget for relationship navigation.

### Q3: Docstring detail level

| Option | Description | Selected |
|--------|-------------|----------|
| Concise: one-line + arg types | Minimal token overhead. Aligns with CountTokens budget. | ✓ |
| Verbose: docstring + examples + return-shape | Better routing accuracy; eats budget. | |
| Mirror CLI `--help` 1:1 | Keeps CLI and tool surface in lockstep. ~30-60 tokens/tool. | |

**User's choice:** Concise: one-line summary + arg types (Recommended)
**Notes:** Preserves headroom for inputs (D-05).

---

## CountTokens budget overflow behavior

### Q1: Overflow response

| Option | Description | Selected |
|--------|-------------|----------|
| Hard abort with clear error | Exit non-zero with actionable message. | ✓ |
| Skip graph tools, run librarian without them | Same path as NOT_INITIALIZED fallback. Silent degradation. | |
| Truncate input prompt to fit | Trim librarian input. Drops context for fidelity. | |

**User's choice:** Hard abort with clear error (Recommended)
**Notes:** Aligns with "no silent wrong behavior" theme.

### Q2: Budget definition

| Option | Description | Selected |
|--------|-------------|----------|
| Configured headroom (e.g. 90% of context window) | Reserve room for tool-call back-and-forth. | ✓ |
| Raw model context window | Simplest; risks mid-conversation overflow. | |
| Fixed token cap regardless of model | Decouples from model; doesn't scale up. | |

**User's choice:** Configured headroom (~90% of context window) (Recommended)
**Notes:** Concrete value lives in models.toml or graph_tools.py constant.

### Q3: Gate location

| Option | Description | Selected |
|--------|-------------|----------|
| `commands/query.py` at command entry | Matches LIBTOOLS-05 verbatim. Clean separation. | ✓ |
| Inside `build_graph_tools(conn)` factory | Co-locates gate with the tool surface. Couples concerns. | |
| Both: factory exposes schema size, caller decides | Most flexible; most code. | |

**User's choice:** `commands/query.py` at command entry (Recommended)
**Notes:** Factory is pure construction; no token logic.

---

## NOT_INITIALIZED fallback UX

### Q1: System-prompt handling when graph missing

| Option | Description | Selected |
|--------|-------------|----------|
| Bind no tools + system-prompt addendum | One canonical prompt + conditional addendum. | ✓ |
| Bind no tools + separate degraded system prompt | Two prompt variants; drift risk. | |
| Refuse to run; tell user to run `cg update` | Breaks today's librarian path; not "graceful." | |

**User's choice:** Bind no tools + 'graph unavailable' notice (Recommended)
**Notes:** Preserves existing librarian-without-tools behavior.

### Q2: Human user visibility

| Option | Description | Selected |
|--------|-------------|----------|
| Single stderr line at top of run | One-shot, greppable signal. | ✓ |
| Per-librarian-call warning | Loud signal across 5 parallel librarians; noisy. | |
| Silent (only system prompt tells LLM) | Hides UX state from user. Discouraged. | |

**User's choice:** Single stderr line at top of run (Recommended)
**Notes:** `[graph unavailable: run 'cg update' …]`

---

## The 5 tools (THE scoping decision)

### Q1: Tool slate

| Option | Description | Selected |
|--------|-------------|----------|
| Identity & relationships slate | cg_find, cg_describe, cg_callers, cg_callees, cg_imports. Reaches ~12 underlying queries. | ✓ |
| Identity & navigation slate | cg_find, cg_describe, cg_list, cg_callers, cg_imports. Drops callees, adds list. | |
| Symbol-centric minimal slate | cg_find, cg_describe, cg_callers, cg_callees only (4 tools); reserves slot 5. | |

**User's choice:** Identity & relationships slate (Recommended)
**Notes:** Covers "who is X / what's in Y / who depends on / what depends on this".

### Q2: `cg_describe.kind` arg type

| Option | Description | Selected |
|--------|-------------|----------|
| Exact enum (package/path/repository/domain/entry_point/test_suite) | Literal mapping; argparse-style strictness. | ✓ |
| Enum + common aliases | `pkg`, `module`, `repo`, etc. Normalization layer + drift risk. | |
| Single string `query`, infer kind heuristically | Powerful but unpredictable; multiplexes two responsibilities. | |

**User's choice:** Exact enum (Recommended)
**Notes:** Clean schema; no aliases.

### Q3: `cg_callers` / `cg_callees` default depth

| Option | Description | Selected |
|--------|-------------|----------|
| Match `queries.py` default of 3 | Mirror exactly; single source of truth. | ✓ |
| Lower default (e.g. 1) | Cheaper output, smaller responses. Drift from CLI. | |
| Remove depth from tool surface | Hard-code depth=3; fewer args in schema. | |

**User's choice:** Match `queries.py` default of 3 (Recommended)
**Notes:** Override stays explicit via the depth arg.

### Q4: `cg_find` CLI parity

| Option | Description | Selected |
|--------|-------------|----------|
| Exact parity with `cg find` CLI | Same at-least-one rule, case-insensitive package match, 50-row cap. | ✓ |
| Looser: allow no-arg `cg_find` to list-all (capped) | Friendlier for LLM exploration; diverges from CLI. | |
| Stricter: require both name AND (kind OR in_package) | Sharper queries, fewer wasted calls. Diverges from CLI. | |

**User's choice:** Exact parity with `cg find` CLI (Recommended)
**Notes:** Tool returns error STRING (not raises) so LLM can recover.

---

## Claude's Discretion

- Exact docstring wording for each of the 5 tools
- Whether `build_graph_tools(conn)` returns list/tuple/NamedTuple
- Concrete `librarian_budget_fraction` value (suggest 0.90)
- New exit code for `BUDGET_EXCEEDED`
- Exact spelling of system-prompt addendum and stderr line
- `cg_describe` dispatch: `match`/dict/if-elif chain — planner picks
- Reuse Phase 36's case-insensitive package match mechanism

## Deferred Ideas

- `cg_list(kind)` tool — rejected for v1.7 slate; revisit if eval data shows librarian enumeration needs
- `cg_imported_by` / `cg_exports` reverse-navigation tools — low marginal value, no slot budget
- Aliases for `cg_describe.kind` — rejected; revisit only if eval data justifies
- Verbose docstrings — rejected for budget; revisit on larger-context librarian models
- MCP server exposure — that's Phase 38 (different namespace, `graph_*` prefix)
- Trace fields for graph-tool calls — design in Phase 38's `--trace` integration
- Per-role budget headroom tuning — empirical work for a future eval-harness-driven phase
