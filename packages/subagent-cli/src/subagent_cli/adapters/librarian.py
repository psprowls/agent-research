"""LibrarianAdapter: single-page excerpt extraction for a user query."""

from __future__ import annotations

from graph_wiki_core.commands.query import _prepare_query_retrieval
from graph_wiki_core.prompts.librarian import LIBRARIAN_SYSTEM

from .base import Prepared, RunContext

_MAX_CHARS = 24_000
_TOP_K = 5


class LibrarianAdapter:
    name = "librarian"
    role = "librarian"
    selector = "query"
    supports_all = False

    async def prepare(self, ctx: RunContext, item: str) -> Prepared:
        """Run hybrid retrieval and build a librarian prompt for the top page.

        *item* is the natural-language query.  The adapter runs
        ``_prepare_query_retrieval`` to get the ranked page list, reads the top
        page (capped at 24 k chars), and builds the standard librarian human
        message (``Query: … / Page (…): …``).
        """
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

        human = f"Query: {item}\n\nPage ({top_page}):\n{page_text}"

        return Prepared(
            item_id=item[:80],
            system=LIBRARIAN_SYSTEM,
            human=human,
            parse=None,
        )

    def items(self, ctx: RunContext) -> list[str]:
        raise ValueError("LibrarianAdapter is a single-query adapter; use prepare() directly")
