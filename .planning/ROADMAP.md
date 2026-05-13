# Roadmap: deep-agents / code-wiki-agent

**Project:** deep-agents (v1 = code-wiki-agent)
**Milestone:** v1
**Created:** 2026-05-13
**Granularity:** Standard (5 phases)
**Coverage:** 67/67 v1 requirements mapped

---

## Phases

- [ ] **Phase 1: Infrastructure, Vault IO, and MCP Skeleton** — Monorepo scaffold, Bedrock IAM proven, vault round-trip fidelity locked, MCP server wired for stderr-only output
- [ ] **Phase 2: Subagent Fan-Out Runtime** — SubagentPool with partial-failure handling, per-role throttle controls, and structured trace output established as shared infrastructure
- [ ] **Phase 3: Query Vertical Slice + Hybrid Search** — `query` command running end-to-end through both MCP and headless CLI on Bedrock, with hybrid BM25+embedding search
- [ ] **Phase 4: Eval Harness** — Cost-frontier measurement infrastructure against the working query command; heterogeneous judge panel; fixture corpus committed
- [ ] **Phase 5: Remaining Commands** — Full lattice-wiki parity: `log`, `init`, `scan`, `ingest`, `lint` via MCP and headless CLI

---

## Phase Details

### Phase 1: Infrastructure, Vault IO, and MCP Skeleton
**Goal:** The monorepo is correctly scaffolded, Bedrock connectivity is proven end-to-end with the right IAM setup, vault IO passes round-trip fidelity on real vault pages, and the MCP server skeleton enforces stderr-only output before any tool logic is wired.
**Mode:** mvp
**Depends on:** Nothing (first phase)
**Requirements:** INFRA-01, INFRA-02, INFRA-03, INFRA-04, INFRA-05, INFRA-06, BED-01, VAULT-01, VAULT-02, VAULT-03, VAULT-04, VAULT-05, VAULT-06, VAULT-07, MCP-05, MCP-08

**Success Criteria** (what must be TRUE):
1. `uv run code-wiki-agent --help` works from a fresh clone; `uv sync` produces a single shared `uv.lock`; per-member `pytest` runs only that member's tests with no fixture bleed
2. `make_llm("haiku").invoke("ping")` succeeds against real Bedrock using the cross-region inference profile ARN — if IAM is missing, the error message includes the exact ARN resource to add
3. `git diff` is empty after parsing-then-writing every page in a real lattice-wiki vault (round-trip golden gate); pages with truncated frontmatter (missing closing `---`) are skipped with a stderr warning, not a crash
4. A subprocess capture of the MCP server's stdout contains only valid JSON-RPC lines — no startup prints, no library debug output, not a single non-JSON byte

**Plans:** 4 plans

Plans:
- [x] 01-01-PLAN.md — Workspace scaffold + open-source hygiene + CLI stub (INFRA-01..06)
- [x] 01-02-PLAN.md — Bedrock ping: model-adapter loader + IAM verification (BED-01)
- [x] 01-03-PLAN.md — Vault round-trip: port lattice-wiki-core modules + golden gate (VAULT-01..07)
- [x] 01-04-PLAN.md — MCP stdio surface: FastMCP server + wiki_ping + stdout discipline (MCP-05, MCP-08)

---

### Phase 2: Subagent Fan-Out Runtime
**Goal:** The shared `SubagentPool` in `cores/subagent-runtime` is correct, throttle-safe, and observable — with all deepagents bug mitigations in place — before any command uses fan-out. Structured trace output is designed here, not retrofitted.
**Mode:** mvp
**Depends on:** Phase 1
**Requirements:** BED-02, BED-03, BED-04, BED-05, SUB-01, SUB-02, SUB-03, SUB-04, SUB-05, SUB-06, SUB-07, OBS-01, OBS-02, OBS-03

**Success Criteria** (what must be TRUE):
1. An integration test dispatches 4 parallel subagents where 1 intentionally raises an exception; the result contains 3 successes and 1 per-item error — no sibling cancellation, no silent truncation
2. A subagent that requires 30 sequential tool calls completes without `GraphRecursionError`; every subagent invocation site passes an explicit `recursion_limit` in config
3. 5 parallel subagents running simultaneously against real Bedrock with role-sized `max_tokens` (librarian: 2000, scanner: 500, linter: 3000) produce no `ThrottlingException`
4. Every fan-out call produces a structured JSONL trace record (role, model, prompt hash, item id, status, latency_ms, tokens_in, tokens_out, cost_usd) written to `.code-wiki/traces/`; `code-wiki-agent trace <file>` renders it as a human-readable timeline
5. `ModelRegistry` resolves each logical role name to a concrete model ID from `models.toml`; the file ships with sensible Bedrock defaults for all defined roles

**Plans:** TBD

---

### Phase 3: Query Vertical Slice + Hybrid Search
**Goal:** The `query` command works end-to-end on real Bedrock — hybrid BM25+embedding search, librarian fan-out, synthesis — accessible via both the MCP server (`wiki_query` tool) and the headless CLI (`code-wiki-agent query`), with both delivery surfaces sharing a single implementation.
**Mode:** mvp
**Depends on:** Phase 2
**Requirements:** SEARCH-01, SEARCH-02, SEARCH-03, SEARCH-04, SEARCH-05, SEARCH-06, CMD-04, CMD-07, CMD-08, MCP-02, MCP-04, MCP-06, MCP-07, CLI-01, CLI-02, CLI-03, CLI-04, CLI-05, CLI-06, CLI-07

