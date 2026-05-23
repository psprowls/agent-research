"""Programmatic divergence checks for the librarian role (LIB-001..LIB-004).

Security (T-06-15): All check callables use regex and string operations only.
No eval/exec of LLM-generated text.
Security (T-06-16): Wikilink resolution delegates to resolve_citation, which
uses wiki.glob() anchored to the wiki root — no path traversal.
"""

from __future__ import annotations

import re
from pathlib import Path

from eval_harness.divergence.check import AgentOutputProxy, DivergenceCheck, Verdict


def _resolve_in_wiki(slug: str, wiki: Path) -> Path | None:
    """Resolve a citation slug against the wiki dir directly (D-03 layer).

    Mirrors eval_harness.structural._resolve_citation's resolution order but
    takes the wiki dir as a bare param (no workspace derivation). Divergence
    helpers operate inside an EvalWorktree where only the wiki path is
    available — there is no workspace concept at this layer.

    Resolution order:
    1. wiki/<slug>.md  (exact path match)
    2. wiki/<slug>/overview.md  (directory-style link where overview.md is the page)
    3. **/overview.md under any dir named <base>  (glob — overview.md convention)
    4. **/<base>.md  (glob — stem fallback for non-overview pages and legacy links)
    """
    exact = wiki / f"{slug}.md"
    if exact.exists():
        return exact
    # Directory-style link: [[packages/lattice-wiki-core]] → packages/lattice-wiki-core/overview.md
    overview = wiki / slug / "overview.md"
    if overview.exists():
        return overview
    base = Path(slug).name
    # Glob for a directory named <base> containing overview.md
    overview_matches = list(wiki.glob(f"**/{base}/overview.md"))
    if overview_matches:
        return overview_matches[0]
    # Glob fallback for stem-named .md files (legacy + non-overview pages)
    matches = list(wiki.glob(f"**/{base}.md"))
    if matches:
        return matches[0]
    return None

# Matches [[any content]] wikilinks.
_WIKILINK_RE = re.compile(r"\[\[([^\]]+)\]\]")

# Matches slug-only wikilinks: single CamelCase word with no slash (e.g. [[PackageName]]).
_SLUG_ONLY_RE = re.compile(r"^[A-Z][A-Za-z]+$")

# Matches bare code paths outside backticks: lines containing path:line patterns
# where the path is not preceded by a backtick.
_BARE_CODE_PATH_RE = re.compile(
    r"(?<!`)(?:src|tests|packages|agents)/[A-Za-z0-9_/.-]+\.(?:py|ts|js|go|rs):\d+"
)

# Matches any citation: wikilink OR backtick-quoted code path.
_BACKTICK_CODE_RE = re.compile(r"`[^`]+:[0-9]+(?:-[0-9]+)?`")


def _check_wikilink_resolves(output: AgentOutputProxy, wiki: Path) -> Verdict:
    """LIB-001: Every [[wikilink]] in the answer resolves to an .md file in the wiki."""
    links = _WIKILINK_RE.findall(output.answer)
    if not links:
        return Verdict(passed=True, excerpt="")
    unresolved = [lnk for lnk in links if _resolve_in_wiki(lnk, wiki) is None]
    if unresolved:
        return Verdict(passed=False, excerpt=f"Unresolved: {unresolved[0]}")
    return Verdict(passed=True, excerpt="")


def _check_citation_present(output: AgentOutputProxy, wiki: Path) -> Verdict:
    """LIB-002: Answer contains at least one citation (wikilink or backtick code path)."""
    has_wikilink = bool(_WIKILINK_RE.search(output.answer))
    has_code_path = bool(_BACKTICK_CODE_RE.search(output.answer))
    if not has_wikilink and not has_code_path:
        return Verdict(passed=False, excerpt="No citation in answer")
    return Verdict(passed=True, excerpt="")


def _check_no_slug_only_wikilinks(output: AgentOutputProxy, wiki: Path) -> Verdict:
    """LIB-003: No wikilinks of the form [[PackageName]] without a path prefix."""
    links = _WIKILINK_RE.findall(output.answer)
    for lnk in links:
        # Strip pipe aliases: [[page|display text]] → page
        slug = lnk.split("|")[0].strip()
        if _SLUG_ONLY_RE.match(slug):
            return Verdict(passed=False, excerpt=f"Slug-only wikilink: [[{slug}]]")
    return Verdict(passed=True, excerpt="")


def _check_code_path_format(output: AgentOutputProxy, wiki: Path) -> Verdict:
    """LIB-004 (soft): Code paths should be cited as `path:line`, not bare text."""
    match = _BARE_CODE_PATH_RE.search(output.answer)
    if match:
        return Verdict(passed=False, excerpt=f"Bare code path: {match.group()[:80]}")
    return Verdict(passed=True, excerpt="")


LIBRARIAN_CHECKS: list[DivergenceCheck] = [
    DivergenceCheck(
        id="LIB-001-wikilink-resolves",
        source_anchor="plugins/graph-wiki/skills/graph-wiki/SKILL.md#iron-rules",
        severity="hard",
        check=_check_wikilink_resolves,
    ),
    DivergenceCheck(
        id="LIB-002-citation-present",
        source_anchor="plugins/graph-wiki/agents/librarian.md#rules",
        severity="hard",
        check=_check_citation_present,
    ),
    DivergenceCheck(
        id="LIB-003-no-slug-only-wikilinks",
        source_anchor="plugins/graph-wiki/agents/librarian.md#rules",
        severity="hard",
        check=_check_no_slug_only_wikilinks,
    ),
    DivergenceCheck(
        id="LIB-004-code-path-format",
        source_anchor="plugins/graph-wiki/agents/librarian.md#rules",
        severity="soft",
        check=_check_code_path_format,
    ),
]
