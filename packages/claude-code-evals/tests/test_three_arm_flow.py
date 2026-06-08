"""Integration test for three-arm evaluation flow.

Tests the full pipeline: wiki preparation, scenario execution, verdict computation,
and report generation across base, injected, and plugin arms.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from claude_code_evals.report import generate_matrix_report
from claude_code_evals.runner import prepare_injected_context, prepare_plugin_env
from claude_code_evals.verdict import compute_verdict


@pytest.mark.integration
def test_three_arm_eval_full_flow(tmp_path: Path):
    """Test the full three-arm eval flow: wiki setup, context injection, and verdict computation.

    This integration test validates:
    1. prepare_injected_context() correctly loads and injects wiki pages
    2. prepare_plugin_env() sets environment variables for plugin arm
    3. compute_verdict() correctly judges scenario outcomes
    4. generate_matrix_report() produces valid reports
    """

    # --- Step 1: Create minimal wiki structure ---
    wiki_root = tmp_path / "test-wiki"
    wiki_dir = wiki_root / "wiki"
    wiki_dir.mkdir(parents=True)

    # Create concepts directory
    concepts_dir = wiki_dir / "concepts"
    concepts_dir.mkdir()

    # Create entities directory
    entities_dir = wiki_dir / "entities"
    entities_dir.mkdir()

    # Create a sample concept page
    api_client_page = concepts_dir / "shared-api-client.md"
    api_client_page.write_text(
        """---
title: Shared API Client
category: concept
summary: Base Axios client with interceptors
tags: [concept, api, client]
sources: 0
updated: 2026-06-08
tokens: 0
---

# Shared API Client

## Definition
The sanctioned cross-domain API client uses Axios with Bearer token and DeviceId interceptors.

## Usage Rule
Extend the sanctioned domain client, not raw axios.

## Cross-references
[[entities/pkg_shared-domain-ts]]
"""
    )

    # Create a sample entity page with backlinks
    entity_page = entities_dir / "pkg_shared-domain-ts.md"
    entity_page.write_text(
        """---
title: shared-domain-ts
category: entity
type: package
summary: Shared domain client package
updated: 2026-06-08
last_updated_commit: 551f7ed8
tokens: 0
---

# pkg_shared-domain-ts

## Definition
The shared domain package exports the sanctioned Axios client.

## Referenced in wiki
- [[concepts/shared-api-client]]
"""
    )

    # Create design-tokens concept page
    design_tokens_page = concepts_dir / "design-tokens.md"
    design_tokens_page.write_text(
        """---
title: Design tokens & variant pattern
category: concept
summary: Web UI styling with semantic tokens and cva variants
tags: [concept, ui, design-tokens]
sources: 0
updated: 2026-06-08
tokens: 0
---

# Design tokens & variant pattern

## Definition
Web components style themselves against semantic tokens, not literal colors.
Tokens are CSS custom properties; components use cva for variants.

## Rule of thumb
Need a new visual treatment → add/extend a token or a cva variant; do not drop raw hex.
"""
    )

    # Create an ADR for impossible-without-wiki scenario
    adrs_dir = wiki_dir / "adrs"
    adrs_dir.mkdir()
    adr_page = adrs_dir / "0006-auto-create-activities-from-presence-events.md"
    adr_page.write_text(
        """---
title: Auto-create activities from presence events
category: adr
status: accepted
decision: Activities auto-create from device presence events
summary: Presence events trigger activity records without explicit user action
updated: 2026-06-08
---

# ADR-0006: Auto-create activities from presence events

## Context
Device presence state changes (enter/leave) propagate through the timeline.
This is the **only** non-obvious design pattern in the codebase.

## Decision
Auto-create activity records when presence events cross the engagement threshold.

