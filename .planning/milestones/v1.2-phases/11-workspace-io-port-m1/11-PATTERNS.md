# Phase 11: workspace-io Port (M1) — Pattern Map

**Mapped:** 2026-05-17
**Files analyzed:** 28 (10 new source modules + 12 new test files + 3 modified agent-research files + 3 modified call-site files)
**Analogs found:** 28 / 28

---

## File Classification

| New/Modified File | Role | Data Flow | Closest Analog | Match Quality |
|---|---|---|---|---|
| `packages/workspace-io/pyproject.toml` | config | — | `packages/vault-io/pyproject.toml` + `lattice-workspace/pyproject.toml` | exact (hatchling variant) |
| `packages/workspace-io/src/workspace_io/__init__.py` | module | — | `lattice_workspace/__init__.py` | exact |
| `packages/workspace-io/src/workspace_io/config.py` | service | request-response | `lattice_workspace/config.py` | exact (port) |
| `packages/workspace-io/src/workspace_io/manifest.py` | service | file-I/O | `lattice_workspace/manifest.py` | exact (port, v1 branch dropped) |
| `packages/workspace-io/src/workspace_io/init.py` | service | file-I/O | `lattice_workspace/init.py` | exact (port, `write_schema` removed) |
| `packages/workspace-io/src/workspace_io/paths.py` | utility | — | `lattice_workspace/paths.py` | exact (verbatim) |
| `packages/workspace-io/src/workspace_io/render.py` | service | file-I/O | `lattice_workspace/render.py` | exact (port, markers renamed) |
| `packages/workspace-io/src/workspace_io/versions.py` | service | file-I/O | `lattice_workspace/versions.py` | exact (port) |
| `packages/workspace-io/src/workspace_io/_local_config.py` | utility | file-I/O | `lattice_workspace/_local_config.py` | exact (verbatim) |
| `packages/workspace-io/src/workspace_io/assets/CLAUDE.md.template` | config | — | `lattice_workspace/assets/CLAUDE.md.template` | exact (prose rebranded) |
| `packages/workspace-io/tests/test_config.py` | test | — | `lattice_workspace/tests/test_config.py` | exact (rebrand + new strict-raises test) |
| `packages/workspace-io/tests/test_manifest.py` | test | — | `lattice_workspace/tests/test_manifest.py` | exact (rebrand) |
| `packages/workspace-io/tests/test_manifest_v2_roundtrip.py` | test | — | `lattice_workspace/tests/test_manifest_v2_roundtrip.py` | exact (rebrand) |
| `packages/workspace-io/tests/test_init.py` | test | — | `lattice_workspace/tests/test_init.py` | exact (rebrand, drop `test_creates_work_schema`) |
| `packages/workspace-io/tests/test_init_records_version.py` | test | — | `lattice_workspace/tests/test_init_records_version.py` | exact (rebrand) |
| `packages/workspace-io/tests/test_init_bumps_version.py` | test | — | `lattice_workspace/tests/test_init_bumps_version.py` | exact (rebrand) |
| `packages/workspace-io/tests/test_paths.py` | test | — | `lattice_workspace/tests/test_paths.py` | exact (rebrand) |
| `packages/workspace-io/tests/test_local_config.py` | test | — | `lattice_workspace/tests/test_local_config.py` | exact (rebrand) |
| `packages/workspace-io/tests/test_render.py` | test | — | `lattice_workspace/tests/test_render.py` | exact (rebrand, marker string) |
| `packages/workspace-io/tests/test_warn_if_stale.py` | test | — | `lattice_workspace/tests/test_warn_if_stale.py` | role-match (v1-coercion test rewritten) |
| `packages/workspace-io/tests/test_pending_updates.py` | test | — | `lattice_workspace/tests/test_pending_updates.py` | exact (rebrand) |
| `packages/vault-io/src/vault_io/_workspace.py` | service | request-response | `lattice_workspace/config.py` + current `_workspace.py` | role-match (delegation rewrite) |
| `packages/vault-io/pyproject.toml` | config | — | current `packages/vault-io/pyproject.toml` | exact (add dep block) |
| `packages/vault-io/tests/test_ports_importable.py` | test | — | current `test_ports_importable.py` | exact (env-var rename + new test) |
| `packages/vault-io/tests/conftest.py` | test | — | current `conftest.py` | exact (one-line rename) |
| `agents/graph-wiki-agent/src/graph_wiki_agent/commands/init.py` | service | request-response | current `commands/init.py` | exact (prepend workspace_io.init call) |
| `agents/graph-wiki-agent/src/graph_wiki_mcp/server.py` | service | request-response | current `server.py` | exact (Field description strings only) |
| `agents/graph-wiki-agent/src/graph_wiki_agent/cli.py` | utility | — | current `cli.py` | exact (help string + init command) |

---

## Pattern Assignments

### `packages/workspace-io/pyproject.toml` (config)

**Primary analog:** `/Users/pat/Personal/lattice/packages/lattice-workspace/pyproject.toml`
**Secondary analog:** `/Users/pat/Personal/agent-research/packages/vault-io/pyproject.toml` (for `addopts = "--import-mode=importlib"`)

