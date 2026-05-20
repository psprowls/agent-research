from __future__ import annotations

"""Fast unit tests for ingest.py trace-record writing (TRACE-FU-01 D-03).

Asserts the per-call trace record helper-routing change in isolation: ingest
must emit a JSONL trace under ``<wiki>/.graph-wiki/traces/`` with role="ingestor"
and tokens populated from the mocked ChatBedrockConverse response's
usage_metadata. No real Bedrock calls.
"""

import json
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest


@pytest.mark.asyncio
async def test_ingest_writes_trace_record_with_tokens(tmp_path: Path) -> None:
    """ingest writes a JSONL trace with role=ingestor + tokens from usage_metadata."""
    from graph_wiki_agent.commands.ingest import run_ingest_source

    wiki = tmp_path / "wiki"
    wiki.mkdir()
    source = tmp_path / "src.py"
    source.write_text("def foo():\n    pass\n")

    fake_resp = MagicMock()
    fake_resp.content = (
        "---\n"
        "page_type: source\n"
        "title: Source\n"
        "target_slug: src\n"
        "---\n"
        "body\n"
    )
    fake_resp.usage_metadata = {
        "input_tokens": 100,
        "output_tokens": 50,
        "total_tokens": 150,
    }
    fake_llm = MagicMock()
    fake_llm.ainvoke = AsyncMock(return_value=fake_resp)

    with (
        patch("graph_wiki_agent.commands.ingest.resolve_wiki_and_repo", return_value=(wiki, tmp_path)),
        patch("graph_wiki_agent.commands.ingest.make_llm", return_value=fake_llm),
        patch("graph_wiki_agent.commands.ingest.update_index"),
        patch("graph_wiki_agent.commands.ingest.append_log"),
        patch("graph_wiki_agent.commands.ingest.render_project_context", return_value=""),
    ):
        await run_ingest_source(source, vault_path=wiki)

    trace_files = list((wiki / ".graph-wiki" / "traces").glob("ingest_*.jsonl"))
    assert len(trace_files) == 1, f"expected one ingest_*.jsonl, found {trace_files}"
    records = [json.loads(line) for line in trace_files[0].read_text().splitlines() if line.strip()]
    assert len(records) == 1
    rec = records[0]
    assert rec["role"] == "ingestor"
    assert rec["status"] == "success"
    assert rec["tokens_in"] == 100
    assert rec["tokens_out"] == 50
    assert rec["schema_version"] == 1


@pytest.mark.asyncio
async def test_ingest_traces_error_path_with_none_tokens(tmp_path: Path) -> None:
    """ingest must still emit a trace record when llm.ainvoke raises."""
    from botocore.exceptions import BotoCoreError

    from graph_wiki_agent.commands.ingest import run_ingest_source

    wiki = tmp_path / "wiki"
    wiki.mkdir()
    source = tmp_path / "src.py"
    source.write_text("def bar():\n    pass\n")

    fake_llm = MagicMock()
    fake_llm.ainvoke = AsyncMock(side_effect=BotoCoreError())

    with (
        patch("graph_wiki_agent.commands.ingest.resolve_wiki_and_repo", return_value=(wiki, tmp_path)),
        patch("graph_wiki_agent.commands.ingest.make_llm", return_value=fake_llm),
        patch("graph_wiki_agent.commands.ingest.update_index"),
        patch("graph_wiki_agent.commands.ingest.append_log"),
        patch("graph_wiki_agent.commands.ingest.render_project_context", return_value=""),
        pytest.raises(BotoCoreError),
    ):
        await run_ingest_source(source, vault_path=wiki)

    trace_files = list((wiki / ".graph-wiki" / "traces").glob("ingest_*.jsonl"))
    assert len(trace_files) == 1
    records = [json.loads(line) for line in trace_files[0].read_text().splitlines() if line.strip()]
    assert len(records) == 1
    rec = records[0]
    assert rec["role"] == "ingestor"
    assert rec["status"] == "error"
    assert rec["tokens_in"] is None
    assert rec["tokens_out"] is None
    assert "error" in rec
