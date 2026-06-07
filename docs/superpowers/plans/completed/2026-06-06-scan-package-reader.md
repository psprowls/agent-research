# Scan Package Reader Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a narrated-scan `package_reader` pass that fills TODO-like human-owned H2 sections on `package`, `app`, `agent_plugin`, and `test_suite` entity pages without rewriting real human prose.

**Architecture:** Add deterministic section-detection and guarded replacement primitives in `wiki_io`, then add a role-specific `graph_wiki_core.commands.package_reader` module that uses the already-extracted `agent_tools` and `agent_loop` helpers. Wire the pass into `run_scan()` after file-map descriptions and before anchor stamping/drift, using the same partial-success and no-Bedrock `narrate=False` boundaries as the existing narrator and file describer passes.

**Tech Stack:** Python 3.11, `uv` workspace, pytest, LangChain `@tool`/messages, `model_adapter.make_llm`, `SubagentPool`, `wiki_io` entity section helpers, `graph_wiki_core.agent_tools`, `graph_wiki_core.agent_loop`.

---

## Background

Read these files before starting:

- `docs/superpowers/specs/2026-06-06-scan-package-reader-design.md` - approved feature spec.
- `docs/superpowers/specs/completed/2026-06-07-agent-tooling-extraction-design.md` - shared helper contract this feature must reuse.
- `packages/graph-wiki-core/src/graph_wiki_core/commands/scan.py` - scan pipeline; package-reader goes after Step 10c and before anchor stamping.
- `packages/graph-wiki-core/src/graph_wiki_core/agent_tools.py` - reuse `read_bounded_wiki_page`, `filter_graph_tools`, `chunk_text`, and `truncate_text`.
- `packages/graph-wiki-core/src/graph_wiki_core/agent_loop.py` - reuse `run_tool_loop`.
- `packages/wiki-io/src/wiki_io/entity_writer.py` and `packages/wiki-io/src/wiki_io/drift.py` - H2 splitting, scanner-owned headings, scanner-data headings, drift hash cleanup.

Important existing behavior:

- `scan.py` imports Bedrock stack at module import behind a guarded `try`. Keep new package-reader imports out of this guarded import unless they are pure local modules.
- `narrate=False` must not call `make_llm`, `load_role_config`, `SubagentPool`, `run_tool_loop`, or package-reader code.
- `last_updated_commit` stamping currently uses `good_prose_uris | redescribed_uris`; add package-reader fills as another stamp reason, still gated by `file_map_todo_paths(page_path) == []`.
- `_drift_flag_pass()` runs after stamping and `_drift_clear_pass()` runs after flagging. Package-reader must run before both so stale `drift_review` hashes naturally clear when sections change.

## File Structure

| File | Change | Responsibility |
|------|--------|----------------|
| `packages/wiki-io/src/wiki_io/human_sections.py` | Create | Pure helpers for TODO-like human H2 detection and stale-safe replacement. |
| `packages/wiki-io/tests/test_human_sections.py` | Create | Unit tests for TODO detection, scanner exclusion, scanner-data exclusion, and replacement guard. |
| `packages/model-adapter/src/model_adapter/models.toml` | Modify | Add `[roles.package_reader]` default config. |
| `packages/model-adapter/tests/test_package_reader_role.py` | Create | Pin role model, token budget, concurrency, and loader behavior. |
| `packages/graph-wiki-core/src/graph_wiki_core/prompts/package_reader.py` | Create | System prompt for JSON section replacements. |
| `packages/graph-wiki-core/src/graph_wiki_core/commands/package_reader.py` | Create | Context dataclasses, repo-bounded tools, JSON parser, and `run_package_reader()`. |
| `packages/graph-wiki-core/tests/unit/test_package_reader.py` | Create | Unit tests for tools, parser, prompt context, shared helper reuse, and loop behavior. |
| `packages/graph-wiki-core/src/graph_wiki_core/commands/scan.py` | Modify | Dispatch package-reader pass and include fills in stamp reasons/errors. |
| `packages/graph-wiki-core/tests/unit/test_commands_scan.py` | Modify | Add no-narrate/import safety and dispatch/error tests. |
| `packages/graph-wiki-core/tests/unit/test_human_section_drift.py` | Modify | Add integration-style stamp/drift-clear coverage using existing fake scan workspace. |

---

## Task 1: Add wiki human-section primitives

**Files:**
- Create: `packages/wiki-io/src/wiki_io/human_sections.py`
- Create: `packages/wiki-io/tests/test_human_sections.py`

- [ ] **Step 1: Write failing tests**

Create `packages/wiki-io/tests/test_human_sections.py`:

