# Ingest Proposal Reasoner Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a non-interactive proposal reasoning stage to `gw wiki ingest source`, using Kimi K2.5 for ingestor, proposal reasoner, and extractor, with richer proposal pages and Source frontmatter status.

**Architecture:** Keep `run_ingest_source()` as the command orchestrator. Replace the current direct extractor-only suggestion pass with a three-stage pipeline: Source page write, `proposal_reasoner` context/tool loop, then `extractor` YAML normalization and proposal-ledger writes. Keep proposal failure best-effort and record the result on the Source page.

**Tech Stack:** Python 3.11, `uv`, `langchain-aws` `ChatBedrockConverse`, LangChain tool calling, `python-frontmatter`, `yaml`, existing `graph_io` graph tools, pytest.

---

## File Structure

- Modify `packages/model-adapter/src/model_adapter/models.toml`: set ingestor/extractor to `moonshotai.kimi-k2.5`; add `proposal_reasoner`.
- Modify `packages/model-adapter/tests/test_loader.py`: assert model config for all three ingest proposal roles.
- Modify `packages/wiki-io/src/wiki_io/proposals.py`: extend proposal records with `rank`, `confidence`, and richer body sections while preserving decided-note behavior.
- Modify `packages/wiki-io/tests/test_proposals.py`: cover richer proposal rendering, optional fields, and decided-note preservation.
- Create `packages/graph-wiki-core/src/graph_wiki_core/prompts/proposal_reasoner.py`: system prompt for candidate reasoning.
- Modify `packages/graph-wiki-core/src/graph_wiki_core/prompts/extractor.py`: make extractor normalize reasoner analysis into top 5 strict YAML proposals.
- Modify `packages/graph-wiki-core/tests/prompts/test_prompt_snapshots.py`: add proposal reasoner prompt snapshot.
- Create `packages/graph-wiki-core/src/graph_wiki_core/commands/proposal_reasoner.py`: context catalog, source chunking, bounded tool loop, and reasoner result type.
- Modify `packages/graph-wiki-core/src/graph_wiki_core/commands/suggest_pages.py`: orchestrate reasoner plus extractor, parse richer YAML, and write enriched proposals.
- Modify `packages/graph-wiki-core/src/graph_wiki_core/commands/ingest.py`: call the new suggestion pipeline, stamp Source `proposal_status`, and expand `IngestResult`.
- Modify `packages/graph-wiki-core/tests/unit/test_commands_ingest.py`: cover success/degraded status and max-5 proposal selection.
- Add `packages/graph-wiki-core/tests/unit/test_proposal_reasoner.py`: cover catalog, chunking, tool loop, and graph-unavailable behavior.

## Task 1: Model Config

**Files:**
- Modify: `packages/model-adapter/src/model_adapter/models.toml`
- Modify: `packages/model-adapter/tests/test_loader.py`

- [ ] **Step 1: Write failing model config tests**

Add this test near the existing role config tests in `packages/model-adapter/tests/test_loader.py`:

```python
def test_ingest_proposal_roles_use_kimi_k25() -> None:
    from model_adapter.loader import load_role_config

    expected = {
        "ingestor": 4096,
        "proposal_reasoner": 4096,
        "extractor": 2048,
    }
    for role, max_tokens in expected.items():
        cfg = load_role_config(role)
        assert cfg["model_id"] == "moonshotai.kimi-k2.5"
        assert cfg["region"] == "us-east-1"
        assert cfg["max_tokens"] == max_tokens
        assert "moonshotai.kimi-k2.5" in cfg["sweep_candidates"]
```

- [ ] **Step 2: Run the failing test**

Run:

```bash
cd packages/model-adapter
uv run pytest tests/test_loader.py::test_ingest_proposal_roles_use_kimi_k25 -q
```

Expected: FAIL because `proposal_reasoner` is missing and `ingestor` / `extractor` still use `zai.glm-4.7-flash`.

- [ ] **Step 3: Update model config**

Change `packages/model-adapter/src/model_adapter/models.toml` so the blocks are:

```toml
[roles.ingestor]
model_id        = "moonshotai.kimi-k2.5"
region          = "us-east-1"
max_tokens      = 4096
max_concurrency = 5
sweep_candidates = [
  "qwen.qwen3-32b-v1:0",
  "openai.gpt-oss-120b-1:0",
  "minimax.minimax-m2.5",
  "qwen.qwen3-next-80b-a3b",
  "moonshotai.kimi-k2.5",
]

[roles.proposal_reasoner]
# Ingest proposal reasoning pass. Uses Kimi K2.5 through Bedrock runtime;
# Kimi K2 Thinking and Bedrock Mantle are deferred.
model_id        = "moonshotai.kimi-k2.5"
region          = "us-east-1"
max_tokens      = 4096
max_concurrency = 3
sweep_candidates = [
  "moonshotai.kimi-k2.5",
]

[roles.extractor]
# Normalizes proposal_reasoner analysis into strict proposal YAML.
model_id        = "moonshotai.kimi-k2.5"
region          = "us-east-1"
max_tokens      = 2048
max_concurrency = 5
sweep_candidates = [
  "qwen.qwen3-32b-v1:0",
  "openai.gpt-oss-120b-1:0",
  "minimax.minimax-m2.5",
  "qwen.qwen3-next-80b-a3b",
  "moonshotai.kimi-k2.5",
]
```

- [ ] **Step 4: Run model-adapter tests**

Run:

```bash
cd packages/model-adapter
uv run pytest tests/test_loader.py -q
```

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add packages/model-adapter/src/model_adapter/models.toml packages/model-adapter/tests/test_loader.py
git commit -m "config: add ingest proposal reasoner role"
```

## Task 2: Rich Proposal Ledger Body

**Files:**
- Modify: `packages/wiki-io/src/wiki_io/proposals.py`
- Modify: `packages/wiki-io/tests/test_proposals.py`

- [ ] **Step 1: Write failing rich proposal tests**

Append these tests to `packages/wiki-io/tests/test_proposals.py`:

```python
def test_rich_proposal_body_renders_review_sections() -> None:
    from wiki_io.proposals import render_proposal_body

    record = {
        "kind": "concept",
        "mode": "create_new",
        "target_slug": "section-ownership",
        "title": "Section ownership",
        "status": "proposed",
        "rank": 1,
        "confidence": "high",
        "origins": [
            {
                "ref": "sources/spec",
                "source": "ingest",
                "rationale": "The source defines ownership boundaries.",
                "evidence": ["Scanner owns narrative sections.", "Humans own notes."],
                "existing_pages_considered": ["concepts/human-owned-sections"],
                "reasoning_summary": "This is reusable across scanner and ingest pages.",
                "potential_conflicts": ["May overlap with existing page ownership docs."],
                "implementation_notes": ["Create a concept page and link scanner docs."],
            }
        ],
    }

    body = render_proposal_body(record)

    assert "## Suggested Action" in body
    assert "Create new concept page `concepts/section-ownership.md`." in body
    assert "## Evidence From Source" in body
    assert "- Scanner owns narrative sections." in body
    assert "## Existing Pages Considered" in body
    assert "- [[concepts/human-owned-sections]]" in body
    assert "## Reasoning Summary" in body
    assert "This is reusable across scanner and ingest pages." in body
    assert "## Potential Conflicts" in body
    assert "## Implementation Notes" in body
    assert "## Origins" in body


