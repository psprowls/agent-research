# Codebase Map

Generated: 2026-05-31T22:23:19Z | Files: 500 | Described: 0/500
<!-- gsd:codebase-meta {"generatedAt":"2026-05-31T22:23:19Z","fingerprint":"3bcd98590f5821d5a10eed821c35c8e9e52be348","fileCount":500,"truncated":true} -->
Note: Truncated to first 500 files. Run with higher --max-files to include all.

### (root)/
- `.brand-grep-allow`
- `.cgignore`
- `.gitignore`
- `.pre-commit-config.yaml`
- `.python-version`
- `CLAUDE.md`
- `LICENSE`
- `README.md`

### .claude-plugin/
- `.claude-plugin/marketplace.json`

### .github/workflows/
- `.github/workflows/ci.yml`
- `.github/workflows/eval.yml`

### agents/graph-wiki-agent/
- `agents/graph-wiki-agent/pyproject.toml`

### agents/graph-wiki-agent/src/graph_wiki_agent/
- `agents/graph-wiki-agent/src/graph_wiki_agent/__init__.py`
- `agents/graph-wiki-agent/src/graph_wiki_agent/cli.py`
- `agents/graph-wiki-agent/src/graph_wiki_agent/config.py`
- `agents/graph-wiki-agent/src/graph_wiki_agent/graph_tools.py`
- `agents/graph-wiki-agent/src/graph_wiki_agent/uri_slug.py`

### agents/graph-wiki-agent/src/graph_wiki_agent/commands/
- `agents/graph-wiki-agent/src/graph_wiki_agent/commands/__init__.py`
- `agents/graph-wiki-agent/src/graph_wiki_agent/commands/_paths.py`
- `agents/graph-wiki-agent/src/graph_wiki_agent/commands/graph.py`
- `agents/graph-wiki-agent/src/graph_wiki_agent/commands/ingest.py`
- `agents/graph-wiki-agent/src/graph_wiki_agent/commands/init.py`
- `agents/graph-wiki-agent/src/graph_wiki_agent/commands/lint.py`
- `agents/graph-wiki-agent/src/graph_wiki_agent/commands/log.py`
- `agents/graph-wiki-agent/src/graph_wiki_agent/commands/migrate_vault.py`
- `agents/graph-wiki-agent/src/graph_wiki_agent/commands/propose_domains.py`
- `agents/graph-wiki-agent/src/graph_wiki_agent/commands/query.py`
- `agents/graph-wiki-agent/src/graph_wiki_agent/commands/scan.py`

### agents/graph-wiki-agent/src/graph_wiki_agent/mcp/
- `agents/graph-wiki-agent/src/graph_wiki_agent/mcp/__init__.py`
- `agents/graph-wiki-agent/src/graph_wiki_agent/mcp/server.py`

### agents/graph-wiki-agent/src/graph_wiki_agent/prompts/
- `agents/graph-wiki-agent/src/graph_wiki_agent/prompts/__init__.py`
- `agents/graph-wiki-agent/src/graph_wiki_agent/prompts/code_reader.py`
- `agents/graph-wiki-agent/src/graph_wiki_agent/prompts/ingestor.py`
- `agents/graph-wiki-agent/src/graph_wiki_agent/prompts/librarian.py`
- `agents/graph-wiki-agent/src/graph_wiki_agent/prompts/linter.py`
- `agents/graph-wiki-agent/src/graph_wiki_agent/prompts/project_context.py`
- `agents/graph-wiki-agent/src/graph_wiki_agent/prompts/scanner.py`
- `agents/graph-wiki-agent/src/graph_wiki_agent/prompts/synthesizer.py`

