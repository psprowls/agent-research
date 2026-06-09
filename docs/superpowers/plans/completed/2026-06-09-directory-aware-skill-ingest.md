# Directory-Aware Skill Ingest Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Let `gw wiki ingest` accept a skill *directory* (or its `SKILL.md`), gather `SKILL.md` plus all transitively-linked companion markdown into one combined text, exclude non-markdown with a warning, and feed that combined text to the existing two-pass planner→synthesizer skill branch unchanged.

**Architecture:** Add one pure, Bedrock-free function family (`SkillBundle`, `resolve_skill_anchor`, `gather_skill_sources`) to `wiki_io.ingest_source` beside `extract`/`guess_source_type`. `run_ingest_source` resolves an anchor first: if found, it gathers the bundle, uses `bundle.combined_text` as `text`, and forces `path_guess = "skill"`; otherwise it falls through to today's single-file path. The bundle is threaded into `_run_skill_branch` so it can render an additive `## Excluded` section and emit warnings. The planner, synthesizer, `guidance-io`, and `_run_common_tail` are untouched — they receive a richer `text`.

**Tech Stack:** Python 3.11, `uv` workspace, pytest (per-package), stdlib `re`/`pathlib` (no new deps in the pure module). Tests are Bedrock-free (pure functions + `make_llm` monkeypatch).

---

## Spec

`docs/superpowers/specs/2026-06-09-directory-aware-skill-ingest-design.md`

## File Structure

| File | Responsibility | Change |
|------|----------------|--------|
| `packages/wiki-io/src/wiki_io/ingest_source.py` | Source-prep pure functions | **Modify** — add `SkillBundle`, `resolve_skill_anchor`, `gather_skill_sources`, and private link/title helpers |
| `packages/wiki-io/tests/test_ingest_source.py` | Pure-function tests | **Modify** — append skill-gathering tests |
| `packages/graph-wiki-core/src/graph_wiki_core/commands/ingest.py` | Ingest orchestration | **Modify** — anchor detection in `run_ingest_source`; `bundle` param + `## Excluded`/warnings in `_run_skill_branch`; `excluded_files` param on `_compose_skill_source_body` |
| `packages/graph-wiki-core/tests/unit/test_commands_ingest.py` | Ingest integration tests | **Modify** — append directory-anchor + `## Excluded` tests |

## Conventions for this repo (read before starting)

- **Run tests scoped per-package**, never from the workspace root:
  - `uv run --package graph-wiki-core pytest ...`
  - `uv run --package wiki-io pytest ...`
- `wiki_io.ingest_source` is **stdlib-only** (see its module docstring). Do **not** add `import yaml` there — parse the SKILL.md `name:` line by hand.
- Match the existing style in each file (the module already uses `from __future__ import annotations`, `re`-module-level compiled patterns, POSIX rel-paths via `.as_posix()`, and `Path.is_relative_to` for boundary checks — mirror all of these).
- `Path.is_relative_to` is available (Python 3.11 floor); the codebase already uses it in `ingest.py:_route_target_path`.
- Commit after every task.

---

### Task 1: `SkillBundle` dataclass + `resolve_skill_anchor`

**Files:**
- Modify: `packages/wiki-io/src/wiki_io/ingest_source.py`
- Test: `packages/wiki-io/tests/test_ingest_source.py`

- [ ] **Step 1: Write the failing tests**

Append to `packages/wiki-io/tests/test_ingest_source.py`:

```python
# ---------------------------------------------------------------------------
# resolve_skill_anchor (directory-aware skill ingest)
# ---------------------------------------------------------------------------


def test_resolve_skill_anchor_directory_with_skill_md(tmp_path: Path) -> None:
    from wiki_io.ingest_source import resolve_skill_anchor

    skill_dir = tmp_path / "my-skill"
    skill_dir.mkdir()
    (skill_dir / "SKILL.md").write_text("# My Skill\n", encoding="utf-8")
    assert resolve_skill_anchor(skill_dir) == skill_dir / "SKILL.md"


def test_resolve_skill_anchor_skill_md_file(tmp_path: Path) -> None:
    from wiki_io.ingest_source import resolve_skill_anchor

    skill_md = tmp_path / "SKILL.md"
    skill_md.write_text("# My Skill\n", encoding="utf-8")
    assert resolve_skill_anchor(skill_md) == skill_md


def test_resolve_skill_anchor_unrelated_file_returns_none(tmp_path: Path) -> None:
    from wiki_io.ingest_source import resolve_skill_anchor

    other = tmp_path / "notes.md"
    other.write_text("# Notes\n", encoding="utf-8")
    assert resolve_skill_anchor(other) is None


def test_resolve_skill_anchor_directory_without_skill_md_returns_none(tmp_path: Path) -> None:
    from wiki_io.ingest_source import resolve_skill_anchor

    plain_dir = tmp_path / "plain"
    plain_dir.mkdir()
    (plain_dir / "README.md").write_text("# Readme\n", encoding="utf-8")
    assert resolve_skill_anchor(plain_dir) is None


def test_skill_bundle_fields() -> None:
    import dataclasses

    from wiki_io.ingest_source import SkillBundle

    field_names = {f.name for f in dataclasses.fields(SkillBundle)}
    assert field_names == {
        "combined_text",
        "skill_dir",
        "anchor",
        "title",
        "included_files",
        "excluded_files",
        "scripts_dominant",
    }
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `uv run --package wiki-io pytest tests/test_ingest_source.py -k "skill_anchor or skill_bundle_fields" -v`
Expected: FAIL — `ImportError: cannot import name 'resolve_skill_anchor'` / `'SkillBundle'`.

- [ ] **Step 3: Add the dataclass and function**

In `packages/wiki-io/src/wiki_io/ingest_source.py`, add `from dataclasses import dataclass` to the imports near the top (after `import re`, before `from pathlib import Path`):

```python
from dataclasses import dataclass
```

Then append at the end of the file:

```python
# ---------------------------------------------------------------------------
# Directory-aware skill ingest (2026-06-09 design).
#
# A skill is frequently a directory: a SKILL.md that links out to companion
# reference markdown. These pure, Bedrock-free helpers gather SKILL.md plus all
# transitively-linked companion .md into one combined text and report the
# non-markdown files that were excluded. The combined text is fed unchanged to
# the existing two-pass skill branch in graph-wiki-core.
# ---------------------------------------------------------------------------


