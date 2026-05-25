"""Unit tests asserting models.toml loader tolerance and tier-to-role sweep candidate spec.

Verifies:
- All six in-scope agent roles have sweep_candidates arrays of length 4 (D-05)
- Candidate lists match the D-03 tier-to-role mapping exactly
- Judges (judge_a, judge_b) do NOT have sweep_candidates (D-01)
- Every candidate model_id is priced in eval_harness.pricing (key_links constraint)
- make_llm() still works for all six roles after the new key is added
- code_reader_cases.json has 5–6 vault-thin fixture cases (Phase 16 D-07 expansion from the original 3)
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from eval_harness.pricing import UnknownModelError, cost_for_usage
from model_adapter.loader import load_role_config, make_llm

# D-01: six in-scope agent roles only
IN_SCOPE_ROLES = ("librarian", "synthesizer", "code_reader", "scanner", "linter", "ingestor")

# D-03 tier-to-role candidate maps (locked)
QUALITY_ROLES = ("librarian", "synthesizer")
QUALITY_CANDIDATES = frozenset([
    "us.anthropic.claude-sonnet-4-6",
    "us.anthropic.claude-haiku-4-5-20251001-v1:0",
    "us.amazon.nova-pro-v1:0",
    "qwen.qwen3-32b-v1:0",
])

MID_ROLES = ("linter", "ingestor")
MID_CANDIDATES = frozenset([
    "us.anthropic.claude-haiku-4-5-20251001-v1:0",
    "us.amazon.nova-pro-v1:0",
    "us.amazon.nova-lite-v1:0",
    "qwen.qwen3-32b-v1:0",
])

CHEAP_FAST_ROLES = ("scanner", "code_reader")
CHEAP_FAST_CANDIDATES = frozenset([
    "us.anthropic.claude-haiku-4-5-20251001-v1:0",
    "us.amazon.nova-micro-v1:0",
    "us.amazon.nova-lite-v1:0",
    "qwen.qwen3-32b-v1:0",
])

# Path to code_reader_cases.json (relative to workspace root)
_WORKSPACE_ROOT = Path(__file__).parent.parent.parent.parent
CODE_READER_CASES_PATH = _WORKSPACE_ROOT / "eval" / "cases" / "code_reader_cases.json"


def test_sweep_candidates_present_for_all_six_roles():
    """Each of the six in-scope roles has sweep_candidates as a list of length 4."""
    for role in IN_SCOPE_ROLES:
        cfg = load_role_config(role)
        candidates = cfg.get("sweep_candidates")
        assert candidates is not None, f"[{role}] missing sweep_candidates key"
        assert isinstance(candidates, list), f"[{role}] sweep_candidates must be a list"
        assert len(candidates) == 4, (
            f"[{role}] expected 4 sweep_candidates, got {len(candidates)}: {candidates}"
        )


def test_tier_to_role_candidate_map():
    """Candidate sets match D-03 tier assignments exactly."""
    # Quality tier: librarian, synthesizer
    for role in QUALITY_ROLES:
        candidates = set(load_role_config(role)["sweep_candidates"])
        assert candidates == QUALITY_CANDIDATES, (
            f"[{role}] quality-tier candidates mismatch.\n"
            f"  expected: {sorted(QUALITY_CANDIDATES)}\n"
            f"  actual:   {sorted(candidates)}"
        )

    # Mid tier: linter, ingestor
    for role in MID_ROLES:
        candidates = set(load_role_config(role)["sweep_candidates"])
        assert candidates == MID_CANDIDATES, (
            f"[{role}] mid-tier candidates mismatch.\n"
            f"  expected: {sorted(MID_CANDIDATES)}\n"
            f"  actual:   {sorted(candidates)}"
        )

    # Cheap-fast tier: scanner, code_reader
    for role in CHEAP_FAST_ROLES:
        candidates = set(load_role_config(role)["sweep_candidates"])
        assert candidates == CHEAP_FAST_CANDIDATES, (
            f"[{role}] cheap-fast-tier candidates mismatch.\n"
            f"  expected: {sorted(CHEAP_FAST_CANDIDATES)}\n"
            f"  actual:   {sorted(candidates)}"
        )

    # Spot-check: librarian and synthesizer contain sonnet-4-6
    for role in QUALITY_ROLES:
        assert "us.anthropic.claude-sonnet-4-6" in load_role_config(role)["sweep_candidates"], (
            f"[{role}] missing us.anthropic.claude-sonnet-4-6"
        )

    # Spot-check: linter and ingestor contain nova-pro
    for role in MID_ROLES:
        assert "us.amazon.nova-pro-v1:0" in load_role_config(role)["sweep_candidates"], (
            f"[{role}] missing us.amazon.nova-pro-v1:0"
        )

    # Spot-check: scanner and code_reader contain nova-micro
    for role in CHEAP_FAST_ROLES:
        assert "us.amazon.nova-micro-v1:0" in load_role_config(role)["sweep_candidates"], (
            f"[{role}] missing us.amazon.nova-micro-v1:0"
        )


def test_no_sweep_candidates_for_judges():
    """judge_a and judge_b must NOT have a sweep_candidates key (D-01 exclusion)."""
    for judge_role in ("judge_a", "judge_b"):
        cfg = load_role_config(judge_role)
        candidates = cfg.get("sweep_candidates")
        assert candidates is None or candidates == [], (
            f"[{judge_role}] must not have sweep_candidates; got: {candidates}"
        )


def test_all_candidates_have_pricing():
    """Every (role, candidate) pair must be priced in eval_harness.pricing.PRICES."""
    for role in IN_SCOPE_ROLES:
        candidates = load_role_config(role)["sweep_candidates"]
        for model_id in candidates:
            try:
                # Use 1 token each — just checking the model is known, not computing real cost
                cost_for_usage(model_id, {"input": 1, "output": 1})
            except UnknownModelError as e:
                pytest.fail(
                    f"[{role}] candidate {model_id!r} is not priced in eval_harness.pricing: {e}"
                )


def test_make_llm_still_works_for_all_roles():
    """make_llm() constructs successfully for all six roles after sweep_candidates addition.

    No .invoke() call — just confirms the role config parses and ChatBedrockConverse
    is constructed without raising (loader ignores unknown keys per Tension 8 finding).
    """
    for role in IN_SCOPE_ROLES:
        try:
            llm = make_llm(role)
            assert llm is not None, f"[{role}] make_llm returned None"
        except Exception as e:
            pytest.fail(f"[{role}] make_llm() raised unexpectedly: {e}")


def test_code_reader_cases_json_loads():
    """eval/cases/code_reader_cases.json exists with 5–6 vault-thin cases (D-07 Phase 16).

    Phase 16 D-07 expands from 3 → 5–6 cases targeting post-rebrand surface
    (workspace-io, wiki-io.wiki_search, wiki-io.lint_wiki). The original 3
    cases are preserved verbatim for baseline comparability — the assertions
    here permit the expansion via range + superset checks.
    """
    if not CODE_READER_CASES_PATH.exists():
        pytest.fail(
            f"code_reader_cases.json not found at {CODE_READER_CASES_PATH}; "
            "Task 2 must create it before Task 3 runs."
        )

    cases = json.loads(CODE_READER_CASES_PATH.read_text())
    assert 5 <= len(cases) <= 6, (
        f"expected 5–6 code_reader cases after Phase 16 expansion, got {len(cases)}"
    )

    for case in cases:
        assert "vault-thin" in case["tags"], (
            f"case {case['case_id']!r} missing 'vault-thin' tag; got tags: {case['tags']}"
        )
        assert "code-reader" in case["tags"], (
            f"case {case['case_id']!r} missing 'code-reader' tag; got tags: {case['tags']}"
        )

    case_ids = {c["case_id"] for c in cases}
    assert case_ids >= {"code-reader-01", "code-reader-02", "code-reader-03"}, (
        f"first 3 case_ids must be preserved (baseline); got {sorted(case_ids)}"
    )
