---
phase: quick-260530-hxy
plan: 01
type: execute
wave: 1
depends_on: []
files_modified:
  - packages/wiki-io/src/wiki_io/_workspace.py
  - agents/graph-wiki-agent/src/graph_wiki_agent/commands/graph.py
  - packages/wiki-io/tests/test_workspace_resolution.py
  - agents/graph-wiki-agent/tests/unit/test_commands_graph.py
autonomous: true
requirements: [QUICK-HXY-01]

must_haves:
  truths:
    - "On the repo≠workspace layout (workspace is its own git repo, source repo elsewhere), `graph build` resolves the SOURCE repo from cwd — the same repo `scan` resolves — not the workspace."
    - "`graph build`, `graph describe`, and `graph query` all resolve (repo_root, workspace_root) through the same single helper `scan` uses (`resolve_wiki_and_repo`), so the two entry points cannot diverge again."
    - "A `repo-directory:` pin in `<workspace>/.graph-wiki.yaml` is honored consistently when an explicit `--workspace`/`workspace_path` is supplied — for BOTH `scan` and `graph build`."
    - "`_resolve_paths` still returns the workspace ROOT (where `.graph/code.db` lives), not the wiki subdirectory, so `run_build`/`graph_dir` keep working."
  artifacts:
    - path: "packages/wiki-io/src/wiki_io/_workspace.py"
      provides: "resolve_wiki_and_repo honoring repo-directory: pin in the explicit-workspace branch"
      contains: "_repo_directory_override"
    - path: "agents/graph-wiki-agent/src/graph_wiki_agent/commands/graph.py"
      provides: "_resolve_paths routed through resolve_wiki_and_repo (cwd-based repo resolution)"
      contains: "resolve_wiki_and_repo"
    - path: "packages/wiki-io/tests/test_workspace_resolution.py"
      provides: "Test proving explicit-workspace branch honors repo-directory: pin"
    - path: "agents/graph-wiki-agent/tests/unit/test_commands_graph.py"
      provides: "Test reproducing the repo≠workspace failure and proving graph build resolves repo from cwd"
  key_links:
    - from: "graph.py:_resolve_paths"
      to: "wiki_io._workspace.resolve_wiki_and_repo"
      via: "direct call"
      pattern: "resolve_wiki_and_repo"
    - from: "wiki_io._workspace.resolve_wiki_and_repo (workspace_path branch)"
      to: "workspace_io.config._repo_directory_override"
      via: "direct call"
      pattern: "_repo_directory_override"
---

<objective>
Converge `graph build`'s source-repo resolution onto the path `scan` already uses, fixing the repo≠workspace layout where `graph build --full` resolves `repo_root = the workspace` (its own commit-less git repo) and dies with `fatal: ambiguous argument 'HEAD'` — or, with commits, graphs the WRONG tree (the wiki vault instead of the source code).

Root cause (verified): `graph build` → `_resolve_paths()` → `workspace_io.config.resolve(Path(workspace_arg).resolve())`. That passes the WORKSPACE dir as `cwd`, so `_find_repo_root` walks up from the workspace and binds to the workspace's own `.git`. `scan` → `resolve_wiki_and_repo(workspace_path)` → `_find_repo_root(Path.cwd())`, resolving the repo from the actual current working directory, which is why `scan` works.

Fix: route `_resolve_paths` through the same `resolve_wiki_and_repo` helper `scan` uses (single shared resolution path → cannot diverge again), and make that helper honor the `repo-directory:` pin in its explicit-workspace branch so the documented workaround works consistently for BOTH commands.

Purpose: `graph build --full` must graph the source repo, not the wiki vault. Aligning on one resolver removes the divergence permanently.
Output: 2 surgical source edits + 2 tests (one per package) that reproduce the failure and prove the fix.
</objective>

<execution_context>
@$HOME/.claude/get-shit-done/workflows/execute-plan.md
@$HOME/.claude/get-shit-done/templates/summary.md
</execution_context>

<context>
@.planning/STATE.md
@.planning/todos/pending/2026-05-30-fix-graph-build-repo-resolution-to-match-scan.md