```python
from __future__ import annotations

from pathlib import Path

from wiki_io.human_sections import (
    find_todo_human_sections,
    is_todo_like_body,
    replace_todo_human_sections,
)


def _page_text(kind: str = "package") -> str:
    return (
        "---\n"
        "uri: pkg:org/repo/pkg-a\n"
        f"kind: {kind}\n"
        "---\n\n"
        "# pkg-a\n\n"
        "## Purpose\n"
        "> TODO: explain why this package exists.\n\n"
        "## Public API\n"
        "TODO list exported functions.\n\n"
        "## Narrative\n"
        "Scanner prose.\n\n"
        "## File map - pkg-a\n"
        "| Path | Kind | Description |\n"
        "|---|---|---|\n"
        "| `src/pkg_a/__init__.py` | file | - TODO |\n\n"
        "## Referenced in wiki\n"
        "- [[concepts/example]]\n\n"
        "## Real Notes\n"
        "Keep this prose.\n"
    )


def test_is_todo_like_body_accepts_existing_template_shapes() -> None:
    assert is_todo_like_body("")
    assert is_todo_like_body("> TODO: explain why this exists.")
    assert is_todo_like_body("TODO list exported functions.")
    assert is_todo_like_body("- TODO")
    assert is_todo_like_body("— TODO")
    assert not is_todo_like_body("This package owns scan orchestration.")


def test_find_todo_human_sections_excludes_scanner_owned_sections() -> None:
    sections = find_todo_human_sections(_page_text(), entity_kind="package")

    assert [section.heading for section in sections] == ["Purpose", "Public API"]
    assert all(not section.body.startswith("Scanner prose") for section in sections)


def test_find_todo_human_sections_excludes_agent_plugin_scanner_data_sections() -> None:
    text = (
        "---\nuri: agent_plugin:graph-wiki\nkind: agent_plugin\n---\n\n"
        "# graph-wiki\n\n"
        "## Commands\n"
        "> TODO: scanner data table placeholder.\n\n"
        "## How it fits together\n"
        "> TODO: explain the plugin architecture.\n"
    )

    sections = find_todo_human_sections(text, entity_kind="agent_plugin")

    assert [section.heading for section in sections] == ["How it fits together"]


def test_replace_todo_human_sections_replaces_only_requested_todo_bodies(tmp_path: Path) -> None:
    page = tmp_path / "pkg-a.md"
    page.write_text(_page_text(), encoding="utf-8")

    changed = replace_todo_human_sections(
        page,
        {
            "Purpose": "Owns package-level scan orchestration.",
            "Real Notes": "This must not overwrite real prose.",
            "Unknown": "This must be ignored.",
        },
    )

    text = page.read_text(encoding="utf-8")
    assert changed == ["Purpose"]
    assert "## Purpose\nOwns package-level scan orchestration.\n\n" in text
    assert "## Public API\nTODO list exported functions." in text
    assert "## Real Notes\nKeep this prose." in text
    assert "Unknown" not in text


def test_replace_todo_human_sections_rejects_still_placeholder_replacement(tmp_path: Path) -> None:
    page = tmp_path / "pkg-a.md"
    page.write_text(_page_text(), encoding="utf-8")

    changed = replace_todo_human_sections(page, {"Purpose": "TODO later"})

    assert changed == []
    assert "## Purpose\n> TODO: explain why this package exists." in page.read_text(encoding="utf-8")
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run --package wiki-io pytest packages/wiki-io/tests/test_human_sections.py -v`

Expected: FAIL with `ModuleNotFoundError: No module named 'wiki_io.human_sections'`.

- [ ] **Step 3: Implement the helpers**

Create `packages/wiki-io/src/wiki_io/human_sections.py`:

```python
"""Human-owned entity-page section helpers."""

from __future__ import annotations

import os
import re
from dataclasses import dataclass
from pathlib import Path

from wiki_io.entity_writer import (
    SCANNER_DATA_HEADINGS,
    _is_scanner_owned_heading,
    _split_h2_sections,
)

_TODO_MARKER_RE = re.compile(r"^(?:>\s*)?(?:[-*]\s*)?(?:TODO\b|[-\u2014]\s*TODO\b)", re.IGNORECASE)


@dataclass(frozen=True)
class HumanTodoSection:
    heading: str
    full_heading: str
    body: str


def _heading_name(full_heading: str) -> str:
    return full_heading.removeprefix("##").strip()


def is_todo_like_body(body: str) -> bool:
    stripped = body.strip()
    if not stripped:
        return True
    meaningful = [line.strip() for line in stripped.splitlines() if line.strip()]
    return bool(meaningful) and all(_TODO_MARKER_RE.match(line) for line in meaningful)


def _body_from_chunk(chunk: str) -> str:
    _heading, sep, body = chunk.partition("\n")
    return body if sep else ""


def find_todo_human_sections(text: str, *, entity_kind: str) -> list[HumanTodoSection]:
    _preamble, sections = _split_h2_sections(text)
    found: list[HumanTodoSection] = []
    for heading, chunk in sections:
        if _is_scanner_owned_heading(heading):
            continue
        if entity_kind == "agent_plugin" and heading in SCANNER_DATA_HEADINGS:
            continue
        body = _body_from_chunk(chunk)
        if is_todo_like_body(body):
            found.append(HumanTodoSection(heading=_heading_name(heading), full_heading=heading, body=body.strip()))
    return found


def replace_todo_human_sections(page_path: Path, replacements: dict[str, str]) -> list[str]:
    text = page_path.read_text(encoding="utf-8", errors="replace")
    _preamble, sections = _split_h2_sections(text)
    allowed = {section.heading for section in find_todo_human_sections(text, entity_kind=_entity_kind_from_text(text))}
    changed: list[str] = []
    new_chunks: list[str] = []
    cursor = 0

    for heading, chunk in sections:
        start = text.find(chunk, cursor)
        if start < 0:
            continue
        new_chunks.append(text[cursor:start])
        name = _heading_name(heading)
        replacement = replacements.get(name, "").strip()
        if name in allowed and replacement and not is_todo_like_body(replacement):
            new_chunks.append(f"{heading}\n{replacement}\n")
            changed.append(name)
        else:
            new_chunks.append(chunk)
        cursor = start + len(chunk)

    new_chunks.append(text[cursor:])
    if not changed:
        return []

    tmp_path = page_path.with_suffix(page_path.suffix + ".tmp")
    tmp_path.write_text("".join(new_chunks), encoding="utf-8")
    os.replace(tmp_path, page_path)
    return changed


def _entity_kind_from_text(text: str) -> str:
    if not text.startswith("---"):
        return ""
    parts = text.split("---", 2)
    if len(parts) < 3:
        return ""
    for line in parts[1].splitlines():
        key, sep, value = line.partition(":")
        if sep and key.strip() == "kind":
            return value.strip()
    return ""
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run --package wiki-io pytest packages/wiki-io/tests/test_human_sections.py -v`

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add packages/wiki-io/src/wiki_io/human_sections.py packages/wiki-io/tests/test_human_sections.py
git commit -m "feat(wiki-io): add human TODO section helpers"
```

---

## Task 2: Add the `package_reader` model role

**Files:**
- Modify: `packages/model-adapter/src/model_adapter/models.toml`
- Create: `packages/model-adapter/tests/test_package_reader_role.py`

- [ ] **Step 1: Write the failing test**

Create `packages/model-adapter/tests/test_package_reader_role.py`:

```python
from __future__ import annotations


