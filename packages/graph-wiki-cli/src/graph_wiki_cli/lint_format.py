"""Shared text renderers for lint results.

Single source of truth for the `gw wiki lint`, `gw work lint`, and `gw lint`
text output so the surfaces cannot drift. Each function returns a list of
lines; callers echo them.
"""

from __future__ import annotations

from typing import Any


def format_wiki_lint(result: Any) -> list[str]:
    """Render a LintResult as the wiki-lint multi-section report (work-free)."""
    lines: list[str] = []
    lines.append(f"Code Wiki lint — {result.wiki}")
    lines.append(f"Total pages: {result.total_pages}")
    lines.append(f"Open proposals: {result.open_proposals}")
    lines.append("")

    def _section(label: str, items: list) -> None:
        sym = "OK" if not items else "WARN"
        lines.append(f"[{sym}] {label}: {len(items)}")
        for item in items[:20]:
            lines.append(f"   - {item}")
        lines.append("")

    _section("Orphans", result.orphans)
    broken = [f"{src} -> [[{tgt}]]" for src, tgt in result.broken_links]
    _section("Broken wikilinks", broken)
    stale_items = [f"{p} (updated {d})" for p, d in result.stale]
    _section("Stale pages", stale_items)
    _section("Missing frontmatter", result.missing_frontmatter)
    _section("Source path drift", result.source_path_drift)

    if result.duplicate_titles:
        lines.append(f"[WARN] Duplicate titles: {len(result.duplicate_titles)}")
        for title, keys in list(result.duplicate_titles.items())[:10]:
            lines.append(f"   - '{title}': {keys}")
        lines.append("")
    else:
        lines.append("[OK] Duplicate titles: 0\n")

    if result.log_gap:
        lines.append(
            f"[WARN] Log gap: last entry {result.log_gap.get('last_entry')} "
            f"({result.log_gap.get('days_ago')} days ago)\n"
        )
    else:
        lines.append("[OK] Log gap: recent\n")

    _section("File map drift", result.file_map_drift)
    _section("Package sync drift", result.package_sync_drift)
    _section("Domain placement", result.domain_placement)
    _section("Workflow hints", result.workflow_hints)
    _section("Concept kinds", result.concept_kind)
    _section("Scanner heading drift", result.scanner_heading_drift)

    for group, findings in result.semantic_findings.items():
        _section(f"Semantic: {group}", findings)

    if result.guidance_lint_findings:
        guidance_items = [
            f"[{f['severity']}] {f['slug']}: {f['rule_id']} — {f['message']}" for f in result.guidance_lint_findings
        ]
        _section("Guidance frontmatter", guidance_items)
    else:
        lines.append("[OK] Guidance frontmatter: 0\n")

    if result.obsidian_render_findings:
        by_rule: dict[str, list[str]] = {}
        for f in result.obsidian_render_findings:
            by_rule.setdefault(f["rule_id"], []).append(f"[{f['severity']}] {f['message']}")
        items = [line for rule in sorted(by_rule) for line in by_rule[rule]]
        _section("Obsidian render", items)
    else:
        lines.append("[OK] Obsidian render: 0\n")

    return lines


def format_work_lint(result: Any) -> list[str]:
    """Render a WorkLintResult as the work-lifecycle lint report."""
    lines: list[str] = [f"Items checked: {result.total_items}"]
    for f in result.findings:
        lines.append(f"  [{f['severity']}] {f['slug']}: {f['rule_id']} — {f['message']}")
    if not result.findings:
        lines.append("  [ok] No findings.")
    return lines
