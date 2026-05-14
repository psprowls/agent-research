from __future__ import annotations

"""Scan command — walk a monorepo, diff against vault, fan-out scanner subagents.

Public API:
    ScanResult              — dataclass: added, updated, deleted, renamed, errors, state_gate
    SCANNER_SYSTEM          — system prompt for scanner role (body-only, no File map)
    build_stub_prompt(pkg)  — human message: package metadata + representative file snippets
    run_scan(vault_path, no_file_map, max_depth)  — end-to-end scan pipeline
"""

import logging
from dataclasses import dataclass, field
from pathlib import Path

from langchain_core.messages import HumanMessage, SystemMessage
from model_adapter.loader import load_role_config, make_llm
from subagent_runtime.pool import FanOutResult, SubagentPool
from vault_io._workspace import resolve_wiki_and_repo
from vault_io.append_log import append_log
from vault_io.layout_io import read_layout
from vault_io.scan_monorepo import (
    _load_existing_pages,
    attach_changed_files,
    build_file_map,
    compute_diff,
    compute_state_gate,
    discover_workspaces,
    regenerate_dependencies_index,
)
from vault_io.update_index import (
    CATEGORY_INDEX_FILES,
    CATEGORY_LABELS,
    render_category_index,
    render_index,
    scan_vault,
    scan_work,
)

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Local helper: update_index (wrapper for vault_io.update_index functions)
# ---------------------------------------------------------------------------


def update_index(wiki: Path) -> None:
    """Regenerate wiki/index.md and category sub-indexes from vault frontmatter.

    Wraps vault_io.update_index scan_vault + render_index pipeline.
    """
    pages = scan_vault(wiki)
    work_entries = scan_work(wiki.parent)
    if work_entries:
        pages["work"] = work_entries
    vault = wiki
    content = render_index(pages, wiki.name, vault.name)
    index_path = wiki / "index.md"
    index_path.write_text(content, encoding="utf-8")
    for cat, fname in CATEGORY_INDEX_FILES.items():
        entries = pages.get(cat, [])
        if not entries:
            continue
        label = CATEGORY_LABELS.get(cat, cat.capitalize())
        cat_content = render_category_index(entries, cat, label, vault.name)
        cat_path = vault / fname
        cat_path.parent.mkdir(parents=True, exist_ok=True)
        cat_path.write_text(cat_content, encoding="utf-8")


# ---------------------------------------------------------------------------
# Local helper: pick_representative
# ---------------------------------------------------------------------------


def pick_representative(pkg_path: Path, entries: list[Path] | None = None) -> list[Path]:
    """Return up to 3 representative source files from a package directory.

    Priority order:
    1. Entry point files (main.py, __init__.py, index.ts, index.js, lib.rs, mod.rs)
    2. Files in src/ or lib/ directories
    3. Any other tracked source files (non-test, non-config)

    If entries is None, walk the package directory directly.
    Returns at most 3 paths.
    """
    if entries is None:
        try:
            entries = list(pkg_path.rglob("*"))
        except OSError:
            return []

    _ENTRY_NAMES = {"main.py", "__init__.py", "index.ts", "index.js", "lib.rs", "mod.rs", "main.ts", "main.js"}
    _SOURCE_EXTS = {".py", ".ts", ".js", ".rs", ".go", ".java", ".kt"}
    _SKIP_DIRS = {"node_modules", ".git", ".venv", "__pycache__", "dist", "build", ".next"}
    _SKIP_PATTERNS = {"test", "spec", "fixture", "mock"}

    def _is_source(p: Path) -> bool:
        # Skip non-files
        if not p.is_file():
            return False
        # Skip files in skippable dirs
        if any(part in _SKIP_DIRS for part in p.parts):
            return False
        # Skip test/fixture files
        name_lower = p.name.lower()
        if any(pat in name_lower for pat in _SKIP_PATTERNS):
            return False
        return p.suffix in _SOURCE_EXTS

    source_files = [p for p in entries if _is_source(p)]

    # Priority 1: entry points
    entry_points = [p for p in source_files if p.name in _ENTRY_NAMES]

    # Priority 2: files in src/ or lib/
    src_files = [p for p in source_files if any(part in {"src", "lib"} for part in p.parts) and p not in entry_points]

    # Combine and deduplicate up to 3
    candidates = entry_points + src_files + [p for p in source_files if p not in entry_points and p not in src_files]
    return candidates[:3]