**Build backend choice:** Use hatchling (matches lattice source; asset inclusion is automatic when `assets/` sits inside `src/workspace_io/`).

**Complete template** (lattice source lines 1-20 + vault-io line 16-17 merged):
```toml
[project]
name = "workspace-io"
version = "0.1.0"
description = "Workspace bootstrap, manifest IO, and config resolution for the graph-wiki ecosystem."
requires-python = ">=3.11"
dependencies = ["pyyaml>=6.0"]

[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"

[tool.hatch.build.targets.wheel]
packages = ["src/workspace_io"]

[tool.pytest.ini_options]
testpaths = ["tests"]
addopts = "--import-mode=importlib"
```

**Key difference from existing agent-research packages:** All existing packages use `uv_build` backend. workspace-io uses `hatchling` because it ships the `assets/CLAUDE.md.template` inside the package and hatchling includes the `assets/` subdirectory automatically when listed in `packages = ["src/workspace_io"]`. No extra `package-data` or `include` block needed.

**After scaffold:** Add `workspace-io = { workspace = true }` under `[tool.uv.sources]` in vault-io and graph-wiki-agent pyproject files.

---

### `packages/workspace-io/src/workspace_io/__init__.py` (module)

**Analog:** `/Users/pat/Personal/lattice/packages/lattice-workspace/src/lattice_workspace/__init__.py` (lines 1-13)

**Source (13 lines total — copy then rebrand):**
```python
from lattice_workspace.config import LatticeConfig, resolve
from lattice_workspace.init import init
from lattice_workspace.versions import PendingUpdate, pending_updates, warn_if_stale

__all__ = [
    "LatticeConfig",
    "PendingUpdate",
    "init",
    "pending_updates",
    "resolve",
    "warn_if_stale",
]
```

**Rebrand changes:** `LatticeConfig` → `GraphWikiConfig`; import paths `lattice_workspace.*` → `workspace_io.*`.

---

### `packages/workspace-io/src/workspace_io/config.py` (service, request-response)

**Analog:** `/Users/pat/Personal/lattice/packages/lattice-workspace/src/lattice_workspace/config.py` (all 78 lines)

**Imports pattern** (lines 1-18):
```python
"""Workspace resolution: cwd -> GraphWikiConfig.

Discovery walks up from cwd looking for `.git`. Once the repo root is
found, `.graph-wiki.local.yaml` is consulted for the `graph-wiki-directory`
key. Falls back to `<repo>/graph-wiki` when the key is absent.

Environment variable `GRAPH_WIKI_WORKSPACE` overrides discovery and pins
a workspace directory directly.
"""
from __future__ import annotations

import os
import sys
from dataclasses import dataclass
from pathlib import Path

from workspace_io import _local_config
```

**Constants and dataclass** (source lines 20-29):
```python
LOCAL_CONFIG_FILENAME = ".graph-wiki.local.yaml"
LATTICE_DIRECTORY_KEY = "graph-wiki-directory"
DEFAULT_WORKSPACE_NAME = "graph-wiki"


@dataclass(frozen=True)
class GraphWikiConfig:
    workspace: Path
    repo_root: Path
```

**Core resolution helpers** (source lines 31-47):
```python
def _find_repo_root(start: Path) -> Path | None:
    start = Path(start).resolve()
    for candidate in (start, *start.parents):
        if (candidate / ".git").exists():
            return candidate
    return None


def _resolve_workspace(repo_root: Path) -> Path:
    local = _local_config.read(repo_root / LOCAL_CONFIG_FILENAME)
    raw = local.get(LATTICE_DIRECTORY_KEY, "").strip()
    if not raw:
        return (repo_root / DEFAULT_WORKSPACE_NAME).resolve()
    expanded = Path(raw).expanduser()
    if expanded.is_absolute():
        return expanded.resolve()
    return (repo_root / expanded).resolve()
```

**`resolve()` function — POST-PORT shape** (source lines 50-68, plus D-03 strict check added):
```python
def resolve(cwd: Path | None = None) -> GraphWikiConfig:
    env_workspace = os.environ.get("GRAPH_WIKI_WORKSPACE", "").strip()
    if env_workspace:
        workspace = Path(env_workspace).expanduser().resolve()
        repo_root = _find_repo_root(workspace) or workspace.parent.resolve()
        return GraphWikiConfig(workspace=workspace, repo_root=repo_root)
    # Normal discovery path
    cwd = Path(cwd) if cwd is not None else Path.cwd()
    repo_root = _find_repo_root(cwd) or cwd.resolve()
    workspace = _resolve_workspace(repo_root)
    # D-03: strict — raise if no .graph-wiki.yaml present
    manifest = workspace / ".graph-wiki.yaml"
    if not manifest.exists():
        raise RuntimeError(
            f"No .graph-wiki.yaml found in {workspace}. "
            f"Run: graph-wiki-agent init <path>"
        )
    return GraphWikiConfig(workspace=workspace, repo_root=repo_root)
```