def test_upsert_persists_rank_confidence_and_rich_origin(tmp_path: Path) -> None:
    from wiki_io.proposals import proposal_path, read_proposal, upsert_proposal

    wiki = tmp_path / "wiki"
    upsert_proposal(
        wiki,
        {
            "kind": "architecture",
            "mode": "update_existing",
            "target_slug": "runtime-flow",
            "title": "Runtime flow",
            "rank": 2,
            "confidence": "medium",
            "origin": {
                "ref": "sources/runtime",
                "source": "ingest",
                "rationale": "The source changes the runtime-flow thesis.",
                "evidence": ["Pipeline adds a reasoner stage."],
                "existing_pages_considered": ["architecture/runtime-flow"],
                "reasoning_summary": "Update the existing architecture page.",
                "potential_conflicts": [],
                "implementation_notes": ["Append to How this synthesis has changed."],
            },
        },
    )

    rec = read_proposal(proposal_path(wiki, "architecture", "runtime-flow"))
    assert rec["rank"] == 2
    assert rec["confidence"] == "medium"
    assert rec["origins"][0]["evidence"] == ["Pipeline adds a reasoner stage."]
```

- [ ] **Step 2: Run failing tests**

Run:

```bash
cd packages/wiki-io
uv run pytest tests/test_proposals.py::test_rich_proposal_body_renders_review_sections tests/test_proposals.py::test_upsert_persists_rank_confidence_and_rich_origin -q
```

Expected: FAIL because optional fields are dropped and the body lacks review sections.

- [ ] **Step 3: Extend proposal record ordering and parsing**

Update `packages/wiki-io/src/wiki_io/proposals.py` constants and helpers:

```python
_RECORD_KEY_ORDER = ("kind", "mode", "target_slug", "title", "status", "rank", "confidence", "origins")
_ORIGIN_KEY_ORDER = (
    "ref",
    "source",
    "rationale",
    "evidence",
    "existing_pages_considered",
    "reasoning_summary",
    "potential_conflicts",
    "implementation_notes",
    "detected_commit",
    "hash",
)
```

Update `_record_from_metadata()`:

```python
def _record_from_metadata(metadata: dict, stem: str) -> dict:
    """Build a proposal record dict from parsed frontmatter metadata."""
    origins = metadata.get("origins") or []
    record = {
        "kind": metadata.get("kind", ""),
        "mode": metadata.get("mode", "create_new"),
        "target_slug": metadata.get("target_slug", stem),
        "title": metadata.get("title", ""),
        "status": metadata.get("status", "proposed"),
        "origins": [dict(o) for o in origins if isinstance(o, dict)],
    }
    if "rank" in metadata:
        record["rank"] = metadata["rank"]
    if "confidence" in metadata:
        record["confidence"] = metadata["confidence"]
    return record
```

- [ ] **Step 4: Render rich proposal body**

Replace `render_proposal_body()` with:

```python
def _as_list(value: object) -> list[str]:
    if value is None:
        return []
    if isinstance(value, list):
        return [str(v).strip() for v in value if str(v).strip()]
    text = str(value).strip()
    return [text] if text else []


def _wikilink_if_page(ref: str) -> str:
    return f"[[{ref}]]" if "/" in ref else ref


def _suggested_action(record: dict) -> str:
    kind = record["kind"]
    target = record["target_slug"]
    mode = record.get("mode", "create_new")
    dirname = {"concept": "concepts", "adr": "adrs", "architecture": "architecture"}[kind]
    verb = "Update existing" if mode == "update_existing" else "Create new"
    return f"{verb} {kind} page `{dirname}/{target}.md`."


def render_proposal_body(record: dict) -> str:
    """Render a proposed note into a review artifact.

    The body is regenerated while status is proposed. Human-decided notes keep
    their current body through set_proposal_status().
    """
    proposal_id = f"{record['kind']}-{record['target_slug']}"
    comment = (
        "<!-- Body regenerated from origins[] while status: proposed. Do not "
        "edit here;\n"
        f"     approve via `gw wiki proposal approve {proposal_id}`. -->"
    )
    origins = record.get("origins", [])
    lines = [
        comment,
        "",
        "## Suggested Action",
        "",
        _suggested_action(record),
        "",
        "## Evidence From Source",
        "",
    ]
    evidence: list[str] = []
    considered: list[str] = []
    conflicts: list[str] = []
    notes: list[str] = []
    summaries: list[str] = []
    for origin in origins:
        evidence.extend(_as_list(origin.get("evidence")))
        considered.extend(_as_list(origin.get("existing_pages_considered")))
        conflicts.extend(_as_list(origin.get("potential_conflicts")))
        notes.extend(_as_list(origin.get("implementation_notes")))
        summaries.extend(_as_list(origin.get("reasoning_summary")))
    lines.extend(f"- {item}" for item in evidence)
    if not evidence:
        lines.append("- No source evidence was captured.")
    lines.extend(["", "## Existing Pages Considered", ""])
    lines.extend(f"- {_wikilink_if_page(item)}" for item in considered)
    if not considered:
        lines.append("- No existing pages were cited by the proposal reasoner.")
    lines.extend(["", "## Reasoning Summary", ""])
    lines.extend(summaries or ["No reasoning summary was captured."])
    lines.extend(["", "## Potential Conflicts", ""])
    lines.extend(f"- {item}" for item in conflicts)
    if not conflicts:
        lines.append("- No conflicts identified.")
    lines.extend(["", "## Implementation Notes", ""])
    lines.extend(f"- {item}" for item in notes)
    if not notes:
        lines.append("- No implementation notes captured.")
    lines.extend(["", "## Origins", ""])
    for origin in origins:
        lines.append(f"**{origin.get('source', '')} · [[{origin.get('ref', '')}]]**")
        rationale = (origin.get("rationale") or "").strip()
        if rationale:
            lines.append(rationale)
        lines.append("")
    return "\n".join(lines).rstrip("\n")
```

- [ ] **Step 5: Preserve optional record fields in upsert**

In `upsert_proposal()`, when updating an existing proposed record, add:

```python
        if "rank" in proposal:
            record["rank"] = proposal["rank"]
        if "confidence" in proposal:
            record["confidence"] = proposal["confidence"]
```

When creating a new record, add optional fields before `_ordered_record(record)`:

```python
        if "rank" in proposal:
            record["rank"] = proposal["rank"]
        if "confidence" in proposal:
            record["confidence"] = proposal["confidence"]
