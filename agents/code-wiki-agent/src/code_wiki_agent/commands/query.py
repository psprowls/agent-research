from __future__ import annotations

"""Hybrid BM25 + embedding search layer and query pipeline for code-wiki-agent.

Public API (Plan 02):
    build_index(vault_path)          -- Build/refresh BM25 + SQLite embedding index
    bm25_query(query_text, vault_path, top_k) -- Query the BM25 index
    _build_tokenizer()               -- bm25s Tokenizer matching lattice-wiki-core behavior
    _discover_pages(vault_path)      -- Vault page discovery with skip-list
    _rrf_fuse(bm25_ranks, embed_ranks, k) -- Reciprocal Rank Fusion
    _cosine_search_sqlite(vault_path, query_vec, top_k) -- Cosine similarity search

Public API (Plan 03):
    QueryResult                      -- Dataclass: answer, citations, pages_drilled, search_scores
    LIBRARIAN_SYSTEM                 -- System prompt for librarian role
    SYNTHESIZER_SYSTEM               -- System prompt for synthesizer role
    run_query(query, vault_path, top_k) -- End-to-end query pipeline
    apply_guardrails(result, vault_path, fan_result) -- G1 + G4 online guardrails
    _extract_wikilinks(text)         -- Extract [[wikilink]] targets from text
"""

import datetime
import hashlib
import json
import logging
import math
import re
import sqlite3
import struct
import uuid
from dataclasses import dataclass
from pathlib import Path

import bm25s
from bm25s.tokenization import Tokenizer
from langchain_aws import BedrockEmbeddings, ChatBedrockConverse
from langchain_core.messages import HumanMessage, SystemMessage
from model_adapter.loader import load_role_config, make_llm
from subagent_runtime.pool import FanOutResult, SubagentPool
from vault_io._workspace import resolve_wiki_and_repo

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Module-level constants
# ---------------------------------------------------------------------------

_TOKEN_RE_PATTERN = r"[a-zA-Z0-9][a-zA-Z0-9_\-']+"

# Full stopword set copied verbatim from lattice-wiki-core wiki_search.py
# (Open Question 3 from RESEARCH.md — use the full ~60-word set)
_STOPWORDS: frozenset[str] = frozenset({
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
})

_BM25_SUBDIR = "bm25"          # relative to .code-wiki/
_SEARCH_DB_NAME = "search.db"  # filename under .code-wiki/

# SQLite DDL — used by build_index; defined here for reuse
_DDL_PAGES = """
CREATE TABLE IF NOT EXISTS pages (
    path         TEXT PRIMARY KEY,
    content_hash TEXT NOT NULL,
    embedding    BLOB NOT NULL
)
"""
_PRAGMA_WAL = "PRAGMA journal_mode=WAL"

# ---------------------------------------------------------------------------
# Plan 03: System prompt constants (AI-SPEC §3 lines 216-228)
# ---------------------------------------------------------------------------

LIBRARIAN_SYSTEM = """You are a wiki librarian. Given a user query and a single wiki page, extract every passage from the page that is directly relevant to the query.

Rules:
- Quote relevant passages **verbatim** from the supplied page only. Do not paraphrase code symbols, file paths, function names, class names, or wikilink targets that are not literally present in the page text.
- Never invent file paths, line numbers, symbol names, or wikilinks. If a fact is not in the page text, it does not belong in your excerpt. The no-invention rule is absolute.
- For every quoted passage that mentions a code path, preserve the exact `path:line` or `path:line-line` annotation if it is present in the page (e.g. `pool.py:115`, `loader.py:82-107`). Never invent a line number, never round a range, never collapse a range to a single line.
- Preserve the page's wikilink syntax verbatim. If the page writes `[[wiki/cores/subagent-runtime/subagent-runtime]]`, quote it that way — do not rewrite it to `[[subagent-runtime]]` or any other slug-only form, and do not invent new wikilinks.
- When the page contains no passage relevant to the query, respond with exactly the sentinel string `NO_RELEVANT_CONTENT` and nothing else. Do not add explanation, apology, or partial-match attempts.
- When the page is a TODO stub, a near-empty placeholder, or otherwise too sparse to address the query, respond with `NO_RELEVANT_CONTENT` rather than guess at what the stub would say once filled in. Acknowledging vault thinness via the sentinel is preferred to fabricating content.

Output format:
- Either a list of verbatim excerpts (each labeled with its wikilink as it appears in the page), or the bare sentinel `NO_RELEVANT_CONTENT`. Nothing else."""

