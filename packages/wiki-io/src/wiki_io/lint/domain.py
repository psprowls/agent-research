"""Domain placement: package pages whose vault location disagrees with their
``domain:`` frontmatter."""

from __future__ import annotations

GROUP = "domain"


def check(pages: dict) -> list[str]:
    """Flag package pages whose vault location disagrees with their ``domain:``.

    Policy:
      - A page under ``domains/<d>/packages/<name>/<name>.md`` must have
        ``domain: <d>`` in frontmatter (or empty, which we treat as drift —
        the page lives under a domain but doesn't claim one).
      - A page under top-level ``packages/<name>/<name>.md`` must NOT carry a
        ``domain:`` value. If it has an owning domain, it should be relocated
        under ``domains/<d>/packages/`` and only linked from the top-level
        index, not duplicated there.

    Apps are not checked: ``apps/`` is always top-level by design.
    """
    issues: list[str] = []
    for key, page in pages.items():
        fm = page["fm"]
        if fm.get("category") != "package":
            continue
        domain = (fm.get("domain") or "").strip()
        parts = key.split("/")
        if len(parts) >= 4 and parts[0] == "domains" and parts[2] == "packages":
            page_domain = parts[1]
            if not domain:
                issues.append(f"{key}: page lives under domain '{page_domain}' but has no `domain:` frontmatter")
            elif domain != page_domain:
                issues.append(f"{key}: `domain: {domain}` disagrees with path domain '{page_domain}'")
        elif parts and parts[0] == "packages":
            if domain:
                issues.append(
                    f"{key}: page is at top-level packages/ but claims "
                    f"`domain: {domain}` — move to "
                    f"domains/{domain}/packages/{parts[-1]}/"
                )
    return issues
