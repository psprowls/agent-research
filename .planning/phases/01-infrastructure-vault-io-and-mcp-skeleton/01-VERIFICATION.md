---
phase: 01-infrastructure-vault-io-and-mcp-skeleton
verified: 2026-05-13T00:00:00Z
status: gaps_found
score: 14/16 must-haves verified
overrides_applied: 0
gaps:
  - truth: "ruff check . and ruff format --check . both exit 0 against a freshly synced workspace"
    status: failed
    reason: "Running `uv run ruff check .` at the workspace root reports 3 errors (I001 import ordering in server.py, F401 unused Path import in append_log.py, F841 unused `vault` variable in scan_monorepo.py). Running `uv run ruff format --check .` reports 11 files would be reformatted. The CI workflow `.github/workflows/ci.yml` runs both `uv run ruff check .` and `uv run ruff format --check .` at root, so a fresh push would fail CI. This was claimed PASSED in 01-01-SUMMARY but is no longer true (or never was — both summaries lack explicit ruff exit-code evidence)."
    artifacts:
      - path: agents/code-wiki-agent/src/code_wiki_mcp/server.py
        issue: "I001 import block un-sorted: `from __future__`, `import sys` block at lines 14-16 is separated from later imports (logging/mcp/pydantic) by the guard install. Ruff wants them grouped; the design needs an isort skip or `# noqa: I001` on the import line."
      - path: cores/vault-io/src/vault_io/append_log.py
        issue: "F401 — `from pathlib import Path` at line 33 is imported but never used (ported verbatim from upstream; safe to drop in this codebase since the path-handling lives elsewhere)."
      - path: cores/vault-io/src/vault_io/scan_monorepo.py
        issue: "F841 — `vault = wiki` at line 1159 assigns a value never read (ported verbatim; ruff catches dead code that upstream's lint config did not)."
      - path: cores/vault-io/src/vault_io/update_tokens.py
        issue: "Format-only diff (ruff format --check fails)."
      - path: cores/vault-io/src/vault_io/_workspace.py
        issue: "Format-only diff."
      - path: cores/vault-io/src/vault_io/graph_analyzer.py
        issue: "Format-only diff."
      - path: cores/vault-io/src/vault_io/lint/common.py
        issue: "Format-only diff."
      - path: cores/vault-io/src/vault_io/update_index.py
        issue: "Format-only diff."
      - path: agents/code-wiki-agent/tests/integration/test_mcp_stdio.py
        issue: "Format-only diff."
      - path: agents/code-wiki-agent/tests/unit/test_stdout_guard.py
        issue: "Format-only diff (and would also need re-verification after fixing server.py I001)."
      - path: cores/vault-io/tests/test_layout_io_smoke.py
        issue: "Format-only diff."
      - path: cores/vault-io/tests/test_round_trip.py
        issue: "Format-only diff."
      - path: cores/vault-io/tests/test_truncated_frontmatter.py
        issue: "Format-only diff."
    missing:
      - "Run `uv run ruff check . --fix` to auto-fix F401 import + I001 ordering (the F841 vault assignment needs manual removal)"
      - "Run `uv run ruff format .` to format the 11 files"
      - "Add `# noqa: I001` to the server.py future-import block if the guard-install pattern is preserved (or move imports into a non-stdlib-only second group below the guard)"
      - "Re-run `uv run ruff check .` and `uv run ruff format --check .` — both must exit 0 before the Phase 1 INFRA-04/INFRA-05 contract holds"
  - truth: "vault-io modules do not leak stale lattice-workspace references into user-visible output"
    status: failed
    reason: "REVIEW WR-01 and WR-02 documented this but it was not fixed. `init_vault.py` lines 241-242 emit `'owned by lattice-workspace'` into the returned `result['layers']` dict, which surfaces in the JSON output of any Phase 5 `init` command. Three module docstrings (append_log.py:8, detect_containers.py:6, graph_analyzer.py:5) still claim `LATTICE_WORKSPACE` env var is read — but the actual codebase reads `CODE_WIKI_REAL_VAULT_PATH`. A developer following the docstrings will set the wrong env var and get RuntimeError. This contradicts VAULT-01..07's spirit even if no explicit must-have line item names it."
    artifacts:
      - path: cores/vault-io/src/vault_io/init_vault.py
        issue: "Lines 241-242 emit 'owned by lattice-workspace' string into user-facing result JSON; lines 246-247 share the same confusion."
      - path: cores/vault-io/src/vault_io/append_log.py
        issue: "Line 8 docstring claims LATTICE_WORKSPACE env var (false in this codebase)."
      - path: cores/vault-io/src/vault_io/detect_containers.py
        issue: "Line 6 docstring claims lattice-workspace discovery (false)."
      - path: cores/vault-io/src/vault_io/graph_analyzer.py
        issue: "Line 5 docstring claims wiki path 'discovered automatically via lattice-workspace' (false)."
    missing:
      - "Rewrite init_vault.py result['layers'] to either omit raw/work entries until Phase 5 or replace 'owned by lattice-workspace' annotation with a Phase 5 deferral notice"
      - "Update the three docstrings (append_log.py, detect_containers.py, graph_analyzer.py) to reference CODE_WIKI_REAL_VAULT_PATH instead of LATTICE_WORKSPACE"
