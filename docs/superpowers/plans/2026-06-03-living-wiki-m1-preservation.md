# Living Wiki M1 — Entity-Page Preservation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make `write_entities` preserve human/LLM-authored entity-page sections (e.g. `## Purpose`, `## Public API`, any hand-added H2) across re-scan, while still regenerating the three scanner-owned sections — and remove the four duplicative forward-link stub sections from the entity templates.

**Architecture:** Today `write_entities` re-renders each page's body wholesale from the template (`_render_entity_page`), discarding the existing body. We add a **heading-aware merge** (Approach A from the roadmap): on re-scan, every H2 section is preserved from the existing page **except** the scanner-owned set (`## Narrative`, `## File map`, `## Referenced in wiki`), which keep the template placeholder so the downstream scan-pipeline injectors (`inject_narrative`, `inject_file_map`, `regenerate_referenced_in_wiki`) can refill them. The merge is a pure string transform on the page body, wired in via a new optional `existing_body` parameter on `_render_entity_page`. Separately, the four never-populated forward-link stubs (`## Concepts`, `## Dependencies`, `## Decisions`, `## Contrasts / alternatives`) are deleted from the templates — `## Referenced in wiki` (backlinks) already supersedes them.

**Tech Stack:** Python 3.11+, `uv` workspace (`wiki-io` package), `pytest` (sync; `--import-mode=importlib`), `python-frontmatter`, stdlib `re`.

**Source spec:** `docs/superpowers/specs/2026-06-03-living-wiki-roadmap.md` (§3 D2, §4 "M1 — Preservation").

---

## Scope

In scope (M1 only):
- Heading-aware section preservation in `write_entities` / `_render_entity_page`.
- Removal of the four forward-link stub sections from entity templates.
- Backward-compat rule wording update (section-ownership model).

Explicitly **out of scope** (later milestones): commit-gated/diff-driven refresh, template-section reconciliation (add/remove H2s to match an evolved template), narrative regeneration gating changes. M1 keeps the existing `needs_narrative` behavior unchanged.

**Migration note (no code):** existing entity pages rendered from the *old* templates still carry the four stub headings. After this lands they are treated as user-added "custom" sections and **preserved** (not auto-dropped) — acceptable per `.claude/rules/backward-compatibility.md` (entity content is regenerable). Recommend a one-time `entities/` rebuild (delete `wiki/entities/` and re-run scan) so stale stubs disappear. This is an operator action, not part of this plan.

---

## File Structure

| File | Responsibility | Change |
|---|---|---|
| `packages/wiki-io/src/wiki_io/entity_writer.py` | Entity page render + write | **Modify**: add 3 helpers (`_is_scanner_owned_heading`, `_split_h2_sections`, `_merge_preserved_sections`); add `existing_body` param to `_render_entity_page`; pass `post.content` from `write_entities` |
| `packages/wiki-io/tests/test_section_merge.py` | Unit tests for the pure merge helpers | **Create** |
| `packages/wiki-io/tests/test_entity_writer.py` | `write_entities` orchestrator tests | **Modify**: add 2 rescan-preservation tests |
| `packages/wiki-io/src/wiki_io/assets/page-templates/entity-package.md` | Package entity template | **Modify**: delete 4 stub sections |
| `.../page-templates/entity-app.md` | App entity template | **Modify**: delete 4 stub sections |
| `.../page-templates/entity-domain.md` | Domain entity template | **Modify**: delete 4 stub sections |
| `.../page-templates/entity-dependency.md` | Dependency entity template | **Modify**: delete 4 stub sections |
| `.../page-templates/entity-agent-plugin.md` | Agent-plugin entity template | **Modify**: delete 3 stub sections (no `## Dependencies`) |
| `packages/wiki-io/tests/test_entity_templates.py` | Template/ADMITTED_KINDS invariants | **Modify**: add stub-absence regression test |
| `.claude/rules/backward-compatibility.md` | Project rule | **Modify**: refine entity-content bullet to section-ownership model |

**Run tests with** (from repo root): `uv run --package wiki-io pytest <path> -v`

---

## Task 1: Scanner-owned predicate + H2 section splitter

Two pure helpers. `_is_scanner_owned_heading` classifies a heading; `_split_h2_sections` losslessly splits a page body into a preamble + ordered `(heading, chunk)` sections. Reuses the existing `_NEXT_H2_RE` (defined at `entity_writer.py:947`).

