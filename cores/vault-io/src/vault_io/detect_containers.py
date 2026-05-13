#!/usr/bin/env python3
"""
detect_containers.py — Classify a repo's top-level directories into container types.

Usage:
    python detect_containers.py --json   # repo discovered via CODE_WIKI_REAL_VAULT_PATH or git

Returns a list of records:
    {"source": "<dir>", "classification": "<type>", "children_count": N, "reason": "<why>"}

Classifications:
    - "app" / "package" / "domain" / "docs"   — concrete container types
    - "single-package"                         — repo root is itself a package, no containers
    - "ambiguous"                              — needs user decision
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from vault_io._workspace import resolve_wiki_and_repo

MANIFEST_FILES = {
    "package.json",
    "pyproject.toml",
    "Cargo.toml",
    "go.mod",
    ".claude-plugin/plugin.json",
}
SKIP_DIRS = {
    ".git",
    ".hg",
    ".svn",
    "node_modules",
    ".venv",
    "venv",
    "__pycache__",
    ".pytest_cache",
    "dist",
    "build",
    "target",
    ".next",
    ".turbo",
}
DOC_THRESHOLD = 0.7
DOMAIN_THRESHOLD = 0.5


def _has_manifest(d: Path) -> bool:
    return any((d / m).exists() for m in MANIFEST_FILES)


def _immediate_subdirs(d: Path):
    return [p for p in d.iterdir() if p.is_dir() and p.name not in SKIP_DIRS and not p.name.startswith(".")]


def _is_package_container_shape(d: Path) -> bool:
    """A directory is a 'package container' if it has no manifest itself,
    but its immediate children include at least one with a manifest."""
    if _has_manifest(d):
        return False
    kids = _immediate_subdirs(d)
    return any(_has_manifest(k) for k in kids)


def _is_domain_member(d: Path) -> bool:
    """A directory qualifies as a domain member if it (recursively) houses
    package containers but isn't itself a package."""
    if _has_manifest(d):
        return False
    if _is_package_container_shape(d):
        return True
    # Check one level deeper: child is itself a package-container.
    return any(_is_package_container_shape(k) for k in _immediate_subdirs(d))


def _classify_dir(d: Path) -> dict:
    children = _immediate_subdirs(d)
    files = [p for p in d.iterdir() if p.is_file() and not p.name.startswith(".")]
    md_files = [p for p in files if p.suffix == ".md"]
    has_manifest_in_root = _has_manifest(d)

    # Rule 1: docs container — children predominantly markdown, no manifests anywhere
    if files and not children and not has_manifest_in_root:
        if len(md_files) / max(len(files), 1) >= DOC_THRESHOLD:
            return {
                "source": d.name,
                "classification": "docs",
                "children_count": len(md_files),
                "reason": f"{len(md_files)}/{len(files)} files are .md, no manifests",
            }

    # Rule 2: domain container — majority of children are themselves package containers
    # (either directly, or one level deeper through a `packages/` style folder).
    if children:
        domain_kids = [c for c in children if _is_domain_member(c)]
        # Only count as domain when children themselves don't have manifests
        # (else this is just a package container).
        if len(domain_kids) / len(children) > DOMAIN_THRESHOLD and not any(_has_manifest(c) for c in children):
            return {
                "source": d.name,
                "classification": "domain",
                "children_count": len(children),
                "reason": f"{len(domain_kids)}/{len(children)} children are package containers",
            }

    # Rule 3: package container — children have manifests
    if children:
        manifest_kids = [c for c in children if _has_manifest(c)]
        if manifest_kids and len(manifest_kids) == len(children) and not md_files:
            return {
                "source": d.name,
                "classification": "package",
                "children_count": len(manifest_kids),
                "reason": f"all {len(manifest_kids)} children have manifests",
            }
        # Mixed: some kids have manifests, some don't, or loose docs alongside packages
        if manifest_kids and (len(manifest_kids) < len(children) or md_files):
            return {
                "source": d.name,
                "classification": "ambiguous",
                "children_count": len(children),
                "reason": f"{len(manifest_kids)}/{len(children)} children have manifests; {len(md_files)} loose .md",
            }

    # Anything else with children but no manifest pattern: ambiguous
    if children or md_files:
        return {
            "source": d.name,
            "classification": "ambiguous",
            "children_count": len(children),
            "reason": "no clear pattern (no manifests in children, not predominantly .md)",
        }

    return {
        "source": d.name,
        "classification": "ambiguous",
        "children_count": 0,
        "reason": "empty or unrecognized",
    }


def detect(repo_root: Path) -> list[dict]:
    repo_root = Path(repo_root).resolve()
    if not repo_root.exists():
        return []
    top = _immediate_subdirs(repo_root)

    records = [_classify_dir(d) for d in top]
    structural = [r for r in records if r["classification"] in {"docs", "domain", "package"}]
    if not structural and _has_manifest(repo_root):
        return [
            {
                "source": "",
                "classification": "single-package",
                "children_count": 1,
                "reason": f"repo root has manifest at {repo_root.name}",
            }
        ]

    return sorted(records, key=lambda r: r["source"])


def main():
    p = argparse.ArgumentParser(description="Classify a repo's top-level dirs.")
    p.add_argument("--json", action="store_true", help="Emit JSON")
    args = p.parse_args()

    _, repo = resolve_wiki_and_repo()
    if repo is None:
        print("[error] could not resolve repo root from workspace", file=sys.stderr)
        sys.exit(1)
    if not repo.exists():
        print(f"[error] repo not found: {repo}", file=sys.stderr)
        sys.exit(1)

    records = detect(repo)

    if args.json:
        print(json.dumps(records, indent=2))
        return

    print(f"Container detection — {repo}")
    if not records:
        print("  (no top-level directories found)")
        return
    for r in records:
        src = r["source"] or "<repo root>"
        print(f"  {src:30s} -> {r['classification']:14s} ({r['children_count']} children) — {r['reason']}")


if __name__ == "__main__":
    main()
