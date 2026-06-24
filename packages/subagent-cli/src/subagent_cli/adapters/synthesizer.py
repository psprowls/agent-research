"""SynthesizerAdapter: answer synthesis from librarian excerpts."""

from __future__ import annotations

from pathlib import Path

from graph_wiki_core.commands.query import _prepare_query_retrieval
from graph_wiki_core.prompts.synthesizer import SYNTHESIZER_SYSTEM

from .base import Prepared, RunContext

_MAX_CHARS = 24_000
_TOP_K = 5


class SynthesizerAdapter:
    """Synthesizer adapter.

    When *excerpts_path* is provided, the adapter loads pre-fetched librarian
    excerpts from that file and skips the retrieval + librarian step.  When it
    is ``None`` (the default), the adapter runs ``_prepare_query_retrieval`` to
    find the top page, reads it as an excerpt, and builds the synthesizer human
    message.
    """

    name = "synthesizer"
    role = "synthesizer"
    selector = "query"
    supports_all = False

    def __init__(self, excerpts_path: Path | None = None) -> None:
        self.excerpts_path = excerpts_path

    async def prepare(self, ctx: RunContext, item: str) -> Prepared:
        """Build a synthesizer prompt for *item* (the natural-language query).

        If *excerpts_path* was supplied at construction time, reads excerpts
        from that file and notes that retrieval was skipped.  Otherwise runs
        hybrid retrieval, reads the top page (capped at 24 k chars), and uses
        it as the excerpt.
        """
        if self.excerpts_path is not None:
            excerpts_text = self.excerpts_path.read_text(encoding="utf-8", errors="replace")
            note = "retrieval skipped — excerpts loaded from disk"
        else:
            prepared = _prepare_query_retrieval(item, ctx.workspace, _TOP_K)
            wiki = prepared.wiki
            top_page = prepared.top_pages[0] if prepared.top_pages else ""
            page_text = ""
            if top_page:
                try:
                    page_text = (wiki / top_page).read_text(encoding="utf-8", errors="replace")
                except OSError:
                    page_text = ""
                if len(page_text) > _MAX_CHARS:
                    page_text = page_text[:_MAX_CHARS] + "\n[TRUNCATED]"
            excerpts_text = f"[{top_page}]\n{page_text}" if top_page else page_text
            note = None

        human = f"Query: {item}\n\nLibrarian excerpts:\n{excerpts_text}"

        return Prepared(
            item_id=item[:80],
            system=SYNTHESIZER_SYSTEM,
            human=human,
            parse=None,
            note=note,
        )

    def items(self, ctx: RunContext) -> list[str]:
        raise ValueError("SynthesizerAdapter is a single-query adapter; use prepare() directly")
