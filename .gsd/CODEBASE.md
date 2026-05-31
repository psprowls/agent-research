# Codebase Map

Generated: 2026-05-31T16:03:16Z | Files: 500 | Described: 0/500
<!-- gsd:codebase-meta {"generatedAt":"2026-05-31T16:03:16Z","fingerprint":"ef6a2549f6afcfe212edfda589766608a2d083e2","fileCount":500,"truncated":true} -->
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
- `packages/source-parser/pyproject.toml`
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
- *(43 files: 25 .json, 18 .ts)*

### packages/source-parser/src/source_parser/
- `packages/source-parser/src/source_parser/__init__.py`
- `packages/source-parser/src/source_parser/errors.py`
- `packages/source-parser/src/source_parser/grammars.py`
- `packages/source-parser/src/source_parser/parse.py`
- `packages/source-parser/src/source_parser/tree.py`

### packages/source-parser/src/source_parser/parsers/
- `packages/source-parser/src/source_parser/parsers/__init__.py`
- `packages/source-parser/src/source_parser/parsers/_base.py`
- `packages/source-parser/src/source_parser/parsers/_config.py`
- `packages/source-parser/src/source_parser/parsers/_generic.py`
- `packages/source-parser/src/source_parser/parsers/javascript.py`
- `packages/source-parser/src/source_parser/parsers/python.py`
- `packages/source-parser/src/source_parser/parsers/typescript.py`

### packages/source-parser/src/source_parser/projections/
- `packages/source-parser/src/source_parser/projections/__init__.py`
- `packages/source-parser/src/source_parser/projections/graph.py`

### packages/source-parser/tests/
- `packages/source-parser/tests/_fixture_loader.py`
- `packages/source-parser/tests/test_generic_walker.py`
- `packages/source-parser/tests/test_grammars.py`
- `packages/source-parser/tests/test_parse_dispatch.py`
- `packages/source-parser/tests/test_parse_errors.py`
- `packages/source-parser/tests/test_parser_javascript.py`
- `packages/source-parser/tests/test_parser_python.py`
- `packages/source-parser/tests/test_parser_typescript.py`
- `packages/source-parser/tests/test_projection_graph.py`
- `packages/source-parser/tests/test_smoke.py`
- `packages/source-parser/tests/test_tree_model.py`
- `packages/source-parser/tests/test_unsupported_language.py`

### packages/subagent-runtime/
- `packages/subagent-runtime/pyproject.toml`

### packages/subagent-runtime/src/subagent_runtime/
- `packages/subagent-runtime/src/subagent_runtime/__init__.py`
- `packages/subagent-runtime/src/subagent_runtime/pool.py`
- `packages/subagent-runtime/src/subagent_runtime/trace_io.py`

### packages/subagent-runtime/tests/
- `packages/subagent-runtime/tests/conftest.py`
- `packages/subagent-runtime/tests/test_pool.py`
- `packages/subagent-runtime/tests/test_trace_io.py`

### packages/subagent-runtime/tests/integration/
- `packages/subagent-runtime/tests/integration/__init__.py`
- `packages/subagent-runtime/tests/integration/test_pool_bedrock.py`

### packages/wiki-io/
- `packages/wiki-io/pyproject.toml`

### packages/wiki-io/src/wiki_io/
- `packages/wiki-io/src/wiki_io/__init__.py`
- `packages/wiki-io/src/wiki_io/_workspace.py`
- `packages/wiki-io/src/wiki_io/append_log.py`
- `packages/wiki-io/src/wiki_io/detect_containers.py`
- `packages/wiki-io/src/wiki_io/entity_writer.py`
- `packages/wiki-io/src/wiki_io/git_state.py`
- `packages/wiki-io/src/wiki_io/graph_analyzer.py`
- `packages/wiki-io/src/wiki_io/index_generator.py`
- `packages/wiki-io/src/wiki_io/ingest_source.py`
- `packages/wiki-io/src/wiki_io/ingest_work_item.py`
- `packages/wiki-io/src/wiki_io/init_vault.py`
- `packages/wiki-io/src/wiki_io/layout_io.py`
- `packages/wiki-io/src/wiki_io/link_rewriter.py`
- `packages/wiki-io/src/wiki_io/lint_wiki.py`
- `packages/wiki-io/src/wiki_io/scan_monorepo.py`
- `packages/wiki-io/src/wiki_io/update_index.py`
- `packages/wiki-io/src/wiki_io/update_tokens.py`
- `packages/wiki-io/src/wiki_io/wiki_search.py`

