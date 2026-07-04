"""Generic config registry: entry schema, precedence resolution, validated writes.

Mechanism only — the catalog of concrete entries lives in graph-wiki-core
(config_catalog.py) and is passed in by callers. The only key knowledge here
is workspace-io-owned: the link-file keys (machine-local repo link) and the
provenance keys (tooling-stamped), both refused on write.

Precedence for reads: env var counterpart > committed manifest > entry default.
Every successful write regenerates the config.json projection.
"""

from __future__ import annotations

import difflib
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, Mapping

import yaml

from workspace_io import manifest, paths
from workspace_io.projection import write_projection

#: Keys that live in <workspace>/.graph-wiki.local.yaml (the machine-local
#: repo-link file), never the manifest.
LINK_FILE_KEYS = frozenset({"repo-directory", "multi-repo", "repos-root", "repos", "exclude"})

_TRUTHY = {"true", "1", "yes", "on"}
_FALSY = {"false", "0", "no", "off"}


class RegistryError(ValueError):
    """Base for registry refusals; message is user-facing."""


class UnknownKeyError(RegistryError):
    pass


class EnvOnlyKeyError(RegistryError):
    pass


class SecretKeyError(RegistryError):
    pass


class LinkFileKeyError(RegistryError):
    pass


class ProvenanceKeyError(RegistryError):
    pass


class InvalidValueError(RegistryError):
    pass


@dataclass(frozen=True)
class ConfigEntry:
    key: str  # dotted path; a "*" segment matches any single segment
    type: str  # "str" | "bool" | "int" | "list[str]"
    default: object
    description: str
    kind: str = "manifest"  # "manifest" | "env-only"
    env_var: str | None = None
    allowed: tuple[str, ...] = ()
    secret: bool = False


@dataclass(frozen=True)
class Resolved:
    key: str
    value: object
    origin: str  # "env" | "manifest" | "default"
    entry: ConfigEntry


def _matches(pattern: str, key: str) -> bool:
    p, k = pattern.split("."), key.split(".")
    return len(p) == len(k) and all(ps in ("*", ks) for ps, ks in zip(p, k))


def find_entry(catalog: Iterable[ConfigEntry], key: str) -> ConfigEntry | None:
    entries = tuple(catalog)
    for entry in entries:
        if entry.key == key:
            return entry
    for entry in entries:
        if "*" in entry.key and _matches(entry.key, key):
            return entry
    return None


def _unknown(catalog: Iterable[ConfigEntry], key: str) -> UnknownKeyError:
    near = difflib.get_close_matches(key, [e.key for e in catalog], n=3, cutoff=0.4)
    hint = f" — did you mean: {', '.join(near)}?" if near else ""
    return UnknownKeyError(f"unknown config key '{key}'{hint}")


def coerce(entry: ConfigEntry, raw: str) -> object:
    if entry.type == "bool":
        low = raw.strip().lower()
        if low in _TRUTHY:
            return True
        if low in _FALSY:
            return False
        raise InvalidValueError(f"'{entry.key}' expects a boolean (true/false), got {raw!r}")
    if entry.type == "int":
        try:
            return int(raw)
        except ValueError:
            raise InvalidValueError(f"'{entry.key}' expects an integer, got {raw!r}") from None
    if entry.type == "list[str]":
        return [s.strip() for s in raw.split(",") if s.strip()]
    value = raw
    if entry.allowed and value not in entry.allowed:
        raise InvalidValueError(f"'{entry.key}' must be one of {sorted(entry.allowed)}, got {value!r}")
    return value


def _raw_manifest(workspace: Path) -> dict:
    """The manifest's explicit on-disk values — no read() normalization, so
    origin reporting can distinguish 'explicitly set' from 'injected default'."""
    mpath = paths.manifest_path(workspace)
    if not mpath.exists():
        return {}
    return yaml.safe_load(mpath.read_text(encoding="utf-8")) or {}


def _get_path(data: dict, key: str) -> object | None:
    node: object = data
    for seg in key.split("."):
        if not isinstance(node, dict) or seg not in node:
            return None
        node = node[seg]
    return node


def _set_path(data: dict, key: str, value: object) -> None:
    segs = key.split(".")
    node = data
    for seg in segs[:-1]:
        nxt = node.get(seg)
        if not isinstance(nxt, dict):
            nxt = {}
            node[seg] = nxt
        node = nxt
    node[segs[-1]] = value


def _unset_path(data: dict, key: str) -> bool:
    segs = key.split(".")
    parents: list[tuple[dict, str]] = []
    node = data
    for seg in segs[:-1]:
        nxt = node.get(seg)
        if not isinstance(nxt, dict):
            return False
        parents.append((node, seg))
        node = nxt
    if segs[-1] not in node:
        return False
    del node[segs[-1]]
    # Prune now-empty parent dicts so write() omit-guards see clean absence.
    for parent, seg in reversed(parents):
        if not parent[seg]:
            del parent[seg]
    return True


def resolve_key(
    catalog: Iterable[ConfigEntry],
    key: str,
    *,
    workspace: Path,
    environ: Mapping[str, str] | None = None,
) -> Resolved:
    environ = os.environ if environ is None else environ
    entry = find_entry(catalog, key)
    if entry is None:
        raise _unknown(catalog, key)
    if entry.env_var and str(environ.get(entry.env_var, "")).strip():
        return Resolved(key, environ[entry.env_var], "env", entry)
    if entry.kind == "manifest":
        explicit = _get_path(_raw_manifest(workspace), key)
        if explicit is not None:
            return Resolved(key, explicit, "manifest", entry)
    return Resolved(key, entry.default, "default", entry)


def _writable_entry(catalog: Iterable[ConfigEntry], key: str) -> ConfigEntry:
    if key in LINK_FILE_KEYS:
        raise LinkFileKeyError(
            f"'{key}' lives in <workspace>/.graph-wiki.local.yaml — the machine-local "
            "repo link file — not the manifest. Edit that file by hand."
        )
    if key in ("version", "initialized_at") or key == "plugins" or key.startswith("plugins."):
        raise ProvenanceKeyError(f"'{key}' is tooling-stamped provenance and is not writable via gw config.")
    entry = find_entry(catalog, key)
    if entry is None:
        raise _unknown(catalog, key)
    if entry.secret:
        raise SecretKeyError(f"'{key}' is a secret and is never stored. export {entry.env_var or key}=... instead.")
    if entry.kind == "env-only":
        raise EnvOnlyKeyError(
            f"'{key}' is env-only and is never stored in the manifest. "
            f"export {entry.env_var or key}=... (e.g. via the repo's .claude/settings.local.json env block)."
        )
    return entry


def set_key(catalog: Iterable[ConfigEntry], key: str, raw_value: str, *, workspace: Path) -> Resolved:
    entry = _writable_entry(catalog, key)
    value = coerce(entry, raw_value)
    mpath = paths.manifest_path(workspace)
    data = manifest.read(mpath)
    _set_path(data, key, value)
    manifest.write(mpath, data)
    write_projection(workspace)
    return Resolved(key, value, "manifest", entry)


def unset_key(catalog: Iterable[ConfigEntry], key: str, *, workspace: Path) -> bool:
    _writable_entry(catalog, key)
    mpath = paths.manifest_path(workspace)
    data = manifest.read(mpath)
    removed = _unset_path(data, key)
    if removed:
        manifest.write(mpath, data)
        write_projection(workspace)
    return removed
