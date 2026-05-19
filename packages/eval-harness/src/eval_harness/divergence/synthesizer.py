"""Programmatic divergence checks for the synthesizer role (SYN-001..SYN-004).

Security (T-06-15 / T-16-04): All check callables use regex and string
operations only. No eval/exec of LLM-generated text.
"""

from __future__ import annotations

import re
from pathlib import Path

from eval_harness.divergence.check import AgentOutputProxy, DivergenceCheck, Verdict

# Any [[...]] wikilink
_WIKILINK_RE = re.compile(r"\[\[([^\]]+)\]\]")

# Slug-only wikilink: a single CamelCase or PascalCase token with no slash.
# Matches [[Foo]], [[FooBar]] but NOT [[wiki/foo/bar]], [[packages/foo|alias]].
_SLUG_ONLY_RE = re.compile(r"^[A-Z][A-Za-z0-9]+$")

# Backtick-wrapped code citation, e.g. `pool.py:115` or `src/foo/bar.py:10-15`.
_BACKTICK_CODE_RE = re.compile(r"`[^`]*?:\d+(?:-\d+)?`")

# Vault-thinness acknowledgement phrasing per packages/prompt-sources/agents/synthesizer.md
# rule 4. Match common variants; case-insensitive.
_VAULT_THIN_PHRASES_RE = re.compile(
    r"\b(?:the\s+vault\s+does(?:\s+not|\s*n['’]t)\s+(?:document|cover|know|contain|describe)"
    r"|vault\s+doesn['’]?t\s+(?:document|cover|know|contain|describe)"
    r"|no\s+(?:relevant\s+)?(?:vault\s+)?page(?:s)?\s+(?:cover|document|describe)"
    r"|not\s+documented\s+in\s+the\s+vault"
    r"|the\s+vault\s+(?:does\s+not|doesn['’]?t)\s+have)\b",
    re.IGNORECASE,
)


def _check_citation_present(output: AgentOutputProxy, vault: Path) -> Verdict:
    """SYN-001 (hard): Answer contains at least one citation (wikilink or
    backtick-wrapped `path:line`).

    Anchors packages/prompt-sources/agents/synthesizer.md#rules (rule 1 + 3).
    """
    text = output.answer or ""
    has_wikilink = bool(_WIKILINK_RE.search(text))
    has_code_path = bool(_BACKTICK_CODE_RE.search(text))
    if has_wikilink or has_code_path:
        return Verdict(passed=True, excerpt="")
    return Verdict(passed=False, excerpt="No wikilink or `path:line` citation in answer")


def _check_no_slug_only_wikilinks(output: AgentOutputProxy, vault: Path) -> Verdict:
    """SYN-002 (hard): No wikilinks of the form [[PackageName]] without a path prefix.

    Anchors packages/prompt-sources/agents/synthesizer.md#rules (rule 2).
    """
    for link in _WIKILINK_RE.findall(output.answer or ""):
        # Strip pipe aliases: [[page|display]] -> page
        slug = link.split("|")[0].strip()
        if _SLUG_ONLY_RE.match(slug):
            return Verdict(passed=False, excerpt=f"Slug-only wikilink: [[{slug}]]")
    return Verdict(passed=True, excerpt="")


def _check_no_path_line_promoted_to_wikilink(
    output: AgentOutputProxy, vault: Path
) -> Verdict:
    """SYN-003 (hard): A `path:line` reference inside `[[...]]` brackets is a
    promotion error — code citations must remain `` `path:line` ``, not wikilinks.

    Anchors packages/prompt-sources/agents/synthesizer.md#red-flags (code-fallback fidelity).
    """
    for link in _WIKILINK_RE.findall(output.answer or ""):
        if re.search(r":\d+", link):
            return Verdict(
                passed=False,
                excerpt=f"Wikilink contains a line number (should be backtick): [[{link[:60]}]]",
            )
    return Verdict(passed=True, excerpt="")


def _check_vault_thin_acknowledgement(
    output: AgentOutputProxy, vault: Path
) -> Verdict:
    """SYN-004 (soft): When the answer is short and emits no wikilink citations,
    it likely needs an explicit vault-thinness acknowledgement.

    Triggers only when (a) no wikilinks present AND (b) answer is non-trivial
    (≥ 40 chars). In that case the answer must contain a vault-thin phrase from
    rule 4. This is "soft" because short legitimate answers (e.g. all-code-fallback)
    may have backtick citations but no wikilinks; the soft signal flags missing
    acknowledgement without failing CI.

    Anchors packages/prompt-sources/agents/synthesizer.md#rules (rule 4).
    """
    text = output.answer or ""
    if len(text.strip()) < 40:
        return Verdict(passed=True, excerpt="")
    if _WIKILINK_RE.search(text):
        return Verdict(passed=True, excerpt="")
    # No wikilinks + non-trivial length -> must acknowledge vault thinness
    if _VAULT_THIN_PHRASES_RE.search(text):
        return Verdict(passed=True, excerpt="")
    return Verdict(
        passed=False,
        excerpt="No wikilinks AND no vault-thinness acknowledgement (e.g. 'the vault does not document X')",
    )


SYNTHESIZER_CHECKS: list[DivergenceCheck] = [
    DivergenceCheck(
        id="SYN-001-citation-present",
        source_anchor="packages/prompt-sources/agents/synthesizer.md#rules",
        severity="hard",
        check=_check_citation_present,
    ),
    DivergenceCheck(
        id="SYN-002-no-slug-only-wikilinks",
        source_anchor="packages/prompt-sources/agents/synthesizer.md#rules",
        severity="hard",
        check=_check_no_slug_only_wikilinks,
    ),
    DivergenceCheck(
        id="SYN-003-no-path-line-in-wikilink",
        source_anchor="packages/prompt-sources/agents/synthesizer.md#red-flags",
        severity="hard",
        check=_check_no_path_line_promoted_to_wikilink,
    ),
    DivergenceCheck(
        id="SYN-004-vault-thin-acknowledgement",
        source_anchor="packages/prompt-sources/agents/synthesizer.md#rules",
        severity="soft",
        check=_check_vault_thin_acknowledgement,
    ),
]
