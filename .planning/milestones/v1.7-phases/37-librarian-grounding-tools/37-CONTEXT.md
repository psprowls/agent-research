# Phase 37: Librarian Grounding Tools - Context

**Gathered:** 2026-05-26
**Status:** Ready for planning

<domain>
## Phase Boundary

Give the librarian agent up to 5 `@tool`-decorated callables that wrap selected `graph_io.queries.*` functions, so it can resolve symbol and package identity through the code graph instead of guessing from vault excerpts. Implementation lives in `agents/graph-wiki-agent/src/graph_wiki_agent/graph_tools.py` exposing a `build_graph_tools(conn)` closure factory, wired into `agents/graph-wiki-agent/src/graph_wiki_agent/commands/query.py`'s librarian fan-out with a shared read-only connection and a CountTokens pre-flight gate.

Out of scope: any `graph-wiki-agent graph` CLI/MCP surface (Phase 38); scanner / ingestor consumption of graph-io (Phases 39-40); changes to non-librarian roles (code_reader, synthesizer); query.py refactors beyond what's needed to wire the new tools.

</domain>

<decisions>
## Implementation Decisions

### Tool Naming & Argument Shape

- **D-01: `cg_*` prefix.** Tools are named `cg_find`, `cg_describe`, `cg_callers`, `cg_callees`, `cg_imports`. Mirrors the `cg` CLI binary 1:1, so the librarian's mental model is "tool == CLI subcommand."
  - **Why:** The LLM already encounters `cg <subcommand>` form throughout vault pages and project docs; reusing the prefix collapses two surfaces into one. Phase 38's `graph_*` MCP prefix is parallel and not in conflict — Phase 38 surfaces graph ops to MCP hosts, Phase 37 surfaces them to the librarian's in-process LLM.
  - **What it does NOT do:** Does not require literal binary-name parity for non-CLI surfaces. Phase 38 still uses `graph_*` for MCP because the prefix lives in a different namespace.

- **D-02: Single multiplexed `cg_describe(kind, identifier)` tool.** Instead of six separate `cg_describe_package` / `cg_describe_path` / `cg_describe_repository` / `cg_describe_domain` / `cg_describe_entry_point` / `cg_describe_test_suite` tools, expose ONE tool with `kind` and `identifier` args.
  - **Why:** Six describe tools would consume the entire ≤5 budget. Multiplexing into one preserves slot budget for `find` + relationship navigation (`callers`/`callees`/`imports`). Mirrors `cg describe-*` CLI subcommand family at the conceptual level.
  - **`kind` arg type (D-10 below):** strict enum.

- **D-03: Concise docstrings — one-line summary + arg types.** Each `@tool` callable carries a single-sentence docstring plus `Args:` listing arg names and types/values. No multi-line examples; no return-shape sketches. The LLM sees minimal tokens per schema.
  - **Why:** Aligns with the CountTokens budget gate (LIBTOOLS-05). Verbose docstrings eat into the headroom (D-05) and risk pushing past the ceiling on long vault inputs. The argparse `--help` strings from Phase 36 are a reasonable docstring source where they overlap.
  - **Acceptable example:** `'Find nodes by name and/or kind in the code graph. Args: name (optional), kind (optional, e.g. "class"|"function"), in_package (optional, case-insensitive package name).'`

### CountTokens Budget Overflow Behavior