def test_package_reader_role_in_models_toml() -> None:
    from model_adapter.loader import load_role_config

    cfg = load_role_config("package_reader")

    assert cfg["model_id"] == "moonshotai.kimi-k2.5"
    assert cfg["region"] == "us-east-1"
    assert cfg["max_tokens"] >= 4096
    assert cfg["max_concurrency"] == 3
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run --package model-adapter pytest packages/model-adapter/tests/test_package_reader_role.py -v`

Expected: FAIL with `KeyError` for `package_reader`.

- [ ] **Step 3: Add role config**

Add this block to `packages/model-adapter/src/model_adapter/models.toml` after `[roles.proposal_reasoner]`:

```toml
[roles.package_reader]
# Narrated scan pass that initializes TODO-like human-owned entity-page sections.
# Separate from code_reader because it writes multi-section markdown and uses a
# page-initialization JSON contract rather than one-line file-map descriptions.
model_id        = "moonshotai.kimi-k2.5"
region          = "us-east-1"
max_tokens      = 4096
max_concurrency = 3
sweep_candidates = [
  "moonshotai.kimi-k2.5",
]
```

- [ ] **Step 4: Run tests**

Run: `uv run --package model-adapter pytest packages/model-adapter/tests/test_package_reader_role.py packages/model-adapter/tests/test_loader.py -v`

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add packages/model-adapter/src/model_adapter/models.toml packages/model-adapter/tests/test_package_reader_role.py
git commit -m "feat(model-adapter): add package_reader role"
```

---

## Task 3: Add package-reader prompt, parser, and bounded tools

**Files:**
- Create: `packages/graph-wiki-core/src/graph_wiki_core/prompts/package_reader.py`
- Create: `packages/graph-wiki-core/src/graph_wiki_core/commands/package_reader.py`
- Create: `packages/graph-wiki-core/tests/unit/test_package_reader.py`

- [ ] **Step 1: Write failing tests**

Create `packages/graph-wiki-core/tests/unit/test_package_reader.py`:

```python
from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

import pytest
from langchain_core.messages import HumanMessage
from langchain_core.tools import tool

from graph_wiki_core.commands.package_reader import (
    PackageReaderItem,
    build_package_reader_tools,
    parse_package_reader_output,
    run_package_reader,
)


def test_parse_package_reader_output_filters_invalid_entries() -> None:
    raw = json.dumps(
        {
            "sections": [
                {"heading": "Purpose", "replacement_markdown": "Owns scan orchestration."},
                {"heading": "Public API", "replacement_markdown": "TODO later"},
                {"heading": "Unknown", "replacement_markdown": "Must be ignored."},
                {"heading": "Purpose", "replacement_markdown": ""},
            ]
        }
    )

    parsed = parse_package_reader_output(raw, requested_headings=["Purpose", "Public API"])

    assert parsed == {"Purpose": "Owns scan orchestration."}


def test_parse_package_reader_output_accepts_fenced_json() -> None:
    raw = '```json\n{"sections":[{"heading":"Purpose","replacement_markdown":"Does real work."}]}\n```'

    parsed = parse_package_reader_output(raw, requested_headings=["Purpose"])

    assert parsed == {"Purpose": "Does real work."}


def test_build_package_reader_tools_rejects_reads_outside_entity_root(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    root = repo / "packages" / "pkg-a"
    root.mkdir(parents=True)
    (root / "pyproject.toml").write_text("[project]\nname = 'pkg-a'\n", encoding="utf-8")
    (repo / "secret.txt").write_text("secret", encoding="utf-8")
    wiki = tmp_path / "wiki"
    wiki.mkdir()

    tools = {agent_tool.name: agent_tool for agent_tool in build_package_reader_tools(repo=repo, entity_root="packages/pkg-a", wiki=wiki, graph_tools=[])}

    assert "name = 'pkg-a'" in tools["read_repo_file"].invoke({"path": "pyproject.toml"})
    assert tools["read_repo_file"].invoke({"path": "../secret.txt"}).startswith("ERROR: path is outside entity root")
    assert tools["list_repo_tree"].invoke({"path": "."}).startswith("pyproject.toml")


def test_build_package_reader_tools_includes_bounded_wiki_and_allowed_graph_tools(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    (repo / "packages" / "pkg-a").mkdir(parents=True)
    wiki = tmp_path / "wiki"
    (wiki / "entities").mkdir(parents=True)
    (wiki / "entities" / "pkg-a.md").write_text("---\ntitle: pkg-a\n---\n\nBody", encoding="utf-8")

    @tool
    def cg_find(name: str) -> str:
        """Find a graph node."""
        return f"find:{name}"

    @tool
    def cg_callers(name: str) -> str:
        """Not allowed for package-reader."""
        return name

    tools = build_package_reader_tools(repo=repo, entity_root="packages/pkg-a", wiki=wiki, graph_tools=[cg_find, cg_callers])
    names = [agent_tool.name for agent_tool in tools]

    assert names == ["read_repo_file", "list_repo_tree", "read_wiki_page", "cg_find"]


@pytest.mark.asyncio
async def test_run_package_reader_uses_shared_tool_loop(monkeypatch, tmp_path: Path) -> None:
    item = PackageReaderItem(
        uri="pkg:org/repo/pkg-a",
        kind="package",
        name="pkg-a",
        graph_path="packages/pkg-a",
        language="python",
        frontmatter={"uri": "pkg:org/repo/pkg-a", "kind": "package"},
        page_content="# pkg-a\n\n## Purpose\n> TODO: explain.\n",
        requested_sections={"Purpose": "> TODO: explain."},
        narrative="Scanner prose.",
        file_map="## File map - pkg-a\n...",
        graph_context="package pkg-a",
        entity_root="packages/pkg-a",
    )
    fake_llm = MagicMock()

    async def fake_loop(**kwargs):
        assert kwargs["llm"] is fake_llm
        assert kwargs["max_iterations"] == 5
        assert kwargs["cap_label"] == "package_reader"
        return MagicMock(status="ok", final_text='{"sections":[{"heading":"Purpose","replacement_markdown":"Owns scan."}]}', error=None)

    monkeypatch.setattr("graph_wiki_core.commands.package_reader.run_tool_loop", fake_loop)

    result = await run_package_reader(llm=fake_llm, item=item, repo=tmp_path / "repo", wiki=tmp_path / "wiki", graph_tools=[])

    assert result.replacements == {"Purpose": "Owns scan."}
    assert result.error is None
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run --package graph-wiki-core pytest packages/graph-wiki-core/tests/unit/test_package_reader.py -v`

