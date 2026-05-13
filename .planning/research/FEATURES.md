# Feature Research

**Domain:** MCP server + deepagents-native code wiki agent with per-subagent eval harness
**Researched:** 2026-05-13
**Confidence:** HIGH (MCP/deepagents from Context7 official docs; eval patterns from deepagents evals lib + LangSmith SDK)

---

## Section 1: MCP Server Features

The MCP server is the primary delivery surface. The DeepAgents CLI hosts the conversation; this server exposes tools. The question is: which MCP primitives are actually useful for a deepagents host vs which are just spec completeness?

### Table Stakes — MCP Server

| Feature | Why Expected | Complexity | Notes |
|---------|--------------|------------|-------|
| Tool registration for all 6 commands | DeepAgents host discovers tools via `tools/list`; missing tools = commands unreachable | S | One `@mcp.tool()` per command: `wiki_init`, `wiki_scan`, `wiki_ingest`, `wiki_query`, `wiki_lint`, `wiki_log` |
| Typed input schemas (Pydantic) | MCP host renders parameter hints; type validation catches bad calls before the agent loop runs | S | FastMCP infers from function signature; use Pydantic models for complex args |
| Structured output (Pydantic return types) | Host can parse success/failure without regex; subagent fan-out aggregation requires structured results | S | Return typed dataclasses/Pydantic models, not raw strings. FastMCP wraps automatically. |
| `isError` flag on tool failures | MCP protocol standard: distinguish tool error from tool success with error content | S | FastMCP surfaces Python exceptions as `isError=true` content automatically |
| `ctx.info()` / `ctx.debug()` log emission | Without log emission, debugging hangs during long scan/lint/ingest runs is impossible | S | `ctx.info(...)` during each major phase of scan/ingest/lint; `ctx.debug(...)` for per-file events |
| `ctx.report_progress()` during long operations | scan, ingest, lint can take 30–120s on large repos; without progress the host shows nothing | S | Emit progress fraction at each package/rule-group boundary |
| stdio transport | DeepAgents CLI spawns MCP servers as stdio subprocesses — this is the primary integration path | S | `mcp.run(transport="stdio")` is one line; required for DeepAgents CLI compatibility |
| Graceful error returns (not process crashes) | A lint parse error on one page must not kill the server process | S | Wrap tool bodies in try/except; return `isError=true` with message |

### Differentiators — MCP Server

| Feature | Value Proposition | Complexity | Notes |
|---------|-------------------|------------|-------|
| Resource exposure for vault pages | Exposes individual wiki pages as addressable `wiki://page/{slug}` resources; host can `read_resource` without calling a tool | M | Useful for Cursor/Claude Code hosts that do RAG over resources; not needed for DeepAgents CLI today but costs little to add |
| Prompt templates for common invocations | Pre-baked prompts like `wiki_query_prompt(question)` reduce token waste on repeated query framing | S | `@mcp.prompt()` decorator; low-cost, good for future MCP host compatibility |
| Streamable HTTP transport (alternative) | Enables deployment as a standalone service (CI, remote use); not needed locally | M | `mcp.run(transport="streamable-http", stateless_http=True)` — add as an optional `--transport` flag; defer to v1.x |
| Server `instructions` metadata | Host-visible description of what the server does and how to invoke it; improves agent planning | S | Set `name`, `description`, `instructions` on the FastMCP instance |
| Per-tool `annotations` (readOnly, destructive) | Lets cautious hosts gate destructive tools (init, ingest) from read-only sessions | S | MCP spec supports tool annotations; mark `wiki_init`, `wiki_ingest`, `wiki_scan` as `destructive=True` |

### Anti-Features — MCP Server

