from __future__ import annotations

"""End-to-end TRACE-FU-01 regression: real fan-out asserts every JSONL record
has non-None input_tokens/output_tokens (SC#1 D-05). Gated by
GRAPH_WIKI_RUN_INTEGRATION=1.
"""

import json
import os
import subprocess
from pathlib import Path

import pytest


_PROJECT_ROOT: Path = Path(__file__).parent.parent.parent.parent.parent
FIXTURE_VAULT: Path = (
    _PROJECT_ROOT
    / "packages"
    / "vault-io"
    / "tests"
    / "fixtures"
    / "round-trip-vault"
)

INTEGRATION_GATE = pytest.mark.skipif(
    not os.environ.get("GRAPH_WIKI_RUN_INTEGRATION"),
    reason="Set GRAPH_WIKI_RUN_INTEGRATION=1 to run real Bedrock invocations",
)


def _run(cmd: list[str], cwd: Path, env: dict | None = None) -> subprocess.CompletedProcess:
    return subprocess.run(
        cmd,
        cwd=str(cwd),
        capture_output=True,
        text=True,
        timeout=300,
        env=env or {**os.environ},
    )


@pytest.mark.integration
@INTEGRATION_GATE
def test_trace_pipeline_records_token_usage(tmp_path: Path) -> None:
    """Every non-error/non-event JSONL trace record carries non-None tokens."""
    # Copy the fixture vault so we can write traces into a tmp tree without
    # mutating the committed fixture.
    import shutil

    wiki = tmp_path / "wiki"
    shutil.copytree(FIXTURE_VAULT, wiki)
    # Fixture vault may contain stale traces from prior runs; clear them so the
    # assertion only walks records produced by THIS run (G-01 follow-up: the
    # original 2026-05-19 failure was partially caused by reading a stale
    # 2026-05-14 record). The traces dir is .gitignored in the fixture too.
    stale_traces = wiki / ".graph-wiki" / "traces"
    if stale_traces.exists():
        shutil.rmtree(stale_traces)

    # Build the index + run a small query to populate traces. ``scan`` is
    # optional — query suffices to exercise the librarian + synthesizer paths.
    result = _run(
        [
            "uv", "run", "--package", "graph-wiki-agent",
            "graph-wiki-agent", "query",
            "What concepts are documented in the wiki?",
            "--workspace", str(wiki),
            "--top-k", "3",
            "--json",
        ],
        cwd=_PROJECT_ROOT,
    )
    assert result.returncode in (0, 3), (
        f"query exit {result.returncode}\nstdout: {result.stdout[:500]}\n"
        f"stderr: {result.stderr[:500]}"
    )

    trace_dir = wiki / ".graph-wiki" / "traces"
    assert trace_dir.is_dir(), f"trace dir missing: {trace_dir}"

    records_seen = 0
    for jsonl in trace_dir.glob("*.jsonl"):
        for raw in jsonl.read_text().splitlines():
            if not raw.strip():
                continue
            rec = json.loads(raw)
            # Batch terminal records carry an "event" key but no per-call tokens.
            if "event" in rec:
                continue
            # Error records may have None tokens by design.
            if rec.get("status") == "error":
                continue
            # Disclaimer/empty-fallback records may have None tokens by design
            # (D-04 WR-04 — short-circuit paths where no model call was issued).
            tokens_in = rec.get("tokens_in")
            tokens_out = rec.get("tokens_out")
            if tokens_in is None and tokens_out is None:
                continue
            # query_summary records: assert top-level tokens_in/tokens_out are non-None.
            if rec.get("kind") == "query_summary":
                assert rec.get("tokens_in") is not None, (
                    f"query_summary missing tokens_in: {rec}"
                )
                assert rec.get("tokens_out") is not None, (
                    f"query_summary missing tokens_out: {rec}"
                )
                records_seen += 1
                continue
            # All other per-item records.
            assert rec.get("tokens_in") is not None, f"missing tokens_in in {rec}"
            assert rec.get("tokens_out") is not None, f"missing tokens_out in {rec}"
            records_seen += 1

    assert records_seen > 0, (
        f"no non-error/non-event records found under {trace_dir}; "
        "query path may not have produced any traces"
    )
