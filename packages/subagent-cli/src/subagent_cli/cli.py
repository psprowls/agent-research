"""Typer CLI surface for invoking Bedrock subagents."""

from __future__ import annotations

import asyncio
import json
from pathlib import Path

import typer
from model_adapter import BedrockAccessDenied, load_role_config
from workspace_io import paths as ws_paths
from workspace_io.config import resolve

from . import render
from .adapters import ADAPTERS
from .runner import run_all, run_single

app = typer.Typer(
    name="subagents",
    help="Invoke Bedrock subagents live with colored prompt/response/model output.",
    no_args_is_help=True,
)

_SELECTOR_FLAG = {"file": "--file", "package": "--package", "query": "--query"}


@app.command(name="list")
def list_cmd(json_output: bool = typer.Option(False, "--json", help="Emit the table as a JSON array")):
    """List every supported subagent and the model it resolves to."""
    rows = []
    for name, cls in ADAPTERS.items():
        adapter = cls()
        cfg = load_role_config(adapter.role)
        rows.append(
            {
                "name": name,
                "role": adapter.role,
                "model_id": cfg["model_id"],
                "region": cfg.get("region", "us-east-1"),
                "selector": adapter.selector,
                "status": "ready",
            }
        )
    if json_output:
        typer.echo(json.dumps(rows, indent=2))
    else:
        render.configure()
        render.list_table(rows)


@app.command()
def run(
    name: str = typer.Argument(..., help="Adapter name (see `subagent list`)"),
    file: str = typer.Option("", "--file", help="File path selector (guidance_classifier)"),
    package: str = typer.Option("", "--package", help="Package name selector (package_reader)"),
    query: str = typer.Option("", "--query", help="Query text selector (query subagents)"),
    all_: bool = typer.Option(False, "--all", help="Fan out over the adapter's real worklist"),
    excerpts: str = typer.Option("", "--excerpts", help="synthesizer only: supply excerpts, skip retrieval"),
    workspace: str = typer.Option("", "--workspace", help="Workspace path (default: resolve from cwd / env)"),
    prompt_mode: str = typer.Option("full", "--prompt", help="full | short"),
    raw: bool = typer.Option(False, "--raw", help="Skip the parse step (raw response only)"),
    no_color: bool = typer.Option(False, "--no-color", help="Plain text (also honors NO_COLOR)"),
    json_output: bool = typer.Option(False, "--json", help="Emit a machine record; suppresses the stream"),
):
    """Invoke one subagent live and render its prompt, response, and parsed result."""
    render.configure(no_color=no_color or json_output)

    cls = ADAPTERS.get(name)
    if cls is None:
        render.error(f"unknown adapter '{name}'. valid names: {', '.join(sorted(ADAPTERS))}")
        raise typer.Exit(code=1)

    adapter = cls(excerpts_path=Path(excerpts)) if name == "synthesizer" and excerpts else cls()

    # Resolve the single selector value for this adapter.
    selectors = {"file": file, "package": package, "query": query}
    item = selectors[adapter.selector]
    if not all_ and not item:
        render.error(f"{name} requires {_SELECTOR_FLAG[adapter.selector]} <value>")
        raise typer.Exit(code=1)

    # Build the run context (workspace → wiki → graph DB).
    try:
        cwd = Path(workspace) if workspace else Path.cwd()
        cfg = resolve(cwd)
        ctx = _build_context(cfg.workspace, cfg.repo_root)
    except Exception as exc:  # RuntimeError on missing manifest, etc.
        render.error(str(exc))
        raise typer.Exit(code=1)

    try:
        if all_:
            _dispatch_all(adapter, ctx)
        else:
            _dispatch_single(adapter, ctx, item, raw=raw, prompt_mode=prompt_mode, json_output=json_output)
    except BedrockAccessDenied as exc:
        render.error(str(exc))
        raise typer.Exit(code=2)
    except ValueError as exc:  # e.g. --all on a single-query adapter
        render.error(str(exc))
        raise typer.Exit(code=1)
    except KeyboardInterrupt:
        raise typer.Exit(code=130)
    except (FileNotFoundError, RuntimeError) as exc:  # missing page, no retrieval, etc.
        render.error(str(exc))
        raise typer.Exit(code=1)
    finally:
        ctx.close()