| Feature | Why Requested | Why Not Build It | Alternative |
|---------|---------------|-----------------|-------------|
| Sampling (`ctx.session.create_message`) | Lets server call back to the host LLM mid-tool | The LLM calls are handled by deepagents subagents running inside the tool, not by sampling back through MCP. Sampling adds a round-trip and couples server to host LLM choice. | Keep all LLM calls in the deepagents subagent layer, not in MCP callbacks |
| SSE-only transport (legacy) | Some older hosts only understand SSE | SSE was deprecated in MCP spec 2025-03-26; streamable HTTP supersedes it | Implement streamable HTTP if remote access is needed; skip SSE entirely |
| Resource subscriptions / change notifications | Nice for live-updating clients | No real-time file watcher exists in lattice-wiki; adding one is out of scope | Clients re-call tools to get fresh state |
| MCP roots negotiation | Protocol feature for multi-root workspaces | DeepAgents CLI doesn't use roots today; the server reads repo path from tool args | Pass `repo_path` as explicit tool argument |

---

## Section 2: Subagent Fan-Out Features

Fan-out is the primary reason for the rewrite — sequential subagents become parallel. Deepagents provides `runSwarm` (bounded parallel fan-out) and per-SubAgent model config via `subagents.yaml` or inline Python dicts.

### Table Stakes — Subagent Fan-Out

| Feature | Why Expected | Complexity | Notes |
|---------|--------------|------------|-------|
| Per-role model routing | Different Bedrock models per role is the cost-savings mechanism; without it, all roles run the same model and there's no optimization lever | M | deepagents SubAgent dict supports `"model": "bedrock:..."` per agent; configure scanner/librarian/linter/ingestor separately |
| Parallel page-drill (librarian) | query currently drills 3–10 pages sequentially; parallelizing is the main latency win | M | `runSwarm` with `concurrency=5`; each task = one page drill + synthesis fragment |
| Parallel rule-group execution (linter) | lint has 6+ rule groups (container, file_map, domain, source_sync, package_sync, dependency_layer); running concurrently cuts wall time ~5x | M | Each rule-group becomes a SubAgent task; results merged into unified report |
| Parallel package review (scanner) | scan walks N packages; reviewing each stub in parallel vs sequentially is the main scan speedup | M | One SubAgent task per package; concurrency bounded by `runSwarm` cap (10) |
| Result aggregation | Fan-out is useless without merging partial results into a coherent output | M | Aggregator function runs after `runSwarm` completes; merges list results, deduplicates cross-refs, sorts lint findings by severity |
| Partial-failure handling | If 2 of 10 page-drills fail (model timeout, malformed page), query must still return the 8 that succeeded | S | Check `result.status == "failed"` in `runSwarm` results; emit warning in output, continue with completed results |
| Structured trace output per run | Without per-run trace, cost accounting and debugging are blind | S | Each SubAgent emits structured result including: role, model_id, input_tokens, output_tokens, duration_ms, status |

### Differentiators — Subagent Fan-Out

| Feature | Value Proposition | Complexity | Notes |
|---------|-------------------|------------|-------|
| Per-subagent cost/token accounting | Enables the cost-frontier report; without it the eval harness has no cost axis | M | Capture `usage_metadata` from LangChain AI message responses; aggregate per role per run. LangChain-AWS exposes token counts via `response_metadata`. |
| Retry policy (per-subagent, with backoff) | Bedrock throttles under load; 1 retry with exponential backoff recovers most transient failures without manual re-run | M | Wrap SubAgent invocation in retry decorator; log retries to structured trace |
| Concurrency limit as config | Different commands have different parallelism budgets (scan: wide, query: narrow) | S | Expose `fan_out_concurrency` per command in config; default safe values (librarian=5, linter=6, scanner=8) |
| Agent-level system prompt overrides | Fine-tuning per-role behavior without code changes; useful for model-specific prompting | S | SubAgent `system_prompt` field; store per-model variants in config |
| Fan-out summary log to `log.md` | Preserves the existing lattice-wiki logging convention while adding subagent stats | S | After aggregation, append structured JSON entry to `log.md` with per-role token + duration summary |

### Anti-Features — Subagent Fan-Out

