---
phase: 05-remaining-commands
verified: 2026-05-14T20:00:00Z
status: human_needed
score: 4/5 must-haves verified
overrides_applied: 0
human_verification:
  - test: "Run `code-wiki-agent scan --json` against a real monorepo fixture and confirm the output contains `{added, updated, deleted}` keys with a non-empty list in at least one key. Scanner fan-out requires live Bedrock credentials."
    expected: "ScanResult JSON with at least one non-empty list among added/updated/deleted, plus a valid state_gate dict."
    why_human: "Scanner fan-out calls AWS Bedrock (scanner role). Unit tests mock the LLM boundary. Cannot verify actual Bedrock invocation or real vault writes without live credentials."
  - test: "Run `code-wiki-agent lint --json` against a real vault with `--stale-days 90` and confirm semantic findings are populated (page_quality, adr_chain, stale_claims keys non-empty)."
    expected: "LintResult JSON with semantic_findings containing at least one non-empty list, no errors key populated."
    why_human: "Semantic linter fan-out calls AWS Bedrock (linter role). Unit tests mock SubagentPool. Cannot verify actual 3-group fan-out behavior without live credentials."
  - test: "SC-5 parity baseline comparison: for any command (scan, lint, ingest, log, init), compare the new tool's output against a recorded lattice-wiki baseline on structural metrics (wikilinks present, frontmatter valid, package coverage)."
    expected: "Output structural metrics match recorded lattice-wiki baseline within acceptable tolerance."
    why_human: "No recorded scan/lint/ingest/log/init baselines exist in eval/baselines/ (all 8 baselines are query-only from Phase 4). SC-5 literally requires 'matches the recorded lattice-wiki baseline on all structural metrics'. The parity tests verify fixture-based invariants but do not compare against recorded lattice-wiki output. A human must decide: (a) record baselines for remaining commands and write baseline-comparison tests, OR (b) accept the fixture-invariant tests as sufficient parity evidence for these commands."
---

# Phase 05: Remaining Commands — Verification Report

**Phase Goal:** Deliver all remaining wiki commands (log, init, scan, ingest, lint) end-to-end through CLI and MCP so a user can run any code-wiki-agent command against a real vault.
**Verified:** 2026-05-14T20:00:00Z
**Status:** human_needed
**Re-verification:** No — initial verification

## Goal Achievement

### Observable Truths

| # | Truth | Status | Evidence |
|---|-------|--------|----------|
| 1 | User can run `code-wiki-agent log` and a line is appended to log.md | VERIFIED | `commands/log.py` has `run_log()` calling `append_log()`; 5 unit tests pass including `test_run_log_appends_to_log_md`; CLI `log` subcommand wired with `--op`, `--title`, `--detail`, `--vault`, `--json` options |
| 2 | User can run `code-wiki-agent init` and vault structure is created including raw/ and work/ | VERIFIED | `commands/init.py` calls `init_wiki(non_interactive=True)`; `init_vault.py` now creates `raw/` and `work/` siblings; 5 unit tests pass; TODO comment removed |
| 3 | `--config <path>` global option loads WikiConfig from TOML; `CODE_WIKI_CONFIG` env var loads config for MCP | VERIFIED | `config.py` has `WikiConfig` + `load_config()` + `_active_config` singleton; `@app.callback()` in `cli.py` (line 28) mutates singleton; `server.py:main()` reads `CODE_WIKI_CONFIG` (line 439); 4 unit tests pass |
| 4 | User can run `code-wiki-agent scan` with fan-out to produce ScanResult JSON | VERIFIED | `commands/scan.py` has `run_scan()`, `ScanResult`, `SCANNER_SYSTEM`, `SubagentPool.run_all()` with `role="scanner"`; stale-tag write-back implemented; file-map appended deterministically; 6 unit tests + 3 parity tests pass |
| 5 | User can run `code-wiki-agent ingest source <path>` and a wiki page is written | VERIFIED | `commands/ingest.py` has `run_ingest_source()` and `run_ingest_work_item()`; wired to `vault_io.ingest_source.extract` + ingestor LLM + `update_index()`; CLI `ingest source / work-item` sub-app wired; 6 unit tests pass |
| 6 | User can run `code-wiki-agent lint` and receive full mechanical+semantic report | VERIFIED | `commands/lint.py` (554 lines) ports `lint_wiki.py:scan()` inline, calls all 7 mechanical modules, runs 3-group semantic fan-out; `_is_placeholder_target` filter honored; 9 unit tests + 4 parity tests pass |
| 7 | All 6 MCP tools registered with typed Pydantic schemas and progress notifications | VERIFIED | `server.py` registers `wiki_log`, `wiki_init`, `wiki_scan`, `wiki_ingest`, `wiki_lint` (plus existing `wiki_query`); `wiki_scan`, `wiki_ingest`, `wiki_lint` each emit 2 progress notifications via `ctx.report_progress()`; 15 MCP unit tests pass |
| 8 | 7 lint mechanical modules ported from lattice-wiki-core with import swaps | VERIFIED | All 7 modules exist in `cores/vault-io/src/vault_io/lint/`; no `lattice_wiki_core` imports survive; each has `GROUP` constant and `check()` function; 11 module tests pass |
| 9 | `ingest_source.py` and `ingest_work_item.py` ported with subprocess replaced by direct imports | VERIFIED | Both files exist; `ingest_work_item.py` imports `from vault_io.update_index import update_index` and `from vault_io.append_log import append_log`; no `subprocess` or `_run_helper`; 45 tests pass |
| 10 | SC-5 parity tests compare output to recorded lattice-wiki baseline | PARTIAL | Parity tests exist (`test_scan_parity.py`, `test_lint_parity.py`) and verify structural invariants (broken_links non-empty, missing_frontmatter non-empty, placeholder filter, JSON round-trip). However, `eval/baselines/` contains only 8 query baselines (Phase 4). No recorded lattice-wiki scan/lint/ingest/log/init baselines exist. SC-5 literally requires "matches the recorded lattice-wiki baseline on all structural metrics." |

