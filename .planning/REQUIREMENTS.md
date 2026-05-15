# Requirements: deep-agents (v1 = code-wiki-agent)

**Defined:** 2026-05-13
**Core Value:** Faithfully reproduce lattice-wiki's wiki-maintenance workflows while running entirely on AWS Bedrock with parallel subagents, so the same outcomes can be achieved at meaningfully lower cost than the current Claude-Code-hosted plugin.

> v1 covers the `code-wiki-agent` package end-to-end (MCP server + headless CLI, all 5 commands, fan-out, eval harness) plus the shared monorepo cores it depends on. Other agent packages anticipated in the monorepo are deferred to v2+.

## v1 Requirements

### Infrastructure (INFRA)

- [ ] **INFRA-01**: Initialize `uv` workspace at repo root with `members = ["cores/*", "agents/*"]` glob; root has no `[project]` table
- [ ] **INFRA-02**: Workspace produces a single shared `uv.lock` reproducible via `uv sync`
- [ ] **INFRA-03**: Each workspace member has its own `pyproject.toml` with per-member `testpaths` to avoid pytest collision across the workspace
- [ ] **INFRA-04**: Repo is open-source-ready — MIT-style LICENSE, top-level README, `.gitignore`, `pre-commit` config with ruff/black (or equivalent), no secrets committed
- [ ] **INFRA-05**: CI scaffold (GitHub Actions) runs `uv sync` + lint + unit tests on push; eval suite is opt-in (separate workflow, not blocking)
- [ ] **INFRA-06**: Python 3.11+ pinned; project boots with `uv run code-wiki-agent --help` from a fresh clone

### Bedrock & Model Routing (BED)

- [ ] **BED-01**: Verify Pat's AWS account has working Bedrock access including cross-region inference profile IAM permissions (e.g., `us.anthropic.claude-sonnet-*`); document the verification steps; fail loudly with actionable guidance if missing
- [ ] **BED-02**: `cores/model-adapter` exposes a `ModelRegistry` keyed by logical role name (`librarian`, `scanner`, `linter`, `ingestor`, `synthesizer`, `judge_a`, `judge_b`) → concrete `ChatBedrockConverse` instance
- [ ] **BED-03**: Per-role config includes `model_id`, `max_tokens` ceiling, and `max_concurrency` (semaphore size) to prevent burst throttling
- [ ] **BED-04**: Models are configured via YAML/TOML file (one canonical `models.toml`) — no hardcoded model IDs; default config ships with sensible Bedrock picks for each role
- [ ] **BED-05**: Token + cost accounting is captured per invocation (input/output/cached tokens, USD estimate) and propagated to traces

### Subagent Runtime (SUB)

- [ ] **SUB-01**: `cores/subagent-runtime` exposes a fan-out primitive that runs N tasks concurrently against role-bound models
- [ ] **SUB-02**: Use deepagents `SubAgentMiddleware` as the primary fan-out path; verify behavior with an integration test that intentionally fails 1 of 4 parallel subagents and confirms partial results are returned (not cancelled)
- [ ] **SUB-03**: If SUB-02 verification fails due to deepagents bugs #694 / #1698, fall back to a raw `asyncio.gather(return_exceptions=True)` `SubagentPool` implementation; the choice is recorded as a Key Decision in PROJECT.md
- [ ] **SUB-04**: Subagent recursion limit is propagated explicitly from parent to child (avoid silent 25-step cap)
- [ ] **SUB-05**: Per-role `max_tokens` and concurrency caps from `ModelRegistry` are enforced at fan-out time (prevent burst throttling)
- [ ] **SUB-06**: Every fan-out call emits a structured trace record (role, model, prompt hash, item id, status, latency_ms, tokens_in, tokens_out, cost_usd) to JSONL — present from day one, not retrofitted
- [ ] **SUB-07**: Subagent results aggregator handles partial failure: returns successes + per-item errors; parent decides whether to fail-fast or degrade-gracefully

### Vault IO (VAULT)

