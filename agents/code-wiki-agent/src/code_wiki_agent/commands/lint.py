from __future__ import annotations

"""Lint command — mechanical + semantic health-check of a Code Wiki.

Public API:
    LintResult              — dataclass: all 18 lint finding fields
    LINTER_PAGE_QUALITY_SYSTEM  — system prompt for page-quality linter role
    LINTER_ADR_CHAIN_SYSTEM     — system prompt for ADR-chain linter role
    LINTER_STALE_CLAIMS_SYSTEM  — system prompt for stale-claims linter role
    run_lint(vault_path, stale_days, log_gap_days)  — end-to-end lint pipeline

Mechanical checks (ported verbatim from lint_wiki.py:scan()):
  - orphans, broken wikilinks (placeholder-filtered), stale pages, missing frontmatter
  - duplicate titles, log gaps, code-drift (packages vs vault)
  - 7 specialized drift modules: container, dependency, domain, file_map,
    package_sync, source_sync, workflow_hints

Semantic checks (3 parallel linter subagents via SubagentPool):
  - page_quality: content quality, contradictions, completeness
  - adr_chain: ADR numbering, status chains, orphaned decisions
  - stale_claims: outdated claims relative to known source paths

Per D-10: NO write-back to vault. run_lint is read-only.
"""

import datetime as dt
import logging
from collections import defaultdict
from dataclasses import dataclass, field
from pathlib import Path

from langchain_core.messages import HumanMessage, SystemMessage
from model_adapter.loader import load_role_config, make_llm
from subagent_runtime.pool import FanOutResult, PerItemError, SubagentPool
from vault_io._workspace import resolve_wiki_and_repo
from vault_io.layout_io import read_layout
from vault_io.lint.common import (
    LOG_ENTRY_RE,
    WIKILINK_RE,
    _is_placeholder_target,
    parse_frontmatter,
    strip_code,
    strip_frontmatter,
)
from vault_io.lint.container import check as check_container_drift
from vault_io.lint.dependency import check as check_dependency_layer
from vault_io.lint.domain import check as check_domain_placement
from vault_io.lint.file_map import check as check_file_map_drift
from vault_io.lint.package_sync import check as check_package_sync_drift
from vault_io.lint.source_sync import check as check_source_sync_drift
from vault_io.lint.workflow_hints import check as check_workflow_hints

logger = logging.getLogger(__name__)

# Tops that get full lint treatment (orphans, stale, missing-fm checks).
# Ported verbatim from lint_wiki.py (line 59 — note: upstream uses {"wiki", "work"},
# but the vault top-level is "wiki" which contains all category dirs; in the new
# architecture the wiki root IS the vault path, so LINTED_TOPS covers the
# category dirs directly: concepts, packages, apps, domains, adrs, work).
LINTED_TOPS = {"wiki", "work", "concepts", "packages", "apps", "domains", "adrs"}

# Sentinel used by upstream for skipped dict checks; preserved for serialization compat
_SKIPPED: dict = {"skipped": True}

# ---------------------------------------------------------------------------
# Semantic linter system prompts
# ---------------------------------------------------------------------------

LINTER_PAGE_QUALITY_SYSTEM = """\
You are a code wiki quality linter. Review the provided wiki pages and identify
quality issues. Report one finding per line in plain text. Focus on:
- Pages with vague or unhelpful summaries (under 10 words, or obviously placeholder)
- Pages that contradict each other about the same fact
- Pages whose body content is empty or near-empty (under 3 sentences)
- Pages with broken [[wikilink]] syntax (malformed bracket patterns)
- Pages missing a clear "## Overview" or "## Summary" section
If no quality issues are found, output exactly: No page quality issues found.
Do not output JSON, lists with bullets, or markdown formatting — one plain text finding per line only.
"""

LINTER_ADR_CHAIN_SYSTEM = """\
You are a code wiki ADR (Architecture Decision Record) chain linter. Review the
provided ADR pages and identify chain integrity issues. Report one finding per line
in plain text. Focus on:
- ADRs with status "superseded" that don't link to the superseding ADR
- ADRs with status "deprecated" that lack a replacement reference
- ADR numbers that appear to be out of sequence (gaps in numbering)
- ADRs referencing another ADR that does not appear in the provided set
- ADRs whose decision is contradicted by another ADR without a superseded relationship
If no ADR chain issues are found, output exactly: No ADR chain issues found.
Do not output JSON, lists with bullets, or markdown formatting — one plain text finding per line only.
"""

