#!/usr/bin/env python3
"""
init_vault.py — Bootstrap a Code Wiki alongside a source code repo.

Creates the wiki structure under `<workspace>/wiki/` and seeds it with
starter templates. Adapted from the upstream source with the workspace.init
integration stubbed out (Phase 5 will reintroduce an equivalent workspace
bootstrap step). All file paths and template copying remain byte-identical
to the source.

Usage:
    python init_vault.py --topic "my-repo"
    python init_vault.py --topic "my-repo" --tool all
    python init_vault.py --topic "my-repo" --tool codex

The --tool flag controls which schema file(s) to install:
    claude-code  → CLAUDE.md (default)
    codex        → AGENTS.md
    cursor       → AGENTS.md + .cursorrules
    antigravity  → AGENTS.md
    all          → CLAUDE.md + AGENTS.md + .cursorrules (recommended for multi-tool)
"""

from __future__ import annotations

import argparse
import datetime as dt
import json
import logging
import sys
from pathlib import Path

logger = logging.getLogger(__name__)

from vault_io._workspace import resolve_wiki_and_repo
from vault_io.detect_containers import detect as _detect_containers
from vault_io.layout_io import write_layout as _write_layout
from workspace_io.init import init as _workspace_init

PLUGIN_NAME = "graph-wiki"
PLUGIN_VERSION = "0.1.0"

ASSETS_DIR = Path(__file__).resolve().parent / "assets"

FIXED_VAULT_DIRS = [
    "concepts",
    "architecture",
    "adrs",
    "sources",
    "dependencies",
    ".templates",
]

TOOL_FILES = {
    "claude-code": ["CLAUDE.md.template:CLAUDE.md"],
    "codex": ["AGENTS.md.template:AGENTS.md"],
    "cursor": ["AGENTS.md.template:AGENTS.md", "cursorrules.template:.cursorrules"],
    "antigravity": ["AGENTS.md.template:AGENTS.md"],
    "opencode": ["AGENTS.md.template:AGENTS.md"],
    "gemini-cli": ["AGENTS.md.template:AGENTS.md"],
    "all": [
        "CLAUDE.md.template:CLAUDE.md",
        "AGENTS.md.template:AGENTS.md",
        "cursorrules.template:.cursorrules",
    ],
}


def render_template(src, dest, variables):
    if not src.exists():
        print(f"[warn] template missing: {src}", file=sys.stderr)
        return False
    try:
        text = src.read_text(encoding="utf-8")
    except OSError as e:
        print(f"[warn] could not read {src}: {e}", file=sys.stderr)
        return False
    for key, value in variables.items():
        text = text.replace("{{" + key + "}}", value)
    try:
        dest.write_text(text, encoding="utf-8")
    except OSError as e:
        print(f"[warn] could not write {dest}: {e}", file=sys.stderr)
        return False
    return True


def _resolve_pinned_containers(
    repo: Path, non_interactive: bool, workspace_path: Path | None = None
) -> list[dict]:
    """Run the detector, prompt for ambiguous rows, return the pinned list."""
    records = _detect_containers(repo, workspace_path=workspace_path)
    if records and records[0]["classification"] == "single-package":
        if not non_interactive:
            print("Detected: single-package repo (no structural containers).")
        else:
            logger.info("Detected: single-package repo (no structural containers).")
        return []
    if not records:
        return []

    if not non_interactive:
        print(f"Detected {len(records)} top-level container(s):")
        print()
        for r in records:
            src = r["source"] or "<root>"
            print(f"  {src:30s} -> {r['classification']:14s} ({r['children_count']} children) - {r['reason']}")
        print()
    else:
        logger.info("Detected %d top-level container(s).", len(records))

    pinned = []
    for r in records:
        cls = r["classification"]
        if cls == "ambiguous":
            if non_interactive:
                cls = "skip"
            else:
                choice = (
                    input(
                        f"  '{r['source']}' is ambiguous. Pick [package/app/domain/docs/skip] (default: skip): "
                    ).strip()
                    or "skip"
                )
                if choice not in {"package", "app", "domain", "docs", "skip"}:
                    print(f"    invalid choice '{choice}'; defaulting to 'skip'")
                    choice = "skip"
                cls = choice
        pinned.append(
            {
                "source": r["source"],
                "vault_dir": None if cls in ("skip", "docs") else r["source"],
                "classification": cls,
                "children_count": r["children_count"],
            }
        )
    return pinned


