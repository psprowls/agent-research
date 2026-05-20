from __future__ import annotations

"""Token-budget regression test (CTX-05 LOCKED).

Enforces the +1500-tokens-per-role ceiling documented in
.planning/phases/10-subagent-context-completion/10-CONTEXT.md §Token budget.

Each role's assembled system prompt (empty `project_context` path) must stay
within `PRE_PHASE_10_BASELINE[role] + TOKEN_CEILING_DELTA` tokens, where
"tokens" is `len(prompt) // 4` (the rule-of-thumb tokenizer mandated by
CONTEXT.md — no tiktoken, no Bedrock CountTokens API in this test, since
both are LLM-provider-specific and the budget is enforced on the role-shaped
prompt floor itself).

The per-vault project_context block is additive but capped by
render_project_context's own bounded size — that pathway is exercised by
test_prompt_snapshots::test_*_with_project_context and by
test_project_context.py.

# ----- PRE_PHASE_10_BASELINE derivation -----
# Baseline source-commit: e9cfd56 — the commit immediately BEFORE plan 10-05
# wiring landed (parent of 1cc94f5 "refactor(10-05): convert scanner/ingestor
# to builder fns with project_context").
#
# Measurement command (rerun to verify):
#   git show e9cfd56:agents/code-wiki-agent/src/code_wiki_agent/prompts/scanner.py > /tmp/old_scanner.py
#   git show e9cfd56:agents/code-wiki-agent/src/code_wiki_agent/prompts/ingestor.py > /tmp/old_ingestor.py
#   git show e9cfd56:agents/code-wiki-agent/src/code_wiki_agent/prompts/linter.py > /tmp/old_linter.py
#   git show e9cfd56:agents/code-wiki-agent/src/code_wiki_agent/prompts/librarian.py > /tmp/old_librarian.py
#   uv run python -c "
#       ns = {}; exec(open('/tmp/old_scanner.py').read(), ns)
#       print('scanner:', len(ns['SCANNER_SYSTEM']) // 4)"
#   ...repeat per file for INGESTOR_SYSTEM, LIBRARIAN_SYSTEM,
#      LINTER_PAGE_QUALITY_SYSTEM, LINTER_ADR_CHAIN_SYSTEM, LINTER_STALE_CLAIMS_SYSTEM.
#
# All shared fragments (_fragments/*.py) are byte-identical between e9cfd56
# and HEAD — `git diff e9cfd56 HEAD -- agents/code-wiki-agent/src/code_wiki_agent/prompts/_fragments/`
# returns no output — so re-execing the historical prompt source against the
# current fragments yields the exact pre-Phase-10 baseline.
"""

import pytest

PRE_PHASE_10_BASELINE = {
    "scanner": 837,
    "ingestor": 1574,
    "linter_page_quality": 617,
    "linter_adr_chain": 514,
    "linter_stale_claims": 529,
    "librarian": 975,
}

TOKEN_CEILING_DELTA = 1500


def _count_tokens(s: str) -> int:
    """Rule-of-thumb tokenizer mandated by CONTEXT.md §Token budget."""
    return len(s) // 4


def _assert_within_budget(role: str, prompt: str) -> None:
    baseline = PRE_PHASE_10_BASELINE[role]
    ceiling = baseline + TOKEN_CEILING_DELTA
    measured = _count_tokens(prompt)
    assert measured <= ceiling, (
        f"Token budget exceeded for role '{role}': "
        f"measured={measured} tokens, baseline={baseline}, ceiling={ceiling} "
        f"(baseline + {TOKEN_CEILING_DELTA}). "
        f"Trim a fragment (e.g. ARCHITECTURE_OVERVIEW) or drop CLAUDE_MD_DISAMBIGUATION "
        f"from a role that doesn't need it. See CONTEXT.md §Token budget LOCKED."
    )


def test_scanner_token_budget() -> None:
    try:
        from code_wiki_agent.prompts.scanner import build_scanner_system
    except ImportError:
        pytest.skip("prompts module not yet implemented")
    _assert_within_budget("scanner", build_scanner_system(project_context=""))


def test_ingestor_token_budget() -> None:
    try:
        from code_wiki_agent.prompts.ingestor import build_ingestor_system
    except ImportError:
        pytest.skip("prompts module not yet implemented")
    _assert_within_budget("ingestor", build_ingestor_system(project_context=""))


def test_linter_page_quality_token_budget() -> None:
    try:
        from code_wiki_agent.prompts.linter import build_linter_page_quality_system
    except ImportError:
        pytest.skip("prompts module not yet implemented")
    _assert_within_budget(
        "linter_page_quality", build_linter_page_quality_system(project_context="")
    )


def test_linter_adr_chain_token_budget() -> None:
    try:
        from code_wiki_agent.prompts.linter import build_linter_adr_chain_system
    except ImportError:
        pytest.skip("prompts module not yet implemented")
    _assert_within_budget(
        "linter_adr_chain", build_linter_adr_chain_system(project_context="")
    )


def test_linter_stale_claims_token_budget() -> None:
    try:
        from code_wiki_agent.prompts.linter import build_linter_stale_claims_system
    except ImportError:
        pytest.skip("prompts module not yet implemented")
    _assert_within_budget(
        "linter_stale_claims", build_linter_stale_claims_system(project_context="")
    )


def test_librarian_token_budget() -> None:
    try:
        from code_wiki_agent.prompts.librarian import build_librarian_system
    except ImportError:
        pytest.skip("prompts module not yet implemented")
    # Librarian has no project_context kwarg (CONTEXT.md §Wiring).
    _assert_within_budget("librarian", build_librarian_system())
