# Guidance Index Pages Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Auto-generate `wiki/guidance/index.md` + `wiki/guidance/<topic>/index.md` on every ingest, and add a navigational `## Guidance` section to the scan-owned main `wiki/index.md`.

**Architecture:** Guidance sub-index rendering lives in `wiki_io/update_index.py` next to its flat category-index siblings, called from `update_index()` (which already runs in every ingest tail — no new call sites). The main-index `## Guidance` section is a pure filesystem scan in `wiki_io/index_generator.py`, rendered after `## Sources` / before `## Work`, omitted when empty, and excluded from the banner's curated-page count. `guidance_io.paths.list_pages` is changed to exclude `index.md` so the new generated files never appear as content pages.

**Tech Stack:** Python 3.11, pytest, `uv` workspace (packages `wiki-io` and `guidance-io`). No new dependencies.

**Spec:** `docs/superpowers/specs/2026-06-09-guidance-index-pages-design.md`

---

## File structure

| File | Change | Responsibility |
|---|---|---|
| `packages/guidance-io/src/guidance_io/paths.py` | Modify `list_pages` | Exclude `index.md` from the topic-dir glob |
| `packages/guidance-io/tests/unit/test_paths.py` | Add 1 test | `list_pages` exclusion |
| `packages/wiki-io/src/wiki_io/update_index.py` | Add `topic_label`, `scan_guidance_topics`, `render_guidance_topic_index`, `render_guidance_root_index`, `update_guidance_indexes`; extend `GENERATED_FILES`; call from `update_index()` | Generate the two guidance index levels at ingest cadence |
| `packages/wiki-io/tests/test_update_index_guidance.py` | New module | All wiki-io guidance-index unit tests |
| `packages/wiki-io/src/wiki_io/index_generator.py` | Add `_scan_guidance_topics`, `_render_guidance_section`; extend `GENERATED_FILES`; wire into `_render` | `## Guidance` section in the main index at scan cadence |
| `packages/wiki-io/tests/test_index_generator.py` | Add `TestGuidanceSection` class | Main-index section tests |
| `plugins/graph-wiki/agents/ingestor.md` | One doc line in step 10 | Plugin parity note |

All test commands below run from the repo root: `/Users/pat/Personal/agent-research`. Explicit file paths are passed to pytest, so they are cwd-relative.

**Repo conventions that apply** (from CLAUDE.md / memory):
- Do NOT run `ruff format` across files — the src tree is pre-existing format-dirty. Match surrounding style by hand.
- `wiki-io` puts the module docstring above `from __future__ import annotations` — both modules already do; don't reorder.
- No migrations / GC: the spec explicitly accepts stale index files for deleted topics. Do not add cleanup code.

---

### Task 1: `guidance_io.paths.list_pages` excludes `index.md`

**Files:**
- Modify: `packages/guidance-io/src/guidance_io/paths.py:37-42`
- Test: `packages/guidance-io/tests/unit/test_paths.py`

- [ ] **Step 1: Write the failing test**

Append to `packages/guidance-io/tests/unit/test_paths.py`:

```python
def test_list_pages_excludes_index_md(tmp_path: Path) -> None:
    topic_dir = tmp_path / "wiki" / "guidance" / "react-native"
    topic_dir.mkdir(parents=True)
    (topic_dir / "a-page.md").write_text("---\n---\n", encoding="utf-8")
    (topic_dir / "index.md").write_text("---\n---\n", encoding="utf-8")
    pages = list_pages(tmp_path, "react-native")
    assert [p.name for p in pages] == ["a-page.md"]
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run --package guidance-io pytest packages/guidance-io/tests/unit/test_paths.py::test_list_pages_excludes_index_md -v`
Expected: FAIL — assertion error, `index.md` is in the result list.

- [ ] **Step 3: Implement the exclusion**

In `packages/guidance-io/src/guidance_io/paths.py`, replace the body of `list_pages`:

```python
def list_pages(workspace: Path, topic: str) -> list[Path]:
    """Sorted .md pages under a topic folder (excluding the generated index.md);
    empty list if the folder is absent."""
    topic_dir = guidance_dir(workspace) / topic
    if not topic_dir.is_dir():
        return []
    return sorted(p for p in topic_dir.glob("*.md") if p.name != "index.md")
```

(There are no production callers of `list_pages` yet — verified by grep — so this is safe.)

- [ ] **Step 4: Run the full guidance-io suite**

Run: `uv run --package guidance-io pytest packages/guidance-io/tests/ -v`
Expected: ALL PASS (existing `test_list_pages_returns_sorted_md` still passes — it has no `index.md` fixture).

- [ ] **Step 5: Commit**

