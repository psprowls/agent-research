# Phase 37: Librarian Grounding Tools — Research

**Researched:** 2026-05-26
**Status:** Research complete; ready for planning.

> Read alongside `37-CONTEXT.md` — this RESEARCH.md does NOT restate decisions D-01..D-12.
> Its job is to surface implementation-level facts the planner needs that are not in CONTEXT.md.

## RESEARCH COMPLETE

---

## 1. Current Librarian Fan-out Structure (the surface to modify)

`agents/graph-wiki-agent/src/graph_wiki_agent/commands/query.py:802-918` defines `run_query()`. The librarian sub-flow (step 6, lines 881-918) currently:

1. Resolves an override or calls `make_llm("librarian")` → `librarian_llm`.
2. Constructs a `SubagentPool` rooted at `wiki / ".graph-wiki" / "traces"`.
3. Defines `drill_page(page_path)` — a coroutine that reads the page, builds a 2-message thread (`SystemMessage(LIBRARIAN_SYSTEM)` + `HumanMessage(...)`), and calls `librarian_llm.ainvoke(msgs)` **once** with no tool-call loop.
4. Fans out via `pool.run_all(items=top_pages, task=drill_page, role="librarian", ...)`.

**Implication for Phase 37:** Adding `.bind_tools(...)` is necessary but not sufficient. A tool-call loop must be added around the existing `ainvoke` so the librarian can actually invoke the bound graph tools mid-response. The code_reader's loop at `query.py:461-489` is the canonical analog and should be copied/adapted (closure over the `conn` instead of `repo_root`; `ToolMessage` reply pattern is identical).

Loop shape (target):
```
for iteration in range(_LIBRARIAN_MAX_ITERS):
    resp = await librarian_llm.ainvoke(msgs)
    tool_calls = getattr(resp, "tool_calls", None) or []
    if not tool_calls:
        return TaskResult(value=resp.content, response=resp)
    msgs.append(resp)
    for call in tool_calls:
        out = _dispatch_tool(call, conn)  # uses tool funcs bound by build_graph_tools
        msgs.append(ToolMessage(content=out, tool_call_id=call.get("id", "")))
return TaskResult(value="NO_RELEVANT_CONTENT", response=None)  # iter-cap exit
```

`_LIBRARIAN_MAX_ITERS` should mirror `_CODE_READER_MAX_ITERS` (already defined as a module-level constant; planner picks the integer — 5 is the existing precedent).

## 2. CountTokens API: Library Already Exists — Reuse, Don't Rebuild

`packages/wiki-io/src/wiki_io/update_tokens.py:64-76` already exposes:

```python
def count_tokens(text: str, model_id: str = DEFAULT_MODEL_ID, region: str = DEFAULT_REGION) -> int:
    client = boto3.client("bedrock-runtime", region_name=region)
    response = client.count_tokens(
        modelId=model_id,
        input={"converse": {"messages": [{"role": "user", "content": [{"text": text}]}]}},
    )
    return response["inputTokens"]
```

**Critical Bedrock fact (already documented in `update_tokens.py:35-39`):** Claude 4.x models (Haiku 4.5, Sonnet 4.x, Opus 4.x) **do NOT support** the Bedrock CountTokens operation. Claude 3.5 Haiku does. Same-family Anthropic models share a tokenizer, so 3.5-Haiku produces a count that matches Haiku 4.5's tokenization.

`DEFAULT_MODEL_ID = "anthropic.claude-3-5-haiku-20241022-v1:0"` is the right counting model. Do not call CountTokens against the librarian's actual model.

`update_tokens.py:44-61` also defines `_is_unsupported_model_error()` and demonstrates how to map ValidationException → graceful skip. Phase 37's gate must decide what to do when CountTokens itself fails:
- **D-04 says hard abort on overflow.** What about API-call failure? Recommendation: treat CountTokens API errors as "cannot verify budget" and emit a stderr warning + proceed (NOT abort). The alternative — refusing to run if Bedrock CountTokens is transiently down — is operationally worse than running with an unverified budget. Planner picks the policy.