Expected: FAIL with `ModuleNotFoundError` for `graph_wiki_core.commands.package_reader`.

- [ ] **Step 3: Add the prompt**

Create `packages/graph-wiki-core/src/graph_wiki_core/prompts/package_reader.py`:

```python
"""Prompt for package-reader scan pass."""

PACKAGE_READER_SYSTEM = """You initialize TODO-like human-owned sections on one Graph Wiki entity page.

You receive the current entity page, exact requested H2 headings, scanner-owned context,
and bounded source/wiki/graph tools. Write only replacement markdown for requested
section bodies.

Rules:
- Return exactly one JSON object with a top-level "sections" array.
- Each section item has "heading" and "replacement_markdown".
- heading must match one requested H2 heading without the leading ##.
- replacement_markdown is body markdown only; do not include the H2 heading.
- Omit a section when source context does not justify a useful replacement.
- Do not rewrite page frontmatter, scanner-owned sections, or whole pages.
- Do not return TODO placeholder text.
- Cite concrete code paths with backticked path:line references when useful.
"""
```

- [ ] **Step 4: Implement package-reader module**

Create `packages/graph-wiki-core/src/graph_wiki_core/commands/package_reader.py`:

```python
"""Package-reader scan pass helpers."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from langchain_core.messages import HumanMessage, SystemMessage
from langchain_core.tools import BaseTool, tool

from graph_wiki_core.agent_loop import run_tool_loop
from graph_wiki_core.agent_tools import filter_graph_tools, read_bounded_wiki_page, truncate_text
from graph_wiki_core.prompts.package_reader import PACKAGE_READER_SYSTEM
from wiki_io.human_sections import is_todo_like_body

MAX_PACKAGE_READER_ITERS = 5
MAX_REPO_FILE_CHARS = 40_000
MAX_WIKI_PAGE_CHARS = 40_000
MAX_TREE_ENTRIES = 200
_ALLOWED_GRAPH_TOOL_NAMES = {"cg_find", "cg_describe"}


@dataclass(frozen=True)
class PackageReaderItem:
    uri: str
    kind: str
    name: str
    graph_path: str
    language: str
    frontmatter: dict[str, Any]
    page_content: str
    requested_sections: dict[str, str]
    narrative: str | None
    file_map: str | None
    graph_context: str | None
    entity_root: str


@dataclass(frozen=True)
class PackageReaderResult:
    replacements: dict[str, str]
    error: str | None = None


def _clean_json_text(raw: str) -> str:
    text = raw.strip()
    if text.startswith("```"):
        lines = text.splitlines()
        if lines and lines[0].startswith("```"):
            lines = lines[1:]
        if lines and lines[-1].strip() == "```":
            lines = lines[:-1]
        text = "\n".join(lines).strip()
    return text


def parse_package_reader_output(raw: str, *, requested_headings: list[str]) -> dict[str, str]:
    try:
        payload = json.loads(_clean_json_text(raw))
    except json.JSONDecodeError:
        return {}
    requested = set(requested_headings)
    sections = payload.get("sections") if isinstance(payload, dict) else None
    if not isinstance(sections, list):
        return {}
    parsed: dict[str, str] = {}
    for entry in sections:
        if not isinstance(entry, dict):
            continue
        heading = entry.get("heading")
        body = entry.get("replacement_markdown")
        if not isinstance(heading, str) or heading not in requested:
            continue
        if not isinstance(body, str):
            continue
        stripped = body.strip()
        if not stripped or is_todo_like_body(stripped):
            continue
        parsed.setdefault(heading, stripped)
    return parsed


