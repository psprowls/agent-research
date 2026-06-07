# Configurable State Gate Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make the git "state gate" (which guards `last_updated_commit` narrative-provenance stamping) configurable per-workspace via a `state_gate:` block in `<workspace>/.graph-wiki.yaml`, so trunk (now `develop`) can stamp again, and remove the dead `graph_wiki_core/config.py` module.

**Architecture:** `workspace_io.manifest.read()` normalizes and validates an optional top-level `state_gate` block (mirroring the existing `plugin:` block); a thin `read_state_gate()` accessor exposes it. `wiki_io.git_state.is_clean_main` generalizes to `is_clean_on_branches(repo, branches)`. `wiki_io.scan_monorepo.compute_state_gate(repo, workspace=None)` reads config and applies gate semantics; callers thread the workspace they already hold. Absent config preserves today's behavior (`enabled: true`, `branches: [main]`).

**Tech Stack:** Python 3.11, `uv` workspace monorepo, pytest (per-package), PyYAML, git via `subprocess`.

---

## Prerequisites (read before starting)

- **Worktree venv.** This plan runs in the `configurable-state-gate` worktree. A fresh worktree's `.pth` points at the *parent* repo's `src`, so bare `python` imports the wrong source. Run `uv sync` once in the worktree root, and run every test command exactly as written (`uv run --package <pkg> pytest ...`) — `uv run` selects the worktree venv.

  Run once at the start:
  ```bash
  uv sync
  ```

- **Layer rules.** `workspace_io` owns manifest schema knowledge (no gate *semantics*). `wiki_io` owns gate semantics and depends on `workspace_io` (already a declared dependency — see `packages/wiki-io/pyproject.toml`). Keep it that way: do not import `wiki_io` from `workspace_io`.

- **No migrations.** Per repo convention (pre-v2.0), the change is additive: an absent `state_gate` block defaults to today's behavior. Do not write migration code.

## File Structure

| File | Responsibility | Change |
|------|----------------|--------|
| `packages/workspace-io/src/workspace_io/manifest.py` | Manifest schema read/validate/normalize | Add `state_gate` normalization in `read()`; add `read_state_gate()` accessor |
| `packages/workspace-io/src/workspace_io/__init__.py` | Package exports | Export `read_state_gate` |
| `packages/workspace-io/tests/test_manifest.py` | Manifest schema tests | Add `state_gate` normalization + accessor tests |
| `packages/wiki-io/src/wiki_io/git_state.py` | Git state helpers | `is_clean_main` → `is_clean_on_branches(repo, branches)` |
| `packages/wiki-io/src/wiki_io/scan_monorepo.py` | `compute_state_gate` gate wrapper | Add `workspace=None` param; read config; apply enabled/branches semantics |
| `packages/wiki-io/tests/test_git_state.py` | git_state tests | Add `is_clean_on_branches` tests |
| `packages/wiki-io/tests/test_state_gate.py` | compute_state_gate tests | **New file** |
| `packages/graph-wiki-core/src/graph_wiki_core/commands/scan.py` | scan caller | Thread workspace into `compute_state_gate` |
| `packages/wiki-io/src/wiki_io/ingest_source.py` | ingest callers | Thread workspace into `compute_state_gate` (2 call sites) |
| `packages/graph-wiki-core/src/graph_wiki_core/config.py` | Dead TOML config module | **Delete** |
| `packages/graph-wiki-core/tests/unit/test_config.py` | Test for dead module | **Delete** |
| `packages/workspace-io/README.md` | Manifest schema reference | Document `state_gate:` block |
| `plugins/graph-wiki/skills/graph-wiki/references/scan-workflow.md` | Scan workflow doc | Note the gate is configurable |

## Resolved spec ambiguities (decided during planning)

1. **Scalar `branches` coercion.** §1 of the spec (detailed design — authoritative) says the `branches` *key* accepts a scalar string coerced to a one-element list. §Schema line 54's `branch: main` is read as "a scalar value under the `branches` key" (i.e. `branches: main` → `["main"]`). A separate singular `branch:` key is **not** introduced — it would land in the unknown-keys set and raise. Coercion is applied to the `branches` value only.

