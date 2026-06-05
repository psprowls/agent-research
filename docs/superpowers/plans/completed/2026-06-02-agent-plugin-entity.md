# `agent-plugin` Entity Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the consumer-side `plugin` graph entity (sourced from `.graph-wiki.yaml plugins[]`) with a producer-side `agent_plugin` entity that documents a claude-code plugin **under development** in the repo — its commands, agents, skills, scripts, hooks, and bundled MCP servers — as a regenerable, drift-aware inventory rendered into a wiki page.

**Architecture:** A new filesystem-walking detector in `graph-io` finds `.claude-plugin/plugin.json` directories, parses each plugin's components into a structured inventory, and emits **one** `kind:agent_plugin` graph node per plugin (repo-scoped URI `agent_plugin:{org}/{repo}/{name}`) with the inventory in `attrs_json`. The `wiki-io` entity writer renders that node to a page whose component sections are deterministic markdown tables. Components are NOT graph nodes/edges — they ride as attrs and render as tables; each carries a stable id so a future promotion to real nodes (Option C) is non-breaking. The narrator prose for the `## How it fits together` section is **deferred to a follow-up plan** (this plan ships a static TODO placeholder there); the existing `## Narrative` placeholder is likewise left for that follow-up.

**Tech Stack:** Python 3.11+, `uv` workspace, SQLite code graph (`graph-io`), `wiki-io` entity writer, `typer` CLI (`graph-wiki-cli`), `pytest` + `pyyaml` (already a `graph-io` dep). No new third-party dependency.

---

## Naming convention (read first)

The spec's prose writes the entity name as "agent-plugin" (hyphen). The **machine identifiers** in this plan use the underscore form `agent_plugin`, matching the existing codebase convention for multi-word kinds (`test_suite`, `entry_point`):

| Surface | Value |
|---|---|
| Graph node `kind` / `ADMITTED_KINDS` member / frontmatter `kind:` | `agent_plugin` |
| Graph URI prefix | `agent_plugin:{org}/{repo}/{name}` |
| Component stable-id prefixes | `command:` `agent:` `skill:` `script:` `hook:` `mcp_server:` |
| Template filename (derived via `kind.replace('_','-')`) | `entity-agent-plugin.md` |
| Wiki page filename stem (`_FILENAME_PREFIX_BY_URI_PREFIX["agent_plugin"]`) | `agent-plugin_{name}` (hyphen, per spec §4) |
| Index `KIND_LABELS` label | `Agent Plugins` |
| CLI subcommand | `gw graph describe-agent-plugin` |

This is a **full rename + repurpose**: the old `plugin` kind, its URI builder, queries, template, CLI command, and `.graph-wiki.yaml plugins[]` ingestion are all removed. Per `.claude/rules/backward-compatibility.md` there is **no data migration** — the user delete-and-rebuilds the wiki/graph. The `.graph-wiki.yaml plugins[]` array itself stays on disk (it is also the `make_llm` role config, a different consumer); only its use as an *entity source* is removed.

## Component inventory data model (shared across tasks)

The detector stores this dict in the node's `attrs["components"]`; `describe_agent_plugin` unpacks it; the entity writer renders it. Every component dict carries a stable `id`.

```python
# attrs["components"] shape — all six keys always present (empty list when none found)
{
    "commands":    [{"id": "command:org/repo/plugin/scan", "name": "scan", "description": "..."}],
    "agents":      [{"id": "agent:org/repo/plugin/scanner", "name": "scanner",
                     "description": "...", "model": "sonnet", "tools": ["Read", "Write"]}],
    "skills":      [{"id": "skill:org/repo/plugin/graph-wiki", "name": "graph-wiki", "description": "..."}],
    "scripts":     [{"id": "script:org/repo/plugin/skills/graph-wiki/scripts/lint_wiki.py",
                     "path": "skills/graph-wiki/scripts/lint_wiki.py", "lang": "python"}],
    "hooks":       [{"id": "hook:org/repo/plugin/PreToolUse", "event": "PreToolUse", "matchers": ["Bash"]}],
    "mcp_servers": [{"id": "mcp_server:org/repo/plugin/graph-wiki", "name": "graph-wiki", "command": "uv run ..."}],
}
```

---

## File Structure

**graph-io (`packages/graph-io/`)**
- Create: `src/graph_io/agent_plugins.py` — filesystem detector (replaces `plugins.py`). Walks `.claude-plugin/plugin.json`, parses components, emits one `agent_plugin` node per plugin.
- Delete: `src/graph_io/plugins.py` — consumer ingestion (retired).
- Modify: `src/graph_io/uri.py` — replace `plugin_uri(name)` with repo-scoped `agent_plugin_uri(ctx, name)`.
- Modify: `src/graph_io/queries.py` — `_VALID_KINDS`, `AgentPluginDescription`, `describe_agent_plugin`, `list_agent_plugins` (remove `plugin` equivalents).
- Modify: `src/graph_io/packages.py` — exclude `.claude-plugin/plugin.json` plugin-root dirs from the package emitter.
- Modify: `src/graph_io/update.py:312-321` — swap `plugins.emit(...)` → `agent_plugins.emit(...)`.
- Tests: `tests/test_agent_plugins.py` (new, replaces `tests/test_plugins.py`), `tests/test_uri.py`, `tests/test_queries.py`, `tests/test_packages.py` (exclusion test).

**wiki-io (`packages/wiki-io/`)**
- Create: `src/wiki_io/assets/page-templates/entity-agent-plugin.md` (replaces `entity-plugin.md`).
- Delete: `src/wiki_io/assets/page-templates/entity-plugin.md`.
- Modify: `src/wiki_io/entity_writer.py` — `ADMITTED_KINDS`, `_URI_PREFIX_BY_KIND`, `_FILENAME_PREFIX_BY_URI_PREFIX`, `_kind_list_fns`, `scanner_frontmatter_for_node` branch, new `_agent_plugin_table_variables` helper + its wiring in `write_entities`.
- Modify: `src/wiki_io/index_generator.py` — `_PLACEABLE_KINDS`, `BY_KIND_ORDER`, `KIND_LABELS`, `kind_to_list_fn`, `_compute_qualifying_domains` branch, import.
- Modify: `src/wiki_io/link_rewriter.py:248` — `_LIST_FNS` key.
- Tests: `tests/conftest.py`, `tests/test_entity_writer.py`, `tests/test_assets.py`, `tests/test_short_filename.py`, `tests/test_index_generator.py`, `tests/test_link_rewriter_build_table.py`, `tests/integration/test_entity_writer_integration.py`.

**graph-wiki-cli (`packages/graph-wiki-cli/`)**
- Create: `src/graph_wiki_cli/graph_cli/q_describe_agent_plugin.py` (replaces `q_describe_plugin.py`).
- Delete: `src/graph_wiki_cli/graph_cli/q_describe_plugin.py`.
- Modify: `src/graph_wiki_cli/graph_cli/main.py:31,217-220` — import + command rename.
- Tests: `tests/graph_cli/test_cli_describe.py`.

**Out of scope (do NOT touch):** the narrator (`graph-wiki-core/.../scan.py` `build_entity_narrative_prompt` / `_NARRATIVE_RELATION_LABELS`) — prose is deferred; the bootstrap *container* templates and `render_container("plugins", ...)` path (a separate legacy mechanism, see `test_bootstrap_e2e_no_broken_links.py`); `.graph-wiki.yaml plugins[]` writing in bootstrap (`test_commands_bootstrap.py`) — that is `make_llm` role config; `references/wiki-schema.md` (its "plugin" refs are directory-layout, not the entity kind — verified, no change needed).

---

## Task 1: URI builder — `agent_plugin_uri`

**Files:**
- Modify: `packages/graph-io/src/graph_io/uri.py:48-51`
- Test: `packages/graph-io/tests/test_uri.py:19,89-90`

- [ ] **Step 1: Update the failing test**

In `packages/graph-io/tests/test_uri.py`, replace the import of `plugin_uri` (line 19) with `agent_plugin_uri`, and replace `test_plugin_uri` (lines 89-90) with:

```python
def test_agent_plugin_uri() -> None:
    ctx = RepoContext(org="test", repo="repo")
    assert agent_plugin_uri(ctx, "graph-wiki") == "agent_plugin:test/repo/graph-wiki"
```

(`RepoContext` is already imported in this test module — it is used by other URI tests. If it is not, add `RepoContext` to the existing `from graph_io.uri import (...)` block.)

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run --package graph-io pytest packages/graph-io/tests/test_uri.py::test_agent_plugin_uri -v`
Expected: FAIL with `ImportError: cannot import name 'agent_plugin_uri'`.

- [ ] **Step 3: Implement the builder**

In `packages/graph-io/src/graph_io/uri.py`, replace lines 48-51:

```python
# v1.8 concept-level kinds (Phase 42 D-04): not repo-scoped, so no RepoContext.
# Phase 51 PKGFAM-02: package_family entity kind retired; builder removed.
def plugin_uri(name: str) -> str:
    return f"plugin:{name}"
