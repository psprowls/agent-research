# Wikilink Base — Part 2: Flip the Producers to the Wiki Root — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make every *producer* of vault wikilinks emit the wiki-root-relative form (`[[concepts/foo]]`, `[[entities/pkg_bar]]`, `[[work/baz]]`) instead of the legacy workspace-root form (`[[wiki/concepts/foo]]`), closing the producer/consumer mismatch Part 1 opened; and correct the dead-category placeholders (`[[packages/…]]`, `[[domains/…]]`, `[[dependencies/…]]`) to the current `entities/` layout.

**Architecture:** Introduce one shared link helper (`wiki_io/wikilinks.py::vault_wikilink`) and route the three duplicate link builders through it; then phase the migration by subsystem (generators → page-templates → fixtures → prompts/agent-docs), keeping each affected package's test suite green at the end of every phase.

**Tech Stack:** Python 3.11, `uv` workspace, pytest (per-package `testpaths`), syrupy `.ambr` snapshots, ruff (line-length 120).

---

## Source spec

`docs/superpowers/specs/2026-06-05-wikilink-base-part2-producers-design.md` (committed `31fd6ded`). Read it for the full rationale. This plan implements it with four decisions made during planning that **deviate from or sharpen the spec** — read these first:

### Planning decisions (override the spec where they conflict)

1. **Phase 2 e2e green-gate is left as-is (user decision: "minimal flip, leave test").**
   `packages/wiki-io/tests/test_bootstrap_e2e_no_broken_links.py` is a **zombie test**: it renders `package/app/plugin` *container overview templates that no longer exist* (the `page-templates/` dir is now flat with `entity-*.md` templates), so `render_template` prints `[warn] template missing`, writes no overview pages, and its broken-link filter (`src.startswith("wiki/packages/test-pkg")`) matches nothing. It passes in ~0.09s asserting nothing. **Do not rewrite or delete it in this plan.** The real green-gate for the producer flip is the **grep guard** (zero `\[\[wiki/` / `f"wiki/` emission hits in `packages/*/src`) plus per-package suites. (A future effort may rebuild this test against the real index generator.)

2. **`project_context.py` is left untouched (user decision: "leave as-is").**
   Its `## Project style (wiki/<filename> §Style)` strings are heading-text labels naming where the schema file physically lives (`<workspace>/wiki/CLAUDE.md`) — **not** Obsidian `[[…]]` wikilinks. No edit; **`test_project_context.ambr` is NOT regenerated.**

3. **L3 agent templates get a FULL layout refresh (user decision: "full L3 layout refresh").**
   These templates do **not** contain `[[wiki/…]]` (that was cleaned up earlier). Their actual staleness is *layout narrative*: "Obsidian opens at the workspace root," `work/` drawn as a `../work/` sibling, and ASCII trees showing the dead `packages/`/`domains/`/`overview.md` container world. Phase 4 rewrites the layout-bearing sections to the current reality — **Obsidian opens at the wiki root (`<workspace>/wiki/`), `work/` lives under the wiki, `entities/` is the flat entity layout, `raw/` is a workspace sibling read at `../raw/`** — across both CLAUDE/AGENTS templates, cursorrules, index/log templates, the workspace-io CLAUDE template, and `init_vault.py`'s runtime next-step text. This intentionally pulls some Tier-B-flavored layout-doc work into Part 2, by user request.

4. **Tier-B container tests are NOT force-migrated.** The spec's L5 list over-includes. These files reference `wiki/...` as **container file-paths**, not the `[[wiki/...]]` wikilink form, and belong to `sync_wiki.py`'s container layout (Tier B, out of scope per spec Wrinkle 3):
   - `packages/graph-io/tests/test_sync_wiki.py` — `_make_overview(workspace, "wiki/packages/alpha/alpha.md")` (file paths, in-test).
   - `packages/graph-wiki-cli/tests/graph_cli/test_cli_sync_wiki.py` — `graph-wiki/wiki/packages/demo/demo.md` (file paths).
   - `packages/wiki-io/tests/test_lint_scanner_heading.py` — builds `wiki/<container>/<slug>/...` link sources **in-test** (HYGIENE container sub-page model).
   **Leave all three untouched.** They build their own paths in tmp dirs and do not read the swept shared fixtures, so the Phase 3 sweep cannot break them. Verify they stay green; if any breaks, that signals a Tier-B entanglement to **flag, not force-fix**.
   Also **`test_entity_writer.py:324`** (`"path": "wiki/entities/…md"`) is incidental data in a deletions-log round-trip test — the test never asserts on that field. **No edit.**

### Ground-truth facts confirmed during planning (use these in the L3 rewrite)

- `workspace_io.paths.work_dir(ws)` returns `wiki_dir(ws) / "work"` — **`work/` is under the wiki.** (`packages/workspace-io/src/workspace_io/paths.py:23`, comment: "work/ lives UNDER the wiki so `[[work/foo]]` resolves against the wiki root identically to `[[concepts/foo]]`".)
- `raw/` is a workspace sibling: `init_vault.py:121` creates `<workspace>/raw`.
- Entity filename slugs come from `entity_writer.short_filename` → `<prefix>_<name>` with the prefix map `entity_writer.py:148`: `repo→repo, pkg→pkg, app→app, domain→domain, agent_plugin→agent-plugin, dependency→dep, test_suite→tests`. Examples: `pkg_subagent-runtime`, `dep_boto3`, `domain_billing`.

---

## File structure

**New file:**
- `packages/wiki-io/src/wiki_io/wikilinks.py` — the single `vault_wikilink(rel_path, text=None)` helper. One responsibility: render a vault-relative wikilink with no `wiki/` prefix.
- `packages/wiki-io/tests/test_wikilinks.py` — unit tests for the helper.

**Modified (by phase):**
- Phase 1: `wiki_io/update_index.py`, `wiki_io/index_generator.py`, `wiki-io/tests/test_index_generator.py`.
- Phase 2: `wiki_io/assets/page-templates/{index,concept,dependency,architecture,concept-pattern,entity-domain,adr}.md`.
- Phase 3: ~134 fixture pages under `wiki-io/tests/fixtures/{round-trip-vault,edge-case-vault,single-package-vault}` and `eval-harness/tests/fixtures/post-rebrand-vault`; 2 self-referential fixture docs (rewritten); `wiki-io/tests/test_wikilink_predicate.py`; targeted graph-wiki-core lint tests **iff** they break.
- Phase 4: `graph_wiki_core/prompts/synthesizer.py`, `prompts/sources/synthesizer.md`, `commands/query.py`; `graph-wiki-core/tests/unit/test_query_result.py`; `wiki_io/graph_analyzer.py`, `eval_harness/divergence/librarian.py` (+ `eval_harness/structural.py`); `wiki_io/assets/{CLAUDE.md.template,AGENTS.md.template,cursorrules.template,index.md.template,log.md.template}`; `workspace_io/assets/CLAUDE.md.template`; `wiki_io/init_vault.py`; regenerate `graph-wiki-core/tests/prompts/__snapshots__/test_prompt_snapshots.ambr`.

---

## Worktree setup (do this once before Task 1)

This is a git worktree. Bare `python` imports the parent repo's `src` (the `.pth` points at the parent). **Always use the worktree's own interpreter.**

- [ ] **Step 0: Sync the worktree venv and confirm the interpreter**

Run:
```bash
cd /Users/pat/Personal/agent-research/.claude/worktrees/wikilink-base-wiki-root
uv sync
ls .venv/bin/python
```
Expected: `.venv/bin/python` exists. Use `.venv/bin/python -m pytest …` OR `uv run --package <pkg> pytest …` for every test run below (both resolve to the worktree venv).

- [ ] **Step 0b: Capture the baseline grep guard (should be NON-zero now)**

Run:
```bash
grep -rn '\[\[wiki/\|f"wiki/\|f"\[\[wiki/' packages/*/src | sort
```
Expected (baseline, ~10 hits): `index_generator.py` (3), `update_index.py` (2), `graph_analyzer.py` (1), `synthesizer.py` (2), `query.py` (2), `synthesizer.md` (5), `page-templates/index.md` (1). This is the set Phases 1/2/4 must drive to **zero**.

- [ ] **Step 0c: Capture baseline ruff counts on files this plan touches** (for the no-new-errors gate at the end)

Run:
```bash
uv run ruff check packages/wiki-io/src packages/graph-wiki-core/src packages/eval-harness/src 2>&1 | tail -3
```
Note the error count. Per repo convention the src tree is pre-existing format-dirty; **never run `ruff format` or `ruff --fix`** — match surrounding style by hand. The gate is "no *new* errors on touched files," compared against this baseline.

---

## Phase 1 — Link helper + generators

**Goal:** one `vault_wikilink` helper; both `_entry_link` duplicates deleted and routed through it; `_entity_wikilink` and the sub-index emitter route through it; generator unit tests updated. End green on the wiki-io generator suite.

### Task 1: The `vault_wikilink` helper

**Files:**
- Create: `packages/wiki-io/src/wiki_io/wikilinks.py`
- Test: `packages/wiki-io/tests/test_wikilinks.py`

- [ ] **Step 1: Write the failing test**