human_verification:
  - test: "Run `CODE_WIKI_RUN_INTEGRATION=1 uv run --directory agents/code-wiki-agent pytest tests/integration/test_bedrock_iam.py -x -q` against Pat's AWS account after completing the Anthropic use case form in the Bedrock console"
    expected: "Test passes with 2 passed (or skipped + 1 passed if test_make_llm_raises_bedrock_access_denied_on_bad_creds is the only integration-marked one). Console output of `result.content` is non-empty."
    why_human: "Requires browser action (AWS Bedrock console → Model access → submit Anthropic use case form) and a 15-minute propagation wait. Cannot be automated from this verification process. The code path is fully implemented and mock-tested; only the account-state gate remains."
  - test: "Run `uv run python scripts/verify_bedrock_iam.py` and observe stderr"
    expected: "stderr contains 'Verifying Bedrock IAM (haiku role)...' followed by 'OK:' line; exit code 0"
    why_human: "Same AWS account-state gate as above. Mock-only check confirms BedrockAccessDenied raised on AccessDeniedException with the required substrings."
---

# Phase 1: Infrastructure, Vault IO, and MCP Skeleton Verification Report

**Phase Goal:** The monorepo is correctly scaffolded, Bedrock connectivity is proven end-to-end with the right IAM setup, vault IO passes round-trip fidelity on real vault pages, and the MCP server skeleton enforces stderr-only output before any tool logic is wired.

**Verified:** 2026-05-13
**Status:** gaps_found
**Re-verification:** No — initial verification

## Goal Achievement

### Observable Truths