```bash
git add packages/guidance-io/src/guidance_io/paths.py packages/guidance-io/tests/unit/test_paths.py
git commit -m "feat(guidance-io): exclude index.md from list_pages"
```

---

### Task 2: `scan_guidance_topics` in `wiki_io/update_index.py`

Collects guidance content pages grouped by topic. Skips dot-dirs, loose `.md` files directly under `guidance/`, `index.md` files, and topic dirs with no content pages.

**Files:**
- Modify: `packages/wiki-io/src/wiki_io/update_index.py` (add functions after `scan_work`, ~line 166)
- Create: `packages/wiki-io/tests/test_update_index_guidance.py`

- [ ] **Step 1: Write the failing tests**

Create `packages/wiki-io/tests/test_update_index_guidance.py`:

```python
"""Guidance index generation (spec: docs/superpowers/specs/2026-06-09-guidance-index-pages-design.md)."""

from __future__ import annotations

import datetime as dt
from pathlib import Path

from wiki_io.update_index import (
    scan_guidance_topics,
    topic_label,
)


def _write_guidance_page(path: Path, *, title: str, summary: str = "", impact: str = "") -> None:
    """Write a guidance page with the flat frontmatter keys the index reads."""
    path.parent.mkdir(parents=True, exist_ok=True)
    lines = ["---", f"title: {title}", "category: guidance"]
    if summary:
        lines.append(f"summary: {summary}")
    if impact:
        lines.append(f"impact: {impact}")
    lines += ["---", "", "Body.", ""]
    path.write_text("\n".join(lines), encoding="utf-8")


class TestTopicLabel:
    def test_hyphens_to_title_case(self):
        assert topic_label("deep-agents") == "Deep Agents"

    def test_underscores_to_title_case(self):
        assert topic_label("react_native") == "React Native"


class TestScanGuidanceTopics:
    def test_absent_guidance_dir_returns_empty(self, tmp_path):
        wiki = tmp_path / "wiki"
        wiki.mkdir()
        assert scan_guidance_topics(wiki) == {}

    def test_empty_guidance_dir_returns_empty(self, tmp_path):
        wiki = tmp_path / "wiki"
        (wiki / "guidance").mkdir(parents=True)
        assert scan_guidance_topics(wiki) == {}

    def test_single_topic_collects_pages(self, tmp_path):
        wiki = tmp_path / "wiki"
        _write_guidance_page(
            wiki / "guidance" / "expo" / "use-eas.md",
            title="Use EAS",
            summary="Build with EAS.",
            impact="high",
        )
        topics = scan_guidance_topics(wiki)
        assert list(topics) == ["expo"]
        entry = topics["expo"][0]
        assert entry["path"] == "guidance/expo/use-eas.md"
        assert entry["title"] == "Use EAS"
        assert entry["summary"] == "Build with EAS."
        assert entry["impact"] == "high"

    def test_topic_with_only_index_md_is_skipped(self, tmp_path):
        wiki = tmp_path / "wiki"
        _write_guidance_page(wiki / "guidance" / "empty-topic" / "index.md", title="Idx")
        _write_guidance_page(wiki / "guidance" / "expo" / "page.md", title="Page")
        assert list(scan_guidance_topics(wiki)) == ["expo"]

    def test_loose_md_under_guidance_is_ignored(self, tmp_path):
        wiki = tmp_path / "wiki"
        _write_guidance_page(wiki / "guidance" / "loose.md", title="Loose")
        assert scan_guidance_topics(wiki) == {}

    def test_dot_dirs_are_skipped(self, tmp_path):
        wiki = tmp_path / "wiki"
        _write_guidance_page(wiki / "guidance" / ".hidden" / "page.md", title="Hidden")
        assert scan_guidance_topics(wiki) == {}

    def test_entries_sorted_by_title_case_insensitive(self, tmp_path):
        wiki = tmp_path / "wiki"
        _write_guidance_page(wiki / "guidance" / "t" / "z.md", title="Zeta")
        _write_guidance_page(wiki / "guidance" / "t" / "a.md", title="alpha")
        _write_guidance_page(wiki / "guidance" / "t" / "m.md", title="Mu")
        topics = scan_guidance_topics(wiki)
        assert [e["title"] for e in topics["t"]] == ["alpha", "Mu", "Zeta"]
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run --package wiki-io pytest packages/wiki-io/tests/test_update_index_guidance.py -v`
Expected: FAIL at import — `ImportError: cannot import name 'scan_guidance_topics'`.

- [ ] **Step 3: Implement `topic_label` + `scan_guidance_topics`**

In `packages/wiki-io/src/wiki_io/update_index.py`, insert after `scan_work` (after line 165, before `render_index`):

