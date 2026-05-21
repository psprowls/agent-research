from __future__ import annotations

"""Unit tests for per-role DivergenceCheck callables (EVAL-11).

All tests are deterministic and require no Bedrock access. They exercise
the DivergenceCheck.check callables against synthetic in-memory
AgentOutputProxy and tiny vault fixtures.
"""

from pathlib import Path

import pytest

from eval_harness.divergence.check import AgentOutputProxy, DivergenceCheck
from eval_harness.divergence.code_reader import (
    _GRAPH_WIKI_PREFIX_RE,
    _PATH_LINE_RE,
)
from eval_harness.divergence.librarian import LIBRARIAN_CHECKS
from eval_harness.divergence.ingestor import INGESTOR_CHECKS
from eval_harness.divergence.linter import LINTER_CHECKS
from eval_harness.divergence.scanner import SCANNER_CHECKS
from eval_harness.divergence.synthesizer import SYNTHESIZER_CHECKS


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _get_check(checks: list[DivergenceCheck], rule_id: str) -> DivergenceCheck:
    """Return the DivergenceCheck matching rule_id from a checks list."""
    for c in checks:
        if c.id == rule_id:
            return c
    raise KeyError(f"No check with id={rule_id!r} in list")


# ---------------------------------------------------------------------------
# Librarian checks — LIB-001 through LIB-004
# ---------------------------------------------------------------------------


def test_lib001_passes_on_resolved_wikilink(fixture_wiki_path: Path) -> None:
    """LIB-001 passes when all wikilinks in the answer resolve to existing vault pages."""
    check = _get_check(LIBRARIAN_CHECKS, "LIB-001-wikilink-resolves")
    # packages/lattice-wiki-core.md exists in the round-trip-vault fixture.
    output = AgentOutputProxy(answer="See [[packages/lattice-wiki-core]].")
    verdict = check.check(output, fixture_wiki_path)
    assert verdict.passed is True
    assert verdict.excerpt == ""


def test_lib001_fails_on_unresolved_wikilink(fixture_wiki_path: Path) -> None:
    """LIB-001 fails when a wikilink does not resolve; excerpt names the unresolved link."""
    check = _get_check(LIBRARIAN_CHECKS, "LIB-001-wikilink-resolves")
    output = AgentOutputProxy(answer="See [[nonexistent/page]].")
    verdict = check.check(output, fixture_wiki_path)
    assert verdict.passed is False
    assert "Unresolved" in verdict.excerpt
    assert "nonexistent/page" in verdict.excerpt


def test_lib001_passes_when_no_wikilinks(fixture_wiki_path: Path) -> None:
    """LIB-001 passes vacuously when the answer contains no wikilinks at all."""
    check = _get_check(LIBRARIAN_CHECKS, "LIB-001-wikilink-resolves")
    output = AgentOutputProxy(answer="No links here, just plain text.")
    verdict = check.check(output, fixture_wiki_path)
    assert verdict.passed is True


def test_lib002_passes_with_wikilink(fixture_wiki_path: Path) -> None:
    """LIB-002 passes when answer contains at least one wikilink citation."""
    check = _get_check(LIBRARIAN_CHECKS, "LIB-002-citation-present")
    output = AgentOutputProxy(answer="See [[packages/lattice-wiki-core]] for details.")
    verdict = check.check(output, fixture_wiki_path)
    assert verdict.passed is True


def test_lib002_passes_with_backtick_code_path(fixture_wiki_path: Path) -> None:
    """LIB-002 passes when answer contains a backtick code path citation."""
    check = _get_check(LIBRARIAN_CHECKS, "LIB-002-citation-present")
    output = AgentOutputProxy(answer="The bug is at `src/foo.py:42`.")
    verdict = check.check(output, fixture_wiki_path)
    assert verdict.passed is True


