# Phase 1: Infrastructure, Vault IO, and MCP Skeleton - Context

**Gathered:** 2026-05-13
**Status:** Ready for planning

<domain>
## Phase Boundary

This phase delivers the foundation everything else assumes:

1. A `uv` workspace correctly tiered into `cores/*` (shared building blocks) and `agents/*` (agent packages), scaffolded with **only** the members Phase 1 actually needs.
2. Real AWS Bedrock connectivity proven end-to-end via `make_llm("haiku").invoke("ping")`, with cross-region inference-profile IAM verified and an actionable error path when permissions are missing.
3. A `cores/vault-io` package that reads existing lattice-wiki vaults and writes them back byte-identical — gated by a round-trip golden test against a real-vault fixture committed to the repo.
4. An MCP stdio server skeleton (`code-wiki-mcp`) that registers a single `wiki_ping` debug tool and is provably stdout-clean under subprocess capture — proving the JSON-RPC framing is intact before any real tool logic lands.

**Out of scope this phase:** any of the 5 commands (init/scan/ingest/query/lint/log), the subagent runtime, hybrid search, eval harness, full ModelRegistry. Those land in later phases against the foundation built here.

</domain>

<decisions>
## Implementation Decisions

### Workspace Layout & Tier Naming
- **D-01: Top-level tier name is `cores/`** (not `packages/`). Workspace members: `cores/*` + `agents/*`. CLAUDE.md "Workspace layout" section is out of date and MUST be updated as part of Phase 1 to match — list this as an explicit planner task.
- **D-02: Vault IO lives at `cores/vault-io`** as a shared core (not inside `agents/code-wiki-agent/`), to future-proof for a second agent that touches vaults in v2. No public API stability promised in v1 — only one consumer.
- **D-03: Phase 1 scaffolds three workspace members only** — `cores/vault-io`, `cores/model-adapter`, `agents/code-wiki-agent`. Do NOT scaffold `cores/subagent-runtime` (Phase 2) or `cores/eval-harness` (Phase 4) in this phase — they get created by their owning phases.
- **D-04: Port style for lattice-wiki-core modules = verbatim file copy** into `cores/vault-io/src/vault_io/`. No path-dep on `~/Personal/lattice/packages/lattice-wiki-core`, no git submodule. Accept that upstream drift is on the human to track; lattice-wiki-core is v0.4.0 and stable.

### Vault IO — What Gets Ported
Modules to port from `/Users/pat/Personal/lattice/packages/lattice-wiki-core/src/lattice_wiki_core/`:
- `layout_io.py` — hand-rolled YAML emitter (VAULT-02; **must** preserve whitespace/ordering byte-identical)
- Wikilink placeholder predicate (commits `9502c45` + `9388cdd`) — VAULT-06
- Frontmatter reader using `python-frontmatter` only (no PyYAML round-trip) — VAULT-03
- Truncated-frontmatter handling matching `lattice-wiki-core` commit `ae6872e` — VAULT-05
- Container detection — VAULT-07
- `_workspace.py` (workspace path resolution) — VAULT-07
- Token counter (uses `tiktoken`, kept as-is for now) — VAULT-07
- Index generator, log appender, graph analyzer — VAULT-07
- Monorepo scan, vault initializer — VAULT-07 (port files in Phase 1; the command-level glue in `scan`/`init` lands in Phase 5)

### Round-Trip Fixture Strategy
- **D-05: Round-trip fixture vault lives at `tests/fixtures/round-trip-vault/`** — committed to the repo, copied as-is from `~/Personal/lattice/wiki/`, **no sanitization step**. The wiki content is not sensitive enough to justify the maintenance cost of a sanitization script.
- **D-06: Env-var override `CODE_WIKI_REAL_VAULT_PATH`** points the test at a live vault for richer local runs. CI uses the committed snapshot; Pat can point at the real vault to catch edge cases the snapshot misses.
- **D-07: Truncated-frontmatter behavior (VAULT-05) gets its own dedicated test case**, not folded into the main round-trip test. The fixture page deliberately has a missing closing `---` and asserts the parser emits a stderr warning + skips the page rather than crashing.

### Bedrock IAM Verification (BED-01)
- **D-08: Two artifacts ship in Phase 1:**
  1. Pytest integration test at `agents/code-wiki-agent/tests/integration/test_bedrock_iam.py` — marked `@pytest.mark.integration`, skipped unless `CODE_WIKI_RUN_INTEGRATION=1`. Calls `make_llm("haiku").invoke("ping")` against real Bedrock.
  2. Standalone diagnostic script at `scripts/verify_bedrock_iam.py` — what Pat runs first on a new account to confirm permissions before touching anything else.
