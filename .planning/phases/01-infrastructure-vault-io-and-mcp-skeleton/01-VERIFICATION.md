---
phase: 01-infrastructure-vault-io-and-mcp-skeleton
verified: 2026-05-13T19:00:00Z
status: human_needed
score: 16/16 must-haves verified
overrides_applied: 0
re_verification:
  previous_status: gaps_found
  previous_score: 14/16
  gaps_closed:
    - "ruff check . and ruff format --check . both exit 0 against a freshly synced workspace"
    - "vault-io modules do not leak stale lattice-workspace references into user-visible output"
  gaps_remaining: []
  regressions: []
human_verification:
  - test: "Run `CODE_WIKI_RUN_INTEGRATION=1 uv run --directory agents/code-wiki-agent pytest tests/integration/test_bedrock_iam.py -x -q` against Pat's AWS account after completing the Anthropic use case form in the Bedrock console"
    expected: "Test passes with 2 passed (or skipped + 1 passed if test_make_llm_raises_bedrock_access_denied_on_bad_creds is the only integration-marked one). Console output of `result.content` is non-empty."
    why_human: "Requires browser action (AWS Bedrock console → Model access → submit Anthropic use case form) and a 15-minute propagation wait. Cannot be automated from this verification process. The code path is fully implemented and mock-tested; only the account-state gate remains."
  - test: "Run `uv run python scripts/verify_bedrock_iam.py` and observe stderr"
    expected: "stderr contains 'Verifying Bedrock IAM (haiku role)...' followed by 'OK:' line; exit code 0"
    why_human: "Same AWS account-state gate as above. Mock-only check confirms BedrockAccessDenied raised on AccessDeniedException with the required substrings."
---

# Phase 1: Infrastructure, Vault IO, and MCP Skeleton Verification Report

**Phase Goal:** Bootstrap the uv workspace, scaffold the three Phase 1 members, install open-source hygiene, get the MCP stdio surface working, land the vault IO round-trip, and make a real Bedrock haiku invocation work end-to-end — the complete walking skeleton.

**Verified:** 2026-05-13T19:00:00Z
**Status:** human_needed
**Re-verification:** Yes — after gap closure (plan 01-05)

## Goal Achievement

### Observable Truths