def test_lib002_fails_on_no_citation(fixture_wiki_path: Path) -> None:
    """LIB-002 fails when the answer has no citation of any kind."""
    check = _get_check(LIBRARIAN_CHECKS, "LIB-002-citation-present")
    output = AgentOutputProxy(answer="Just a plain answer with no links.")
    verdict = check.check(output, fixture_wiki_path)
    assert verdict.passed is False
    assert "No citation" in verdict.excerpt


def test_lib003_passes_with_path_wikilink(fixture_wiki_path: Path) -> None:
    """LIB-003 passes when wikilinks include a slash path prefix."""
    check = _get_check(LIBRARIAN_CHECKS, "LIB-003-no-slug-only-wikilinks")
    output = AgentOutputProxy(answer="See [[packages/lattice-wiki-core]] for the API.")
    verdict = check.check(output, fixture_wiki_path)
    assert verdict.passed is True


def test_lib003_fails_on_slug_only_wikilink(fixture_wiki_path: Path) -> None:
    """LIB-003 fails when a wikilink is a bare CamelCase slug with no path."""
    check = _get_check(LIBRARIAN_CHECKS, "LIB-003-no-slug-only-wikilinks")
    output = AgentOutputProxy(answer="See [[LatticeWikiCore]] for details.")
    verdict = check.check(output, fixture_wiki_path)
    assert verdict.passed is False
    assert "Slug-only" in verdict.excerpt
    assert "LatticeWikiCore" in verdict.excerpt


def test_lib004_passes_when_no_bare_paths(fixture_wiki_path: Path) -> None:
    """LIB-004 passes when code paths appear only inside backticks."""
    check = _get_check(LIBRARIAN_CHECKS, "LIB-004-code-path-format")
    output = AgentOutputProxy(answer="See `src/main.py:10` for the entry point.")
    verdict = check.check(output, fixture_wiki_path)
    assert verdict.passed is True


def test_lib004_fails_on_bare_code_path(fixture_wiki_path: Path) -> None:
    """LIB-004 fails when a code path appears outside backticks."""
    check = _get_check(LIBRARIAN_CHECKS, "LIB-004-code-path-format")
    output = AgentOutputProxy(answer="The bug is at src/core/runner.py:55 in main.")
    verdict = check.check(output, fixture_wiki_path)
    assert verdict.passed is False
    assert "Bare code path" in verdict.excerpt


# ---------------------------------------------------------------------------
# Ingestor checks — ING-001 through ING-004
# ---------------------------------------------------------------------------

_FULL_FRONTMATTER = """\
---
title: Example Package
category: package
page_type: package
target_slug: packages/example-package
summary: A test package page.
---

# Body text here.
"""


def test_ing001_passes_with_frontmatter(fixture_wiki_path: Path) -> None:
    """ING-001 passes when ingestor output contains YAML frontmatter delimiters."""
    check = _get_check(INGESTOR_CHECKS, "ING-001-frontmatter-present")
    output = AgentOutputProxy(answer=_FULL_FRONTMATTER)
    verdict = check.check(output, fixture_wiki_path)
    assert verdict.passed is True


def test_ing001_fails_without_frontmatter(fixture_wiki_path: Path) -> None:
    """ING-001 fails when the output has no --- delimiters."""
    check = _get_check(INGESTOR_CHECKS, "ING-001-frontmatter-present")
    output = AgentOutputProxy(answer="No frontmatter here, just prose.")
    verdict = check.check(output, fixture_wiki_path)
    assert verdict.passed is False
    assert "frontmatter" in verdict.excerpt.lower()


def test_ing001_fails_missing_closing_delimiter(fixture_wiki_path: Path) -> None:
    """ING-001 fails when the closing --- delimiter is missing."""
    check = _get_check(INGESTOR_CHECKS, "ING-001-frontmatter-present")
    output = AgentOutputProxy(answer="---\ntitle: foo\n# body without closing delimiter")
    verdict = check.check(output, fixture_wiki_path)
    assert verdict.passed is False