### agents/graph-wiki-agent/src/graph_wiki_agent/prompts/_fragments/
- `agents/graph-wiki-agent/src/graph_wiki_agent/prompts/_fragments/__init__.py`
- `agents/graph-wiki-agent/src/graph_wiki_agent/prompts/_fragments/architecture_overview.py`
- `agents/graph-wiki-agent/src/graph_wiki_agent/prompts/_fragments/citation_rules.py`
- `agents/graph-wiki-agent/src/graph_wiki_agent/prompts/_fragments/claude_md_disambiguation.py`
- `agents/graph-wiki-agent/src/graph_wiki_agent/prompts/_fragments/frontmatter_rules.py`
- `agents/graph-wiki-agent/src/graph_wiki_agent/prompts/_fragments/iron_rules.py`
- `agents/graph-wiki-agent/src/graph_wiki_agent/prompts/_fragments/log_format.py`
- `agents/graph-wiki-agent/src/graph_wiki_agent/prompts/_fragments/page_categories.py`
- `agents/graph-wiki-agent/src/graph_wiki_agent/prompts/_fragments/style_rules.py`

### agents/graph-wiki-agent/src/graph_wiki_agent/prompts/sources/
- `agents/graph-wiki-agent/src/graph_wiki_agent/prompts/sources/code_reader.md`
- `agents/graph-wiki-agent/src/graph_wiki_agent/prompts/sources/synthesizer.md`

### agents/graph-wiki-agent/tests/
- `agents/graph-wiki-agent/tests/conftest.py`
- `agents/graph-wiki-agent/tests/test_command_overrides.py`
- `agents/graph-wiki-agent/tests/test_ingest_trace_unit.py`
- `agents/graph-wiki-agent/tests/test_migrate_vault.py`
- `agents/graph-wiki-agent/tests/test_propose_domains.py`
- `agents/graph-wiki-agent/tests/test_query_graph_tools.py`
- `agents/graph-wiki-agent/tests/test_query_trace_unit.py`

### agents/graph-wiki-agent/tests/commands/
- `agents/graph-wiki-agent/tests/commands/__init__.py`
- `agents/graph-wiki-agent/tests/commands/test_lint_parity.py`
- `agents/graph-wiki-agent/tests/commands/test_scan_parity.py`

### agents/graph-wiki-agent/tests/integration/
- `agents/graph-wiki-agent/tests/integration/__init__.py`
- `agents/graph-wiki-agent/tests/integration/test_bedrock_iam.py`
- `agents/graph-wiki-agent/tests/integration/test_mcp_cancel.py`
- `agents/graph-wiki-agent/tests/integration/test_mcp_e2e.py`
- `agents/graph-wiki-agent/tests/integration/test_mcp_stdio.py`
- `agents/graph-wiki-agent/tests/integration/test_propose_domains_e2e.py`
- `agents/graph-wiki-agent/tests/integration/test_propose_domains_isolation.py`
- `agents/graph-wiki-agent/tests/integration/test_query_e2e.py`
- `agents/graph-wiki-agent/tests/integration/test_scan_entity_integration.py`
- `agents/graph-wiki-agent/tests/integration/test_scan_graph_end_to_end.py`
- `agents/graph-wiki-agent/tests/integration/test_trace_coverage.py`

### agents/graph-wiki-agent/tests/prompts/
- `agents/graph-wiki-agent/tests/prompts/__init__.py`
- `agents/graph-wiki-agent/tests/prompts/test_project_context.py`
- `agents/graph-wiki-agent/tests/prompts/test_prompt_snapshots.py`
- `agents/graph-wiki-agent/tests/prompts/test_provenance.py`
- `agents/graph-wiki-agent/tests/prompts/test_token_budget.py`

### agents/graph-wiki-agent/tests/prompts/__snapshots__/
- `agents/graph-wiki-agent/tests/prompts/__snapshots__/test_project_context.ambr`
- `agents/graph-wiki-agent/tests/prompts/__snapshots__/test_prompt_snapshots.ambr`

### agents/graph-wiki-agent/tests/unit/
- *(29 files: 29 .py)*