| # | Truth | Status | Evidence |
| --- | --- | --- | --- |
| 1 | `uv sync` from a fresh clone produces a single repo-root `uv.lock` | VERIFIED | `uv.lock` (385KB) exists; `members = ["cores/*", "agents/*"]` in root `pyproject.toml`; no `[project]` table at root |
| 2 | `uv run code-wiki-agent --help` exits 0 and prints help text mentioning the program name | VERIFIED | Live run: `Usage: code-wiki-agent [OPTIONS]` in stdout; exit 0 |
| 3 | Per-member `pytest --collect-only` is scoped to each member (INFRA-03) | VERIFIED | `uv run --directory cores/vault-io pytest` collects 14 vault-io tests; `--directory cores/model-adapter pytest` collects 6; `--directory agents/code-wiki-agent pytest -m "not integration"` collects 9. CI workflow uses `--directory` correctly. |
| 4 | `ruff check .` and `ruff format --check .` both exit 0 against a freshly synced workspace | VERIFIED | `uv run ruff check .` → "All checks passed!" (exit 0); `uv run ruff format --check .` → "38 files already formatted" (exit 0). Gap closed by plan 01-05 Tasks 1+2: I001 suppressed via `# noqa: I001` on server.py future-import line; F401 unused Path import removed from append_log.py; F841 dead `vault = wiki` in main() removed from scan_monorepo.py; 11 files reformatted. |
| 5 | GitHub Actions ci.yml exists and references uv sync + ruff + per-member pytest | VERIFIED | `.github/workflows/ci.yml` has `uv sync`, `uv run ruff check .`, `uv run ruff format --check .`, three per-member pytest steps. With ruff now clean, a fresh push will pass CI. |
| 6 | CLAUDE.md uses `cores/` for the deep-agents tier (no `packages/*` references in the layout section) | VERIFIED | `grep -E 'packages/\*' CLAUDE.md \| grep -v 'lattice/packages'` returns empty; `cores/` present 3 times |
| 7 | REQUIREMENTS.md MCP-07 references `code-wiki-mcp` (not `code-wiki-agent-mcp`) | VERIFIED | `grep -c 'code-wiki-agent-mcp' .planning/REQUIREMENTS.md` returns 0; `code-wiki-mcp` present with D-14 provenance note |
| 8 | `make_llm("haiku")` returns ChatBedrockConverse whose model attribute matches the haiku ARN in models.toml | VERIFIED | `loader.py` uses `_GuardedChatBedrockConverse(model=model_id, region_name=region)`; 6 unit tests in `test_loader.py` pass including model_id attribute check |
| 9 | `.invoke('ping')` hits real Bedrock when `CODE_WIKI_RUN_INTEGRATION=1` and returns non-empty content | HUMAN | Live invoke blocked by AWS account-state gate (Anthropic use case form not submitted for the account in us-east-1). Code path fully implemented and mock-tested. |
| 10 | `AccessDeniedException` → `BedrockAccessDenied` with ARN + `bedrock:InvokeModel` in message | VERIFIED | `loader.py` `_format_access_denied_message()` emits "Model ARN attempted", "IAM action required: bedrock:InvokeModel", and example IAM policy with `arn:aws:bedrock:*::foundation-model/*`. Mock test exercises the path in default CI suite. |
| 11 | `uv run python scripts/verify_bedrock_iam.py` runs end-to-end (success or actionable-error path) | VERIFIED (import) / HUMAN (live) | Script is executable, imports `BedrockAccessDenied`, has tri-state exit codes, smoke-importable. Live run is an AWS account-state gate. |
| 12 | No Bedrock model ID string appears in `cores/model-adapter/src/**/*.py` (D-11) | VERIFIED | `grep -rn 'claude-haiku\|claude-sonnet' cores/model-adapter/src/ --include='*.py'` returns no matches (exit 1) |
| 13 | Round-trip golden gate: re-writing every fixture page produces identical bytes (VAULT-04) | VERIFIED | `tests/test_round_trip.py::test_round_trip_all_fixture_pages` PASSED in 0.25s; 148 `.md` files in fixture |
| 14 | Truncated-frontmatter page returns `("skipped", 0)` + stderr warning (VAULT-05) | VERIFIED | Both `test_update_page_skips_truncated_frontmatter` and `test_truncated_frontmatter_emits_stderr_warning` PASSED |
| 15 | `_is_placeholder_target` detects ellipsis + angle brackets, rejects normal links (VAULT-06) | VERIFIED | All 4 cases in `test_wikilink_predicate.py` PASSED |
| 16 | `layout_io.write_layout` writes deterministic bytes given the same input (VAULT-02) | VERIFIED | `test_write_layout_is_byte_stable`, `test_write_layout_replaces_existing_block`, `test_write_layout_handles_null_vault_dir` PASSED |
| 17 | All ported modules import cleanly (VAULT-07) | VERIFIED | `test_all_ports_importable` + `test_detect_containers_smoke` + `test_resolve_wiki_and_repo_*` PASSED |
| 18 | No source file in `cores/vault-io/src/vault_io/**` imports `lattice_wiki_core` or `lattice_workspace` | VERIFIED | `grep -rn 'lattice_wiki_core\|lattice_workspace' cores/vault-io/src/` returns no matches |
| 19 | `frontmatter.dumps()` does not appear in any write path under `cores/vault-io/src/` | VERIFIED | `grep -rn 'frontmatter\.dumps' cores/vault-io/src/` returns no matches (exit 1) |
| 20 | Subprocess MCP stdout is valid JSON-RPC; wiki_ping returns pong (MCP-05) | VERIFIED | `tests/integration/test_mcp_stdio.py` 2 passed; not marked integration (runs in CI by default) |
| 21 | `_StdoutGuard` raises on stray `print('x')` after server import | VERIFIED | `test_stdout_guard_raises_on_nonempty_write` PASSED; guard at line 53 precedes mcp/pydantic imports (awk ordering check passes) |
| 22 | `logging.basicConfig` routes all root-logger output to `sys.stderr` | VERIFIED | `server.py`: `logging.basicConfig(stream=sys.stderr, level=logging.WARNING, ...)` |
| 23 | Server uses `from mcp.server.fastmcp import FastMCP` (not `from fastmcp`) | VERIFIED | grep matches; no `from fastmcp` import |
| 24 | `mcp.run()` called with `transport="stdio"` explicitly | VERIFIED | `server.py main()`: `mcp.run(transport="stdio")` |
| 25 | MCP-08 anti-features absent (no resources, prompts, sampling, SSE/HTTP) | VERIFIED | `grep -E '@mcp.resource\|@mcp.prompt\|streamable_http\|create_sse_app'` returns no matches |
| 26 | vault-io modules do not leak stale lattice-workspace references into user-visible output | VERIFIED | `init_vault.py` result['layers'] now uses "pending Phase 5 workspace init"; three module docstrings (append_log.py, detect_containers.py, graph_analyzer.py) now reference `CODE_WIKI_REAL_VAULT_PATH`. Gap closed by plan 01-05 Task 3. |

