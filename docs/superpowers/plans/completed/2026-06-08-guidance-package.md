# `guidance-io` Package (Base Slice) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Stand up the `guidance-io` package skeleton — frontmatter parse/emit/validate, path helpers, and a shipped `guidance.md` page template — for the new `guidance` wiki page family.

**Architecture:** A new `uv`-workspace member `guidance-io` mirroring the existing `work-io` package (the closest precedent: a distinct page-family with its own `-io` package). It contains page-type-agnostic frontmatter primitives copied verbatim from `work_io.frontmatter`, plus a `validate()` for the guidance schema, plus `paths.py` resolving `wiki/guidance/<topic>/<slug>.md`. A `guidance.md` template is added to `wiki-io`'s `page-templates/` assets (auto-copied into vaults by the existing `init_vault` machinery — no code change needed). This base slice deliberately excludes the importer, search, curator, sidecar, and lint rules (deferred to follow-up specs).

**Tech Stack:** Python 3.11+, `uv` workspace, `pyyaml`, `pytest` (per-package, `--import-mode=importlib`).

---

## Background notes for the implementer

Read these before starting — they prevent the most likely mistakes:

- **This is a `uv` workspace.** `members = ["packages/*"]` in the root `pyproject.toml`, so dropping a new directory under `packages/` auto-registers it as a member. No root edit is required. After creating the package, run `uv sync` from the repo root so the editable install is wired up.
- **Tests are per-package.** Never run `pytest` from the repo root. Use `uv run --package guidance-io pytest`.
- **The `parse`/`emit` functions are page-type-agnostic.** The spec says to copy `work_io.frontmatter`'s implementations verbatim. Do not "improve" them — byte-for-byte identical bodies (only the module docstring changes).
- **The page template is auto-copied.** `wiki_io.init_vault` walks `page-templates/` with `rglob("*")` and copies every file into a vault's `.templates/` dir. Adding `guidance.md` there is sufficient — there is **no** registry/list to update.
- **`validate()` returns a list of messages, not exceptions.** This matches the house validator style (`work_io.lifecycle_lint.run_lint -> list[LintFinding]`). Empty list == valid.

## File structure

Files created by this plan:

- `packages/guidance-io/pyproject.toml` — package manifest (mirrors `work-io/pyproject.toml`).
- `packages/guidance-io/src/guidance_io/__init__.py` — empty (mirrors `work_io/__init__.py`).
- `packages/guidance-io/src/guidance_io/frontmatter.py` — `parse`, `emit` (verbatim copy), `validate`.
- `packages/guidance-io/src/guidance_io/paths.py` — `guidance_dir`, `slugify`, `page_path`, `list_pages`.
- `packages/guidance-io/tests/__init__.py` — empty.
- `packages/guidance-io/tests/unit/__init__.py` — empty.
- `packages/guidance-io/tests/unit/test_frontmatter.py` — parse/emit/validate tests.
- `packages/guidance-io/tests/unit/test_paths.py` — path helper tests.
- `packages/guidance-io/tests/unit/test_template.py` — shipped-template parse+validate test.
- `packages/wiki-io/src/wiki_io/assets/page-templates/guidance.md` — the page template.

---

## Task 1: Scaffold the `guidance-io` package

**Files:**
- Create: `packages/guidance-io/pyproject.toml`
- Create: `packages/guidance-io/src/guidance_io/__init__.py`
- Create: `packages/guidance-io/tests/__init__.py`
- Create: `packages/guidance-io/tests/unit/__init__.py`
- Test: `packages/guidance-io/tests/unit/test_smoke.py`

- [ ] **Step 1: Create the package manifest**

Create `packages/guidance-io/pyproject.toml`:

```toml
[project]
name = "guidance-io"
version = "0.1.0"
description = "Frontmatter, paths, and lifecycle helpers for graph-wiki guidance pages."
requires-python = ">=3.11"
dependencies = ["workspace-io", "pyyaml>=6.0"]

[build-system]
requires = ["uv_build>=0.11.14,<0.12"]
build-backend = "uv_build"

[tool.uv.sources]
workspace-io = { workspace = true }

[tool.pytest.ini_options]
testpaths = ["tests"]
addopts = "--import-mode=importlib"
asyncio_mode = "auto"
markers = ["integration: requires real Bedrock or subprocess (skipped in CI by default)"]
```