def test_ing002_passes_with_all_required_fields(fixture_wiki_path: Path) -> None:
    """ING-002 passes when all 5 required frontmatter fields are present."""
    check = _get_check(INGESTOR_CHECKS, "ING-002-required-fields")
    output = AgentOutputProxy(answer=_FULL_FRONTMATTER)
    verdict = check.check(output, fixture_wiki_path)
    assert verdict.passed is True


def test_ing002_fails_missing_target_slug(fixture_wiki_path: Path) -> None:
    """ING-002 fails when target_slug is absent; excerpt names the missing field."""
    check = _get_check(INGESTOR_CHECKS, "ING-002-required-fields")
    answer = """\
---
title: Example
category: package
page_type: package
summary: A summary.
---
"""
    output = AgentOutputProxy(answer=answer)
    verdict = check.check(output, fixture_wiki_path)
    assert verdict.passed is False
    assert "target_slug" in verdict.excerpt


def test_ing002_fails_missing_multiple_fields(fixture_wiki_path: Path) -> None:
    """ING-002 fails and names all missing fields when several are absent."""
    check = _get_check(INGESTOR_CHECKS, "ING-002-required-fields")
    answer = "---\ntitle: Only Title\n---\n"
    output = AgentOutputProxy(answer=answer)
    verdict = check.check(output, fixture_wiki_path)
    assert verdict.passed is False
    assert "Missing fields" in verdict.excerpt


def test_ing003_passes_with_valid_page_type(fixture_wiki_path: Path) -> None:
    """ING-003 passes when page_type is one of the four valid values."""
    check = _get_check(INGESTOR_CHECKS, "ING-003-page-type-routing")
    for pt in ("package", "concept", "adr", "source"):
        answer = f"---\ntitle: T\ncategory: {pt}\npage_type: {pt}\ntarget_slug: x\nsummary: s\n---\n"
        verdict = check.check(AgentOutputProxy(answer=answer), fixture_wiki_path)
        assert verdict.passed is True, f"Expected pass for page_type={pt!r}"


def test_ing003_fails_with_invalid_page_type(fixture_wiki_path: Path) -> None:
    """ING-003 fails when page_type is not in the allowed set."""
    check = _get_check(INGESTOR_CHECKS, "ING-003-page-type-routing")
    answer = """\
---
title: Bad
category: tool
page_type: tool
target_slug: packages/bad
summary: Bad page type.
---
"""
    output = AgentOutputProxy(answer=answer)
    verdict = check.check(output, fixture_wiki_path)
    assert verdict.passed is False
    assert "tool" in verdict.excerpt


def test_ing004_passes_source_with_source_category(fixture_wiki_path: Path) -> None:
    """ING-004 passes when page_type=source and category=source."""
    check = _get_check(INGESTOR_CHECKS, "ING-004-page-type-valid-category")
    answer = """\
---
title: A Source Page
category: source
page_type: source
target_slug: sources/example
summary: Source page.
---
"""
    verdict = check.check(AgentOutputProxy(answer=answer), fixture_wiki_path)
    assert verdict.passed is True


def test_ing004_fails_source_page_type_with_wrong_category(fixture_wiki_path: Path) -> None:
    """ING-004 fails when page_type=source but category=package."""
    check = _get_check(INGESTOR_CHECKS, "ING-004-page-type-valid-category")
    answer = """\
---
title: Wrong Category
category: package
page_type: source
target_slug: sources/wrong
summary: Mismatch.
---
"""
    output = AgentOutputProxy(answer=answer)
    verdict = check.check(output, fixture_wiki_path)
    assert verdict.passed is False
    assert "source" in verdict.excerpt.lower()


def test_ing004_fails_package_page_type_with_concept_category(fixture_wiki_path: Path) -> None:
    """ING-004 fails when page_type=package but category=concept."""
    check = _get_check(INGESTOR_CHECKS, "ING-004-page-type-valid-category")
    answer = """\
---
title: Mixed Up
category: concept
page_type: package
target_slug: packages/mixed
summary: Mixed up.
---
"""
    output = AgentOutputProxy(answer=answer)
    verdict = check.check(output, fixture_wiki_path)
    assert verdict.passed is False
    assert "concept" in verdict.excerpt or "package" in verdict.excerpt