**Score:** 16/16 must-have truths verified (2 previously FAILED are now VERIFIED; 1 remains HUMAN for AWS account-state gate)

### Re-verification: Gap-Closure Results

Both gaps from the initial VERIFICATION.md are now closed:

**Gap 0 — Ruff lint/format (CLOSED):**
- I001 in `agents/code-wiki-agent/src/code_wiki_mcp/server.py` → suppressed with `# noqa: I001` on the future-import line; guard-install ordering preserved (D-15)
- F401 in `cores/vault-io/src/vault_io/append_log.py` → unused `from pathlib import Path` removed
- F841 in `cores/vault-io/src/vault_io/scan_monorepo.py` → dead `vault = wiki` in `main()` removed (the used assignment at line 620 in `_collect_vault_pages()` is intact)
- 11 files reformatted by `ruff format .`; `ruff format --check .` now exits 0

**Gap 1 — Stale lattice-workspace references (CLOSED):**
- `init_vault.py` result['layers']['raw'] and ['work']: "owned by lattice-workspace" → "pending Phase 5 workspace init"
- `append_log.py` module docstring: `LATTICE_WORKSPACE env var` → `CODE_WIKI_REAL_VAULT_PATH env var`
- `detect_containers.py` usage docstring: `repo discovered via lattice-workspace` → `repo discovered via CODE_WIKI_REAL_VAULT_PATH or git`
- `graph_analyzer.py` module docstring: `via lattice-workspace` → `via vault_io._workspace.resolve_wiki_and_repo (reads CODE_WIKI_REAL_VAULT_PATH...)`

Remaining acceptable occurrences of `lattice-workspace` string:
- `init_vault.py:155` — intentional Phase-5 TODO marker; plan explicitly leaves this intact
- `_workspace.py:5` — negative documentation: "There is no lattice-workspace discovery in this codebase" — correct and useful

**Regressions:** None. `uv run pytest -q` → 29 passed, 1 skipped (same count as before gap closure). Round-trip gate, MCP stdio, stdout guard, and all invariants confirmed intact.

### Required Artifacts