```python
def topic_label(topic: str) -> str:
    """Display name for a guidance topic dir: 'deep-agents' -> 'Deep Agents'.

    Same derivation as infer_title's filename fallback.
    """
    return topic.replace("-", " ").replace("_", " ").title()


def scan_guidance_topics(wiki):
    """Scan wiki/guidance/<topic>/*.md into {topic: [entry, ...]}.

    Skips dot-dirs, loose .md files directly under guidance/ (the ingest
    writer always nests under a topic), generated index.md files, and topic
    dirs with no content pages. Entries are sorted by title case-insensitively;
    topics iterate in alphabetical topic-slug order.
    """
    guidance = wiki / "guidance"
    if not guidance.is_dir():
        return {}
    topics = {}
    for topic_dir in sorted(guidance.iterdir()):
        if not topic_dir.is_dir() or topic_dir.name.startswith("."):
            continue
        entries = []
        for md in sorted(topic_dir.glob("*.md")):
            if md.name == "index.md":
                continue
            text = md.read_text(encoding="utf-8", errors="replace")
            fm = parse_frontmatter(text)
            entries.append(
                {
                    "path": f"guidance/{topic_dir.name}/{md.name}",
                    "title": infer_title(md, fm),
                    "summary": fm.get("summary", ""),
                    "impact": fm.get("impact", ""),
                }
            )
        if entries:
            entries.sort(key=lambda e: e["title"].lower())
            topics[topic_dir.name] = entries
    return topics
```

(No type annotations on `scan_guidance_topics` params — matching the untyped `scan_vault`/`parse_frontmatter` style of this module. The nested `triggers:` block in guidance frontmatter is ignored by the regex-subset `parse_frontmatter`, which is fine per spec.)

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run --package wiki-io pytest packages/wiki-io/tests/test_update_index_guidance.py -v`
Expected: ALL PASS (9 tests).

- [ ] **Step 5: Commit**

```bash
git add packages/wiki-io/src/wiki_io/update_index.py packages/wiki-io/tests/test_update_index_guidance.py
git commit -m "feat(wiki-io): scan guidance topics for index generation"
```

---

### Task 3: Guidance index renderers in `wiki_io/update_index.py`

Two pure renderers: the per-topic page list and the root topic list. Frontmatter shape matches `render_category_index` (`title`, `category: index`, `summary`, `updated`).

**Files:**
- Modify: `packages/wiki-io/src/wiki_io/update_index.py` (add after `render_category_index`, ~line 264)
- Test: `packages/wiki-io/tests/test_update_index_guidance.py`

- [ ] **Step 1: Write the failing tests**

Append to `packages/wiki-io/tests/test_update_index_guidance.py` (and extend the import at the top of the file):

```python
from wiki_io.update_index import (
    render_guidance_root_index,
    render_guidance_topic_index,
    scan_guidance_topics,
    topic_label,
)
```

```python
class TestRenderGuidanceTopicIndex:
    def _entry(self, **overrides):
        entry = {
            "path": "guidance/deep-agents/skill-md-requires-yaml-frontmatter.md",
            "title": "SKILL.md Requires YAML Frontmatter",
            "summary": "Every SKILL.md must open with a YAML frontmatter block.",
            "impact": "high",
        }
        entry.update(overrides)
        return entry

    def test_full_entry_with_summary_and_impact(self):
        text = render_guidance_topic_index("deep-agents", [self._entry()], "wiki")
        assert (
            "- [[guidance/deep-agents/skill-md-requires-yaml-frontmatter|SKILL.md Requires YAML Frontmatter]]"
            " — Every SKILL.md must open with a YAML frontmatter block. _(high)_" in text
        )

    def test_missing_summary_omits_dash_segment(self):
        text = render_guidance_topic_index("deep-agents", [self._entry(summary="")], "wiki")
        assert (
            "- [[guidance/deep-agents/skill-md-requires-yaml-frontmatter|SKILL.md Requires YAML Frontmatter]]"
            " _(high)_" in text
        )
        assert "]] —" not in text

    def test_missing_impact_omits_suffix(self):
        text = render_guidance_topic_index("deep-agents", [self._entry(impact="")], "wiki")
        assert "_(" not in text

    def test_frontmatter_and_banner(self):
        today = dt.date.today().isoformat()
        text = render_guidance_topic_index("deep-agents", [self._entry()], "wiki")
        lines = text.splitlines()
        assert lines[0] == "---"
        assert "title: Deep Agents Guidance Index" in lines
        assert "category: index" in lines
        assert f"updated: {today}" in lines
        assert "# Deep Agents Guidance Index" in lines
        assert f"_Auto-generated {today} • 1 pages_" in lines


