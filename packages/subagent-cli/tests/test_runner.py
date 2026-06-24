from subagent_cli.runner import stream_and_parse


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