@dataclass
class SkillBundle:
    """Result of gathering a skill directory into one combined markdown blob.

    Fields:
        combined_text:   SKILL.md, then linked companion files in DFS link order,
                         each prefixed with an `<!-- skill-file: <rel> -->` marker.
        skill_dir:       the resolved directory containing the anchor SKILL.md.
        anchor:          the resolved SKILL.md the bundle is anchored on.
        title:           SKILL.md frontmatter `name:` → first `# ` heading → None.
        included_files:  skill_dir-relative POSIX paths, SKILL.md first, DFS order.
        excluded_files:  every non-.md file under skill_dir (POSIX rel, sorted).
        scripts_dominant: True when a top-level `scripts/` dir exists OR there are
                         more excluded files than included.
    """

    combined_text: str
    skill_dir: Path
    anchor: Path
    title: str | None
    included_files: list[str]
    excluded_files: list[str]
    scripts_dominant: bool


def resolve_skill_anchor(source_path: Path) -> Path | None:
    """Return the SKILL.md to anchor a skill ingest on, or None.

    - a directory containing `SKILL.md` -> `<dir>/SKILL.md`
    - a file named `SKILL.md`           -> the file itself
    - anything else                     -> None (caller falls back to today's path)
    """
    if source_path.is_dir():
        candidate = source_path / "SKILL.md"
        return candidate if candidate.is_file() else None
    if source_path.is_file() and source_path.name == "SKILL.md":
        return source_path
    return None
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `uv run --package wiki-io pytest tests/test_ingest_source.py -k "skill_anchor or skill_bundle_fields" -v`
Expected: PASS (5 tests).

- [ ] **Step 5: Commit**

```bash
git add packages/wiki-io/src/wiki_io/ingest_source.py packages/wiki-io/tests/test_ingest_source.py
git commit -m "feat(wiki-io): add SkillBundle + resolve_skill_anchor for directory-aware ingest"
```

---

### Task 2: `gather_skill_sources` — anchor-only (title, markers, excluded, scripts_dominant)

This task builds `gather_skill_sources` for a skill with no companion links: a single `SKILL.md`. Title resolution, the combined-text marker format, the non-markdown `excluded_files` walk, and `scripts_dominant` all land here. Transitive link-following is added in Task 3.

**Files:**
- Modify: `packages/wiki-io/src/wiki_io/ingest_source.py`
- Test: `packages/wiki-io/tests/test_ingest_source.py`

- [ ] **Step 1: Write the failing tests**

Append to `packages/wiki-io/tests/test_ingest_source.py`:

```python
# ---------------------------------------------------------------------------
# gather_skill_sources — single-file (no companion links)
# ---------------------------------------------------------------------------


def test_gather_single_file_combined_text_and_marker(tmp_path: Path) -> None:
    from wiki_io.ingest_source import gather_skill_sources

    skill_dir = tmp_path / "skill"
    skill_dir.mkdir()
    anchor = skill_dir / "SKILL.md"
    anchor.write_text("# Skill\n\nBody line.\n", encoding="utf-8")

    bundle = gather_skill_sources(anchor)

    assert bundle.included_files == ["SKILL.md"]
    assert bundle.combined_text.startswith("<!-- skill-file: SKILL.md -->\n")
    assert "Body line." in bundle.combined_text
    # The marker appears exactly once for the single included file.
    assert bundle.combined_text.count("<!-- skill-file:") == 1
    assert bundle.skill_dir == skill_dir.resolve()
    assert bundle.anchor == anchor.resolve()


def test_gather_title_frontmatter_name_wins(tmp_path: Path) -> None:
    from wiki_io.ingest_source import gather_skill_sources

    skill_dir = tmp_path / "skill"
    skill_dir.mkdir()
    anchor = skill_dir / "SKILL.md"
    anchor.write_text(
        "---\nname: Frontmatter Name\n---\n\n# Heading Title\n\nBody.\n",
        encoding="utf-8",
    )
    assert gather_skill_sources(anchor).title == "Frontmatter Name"


def test_gather_title_falls_back_to_heading(tmp_path: Path) -> None:
    from wiki_io.ingest_source import gather_skill_sources

    skill_dir = tmp_path / "skill"
    skill_dir.mkdir()
    anchor = skill_dir / "SKILL.md"
    anchor.write_text("# Heading Title\n\nBody.\n", encoding="utf-8")
    assert gather_skill_sources(anchor).title == "Heading Title"


def test_gather_title_none_when_absent(tmp_path: Path) -> None:
    from wiki_io.ingest_source import gather_skill_sources

    skill_dir = tmp_path / "skill"
    skill_dir.mkdir()
    anchor = skill_dir / "SKILL.md"
    anchor.write_text("Just body text, no heading and no frontmatter.\n", encoding="utf-8")
    assert gather_skill_sources(anchor).title is None


def test_gather_excluded_files_captures_non_markdown(tmp_path: Path) -> None:
    from wiki_io.ingest_source import gather_skill_sources

    skill_dir = tmp_path / "skill"
    skill_dir.mkdir()
    (skill_dir / "SKILL.md").write_text("# S\n", encoding="utf-8")
    (skill_dir / "helper.py").write_text("print('hi')\n", encoding="utf-8")
    (skill_dir / "logo.png").write_bytes(b"\x89PNG\r\n")

    bundle = gather_skill_sources(skill_dir / "SKILL.md")

    assert bundle.excluded_files == ["helper.py", "logo.png"]  # sorted POSIX rel paths
    assert "helper.py" not in bundle.combined_text  # not read into combined text


def test_gather_scripts_dominant_on_top_level_scripts_dir(tmp_path: Path) -> None:
    from wiki_io.ingest_source import gather_skill_sources

    skill_dir = tmp_path / "skill"
    (skill_dir / "scripts").mkdir(parents=True)
    (skill_dir / "SKILL.md").write_text("# S\n", encoding="utf-8")
    (skill_dir / "scripts" / "run.sh").write_text("echo hi\n", encoding="utf-8")

    bundle = gather_skill_sources(skill_dir / "SKILL.md")

    assert bundle.scripts_dominant is True
    assert bundle.excluded_files == ["scripts/run.sh"]


def test_gather_scripts_dominant_on_excluded_majority(tmp_path: Path) -> None:
    from wiki_io.ingest_source import gather_skill_sources

    skill_dir = tmp_path / "skill"
    skill_dir.mkdir()
    (skill_dir / "SKILL.md").write_text("# S\n", encoding="utf-8")  # 1 included
    (skill_dir / "a.py").write_text("a\n", encoding="utf-8")  # 2 excluded > 1 included
    (skill_dir / "b.py").write_text("b\n", encoding="utf-8")

    assert gather_skill_sources(skill_dir / "SKILL.md").scripts_dominant is True


def test_gather_not_scripts_dominant_when_markdown_majority(tmp_path: Path) -> None:
    from wiki_io.ingest_source import gather_skill_sources

    skill_dir = tmp_path / "skill"
    skill_dir.mkdir()
    (skill_dir / "SKILL.md").write_text("# S\n", encoding="utf-8")
    (skill_dir / "data.json").write_text("{}\n", encoding="utf-8")  # 1 excluded, 1 included

    assert gather_skill_sources(skill_dir / "SKILL.md").scripts_dominant is False
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `uv run --package wiki-io pytest tests/test_ingest_source.py -k "gather_single or gather_title or gather_excluded or gather_scripts or gather_not_scripts" -v`
Expected: FAIL — `ImportError: cannot import name 'gather_skill_sources'`.

- [ ] **Step 3: Add the title helper and `gather_skill_sources` (anchor-only)**

In `packages/wiki-io/src/wiki_io/ingest_source.py`, append after the `resolve_skill_anchor` function from Task 1:

```python
def _skill_title(anchor_text: str) -> str | None:
    """Title from a SKILL.md: frontmatter `name:` → first `# ` heading → None.

    Stdlib-only (this module avoids a yaml dependency): the frontmatter `name:`
    is read line-by-line from the leading `---`-fenced block.
    """
    stripped = anchor_text.lstrip()
    if stripped.startswith("---"):
        after = stripped[3:].lstrip("\n")
        end = after.find("\n---")
        if end != -1:
            for line in after[:end].splitlines():
                if line.strip().startswith("name:"):
                    value = line.split(":", 1)[1].strip().strip("\"'")
                    if value:
                        return value
    for line in anchor_text.splitlines():
        if line.startswith("# "):
            return line[2:].strip()
    return None


def gather_skill_sources(anchor: Path) -> SkillBundle:
    """Gather a skill directory into one combined markdown blob.

    Reads `anchor` (a SKILL.md) plus every companion `.md` it links to,
    transitively, and concatenates them with `<!-- skill-file: <rel> -->`
    markers. Non-markdown files under the skill directory are recorded in
    `excluded_files` (not read). Pure / Bedrock-free.
    """
    skill_dir = anchor.parent.resolve()

    # DFS preorder from the anchor, visited-set keyed by resolved abs path so
    # cycles terminate and each file is included at most once. (Link-following
    # recursion is wired in a later step; here we visit the anchor only.)
    visited: set[Path] = set()
    included: list[tuple[Path, str]] = []  # (resolved_abs_path, content), DFS order

    def visit(md_file: Path) -> None:
        resolved = md_file.resolve()
        if resolved in visited:
            return
        visited.add(resolved)
        content = resolved.read_text(encoding="utf-8", errors="replace")
        included.append((resolved, content))

    visit(anchor)

    parts = []
    for abs_path, content in included:
        rel = abs_path.relative_to(skill_dir).as_posix()
        parts.append(f"<!-- skill-file: {rel} -->\n{content}")
    combined_text = "\n\n".join(parts)

    included_files = [abs_path.relative_to(skill_dir).as_posix() for abs_path, _ in included]
    excluded_files = sorted(
        p.relative_to(skill_dir).as_posix()
        for p in skill_dir.rglob("*")
        if p.is_file() and p.suffix.lower() != ".md"
    )
    scripts_dominant = (skill_dir / "scripts").is_dir() or len(excluded_files) > len(included_files)

    return SkillBundle(
        combined_text=combined_text,
        skill_dir=skill_dir,
        anchor=anchor.resolve(),
        title=_skill_title(included[0][1]),
        included_files=included_files,
        excluded_files=excluded_files,
        scripts_dominant=scripts_dominant,
    )
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `uv run --package wiki-io pytest tests/test_ingest_source.py -k "gather_single or gather_title or gather_excluded or gather_scripts or gather_not_scripts" -v`
Expected: PASS (8 tests).

- [ ] **Step 5: Commit**

```bash
git add packages/wiki-io/src/wiki_io/ingest_source.py packages/wiki-io/tests/test_ingest_source.py
git commit -m "feat(wiki-io): gather_skill_sources anchor-only (title, markers, excluded, scripts_dominant)"
```

---

### Task 3: `gather_skill_sources` — transitive link-following

Add the companion-markdown link parsing and recursion: inline `[text](target)` and reference-definition `[id]: target` links, kept only when the target ends in `.md`, is not an `http(s)`/`mailto:` URL or pure `#anchor`, resolves to an existing file relative to the *linking* file, and stays inside `skill_dir`. Recursion is transitive with the visited-set from Task 2; DFS in link-appearance order.