| # | Truth | Status | Evidence |
| --- | --- | --- | --- |
| 1 | `uv sync` from a fresh clone produces a single repo-root `uv.lock` | VERIFIED | `uv.lock` (385KB) exists; `[tool.uv.workspace]` `members = ["cores/*", "agents/*"]` in `pyproject.toml`; `grep -E 'members = \["cores/\*", "agents/\*"\]' pyproject.toml` matches; no `[project]` table at root |
| 2 | `uv run code-wiki-agent --help` exits 0 and prints help text mentioning the program name | VERIFIED | Live run shows `Usage: code-wiki-agent [OPTIONS]` followed by Typer help; exit 0 |
| 3 | Per-member `pytest --collect-only` is scoped (INFRA-03) | VERIFIED (with adjustment) | `uv run --directory cores/vault-io pytest` collects 14 vault-io tests only; `uv run --directory cores/model-adapter pytest` collects 6; `uv run --directory agents/code-wiki-agent pytest -m "not integration"` collects 9 (cli-help, stdout-guard, mcp-stdio). NOTE: SUMMARY documents pivoting from `--package` to `--directory` because uv 0.11 does not chdir on `--package`. CI workflow uses `--directory` correctly. |
| 4 | `ruff check .` and `ruff format --check .` both exit 0 against a freshly synced workspace | FAILED | `uv run ruff check .` reports 3 errors (I001, F401, F841); `uv run ruff format --check .` would reformat 11 files. CI workflow runs both at root → would fail. See gaps[0]. |
| 5 | GitHub Actions ci.yml exists and references uv sync + ruff + per-member pytest | VERIFIED | `.github/workflows/ci.yml` present with `uv sync`, `uv run ruff check .`, `uv run ruff format --check .`, three per-member pytest steps using `--directory` |
| 6 | CLAUDE.md uses `cores/` (no `packages/*` deep-agents-tier references) | VERIFIED | `grep -E 'packages/\*' CLAUDE.md \| grep -v 'lattice/packages'` returns empty |
| 7 | REQUIREMENTS.md MCP-07 references `code-wiki-mcp` (not `code-wiki-agent-mcp`) | VERIFIED | `grep -c 'code-wiki-agent-mcp' .planning/REQUIREMENTS.md` returns 0; `code-wiki-mcp` present with D-14 provenance note |
| 8 | `make_llm("haiku")` returns ChatBedrockConverse whose model attribute matches the haiku ARN | VERIFIED | `loader.py` instantiates `_GuardedChatBedrockConverse(model=model_id, region_name=region)`; unit test in `test_loader.py` (6 passed) verifies via `model_id` attribute |
| 9 | `.invoke('ping')` hits real Bedrock when `CODE_WIKI_RUN_INTEGRATION=1` | HUMAN | Live invoke blocked by AWS account-state gate (Anthropic use case form not submitted for the account in us-east-1). Code path verified via mock test. Routed to `human_verification`. |
| 10 | `AccessDeniedException` → `BedrockAccessDenied` with ARN + `bedrock:InvokeModel` in message | VERIFIED | `loader.py` lines 31-39 (`_format_access_denied_message`) emits "Model ARN attempted", "IAM action required: bedrock:InvokeModel", and an example IAM policy line containing `arn:aws:bedrock:*::foundation-model/*`. Mock test in `test_loader.py` exercises the AccessDeniedException path; runs in CI by default. |
| 11 | `uv run python scripts/verify_bedrock_iam.py` runs end-to-end | VERIFIED (script importable) / HUMAN (live run) | Script exists, is executable, imports `BedrockAccessDenied`, has tri-state exit codes. Smoke importable. Live run is part of human verification (AWS gate). |
| 12 | No Bedrock model ID string appears in `cores/model-adapter/src/**/*.py` (D-11) | VERIFIED | `grep -rn 'claude-haiku\|claude-sonnet' cores/model-adapter/src/ --include='*.py'` returns no matches |
| 13 | Round-trip golden gate: re-writing every fixture page produces identical bytes (VAULT-04) | VERIFIED | `tests/test_round_trip.py::test_round_trip_all_fixture_pages PASSED` in 0.27s; fixture has 148 `.md` files |
| 14 | Truncated-frontmatter page returns `("skipped", 0)` + stderr warning (VAULT-05) | VERIFIED | Both `test_update_page_skips_truncated_frontmatter` and `test_truncated_frontmatter_emits_stderr_warning` PASSED |
| 15 | `_is_placeholder_target` detects ellipsis + angle brackets, rejects normal links (VAULT-06) | VERIFIED | All four cases in `test_wikilink_predicate.py` PASSED |
| 16 | `layout_io.write_layout` writes deterministic bytes given the same input (VAULT-02) | VERIFIED | `test_write_layout_is_byte_stable`, `test_write_layout_replaces_existing_block`, `test_write_layout_handles_null_vault_dir` all PASSED |
| 17 | All ported modules import cleanly | VERIFIED | `test_all_ports_importable` + `test_detect_containers_smoke` + `test_resolve_wiki_and_repo_*` PASSED |
| 18 | No source file in `cores/vault-io/src/vault_io/**` imports `lattice_wiki_core` or `lattice_workspace` | VERIFIED | `grep -rn 'lattice_wiki_core\|lattice_workspace' cores/vault-io/src/` returns no matches |
| 19 | `frontmatter.dumps()` does not appear in any write path under `cores/vault-io/src/` | VERIFIED | `grep -rn 'frontmatter\.dumps' cores/vault-io/src/` returns no matches |
| 20 | Subprocess MCP stdout is valid JSON-RPC; wiki_ping returns pong (MCP-05) | VERIFIED | `tests/integration/test_mcp_stdio.py` 2 passed; runs in default suite (no `pytest.mark.integration`). Stdout proven JSON-RPC; structuredContent has status=pong, echo=hello. |
| 21 | `_StdoutGuard` raises on stray `print('x')` after server import | VERIFIED | `test_stdout_guard_raises_on_nonempty_write` PASSED; guard installed at line 53, before mcp/pydantic imports at lines 59/60 (awk-ordering check passes) |
| 22 | `logging.basicConfig` routes to sys.stderr | VERIFIED | server.py line 65: `logging.basicConfig(stream=sys.stderr, level=logging.WARNING, ...)` |
| 23 | Server uses `from mcp.server.fastmcp import FastMCP` (correct import path) | VERIFIED | grep matches; no `from fastmcp` import |
| 24 | `mcp.run()` called with `transport="stdio"` explicitly | VERIFIED | server.py `main()`: `mcp.run(transport="stdio")` |
| 25 | MCP-08 anti-features absent (no resources, prompts, sampling, SSE/HTTP) | VERIFIED | `grep -E '@mcp.resource\|@mcp.prompt\|streamable_http\|create_sse_app' agents/code-wiki-agent/src/code_wiki_mcp/server.py` returns no matches |
| 26 | vault-io modules do not leak stale lattice-workspace references | FAILED | `init_vault.py` lines 241-242 emit 'owned by lattice-workspace' into user-visible result JSON; 3 docstrings still claim `LATTICE_WORKSPACE` env var. See gaps[1]. |

