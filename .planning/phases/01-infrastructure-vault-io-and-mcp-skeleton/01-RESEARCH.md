# Phase 1: Infrastructure, Vault IO, and MCP Skeleton — Research

**Researched:** 2026-05-13
**Domain:** Python monorepo scaffolding, AWS Bedrock IAM, vault IO portability, MCP stdio framing
**Confidence:** HIGH (core stack verified against live Bedrock, real vault, and official AWS docs)

---

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions

- **D-01:** Top-level tier name is `cores/` (not `packages/`). Workspace members: `cores/*` + `agents/*`. CLAUDE.md "Workspace layout" section is out of date; updating it is an explicit planner task for Phase 1.
- **D-02:** Vault IO lives at `cores/vault-io`.
- **D-03:** Phase 1 scaffolds three workspace members only: `cores/vault-io`, `cores/model-adapter`, `agents/code-wiki-agent`. No other members in Phase 1.
- **D-04:** Port style for lattice-wiki-core modules = verbatim file copy into `cores/vault-io/src/vault_io/`. No path-dep or git submodule.
- **D-05:** Round-trip fixture vault lives at `tests/fixtures/round-trip-vault/` — committed from `~/Personal/lattice/lattice/wiki/` as-is, no sanitization.
- **D-06:** `CODE_WIKI_REAL_VAULT_PATH` env-var override points tests at live vault. CI uses committed snapshot.
- **D-07:** Truncated-frontmatter (VAULT-05) gets its own dedicated test, not folded into the round-trip test.
- **D-08:** Two Bedrock IAM artifacts: integration test at `agents/code-wiki-agent/tests/integration/test_bedrock_iam.py` (skipped unless `CODE_WIKI_RUN_INTEGRATION=1`); standalone script at `scripts/verify_bedrock_iam.py`.
- **D-09:** Actionable-ARN error path: `make_llm()` wraps invoke in `try/except botocore.exceptions.ClientError`; on `AccessDeniedException` raises `BedrockAccessDenied` with the ARN, the IAM action (`bedrock:InvokeModel`), and downstream foundation-model ARNs. No pre-flight `ListInferenceProfiles`.
- **D-10:** `cores/model-adapter` ships with a minimal `models.toml` with `haiku` and `sonnet` roles. Phase 2 extends it.
- **D-11:** No hardcoded model IDs in Python code anywhere. All IDs live in `models.toml`.
- **D-12:** Exact inference-profile ARNs are researcher's call (confirmed in this document).
- **D-13:** FastMCP server registers exactly one tool in Phase 1: `wiki_ping`. Fully typed Pydantic schema.
- **D-14:** Server entry point is `code-wiki-mcp` (overrides REQUIREMENTS.md MCP-07 which said `code-wiki-agent-mcp`). Planner must amend MCP-07.
- **D-15:** Stderr-only enforcement uses a module-init guard in `code_wiki_mcp/server.py` that rebinds `sys.stdout` to a write-raising sentinel.
- **D-16:** Stdout-cleanliness test at `agents/code-wiki-agent/tests/integration/test_mcp_stdio.py`. Subprocess-launches `uv run code-wiki-mcp`, sends `initialize` + `tools/call wiki_ping`, asserts every stdout line is valid JSON-RPC.
- **Pre-flight:** Workspace root has no `[project]` table; members via `[tool.uv.workspace]` with `members = ["cores/*", "agents/*"]`. Python ≥ 3.11. MIT license, README, `.gitignore`, `pre-commit` with ruff. GitHub Actions CI.

### Claude's Discretion

- D-12: Exact inference-profile ARNs in `models.toml` (confirmed in this document).
- Pre-commit tool combo (ruff alone vs ruff+format vs ruff+black).
- Whether `wiki_ping` accepts free-form input or a fixed enum.
- CI matrix shape (3.11 only vs 3.11+3.12; linux only vs linux+mac).

### Deferred Ideas (OUT OF SCOPE)