- [ ] **VAULT-01**: Read existing `lattice-wiki` vaults without modification — frontmatter, layout block, wikilinks, file maps, citations all parse to identical in-memory structures as the current tool produces
- [ ] **VAULT-02**: Port `layout_io.py` (layout block read/write) verbatim from `lattice-wiki-core` — hand-rolled YAML emitter preserves exact whitespace/ordering on write-back
- [ ] **VAULT-03**: Use `python-frontmatter` for reads only; all writes route through the ported emitter (no PyYAML re-normalization)
- [ ] **VAULT-04**: `git diff` is empty after parsing-then-writing a real vault page round-trip (golden test gates all vault-write code)
- [ ] **VAULT-05**: Handle truncated frontmatter (missing closing `---`) without crashing; matches behavior of `lattice-wiki-core` commit `ae6872e`
- [ ] **VAULT-06**: Wikilink placeholder predicate (e.g., `[[wiki/...]]`, `[[work/<slug>]]`) is ported verbatim from `lattice-wiki-core` commits `9502c45` + `9388cdd`
- [ ] **VAULT-07**: Port: container detection, monorepo scan, vault initializer, index generator, log appender, token counter (`tiktoken`), graph analyzer — verbatim or close

### Search (SEARCH)

- [ ] **SEARCH-01**: BM25 index over vault pages using `bm25s` 0.3.8 (replacement for dead `rank-bm25`)
- [ ] **SEARCH-02**: Bedrock-embedding index for semantic similarity — Titan Embeddings v2 or Cohere Embed (pick during phase research)
- [ ] **SEARCH-03**: Hybrid search combines BM25 + embedding scores via RRF or weighted fusion; configurable weights with sensible default
- [ ] **SEARCH-04**: Embedding index persists to local sqlite/parquet (no external vector DB); rebuild is cheap (<1 min for typical vault)
- [ ] **SEARCH-05**: Index rebuild is incremental — only re-embed pages whose content hash changed
- [ ] **SEARCH-06**: Search returns top-K results with both raw scores (BM25 / cosine) and fused score visible for debugging

### Commands — Full Parity (CMD)

- [x] **CMD-01** `init`: Bootstrap wiki vault at `<workspace>/wiki/`; discover containers (apps/packages/domains/docs); create category directories + `index.md`, `log.md`, `.templates/`; render tool-specific schema files (CLAUDE.md / AGENTS.md / .cursorrules / opencode / gemini-cli / antigravity); pin layout block; matches `lattice-wiki:init` output structurally
- [x] **CMD-02** `scan`: Walk repo for `package.json`, `pyproject.toml`, `Cargo.toml`, `go.mod`, `pnpm-workspace.yaml`; diff packages vs vault; create/update package stubs in parallel via scanner fan-out; flag renames + deletions; update `index.md` + append `log.md` entry; matches current `lattice-wiki:scan` semantics
- [x] **CMD-03** `ingest`: Extract text + metadata from `.md/.txt/.html/.json/.csv` source; compute slug; route to package/concept/adr page; synthesize summary via ingestor subagent; update cross-references and index; append log entry
- [ ] **CMD-04** `query`: Read `index.md` first; hybrid-search top relevant pages; drill 3–10 in parallel via librarian fan-out; synthesize answer with `[[wikilinks]]` + code-path citations; offer optional file-back; output matches current `lattice-wiki:query` shape (structured JSON via `--json` flag)
- [x] **CMD-05** `lint`: Mechanical pass (orphans, broken wikilinks honoring placeholder filter, stale pages, missing frontmatter, code-drift); semantic pass (contradictions, stale claims, ADR chain) via linter fan-out across rule-groups in parallel; produce actionable report; honor `--stale-days` / `--log-gap-days` thresholds
- [x] **CMD-06** `log`: Append timestamped event (op, title, detail) to `log.md`; structured + atomic
- [ ] **CMD-07**: All 6 commands accept `--json` for structured output (CI/script consumption)
- [ ] **CMD-08**: All commands honor a `state-gate` mechanism equivalent to today's (don't write when git state isn't appropriate); behavior is configurable

