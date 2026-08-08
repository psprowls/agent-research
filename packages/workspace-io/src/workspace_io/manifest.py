"""Read/write `.graph-wiki.yaml`. v2 only — raises on v1 format (D-14)."""

from __future__ import annotations

from pathlib import Path

import yaml

_KNOWN_PLUGIN_KEYS = {"backend_default", "backend_overrides"}
_VALID_BACKENDS = {"claude", "bedrock"}
_KNOWN_STATE_GATE_KEYS = {"enabled", "branches"}
_KNOWN_GUIDANCE_KEYS = {"enabled"}
_KNOWN_WORKFLOW_KEYS = {"commit_strategy", "model_routing", "auto_drive"}
_VALID_COMMIT_STRATEGIES = {"per-task", "at-end"}
_VALID_ROUTING_TIERS = {"mechanical", "standard", "frontier"}
_KNOWN_AUTO_DRIVE_KEYS = {"max_parallel", "permission_mode", "models", "overrides"}
# Hard-coded here on the _VALID_ROUTING_TIERS precedent — workspace-io cannot
# import work-io's enums; kind/effort membership is validated in work_io.auto_drive.
_VALID_AUTO_DRIVE_PHASES = {"design", "plan", "execute", "finish"}
_KNOWN_OVERRIDE_KEYS = {"match", "model", "reasoning_effort"}
_VALID_MATCH_KEYS = {"phase", "kind", "effort"}
_VALID_REASONING_EFFORTS = {"low", "medium", "high", "xhigh", "max"}
_KNOWN_ROLE_FIELDS = {"model_id", "region", "max_tokens", "max_concurrency", "backend"}

#: Hand-edited link-file keys (repo_directory / multi-repo member config). Not
#: validated or normalized by read() — write() passes them through verbatim so
#: a bootstrap re-run or `gw config set` doesn't erase hand-edited config.
#: workspace_io.registry re-exports this for its own writable-key guard.
LINK_FILE_KEYS = frozenset({"repo-directory", "multi-repo", "repos-root", "repos", "exclude"})


