---
phase: 01
type: walking-skeleton
created: 2026-05-13
---

# Walking Skeleton — Phase 1

The thinnest end-to-end slice that proves every architectural seam Phase 1 establishes. Every plan's `must_haves` ladder up to one or more rows of the demos table below.

---

## Architectural Decisions (locked here; later phases build on these without renegotiation)

| Area | Decision | Source |
|------|----------|--------|
| Monorepo manager | `uv` workspaces; root `pyproject.toml` has no `[project]` table; members declared via `[tool.uv.workspace] members = ["cores/*", "agents/*"]` | D-01, RESEARCH §Pattern 1 |
| Tier names | `cores/` (shared) and `agents/` (agent packages) | D-01 |
| Phase 1 members | `cores/vault-io`, `cores/model-adapter`, `agents/code-wiki-agent` (3 only — no `cores/subagent-runtime` or `cores/eval-harness` until their phases) | D-03 |
| Python floor | 3.11+ (deepagents requirement) | INFRA-06 |
| Build backend | `uv_build>=0.11.14,<0.12` per-member | RESEARCH §Pattern 2 |
| Lint / format | `ruff` only (lint + format); no black | RESEARCH §CI-and-Pre-Commit |
| CI | GitHub Actions: `uv sync` + `ruff check` + `ruff format --check` + per-member pytest (integration skipped) | INFRA-05 |
| Pre-commit | `astral-sh/ruff-pre-commit` v0.15.12 with `ruff` + `ruff-format` hooks | RESEARCH §CI |
| License | MIT | INFRA-04 |
| Model provider | AWS Bedrock only; `ChatBedrockConverse`; cross-region inference profiles | RESEARCH §Bedrock |
| Model registry shape (v0) | `cores/model-adapter/models.toml` with `[roles.haiku]` + `[roles.sonnet]`; `make_llm(role) -> ChatBedrockConverse` | D-10, D-11 |
| Vault read | `python-frontmatter` only | D-03, VAULT-03 |
| Vault write | Hand-rolled emitter (`layout_io.py`) + raw-string manipulation (`update_tokens.py`); never `frontmatter.dumps()` | D-03, VAULT-02 |
| Vault path resolution | Explicit `Path` arg or `CODE_WIKI_REAL_VAULT_PATH` env var; no `lattice_workspace` discovery | RESEARCH §Pitfall 5 |
| Round-trip fixture | Real-vault snapshot at `cores/vault-io/tests/fixtures/round-trip-vault/` — committed as-is from `/Users/pat/Personal/lattice/lattice/wiki/`, no sanitization | D-05 |
| MCP server entry point | `code-wiki-mcp` (NOT `code-wiki-agent-mcp` — REQUIREMENTS MCP-07 amended per D-14) | D-14 |
| MCP transport | stdio only; `mcp.run(transport="stdio")` | MCP-08, RESEARCH §Pattern 6 |
| MCP FastMCP source | `from mcp.server.fastmcp import FastMCP` (NOT the standalone `fastmcp` PyPI package) | RESEARCH §Pitfall 2 |
| Stdout discipline | `_StdoutGuard` sentinel installed before any other import in `server.py`; raises on any non-FastMCP stdout write | D-15, MCP-05 |
| Phase 1 MCP tools | Exactly one: `wiki_ping` (kept across phases as a debugging utility) | D-13 |
| Stderr-only logging | `logging.basicConfig(stream=sys.stderr)` in `server.py`; all vault-io warnings use `print(..., file=sys.stderr)` | MCP-05 |
| Per-member testpaths | Every member's `pyproject.toml` sets `testpaths = ["tests"]` + `--import-mode=importlib` to prevent cross-member fixture bleed | INFRA-03 |
| Bedrock IAM diagnostic | Two artifacts: integration test (`@pytest.mark.integration`, gated by `CODE_WIKI_RUN_INTEGRATION=1`) + standalone script (`scripts/verify_bedrock_iam.py`) | D-08 |
| IAM error path | `make_llm()` wraps invoke; on `AccessDeniedException` raises `BedrockAccessDenied` whose message includes the model ARN attempted, `bedrock:InvokeModel`, and the foundation-model ARN pattern | D-09 |

---

## End-to-End Demos (the "done" criteria)

