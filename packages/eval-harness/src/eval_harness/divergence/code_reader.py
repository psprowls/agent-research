"""Programmatic divergence checks for the code_reader role (CR-001..CR-004).

Security (T-06-15 / T-16-04): All check callables use regex and string
operations only. No eval/exec of LLM-generated text.
"""

from __future__ import annotations

import re
from pathlib import Path

from eval_harness.divergence.check import AgentOutputProxy, DivergenceCheck, Verdict

# Sentinel string the code_reader returns when no file is relevant
# (agents/graph-wiki-agent/src/graph_wiki_agent/prompts/sources/code_reader.md#rules — rule 6).
_SENTINEL = "NO_RELEVANT_CONTENT"

# path:line or path:line-line annotation, e.g. `pool.py:115`,
# `packages/foo/bar.py:42`, or `src/baz.py:10-15`. Path may be a bare filename
# or directory-qualified; trailing component must end in a recognized source
# extension. Allow the citation to be inside or outside backticks.
_PATH_LINE_RE = re.compile(
    r"`?[A-Za-z0-9_./-]*[A-Za-z0-9_-]+\.(?:py|ts|js|tsx|jsx|go|rs|md|toml|yaml|yml|sh):\d+(?:-\d+)?`?"
)

# Wikilink pattern — code_reader should NEVER emit wikilinks (it returns
# source-code excerpts, not vault citations).
_WIKILINK_RE = re.compile(r"\[\[[^\]]+\]\]")

# Forbidden prefix: the tool refuses `.graph-wiki/` reads; the agent must not
# claim to quote anything from that prefix either.
_GRAPH_WIKI_PREFIX_RE = re.compile(r"(?<![A-Za-z0-9_-])\.graph-wiki/")


def _is_sentinel_only(text: str) -> bool:
    """True when text is the bare sentinel (no surrounding prose / markdown)."""
    return text.strip() == _SENTINEL


def _check_sentinel_or_path_line(output: AgentOutputProxy, wiki: Path) -> Verdict:
    """CR-001 (hard): Output is either the bare sentinel OR contains at least one
    `path:line` annotation.

    Anchors agents/graph-wiki-agent/src/graph_wiki_agent/prompts/sources/code_reader.md#outputs (rule 6 + output format).
    """
    text = output.answer or ""
    if _is_sentinel_only(text):
        return Verdict(passed=True, excerpt="")
    if _PATH_LINE_RE.search(text):
        return Verdict(passed=True, excerpt="")
    return Verdict(
        passed=False,
        excerpt="No path:line annotation and not the bare sentinel",
    )


def _check_no_wikilinks(output: AgentOutputProxy, wiki: Path) -> Verdict:
    """CR-002 (hard): code_reader never emits `[[wikilinks]]` — that is the
    synthesizer's job. Wikilinks here indicate the agent confused its role.

    Anchors agents/graph-wiki-agent/src/graph_wiki_agent/prompts/sources/code_reader.md#outputs.
    """
    match = _WIKILINK_RE.search(output.answer or "")
    if match:
        return Verdict(
            passed=False,
            excerpt=f"Forbidden wikilink in code_reader output: {match.group()[:80]}",
        )
    return Verdict(passed=True, excerpt="")


def _check_no_code_wiki_prefix(output: AgentOutputProxy, wiki: Path) -> Verdict:
    """CR-003 (hard): Output does not cite anything inside `.graph-wiki/` —
    the tool refuses such reads, so any such citation is invented.

    Anchors agents/graph-wiki-agent/src/graph_wiki_agent/prompts/sources/code_reader.md#rules (rule 4).
    """
    if _GRAPH_WIKI_PREFIX_RE.search(output.answer or ""):
        return Verdict(
            passed=False,
            excerpt="Citation references forbidden .graph-wiki/ prefix",
        )
    return Verdict(passed=True, excerpt="")


def _check_sentinel_is_bare(output: AgentOutputProxy, wiki: Path) -> Verdict:
    """CR-004 (soft): When the sentinel appears, it appears alone (no
    surrounding prose). The orchestrator filters on the bare sentinel; extras
    break that filter.

    Anchors agents/graph-wiki-agent/src/graph_wiki_agent/prompts/sources/code_reader.md#red-flags.
    """
    text = output.answer or ""
    if _SENTINEL not in text:
        return Verdict(passed=True, excerpt="")
    if _is_sentinel_only(text):
        return Verdict(passed=True, excerpt="")
    return Verdict(
        passed=False,
        excerpt="NO_RELEVANT_CONTENT sentinel has surrounding prose (must be bare)",
    )


CODE_READER_CHECKS: list[DivergenceCheck] = [
    DivergenceCheck(
        id="CR-001-path-line-or-sentinel",
        source_anchor="agents/graph-wiki-agent/src/graph_wiki_agent/prompts/sources/code_reader.md#outputs",
        severity="hard",
        check=_check_sentinel_or_path_line,
    ),
    DivergenceCheck(
        id="CR-002-no-wikilinks",
        source_anchor="agents/graph-wiki-agent/src/graph_wiki_agent/prompts/sources/code_reader.md#outputs",
        severity="hard",
        check=_check_no_wikilinks,
    ),
    DivergenceCheck(
        id="CR-003-no-code-wiki-prefix",
        source_anchor="agents/graph-wiki-agent/src/graph_wiki_agent/prompts/sources/code_reader.md#rules",
        severity="hard",
        check=_check_no_code_wiki_prefix,
    ),
    DivergenceCheck(
        id="CR-004-sentinel-is-bare",
        source_anchor="agents/graph-wiki-agent/src/graph_wiki_agent/prompts/sources/code_reader.md#red-flags",
        severity="soft",
        check=_check_sentinel_is_bare,
    ),
]
