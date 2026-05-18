"""Per-plugin version comparison helpers."""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import workspace_io.manifest as manifest
from workspace_io.paths import manifest_path


@dataclass(frozen=True)
class PendingUpdate:
    plugin: str
    applied_version: str | None
    installed_version: str


def warn_if_stale(workspace: Path, *, plugin: str, version: str) -> bool:
    """Compare `version` against stored `applied_version`.

    Returns True only when there's an existing entry with a non-null
    `applied_version` that differs from `version`. On True, writes
    `installed_version=version` (applied_version untouched). Otherwise
    no write."""
    workspace = Path(workspace)
    mpath = manifest_path(workspace)
    if not mpath.exists():
        return False
    data = manifest.read(mpath)
    entry = next((p for p in data.get("plugins", []) if p["name"] == plugin), None)
    if entry is None:
        return False
    applied = entry.get("applied_version")
    if applied is None or applied == version:
        return False
    entry["installed_version"] = version
    manifest.write(mpath, data)
    return True


def pending_updates(workspace: Path) -> list[PendingUpdate]:
    """Pure read. Returns plugins where installed_version != applied_version
    and installed_version is not None."""
    workspace = Path(workspace)
    mpath = manifest_path(workspace)
    if not mpath.exists():
        return []
    data = manifest.read(mpath)
    out: list[PendingUpdate] = []
    for entry in data.get("plugins", []):
        installed = entry.get("installed_version")
        applied = entry.get("applied_version")
        if installed is not None and installed != applied:
            out.append(
                PendingUpdate(
                    plugin=entry["name"],
                    applied_version=applied,
                    installed_version=installed,
                )
            )
    return out