def _resolve_under(base: Path, rel_path: str) -> Path | None:
    try:
        root = base.resolve()
        target = (root / rel_path).resolve()
        target.relative_to(root)
    except (OSError, ValueError):
        return None
    return target


def build_package_reader_tools(*, repo: Path, entity_root: str, wiki: Path, graph_tools: list[BaseTool]) -> list[BaseTool]:
    entity_root_path = _resolve_under(repo, entity_root)

    @tool
    def read_repo_file(path: str) -> str:
        """Read a repo-relative file under the current entity root."""
        if entity_root_path is None:
            return "ERROR: entity root is outside repo"
        target = _resolve_under(entity_root_path, path)
        if target is None:
            return "ERROR: path is outside entity root"
        if not target.is_file():
            return f"ERROR: repo file not found: {path}"
        try:
            return truncate_text(target.read_text(encoding="utf-8", errors="replace"), MAX_REPO_FILE_CHARS)
        except OSError as exc:
            return f"ERROR: {exc}"

    @tool
    def list_repo_tree(path: str = ".") -> str:
        """List a shallow repo tree under the current entity root."""
        if entity_root_path is None:
            return "ERROR: entity root is outside repo"
        target = _resolve_under(entity_root_path, path)
        if target is None:
            return "ERROR: path is outside entity root"
        if not target.is_dir():
            return f"ERROR: repo directory not found: {path}"
        rows: list[str] = []
        try:
            for child in sorted(target.iterdir(), key=lambda p: p.name)[:MAX_TREE_ENTRIES]:
                suffix = "/" if child.is_dir() else ""
                rows.append(f"{child.relative_to(entity_root_path).as_posix()}{suffix}")
        except OSError as exc:
            return f"ERROR: {exc}"
        if not rows:
            return "(empty)"
        return "\n".join(rows)

    @tool
    def read_wiki_page(path: str) -> str:
        """Read one markdown wiki page under the wiki root, bounded to a safe size."""
        return read_bounded_wiki_page(wiki, path, max_chars=MAX_WIKI_PAGE_CHARS)

    return [
        read_repo_file,
        list_repo_tree,
        read_wiki_page,
        *filter_graph_tools(graph_tools, _ALLOWED_GRAPH_TOOL_NAMES),
    ]


def build_package_reader_prompt(item: PackageReaderItem) -> str:
    requested = "\n".join(f"- {heading}: {body}" for heading, body in item.requested_sections.items())
    return (
        f"Entity URI: {item.uri}\n"
        f"Kind: {item.kind}\n"
        f"Name: {item.name}\n"
        f"Graph path: {item.graph_path}\n"
        f"Language: {item.language}\n"
        f"Entity root for repo tools: {item.entity_root}\n\n"
        f"Requested H2 sections:\n{requested}\n\n"
        f"Narrative:\n{item.narrative or '(none)'}\n\n"
        f"File map:\n{item.file_map or '(none)'}\n\n"
        f"Graph context:\n{item.graph_context or '(graph tools unavailable or no context)'}\n\n"
        f"Current page content:\n{truncate_text(item.page_content, 80_000)}\n\n"
        "Return the JSON object now."
    )


async def run_package_reader(
    *,
    llm: Any,
    item: PackageReaderItem,
    repo: Path,
    wiki: Path,
    graph_tools: list[BaseTool],
) -> PackageReaderResult:
    tools = build_package_reader_tools(repo=repo, entity_root=item.entity_root, wiki=wiki, graph_tools=graph_tools)
    loop_result = await run_tool_loop(
        llm=llm,
        tools=tools,
        messages=[
            SystemMessage(content=PACKAGE_READER_SYSTEM),
            HumanMessage(content=build_package_reader_prompt(item)),
        ],
        max_iterations=MAX_PACKAGE_READER_ITERS,
        cap_label="package_reader",
    )
    if loop_result.status != "ok":
        return PackageReaderResult(replacements={}, error=loop_result.error or "package_reader failed")
    replacements = parse_package_reader_output(
        loop_result.final_text,
        requested_headings=list(item.requested_sections),
    )
    return PackageReaderResult(replacements=replacements, error=loop_result.error)
```

- [ ] **Step 5: Run tests**

Run: `uv run --package graph-wiki-core pytest packages/graph-wiki-core/tests/unit/test_package_reader.py -v`

Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add packages/graph-wiki-core/src/graph_wiki_core/prompts/package_reader.py packages/graph-wiki-core/src/graph_wiki_core/commands/package_reader.py packages/graph-wiki-core/tests/unit/test_package_reader.py
git commit -m "feat(graph-wiki-core): add package reader role module"
```

---

## Task 4: Wire package-reader into narrated scan

**Files:**
- Modify: `packages/graph-wiki-core/src/graph_wiki_core/commands/scan.py`
- Modify: `packages/graph-wiki-core/tests/unit/test_commands_scan.py`

- [ ] **Step 1: Add failing no-narrate safety test**

Append this test to `packages/graph-wiki-core/tests/unit/test_commands_scan.py`:

```python
def test_run_scan_no_narrate_does_not_call_package_reader(monkeypatch, tmp_path: Path) -> None:
    import asyncio
    import graph_wiki_core.commands.scan as scan_mod
    from graph_io import exit_codes
    from graph_io.store import GraphNotInitializedError

    workspace = tmp_path / "workspace"
    wiki = workspace / "wiki"
    repo = workspace / "repo"
    wiki.mkdir(parents=True)
    repo.mkdir()
    (wiki / "log.md").write_text("", encoding="utf-8")
    monkeypatch.setenv("GRAPH_WIKI_WORKSPACE", str(workspace))
    monkeypatch.setattr(scan_mod, "_cg_run_build", lambda repo, ws, *, full: (exit_codes.SUCCESS, "", ""))
    monkeypatch.setattr(scan_mod, "read_only_connect", lambda path: (_ for _ in ()).throw(GraphNotInitializedError("no db")))
    monkeypatch.setattr(scan_mod, "compute_state_gate", lambda repo, **kwargs: {"allowed": True, "reason": "clean", "head_commit": "abc"})
    monkeypatch.setattr(scan_mod, "update_index", lambda wiki: None)
    monkeypatch.setattr(scan_mod, "generate_index", lambda wiki, conn: None)
    monkeypatch.setattr(scan_mod, "regenerate_referenced_in_wiki", lambda wiki: None)
    monkeypatch.setattr(scan_mod, "append_log", lambda *args, **kwargs: None)
    assert hasattr(scan_mod, "_run_package_reader_pass")

    def explode_package_reader(*args, **kwargs):
        raise AssertionError("package_reader must not run when narrate=False")

    monkeypatch.setattr(scan_mod, "_run_package_reader_pass", explode_package_reader)

    asyncio.run(scan_mod.run_scan(workspace_path=workspace, repo_path=repo, narrate=False))
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run --package graph-wiki-core pytest packages/graph-wiki-core/tests/unit/test_commands_scan.py::test_run_scan_no_narrate_does_not_call_package_reader -v`

Expected: FAIL because `_run_package_reader_pass` does not exist yet.

- [ ] **Step 3: Modify imports and add helper constants**

In `packages/graph-wiki-core/src/graph_wiki_core/commands/scan.py`, add imports:

```python
from graph_wiki_core.commands.package_reader import PackageReaderItem, run_package_reader
from graph_wiki_core.graph_tools import build_graph_tools
from wiki_io.human_sections import find_todo_human_sections, replace_todo_human_sections
```

Add near module constants:

```python
PACKAGE_READER_TARGET_KINDS = frozenset({"package", "app", "agent_plugin", "test_suite"})
```

- [ ] **Step 4: Add package-reader pass helper**

Add this helper above `run_scan()`:

```python
async def _run_package_reader_pass(
    *,
    wiki: Path,
    repo: Path,
    conn: Any | None,
    model_override: str | None,
    candidate_pages: dict[str, Path],
) -> tuple[set[str], list[str]]:
    stack = _bedrock_stack()
    if stack is None:
        return set(), []
    load_role_config_fn, make_llm_fn, subagent_pool_type, task_result_type = stack

    graph_tools = build_graph_tools(conn) if conn is not None else []
    items: list[tuple[str, Path, PackageReaderItem]] = []
    for uri, page_path in sorted(candidate_pages.items()):
        try:
            post = frontmatter.load(page_path)
        except Exception as exc:  # noqa: BLE001
            return set(), [f"{uri}: package_reader page load failed: {exc!r}"]
        kind = str(post.metadata.get("kind") or "")
        if kind not in PACKAGE_READER_TARGET_KINDS:
            continue
        page_text = page_path.read_text(encoding="utf-8", errors="replace")
        todo_sections = find_todo_human_sections(page_text, entity_kind=kind)
        if not todo_sections:
            continue
        graph_path = str(post.metadata.get("graph_path") or post.metadata.get("path") or "")
        if not graph_path:
            graph_path = _entity_root_from_frontmatter(post.metadata)
        item = PackageReaderItem(
            uri=uri,
            kind=kind,
            name=str(post.metadata.get("graph_name") or post.metadata.get("title") or page_path.stem),
            graph_path=graph_path,
            language=str(post.metadata.get("language") or "unknown"),
            frontmatter=dict(post.metadata),
            page_content=page_text,
            requested_sections={section.heading: section.body for section in todo_sections},
            narrative=extract_narrative(page_text),
            file_map=extract_file_map(page_text),
            graph_context=None,
            entity_root=graph_path,
        )
        items.append((uri, page_path, item))

    if not items:
        return set(), []

    cfg = load_role_config_fn("package_reader")
    llm = make_llm_fn("package_reader", model_override=model_override)
    pool = subagent_pool_type(trace_dir=graph_dir(wiki.parent) / "traces")

    async def fill_sections(item_tuple: tuple[str, Path, PackageReaderItem]) -> Any:
        _uri, _page_path, reader_item = item_tuple
        result = await run_package_reader(llm=llm, item=reader_item, repo=repo, wiki=wiki, graph_tools=graph_tools)
        return task_result_type(value=result, response=result)

    fanout = await pool.run_all(
        items=items,
        task=fill_sections,
        role="package_reader",
        model_id=cfg["model_id"],
        max_concurrency=cfg["max_concurrency"],
    )
    filled: set[str] = set()
    errors: list[str] = []
    for item_tuple, result in fanout.successes:
        uri, page_path, _reader_item = item_tuple
        if result.error:
            errors.append(f"{uri}: {result.error}")
        if not result.replacements:
            continue
        try:
            changed = replace_todo_human_sections(page_path, result.replacements)
        except Exception as exc:  # noqa: BLE001
            errors.append(f"{uri}: replace_todo_human_sections failed: {exc!r}")
            continue
        if changed:
            filled.add(uri)
    for err in fanout.errors:
        uri = err.item[0]
        errors.append(f"{uri}: {err.exception!r}")
    return filled, errors


def _entity_root_from_frontmatter(metadata: dict[str, Any]) -> str:
    uri = str(metadata.get("uri") or "")
    if ":" not in uri:
        return ""
    return uri.split(":", 1)[1]
```