```

with:

```python
# agent_plugin entities are repo-scoped (a development artifact lives in a
# specific repo), unlike the retired concept-level `plugin:{name}`.
def agent_plugin_uri(ctx: RepoContext, name: str) -> str:
    return f"agent_plugin:{ctx.org}/{ctx.repo}/{name}"
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run --package graph-io pytest packages/graph-io/tests/test_uri.py -v`
Expected: PASS (all URI tests green).

- [ ] **Step 5: Commit**

```bash
git add packages/graph-io/src/graph_io/uri.py packages/graph-io/tests/test_uri.py
git commit -m "feat(graph-io): repo-scoped agent_plugin_uri replaces plugin_uri"
```

---

## Task 2: graph-io queries — `agent_plugin` kind, description, list

**Files:**
- Modify: `packages/graph-io/src/graph_io/queries.py:9-33` (`_VALID_KINDS`), `181-187` (`PluginDescription`), `830-850` (`describe_plugin`), `902-904` (`list_plugins`)
- Test: `packages/graph-io/tests/test_queries.py:1133-1140,1231-1259,1470-1484`

- [ ] **Step 1: Update the failing tests**

In `packages/graph-io/tests/test_queries.py`:

(a) Replace `test_valid_kinds_includes_dependency_plugin` (around lines 1133-1140):

```python
def test_valid_kinds_includes_dependency_and_agent_plugin(conn: sqlite3.Connection) -> None:
    """_VALID_KINDS carries dependency + agent_plugin; legacy plugin is gone."""
    assert "dependency" in queries._VALID_KINDS
    assert "agent_plugin" in queries._VALID_KINDS
    assert "plugin" not in queries._VALID_KINDS
    rows = queries.find(conn, kind="agent_plugin")
    assert rows == []
```

(b) Replace `test_describe_plugin_returns_plugin_description` and `test_describe_plugin_returns_none_when_missing` (around lines 1231-1259) with:

```python
def test_describe_agent_plugin_returns_description(conn: sqlite3.Connection) -> None:
    """describe_agent_plugin returns AgentPluginDescription from node attrs."""
    from source_parser.projections.graph import GraphNode, GraphRecords
    from graph_io import upsert

    upsert.upsert_records(conn, GraphRecords(
        nodes=[
            GraphNode(
                kind="agent_plugin",
                name="graph-wiki",
                path=None,
                line=None,
                attrs={
                    "uri": "agent_plugin:test/repo/graph-wiki",
                    "ecosystem": "claude-code",
                    "version": "0.1.0",
                    "description": "A wiki plugin.",
                    "components": {
                        "commands": [{"id": "command:test/repo/graph-wiki/scan",
                                      "name": "scan", "description": "Walk the monorepo."}],
                        "agents": [], "skills": [], "scripts": [],
                        "hooks": [], "mcp_servers": [],
                    },
                },
            ),
        ],
        edges=[],
    ))
    p = queries.describe_agent_plugin(conn, name="graph-wiki")
    assert p is not None
    assert p.name == "graph-wiki"
    assert p.uri == "agent_plugin:test/repo/graph-wiki"
    assert p.ecosystem == "claude-code"
    assert p.version == "0.1.0"
    assert p.description == "A wiki plugin."
    assert p.commands == [{"id": "command:test/repo/graph-wiki/scan",
                           "name": "scan", "description": "Walk the monorepo."}]
    assert p.agents == [] and p.mcp_servers == []


def test_describe_agent_plugin_returns_none_when_missing(conn: sqlite3.Connection) -> None:
    assert queries.describe_agent_plugin(conn, name="nonexistent") is None
```

(c) Replace `test_list_plugins_alphabetical` (around lines 1470-1484):

```python
def test_list_agent_plugins_alphabetical(conn: sqlite3.Connection) -> None:
    """list_agent_plugins returns alphabetically-sorted agent_plugin NodeRecords."""
    from source_parser.projections.graph import GraphNode, GraphRecords
    from graph_io import upsert

    upsert.upsert_records(conn, GraphRecords(
        nodes=[
            GraphNode(kind="agent_plugin", name="zeta", path=None, line=None,
                      attrs={"ecosystem": "claude-code", "uri": "agent_plugin:o/r/zeta"}),
            GraphNode(kind="agent_plugin", name="alpha", path=None, line=None,
                      attrs={"ecosystem": "claude-code", "uri": "agent_plugin:o/r/alpha"}),
        ],
        edges=[],
    ))
    assert [n.name for n in queries.list_agent_plugins(conn)] == ["alpha", "zeta"]
```

(Match the exact construction style already used by the surrounding tests — if those tests `upsert` via a shared helper or a module-level `GraphNode` import, reuse it instead of the inline imports shown here.)

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run --package graph-io pytest packages/graph-io/tests/test_queries.py -k "agent_plugin or valid_kinds" -v`
Expected: FAIL — `AttributeError: module 'graph_io.queries' has no attribute 'describe_agent_plugin'` (and `_VALID_KINDS` still contains `plugin`).

- [ ] **Step 3: Implement the query surface**

In `packages/graph-io/src/graph_io/queries.py`:

(a) In `_VALID_KINDS` (lines 9-33), replace the line:

```python
        "plugin",
```

with:

```python
        # agent-plugin entity: a claude-code plugin under development in this repo.
        "agent_plugin",
```

(b) Replace the `PluginDescription` dataclass (lines 181-187):

```python
@dataclass(frozen=True)
class PluginDescription:
    """Description of a `plugin` node (Phase 43 D-03 + D-05)."""
    name: str
    uri: str
    ecosystem: str
```

with:

```python
@dataclass(frozen=True)
class AgentPluginDescription:
    """Description of an `agent_plugin` node.

    Carries the plugin manifest fields plus the component inventory parsed at
    graph-build time (commands/agents/skills/scripts/hooks/mcp_servers). Each
    component is a plain dict with a stable `id`; they are NOT graph nodes.
    """
    name: str
    uri: str
    ecosystem: str
    version: str
    description: str
    commands: list[dict] = field(default_factory=list)
    agents: list[dict] = field(default_factory=list)
    skills: list[dict] = field(default_factory=list)
    scripts: list[dict] = field(default_factory=list)
    hooks: list[dict] = field(default_factory=list)
    mcp_servers: list[dict] = field(default_factory=list)
```

(`field` and `dataclass` are already imported at the top of this module: `from dataclasses import dataclass, field`.)

(c) Replace `describe_plugin` (lines 830-850):

```python
def describe_plugin(
    conn: sqlite3.Connection, *, name: str
) -> PluginDescription | None:
    ...
```

with:

```python
def describe_agent_plugin(
    conn: sqlite3.Connection, *, name: str
) -> AgentPluginDescription | None:
    """Return the description of an agent_plugin node, or None.

    `conn` must be opened read-only.
    """
    row = conn.execute(
        "SELECT name, attrs_json, uri FROM nodes "
        "WHERE kind='agent_plugin' AND name = ?",
        (name,),
    ).fetchone()
    if not row:
        return None
    plugin_name, attrs_json, uri = row
    attrs = json.loads(attrs_json) if attrs_json else {}
    comp = attrs.get("components") or {}
    return AgentPluginDescription(
        name=plugin_name,
        uri=uri or "",
        ecosystem=attrs.get("ecosystem", ""),
        version=attrs.get("version", ""),
        description=attrs.get("description", ""),
        commands=list(comp.get("commands") or []),
        agents=list(comp.get("agents") or []),
        skills=list(comp.get("skills") or []),
        scripts=list(comp.get("scripts") or []),
        hooks=list(comp.get("hooks") or []),
        mcp_servers=list(comp.get("mcp_servers") or []),
    )
```

(d) Replace `list_plugins` (lines 902-904):

```python
def list_plugins(conn: sqlite3.Connection) -> list[NodeRecord]:
    """List all Plugin nodes alphabetically. `conn` must be read-only."""
    return _list_by_kind(conn, "plugin")
```

with:

```python
def list_agent_plugins(conn: sqlite3.Connection) -> list[NodeRecord]:
    """List all agent_plugin nodes alphabetically. `conn` must be read-only."""
    return _list_by_kind(conn, "agent_plugin")
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run --package graph-io pytest packages/graph-io/tests/test_queries.py -k "agent_plugin or valid_kinds" -v`
Expected: PASS.

(Other modules still import `describe_plugin`/`list_plugins`/`PluginDescription` — they are fixed in Tasks 5-10. The whole `graph-io` suite is green after this task because nothing inside `graph-io` imports those symbols except `plugins.py`, which is deleted in Task 3. Run `uv run --package graph-io pytest packages/graph-io/tests/test_queries.py -v` to confirm no `test_queries` regressions.)

