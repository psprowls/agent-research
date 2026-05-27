# Domain Pitfalls — v1.7 graph-io Integration & Wiki Hygiene

**Domain:** Wiring a structured graph store into an LLM agent (graph-io → graph-wiki-agent integration) + CLI ergonomics + bulk hygiene
**Researched:** 2026-05-26
**Confidence:** HIGH — grounded entirely in the existing codebase (query.py, cli/main.py, queries.py, q_find.py, RETROSPECTIVE.md, quick-plan transcripts)

---

## Critical Pitfalls

### Pitfall 1: Over-Exposed @tool Surface Degrades Librarian Routing

**What goes wrong:**
The graph-io `queries.py` module supports ~15 distinct query shapes (find, callers, callees, imports, imported-by, exports, exported-by, describe-package, describe-path, describe-repo, list-packages, list-entry-points, list-suites, what-tests, list-domains, describe-domain, domain-refs, domain-deps, cross-cutting). The temptation is to expose each as its own `@tool` callable. Bedrock Converse (Claude models via `ChatBedrockConverse`) exhibits measurable degradation in tool selection quality above ~10 tools in a single call. With 15+ narrow tools, the librarian wastes turns routing through the wrong tool before finding the right one, and tool descriptions bleed into each other (every "describe-X" looks similar to the model). This is a known pattern in LangChain tool-binding literature and from the existing `code_reader` pattern in `query.py`.

**Why it happens:**
The natural implementation instinct is 1-to-1 mapping: one `cg` subcommand → one `@tool`. Each tool has a small, accurate docstring. But narrow tools create a routing problem: the LLM must pick from a menu that grows linearly, and with graph-io's lexicon (`domain`, `package`, `repository`, `entry_point`, `test_suite`) the discriminating words are few and close together.

**WARNING SIGN:** The librarian makes 2+ tool calls per query where each retrieves slightly different graph data. Or the librarian calls `describe_package` when it should have called `list_packages` first. Or tool call logs show repeated `find` + `describe_package` combos on every query regardless of question type.

**PREVENTION:**
Organize graph-io tools into 4-6 "broader" callables grouped by concern, not by `cg` subcommand:

```python
@tool
def graph_find_symbol(name: str, kind: str | None = None) -> str:
    """Find nodes in the code graph by name and optional kind.
    Returns URI, path, and key attributes. kind can be: function, class,
    file, package, domain, entry_point, test_suite."""
    ...

@tool
def graph_describe(uri: str) -> str:
    """Get full details for any graph node by its URI.
    Works for any node kind: package, domain, file, entry_point, test_suite."""
    ...

@tool
def graph_edges(uri: str, direction: str, edge_kind: str | None = None) -> str:
    """Traverse edges from a node. direction: 'out' or 'in'.
    edge_kind filters to: calls, imports, physically_contains, belongs_to_domain,
    implements, tests."""
    ...

@tool
def graph_list(kind: str, filter: str | None = None) -> str:
    """List all nodes of a given kind, optionally filtered by name substring.
    kind: package | domain | entry_point | test_suite | repository."""
    ...
```

The existing `read_file` tool in `query.py` is the right model — one tool, descriptive docstring, broad enough to subsume multiple query patterns. Keep the total librarian graph-tool count at or below 5.

**WHICH PHASE:** Phase covering "Librarian grounding tools" (the first integration phase). Design the tool surface before writing any implementation. If the tool count exceeds 6, split is required before proceeding.

---

### Pitfall 2: graph-io Returns Hundreds of Rows — LLM Context Overflow and Token Cost

**What goes wrong:**
`queries.list_packages` on this monorepo (7 workspace members) returns a small result, but the same call on a user's real repo might return 40+ packages with full `NodeRecord` attributes. `queries.find("main")` with `kind=None` can return dozens of matches (every function, method, and script named `main` in the entire graph). If the `@tool` callable serializes the full `NodeRecord` list to JSON and returns it in a `ToolMessage`, the librarian's context grows unboundedly. On Bedrock Converse, `ToolMessage.content` is treated as opaque text — there is no streaming or pagination at the protocol level. A single tool call returning 400 rows × 300 bytes each = 120KB of ToolMessage content, which: (a) blows the librarian's `max_tokens` allocation, (b) costs significantly more than the query itself, and (c) produces a context window where the LLM cannot meaningfully reason over the data.

The existing pattern in `query.py` already handles this for page content via the `24000` char truncation guard and `60000` excerpt cap — but those are vault page guardrails, not graph-io query guardrails.

**Why it happens:**
`queries.py` returns Python dataclasses. The natural serialization path is `json.dumps([dataclasses.asdict(r) for r in records])`. This is correct for the `cg` CLI (human-readable output) but destructive in an LLM tool context because it reveals implementation details (internal IDs, raw `attrs_json` fields, `line: null` for 80% of rows) that the model does not need and cannot filter.

