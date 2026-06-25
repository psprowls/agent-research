"""`gw guidance scan` — build the file->vocabulary index via a Bedrock fan-out.

Per-file closed-vocab classification (guidance_classifier role) over file nodes
from the code graph. Incremental by content-hash; full rebuild when the
vocab_hash changes or --full is passed. graph-io is read-only; the index is the
sidecar at .graph-wiki/guidance-index.json (owned by guidance-io).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from pathlib import Path
from typing import Any, cast

from graph_io.queries import describe_path
from graph_io.store import GraphNotInitializedError, read_only_connect
from guidance_io.index_store import GuidanceIndex, IndexEntry, content_hash, load_index, save_index
from guidance_io.vocab import load_vocab, write_tags_yaml
from guidance_io.vocab import seed_tags as seed_tags_fn
from langchain_core.messages import HumanMessage, SystemMessage
from wiki_io._workspace import resolve_wiki_and_repo
from workspace_io.paths import graph_dir

from graph_wiki_core.prompts.guidance_classifier import (
    build_guidance_classifier_prompt,
    parse_classifier_response,
)

try:  # Bedrock stack — guarded so the plugin/non-Bedrock import path stays light
    from subagent_runtime.pool import SubagentPool, TaskResult

    from graph_wiki_core.roles import load_role_config, make_llm
except ImportError:  # pragma: no cover
    load_role_config = make_llm = None  # type: ignore[assignment]
    SubagentPool = TaskResult = None  # type: ignore[assignment]

# Light extra filter on top of the graph's .graphignore-respecting enumeration.
_SKIP_SUFFIXES = (".min.js", ".lock", ".map")


@dataclass
class GuidanceScanResult:
    scanned: list[str] = field(default_factory=list)
    skipped: list[str] = field(default_factory=list)
    total: int = 0
    seeded_tags: list[str] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)
    vocab_hash: str = ""


def _enumerate_files(conn, package: str | None, paths: list[str] | None) -> list[str]:
    if paths:
        wanted = {Path(p).as_posix() for p in paths}
        rows = conn.execute("SELECT path FROM nodes WHERE kind='file' AND path IS NOT NULL").fetchall()
        return sorted({r[0] for r in rows if r[0] in wanted})
    if package:
        rows = conn.execute(
            "SELECT f.path FROM nodes p "
            "JOIN edges ce ON ce.src = p.id AND ce.kind='contains' "
            "JOIN nodes f ON ce.dst = f.id AND f.kind='file' "
            "WHERE p.kind IN ('package','app') AND LOWER(p.name)=LOWER(?)",
            (package,),
        ).fetchall()
        return sorted({r[0] for r in rows if r[0]})
    rows = conn.execute("SELECT path FROM nodes WHERE kind='file' AND path IS NOT NULL").fetchall()
    return sorted({r[0] for r in rows if r[0] and not r[0].endswith(_SKIP_SUFFIXES)})


def _symbols_for(conn, rel: str) -> list[str]:
    import sqlite3

    try:
        desc = describe_path(conn, path=rel)
    except sqlite3.OperationalError:
        return []
    if desc is None:
        return []
    return [c.name for c in desc.children]


async def run_guidance_scan(
    workspace_path: Path | None = None,
    repo_path: Path | None = None,
    *,
    package: str | None = None,
    paths: list[str] | None = None,
    limit: int | None = None,
    full: bool = False,
    seed_tags: bool = False,
    model_override: str | None = None,
    stamp: str | None = None,
    make_llm_fn: Any = None,
    load_role_config_fn: Any = None,
    subagent_pool_type: Any = None,
    task_result_type: Any = None,
) -> GuidanceScanResult:
    """Build/refresh the guidance file index. See module docstring."""
    wiki, resolved_repo = resolve_wiki_and_repo(workspace_path)
    workspace = wiki.parent
    repo = repo_path.resolve() if repo_path else (resolved_repo or Path.cwd())
    stamp = stamp or date.today().isoformat()

    if seed_tags:
        seeded = seed_tags_fn(workspace)
        write_tags_yaml(workspace, seeded)
        return GuidanceScanResult(seeded_tags=seeded, vocab_hash=load_vocab(workspace).vocab_hash)

    vocab = load_vocab(workspace)
    result = GuidanceScanResult(vocab_hash=vocab.vocab_hash)
    if not vocab.topics:
        return result  # no guidance corpus → nothing to classify against

    try:
        conn = read_only_connect(graph_dir(workspace) / "code.db")
    except GraphNotInitializedError as exc:
        result.errors.append(f"graph not initialized: {exc}")
        return result

    try:
        files = _enumerate_files(conn, package, paths)
        result.total = len(files)
        index = load_index(workspace)
        vocab_changed = index.vocab_hash != vocab.vocab_hash
        # NOTE: `--limit` is a per-run cost cap, not an incremental-migration
        # mechanism. When the vocab_hash changes, a limited run classifies only
        # the first `limit` in-scope files but still stamps the new vocab_hash,
        # so the remaining files keep their prior classifications until a `--full`
        # (or unlimited) run. To complete a vocab migration, omit `--limit` or
        # pass `--full`.

        worklist: list[tuple[str, str, str, list[str]]] = []  # (rel, head, chash, symbols)
        for rel in files:
            abs_path = repo / rel
            try:
                data = abs_path.read_bytes()
            except OSError:
                continue
            chash = content_hash(data)
            prior = index.files.get(rel)
            if not full and not vocab_changed and prior is not None and prior.content_hash == chash:
                result.skipped.append(rel)
                continue
            head = data.decode("utf-8", errors="replace")
            worklist.append((rel, head, chash, _symbols_for(conn, rel)))
            if limit is not None and len(worklist) >= limit:
                break

        if not worklist:
            new_index = GuidanceIndex(vocab_hash=vocab.vocab_hash, files=dict(index.files))
            save_index(workspace, new_index)
            return result

        seams = _resolve_seams(make_llm_fn, load_role_config_fn, subagent_pool_type, task_result_type)
        if seams is None:
            result.errors.append("Bedrock stack unavailable; cannot classify files")
            return result
        _make_llm, _load_cfg, _PoolType, _TaskResult = seams

        cfg = _load_cfg("guidance_classifier")
        llm = _make_llm("guidance_classifier", model_override=model_override)
        pool = _PoolType(trace_dir=graph_dir(workspace) / "traces")
        topics = sorted(vocab.topics)
        tags = sorted(vocab.tags)

        async def classify(item: tuple[str, str, str, list[str]]):
            rel, head, _chash, symbols = item
            system, human = build_guidance_classifier_prompt(rel, head, symbols, topics, tags)
            resp = await llm.ainvoke([SystemMessage(system), HumanMessage(human)])
            content = resp.content if isinstance(resp.content, str) else str(resp.content)
            parsed = parse_classifier_response(content, vocab)
            return _TaskResult(value=(rel, parsed), response=resp)

        fan = await pool.run_all(
            items=worklist,
            task=classify,
            role="guidance_classifier",
            model_id=cfg["model_id"],
            max_concurrency=cfg["max_concurrency"],
        )

        new_files = dict(index.files)
        chash_by_rel = {rel: ch for rel, _h, ch, _s in worklist}
        for _item, (rel, parsed) in fan.successes:
            new_files[rel] = IndexEntry(
                topics=parsed["topics"],
                tags=parsed["tags"],
                content_hash=chash_by_rel[rel],
                scanned_at=stamp,
            )
            result.scanned.append(rel)
        for err in fan.errors:
            result.errors.append(f"{err.item[0]}: {err.exception!r}")

        save_index(workspace, GuidanceIndex(vocab_hash=vocab.vocab_hash, files=new_files))
        return result
    finally:
        conn.close()


def _resolve_seams(make_llm_fn, load_role_config_fn, subagent_pool_type, task_result_type):
    make_llm_fn = make_llm_fn or make_llm
    load_role_config_fn = load_role_config_fn or load_role_config
    subagent_pool_type = subagent_pool_type or SubagentPool
    task_result_type = task_result_type or TaskResult
    if None in (make_llm_fn, load_role_config_fn, subagent_pool_type, task_result_type):
        return None
    return (
        cast(Any, make_llm_fn),
        cast(Any, load_role_config_fn),
        cast(Any, subagent_pool_type),
        cast(Any, task_result_type),
    )