2. **Bootstrap seeding (spec §3) is documentation-only.** Investigation of the live manifest (`/Users/pat/Personal/workspaces/agent-research/combined/.graph-wiki.yaml`) shows the `plugin:` block is *hand-edited*, appended after the `manifest.write()` payload. `init.py` writes via `manifest.write()`, which reconstructs a fixed payload (`version`, `initialized_at`, `topic`, `plugins`) and emits **no** `plugin:` block. There is therefore no init template to seed a commented `state_gate:` block into, and the spec's own non-goal confirms these blocks are hand-edited ("`manifest.write()` losiness for hand-edited blocks (`plugin:`, `state_gate:`) is a pre-existing wart"). Discoverability is delivered via the README schema reference (Task 8). No code seeding is added.

---

## Task 1: `state_gate` normalization in `manifest.read()`

**Files:**
- Modify: `packages/workspace-io/src/workspace_io/manifest.py`
- Test: `packages/workspace-io/tests/test_manifest.py`

- [ ] **Step 1: Write the failing tests**

Add to `packages/workspace-io/tests/test_manifest.py` (append at end of file):

```python
def test_state_gate_default_when_missing(tmp_path):
    """Block absent → defaults to {enabled: True, branches: ['main']}."""
    mpath = tmp_path / ".graph-wiki.yaml"
    mpath.write_text(
        "version: 2\ninitialized_at: 2026-05-08\nplugins: []\n",
        encoding="utf-8",
    )
    assert read(mpath)["state_gate"] == {"enabled": True, "branches": ["main"]}


def test_state_gate_explicit_values(tmp_path):
    """Explicit enabled + branches are returned verbatim."""
    mpath = tmp_path / ".graph-wiki.yaml"
    mpath.write_text(
        "version: 2\ninitialized_at: 2026-05-08\nplugins: []\n"
        "state_gate:\n  enabled: false\n  branches:\n    - main\n    - develop\n",
        encoding="utf-8",
    )
    assert read(mpath)["state_gate"] == {"enabled": False, "branches": ["main", "develop"]}


def test_state_gate_scalar_branches_coerced(tmp_path):
    """A scalar branches value is coerced to a one-element list."""
    mpath = tmp_path / ".graph-wiki.yaml"
    mpath.write_text(
        "version: 2\ninitialized_at: 2026-05-08\nplugins: []\nstate_gate:\n  branches: develop\n",
        encoding="utf-8",
    )
    assert read(mpath)["state_gate"] == {"enabled": True, "branches": ["develop"]}


def test_state_gate_partial_block_uses_defaults(tmp_path):
    """A present block with only enabled keeps the default branches."""
    mpath = tmp_path / ".graph-wiki.yaml"
    mpath.write_text(
        "version: 2\ninitialized_at: 2026-05-08\nplugins: []\nstate_gate:\n  enabled: false\n",
        encoding="utf-8",
    )
    assert read(mpath)["state_gate"] == {"enabled": False, "branches": ["main"]}


def test_state_gate_raises_when_not_mapping(tmp_path):
    mpath = tmp_path / ".graph-wiki.yaml"
    mpath.write_text(
        "version: 2\ninitialized_at: 2026-05-08\nplugins: []\nstate_gate: main\n",
        encoding="utf-8",
    )
    with pytest.raises(RuntimeError, match="must be a mapping"):
        read(mpath)


def test_state_gate_raises_on_unknown_key(tmp_path):
    mpath = tmp_path / ".graph-wiki.yaml"
    mpath.write_text(
        "version: 2\ninitialized_at: 2026-05-08\nplugins: []\nstate_gate:\n  foo: bar\n",
        encoding="utf-8",
    )
    with pytest.raises(RuntimeError, match="unknown keys"):
        read(mpath)


def test_state_gate_raises_on_non_bool_enabled(tmp_path):
    mpath = tmp_path / ".graph-wiki.yaml"
    mpath.write_text(
        "version: 2\ninitialized_at: 2026-05-08\nplugins: []\nstate_gate:\n  enabled: yes_please\n",
        encoding="utf-8",
    )
    with pytest.raises(RuntimeError, match="must be a bool"):
        read(mpath)


def test_state_gate_raises_on_empty_branches(tmp_path):
    mpath = tmp_path / ".graph-wiki.yaml"
    mpath.write_text(
        "version: 2\ninitialized_at: 2026-05-08\nplugins: []\nstate_gate:\n  branches: []\n",
        encoding="utf-8",
    )
    with pytest.raises(RuntimeError, match="non-empty list"):
        read(mpath)


def test_state_gate_raises_on_non_string_branch_item(tmp_path):
    mpath = tmp_path / ".graph-wiki.yaml"
    mpath.write_text(
        "version: 2\ninitialized_at: 2026-05-08\nplugins: []\nstate_gate:\n  branches:\n    - main\n    - 7\n",
        encoding="utf-8",
    )
    with pytest.raises(RuntimeError, match="strings"):
        read(mpath)
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `uv run --package workspace-io pytest tests/test_manifest.py -k state_gate -v`
Expected: FAIL — `KeyError: 'state_gate'` on the passing-path tests and no `RuntimeError` raised on the validation tests (the block is currently ignored by `read()`).

- [ ] **Step 3: Add the normalization constant and logic**

In `packages/workspace-io/src/workspace_io/manifest.py`, add a constant next to `_KNOWN_PLUGIN_KEYS` (after line 10):

```python
_KNOWN_STATE_GATE_KEYS = {"enabled", "branches"}
```

Then, inside `read()`, immediately **before** the final `return raw` (currently line 55), insert:

```python
    # Validate and normalise the optional [state_gate] block. Always returns
    # {"enabled": bool, "branches": [str, ...]}; defaults to the historical
    # behavior (gate on a clean `main`) when the block is absent.
    state_gate = raw.get("state_gate")
    if state_gate is None:
        raw["state_gate"] = {"enabled": True, "branches": ["main"]}
    else:
        if not isinstance(state_gate, dict):
            raise RuntimeError(f"{path}: 'state_gate' must be a mapping, got {type(state_gate).__name__}")
        unknown = set(state_gate.keys()) - _KNOWN_STATE_GATE_KEYS
        if unknown:
            raise RuntimeError(f"{path}: unknown keys in state_gate block: {sorted(unknown)}")
        enabled = state_gate.get("enabled", True)
        if not isinstance(enabled, bool):
            raise RuntimeError(f"{path}: state_gate.enabled must be a bool, got {type(enabled).__name__}")
        branches = state_gate.get("branches", ["main"])
        if isinstance(branches, str):
            branches = [branches]
        if not isinstance(branches, list) or not branches:
            raise RuntimeError(f"{path}: state_gate.branches must be a non-empty list of branch names")
        if not all(isinstance(b, str) for b in branches):
            raise RuntimeError(f"{path}: state_gate.branches must contain only strings")
        raw["state_gate"] = {"enabled": enabled, "branches": branches}
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `uv run --package workspace-io pytest tests/test_manifest.py -k state_gate -v`
Expected: PASS (9 tests).