**CRITICAL BEHAVIORAL DIVERGENCE:** Lattice's `resolve()` returns even without a manifest. The ported version raises. This is the single most important code change in the entire phase. The strict check lives at the end of the env-bypass-else path only — env override still returns without checking manifest (allows `GRAPH_WIKI_WORKSPACE` to work even before manifest is written, which the test suite requires).

**`_main()` and `__name__` guard** (source lines 71-77) — port verbatim; update module path in `subprocess.run` test.

---

### `packages/workspace-io/src/workspace_io/manifest.py` (service, file-I/O)

**Analog:** `/Users/pat/Personal/lattice/packages/lattice-workspace/src/lattice_workspace/manifest.py` (65 lines)

**Imports pattern** (lines 1-6):
```python
"""Read/write `.graph-wiki.yaml`. v2 only — raises on v1 format."""
from __future__ import annotations

from pathlib import Path

import yaml
```

**`read()` — POST-PORT shape** (drop `_coerce()` entirely; add v1 guard per D-14):
```python
def read(path: Path) -> dict:
    """Read `.graph-wiki.yaml`. Returns v2 dict; does NOT rewrite disk.
    Raises RuntimeError on v1 format (version < 2).
    """
    if not path.exists():
        return {}
    raw = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    if raw.get("version", 1) < 2:
        raise RuntimeError(
            f"{path}: manifest version {raw.get('version', 1)} is not supported. "
            "Edit the file and set version: 2 (see README for schema)."
        )
    # PyYAML parses bare dates as datetime.date; normalize to str.
    if "initialized_at" in raw:
        raw["initialized_at"] = str(raw["initialized_at"])
    return raw
```

**`write()` function** (source lines 46-64 — port verbatim; only YAML filename in comments changes):
```python
def write(path: Path, data: dict) -> None:
    """Write v2 manifest. Creates parent dirs."""
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "version": 2,
        "initialized_at": str(data.get("initialized_at", "") or ""),
        "plugins": [
            {
                "name": p["name"],
                "installed_version": p.get("installed_version"),
                "applied_version": p.get("applied_version"),
            }
            for p in data.get("plugins", [])
        ],
    }
    path.write_text(
        yaml.safe_dump(payload, sort_keys=False, default_flow_style=False),
        encoding="utf-8",
    )
```

**Key serialization notes:** `yaml.safe_load(...) or {}` handles empty/whitespace-only files. `sort_keys=False` preserves key order `version < initialized_at < plugins`. `default_flow_style=False` ensures block style (no inline `{}`).

---

### `packages/workspace-io/src/workspace_io/init.py` (service, file-I/O)

**Analog:** `/Users/pat/Personal/lattice/packages/lattice-workspace/src/lattice_workspace/init.py` (104 lines)

**Imports pattern** (source lines 1-19 — drop `write_schema` import per D-06):
```python
"""Idempotent workspace bootstrapping.

Creates the workspace directory (default `<repo_root>/graph-wiki`, override
via `workspace=`), writes `.graph-wiki.yaml`, ensures `.graph-wiki.local.yaml`
is gitignored. If the workspace is outside any git repo, runs `git init`
before writing the manifest.
"""
from __future__ import annotations

import datetime
import subprocess
from pathlib import Path

from workspace_io import manifest
from workspace_io import paths as _paths
from workspace_io.render import render_workspace_claude_md

_GITIGNORE_ENTRY = ".graph-wiki.local.yaml"
```

**`init()` function** (source lines 22-71 — remove `write_schema` call at line 69; update default workspace name):
```python
def init(
    repo_root: Path,
    *,
    plugin: str,
    version: str,
    workspace: Path | None = None,
) -> None:
    """Create the workspace and `.graph-wiki.yaml` if absent. Append/update plugin entry. Idempotent."""
    repo_root = Path(repo_root).resolve()
    if workspace is None:
        workspace = repo_root / "graph-wiki"
    workspace = Path(workspace).resolve()

    workspace.mkdir(parents=True, exist_ok=True)

    if not _is_inside_git_repo(workspace):
        _git_init(workspace)

    mpath = _paths.manifest_path(workspace)
    if mpath.exists():
        data = manifest.read(mpath)
    else:
        data = {
            "version": 2,
            "initialized_at": datetime.date.today().isoformat(),
            "plugins": [],
        }

    entry = next((p for p in data["plugins"] if p["name"] == plugin), None)
    if entry is None:
        data["plugins"].append(
            {"name": plugin, "installed_version": version, "applied_version": version}
        )
        changed = True
    else:
        changed = (
            entry.get("installed_version") != version
            or entry.get("applied_version") != version
        )
        entry["installed_version"] = version
        entry["applied_version"] = version

    if changed or not mpath.exists():
        manifest.write(mpath, data)

    render_workspace_claude_md(workspace)
    # NOTE: write_schema() call removed (D-06 — schema.py not ported)
    _ensure_gitignore_entry(repo_root)
```