| Feature | Why Requested | Why Not Build It | Alternative |
|---------|---------------|-----------------|-------------|
| Nested subagents (sub-subagents) | More parallelism | PROJECT.md explicitly rules out nested subagents in v1; debugging cost is high, quality gain unproven | Profile single-level fan-out first; revisit if eval shows bottleneck |
| Dynamic concurrency scaling | Automatically adjusting concurrency based on model latency | Over-engineering for v1; Bedrock throttle behavior is not deterministic enough for reliable auto-scaling | Fixed concurrency per command in config; manual tuning after eval |
| Cross-command subagent pooling | Reusing a "warm" subagent across commands | Not supported by deepagents SubAgent model; each `runSwarm` call is stateless | Accept stateless fan-out; it simplifies reasoning about side effects |

---

## Section 3: Eval Suite Features

The eval suite exists to answer one question: "Which Bedrock model is cheapest while still meeting quality bar per role?" It must produce a cost-vs-quality frontier per subagent role.

### Table Stakes — Eval Suite

| Feature | Why Expected | Complexity | Notes |
|---------|--------------|------------|-------|
| Baseline corpus capture | Without a recorded baseline from the current tool, there's no reference point for "same quality" | M | Run each lattice-wiki command against fixture repos; capture full outputs as JSON/markdown files. Store in `evals/baselines/`. Run once, commit. |
| Fixture repos (test repos) | Eval needs stable, controlled inputs — not Pat's live repos | M | Create 2–3 small synthetic repos (monorepo with 5 packages, single package, ADR-heavy repo) as git submodules or committed snapshots in `evals/fixtures/` |
| Per-role model comparison harness | Core eval: swap Bedrock models per role (Haiku/Sonnet/Llama/Nova), hold prompts fixed, score against baseline | M | pytest parametrize over model list per role; `deepagents-evals`-style trial runner or custom pytest fixtures |
| Structural scoring (deterministic checks) | Some outputs are checkable without LLM: frontmatter valid, wikilinks resolve, all packages present in scan output | S | Pure Python assertions: parse frontmatter, check link targets exist, verify index entry counts |
| Similarity scoring (vs baseline) | Measures semantic closeness of new output to recorded baseline; catches regressions that structural checks miss | M | Jaccard similarity on token sets for lightweight checks; optionally add embedding cosine similarity for query answers |
| Cost tracking per run | Without cost data, the cost-frontier report has no Y axis | S | Capture `input_tokens` + `output_tokens` per subagent from trace; multiply by Bedrock per-token price for each model; store in trial JSON |
| JSON trial output | Machine-readable results enable automated regression detection and chart generation | S | Per-trial JSON: `{role, model_id, query, score, cost_usd, duration_ms, baseline_match}`; schema matches deepagents evals trial format |
| Regression detection (run vs baseline threshold) | CI must fail when quality drops below threshold | S | Assert `score >= MIN_SCORE` in pytest; MIN_SCORE set per role based on initial calibration |
| CI integration (pytest-based) | The eval suite must be runnable in CI without manual intervention | S | Standard `pytest evals/` invocation; `@pytest.mark.slow` for LLM-calling tests; `@pytest.mark.eval` for model-comparison tests; skip by default in unit CI |

### Differentiators — Eval Suite

| Feature | Value Proposition | Complexity | Notes |
|---------|-------------------|------------|-------|
| LLM-judge scoring for query answers | Structural + similarity checks may miss answer quality nuance; an LLM judge catches factual errors and hallucinations | L | Use a cheap model (Nova Micro or Haiku) as judge; prompt: "Does this answer correctly address the question given this wiki?" Score 0–1. Higher cost; defer if similarity scoring is sufficient. |
| Cost-vs-quality chart (per role) | The deliverable — a visual that shows which model is on the Pareto frontier per role | M | Generate via matplotlib or simple HTML table; one chart per role; axes: quality score (Y) vs $/run (X); models as labeled points |
| Per-query breakdown report | Pinpoints which queries drive quality differences between models | M | Per-query score in trial JSON; sort by score delta vs baseline; output top-10 worst queries per model |
| Reproducibility controls (seed, model pinning) | Ensures trial-over-trial comparability | S | Pass `temperature=0.0` where Bedrock supports it; pin `model_id` including version suffix (e.g., `anthropic.claude-haiku-4-5-20251001-v1:0`); record in trial metadata |
| Retry-failed-only mode | Re-running only failed eval cases saves significant time/cost during debugging | S | Store failures in trial JSON; `pytest --rerun-failed=trials_summary.json`; mirrors `deepagents-evals --retry-failed` pattern |
| LangSmith dataset integration | Offload dataset storage and experiment tracking to LangSmith; enables UI-based comparison | L | LangSmith `evaluate()` with custom evaluators; useful if suite grows large; adds dependency and auth requirement; defer unless manual JSON management becomes painful |