- [ ] **Step 2: Create the empty package and test `__init__` files**

Create three empty files (0 bytes each, exactly as `work_io/__init__.py` is empty):

```bash
mkdir -p packages/guidance-io/src/guidance_io packages/guidance-io/tests/unit
: > packages/guidance-io/src/guidance_io/__init__.py
: > packages/guidance-io/tests/__init__.py
: > packages/guidance-io/tests/unit/__init__.py
```

- [ ] **Step 3: Write a smoke test**

Create `packages/guidance-io/tests/unit/test_smoke.py`:

```python
from __future__ import annotations


def test_package_imports() -> None:
    import guidance_io  # noqa: F401
```

- [ ] **Step 4: Sync the workspace so the new member installs**

Run: `uv sync`
Expected: completes without error; output mentions `guidance-io` among the resolved/installed members (e.g. `+ guidance-io==0.1.0` or it appears in the editable set).

- [ ] **Step 5: Run the smoke test to verify the package is importable**

Run: `uv run --package guidance-io pytest -q`
Expected: PASS — `1 passed`.

- [ ] **Step 6: Commit**

```bash
git add packages/guidance-io/pyproject.toml \
        packages/guidance-io/src/guidance_io/__init__.py \
        packages/guidance-io/tests/__init__.py \
        packages/guidance-io/tests/unit/__init__.py \
        packages/guidance-io/tests/unit/test_smoke.py \
        uv.lock
git commit -m "feat(guidance-io): scaffold base package skeleton"
```

---

## Task 2: Frontmatter `parse` / `emit` (verbatim copy)

**Files:**
- Create: `packages/guidance-io/src/guidance_io/frontmatter.py`
- Test: `packages/guidance-io/tests/unit/test_frontmatter.py`

- [ ] **Step 1: Write the failing tests**

Create `packages/guidance-io/tests/unit/test_frontmatter.py`:

```python
from __future__ import annotations

import pytest
from guidance_io.frontmatter import emit, parse


def test_parse_roundtrip() -> None:
    text = "---\ntitle: Use a Virtualizer\ncategory: guidance\n---\n\n## Guidance\nContent.\n"
    fm, body = parse(text)
    assert fm == {"title": "Use a Virtualizer", "category": "guidance"}
    assert body.strip() == "## Guidance\nContent."


def test_parse_nested_triggers_block() -> None:
    text = (
        "---\n"
        "triggers:\n"
        "  globs: ['**/*.tsx']\n"
        "  keywords: [ScrollView, FlatList]\n"
        "---\n"
    )
    fm, _ = parse(text)
    assert fm["triggers"]["globs"] == ["**/*.tsx"]
    assert fm["triggers"]["keywords"] == ["ScrollView", "FlatList"]


def test_parse_missing_open_fence_raises() -> None:
    with pytest.raises(ValueError, match="no frontmatter block"):
        parse("title: foo\n")


def test_parse_unclosed_fence_raises() -> None:
    with pytest.raises(ValueError, match="unclosed frontmatter"):
        parse("---\ntitle: foo\n")


def test_parse_non_mapping_raises() -> None:
    with pytest.raises(ValueError, match="YAML mapping"):
        parse("---\n- item1\n- item2\n---\n")


def test_emit_parse_roundtrip() -> None:
    fm = {"title": "Test", "category": "guidance", "tags": ["performance", "lists"]}
    emitted = emit(fm)
    parsed_fm, _ = parse(emitted + "\n\nbody\n")
    assert parsed_fm == fm
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run --package guidance-io pytest tests/unit/test_frontmatter.py -q`
Expected: FAIL — `ModuleNotFoundError: No module named 'guidance_io.frontmatter'`.

- [ ] **Step 3: Write the implementation**

Create `packages/guidance-io/src/guidance_io/frontmatter.py` (the `parse`/`emit` bodies are copied verbatim from `work_io.frontmatter` — they are page-type-agnostic):

