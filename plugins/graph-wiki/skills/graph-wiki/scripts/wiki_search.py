#!/usr/bin/env python3
"""Plugin script for BM25 wiki search."""

from __future__ import annotations

import argparse
import json
import subprocess
import sys

from _uv_reexec import ensure as _ensure_uv

_ensure_uv()


def _backend_for(command: str) -> str:
    try:
        from _config import backend_for
    except ImportError:
        return "claude"
    return backend_for(command)


def _run_bedrock() -> None:
    result = subprocess.run(["gw", "query"] + sys.argv[1:], check=True)
    sys.exit(result.returncode)


def main() -> None:
    if _backend_for("query") == "bedrock":
        _run_bedrock()

    from wiki_io._workspace import resolve_wiki_and_repo
    from wiki_io.wiki_search import bm25_scores, load_docs, snippet, tokenize

    parser = argparse.ArgumentParser(description="BM25 search over a Code Wiki")
    parser.add_argument("--query", required=True)
    parser.add_argument("--limit", type=int, default=10)
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()

    wiki, _ = resolve_wiki_and_repo()
    docs = load_docs(wiki)
    qtokens = tokenize(args.query)
    if not qtokens:
        print("[error] empty query after tokenization", file=sys.stderr)
        sys.exit(1)

    scored = bm25_scores(docs, qtokens)[: args.limit]
    hits = []
    for i, score in scored:
        doc = docs[i]
        hits.append(
            {
                "path": doc["path"],
                "score": round(score, 3),
                "snippet": snippet(doc["text"], qtokens),
            }
        )

    if args.json:
        print(json.dumps({"query": args.query, "hits": hits}, indent=2, ensure_ascii=False))
        return

    if not hits:
        print(f"No matches for: {args.query}")
        return
    print(f"Query: {args.query}  ({len(hits)} hits)")
    for hit in hits:
        print(f"\n  [{hit['score']}] {hit['path']}")
        print(f"     {hit['snippet']}")


if __name__ == "__main__":
    main()