**Score:** 14/16 truths verified (of the must-have truths from PLAN frontmatter that gate Phase 1; the auxiliary observations above include cross-cutting verification of all 4 ROADMAP success criteria). Counting only must_haves explicit in plan frontmatter (truths from PLANs 01-01 / 01-02 / 01-03 / 01-04):

- Plan 01-01 truths (7): 6 verified, 1 failed (ruff)
- Plan 01-02 truths (6): 5 verified, 1 human (live Bedrock)
- Plan 01-03 truths (7): 7 verified
- Plan 01-04 truths (6): 6 verified

Adjusted score: **25/26 plan-frontmatter truths verified, 1 failed (ruff), 1 human (BED-01 live).** Cross-cutting failure from REVIEW WR-01/WR-02 (lattice-workspace leaks) recorded as gaps[1] even though no PLAN truth named it directly — it conflicts with the Phase 1 goal's "vault IO passes round-trip fidelity on real vault pages" spirit if any consumer relies on result JSON.

### Required Artifacts

| Artifact | Expected | Status | Details |
| --- | --- | --- | --- |
| `pyproject.toml` (root) | uv workspace, no [project], ruff config | VERIFIED | `members = ["cores/*", "agents/*"]`, no `[project]`, ruff line-length=120 + py311 + exclude fixtures + select E/F/I |
| `.python-version` | `3.11` | VERIFIED | Contains `3.11` |
| `LICENSE` | MIT | VERIFIED | "MIT License" + "Copyright (c) 2026 Patrick Sprowls" |
| `README.md` | Quickstart + layout | VERIFIED | Present, 1356 bytes |
| `.gitignore` | Python + uv + env + IDE; NOT uv.lock | VERIFIED | Contains `__pycache__`; does NOT contain `uv.lock` |
| `.pre-commit-config.yaml` | astral-sh/ruff-pre-commit v0.15.12 | VERIFIED | Pins rev `v0.15.12`, both ruff + ruff-format hooks |
| `.github/workflows/ci.yml` | uv sync + ruff + per-member pytest | VERIFIED (file) / FAILED (would fail at runtime due to ruff) | Steps present; setup-uv@v5 pinned 0.11.14; per-member uses `--directory` |
| `.github/workflows/eval.yml` | workflow_dispatch stub | VERIFIED | `on: workflow_dispatch`; single echo step |
| `cores/vault-io/pyproject.toml` | python-frontmatter + tiktoken + testpaths | VERIFIED | name=vault-io; testpaths=["tests"]; uv_build backend |
| `cores/model-adapter/pyproject.toml` | langchain-aws + boto3 + testpaths | VERIFIED | name=model-adapter; testpaths=["tests"]; uv_build |
| `agents/code-wiki-agent/pyproject.toml` | workspace deps + [project.scripts] for both entry points | VERIFIED | `[tool.uv.sources] vault-io = { workspace = true }` and `model-adapter = { workspace = true }`; scripts `code-wiki-agent = "code_wiki_agent.cli:app"` and `code-wiki-mcp = "code_wiki_mcp.server:main"` |
| `agents/code-wiki-agent/src/code_wiki_agent/cli.py` | Typer app with `--help` | VERIFIED | `app = typer.Typer(...)`; live run shows help output |
| `agents/code-wiki-agent/tests/unit/test_cli_help.py` | subprocess test for --help | VERIFIED | Test PASSED |
| `cores/model-adapter/models.toml` | haiku + sonnet roles with us-east-1 ARNs | VERIFIED | Contains `us.anthropic.claude-haiku-4-5-20251001-v1:0` and `us.anthropic.claude-sonnet-4-6`; region us-east-1 |
| `cores/model-adapter/src/model_adapter/exceptions.py` | `class BedrockAccessDenied` | VERIFIED | Present |
| `cores/model-adapter/src/model_adapter/loader.py` | `make_llm`; AccessDeniedException wrapping | VERIFIED | Subclass-override strategy; `_GuardedChatBedrockConverse`; error message contains all three required substrings |
| `cores/model-adapter/src/model_adapter/__init__.py` | Re-exports | VERIFIED | Re-exports `make_llm` and `BedrockAccessDenied` |
| `cores/model-adapter/tests/test_loader.py` | Unit tests | VERIFIED | 6 tests PASSED |
| `agents/code-wiki-agent/tests/integration/test_bedrock_iam.py` | `@pytest.mark.integration` + `CODE_WIKI_RUN_INTEGRATION` gate | VERIFIED | Marker on the live test; mock test runs in default suite |
| `scripts/verify_bedrock_iam.py` | Diagnostic; stderr-only; tri-state exit | VERIFIED | Executable; imports `BedrockAccessDenied`; smoke-importable |
| `cores/vault-io/src/vault_io/layout_io.py` | Hand-rolled YAML emitter; `write_layout` | VERIFIED | `def write_layout` present; `<!-- lattice-wiki:layout:start -->` sentinel preserved |
| `cores/vault-io/src/vault_io/update_tokens.py` | Truncated-frontmatter guard + raw-string write | VERIFIED | Contains `no closing frontmatter fence`; `raw.split("---", 2)` |
| `cores/vault-io/src/vault_io/lint/common.py` | `_is_placeholder_target` + WIKILINK_RE | VERIFIED | Both present |
| `cores/vault-io/src/vault_io/_workspace.py` | Raises on misconfig; reads `CODE_WIKI_REAL_VAULT_PATH` | VERIFIED | Contains both `CODE_WIKI_REAL_VAULT_PATH` and `raise RuntimeError` |
| `cores/vault-io/tests/fixtures/round-trip-vault/` | ≥100 .md pages | VERIFIED | 148 .md files |
| `cores/vault-io/tests/test_round_trip.py` | git diff / hash-based round-trip | VERIFIED | PASSED |
| `cores/vault-io/tests/test_truncated_frontmatter.py` | Skip + stderr warning | VERIFIED | 2 tests PASSED |
| `cores/vault-io/tests/test_wikilink_predicate.py` | 4-case predicate suite | VERIFIED | 4 tests PASSED |
| `cores/vault-io/tests/test_ports_importable.py` | VAULT-07 surface check | VERIFIED | 4 tests PASSED |
| `agents/code-wiki-agent/src/code_wiki_mcp/server.py` | FastMCP + _StdoutGuard + wiki_ping | VERIFIED | All checks pass (correct import path, transport=stdio, anti-features absent, guard installed before mcp/pydantic imports) |
| `agents/code-wiki-agent/tests/integration/test_mcp_stdio.py` | subprocess JSON-RPC integrity test | VERIFIED | 2 tests PASSED |
| `agents/code-wiki-agent/tests/unit/test_stdout_guard.py` | guard unit tests | VERIFIED | 5 tests PASSED |