### Anti-Features — Eval Suite

| Feature | Why Requested | Why Not Build It | Alternative |
|---------|---------------|-----------------|-------------|
| MMLU/academic benchmarks | General model quality benchmarks exist | This eval measures task-specific quality on wiki outputs, not general intelligence. Academic benchmarks don't tell you if Haiku can lint a Python monorepo. | Domain-specific structural + similarity + optional LLM-judge scoring |
| Real-time eval dashboard | Pretty UI for exploring results | Overkill for one developer; adds a web server dependency | JSON files + single chart script; open in browser when needed |
| Multi-provider eval (non-Bedrock) | Compare OpenRouter / direct Anthropic / Ollama | PROJECT.md rules out non-Bedrock in v1; adding providers now fragments the eval matrix | Bedrock-only in v1; eval harness is provider-agnostic enough to extend later |
| Automatic prompt optimization | Iteratively improve prompts based on eval scores | Dangerous scope creep; prompt changes must be human-reviewed, not auto-applied | Eval surfaces score deltas; human decides whether to update prompts |

---

## Section 4: Features Lattice-Wiki Lacks (Consider for This Rewrite)

These are gaps in lattice-wiki today that a deepagents-native rebuild could address. Categorized by whether they're worth picking up during this rewrite.

### Worth Considering in v1 (Low Complexity, High Value)

| Feature | Current Gap | Complexity | Recommendation |
|---------|-------------|------------|----------------|
| Semantic search (BM25 + embedding hybrid) | lattice-wiki uses BM25 only; semantic search finds conceptually related pages that keyword search misses | M | Add optional embedding-based re-ranking on top of BM25 results using a Bedrock embedding model (Titan Embeddings v2). Gated by config flag; BM25-only remains default. |
| Structured scan diff output | scan today logs human-readable text; a structured JSON diff (added/updated/deleted stubs) would make scan composable with other tools | S | Return `{added: [...], updated: [...], deleted: [...]}` from `wiki_scan` tool; existing human log still emitted |
| Query answer confidence / uncertainty signal | query today returns synthesized text with no quality signal; a confidence flag ("HIGH / LOW coverage") helps the user decide whether to ingest more pages | S | Append confidence field to query output: based on number of pages found vs requested, and whether all wikilinks resolved |

### Defer to v2 (High Complexity or Needs Validation First)

| Feature | Current Gap | Why Defer |
|---------|-------------|-----------|
| Vector store / persistent embedding index | Embedding-based search requires maintaining a vector DB across runs | Adds infra dependency (local Chroma or cloud service); validate BM25+hybrid approach first |
| Git-diff-aware ingest (only re-ingest changed files) | ingest today re-processes all files; a git-diff pre-filter would cut cost on large repos | Requires git integration inside ingest loop; significant complexity; defer until cost becomes measurable pain |
| ADR / decision log cross-referencing | ADRs exist in the vault but aren't first-class linked to package pages they affect | Medium complexity; needs a new page category type and lint rule; worth a dedicated milestone |
| Automatic page staleness scoring | Detect which pages are most likely out of date based on git activity vs last-ingest timestamp | Needs git integration + scoring heuristic; medium complexity; useful but not blocking parity |
| Streaming query responses | Stream query answer tokens back to the MCP host as they arrive | Requires streaming-aware MCP tool (async generator); deepagents fan-out aggregation doesn't naturally compose with streaming; defer |

### Explicit Non-Goals (Anti-Features for This Rewrite)