- [ ] **Step 5: Run the full manifest suite to confirm no regression**

Run: `uv run --package workspace-io pytest tests/test_manifest.py -v`
Expected: PASS (all existing + new tests).

- [ ] **Step 6: Commit**

```bash
git add packages/workspace-io/src/workspace_io/manifest.py packages/workspace-io/tests/test_manifest.py
git commit -m "feat(workspace-io): normalize optional state_gate manifest block"
```

---

## Task 2: `read_state_gate()` accessor + package export

**Files:**
- Modify: `packages/workspace-io/src/workspace_io/manifest.py`
- Modify: `packages/workspace-io/src/workspace_io/__init__.py`
- Test: `packages/workspace-io/tests/test_manifest.py`

- [ ] **Step 1: Write the failing tests**

Append to `packages/workspace-io/tests/test_manifest.py`. Note the import on line 4 must gain `read_state_gate`:

Change line 4 from:
```python
from workspace_io.manifest import read, read_roles, write
```
to:
```python
from workspace_io.manifest import read, read_roles, read_state_gate, write
```

Then append:

```python
def test_read_state_gate_returns_tuple(tmp_path):
    """read_state_gate returns (enabled, branches) from the normalized block."""
    mpath = tmp_path / ".graph-wiki.yaml"
    mpath.write_text(
        "version: 2\ninitialized_at: 2026-05-08\nplugins: []\n"
        "state_gate:\n  enabled: false\n  branches:\n    - develop\n",
        encoding="utf-8",
    )
    assert read_state_gate(mpath) == (False, ["develop"])


def test_read_state_gate_defaults_when_block_absent(tmp_path):
    """Block absent on an existing manifest → (True, ['main'])."""
    mpath = tmp_path / ".graph-wiki.yaml"
    mpath.write_text(
        "version: 2\ninitialized_at: 2026-05-08\nplugins: []\n",
        encoding="utf-8",
    )
    assert read_state_gate(mpath) == (True, ["main"])


def test_read_state_gate_defaults_when_manifest_missing(tmp_path):
    """Missing manifest → (True, ['main']) (matches read() empty-dict contract)."""
    assert read_state_gate(tmp_path / ".graph-wiki.yaml") == (True, ["main"])
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `uv run --package workspace-io pytest tests/test_manifest.py -k read_state_gate -v`
Expected: FAIL — `ImportError: cannot import name 'read_state_gate'`.

- [ ] **Step 3: Implement `read_state_gate()`**

In `packages/workspace-io/src/workspace_io/manifest.py`, append after `read_roles()` (end of file):

```python
def read_state_gate(manifest_path: Path) -> tuple[bool, list[str]]:
    """Return the (enabled, branches) state-gate config for the workspace.

    Reads the manifest and returns the normalized `state_gate` block as a typed
    tuple. Defaults to (True, ["main"]) — today's behavior — when the manifest
    is missing or carries no `state_gate` block. Mirrors `read_roles()`: a thin
    read-only accessor that does not mutate disk.
    """
    block = read(manifest_path).get("state_gate") or {"enabled": True, "branches": ["main"]}
    return block["enabled"], block["branches"]