- **D-09: Actionable-ARN error path:** `make_llm()` wraps `invoke()` in `try/except botocore.exceptions.ClientError`. On `AccessDeniedException`, raise a custom `BedrockAccessDenied` exception whose message includes:
  - The cross-region inference-profile ARN we attempted (resolved from `models.toml`)
  - The IAM action required (`bedrock:InvokeModel`)
  - The underlying foundation-model ARNs the profile resolves to (best-effort — derive from the profile name pattern)
  No pre-flight `bedrock:ListInferenceProfiles` call — keep the failure path self-contained to the invoke attempt.

### Model Adapter v0 (Phase 1 minimum)
- **D-10: `cores/model-adapter` ships with a tiny `models.toml`** containing two entries: a `haiku` role and a `sonnet` role, each pointing at a cross-region inference-profile ARN. A `make_llm(role_or_id) -> ChatBedrockConverse` loader function reads this file. Phase 2 extends the same file/loader for the full `ModelRegistry` (BED-02..04) — no rewrite, just additions.
- **D-11: No hardcoded model IDs anywhere in Python code** — even in Phase 1, BED-04's "no hardcoded IDs" rule applies from day one. All IDs live in `models.toml`.
- **D-12: Specific Bedrock model IDs are Claude's discretion.** Researcher confirms the current cross-region inference-profile ARNs for Haiku 4.5 and Sonnet 4.6 against Pat's account before committing. Defaults to: `us.anthropic.claude-haiku-4-5-*` for `haiku`, `us.anthropic.claude-sonnet-4-6-*` for `sonnet` — researcher verifies and adjusts if Bedrock's current naming differs.

### MCP Skeleton
- **D-13: FastMCP server registers exactly one tool in Phase 1: `wiki_ping`.** It returns a structured response (e.g., `{"status": "pong", "echo": <input>}`) and stays in the production tool list as a debugging utility (kept across phases). Schema is fully typed via Pydantic.
- **D-14: Server entry point is `code-wiki-mcp`** (shorter than `code-wiki-agent-mcp`). **NOTE:** this contradicts REQUIREMENTS.md MCP-07 which says `code-wiki-agent-mcp`. Pat's call wins; planner task: amend MCP-07 in REQUIREMENTS.md as part of Phase 1.
- **D-15: Stderr-only enforcement uses a module-init guard** in `code_wiki_mcp/server.py`: on import, rebind `sys.stdout` to a strict writer that raises if anything other than the FastMCP JSON-RPC layer writes to it. Any stray `print()` or library-logging-to-stdout fails loudly in tests. Belt-and-suspenders with the subprocess test.
- **D-16: Stdout-cleanliness test** at `agents/code-wiki-agent/tests/integration/test_mcp_stdio.py`. Spawns `uv run code-wiki-mcp` as a subprocess via `subprocess`/`pexpect`, sends `initialize` + `tools/call wiki_ping` over stdin, reads stdout line-by-line, `json.loads()` every line, asserts each is valid JSON-RPC. Any non-JSON byte fails the test. Runs in CI by default — no Bedrock needed for `wiki_ping`.

### Pre-flight (locked elsewhere, repeated for planner clarity)
- `uv` workspace root has no `[project]` table; members declared via `[tool.uv.workspace]` with `members = ["cores/*", "agents/*"]`.
- Python ≥ 3.11 (deepagents floor).
- `python-frontmatter` reads only; **all writes** route through the ported `layout_io.py` emitter (VAULT-03).
- MIT license, top-level README, `.gitignore`, `pre-commit` with ruff (+ either black or `ruff format`). Researcher picks the exact tool combo during research.
- GitHub Actions CI scaffold: `uv sync` + lint + unit tests on push; eval suite is a separate workflow, non-blocking.

