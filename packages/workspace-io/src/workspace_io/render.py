"""Render the workspace-level CLAUDE.md from a template + manifest.

The template ships in `workspace_io/assets/CLAUDE.md.template`. Two
regions are recognised:

- Free-form prose anywhere outside the marker pair below — preserved on
  re-render.
- The auto-rendered plugin list bounded by:

      <!-- workspace-io:auto:plugins:start -->
      <!-- workspace-io:auto:plugins:end -->

  Refreshed from `.graph-wiki.yaml` on every render.

If `.graph-wiki.yaml` is missing, render is a no-op (the caller is responsible
for creating the manifest first).
"""
from __future__ import annotations

import re
from pathlib import Path

from workspace_io import manifest
from workspace_io.paths import manifest_path

AUTO_START = "<!-- workspace-io:auto:plugins:start -->"
AUTO_END = "<!-- workspace-io:auto:plugins:end -->"

_BLOCK_RE = re.compile(re.escape(AUTO_START) + r".*?" + re.escape(AUTO_END), re.DOTALL)

_TEMPLATE_PATH = Path(__file__).resolve().parent / "assets" / "CLAUDE.md.template"

# Known plugins → human-readable detail pointer. Unknown plugins are
# listed with no pointer.
_PLUGIN_POINTERS: dict[str, str] = {
    "code-wiki-agent": "see [`wiki/CLAUDE.md`](wiki/CLAUDE.md)",
}


def _render_plugin_list(plugins: list[dict]) -> str:
    """Return the markdown body that goes between the auto-block markers."""
    if not plugins:
        return "_No plugins registered yet._"
    lines = []
    for entry in plugins:
        name = entry["name"]
        pointer = _PLUGIN_POINTERS.get(name)
        if pointer:
            lines.append(f"- `{name}` — {pointer}")
        else:
            lines.append(f"- `{name}`")
    return "\n".join(lines)


def _render_full_template(workspace: Path, plugins: list[dict], initialized_at: str) -> str:
    """Render the full template once (first-create path)."""
    text = _TEMPLATE_PATH.read_text(encoding="utf-8")
    text = text.replace("{{WORKSPACE_PATH}}", str(workspace))
    text = text.replace("{{INITIALIZED_AT}}", initialized_at)
    text = text.replace("{{PLUGIN_LIST}}", _render_plugin_list(plugins))
    return text


def _refresh_auto_block(text: str, plugins: list[dict]) -> str:
    """Replace the existing auto block in `text` with a freshly rendered one."""
    block = (
        AUTO_START
        + "\n"
        + _render_plugin_list(plugins)
        + "\n"
        + AUTO_END
    )
    return _BLOCK_RE.sub(lambda _: block, text, count=1)


def render_workspace_claude_md(workspace: Path) -> None:
    """Write or refresh `<workspace>/CLAUDE.md`.

    Reads `<workspace>/.graph-wiki.yaml` for the plugin list. If the manifest
    doesn't exist, returns silently — the caller is responsible for
    creating it before calling this function.

    On first call (CLAUDE.md absent), renders the full template.
    On subsequent calls, refreshes only the auto-bounded plugin block
    and preserves all surrounding prose.
    """
    workspace = Path(workspace)
    mpath = manifest_path(workspace)
    if not mpath.exists():
        return
    data = manifest.read(mpath)
    plugins = data.get("plugins", [])
    initialized_at = data.get("initialized_at", "")

    claude_md = workspace / "CLAUDE.md"
    if not claude_md.exists():
        claude_md.write_text(
            _render_full_template(workspace, plugins, initialized_at),
            encoding="utf-8",
        )
        return

    text = claude_md.read_text(encoding="utf-8")
    if AUTO_START in text and AUTO_END in text:
        new_text = _refresh_auto_block(text, plugins)
    else:
        # User deleted the markers — append a fresh auto block at the end
        # rather than rewriting their hand-edited file.
        block = AUTO_START + "\n" + _render_plugin_list(plugins) + "\n" + AUTO_END + "\n"
        sep = "" if text.endswith("\n") else "\n"
        new_text = text + sep + "\n" + block
    if new_text != text:
        claude_md.write_text(new_text, encoding="utf-8")