# The working path (scan) and the broken path (graph build)
@packages/wiki-io/src/wiki_io/_workspace.py
@agents/graph-wiki-agent/src/graph_wiki_agent/commands/graph.py

# The override helper + config resolution semantics
@packages/workspace-io/src/workspace_io/config.py
@packages/workspace-io/src/workspace_io/paths.py

<interfaces>
<!-- Key contracts the executor needs — do not re-explore the codebase. -->

From packages/wiki-io/src/wiki_io/_workspace.py:
```python
# CURRENT — explicit-workspace branch does NOT honor the repo-directory: pin
def resolve_wiki_and_repo(
    workspace_path: Path | None = None,
    repo_path: Path | None = None,
) -> tuple[Path, Path | None]:
    # returns (wiki_dir, repo_root); wiki_dir == workspace/wiki
    if workspace_path is not None:
        return _ws_paths.wiki_dir(workspace_path), repo_path or _find_repo_root(Path.cwd())
    cfg = _ws_config.resolve()
    return _ws_paths.wiki_dir(cfg.workspace), repo_path or cfg.repo_root
```

From packages/workspace-io/src/workspace_io/config.py:
```python
# _repo_directory_override(workspace, repo_root_default) -> Path
#   Reads `repo-directory:` from <workspace>/.graph-wiki.yaml (+ .local overlay).
#   Returns repo_root_default unchanged when the key is absent/blank.
#   ~ expands; relative resolves against `workspace`. Already imported in
#   _workspace.py is `_find_repo_root` from this module.
def _repo_directory_override(workspace: Path, repo_root_default: Path) -> Path: ...
def _find_repo_root(start: Path) -> Path | None: ...
```

From packages/workspace-io/src/workspace_io/paths.py:
```python
def wiki_dir(workspace: Path) -> Path:  # workspace / "wiki"
def graph_dir(workspace: Path) -> Path: # workspace / ".graph"   <- where code.db lives
```

From agents/graph-wiki-agent/src/graph_wiki_agent/commands/graph.py:
```python
# CURRENT — the broken resolver. Three Typer call sites (build:435, describe:385,
# query:604) and the MCP server (server.py:517/568/610) consume it.
def _resolve_paths(workspace_arg: str) -> tuple[Path, Path]:
    """Resolve (repo_root, workspace) from --workspace arg or GRAPH_WIKI_WORKSPACE env."""
    if workspace_arg:
        cfg = resolve_config(Path(workspace_arg).resolve(), require_manifest=False)
    else:
        cfg = resolve_config(None, require_manifest=False)
    return cfg.repo_root, cfg.workspace   # <- repo_root wrong on repo≠workspace
```

From agents/graph-wiki-agent/src/graph_wiki_agent/commands/scan.py (the convention to match):
```python
# wiki, resolved_repo = resolve_wiki_and_repo(workspace_path)
# _workspace_root = wiki.parent   # workspace root passed to run_build
```
</interfaces>
</context>

<tasks>