**WARNING SIGN:** Tool call response logging shows `ToolMessage.content` exceeding 8000 characters. Or librarian traces show high `tokens_in` values (>3000) for a single tool-call round-trip on a list query. Or the librarian hallucinates node attributes that were not in the summary but were in the raw data (meaning it read the raw dump and partially misremembered).

**PREVENTION — four-level strategy:**

1. **Return summaries by default, not full records.** For list queries, return `name: str, uri: str, kind: str` triples only. For describe queries, return only human-salient fields (name, uri, path, key attrs). Strip internal IDs, sqlite rowids, attrs_json blobs.

2. **Hard cap at 50 rows.** Any `@tool` callable that calls a list query must cap the result at `MAX_ROWS = 50` and append a `"[X more results — narrow the query with a kind or name filter]"` suffix if truncated.

3. **Return plain text, not JSON.** The `_format.render(records, fmt="human")` function already exists in `graph_io.cli._format`. Use it. Plain prose summaries are more LLM-friendly than JSON on Bedrock Converse. Return format example:
   ```
   package  auth-service  pkg:org/repo/auth-service  packages/auth/
   package  billing       pkg:org/repo/billing         packages/billing/
   [3 more — use graph_describe(uri) for details]
   ```

4. **Use `fmt="json"` only when the caller explicitly needs machine-parseable URIs.** The URI is the only field the librarian needs to identify a node — once it has the URI it calls `graph_describe(uri)` for details. This naturally prevents one fat tool call from returning everything.

**WHICH PHASE:** Same phase as Pitfall 1. This is a co-design constraint — the tool surface and the return format must be decided together before writing any implementation.

---

### Pitfall 3: ToolMessage.content Format — Bedrock Converse Rejects Non-String Content

**What goes wrong:**
LangChain's `ToolMessage` accepts `content: str | list`. When a `@tool` callable returns a Python dict or list, LangChain's `ChatBedrockConverse` serializes it differently depending on the `langchain-aws` version. In `langchain-aws ≥ 1.4` (current: 1.4.6), returning a `dict` from a `@tool` callable causes the Converse API to receive `toolResult.content` as a JSON blob string — which is valid. However, returning a Pydantic model instance causes `ToolMessage.content` to serialize as the model's `__str__` representation (the human-readable form), not as structured JSON. This is inconsistent behavior that was introduced with the Converse API's `toolResult` shape.

The existing `read_file` tool in `query.py` avoids this by always returning `str`. That is the safe contract.

**Why it happens:**
The `@tool` decorator in `langchain_core` infers the return type from the function annotation. If the annotation is `-> list[NodeRecord]`, LangChain tries to serialize it via its `_stringify` helper, which may call `str()` on a dataclass rather than `json.dumps(dataclasses.asdict(...))`.

**WARNING SIGN:** Bedrock raises `ValidationException: Malformed input...` or `InvalidRequestException` on the tool-use response. Or the model receives garbled content like `NodeRecord(kind='package', name='auth-service', ...)` as a literal string when it expected field-value data.

**PREVENTION:**
All `@tool` callables for graph-io must have explicit `-> str` return type annotations and must convert all graph-io records to plain text before returning. The tool callable owns the serialization; it must never return a dataclass, Pydantic model, or list thereof.

```python
@tool
def graph_find_symbol(name: str, kind: str | None = None) -> str:
    """..."""
    records = queries.find(conn, name=name, kind=kind)
    if not records:
        return "No results found."
    lines = [f"{r.kind}  {r.name}  {r.attrs.get('uri', '?')}  {r.path or '?'}"
             for r in records[:50]]
    if len(records) > 50:
        lines.append(f"[{len(records) - 50} more — narrow your query]")
    return "\n".join(lines)
```

This pattern mirrors `read_file`'s `return str` contract exactly and avoids the serialization ambiguity.

**WHICH PHASE:** First integration phase. Lock return type in the `@tool` wrapper layer before any tool is bound to the librarian LLM.

---

### Pitfall 4: URI Identity Drift — graph-io Rebuild Mid-Agent-Run Invalidates Librarian's URIs

**What goes wrong:**
The librarian fan-out in `run_query` runs `SubagentPool.run_all` over `top_pages` — this takes several seconds with 5 concurrent librarian calls. If the user (or a concurrent process) runs `cg update --full` during that window, the graph DB is rebuilt with a fresh SQLite file (write-lock during rebuild, then atomic rename). After `--full`, all `Repository` and `SubPackage` nodes get new sqlite `id` values (autoincrement resets). But the `uri` TEXT column is stable across rebuilds — `pkg:org/repo/auth-service` stays `pkg:org/repo/auth-service`. So URIs as identity strings are rebuild-safe.

**However:** the scanner consuming graph-io in v1.7 runs a separate process from the librarian. The scanner calls `cg update` (incremental) to ensure the graph is fresh before scanning. If the scanner's `cg update` runs while a librarian fan-out is in progress (both called from `run_scan` + `run_query` in rapid succession), the SQLite write lock (`GRAPH_WIKI_LOCK_TIMEOUT_MS` controls this) causes the librarian's graph queries to either block or fail with a lock timeout error.