Create `packages/wiki-io/tests/test_wikilinks.py`:
```python
"""Unit tests for vault_wikilink — the single vault-relative wikilink builder."""

from __future__ import annotations

import pytest

from wiki_io.wikilinks import vault_wikilink


def test_bare_link_no_text():
    assert vault_wikilink("concepts/foo") == "[[concepts/foo]]"


def test_piped_link_with_text():
    assert vault_wikilink("concepts/foo", "Foo") == "[[concepts/foo|Foo]]"


def test_strips_trailing_md():
    assert vault_wikilink("concepts/foo.md", "Foo") == "[[concepts/foo|Foo]]"


def test_entities_path():
    assert vault_wikilink("entities/pkg_subagent-runtime", "subagent-runtime") == (
        "[[entities/pkg_subagent-runtime|subagent-runtime]]"
    )


def test_work_path_passes_through_unprefixed():
    # work/ lives under the wiki now — no special-casing, same base as any page.
    assert vault_wikilink("work/2026-05-03-foo.md", "Foo") == "[[work/2026-05-03-foo|Foo]]"


def test_forbids_wiki_prefix():
    with pytest.raises(ValueError, match="wiki/"):
        vault_wikilink("wiki/concepts/foo", "Foo")
```

- [ ] **Step 2: Run it to verify it fails**

Run: `uv run --package wiki-io pytest tests/test_wikilinks.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'wiki_io.wikilinks'`.

- [ ] **Step 3: Write the minimal implementation**

Create `packages/wiki-io/src/wiki_io/wikilinks.py`:
```python
"""Single source of truth for vault-relative wikilink rendering.

Every producer of vault wikilinks (index generators, entity-page builders,
prompt examples that are rendered) routes through `vault_wikilink` so the link
form lives in exactly one place. Links are **wiki-root-relative**: the Obsidian
vault opens at `<workspace>/wiki/`, so `[[concepts/foo]]`, `[[entities/pkg_x]]`,
and `[[work/<slug>]]` all resolve against the same base. The legacy `wiki/`
prefix is forbidden — passing one in is a programming error.
"""

from __future__ import annotations


def vault_wikilink(rel_path: str, text: str | None = None) -> str:
    """Render a wiki-root-relative Obsidian wikilink.

    `rel_path` is a vault-relative page path (e.g. ``concepts/foo``,
    ``entities/pkg_x``, ``work/2026-05-03-foo``), with or without a trailing
    ``.md``. Returns ``[[<stem>]]`` or ``[[<stem>|<text>]]``.

    Raises ``ValueError`` if `rel_path` carries a leading ``wiki/`` segment —
    that is the legacy workspace-root form this helper exists to eliminate.
    """
    stem = rel_path[:-3] if rel_path.endswith(".md") else rel_path
    if stem == "wiki" or stem.startswith("wiki/"):
        raise ValueError(
            f"vault_wikilink: refusing leading 'wiki/' segment in {rel_path!r}; "
            "pass a wiki-root-relative path (e.g. 'concepts/foo', 'entities/pkg_x')"
        )
    return f"[[{stem}|{text}]]" if text is not None else f"[[{stem}]]"
```

- [ ] **Step 4: Run the test to verify it passes**

Run: `uv run --package wiki-io pytest tests/test_wikilinks.py -v`
Expected: PASS (6 passed).

- [ ] **Step 5: Commit**

```bash
git add packages/wiki-io/src/wiki_io/wikilinks.py packages/wiki-io/tests/test_wikilinks.py
git commit -m "feat(wiki-io): add vault_wikilink — single wiki-root-relative link builder

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

### Task 2: Route `update_index.py` through the helper

**Files:**
- Modify: `packages/wiki-io/src/wiki_io/update_index.py` (`_entry_link` `:166-176`, callers `:207` & `:265`, sub-index emitter `:214-226`)

- [ ] **Step 1: Delete `_entry_link` and import the helper**

In `packages/wiki-io/src/wiki_io/update_index.py`, add the import near the top (with the other imports). Then **delete** the entire `_entry_link` function (lines 166-176):
```python
def _entry_link(path, title):
    """Build an Obsidian wikilink for a page entry.

    Wiki entries have wiki-relative paths (e.g. "concepts/foo.md") and need
    the "wiki/" prefix because the Obsidian vault opens at the workspace root.
    Work entries are scanned from <workspace>/wiki/work/ and arrive as
    wiki-relative paths (e.g. "work/2026-05-03-foo.md") — no prefix.
    """
    stem = path[:-3] if path.endswith(".md") else path
    target = stem if stem.startswith("work/") else f"wiki/{stem}"
    return f"[[{target}|{title}]]"
```

Add this import alongside the existing imports at the top of the file:
```python
from wiki_io.wikilinks import vault_wikilink
```

- [ ] **Step 2: Update the two `_entry_link` call sites**

At `:207` and `:265`, replace:
```python
            link = _entry_link(e["path"], e["title"])
```
with:
```python
            link = vault_wikilink(e["path"], e["title"])