**Private helpers** (source lines 73-103 — port verbatim; only `.lattice.local.yaml` string in `_ensure_gitignore_entry` changes to `.graph-wiki.local.yaml` via `_GITIGNORE_ENTRY`):
```python
def _is_inside_git_repo(path: Path) -> bool:
    for candidate in (path, *path.parents):
        if (candidate / ".git").exists():
            return True
    return False


def _git_init(path: Path) -> None:
    result = subprocess.run(
        ["git", "init", "-q", str(path)],
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        raise RuntimeError(f"git init failed at {path}: {result.stderr.strip()}")


def _ensure_gitignore_entry(repo_root: Path) -> None:
    gitignore = repo_root / ".gitignore"
    if gitignore.exists():
        text = gitignore.read_text(encoding="utf-8")
        existing_lines = {line.strip() for line in text.splitlines()}
        if _GITIGNORE_ENTRY in existing_lines:
            return
        sep = "" if text.endswith("\n") or text == "" else "\n"
        gitignore.write_text(text + sep + _GITIGNORE_ENTRY + "\n", encoding="utf-8")
    else:
        gitignore.write_text(_GITIGNORE_ENTRY + "\n", encoding="utf-8")
```

---

### `packages/workspace-io/src/workspace_io/paths.py` (utility)

**Analog:** `/Users/pat/Personal/lattice/packages/lattice-workspace/src/lattice_workspace/paths.py` (all 32 lines)

**Port verbatim** — only one string changes: `manifest_path` returns `.graph-wiki.yaml` not `.lattice.yaml`:
```python
"""Pure path accessors over a resolved workspace path."""
from __future__ import annotations
from pathlib import Path


def manifest_path(workspace: Path) -> Path:
    return Path(workspace) / ".graph-wiki.yaml"   # only change from source


def wiki_dir(workspace: Path) -> Path:
    return Path(workspace) / "wiki"


def raw_dir(workspace: Path) -> Path:
    return Path(workspace) / "raw"


def work_dir(workspace: Path) -> Path:
    return Path(workspace) / "work"


def knowledge_dir(workspace: Path) -> Path:
    return Path(workspace) / "knowledge"


def graph_dir(workspace: Path) -> Path:
    return Path(workspace) / ".graph"
```

---

### `packages/workspace-io/src/workspace_io/render.py` (service, file-I/O)

**Analog:** `/Users/pat/Personal/lattice/packages/lattice-workspace/src/lattice_workspace/render.py` (all 118 lines)

**Imports and constants** (source lines 1-41 — marker strings renamed, plugin pointers dict rebranded):
```python
"""Render the workspace-level CLAUDE.md from a template + manifest."""
from __future__ import annotations

import re
from pathlib import Path

from workspace_io import manifest
from workspace_io.paths import manifest_path

AUTO_START = "<!-- workspace-io:auto:plugins:start -->"
AUTO_END = "<!-- workspace-io:auto:plugins:end -->"

_BLOCK_RE = re.compile(re.escape(AUTO_START) + r".*?" + re.escape(AUTO_END), re.DOTALL)

_TEMPLATE_PATH = Path(__file__).resolve().parent / "assets" / "CLAUDE.md.template"

_PLUGIN_POINTERS: dict[str, str] = {
    "graph-wiki-agent": "see wiki/CLAUDE.md",
}
```

**Key changes vs source:**
- `AUTO_START/END`: `lattice-workspace:auto` → `workspace-io:auto` (must match the template)
- `_TEMPLATE_PATH`: same pattern (`Path(__file__).resolve().parent / "assets" / "CLAUDE.md.template"`) — works identically in editable and wheel installs
- `_PLUGIN_POINTERS`: drop all `lattice-*` entries; add one `"graph-wiki-agent"` entry

**All helper functions** (`_render_plugin_list`, `_render_full_template`, `_refresh_auto_block`, `render_workspace_claude_md`) — port verbatim from source lines 44-117. No logic changes; only the import paths and the constants above differ.

---

### `packages/workspace-io/src/workspace_io/versions.py` (service, file-I/O)

**Analog:** `/Users/pat/Personal/lattice/packages/lattice-workspace/src/lattice_workspace/versions.py` (all 62 lines)

**Port verbatim** — only import paths change:
```python
"""Per-plugin version comparison helpers."""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import workspace_io.manifest as manifest
from workspace_io.paths import manifest_path
```

All three exported symbols (`PendingUpdate`, `warn_if_stale`, `pending_updates`) — copy source lines 11-61 unchanged.

---

### `packages/workspace-io/src/workspace_io/_local_config.py` (utility, file-I/O)

**Analog:** `/Users/pat/Personal/lattice/packages/lattice-workspace/src/lattice_workspace/_local_config.py` (all 49 lines)

**Port verbatim** — only the module docstring comment changes (`.lattice.local.yaml` → `.graph-wiki.local.yaml`). The parser logic is deliberately PyYAML-free and handles inline comments, quote stripping, blank lines, and malformed lines.

```python
"""Minimal line-by-line parser for .graph-wiki.local.yaml.

No PyYAML dependency. Same style as manifest.py — recognizes flat
`key: value` pairs at the top level. Skips blanks, comments, and
malformed lines silently.
"""
from __future__ import annotations

from pathlib import Path


def read(path: Path) -> dict[str, str]:
    """Read .graph-wiki.local.yaml. Returns dict of all top-level key:value pairs.
    ...
    """
```

