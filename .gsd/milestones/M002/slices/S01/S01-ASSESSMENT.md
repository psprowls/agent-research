---
sliceId: S01
uatType: browser-executable
verdict: PASS
date: 2026-05-31T16:19:50Z
---

# UAT Result — S01

## Checks

| Check | Mode | Result | Notes |
|-------|------|--------|-------|
| Run `uv sync` from the workspace root. | runtime | PASS | `gsd_exec` 7171d2dc ran `uv sync`; exit code 0. stderr: `Resolved 134 packages in 4ms`; `Checked 132 packages in 26ms`. |
| Smoke-test import `graph_wiki_core.commands.query`. | runtime | PASS | `uv run --package graph-wiki-core python -c "import graph_wiki_core.commands.query"`; exit code 0. |
| Smoke-test import `graph_wiki_core.commands.scan`. | runtime | PASS | `uv run --package graph-wiki-core python -c "import graph_wiki_core.commands.scan"`; exit code 0. |
| Smoke-test import `graph_wiki_core.prompts.scanner`. | runtime | PASS | `uv run --package graph-wiki-core python -c "import graph_wiki_core.prompts.scanner"`; exit code 0. |
| Run the package-local core test suite: `uv run --package graph-wiki-core python -m pytest packages/graph-wiki-core/tests`. | runtime | PASS | `gsd_exec` 7171d2dc collected 263 tests; result `256 passed, 7 skipped in 11.29s`; exit code 0. Output included the intentional provenance/legacy scanner skips described by the UAT. |
| Run selected eval-harness consumer tests: `uv run --package eval-harness python -m pytest packages/eval-harness/tests/test_structural.py packages/eval-harness/tests/test_sweep.py`. | runtime | PASS | `gsd_exec` 7171d2dc collected 17 tests; result `17 passed in 21.61s`; exit code 0. |
| Run the temporary presentation help smoke: `uv run --package graph-wiki-agent graph-wiki-agent --help`. | runtime | PASS | `gsd_exec` 7171d2dc rendered Typer help for `graph-wiki-agent: AWS Bedrock-powered wiki maintenance CLI` and listed commands including `version`, `trace`, `query`, `log`, `bootstrap`, `scan`, `migrate-vault`, `lint`, `ingest`, and `graph`; exit code 0. |
| Verify `packages/graph-wiki-core` package metadata and namespace boundary. | artifact | PASS | `gsd_exec` f92321b5 confirmed `package_name_is_graph_wiki_core=True`, `no_project_scripts=True`, `new_namespace_exists=True`, and `old_namespace_absent_in_core=True`. |
| Verify no bytecode/cache artifacts remain under the core source/test tree. | artifact | PASS | Runtime imports/tests generated transient `__pycache__` files. They were removed as UAT cleanup, then `gsd_exec` f92321b5 confirmed `no_bytecode_or_cache_artifacts=True` and `cache_artifact_count=0`. |

## Overall Verdict

PASS — All automatable S01 UAT checks passed, including workspace sync, core import smoke tests, package-local tests, selected eval-harness consumer tests, temporary presentation help rendering, and package-boundary artifact checks.

## Notes

- Primary command evidence: `.gsd/exec/7171d2dc-ad5c-420a-8a04-ec71d8ab1f14.stdout` and `.gsd/exec/7171d2dc-ad5c-420a-8a04-ec71d8ab1f14.stderr`.
- Boundary artifact evidence and cleanup: `.gsd/exec/f92321b5-77ad-42d7-807c-2b68bc1f91d6.stdout`.
- The detected UAT mode was `browser-executable`, but the UAT specification itself defines package/runtime command checks and no browser target URL or UI flow; therefore evidence was gathered via runtime and artifact checks rather than browser screenshots.
- No human-only follow-up is required for this UAT.
