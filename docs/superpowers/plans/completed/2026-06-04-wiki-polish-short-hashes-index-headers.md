# Wiki Polish — Short Commit Hashes + Per-Entity Index Headers + `updated`-Field Confirmation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Three independent browsing-quality fixes to the graph-wiki: (1) abbreviate git SHAs written into entity-page frontmatter to git's canonical short form at the single write boundary; (2) give each By-Kind entity in `index.md` its own `####` header so it becomes a deep-link/TOC anchor target; (3) confirm (no code change) that the `updated:` frontmatter instruction is not stale.

**Architecture:** Item 1 adds one tolerant helper (`short_commit`) in `wiki_io.git_state` and calls it once per scan in `commands/scan.py`, stamping the short form; downstream `drift_checked_commit`/`detected_commit` inherit it via `anchor`. Item 2 changes only `_render_by_kind` in `wiki_io.index_generator` (the `## Domains` tree is untouched), reusing the existing `_entity_wikilink` (extended with an optional `label`) and the unchanged `_render_pkg_nested`. Item 3 is a confirmation only.

**Tech Stack:** Python 3.11, `uv` workspace monorepo, pytest (`asyncio_mode=auto`), git via `subprocess`, SQLite code-graph, `python-frontmatter`.

---

## Background facts (verified against the code on 2026-06-04)

Read these before starting — they prevent the most likely mistakes.