### MCP Server Surface (MCP)

- [x] **MCP-01**: FastMCP-based stdio server exposes each command as an MCP tool: `wiki_init`, `wiki_scan`, `wiki_ingest`, `wiki_query`, `wiki_lint`, `wiki_log`
- [ ] **MCP-02**: Tool descriptions + input schemas are sufficient for DeepAgents CLI to call them without extra documentation
- [x] **MCP-03**: Progress reporting via MCP `notifications/progress` for long-running commands (scan, lint, ingest, query — anything with fan-out)
- [ ] **MCP-04**: Errors return structured MCP error responses (no crashes that kill the stdio session)
- [ ] **MCP-05**: ALL logging routes to stderr; nothing — not even `print()` — goes to stdout (would corrupt JSON-RPC framing)
- [ ] **MCP-06**: Cancellation: long-running tools respond to MCP cancel requests within a reasonable window (best-effort, may not interrupt mid-Bedrock-call)
- [ ] **MCP-07**: Server can be launched via `uv run code-wiki-mcp` (entry point); DeepAgents CLI launches it as a stdio subprocess (entry point name amended per Phase 1 CONTEXT D-14)
- [ ] **MCP-08**: NOT in v1: MCP resources, prompts, sampling, SSE/streamable-HTTP transport (anti-features documented in research)

### Headless CLI (CLI)

- [ ] **CLI-01**: Typer-based CLI: `code-wiki-agent <init|scan|ingest|query|lint|log> [args]`
- [ ] **CLI-02**: Each subcommand runs the full agent loop in-process on Bedrock (no MCP host required) — suitable for CI, cron, scripts
- [ ] **CLI-03**: CLI and MCP server share the exact same command implementations (single source of truth, no behavioral divergence)
- [ ] **CLI-04**: `--json` flag on every subcommand for structured output
- [ ] **CLI-05**: `--config <path>` for non-default model/role configuration
- [ ] **CLI-06**: Exit codes: 0 success, 1 user error, 2 system error, 3 partial success (e.g., fan-out had failures but produced usable result)
- [ ] **CLI-07**: Interactive mode (default): rich progress display; headless mode (`--quiet` or non-TTY): line-oriented output suitable for log capture

### Evaluation Harness (EVAL)

- [ ] **EVAL-01**: `cores/eval-harness` is a separate package usable by future agent packages (not in-tree to `code-wiki-agent`)
- [ ] **EVAL-02**: Fixture corpus: 2–3 small test repos with pre-built wikis committed to `tests/fixtures/` covering single-package, monorepo, and edge-case shapes
- [ ] **EVAL-03**: Baseline recorder: replay-able harness that runs the existing `lattice-wiki` plugin (Claude Sonnet via Claude Code) against each fixture and snapshots outputs to `eval/baselines/` (one-time manual step, instructions documented)
- [ ] **EVAL-04**: Model sweep runner: for a given subagent role (e.g., `librarian`), runs N candidate Bedrock models against the fixture suite holding prompts fixed
- [ ] **EVAL-05**: Scoring uses `deepeval` 4.0 with `AmazonBedrockModel`; heterogeneous judge panel (one Claude model + one non-Claude model on Bedrock) to mitigate self-preference bias
- [ ] **EVAL-06**: Structural metrics (cheap, deterministic): cites at least one code path, all wikilinks resolve, frontmatter valid, output matches expected JSON schema. Required for every run; LLM-judge metrics layer on top
- [ ] **EVAL-07**: Cost-frontier report: per-role chart of quality (composite score 0–1) vs cost (USD/run), with the cost-optimal-still-passing model highlighted
- [ ] **EVAL-08**: Reproducibility: each eval run pins model ARN + version; result JSON includes ARN + hash of prompt + timestamp + seed
- [ ] **EVAL-09**: Regression check: comparing current run to baseline raises a CI-friendly failure if quality drops below a configurable threshold for any role
- [ ] **EVAL-10**: Pytest integration via `pytest-evals` so individual eval cases run as pytest tests (selectable, parallelizable, CI-skippable by mark)

