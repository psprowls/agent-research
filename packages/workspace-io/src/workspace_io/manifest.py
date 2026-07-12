"""Read/write `.graph-wiki.yaml`. v2 only — raises on v1 format (D-14)."""

from __future__ import annotations

from pathlib import Path

import yaml

_KNOWN_PLUGIN_KEYS = {"backend_default", "backend_overrides"}
_VALID_BACKENDS = {"claude", "bedrock"}
_KNOWN_STATE_GATE_KEYS = {"enabled", "branches"}
_KNOWN_GRAPH_KEYS = {"domains", "resources", "resource_matchers"}
_KNOWN_WORKFLOW_KEYS = {"commit_strategy", "model_routing"}
_VALID_COMMIT_STRATEGIES = {"per-task", "at-end"}
_VALID_ROUTING_TIERS = {"mechanical", "standard", "frontier"}
_KNOWN_ROLE_FIELDS = {"model_id", "region", "max_tokens", "max_concurrency", "backend"}


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
    # Validate and normalise the optional [graph] block. Always returns
    # {"domains": {...}, "resources": {...}}; absent → both empty. Mirrors the
    # plugin / state_gate normalization style.
    graph = raw.get("graph")
    if graph is None:
        raw["graph"] = {"domains": {}, "resources": {}, "resource_matchers": []}
    else:
        if not isinstance(graph, dict):
            raise RuntimeError(f"{path}: 'graph' must be a mapping, got {type(graph).__name__}")
        unknown = set(graph.keys()) - _KNOWN_GRAPH_KEYS
        if unknown:
            raise RuntimeError(f"{path}: unknown keys in graph block: {sorted(unknown)}")
        domains = graph.get("domains", {}) or {}
        if not isinstance(domains, dict):
            raise RuntimeError(f"{path}: graph.domains must be a mapping, got {type(domains).__name__}")
        resources = graph.get("resources", {}) or {}
        if not isinstance(resources, dict):
            raise RuntimeError(f"{path}: graph.resources must be a mapping, got {type(resources).__name__}")
        matchers = graph.get("resource_matchers")
        if matchers is None:
            matchers = []
        if not isinstance(matchers, list):
            raise RuntimeError(f"{path}: graph.resource_matchers must be a list, got {type(matchers).__name__}")
        raw["graph"] = {"domains": domains, "resources": resources, "resource_matchers": matchers}
    # Validate and normalise the optional [workflow] block (config consolidation).
    # Always returns {"commit_strategy": str, "model_routing": dict}; absent →
    # per-task commits with routing off.
    workflow = raw.get("workflow")
    if workflow is None:
        raw["workflow"] = {"commit_strategy": "per-task", "model_routing": {}}
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
        raw["workflow"] = {"commit_strategy": commit_strategy, "model_routing": routing}
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
    graph = data.get("graph")
    if graph is not None:
        graph_payload = {}
        if graph.get("domains"):
            graph_payload["domains"] = graph["domains"]
        if graph.get("resources"):
            graph_payload["resources"] = graph["resources"]
        if graph.get("resource_matchers"):
            graph_payload["resource_matchers"] = graph["resource_matchers"]
        if graph_payload:
            payload["graph"] = graph_payload
    workflow = data.get("workflow")
    if workflow is not None:
        wf_payload = {}
        if workflow.get("commit_strategy", "per-task") != "per-task":
            wf_payload["commit_strategy"] = workflow["commit_strategy"]
        if workflow.get("model_routing"):
            wf_payload["model_routing"] = workflow["model_routing"]
        if wf_payload:
            payload["workflow"] = wf_payload
    roles = data.get("roles")
    if roles:
        payload["roles"] = roles
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


def read_graph_domains(manifest_path: Path) -> dict[str, dict]:
    """Return the `graph.domains` mapping ({domain_name: info_dict}) or {}.

    Reads the manifest and returns the normalized `graph.domains` block.
    Defaults to {} when the manifest is missing or carries no `graph` block.
    Mirrors `read_state_gate()` / `read_roles()`: a thin read-only accessor
    that does not mutate disk and does not validate per-domain field shape
    (graph_io.domains.emit owns that).
    """
    block = read(manifest_path).get("graph") or {"domains": {}}
    return block.get("domains") or {}


def read_graph_resources(manifest_path: Path) -> dict[str, dict]:
    """Return the `graph.resources` mapping ({resource_name: info_dict}) or {}.

    Reads the manifest and returns the normalized `graph.resources` block.
    Defaults to {} when the manifest is missing or carries no `graph` block.
    Mirrors `read_graph_domains()`: a thin read-only accessor that does not
    mutate disk and does not validate per-resource field shape
    (graph_io.resources.emit owns that).
    """
    block = read(manifest_path).get("graph") or {"domains": {}, "resources": {}}
    return block.get("resources") or {}


def read_graph_resource_matchers(manifest_path: Path) -> list[dict]:
    """Return the `graph.resource_matchers` list, or [] when absent.

    Mirrors read_graph_domains/read_graph_resources: a thin read-only accessor.
    The matcher rule shape is owned by graph_io.resource_matchers, not validated here.
    """
    block = read(manifest_path).get("graph") or {}
    return block.get("resource_matchers") or []
