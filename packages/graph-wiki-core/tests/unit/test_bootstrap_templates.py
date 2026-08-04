"""End-to-end check that core's bootstrap orchestration reassembles all page
templates in <wiki>/.templates/, including the work.md + guidance.md that now
live in work-io / guidance-io, plus the 9 per-kind work-item body templates
seeded under .templates/bodies/."""

from __future__ import annotations

from pathlib import Path

from graph_wiki_core.commands.init import run_init

EXPECTED_TEMPLATES = {
    "adr.md",
    "concept-architecture.md",
    "concept-pattern.md",
    "concept.md",
    "entity-agent-plugin.md",
    "entity-app.md",
    "entity-dependency.md",
    "entity-package.md",
    "entity-repository.md",
    "entity-test-suite.md",
    "guidance.md",
    "index.md",
    "proposal.md",
    "source.md",
    "work.md",
}


async def test_bootstrap_copies_all_templates(tmp_path: Path) -> None:
    ws = tmp_path / "ws"
    repo = tmp_path / "repo"
    repo.mkdir()

    result = await run_init(
        topic="smoke",
        tool="claude-code",
        force=True,
        workspace_path=ws,
        repo_path=repo,
    )

    templates = {p.name for p in (Path(result.wiki_path) / ".templates").glob("*.md")}
    assert templates == EXPECTED_TEMPLATES
    assert "work.md" in templates
    assert "guidance.md" in templates
    # 15 top-level page templates (Task 8: entity-domain.md retired) + 9
    # per-kind work-item body templates (.templates/bodies/*.md), counted
    # recursively by the bootstrap copier.
    assert result.page_templates_copied == 24