```

- [ ] **Step 4: Export it from the package**

In `packages/workspace-io/src/workspace_io/__init__.py`, change line 5 from:
```python
from workspace_io.manifest import read_roles
```
to:
```python
from workspace_io.manifest import read_roles, read_state_gate
```

And add `"read_state_gate"` to `__all__` (insert in alphabetical position, after `"read_roles"`):
```python
__all__ = [
    "GraphWikiConfig",
    "PendingUpdate",
    "init",
    "pending_updates",
    "read_roles",
    "read_state_gate",
    "resolve",
    "warn_if_stale",
]
```

- [ ] **Step 5: Run the tests to verify they pass**

Run: `uv run --package workspace-io pytest tests/test_manifest.py -k read_state_gate -v`
Expected: PASS (3 tests).

- [ ] **Step 6: Commit**

```bash
git add packages/workspace-io/src/workspace_io/manifest.py packages/workspace-io/src/workspace_io/__init__.py packages/workspace-io/tests/test_manifest.py
git commit -m "feat(workspace-io): add read_state_gate accessor and export"
```

---

## Task 3: Generalize `is_clean_main` → `is_clean_on_branches`

**Files:**
- Modify: `packages/wiki-io/src/wiki_io/git_state.py:52-69`
- Test: `packages/wiki-io/tests/test_git_state.py`

- [ ] **Step 1: Write the failing tests**

Append to `packages/wiki-io/tests/test_git_state.py`. First extend the import on line 8 from:
```python
from wiki_io.git_state import head_commit, short_commit
```
to:
```python
from wiki_io.git_state import head_commit, is_clean_on_branches, short_commit
```

Then append a branch-aware helper and the tests:

```python
def _init_repo_on_branch(repo: Path, branch: str) -> None:
    """Init a one-commit git repo with HEAD on `branch` (clean tree)."""
    repo.mkdir(parents=True, exist_ok=True)
    (repo / "f.txt").write_text("hi\n", encoding="utf-8")
    _git(repo, "init")
    _git(repo, "add", "-A")
    _git(repo, "-c", "user.email=t@t", "-c", "user.name=t", "commit", "-m", "init")
    _git(repo, "branch", "-M", branch)


def test_is_clean_on_branches_allowed_branch_clean(tmp_path):
    repo = tmp_path / "repo"
    _init_repo_on_branch(repo, "main")
    assert is_clean_on_branches(repo, ["main", "develop"]) == (True, "")


def test_is_clean_on_branches_matches_non_first_entry(tmp_path):
    repo = tmp_path / "repo"
    _init_repo_on_branch(repo, "develop")
    assert is_clean_on_branches(repo, ["main", "develop"]) == (True, "")


def test_is_clean_on_branches_branch_not_listed(tmp_path):
    repo = tmp_path / "repo"
    _init_repo_on_branch(repo, "feature-x")
    ok, reason = is_clean_on_branches(repo, ["main"])
    assert ok is False
    assert "not in" in reason
    assert "feature-x" in reason


def test_is_clean_on_branches_dirty_tree(tmp_path):
    repo = tmp_path / "repo"
    _init_repo_on_branch(repo, "main")
    (repo / "dirty.txt").write_text("uncommitted\n", encoding="utf-8")
    assert is_clean_on_branches(repo, ["main"]) == (False, "working tree is dirty")