class TestRenderGuidanceRootIndex:
    def test_topics_sorted_alphabetically_with_counts(self):
        topics = {
            "expo": [{"path": "guidance/expo/a.md", "title": "A", "summary": "", "impact": ""}],
            "deep-agents": [
                {"path": f"guidance/deep-agents/p{i}.md", "title": f"P{i}", "summary": "", "impact": ""}
                for i in range(9)
            ],
        }
        text = render_guidance_root_index(topics, "wiki")
        deep = text.index("- [[guidance/deep-agents/index|Deep Agents]] — 9 pages")
        expo = text.index("- [[guidance/expo/index|Expo]] — 1 page")
        assert deep < expo

    def test_singular_page_count(self):
        topics = {"expo": [{"path": "guidance/expo/a.md", "title": "A", "summary": "", "impact": ""}]}
        text = render_guidance_root_index(topics, "wiki")
        assert "— 1 page" in text
        assert "— 1 pages" not in text

    def test_frontmatter(self):
        today = dt.date.today().isoformat()
        topics = {"expo": [{"path": "guidance/expo/a.md", "title": "A", "summary": "", "impact": ""}]}
        text = render_guidance_root_index(topics, "wiki")
        lines = text.splitlines()
        assert lines[0] == "---"
        assert "title: Guidance Index" in lines
        assert "category: index" in lines
        assert f"updated: {today}" in lines
        assert "# Guidance Index" in lines
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run --package wiki-io pytest packages/wiki-io/tests/test_update_index_guidance.py -v`
Expected: FAIL at import — `ImportError: cannot import name 'render_guidance_root_index'`.

- [ ] **Step 3: Implement the renderers**

In `packages/wiki-io/src/wiki_io/update_index.py`, insert after `render_category_index` (after line 264, before `update_index`):

```python
def render_guidance_topic_index(topic, entries, vault_name):
    """Render guidance/<topic>/index.md: one bullet per guidance page.

    Entry shape: `- [[guidance/<topic>/<slug>|Title]] — <summary> _(<impact>)_`,
    with the summary segment / impact suffix omitted when absent.
    """
    today = dt.date.today().isoformat()
    label = topic_label(topic)
    lines = [
        "---",
        f"title: {label} Guidance Index",
        "category: index",
        f"summary: Auto-generated sub-index of guidance pages in {vault_name}/guidance/{topic}/.",
        f"updated: {today}",
        "---",
        "",
        f"# {label} Guidance Index",
        "",
        f"_Auto-generated {today} • {len(entries)} pages_",
        "",
        f"> Sub-index of all guidance pages in `{vault_name}/guidance/{topic}/`.",
        "> Generated by command-layer index maintenance.",
        "",
    ]
    for e in entries:
        link = vault_wikilink(e["path"], e["title"])
        summary = f" — {e['summary']}" if e["summary"] else ""
        impact = f" _({e['impact']})_" if e["impact"] else ""
        lines.append(f"- {link}{summary}{impact}")
    lines.append("")
    return "\n".join(lines)


def render_guidance_root_index(topics, vault_name):
    """Render guidance/index.md: one bullet per topic, sorted by topic slug."""
    today = dt.date.today().isoformat()
    lines = [
        "---",
        "title: Guidance Index",
        "category: index",
        f"summary: Auto-generated index of guidance topics in {vault_name}/guidance/.",
        f"updated: {today}",
        "---",
        "",
        "# Guidance Index",
        "",
        f"_Auto-generated {today} • {len(topics)} topics_",
        "",
        f"> Index of guidance topics in `{vault_name}/guidance/`.",
        "> Generated by command-layer index maintenance.",
        "",
    ]
    for topic in sorted(topics):
        count = len(topics[topic])
        noun = "page" if count == 1 else "pages"
        link = vault_wikilink(f"guidance/{topic}/index", topic_label(topic))
        lines.append(f"- {link} — {count} {noun}")
    lines.append("")
    return "\n".join(lines)
```

(The topic-index banner keeps the existing `render_category_index` "N pages" shape; the spec's singular/plural rule applies to the root index's per-topic bullets, which is implemented above.)

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run --package wiki-io pytest packages/wiki-io/tests/test_update_index_guidance.py -v`
Expected: ALL PASS.

- [ ] **Step 5: Commit**

```bash
git add packages/wiki-io/src/wiki_io/update_index.py packages/wiki-io/tests/test_update_index_guidance.py
git commit -m "feat(wiki-io): render guidance root + topic index pages"
```

---

### Task 4: `update_guidance_indexes` wired into `update_index()` + `GENERATED_FILES`

The orchestrator: write per-topic indexes then the root index, unconditional `write_text` (matching existing category-index behavior — no byte-compare). Plus the documentation-value `GENERATED_FILES` addition.

**Files:**
- Modify: `packages/wiki-io/src/wiki_io/update_index.py:47` (`GENERATED_FILES`) and `update_index()` (~line 267)
- Test: `packages/wiki-io/tests/test_update_index_guidance.py`