**Token serialization:** CountTokens takes plain text. To estimate tool-schema tokens, the planner needs to serialize the bound-tool list into a deterministic string before counting. Options:
- (a) Call `librarian_llm.bind_tools([...])` then introspect `tool_calls`/`tools` on the bound instance.
- (b) Use `langchain_core.utils.function_calling.convert_to_openai_tool(tool)` on each `@tool` callable to get the JSON schema dict, `json.dumps(...)`, count that text.
- (c) Concatenate each tool's `.name + .description + json.dumps(.args_schema.schema())` for a rough but stable estimate.

Option (b) is closest to what Bedrock actually receives (it converts schemas internally), but the exact wire format Bedrock uses is opaque. Option (c) is the cheapest, most stable estimate. Planner picks; recommend (c) for simplicity — the budget headroom (D-05) absorbs ~10% slop, more than enough to cover serialization differences.

## 3. Librarian Model Context Window (the budget denominator)

`packages/model-adapter/src/model_adapter/models.toml:18` pins the librarian to `us.anthropic.claude-haiku-4-5-20251001-v1:0`. **Anthropic Haiku 4.5 has a 200,000-token context window** (per Anthropic's model card — same as Sonnet 4.x and Opus 4.x in the 4 family).

`max_tokens` in the role config (2048) is the **output** budget. The **input** budget is `context_window - max_tokens`, which is ≈197,952 tokens. Apply D-05's 0.90 fraction → ≈178,156 tokens of input headroom.

**Where the budget number should live:** CONTEXT D-05 prefers `models.toml` per-role override (`librarian_budget_fraction = 0.90` or `librarian_context_window = 200000`). The current `models.toml` keys are `model_id`, `region`, `max_tokens`, `max_concurrency`, `sweep_candidates`. Adding `context_window` and `budget_fraction` is a non-breaking additive change to `load_role_config()` (which just returns the dict; callers must explicitly read the keys with defaults).

Planner choice:
- (A) Add `context_window` + `budget_fraction` to `[roles.librarian]` in `models.toml`. Read via `load_role_config("librarian").get("context_window", 200_000)` and `.get("budget_fraction", 0.90)`.
- (B) Hard-code as module-level constants in `graph_tools.py`: `LIBRARIAN_CONTEXT_WINDOW = 200_000`, `LIBRARIAN_BUDGET_FRACTION = 0.90`.

Recommend (A): it future-proofs the per-role tuning path mentioned in CONTEXT.md's deferred ideas ("Per-role budget headroom values"). (B) is acceptable if the planner wants the smaller diff — `models.toml` then stays untouched in this phase.

## 4. The Six `describe_*` Functions: Argument Shapes

`packages/graph-io/src/graph_io/queries.py` lines 266-497:

| Function | Signature | `identifier` mapping for `cg_describe` |
|---|---|---|
| `describe_package(conn, *, name)` | `(name: str)` | `name=identifier` |
| `describe_path(conn, *, path)` | `(path: str)` | `path=identifier` |
| `describe_repository(conn)` | _no identifier_ | identifier ignored (or required-but-unused; planner picks) |
| `describe_domain(conn, *, name)` | `(name: str)` | `name=identifier` |
| `describe_entry_point(conn, *, name)` | `(name: str)` | `name=identifier` |
| `describe_test_suite(conn, *, name)` | `(name: str)` | `name=identifier` |

**Two gotchas:**

1. **`describe_repository` takes no identifier.** D-10 locks `kind` as an enum that includes `repository`. The tool can either:
   - (a) Accept `identifier` and silently ignore it for `kind="repository"`.
   - (b) Require `identifier` syntactically but document it as "ignored for repository".
   - (c) Make the LLM-facing signature `cg_describe(kind, identifier="")` so `identifier=""` is the conventional value for `repository`.
   Planner picks. Option (a) is the lowest-friction: LLM passes any string, tool ignores it. Document in the docstring.

2. **All `describe_*` functions return `... | None`.** When the entity does not exist, they return `None`, NOT raise. `_format.render([None])` would crash on the dataclass coercion. The tool must check for `None` and return a clean error string: `f"error: no {kind} named {identifier!r} found in graph"`.

## 5. `_format.render()` — Post-Phase-36 Signature (cap kwarg)

Current signature (in main, pre-Phase-36): `render(records: Iterable[Any], fmt: str) -> str`.

Phase 36 plan 36-01 (already written) modifies `_format.py` to add a `cap` parameter (truncates to 50 rows with a notice). Phase 37 plans MUST assume that signature: `render(records, fmt="human", cap=50)`.

**Cross-phase coupling:** Phase 36's `36-01-PLAN.md` already lists `_format.py` in `files_modified` with `provides: "render() with cap parameter for 50-row truncation"` and `contains: "cap"`. Phase 37's plan should:
- Cite Phase 36 as a dependency in `depends_on` (or document the merge-order assumption).
- Call `render(records, fmt="human", cap=50)` everywhere — never re-implement the cap.

If Phase 36 has not merged when Phase 37 starts execution, the executor will see a TypeError on the `cap=` kwarg. The planner should mention this in a Truth/risk note.

**Single-record outputs:** `describe_*` functions return a single dataclass, not a list. `render([single_record], "human", cap=50)` is the canonical wrapping (cap is irrelevant for n=1 but harmless).

**`importer_human` shape:** `_format.py:21-36` shows that `ImporterRecord` lists render differently. `cg_imports` returns `ImportRecord` (not `ImporterRecord`) — verify by reading `_format._is_importer_batch()`'s check (`type(rows[0]).__name__ == "ImporterRecord"`). `ImportRecord` (from `cg_imports`) is the generic fall-through path.

## 6. `read_only_connect()` and `GraphNotInitializedError`

`packages/graph-io/src/graph_io/store.py:68-76`:
```python
def read_only_connect(db_path: Path) -> sqlite3.Connection:
    if not db_path.exists():
        raise GraphNotInitializedError(f"graph DB not found at {db_path}; run `cg update --full` to initialize")
    # ...
```

The exception class is `graph_io.store.GraphNotInitializedError`. The `query.py` code should catch it at command entry and switch to the no-tools path (CONTEXT D-07).

**The full path is:** `workspace_io.paths.graph_dir(workspace) / "code.db"` → resolves to `<workspace>/.graph/code.db`. Confirm via `packages/workspace-io/src/workspace_io/paths.py:31` — `graph_dir(workspace)` returns `Path(workspace) / ".graph"`. The DB filename `code.db` is hard-coded in the graph-io test conftest and `cg update` writes it there.

## 7. Bedrock Tool Schema Translation (the `bind_tools` mechanism)

`langchain_aws.ChatBedrockConverse` exposes `bind_tools(tools: list[BaseTool | dict])`. Internally it converts each `@tool`-decorated callable to Bedrock Converse tool-spec format (a JSON dict with `toolSpec.name`, `toolSpec.description`, `toolSpec.inputSchema.json`). The schema is generated from the function's type hints + docstring.

**Tool-call return shape.** After `bind_tools`, an `AIMessage` returned by `await llm.ainvoke(msgs)` has a `tool_calls` attribute when the model decided to call tools:
```python
resp.tool_calls = [
    {"name": "cg_find", "args": {"name": "SubagentPool"}, "id": "tool_call_001"},
    ...
]
```
The agentic loop must:
1. Append the `AIMessage` itself to `msgs` (preserves the tool_use blocks).
2. For each `call`, invoke the underlying Python function (lookup by `call["name"]`).
3. Append a `ToolMessage(content=<str result>, tool_call_id=call["id"])` for EACH call.
4. Re-invoke `llm.ainvoke(msgs)` and repeat until `tool_calls` is empty (terminal AIMessage with content).

**Dispatch mechanism inside `build_graph_tools`.** The 5 returned `@tool` callables are real Python functions — the loop can either:
- (a) Iterate the returned list and match by `t.name` to dispatch `t.invoke(call.args)`. This delegates dispatch to LangChain's `BaseTool.invoke()` which validates args against the schema.
- (b) Build a `{name: callable}` dict alongside the list and dispatch directly.
Option (a) is preferred — it gets schema validation for free (e.g., if the LLM passes `kind="bogus"` to `cg_describe`, the Pydantic schema rejects it before the function body sees it). Option (b) requires the tool body to do its own validation (which it should do anyway, per D-12).

**`langchain-aws>=1.4.7`.** Per CONTEXT.md final canonical ref + `.planning/STATE.md`, 1.4.6 has a bug where invalid tool_use blocks crash multi-tool fan-outs. 1.4.7 strips invalid blocks. Phase 37 MUST bump `agents/graph-wiki-agent/pyproject.toml` to `langchain-aws>=1.4.7`. The root workspace pin (if any) must follow.

## 8. `graph-io` Dependency — Net-New for `graph-wiki-agent`

`agents/graph-wiki-agent/pyproject.toml` currently lists `wiki-io`, `model-adapter`, `subagent-runtime`, `workspace-io`, `bm25s`, `mcp`, `langchain-aws`, `typer`, `pydantic` — but **NOT** `graph-io`. Phase 37 introduces this dependency:

- Add `"graph-io"` to `dependencies`.
- Add `graph-io = { workspace = true }` to `[tool.uv.sources]`.

After the edit, `uv sync` must succeed before `uv run --package graph-wiki-agent pytest -q` will resolve the new imports. Plan must include this step explicitly (the planner-checker's "every action must be concrete" rule applies).

## 9. Test Strategy

### Existing graph-wiki-agent test patterns

`agents/graph-wiki-agent/tests/unit/test_query_*.py` are the closest existing tests. They:
- Mock or fake the Bedrock LLM via `unittest.mock.AsyncMock` patched onto `ChatBedrockConverse.ainvoke`.
- Patch BM25 / embedding search to return fixed page lists.
- Assert on the structure of the returned `QueryResult`.

### graph-io seeded-DB fixture

`packages/graph-io/tests/conftest.py` defines a session-scoped `seeded_db` fixture that:
1. Copies `tests/fixtures/sample_monorepo` to a tmp dir.
2. Runs `git init` + commits.
3. Calls `graph_io.update.run(repo_root, full=True)` to populate `code.db`.
4. Yields a read-only `sqlite3.Connection`.

**Reuse path:** Phase 37 tests for `build_graph_tools(conn)` and the tool callables should construct a similar fixture (or import the helper directly via `from graph_io.tests._git_repo import ...` if exposed). Since cross-package fixture reuse is awkward, the cleaner pattern is to **mirror the conftest in `agents/graph-wiki-agent/tests/conftest.py` or a new `tests/fixtures/conftest_graph.py`**. The fixture only needs the connection — no librarian, no Bedrock.

### Tests Phase 37 needs

| Surface | Test |
|---|---|
| `build_graph_tools(conn)` returns 5 tools | `len(build_graph_tools(conn)) == 5`; names match `{cg_find, cg_describe, cg_callers, cg_callees, cg_imports}` |
| Each tool returns `str` | `isinstance(tool.invoke({...valid_args...}), str)` for every tool |
| `cg_find` no-args returns error string | `cg_find.invoke({}) == "error: at least one of name, kind, in_package required"` (matches D-12) |
| `cg_describe.kind` enum validation | `cg_describe.invoke({"kind": "bogus", "identifier": "x"})` returns `error: invalid kind 'bogus'; ...` |
| `cg_describe` dispatch to each of 6 functions | parametrized test, kind∈{package,path,repository,domain,entry_point,test_suite} |
| `cg_describe` returns clean error on miss | `cg_describe.invoke({"kind":"package","identifier":"nonexistent"})` returns `error: no package ...` |
| Row cap | feed >50 rows via a fixture; assert truncation notice present |
| CountTokens gate fires on overflow | Mock `count_tokens` to return a huge number; assert non-zero exit + stderr message (D-04) |
| CountTokens gate passes on small inputs | Real-ish path; assert no exception, librarian fan-out proceeds |
| NOT_INITIALIZED fallback (D-07) | Pass a workspace with no `.graph/code.db`; assert librarian runs with NO tools + stderr line emitted exactly once + system prompt has addendum |
| Connection lifetime (D-03/LIBTOOLS-03) | Open conn at command entry; mock librarian to record the conn id seen by each tool call; assert all calls share the same conn object; assert `conn.close()` called in `finally` |
| Tool-call loop iter cap | Mock librarian to return `tool_calls` forever; assert loop terminates at `_LIBRARIAN_MAX_ITERS` |
| End-to-end smoke (integration-marked) | Real Bedrock call against the seeded DB; one of the librarian's drills calls at least one graph tool; marked `@pytest.mark.integration` (skipped in CI per existing convention) |

### Snapshot tests for tool docstrings (optional)

Per D-03 (concise docstrings, budget-conscious), a `syrupy` snapshot of each tool's schema (`@tool`'s generated `args_schema.schema()` JSON) is a cheap regression guard against docstring drift expanding the token footprint. Optional — planner picks.

## 10. NOT_INITIALIZED Fallback: Wiring Specifics

Where the catch happens (CONTEXT D-07/D-08):

```python
# commands/query.py — inside run_query, before pool.run_all
db_path = graph_dir(wiki) / "code.db"
graph_tools: list = []
addendum = ""
conn = None
try:
    try:
        conn = read_only_connect(db_path)
    except GraphNotInitializedError:
        sys.stderr.write("[graph unavailable: run 'cg update' to enable code-graph grounding tools]\n")
        addendum = "\nNOTE: code graph tools are unavailable in this workspace; rely on vault excerpts only."
        # graph_tools stays []
    else:
        graph_tools = build_graph_tools(conn)

    # CountTokens gate (D-06) — runs in BOTH paths (the tool list may be empty)
    # ...

    librarian_llm = librarian_llm.bind_tools(graph_tools) if graph_tools else librarian_llm
    # ... fan-out
finally:
    if conn is not None:
        conn.close()
```

**Important: the stderr line emits exactly once per `run_query`,** before any subagent fan-out begins. CONTEXT D-08 is explicit: "emit ... exactly once."

**Where the prompt addendum is concatenated.** Inside `drill_page`:
```python
msgs = [
    SystemMessage(content=LIBRARIAN_SYSTEM + addendum),  # addendum is "" in normal path
    HumanMessage(content=...),
]
```
The `addendum` variable is closed over from the outer scope. No edit to `prompts/librarian.py`. No second prompt file.

## 11. Exit Code for BUDGET_EXCEEDED (D-04)

`graph_wiki_agent`'s existing exit-code surface: `cli.py` raises Typer-style `typer.Exit(code=N)` in a few places (look for them when planning). Convention so far: 1 = general error, 2 = CLI usage / argparse-style. A reasonable choice for budget exceeded:
- **`exit_code = 3`** — distinct from generic error / usage error; greppable in logs/tests.
- Define `BUDGET_EXCEEDED_EXIT_CODE = 3` near the top of `commands/query.py` (or in a new `constants.py` if the planner wants to centralize).

The stderr message format from D-04:
```
librarian: token budget exceeded (X of Y tokens). Reduce vault scope or use a larger-context model.
```
Where X is the measured count and Y is the configured budget (=`int(context_window * budget_fraction)`).

## 12. Repository / cross-cutting / domain-specific gotchas

- **`workspace_io.config.resolve()` semantics.** `commands/query.py` already calls `resolve_wiki_and_repo(workspace_path)` (see `query.py:850`). This returns `(wiki_path, _)` — the wiki dir, not the workspace root. The workspace root needed for `graph_dir()` is one level up (typically). Trace through `_workspace.py` to confirm which Path `graph_dir` should receive. The simplest safe choice: pass `wiki.parent` (since `wiki = workspace / "wiki"` by convention) OR explicitly call `resolve()` and use `.workspace`. Planner picks; recommend resolving the workspace once at top of `run_query` and threading both `wiki` and `workspace` downward.

- **Phase 35 in flight.** STATE.md notes Phase 35 is executing in parallel. Phase 35 touches `cli.py` and `commands/init.py` — files NOT in Phase 37's scope. No file overlap. Phase 37 must NOT edit those files.

- **Phase 36 ordering.** Phase 36 must merge before Phase 37 execution. `find()`'s `in_package` arg and `_format.render(cap=...)` are both Phase 36 deliverables that Phase 37 consumes verbatim. If a planner produces a Wave 1 plan that runs before Phase 36 merges, the plan must explicitly state the dependency in its `depends_on` frontmatter and in `must_haves.truths` ("Phase 36 must be merged on this branch before this plan is executed").

- **`SubagentPool` trace records.** `pool.run_all(...)` writes per-task JSONL traces under `wiki/.graph-wiki/traces/`. Tool calls inside the agentic loop will surface in `usage_metadata` per Phase 9. No schema change needed; the existing trace pipeline captures multi-iteration token usage by summing across the `AIMessage` chain.

## 13. Validation Architecture (Nyquist)

Validation requirements for VALIDATION.md (per `gsd-phase-researcher` convention):

| Dimension | Requirement |
|---|---|
| **Behavior** | Each of the 5 tools is invocable via `BaseTool.invoke(...)` against a seeded `code.db` and returns a non-empty string for valid args. |
| **Boundary** | (a) `cg_find` with no args returns error string (not raises). (b) `cg_describe` with bogus `kind` returns error string. (c) `cg_describe` on a non-existent identifier returns `"error: no <kind> named ..."`. (d) Row cap kicks in at 51 rows with truncation notice. |
| **Identity** | `build_graph_tools(conn)` returns exactly 5 tools; names are `{cg_find, cg_describe, cg_callers, cg_callees, cg_imports}` (no extras, no renames). |
| **Wiring** | `commands/query.py` opens ONE conn at command entry, passes it into `build_graph_tools(conn)`, calls `.bind_tools(...)`, fans out, and closes the conn in `finally`. No per-tool-call connection open (Pitfall 4). |
| **Fallback** | When `graph_dir(workspace) / "code.db"` is absent, the librarian still runs; the stderr line is emitted exactly once; the system prompt receives the addendum; the librarian is given NO bound tools. |
| **Budget** | CountTokens gate runs at command entry; on overflow, process exits non-zero with the exact D-04 stderr line. On underflow, fan-out proceeds normally. |
| **Multiplex** | `cg_describe.kind` accepts {package, path, repository, domain, entry_point, test_suite} exactly; every other string returns the D-10 error format. Each kind dispatches to the correct `describe_*` function. |
| **Strings-only** | Every tool returns `str` for every code path (success + error). No `None`, no raises crossing the tool boundary. |
| **Concurrency** | The shared `conn` is read-only (`mode=ro`) and SQLite read-only connections are safe for concurrent reads across asyncio fan-out within a single process — no per-tool lock required. Confirmed by `read_only_connect()`'s URI suffix in `store.py`. |
| **Trace** | Multi-iteration tool calls surface in `pool.run_all` trace records via `usage_metadata` accumulation (Phase 9 contract). No new trace schema needed in this phase. |

## 14. Open Questions / Planner's Discretion (re-statement, with research data attached)

These are the items CONTEXT.md left for the planner. Research data is attached so the planner can pick with grounding.

1. **`librarian_budget_fraction`** — D-05 suggests 0.90. Research §3 above gives context window = 200,000 and output = 2048, so input budget = 200_000 - 2048 = 197_952. `0.90 * 197_952 = 178_156` tokens. This is plenty (current librarian inputs run 6-15K tokens per drill on typical pages). 0.90 is fine.

2. **`BUDGET_EXCEEDED` exit code** — Recommend `3` (Research §11).

3. **Where the budget constants live** — Recommend `models.toml` per-role (Research §3 option A) for tunability; module constants (option B) acceptable for smaller diff.

4. **Dispatch style for `cg_describe`** — Module-level `_DESCRIBE_DISPATCH = {"package": queries.describe_package, ...}` is the consensus pattern in this codebase (grep'able, extensible). Recommend over `match`/elif.

5. **Tool return type for the factory** — `list[BaseTool]` (Research §7 dispatch option A). The librarian fan-out site calls `.bind_tools(graph_tools)` directly; iteration is unnecessary at the call site.

6. **Docstring source for the 5 tools** — Recommend reusing Phase 36's argparse `help=` strings verbatim where they overlap (`cg find`, `cg describe-*`, `cg callers/callees/imports`). Keeps the librarian's mental model aligned with the CLI text the user sees in `cg --help`.

7. **`describe_repository` identifier slot** — Recommend ignore-with-docstring-note (Research §4 option a). Cheapest LLM ergonomics; the schema can still require a string for symmetry.

8. **`_LIBRARIAN_MAX_ITERS`** — Mirror `_CODE_READER_MAX_ITERS` (5). Per-page drills with ≤5 tool calls is a generous ceiling; most librarian drills will terminate in 1-2 iterations.

## 15. Risk Register

| Risk | Likelihood | Mitigation |
|---|---|---|
| Phase 36 not merged → `_format.render(cap=...)` TypeError | medium (Phase 36 already planned but not executed) | Plan declares dependency in `depends_on` + `must_haves.truths`; executor checks before running |
| Phase 35 in-flight touches the same files | low (CONTEXT explicitly excludes `cli.py`/`init.py`) | Plan does not modify `cli.py` or `commands/init.py` |
| `langchain-aws<1.4.7` strips-invalid-tool_use bug bites with 5 tools bound | high if not bumped | Pin in `pyproject.toml`, `uv sync`, run smoke tests |
| Bedrock CountTokens API transient failure aborts every librarian run | medium | Treat CountTokens API errors as "cannot verify" → warn + proceed; reserve hard-abort for budget-exceeded (the actual overflow signal) |
| LLM exceeds 5 tool-call iterations and produces no terminal content | low (default depth in tools is 3; cap is hit only on pathological inputs) | Iteration cap returns `NO_RELEVANT_CONTENT` (sentinel that already short-circuits the fan-out useful-excerpt check at `query.py:921-926`) |
| Tool-call schema serialization drift between LangChain versions breaks budget estimate | low | Budget headroom is 10% of 200k = 20k tokens; schema serialization for 5 small tools fits in ~3k tokens of slop |
| Connection closed mid-loop by exception in `drill_page` | low (asyncio gather rolls up exceptions) | The `try/finally` in `run_query` closes the conn after the pool returns, not during; per-task exceptions don't touch the conn |
| Tool calls hammering SQLite from 5 concurrent librarians | low | SQLite read-only URIs (`mode=ro`) explicitly support concurrent readers; no write contention |

## 16. Files the Planner Will Touch

**Net-new:**
- `agents/graph-wiki-agent/src/graph_wiki_agent/graph_tools.py` (the factory + 5 tools + dispatch table)
- `agents/graph-wiki-agent/tests/unit/test_graph_tools.py` (tool surface + dispatch + cap)
- `agents/graph-wiki-agent/tests/unit/test_query_graph_tools_wiring.py` (CountTokens gate + NOT_INITIALIZED fallback + conn lifetime; covers `commands/query.py` integration)

**Modified:**
- `agents/graph-wiki-agent/src/graph_wiki_agent/commands/query.py` (open conn, gate, bind tools, fallback, agentic loop in `drill_page`)
- `agents/graph-wiki-agent/pyproject.toml` (add `graph-io` dep + workspace source; bump `langchain-aws>=1.4.7`)

**Unchanged (read-only references):**
- `agents/graph-wiki-agent/src/graph_wiki_agent/prompts/librarian.py` (addendum is concatenated at runtime, not edited into the file)
- `packages/graph-io/src/graph_io/queries.py` (Phase 36 adds `in_package`; Phase 37 only calls)
- `packages/graph-io/src/graph_io/cli/_format.py` (Phase 36 adds `cap`; Phase 37 only calls)
- `packages/wiki-io/src/wiki_io/update_tokens.py` (reused as-is)

## 17. Wave Layout Recommendation

This phase is small enough to fit in 1-2 plans. Recommended split:

- **Plan 37-01 (Wave 1, autonomous):** Create `graph_tools.py` with `build_graph_tools(conn)` and the 5 tools + tests against a seeded fixture DB. Bump `langchain-aws` and add `graph-io` dependency. No edits to `commands/query.py` yet — this plan delivers a unit-tested, importable factory.

- **Plan 37-02 (Wave 2, depends on 37-01, autonomous):** Wire `build_graph_tools` into `commands/query.py`: open conn, run CountTokens gate, bind tools, add tool-call loop in `drill_page`, NOT_INITIALIZED fallback, stderr line, prompt addendum, integration tests for the wiring.

The wave split keeps the factory testable in isolation before adding the query.py integration complexity. Optional collapse to 1 plan if the planner judges the scope manageable; the agent-skills planner prompt allows that.

---

*Phase: 37-librarian-grounding-tools*
*Research completed: 2026-05-26*
