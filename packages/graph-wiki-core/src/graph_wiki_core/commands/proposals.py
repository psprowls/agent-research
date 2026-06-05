"""Living Wiki — `gw wiki proposals` / `gw wiki proposal approve|reject` bodies.

Thin core wrappers over wiki_io.proposals: resolve the wiki from the workspace,
then list or flip the status of ledger notes. No LLM. The CLI owns presentation.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from wiki_io._workspace import resolve_wiki_and_repo
from wiki_io.proposals import list_proposals, set_proposal_status, split_proposal_id


@dataclass
class ProposalDecision:
    proposal_id: str
    status: str


def run_list_proposals(
    workspace_path: Path | None = None,
    status: str | None = "proposed",
    kind: str | None = None,
) -> list[dict]:
    """List ledger records, default-filtered to open (`proposed`)."""
    wiki, _repo = resolve_wiki_and_repo(workspace_path)
    return list_proposals(wiki, status=status, kind=kind)


def run_set_proposal_status(
    proposal_id: str,
    status: str,
    workspace_path: Path | None = None,
) -> ProposalDecision:
    """Flip one note's status (approve/reject). Raises ValueError on no match."""
    wiki, _repo = resolve_wiki_and_repo(workspace_path)
    kind, target_slug = split_proposal_id(proposal_id)
    if not set_proposal_status(wiki, kind, target_slug, status):
        raise ValueError(f"no proposal note found for {proposal_id!r}")
    return ProposalDecision(proposal_id=proposal_id, status=status)