A subtler form: the librarian holds a `conn = store.read_only_connect(db)` for the duration of the tool call. If `--full` runs concurrently, the rebuild creates a new `code.db` via a temp file + atomic rename. The librarian's open connection is on the *old* inode — it continues to read stale data without error. The page the librarian just grounded via `pkg:org/repo/auth-service` may refer to nodes that no longer exist in the new DB. The librarian's tool calls succeed but are answering from pre-rebuild data.

**Why it happens:**
SQLite WAL mode supports concurrent readers with one writer. But `cg update --full` uses `store.connect(create=True)` which drops and recreates tables — not a WAL write. The lock pattern is: exclusive lock for DDL operations, then release. Readers in WAL mode on the old checkpoint can continue reading the old snapshot; they are not notified that a rebuild occurred.

**WARNING SIGN:** Librarian produces a tool call result with a URI like `pkg:org/repo/old-service` that does not exist in the current graph (the package was renamed between scan and query). Or scan + query pipeline reports a "graph last updated 2 runs ago" warning because the scanner's `cg update` call was blocked by a lock timeout mid-fan-out.

**PREVENTION:**

1. **Single-writer contract:** the `graph-wiki-agent` commands must serialize graph updates. `run_scan` and `run_ingest` should be the only commands that call `cg update`. `run_query` must be read-only. The scan command acquires the graph lock, runs the update, releases it. Query commands use `store.read_only_connect()` exclusively.

2. **Open graph connection once per command, not per tool call.** The `@tool` callable must close over a single read-only `conn` opened at command entry. Do not open and close the connection on each tool invocation — this creates a window where the DB can be swapped between calls. Closing over a single conn ensures the librarian reads a consistent snapshot for the duration of its fan-out.

3. **URI stability is the correct identity layer.** Do not use sqlite `id` integers in any tool return value. Only return `uri` strings. Then if a full rebuild occurs between a tool call and the agent's next action, the URI-keyed data is still meaningful.

**WHICH PHASE:** Integration phase for scanner + librarian. The connection-lifetime and write-lock contract must be documented as part of the integration design, not retrofitted after the fact.

---

### Pitfall 5: `cg find` Positional Argument — `args.name` Is Currently `parser.add_argument("name")` (Positional)

**What goes wrong:**
The current `q_find.py` uses `parser.add_argument("name")` — a positional argument. All callers (both `cg find foo.py` and any internal test callsites) pass `name` as `argv[1]`. The v1.7 milestone's "parser ergonomics" goal is to make `cg find` support `--name foo.py --kind file` (named flags), presumably to improve shell quoting and to mirror the rest of the `cg` command surface (all other commands use named flags for their primary arguments).

If a new `--name` flag is added alongside the positional, both syntaxes parse — but `argparse` will reject invocations that provide both. If the positional is removed, `cg find foo.py --kind file` (the current form) silently breaks — `foo.py` becomes an unrecognized argument.

Single-user repo means there is no backwards-compat obligation beyond fixing internal callers. The risk is not user breakage — it is that internal test callsites (any test that calls `q_find.run(args)` with `args.name = "foo"` constructed by the test fixture) break silently because the test fixtures bypass the parser entirely.

**Why it happens:**
Tests that call `run(args)` directly by constructing an `argparse.Namespace` object (`args = argparse.Namespace(name="foo.py", kind="file", workspace=..., fmt="human")`) will not break — they bypass the parser. But tests that call `main(["find", "foo.py", "--kind", "file"])` will break when the positional is removed. The break is not silent if the test asserts a specific return code, but if a test only asserts the return type and not the exit code, it may hide the failure.

**WARNING SIGN:** `cg find foo.py --kind file` returns exit 2 (argparse error) after the positional is removed. Or test suite shows 0 new failures after the change (meaning no tests called `main(["find", "foo.py"])` directly — good, but it does not prove no regressions).

**PREVENTION:**
Single-commit break-and-fix:
1. Change `parser.add_argument("name")` to `parser.add_argument("--name", required=True)` in `q_find.py`.
2. Grep for all internal callers: `grep -rn '"find"' packages/graph-io/tests/`. Update any `main(["find", "foo.py"])` to `main(["find", "--name", "foo.py"])`.
3. Add a smoke test: `main(["find", "--name", "SubagentPool", "--kind", "class"])` → exit 0 or exit 1 (not-found), not exit 2 (argparse parse error).
4. The old positional form `cg find foo.py` must produce a clear parse error, not silent wrong behavior.

Single-user project: document the breaking change in the phase SUMMARY.md but do not create a migration alias.

**WHICH PHASE:** The dedicated `cg find` ergonomics phase (or folded into hygiene). Change in one commit, test update in the same commit. Do not split across phases.

---

### Pitfall 6: `graph-wiki-agent graph` Subcommand vs `cg` CLI — Feature Drift Between Two Surfaces

