# Agent Tooling Extraction Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Extract proposal-reasoner safe wiki tools, catalog helpers, chunking, graph-tool filtering, and capped LangChain tool-loop mechanics into reusable `graph_wiki_core` modules without changing ingest behavior.

**Architecture:** Add `graph_wiki_core.agent_tools` for deterministic bounded context/tool helpers and `graph_wiki_core.agent_loop` for the generic capped `ainvoke` plus tool-dispatch loop. Keep `commands/proposal_reasoner.py` as the proposal-specific boundary: it owns prompts, role selection, source-page semantics, allowed graph tool names, and conversion from generic loop results to `ProposalReasonerResult`.

**Tech Stack:** Python 3.11, uv workspace packages, pytest with `asyncio_mode=auto`, LangChain Core messages/tools, Bedrock access only through `model_adapter.make_llm(role)`.

---

## File Structure

- Create `packages/graph-wiki-core/src/graph_wiki_core/agent_tools.py`: shared `SourceChunks`, bounded wiki-page read, wiki catalog construction/search, deterministic text chunking, and graph-tool filtering.
- Create `packages/graph-wiki-core/src/graph_wiki_core/agent_loop.py`: shared `ToolLoopResult`, tool-call parsing, role LLM binding, async capped tool-call loop, unknown-tool handling, tool-exception-to-string behavior, and iteration-cap status mapping.
- Modify `packages/graph-wiki-core/src/graph_wiki_core/commands/proposal_reasoner.py`: remove duplicated helper implementations, import from `agent_tools` and `agent_loop`, keep proposal constants/prompt/result shape, and delegate the loop to `run_tool_loop()`.
- Create `packages/graph-wiki-core/tests/unit/test_agent_tools.py`: direct unit coverage for catalog, bounded reads, search, chunking, and graph-tool filtering.
- Create `packages/graph-wiki-core/tests/unit/test_agent_loop.py`: direct async unit coverage for terminal responses, one tool call, unknown tools, tool exceptions, and iteration-cap behavior.
- Modify `packages/graph-wiki-core/tests/unit/test_proposal_reasoner.py`: move shared-helper tests out to the new test files, keep proposal prompt/tool composition and `run_proposal_reasoner()` behavior coverage.

---

### Task 1: Add Shared Agent Tool Tests

**Files:**
- Create: `packages/graph-wiki-core/tests/unit/test_agent_tools.py`
- Test: `packages/graph-wiki-core/tests/unit/test_agent_tools.py`

- [ ] **Step 1: Write the failing shared helper tests**

Create `packages/graph-wiki-core/tests/unit/test_agent_tools.py`:

```python
from __future__ import annotations

from pathlib import Path

from langchain_core.tools import tool


def _page(path: Path, title: str | None = None, kind: str | None = None, **frontmatter: str) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    metadata: dict[str, str] = {}
    if title is not None:
        metadata["title"] = title
    if kind is not None:
        metadata["kind"] = kind
    metadata.update(frontmatter)
    yaml_lines = [f"{key}: {value}" for key, value in metadata.items()]
    path.write_text("---\n" + "\n".join(yaml_lines) + "\n---\n\nBody text for " + path.stem, encoding="utf-8")
    return path


def test_build_wiki_catalog_lists_curated_sources_entities_and_proposals(tmp_path: Path) -> None:
    from graph_wiki_core.agent_tools import build_wiki_catalog
    from wiki_io.proposals import upsert_proposal

    wiki = tmp_path / "wiki"
    _page(wiki / "concepts" / "ownership.md", title="Ownership", summary="Owns sections")
    _page(wiki / "adrs" / "0007-md.md", title="ADR-0007: Markdown", summary="Markdown stays canonical")
    _page(wiki / "architecture" / "layers.md", title="Layers", summary="Bottom to top")
    _page(wiki / "sources" / "spec.md", title="Spec", summary="Imported source")
    _page(
        wiki / "entities" / "packages" / "graph-wiki-core.md",
        title="graph-wiki-core",
        summary="Core package",
        uri="pkg:graph-wiki-core",
        kind="package",
    )
    upsert_proposal(
        wiki,
        {
            "kind": "concept",
            "mode": "create_new",
            "target_slug": "fanout",
            "title": "Fanout",
            "origin": {"ref": "sources/spec", "source": "ingest", "rationale": "Source justifies it."},
        },
    )

    catalog = build_wiki_catalog(wiki)

    assert {entry["slug"] for entry in catalog["concepts"]} == {"ownership"}
    assert {entry["slug"] for entry in catalog["adrs"]} == {"0007-md"}
    assert {entry["slug"] for entry in catalog["architecture"]} == {"layers"}
    assert {entry["slug"] for entry in catalog["sources"]} == {"spec"}
    assert [entry["uri"] for entry in catalog["entities"]] == ["pkg:graph-wiki-core"]
    assert catalog["entities"][0]["entity_kind"] == "package"
    assert [entry["target_slug"] for entry in catalog["proposals"]] == ["fanout"]


def test_read_bounded_wiki_page_includes_title_body_and_truncates(tmp_path: Path) -> None:
    from graph_wiki_core.agent_tools import read_bounded_wiki_page

    wiki = tmp_path / "wiki"
    page = wiki / "concepts" / "ownership.md"
    page.parent.mkdir(parents=True, exist_ok=True)
    page.write_text("---\ntitle: Ownership\nkind: concept\n---\n\n" + ("x" * 120) + "marker", encoding="utf-8")

    out = read_bounded_wiki_page(wiki, "concepts/ownership.md", max_chars=40)
    bounded_content = out.split("\n\n[TRUNCATED after", 1)[0]

    assert out.startswith("# Ownership\n\n")
    assert len(bounded_content) == 40
    assert "[TRUNCATED after 40 chars]" in out
    assert "marker" not in out


def test_read_bounded_wiki_page_rejects_unsafe_missing_and_non_markdown_paths(tmp_path: Path) -> None:
    from graph_wiki_core.agent_tools import read_bounded_wiki_page

    wiki = tmp_path / "wiki"
    wiki.mkdir()
    (tmp_path / "secret.md").write_text("secret", encoding="utf-8")
    (wiki / "notes.txt").write_text("not markdown", encoding="utf-8")

    assert read_bounded_wiki_page(wiki, "../secret.md").startswith("ERROR: path is outside wiki")
    assert read_bounded_wiki_page(wiki, "missing.md").startswith("ERROR: wiki page not found")
    assert read_bounded_wiki_page(wiki, "notes.txt").startswith("ERROR: only markdown wiki pages may be read")


def test_search_wiki_catalog_respects_kind_filter_and_limit(tmp_path: Path) -> None:
    from graph_wiki_core.agent_tools import build_wiki_catalog, search_wiki_catalog

    wiki = tmp_path / "wiki"
    _page(wiki / "concepts" / "ownership.md", title="Ownership", summary="sections")
    _page(wiki / "sources" / "ownership-source.md", title="Ownership Source", summary="source")
    _page(wiki / "entities" / "packages" / "ownership-pkg.md", title="Ownership Package", kind="package")

    catalog = build_wiki_catalog(wiki)
    concepts = search_wiki_catalog(catalog, "ownership", kind="concept", limit=1)
    entities = search_wiki_catalog(catalog, "ownership", kind="entity", limit=10)

    assert [row["path"] for row in concepts] == ["concepts/ownership.md"]
    assert [row["path"] for row in entities] == ["entities/packages/ownership-pkg.md"]


def test_chunk_text_uses_full_text_under_budget() -> None:
    from graph_wiki_core.agent_tools import chunk_text

    chunks = chunk_text("short text", max_chars=100, chunk_chars=20)

    assert chunks.full_text == "short text"
    assert chunks.chunks == []
    assert chunks.over_budget is False


def test_chunk_text_splits_over_budget_text_deterministically() -> None:
    from graph_wiki_core.agent_tools import chunk_text

    chunks = chunk_text("abcdefghijklmnopqrstuvwxyz", max_chars=10, chunk_chars=8)

    assert chunks.chunks == ["abcdefgh", "ijklmnop", "qrstuvwx", "yz"]
    assert chunks.full_text is None
    assert chunks.over_budget is True


def test_filter_graph_tools_exposes_only_allowed_names() -> None:
    from graph_wiki_core.agent_tools import filter_graph_tools

    @tool
    def cg_find(name: str) -> str:
        """Find a node."""
        return name

    @tool
    def cg_describe(kind: str, identifier: str) -> str:
        """Describe a node."""
        return f"{kind}:{identifier}"

    @tool
    def cg_callers(name: str) -> str:
        """Find callers."""
        return name

    filtered = filter_graph_tools([cg_find, cg_describe, cg_callers], {"cg_find", "cg_describe"})

    assert [graph_tool.name for graph_tool in filtered] == ["cg_find", "cg_describe"]
```

- [ ] **Step 2: Run the new tests to verify they fail**

Run:

```bash
uv run --package graph-wiki-core pytest packages/graph-wiki-core/tests/unit/test_agent_tools.py -v
```

Expected: FAIL with `ModuleNotFoundError: No module named 'graph_wiki_core.agent_tools'`.

- [ ] **Step 3: Commit the failing tests**

Run:

```bash
git add packages/graph-wiki-core/tests/unit/test_agent_tools.py
git commit -m "test: cover shared agent tool helpers"
```

---

### Task 2: Implement Shared Agent Tools

**Files:**
- Create: `packages/graph-wiki-core/src/graph_wiki_core/agent_tools.py`
- Test: `packages/graph-wiki-core/tests/unit/test_agent_tools.py`

- [ ] **Step 1: Add the shared helper module**

Create `packages/graph-wiki-core/src/graph_wiki_core/agent_tools.py`:

```python
"""Reusable bounded tool and context helpers for graph-wiki agent roles."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from langchain_core.tools import BaseTool
from wiki_io.proposals import list_proposals
from wiki_io.update_index import parse_frontmatter

CURATED_CATALOG_BUCKETS = ("concepts", "adrs", "architecture", "sources")
DEFAULT_EXCERPT_CHARS = 500


@dataclass(frozen=True)
class SourceChunks:
    full_text: str | None
    chunks: list[str]
    over_budget: bool


def body_without_frontmatter(text: str) -> str:
    if not text.startswith("---"):
        return text
    parts = text.split("---", 2)
    if len(parts) < 3:
        return text
    return parts[2].strip()


def truncate_text(text: str, max_chars: int) -> str:
    if len(text) <= max_chars:
        return text
    return text[:max_chars] + f"\n\n[TRUNCATED after {max_chars} chars]"


def _frontmatter_entry(path: Path, wiki: Path, kind: str, *, excerpt_chars: int) -> dict[str, Any] | None:
    try:
        text = path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return None

    metadata = parse_frontmatter(text)
    rel_path = path.relative_to(wiki).as_posix()
    body = body_without_frontmatter(text)
    excerpt = " ".join(body.split())[:excerpt_chars]
    return {
        "kind": kind,
        "slug": path.stem,
        "path": rel_path,
        "title": metadata.get("title", path.stem.replace("-", " ").replace("_", " ").title()),
        "summary": metadata.get("summary", ""),
        "uri": metadata.get("uri", ""),
        "entity_kind": metadata.get("kind", ""),
        "excerpt": excerpt,
    }


def build_wiki_catalog(
    wiki: Path,
    buckets: tuple[str, ...] = CURATED_CATALOG_BUCKETS,
    *,
    excerpt_chars: int = DEFAULT_EXCERPT_CHARS,
) -> dict[str, list[dict[str, Any]]]:
    catalog: dict[str, list[dict[str, Any]]] = {name: [] for name in buckets}
    catalog["entities"] = []
    catalog["proposals"] = list_proposals(wiki)

    for dirname in buckets:
        directory = wiki / dirname
        if not directory.is_dir():
            continue
        for path in sorted(directory.glob("*.md")):
            if path.name == "index.md":
                continue
            entry = _frontmatter_entry(path, wiki, dirname.rstrip("s"), excerpt_chars=excerpt_chars)
            if entry is not None:
                catalog[dirname].append(entry)

    entities = wiki / "entities"
    if entities.is_dir():
        for path in sorted(entities.rglob("*.md")):
            if path.name == "index.md":
                continue
            entry = _frontmatter_entry(path, wiki, "entity", excerpt_chars=excerpt_chars)
            if entry is not None:
                catalog["entities"].append(entry)

    return catalog


def read_bounded_wiki_page(wiki: Path, rel_path: str, *, max_chars: int) -> str:
    try:
        wiki_root = wiki.resolve()
        page = (wiki_root / rel_path).resolve()
        page.relative_to(wiki_root)
    except ValueError:
        return "ERROR: path is outside wiki"
    except OSError as exc:
        return f"ERROR: {exc}"

    if page.suffix != ".md":
        return "ERROR: only markdown wiki pages may be read"
    if not page.is_file():
        return f"ERROR: wiki page not found: {rel_path}"

    try:
        text = page.read_text(encoding="utf-8", errors="replace")
    except OSError as exc:
        return f"ERROR: {exc}"

    metadata = parse_frontmatter(text)
    body = body_without_frontmatter(text)
    title = str(metadata.get("title") or page.stem.replace("-", " ").replace("_", " ").title())
    content = f"# {title}\n\n{body}" if body else f"# {title}"
    return truncate_text(content, max_chars)


def _flatten_catalog(catalog: dict[str, list[dict[str, Any]]]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for bucket, entries in catalog.items():
        for entry in entries:
            if isinstance(entry, dict):
                row = dict(entry)
                row.setdefault("bucket", bucket)
                rows.append(row)
    return rows


def _catalog_bucket_matches(bucket: str, entry: dict[str, Any], kind: str | None) -> bool:
    if not kind:
        return True
    normalized = kind.lower().strip()
    if normalized == bucket or normalized == bucket.rstrip("s"):
        return True
    entry_kind = str(entry.get("kind", "")).lower()
    return normalized == entry_kind or normalized == f"{entry_kind}s"


def search_wiki_catalog(
    catalog: dict[str, list[dict[str, Any]]],
    query: str,
    *,
    kind: str | None = None,
    limit: int = 20,
) -> list[dict[str, Any]]:
    query_lc = query.lower().strip()
    matches: list[dict[str, Any]] = []
    for row in _flatten_catalog(catalog):
        bucket = str(row.get("bucket", ""))
        if not _catalog_bucket_matches(bucket, row, kind):
            continue
        fields = [
            str(row.get("title", "")),
            str(row.get("summary", "")),
            str(row.get("slug", "")),
            str(row.get("target_slug", "")),
        ]
        haystack = " ".join(fields).lower()
        if not query_lc or query_lc in haystack:
            matches.append(row)
        if len(matches) >= limit:
            break
    return matches


def chunk_text(text: str, *, max_chars: int, chunk_chars: int) -> SourceChunks:
    if len(text) <= max_chars:
        return SourceChunks(full_text=text, chunks=[], over_budget=False)
    chunks = [text[start : start + chunk_chars] for start in range(0, len(text), chunk_chars)]
    return SourceChunks(full_text=None, chunks=chunks, over_budget=True)


def filter_graph_tools(graph_tools: list[BaseTool], allowed_names: set[str]) -> list[BaseTool]:
    return [graph_tool for graph_tool in graph_tools if graph_tool.name in allowed_names]
```

- [ ] **Step 2: Run the shared helper tests**

Run:

```bash
uv run --package graph-wiki-core pytest packages/graph-wiki-core/tests/unit/test_agent_tools.py -v
```

Expected: PASS.

- [ ] **Step 3: Commit the helper implementation**

Run:

```bash
git add packages/graph-wiki-core/src/graph_wiki_core/agent_tools.py packages/graph-wiki-core/tests/unit/test_agent_tools.py
git commit -m "feat: add shared agent tool helpers"
```

---

### Task 3: Add Shared Tool Loop Tests

**Files:**
- Create: `packages/graph-wiki-core/tests/unit/test_agent_loop.py`
- Test: `packages/graph-wiki-core/tests/unit/test_agent_loop.py`

- [ ] **Step 1: Write terminal and dispatch tests**

Create `packages/graph-wiki-core/tests/unit/test_agent_loop.py` with the first two tests:

```python
from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest
from langchain_core.messages import HumanMessage, ToolMessage
from langchain_core.tools import tool


@pytest.mark.asyncio
async def test_run_tool_loop_returns_terminal_no_tool_response() -> None:
    from graph_wiki_core.agent_loop import run_tool_loop

    llm = MagicMock()
    llm.bind_tools = MagicMock(return_value=llm)
    llm.ainvoke = AsyncMock(return_value=MagicMock(content="final answer", tool_calls=[]))

    result = await run_tool_loop(
        llm=llm,
        tools=[],
        messages=[HumanMessage(content="hello")],
        max_iterations=3,
    )

    assert result.status == "ok"
    assert result.final_text == "final answer"
    assert result.error is None
    assert llm.bind_tools.call_count == 0
    assert llm.ainvoke.call_count == 1


@pytest.mark.asyncio
async def test_run_tool_loop_dispatches_one_tool_call_and_feeds_result_back() -> None:
    from graph_wiki_core.agent_loop import run_tool_loop

    @tool
    def echo(value: str) -> str:
        """Echo a value."""
        return f"tool:{value}"

    first = MagicMock(content="", tool_calls=[{"name": "echo", "args": {"value": "one"}, "id": "call_1"}])
    second = MagicMock(content="done", tool_calls=[])
    llm = MagicMock()
    llm.bind_tools = MagicMock(return_value=llm)
    llm.ainvoke = AsyncMock(side_effect=[first, second])

    result = await run_tool_loop(
        llm=llm,
        tools=[echo],
        messages=[HumanMessage(content="hello")],
        max_iterations=3,
    )

    assert result.status == "ok"
    assert result.final_text == "done"
    assert result.error is None
    assert llm.bind_tools.call_count == 1
    second_messages = llm.ainvoke.call_args_list[1].args[0]
    assert second_messages[-1] == ToolMessage(content="tool:one", tool_call_id="call_1")
```

- [ ] **Step 2: Run the partial loop tests to verify they fail**

Run:

```bash
uv run --package graph-wiki-core pytest packages/graph-wiki-core/tests/unit/test_agent_loop.py -v
```

Expected: FAIL with `ModuleNotFoundError: No module named 'graph_wiki_core.agent_loop'`.

- [ ] **Step 3: Add error and cap tests**

Append these tests to `packages/graph-wiki-core/tests/unit/test_agent_loop.py`:

```python
@pytest.mark.asyncio
async def test_run_tool_loop_turns_unknown_tool_into_tool_message() -> None:
    from graph_wiki_core.agent_loop import run_tool_loop

    first = MagicMock(content="", tool_calls=[{"name": "missing_tool", "args": {}, "id": "call_1"}])
    second = MagicMock(content="recovered", tool_calls=[])
    llm = MagicMock()
    llm.bind_tools = MagicMock(return_value=llm)
    llm.ainvoke = AsyncMock(side_effect=[first, second])

    result = await run_tool_loop(
        llm=llm,
        tools=[],
        messages=[HumanMessage(content="hello")],
        max_iterations=3,
    )

    assert result.status == "ok"
    assert result.final_text == "recovered"
    second_messages = llm.ainvoke.call_args_list[1].args[0]
    assert second_messages[-1] == ToolMessage(content="ERROR: unknown tool 'missing_tool'", tool_call_id="call_1")


@pytest.mark.asyncio
async def test_run_tool_loop_turns_tool_exception_into_tool_message() -> None:
    from graph_wiki_core.agent_loop import run_tool_loop

    @tool
    def explode() -> str:
        """Raise a controlled error."""
        raise RuntimeError("boom")

    first = MagicMock(content="", tool_calls=[{"name": "explode", "args": {}, "id": "call_1"}])
    second = MagicMock(content="recovered", tool_calls=[])
    llm = MagicMock()
    llm.bind_tools = MagicMock(return_value=llm)
    llm.ainvoke = AsyncMock(side_effect=[first, second])

    result = await run_tool_loop(
        llm=llm,
        tools=[explode],
        messages=[HumanMessage(content="hello")],
        max_iterations=3,
    )

    assert result.status == "ok"
    assert result.final_text == "recovered"
    second_messages = llm.ainvoke.call_args_list[1].args[0]
    assert second_messages[-1] == ToolMessage(content="ERROR: boom", tool_call_id="call_1")


@pytest.mark.asyncio
async def test_run_tool_loop_iteration_cap_with_prior_text_returns_ok_with_error() -> None:
    from graph_wiki_core.agent_loop import run_tool_loop

    first = MagicMock(content="partial answer", tool_calls=[{"name": "missing_tool", "args": {}, "id": "call_1"}])
    llm = MagicMock()
    llm.bind_tools = MagicMock(return_value=llm)
    llm.ainvoke = AsyncMock(return_value=first)

    result = await run_tool_loop(
        llm=llm,
        tools=[],
        messages=[HumanMessage(content="hello")],
        max_iterations=1,
    )

    assert result.status == "ok"
    assert result.final_text == "partial answer"
    assert result.error == "tool loop hit iteration cap (1) after producing text"


@pytest.mark.asyncio
async def test_run_tool_loop_iteration_cap_without_prior_text_returns_failed() -> None:
    from graph_wiki_core.agent_loop import run_tool_loop

    first = MagicMock(content="", tool_calls=[{"name": "missing_tool", "args": {}, "id": "call_1"}])
    llm = MagicMock()
    llm.bind_tools = MagicMock(return_value=llm)
    llm.ainvoke = AsyncMock(return_value=first)

    result = await run_tool_loop(
        llm=llm,
        tools=[],
        messages=[HumanMessage(content="hello")],
        max_iterations=1,
    )

    assert result.status == "failed"
    assert result.final_text == ""
    assert result.error == "tool loop hit iteration cap (1)"
```