### Observability (OBS)

- [ ] **OBS-01**: Every command run emits a structured trace JSONL file under `.code-wiki/traces/<timestamp>.jsonl` (configurable path) containing the full subagent fan-out tree, model choices, tokens, cost, latencies
- [ ] **OBS-02**: A `code-wiki-agent trace <file>` viewer subcommand renders the JSONL as a human-readable timeline
- [ ] **OBS-03**: Cost summary printed at the end of every interactive run (always-on; `--quiet` suppresses)

## v2 Requirements

Acknowledged, deferred from v1.

### Other Agent Packages

- **V2-AGENT-01**: Second agent package (TBD — likely `code-workflow-agent` or `code-research-agent`) — proves the tiered monorepo cores are actually reusable
- **V2-AGENT-02**: Shared core promoted from `code-wiki-agent` learnings (e.g., extract command-dispatch boilerplate into a `cores/command-runner` if patterns repeat)

### Custom TUI

- **V2-TUI-01**: Optional Textual-based TUI for `code-wiki-agent` when DeepAgents CLI isn't a fit

### Provider Expansion

- **V2-PROV-01**: OpenRouter adapter for `cores/model-adapter`
- **V2-PROV-02**: Local OpenAI-compatible endpoint adapter (Ollama, LM Studio, vLLM)
- **V2-PROV-03**: Direct Anthropic API adapter (cheaper than Bedrock for some Claude models)

### Capability Upgrades

- **V2-CAP-01**: Nested subagents (subagent spawns sub-subagent) — only if eval shows quality gaps that flat fan-out can't close
- **V2-CAP-02**: Real-time file watcher → auto-scan/auto-lint
- **V2-CAP-03**: MCP resources + prompts (broader MCP host compatibility beyond DeepAgents CLI)
- **V2-CAP-04**: Streamable-HTTP transport for remote MCP deployment

### Eval Maturity