**Score:** 4/5 roadmap success criteria verified (SC-1 through SC-4 fully verified; SC-5 partially met — parity tests exist but without recorded lattice-wiki baselines for non-query commands)

### Required Artifacts

| Artifact | Expected | Status | Details |
|----------|----------|--------|---------|
| `agents/code-wiki-agent/src/code_wiki_agent/config.py` | WikiConfig + load_config() + _active_config | VERIFIED | 76 lines; all required symbols present |
| `agents/code-wiki-agent/src/code_wiki_agent/commands/log.py` | run_log() + LogResult | VERIFIED | 68 lines; calls `append_log()` |
| `agents/code-wiki-agent/src/code_wiki_agent/commands/init.py` | run_init() + InitResult | VERIFIED | 83 lines; calls `init_wiki(non_interactive=True)` |
| `agents/code-wiki-agent/src/code_wiki_agent/commands/scan.py` | run_scan() + ScanResult + SCANNER_SYSTEM + SubagentPool fan-out | VERIFIED | 448 lines (plan required min 150) |
| `agents/code-wiki-agent/src/code_wiki_agent/commands/ingest.py` | run_ingest_source() + run_ingest_work_item() + IngestResult + INGESTOR_SYSTEM | VERIFIED | 389 lines (plan required min 120) |
| `agents/code-wiki-agent/src/code_wiki_agent/commands/lint.py` | run_lint() + LintResult (18 fields) + 3 LINTER_*_SYSTEM + mechanical pass + semantic fan-out | VERIFIED | 554 lines (plan required min 300) |
| `cores/vault-io/src/vault_io/lint/{container,dependency,domain,file_map,package_sync,source_sync,workflow_hints}.py` | 7 modules with GROUP + check() | VERIFIED | All 7 files exist; sizes 43-155 lines; no lattice imports |
| `cores/vault-io/src/vault_io/ingest_source.py` | slugify, extract, guess_source_type, etc. | VERIFIED | 211 lines; all 7 functions + _HTMLTextExtractor exported |
| `cores/vault-io/src/vault_io/ingest_work_item.py` | _slugify, _parse_frontmatter, _validate, _emit_yaml, file_work_item() | VERIFIED | 183 lines; direct imports from update_index + append_log |
| `cores/vault-io/src/vault_io/init_vault.py` | raw/ + work/ mkdir; no TODO Phase 5 comment | VERIFIED | Lines 157-158 create raw/ and work/; return dict includes raw_path/work_path |
| All 12 Wave-0 test files | Non-stub test files for all commands | VERIFIED | 109 tests pass in code-wiki-agent; 70 tests pass in vault-io; all stubs replaced |
| `agents/code-wiki-agent/tests/commands/test_scan_parity.py` | Parity test for ScanResult shape | VERIFIED | 3 tests pass; tests ScanResult shape, state_gate keys, JSON round-trip |
| `agents/code-wiki-agent/tests/commands/test_lint_parity.py` | Parity test with fixture vault | VERIFIED | 4 tests pass including placeholder filter assertion (phase SC-3) |
| `cores/vault-io/tests/fixtures/edge-case-vault/` | Fixture vault for lint parity tests | VERIFIED | 4 files committed: CLAUDE.md, index.md, log.md, concepts/ |