LINTER_STALE_CLAIMS_SYSTEM = """\
You are a code wiki stale-claims linter. Review the provided wiki pages and identify
claims that may be outdated based on their source_path or package_path frontmatter.
Report one finding per line in plain text. Focus on:
- Pages whose frontmatter declares a source_path but the body describes behavior
  that sounds like it may have changed (version numbers, removed APIs, renamed modules)
- Pages with "TODO", "FIXME", "WIP", or "placeholder" in the body (unresolved debt)
- Pages whose summary claims the package does something the body text contradicts
- Pages where the "updated" date is more than 180 days ago AND the body contains
  claims about "current" or "latest" state
If no stale claim issues are found, output exactly: No stale claim issues found.
Do not output JSON, lists with bullets, or markdown formatting — one plain text finding per line only.
"""


# ---------------------------------------------------------------------------
# LintResult dataclass
# ---------------------------------------------------------------------------


@dataclass
class LintResult:
    """Result of a run_lint() call.

    Fields map to the shape of lint_wiki.py:scan() return dict, extended with
    semantic_findings and errors for the semantic fan-out pass.
    """

    wiki: str
    total_pages: int
    orphans: list[str] = field(default_factory=list)
    broken_links: list[tuple[str, str]] = field(default_factory=list)
    stale: list[tuple[str, str]] = field(default_factory=list)
    missing_frontmatter: list[str] = field(default_factory=list)
    duplicate_titles: dict[str, list[str]] = field(default_factory=dict)
    log_gap: dict | None = None
    code_drift: dict = field(default_factory=lambda: _SKIPPED.copy())
    container_drift: list[str] = field(default_factory=list)
    source_sync_drift: list[str] = field(default_factory=list)
    file_map_drift: list[str] = field(default_factory=list)
    package_sync_drift: list[str] = field(default_factory=list)
    domain_placement: list[str] = field(default_factory=list)
    workflow_hints: list[str] = field(default_factory=list)
    dependency_layer: list[str] | None = None
    semantic_findings: dict[str, list[str]] = field(default_factory=dict)
    errors: list[str] = field(default_factory=list)


# ---------------------------------------------------------------------------
# Private: _mechanical_pass — port of lint_wiki.py:scan() lines 77-331
# ---------------------------------------------------------------------------