- **V2-EVAL-01**: Confidence calibration (does the librarian know when to say "I'm not sure"?)
- **V2-EVAL-02**: Cost-frontier curves over time (track drift as models update)
- **V2-EVAL-03**: A/B prompt regression suite (today's eval is model-focused)

## Out of Scope

| Feature | Reason |
|---------|--------|
| Custom TUI in v1 | DeepAgents CLI is the host; building a TUI is parallel work that doesn't help the cost-savings goal |
| Non-Bedrock providers in v1 | Single-provider focus simplifies adapter layer and eval harness; cost savings story is Bedrock-specific |
| Nested subagents in v1 | Within-command fan-out is enough complexity; nested adds debug/cost surprises without proven need |
| Vault format migration / rewrite | Read-compatible means we don't change the format; preserves Obsidian + side-by-side use with old plugin |
| Writing to old lattice-wiki vaults during transition | Read yes, write no, until the new tool is validated — avoids dual-writer drift |
| PyPI release on day one | Build clean enough to open-source later; release after eval validates the cost story |
| Real-time file watcher / auto-sync | Commands stay manually triggered, matches lattice-wiki today; no clear pain point yet |
| MCP sampling | Would couple server to host's model choice; all LLM calls belong in subagents on Bedrock |
| MCP resources / prompts | Not needed by DeepAgents CLI host; add later if a different host requires them |
| SSE / streamable-HTTP MCP transport | stdio is sufficient for DeepAgents CLI; remote deployment is not a v1 use case |
| `rank-bm25` library | Unmaintained since 2022; `bm25s` is 5–50× faster and active |
| LangGraph multi-agent platform features | deepagents' superstep parallelism + our SubagentPool is enough; LangGraph Platform is overkill |
| Direct Anthropic API in v1 | Bedrock-only for cost focus; revisit if eval shows a clear Bedrock gap |
| Hand-curated golden eval answers | Recording from existing tool is faster and more representative than hand-authoring |
| Single-judge LLM eval | Self-preference bias well documented; heterogeneous panel from day one |

## Traceability

| Requirement | Phase | Status |
|-------------|-------|--------|
| INFRA-01 | Phase 1 | Pending |
| INFRA-02 | Phase 1 | Pending |
| INFRA-03 | Phase 1 | Pending |
| INFRA-04 | Phase 1 | Pending |
| INFRA-05 | Phase 1 | Pending |
| INFRA-06 | Phase 1 | Pending |
| BED-01 | Phase 1 | Pending |
| VAULT-01 | Phase 1 | Pending |
| VAULT-02 | Phase 1 | Pending |
| VAULT-03 | Phase 1 | Pending |
| VAULT-04 | Phase 1 | Pending |
| VAULT-05 | Phase 1 | Pending |
| VAULT-06 | Phase 1 | Pending |
| VAULT-07 | Phase 1 | Pending |
| MCP-05 | Phase 1 | Pending |
| MCP-08 | Phase 1 | Pending |
| BED-02 | Phase 2 | Pending |
| BED-03 | Phase 2 | Pending |
| BED-04 | Phase 2 | Pending |
| BED-05 | Phase 2 | Pending |
| SUB-01 | Phase 2 | Pending |
| SUB-02 | Phase 2 | Pending |
| SUB-03 | Phase 2 | Pending |
| SUB-04 | Phase 2 | Pending |
| SUB-05 | Phase 2 | Pending |
| SUB-06 | Phase 2 | Pending |
| SUB-07 | Phase 2 | Pending |
| OBS-01 | Phase 2 | Pending |
| OBS-02 | Phase 2 | Pending |
| OBS-03 | Phase 2 | Pending |
| SEARCH-01 | Phase 3 | Pending |
| SEARCH-02 | Phase 3 | Pending |
| SEARCH-03 | Phase 3 | Pending |
| SEARCH-04 | Phase 3 | Pending |
| SEARCH-05 | Phase 3 | Pending |
| SEARCH-06 | Phase 3 | Pending |
| CMD-04 | Phase 3 | Pending |
| CMD-07 | Phase 3 | Pending |
| CMD-08 | Phase 3 | Pending |
| MCP-02 | Phase 3 | Pending |
| MCP-04 | Phase 3 | Pending |
| MCP-06 | Phase 3 | Pending |
| MCP-07 | Phase 3 | Pending |
| CLI-01 | Phase 3 | Pending |
| CLI-02 | Phase 3 | Pending |
| CLI-03 | Phase 3 | Pending |
| CLI-04 | Phase 3 | Pending |
| CLI-05 | Phase 3 | Pending |
| CLI-06 | Phase 3 | Pending |
| CLI-07 | Phase 3 | Pending |
| EVAL-01 | Phase 4 | Pending |
| EVAL-02 | Phase 4 | Pending |
| EVAL-03 | Phase 4 | Pending |
| EVAL-04 | Phase 4 | Pending |
| EVAL-05 | Phase 4 | Pending |
| EVAL-06 | Phase 4 | Pending |
| EVAL-07 | Phase 4 | Pending |
| EVAL-08 | Phase 4 | Pending |
| EVAL-09 | Phase 4 | Pending |
| EVAL-10 | Phase 4 | Pending |
| CMD-01 | Phase 5 | Complete |
| CMD-02 | Phase 5 | Complete |
| CMD-03 | Phase 5 | Complete |
| CMD-05 | Phase 5 | Complete |
| CMD-06 | Phase 5 | Complete |
| MCP-01 | Phase 5 | Complete |
| MCP-03 | Phase 5 | Complete |

**Coverage:**
- v1 requirements: 67
- Mapped to phases: 67
- Unmapped: 0

---
*Requirements defined: 2026-05-13*
*Last updated: 2026-05-13 after roadmap creation*