| Artifact | Expected | Status | Details |
| --- | --- | --- | --- |
| `pyproject.toml` (root) | uv workspace, no [project], ruff config | VERIFIED | `members = ["cores/*", "agents/*"]`; no `[project]`; ruff line-length=120 + py311 + exclude fixtures |
| `.python-version` | `3.11` | VERIFIED | Contains `3.11` |
| `LICENSE` | MIT | VERIFIED | "MIT License" + "Copyright (c) 2026 Patrick Sprowls" |
| `README.md` | Quickstart + layout | VERIFIED | Present |
| `.gitignore` | Python + uv + env + IDE; NOT uv.lock | VERIFIED | Contains `__pycache__`; does NOT contain `uv.lock` |
| `.pre-commit-config.yaml` | astral-sh/ruff-pre-commit v0.15.12 | VERIFIED | Pins rev `v0.15.12`, both ruff + ruff-format hooks |
| `.github/workflows/ci.yml` | uv sync + ruff + per-member pytest | VERIFIED | Steps present; ruff commands now pass; setup-uv@v5 pinned 0.11.14 |
| `.github/workflows/eval.yml` | workflow_dispatch stub | VERIFIED | `on: workflow_dispatch`; single echo step |
| `cores/vault-io/pyproject.toml` | python-frontmatter + tiktoken + testpaths | VERIFIED | name=vault-io; testpaths=["tests"]; uv_build backend |
| `cores/model-adapter/pyproject.toml` | langchain-aws + boto3 + testpaths | VERIFIED | name=model-adapter; testpaths=["tests"]; uv_build |
| `agents/code-wiki-agent/pyproject.toml` | workspace deps + [project.scripts] for both entry points | VERIFIED | vault-io + model-adapter workspace sources; both `code-wiki-agent` and `code-wiki-mcp` scripts declared |
| `agents/code-wiki-agent/src/code_wiki_agent/cli.py` | Typer app with `--help` | VERIFIED | `app = typer.Typer(...)`; live run shows help output |
| `agents/code-wiki-agent/tests/unit/test_cli_help.py` | subprocess test for --help | VERIFIED | Test PASSED |
| `cores/model-adapter/models.toml` | haiku + sonnet roles with us-east-1 ARNs | VERIFIED | Contains `us.anthropic.claude-haiku-4-5-20251001-v1:0` and `us.anthropic.claude-sonnet-4-6` |
| `cores/model-adapter/src/model_adapter/exceptions.py` | `class BedrockAccessDenied` | VERIFIED | Present |
| `cores/model-adapter/src/model_adapter/loader.py` | `make_llm`; AccessDeniedException wrapping | VERIFIED | Subclass-override strategy; all three required error substrings emitted |
| `cores/model-adapter/src/model_adapter/__init__.py` | Re-exports `make_llm` + `BedrockAccessDenied` | VERIFIED | Re-exports present |
| `cores/model-adapter/tests/test_loader.py` | Unit tests | VERIFIED | 6 tests PASSED |
| `agents/code-wiki-agent/tests/integration/test_bedrock_iam.py` | `@pytest.mark.integration` + env gate | VERIFIED | Marker on live test; mock AccessDenied test runs in default suite |
| `scripts/verify_bedrock_iam.py` | Diagnostic; stderr-only; tri-state exit | VERIFIED | Executable; imports `BedrockAccessDenied`; smoke-importable |
| `cores/vault-io/src/vault_io/layout_io.py` | Hand-rolled YAML emitter; `write_layout` | VERIFIED | `def write_layout` present; `<!-- lattice-wiki:layout:start -->` sentinel preserved |
| `cores/vault-io/src/vault_io/update_tokens.py` | Truncated-frontmatter guard + raw-string write | VERIFIED | Contains `no closing frontmatter fence`; `raw.split("---", 2)` |
| `cores/vault-io/src/vault_io/lint/common.py` | `_is_placeholder_target` + WIKILINK_RE | VERIFIED | Both present |
| `cores/vault-io/src/vault_io/_workspace.py` | Raises on misconfig; reads `CODE_WIKI_REAL_VAULT_PATH` | VERIFIED | Both present |
| `cores/vault-io/tests/fixtures/round-trip-vault/` | ≥100 .md pages | VERIFIED | 148 .md files |
| `cores/vault-io/tests/test_round_trip.py` | git diff / hash-based round-trip | VERIFIED | 1 PASSED |
| `cores/vault-io/tests/test_truncated_frontmatter.py` | Skip + stderr warning | VERIFIED | 2 tests PASSED |
| `cores/vault-io/tests/test_wikilink_predicate.py` | 4-case predicate suite | VERIFIED | 4 tests PASSED |
| `cores/vault-io/tests/test_ports_importable.py` | VAULT-07 surface check | VERIFIED | 4 tests PASSED |
| `agents/code-wiki-agent/src/code_wiki_mcp/server.py` | FastMCP + _StdoutGuard + wiki_ping | VERIFIED | Correct import path; transport=stdio; anti-features absent; guard before mcp/pydantic; `# noqa: I001` added |
| `agents/code-wiki-agent/tests/integration/test_mcp_stdio.py` | subprocess JSON-RPC integrity test | VERIFIED | 2 tests PASSED |
| `agents/code-wiki-agent/tests/unit/test_stdout_guard.py` | guard unit tests | VERIFIED | 5 tests PASSED |
| `cores/vault-io/src/vault_io/append_log.py` | Ruff-clean; correct env-var docstring | VERIFIED | F401 removed; `CODE_WIKI_REAL_VAULT_PATH` in docstring |
| `cores/vault-io/src/vault_io/scan_monorepo.py` | Ruff-clean; no dead-code assignment in main() | VERIFIED | F841 removed from main(); active assignment at line 620 preserved |
| `cores/vault-io/src/vault_io/init_vault.py` | result['layers'] no longer leaks lattice-workspace | VERIFIED | "pending Phase 5 workspace init" in raw + work values |
| `cores/vault-io/src/vault_io/detect_containers.py` | Corrected env-var docstring | VERIFIED | `CODE_WIKI_REAL_VAULT_PATH` in usage docstring |
| `cores/vault-io/src/vault_io/graph_analyzer.py` | Corrected env-var docstring | VERIFIED | `CODE_WIKI_REAL_VAULT_PATH` in module docstring |