```
(There are two call sites — one indented inside a loop at ~207, one at ~265. The indentation differs; preserve each call's existing indentation, only swapping `_entry_link(` → `vault_wikilink(`.)

- [ ] **Step 3: Flip the sub-index `more_links` emitter**

Replace the block at `:214-226`:
```python
    # ## More — links to category sub-indexes
    # These categories always appear even at 0 pages (browsing entrypoints).
    # "work" stays conditional — it is a workspace namespace, not a wiki entrypoint.
    _ALWAYS_IN_MORE = {"architecture", "source", "concept", "adr"}
    more_links = []
    for cat, fname in CATEGORY_INDEX_FILES.items():
        entries = pages.get(cat, [])
        if entries or cat in _ALWAYS_IN_MORE:
            label = CATEGORY_LABELS.get(cat, cat.capitalize())
            stem = fname[:-3]  # strip .md
            more_links.append(f"- [[wiki/{stem}]] — {label} ({len(entries)} pages)")
    # Work index lives at <workspace>/work/index.md (sibling of the wiki),
    # so its wikilink is workspace-rooted, not wiki-rooted.
    work_entries = pages.get("work", [])
    if work_entries:
        more_links.append(f"- [[work/index]] — {CATEGORY_LABELS['work']} ({len(work_entries)} pages)")
```
with:
```python
    # ## More — links to category sub-indexes
    # These categories always appear even at 0 pages (browsing entrypoints).
    # "work" stays conditional — it is its own namespace under the wiki.
    _ALWAYS_IN_MORE = {"architecture", "source", "concept", "adr"}
    more_links = []
    for cat, fname in CATEGORY_INDEX_FILES.items():
        entries = pages.get(cat, [])
        if entries or cat in _ALWAYS_IN_MORE:
            label = CATEGORY_LABELS.get(cat, cat.capitalize())
            more_links.append(f"- {vault_wikilink(fname)} — {label} ({len(entries)} pages)")
    # Work index lives under the wiki at work/index.md, so it shares the
    # single wiki-root-relative base with every other page.
    work_entries = pages.get("work", [])
    if work_entries:
        more_links.append(f"- {vault_wikilink('work/index')} — {CATEGORY_LABELS['work']} ({len(work_entries)} pages)")
```
(`vault_wikilink(fname)` handles the `.md` strip; `vault_wikilink('work/index')` yields `[[work/index]]`.)

- [ ] **Step 4: Run the update_index tests**

Run: `uv run --package wiki-io pytest tests/test_update_index_surgical.py -v`
Expected: PASS (this suite asserts only that `update_index` does not write `wiki/index.md`; it has no wikilink-form assertions).

- [ ] **Step 5: Commit**

```bash
git add packages/wiki-io/src/wiki_io/update_index.py
git commit -m "refactor(wiki-io): route update_index links through vault_wikilink (drop wiki/ prefix)

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

### Task 3: Route `index_generator.py` through the helper

**Files:**
- Modify: `packages/wiki-io/src/wiki_io/index_generator.py` (`_entry_link` `:448-457`, `_entity_wikilink` `:551-572`, caller `:795`, `__all__` `:935`)

- [ ] **Step 1: Add the import**

Add to the imports at the top of `packages/wiki-io/src/wiki_io/index_generator.py`:
```python
from wiki_io.wikilinks import vault_wikilink
```

- [ ] **Step 2: Delete `_entry_link` (`:448-457`) and fix its caller**

Delete:
```python
def _entry_link(path: str, title: str) -> str:
    """Port of `update_index.py::_entry_link`.

    Wiki entries (rel paths not starting with `work/`) get a `wiki/` prefix
    so Obsidian (rooted at the workspace) resolves the link. Work entries
    arrive workspace-rooted and pass through.
    """
    stem = path[:-3] if path.endswith(".md") else path
    target = stem if stem.startswith("work/") else f"wiki/{stem}"
    return f"[[{target}|{title}]]"
```
At the caller `:795`, replace:
```python
        link = _entry_link(e["path"], e["title"])
```
with:
```python
        link = vault_wikilink(e["path"], e["title"])
```

- [ ] **Step 3: Flip `_entity_wikilink` to emit the unprefixed form**

In `_entity_wikilink` (`:551-572`), update the docstring's first line and the return statement. Replace the docstring opener:
```python
    """Forward-derive the piped `[[wiki/entities/<stem>|<text>]]` wikilink.
```
with:
```python
    """Forward-derive the piped `[[entities/<stem>|<text>]]` wikilink.
```
And replace the return at `:572`:
```python
    return f"[[wiki/entities/{stem}|{text}]]"
```
with:
```python
    return vault_wikilink(f"entities/{stem}", text)
```

- [ ] **Step 4: Remove `_entry_link` from `__all__`**

At `:935`, delete the `"_entry_link",` entry from the `__all__` list. (Leave `_entity_wikilink` in `__all__` if it is present; only `_entry_link` is being removed.)

- [ ] **Step 5: Run — expect the generator unit tests to FAIL on stale assertions**

Run: `uv run --package wiki-io pytest tests/test_index_generator.py -v`
Expected: FAIL — many assertions still expect `[[wiki/entities/…]]`, and `test_entry_link_wiki_vs_work` imports the now-deleted `_entry_link`. Task 4 fixes the test.

- [ ] **Step 6: Commit (implementation only; test fix is Task 4)**

```bash
git add packages/wiki-io/src/wiki_io/index_generator.py
git commit -m "refactor(wiki-io): route index_generator links through vault_wikilink

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

### Task 4: Update `test_index_generator.py` assertions

**Files:**
- Modify: `packages/wiki-io/tests/test_index_generator.py`

- [ ] **Step 1: Replace the `_entry_link` test with a vault_wikilink import check**

The test imports `_entry_link` from `index_generator` and exercises it at `:108-110`:
```python
    def test_entry_link_wiki_vs_work(self):
        assert _entry_link("work/foo.md", "Foo") == "[[work/foo|Foo]]"
        assert _entry_link("concepts/foo.md", "Foo") == "[[wiki/concepts/foo|Foo]]"
```
Replace that method body with the new canonical form (and route through the helper — the work/-vs-wiki distinction is gone):
```python
    def test_entry_link_wiki_vs_work(self):
        from wiki_io.wikilinks import vault_wikilink

        assert vault_wikilink("work/foo.md", "Foo") == "[[work/foo|Foo]]"
        assert vault_wikilink("concepts/foo.md", "Foo") == "[[concepts/foo|Foo]]"
```
Then find the `_entry_link` import near the top of the file (it is imported from `wiki_io.index_generator`) and remove `_entry_link` from that import list (it no longer exists). If `_entry_link` is the only name on its import line, delete the line; otherwise drop just that name.

- [ ] **Step 2: Strip the `wiki/` prefix from every entity-link assertion**

Replace `[[wiki/entities/` → `[[entities/` throughout the file. These are the assertion lines (verify each exists, then edit):
- `:488` `"[[wiki/entities/pkg_pkg-a|pkg-a]]"` → `"[[entities/pkg_pkg-a|pkg-a]]"`
- `:557` `"[[wiki/entities/pkg_pkg-cross|open page]]"` → `"[[entities/pkg_pkg-cross|open page]]"`
- `:559` `"[[wiki/entities/app_myapp|open page]]"` → `"[[entities/app_myapp|open page]]"`
- `:561` `"[[wiki/entities/agent-plugin_graph-wiki|open page]]"` → `"[[entities/agent-plugin_graph-wiki|open page]]"`
- `:563` `"[[wiki/entities/pkg_pkg-cross|pkg-cross]]" not in text` → `"[[entities/pkg_pkg-cross|pkg-cross]]" not in text`
- `:567` `"[[wiki/entities/dep_boto3|boto3]]"` → `"[[entities/dep_boto3|boto3]]"`
- `:590` `"Cross summary — [[wiki/entities/pkg_pkg-cross|open page]]"` → `"Cross summary — [[entities/pkg_pkg-cross|open page]]"`
- `:633` `text.count("[[wiki/entities/tests_suite|suite]]") == 2` → `text.count("[[entities/tests_suite|suite]]") == 2`
- `:723` `"[[wiki/entities/pkg_pkg-a|pkg-a]]"` → `"[[entities/pkg_pkg-a|pkg-a]]"`
- `:724` `"[[wiki/entities/dep_boto3|boto3]]"` → `"[[entities/dep_boto3|boto3]]"`
- `:874` `cross_link = "[[wiki/entities/pkg_pkg-cross|open page]]"` → `cross_link = "[[entities/pkg_pkg-cross|open page]]"`
- `:957` `"[[wiki/entities/pkg_pkg-solo|pkg-solo]]"` → `"[[entities/pkg_pkg-solo|pkg-solo]]"`
- `:1083` `"[[wiki/entities/app_myapp|open page]]"` → `"[[entities/app_myapp|open page]]"`
- `:1107` `"[[wiki/entities/app_myapp|myapp]]"` → `"[[entities/app_myapp|myapp]]"`
- `:1143` `"[[wiki/entities/dep_boto3|boto3]]"` → `"[[entities/dep_boto3|boto3]]"`
- `:1144` `"[[wiki/entities/pkg_target|target]]"` → `"[[entities/pkg_target|target]]"`
- `:1180` `"[[wiki/entities/pkg_pkg-a|pkg-a]] — Some summary"` → `"[[entities/pkg_pkg-a|pkg-a]] — Some summary"`
- `:1182` `"[[wiki/entities/pkg_pkg-b|pkg-b]]"` → `"[[entities/pkg_pkg-b|pkg-b]]"`
- `:1183` `"[[wiki/entities/pkg_pkg-b|pkg-b]] —" not in text` → `"[[entities/pkg_pkg-b|pkg-b]] —" not in text`

The cleanest way to do all of these at once (these are the only `[[wiki/entities/` occurrences in the file — the lines at `:63`/`:71` are `/tmp/wiki/index.md` filesystem paths and must NOT change):
```bash
sed -i '' 's/\[\[wiki\/entities\//[[entities\//g' packages/wiki-io/tests/test_index_generator.py
```
Then re-grep to confirm `:63` and `:71` (the `/tmp/wiki/index.md` paths) are untouched:
```bash
grep -n 'wiki/' packages/wiki-io/tests/test_index_generator.py
```
Expected remaining `wiki/` hits: only `:63`/`:71` (`/tmp/wiki/index.md`) and `:1000` (the docstring "lanes are sections IN wiki/index.md") and `:1319` (`.graph-wiki/graph.db`) — all filesystem paths, all correct to leave.

- [ ] **Step 3: Run the full generator suite**

Run: `uv run --package wiki-io pytest tests/test_index_generator.py tests/test_wikilinks.py tests/test_update_index_surgical.py -v`
Expected: PASS.

- [ ] **Step 4: Run the whole wiki-io suite to catch collateral** (excluding integration)

Run: `uv run --package wiki-io pytest -m "not integration"`
Expected: the fixture-dependent suites (lint/round-trip) may still fail here — that is Phase 3's job. **Note which tests fail**; they should be only fixture-driven ones (e.g. `test_lint_*`, round-trip). If a *generator/helper* test fails, fix it before committing.

- [ ] **Step 5: Commit**

```bash
git add packages/wiki-io/tests/test_index_generator.py
git commit -m "test(wiki-io): assert unprefixed [[entities/...]] form; test vault_wikilink

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

---

## Phase 2 — Page templates

**Goal:** flip the one `wiki/` prefix in the index page-template and correct the Tier-A dead-category placeholders to the `entities/` layout. (No e2e test change — see Planning decision 1.)

### Task 5: Flip `page-templates/index.md`

**Files:**
- Modify: `packages/wiki-io/src/wiki_io/assets/page-templates/index.md` (`:18`)

- [ ] **Step 1: Strip the `wiki/` prefix**

Replace `:18`:
```
- [[wiki/<path>|<Title>]] — <summary>
```
with:
```
- [[<path>|<Title>]] — <summary>
```

- [ ] **Step 2: Verify no `[[wiki/` remains in page-templates**

Run: `grep -rn '\[\[wiki/' packages/wiki-io/src/wiki_io/assets/page-templates/`
Expected: no output.

### Task 6: Tier-A dead-category fixes in page-templates

**Files:**
- Modify: `concept.md`, `dependency.md`, `architecture.md`, `concept-pattern.md`, `entity-domain.md`, `adr.md` (all under `packages/wiki-io/src/wiki_io/assets/page-templates/`)

Mapping (per `entity_writer.short_filename` prefixes): `packages/<pkg>` → `entities/pkg_<pkg>`, `domains/<domain>` → `entities/domain_<domain>`, `dependencies/<lib>` → `entities/dep_<lib>`.

- [ ] **Step 1: `concept.md`**

- `:26` `- [[packages/<pkg>]] — how it's used there` → `- [[entities/pkg_<pkg>]] — how it's used there`
- `:27` `- [[packages/<pkg>]] — ...` → `- [[entities/pkg_<pkg>]] — ...`
- `:33` `- [[dependencies/<lib>]] — if relevant` → `- [[entities/dep_<lib>]] — if relevant`

- [ ] **Step 2: `dependency.md`**

- `:30` `- [[packages/<pkg>]]` → `- [[entities/pkg_<pkg>]]`
- `:45` `- [[dependencies/<other>]]` → `- [[entities/dep_<other>]]`

- [ ] **Step 3: `architecture.md`**

- `:25` `- [[packages/<pkg>]]` → `- [[entities/pkg_<pkg>]]`
- `:31` `- [[dependencies/<lib>]]` → `- [[entities/dep_<lib>]]`

- [ ] **Step 4: `concept-pattern.md`**

- `:38` `- [[packages/<pkg>]] — current state and how this pattern would apply.` → `- [[entities/pkg_<pkg>]] — current state and how this pattern would apply.`

- [ ] **Step 5: `entity-domain.md`**

- `:25` `> TODO: <One entry per package: ### [[packages/<pkg-slug>/<pkg-slug>|<pkg-slug>]] then two to three sentences on its role in the domain. Keep it concise — the package overview page has the full detail.>`
  → `> TODO: <One entry per package: ### [[entities/pkg_<pkg-slug>|<pkg-slug>]] then two to three sentences on its role in the domain. Keep it concise — the package's entity page has the full detail.>`

- [ ] **Step 6: `adr.md`**

- `:39` `- [[packages/<pkg>]]` → `- [[entities/pkg_<pkg>]]`
- `:40` `- [[domains/<domain>]]` → `- [[entities/domain_<domain>]]`

- [ ] **Step 7: Verify no dead-category placeholders remain in page-templates**

Run:
```bash
grep -rn '\[\[packages/\|\[\[domains/\|\[\[dependencies/\|\[\[apps/\|\[\[agents/' packages/wiki-io/src/wiki_io/assets/page-templates/
```
Expected: no output.

- [ ] **Step 8: Run the wiki-io suite (generator + bootstrap-template tests)**

Run: `uv run --package wiki-io pytest -m "not integration"`
Expected: same fixture-driven failures as end of Phase 1 (Phase 3 fixes them); **no new** failures introduced by the template edits. The zombie e2e test (`test_bootstrap_e2e_no_broken_links`) still passes vacuously — leave it.

- [ ] **Step 9: Commit**

```bash
git add packages/wiki-io/src/wiki_io/assets/page-templates/
git commit -m "fix(templates): wiki-root index link + Tier-A entities/ dead-category placeholders

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

---

## Phase 3 — Fixtures, self-referential docs, and fixture-driven tests

**Goal:** sweep `[[wiki/` → `[[` across the four fixture vaults (preserving `[[work/…]]`, bare stems, and aliases), rewrite the two self-referential docs to describe the new convention, and update the genuinely wikilink-form-asserting tests. End green on the lint/round-trip/eval suites.

> The flip rule strips exactly one leading `wiki/` from each wikilink **target**. `[[work/…]]` never starts with `wiki/`; bare stems (`[[foo]]`) never start with `wiki/`; the alias on the right of `|` is never at the start of a `[[`. So `[[wiki/` → `[[` is a safe, complete rewrite. Code references `` `path:line` `` are untouched (no `[[`).

### Task 7: Mechanical fixture sweep

**Files:**
- Modify: ~134 fixture `.md` files under `packages/wiki-io/tests/fixtures/{round-trip-vault,edge-case-vault,single-package-vault}` and `packages/eval-harness/tests/fixtures/post-rebrand-vault`
- **Exclude** the two self-referential docs (rewritten in Task 8).

- [ ] **Step 1: Run the sweep, excluding the two rewrite-only docs**

Run:
```bash
EXC1="packages/wiki-io/tests/fixtures/round-trip-vault/adrs/0015-workspace-root-wikilink-form.md"
EXC2="packages/wiki-io/tests/fixtures/round-trip-vault/sources/2026-05-workspace-relative-wikilinks-linter-and-content-rewrite.md"
grep -rl '\[\[wiki/' packages/wiki-io/tests/fixtures packages/eval-harness/tests/fixtures \
  | grep -vxF "$EXC1" | grep -vxF "$EXC2" \
  | while IFS= read -r f; do sed -i '' 's/\[\[wiki\//[[/g' "$f"; done
```

- [ ] **Step 2: Verify the sweep — only the two excluded docs still carry `[[wiki/`**

Run: `grep -rl '\[\[wiki/' packages/wiki-io/tests/fixtures packages/eval-harness/tests/fixtures`
Expected: exactly the two excluded paths (`$EXC1`, `$EXC2`) and nothing else.

- [ ] **Step 3: Spot-check that `[[work/…]]` and aliases survived**

Run:
```bash
grep -rn '\[\[work/' packages/wiki-io/tests/fixtures/round-trip-vault | head -3
grep -rn '\[\[\([^]|]*\)|' packages/wiki-io/tests/fixtures/round-trip-vault | head -3
```
Expected: `[[work/…]]` links present and unchanged; aliased links (`[[target|Display]]`) intact with display text preserved.

- [ ] **Step 4: Commit the sweep**

```bash
git add packages/wiki-io/tests/fixtures packages/eval-harness/tests/fixtures
git commit -m "test(fixtures): sweep [[wiki/ -> [[ across the four fixture vaults

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

### Task 8: Rewrite the two self-referential docs

These docs *argue for* the old workspace-root form; a blind sweep makes their prose self-contradictory. Rewrite both to describe the new wiki-root convention, using **swept link forms** (`[[concepts/…]]`, `[[adrs/…]]`, `[[packages/lattice-wiki-core/lattice-wiki-core]]`, `[[work/…]]`) so they stay link-consistent with the rest of the (still container-layout) round-trip fixture. Preserve frontmatter keys so round-trip parsing is unaffected.

**Files:**
- Modify (full rewrite): `packages/wiki-io/tests/fixtures/round-trip-vault/adrs/0015-workspace-root-wikilink-form.md`
- Modify (full rewrite): `packages/wiki-io/tests/fixtures/round-trip-vault/sources/2026-05-workspace-relative-wikilinks-linter-and-content-rewrite.md`

- [ ] **Step 1: Rewrite ADR-0015**

Overwrite `packages/wiki-io/tests/fixtures/round-trip-vault/adrs/0015-workspace-root-wikilink-form.md` with:
```markdown
---
title: "ADR-0015: Wiki-root-relative wikilink form"
category: adr
summary: Wikilinks in the lattice vault are wiki-root-relative — `[[concepts/...]]`, `[[adrs/...]]`, `[[packages/...]]`, and `[[work/<slug>]]` are canonical; the `[[wiki/...]]` prefix and `[[../work/...]]` are forbidden. Obsidian opens at `<workspace>/wiki/` and work/ lives under the wiki.
adr_id: "0015"
status: accepted
decision_date: 2026-05-09
deciders: ["@psprowls"]
supersedes: []
superseded_by:
tags: [wiki, obsidian, wikilinks, layout, conventions]
updated: 2026-06-05
tokens: 1519
---

# ADR-0015: Wiki-root-relative wikilink form

**Status:** accepted (2026-05-09; convention revised 2026-06-05)

## Context

Obsidian opens the vault at the **wiki root** (`<workspace>/wiki/`), and resolves
every wikilink relative to it. Work items live under the wiki at `work/`, so
`[[work/<slug>]]` resolves against the same base as `[[concepts/...]]`. The
immutable `raw/` sources sit beside the vault as a workspace sibling, reached on
disk at `../raw/` and never wikilinked.

Earlier schema docs and live content used two non-canonical forms:

1. `[[../work/<slug>]]` — Obsidian does not support relative-to-current-page
   wikilinks; the `../` prefix escapes the vault and never resolves.
2. `[[wiki/packages/foo/foo]]` — the legacy workspace-root form, which only
   resolved when Obsidian opened one level up at `<workspace>/`. Now that the
   vault opens at the wiki root, the `wiki/` segment points nowhere.

## Decision

All wikilinks in the lattice vault are **wiki-root-relative**. Canonical forms:

| Target | Canonical form |
|---|---|
| Work item | `[[work/<slug>]]` |
| Wiki page (any category) | `[[<category>/<path>]]` — e.g. `[[packages/foo/foo]]`, `[[concepts/bar]]`, `[[adrs/0011-single-workspace-root]]` |
| Folder shorthand | `[[packages/foo]]` resolves to `packages/foo/foo.md` |
| Stem shorthand | `[[foo]]` resolved via the linter's `stems` dict |
| Aliased | `[[foo|Display Text]]` — alias preserved on the right of the `|` |

==Forbidden:== the `[[wiki/...]]` prefix and `[[../work/...]]` / `[[../<anything>]]`.

Companion enforcement:
- The linter ([[packages/lattice-wiki-core/lattice-wiki-core]] `lint_wiki.py`) walks the
  wiki root and keys pages wiki-relative, so the canonical forms resolve and the
  forbidden forms are flagged as broken links.
- Schema docs and page templates lead by example with the wiki-root forms.

## Consequences

**Positive:**
- A single link base across every category — work items, entities, concepts,
  ADRs all resolve the same way.
- Obsidian's graph view and backlinks panel work for every link.
- The deprecated `[[wiki/...]]` and `[[../work/...]]` forms become regression
  guards — any reintroduction is flagged as a broken link.

**Negative:**
- Existing content carried the old `[[wiki/...]]` form and required a one-shot
  sweep (specified in [[sources/2026-05-workspace-relative-wikilinks-linter-and-content-rewrite]]).
- Authors writing by hand must use wiki-root paths; tooling and templates lead
  by example.

## Alternatives considered

- **Open Obsidian at `<workspace>/` and keep the `[[wiki/...]]` prefix** —
  rejected: that buries the vault's own pages one level down and leaves `raw/`
  (immutable, never linked) cluttering the graph. Opening at the wiki root gives
  one clean link base.
- **Auto-rewrite forbidden forms at lint time** — rejected for v1: a lint-time
  regex risks masking real authoring intent. Flagging as broken surfaces
  violations explicitly.

## Impact

- [[packages/lattice-wiki-core/lattice-wiki-core]] — `lint_wiki.py` walks the wiki root and keys pages wiki-relative.
- [[plugins/lattice-wiki/lattice-wiki]] — schema docs and page templates document the canonical forms.
- [[plugins/lattice-work/lattice-work]] — work items live under the wiki and are linted by the wiki-root walk; exempt from orphan detection.
- [[concepts/lattice-vault-terminology]] — vault-terminology reflects the wiki-root-as-vault model.
- [[concepts/per-repo-layout]] — wikilink form follows from the layout shape.

## Follow-ups

- After landing, run `grep -r '\[\[wiki/' lattice/wiki/` and confirm zero results.
- Watch for new authoring drift; consider a `--check-canonical-form` lint flag if drift recurs.
```

- [ ] **Step 2: Rewrite the source spec**

Overwrite `packages/wiki-io/tests/fixtures/round-trip-vault/sources/2026-05-workspace-relative-wikilinks-linter-and-content-rewrite.md` with:
```markdown
---
title: "Wiki-root-relative wikilinks — linter and content rewrite"
category: source
summary: Approved design aligning the lint_wiki.py walker and all wiki content with the wiki-root vault base — wikilinks become wiki-root-relative ([[work/...]] and [[concepts/...]]), the linter walks the wiki root and keys pages wiki-relative, and a sweep rewrites the legacy [[wiki/...]] prefix out of the existing vault.
source_path: lattice/specs/2026-05-09-lattice-wiki-root-wikilinks-design.md
source_type: spec
source_date: 2026-05-09
authors: ["@psprowls"]
ingested: 2026-05-09
updated: 2026-06-05
tokens: 1790
---

# Wiki-root-relative wikilinks — linter and content rewrite

## TL;DR
Obsidian opens the vault at the wiki root (`<workspace>/wiki/`), so wikilinks are
wiki-root-relative — `[[work/<slug>]]`, `[[concepts/...]]`, `[[packages/...]]` —
not `[[wiki/...]]` or `[[../work/...]]`. The spec aligns the linter (walk the wiki
root, key pages wiki-relative, work items live under the wiki) and the existing
content (a one-pass sweep of the legacy `wiki/` prefix) with this reality.

## Key claims
1. The legacy `[[wiki/...]]` prefix only resolved when Obsidian opened at
   `<workspace>/`. Opening at the wiki root makes `[[concepts/...]]`,
   `[[packages/...]]`, and `[[work/...]]` share one link base.
2. **Linter fix:** `lint_wiki.py` walks the wiki root and keys pages
   wiki-relative (e.g. `concepts/foo`, `packages/foo/foo`, `work/2026-05-09-foo`).
3. **Work items live under the wiki** at `work/`, so they are linted by the
   wiki-root walk and `[[work/<slug>]]` resolves like any other page. Work pages
   are exempt from orphan detection — they legitimately exist without backlinks.
4. **Wikilink resolution is unchanged in logic** — it now operates on
   wiki-relative keys, so `[[packages/foo/foo]]`, `[[work/2026-05-09-fix]]`,
   folder-shorthand `[[packages/foo]]`, and stem-shorthand `[[foo]]` all resolve.
5. **Content rewrite is a single sweep** over every `*.md` in the vault:
   `\[\[wiki/` → `[[`. Aliases (`[[foo|Display Text]]`) are preserved; `[[work/...]]`
   and bare stems are never touched (they never start with `wiki/`).
6. **Schema doc edits:** templates and `CLAUDE.md`/`AGENTS.md` document
   `[[work/<slug>]]` and `[[<category>/...]]` as canonical and drop the `wiki/`
   prefix and the `../work/` form.

## Proposed changes
- `lint_wiki.py` — walk the wiki root; key pages wiki-relative; work items under the wiki.
- page templates — wikilink examples use the wiki-root form.
- All `*.md` under the vault — one-pass `\[\[wiki/` → `[[` sweep.

## Acceptance criteria
- `grep -r '\[\[wiki/' lattice/wiki/` returns zero results.
- The linter reports zero broken links for the canonical forms.
- Schema docs document `[[work/<slug>]]` and `[[<category>/...]]` as canonical.

## Touches
- [[concepts/lattice-vault-terminology]]
- [[concepts/per-repo-layout]]
- [[concepts/lattice-work-namespace-schema]]
- [[packages/lattice-wiki-core/lattice-wiki-core]]
- [[plugins/lattice-wiki/lattice-wiki]]
- [[plugins/lattice-work/lattice-work]]

## Decisions triggered
- [[adrs/0015-workspace-root-wikilink-form]]

## Closes
- [[work/2026-05-09-fix-vault-rooted-wikilinks]]
- [[work/2026-05-09-adjust-linter-for-work-sibling-to-vault]]

## Where it's cited in this wiki
- [[adrs/0015-workspace-root-wikilink-form]]
- [[concepts/lattice-vault-terminology]]
- [[concepts/per-repo-layout]]
- [[packages/lattice-wiki-core/lattice-wiki-core]]
- [[plugins/lattice-wiki/lattice-wiki]]
- [[plugins/lattice-work/lattice-work]]
```

> Note on the `deciders:`/`authors:` change to `["@psprowls"]`: the original used the unquoted `[Patrick Sprowls]`. The quoted `@handle` form matches the project's page-format convention and avoids the YAML `@`-indicator parse failure noted in project memory. If the round-trip test pins the exact `deciders:` string, keep whatever value makes it pass — the link sweep is what matters, not the author field.

- [ ] **Step 3: Run the round-trip suite**

Run: `uv run --package wiki-io pytest -k "round_trip or roundtrip or lint" -m "not integration" -v`
Expected: PASS. If a round-trip test compares byte-for-byte against a stored expected output that itself contained `[[wiki/...]]`, that expected file was swept in Task 7 and should now match. If a test fails on the rewritten docs' *prose*, inspect what it asserts — round-trip tests should assert structure/links, not prose; if it pins prose, adjust the rewrite minimally to satisfy it while keeping the new convention.

- [ ] **Step 4: Commit**

```bash
git add packages/wiki-io/tests/fixtures/round-trip-vault/adrs/0015-workspace-root-wikilink-form.md \
        packages/wiki-io/tests/fixtures/round-trip-vault/sources/2026-05-workspace-relative-wikilinks-linter-and-content-rewrite.md
git commit -m "test(fixtures): rewrite the two self-referential docs for the wiki-root convention

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

### Task 9: Update `test_wikilink_predicate.py`

**Files:**
- Modify: `packages/wiki-io/tests/test_wikilink_predicate.py`

The placeholder predicate and `WIKILINK_RE` don't depend on the `wiki/` prefix, but the sample inputs should model the current convention.

- [ ] **Step 1: Drop the `wiki/` prefix from the sample targets**

- `:19` `self.assertTrue(_is_placeholder_target("wiki/packages/..."))` → `self.assertTrue(_is_placeholder_target("entities/..."))`
- `:21` `self.assertTrue(_is_placeholder_target("wiki/..."))` → delete this line (the bare `[[...]]`-with-no-category placeholder is already covered by `:20`'s `"..."`); **or** replace with `self.assertTrue(_is_placeholder_target("concepts/..."))`. Use the replacement form to keep the count.
- `:25` `self.assertTrue(_is_placeholder_target("wiki/<package>"))` → `self.assertTrue(_is_placeholder_target("entities/<package>"))`
- `:28` `self.assertTrue(_is_placeholder_target("wiki/adrs/<adr_id>"))` → `self.assertTrue(_is_placeholder_target("adrs/<adr_id>"))`
- `:32` `self.assertFalse(_is_placeholder_target("wiki/adrs/index"))` → `self.assertFalse(_is_placeholder_target("adrs/index"))`
- `:33` `self.assertFalse(_is_placeholder_target("wiki/packages/foo"))` → `self.assertFalse(_is_placeholder_target("entities/pkg_foo"))`
- `:35` `self.assertFalse(_is_placeholder_target("wiki/domains/bar"))` → `self.assertFalse(_is_placeholder_target("entities/domain_bar"))`

- [ ] **Step 2: Update the `WIKILINK_RE` table-cell test target**

- `:66-69`:
```python
        self.assertEqual(
            self._target(r"[[wiki/concepts/orchestrator-agent-anatomy\|orchestrator]]"),
            "wiki/concepts/orchestrator-agent-anatomy",
        )
```
→
```python
        self.assertEqual(
            self._target(r"[[concepts/orchestrator-agent-anatomy\|orchestrator]]"),
            "concepts/orchestrator-agent-anatomy",
        )
```

- [ ] **Step 3: Run it**

Run: `uv run --package wiki-io pytest tests/test_wikilink_predicate.py -v`
Expected: PASS.

- [ ] **Step 4: Run the full wiki-io suite — expect fully green now**

Run: `uv run --package wiki-io pytest -m "not integration"`
Expected: PASS (all of wiki-io). If anything still fails, it is either (a) a genuine wikilink-form test not yet updated — fix it; or (b) `test_lint_scanner_heading.py` (Tier-B container model, Planning decision 4) — if *that* fails, do **not** force-fix; capture the failure and flag it as a Tier-B entanglement in the final report.

- [ ] **Step 5: Commit**

```bash
git add packages/wiki-io/tests/test_wikilink_predicate.py
git commit -m "test(wiki-io): model wiki-root forms in wikilink-predicate samples

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

### Task 10: Eval-harness + graph-io / graph-wiki-core fixture-driven suites

**Files:**
- Run/verify: `packages/eval-harness`, `packages/graph-io`, `packages/graph-wiki-cli`, `packages/graph-wiki-core` test suites. Edit **only** the tests that break on the swept fixtures and that assert the wikilink *form* (not container file-paths).

- [ ] **Step 1: Run eval-harness (post-rebrand-vault was swept)**

Run: `uv run --package eval-harness pytest -m "not integration"`
Expected: PASS. `test_divergence_checks.py:483` builds its input string in-test (`"See [[wiki/bedrock]] and [[packages/foo|alias]]."`) — that is a *test input*, not a fixture; it exercises the divergence regex. If it fails, inspect whether the divergence check's expected output changed; only then edit. The `_GRAPH_WIKI_PREFIX_RE` tests (`:496-506`) are about `.graph-wiki/` paths, unrelated — leave them.

- [ ] **Step 2: Run graph-io and graph-wiki-cli**

Run:
```bash
uv run --package graph-io pytest -m "not integration"
uv run --package graph-wiki-cli pytest -m "not integration"
```
Expected: PASS **without edits.** `test_sync_wiki.py` and `test_cli_sync_wiki.py` use `wiki/packages/...` as container file-paths for `sync_wiki.py` (Tier B, Planning decision 4) and build them in-test — the fixture sweep does not touch them. If either fails, it is a pre-existing/Tier-B issue: capture and flag, do not migrate.

- [ ] **Step 3: Run graph-wiki-core (lint/parity/provenance) — prompts come in Phase 4**

Run: `uv run --package graph-wiki-core pytest -m "not integration"`
Expected: the **prompt** tests (`test_query_result.py::test_synthesizer_prompt_requires_full_wikilink_paths`) still pass here because the prompt is unchanged until Phase 4. The lint tests (`test_commands_lint.py`, `test_lint_parity.py`) use `[[wiki/...]]` strings as *placeholder examples containing `...`* — placeholder detection keys off `...`, not the prefix, so they should still pass. `test_provenance.py`'s `wiki/packages/` references are repo-tree vocabulary, unrelated. **If any lint test fails**, it asserts the literal `wiki/` form in resolved output — update that single assertion to the wiki-root form and note it. Otherwise, no edits.

- [ ] **Step 4: Commit (only if Step 1–3 required edits)**

```bash
git add -A
git commit -m "test: align fixture-driven suites with the wiki-root link sweep

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```
(If no edits were needed, skip the commit and note "no changes required" in the task report.)

---

## Phase 4 — Prompts, agent templates, misc emitters, Obsidian wording

**Goal:** flip the `[[wiki/…]]` forms (and fix stale categories) in the L2 prompts; rewrite the L3 agent-template layout narrative to the wiki-root world (full refresh, Planning decision 3); fix the L4 comments; update the synthesizer prompt test and regenerate the prompt snapshot. End with the grep guard at zero and graph-wiki-core prompts green.

### Task 11: L2 prompts — synthesizer + query

**Files:**
- Modify: `packages/graph-wiki-core/src/graph_wiki_core/prompts/synthesizer.py` (`:11`, `:17`)
- Modify: `packages/graph-wiki-core/src/graph_wiki_core/prompts/sources/synthesizer.md` (`:3`, `:33`, `:41`, `:54`, `:60`)
- Modify: `packages/graph-wiki-core/src/graph_wiki_core/commands/query.py` (`:633`, `:648`)

Concrete example mapping (use real entity slugs so the prompt teaches the right form): `wiki/packages/subagent-runtime/subagent-runtime` → `entities/pkg_subagent-runtime`; `wiki/agents/graph-wiki-core/commands/query` → `entities/agent-plugin_graph-wiki`; `wiki/packages/foo/foo` → `entities/pkg_foo`; generic `[[wiki/...]]` → `[[entities/...]]`.

- [ ] **Step 1: `synthesizer.py`**

`:11` — replace:
```
- Cite vault pages using the **full page-path form** that appears in the excerpts, for example `[[wiki/packages/subagent-runtime/subagent-runtime]]` or `[[wiki/agents/graph-wiki-core/commands/query]]`. Never collapse a wikilink to a slug-only form such as `[[SubagentPool]]` or `[[Bedrock]]`. Slug-only wikilinks are forbidden — they do not resolve against the vault.
```
with:
```
- Cite vault pages using the **full page-path form** that appears in the excerpts, for example `[[entities/pkg_subagent-runtime]]` or `[[entities/agent-plugin_graph-wiki]]`. Never collapse a wikilink to a slug-only form such as `[[SubagentPool]]` or `[[Bedrock]]`. Slug-only wikilinks are forbidden — they do not resolve against the vault.
```
`:17` — replace `` `[[wiki/...]]` wikilinks for vault pages `` with `` `[[entities/...]]` wikilinks for vault pages ``. (Full line: `2. **Supporting detail** — organized thematically, weaving in inline citations: `[[entities/...]]` wikilinks for vault pages and `` `path:line` `` backtick-wrapped references for code locations.`)

- [ ] **Step 2: `synthesizer.md`**

- `:3` `Enforces full-path [[wiki/...]] wikilinks,` → `Enforces full-path [[entities/...]] wikilinks,`
- `:33` `weaving inline citations: `[[wiki/...]]` wikilinks for vault pages` → `weaving inline citations: `[[entities/...]]` wikilinks for vault pages`
- `:41` `for example `[[wiki/packages/subagent-runtime/subagent-runtime]]` or `[[wiki/agents/graph-wiki-core/commands/query]]`.` → `for example `[[entities/pkg_subagent-runtime]]` or `[[entities/agent-plugin_graph-wiki]]`.`
- `:54` `like `[wiki/packages/foo/foo.md]` instead of converting them to `[[wiki/packages/foo/foo]]` wikilinks` → `like `[entities/pkg_foo.md]` instead of converting them to `[[entities/pkg_foo]]` wikilinks`
- `:60` `([[wiki/packages/subagent-runtime/subagent-runtime]]; `pool.py:115`).` → `([[entities/pkg_subagent-runtime]]; `pool.py:115`).`

- [ ] **Step 3: `query.py`**

- `:633` `` `[[wiki/...]]` path from the excerpts or drop them entirely. `` → `` `[[entities/...]]` path from the excerpts or drop them entirely. ``
- `:648` `"either replace it with a valid full-path [[wiki/...]] wikilink that "` → `"either replace it with a valid full-path [[entities/...]] wikilink that "`

- [ ] **Step 4: Verify no `[[wiki/` remains in these three files**

Run: `grep -rn '\[\[wiki/\|f"wiki/' packages/graph-wiki-core/src/graph_wiki_core/prompts/synthesizer.py packages/graph-wiki-core/src/graph_wiki_core/prompts/sources/synthesizer.md packages/graph-wiki-core/src/graph_wiki_core/commands/query.py`
Expected: no output.

### Task 12: Update the synthesizer prompt test + regenerate the prompt snapshot

**Files:**
- Modify: `packages/graph-wiki-core/tests/unit/test_query_result.py` (`:329-331`)
- Regenerate: `packages/graph-wiki-core/tests/prompts/__snapshots__/test_prompt_snapshots.ambr`

- [ ] **Step 1: Update the assertion**

`:329-331` — replace:
```python
    assert "[[wiki/" in SYNTHESIZER_SYSTEM, (
        "Synthesizer prompt must show full-path wikilink form like [[wiki/...]]"
    )
```
with:
```python
    assert "[[entities/" in SYNTHESIZER_SYSTEM, (
        "Synthesizer prompt must show full-path wikilink form like [[entities/...]]"
    )
```

- [ ] **Step 2: Run the prompt unit tests (non-snapshot)**

Run: `uv run --package graph-wiki-core pytest tests/unit/test_query_result.py -v`
Expected: PASS.

- [ ] **Step 3: Regenerate the prompt snapshot**

Run: `uv run --package graph-wiki-core pytest tests/prompts/test_prompt_snapshots.py --snapshot-update`
Then **diff and confirm only link forms changed** (`wiki/...` → `entities/...`, no other prose drift):
```bash
git diff packages/graph-wiki-core/tests/prompts/__snapshots__/test_prompt_snapshots.ambr
```
Expected diff: only `[[wiki/...]]` → `[[entities/...]]` (and the example slugs). **Do not** touch `test_project_context.ambr` (Planning decision 2).

- [ ] **Step 4: Re-run prompt snapshot tests without update to confirm green**

Run: `uv run --package graph-wiki-core pytest tests/prompts/test_prompt_snapshots.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add packages/graph-wiki-core/src/graph_wiki_core/prompts/synthesizer.py \
        packages/graph-wiki-core/src/graph_wiki_core/prompts/sources/synthesizer.md \
        packages/graph-wiki-core/src/graph_wiki_core/commands/query.py \
        packages/graph-wiki-core/tests/unit/test_query_result.py \
        packages/graph-wiki-core/tests/prompts/__snapshots__/test_prompt_snapshots.ambr
git commit -m "fix(prompts): wiki-root [[entities/...]] citation form in synthesizer + query

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

### Task 13: L4 comment emitters

**Files:**
- Modify: `packages/wiki-io/src/wiki_io/graph_analyzer.py` (`:86`)
- Modify: `packages/eval-harness/src/eval_harness/divergence/librarian.py` (`:34`)
- Modify: `packages/eval-harness/src/eval_harness/structural.py` (`:39` — identical comment; fix for consistency, flag as adjacent-to-spec)

- [ ] **Step 1: `graph_analyzer.py:86`** (this comment matches the grep guard `\[\[wiki/` and MUST change)

Replace:
```python
            # wikilinks like [[wiki/packages/foo/api]] resolve to vault-relative keys.
```
with:
```python
            # wikilinks like [[packages/foo/api]] resolve to vault-relative keys.
```

- [ ] **Step 2: `librarian.py:34` and `structural.py:39`** (dead-category comment; Tier-A consistency)

In both files replace:
```python
    # Directory-style link: [[packages/lattice-wiki-core]] → packages/lattice-wiki-core/overview.md
```
with:
```python
    # Directory-style link: [[entities/pkg_lattice-wiki-core]] → entities/pkg_lattice-wiki-core.md
```
(`structural.py` is not named in the spec but carries the byte-identical comment; fixing both keeps the codebase consistent. These are comments only — no behavior change.)

- [ ] **Step 3: Run the affected suites to confirm comments-only edits are inert**

Run:
```bash
uv run --package wiki-io pytest tests/ -k "graph_analyzer" -m "not integration"
uv run --package eval-harness pytest -m "not integration"
```
Expected: PASS.

- [ ] **Step 4: Commit**

```bash
git add packages/wiki-io/src/wiki_io/graph_analyzer.py \
        packages/eval-harness/src/eval_harness/divergence/librarian.py \
        packages/eval-harness/src/eval_harness/structural.py
git commit -m "docs(comments): wiki-root link forms in graph_analyzer + eval-harness comments

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

### Task 14: L3 agent templates — full layout refresh

**Files:**
- Modify: `packages/wiki-io/src/wiki_io/assets/CLAUDE.md.template`
- Modify: `packages/wiki-io/src/wiki_io/assets/AGENTS.md.template`
- Modify: `packages/wiki-io/src/wiki_io/assets/cursorrules.template`
- Modify: `packages/wiki-io/src/wiki_io/assets/index.md.template`
- Modify: `packages/wiki-io/src/wiki_io/assets/log.md.template`
- Modify: `packages/workspace-io/src/workspace_io/assets/CLAUDE.md.template`

**Canonical layout facts to assert across all of these** (confirmed during planning):
- Obsidian opens at the **wiki root** (`<workspace>/wiki/`); that directory **is** the vault.
- `work/` lives **under** the wiki (`<workspace>/wiki/work/`); reference items as `[[work/<slug>]]`.
- The entity layout is **flat `entities/`** (one page per code-graph entity: repository / domain / package / app / agent_plugin / dependency / test_suite; filenames `pkg_<name>`, `dep_<name>`, `domain_<name>`, …). There are no `packages/`/`domains/`/`apps/` container folders or `overview.md` pages.
- `raw/` is a **workspace sibling** (outside the vault), read on disk at `../raw/`, immutable.

- [ ] **Step 1: `CLAUDE.md.template` — replace the "## Where the wiki sits" section (`:10-26`)**

Replace lines 10-26 with:
```markdown
## Where the wiki sits

Obsidian opens at the **wiki root** (`<workspace>/wiki/`) — this directory *is* the vault, and every `[[wikilink]]` resolves relative to it.

```
<workspace>/                  → e.g. <repo>/graph-wiki/.
├── .graph-wiki.yaml          → workspace manifest (owned by graph-wiki workspace)
├── CLAUDE.md                 → workspace-level schema (owned by graph-wiki workspace)
├── raw/                      → ingested sources. IMMUTABLE. A workspace sibling — read it on disk at ../raw/.
└── wiki/                     → this wiki — the Obsidian vault opens here; you own everything inside
    ├── CLAUDE.md             → this file
    ├── index.md / log.md     → content catalog + append-only timeline
    ├── entities/             → one page per code-graph entity (written by scan)
    ├── concepts/ sources/ architecture/ adrs/   → curated pages
    └── work/                 → work-item tracker (under the wiki, so [[work/<slug>]] resolves)
```

When this file says "wiki root" it means the directory containing this `CLAUDE.md` — the Obsidian vault root. All `[[wikilinks]]` are relative to it. `../raw/` is the one path you reach outside the vault (read-only).
```

- [ ] **Step 2: `CLAUDE.md.template` — replace the "## Wiki structure" block (`:28-55`)**

Replace lines 28-55 with:
```markdown
## Wiki structure

```
index.md                  → content catalog — regenerated every scan/ingest
log.md                    → append-only timeline
entities/                 → one page per code-graph entity, written by scan:
                            repository / domain / package / app / agent_plugin /
                            dependency / test_suite. Filenames are slugs like
                            `pkg_<name>`, `dep_<name>`, `domain_<name>`.
concepts/                 → cross-cutting technical concepts
sources/                  → one summary per ingested source (cites files in ../raw/)
architecture/             → high-level syntheses
adrs/                     → architecture decision records
work/                     → unified bug / tech-debt / feature / initiative / spike tracker
.templates/               → page templates (reference only)
```

Work items live under the wiki at `work/`. Reference them from any page with `[[work/2026-04-21-flaky-healthkit-tests]]` — the same wiki-root base as `[[concepts/...]]` and `[[entities/...]]`.
```

- [ ] **Step 3: `CLAUDE.md.template` — fix the scan/lint/iron-rule container references**

- `:78` `4. Create stub `packages/<name>/overview.md` pages for new packages (one folder per package)` → `4. Create/refresh `entities/<slug>.md` pages for new entities (scan writes these from the code graph)`
- `:91` `6. Update every relevant package/domain/concept page (typically 5-15 pages)` → `6. Update every relevant entity, concept, and source page (typically 5-15 pages)`
- `:111` `... stale work items (`../work/` items past their target date) ...` → `... stale work items (`work/` items past their target date) ...`
- `:119` `3. **All wiki writes go under this wiki directory.** Work items go to `../work/` (owned by `graph-wiki workspace`). No exceptions.` → `3. **All wiki writes go under this wiki directory** — including work items, which live at `work/`. No exceptions.`

- [ ] **Step 4: `CLAUDE.md.template` — replace the "## Obsidian" section (`:151-153`)**

Replace lines 151-153 with:
```markdown
## Obsidian

Open `<workspace>/wiki/` in Obsidian — this wiki directory **is** the vault, so `[[entities/...]]`, `[[concepts/...]]`, `[[work/...]]`, and every other page resolve directly. The immutable `../raw/` sources sit beside the vault; open the parent `<workspace>/` instead if you want them in the sidebar too. Useful plugins: Graph view, Backlinks, Dataview, Marp, Templates, Git.
```

- [ ] **Step 5: `AGENTS.md.template` — apply the same refresh**

Apply the equivalent replacements (`AGENTS.md` is near-identical to `CLAUDE.md`):
- Replace "## Where the wiki sits" (`:10-26`) with the Step-1 block, but with the in-vault filename line reading `├── AGENTS.md             → this file` instead of `CLAUDE.md`.
- Replace "## Wiki structure" (`:28-55`) with the Step-2 block (note AGENTS uses slightly terser right-hand captions — the replacement block above is fine to use verbatim).
- `:55` work-items line — covered by the Step-2 block's trailing paragraph.
- `:91` `5. Update every relevant package/domain/concept page` → `5. Update every relevant entity, concept, and source page`
- `:116` `... stale work items (`../work/` items past their target date) ...` → `... stale work items (`work/` items past their target date) ...`
- `:124` `3. **All wiki writes go under this wiki directory.** Work items go to `../work/`.` → `3. **All wiki writes go under this wiki directory** — including work items at `work/`.`
- AGENTS has no dedicated "## Obsidian" section; no Step-4 equivalent.

- [ ] **Step 6: `cursorrules.template` — fix layout + work location (`:10`, `:15`)**

- `:10` `Layout: this wiki sits at `<workspace>/wiki/`. `../raw/` (sources) and `../work/` (work tracker) are siblings, owned by `graph-wiki workspace`. Reference work items with `[[work/<slug>]]`.` → `Layout: Obsidian opens at the wiki root `<workspace>/wiki/` (the vault). `work/` lives under the wiki; reference items with `[[work/<slug>]]`. `../raw/` (immutable sources) is a workspace sibling, read-only.`
- `:15` `3. All wiki writes go under this wiki directory. Work items go to `../work/`.` → `3. All wiki writes go under this wiki directory, including work items at `work/`.`

- [ ] **Step 7: `index.md.template` — refresh the empty-state category blurbs (`:15-19`)**

- `:16` `_No pages yet. Run `/graph-wiki:scan` to populate application workspaces (web, mobile, CLI)._` → `_No pages yet. Run `/graph-wiki:scan` to populate `entities/app_*.md` pages._`
- `:18-19` `## Package (0)` / `_No pages yet. Run `/graph-wiki:scan` to populate library/service workspaces._` → keep the heading; body → `_No pages yet. Run `/graph-wiki:scan` to populate `entities/pkg_*.md` pages._`
- (Leave the `## Dependency` blurb at `:28` — it already says `entities/dep_*.md`.)

- [ ] **Step 8: `log.md.template` — fix the init entry (`:12`, `:14`)**

- `:12` `Wiki created at `<workspace>/wiki/` with subdirs `entities/`, `concepts/`, `sources/`, `architecture/`, `adrs/`, `.templates/`. `raw/` and `work/` live at the workspace level (owned by `graph-wiki workspace`).` → `Wiki created at `<workspace>/wiki/` with subdirs `entities/`, `concepts/`, `sources/`, `architecture/`, `adrs/`, `work/`, `.templates/`. `raw/` is a workspace sibling (owned by `graph-wiki workspace`); `work/` lives under the wiki.`
- `:14` `Next: run `/graph-wiki:scan` to populate `packages/`.` → `Next: run `/graph-wiki:scan` to populate `entities/`.`

- [ ] **Step 9: `workspace_io/assets/CLAUDE.md.template` — fix Obsidian root, layout, and the `../work/` wikilink (`:6`, `:10`, `:12`, `:29`)**

- `:6` `This is a graph-wiki workspace — a per-repo container for plugin-managed knowledge. The Obsidian vault opens here, so the sidebar shows every workspace-level directory side by side.` → `This is a graph-wiki workspace — a per-repo container for plugin-managed knowledge. The Obsidian vault opens at `wiki/` (the code wiki); `raw/` and the files below are siblings of that vault.`
- `:10` `- `wiki/` — code wiki (curated package/domain/concept pages, ADRs, architecture syntheses). Owned by `graph-wiki-agent`. See [`wiki/CLAUDE.md`](wiki/CLAUDE.md) when present.` → `- `wiki/` — the code wiki and Obsidian vault (entity pages under `entities/`, plus concepts, sources, ADRs, architecture, and the `work/` tracker). Owned by `graph-wiki-agent`. See [`wiki/CLAUDE.md`](wiki/CLAUDE.md) when present.`
- `:12` `- `work/` — unified bug / tech-debt / feature / initiative / spike tracker. Schema owned by `workspace-io`; lifecycle (lint, sidecar, archive, status) owned by `graph-wiki-agent`.` → `- `wiki/work/` — unified bug / tech-debt / feature / initiative / spike tracker (under the wiki). Schema owned by `workspace-io`; lifecycle (lint, sidecar, archive, status) owned by `graph-wiki-agent`.`
- `:29` `- Cite work items from wiki pages as `[[../work/<slug>]]` (relative to a wiki page).` → `- Cite work items from wiki pages as `[[work/<slug>]]` (work/ lives under the wiki, same base as every page).`

- [ ] **Step 10: Verify the templates carry no stale layout tokens**

Run:
```bash
grep -rn '\.\./work/\|\[\[wiki/\|Obsidian opens at the workspace root\|opens here' \
  packages/wiki-io/src/wiki_io/assets/ packages/workspace-io/src/workspace_io/assets/
```
Expected: no output for `../work/`, `[[wiki/`, or the old Obsidian-root phrasings. (`../raw/` references are expected and correct — leave them.)

- [ ] **Step 11: Run the template-dependent suites**

Run:
```bash
uv run --package wiki-io pytest -m "not integration"
uv run --package workspace-io pytest -m "not integration"
```
Expected: PASS. If a test asserts on specific template prose (e.g. a bootstrap test grepping the rendered CLAUDE.md for "workspace root"), update that assertion to the new wording.

- [ ] **Step 12: Commit**

```bash
git add packages/wiki-io/src/wiki_io/assets/ packages/workspace-io/src/workspace_io/assets/
git commit -m "docs(templates): refresh agent-template layout to wiki-root vault + work-under-wiki + entities/

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

### Task 15: `init_vault.py` runtime next-step text

**Files:**
- Modify: `packages/wiki-io/src/wiki_io/init_vault.py` (`:228-229`, `:246-247`)

- [ ] **Step 1: Find any test that pins these strings first**

Run:
```bash
grep -rn "populate wiki/packages\|in Obsidian\|workspace root\|next_steps" packages/wiki-io/tests packages/graph-wiki-cli/tests packages/graph-wiki-core/tests
```
Note any test asserting the next-step / Obsidian strings; update them in Step 3.

- [ ] **Step 2: Update the next-step text**

- `:228` `f"Open {workspace_path} in Obsidian (sidebar shows wiki/ and raw/; work/ lives under wiki/)",` → `f"Open {wiki_path} in Obsidian (the wiki root is the vault; raw/ sits beside it at {workspace_path}/raw/)",`
- `:229` `"Run /graph-wiki:scan to populate wiki/packages/ from workspace manifests",` → `"Run /graph-wiki:scan to populate wiki/entities/ from the code graph",`
- `:246` `logger.info("  1. Open %s in Obsidian (workspace root)", workspace_path)` → `logger.info("  1. Open %s in Obsidian (wiki root = vault)", wiki_path)`
- `:247` `logger.info("  2. Run /graph-wiki:scan to populate wiki/packages/")` → `logger.info("  2. Run /graph-wiki:scan to populate wiki/entities/")`

- [ ] **Step 3: Update any pinning tests found in Step 1, then run init/bootstrap tests**

Run:
```bash
uv run --package wiki-io pytest -k "init or bootstrap" -m "not integration" -v
uv run --package graph-wiki-cli pytest -k "bootstrap or init" -m "not integration" -v
```
Expected: PASS.

- [ ] **Step 4: Commit**

```bash
git add packages/wiki-io/src/wiki_io/init_vault.py
git commit -m "docs(init_vault): Obsidian-at-wiki-root + entities/ in bootstrap next-steps

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

---

## Final verification (run after all phases)

- [ ] **Step 1: SSOT grep guard — must be ZERO**

Run:
```bash
grep -rn '\[\[wiki/\|f"wiki/\|f"\[\[wiki/' packages/*/src
```
Expected: **no output.** (Every emission site flipped. Filesystem-path strings like `wiki/index.md` or `.graph-wiki/` do not match this pattern.)

- [ ] **Step 2: Per-package suites green**

Run:
```bash
uv run --package workspace-io pytest
uv run --package wiki-io pytest
uv run --package graph-wiki-core pytest -m "not integration"
uv run --package graph-io pytest -m "not integration"
uv run --package graph-wiki-cli pytest -m "not integration"
uv run --package eval-harness pytest -m "not integration"
```
Expected: all PASS. Any Tier-B container test that fails (`test_sync_wiki`, `test_cli_sync_wiki`, `test_lint_scanner_heading`) must be **the same status as before this branch** — if one newly fails, investigate; do not paper over.

- [ ] **Step 3: Generated-vault no-broken-links spot check** (the Part-1 repro, now expected clean)

Render an index the real way against a small vault and lint it, confirming no `wiki/...` broken links appear. Minimal repro:
```bash
.venv/bin/python - <<'PY'
import tempfile, pathlib
from wiki_io.update_index import update_index  # adjust import to the real index entrypoint
# Build a tiny wiki dir with a concept page + index, render, lint, assert no broken 'wiki/...' links.
# (If update_index's signature differs, use the same call the command layer uses; the point is
#  to render via the real producer and confirm the output contains no '[[wiki/' targets.)
print("manual repro: confirm rendered index contains no '[[wiki/' and lint broken_links has no 'wiki/...'")
PY
grep -rn '\[\[wiki/' /tmp 2>/dev/null || true
```
Expected: the rendered index contains `[[concepts/...]]` / `[[entities/...]]` / `[[work/...]]`, never `[[wiki/...]]`. (This is a sanity check, not a committed test — Planning decision 1 keeps the zombie e2e test as-is.)

- [ ] **Step 4: ruff — no new errors on touched files**

Run:
```bash
uv run ruff check packages/wiki-io/src/wiki_io/wikilinks.py \
  packages/wiki-io/src/wiki_io/update_index.py \
  packages/wiki-io/src/wiki_io/index_generator.py \
  packages/wiki-io/src/wiki_io/graph_analyzer.py \
  packages/wiki-io/src/wiki_io/init_vault.py \
  packages/graph-wiki-core/src/graph_wiki_core/prompts/synthesizer.py \
  packages/graph-wiki-core/src/graph_wiki_core/commands/query.py \
  packages/eval-harness/src/eval_harness/divergence/librarian.py \
  packages/eval-harness/src/eval_harness/structural.py
```
Expected: no **new** errors vs the Step-0c baseline. **Never** run `ruff format` or `ruff --fix` (repo convention — the src tree is pre-existing format-dirty).

- [ ] **Step 5: Snapshot diff review**

Run: `git diff --stat HEAD~<N> -- '*.ambr'` and confirm only `test_prompt_snapshots.ambr` changed, and only link prefixes within it (`wiki/...` → `entities/...`). `test_project_context.ambr` must be unchanged.

- [ ] **Step 6: Confirm the branch is ready (merge still held — Part 1 + Part 2 land together)**

Do **not** merge. Report status: all phases complete, grep guard zero, suites green, snapshots reviewed. The branch `worktree-wikilink-base-wiki-root` now holds Part 1 + Part 2 together, ready for the held merge.

---

## Self-review notes (planning)

- **Spec coverage:** L1 (Task 1–6), L2 (Task 11–12), L3 (Task 14–15), L4 (Task 13), L5 fixtures+snapshots (Task 7–10, 12). The shared-helper consolidation (approach C) is Tasks 1–4. Phasing (approach B) is the four phase headers, each ending green.
- **Deliberate deviations** (all from user decisions / verified code reality): zombie e2e test left as-is; `project_context.py` + its snapshot untouched; full L3 layout refresh (broader than the spec's "note-only," includes `init_vault.py`); Tier-B container tests (`sync_wiki`, `lint_scanner_heading`) and `test_entity_writer.py:324` explicitly NOT migrated. Each is flagged inline where it occurs.
- **Type/name consistency:** the helper is `vault_wikilink(rel_path, text=None)` everywhere; entity slugs use the `entity_writer` prefix map (`pkg_`, `dep_`, `domain_`, `app_`, `agent-plugin_`, `tests_`, `repo_`).
- **Open risk for the executor:** Phase 3 Tasks 9–10 and Phase 4 Tasks 11/14/15 each say "run the suite; edit only what genuinely breaks on the wikilink form." That is intentional — the spec's L5 file list over-includes container-layout tests. Treat a failing *container-layout* test as a flag, not a force-fix target.