def test_is_clean_on_branches_non_git_dir(tmp_path):
    non_repo = tmp_path / "plain"
    non_repo.mkdir()
    ok, reason = is_clean_on_branches(non_repo, ["main"])
    assert ok is False
    assert reason == "not a git repo"
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `uv run --package wiki-io pytest tests/test_git_state.py -k is_clean_on_branches -v`
Expected: FAIL — `ImportError: cannot import name 'is_clean_on_branches'`.

- [ ] **Step 3: Replace `is_clean_main` with `is_clean_on_branches`**

In `packages/wiki-io/src/wiki_io/git_state.py`, replace the entire `is_clean_main` function (lines 52-69) with:

```python
def is_clean_on_branches(repo: Path, branches: list[str]) -> tuple[bool, str]:
    """Return (True, "") iff working tree is clean AND HEAD is on a listed branch.

    Otherwise (False, "<reason>"). Used by /graph-wiki:scan and /graph-wiki:ingest
    (via compute_state_gate) to decide whether to write new sync-state to vault
    frontmatter. `branches` is the configured allow-list from .graph-wiki.yaml.
    """
    branch_out = _run(repo, "rev-parse", "--abbrev-ref", "HEAD")
    if branch_out is None or branch_out[0] != 0:
        return False, "not a git repo"
    branch = branch_out[1].strip()
    if branch not in branches:
        return False, f"branch is {branch!r}, not in {branches}"
    status_out = _run(repo, "status", "--porcelain")
    if status_out is None or status_out[0] != 0:
        return False, "git status failed"
    if status_out[1].strip():
        return False, "working tree is dirty"
    return True, ""
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `uv run --package wiki-io pytest tests/test_git_state.py -v`
Expected: PASS (existing `short_commit` tests + 5 new `is_clean_on_branches` tests).

- [ ] **Step 5: Commit**

```bash
git add packages/wiki-io/src/wiki_io/git_state.py packages/wiki-io/tests/test_git_state.py
git commit -m "feat(wiki-io): generalize is_clean_main to is_clean_on_branches"
```

---

## Task 4: `compute_state_gate(repo, workspace=None)` reads config + applies semantics

**Files:**
- Modify: `packages/wiki-io/src/wiki_io/scan_monorepo.py:744-760`
- Test: `packages/wiki-io/tests/test_state_gate.py` (new)

- [ ] **Step 1: Write the failing tests**

Create `packages/wiki-io/tests/test_state_gate.py`:

```python
"""Tests for wiki_io.scan_monorepo.compute_state_gate — config-driven gate."""

from __future__ import annotations

import subprocess
from pathlib import Path

from wiki_io.scan_monorepo import compute_state_gate


def _git(repo: Path, *args: str) -> None:
    subprocess.run(["git", *args], cwd=repo, check=True, capture_output=True)


def _init_repo_on_branch(repo: Path, branch: str) -> None:
    repo.mkdir(parents=True, exist_ok=True)
    (repo / "f.txt").write_text("hi\n", encoding="utf-8")
    _git(repo, "init")
    _git(repo, "add", "-A")
    _git(repo, "-c", "user.email=t@t", "-c", "user.name=t", "commit", "-m", "init")
    _git(repo, "branch", "-M", branch)


def _write_manifest(workspace: Path, body: str) -> None:
    (workspace / ".graph-wiki.yaml").write_text(
        "version: 2\ninitialized_at: 2026-06-06\nplugins: []\n" + body,
        encoding="utf-8",
    )


def test_disabled_gate_allows_regardless_of_branch(tmp_path):
    repo = tmp_path / "repo"
    _init_repo_on_branch(repo, "feature-x")
    workspace = tmp_path / "ws"
    workspace.mkdir()
    _write_manifest(workspace, "state_gate:\n  enabled: false\n")
    gate = compute_state_gate(repo, workspace=workspace)
    assert gate["allowed"] is True
    assert gate["reason"] == "state gate disabled in .graph-wiki.yaml"
    assert gate["head_commit"] is not None


def test_disabled_gate_allows_when_dirty(tmp_path):
    repo = tmp_path / "repo"
    _init_repo_on_branch(repo, "main")
    (repo / "dirty.txt").write_text("x\n", encoding="utf-8")
    workspace = tmp_path / "ws"
    workspace.mkdir()
    _write_manifest(workspace, "state_gate:\n  enabled: false\n")
    assert compute_state_gate(repo, workspace=workspace)["allowed"] is True