- [ ] **Step 1: Write the failing tests**

Append to `packages/wiki-io/tests/test_update_index_guidance.py` (extend the import block with `GENERATED_FILES`, `update_guidance_indexes`, `update_index`):

```python
from wiki_io.update_index import (
    GENERATED_FILES,
    render_guidance_root_index,
    render_guidance_topic_index,
    scan_guidance_topics,
    topic_label,
    update_guidance_indexes,
    update_index,
)
```

```python
class TestUpdateGuidanceIndexes:
    def test_absent_guidance_writes_nothing(self, tmp_path):
        wiki = tmp_path / "wiki"
        wiki.mkdir()
        update_guidance_indexes(wiki)
        assert not (wiki / "guidance").exists()

    def test_empty_topic_dirs_write_nothing(self, tmp_path):
        wiki = tmp_path / "wiki"
        (wiki / "guidance" / "empty-topic").mkdir(parents=True)
        update_guidance_indexes(wiki)
        assert not (wiki / "guidance" / "index.md").exists()
        assert not (wiki / "guidance" / "empty-topic" / "index.md").exists()

    def test_single_topic_writes_root_and_topic_index(self, tmp_path):
        wiki = tmp_path / "wiki"
        _write_guidance_page(
            wiki / "guidance" / "expo" / "use-eas.md",
            title="Use EAS",
            summary="Build with EAS.",
            impact="high",
        )
        update_guidance_indexes(wiki)

        root = (wiki / "guidance" / "index.md").read_text(encoding="utf-8")
        assert "- [[guidance/expo/index|Expo]] — 1 page" in root

        topic = (wiki / "guidance" / "expo" / "index.md").read_text(encoding="utf-8")
        assert "- [[guidance/expo/use-eas|Use EAS]] — Build with EAS. _(high)_" in topic

    def test_multiple_topics_alphabetical_in_root(self, tmp_path):
        wiki = tmp_path / "wiki"
        _write_guidance_page(wiki / "guidance" / "expo" / "a.md", title="A")
        _write_guidance_page(wiki / "guidance" / "deep-agents" / "b.md", title="B")
        update_guidance_indexes(wiki)
        root = (wiki / "guidance" / "index.md").read_text(encoding="utf-8")
        assert root.index("Deep Agents") < root.index("Expo")
        assert (wiki / "guidance" / "deep-agents" / "index.md").exists()
        assert (wiki / "guidance" / "expo" / "index.md").exists()

    def test_rerun_is_idempotent(self, tmp_path):
        wiki = tmp_path / "wiki"
        _write_guidance_page(wiki / "guidance" / "expo" / "a.md", title="A", impact="low")
        update_guidance_indexes(wiki)
        first_root = (wiki / "guidance" / "index.md").read_bytes()
        first_topic = (wiki / "guidance" / "expo" / "index.md").read_bytes()
        update_guidance_indexes(wiki)
        assert (wiki / "guidance" / "index.md").read_bytes() == first_root
        assert (wiki / "guidance" / "expo" / "index.md").read_bytes() == first_topic

    def test_generated_index_not_listed_as_content_on_rerun(self, tmp_path):
        """The root index must not list itself or topic indexes after a re-run."""
        wiki = tmp_path / "wiki"
        _write_guidance_page(wiki / "guidance" / "expo" / "a.md", title="A")
        update_guidance_indexes(wiki)
        update_guidance_indexes(wiki)
        root = (wiki / "guidance" / "index.md").read_text(encoding="utf-8")
        assert "— 1 page" in root  # index.md not counted as a content page


class TestUpdateIndexIntegration:
    def test_update_index_regenerates_guidance_indexes(self, tmp_path):
        wiki = tmp_path / "wiki"
        _write_guidance_page(wiki / "guidance" / "expo" / "a.md", title="A")
        # update_index also needs the vault root to exist (it does) — no other seeding required.
        update_index(wiki)
        assert (wiki / "guidance" / "index.md").exists()
        assert (wiki / "guidance" / "expo" / "index.md").exists()

    def test_guidance_root_index_in_generated_files(self):
        assert "guidance/index.md" in GENERATED_FILES
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run --package wiki-io pytest packages/wiki-io/tests/test_update_index_guidance.py -v`
Expected: FAIL at import — `ImportError: cannot import name 'update_guidance_indexes'`.

- [ ] **Step 3: Implement `update_guidance_indexes`, extend `GENERATED_FILES`, wire into `update_index()`**

In `packages/wiki-io/src/wiki_io/update_index.py`:

3a. Change line 47 from:

```python
GENERATED_FILES = {"index.md", "log.md"} | set(CATEGORY_INDEX_FILES.values())
```

