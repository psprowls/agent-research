from subagent_cli.adapters.base import LoopAdapter, LoopOutcome, RunContext
from subagent_cli.runner import run_loop, stream_and_parse


def _loop_ctx(tmp_path):
    return RunContext(
        workspace=tmp_path,
        repo_root=tmp_path,
        wiki=tmp_path / "wiki",
    )


class _FakeLoopAdapter:
    name = "query_orchestrator"
    role = "query_orchestrator"
    selector = "query"

    async def run(self, ctx, item) -> LoopOutcome:
        return LoopOutcome(
            item_id=item[:80],
            role=self.role,
            model_id="",
            region="",
            answer="the answer",
            structured={"confidence": "high", "citations": ["a"], "gaps": []},
            trace_metadata={"status": "ok", "worker_batches": 1},
            latency_s=0.0,
            trace_path=None,
            note="loop note",
        )


def test_fake_adapter_satisfies_loop_protocol():
    assert isinstance(_FakeLoopAdapter(), LoopAdapter)


async def test_run_loop_overlays_model_region_latency_and_trace(tmp_path, monkeypatch):
    import subagent_cli.runner as runner_mod

    monkeypatch.setattr(
        runner_mod,
        "load_role_config",
        lambda role: {"model_id": "vendor.model-1:0", "region": "us-west-2"},
    )
    # Newest trace file under <ws>/.graph-wiki/traces should win.
    traces = tmp_path / ".graph-wiki" / "traces"
    traces.mkdir(parents=True)
    (traces / "old.jsonl").write_text("{}\n")
    newest = traces / "new.jsonl"
    newest.write_text("{}\n")
    import os
    import time as _t

    os.utime(traces / "old.jsonl", (1, 1))
    os.utime(newest, (_t.time(), _t.time()))

    ctx = _loop_ctx(tmp_path)
    outcome = await run_loop(_FakeLoopAdapter(), ctx, "what is X?")
    assert outcome.model_id == "vendor.model-1:0"
    assert outcome.region == "us-west-2"
    assert outcome.answer == "the answer"
    assert outcome.latency_s >= 0.0
    assert outcome.trace_path == str(newest)
    assert outcome.note == "loop note"


async def test_run_loop_no_trace_dir_yields_none(tmp_path, monkeypatch):
    import subagent_cli.runner as runner_mod

    monkeypatch.setattr(
        runner_mod,
        "load_role_config",
        lambda role: {"model_id": "vendor.model-1:0"},
    )
    ctx = _loop_ctx(tmp_path)  # no .graph-wiki/traces
    outcome = await run_loop(_FakeLoopAdapter(), ctx, "q")
    assert outcome.trace_path is None
    assert outcome.region == "us-east-1"  # default when cfg omits region


class _Chunk:
    """Minimal stand-in for langchain AIMessageChunk supporting + accumulation."""

    def __init__(self, content, usage=None):
        self.content = content
        self.usage_metadata = usage

    def __add__(self, other):
        return _Chunk(self.content + other.content, other.usage_metadata or self.usage_metadata)


class FakeLLM:
    def __init__(self, chunks):
        self._chunks = chunks

    async def astream(self, messages):
        for c in self._chunks:
            yield c


async def test_stream_aggregates_usage_and_parses():
    chunks = [
        _Chunk("topic: "),
        _Chunk("parsing\n"),
        _Chunk("", usage={"input_tokens": 142, "output_tokens": 38}),
    ]
    seen = []
    raw, parsed, perr, tin, tout, latency, interrupted = await stream_and_parse(
        FakeLLM(chunks),
        system="s",
        human="h",
        parse=lambda text: {"len": len(text)},
        do_parse=True,
        on_chunk=seen.append,
    )
    assert raw == "topic: parsing\n"
    assert seen == ["topic: ", "parsing\n", ""]
    assert tin == 142 and tout == 38
    assert parsed == {"len": len("topic: parsing\n")} and perr is None
    assert interrupted is False and latency >= 0.0


async def test_parser_failure_is_captured_not_raised():
    def boom(_text):
        raise ValueError("bad")

    raw, parsed, perr, tin, tout, latency, interrupted = await stream_and_parse(
        FakeLLM([_Chunk("x")]), system="s", human="h", parse=boom, do_parse=True, on_chunk=lambda _t: None
    )
    assert parsed is None
    assert perr == "ValueError: bad"


async def test_no_usage_metadata_leaves_tokens_none():
    raw, parsed, perr, tin, tout, *_ = await stream_and_parse(
        FakeLLM([_Chunk("hi")]), system="s", human="h", parse=None, do_parse=False, on_chunk=lambda _t: None
    )
    assert tin is None and tout is None and parsed is None
