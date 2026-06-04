"""Scanner-heading drift: entity pages missing an expected scanner-owned
section for their kind (e.g. a human renamed `## Narrative`).

Flag-only (M2d D4) — PTO cannot safely auto-heal a renamed scanner heading
(it can't distinguish a rename from an intentional human section), so this
lint surfaces it as a warning. No content migration.
"""

from __future__ import annotations

import re

from wiki_io.entity_writer import ADMITTED_KINDS

GROUP = "scanner_heading"

# Scanner-owned sections each entity kind's template carries. `## File map`
# only appears on package/app/test_suite templates; `## Narrative` and
# `## Referenced in wiki` appear on all admitted kinds.
_BASE_SECTIONS = ("## Narrative", "## Referenced in wiki")
_FILE_MAP_KINDS = frozenset({"package", "app", "test_suite"})
_EXPECTED_SCANNER_HEADINGS: dict[str, tuple[str, ...]] = {
    kind: (_BASE_SECTIONS + ("## File map",) if kind in _FILE_MAP_KINDS else _BASE_SECTIONS)
    for kind in ADMITTED_KINDS
}

# Defence-in-depth: if this dict is ever rewritten as a literal (instead of the
# ADMITTED_KINDS comprehension), this guards against a kind being omitted.
assert set(_EXPECTED_SCANNER_HEADINGS) == set(ADMITTED_KINDS), \
    "scanner-heading lint map must cover every admitted kind"

_FILE_MAP_PREFIX_RE = re.compile(r"^## File map\b", re.MULTILINE)


def _heading_present(text: str, heading: str) -> bool:
    """True when ``heading`` appears as an H2 at column 0.

    `## File map` carries a `- <name>` suffix, so it is matched by prefix; the
    other scanner headings are exact (humans must not rename them — that is the
    failure mode this lint catches).
    """
    if heading == "## File map":
        return _FILE_MAP_PREFIX_RE.search(text) is not None
    pat = re.compile(r"^" + re.escape(heading) + r"[ \t]*$", re.MULTILINE)
    return pat.search(text) is not None


def check(pages: dict) -> list[str]:
    """Flag entity pages missing an expected scanner-owned section for their kind.

    ``pages`` is the lint command's page map: ``{key: {"fm": {...}, "text": str}}``.
    Only pages whose frontmatter ``kind`` is an admitted entity kind are checked;
    every other page (concepts, ADRs, etc.) is ignored. Returns a sorted list of
    warning strings.
    """
    issues: list[str] = []
    for key, page in pages.items():
        fm = page.get("fm") or {}
        kind = fm.get("kind")
        expected = _EXPECTED_SCANNER_HEADINGS.get(kind)
        if not expected:
            continue
        text = page.get("text") or ""
        for heading in expected:
            if not _heading_present(text, heading):
                issues.append(
                    f"{key}: missing scanner section '{heading}' "
                    f"(renamed or dropped?)"
                )
    return sorted(issues)