**Critical:** Do NOT refactor to use `yaml.safe_load` even though `pyyaml` is now a package dep.

---

### `packages/workspace-io/src/workspace_io/assets/CLAUDE.md.template` (config)

**Analog:** `/Users/pat/Personal/lattice/packages/lattice-workspace/src/lattice_workspace/assets/CLAUDE.md.template` (all 30 lines)

**Port with prose rebrand** — structure and `{{PLACEHOLDER}}` tokens are identical; only human-readable content changes:

| Source string | Target string |
|---|---|
| `# Lattice Workspace` | `# Graph-Wiki Workspace` |
| `lattice-wiki` references | `graph-wiki-agent` |
| `.lattice.yaml` | `.graph-wiki.yaml` |
| `.lattice.local.yaml` | `.graph-wiki.local.yaml` |
| `lattice-directory:` | `graph-wiki-directory:` |
| `<!-- lattice-workspace:auto:plugins:start -->` | `<!-- workspace-io:auto:plugins:start -->` |
| `<!-- lattice-workspace:auto:plugins:end -->` | `<!-- workspace-io:auto:plugins:end -->` |

**Critical:** The auto-block marker strings in the template MUST exactly match `AUTO_START`/`AUTO_END` in `render.py`. If they diverge, every re-render appends a fresh block instead of refreshing the existing one.

---

## Test Pattern Assignments

### General test fixture pattern (all workspace-io tests)

**Analog:** `/Users/pat/Personal/lattice/packages/lattice-workspace/tests/test_config.py` lines 1-18

```python
# Standard fixture setup used across all test files:
from pathlib import Path
from workspace_io.config import GraphWikiConfig, resolve  # (module-specific imports)

def _make_repo(root: Path) -> Path:
    (root / ".git").mkdir(parents=True)
    return root
```

All tests use `tmp_path` (pytest built-in). No `conftest.py` needed for workspace-io tests — lattice tests had none either.

---

### `packages/workspace-io/tests/test_config.py` (test)

**Analog:** `/Users/pat/Personal/lattice/packages/lattice-workspace/tests/test_config.py` (all 89 lines)

**Rebrand changes:**
- Import: `from workspace_io.config import GraphWikiConfig, resolve`
- `(repo / "lattice").resolve()` → `(repo / "graph-wiki").resolve()`
- `".lattice.local.yaml"` → `".graph-wiki.local.yaml"`
- `"lattice-directory:"` → `"graph-wiki-directory:"`
- `monkeypatch.setattr("lattice_workspace.config._find_repo_root", ...)` → `"workspace_io.config._find_repo_root"`
- `[sys.executable, "-m", "lattice_workspace.config"]` → `[sys.executable, "-m", "workspace_io.config"]`

**New test required** (not in lattice, per D-03):
```python
def test_resolve_raises_when_no_manifest_found(tmp_path, monkeypatch):
    """Without GRAPH_WIKI_WORKSPACE env and without .graph-wiki.yaml, resolve() raises RuntimeError."""
    monkeypatch.delenv("GRAPH_WIKI_WORKSPACE", raising=False)
    repo = _make_repo(tmp_path)
    with pytest.raises(RuntimeError, match="graph-wiki-agent init"):
        resolve(repo)
```

---

### `packages/workspace-io/tests/test_manifest.py` (test)

**Analog:** `/Users/pat/Personal/lattice/packages/lattice-workspace/tests/test_manifest.py` (all 49 lines)

**Rebrand changes:** All `".lattice.yaml"` path strings → `".graph-wiki.yaml"`.

**New test for D-14 behavior** (replaces the dropped `test_manifest_v1_read.py`):
```python
def test_read_raises_on_v1(tmp_path):
    mpath = tmp_path / ".graph-wiki.yaml"
    mpath.write_text("version: 1\ninitialized_at: 2026-05-17\nplugins:\n  - graph-wiki-agent\n")
    with pytest.raises(RuntimeError):
        read(mpath)
```

---

### `packages/workspace-io/tests/test_init.py` (test)

**Analog:** `/Users/pat/Personal/lattice/packages/lattice-workspace/tests/test_init.py` (all 136 lines)

**Rebrand changes:**
- `from workspace_io.init import init`
- All `tmp_path / "lattice"` → `tmp_path / "graph-wiki"`
- `".lattice.local.yaml"` → `".graph-wiki.local.yaml"`
- Plugin name args `"lattice-wiki"` → `"graph-wiki-agent"`; `"lattice-work"` → `"code-wiki-second"` (or any name)
- `"<!-- lattice-workspace:auto:plugins:start -->"` → `"<!-- workspace-io:auto:plugins:start -->"`

**Drop:** `test_creates_work_schema` (line 48-50) — `write_schema` call removed per D-06.

**Gitignore assertion pattern** (source line 88-92 — key lines):
```python
def test_appends_local_yaml_to_gitignore(tmp_path):
    repo = tmp_path
    init(repo, plugin="graph-wiki-agent", version="1.0.0")
    text = (repo / ".gitignore").read_text()
    assert ".graph-wiki.local.yaml" in text
```

---

