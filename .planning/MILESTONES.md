# Milestones

## v1.0 code-wiki-agent parity (Shipped: 2026-05-15)

**Phases completed:** 5 phases, 25 plans
**Timeline:** 2026-05-13 → 2026-05-15 (3 calendar days, ~12 sessions)
**Requirements:** 67/67 v1 requirements complete

**Delivered:** End-to-end `code-wiki-agent` reaches full parity with the existing `lattice-wiki` Claude Code plugin, running entirely on AWS Bedrock with within-command subagent fan-out for cost and context savings.

### Key accomplishments

- **All 6 commands shipped** on both MCP (`code-wiki-mcp` stdio server) and headless Typer CLI (`code-wiki-agent <cmd>`) surfaces, sharing a single command-implementation module: `init`, `scan`, `ingest`, `query`, `lint`, `log` (CMD-01..08, MCP-01..08, CLI-01..07).
- **`cores/subagent-runtime` → `SubagentPool.run_all()`** with partial-failure isolation (one failure ≠ sibling cancellation), per-role semaphore throttling, explicit recursion-limit propagation, and structured JSONL trace output to `.code-wiki/traces/` from day one (SUB-01..07, OBS-01..03). Powers fan-out for librarian (Phase 3), scanner (Phase 5), and 3-way linter (Phase 5).
- **`cores/vault-io`** — 11 modules ported verbatim from `lattice-wiki-core` with import surgery only; round-trip golden test green on a 148-page real-vault fixture (byte-identical write-back). `python-frontmatter` for reads only; all writes route through the ported `layout_io.py` emitter to preserve hand-rolled YAML formatting (VAULT-01..07).
- **Hybrid search**: BM25 via `bm25s` 0.3.8 + Titan Embeddings v2 in SQLite (WAL mode), sha256-keyed incremental rebuild, RRF fusion with configurable weights, raw + fused scores exposed in `--json` (SEARCH-01..06).
- **`cores/model-adapter`** — `ModelRegistry` resolves logical role names (`librarian`, `scanner`, `linter`, `ingestor`, `synthesizer`, `judge_a`, `judge_b`, etc.) to `ChatBedrockConverse` instances via a single `models.toml`. No hardcoded model IDs anywhere. `BedrockAccessDenied` raised with attempted ARN + IAM verb on permission failure (BED-01..05).
- **`cores/eval-harness`** — fixture corpus (3 repos), headless `claude -p` baseline recorder with EVAL-08 reproducibility schema, `deepeval` 4.0 integration with `AmazonBedrockModel`, heterogeneous two-judge GEval panel (`claude-sonnet-4-6` + `nova-pro-v1:0`) with position-bias check, cost-frontier sweep runner via `pytest-evals`, structural metrics (cites code path / wikilinks resolve / valid frontmatter), and a regression-check AssertionError gate (EVAL-01..10).
- **MCP stdout discipline** locked at infrastructure level — `_StdoutGuard` sentinel + subprocess JSON-RPC integrity test that asserts every stdout byte is valid framing (MCP-05).
- **`ingest` ships as ONE MCP tool** (`wiki_ingest`) with `type: Literal['source', 'work-item']` discriminator rather than two tools — cleaner schema, type-narrowing server-side, matches lattice-wiki semantics.
- **CI hygiene** — ruff lint+format clean across the workspace; `uv` single shared `uv.lock`; per-member pytest isolation; GitHub Actions wired for both CI and opt-in eval workflows (INFRA-01..06).

### Outcomes against thesis

The infrastructure to measure the project's core thesis (cost-frontier on Bedrock vs current Claude-Code-hosted plugin) shipped in this milestone; *executing* the sweep — running it against all 7 roles, picking cost-optimal models, swapping `models.toml` defaults — is the v1.1 lift.

### Known deferred items (carried into v1.1)

- **BED-01 live-Bedrock gate** — code-side acceptance passed; the live `make_llm("haiku").invoke("ping")` call against real Bedrock remains blocked on a one-time AWS account onboarding form ("Anthropic use case details") that Pat needs to complete out-of-band.
- **Cost-frontier sweep execution** — harness shipped; results pending `CODE_WIKI_RUN_EVAL=1` runs.

For full milestone detail see [`milestones/v1.0-ROADMAP.md`](milestones/v1.0-ROADMAP.md) and [`milestones/v1.0-REQUIREMENTS.md`](milestones/v1.0-REQUIREMENTS.md). For lessons learned see [`RETROSPECTIVE.md`](RETROSPECTIVE.md).

---