def _build_context(workspace: Path, repo_root: Path):
    from .adapters.base import RunContext

    return RunContext(
        workspace=workspace,
        repo_root=repo_root,
        wiki=ws_paths.wiki_dir(workspace),
        db_path=ws_paths.graph_dir(workspace) / "code.db",
    )


def _dispatch_single(adapter, ctx, item, *, raw, prompt_mode, json_output):
    if json_output:
        outcome = asyncio.run(run_single(adapter, ctx, item, do_parse=not raw, on_chunk=lambda *_: None))
        typer.echo(json.dumps(render.json_record(outcome), indent=2))
        return

    # Stream live: header + prompt first, then response chunks, then parsed + footer.
    streamed = {"started": False}

    def on_chunk(text: str) -> None:
        if not streamed["started"]:
            render.response_start()
            streamed["started"] = True
        render.response_chunk(text)

    outcome = asyncio.run(_single_with_preface(adapter, ctx, item, raw, prompt_mode, on_chunk))
    if streamed["started"]:
        render.response_end()
    render.parsed(outcome)
    render.footer(outcome)
    if outcome.interrupted:  # Ctrl-C: partial flushed + interrupted footer shown, now exit 130
        raise typer.Exit(code=130)


async def _single_with_preface(adapter, ctx, item, raw, prompt_mode, on_chunk):
    from model_adapter import make_llm

    from .runner import RunOutcome, _cost, stream_and_parse

    cfg = load_role_config(adapter.role)
    model_id = cfg["model_id"]
    region = cfg.get("region", "us-east-1")
    prepared = await adapter.prepare(ctx, item)
    # Render header + prompt before the stream begins.
    pre = RunOutcome(
        item_id=prepared.item_id,
        role=adapter.role,
        model_id=model_id,
        region=region,
        system=prepared.system,
        human=prepared.human,
        raw="",
        parsed=None,
        parse_error=None,
        tokens_in=None,
        tokens_out=None,
        latency_s=0.0,
        cost_usd=None,
        note=prepared.note,
    )
    render.header(pre)
    render.prompt(pre, mode=prompt_mode)
    llm = make_llm(adapter.role)
    raw_text, parsed, perr, tin, tout, latency, interrupted = await stream_and_parse(
        llm,
        system=prepared.system,
        human=prepared.human,
        parse=prepared.parse,
        do_parse=not raw,
        on_chunk=on_chunk,
    )
    return RunOutcome(
        item_id=prepared.item_id,
        role=adapter.role,
        model_id=model_id,
        region=region,
        system=prepared.system,
        human=prepared.human,
        raw=raw_text,
        parsed=parsed,
        parse_error=perr,
        tokens_in=tin,
        tokens_out=tout,
        latency_s=latency,
        cost_usd=_cost(model_id, tin, tout),
        interrupted=interrupted,
        note=prepared.note,
    )


def _dispatch_all(adapter, ctx):
    from subagent_runtime.trace_io import render_trace_record

    trace_dir = ws_paths.graph_dir(ctx.workspace) / "traces"
    fan = asyncio.run(run_all(adapter, ctx, trace_dir=trace_dir))
    traces = sorted(trace_dir.glob("*.jsonl"), key=lambda p: p.stat().st_mtime)
    if traces:
        for line in traces[-1].read_text(encoding="utf-8").splitlines():
            if line.strip():
                render.trace_line(render_trace_record(json.loads(line)))
    where = traces[-1] if traces else trace_dir
    render.info(f"done: {len(fan.successes)} ok, {len(fan.errors)} error(s) · trace: {where}")