- **D-04: Hard abort with clear error.** When CountTokens pre-flight detects total tokens (system prompt + tool schemas + librarian input) exceeds the budget, exit non-zero with a structured stderr message: `librarian: token budget exceeded (X of Y tokens). Reduce vault scope or use a larger-context model.`
  - **Why:** Honors "no silent wrong behavior" from Phase 36's spirit. User gets actionable feedback (use a different model OR reduce inputs). The alternatives (drop tools / truncate input) silently degrade response quality, which is worse than a clear stop.
  - **Exit code:** non-zero; specific code TBD by planner (suggest a new `BUDGET_EXCEEDED` exit code in `graph_wiki_agent` if one doesn't exist yet, OR reuse a generic non-success code if the existing exit-code surface is small).

- **D-05: Budget = configured headroom (~90% of model context window).** Reserve ~10% of the model's context for the librarian's tool-call back-and-forth and its own output. The concrete value lives in `models.toml` per-role (preferred) or as a constant in `graph_tools.py` if per-role overrides aren't already a thing.
  - **Why:** Avoids edge-case overflow during the agent loop when the librarian appends tool messages mid-conversation. 90% is a starting point; planner may pick a different fraction if research surfaces a better empirical value.
  - **Concrete number:** Planner picks. Suggest `librarian_budget_fraction = 0.90` (configurable) so the headroom can be tuned without code changes.

- **D-06: Gate lives in `commands/query.py` at command entry.** The CountTokens check happens BEFORE any `pool.run_all()` fan-out. `build_graph_tools(conn)` is pure construction — no token logic inside the factory.
  - **Why:** Matches LIBTOOLS-05 ("gate enforced at command entry before any LLM call") verbatim. Clean separation: factory builds tools, caller decides whether to use them.
  - **Implementation note:** Planner should expose a helper (e.g. `estimate_tool_schema_tokens(tools)`) that `commands/query.py` can call without coupling to `build_graph_tools()` internals.

### NOT_INITIALIZED Fallback UX

- **D-07: Bind no tools + system-prompt addendum.** When `graph_dir(workspace) / "code.db"` does not exist (or `read_only_connect()` raises `GraphNotInitializedError`), the librarian runs with NO tools, using the standard `LIBRARIAN_SYSTEM` prompt PLUS a one-line addendum: `NOTE: code graph tools are unavailable in this workspace; rely on vault excerpts only.`
  - **Why:** Honors LIBTOOLS-04's "graceful fallback (librarian still runs, with a clear notice)." Preserves the current librarian-without-tools behavior (this is the today path) so v1.7 doesn't regress any workspace lacking a graph.
  - **What it does NOT do:** Does not maintain two separate system-prompt files. One canonical prompt + one conditional addendum string concatenated at runtime.

- **D-08: Single stderr line at top of run.** Before any librarian fan-out begins, emit `[graph unavailable: run 'cg update' to enable code-graph grounding tools]` to stderr exactly once.
  - **Why:** One-shot signal is greppable in traces; per-call warnings would be noisy across 5 parallel librarians. Silent is unacceptable — users need to know they ran in degraded mode.
  - **Trace impact:** If `--trace` is on (Phase 38 territory), planner should mention this in the trace record as a structured field (e.g. `"graph_tools": "unavailable"`). Not blocking for Phase 37; just don't make it impossible to add later.

### The 5 Tools (THE scoping decision)

- **D-09: Identity & relationships slate.** The 5 `@tool` callables exposed by `build_graph_tools(conn)`:
  1. **`cg_find(name=None, kind=None, in_package=None) -> str`** — wraps `queries.find()`; exact parity with `cg find` CLI (D-12).
  2. **`cg_describe(kind, identifier) -> str`** — multiplexed (D-02); dispatches to one of `describe_package` / `describe_path` / `describe_repository` / `describe_domain` / `describe_entry_point` / `describe_test_suite` based on `kind`.
  3. **`cg_callers(name, depth=3) -> str`** — wraps `queries.callers()`.
  4. **`cg_callees(name, depth=3) -> str`** — wraps `queries.callees()`.
  5. **`cg_imports(path) -> str`** — wraps `queries.imports()`.
  - **Why:** Covers "who is X" (find), "what's in Y" (describe — fans out to 6 query functions), "who depends on this / what does this depend on" (callers, callees, imports). Skips `list_*` (librarian rarely needs top-level enumeration mid-query), `imported_by` / `exports` / `exported_by` (file-level reverse navigation rarely surfaces in wiki Q&A), and `tests_for_*` / `domain_*` / `cross_cutting_packages` (specialized; librarian falls back to vault excerpts if asked).
  - **Slot accounting:** 5 tools used; 0 reserved. If a future need surfaces, retire the lowest-value tool first (likely `cg_imports`, but planner should leave that decision for a later phase that has measurement data).

- **D-10: `cg_describe.kind` = exact enum.** Accepted values: `package` | `path` | `repository` | `domain` | `entry_point` | `test_suite`. Literal mapping to the 6 `describe_*` query functions. Any other value returns an error string the LLM can read: `error: invalid kind '<value>'; valid: package, path, repository, domain, entry_point, test_suite`.
  - **Why:** Strict enum surfaces a clean schema to the LLM and matches argparse-style strictness. No aliases (`pkg`, `module`, etc.) — adds normalization layer + drift risk for marginal ergonomic gain. The LLM can read the enum from the tool schema.

- **D-11: `cg_callers` / `cg_callees` default depth = 3.** Mirror `queries.callers(conn, *, name, depth=3)` exactly. Override is explicit via the `depth` arg.
  - **Why:** Single source of truth — librarian sees the same default whether the query runs from CLI or LLM tool. Changing the default at the tool layer would create CLI/tool divergence the librarian then has to remember.

- **D-12: `cg_find` = exact parity with `cg find` CLI.** Same at-least-one-flag rule (D-01 of Phase 36 CONTEXT.md), same case-insensitive package match (D-08 of Phase 36), same 50-row cap (D-09 of Phase 36). If LLM calls `cg_find()` with no args, the tool returns an error STRING (not an exception): `error: at least one of name, kind, in_package required`.
  - **Why:** Single mental model. The LLM can recover from the error string by issuing a corrected call. Tool errors as strings (not exceptions) keep the agent loop driving forward without crashing the fan-out.
  - **Cross-phase coupling:** Phase 36 must merge before Phase 37 implementation — `queries.find()` signature gains `in_package` in Phase 36 (D-06/D-08/D-09 of `36-CONTEXT.md`), and `cg_find` consumes it.

### Claude's Discretion

- Exact docstring wording for each of the 5 tools (D-03 says concise + arg types — planner picks the prose, may reuse argparse `help=` strings from Phase 36 where they overlap).
- Whether `build_graph_tools(conn)` returns a list, a tuple, or a NamedTuple of tools — planner picks based on how `commands/query.py` will iterate.
- Concrete `librarian_budget_fraction` value (D-05 suggests 0.90; planner may settle on a different number after consulting models.toml limits and any empirical data from the eval harness).
- New exit code for `BUDGET_EXCEEDED` (D-04) — planner picks code value and decides whether to add a new constant or reuse an existing one.
- Exact spelling of the system-prompt addendum (D-07) and the stderr line (D-08).
- Implementation seam for the case-insensitive package match inside `cg_find` — should reuse Phase 36's mechanism (whatever the planner there landed on; see Phase 36 task notes).
- Whether `cg_describe` dispatches via Python `match`/dict-of-callables vs. an if/elif chain — both are fine; planner picks based on existing code style in the agent package.

### Folded Todos

None. The todo-match scan (run during Phase 37 prep) returned no new matches for Phase 37 keywords. The two bootstrap todos are already folded into Phase 35 (HYGIENE-11, HYGIENE-12).

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Phase Scope & Requirements
- `.planning/REQUIREMENTS.md` (LIBTOOLS-01..05 section) — five locked requirements
- `.planning/ROADMAP.md` (Phase 37 section) — phase goal + 5 concrete success criteria + the explicit "open scoping question" deferred-to-here-and-now-resolved-in-D-09 about tool grouping
- `.planning/STATE.md` (Pitfalls 1, 2, 4) — tool count ≤5; non-string returns crash Bedrock; per-tool-call connection open is forbidden

### Cross-Phase Coupling (READ BEFORE PLANNING)
- `.planning/phases/36-cg-find-parser-ergonomics/36-CONTEXT.md` — `cg_find` tool surface mirrors Phase 36's CLI behavior verbatim (D-12 above); Phase 36 must merge first
- `.planning/phases/36-cg-find-parser-ergonomics/36-01-PLAN.md` — concrete implementation of `queries.find()`'s new `in_package` arg and the `_format.render(cap=…)` symmetry that LIBTOOLS-02 will reuse
- `.planning/phases/35-wiki-bootstrap-hygiene-burn-down/35-CONTEXT.md` — Phase 35 must merge first (Pitfall 3 hygiene-first ordering); no direct file overlap with Phase 37 but the queue order matters

### Target Files (Net-New)
- `agents/graph-wiki-agent/src/graph_wiki_agent/graph_tools.py` — NEW; exposes `build_graph_tools(conn)` factory returning the 5 `@tool` callables

### Target Files (Modified)
- `agents/graph-wiki-agent/src/graph_wiki_agent/commands/query.py` — librarian fan-out site; opens read-only connection, runs CountTokens gate, calls `bind_tools(build_graph_tools(conn))`, handles NOT_INITIALIZED fallback. Existing `read_file`/`code_reader` pattern at `query.py:415-429` is the structural analog — Phase 37 mirrors it for the librarian role.
- `agents/graph-wiki-agent/src/graph_wiki_agent/prompts/librarian.py` — `LIBRARIAN_SYSTEM` string; D-07 addendum is concatenated to this at runtime (not edited into the static string).

### Query Layer (Read-Only; No Changes Beyond Phase 36's)
- `packages/graph-io/src/graph_io/queries.py` — source of the 6 target functions:
  - `find` (line 166) — wraps into `cg_find` (after Phase 36 adds `in_package` arg)
  - `callers` (line 204), `callees` (line 228) — wrap into `cg_callers` / `cg_callees`
  - `imports` (line 252) — wraps into `cg_imports`
  - `describe_package` (line 266), `describe_path` (line 345), `describe_repository` (line 393), `describe_domain` (line 420), `describe_entry_point` (line 451), `describe_test_suite` (line 476) — multiplexed by `cg_describe`
- `packages/graph-io/src/graph_io/cli/_format.py` — `render(records, fmt="human", cap=…)` (Phase 36 adds `cap`; Phase 37 LIBTOOLS-02 reuses it)
- `packages/graph-io/src/graph_io/store.py` — `read_only_connect()` and `GraphNotInitializedError`
- `packages/workspace-io/src/workspace_io/paths.py` — `graph_dir(workspace)` resolves to `<workspace>/.graph-wiki/graph/code.db` (or similar — planner: verify against current paths.py)

### Connection Lifetime Pattern
- `agents/graph-wiki-agent/src/graph_wiki_agent/commands/query.py:415-429` (`@tool def read_file: ... code_llm = code_llm_raw.bind_tools([read_file])`) — established closure pattern that `build_graph_tools(conn)` mirrors. Connection opened at command entry, captured by closure, closed in `finally` (LIBTOOLS-03).

### langchain-aws Floor
- `pyproject.toml` of `agents/graph-wiki-agent` (and root workspace if it pins) — bump `langchain-aws>=1.4.7` (strip-invalid-tool_use-block fix is load-bearing for multi-tool fan-out; STATE.md key decision).

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- `agents/graph-wiki-agent/src/graph_wiki_agent/commands/query.py:415-429` — the `@tool def read_file` closure + `bind_tools([read_file])` pattern is THE template for `build_graph_tools(conn)`. Same shape: closure captures a resource (here `repo_root`, in Phase 37 `conn`), tool body is short, errors return as `str` rather than raise.
- `graph_io.queries.find()` and the `describe_*` family already return rich record dataclasses (`NodeRecord`, `PackageDescription`, etc.) — Phase 37 just needs to wrap each in `_format.render(records, fmt="human", cap=50)` (LIBTOOLS-02) and return the string.
- `_format.render(records, fmt="human")` — Phase 36 is adding a `cap` kwarg; Phase 37 reuses it for LIBTOOLS-02. Don't fork.
- `LIBRARIAN_SYSTEM` prompt at `prompts/librarian.py` — base prompt is unchanged; D-07 concatenates an addendum at runtime when graph is missing.
- `model_adapter.loader.make_llm("librarian")` — already exists and returns a `_GuardedChatBedrockConverse`. Just call `.bind_tools(build_graph_tools(conn))` after it.

### Established Patterns
- Tool wrappers in this codebase return strings, never raise into the agent loop (read_file pattern: catches `PermissionError` / `OSError`, returns `f"ERROR: {exc}"`). D-12 extends this: tool argument errors also return error strings instead of raising — LLM can recover via a corrected call.
- Connection lifetime: open in the outermost command function (here `run_query` or its sibling), pass into factory, close in `finally`. Mirrors how `code_reader` doesn't keep file handles open across the fan-out.
- Subagent fan-out via `SubagentPool` (in-house, not LangGraph) — `pool.run_all(...)` is the existing async fan-out primitive. Phase 37 does NOT change this; the tools are added to each subagent's LLM via `.bind_tools()` before the fan-out starts.

### Integration Points
- `commands/query.py` opens the conn → calls CountTokens gate (D-06) → passes conn to `build_graph_tools(conn)` → calls `.bind_tools()` on the librarian LLM → kicks off `pool.run_all()` → in `finally`, closes the conn. Single linear flow at command entry; no per-tool-call SQLite opens (Pitfall 4).
- The CountTokens gate (D-06) needs total token count for: librarian system prompt + addendum if any + tool schemas + the librarian's input messages. `boto3.bedrock-runtime` already exposes `count_tokens` for `ChatBedrockConverse`-compatible models (research item for planner — verify whether to call the boto3 API directly or use a LangChain helper).
- D-07 NOT_INITIALIZED fallback: catch `GraphNotInitializedError` from `read_only_connect()` at command entry; switch to no-tools path; emit D-08 stderr line.

</code_context>

<specifics>
## Specific Ideas

- `build_graph_tools(conn)` factory signature: `def build_graph_tools(conn: sqlite3.Connection) -> list[BaseTool]` — returns a plain list, lets `commands/query.py` iterate or pass directly to `.bind_tools()`.
- For D-12's "error string when LLM calls `cg_find()` with no args" behavior: the tool body catches its own `ValueError` from the bare-flag check and returns a formatted string. Same pattern as `read_file`'s `f"ERROR: {exc}"` but with a recoverable message.
- For D-02's multiplexed `cg_describe`, the dispatch table is fine as a module-level dict mapping kind → function: `_DESCRIBE_DISPATCH = {"package": queries.describe_package, ...}` — easy to grep, easy to extend in a future phase that goes from 5 → fewer-but-more-flexible tools.
- D-08's stderr line should be emitted from `commands/query.py` (not from `build_graph_tools` — the factory is pure tool construction). Emit it in the same `try/except GraphNotInitializedError` block that decides to skip the conn.

</specifics>

<deferred>
## Deferred Ideas

- **Add `cg_list(kind)` tool** — Considered (alternative slate B in the gray-area discussion); rejected because top-level enumeration is rare in librarian Q&A. Revisit if eval harness data shows the librarian repeatedly trying to enumerate.
- **Add `cg_imported_by(name)` / `cg_exports(path)` tools** — Reverse-navigation tools rejected for the v1.7 slate (low marginal value, no slot budget). Revisit in a future phase that focuses on dependency-graph exploration use cases.
- **Aliases for `cg_describe.kind`** (e.g. `pkg` → `package`) — Considered and rejected (D-10) as a normalization layer that adds drift risk. Revisit only if eval data shows the LLM consistently using shorthand and getting penalized.
- **Verbose docstrings with examples** — Considered (D-03 alternative); rejected for the CountTokens budget. If a future phase introduces a larger-context librarian model where the headroom isn't tight, revisit and trade verbosity for routing accuracy.
- **MCP server exposure of `cg_*` tools** — That's Phase 38 (`graph_*` prefix, MCP namespace). Not deferred so much as scoped-elsewhere.
- **Trace fields for graph-tool calls** (e.g. `tool_name`, `args`, `row_count`, `truncated_at_50`) — Useful for Phase 38's `--trace` integration; record-shape can be designed in Phase 38 without changing Phase 37's tool code (the agent loop already records tool calls via `usage_metadata` per Phase 9). Defer concrete trace schema to Phase 38.
- **Per-role budget headroom values** — D-05 picks 0.90 as a starting point. Empirical tuning belongs to a future eval-harness-driven phase (or a quick task).

</deferred>

---

*Phase: 37-librarian-grounding-tools*
*Context gathered: 2026-05-26*