| Feature | Why Not |
|---------|---------|
| Full-text search over source code (not wiki) | This is a wiki agent, not a code search engine. Serena, code-index-mcp, and similar tools handle code search. The wiki is an abstraction layer over code, not a code index. |
| Automatic wiki generation from scratch without human review | Fully automated generation without a state-gate leads to hallucinated pages. lattice-wiki's state-gate convention (DRAFT → REVIEW → STABLE) must be preserved. |
| Real-time file watchers / auto-sync | Explicitly ruled out in PROJECT.md. Manual triggers match the existing workflow. |
| Multi-repo federation | Each wiki vault maps to one repo. Multi-repo is an architectural change that requires vault schema changes. Defer indefinitely. |
| Web UI for wiki browsing | Obsidian already handles this. Adding a web UI duplicates it. |

---

## Feature Dependencies

```
wiki_init
    └──required by──> wiki_scan (vault must exist before scan writes stubs)
    └──required by──> wiki_ingest (vault must exist before ingest writes pages)
    └──required by──> wiki_query (index must exist to query)
    └──required by──> wiki_lint (vault must exist to lint)

wiki_scan
    └──required by──> wiki_query (index populated by scan)
    └──required by──> wiki_lint (stubs created by scan are lint targets)
    └──enhances──> wiki_ingest (scan creates stubs that ingest fills)

Structured trace output (fan-out)
    └──required by──> Cost tracking (eval)
    └──required by──> Cost-vs-quality chart (eval)

Baseline corpus
    └──required by──> Regression detection
    └──required by──> Similarity scoring
    └──required by──> Per-role model comparison harness

Fixture repos
    └──required by──> Baseline corpus capture
    └──required by──> Per-role model comparison harness

Per-role model routing (fan-out)
    └──required by──> Cost-vs-quality chart (eval)
    └──enhances──> Cost tracking (eval)
```

### Dependency Notes

- `wiki_init` must ship before any other command can be tested end-to-end.
- Baseline corpus capture depends on fixture repos being committed first; capture should be a one-time recorded step, not regenerated on each eval run.
- The cost-vs-quality chart is only meaningful after per-role model routing is wired and cost tracking is capturing real token counts. These three features form a single deliverable unit.
- Structured trace output is a cross-cutting concern that must be designed before fan-out is implemented — retrofitting it is harder than building it in.

---

## MVP Definition

### Launch With (v1 — full parity milestone)

These are the features without which the tool doesn't replace lattice-wiki.

- [ ] All 6 MCP tools registered with typed schemas — required for DeepAgents host to discover commands
- [ ] `ctx.info()` + `ctx.report_progress()` in scan, ingest, lint — required because these commands take >30s
- [ ] Graceful error returns (`isError=true`) — required to avoid server crashes killing the DeepAgents session
- [ ] stdio transport — required for DeepAgents CLI integration
- [ ] Per-role model routing (scanner, librarian, linter, ingestor to separate Bedrock models) — required for the cost savings goal to be testable
- [ ] Parallel page-drill (librarian), parallel rule-groups (linter), parallel package review (scanner) — required; these are the primary v1 differentiator over the existing tool
- [ ] Partial-failure handling in fan-out — required; without it, one bad page crashes the whole query
- [ ] Structured trace output per subagent run — required foundation for eval
- [ ] Fixture repos committed — required before any eval run
- [ ] Baseline corpus captured from current lattice-wiki — required before eval produces meaningful comparisons
- [ ] Structural scoring (deterministic checks) — required as the lowest-cost eval signal
- [ ] Cost tracking per run (token counts × price) — required for cost-frontier report
- [ ] JSON trial output — required for regression detection in CI
- [ ] pytest CI integration with `@pytest.mark.eval` — required for automated regression gate

### Add After Validation (v1.x)

Once parity is confirmed and the first cost-frontier report is generated:

- [ ] Semantic search (BM25 + Bedrock embedding hybrid) — add when query quality evaluation shows BM25 misses are real
- [ ] Similarity scoring (embedding cosine vs baseline) — add if structural scoring proves insufficient to catch regressions
- [ ] Retry policy with backoff — add when Bedrock throttle events appear in trace logs
- [ ] Streamable HTTP transport — add when there's a use case beyond the local DeepAgents CLI
- [ ] Cost-vs-quality chart generation — add once ≥3 trial runs exist to chart
- [ ] LLM-judge scoring — add if similarity scores produce false negatives (regressions the judge catches that Jaccard misses)

