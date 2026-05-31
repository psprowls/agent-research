---
estimated_steps: 16
estimated_files: 4
skills_used: []
---

# T01: Cut over to a package-only uv workspace

---
estimated_steps: 7
estimated_files: 4
skills_used:
  - uv-package-manager
  - python-testing-patterns
  - verify-before-complete
---

Why: S05's highest-risk blocker is that the root workspace still includes `agents/*`, the old `agents/graph-wiki-agent` tree still exists, and `uv.lock` still contains the obsolete editable package. The final package split is not real until root package resolution works without that member.

Do:
1. Add a repo-level package-split boundary test at `tests/test_package_split_workspace.py` that reads only active non-gitignored project files and asserts: root workspace members do not include `agents/*`; `agents/` does not exist; `uv.lock` does not mention `name = "graph-wiki-agent"` or `agents/graph-wiki-agent`; `graph_wiki_agent` is not importable; package metadata/entrypoints remain owned by `graph-wiki-cli` (`gw`) and `graph-wiki-mcp` (`graph-wiki-mcp`). Keep allowed plugin identity strings out of this test unless they are active package/workspace membership.
2. Edit root `pyproject.toml` so `[tool.uv.workspace] members` is package-only, expected `['packages/*']`.
3. Delete the obsolete `agents/` directory tree. Do not copy anything from it back into packages; package trees are authoritative.
4. Run `uv sync` to refresh workspace resolution and `uv.lock`.
5. Confirm the new boundary test passes after the lock refresh.

Done when: The root workspace resolves with `uv sync`, the old agent package and directory are absent, and `tests/test_package_split_workspace.py` proves the final workspace/package boundary.

## Inputs

- `pyproject.toml`
- `uv.lock`
- `agents/graph-wiki-agent`
- `packages/graph-wiki-cli/pyproject.toml`
- `packages/graph-wiki-mcp/pyproject.toml`

## Expected Output

- `pyproject.toml`
- `uv.lock`
- `tests/test_package_split_workspace.py`

## Verification

uv sync && uv run python -m pytest tests/test_package_split_workspace.py -q

## Observability Impact

Adds an executable repo-level diagnostic for future agents: failures name whether the workspace metadata, stale directory, lockfile, import namespace, or entrypoint ownership regressed.