- Full `ModelRegistry` with 7 logical roles (Phase 2).
- Token + cost accounting per invocation (Phase 2).
- Pre-flight `bedrock:ListInferenceProfiles` (not added in v1).
- Sanitization script for fixture vault.
- CI multi-Python-version matrix (planner's call).
- `bedrock:ListInferenceProfiles` as MCP server startup probe.
</user_constraints>

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| INFRA-01 | Initialize `uv` workspace at repo root with `members = ["cores/*", "agents/*"]`; root has no `[project]` table | Workspace root config pattern verified against Context7 `/astral-sh/uv` docs |
| INFRA-02 | Workspace produces a single shared `uv.lock` reproducible via `uv sync` | Workspace lock semantics verified; single-lock is the uv default |
| INFRA-03 | Each workspace member has its own `pyproject.toml` with per-member `testpaths` to avoid pytest collision | Pattern confirmed from lattice reference repo; per-member `[tool.pytest.ini_options] testpaths` shown |
| INFRA-04 | Repo is open-source-ready — MIT LICENSE, README, `.gitignore`, `pre-commit` config with ruff | ruff 0.15.12 confirmed; pre-commit pattern documented |
| INFRA-05 | CI scaffold (GitHub Actions) runs `uv sync` + lint + unit tests on push | Standard GitHub Actions pattern; environment availability confirms `uv` 0.11.7 on host |
| INFRA-06 | Python 3.11+ pinned; project boots with `uv run code-wiki-agent --help` from a fresh clone | Entry point wiring documented; `code-wiki-agent` registered in `agents/code-wiki-agent/pyproject.toml` |
| BED-01 | Verify Bedrock IAM with cross-region inference profile; fail loudly with actionable guidance | VERIFIED: both `us.anthropic.claude-haiku-4-5-20251001-v1:0` and `us.anthropic.claude-sonnet-4-6` invoke successfully in us-east-1. IAM error handling pattern documented. |
| VAULT-01 | Read existing lattice-wiki vaults without modification | Vault format fully read; `python-frontmatter` handles it; schema documented below |
| VAULT-02 | Port `layout_io.py` verbatim from lattice-wiki-core | Source read; minimal YAML emitter is stdlib-only, no PyYAML; porting strategy documented |
| VAULT-03 | Use `python-frontmatter` for reads only; writes through ported emitter | `python-frontmatter` read confirmed; write path through hand-rolled emitter documented |
| VAULT-04 | `git diff` empty after round-trip on real vault page (golden test gate) | Real vault confirmed at `/Users/pat/Personal/lattice/lattice/wiki/` (148 pages); fixture copy strategy documented |
| VAULT-05 | Handle truncated frontmatter without crashing; match `ae6872e` behavior | Commit `ae6872e` read; exact guard pattern extracted and documented |
| VAULT-06 | Wikilink placeholder predicate ported from commits `9502c45` + `9388cdd` | Both commits read; `_is_placeholder_target()` logic fully documented |
| VAULT-07 | Port container detection, scan, init, index, log, token counter, graph analyzer | All source files read; tiktoken dependency noted; porting strategy documented |
| MCP-05 | ALL logging routes to stderr; nothing goes to stdout | FastMCP stdio routing verified; logging guard pattern documented |
| MCP-08 | NOT in v1: MCP resources, prompts, sampling, SSE/streamable-HTTP | FastMCP confirms these are opt-in; documented as explicit anti-features |
</phase_requirements>

---

## Summary

Phase 1 is a greenfield monorepo bootstrapping phase. The codebase has exactly one file today (`CLAUDE.md`). Every structural pattern — tier naming, per-package `pyproject.toml` shape, test layout, error-message conventions — is established here and must be followed by all later phases.

The four deliverables are structurally independent and can be developed in parallel after the workspace root is scaffolded: (1) `cores/model-adapter` with Bedrock IAM verification, (2) `cores/vault-io` with vault round-trip gate, (3) the `agents/code-wiki-agent` scaffold with MCP skeleton, (4) CI and open-source hygiene. The round-trip vault test is the single most important deliverable — no vault-write code lands anywhere until it passes.

**Bedrock access is CONFIRMED:** Both `us.anthropic.claude-haiku-4-5-20251001-v1:0` (Haiku 4.5) and `us.anthropic.claude-sonnet-4-6` (Sonnet 4.6) invoke successfully via the Converse API from `us-east-1` using the existing AWS credentials. The real vault is at `/Users/pat/Personal/lattice/lattice/wiki/` (148 pages). The fixture copy requires no sanitization.

**Primary recommendation:** Scaffold the workspace root first (single `pyproject.toml` change), then develop the three members in parallel with the vault round-trip test as the blocking gate for the vault-io member. Everything else can be done concurrently.

---

## Architectural Responsibility Map

| Capability | Primary Tier | Secondary Tier | Rationale |
|------------|-------------|----------------|-----------|
| Bedrock LLM invocation | `cores/model-adapter` | — | Single source of truth for model IDs and ChatBedrockConverse construction; agents import this, never boto3 directly |
| Vault read (frontmatter parse) | `cores/vault-io` | — | `python-frontmatter` read is shared across all agents/commands |
| Vault write (layout block + pages) | `cores/vault-io` | — | Hand-rolled emitter must be the only path that writes vault files |
| Wikilink placeholder predicate | `cores/vault-io` | — | Shared logic used by lint (Phase 5); must be in core, not inline |
| Container detection / monorepo scan | `cores/vault-io` | — | Shared across init, scan, lint commands |
| MCP server entry point | `agents/code-wiki-agent` | — | Only one agent in v1; server registered in this member's `pyproject.toml` |
| Headless CLI entry point | `agents/code-wiki-agent` | — | Both `code-wiki-mcp` and `code-wiki-agent` scripts registered here |
| Test fixtures (vault snapshot) | `agents/code-wiki-agent` | `cores/vault-io` | Round-trip tests live in `cores/vault-io/tests/`; fixture vault path discoverable via env var |
| IAM verification | `cores/model-adapter` | `scripts/` | Integration test in the agent member; standalone script in `scripts/` |

---

## Standard Stack

All versions are locked in CLAUDE.md. Not re-verified here (CLAUDE.md is the canonical source). Reproduced only where this research adds detail CLAUDE.md lacks.

### Core (phase 1 only)

| Library | Version | Purpose | Notes |
|---------|---------|---------|-------|
| `uv` | 0.11.7 installed (0.11.14 pinned in CLAUDE.md) | Workspace manager | `uv_build>=0.11.14,<0.12` as build backend per-member |
| `mcp` | 1.27.1 | MCP server SDK; FastMCP is `mcp.server.fastmcp` | [VERIFIED: PyPI] FastMCP is bundled inside `mcp`, import as `from mcp.server.fastmcp import FastMCP` |
| `langchain-aws` | 1.4.6 | `ChatBedrockConverse` | Used in `cores/model-adapter` |
| `python-frontmatter` | 1.1.0 | Vault frontmatter reads | Read-only per D-03 |
| `tiktoken` | ≥0.7 | Token counter (ported from lattice-wiki-core as-is) | OpenAI tokenizer used for cl100k_base; kept verbatim despite being off-provider |
| `pytest` | ≥8.3 | Test runner | Per-member `testpaths` required |
| `ruff` | 0.15.12 | Linting + formatting | [VERIFIED: PyPI] Latest stable; replaces black + isort |

### Supporting

| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| `botocore` | (boto3 transitive) | `ClientError` exception handling for IAM errors | Only in `cores/model-adapter` error path |
| `toml` or `tomllib` | stdlib (3.11+) | Parse `models.toml` | Python 3.11 ships `tomllib` in stdlib |

### Alternatives Considered

| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| `ruff` alone (format + lint) | `ruff` + `black` | Ruff's formatter is black-compatible; using ruff alone avoids a second tool. Chosen: **ruff only** — `ruff format` + `ruff check`. |
| `fastmcp` (standalone package) | `mcp.server.fastmcp` | `fastmcp` standalone package is a different project (prefecthq/fastmcp). The official Anthropic MCP Python SDK (`mcp` 1.27.1) bundles its own FastMCP at `mcp.server.fastmcp`. Use `mcp.server.fastmcp`, not `pip install fastmcp`. |
| `tomllib` (stdlib) | `tomli` | `tomllib` is in Python 3.11 stdlib; no extra dep needed |

---

## Architecture Patterns

### System Architecture Diagram

```
[uv workspace root pyproject.toml]
  members = ["cores/*", "agents/*"]
  shared uv.lock

cores/vault-io/                    cores/model-adapter/
  src/vault_io/                      src/model_adapter/
    layout_io.py (ported)              models.toml
    _workspace.py (ported)             loader.py → ChatBedrockConverse
    detect_containers.py (ported)      exceptions.py (BedrockAccessDenied)
    lint/common.py (ported)
    update_tokens.py (ported)       agents/code-wiki-agent/
    ... (other ported modules)        src/code_wiki_agent/
                                        cli.py (typer, stub)
                                      src/code_wiki_mcp/
                                        server.py (FastMCP + wiki_ping)
  tests/
    fixtures/round-trip-vault/ ←── copy of ~/Personal/lattice/lattice/wiki/
    test_round_trip.py
    test_truncated_frontmatter.py

       ↓                                    ↓
  [git diff == empty]              [subprocess stdout == JSON-RPC only]
  (round-trip gate)                (MCP stdio gate)
```

Data flow for vault round-trip:
```
real .md file ──→ python-frontmatter.loads() ──→ in-memory Post object
                                                         │
                          ┌──────────────────────────────┘
                          ↓
                layout_io._emit_yaml() / raw string manipulation
                          │
                          ↓
                write to tmp file ──→ git diff ──→ must be empty
```

Data flow for MCP stdio:
```
subprocess stdin ──→ FastMCP JSON-RPC parser ──→ wiki_ping handler ──→ result dict
                                                                              │
                          ┌───────────────────────────────────────────────────┘
                          ↓
subprocess stdout ← FastMCP serializer (JSON-RPC line) ← ONLY valid JSON bytes
```

### Recommended Project Structure

```
deep-agents/
├── pyproject.toml               # workspace root — NO [project] table
├── .python-version              # 3.11
├── uv.lock                      # shared lockfile
├── LICENSE                      # MIT
├── README.md
├── .gitignore
├── .pre-commit-config.yaml      # ruff check + ruff format
├── .github/
│   └── workflows/
│       ├── ci.yml               # lint + unit tests
│       └── eval.yml             # opt-in, non-blocking
├── scripts/
│   └── verify_bedrock_iam.py    # standalone diagnostic
├── cores/
│   ├── vault-io/
│   │   ├── pyproject.toml
│   │   ├── src/vault_io/
│   │   │   ├── __init__.py
│   │   │   ├── layout_io.py      # ported verbatim
│   │   │   ├── _workspace.py     # ported (adapted — no lattice_workspace dep)
│   │   │   ├── detect_containers.py
│   │   │   ├── append_log.py
│   │   │   ├── update_index.py
│   │   │   ├── update_tokens.py
│   │   │   ├── graph_analyzer.py
│   │   │   ├── scan_monorepo.py
│   │   │   ├── init_vault.py
│   │   │   └── lint/
│   │   │       ├── __init__.py
│   │   │       └── common.py     # _is_placeholder_target() lives here
│   │   └── tests/
│   │       ├── fixtures/
│   │       │   └── round-trip-vault/  # committed snapshot from real vault
│   │       ├── conftest.py
│   │       ├── test_round_trip.py
│   │       └── test_truncated_frontmatter.py
│   └── model-adapter/
│       ├── pyproject.toml
│       ├── models.toml
│       └── src/model_adapter/
│           ├── __init__.py
│           ├── loader.py         # make_llm(role) -> ChatBedrockConverse
│           └── exceptions.py     # BedrockAccessDenied
└── agents/
    └── code-wiki-agent/
        ├── pyproject.toml
        └── src/
            ├── code_wiki_agent/
            │   ├── __init__.py
            │   └── cli.py         # typer stub with --help
            └── code_wiki_mcp/
                ├── __init__.py
                └── server.py      # FastMCP + wiki_ping + stdout guard
        └── tests/
            ├── integration/
            │   ├── test_bedrock_iam.py   # @pytest.mark.integration
            │   └── test_mcp_stdio.py     # subprocess stdout capture
            └── unit/
                └── test_cli_help.py
```

### Pattern 1: Workspace Root pyproject.toml (no `[project]` table)

The workspace root is a **virtual project** — it has no `[project]` table and is not itself a distributable package. It only declares workspace membership and shared dev dependencies.

```toml
# pyproject.toml (repo root)
[tool.uv.workspace]
members = ["cores/*", "agents/*"]

[dependency-groups]
dev = [
    "pytest>=8.3",
    "pytest-asyncio==1.3.0",
    "ruff>=0.15",
    "pre-commit",
]

[tool.ruff]
line-length = 120

[tool.ruff.lint]
select = ["E", "F", "I"]

[tool.pytest.ini_options]
# Per-member testpaths are set in each member's pyproject.toml.
# Root-level runs ALL members; per-member runs are scoped.
```
[CITED: docs.astral.sh/uv/concepts/projects/workspaces]

### Pattern 2: Per-Member pyproject.toml (cores/vault-io example)

```toml
# cores/vault-io/pyproject.toml
[project]
name = "vault-io"
version = "0.1.0"
description = "Vault IO for code-wiki-agent"
requires-python = ">=3.11"
dependencies = [
    "python-frontmatter>=1.1",
    "tiktoken>=0.7",
]

[build-system]
requires = ["uv_build>=0.11.14,<0.12"]
build-backend = "uv_build"

[tool.pytest.ini_options]
testpaths = ["tests"]
addopts = "--import-mode=importlib"

[tool.uv.sources]
# (no workspace deps for vault-io — it's a leaf)
```
[CITED: docs.astral.sh/uv/concepts/build-backend]

### Pattern 3: Per-Member pyproject.toml (agents/code-wiki-agent example)

```toml
# agents/code-wiki-agent/pyproject.toml
[project]
name = "code-wiki-agent"
version = "0.1.0"
requires-python = ">=3.11"
dependencies = [
    "vault-io",
    "model-adapter",
    "mcp>=1.27.1",
    "langchain-aws>=1.4.6",
    "typer>=0.25.1",
]

[project.scripts]
code-wiki-agent = "code_wiki_agent.cli:app"
code-wiki-mcp   = "code_wiki_mcp.server:main"

[build-system]
requires = ["uv_build>=0.11.14,<0.12"]
build-backend = "uv_build"

[tool.uv.sources]
vault-io      = { workspace = true }
model-adapter = { workspace = true }

[tool.pytest.ini_options]
testpaths = ["tests"]
addopts = "--import-mode=importlib"
markers = ["integration: requires real Bedrock (skipped in CI by default)"]
```

### Pattern 4: Per-Member pytest Isolation

Running `uv run --package vault-io pytest` scopes pytest to `cores/vault-io/tests/` because that member's `pyproject.toml` sets `testpaths = ["tests"]`. This is the correct isolation mechanism — no `conftest.py` at the workspace root is needed. [CITED: uv workspace docs, testpaths behavior]

Fixture-bleed prevention:
- Each member has its own `tests/conftest.py`
- Workspace-wide fixtures (if needed later) live in the workspace root `conftest.py` with explicit `scope="session"` — not needed in Phase 1
- `--import-mode=importlib` prevents `__init__.py`-based import collisions across members

### Pattern 5: models.toml + make_llm() Loader

```toml
# cores/model-adapter/models.toml
[roles.haiku]
model_id = "us.anthropic.claude-haiku-4-5-20251001-v1:0"
region   = "us-east-1"

[roles.sonnet]
model_id = "us.anthropic.claude-sonnet-4-6"
region   = "us-east-1"
```

```python
# cores/model-adapter/src/model_adapter/loader.py
from __future__ import annotations
import tomllib
from pathlib import Path
import botocore.exceptions
from langchain_aws import ChatBedrockConverse
from model_adapter.exceptions import BedrockAccessDenied

_MODELS_TOML = Path(__file__).parent.parent.parent / "models.toml"

def make_llm(role: str) -> ChatBedrockConverse:
    """Return a ChatBedrockConverse for the given role name.

    Wraps invoke to raise BedrockAccessDenied with the exact ARN
    resource when IAM permissions are missing.
    """
    with open(_MODELS_TOML, "rb") as f:
        config = tomllib.load(f)
    role_cfg = config["roles"][role]
    model_id = role_cfg["model_id"]
    region   = role_cfg.get("region", "us-east-1")
    llm = ChatBedrockConverse(model=model_id, region_name=region)
    return _wrap_access_denied(llm, model_id)

def _wrap_access_denied(llm, model_id: str) -> ChatBedrockConverse:
    original_invoke = llm.invoke
    def invoke_with_error(*args, **kwargs):
        try:
            return original_invoke(*args, **kwargs)
        except botocore.exceptions.ClientError as e:
            if e.response["Error"]["Code"] == "AccessDeniedException":
                raise BedrockAccessDenied(
                    f"Bedrock access denied.\n"
                    f"  Model ARN attempted: {model_id}\n"
                    f"  IAM action required: bedrock:InvokeModel\n"
                    f"  Add an IAM policy with: "
                    f'  {{"Effect":"Allow","Action":"bedrock:InvokeModel",'
                    f'"Resource":"arn:aws:bedrock:*::foundation-model/*"}}\n'
                    f"  Original error: {e}"
                ) from e
            raise
    llm.invoke = invoke_with_error
    return llm
```
[ASSUMED] The exact attribute to patch on `ChatBedrockConverse` may differ from `llm.invoke` — verify against langchain-aws 1.4.6 source during implementation. Alternative: subclass and override `_generate`.

### Pattern 6: MCP Server with Stdout Guard

```python
# agents/code-wiki-agent/src/code_wiki_mcp/server.py
"""code-wiki-mcp MCP server.

IMPORTANT: This module is consumed by stdio-based MCP hosts.
ANY byte written to stdout other than JSON-RPC frames breaks the protocol.
The _StdoutGuard below enforces this at module-init time.
"""
from __future__ import annotations
import logging
import sys
from mcp.server.fastmcp import FastMCP
from pydantic import BaseModel

# --- Stdout guard (must run before any import that might print) ---
class _StdoutGuard:
    """Raise immediately if any non-FastMCP code writes to stdout."""
    def write(self, data: str) -> int:
        if data.strip():
            raise RuntimeError(
                f"Illegal stdout write in MCP server: {data!r}\n"
                "All logging must go to sys.stderr."
            )
        return len(data)
    def flush(self) -> None:
        pass

sys.stdout = _StdoutGuard()  # type: ignore[assignment]

# --- Redirect all logging to stderr ---
logging.basicConfig(
    stream=sys.stderr,
    level=logging.WARNING,
    format="%(levelname)s %(name)s: %(message)s",
)

# --- FastMCP server ---
mcp = FastMCP(
    name="code-wiki-mcp",
    version="0.1.0",
)

class PingInput(BaseModel):
    message: str = "ping"

class PingOutput(BaseModel):
    status: str
    echo: str

@mcp.tool(
    name="wiki_ping",
    description="Returns pong; used to verify MCP wiring is intact.",
)
def wiki_ping(input: PingInput) -> PingOutput:
    return PingOutput(status="pong", echo=input.message)

def main() -> None:
    mcp.run()  # FastMCP handles stdio transport by default

if __name__ == "__main__":
    main()
```
[CITED: mcp.server.fastmcp quickstart; FastMCP uses `mcp.run()` with transport="stdio" by default]

**Critical note on FastMCP import path:** The official Anthropic MCP Python SDK (`mcp` 1.27.1) exposes FastMCP at `mcp.server.fastmcp.FastMCP`. Do NOT install the separate `fastmcp` PyPI package (prefecthq/fastmcp) — it is a different project. [VERIFIED: PyPI mcp 1.27.1 info]

**FastMCP stdout behavior:** When launched with `mcp.run()` (stdio transport), FastMCP writes all JSON-RPC frames to stdout and all diagnostic output to stderr by default. The `_StdoutGuard` provides belt-and-suspenders enforcement: if any third-party library initialization (boto3, anyio, langchain startup logs) accidentally writes to stdout, it fails the test loudly rather than silently corrupting the protocol stream. [CITED: FastMCP docs — "reading messages from stdin and writing responses to stdout"]

### Pattern 7: MCP Stdio Integration Test

```python
# agents/code-wiki-agent/tests/integration/test_mcp_stdio.py
"""Verify MCP server stdout contains only valid JSON-RPC lines."""
import json
import subprocess
import sys
import textwrap
import pytest

def _send_initialize() -> dict:
    return {
        "jsonrpc": "2.0",
        "id": 1,
        "method": "initialize",
        "params": {
            "protocolVersion": "2024-11-05",
            "capabilities": {},
            "clientInfo": {"name": "test", "version": "0.0.1"},
        },
    }

def _send_tools_call() -> dict:
    return {
        "jsonrpc": "2.0",
        "id": 2,
        "method": "tools/call",
        "params": {"name": "wiki_ping", "arguments": {"message": "hello"}},
    }

def test_mcp_stdout_is_valid_jsonrpc():
    """Every byte on stdout must be valid JSON-RPC (newline-delimited)."""
    proc = subprocess.Popen(
        ["uv", "run", "--package", "code-wiki-agent", "code-wiki-mcp"],
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    try:
        # Send initialize then a tool call, then close stdin
        payload = (
            json.dumps(_send_initialize()) + "\n" +
            json.dumps(_send_tools_call()) + "\n"
        )
        stdout_bytes, stderr_bytes = proc.communicate(
            input=payload.encode(), timeout=15
        )
    finally:
        proc.kill()

    lines = [l for l in stdout_bytes.decode().splitlines() if l.strip()]
    assert lines, "MCP server produced no stdout output"
    for line in lines:
        try:
            obj = json.loads(line)
        except json.JSONDecodeError as e:
            pytest.fail(
                f"Non-JSON stdout line from MCP server: {line!r}\n"
                f"JSON error: {e}\n"
                f"Full stderr: {stderr_bytes.decode()[:500]}"
            )
        assert "jsonrpc" in obj or "id" in obj, (
            f"Line is JSON but not JSON-RPC: {line!r}"
        )
```

### Pattern 8: Truncated Frontmatter Guard

Exact behavior from commit `ae6872e` in `update_tokens.py`:

```python
# The guard: split on "---" expecting at least 3 parts
# (before-open, frontmatter-content, after-close)
parts = raw.split("---", 2)
if len(parts) < 3:
    print(f"[warn] skipping {path}: no closing frontmatter fence", file=sys.stderr)
    return ("skipped", 0)
```

This pattern must be replicated in any vault-io function that reads frontmatter for writing. The test fixture is a file containing:
```
---
title: No closing fence
category: concept
```
(no `---` closer). The test asserts: `status == "skipped"`, file unchanged on disk, warning on stderr. [VERIFIED: read from commit ae6872e source]

### Pattern 9: Wikilink Placeholder Predicate

From `lint_wiki.py` after commits `9502c45` + `9388cdd`:

```python
def _is_placeholder_target(target: str) -> bool:
    """Returns True for template tokens like [[wiki/...]], [[work/<slug>]].

    Placeholder targets contain template markers (..., <, or >)
    and should not be treated as broken links.
    """
    return "..." in target or "<" in target or ">" in target
```

This function belongs in `cores/vault-io/src/vault_io/lint/common.py` so Phase 5 lint can import it. [VERIFIED: read from lattice-wiki-core source]

### Anti-Patterns to Avoid

- **PyYAML round-trip on vault pages:** `yaml.dump(yaml.safe_load(frontmatter))` silently reorders keys, normalizes quoting, and adds or removes trailing newlines. The existing `python-frontmatter` + hand-rolled emitter combination is non-negotiable.
- **`from fastmcp import FastMCP`:** This imports the wrong package (prefecthq/fastmcp). Use `from mcp.server.fastmcp import FastMCP`.
- **`ChatBedrock` (legacy class):** Use `ChatBedrockConverse` only.
- **Hardcoded model IDs in Python code:** Any `"us.anthropic.claude-haiku-*"` string in `.py` files violates D-11. Route through `models.toml`.
- **`print()` calls at module import time in the MCP server:** These fire before `_StdoutGuard` is installed if the import happens in a transitive dep. The guard is set at the top of `server.py` before any other import.
- **pytest `testpaths` collision:** Without per-member `testpaths`, `uv run pytest` at the workspace root collects all members' tests. This is intentional for the full suite, but `uv run --package vault-io pytest` must only run vault-io tests. Confirmed: uv scopes `--package` to that member's directory, which respects its `testpaths`.

---

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| YAML serialization for vault pages | Custom YAML writer | `layout_io.py` (ported verbatim) | 148+ real pages have been byte-tested against this emitter; any rewrite risks subtle drift |
| TOML parsing for models.toml | `re`-based parser | `tomllib` (Python 3.11 stdlib) | Handles multi-line strings, escaping, comments correctly |
| MCP JSON-RPC framing | Custom stdin/stdout loop | `mcp.server.fastmcp.FastMCP.run()` | Protocol framing, error responses, initialize handshake, capability negotiation — all handled |
| IAM error classification | `e.response['Error']['Code'] == ...` in every call site | Single `BedrockAccessDenied` exception in `model_adapter` | Centralizes IAM diagnostic message with ARN; consumers get structured error |
| Subprocess-scoped Python path manipulation | `sys.path.insert(0, ...)` | `uv_build` editable installs via workspace | `uv sync` installs all members as editable; `import vault_io` works everywhere |

---

## Common Pitfalls

### Pitfall 1: PyYAML Normalization Breaks Round-Trip

**What goes wrong:** Any code path that reads frontmatter with `python-frontmatter` and writes it back with `frontmatter.dumps()` will silently reorder keys, add or remove quotes, and potentially change list serialization format.

**Why it happens:** `python-frontmatter.dumps()` uses PyYAML's `yaml.dump()` under the hood, which applies its own formatting rules regardless of what the original file contained.

**How to avoid:** For the token counter port (`update_tokens.py`), use the exact strategy from the source: read raw string, `raw.split("---", 2)`, manipulate frontmatter as lines, reconstruct with string concatenation. Never call `frontmatter.dumps()` in write paths.

**Warning signs:** `git diff` shows cosmetic-only changes (quotes added/removed, key order changed, `null` changed to `~`).

### Pitfall 2: FastMCP Import from Wrong Package

**What goes wrong:** `pip install fastmcp` installs `prefecthq/fastmcp`, a different framework. Code using `from fastmcp import FastMCP` will work locally but uses a different API than `mcp.server.fastmcp.FastMCP`.

**Why it happens:** The PyPI name collision between the official MCP SDK's bundled FastMCP and the standalone `fastmcp` package by Prefect.

**How to avoid:** The only dependency in `pyproject.toml` is `mcp>=1.27.1`. Import path is `from mcp.server.fastmcp import FastMCP`. Never add `fastmcp` as a separate dependency.

### Pitfall 3: Stdout Pollution from boto3/botocore Startup

**What goes wrong:** Some botocore/boto3 versions emit debug output to stdout during the first `client()` call if `AWS_DEBUG` or similar env vars are set, or if a custom event handler prints.

**Why it happens:** Library-level logging defaults, especially in development environments.

**How to avoid:** The `_StdoutGuard` in `server.py` catches this immediately. Additionally, set `logging.getLogger("boto3").setLevel(logging.WARNING)` and `logging.getLogger("botocore").setLevel(logging.WARNING)` in server startup before importing AWS libs.

**Warning signs:** The integration test `test_mcp_stdio.py` fails with a `JSONDecodeError` on a line containing "DEBUG" or "boto".

### Pitfall 4: Workspace Root testpaths Causes Test Bleed

**What goes wrong:** Running `uv run pytest` from workspace root with no `testpaths` in the root `pyproject.toml` causes pytest to discover all tests in all members. A fixture defined in `cores/vault-io/tests/conftest.py` with the same name as one in `agents/code-wiki-agent/tests/conftest.py` can shadow unexpectedly.

**Why it happens:** pytest fixture lookup is hierarchical; duplicate names at the same scope level cause the last-registered one to win, non-deterministically.

**How to avoid:** Each member defines its own `testpaths = ["tests"]`. Root `pyproject.toml` has no `testpaths` (default: collect from root). `--import-mode=importlib` prevents `__init__.py` import aliasing. Workspace-wide fixtures do not exist in Phase 1.

### Pitfall 5: `_workspace.py` Import Chain

**What goes wrong:** The ported `_workspace.py` imports `lattice_workspace.config` and `lattice_workspace.paths` (a separate lattice-internal package not in deep-agents). The fallback path (`except ImportError`) returns `Path("lattice").resolve()` — wrong for the new context.

**Why it happens:** The original module was written for the lattice monorepo where `lattice-workspace` is always available.

**How to avoid:** The ported `_workspace.py` should be adapted (not verbatim-copied) to accept the vault path as an explicit argument or read from `CODE_WIKI_REAL_VAULT_PATH` env var, removing the `lattice_workspace` import entirely. The only lattice-workspace functionality needed in Phase 1 is "resolve vault path" — a single `Path` constructor.

### Pitfall 6: Cross-Region Inference Profile ARN Format Varies by Model

**What goes wrong:** Older Claude models use versioned IDs like `us.anthropic.claude-3-5-haiku-20241022-v1:0`; Haiku 4.5 uses `us.anthropic.claude-haiku-4-5-20251001-v1:0`; Sonnet 4.6 uses `us.anthropic.claude-sonnet-4-6` (no version suffix at the end). Mixing the formats causes `ValidationException`.

**How to avoid:** Use the exact IDs from the AWS model card pages (verified in this research and documented in the Bedrock ARNs section below).

---

## Bedrock Cross-Region Inference Profile ARNs

**VERIFIED against AWS official documentation on 2026-05-13 and confirmed via live Bedrock invocations.**

### Claude Haiku 4.5

| Profile Type | Model ID |
|--------------|----------|
| In-Region | `anthropic.claude-haiku-4-5-20251001-v1:0` |
| Geo (US) | `us.anthropic.claude-haiku-4-5-20251001-v1:0` |
| Geo (EU) | `eu.anthropic.claude-haiku-4-5-20251001-v1:0` |
| Global | `global.anthropic.claude-haiku-4-5-20251001-v1:0` |

**Recommended for `models.toml` `haiku` role:** `us.anthropic.claude-haiku-4-5-20251001-v1:0` (US Geo profile; routes across us-east-1, us-east-2, us-west-2 for burst tolerance). [VERIFIED: AWS model card; live Bedrock invoke confirmed in us-east-1]

### Claude Sonnet 4.6

| Profile Type | Model ID |
|--------------|----------|
| In-Region | `anthropic.claude-sonnet-4-6` (in eu-west-2 only) |
| Geo (US) | `us.anthropic.claude-sonnet-4-6` |
| Geo (EU) | `eu.anthropic.claude-sonnet-4-6` |
| Global | `global.anthropic.claude-sonnet-4-6` |

**Recommended for `models.toml` `sonnet` role:** `us.anthropic.claude-sonnet-4-6` (US Geo profile). [VERIFIED: AWS model card; live Bedrock invoke confirmed in us-east-1]

### IAM Permissions Required

Minimum IAM policy for invoking cross-region inference profiles:

```json
{
  "Effect": "Allow",
  "Action": [
    "bedrock:InvokeModel",
    "bedrock:InvokeModelWithResponseStream"
  ],
  "Resource": [
    "arn:aws:bedrock:*::foundation-model/*",
    "arn:aws:bedrock:*:*:inference-profile/*"
  ]
}
```

**Note:** `bedrock:InvokeModelWithResponseStream` is needed for streaming calls (`astream()`). Phase 1 tests use non-streaming `invoke()`, but including it now prevents a Phase 2 IAM surprise. [CITED: AWS Bedrock IAM docs]

**Pat's current account status:** AWS credentials confirmed active (`PSprowls` user, account 210412004691, us-east-1 region). Both Haiku 4.5 and Sonnet 4.6 invoke successfully via Converse API. No IAM changes needed for Pat's current account. [VERIFIED: live Bedrock invocations executed during this research session]

---

## Vault Format — Complete Specification

**VERIFIED by reading real vault at `/Users/pat/Personal/lattice/lattice/wiki/` (148 pages) and lattice-wiki-core source.**

### Frontmatter Schema

Frontmatter is standard YAML between `---` delimiters. Key ordering is not mandated by the format, but `python-frontmatter` preserves key insertion order on read, and the hand-rolled emitter writes keys in a fixed order. Round-trip safety requires not re-sorting keys.

**Package page frontmatter (from real vault):**
```yaml
---
title: lattice-wiki-core
category: package
summary: <one-line summary>
status: active
package_path: packages/lattice-wiki-core
package_type: library
domain:
language: Python
depends_on: []
tags: [python, wiki, core, stdlib]
sources: 3
updated: 2026-05-11
last_sync_commit: c2a5068
last_sync_at: 2026-05-10
workflow_hints:
  brainstorming: [context.md]
  planning:      [api.md, patterns.md]
  debugging:     [api.md, work.md]
tokens: 3778
---
```

**Index/auto-generated page frontmatter (from real vault):**
```yaml
---
title: Concept Index
category: index
summary: Auto-generated sub-index of all concept pages in wiki/.
updated: 2026-05-11
---
```

**Known frontmatter keys by category:**

| Key | Categories | Type | Notes |
|-----|-----------|------|-------|
| `title` | all | string | Always present |
| `category` | all | string | `package`, `plugin`, `concept`, `source`, `adr`, `architecture`, `index`, `dependency`, `app` |
| `summary` | most | string | One-line description |
| `status` | package/plugin | string | `active`, `planned`, `deprecated` |
| `package_path` | package | string | Relative path from repo root |
| `package_type` | package | string | `library`, `plugin`, `app`, `cli` |
| `domain` | package | string or null | Domain grouping |
| `language` | package | string | `Python`, `TypeScript`, etc. |
| `depends_on` | package | YAML list `[]` | Inline list |
| `tags` | most | YAML inline list | `[tag1, tag2]` format |
| `sources` | package | integer | Source count |
| `updated` | all | date string `YYYY-MM-DD` | Last update date |
| `last_sync_commit` | package | string | Short commit hash |
| `last_sync_at` | package | date string | Last sync date |
| `workflow_hints` | package | nested mapping | Keys: brainstorming, planning, debugging; values: inline lists |
| `tokens` | most (not index/log) | integer | Stamped by `update_tokens.py` |
| `references` | source/adr | varies | Optional |

### Critical YAML Serialization Rules (for round-trip)

1. **Inline lists:** `tags: [python, wiki]` — NOT block-style (no leading `-` per item). `python-frontmatter` reads this correctly. The write path must reconstruct inline lists identically.
2. **Null values:** `domain:` (bare key with nothing after colon) — PyYAML writes this as `domain: null`. The round-trip test will catch if `python-frontmatter` normalizes it.
3. **Multi-line values (workflow_hints):** The `workflow_hints` block uses indented YAML mappings with inline lists. This is one of the more complex structures; the round-trip test against real pages covers this.
4. **Trailing newlines:** All vault pages end with exactly one trailing newline. Any emitter that adds or removes one will fail the `git diff` gate.
5. **Key ordering:** Real vault pages have inconsistent ordering between pages (they were written at different times). Round-trip fidelity means writing back in the SAME order the file had, not a canonical order.

**The safest write strategy for the token counter (the only write-path component in Phase 1):** As implemented in the ported `update_tokens.py` — manipulate frontmatter lines as strings, not as a YAML round-trip. `raw.split("---", 2)`, filter/update the `tokens:` line, reconstruct with string concatenation. Never call `frontmatter.dumps()`.

### Layout Block (CLAUDE.md / AGENTS.md)

The layout block is the only structured write target in Phase 1 (via `layout_io.py`). Its format:

```
<!-- lattice-wiki:layout:start -->
```yaml
version: 1
detected_at: 2026-04-29
repo_root: ..
containers:
  - source: apps
    vault_dir: apps
    classification: app
    children_count: 3
```
<!-- lattice-wiki:layout:end -->
```

The hand-rolled emitter in `layout_io.py` handles this structure. It is stdlib-only (no PyYAML dependency). It produces deterministic output — given the same input dict, the same bytes are emitted — making round-trip testing trivial for this case.

### Wikilink Format

- Standard: `[[wiki/packages/lattice-wiki-core/lattice-wiki-core]]`
- With alias: `[[wiki/packages/lattice-wiki-core/lattice-wiki-core|lattice-wiki-core]]`
- With section: `[[wiki/concepts/foo#section]]`
- Template token (placeholder — NOT a broken link): `[[wiki/...]]`, `[[work/<slug>]]`, `[[wiki/<container>/<name>]]`

Regex from `lint/common.py`:
```python
WIKILINK_RE = re.compile(r"\[\[([^\]|#]+)(?:#[^\]|]*)?(?:\|[^\]]*)?\]\]")
```

The placeholder predicate (`_is_placeholder_target`) must be applied before classifying a wikilink as broken.

### Edge Cases Confirmed in Source

| Edge Case | Behavior | Source |
|-----------|----------|--------|
| Missing closing `---` | Skip with stderr warning; return `("skipped", 0)` | commit `ae6872e` |
| File without frontmatter (e.g., `index.md`, `log.md`) | Skip (`not raw.startswith("---")`) | `update_tokens.py` |
| BOM marker at file start | Not handled specially; `encoding="utf-8"` (not `utf-8-sig`) | `update_tokens.py`, `layout_io.py` |
| CRLF line endings | Not specially handled; round-trip test on real vault will catch | confirmed by absence of CRLF handling in source |
| Null vault_dir in layout block | Serialized as `vault_dir: null` | `layout_io._emit_scalar(None)` |
| `note` field with spaces | Double-quoted: `note: "user opted to skip"` | `layout_io._emit_yaml()` |

### Real Vault for Round-Trip Fixture

**VERIFIED: `/Users/pat/Personal/lattice/lattice/wiki/` — 148 pages.**

Structure:
```
wiki/
├── CLAUDE.md         (has layout block)
├── index.md          (no frontmatter — auto-generated)
├── log.md            (no frontmatter — append-only log)
├── adrs/             (16 pages)
├── architecture/     (0 pages)
├── concepts/         (34 pages — varied frontmatter)
├── dependencies/     (0 pages)
├── packages/         (12 packages × ~5 sub-pages each)
│   └── lattice-wiki-core/
│       ├── lattice-wiki-core.md (package page with workflow_hints)
│       ├── api.md
│       ├── context.md
│       ├── patterns.md
│       └── work.md
├── plugins/          (7 plugins)
└── sources/          (12 pages)
```

**Fixture copy strategy:** `cp -r /Users/pat/Personal/lattice/lattice/wiki/ cores/vault-io/tests/fixtures/round-trip-vault/`. Commit as-is. The fixture is ~148 `.md` files; no binary content; acceptable repo size impact (~500KB estimated).

---

## CI and Pre-Commit Configuration

### Pre-Commit (Recommended: ruff only)

```yaml
# .pre-commit-config.yaml
repos:
  - repo: https://github.com/astral-sh/ruff-pre-commit
    rev: v0.15.12
    hooks:
      - id: ruff
        args: [--fix]
      - id: ruff-format
```
[VERIFIED: ruff 0.15.12 is current stable as of 2026-05-13]

**Rationale for ruff-only (not ruff + black):** ruff's formatter is black-compatible in output. A single tool (two hooks: lint + format) is simpler than two tools. ruff's formatter is faster and avoids version-sync issues between ruff and black.

### GitHub Actions CI

```yaml
# .github/workflows/ci.yml
name: CI
on: [push, pull_request]
jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: astral-sh/setup-uv@v5
        with:
          version: "0.11.14"
      - run: uv sync
      - run: uv run ruff check .
      - run: uv run ruff format --check .
      - run: uv run --package vault-io pytest
      - run: uv run --package model-adapter pytest
      - run: uv run --package code-wiki-agent pytest -m "not integration"
```

**CI matrix decision (researcher's recommendation):** Python 3.11 only for Phase 1 (matching the `requires-python = ">=3.11"` floor). Adding 3.12 is low-friction to add in a later phase; the cost vs benefit ratio doesn't favor it in a Phase 1 walking skeleton. Linux only; mac is optional and can be added if CI shows platform-specific issues.

---

## Environment Availability

| Dependency | Required By | Available | Version | Fallback |
|------------|------------|-----------|---------|----------|
| `uv` | Workspace management, all `uv run` commands | ✓ | 0.11.7 (0.11.14 pinned in CLAUDE.md — needs upgrade via `brew upgrade uv`) | — |
| Python 3.11+ | Runtime floor | ✓ | 3.14.4 (exceeds floor) | — |
| AWS CLI | IAM verification script | ✓ | 2.34.32 | — |
| AWS credentials | Bedrock invocations | ✓ | us-east-1, account 210412004691, PSprowls | — |
| Bedrock Haiku 4.5 | BED-01 integration test | ✓ | `us.anthropic.claude-haiku-4-5-20251001-v1:0` confirmed | — |
| Bedrock Sonnet 4.6 | BED-01 integration test | ✓ | `us.anthropic.claude-sonnet-4-6` confirmed | — |
| `ruff` | Linting + formatting | ✗ (not globally installed) | — | Installed via `uv sync` (dev dep) |
| `pre-commit` | Git hooks | ✗ (not globally installed) | — | `uv run pre-commit install` after `uv sync` |
| `pytest` | Tests | ✗ (not globally installed) | — | `uv run pytest` via workspace |
| git | Version control | ✓ | 2.53.0 | — |

**uv version note:** Host has `uv 0.11.7`; CLAUDE.md specifies `uv_build>=0.11.14`. The build backend version pinned in `pyproject.toml` (`requires = ["uv_build>=0.11.14,<0.12"]`) is the package version that uv downloads during build — it does not require the local uv CLI to be exactly 0.11.14. However, upgrading the local uv CLI to 0.11.14+ is good hygiene: `brew upgrade uv`.

**Missing dependencies with no fallback:** None.

**Missing dependencies with fallback (via `uv sync`):** ruff, pre-commit, pytest — all installed into the workspace virtual environment by `uv sync`. No global installation needed.

---

## Validation Architecture

### Test Framework

| Property | Value |
|----------|-------|
| Framework | pytest ≥ 8.3 |
| Config location | Per-member `pyproject.toml` `[tool.pytest.ini_options]` |
| Quick run (vault-io) | `uv run --package vault-io pytest` |
| Quick run (model-adapter) | `uv run --package model-adapter pytest` |
| Quick run (agent unit) | `uv run --package code-wiki-agent pytest -m "not integration"` |
| Integration tests | `CODE_WIKI_RUN_INTEGRATION=1 uv run --package code-wiki-agent pytest -m integration` |
| Full suite | `uv run pytest` (all members) |

### Phase Requirements → Test Map

| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| INFRA-01 | Workspace root has `[tool.uv.workspace]` with `cores/*` + `agents/*` | smoke | `uv sync && uv run --package vault-io pytest --collect-only` | ❌ Wave 0 |
| INFRA-02 | `uv sync` produces single `uv.lock` | smoke | `uv sync && ls uv.lock` | ❌ Wave 0 |
| INFRA-03 | `uv run --package vault-io pytest` runs only vault-io tests (no agent tests) | smoke | `uv run --package vault-io pytest --collect-only 2>&1 \| grep -v code_wiki` | ❌ Wave 0 |
| INFRA-06 | `uv run code-wiki-agent --help` exits 0 | unit | `uv run --package code-wiki-agent pytest tests/unit/test_cli_help.py` | ❌ Wave 0 |
| BED-01 | `make_llm("haiku").invoke("ping")` succeeds; AccessDeniedException raises `BedrockAccessDenied` with ARN | integration | `CODE_WIKI_RUN_INTEGRATION=1 uv run --package code-wiki-agent pytest tests/integration/test_bedrock_iam.py` | ❌ Wave 0 |
| VAULT-04 | `git diff` empty after round-trip on all fixture pages | unit | `uv run --package vault-io pytest tests/test_round_trip.py` | ❌ Wave 0 |
| VAULT-05 | Truncated frontmatter skipped with stderr warning, file unchanged | unit | `uv run --package vault-io pytest tests/test_truncated_frontmatter.py` | ❌ Wave 0 |
| VAULT-06 | `_is_placeholder_target("wiki/...")` returns True; real link returns False | unit | `uv run --package vault-io pytest tests/test_wikilink_predicate.py` | ❌ Wave 0 |
| MCP-05/D-16 | All stdout lines from `uv run code-wiki-mcp` are valid JSON-RPC | integration | `uv run --package code-wiki-agent pytest tests/integration/test_mcp_stdio.py` | ❌ Wave 0 |

### Evidence Map (Success Criterion → Test)

| Success Criterion | Evidence | Test |
|-------------------|----------|------|
| SC-1: `uv run code-wiki-agent --help` works from fresh clone; single `uv.lock`; per-member isolation | `uv sync` exits 0; `--help` exits 0; `pytest --collect-only` scoped correctly | `test_cli_help.py` + smoke scripts |
| SC-2: `make_llm("haiku").invoke("ping")` succeeds; IAM error includes exact ARN | Integration test passes; `BedrockAccessDenied` message contains `us.anthropic.claude-haiku-4-5-20251001-v1:0` | `test_bedrock_iam.py` |
| SC-3: `git diff` empty after round-trip; truncated frontmatter skipped not crashed | `test_round_trip.py` passes on all 148 fixture pages; `test_truncated_frontmatter.py` asserts `status == "skipped"` and stderr has warning | both files |
| SC-4: MCP stdout contains only valid JSON-RPC | `test_mcp_stdio.py` subprocess test: every stdout line parses as JSON with `jsonrpc` key | `test_mcp_stdio.py` |

### Sampling Rate

- **Per task commit:** `uv run --package <member> pytest -x -q` (fail-fast, quiet)
- **Per wave merge:** Full suite: `uv run pytest`
- **Phase gate before `/gsd-verify-work`:** Full suite green AND integration tests green (`CODE_WIKI_RUN_INTEGRATION=1`)

### Wave 0 Gaps (test infrastructure to create before implementation)

- [ ] `cores/vault-io/tests/conftest.py` — shared `tmp_path`-based fixtures
- [ ] `cores/vault-io/tests/fixtures/round-trip-vault/` — copy from real vault
- [ ] `cores/vault-io/tests/test_round_trip.py` — VAULT-04 gate
- [ ] `cores/vault-io/tests/test_truncated_frontmatter.py` — VAULT-05
- [ ] `cores/vault-io/tests/test_wikilink_predicate.py` — VAULT-06
- [ ] `cores/model-adapter/tests/test_loader.py` — unit tests with mocked Bedrock
- [ ] `agents/code-wiki-agent/tests/unit/test_cli_help.py` — INFRA-06
- [ ] `agents/code-wiki-agent/tests/integration/test_bedrock_iam.py` — BED-01
- [ ] `agents/code-wiki-agent/tests/integration/test_mcp_stdio.py` — MCP-05

---

## Security Domain

Phase 1 has a narrow security surface: no user-facing inputs, no web endpoints, no authentication beyond AWS IAM. ASVS categories that apply are minimal.

### Applicable ASVS Categories

| ASVS Category | Applies | Standard Control |
|---------------|---------|-----------------|
| V2 Authentication | No | AWS IAM handles auth; no app-level auth in Phase 1 |
| V3 Session Management | No | No sessions in Phase 1 |
| V4 Access Control | Partial | IAM policy scope — use least-privilege; no `bedrock:*` wildcard |
| V5 Input Validation | Partial | `wiki_ping` input: Pydantic model validates `message: str` |
| V6 Cryptography | No | AWS SDK handles TLS; no custom crypto |

### Known Threat Patterns

| Pattern | STRIDE | Standard Mitigation |
|---------|--------|---------------------|
| Credentials in `models.toml` | Information Disclosure | Never commit AWS keys; `models.toml` contains only model IDs and region, no credentials — credentials from env/`~/.aws/credentials` via boto3 default chain |
| MCP stdout injection via stray `print()` | Tampering | `_StdoutGuard` sentinel + subprocess stdout-only assertion test |
| Vault fixture with sensitive content | Information Disclosure | D-05 accepted this risk; 148 lattice wiki pages are technical content about Pat's own tools — no PII, no secrets |

---

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| `ChatBedrock` | `ChatBedrockConverse` | langchain-aws ~1.3 | Converse API supports all current Bedrock models uniformly; `ChatBedrock` deprecated |
| `from mcp import Server` (low-level) | `from mcp.server.fastmcp import FastMCP` | mcp ~1.0 | FastMCP handles protocol boilerplate, tool schema generation, type coercion |
| Versioned cross-region ARNs for Sonnet 4.x | Versionless IDs (`us.anthropic.claude-sonnet-4-6`) | 2026 | Newer Claude 4.x models use versionless Geo IDs; don't append `-v1:0` suffix |
| SSE transport for MCP | stdio (local) / Streamable HTTP (remote) | MCP spec 2025-03-26 | SSE deprecated; stdio is default for local CLI hosting |

**Deprecated/outdated:**
- `mcp.server.Server` (low-level): Use `FastMCP` instead.
- `ChatBedrock`: Use `ChatBedrockConverse`.
- SSE MCP transport: Explicitly excluded by MCP-08.
- `rank-bm25`: Use `bm25s` (not in Phase 1 but noted).

---

## Assumptions Log

| # | Claim | Section | Risk if Wrong |
|---|-------|---------|---------------|
| A1 | `ChatBedrockConverse.invoke` can be monkey-patched by replacing the attribute on the instance | Pattern 5 (make_llm) | If langchain-aws uses slots or `__slots__`, patching will fail; subclass override is safer — verify during implementation |
| A2 | `mcp.run()` with no arguments defaults to stdio transport | Pattern 6 (MCP server) | If the default changed in 1.27.1, specify `transport="stdio"` explicitly: `mcp.run(transport="stdio")` |
| A3 | The fixture vault (~148 pages, ~500KB) is safe to commit to git without size concerns | Vault fixture section | If the wiki has grown to MB-scale or contains binary files, the committed fixture approach needs revisiting |

---

## Open Questions (RESOLVED)

1. **RESOLVED — `_workspace.py` adaptation scope**
   - What we know: The ported `_workspace.py` imports `lattice_workspace` (unavailable in deep-agents). The fallback is wrong for the new context.
   - What's unclear (was): Which ported modules actually call `resolve_wiki_and_repo()` vs accept a `wiki: Path` argument directly?
   - **Resolution (locked in Plan 01-03 Task 2):** Drop `lattice_workspace` import entirely. Rewrite `_workspace.py` as a two-path resolver: explicit `vault_path: Path` argument when supplied, else read `CODE_WIKI_REAL_VAULT_PATH` env var, else raise `RuntimeError` with a remediation message. Every ported module that previously called `resolve_wiki_and_repo()` is updated during import surgery (Task 2) to accept and forward `vault_path: Path` instead. No silent fallback.

2. **RESOLVED — CI integration test gating for BED-01**
   - What we know: `@pytest.mark.integration` tests are skipped unless `CODE_WIKI_RUN_INTEGRATION=1`. CI workflow does not set this.
   - What's unclear (was): Should CI run the IAM verification on any branch? On main only?
   - **Resolution (per D-08 / D-16 + Plan 01-02):** Phase 1 CI does NOT run integration tests on any branch. Pat runs them locally via `CODE_WIKI_RUN_INTEGRATION=1 uv run --package code-wiki-agent pytest -m integration` or the standalone `scripts/verify_bedrock_iam.py` diagnostic. A separate `eval.yml` workflow (Phase 2 or later) can run integration tests with AWS secrets if needed — not in scope for Phase 1.

---

## Sources

### Primary (HIGH confidence)
- AWS Bedrock model card — Claude Haiku 4.5: https://docs.aws.amazon.com/bedrock/latest/userguide/model-card-anthropic-claude-haiku-4-5.md — exact Geo inference IDs confirmed
- AWS Bedrock model card — Claude Sonnet 4.6: https://docs.aws.amazon.com/bedrock/latest/userguide/model-card-anthropic-claude-sonnet-4-6.md — exact Geo inference IDs confirmed
- Live Bedrock invocations: `us.anthropic.claude-haiku-4-5-20251001-v1:0` and `us.anthropic.claude-sonnet-4-6` both respond to `ping` in us-east-1, 2026-05-13
- Context7 `/astral-sh/uv` — workspace `pyproject.toml` patterns, `uv_build` backend, `dependency-groups`
- Context7 `/prefecthq/fastmcp` — stdio transport routing, `mcp.run()` behavior, `_StdoutGuard` motivation
- lattice-wiki-core source (commit `ae6872e`): `/Users/pat/Personal/lattice/packages/lattice-wiki-core/src/lattice_wiki_core/update_tokens.py` — truncated frontmatter guard
- lattice-wiki-core source (commits `9502c45`, `9388cdd`): `lint_wiki.py` — `_is_placeholder_target()` function
- Real vault: `/Users/pat/Personal/lattice/lattice/wiki/` — 148 pages, frontmatter schema confirmed
- PyPI: `mcp` 1.27.1 — https://pypi.org/project/mcp/ — FastMCP bundled; `mcp.server.fastmcp` import path

### Secondary (MEDIUM confidence)
- CLAUDE.md (this project) — full stack rationale and version pins
- lattice root `pyproject.toml` — workspace root pattern reference (no `[project]` table confirmed)

### Tertiary (LOW confidence)
- None

---

## Metadata

**Confidence breakdown:**
- Bedrock ARNs and connectivity: HIGH — live invocations confirmed
- Workspace structure: HIGH — verified against uv docs and lattice reference repo
- Vault format: HIGH — read from 148 real pages and source commits
- MCP stdio guard: HIGH — FastMCP docs confirm stdout routing; pattern is standard
- IAM permissions: MEDIUM — verified that `bedrock:InvokeModel` on `*` works; exact minimum ARN scope for inference-profile ARN resource not separately verified

**Research date:** 2026-05-13
**Valid until:** 2026-06-13 (stable stack; Bedrock ARNs may change if AWS releases new model versions)

---

## RESEARCH COMPLETE

**Phase:** 1 — Infrastructure, Vault IO, and MCP Skeleton
**Confidence:** HIGH

### Key Findings

- **Bedrock access confirmed:** Both `us.anthropic.claude-haiku-4-5-20251001-v1:0` and `us.anthropic.claude-sonnet-4-6` invoke successfully. No IAM changes needed on Pat's account. Exact model IDs for `models.toml` are now locked.
- **Real vault identified:** `/Users/pat/Personal/lattice/lattice/wiki/` — 148 pages. Commits directly as fixture with no sanitization needed.
- **Vault round-trip strategy clarified:** The ONLY write-path in Phase 1 is `update_tokens.py` (stamps `tokens:` field). The strategy is raw string manipulation via `split("---", 2)`, NOT `frontmatter.dumps()`. The `layout_io.py` hand-rolled emitter handles layout blocks and is stdlib-only.
- **MCP import path is `mcp.server.fastmcp.FastMCP`:** The `fastmcp` standalone PyPI package (prefecthq) is a different project. Do not install it.
- **`_workspace.py` must be adapted, not verbatim-copied:** The `lattice_workspace` import dependency must be removed; vault paths come from explicit `Path` arguments or `CODE_WIKI_REAL_VAULT_PATH`.
- **`_StdoutGuard` + `logging.basicConfig(stream=sys.stderr)` is the complete stderr-only enforcement pattern.** Belt: FastMCP routes frames to stdout only. Suspenders: guard raises on any other stdout write. Test: subprocess capture asserts every line is valid JSON-RPC.

### File Created
`.planning/phases/01-infrastructure-vault-io-and-mcp-skeleton/01-RESEARCH.md`

### Ready for Planning
Research complete. Planner can now create PLAN.md files.
