---
phase: 05-remaining-commands
plan: "01"
subsystem: code-wiki-agent / vault-io
tags: [commands, config, log, init, wave-0-scaffolding, cli, mcp]
dependency_graph:
  requires: []
  provides:
    - code_wiki_agent.config.WikiConfig
    - code_wiki_agent.config.load_config
    - code_wiki_agent.config.get_config
    - code_wiki_agent.commands.log.run_log
    - code_wiki_agent.commands.log.LogResult
    - code_wiki_agent.commands.init.run_init
    - code_wiki_agent.commands.init.InitResult
    - vault_io.init_vault.init_wiki (raw/ and work/ dirs)
  affects:
    - cli.py (added --config callback, log, init subcommands)
    - server.py (added wiki_log, wiki_init MCP tools; CODE_WIKI_CONFIG env read)
tech_stack:
  added:
    - tomllib (stdlib, Python 3.11+) — TOML config parsing
  patterns:
    - WikiConfig dataclass singleton with load_config() / get_config() accessors
    - @app.callback() for global CLI options
    - Lazy module import in CLI callback to avoid circular imports
    - MCP tool imports placed after mcp = FastMCP(...) to preserve _StdoutGuard invariant
key_files:
  created:
    - agents/code-wiki-agent/src/code_wiki_agent/config.py
    - agents/code-wiki-agent/src/code_wiki_agent/commands/log.py
    - agents/code-wiki-agent/src/code_wiki_agent/commands/init.py
    - agents/code-wiki-agent/tests/unit/test_config.py
    - agents/code-wiki-agent/tests/unit/test_commands_log.py
    - agents/code-wiki-agent/tests/unit/test_commands_init.py
    - agents/code-wiki-agent/tests/unit/test_commands_scan.py (skip stub)
    - agents/code-wiki-agent/tests/unit/test_commands_ingest.py (skip stub)
    - agents/code-wiki-agent/tests/unit/test_commands_lint.py (skip stub)
    - agents/code-wiki-agent/tests/unit/test_mcp_new_tools.py (skip stub)
    - cores/vault-io/tests/test_ingest_source.py (skip stub)
    - cores/vault-io/tests/test_ingest_work_item.py (skip stub)
    - cores/vault-io/tests/test_lint_modules.py (skip stub)
    - agents/code-wiki-agent/tests/commands/test_scan_parity.py (skip stub)
    - agents/code-wiki-agent/tests/commands/test_lint_parity.py (skip stub)
  modified:
    - agents/code-wiki-agent/src/code_wiki_agent/cli.py (--config callback, log, init commands)
    - agents/code-wiki-agent/src/code_wiki_mcp/server.py (wiki_log, wiki_init tools; CODE_WIKI_CONFIG)
    - cores/vault-io/src/vault_io/init_vault.py (raw/ and work/ mkdir; raw_path/work_path in return dict)
decisions:
  - "WikiConfig uses tomllib (stdlib) — no extra dep; unknown keys filtered by dataclass_fields dict"
  - "CLI callback uses lazy import of config module to avoid circular import at module load time"
  - "MCP wiki_log/wiki_init are async but do not call ctx.report_progress — both are fast sync ops per RESEARCH §G"
  - "init_wiki() signature unchanged; only body modified; plan-05-04 scan safe to depend on it"
  - "LogResult.detail is str | None (append_log can return None for detail)"
metrics:
  duration_seconds: 376
  completed_date: "2026-05-14"
  tasks_completed: 4
  tasks_total: 4
  files_created: 15
  files_modified: 3
---

# Phase 05 Plan 01: log + init commands + config plumbing Summary

Delivered the `log` and `init` command vertical slices end-to-end through both CLI and MCP surfaces, plus the global `--config` plumbing (D-11, D-12, D-13). Created all 11 Wave 0 test stub files. Resolved the `init_vault.py` Phase 5 TODO by creating `raw/` and `work/` sibling directories.

## Tasks Completed

| Task | Name | Commit | Files |
|------|------|--------|-------|
| 1 | Wave 0 test scaffolding | cad25b0 | 12 test files created |
| 2 | Config module + --config callback + CODE_WIKI_CONFIG | 7dd3b8f | config.py, cli.py, server.py |
| 3 | log command vertical slice | d6f11f4 | commands/log.py, cli.py, server.py |
| 4 | init command vertical slice + init_vault.py TODO | e56bff1 | commands/init.py, cli.py, server.py, init_vault.py |

## Tests Passing

| File | Tests |
|------|-------|
| agents/code-wiki-agent/tests/unit/test_config.py | 4 passed |
| agents/code-wiki-agent/tests/unit/test_commands_log.py | 5 passed |
| agents/code-wiki-agent/tests/unit/test_commands_init.py | 5 passed |
| cores/vault-io/tests/ (full suite) | 14 passed, 3 skipped (stubs) |

**Total: 14 real tests passing across this plan's deliverables.**

## Deviations from Plan

None — plan executed exactly as written.

## Key-Links Verified

| From | To | Via | Verified |
|------|----|-----|---------|
| cli.py | config.py | @app.callback() mutates _active_config | yes — test_config.py test_typer_callback_sets_active_config |
| server.py | config.py | main() reads CODE_WIKI_CONFIG | yes — grep confirmed; manual review of test_config.py |
| commands/log.py | vault_io.append_log | run_log calls append_log() | yes — test_commands_log.py test_run_log_appends_to_log_md |
| commands/init.py | vault_io.init_vault | run_init calls init_wiki(non_interactive=True) | yes — test_commands_init.py test_run_init_returns_init_result_with_raw_work |

## init_wiki() Signature Change Note

`init_wiki()` signature is **unchanged** — all parameters identical to pre-plan state. Only body changed: added two `mkdir` calls and two new keys (`raw_path`, `work_path`) in the returned dict. Plan-05-04 (scan) depends on init_wiki and can safely use it without updates.

## Open Issues for Downstream Plans

- `test_commands_scan.py`, `test_commands_ingest.py`, `test_commands_lint.py`, `test_mcp_new_tools.py`: all skipped with reason referencing future plan IDs — downstream plans flesh these out
- `test_ingest_source.py`, `test_ingest_work_item.py`, `test_lint_modules.py`: vault-io stubs for plans 05-02, 05-03
- `test_scan_parity.py`, `test_lint_parity.py`: integration stubs for plan-05-06

## Known Stubs

None — all functionality delivered in this plan is fully wired. The stub test files are intentional Wave 0 scaffolding for downstream plans, not data stubs.

## Threat Flags

None — no new network endpoints, auth paths, or schema changes at trust boundaries beyond what the plan's threat model already covers.

## Self-Check: PASSED

Files exist:
- agents/code-wiki-agent/src/code_wiki_agent/config.py ✓
- agents/code-wiki-agent/src/code_wiki_agent/commands/log.py ✓
- agents/code-wiki-agent/src/code_wiki_agent/commands/init.py ✓
- All 12 test files ✓

Commits exist:
- cad25b0 ✓
- 7dd3b8f ✓
- d6f11f4 ✓
- e56bff1 ✓