### `packages/workspace-io/tests/test_render.py` (test)

**Analog:** `/Users/pat/Personal/lattice/packages/lattice-workspace/tests/test_render.py` (all 89 lines)

**Key fixture helper — rebrand the manifest writer:**
```python
def _write_manifest(workspace: Path, plugins: list[str]) -> None:
    workspace.mkdir(parents=True, exist_ok=True)
    body = "version: 2\ninitialized_at: 2026-05-09\nplugins:\n"
    for p in plugins:
        body += (
            f"  - name: {p}\n"
            f"    installed_version: null\n"
            f"    applied_version: null\n"
        )
    (workspace / ".graph-wiki.yaml").write_text(body, encoding="utf-8")
```

**Rebrand changes:**
- `from workspace_io.render import AUTO_END, AUTO_START, render_workspace_claude_md`
- `AUTO_START` / `AUTO_END` constants now equal `workspace-io:auto:*` strings (imported from module, not hardcoded in tests)
- All `".lattice.yaml"` → `".graph-wiki.yaml"`

---

### `packages/workspace-io/tests/test_warn_if_stale.py` (test — behavioral change)

**Analog:** `/Users/pat/Personal/lattice/packages/lattice-workspace/tests/test_warn_if_stale.py` (all 48 lines)

**Rebrand changes:** workspace paths `tmp_path / "lattice"` → `tmp_path / "graph-wiki"`; plugin names.

**Behavioral rewrite required for `test_v1_coerced_entry_no_signal`** (source lines 36-47):

The original test writes a v1-format manifest and expects `warn_if_stale` to return False. After D-14, `manifest.read()` raises on v1 format. Rewrite to simulate the same logical state using a v2 manifest with `applied_version: null`:
```python
def test_null_applied_version_no_signal(tmp_path):
    """An entry whose applied_version is null returns False, no write."""
    workspace = tmp_path / "graph-wiki"
    workspace.mkdir(parents=True)
    mpath = workspace / ".graph-wiki.yaml"
    mpath.write_text(
        "version: 2\ninitialized_at: 2026-05-17\nplugins:\n"
        "  - name: graph-wiki-agent\n    installed_version: null\n    applied_version: null\n",
        encoding="utf-8",
    )
    before = mpath.read_bytes()
    assert warn_if_stale(workspace, plugin="graph-wiki-agent", version="0.7.0") is False
    assert mpath.read_bytes() == before
```

---

### `packages/workspace-io/tests/test_local_config.py` (test)

**Analog:** `/Users/pat/Personal/lattice/packages/lattice-workspace/tests/test_local_config.py` (all 57 lines)

**Rebrand changes only:** Replace `".lattice.local.yaml"` with `".graph-wiki.local.yaml"` in all fixture writes; replace `"lattice-directory:"` with `"graph-wiki-directory:"` in content. Import: `from workspace_io._local_config import read`.

---

## Modified File Pattern Assignments

### `packages/vault-io/src/vault_io/_workspace.py` (service, request-response — full rewrite)

**Current analog:** `/Users/pat/Personal/agent-research/packages/vault-io/src/vault_io/_workspace.py` (34 lines)
**Post-port shape from:** RESEARCH.md §Code Examples and current source

**Complete post-port file:**
```python
"""Workspace path resolution for vault-io.

Thin delegation shim. Resolution priority:
1. vault_path argument — short-circuit (MCP boundary contract, Phase 11 SC#3)
2. workspace_io.config.resolve() — GRAPH_WIKI_WORKSPACE env or .graph-wiki.yaml walk-up
3. RuntimeError from workspace_io (names graph-wiki-agent init as bootstrap command)
"""
from __future__ import annotations

from pathlib import Path

from workspace_io import config as _ws_config
from workspace_io import paths as _ws_paths
from workspace_io.config import _find_repo_root


def resolve_wiki_and_repo(
    vault_path: Path | None = None,
) -> tuple[Path, Path | None]:
    """Return (wiki_path, repo_root).

    Priority:
    1. ``vault_path`` argument if provided — short-circuit
    2. ``GRAPH_WIKI_WORKSPACE`` env var (via workspace_io.config.resolve)
    3. ``.graph-wiki.yaml`` walk-up from cwd (via workspace_io.config.resolve)
    4. Raises RuntimeError — names ``graph-wiki-agent init <path>`` as fix
    """
    if vault_path is not None:
        return vault_path.resolve(), _find_repo_root(vault_path)
    cfg = _ws_config.resolve()
    return _ws_paths.wiki_dir(cfg.workspace), cfg.repo_root
```

**Signature is bit-identical** to current: `resolve_wiki_and_repo(vault_path: Path | None = None) -> tuple[Path, Path | None]`. All 9 vault-io call sites (`wiki, _ = resolve_wiki_and_repo()`) are unaffected.

---

### `packages/vault-io/pyproject.toml` (config — add dep)

**Analog:** Current `/Users/pat/Personal/agent-research/packages/vault-io/pyproject.toml` (18 lines)