### Key Link Verification

| From | To | Via | Status | Details |
|------|----|-----|--------|---------|
| `cli.py` | `config.py` | `@app.callback()` mutates `_active_config` | WIRED | Line 28 `@app.callback()`, line 36 `_cfg_module._active_config = _cfg_module.load_config(config)` |
| `server.py` | `config.py` | `main()` reads `CODE_WIKI_CONFIG` env var | WIRED | Line 439 `os.environ.get("CODE_WIKI_CONFIG")`, line 443 `load_config(Path(...))` |
| `commands/log.py` | `vault_io.append_log` | `run_log()` calls `append_log(wiki, op, title, detail)` | WIRED | Line 18 import; line 59 direct call |
| `commands/init.py` | `vault_io.init_vault` | `run_init()` calls `init_wiki(..., non_interactive=True)` | WIRED | Line 18 import; line 63 direct call |
| `commands/scan.py` | `subagent_runtime.pool.SubagentPool` | `SubagentPool.run_all(role="scanner")` | WIRED | Line 18 import; line 351 `SubagentPool(...)`, line 366 `role="scanner"` |
| `commands/scan.py` | `vault_io.scan_monorepo` | `discover_workspaces / compute_diff / build_file_map` | WIRED | Lines 22-30 import block |
| `commands/lint.py` | `vault_io.lint.{container,...}` | `from vault_io.lint.container import check as check_container_drift` (×7) | WIRED | Lines 45-51 import all 7 module check functions |
| `commands/lint.py` | `vault_io.lint.common._is_placeholder_target` | Used in `_mechanical_pass()` to filter wikilinks | WIRED | Line 40 import; lines 221, 254 usage in broken-link detection |
| `commands/lint.py` | `subagent_runtime.pool.SubagentPool` | 3-group semantic fan-out `role="linter"` | WIRED | Line 34 import; line 425 pool argument; line 472 `role="linter"` |
| `commands/ingest.py` | `vault_io.ingest_source` | `from vault_io.ingest_source import extract, slugify, guess_source_type` | WIRED | Line 28 import |
| `commands/ingest.py` | `vault_io.ingest_work_item` | `from vault_io.ingest_work_item import _parse_frontmatter, _validate, file_work_item` | WIRED | Line 29 import |
| `server.py` | `commands/scan.run_scan` | `from code_wiki_agent.commands.scan import ScanResult, run_scan` | WIRED | Line 237 import |
| `server.py` | `commands/ingest.run_ingest_source` | `from code_wiki_agent.commands.ingest import IngestResult, run_ingest_source, run_ingest_work_item` | WIRED | Line 289 import |
| `server.py` | `commands/lint.run_lint` | `from code_wiki_agent.commands.lint import LintResult, run_lint` | WIRED | Line 364 import |
| `ingest_work_item.py` | `vault_io.update_index.update_index` | Direct import, replaces `_run_helper("update_index.py")` | WIRED | Line 30 `from vault_io.update_index import update_index` |
| `ingest_work_item.py` | `vault_io.append_log.append_log` | Direct import, replaces `_run_helper("append_log.py")` | WIRED | Line 28 `from vault_io.append_log import append_log` |

### Data-Flow Trace (Level 4)