**Files:**
- Create: `packages/wiki-io/tests/test_section_merge.py`
- Modify: `packages/wiki-io/src/wiki_io/entity_writer.py` (insert helpers immediately above `_render_entity_page`, which begins at line 501)

- [ ] **Step 1: Write the failing test**

Create `packages/wiki-io/tests/test_section_merge.py`:

```python
"""Unit tests for heading-aware section preservation helpers (Living Wiki M1)."""

from __future__ import annotations

from wiki_io.entity_writer import (
    _is_scanner_owned_heading,
    _merge_preserved_sections,
    _split_h2_sections,
)


def test_is_scanner_owned_heading_true_cases() -> None:
    assert _is_scanner_owned_heading("## Narrative")
    assert _is_scanner_owned_heading("## File map")
    assert _is_scanner_owned_heading("## File map - graph-io")
    assert _is_scanner_owned_heading("## Referenced in wiki")


def test_is_scanner_owned_heading_false_cases() -> None:
    assert not _is_scanner_owned_heading("## Purpose")
    assert not _is_scanner_owned_heading("## Public API")
    assert not _is_scanner_owned_heading("## Field Notes")


def test_split_h2_sections_round_trips() -> None:
    body = "# Title\n\nintro\n\n## A\na body\n\n## B\nb body\n"
    preamble, sections = _split_h2_sections(body)
    assert preamble == "# Title\n\nintro\n\n"
    assert [h for h, _ in sections] == ["## A", "## B"]
    # Lossless: preamble + all chunks reconstruct the original exactly.
    assert preamble + "".join(chunk for _, chunk in sections) == body


def test_split_h2_sections_no_headings() -> None:
    body = "# Title\n\njust an intro, no H2\n"
    preamble, sections = _split_h2_sections(body)
    assert preamble == body
    assert sections == []
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run --package wiki-io pytest packages/wiki-io/tests/test_section_merge.py -v`
Expected: FAIL — `ImportError: cannot import name '_is_scanner_owned_heading'` (and the other two).

- [ ] **Step 3: Write minimal implementation**

In `packages/wiki-io/src/wiki_io/entity_writer.py`, insert immediately **above** `def _render_entity_page(` (line 501). (`_NEXT_H2_RE` is a module global defined at line 947; it resolves at call time, so the forward reference is fine.)