### Claude's Discretion
- **D-12 above** — exact inference-profile ARNs in `models.toml`. Researcher confirms current Bedrock cross-region profile naming.
- Pre-commit tool combo (ruff alone, ruff + black, ruff + ruff-format, etc.) — researcher picks based on current consensus.
- Whether `wiki_ping`'s schema accepts free-form input or a fixed enum — planner decides based on what makes the FastMCP wiring most exemplary for later tools to copy.
- CI matrix shape (3.11 only vs 3.11 + 3.12; linux only vs linux + mac) — planner picks based on cost vs coverage.

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Project Planning
- `/Users/pat/Personal/deep-agents/.planning/ROADMAP.md` §"Phase 1" — phase goal, success criteria, requirement mapping
- `/Users/pat/Personal/deep-agents/.planning/REQUIREMENTS.md` §"Infrastructure" + §"Bedrock & Model Routing" + §"Vault IO" + §"MCP Server Surface" — full requirement text for INFRA-01..06, BED-01, VAULT-01..07, MCP-05, MCP-08
- `/Users/pat/Personal/deep-agents/.planning/STATE.md` §"Key Decisions" — vault round-trip golden test as Phase 1 gate; python-frontmatter read-only + ported emitter writes; Bedrock IAM cross-region inference profile verified in Phase 1
- `/Users/pat/Personal/deep-agents/.planning/PROJECT.md` §"Constraints" + §"Key Decisions" — Bedrock-only, MCP primary surface, read-compatible vaults, uv tiered monorepo

### Project Research (already produced)
- `/Users/pat/Personal/deep-agents/.planning/research/STACK.md` — full tech stack rationale (versions, alternatives considered, why each chosen)
- `/Users/pat/Personal/deep-agents/.planning/research/ARCHITECTURE.md` — architecture overview
- `/Users/pat/Personal/deep-agents/.planning/research/PITFALLS.md` — known pitfalls (read before research)
- `/Users/pat/Personal/deep-agents/.planning/research/FEATURES.md` — feature inventory
- `/Users/pat/Personal/deep-agents/.planning/research/SUMMARY.md` — research synthesis
- `/Users/pat/Personal/deep-agents/CLAUDE.md` — project tech-stack reference doc (NOTE: "Workspace layout" section uses `packages/*` which is OUT OF DATE; Phase 1 will replace `packages` with `cores`)

### Source-of-Truth: lattice-wiki-core (modules being ported verbatim)
- `/Users/pat/Personal/lattice/packages/lattice-wiki-core/src/lattice_wiki_core/layout_io.py` — hand-rolled YAML emitter (VAULT-02); must be ported byte-identical in behavior
- `/Users/pat/Personal/lattice/packages/lattice-wiki-core/src/lattice_wiki_core/detect_containers.py` — container detection (VAULT-07)
- `/Users/pat/Personal/lattice/packages/lattice-wiki-core/src/lattice_wiki_core/_workspace.py` — workspace path resolution (VAULT-07)
- `/Users/pat/Personal/lattice/packages/lattice-wiki-core/src/lattice_wiki_core/init_vault.py` — vault initializer (port file in Phase 1; command glue in Phase 5)
- `/Users/pat/Personal/lattice/packages/lattice-wiki-core/src/lattice_wiki_core/scan_monorepo.py` — monorepo scan (port file in Phase 1; command glue in Phase 5)
- `/Users/pat/Personal/lattice/packages/lattice-wiki-core/src/lattice_wiki_core/append_log.py` — log appender (VAULT-07)
- `/Users/pat/Personal/lattice/packages/lattice-wiki-core/src/lattice_wiki_core/update_index.py` — index generator (VAULT-07)
- `/Users/pat/Personal/lattice/packages/lattice-wiki-core/src/lattice_wiki_core/graph_analyzer.py` — graph analyzer (VAULT-07)
- `/Users/pat/Personal/lattice/packages/lattice-wiki-core/src/lattice_wiki_core/update_tokens.py` — token counter (VAULT-07)
- `/Users/pat/Personal/lattice/packages/lattice-wiki-core/src/lattice_wiki_core/wiki_search.py` — read only (BM25 stays out; replaced by `bm25s` in Phase 3)
- Git history of `/Users/pat/Personal/lattice/packages/lattice-wiki-core/` at commits `9502c45` + `9388cdd` (wikilink placeholder predicate — VAULT-06) and `ae6872e` (truncated frontmatter behavior — VAULT-05)

### External Documentation
- AWS Bedrock cross-region inference profiles: https://docs.aws.amazon.com/bedrock/latest/userguide/inference-profiles-support.html
- AWS Bedrock CountTokens API: https://docs.aws.amazon.com/bedrock/latest/userguide/count-tokens.html (for future token-pre-flight in Phase 2/3)
- MCP spec (build-server): https://modelcontextprotocol.io/docs/develop/build-server — stdio transport pattern
- `langchain-aws` ChatBedrockConverse: Context7 `/langchain-ai/langchain-aws`
- `uv` workspace docs: Context7 `/astral-sh/uv` — workspace pyproject.toml patterns

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets (from lattice-wiki-core, to be copied verbatim)
- `layout_io.py` — handles all layout-block read/write; the hand-rolled emitter is non-negotiable (any PyYAML re-normalization breaks vault parity)
- `detect_containers.py` — monorepo container detection (`package.json`, `pyproject.toml`, `Cargo.toml`, `go.mod`, `pnpm-workspace.yaml`)
- Wikilink placeholder predicate in `lint/` (commits `9502c45` + `9388cdd`) — must be carried into `cores/vault-io` so future Phase 5 lint inherits it correctly
- Pytest patterns in `/Users/pat/Personal/lattice/packages/lattice-wiki-core/tests/` — 37 pytest files; reasonable reference for how vault IO is currently tested. Don't copy tests blindly; copy patterns where they add value.