def read(path: Path) -> dict:
    """Read `.graph-wiki.yaml`. Returns v2 dict; does NOT rewrite disk.

    Raises RuntimeError on v1 format (version < 2).
    """
    if not path.exists():
        return {}
    raw = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    if raw.get("version", 1) < 2:
        raise RuntimeError(
            f"{path}: manifest version {raw.get('version', 1)} is not supported. "
            "Edit the file and set version: 2 (see README for schema)."
        )
    # PyYAML parses bare dates (e.g. 2026-05-09) as datetime.date; normalize to str.
    if "initialized_at" in raw:
        raw["initialized_at"] = str(raw["initialized_at"])
    # Validate and normalise the optional [plugin] block (D-02 / SO-03).
    plugin = raw.get("plugin")
    if plugin is None:
        raw["plugin"] = {"backend_default": "claude", "backend_overrides": {}}
    else:
        if not isinstance(plugin, dict):
            raise RuntimeError(f"{path}: 'plugin' must be a mapping, got {type(plugin).__name__}")
        unknown = set(plugin.keys()) - _KNOWN_PLUGIN_KEYS
        if unknown:
            raise RuntimeError(f"{path}: unknown keys in plugin block: {sorted(unknown)}")
        backend_default = plugin.get("backend_default", "claude")
        if backend_default not in _VALID_BACKENDS:
            raise RuntimeError(
                f"{path}: plugin.backend_default must be one of {sorted(_VALID_BACKENDS)}, got {backend_default!r}"
            )
        overrides = plugin.get("backend_overrides", {}) or {}
        if not isinstance(overrides, dict):
            raise RuntimeError(f"{path}: plugin.backend_overrides must be a mapping")
        for cmd, val in overrides.items():
            if val not in _VALID_BACKENDS:
                raise RuntimeError(
                    f"{path}: plugin.backend_overrides[{cmd!r}] must be one of {sorted(_VALID_BACKENDS)}, got {val!r}"
                )
        plugin["backend_default"] = backend_default
        plugin["backend_overrides"] = overrides
        raw["plugin"] = plugin
    # Validate and normalise the optional [state_gate] block. Always returns
    # {"enabled": bool, "branches": [str, ...]}; defaults to the historical
    # behavior (gate on a clean `main`) when the block is absent.
    state_gate = raw.get("state_gate")
    if state_gate is None:
        raw["state_gate"] = {"enabled": True, "branches": ["main"]}
    else:
        if not isinstance(state_gate, dict):
            raise RuntimeError(f"{path}: 'state_gate' must be a mapping, got {type(state_gate).__name__}")
        unknown = set(state_gate.keys()) - _KNOWN_STATE_GATE_KEYS
        if unknown:
            raise RuntimeError(f"{path}: unknown keys in state_gate block: {sorted(unknown)}")
        enabled = state_gate.get("enabled", True)
        if not isinstance(enabled, bool):
            raise RuntimeError(f"{path}: state_gate.enabled must be a bool, got {type(enabled).__name__}")
        branches = state_gate.get("branches", ["main"])
        if isinstance(branches, str):
            branches = [branches]
        if not isinstance(branches, list) or not branches:
            raise RuntimeError(f"{path}: state_gate.branches must be a non-empty list of branch names")
        if not all(isinstance(b, str) for b in branches):
            raise RuntimeError(f"{path}: state_gate.branches must contain only strings")
        raw["state_gate"] = {"enabled": enabled, "branches": branches}
    # Validate and normalise the optional [guidance] block. Always returns
    # {"enabled": bool}; defaults to disabled when absent — guidance is opt-in,
    # deliberately unlike state_gate (which defaults on).
    guidance = raw.get("guidance")
    if guidance is None:
        raw["guidance"] = {"enabled": False}
    else:
        if not isinstance(guidance, dict):
            raise RuntimeError(f"{path}: 'guidance' must be a mapping, got {type(guidance).__name__}")
        unknown = set(guidance.keys()) - _KNOWN_GUIDANCE_KEYS
        if unknown:
            raise RuntimeError(f"{path}: unknown keys in guidance block: {sorted(unknown)}")
        enabled = guidance.get("enabled", False)
        if not isinstance(enabled, bool):
            raise RuntimeError(f"{path}: guidance.enabled must be a bool, got {type(enabled).__name__}")
        raw["guidance"] = {"enabled": enabled}
    # Validate and normalise the optional [workflow] block (config consolidation).
    # Always returns {"commit_strategy": str, "model_routing": dict, "auto_drive": dict}; absent →
    # per-task commits, routing off, auto-drive defaults.
    workflow = raw.get("workflow")
    if workflow is None:
        raw["workflow"] = {"commit_strategy": "per-task", "model_routing": {}, "auto_drive": {}}
    else:
        if not isinstance(workflow, dict):
            raise RuntimeError(f"{path}: 'workflow' must be a mapping, got {type(workflow).__name__}")
        unknown = set(workflow.keys()) - _KNOWN_WORKFLOW_KEYS
        if unknown:
            raise RuntimeError(f"{path}: unknown keys in workflow block: {sorted(unknown)}")
        commit_strategy = workflow.get("commit_strategy", "per-task")
        if commit_strategy not in _VALID_COMMIT_STRATEGIES:
            raise RuntimeError(
                f"{path}: workflow.commit_strategy must be one of "
                f"{sorted(_VALID_COMMIT_STRATEGIES)}, got {commit_strategy!r}"
            )
        routing = workflow.get("model_routing", {}) or {}
        if not isinstance(routing, dict):
            raise RuntimeError(f"{path}: workflow.model_routing must be a mapping")
        unknown_tiers = set(routing.keys()) - _VALID_ROUTING_TIERS
        if unknown_tiers:
            raise RuntimeError(
                f"{path}: unknown tiers in workflow.model_routing: {sorted(unknown_tiers)} "
                f"(valid: {sorted(_VALID_ROUTING_TIERS)})"
            )
        for tier, val in routing.items():
            if not isinstance(val, str) or not val.strip():
                raise RuntimeError(f"{path}: workflow.model_routing[{tier!r}] must be a non-empty string")
        auto_drive = _validate_auto_drive(path, workflow.get("auto_drive", {}))
        raw["workflow"] = {
            "commit_strategy": commit_strategy,
            "model_routing": routing,
            "auto_drive": auto_drive,
        }
    # Validate and normalise the optional top-level [roles] mapping (flattened
    # from plugins[].roles[] — schema change, no migration per pre-v2 rule).
    roles = raw.get("roles")
    if roles is None:
        raw["roles"] = {}
    else:
        if not isinstance(roles, dict):
            raise RuntimeError(f"{path}: 'roles' must be a mapping, got {type(roles).__name__}")
        for name, fields in roles.items():
            if not isinstance(fields, dict):
                raise RuntimeError(f"{path}: roles[{name!r}] must be a mapping")
            unknown_fields = set(fields.keys()) - _KNOWN_ROLE_FIELDS
            if unknown_fields:
                raise RuntimeError(
                    f"{path}: unknown fields in roles[{name!r}]: {sorted(unknown_fields)} "
                    f"(valid: {sorted(_KNOWN_ROLE_FIELDS)})"
                )
    return raw


