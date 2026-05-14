"""code-wiki-mcp MCP server.

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
from pydantic import BaseModel, Field  # noqa: E402

from code_wiki_agent.commands.query import QueryResult, run_query  # noqa: E402

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
mcp = FastMCP(name="code-wiki-mcp")


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
    query: str
    vault_path: str = ""  # empty -> resolve from CODE_WIKI_REAL_VAULT_PATH env var
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
        "vault_path defaults to CODE_WIKI_REAL_VAULT_PATH env var."
    ),
)
async def wiki_query(input: WikiQueryInput, ctx: Context) -> WikiQueryOutput:
    vault = Path(input.vault_path) if input.vault_path else None
    await ctx.report_progress(progress=0, total=input.top_k, message="Starting hybrid search")
    result: QueryResult = await run_query(
        query=input.query,
        vault_path=vault,
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

from code_wiki_agent.commands.log import LogResult, run_log  # noqa: E402


class WikiLogInput(BaseModel):
    op: str = Field(..., description="Log operation type (scan/ingest/lint/create/update/delete/note/query)")
    title: str = Field(..., description="Short title for the log entry")
    detail: str | None = Field(None, description="Optional extended detail")
    vault_path: str = Field("", description="Vault path (default: CODE_WIKI_REAL_VAULT_PATH env var)")


class WikiLogOutput(BaseModel):
    status: str
    log_path: str
    date: str
    op: str
    title: str
    header: str


@mcp.tool(name="wiki_log", description="Append a timestamped event to log.md.")
async def wiki_log(input: WikiLogInput, ctx: Context) -> WikiLogOutput:
    vault = Path(input.vault_path) if input.vault_path else None
    result: LogResult = await run_log(
        op=input.op,
        title=input.title,
        detail=input.detail,
        vault_path=vault,
    )
    return WikiLogOutput(
        status=result.status,
        log_path=result.log_path,
        date=result.date,
        op=result.op,
        title=result.title,
        header=result.header,
    )


# --- wiki_init tool ---

from code_wiki_agent.commands.init import InitResult, run_init  # noqa: E402


class WikiInitInput(BaseModel):
    topic: str = Field(..., description="Short description of the repository")
    tool: str = Field(..., description="Schema file(s) to install (claude-code, codex, cursor, all, ...)")
    force: bool = Field(False, description="Overwrite non-empty target directory")
    vault_path: str = Field("", description="Vault path (default: CODE_WIKI_REAL_VAULT_PATH env var)")


class WikiInitOutput(BaseModel):
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


@mcp.tool(name="wiki_init", description="Bootstrap a wiki vault structure.")
async def wiki_init(input: WikiInitInput, ctx: Context) -> WikiInitOutput:
    vault = Path(input.vault_path) if input.vault_path else None
    result: InitResult = await run_init(
        topic=input.topic,
        tool=input.tool,
        force=input.force,
        vault_path=vault,
    )
    return WikiInitOutput(
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

from code_wiki_agent.commands.scan import ScanResult, run_scan  # noqa: E402


class WikiScanInput(BaseModel):
    vault_path: str = Field("", description="Vault path (default: CODE_WIKI_REAL_VAULT_PATH env var)")
    no_file_map: bool = Field(False, description="Skip per-package file-map generation")
    max_depth: int = Field(3, description="Max directory depth for file map headers")


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
    vault = Path(input.vault_path) if input.vault_path else None
    await ctx.report_progress(progress=0, total=2, message="Starting scan")
    result: ScanResult = await run_scan(
        vault_path=vault,
        no_file_map=input.no_file_map,
        max_depth=input.max_depth,
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


def main() -> None:
    import os

    # Load config from env var before serving (D-13).
    config_path_str = os.environ.get("CODE_WIKI_CONFIG")
    if config_path_str:
        import code_wiki_agent.config as _cfg_module

        _cfg_module._active_config = _cfg_module.load_config(Path(config_path_str))

    # Be explicit about transport — do not rely on the default (RESEARCH A2).
    mcp.run(transport="stdio")


if __name__ == "__main__":
    main()
