"""Single source of truth for the page-kind template dirs every bootstrap
surface must seed into ``<wiki>/.templates/``.

These templates (``work.md``, ``guidance.md``) live in their owning packages'
``assets/`` dirs, not in wiki-io's ``page-templates/``. They reach
``.templates/`` only when a caller passes them to ``init_wiki`` as
``extra_template_dirs``. Centralizing the list here keeps both callers —
``commands.init.run_init`` (Bedrock / ``gw bootstrap``) and the Claude-hosted
plugin shim — in sync, so a future page-kind is registered in exactly one place.

This is a deliberately leaf module: it imports only the two ``*.templates``
accessors (no ``commands`` package, no Bedrock/langchain stack), so the plugin
shim's Claude branch can import it without dragging in heavy dependencies.
"""

from __future__ import annotations

from pathlib import Path

from guidance_io import templates as guidance_templates
from work_io import templates as work_templates


def kind_template_dirs() -> list[Path]:
    """Directories holding the page-kind templates seeded into every wiki's
    ``.templates/`` (work.md, guidance.md)."""
    return [work_templates.templates_dir(), guidance_templates.templates_dir()]
