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
    LIBRARIAN_SYSTEM                 -- System prompt for librarian role (re-exported from code_wiki_agent.prompts.librarian)
    SYNTHESIZER_SYSTEM               -- System prompt for synthesizer role (re-exported from code_wiki_agent.prompts.synthesizer)
    run_query(query, vault_path, top_k) -- End-to-end query pipeline
    apply_guardrails(result, vault_path, fan_result) -- G1 + G4 online guardrails
    _extract_wikilinks(text)         -- Extract [[wikilink]] targets from text

Public API (Plan 09 — vault-thin code-fallback):
    CODE_READER_SYSTEM               -- System prompt for code_reader role (re-exported from code_wiki_agent.prompts.code_reader)
    _resolve_repo_root(vault_path)   -- Repo-root heuristic (.git / pyproject.toml sibling)
    _read_file_bounded(repo_root, requested_path, max_bytes) -- Allow-list bounded file reader
"""

import datetime
import hashlib
import json
import logging
import math
import re
import sqlite3
import struct
import time
import uuid
from dataclasses import dataclass
from pathlib import Path

import bm25s
from bm25s.tokenization import Tokenizer
from langchain_aws import BedrockEmbeddings, ChatBedrockConverse
from langchain_core.messages import HumanMessage, SystemMessage, ToolMessage
from langchain_core.tools import tool
from model_adapter.loader import load_role_config, make_llm
from subagent_runtime.pool import FanOutResult, SubagentPool
from subagent_runtime.trace_io import write_trace_record
from vault_io._workspace import resolve_wiki_and_repo
from code_wiki_agent.prompts.librarian import LIBRARIAN_SYSTEM  # noqa: F401
from code_wiki_agent.prompts.synthesizer import SYNTHESIZER_SYSTEM  # noqa: F401
from code_wiki_agent.prompts.code_reader import CODE_READER_SYSTEM  # noqa: F401

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

# Plan 09: marker prefix used to flag any answer produced by the code-fallback
# path. The eval harness (Phase 04) can count occurrences of this marker in
# query trace summaries to measure vault-thinness frequency.
CODE_FALLBACK_MARKER = "[vault-thin: answer derived from source code]"

# Plan 09: disclaimer line used when both the librarian fan-out and the
# code-reader fan-out return nothing useful. Never fabricate content.
CODE_FALLBACK_DISCLAIMER = (
    "The vault does not document this and source code did not yield a relevant match."
)


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


def _extract_usage_tokens(response) -> tuple[int | None, int | None]:
    """Extract (input_tokens, output_tokens) from a ChatBedrockConverse response.

    None-guarded — Bedrock returns ``usage_metadata = None`` on throttling /
    content-filter responses (deepagents #1698). Block lifted verbatim from
    subagent_runtime.pool._write_trace:203-209 so trace records on the synthesizer
    call sites carry the same usage data as pool-driven trace records.
    """
    tokens_in: int | None = None
    tokens_out: int | None = None
    if response is not None and hasattr(response, "usage_metadata"):
        meta = response.usage_metadata  # None on ThrottlingException / content filter
        # isinstance(dict) guards against bare-MagicMock test responses where
        # usage_metadata auto-resolves to a MagicMock object (matches the
        # corresponding defensive guard in subagent_runtime.trace_io).
        if isinstance(meta, dict):
            tokens_in = meta.get("input_tokens")
            tokens_out = meta.get("output_tokens")
    return tokens_in, tokens_out


# ---------------------------------------------------------------------------
# Plan 09: vault-thin code-fallback helpers
# ---------------------------------------------------------------------------


def _resolve_repo_root(vault_path: Path) -> Path:
    """Heuristic resolver for the repo root that backs a vault.

    Looks at `vault_path.parent`. If that directory contains either a `.git`
    entry (file or dir — a worktree's `.git` is a file) or a `pyproject.toml`,
    it is treated as the repo root. Otherwise falls back to `vault_path`
    itself with a logged warning.

    This is intentionally a starter heuristic; the UAT vault layout (vault at
    `~/Personal/wiki/deep-agents/` with repo at `~/Personal/deep-agents/`) is
    NOT a parent-child relationship, so the fallback path is hit in that
    setup — that's acceptable for v1 because the code-fallback only ever
    reads files via `_read_file_bounded`, which keeps the read inside the
    resolved root.
    """
    parent = vault_path.parent
    if (parent / ".git").exists() or (parent / "pyproject.toml").exists():
        return parent
    logger.warning(
        "_resolve_repo_root: no .git or pyproject.toml at %s; "
        "falling back to vault_path itself (%s) for code-fallback reads",
        parent,
        vault_path,
    )
    return vault_path


def _read_file_bounded(
    repo_root: Path,
    requested_path: str,
    max_bytes: int = 200_000,
) -> str:
    """Allow-listed bounded read of a single file under `repo_root`.

    Security contract (pinned by unit tests in test_query_code_fallback.py):
    - Resolves `requested_path` against `repo_root`. Both sides go through
      `Path.resolve(strict=False)` BEFORE the containment check, so a symlink
      whose target lives outside `repo_root` is rejected. Dropping `resolve()`
      will silently leak files; the symlink-escape test exists to catch that.
    - Rejects any path whose parts include `.code-wiki` (vault metadata, not
      source).
    - Reads at most `max_bytes` bytes. If the file is larger, the returned
      content is truncated to `max_bytes` and suffixed with the literal
      `[TRUNCATED]` marker.
    - Raises `PermissionError` on any allow-list violation. Callers in the
      LangChain tool wrapper convert that into a tool-error string so the
      model can recover without crashing.
    """
    root = repo_root.resolve(strict=False)
    candidate = (repo_root / requested_path).resolve(strict=False)

    if not candidate.is_relative_to(root):
        raise PermissionError(
            f"refusing to read {requested_path!r}: resolves outside repo root {root}"
        )
    if ".code-wiki" in candidate.parts:
        raise PermissionError(
            f"refusing to read {requested_path!r}: path is inside .code-wiki/"
        )
    if not candidate.is_file():
        raise PermissionError(
            f"refusing to read {requested_path!r}: not a regular file"
        )

    with candidate.open("rb") as f:
        raw = f.read(max_bytes + 1)
    if len(raw) > max_bytes:
        return raw[:max_bytes].decode("utf-8", errors="replace") + "[TRUNCATED]"
    return raw.decode("utf-8", errors="replace")


# Maximum tool-call iterations per page in the code-reader loop. Prevents a
# runaway model from chewing through tokens reading unrelated files.
_CODE_READER_MAX_ITERS = 5


async def _run_code_fallback(
    query: str,
    wiki: Path,
    top_pages: list[str],
    pool: SubagentPool,
    query_id: str,
    code_reader_override: str | None = None,
) -> tuple[str, int | None, int | None]:
    """Vault-thin fallback: fan out to a code-reader that uses a bounded
    `read_file` tool to read source code, then synthesize an answer prefixed
    with the `CODE_FALLBACK_MARKER`.

    Returns ``(answer, tokens_in, tokens_out)``. ``tokens_in`` / ``tokens_out``
    capture the synthesizer call's usage_metadata so the caller can thread
    them into the per-query summary_record (TRACE-FU-01 D-03). They are None
    when the fallback exits before synthesis (no useful code excerpts).

    Args:
        code_reader_override: Bedrock model ID to use for the code_reader role
            instead of the default from models.toml. Used by the sweep runner
            for single-role-swap evaluation (D-06).
    """
    repo_root = _resolve_repo_root(wiki)
    code_cfg = load_role_config("code_reader")
    if code_reader_override is not None:
        code_llm_raw = ChatBedrockConverse(
            model_id=code_reader_override,
            region_name=code_cfg["region"],
            max_tokens=code_cfg["max_tokens"],
        )
    else:
        code_llm_raw = make_llm("code_reader")

    # Bound the read_file tool to the resolved repo_root and bind it to the LLM.
    @tool
    def read_file(path: str) -> str:
        """Read a source file by repo-relative path.

        Refuses paths outside the repo root, inside `.code-wiki/`, or
        non-regular-files. Truncates at 200_000 bytes.
        """
        try:
            return _read_file_bounded(repo_root, path)
        except PermissionError as exc:
            return f"ERROR: {exc}"
        except OSError as exc:
            return f"ERROR: {exc}"

    code_llm = code_llm_raw.bind_tools([read_file])

    # Build candidate-path hints per top_page. Simple heuristic: pass the
    # vault page path minus `.md` and its parent dirname as hints. A future
    # plan can refine this to map vault paths -> probable source dirs.
    def _candidates_for(page_path: str) -> list[str]:
        page_no_md = page_path.removesuffix(".md")
        parts = page_no_md.split("/")
        hints: list[str] = [page_no_md]
        if len(parts) > 1:
            hints.append("/".join(parts[:-1]))
        return hints

    async def code_drill(page_path: str) -> str:
        candidates = _candidates_for(page_path)
        hint_lines = "\n".join(f"- {c}" for c in candidates)
        msgs: list = [
            SystemMessage(content=CODE_READER_SYSTEM),
            HumanMessage(
                content=(
                    f"Query: {query}\n\n"
                    f"The vault page `{page_path}` did not cover this query. "
                    "Use the `read_file` tool to read source files under these "
                    "candidate path hints and any other plausible files you can "
                    "infer from what you find:\n"
                    f"{hint_lines}\n\n"
                    "Quote relevant code verbatim with `path:line` annotations. "
                    "If nothing you can read is relevant, respond with exactly "
                    "`NO_RELEVANT_CONTENT`."
                )
            ),
        ]
        for iteration in range(_CODE_READER_MAX_ITERS):
            resp = await code_llm.ainvoke(msgs)
            tool_calls = getattr(resp, "tool_calls", None) or []
            if not tool_calls:
                return getattr(resp, "content", "") or ""
            msgs.append(resp)
            for call in tool_calls:
                call_args = call.get("args", {}) if isinstance(call, dict) else {}
                call_id = call.get("id", "") if isinstance(call, dict) else ""
                requested = call_args.get("path", "")
                try:
                    tool_output = _read_file_bounded(repo_root, requested)
                except PermissionError as exc:
                    tool_output = f"ERROR: {exc}"
                except OSError as exc:
                    tool_output = f"ERROR: {exc}"
                msgs.append(
                    ToolMessage(content=tool_output, tool_call_id=call_id)
                )
        logger.warning(
            "code-reader hit max iteration cap (%d) on page %s (query_id=%s)",
            _CODE_READER_MAX_ITERS,
            page_path,
            query_id,
        )
        # Stop without invention; treat as no content.
        return "NO_RELEVANT_CONTENT"

    code_fan: FanOutResult = await pool.run_all(
        items=top_pages,
        task=code_drill,
        role="code_reader",
        model_id=code_cfg["model_id"],
        max_concurrency=code_cfg["max_concurrency"],
    )

    code_useful = [
        (item, result)
        for item, result in code_fan.successes
        if (result or "").strip() and (result or "").strip() != "NO_RELEVANT_CONTENT"
    ]

    if not code_useful:
        # Both pathways empty — no fabrication.
        return CODE_FALLBACK_DISCLAIMER, None, None

    code_excerpts_text = "\n\n---\n\n".join(
        f"[{item}]\n{result}" for item, result in code_useful
    )
    if len(code_excerpts_text) > 60000:
        code_excerpts_text = code_excerpts_text[:60000]

    synth_llm = make_llm("synthesizer")
    synth_cfg = load_role_config("synthesizer")
    synth_msgs = [
        SystemMessage(content=SYNTHESIZER_SYSTEM),
        HumanMessage(
            content=(
                f"Query: {query}\n\n"
                "Source: code (vault did not cover this query). The excerpts "
                "below are quoted directly from source files by a code-reader "
                "subagent, not from vault pages.\n\n"
                f"Librarian excerpts:\n{code_excerpts_text}"
            )
        ),
    ]
    # TRACE-FU-01 (D-03): trace per-call synthesizer invocation alongside the
    # summary_record. The synth_resp also feeds the summary_record's
    # tokens_in / tokens_out so the per-query summary reports usage.
    trace_dir = wiki / ".code-wiki" / "traces"
    trace_dir.mkdir(parents=True, exist_ok=True)
    trace_file = trace_dir / f"synth_{query_id}.jsonl"
    t0 = time.monotonic()
    synth_resp = await synth_llm.ainvoke(synth_msgs)
    latency_ms = int((time.monotonic() - t0) * 1000)
    write_trace_record(
        trace_file,
        role="synthesizer",
        model_id=synth_cfg["model_id"],
        item=query_id,
        status="success",
        latency_ms=latency_ms,
        response=synth_resp,
    )
    tokens_in, tokens_out = _extract_usage_tokens(synth_resp)
    synth_answer = getattr(synth_resp, "content", "") or ""

    return f"{CODE_FALLBACK_MARKER}\n\n{synth_answer}", tokens_in, tokens_out


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
    *,
    skip_g4: bool = False,
) -> QueryResult:
    """Apply online guardrails G1 and G4. Returns a (possibly mutated) QueryResult.

    G4 (empty-result safety): If fan_result.successes is empty AND result.citations
    is non-empty, clear citations and prepend an unsupported-answer warning.
    G4 runs BEFORE G1 to avoid false-positive unresolved-citation warnings on
    an already-cleared citation list.

    G1 (citation resolution): For each [[wikilink]] in result.answer, check if
    vault_path/<link>.md exists (direct or via glob). Unresolved citations trigger
    an appended warning listing them.

    skip_g4: When True, suppress G4 entirely. Used on the code-fallback path
    where fan_result reflects the (possibly empty/errored) librarian fan-out
    but the answer is supported by the code-reader fan-out's excerpts. G1
    still runs — unresolved wikilinks in the synthesizer's output are valid
    to flag on either path.
    """
    flags: list[str] = []

    # G4: empty excerpts + confident citations
    if not skip_g4 and not fan_result.successes and result.citations:
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
    librarian_model_override: str | None = None,  # deprecated; prefer role_model_overrides
    role_model_overrides: dict[str, str] | None = None,
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
        vault_path:               Path to vault root. None uses GRAPH_WIKI_WORKSPACE env var.
        top_k:                    Pages to drill. Must be in [3, 10].
        librarian_model_override: Bedrock model ID to use for librarian role instead of
                                  the default from models.toml. Deprecated — prefer
                                  role_model_overrides={"librarian": model_id}. Kept for
                                  backward compatibility; role_model_overrides takes
                                  precedence when both are supplied.
        role_model_overrides:     Dict mapping role name to Bedrock model ID. Supports
                                  single-role-swap protocol (D-06): only the named role
                                  uses the candidate model; all other roles use their
                                  models.toml defaults. Supported keys: "librarian",
                                  "synthesizer", "code_reader".

    Raises:
        RuntimeError: If top_k out of range or vault not resolvable.
    """
    if not (3 <= top_k <= 10):
        raise RuntimeError(
            f"top_k must be between 3 and 10 (got {top_k})"
        )

    query_id = uuid.uuid4().hex[:12]
    started_at = datetime.datetime.now(tz=datetime.timezone.utc).isoformat()

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
    # Override resolution: role_model_overrides["librarian"] takes precedence over the
    # deprecated librarian_model_override parameter (D-06 single-role-swap protocol).
    _lib_override = (role_model_overrides or {}).get("librarian") or librarian_model_override
    lib_cfg = load_role_config("librarian")
    if _lib_override is not None:
        librarian_llm = ChatBedrockConverse(
            model_id=_lib_override,
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

    # Step 7: Determine whether the librarian fan-out yielded any useful
    # excerpts. Plan 09 vault-thin code-fallback fires only when this is empty.
    useful_excerpts = [
        (item, result)
        for item, result in fan_result.successes
        if (result or "").strip() and (result or "").strip() != "NO_RELEVANT_CONTENT"
    ]

    code_fallback_used = False

    if useful_excerpts:
        # ---- Regular path (vault-rich): synth on librarian excerpts ----
        excerpts_text = "\n\n---\n\n".join(
            f"[{item}]\n{result}" for item, result in useful_excerpts
        )
        # Optional safety truncation per AI-SPEC §4b.4
        if len(excerpts_text) > 60000:
            logger.warning(
                "Truncating librarian excerpts before synthesis (query_id=%s)",
                query_id,
            )
            excerpts_text = excerpts_text[:60000]

        synth_override = (role_model_overrides or {}).get("synthesizer")
        synth_cfg = load_role_config("synthesizer")
        if synth_override is not None:
            synth_llm = ChatBedrockConverse(
                model_id=synth_override,
                region_name=synth_cfg["region"],
                max_tokens=synth_cfg["max_tokens"],
            )
        else:
            synth_llm = make_llm("synthesizer")
        resolved_synth_model_id = synth_override or synth_cfg["model_id"]
        synth_msgs = [
            SystemMessage(content=SYNTHESIZER_SYSTEM),
            HumanMessage(
                content=f"Query: {query}\n\nLibrarian excerpts:\n{excerpts_text}"
            ),
        ]
        # TRACE-FU-01 (D-03): trace per-call synthesizer invocation; tokens also
        # feed the summary_record so the query summary reports usage.
        synth_trace_dir = wiki / ".code-wiki" / "traces"
        synth_trace_dir.mkdir(parents=True, exist_ok=True)
        synth_trace_file = synth_trace_dir / f"synth_{query_id}.jsonl"
        synth_t0 = time.monotonic()
        synth_resp = await synth_llm.ainvoke(synth_msgs)
        synth_latency_ms = int((time.monotonic() - synth_t0) * 1000)
        write_trace_record(
            synth_trace_file,
            role="synthesizer",
            model_id=resolved_synth_model_id,
            item=query_id,
            status="success",
            latency_ms=synth_latency_ms,
            response=synth_resp,
        )
        tokens_in, tokens_out = _extract_usage_tokens(synth_resp)
        answer = synth_resp.content

        # Plan 03-08: One-shot retry if the synthesizer emitted unresolved
        # wikilinks. fan_result.successes is non-empty here by construction
        # (useful_excerpts is a subset).
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
    else:
        # ---- Plan 09 vault-thin code-fallback branch ----
        logger.info(
            "librarian fan-out returned no useful excerpts; entering code-fallback (query_id=%s)",
            query_id,
        )
        code_fallback_used = True
        answer, tokens_in, tokens_out = await _run_code_fallback(
            query=query,
            wiki=wiki,
            top_pages=top_pages,
            pool=pool,
            query_id=query_id,
            code_reader_override=(role_model_overrides or {}).get("code_reader"),
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

    # Step 9: Apply guardrails (G1 + G4). On the code-fallback path the
    # librarian fan_result may have zero successes (all errored, or none at
    # all) — G4 would then falsely flag the code-derived answer as
    # unsupported. Skip G4 on the code-fallback path; G1 still runs so
    # unresolved wikilinks emitted by the synthesizer are caught either way.
    query_result = apply_guardrails(
        query_result, wiki, fan_result, skip_g4=code_fallback_used
    )

    # Write query summary trace record (RESEARCH Open Question 1 — write directly)
    ended_at = datetime.datetime.now(tz=datetime.timezone.utc).isoformat()
    trace_dir = wiki / ".code-wiki" / "traces"
    trace_dir.mkdir(parents=True, exist_ok=True)
    summary_file = trace_dir / f"query_{query_id}.jsonl"
    try:
        summary_record = {
            "schema_version": 1,  # Phase 9 OBS-04 D-01/D-02 — every record self-describing
            "kind": "query_summary",
            "query_id": query_id,
            "query": query,
            "top_k": top_k,
            "pages_retrieved": len(top_pages),
            "pages_drilled": query_result.pages_drilled,
            "code_fallback": code_fallback_used,
            "started_at": started_at,
            "ended_at": ended_at,
            "tokens_in": tokens_in,  # TRACE-FU-01 D-03: synth usage_metadata
            "tokens_out": tokens_out,
        }
        with summary_file.open("w") as f:
            f.write(json.dumps(summary_record) + "\n")
    except OSError as exc:
        logger.warning("Could not write query summary trace: %s", exc)

    return query_result