def test_enabled_gate_honors_configured_branches(tmp_path):
    repo = tmp_path / "repo"
    _init_repo_on_branch(repo, "develop")
    workspace = tmp_path / "ws"
    workspace.mkdir()
    _write_manifest(workspace, "state_gate:\n  enabled: true\n  branches:\n    - develop\n")
    assert compute_state_gate(repo, workspace=workspace)["allowed"] is True


def test_enabled_gate_blocks_branch_not_in_list(tmp_path):
    repo = tmp_path / "repo"
    _init_repo_on_branch(repo, "main")
    workspace = tmp_path / "ws"
    workspace.mkdir()
    _write_manifest(workspace, "state_gate:\n  enabled: true\n  branches:\n    - develop\n")
    gate = compute_state_gate(repo, workspace=workspace)
    assert gate["allowed"] is False
    assert "not in" in gate["reason"]


def test_workspace_none_defaults_to_main(tmp_path):
    """No workspace → (enabled, ['main']) default (backward compat)."""
    repo_main = tmp_path / "repo_main"
    _init_repo_on_branch(repo_main, "main")
    assert compute_state_gate(repo_main)["allowed"] is True

    repo_dev = tmp_path / "repo_dev"
    _init_repo_on_branch(repo_dev, "develop")
    gate = compute_state_gate(repo_dev)
    assert gate["allowed"] is False
    assert "not in" in gate["reason"]
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `uv run --package wiki-io pytest tests/test_state_gate.py -v`
Expected: FAIL — `compute_state_gate()` does not accept a `workspace` keyword (`TypeError`), and it still imports the now-removed `is_clean_main`.

- [ ] **Step 3: Rewrite `compute_state_gate`**

In `packages/wiki-io/src/wiki_io/scan_monorepo.py`, replace the `compute_state_gate` function (lines 744-760) with:

```python
def compute_state_gate(repo: Path, workspace: Path | None = None) -> dict:
    """Return JSON-serializable gate info: whether state writes are allowed.

    {"allowed": bool, "reason": str, "head_commit": str | None}

    The agent reads this to decide whether to bump last_updated_commit on
    reviewed pages. When allowed=False, scan still runs in read-only mode — it
    reports drift but does not bump state.

    Gate config comes from `<workspace>/.graph-wiki.yaml`'s `state_gate` block.
    `workspace=None` preserves the historical default (enabled, branches=["main"]).
    """
    from wiki_io.git_state import head_commit, is_clean_on_branches

    if workspace is None:
        enabled, branches = True, ["main"]
    else:
        from workspace_io import manifest

        enabled, branches = manifest.read_state_gate(workspace / ".graph-wiki.yaml")

    if not enabled:
        return {
            "allowed": True,
            "reason": "state gate disabled in .graph-wiki.yaml",
            "head_commit": head_commit(repo),
        }

    ok, reason = is_clean_on_branches(repo, branches)
    return {
        "allowed": ok,
        "reason": reason,
        "head_commit": head_commit(repo),
    }
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `uv run --package wiki-io pytest tests/test_state_gate.py -v`
Expected: PASS (5 tests).

- [ ] **Step 5: Commit**

```bash
git add packages/wiki-io/src/wiki_io/scan_monorepo.py packages/wiki-io/tests/test_state_gate.py
git commit -m "feat(wiki-io): make compute_state_gate read per-workspace config"
```

---

## Task 5: Thread workspace through callers

The default `workspace=None` keeps all existing callers/tests working, so this task wires real workspaces in so the config actually takes effect. The 3 call sites are in `scan.py` (1) and `ingest_source.py` (2).

**Files:**
- Modify: `packages/graph-wiki-core/src/graph_wiki_core/commands/scan.py:920`
- Modify: `packages/wiki-io/src/wiki_io/ingest_source.py:256`
- Modify: `packages/wiki-io/src/wiki_io/ingest_source.py:307`

- [ ] **Step 1: Update the scan caller**

In `packages/graph-wiki-core/src/graph_wiki_core/commands/scan.py`, line 920, change:
```python
        state_gate = compute_state_gate(repo)
```
to:
```python
        state_gate = compute_state_gate(repo, workspace=wiki.parent)