def _mechanical_pass(
    wiki: Path,
    workspace: Path,
    stale_days: int,
    log_gap_days: int,
) -> dict:
    """Port of lint_wiki.py:scan() mechanical section.

    Walks the workspace tree, builds a link graph, detects orphans/broken links/
    stale pages/missing frontmatter/duplicate titles/log gaps.

    Returns a dict with all mechanical fields matching LintResult field names.
    Import swaps: lattice_wiki_core.* → vault_io.*
    Logic ported verbatim from lint_wiki.py:scan() lines 77-331.
    """
    pages: dict = {}
    link_targets: set[str] = set()
    inbound: dict[str, set] = defaultdict(set)
    outbound: dict[str, set] = defaultdict(set)

    for md in workspace.rglob("*.md"):
        rel = md.relative_to(workspace)
        # Exclude any path that has a dotdir component (.graph/, .obsidian/, etc.)
        if any(part.startswith(".") for part in rel.parts):
            continue
        if rel.name in {"log.md"}:
            continue
        top = rel.parts[0] if rel.parts else ""
        # Skip work/archived/ — lifecycle is owned by lattice-work
        if top == "work" and len(rel.parts) >= 2 and rel.parts[1] == "archived":
            continue
        key = str(rel).replace("\\", "/")[:-3]
        # Add to link_targets regardless of whether it's an index page
        link_targets.add(key)
        # Skip adding index.md to pages dict for orphan/stale/frontmatter checks
        if rel.name == "index.md":
            continue
        text = md.read_text(encoding="utf-8", errors="replace")
        fm = parse_frontmatter(text)
        pages[key] = {
            "path": key + ".md",
            "fm": fm,
            "text": text,
            "linted": top in LINTED_TOPS,
            "is_work": top == "work",
        }

    stems = {Path(k).name: k for k in pages}
    for key, page in pages.items():
        scan_text = strip_code(strip_frontmatter(page["text"]))
        for m in WIKILINK_RE.finditer(scan_text):
            target = m.group(1).strip()
            if target.endswith(".md"):
                target = target[:-3]
            if target in link_targets:
                outbound[key].add(target)
                inbound[target].add(key)
            elif (target + "/" + Path(target).name) in link_targets:
                # [[<container>/<name>]] resolves to <container>/<name>/<name>.md
                resolved = target + "/" + Path(target).name
                outbound[key].add(resolved)
                inbound[resolved].add(key)
            elif "/" not in target and Path(target).name in stems:
                # Bare-filename shorthand: [[my-pkg]] resolves to any page named my-pkg.
                resolved = stems[Path(target).name]
                outbound[key].add(resolved)
                inbound[resolved].add(key)
            else:
                if not _is_placeholder_target(target):
                    outbound[key].add(f"__BROKEN__:{target}")

    # Parse outbound links from index.md files so that:
    # (a) pages only linked from an index are not flagged as orphans, and
    # (b) broken links inside index.md files are reported.
    for md in workspace.rglob("*.md"):
        rel = md.relative_to(workspace)
        if rel.name != "index.md":
            continue
        if any(part.startswith(".") for part in rel.parts):
            continue
        top = rel.parts[0] if rel.parts else ""
        if top == "work" and len(rel.parts) >= 2 and rel.parts[1] == "archived":
            continue
        idx_key = str(rel).replace("\\", "/")[:-3]
        text = md.read_text(encoding="utf-8", errors="replace")
        scan_text = strip_code(strip_frontmatter(text))
        for m in WIKILINK_RE.finditer(scan_text):
            target = m.group(1).strip()
            if target.endswith(".md"):
                target = target[:-3]
            if target in link_targets:
                if target in pages:
                    inbound[target].add(idx_key)
            elif (target + "/" + Path(target).name) in link_targets:
                resolved = target + "/" + Path(target).name
                if resolved in pages:
                    inbound[resolved].add(idx_key)
            elif "/" not in target and Path(target).name in stems:
                resolved = stems[Path(target).name]
                inbound[resolved].add(idx_key)
            else:
                if not _is_placeholder_target(target):
                    outbound[idx_key].add(f"__BROKEN__:{target}")

    today = dt.date.today()
    stale_cutoff = today - dt.timedelta(days=stale_days)

    orphans = sorted(
        k for k, p in pages.items()
        if p["linted"] and not p["is_work"] and not inbound.get(k)
    )
    broken_links = []
    for src, targets in outbound.items():
        for t in targets:
            if t.startswith("__BROKEN__:"):
                broken_links.append((src, t.split(":", 1)[1]))
    broken_links.sort()

    stale = []
    missing_fm = []
    titles: dict[str, list[str]] = defaultdict(list)
    for key, page in pages.items():
        if not page["linted"]:
            continue
        fm = page["fm"]
        title = fm.get("title") or Path(key).name
        titles[title].append(key)
        required = {"title", "category", "summary"}
        if not required.issubset(fm.keys()):
            missing_fm.append(key)
        updated = fm.get("updated")
        if updated:
            try:
                d = dt.date.fromisoformat(updated)
                if d < stale_cutoff:
                    stale.append((key, updated))
            except ValueError:
                pass
    duplicate_titles = {t: ks for t, ks in titles.items() if len(ks) > 1}

    # Log gap detection
    log_path = wiki / "log.md"
    log_gap = None
    if log_path.exists():
        log_text = log_path.read_text(encoding="utf-8", errors="replace")
        dates = [dt.date.fromisoformat(m) for m in LOG_ENTRY_RE.findall(log_text)]
        if dates:
            last = max(dates)
            gap = (today - last).days
            if gap > log_gap_days:
                log_gap = {"last_entry": last.isoformat(), "days_ago": gap}
        else:
            log_gap = {"last_entry": None, "days_ago": None}

    return {
        "pages": pages,
        "orphans": orphans,
        "broken_links": broken_links,
        "stale": stale,
        "missing_frontmatter": sorted(missing_fm),
        "duplicate_titles": duplicate_titles,
        "log_gap": log_gap,
        "total_pages": len(pages),
    }


# ---------------------------------------------------------------------------
# Private: _module_pass — call all 7 drift-check modules
# ---------------------------------------------------------------------------