| Artifact | Data Variable | Source | Produces Real Data | Status |
|----------|---------------|--------|-------------------|--------|
| `commands/log.py:run_log()` | `result` dict | `append_log(wiki, op, title, detail)` → vault_io.append_log reads/writes log.md | Yes | FLOWING |
| `commands/init.py:run_init()` | `result` dict | `init_wiki()` → creates vault directory structure on disk | Yes | FLOWING |
| `commands/scan.py:run_scan()` | `fan_result.successes` | `SubagentPool.run_all()` → Bedrock scanner LLM (mocked in tests) | Real (Bedrock) | FLOWING |
| `commands/ingest.py:run_ingest_source()` | `resp.content` | `make_llm("ingestor").ainvoke()` → Bedrock ingestor LLM | Real (Bedrock) | FLOWING |
| `commands/lint.py:run_lint()` | `semantic_findings` | 3-group `SubagentPool.run_all()` → Bedrock linter LLM | Real (Bedrock) | FLOWING |
| `commands/lint.py:_mechanical_pass()` | `broken_links`, `orphans`, etc. | Walks vault files, parses frontmatter, builds link graph | Real filesystem | FLOWING |

### Behavioral Spot-Checks

| Behavior | Command | Result | Status |
|----------|---------|--------|--------|
| CLI shows all 6 commands | `uv run code-wiki-agent --help` | log, init, scan, lint, ingest, query all listed; `--config` global option shown | PASS |
| log subcommand has required options | `uv run code-wiki-agent log --help` | --op, --title, --detail, --vault, --json shown | PASS |
| lint subcommand has required options | `uv run code-wiki-agent lint --help` | --vault, --stale-days (default 90), --log-gap-days (default 14), --json shown | PASS |
| scan subcommand has required options | `uv run code-wiki-agent scan --help` | --vault, --no-file-map, --max-depth (default 3), --json shown | PASS |
| ingest sub-app dispatches correctly | `uv run code-wiki-agent ingest --help` | Shows `source` and `work-item` subcommands | PASS |
| ingest source has correct args | `uv run code-wiki-agent ingest source --help` | PATH positional arg + --vault, --json shown | PASS |
| ingest work-item has required options | `uv run code-wiki-agent ingest work-item --help` | --frontmatter, --body, --slug, --force, --pkg-dir, --vault, --json shown | PASS |
| Full vault-io test suite | `uv run --package vault-io pytest cores/vault-io/tests -q` | 70 passed in 0.69s | PASS |
| Full code-wiki-agent test suite | `uv run --package code-wiki-agent pytest agents/code-wiki-agent/tests/unit agents/code-wiki-agent/tests/commands -q` | 109 passed in 6.39s | PASS |

### Anti-Patterns Found

| File | Line | Pattern | Severity | Impact |
|------|------|---------|----------|--------|
| `commands/ingest.py` | 259, 263, 273 | `pass` in except blocks | Info | All are in try/except ValueError/OSError handlers for best-effort path relativization; correct usage, not stubs |
| `commands/scan.py` | 92 | `return []` in except | Info | In OSError handler for `rglob` failure; graceful degradation, not stub |
| `commands/lint.py` | 457 | `return []` in guard | Info | Early return when `pages_input` is empty (no pages to analyze); correct logic |
| `commands/lint.py` | 100 | "placeholder" in string literal | Info | In `LINTER_STALE_CLAIMS_SYSTEM` prompt constant, not code — describes what to look for |

No TBD, FIXME, or XXX markers found in any phase-modified file.

### Human Verification Required

#### 1. Scanner Fan-Out Against Real Bedrock

**Test:** Run `uv run code-wiki-agent scan --vault <real-vault-path> --json` against a real monorepo with AWS credentials configured.
**Expected:** JSON output with `{added, updated, deleted, renamed, errors, state_gate}` keys; at least one of added/updated/deleted is non-empty; scanner LLM generates stub bodies; `## File map` section is appended deterministically after LLM output; stale-tagged packages show `stale: true` in frontmatter.
**Why human:** Scanner fan-out invokes Bedrock (`us.anthropic.claude-...` scanner role). All unit tests mock `SubagentPool.run_all`. Actual Bedrock invocation and real vault writes require live credentials + a real monorepo.

#### 2. Semantic Linter Fan-Out Against Real Bedrock

**Test:** Run `uv run code-wiki-agent lint --vault <real-vault-path> --json` with AWS credentials.
**Expected:** LintResult JSON with all 18 fields; `semantic_findings.page_quality`, `semantic_findings.adr_chain`, `semantic_findings.stale_claims` each populated; `errors` list empty on clean vault; placeholder filter verified to produce no false positives on real vault wikilinks.
**Why human:** Linter semantic pass calls Bedrock linter role (3 parallel SubagentPool invocations). Tests mock at SubagentPool boundary.

