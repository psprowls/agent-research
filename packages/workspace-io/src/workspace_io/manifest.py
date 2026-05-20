"""Read/write `.graph-wiki.yaml`. v2 only — raises on v1 format (D-14)."""
from __future__ import annotations

from pathlib import Path

import yaml

_KNOWN_PLUGIN_KEYS = {"backend_default", "backend_overrides"}
_VALID_BACKENDS = {"claude", "bedrock"}


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
            raise RuntimeError(
                f"{path}: 'plugin' must be a mapping, got {type(plugin).__name__}"
            )
        unknown = set(plugin.keys()) - _KNOWN_PLUGIN_KEYS
        if unknown:
            raise RuntimeError(
                f"{path}: unknown keys in plugin block: {sorted(unknown)}"
            )
        backend_default = plugin.get("backend_default", "claude")
        if backend_default not in _VALID_BACKENDS:
            raise RuntimeError(
                f"{path}: plugin.backend_default must be one of {sorted(_VALID_BACKENDS)}, "
                f"got {backend_default!r}"
            )
        overrides = plugin.get("backend_overrides", {}) or {}
        if not isinstance(overrides, dict):
            raise RuntimeError(f"{path}: plugin.backend_overrides must be a mapping")
        for cmd, val in overrides.items():
            if val not in _VALID_BACKENDS:
                raise RuntimeError(
                    f"{path}: plugin.backend_overrides[{cmd!r}] must be one of "
                    f"{sorted(_VALID_BACKENDS)}, got {val!r}"
                )
        plugin["backend_default"] = backend_default
        plugin["backend_overrides"] = overrides
        raw["plugin"] = plugin
    return raw


def write(path: Path, data: dict) -> None:
    """Write v2 manifest. Creates parent dirs.

    Preserves per-plugin `roles[]` when present and non-empty; absent and empty
    both result in no `roles:` key on disk (avoids writing `roles: []` for plugins
    with no role overrides).
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    plugins_payload = []
    for p in data.get("plugins", []):
        entry = {
            "name": p["name"],
            "installed_version": p.get("installed_version"),
            "applied_version": p.get("applied_version"),
        }
        roles = p.get("roles")
        if roles:
            entry["roles"] = roles
        plugins_payload.append(entry)
    payload = {
        "version": 2,
        "initialized_at": str(data.get("initialized_at", "") or ""),
        "plugins": plugins_payload,
    }
    path.write_text(
        yaml.safe_dump(payload, sort_keys=False, default_flow_style=False),
        encoding="utf-8",
    )


def read_roles(plugin_name: str, manifest_path: Path) -> list[dict]:
    """Return the `roles[]` list for the named plugin, or [] when absent.

    Resolution: read the manifest, find the first plugin entry whose `name`
    matches, and return its `roles` list. Returns [] when the manifest is
    missing, the plugin is absent, or the plugin entry has no `roles` key.

    This is a read-only accessor — does not mutate disk or validate role-dict
    field shape. Callers (model_adapter.loader) decide how to merge with
    packaged defaults on a per-role basis.
    """
    manifest = read(manifest_path)
    for plugin in manifest.get("plugins", []):
        if plugin.get("name") == plugin_name:
            return plugin.get("roles") or []
    return []
