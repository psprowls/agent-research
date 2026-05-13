#!/usr/bin/env python3
"""
layout_io.py — Read and write the vault-io layout block in CLAUDE.md / AGENTS.md.

The layout block is delimited by sentinel HTML comments and contains a YAML
document inside a fenced code block. Format:

    <!-- lattice-wiki:layout:start -->
    ```yaml
    version: 1
    detected_at: 2026-04-29
    repo_root: ..
    containers:
      - source: apps
        vault_dir: apps
        classification: app
        children_count: 3
    ```
    <!-- lattice-wiki:layout:end -->

Hand-rolled minimal YAML emitter and parser tailored to this fixed shape
(stdlib-only — no PyYAML dependency).
"""

from __future__ import annotations

import datetime as dt
import re
from pathlib import Path
from typing import Optional

LAYOUT_START = "<!-- lattice-wiki:layout:start -->"
LAYOUT_END = "<!-- lattice-wiki:layout:end -->"

_BLOCK_RE = re.compile(
    re.escape(LAYOUT_START) + r"\s*\n```yaml\s*\n(.*?)\n```\s*\n" + re.escape(LAYOUT_END),
    re.DOTALL,
)


def read_layout(schema_path: Path) -> Optional[dict]:
    """Return parsed layout dict, or None if no block is present."""
    if not schema_path.exists():
        return None
    text = schema_path.read_text(encoding="utf-8")
    m = _BLOCK_RE.search(text)
    if not m:
        return None
    return _parse_yaml(m.group(1))


def write_layout(schema_path: Path, layout: dict) -> None:
    """Replace the existing block, or append a new one if none exists."""
    block = LAYOUT_START + "\n```yaml\n" + _emit_yaml(layout) + "```\n" + LAYOUT_END
    text = schema_path.read_text(encoding="utf-8") if schema_path.exists() else ""
    if _BLOCK_RE.search(text):
        new_text = _BLOCK_RE.sub(lambda _: block, text, count=1)
    else:
        sep = "" if text.endswith("\n") or not text else "\n"
        new_text = text + sep + "\n" + block + "\n"
    schema_path.write_text(new_text, encoding="utf-8")


# ---------- minimal YAML serializer for our schema ----------


def _emit_yaml(layout: dict) -> str:
    out = []
    out.append(f"version: {int(layout.get('version', 1))}")
    out.append(f"detected_at: {layout.get('detected_at', '')}")
    out.append(f"repo_root: {layout.get('repo_root', '..')}")
    out.append("containers:")
    for c in layout.get("containers", []):
        out.append(f"  - source: {c['source']}")
        out.append(f"    vault_dir: {_emit_scalar(c.get('vault_dir'))}")
        out.append(f"    classification: {c['classification']}")
        if "children_count" in c:
            out.append(f"    children_count: {int(c['children_count'])}")
        if c.get("note"):
            out.append(f'    note: "{c["note"]}"')
    return "\n".join(out) + "\n"


def _emit_scalar(v) -> str:
    if v is None:
        return "null"
    return str(v)


# ---------- minimal YAML parser for our schema ----------


def _parse_yaml(text: str) -> dict:
    out = {"containers": []}
    current = None
    for raw in text.splitlines():
        line = raw.rstrip()
        if not line.strip() or line.lstrip().startswith("#"):
            continue
        # top-level key: value
        if not line.startswith(" "):
            if line.rstrip(":") == "containers":
                continue
            k, _, v = line.partition(":")
            out[k.strip()] = _parse_scalar(v.strip())
            continue
        # list-item start
        if line.startswith("  - "):
            current = {}
            out["containers"].append(current)
            rest = line[4:]  # after "  - "
            k, _, v = rest.partition(":")
            current[k.strip()] = _parse_scalar(v.strip())
            continue
        # nested key in current item
        if line.startswith("    ") and current is not None:
            k, _, v = line.strip().partition(":")
            current[k.strip()] = _parse_scalar(v.strip())
            continue
    if "version" in out:
        out["version"] = int(out["version"])
    return out


def _parse_scalar(v: str):
    if v == "null" or v == "":
        return None
    if v.startswith('"') and v.endswith('"'):
        return v[1:-1]
    if v.lstrip("-").isdigit():
        return int(v)
    return v


def ensure_subpage(
    pkg_dir: Path,
    subpage_name: str,
    pkg_title: str,
    templates_dir: Path,
    today: Optional[str] = None,
) -> tuple[Path, bool]:
    """Create a package sub-page from template if it doesn't exist.

    Returns (path, created) where created=True if the file was just written.
    Raises FileNotFoundError if the template is missing.
    """
    dest = pkg_dir / f"{subpage_name}.md"
    if dest.exists():
        return dest, False
    tmpl = templates_dir / "package" / f"{subpage_name}.md"
    if not tmpl.exists():
        raise FileNotFoundError(f"template not found: {tmpl}")
    date = today or dt.date.today().isoformat()
    text = tmpl.read_text(encoding="utf-8")
    text = text.replace("{{PACKAGE_TITLE}}", pkg_title).replace("{{DATE}}", date)
    pkg_dir.mkdir(parents=True, exist_ok=True)
    dest.write_text(text, encoding="utf-8")
    return dest, True


def ensure_domain_page(
    domain_dir: Path,
    domain_title: str,
    templates_dir: Path,
    today: Optional[str] = None,
) -> tuple[Path, bool]:
    """Create <domain>/<domain>.md from the overview template if it doesn't exist.

    Returns (path, created) where created=True if the file was just written.
    Raises FileNotFoundError if the template is missing.
    """
    dest = domain_dir / f"{domain_dir.name}.md"
    if dest.exists():
        return dest, False
    tmpl = templates_dir / "domain" / "overview.md"
    if not tmpl.exists():
        raise FileNotFoundError(f"template not found: {tmpl}")
    date = today or dt.date.today().isoformat()
    text = tmpl.read_text(encoding="utf-8")
    text = text.replace("{{DOMAIN_TITLE}}", domain_title).replace("{{DATE}}", date)
    domain_dir.mkdir(parents=True, exist_ok=True)
    dest.write_text(text, encoding="utf-8")
    return dest, True


def ensure_domain_details(
    domain_dir: Path,
    domain_title: str,
    templates_dir: Path,
    today: Optional[str] = None,
) -> tuple[Path, bool]:
    """Create <domain>/details.md from the details template if it doesn't exist.

    Returns (path, created) where created=True if the file was just written.
    Raises FileNotFoundError if the template is missing.
    """
    dest = domain_dir / "details.md"
    if dest.exists():
        return dest, False
    tmpl = templates_dir / "domain" / "details.md"
    if not tmpl.exists():
        raise FileNotFoundError(f"template not found: {tmpl}")
    date = today or dt.date.today().isoformat()
    text = tmpl.read_text(encoding="utf-8")
    text = text.replace("{{DOMAIN_TITLE}}", domain_title).replace("{{DATE}}", date)
    domain_dir.mkdir(parents=True, exist_ok=True)
    dest.write_text(text, encoding="utf-8")
    return dest, True