### packages/wiki-io/src/wiki_io/assets/
- `packages/wiki-io/src/wiki_io/assets/AGENTS.md.template`
- `packages/wiki-io/src/wiki_io/assets/CLAUDE.md.template`
- `packages/wiki-io/src/wiki_io/assets/cursorrules.template`
- `packages/wiki-io/src/wiki_io/assets/index.md.template`
- `packages/wiki-io/src/wiki_io/assets/log.md.template`

### packages/wiki-io/src/wiki_io/assets/page-templates/
- `packages/wiki-io/src/wiki_io/assets/page-templates/adr.md`
- `packages/wiki-io/src/wiki_io/assets/page-templates/architecture.md`
- `packages/wiki-io/src/wiki_io/assets/page-templates/concept-pattern.md`
- `packages/wiki-io/src/wiki_io/assets/page-templates/concept.md`
- `packages/wiki-io/src/wiki_io/assets/page-templates/dependency.md`
- `packages/wiki-io/src/wiki_io/assets/page-templates/entity-app.md`
- `packages/wiki-io/src/wiki_io/assets/page-templates/entity-dependency.md`
- `packages/wiki-io/src/wiki_io/assets/page-templates/entity-domain.md`
- `packages/wiki-io/src/wiki_io/assets/page-templates/entity-package.md`
- `packages/wiki-io/src/wiki_io/assets/page-templates/entity-plugin.md`
- `packages/wiki-io/src/wiki_io/assets/page-templates/entity-repository.md`
- `packages/wiki-io/src/wiki_io/assets/page-templates/entity-test-suite.md`
- `packages/wiki-io/src/wiki_io/assets/page-templates/index.md`
- `packages/wiki-io/src/wiki_io/assets/page-templates/source.md`
- `packages/wiki-io/src/wiki_io/assets/page-templates/work.md`

### packages/wiki-io/src/wiki_io/lint/
- `packages/wiki-io/src/wiki_io/lint/__init__.py`
- `packages/wiki-io/src/wiki_io/lint/common.py`
- `packages/wiki-io/src/wiki_io/lint/container.py`
- `packages/wiki-io/src/wiki_io/lint/dependency.py`
- `packages/wiki-io/src/wiki_io/lint/domain.py`
- `packages/wiki-io/src/wiki_io/lint/file_map.py`
- `packages/wiki-io/src/wiki_io/lint/package_sync.py`
- `packages/wiki-io/src/wiki_io/lint/source_sync.py`
- `packages/wiki-io/src/wiki_io/lint/workflow_hints.py`

### packages/wiki-io/tests/
- `packages/wiki-io/tests/conftest.py`

### packages/wiki-io/tests/fixtures/edge-case-vault/
- `packages/wiki-io/tests/fixtures/edge-case-vault/CLAUDE.md`
- `packages/wiki-io/tests/fixtures/edge-case-vault/index.md`

### packages/wiki-io/tests/fixtures/edge-case-vault/concepts/
- `packages/wiki-io/tests/fixtures/edge-case-vault/concepts/broken-wikilinks.md`
- `packages/wiki-io/tests/fixtures/edge-case-vault/concepts/index.md`
- `packages/wiki-io/tests/fixtures/edge-case-vault/concepts/missing-title.md`
- `packages/wiki-io/tests/fixtures/edge-case-vault/concepts/truncated-frontmatter.md`
