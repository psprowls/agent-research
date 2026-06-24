"""guidance_classifier adapter: file-level classification into the closed vocab."""

from __future__ import annotations

from pathlib import Path

from graph_io import queries
from graph_wiki_core.prompts.guidance_classifier import (
    build_guidance_classifier_prompt,
    parse_classifier_response,
)
from guidance_io.vocab import load_vocab

from .base import Prepared, RunContext

_SKIP_SUFFIXES = (".min.js", ".lock", ".map")


class GuidanceClassifierAdapter:
    name = "guidance_classifier"
    role = "guidance_classifier"
    selector = "file"
    supports_all = True

    async def prepare(self, ctx: RunContext, item: str) -> Prepared:
        rel = Path(item).as_posix()
        head = (ctx.repo_root / rel).read_bytes().decode("utf-8", errors="replace")
        desc = queries.describe_path(ctx.graph_conn(), path=rel)
        symbols = [c.name for c in desc.children] if desc else []
        vocab = load_vocab(ctx.workspace)
        system, human = build_guidance_classifier_prompt(rel, head, symbols, sorted(vocab.topics), sorted(vocab.tags))
        return Prepared(
            item_id=rel,
            system=system,
            human=human,
            parse=lambda text: parse_classifier_response(text, vocab),
        )

    def items(self, ctx: RunContext) -> list[str]:
        rows = ctx.graph_conn().execute("SELECT path FROM nodes WHERE kind='file' AND path IS NOT NULL").fetchall()
        return sorted({r[0] for r in rows if r[0] and not r[0].endswith(_SKIP_SUFFIXES)})