**Two additions** — add to `[project] dependencies` and add `[tool.uv.sources]` section:
```toml
[project]
dependencies = [
    "python-frontmatter>=1.1",
    "boto3>=1.38",
    "workspace-io",           # ADD
]

[tool.uv.sources]
workspace-io = { workspace = true }   # ADD entire section
```

---

### `packages/vault-io/tests/test_ports_importable.py` (test — targeted updates)

**Analog:** Current `/Users/pat/Personal/agent-research/packages/vault-io/tests/test_ports_importable.py` (91 lines)

**`test_resolve_wiki_and_repo_raises_on_no_config`** (lines 67-78) — two changes:
- `monkeypatch.delenv("GRAPH_WIKI_REAL_VAULT_PATH", raising=False)` → `monkeypatch.delenv("GRAPH_WIKI_WORKSPACE", raising=False)`
- Error string assertion: `assert "GRAPH_WIKI_REAL_VAULT_PATH" in str(exc)` → `assert "graph-wiki-agent init" in str(exc)`

**`test_resolve_wiki_and_repo_honors_env_var`** (lines 81-91) — pitfall-aware rewrite (RESEARCH.md §Pitfall 1):
```python
def test_resolve_wiki_and_repo_honors_env_var(monkeypatch, tmp_path: Path):
    """Env var alone is sufficient to resolve the wiki path."""
    from vault_io._workspace import resolve_wiki_and_repo

    fake_workspace = tmp_path / "workspace"
    fake_workspace.mkdir()
    # workspace_io.config.resolve() with env set reads the workspace dir,
    # then paths.wiki_dir() returns workspace/"wiki". No manifest needed
    # because the env-override path skips the strict manifest check.
    monkeypatch.setenv("GRAPH_WIKI_WORKSPACE", str(fake_workspace))

    wiki, repo = resolve_wiki_and_repo()
    assert wiki == (fake_workspace / "wiki").resolve()
    # repo_root is discovered via _find_repo_root; may be None or a real path
```

**New test to add:**
```python
def test_resolve_wiki_and_repo_strict_raises_without_manifest(monkeypatch, tmp_path: Path):
    """Without env var and without .graph-wiki.yaml, raises RuntimeError naming init command."""
    from vault_io._workspace import resolve_wiki_and_repo

    monkeypatch.delenv("GRAPH_WIKI_WORKSPACE", raising=False)
    monkeypatch.chdir(tmp_path)
    # Ensure no .git ancestor to avoid hitting a real workspace
    monkeypatch.setattr("workspace_io.config._find_repo_root", lambda _: None)

    try:
        resolve_wiki_and_repo()
    except RuntimeError as exc:
        assert "graph-wiki-agent init" in str(exc)
        return
    raise AssertionError("did not raise RuntimeError")
```

---

### `packages/vault-io/tests/conftest.py` (test — one-line update)

**Analog:** Current `/Users/pat/Personal/agent-research/packages/vault-io/tests/conftest.py` (38 lines)

**Single change** (line 35):
```python
# Before:
override = os.environ.get("GRAPH_WIKI_REAL_VAULT_PATH")
# After:
override = os.environ.get("GRAPH_WIKI_WORKSPACE")
```

---

### `agents/graph-wiki-agent/src/graph_wiki_agent/commands/init.py` (service — prepend workspace_io call)

**Analog:** Current `/Users/pat/Personal/agent-research/agents/graph-wiki-agent/src/graph_wiki_agent/commands/init.py` (86 lines)

**Changes:**

1. Add import at top:
```python
import importlib.metadata
from workspace_io import init as _ws_init
```

2. Update docstring for `vault_path` arg (line 52):
```python
        vault_path: Explicit vault path; if None, reads GRAPH_WIKI_WORKSPACE env var.
```

3. Prepend workspace bootstrap to `run_init()` before the existing `resolve_wiki_and_repo` call (after line 60):
```python
async def run_init(
    topic: str,
    tool: str,
    force: bool,
    vault_path: Path | None = None,
) -> InitResult:
    # Phase 11: two-phase init — workspace bootstrap first, then wiki tree
    # Determine repo_root: if vault_path explicit, use its parent; else use cwd
    repo_root = vault_path.parent if vault_path is not None else Path.cwd()
    _ws_init(
        repo_root,
        plugin="graph-wiki-agent",
        version=importlib.metadata.version("graph-wiki-agent"),
    )
    # Existing resolution logic (unchanged — vault_path short-circuits to skip workspace_io)
    wiki, repo = resolve_wiki_and_repo(vault_path)
    ...
```

**The existing `resolve_wiki_and_repo(vault_path)` call and all downstream code stays unchanged.**

---

### `agents/graph-wiki-agent/src/graph_wiki_mcp/server.py` (service — Field description strings)

**Analog:** Current `server.py` — 5 occurrences of `GRAPH_WIKI_REAL_VAULT_PATH` in `Field(description=...)` and tool `description=` strings (lines 105, 121, 154, 196, 243, 309, 328, 375 per grep).