# ---------------------------------------------------------------------------
# Linter checks — LNT-001 through LNT-003
# ---------------------------------------------------------------------------


def test_lnt001_passes_code_drift_before_orphan(fixture_wiki_path: Path) -> None:
    """LNT-001 passes when code-drift finding appears before orphan/stale finding."""
    check = _get_check(LINTER_CHECKS, "LNT-001-code-drift-first")
    answer = (
        "1. Code drift detected in packages/foo — summary is outdated.\n"
        "2. Orphan page found: packages/bar/old-page.md\n"
    )
    verdict = check.check(AgentOutputProxy(answer=answer), fixture_wiki_path)
    assert verdict.passed is True


def test_lnt001_fails_orphan_before_code_drift(fixture_wiki_path: Path) -> None:
    """LNT-001 fails when orphan finding precedes code-drift finding."""
    check = _get_check(LINTER_CHECKS, "LNT-001-code-drift-first")
    answer = (
        "1. Stale reference detected in adrs/0001.md\n"
        "2. Code drift in packages/foo — outdated claim.\n"
    )
    verdict = check.check(AgentOutputProxy(answer=answer), fixture_wiki_path)
    assert verdict.passed is False
    assert "Code-drift" in verdict.excerpt


def test_lnt001_passes_no_findings_of_either_type(fixture_wiki_path: Path) -> None:
    """LNT-001 passes vacuously when output contains neither code-drift nor orphan terms."""
    check = _get_check(LINTER_CHECKS, "LNT-001-code-drift-first")
    answer = "No issues found in the vault.\n"
    verdict = check.check(AgentOutputProxy(answer=answer), fixture_wiki_path)
    assert verdict.passed is True


def test_lnt002_passes_with_nonempty_findings(fixture_wiki_path: Path) -> None:
    """LNT-002 passes when linter output is non-empty."""
    check = _get_check(LINTER_CHECKS, "LNT-002-findings-nonempty-when-issues")
    answer = "Found 3 issues: orphan page, stale claim, broken wikilink."
    verdict = check.check(AgentOutputProxy(answer=answer), fixture_wiki_path)
    assert verdict.passed is True


def test_lnt002_fails_on_empty_output(fixture_wiki_path: Path) -> None:
    """LNT-002 fails when linter output is empty (or only whitespace)."""
    check = _get_check(LINTER_CHECKS, "LNT-002-findings-nonempty-when-issues")
    for empty in ("", "   ", "\n\n\t"):
        verdict = check.check(AgentOutputProxy(answer=empty), fixture_wiki_path)
        assert verdict.passed is False, f"Expected fail for answer={empty!r}"
        assert verdict.excerpt  # excerpt must be non-empty for evidence


def test_lnt003_passes_on_report_only_output(fixture_wiki_path: Path) -> None:
    """LNT-003 passes when the output reports findings without write operations."""
    check = _get_check(LINTER_CHECKS, "LNT-003-no-silent-fix")
    answer = "Found 3 issues: orphan page, stale claim, broken wikilink."
    verdict = check.check(AgentOutputProxy(answer=answer), fixture_wiki_path)
    assert verdict.passed is True


def test_lnt003_fails_on_write_operation_in_output(fixture_wiki_path: Path) -> None:
    """LNT-003 fails when output contains a write-operation verb next to a .md file."""
    check = _get_check(LINTER_CHECKS, "LNT-003-no-silent-fix")
    answer = "Updated foo.md to fix the typo in the summary."
    verdict = check.check(AgentOutputProxy(answer=answer), fixture_wiki_path)
    assert verdict.passed is False
    assert verdict.excerpt  # excerpt must name the offending match