to:

```python
# guidance/index.md is listed for documentation value; the per-topic
# guidance/<topic>/index.md paths are dynamic and rely on the rel.name
# == "index.md" check that scan_vault applies to every file.
GENERATED_FILES = {"index.md", "log.md", "guidance/index.md"} | set(CATEGORY_INDEX_FILES.values())
```

3b. Add after `render_guidance_root_index` (before `update_index`):

```python
def update_guidance_indexes(wiki: Path) -> None:
    """Regenerate guidance/index.md and guidance/<topic>/index.md.

    Writes nothing when guidance/ is absent or has no topic dirs with content
    pages. Writes are unconditional write_text, matching the category-index
    behavior. Stale indexes for deleted topics are NOT garbage-collected
    (accepted gap — consistent with the rest of the system).
    """
    topics = scan_guidance_topics(wiki)
    if not topics:
        return
    for topic, entries in topics.items():
        content = render_guidance_topic_index(topic, entries, wiki.name)
        (wiki / "guidance" / topic / "index.md").write_text(content, encoding="utf-8")
    root_content = render_guidance_root_index(topics, wiki.name)
    (wiki / "guidance" / "index.md").write_text(root_content, encoding="utf-8")
```

3c. At the end of `update_index()` (after the `work_index_path.write_text(...)` block, currently line 297), add:

```python
    update_guidance_indexes(wiki)
```

- [ ] **Step 4: Run the new module, then the full wiki-io suite**

Run: `uv run --package wiki-io pytest packages/wiki-io/tests/test_update_index_guidance.py -v`
Expected: ALL PASS.

Run: `uv run --package wiki-io pytest packages/wiki-io/tests/ -m "not integration"`
Expected: ALL PASS — in particular `test_update_index_surgical.py` (update_index must still not touch `wiki/index.md`) and `test_lint_wiki.py` / backlink tests (no behavior change for them: generated guidance indexes carry `category: index` and no `[[entities/...]]` links).

- [ ] **Step 5: Commit**

```bash
git add packages/wiki-io/src/wiki_io/update_index.py packages/wiki-io/tests/test_update_index_guidance.py
git commit -m "feat(wiki-io): generate guidance indexes from update_index"
```

---

### Task 5: `## Guidance` section in the main index (`index_generator.py`)

Filesystem scan (no graph), rendered after `## Sources` and before `## Work`, omitted when empty, excluded from the banner's curated-page count.

**Files:**
- Modify: `packages/wiki-io/src/wiki_io/index_generator.py` (`GENERATED_FILES` ~line 112, new helpers after `_scan_work` ~line 509, wiring in `_render` ~line 852, `__all__` ~line 904)
- Test: `packages/wiki-io/tests/test_index_generator.py`

- [ ] **Step 1: Write the failing tests**

Append to `packages/wiki-io/tests/test_index_generator.py`. The module already imports `generate_index` and defines `_write_curated_page`; the existing graph fixture is `make_index_fixture_graph` (conftest). Add imports for the two new helpers near the existing `from wiki_io.index_generator import ...` block:

```python
from wiki_io.index_generator import _render_guidance_section, _scan_guidance_topics
```

