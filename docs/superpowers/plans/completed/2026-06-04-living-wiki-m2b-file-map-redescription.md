# Living Wiki M2b — Commit-Gated File-Map Re-Description Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** When a tracked file's content changes since its entity page's `last_updated_commit` anchor, re-describe that file's `## File map` Description row on the next scan — riding the existing `code_reader` describer pass, not a new fan-out.

**Architecture:** M2a wired a per-page commit anchor and `changed_files_since(repo, anchor, node_path)` to gate `## Narrative` refresh, collapsing the returned changed-file list to a boolean. M2b consumes that **same list** at file-row granularity: it drops changed paths from the `preserved` description map before `inject_file_map`, so the changed rows re-emerge as `— TODO` and Step 10c's existing describer fan-out re-fills them. One filtering step, one shared anchor for narrative + file map.

**Tech Stack:** Python 3.11+, `uv` workspace, `pytest` + `pytest-asyncio`, `python-frontmatter`. All LLM fan-out is mocked at the `SubagentPool.run_all` boundary (project fixture pattern) — no Bedrock calls in tests.

---

## Background — read before starting

You are finishing a spine M2a already built. Read the spec first: `docs/superpowers/specs/2026-06-04-living-wiki-m2b-file-map-redescription-design.md`. The five architecture decisions (D1–D3 in §2, the rider in §3.4) are settled — do not re-litigate them.

**The pipeline you are extending** lives entirely in `packages/graph-wiki-core/src/graph_wiki_core/commands/scan.py`, function `run_scan`:

1. `_snapshot_file_map_descriptions(wiki)` (≈`scan.py:112`) captures filled Description cells into `prior_file_map_descs = {uri: {package_root_path: description}}` **before** `write_entities` resets page bodies. This is a **cost cache**, not a human-authorship guarantee.
2. `_commit_dirty_uris(...)` (≈`scan.py:542`) computes, per `package`/`app`, whether files changed since the page's `last_updated_commit`. M2a uses only the boolean.
3. The narrator inject loop (≈`scan.py:865`) injects prose and stamps `last_updated_commit = HEAD`.
4. **Step 10b** (≈`scan.py:937`) re-injects the deterministic file map for `refreshed = created | updated`, grafting `preserved` descriptions back onto rows whose paths still exist; everything else shows `— TODO`.
5. **Step 10c** (≈`scan.py:1032`) `code_reader` fan-out fills **only** `— TODO` rows. A fully-described package has no TODO rows → no model call.

**The gap:** a file whose content changed keeps its preserved (now stale) description — its path still exists, so Step 10b grafts it back, Step 10c skips it (not a TODO). M2b drops changed paths from `preserved` so those rows become TODO again.

**Two facts that shape the tests (verified in the code):**

- `write_entities` treats `## Narrative` and `## File map` as **scanner-owned** sections (`_merge_preserved_sections`, `entity_writer.py:569`) — they always come from the template placeholder on re-render. So **any** page with a filled narrative or filled file map on disk re-renders to different bytes and is marked `updated` (the §4 "updated-churn"). Consequence: in a normal integration scan a commit-dirty page is *also* in `refreshed`. The §3.2 trigger extension is therefore **only observable when `write_entities`'s `updated` set is forced empty** — Task 5's regression test monkeypatches `write_entities` to do exactly that.
- The `preserved` dict is keyed by **package-root-relative** paths (e.g. `src/bar.py`), produced by `_file_map_full_path(_section_path_context(...), token)` (`entity_writer.py:1181`). `changed_files_since` returns **repo-relative** paths (e.g. `packages/foo/src/bar.py`). Task 1 is the transform that reconciles them.

---

## File Structure

Two files change; one new test file is added.

- **Modify** `packages/graph-wiki-core/src/graph_wiki_core/commands/scan.py`
  - New module helper `_changed_rel_paths(changed, node_path)` (§3.3 transform).
  - `_commit_dirty_uris` → `_commit_dirty_changes`, returning `dict[str, list[str] | None]` (keys = dirty URIs; value = changed repo-relative paths, or `None` for unknown anchor).
  - `run_scan`: hoist `head`, pre-init `commit_dirty`, extend the Step 10b trigger to `refreshed | commit_dirty`, apply the preserved-drop, track re-described pages, add the empty-prose guard, add the shared-anchor restamp.
- **Modify** `packages/graph-wiki-core/tests/unit/test_commit_gated_narrative.py`
  - Rename the imported helper and update the 5 unit assertions to the new dict return type. (M2a integration tests in this file are unchanged and must keep passing.)
- **Create** `packages/graph-wiki-core/tests/unit/test_commit_gated_file_map.py`
  - Unit tests for `_changed_rel_paths` + integration tests for re-describe-on-change, trigger-gap, idempotence, empty-prose guard, unknown-anchor, and `--no-narrate`.

All test commands run from the worktree root:
`/Users/pat/Personal/agent-research/.claude/worktrees/living-wiki-m2a`

---

## Task 1: `_changed_rel_paths` — the path-namespace transform (§3.3)

**Files:**
- Modify: `packages/graph-wiki-core/src/graph_wiki_core/commands/scan.py` (add helper above `_commit_dirty_uris`, i.e. just before line 542)
- Create: `packages/graph-wiki-core/tests/unit/test_commit_gated_file_map.py`

- [ ] **Step 1: Write the failing test**

Create `packages/graph-wiki-core/tests/unit/test_commit_gated_file_map.py` with exactly this content (more tests are appended in later tasks):

