---
estimated_steps: 9
estimated_files: 13
skills_used: []
---

# T04: Enforce the MCP package boundary and close targeted verification

Why: After relocation, the repo needs an executable boundary check so stale `graph_wiki_agent.mcp` imports or old script ownership fail fast instead of hiding an incomplete split. This also gives S05 a clean package-local verification target.

Do:
1. Add `packages/graph-wiki-mcp/tests/unit/test_mcp_package_boundary.py` or equivalent package-local tests that assert the `graph-wiki-mcp` distribution owns the `graph-wiki-mcp` console script and that the entrypoint targets `graph_wiki_mcp.server:main`.
2. Add boundary assertions that files under `packages/graph-wiki-mcp` do not contain active imports, mocks, or subprocess package invocations for `graph_wiki_agent.mcp` or `uv run --package graph-wiki-agent graph-wiki-mcp`.
3. Remove the old inactive `agents/graph-wiki-agent/src/graph_wiki_agent/mcp` source once all tests target `graph_wiki_mcp`; do not add compatibility shims.
4. Remove or relocate the old MCP tests from `agents/graph-wiki-agent/tests` so pytest does not keep an old namespace test owner. If non-MCP tests remain for S05, leave them untouched.
5. Run the full targeted S03 verification chain: `uv sync`, all `packages/graph-wiki-mcp/tests`, and any package-boundary test added in this task.

Done when: all package-local MCP tests pass, the new boundary test proves there are no active stale MCP references inside the MCP package, and the temporary agent package no longer exposes or tests the MCP server. Expected executor skills: `python-testing-patterns`, `uv-package-manager`.

Requirement Impact (Q4): Covers R004 and supports R001/R006/R007. Decisions D002 and D003 are enforced: separate presentation package, no old import shim. Failure Modes (Q5): If deleting the old source breaks unrelated temporary agent checks, confirm the failure is not an MCP ownership dependency before restoring anything; prefer updating the dependent import to `graph_wiki_mcp` over recreating a shim. Negative Tests (Q7): Boundary tests should fail on old import strings, old patch strings, or old subprocess invocation strings inside `packages/graph-wiki-mcp`. Integration Closure: Leaves docs/shim rewiring and final deletion of `agents/` to S04/S05, but closes MCP runtime ownership for S03.

## Inputs

- `packages/graph-wiki-mcp/pyproject.toml`
- `packages/graph-wiki-mcp/src/graph_wiki_mcp/server.py`
- `packages/graph-wiki-mcp/tests/unit/test_stdout_guard.py`
- `packages/graph-wiki-mcp/tests/unit/test_mcp_query_schema.py`
- `packages/graph-wiki-mcp/tests/unit/test_mcp_schema_forbid_extra.py`
- `packages/graph-wiki-mcp/tests/unit/test_mcp_new_tools.py`
- `packages/graph-wiki-mcp/tests/unit/test_mcp_graph_tools.py`
- `packages/graph-wiki-mcp/tests/unit/test_wiki_scan_input.py`
- `packages/graph-wiki-mcp/tests/unit/test_commands_log.py`
- `packages/graph-wiki-mcp/tests/integration/test_mcp_stdio.py`
- `packages/graph-wiki-mcp/tests/integration/test_mcp_e2e.py`
- `packages/graph-wiki-mcp/tests/integration/test_mcp_cancel.py`
- `agents/graph-wiki-agent/src/graph_wiki_agent/mcp/server.py`

## Expected Output

- `packages/graph-wiki-mcp/tests/unit/test_mcp_package_boundary.py`

## Verification

uv sync && uv run --package graph-wiki-mcp python -m pytest packages/graph-wiki-mcp/tests

## Observability Impact

No new runtime diagnostics; boundary tests provide future-agent inspection for package ownership and stale-reference regressions.
