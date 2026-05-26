"""graph-wiki-mcp MCP server.

IMPORTANT: This module is consumed by stdio-based MCP hosts.
ANY byte written to stdout other than JSON-RPC frames breaks the protocol
because MCP framing is newline-delimited JSON-RPC on stdout. A single stray
``print()`` (or a library debug log routed to stdout) corrupts the stream
and every downstream MCP host sees a JSON parse error.

The :class:`_StdoutGuard` below enforces this at module-init time: it rebinds
``sys.stdout`` to a sentinel that raises ``RuntimeError`` on any non-empty
write *before* any other import runs. ``logging.basicConfig(stream=sys.stderr)``
provides the second line of defence by routing all logging output to stderr.
"""

from __future__ import annotations  # noqa: I001

import sys


# --- Stdout guard (must run before any import that might print) ---
#
# We capture the original sys.stdout BEFORE rebinding so that:
#   1. FastMCP's stdio_server can still access the raw binary stream
#      (it grabs `sys.stdout.buffer` once to build its JSON-RPC writer).
#   2. Any Python-level write through ``sys.stdout.write(...)`` — e.g. a
#      stray ``print()``, a logging StreamHandler pointed at sys.stdout,
#      or a library debug call — trips the guard with RuntimeError.
_ORIGINAL_STDOUT = sys.stdout


class _StdoutGuard:
    """Raise immediately if any non-FastMCP code writes to stdout."""

    # Expose the original binary buffer so FastMCP's stdio_server can wrap
    # the raw file descriptor (mcp 1.27.1: ``sys.stdout.buffer`` is read at
    # startup inside ``mcp.server.stdio.stdio_server``). All subsequent
    # JSON-RPC frames go through that wrapper directly, bypassing
    # ``write()`` below — which is correct: those frames are the legitimate
    # stdout traffic. ``write()`` only catches Python-level stray writes.
    buffer = _ORIGINAL_STDOUT.buffer

    def write(self, data: str) -> int:
        if data.strip():
            raise RuntimeError(f"Illegal stdout write in MCP server: {data!r}\nAll logging must go to sys.stderr.")
        return len(data)

    def flush(self) -> None:
        return None


sys.stdout = _StdoutGuard()  # type: ignore[assignment]

# All other imports come AFTER the guard is installed so any library-init
# stdout chatter (boto3, botocore, anyio, etc.) trips the guard loudly.
import logging  # noqa: E402

from pathlib import Path  # noqa: E402

from mcp.server.fastmcp import Context, FastMCP  # noqa: E402
from pydantic import BaseModel, ConfigDict, Field  # noqa: E402

from graph_wiki_agent.commands.query import QueryResult, run_query  # noqa: E402

# --- Redirect all logging to stderr ---
logging.basicConfig(
    stream=sys.stderr,
    level=logging.WARNING,
    format="%(levelname)s %(name)s: %(message)s",
)

# Defensive: silence boto3/botocore debug chatter that some versions emit
# to stdout during the first client() call (RESEARCH §"Pitfall 3").
# Harmless if these libraries are never imported.
logging.getLogger("boto3").setLevel(logging.WARNING)
logging.getLogger("botocore").setLevel(logging.WARNING)


# --- FastMCP server ---
# NOTE: mcp 1.27.1's FastMCP constructor does not accept a `version` kwarg
# (verified via inspect.signature). Only `name` is set here.
mcp = FastMCP(name="graph-wiki-mcp")


class PingInput(BaseModel):
    message: str = "ping"


class PingOutput(BaseModel):
    status: str
    echo: str


@mcp.tool(
    name="wiki_ping",
    description="Returns pong; used to verify MCP wiring is intact.",
)
def wiki_ping(input: PingInput) -> PingOutput:
    return PingOutput(status="pong", echo=input.message)


# --- wiki_query tool ---

class WikiQueryInput(BaseModel):
    model_config = ConfigDict(extra='forbid')
    query: str
    workspace_path: str = ""  # empty -> resolve from GRAPH_WIKI_WORKSPACE env var
    top_k: int = Field(default=5, ge=3, le=10)  # 3-10 range enforced (MCP-04)


class WikiQueryOutput(BaseModel):
    answer: str
    citations: list[str]
    pages_drilled: int
    search_scores: dict  # {page_path: {"bm25": float, "embed": float, "rrf": float}}