```python
"""Frontmatter parse/emit/validate for guidance pages."""

from __future__ import annotations

import yaml


def parse(text: str) -> tuple[dict, str]:
    """Return (frontmatter_dict, body_text). Raises ValueError on malformed input."""
    if not text.startswith("---"):
        raise ValueError("no frontmatter block found: text must start with ---")
    rest = text[3:]
    if "\n---" not in rest:
        raise ValueError("unclosed frontmatter block: no closing ---")
    idx = rest.index("\n---")
    fm_text = rest[:idx].strip()
    body = rest[idx + 4 :]
    if body.startswith("\n"):
        body = body[1:]
    fm = yaml.safe_load(fm_text) if fm_text else {}
    if fm is None:
        fm = {}
    if not isinstance(fm, dict):
        raise ValueError(f"frontmatter must be a YAML mapping, got {type(fm).__name__}")
    return fm, body


def emit(fm: dict) -> str:
    """Serialize frontmatter dict to a fenced YAML block (--- ... ---)."""
    content = yaml.safe_dump(fm, default_flow_style=False, sort_keys=False, allow_unicode=True)
    return f"---\n{content}---"
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run --package guidance-io pytest tests/unit/test_frontmatter.py -q`
Expected: PASS — `6 passed`.

- [ ] **Step 5: Commit**

```bash
git add packages/guidance-io/src/guidance_io/frontmatter.py \
        packages/guidance-io/tests/unit/test_frontmatter.py
git commit -m "feat(guidance-io): frontmatter parse/emit"
```

---

## Task 3: Frontmatter `validate`

**Files:**
- Modify: `packages/guidance-io/src/guidance_io/frontmatter.py`
- Test: `packages/guidance-io/tests/unit/test_frontmatter.py` (append)

The validator enforces the spec's rules: required keys present, `category == "guidance"`, `impact` in the enum, `topic` non-empty, and `triggers` (when present) is a mapping whose `globs`/`keywords`/`entities` are lists. It returns a list of human-readable violation strings (empty == valid), matching the house validator style.

- [ ] **Step 1: Write the failing tests**

Append to `packages/guidance-io/tests/unit/test_frontmatter.py`:

```python
from guidance_io.frontmatter import validate


def _valid_fm() -> dict:
    return {
        "title": "Use a List Virtualizer for Any List",
        "category": "guidance",
        "summary": "Use a virtualizer instead of ScrollView for lists.",
        "topic": "react-native",
        "applies_when": "Rendering any scrollable list in React Native.",
        "impact": "high",
        "updated": "2026-06-08",
        "tokens": 0,
    }


def test_validate_accepts_minimal_valid_fm() -> None:
    assert validate(_valid_fm()) == []


def test_validate_accepts_full_triggers_block() -> None:
    fm = _valid_fm()
    fm["triggers"] = {
        "globs": ["**/*.tsx"],
        "keywords": ["ScrollView", "FlatList"],
        "entities": ["[[entities/pkg_foo]]"],
    }
    assert validate(fm) == []


def test_validate_flags_missing_required_key() -> None:
    fm = _valid_fm()
    del fm["summary"]
    errors = validate(fm)
    assert any("summary" in e for e in errors)


def test_validate_flags_wrong_category() -> None:
    fm = _valid_fm()
    fm["category"] = "concept"
    errors = validate(fm)
    assert any("category" in e for e in errors)


def test_validate_flags_bad_impact() -> None:
    fm = _valid_fm()
    fm["impact"] = "HIGH"  # uppercase is invalid; enum is lowercased
    errors = validate(fm)
    assert any("impact" in e for e in errors)


def test_validate_flags_empty_topic() -> None:
    fm = _valid_fm()
    fm["topic"] = "  "
    errors = validate(fm)
    assert any("topic" in e for e in errors)


def test_validate_flags_non_mapping_triggers() -> None:
    fm = _valid_fm()
    fm["triggers"] = ["**/*.tsx"]
    errors = validate(fm)
    assert any("triggers" in e for e in errors)


def test_validate_flags_non_list_trigger_value() -> None:
    fm = _valid_fm()
    fm["triggers"] = {"globs": "**/*.tsx"}  # should be a list
    errors = validate(fm)
    assert any("globs" in e for e in errors)
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run --package guidance-io pytest tests/unit/test_frontmatter.py -q`
Expected: FAIL — `ImportError: cannot import name 'validate' from 'guidance_io.frontmatter'`.

- [ ] **Step 3: Write the implementation**

Add the module-level constants directly under the imports in `packages/guidance-io/src/guidance_io/frontmatter.py`:

```python
REQUIRED_KEYS = ("title", "category", "summary", "topic", "applies_when", "impact", "updated", "tokens")
IMPACT_VALUES = ("critical", "high", "medium", "low")
TRIGGER_LIST_KEYS = ("globs", "keywords", "entities")
```