<task type="auto" tdd="true">
  <name>Task 1: Honor repo-directory: pin in resolve_wiki_and_repo's explicit-workspace branch</name>
  <files>packages/wiki-io/src/wiki_io/_workspace.py, packages/wiki-io/tests/test_workspace_resolution.py</files>
  <behavior>
    - With an explicit `workspace_path` whose `.graph-wiki.yaml` declares `repo-directory: <abs source repo>`, and NO `repo_path` arg: `resolve_wiki_and_repo(workspace_path)` returns repo_root == the pinned source repo (NOT the workspace, even if the workspace is itself a git repo).
    - With an explicit `workspace_path` and NO `repo-directory:` pin: repo_root == `_find_repo_root(Path.cwd())` (unchanged behavior — repo from cwd).
    - An explicit `repo_path` arg still overrides everything (existing contract preserved — pin must NOT clobber an explicit repo_path).
    - `repo-directory:` with a `~` or relative value expands per `_repo_directory_override`'s existing rules (relative resolves against the workspace).
  </behavior>
  <action>
    In `resolve_wiki_and_repo`, modify ONLY the `workspace_path is not None` branch (the explicit-workspace short-circuit). Today it returns `repo_path or _find_repo_root(Path.cwd())`, which ignores any `repo-directory:` pin. Change it so: when `repo_path` is supplied, keep returning `repo_path` (explicit override wins — do NOT apply the pin over it). Otherwise compute the cwd-discovered default (`_find_repo_root(Path.cwd())`), then pass it through `workspace_io.config._repo_directory_override(workspace_path, <default>)` so a `repo-directory:` pin in `<workspace>/.graph-wiki.yaml` overrides it. Import `_repo_directory_override` from `workspace_io.config` (the module already imports `_find_repo_root` from there — add the new name to that same import). Guard against `_find_repo_root` returning None before passing to the override: if the cwd default is None and there is a pin, the pin should still apply; if both are None, return None (preserve the `Path | None` return type). Do NOT touch the `else:` (cfg-based) branch — `config.resolve()` already applies `_repo_directory_override` internally, so that path is correct. Surgical change only; per CLAUDE.md Karpathy guidelines do not refactor adjacent code or the docstring beyond a one-line note that the explicit-workspace branch now honors the pin.

    Add tests to a NEW file `packages/wiki-io/tests/test_workspace_resolution.py`. Mirror the manifest-seeding pattern from `packages/workspace-io/tests/test_config.py` (`_seed_manifest_with` writes `version: 2\ninitialized_at: ...\nplugins: []\n` plus a `repo-directory: <path>` line). Cover the four behaviors above. For the cwd-based default cases, `monkeypatch.setattr("wiki_io._workspace._find_repo_root", lambda _: <fake repo>)` (or chdir into a constructed repo) so the test does not depend on the host's real git tree. Set `monkeypatch.delenv("GRAPH_WIKI_WORKSPACE", raising=False)` for hygiene.
  </action>
  <verify>
    <automated>cd /Users/pat/Personal/agent-research && uv run --package wiki-io pytest packages/wiki-io/tests/test_workspace_resolution.py -x -q</automated>
  </verify>
  <done>resolve_wiki_and_repo's explicit-workspace branch honors a repo-directory: pin (and still respects an explicit repo_path override); new test file passes; no other workspace-io/wiki-io tests regress.</done>
</task>