def _validate_auto_drive(path: Path, auto_drive: object) -> dict:
    """Structural validation of workflow.auto_drive — types and shapes only.

    Kind/effort (and match-phase) enum membership lives in
    work_io.auto_drive.validate_auto_drive; this layer cannot import work-io.
    """
    auto_drive = auto_drive or {}
    if not isinstance(auto_drive, dict):
        raise RuntimeError(f"{path}: workflow.auto_drive must be a mapping")
    unknown = set(auto_drive.keys()) - _KNOWN_AUTO_DRIVE_KEYS
    if unknown:
        raise RuntimeError(
            f"{path}: unknown keys in workflow.auto_drive: {sorted(unknown)} (valid: {sorted(_KNOWN_AUTO_DRIVE_KEYS)})"
        )
    if "max_parallel" in auto_drive:
        mp = auto_drive["max_parallel"]
        # bool is an int subclass; `max_parallel: true` is a config error, not 1.
        if isinstance(mp, bool) or not isinstance(mp, int) or mp < 1:
            raise RuntimeError(f"{path}: workflow.auto_drive.max_parallel must be an integer >= 1, got {mp!r}")
    if "permission_mode" in auto_drive:
        pm = auto_drive["permission_mode"]
        if not isinstance(pm, str) or not pm.strip():
            raise RuntimeError(f"{path}: workflow.auto_drive.permission_mode must be a non-empty string")
    if "models" in auto_drive:
        models = auto_drive["models"]
        if not isinstance(models, dict):
            raise RuntimeError(f"{path}: workflow.auto_drive.models must be a mapping")
        unknown_phases = set(models.keys()) - _VALID_AUTO_DRIVE_PHASES
        if unknown_phases:
            raise RuntimeError(
                f"{path}: unknown phases in workflow.auto_drive.models: {sorted(unknown_phases)} "
                f"(valid: {sorted(_VALID_AUTO_DRIVE_PHASES)})"
            )
        for phase, val in models.items():
            if not isinstance(val, str) or not val.strip():
                raise RuntimeError(f"{path}: workflow.auto_drive.models[{phase!r}] must be a non-empty string")
    if "overrides" in auto_drive:
        overrides = auto_drive["overrides"]
        if not isinstance(overrides, list):
            raise RuntimeError(f"{path}: workflow.auto_drive.overrides must be a list")
        for i, rule in enumerate(overrides):
            where = f"workflow.auto_drive.overrides[{i}]"
            if not isinstance(rule, dict):
                raise RuntimeError(f"{path}: {where} must be a mapping")
            unknown_rule = set(rule.keys()) - _KNOWN_OVERRIDE_KEYS
            if unknown_rule:
                raise RuntimeError(
                    f"{path}: unknown keys in {where}: {sorted(unknown_rule)} (valid: {sorted(_KNOWN_OVERRIDE_KEYS)})"
                )
            if "match" not in rule or "model" not in rule:
                raise RuntimeError(f"{path}: {where} requires both 'match' and 'model'")
            match = rule["match"]
            if not isinstance(match, dict) or not match:
                raise RuntimeError(f"{path}: {where}.match must be a non-empty mapping")
            unknown_match = set(match.keys()) - _VALID_MATCH_KEYS
            if unknown_match:
                raise RuntimeError(
                    f"{path}: unknown keys in {where}.match: {sorted(unknown_match)} "
                    f"(valid: {sorted(_VALID_MATCH_KEYS)})"
                )
            for mkey, mval in match.items():
                vals = mval if isinstance(mval, list) else [mval]
                if not vals or not all(isinstance(v, str) and v.strip() for v in vals):
                    raise RuntimeError(
                        f"{path}: {where}.match[{mkey!r}] must be a non-empty string "
                        "or non-empty list of non-empty strings"
                    )
            model = rule["model"]
            if not isinstance(model, str) or not model.strip():
                raise RuntimeError(f"{path}: {where}.model must be a non-empty string")
            if "reasoning_effort" in rule and rule["reasoning_effort"] not in _VALID_REASONING_EFFORTS:
                raise RuntimeError(
                    f"{path}: {where}.reasoning_effort must be one of "
                    f"{sorted(_VALID_REASONING_EFFORTS)}, got {rule['reasoning_effort']!r}"
                )
    return auto_drive