- [ ] **Step 5: Commit**

```bash
git add packages/graph-io/src/graph_io/queries.py packages/graph-io/tests/test_queries.py
git commit -m "feat(graph-io): agent_plugin query surface replaces plugin"
```

---

## Task 3: graph-io detector — `agent_plugins.emit`

This is the core of the feature. It walks `.claude-plugin/plugin.json`, parses six component types, and emits one `agent_plugin` node per plugin.

**Files:**
- Create: `packages/graph-io/src/graph_io/agent_plugins.py`
- Delete: `packages/graph-io/src/graph_io/plugins.py`
- Create: `packages/graph-io/tests/test_agent_plugins.py`
- Delete: `packages/graph-io/tests/test_plugins.py`

- [ ] **Step 1: Write the failing tests**

Create `packages/graph-io/tests/test_agent_plugins.py`:

```python
"""agent_plugin detector: .claude-plugin/plugin.json -> kind:agent_plugin nodes."""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path

import pytest

from graph_io import agent_plugins, store
from graph_io.uri import RepoContext

_CTX = RepoContext(org="test", repo="repo")


@pytest.fixture()
def conn(tmp_path: Path) -> sqlite3.Connection:
    db = tmp_path / "code.db"
    c = store.connect(db, create=True)
    yield c
    c.close()


def _make_plugin(root: Path) -> Path:
    """Lay down a minimal but complete plugin tree under root/plugins/demo."""
    pdir = root / "plugins" / "demo"
    (pdir / ".claude-plugin").mkdir(parents=True)
    (pdir / ".claude-plugin" / "plugin.json").write_text(json.dumps({
        "name": "demo", "version": "1.2.3", "description": "A demo plugin.",
    }))
    (pdir / "commands").mkdir()
    (pdir / "commands" / "scan.md").write_text(
        "---\nname: scan\ndescription: Walk the monorepo.\n---\n# /demo:scan\n"
    )
    (pdir / "agents").mkdir()
    (pdir / "agents" / "scanner.md").write_text(
        "---\nname: scanner\ndescription: Sub-agent.\nmodel: sonnet\n"
        "tools: [Read, Write]\n---\nbody\n"
    )
    (pdir / "skills" / "demo-skill").mkdir(parents=True)
    (pdir / "skills" / "demo-skill" / "SKILL.md").write_text(
        "---\nname: demo-skill\ndescription: A skill.\n---\nbody\n"
    )
    (pdir / "scripts").mkdir()
    (pdir / "scripts" / "lint.py").write_text("print('hi')\n")
    (pdir / "hooks").mkdir()
    (pdir / "hooks" / "hooks.json").write_text(json.dumps({
        "hooks": {"PreToolUse": [{"matcher": "Bash", "hooks": [{"type": "command"}]}]}
    }))
    (pdir / ".mcp.json").write_text(json.dumps({
        "mcpServers": {"demo-server": {"command": "uv run demo-mcp"}}
    }))
    return pdir


def test_emit_no_plugins_is_silent(tmp_path: Path, conn: sqlite3.Connection) -> None:
    agent_plugins.emit(conn, repo_root=tmp_path, ctx=_CTX)
    n = conn.execute("SELECT COUNT(*) FROM nodes WHERE kind='agent_plugin'").fetchone()[0]
    assert n == 0


def test_emit_creates_one_node_with_manifest_fields(tmp_path: Path, conn: sqlite3.Connection) -> None:
    _make_plugin(tmp_path)
    agent_plugins.emit(conn, repo_root=tmp_path, ctx=_CTX)
    rows = conn.execute(
        "SELECT name, attrs_json, uri FROM nodes WHERE kind='agent_plugin'"
    ).fetchall()
    assert len(rows) == 1
    name, attrs_json, uri = rows[0]
    attrs = json.loads(attrs_json)
    assert name == "demo"
    assert uri == "agent_plugin:test/repo/demo"
    assert attrs["ecosystem"] == "claude-code"
    assert attrs["version"] == "1.2.3"
    assert attrs["description"] == "A demo plugin."


def test_emit_parses_all_component_types(tmp_path: Path, conn: sqlite3.Connection) -> None:
    _make_plugin(tmp_path)
    agent_plugins.emit(conn, repo_root=tmp_path, ctx=_CTX)
    attrs = json.loads(conn.execute(
        "SELECT attrs_json FROM nodes WHERE kind='agent_plugin'"
    ).fetchone()[0])
    c = attrs["components"]

    assert c["commands"] == [
        {"id": "command:test/repo/demo/scan", "name": "scan",
         "description": "Walk the monorepo."}
    ]
    assert c["agents"] == [
        {"id": "agent:test/repo/demo/scanner", "name": "scanner",
         "description": "Sub-agent.", "model": "sonnet", "tools": ["Read", "Write"]}
    ]
    assert c["skills"] == [
        {"id": "skill:test/repo/demo/demo-skill", "name": "demo-skill",
         "description": "A skill."}
    ]
    assert c["scripts"] == [
        {"id": "script:test/repo/demo/scripts/lint.py",
         "path": "scripts/lint.py", "lang": "python"}
    ]
    assert c["hooks"] == [
        {"id": "hook:test/repo/demo/PreToolUse", "event": "PreToolUse",
         "matchers": ["Bash"]}
    ]
    assert c["mcp_servers"] == [
        {"id": "mcp_server:test/repo/demo/demo-server", "name": "demo-server",
         "command": "uv run demo-mcp"}
    ]


def test_emit_tolerates_missing_components(tmp_path: Path, conn: sqlite3.Connection) -> None:
    """A bare plugin (manifest only) emits a node with all-empty component lists."""
    pdir = tmp_path / "plugins" / "bare" / ".claude-plugin"
    pdir.mkdir(parents=True)
    (pdir / "plugin.json").write_text(json.dumps({"name": "bare"}))
    agent_plugins.emit(conn, repo_root=tmp_path, ctx=_CTX)
    attrs = json.loads(conn.execute(
        "SELECT attrs_json FROM nodes WHERE kind='agent_plugin'"
    ).fetchone()[0])
    assert attrs["version"] == ""
    assert attrs["components"] == {
        "commands": [], "agents": [], "skills": [],
        "scripts": [], "hooks": [], "mcp_servers": [],
    }


def test_emit_skips_vendored_plugins(tmp_path: Path, conn: sqlite3.Connection) -> None:
    """A plugin under a skip-dir (e.g. node_modules) is not emitted."""
    vend = tmp_path / "node_modules" / "vendored" / ".claude-plugin"
    vend.mkdir(parents=True)
    (vend / "plugin.json").write_text(json.dumps({"name": "vendored"}))
    agent_plugins.emit(conn, repo_root=tmp_path, ctx=_CTX)
    n = conn.execute("SELECT COUNT(*) FROM nodes WHERE kind='agent_plugin'").fetchone()[0]
    assert n == 0


def test_emit_skips_entries_without_name(tmp_path: Path, conn: sqlite3.Connection) -> None:
    pdir = tmp_path / "plugins" / "noname" / ".claude-plugin"
    pdir.mkdir(parents=True)
    (pdir / "plugin.json").write_text(json.dumps({"version": "1.0.0"}))
    agent_plugins.emit(conn, repo_root=tmp_path, ctx=_CTX)
    n = conn.execute("SELECT COUNT(*) FROM nodes WHERE kind='agent_plugin'").fetchone()[0]
    assert n == 0
```

Then delete the old test file:

```bash
git rm packages/graph-io/tests/test_plugins.py
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run --package graph-io pytest packages/graph-io/tests/test_agent_plugins.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'graph_io.agent_plugins'`.

- [ ] **Step 3: Implement the detector**

Create `packages/graph-io/src/graph_io/agent_plugins.py`:

```python
"""agent_plugin detector: walks `.claude-plugin/plugin.json` directories and
emits one `kind:agent_plugin` node per plugin, with its component inventory
(commands/agents/skills/scripts/hooks/mcp_servers) carried in attrs_json.

Replaces the retired consumer-side `plugins.py` (which read `.graph-wiki.yaml
plugins[]`). agent_plugin nodes have NO edges — components are inventory, not
graph nodes (see the design spec, "Why components are prose/attrs, not edges").
Each component carries a stable id so a future promotion to real graph nodes
(Option C) is a non-breaking extension.
"""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path
from typing import Any

import yaml

from source_parser.projections.graph import GraphNode, GraphRecords

from graph_io import _ignore, upsert
from graph_io.uri import RepoContext, agent_plugin_uri

# Map file extension -> a coarse language label for the Scripts inventory.
_LANG_BY_SUFFIX: dict[str, str] = {
    ".py": "python",
    ".js": "javascript",
    ".ts": "typescript",
    ".sh": "shell",
    ".bash": "shell",
    ".rb": "ruby",
    ".go": "go",
}


def _read_frontmatter(path: Path) -> dict:
    """Parse the leading `---\\n...\\n---` YAML frontmatter block of a markdown
    file. Returns {} when the file has no frontmatter, is unreadable, or the
    block is not a mapping. Avoids a python-frontmatter dependency — graph-io
    already ships pyyaml."""
    try:
        text = path.read_text(encoding="utf-8")
    except OSError:
        return {}
    if not text.startswith("---"):
        return {}
    parts = text.split("---", 2)
    if len(parts) < 3:
        return {}
    try:
        data = yaml.safe_load(parts[1])
    except yaml.YAMLError:
        return {}
    return data if isinstance(data, dict) else {}


def _read_json(path: Path) -> dict:
    """Read a JSON file into a dict; {} on any error or non-dict top level."""
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return data if isinstance(data, dict) else {}


def _as_str_list(value: Any) -> list[str]:
    """Coerce a frontmatter value to a list of strings (tools/skills may be a
    YAML list or a single string)."""
    if isinstance(value, list):
        return [str(v) for v in value]
    if value is None or value == "":
        return []
    return [str(value)]


def _parse_commands(plugin_dir: Path, id_for) -> list[dict]:
    out: list[dict] = []
    for p in sorted(plugin_dir.glob("commands/*.md")):
        fm = _read_frontmatter(p)
        name = str(fm.get("name") or p.stem)
        out.append({
            "id": id_for("command", name),
            "name": name,
            "description": str(fm.get("description") or ""),
        })
    return out


def _parse_agents(plugin_dir: Path, id_for) -> list[dict]:
    out: list[dict] = []
    for p in sorted(plugin_dir.glob("agents/*.md")):
        fm = _read_frontmatter(p)
        name = str(fm.get("name") or p.stem)
        out.append({
            "id": id_for("agent", name),
            "name": name,
            "description": str(fm.get("description") or ""),
            "model": str(fm.get("model") or ""),
            "tools": _as_str_list(fm.get("tools")),
        })
    return out


def _parse_skills(plugin_dir: Path, id_for) -> list[dict]:
    out: list[dict] = []
    for p in sorted(plugin_dir.glob("skills/*/SKILL.md")):
        fm = _read_frontmatter(p)
        name = str(fm.get("name") or p.parent.name)
        out.append({
            "id": id_for("skill", name),
            "name": name,
            "description": str(fm.get("description") or ""),
        })
    return out


def _parse_scripts(plugin_dir: Path, id_for) -> list[dict]:
    scripts_dir = plugin_dir / "scripts"
    if not scripts_dir.is_dir():
        return []
    out: list[dict] = []
    for p in sorted(scripts_dir.rglob("*")):
        if not p.is_file():
            continue
        if "__pycache__" in p.parts:
            continue
        rel = p.relative_to(plugin_dir).as_posix()
        out.append({
            "id": id_for("script", rel),
            "path": rel,
            "lang": _LANG_BY_SUFFIX.get(p.suffix, ""),
        })
    return out


def _parse_hooks(plugin_dir: Path, id_for) -> list[dict]:
    data = _read_json(plugin_dir / "hooks" / "hooks.json")
    # claude-code hooks.json nests events under a top-level "hooks" map; tolerate
    # either {"hooks": {Event: [...]}} or a bare {Event: [...]} top level.
    events = data.get("hooks") if isinstance(data.get("hooks"), dict) else data
    out: list[dict] = []
    if not isinstance(events, dict):
        return out
    for event, entries in sorted(events.items()):
        matchers: list[str] = []
        if isinstance(entries, list):
            for entry in entries:
                if isinstance(entry, dict) and entry.get("matcher") is not None:
                    matchers.append(str(entry["matcher"]))
        out.append({
            "id": id_for("hook", str(event)),
            "event": str(event),
            "matchers": matchers,
        })
    return out


def _parse_mcp_servers(plugin_dir: Path, id_for) -> list[dict]:
    data = _read_json(plugin_dir / ".mcp.json")
    servers = data.get("mcpServers")
    out: list[dict] = []
    if not isinstance(servers, dict):
        return out
    for srv_name, cfg in sorted(servers.items()):
        command = ""
        if isinstance(cfg, dict):
            command = str(cfg.get("command") or "")
        out.append({
            "id": id_for("mcp_server", str(srv_name)),
            "name": str(srv_name),
            "command": command,
        })
    return out


def emit(
    conn: sqlite3.Connection,
    *,
    repo_root: Path,
    ctx: RepoContext,
    skip_dirs: frozenset[str] | None = None,
) -> None:
    """Walk `repo_root` for `.claude-plugin/plugin.json`, emit one
    `kind:agent_plugin` node per plugin with its component inventory in attrs.

    Honors the same vendored/fixture skip-dir filtering as the package walker
    (`graph_io._ignore`). Silently tolerates plugins with no components and
    manifests missing a `name`. Nodes carry `path=None` (like the retired
    plugin nodes); whole-plugin removal is covered by delete-and-rebuild per
    the project backward-compatibility rule.
    """
    repo_root = Path(repo_root).resolve()
    if skip_dirs is None:
        skip_dirs = _ignore.load_skip_dirs(repo_root)

    nodes: list[GraphNode] = []
    for manifest_path in sorted(repo_root.rglob(".claude-plugin/plugin.json")):
        rel = manifest_path.relative_to(repo_root).as_posix()
        if _ignore.should_skip(rel, skip_dirs):
            continue
        manifest = _read_json(manifest_path)
        name = manifest.get("name")
        if not name:
            continue
        name = str(name)
        plugin_dir = manifest_path.parent.parent  # .claude-plugin/ sits inside it

        def id_for(kind: str, leaf: str, _name: str = name) -> str:
            return f"{kind}:{ctx.org}/{ctx.repo}/{_name}/{leaf}"

        components = {
            "commands": _parse_commands(plugin_dir, id_for),
            "agents": _parse_agents(plugin_dir, id_for),
            "skills": _parse_skills(plugin_dir, id_for),
            "scripts": _parse_scripts(plugin_dir, id_for),
            "hooks": _parse_hooks(plugin_dir, id_for),
            "mcp_servers": _parse_mcp_servers(plugin_dir, id_for),
        }
        attrs: dict[str, Any] = {
            "uri": agent_plugin_uri(ctx, name),
            "ecosystem": "claude-code",
            "name": name,
            "version": str(manifest.get("version") or ""),
            "description": str(manifest.get("description") or ""),
            "components": components,
        }
        nodes.append(GraphNode(kind="agent_plugin", name=name, path=None, line=None, attrs=attrs))

    if nodes:
        upsert.upsert_records(conn, GraphRecords(nodes=nodes, edges=[]))
```

Then delete the retired module:

```bash
git rm packages/graph-io/src/graph_io/plugins.py
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run --package graph-io pytest packages/graph-io/tests/test_agent_plugins.py -v`
Expected: PASS (all 6 tests).

- [ ] **Step 5: Commit**

```bash
git add packages/graph-io/src/graph_io/agent_plugins.py packages/graph-io/tests/test_agent_plugins.py
git add -u packages/graph-io/src/graph_io/plugins.py packages/graph-io/tests/test_plugins.py
git commit -m "feat(graph-io): agent_plugins filesystem detector replaces plugins ingestion"
```

---

## Task 4: Package emitter — exclude plugin-root dirs

Per spec decision 4: a directory with `.claude-plugin/plugin.json` reclassifies as `agent_plugin`, not `package`. A manifest (`pyproject.toml`/`package.json`) located **at the plugin root** must be skipped by the package emitter. Nested real packages (with their own manifest in a subdirectory) are still detected.

**Files:**
- Modify: `packages/graph-io/src/graph_io/packages.py:154-170` (`_discover_manifests`)
- Test: `packages/graph-io/tests/test_packages.py`

- [ ] **Step 1: Write the failing test**