**What goes wrong:**
v1.7 adds a `graph-wiki-agent graph build|describe|query` subcommand. This surface mirrors `cg update|describe-*|find` but adds agent-aware features (cost tracking, model selection, trace output). Within 2 milestones, the two CLIs diverge: `cg describe-domain` gains a new `--with-deps` flag; `graph-wiki-agent graph describe` does not get it. Users ask "why does `cg` support X but `graph-wiki-agent graph` doesn't?" — two maintenance surfaces for the same underlying data.

The v1.2 retrospective explicitly warns about this pattern: "avoid parallel surfaces over the same helpers that drift." The `wiki_io` / `workspace_io` / `graph_io` layer should be called by both CLIs, but the agent CLI must not re-implement graph-io query logic.

**Why it happens:**
`graph-wiki-agent graph` is built by an LLM following a spec that says "mirror `cg` patterns." Without an explicit constraint, the implementer adds convenience flags that seem natural at implementation time and are not in `cg`. Each addition is small; the cumulative drift is the problem.

**WARNING SIGN:** Phase SUMMARY for the `graph` subcommand shows more than 3 flags per subcommand that do not have a direct equivalent in `graph_io.cli`. Or `graph-wiki-agent graph query` does something `cg` does not (e.g., returns formatted markdown instead of plain text). Or a future phase touches both `cg` and `graph-wiki-agent graph` to add the same feature.