### agents/graph-wiki-agent/tests/unit/__snapshots__/
- `agents/graph-wiki-agent/tests/unit/__snapshots__/test_commands_graph.ambr`
- `agents/graph-wiki-agent/tests/unit/__snapshots__/test_trace_viewer.ambr`

### docs/notes/
- `docs/notes/cancellation.md`
- `docs/notes/testing.md`
- `docs/notes/trace-schema.md`

### eval/
- `eval/README.md`

### eval/baselines/
- `eval/baselines/concept-01.json`
- `eval/baselines/cross-ref-01.json`
- `eval/baselines/edge-case-01.json`
- `eval/baselines/edge-case-02.json`
- `eval/baselines/format-01.json`
- `eval/baselines/pkg-lookup-01.json`
- `eval/baselines/single-pkg-01.json`
- `eval/baselines/single-pkg-02.json`

### eval/cases/
- `eval/cases/code_reader_cases.json`
- `eval/cases/query_cases.json`

### packages/eval-harness/
- `packages/eval-harness/pyproject.toml`

### packages/eval-harness/baselines/
- `packages/eval-harness/baselines/divergence-ingestor.json`
- `packages/eval-harness/baselines/divergence-librarian.json`
- `packages/eval-harness/baselines/divergence-linter.json`
- `packages/eval-harness/baselines/divergence-scanner.json`

### packages/eval-harness/src/eval_harness/
- `packages/eval-harness/src/eval_harness/__init__.py`
- `packages/eval-harness/src/eval_harness/baseline.py`
- `packages/eval-harness/src/eval_harness/isolation.py`
- `packages/eval-harness/src/eval_harness/judge.py`
- `packages/eval-harness/src/eval_harness/preflight.py`
- `packages/eval-harness/src/eval_harness/pricing.py`
- `packages/eval-harness/src/eval_harness/report.py`
- `packages/eval-harness/src/eval_harness/structural.py`
- `packages/eval-harness/src/eval_harness/sweep.py`
- `packages/eval-harness/src/eval_harness/two_gate.py`

### packages/eval-harness/src/eval_harness/divergence/
- `packages/eval-harness/src/eval_harness/divergence/__init__.py`
- `packages/eval-harness/src/eval_harness/divergence/check.py`
- `packages/eval-harness/src/eval_harness/divergence/code_reader.py`
- `packages/eval-harness/src/eval_harness/divergence/ingestor.py`
- `packages/eval-harness/src/eval_harness/divergence/librarian.py`
- `packages/eval-harness/src/eval_harness/divergence/linter.py`
- `packages/eval-harness/src/eval_harness/divergence/metric.py`
- `packages/eval-harness/src/eval_harness/divergence/scanner.py`
- `packages/eval-harness/src/eval_harness/divergence/synthesizer.py`

### packages/eval-harness/src/eval_harness/divergence/rubrics/
- `packages/eval-harness/src/eval_harness/divergence/rubrics/code_reader.md`
- `packages/eval-harness/src/eval_harness/divergence/rubrics/ingestor.md`
- `packages/eval-harness/src/eval_harness/divergence/rubrics/librarian.md`
- `packages/eval-harness/src/eval_harness/divergence/rubrics/linter.md`
- `packages/eval-harness/src/eval_harness/divergence/rubrics/scanner.md`
- `packages/eval-harness/src/eval_harness/divergence/rubrics/synthesizer.md`

### packages/eval-harness/tests/
- *(21 files: 21 .py)*

### packages/eval-harness/tests/eval/
- `packages/eval-harness/tests/eval/__init__.py`
- `packages/eval-harness/tests/eval/test_sweep_dry_run.py`
- `packages/eval-harness/tests/eval/test_sweep_eval.py`

### packages/eval-harness/tests/fixtures/post-rebrand-vault/
- `packages/eval-harness/tests/fixtures/post-rebrand-vault/index.md`