```

(`wiki` is the resolved wiki dir — line 820; its parent is the workspace root, the same value used at line 902's `graph_dir(wiki.parent)`.)

- [ ] **Step 2: Update the ingest folder-brief caller**

In `packages/wiki-io/src/wiki_io/ingest_source.py`, line 256, inside `build_folder_ingest_brief(source_path, wiki, repo)`, change:
```python
        "state_gate": compute_state_gate(repo),
```
to:
```python
        "state_gate": compute_state_gate(repo, workspace=wiki.parent),
```

- [ ] **Step 3: Update the ingest single-source caller**

In `packages/wiki-io/src/wiki_io/ingest_source.py`, line 307, inside `build_ingest_brief(...)` (which already receives `workspace_root`), change:
```python
        "state_gate": compute_state_gate(repo),
```
to:
```python
        "state_gate": compute_state_gate(repo, workspace=workspace_root),
```

- [ ] **Step 4: Run the affected package suites (excluding integration)**

Run:
```bash
uv run --package wiki-io pytest -m "not integration"
uv run --package graph-wiki-core pytest -m "not integration"
```
Expected: PASS. The graph-wiki-core scan tests patch `compute_state_gate` with a mock, so the added keyword argument does not break them; confirm green.

- [ ] **Step 5: Commit**

```bash
git add packages/graph-wiki-core/src/graph_wiki_core/commands/scan.py packages/wiki-io/src/wiki_io/ingest_source.py
git commit -m "feat: thread workspace into compute_state_gate callers"
```

---

## Task 6: Remove the dead `graph_wiki_core/config.py` module

`graph_wiki_core.config` is imported only by its own `tests/unit/test_config.py` (verified: no `src/` importer, not in the package `__init__`). Removing it eliminates the confusing second `state_gate_enabled`.

**Files:**
- Delete: `packages/graph-wiki-core/src/graph_wiki_core/config.py`
- Delete: `packages/graph-wiki-core/tests/unit/test_config.py`

- [ ] **Step 1: Re-verify there are no production importers**

Run:
```bash
grep -rn "graph_wiki_core.config\|from graph_wiki_core import config" packages --include="*.py"
```
Expected: matches ONLY in `packages/graph-wiki-core/tests/unit/test_config.py`. If anything else appears, STOP and reassess (do not delete).

- [ ] **Step 2: Delete the module and its test**

```bash
git rm packages/graph-wiki-core/src/graph_wiki_core/config.py packages/graph-wiki-core/tests/unit/test_config.py
```

- [ ] **Step 3: Confirm the package still imports**

Run:
```bash
uv run --package graph-wiki-core python -c "import graph_wiki_core"
```
Expected: no output, exit 0.

- [ ] **Step 4: Run the graph-wiki-core suite (excluding integration)**

Run: `uv run --package graph-wiki-core pytest -m "not integration"`
Expected: PASS, with `test_config.py` no longer collected.

- [ ] **Step 5: Commit**

```bash
git add -A
git commit -m "refactor(graph-wiki-core): remove dead config.py module"
```

---

## Task 7: Full regression sweep across touched packages

**Files:** none (verification only)

- [ ] **Step 1: Run each touched package's suite (excluding integration)**

Run:
```bash
uv run --package workspace-io pytest
uv run --package wiki-io pytest -m "not integration"
uv run --package graph-wiki-core pytest -m "not integration"
```
Expected: all PASS. If any failure references `is_clean_main` or `graph_wiki_core.config`, fix the stale reference (search-and-replace to `is_clean_on_branches` / remove the import) and re-run.

- [ ] **Step 2: Lint + format check**

Run:
```bash
uv run ruff check packages/workspace-io/src packages/wiki-io/src packages/graph-wiki-core/src
```
Expected: no new errors in the files this plan touched. (Per repo convention, do NOT run `ruff format` to "fix" unrelated pre-existing format drift — match surrounding multi-line style by hand.)

- [ ] **Step 3: Commit (only if any fixes were needed)**

```bash
git add -A
git commit -m "test: fix stale state-gate references after generalization"
```

(Skip the commit if Steps 1-2 were clean.)

---

## Task 8: Documentation

The `state_gate:` block is hand-edited (see "Resolved spec ambiguities" #2), so discoverability is via the README schema reference and the scan-workflow note — there is no init template to seed.

**Files:**
- Modify: `packages/workspace-io/README.md`
- Modify: `plugins/graph-wiki/skills/graph-wiki/references/scan-workflow.md`

- [ ] **Step 1: Add the `state_gate` bullet to the manifest schema list**

In `packages/workspace-io/README.md`, after the `plugin:` bullet (currently lines 13-15, ending with "the exact rules."), insert:

```markdown
- `state_gate:` (top-level, optional) — gate that guards `last_updated_commit`
  narrative-provenance stamping. `{enabled: bool, branches: [str, ...]}`,
  defaulting to `{enabled: true, branches: [main]}` when absent. Validated and
  normalized by `manifest.read()`; read via `read_state_gate()`.