| # | Demo Command | Proves | Owning Plan |
|---|--------------|--------|-------------|
| 1 | `uv sync` produces a single `uv.lock` at repo root | INFRA-01, INFRA-02 | 01-01 |
| 2 | `uv run code-wiki-agent --help` exits 0 from a fresh clone | INFRA-06 | 01-01 |
| 3 | `uv run --package vault-io pytest --collect-only` lists vault-io tests only (no `code_wiki_*` leakage) | INFRA-03 | 01-01 |
| 4 | `ruff check .` and `ruff format --check .` both exit 0; pre-commit hook installs | INFRA-04 | 01-01 |
| 5 | GitHub Actions `ci.yml` workflow file exists and runs the lint+test gate on push | INFRA-05 | 01-01 |
| 6 | `CODE_WIKI_RUN_INTEGRATION=1 uv run --package code-wiki-agent pytest tests/integration/test_bedrock_iam.py` invokes `us.anthropic.claude-haiku-4-5-20251001-v1:0` against real Bedrock and returns non-empty content | BED-01 | 01-02 |
| 7 | `uv run python scripts/verify_bedrock_iam.py` either prints "OK: <pong>" to stderr (and exits 0) or prints a `BedrockAccessDenied` message containing the attempted ARN + `bedrock:InvokeModel` (and exits 1) | BED-01 | 01-02 |
| 8 | Round-trip: `uv run --package vault-io pytest tests/test_round_trip.py` reads-then-writes every fixture page via `update_tokens.update_vault`; second pass produces empty `git diff` against the original fixture | VAULT-01..04 | 01-03 |
| 9 | `uv run --package vault-io pytest tests/test_truncated_frontmatter.py` — page missing closing `---` returns `("skipped", 0)`, file bytes unchanged, stderr contains `"no closing frontmatter fence"` | VAULT-05 | 01-03 |
| 10 | `uv run --package vault-io pytest tests/test_wikilink_predicate.py` — `_is_placeholder_target("wiki/...")` → True; `_is_placeholder_target("wiki/foo")` → False | VAULT-06 | 01-03 |
| 11 | `uv run --package vault-io pytest -k "container or scan or index"` — container detection, monorepo scan, index/log/graph/token modules importable + smoke-callable | VAULT-07 | 01-03 |
| 12 | `uv run code-wiki-mcp` launches via subprocess, accepts `initialize` + `tools/call wiki_ping` on stdin, returns `{"status":"pong","echo":"<input>"}`; every stdout line `json.loads()` as valid JSON-RPC | MCP-05, MCP-08 | 01-04 |
| 13 | An in-process stray `print("oops")` after `_StdoutGuard` is installed raises `RuntimeError` (belt-and-suspenders test) | MCP-05 | 01-04 |
| 14 | CLAUDE.md "Workspace layout" section uses `cores/` (not `packages/`); REQUIREMENTS.md MCP-07 references `code-wiki-mcp` (not `code-wiki-agent-mcp`) | Doc consistency per D-01, D-14 | 01-01 |

---

## Wave Structure

| Wave | Plans | Parallelism Notes |
|------|-------|-------------------|
| 1 | 01-01 (workspace + CLI + open-source hygiene + doc fixes) | Bootstrap — must land first; creates pyproject files, ruff config, CI, all three member skeletons |
| 2 | 01-02 (Bedrock ping), 01-03 (Vault round-trip) | Run in parallel — disjoint `files_modified` (model-adapter/* vs vault-io/*) |
| 3 | 01-04 (MCP stdio surface + wiki_ping) | Depends on 01-01 (agent package scaffold) for `agents/code-wiki-agent/src/code_wiki_mcp/`; does not depend on 01-02 or 01-03 substantively, but imports `model_adapter` for type discipline so we sequence after 01-02 to avoid speculative imports |

---

## Out-of-Scope Reminders (deferred to later phases — do not plan)

- `cores/subagent-runtime` and any fan-out primitives (Phase 2)
- Full `ModelRegistry` with 7 roles + `max_tokens`/`max_concurrency` (Phase 2)
- Token + cost accounting per invocation (Phase 2)
- Hybrid search / embeddings (Phase 3)
- Any of the 5 user-facing commands (`init`, `scan`, `ingest`, `query`, `lint`, `log`) — only the port of their supporting vault-io modules ships in Phase 1
- `cores/eval-harness` (Phase 4)
- MCP resources, prompts, sampling, SSE / streamable-HTTP (MCP-08 anti-features)

---

*Skeleton locked: 2026-05-13. Phase 1 is "done" when all 14 demos above pass on a fresh clone.*