### Key Link Verification

| From | To | Via | Status | Details |
| --- | --- | --- | --- | --- |
| `pyproject.toml` (root) | `cores/vault-io`, `cores/model-adapter`, `agents/code-wiki-agent` | `[tool.uv.workspace] members` glob | WIRED | `members = ["cores/*", "agents/*"]` matches; uv.lock resolves all three |
| `agents/code-wiki-agent/pyproject.toml` | `vault-io`, `model-adapter` | `[tool.uv.sources] workspace = true` | WIRED | Both entries present |
| `agents/code-wiki-agent/pyproject.toml` | `code_wiki_agent.cli:app` | `[project.scripts]` | WIRED | `code-wiki-agent = "code_wiki_agent.cli:app"`; live --help works |
| `agents/code-wiki-agent/pyproject.toml` | `code_wiki_mcp.server:main` | `[project.scripts]` | WIRED | Subprocess test launches it successfully |
| `cores/model-adapter/src/model_adapter/loader.py` | `cores/model-adapter/models.toml` | `tomllib.load(_MODELS_TOML)` | WIRED | Works under `uv sync` editable install |
| `loader.py` | `ChatBedrockConverse` | `_GuardedChatBedrockConverse(ChatBedrockConverse)` | WIRED | Import present; subclass used |
| `loader.py` | `exceptions.BedrockAccessDenied` | `raise BedrockAccessDenied(...)` in subclass `invoke` | WIRED | Mock test verifies all three required substrings |
| `scripts/verify_bedrock_iam.py` | `model_adapter.loader.make_llm` | `from model_adapter.loader import make_llm` + `make_llm("haiku")` | WIRED | Lines 27, 31 |
| `cores/vault-io/src/vault_io/update_tokens.py` | `vault_io._workspace.resolve_wiki_and_repo` | `from vault_io._workspace import resolve_wiki_and_repo` | WIRED | Line 31 |
| `cores/vault-io/src/vault_io/scan_monorepo.py` | `vault_io.layout_io.read_layout` | `from vault_io.layout_io import read_layout` | WIRED | Line 46 |
| `tests/test_round_trip.py` | `vault_io.update_tokens.update_vault` | Import + invocation against fixture | WIRED | Test PASSED |
| `server.py` | `mcp.server.fastmcp.FastMCP` | `from mcp.server.fastmcp import FastMCP` + `mcp.run(transport="stdio")` | WIRED | Subprocess test confirms runtime behavior |
| `server.py` | `sys.stdout` | `_StdoutGuard` rebind BEFORE other imports | WIRED | Line 53 precedes lines 59/60 (mcp/pydantic); awk ordering check passes; `# noqa: I001` suppresses false isort positive |
| `.github/workflows/ci.yml` | `ruff check . / ruff format --check .` | CI lint step | WIRED | Both commands now exit 0; a fresh push will pass CI lint stage |