### packages/eval-harness/tests/fixtures/post-rebrand-vault/packages/eval-harness/
- `packages/eval-harness/tests/fixtures/post-rebrand-vault/packages/eval-harness/eval-harness.md`

### packages/eval-harness/tests/fixtures/post-rebrand-vault/packages/model-adapter/
- `packages/eval-harness/tests/fixtures/post-rebrand-vault/packages/model-adapter/model-adapter.md`

### packages/eval-harness/tests/fixtures/post-rebrand-vault/packages/prompt-sources/
- `packages/eval-harness/tests/fixtures/post-rebrand-vault/packages/prompt-sources/prompt-sources.md`

### packages/eval-harness/tests/fixtures/post-rebrand-vault/packages/subagent-runtime/
- `packages/eval-harness/tests/fixtures/post-rebrand-vault/packages/subagent-runtime/subagent-runtime.md`

### packages/eval-harness/tests/fixtures/post-rebrand-vault/packages/wiki-io/
- `packages/eval-harness/tests/fixtures/post-rebrand-vault/packages/wiki-io/wiki-io.md`

### packages/eval-harness/tests/fixtures/post-rebrand-vault/packages/workspace-io/
- `packages/eval-harness/tests/fixtures/post-rebrand-vault/packages/workspace-io/workspace-io.md`

### packages/graph-io/
- `packages/graph-io/CLAUDE.md`
- `packages/graph-io/conftest.py`
- `packages/graph-io/pyproject.toml`
- `packages/graph-io/README.md`

### packages/graph-io/src/graph_io/
- *(23 files: 23 .py)*

### packages/graph-io/src/graph_io/cli/
- *(36 files: 36 .py)*

### packages/graph-io/tests/
- *(37 files: 37 .py)*

### packages/graph-io/tests/fixtures/
- `packages/graph-io/tests/fixtures/conftest.py`

### packages/graph-io/tests/fixtures/sample_monorepo/
- `packages/graph-io/tests/fixtures/sample_monorepo/domains.yaml`
- `packages/graph-io/tests/fixtures/sample_monorepo/pyproject.toml`

### packages/graph-io/tests/fixtures/sample_monorepo/packages/commonlib/
- `packages/graph-io/tests/fixtures/sample_monorepo/packages/commonlib/pyproject.toml`

### packages/graph-io/tests/fixtures/sample_monorepo/packages/commonlib/src/commonlib/
- `packages/graph-io/tests/fixtures/sample_monorepo/packages/commonlib/src/commonlib/__init__.py`

### packages/graph-io/tests/fixtures/sample_monorepo/packages/jspkg/
- `packages/graph-io/tests/fixtures/sample_monorepo/packages/jspkg/index.js`
- `packages/graph-io/tests/fixtures/sample_monorepo/packages/jspkg/package.json`
- `packages/graph-io/tests/fixtures/sample_monorepo/packages/jspkg/types.d.ts`

### packages/graph-io/tests/fixtures/sample_monorepo/packages/jspkg/__tests__/
- `packages/graph-io/tests/fixtures/sample_monorepo/packages/jspkg/__tests__/__init__placeholder`
- `packages/graph-io/tests/fixtures/sample_monorepo/packages/jspkg/__tests__/index.test.js`

### packages/graph-io/tests/fixtures/sample_monorepo/packages/jspkg/gen/
- `packages/graph-io/tests/fixtures/sample_monorepo/packages/jspkg/gen/data.gen.ts`

### packages/graph-io/tests/fixtures/sample_monorepo/packages/mypkg/
- `packages/graph-io/tests/fixtures/sample_monorepo/packages/mypkg/pyproject.toml`

### packages/graph-io/tests/fixtures/sample_monorepo/packages/mypkg/scripts/
- `packages/graph-io/tests/fixtures/sample_monorepo/packages/mypkg/scripts/run.sh`