SYNTHESIZER_SYSTEM = """You are a wiki synthesizer. Given a user query and a set of excerpts from relevant wiki pages, produce a concise, accurate answer drawn strictly from those excerpts.

Rules:
- Compose the answer **only** from the supplied librarian excerpts. Never invent a file path, function name, class name, symbol, or wikilink target that does not appear verbatim in at least one excerpt. The no-invention rule is absolute — plausible-sounding prose that is not grounded in the excerpts is worse than a shorter, narrower answer.
- Cite vault pages using the **full page-path form** that appears in the excerpts, for example `[[wiki/cores/subagent-runtime/subagent-runtime]]` or `[[wiki/agents/code-wiki-agent/commands/query]]`. Never collapse a wikilink to a slug-only form such as `[[SubagentPool]]` or `[[Bedrock]]`. Slug-only wikilinks are forbidden — they do not resolve against the vault.
- When an excerpt cites a code path with a line number (e.g. `pool.py:115`, `loader.py:82-107`, `src/foo/bar.py:42`), preserve that exact `path:line` reference inline in the answer wrapped in backticks, like `` `pool.py:115` ``. Do not strip the line number, do not change it, do not invent one when the excerpt did not supply one.
- When the supplied excerpts do not cover some aspect of the query, **say so explicitly** in the answer using a phrase like "The vault does not document X." or "The vault doesn't cover Y." rather than filling the gap with plausible-sounding prose. Acknowledging vault thinness is required, not optional.

Output structure:
1. **Direct answer** — 1-3 sentences answering the question.
2. **Supporting detail** — organized thematically, weaving in inline citations: `[[wiki/...]]` wikilinks for vault pages and `` `path:line` `` backtick-wrapped references for code locations.
3. **Related pages** — a short section listing 3-5 wikilinks drawn from the excerpts only. Never invent a wikilink target that is not present in at least one excerpt.

If the excerpts collectively contain no answer to the query, return a short answer that says exactly that and lists which pages were checked. Do not fabricate."""


# ---------------------------------------------------------------------------
# Plan 03: QueryResult dataclass
# ---------------------------------------------------------------------------


@dataclass
class QueryResult:
    """Result of a run_query() call.

    Fields:
        answer:        Synthesized answer string (may contain [[wikilink]] tokens).
        citations:     List of wikilink targets extracted from the answer.
        pages_drilled: Number of librarian fan-out calls that succeeded.
        search_scores: Per-page scores dict: {page_path: {bm25, embed, rrf}}.
    """

    answer: str
    citations: list[str]
    pages_drilled: int
    search_scores: dict  # {page_path: {"bm25": float, "embed": float, "rrf": float}}


# ---------------------------------------------------------------------------
# Helper: tokenizer
# ---------------------------------------------------------------------------


def _build_tokenizer() -> Tokenizer:
    """Return a bm25s Tokenizer replicating lattice-wiki-core's TOKEN_RE behavior."""
    return Tokenizer(
        lower=True,
        splitter=_TOKEN_RE_PATTERN,
        stopwords=list(_STOPWORDS),
    )


# ---------------------------------------------------------------------------
# Helper: page discovery
# ---------------------------------------------------------------------------


