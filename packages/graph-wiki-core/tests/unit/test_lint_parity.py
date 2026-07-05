"""Mechanical parity guard: gw lint vs the plugin's lint_wiki.scan().

Both surfaces must expose the same mechanical checks — `gw lint` via
LintResult (+ the separate WorkLintResult in LintAllResult) and
`/graph-wiki:lint` via wiki_io.lint_wiki.scan()'s return dict. This test
fails whenever either surface gains a mechanical check the other lacks,
which is the silent-skip drift this work item closed.

Lives in graph-wiki-core because both sides are importable here.
"""

from __future__ import annotations

from dataclasses import fields
from pathlib import Path

from graph_wiki_core.commands.lint import LintResult
from graph_wiki_core.commands.work import WorkLintResult
from wiki_io.lint_wiki import scan

# LintResult fields that are not mechanical checks: the Bedrock semantic
# fan-out and its plumbing. Everything else must have a scan() counterpart.
NON_MECHANICAL_FIELDS = {"semantic_findings", "errors", "open_proposals"}

# The lifecycle split: scan() delivers the work-lifecycle pass inline as
# scan()["work_lifecycle"] == {"total_items", "findings"}, while gw lint
# ships it as the separate WorkLintResult in LintAllResult (lint_all.py),
# not as a LintResult field. This is the one intentional shape difference.
SCAN_ONLY_KEYS = {"work_lifecycle"}


def test_mechanical_check_parity(tmp_path: Path) -> None:
    workspace = tmp_path / "workspace"
    wiki = workspace / "wiki"
    wiki.mkdir(parents=True)
    (wiki / "index.md").write_text("---\ntitle: Index\n---\n\nWelcome.\n", encoding="utf-8")

    result = scan(wiki, stale_days=90, log_gap_days=14)
    scan_keys = set(result)
    mechanical_fields = {f.name for f in fields(LintResult)} - NON_MECHANICAL_FIELDS

    missing_from_scan = mechanical_fields - scan_keys
    assert not missing_from_scan, (
        f"gw lint has mechanical checks the plugin's scan() lacks: {sorted(missing_from_scan)} — "
        "wire them into wiki_io.lint_wiki.scan() (see work item "
        "2026-07-04-lint-skill-drifted-from-gw-lint-...)"
    )

    extra_in_scan = scan_keys - mechanical_fields
    assert extra_in_scan == SCAN_ONLY_KEYS, (
        f"scan() has mechanical keys gw lint's LintResult lacks: {sorted(extra_in_scan - SCAN_ONLY_KEYS)} — "
        "add matching LintResult fields (or extend SCAN_ONLY_KEYS if the check "
        "intentionally ships outside LintResult, like work_lifecycle)"
    )


def test_work_lifecycle_shape_matches_work_lint_result(tmp_path: Path) -> None:
    """scan()['work_lifecycle'] mirrors WorkLintResult field-for-field, so the
    lifecycle split stays a shape difference, not a content difference."""
    workspace = tmp_path / "workspace"
    wiki = workspace / "wiki"
    wiki.mkdir(parents=True)
    (wiki / "index.md").write_text("---\ntitle: Index\n---\n\nWelcome.\n", encoding="utf-8")

    result = scan(wiki, stale_days=90, log_gap_days=14)
    assert set(result["work_lifecycle"]) == {f.name for f in fields(WorkLintResult)}
