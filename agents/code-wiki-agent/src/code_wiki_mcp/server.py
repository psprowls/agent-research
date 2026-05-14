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


def main() -> None:
    # Be explicit about transport — do not rely on the default (RESEARCH A2).
    mcp.run(transport="stdio")


if __name__ == "__main__":
    main()
