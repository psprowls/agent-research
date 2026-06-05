#!/usr/bin/env python3
"""Plugin script for wiki graph analysis."""

from __future__ import annotations

import argparse
import json

from _uv_reexec import ensure as _ensure_uv

_ensure_uv()


def main() -> None:
    from wiki_io._workspace import resolve_wiki_and_repo
    from wiki_io.graph_analyzer import analyze

    parser = argparse.ArgumentParser(description="Analyze the wikilink graph of a Code Wiki")
    parser.add_argument("--top", type=int, default=10)
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()

    wiki, _ = resolve_wiki_and_repo()
    result = analyze(wiki, args.top)

    if args.json:
        print(json.dumps(result, indent=2, default=list))
        return

    print(f"Code Wiki graph — {result['total_pages']} pages, {result['total_edges']} links")
    print(f"Connected components: {result['component_count']}")
    print()
    print("Top outbound hubs:")
    for hub in result["top_outbound_hubs"]:
        print(f"  - {hub['page']}  ({hub['outbound']} out)")
    print()
    print("Top inbound hubs:")
    for hub in result["top_inbound_hubs"]:
        print(f"  - {hub['page']}  ({hub['inbound']} in)")
    print()
    print(f"Orphans (no inbound): {len(result['orphans'])}")
    for orphan in result["orphans"][:10]:
        print(f"  - {orphan}")
    print()
    print(f"Sinks (no outbound): {len(result['sinks'])}")
    for sink in result["sinks"][:10]:
        print(f"  - {sink}")


if __name__ == "__main__":
    main()