@mcp.tool(
    name="wiki_query",
    description=(
        "Query the code wiki using hybrid BM25+embedding search with parallel librarian "
        "analysis. Returns an answer with [[wikilink]] citations. "
        "workspace_path defaults to GRAPH_WIKI_WORKSPACE env var."
    ),
)
async def wiki_query(input: WikiQueryInput, ctx: Context) -> WikiQueryOutput:
    vault = Path(input.workspace_path) if input.workspace_path else None
    await ctx.report_progress(progress=0, total=input.top_k, message="Starting hybrid search")
    result: QueryResult = await run_query(
        query=input.query,
        workspace_path=vault,
        top_k=input.top_k,
    )
    await ctx.report_progress(
        progress=result.pages_drilled,
        total=input.top_k,
        message=f"Synthesized from {result.pages_drilled} pages",
    )
    return WikiQueryOutput(
        answer=result.answer,
        citations=result.citations,
        pages_drilled=result.pages_drilled,
        search_scores=result.search_scores,
    )


# --- wiki_log tool ---

from graph_wiki_agent.commands.log import LogResult, run_log  # noqa: E402


class WikiLogInput(BaseModel):
    model_config = ConfigDict(extra='forbid')
    op: str = Field(..., description="Log operation type (scan/ingest/lint/create/update/delete/note/query)")
    title: str = Field(..., description="Short title for the log entry")
    detail: str | None = Field(None, description="Optional extended detail")
    workspace_path: str = Field("", description="Workspace path (default: GRAPH_WIKI_WORKSPACE env var)")


class WikiLogOutput(BaseModel):
    status: str
    log_path: str
    date: str
    op: str
    title: str
    header: str
    detail: str | None = None


@mcp.tool(name="wiki_log", description="Append a timestamped event to log.md.")
async def wiki_log(input: WikiLogInput, ctx: Context) -> WikiLogOutput:
    vault = Path(input.workspace_path) if input.workspace_path else None
    result: LogResult = await run_log(
        op=input.op,
        title=input.title,
        detail=input.detail,
        workspace_path=vault,
    )
    return WikiLogOutput(
        status=result.status,
        log_path=result.log_path,
        date=result.date,
        op=result.op,
        title=result.title,
        header=result.header,
        detail=result.detail,
    )


# --- wiki_bootstrap tool ---

from graph_wiki_agent.commands.init import InitResult, run_init  # noqa: E402


class WikiBootstrapInput(BaseModel):
    model_config = ConfigDict(extra='forbid')
    topic: str = Field(..., description="Short description of the repository")
    tool: str = Field(..., description="Schema file(s) to install (claude-code, codex, cursor, all, ...)")
    force: bool = Field(False, description="Overwrite non-empty target directory")
    workspace_path: str = Field("", description="Workspace path (default: GRAPH_WIKI_WORKSPACE env var)")


class WikiBootstrapOutput(BaseModel):
    status: str
    wiki_path: str
    repo_path: str
    topic: str
    tool: str
    date: str
    installed_files: list
    page_templates_copied: int
    layers: dict
    raw_path: str
    work_path: str


@mcp.tool(name="wiki_bootstrap", description="Bootstrap a wiki vault structure.")
async def wiki_bootstrap(input: WikiBootstrapInput, ctx: Context) -> WikiBootstrapOutput:
    vault = Path(input.workspace_path) if input.workspace_path else None
    result: InitResult = await run_init(
        topic=input.topic,
        tool=input.tool,
        force=input.force,
        workspace_path=vault,
    )
    return WikiBootstrapOutput(
        status=result.status,
        wiki_path=result.wiki_path,
        repo_path=result.repo_path,
        topic=result.topic,
        tool=result.tool,
        date=result.date,
        installed_files=result.installed_files,
        page_templates_copied=result.page_templates_copied,
        layers=result.layers,
        raw_path=result.raw_path,
        work_path=result.work_path,
    )


# --- wiki_scan tool ---

from graph_wiki_agent.commands.scan import ScanResult, run_scan  # noqa: E402


class WikiScanInput(BaseModel):
    model_config = ConfigDict(extra='forbid')
    workspace_path: str = Field("", description="Workspace path (default: GRAPH_WIKI_WORKSPACE env var)")
    no_file_map: bool = Field(False, description="Skip per-package file-map generation")
    max_depth: int = Field(3, description="Max directory depth for file map headers")
    repo_path: str = Field(
        "",
        description="Override repo root for scanner (default: resolved from workspace_path). Use for testing.",
    )


class WikiScanOutput(BaseModel):
    added: list[str]
    updated: list[str]
    deleted: list[str]
    renamed: list[list[str]]
    errors: list[str]
    state_gate: dict