**Success Criteria** (what must be TRUE):
1. `code-wiki-agent query "What does the middleware pipeline do?"` against a real lattice-wiki vault returns a coherent answer with `[[wikilink]]` citations and code-path references — output comparable in depth and structure to the current lattice-wiki result
2. The DeepAgents CLI can invoke `wiki_query` via MCP and receive a structured result; the tool description and input schema are sufficient without external documentation
3. Hybrid search (BM25 + Bedrock embedding) returns top-K results with both raw scores (BM25/cosine) and fused score visible in `--json` output; the embedding index persists locally and rebuilds only for changed pages
4. The `--json` flag and state-gate mechanism are present on the `query` subcommand and honored by both MCP and CLI surfaces; `code-wiki-agent-mcp` launches as a stdio subprocess from the registered entry point
5. An end-to-end integration test runs `query` in headless CLI mode against a committed fixture vault and asserts the answer contains at least one valid `[[wikilink]]` citation

**Plans:** TBD

---

### Phase 4: Eval Harness
**Goal:** `cores/eval-harness` is a standalone package with a working baseline recorder, model sweep runner, heterogeneous judge panel, and cost-frontier report — all validated against the working `query` command before any other command's baseline is committed.
**Mode:** mvp
**Depends on:** Phase 3
**Requirements:** EVAL-01, EVAL-02, EVAL-03, EVAL-04, EVAL-05, EVAL-06, EVAL-07, EVAL-08, EVAL-09, EVAL-10

**Success Criteria** (what must be TRUE):
1. The fixture corpus (2–3 small test repos with pre-built wikis) is committed under `tests/fixtures/` and the baseline recorder produces a snapshot of the current lattice-wiki `query` output that is reproducible: re-recording with the same pinned model ARN produces an identical content hash
2. A model sweep over at least 3 Bedrock models for the librarian role produces a cost-frontier table showing at least 2 models at different quality/cost tradeoffs — the cheaper model's score is within a measurable margin of the more expensive one
3. The judge panel includes at least one Claude judge and one non-Claude judge (e.g., Nova Pro or Llama 3 70B); swapping answer position changes scores by less than 5%, confirming no significant position bias
4. Structural metrics (wikilinks resolve, all packages present, frontmatter valid, output matches expected JSON schema) pass on every run without requiring LLM calls; `@pytest.mark.eval` marks eval cases as opt-in and CI-skippable
5. Each eval result JSON includes the concrete model ARN (not alias), prompt hash, timestamp, and seed; a regression check raises a CI-friendly failure if quality drops below the configured threshold for any role

**Plans:** TBD

---

### Phase 5: Remaining Commands
**Goal:** Full lattice-wiki parity — all 6 commands available via both MCP and headless CLI, each with fan-out where applicable, the wikilink placeholder filter in place before lint runs, and parity tests passing against recorded lattice-wiki output.
**Mode:** mvp
**Depends on:** Phase 4
**Requirements:** CMD-01, CMD-02, CMD-03, CMD-05, CMD-06, MCP-01, MCP-03

**Success Criteria** (what must be TRUE):
1. `wiki_log` and `code-wiki-agent log` append a timestamped event to `log.md` atomically; `wiki_init` and `code-wiki-agent init` bootstrap a vault in an empty workspace matching lattice-wiki's init output structure
2. `wiki_scan` and `code-wiki-agent scan` walk a fixture monorepo, diff packages vs vault, create/update stubs via scanner fan-out, and emit a structured `{added, updated, deleted}` JSON alongside the human log entry
3. `wiki_lint` and `code-wiki-agent lint` run the mechanical pass (orphans, broken links honoring placeholder filter, stale pages, missing frontmatter, code-drift) AND the semantic fan-out pass; `[[wiki/...]]` and `[[work/<slug>]]` patterns produce zero broken-link violations on the real vault
4. All 6 MCP tools (`wiki_init`, `wiki_scan`, `wiki_ingest`, `wiki_query`, `wiki_lint`, `wiki_log`) are registered with typed Pydantic schemas and return structured MCP error responses on failure — no crash that kills the stdio session; progress notifications are emitted for long-running commands
5. Each command has a parity test: given the same fixture vault, the new tool's output matches the recorded lattice-wiki baseline on all structural metrics (wikilinks, frontmatter, package coverage)

**Plans:** TBD

---

## Progress Table

| Phase | Plans Complete | Status | Completed |
|-------|----------------|--------|-----------|
| 1. Infrastructure, Vault IO, and MCP Skeleton | 0/4 | Not started | - |
| 2. Subagent Fan-Out Runtime | 0/0 | Not started | - |
| 3. Query Vertical Slice + Hybrid Search | 0/0 | Not started | - |
| 4. Eval Harness | 0/0 | Not started | - |
| 5. Remaining Commands | 0/0 | Not started | - |

---

## Key Decisions Encoded

| Decision | Encoded In |
|----------|------------|
| SubagentPool over deepagents SubAgentMiddleware (bugs #694, #1698) | Phase 2 success criteria + SUB-02/SUB-03 assignment |
| Vault round-trip golden test gates all write-path code | Phase 1 success criterion 3 + VAULT-04 in Phase 1 |
| Structured trace output in Phase 2, not retrofitted | Phase 2 goal + SUB-06/OBS-01 in Phase 2 |
| Hybrid search (BM25 + embeddings) in v1, lands in Phase 3 | SEARCH-01..06 assigned to Phase 3 |
| Eval harness after working query, before remaining commands | Phase 4 position + dependency chain |
| lint wikilink placeholder filter before any wikilink resolver | Phase 5 success criterion 3 + VAULT-06 in Phase 1 |
| Bedrock IAM (cross-region inference profiles) is explicit Phase 1 gate | Phase 1 success criterion 2 + BED-01 in Phase 1 |
| MCP-08 (anti-features not in v1) documented in Phase 1 | MCP-08 maps to Phase 1 as a documented constraint |