```python
# ---------------------------------------------------------------------------
# Living Wiki M1: heading-aware section preservation (Approach A).
# Scanner-owned H2 sections are regenerated from the template every scan;
# every other H2 section is preserved from the existing page on re-scan.
# ---------------------------------------------------------------------------


def _is_scanner_owned_heading(heading: str) -> bool:
    """True for the three H2 sections the scanner regenerates each scan:
    `## Narrative`, `## File map[ - <name>]`, `## Referenced in wiki`.

    Everything else (e.g. `## Purpose`, `## Public API`, any hand-added H2)
    is human-owned and preserved across re-scan.
    """
    h = heading.strip()
    return (
        h == "## Narrative"
        or h.startswith("## File map")
        or h == "## Referenced in wiki"
    )


def _split_h2_sections(text: str) -> tuple[str, list[tuple[str, str]]]:
    """Split a page body into ``(preamble, [(heading, chunk), ...])``.

    ``preamble`` is everything before the first H2 (the H1 + any intro). Each
    ``chunk`` starts at its ``## `` heading and runs up to (but not including)
    the next H2, or EOF; ``heading`` is the stripped first line of the chunk.
    Lossless: ``preamble + "".join(chunks) == text`` (uses ``_NEXT_H2_RE``,
    defined at module scope below).
    """
    starts = [m.start() for m in _NEXT_H2_RE.finditer(text)]
    if not starts:
        return text, []
    preamble = text[: starts[0]]
    sections: list[tuple[str, str]] = []
    for i, start in enumerate(starts):
        end = starts[i + 1] if i + 1 < len(starts) else len(text)
        chunk = text[start:end]
        heading = chunk.split("\n", 1)[0].strip()
        sections.append((heading, chunk))
    return preamble, sections
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run --package wiki-io pytest packages/wiki-io/tests/test_section_merge.py -v`
Expected: PASS (4 tests). Note `_merge_preserved_sections` is imported but not yet exercised — its import resolves only after Task 2; if the import line fails here, add a temporary `_merge_preserved_sections` defined in Task 2 first. (It is defined in Task 2 in the same file, so prefer running Task 1 + Task 2 implementation before this import-level run, or temporarily drop `_merge_preserved_sections` from the import until Task 2.)

> Implementation note: to keep Step 4 green standalone, the import of `_merge_preserved_sections` will fail until Task 2. Either (a) run Tasks 1–2 implementation, then this command, or (b) temporarily remove `_merge_preserved_sections` from the Task-1 import and add it back in Task 2's test step. Option (a) is simplest.

- [ ] **Step 5: Commit**

```bash
git add packages/wiki-io/src/wiki_io/entity_writer.py packages/wiki-io/tests/test_section_merge.py
git commit -m "feat(wiki-io): add scanner-owned predicate + H2 section splitter"
```

---

## Task 2: Heading-aware merge function

The core pure transform: given a freshly-rendered template body and the existing page body, return a body where human-owned sections come from the existing page and scanner-owned sections keep the template placeholder. Idempotent by construction.

**Files:**
- Modify: `packages/wiki-io/src/wiki_io/entity_writer.py` (add `_merge_preserved_sections` after `_split_h2_sections` from Task 1)
- Modify: `packages/wiki-io/tests/test_section_merge.py` (add merge tests)

- [ ] **Step 1: Write the failing test**

Append to `packages/wiki-io/tests/test_section_merge.py`:

```python
def test_merge_identity_is_stable() -> None:
    """merge(t, t) == t — guarantees a no-edit re-scan is byte-identical."""
    body = "# T\n\n## Narrative\n_(placeholder)_\n\n## Purpose\n> TODO\n"
    assert _merge_preserved_sections(body, body) == body


def test_merge_preserves_human_section_and_regenerates_scanner_section() -> None:
    template = (
        "# T\n\n## Narrative\n_(placeholder)_\n\n## Purpose\n> TODO: fill me\n"
    )
    existing = (
        "# T\n\n## Narrative\nOLD NARRATIVE PROSE\n\n## Purpose\nReal human purpose.\n"
    )
    out = _merge_preserved_sections(template, existing)
    assert "Real human purpose." in out          # human section preserved
    assert "_(placeholder)_" in out               # scanner section from template
    assert "OLD NARRATIVE PROSE" not in out       # scanner section NOT preserved
    assert "> TODO: fill me" not in out           # template Purpose overwritten by human


def test_merge_appends_user_added_custom_section() -> None:
    template = "# T\n\n## Narrative\n_p_\n\n## Purpose\n> TODO\n"
    existing = (
        "# T\n\n## Narrative\n_p_\n\n## Purpose\nKept.\n\n## My Notes\ncustom stuff\n"
    )
    out = _merge_preserved_sections(template, existing)
    assert "## My Notes" in out
    assert "custom stuff" in out


def test_merge_file_map_is_scanner_owned() -> None:
    template = "# T\n\n## File map - foo\n> TODO\n\n## Purpose\n> TODO\n"
    existing = "# T\n\n## File map - foo\n| a | b | c |\n\n## Purpose\nKeep me.\n"
    out = _merge_preserved_sections(template, existing)
    assert "Keep me." in out                       # human Purpose preserved
    assert "| a | b | c |" not in out              # file map regenerated, not preserved


def test_merge_with_empty_existing_returns_template() -> None:
    template = "# T\n\n## Narrative\n_p_\n\n## Purpose\n> TODO\n"
    assert _merge_preserved_sections(template, "") == template
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run --package wiki-io pytest packages/wiki-io/tests/test_section_merge.py -k merge -v`
Expected: FAIL — `ImportError`/`AttributeError: _merge_preserved_sections` not defined.

- [ ] **Step 3: Write minimal implementation**

In `entity_writer.py`, add directly after `_split_h2_sections`:

```python
def _merge_preserved_sections(template_body: str, existing_body: str) -> str:
    """Merge human-owned sections from ``existing_body`` into ``template_body``.

    Scanner-owned sections (``_is_scanner_owned_heading``) always come from the
    template (placeholders the scan pipeline re-injects). Every other section
    whose heading appears in ``existing_body`` replaces the template's version;
    sections present only in ``existing_body`` (user-added) are appended in
    their original order. The preamble (H1 + intro) always comes from the
    template.

    Idempotent: ``_merge_preserved_sections(t, t) == t`` because the split is
    lossless and each section round-trips by heading.
    """
    pre_t, secs_t = _split_h2_sections(template_body)
    _pre_e, secs_e = _split_h2_sections(existing_body)

    existing_by_heading: dict[str, str] = {}
    for heading, chunk in secs_e:
        existing_by_heading.setdefault(heading, chunk)  # first occurrence wins

    out = [pre_t]
    template_headings: set[str] = set()
    consumed: set[str] = set()
    for heading, chunk in secs_t:
        template_headings.add(heading)
        if not _is_scanner_owned_heading(heading) and heading in existing_by_heading:
            out.append(existing_by_heading[heading])
            consumed.add(heading)
        else:
            out.append(chunk)

    # Preserve user-added sections the template does not define.
    for heading, chunk in secs_e:
        if (
            heading in template_headings
            or heading in consumed
            or _is_scanner_owned_heading(heading)
        ):
            continue
        consumed.add(heading)
        out.append(chunk)

    return "".join(out)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run --package wiki-io pytest packages/wiki-io/tests/test_section_merge.py -v`
Expected: PASS (all tests in the file, ~9).

- [ ] **Step 5: Commit**

```bash
git add packages/wiki-io/src/wiki_io/entity_writer.py packages/wiki-io/tests/test_section_merge.py
git commit -m "feat(wiki-io): add heading-aware section merge (idempotent)"
```

---

## Task 3: Wire the merge into the write path

Add an optional `existing_body` parameter to `_render_entity_page`; when provided, run the merge after token substitution. In `write_entities`, capture the existing page's body and pass it through. Existing-section content survives re-scan; scanner-owned sections still get refilled downstream by the scan pipeline.

**Files:**
- Modify: `packages/wiki-io/src/wiki_io/entity_writer.py` (`_render_entity_page` ~501-538; `write_entities` create/merge block ~839-863)
- Modify: `packages/wiki-io/tests/test_entity_writer.py` (add 2 tests near the existing write_entities tests, after line 612)

- [ ] **Step 1: Write the failing test**

Append to `packages/wiki-io/tests/test_entity_writer.py` (after `test_write_entities_needs_narrative_on_structural_change`, line 612). These reuse the existing module-level `_wire_mock_queries` helper and `mock_graph_conn` fixture.

```python
def test_write_entities_preserves_human_body_section_across_rescan(
    tmp_path, mock_graph_conn, monkeypatch,
):
    """A hand-filled ## Purpose section survives a second write_entities run."""
    from graph_io import queries as q
    _wire_mock_queries(monkeypatch, q)
    wiki_root = tmp_path / "wiki"
    write_entities(mock_graph_conn, wiki_root, ADMITTED_KINDS)

    page_path = wiki_root / "entities" / "pkg_graph-io.md"
    raw = page_path.read_text()
    marker = "> TODO: <One paragraph: what this package does, who uses it, why it exists.>"
    assert marker in raw, "expected the package template's Purpose placeholder"
    human_prose = "The graph-io package builds and queries the SQLite code graph."
    page_path.write_text(raw.replace(marker, human_prose))

    write_entities(mock_graph_conn, wiki_root, ADMITTED_KINDS)
    final = page_path.read_text()
    assert human_prose in final            # human ## Purpose preserved
    assert "## Public API" in final        # sibling sections intact


