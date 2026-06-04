# Living Wiki M2c — Commit-Gate Consolidation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make the M2a/M2b commit-gate the *actual* driver of incremental scans — by stopping the per-scan `updated` churn that masks it (#3), unifying anchor stamping so a failed describer can't strand a `— TODO` row behind an advanced anchor (Part 3), and extending the commit-gated file-map re-description to `test_suite` entities (#4).

**Architecture:** Three disjoint changes, sequenced #3 → Part 3 → #4. (#3) `write_entities` gains a body comparison that ignores scanner-owned section *bodies* and skips the write when only those differ, so structurally-unchanged pages bucket `unchanged`. (Part 3) `scan.py` stops stamping the anchor inside the narrator loop; instead a single post-describe pass stamps `last_updated_commit` iff the page has good prose or a re-described row **and** no remaining file-map `— TODO`. (#4) `_commit_dirty_changes` and the test-suite file-map branch are brought to package/app parity, reusing M2b's `changed_files_since` + `_changed_rel_paths` verbatim.

**Tech Stack:** Python 3.11+, `uv` workspace, `pytest` + `pytest-asyncio`, `python-frontmatter`. Tests mock the LLM fan-out at the `SubagentPool.run_all` boundary (project fixture pattern; mirrors `test_commit_gated_file_map.py`).

---

## Background the engineer needs

