"""Pure path accessors over a resolved workspace path, for per-item artifacts.

Callers obtain the workspace from `workspace_io.config.resolve()` and pass
`.workspace` here. These functions do no I/O — they only compose paths.
"""

from __future__ import annotations

from pathlib import Path

from workspace_io.paths import work_dir

PHASE_ORDINALS: dict[str, str] = {
    "open": "00",  # synthetic: pre-design / archive-time page rename
    "design": "01",
    "plan": "02",
    "execute": "03",
    "finish": "04",
}
# Deliberately its own map, not work_io.lifecycle_lint.VALID_PHASES — swaps
# in "open" for "done" (done is terminal and produces no new artifacts).

ARTIFACT_KINDS = frozenset({"spec", "plan", "guidance", "results"})


def work_item_dir(workspace: Path, slug: str) -> Path:
    """<workspace>/wiki/work/<slug>/ — the live per-item working directory."""
    return work_dir(workspace) / slug


def artifact_path(
    workspace: Path,
    slug: str,
    phase: str,
    artifact_kind: str | None = None,
    *,
    role: str | None = None,
    agent: str | None = None,
    ext: str,
) -> Path:
    """Compose a per-item artifact path: NN-<phase>[-<kind>][-<suffix>].<ext>.

    `phase` must be a PHASE_ORDINALS key; `artifact_kind` (when given) must be
    an ARTIFACT_KINDS member — both raise ValueError otherwise. The optional
    suffix slot is `role`, `agent`, or `<agent>-<role>` when both are given
    (callers compose the whole `agent` segment themselves, e.g.
    "subagent-explore" or "subagent-1" for sidechain transcripts).
    """
    if phase not in PHASE_ORDINALS:
        raise ValueError(f"unknown phase {phase!r}; expected one of {sorted(PHASE_ORDINALS)}")
    if artifact_kind is not None and artifact_kind not in ARTIFACT_KINDS:
        raise ValueError(f"unknown artifact_kind {artifact_kind!r}; expected one of {sorted(ARTIFACT_KINDS)}")

    parts = [PHASE_ORDINALS[phase], phase]
    if artifact_kind is not None:
        parts.append(artifact_kind)

    if agent is not None and role is not None:
        parts.append(f"{agent}-{role}")
    elif agent is not None:
        parts.append(agent)
    elif role is not None:
        parts.append(role)

    filename = "-".join(parts) + f".{ext}"
    return work_item_dir(workspace, slug) / filename


def sidechain_dir(transcript_path: Path) -> Path:
    """Where a SessionEnd hook finds this session's subagent sidechain transcripts.

    Empirically confirmed against real `~/.claude/projects/` layout (not
    officially documented): `<project-dir>/<session-id>/subagents/`, a
    sibling of the main transcript `<project-dir>/<session-id>.jsonl`.
    Contains `agent-<id>.jsonl` files plus an unused `.meta.json` sidecar
    per agent.
    """
    p = Path(transcript_path)
    return p.parent / p.stem / "subagents"
