from __future__ import annotations

"""Verify run_scan calls regenerate_referenced_in_wiki(wiki) after index regen."""

from pathlib import Path
from unittest.mock import AsyncMock, patch

import pytest


@pytest.mark.asyncio
async def test_run_scan_regenerates_referenced_in_wiki(tmp_path: Path) -> None:
    """run_scan calls regenerate_referenced_in_wiki(wiki) in both narrate modes."""
    from graph_wiki_core.commands import scan as scan_mod

    wiki = tmp_path / "wiki"
    (wiki / "entities").mkdir(parents=True)
    (wiki / "log.md").write_text("", encoding="utf-8")
    (wiki / "packages").mkdir(exist_ok=True)
    (wiki / "CLAUDE.md").write_text(
        "# wiki\n\n```yaml\nversion: 1\ncontainers:\n  - source: .\n    vault_dir: packages\n    classification: single-package\n    children_count: 1\n```\n",
        encoding="utf-8",
    )
    (wiki / "index.md").write_text("# Index\n", encoding="utf-8")

    fake_state_gate = {"allowed": True, "reason": "test-mode", "head_commit": "abc123"}

    pool_mock = AsyncMock()
    pool_mock.run_all = AsyncMock(
        return_value=scan_mod.FanOutResult() if scan_mod.FanOutResult is not None else None
    )

    with (
        patch.object(scan_mod, "resolve_wiki_and_repo", return_value=(wiki, tmp_path)),
        patch.object(scan_mod, "compute_state_gate", return_value=fake_state_gate),
        patch.object(scan_mod, "make_llm"),
        patch.object(scan_mod, "SubagentPool", return_value=pool_mock),
        patch.object(scan_mod, "update_index"),
        patch.object(scan_mod, "_cg_run_build", return_value=(0, "", "")),
        patch.object(
            scan_mod,
            "read_only_connect",
            side_effect=scan_mod.GraphNotInitializedError("test stub"),
        ),
        patch.object(scan_mod, "append_log"),
        patch.object(
            scan_mod, "regenerate_referenced_in_wiki", return_value=["pkg_foo"]
        ) as mock_regen,
    ):
        await scan_mod.run_scan(workspace_path=tmp_path, narrate=False)

    mock_regen.assert_called_once_with(wiki)
