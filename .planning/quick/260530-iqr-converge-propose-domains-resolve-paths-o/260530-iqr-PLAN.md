---
phase: quick-260530-iqr
plan: 01
type: execute
wave: 1
depends_on: []
files_modified:
  - agents/graph-wiki-agent/src/graph_wiki_agent/commands/_paths.py
  - agents/graph-wiki-agent/src/graph_wiki_agent/commands/graph.py
  - agents/graph-wiki-agent/src/graph_wiki_agent/commands/propose_domains.py
  - agents/graph-wiki-agent/tests/test_propose_domains.py
autonomous: true
requirements: [QUICK-IQR-01]

must_haves:
  truths:
    - "Both `graph.py` and `propose_domains.py` resolve (repo_root, workspace_root) through ONE shared helper, so they can never diverge again — the DRY point of this todo."
    - "On the repo≠workspace layout (workspace is its own git repo, source repo is the cwd), `propose-domains` resolves the SOURCE repo as repo_root — NOT the wiki vault — so `domains.proposed.yaml` lands in the source repo, not silently inside the vault."
    - "`graph.py`'s exact current behavior is preserved: the shared helper returns `(repo if repo is not None else Path.cwd(), wiki.parent)`, and all 10 hxy graph repo-resolution tests stay green."
    - "A `repo-directory:` pin in `<workspace>/.graph-wiki.yaml` is honored for `propose-domains` too (inherited from the shared resolver delegating to `resolve_wiki_and_repo`)."
  artifacts:
    - path: "agents/graph-wiki-agent/src/graph_wiki_agent/commands/_paths.py"
      provides: "Single shared _resolve_paths(workspace_arg) -> (repo_root, workspace_root), lifted verbatim from the fixed graph.py:61-78"
      contains: "resolve_wiki_and_repo"
    - path: "agents/graph-wiki-agent/src/graph_wiki_agent/commands/graph.py"
      provides: "graph.py imports _resolve_paths from _paths (local copy removed)"
      contains: "from graph_wiki_agent.commands._paths import _resolve_paths"
    - path: "agents/graph-wiki-agent/src/graph_wiki_agent/commands/propose_domains.py"
      provides: "propose_domains.py imports _resolve_paths from _paths; orphaned resolve_config import removed"
      contains: "from graph_wiki_agent.commands._paths import _resolve_paths"
    - path: "agents/graph-wiki-agent/tests/test_propose_domains.py"
      provides: "Test proving propose-domains resolves SOURCE repo (not vault) on repo≠workspace layout"
  key_links:
    - from: "propose_domains.py:propose_domains_cmd"
      to: "graph_wiki_agent.commands._paths._resolve_paths"
      via: "import + call"
      pattern: "from graph_wiki_agent.commands._paths import _resolve_paths"
    - from: "_paths._resolve_paths"
      to: "wiki_io._workspace.resolve_wiki_and_repo"
      via: "direct call"
      pattern: "resolve_wiki_and_repo"
---

<objective>
Eliminate the duplicate `_resolve_paths` that quick task 260530-hxy left behind. `propose_domains.py:564-570` has its OWN copy still on the buggy `resolve_config` path — it walks up from the WORKSPACE dir for `.git`, so on the repo≠workspace layout `repo_root` binds to the wiki vault instead of the source repo. The failure is quiet: `propose_domains_cmd` writes `<repo_root>/domains.proposed.yaml` (:605-606), so the proposed-domains file lands silently inside the vault.

Fix per the todo's DRY mandate: do NOT copy the hxy fix into propose_domains. EXTRACT the corrected `graph.py:61-78` `_resolve_paths` into ONE shared helper (`commands/_paths.py`) that BOTH files import. Single source of truth → future divergence is structurally impossible.

Purpose: `propose-domains` must resolve the same source repo `scan`/`graph build` resolve, so its output lands in the right place. Converging on one helper removes the duplicate permanently.
Output: 1 new shared module + 2 surgical import swaps + 1 new test proving the propose-domains repo≠workspace case.
</objective>

<execution_context>
@$HOME/.claude/get-shit-done/workflows/execute-plan.md
@$HOME/.claude/get-shit-done/templates/summary.md
</execution_context>

<context>
@.planning/STATE.md
@.planning/todos/pending/2026-05-30-converge-propose-domains-resolve-paths-onto-shared-resolver.md

# The already-fixed source of truth (graph.py:61-78) and the still-broken duplicate
@agents/graph-wiki-agent/src/graph_wiki_agent/commands/graph.py
@agents/graph-wiki-agent/src/graph_wiki_agent/commands/propose_domains.py

# The shared upstream resolver the helper wraps (READ-ONLY — do not modify)
@packages/wiki-io/src/wiki_io/_workspace.py

<interfaces>
<!-- Key contracts the executor needs — do not re-explore the codebase. -->

The CORRECT (already-fixed) _resolve_paths to extract verbatim — graph.py:61-78:
- signature: `def _resolve_paths(workspace_arg: str) -> tuple[Path, Path]`
- body: if workspace_arg truthy → `wiki, repo = resolve_wiki_and_repo(Path(workspace_arg).resolve())`; else `wiki, repo = resolve_wiki_and_repo()`
- returns `(repo if repo is not None else Path.cwd(), wiki.parent)`
- imports needed by the helper: `from pathlib import Path`, `from wiki_io._workspace import resolve_wiki_and_repo`