- [ ] **Step 4: Commit the failing loop tests**

Run:

```bash
git add packages/graph-wiki-core/tests/unit/test_agent_loop.py
git commit -m "test: cover shared agent tool loop"
```

---

### Task 4: Implement Shared Tool Loop

**Files:**
- Create: `packages/graph-wiki-core/src/graph_wiki_core/agent_loop.py`
- Test: `packages/graph-wiki-core/tests/unit/test_agent_loop.py`

- [ ] **Step 1: Add the shared loop module**

Create `packages/graph-wiki-core/src/graph_wiki_core/agent_loop.py`:

```python
"""Reusable capped LangChain tool-call loop for graph-wiki agent roles."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from langchain_core.messages import ToolMessage
from langchain_core.tools import BaseTool


@dataclass(frozen=True)
class ToolLoopResult:
    status: str
    final_text: str
    error: str | None = None


def tool_call_parts(call: Any) -> tuple[str, dict[str, Any], str]:
    if not isinstance(call, dict):
        return "", {}, ""
    name = str(call.get("name", ""))
    args = call.get("args", {})
    if not isinstance(args, dict):
        args = {}
    call_id = str(call.get("id", ""))
    return name, args, call_id


async def run_tool_loop(
    *,
    llm: Any,
    tools: list[BaseTool],
    messages: list[Any],
    max_iterations: int,
    cap_label: str = "tool loop",
) -> ToolLoopResult:
    bound_llm = llm.bind_tools(tools) if tools else llm
    tool_by_name = {agent_tool.name: agent_tool for agent_tool in tools}
    loop_messages = list(messages)
    last_text = ""

    for _iteration in range(max_iterations):
        response = await bound_llm.ainvoke(loop_messages)
        text = getattr(response, "content", "") or ""
        if text:
            last_text = str(text)
        tool_calls = getattr(response, "tool_calls", None) or []
        if not tool_calls:
            return ToolLoopResult(status="ok", final_text=str(text))

        loop_messages.append(response)
        for call in tool_calls:
            call_name, call_args, call_id = tool_call_parts(call)
            agent_tool = tool_by_name.get(call_name)
            if agent_tool is None:
                tool_output = f"ERROR: unknown tool {call_name!r}"
            else:
                try:
                    tool_output = agent_tool.invoke(call_args)
                except Exception as exc:
                    tool_output = f"ERROR: {exc}"
            if not isinstance(tool_output, str):
                tool_output = str(tool_output)
            loop_messages.append(ToolMessage(content=tool_output, tool_call_id=call_id))

    if last_text:
        return ToolLoopResult(
            status="ok",
            final_text=last_text,
            error=f"{cap_label} hit iteration cap ({max_iterations}) after producing text",
        )
    return ToolLoopResult(
        status="failed",
        final_text="",
        error=f"{cap_label} hit iteration cap ({max_iterations})",
    )
```

- [ ] **Step 2: Run the loop tests**

Run:

```bash
uv run --package graph-wiki-core pytest packages/graph-wiki-core/tests/unit/test_agent_loop.py -v
```

Expected: PASS.

- [ ] **Step 3: Commit the loop implementation**

Run:

```bash
git add packages/graph-wiki-core/src/graph_wiki_core/agent_loop.py packages/graph-wiki-core/tests/unit/test_agent_loop.py
git commit -m "feat: add shared agent tool loop"
```

---

### Task 5: Update Proposal Reasoner Tests for the Extraction Boundary

**Files:**
- Modify: `packages/graph-wiki-core/tests/unit/test_proposal_reasoner.py`
- Test: `packages/graph-wiki-core/tests/unit/test_proposal_reasoner.py`

- [ ] **Step 1: Remove tests now owned by `test_agent_tools.py`**

In `packages/graph-wiki-core/tests/unit/test_proposal_reasoner.py`, delete these complete test functions by name:

```python
test_page_helper_writes_frontmatter_pages
test_build_wiki_catalog_lists_curated_sources_entities_and_proposals
test_build_source_chunks_uses_full_text_under_budget
test_build_source_chunks_splits_when_over_budget
test_build_reasoner_tools_read_wiki_page_is_bounded
```

Keep `_page()` because `test_run_proposal_reasoner_handles_one_tool_call()` still uses it.

- [ ] **Step 2: Rename the source chunk tool test to assert proposal-specific wiring**

Replace `test_build_reasoner_tools_read_source_chunk()` with:

```python
def test_build_reasoner_tools_wires_source_chunk_and_allowed_graph_tools(tmp_path: Path) -> None:
    from langchain_core.tools import tool

    from graph_wiki_core.commands.proposal_reasoner import build_reasoner_tools

    @tool
    def cg_find(name: str) -> str:
        """Find a graph node."""
        return name

    @tool
    def cg_callers(name: str) -> str:
        """Find callers."""
        return name

    tools = {
        reasoner_tool.name: reasoner_tool
        for reasoner_tool in build_reasoner_tools(
            wiki=tmp_path / "wiki",
            chunks=["one", "two"],
            graph_tools=[cg_find, cg_callers],
        )
    }

    assert tools["read_source_chunk"].invoke({"index": 1}) == "two"
    assert "ERROR" in tools["read_source_chunk"].invoke({"index": 4})
    assert "read_wiki_page" in tools
    assert "search_wiki_catalog" in tools
    assert "cg_find" in tools
    assert "cg_callers" not in tools
```