def test_lnt003_fails_on_created_verb(fixture_wiki_path: Path) -> None:
    """LNT-003 fails when output says 'created' with a .md reference."""
    check = _get_check(LINTER_CHECKS, "LNT-003-no-silent-fix")
    answer = "I created packages/new-page.md with the corrected frontmatter."
    verdict = check.check(AgentOutputProxy(answer=answer), fixture_wiki_path)
    assert verdict.passed is False
    assert "Write operation" in verdict.excerpt


# ---------------------------------------------------------------------------
# Scanner checks — SCN-001 through SCN-004
# ---------------------------------------------------------------------------

_FULL_SCANNER_OUTPUT = """\
---
title: Lattice Wiki Core
category: package
summary: Core wiki maintenance package.
package_path: packages/lattice-wiki-core
language: python
---

## Overview

The lattice-wiki-core package implements the wiki maintenance workflows.

## Notable files

- src/main.py — entry point
"""


def test_scn001_passes_with_frontmatter(fixture_wiki_path: Path) -> None:
    """SCN-001 passes when scanner stub output contains YAML frontmatter."""
    check = _get_check(SCANNER_CHECKS, "SCN-001-frontmatter-present")
    verdict = check.check(AgentOutputProxy(answer=_FULL_SCANNER_OUTPUT), fixture_wiki_path)
    assert verdict.passed is True


def test_scn001_fails_without_frontmatter(fixture_wiki_path: Path) -> None:
    """SCN-001 fails when scanner output has no --- frontmatter delimiters."""
    check = _get_check(SCANNER_CHECKS, "SCN-001-frontmatter-present")
    output = AgentOutputProxy(answer="## Overview\n\nJust prose without frontmatter.")
    verdict = check.check(output, fixture_wiki_path)
    assert verdict.passed is False
    assert "frontmatter" in verdict.excerpt.lower()


def test_scn002_passes_with_all_required_fields(fixture_wiki_path: Path) -> None:
    """SCN-002 passes when all 5 required frontmatter fields are present."""
    check = _get_check(SCANNER_CHECKS, "SCN-002-required-fields")
    verdict = check.check(AgentOutputProxy(answer=_FULL_SCANNER_OUTPUT), fixture_wiki_path)
    assert verdict.passed is True


def test_scn002_fails_missing_language_field(fixture_wiki_path: Path) -> None:
    """SCN-002 fails and names 'language' when that field is absent."""
    check = _get_check(SCANNER_CHECKS, "SCN-002-required-fields")
    answer = """\
---
title: Foo Package
category: package
summary: A package.
package_path: packages/foo
---

## Overview

Stuff.
"""
    verdict = check.check(AgentOutputProxy(answer=answer), fixture_wiki_path)
    assert verdict.passed is False
    assert "language" in verdict.excerpt


def test_scn003_passes_without_file_map_section(fixture_wiki_path: Path) -> None:
    """SCN-003 passes when output does not contain a ## File map section."""
    check = _get_check(SCANNER_CHECKS, "SCN-003-no-file-map-section")
    verdict = check.check(AgentOutputProxy(answer=_FULL_SCANNER_OUTPUT), fixture_wiki_path)
    assert verdict.passed is True


def test_scn003_fails_with_file_map_section(fixture_wiki_path: Path) -> None:
    """SCN-003 fails when output contains the ## File map section."""
    check = _get_check(SCANNER_CHECKS, "SCN-003-no-file-map-section")
    answer = _FULL_SCANNER_OUTPUT + "\n## File map\n\n- src/foo.py\n"
    verdict = check.check(AgentOutputProxy(answer=answer), fixture_wiki_path)
    assert verdict.passed is False
    assert "File map" in verdict.excerpt


def test_scn004_passes_with_overview_section(fixture_wiki_path: Path) -> None:
    """SCN-004 passes when output contains ## Overview."""
    check = _get_check(SCANNER_CHECKS, "SCN-004-overview-present")
    verdict = check.check(AgentOutputProxy(answer=_FULL_SCANNER_OUTPUT), fixture_wiki_path)
    assert verdict.passed is True