The STILL-BROKEN duplicate to delete — propose_domains.py:564-570:
- same name/signature, but uses `resolve_config(...)` and returns `(cfg.repo_root, cfg.workspace)` — repo_root wrong on repo≠workspace.
- `resolve_config` is imported at propose_domains.py:61 (`from workspace_io.config import resolve as resolve_config`) and used ONLY inside this `_resolve_paths` (grep-confirmed: usages at :567 and :569 only) → import becomes orphaned, remove it.
- `from workspace_io.paths import graph_dir` (propose_domains.py:62) stays — used at :612.

resolve_wiki_and_repo contract (wiki_io._workspace, DO NOT MODIFY):
- `resolve_wiki_and_repo(workspace_path=None, repo_path=None) -> tuple[Path, Path | None]`
- returns `(wiki_dir, repo_root)` where `wiki_dir == workspace/wiki`, so `wiki.parent` == workspace root.
- already honors a `repo-directory:` pin and resolves repo from `Path.cwd()` in the explicit-workspace branch (hxy fix).

Test fixture helpers to mirror (from agents/graph-wiki-agent/tests/unit/test_commands_graph.py:481-526):
- `_make_fake_repo(path)`: mkdir + `(path/".git").mkdir()`; returns path.
- manifest seed: write `<ws>/.graph-wiki.yaml` = `"version: 2\ninitialized_at: 2026-05-30\nplugins: []\n"` (+ optional `repo-directory: <path>` line).
- pattern: `monkeypatch.delenv("GRAPH_WIKI_WORKSPACE", raising=False)`, build source_repo + chdir into it, build separate workspace repo, create `<ws>/wiki` dir, call `_resolve_paths(str(workspace))`, assert repo_root == source_repo.resolve() and workspace_root == workspace.resolve().
</interfaces>
</context>

<tasks>

<task type="auto">
  <name>Task 1: Extract shared _resolve_paths into commands/_paths.py and swap both call sites</name>
  <files>agents/graph-wiki-agent/src/graph_wiki_agent/commands/_paths.py, agents/graph-wiki-agent/src/graph_wiki_agent/commands/graph.py, agents/graph-wiki-agent/src/graph_wiki_agent/commands/propose_domains.py</files>
  <action>
    Create NEW module `agents/graph-wiki-agent/src/graph_wiki_agent/commands/_paths.py`. Move the EXACT body of the already-fixed `graph.py` `_resolve_paths` (graph.py:61-78) into it verbatim — same signature `_resolve_paths(workspace_arg: str) -> tuple[Path, Path]`, same docstring (it explains the hxy fix and is now the single source of truth), same return `(repo if repo is not None else Path.cwd(), wiki.parent)`. The new module needs `from __future__ import annotations`, `from pathlib import Path`, and `from wiki_io._workspace import resolve_wiki_and_repo`. Do NOT re-implement or "improve" the logic — it is behavior-preserving for graph.py per the constraint (its 10 hxy tests must stay green).

    In `graph.py`: DELETE the local `_resolve_paths` def (currently :61-78) and ADD `from graph_wiki_agent.commands._paths import _resolve_paths` to the imports. Keep `from wiki_io._workspace import resolve_wiki_and_repo` (graph.py:45) ONLY if anything else in graph.py still uses `resolve_wiki_and_repo` directly — grep first; if `_resolve_paths` was its sole consumer, remove that now-orphaned import too (per CLAUDE.md: clean up orphans YOUR change creates). The three Typer call sites (build/describe/query) and the MCP server import `_resolve_paths` from `graph` module — verify they still resolve: if any code does `from ...commands.graph import _resolve_paths` or `graph_module._resolve_paths`, re-export by keeping the name importable from graph (the `from ..._paths import _resolve_paths` line makes `graph._resolve_paths` valid, so existing references keep working). Grep for `_resolve_paths` across the package to confirm no caller breaks.

    In `propose_domains.py`: DELETE the duplicate `_resolve_paths` def (:564-570), ADD `from graph_wiki_agent.commands._paths import _resolve_paths` to imports, and REMOVE the now-orphaned `from workspace_io.config import resolve as resolve_config` (:61) — grep-confirmed it is used ONLY inside the deleted function. Leave `from workspace_io.paths import graph_dir` (:62) and everything else untouched. Do NOT change `propose_domains_cmd`'s body or the `domains.proposed.yaml` write logic — only the resolution source changes.
  </action>
  <verify>
    <automated>cd /Users/pat/Personal/agent-research && grep -rn "_resolve_paths\b" agents/graph-wiki-agent/src | grep -v "_paths.py" | grep -v "import _resolve_paths" ; uv run --package graph-wiki-agent pytest agents/graph-wiki-agent/tests/unit/test_commands_graph.py -x -q</automated>
  </verify>
  <done>`commands/_paths.py` holds the single `_resolve_paths`; both graph.py and propose_domains.py import it; orphaned `resolve_config` import removed from propose_domains.py; no dangling local `_resolve_paths` definitions remain; all 10 hxy graph repo-resolution tests still pass; no caller of `_resolve_paths` breaks.</done>