### Key Link Verification

| From | To | Via | Status | Details |
| --- | --- | --- | --- | --- |
| `pyproject.toml` (root) | `cores/vault-io`, `cores/model-adapter`, `agents/code-wiki-agent` | `[tool.uv.workspace] members` glob | WIRED | `members = ["cores/*", "agents/*"]` matches; `uv.lock` resolves all three (per 01-01-SUMMARY) |
| `agents/code-wiki-agent/pyproject.toml` | `vault-io`, `model-adapter` | `[tool.uv.sources] workspace = true` | WIRED | Both entries present and matched by sources block |
| `agents/code-wiki-agent/pyproject.toml` | `code_wiki_agent.cli:app` | `[project.scripts]` | WIRED | `code-wiki-agent = "code_wiki_agent.cli:app"`; live `uv run code-wiki-agent --help` works |
| `agents/code-wiki-agent/pyproject.toml` | `code_wiki_mcp.server:main` | `[project.scripts]` | WIRED | Subprocess test launches it successfully |
| `cores/model-adapter/src/model_adapter/loader.py` | `cores/model-adapter/models.toml` | `tomllib.load(_MODELS_TOML)` | WIRED (editable) | Works under `uv sync`. NOTE: REVIEW CR-01 flagged this would BREAK under non-editable wheel install — not a Phase 1 must-have failure but a known distribution-time risk. |
| `loader.py` | `ChatBedrockConverse` | langchain_aws import + `_GuardedChatBedrockConverse(ChatBedrockConverse)` | WIRED | Import present; subclass used |
| `loader.py` | `exceptions.BedrockAccessDenied` | `raise BedrockAccessDenied(...)` in subclass `invoke` | WIRED | Test mocks the exception path; assertion verifies the three required substrings |
| `scripts/verify_bedrock_iam.py` | `model_adapter.loader.make_llm` | `from model_adapter.loader import make_llm` + `make_llm("haiku")` | WIRED | Lines 27, 31 |
| `cores/vault-io/src/vault_io/update_tokens.py` | `vault_io._workspace.resolve_wiki_and_repo` | `from vault_io._workspace import resolve_wiki_and_repo` | WIRED | Line 31 |
| `cores/vault-io/src/vault_io/scan_monorepo.py` | `vault_io.layout_io.read_layout` | `from vault_io.layout_io import read_layout` | WIRED | Line 46 |
| `tests/test_round_trip.py` | `vault_io.update_tokens.update_vault` | Import + invocation against fixture | WIRED | Test PASSED |
| `tests/test_round_trip.py` | `cores/vault-io/tests/fixtures/round-trip-vault/` | `shutil.copytree` + git diff / hash | WIRED | Test PASSED |
| `server.py` | `mcp.server.fastmcp.FastMCP` | `from mcp.server.fastmcp import FastMCP` + `FastMCP(name=...)` + `mcp.run(transport="stdio")` | WIRED | All three present; subprocess test confirms runtime behavior |
| `server.py` | `sys.stdout` | `_StdoutGuard` rebind BEFORE other imports | WIRED | Line 53 (`sys.stdout = _StdoutGuard()`) precedes line 59 (`from mcp.server.fastmcp import FastMCP`) and line 60 (`from pydantic import BaseModel`) — awk ordering check passes |