```

- [ ] **Step 6: Run proposal tests**

Run:

```bash
cd packages/wiki-io
uv run pytest tests/test_proposals.py -q
```

Expected: PASS.

- [ ] **Step 7: Commit**

```bash
git add packages/wiki-io/src/wiki_io/proposals.py packages/wiki-io/tests/test_proposals.py
git commit -m "feat: enrich proposal ledger notes"
```

## Task 3: Proposal Reasoner Prompt And Context Unit

**Files:**
- Create: `packages/graph-wiki-core/src/graph_wiki_core/prompts/proposal_reasoner.py`
- Create: `packages/graph-wiki-core/src/graph_wiki_core/commands/proposal_reasoner.py`
- Create: `packages/graph-wiki-core/tests/unit/test_proposal_reasoner.py`
- Modify: `packages/graph-wiki-core/tests/prompts/test_prompt_snapshots.py`

- [ ] **Step 1: Write failing context tests**

Create `packages/graph-wiki-core/tests/unit/test_proposal_reasoner.py`:

```python
from __future__ import annotations

from pathlib import Path


def _page(path: Path, title: str, category: str, summary: str = "summary") -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        f"---\ntitle: {title}\ncategory: {category}\nsummary: {summary}\n---\n\n# {title}\n\nBody.",
        encoding="utf-8",
    )


def test_build_wiki_catalog_lists_curated_sources_entities_and_proposals(tmp_path: Path) -> None:
    from graph_wiki_core.commands.proposal_reasoner import build_wiki_catalog
    from wiki_io.proposals import upsert_proposal

    wiki = tmp_path / "wiki"
    _page(wiki / "concepts" / "ownership.md", "Ownership", "concept", "Section ownership")
    _page(wiki / "adrs" / "0001-runtime.md", "Runtime", "adr", "Runtime decision")
    _page(wiki / "architecture" / "flow.md", "Flow", "architecture", "Runtime flow")
    _page(wiki / "sources" / "spec.md", "Spec", "source", "Design source")
    (wiki / "entities").mkdir()
    (wiki / "entities" / "pkg_core.md").write_text(
        "---\ntitle: core\nuri: pkg:repo/core\nkind: package\nsummary: Core package\n---\n\n## Narrative\nCore runtime.\n",
        encoding="utf-8",
    )
    upsert_proposal(
        wiki,
        {
            "kind": "concept",
            "mode": "create_new",
            "target_slug": "open-proposal",
            "title": "Open Proposal",
            "origin": {"ref": "sources/spec", "source": "ingest", "rationale": "r"},
        },
    )

    catalog = build_wiki_catalog(wiki)

    assert [e["slug"] for e in catalog["concepts"]] == ["ownership"]
    assert [e["slug"] for e in catalog["adrs"]] == ["0001-runtime"]
    assert [e["slug"] for e in catalog["architecture"]] == ["flow"]
    assert [e["slug"] for e in catalog["sources"]] == ["spec"]
    assert catalog["entities"][0]["uri"] == "pkg:repo/core"
    assert catalog["proposals"][0]["target_slug"] == "open-proposal"


def test_build_source_chunks_uses_full_text_under_budget() -> None:
    from graph_wiki_core.commands.proposal_reasoner import build_source_chunks

    chunks = build_source_chunks("short text", max_chars=100, chunk_chars=20)

    assert chunks.full_text == "short text"
    assert chunks.chunks == []
    assert chunks.over_budget is False


def test_build_source_chunks_splits_when_over_budget() -> None:
    from graph_wiki_core.commands.proposal_reasoner import build_source_chunks

    chunks = build_source_chunks("abcdefghijklmnopqrstuvwxyz", max_chars=10, chunk_chars=8)

    assert chunks.full_text is None
    assert chunks.over_budget is True
    assert chunks.chunks == ["abcdefgh", "ijklmnop", "qrstuvwx", "yz"]
```

- [ ] **Step 2: Run failing context tests**

Run:

```bash
cd packages/graph-wiki-core
uv run pytest tests/unit/test_proposal_reasoner.py -q
```

Expected: FAIL because `proposal_reasoner.py` does not exist.

- [ ] **Step 3: Add reasoner prompt**

Create `packages/graph-wiki-core/src/graph_wiki_core/prompts/proposal_reasoner.py`:

```python
"""Proposal reasoner prompt for ingest-time curated-page suggestions."""

from __future__ import annotations