def _discover_pages(vault_path: Path) -> list[tuple[str, str]]:
    """Walk vault_path and return [(posix_rel_path, page_text), ...] sorted.

    Skip rules (matching lattice-wiki-core reference behavior):
    - rel.name in {"index.md", "log.md"}
    - any path component starts with "." (e.g. .git/, .templates/)
    """
    results: list[tuple[str, str]] = []
    for md in sorted(vault_path.rglob("*.md")):
        rel = md.relative_to(vault_path)
        if rel.name in {"index.md", "log.md"}:
            continue
        if any(part.startswith(".") for part in rel.parts):
            continue
        text = md.read_text(encoding="utf-8", errors="replace")
        posix_path = str(rel).replace("\\", "/")
        results.append((posix_path, text))
    return results


# ---------------------------------------------------------------------------
# Helper: RRF fusion
# ---------------------------------------------------------------------------


def _rrf_fuse(
    bm25_ranks: dict[str, int],
    embed_ranks: dict[str, int],
    k: int = 60,
) -> dict[str, float]:
    """Reciprocal Rank Fusion.

    score(p) = 1/(k + rank_bm25(p)) + 1/(k + rank_embed(p))

    Missing pages use sentinel rank = n + k where n = len(all_pages).
    """
    all_pages = set(bm25_ranks) | set(embed_ranks)
    n = len(all_pages)
    return {
        p: 1.0 / (k + bm25_ranks.get(p, n + k)) + 1.0 / (k + embed_ranks.get(p, n + k))
        for p in all_pages
    }


# ---------------------------------------------------------------------------
# Helper: cosine search over SQLite
# ---------------------------------------------------------------------------


def _cosine_search_sqlite(
    vault_path: Path,
    query_vec: list[float],
    top_k: int,
) -> list[tuple[str, float]]:
    """Linear cosine scan over embeddings in search.db.

    Opens and closes the connection per call (no module-level state).
    Returns list of (page_path, cosine_score) sorted descending.
    """
    db_path = vault_path / ".code-wiki" / _SEARCH_DB_NAME
    conn = sqlite3.connect(str(db_path))
    try:
        rows = conn.execute("SELECT path, embedding FROM pages").fetchall()
    finally:
        conn.close()

    q_mag = math.sqrt(sum(x * x for x in query_vec))
    results: list[tuple[str, float]] = []
    for path, blob in rows:
        vec = struct.unpack(f"{len(blob) // 4}f", blob)
        dot = sum(a * b for a, b in zip(query_vec, vec))
        v_mag = math.sqrt(sum(x * x for x in vec))
        score = dot / (q_mag * v_mag) if (q_mag and v_mag) else 0.0
        results.append((path, score))
    results.sort(key=lambda x: x[1], reverse=True)
    return results[:top_k]


# ---------------------------------------------------------------------------
# Plan 03: wikilink extraction
# ---------------------------------------------------------------------------


def _extract_wikilinks(text: str) -> list[str]:
    """Extract [[wikilink]] target strings from text."""
    return re.findall(r"\[\[([^\]]+)\]\]", text)


def _compute_unresolved_wikilinks(answer: str, vault_path: Path) -> list[str]:
    """Return the list of [[wikilink]] targets in `answer` that do not resolve
    against `vault_path`.

    Resolution rules mirror apply_guardrails' G1 logic:
      - Link may already include .md (e.g. [[concepts/foo.md]]) or omit it.
      - Direct path lookup first; then glob fallback `**/<base>.md`.
    Exposed as a top-level helper so run_query can decide whether to trigger
    a one-shot synthesizer retry before falling through to apply_guardrails.
    """
    unresolved: list[str] = []
    for link in _extract_wikilinks(answer):
        link_path = link if link.endswith(".md") else f"{link}.md"
        candidate = vault_path / link_path
        if not candidate.exists():
            base = link.removesuffix(".md")
            matches = list(vault_path.glob(f"**/{base}.md"))
            if not matches:
                unresolved.append(link)
    return unresolved