### Data-Flow Trace (Level 4)

| Artifact | Data Variable | Source | Produces Real Data | Status |
| --- | --- | --- | --- | --- |
| `wiki_ping` tool | `input: PingInput` | MCP client over stdin | Yes (echoes input.message) | FLOWING |
| `update_vault` | per-page frontmatter+body | filesystem read via python-frontmatter | Yes (148 fixture pages reach the wrapper) | FLOWING |
| `_GuardedChatBedrockConverse.invoke` | `model_id_for_errors` | Set via `object.__setattr__` in `make_llm` | Yes (per-instance) | FLOWING |
| `make_llm` | `config` | `tomllib.load(_MODELS_TOML)` | Yes (models.toml has haiku + sonnet entries) | FLOWING |

### Behavioral Spot-Checks

| Behavior | Command | Result | Status |
| --- | --- | --- | --- |
| CLI help | `uv run code-wiki-agent --help` | Exit 0; "Usage: code-wiki-agent [OPTIONS]" in stdout | PASS |
| Full pytest suite | `uv run pytest -q` | 29 passed, 1 skipped, 1 warning | PASS |
| vault-io tests | `uv run --directory cores/vault-io pytest -x -q` | 14 passed | PASS |
| model-adapter tests | `uv run --directory cores/model-adapter pytest` | 6 passed | PASS |
| code-wiki-agent tests (CI mode) | `uv run --directory agents/code-wiki-agent pytest -m "not integration"` | 9 passed, 1 deselected | PASS |
| MCP stdio integration | `uv run --directory agents/code-wiki-agent pytest tests/integration/test_mcp_stdio.py` | 2 passed | PASS |
| Round-trip golden gate | `uv run --directory cores/vault-io pytest tests/test_round_trip.py -v` | 1 passed | PASS |
| Stdout guard | `uv run --directory agents/code-wiki-agent pytest tests/unit/test_stdout_guard.py -v` | 5 passed | PASS |
| ruff lint | `uv run ruff check .` | 3 errors (I001, F401, F841) | FAIL |
| ruff format | `uv run ruff format --check .` | 11 files would be reformatted | FAIL |

### Probe Execution

No conventional probes declared under `scripts/*/tests/probe-*.sh`. The phase's runnable-check surface is the pytest suite (already covered above) plus `scripts/verify_bedrock_iam.py`. The script's `main()` cannot be executed automatically (blocked by AWS account-state gate — see Human Verification).

### Requirements Coverage