def write(path: Path, data: dict) -> None:
    """Write v2 manifest. Creates parent dirs.

    `plugins[]` entries keep only name/version provenance — role config lives
    in the top-level `roles:` mapping (see below), never nested under a plugin.
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    plugins_payload = []
    for p in data.get("plugins", []):
        entry = {
            "name": p["name"],
            "installed_version": p.get("installed_version"),
            "applied_version": p.get("applied_version"),
        }
        plugins_payload.append(entry)
    payload = {
        "version": 2,
        "initialized_at": str(data.get("initialized_at", "") or ""),
    }
    # Wiki display name. Optional — only emitted when set, so manifests for
    # workspaces bootstrapped before this key existed stay topic-free.
    topic = data.get("topic")
    if topic:
        payload["topic"] = str(topic)
    payload["plugins"] = plugins_payload
    # Round-trip optional blocks using the same omit-when-absent-or-default
    # pattern as `topic` above. Guards prevent writing default-valued blocks
    # that read() would re-inject anyway (avoids disk churn on vanilla manifests).
    plugin = data.get("plugin")
    if plugin is not None:
        if plugin.get("backend_default", "claude") != "claude" or plugin.get("backend_overrides"):
            payload["plugin"] = plugin
    state_gate = data.get("state_gate")
    if state_gate is not None:
        if state_gate.get("enabled", True) is not True or state_gate.get("branches", ["main"]) != ["main"]:
            payload["state_gate"] = state_gate
    guidance = data.get("guidance")
    if guidance is not None:
        # Only `enabled: true` is worth persisting — False is the default and
        # read() re-injects it, so writing it would be pure churn.
        if guidance.get("enabled", False) is True:
            payload["guidance"] = guidance
    workflow = data.get("workflow")
    if workflow is not None:
        wf_payload = {}
        if workflow.get("commit_strategy", "per-task") != "per-task":
            wf_payload["commit_strategy"] = workflow["commit_strategy"]
        if workflow.get("model_routing"):
            wf_payload["model_routing"] = workflow["model_routing"]
        if workflow.get("auto_drive"):
            wf_payload["auto_drive"] = workflow["auto_drive"]
        if wf_payload:
            payload["workflow"] = wf_payload
    roles = data.get("roles")
    if roles:
        payload["roles"] = roles
    # Link-file keys are hand-edited directly into .graph-wiki.yaml (see
    # config.py's _repo_directory_override / _multi_repo_members) and aren't
    # read()-normalized, so pass them through verbatim rather than dropping
    # any not in the allowlist above.
    for key in LINK_FILE_KEYS:
        if key in data:
            payload[key] = data[key]
    path.write_text(
        yaml.safe_dump(payload, sort_keys=False, default_flow_style=False),
        encoding="utf-8",
    )


def read_roles(manifest_path: Path) -> dict[str, dict]:
    """Return the top-level `roles:` mapping ({role_name: field_dict}) or {}.

    Flattened schema: roles live at the manifest top level, not nested under
    plugins[]. Returns {} when the manifest is missing or carries no roles.

    This is a read-only accessor — does not mutate disk. Callers
    (graph_wiki_core.roles) merge with packaged defaults on a per-role basis.
    """
    return read(manifest_path).get("roles") or {}


def read_state_gate(manifest_path: Path) -> tuple[bool, list[str]]:
    """Return the (enabled, branches) state-gate config for the workspace.

    Reads the manifest and returns the normalized `state_gate` block as a typed
    tuple. Defaults to (True, ["main"]) — today's behavior — when the manifest
    is missing or carries no `state_gate` block. Mirrors `read_roles()`: a thin
    read-only accessor that does not mutate disk.
    """
    block = read(manifest_path).get("state_gate") or {"enabled": True, "branches": ["main"]}
    return block["enabled"], block["branches"]


def read_guidance(manifest_path: Path) -> bool:
    """Return whether `gw next` guidance is enabled for the workspace.

    Opt-in: defaults to False when the manifest is missing or carries no
    `guidance` block. Mirrors `read_state_gate()` — a thin read-only accessor
    that does not mutate disk.
    """
    block = read(manifest_path).get("guidance") or {"enabled": False}
    return block["enabled"]
