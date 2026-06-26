"""Lint command — mechanical + semantic health-check of a Code Wiki.

Public API:
    LintResult              — dataclass: all lint finding fields
    run_lint(workspace_path, stale_days, log_gap_days)  — end-to-end lint pipeline

Linter system prompts are constructed inline via
`build_linter_{page_quality,adr_chain,stale_claims}_system(project_context=...)`
where `project_context` is the rendered output of
`render_project_context(wiki)` — see CTX-03.

Mechanical checks (delegated to wiki_io.lint_wiki.mechanical_scan, the single
canonical scanner shared with lint_wiki.scan()):
  - orphans, broken wikilinks (placeholder-filtered), stale pages, missing frontmatter
  - duplicate titles, log gaps, code-drift (packages vs vault)
  - specialized drift modules: dependency, domain, file_map,
    package_sync, workflow_hints

Semantic checks (3 parallel linter subagents via SubagentPool):
  - page_quality: content quality, contradictions, completeness
  - adr_chain: ADR numbering, status chains, orphaned decisions
  - stale_claims: outdated claims relative to known source paths

Per D-10: NO write-back to vault. run_lint is read-only.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from pathlib import Path

from langchain_core.messages import HumanMessage, SystemMessage
from subagent_runtime.pool import FanOutResult, SubagentPool, TaskResult
from wiki_io._workspace import resolve_wiki_and_repo
from wiki_io.lint.common import strip_frontmatter
from wiki_io.lint.concept_kind import check as check_concept_kind
from wiki_io.lint.dependency import check as check_dependency_layer
from wiki_io.lint.domain import check as check_domain_placement
from wiki_io.lint.file_map import check as check_file_map_drift
from wiki_io.lint.package_sync import check as check_package_sync_drift
from wiki_io.lint.scanner_heading import check as check_scanner_heading
from wiki_io.lint.workflow_hints import check as check_workflow_hints
from wiki_io.lint_wiki import mechanical_scan
from wiki_io.proposals import list_proposals
from workspace_io.paths import graph_dir

from graph_wiki_core.roles import load_role_config, make_llm

logger = logging.getLogger(__name__)

# Sentinel used by upstream for skipped dict checks; preserved for serialization compat
_SKIPPED: dict = {"skipped": True}

# ---------------------------------------------------------------------------
# Semantic linter prompt builders (wired with project_context per CTX-03)
# ---------------------------------------------------------------------------

from graph_wiki_core.prompts.linter import (  # noqa: E402
    build_linter_adr_chain_system,
    build_linter_page_quality_system,
    build_linter_stale_claims_system,
)
from graph_wiki_core.prompts.project_context import render_project_context  # noqa: E402

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
    missing_tokens: list[str] = field(default_factory=list)
    source_path_drift: list[str] = field(default_factory=list)
    duplicate_titles: dict[str, list[str]] = field(default_factory=dict)
    log_gap: dict | None = None
    code_drift: dict = field(default_factory=lambda: _SKIPPED.copy())
    file_map_drift: list[str] = field(default_factory=list)
    package_sync_drift: list[str] = field(default_factory=list)
    domain_placement: list[str] = field(default_factory=list)
    workflow_hints: list[str] = field(default_factory=list)
    concept_kind: list[str] = field(default_factory=list)
    dependency_layer: list[str] | None = None
    scanner_heading_drift: list[str] = field(default_factory=list)
    semantic_findings: dict[str, list[str]] = field(default_factory=dict)
    errors: list[str] = field(default_factory=list)
    open_proposals: int = 0
    guidance_lint_findings: list[dict] = field(default_factory=list)


# ---------------------------------------------------------------------------
# Private: _module_pass — call all drift-check modules
# ---------------------------------------------------------------------------


def _module_pass(repo: Path | None, wiki: Path, workspace: Path, pages: dict) -> dict:
    """Call all mechanical lint modules and return their findings.

    Modules that require a repo path are skipped (return _SKIPPED) when repo is None,
    matching lint_wiki.py:scan() behavior (lines 283-311).
    """
    if repo is not None:
        file_map_drift = check_file_map_drift(repo, pages)
        package_sync_drift = check_package_sync_drift(repo, wiki)
    else:
        file_map_drift = []
        package_sync_drift = []
    domain_placement = check_domain_placement(pages)
    workflow_hints_issues = check_workflow_hints(pages, workspace)
    concept_kind_issues = check_concept_kind(pages, wiki)
    # dependency_layer is optional — pass pages only, no workspaces (skip workspaces arg)
    dependency_layer = check_dependency_layer(pages)
    scanner_heading_drift = check_scanner_heading(pages)

    # Code-drift check (packages on disk vs vault) — skipped when repo is None
    code_drift = _SKIPPED.copy()
    if repo is not None:
        try:
            from wiki_io.scan_monorepo import _discover_heuristic, unscope
            from workspace_io.config import resolve as _resolve_cfg

            # Container-free discovery: heuristic walk of on-disk package dirs.
            # In a multi-repo workspace, on-disk packages span every member root,
            # so enumerate the UNION across all members (``members or [repo]``
            # keeps single-repo byte-identical: iterate the one repo).
            members = list(_resolve_cfg(repo, require_manifest=False).members) or [repo]
            disk_names = set()
            for member in members:
                workspaces = _discover_heuristic(member)
                disk_names |= {unscope(w["name"]) for w in workspaces}
            vault_pkg_pages = {
                k: p
                for k, p in pages.items()
                if p["fm"].get("category") in ("package", "app") and Path(k).parent.name == Path(k).name
            }
            vault_names = {Path(k).name for k in vault_pkg_pages}
            planned_names = {Path(k).name for k, p in vault_pkg_pages.items() if p["fm"].get("status") == "planned"}
            code_drift = {
                "packages_on_disk": len(disk_names),
                "packages_in_vault": len(vault_names),
                "missing_in_vault": sorted(disk_names - vault_names),
                "orphaned_in_vault": sorted((vault_names - disk_names) - planned_names),
                "planned_in_vault": sorted(planned_names),
            }
        except Exception as exc:
            # warning (not debug): a swallowed failure here silently drops the
            # whole code-drift pass, so surface it in normal lint output.
            logger.warning("Code-drift check failed: %s", exc)

    return {
        "file_map_drift": file_map_drift,
        "package_sync_drift": package_sync_drift,
        "domain_placement": domain_placement,
        "workflow_hints": workflow_hints_issues,
        "concept_kind": concept_kind_issues,
        "dependency_layer": dependency_layer,
        "scanner_heading_drift": scanner_heading_drift,
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
    model_override: str | None = None,
    project_context: str = "",
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
    pages_with_source = [pg for pg in all_page_list if pg["fm"].get("source_path") or pg["fm"].get("package_path")]

    semantic_groups = [
        (
            "page_quality",
            build_linter_page_quality_system(project_context=project_context),
            pages_sample,
        ),
        (
            "adr_chain",
            build_linter_adr_chain_system(project_context=project_context),
            adr_pages,
        ),
        (
            "stale_claims",
            build_linter_stale_claims_system(project_context=project_context),
            pages_with_source,
        ),
    ]

    async def run_linter_group(group_tuple: tuple) -> TaskResult:
        name, system_prompt, pages_input = group_tuple
        if not pages_input:
            # Phase 16-02 G-01: empty group never invokes the LLM — no
            # usage_metadata exists; wrap empty findings list for contract
            # consistency.
            return TaskResult(value=[], response=None)
        linter_llm = make_llm("linter", model_override=model_override)
        msgs = [
            SystemMessage(content=system_prompt),
            HumanMessage(content=_build_linter_input(pages_input)),
        ]
        response = await linter_llm.ainvoke(msgs)
        content = response.content if hasattr(response, "content") else str(response)
        if not isinstance(content, str):
            raise RuntimeError(f"linter {name} returned non-text content")
        # Parse response: one finding per non-empty line
        findings = [line.strip() for line in content.splitlines() if line.strip()]
        # Phase 16-02 G-01: surface response.usage_metadata to pool trace.
        return TaskResult(value=findings, response=response)

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
    workspace_path: Path | None = None,
    stale_days: int = 90,
    log_gap_days: int = 14,
    model_override: str | None = None,
) -> LintResult:
    """End-to-end lint: mechanical pass (wiki_io.mechanical_scan) + module checks + semantic fan-out.

    Steps:
        1. Resolve wiki and repo from workspace_path.
        2. MECHANICAL pass — wiki_io.lint_wiki.mechanical_scan (canonical scanner).
        3. MECHANICAL module pass — call all drift-check modules.
        4. SEMANTIC pass — 3-group linter fan-out via SubagentPool.
        5. Return LintResult (NO write-back to vault — D-10).

    Args:
        workspace_path: Path to the wiki workspace root (None → env var / git heuristic).
        stale_days:     Pages not updated within this many days are flagged as stale (default 90).
        log_gap_days:   Flag if log.md has no entry within this many days (default 14).
        model_override: Bedrock model ID to use for the linter role instead of
                        the default from models.toml. Used by the sweep runner
                        for single-role-swap evaluation (D-06).

    Returns:
        LintResult with all mechanical and semantic findings.
    """
    # Step 1: resolve wiki and repo
    wiki, repo = resolve_wiki_and_repo(workspace_path)
    open_proposals = len(list_proposals(wiki, status="proposed"))
    project_ctx = render_project_context(wiki)
    if repo is None:
        repo = Path.cwd()
    workspace = wiki.parent

    # Step 2: mechanical pass — canonical scanner owned by wiki_io.lint_wiki
    mech = mechanical_scan(wiki, stale_days, log_gap_days)
    pages = mech["pages"]

    # Step 3: module checks
    mod = _module_pass(repo, wiki, workspace, pages)

    # Step 4: semantic pass
    pool = SubagentPool(trace_dir=graph_dir(wiki.parent) / "traces")
    cfg = load_role_config("linter")
    semantic_findings, errors = await _semantic_pass(
        wiki, pages, pool, cfg, model_override=model_override, project_context=project_ctx
    )

    # Guidance-layer mechanical lint (owned by guidance-io)
    from guidance_io.lint import run_lint as _run_guidance_lint

    guidance_findings = [
        {"rule_id": f.rule_id, "severity": f.severity, "slug": f.slug, "message": f.message}
        for f in _run_guidance_lint(workspace)
    ]
    for f in guidance_findings:
        if f["severity"] == "error":
            errors.append(f"{f['slug']}: [{f['rule_id']}] {f['message']}")

    return LintResult(
        wiki=str(wiki),
        total_pages=mech["total_pages"],
        orphans=mech["orphans"],
        broken_links=mech["broken_links"],
        stale=mech["stale"],
        missing_frontmatter=mech["missing_frontmatter"],
        missing_tokens=mech["missing_tokens"],
        source_path_drift=mech["source_path_drift"],
        duplicate_titles=mech["duplicate_titles"],
        log_gap=mech["log_gap"],
        code_drift=mod["code_drift"],
        file_map_drift=mod["file_map_drift"],
        package_sync_drift=mod["package_sync_drift"],
        domain_placement=mod["domain_placement"],
        workflow_hints=mod["workflow_hints"],
        concept_kind=mod["concept_kind"],
        dependency_layer=mod["dependency_layer"],
        scanner_heading_drift=mod["scanner_heading_drift"],
        semantic_findings=semantic_findings,
        errors=errors,
        open_proposals=open_proposals,
        guidance_lint_findings=guidance_findings,
    )
