"""
wiki_search.py — BM25 search helpers over a Code Wiki. Standard library only.

Import-only library module used by plugin and CLI delivery surfaces.
"""

from __future__ import annotations

import math
import re
from collections import Counter, defaultdict

TOKEN_RE = re.compile(r"[a-zA-Z0-9][a-zA-Z0-9_\-']+")
STOPWORDS = {
    "the",
    "a",
    "an",
    "and",
    "or",
    "but",
    "if",
    "then",
    "so",
    "to",
    "of",
    "in",
    "on",
    "at",
    "for",
    "by",
    "with",
    "from",
    "is",
    "are",
    "was",
    "were",
    "be",
    "been",
    "being",
    "this",
    "that",
    "these",
    "those",
    "it",
    "its",
    "as",
    "we",
    "you",
    "they",
    "their",
    "our",
    "us",
    "i",
    "not",
    "no",
    "yes",
    "do",
    "does",
    "did",
    "will",
    "would",
    "can",
    "could",
    "should",
    "about",
    "into",
    "than",
    "out",
    "up",
    "down",
    "over",
    "under",
    "also",
}


def tokenize(text):
    return [t.lower() for t in TOKEN_RE.findall(text) if t.lower() not in STOPWORDS and len(t) > 1]


def load_docs(wiki):
    vault = wiki
    if not vault.exists():
        raise SystemExit(f"[error] {vault} not found")
    docs = []
    for md in sorted(vault.rglob("*.md")):
        rel = md.relative_to(vault)
        if rel.name in {"index.md", "log.md"}:
            continue
        if any(part.startswith(".") for part in rel.parts):
            continue
        text = md.read_text(encoding="utf-8", errors="replace")
        tokens = tokenize(text)
        docs.append(
            {
                "path": str(rel).replace("\\", "/"),
                "text": text,
                "tokens": tokens,
                "tf": Counter(tokens),
                "len": len(tokens),
            }
        )
    return docs


def bm25_scores(docs, query, k1=1.5, b=0.75):
    N = len(docs)
    if N == 0:
        return []
    avgdl = sum(d["len"] for d in docs) / N or 1
    df = defaultdict(int)
    for d in docs:
        for term in set(d["tokens"]):
            df[term] += 1
    idf = {term: math.log(1 + (N - df_t + 0.5) / (df_t + 0.5)) for term, df_t in df.items()}
    scores = []
    for i, d in enumerate(docs):
        score = 0.0
        for term in query:
            if term not in d["tf"]:
                continue
            tf = d["tf"][term]
            denom = tf + k1 * (1 - b + b * d["len"] / avgdl)
            score += idf.get(term, 0.0) * (tf * (k1 + 1)) / (denom or 1)
        if score > 0:
            scores.append((i, score))
    scores.sort(key=lambda x: x[1], reverse=True)
    return scores


def snippet(text, query, width=220):
    lower = text.lower()
    for term in query:
        idx = lower.find(term)
        if idx >= 0:
            start = max(0, idx - width // 3)
            end = min(len(text), start + width)
            s = text[start:end].replace("\n", " ")
            return ("…" if start > 0 else "") + s + ("…" if end < len(text) else "")
    return text[:width].replace("\n", " ") + ("…" if len(text) > width else "")
