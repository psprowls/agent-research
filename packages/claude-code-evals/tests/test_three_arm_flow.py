"""Integration test for three-arm evaluation flow.

Tests the full pipeline: wiki preparation, scenario execution, verdict computation,
and report generation across base, injected, and plugin arms.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from claude_code_evals.runner import prepare_injected_context


@pytest.mark.integration
def test_three_arm_injected_arm_wikilink_resolution(tmp_path: Path):
    """Test that injected context preserves wikilinks correctly."""
    wiki_root = tmp_path / "wiki-test"
    wiki_dir = wiki_root / "wiki"
    concepts_dir = wiki_dir / "concepts"
    concepts_dir.mkdir(parents=True)

    # Create concept with cross-references
    page = concepts_dir / "architecture.md"
    page.write_text(
        """---
title: Architecture
category: concept
updated: 2026-06-08
---

# Architecture

## Overview
The monorepo is organized by domains.

## See also
- [[shared-api-client]]
- [[entities/pkg_location-domain-ts]]
"""
    )

    base_prompt = "Describe the architecture."
    context = prepare_injected_context(
        base_prompt=base_prompt,
        wiki_root=str(wiki_root),
        inject_paths=["concepts/architecture.md"],
    )

    # Verify wikilinks are preserved (not resolved/mangled)
    assert "[[shared-api-client]]" in context
    assert "[[entities/pkg_location-domain-ts]]" in context


@pytest.mark.integration
def test_three_arm_missing_wiki_page_raises(tmp_path: Path):
    """Test that missing wiki pages raise appropriate errors."""
    wiki_root = tmp_path / "wiki-test"
    wiki_dir = wiki_root / "wiki"
    wiki_dir.mkdir(parents=True)

    base_prompt = "What is the design?"
    with pytest.raises(ValueError, match="Wiki page not found"):
        prepare_injected_context(
            base_prompt=base_prompt,
            wiki_root=str(wiki_root),
            inject_paths=["concepts/missing-page.md"],
        )


@pytest.mark.integration
def test_three_arm_multiple_injected_pages(tmp_path: Path):
    """Test injecting multiple wiki pages into context."""
    wiki_root = tmp_path / "wiki-test"
    wiki_dir = wiki_root / "wiki"
    concepts_dir = wiki_dir / "concepts"
    concepts_dir.mkdir(parents=True)

    # Create multiple pages
    page1 = concepts_dir / "page-1.md"
    page1.write_text("# Page 1\nContent about design tokens.")

    page2 = concepts_dir / "page-2.md"
    page2.write_text("# Page 2\nContent about API conventions.")

    base_prompt = "Answer based on both pages."
    context = prepare_injected_context(
        base_prompt=base_prompt,
        wiki_root=str(wiki_root),
        inject_paths=["concepts/page-1.md", "concepts/page-2.md"],
    )

    # Both pages should be in context, separated by delimiter
    assert "Page 1" in context
    assert "Page 2" in context
    assert "design tokens" in context
    assert "API conventions" in context
    assert base_prompt in context
    # Should have separator between pages
    assert "---" in context
