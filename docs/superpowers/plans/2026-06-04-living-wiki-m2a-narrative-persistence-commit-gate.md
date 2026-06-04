# Living Wiki M2a — Narrative Persistence + Commit-Gated Refresh Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make entity-page `## Narrative` prose **survive re-scan** (it is wiped today), and **refresh it only when the entity's code actually changed** — by snapshotting/restoring narratives across `write_entities`, gating re-narration on a `git diff` of each package/app's files since a per-entity `last_updated_commit`, and stamping that commit when an entity is freshly narrated.

**Architecture:** This is the foundation slice ("M2a") of roadmap Milestone 2. It has three coupled parts:

1. **Narrative persistence (the wipe fix).** The M1 heading-aware merge resets the scanner-owned `## Narrative` to the template placeholder on every re-render (`_merge_preserved_sections`), and the narrator only refills pages in `needs_narrative` (new / structural-frontmatter change). So a narrated page that is neither new nor structurally changed has its prose **wiped and never refilled**. We fix this by mirroring the existing file-map idiom: snapshot narratives *before* `write_entities`, restore them *after* for entities not re-narrated this scan. (`_snapshot_file_map_descriptions` + `inject_file_map(preserved=…)` is the precedent.)
2. **Commit-gate.** A new per-entity `last_updated_commit` frontmatter key records the HEAD at which an entity's narrative was last regenerated. On re-scan, package/app entities whose files changed since that anchor (`git diff <anchor>..HEAD`) are unioned into `needs_narrative` so their prose is refreshed instead of merely preserved-stale.
3. **Stamping.** When an entity is successfully narrated, stamp `last_updated_commit = HEAD` on its page via an order-preserving, byte-stable frontmatter setter.

**Tech Stack:** Python 3.11+, `uv` workspace (`wiki-io`, `graph-wiki-core` packages), `pytest` (`pytest-asyncio` for `run_scan`), `python-frontmatter`, `PyYAML`, stdlib `re`/`subprocess`, `unittest.mock`.

**Source spec:** `docs/superpowers/specs/2026-06-03-living-wiki-roadmap.md` (§3 D3, §4 "M2 — Commit-gated incremental updates"). This plan implements the foundation; later M2 slices (file-map content-hash re-description, template reconciliation, human-section drift flagging) are explicitly out of scope (see Scope).

**Prior milestone:** Builds directly on M1 (`docs/superpowers/plans/2026-06-03-living-wiki-m1-preservation.md`, landed — commits `85e56c3a`…`c521d014`). M1 added `_is_scanner_owned_heading` / `_split_h2_sections` / `_merge_preserved_sections` and made `## Narrative`/`## File map`/`## Referenced in wiki` scanner-owned. This plan adds the persistence + refresh layer that M1's scanner-owned reset made necessary.

---

## Key finding driving this plan (verify, don't skip)

`_merge_preserved_sections(template_body, existing_body)` takes scanner-owned sections from the **template**, so a page whose `## Narrative` holds real prose has it reset to `_(scanner will populate on next scan)_` on the next `write_entities` run. The narrator (`scan.py` Step 9b) only processes `needs_narrative` = new ∪ structural-change. **No narrative snapshot/restore exists anywhere.** Net effect in `main` today: narrated prose is lost on the next non-structural re-scan. Reproduce it before starting:

```bash
uv run --package wiki-io python -c "
from wiki_io.entity_writer import _merge_preserved_sections
template = '# P\n\n## Narrative\n_(scanner will populate on next scan)_\n\n## Purpose\n> TODO\n'
existing = '# P\n\n## Narrative\nReal narrated prose.\n\n## Purpose\nHuman purpose.\n'
out = _merge_preserved_sections(template, existing)
print('prose survives:', 'Real narrated prose' in out)   # -> False (the bug)
print('placeholder back:', 'scanner will populate' in out) # -> True
"
```

---

## Design decisions (made for this foundation slice; documented so they are reviewable)

