---
title: code-wiki-agent
category: package
summary: AWS Bedrock-powered wiki maintenance agent (MCP server + CLI)
status: active
package_path: agents/code-wiki-agent
package_type: library
language: python
exports: [code-wiki-agent, code-wiki-mcp]
depends_on: [vault-io, model-adapter, subagent-runtime, workspace-io]
depended_on_by: 0
tags: []
sources: 0
updated: 2026-05-18
tokens: 0
last_sync_commit:
last_sync_at:
workflow_hints:
  brainstorming: [context.md]
  planning:      [api.md, patterns.md]
  debugging:     [api.md, work.md]
---

# code-wiki-agent

## Purpose
AWS Bedrock-powered wiki maintenance agent (MCP server + CLI)

## File map - code-wiki-agent
TODO — describe what this directory contains.

- `pyproject.toml` — TODO

### code-wiki-agent/src/
TODO — describe what this directory contains.


#### code-wiki-agent/src/code_wiki_agent/
TODO — describe what this directory contains.

- `__init__.py` — TODO
- `cli.py` — TODO
- `config.py` — TODO

##### code-wiki-agent/src/code_wiki_agent/commands/
TODO — describe what this directory contains.

- `__init__.py` — TODO
- `ingest.py` — TODO
- `init.py` — TODO
- `lint.py` — TODO
- `log.py` — TODO
- `query.py` — TODO
- `scan.py` — TODO

##### code-wiki-agent/src/code_wiki_agent/prompts/
TODO — describe what this directory contains.

- `__init__.py` — TODO
- `code_reader.py` — TODO
- `ingestor.py` — TODO
- `librarian.py` — TODO
- `linter.py` — TODO
- `project_context.py` — TODO
- `scanner.py` — TODO
- `synthesizer.py` — TODO

###### code-wiki-agent/src/code_wiki_agent/prompts/_fragments/
TODO — describe what this directory contains.

- `__init__.py` — TODO
- `architecture_overview.py` — TODO
- `citation_rules.py` — TODO
- `claude_md_disambiguation.py` — TODO
- `frontmatter_rules.py` — TODO
- `iron_rules.py` — TODO
- `log_format.py` — TODO
- `page_categories.py` — TODO
- `style_rules.py` — TODO

#### code-wiki-agent/src/code_wiki_mcp/
TODO — describe what this directory contains.

- `__init__.py` — TODO
- `server.py` — TODO

### code-wiki-agent/tests/
TODO — describe what this directory contains.

- `conftest.py` — TODO
- `test_command_overrides.py` — TODO

#### code-wiki-agent/tests/commands/
TODO — describe what this directory contains.

- `__init__.py` — TODO
- `test_lint_parity.py` — TODO
- `test_scan_parity.py` — TODO

#### code-wiki-agent/tests/integration/
TODO — describe what this directory contains.

- `__init__.py` — TODO
- `test_bedrock_iam.py` — TODO
- `test_mcp_cancel.py` — TODO
- `test_mcp_e2e.py` — TODO
- `test_mcp_stdio.py` — TODO
- `test_query_e2e.py` — TODO

#### code-wiki-agent/tests/prompts/
TODO — describe what this directory contains.

- `__init__.py` — TODO
- `test_project_context.py` — TODO
- `test_prompt_snapshots.py` — TODO
- `test_provenance.py` — TODO
- `test_token_budget.py` — TODO

##### code-wiki-agent/tests/prompts/__snapshots__/
TODO — describe what this directory contains.

- `test_project_context.ambr` — TODO
- `test_prompt_snapshots.ambr` — TODO

#### code-wiki-agent/tests/unit/
TODO — describe what this directory contains.

- `__init__.py` — TODO
- `test_cli_help.py` — TODO
- `test_cli_query.py` — TODO
- `test_commands_ingest.py` — TODO
- `test_commands_init.py` — TODO
- `test_commands_lint.py` — TODO
- `test_commands_log.py` — TODO
- `test_commands_scan.py` — TODO
- `test_config.py` — TODO
- `test_mcp_new_tools.py` — TODO
- `test_mcp_query_schema.py` — TODO
- `test_query_code_fallback.py` — TODO
- `test_query_result.py` — TODO
- `test_query_search.py` — TODO
- `test_query_summary_schema_version.py` — TODO
- `test_stdout_guard.py` — TODO
- `test_trace_viewer.py` — TODO
- `test_wiki_scan_input.py` — TODO

##### code-wiki-agent/tests/unit/__snapshots__/
TODO — describe what this directory contains.

- `test_trace_viewer.ambr` — TODO

## Sub-pages
- [[api]]      — public API, exports, CLI subcommands
- [[patterns]] — key patterns and conventions
- [[work]]     — bugs, tech debt, features, open questions
- [[context]]  — concepts, decisions, ADRs, sources
