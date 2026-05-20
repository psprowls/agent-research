from __future__ import annotations

"""Phase 9 OBS-04 (Plan 09-01 Task 2): query.py query_summary writer test.

Decision rule per plan: no existing test in agents/graph-wiki-agent/tests/unit/
reads back a query_{...}.jsonl summary file (grep on "query_summary" /
"summary_record" / "query_*.jsonl" returns no hits in tests/). Therefore this
test is a NEW file rather than an extension to an existing one.

Test drives run_query end-to-end with fast in-process stubs (mirrors the
monkeypatch boundaries already used by
agents/graph-wiki-agent/tests/integration/test_mcp_cancel.py) so the writer block
at query.py:980-995 actually executes against real I/O. The assertion target is
the JSONL line written to .graph-wiki/traces/query_{query_id}.jsonl — that record
must carry schema_version: 1 (D-01 / D-02) AND still carry every pre-existing key.
"""

import json
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

import pytest

from graph_wiki_agent.commands.query import run_query


def _seed_minimal_vault(vault: Path) -> list[str]:
    """Seed enough vault structure that run_query reaches the summary writer.

    Same seed pattern as integration/test_mcp_cancel.py: stub index presence,
    real page files for drill_page's read_text().
    """
    (vault / ".graph-wiki" / "bm25").mkdir(parents=True)
    (vault / ".graph-wiki" / "search.db").touch()

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


async def test_query_summary_record_has_schema_version_one(
    tmp_path: Path, monkeypatch
) -> None:
    """Per Phase 9 OBS-04 D-01/D-02: the query_summary record written by
    query.py at the tail of run_query must contain schema_version: 1 in
    addition to every pre-existing key (kind, query_id, query, top_k,
    pages_retrieved, pages_drilled, code_fallback, started_at, ended_at).
    """
    page_paths = _seed_minimal_vault(tmp_path)

    # Fast stub LLM — returns a real string immediately so librarian fan-out
    # produces useful excerpts and run_query takes the regular (non-fallback) path.
    async def _fast_ainvoke(*args, **kwargs):
        msg = MagicMock()
        msg.usage_metadata = {
            "input_tokens": 1,
            "output_tokens": 1,
            "total_tokens": 2,
        }
        msg.content = "alpha is a package."
        return msg

    fake_llm = MagicMock()
    fake_llm.ainvoke = AsyncMock(side_effect=_fast_ainvoke)

    # Same monkeypatch boundaries as integration/test_mcp_cancel.py so no
    # real Bedrock / BM25 / embedding work runs.
    monkeypatch.setattr(
        "graph_wiki_agent.commands.query.make_llm",
        lambda *a, **kw: fake_llm,
    )
    monkeypatch.setattr(
        "graph_wiki_agent.commands.query.resolve_wiki_and_repo",
        lambda workspace_path=None: (tmp_path.resolve(), None),
    )
    monkeypatch.setattr(
        "graph_wiki_agent.commands.query.bm25_query",
        lambda query_text, vault_path, top_k: (page_paths, [2.0, 1.5, 1.0]),
    )
    monkeypatch.setattr(
        "graph_wiki_agent.commands.query._cosine_search_sqlite",
        lambda vault_path, query_vec, top_k: [
            (p, 0.9 - i * 0.1) for i, p in enumerate(page_paths)
        ],
    )
    mock_embeddings_inst = MagicMock()
    mock_embeddings_inst.embed_query.return_value = [0.1] * 1024
    monkeypatch.setattr(
        "graph_wiki_agent.commands.query.BedrockEmbeddings",
        lambda **kw: mock_embeddings_inst,
    )

    await run_query(query="What is alpha?", workspace_path=tmp_path, top_k=3)

    # Locate the per-query summary file. Filename pattern: query_{query_id}.jsonl
    trace_dir = tmp_path.resolve() / ".graph-wiki" / "traces"
    summary_files = list(trace_dir.glob("query_*.jsonl"))
    assert len(summary_files) == 1, (
        f"Expected exactly one query_*.jsonl summary file in {trace_dir}; "
        f"found {summary_files}"
    )

    # The summary writer opens with "w" and writes one JSON line, so the file
    # is a single-record JSONL.
    raw = summary_files[0].read_text().strip()
    record = json.loads(raw)

    # Primary assertion — Phase 9 OBS-04
    assert record["schema_version"] == 1, (
        f"query_summary record missing schema_version: 1; got {record!r}"
    )
    # Pre-existing keys all still present (additive change rule, Phase 8 D-06/D-07)
    expected_keys = {
        "schema_version",
        "kind",
        "query_id",
        "query",
        "top_k",
        "pages_retrieved",
        "pages_drilled",
        "code_fallback",
        "started_at",
        "ended_at",
    }
    assert expected_keys.issubset(record.keys()), (
        f"query_summary record missing pre-existing keys; "
        f"have {sorted(record.keys())} expected {sorted(expected_keys)}"
    )
    assert record["kind"] == "query_summary"
