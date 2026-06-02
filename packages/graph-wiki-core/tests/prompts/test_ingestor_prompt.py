from __future__ import annotations

from graph_wiki_core.prompts.ingestor import build_ingestor_system


def test_ingestor_prompt_has_no_package_page_type() -> None:
    """Slice 4: the ingestor must not offer a package page_type or packages/ route."""
    system = build_ingestor_system()
    assert "page_type: package" not in system
    assert "-> `packages/`" not in system
    # It must instead steer the model to entity wikilinks.
    assert "[[entities/" in system