**PREVENTION:**
`graph-wiki-agent graph` must be a thin wrapper: it calls `graph_io.cli.main([...])` internally or calls the same `graph_io.queries.*` functions that `cg` calls, with exactly the same argument semantics. No new flags that are not in `cg`. The only additions allowed are: `--trace` (to write a cost trace), `--model` (to specify the Bedrock model for the `query` subcommand's LLM reasoning step). Document this constraint in the phase plan as a hard constraint.

**WHICH PHASE:** `graph-wiki-agent graph` subcommand phase. Enforce at plan-writing time, not at code-review time.

---

## Moderate Pitfalls

### Pitfall 7: Hygiene Phase — 10+ Small Touches on Overlapping Files Creates Ordering Regressions

**What goes wrong:**
The hygiene phase touches at least 10 separate items (`hfr`, `i26`, `he3`, `i35`, `iws`, `kxi`, `ans`, `gc0`, `lj3`, `mfm`, bootstrap interactive flag, bootstrap stub categories). Several of these touch the same files:
- `hfr` (scanner wikilink prefix) + `he3` (file-map format) both touch `commands/scan.py`
- `i26` ({{CONTAINER_DIR}} template var) + `iws` (overview page renames) both touch wiki-io templates
- `mfm` (uv re-exec bootstrap) + bootstrap interactive flag both touch plugin scripts

If the hygiene plans are executed as separate parallel worktree commits (as was done for v1.2 Phase 12 brand sweep), changes to the same file in different plans will produce merge conflicts. If executed sequentially without careful ordering, an earlier fix can be silently reverted by a later fix to the same file (the "undo" anti-pattern from v1.2 Phase 16 code review: "a code review that produces issues without a fix plan is review-as-documentation, not review-as-gate").

**Why it happens:**
The hygiene items are logically independent but physically overlapping. When a plan writer assigns items to separate plans without checking which files each item touches, merge conflicts or silent reversions are the natural outcome.

**WARNING SIGN:** Phase plan for hygiene shows any two items touching the same file in different plan waves without an explicit "Plan B depends on Plan A complete" dependency edge. Or the phase verification shows test failures in scan-related tests after the `iws` plan ran — which touched the scanner's template output expectations.

**PREVENTION:**
1. Before writing any plan, produce a file-touch matrix: `item × file`. Items that share any file must be in the same plan or must be in sequentially-ordered plans with an explicit dependency.
2. Execute hygiene plans in a single wave (one plan per logical file cluster), not as parallel worktrees. The v1.2 brand sweep worked in parallel because each sweep wave touched disjoint file sets. The hygiene items here do not have disjoint file sets.
3. Run the full test suite after each plan — not just the tests for the affected subsystem. Hygiene items often change output formats that affect snapshot tests in other subsystems.

**WHICH PHASE:** Hygiene phase planning step. The file-touch matrix must be produced before any plan is assigned a wave number.

---

### Pitfall 8: Hygiene Phase — wiki-io Template Changes Break Plugin Without a Verification Path

**What goes wrong:**
The hygiene items `hfr` (scanner wikilink prefix), `i26` ({{CONTAINER_DIR}} template variable), `he3` (file-map format), `i35` (testing.md subpage), and `iws` (overview page renames) all touch `wiki-io` template output that the `plugins/graph-wiki/` plugin consumes via its shim scripts. The plugin calls wiki-io via `uv run --project ...` and parses the output in its Claude Code SKILL.md prompts (which reference field names like `## File map` and `## Overview`). If a hygiene item renames or reformats these outputs without updating the plugin's SKILL.md content and prompts, the plugin silently starts producing wrong output.

The constraint from v1.2 (Phase 13 CONTRACT-INDEX.md): the plugin runs on Claude Code inference and is NOT a wrapper around `graph-wiki-agent`. wiki-io changes that affect the plugin's input format are the plugin's responsibility to track — but there is no automated CI gate for this. The Phase 14 SC#4 plugin smoke transcript was never captured (carried since v1.2 close — see MILESTONES.md).

**Why it happens:**
Wiki-io templates are Python string constants that produce structured markdown. The plugin's SKILL.md prompts reference these structures by section name. There is no schema contract between the two — it is a convention enforced only by manual smoke tests.

**WARNING SIGN:** After hygiene, running the plugin's `/graph-wiki:scan` command produces pages where the `## File map` section is missing or has changed structure. The test `test_layout_io.py` passes (because layout_io round-trips correctly), but the *contents* that layout_io preserves are wrong because the generator changed.

**PREVENTION:**
1. Before touching any wiki-io template, run a manual smoke test against the actual `~/Personal/graph-wiki/agent-research` vault: `graph-wiki-agent scan --workspace ~/Personal/graph-wiki/agent-research`. Capture a before-sample of any page that will be affected.
2. After the hygiene item, run the same command and diff the output against the before-sample. Only accept the change if the diff is exactly the intended change.
3. The Phase 14 SC#4 missing smoke transcript must be captured at the end of the hygiene phase. This is the regression baseline for the plugin's end-to-end happy path.

**WHICH PHASE:** Hygiene phase. Each wiki-io template touch must include a "before/after scan sample" verification step. Do not accept "tests pass" as sufficient — the plugin's Claude Code inference is outside CI.

---

### Pitfall 9: `ans` ANSI Fix — `CliRunner` vs `subprocess.run` vs `NO_COLOR` Env

**What goes wrong:**
The `260521-ans` PLAN already chose a specific mitigation: `NO_COLOR=1`, `TERM=dumb`, `COLUMNS=200` passed to every `subprocess.run([..., "--help"])` call. This is the right decision (per the plan's "Why not a different fix?" section). The risk at execution time is that the implementer uses `typer.testing.CliRunner` instead of `subprocess.run`, which has a different ANSI behavior.

`CliRunner` from Click/Typer invokes the app in-process. It respects `mix_stderr=False` and has its own `color` argument. However, Rich's ANSI output is driven by the TTY detection, not solely by Typer's runner. `CliRunner` with `mix_stderr=False` still allows Rich to emit ANSI codes if the `TERM` environment is not controlled. The result: using `CliRunner` without env overrides still produces ANSI-bearing output that breaks word-boundary regexes.

The `NO_COLOR=1` env var approach (chosen in the plan) is the only approach that works for both subprocess and in-process invocations because Rich respects the `no-color.org` convention at its initialization stage.

**Why it happens:**
A developer fixing the 5 failing tests opens the test files, sees `subprocess.run`, thinks "I can simplify this with CliRunner" (it does not spawn a subprocess), and switches to CliRunner without setting `env={"NO_COLOR": "1"}`. The tests still fail because Rich still emits ANSI in CliRunner mode without the env override.

**WARNING SIGN:** After the fix, 3 of 5 tests pass but 2 still fail. Or the fix introduces `CliRunner` but does not set `color=False` and the env override.

**PREVENTION:**
The `260521-ans` PLAN is already written correctly. Execute it as written:
- `NO_COLOR=1` + `TERM=dumb` + `COLUMNS=200` in `env={**os.environ, ...}` passed to every `subprocess.run` call.
- Do NOT switch to `CliRunner` — the plan explicitly ruled this out.
- Verify: 5 specific tests listed in the plan pass, snapshot count unchanged.

**WHICH PHASE:** Hygiene phase (this is quick-task `260521-ans`). Execute as the pre-written plan specifies. No deviation.

---

### Pitfall 10: `mfm` Bootstrap Self-Healing uv Re-Exec — Loop Prevention and env Hygiene

**What goes wrong:**
The `260521-mfm` PLAN implements a `GRAPH_WIKI_SHIM_REEXEC` guard to prevent infinite re-exec loops. Three failure modes not covered by the plan's verification steps:

1. **`uv` not on PATH for the re-exec environment.** `os.execvpe("uv", [...], new_env)` uses the env dict passed to it — which is `{**os.environ, "GRAPH_WIKI_SHIM_REEXEC": "1"}`. If the user's PATH is in `os.environ`, `uv` is findable. But if the script is called from a subprocess where PATH is stripped (e.g., from a CI runner that sets a minimal env), `os.execvpe` raises `FileNotFoundError: [Errno 2] No such file or directory: 'uv'`. The plan says "if uv is not on PATH, the OSError will surface with a clear message" — which is acceptable behavior, but the error message will say `[Errno 2] No such file or directory` without context about what failed.

2. **Walk-up search finds the wrong `packages/wiki-io/pyproject.toml`.** If the script is invoked from a different repo that also happens to have a `packages/wiki-io/` directory in its parent tree (unlikely but possible in nested workspace setups), the walk-up finds the wrong project. The re-exec then uses the wrong `wiki_io` installation, and the import succeeds but produces wrong behavior without any error.

3. **`sys.argv[0]` is not an absolute path.** When a shim is invoked as `python detect_containers.py` (relative path) from a different working directory, `sys.argv[0]` is `"detect_containers.py"` — a relative path. The re-exec calls `os.execvpe("uv", ["uv", "run", "--project", ..., "python", "detect_containers.py", ...], env)`. If `uv run python detect_containers.py` is invoked from a different cwd than where the script lives, Python cannot find `detect_containers.py`. The fix: use `Path(sys.argv[0]).resolve()` or `__file__` instead of `sys.argv[0]` as the script path in the re-exec.

**Why it happens:**
The plan's Task 3 end-to-end smoke test only verifies the happy path from the repo root. The `sys.argv[0]` relative-path edge case is easy to miss because local testing always runs from the repo root.

**WARNING SIGN:** A user reports "the plugin works when run from the repo root but fails when invoked by Claude Code from a different directory." The error is `python: can't open file 'detect_containers.py': [Errno 2] No such file or directory`.

**PREVENTION:**
In `_uv_reexec.py`, use `Path(__file__).resolve()` as the script path in the `os.execvpe` call, not `sys.argv[0]`:
```python
script_path = str(Path(__file__).resolve().parent / Path(sys.argv[0]).name)
```
Or more robustly: `str(Path(sys.argv[0]).resolve())` — but only if the file exists at the resolved path. The plan already uses `Path(__file__).resolve().parent` for the walk-up search; extend that pattern to the re-exec script path. Add a test that invokes the shim with a relative path from a tmp working directory.

**WHICH PHASE:** Hygiene phase (quick-task `260521-mfm`). Add the `sys.argv[0]` resolution note to the plan before execution.

---

### Pitfall 11: Scanner Consuming graph-io as Source-of-Truth — Stale Graph on First Scan

**What goes wrong:**
When the scanner is updated to key pages by URI (via graph-io), it calls `cg update` (or calls `graph_io.resolve.sweep` + `graph_io.packages.refresh` directly) to ensure the graph is current before scanning. For a brand-new workspace that has never been scanned (`~/.graph-wiki/code.db` does not exist yet), `store.read_only_connect` raises `GraphNotInitializedError`. The scanner must handle this by running `cg update --full` first, then proceeding.

But there is a subtler issue: during a workspace's first scan, the graph is built from the current filesystem snapshot. If a file was added to the repo in the last 5 minutes and `cg update` has not yet run, the graph does not contain that file's node. The scanner's URI-keyed output will produce pages for all URIs in the graph but miss the new file. The wiki goes out of sync not because of a bug but because of a sequencing issue: file add → scan → update is wrong; the correct order is file add → update → scan.

**Why it happens:**
The natural UX for `graph-wiki-agent scan` is "run this and get fresh wiki pages." The user does not know that the graph must be updated before the scan. If the scan command silently calls `cg update` before scanning, it always produces correct output but adds 5-30 seconds of graph rebuild time to every scan invocation.

**WARNING SIGN:** User runs `graph-wiki-agent scan` after adding a new package; no page is generated for the new package. No error is raised. The user runs `cg update` then `graph-wiki-agent scan` — the page appears.

**PREVENTION:**
`run_scan` must call `cg update` (incremental, not `--full`) at the start of the scan command, before any scanner subagent is dispatched. This is the correct design: scan always runs on a fresh graph. Add the update call to the scan command implementation as a first step, before the SubagentPool fan-out. Document this as a design decision (scan depends on a fresh graph) in the phase SUMMARY.

**WHICH PHASE:** Scanner integration phase.

---

### Pitfall 12: Ingestor Consuming graph-io — Node Identity Conflicts When URI Changes Between Ingest and Next Update

**What goes wrong:**
The ingestor creates wiki pages keyed by URI. If the ingestor creates a page for `pkg:org/repo/auth-service` and then the package is renamed in `pyproject.toml`, the next `cg update` generates a new URI `pkg:org/repo/auth` (or whatever the new name is). The old page `pkg:org/repo/auth-service.md` is now orphaned — it has a URI that no longer exists in the graph. The wiki accumulates stale pages with dead URIs.

The current non-URI-keyed ingestor has the same problem (pages keyed by filesystem path, which also changes on rename) but at a slower rate since package renames are rare. URI-keyed pages make the problem more visible because URIs change on any manifest rename, not just on directory moves.

**Why it happens:**
Page identity and node identity use different persistence domains. wiki-io pages live on the filesystem; graph-io nodes live in SQLite. There is no reconciliation mechanism between them in v1.7 (wiki redesign is v1.8 work).

**WARNING SIGN:** `wiki-io lint` reports pages with URIs that resolve to no graph node. Or `graph-wiki-agent scan` generates a new page for `pkg:org/repo/auth` while an old page for `pkg:org/repo/auth-service` still exists in the vault.

**PREVENTION:**
In v1.7, document this limitation explicitly in the ingestor design: "URI-keyed pages may become stale if URIs change between ingests. The wiki redesign (v1.8) will introduce a reconciliation step that deletes pages for non-existent URIs." Do not try to solve the reconciliation problem in v1.7 — it is a v1.8 concern per `PROJECT.md` Deferred section. The ingestor should log a warning when it creates a page for a URI that was not present in the last graph update timestamp; do not block ingestion on stale URI detection.

**WHICH PHASE:** Ingestor integration phase. State the limitation and the v1.8 reconciliation path in the phase plan's "known limitations" section.

---

## Minor Pitfalls

### Pitfall 13: `graph-wiki-agent graph` Subcommand Name Collision with Typer Reserved Names

**What goes wrong:**
Typer uses `app.command()` decorators. The new subcommand will be registered as `graph`. This conflicts if any existing code uses `app.command(name="graph")` or if Typer internally reserves `graph` as a help-system keyword. More practically: adding a `graph` subcommand alongside `scan`, `ingest`, `lint`, `query` creates an ambiguity risk when a user types `graph-wiki-agent g<TAB>` — tab completion returns both `graph` and no other `g`-prefixed commands today, so this is not a real ambiguity yet, but could become one if new subcommands starting with `g` are added later.

**PREVENTION:**
Run `graph-wiki-agent --help` after adding the `graph` subcommand; verify it appears in the list without mangling any existing commands. Check for import-time conflicts with `typer.Typer().command("graph")` registration. No action needed unless a conflict is found.

**WHICH PHASE:** `graph-wiki-agent graph` subcommand phase. Smoke test: `graph-wiki-agent graph --help` exits 0 and lists `build`, `describe`, `query`.

---

### Pitfall 14: Token Budget Regression from Grounding Tools in Librarian Prompt

**What goes wrong:**
Adding `@tool` callables to the librarian changes the effective context available per librarian call. The token budget regression test (`test_token_budget.py`) enforces a +1500 token ceiling on the system prompt. But it does not account for the tool definitions themselves — the Bedrock Converse API includes tool definitions (JSON schema for each `@tool`) in the request's `tools` array, which counts against the context window. With 5 graph-io tools, each with a 100-token description and 50-token parameter schema, that is ~750 additional tokens per librarian invocation, outside the system prompt.

**Why it happens:**
`test_token_budget.py` measures prompt token count at construction time, not at invocation time. Tool binding (`librarian_llm.bind_tools([...])`) happens at command entry, not at prompt construction. The snapshot tests do not capture the `tools` array.

**WARNING SIGN:** Librarian invocations on a large monorepo run out of tokens mid-fan-out and return truncated responses. Or Bedrock raises `ValidationException: max_tokens exceeds model limit` because the system prompt + tool schemas + input message exceeds the model's context window.

**PREVENTION:**
Use the Bedrock `CountTokens` API (already used in the codebase) to measure a representative librarian invocation with tools bound and the system prompt attached, before the integration phase ships. Set `max_tokens` for the librarian role conservatively to leave room for tool definitions. Update `test_token_budget.py` to mock a bound-tools invocation and assert the effective context budget stays within bounds.

**WHICH PHASE:** Librarian grounding tools phase. Run CountTokens on a sample invocation before committing the tool binding.

---

### Pitfall 15: syrupy Snapshot Drift from Hygiene Changes to Prompt Fragments

**What goes wrong:**
The hygiene items `hfr` and `i26` change scanner template output. If any scanner prompt test uses a syrupy snapshot that includes the template output (e.g., the `render_project_context` output contains a `## File map` section sampled from a real page), the hygiene change will fail the snapshot. The failure is caught — which is correct behavior — but if the developer accepts the new snapshot without manually reviewing the diff, they silently accept a regression.

**Why it happens:**
syrupy's `assert_match_snapshot()` does not distinguish between intended output changes (the hygiene fix) and unintended regressions (a template change that also corrupted an unrelated field). The acceptance workflow is `pytest --snapshot-update` which bulk-accepts all diffs.

**WARNING SIGN:** After a hygiene item, `pytest --snapshot-update` is run without a manual diff review. The commit message says "update snapshots" without specifying which snapshots changed and why.

**PREVENTION:**
For each hygiene item that changes template output:
1. Run `pytest` — observe which snapshot tests fail.
2. Manually review the diff output (not just `pytest --snapshot-update`).
3. Accept only the snapshots that changed because of the intended hygiene fix.
4. Commit with a message that names which snapshots changed and why.

**WHICH PHASE:** Hygiene phase. Add this to the phase's verification checklist.

---

## Phase-Specific Warnings

| Phase Topic | Likely Pitfall | Mitigation |
|-------------|---------------|------------|
| Librarian grounding tools | Tool surface too broad → routing confusion | Design ≤5 tools before writing any; use `_format.render` not raw JSON |
| Librarian grounding tools | Return payload overflow | Hard-cap at 50 rows; `-> str` return type on all @tools |
| Scanner consumes graph-io | Stale graph on first scan | `run_scan` calls `cg update` (incremental) before fan-out |
| Scanner consumes graph-io | Open connection per-tool vs per-command | Close over single read-only conn at command entry, not per tool call |
| Ingestor consumes graph-io | URI drift on package rename | Document v1.8 reconciliation; warn don't block in v1.7 |
| `graph-wiki-agent graph` subcommand | Feature drift from `cg` | Thin wrapper only; no new flags not in `cg`; enforce in plan |
| `cg find` parser ergonomics | Positional→named flag breaks internal callers | Single-commit break-and-fix; grep all `main(["find", "foo"])` callers |
| Hygiene phase | File-touch overlap causes silent reversions | File-touch matrix before plan wave assignment; sequential not parallel |
| Hygiene phase | wiki-io template changes break plugin | Before/after smoke scan on live vault; capture SC#4 transcript |
| ANSI fix (`260521-ans`) | Developer switches to CliRunner without NO_COLOR | Execute the pre-written plan exactly; no CliRunner substitution |
| uv re-exec (`260521-mfm`) | `sys.argv[0]` relative path breaks from non-root cwd | Use `Path(__file__).resolve()` in re-exec script path |
| Token budget after tool binding | Tool schemas add ~750 tokens not counted by test | Run CountTokens before finalizing librarian tool binding |
| syrupy snapshots | Bulk snapshot accept without manual diff review | Named-snapshot diff review for each hygiene item |

---

## "Looks Done But Isn't" Checklist for v1.7

- [ ] **@tool return types:** Every graph-io `@tool` callable returns `str`, not `dict` / `list` / dataclass. Verify with `grep -n "-> " agents/.../commands/*.py | grep tool`.
- [ ] **Row cap:** Every list-returning `@tool` has a `[:50]` or equivalent cap with a truncation notice. Verify by testing `graph_list("package")` on a large fixture.
- [ ] **Connection lifetime:** The read-only graph connection is opened once at command entry, closed after the fan-out completes — not opened/closed per tool call.
- [ ] **Scanner update-before-scan:** `run_scan` calls `cg update` (incremental) before dispatching the SubagentPool. Verify: scan on a repo with an uninitialized graph produces a helpful error, not a silent empty scan.
- [ ] **`cg find` positional removed:** `cg find foo.py --kind file` (old positional form) produces argparse error. `cg find --name foo.py --kind file` succeeds.
- [ ] **Plugin smoke transcript:** A `/graph-wiki:scan` session transcript from Claude Code against `~/Personal/graph-wiki/agent-research` is committed as a regression artifact. (Carried since v1.2 — must close in v1.7.)
- [ ] **Hygiene snapshot review:** No `pytest --snapshot-update` commit without a named list of changed snapshots and why.
- [ ] **`mfm` re-exec from non-root cwd:** `cd /tmp && python /path/to/detect_containers.py --help` succeeds without `ModuleNotFoundError`.
- [ ] **`ans` ANSI fix:** All 5 tests listed in `260521-ans-PLAN.md` pass; snapshot count unchanged.
- [ ] **Token budget:** CountTokens API confirms librarian invocation with 5 bound tools + system prompt stays within `lib_cfg["max_tokens"]` budget.

---

## Sources

- `agents/graph-wiki-agent/src/graph_wiki_agent/commands/query.py` — existing `@tool read_file` pattern; `bind_tools`, `ToolMessage`, 24000-char truncation guard, 60000-char excerpt cap
- `agents/graph-wiki-agent/src/graph_wiki_agent/prompts/librarian.py` — current librarian prompt structure; token budget context
- `packages/graph-io/src/graph_io/cli/main.py` — 25 subcommand surface; `_SUBCOMMANDS` dict; argparse dispatch
- `packages/graph-io/src/graph_io/cli/q_find.py` — `parser.add_argument("name")` positional form (the current state to change)
- `packages/graph-io/src/graph_io/queries.py` — `NodeRecord` dataclass, `_VALID_KINDS`, `find()` function surface
- `.planning/quick/260521-ans-typer-help-ansi-strip/260521-ans-PLAN.md` — chosen ANSI fix: `NO_COLOR=1` + `TERM=dumb` + `COLUMNS=200`; explicit "why not CliRunner" rationale
- `.planning/quick/260521-mfm-add-self-healing-uv-re-exec-to-graph-wik/260521-mfm-PLAN.md` — `_uv_reexec.ensure()` design; `GRAPH_WIKI_SHIM_REEXEC` guard; `os.execvpe` with walk-up search
- `.planning/RETROSPECTIVE.md` — v1.2 Phase 16: "code review that produces issues without a fix plan is review-as-documentation, not review-as-gate"; v1.1 Phase 8: "documented scope narrowing before implementation"; v1.2 Phase 14: "SC#4 plugin smoke transcript not captured at close"; v1.0 Phase 3: "cap phase plan count at ~6"
- `.planning/MILESTONES.md` — v1.2 Phase 14 SC#4 deferred item (still open at v1.7 start)
- `.planning/PROJECT.md` — v1.7 target features, plugin stays untouched constraint, cg 25-subcommand count, single-writer Bedrock-only constraint

---
*Pitfalls research for: v1.7 graph-io Integration & Wiki Hygiene*
*Researched: 2026-05-26*
