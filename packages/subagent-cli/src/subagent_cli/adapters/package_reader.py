"""package_reader adapter: single-shot inspection of the entity-page section filler."""

from __future__ import annotations

from typing import Any, cast

import frontmatter
from graph_wiki_core.commands.package_reader import (
    PackageReaderItem,
    build_package_reader_prompt,
    extract_file_map,
    extract_narrative,
    find_todo_human_sections,
    parse_package_reader_output,
)
from graph_wiki_core.prompts.package_reader import PACKAGE_READER_SYSTEM

from .base import Prepared, RunContext


class PackageReaderAdapter:
    name = "package_reader"
    role = "package_reader"
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
        todo = find_todo_human_sections(page_text, entity_kind=kind)
        reader_item = PackageReaderItem(
            uri=str(post.metadata.get("uri", "")),
            kind=kind,
            name=name,
            graph_path=graph_path,
            language=str(post.metadata.get("language", "unknown")),
            frontmatter=cast(Any, dict(post.metadata)),
            page_content=page_text,
            requested_sections={s.heading: s.body for s in todo},
            narrative=extract_narrative(page_text) or "",
            file_map=extract_file_map(page_text) or "",
            graph_context="",
            entity_root=graph_path,
        )
        note = "single-shot inspection — production runs package_reader as an agentic tool loop"
        if not reader_item.requested_sections:
            note += "; this page has no TODO human sections (empty request)"
        return Prepared(
            item_id=f"{name} ({kind})",
            system=PACKAGE_READER_SYSTEM,
            human=build_package_reader_prompt(reader_item),
            parse=lambda raw: parse_package_reader_output(raw, requested_headings=list(reader_item.requested_sections)),
            note=note,
        )

    def items(self, ctx: RunContext) -> list[str]:
        return sorted({n.name for n in ctx.graph_reader().find(kind="package")})
