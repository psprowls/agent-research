from __future__ import annotations

"""log command — append timestamped events to wiki/log.md.

Public API:
    LogResult    -- Dataclass mirroring the dict keys returned by append_log()
    run_log()    -- Async wrapper: resolves workspace, calls append_log, returns LogResult

State gate: intentionally not applied to log — log is the recording mechanism itself.
Applying a state gate to the recording mechanism would be circular (RESEARCH §log Command).
"""

import logging
from dataclasses import dataclass
from pathlib import Path

from vault_io._workspace import resolve_wiki_and_repo
from vault_io.append_log import append_log

logger = logging.getLogger(__name__)


@dataclass
class LogResult:
    """Result returned by run_log(), mirroring the dict keys from append_log()."""

    status: str
    log_path: str
    date: str
    op: str
    title: str
    header: str
    detail: str | None


async def run_log(
    op: str,
    title: str,
    detail: str | None,
    workspace_path: Path | None = None,
) -> LogResult:
    """Append a timestamped entry to the wiki log.

    Args:
        op: Log operation type (must be in VALID_OPS from append_log).
        title: Short title for the log entry.
        detail: Optional extended detail text.
        workspace_path: Explicit workspace path; if None, reads GRAPH_WIKI_WORKSPACE env var.

    Returns:
        LogResult with fields populated from append_log's return dict.

    Raises:
        RuntimeError: If the vault or log.md cannot be found/written.
        ValueError: If append_log rejects the op or cannot locate/write the log
            (raise_exception=True). The MCP boundary catches this; the stdio
            server is not terminated.
    """
    wiki, _ = resolve_wiki_and_repo(workspace_path)
    logger.debug("run_log: wiki=%s op=%s title=%r", wiki, op, title)
    result = append_log(wiki, op, title, detail, silent=True, raise_exception=True)
    return LogResult(
        status=result["status"],
        log_path=result["log_path"],
        date=result["date"],
        op=result["op"],
        title=result["title"],
        header=result["header"],
        detail=result["detail"],
    )