def test_scn004_fails_without_overview_section(fixture_wiki_path: Path) -> None:
    """SCN-004 fails when ## Overview is absent."""
    check = _get_check(SCANNER_CHECKS, "SCN-004-overview-present")
    answer = """\
---
title: Foo
category: package
summary: A package.
package_path: packages/foo
language: python
---

No overview section here.
"""
    verdict = check.check(AgentOutputProxy(answer=answer), fixture_wiki_path)
    assert verdict.passed is False
    assert "Overview" in verdict.excerpt


# ---------------------------------------------------------------------------
# Synthesizer SYN-002 — slug-only wikilinks (WR-01 regression: lowercase /
# hyphenated slug targets must be flagged, not just PascalCase).
# ---------------------------------------------------------------------------


def test_syn002_fails_on_lowercase_and_hyphenated_slug_only_wikilinks(
    fixture_wiki_path: Path,
) -> None:
    """SYN-002 must catch slug-only wikilinks regardless of casing.

    Pre-WR-01 the check used a PascalCase regex and silently passed
    `[[bedrock]]` and `[[subagent-pool]]`. The fix defines slug-only as
    "no path separator in the target", which covers every casing variant.
    """
    check = _get_check(SYNTHESIZER_CHECKS, "SYN-002-no-slug-only-wikilinks")
    for slug in ("Bedrock", "bedrock", "subagent-pool", "foo_bar"):
        output = AgentOutputProxy(answer=f"See [[{slug}]] for details.")
        verdict = check.check(output, fixture_wiki_path)
        assert verdict.passed is False, f"Expected SYN-002 to fail on [[{slug}]]"
        assert slug in verdict.excerpt


def test_syn002_passes_on_path_prefixed_wikilink(fixture_wiki_path: Path) -> None:
    """SYN-002 passes when the wikilink target contains a path separator."""
    check = _get_check(SYNTHESIZER_CHECKS, "SYN-002-no-slug-only-wikilinks")
    output = AgentOutputProxy(answer="See [[wiki/bedrock]] and [[packages/foo|alias]].")
    verdict = check.check(output, fixture_wiki_path)
    assert verdict.passed is True


# ---------------------------------------------------------------------------
# code_reader regex behavior — WR-02 (`_GRAPH_WIKI_PREFIX_RE`) and WR-03
# (`_PATH_LINE_RE`). Module-level regex assertions per D-18 exception
# (silent-pass: previously zero direct coverage).
# ---------------------------------------------------------------------------


def test_graph_wiki_prefix_re_matches_slash_prefixed_inline_path() -> None:
    """WR-02: `vault/.graph-wiki/foo` must match — lookbehind excludes only
    word/hyphen characters, not the path separator."""
    assert _GRAPH_WIKI_PREFIX_RE.search("vault/.graph-wiki/bm25") is not None
    assert _GRAPH_WIKI_PREFIX_RE.search(".graph-wiki/foo") is not None


def test_graph_wiki_prefix_re_still_rejects_identifier_prefixed_match() -> None:
    """WR-02: identifier-bearing prefixes like `mygraph-wiki/foo` must NOT
    match — the lookbehind still excludes alphanumeric/underscore/hyphen."""
    assert _GRAPH_WIKI_PREFIX_RE.search("mygraph-wiki/foo") is None
    assert _GRAPH_WIKI_PREFIX_RE.search("foo_.graph-wiki/bar") is None


def test_path_line_re_matches_bare_filename_citation() -> None:
    """WR-03: bare-filename citations like `pool.py:115` are valid `path:line`
    annotations and must match (no mandatory `/` in the path)."""
    assert _PATH_LINE_RE.search("pool.py:115") is not None
    assert _PATH_LINE_RE.search("`pool.py:115`") is not None


def test_path_line_re_still_matches_qualified_paths() -> None:
    """WR-03: qualified `path:line` citations continue to match."""
    assert (
        _PATH_LINE_RE.search("packages/subagent-runtime/src/foo/pool.py:115")
        is not None
    )
    assert _PATH_LINE_RE.search("src/baz.py:10-15") is not None