- **D-A `last_updated_commit` is a preserved (non-scanner) frontmatter key.** It is NOT added to `SCANNER_OWNED_KEYS`, so `merge_frontmatter` preserves it across re-scan as a "human" key (Task 1 adds a regression test locking this in). It is written **only** by the scan pipeline when an entity is freshly narrated — never by `write_entities` (which cannot know whether narration will succeed).
- **D-B Stamp only on successful narration.** The anchor advances to HEAD exclusively after `inject_narrative` succeeds for that page. It is never advanced for `--no-narrate` scans or pages still pending narration. This guarantees no "accumulation bug" (changed-but-unnarrated files stay visible to the next scan's diff).
- **D-C Anchor-absent pages are not force-narrated.** Pre-M2 pages (and any page that has never been narrated under M2) have no `last_updated_commit`; the commit-gate skips them, leaving their refresh governed by the existing new/structural gate until a narration stamps an anchor. This avoids a re-narrate-everything cost spike on the first M2 scan. (Documented migration behavior; an operator can force a one-time re-narrate to activate gating immediately.)
- **D-D Unknown anchor ⇒ dirty.** `changed_files_since` returns `None` when the recorded SHA is unknown to the repo (e.g. after a rebase/GC). The gate treats `None` as "changed" so a stale anchor self-corrects (re-narrate → re-stamp) on the next scan.
- **D-E Commit-gate covers `package`/`app` only.** Those are the kinds with a single directory (`node.path`) that defines a file set. `domain`/`dependency`/`repository`/`test_suite` have no such file set; they keep the existing new/structural gate. (Narrative *persistence*, by contrast, applies to **all** kinds.)
- **D-F Persistence is independent of `narrate`.** `write_entities` wipes narratives whether or not narration runs, so snapshot+restore runs on `--no-narrate` scans too.
- **D-G Restore never clobbers fresh prose.** The restore step only refills a page whose current `## Narrative` is empty/placeholder (`extract_narrative(...) is None`), and skips any URI freshly narrated this scan.

---

## Scope

In scope (M2a foundation):
- Narrative snapshot-before / restore-after across `write_entities` (the wipe fix).
- `last_updated_commit` frontmatter key + byte-stable setter.
- Commit-gate: union package/app URIs whose files changed since their anchor into `needs_narrative`.
- Stamping the anchor on freshly-narrated pages.

Explicitly **out of scope** (later M2 slices, each warranting its own plan):
- File-map **content-hash re-description** (re-describing a file when its content changed — carries a re-describe-vs-preserve-human-edit tension).
- **Template reconciliation** of evolved H2 sets beyond what M1's merge already does.
- **Human-section drift flagging** (`## Purpose`/`## Public API` going stale).
- Reducing the existing per-scan "updated" churn (write_entities transiently marking narrated pages "updated" because Narrative is reset). M2a fixes correctness (prose persists); this efficiency item is deferred.

---

## File Structure

| File | Responsibility | Change |
|---|---|---|
| `packages/wiki-io/src/wiki_io/entity_writer.py` | Entity render/IO; frontmatter dump | **Modify**: add `LAST_UPDATED_COMMIT_KEY`; extract `_render_page_text`; add `set_frontmatter_value`; add `extract_narrative` + `_NARRATIVE_PLACEHOLDER` |
| `packages/wiki-io/tests/test_set_frontmatter_value.py` | Unit tests for the setter | **Create** |
| `packages/wiki-io/tests/test_extract_narrative.py` | Unit tests for the narrative extractor | **Create** |
| `packages/wiki-io/tests/test_entity_writer.py` | merge_frontmatter / write_entities tests | **Modify**: add `last_updated_commit` preservation regression test |
| `packages/graph-wiki-core/src/graph_wiki_core/commands/scan.py` | Scan pipeline | **Modify**: imports; `_commit_dirty_uris`; `_snapshot_narratives`; restore step; commit-gate union; anchor stamping |
| `packages/graph-wiki-core/tests/unit/test_commit_gated_narrative.py` | Gate + persistence + stamp tests | **Create** |
| `.claude/rules/backward-compatibility.md` | Project rule | **Modify**: note `last_updated_commit` as a scanner-stamped, preserved provenance key |

**Run tests with** (from repo root):
- `uv run --package wiki-io pytest <path> -v`
- `uv run --package graph-wiki-core pytest <path> -v`

---

## Task 1: `last_updated_commit` key + byte-stable frontmatter setter

Add a named key constant, extract the page-framing logic into one reusable helper (so the setter and the renderer agree byte-for-byte), and add `set_frontmatter_value`. New keys are appended last, matching `merge_frontmatter`'s placement of non-scanner keys, so a later `write_entities` re-render is byte-identical.

**Files:**
- Modify: `packages/wiki-io/src/wiki_io/entity_writer.py`
- Create: `packages/wiki-io/tests/test_set_frontmatter_value.py`
- Modify: `packages/wiki-io/tests/test_entity_writer.py`

- [ ] **Step 1: Write the failing tests**

Create `packages/wiki-io/tests/test_set_frontmatter_value.py`:

```python
"""Unit tests for set_frontmatter_value (Living Wiki M2a)."""

from __future__ import annotations

from pathlib import Path

import frontmatter

from wiki_io.entity_writer import LAST_UPDATED_COMMIT_KEY, set_frontmatter_value


def _write(p: Path, text: str) -> None:
    p.write_text(text, encoding="utf-8")


def test_appends_new_key_last_preserving_body(tmp_path: Path) -> None:
    page = tmp_path / "e.md"
    _write(page, "---\ntitle: A\nuri: pkg:a\n---\n# A\n\n## Narrative\nprose here\n")
    set_frontmatter_value(page, LAST_UPDATED_COMMIT_KEY, "abc123")
    post = frontmatter.load(page)
    assert post.metadata[LAST_UPDATED_COMMIT_KEY] == "abc123"
    assert post.metadata["title"] == "A"            # existing keys preserved
    assert "## Narrative\nprose here" in post.content  # body preserved
    assert list(post.metadata.keys())[-1] == LAST_UPDATED_COMMIT_KEY  # appended last


def test_updates_existing_key_in_place(tmp_path: Path) -> None:
    page = tmp_path / "e.md"
    _write(
        page,
        "---\nuri: pkg:a\nlast_updated_commit: old\ntitle: A\n---\n# A\n",
    )
    set_frontmatter_value(page, LAST_UPDATED_COMMIT_KEY, "new")
    post = frontmatter.load(page)
    assert post.metadata[LAST_UPDATED_COMMIT_KEY] == "new"
    keys = list(post.metadata.keys())
    assert keys.index("last_updated_commit") < keys.index("title")  # position kept


def test_resetting_same_value_is_byte_stable(tmp_path: Path) -> None:
    page = tmp_path / "e.md"
    _write(page, "---\nuri: pkg:a\n---\n# A\n\n## Purpose\nkept\n")
    set_frontmatter_value(page, LAST_UPDATED_COMMIT_KEY, "abc123")
    first = page.read_text(encoding="utf-8")
    set_frontmatter_value(page, LAST_UPDATED_COMMIT_KEY, "abc123")
    assert page.read_text(encoding="utf-8") == first
```

Append to `packages/wiki-io/tests/test_entity_writer.py` (near the other `merge_frontmatter` tests):

```python
def test_merge_frontmatter_preserves_last_updated_commit() -> None:
    """last_updated_commit is NOT scanner-owned: merge_frontmatter must keep an
    existing value (regression guard — adding it to SCANNER_OWNED_KEYS would
    silently break the M2a commit-gate)."""
    from wiki_io.entity_writer import (
        LAST_UPDATED_COMMIT_KEY,
        SCANNER_OWNED_KEYS,
        merge_frontmatter,
    )

    assert LAST_UPDATED_COMMIT_KEY not in SCANNER_OWNED_KEYS
    existing = {"uri": "pkg:a", "kind": "package", LAST_UPDATED_COMMIT_KEY: "sha1"}
    scanner = {"uri": "pkg:a", "kind": "package"}
    merged = merge_frontmatter(existing, scanner)
    assert merged[LAST_UPDATED_COMMIT_KEY] == "sha1"
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run --package wiki-io pytest packages/wiki-io/tests/test_set_frontmatter_value.py packages/wiki-io/tests/test_entity_writer.py::test_merge_frontmatter_preserves_last_updated_commit -v`
Expected: FAIL — `ImportError: cannot import name 'LAST_UPDATED_COMMIT_KEY'` / `'set_frontmatter_value'`.

- [ ] **Step 3: Add the constant and the framing helper**

In `packages/wiki-io/src/wiki_io/entity_writer.py`, immediately **above** the M1 preservation comment block (the line `# Living Wiki M1: heading-aware section preservation (Approach A).`, currently at line 502), insert:

```python
# Living Wiki M2a: per-entity provenance key. Holds the full HEAD SHA at which
# this entity's `## Narrative` was last regenerated. NOT in SCANNER_OWNED_KEYS —
# merge_frontmatter preserves it; only the scan pipeline stamps it (on narration).
LAST_UPDATED_COMMIT_KEY = "last_updated_commit"


def _render_page_text(frontmatter_dict: dict, body: str) -> str:
    """Frame a frontmatter dict + body into the canonical entity-page text.

    Single source of truth for the dump convention (D-14/D-15): `sort_keys=False`
    (order pre-decided by `merge_frontmatter`), one trailing newline. Shared by
    `_render_entity_page` and `set_frontmatter_value` so a page stamped by the
    latter re-renders byte-identically through the former.
    """
    yaml_block = yaml.safe_dump(
        frontmatter_dict,
        sort_keys=False,
        default_flow_style=False,
        allow_unicode=True,
        width=10_000,
    ).rstrip("\n")
    return f"---\n{yaml_block}\n---\n{body}".rstrip("\n") + "\n"
```

- [ ] **Step 4: Route `_render_entity_page` through the helper**

In `_render_entity_page`, replace its current tail (lines 624-632, the `yaml_block = yaml.safe_dump(...)` block through `rendered = ...`, ending just before `return rendered`):

```python
    yaml_block = yaml.safe_dump(
        frontmatter_dict,
        sort_keys=False,
        default_flow_style=False,
        allow_unicode=True,
        width=10_000,
    )
    yaml_block = yaml_block.rstrip("\n")
    rendered = f"---\n{yaml_block}\n---\n{body}".rstrip("\n") + "\n"
    return rendered
```

with:

```python
    return _render_page_text(frontmatter_dict, body)
```

- [ ] **Step 5: Add `set_frontmatter_value`**

In `entity_writer.py`, insert immediately **after** `_render_entity_page` (which ends at the new `return _render_page_text(...)`; the next thing is the `write_entities orchestrator` comment banner around line 636):

```python
def set_frontmatter_value(page_path: Path, key: str, value: str) -> None:
    """Set a single frontmatter `key` to `value` on an entity page, preserving
    the body bytes and the canonical dump convention.

    The key is updated in place when present, or appended last when new — which
    matches `merge_frontmatter`'s placement of non-scanner keys, so a subsequent
    `write_entities` re-render is byte-identical. Writes atomically via a temp
    file + `os.replace` (mirrors `inject_narrative`).

    Raises:
        FileNotFoundError: when `page_path` does not exist.
    """
    post = frontmatter.load(page_path)  # raises FileNotFoundError naturally
    fm = dict(post.metadata)
    fm[key] = value
    new_content = _render_page_text(fm, post.content)
    tmp_path = page_path.with_suffix(page_path.suffix + ".tmp")
    tmp_path.write_text(new_content, encoding="utf-8")
    os.replace(tmp_path, page_path)
```

- [ ] **Step 6: Run tests to verify they pass**

Run: `uv run --package wiki-io pytest packages/wiki-io/tests/test_set_frontmatter_value.py packages/wiki-io/tests/test_entity_writer.py -v`
Expected: PASS (the 3 setter tests + the new merge regression test; all pre-existing `test_entity_writer.py` tests stay green — the `_render_page_text` extraction is behavior-preserving).

- [ ] **Step 7: Commit**

```bash
git add packages/wiki-io/src/wiki_io/entity_writer.py \
        packages/wiki-io/tests/test_set_frontmatter_value.py \
        packages/wiki-io/tests/test_entity_writer.py
git commit -m "feat(wiki-io): add last_updated_commit key + byte-stable set_frontmatter_value"
```

---

## Task 2: `extract_narrative` — read non-placeholder narrative prose

A pure reader used by the scan pipeline to (a) snapshot prose before re-render and (b) guard the restore step from clobbering fresh prose. Returns the stripped `## Narrative` body, or `None` when the section is missing, empty, or the template placeholder.

**Files:**
- Modify: `packages/wiki-io/src/wiki_io/entity_writer.py`
- Create: `packages/wiki-io/tests/test_extract_narrative.py`

- [ ] **Step 1: Write the failing tests**

Create `packages/wiki-io/tests/test_extract_narrative.py`:

```python
"""Unit tests for extract_narrative (Living Wiki M2a)."""

from __future__ import annotations

from wiki_io.entity_writer import extract_narrative


def test_returns_real_prose_stripped() -> None:
    text = "# P\n\n## Narrative\nReal prose about the package.\n\n## Purpose\nx\n"
    assert extract_narrative(text) == "Real prose about the package."


def test_placeholder_returns_none() -> None:
    text = "# P\n\n## Narrative\n_(scanner will populate on next scan)_\n\n## Purpose\nx\n"
    assert extract_narrative(text) is None


def test_empty_section_returns_none() -> None:
    text = "# P\n\n## Narrative\n\n## Purpose\nx\n"
    assert extract_narrative(text) is None


def test_missing_heading_returns_none() -> None:
    assert extract_narrative("# P\n\n## Purpose\nx\n") is None


def test_narrative_at_eof() -> None:
    text = "# P\n\n## Narrative\nProse with no trailing section.\n"
    assert extract_narrative(text) == "Prose with no trailing section."
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run --package wiki-io pytest packages/wiki-io/tests/test_extract_narrative.py -v`
Expected: FAIL — `ImportError: cannot import name 'extract_narrative'`.

- [ ] **Step 3: Add the placeholder constant + extractor**

In `entity_writer.py`, the regexes `_NARRATIVE_HEADING_RE` (line 1041) and `_NEXT_H2_RE` (line 1045) are defined just above `inject_narrative` (line 1048). Insert immediately **after** line 1045 (`_NEXT_H2_RE = ...`) and **before** `def inject_narrative`:

```python
# Living Wiki M2a: the entity templates' `## Narrative` placeholder. A section
# equal to this (or empty) is treated as "no prose" by extract_narrative.
_NARRATIVE_PLACEHOLDER = "_(scanner will populate on next scan)_"


def extract_narrative(text: str) -> str | None:
    """Return the stripped body of the `## Narrative` section, or None when the
    section is missing, empty, or still the template placeholder.

    Used by the scan pipeline to snapshot narrated prose before `write_entities`
    re-renders the page (which resets this scanner-owned section), and to guard
    the restore step from overwriting freshly-injected prose.
    """
    match = _NARRATIVE_HEADING_RE.search(text)
    if match is None:
        return None
    body_start = match.end()
    next_h2 = _NEXT_H2_RE.search(text, body_start)
    body_end = next_h2.start() if next_h2 is not None else len(text)
    body = text[body_start:body_end].strip()
    if not body or body == _NARRATIVE_PLACEHOLDER:
        return None
    return body
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run --package wiki-io pytest packages/wiki-io/tests/test_extract_narrative.py -v`
Expected: PASS (5 tests).

- [ ] **Step 5: Commit**

```bash
git add packages/wiki-io/src/wiki_io/entity_writer.py \
        packages/wiki-io/tests/test_extract_narrative.py
git commit -m "feat(wiki-io): add extract_narrative (non-placeholder narrative reader)"
```

---

## Task 3: `_commit_dirty_uris` — the commit-gate helper

A scan-pipeline helper that returns the package/app URIs whose files changed since the commit recorded on their page (`last_updated_commit`). Pure glue over the existing `wiki_io.git_state.changed_files_since`; fully unit-testable by monkeypatching that function and `_kind_list_fns`.

**Files:**
- Modify: `packages/graph-wiki-core/src/graph_wiki_core/commands/scan.py`
- Create: `packages/graph-wiki-core/tests/unit/test_commit_gated_narrative.py`

- [ ] **Step 1: Write the failing tests**

Create `packages/graph-wiki-core/tests/unit/test_commit_gated_narrative.py`:

```python
"""Living Wiki M2a: commit-gate + narrative persistence + anchor stamping."""

from __future__ import annotations

import types
from pathlib import Path

import graph_wiki_core.commands.scan as scan_mod
from graph_wiki_core.commands.scan import _commit_dirty_uris
from wiki_io.entity_writer import LAST_UPDATED_COMMIT_KEY, short_filename


def _node(uri: str, path: str):
    return types.SimpleNamespace(
        attrs={"uri": uri}, path=path, name=Path(path).name, kind="package"
    )


def _write_page(wiki: Path, uri: str, *, anchor: str | None) -> Path:
    page = wiki / "entities" / f"{short_filename(uri, frozenset())}.md"
    page.parent.mkdir(parents=True, exist_ok=True)
    fm = f"uri: {uri}\nkind: package\n"
    if anchor:
        fm += f"{LAST_UPDATED_COMMIT_KEY}: {anchor}\n"
    page.write_text(
        f"---\n{fm}---\n# {uri}\n\n## Narrative\nprose\n", encoding="utf-8"
    )
    return page


def _patch_list_fns(monkeypatch, nodes) -> None:
    monkeypatch.setattr(
        scan_mod,
        "_kind_list_fns",
        lambda: {"package": lambda conn: nodes, "app": lambda conn: []},
    )


def test_dirty_when_files_changed(tmp_path, monkeypatch) -> None:
    wiki = tmp_path / "wiki"
    uri = "pkg:org/repo/foo"
    _write_page(wiki, uri, anchor="anchor_sha")
    _patch_list_fns(monkeypatch, [_node(uri, "packages/foo")])
    monkeypatch.setattr(
        scan_mod, "changed_files_since", lambda repo, sha, sub: ["packages/foo/x.py"]
    )
    dirty = _commit_dirty_uris(
        wiki, tmp_path / "repo", object(), "head_sha", frozenset()
    )
    assert dirty == {uri}


def test_clean_when_no_changes(tmp_path, monkeypatch) -> None:
    wiki = tmp_path / "wiki"
    uri = "pkg:org/repo/foo"
    _write_page(wiki, uri, anchor="anchor_sha")
    _patch_list_fns(monkeypatch, [_node(uri, "packages/foo")])
    monkeypatch.setattr(scan_mod, "changed_files_since", lambda *a: [])
    assert _commit_dirty_uris(
        wiki, tmp_path / "repo", object(), "head_sha", frozenset()
    ) == set()


def test_skips_pages_without_anchor(tmp_path, monkeypatch) -> None:
    wiki = tmp_path / "wiki"
    uri = "pkg:org/repo/foo"
    _write_page(wiki, uri, anchor=None)  # pre-M2 page
    _patch_list_fns(monkeypatch, [_node(uri, "packages/foo")])
    consulted: list[int] = []
    monkeypatch.setattr(
        scan_mod, "changed_files_since", lambda *a: consulted.append(1) or []
    )
    assert _commit_dirty_uris(
        wiki, tmp_path / "repo", object(), "head_sha", frozenset()
    ) == set()
    assert consulted == []  # git never consulted for anchorless pages


def test_unknown_anchor_treated_as_dirty(tmp_path, monkeypatch) -> None:
    wiki = tmp_path / "wiki"
    uri = "pkg:org/repo/foo"
    _write_page(wiki, uri, anchor="gone_sha")
    _patch_list_fns(monkeypatch, [_node(uri, "packages/foo")])
    monkeypatch.setattr(scan_mod, "changed_files_since", lambda *a: None)  # SHA unknown
    assert _commit_dirty_uris(
        wiki, tmp_path / "repo", object(), "head_sha", frozenset()
    ) == {uri}


def test_no_head_returns_empty(tmp_path, monkeypatch) -> None:
    wiki = tmp_path / "wiki"
    uri = "pkg:org/repo/foo"
    _write_page(wiki, uri, anchor="anchor_sha")
    _patch_list_fns(monkeypatch, [_node(uri, "packages/foo")])
    assert _commit_dirty_uris(
        wiki, tmp_path / "repo", object(), None, frozenset()
    ) == set()
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run --package graph-wiki-core pytest packages/graph-wiki-core/tests/unit/test_commit_gated_narrative.py -v`
Expected: FAIL — `ImportError: cannot import name '_commit_dirty_uris'` (and `changed_files_since` is not yet an attribute of the scan module).

- [ ] **Step 3: Add the import + helper**

In `scan.py`, extend the `wiki_io.entity_writer` import block (lines 36-48) — add the three M2a names (keep alphabetical-ish grouping; exact placement is not load-bearing):

```python
from wiki_io.entity_writer import (
    ADMITTED_KINDS,
    LAST_UPDATED_COMMIT_KEY,
    _compute_collision_set,
    _extract_file_map_descriptions,
    _kind_list_fns,
    extract_narrative,
    fill_file_map_descriptions,
    file_map_todo_paths,
    inject_file_map,
    inject_narrative,
    scanner_frontmatter_for_node,
    set_frontmatter_value,
    short_filename,
    write_entities,
)
```

Add a new import immediately after the `wiki_io.backlink_index` import (line 56):

```python
from wiki_io.git_state import changed_files_since
```

Then insert `_commit_dirty_uris` immediately **after** `_entity_page_path` (which ends at line 508, just before the `# Public: run_scan` banner at line 511):

```python
def _commit_dirty_uris(
    wiki: Path,
    repo: Path,
    conn: Any,
    head: str | None,
    collision_set: frozenset[str],
) -> set[str]:
    """URIs of `package`/`app` entities whose files changed since the commit
    recorded on their page (`last_updated_commit`).

    M2a commit-gate: makes `## Narrative` refresh track real code changes, not
    just frontmatter structural deltas. Pages WITHOUT an anchor are skipped
    (D-C) — their refresh stays governed by the existing new/structural gate
    until a narration stamps an anchor. A `None` from `changed_files_since`
    (anchor SHA unknown to this repo) is treated as dirty (D-D) so a stale
    anchor self-corrects on the next narrated scan.
    """
    dirty: set[str] = set()
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
                dirty.add(uri)
    return dirty
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run --package graph-wiki-core pytest packages/graph-wiki-core/tests/unit/test_commit_gated_narrative.py -v`
Expected: PASS (5 gate tests).

- [ ] **Step 5: Commit**

```bash
git add packages/graph-wiki-core/src/graph_wiki_core/commands/scan.py \
        packages/graph-wiki-core/tests/unit/test_commit_gated_narrative.py
git commit -m "feat(scan): add _commit_dirty_uris commit-gate helper"
```

---

## Task 4: Narrative snapshot + restore (the wipe fix) in `run_scan`

Snapshot non-placeholder narratives before `write_entities`; after the narrator inject loop, restore prior prose for any entity not freshly narrated whose `## Narrative` is back to placeholder. Runs in narrate and `--no-narrate` scans alike (D-F).

**Files:**
- Modify: `packages/graph-wiki-core/src/graph_wiki_core/commands/scan.py`
- Modify: `packages/graph-wiki-core/tests/unit/test_commit_gated_narrative.py`

- [ ] **Step 1: Write the failing test (integration via `run_scan`)**

Append to `packages/graph-wiki-core/tests/unit/test_commit_gated_narrative.py` (these reuse the `run_scan` harness pattern from `tests/unit/test_scan_narrate.py`):

```python
import asyncio
import sqlite3

import frontmatter as _fm
import pytest
from graph_io import exit_codes
from unittest.mock import MagicMock


def _seed_one_package(db_path: Path) -> None:
    """Graph with a single package node pkg-a at packages/pkg-a."""
    from graph_io import schema

    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(db_path)
    try:
        schema.apply_schema(conn)
        conn.execute(
            "INSERT INTO nodes(kind, name, path, line, attrs_json, uri) VALUES "
            "('package', 'pkg-a', 'packages/pkg-a', NULL, '{\"language\": \"python\"}', "
            "'pkg:org/repo/pkg-a')"
        )
        conn.commit()
    finally:
        conn.close()


@pytest.fixture
def m2a_workspace(tmp_path, monkeypatch):
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
        scan_mod, "_cg_run_build", lambda repo, ws, *, full: (exit_codes.SUCCESS, "", "")
    )
    monkeypatch.setattr(
        scan_mod, "make_llm", lambda role, *, model_override=None: MagicMock()
    )
    # Minimal deterministic file map so the package page gets a File map section.
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
    return workspace


def _narrate_all_spy(prose_fn):
    """Return an async SubagentPool.run_all that narrates every item via prose_fn."""

    async def _run_all(self, *, items, task, role, model_id, max_concurrency):
        from subagent_runtime.pool import FanOutResult

        result = FanOutResult()
        result.successes = [(it, prose_fn(it)) for it in items]
        return result

    return _run_all


_PKG_A = "pkg:org/repo/pkg-a"


def _page_for(wiki: Path):
    return next(
        p
        for p in (wiki / "entities").glob("*.md")
        if _fm.load(p).metadata.get("uri") == _PKG_A
    )


def test_narrative_survives_no_op_rescan(m2a_workspace, monkeypatch) -> None:
    """A narrated package keeps its prose on a second scan with no code change
    (the M1 wipe is fixed by snapshot+restore)."""
    workspace = m2a_workspace
    wiki = workspace / "wiki"
    repo = workspace / "repo"
    monkeypatch.setattr(
        scan_mod, "compute_state_gate",
        lambda repo: {"allowed": True, "reason": "clean", "head_commit": "head1"},
    )
    monkeypatch.setattr(
        scan_mod.SubagentPool, "run_all",
        _narrate_all_spy(lambda it: f"PROSE for {it[0]}"),
    )

    # Scan 1: new page → narrated.
    asyncio.run(scan_mod.run_scan(workspace_path=workspace, repo_path=repo, narrate=True))
    text1 = _page_for(wiki).read_text(encoding="utf-8")
    assert "PROSE for pkg:org/repo/pkg-a" in text1
    assert _fm.load(_page_for(wiki)).metadata.get("last_updated_commit") == "head1"

    # Scan 2: no code change (files clean), so NOT re-narrated. Prose must persist.
    monkeypatch.setattr(scan_mod, "changed_files_since", lambda *a: [])
    asyncio.run(scan_mod.run_scan(workspace_path=workspace, repo_path=repo, narrate=True))
    text2 = _page_for(wiki).read_text(encoding="utf-8")
    assert "PROSE for pkg:org/repo/pkg-a" in text2  # <-- the fix
    assert "_(scanner will populate on next scan)_" not in text2
    # Anchor unchanged (not re-narrated).
    assert _fm.load(_page_for(wiki)).metadata.get("last_updated_commit") == "head1"


def test_narrative_survives_no_narrate_rescan(m2a_workspace, monkeypatch) -> None:
    """Persistence is independent of narration (D-F): a --no-narrate rescan must
    not wipe an existing narrative."""
    workspace = m2a_workspace
    wiki = workspace / "wiki"
    repo = workspace / "repo"
    monkeypatch.setattr(
        scan_mod, "compute_state_gate",
        lambda repo: {"allowed": True, "reason": "clean", "head_commit": "head1"},
    )
    monkeypatch.setattr(
        scan_mod.SubagentPool, "run_all",
        _narrate_all_spy(lambda it: f"PROSE for {it[0]}"),
    )
    asyncio.run(scan_mod.run_scan(workspace_path=workspace, repo_path=repo, narrate=True))
    assert "PROSE for" in _page_for(wiki).read_text(encoding="utf-8")

    asyncio.run(scan_mod.run_scan(workspace_path=workspace, repo_path=repo, narrate=False))
    text = _page_for(wiki).read_text(encoding="utf-8")
    assert "PROSE for pkg:org/repo/pkg-a" in text
    assert "_(scanner will populate on next scan)_" not in text
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `uv run --package graph-wiki-core pytest packages/graph-wiki-core/tests/unit/test_commit_gated_narrative.py -k "survives" -v`
Expected: FAIL. Scan 1 also fails its anchor assertion (stamping not wired until Task 5), but the load-bearing failure is `assert "PROSE for pkg:org/repo/pkg-a" in text2` — scan 2 wipes the narrative to placeholder. (Both `survives` tests fail at the post-rescan prose assertion; the `last_updated_commit == "head1"` assertions also fail pending Task 5.)

> Note: Task 4 wires **restore**; the anchor-stamp assertions go green in Task 5. If you run these tests after Task 4 only, the prose-persistence assertions pass but the `last_updated_commit` assertions still fail. That is expected until Task 5. (Run with `-k "survives and no_op"` and temporarily ignore the anchor asserts, or simply implement Tasks 4 and 5 back-to-back and run the suite once at the end of Task 5.)

- [ ] **Step 3: Add the snapshot helper**

In `scan.py`, insert `_snapshot_narratives` immediately **after** `_snapshot_file_map_descriptions` (which ends at line 140, before the `# Local helper: pick_representative` banner at line 143):

```python
def _snapshot_narratives(wiki: Path) -> dict[str, str]:
    """Snapshot non-placeholder `## Narrative` prose from existing entity pages,
    keyed by URI, BEFORE write_entities resets page bodies to template.

    Mirrors `_snapshot_file_map_descriptions`: the M1 heading-aware merge resets
    the scanner-owned `## Narrative` to the template placeholder on every
    re-render, so prior narrated prose must be captured here and restored after
    write_entities for entities not re-narrated this scan (M2a persistence).
    """
    snapshot: dict[str, str] = {}
    entities_dir = wiki / "entities"
    if not entities_dir.is_dir():
        return snapshot
    for page_path in entities_dir.glob("*.md"):
        try:
            post = frontmatter.load(page_path)
        except Exception:  # noqa: BLE001 — a malformed page must not abort scan
            continue
        uri = post.metadata.get("uri")
        if not uri:
            continue
        prose = extract_narrative(post.content)
        if prose:
            snapshot[uri] = prose
    return snapshot
```

- [ ] **Step 4: Take the snapshot before `write_entities`**

In `run_scan`, find the file-map snapshot block (lines 682-684):

```python
        prior_file_map_descs: dict[str, dict[str, str]] = {}
        if conn is not None:
            prior_file_map_descs = _snapshot_file_map_descriptions(wiki)
```

Replace it with:

```python
        prior_file_map_descs: dict[str, dict[str, str]] = {}
        prior_narratives: dict[str, str] = {}
        if conn is not None:
            prior_file_map_descs = _snapshot_file_map_descriptions(wiki)
            prior_narratives = _snapshot_narratives(wiki)
```

- [ ] **Step 5: Restore narratives after the narrator inject loop**

In `run_scan`, locate the end of the narrator inject block — the `for err in narrator_result.errors:` loop that ends at line 782 (just before the `# Step 10b: deterministic File-map injection` comment at line 784). Insert immediately after line 782 and before line 784:

```python
        # M2a narrative persistence: restore prior narrative prose for entities
        # NOT re-narrated this scan. write_entities reset every `## Narrative` to
        # the template placeholder (M1 heading-aware merge); without this, prose
        # injected on a prior scan would be wiped whenever the entity is not in
        # needs_narrative. Runs in narrate and --no-narrate scans alike (D-F);
        # never clobbers fresh prose (D-G).
        if conn is not None and prior_narratives:
            narrated_set = set(entities_narrated)
            for page_path in sorted((wiki / "entities").glob("*.md")):
                try:
                    post = frontmatter.load(page_path)
                except Exception:  # noqa: BLE001
                    continue
                restore_uri = post.metadata.get("uri")
                if not restore_uri or restore_uri in narrated_set:
                    continue
                prose = prior_narratives.get(restore_uri)
                if not prose:
                    continue
                if extract_narrative(post.content) is not None:
                    continue  # already carries real prose — don't clobber (D-G)
                try:
                    inject_narrative(page_path, prose)
                except Exception as exc:  # noqa: BLE001 — non-fatal restore
                    logger.warning(
                        "narrative restore failed for %s: %s", restore_uri, exc
                    )
```

- [ ] **Step 6: Run the persistence tests**

Run: `uv run --package graph-wiki-core pytest packages/graph-wiki-core/tests/unit/test_commit_gated_narrative.py -k "survives" -v`
Expected: the **prose-persistence** assertions now PASS (`"PROSE for ..." in text2`, no placeholder). The `last_updated_commit == "head1"` assertions still FAIL — that is wired in Task 5. Proceed to Task 5, then run the full file.

- [ ] **Step 7: Commit**

```bash
git add packages/graph-wiki-core/src/graph_wiki_core/commands/scan.py \
        packages/graph-wiki-core/tests/unit/test_commit_gated_narrative.py
git commit -m "fix(scan): preserve entity narratives across re-scan (snapshot+restore)"
```

---

## Task 5: Wire the commit-gate union + anchor stamping into `run_scan`

Union commit-dirty package/app URIs into `needs_narrative` before the narrator fan-out, and stamp `last_updated_commit = HEAD` on each page that is successfully narrated.

**Files:**
- Modify: `packages/graph-wiki-core/src/graph_wiki_core/commands/scan.py`
- Modify: `packages/graph-wiki-core/tests/unit/test_commit_gated_narrative.py`

- [ ] **Step 1: Write the failing test**

Append to `packages/graph-wiki-core/tests/unit/test_commit_gated_narrative.py`:

```python
def test_commit_dirty_entity_is_refreshed_and_restamped(m2a_workspace, monkeypatch) -> None:
    """Scan 1 narrates at head1; scan 2 (files changed, head2) re-narrates the
    package and advances its last_updated_commit to head2."""
    workspace = m2a_workspace
    wiki = workspace / "wiki"
    repo = workspace / "repo"

    heads = {"v": "head1"}
    monkeypatch.setattr(
        scan_mod, "compute_state_gate",
        lambda repo: {"allowed": True, "reason": "clean", "head_commit": heads["v"]},
    )
    # Distinct prose per scan so we can tell a refresh from a restore.
    prose_tag = {"v": "FIRST"}
    monkeypatch.setattr(
        scan_mod.SubagentPool, "run_all",
        _narrate_all_spy(lambda it: f"{prose_tag['v']} prose for {it[0]}"),
    )

    asyncio.run(scan_mod.run_scan(workspace_path=workspace, repo_path=repo, narrate=True))
    assert _fm.load(_page_for(wiki)).metadata.get("last_updated_commit") == "head1"
    assert "FIRST prose for" in _page_for(wiki).read_text(encoding="utf-8")

    # Scan 2: HEAD moved and the package's files changed since head1.
    heads["v"] = "head2"
    prose_tag["v"] = "SECOND"
    monkeypatch.setattr(
        scan_mod, "changed_files_since",
        lambda repo, sha, sub: ["packages/pkg-a/mod.py"],
    )
    asyncio.run(scan_mod.run_scan(workspace_path=workspace, repo_path=repo, narrate=True))
    final = _page_for(wiki).read_text(encoding="utf-8")
    assert "SECOND prose for pkg:org/repo/pkg-a" in final  # refreshed, not restored
    assert _fm.load(_page_for(wiki)).metadata.get("last_updated_commit") == "head2"
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `uv run --package graph-wiki-core pytest packages/graph-wiki-core/tests/unit/test_commit_gated_narrative.py -k "refreshed_and_restamped" -v`
Expected: FAIL — scan 1's `last_updated_commit == "head1"` assertion fails (no stamping yet); even once that's wired, scan 2 would only re-narrate via the gate.

- [ ] **Step 3: Union the commit-gate into `needs_narrative`**

In `run_scan`, inside the `if conn is not None:` block, immediately **after** the entity-write `append_log(...)` call that ends at line 701 and **before** the `# Step 9b: narrator fan-out` comment (line 703), insert:

```python
            # M2a commit-gate: re-narrate package/app entities whose files
            # changed since their recorded last_updated_commit (Living Wiki M2).
            commit_dirty = _commit_dirty_uris(
                wiki,
                repo,
                conn,
                state_gate.get("head_commit"),
                _compute_collision_set(conn, ADMITTED_KINDS, _kind_list_fns()),
            )
            if commit_dirty:
                entity_write_result.needs_narrative |= commit_dirty
                append_log(
                    wiki,
                    "scan",
                    f"commit-gate: {len(commit_dirty)} entity(s) flagged for re-narration",
                    detail=None,
                    silent=True,
                    raise_exception=True,
                )
```

- [ ] **Step 4: Stamp `last_updated_commit` on narrated pages**

In `run_scan`, find the narrator inject loop (lines 768-779). Insert a `head` lookup just **before** the loop (after `inject_collision_set = _compute_collision_set(...)` at line 766, before `for item, prose in narrator_result.successes:` at line 768):

```python
            head = state_gate.get("head_commit")
```

Then, inside the loop's `try` block (currently lines 773-775):

```python
                try:
                    inject_narrative(entity_page_path, prose)
                    entities_narrated.append(uri_inner)
```

change to:

```python
                try:
                    inject_narrative(entity_page_path, prose)
                    if head:
                        set_frontmatter_value(
                            entity_page_path, LAST_UPDATED_COMMIT_KEY, head
                        )
                    entities_narrated.append(uri_inner)
```

- [ ] **Step 5: Run the full M2a test file**

Run: `uv run --package graph-wiki-core pytest packages/graph-wiki-core/tests/unit/test_commit_gated_narrative.py -v`
Expected: PASS — all of it: the 5 `_commit_dirty_uris` gate tests, both `survives` persistence tests (including the now-green `last_updated_commit == "head1"` anchor assertions), and `refreshed_and_restamped`.

- [ ] **Step 6: Commit**

```bash
git add packages/graph-wiki-core/src/graph_wiki_core/commands/scan.py \
        packages/graph-wiki-core/tests/unit/test_commit_gated_narrative.py
git commit -m "feat(scan): commit-gate narrative refresh + stamp last_updated_commit"
```

---

## Task 6: Document `last_updated_commit` in the backward-compat rule

The new key is scanner-stamped but preserved — neither a pure human key nor a `SCANNER_OWNED_KEYS` member. Record it so a future contributor does not "tidy" it into `SCANNER_OWNED_KEYS` (which would silently break the gate).

**Files:**
- Modify: `.claude/rules/backward-compatibility.md`

- [ ] **Step 1: Make the edit**

In `.claude/rules/backward-compatibility.md`, the `entity` content bullet currently reads (M1 wording):

```markdown
    * **human-owned** sections (e.g. `## Purpose`, `## Public API`, any hand-added H2) and human frontmatter keys (`status`, `last_reviewed`, `owner`, `notes`) are preserved across re-scan and should be treated like other curated content.
```

Add a third sub-bullet immediately after it:

```markdown
    * **provenance** key `last_updated_commit` is scanner-stamped (the HEAD at which `## Narrative` was last regenerated) but is preserved across re-scan and is NOT in `SCANNER_OWNED_KEYS`. It gates commit-driven narrative refresh (Living Wiki M2a) — do not move it into `SCANNER_OWNED_KEYS`.
```

- [ ] **Step 2: Verify**

Run: `grep -n "last_updated_commit\|provenance" .claude/rules/backward-compatibility.md`
Expected: the new sub-bullet is present.

- [ ] **Step 3: Commit**

```bash
git add .claude/rules/backward-compatibility.md
git commit -m "docs: document last_updated_commit provenance key (M2a)"
```

---

## Task 7: Full-suite regression gate

Confirm M2a did not regress the M1 preservation behavior, the entity-writer byte-stability/idempotence suite, or the scan tests.

**Files:** none (verification only)

- [ ] **Step 1: Run the wiki-io suite**

Run: `uv run --package wiki-io pytest packages/wiki-io/tests/ -v`
Expected: PASS. In particular `test_section_merge.py`, `test_entity_writer.py` (incl. `test_write_entities_second_run_all_unchanged` / determinism), `test_inject_narrative.py`, and the new `test_set_frontmatter_value.py` / `test_extract_narrative.py` are green. (If `test_index_generator.py::test_snapshot_against_agent_research` runs and fails, it is the pre-existing live-`graph.db` snapshot test — unrelated to M2a, which touches no index output. Confirm the diff is unrelated before accepting.)

- [ ] **Step 2: Run the graph-wiki-core scan suite**

Run: `uv run --package graph-wiki-core pytest packages/graph-wiki-core/tests/ -v`
Expected: PASS. Watch specifically:
- `tests/unit/test_scan_narrate.py` — `narrate=False` still skips fan-out; placeholders behave (now also exercised by restore — narratives that were never filled stay placeholder because `prior_narratives` is empty on a first scan).
- `tests/unit/test_scan_decontainerize_parity.py` (`__snapshots__/test_scan_decontainerize_parity.ambr`) — if this snapshot diffs, inspect it: M2a adds a `last_updated_commit` frontmatter line **only to narrated pages**. If the parity fixture narrates, the snapshot legitimately gains that line; regenerate with `uv run --package graph-wiki-core pytest packages/graph-wiki-core/tests/unit/test_scan_decontainerize_parity.py --snapshot-update` and confirm the only change is the added `last_updated_commit` key (plus persisted narrative prose) before accepting.
- `tests/unit/test_commit_gated_narrative.py` — all green.

- [ ] **Step 3: Final confirmation**

Run: `git log --oneline -6 && git status`
Expected: the 6 task commits (Tasks 1-6) present; clean working tree.

---

## Self-Review

**1. Spec coverage** (roadmap §3 D3 + §4 "M2 — Commit-gated incremental updates", foundation slice):
- "Per-entity `last_updated_commit` frontmatter (sourced from graph `last_indexed_commit`)" → Task 1 (key + setter), Task 5 (stamped from `state_gate.head_commit`, which is HEAD = the same commit the graph records). ✓
- "refresh `## Narrative` **only if the entity's files changed** since `last_updated_commit`" → Task 3 (`_commit_dirty_uris` via `changed_files_since`), Task 5 (union into `needs_narrative`). ✓
- Implicit prerequisite the roadmap line assumes ("refresh only what changed" requires unchanged narratives to **persist**) → Task 4 (snapshot/restore). This was discovered to be missing in `main`; folded into the foundation per the user's decision. ✓
- Out-of-scope items (file-map content-hash re-description, template reconciliation, human-section drift flagging, updated-churn reduction) correctly deferred with rationale. ✓

**2. Placeholder scan:** No "TBD"/"handle edge cases"/"add error handling" — every code/test step shows complete content. The only conditional notes are (a) Task 4 Step 2/6's explicit "anchor assertions go green in Task 5" sequencing guidance, and (b) Task 7's snapshot-regeneration instructions — both give exact commands and the exact expected diff, not placeholders.

**3. Type/name consistency:** `LAST_UPDATED_COMMIT_KEY`, `set_frontmatter_value`, `_render_page_text`, `extract_narrative`, `_NARRATIVE_PLACEHOLDER`, `_snapshot_narratives`, `_commit_dirty_uris`, `changed_files_since`, and `prior_narratives` are spelled identically across tasks and tests. `changed_files_since(repo, since_sha, sub_path)` matches the existing `wiki_io/git_state.py:59` signature. `_entity_page_path(wiki, kind, node, uri, collision_set)` and `_compute_collision_set(conn, ADMITTED_KINDS, _kind_list_fns())` match their existing call sites in `scan.py`.

**4. Known interactions verified against the code:**
- The merge resets `## Narrative` (empirically reproduced in "Key finding") → Task 4 restore is required and sufficient; restore is gated to never clobber fresh prose (D-G) and runs independent of `narrate` (D-F).
- `last_updated_commit` is non-scanner → `merge_frontmatter` preserves it (Task 1 regression test) and `set_frontmatter_value` appends it last, matching `merge_frontmatter`'s human-key ordering → re-render byte-stability holds, so the M1 idempotence tests stay green.
- Stamping happens only after a successful `inject_narrative` (D-B) → no anchor advances for `--no-narrate` or failed narration → no accumulation bug.
- The commit-gate runs after `write_entities` (so `needs_narrative` exists) but before the narrator fan-out builds `narrator_items` (line 703) → unioned URIs are narrated this scan.
