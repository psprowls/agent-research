"""Pure auto-drive model resolution over the manifest's workflow.auto_drive block.

Epic child 1 (Orca auto-drive pipeline): `gw work orchestrate` (child 2) calls
resolve_model per dispatchable leaf and passes the result to the coordinator,
which never interprets the rules itself. Structural validation of the block
lives in workspace_io.manifest (this layer's input is already shape-checked);
this module owns the enum-membership check workspace-io cannot perform —
validate_auto_drive — and the resolution semantics.

Contract for child 2: `gw work orchestrate` must call validate_auto_drive at
startup and fail loudly on errors — hand-edited manifests bypass the set-time
check in gw config set.
"""

from __future__ import annotations

from dataclasses import dataclass

from work_io.lifecycle_lint import VALID_EFFORTS, VALID_KINDS, VALID_PHASES

#: Phases a stage can be dispatched at — `done` is terminal, never dispatched.
DISPATCH_PHASES = frozenset(VALID_PHASES - {"done"})


@dataclass(frozen=True)
class ModelResolution:
    """A resolved worker-session model, plus the launched agent's reasoning
    effort when an override set one (match.effort is work-item sizing; this
    is the agent knob — deliberately distinct names)."""

    model: str
    reasoning_effort: str | None = None


def _rule_matches(match: dict, *, phase: str, kind: str, effort: str | None) -> bool:
    item = {"phase": phase, "kind": kind, "effort": effort}
    for key, constraint in match.items():
        value = item[key]
        if value is None:
            # An effort constraint never matches an unsized item.
            return False
        allowed = constraint if isinstance(constraint, list) else [constraint]
        if value not in allowed:
            return False
    return True


def resolve_model(auto_drive: dict, *, phase: str, kind: str, effort: str | None) -> ModelResolution | None:
    """Resolve the worker model for one (phase, kind, effort) dispatch.

    First-match-wins over `overrides` (scalar = equality, list = membership,
    absent match key = wildcard), then the `models[phase]` default, then None —
    meaning "inherit the session model" (the coordinator omits --model).
    Assumes a structurally valid block (workspace_io.manifest guarantees that
    for manifest-sourced dicts); does not re-validate.
    """
    for rule in auto_drive.get("overrides", []):
        if _rule_matches(rule["match"], phase=phase, kind=kind, effort=effort):
            return ModelResolution(rule["model"], rule.get("reasoning_effort"))
    model = (auto_drive.get("models") or {}).get(phase)
    if model:
        return ModelResolution(model, None)
    return None


def validate_auto_drive(auto_drive: dict) -> list[str]:
    """Enum-membership check for override match values.

    The complement of workspace_io.manifest's structural validation: flags
    match values outside the work-item vocabularies (canonical names only —
    xs/s shorthand is an error, not an alias). Returns human-readable error
    strings; empty list = clean.
    """
    enums = {"phase": DISPATCH_PHASES, "kind": VALID_KINDS, "effort": VALID_EFFORTS}
    errors: list[str] = []
    for i, rule in enumerate(auto_drive.get("overrides", [])):
        for key, constraint in rule.get("match", {}).items():
            valid = enums.get(key)
            if valid is None:
                continue  # unknown match keys are a structural error, not ours
            for v in constraint if isinstance(constraint, list) else [constraint]:
                if v not in valid:
                    errors.append(f"overrides[{i}].match.{key}: {v!r} not in {sorted(valid)}")
    return errors