```python
def _write_guidance_fixture_page(wiki_root: Path, topic: str, name: str, title: str):
    """Guidance content page under wiki/guidance/<topic>/."""
    _write_curated_page(wiki_root / "guidance" / topic / f"{name}.md", title=title)


class TestGuidanceSection:
    def test_scan_returns_sorted_topic_counts(self, tmp_path):
        wiki_root = tmp_path / "wiki"
        _write_guidance_fixture_page(wiki_root, "expo", "a", "A")
        _write_guidance_fixture_page(wiki_root, "deep-agents", "b", "B")
        _write_guidance_fixture_page(wiki_root, "deep-agents", "c", "C")
        assert _scan_guidance_topics(wiki_root) == [("deep-agents", 2), ("expo", 1)]

    def test_scan_missing_dir_and_index_only_topic(self, tmp_path):
        wiki_root = tmp_path / "wiki"
        wiki_root.mkdir(parents=True)
        assert _scan_guidance_topics(wiki_root) == []
        _write_curated_page(wiki_root / "guidance" / "empty" / "index.md", title="Idx")
        assert _scan_guidance_topics(wiki_root) == []

    def test_render_section_shape(self):
        lines = _render_guidance_section([("deep-agents", 9), ("expo", 1)])
        assert lines[0] == "## Guidance"
        assert "- [[guidance/index|All guidance topics]]" in lines
        assert "- [[guidance/deep-agents/index|Deep Agents]] — 9 pages" in lines
        assert "- [[guidance/expo/index|Expo]] — 1 page" in lines

    def test_render_section_empty_returns_nothing(self):
        assert _render_guidance_section([]) == []

    def test_generate_index_renders_guidance_after_sources_before_work(
        self, tmp_path, make_index_fixture_graph
    ):
        conn = make_index_fixture_graph(
            {"nodes": [("repository", "agent-research", {"uri": "repo:agent-research"})], "edges": []}
        )
        wiki_root = tmp_path / "wiki"
        wiki_root.mkdir(parents=True)
        _write_curated_page(wiki_root / "sources" / "spec.md", title="A Spec")
        _write_curated_page(wiki_root / "work" / "2026-06-09-item.md", title="An Item")
        _write_guidance_fixture_page(wiki_root, "expo", "a", "A Guidance Page")

        generate_index(conn, wiki_root)
        text = (wiki_root / "index.md").read_text(encoding="utf-8")
        assert "## Guidance" in text
        assert "- [[guidance/index|All guidance topics]]" in text
        assert "- [[guidance/expo/index|Expo]] — 1 page" in text
        assert text.index("## Sources") < text.index("## Guidance") < text.index("## Work")

    def test_generate_index_omits_guidance_when_none(self, tmp_path, make_index_fixture_graph):
        conn = make_index_fixture_graph(
            {"nodes": [("repository", "agent-research", {"uri": "repo:agent-research"})], "edges": []}
        )
        wiki_root = tmp_path / "wiki"
        wiki_root.mkdir(parents=True)
        generate_index(conn, wiki_root)
        text = (wiki_root / "index.md").read_text(encoding="utf-8")
        assert "## Guidance" not in text

    def test_guidance_pages_not_in_curated_count(self, tmp_path, make_index_fixture_graph):
        conn = make_index_fixture_graph(
            {"nodes": [("repository", "agent-research", {"uri": "repo:agent-research"})], "edges": []}
        )
        wiki_root = tmp_path / "wiki"
        wiki_root.mkdir(parents=True)
        _write_curated_page(wiki_root / "concepts" / "foo.md", title="Foo")
        _write_guidance_fixture_page(wiki_root, "expo", "a", "A")
        _write_guidance_fixture_page(wiki_root, "expo", "b", "B")

        result = generate_index(conn, wiki_root)
        assert result.curated_count == 1  # the concept only; guidance is navigational

    def test_guidance_index_in_generated_files(self):
        from wiki_io.index_generator import GENERATED_FILES

        assert "guidance/index.md" in GENERATED_FILES
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run --package wiki-io pytest packages/wiki-io/tests/test_index_generator.py -v -k Guidance`
Expected: FAIL at import — `ImportError: cannot import name '_render_guidance_section'`.

- [ ] **Step 3: Implement scan + render + wiring**

In `packages/wiki-io/src/wiki_io/index_generator.py`:

3a. Extend `GENERATED_FILES` (line 112) — add `"guidance/index.md"`:

```python
GENERATED_FILES: frozenset[str] = frozenset(
    {
        "index.md",
        "log.md",
        "concepts/index.md",
        "adrs/index.md",
        "sources/index.md",
        "architecture/index.md",
        # Documentation value: guidance/<topic>/index.md paths are dynamic and
        # rely on the rel.name check in _scan_curated_lane / scan_vault.
        "guidance/index.md",
    }
)
```

3b. Add after `_scan_work` (after line 508, before the rendering-helpers banner comment):

```python
def _scan_guidance_topics(wiki_root: Path) -> list[tuple[str, int]]:
    """Topic dirs under wiki/guidance/ with their content-page counts.

    Filesystem scan, no graph involvement (like the curated lanes). Skips
    dot-dirs, generated index.md files, and topics with zero content pages.
    Sorted alphabetically by topic slug.
    """
    guidance = wiki_root / "guidance"
    if not guidance.is_dir():
        return []
    topics: list[tuple[str, int]] = []
    for topic_dir in sorted(guidance.iterdir()):
        if not topic_dir.is_dir() or topic_dir.name.startswith("."):
            continue
        count = sum(1 for md in topic_dir.glob("*.md") if md.name != "index.md")
        if count:
            topics.append((topic_dir.name, count))
    return topics
```

3c. Add after `_render_curated_section` (after line 786):