@mcp.tool(
    name="wiki_scan",
    description="Walk repo, diff packages vs vault, create/update stubs via scanner fan-out.",
)
async def wiki_scan(input: WikiScanInput, ctx: Context) -> WikiScanOutput:
    vault = Path(input.workspace_path) if input.workspace_path else None
    await ctx.report_progress(progress=0, total=2, message="Starting scan")
    result: ScanResult = await run_scan(
        workspace_path=vault,
        no_file_map=input.no_file_map,
        max_depth=input.max_depth,
        repo_path=Path(input.repo_path).resolve() if input.repo_path else None,
    )
    added = len(result.added)
    updated = len(result.updated)
    deleted = len(result.deleted)
    await ctx.report_progress(
        progress=2,
        total=2,
        message=f"Scan complete: +{added} ~{updated} -{deleted}",
    )
    return WikiScanOutput(
        added=result.added,
        updated=result.updated,
        deleted=result.deleted,
        renamed=result.renamed,
        errors=result.errors,
        state_gate=result.state_gate,
    )


# --- wiki_ingest tool ---

from typing import Literal  # noqa: E402

from graph_wiki_agent.commands.ingest import IngestResult, run_ingest_source, run_ingest_work_item  # noqa: E402


class WikiIngestInput(BaseModel):
    model_config = ConfigDict(extra='forbid')
    type: Literal["source", "work-item"] = Field(
        ..., description="Ingest type: 'source' for files, 'work-item' for structured tickets"
    )
    source_path: str = Field("", description="Path to source file (required when type='source')")
    frontmatter: str = Field("", description="YAML frontmatter string (required when type='work-item')")
    body: str = Field("", description="Markdown body text (required when type='work-item')")
    slug: str | None = Field(None, description="Page slug (derived from title if omitted)")
    force: bool = Field(False, description="Overwrite existing page")
    pkg_dir: str = Field("", description="Optional vault package directory path for work sub-page linking")
    workspace_path: str = Field("", description="Workspace path (default: GRAPH_WIKI_WORKSPACE env var)")


class WikiIngestOutput(BaseModel):
    status: str
    page_path: str
    slug: str
    title: str
    page_type: str
    source_path: str
    cross_refs_updated: int
    entity_uri: str | None = None  # Phase 40: canonical entity URI (None for free-form sources)


@mcp.tool(
    name="wiki_ingest",
    description=(
        "Ingest a source file or work item into the wiki. "
        "Use type='source' to route a file through the ingestor LLM into the vault. "
        "Use type='work-item' to file a structured work ticket into <workspace>/work/. "
        "workspace_path defaults to GRAPH_WIKI_WORKSPACE env var."
    ),
)
async def wiki_ingest(input: WikiIngestInput, ctx: Context) -> WikiIngestOutput:
    vault = Path(input.workspace_path) if input.workspace_path else None
    await ctx.report_progress(progress=0, total=2, message="Starting ingest")
    try:
        if input.type == "source":
            result: IngestResult = await run_ingest_source(
                Path(input.source_path),
                vault,
            )
        else:  # work-item
            result = await run_ingest_work_item(
                frontmatter_text=input.frontmatter,
                body=input.body,
                slug=input.slug,
                force=input.force,
                pkg_dir=Path(input.pkg_dir) if input.pkg_dir else None,
                workspace_path=vault,
            )
    except (ValueError, FileExistsError) as e:
        # Surface validation errors as a structured MCP error (no stdout crash)
        raise RuntimeError(f"ingest failed: {e}") from e

    await ctx.report_progress(
        progress=2,
        total=2,
        message=f"Ingest complete: {result.page_path}",
    )
    return WikiIngestOutput(
        status=result.status,
        page_path=result.page_path,
        slug=result.slug,
        title=result.title,
        page_type=result.page_type,
        source_path=result.source_path,
        cross_refs_updated=result.cross_refs_updated,
        entity_uri=result.entity_uri,
    )


# --- wiki_lint tool ---

from graph_wiki_agent.commands.lint import LintResult, run_lint  # noqa: E402


class WikiLintInput(BaseModel):
    model_config = ConfigDict(extra='forbid')
    workspace_path: str = Field("", description="Workspace path (default: GRAPH_WIKI_WORKSPACE env var)")
    stale_days: int = Field(90, description="Days before a page is flagged as stale")
    log_gap_days: int = Field(14, description="Days before a log gap is flagged")