### packages/graph-io/tests/fixtures/sample_monorepo/packages/mypkg/src/mypkg/
- `packages/graph-io/tests/fixtures/sample_monorepo/packages/mypkg/src/mypkg/__init__.py`
- `packages/graph-io/tests/fixtures/sample_monorepo/packages/mypkg/src/mypkg/foo.py`

### packages/graph-io/tests/fixtures/sample_monorepo/packages/mypkg/src/mypkg/proto/
- `packages/graph-io/tests/fixtures/sample_monorepo/packages/mypkg/src/mypkg/proto/data_pb2.py`

### packages/graph-io/tests/fixtures/sample_monorepo/packages/mypkg/src/mypkg/sub/
- `packages/graph-io/tests/fixtures/sample_monorepo/packages/mypkg/src/mypkg/sub/__init__.py`
- `packages/graph-io/tests/fixtures/sample_monorepo/packages/mypkg/src/mypkg/sub/bar.py`

### packages/graph-io/tests/fixtures/sample_monorepo/packages/mypkg/src/mypkg/sub/deep/
- `packages/graph-io/tests/fixtures/sample_monorepo/packages/mypkg/src/mypkg/sub/deep/__init__.py`
- `packages/graph-io/tests/fixtures/sample_monorepo/packages/mypkg/src/mypkg/sub/deep/baz.py`

### packages/graph-io/tests/fixtures/sample_monorepo/packages/mypkg/tests/
- `packages/graph-io/tests/fixtures/sample_monorepo/packages/mypkg/tests/test_foo.py`

### packages/graph-io/tests/fixtures/sample_monorepo/packages/pyutil/
- `packages/graph-io/tests/fixtures/sample_monorepo/packages/pyutil/pyproject.toml`

### packages/graph-io/tests/fixtures/sample_monorepo/packages/pyutil/src/pyutil/
- `packages/graph-io/tests/fixtures/sample_monorepo/packages/pyutil/src/pyutil/__init__.py`

### packages/graph-io/tests/fixtures/sample_monorepo/packages/webutil/
- `packages/graph-io/tests/fixtures/sample_monorepo/packages/webutil/pyproject.toml`

### packages/graph-io/tests/fixtures/sample_monorepo/packages/webutil/src/webutil/
- `packages/graph-io/tests/fixtures/sample_monorepo/packages/webutil/src/webutil/__init__.py`

### packages/graph-io/tests/fixtures/sample_monorepo/tests/integration/
- `packages/graph-io/tests/fixtures/sample_monorepo/tests/integration/test_top.py`

### packages/graph-io/tests/fixtures/sample_monorepo/tests/unit/
- `packages/graph-io/tests/fixtures/sample_monorepo/tests/unit/test_core.py`

### packages/graph-io/tests/integration/
- `packages/graph-io/tests/integration/__init__.py`
- `packages/graph-io/tests/integration/test_cluster_cli.py`
- `packages/graph-io/tests/integration/test_e2e_apps.py`
- `packages/graph-io/tests/integration/test_e2e_builtins.py`

### packages/graph-wiki-cli/
- `packages/graph-wiki-cli/pyproject.toml`

### packages/graph-wiki-cli/src/graph_wiki_cli/
- `packages/graph-wiki-cli/src/graph_wiki_cli/__init__.py`
- `packages/graph-wiki-cli/src/graph_wiki_cli/cli.py`

### packages/graph-wiki-cli/tests/
- `packages/graph-wiki-cli/tests/conftest.py`
- `packages/graph-wiki-cli/tests/test_cli_package.py`