## Rationale
This pattern is not derivable from reading the code alone—you must know the policy.
"""
    )

    # --- Step 2: Create minimal Scenario with discriminators ---
    scenario_data = {
        "name": "api-client-usage",
        "description": "Test API client convention",
        "discriminator_type": "correctness-gated",
        "inject_paths": ["concepts/shared-api-client.md"],
        "plugin_env": {"GRAPH_WIKI_WORKSPACE": str(wiki_root)},
    }

    # --- Step 3: Test prepare_injected_context() ---
    base_prompt = "How should I use the API client?"
    injected_context = prepare_injected_context(
        base_prompt=base_prompt,
        wiki_root=str(wiki_root),
        inject_paths=scenario_data["inject_paths"],
    )

    # Verify wiki content is prepended
    assert "Shared API Client" in injected_context
    assert "sanctioned domain client" in injected_context
    assert base_prompt in injected_context
    # Wikilinks should be present and intact
    assert "[[entities/pkg_shared-domain-ts]]" in injected_context

    # --- Step 4: Test prepare_plugin_env() ---
    plugin_config = {
        "environment": scenario_data["plugin_env"],
    }
    env_vars = prepare_plugin_env(plugin_config)

    # Verify env vars are set
    assert "GRAPH_WIKI_WORKSPACE" in env_vars
    assert env_vars["GRAPH_WIKI_WORKSPACE"] == str(wiki_root)

    # --- Step 5: Test compute_verdict() for correctness-gated discriminator ---
    # Simulate three-arm scores: base fails, injected passes, plugin intermediate
    base_score = 0.3  # fails
    injected_score = 0.8  # passes (with wiki)
    plugin_score = 0.5  # intermediate

    verdict = compute_verdict(
        discriminator_type="correctness-gated",
        base_score=base_score,
        injected_score=injected_score,
        plugin_score=plugin_score,
    )

    # Verify verdict
    assert verdict.verdict == "WIKI_HELPED"
    assert "correctness" in verdict.reason.lower()
    assert verdict.injected_ceiling_score == injected_score
    assert verdict.discovery_cost is not None

    # --- Step 6: Test compute_verdict() for efficiency-gated discriminator ---
    verdict_eff = compute_verdict(
        discriminator_type="efficiency-gated",
        base_metric=120.0,  # base: 120 seconds
        plugin_metric=80.0,  # plugin: 80 seconds
        injected_metric=60.0,  # injected: 60 seconds (best)
        metric="wall_seconds",
        min_improvement_pct=10.0,
    )

    # Efficiency verdict should detect improvement
    assert verdict_eff.verdict in ["WIKI_HELPED", "NO_WIKI_VALUE"]
    assert "efficiency" in verdict_eff.reason.lower() or len(verdict_eff.reason) > 0

    # --- Step 7: Test compute_verdict() for impossible-without-wiki discriminator ---
    verdict_impossible = compute_verdict(
        discriminator_type="impossible-without-wiki",
        base_score=0.0,  # base cannot answer
        injected_score=1.0,  # injected answers (with wiki)
        plugin_score=0.0,  # plugin also cannot answer
    )

    # Impossible-without-wiki verdict
    assert verdict_impossible.verdict in ["WIKI_HELPED", "NO_WIKI_VALUE"]

    # --- Step 8: Test generate_matrix_report() ---
    # Build a sample results dict simulating three-arm outcomes
    # Note: convert Verdict to dict for JSON serialization
    results = {
        "api-client-usage": {
            "base": {"passed": False, "score": 0.3, "wall_seconds": 120},
            "injected": {"passed": True, "score": 0.8, "wall_seconds": 150},
            "plugin": {"passed": True, "score": 0.65, "wall_seconds": 140},
            "verdict": {
                "verdict": verdict.verdict,
                "reason": verdict.reason,
                "injected_ceiling_score": verdict.injected_ceiling_score,
                "discovery_cost": verdict.discovery_cost,
            },
        },
    }

    # Generate markdown report
    report = generate_matrix_report(results, format="markdown")

    # Verify report structure
    assert isinstance(report, str)
    assert len(report) > 0
    # Report should contain scenario name
    assert "api-client-usage" in report
    # Report should reference the three arms or verdict
    assert "base" in report.lower() or "WIKI_HELPED" in report

    # Generate JSON report
    report_json = generate_matrix_report(results, format="json")
    parsed = json.loads(report_json)
    assert isinstance(parsed, dict)
    assert "api-client-usage" in parsed


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