class WikiLintOutput(BaseModel):
    wiki: str
    total_pages: int
    orphans: list[str]
    broken_links: list[list[str]]  # tuples serialized as lists
    stale: list[list[str]]  # tuples serialized as lists
    missing_frontmatter: list[str]
    duplicate_titles: dict
    log_gap: dict | None
    code_drift: dict
    container_drift: list[str]
    source_sync_drift: list[str]
    file_map_drift: list[str]
    package_sync_drift: list[str]
    domain_placement: list[str]
    workflow_hints: list[str]
    dependency_layer: list[str] | None
    semantic_findings: dict
    errors: list[str]


@mcp.tool(
    name="wiki_lint",
    description="Run mechanical + semantic lint pass over the wiki.",
)
async def wiki_lint(input: WikiLintInput, ctx: Context) -> WikiLintOutput:
    vault = Path(input.workspace_path) if input.workspace_path else None
    await ctx.report_progress(progress=0, total=2, message="Starting lint")
    result: LintResult = await run_lint(
        workspace_path=vault,
        stale_days=input.stale_days,
        log_gap_days=input.log_gap_days,
    )
    n_mech = len(result.broken_links) + len(result.orphans) + len(result.missing_frontmatter)
    n_sem = sum(len(v) for v in result.semantic_findings.values())
    await ctx.report_progress(
        progress=2,
        total=2,
        message=f"Lint complete: {n_mech} mechanical + {n_sem} semantic findings",
    )
    return WikiLintOutput(
        wiki=result.wiki,
        total_pages=result.total_pages,
        orphans=result.orphans,
        broken_links=[list(pair) for pair in result.broken_links],
        stale=[list(pair) for pair in result.stale],
        missing_frontmatter=result.missing_frontmatter,
        duplicate_titles=result.duplicate_titles,
        log_gap=result.log_gap,
        code_drift=result.code_drift,
        container_drift=result.container_drift,
        source_sync_drift=result.source_sync_drift,
        file_map_drift=result.file_map_drift,
        package_sync_drift=result.package_sync_drift,
        domain_placement=result.domain_placement,
        workflow_hints=result.workflow_hints,
        dependency_layer=result.dependency_layer,
        semantic_findings=result.semantic_findings,
        errors=result.errors,
    )


# ---------------------------------------------------------------------------
# graph_build, graph_describe, graph_query tools (Phase 38 / GRAPHCMD-04)
# ---------------------------------------------------------------------------

import time  # noqa: E402

from graph_wiki_agent.commands import graph as graph_module  # noqa: E402


class GraphBuildInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    full: bool = Field(False, description="Full rebuild from scratch (else incremental).")
    trace: bool = Field(False, description="Write JSONL trace to .graph-wiki/traces/.")
    model: str | None = Field(
        None,
        description="Model ID — recorded in trace; NOT invoked in v1.7 (graph build does not call an LLM).",
    )
    workspace_path: str = Field("", description="Workspace path (default: GRAPH_WIKI_WORKSPACE env var).")


class GraphDescribeInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    kind: Literal[
        "package", "path", "repository", "domain", "entry_point", "test_suite"
    ] = Field(..., description="Entity kind (snake_case enum).")
    identifier: str | None = Field(
        None,
        description="Identifier (e.g. package name, file path). Required for all kinds except 'repository'.",
    )
    trace: bool = Field(False, description="Write JSONL trace to .graph-wiki/traces/.")
    workspace_path: str = Field("", description="Workspace path (default: GRAPH_WIKI_WORKSPACE env var).")


class GraphQueryInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    name: str | None = Field(None, description="Node name (exact match).")
    kind: str | None = Field(None, description="Node kind (e.g. class, function, file).")
    in_package: str | None = Field(None, description="Filter to nodes in named package.")
    trace: bool = Field(False, description="Write JSONL trace to .graph-wiki/traces/.")
    workspace_path: str = Field("", description="Workspace path (default: GRAPH_WIKI_WORKSPACE env var).")


class GraphCommandOutput(BaseModel):
    status: Literal["success", "error"]
    exit_code: int
    stdout: str
    stderr: str
    trace_path: str | None = None


def _pack_output(
    exit_code: int, stdout: str, stderr: str, trace_path: str | None
) -> GraphCommandOutput:
    return GraphCommandOutput(
        status="success" if exit_code == 0 else "error",
        exit_code=exit_code,
        stdout=stdout,
        stderr=stderr,
        trace_path=trace_path,
    )