- [ ] **Step 3: Update `run_proposal_reasoner` patch point expectation**

In `test_run_proposal_reasoner_handles_one_tool_call()`, keep this patch path unchanged:

```python
with patch("graph_wiki_core.commands.proposal_reasoner.make_llm", return_value=llm):
```

Add this assertion at the end so the refactor preserves role-local binding through the shared loop:

```python
    assert llm.bind_tools.call_count == 1
```

- [ ] **Step 4: Run proposal reasoner tests before refactor**

Run:

```bash
uv run --package graph-wiki-core pytest packages/graph-wiki-core/tests/unit/test_proposal_reasoner.py -v
```

Expected: PASS before implementation refactor. These tests still use the old implementation but now assert the extraction boundary.

- [ ] **Step 5: Commit the test adjustment**

Run:

```bash
git add packages/graph-wiki-core/tests/unit/test_proposal_reasoner.py
git commit -m "test: narrow proposal reasoner extraction boundary"
```

---

### Task 6: Refactor Proposal Reasoner to Shared Helpers

**Files:**
- Modify: `packages/graph-wiki-core/src/graph_wiki_core/commands/proposal_reasoner.py`
- Test: `packages/graph-wiki-core/tests/unit/test_agent_tools.py`
- Test: `packages/graph-wiki-core/tests/unit/test_agent_loop.py`
- Test: `packages/graph-wiki-core/tests/unit/test_proposal_reasoner.py`

- [ ] **Step 1: Replace local helper imports and constants**

In `packages/graph-wiki-core/src/graph_wiki_core/commands/proposal_reasoner.py`, remove these imports:

```python
from typing import Any

from langchain_core.messages import ToolMessage
from wiki_io.proposals import list_proposals
from wiki_io.update_index import parse_frontmatter
```

Keep `dataclass` because `ProposalReasonerResult` still uses it. The corrected import block should include:

```python
import json
from dataclasses import dataclass
from pathlib import Path

from langchain_core.messages import HumanMessage, SystemMessage
from langchain_core.tools import BaseTool, tool
from model_adapter.loader import make_llm

from graph_wiki_core.agent_loop import run_tool_loop
from graph_wiki_core.agent_tools import (
    build_wiki_catalog,
    chunk_text,
    filter_graph_tools,
    read_bounded_wiki_page,
    search_wiki_catalog as search_catalog_rows,
    truncate_text,
)
from graph_wiki_core.prompts.proposal_reasoner import PROPOSAL_REASONER_SYSTEM
```

Delete the obsolete constants:

```python
CURATED_DIRS = ("concepts", "adrs", "architecture", "sources")
EXCERPT_CHARS = 500
```

- [ ] **Step 2: Delete moved helper definitions**

Delete these complete definitions from `proposal_reasoner.py` because `agent_tools.py` or `agent_loop.py` now owns them:

```python
SourceChunks
_body_without_frontmatter
_frontmatter_entry
build_wiki_catalog
build_source_chunks
_truncate_text
_read_bounded_wiki_page
_flatten_catalog
_catalog_bucket_matches
_search_catalog
_tool_call_parts
```

- [ ] **Step 3: Add compatibility aliases for package-local callers**

Add this compatibility alias near the constants so existing imports from `commands.proposal_reasoner` continue to work during this extraction:

```python
build_source_chunks = chunk_text
```

Do not keep aliases for private underscore helpers.

- [ ] **Step 4: Update `build_reasoner_tools()`**

Replace `build_reasoner_tools()` with:

```python
def build_reasoner_tools(*, wiki: Path, chunks: list[str], graph_tools: list[BaseTool]) -> list[BaseTool]:
    catalog = build_wiki_catalog(wiki)

    @tool
    def read_wiki_page(path: str) -> str:
        """Read one markdown page under the wiki root, bounded to a safe size."""
        return read_bounded_wiki_page(wiki, path, max_chars=MAX_WIKI_PAGE_CHARS)

    @tool
    def read_source_chunk(index: int) -> str:
        """Read one source chunk by zero-based index when the source exceeded the prompt budget."""
        if index < 0 or index >= len(chunks):
            return f"ERROR: source chunk index out of range: {index}"
        return chunks[index]

    @tool
    def search_wiki_catalog(query: str, kind: str | None = None) -> str:
        """Search the wiki catalog by title, summary, or slug and return up to 20 JSON rows."""
        rows = search_catalog_rows(catalog, query, kind=kind, limit=20)
        return json.dumps(rows, indent=2, sort_keys=True)

    allowed_graph_tools = filter_graph_tools(graph_tools, _ALLOWED_GRAPH_TOOL_NAMES)
    return [read_wiki_page, read_source_chunk, search_wiki_catalog, *allowed_graph_tools]
```

- [ ] **Step 5: Update `build_reasoner_prompt()`**

Inside `build_reasoner_prompt()`, replace:

```python
source_chunks = build_source_chunks(source_text)
```

with:

```python
source_chunks = chunk_text(source_text, max_chars=FULL_SOURCE_MAX_CHARS, chunk_chars=SOURCE_CHUNK_CHARS)
```

Replace both `_truncate_text(...)` calls with `truncate_text(...)`.

- [ ] **Step 6: Update `run_proposal_reasoner()` to delegate to the loop**