### Established Patterns (project-side)
- This is a fresh codebase — no prior project patterns to match. Phase 1 *establishes* them: tier naming, per-package pyproject shape, test layout, error-message conventions.
- Three patterns Phase 1 explicitly creates and downstream phases should follow:
  1. **Workspace member structure:** `<member>/pyproject.toml` + `<member>/src/<package_name>/` + `<member>/tests/` with per-member `testpaths` (INFRA-03 — avoids pytest collection collisions).
  2. **Cross-package imports:** workspace members are auto-editable in `uv` workspaces; import directly as `from vault_io import ...` — no path manipulation.
  3. **Stderr-only logging:** every Python module that runs under MCP stdio must use `sys.stderr` (or the standard `logging` module configured to a stderr handler). The module-init guard catches anything that slips through.

### Integration Points
- `cores/model-adapter` is consumed by:
  - Phase 1: `scripts/verify_bedrock_iam.py` (diag) and the integration test.
  - Phase 2: `cores/subagent-runtime` (full `ModelRegistry` keyed by role).
  - Phases 3–5: every command via subagent role resolution.
- `cores/vault-io` is consumed by:
  - Phase 1: round-trip golden test only.
  - Phase 3: `query` command (reads `index.md`, reads page bodies).
  - Phase 5: `init`/`scan`/`ingest`/`lint`/`log` commands (all write paths route through the ported emitter).
- `agents/code-wiki-agent` is the only agent in v1; ships both the MCP entry point (`code-wiki-mcp`) and the headless CLI (`code-wiki-agent`, Phase 3+).
- MCP server entry point registered in `agents/code-wiki-agent/pyproject.toml` under `[project.scripts]` so `uv run code-wiki-mcp` works from a fresh clone (INFRA-06 + MCP-07).

</code_context>

<specifics>
## Specific Ideas

- The phrase "verbatim port" means: read the source file, copy it into `cores/vault-io/src/vault_io/`, adjust imports (`lattice_wiki_core` → `vault_io`), and verify it still works against the round-trip fixture. Behavior is byte-identical; structure may be reorganized into a cleaner package layout inside `vault_io/` (e.g., subpackages for `layout/`, `links/`, `containers/`).
- The round-trip test is the **gate** — no other vault-write code lands in Phase 1 until this passes against the committed fixture. This is the single most important deliverable of the phase.
- `wiki_ping` stays shipped in production. It's a debugging tool, not a test artifact. Give it a proper schema and a description that says "Returns pong; used to verify MCP wiring".
- The CLAUDE.md "Workspace layout" section update is part of Phase 1 scope, not a deferred item. Same for the REQUIREMENTS.md MCP-07 amendment.

</specifics>

<deferred>
## Deferred Ideas

- **Full `ModelRegistry` with per-role `max_tokens`/`max_concurrency` + `models.toml` schema for 7 logical roles (librarian, scanner, linter, ingestor, synthesizer, judge_a, judge_b)** — Phase 2 (BED-02..04). Phase 1 ships only the 2-entry minimal shape.
- **Token + cost accounting per invocation (BED-05)** — Phase 2.
- **Pre-flight `bedrock:ListInferenceProfiles` for richer IAM diagnostics** — not added in v1; the failure-path error message is good enough. Revisit if Pat hits IAM surprises in practice.
- **Sanitization script for fixture vault** — not adopted; we commit real-vault content as-is. Revisit only if a privacy concern emerges.
- **CI multi-Python-version matrix (3.11 + 3.12)** — planner's call; if deferred, can land in a later infra-tidy phase.
- **`bedrock:ListInferenceProfiles` as a startup probe in the MCP server** — out of v1 scope (would couple server startup to a Bedrock call).

</deferred>

---

*Phase: 1-Infrastructure, Vault IO, and MCP Skeleton*
*Context gathered: 2026-05-13*