async def _retry_synthesis_drop_unresolved(
    synth_llm,
    query: str,
    excerpts_text: str,
    unresolved: list[str],
) -> str:
    """One-shot synthesizer retry that names the unresolved wikilink tokens
    literally and tells the model to either repair them with a valid
    `[[wiki/...]]` path from the excerpts or drop them entirely.

    The retry HumanMessage embeds each unresolved token as written (e.g.
    `[[ghost]]`) so the model is told exactly which targets to fix — this is
    the behavior pinned by `test_run_query_retries_on_unresolved_wikilink`'s
    `call_args` assertion. Do not collapse to a generic "remove unresolved
    citations" instruction.
    """
    # Literal join of unresolved tokens, formatted as wikilinks
    unresolved_tokens = ", ".join(f"[[{u}]]" for u in unresolved)
    retry_instruction = (
        "Your previous answer included unresolved wikilink citations: "
        f"{unresolved_tokens}. "
        "These targets do not exist in the vault. "
        "Rewrite the answer below. For each unresolved citation listed above, "
        "either replace it with a valid full-path [[wiki/...]] wikilink that "
        "appears verbatim in at least one excerpt, or remove the citation "
        "entirely. Do not invent a new wikilink target. Preserve all other "
        "content, code-path:line references, and structure from your previous "
        "answer."
    )
    msgs = [
        SystemMessage(content=SYNTHESIZER_SYSTEM),
        HumanMessage(
            content=(
                f"Query: {query}\n\n"
                f"Librarian excerpts:\n{excerpts_text}\n\n"
                f"{retry_instruction}"
            )
        ),
    ]
    resp = await synth_llm.ainvoke(msgs)
    return resp.content


# ---------------------------------------------------------------------------
# Plan 03: Online guardrails (G1 + G4)
# ---------------------------------------------------------------------------


def apply_guardrails(
    result: QueryResult,
    vault_path: Path,
    fan_result: FanOutResult,
) -> QueryResult:
    """Apply online guardrails G1 and G4. Returns a (possibly mutated) QueryResult.

    G4 (empty-result safety): If fan_result.successes is empty AND result.citations
    is non-empty, clear citations and prepend an unsupported-answer warning.
    G4 runs BEFORE G1 to avoid false-positive unresolved-citation warnings on
    an already-cleared citation list.

    G1 (citation resolution): For each [[wikilink]] in result.answer, check if
    vault_path/<link>.md exists (direct or via glob). Unresolved citations trigger
    an appended warning listing them.
    """
    flags: list[str] = []

    # G4: empty excerpts + confident citations
    if not fan_result.successes and result.citations:
        flags.append(
            "[warning: no librarian excerpts; answer is unsupported by retrieved pages]"
        )
        result = QueryResult(
            answer=result.answer,
            citations=[],  # clear to avoid G1 false-positives
            pages_drilled=result.pages_drilled,
            search_scores=result.search_scores,
        )

    # G1: citation resolution
    # Links may already include .md (e.g. [[concepts/foo.md]]) or omit it
    # (e.g. [[concepts/foo]]). Normalise before checking.
    unresolved: list[str] = []
    for link in _extract_wikilinks(result.answer):
        link_path = link if link.endswith(".md") else f"{link}.md"
        candidate = vault_path / link_path
        if not candidate.exists():
            base = link.removesuffix(".md")
            matches = list(vault_path.glob(f"**/{base}.md"))
            if not matches:
                unresolved.append(link)

    if unresolved:
        flags.append(
            f"[warning: {len(unresolved)} citation(s) did not resolve: {unresolved}]"
        )

    if flags:
        flagged_answer = result.answer + "\n" + "\n".join(flags)
        return QueryResult(
            answer=flagged_answer,
            citations=result.citations,
            pages_drilled=result.pages_drilled,
            search_scores=result.search_scores,
        )
    return result


# ---------------------------------------------------------------------------
# Public: build_index
# ---------------------------------------------------------------------------


