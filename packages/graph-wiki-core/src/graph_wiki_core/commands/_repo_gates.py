# packages/graph-wiki-core/src/graph_wiki_core/commands/_repo_gates.py
"""Multi-repo state-gate and checkout-path helpers for the scan/drift commands.

Relocated from wiki_io.scan_monorepo (mechanical decoupling, 2026-07): these
functions belong in core because core orchestrates the io packages, whereas
wiki-io must not depend on graph-io. They import wiki_io.index_generator's
_parse_repo_key, which is the sanctioned core -> wiki-io direction.
"""

from __future__ import annotations

from pathlib import Path

from graph_io.repo_context import repo_context
from graph_io.uri import repo_uri
from wiki_io.index_generator import _parse_repo_key
from wiki_io.scan_monorepo import compute_state_gate


def compute_state_gates(members: list[Path], workspace: Path | None = None) -> dict[str, dict]:
    """Per-member state-gate map keyed by ``'{org}/{repo}'``.

    Each value is the dict returned by ``compute_state_gate(member, workspace)``
    (``{allowed, reason, head_commit}``) — one HEAD per member. Members whose URI
    yields no repo key (``_parse_repo_key`` returns None) are skipped.

    Single-repo callers can keep using ``compute_state_gate`` directly; this is
    the multi-repo building block consumed by the per-repo narrative/drift gating.
    """
    gates: dict[str, dict] = {}
    for member in members:
        ctx = repo_context(Path(member))
        key = _parse_repo_key(repo_uri(ctx))
        if key is None:
            continue
        gates[key] = compute_state_gate(Path(member), workspace=workspace)
    return gates


def build_repo_paths(members: list[Path]) -> dict[str, Path]:
    """Per-member checkout-path map keyed by ``'{org}/{repo}'``.

    The companion to ``compute_state_gates``: where that maps each member to its
    state gate (HEAD/allowed), this maps each member to its checkout ``Path`` so
    per-entity dirty diffs and drift gating can run ``changed_files_since``
    against the OWNING member repo. Members whose URI yields no repo key
    (``_parse_repo_key`` returns None) are skipped. Empty for single-repo.
    """
    repo_paths: dict[str, Path] = {}
    for member in members:
        key = _parse_repo_key(repo_uri(repo_context(Path(member))))
        if key is None:
            continue
        repo_paths[key] = Path(member)
    return repo_paths


def owning_repo(uri: str, repo: Path, repo_paths: dict[str, Path]) -> Path:
    """The member checkout that owns this entity URI; `repo` when not multi-repo.

    Resolves the ``'{org}/{repo}'`` key from the URI (``_parse_repo_key``) against
    ``repo_paths`` (the ``build_repo_paths`` map). Empty ``repo_paths`` (single-repo)
    or no key match falls back to the single-repo ``repo``. Shared by the scan
    front-half and the M4 drift producer for per-entity repo routing.
    """
    if repo_paths:
        key = _parse_repo_key(uri or "")
        if key and key in repo_paths:
            return repo_paths[key]
    return repo