- [ ] **Step 5: Call helper from `run_scan()`**

Immediately after Step 10c and before the anchor stamping block, add:

```python
        package_reader_filled_uris: set[str] = set()
        package_reader_errors: list[str] = []
        if narrate:
            package_reader_candidates: dict[str, Path] = {}
            package_reader_candidates.update(narrated_page_paths)
            for uri_inner, _node, page_path in file_mapped_pages:
                package_reader_candidates.setdefault(uri_inner, page_path)
            if package_reader_candidates:
                package_reader_filled_uris, package_reader_errors = await _run_package_reader_pass(
                    wiki=wiki,
                    repo=repo,
                    conn=conn,
                    model_override=model_override,
                    candidate_pages=package_reader_candidates,
                )
                if package_reader_filled_uris or package_reader_errors:
                    append_log(
                        wiki,
                        "scan",
                        (
                            f"package-reader sections filled: {len(package_reader_filled_uris)} "
                            f"entity(s) (errors: {len(package_reader_errors)})"
                        ),
                        detail=None,
                        silent=True,
                        raise_exception=True,
                    )
```

Then update stamping:

```python
            for uri_inner in good_prose_uris | redescribed_uris | package_reader_filled_uris:
```

Then update the returned errors:

```python
            entity_errors=(
                entity_write_errors
                + narrator_errors
                + file_map_errors
                + describer_errors
                + package_reader_errors
            ),
```

- [ ] **Step 6: Run no-narrate test**

Run: `uv run --package graph-wiki-core pytest packages/graph-wiki-core/tests/unit/test_commands_scan.py::test_run_scan_no_narrate_does_not_call_package_reader -v`

Expected: PASS.

- [ ] **Step 7: Commit**

```bash
git add packages/graph-wiki-core/src/graph_wiki_core/commands/scan.py packages/graph-wiki-core/tests/unit/test_commands_scan.py
git commit -m "feat(scan): run package reader in narrated scans"
```

---

## Task 5: Add scan integration tests for fill, skip, errors, and stamping

**Files:**
- Modify: `packages/graph-wiki-core/tests/unit/test_human_section_drift.py`
- Modify: `packages/graph-wiki-core/tests/unit/test_commands_scan.py`

- [ ] **Step 1: Add integration-style package-reader fill test**

Append to `packages/graph-wiki-core/tests/unit/test_human_section_drift.py`:

```python
def test_package_reader_fill_stamps_and_skips_on_rescan(ws, monkeypatch):
    import asyncio

    wiki = ws / "wiki"
    repo = ws / "repo"
    heads = {"v": "head1"}
    calls = {"package_reader": 0}
    monkeypatch.setattr(
        scan_mod,
        "compute_state_gate",
        lambda repo, **kwargs: {"allowed": True, "reason": "clean", "head_commit": heads["v"]},
    )

    async def fake_package_reader_pass(**kwargs):
        calls["package_reader"] += 1
        page = _page_for(wiki)
        from wiki_io.human_sections import replace_todo_human_sections

        changed = replace_todo_human_sections(page, {"Purpose": "Owns package-level scan orchestration."})
        return ({_PKG_A} if changed else set(), [])

    monkeypatch.setattr(scan_mod, "_run_package_reader_pass", fake_package_reader_pass)
    monkeypatch.setattr(scan_mod.SubagentPool, "run_all", _spy(lambda it: {"stale": False, "reason": ""}))

    asyncio.run(scan_mod.run_scan(workspace_path=ws, repo_path=repo, narrate=True))
    page = _page_for(wiki)
    text = page.read_text(encoding="utf-8")
    meta = _fm.load(page).metadata

    assert "## Purpose\nOwns package-level scan orchestration." in text
    assert meta["last_updated_commit"] == "head1"
    assert calls["package_reader"] == 1

    asyncio.run(scan_mod.run_scan(workspace_path=ws, repo_path=repo, narrate=True))

    assert calls["package_reader"] == 2
    assert "## Purpose\nOwns package-level scan orchestration." in _page_for(wiki).read_text(encoding="utf-8")
```

- [ ] **Step 2: Add package-reader error propagation test**

Append to `packages/graph-wiki-core/tests/unit/test_commands_scan.py`:

```python
def test_package_reader_errors_join_scan_result(monkeypatch, tmp_path: Path) -> None:
    import asyncio
    import sqlite3
    import graph_wiki_core.commands.scan as scan_mod
    from graph_io import exit_codes, schema
    from workspace_io.paths import graph_dir

    workspace = tmp_path / "workspace"
    wiki = workspace / "wiki"
    repo = workspace / "repo"
    wiki.mkdir(parents=True)
    repo.mkdir()
    (wiki / "log.md").write_text("", encoding="utf-8")
    monkeypatch.setenv("GRAPH_WIKI_WORKSPACE", str(workspace))
    graph_path = graph_dir(workspace) / "code.db"
    graph_path.parent.mkdir(parents=True)
    conn = sqlite3.connect(graph_path)
    schema.apply_schema(conn)
    conn.execute(
        "INSERT INTO nodes(kind, name, path, line, attrs_json, uri) VALUES "
        "('package', 'pkg-a', 'packages/pkg-a', NULL, '{\"language\":\"python\"}', 'pkg:org/repo/pkg-a')"
    )
    conn.commit()
    conn.close()
    monkeypatch.setattr(scan_mod, "_cg_run_build", lambda repo, ws, *, full: (exit_codes.SUCCESS, "", ""))
    monkeypatch.setattr(scan_mod, "compute_state_gate", lambda repo, **kwargs: {"allowed": True, "reason": "clean", "head_commit": "abc"})
    monkeypatch.setattr(scan_mod, "build_file_map", lambda *args, **kwargs: None)
    monkeypatch.setattr(scan_mod.SubagentPool, "run_all", _spy(lambda it: {"stale": False, "reason": ""}))

    async def fake_package_reader_pass(**kwargs):
        return set(), ["pkg:org/repo/pkg-a: invalid JSON"]

    monkeypatch.setattr(scan_mod, "_run_package_reader_pass", fake_package_reader_pass)

    result = asyncio.run(scan_mod.run_scan(workspace_path=workspace, repo_path=repo, narrate=True))

    assert "pkg:org/repo/pkg-a: invalid JSON" in result.entity_errors
```

- [ ] **Step 3: Run tests**

Run:

```bash
uv run --package graph-wiki-core pytest \
  packages/graph-wiki-core/tests/unit/test_human_section_drift.py::test_package_reader_fill_stamps_and_skips_on_rescan \
  packages/graph-wiki-core/tests/unit/test_commands_scan.py::test_package_reader_errors_join_scan_result \
  -v
```

Expected: PASS.

- [ ] **Step 4: Run broader scan tests**

Run:

```bash
uv run --package graph-wiki-core pytest \
  packages/graph-wiki-core/tests/unit/test_commands_scan.py \
  packages/graph-wiki-core/tests/unit/test_human_section_drift.py \
  -v
```

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add packages/graph-wiki-core/tests/unit/test_human_section_drift.py packages/graph-wiki-core/tests/unit/test_commands_scan.py
git commit -m "test(scan): cover package reader scan behavior"
```

---

## Task 6: Final verification and cleanup

**Files:**
- No new files.

- [ ] **Step 1: Run scoped verification from the spec**

Run:

```bash
uv run --package graph-wiki-core pytest packages/graph-wiki-core/tests/unit/test_agent_tools.py packages/graph-wiki-core/tests/unit/test_agent_loop.py
uv run --package model-adapter pytest packages/model-adapter/tests/test_loader.py packages/model-adapter/tests/test_package_reader_role.py
uv run --package wiki-io pytest packages/wiki-io/tests/test_human_sections.py
uv run --package graph-wiki-core pytest packages/graph-wiki-core/tests/unit/test_package_reader.py packages/graph-wiki-core/tests/unit/test_commands_scan.py
```

Expected: all commands PASS.

- [ ] **Step 2: Run scoped Ruff**

Run:

```bash
uv run ruff check \
  packages/wiki-io/src/wiki_io/human_sections.py \
  packages/wiki-io/tests/test_human_sections.py \
  packages/model-adapter/tests/test_package_reader_role.py \
  packages/graph-wiki-core/src/graph_wiki_core/prompts/package_reader.py \
  packages/graph-wiki-core/src/graph_wiki_core/commands/package_reader.py \
  packages/graph-wiki-core/tests/unit/test_package_reader.py \
  packages/graph-wiki-core/src/graph_wiki_core/commands/scan.py \
  packages/graph-wiki-core/tests/unit/test_commands_scan.py \
  packages/graph-wiki-core/tests/unit/test_human_section_drift.py
```

Expected: PASS.

- [ ] **Step 3: Review no-Bedrock boundary**

Run:

```bash
uv run --package graph-wiki-core pytest packages/graph-wiki-core/tests/unit/test_commands_scan.py::test_run_scan_no_narrate_does_not_call_package_reader -v
```

Expected: PASS, confirming `narrate=False` does not enter the package-reader path.

- [ ] **Step 4: Final commit**

If Step 1 or Step 2 required fixes, commit them:

```bash
git add packages/wiki-io packages/model-adapter packages/graph-wiki-core
git commit -m "fix: address package reader verification issues"
```

Skip this commit when there are no verification fixes.

---

## Self-Review

Spec coverage:

- Target kinds `package`, `app`, `agent_plugin`, `test_suite`: Task 4 uses `PACKAGE_READER_TARGET_KINDS`.
- Placeholder-only behavior: Task 1 guards replacement with `is_todo_like_body()` on the re-read page.
- Scanner-owned and scanner-data exclusions: Task 1 tests and helper exclude both.
- Shared agent helpers: Task 3 uses `read_bounded_wiki_page`, `filter_graph_tools`, `truncate_text`, and `run_tool_loop`.
- Repo-bounded tools: Task 3 implements `read_repo_file` and `list_repo_tree` under `entity_root`.
- JSON contract: Task 3 parser accepts only requested headings and non-placeholder bodies.
- Stamping and drift ordering: Task 4 runs before stamping/drift and adds fills to stamp reasons.
- Best-effort errors: Task 4 returns package-reader errors into `ScanResult.entity_errors`.
- `narrate=False` Bedrock-free path: Task 4 and Task 6 verify the path.

Placeholder scan:

- No implementation step uses unspecified placeholders. Mentions of TODO refer to the feature's real TODO-like page content.

Type consistency:

- `PackageReaderItem`, `PackageReaderResult`, `find_todo_human_sections`, `replace_todo_human_sections`, and `_run_package_reader_pass` names are consistent across tasks.
