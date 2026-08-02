# packages/wiki-io/scripts/frontmatter_differ.py
"""Throwaway audit tool for the python-frontmatter migration.

Parses every vault page with BOTH the frozen naive line parser (copy below)
and ``wiki_io.frontmatter.parse``, printing one tab-separated row per
divergence: page, key, old typed repr, new typed repr. Summary counts by key
go to stderr. Operator tool run against a real vault — not a test. DELETE in
the final task of this plan.

Usage: python packages/wiki-io/scripts/frontmatter_differ.py <wiki-dir>
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

from wiki_io.frontmatter import parse as yaml_parse

FRONTMATTER_RE = re.compile(r"^---\s*\n(.*?)\n---\s*\n", re.DOTALL)


def naive_parse(text: str) -> dict:
    """Frozen copy of the line-based parser being deleted (do not 'fix')."""
    m = FRONTMATTER_RE.match(text)
    if not m:
        return {}
    fm: dict = {}
    for line in m.group(1).splitlines():
        if ":" in line and not line.lstrip().startswith("#"):
            k, _, v = line.partition(":")
            fm[k.strip()] = v.strip().strip("'\"")
    return fm


def main(wiki: Path) -> int:
    rows = 0
    by_key: dict[str, int] = {}
    for md in sorted(wiki.rglob("*.md")):
        rel = md.relative_to(wiki)
        if any(p.startswith(".") for p in rel.parts):
            continue
        text = md.read_text(encoding="utf-8", errors="replace")
        old = naive_parse(text)
        new, err = yaml_parse(text)
        if err:
            print(f"{rel}\t<PARSE-ERROR>\t{err}")
            rows += 1
            by_key["<PARSE-ERROR>"] = by_key.get("<PARSE-ERROR>", 0) + 1
            continue
        for key in sorted(set(old) | set(new)):
            ov, nv = old.get(key), new.get(key)
            if ov == nv:
                continue
            rows += 1
            by_key[key] = by_key.get(key, 0) + 1
            print(f"{rel}\t{key}\t{type(ov).__name__}:{ov!r}\t->\t{type(nv).__name__}:{nv!r}")
    print(f"\n{rows} divergences across {len(by_key)} keys", file=sys.stderr)
    for key, n in sorted(by_key.items(), key=lambda kv: -kv[1]):
        print(f"  {key}: {n}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    if len(sys.argv) != 2:
        sys.exit("usage: frontmatter_differ.py <wiki-dir>")
    sys.exit(main(Path(sys.argv[1])))
