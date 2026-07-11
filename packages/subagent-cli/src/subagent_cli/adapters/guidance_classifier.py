"""guidance_classifier adapter: file-level classification into the closed vocab."""

from __future__ import annotations

from pathlib import Path

from graph_wiki_core.commands.guidance_signals import load_vocab
from graph_wiki_core.prompts.guidance_classifier import (
    build_guidance_classifier_prompt,
    parse_classifier_response,
)

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
        desc = ctx.graph_reader().describe_path(path=rel)
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
        paths = ctx.graph_reader().file_paths()
        return sorted({p for p in paths if p and not p.endswith(_SKIP_SUFFIXES)})
