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

from wiki_io._workspace import resolve_wiki_and_repo
from workspace_io.init import init as _workspace_init

PLUGIN_NAME = "graph-wiki"
PLUGIN_VERSION = "0.1.1"

ASSETS_DIR = Path(__file__).resolve().parent / "assets"

FIXED_VAULT_DIRS = [
    "concepts",
    "architecture",
    "adrs",
    "entities",
    "sources",
    ".templates",
]

SECTION_INDEX_STUBS = {
    "concepts": "Concept",
    "sources": "Source",
    "adrs": "ADR",
    "architecture": "Architecture",
}

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
    in agent-research; Phase 5 will provide a workspace-bootstrap equivalent.
    For now, this function only writes inside `wiki_path`.

    `non_interactive` is accepted but ignored: it previously drove the
    ambiguous-container prompt during layout detection. Entity discovery is now
    purely graph-driven, so no container detection or layout block is written.
    The parameter is retained as a no-op so existing callers (run_init, the CLI
    `gw bootstrap --interactive` flag) keep working unchanged.
    """
    del non_interactive  # no-op: container detection removed (decontainerize)
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
        topic=topic,
    )

    try:
        wiki_path.mkdir(parents=True, exist_ok=True)
        for d in FIXED_VAULT_DIRS:
            (wiki_path / d).mkdir(parents=True, exist_ok=True)
    except OSError as e:
        _error(f"failed to create wiki structure: {e}", as_json)

    today = dt.date.today().isoformat()
    variables = {
        "TOPIC": topic,
        "DATE": today,
        # Display name for page titles. Use the human topic, not the literal
        # wiki dir name ("wiki"), so titles read "# Agent Research — Code Wiki".
        "WIKI_NAME": topic,
        "REPO_PATH": str(repo_path),
    }

    installed_files = []

    # Seed wiki/entities/ with an empty .gitkeep so the otherwise-empty dir is
    # committable. write_entities() self-heals it away once real entity pages
    # exist (and restores it if a deletion sweep empties the dir again).
    entities_gitkeep = wiki_path / "entities" / ".gitkeep"
    if not entities_gitkeep.exists():
        entities_gitkeep.write_text("", encoding="utf-8")
        installed_files.append(str(entities_gitkeep.relative_to(wiki_path)))

    for section, label in SECTION_INDEX_STUBS.items():
        stub_path = wiki_path / section / "index.md"
        if stub_path.exists():
            continue
        stub_path.write_text(
            f"# {label}\n\n"
            f"Auto-generated stub. Pages of category `{label.lower()}` "
            f"appear here as they are added to the wiki via "
            f"`/graph-wiki:ingest` or manual creation. "
            f"Regenerated by `scripts/update_index.py` once entries exist.\n",
            encoding="utf-8",
        )
        installed_files.append(str(stub_path.relative_to(wiki_path)))

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
        help="Accepted for compatibility; has no effect (container detection removed).",
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