def _error(message, as_json=False):
    if as_json:
        print(json.dumps({"status": "error", "message": message}))
    else:
        logger.error("%s", message)
    raise RuntimeError(message)


def init_wiki(
    wiki_path,
    repo_path,
    topic,
    tool,
    force,
    as_json=False,
    non_interactive=False,
):
    """Bootstrap a Code Wiki at `wiki_path`.

    NOTE: The upstream implementation called a workspace.init() helper to
    register the plugin with the workspace (creating `<workspace>/raw/`,
    `<workspace>/work/`, `.graph-wiki.yaml`). That dependency is not available
    in deep-agents; Phase 5 will provide a workspace-bootstrap equivalent.
    For now, this function only writes inside `wiki_path`.
    """
    if wiki_path.exists() and any(wiki_path.iterdir()) and not force:
        _error(f"{wiki_path} is not empty. Use --force to overwrite.", as_json)

    workspace_path = wiki_path.parent
    # Create raw/ and work/ workspace sibling directories.
    (workspace_path / "raw").mkdir(parents=True, exist_ok=True)
    (workspace_path / "work").mkdir(parents=True, exist_ok=True)
    # Register plugin with the workspace: writes .graph-wiki.yaml, runs git init
    # if needed, ensures .graph-wiki.local.yaml is gitignored, renders <workspace>/CLAUDE.md.
    _workspace_init(
        repo_path,
        plugin=PLUGIN_NAME,
        version=PLUGIN_VERSION,
        workspace=workspace_path,
    )

    pinned = _resolve_pinned_containers(repo_path, non_interactive, workspace_path=workspace_path)
    structural_dirs = [c["vault_dir"] for c in pinned if c["vault_dir"]]

    try:
        wiki_path.mkdir(parents=True, exist_ok=True)
        for d in structural_dirs + FIXED_VAULT_DIRS:
            (wiki_path / d).mkdir(parents=True, exist_ok=True)
    except OSError as e:
        _error(f"failed to create wiki structure: {e}", as_json)

    today = dt.date.today().isoformat()
    variables = {
        "TOPIC": topic,
        "DATE": today,
        "WIKI_NAME": wiki_path.name,
        "REPO_PATH": str(repo_path),
    }

    installed_files = []

    for spec in TOOL_FILES.get(tool, TOOL_FILES["claude-code"]):
        src_name, dest_name = spec.split(":", 1)
        dest = wiki_path / dest_name
        if render_template(ASSETS_DIR / src_name, dest, variables):
            installed_files.append(dest_name)

    for spec in [
        ("index.md.template", wiki_path / "index.md"),
        ("log.md.template", wiki_path / "log.md"),
    ]:
        if render_template(ASSETS_DIR / spec[0], spec[1], variables):
            installed_files.append(str(spec[1].relative_to(wiki_path)))

    tmpl_dest = wiki_path / ".templates"
    tmpl_dest.mkdir(exist_ok=True)
    src_tmpl = ASSETS_DIR / "page-templates"
    template_count = 0
    if src_tmpl.exists():
        for f in src_tmpl.rglob("*"):
            if f.is_file():
                rel = f.relative_to(src_tmpl)
                dest_file = tmpl_dest / rel
                dest_file.parent.mkdir(parents=True, exist_ok=True)
                try:
                    dest_file.write_text(f.read_text(encoding="utf-8"), encoding="utf-8")
                    template_count += 1
                except OSError as e:
                    print(f"[warn] failed to copy template {rel}: {e}", file=sys.stderr)

    layout = {
        "version": 1,
        "detected_at": today,
        "repo_root": "..",
        "containers": pinned,
    }
    for schema_name in ("CLAUDE.md", "AGENTS.md"):
        schema_path = wiki_path / schema_name
        if schema_path.exists():
            try:
                _write_layout(schema_path, layout)
            except OSError as e:
                print(
                    f"[warn] failed to write layout to {schema_name}: {e}",
                    file=sys.stderr,
                )

    gitignore = wiki_path / ".gitignore"
    gitignore.write_text(
        "\n".join([".obsidian/workspace*", ".obsidian/cache", ".DS_Store", ""]),
        encoding="utf-8",
    )

    result = {
        "status": "ok",
        "wiki_path": str(wiki_path),
        "repo_path": str(repo_path),
        "topic": topic,
        "tool": tool,
        "date": today,
        "installed_files": installed_files,
        "page_templates_copied": template_count,
        "raw_path": str(workspace_path / "raw"),
        "work_path": str(workspace_path / "work"),
        "layers": {
            "wiki": f"{wiki_path}/ — LLM-maintained knowledge base",
            "raw": f"{workspace_path}/raw/ — staging area for source ingestion",
            "work": f"{workspace_path}/work/ — work item pages",
            "index": f"{wiki_path}/index.md",
            "log": f"{wiki_path}/log.md",
        },
        "next_steps": [
            f"Open {workspace_path} in Obsidian (sidebar shows wiki/, raw/, work/ as siblings)",
            "Run /graph-wiki:scan to populate wiki/packages/ from workspace manifests",
            f"Stage a source under {workspace_path}/raw/ and run /graph-wiki:ingest",
        ],
    }

    if as_json:
        print(json.dumps(result, indent=2))
        return result

    logger.info("[ok] Initialized Code Wiki at: %s", wiki_path)
    logger.info("     Workspace: %s", workspace_path)
    logger.info("     Repo:      %s", repo_path)
    logger.info("     Topic:     %s", topic)
    logger.info("     Tool:      %s", tool)
    logger.info("     Installed: %s", ", ".join(installed_files))
    logger.info("     Page templates copied: %d", template_count)
    logger.info("Next steps:")
    logger.info("  1. Open %s in Obsidian (workspace root)", workspace_path)
    logger.info("  2. Run /graph-wiki:scan to populate wiki/packages/")
    logger.info("  3. Stage a source under %s/raw/ and run /graph-wiki:ingest <path>", workspace_path)
    return result