def _module_pass(repo: Path | None, wiki: Path, workspace: Path, pages: dict) -> dict:
    """Call all 7 mechanical lint modules and return their findings.

    Modules that require a repo path are skipped (return _SKIPPED) when repo is None,
    matching lint_wiki.py:scan() behavior (lines 283-311).
    """
    if repo is not None:
        container_drift = check_container_drift(repo, wiki)
        source_sync_drift = check_source_sync_drift(repo, wiki)
        file_map_drift = check_file_map_drift(repo, pages)
        package_sync_drift = check_package_sync_drift(repo, wiki)
    else:
        container_drift = []
        source_sync_drift = []
        file_map_drift = []
        package_sync_drift = []
    domain_placement = check_domain_placement(pages)
    workflow_hints_issues = check_workflow_hints(pages, workspace)
    # dependency_layer is optional — pass pages only, no workspaces (skip workspaces arg)
    dependency_layer = check_dependency_layer(pages)

    # Code-drift check (packages on disk vs vault) — skipped when repo is None
    code_drift = _SKIPPED.copy()
    if repo is not None:
        try:
            from vault_io.scan_monorepo import discover_workspaces, unscope

            layout = read_layout(wiki / "CLAUDE.md")
            pinned_containers = layout.get("containers") if layout else None
            workspaces = discover_workspaces(repo, pinned_containers=pinned_containers)
            disk_names = {unscope(w["name"]) for w in workspaces}
            vault_pkg_pages = {
                k: p
                for k, p in pages.items()
                if p["fm"].get("category") in ("package", "app")
                and Path(k).parent.name == Path(k).name
            }
            vault_names = {Path(k).name for k in vault_pkg_pages}
            planned_names = {
                Path(k).name
                for k, p in vault_pkg_pages.items()
                if p["fm"].get("status") == "planned"
            }
            code_drift = {
                "packages_on_disk": len(disk_names),
                "packages_in_vault": len(vault_names),
                "missing_in_vault": sorted(disk_names - vault_names),
                "orphaned_in_vault": sorted((vault_names - disk_names) - planned_names),
                "planned_in_vault": sorted(planned_names),
            }
        except Exception as exc:
            logger.debug("Code-drift check failed: %s", exc)

    return {
        "container_drift": container_drift,
        "source_sync_drift": source_sync_drift,
        "file_map_drift": file_map_drift,
        "package_sync_drift": package_sync_drift,
        "domain_placement": domain_placement,
        "workflow_hints": workflow_hints_issues,
        "dependency_layer": dependency_layer,
        "code_drift": code_drift,
    }


# ---------------------------------------------------------------------------
# Private: build_linter_input — format pages for LLM
# ---------------------------------------------------------------------------


def _build_linter_input(pages_input: list[dict]) -> str:
    """Build a human message string from a list of page dicts for a linter group."""
    if not pages_input:
        return "(no pages in this category)\n"
    lines: list[str] = []
    for page in pages_input:
        key = page.get("key", "unknown")
        fm = page.get("fm", {})
        text = page.get("text", "")
        lines.append(f"--- Page: {key} ---")
        if fm:
            lines.append(f"title: {fm.get('title', '(none)')}")
            lines.append(f"category: {fm.get('category', '(none)')}")
            lines.append(f"summary: {fm.get('summary', '(none)')}")
            lines.append(f"updated: {fm.get('updated', '(none)')}")
        # Include first 800 chars of body
        body_preview = strip_frontmatter(text)[:800]
        if body_preview:
            lines.append(body_preview)
        lines.append("")
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Private: _semantic_pass — fan-out 3 linter groups via SubagentPool
# ---------------------------------------------------------------------------