Then append the function at the end of the file:

```python
def validate(fm: dict) -> list[str]:
    """Return a list of violation messages for a guidance frontmatter dict.

    Empty list means valid. Checks: required keys present, category fixed to
    'guidance', impact in the lowercased enum, topic non-empty, and (when
    present) triggers is a mapping whose globs/keywords/entities are lists.
    """
    errors: list[str] = []

    for key in REQUIRED_KEYS:
        if key not in fm:
            errors.append(f"missing required key: {key}")

    if fm.get("category") != "guidance":
        errors.append(f"category must be 'guidance', got {fm.get('category')!r}")

    impact = fm.get("impact")
    if impact is not None and impact not in IMPACT_VALUES:
        errors.append(f"impact must be one of {IMPACT_VALUES}, got {impact!r}")

    if "topic" in fm:
        topic = fm["topic"]
        if not isinstance(topic, str) or not topic.strip():
            errors.append("topic must be a non-empty string")

    triggers = fm.get("triggers")
    if triggers is not None:
        if not isinstance(triggers, dict):
            errors.append(f"triggers must be a mapping, got {type(triggers).__name__}")
        else:
            for tk in TRIGGER_LIST_KEYS:
                if tk in triggers and not isinstance(triggers[tk], list):
                    errors.append(f"triggers.{tk} must be a list, got {type(triggers[tk]).__name__}")

    return errors
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run --package guidance-io pytest tests/unit/test_frontmatter.py -q`
Expected: PASS — all frontmatter tests green (6 from Task 2 + 8 here = `14 passed`).

- [ ] **Step 5: Commit**

```bash
git add packages/guidance-io/src/guidance_io/frontmatter.py \
        packages/guidance-io/tests/unit/test_frontmatter.py
git commit -m "feat(guidance-io): frontmatter validate()"
```

---

## Task 4: Path helpers

**Files:**
- Create: `packages/guidance-io/src/guidance_io/paths.py`
- Test: `packages/guidance-io/tests/unit/test_paths.py`

Path helpers resolve `wiki/guidance/<topic>/<slug>.md`, slugify a title, and list pages within a topic. They do no business logic beyond path composition + a directory glob, mirroring `workspace_io.paths` (pure) and `work_io`'s slug pattern (`re.compile(r"[^a-z0-9]+")`).

- [ ] **Step 1: Write the failing tests**

Create `packages/guidance-io/tests/unit/test_paths.py`:

```python
from __future__ import annotations

from pathlib import Path

from guidance_io.paths import guidance_dir, list_pages, page_path, slugify


def test_guidance_dir_is_under_wiki() -> None:
    ws = Path("/tmp/ws")
    assert guidance_dir(ws) == ws / "wiki" / "guidance"


def test_page_path_composes_topic_and_slug() -> None:
    ws = Path("/tmp/ws")
    assert page_path(ws, "react-native", "use-a-virtualizer") == (
        ws / "wiki" / "guidance" / "react-native" / "use-a-virtualizer.md"
    )


def test_slugify_lowercases_and_dashes() -> None:
    assert slugify("Use a List Virtualizer for Any List") == "use-a-list-virtualizer-for-any-list"


def test_slugify_strips_punctuation_and_edges() -> None:
    assert slugify("  FlashList / LegendList!  ") == "flashlist-legendlist"


def test_slugify_empty_returns_untitled() -> None:
    assert slugify("!!!") == "untitled"


def test_list_pages_returns_sorted_md(tmp_path: Path) -> None:
    topic_dir = tmp_path / "wiki" / "guidance" / "react-native"
    topic_dir.mkdir(parents=True)
    (topic_dir / "b-page.md").write_text("---\n---\n", encoding="utf-8")
    (topic_dir / "a-page.md").write_text("---\n---\n", encoding="utf-8")
    (topic_dir / "notes.txt").write_text("ignore me", encoding="utf-8")
    pages = list_pages(tmp_path, "react-native")
    assert [p.name for p in pages] == ["a-page.md", "b-page.md"]


def test_list_pages_absent_topic_returns_empty(tmp_path: Path) -> None:
    assert list_pages(tmp_path, "nonexistent") == []
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run --package guidance-io pytest tests/unit/test_paths.py -q`
Expected: FAIL — `ModuleNotFoundError: No module named 'guidance_io.paths'`.