# ---------------------------------------------------------------------------
# System prompt constant
# ---------------------------------------------------------------------------

SCANNER_SYSTEM = """\
You are a code wiki scanner. Your job is to write a concise stub page for a software package.

Produce ONLY the page body with YAML frontmatter. Do NOT include a "## File map" section — that
is added separately by the build pipeline and must not appear in your output.

Your output must include:
1. YAML frontmatter (between --- delimiters) with these fields:
   - title: <package name>
   - category: package  (use "app" if it is an application, otherwise "package")
   - summary: <one-line description of what the package does>
   - package_path: <relative path of the package in the repo>
   - language: <primary language: python, typescript, javascript, rust, go, unknown>
   - version: <version string or omit if unknown>
   - depends_on: []  (list of internal workspace dependencies, or empty list)
   - exports: []  (list of public exports/scripts, or empty list)

2. ONE short "## Overview" section (3-5 sentences) describing what the package does and why.

3. ONE short "## Notable files" section listing 2-4 key files with a one-line description each.

Keep total output under 380 tokens. Do NOT speculate beyond what the provided file listing shows.
Do NOT include a "## File map" section — it will be appended automatically.
"""

# ---------------------------------------------------------------------------
# ScanResult dataclass
# ---------------------------------------------------------------------------


@dataclass
class ScanResult:
    """Result of a run_scan() call.

    Fields:
        added:      Names of packages that received newly created vault pages.
        updated:    Names of packages whose existing vault pages were refreshed.
        deleted:    Names of packages marked stale (vault page exists, repo package gone).
        renamed:    Pairs [[old_name, new_name], ...] for detected renames.
        errors:     Error strings for packages that failed during fan-out.
        state_gate: Dict from compute_state_gate() — {allowed, reason, head_commit}.
    """

    added: list[str] = field(default_factory=list)
    updated: list[str] = field(default_factory=list)
    deleted: list[str] = field(default_factory=list)
    renamed: list[list[str]] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)
    state_gate: dict = field(default_factory=dict)


# ---------------------------------------------------------------------------
# Helper: build_stub_prompt
# ---------------------------------------------------------------------------


def build_stub_prompt(pkg: dict, no_file_map: bool = False) -> str:
    """Return the human message text for the scanner LLM.

    Includes package metadata dict, repo-relative path, and up to 3 sampled
    file snippets via pick_representative(). File snippets are capped at 800
    chars each to stay within the 500-token scanner budget.
    """
    lines: list[str] = [
        f"Package name: {pkg.get('name', 'unknown')}",
        f"Path in repo: {pkg.get('path', 'unknown')}",
        f"Type: {pkg.get('type', 'unknown')}",
        f"Language: {pkg.get('language', 'unknown')}",
        f"Version: {pkg.get('version') or 'unknown'}",
        f"Exports: {pkg.get('exports') or []}",
        f"Depends on (workspace): {pkg.get('depends_on') or []}",
        "",
    ]

    # Attach file_map if it was pre-computed
    if not no_file_map and pkg.get("file_map"):
        lines.append("File listing (for reference):")
        lines.append(pkg["file_map"][:1000])
        lines.append("")

    # Representative file snippets (up to 3)
    pkg_path_str = pkg.get("path")
    if pkg_path_str:
        try:
            pkg_abs = Path(pkg_path_str).resolve()
            representatives = pick_representative(pkg_abs)
            for file_path in representatives[:3]:
                try:
                    snippet = file_path.read_text(encoding="utf-8", errors="replace")
                    if len(snippet) > 800:
                        snippet = snippet[:800] + "\n[TRUNCATED]"
                    lines.append(f"--- {file_path.name} ---")
                    lines.append(snippet)
                    lines.append("")
                except OSError:
                    pass
        except Exception:
            pass  # pick_representative failures are non-fatal

    lines.append("Write the vault stub page for this package. Do NOT include a ## File map section.")
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Helper: _add_stale_tag
# ---------------------------------------------------------------------------