### packages/graph-wiki-cli/tests/unit/
- `packages/graph-wiki-cli/tests/unit/test_cli_bootstrap.py`
- `packages/graph-wiki-cli/tests/unit/test_cli_boundary.py`
- `packages/graph-wiki-cli/tests/unit/test_cli_help.py`
- `packages/graph-wiki-cli/tests/unit/test_cli_query.py`
- `packages/graph-wiki-cli/tests/unit/test_commands_bootstrap.py`
- `packages/graph-wiki-cli/tests/unit/test_commands_graph.py`
- `packages/graph-wiki-cli/tests/unit/test_commands_log.py`
- `packages/graph-wiki-cli/tests/unit/test_plugin_bedrock_shims.py`
- `packages/graph-wiki-cli/tests/unit/test_runtime_docs.py`
- `packages/graph-wiki-cli/tests/unit/test_seeded_graph_workspace_smoke.py`
- `packages/graph-wiki-cli/tests/unit/test_trace_viewer.py`

### packages/graph-wiki-cli/tests/unit/__snapshots__/
- `packages/graph-wiki-cli/tests/unit/__snapshots__/test_commands_graph.ambr`
- `packages/graph-wiki-cli/tests/unit/__snapshots__/test_trace_viewer.ambr`

### packages/graph-wiki-core/
- `packages/graph-wiki-core/pyproject.toml`

### packages/graph-wiki-core/src/graph_wiki_core/
- `packages/graph-wiki-core/src/graph_wiki_core/__init__.py`
- `packages/graph-wiki-core/src/graph_wiki_core/config.py`
- `packages/graph-wiki-core/src/graph_wiki_core/graph_tools.py`
- `packages/graph-wiki-core/src/graph_wiki_core/uri_slug.py`

### packages/graph-wiki-core/src/graph_wiki_core/commands/
- `packages/graph-wiki-core/src/graph_wiki_core/commands/__init__.py`
- `packages/graph-wiki-core/src/graph_wiki_core/commands/_paths.py`
- `packages/graph-wiki-core/src/graph_wiki_core/commands/graph.py`
- `packages/graph-wiki-core/src/graph_wiki_core/commands/ingest.py`
- `packages/graph-wiki-core/src/graph_wiki_core/commands/init.py`
- `packages/graph-wiki-core/src/graph_wiki_core/commands/lint.py`
- `packages/graph-wiki-core/src/graph_wiki_core/commands/log.py`
- `packages/graph-wiki-core/src/graph_wiki_core/commands/migrate_vault.py`
- `packages/graph-wiki-core/src/graph_wiki_core/commands/propose_domains.py`
- `packages/graph-wiki-core/src/graph_wiki_core/commands/query.py`
- `packages/graph-wiki-core/src/graph_wiki_core/commands/scan.py`

### packages/graph-wiki-core/src/graph_wiki_core/prompts/
- `packages/graph-wiki-core/src/graph_wiki_core/prompts/__init__.py`
- `packages/graph-wiki-core/src/graph_wiki_core/prompts/code_reader.py`
- `packages/graph-wiki-core/src/graph_wiki_core/prompts/ingestor.py`
- `packages/graph-wiki-core/src/graph_wiki_core/prompts/librarian.py`
- `packages/graph-wiki-core/src/graph_wiki_core/prompts/linter.py`
- `packages/graph-wiki-core/src/graph_wiki_core/prompts/project_context.py`
- `packages/graph-wiki-core/src/graph_wiki_core/prompts/scanner.py`
- `packages/graph-wiki-core/src/graph_wiki_core/prompts/synthesizer.py`

### packages/graph-wiki-core/src/graph_wiki_core/prompts/_fragments/
- `packages/graph-wiki-core/src/graph_wiki_core/prompts/_fragments/__init__.py`
- `packages/graph-wiki-core/src/graph_wiki_core/prompts/_fragments/architecture_overview.py`
- `packages/graph-wiki-core/src/graph_wiki_core/prompts/_fragments/citation_rules.py`
- `packages/graph-wiki-core/src/graph_wiki_core/prompts/_fragments/claude_md_disambiguation.py`
- `packages/graph-wiki-core/src/graph_wiki_core/prompts/_fragments/frontmatter_rules.py`
- `packages/graph-wiki-core/src/graph_wiki_core/prompts/_fragments/iron_rules.py`
- `packages/graph-wiki-core/src/graph_wiki_core/prompts/_fragments/log_format.py`
- `packages/graph-wiki-core/src/graph_wiki_core/prompts/_fragments/page_categories.py`
- `packages/graph-wiki-core/src/graph_wiki_core/prompts/_fragments/style_rules.py`