PROPOSAL_REASONER_SYSTEM = """You are a code-wiki proposal reasoner.

Analyze an ingested source document and decide which durable wiki pages it justifies.
You do NOT write wiki pages. You produce candidate analyses for a downstream extractor.

Candidate kinds:
- concept: reusable technical idea, pattern, or practice.
- adr: dated consequential decision recorded or strongly implied by the source.
- architecture: cross-cutting synthesis of how system parts fit together.

Rules:
- Use the provided wiki catalog before proposing a new page.
- Prefer updating an existing page when the idea is already covered.
- Generate at most 10 candidates.
- Each candidate must include source evidence, existing pages considered, reasoning summary, potential conflicts, implementation notes, confidence, and rank.
- Be conservative. It is valid to return no candidates.
- Do not emit strict final proposal YAML; the extractor normalizes your analysis.
"""
```

- [ ] **Step 4: Add catalog and chunk helpers**

Create `packages/graph-wiki-core/src/graph_wiki_core/commands/proposal_reasoner.py`:

```python
"""Ingest proposal reasoner support: context, tools, and bounded tool loop."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from wiki_io.proposals import list_proposals
from wiki_io.update_index import parse_frontmatter

CURATED_DIRS = ("concepts", "adrs", "architecture", "sources")
FULL_SOURCE_MAX_CHARS = 120_000
SOURCE_CHUNK_CHARS = 20_000


@dataclass(frozen=True)
class SourceChunks:
    full_text: str | None
    chunks: list[str]
    over_budget: bool


def _frontmatter_entry(path: Path, wiki: Path, kind: str) -> dict[str, Any] | None:
    try:
        text = path.read_text(encoding="utf-8")
    except OSError:
        return None
    fm = parse_frontmatter(text)
    body_preview = text.split("---", 2)[-1].strip()[:500] if text.startswith("---") else text[:500]
    return {
        "kind": kind,
        "slug": path.stem,
        "path": path.relative_to(wiki).as_posix(),
        "title": fm.get("title", path.stem),
        "summary": fm.get("summary", ""),
        "uri": fm.get("uri"),
        "entity_kind": fm.get("kind"),
        "excerpt": body_preview,
    }


def build_wiki_catalog(wiki: Path) -> dict[str, list[dict[str, Any]]]:
    catalog: dict[str, list[dict[str, Any]]] = {name: [] for name in CURATED_DIRS}
    for dirname in CURATED_DIRS:
        directory = wiki / dirname
        if not directory.is_dir():
            continue
        for page in sorted(directory.glob("*.md")):
            entry = _frontmatter_entry(page, wiki, dirname.rstrip("s"))
            if entry is not None:
                catalog[dirname].append(entry)
    entities: list[dict[str, Any]] = []
    entity_dir = wiki / "entities"
    if entity_dir.is_dir():
        for page in sorted(entity_dir.glob("*.md")):
            entry = _frontmatter_entry(page, wiki, "entity")
            if entry is not None:
                entities.append(entry)
    catalog["entities"] = entities
    catalog["proposals"] = list_proposals(wiki)
    return catalog


def build_source_chunks(
    source_text: str,
    *,
    max_chars: int = FULL_SOURCE_MAX_CHARS,
    chunk_chars: int = SOURCE_CHUNK_CHARS,
) -> SourceChunks:
    if len(source_text) <= max_chars:
        return SourceChunks(full_text=source_text, chunks=[], over_budget=False)
    chunks = [source_text[i : i + chunk_chars] for i in range(0, len(source_text), chunk_chars)]
    return SourceChunks(full_text=None, chunks=chunks, over_budget=True)
```

- [ ] **Step 5: Add prompt snapshot test**

In `packages/graph-wiki-core/tests/prompts/test_prompt_snapshots.py`, add:

```python
def test_proposal_reasoner_system_snapshot(snapshot: SnapshotAssertion) -> None:
    from graph_wiki_core.prompts.proposal_reasoner import PROPOSAL_REASONER_SYSTEM

    assert PROPOSAL_REASONER_SYSTEM == snapshot
```

- [ ] **Step 6: Run context and prompt tests**

Run:

```bash
cd packages/graph-wiki-core
uv run pytest tests/unit/test_proposal_reasoner.py tests/prompts/test_prompt_snapshots.py::test_proposal_reasoner_system_snapshot -q
```

Expected: PASS if the snapshot already exists. If the new prompt snapshot is missing, update only that snapshot:

```bash
cd packages/graph-wiki-core
uv run pytest tests/prompts/test_prompt_snapshots.py::test_proposal_reasoner_system_snapshot --snapshot-update -q
uv run pytest tests/prompts/test_prompt_snapshots.py::test_proposal_reasoner_system_snapshot -q
```

- [ ] **Step 7: Commit**

```bash
git add packages/graph-wiki-core/src/graph_wiki_core/prompts/proposal_reasoner.py packages/graph-wiki-core/src/graph_wiki_core/commands/proposal_reasoner.py packages/graph-wiki-core/tests/unit/test_proposal_reasoner.py packages/graph-wiki-core/tests/prompts/test_prompt_snapshots.py packages/graph-wiki-core/tests/prompts/__snapshots__/test_prompt_snapshots.ambr
git commit -m "feat: add ingest proposal reasoner context"
```

## Task 4: Reasoner Tool Loop

**Files:**
- Modify: `packages/graph-wiki-core/src/graph_wiki_core/commands/proposal_reasoner.py`
- Modify: `packages/graph-wiki-core/tests/unit/test_proposal_reasoner.py`

- [ ] **Step 1: Write failing tool-loop tests**

Append to `packages/graph-wiki-core/tests/unit/test_proposal_reasoner.py`:

```python
from unittest.mock import AsyncMock, MagicMock, patch


def test_build_reasoner_tools_read_wiki_page_is_bounded(tmp_path: Path) -> None:
    from graph_wiki_core.commands.proposal_reasoner import build_reasoner_tools

    wiki = tmp_path / "wiki"
    _page(wiki / "concepts" / "ownership.md", "Ownership", "concept")
    tools = {tool.name: tool for tool in build_reasoner_tools(wiki=wiki, chunks=[], graph_tools=[])}

    out = tools["read_wiki_page"].invoke({"path": "concepts/ownership.md"})

    assert "# Ownership" in out
    assert "ERROR" not in out
    assert "outside wiki" in tools["read_wiki_page"].invoke({"path": "../secret.md"})


def test_build_reasoner_tools_read_source_chunk(tmp_path: Path) -> None:
    from graph_wiki_core.commands.proposal_reasoner import build_reasoner_tools

    tools = {tool.name: tool for tool in build_reasoner_tools(wiki=tmp_path / "wiki", chunks=["one", "two"], graph_tools=[])}

    assert tools["read_source_chunk"].invoke({"index": 1}) == "two"
    assert "ERROR" in tools["read_source_chunk"].invoke({"index": 4})


@pytest.mark.asyncio
async def test_run_proposal_reasoner_handles_one_tool_call(tmp_path: Path) -> None:
    from graph_wiki_core.commands.proposal_reasoner import run_proposal_reasoner

    wiki = tmp_path / "wiki"
    _page(wiki / "concepts" / "ownership.md", "Ownership", "concept")
    source_page = wiki / "sources" / "spec.md"
    _page(source_page, "Spec", "source")

    first = MagicMock(
        content="",
        tool_calls=[{"name": "read_wiki_page", "args": {"path": "concepts/ownership.md"}, "id": "call_1"}],
    )
    second = MagicMock(content="Candidate: update Ownership", tool_calls=[])
    llm = MagicMock()
    llm.bind_tools = MagicMock(return_value=llm)
    llm.ainvoke = AsyncMock(side_effect=[first, second])

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
    assert result.analysis == "Candidate: update Ownership"
    assert llm.ainvoke.call_count == 2
```

Add `import pytest` at the top of the file.

- [ ] **Step 2: Run failing tests**

Run:

```bash
cd packages/graph-wiki-core
uv run pytest tests/unit/test_proposal_reasoner.py -q
```

Expected: FAIL because tool helpers and `run_proposal_reasoner()` are missing.

- [ ] **Step 3: Add result type, tools, and bounded loop**

Append these imports and definitions to `packages/graph-wiki-core/src/graph_wiki_core/commands/proposal_reasoner.py`:

```python
import json

from langchain_core.messages import HumanMessage, SystemMessage, ToolMessage
from langchain_core.tools import BaseTool, tool
from model_adapter.loader import make_llm

from graph_wiki_core.prompts.proposal_reasoner import PROPOSAL_REASONER_SYSTEM

MAX_REASONER_ITERS = 5
MAX_WIKI_PAGE_CHARS = 40_000


@dataclass(frozen=True)
class ProposalReasonerResult:
    status: str
    analysis: str
    error: str | None = None


def _read_bounded_wiki_page(wiki: Path, rel_path: str) -> str:
    target = (wiki / rel_path).resolve()
    wiki_resolved = wiki.resolve()
    if not target.is_relative_to(wiki_resolved):
        return "ERROR: path is outside wiki"
    if target.suffix != ".md":
        return "ERROR: only markdown wiki pages can be read"
    try:
        text = target.read_text(encoding="utf-8")
    except OSError as exc:
        return f"ERROR: {exc}"
    return text[:MAX_WIKI_PAGE_CHARS]


def build_reasoner_tools(*, wiki: Path, chunks: list[str], graph_tools: list[BaseTool]) -> list[BaseTool]:
    @tool
    def read_wiki_page(path: str) -> str:
        """Read a bounded markdown page under the wiki root by wiki-relative path."""
        return _read_bounded_wiki_page(wiki, path)

    @tool
    def read_source_chunk(index: int) -> str:
        """Read one zero-based chunk from an oversized source document."""
        if index < 0 or index >= len(chunks):
            return f"ERROR: source chunk index {index} is out of range"
        return chunks[index]

    @tool
    def search_wiki_catalog(query: str, kind: str | None = None) -> str:
        """Search prepared wiki catalog titles and summaries by substring."""
        catalog = build_wiki_catalog(wiki)
        query_l = query.lower()
        rows: list[dict[str, Any]] = []
        for bucket, entries in catalog.items():
            if kind and bucket != kind and bucket.rstrip("s") != kind:
                continue
            for entry in entries:
                haystack = f"{entry.get('title', '')} {entry.get('summary', '')} {entry.get('slug', '')}".lower()
                if query_l in haystack:
                    rows.append(entry)
        return json.dumps(rows[:20], indent=2)

    tools = [read_wiki_page, read_source_chunk, search_wiki_catalog]
    tools.extend(t for t in graph_tools if t.name in {"cg_find", "cg_describe"})
    return tools


def build_reasoner_prompt(
    *,
    source_path: Path,
    source_text: str,
    source_page_path: Path,
    source_page_text: str,
    catalog: dict[str, list[dict[str, Any]]],
    chunks: SourceChunks,
    entity_uri: str | None,
    entity_stem: str | None,
) -> str:
    source_block = source_text if chunks.full_text is not None else "[SOURCE OVER BUDGET: use read_source_chunk(index)]"
    chunk_block = "\n".join(f"- chunk {i}: {len(chunk)} chars" for i, chunk in enumerate(chunks.chunks))
    return (
        f"Source path: {source_path}\n"
        f"Source page: {source_page_path.name}\n"
        f"Entity URI: {entity_uri or 'null'}\n"
        f"Entity page stem: {entity_stem or 'null'}\n\n"
        f"Catalog JSON:\n{json.dumps(catalog, indent=2)[:80_000]}\n\n"
        f"Source chunks:\n{chunk_block or '(full source included)'}\n\n"
        f"--- Source page ---\n{source_page_text[:40_000]}\n--- End Source page ---\n\n"
        f"--- Raw source ---\n{source_block}\n--- End raw source ---\n\n"
        "Produce up to 10 candidate analyses. Include kind, title, slug, mode, existing_slug, "
        "rank, confidence, source evidence, existing pages considered, reasoning summary, "
        "potential conflicts, and implementation notes for each candidate."
    )


async def run_proposal_reasoner(
    *,
    wiki: Path,
    source_path: Path,
    source_text: str,
    source_page_path: Path,
    source_page_text: str,
    entity_uri: str | None,
    entity_stem: str | None,
    graph_tools: list[BaseTool],
) -> ProposalReasonerResult:
    chunks = build_source_chunks(source_text)
    catalog = build_wiki_catalog(wiki)
    tools = build_reasoner_tools(wiki=wiki, chunks=chunks.chunks, graph_tools=graph_tools)
    llm = make_llm("proposal_reasoner").bind_tools(tools)
    msgs: list = [
        SystemMessage(content=PROPOSAL_REASONER_SYSTEM),
        HumanMessage(
            content=build_reasoner_prompt(
                source_path=source_path,
                source_text=source_text,
                source_page_path=source_page_path,
                source_page_text=source_page_text,
                catalog=catalog,
                chunks=chunks,
                entity_uri=entity_uri,
                entity_stem=entity_stem,
            )
        ),
    ]
    tool_by_name = {t.name: t for t in tools}
    last_text = ""
    for _ in range(MAX_REASONER_ITERS):
        resp = await llm.ainvoke(msgs)
        if isinstance(getattr(resp, "content", ""), str):
            last_text = resp.content
        tool_calls = getattr(resp, "tool_calls", None) or []
        if not tool_calls:
            return ProposalReasonerResult(status="ok", analysis=last_text)
        msgs.append(resp)
        for call in tool_calls:
            name = call.get("name", "") if isinstance(call, dict) else ""
            args = call.get("args", {}) if isinstance(call, dict) else {}
            call_id = call.get("id", "") if isinstance(call, dict) else ""
            tool_obj = tool_by_name.get(name)
            tool_output = f"ERROR: unknown tool {name!r}" if tool_obj is None else tool_obj.invoke(args)
            msgs.append(ToolMessage(content=str(tool_output), tool_call_id=call_id))
    if last_text.strip():
        return ProposalReasonerResult(status="ok", analysis=last_text)
    return ProposalReasonerResult(status="failed", analysis="", error="proposal_reasoner hit tool iteration cap")
```

- [ ] **Step 4: Run tool-loop tests**

Run:

```bash
cd packages/graph-wiki-core
uv run pytest tests/unit/test_proposal_reasoner.py -q
```

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add packages/graph-wiki-core/src/graph_wiki_core/commands/proposal_reasoner.py packages/graph-wiki-core/tests/unit/test_proposal_reasoner.py
git commit -m "feat: add proposal reasoner tool loop"
```

## Task 5: Extractor Normalization And Suggest Pipeline

**Files:**
- Modify: `packages/graph-wiki-core/src/graph_wiki_core/prompts/extractor.py`
- Modify: `packages/graph-wiki-core/src/graph_wiki_core/commands/suggest_pages.py`
- Modify: `packages/graph-wiki-core/tests/unit/test_commands_ingest.py`

- [ ] **Step 1: Write failing parse and top-5 tests**

Append to `packages/graph-wiki-core/tests/unit/test_commands_ingest.py`:

```python
def test_parse_extractor_response_accepts_rich_fields_and_limits_to_five() -> None:
    from graph_wiki_core.commands.suggest_pages import parse_extractor_response

    items = "\n".join(
        f"""  - kind: concept
    title: Candidate {i}
    slug: candidate-{i}
    mode: create_new
    existing_slug:
    rank: {i}
    confidence: medium
    rationale: Candidate {i} rationale.
    evidence:
      - Evidence {i}
    existing_pages_considered:
      - concepts/existing
    reasoning_summary: Reasoning {i}
    potential_conflicts:
      - Conflict {i}
    implementation_notes:
      - Note {i}"""
        for i in range(1, 7)
    )
    proposals, parsed = parse_extractor_response(f"suggestions:\n{items}")

    assert parsed is True
    assert len(proposals) == 5
    assert proposals[0]["rank"] == 1
    assert proposals[0]["confidence"] == "medium"
    assert proposals[0]["evidence"] == ["Evidence 1"]
```

- [ ] **Step 2: Run failing parse test**

Run:

```bash
cd packages/graph-wiki-core
uv run pytest tests/unit/test_commands_ingest.py::test_parse_extractor_response_accepts_rich_fields_and_limits_to_five -q
```

Expected: FAIL because `_validate_proposal()` drops rich fields and does not cap to 5.

- [ ] **Step 3: Update extractor prompt**

Replace `EXTRACTOR_SYSTEM` in `packages/graph-wiki-core/src/graph_wiki_core/prompts/extractor.py` with:

```python
EXTRACTOR_SYSTEM = """You normalize proposal-reasoner analysis into strict YAML.