</task>

<task type="auto" tdd="true">
  <name>Task 2: Test propose-domains resolves SOURCE repo (not vault) on repo≠workspace layout</name>
  <files>agents/graph-wiki-agent/tests/test_propose_domains.py</files>
  <behavior>
    - On the repo≠workspace layout (cwd is the source repo with `.git`; workspace is a SEPARATE git repo with a seeded `.graph-wiki.yaml`, no `repo-directory:` pin), `_resolve_paths(str(workspace))` (imported into propose_domains) returns repo_root == the SOURCE repo (cwd) — NOT the workspace. This is the quiet bug: previously repo_root == workspace → `domains.proposed.yaml` written into the vault.
    - The returned workspace_root == the workspace dir (so `graph_dir(workspace_root)/code.db` still resolves correctly).
    - With a `repo-directory: <pinned source>` line in the workspace manifest, `_resolve_paths` returns repo_root == the pinned path (inherited from the shared resolver) — proves propose-domains now honors the pin too.
  </behavior>
  <action>
    Add tests to the EXISTING `agents/graph-wiki-agent/tests/test_propose_domains.py`. Import the shared `_resolve_paths` via propose_domains to prove the swap took effect: `from graph_wiki_agent.commands.propose_domains import _resolve_paths` (this MUST be the shared one after Task 1; importing it here is the regression guard against the duplicate creeping back).

    Add a local `_make_fake_repo(path)` helper mirroring test_commands_graph.py:481-485 (mkdir + create `.git` subdir) — keep it module-local; do not import from the unit test file. Write `test_propose_domains_resolves_source_repo_not_vault`: `monkeypatch.delenv("GRAPH_WIKI_WORKSPACE", raising=False)`; build `source_repo = tmp_path/"source-code"`, `_make_fake_repo(source_repo)`, `monkeypatch.chdir(source_repo)`; build `workspace = tmp_path/"wiki-vault"`, `_make_fake_repo(workspace)`, seed `<workspace>/.graph-wiki.yaml` with `"version: 2\ninitialized_at: 2026-05-30\nplugins: []\n"`, `(workspace/"wiki").mkdir()`. Call `repo_root, workspace_root = _resolve_paths(str(workspace))`. Assert `repo_root == source_repo.resolve()` with a message naming the bug (todo 260530-iqr: previously the vault was returned → domains.proposed.yaml written into the vault), and `workspace_root == workspace.resolve()`.

    Add `test_propose_domains_resolves_honors_repo_directory_pin`: same setup but seed the manifest with an extra `repo-directory: {source_repo}\n` line (mirror test_commands_graph.py:540-543), and assert `repo_root == source_repo.resolve()`. This proves the pin path flows through the shared helper for propose-domains.

    Surgical: do not touch existing tests in this file; only append the helper + two tests.
  </action>
  <verify>
    <automated>cd /Users/pat/Personal/agent-research && uv run --package graph-wiki-agent pytest agents/graph-wiki-agent/tests/test_propose_domains.py -x -q</automated>
  </verify>
  <done>New tests prove propose-domains resolves the source repo (cwd) — not the vault — on the repo≠workspace layout, and honors a repo-directory: pin; the tests import `_resolve_paths` from propose_domains (guarding against re-divergence); existing propose_domains tests still pass.</done>
</task>

</tasks>

<verification>
Full regression across the affected agent test surface (the resolution swap touches both graph and propose-domains command paths):

```bash
cd /Users/pat/Personal/agent-research && \
  uv run --package graph-wiki-agent pytest \
    agents/graph-wiki-agent/tests/unit/test_commands_graph.py \
    agents/graph-wiki-agent/tests/test_propose_domains.py \
    agents/graph-wiki-agent/tests/integration/test_propose_domains_e2e.py \
    agents/graph-wiki-agent/tests/integration/test_propose_domains_isolation.py \
    -q
```

Confirm the duplicate is gone:
```bash
cd /Users/pat/Personal/agent-research && grep -rn "def _resolve_paths" agents/graph-wiki-agent/src
# Expect exactly ONE hit: commands/_paths.py
```
</verification>

<success_criteria>
- A single `_resolve_paths` definition exists (`commands/_paths.py`); both graph.py and propose_domains.py import it — divergence is structurally impossible.
- `propose-domains` resolves the same SOURCE repo as `scan`/`graph build` on the repo≠workspace layout, proven by a test that previously would have returned the vault as repo_root.
- The orphaned `resolve_config` import is removed from propose_domains.py.
- `graph.py` behavior is unchanged — all 10 hxy graph repo-resolution tests pass.
- `repo-directory:` pin is honored for propose-domains.
- No regressions in graph command or propose_domains tests.
</success_criteria>

<output>
Create `.planning/quick/260530-iqr-converge-propose-domains-resolve-paths-o/260530-iqr-SUMMARY.md` when done.
</output>