Append to `packages/graph-io/tests/test_packages.py` (reuse the file's existing fixtures/imports; if it has no `conn` fixture, mirror the one in `test_agent_plugins.py`):

```python
def test_plugin_root_manifest_excluded_from_packages(tmp_path, conn) -> None:
    """A pyproject.toml AT a .claude-plugin/ dir is NOT emitted as a package;
    a nested real package under the plugin IS."""
    import json
    from graph_io import packages
    from graph_io.uri import RepoContext

    pdir = tmp_path / "plugins" / "demo"
    (pdir / ".claude-plugin").mkdir(parents=True)
    (pdir / ".claude-plugin" / "plugin.json").write_text(json.dumps({"name": "demo"}))
    # A manifest at the plugin ROOT — must be skipped.
    (pdir / "pyproject.toml").write_text('[project]\nname = "demo-plugin-pkg"\nversion = "0"\n')
    # A nested real workspace package — must still be detected.
    nested = pdir / "scripts" / "helper"
    nested.mkdir(parents=True)
    (nested / "pyproject.toml").write_text('[project]\nname = "demo-helper"\nversion = "0"\n')

    packages.refresh(conn, repo_root=tmp_path, ctx=RepoContext(org="t", repo="r"))
    names = {r[0] for r in conn.execute("SELECT name FROM nodes WHERE kind='package'").fetchall()}
    assert "demo-plugin-pkg" not in names
    assert "demo-helper" in names
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run --package graph-io pytest packages/graph-io/tests/test_packages.py::test_plugin_root_manifest_excluded_from_packages -v`
Expected: FAIL — `assert "demo-plugin-pkg" not in names` fails (the plugin-root manifest is currently emitted as a package).

- [ ] **Step 3: Implement the exclusion**

In `packages/graph-io/src/graph_io/packages.py`, add a helper above `_discover_manifests` (after `_should_skip`, around line 71):

```python
def _is_plugin_root(manifest_dir: Path) -> bool:
    """True when `manifest_dir` is a claude-code plugin root (has
    `.claude-plugin/plugin.json`). Such a manifest is owned by the
    agent_plugin detector, not the package emitter (spec decision 4)."""
    return (manifest_dir / ".claude-plugin" / "plugin.json").exists()
```

Then in `_discover_manifests` (lines 154-170), add the guard to both loops. Change:

```python
    for manifest_path in repo_root.rglob("pyproject.toml"):
        if _should_skip(manifest_path, repo_root, skip_dirs):
            continue
        info = _read_pyproject(manifest_path)
        if info:
            found.append((manifest_path.parent, info))
    for manifest_path in repo_root.rglob("package.json"):
        if _should_skip(manifest_path, repo_root, skip_dirs):
            continue
        info = _read_package_json(manifest_path)
        if info:
            found.append((manifest_path.parent, info))
```

to:

```python
    for manifest_path in repo_root.rglob("pyproject.toml"):
        if _should_skip(manifest_path, repo_root, skip_dirs):
            continue
        if _is_plugin_root(manifest_path.parent):
            continue
        info = _read_pyproject(manifest_path)
        if info:
            found.append((manifest_path.parent, info))
    for manifest_path in repo_root.rglob("package.json"):
        if _should_skip(manifest_path, repo_root, skip_dirs):
            continue
        if _is_plugin_root(manifest_path.parent):
            continue
        info = _read_package_json(manifest_path)
        if info:
            found.append((manifest_path.parent, info))
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run --package graph-io pytest packages/graph-io/tests/test_packages.py -v`
Expected: PASS (new test + no regressions).

- [ ] **Step 5: Commit**

```bash
git add packages/graph-io/src/graph_io/packages.py packages/graph-io/tests/test_packages.py
git commit -m "feat(graph-io): exclude plugin-root manifests from package emitter"
```

---

## Task 5: Wire the detector into the graph build

**Files:**
- Modify: `packages/graph-io/src/graph_io/update.py:312-321`

- [ ] **Step 1: Swap the emit call and deferred import**

In `packages/graph-io/src/graph_io/update.py`, in the deferred-import block (lines 312-319), replace `plugins` with `agent_plugins`:

```python
                from graph_io import (  # noqa: PLC0415
                    agent_plugins,
                    derived_edges,
                    domains,
                    entry_points,
                    structural_nodes,
                    test_suites,
                )
```

Then replace the emit call (line 321):

```python
                plugins.emit(conn, workspace_root=workspace, ctx=ctx)
```

with:

```python
                agent_plugins.emit(conn, repo_root=repo_root, ctx=ctx)
```

(`repo_root` is already in scope in this function — it is used on the surrounding lines, e.g. `structural_nodes.emit(conn, repo_root=repo_root, ...)`. The detector walks the filesystem, so it takes `repo_root`, not `workspace`. Note: `agent_plugin` nodes have `path=None`, so the full-mode cleanup DELETE at lines 301-306 — gated on `path IS NOT NULL` — never touches them; the subsequent `emit` upserts the current set.)

- [ ] **Step 2: Run the graph-io suite to verify wiring**

Run: `uv run --package graph-io pytest packages/graph-io/tests/ -v`
Expected: PASS for the whole `graph-io` suite (including `test_update.py` and any `seeded_db`-backed tests — the fixture monorepo at `tests/fixtures/sample_monorepo` has no `.claude-plugin/plugin.json`, so the detector is a no-op there).

- [ ] **Step 3: Commit**

```bash
git add packages/graph-io/src/graph_io/update.py
git commit -m "feat(graph-io): run agent_plugins detector in the graph build"
```

---

## Task 6: wiki-io entity writer — admit `agent_plugin`, render inventory tables

**Files:**
- Modify: `packages/wiki-io/src/wiki_io/entity_writer.py:60-70,80-93,148-157,548-557,631-635,705-869`
- Modify: `packages/wiki-io/tests/conftest.py:10-18,38-46,98-102,130-132`
- Modify: `packages/wiki-io/tests/test_entity_writer.py:30-50,507,520-521,532,541,653-689`

- [ ] **Step 1: Update the conftest fixture**

In `packages/wiki-io/tests/conftest.py`:

(a) In the import block (lines 10-18), replace `PluginDescription` with `AgentPluginDescription`:

```python
from graph_io.queries import (
    AgentPluginDescription,
    DependencyDescription,
    DomainDescription,
    NodeRecord,
    PackageDescription,
    RepoDescription,
    SuiteDescription,
)
```

(b) In `MockGraphConn.__init__` (lines 38-46), change the `"plugin"` key to `"agent_plugin"`:

```python
        self._nodes: dict[str, list[NodeRecord]] = {
            "repository": [],
            "domain": [],
            "package": [],
            "app": [],
            "agent_plugin": [],
            "dependency": [],
            "test_suite": [],
        }
```

(c) Replace the plugin node seed (lines 98-102):

```python
    conn.set_nodes("agent_plugin", [
        NodeRecord(kind="agent_plugin", name="graph-wiki", path=None, line=None,
                   attrs={"uri": "agent_plugin:local/agent-research/graph-wiki",
                          "ecosystem": "claude-code", "version": "0.1.0",
                          "description": "A wiki plugin.",
                          "components": {
                              "commands": [{"id": "command:local/agent-research/graph-wiki/scan",
                                            "name": "scan", "description": "Walk the monorepo."}],
                              "agents": [], "skills": [], "scripts": [],
                              "hooks": [], "mcp_servers": [],
                          }}),
    ])
```

(d) Replace the plugin description seed (lines 130-132):

```python
    conn.set_description("agent_plugin", "graph-wiki", AgentPluginDescription(
        name="graph-wiki", uri="agent_plugin:local/agent-research/graph-wiki",
        ecosystem="claude-code", version="0.1.0", description="A wiki plugin.",
        commands=[{"id": "command:local/agent-research/graph-wiki/scan",
                   "name": "scan", "description": "Walk the monorepo."}],
        agents=[], skills=[], scripts=[], hooks=[], mcp_servers=[],
    ))
```

- [ ] **Step 2: Update the entity-writer tests**

In `packages/wiki-io/tests/test_entity_writer.py`:

(a) In `test_admitted_kinds_*` (lines 30-50), replace `"plugin"` with `"agent_plugin"` in the `expected` frozenset, and the disjointness assertion list comment stays. The block becomes:

```python
    expected = frozenset({
        "repository",
        "domain",
        "package",
        "app",
        "agent_plugin",
        "dependency",
        "test_suite",
    })
    assert ADMITTED_KINDS == expected
```

Also change the assertion `assert "package_family" not in ADMITTED_KINDS` to additionally assert `assert "plugin" not in ADMITTED_KINDS` on the following line.

(b) In `_wire_mock_queries` (lines 507, 520-521), replace the plugin bindings:

```python
    monkeypatch.setattr(q_module, "list_agent_plugins", lambda c: c.list_nodes("agent_plugin"))
```
and
```python
    monkeypatch.setattr(q_module, "describe_agent_plugin",
                        lambda c, *, name: c.get_description("agent_plugin", name))
```

(c) In `test_write_entities_creates_pages_per_admitted_kind` (line 532, 541), update the comment to `... + 1 agent_plugin = 7` and the filename assertion:

```python
    assert (entities / "agent-plugin_graph-wiki.md").exists()
```

(d) In the deletion test that seeds `demo-plugin` (lines 653-689), replace the `set_nodes("plugin", ...)` block and the expected filename:

```python
    mock_graph_conn.set_nodes("agent_plugin", [
        NodeRecord(
            kind="agent_plugin", name="demo-plugin", path=None, line=None,
            attrs={"uri": "agent_plugin:local/agent-research/demo-plugin",
                   "ecosystem": "claude-code", "version": "", "description": "",
                   "components": {"commands": [], "agents": [], "skills": [],
                                  "scripts": [], "hooks": [], "mcp_servers": []}},
        ),
    ])
    mock_graph_conn.set_description("agent_plugin", "demo-plugin", AgentPluginDescription(
        name="demo-plugin", uri="agent_plugin:local/agent-research/demo-plugin",
        ecosystem="claude-code", version="", description="",
    ))
```

and the expected filename string `"plugin_demo-plugin.md"` → `"agent-plugin_demo-plugin.md"`. (Add `AgentPluginDescription` to this test module's `from graph_io.queries import ...`.) For every other `set_nodes("plugin", [])` / `set_nodes("plugin", ...)` occurrence in this file (lines 714, 750, 802), change the kind string to `"agent_plugin"`.

- [ ] **Step 3: Run tests to verify they fail**

Run: `uv run --package wiki-io pytest packages/wiki-io/tests/test_entity_writer.py -v`
Expected: FAIL — `ADMITTED_KINDS` still contains `plugin`; `list_agent_plugins`/`describe_agent_plugin` attrs missing on the mock; `agent-plugin_graph-wiki.md` not produced.

- [ ] **Step 4: Implement the entity-writer changes**

In `packages/wiki-io/src/wiki_io/entity_writer.py`:

(a) `ADMITTED_KINDS` (lines 60-70): replace `"plugin",` with `"agent_plugin",`.

(b) `_URI_PREFIX_BY_KIND` (lines 80-93): replace the `"plugin": "plugin",` entry with:

```python
    "agent_plugin": "agent_plugin",
```

(c) `_FILENAME_PREFIX_BY_URI_PREFIX` (lines 148-156): replace `"plugin": "plugin",` with:

```python
    "agent_plugin": "agent-plugin",
```

(d) `_kind_list_fns` (lines 548-557): replace the plugin lambda:

```python
        "agent_plugin": lambda conn: _queries.list_agent_plugins(conn),
```

(e) `scanner_frontmatter_for_node` plugin branch (lines 631-635): replace:

```python
    elif kind == "plugin":
        d = _queries.describe_plugin(conn, name=node.name)
        if d is not None:
            fm["ecosystem"] = d.ecosystem
```

with:

```python
    elif kind == "agent_plugin":
        d = _queries.describe_agent_plugin(conn, name=node.name)
        if d is not None:
            fm["ecosystem"] = d.ecosystem
            fm["version"] = d.version
```

(f) Add the inventory-table helper. Insert this function just above `write_entities` (before line 705):

```python
def _md_escape(cell: str) -> str:
    """Escape a markdown-table cell: pipes and newlines would break the row."""
    return str(cell).replace("|", "\\|").replace("\n", " ").strip()


def _md_table(headers: list[str], rows: list[list[str]]) -> str:
    """Render a GitHub-flavored markdown table, or `_None._` when there are no
    rows (so the template token is always substituted to a non-empty value and
    no residual `{{...}}` survives)."""
    if not rows:
        return "_None._"
    head = "| " + " | ".join(headers) + " |"
    sep = "| " + " | ".join("---" for _ in headers) + " |"
    body = "\n".join(
        "| " + " | ".join(_md_escape(c) for c in row) + " |" for row in rows
    )
    return f"{head}\n{sep}\n{body}"


def _agent_plugin_table_variables(conn: Any, node: Any) -> dict[str, str]:
    """Build the six `{{*_table}}` substitution values for an agent_plugin page
    from its component inventory. Returns `_None._` per section when empty."""
    d = _queries.describe_agent_plugin(conn, name=node.name)
    if d is None:
        empty = "_None._"
        return {
            "commands_table": empty, "agents_table": empty, "skills_table": empty,
            "scripts_table": empty, "hooks_table": empty, "mcp_servers_table": empty,
        }
    return {
        "commands_table": _md_table(
            ["Command", "Description"],
            [[c.get("name", ""), c.get("description", "")] for c in d.commands],
        ),
        "agents_table": _md_table(
            ["Agent", "Model", "Tools", "Description"],
            [[a.get("name", ""), a.get("model", ""),
              ", ".join(a.get("tools", []) or []), a.get("description", "")]
             for a in d.agents],
        ),
        "skills_table": _md_table(
            ["Skill", "Description"],
            [[s.get("name", ""), s.get("description", "")] for s in d.skills],
        ),
        "scripts_table": _md_table(
            ["Script", "Language"],
            [[s.get("path", ""), s.get("lang", "")] for s in d.scripts],
        ),
        "hooks_table": _md_table(
            ["Event", "Matchers"],
            [[h.get("event", ""), ", ".join(h.get("matchers", []) or [])] for h in d.hooks],
        ),
        "mcp_servers_table": _md_table(
            ["Server", "Command"],
            [[m.get("name", ""), m.get("command", "")] for m in d.mcp_servers],
        ),
    }
```

(g) Wire the helper into `write_entities`. In the `variables` construction block (lines 791-798), after the `variables: dict[str, str] = {...}` literal and before `new_content = _render_entity_page(...)` (line 799), add:

```python
                    if kind == "agent_plugin":
                        variables.update(_agent_plugin_table_variables(conn, node))
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `uv run --package wiki-io pytest packages/wiki-io/tests/test_entity_writer.py -v`
Expected: PASS. (The template created in Task 7 is required for the page-creation tests to render without a missing-template error — if Task 7 is not yet done, the `test_write_entities_creates_pages_per_admitted_kind` test will report a `<missing-template:agent_plugin>` error. Run Task 7 before re-running this step if executing tasks strictly in order; the helper/branch logic above is otherwise independently testable.)

- [ ] **Step 6: Commit**

```bash
git add packages/wiki-io/src/wiki_io/entity_writer.py packages/wiki-io/tests/conftest.py packages/wiki-io/tests/test_entity_writer.py
git commit -m "feat(wiki-io): admit agent_plugin kind + render component inventory tables"
```

---

## Task 7: Entity template — `entity-agent-plugin.md`

**Files:**
- Create: `packages/wiki-io/src/wiki_io/assets/page-templates/entity-agent-plugin.md`
- Delete: `packages/wiki-io/src/wiki_io/assets/page-templates/entity-plugin.md`
- Test: `packages/wiki-io/tests/test_assets.py:27-38`

- [ ] **Step 1: Update the failing test**

In `packages/wiki-io/tests/test_assets.py`, in `test_core_entity_templates_still_present` (lines 27-38), replace `"entity-plugin.md",` in the expected set with `"entity-agent-plugin.md",`. Add a new test below it:

```python
def test_no_legacy_plugin_template() -> None:
    """The repurposed entity-plugin.md is gone; entity-agent-plugin.md replaces it."""
    names = _template_names()
    assert "entity-plugin.md" not in names
    assert "entity-agent-plugin.md" in names
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run --package wiki-io pytest packages/wiki-io/tests/test_assets.py -v`
Expected: FAIL — `entity-agent-plugin.md` missing; `entity-plugin.md` still present.

- [ ] **Step 3: Create the template, delete the old one**

Create `packages/wiki-io/src/wiki_io/assets/page-templates/entity-agent-plugin.md`:

```markdown
---
title: <Agent Plugin Name>
uri: <agent-plugin-uri>
kind: agent_plugin
ecosystem: <ecosystem>
graph_name: <graph-name>
last_scan_at: <YYYY-MM-DD>
updated: <YYYY-MM-DD>
---

# {{agent_plugin_name}}

## Narrative
_(scanner will populate on next scan)_

## Purpose
> TODO: <One paragraph: what this plugin does, which host consumes it, what feature surface it adds.>

## Commands
{{commands_table}}

## Agents
{{agents_table}}

## Skills
{{skills_table}}

## Scripts
{{scripts_table}}

## Hooks
{{hooks_table}}

## MCP servers
{{mcp_servers_table}}

## How it fits together
> TODO: <Inferred cross-component relationships — populated by a follow-up narrator pass.>

## Concepts
- [[concepts/<concept>]]

## Decisions
- [[adrs/<id>-<slug>]]

## Contrasts / alternatives
- [[concepts/<a>-vs-<b>]]
```

Then delete the old template:

```bash
git rm packages/wiki-io/src/wiki_io/assets/page-templates/entity-plugin.md
```

(Note: the H1 token must be `{{agent_plugin_name}}` — `write_entities` sets `variables[f"{kind}_name"] = node.name`, and `kind` is `agent_plugin`. The `## Purpose` and `## How it fits together` TODOs use `<...>` instruction placeholders, which `_render_entity_page` leaves untouched; only `{{...}}` data tokens are substituted. The six `{{*_table}}` tokens are all provided by `_agent_plugin_table_variables`, so no residual-token TODO marker fires.)

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run --package wiki-io pytest packages/wiki-io/tests/test_assets.py packages/wiki-io/tests/test_entity_writer.py -v`
Expected: PASS (assets test + the entity-writer page-creation tests from Task 6 now render the template).

- [ ] **Step 5: Commit**

```bash
git add packages/wiki-io/src/wiki_io/assets/page-templates/entity-agent-plugin.md packages/wiki-io/tests/test_assets.py
git add -u packages/wiki-io/src/wiki_io/assets/page-templates/entity-plugin.md
git commit -m "feat(wiki-io): entity-agent-plugin.md template with inventory sections"
```

---

## Task 8: Index generator + link rewriter rename

**Files:**
- Modify: `packages/wiki-io/src/wiki_io/index_generator.py:47-56,78-90,218-222,359-365`
- Modify: `packages/wiki-io/src/wiki_io/link_rewriter.py:244-251`
- Test: `packages/wiki-io/tests/test_index_generator.py` (many `plugin` refs), `packages/wiki-io/tests/test_link_rewriter_build_table.py:30-31,88`

- [ ] **Step 1: Update the failing tests**

In `packages/wiki-io/tests/test_index_generator.py`, do a scoped rename of the `plugin` entity to `agent_plugin` (these are graph-fixture specs and assertions):
- Every fixture node tuple `("plugin", "graph-wiki", {"uri": "plugin:graph-wiki", ...})` → `("agent_plugin", "graph-wiki", {"uri": "agent_plugin:o/r/graph-wiki", "ecosystem": "claude-code"})`.
- `assert BY_KIND_ORDER == ("app", "package", "plugin")` (line 94) → `("app", "package", "agent_plugin")`.
- `assert KIND_LABELS["plugin"] == "Plugins"` (line 102) → `assert KIND_LABELS["agent_plugin"] == "Agent Plugins"`.
- `_compute_qualifying_domains(conn, kind="plugin", name="graph-wiki")` (line 263) → `kind="agent_plugin"`.
- The `kinds == ["package", "dependency", "plugin"]` assertion (line 354) → `["package", "dependency", "agent_plugin"]`.
- `e.kind == "plugin"` checks (lines 337, ~552) → `"agent_plugin"`.
- `plugin_slug = "plugin_graph-wiki"` (line 927) → `agent_plugin_slug = "agent-plugin_graph-wiki"` and update the three following references (`text.count(...)`, `text.find(...)`, the ordering assertion). `text.find("### Plugins")` (line 930) → `text.find("### Agent Plugins")`.
- Rename the test functions `test_plugin_always_empty`, `test_plugin_always_in_by_kind`, `test_plugin_always_by_kind` to `test_agent_plugin_*` for clarity (optional but keeps intent legible).

In `packages/wiki-io/tests/test_link_rewriter_build_table.py` (lines 30-31, 88):
- `"plugin": [ _node("plugin", "graph-wiki", "plugin:graph-wiki") ]` → `"agent_plugin": [ _node("agent_plugin", "graph-wiki", "agent_plugin:o/r/graph-wiki") ]`.
- `assert "plugin/graph-wiki/overview" in table` (line 88): this asserts the legacy→new rewrite entry. Replace with an assertion against the new short-form target slug:
  ```python
  assert "agent-plugin_graph-wiki" in table
  ```
  (Confirm against the surrounding assertions in that test how `table` keys/values are shaped — match their form. The point is the agent_plugin entity now rewrites to the `agent-plugin_<name>` short filename.)

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run --package wiki-io pytest packages/wiki-io/tests/test_index_generator.py packages/wiki-io/tests/test_link_rewriter_build_table.py -v`
Expected: FAIL (label/order/list-fn lookups still keyed on `plugin`).

- [ ] **Step 3: Implement the rename in source**

In `packages/wiki-io/src/wiki_io/index_generator.py`:
- Import (line 54): `list_plugins,` → `list_agent_plugins,`.
- `_PLACEABLE_KINDS` (lines 78-80): `"app", "package", "test_suite", "dependency", "plugin",` → `..., "agent_plugin",`.
- `BY_KIND_ORDER` (line 82): `("app", "package", "plugin")` → `("app", "package", "agent_plugin")`.
- `KIND_LABELS` (lines 84-90): replace `"plugin": "Plugins",` with `"agent_plugin": "Agent Plugins",`.
- `_compute_qualifying_domains` (lines 218-222): `if kind == "plugin":` → `if kind == "agent_plugin":`, and update the `ValueError` message string `"...test_suite/dependency/plugin are placeable; got..."` → `"...test_suite/dependency/agent_plugin are placeable; got..."`.
- `kind_to_list_fn` (lines 359-365): replace `"plugin": list_plugins,` with `"agent_plugin": list_agent_plugins,`.

In `packages/wiki-io/src/wiki_io/link_rewriter.py` (`_LIST_FNS`, line 248): replace `"plugin": _queries.list_plugins,` with `"agent_plugin": _queries.list_agent_plugins,`.

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run --package wiki-io pytest packages/wiki-io/tests/test_index_generator.py packages/wiki-io/tests/test_link_rewriter_build_table.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add packages/wiki-io/src/wiki_io/index_generator.py packages/wiki-io/src/wiki_io/link_rewriter.py packages/wiki-io/tests/test_index_generator.py packages/wiki-io/tests/test_link_rewriter_build_table.py
git commit -m "feat(wiki-io): rename plugin->agent_plugin in index + link rewriter"
```

---

## Task 9: `short_filename` test coverage

**Files:**
- Test: `packages/wiki-io/tests/test_short_filename.py:39,134,148-149`

- [ ] **Step 1: Update the tests**

In `packages/wiki-io/tests/test_short_filename.py`:
- The parametrized case `("plugin:graph-wiki", {}, "plugin_graph-wiki")` (line 39): replace with `("agent_plugin:org/repo/graph-wiki", {}, "agent-plugin_graph-wiki")`.
- In the hypothesis strategy template list (line 134): `"plugin",` → `"agent_plugin",`.
- In the strategy branch (lines 148-149): `if template == "plugin": return f"plugin:{draw(_FRAGMENT)}"` → `if template == "agent_plugin": return f"agent_plugin:{draw(_FRAGMENT)}/{draw(_FRAGMENT)}/{draw(_FRAGMENT)}"` (repo-scoped URI now has org/repo/name segments; match the segment shape the other repo-scoped templates in this file use, e.g. `pkg`).

- [ ] **Step 2: Run tests to verify they pass**

Run: `uv run --package wiki-io pytest packages/wiki-io/tests/test_short_filename.py -v`
Expected: PASS — `short_filename("agent_plugin:org/repo/graph-wiki", frozenset())` returns `agent-plugin_graph-wiki` (prefix `agent-plugin` from `_FILENAME_PREFIX_BY_URI_PREFIX`, last path segment `graph-wiki`). No source change needed — Task 6 already added the prefix mapping.

- [ ] **Step 3: Commit**

```bash
git add packages/wiki-io/tests/test_short_filename.py
git commit -m "test(wiki-io): short_filename covers agent_plugin prefix"
```

---

## Task 10: CLI — `gw graph describe-agent-plugin`

**Files:**
- Create: `packages/graph-wiki-cli/src/graph_wiki_cli/graph_cli/q_describe_agent_plugin.py`
- Delete: `packages/graph-wiki-cli/src/graph_wiki_cli/graph_cli/q_describe_plugin.py`
- Modify: `packages/graph-wiki-cli/src/graph_wiki_cli/graph_cli/main.py:31,217-220`
- Test: `packages/graph-wiki-cli/tests/graph_cli/test_cli_describe.py:1,22,27-49,80-90,119-133`

- [ ] **Step 1: Update the failing test**

In `packages/graph-wiki-cli/tests/graph_cli/test_cli_describe.py`:
- Import (line 22): `q_describe_plugin,` → `q_describe_agent_plugin,`.
- The fixture `workspace_with_deps_and_plugin` (lines 27-49) runs `gw graph update --full` on a workspace. For the agent_plugin entity to exist, the fixture must lay down a `.claude-plugin/plugin.json` **in the repo tree** rather than (or in addition to) the `.graph-wiki.yaml plugins[]` entry. Add to the fixture, before the `update --full` call:
  ```python
  import json as _json
  pdir = workspace / "plugins" / "graph-wiki" / ".claude-plugin"
  pdir.mkdir(parents=True, exist_ok=True)
  (pdir / "plugin.json").write_text(_json.dumps({"name": "graph-wiki", "version": "0.1.0"}))
  ```
  (Match the fixture's existing variable name for the repo/workspace root — it builds a repo with a manifest at `<repo>/graph-wiki/.graph-wiki.yaml`; place the plugin dir under the same repo root the graph build walks. If the fixture's repo root differs from `workspace`, use that path.)
- `_ns_plugin` helper (line 80-90): keep, it just builds an argparse-style namespace with `name`/`fmt`/`workspace`.
- `test_cg_describe_plugin_smoke` (lines 119-126): rename to `test_cg_describe_agent_plugin_smoke`, call `q_describe_agent_plugin.run(args)`, and assert the human output contains `name:      graph-wiki` and `ecosystem: claude-code`.
- `test_cg_describe_plugin_not_found` (lines 128-133): rename to `test_cg_describe_agent_plugin_not_found`, call `q_describe_agent_plugin.run(...)`, assert `"error: agent_plugin not found:"` in stderr.

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run --package graph-wiki-cli pytest packages/graph-wiki-cli/tests/graph_cli/test_cli_describe.py -v`
Expected: FAIL — `ImportError: cannot import name 'q_describe_agent_plugin'`.

- [ ] **Step 3: Implement the CLI query + command**

Create `packages/graph-wiki-cli/src/graph_wiki_cli/graph_cli/q_describe_agent_plugin.py`:

```python
"""gw graph describe-agent-plugin <name>"""

from __future__ import annotations

import dataclasses
import json as _json
import sys

from workspace_io.paths import graph_dir

from graph_io import exit_codes, queries, store


def run(args: object) -> int:
    db = graph_dir(args.workspace) / "code.db"
    try:
        conn = store.read_only_connect(db)
    except store.GraphNotInitializedError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return exit_codes.NOT_INITIALIZED
    except store.SchemaMismatchError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return exit_codes.SCHEMA_MISMATCH
    try:
        desc = queries.describe_agent_plugin(conn, name=args.name)
    finally:
        conn.close()
    if desc is None:
        print(f"error: agent_plugin not found: {args.name}", file=sys.stderr)
        return exit_codes.GENERIC
    if args.fmt == "json":
        print(_json.dumps(dataclasses.asdict(desc), default=str))
    else:
        print(f"name:        {desc.name}")
        print(f"ecosystem:   {desc.ecosystem}")
        print(f"version:     {desc.version}")
        print(f"uri:         {desc.uri}")
        print(f"commands:    {len(desc.commands)}")
        print(f"agents:      {len(desc.agents)}")
        print(f"skills:      {len(desc.skills)}")
        print(f"scripts:     {len(desc.scripts)}")
        print(f"hooks:       {len(desc.hooks)}")
        print(f"mcp_servers: {len(desc.mcp_servers)}")
    return exit_codes.SUCCESS
```

Delete the old module:

```bash
git rm packages/graph-wiki-cli/src/graph_wiki_cli/graph_cli/q_describe_plugin.py
```

In `packages/graph-wiki-cli/src/graph_wiki_cli/graph_cli/main.py`:
- Import (line 31): `q_describe_plugin,` → `q_describe_agent_plugin,`.
- Command (lines 217-220): replace

```python
@graph_app.command(name="describe-plugin")
def describe_plugin_cmd(ctx: typer.Context, name: str) -> None:
    """Describe a plugin."""
    _run(q_describe_plugin, ctx, name=name)
```

with:

```python
@graph_app.command(name="describe-agent-plugin")
def describe_agent_plugin_cmd(ctx: typer.Context, name: str) -> None:
    """Describe an agent plugin (claude-code plugin under development)."""
    _run(q_describe_agent_plugin, ctx, name=name)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run --package graph-wiki-cli pytest packages/graph-wiki-cli/tests/graph_cli/test_cli_describe.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add packages/graph-wiki-cli/src/graph_wiki_cli/graph_cli/q_describe_agent_plugin.py packages/graph-wiki-cli/src/graph_wiki_cli/graph_cli/main.py packages/graph-wiki-cli/tests/graph_cli/test_cli_describe.py
git add -u packages/graph-wiki-cli/src/graph_wiki_cli/graph_cli/q_describe_plugin.py
git commit -m "feat(cli): describe-agent-plugin replaces describe-plugin"
```

---

## Task 11: Integration test — end-to-end roundtrip

**Files:**
- Modify: `packages/wiki-io/tests/integration/test_entity_writer_integration.py:29,62,81-99,110,122`

- [ ] **Step 1: Update the integration test**

In `packages/wiki-io/tests/integration/test_entity_writer_integration.py`:
- Import (line 29): `from graph_io import packages, plugins, structural_nodes` → `from graph_io import agent_plugins, packages, structural_nodes`.
- The fixture builds a `root` repo with `.graph-wiki.yaml ... plugins: [graph-wiki]` (lines 81-88). Replace the dependency on `plugins.emit` with the filesystem detector. First, lay down a real plugin tree in the fixture `root` (before the emit calls, near line 96):
  ```python
  import json as _json
  pdir = root / "plugins" / "graph-wiki" / ".claude-plugin"
  pdir.mkdir(parents=True, exist_ok=True)
  (pdir / "plugin.json").write_text(_json.dumps(
      {"name": "graph-wiki", "version": "0.1.0", "description": "A wiki plugin."}
  ))
  ```
- Replace the emit call (line 99) `plugins.emit(conn, workspace_root=workspace, ctx=CTX)` with:
  ```python
  agent_plugins.emit(conn, repo_root=root, ctx=CTX)
  ```
  (Use the fixture's repo-root variable — here assumed `root`; confirm the name the fixture uses for the directory it runs the graph build against.)
- Expected-page comment (line 110): `... + 1 plugin = 7` → `... + 1 agent_plugin = 7`.
- Filename assertion (line 122): `assert (entities / "plugin_graph-wiki.md").exists()` → `assert (entities / "agent-plugin_graph-wiki.md").exists()`.

(The `.graph-wiki.yaml plugins: [graph-wiki]` entry can stay in the fixture — it is harmless role config and no longer drives entity creation.)

- [ ] **Step 2: Run the integration test**

Run: `uv run --package wiki-io pytest packages/wiki-io/tests/integration/test_entity_writer_integration.py -v`
Expected: PASS — 7 entity pages including `agent-plugin_graph-wiki.md`, with rendered (empty) inventory tables showing `_None._`.

- [ ] **Step 3: Run the full affected suites**

Run:
```bash
uv run --package graph-io pytest packages/graph-io/tests/ -q
uv run --package wiki-io pytest packages/wiki-io/tests/ -q
uv run --package graph-wiki-cli pytest packages/graph-wiki-cli/tests/ -q
```
Expected: all PASS. Investigate any remaining `plugin` reference surfaced as a failure (e.g. a snapshot/syrupy file referencing `plugin_graph-wiki.md` — regenerate with `--snapshot-update` only after confirming the new `agent-plugin_*` output is correct).

- [ ] **Step 4: End-to-end smoke against this repo (manual verification)**

Run a real graph build + entity write against this repo, which contains `plugins/graph-wiki/.claude-plugin/plugin.json`:
```bash
uv run --package graph-wiki-cli gw graph update --full
uv run --package graph-wiki-cli gw graph describe-agent-plugin graph-wiki
```
Expected: `describe-agent-plugin graph-wiki` prints `ecosystem: claude-code`, `version: 0.1.0`, and non-zero counts for `commands` (6), `agents` (4), and `skills` (1), with `scripts` reflecting the files under `skills/graph-wiki/scripts/`. (`hooks`/`mcp_servers` are 0 — none present.) This confirms the detector parses the repo's own plugin correctly.

- [ ] **Step 5: Commit**

```bash
git add packages/wiki-io/tests/integration/test_entity_writer_integration.py
git commit -m "test(wiki-io): integration roundtrip emits agent-plugin entity page"
```

---

## Follow-up (out of scope for this plan)

- **Narrator prose** for `## How it fits together` (and the `## Narrative` body) on agent_plugin pages — requires extending the narrator (`graph-wiki-core/.../scan.py`) to feed the component inventory into the prompt and, for the second section, a generalized section-injection. Tracked separately per the design decision recorded for this plan.
- **Option C** — promoting components to first-class graph nodes/edges. Component stable ids are already captured in attrs, making this a non-breaking extension.
- **Reworking the graph-wiki plugin's own scan path** to adopt graph-based scanning.

---

## Self-Review notes

- **Spec coverage:** detector replacing `plugins.py` (T3), repo-scoped URI (T1), `_VALID_KINDS`/queries (T2), package-emitter exclusion (T4), build wiring (T5), `ADMITTED_KINDS`/prefix maps/scanner branch/inventory tables (T6), template (T7), six component types incl. hooks + MCP (T3 parsing, T6 rendering, T7 sections), stable ids (T3), no migration (uses delete-and-rebuild; T11 smoke). Narrator prose explicitly deferred per user decision.
- **Type consistency:** `AgentPluginDescription` fields (T2) match the dicts produced by the detector (T3) and consumed by `_agent_plugin_table_variables` (T6). `describe_agent_plugin`/`list_agent_plugins` names are consistent across queries (T2), entity_writer (T6), index_generator + link_rewriter (T8), and CLI (T10). Kind string `agent_plugin` and filename prefix `agent-plugin` are consistent everywhere.
- **Consumers beyond the spec's key-files table** (`index_generator`, `link_rewriter`, CLI `describe-plugin`, ~7 test files) are covered by T8/T10/T11 — the spec's table omitted them.