**Pattern for each occurrence:**
```python
# Before:
vault_path: str = Field("", description="Vault path (default: GRAPH_WIKI_REAL_VAULT_PATH env var)")
# After:
vault_path: str = Field("", description="Vault path (default: GRAPH_WIKI_WORKSPACE env var)")

# Before (tool description string):
"vault_path defaults to GRAPH_WIKI_REAL_VAULT_PATH env var."
# After:
"vault_path defaults to GRAPH_WIKI_WORKSPACE env var."

# Before (inline comment):
vault_path: str = ""  # empty -> resolve from GRAPH_WIKI_REAL_VAULT_PATH env var
# After:
vault_path: str = ""  # empty -> resolve from GRAPH_WIKI_WORKSPACE env var
```

**Apply the same rename to all 8 grep hits** — these are user-visible MCP tool schema descriptions, not just comments.

---

### `agents/graph-wiki-agent/src/graph_wiki_agent/cli.py` (utility — help strings)

**Analog:** Current `cli.py` lines 433 and 455 (and equivalent in all other `@app.command()` blocks).

**Pattern:**
```python
# Before:
vault: str = typer.Option("", "--vault", help="Vault path (default: GRAPH_WIKI_REAL_VAULT_PATH env var)"),
# After:
vault: str = typer.Option("", "--vault", help="Vault path (default: GRAPH_WIKI_WORKSPACE env var)"),
```

Apply to all `@app.command()` definitions that have the `--vault` option (grep shows 6 occurrences).

---

### Docstring-only changes (8 vault-io modules + config.py)

**Analog:** Current files with `GRAPH_WIKI_REAL_VAULT_PATH` in module-level docstrings.

**Pattern** (same in every file):
```python
# Before: module docstring mentions GRAPH_WIKI_REAL_VAULT_PATH
"""
Requires GRAPH_WIKI_REAL_VAULT_PATH env var ...
"""
# After:
"""
Requires GRAPH_WIKI_WORKSPACE env var ...
"""
```

Files to update (docstring only, no logic change):
- `packages/vault-io/src/vault_io/append_log.py:9`
- `packages/vault-io/src/vault_io/detect_containers.py:6`
- `packages/vault-io/src/vault_io/graph_analyzer.py:5-6`
- `agents/graph-wiki-agent/src/graph_wiki_agent/commands/log.py:48`
- `agents/graph-wiki-agent/src/graph_wiki_agent/commands/init.py:52`
- `agents/graph-wiki-agent/src/graph_wiki_agent/commands/query.py:788`
- `agents/graph-wiki-agent/src/graph_wiki_agent/config.py:38`

---

### `agents/graph-wiki-agent/pyproject.toml` (config — add dep)

**Analog:** Current `agents/graph-wiki-agent/pyproject.toml` (34 lines)

**Two additions:**
```toml
[project]
dependencies = [
    "vault-io",
    "model-adapter",
    "subagent-runtime",
    "workspace-io",           # ADD
    ...
]

[tool.uv.sources]
vault-io         = { workspace = true }
model-adapter    = { workspace = true }
subagent-runtime = { workspace = true }
workspace-io     = { workspace = true }   # ADD
```

---

## Shared Patterns

### `from __future__ import annotations`
**Source:** Every existing module in `vault_io/` and `lattice_workspace/`
**Apply to:** All new `workspace_io/*.py` modules
```python
from __future__ import annotations
```
First line of every module (after the docstring if present, before other imports).

### PyYAML safe_load with `or {}` guard
**Source:** `lattice_workspace/manifest.py` line 38
**Apply to:** `workspace_io/manifest.py` `read()` function
```python
raw = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
```
Never `yaml.load()`. Always `yaml.safe_load(...) or {}` to handle whitespace-only files.

### Asset path resolution via `Path(__file__)`
**Source:** `lattice_workspace/render.py` line 31
**Apply to:** `workspace_io/render.py`
```python
_TEMPLATE_PATH = Path(__file__).resolve().parent / "assets" / "CLAUDE.md.template"
```
Works identically in editable installs and built wheels. No `importlib.resources`.

### Workspace member dependency pattern
**Source:** Current `agents/graph-wiki-agent/pyproject.toml` `[tool.uv.sources]` block
**Apply to:** vault-io and graph-wiki-agent pyproject files when adding workspace-io dep
```toml
[tool.uv.sources]
workspace-io = { workspace = true }
```

### `importlib.metadata.version()` for version introspection
**Source:** `agents/graph-wiki-agent/src/graph_wiki_agent/cli.py` line 51
**Apply to:** `agents/graph-wiki-agent/src/graph_wiki_agent/commands/init.py` (call site for workspace_io.init)
```python
import importlib.metadata
version=importlib.metadata.version("graph-wiki-agent")
```
Verified to return `"0.1.0"` under `uv run --package graph-wiki-agent` editable install.

---

## No Analog Found

No files in this phase lack a codebase analog. All files have direct source templates (lattice-workspace modules) or existing agent-research files to modify.

---

## Metadata

**Analog search scope:** `/Users/pat/Personal/lattice/packages/lattice-workspace/` (all source + tests), `/Users/pat/Personal/agent-research/packages/vault-io/`, `/Users/pat/Personal/agent-research/agents/graph-wiki-agent/`
**Files read:** 28 source/test/config files
**Pattern extraction date:** 2026-05-17
