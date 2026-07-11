"""tokens command — stamp `tokens: <count>` frontmatter across the wiki.

Public API:
    run_tokens_update() -- resolves workspace, counts tokens offline via
                            tiktoken, writes/dry-runs the update.

Mirrors commands/log.py's run_log() shape: a thin async-free wrapper around
an io-package primitive, so delivery surfaces (graph-wiki-cli) call this
instead of wiki_io.update_tokens / graph_io.tokens directly.
"""

from __future__ import annotations

from pathlib import Path

from graph_io.tokens import count_tokens
from wiki_io._workspace import resolve_wiki_and_repo
from wiki_io.update_tokens import update_vault


def run_tokens_update(workspace_path: Path | None = None, dry_run: bool = False) -> dict[str, list[str]]:
    """Count tokens for every wiki page and stamp (or dry-run) the `tokens:` frontmatter key.

    Args:
        workspace_path: Explicit workspace path; if None, reads GRAPH_WIKI_WORKSPACE env var.
        dry_run: Count without writing.

    Returns:
        {"updated": [...], "unchanged": [...], "skipped": [...]} — relative page paths per bucket.

    Raises:
        RuntimeError, FileNotFoundError: if the vault cannot be resolved.
    """
    wiki, _ = resolve_wiki_and_repo(workspace_path)
    return update_vault(wiki, count_tokens, dry_run=dry_run)