### packages/graph-wiki-core/src/graph_wiki_core/prompts/sources/
- `packages/graph-wiki-core/src/graph_wiki_core/prompts/sources/code_reader.md`
- `packages/graph-wiki-core/src/graph_wiki_core/prompts/sources/synthesizer.md`

### packages/graph-wiki-core/tests/
- `packages/graph-wiki-core/tests/conftest.py`
- `packages/graph-wiki-core/tests/test_command_overrides.py`
- `packages/graph-wiki-core/tests/test_ingest_trace_unit.py`
- `packages/graph-wiki-core/tests/test_migrate_vault.py`
- `packages/graph-wiki-core/tests/test_package_boundary.py`
- `packages/graph-wiki-core/tests/test_propose_domains.py`
- `packages/graph-wiki-core/tests/test_query_graph_tools.py`
- `packages/graph-wiki-core/tests/test_query_trace_unit.py`

### packages/graph-wiki-core/tests/commands/
- `packages/graph-wiki-core/tests/commands/__init__.py`
- `packages/graph-wiki-core/tests/commands/test_lint_parity.py`
- `packages/graph-wiki-core/tests/commands/test_scan_parity.py`

### packages/graph-wiki-core/tests/prompts/
- `packages/graph-wiki-core/tests/prompts/__init__.py`
- `packages/graph-wiki-core/tests/prompts/test_project_context.py`
- `packages/graph-wiki-core/tests/prompts/test_prompt_snapshots.py`
- `packages/graph-wiki-core/tests/prompts/test_provenance.py`
- `packages/graph-wiki-core/tests/prompts/test_token_budget.py`

### packages/graph-wiki-core/tests/prompts/__snapshots__/
- `packages/graph-wiki-core/tests/prompts/__snapshots__/test_project_context.ambr`
- `packages/graph-wiki-core/tests/prompts/__snapshots__/test_prompt_snapshots.ambr`

### packages/graph-wiki-core/tests/unit/
- `packages/graph-wiki-core/tests/unit/__init__.py`
- `packages/graph-wiki-core/tests/unit/test_commands_bootstrap.py`
- `packages/graph-wiki-core/tests/unit/test_commands_graph.py`
- `packages/graph-wiki-core/tests/unit/test_commands_ingest.py`
- `packages/graph-wiki-core/tests/unit/test_commands_lint.py`
- `packages/graph-wiki-core/tests/unit/test_commands_log.py`
- `packages/graph-wiki-core/tests/unit/test_commands_scan.py`
- `packages/graph-wiki-core/tests/unit/test_config.py`
- `packages/graph-wiki-core/tests/unit/test_entity_narrative_prompt.py`
- `packages/graph-wiki-core/tests/unit/test_graph_tools.py`
- `packages/graph-wiki-core/tests/unit/test_query_code_fallback.py`
- `packages/graph-wiki-core/tests/unit/test_query_graph_tools_wiring.py`
- `packages/graph-wiki-core/tests/unit/test_query_result.py`
- `packages/graph-wiki-core/tests/unit/test_query_search.py`
- `packages/graph-wiki-core/tests/unit/test_query_summary_schema_version.py`
- `packages/graph-wiki-core/tests/unit/test_scan_graph_integration.py`
- `packages/graph-wiki-core/tests/unit/test_scan_result_shape.py`
- `packages/graph-wiki-core/tests/unit/test_seeded_graph_workspace_smoke.py`
- `packages/graph-wiki-core/tests/unit/test_uri_slug.py`

### packages/graph-wiki-core/tests/unit/__snapshots__/
- `packages/graph-wiki-core/tests/unit/__snapshots__/test_commands_graph.ambr`

