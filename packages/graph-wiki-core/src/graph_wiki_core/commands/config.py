"""gw config — the sole programmatic writer for graph-wiki configuration.

Logic layer for the config verbs (get/set/unset/list/sync); the Typer surface
in graph-wiki-cli is a thin shell over these functions. Hooks wiring and the
interactive init flow live in this module too (added by later tasks).
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from workspace_io.projection import write_projection
from workspace_io.registry import Resolved, _get_path, _raw_manifest, resolve_key, set_key, unset_key

from graph_wiki_core.config_catalog import CATALOG

_MASK = "••••"


def _resolve_workspace(workspace_path: Path | None) -> Path:
    if workspace_path is not None:
        return Path(workspace_path).resolve()
    from workspace_io import resolve

    return resolve().workspace


@dataclass
class ConfigValue:
    """A single resolved config key, ready for display or programmatic use."""

    key: str
    value: object
    origin: str  # "env" | "manifest" | "default"
    default: object
    description: str
    kind: str
    env_var: str | None
    secret: bool
    shadows: object | None = None  # explicit manifest value hidden behind an env override


def _to_config_value(workspace: Path, resolved: Resolved) -> ConfigValue:
    entry = resolved.entry
    value = _MASK if (entry.secret and resolved.value not in (None, "")) else resolved.value
    shadows = None
    if resolved.origin == "env" and entry.kind == "manifest":
        explicit = _get_path(_raw_manifest(workspace), resolved.key)
        if explicit is not None:
            shadows = explicit
    return ConfigValue(
        key=resolved.key,
        value=value,
        origin=resolved.origin,
        default=_MASK if (entry.secret and entry.default not in (None, "")) else entry.default,
        description=entry.description,
        kind=entry.kind,
        env_var=entry.env_var,
        secret=entry.secret,
        shadows=shadows,
    )


async def run_config_get(key: str, workspace_path: Path | None = None) -> ConfigValue:
    """Resolve a single config key through the env > manifest > default precedence."""
    workspace = _resolve_workspace(workspace_path)
    return _to_config_value(workspace, resolve_key(CATALOG, key, workspace=workspace))


async def run_config_set(key: str, value: str, workspace_path: Path | None = None) -> ConfigValue:
    """Write a key into the manifest (validated + rollback-safe) and re-resolve it."""
    workspace = _resolve_workspace(workspace_path)
    return _to_config_value(workspace, set_key(CATALOG, key, value, workspace=workspace))


async def run_config_unset(key: str, workspace_path: Path | None = None) -> ConfigValue:
    """Remove a key's explicit manifest value, returning its now-resolved (env/default) value."""
    workspace = _resolve_workspace(workspace_path)
    unset_key(CATALOG, key, workspace=workspace)
    return _to_config_value(workspace, resolve_key(CATALOG, key, workspace=workspace))


def _expand_wildcards(workspace: Path) -> list[str]:
    """Concrete keys present in the manifest that match a wildcard catalog entry.

    Handles both wildcard shapes: `roles.*.<field>` (head="roles", field="<field>")
    and `plugin.backend_overrides.*` (head="plugin.backend_overrides", field="").
    """
    raw = _raw_manifest(workspace)
    concrete: list[str] = []
    for entry in CATALOG:
        if "*" not in entry.key:
            continue
        head, _, tail = entry.key.partition(".*")
        block = _get_path(raw, head)
        if not isinstance(block, dict):
            continue
        field = tail.lstrip(".")
        for name, fields in block.items():
            if field:
                if isinstance(fields, dict) and field in fields:
                    concrete.append(f"{head}.{name}.{field}")
            else:
                concrete.append(f"{head}.{name}")
    return concrete


async def run_config_list(workspace_path: Path | None = None) -> list[ConfigValue]:
    """One row per catalog entry, with wildcard entries expanded to concrete keys."""
    workspace = _resolve_workspace(workspace_path)
    keys = [entry.key for entry in CATALOG if "*" not in entry.key] + _expand_wildcards(workspace)
    return [_to_config_value(workspace, resolve_key(CATALOG, key, workspace=workspace)) for key in keys]


async def run_config_sync(workspace_path: Path | None = None) -> Path:
    """Regenerate `<workspace>/.graph-wiki/config.json` from the manifest and return its path."""
    return write_projection(_resolve_workspace(workspace_path))
