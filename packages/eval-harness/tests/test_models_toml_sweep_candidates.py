"""Unit tests asserting models.toml loader tolerance and sweep-candidate structural invariants.

Verifies:
- All six in-scope agent roles have non-empty sweep_candidates arrays (bespoke per-role lengths)
- global.anthropic.claude-haiku-4-5-20251001-v1:0 is present in every in-scope role's list
- Judges (judge_a, judge_b) do NOT have sweep_candidates (D-01)
- Every candidate model_id is priced in eval_harness.pricing (key_links constraint)
- make_llm() still works for all six roles after the new key is added
- code_reader_cases.json has 5–6 vault-thin fixture cases (Phase 16 D-07 expansion from the original 3)

Note: the D-03 tier-to-role mapping (uniform 4-entry lists) was retired with the
2026-05-29 na9 sweep-config refresh; lists are now bespoke per role (6/8/6/7/6/6).
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from eval_harness.pricing import UnknownModelError, cost_for_usage
from model_adapter.loader import load_role_config, make_llm

# D-01: six in-scope agent roles only
IN_SCOPE_ROLES = ("librarian", "synthesizer", "code_reader", "scanner", "linter", "ingestor")

# Haiku global inference profile — must appear in every in-scope role's sweep_candidates
HAIKU_GLOBAL_ARN = "global.anthropic.claude-haiku-4-5-20251001-v1:0"

# Path to code_reader_cases.json (relative to workspace root)
_WORKSPACE_ROOT = Path(__file__).parent.parent.parent.parent
CODE_READER_CASES_PATH = _WORKSPACE_ROOT / "eval" / "cases" / "code_reader_cases.json"


def test_sweep_candidates_present_for_all_six_roles():
    """Each of the six in-scope roles has a non-empty sweep_candidates list.

    Lengths are bespoke per role (6/8/6/7/6/6 after the na9 refresh); a
    fixed-length assertion would be wrong here.
    """
    for role in IN_SCOPE_ROLES:
        cfg = load_role_config(role)
        candidates = cfg.get("sweep_candidates")
        assert candidates is not None, f"[{role}] missing sweep_candidates key"
        assert isinstance(candidates, list), f"[{role}] sweep_candidates must be a list"
        assert len(candidates) >= 1, (
            f"[{role}] sweep_candidates must not be empty; got: {candidates}"
        )


def test_haiku_present_in_every_in_scope_role():
    """global.anthropic.claude-haiku-4-5-20251001-v1:0 must appear in every
    in-scope role's sweep_candidates (Pat's 'always include Haiku' rule)."""
    for role in IN_SCOPE_ROLES:
        candidates = load_role_config(role)["sweep_candidates"]
        assert HAIKU_GLOBAL_ARN in candidates, (
            f"[{role}] missing {HAIKU_GLOBAL_ARN!r} in sweep_candidates: {candidates}"
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
