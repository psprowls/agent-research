"""Render the manifest's explicit values to `<workspace>/.graph-wiki/config.json`.

The projection is the read surface for bash hooks (per-tool-use hooks must not
spawn the uv stack). Explicit values only — no defaults merged; hooks apply
their own `${VAR:-default}` fallbacks, so an absent key means "default",
unchanged behavior. Embeds the manifest's mtime + sha256 under `_meta` so
`session-start` can detect hand-edits and instruct `gw config sync`.
"""

from __future__ import annotations

import hashlib
import json
import os
import tempfile
from pathlib import Path

import yaml

from workspace_io import paths

PROJECTION_FILENAME = "config.json"


def projection_path(workspace: Path) -> Path:
    return paths.graph_dir(workspace) / PROJECTION_FILENAME


def write_projection(workspace: Path) -> Path:
    """Regenerate config.json from the manifest's on-disk explicit values."""
    workspace = Path(workspace)
    mpath = paths.manifest_path(workspace)
    # Single existence check, then stat + read off it — keeps _meta internally
    # consistent (both fields None on a missing manifest, never a mix).
    if mpath.exists():
        mtime = mpath.stat().st_mtime
        raw_bytes = mpath.read_bytes()
        sha256 = hashlib.sha256(raw_bytes).hexdigest()
        data = (yaml.safe_load(raw_bytes.decode("utf-8")) or {}) if raw_bytes else {}
    else:
        mtime = None
        sha256 = None
        data = {}
    payload = dict(data)
    payload["_meta"] = {
        "manifest_mtime": mtime,
        "manifest_sha256": sha256,
    }
    target = projection_path(workspace)
    target.parent.mkdir(parents=True, exist_ok=True)
    # default=str: PyYAML parses bare dates as datetime.date.
    rendered = json.dumps(payload, indent=2, default=str) + "\n"
    # Atomic replace: bash hooks read config.json concurrently (per-tool-use),
    # so a reader must never observe a truncated file.
    fd, tmp_name = tempfile.mkstemp(dir=target.parent, prefix=f".{PROJECTION_FILENAME}.", suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as fh:
            fh.write(rendered)
        os.replace(tmp_name, target)
    except BaseException:
        try:
            os.unlink(tmp_name)
        except OSError:
            pass
        raise
    return target