**Files:**
- Modify: `packages/wiki-io/src/wiki_io/ingest_source.py`
- Test: `packages/wiki-io/tests/test_ingest_source.py`

- [ ] **Step 1: Write the failing tests**

Append to `packages/wiki-io/tests/test_ingest_source.py`:

```python
# ---------------------------------------------------------------------------
# gather_skill_sources — transitive link following
# ---------------------------------------------------------------------------


def test_gather_transitive_dfs_order(tmp_path: Path) -> None:
    from wiki_io.ingest_source import gather_skill_sources

    skill_dir = tmp_path / "skill"
    (skill_dir / "references").mkdir(parents=True)
    (skill_dir / "SKILL.md").write_text("# S\n\nSee [a](references/a.md).\n", encoding="utf-8")
    (skill_dir / "references" / "a.md").write_text("# A\n\nSee [b](b.md).\n", encoding="utf-8")
    (skill_dir / "references" / "b.md").write_text("# B\n\nLeaf.\n", encoding="utf-8")

    bundle = gather_skill_sources(skill_dir / "SKILL.md")

    assert bundle.included_files == ["SKILL.md", "references/a.md", "references/b.md"]
    # Each file gets exactly one marker, in DFS order.
    assert bundle.combined_text.count("<!-- skill-file:") == 3
    assert bundle.combined_text.index("SKILL.md -->") < bundle.combined_text.index("references/a.md -->")
    assert bundle.combined_text.index("references/a.md -->") < bundle.combined_text.index("references/b.md -->")


def test_gather_reference_style_links_followed(tmp_path: Path) -> None:
    from wiki_io.ingest_source import gather_skill_sources

    skill_dir = tmp_path / "skill"
    skill_dir.mkdir()
    (skill_dir / "SKILL.md").write_text("# S\n\nSee [the guide][g].\n\n[g]: guide.md\n", encoding="utf-8")
    (skill_dir / "guide.md").write_text("# Guide\n", encoding="utf-8")

    bundle = gather_skill_sources(skill_dir / "SKILL.md")
    assert bundle.included_files == ["SKILL.md", "guide.md"]


def test_gather_cycle_terminates_each_once(tmp_path: Path) -> None:
    from wiki_io.ingest_source import gather_skill_sources

    skill_dir = tmp_path / "skill"
    skill_dir.mkdir()
    (skill_dir / "SKILL.md").write_text("# S\n\nSee [a](a.md).\n", encoding="utf-8")
    (skill_dir / "a.md").write_text("# A\n\nBack to [b](b.md).\n", encoding="utf-8")
    (skill_dir / "b.md").write_text("# B\n\nBack to [a](a.md).\n", encoding="utf-8")

    bundle = gather_skill_sources(skill_dir / "SKILL.md")
    assert bundle.included_files == ["SKILL.md", "a.md", "b.md"]
    assert bundle.combined_text.count("<!-- skill-file: a.md -->") == 1
    assert bundle.combined_text.count("<!-- skill-file: b.md -->") == 1


def test_gather_directory_boundary_guard(tmp_path: Path) -> None:
    from wiki_io.ingest_source import gather_skill_sources

    outside = tmp_path / "outside.md"
    outside.write_text("# Outside\n", encoding="utf-8")
    skill_dir = tmp_path / "skill"
    skill_dir.mkdir()
    (skill_dir / "SKILL.md").write_text("# S\n\nEscape [o](../outside.md).\n", encoding="utf-8")

    bundle = gather_skill_sources(skill_dir / "SKILL.md")
    assert bundle.included_files == ["SKILL.md"]
    assert "Outside" not in bundle.combined_text


def test_gather_skips_non_md_http_and_anchor_targets(tmp_path: Path) -> None:
    from wiki_io.ingest_source import gather_skill_sources

    skill_dir = tmp_path / "skill"
    skill_dir.mkdir()
    (skill_dir / "SKILL.md").write_text(
        "# S\n\n"
        "Script [s](helper.py).\n"
        "Web [w](https://example.com/page.md).\n"
        "Anchor [a](#section).\n"
        "Mail [m](mailto:x@y.md).\n"
        "Real [r](real.md).\n",
        encoding="utf-8",
    )
    (skill_dir / "helper.py").write_text("x\n", encoding="utf-8")
    (skill_dir / "real.md").write_text("# Real\n", encoding="utf-8")

    bundle = gather_skill_sources(skill_dir / "SKILL.md")
    assert bundle.included_files == ["SKILL.md", "real.md"]


def test_gather_strips_fragment_before_resolving(tmp_path: Path) -> None:
    from wiki_io.ingest_source import gather_skill_sources

    skill_dir = tmp_path / "skill"
    skill_dir.mkdir()
    (skill_dir / "SKILL.md").write_text("# S\n\nSee [a](a.md#heading).\n", encoding="utf-8")
    (skill_dir / "a.md").write_text("# A\n", encoding="utf-8")

    bundle = gather_skill_sources(skill_dir / "SKILL.md")
    assert bundle.included_files == ["SKILL.md", "a.md"]
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `uv run --package wiki-io pytest tests/test_ingest_source.py -k "gather_transitive or gather_reference or gather_cycle or gather_directory_boundary or gather_skips_non or gather_strips_fragment" -v`
Expected: FAIL — links are not followed yet, so `included_files` is `["SKILL.md"]` (assertion failures, not import errors).

- [ ] **Step 3: Add link helpers and wire recursion into `gather_skill_sources`**

In `packages/wiki-io/src/wiki_io/ingest_source.py`, add these compiled patterns immediately above the `SkillBundle` dataclass (beside the other module-level `re.compile` constants):

```python
# Inline markdown link target: captures the URL token after `](` up to the
# first whitespace or `)`. Optional `<...>` angle-bracket form is captured too.
_MD_INLINE_LINK_RE = re.compile(r"\]\(\s*(<[^>]+>|[^)\s]+)")
# Reference-style definition `[id]: target` at line start (≤3 leading spaces).
_MD_REF_DEF_RE = re.compile(r"^[ ]{0,3}\[[^\]]+\]:\s*(\S+)", re.MULTILINE)
```

Then add these two helpers immediately above `gather_skill_sources` (after `_skill_title`):

```python
def _iter_link_targets(content: str) -> list[str]:
    """Return markdown link targets in appearance order (inline + reference defs)."""
    matches: list[tuple[int, str]] = []
    for m in _MD_INLINE_LINK_RE.finditer(content):
        matches.append((m.start(), m.group(1)))
    for m in _MD_REF_DEF_RE.finditer(content):
        matches.append((m.start(), m.group(1)))
    matches.sort(key=lambda pair: pair[0])
    return [raw.strip().strip("<>") for _, raw in matches]