### Data-Flow Trace (Level 4)

| Artifact | Data Variable | Source | Produces Real Data | Status |
| --- | --- | --- | --- | --- |
| `wiki_ping` tool | `input: PingInput` | MCP client over stdin | Yes (echoes input.message) | FLOWING |
| `update_vault` | per-page frontmatter+body | filesystem read via python-frontmatter | Yes (148 fixture pages) | FLOWING |
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
| ruff lint | `uv run ruff check .` | All checks passed! (exit 0) | PASS |
| ruff format | `uv run ruff format --check .` | 38 files already formatted (exit 0) | PASS |

### Probe Execution

No conventional probes declared under `scripts/*/tests/probe-*.sh`. The phase's runnable-check surface is the pytest suite (covered above) plus `scripts/verify_bedrock_iam.py`. The script's `main()` cannot be executed automatically (blocked by AWS account-state gate — see Human Verification).

### Requirements Coverage

| Requirement | Source Plan | Description | Status | Evidence |
| --- | --- | --- | --- | --- |
| INFRA-01 | 01-01 | uv workspace root with `members = ["cores/*", "agents/*"]`, no `[project]` | SATISFIED | pyproject.toml correct |
| INFRA-02 | 01-01 | `uv sync` produces a single shared `uv.lock` | SATISFIED | uv.lock present at root |
| INFRA-03 | 01-01 | Per-member `testpaths`; pytest scoped per member | SATISFIED | Each member pyproject has `testpaths=["tests"]`; CI uses `--directory` |
| INFRA-04 | 01-01, 01-05 | MIT LICENSE, README, .gitignore, pre-commit ruff config; ruff passes | SATISFIED | All files exist AND `ruff check .` + `ruff format --check .` both exit 0 (gap closed by 01-05) |
| INFRA-05 | 01-01, 01-05 | CI scaffold runs uv sync + lint + per-member tests; eval opt-in | SATISFIED | ci.yml steps present; ruff commands now pass locally → CI lint stage will succeed on next push (gap closed by 01-05) |
| INFRA-06 | 01-01 | Python 3.11+ pinned; `uv run code-wiki-agent --help` from fresh clone | SATISFIED | .python-version pins 3.11; CLI works |
| BED-01 | 01-02 | Bedrock cross-region IAM verified; fail loudly with actionable guidance | PARTIAL | Code path complete + mock-tested; live invoke is an AWS account-state gate routed to human_verification |
| VAULT-01 | 01-03 | Read existing lattice-wiki vaults without modification | SATISFIED | Proved by round-trip on 148 real pages |
| VAULT-02 | 01-03 | Port `layout_io.py` verbatim; hand-rolled emitter preserves byte-identical output | SATISFIED | layout_io.py present; layout-io smoke tests pass |
| VAULT-03 | 01-03 | `python-frontmatter` reads only; writes through ported emitter | SATISFIED | `grep -rn 'frontmatter\.dumps' cores/vault-io/src/` returns no matches |
| VAULT-04 | 01-03 | `git diff` empty after round-trip on every page in a real vault | SATISFIED | Round-trip test passes against 148-page fixture |
| VAULT-05 | 01-03 | Truncated frontmatter handled without crash | SATISFIED | Two truncated-frontmatter tests pass |
| VAULT-06 | 01-03 | Wikilink placeholder predicate ported verbatim | SATISFIED | `_is_placeholder_target` in lint/common.py; 4 tests pass |
| VAULT-07 | 01-03 | All vault IO modules ported | SATISFIED | All ports importable; detect_containers smoke test passes |
| MCP-05 | 01-04 | All logging to stderr; nothing to stdout | SATISFIED | `_StdoutGuard` raises on stray writes; subprocess capture proves all stdout is JSON-RPC |
| MCP-08 | 01-04 | NOT in v1: MCP resources, prompts, sampling, SSE/HTTP | SATISFIED | grep confirms anti-features absent |