```python
def _render_guidance_section(topics: list[tuple[str, int]]) -> list[str]:
    """Render the navigational `## Guidance` section (omitted when empty).

    One lead link to guidance/index plus one link per topic with a page
    count. Guidance pages do NOT count into the banner's curated total.
    """
    if not topics:
        return []
    lines = ["## Guidance", "", f"- {vault_wikilink('guidance/index', 'All guidance topics')}"]
    for topic, count in topics:
        label = topic.replace("-", " ").replace("_", " ").title()
        noun = "page" if count == 1 else "pages"
        lines.append(f"- {vault_wikilink(f'guidance/{topic}/index', label)} — {count} {noun}")
    lines.append("")
    return lines
```

3d. Wire into `_render` — change the curated-lanes tail (currently lines 852-854):

```python
    for stable_id, _lane_dir, section_label in CURATED_LANES:
        lines.extend(_render_curated_section(section_label, curated_entries_by_lane[stable_id]))
    lines.extend(_render_guidance_section(_scan_guidance_topics(wiki_root)))
    lines.extend(_render_curated_section("Work", work_entries))
```

(CURATED_LANES ends with Sources, so this lands the section after `## Sources` and before `## Work`. Do NOT add guidance to `curated_count` — banner semantics unchanged.)

3e. Add to `__all__` (keep alphabetical order within the list):

```python
    "_render_guidance_section",
    "_scan_guidance_topics",
```

- [ ] **Step 4: Run the index_generator suite, then the full wiki-io suite**

Run: `uv run --package wiki-io pytest packages/wiki-io/tests/test_index_generator.py -v`
Expected: ALL PASS — including the pre-existing `test_generate_index_against_fixture_graph` (no guidance fixtures → section omitted, counts unchanged) and determinism/write-if-changed tests.

Run: `uv run --package wiki-io pytest packages/wiki-io/tests/ -m "not integration"`
Expected: ALL PASS.

- [ ] **Step 5: Commit**

```bash
git add packages/wiki-io/src/wiki_io/index_generator.py packages/wiki-io/tests/test_index_generator.py
git commit -m "feat(wiki-io): render Guidance section in main index"
```

---

### Task 6: Plugin parity doc line + final verification

**Files:**
- Modify: `plugins/graph-wiki/agents/ingestor.md` (step 10, ~line 91)

- [ ] **Step 1: Add the doc line**

In `plugins/graph-wiki/agents/ingestor.md`, step 10 currently reads:

```markdown
### 10. Update index
If you edited wiki pages manually, update the relevant `index.md` category sections inline. Command-layer ingest/scan flows update indexes automatically.
```

Change to:

```markdown
### 10. Update index
If you edited wiki pages manually, update the relevant `index.md` category sections inline. Command-layer ingest/scan flows update indexes automatically.
If you wrote guidance pages manually, also refresh `guidance/index.md` and the affected `guidance/<topic>/index.md` (match the existing auto-generated bullet format).
```

- [ ] **Step 2: Lint the changed Python files**

Run: `uv run ruff check packages/wiki-io/src/wiki_io/update_index.py packages/wiki-io/src/wiki_io/index_generator.py packages/guidance-io/src/guidance_io/paths.py packages/wiki-io/tests/test_update_index_guidance.py packages/wiki-io/tests/test_index_generator.py packages/guidance-io/tests/unit/test_paths.py`
Expected: no NEW errors introduced by this change (the src tree has pre-existing lint debt; only fix findings on lines this plan touched). Do NOT run `ruff format`.

- [ ] **Step 3: Run both package suites one final time**

Run: `uv run --package wiki-io pytest packages/wiki-io/tests/ -m "not integration" && uv run --package guidance-io pytest packages/guidance-io/tests/`
Expected: ALL PASS.

- [ ] **Step 4: Commit**

```bash
git add plugins/graph-wiki/agents/ingestor.md
git commit -m "docs(plugin): note manual guidance index refresh in ingestor step 10"
```

---

## Spec coverage checklist (self-review)

- Root index `guidance/index.md` format (frontmatter, banner, sorted topic bullets, 1 page / N pages) → Tasks 3 + 4
- Per-topic index format (frontmatter, banner, title-sorted bullets, summary/impact omission) → Task 3
- Topic display-name derivation (`deep-agents` → "Deep Agents") → Task 2 (`topic_label`) + tests
- `update_guidance_indexes` semantics (absent/empty → no writes; empty topic dirs skipped; loose `.md` ignored; unconditional writes; called from `update_index()`) → Tasks 2 + 4
- Accepted gap (no GC of stale indexes) → documented in `update_guidance_indexes` docstring, no code
- `guidance_io.paths.list_pages` excludes `index.md` → Task 1
- `GENERATED_FILES` additions in both modules (documentation value) → Tasks 4 + 5 with assertions
- `backlink_index.py` untouched; lint untouched → no task (spec: no change required)
- Main index `## Guidance` section (after Sources / before Work, lead link + per-topic counts, omitted when empty, banner count unchanged) → Task 5
- Accepted cadence wrinkle (main index updates on next scan) → inherent to placement in `index_generator.py`, no code
- Plugin parity doc line in ingestor step 10 → Task 6
- All spec test bullets have a matching test (re-run idempotence: `test_rerun_is_idempotent`)