def _resolve_companion(target: str, linking_dir: Path, skill_dir: Path) -> Path | None:
    """Resolve a link target to a companion .md inside skill_dir, or None.

    Keeps only targets that: end in `.md`; are not http(s)/mailto URLs or pure
    `#anchor`; resolve (relative to the linking file's dir) to an existing file;
    and stay inside `skill_dir` (no `../` escape). `skill_dir` must be resolved.
    """
    cleaned = target.split("#", 1)[0].strip()  # strip any #fragment
    if not cleaned:
        return None
    lowered = cleaned.lower()
    if lowered.startswith(("http://", "https://", "mailto:")):
        return None
    if not cleaned.endswith(".md"):
        return None
    candidate = (linking_dir / cleaned).resolve()
    if not candidate.is_file():
        return None
    if not candidate.is_relative_to(skill_dir):
        return None
    return candidate
```

Finally, replace the `visit` function body inside `gather_skill_sources` (the anchor-only version from Task 2) so it recurses over resolved companion links:

```python
    def visit(md_file: Path) -> None:
        resolved = md_file.resolve()
        if resolved in visited:
            return
        visited.add(resolved)
        content = resolved.read_text(encoding="utf-8", errors="replace")
        included.append((resolved, content))
        for target in _iter_link_targets(content):
            child = _resolve_companion(target, resolved.parent, skill_dir)
            if child is not None:
                visit(child)
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `uv run --package wiki-io pytest tests/test_ingest_source.py -k "gather_transitive or gather_reference or gather_cycle or gather_directory_boundary or gather_skips_non or gather_strips_fragment" -v`
Expected: PASS (6 tests).

Then run the whole pure suite to confirm nothing regressed:

Run: `uv run --package wiki-io pytest tests/test_ingest_source.py -v`
Expected: PASS (all, including the original slugify/extract/guess tests).

- [ ] **Step 5: Commit**

```bash
git add packages/wiki-io/src/wiki_io/ingest_source.py packages/wiki-io/tests/test_ingest_source.py
git commit -m "feat(wiki-io): transitive companion-markdown link following in gather_skill_sources"
```

---

### Task 4: `## Excluded` rendering + warnings in the skill branch

Add the additive `## Excluded` section to the skill Source-page body and the warnings, threading the bundle's excluded-files data into `_run_skill_branch`. The planner/synthesizer logic is unchanged. This task is unit-testable on the body composer; the end-to-end wiring is verified in Task 5.

**Files:**
- Modify: `packages/graph-wiki-core/src/graph_wiki_core/commands/ingest.py`
- Test: `packages/graph-wiki-core/tests/unit/test_commands_ingest.py`

- [ ] **Step 1: Write the failing tests**

Append to `packages/graph-wiki-core/tests/unit/test_commands_ingest.py`:

```python
# ---------------------------------------------------------------------------
# Skill-branch ## Excluded section (directory-aware skill ingest)
# ---------------------------------------------------------------------------


def test_compose_skill_source_body_renders_excluded_section() -> None:
    from graph_wiki_core.commands.ingest import _compose_skill_source_body

    body = _compose_skill_source_body(
        "My Skill",
        ["wiki/guidance/topic/a.md"],
        excluded_files=["scripts/run.sh", "logo.png"],
    )
    assert "## Excluded" in body
    assert "2 non-markdown file(s)" in body
    assert "`scripts/run.sh`" in body
    assert "`logo.png`" in body
    # The ## Generates section is still present (additive, not a replacement).
    assert "## Generates" in body


def test_compose_skill_source_body_omits_excluded_when_empty() -> None:
    from graph_wiki_core.commands.ingest import _compose_skill_source_body

    assert "## Excluded" not in _compose_skill_source_body("My Skill", [], excluded_files=[])
    assert "## Excluded" not in _compose_skill_source_body("My Skill", [])  # default None
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `uv run --package graph-wiki-core pytest tests/unit/test_commands_ingest.py -k "compose_skill_source_body" -v`
Expected: FAIL — `_compose_skill_source_body()` got an unexpected keyword argument `excluded_files`.

- [ ] **Step 3: Add the `excluded_files` parameter and section**

In `packages/graph-wiki-core/src/graph_wiki_core/commands/ingest.py`, replace the existing `_compose_skill_source_body` function (currently around line 726) with:

```python
def _compose_skill_source_body(
    title: str, written_rel_paths: list[str], excluded_files: list[str] | None = None
) -> str:
    """Build the Source page body for a skill ingest.

    Minimal frontmatter (title only — source_type/target_slug/entity_uri are
    stamped by the common tail) plus a `## Generates` section linking every
    guidance page the skill produced. Provenance: skill → guidance. When the
    skill directory had non-markdown files, an additive `## Excluded` section
    records them (directory-aware skill ingest, 2026-06-09).
    """
    lines = [f"- [[{_guidance_wikilink_target(p)}]]" for p in written_rel_paths]
    generates = "\n".join(lines) if lines else "_No guidance pages were generated._"
    body = (
        f"---\ntitle: {title}\n---\n\n"
        f"# {title}\n\n"
        f"## Summary\n"
        f"Agent skill ingested. Reusable guidance was synthesized into "
        f"{len(written_rel_paths)} guidance page(s) under `wiki/guidance/`.\n\n"
        f"## Generates\n{generates}\n"
    )
    if excluded_files:
        excl_lines = "\n".join(f"- `{p}`" for p in excluded_files)
        body += (
            f"\n## Excluded\n"
            f"{len(excluded_files)} non-markdown file(s) were not ingested:\n"
            f"{excl_lines}\n"
        )
    return body
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `uv run --package graph-wiki-core pytest tests/unit/test_commands_ingest.py -k "compose_skill_source_body" -v`
Expected: PASS (2 tests).

