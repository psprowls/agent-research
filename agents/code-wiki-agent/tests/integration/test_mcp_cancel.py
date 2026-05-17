from __future__ import annotations

"""Cancel-mid-fan-out test (direct asyncio; no subprocess). Requirements covered: MCP-10, MCP-11."""

import asyncio
import json
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

import pytest

from code_wiki_agent.commands.query import run_query


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _seed_minimal_vault(vault: Path) -> list[str]:
    """Seed a minimal vault so drill_page can read real pages.

    Creates .code-wiki/bm25/ and .code-wiki/search.db so auto-build is
    skipped, plus 3 page files that the mocked search layer returns.
    Returns the page paths that bm25_query / _cosine_search_sqlite will report.
    """
    # Stub index presence so run_query skips the real build_index call
    (vault / ".code-wiki" / "bm25").mkdir(parents=True)
    (vault / ".code-wiki" / "search.db").touch()

    # Real page files — drill_page reads these via (wiki / page_path).read_text()
    pages_dir = vault / "pages"
    pages_dir.mkdir()
    (pages_dir / "alpha.md").write_text(
        "---\ntitle: Alpha\n---\n\n# Alpha\n\nAlpha is a package.\n"
    )
    (pages_dir / "beta.md").write_text(
        "---\ntitle: Beta\n---\n\n# Beta\n\nBeta depends on alpha.\n"
    )
    (pages_dir / "gamma.md").write_text(
        "---\ntitle: Gamma\n---\n\n# Gamma\n\nGamma provides utilities.\n"
    )

    return ["pages/alpha.md", "pages/beta.md", "pages/gamma.md"]


# ---------------------------------------------------------------------------
# Cancel test
# ---------------------------------------------------------------------------


async def test_cancel_mid_fan_out(tmp_path: Path, monkeypatch) -> None:
    """Cancelling the run_query task mid-fan-out emits per-item cancelled records
    and a single batch_cancelled summary record in the trace file.

    Requirements covered: MCP-10, MCP-11.

    Design:
    - Direct asyncio (no subprocess) — allows in-process monkeypatch of make_llm.
    - No INTEGRATION_GATE — runs unconditionally; stub LLM means zero Bedrock cost.
    - Race control: stub ainvoke sleeps 3 s; test cancels after asyncio.sleep(0)
      yield, guaranteeing all _run_one coroutines are in-flight (deterministic).
    """
    page_paths = _seed_minimal_vault(tmp_path)

    # --- Slow stub LLM ---
    # ainvoke sleeps long enough that cancellation always arrives mid-flight.
    # Returns a MagicMock with usage_metadata=None so _write_trace None-guard
    # does not blow up if somehow the success path is reached.
    async def _slow_ainvoke(*args, **kwargs):
        await asyncio.sleep(3)
        msg = MagicMock()
        msg.usage_metadata = None
        msg.content = "stub answer"
        return msg

    fake_llm = MagicMock()
    fake_llm.ainvoke = AsyncMock(side_effect=_slow_ainvoke)

    # Patch make_llm at the importer's binding (code_wiki_agent.commands.query).
    # `from model_adapter.loader import make_llm` creates a local name in query.py,
    # so patching model_adapter.loader.make_llm here would not redirect run_query's
    # call. Targeting the importer's namespace ensures the slow stub is actually
    # installed and no Bedrock call is attempted.
    monkeypatch.setattr(
        "code_wiki_agent.commands.query.make_llm",
        lambda *a, **kw: fake_llm,
    )

    # Patch resolve_wiki_and_repo so run_query uses our tmp_path vault directly.
    monkeypatch.setattr(
        "code_wiki_agent.commands.query.resolve_wiki_and_repo",
        lambda vault_path=None: (tmp_path.resolve(), None),
    )

    # Patch the search layer — BM25 and embedding calls — to return the seeded pages
    # without hitting the real bm25 index or Bedrock embedding API.
    monkeypatch.setattr(
        "code_wiki_agent.commands.query.bm25_query",
        lambda query_text, vault_path, top_k: (page_paths, [2.0, 1.5, 1.0]),
    )
    monkeypatch.setattr(
        "code_wiki_agent.commands.query._cosine_search_sqlite",
        lambda vault_path, query_vec, top_k: [(p, 0.9 - i * 0.1) for i, p in enumerate(page_paths)],
    )

    # Patch BedrockEmbeddings to avoid the real Titan embed call in run_query's
    # Step 4. embed_query returns a dummy 1024-dim vector.
    mock_embeddings_inst = MagicMock()
    mock_embeddings_inst.embed_query.return_value = [0.1] * 1024
    monkeypatch.setattr(
        "code_wiki_agent.commands.query.BedrockEmbeddings",
        lambda **kw: mock_embeddings_inst,
    )

    # --- Cancel sequence ---
    # asyncio.ensure_future schedules run_query on the running event loop.
    task = asyncio.ensure_future(
        run_query(query="What is alpha?", vault_path=tmp_path, top_k=3)
    )

    # Yield control long enough for asyncio.gather to start _run_one coroutines and
    # for each _run_one to reach its "await asyncio.sleep(3)" in _slow_ainvoke.
    # A single asyncio.sleep(0) is not enough — the event loop needs multiple turns
    # to: (1) start run_query, (2) enter pool.run_all, (3) schedule gather, (4) start
    # each _run_one, (5) acquire semaphore, (6) reach "await task(item)".
    # 0.05 s is deterministic with a 3 s stub sleep (ratio 60:1).
    await asyncio.sleep(0.05)

    task.cancel()

    # The outer CancelledError MUST propagate (Invariant 3 — FastMCP depends on this).
    with pytest.raises(asyncio.CancelledError):
        await task

    # --- Trace assertions ---
    # Trace files are written to: wiki / ".code-wiki" / "traces" / "*.jsonl"
    # wiki = tmp_path.resolve() per the monkeypatched resolve_wiki_and_repo.
    trace_dir = tmp_path.resolve() / ".code-wiki" / "traces"
    trace_files = list(trace_dir.glob("*.jsonl"))
    assert trace_files, f"No trace files found in {trace_dir}"

    lines = [
        json.loads(line)
        for line in trace_files[0].read_text().splitlines()
        if line.strip()
    ]
    assert lines, "Trace file is empty"

    # (a) At least one per-item record with status: cancelled
    cancelled = [line for line in lines if line.get("status") == "cancelled"]
    assert cancelled, f"Expected ≥1 per-item cancelled record; got lines: {lines}"

    # (b) Exactly one batch terminal record with event: batch_cancelled
    batch = [line for line in lines if line.get("event") == "batch_cancelled"]
    assert len(batch) == 1, (
        f"Expected exactly one batch_cancelled record, got {len(batch)}; lines: {lines}"
    )

    # (c) The batch_cancelled record is the LAST line in the trace file (Invariant 5)
    assert lines[-1].get("event") == "batch_cancelled", (
        f"batch_cancelled must be the last trace line; last line: {lines[-1]}"
    )

    # (d) Per-item cancelled records have NO event key (D-07 discriminator)
    assert all("event" not in line for line in cancelled), (
        "Per-item cancelled records must not carry an 'event' key"
    )