```python
"""Living Wiki M2b: commit-gated File-map row re-description + shared anchor."""

from __future__ import annotations

import asyncio
import json
import sqlite3
from pathlib import Path
from unittest.mock import MagicMock

import frontmatter as _fm
import graph_wiki_core.commands.scan as scan_mod
import pytest
from graph_io import exit_codes
from graph_wiki_core.commands.scan import _changed_rel_paths
from wiki_io.entity_writer import EntityWriteResult


# ---------------------------------------------------------------------------
# §3.3 path-namespace transform (unit)
# ---------------------------------------------------------------------------


def test_changed_rel_paths_relativizes_under_root() -> None:
    assert _changed_rel_paths(
        ["packages/pkg-a/mod.py", "packages/pkg-a/src/util.py"],
        "packages/pkg-a",
    ) == {"mod.py", "src/util.py"}


def test_changed_rel_paths_drops_paths_outside_root() -> None:
    assert _changed_rel_paths(
        ["packages/pkg-a/mod.py", "packages/pkg-b/other.py", "README.md"],
        "packages/pkg-a",
    ) == {"mod.py"}


def test_changed_rel_paths_empty() -> None:
    assert _changed_rel_paths([], "packages/pkg-a") == set()
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `uv run --package graph-wiki-core pytest packages/graph-wiki-core/tests/unit/test_commit_gated_file_map.py -v`
Expected: FAIL at import — `ImportError: cannot import name '_changed_rel_paths' from 'graph_wiki_core.commands.scan'`.

- [ ] **Step 3: Write the minimal implementation**

In `scan.py`, immediately **above** the `def _commit_dirty_uris(` line (currently line 542), add:

```python
def _changed_rel_paths(changed: list[str], node_path: str) -> set[str]:
    """Relativize repo-relative changed paths to package-root-relative keys.

    `changed_files_since` returns repo-relative paths (e.g.
    ``packages/foo/src/bar.py``); the File-map ``preserved`` dict is keyed by
    package-root-relative paths (e.g. ``src/bar.py``, see
    ``_extract_file_map_descriptions``). This maps the former to the latter so
    the preserved-drop's set-matching works. Paths not under ``node_path`` are
    silently dropped — they cannot match a row in this page's File map (§3.3).
    """
    base = Path(node_path)
    rel: set[str] = set()
    for p in changed:
        try:
            rel.add(str(Path(p).relative_to(base)))
        except ValueError:
            continue
    return rel
```

`Path` is already imported at `scan.py:17`.

- [ ] **Step 4: Run the test to verify it passes**

Run: `uv run --package graph-wiki-core pytest packages/graph-wiki-core/tests/unit/test_commit_gated_file_map.py -v`
Expected: 3 passed.

- [ ] **Step 5: Commit**

```bash
git add packages/graph-wiki-core/src/graph_wiki_core/commands/scan.py \
        packages/graph-wiki-core/tests/unit/test_commit_gated_file_map.py
git commit -m "feat(scan): add _changed_rel_paths repo→package-root transform (M2b §3.3)"
```

---

## Task 2: `_commit_dirty_changes` — return the changed-file list, not just the URI set

This converts M2a's boolean signal into the per-URI changed-file map M2b consumes, hoists `head`, pre-initializes `commit_dirty`, and updates the 5 existing unit tests + the call site. No external behavior changes yet.

**Files:**
- Modify: `packages/graph-wiki-core/src/graph_wiki_core/commands/scan.py:542-588` (function), `:749` (hoist `head`), `:755-756` (pre-init), `:787-805` (call site)
- Modify: `packages/graph-wiki-core/tests/unit/test_commit_gated_narrative.py:15` (import) and the 5 unit assertions at `:53-56,:64-67,:79-82,:90-93,:99-103`

- [ ] **Step 1: Update the existing unit tests to the new return type (these become the failing tests)**

In `packages/graph-wiki-core/tests/unit/test_commit_gated_narrative.py`:

Change the import on line 15:
```python
from graph_wiki_core.commands.scan import _commit_dirty_changes
```

`test_dirty_when_files_changed` — replace the call + assertion (lines 53-56):
```python
    dirty = _commit_dirty_changes(
        wiki, tmp_path / "repo", object(), "head_sha", frozenset()
    )
    assert dirty == {uri: ["packages/foo/x.py"]}
```

`test_clean_when_no_changes` — replace (lines 65-67):
```python
    assert _commit_dirty_changes(
        wiki, tmp_path / "repo", object(), "head_sha", frozenset()
    ) == {}
```

`test_skips_pages_without_anchor` — replace the call (lines 79-81) but keep the `consulted == []` assertion on line 82:
```python
    assert _commit_dirty_changes(
        wiki, tmp_path / "repo", object(), "head_sha", frozenset()
    ) == {}
    assert consulted == []  # git never consulted for anchorless pages
```

`test_unknown_anchor_treated_as_dirty` — replace (lines 91-93):
```python
    assert _commit_dirty_changes(
        wiki, tmp_path / "repo", object(), "head_sha", frozenset()
    ) == {uri: None}
```

`test_no_head_returns_empty` — replace (lines 101-103):
```python
    assert _commit_dirty_changes(
        wiki, tmp_path / "repo", object(), None, frozenset()
    ) == {}
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `uv run --package graph-wiki-core pytest packages/graph-wiki-core/tests/unit/test_commit_gated_narrative.py -v -k "dirty or clean or anchor or head"`
Expected: FAIL at import — `ImportError: cannot import name '_commit_dirty_changes'`.

- [ ] **Step 3: Rename + change the return type in `scan.py`**

Replace the entire `_commit_dirty_uris` function (lines 542-588) with:

```python
def _commit_dirty_changes(
    wiki: Path,
    repo: Path,
    conn: Any,
    head: str | None,
    collision_set: frozenset[str],
) -> dict[str, list[str] | None]:
    """Map `package`/`app` URIs whose files changed since the commit recorded on
    their page (`last_updated_commit`) to the changed-file list.

    Keys are the dirty URIs (so ``result.keys()`` is the M2a "needs
    re-narration" set). Each value is the repo-relative list of files
    ``changed_files_since`` reported, or ``None`` when the anchor SHA is unknown
    to this repo (D-D self-correction). Pages WITHOUT an anchor are skipped
    (D-C). M2a used only the keys; M2b consumes the values to drop changed rows
    from the File-map ``preserved`` map (§3.1).
    """
    dirty: dict[str, list[str] | None] = {}
    if head is None or conn is None:
        return dirty
    list_fns = _kind_list_fns()
    for kind in ("package", "app"):
        list_fn = list_fns.get(kind)
        if list_fn is None:
            continue
        for node in list_fn(conn):
            if not isinstance(node.attrs, dict):
                continue
            uri = node.attrs.get("uri")
            node_path = node.path
            if not uri or not node_path:
                continue
            page_path = _entity_page_path(wiki, kind, node, uri, collision_set)
            if not page_path.exists():
                continue
            try:
                anchor = frontmatter.load(page_path).metadata.get(
                    LAST_UPDATED_COMMIT_KEY
                )
            except Exception:  # noqa: BLE001 — a malformed page must not abort scan
                continue
            if not anchor:
                continue
            changed = changed_files_since(repo, str(anchor), node_path)
            if changed is None or changed:
                dirty[uri] = changed
    return dirty
```

- [ ] **Step 4: Hoist `head` and pre-initialize `commit_dirty`**

After line 749 (`state_gate = compute_state_gate(repo)`), add the `head` binding:

```python
        # Step 8: compute state gate
        state_gate = compute_state_gate(repo)
        head = state_gate.get("head_commit")
```

After line 756 (`narrator_result: FanOutResult | None = None`), add the `commit_dirty` pre-init:

```python
        entity_write_result = None
        narrator_result: FanOutResult | None = None
        # M2b: per-URI changed-file lists for commit-dirty package/app pages
        # (keys = dirty URIs; value = repo-relative changed paths, or None when
        # the page's anchor SHA is unknown to the repo). Consumed by Step 10b's
        # preserved-drop. Pre-initialized so the file-map block reads it safely
        # even when the graph conn is None.
        commit_dirty: dict[str, list[str] | None] = {}
```

- [ ] **Step 5: Update the call site**

Replace lines 787-805 (the `commit_dirty = _commit_dirty_uris(...)` block) with:

```python
            # M2a commit-gate: re-narrate package/app entities whose files
            # changed since their recorded last_updated_commit (Living Wiki M2).
            commit_dirty = _commit_dirty_changes(
                wiki,
                repo,
                conn,
                head,
                _compute_collision_set(conn, ADMITTED_KINDS, _kind_list_fns()),
            )
            if commit_dirty:
                # EntityWriteResult is a frozen dataclass; mutate the set in
                # place rather than rebinding the field (`|=` would rebind).
                entity_write_result.needs_narrative.update(commit_dirty.keys())
                append_log(
                    wiki,
                    "scan",
                    f"commit-gate: {len(commit_dirty)} entity(s) flagged for re-narration",
                    detail=None,
                    silent=True,
                    raise_exception=True,
                )
```

- [ ] **Step 6: Remove the now-redundant local `head` in the narrator loop**

In the `if narrator_result is not None:` block, delete the line `head = state_gate.get("head_commit")` (currently line 871). The loop now uses the hoisted `head`. Leave everything else in that block unchanged for now.

- [ ] **Step 7: Run the unit tests + the full M2a suite**

Run: `uv run --package graph-wiki-core pytest packages/graph-wiki-core/tests/unit/test_commit_gated_narrative.py -v`
Expected: all pass — the 5 renamed unit tests AND the 4 M2a integration tests (`test_narrative_survives_*`, `test_commit_dirty_entity_is_refreshed_and_restamped`, `test_mixed_scan_refreshes_changed_preserves_unchanged`).

- [ ] **Step 8: Commit**

```bash
git add packages/graph-wiki-core/src/graph_wiki_core/commands/scan.py \
        packages/graph-wiki-core/tests/unit/test_commit_gated_narrative.py
git commit -m "refactor(scan): _commit_dirty_changes returns per-URI changed-file list (M2b §3.1)"
```

---

## Task 3: Step 10b — trigger extension + preserved-drop (§3.1, §3.2, §3.3)

This is the core mechanism. The file-map injection trigger becomes `refreshed | commit_dirty`; for each commit-dirty page, changed paths are dropped from `preserved` (or all of it, on an unknown anchor) so those rows re-emerge as `— TODO` and Step 10c re-fills them. Re-described pages are tracked in `redescribed_uris` (consumed by Task 4).

**Files:**
- Modify: `packages/graph-wiki-core/src/graph_wiki_core/commands/scan.py:930-976` (Step 10b package/app branch only — leave the `test_suite` branch at `:983-1010` untouched, per §4 scope)
- Modify: `packages/graph-wiki-core/tests/unit/test_commit_gated_file_map.py` (append fixtures + 2 integration tests)

- [ ] **Step 1: Append the shared fixtures + the two failing integration tests**

Append to `packages/graph-wiki-core/tests/unit/test_commit_gated_file_map.py`:

```python
# ---------------------------------------------------------------------------
# Integration harness (mocks fan-out at the SubagentPool.run_all boundary)
# ---------------------------------------------------------------------------

_PKG_A = "pkg:org/repo/pkg-a"

# A deterministic file map with TWO file rows so tests can change one and assert
# the other's description survives (the cost cache).
_FILE_MAP_TWO_ROWS = (
    "## File map - pkg-a\nTODO\n\n### pkg-a/\nTODO\n\n"
    "| Path | Kind | Description |\n|---|---|---|\n"
    "| `mod.py` | file | — TODO |\n"
    "| `util.py` | file | — TODO |\n"
)


def _seed_one_package(db_path: Path) -> None:
    from graph_io import schema

    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(db_path)
    try:
        schema.apply_schema(conn)
        conn.execute(
            "INSERT INTO nodes(kind, name, path, line, attrs_json, uri) VALUES "
            "('package', 'pkg-a', 'packages/pkg-a', NULL, "
            "'{\"language\": \"python\"}', 'pkg:org/repo/pkg-a')"
        )
        conn.commit()
    finally:
        conn.close()


@pytest.fixture
def m2b_workspace(tmp_path, monkeypatch):
    workspace = tmp_path / "workspace"
    wiki = workspace / "wiki"
    repo = workspace / "repo"
    (wiki / ".graph-wiki").mkdir(parents=True)
    (wiki / "CLAUDE.md").write_text("# Wiki\n")
    (wiki / "log.md").write_text("", encoding="utf-8")
    repo.mkdir()
    monkeypatch.setenv("GRAPH_WIKI_WORKSPACE", str(workspace))
    _seed_one_package(workspace / ".graph" / "code.db")
    monkeypatch.setattr(
        scan_mod, "_cg_run_build",
        lambda repo, ws, *, full: (exit_codes.SUCCESS, "", ""),
    )
    monkeypatch.setattr(
        scan_mod, "make_llm", lambda role, *, model_override=None: MagicMock()
    )
    monkeypatch.setattr(
        scan_mod, "build_file_map",
        lambda path, **kw: (
            _FILE_MAP_TWO_ROWS if str(path).endswith("pkg-a") else None
        ),
    )
    return workspace


def _fanout_spy(*, prose, descs):
    """Patch SubagentPool.run_all: narrator items -> prose(item) (a str);
    code_reader items -> JSON of descs(item) (a {package_root_path: desc} dict).

    The real `task` callable is never invoked — like the M2a `_narrate_all_spy`,
    this short-circuits the pool so no Bedrock/file-read work happens.
    """

    async def _run_all(self, *, items, task, role, model_id, max_concurrency):
        from subagent_runtime.pool import FanOutResult

        result = FanOutResult()
        if role == "narrator":
            result.successes = [(it, prose(it)) for it in items]
        else:  # code_reader — item == (uri, ws_dict, page_path, todo_paths)
            result.successes = [(it, json.dumps(descs(it))) for it in items]
        return result

    return _run_all


def _descs_tagged(tag: dict):
    """Describer callback: every TODO path gets `<tag>:<path>` so a re-describe
    is distinguishable from the prior fill."""

    def _f(item) -> dict[str, str]:
        todo_paths = item[3]
        return {p: f"{tag['v']}:{p}" for p in todo_paths}

    return _f


def _page(wiki: Path, uri: str = _PKG_A) -> Path:
    return next(
        p
        for p in (wiki / "entities").glob("*.md")
        if _fm.load(p).metadata.get("uri") == uri
    )


def test_redescribe_changed_row_preserves_unchanged(m2b_workspace, monkeypatch) -> None:
    """Mutate one tracked file → its row re-describes; the other row keeps its
    prior description (cost cache intact). [spec test 1]"""
    workspace = m2b_workspace
    wiki = workspace / "wiki"
    repo = workspace / "repo"
    heads = {"v": "head1"}
    monkeypatch.setattr(
        scan_mod, "compute_state_gate",
        lambda repo: {"allowed": True, "reason": "clean", "head_commit": heads["v"]},
    )
    desc_tag = {"v": "D1"}
    monkeypatch.setattr(
        scan_mod.SubagentPool, "run_all",
        _fanout_spy(prose=lambda it: f"prose {it[0]}", descs=_descs_tagged(desc_tag)),
    )

    # Scan 1 at head1: describer fills both rows.
    asyncio.run(scan_mod.run_scan(workspace_path=workspace, repo_path=repo, narrate=True))
    t1 = _page(wiki).read_text(encoding="utf-8")
    assert "D1:mod.py" in t1
    assert "D1:util.py" in t1

    # Scan 2 at head2: only mod.py changed since head1.
    heads["v"] = "head2"
    desc_tag["v"] = "D2"
    monkeypatch.setattr(
        scan_mod, "changed_files_since",
        lambda repo, sha, sub: ["packages/pkg-a/mod.py"],
    )
    asyncio.run(scan_mod.run_scan(workspace_path=workspace, repo_path=repo, narrate=True))
    t2 = _page(wiki).read_text(encoding="utf-8")
    assert "D2:mod.py" in t2       # changed row re-described
    assert "D1:mod.py" not in t2   # stale description gone
    assert "D1:util.py" in t2      # unchanged row preserved (cost cache)


def test_trigger_gap_commit_dirty_not_refreshed(m2b_workspace, monkeypatch) -> None:
    """A commit-dirty package that write_entities reports as structurally
    UNCHANGED (refreshed == {}) still gets its File map re-injected and the
    changed row re-described. Fails without the `refreshed | commit_dirty`
    trigger extension. [spec test 2]"""
    workspace = m2b_workspace
    wiki = workspace / "wiki"
    repo = workspace / "repo"
    heads = {"v": "head1"}
    monkeypatch.setattr(
        scan_mod, "compute_state_gate",
        lambda repo: {"allowed": True, "reason": "clean", "head_commit": heads["v"]},
    )
    desc_tag = {"v": "D1"}
    monkeypatch.setattr(
        scan_mod.SubagentPool, "run_all",
        _fanout_spy(prose=lambda it: f"prose {it[0]}", descs=_descs_tagged(desc_tag)),
    )
    asyncio.run(scan_mod.run_scan(workspace_path=workspace, repo_path=repo, narrate=True))
    assert "D1:mod.py" in _page(wiki).read_text(encoding="utf-8")

    # Scan 2: force write_entities to report the package as unchanged (so the
    # only thing that can re-inject it is commit_dirty). The no-op leaves the
    # scan-1 page on disk intact — exactly the "body retained, not refreshed"
    # state §3.2 describes.
    heads["v"] = "head2"
    desc_tag["v"] = "D2"
    monkeypatch.setattr(
        scan_mod, "write_entities",
        lambda conn, wiki_arg, kinds: EntityWriteResult(unchanged=[_PKG_A]),
    )
    monkeypatch.setattr(
        scan_mod, "changed_files_since",
        lambda repo, sha, sub: ["packages/pkg-a/mod.py"],
    )
    asyncio.run(scan_mod.run_scan(workspace_path=workspace, repo_path=repo, narrate=True))
    t2 = _page(wiki).read_text(encoding="utf-8")
    assert "D2:mod.py" in t2
    assert "D1:mod.py" not in t2
    assert "D1:util.py" in t2
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `uv run --package graph-wiki-core pytest packages/graph-wiki-core/tests/unit/test_commit_gated_file_map.py -v -k "redescribe or trigger_gap"`
Expected: both FAIL. `test_redescribe_changed_row_preserves_unchanged` fails because the changed row keeps `D1:mod.py` (no drop yet). `test_trigger_gap_commit_dirty_not_refreshed` fails because with `refreshed == {}` the package is never file-mapped (`D1:mod.py` survives, `D2:mod.py` absent).

- [ ] **Step 3: Extend the Step 10b trigger + apply the preserved-drop**

In `scan.py`, find the file-map block starting at line 930. First, add `redescribed_uris` to the result-bucket declarations. Replace lines 930-936:

```python
        entities_file_mapped: list[str] = []
        file_map_errors: list[str] = []
        describer_filled: list[str] = []
        describer_errors: list[str] = []
        # (uri, node, page_path) for each package/app whose File map was injected
        # this scan — Step 10c uses these to fill remaining `— TODO` rows.
        file_mapped_pages: list[tuple[str, Any, Path]] = []
```

with:

```python
        entities_file_mapped: list[str] = []
        file_map_errors: list[str] = []
        describer_filled: list[str] = []
        describer_errors: list[str] = []
        # (uri, node, page_path) for each package/app whose File map was injected
        # this scan — Step 10c uses these to fill remaining `— TODO` rows.
        file_mapped_pages: list[tuple[str, Any, Path]] = []
        # M2b §3.4: package/app URIs whose File map was re-described this scan
        # (>=1 changed row dropped from preserved, or an unknown anchor forced a
        # full drop). Consumed by the shared-anchor restamp after Step 10c.
        redescribed_uris: set[str] = set()
```

Then replace the package/app injection branch. The current code (lines 937-976) reads:

```python
        if entity_write_result is not None and conn is not None:
            refreshed = set(entity_write_result.created) | set(
                entity_write_result.updated
            )
            list_fns = _kind_list_fns()
            # Collision set shared by the package/app and test-suite branches.
            fm_collision_set = (
                _compute_collision_set(conn, ADMITTED_KINDS, list_fns)
                if refreshed
                else frozenset()
            )
            fm_list_fns = [list_fns.get("package"), list_fns.get("app")]
            if refreshed and any(fm_list_fns) and not no_file_map:
                fm_nodes = [n for fn in fm_list_fns if fn for n in fn(conn)]
                for node in fm_nodes:
                    if not isinstance(node.attrs, dict):
                        continue
                    node_uri = node.attrs.get("uri")
                    if not node_uri or node_uri not in refreshed:
                        continue
                    node_path = node.path
                    if not node_path:
                        continue
                    file_map = build_file_map(repo / node_path, max_depth=max_depth)
                    if not file_map:
                        continue
                    slug = short_filename(node_uri, fm_collision_set)
                    fm_page_path = wiki / "entities" / f"{slug}.md"
                    try:
                        inject_file_map(
                            fm_page_path,
                            file_map,
                            preserved=prior_file_map_descs.get(node_uri),
                        )
                        entities_file_mapped.append(node_uri)
                        file_mapped_pages.append((node_uri, node, fm_page_path))
                    except Exception as fm_exc:  # noqa: BLE001 — partial-success
                        file_map_errors.append(
                            f"{node_uri}: inject_file_map failed: {fm_exc!r}"
                        )
```

Replace it with (only the package/app branch — do **not** touch the `test_suite` branch that follows it):

```python
        if entity_write_result is not None and conn is not None:
            refreshed = set(entity_write_result.created) | set(
                entity_write_result.updated
            )
            # M2b §3.2 (load-bearing): a package whose source changed with no
            # structural delta is in commit_dirty but NOT refreshed; without this
            # union its File map is never re-injected and the preserved-drop below
            # can't fire. Mirrors M2a's needs_narrative.update(commit_dirty).
            fm_targets = refreshed | set(commit_dirty)
            list_fns = _kind_list_fns()
            # Collision set shared by the package/app and test-suite branches.
            fm_collision_set = (
                _compute_collision_set(conn, ADMITTED_KINDS, list_fns)
                if fm_targets
                else frozenset()
            )
            fm_list_fns = [list_fns.get("package"), list_fns.get("app")]
            if fm_targets and any(fm_list_fns) and not no_file_map:
                fm_nodes = [n for fn in fm_list_fns if fn for n in fn(conn)]
                for node in fm_nodes:
                    if not isinstance(node.attrs, dict):
                        continue
                    node_uri = node.attrs.get("uri")
                    if not node_uri or node_uri not in fm_targets:
                        continue
                    node_path = node.path
                    if not node_path:
                        continue
                    file_map = build_file_map(repo / node_path, max_depth=max_depth)
                    if not file_map:
                        continue
                    # M2b §3.1/§3.3: drop changed rows from preserved so they
                    # re-emerge as `— TODO` and Step 10c re-describes them. Gated
                    # on `narrate` — an LLM-free scan keeps the cost cache intact
                    # and re-describes nothing (Step 10c is narrate-gated too).
                    preserved = dict(prior_file_map_descs.get(node_uri) or {})
                    if narrate and node_uri in commit_dirty:
                        changed = commit_dirty[node_uri]
                        if changed is None:
                            # Unknown anchor: no preserved row can be trusted —
                            # drop all, forcing a full re-describe (D-D / §3.1).
                            preserved = {}
                            redescribed_uris.add(node_uri)
                        else:
                            changed_rel = _changed_rel_paths(changed, node_path)
                            dropped = {p for p in preserved if p in changed_rel}
                            if dropped:
                                for p in dropped:
                                    preserved.pop(p, None)
                                redescribed_uris.add(node_uri)
                    slug = short_filename(node_uri, fm_collision_set)
                    fm_page_path = wiki / "entities" / f"{slug}.md"
                    try:
                        inject_file_map(
                            fm_page_path,
                            file_map,
                            preserved=preserved,
                        )
                        entities_file_mapped.append(node_uri)
                        file_mapped_pages.append((node_uri, node, fm_page_path))
                    except Exception as fm_exc:  # noqa: BLE001 — partial-success
                        file_map_errors.append(
                            f"{node_uri}: inject_file_map failed: {fm_exc!r}"
                        )
```

Note: `inject_file_map(preserved=preserved)` now receives a (possibly empty) dict instead of `None`; `_merge_preserved_descriptions` treats an empty dict as a no-op (`if not preserved: return block`), so this is behavior-equivalent for the no-drop case.

- [ ] **Step 4: Run the two new tests to verify they pass**

Run: `uv run --package graph-wiki-core pytest packages/graph-wiki-core/tests/unit/test_commit_gated_file_map.py -v -k "redescribe or trigger_gap"`
Expected: both pass.

- [ ] **Step 5: Run the M2a suite to confirm no regression**

Run: `uv run --package graph-wiki-core pytest packages/graph-wiki-core/tests/unit/test_commit_gated_narrative.py -v`
Expected: all pass (the M2a fixtures fill no JSON descriptions, so `preserved` stays empty and nothing is dropped).

- [ ] **Step 6: Commit**

```bash
git add packages/graph-wiki-core/src/graph_wiki_core/commands/scan.py \
        packages/graph-wiki-core/tests/unit/test_commit_gated_file_map.py
git commit -m "feat(scan): commit-gated file-map row re-description via preserved-drop (M2b §3.1-3.3)"
```

---

## Task 4: empty-prose guard + shared-anchor restamp (§3.4)

The anchor is the baseline 3.1 diffs against. Today it stamps on every narration. M2b: (a) the empty-prose guard skips the stamp when narration returns empty, so empty prose alone cannot mint a sticky "up-to-date" anchor; (b) a page whose file map was re-described this scan still advances its anchor to HEAD even if its narration was empty — otherwise the next scan re-describes the same files forever (non-idempotence + cost churn).

**Files:**
- Modify: `packages/graph-wiki-core/src/graph_wiki_core/commands/scan.py:865-884` (narrator inject loop) and after `:1106` (new restamp block, before Step 12 at `:1108`)
- Modify: `packages/graph-wiki-core/tests/unit/test_commit_gated_file_map.py` (append 4 integration tests)

- [ ] **Step 1: Append the four failing tests**

Append to `packages/graph-wiki-core/tests/unit/test_commit_gated_file_map.py`:

```python
def test_redescription_advances_anchor_then_idempotent(m2b_workspace, monkeypatch) -> None:
    """A re-description scan advances last_updated_commit to HEAD; a subsequent
    no-change scan re-describes nothing and leaves the anchor put. [spec test 4]"""
    workspace = m2b_workspace
    wiki = workspace / "wiki"
    repo = workspace / "repo"
    heads = {"v": "head1"}
    monkeypatch.setattr(
        scan_mod, "compute_state_gate",
        lambda repo: {"allowed": True, "reason": "clean", "head_commit": heads["v"]},
    )
    desc_tag = {"v": "D1"}
    monkeypatch.setattr(
        scan_mod.SubagentPool, "run_all",
        _fanout_spy(prose=lambda it: f"prose {it[0]}", descs=_descs_tagged(desc_tag)),
    )
    asyncio.run(scan_mod.run_scan(workspace_path=workspace, repo_path=repo, narrate=True))
    assert _fm.load(_page(wiki)).metadata.get("last_updated_commit") == "head1"

    # Scan 2: mod.py changed → re-described, anchor advances to head2.
    heads["v"] = "head2"
    desc_tag["v"] = "D2"
    monkeypatch.setattr(
        scan_mod, "changed_files_since",
        lambda repo, sha, sub: ["packages/pkg-a/mod.py"],
    )
    asyncio.run(scan_mod.run_scan(workspace_path=workspace, repo_path=repo, narrate=True))
    assert "D2:mod.py" in _page(wiki).read_text(encoding="utf-8")
    assert _fm.load(_page(wiki)).metadata.get("last_updated_commit") == "head2"

    # Scan 3: nothing changed since head2 → no re-description, anchor stable.
    heads["v"] = "head3"
    desc_tag["v"] = "D3"
    monkeypatch.setattr(scan_mod, "changed_files_since", lambda *a: [])
    asyncio.run(scan_mod.run_scan(workspace_path=workspace, repo_path=repo, narrate=True))
    t3 = _page(wiki).read_text(encoding="utf-8")
    assert "D2:mod.py" in t3        # untouched
    assert "D3:mod.py" not in t3    # describer never re-ran for it
    assert "D1:util.py" in t3
    assert _fm.load(_page(wiki)).metadata.get("last_updated_commit") == "head2"


def test_empty_narration_alone_does_not_stamp(m2b_workspace, monkeypatch) -> None:
    """Empty narration on a fresh page (no prior anchor, nothing re-described)
    must not mint an anchor. [spec test 5, part A]"""
    workspace = m2b_workspace
    wiki = workspace / "wiki"
    repo = workspace / "repo"
    monkeypatch.setattr(
        scan_mod, "compute_state_gate",
        lambda repo: {"allowed": True, "reason": "clean", "head_commit": "head1"},
    )
    monkeypatch.setattr(
        scan_mod.SubagentPool, "run_all",
        _fanout_spy(prose=lambda it: "", descs=_descs_tagged({"v": "D1"})),
    )
    asyncio.run(scan_mod.run_scan(workspace_path=workspace, repo_path=repo, narrate=True))
    assert _fm.load(_page(wiki)).metadata.get("last_updated_commit") is None


def test_redescription_advances_anchor_despite_empty_narration(
    m2b_workspace, monkeypatch
) -> None:
    """A scan that re-describes file-map rows advances the anchor even when
    narration returns empty. [spec test 5, part B]"""
    workspace = m2b_workspace
    wiki = workspace / "wiki"
    repo = workspace / "repo"
    heads = {"v": "head1"}
    monkeypatch.setattr(
        scan_mod, "compute_state_gate",
        lambda repo: {"allowed": True, "reason": "clean", "head_commit": heads["v"]},
    )
    prose_tag = {"v": "real prose"}
    desc_tag = {"v": "D1"}
    monkeypatch.setattr(
        scan_mod.SubagentPool, "run_all",
        _fanout_spy(prose=lambda it: prose_tag["v"], descs=_descs_tagged(desc_tag)),
    )
    # Scan 1: real prose stamps head1.
    asyncio.run(scan_mod.run_scan(workspace_path=workspace, repo_path=repo, narrate=True))
    assert _fm.load(_page(wiki)).metadata.get("last_updated_commit") == "head1"

    # Scan 2: mod.py changed, but narration comes back EMPTY. The re-description
    # must still advance the anchor.
    heads["v"] = "head2"
    prose_tag["v"] = ""
    desc_tag["v"] = "D2"
    monkeypatch.setattr(
        scan_mod, "changed_files_since",
        lambda repo, sha, sub: ["packages/pkg-a/mod.py"],
    )
    asyncio.run(scan_mod.run_scan(workspace_path=workspace, repo_path=repo, narrate=True))
    assert "D2:mod.py" in _page(wiki).read_text(encoding="utf-8")
    assert _fm.load(_page(wiki)).metadata.get("last_updated_commit") == "head2"


def test_unknown_anchor_full_redescribe_and_restamp(m2b_workspace, monkeypatch) -> None:
    """An anchor SHA unknown to the repo drops ALL preserved rows, re-describes
    every row once, then re-stamps to HEAD. [spec test 6]"""
    workspace = m2b_workspace
    wiki = workspace / "wiki"
    repo = workspace / "repo"
    heads = {"v": "head1"}
    monkeypatch.setattr(
        scan_mod, "compute_state_gate",
        lambda repo: {"allowed": True, "reason": "clean", "head_commit": heads["v"]},
    )
    desc_tag = {"v": "D1"}
    monkeypatch.setattr(
        scan_mod.SubagentPool, "run_all",
        _fanout_spy(prose=lambda it: f"prose {it[0]}", descs=_descs_tagged(desc_tag)),
    )
    asyncio.run(scan_mod.run_scan(workspace_path=workspace, repo_path=repo, narrate=True))
    assert "D1:util.py" in _page(wiki).read_text(encoding="utf-8")

    # Scan 2: changed_files_since returns None (anchor SHA gone) → drop all rows.
    heads["v"] = "head2"
    desc_tag["v"] = "D2"
    monkeypatch.setattr(scan_mod, "changed_files_since", lambda *a: None)
    asyncio.run(scan_mod.run_scan(workspace_path=workspace, repo_path=repo, narrate=True))
    t2 = _page(wiki).read_text(encoding="utf-8")
    assert "D2:mod.py" in t2
    assert "D2:util.py" in t2       # both rows re-described
    assert "D1:util.py" not in t2
    assert _fm.load(_page(wiki)).metadata.get("last_updated_commit") == "head2"
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `uv run --package graph-wiki-core pytest packages/graph-wiki-core/tests/unit/test_commit_gated_file_map.py -v -k "idempotent or empty_narration or despite_empty or unknown_anchor"`
Expected: `test_empty_narration_alone_does_not_stamp` FAILs (anchor is `head1`, not `None`, because the current loop stamps on any non-None `head`); `test_redescription_advances_anchor_despite_empty_narration` FAILs (anchor stays `head1` — empty prose currently stamps, then nothing re-advances after the future guard). The idempotence and unknown-anchor tests may pass already (narration is non-empty there), but keep them — they lock in the shared-anchor behavior.

- [ ] **Step 3: Add the empty-prose guard + `narr_stamped` tracking in the narrator loop**

In `scan.py`, the bucket declarations before the narrator block currently read (around lines 865-867):

```python
        entities_narrated: list[str] = []
        narrator_errors: list[str] = []
        if narrator_result is not None:
```

Insert `narr_stamped` so it exists regardless of whether the narrator ran:

```python
        entities_narrated: list[str] = []
        narrator_errors: list[str] = []
        # M2b §3.4: URIs the narrator loop stamped this scan (non-empty prose).
        # The shared-anchor restamp dedups against this set.
        narr_stamped: set[str] = set()
        if narrator_result is not None:
```

Then in the loop body, replace the stamp block. Current (after Task 2 removed the local `head =`):

```python
                try:
                    inject_narrative(entity_page_path, prose)
                    if head:
                        set_frontmatter_value(
                            entity_page_path, LAST_UPDATED_COMMIT_KEY, head
                        )
                    entities_narrated.append(uri_inner)
```

Replace with:

```python
                try:
                    inject_narrative(entity_page_path, prose)
                    # M2b §3.4 empty-prose guard: empty narration must not mint a
                    # sticky "up-to-date" anchor. Stamp only on real prose; a
                    # file-map re-description advances the anchor separately below.
                    if head and prose.strip():
                        set_frontmatter_value(
                            entity_page_path, LAST_UPDATED_COMMIT_KEY, head
                        )
                        narr_stamped.add(uri_inner)
                    entities_narrated.append(uri_inner)
```

- [ ] **Step 4: Add the shared-anchor restamp block after Step 10c**

In `scan.py`, after the Step 10c block ends (after line 1106, the `append_log(... "file descriptions filled" ...)` that closes the `if describer_filled or describer_errors:` inside `if narrate and file_mapped_pages and conn is not None:`) and **before** the `# Step 12: regenerate indexes` comment (line 1108), insert:

```python
        # M2b §3.4 shared-anchor rider: a page whose File map was re-described
        # this scan (>=1 changed row dropped & re-queued, or an unknown anchor
        # forced a full re-describe) must advance last_updated_commit to HEAD so
        # the next scan's diff baseline includes this re-description (idempotence
        # + cost-churn guard). Pages the narrator loop already stamped (non-empty
        # prose) are skipped — the empty-prose guard's intent is preserved.
        if narrate and head and redescribed_uris:
            for uri_inner, _node, page_path in file_mapped_pages:
                if uri_inner in redescribed_uris and uri_inner not in narr_stamped:
                    try:
                        set_frontmatter_value(
                            page_path, LAST_UPDATED_COMMIT_KEY, head
                        )
                    except Exception as exc:  # noqa: BLE001 — non-fatal stamp
                        logger.warning(
                            "anchor restamp failed for %s: %s", uri_inner, exc
                        )
```

- [ ] **Step 5: Run the four tests to verify they pass**

Run: `uv run --package graph-wiki-core pytest packages/graph-wiki-core/tests/unit/test_commit_gated_file_map.py -v -k "idempotent or empty_narration or despite_empty or unknown_anchor"`
Expected: all 4 pass.

- [ ] **Step 6: Run the M2a suite (the empty-prose guard must not regress it)**

Run: `uv run --package graph-wiki-core pytest packages/graph-wiki-core/tests/unit/test_commit_gated_narrative.py -v`
Expected: all pass — M2a tests always narrate non-empty prose, so the guard still stamps.

- [ ] **Step 7: Commit**

```bash
git add packages/graph-wiki-core/src/graph_wiki_core/commands/scan.py \
        packages/graph-wiki-core/tests/unit/test_commit_gated_file_map.py
git commit -m "feat(scan): empty-prose guard + shared-anchor restamp for re-described pages (M2b §3.4)"
```

---

## Task 5: `--no-narrate` leaves the cost cache and anchor untouched (spec test 7)

The preserved-drop and restamp are both `narrate`-gated and Step 10c is already `narrate`-gated, so a `--no-narrate` scan should refresh file-map *structure* but re-describe nothing and stamp no anchor. This task adds the regression test that locks that in.

**Files:**
- Modify: `packages/graph-wiki-core/tests/unit/test_commit_gated_file_map.py` (append 1 test)

- [ ] **Step 1: Append the test**

Append to `packages/graph-wiki-core/tests/unit/test_commit_gated_file_map.py`:

```python
def test_no_narrate_keeps_cost_cache_and_anchor(m2b_workspace, monkeypatch) -> None:
    """A --no-narrate rescan with a changed file refreshes structure but does
    NOT drop/re-describe rows and does NOT move the anchor. [spec test 7]"""
    workspace = m2b_workspace
    wiki = workspace / "wiki"
    repo = workspace / "repo"
    heads = {"v": "head1"}
    monkeypatch.setattr(
        scan_mod, "compute_state_gate",
        lambda repo: {"allowed": True, "reason": "clean", "head_commit": heads["v"]},
    )
    desc_tag = {"v": "D1"}
    monkeypatch.setattr(
        scan_mod.SubagentPool, "run_all",
        _fanout_spy(prose=lambda it: f"prose {it[0]}", descs=_descs_tagged(desc_tag)),
    )
    # Scan 1 (narrate) fills rows + stamps head1.
    asyncio.run(scan_mod.run_scan(workspace_path=workspace, repo_path=repo, narrate=True))
    assert _fm.load(_page(wiki)).metadata.get("last_updated_commit") == "head1"

    # Scan 2 (--no-narrate) at head2 with mod.py changed.
    heads["v"] = "head2"
    desc_tag["v"] = "D2"
    monkeypatch.setattr(
        scan_mod, "changed_files_since",
        lambda repo, sha, sub: ["packages/pkg-a/mod.py"],
    )
    asyncio.run(scan_mod.run_scan(workspace_path=workspace, repo_path=repo, narrate=False))
    t2 = _page(wiki).read_text(encoding="utf-8")
    assert "D1:mod.py" in t2        # NOT re-described (cost cache intact)
    assert "D2:mod.py" not in t2
    assert "D1:util.py" in t2
    assert _fm.load(_page(wiki)).metadata.get("last_updated_commit") == "head1"
```

- [ ] **Step 2: Run the test**

Run: `uv run --package graph-wiki-core pytest packages/graph-wiki-core/tests/unit/test_commit_gated_file_map.py -v -k "no_narrate"`
Expected: PASS (the gating from Tasks 3–4 already enforces this; this test documents and protects it).

If it fails, the drop or restamp is missing a `narrate` guard — re-check Task 3 Step 3 (`if narrate and node_uri in commit_dirty:`) and Task 4 Step 4 (`if narrate and head and redescribed_uris:`).

- [ ] **Step 3: Run the whole M2b + M2a file/narrative suite + lint**

Run:
```bash
uv run --package graph-wiki-core pytest \
  packages/graph-wiki-core/tests/unit/test_commit_gated_file_map.py \
  packages/graph-wiki-core/tests/unit/test_commit_gated_narrative.py -v
uv run ruff check packages/graph-wiki-core/src/graph_wiki_core/commands/scan.py \
  packages/graph-wiki-core/tests/unit/test_commit_gated_file_map.py
```
Expected: all tests pass; ruff reports no errors (in particular no `I001` import-sort and no `F841` unused-variable findings).

- [ ] **Step 4: Run the full graph-wiki-core test package to confirm no wider regression**

Run: `uv run --package graph-wiki-core pytest packages/graph-wiki-core -q`
Expected: green (no failures introduced by the scan.py changes).

- [ ] **Step 5: Commit**

```bash
git add packages/graph-wiki-core/tests/unit/test_commit_gated_file_map.py
git commit -m "test(scan): --no-narrate keeps file-map cost cache and anchor (M2b test 7)"
```

---

## Self-Review

**Spec coverage** (each §/test mapped to a task):

| Spec item | Where implemented |
|---|---|
| D1 — reuse M2a anchor, no content-hash ledger | No ledger added; Task 2/3 reuse `changed_files_since` + `last_updated_commit`. |
| D2 — file-map rows scanner-owned, re-describe freely | Task 3 overwrites rows via drop-from-preserved; no ownership marker. |
| D3 — ride the existing describer (drop-from-preserved) | Task 3 drops paths; Step 10c (unchanged) re-fills. |
| §3.1 core filtering step + `changed is None` drop-all | Task 3 Step 3. |
| §3.2 trigger extension `refreshed \| commit_dirty` | Task 3 Step 3 (`fm_targets`); regression = Task 3 Step 1 `test_trigger_gap_*`. |
| §3.3 path-namespace reconciliation | Task 1 (`_changed_rel_paths`) + applied in Task 3. |
| §3.4 shared-anchor stamping + empty-prose guard | Task 4. |
| §4 out-of-scope (test_suite, churn #4) | `test_suite` branch left untouched in Task 3 Step 3; no churn-fix attempted. |
| Test 1 re-describe on change | Task 3 `test_redescribe_changed_row_preserves_unchanged`. |
| Test 2 trigger-gap regression | Task 3 `test_trigger_gap_commit_dirty_not_refreshed`. |
| Test 3 path-namespace | Task 1 unit tests. |
| Test 4 shared-anchor advance + idempotence | Task 4 `test_redescription_advances_anchor_then_idempotent`. |
| Test 5 empty-prose guard (both halves) | Task 4 `test_empty_narration_alone_does_not_stamp` + `test_redescription_advances_anchor_despite_empty_narration`. |
| Test 6 unknown anchor self-corrects | Task 4 `test_unknown_anchor_full_redescribe_and_restamp`. |
| Test 7 `--no-narrate` | Task 5 `test_no_narrate_keeps_cost_cache_and_anchor`. |

**Type consistency:** `_commit_dirty_changes` returns `dict[str, list[str] | None]` everywhere it's named (def, call site, unit tests). `commit_dirty` is the dict; `commit_dirty.keys()` feeds `needs_narrative`; `set(commit_dirty)` feeds `fm_targets`; `commit_dirty[node_uri]` is `list[str] | None` and is branched on `is None`. `_changed_rel_paths(list[str], str) -> set[str]` matches its one call site. `redescribed_uris`/`narr_stamped` are `set[str]`; `file_mapped_pages` is `list[tuple[str, Any, Path]]`, unpacked as `(uri_inner, _node, page_path)` in the restamp loop. `inject_file_map(preserved=...)` accepts `dict | None`; a possibly-empty dict is passed and treated as a no-op when empty.

**Placeholder scan:** no TBD/TODO-in-plan, no "add error handling" hand-waves — every code step shows complete code and every test step shows the exact assertion and command.

**Known, in-spec limitation (not a gap):** a commit-dirty page whose only change is a brand-new file (no prior preserved row) AND whose narration returns empty will not advance its anchor that scan (nothing was *re*-described; a first-time TODO fill is a describe, not a re-describe). This matches §3.4's rule ("a file-map re-description happened") and the empty-prose guard's intent. It is not the idempotence case Test 4 protects (which mutates an existing filled row).

---

## Execution Handoff

**Plan complete and saved to `docs/superpowers/plans/2026-06-04-living-wiki-m2b-file-map-redescription.md`. Two execution options:**

**1. Subagent-Driven (recommended)** — I dispatch a fresh subagent per task, review between tasks, fast iteration.

**2. Inline Execution** — Execute tasks in this session using executing-plans, batch execution with checkpoints for review.

**Which approach?**