- [ ] **Step 5: Thread `bundle` into `_run_skill_branch` and emit warnings**

Still in `packages/graph-wiki-core/src/graph_wiki_core/commands/ingest.py`:

First, extend the existing `wiki_io.ingest_source` import block (currently around line 49) to add **only** `SkillBundle` (it is the only new name used in this task — the other two are added in Task 5, where they are first used, to keep each commit's imports lint-clean for the pre-commit ruff hook):

```python
from wiki_io.ingest_source import (
    PREVIEW_CHARS,
    RAW_FOLDER_TYPES,
    SOURCE_TYPE_ENUM,
    SkillBundle,
    extract,
    guess_source_type,
    slugify,
)
```

Then add a `bundle` parameter to `_run_skill_branch`. Change its signature (currently around line 819) by adding the parameter after `model_override`:

```python
async def _run_skill_branch(
    *,
    text: str,
    title_guess: str,
    slug: str,
    source_path: Path,
    workspace_root: Path,
    wiki: Path,
    project_ctx: str,
    canonical_uri: str | None,
    entity_stem: str | None,
    model_override: str | None,
    bundle: SkillBundle | None = None,
) -> _IngestBranchResult | None:
```

Inside `_run_skill_branch`, replace the block that builds `page_body` (currently `page_body = _compose_skill_source_body(title_guess, written)` near line 888) with:

```python
    excluded_files = bundle.excluded_files if bundle is not None else []
    if excluded_files:
        logger.warning(
            "skill ingest excluded %d non-markdown file(s): %s",
            len(excluded_files),
            excluded_files,
        )
    if bundle is not None and bundle.scripts_dominant:
        logger.warning(
            "skill directory %s looks like a workflow skill (scripts/non-markdown dominant); "
            "guidance ingestion may be a poor fit — proceeding anyway",
            bundle.skill_dir,
        )

    page_body = _compose_skill_source_body(title_guess, written, excluded_files=excluded_files)
```

- [ ] **Step 6: Run the existing skill-branch tests to confirm no regression**

Run: `uv run --package graph-wiki-core pytest tests/unit/test_commands_ingest.py -k "skill" -v`
Expected: PASS (existing `test_run_ingest_source_skill_writes_guidance_and_skips_suggest`, `test_run_ingest_source_skill_falls_back_when_plan_unparseable`, and the two new `compose_skill_source_body` tests). The bundle param defaults to `None`, so the existing `run_ingest_source` call sites still compile and pass.

- [ ] **Step 7: Commit**

```bash
git add packages/graph-wiki-core/src/graph_wiki_core/commands/ingest.py packages/graph-wiki-core/tests/unit/test_commands_ingest.py
git commit -m "feat(ingest): render ## Excluded section + warnings in skill branch"
```

---

### Task 5: Wire anchor detection into `run_ingest_source`

Resolve a skill anchor at the top of `run_ingest_source`: when found, use `bundle.combined_text` / `bundle.title`, force `path_guess = "skill"`, and pass the bundle to `_run_skill_branch`. When no anchor is found, behavior is exactly today's (including a `raw/skill/foo.md` single file, which still ingests as `skill` via the path-guess with `bundle=None`).

**Files:**
- Modify: `packages/graph-wiki-core/src/graph_wiki_core/commands/ingest.py`
- Test: `packages/graph-wiki-core/tests/unit/test_commands_ingest.py`

- [ ] **Step 1: Write the failing test**

Append to `packages/graph-wiki-core/tests/unit/test_commands_ingest.py`:

```python
# ---------------------------------------------------------------------------
# Directory anchor forces the skill branch + renders ## Excluded end-to-end
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_run_ingest_source_skill_directory_forces_skill_and_excludes(tmp_path, monkeypatch):
    """A skill DIRECTORY (outside raw/skill/) is anchored on SKILL.md, gathers a
    linked companion .md, excludes a script, and renders ## Excluded."""
    from graph_wiki_core.commands import ingest as ingest_mod

    ws = tmp_path
    (ws / "wiki").mkdir()
    (ws / "wiki" / "log.md").write_text("", encoding="utf-8")

    # Skill directory lives OUTSIDE raw/ — only the anchor (not the path-guess)
    # can route this to the skill branch.
    skill_dir = ws / "skills" / "my-skill"
    (skill_dir / "references").mkdir(parents=True)
    (skill_dir / "SKILL.md").write_text(
        "---\nname: My Skill\n---\n\n# My Skill\n\nSee [adv](references/advanced.md).\n",
        encoding="utf-8",
    )
    (skill_dir / "references" / "advanced.md").write_text("# Advanced\n\nDeep guidance.\n", encoding="utf-8")
    (skill_dir / "run.py").write_text("print('workflow')\n", encoding="utf-8")  # excluded

    monkeypatch.setattr(ingest_mod, "resolve_wiki_and_repo", lambda wp: (ws / "wiki", ws))
    monkeypatch.setattr(ingest_mod, "render_project_context", lambda wiki: "")

    class _Conn:
        def close(self):
            pass

    monkeypatch.setattr(ingest_mod, "read_only_connect", lambda db: _Conn())
    monkeypatch.setattr(ingest_mod, "lookup_entity_by_path", lambda conn, repo, sp: None)
    monkeypatch.setattr(ingest_mod, "lookup_entity_by_name", lambda conn, name: None)

    captured: dict = {}

    planner_yaml = (
        "- title: Deep Guidance\n"
        "  slug: deep-guidance\n"
        "  topic: my-skill\n"
        "  summary: Deep guidance.\n"
        "  applies_when: Working on the skill.\n"
        "  impact: high\n"
        "  content: Deep guidance from the companion file.\n"
    )
    guidance_page = (
        "---\ntitle: Deep Guidance\ncategory: guidance\ntopic: my-skill\n"
        "summary: Deep guidance.\napplies_when: Working on the skill.\nimpact: high\n"
        "updated: 2026-06-09\ntokens: 0\n---\n\n## Guidance\nDeep guidance.\n"
    )

    def _fake_make_llm(role, model_override=None):
        out = planner_yaml if role == "skill_planner" else guidance_page

        class _LLM:
            async def ainvoke(self, messages):
                # Capture the planner human message to assert the companion text
                # made it into the combined blob the planner sees.
                if role == "skill_planner":
                    captured["planner_human"] = messages[-1].content

                class _R:
                    content = out
                    usage_metadata = None

                return _R()

        return _LLM()

    monkeypatch.setattr(ingest_mod, "make_llm", _fake_make_llm)

    # Pass the DIRECTORY, not a file.
    result = await ingest_mod.run_ingest_source(skill_dir, workspace_path=ws)

    # Directory anchor forced the skill branch despite living outside raw/skill/.
    assert result.source_type == "skill"
    assert result.page_type == "source"
    # Title came from SKILL.md frontmatter `name:`.
    assert result.title == "My Skill"
    # Companion markdown was gathered into the combined text the planner saw.
    assert "Deep guidance" in captured["planner_human"]
    assert "<!-- skill-file: references/advanced.md -->" in captured["planner_human"]
    # Guidance page written from the plan.
    assert result.guidance_pages_written == ["wiki/guidance/my-skill/deep-guidance.md"]
    # ## Excluded section recorded the non-markdown file.
    src = (ws / "wiki" / result.page_path).read_text(encoding="utf-8")
    assert "## Excluded" in src
    assert "`run.py`" in src


@pytest.mark.asyncio
async def test_run_ingest_source_raw_skill_single_file_still_works(tmp_path, monkeypatch):
    """Regression: a raw/skill/<file>.md single file (NOT named SKILL.md) has no
    anchor, so bundle is None — it still routes to the skill branch via the
    path-guess and renders no ## Excluded section."""
    from graph_wiki_core.commands import ingest as ingest_mod

    ws = tmp_path
    (ws / "wiki").mkdir()
    (ws / "wiki" / "log.md").write_text("", encoding="utf-8")
    skill_dir = ws / "raw" / "skill"
    skill_dir.mkdir(parents=True)
    skill_file = skill_dir / "react-native.md"
    skill_file.write_text("# RN Skill\nAlways use a virtualizer.\n", encoding="utf-8")

    monkeypatch.setattr(ingest_mod, "resolve_wiki_and_repo", lambda wp: (ws / "wiki", ws))
    monkeypatch.setattr(ingest_mod, "render_project_context", lambda wiki: "")

    class _Conn:
        def close(self):
            pass

    monkeypatch.setattr(ingest_mod, "read_only_connect", lambda db: _Conn())
    monkeypatch.setattr(ingest_mod, "lookup_entity_by_path", lambda conn, repo, sp: None)
    monkeypatch.setattr(ingest_mod, "lookup_entity_by_name", lambda conn, name: None)

    planner_yaml = (
        "- title: Use a Virtualizer\n"
        "  slug: use-virtualizer\n"
        "  topic: react-native\n"
        "  summary: Use a virtualizer.\n"
        "  applies_when: Rendering a list.\n"
        "  impact: high\n"
        "  content: Use a virtualizer instead of ScrollView.\n"
    )
    guidance_page = (
        "---\ntitle: Use a Virtualizer\ncategory: guidance\ntopic: react-native\n"
        "summary: Use a virtualizer.\napplies_when: Rendering a list.\nimpact: high\n"
        "updated: 2026-06-09\ntokens: 0\n---\n\n## Guidance\nUse a virtualizer.\n"
    )

    def _fake_make_llm(role, model_override=None):
        out = planner_yaml if role == "skill_planner" else guidance_page

        class _LLM:
            async def ainvoke(self, messages):
                class _R:
                    content = out
                    usage_metadata = None

                return _R()

        return _LLM()

    monkeypatch.setattr(ingest_mod, "make_llm", _fake_make_llm)

    result = await ingest_mod.run_ingest_source(skill_file, workspace_path=ws)

    assert result.source_type == "skill"
    assert result.guidance_pages_written == ["wiki/guidance/react-native/use-virtualizer.md"]
    src = (ws / "wiki" / result.page_path).read_text(encoding="utf-8")
    assert "## Excluded" not in src  # no bundle -> no excluded section
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `uv run --package graph-wiki-core pytest tests/unit/test_commands_ingest.py -k "skill_directory_forces or raw_skill_single_file" -v`
Expected: FAIL — `test_run_ingest_source_skill_directory_forces_skill_and_excludes` fails because a directory `source_path` currently routes through `extract()` (not the skill branch) and no `## Excluded` is rendered. (`test_run_ingest_source_raw_skill_single_file_still_works` may already pass — it asserts current behavior plus the no-`## Excluded` invariant.)

- [ ] **Step 3: Add anchor detection to `run_ingest_source`**

In `packages/graph-wiki-core/src/graph_wiki_core/commands/ingest.py`, first add the two remaining names to the `wiki_io.ingest_source` import block (they are used for the first time in this task, so the commit stays lint-clean). The block becomes:

```python
from wiki_io.ingest_source import (
    PREVIEW_CHARS,
    RAW_FOLDER_TYPES,
    SOURCE_TYPE_ENUM,
    SkillBundle,
    extract,
    gather_skill_sources,
    guess_source_type,
    resolve_skill_anchor,
    slugify,
)
```

Then, inside `run_ingest_source` replace the Step 2 + Step 3 block (currently lines ~1146–1165, from `# Step 2: extract text and title` through `path_guess = guess_source_type(rel_to_workspace, rel_to_repo)`) with:

```python
        # Step 2: resolve a skill anchor (a directory containing SKILL.md, or a
        # SKILL.md file). When found, gather SKILL.md + all transitively-linked
        # companion markdown into one combined text and force the skill branch.
        # Otherwise fall through to today's single-file extract.
        anchor = resolve_skill_anchor(source_path)
        bundle: SkillBundle | None = None
        if anchor is not None:
            bundle = gather_skill_sources(anchor)
            text = bundle.combined_text
            title = bundle.title
        else:
            text, title = extract(source_path)
        title_guess = title or source_path.stem.replace("-", " ").title()
        slug = slugify(title_guess)

        # Step 3: path-guess the source_type. A resolved skill anchor forces
        # "skill" regardless of where the directory lives (works for skills
        # outside raw/skill/). Otherwise guess from the path: raw/<type>/
        # folders are authoritative (measured workspace-relative — raw/ is a
        # sibling of wiki/), in-repo docs fall to `doc`, loose files to `note`.
        if anchor is not None:
            path_guess = "skill"
        else:
            rel_to_workspace: Path | None = None
            rel_to_repo: Path | None = None
            try:
                rel_to_workspace = source_path.relative_to(workspace_root)
            except ValueError:
                pass
            try:
                rel_to_repo = source_path.relative_to(repo)
            except ValueError:
                pass
            path_guess = guess_source_type(rel_to_workspace, rel_to_repo)
```

Then, in the dispatch block (currently around line 1189), pass the bundle to `_run_skill_branch` by adding the `bundle=bundle` keyword argument:

```python
        branch: _IngestBranchResult | None = None
        if path_guess == "skill":
            branch = await _run_skill_branch(
                text=text,
                title_guess=title_guess,
                slug=slug,
                source_path=source_path,
                workspace_root=workspace_root,
                wiki=wiki,
                project_ctx=project_ctx,
                canonical_uri=canonical_uri,
                entity_stem=entity_stem,
                model_override=model_override,
                bundle=bundle,
            )
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `uv run --package graph-wiki-core pytest tests/unit/test_commands_ingest.py -k "skill_directory_forces or raw_skill_single_file" -v`
Expected: PASS (2 tests).

- [ ] **Step 5: Run the full ingest suite to confirm no regression**

Run: `uv run --package graph-wiki-core pytest tests/unit/test_commands_ingest.py -v`
Expected: PASS (all, including the pre-existing skill, entity-link, and routing tests).

- [ ] **Step 6: Commit**

```bash
git add packages/graph-wiki-core/src/graph_wiki_core/commands/ingest.py packages/graph-wiki-core/tests/unit/test_commands_ingest.py
git commit -m "feat(ingest): directory/SKILL.md anchor routes ingest to gathered skill branch"
```

---

### Task 6: Final verification

**Files:** none (verification only)

- [ ] **Step 1: Lint the changed files**

Run: `uv run ruff check packages/wiki-io/src/wiki_io/ingest_source.py packages/graph-wiki-core/src/graph_wiki_core/commands/ingest.py packages/wiki-io/tests/test_ingest_source.py packages/graph-wiki-core/tests/unit/test_commands_ingest.py`
Expected: no errors. (Per the repo's known ruff state, do NOT run `ruff format` to "fix" the diff — match surrounding multi-line style by hand.)

- [ ] **Step 2: Run both package suites**

Run: `uv run --package wiki-io pytest tests/test_ingest_source.py -v && uv run --package graph-wiki-core pytest tests/unit/test_commands_ingest.py -v`
Expected: PASS for both.

- [ ] **Step 3: Confirm spec coverage**

Verify against the spec sections:
- §1 Detection/normalization → `resolve_skill_anchor` (Task 1) + forced `path_guess` (Task 5).
- §1 Title → `_skill_title` frontmatter `name:` → heading → None (Task 2).
- §2 Link-following (transitive, cycle, boundary, non-md/http/anchor) → Task 3.
- §3 Concatenation with `<!-- skill-file: -->` markers → Tasks 2–3.
- §4 Scripts/non-markdown: `excluded_files`, `scripts_dominant`, `## Excluded` section, warnings → Tasks 2, 4.
- §5 Fallback (planner failure → default branch, no `## Excluded`) → unchanged `_run_skill_branch` return-None path; covered by the pre-existing `test_run_ingest_source_skill_falls_back_when_plan_unparseable`.

- [ ] **Step 4: No commit needed** (verification only — all work already committed).

---

## Notes for the implementer

- **Don't modify** the planner, synthesizer, `guidance-io`, or `_run_common_tail` — they receive a richer `text` and are out of scope (spec "Out of Scope").
- The combined-text marker is an **HTML comment** (`<!-- skill-file: ... -->`), deliberately not a heading, so it doesn't render as content or perturb the planner's chunking.
- `gather_skill_sources` is recursive; the visited-set keyed by resolved absolute path is what makes cycles terminate — keep it.
- `_resolve_companion` takes an **already-resolved** `skill_dir` (resolved once at the top of `gather_skill_sources`); the `is_relative_to` boundary check depends on that.
- The fallback path (planner fails / unparseable plan) deliberately does **not** emit `## Excluded` or the warnings — those are tied to the skill branch, and on fallback the default branch produces a generic Source page (spec §5). No new code needed for this; it's the existing return-`None` behavior.
```
