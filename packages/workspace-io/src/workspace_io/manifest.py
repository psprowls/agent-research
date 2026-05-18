"""Read/write `.graph-wiki.yaml`. v2 only — raises on v1 format (D-14)."""
from __future__ import annotations

from pathlib import Path

import yaml


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
    return raw


def write(path: Path, data: dict) -> None:
    """Write v2 manifest. Creates parent dirs."""
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "version": 2,
        "initialized_at": str(data.get("initialized_at", "") or ""),
        "plugins": [
            {
                "name": p["name"],
                "installed_version": p.get("installed_version"),
                "applied_version": p.get("applied_version"),
            }
            for p in data.get("plugins", [])
        ],
    }
    path.write_text(
        yaml.safe_dump(payload, sort_keys=False, default_flow_style=False),
        encoding="utf-8",
    )