#### 3. SC-5 Parity Baseline Decision

**Test:** Determine whether SC-5 ("each command has a parity test matching the recorded lattice-wiki baseline on all structural metrics") is satisfied by the fixture-invariant parity tests, or whether scan/lint/ingest/log/init baselines must be recorded using the lattice-wiki plugin and comparison tests added.
**Expected:** Developer decision on one of:
  - **Accept as-is:** The fixture-invariant parity tests (shape checks, non-empty findings, placeholder filter) are sufficient for Phase 5's purposes; baselines for non-query commands are a future concern.
  - **Record baselines:** Run lattice-wiki against fixture vaults for each new command, snapshot outputs to `eval/baselines/`, add comparison assertions to parity tests.
**Why human:** SC-5 literal text requires "matches the recorded lattice-wiki baseline." The eval infrastructure (EVAL-03) was built for query. No scan/lint/ingest/log/init baselines exist. The parity tests verify correct structural behavior against fixture vaults but do not compare to recorded lattice-wiki output. This is a scope question requiring a developer decision.

### Requirements Coverage

| Requirement | Source Plan | Description | Status | Evidence |
|-------------|------------|-------------|--------|---------|
| CMD-01 | 05-01 | `init` command — bootstrap vault, create dirs, render tool files | SATISFIED | `commands/init.py` + CLI `init` + MCP `wiki_init`; `init_vault.py` creates raw/ + work/; 5 unit tests pass |
| CMD-02 | 05-04 | `scan` command — walk repo, diff packages, fan-out, flag renames/deletions | SATISFIED | `commands/scan.py` with SubagentPool scanner fan-out; stale-tag write-back; `regenerate_dependencies_index` called; 6 unit tests + 3 parity tests pass |
| CMD-03 | 05-03, 05-05 | `ingest` command — extract, route, synthesize, update index, log | SATISFIED | `ingest_source.py` + `ingest_work_item.py` ported; `commands/ingest.py` with ingestor LLM call; `update_index()` called after write; 45 vault-io tests + 6 command tests pass |
| CMD-05 | 05-02, 05-06 | `lint` command — mechanical pass (7 modules + scan() port), semantic fan-out, placeholder filter | SATISFIED | `commands/lint.py` (554 lines); 7 modules imported with aliases; `_is_placeholder_target` filter wired; 3-group semantic fan-out; 9 unit tests + 4 parity tests pass |
| CMD-06 | 05-01 | `log` command — append timestamped event atomically | SATISFIED | `commands/log.py` calls `append_log()`; CLI `log` + MCP `wiki_log`; 5 unit tests pass |
| MCP-01 | 05-01, 05-04, 05-05, 05-06 | FastMCP server exposes all commands as typed MCP tools | SATISFIED | `server.py` registers `wiki_log`, `wiki_init`, `wiki_scan`, `wiki_ingest`, `wiki_lint` (+ existing `wiki_query`); Pydantic input/output schemas for each; 15 MCP tests pass |
| MCP-03 | 05-04, 05-05, 05-06 | Progress notifications for long-running commands | SATISFIED | `wiki_scan` emits 2 notifications; `wiki_ingest` emits 2; `wiki_lint` emits 2; `wiki_query` already had notifications; all verified in test_mcp_new_tools.py |

### Gaps Summary

No automated-verifiable blockers were found. All must-have truths are VERIFIED at the code level. All requirement IDs (CMD-01, CMD-02, CMD-03, CMD-05, CMD-06, MCP-01, MCP-03) are satisfied.

The `human_needed` status stems from three items that cannot be verified programmatically:

1. **Live Bedrock verification** (scan fan-out, lint semantic pass): unit tests mock Bedrock; actual Bedrock invocation with real credentials has not been verified in this verification pass.

2. **SC-5 parity baseline gap**: ROADMAP success criterion 5 requires comparing output to "recorded lattice-wiki baseline." No baselines exist for scan/lint/ingest/log/init commands. The parity tests verify structural correctness against fixture vaults but fall short of the SC-5 literal contract. Developer must decide scope.

The SC-5 gap is the most significant finding — it's a deviation from the roadmap contract. The code correctly implements all commands; the gap is in the evaluation infrastructure for the non-query commands.

---

_Verified: 2026-05-14T20:00:00Z_
_Verifier: Claude (gsd-verifier)_