Replace the body of `run_proposal_reasoner()` after the signature with:

```python
    source_chunks = chunk_text(source_text, max_chars=FULL_SOURCE_MAX_CHARS, chunk_chars=SOURCE_CHUNK_CHARS)
    tools = build_reasoner_tools(wiki=wiki, chunks=source_chunks.chunks, graph_tools=graph_tools)
    messages = [
        SystemMessage(content=PROPOSAL_REASONER_SYSTEM),
        HumanMessage(
            content=build_reasoner_prompt(
                wiki=wiki,
                source_path=source_path,
                source_text=source_text,
                source_page_path=source_page_path,
                source_page_text=source_page_text,
                entity_uri=entity_uri,
                entity_stem=entity_stem,
            )
        ),
    ]
    loop_result = await run_tool_loop(
        llm=make_llm("proposal_reasoner"),
        tools=tools,
        messages=messages,
        max_iterations=MAX_REASONER_ITERS,
        cap_label="reasoner",
    )
    return ProposalReasonerResult(
        status=loop_result.status,
        analysis=loop_result.final_text,
        error=loop_result.error,
    )
```

- [ ] **Step 7: Run focused extraction tests**

Run:

```bash
uv run --package graph-wiki-core pytest packages/graph-wiki-core/tests/unit/test_agent_tools.py packages/graph-wiki-core/tests/unit/test_agent_loop.py packages/graph-wiki-core/tests/unit/test_proposal_reasoner.py -v
```

Expected: PASS.

- [ ] **Step 8: Commit the refactor**

Run:

```bash
git add packages/graph-wiki-core/src/graph_wiki_core/commands/proposal_reasoner.py
git commit -m "refactor: delegate proposal reasoner mechanics"
```

---

### Task 7: Add Proposal Reasoner Cap Compatibility Tests

**Files:**
- Modify: `packages/graph-wiki-core/tests/unit/test_proposal_reasoner.py`
- Test: `packages/graph-wiki-core/tests/unit/test_proposal_reasoner.py`

- [ ] **Step 1: Add cap-with-prior-text compatibility coverage**

Append this test to `packages/graph-wiki-core/tests/unit/test_proposal_reasoner.py`:

```python
@pytest.mark.asyncio
async def test_run_proposal_reasoner_iteration_cap_with_prior_text_returns_ok(tmp_path: Path) -> None:
    from graph_wiki_core.commands.proposal_reasoner import MAX_REASONER_ITERS, run_proposal_reasoner

    wiki = tmp_path / "wiki"
    source_page = wiki / "sources" / "spec.md"
    _page(source_page, "Spec", "source")
    response = MagicMock(
        content="Partial candidate analysis",
        tool_calls=[{"name": "missing_tool", "args": {}, "id": "call_1"}],
    )
    llm = MagicMock()
    llm.bind_tools = MagicMock(return_value=llm)
    llm.ainvoke = AsyncMock(return_value=response)

    with patch("graph_wiki_core.commands.proposal_reasoner.make_llm", return_value=llm):
        result = await run_proposal_reasoner(
            wiki=wiki,
            source_path=tmp_path / "source.md",
            source_text="Full source text",
            source_page_path=source_page,
            source_page_text=source_page.read_text(encoding="utf-8"),
            entity_uri=None,
            entity_stem=None,
            graph_tools=[],
        )

    assert result.status == "ok"
    assert result.analysis == "Partial candidate analysis"
    assert result.error == f"reasoner hit iteration cap ({MAX_REASONER_ITERS}) after producing text"
```

- [ ] **Step 2: Add cap-without-text compatibility coverage**

Append this test to `packages/graph-wiki-core/tests/unit/test_proposal_reasoner.py`:

```python
@pytest.mark.asyncio
async def test_run_proposal_reasoner_iteration_cap_without_text_returns_failed(tmp_path: Path) -> None:
    from graph_wiki_core.commands.proposal_reasoner import MAX_REASONER_ITERS, run_proposal_reasoner

    wiki = tmp_path / "wiki"
    source_page = wiki / "sources" / "spec.md"
    _page(source_page, "Spec", "source")
    response = MagicMock(content="", tool_calls=[{"name": "missing_tool", "args": {}, "id": "call_1"}])
    llm = MagicMock()
    llm.bind_tools = MagicMock(return_value=llm)
    llm.ainvoke = AsyncMock(return_value=response)

    with patch("graph_wiki_core.commands.proposal_reasoner.make_llm", return_value=llm):
        result = await run_proposal_reasoner(
            wiki=wiki,
            source_path=tmp_path / "source.md",
            source_text="Full source text",
            source_page_path=source_page,
            source_page_text=source_page.read_text(encoding="utf-8"),
            entity_uri=None,
            entity_stem=None,
            graph_tools=[],
        )

    assert result.status == "failed"
    assert result.analysis == ""
    assert result.error == f"reasoner hit iteration cap ({MAX_REASONER_ITERS})"
```

- [ ] **Step 3: Run proposal reasoner tests**

Run:

```bash
uv run --package graph-wiki-core pytest packages/graph-wiki-core/tests/unit/test_proposal_reasoner.py -v
```

Expected: PASS.

- [ ] **Step 4: Commit cap compatibility tests**

Run:

```bash
git add packages/graph-wiki-core/tests/unit/test_proposal_reasoner.py
git commit -m "test: preserve proposal reasoner cap semantics"
```

---

### Task 8: Run Behavior-Preserving Ingest Verification