def _add_stale_tag(page_path: Path) -> None:
    """Prepend stale: true to the YAML frontmatter of an existing vault page.

    Idempotent: checks for existing stale: line before prepending (T-05-04-03).
    Preserves all other frontmatter keys and body content.
    """
    if not page_path.exists():
        logger.warning("Cannot add stale tag — page not found: %s", page_path)
        return

    text = page_path.read_text(encoding="utf-8")

    # Already stale
    if "stale: true" in text:
        return

    # Insert stale: true as the first field after the opening ---
    if text.startswith("---\n"):
        # Replace opening --- with --- + stale: true
        new_text = "---\nstale: true\n" + text[4:]
    else:
        # No frontmatter — prepend it
        new_text = "---\nstale: true\n---\n\n" + text

    page_path.write_text(new_text, encoding="utf-8")


# ---------------------------------------------------------------------------
# Public: run_scan
# ---------------------------------------------------------------------------


async def run_scan(
    vault_path: Path | None = None,
    no_file_map: bool = False,
    max_depth: int = 3,
) -> ScanResult:
    """End-to-end scan: discovery → diff → scanner fan-out → post-processing.

    Steps:
        1. Resolve wiki and repo from vault_path.
        2. Read layout block from wiki/CLAUDE.md or wiki/AGENTS.md.
        3. discover_workspaces(repo, pinned_containers=pinned).
        4. Build file_map per workspace (unless no_file_map=True).
        5. _load_existing_pages(wiki) — existing vault pages by name.
        6. attach_changed_files(workspaces, existing, repo).
        7. compute_diff(workspaces, existing) → {new, renamed, deleted, unchanged}.
        8. compute_state_gate(repo) → {allowed, reason, head_commit}.
        9. Scanner fan-out: SubagentPool.run_all for new + changed packages.
        10. Write successful stub pages (LLM body + deterministic file map).
        11. Add stale: true to deleted/renamed vault pages + log entries.
        12. regenerate_dependencies_index + update_index.
        13. Final append_log summary.
        14. Return ScanResult.

    Args:
        vault_path:   Path to the wiki vault root (None → env var / git heuristic).
        no_file_map:  Skip per-workspace file-map generation (faster on huge repos).
        max_depth:    Max directory depth for file map section headers.

    Returns:
        ScanResult with added, updated, deleted, renamed, errors, state_gate.
    """
    # Step 1: resolve wiki and repo
    wiki, repo = resolve_wiki_and_repo(vault_path)

    # Step 2: read layout block
    pinned: list[dict] | None = None
    for schema_name in ("CLAUDE.md", "AGENTS.md"):
        layout = read_layout(wiki / schema_name)
        if layout and layout.get("containers"):
            pinned = layout.get("containers", [])
            break

    # Step 3: discover workspaces
    workspaces = discover_workspaces(repo, pinned_containers=pinned)

    # Step 4: build file_map per workspace
    if not no_file_map:
        for w in workspaces:
            pkg_dir = repo / w["path"]
            fm = build_file_map(pkg_dir, max_depth=max_depth)
            if fm is not None:
                w["file_map"] = fm

    # Step 5: load existing vault pages
    existing = _load_existing_pages(wiki)

    # Step 6: attach changed files since last sync
    attach_changed_files(workspaces, existing, repo)

    # Step 7: compute diff
    diff = compute_diff(workspaces, existing)

    # Step 8: compute state gate
    state_gate = compute_state_gate(repo)

    # Build workspace lookup by unscoped name for post-processing
    from vault_io.scan_monorepo import unscope
    ws_by_name = {unscope(w["name"]): w for w in workspaces}

    # Step 9: scanner fan-out
    # Items = new packages + unchanged packages with changed files
    fan_items: list[dict] = []
    for name in diff["new"]:
        if name in ws_by_name:
            fan_items.append(ws_by_name[name])
    for name in diff["unchanged"]:
        if name in ws_by_name:
            w = ws_by_name[name]
            changed = w.get("changed_files")
            if changed:  # non-empty list means files changed
                fan_items.append(w)

    cfg = load_role_config("scanner")
    pool = SubagentPool(trace_dir=wiki / ".code-wiki" / "traces")
    scanner_llm = make_llm("scanner")

    async def generate_stub(pkg: dict) -> str:
        prompt = build_stub_prompt(pkg, no_file_map=no_file_map)
        msgs = [
            SystemMessage(content=SCANNER_SYSTEM),
            HumanMessage(content=prompt),
        ]
        resp = await scanner_llm.ainvoke(msgs)
        return resp.content

    fan_result: FanOutResult = await pool.run_all(
        items=fan_items,
        task=generate_stub,
        role="scanner",
        model_id=cfg["model_id"],
        max_concurrency=cfg["max_concurrency"],
    )

    # Step 10: write successful stub pages
    added: list[str] = []
    updated: list[str] = []

    for pkg, llm_body in fan_result.successes:
        pkg_name = unscope(pkg["name"])
        vault_page_rel = pkg.get("vault_path", f"packages/{pkg_name}/{pkg_name}.md")
        page_path = wiki / vault_page_rel
        page_path.parent.mkdir(parents=True, exist_ok=True)

        # Deterministic file map append (RESEARCH Risk 5)
        pkg_dir = repo / pkg["path"]
        file_map_text = ""
        if not no_file_map:
            fm = build_file_map(pkg_dir, max_depth=max_depth)
            if fm is not None:
                file_map_text = "\n\n" + fm

        final_page = llm_body + file_map_text
        page_path.write_text(final_page, encoding="utf-8")

        if pkg_name in diff["new"]:
            added.append(pkg_name)
        else:
            updated.append(pkg_name)

    # Collect errors
    errors: list[str] = [
        f"{unscope(err.item['name'])}: {err.exception}"
        for err in fan_result.errors
    ]

    # Step 11: stale-tag deleted packages
    for pkg_name in diff["deleted"]:
        existing_rec = existing.get(pkg_name)
        if existing_rec:
            page_path = wiki / existing_rec["vault_path"]
            _add_stale_tag(page_path)
            append_log(wiki, "scan", f"marked stale: {pkg_name}", detail=None)
            logger.info("Marked stale: %s", pkg_name)

    # stale-tag renamed packages (old side)
    for rename_pair in diff["renamed"]:
        old_name = rename_pair[0]
        existing_rec = existing.get(old_name)
        if existing_rec:
            page_path = wiki / existing_rec["vault_path"]
            _add_stale_tag(page_path)
            new_name = rename_pair[1] if len(rename_pair) > 1 else "unknown"
            append_log(wiki, "scan", f"marked stale: {old_name} (renamed to {new_name})", detail=None)
            logger.info("Marked stale (renamed): %s -> %s", old_name, new_name)

    # Step 12: regenerate indexes
    regenerate_dependencies_index(wiki, workspaces)
    try:
        update_index(wiki)
    except Exception as exc:
        logger.warning("update_index failed (non-fatal): %s", exc)

    # Step 13: final log entry
    n_added = len(added)
    n_updated = len(updated)
    n_deleted = len(diff["deleted"])
    append_log(
        wiki,
        "scan",
        f"scan complete: +{n_added} ~{n_updated} -{n_deleted}",
        detail=None,
    )

    return ScanResult(
        added=added,
        updated=updated,
        deleted=diff["deleted"],
        renamed=diff["renamed"],
        errors=errors,
        state_gate=state_gate,
    )