| Requirement | Source Plan | Description | Status | Evidence |
| --- | --- | --- | --- | --- |
| INFRA-01 | 01-01 | uv workspace root with `members = ["cores/*", "agents/*"]`, no `[project]` | SATISFIED | pyproject.toml correct |
| INFRA-02 | 01-01 | `uv sync` produces a single shared `uv.lock` | SATISFIED | uv.lock present (385KB) at root |
| INFRA-03 | 01-01 | Per-member `testpaths`; pytest scoped per member | SATISFIED | Each member pyproject has `testpaths=["tests"]`; CI uses `--directory` (per SUMMARY deviation) |
| INFRA-04 | 01-01 | MIT LICENSE, README, .gitignore, pre-commit ruff config | PARTIAL | All files exist, but the committed code does not pass `ruff check` / `ruff format --check` → pre-commit + CI would fail on a fresh push. The spirit of "lint config is enforceable" is breached. |
| INFRA-05 | 01-01 | CI scaffold (push-triggered) with uv sync + lint + per-member tests; opt-in eval | PARTIAL | Workflow files exist with correct steps. Real-run blocker: ruff steps fail (see INFRA-04). When ruff is fixed, INFRA-05 becomes fully satisfied. |
| INFRA-06 | 01-01 | Python 3.11+ pinned; `uv run code-wiki-agent --help` from fresh clone | SATISFIED | .python-version pins 3.11; CLI works |
| BED-01 | 01-02 | Bedrock cross-region IAM verified; fail loudly with actionable guidance | PARTIAL | Code path complete; mock-test gate passes; live invoke is an AWS account-state gate (Anthropic use case form not submitted in us-east-1). Per user instruction this routes to `human_verification`, not to a code failure. |
| VAULT-01 | 01-03 | Read existing lattice-wiki vaults without modification (frontmatter, layout, wikilinks, file maps, citations) | SATISFIED (indirect) | Proved by round-trip on 148 real pages |
| VAULT-02 | 01-03 | Port `layout_io.py` verbatim; hand-rolled emitter preserves whitespace/ordering | SATISFIED | layout_io.py present; layout-io smoke tests prove byte stability |
| VAULT-03 | 01-03 | `python-frontmatter` reads only; writes through ported emitter | SATISFIED | `grep -rn 'frontmatter\.dumps' cores/vault-io/src/` returns no matches |
| VAULT-04 | 01-03 | `git diff` empty after parsing-then-writing every page in a real vault | SATISFIED | Round-trip test passes against 148-page fixture |
| VAULT-05 | 01-03 | Truncated frontmatter handled without crash | SATISFIED | Two truncated-frontmatter tests pass; stderr warning emitted |
| VAULT-06 | 01-03 | Wikilink placeholder predicate ported verbatim | SATISFIED | `_is_placeholder_target` in lint/common.py; 4 tests pass |
| VAULT-07 | 01-03 | Container detection, monorepo scan, init, index, log, token counter, graph analyzer ported | SATISFIED | All ports importable; detect_containers smoke test passes |
| MCP-05 | 01-04 | All logging to stderr; nothing — even `print()` — to stdout | SATISFIED | `_StdoutGuard` raises on stray writes; subprocess capture proves every stdout line is JSON-RPC |
| MCP-08 | 01-04 | NOT in v1: MCP resources, prompts, sampling, SSE/HTTP transport | SATISFIED | grep confirms anti-features absent |

**Orphaned requirements check:** REQUIREMENTS.md maps Phase 1 to exactly the 16 IDs listed above (INFRA-01..06, BED-01, VAULT-01..07, MCP-05, MCP-08). PLAN frontmatter (across 01-01..04) claims those 16 IDs and no others. No orphaned IDs.

### Anti-Patterns Found

| File | Line | Pattern | Severity | Impact |
| --- | --- | --- | --- | --- |
| `cores/vault-io/src/vault_io/init_vault.py` | 155 | `# TODO Phase 5: workspace init (lattice-workspace equivalent)` | Info | Intentional deferral; referenced in 01-03 SUMMARY's "Known Stubs" section. Not a blocker — the comment names a follow-up phase and explains scope. |
| `cores/vault-io/src/vault_io/scan_monorepo.py` | 278, 309, 315, 319, 328, 331, 355, 362, 367 | `TODO`, `placeholder` strings | Info | Ported verbatim from upstream; these are template strings the scan command writes INTO the vault for the agent to fill in (intentional output content, not source debt). |
| `cores/vault-io/src/vault_io/init_vault.py` | 241-242 | `owned by lattice-workspace` string emitted into result['layers'] JSON | Warning | REVIEW WR-02; would surface as user-visible misleading text in Phase 5 init JSON output. Flagged as gap[1]. |
| `cores/vault-io/src/vault_io/append_log.py`, `detect_containers.py`, `graph_analyzer.py` | Module docstrings | Mention `LATTICE_WORKSPACE` env var (false — code reads `CODE_WIKI_REAL_VAULT_PATH`) | Warning | REVIEW WR-01; misleading documentation. Flagged as gap[1]. |
| `cores/vault-io/src/vault_io/append_log.py` | 33 | F401 — unused `Path` import | Warning | Ruff lint failure; part of gap[0]. |
| `cores/vault-io/src/vault_io/scan_monorepo.py` | 1159 | F841 — unused `vault = wiki` assignment | Warning | Ruff lint failure; part of gap[0]. |
| `agents/code-wiki-agent/src/code_wiki_mcp/server.py` | 14-16 | I001 — import block flagged un-sorted | Warning | Ruff lint failure; intentional ordering for `_StdoutGuard`-before-imports requires a noqa or restructuring; part of gap[0]. |