**The churn (#3).** `write_entities` (`packages/wiki-io/src/wiki_io/entity_writer.py:896-1065`) renders each entity page from its template, merging back human-owned H2 sections but **resetting** the three scanner-owned sections — `## Narrative`, `## File map[ - <name>]`, `## Referenced in wiki` (`_is_scanner_owned_heading`, `:532-544`) — to their template placeholders. Later scan steps re-populate them. The bucketing compares `old_bytes == new_bytes` (`:1001`): because the on-disk page has *filled* scanner sections and the freshly-rendered `new_content` has *placeholder* scanner sections, every populated page differs → bucketed `updated` every scan. That makes `refreshed = created | updated` contain ~every page, so the commit-gate's `fm_targets = refreshed | commit_dirty` (`scan.py:982`) is dominated by `refreshed` and `commit_dirty` is never the deciding factor.

The fix (Approach B, spec §3.3 D3): compare frontmatter in full but the body **modulo scanner-owned section bodies**. When a page `existed` and the comparison is equal → `unchanged` and **skip the write** (leave real on-disk content untouched). Otherwise write as today.

> ⚠️ The `## File map` heading carries a name suffix that differs between the two sides: `write_entities` renders the template token `{{PACKAGE_SLUG}}` → `## File map - <slug>` (e.g. `## File map - pkg_pkg-a`), while the injected deterministic block (`build_file_map`) emits `## File map - <dir-basename>` (e.g. `## File map - pkg-a`). So the comparison helper **must collapse each scanner section's heading+body to a constant per-type token** — comparing scanner headings literally would always differ and defeat the fix.

> ✅ Frontmatter is stable across no-op scans: `scanner_frontmatter_for_node` (`entity_writer.py:697`) derives keys purely from the graph (no wall-clock timestamp), and `merge_frontmatter` (`:358`) is deterministic. So comparing frontmatter in full is safe — a no-op rescan yields identical frontmatter.

**The narrator-path residual (Part 3, spec §1.2 / §3.3 D4).** The M2b review-fix (`f74e8e36`) gated the *file-map* restamp on row-refill (`scan.py:1179-1193`), but the *narrator* loop still stamps the anchor inline on any good prose (`scan.py:912-916`), regardless of unfilled rows. A commit-dirty page that (1) re-narrates with good prose, (2) drops a changed file-map row to `— TODO`, and (3) has the describer **fail** to refill it, ends up with its anchor advanced to HEAD — so the next scan sees no diff and the `— TODO` is stranded forever. Fix: the narrator loop only *records* good-prose URIs; a single post-Step-10c pass stamps `(good_prose_uris | redescribed_uris)` iff `not file_map_todo_paths(page)`.

> ⚠️ This Part-3 change breaks the existing M2a integration tests in `test_commit_gated_narrative.py`: their fan-out spy `_narrate_all_spy` returns non-JSON for the `code_reader` role, so `parse_file_describer_output` yields `{}` and file-map rows stay `— TODO` permanently. Under the new gate those pages would never stamp, failing the M2a anchor assertions. Task 3 updates that spy to fill rows (mirroring M2b's `_fanout_spy`) — a legitimate harness fix that leaves the narrative-specific assertions intact.

**test_suite parity (#4, spec §3.1 D1/D2).** `test_suite` nodes populate the `path` column via the 6-column projection in `_list_by_kind` (`queries.py:876`), so `node.path` == the suite's repo-relative root == the base `build_dir_file_map(repo / node.path)` already uses and the `sub_path` `changed_files_since` expects. Suite `## File map` rows are keyed package-root-relative to that same root, so `_changed_rel_paths(changed, node.path)` matches with **no new transform**. #4 = M2b with `test_suite` added to the `_commit_dirty_changes` kind loop and the Step 10b-ts branch brought to package/app parity (trigger via `fm_targets`, preserved-drop, `redescribed_uris`).

---

## File structure

| File | Responsibility | Change |
|------|----------------|--------|
| `packages/wiki-io/src/wiki_io/entity_writer.py` | Entity page render + bucketing | Add `_equal_modulo_scanner` + `_normalize_scanner_bodies`; gate the `existed` write on it (Tasks 1–2) |
| `packages/wiki-io/tests/test_equal_modulo_scanner.py` | Unit tests for the comparison helper | **Create** (Task 1) |
| `packages/graph-wiki-core/src/graph_wiki_core/commands/scan.py` | Scan orchestration: commit-gate, narrator inject, file-map inject, anchor stamping | Part 3 unified stamping (Task 3); #4 `_commit_dirty_changes` loop (Task 4) + Step 10b-ts parity (Task 5) |
| `packages/graph-wiki-core/tests/unit/test_updated_churn.py` | Churn integration tests (5–8) | **Create** (Task 2) |
| `packages/graph-wiki-core/tests/unit/test_commit_gated_file_map.py` | Stamping/file-map integration tests | Add Part-3 tests 9–11 (Task 3) |
| `packages/graph-wiki-core/tests/unit/test_commit_gated_narrative.py` | M2a narrative/anchor tests | Update `_narrate_all_spy` to fill rows (Task 3) |
| `packages/graph-wiki-core/tests/unit/test_commit_gated_test_suite.py` | Suite commit-gate integration tests (1–4) | **Create** (Task 5) |

Sequencing rationale (spec §7): #3 first unmasks the gate so #4's integration behavior is observable without monkeypatching `write_entities`, and makes the residual the common case; Part 3 then unifies stamping on the now-load-bearing gate; #4 extends to suites on top of the unified stamping. #3 (`entity_writer`) and Part 3 (`scan.py` anchor logic) touch disjoint code.

---

## Task 1: `_equal_modulo_scanner` comparison helper (#3, part 1 of 2)

A pure helper in `wiki_io.entity_writer` that decides whether two full page texts are equal once scanner-owned section bodies (and the variable `## File map` heading suffix) are normalized out. No bucketing change yet — just the helper + its unit tests.

**Files:**
- Modify: `packages/wiki-io/src/wiki_io/entity_writer.py` (add helpers near `_split_h2_sections`, `:547`)
- Test: `packages/wiki-io/tests/test_equal_modulo_scanner.py` (create)

- [ ] **Step 1: Write the failing tests**

Create `packages/wiki-io/tests/test_equal_modulo_scanner.py`:

```python
"""Living Wiki M2c #3: body comparison that ignores scanner-owned section bodies."""

from __future__ import annotations

from wiki_io.entity_writer import _equal_modulo_scanner

# A page whose scanner sections are FILLED (as found on disk after a scan).
_FILLED = """---
uri: pkg:org/repo/pkg-a
kind: package
language: python
---
# pkg-a

## Narrative
Real narrative prose written by the narrator.

## Purpose
> A human wrote this.

## File map - pkg-a
### pkg-a/
| Path | Kind | Description |
|---|---|---|
| `mod.py` | file | does a thing |

## Referenced in wiki
- [[entities/other]]
"""

# The SAME page as write_entities re-renders it: scanner sections reset to
# placeholders AND the File-map heading uses the slug suffix (`pkg_pkg-a`),
# not the dir basename (`pkg-a`). Frontmatter + preamble + human section match.
_PLACEHOLDER = """---
uri: pkg:org/repo/pkg-a
kind: package
language: python
---
# pkg-a

## Narrative
_(scanner will populate on next scan)_

## Purpose
> A human wrote this.

## File map - pkg_pkg-a
> TODO: <Overview>

### pkg_pkg-a/
| Path | Kind | Description |
|---|---|---|
| `<file>` | file | — TODO |

## Referenced in wiki
_(scanner will populate on next scan)_
"""


def test_equal_when_only_scanner_bodies_and_filemap_heading_differ() -> None:
    # Despite different scanner bodies AND a different `## File map` heading
    # suffix, the two pages are equal modulo scanner sections.
    assert _equal_modulo_scanner(_FILLED, _PLACEHOLDER) is True


def test_not_equal_when_human_section_differs() -> None:
    edited = _FILLED.replace("> A human wrote this.", "> A human EDITED this.")
    assert _equal_modulo_scanner(edited, _PLACEHOLDER) is False


def test_not_equal_when_frontmatter_differs() -> None:
    edited = _FILLED.replace("language: python", "language: rust")
    assert _equal_modulo_scanner(edited, _PLACEHOLDER) is False


def test_not_equal_when_preamble_differs() -> None:
    edited = _FILLED.replace("# pkg-a", "# pkg-a-renamed")
    assert _equal_modulo_scanner(edited, _PLACEHOLDER) is False


def test_not_equal_when_human_section_added() -> None:
    added = _PLACEHOLDER.replace(
        "## Referenced in wiki",
        "## Extra Notes\n> new human section\n\n## Referenced in wiki",
    )
    assert _equal_modulo_scanner(_FILLED, added) is False


def test_identical_text_is_equal() -> None:
    assert _equal_modulo_scanner(_FILLED, _FILLED) is True


def test_malformed_text_is_not_equal() -> None:
    # A parse failure must be conservative — treated as "changed" (write).
    assert _equal_modulo_scanner("\x00not yaml frontmatter", _FILLED) is False
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `uv run --package wiki-io pytest packages/wiki-io/tests/test_equal_modulo_scanner.py -v`
Expected: FAIL — `ImportError: cannot import name '_equal_modulo_scanner'`.

- [ ] **Step 3: Implement the helpers**

In `packages/wiki-io/src/wiki_io/entity_writer.py`, immediately after `_split_h2_sections` (which ends at `:566`) and before `_merge_preserved_sections` (`:569`), insert:

```python
def _scanner_section_token(heading: str) -> str:
    """Collapse a scanner-owned H2 heading to a constant per-type token.

    The `## File map - <name>` heading carries a name suffix that differs
    between the template render (`{{PACKAGE_SLUG}}` → the slug) and the injected
    deterministic block (the directory basename), so the suffix — like the body —
    must be normalized away. The token distinguishes the three scanner sections
    so an added/removed section still registers as a difference.
    """
    h = heading.strip()
    if h == "## Narrative":
        return "\x00scanner:narrative\x00"
    if h.startswith("## File map"):
        return "\x00scanner:filemap\x00"
    # `_is_scanner_owned_heading` guarantees the only remaining case.
    return "\x00scanner:referenced\x00"


def _normalize_scanner_bodies(body: str) -> str:
    """Return `body` with every scanner-owned section (heading + body) replaced
    by a constant token, leaving the preamble and human sections verbatim.

    Used by `_equal_modulo_scanner`: two bodies that differ only inside scanner
    sections (or in the `## File map` heading suffix) normalize to the same text.
    """
    preamble, sections = _split_h2_sections(body)
    parts = [preamble]
    for heading, chunk in sections:
        if _is_scanner_owned_heading(heading):
            parts.append(_scanner_section_token(heading) + "\n")
        else:
            parts.append(chunk)
    return "".join(parts)


def _equal_modulo_scanner(old_text: str, new_text: str) -> bool:
    """True iff two full page texts are equal once scanner-owned section bodies
    are normalized out: identical frontmatter (compared in full), identical
    preamble, identical human sections, and the same set/order of scanner
    sections (their bodies and `## File map` heading suffixes ignored).

    Conservative on any parse failure → returns False (caller writes the page).
    """
    try:
        old_post = frontmatter.loads(old_text)
        new_post = frontmatter.loads(new_text)
    except Exception:  # noqa: BLE001 — a malformed page must fall back to "write"
        return False
    if dict(old_post.metadata) != dict(new_post.metadata):
        return False
    return _normalize_scanner_bodies(old_post.content) == _normalize_scanner_bodies(
        new_post.content
    )
```

(`frontmatter` is already imported at module top — it backs `frontmatter.load` used elsewhere in this file.)

- [ ] **Step 4: Run the tests to verify they pass**

Run: `uv run --package wiki-io pytest packages/wiki-io/tests/test_equal_modulo_scanner.py -v`
Expected: PASS (7 tests).

- [ ] **Step 5: Commit**

```bash
git add packages/wiki-io/src/wiki_io/entity_writer.py packages/wiki-io/tests/test_equal_modulo_scanner.py
git commit -m "feat(entity-writer): add _equal_modulo_scanner body comparison (M2c #3)

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

---

## Task 2: skip-write for scanner-only differences (#3, part 2 of 2)

Wire `_equal_modulo_scanner` into `write_entities` bucketing: when a page `existed` and differs only inside scanner sections, bucket it `unchanged` and skip the write. Add full-scan integration tests (spec tests 5–8).

**Files:**
- Modify: `packages/wiki-io/src/wiki_io/entity_writer.py:999-1013` (the `existed` branch of the bucketing)
- Test: `packages/graph-wiki-core/tests/unit/test_updated_churn.py` (create)

- [ ] **Step 1: Write the failing integration tests**

Create `packages/graph-wiki-core/tests/unit/test_updated_churn.py`:

```python
"""Living Wiki M2c #3: a no-op rescan buckets populated pages `unchanged`
(scanner-body churn no longer forces `updated`)."""

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

_PKG_A = "pkg:org/repo/pkg-a"

_FILE_MAP = (
    "## File map - pkg-a\nTODO\n\n### pkg-a/\nTODO\n\n"
    "| Path | Kind | Description |\n|---|---|---|\n"
    "| `mod.py` | file | — TODO |\n"
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


def _fanout_spy(*, prose):
    """narrator items -> prose(item); code_reader items -> JSON filling each
    TODO path (so file maps reach a steady, fully-described state)."""

    async def _run_all(self, *, items, task, role, model_id, max_concurrency):
        from subagent_runtime.pool import FanOutResult

        result = FanOutResult()
        if role == "narrator":
            result.successes = [(it, prose(it)) for it in items]
        else:
            result.successes = [
                (it, json.dumps({p: f"desc {p}" for p in it[3]})) for it in items
            ]
        return result

    return _run_all


@pytest.fixture
def churn_workspace(tmp_path, monkeypatch):
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
        lambda path, **kw: (_FILE_MAP if str(path).endswith("pkg-a") else None),
    )
    monkeypatch.setattr(
        scan_mod, "compute_state_gate",
        lambda repo: {"allowed": True, "reason": "clean", "head_commit": "head1"},
    )
    monkeypatch.setattr(
        scan_mod.SubagentPool, "run_all",
        _fanout_spy(prose=lambda it: f"PROSE for {it[0]}"),
    )
    return workspace


def _page(wiki: Path, uri: str = _PKG_A) -> Path:
    return next(
        p for p in (wiki / "entities").glob("*.md")
        if _fm.load(p).metadata.get("uri") == uri
    )


def test_no_op_rescan_reports_zero_updated(churn_workspace, monkeypatch) -> None:
    """[spec test 5] A second scan with no repo change buckets the populated
    page `unchanged`; its content is byte-identical (not rewritten to
    placeholder)."""
    workspace = churn_workspace
    wiki = workspace / "wiki"
    repo = workspace / "repo"
    # Scan 1 fills Narrative + File-map row.
    asyncio.run(scan_mod.run_scan(workspace_path=workspace, repo_path=repo, narrate=True))
    text1 = _page(wiki).read_text(encoding="utf-8")
    assert "PROSE for pkg:org/repo/pkg-a" in text1
    assert "desc mod.py" in text1

    # Scan 2: nothing changed since head1.
    monkeypatch.setattr(scan_mod, "changed_files_since", lambda *a: [])
    result = asyncio.run(
        scan_mod.run_scan(workspace_path=workspace, repo_path=repo, narrate=True)
    )
    assert result.entities_updated == []          # the fix: no churn
    text2 = _page(wiki).read_text(encoding="utf-8")
    assert text2 == text1                          # byte-identical, not rewritten
    assert "_(scanner will populate on next scan)_" not in text2


def test_human_section_edit_forces_updated(churn_workspace, monkeypatch) -> None:
    """[spec test 6] A hand-edit to a human-owned section forces `updated`."""
    workspace = churn_workspace
    wiki = workspace / "wiki"
    repo = workspace / "repo"
    asyncio.run(scan_mod.run_scan(workspace_path=workspace, repo_path=repo, narrate=True))

    # Hand-edit the human-owned `## Purpose` body on disk.
    page = _page(wiki)
    edited = page.read_text(encoding="utf-8").replace(
        "## Purpose", "## Purpose\nHUMAN EDIT MARKER", 1
    )
    page.write_text(edited, encoding="utf-8")

    monkeypatch.setattr(scan_mod, "changed_files_since", lambda *a: [])
    result = asyncio.run(
        scan_mod.run_scan(workspace_path=workspace, repo_path=repo, narrate=True)
    )
    assert _PKG_A in result.entities_updated       # human-section drift forces updated
    assert "HUMAN EDIT MARKER" in _page(wiki).read_text(encoding="utf-8")


def test_frontmatter_only_change_forces_updated(churn_workspace, monkeypatch) -> None:
    """[spec test 7] A scanner-frontmatter delta forces `updated` even with
    identical bodies."""
    workspace = churn_workspace
    wiki = workspace / "wiki"
    repo = workspace / "repo"
    asyncio.run(scan_mod.run_scan(workspace_path=workspace, repo_path=repo, narrate=True))

    # Mutate the graph: change the package language (a scanner-owned fm key).
    conn = sqlite3.connect(workspace / ".graph" / "code.db")
    try:
        conn.execute(
            "UPDATE nodes SET attrs_json='{\"language\": \"rust\"}' "
            "WHERE uri='pkg:org/repo/pkg-a'"
        )
        conn.commit()
    finally:
        conn.close()

    monkeypatch.setattr(scan_mod, "changed_files_since", lambda *a: [])
    result = asyncio.run(
        scan_mod.run_scan(workspace_path=workspace, repo_path=repo, narrate=True)
    )
    assert _PKG_A in result.entities_updated
    assert _fm.load(_page(wiki)).metadata.get("language") == "rust"


def test_idempotence_across_all_three_scanner_sections(churn_workspace, monkeypatch) -> None:
    """[spec test 8] A page with a filled Narrative + File map (the two
    expensive scanner sections) rescans to `unchanged`; prose + descriptions
    survive."""
    workspace = churn_workspace
    wiki = workspace / "wiki"
    repo = workspace / "repo"
    asyncio.run(scan_mod.run_scan(workspace_path=workspace, repo_path=repo, narrate=True))

    monkeypatch.setattr(scan_mod, "changed_files_since", lambda *a: [])
    result = asyncio.run(
        scan_mod.run_scan(workspace_path=workspace, repo_path=repo, narrate=True)
    )
    assert result.entities_updated == []
    text = _page(wiki).read_text(encoding="utf-8")
    assert "PROSE for pkg:org/repo/pkg-a" in text
    assert "desc mod.py" in text
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `uv run --package graph-wiki-core pytest packages/graph-wiki-core/tests/unit/test_updated_churn.py -v`
Expected: `test_no_op_rescan_reports_zero_updated` and `test_idempotence_across_all_three_scanner_sections` FAIL — `assert result.entities_updated == []` fails because the page is bucketed `updated` (scanner-body churn). (Tests 6 and 7 may already pass — they assert `updated` is set, which is current behavior — but must still pass after the fix.)

- [ ] **Step 3: Implement the skip-write**

In `packages/wiki-io/src/wiki_io/entity_writer.py`, replace the `existed` branch of the bucketing (`:999-1008`):

```python
                    if existed:
                        old_bytes = page_path.read_bytes()
                        if old_bytes == new_bytes:
                            unchanged.append(uri)
                            continue
                        page_path.write_text(new_content, encoding="utf-8")
                        page_path.chmod(0o644)
                        updated.append(uri)
                        if _detect_structural_change(existing_fm, merged_fm):
                            needs_narrative.add(uri)
```

with:

```python
                    if existed:
                        old_bytes = page_path.read_bytes()
                        # M2c #3 (Approach B): absorb scanner-body churn. The
                        # three scanner-owned sections are reset to placeholders
                        # in `new_content` and re-populated by later scan steps;
                        # a page whose only differences are inside those sections
                        # is `unchanged` — skip the write so the real on-disk
                        # body (filled by a prior scan) is left untouched.
                        if old_bytes == new_bytes:
                            unchanged.append(uri)
                            continue
                        try:
                            old_text = old_bytes.decode("utf-8")
                        except UnicodeDecodeError:
                            old_text = None
                        if old_text is not None and _equal_modulo_scanner(
                            old_text, new_content
                        ):
                            unchanged.append(uri)
                            continue
                        page_path.write_text(new_content, encoding="utf-8")
                        page_path.chmod(0o644)
                        updated.append(uri)
                        if _detect_structural_change(existing_fm, merged_fm):
                            needs_narrative.add(uri)
```

- [ ] **Step 4: Run the new tests to verify they pass**

Run: `uv run --package graph-wiki-core pytest packages/graph-wiki-core/tests/unit/test_updated_churn.py -v`
Expected: PASS (4 tests).

- [ ] **Step 5: Run the existing wiki-io + M2a/M2b suites to verify no regression**

Run: `uv run --package wiki-io pytest packages/wiki-io/tests/ -q && uv run --package graph-wiki-core pytest packages/graph-wiki-core/tests/unit/test_commit_gated_narrative.py packages/graph-wiki-core/tests/unit/test_commit_gated_file_map.py -q`
Expected: PASS. (M2a/M2b stamping still works because, pre-Part-3, the narrator loop still stamps inline; their commit-dirty pages now bucket `unchanged` but are still re-narrated/re-file-mapped via `commit_dirty`.)

- [ ] **Step 6: Commit**

```bash
git add packages/wiki-io/src/wiki_io/entity_writer.py packages/graph-wiki-core/tests/unit/test_updated_churn.py
git commit -m "feat(entity-writer): skip write when only scanner bodies differ (M2c #3)

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

---

## Task 3: unified, refill-gated anchor stamping (Part 3)

Stop stamping the anchor inside the narrator inject loop. Record good-prose URIs and their page paths instead; replace the M2b restamp block with one post-Step-10c pass that stamps `(good_prose_uris | redescribed_uris)` iff the page has no remaining file-map `— TODO`. Update the M2a integration spy to fill rows (so its anchor assertions hold under the new gate). Add spec tests 9–11.

**Files:**
- Modify: `packages/graph-wiki-core/src/graph_wiki_core/commands/scan.py` — narrator loop (`:892-924`) and restamp block (`:1169-1193`)
- Modify: `packages/graph-wiki-core/tests/unit/test_commit_gated_narrative.py` — `_narrate_all_spy` (`:184-194`)
- Test: `packages/graph-wiki-core/tests/unit/test_commit_gated_file_map.py` — add tests 9–11

- [ ] **Step 1: Write the failing test for the residual (spec test 9)**

Append to `packages/graph-wiki-core/tests/unit/test_commit_gated_file_map.py`:

```python
def test_good_prose_with_failed_describe_does_not_strand_todo(
    m2b_workspace, monkeypatch
) -> None:
    """[spec test 9] A commit-dirty page that re-narrates with GOOD prose AND
    drops a row whose describer then returns nothing must NOT advance its anchor
    — the page stays commit-dirty so the next scan retries. Fails on current
    `main` (the narrator loop stamps on good prose regardless of TODO rows)."""
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
    # Scan 1: good prose + both rows filled → anchor head1.
    asyncio.run(scan_mod.run_scan(workspace_path=workspace, repo_path=repo, narrate=True))
    assert _fm.load(_page(wiki)).metadata.get("last_updated_commit") == "head1"

    # Scan 2: mod.py changed → its row drops to `— TODO`. Narration is GOOD
    # prose, but the describer returns NOTHING, so the row is never refilled.
    heads["v"] = "head2"
    monkeypatch.setattr(
        scan_mod, "changed_files_since",
        lambda repo, sha, sub: ["packages/pkg-a/mod.py"],
    )
    monkeypatch.setattr(
        scan_mod.SubagentPool, "run_all",
        _fanout_spy(prose=lambda it: f"prose {it[0]}", descs=_descs_empty),
    )
    asyncio.run(scan_mod.run_scan(workspace_path=workspace, repo_path=repo, narrate=True))
    t2 = _page(wiki).read_text(encoding="utf-8")
    assert "| `mod.py` | file | — TODO |" in t2     # row dropped, left unfilled
    assert "D1:util.py" in t2                         # untouched row preserved
    # The anchor must stay at head1 despite the good prose (refill-gate).
    assert _fm.load(_page(wiki)).metadata.get("last_updated_commit") == "head1"

    # Scan 3 at head3: describer succeeds now → row refilled, anchor advances.
    heads["v"] = "head3"
    desc_tag["v"] = "D3"
    monkeypatch.setattr(
        scan_mod, "changed_files_since",
        lambda repo, sha, sub: ["packages/pkg-a/mod.py"],
    )
    monkeypatch.setattr(
        scan_mod.SubagentPool, "run_all",
        _fanout_spy(prose=lambda it: f"prose {it[0]}", descs=_descs_tagged(desc_tag)),
    )
    asyncio.run(scan_mod.run_scan(workspace_path=workspace, repo_path=repo, narrate=True))
    t3 = _page(wiki).read_text(encoding="utf-8")
    assert "D3:mod.py" in t3
    assert _fm.load(_page(wiki)).metadata.get("last_updated_commit") == "head3"


def test_narrated_only_page_still_stamps(m2b_workspace, monkeypatch) -> None:
    """[spec test 10] A re-narrated page with good prose and NO unfilled
    file-map rows advances its anchor to HEAD (M2a behavior preserved)."""
    workspace = m2b_workspace
    wiki = workspace / "wiki"
    repo = workspace / "repo"
    heads = {"v": "head1"}
    monkeypatch.setattr(
        scan_mod, "compute_state_gate",
        lambda repo: {"allowed": True, "reason": "clean", "head_commit": heads["v"]},
    )
    monkeypatch.setattr(
        scan_mod.SubagentPool, "run_all",
        _fanout_spy(prose=lambda it: f"prose {it[0]}", descs=_descs_tagged({"v": "D1"})),
    )
    # Scan 1: rows filled, anchor head1.
    asyncio.run(scan_mod.run_scan(workspace_path=workspace, repo_path=repo, narrate=True))
    assert _fm.load(_page(wiki)).metadata.get("last_updated_commit") == "head1"

    # Scan 2: files changed since head1 → re-narrate with good prose; the changed
    # row is refilled (describer succeeds) so no TODO remains → anchor advances.
    heads["v"] = "head2"
    monkeypatch.setattr(
        scan_mod, "changed_files_since",
        lambda repo, sha, sub: ["packages/pkg-a/mod.py"],
    )
    monkeypatch.setattr(
        scan_mod.SubagentPool, "run_all",
        _fanout_spy(prose=lambda it: f"prose {it[0]}", descs=_descs_tagged({"v": "D2"})),
    )
    asyncio.run(scan_mod.run_scan(workspace_path=workspace, repo_path=repo, narrate=True))
    assert _fm.load(_page(wiki)).metadata.get("last_updated_commit") == "head2"
```

(Spec test 11 — "empty narration alone still does not stamp" — is already covered by the existing `test_empty_narration_alone_does_not_stamp` in this file; it must keep passing.)

- [ ] **Step 2: Run the new tests to verify test 9 fails**

Run: `uv run --package graph-wiki-core pytest packages/graph-wiki-core/tests/unit/test_commit_gated_file_map.py::test_good_prose_with_failed_describe_does_not_strand_todo -v`
Expected: FAIL on the scan-2 assertion `last_updated_commit == "head1"` — current `main` stamps head2 via the narrator loop's inline stamp despite the unfilled row.

- [ ] **Step 3: Rewrite the narrator inject loop to record (not stamp)**

In `scan.py`, replace the narrator-stamp block (`:892-924`). Replace this:

```python
        entities_narrated: list[str] = []
        narrator_errors: list[str] = []
        # M2b §3.4: URIs the narrator loop stamped this scan (non-empty prose).
        # The shared-anchor restamp dedups against this set.
        narr_stamped: set[str] = set()
        if narrator_result is not None:
            inject_collision_set = _compute_collision_set(
                conn, ADMITTED_KINDS, _kind_list_fns(),
            )

            for item, prose in narrator_result.successes:
                uri_inner, kind_inner, node_inner = item
                entity_page_path = _entity_page_path(
                    wiki, kind_inner, node_inner, uri_inner, inject_collision_set,
                )
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
                except Exception as inject_exc:  # noqa: BLE001 — partial-success
                    narrator_errors.append(
                        f"{uri_inner}: inject_narrative failed: {inject_exc!r}"
                    )
            for err in narrator_result.errors:
                uri_inner, _kind_inner, _node_inner = err.item
                narrator_errors.append(f"{uri_inner}: {err.exception!r}")
```

with:

```python
        entities_narrated: list[str] = []
        narrator_errors: list[str] = []
        # M2c Part 3 (§3.3 D4): the narrator loop no longer stamps the anchor
        # inline. It records which pages got real prose (`good_prose_uris`) and
        # where each narrated page lives (`narrated_page_paths`); a single
        # refill-gated pass after Step 10c does the stamping. This closes the
        # narrator-path residual where good prose advanced the anchor even though
        # a dropped file-map row was never refilled.
        good_prose_uris: set[str] = set()
        narrated_page_paths: dict[str, Path] = {}
        if narrator_result is not None:
            inject_collision_set = _compute_collision_set(
                conn, ADMITTED_KINDS, _kind_list_fns(),
            )

            for item, prose in narrator_result.successes:
                uri_inner, kind_inner, node_inner = item
                entity_page_path = _entity_page_path(
                    wiki, kind_inner, node_inner, uri_inner, inject_collision_set,
                )
                try:
                    inject_narrative(entity_page_path, prose)
                    narrated_page_paths[uri_inner] = entity_page_path
                    # Empty-prose guard (M2b §3.4): empty narration records
                    # nothing, so it can never mint an anchor on its own.
                    if head and prose.strip():
                        good_prose_uris.add(uri_inner)
                    entities_narrated.append(uri_inner)
                except Exception as inject_exc:  # noqa: BLE001 — partial-success
                    narrator_errors.append(
                        f"{uri_inner}: inject_narrative failed: {inject_exc!r}"
                    )
            for err in narrator_result.errors:
                uri_inner, _kind_inner, _node_inner = err.item
                narrator_errors.append(f"{uri_inner}: {err.exception!r}")
```

- [ ] **Step 4: Replace the M2b restamp block with the unified pass**

In `scan.py`, replace the restamp block (`:1169-1193`):

```python
        # M2b §3.4 shared-anchor rider: a page whose File map was re-described
        # this scan (>=1 changed row dropped & re-queued, or an unknown anchor
        # forced a full re-describe) must advance last_updated_commit to HEAD so
        # the next scan's diff baseline includes this re-description (idempotence
        # + cost-churn guard). Pages the narrator loop already stamped (non-empty
        # prose) are skipped — the empty-prose guard's intent is preserved. A page
        # whose describer (Step 10c) failed to refill its dropped rows still shows
        # `— TODO`; it is NOT stamped, so it stays commit-dirty and the next scan
        # retries the describe rather than stranding the TODO behind an advanced
        # anchor (final-review issue 1: stamp on refill, not merely on drop).
        if narrate and head and redescribed_uris:
            for uri_inner, _node, page_path in file_mapped_pages:
                if (
                    uri_inner in redescribed_uris
                    and uri_inner not in narr_stamped
                    and not file_map_todo_paths(page_path)
                ):
                    try:
                        set_frontmatter_value(
                            page_path, LAST_UPDATED_COMMIT_KEY, head
                        )
                    except Exception as exc:  # noqa: BLE001 — non-fatal stamp
                        logger.warning(
                            "anchor restamp failed for %s: %s", uri_inner, exc
                        )
```

with:

```python
        # M2c Part 3 (§3.3 D4): unified, refill-gated anchor stamping. A page
        # advances last_updated_commit to HEAD iff it was re-narrated with good
        # prose OR had a file-map row re-described this scan, AND no file-map
        # `— TODO` row remains. The single gate covers both stamp reasons:
        #   - good prose with an unrefilled dropped row → NOT stamped (stays
        #     commit-dirty; next scan retries the describe) — closes the residual;
        #   - a re-described page whose rows are all refilled → stamped
        #     (idempotence + cost-churn guard, preserves M2b);
        #   - a narrated-only page with no file-map TODO (file_map_todo_paths
        #     returns [] for pages with all rows filled or no File map section) →
        #     stamped, preserving M2a behavior.
        if narrate and head:
            stamp_page_paths: dict[str, Path] = dict(narrated_page_paths)
            for uri_inner, _node, page_path in file_mapped_pages:
                stamp_page_paths.setdefault(uri_inner, page_path)
            for uri_inner in good_prose_uris | redescribed_uris:
                page_path = stamp_page_paths.get(uri_inner)
                if page_path is None or file_map_todo_paths(page_path):
                    continue
                try:
                    set_frontmatter_value(
                        page_path, LAST_UPDATED_COMMIT_KEY, head
                    )
                except Exception as exc:  # noqa: BLE001 — non-fatal stamp
                    logger.warning(
                        "anchor stamp failed for %s: %s", uri_inner, exc
                    )
```

- [ ] **Step 5: Run the new tests to verify they pass**

Run: `uv run --package graph-wiki-core pytest packages/graph-wiki-core/tests/unit/test_commit_gated_file_map.py -v`
Expected: PASS — including the new `test_good_prose_with_failed_describe_does_not_strand_todo` and `test_narrated_only_page_still_stamps`, plus all existing M2b tests (their describers fill rows, so the gate is a no-op for them).

- [ ] **Step 6: Update the M2a spy and verify M2a tests pass under the new gate**

Run: `uv run --package graph-wiki-core pytest packages/graph-wiki-core/tests/unit/test_commit_gated_narrative.py -v`
Expected: FAIL — the integration tests (e.g. `test_commit_dirty_entity_is_refreshed_and_restamped`) now fail their anchor assertions, because `_narrate_all_spy` returns non-JSON for the `code_reader` role, leaving the file-map row `— TODO` so the new gate blocks the stamp.

Fix `_narrate_all_spy` in `test_commit_gated_narrative.py` (`:184-194`). Replace:

```python
def _narrate_all_spy(prose_fn):
    """Return an async SubagentPool.run_all that narrates every item via prose_fn."""

    async def _run_all(self, *, items, task, role, model_id, max_concurrency):
        from subagent_runtime.pool import FanOutResult

        result = FanOutResult()
        result.successes = [(it, prose_fn(it)) for it in items]
        return result

    return _run_all
```

with:

```python
def _narrate_all_spy(prose_fn):
    """Return an async SubagentPool.run_all that narrates every item via prose_fn.

    For the code_reader role it returns JSON descriptions filling every TODO
    file-map row, so the M2c Part-3 refill gate (stamp iff no `— TODO` remains)
    is satisfied and the anchor-stamping assertions hold. The narrative-specific
    assertions in these tests are unaffected.
    """

    async def _run_all(self, *, items, task, role, model_id, max_concurrency):
        from subagent_runtime.pool import FanOutResult

        result = FanOutResult()
        if role == "narrator":
            result.successes = [(it, prose_fn(it)) for it in items]
        else:  # code_reader — item == (uri, ws_dict, page_path, todo_paths)
            import json as _json

            result.successes = [
                (it, _json.dumps({p: f"desc {p}" for p in it[3]})) for it in items
            ]
        return result

    return _run_all
```

Re-run: `uv run --package graph-wiki-core pytest packages/graph-wiki-core/tests/unit/test_commit_gated_narrative.py -v`
Expected: PASS (all M2a tests).

- [ ] **Step 7: Commit**

```bash
git add packages/graph-wiki-core/src/graph_wiki_core/commands/scan.py packages/graph-wiki-core/tests/unit/test_commit_gated_file_map.py packages/graph-wiki-core/tests/unit/test_commit_gated_narrative.py
git commit -m "fix(scan): unify refill-gated anchor stamping; close narrator-path residual (M2c Part 3)

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

---

## Task 4: extend the commit-gate to test_suite entities (#4, part 1 of 2)

Add `test_suite` to the `_commit_dirty_changes` kind loop so a content-changed suite flows into `needs_narrative` (via the existing `needs_narrative.update(commit_dirty.keys())`) and into `fm_targets`. The helper is otherwise kind-agnostic.

**Files:**
- Modify: `packages/graph-wiki-core/src/graph_wiki_core/commands/scan.py:569-608` (`_commit_dirty_changes`)
- Test: `packages/graph-wiki-core/tests/unit/test_commit_gated_narrative.py` (add a unit test)

- [ ] **Step 1: Write the failing unit test**

Append to `packages/graph-wiki-core/tests/unit/test_commit_gated_narrative.py`:

```python
def test_commit_dirty_includes_test_suite(tmp_path, monkeypatch) -> None:
    """[M2c #4] A test_suite page with an anchor whose files changed since it
    appears in the commit-dirty map (previously the kind loop skipped suites)."""
    import types

    from wiki_io.entity_writer import LAST_UPDATED_COMMIT_KEY, short_filename

    wiki = tmp_path / "wiki"
    uri = "test_suite:org/repo/pkg-a/tests"
    suite_path = "packages/pkg-a/tests"
    node = types.SimpleNamespace(
        attrs={"uri": uri, "suite_kind": "unit", "path": suite_path},
        path=suite_path,
        name="pkg-a-unit-tests",
        kind="test_suite",
    )
    stem = short_filename(uri, frozenset(), suite_kind="unit", pkg_for_suite="pkg-a")
    page = wiki / "entities" / f"{stem}.md"
    page.parent.mkdir(parents=True, exist_ok=True)
    page.write_text(
        f"---\nuri: {uri}\nkind: test_suite\n{LAST_UPDATED_COMMIT_KEY}: anchor_sha\n"
        f"---\n# {uri}\n\n## Narrative\nprose\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(
        scan_mod, "_kind_list_fns",
        lambda: {
            "package": lambda conn: [],
            "app": lambda conn: [],
            "test_suite": lambda conn: [node],
        },
    )
    monkeypatch.setattr(
        scan_mod, "changed_files_since",
        lambda repo, sha, sub: ["packages/pkg-a/tests/test_mod.py"],
    )
    dirty = scan_mod._commit_dirty_changes(
        wiki, tmp_path / "repo", object(), "head_sha", frozenset()
    )
    assert dirty == {uri: ["packages/pkg-a/tests/test_mod.py"]}
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `uv run --package graph-wiki-core pytest packages/graph-wiki-core/tests/unit/test_commit_gated_narrative.py::test_commit_dirty_includes_test_suite -v`
Expected: FAIL — `assert dirty == {...}` fails (`dirty == {}`): the kind loop is `("package", "app")`, so the suite node is never consulted.

- [ ] **Step 3: Extend the kind loop**

In `scan.py`, update `_commit_dirty_changes`. Change the loop line (`:583`):

```python
    for kind in ("package", "app"):
```

to:

```python
    for kind in ("package", "app", "test_suite"):
```

And update the docstring's first sentence (`:569-570`) for accuracy:

```python
    """Map `package`/`app`/`test_suite` URIs whose files changed since the commit
    recorded on their page (`last_updated_commit`) to the changed-file list.
```

- [ ] **Step 4: Run the test to verify it passes**

Run: `uv run --package graph-wiki-core pytest packages/graph-wiki-core/tests/unit/test_commit_gated_narrative.py::test_commit_dirty_includes_test_suite -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add packages/graph-wiki-core/src/graph_wiki_core/commands/scan.py packages/graph-wiki-core/tests/unit/test_commit_gated_narrative.py
git commit -m "feat(scan): commit-gate test_suite entities (M2c #4 part 1)

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

---

## Task 5: bring the test_suite file-map branch to package/app parity (#4, part 2 of 2)

Change Step 10b-ts's trigger from `if refreshed:` to the suite slice of `fm_targets = refreshed | commit_dirty`, apply the M2b preserved-drop keyed on `node.path`, and record re-described suites in `redescribed_uris` so the unified stamp pass (Task 3) picks them up. Add suite integration tests (spec tests 1–4).

**Files:**
- Modify: `packages/graph-wiki-core/src/graph_wiki_core/commands/scan.py:1038-1071` (Step 10b-ts branch)
- Test: `packages/graph-wiki-core/tests/unit/test_commit_gated_test_suite.py` (create)

- [ ] **Step 1: Write the failing integration tests**

Create `packages/graph-wiki-core/tests/unit/test_commit_gated_test_suite.py`:

```python
"""Living Wiki M2c #4: commit-gated File-map row re-description for test_suite
entities (package/app parity)."""

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
from wiki_io.entity_writer import EntityWriteResult

_SUITE = "test_suite:org/repo/pkg-a/tests"
_SUITE_PATH = "packages/pkg-a/tests"

# A suite file map with TWO rows (keyed suite-root-relative).
_SUITE_MAP_TWO_ROWS = (
    "## File map - unit_tests_pkg-a\nTODO\n\n### tests/\nTODO\n\n"
    "| Path | Kind | Description |\n|---|---|---|\n"
    "| `test_mod.py` | file | — TODO |\n"
    "| `test_util.py` | file | — TODO |\n"
)


def _seed_one_suite(db_path: Path) -> None:
    from graph_io import schema

    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(db_path)
    try:
        schema.apply_schema(conn)
        conn.execute(
            "INSERT INTO nodes(kind, name, path, line, attrs_json, uri) VALUES "
            "('test_suite', 'pkg-a-unit-tests', 'packages/pkg-a/tests', NULL, "
            "'{\"suite_kind\": \"unit\", \"path\": \"packages/pkg-a/tests\", "
            "\"owner_kind\": \"package\"}', 'test_suite:org/repo/pkg-a/tests')"
        )
        conn.commit()
    finally:
        conn.close()


def _fanout_spy(*, prose, descs):
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
    def _f(item) -> dict[str, str]:
        return {p: f"{tag['v']}:{p}" for p in item[3]}

    return _f


@pytest.fixture
def suite_workspace(tmp_path, monkeypatch):
    workspace = tmp_path / "workspace"
    wiki = workspace / "wiki"
    repo = workspace / "repo"
    (wiki / ".graph-wiki").mkdir(parents=True)
    (wiki / "CLAUDE.md").write_text("# Wiki\n")
    (wiki / "log.md").write_text("", encoding="utf-8")
    repo.mkdir()
    monkeypatch.setenv("GRAPH_WIKI_WORKSPACE", str(workspace))
    _seed_one_suite(workspace / ".graph" / "code.db")
    monkeypatch.setattr(
        scan_mod, "_cg_run_build",
        lambda repo, ws, *, full: (exit_codes.SUCCESS, "", ""),
    )
    monkeypatch.setattr(
        scan_mod, "make_llm", lambda role, *, model_override=None: MagicMock()
    )
    # Step 10b-ts uses build_dir_file_map for suites (not build_file_map).
    monkeypatch.setattr(
        scan_mod, "build_dir_file_map",
        lambda path, **kw: (
            _SUITE_MAP_TWO_ROWS if str(path).endswith("tests") else None
        ),
    )
    return workspace


def _page(wiki: Path, uri: str = _SUITE) -> Path:
    return next(
        p for p in (wiki / "entities").glob("*.md")
        if _fm.load(p).metadata.get("uri") == uri
    )


def test_suite_redescribe_on_change(suite_workspace, monkeypatch) -> None:
    """[spec test 1] A changed file under the suite root re-describes that row;
    unchanged suite rows keep their prior descriptions."""
    workspace = suite_workspace
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
    t1 = _page(wiki).read_text(encoding="utf-8")
    assert "D1:test_mod.py" in t1
    assert "D1:test_util.py" in t1

    heads["v"] = "head2"
    desc_tag["v"] = "D2"
    monkeypatch.setattr(
        scan_mod, "changed_files_since",
        lambda repo, sha, sub: ["packages/pkg-a/tests/test_mod.py"],
    )
    asyncio.run(scan_mod.run_scan(workspace_path=workspace, repo_path=repo, narrate=True))
    t2 = _page(wiki).read_text(encoding="utf-8")
    assert "D2:test_mod.py" in t2        # changed row re-described
    assert "D1:test_mod.py" not in t2
    assert "D1:test_util.py" in t2       # unchanged row preserved
    assert _fm.load(_page(wiki)).metadata.get("last_updated_commit") == "head2"


def test_suite_trigger_gap_commit_dirty_not_refreshed(suite_workspace, monkeypatch) -> None:
    """[spec test 2] A commit-dirty suite that write_entities reports as
    `unchanged` still gets its file map re-injected and the changed row
    re-described. Fails without the `commit_dirty` extension on the suite
    branch."""
    workspace = suite_workspace
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
    assert "D1:test_mod.py" in _page(wiki).read_text(encoding="utf-8")

    heads["v"] = "head2"
    desc_tag["v"] = "D2"
    monkeypatch.setattr(
        scan_mod, "write_entities",
        lambda conn, wiki_arg, kinds: EntityWriteResult(unchanged=[_SUITE]),
    )
    monkeypatch.setattr(
        scan_mod, "changed_files_since",
        lambda repo, sha, sub: ["packages/pkg-a/tests/test_mod.py"],
    )
    asyncio.run(scan_mod.run_scan(workspace_path=workspace, repo_path=repo, narrate=True))
    t2 = _page(wiki).read_text(encoding="utf-8")
    assert "D2:test_mod.py" in t2
    assert "D1:test_mod.py" not in t2
    assert "D1:test_util.py" in t2


def test_suite_path_namespace_nested_file(suite_workspace, monkeypatch) -> None:
    """[spec test 3] A changed file nested under the suite root matches and
    re-describes (guards the repo-relative vs suite-root-relative transform)."""
    workspace = suite_workspace
    wiki = workspace / "wiki"
    repo = workspace / "repo"
    heads = {"v": "head1"}
    monkeypatch.setattr(
        scan_mod, "compute_state_gate",
        lambda repo: {"allowed": True, "reason": "clean", "head_commit": heads["v"]},
    )
    # Suite map with a NESTED row so the transform must strip the suite root.
    nested_map = (
        "## File map - unit_tests_pkg-a\nTODO\n\n### tests/\nTODO\n\n"
        "| Path | Kind | Description |\n|---|---|---|\n"
        "| `sub/test_deep.py` | file | — TODO |\n"
        "| `test_util.py` | file | — TODO |\n"
    )
    monkeypatch.setattr(
        scan_mod, "build_dir_file_map",
        lambda path, **kw: (nested_map if str(path).endswith("tests") else None),
    )
    desc_tag = {"v": "D1"}
    monkeypatch.setattr(
        scan_mod.SubagentPool, "run_all",
        _fanout_spy(prose=lambda it: f"prose {it[0]}", descs=_descs_tagged(desc_tag)),
    )
    asyncio.run(scan_mod.run_scan(workspace_path=workspace, repo_path=repo, narrate=True))
    assert "D1:sub/test_deep.py" in _page(wiki).read_text(encoding="utf-8")

    heads["v"] = "head2"
    desc_tag["v"] = "D2"
    monkeypatch.setattr(
        scan_mod, "changed_files_since",
        lambda repo, sha, sub: ["packages/pkg-a/tests/sub/test_deep.py"],
    )
    asyncio.run(scan_mod.run_scan(workspace_path=workspace, repo_path=repo, narrate=True))
    t2 = _page(wiki).read_text(encoding="utf-8")
    assert "D2:sub/test_deep.py" in t2     # nested changed row re-described
    assert "D1:test_util.py" in t2         # sibling preserved


def test_suite_no_narrate_keeps_cost_cache_and_anchor(suite_workspace, monkeypatch) -> None:
    """[spec test 4] A --no-narrate rescan refreshes suite file-map structure but
    re-describes no row and stamps no suite anchor."""
    workspace = suite_workspace
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

    heads["v"] = "head2"
    desc_tag["v"] = "D2"
    monkeypatch.setattr(
        scan_mod, "changed_files_since",
        lambda repo, sha, sub: ["packages/pkg-a/tests/test_mod.py"],
    )
    asyncio.run(scan_mod.run_scan(workspace_path=workspace, repo_path=repo, narrate=False))
    t2 = _page(wiki).read_text(encoding="utf-8")
    assert "D1:test_mod.py" in t2          # NOT re-described (cost cache intact)
    assert "D2:test_mod.py" not in t2
    assert _fm.load(_page(wiki)).metadata.get("last_updated_commit") == "head1"
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `uv run --package graph-wiki-core pytest packages/graph-wiki-core/tests/unit/test_commit_gated_test_suite.py -v`
Expected: FAIL — `test_suite_redescribe_on_change` and `test_suite_path_namespace_nested_file` fail (the changed row is NOT re-described: the suite branch has no preserved-drop); `test_suite_trigger_gap_commit_dirty_not_refreshed` fails (the suite branch triggers only on `if refreshed:`, so a commit-dirty-but-unchanged suite is skipped entirely). (Note: under current `main` the suite branch grafts `preserved` whole, so scan 2 keeps `D1:test_mod.py` rather than producing `D2`.)

- [ ] **Step 3: Rewrite the Step 10b-ts branch to package/app parity**

In `scan.py`, replace the test-suite file-map branch (`:1038-1071`):

```python
            # Step 10b-ts: test-suite File-map injection. Mirrors Step 10b but
            # for test_suite entity pages — the suite map starts at the suite
            # root (node.attrs["path"]) and is UNPARTITIONED (every tracked file
            # under the root). Reuses the shared collision set and the same
            # snapshot→merge durability path (preserved=...). Appends each
            # injected page to file_mapped_pages so Step 10c fills its TODO rows.
            if refreshed:
                for node in queries.list_test_suites(conn):
                    if not isinstance(node.attrs, dict):
                        continue
                    suite_uri = node.attrs.get("uri")
                    if not suite_uri or suite_uri not in refreshed:
                        continue
                    suite_path = node.attrs.get("path")
                    if not suite_path:
                        continue
                    block = build_dir_file_map(repo / suite_path, max_depth=max_depth)
                    if not block:
                        continue
                    ts_page_path = _entity_page_path(
                        wiki, "test_suite", node, suite_uri, fm_collision_set,
                    )
                    try:
                        inject_file_map(
                            ts_page_path,
                            block,
                            preserved=prior_file_map_descs.get(suite_uri),
                        )
                        entities_file_mapped.append(suite_uri)
                        file_mapped_pages.append((suite_uri, node, ts_page_path))
                    except Exception as fm_exc:  # noqa: BLE001 — partial-success
                        file_map_errors.append(
                            f"{suite_uri}: inject_file_map failed: {fm_exc!r}"
                        )
```

with:

```python
            # Step 10b-ts: test-suite File-map injection — commit-gated parity
            # with Step 10b (M2c #4 §3.1). The suite map starts at the suite root
            # (node.path, authoritative — D1) and is UNPARTITIONED (every tracked
            # file under the root). Trigger is the suite slice of fm_targets so a
            # commit-dirty-but-structurally-unchanged suite is still re-injected;
            # the preserved-drop re-queues changed rows as `— TODO`, and
            # re-described suites join redescribed_uris for the unified stamp.
            if fm_targets:
                for node in queries.list_test_suites(conn):
                    if not isinstance(node.attrs, dict):
                        continue
                    suite_uri = node.attrs.get("uri")
                    if not suite_uri or suite_uri not in fm_targets:
                        continue
                    suite_path = node.path
                    if not suite_path:
                        continue
                    block = build_dir_file_map(repo / suite_path, max_depth=max_depth)
                    if not block:
                        continue
                    preserved = dict(prior_file_map_descs.get(suite_uri) or {})
                    if narrate and suite_uri in commit_dirty:
                        changed = commit_dirty[suite_uri]
                        if changed is None:
                            # Unknown anchor: no preserved row can be trusted —
                            # drop all, forcing a full re-describe (D-D / §3.1).
                            preserved = {}
                            redescribed_uris.add(suite_uri)
                        else:
                            changed_rel = _changed_rel_paths(changed, suite_path)
                            dropped = {p for p in preserved if p in changed_rel}
                            if dropped:
                                for p in dropped:
                                    preserved.pop(p, None)
                                redescribed_uris.add(suite_uri)
                    ts_page_path = _entity_page_path(
                        wiki, "test_suite", node, suite_uri, fm_collision_set,
                    )
                    try:
                        inject_file_map(
                            ts_page_path,
                            block,
                            preserved=preserved,
                        )
                        entities_file_mapped.append(suite_uri)
                        file_mapped_pages.append((suite_uri, node, ts_page_path))
                    except Exception as fm_exc:  # noqa: BLE001 — partial-success
                        file_map_errors.append(
                            f"{suite_uri}: inject_file_map failed: {fm_exc!r}"
                        )
```

- [ ] **Step 4: Run the suite tests to verify they pass**

Run: `uv run --package graph-wiki-core pytest packages/graph-wiki-core/tests/unit/test_commit_gated_test_suite.py -v`
Expected: PASS (4 tests).

- [ ] **Step 5: Commit**

```bash
git add packages/graph-wiki-core/src/graph_wiki_core/commands/scan.py packages/graph-wiki-core/tests/unit/test_commit_gated_test_suite.py
git commit -m "feat(scan): commit-gated suite file-map re-description (M2c #4 part 2)

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

---

## Task 6: full-suite verification + lint

Confirm the whole milestone holds together and nothing regressed across the two affected packages.

**Files:** none (verification only)

- [ ] **Step 1: Run the full graph-wiki-core + wiki-io test suites**

Run: `uv run --package graph-wiki-core pytest packages/graph-wiki-core/tests/ -q && uv run --package wiki-io pytest packages/wiki-io/tests/ -q`
Expected: PASS, no failures. (Pay attention to `test_scan_parity.py`, `test_commands_scan.py`, `test_scan_narrate.py`, and `test_entity_writer.py` — they exercise the touched code paths.)

- [ ] **Step 2: Lint the changed files**

Run: `uv run ruff check packages/wiki-io/src/wiki_io/entity_writer.py packages/graph-wiki-core/src/graph_wiki_core/commands/scan.py packages/wiki-io/tests/test_equal_modulo_scanner.py packages/graph-wiki-core/tests/unit/test_updated_churn.py packages/graph-wiki-core/tests/unit/test_commit_gated_test_suite.py packages/graph-wiki-core/tests/unit/test_commit_gated_file_map.py packages/graph-wiki-core/tests/unit/test_commit_gated_narrative.py`
Expected: `All checks passed!` (fix any import-sort `I001` or line-length findings the tooling reports, then re-run).

- [ ] **Step 3: Confirm no orphaned `narr_stamped` reference remains**

Run: `grep -rn "narr_stamped" packages/graph-wiki-core/src/`
Expected: no output (the symbol was fully removed in Task 3).

- [ ] **Step 4: Final commit (only if Step 2 required lint fixes)**

```bash
git add -A
git commit -m "style(m2c): lint fixes for commit-gate consolidation

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

---

## Self-review notes (spec coverage)

- Spec §3.1 #4 part 1 (kind loop) → Task 4. Part 2 (trigger + preserved-drop + `redescribed_uris`, `node.path` per D1) → Task 5.
- Spec §3.2 #3 Approach B (`_equal_modulo_scanner` + skip-write, all three scanner sections) → Tasks 1–2. Frontmatter compared in full; human/structural edits force `updated` (tests 6, 7).
- Spec §3.3 Part 3 (record good prose, drop inline stamp, unified refill-gated pass over file-mapped + narrated-only pages) → Task 3.
- Spec §5 tests: 1–4 → Task 5; 5–8 → Task 2; 9–10 → Task 3; 11 → existing `test_empty_narration_alone_does_not_stamp` (kept green in Task 3 Step 5).
- Type consistency: `good_prose_uris: set[str]`, `narrated_page_paths: dict[str, Path]`, `redescribed_uris: set[str]`, `file_mapped_pages: list[tuple[str, Any, Path]]`, `commit_dirty: dict[str, list[str] | None]`, `fm_targets` (set) — all consistent across the narrator loop, Step 10b/10b-ts, and the unified stamp pass.
- Out of scope (spec §4) — not touched: Approach A (`_merge_preserved_sections` inversion + snapshot/restore deletion), template reconciliation (#1/M2d), human-section drift flagging (#2/M2e), content-hash ledger.
```