def build_index(vault_path: Path) -> None:
    """Build/refresh BM25 and embedding indexes for the vault.

    BM25 index: always rebuilt from scratch (cheap for small vaults).
    Embedding index: incremental via sha256 content hash (D-02 / SEARCH-05).

    Threat model T-03-07: WAL mode enables safe concurrent reads during rebuild.
    Threat model T-03-06: log WARNING for pages exceeding 32000 chars.
    """
    pages = _discover_pages(vault_path)
    if not pages:
        logger.warning("build_index: no pages discovered in %s", vault_path)
        return

    # ---- BM25 ----
    bm25_dir = vault_path / ".code-wiki" / _BM25_SUBDIR
    bm25_dir.mkdir(parents=True, exist_ok=True)

    logger.info("Rebuilding BM25 index for %d pages", len(pages))
    tokenizer = _build_tokenizer()
    corpus_paths = [path for path, _ in pages]
    corpus_texts = [text for _, text in pages]
    # return_as="tuple" yields a Tokenized object whose vocab_dict has string keys
    # required for orjson serialization in retriever.save() (Pitfall: integer keys fail)
    corpus_tokens = tokenizer.tokenize(corpus_texts, return_as="tuple")

    retriever = bm25s.BM25(method="lucene", k1=1.5, b=0.75)
    retriever.index(corpus_tokens)
    retriever.save(str(bm25_dir), corpus=corpus_paths)  # corpus items = page paths
    tokenizer.save_vocab(str(bm25_dir))
    tokenizer.save_stopwords(str(bm25_dir))

    # ---- Embedding index (incremental) ----
    db_path = vault_path / ".code-wiki" / _SEARCH_DB_NAME
    db_path.parent.mkdir(parents=True, exist_ok=True)

    conn = sqlite3.connect(str(db_path))
    try:
        conn.execute(_PRAGMA_WAL)
        conn.execute(_DDL_PAGES)
        conn.commit()

        embeddings = BedrockEmbeddings(
            model_id="amazon.titan-embed-text-v2:0",  # no "us." prefix for Titan (Pitfall 2)
            region_name="us-east-1",
            normalize=True,
        )

        for path, text in pages:
            if len(text) > 32000:
                logger.warning(
                    "Page %s exceeds 32000 chars (%d); Titan v2 will truncate at 8192 tokens",
                    path,
                    len(text),
                )
            content_hash = hashlib.sha256(text.encode()).hexdigest()
            row = conn.execute(
                "SELECT content_hash FROM pages WHERE path = ?", (path,)
            ).fetchone()
            if row is not None and row[0] == content_hash:
                continue  # unchanged — skip re-embedding (SEARCH-05 / D-02)

            vec = embeddings.embed_query(text)
            blob = struct.pack(f"{len(vec)}f", *vec)
            conn.execute(
                "INSERT OR REPLACE INTO pages (path, content_hash, embedding) VALUES (?, ?, ?)",
                (path, content_hash, blob),
            )
        conn.commit()
    finally:
        conn.close()


# ---------------------------------------------------------------------------
# Public: bm25_query
# ---------------------------------------------------------------------------


def bm25_query(
    query_text: str,
    vault_path: Path,
    top_k: int,
) -> tuple[list[str], list[float]]:
    """Load BM25 index and return top-k (page_paths, bm25_scores).

    Vocab is frozen at query time (update_vocab=False) — Pitfall 1 fix.
    """
    bm25_dir = vault_path / ".code-wiki" / _BM25_SUBDIR

    retriever = bm25s.BM25.load(str(bm25_dir), load_corpus=True)

    tokenizer = _build_tokenizer()
    tokenizer.load_vocab(str(bm25_dir))
    tokenizer.load_stopwords(str(bm25_dir))

    # update_vocab=False: prevents expanding the frozen index vocabulary (Pitfall 1)
    query_tokens = tokenizer.tokenize([query_text], update_vocab=False)
    num_docs = retriever.scores["num_docs"]
    results, scores = retriever.retrieve(query_tokens, k=min(top_k, num_docs))

    # results[0, i] is a dict {'id': int, 'text': str} when load_corpus=True
    def _corpus_text(item: object) -> str:
        if isinstance(item, dict):
            return str(item["text"])
        return str(item)

    page_paths = [_corpus_text(results[0, i]) for i in range(results.shape[1])]
    bm25_scores = [float(scores[0, i]) for i in range(scores.shape[1])]
    return page_paths, bm25_scores


