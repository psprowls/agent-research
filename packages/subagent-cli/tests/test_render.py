import io
import json

from subagent_cli import render
from subagent_cli.runner import RunOutcome


def _outcome(**over):
    base = dict(
        item_id="packages/foo/x.py",
        role="guidance_classifier",
        model_id="openai.gpt-oss-20b-1:0",
        region="us-east-1",
        system="SYS",
        human="HUMAN BODY\nline2\nline3",
        raw="topic: parsing",
        parsed={"topics": ["parsing"], "tags": []},
        parse_error=None,
        tokens_in=142,
        tokens_out=38,
        latency_s=1.24,
        cost_usd=0.0003,
        interrupted=False,
        note=None,
    )
    base.update(over)
    return RunOutcome(**base)


def _plain_console():
    buf = io.StringIO()
    render.configure(no_color=True, file=buf)
    return buf


def test_no_color_output_has_no_escape_codes():
    buf = _plain_console()
    o = _outcome()
    render.header(o)
    render.prompt(o, mode="full")
    render.parsed(o)
    render.footer(o)
    text = buf.getvalue()
    assert "\x1b[" not in text  # no ANSI escapes
    assert "guidance_classifier" in text
    assert "openai.gpt-oss-20b-1:0" in text
    assert "PARSED" in text
    assert "142" in text and "38" in text


def test_parsed_failure_marker():
    buf = _plain_console()
    o = _outcome(parsed=None, parse_error="ValueError: bad")
    render.parsed(o)
    text = buf.getvalue()
    assert "✗" in text or "PARSED" in text
    assert "ValueError: bad" in text


def test_prompt_short_mode_truncates():
    buf = _plain_console()
    o = _outcome(human="\n".join(f"line{i}" for i in range(50)))
    render.prompt(o, mode="short")
    text = buf.getvalue()
    assert "50" in text  # reports the line count
    assert "line49" not in text  # does not print the whole body


def test_json_record_schema():
    o = _outcome()
    rec = render.json_record(o)
    assert set(rec) == {
        "name",
        "role",
        "model_id",
        "region",
        "item_id",
        "system",
        "human",
        "raw",
        "parsed",
        "parse_error",
        "tokens_in",
        "tokens_out",
        "latency_s",
        "cost_usd",
        "interrupted",
        "note",
    }
    # round-trips through JSON
    assert json.loads(json.dumps(rec))["tokens_in"] == 142


def test_list_table_renders_rows():
    buf = _plain_console()
    render.list_table(
        [
            {
                "name": "librarian",
                "role": "librarian",
                "model_id": "moonshotai.kimi-k2.5",
                "region": "us-east-1",
                "selector": "query",
                "status": "ready",
            }
        ]
    )
    text = buf.getvalue()
    assert "librarian" in text and "moonshotai.kimi-k2.5" in text