**Orphaned requirements check:** REQUIREMENTS.md maps Phase 1 to exactly INFRA-01..06, BED-01, VAULT-01..07, MCP-05, MCP-08. Plan frontmatter across 01-01..05 claims exactly these IDs (01-05 claims INFRA-04 and INFRA-05). No orphaned IDs.

### Anti-Patterns Found

| File | Line | Pattern | Severity | Impact |
| --- | --- | --- | --- | --- |
| `cores/vault-io/src/vault_io/init_vault.py` | 155 | `# TODO Phase 5: workspace init (lattice-workspace equivalent)` | Info | Intentional Phase-5 deferral marker; explicitly preserved by plan 01-05. Not a blocker. |
| `cores/vault-io/src/vault_io/scan_monorepo.py` | 278, 309, 315 etc. | `TODO`, `placeholder` strings | Info | Template strings written INTO the vault by the scan command (intentional output content, not source debt). |
| `cores/vault-io/src/vault_io/_workspace.py` | 5 | "There is no lattice-workspace discovery in this codebase." | Info | Accurate negative documentation explaining what this codebase does NOT do. Correct and useful. |

No `TBD`, `FIXME`, or `XXX` debt markers in Phase 1 source files. `TODO` markers all reference Phase 5 follow-up or are template content.

### Human Verification Required

1. **BED-01 live Bedrock invoke**

   **Test:** Submit the Anthropic use case form in the AWS Bedrock console for the account/region used by Pat's credentials. Then run:
   ```
   CODE_WIKI_RUN_INTEGRATION=1 uv run --directory agents/code-wiki-agent pytest tests/integration/test_bedrock_iam.py -x -q
   ```
   **Expected:** Test passes. `make_llm("haiku").invoke("ping")` returns non-empty `result.content`.

   **Why human:** Requires browser action (AWS Bedrock console → Model access → Anthropic Claude Haiku 4.5 → Submit use case details form) plus a propagation wait. Cannot be automated. Code path fully implemented and mock-tested.

2. **scripts/verify_bedrock_iam.py live diagnostic**

   **Test:**
   ```
   uv run python scripts/verify_bedrock_iam.py
   ```
   **Expected:** stderr line `Verifying Bedrock IAM (haiku role)...` then `OK:` line with `result.content` repr; exit code 0.

   **Why human:** Same AWS account-state gate as item 1.

### Gaps Summary

No gaps remain. Both gaps from the initial verification are closed:

- **Gap 0 (ruff lint/format):** CLOSED. `ruff check .` exits 0 ("All checks passed!"). `ruff format --check .` exits 0 ("38 files already formatted"). The CI lint stage will pass on next push.

- **Gap 1 (stale lattice-workspace references):** CLOSED. Four files updated. `init_vault.py` result['layers'] uses "pending Phase 5 workspace init". Three module docstrings reference `CODE_WIKI_REAL_VAULT_PATH`. No user-visible misleading references remain.

The only remaining non-VERIFIED item is BED-01 live invoke, which is an AWS account-state gate treated as `human_verification` (not a code gap) — the implementation is complete and mock-tested.

Forward-looking note: **CR-01 from REVIEW.md** (models.toml not in wheel — would break non-editable install) remains a distribution-time risk. Not a Phase 1 gap (editable install works). Suggested fix for later: load via `importlib.resources`.

---

_Verified: 2026-05-13T19:00:00Z_
_Verifier: Claude (gsd-verifier)_
_Re-verification: Yes — gap closure after plan 01-05_