- [ ] **Step 3: Write the implementation**

Create `packages/guidance-io/src/guidance_io/paths.py`:

```python
"""Pure path accessors for guidance pages: wiki/guidance/<topic>/<slug>.md.

Callers obtain the workspace from `workspace_io.config.resolve()` and pass
`.workspace` here. These functions do no business logic — they compose paths
and, for `list_pages`, glob a single directory.
"""

from __future__ import annotations

import re
from pathlib import Path

from workspace_io.paths import wiki_dir

_SLUG_RE = re.compile(r"[^a-z0-9]+")


def guidance_dir(workspace: Path) -> Path:
    """The wiki/guidance/ root holding per-topic subfolders."""
    return wiki_dir(workspace) / "guidance"


def slugify(title: str) -> str:
    """Lowercase a title and collapse non-alphanumeric runs to '-'.

    Edge dashes are trimmed; an otherwise-empty result becomes 'untitled'.
    """
    s = _SLUG_RE.sub("-", title.lower()).strip("-")
    return s or "untitled"


def page_path(workspace: Path, topic: str, slug: str) -> Path:
    """Resolve wiki/guidance/<topic>/<slug>.md (no I/O)."""
    return guidance_dir(workspace) / topic / f"{slug}.md"


def list_pages(workspace: Path, topic: str) -> list[Path]:
    """Sorted .md pages under a topic folder; empty list if the folder is absent."""
    topic_dir = guidance_dir(workspace) / topic
    if not topic_dir.is_dir():
        return []
    return sorted(topic_dir.glob("*.md"))
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run --package guidance-io pytest tests/unit/test_paths.py -q`
Expected: PASS — `7 passed`.

- [ ] **Step 5: Commit**

```bash
git add packages/guidance-io/src/guidance_io/paths.py \
        packages/guidance-io/tests/unit/test_paths.py
git commit -m "feat(guidance-io): path helpers"
```

---

## Task 5: `guidance.md` page template

**Files:**
- Create: `packages/wiki-io/src/wiki_io/assets/page-templates/guidance.md`
- Test: `packages/guidance-io/tests/unit/test_template.py`

The template carries the spec's frontmatter (filled with concrete, parseable, *valid* values so the shipped template passes `validate()`) plus a minimal body: `## Guidance`, optional `## Incorrect` / `## Correct` examples, and a `## Applies to` section that mirrors `triggers.entities` as `[[entities/...]]` wikilinks. The `## Applies to` mirror is load-bearing: it gives each referenced entity page a `## Referenced in wiki` backlink from guidance for free via the existing backlink index (same pattern as work pages' `affects` and the M3 suggestion step's `suggested_pages`).

The test reads the shipped template through `importlib.resources` (the same anchor `wiki_io.entity_writer` uses) and asserts it both parses and validates clean. `wiki_io` is importable from any workspace test because the workspace installs every member editable — even though `guidance-io` does not declare a `wiki-io` dependency (it deliberately does not, per spec).

- [ ] **Step 1: Write the failing test**

Create `packages/guidance-io/tests/unit/test_template.py`:

```python
from __future__ import annotations

from importlib.resources import files

from guidance_io.frontmatter import parse, validate


def _template_text() -> str:
    return files("wiki_io.assets.page-templates").joinpath("guidance.md").read_text(encoding="utf-8")


def test_shipped_template_parses() -> None:
    fm, body = parse(_template_text())
    assert fm["category"] == "guidance"
    assert "## Guidance" in body
    assert "## Applies to" in body


def test_shipped_template_validates_clean() -> None:
    fm, _ = parse(_template_text())
    assert validate(fm) == []


def test_shipped_template_has_triggers_block() -> None:
    fm, _ = parse(_template_text())
    assert isinstance(fm["triggers"], dict)
    assert isinstance(fm["triggers"]["globs"], list)
    assert isinstance(fm["triggers"]["keywords"], list)
    assert isinstance(fm["triggers"]["entities"], list)
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `uv run --package guidance-io pytest tests/unit/test_template.py -q`
Expected: FAIL — `FileNotFoundError` / resource-not-found when reading `guidance.md` (the template does not exist yet).

- [ ] **Step 3: Create the template**

Create `packages/wiki-io/src/wiki_io/assets/page-templates/guidance.md`:

```markdown
---
title: <Guidance title>
category: guidance               # spine — fixed value
summary: <one-line — what to do and why, also a relevance signal>
topic: <topic>                   # taxonomy axis + folder name under wiki/guidance/
applies_when: <one-sentence prose trigger — what the curator ranks against>
triggers:                        # structured pre-filter — block + all keys optional
  globs: []                      # e.g. ['**/*.tsx']
  keywords: []                   # e.g. [ScrollView, FlatList, virtualization]
  entities: []                   # e.g. ['[[entities/pkg_...]]'] — curate by code the task touches