You do NOT create wiki pages. You select at most 5 strongest proposals from the reasoner's candidates.
Output one YAML mapping with a single `suggestions:` list. No prose and no code fence.

Allowed kinds:
- concept
- adr
- architecture

Each suggestion requires:
- kind
- title
- slug
- mode: create_new or update_existing
- existing_slug: slug when mode is update_existing, blank otherwise
- rank: integer starting at 1
- confidence: high, medium, or low
- rationale: one sentence
- evidence: list of source-grounded bullets
- existing_pages_considered: list of wiki-relative page refs
- reasoning_summary: one short paragraph
- potential_conflicts: list, empty if none
- implementation_notes: list, empty if none

Rules:
- Return at most 5 suggestions.
- Prefer update_existing when the reasoner found an existing page match.
- Drop weak, duplicate, or unsupported candidates.
- Return `suggestions: []` when no durable page is justified.
"""
```

- [ ] **Step 4: Extend parser validation**

In `packages/graph-wiki-core/src/graph_wiki_core/commands/suggest_pages.py`, update `_ENTRY_KEY_ORDER`:

```python
_ENTRY_KEY_ORDER = (
    "kind",
    "title",
    "slug",
    "mode",
    "existing_slug",
    "rank",
    "confidence",
    "rationale",
    "evidence",
    "existing_pages_considered",
    "reasoning_summary",
    "potential_conflicts",
    "implementation_notes",
    "status",
)
```

Add helper:

```python
def _string_list(value: object) -> list[str]:
    if value is None:
        return []
    if isinstance(value, list):
        return [str(v).strip() for v in value if str(v).strip()]
    text = str(value).strip()
    return [text] if text else []
```

Extend `_validate_proposal()` return payload:

```python
    rank_raw = raw.get("rank", 999)
    try:
        rank = int(rank_raw)
    except (TypeError, ValueError):
        rank = 999
    confidence = str(raw.get("confidence", "medium")).strip().lower()
    if confidence not in {"high", "medium", "low"}:
        confidence = "medium"
    return _ordered_entry(
        {
            "kind": kind,
            "title": title,
            "slug": slug,
            "mode": mode,
            "existing_slug": existing_slug,
            "rank": rank,
            "confidence": confidence,
            "rationale": rationale,
            "evidence": _string_list(raw.get("evidence")),
            "existing_pages_considered": _string_list(raw.get("existing_pages_considered")),
            "reasoning_summary": str(raw.get("reasoning_summary", "")).strip(),
            "potential_conflicts": _string_list(raw.get("potential_conflicts")),
            "implementation_notes": _string_list(raw.get("implementation_notes")),
        }
    )
```

At the end of `parse_extractor_response()`, sort and cap:

```python
    proposals.sort(key=lambda p: int(p.get("rank", 999)))
    return proposals[:5], True
```

- [ ] **Step 5: Thread rich proposal fields into upsert**

In `run_suggest_phase()`, when building the `upsert_proposal()` payload, include:

```python
                "rank": p.get("rank"),
                "confidence": p.get("confidence"),
                "origin": {
                    "ref": source_ref,
                    "source": "ingest",
                    "rationale": p.get("rationale", ""),
                    "evidence": p.get("evidence", []),
                    "existing_pages_considered": p.get("existing_pages_considered", []),
                    "reasoning_summary": p.get("reasoning_summary", ""),
                    "potential_conflicts": p.get("potential_conflicts", []),
                    "implementation_notes": p.get("implementation_notes", []),
                },
```

Also include `rank` and `confidence` in each report dict.

- [ ] **Step 6: Run ingest parser tests**

Run:

```bash
cd packages/graph-wiki-core
uv run pytest tests/unit/test_commands_ingest.py::test_parse_extractor_response_accepts_rich_fields_and_limits_to_five -q
```

Expected: PASS.

- [ ] **Step 7: Commit**

```bash
git add packages/graph-wiki-core/src/graph_wiki_core/prompts/extractor.py packages/graph-wiki-core/src/graph_wiki_core/commands/suggest_pages.py packages/graph-wiki-core/tests/unit/test_commands_ingest.py
git commit -m "feat: normalize rich ingest proposals"
```

## Task 6: Wire Reasoner Into Suggest Phase

**Files:**
- Modify: `packages/graph-wiki-core/src/graph_wiki_core/commands/suggest_pages.py`
- Modify: `packages/graph-wiki-core/src/graph_wiki_core/commands/ingest.py`
- Modify: `packages/graph-wiki-core/tests/unit/test_commands_ingest.py`

- [ ] **Step 1: Write failing orchestration test**

Append to `packages/graph-wiki-core/tests/unit/test_commands_ingest.py`:

```python
@pytest.mark.asyncio
async def test_run_suggest_phase_uses_reasoner_analysis(tmp_path: Path) -> None:
    from graph_wiki_core.commands.suggest_pages import run_suggest_phase
    from graph_wiki_core.commands.proposal_reasoner import ProposalReasonerResult

    wiki = tmp_path / "wiki"
    page = wiki / "sources" / "spec.md"
    page.parent.mkdir(parents=True)
    page.write_text("---\ntitle: Spec\ncategory: source\n---\n\nSummary.", encoding="utf-8")

    extractor = MagicMock()
    extractor.ainvoke = AsyncMock(
        return_value=MagicMock(
            content=(
                "suggestions:\n"
                "  - kind: concept\n"
                "    title: Better Ingest\n"
                "    slug: better-ingest\n"
                "    mode: create_new\n"
                "    existing_slug:\n"
                "    rank: 1\n"
                "    confidence: high\n"
                "    rationale: The reasoner found a durable ingest pattern.\n"
                "    evidence:\n"
                "      - Full document evidence.\n"
                "    existing_pages_considered: []\n"
                "    reasoning_summary: Create a focused concept.\n"
                "    potential_conflicts: []\n"
                "    implementation_notes:\n"
                "      - Link to the source page.\n"
            )
        )
    )

    with (
        patch(
            "graph_wiki_core.commands.suggest_pages.run_proposal_reasoner",
            return_value=ProposalReasonerResult(status="ok", analysis="rich reasoner analysis"),
        ) as reasoner,
        patch("graph_wiki_core.commands.suggest_pages.make_llm", return_value=extractor),
    ):
        reports, status = await run_suggest_phase(
            wiki=wiki,
            page_path=page,
            source_path=tmp_path / "raw.md",
            source_text="full raw document",
            entity_uri=None,
            entity_stem=None,
            graph_tools=[],
        )

    reasoner.assert_called_once()
    assert status["reasoner"] == "ok"
    assert status["extractor"] == "ok"
    assert reports[0]["slug"] == "better-ingest"
```

- [ ] **Step 2: Run failing orchestration test**

Run:

```bash
cd packages/graph-wiki-core
uv run pytest tests/unit/test_commands_ingest.py::test_run_suggest_phase_uses_reasoner_analysis -q
```

Expected: FAIL because `run_suggest_phase()` does not accept the new arguments or call the reasoner.

- [ ] **Step 3: Add pipeline status type**

In `packages/graph-wiki-core/src/graph_wiki_core/commands/suggest_pages.py`, import the reasoner:

```python
from graph_wiki_core.commands.proposal_reasoner import ProposalReasonerResult, run_proposal_reasoner
```

Change `build_extract_suggestions_prompt()` signature:

```python
def build_extract_suggestions_prompt(reasoner_analysis: str, vault_index: list[dict]) -> str:
```

Make the body use `reasoner_analysis` instead of source-page preview:

```python
        "--- Proposal reasoner analysis ---\n"
        f"{reasoner_analysis}\n"
        "--- End proposal reasoner analysis ---\n\n"
        "Normalize the reasoner analysis into at most 5 YAML `suggestions:` entries. "
        "Return `suggestions: []` if none are warranted."
```

- [ ] **Step 4: Change `run_suggest_phase()` signature and body**

Replace the signature with:

```python
async def run_suggest_phase(
    *,
    wiki: Path,
    page_path: Path,
    source_path: Path,
    source_text: str,
    entity_uri: str | None,
    entity_stem: str | None,
    graph_tools: list,
) -> tuple[list[dict], dict]:
```

At the start of the function:

```python
    page_text = page_path.read_text(encoding="utf-8")
    status = {"reasoner": "skipped", "extractor": "skipped", "proposals": 0, "error": None}
    reasoner_result = await run_proposal_reasoner(
        wiki=wiki,
        source_path=source_path,
        source_text=source_text,
        source_page_path=page_path,
        source_page_text=page_text,
        entity_uri=entity_uri,
        entity_stem=entity_stem,
        graph_tools=graph_tools,
    )
    status["reasoner"] = reasoner_result.status
    if reasoner_result.status != "ok":
        status["error"] = reasoner_result.error or "proposal_reasoner failed"
        return [], status
```

Then build the extractor prompt from `reasoner_result.analysis`. On extractor exceptions, return `([], status)` with `extractor: failed` and a short error. On parse miss, set `extractor: failed`, `error: extractor output did not parse`. On success, set `extractor: ok` and `proposals: len(reports)`.

- [ ] **Step 5: Pass graph tools from ingest**

In `packages/graph-wiki-core/src/graph_wiki_core/commands/ingest.py`, import:

```python
from graph_wiki_core.graph_tools import build_graph_tools
```

Before calling `run_suggest_phase()`, build:

```python
        graph_tools = build_graph_tools(conn)
```

Change the call:

```python
            suggested_pages, proposal_status = await run_suggest_phase(
                wiki=wiki,
                page_path=target_path,
                source_path=source_path,
                source_text=text,
                entity_uri=canonical_uri,
                entity_stem=entity_stem,
                graph_tools=graph_tools,
            )
```

In the `except` branch:

```python
            suggested_pages = []
            proposal_status = {
                "reasoner": "failed",
                "extractor": "skipped",
                "proposals": 0,
                "error": "suggest phase failed",
            }
```

Temporarily keep `suggestions_parsed = proposal_status["extractor"] == "ok"` for compatibility.

- [ ] **Step 6: Run orchestration test**

Run:

```bash
cd packages/graph-wiki-core
uv run pytest tests/unit/test_commands_ingest.py::test_run_suggest_phase_uses_reasoner_analysis -q
```

Expected: PASS.

- [ ] **Step 7: Commit**

```bash
git add packages/graph-wiki-core/src/graph_wiki_core/commands/suggest_pages.py packages/graph-wiki-core/src/graph_wiki_core/commands/ingest.py packages/graph-wiki-core/tests/unit/test_commands_ingest.py
git commit -m "feat: run proposal reasoner during ingest"
```

## Task 7: Source Proposal Status Frontmatter

**Files:**
- Modify: `packages/graph-wiki-core/src/graph_wiki_core/commands/ingest.py`
- Modify: `packages/graph-wiki-core/tests/unit/test_commands_ingest.py`

- [ ] **Step 1: Write failing Source frontmatter status tests**

Append to `packages/graph-wiki-core/tests/unit/test_commands_ingest.py`:

```python
def test_set_proposal_status_in_body_inserts_nested_block() -> None:
    from graph_wiki_core.commands.ingest import _set_proposal_status_in_body

    text = "---\ntitle: Spec\ntarget_slug: spec\n---\n\nBody"
    out = _set_proposal_status_in_body(
        text,
        {"reasoner": "ok", "extractor": "ok", "proposals": 2, "error": None},
        today="2026-06-06",
    )

    assert "proposal_status:" in out
    assert "  reasoner: ok" in out
    assert "  extractor: ok" in out
    assert "  proposals: 2" in out
    assert "  updated: 2026-06-06" in out
    assert "error:" not in out


def test_set_proposal_status_in_body_replaces_existing_block() -> None:
    from graph_wiki_core.commands.ingest import _set_proposal_status_in_body

    text = (
        "---\n"
        "title: Spec\n"
        "proposal_status:\n"
        "  reasoner: failed\n"
        "  extractor: skipped\n"
        "  proposals: 0\n"
        "  updated: 2026-06-05\n"
        "  error: old\n"
        "---\n\nBody"
    )
    out = _set_proposal_status_in_body(
        text,
        {"reasoner": "ok", "extractor": "ok", "proposals": 1, "error": None},
        today="2026-06-06",
    )

    assert out.count("proposal_status:") == 1
    assert "old" not in out
    assert "  proposals: 1" in out
```

- [ ] **Step 2: Run failing tests**

Run:

```bash
cd packages/graph-wiki-core
uv run pytest tests/unit/test_commands_ingest.py::test_set_proposal_status_in_body_inserts_nested_block tests/unit/test_commands_ingest.py::test_set_proposal_status_in_body_replaces_existing_block -q
```

Expected: FAIL because helper does not exist.

- [ ] **Step 3: Add frontmatter helper**

In `packages/graph-wiki-core/src/graph_wiki_core/commands/ingest.py`, add imports:

```python
from datetime import date
```

Add helper near the other frontmatter helpers:

```python
def _sanitize_proposal_error(error: object) -> str | None:
    if not error:
        return None
    text = str(error).replace("\n", " ").strip()
    return text[:160]


def _set_proposal_status_in_body(text: str, status: dict, *, today: str | None = None) -> str:
    """Insert or replace proposal_status in Source frontmatter."""
    stripped = text.lstrip()
    if not stripped.startswith("---"):
        return text
    after_open = stripped[3:].lstrip("\n")
    close_idx = after_open.find("\n---")
    if close_idx == -1:
        return text
    leading_ws = text[: len(text) - len(stripped)]
    fm_block = after_open[:close_idx]
    body_and_close = after_open[close_idx:]
    updated = today or date.today().isoformat()
    proposal_lines = [
        "proposal_status:",
        f"  reasoner: {status.get('reasoner', 'skipped')}",
        f"  extractor: {status.get('extractor', 'skipped')}",
        f"  proposals: {int(status.get('proposals', 0) or 0)}",
        f"  updated: {updated}",
    ]
    error = _sanitize_proposal_error(status.get("error"))
    if error:
        proposal_lines.append(f"  error: {error}")

    new_lines: list[str] = []
    skipping = False
    for line in fm_block.splitlines():
        if line.startswith("proposal_status:"):
            skipping = True
            continue
        if skipping:
            if line.startswith(" ") or line.startswith("\t") or not line.strip():
                continue
            skipping = False
        new_lines.append(line)
    new_lines.extend(proposal_lines)
    return f"{leading_ws}---\n" + "\n".join(new_lines) + body_and_close
```

- [ ] **Step 4: Stamp status after proposal phase**

In `run_ingest_source()`, after the `run_suggest_phase()` try/except and before `update_index(wiki)`, add:

```python
        current_text = target_path.read_text(encoding="utf-8")
        stamped_text = _set_proposal_status_in_body(current_text, proposal_status)
        if stamped_text != current_text:
            target_path.write_text(stamped_text, encoding="utf-8")
```

- [ ] **Step 5: Expand `IngestResult` fields**

In the `IngestResult` dataclass, add:

```python
    proposal_reasoner_status: str = "skipped"
    proposal_extractor_status: str = "skipped"
    proposal_error: str | None = None
```

In the return statement, add:

```python
            proposal_reasoner_status=str(proposal_status.get("reasoner", "skipped")),
            proposal_extractor_status=str(proposal_status.get("extractor", "skipped")),
            proposal_error=proposal_status.get("error"),
```

- [ ] **Step 6: Run Source status tests**

Run:

```bash
cd packages/graph-wiki-core
uv run pytest tests/unit/test_commands_ingest.py::test_set_proposal_status_in_body_inserts_nested_block tests/unit/test_commands_ingest.py::test_set_proposal_status_in_body_replaces_existing_block -q
```

Expected: PASS.

- [ ] **Step 7: Commit**

```bash
git add packages/graph-wiki-core/src/graph_wiki_core/commands/ingest.py packages/graph-wiki-core/tests/unit/test_commands_ingest.py
git commit -m "feat: record ingest proposal status"
```

## Task 8: End-To-End Unit Coverage And Verification

**Files:**
- Modify: `packages/graph-wiki-core/tests/unit/test_commands_ingest.py`
- Modify: `packages/graph-wiki-core/tests/unit/test_proposal_reasoner.py`

- [ ] **Step 1: Add success end-to-end assertion**

In the existing proposal success test in `packages/graph-wiki-core/tests/unit/test_commands_ingest.py`, update assertions to include:

```python
    written = (wiki / result.page_path).read_text(encoding="utf-8")
    assert "proposal_status:" in written
    assert "  reasoner: ok" in written
    assert "  extractor: ok" in written
    assert result.proposal_reasoner_status == "ok"
    assert result.proposal_extractor_status == "ok"
```

Patch `run_proposal_reasoner` in that test to return `ProposalReasonerResult(status="ok", analysis="reasoned candidates")`.

- [ ] **Step 2: Add degraded reasoner test**

Add:

```python
@pytest.mark.asyncio
async def test_run_ingest_source_records_reasoner_failure(tmp_path: Path) -> None:
    from graph_wiki_core.commands.ingest import run_ingest_source
    from graph_wiki_core.commands.proposal_reasoner import ProposalReasonerResult

    source_file = tmp_path / "spec.md"
    source_file.write_text("# Spec\n\nContent.", encoding="utf-8")
    wiki = tmp_path / "wiki"
    wiki.mkdir()
    (wiki / "log.md").write_text("", encoding="utf-8")
    _seed_graph_db_for_ingest_tests(wiki, packages=[])

    ingestor = MagicMock()
    ingestor.ainvoke = AsyncMock(return_value=MagicMock(content="---\ntarget_slug: spec\ntitle: Spec\nsummary: x\n---\nBody."))

    with (
        patch("graph_wiki_core.commands.ingest.resolve_wiki_and_repo", return_value=(wiki, tmp_path)),
        patch("graph_wiki_core.commands.ingest.make_llm", return_value=ingestor),
        patch("graph_wiki_core.commands.ingest.update_index"),
        patch("graph_wiki_core.commands.ingest.append_log"),
        patch("graph_wiki_core.commands.ingest.render_project_context", return_value=""),
        patch(
            "graph_wiki_core.commands.suggest_pages.run_proposal_reasoner",
            return_value=ProposalReasonerResult(status="failed", analysis="", error="reasoner failed"),
        ),
    ):
        result = await run_ingest_source(source_file, wiki)

    written = (wiki / result.page_path).read_text(encoding="utf-8")
    assert "  reasoner: failed" in written
    assert "  extractor: skipped" in written
    assert "  error: reasoner failed" in written
    assert result.proposal_reasoner_status == "failed"
    assert result.proposal_extractor_status == "skipped"
```

- [ ] **Step 3: Run focused graph-wiki-core tests**

Run:

```bash
cd packages/graph-wiki-core
uv run pytest tests/unit/test_proposal_reasoner.py tests/unit/test_commands_ingest.py -q
```

Expected: PASS.

- [ ] **Step 4: Run wiki-io and model-adapter tests**

Run:

```bash
cd packages/wiki-io
uv run pytest tests/test_proposals.py -q

cd ../model-adapter
uv run pytest tests/test_loader.py -q
```

Expected: PASS.

- [ ] **Step 5: Run scoped Ruff**

Run:

```bash
uv run ruff check \
  packages/model-adapter/src/model_adapter/models.toml \
  packages/model-adapter/tests/test_loader.py \
  packages/wiki-io/src/wiki_io/proposals.py \
  packages/wiki-io/tests/test_proposals.py \
  packages/graph-wiki-core/src/graph_wiki_core/commands/ingest.py \
  packages/graph-wiki-core/src/graph_wiki_core/commands/suggest_pages.py \
  packages/graph-wiki-core/src/graph_wiki_core/commands/proposal_reasoner.py \
  packages/graph-wiki-core/src/graph_wiki_core/prompts/extractor.py \
  packages/graph-wiki-core/src/graph_wiki_core/prompts/proposal_reasoner.py \
  packages/graph-wiki-core/tests/unit/test_commands_ingest.py \
  packages/graph-wiki-core/tests/unit/test_proposal_reasoner.py
```

Expected: PASS. If Ruff rejects the `.toml` path, rerun without it:

```bash
uv run ruff check \
  packages/model-adapter/tests/test_loader.py \
  packages/wiki-io/src/wiki_io/proposals.py \
  packages/wiki-io/tests/test_proposals.py \
  packages/graph-wiki-core/src/graph_wiki_core/commands/ingest.py \
  packages/graph-wiki-core/src/graph_wiki_core/commands/suggest_pages.py \
  packages/graph-wiki-core/src/graph_wiki_core/commands/proposal_reasoner.py \
  packages/graph-wiki-core/src/graph_wiki_core/prompts/extractor.py \
  packages/graph-wiki-core/src/graph_wiki_core/prompts/proposal_reasoner.py \
  packages/graph-wiki-core/tests/unit/test_commands_ingest.py \
  packages/graph-wiki-core/tests/unit/test_proposal_reasoner.py
```

- [ ] **Step 6: Commit**

```bash
git add packages/graph-wiki-core/tests/unit/test_commands_ingest.py packages/graph-wiki-core/tests/unit/test_proposal_reasoner.py
git commit -m "test: cover ingest proposal reasoner pipeline"
```

## Final Verification

- [ ] **Step 1: Run all targeted tests**

```bash
cd packages/model-adapter
uv run pytest tests/test_loader.py -q

cd ../wiki-io
uv run pytest tests/test_proposals.py -q

cd ../graph-wiki-core
uv run pytest tests/unit/test_proposal_reasoner.py tests/unit/test_commands_ingest.py -q
```

Expected: all pass.

- [ ] **Step 2: Check status**

```bash
git status --short
```

Expected: clean working tree.

- [ ] **Step 3: Summarize commits**

```bash
git log --oneline --decorate --max-count=10
```

Expected: the feature branch contains the spec commit plus task commits for model config, proposal ledger, reasoner context/tools, suggest pipeline, Source status, and tests.