- **`wiki_io.git_state`** (`packages/wiki-io/src/wiki_io/git_state.py`) already has a private `_run(repo, *args) -> tuple[int, str, str] | None` returning `(returncode, stdout, stderr)` (or `None` if git is missing / errored), plus `head_commit`, `is_clean_main`, `changed_files_since`. The module docstring is a `#!/usr/bin/env python3` shebang then a `"""..."""` docstring, then `from __future__ import annotations`. Add the new helper in this style.
- **The single SHA write boundary** is `commands/scan.py`. `head = state_gate.get("head_commit")` is set at `scan.py:914` (full 40-char SHA). The only `set_frontmatter_value(page_path, LAST_UPDATED_COMMIT_KEY, head)` call is at `scan.py:1330-1331`, inside `if narrate and head:` (the M2c Part-3 refill-gated stamping block, ~`scan.py:1316-1336`). `repo` is already in scope (resolved at `scan.py:805-811`). `drift_checked_commit` (`scan.py:715,720`) and `detected_commit` (`scan.py:703`) are assigned `anchor` (the page's own stored `last_updated_commit`), so they inherit whatever form it has — no separate change needed.
- **Existing commit-gate tests keep passing after Item 1.** Every test in `packages/graph-wiki-core/tests/unit/test_commit_gated_*.py`, `test_updated_churn.py`, `test_m2d_crash_window.py`, `test_human_section_drift.py` uses a bare `repo.mkdir()` directory (NOT a git checkout) and a fake SHA like `"head1"`. `short_commit(<non-git-dir>, "head1")` runs `git rev-parse --short head1`, which fails (returncode 128) → the helper returns the input unchanged. So `last_updated_commit == "head1"` still holds everywhere. This is the whole reason the fallback exists.
- **`index_generator._render_by_kind`** (`index_generator.py:731-774`) renders, under `## By Kind` → `### {KIND_LABELS[kind]}` (H3 per kind, apps→packages→agent_plugins via `BY_KIND_ORDER`), one **bare name bullet** per entity via `_entity_bullet(e, collision_set, "")` (`index_generator.py:762-763`), then for `package`/`app` appends `_render_pkg_nested(...)`.
- **`_entity_wikilink(entity, collision_set)`** (`index_generator.py:549-565`) returns `[[wiki/entities/{stem}|{entity.name}]]` — the display text is plainly `entity.name` (collision disambiguation lives only in the `stem`/filename, via `_short_filename`). So the "collision-aware display name" for a header is just `entity.name`; no new disambiguation helper is needed. `_entity_wikilink` is referenced ONLY inside `index_generator.py` and is NOT in `__all__`, so adding an optional parameter is safe.
- **`_render_pkg_nested`** (`index_generator.py:578-621`) is shared byte-for-byte by the Domains tree and By-Kind, and its sub-lists start at 2-space indent (`  - Test Suites`, `    - [[…]]`). It is reused **unchanged**. A `  - ...` bullet list directly after a paragraph line is valid CommonMark (a bullet list interrupts a paragraph), so no blank line is inserted between the link line and the nested list — matching today's behavior where the nested list followed the bullet.
- **No committed syrupy snapshot exists** for `index_generator`. `test_snapshot_against_agent_research` (`test_index_generator.py:1297-1306`) is `@pytest.mark.skipif(_WS_ROOT is None)` and `_WS_ROOT` walks up from the test file looking for `.graph-wiki/graph.db`; in this repo the workspace is a sibling (not under the repo), so it is skipped in normal runs. If a developer has a live graph that makes it run, regenerate with `--snapshot-update` — but this plan does not depend on it.

**Convention note / assumption:** CLAUDE.md says `integration`-marked tests "need real Bedrock or subprocesses". The new tests in this plan use `git` via `subprocess` but are hermetic (temp dirs) and fast, and the existing `run_scan` narrate-style tests in `test_commit_gated_narrative.py` are **unmarked** despite exercising the full scan. To keep these tests running by default (where their value is), this plan leaves them **unmarked**. If the team prefers, they can later add `@pytest.mark.integration` — that is a one-line change and does not affect correctness.

---

## File Structure

- `packages/wiki-io/src/wiki_io/git_state.py` — **modify**: add `short_commit(repo, sha)` helper.
- `packages/wiki-io/tests/test_git_state.py` — **create**: unit tests for `short_commit` (real temp git repo + failure paths).
- `packages/graph-wiki-core/src/graph_wiki_core/commands/scan.py` — **modify**: import `short_commit`; compute `short_head` once; stamp with it.
- `packages/graph-wiki-core/tests/unit/test_commit_gated_narrative.py` — **modify**: add a real-git-repo fixture + one test asserting the stamped commit is the short form (reuses existing helpers in that file).
- `packages/wiki-io/src/wiki_io/index_generator.py` — **modify**: add optional `label` to `_entity_wikilink`; rewrite the per-entity loop in `_render_by_kind` to emit `####` headers.
- `packages/wiki-io/tests/test_index_generator.py` — **modify**: augment/update By-Kind assertions for the new header shape.

---

## Task 1: `short_commit` helper in `wiki_io.git_state`

**Files:**
- Modify: `packages/wiki-io/src/wiki_io/git_state.py` (add helper after `head_commit`, ~line 37)
- Test: `packages/wiki-io/tests/test_git_state.py` (create)

- [ ] **Step 1: Write the failing tests**

Create `packages/wiki-io/tests/test_git_state.py`:

```python
"""Tests for wiki_io.git_state.short_commit (Item 1 — short commit hashes)."""
from __future__ import annotations

import subprocess
from pathlib import Path

from wiki_io.git_state import head_commit, short_commit


def _git(repo: Path, *args: str) -> None:
    subprocess.run(["git", *args], cwd=repo, check=True, capture_output=True)


def _init_repo(repo: Path) -> str:
    """Init a one-commit git repo; return its full HEAD SHA."""
    repo.mkdir(parents=True, exist_ok=True)
    (repo / "f.txt").write_text("hi\n", encoding="utf-8")
    _git(repo, "init")
    _git(repo, "add", "-A")
    _git(repo, "-c", "user.email=t@t", "-c", "user.name=t", "commit", "-m", "init")
    full = head_commit(repo)
    assert full is not None and len(full) == 40
    return full


def test_short_commit_returns_resolvable_prefix(tmp_path):
    repo = tmp_path / "repo"
    full = _init_repo(repo)
    short = short_commit(repo, full)
    assert short != full
    assert len(short) < 40
    assert full.startswith(short)
    # git still resolves the short form back to the full SHA
    out = subprocess.run(
        ["git", "rev-parse", short], cwd=repo, capture_output=True, text=True
    )
    assert out.stdout.strip() == full


def test_short_commit_bogus_sha_returns_input(tmp_path):
    repo = tmp_path / "repo"
    _init_repo(repo)
    assert short_commit(repo, "deadbeefdeadbeef") == "deadbeefdeadbeef"


def test_short_commit_non_git_dir_returns_input(tmp_path):
    non_repo = tmp_path / "plain"
    non_repo.mkdir()
    sha = "a" * 40
    assert short_commit(non_repo, sha) == sha
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `uv run --package wiki-io pytest tests/test_git_state.py -v`
Expected: FAIL — `ImportError: cannot import name 'short_commit' from 'wiki_io.git_state'`.

- [ ] **Step 3: Implement `short_commit`**

In `packages/wiki-io/src/wiki_io/git_state.py`, add immediately after the `head_commit` function (after line 36, before `is_clean_main`):

```python
def short_commit(repo: Path, sha: str) -> str:
    """Abbreviate a SHA to git's canonical short form (adaptive length).

    Returns the input unchanged on any git failure — a full SHA is still
    git-resolvable, so callers never break. Mirrors the other _run-based
    helpers in this module.
    """
    out = _run(repo, "rev-parse", "--short", sha)
    if out is None or out[0] != 0 or not out[1].strip():
        return sha
    return out[1].strip()
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `uv run --package wiki-io pytest tests/test_git_state.py -v`
Expected: PASS (3 passed).

- [ ] **Step 5: Commit**

```bash
git add packages/wiki-io/src/wiki_io/git_state.py packages/wiki-io/tests/test_git_state.py
git commit -m "feat(wiki-io): add short_commit helper for canonical SHA abbreviation

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

---

## Task 2: Stamp the short SHA in `commands/scan.py`

**Files:**
- Modify: `packages/graph-wiki-core/src/graph_wiki_core/commands/scan.py:68` (import), `:914` (compute once), `:1331` (use it)
- Test: `packages/graph-wiki-core/tests/unit/test_commit_gated_narrative.py` (add fixture + test)

- [ ] **Step 1: Write the failing test**

In `packages/graph-wiki-core/tests/unit/test_commit_gated_narrative.py`, add `import subprocess` to the top-of-file imports (alongside the existing `import asyncio` / `import sqlite3`), then append this fixture and test at the END of the file. It reuses the existing module-level helpers `_seed_one_package`, `_narrate_all_spy`, `_page_for`, and the already-imported `scan_mod`, `exit_codes`, `MagicMock`, `_fm`, `asyncio`:

```python
# ---------------------------------------------------------------------------
# Item 1: stamped last_updated_commit is git's canonical short form
# ---------------------------------------------------------------------------


@pytest.fixture
def m2a_workspace_gitrepo(tmp_path, monkeypatch):
    """Like m2a_workspace, but `repo` is a REAL one-commit git checkout so
    short_commit(repo, full_sha) actually abbreviates (instead of falling back).
    Yields (workspace, full_head_sha)."""
    workspace = tmp_path / "workspace"
    wiki = workspace / "wiki"
    repo = workspace / "repo"
    (wiki / ".graph-wiki").mkdir(parents=True)
    (wiki / "CLAUDE.md").write_text("# Wiki\n")
    (wiki / "log.md").write_text("", encoding="utf-8")

    # Real git repo with one commit (so `git rev-parse --short <full>` resolves).
    (repo / "packages" / "pkg-a").mkdir(parents=True)
    (repo / "packages" / "pkg-a" / "pyproject.toml").write_text(
        "[project]\n", encoding="utf-8"
    )
    for args in (
        ["init"],
        ["add", "-A"],
        ["-c", "user.email=t@t", "-c", "user.name=t", "commit", "-m", "init"],
    ):
        subprocess.run(["git", *args], cwd=repo, check=True, capture_output=True)
    full = subprocess.run(
        ["git", "rev-parse", "HEAD"], cwd=repo, capture_output=True, text=True
    ).stdout.strip()

    monkeypatch.setenv("GRAPH_WIKI_WORKSPACE", str(workspace))
    _seed_one_package(workspace / ".graph-wiki" / "code.db")
    monkeypatch.setattr(
        scan_mod, "_cg_run_build", lambda repo, ws, *, full: (exit_codes.SUCCESS, "", "")
    )
    monkeypatch.setattr(
        scan_mod, "make_llm", lambda role, *, model_override=None: MagicMock()
    )
    monkeypatch.setattr(
        scan_mod,
        "build_file_map",
        lambda path, **kw: (
            "## File map - pkg-a\nTODO\n\n### pkg-a/\nTODO\n\n"
            "| Path | Kind | Description |\n|---|---|---|\n"
            "| `pyproject.toml` | file | — TODO |\n"
            if str(path).endswith("pkg-a")
            else None
        ),
    )
    monkeypatch.setattr(
        scan_mod,
        "compute_state_gate",
        lambda repo: {"allowed": True, "reason": "clean", "head_commit": full},
    )
    return workspace, full


def test_stamped_commit_is_short_form(m2a_workspace_gitrepo, monkeypatch) -> None:
    """A narrated page's last_updated_commit is stamped as git's short SHA
    (abbreviated, a strict prefix of HEAD, and still git-resolvable)."""
    workspace, full = m2a_workspace_gitrepo
    wiki = workspace / "wiki"
    repo = workspace / "repo"
    monkeypatch.setattr(
        scan_mod.SubagentPool,
        "run_all",
        _narrate_all_spy(lambda it: f"PROSE for {it[0]}"),
    )

    asyncio.run(
        scan_mod.run_scan(workspace_path=workspace, repo_path=repo, narrate=True)
    )

    stamped = str(_fm.load(_page_for(wiki)).metadata.get("last_updated_commit"))
    assert stamped != full           # abbreviated, not the full 40-char SHA
    assert len(stamped) < 40
    assert full.startswith(stamped)  # git's canonical prefix
    resolved = subprocess.run(
        ["git", "rev-parse", stamped], cwd=repo, capture_output=True, text=True
    ).stdout.strip()
    assert resolved == full          # short form still resolves to HEAD
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `uv run --package graph-wiki-core pytest tests/unit/test_commit_gated_narrative.py::test_stamped_commit_is_short_form -v`
Expected: FAIL on `assert stamped != full` — scan currently stamps the full SHA.

- [ ] **Step 3: Wire `short_commit` into scan**

In `packages/graph-wiki-core/src/graph_wiki_core/commands/scan.py`:

Change the import at line 68 from:
```python
from wiki_io.git_state import changed_files_since
```
to:
```python
from wiki_io.git_state import changed_files_since, short_commit
```

Then at line 914, change:
```python
        head = state_gate.get("head_commit")
```
to:
```python
        head = state_gate.get("head_commit")
        # Item 1: abbreviate to git's canonical short form ONCE per scan (HEAD is
        # the same for every page stamped this run). Falls back to the full SHA on
        # any git failure, so stamping never breaks (full SHAs stay git-resolvable).
        short_head = short_commit(repo, head) if head else head
```

Then at line 1330-1331, change:
```python
                    set_frontmatter_value(
                        page_path, LAST_UPDATED_COMMIT_KEY, head
                    )
```
to:
```python
                    set_frontmatter_value(
                        page_path, LAST_UPDATED_COMMIT_KEY, short_head
                    )
```

(The `if narrate and head:` gate at line 1316 stays gated on `head`; `short_head` is non-empty whenever `head` is.)

- [ ] **Step 4: Run the new test to verify it passes**

Run: `uv run --package graph-wiki-core pytest tests/unit/test_commit_gated_narrative.py::test_stamped_commit_is_short_form -v`
Expected: PASS.

- [ ] **Step 5: Run the full commit-gate suite to confirm no regression**

Run: `uv run --package graph-wiki-core pytest tests/unit/test_commit_gated_narrative.py tests/unit/test_commit_gated_file_map.py tests/unit/test_commit_gated_agent_plugin.py tests/unit/test_commit_gated_test_suite.py tests/unit/test_updated_churn.py tests/unit/test_m2d_crash_window.py tests/unit/test_human_section_drift.py -q`
Expected: PASS (all green). These use bare-dir repos + fake SHAs, so `short_commit` falls back to the input and `last_updated_commit == "head1"`/`"head2"` assertions are unaffected.

- [ ] **Step 6: Commit**

```bash
git add packages/graph-wiki-core/src/graph_wiki_core/commands/scan.py packages/graph-wiki-core/tests/unit/test_commit_gated_narrative.py
git commit -m "feat(scan): stamp last_updated_commit as git short SHA

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

---

## Task 3: Per-entity `####` headers in `## By Kind` (`index_generator.py`)

**Files:**
- Modify: `packages/wiki-io/src/wiki_io/index_generator.py:549-565` (add `label` to `_entity_wikilink`), `:762-770` (rewrite per-entity loop body in `_render_by_kind`)
- Test: `packages/wiki-io/tests/test_index_generator.py`

- [ ] **Step 1: Update the failing tests (red)**

Make three edits in `packages/wiki-io/tests/test_index_generator.py`.

**Edit 1 — augment `TestRenderByKind::test_by_kind_section_order`.** Replace the assertion block at the end of that test (currently lines 548-557, from `app_idx = text.find("### Apps")` through `assert "[[wiki/entities/dep_boto3|boto3]]" in text`) with:

```python
        app_idx = text.find("### Apps")
        pkg_idx = text.find("### Packages")
        plug_idx = text.find("### Agent Plugins")
        assert app_idx > -1 and pkg_idx > -1 and plug_idx > -1
        # Apps first, then packages, then agent_plugins (D-03).
        assert app_idx < pkg_idx < plug_idx
        # By-kind entities now render as `#### {name}` headers with an
        # `open page` link line (header replaces the old name bullet).
        assert "#### pkg-cross" in text
        assert "[[wiki/entities/pkg_pkg-cross|open page]]" in text
        assert "#### myapp" in text
        assert "[[wiki/entities/app_myapp|open page]]" in text
        assert "#### graph-wiki" in text
        assert "[[wiki/entities/agent-plugin_graph-wiki|open page]]" in text
        # The old bare name bullet for a by-kind entity is gone.
        assert "[[wiki/entities/pkg_pkg-cross|pkg-cross]]" not in text
        # No flat dependency group; boto3 still nests under pkg-cross (bullet).
        assert "### Dependencies" not in text
        assert "  - Dependencies" in text
        assert "[[wiki/entities/dep_boto3|boto3]]" in text
```

**Edit 2 — fix `test_cross_cutting_in_by_kind_only`** (currently line 841). Change:
```python
    cross_link = "[[wiki/entities/pkg_pkg-cross|pkg-cross]]"
```
to:
```python
    cross_link = "[[wiki/entities/pkg_pkg-cross|open page]]"
```
(The rest of the test — `text.count(cross_link) == 1`, By-Kind ordering — still holds: pkg-cross is a by-kind package, now rendered as a header + a single `open page` link.)

**Edit 3 — fix `test_app_zero_domain_renders_in_by_kind_apps_first`** (currently line 1049). Change:
```python
    assert "[[wiki/entities/app_myapp|myapp]]" in text
```
to:
```python
    assert "#### myapp" in text
    assert "[[wiki/entities/app_myapp|open page]]" in text
```

(Do NOT touch `test_app_single_domain_renders_under_its_domain`, `test_inline_summary_from_entity_page_frontmatter`, `test_internal_dependencies_subsection_distinct_from_dependencies`, `test_generate_index_against_fixture_graph`, or any `## Domains` assertion — those exercise the Domains tree / nested-bullet paths, which use `_entity_bullet` and are intentionally unchanged.)

- [ ] **Step 2: Run the By-Kind tests to verify they fail**

Run: `uv run --package wiki-io pytest tests/test_index_generator.py -k "by_kind or cross_cutting or app_zero_domain" -v`
Expected: FAIL — `#### pkg-cross` / `|open page]]` not yet emitted; `cross_link` count is 0 with the new label.

- [ ] **Step 3: Add an optional `label` to `_entity_wikilink`**

In `packages/wiki-io/src/wiki_io/index_generator.py`, change `_entity_wikilink` (lines 549-565). Update the signature and the final return; leave the docstring and `stem` derivation as-is:

```python
def _entity_wikilink(
    entity: PlacedEntity, collision_set: frozenset[str], label: str | None = None
) -> str:
    """Forward-derive the piped `[[wiki/entities/<stem>|<text>]]` wikilink.

    Phase 53 D-05: uses `short_filename` from Phase 52 with the precomputed
    collision_set so the index agrees with `write_entities` on filenames
    (including the `__<6hex>` disambiguator for colliders).

    Phase 57 IDX-02/D-05: the link is PIPED with display text = `entity.name`
    (human-readable) — the bare stem is the link target, not the visible text.
    `label` overrides the display text (e.g. "open page") when the entity name
    already lives in a `####` header above the link (Item 2 / By-Kind).
    """
    stem = _short_filename(
        entity.uri,
        collision_set,
        suite_kind=entity.suite_kind,
        pkg_for_suite=entity.pkg_for_suite,
    )
    text = label if label is not None else entity.name
    return f"[[wiki/entities/{stem}|{text}]]"
```

(`_entity_bullet` calls `_entity_wikilink(entity, collision_set)` with no label, so its behavior — and the Domains tree / nested sub-lists — is unchanged.)

- [ ] **Step 4: Rewrite the per-entity loop in `_render_by_kind`**

In the same file, in `_render_by_kind`, replace the per-entity loop body (lines 762-770, from `for e in group:` through the `_render_pkg_nested(...)` call) with:

```python
        for e in group:
            lines.append(f"#### {e.name}")
            lines.append("")
            link = _entity_wikilink(e, collision_set, label="open page")
            summary = f"{e.summary} — " if e.summary else ""
            lines.append(f"{summary}{link}")
            total += 1
            if e.kind in ("package", "app"):
                lines.extend(
                    _render_pkg_nested(
                        conn, e, sub_for_pkg, name_to_entity, collision_set
                    )
                )
            lines.append("")
```

(The `lines.append(f"### {KIND_LABELS[kind]}")` H3 header above this loop, the `lines.append("")` after the group, and `BY_KIND_ORDER` iteration are all unchanged. The nested sub-lists follow the `open page` link line directly — a CommonMark bullet list validly interrupts the preceding paragraph.)

- [ ] **Step 5: Run the By-Kind tests to verify they pass**

Run: `uv run --package wiki-io pytest tests/test_index_generator.py -k "by_kind or cross_cutting or app_zero_domain" -v`
Expected: PASS.

- [ ] **Step 6: Run the full index-generator suite (regression guard for Domains / summaries / internal-deps)**

Run: `uv run --package wiki-io pytest tests/test_index_generator.py -q`
Expected: PASS. The `## Domains`, inline-summary, and internal-dependency tests must stay green (they use the unchanged `_entity_bullet` path). The live-graph snapshot test stays skipped (no `.graph-wiki/graph.db` above the test file).

- [ ] **Step 7: Commit**

```bash
git add packages/wiki-io/src/wiki_io/index_generator.py packages/wiki-io/tests/test_index_generator.py
git commit -m "feat(index): per-entity #### headers in By Kind section

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

---

## Task 4: Item 3 — `updated` frontmatter instruction (confirmation, no code change)

**Files:** none modified. This task is a verification, not an implementation — there is nothing to build. It exists so the executor records that the `updated:` instruction was deliberately left alone.

- [ ] **Step 1: Confirm the three consumption sites still exist**

Run:
```bash
cd /Users/pat/Personal/agent-research
grep -n "Update \`updated:\` frontmatter" packages/workspace-io/src/workspace_io/assets/CLAUDE.md.template
grep -n "updated" packages/graph-wiki-core/src/graph_wiki_core/commands/lint.py | head
grep -rn "updated" packages/wiki-io/src/wiki_io/assets/page-templates/ | head
```
Expected: the template instruction is present; `lint.py` reads `updated` for stale-page flagging; the page templates carry an `updated:` placeholder. This confirms the instruction is **not** stale.

- [ ] **Step 2: Record the decision — no change**

Per the spec (§3.2), leave the instruction, its templates, and lint's use of it untouched. No edit, no commit for this item. (Entity pages track freshness via `last_updated_commit` from Item 1, not `updated`; that asymmetry is known and accepted.)

---

## Final verification

- [ ] **Step 1: Lint + format the touched files**

Run: `uv run ruff check packages/wiki-io packages/graph-wiki-core && uv run ruff format packages/wiki-io packages/graph-wiki-core`
Expected: no lint errors. (Note from project memory: avoid reformatting pre-existing multi-line style unrelated to your edits — `ruff format` line-length differs per package; match the surrounding style and only keep formatting changes that touch your new code.)

- [ ] **Step 2: Run both affected package suites**

Run:
```bash
uv run --package wiki-io pytest -q
uv run --package graph-wiki-core pytest -q
```
Expected: PASS (integration/eval tests skipped by default).

- [ ] **Step 3: (Optional) Brand gate**

Run: `bash scripts/check-brand.sh`
Expected: PASS (no new code added stray upstream names; this plan introduces none).

---

## Self-review notes

- **Spec coverage:** Item 1 §1.2 D1 → Task 1 (`short_commit`, tolerant fallback, canonical via `git rev-parse --short`); D1 single-site change + D-inheritance of `drift_checked_commit`/`detected_commit` via `anchor` → Task 2 (the `anchor`-derived keys need no edit, confirmed in Background). D2 (leave graph DB `last_indexed_commit` full) and D3 (no migration) → respected, no task. Item 2 §2.2 D4 (`####` header replaces bullet in `_render_by_kind` only, `open page` link, summary on the line beneath, `_render_pkg_nested` reused) → Task 3; D5 scope guard (no change to Domains / `_entity_bullet` / ordering / `BY_KIND_ORDER`) → respected, asserted by the unchanged Domains tests. Item 3 → Task 4 (confirmation only).
- **Tests cover both 1.3 cases:** unit (`short_commit` prefix/length/round-trip + failure paths) and integration (scan stamps the short form, still git-resolvable). Item 2's 2.3 list (header + `open page` line present, old name bullet gone, nested sub-lists still present, Domains unchanged) is covered by the augmented `test_by_kind_section_order` plus the unchanged Domains/internal-dep/summary tests left intact.
- **Type/name consistency:** `short_commit(repo: Path, sha: str) -> str` used identically in Task 1 and the Task 2 import; `_entity_wikilink(entity, collision_set, label=None)` — the only new call passes `label="open page"`, all existing calls (in `_entity_bullet`) omit it and keep prior behavior.

---

## Execution Handoff

**Plan complete and saved to `docs/superpowers/plans/2026-06-04-wiki-polish-short-hashes-index-headers.md`. Two execution options:**

**1. Subagent-Driven (recommended)** — I dispatch a fresh subagent per task, review between tasks, fast iteration.

**2. Inline Execution** — Execute tasks in this session using executing-plans, batch execution with checkpoints.

**Which approach?**