**Files:**
- Test: `packages/graph-wiki-core/tests/unit/test_agent_tools.py`
- Test: `packages/graph-wiki-core/tests/unit/test_agent_loop.py`
- Test: `packages/graph-wiki-core/tests/unit/test_proposal_reasoner.py`
- Test: `packages/graph-wiki-core/tests/unit/test_suggest_pages.py`
- Test: `packages/graph-wiki-core/tests/unit/test_commands_ingest.py`
- Test: `packages/model-adapter/tests/test_loader.py`

- [ ] **Step 1: Run new extraction tests**

Run:

```bash
uv run --package graph-wiki-core pytest packages/graph-wiki-core/tests/unit/test_agent_tools.py packages/graph-wiki-core/tests/unit/test_agent_loop.py -v
```

Expected: PASS.

- [ ] **Step 2: Run proposal reasoner tests**

Run:

```bash
uv run --package graph-wiki-core pytest packages/graph-wiki-core/tests/unit/test_proposal_reasoner.py -v
```

Expected: PASS.

- [ ] **Step 3: Run ingest-adjacent tests**

Run:

```bash
uv run --package graph-wiki-core pytest packages/graph-wiki-core/tests/unit/test_suggest_pages.py packages/graph-wiki-core/tests/unit/test_commands_ingest.py -v
```

Expected: PASS.

- [ ] **Step 4: Run model adapter loader smoke test**

Run:

```bash
uv run --package model-adapter pytest packages/model-adapter/tests/test_loader.py -v
```

Expected: PASS.

- [ ] **Step 5: Run scoped Ruff on changed Python files**

Run:

```bash
uv run ruff check packages/graph-wiki-core/src/graph_wiki_core/agent_tools.py packages/graph-wiki-core/src/graph_wiki_core/agent_loop.py packages/graph-wiki-core/src/graph_wiki_core/commands/proposal_reasoner.py packages/graph-wiki-core/tests/unit/test_agent_tools.py packages/graph-wiki-core/tests/unit/test_agent_loop.py packages/graph-wiki-core/tests/unit/test_proposal_reasoner.py
```

Expected: PASS.

- [ ] **Step 6: Commit verification-only fixes if needed**

If any verification step required a code or test fix, commit only those touched files:

```bash
git add packages/graph-wiki-core/src/graph_wiki_core/agent_tools.py packages/graph-wiki-core/src/graph_wiki_core/agent_loop.py packages/graph-wiki-core/src/graph_wiki_core/commands/proposal_reasoner.py packages/graph-wiki-core/tests/unit/test_agent_tools.py packages/graph-wiki-core/tests/unit/test_agent_loop.py packages/graph-wiki-core/tests/unit/test_proposal_reasoner.py
git commit -m "fix: stabilize agent tooling extraction"
```

If no fixes were needed, skip this commit.

---

### Task 9: Final Diff Audit

**Files:**
- Inspect: `packages/graph-wiki-core/src/graph_wiki_core/agent_tools.py`
- Inspect: `packages/graph-wiki-core/src/graph_wiki_core/agent_loop.py`
- Inspect: `packages/graph-wiki-core/src/graph_wiki_core/commands/proposal_reasoner.py`
- Inspect: `packages/graph-wiki-core/tests/unit/test_agent_tools.py`
- Inspect: `packages/graph-wiki-core/tests/unit/test_agent_loop.py`
- Inspect: `packages/graph-wiki-core/tests/unit/test_proposal_reasoner.py`

- [ ] **Step 1: Confirm no broad runtime was introduced**

Run:

```bash
rg -n "SubagentPool|trace|worker|batch|planner|runtime" packages/graph-wiki-core/src/graph_wiki_core/agent_tools.py packages/graph-wiki-core/src/graph_wiki_core/agent_loop.py packages/graph-wiki-core/src/graph_wiki_core/commands/proposal_reasoner.py
```

Expected: no matches for new worker-batch orchestration, generic trace runtime, or planning runtime. Existing words in comments or unrelated prompt text must be removed or justified before final handoff.

- [ ] **Step 2: Confirm Bedrock access still goes through the adapter**

Run:

```bash
rg -n "ChatBedrock|ChatBedrockConverse|langchain_anthropic|make_llm" packages/graph-wiki-core/src/graph_wiki_core/agent_tools.py packages/graph-wiki-core/src/graph_wiki_core/agent_loop.py packages/graph-wiki-core/src/graph_wiki_core/commands/proposal_reasoner.py
```

Expected: only `commands/proposal_reasoner.py` imports and calls `make_llm`; no direct `ChatBedrockConverse`, `ChatBedrock`, or `langchain_anthropic` usage exists.

- [ ] **Step 3: Confirm proposal-specific logic stayed in `proposal_reasoner.py`**

Run:

```bash
rg -n "PROPOSAL_REASONER_SYSTEM|proposal_reasoner|ProposalReasonerResult|Source path|candidate analyses" packages/graph-wiki-core/src/graph_wiki_core/agent_tools.py packages/graph-wiki-core/src/graph_wiki_core/agent_loop.py packages/graph-wiki-core/src/graph_wiki_core/commands/proposal_reasoner.py
```

Expected: proposal role, prompt, result type, and candidate-analysis wording appear only in `commands/proposal_reasoner.py`.

- [ ] **Step 4: Show final status**

Run:

```bash
git status --short
```

Expected: clean except for intentional uncommitted files if the execution workflow deliberately deferred commits. If the plan was executed with the requested frequent commits, the worktree should be clean.