async def _semantic_pass(
    wiki: Path,
    pages: dict,
    pool: SubagentPool,
    cfg: dict,
) -> tuple[dict[str, list[str]], list[str]]:
    """Run 3 semantic linter groups in parallel; return (findings_dict, errors)."""
    # Build page lists for each group
    all_page_list = [
        {"key": k, "fm": p["fm"], "text": p["text"]}
        for k, p in pages.items()
        if p.get("linted") and not p.get("is_work")
    ]

    # page_quality: sample up to first 20 non-work pages
    pages_sample = all_page_list[:20]

    # adr_chain: all pages under adrs/
    adr_pages = [pg for pg in all_page_list if pg["key"].startswith("adrs/")]

    # stale_claims: pages with source_path or package_path frontmatter
    pages_with_source = [
        pg for pg in all_page_list
        if pg["fm"].get("source_path") or pg["fm"].get("package_path")
    ]

    semantic_groups = [
        ("page_quality", LINTER_PAGE_QUALITY_SYSTEM, pages_sample),
        ("adr_chain", LINTER_ADR_CHAIN_SYSTEM, adr_pages),
        ("stale_claims", LINTER_STALE_CLAIMS_SYSTEM, pages_with_source),
    ]

    async def run_linter_group(group_tuple: tuple) -> list[str]:
        name, system_prompt, pages_input = group_tuple
        if not pages_input:
            return []
        linter_llm = make_llm("linter")
        msgs = [
            SystemMessage(content=system_prompt),
            HumanMessage(content=_build_linter_input(pages_input)),
        ]
        response = await linter_llm.ainvoke(msgs)
        content = response.content if hasattr(response, "content") else str(response)
        # Parse response: one finding per non-empty line
        findings = [line.strip() for line in content.splitlines() if line.strip()]
        return findings

    fan_result: FanOutResult = await pool.run_all(
        items=semantic_groups,
        task=run_linter_group,
        role="linter",
        model_id=cfg["model_id"],
        max_concurrency=cfg.get("max_concurrency", 3),
    )

    semantic_findings: dict[str, list[str]] = {}
    errors: list[str] = []

    for group_tuple, findings in fan_result.successes:
        name = group_tuple[0]
        semantic_findings[name] = findings

    for per_item_error in fan_result.errors:
        group_tuple = per_item_error.item
        name = group_tuple[0] if isinstance(group_tuple, tuple) else str(group_tuple)
        errors.append(f"{name}: {per_item_error.exception}")

    return semantic_findings, errors


# ---------------------------------------------------------------------------
# Public: run_lint
# ---------------------------------------------------------------------------


async def run_lint(
    vault_path: Path | None = None,
    stale_days: int = 90,
    log_gap_days: int = 14,
) -> LintResult:
    """End-to-end lint: mechanical pass (inline scan port) + 7 module checks + semantic fan-out.

    Steps:
        1. Resolve wiki and repo from vault_path.
        2. MECHANICAL inline pass — port of lint_wiki.py:scan() lines 77-331.
        3. MECHANICAL module pass — call all 7 drift-check modules.
        4. SEMANTIC pass — 3-group linter fan-out via SubagentPool.
        5. Return LintResult (NO write-back to vault — D-10).

    Args:
        vault_path:    Path to the wiki vault root (None → env var / git heuristic).
        stale_days:    Pages not updated within this many days are flagged as stale (default 90).
        log_gap_days:  Flag if log.md has no entry within this many days (default 14).

    Returns:
        LintResult with all mechanical and semantic findings.
    """
    # Step 1: resolve wiki and repo
    wiki, repo = resolve_wiki_and_repo(vault_path)
    workspace = wiki.parent

    # Step 2: mechanical inline pass
    mech = _mechanical_pass(wiki, workspace, stale_days, log_gap_days)
    pages = mech["pages"]

    # Step 3: 7 module checks
    mod = _module_pass(repo, wiki, workspace, pages)

    # Step 4: semantic pass
    pool = SubagentPool(trace_dir=wiki / ".code-wiki" / "traces")
    cfg = load_role_config("linter")
    semantic_findings, errors = await _semantic_pass(wiki, pages, pool, cfg)

    return LintResult(
        wiki=str(wiki),
        total_pages=mech["total_pages"],
        orphans=mech["orphans"],
        broken_links=mech["broken_links"],
        stale=mech["stale"],
        missing_frontmatter=mech["missing_frontmatter"],
        duplicate_titles=mech["duplicate_titles"],
        log_gap=mech["log_gap"],
        code_drift=mod["code_drift"],
        container_drift=mod["container_drift"],
        source_sync_drift=mod["source_sync_drift"],
        file_map_drift=mod["file_map_drift"],
        package_sync_drift=mod["package_sync_drift"],
        domain_placement=mod["domain_placement"],
        workflow_hints=mod["workflow_hints"],
        dependency_layer=mod["dependency_layer"],
        semantic_findings=semantic_findings,
        errors=errors,
    )
