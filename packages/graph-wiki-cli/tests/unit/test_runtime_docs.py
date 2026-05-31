from __future__ import annotations

import json
import re
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[4]
DOC_PATHS = [
    REPO_ROOT / "README.md",
    REPO_ROOT / "plugins" / "graph-wiki" / "README.md",
    REPO_ROOT / "plugins" / "graph-wiki" / "CLAUDE.md",
    REPO_ROOT / "plugins" / "graph-wiki" / ".claude-plugin" / "plugin.json",
]


STALE_RUNTIME_PATTERNS = [
    re.compile(r"uv\s+run\s+(?:--package\s+\S+\s+)?graph-wiki-agent\b"),
    re.compile(r"\bgraph-wiki-agent\s+<cmd>\b"),
    re.compile(r"\bgraph-wiki-agent\s+--help\b"),
    re.compile(r"\bgraph-wiki-agent\s+(?:bootstrap|scan|ingest|query|lint|log)\b"),
    re.compile(r"graph-wiki-agent[^\n.]*Bedrock CLI companion", re.IGNORECASE),
    re.compile(r"routes?\s+to\s+`?graph-wiki-agent`?", re.IGNORECASE),
]


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def test_current_help_examples_use_package_scoped_gw_entrypoint() -> None:
    """User-facing help snippets should teach the package-scoped gw command."""
    root_readme = _read(REPO_ROOT / "README.md")
    plugin_readme = _read(REPO_ROOT / "plugins" / "graph-wiki" / "README.md")

    assert "uv run --package graph-wiki-cli gw --help" in root_readme
    assert "uv run --package graph-wiki-cli gw --help" in plugin_readme
    assert "uv run --package graph-wiki-cli gw scan" in plugin_readme


def test_current_runtime_docs_do_not_advertise_stale_executable() -> None:
    """Active runtime prose must not direct users or shims to graph-wiki-agent."""
    failures: list[str] = []
    for path in DOC_PATHS:
        text = _read(path)
        rel = path.relative_to(REPO_ROOT)
        for pattern in STALE_RUNTIME_PATTERNS:
            for match in pattern.finditer(text):
                line_no = text.count("\n", 0, match.start()) + 1
                failures.append(f"{rel}:{line_no}: {match.group(0)!r}")

    assert not failures, "stale executable guidance found:\n" + "\n".join(failures)


def test_plugin_identity_is_allowed_but_bedrock_description_names_gw() -> None:
    """The plugin remains named graph-wiki; only runtime companion wording moved to gw."""
    plugin_json = json.loads(_read(REPO_ROOT / "plugins" / "graph-wiki" / ".claude-plugin" / "plugin.json"))
    plugin_claude = _read(REPO_ROOT / "plugins" / "graph-wiki" / "CLAUDE.md")

    assert plugin_json["name"] == "graph-wiki"
    assert "/graph-wiki:bootstrap" in plugin_claude
    assert "graph-wiki:scanner" in plugin_claude

    description = plugin_json["description"]
    assert "gw from graph-wiki-cli" in description
    assert "graph-wiki-agent" not in description