```

- [ ] **Step 2: Add a `state_gate` schema subsection**

In `packages/workspace-io/README.md`, after the "Reading roles programmatically" section (i.e. after the `read_roles` example block near the end), append:

```markdown
## State gate

The optional top-level `state_gate:` block controls whether a scan/ingest run is
allowed to stamp `last_updated_commit` provenance:

```yaml
state_gate:           # gate that guards last_updated_commit narrative stamping
  enabled: true       # set false to disable the gate entirely (writes always allowed)
  branches:           # branches on which stamping is allowed (clean tree also required)
    - main
    - develop
```

- `enabled` (bool, default `true`) — `false` bypasses both the branch check and
  the clean-tree check; stamping is always allowed.
- `branches` (list of branch names, default `[main]`) — when enabled, stamping is
  allowed iff HEAD is on one of these branches AND the working tree is clean. A
  scalar value (`branches: main`) is coerced to a one-element list.

Read it programmatically:

```python
from pathlib import Path
from workspace_io import read_state_gate

enabled, branches = read_state_gate(Path(".graph-wiki.yaml"))
# -> (True, ["main"]) when the block / manifest is absent
```

Like the `plugin:` block, `state_gate:` is hand-edited — `manifest.write()` does
not emit it, so it survives only because `read()` round-trips disk additively.
```
````

(Note: the inner triple-backtick fences above are part of the README content being added.)

- [ ] **Step 3: Note configurability in the scan-workflow reference**

In `plugins/graph-wiki/skills/graph-wiki/references/scan-workflow.md`, find the section describing the state gate / `last_updated_commit` stamping. Add a sentence (match surrounding prose style):

```markdown
The state gate is configurable per-workspace via the `state_gate:` block in
`<workspace>/.graph-wiki.yaml` (`enabled` + allowed `branches`); absent config
gates on a clean `main`. See the workspace-io README for the schema.
```

If no existing state-gate paragraph is present in that file, add the sentence under the section that describes provenance/commit stamping.

- [ ] **Step 4: Verify the README renders the YAML blocks correctly**

Run: `grep -n "state_gate" packages/workspace-io/README.md`
Expected: the new bullet + subsection appear; fences are balanced (the file still has matching ```` ``` ```` counts — eyeball the added block).

- [ ] **Step 5: Commit**

```bash
git add packages/workspace-io/README.md plugins/graph-wiki/skills/graph-wiki/references/scan-workflow.md
git commit -m "docs: document configurable state_gate block"
```

---

## Self-Review (completed by plan author)

**Spec coverage:**
- §Schema (`state_gate` block, enabled/branches, scalar coercion) → Task 1.
- §1 (config read & schema validation in workspace-io; `read_state_gate`) → Tasks 1, 2.
- §2 (`is_clean_on_branches`, `compute_state_gate(repo, workspace=None)`, caller threading) → Tasks 3, 4, 5.
- §3 (bootstrap seeding) → resolved as documentation-only (Task 8) with rationale; see "Resolved spec ambiguities" #2.
- §4 (remove dead `config.py` + `test_config.py`) → Task 6.
- §Testing → tests embedded in Tasks 1-4; regression sweep Task 7.
- §Docs → Task 8.
- §Non-goals (no migration; `manifest.write()` losiness untouched) → honored; no `write()` change in any task.

**Type/name consistency:** `is_clean_on_branches(repo, branches: list[str]) -> tuple[bool, str]`, `read_state_gate(manifest_path) -> tuple[bool, list[str]]`, `compute_state_gate(repo, workspace=None) -> dict`, normalized block `{"enabled": bool, "branches": [str, ...]}` — used identically across producer (Task 1), accessor (Task 2), and consumer (Task 4).

**Placeholder scan:** none — every code/test step shows full content and exact commands.