No `TBD`, `FIXME`, or `XXX` debt markers in Phase 1 source files (debt-marker gate passes — `TODO` markers all reference Phase 5 follow-up or are template content).

### Human Verification Required

1. **BED-01 live Bedrock invoke**

   **Test:** Submit the Anthropic use case form in the AWS Bedrock console for the account/region used by Pat's credentials. Then run:
   ```
   CODE_WIKI_RUN_INTEGRATION=1 uv run --directory agents/code-wiki-agent pytest tests/integration/test_bedrock_iam.py -x -q
   ```
   **Expected:** Test passes (1 + 1, or 2 — depending on selection). `make_llm("haiku").invoke("ping")` returns non-empty `result.content`.

   **Why human:** Requires browser action (AWS Bedrock console → Model access → Anthropic Claude Haiku 4.5 → Submit use case details form) plus a propagation wait of up to 15 minutes. Cannot be automated from this verification process. Per user instruction, treated as a human-verification item rather than an automated must-have gate because the code path is fully implemented and mock-tested.

2. **scripts/verify_bedrock_iam.py live diagnostic**

   **Test:**
   ```
   uv run python scripts/verify_bedrock_iam.py
   ```
   **Expected:** stderr line `Verifying Bedrock IAM (haiku role)...` then `OK:` line with the `result.content` repr; exit code 0.

   **Why human:** Same AWS account-state gate as item 1.

### Gaps Summary

Two gaps block claiming the phase fully met its goal:

1. **Ruff lint/format would fail CI on a fresh push.** The committed code triggers 3 ruff `check` errors and 11 ruff `format` reformat candidates. The CI workflow runs both at root and would fail on the next push. This breaks must-have truth "ruff check . and ruff format --check . both exit 0 against a freshly synced workspace" from Plan 01-01 frontmatter, and weakens INFRA-04 + INFRA-05 in spirit (the lint contract is supposed to be enforced, not silently broken). Fix is mechanical: run `uv run ruff check . --fix` + `uv run ruff format .` + add a `# noqa: I001` to the server.py future-import block to preserve the guard-install-first ordering. Re-run both ruff commands; both must exit 0.

2. **Stale "lattice-workspace" references leak into user-visible output.** REVIEW.md flagged this in WR-01 and WR-02 but no commit closed it. `init_vault.py` returns a `result['layers']` dict containing strings like `"owned by lattice-workspace"` — that text is part of any Phase 5 `init` command's JSON output. Three module docstrings claim `LATTICE_WORKSPACE` env var is read (false). A user following the docstrings will set the wrong env var and hit RuntimeError. Fix is mechanical: rewrite the four strings.

Both gaps are small, isolated, and groupable into one follow-up plan (a hygiene/lint sweep). They do not invalidate the major architectural achievements of Phase 1 — round-trip gate, _StdoutGuard, AccessDeniedException wrapping, workspace scaffolding all hold.

Additionally:

- **CR-01 from REVIEW.md** (models.toml not in wheel) is a distribution-time risk noted but NOT recorded as a Phase 1 gap because Phase 1's gate is editable-install behavior (which works); the issue surfaces only on wheel install. Worth tracking for Phase 2/3 if any consumer starts building wheels. Suggested fix: move `models.toml` into the package and load via `importlib.resources` — left as a forward-looking note, not a gap.

- **BED-01 live invoke** is genuinely blocked by an AWS account-state action (Anthropic use case form). Per user instruction, this is `human_verification`, not a gap.

---

_Verified: 2026-05-13_
_Verifier: Claude (gsd-verifier)_