tags: []                         # coarse free-form filter
impact: medium                   # critical | high | medium | low
source:                          # provenance — imported skill/repo the bit came from
updated: <YYYY-MM-DD>
tokens: 0
---

# <Guidance title>

## Guidance
The prescriptive bit: how to do X correctly, and why it matters.

## Incorrect
```
# the anti-pattern this guidance steers away from
```

## Correct
```
# the recommended approach
```

## Applies to
- [[entities/<prefix>_<name>]]
```

- [ ] **Step 4: Run the test to verify it passes**

Run: `uv run --package guidance-io pytest tests/unit/test_template.py -q`
Expected: PASS — `3 passed`.

Note: `topic: <topic>` and `title: <Guidance title>` are non-empty plain-scalar strings (YAML does not treat a leading `<` as a reserved indicator — only `@` and `` ` `` are), so they parse as strings and satisfy the non-empty `topic` check. `impact: medium` is in the enum. `source:` is left blank (optional key — absence/`None` is fine; it is not in `REQUIRED_KEYS`).

- [ ] **Step 5: Commit**

```bash
git add packages/wiki-io/src/wiki_io/assets/page-templates/guidance.md \
        packages/guidance-io/tests/unit/test_template.py
git commit -m "feat(wiki-io): guidance page template + shipped-template test"
```

---

## Task 6: Full-package verification

**Files:** none (verification only)

- [ ] **Step 1: Run the full `guidance-io` suite**

Run: `uv run --package guidance-io pytest -q`
Expected: PASS — all tests green (`test_smoke` 1 + `test_frontmatter` 14 + `test_paths` 7 + `test_template` 3 = `25 passed`).

- [ ] **Step 2: Confirm `wiki-io` still passes (template addition is inert)**

Run: `uv run --package wiki-io pytest -m "not integration" -q`
Expected: PASS — no regressions (the new template file is picked up by `init_vault`'s `rglob` copy but changes no existing assertion).

- [ ] **Step 3: Lint + format check the new files**

Run: `uv run ruff check packages/guidance-io packages/wiki-io/src/wiki_io/assets/page-templates/guidance.md`
Expected: no errors on the new Python files. (Per repo memory, do not run `ruff format` to "fix" the broader src tree — match surrounding style; the new files were written to 120-col, ruff-clean style.)

- [ ] **Step 4: Final commit if anything changed**

Only if ruff or verification surfaced a fixable nit:

```bash
git add -A
git commit -m "chore(guidance-io): verification fixes"
```

---

## Self-review notes (author checklist — already applied)

- **Spec coverage:** Naming/category/folder (Task 4 `guidance_dir`/`page_path`); frontmatter schema + field rules (Task 3 `validate`); `pyproject.toml` per spec incl. workspace pin and pytest stanza (Task 1); `frontmatter.py` parse/emit verbatim + validate (Tasks 2–3); `paths.py` resolve + slugify + list-by-topic (Task 4); `__init__.py` (Task 1); template with `## Applies to` body mirror (Task 5). Workspace registration is automatic via `members = ["packages/*"]` (noted in Task 1, Step 4) — no root edit, which the spec's "register the member" line is satisfied by. The spec's "add `wiki-io` only if we reuse its frontmatter primitives" is resolved as **do not add** — we copy `work_io`'s primitives, so `guidance-io` depends only on `workspace-io` + `pyyaml`.
- **Deferred items** (importer, search, curator, sidecar, lint) are intentionally **not** in any task — matches the spec's explicit deferral.
- **Type consistency:** `validate` returns `list[str]` everywhere; `slugify`/`page_path`/`guidance_dir`/`list_pages` signatures are identical between `paths.py` and every test call site; `REQUIRED_KEYS`/`IMPACT_VALUES`/`TRIGGER_LIST_KEYS` names are used consistently in the implementation.
- **No placeholders:** every code/test step contains complete, runnable content.
```
