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
    raw_bytes = mpath.read_bytes() if mpath.exists() else b""
    data = (yaml.safe_load(raw_bytes.decode("utf-8")) or {}) if raw_bytes else {}
    payload = dict(data)
    payload["_meta"] = {
        "manifest_mtime": mpath.stat().st_mtime if mpath.exists() else None,
        "manifest_sha256": hashlib.sha256(raw_bytes).hexdigest(),
    }
    target = projection_path(workspace)
    target.parent.mkdir(parents=True, exist_ok=True)
    # default=str: PyYAML parses bare dates as datetime.date.
    target.write_text(json.dumps(payload, indent=2, default=str) + "\n", encoding="utf-8")
    return target
