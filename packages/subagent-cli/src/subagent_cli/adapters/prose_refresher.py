"""prose_refresher adapter: single-shot inspection of the unified prose-refresh agent."""

from __future__ import annotations

import frontmatter
from graph_wiki_core.commands.prose_refresh import (
    build_prose_refresh_prompt,
    parse_prose_refresher_output,
)
from graph_wiki_core.commands.scan_contract import ProseRefreshTask
from graph_wiki_core.prompts.prose_refresher import PROSE_REFRESHER_SYSTEM
from wiki_io.drift import extract_file_map
from wiki_io.entity_writer import prose_section_bodies

from .base import Prepared, RunContext


class ProseRefresherAdapter:
    name = "prose_refresher"
    role = "prose_refresher"
    selector = "package"
    supports_all = True

    async def prepare(self, ctx: RunContext, item: str) -> Prepared:
        name = item
        page_path = ctx.wiki / "entities" / f"pkg_{name}.md"
        if not page_path.exists():
            raise FileNotFoundError(f"no package entity page at {page_path}; run `gw scan` first")
        post = frontmatter.load(str(page_path))
        page_text = page_path.read_text(encoding="utf-8", errors="replace")
        kind = str(post.metadata.get("kind", "package"))
        nodes = ctx.graph_reader().find(name=name, kind="package")
        graph_path = (nodes[0].path or "") if nodes else ""
        task = ProseRefreshTask(
            uri=str(post.metadata.get("uri", "")),
            kind=kind,
            name=name,
            page_path=str(page_path),
            graph_path=graph_path,
            language=str(post.metadata.get("language", "unknown")),
            entity_root=graph_path,
            trigger="first_fill",
            diff=None,
            page_content=page_text,
            file_map_rows=extract_file_map(post.content) or "",
            prose_sections=prose_section_bodies(post.content),
            graph_context="",
        )
        note = "single-shot inspection — production runs prose_refresher as an agentic tool loop"
        if not task.prose_sections:
            note += "; this page has no prose sections (empty request)"

        def _parse(raw: str):
            result = parse_prose_refresher_output(raw, allowed_headings=list(task.prose_sections))
            result.uri = task.uri
            return result

        return Prepared(
            item_id=f"{name} ({kind})",
            system=PROSE_REFRESHER_SYSTEM,
            human=build_prose_refresh_prompt(task),
            parse=_parse,
            note=note,
        )

    def items(self, ctx: RunContext) -> list[str]:
        return sorted({n.name for n in ctx.graph_reader().find(kind="package")})