@mcp.tool(
    name="graph_build",
    description="Build the code graph (cg update) for the workspace. Mirrors `graph-wiki-agent graph build`.",
)
async def graph_build(input: GraphBuildInput, ctx: Context) -> GraphCommandOutput:
    repo, workspace = graph_module._resolve_paths(input.workspace_path)
    trace_file = None
    trace_path_str: str | None = None
    if input.trace:
        shared_stamp = graph_module._iso_utc_timestamp()
        trace_file = graph_module._trace_path(workspace, "graph-build", shared_stamp)
        trace_path_str = str(trace_file.resolve())
        graph_module._write_trace_record(
            trace_file,
            event="graph_build_start",
            command="graph build",
            args_dict={"full": input.full, "model": input.model},
            exit_code=None,
            duration_ms=0,
            model_id=input.model,
        )

    args = graph_module._build_namespace(
        graph_module.ops_update,
        repo=repo,
        workspace=workspace,
        full=input.full,
    )
    t0 = time.monotonic()
    exit_code, stdout, stderr = graph_module._capture_run(graph_module.ops_update, args)
    dur_ms = int((time.monotonic() - t0) * 1000)

    if trace_file is not None:
        graph_module._write_trace_record(
            trace_file,
            event="graph_build_complete",
            command="graph build",
            args_dict={"full": input.full, "model": input.model},
            exit_code=exit_code,
            duration_ms=dur_ms,
            model_id=input.model,
        )

    return _pack_output(exit_code, stdout, stderr, trace_path_str)


@mcp.tool(
    name="graph_describe",
    description="Describe a graph entity by kind and identifier. Mirrors `graph-wiki-agent graph describe <kind>`.",
)
async def graph_describe(input: GraphDescribeInput, ctx: Context) -> GraphCommandOutput:
    module, id_attr = graph_module._DESCRIBE_DISPATCH[input.kind]
    if id_attr is not None and input.identifier is None:
        return _pack_output(
            exit_code=2,
            stdout="",
            stderr=f"identifier required for kind={input.kind}",
            trace_path=None,
        )

    repo, workspace = graph_module._resolve_paths(input.workspace_path)
    extras: dict = {} if id_attr is None else {id_attr: input.identifier}

    trace_file = None
    trace_path_str: str | None = None
    if input.trace:
        shared_stamp = graph_module._iso_utc_timestamp()
        trace_file = graph_module._trace_path(workspace, "graph-describe", shared_stamp)
        trace_path_str = str(trace_file.resolve())

    args = graph_module._build_namespace(module, repo=repo, workspace=workspace, **extras)
    t0 = time.monotonic()
    exit_code, stdout, stderr = graph_module._capture_run(module, args)
    dur_ms = int((time.monotonic() - t0) * 1000)

    if trace_file is not None:
        graph_module._write_trace_record(
            trace_file,
            event="graph_describe",
            command=f"graph describe {input.kind.replace('_', '-')}",
            args_dict={"kind": input.kind, "identifier": input.identifier},
            exit_code=exit_code,
            duration_ms=dur_ms,
            model_id=None,  # D-03 honest-omission: cost fields absent on proxy commands
        )

    return _pack_output(exit_code, stdout, stderr, trace_path_str)


@mcp.tool(
    name="graph_query",
    description="Find graph nodes by name/kind/in-package. Mirrors `graph-wiki-agent graph query` (= `cg find`).",
)
async def graph_query(input: GraphQueryInput, ctx: Context) -> GraphCommandOutput:
    if input.name is None and input.kind is None and input.in_package is None:
        return _pack_output(
            exit_code=2,
            stdout="",
            stderr="at least one of name, kind, in_package required",
            trace_path=None,
        )

    repo, workspace = graph_module._resolve_paths(input.workspace_path)

    trace_file = None
    trace_path_str: str | None = None
    if input.trace:
        shared_stamp = graph_module._iso_utc_timestamp()
        trace_file = graph_module._trace_path(workspace, "graph-query", shared_stamp)
        trace_path_str = str(trace_file.resolve())

    args = graph_module._build_namespace(
        graph_module.q_find,
        repo=repo,
        workspace=workspace,
        name=input.name,
        kind=input.kind,
        in_package=input.in_package,
    )
    t0 = time.monotonic()
    exit_code, stdout, stderr = graph_module._capture_run(graph_module.q_find, args)
    dur_ms = int((time.monotonic() - t0) * 1000)

    if trace_file is not None:
        graph_module._write_trace_record(
            trace_file,
            event="graph_query",
            command="graph query",
            args_dict={"name": input.name, "kind": input.kind, "in_package": input.in_package},
            exit_code=exit_code,
            duration_ms=dur_ms,
            model_id=None,  # D-03 honest-omission
        )

    return _pack_output(exit_code, stdout, stderr, trace_path_str)


def main() -> None:
    # Be explicit about transport — do not rely on the default (RESEARCH A2).
    mcp.run(transport="stdio")


if __name__ == "__main__":
    main()