<task type="auto" tdd="true">
  <name>Task 2: Route graph.py _resolve_paths through resolve_wiki_and_repo (cwd-based repo)</name>
  <files>agents/graph-wiki-agent/src/graph_wiki_agent/commands/graph.py, agents/graph-wiki-agent/tests/unit/test_commands_graph.py</files>
  <behavior>
    - On the repo≠workspace layout (workspace is its own git repo with no source commits; source repo lives elsewhere and is the cwd), `_resolve_paths(workspace_arg)` returns repo_root == the SOURCE repo (resolved from cwd via resolve_wiki_and_repo), NOT the workspace. This is the exact failure from the todo: previously repo_root == workspace → `git rev-parse HEAD` dies.
    - `_resolve_paths` still returns the workspace ROOT as the second tuple element (so `graph_dir(workspace_root)/code.db` and `run_build(repo, workspace_root, ...)` keep working). Derive it as `wiki.parent` since `resolve_wiki_and_repo` returns `wiki == workspace/wiki`.
    - When `workspace_arg` is empty, resolution falls back to `resolve_wiki_and_repo()` (env var / cwd walk-up) — same as scan with no explicit workspace.
    - A `repo-directory:` pin in the workspace manifest is honored (delegated to Task 1's helper change).
  </behavior>
  <action>
    Rewrite `_resolve_paths` in `commands/graph.py` to delegate to `wiki_io._workspace.resolve_wiki_and_repo` instead of `workspace_io.config.resolve`. New body: if `workspace_arg` is truthy, call `wiki, repo = resolve_wiki_and_repo(Path(workspace_arg).resolve())`; else `wiki, repo = resolve_wiki_and_repo()`. Then return `(repo, wiki.parent)` — `wiki.parent` is the workspace root because `resolve_wiki_and_repo` returns `wiki_dir(workspace) == workspace/wiki` (confirmed in workspace_io/paths.py and scan.py's `wiki.parent` convention). Preserve the return type `tuple[Path, Path]`: if `repo` is None, fall back to `Path.cwd()` for the repo element (mirror scan.py:455-461 which uses `Path.cwd()` when resolved_repo is None) so callers never receive None where a Path is expected. Add `from wiki_io._workspace import resolve_wiki_and_repo` to the imports. Remove the now-unused `from workspace_io.config import resolve as resolve_config` import ONLY if nothing else in the file uses it (grep first — it appears solely in `_resolve_paths`; `workspace_io.paths.graph_dir` is a separate import and stays). Keep `_resolve_paths`'s signature, name, and docstring intent intact — the three Typer call sites (build/describe/query) and the MCP server import it unchanged. Do NOT touch `propose_domains.py`'s separate `_resolve_paths` copy — out of scope for this task. Surgical change only.

    Add a test to the EXISTING `agents/graph-wiki-agent/tests/unit/test_commands_graph.py` that reproduces the repo≠workspace failure and proves the fix at the `_resolve_paths` level (fast, no real git build). Construct: a SOURCE repo dir with `.git` (the cwd), and a SEPARATE workspace dir that is ALSO its own git repo (`<ws>/.git`) with a seeded `.graph-wiki.yaml` (and a `<ws>/wiki` dir is not required since `_resolve_paths` only takes `.parent`). `monkeypatch.chdir(source_repo)` and `monkeypatch.delenv("GRAPH_WIKI_WORKSPACE", raising=False)`. Call `graph_module._resolve_paths(str(workspace))` and assert: (a) returned repo_root == source_repo.resolve() (the cwd repo — proves it is NOT the workspace, which is the bug); (b) returned workspace_root == workspace.resolve(). Add a second assertion variant proving the `repo-directory:` pin path: seed the workspace manifest with `repo-directory: <other source>` and assert repo_root == that pinned path. Reference the failure in a comment (todo 260530-hxy: previously returned workspace as repo_root → `git rev-parse HEAD` fatal).
  </action>
  <verify>
    <automated>cd /Users/pat/Personal/agent-research && uv run --package graph-wiki-agent pytest agents/graph-wiki-agent/tests/unit/test_commands_graph.py -x -q</automated>
  </verify>
  <done>`_resolve_paths` resolves the source repo from cwd (matching scan) and still returns the workspace root; new test reproduces the old failure and passes against the fix; existing test_commands_graph.py tests still pass.</done>
</task>

</tasks>

<verification>
Full regression across the three affected packages (resolution change touches wiki-io, workspace-io semantics, and the agent):

```bash
cd /Users/pat/Personal/agent-research && \
  uv run --package wiki-io pytest packages/wiki-io/tests -q && \
  uv run --package workspace-io pytest packages/workspace-io/tests/test_config.py -q && \
  uv run --package graph-wiki-agent pytest agents/graph-wiki-agent/tests/unit/test_commands_graph.py agents/graph-wiki-agent/tests/unit/test_scan_graph_integration.py -q
```

Manual confirmation of intent (optional, no real Bedrock call needed): `graph build` and `scan` now both source repo_root from cwd → on a repo≠workspace layout `graph build --full` no longer hits `fatal: ambiguous argument 'HEAD'`.
</verification>

<success_criteria>
- `graph build` resolves the SAME source repo as `scan` on the repo≠workspace layout (from cwd), proven by a test that previously would have returned the workspace as repo_root.
- Both commands route through the single `resolve_wiki_and_repo` helper — divergence is structurally impossible.
- `repo-directory:` pin in `<workspace>/.graph-wiki.yaml` is honored for both commands when an explicit workspace is supplied.
- `_resolve_paths` still returns the workspace root (not the wiki dir) — `run_build`/`graph_dir` unaffected.
- No regressions in wiki-io, workspace-io config, or graph command unit tests.
</success_criteria>

<output>
Create `.planning/quick/260530-hxy-fix-graph-build-repo-resolution-to-match/260530-hxy-SUMMARY.md` when done.
</output>