# ---------------------------------------------------------------------------
# Plan 03: run_query — end-to-end query pipeline
# ---------------------------------------------------------------------------


async def run_query(
    query: str,
    vault_path: Path | None = None,
    top_k: int = 5,
    librarian_model_override: str | None = None,
) -> QueryResult:
    """End-to-end query: hybrid search -> librarian fan-out -> synthesis -> guardrails.

    Steps:
        1. Resolve vault path via resolve_wiki_and_repo().
        2. Auto-build index if missing (.code-wiki/bm25/ or .code-wiki/search.db absent).
        3. BM25 search (top_k * 3 candidates).
        4. Embedding search via Titan v2 (top_k * 3 candidates).
        5. RRF fusion -> top_k pages.
        6. Librarian fan-out via SubagentPool.run_all (role=librarian, max_concurrency=5).
        7. Synthesizer call (single, Sonnet, 4096 tokens).
        8. Build QueryResult with search_scores per top page.
        9. Apply G1 + G4 guardrails.
        10. Return guarded QueryResult.

    Args:
        query:                    Natural language query string.
        vault_path:               Path to vault root. None uses CODE_WIKI_REAL_VAULT_PATH env var.
        top_k:                    Pages to drill. Must be in [3, 10].
        librarian_model_override: Bedrock model ID to use for librarian role instead of
                                  the default from models.toml. Used by the eval sweep
                                  runner to test different models holding prompts fixed.

    Raises:
        RuntimeError: If top_k out of range or vault not resolvable.
    """
    if not (3 <= top_k <= 10):
        raise RuntimeError(
            f"top_k must be between 3 and 10 (got {top_k})"
        )

    query_id = uuid.uuid4().hex[:12]
    started_at = datetime.datetime.utcnow().isoformat() + "Z"

    # Step 1: resolve vault
    wiki, _ = resolve_wiki_and_repo(vault_path)

    # Step 2: auto-build index if missing
    bm25_dir = wiki / ".code-wiki" / _BM25_SUBDIR
    db_path = wiki / ".code-wiki" / _SEARCH_DB_NAME
    if not bm25_dir.exists() or not db_path.exists():
        logger.warning(
            "First-time index build — may take a moment. query_id=%s", query_id
        )
        build_index(wiki)

    # Step 3: BM25 search (over-retrieve: top_k * 3)
    bm25_paths, bm25_raw = bm25_query(query, wiki, top_k * 3)
    bm25_rank_map = {p: i + 1 for i, p in enumerate(bm25_paths)}
    bm25_score_map = {p: s for p, s in zip(bm25_paths, bm25_raw)}

    # Step 4: Embedding search
    embeddings = BedrockEmbeddings(
        model_id="amazon.titan-embed-text-v2:0",  # no "us." prefix for Titan
        region_name="us-east-1",
        normalize=True,
    )
    query_vec = embeddings.embed_query(query)
    embed_hits = _cosine_search_sqlite(wiki, query_vec, top_k * 3)
    embed_rank_map = {path: i + 1 for i, (path, _) in enumerate(embed_hits)}
    embed_score_map = {path: score for path, score in embed_hits}

    # Step 5: RRF fusion -> top_k pages
    fused = _rrf_fuse(bm25_rank_map, embed_rank_map)
    top_pages = sorted(fused, key=fused.get, reverse=True)[:top_k]  # type: ignore[arg-type]

    # Step 6: Librarian fan-out
    lib_cfg = load_role_config("librarian")
    if librarian_model_override is not None:
        librarian_llm = ChatBedrockConverse(
            model_id=librarian_model_override,
            region_name=lib_cfg["region"],
            max_tokens=lib_cfg["max_tokens"],
        )
    else:
        librarian_llm = make_llm("librarian")
    pool = SubagentPool(trace_dir=wiki / ".code-wiki" / "traces")

    async def drill_page(page_path: str) -> str:
        page_text = (wiki / page_path).read_text(encoding="utf-8", errors="replace")
        # Truncation guard per AI-SPEC §4b.4: cap at 24000 chars
        if len(page_text) > 24000:
            page_text = page_text[:24000] + "\n[TRUNCATED]"
            logger.warning("Truncated oversized page: %s", page_path)
        msgs = [
            SystemMessage(content=LIBRARIAN_SYSTEM),
            HumanMessage(content=f"Query: {query}\n\nPage ({page_path}):\n{page_text}"),
        ]
        resp = await librarian_llm.ainvoke(msgs)
        return resp.content

    fan_result: FanOutResult = await pool.run_all(
        items=top_pages,
        task=drill_page,
        role="librarian",
        model_id=lib_cfg["model_id"],
        max_concurrency=lib_cfg["max_concurrency"],
    )

    # Step 7: Synthesizer (single call)
    excerpts_text = "\n\n---\n\n".join(
        f"[{item}]\n{result}"
        for item, result in fan_result.successes
        if (result or "").strip() != "NO_RELEVANT_CONTENT"
    )
    # Optional safety truncation per AI-SPEC §4b.4
    if len(excerpts_text) > 60000:
        logger.warning(
            "Truncating librarian excerpts before synthesis (query_id=%s)", query_id
        )
        excerpts_text = excerpts_text[:60000]

    synth_llm = make_llm("synthesizer")
    synth_msgs = [
        SystemMessage(content=SYNTHESIZER_SYSTEM),
        HumanMessage(content=f"Query: {query}\n\nLibrarian excerpts:\n{excerpts_text}"),
    ]
    synth_resp = await synth_llm.ainvoke(synth_msgs)
    answer = synth_resp.content

    # Plan 03-08: One-shot retry if the synthesizer emitted unresolved
    # wikilinks AND there were real librarian successes to ground against.
    # G4 (empty successes) takes precedence — when G4 will fire, we skip
    # the retry because the answer is already going to be marked unsupported.
    if fan_result.successes:
        unresolved = _compute_unresolved_wikilinks(answer, wiki)
        if unresolved:
            logger.info(
                "synthesizer emitted %d unresolved wikilink(s); retrying once: %s",
                len(unresolved),
                unresolved,
            )
            answer = await _retry_synthesis_drop_unresolved(
                synth_llm, query, excerpts_text, unresolved
            )

    # Step 8: Build QueryResult with search_scores
    query_result = QueryResult(
        answer=answer,
        citations=_extract_wikilinks(answer),
        pages_drilled=len(fan_result.successes),
        search_scores={
            p: {
                "bm25": bm25_score_map.get(p, 0.0),
                "embed": embed_score_map.get(p, 0.0),
                "rrf": fused.get(p, 0.0),
            }
            for p in top_pages
        },
    )

    # Step 9: Apply guardrails (G1 + G4). If the retry above failed to clean
    # all unresolved wikilinks, G1 will append the warning footer as fallback.
    query_result = apply_guardrails(query_result, wiki, fan_result)

    # Write query summary trace record (RESEARCH Open Question 1 — write directly)
    ended_at = datetime.datetime.utcnow().isoformat() + "Z"
    trace_dir = wiki / ".code-wiki" / "traces"
    trace_dir.mkdir(parents=True, exist_ok=True)
    summary_file = trace_dir / f"query_{query_id}.jsonl"
    try:
        summary_record = {
            "kind": "query_summary",
            "query_id": query_id,
            "query": query,
            "top_k": top_k,
            "pages_retrieved": len(top_pages),
            "pages_drilled": query_result.pages_drilled,
            "started_at": started_at,
            "ended_at": ended_at,
        }
        with summary_file.open("w") as f:
            f.write(json.dumps(summary_record) + "\n")
    except OSError as exc:
        logger.warning("Could not write query summary trace: %s", exc)

    return query_result