def test_write_entities_preserves_custom_h2_across_rescan(
    tmp_path, mock_graph_conn, monkeypatch,
):
    """A user-added H2 section (not in the template) survives a re-scan."""
    from graph_io import queries as q
    _wire_mock_queries(monkeypatch, q)
    wiki_root = tmp_path / "wiki"
    write_entities(mock_graph_conn, wiki_root, ADMITTED_KINDS)

    page_path = wiki_root / "entities" / "pkg_graph-io.md"
    raw = page_path.read_text()
    page_path.write_text(raw.rstrip() + "\n\n## Field Notes\nMy hand-written notes.\n")

    write_entities(mock_graph_conn, wiki_root, ADMITTED_KINDS)
    final = page_path.read_text()
    assert "## Field Notes" in final
    assert "My hand-written notes." in final
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run --package wiki-io pytest packages/wiki-io/tests/test_entity_writer.py -k "preserves_human_body_section or preserves_custom_h2" -v`
Expected: FAIL — both assert the preserved content is present, but the current code re-renders from template (wiping it). `assert human_prose in final` / `assert "## Field Notes" in final` fail.

- [ ] **Step 3: Write minimal implementation**

Edit 3a — add the parameter and merge call in `_render_entity_page`. Change the signature (currently lines 501-503):

```python
def _render_entity_page(
    template_path: Path, frontmatter_dict: dict, variables: dict[str, str]
) -> str:
```

to:

```python
def _render_entity_page(
    template_path: Path,
    frontmatter_dict: dict,
    variables: dict[str, str],
    existing_body: str | None = None,
) -> str:
```

Then, in the same function, immediately after the residual-token rewrite (the `body = _RESIDUAL_TOKEN_RE.sub(...)` block ends at line 528) and **before** `yaml_block = yaml.safe_dump(` (line 529), insert:

```python
    # Living Wiki M1: preserve human-owned sections from the existing page.
    if existing_body is not None:
        body = _merge_preserved_sections(body, existing_body)
```

Edit 3b — in `write_entities`, capture and pass the existing body. Replace the existing block (lines 839-844):

```python
                    existing_fm: dict = {}
                    existed = page_path.exists()
                    if existed:
                        post = frontmatter.load(page_path)
                        existing_fm = dict(post.metadata)
                    merged_fm = merge_frontmatter(existing_fm, scanner_fm)
```

with:

```python
                    existing_fm: dict = {}
                    existing_body: str | None = None
                    existed = page_path.exists()
                    if existed:
                        post = frontmatter.load(page_path)
                        existing_fm = dict(post.metadata)
                        existing_body = post.content
                    merged_fm = merge_frontmatter(existing_fm, scanner_fm)
```

Then update the `_render_entity_page` call (currently lines 861-863):

```python
                    new_content = _render_entity_page(
                        template_path, merged_fm, variables
                    )
```

to:

```python
                    new_content = _render_entity_page(
                        template_path, merged_fm, variables,
                        existing_body=existing_body,
                    )
```

- [ ] **Step 4: Run the new tests to verify they pass**

Run: `uv run --package wiki-io pytest packages/wiki-io/tests/test_entity_writer.py -k "preserves_human_body_section or preserves_custom_h2" -v`
Expected: PASS (2 tests).

- [ ] **Step 5: Run the full entity-writer + idempotence suites (regression guard)**

Run: `uv run --package wiki-io pytest packages/wiki-io/tests/test_entity_writer.py packages/wiki-io/tests/test_inject_narrative.py packages/wiki-io/tests/test_inject_file_map.py packages/wiki-io/tests/integration/test_entity_writer_integration.py -v`
Expected: PASS. In particular `test_write_entities_second_run_all_unchanged` and `test_determinism_second_run_all_unchanged` must stay green — they prove the merge is idempotent on unedited pages (`merge(t, t) == t`).

- [ ] **Step 6: Commit**

```bash
git add packages/wiki-io/src/wiki_io/entity_writer.py packages/wiki-io/tests/test_entity_writer.py
git commit -m "feat(wiki-io): preserve human entity-page sections across re-scan"
```

---

## Task 4: Remove the four forward-link stub sections from templates

Delete `## Concepts`, `## Dependencies`, `## Decisions`, `## Contrasts / alternatives` (and `agent-plugin`'s three: no `## Dependencies`) — they are never populated and are superseded by `## Referenced in wiki`. In every template these are the contiguous trailing block, so the deletion runs from the first stub heading to EOF, leaving exactly one trailing newline after the now-last real section.

**Files:**
- Modify: `entity-package.md`, `entity-app.md`, `entity-domain.md`, `entity-dependency.md`, `entity-agent-plugin.md` (under `packages/wiki-io/src/wiki_io/assets/page-templates/`)
- Modify: `packages/wiki-io/tests/test_entity_templates.py` (regression test)

- [ ] **Step 1: Write the failing test**

Append to `packages/wiki-io/tests/test_entity_templates.py` (it already defines `ENTITY_TEMPLATES` at line 25 and imports `re`, `pytest`, `Path`):

```python
_FORWARD_LINK_HEADINGS = (
    "## Concepts",
    "## Dependencies",
    "## Decisions",
    "## Contrasts / alternatives",
)


@pytest.mark.parametrize(
    "template_path",
    ENTITY_TEMPLATES,
    ids=[p.name for p in ENTITY_TEMPLATES],
)
def test_no_forward_link_stub_sections(template_path: Path) -> None:
    """Entity templates must not carry the duplicative forward-link stubs;
    `## Referenced in wiki` (backlinks) supersedes them (Living Wiki M1)."""
    text = template_path.read_text(encoding="utf-8")
    for heading in _FORWARD_LINK_HEADINGS:
        assert not re.search(
            rf"^{re.escape(heading)}\s*$", text, re.MULTILINE
        ), f"{template_path.name} still carries `{heading}`"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run --package wiki-io pytest packages/wiki-io/tests/test_entity_templates.py -k no_forward_link_stub -v`
Expected: FAIL for `entity-package.md`, `entity-app.md`, `entity-domain.md`, `entity-dependency.md`, `entity-agent-plugin.md` (each still carries the stubs). `entity-repository.md` and `entity-test-suite.md` PASS (they never had them).

- [ ] **Step 3: Remove the stub block from each template**

For each file, delete the contiguous trailing block. Use the Edit tool; each `old_string` below is the exact trailing text to remove (delete it entirely, leaving the file ending after the preceding section with a single trailing newline). After editing, the file's last real section is noted.

**`entity-package.md`** — remove (last real section becomes `## Public API`):
```

## Concepts
- [[concepts/<concept>]]

## Dependencies
- [[dependencies/<lib>]]

## Decisions
- [[adrs/<id>-<slug>]]

## Contrasts / alternatives
- [[concepts/<a>-vs-<b>]]
```

**`entity-app.md`** — remove (last real section becomes `## File map - {{app_name}}`):
```

## Concepts
- [[concepts/<concept>]]

## Dependencies
- [[dependencies/<lib>]]

## Decisions
- [[adrs/<id>-<slug>]]

## Contrasts / alternatives
- [[concepts/<a>-vs-<b>]]
```

**`entity-domain.md`** — remove (last real section becomes `## Key flows`):
```

## Concepts
- [[concepts/<concept>]]

## Dependencies
- [[dependencies/<lib>]]

## Decisions
- [[adrs/<id>-<slug>]]

## Contrasts / alternatives
- [[concepts/<a>-vs-<b>]]
```

**`entity-dependency.md`** — remove (last real section becomes `## Gotchas / workarounds`):
```

## Concepts
- [[concepts/<concept>]]

## Dependencies
- [[dependencies/<lib>]]

## Decisions
- [[adrs/<id>-<slug>]]

## Contrasts / alternatives
- [[concepts/<a>-vs-<b>]]
```

**`entity-agent-plugin.md`** — remove (note: only THREE sections, no `## Dependencies`; last real section becomes `## How it fits together`):
```

## Concepts
- [[concepts/<concept>]]

## Decisions
- [[adrs/<id>-<slug>]]

## Contrasts / alternatives
- [[concepts/<a>-vs-<b>]]
```

> If an `old_string` fails to match due to a trailing-newline difference at EOF, read the file's last lines and adjust the trailing newline of the `old_string` to match exactly. Each file must still end with a single newline after its new last section.

- [ ] **Step 4: Run the regression test + template suite to verify pass**

Run: `uv run --package wiki-io pytest packages/wiki-io/tests/test_entity_templates.py -v`
Expected: PASS — `test_no_forward_link_stub_sections` passes for all 7 templates; `test_six_entity_templates_exist`, `test_each_template_has_narrative_h2`, and the migrated-section tests still pass (none of those sections were removed).

- [ ] **Step 5: Confirm merge tests still pass with the slimmer templates**

Run: `uv run --package wiki-io pytest packages/wiki-io/tests/test_entity_writer.py packages/wiki-io/tests/test_section_merge.py -v`
Expected: PASS (the merge logic is template-agnostic; removing sections doesn't affect it).

- [ ] **Step 6: Commit**

```bash
git add packages/wiki-io/src/wiki_io/assets/page-templates/entity-package.md \
        packages/wiki-io/src/wiki_io/assets/page-templates/entity-app.md \
        packages/wiki-io/src/wiki_io/assets/page-templates/entity-domain.md \
        packages/wiki-io/src/wiki_io/assets/page-templates/entity-dependency.md \
        packages/wiki-io/src/wiki_io/assets/page-templates/entity-agent-plugin.md \
        packages/wiki-io/tests/test_entity_templates.py
git commit -m "feat(wiki-io): drop duplicative forward-link stub sections from entity templates"
```

---

## Task 5: Update the backward-compatibility rule wording

Refine the entity-content bullet to the section-ownership model so the rule no longer reads as "all entity content is disposable" (which now contradicts the preservation behavior).

**Files:**
- Modify: `.claude/rules/backward-compatibility.md`

- [ ] **Step 1: Make the edit**

Replace this line:

```markdown
* `entity` content can be deleted and regenerated at will.
```

with:

```markdown
* `entity` content is split by ownership:
    * **scanner-owned** sections (`## Narrative`, `## File map`, `## Referenced in wiki`) and scanner-owned frontmatter keys are regenerated from the graph every scan — these can be deleted and regenerated at will.
    * **human-owned** sections (e.g. `## Purpose`, `## Public API`, any hand-added H2) and human frontmatter keys (`status`, `last_reviewed`, `owner`, `notes`) are preserved across re-scan and should be treated like other curated content.
```

- [ ] **Step 2: Verify the file reads correctly**

Run: `grep -n "human-owned\|scanner-owned" .claude/rules/backward-compatibility.md`
Expected: matches showing both new bullets present.

- [ ] **Step 3: Commit**

```bash
git add .claude/rules/backward-compatibility.md
git commit -m "docs: refine entity backward-compat rule to section-ownership model"
```

---

## Task 6: Full wiki-io suite verification

Final regression gate across the whole package.

**Files:** none (verification only)

- [ ] **Step 1: Run the full wiki-io test suite**

Run: `uv run --package wiki-io pytest packages/wiki-io/tests/ -v`
Expected: PASS (no failures, no errors). If `test_index_generator.py::test_snapshot_against_agent_research` runs and fails, it is a pre-existing live-snapshot test gated on a local `graph.db`; confirm it is unrelated to template/section changes (it snapshots `index.md`, not entity bodies). If it legitimately changed, regenerate with `uv run --package wiki-io pytest packages/wiki-io/tests/test_index_generator.py --snapshot-update` and inspect the diff before accepting.

- [ ] **Step 2: Final confirmation**

Confirm the working tree is clean and all task commits are present:

Run: `git log --oneline -6 && git status`
Expected: 5 feature/docs commits from Tasks 1–5; clean working tree.

---

## Self-Review

**1. Spec coverage** (roadmap §4 "M1 — Preservation"):
- "re-scan preserves all non-scanner-owned H2 sections; regenerates only `## Narrative`, `## File map`, `## Referenced in wiki`" → Tasks 1–3 (`_is_scanner_owned_heading` + `_merge_preserved_sections`, wired into `write_entities`). ✓
- "Remove `## Concepts`/`## Dependencies`/`## Decisions`/`## Contrasts` from all entity templates" → Task 4. ✓
- "Tests: preserves hand-edited `## Purpose`/`## Public API` and a user-added custom H2; still regenerates the three scanner sections; File-map preservation continues; byte-stability/idempotence on no-op re-scan" → Task 2 (`test_merge_file_map_is_scanner_owned`, identity test), Task 3 (two rescan tests + idempotence regression run). ✓
- "Update `.claude/rules/backward-compatibility.md` to the section-ownership model" → Task 5. ✓
- Out-of-scope items (commit gating, template reconciliation) correctly deferred. ✓

**2. Placeholder scan:** No "TBD"/"implement later"/"handle edge cases" — every code/test step shows complete content. The only conditional note is the EOF-newline guard in Task 4 Step 3, which gives an explicit recovery instruction, not a placeholder.

**3. Type/name consistency:** `_is_scanner_owned_heading`, `_split_h2_sections`, `_merge_preserved_sections`, and the `existing_body` parameter are spelled identically across Tasks 1–3 and the tests. `ENTITY_TEMPLATES` and `_FORWARD_LINK_HEADINGS` match the existing `test_entity_templates.py` structure.

**4. Known interaction verified:** the merge keeps scanner-owned sections as template placeholders, which the downstream scan pipeline (`inject_narrative`, `inject_file_map` with preserved descriptions, `regenerate_referenced_in_wiki`) refills — so File-map description preservation and narrative regeneration behave exactly as before. M1 does not change `needs_narrative` gating.