### Future Consideration (v2+)

- [ ] Vector store / persistent embedding index — after hybrid search is validated in v1.x
- [ ] Git-diff-aware ingest — after cost of full ingest is measured and confirmed as a pain point
- [ ] ADR cross-referencing as first-class feature — dedicated milestone
- [ ] LangSmith dataset integration — if eval suite outgrows local JSON management
- [ ] Streaming query responses — if latency becomes a complaint with DeepAgents CLI

---

## Feature Prioritization Matrix

| Feature | User Value | Implementation Cost | Priority |
|---------|------------|---------------------|----------|
| 6 MCP tools with typed schemas | HIGH | LOW | P1 |
| stdio transport | HIGH | LOW | P1 |
| Progress reporting + logging in tools | HIGH | LOW | P1 |
| Graceful error returns | HIGH | LOW | P1 |
| Per-role model routing | HIGH | MEDIUM | P1 |
| Parallel fan-out (librarian/linter/scanner) | HIGH | MEDIUM | P1 |
| Partial-failure handling | HIGH | LOW | P1 |
| Structured trace + cost tracking | HIGH | MEDIUM | P1 |
| Fixture repos + baseline corpus | HIGH | MEDIUM | P1 |
| Structural scoring + CI integration | HIGH | LOW | P1 |
| Cost-vs-quality chart | HIGH | MEDIUM | P2 |
| Semantic hybrid search | MEDIUM | MEDIUM | P2 |
| Resource exposure (vault pages) | MEDIUM | MEDIUM | P2 |
| Retry policy with backoff | MEDIUM | MEDIUM | P2 |
| LLM-judge scoring | MEDIUM | HIGH | P2 |
| Prompt templates | LOW | LOW | P2 |
| Streamable HTTP transport | LOW | MEDIUM | P3 |
| LangSmith integration | LOW | HIGH | P3 |
| Streaming query responses | LOW | HIGH | P3 |
| Git-diff-aware ingest | MEDIUM | HIGH | P3 |

---

## Sources

- MCP Python SDK (Context7 `/modelcontextprotocol/python-sdk`, v1.12.4): tool registration, progress, structured output, error handling, sampling, transport options
- DeepAgents (Context7 `/langchain-ai/deepagents`): `runSwarm`, SubAgent model config, `subagents.yaml`, MCP integration via `langchain-mcp-adapters`, eval trial schema
- LangSmith SDK (Context7 `/langchain-ai/langsmith-sdk`): `evaluate()`, custom evaluators, dataset management
- MCP transports: [MCP Transports Explained](https://dev.to/jefe_cool/mcp-transports-explained-stdio-vs-streamable-http-and-when-to-use-each-3lco); [Roo Code transport docs](https://docs.roocode.com/features/mcp/server-transports)
- MCP primitives: [MCP Architecture Deep Dive](https://www.getknit.dev/blog/mcp-architecture-deep-dive-tools-resources-and-prompts-explained); [Prompts and Resources: The Primitives You're Not Using](https://dev.to/aws-heroes/mcp-prompts-and-resources-the-primitives-youre-not-using-3oo1)
- Code wiki ecosystem: [Serena MCP Server](https://a2a-mcp.org/entry/serena-mcp-server); [Code-Index-MCP](https://github.com/johnhuang316/code-index-mcp); [Claude Context MCP](https://www.augmentcode.com/mcp/claude-context-mcp-server)
- Eval patterns: [pytest-evals](https://github.com/AlmogBaku/pytest-evals); [LLM Testing guide](https://langfuse.com/blog/2025-10-21-testing-llm-applications)
- Semantic code search: [Roo Code Codebase Indexing](https://docs.roocode.com/features/codebase-indexing); [Hugging Face code search cookbook](https://huggingface.co/learn/cookbook/code_search)

---

*Feature research for: code-wiki-agent (deepagents MCP server + eval harness)*
*Researched: 2026-05-13*