### packages/graph-wiki-mcp/
- `packages/graph-wiki-mcp/pyproject.toml`

### packages/graph-wiki-mcp/src/graph_wiki_mcp/
- `packages/graph-wiki-mcp/src/graph_wiki_mcp/__init__.py`
- `packages/graph-wiki-mcp/src/graph_wiki_mcp/server.py`

### packages/graph-wiki-mcp/tests/integration/
- `packages/graph-wiki-mcp/tests/integration/test_mcp_cancel.py`
- `packages/graph-wiki-mcp/tests/integration/test_mcp_e2e.py`
- `packages/graph-wiki-mcp/tests/integration/test_mcp_stdio.py`

### packages/graph-wiki-mcp/tests/unit/
- `packages/graph-wiki-mcp/tests/unit/test_commands_log.py`
- `packages/graph-wiki-mcp/tests/unit/test_mcp_graph_tools.py`
- `packages/graph-wiki-mcp/tests/unit/test_mcp_new_tools.py`
- `packages/graph-wiki-mcp/tests/unit/test_mcp_package_boundary.py`
- `packages/graph-wiki-mcp/tests/unit/test_mcp_query_schema.py`
- `packages/graph-wiki-mcp/tests/unit/test_mcp_schema_forbid_extra.py`
- `packages/graph-wiki-mcp/tests/unit/test_stdout_guard.py`
- `packages/graph-wiki-mcp/tests/unit/test_wiki_scan_input.py`

### packages/model-adapter/
- `packages/model-adapter/models.toml`
- `packages/model-adapter/pyproject.toml`

### packages/model-adapter/src/model_adapter/
- `packages/model-adapter/src/model_adapter/__init__.py`
- `packages/model-adapter/src/model_adapter/exceptions.py`
- `packages/model-adapter/src/model_adapter/loader.py`
- `packages/model-adapter/src/model_adapter/models.toml`

### packages/model-adapter/tests/
- `packages/model-adapter/tests/conftest.py`
- `packages/model-adapter/tests/test_loader.py`
- `packages/model-adapter/tests/test_narrator_role.py`

### packages/source-parser/
- `packages/source-parser/CLAUDE.md`
- `packages/source-parser/conftest.py`
- `packages/source-parser/README.md`

### packages/source-parser/fixtures/javascript/
- `packages/source-parser/fixtures/javascript/basic_function.expected.json`
- `packages/source-parser/fixtures/javascript/basic_function.graph.expected.json`
- `packages/source-parser/fixtures/javascript/basic_function.js`
- `packages/source-parser/fixtures/javascript/cjs_module.cjs`
- `packages/source-parser/fixtures/javascript/cjs_module.expected.json`
- `packages/source-parser/fixtures/javascript/class_with_methods.expected.json`
- `packages/source-parser/fixtures/javascript/class_with_methods.js`
- `packages/source-parser/fixtures/javascript/default_export.expected.json`
- `packages/source-parser/fixtures/javascript/default_export.js`
- `packages/source-parser/fixtures/javascript/esm_module.expected.json`
- `packages/source-parser/fixtures/javascript/esm_module.graph.expected.json`
- `packages/source-parser/fixtures/javascript/esm_module.mjs`
- `packages/source-parser/fixtures/javascript/import_variants.expected.json`
- `packages/source-parser/fixtures/javascript/import_variants.js`
- `packages/source-parser/fixtures/javascript/re_export_source.expected.json`
- `packages/source-parser/fixtures/javascript/re_export_source.js`
- `packages/source-parser/fixtures/javascript/re_export.expected.json`
- `packages/source-parser/fixtures/javascript/re_export.js`

### packages/source-parser/fixtures/python/
- *(22 files: 12 .json, 10 .py)*

### packages/source-parser/fixtures/typescript/
- *(29 files: 17 .json, 12 .ts)*