def main():
    p = argparse.ArgumentParser(
        description="Initialize a Code Wiki in the resolved graph-wiki workspace.",
    )
    p.add_argument(
        "--topic",
        required=True,
        help="Short description of the repo (e.g. 'psprowls my-repo')",
    )
    p.add_argument(
        "--tool",
        default="all",
        choices=sorted(TOOL_FILES.keys()),
        help="Which schema file(s) to install (default: all)",
    )
    p.add_argument("--force", action="store_true", help="Overwrite non-empty target directory")
    p.add_argument("--json", action="store_true", help="Emit result as JSON")
    p.add_argument(
        "--non-interactive",
        action="store_true",
        help="Don't prompt for ambiguous containers; mark them skip.",
    )
    p.add_argument(
        "--workspace",
        default=None,
        help="Workspace path (bypasses .graph-wiki.yaml discovery; required on first bootstrap).",
    )
    p.add_argument(
        "--repo",
        default=None,
        help="Override repo root (default: walk up from cwd for .git).",
    )
    args = p.parse_args()
    workspace_arg = Path(args.workspace).expanduser().resolve() if args.workspace else None
    repo_arg = Path(args.repo).expanduser().resolve() if args.repo else None
    wiki, repo = resolve_wiki_and_repo(workspace_path=workspace_arg, repo_path=repo_arg)
    init_wiki(
        wiki,
        repo,
        args.topic,
        args.tool,
        args.force,
        as_json=args.json,
        non_interactive=args.non_interactive,
    )


if __name__ == "__main__":
    main()
