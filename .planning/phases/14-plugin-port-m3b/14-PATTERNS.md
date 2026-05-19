# Phase 14: Plugin Port (M3b) — Pattern Map

**Mapped:** 2026-05-18
**Files analyzed:** ~30 new/modified artifacts across 3 plans
**Analogs found:** all categories matched — in-tree analog for every Python file, upstream-only analog for every plugin asset (intended — port surface)

## File Classification

### Plan 1 — `vault_io.lint_wiki` port

| New/Modified File | Role | Data Flow | Closest Analog | Match Quality |
|---|---|---|---|---|
| `packages/vault-io/src/vault_io/lint_wiki.py` | port (module) | batch / CLI | `/Users/pat/Personal/lattice/packages/lattice-wiki-core/src/lattice_wiki_core/lint_wiki.py` (upstream, verbatim source) **and** in-tree shape `packages/vault-io/src/vault_io/scan_monorepo.py` | exact (upstream) + role-match (in-tree shape) |
| `packages/vault-io/tests/test_lint_wiki.py` (new) | test | request-response | `packages/vault-io/tests/test_lint_modules.py` (already tests `vault_io.lint.*` siblings) | role-match |

### Plan 2 — `vault_io.wiki_search` port

| New/Modified File | Role | Data Flow | Closest Analog | Match Quality |
|---|---|---|---|---|
| `packages/vault-io/src/vault_io/wiki_search.py` | port (module) | batch / CLI | `/Users/pat/Personal/lattice/packages/lattice-wiki-core/src/lattice_wiki_core/wiki_search.py` (verbatim source) **and** in-tree shape `packages/vault-io/src/vault_io/graph_analyzer.py` | exact (upstream) + role-match (in-tree shape) |
| `packages/vault-io/tests/test_wiki_search.py` (new) | test | request-response | `packages/vault-io/tests/test_ports_importable.py` (smoke-import pattern) + `packages/vault-io/tests/test_lint_modules.py` (fixture-vault test pattern) | role-match |

### Plan 3 — Bundled plugin port

#### 3a. Manifest extension

| New/Modified File | Role | Data Flow | Closest Analog | Match Quality |
|---|---|---|---|---|
| `packages/workspace-io/src/workspace_io/manifest.py` (MODIFY) | config (manifest read/write) | request-response | self (existing strict-raises pattern at `raw.get("version", 1) < 2`) | exact (extend in-place) |
| `packages/workspace-io/tests/test_manifest.py` (MODIFY — add cases) | test | request-response | self (existing `test_read_raises_on_v1` / round-trip cases) | exact |

#### 3b. Plugin scaffold (copy + rebrand from upstream)

| New File | Role | Data Flow | Closest Analog | Match Quality |
|---|---|---|---|---|
| `plugins/graph-wiki/.claude-plugin/plugin.json` | config (plugin metadata) | static | `/Users/pat/Personal/lattice/plugins/lattice-wiki/.claude-plugin/plugin.json` | exact (rebrand + version reset per D-03) |
| `plugins/graph-wiki/CLAUDE.md` | docs (host-loaded guidance) | static | upstream `plugins/lattice-wiki/CLAUDE.md` | exact (brand-swap pass) |
| `plugins/graph-wiki/README.md` | docs | FRESH-WRITE | none in upstream — D-04 deliberately diverges; structural sibling is `packages/workspace-io/README.md` | role-match (deep-agents-repo readme tone) |
| `plugins/graph-wiki/commands/init.md` | docs (slash command body) | event-driven (Claude Code dispatch) | upstream `commands/init.md` | exact (rename per spec) |
| `plugins/graph-wiki/commands/scan.md` | docs | event-driven | upstream `commands/scan.md` | exact |
| `plugins/graph-wiki/commands/ingest.md` | docs | event-driven | upstream `commands/ingest.md` | exact |
| `plugins/graph-wiki/commands/lint.md` | docs | event-driven | upstream `commands/lint.md` | exact (reshape per spec) |
| `plugins/graph-wiki/commands/query.md` | docs | event-driven | upstream `commands/query.md` | exact |
| `plugins/graph-wiki/commands/log.md` | docs | event-driven | upstream `commands/log.md` | exact |
| `plugins/graph-wiki/agents/{ingestor,librarian,linter,scanner}.md` (4 files) | docs (sub-agent prose) | event-driven | upstream `agents/<same>.md` (4 files) | exact (file names stay; prose rebrand) |
| `plugins/graph-wiki/skills/graph-wiki/SKILL.md` | docs (skill index) | static | upstream `skills/lattice-wiki/SKILL.md` | exact (directory rename + brand swap) |
| `plugins/graph-wiki/skills/graph-wiki/README.md` | docs | static | upstream `skills/lattice-wiki/README.md` | exact |
| `plugins/graph-wiki/skills/graph-wiki/references/*.md` (12 files) | docs (reference docs) | static | upstream `skills/lattice-wiki/references/*.md` | exact (per file: `cross-tool-setup`, `detection-workflow`, `ingest-workflow`, `lifecycle-rules`, `lint-workflow`, `monorepo-principles`, `obsidian-setup`, `page-formats`, `query-workflow`, `scan-workflow`, `sidecar-schema`, `wiki-schema`) |

#### 3c. Plugin scripts (shim retarget + selector)

| New File | Role | Data Flow | Closest Analog | Match Quality |
|---|---|---|---|---|
| `plugins/graph-wiki/skills/graph-wiki/scripts/_config.py` | config (backend selector) | request-response | upstream `skills/lattice-wiki/scripts/_config.py` (shape) + `packages/workspace-io/src/workspace_io/manifest.py` (read API) | exact (upstream) + role-match (manifest reader) |
| `plugins/graph-wiki/skills/graph-wiki/scripts/init_vault.py` | shim | request-response | upstream `skills/lattice-wiki/scripts/init_vault.py` (canonical template per SO-02) + in-tree analog `packages/vault-io/src/vault_io/_workspace.py` (thin-delegation idiom) | exact |
| `plugins/graph-wiki/skills/graph-wiki/scripts/scan_monorepo.py` | shim | request-response | same as above (SO-02 retarget) | exact |
| `plugins/graph-wiki/skills/graph-wiki/scripts/ingest_source.py` | shim | request-response | same (SO-02 retarget) | exact |
| `plugins/graph-wiki/skills/graph-wiki/scripts/lint_wiki.py` | shim | request-response | same (SO-02 retarget) | exact |
| `plugins/graph-wiki/skills/graph-wiki/scripts/wiki_search.py` | shim | request-response | same (SO-02 retarget) | exact |
| `plugins/graph-wiki/skills/graph-wiki/scripts/detect_containers.py` | shim | request-response | same (SO-02 retarget) — invoked as pre-step from `init.md` per spec | exact |
| *(no `scripts/log.py`)* | — | — | — | per `log.md` spec: prose-only |
| *(no `scripts/lint_work.py`, `ingest_work_item.py`, `archive_work.py`, `regenerate_work_index.py`, `work_status.py`, `export_marp.py`)* | — | — | — | per C-01 / out-of-scope: work-layer dropped, marp dropped |

#### 3d. Verification artifact

| New File | Role | Data Flow | Closest Analog | Match Quality |
|---|---|---|---|---|
| `.planning/phases/14-plugin-port-m3b/14-VERIFICATION.md` | docs (audit transcript per D-05) | static | `.planning/phases/12-drift-backport-ecosystem-rebrand-m2/12-VERIFICATION.md` (Phase 12 verification log pattern) | role-match |

---

## Pattern Assignments

### `packages/vault-io/src/vault_io/lint_wiki.py` (port, batch / CLI)

**Primary analog (verbatim port source):** `/Users/pat/Personal/lattice/packages/lattice-wiki-core/src/lattice_wiki_core/lint_wiki.py`
**In-tree shape analog:** `packages/vault-io/src/vault_io/scan_monorepo.py` and the existing `packages/vault-io/src/vault_io/lint/*` modules

**Module-docstring + import-block pattern** (mirror in-tree shape, lines 1–40 of `scan_monorepo.py`):

```python
#!/usr/bin/env python3
"""
lint_wiki.py — Health-check a Code Wiki.

Mechanical checks:
  - orphans, broken wikilinks, stale pages, missing frontmatter
  - duplicate titles, log gaps
  - code-drift (monorepo-specific): packages on disk vs. in the vault

Discovers wiki and repo locations from the resolved graph-wiki workspace.

This file is a thin dispatcher. Per-group checks live under ``lint/``:
``container``, ``file_map``, ``domain``, ``source_sync``, ``package_sync``.
Each module exposes a ``check(...)`` entry point and a ``GROUP`` constant.

Usage:
    python lint_wiki.py
    python lint_wiki.py --stale-days 60 --json
"""

from __future__ import annotations

import argparse
import datetime as dt
import json
import sys
from collections import defaultdict
from pathlib import Path
```

**Brand-rename rules applied during port (BRAND-04 / VP-03; mirrors what `_workspace.py` already shows):**

```python
# Upstream                                          # Ported
from lattice_wiki_core.scan_monorepo import ...  →  from vault_io.scan_monorepo import ...
from lattice_wiki_core._workspace import ...     →  from vault_io._workspace import ...
from lattice_wiki_core.lint.container import ... →  from vault_io.lint.container import ...
# Drop the upstream _version_check import — not present in vault_io and not in scope.
from lattice_wiki_core._version_check import check_for_updates  →  (deleted)
```

**No provenance comments needed.** Phase 11/12 did **not** establish `# Source: / # Anchor: / # Source-commit:` headers in tree (confirmed: zero such headers exist in `packages/vault-io/`). Match the existing in-tree pattern — clean module docstring, plain imports — not a documented header convention.

**Existing in-tree env-var convention (mirror this in any new error strings):** `packages/vault-io/src/vault_io/_workspace.py` lines 7–11 use `GRAPH_WIKI_WORKSPACE` and reference `code-wiki-agent init <path>` as the fix command. Any new error messages in `lint_wiki.py` follow that exact phrasing.

**Behavior preservation rubric (Phase 12 SR-01, restated for VP-01):** Bug fixes, helper extractions, behavior-preserving refactors come over verbatim. `main()` entry point shape, CLI argparse surface, and `scan(...)` return shape match upstream byte-for-byte modulo brand strings.

---

### `packages/vault-io/src/vault_io/wiki_search.py` (port, batch / CLI)

**Primary analog (verbatim port source):** `/Users/pat/Personal/lattice/packages/lattice-wiki-core/src/lattice_wiki_core/wiki_search.py`
**In-tree shape analog:** `packages/vault-io/src/vault_io/graph_analyzer.py` (only-stdlib + argparse + JSON-output module)

**Module-docstring pattern (from upstream, lines 1–10) — apply brand rename:**

```python
#!/usr/bin/env python3
"""
wiki_search.py — BM25 search over a Code Wiki. Standard library only.

Discovers wiki location from the resolved graph-wiki workspace.

Usage:
    python wiki_search.py --query "middleware pipeline"
    python wiki_search.py --query "global context" --limit 5 --json
"""
```

**Import rewrites (same rules as lint_wiki):**

```python
from lattice_wiki_core._workspace import resolve_wiki_and_repo  →  from vault_io._workspace import resolve_wiki_and_repo
from lattice_wiki_core._version_check import check_for_updates  →  (deleted — not in vault_io scope)
```

**Same `main()` + CLI + brand-rename rubric as Plan 1.**

---

### `packages/vault-io/tests/test_lint_wiki.py` and `tests/test_wiki_search.py` (test)

**Analog (importability + smoke pattern):** `packages/vault-io/tests/test_ports_importable.py` lines 1–40

```python
"""VAULT-07 surface check: every ported module imports cleanly."""

from __future__ import annotations

from pathlib import Path


def test_all_ports_importable():
    from vault_io.lint_wiki import main, scan  # noqa: F401
    # …
    assert callable(scan)
```

**Analog (fixture-vault structural pattern):** `packages/vault-io/tests/test_lint_modules.py` lines 16–40 — use `FIXTURES = Path(__file__).parent / "fixtures"` and the existing `edge-case-vault` / `round-trip-vault` directories already present under `packages/vault-io/tests/fixtures/`.

**Scope per Phase 14 (VP-02 rubric, mirrors Phase 12 SR-01):** importability + structural smoke is enough; finding-count parity with upstream is **not** in scope (matches the `test_lint_modules.py` opener: "Finding-count parity with lattice-wiki-core is a plan-05-06 concern — this file only asserts structural correctness").

---

### `packages/workspace-io/src/workspace_io/manifest.py` (MODIFY — config)

**Self-analog (existing strict-raises pattern at lines 14–22):**

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
```

**Extension shape (per CONTEXT.md §D-02; carries the same idiom forward):**

```python
# After existing version + initialized_at normalization, before return raw:

_KNOWN_PLUGIN_KEYS = {"backend_default", "backend_overrides"}
_VALID_BACKENDS = {"claude", "bedrock"}

plugin = raw.get("plugin")
if plugin is None:
    raw["plugin"] = {"backend_default": "claude", "backend_overrides": {}}
else:
    if not isinstance(plugin, dict):
        raise RuntimeError(f"{path}: 'plugin' must be a mapping, got {type(plugin).__name__}")
    unknown = set(plugin.keys()) - _KNOWN_PLUGIN_KEYS
    if unknown:
        raise RuntimeError(f"{path}: unknown keys in plugin block: {sorted(unknown)}")
    backend_default = plugin.get("backend_default", "claude")
    if backend_default not in _VALID_BACKENDS:
        raise RuntimeError(
            f"{path}: plugin.backend_default must be one of {sorted(_VALID_BACKENDS)}, "
            f"got {backend_default!r}"
        )
    overrides = plugin.get("backend_overrides", {}) or {}
    if not isinstance(overrides, dict):
        raise RuntimeError(f"{path}: plugin.backend_overrides must be a mapping")
    for cmd, val in overrides.items():
        if val not in _VALID_BACKENDS:
            raise RuntimeError(
                f"{path}: plugin.backend_overrides[{cmd!r}] must be one of "
                f"{sorted(_VALID_BACKENDS)}, got {val!r}"
            )
    plugin["backend_default"] = backend_default
    plugin["backend_overrides"] = overrides
    raw["plugin"] = plugin
```

**Default-when-missing contract (CONTEXT.md §D-02):** when `.graph-wiki.yaml` exists but has no `plugin:` key, `read()` returns the same dict it always did but with `raw["plugin"] = {"backend_default": "claude", "backend_overrides": {}}` filled in. When the file is missing, the existing `return {}` branch fires unchanged — callers must handle the empty-dict case (this is the existing contract).

---

### `packages/workspace-io/tests/test_manifest.py` (MODIFY — add cases)

**Self-analog — match the existing test factory and assertion style:**

```python
# Existing pattern at lines 7–15 (the _v2 helper):
def _v2(plugins):
    return {
        "version": 2,
        "initialized_at": "2026-05-08",
        "plugins": [
            {"name": p, "installed_version": None, "applied_version": None}
            for p in plugins
        ],
    }
```

**Existing raises-test pattern at lines 53–61 (template for new negative cases):**

```python
def test_read_raises_on_v1(tmp_path):
    """D-14: manifest.read() raises on v1 format (no coercion path)."""
    mpath = tmp_path / ".graph-wiki.yaml"
    mpath.write_text(
        "version: 1\ninitialized_at: 2026-05-17\nplugins:\n  - code-wiki-agent\n",
        encoding="utf-8",
    )
    with pytest.raises(RuntimeError):
        read(mpath)
```

**New cases to add (D-02 strict-raises coverage):**

- `test_plugin_block_default_when_missing` — manifest with no `plugin:` key returns `{backend_default: "claude", backend_overrides: {}}`.
- `test_plugin_block_passthrough` — known keys are returned verbatim (`backend_default: bedrock` + one override).
- `test_plugin_block_raises_on_unknown_key` — `pytest.raises(RuntimeError, match="unknown keys")`.
- `test_plugin_block_raises_on_invalid_backend` — `pytest.raises(RuntimeError, match="must be one of")` for both `backend_default` and an override value.
- `test_plugin_block_raises_when_not_mapping` — `plugin: "claude"` (string instead of dict).

---

### `plugins/graph-wiki/.claude-plugin/plugin.json` (config)

**Analog (verbatim source, 21 lines):** `/Users/pat/Personal/lattice/plugins/lattice-wiki/.claude-plugin/plugin.json`

```json
{
    "name": "lattice-wiki",
    "version": "0.5.2",
    "description": "Build and maintain a persistent, cross-referenced markdown wiki alongside any source-code project — single packages, monorepos, or hybrid shapes. Adapts to the repo's folder structure: classifies top-level dirs as apps, packages, domains, or docs containers, and pins the layout in CLAUDE.md/AGENTS.md.",
    "author": { "name": "Patrick Sprowls" },
    "license": "MIT",
    "keywords": ["documentation", "knowledge-management", "wiki", "obsidian", "monorepo", "single-package", "adaptive"],
    "env": { "LATTICE_WIKI_ROOT": "${CLAUDE_PLUGIN_ROOT}" }
}
```

**Required rewrites (CONTEXT.md §D-03 + SHELL-OUT-PATTERN.md):**

- `name`: `"lattice-wiki"` → `"graph-wiki"`
- `version`: `"0.5.2"` → `"0.1.0"` (new package identity — D-03)
- `description`: `lattice-wiki` → `graph-wiki` in prose; append one sentence noting this is the Claude Code host path with `code-wiki-agent` as the Bedrock companion (executor discretion on exact wording per Claude's Discretion)
- `author`, `license`: preserved verbatim
- `keywords`: preserved verbatim (no additions per D-03)
- `env.LATTICE_WIKI_ROOT` → `env.GRAPH_WIKI_ROOT` (key rename; value `${CLAUDE_PLUGIN_ROOT}` preserved)

---

### `plugins/graph-wiki/skills/graph-wiki/scripts/_config.py` (config — backend selector, SO-04)

**Primary analog (verbatim source, 24 lines):** `/Users/pat/Personal/lattice/plugins/lattice-wiki/skills/lattice-wiki/scripts/_config.py`

```python
"""Load .lattice-wiki.json for plugin shim dispatch."""
from __future__ import annotations

import json
from pathlib import Path

_DEFAULTS = {
    "scan": "claude", "lint": "claude", "ingest": "claude",
    "query": "claude", "init": "claude", "log": "claude",
}


def backend_for(command: str, repo_root: str | None = None) -> str:
    """Return 'claude' or 'bedrock' for the given command."""
    root = Path(repo_root) if repo_root else Path.cwd()
    cfg_path = root / ".lattice-wiki.json"
    if not cfg_path.exists():
        return "claude"
    try:
        with open(cfg_path) as f:
            raw = json.load(f)
        return raw.get("backends", {}).get(command, "claude")
    except (json.JSONDecodeError, OSError):
        return "claude"
```

**Required rewrites (SO-04 + D-02):**

```python
"""Backend selector for graph-wiki shims. Reads .graph-wiki.yaml [plugin] block."""
from __future__ import annotations

from typing import Literal

from workspace_io import config as _ws_config
from workspace_io.manifest import read as _read_manifest


def backend_for(command: str, repo: str | None = None) -> Literal["claude", "bedrock"]:
    """Return 'claude' (default) or 'bedrock' for the given command.

    Resolution order: backend_overrides[command] > backend_default > "claude".
    On any resolution failure (no workspace, missing manifest, malformed block)
    falls back to "claude" — mirrors upstream's tolerant fallback shape.
    """
    try:
        cfg = _ws_config.resolve()
        manifest = _read_manifest(cfg.workspace / ".graph-wiki.yaml")
    except Exception:
        return "claude"
    plugin = manifest.get("plugin") or {}
    overrides = plugin.get("backend_overrides") or {}
    if command in overrides:
        return overrides[command]
    return plugin.get("backend_default", "claude")
```

**Two changes from upstream (per SO-04):**
1. **Manifest source:** `.lattice-wiki.json` → `.graph-wiki.yaml` via `workspace_io.manifest.read`.
2. **Key path:** JSON `backends.<cmd>` → YAML `plugin.backend_overrides.<cmd>` with fallback to `plugin.backend_default`.

**Error-shape discretion (CONTEXT.md Claude's Discretion):** Upstream returns `"claude"` on every failure (no raise). Match upstream verbatim — the `except Exception:` is intentional, not lazy.

---

### `plugins/graph-wiki/skills/graph-wiki/scripts/<cmd>.py` (5 shims — SO-02 template)

**Primary analog (canonical shim shape, 53 lines, retargeted 5×):** `/Users/pat/Personal/lattice/plugins/lattice-wiki/skills/lattice-wiki/scripts/init_vault.py`

```python
#!/usr/bin/env python3
"""Plugin shim for init_vault — dispatches to lattice-wiki-core or lattice-wiki-agent."""
import sys
from pathlib import Path

_vendor = Path(__file__).parent / "vendor"
if _vendor.exists():
    sys.path.insert(0, str(_vendor))

from lattice_wiki_core.init_vault import main as _core_main


def main() -> None:
    try:
        from _config import backend_for
    except ImportError:
        backend_for = lambda cmd, repo=None: "claude"  # noqa: E731

    backend = backend_for("init")

    if backend == "bedrock":
        try:
            # Upstream calls Bedrock agent directly (~20 lines of asyncio + InitAgent).
            ...
        except ImportError:
            sys.exit("[error] backend=bedrock requires lattice-wiki-agent to be installed")
    else:
        _core_main()


if __name__ == "__main__":
    main()
```

**Required rewrites (SO-02; apply identically across all 5 + 1 shims):**

```python
#!/usr/bin/env python3
"""Plugin shim for <cmd> — dispatches to vault_io (claude) or code-wiki-agent (bedrock)."""
import subprocess
import sys

from vault_io.<module> import main as _core_main


def main() -> None:
    try:
        from _config import backend_for
    except ImportError:
        backend_for = lambda cmd, repo=None: "claude"  # noqa: E731

    backend = backend_for("<cmd>")

    if backend == "bedrock":
        subprocess.run(["code-wiki-agent", "<cmd>", *sys.argv[1:]], check=True)
    else:
        _core_main()


if __name__ == "__main__":
    main()
```

**Three deltas from upstream (per SHELL-OUT-PATTERN.md §SO-02):**

1. **Drop the `vendor/` sys.path injection** — not needed; `uv run --project "$DEEP_AGENTS_ROOT"` already resolves the venv per SO-01.
2. **Import source rename:** `from lattice_wiki_core.<module> import main` → `from vault_io.<module> import main`.
3. **Bedrock branch:** the upstream ~20-line `InitAgent` / `asyncio.run` block becomes a single `subprocess.run(["code-wiki-agent", "<cmd>", *sys.argv[1:]], check=True)` — entire Bedrock path stays inside the headless CLI surface.

**Per-shim retarget table:**

| Shim file | `<module>` import | `"<cmd>"` selector | Bedrock subcommand |
|---|---|---|---|
| `init_vault.py` | `vault_io.init_vault` | `"init"` | `code-wiki-agent init` |
| `scan_monorepo.py` | `vault_io.scan_monorepo` | `"scan"` | `code-wiki-agent scan` |
| `ingest_source.py` | `vault_io.ingest_source` | `"ingest"` | `code-wiki-agent ingest source` *(explicitly `ingest source`, NOT `ingest work-item` — per `ingest.md` spec)* |
| `lint_wiki.py` | `vault_io.lint_wiki` | `"lint"` | `code-wiki-agent lint` |
| `wiki_search.py` | `vault_io.wiki_search` | `"query"` | `code-wiki-agent query` |
| `detect_containers.py` | `vault_io.detect_containers` | `"init"` | `code-wiki-agent init` *(pre-step of init; spec keeps it under the init backend selector per `init.md`)* |

**In-tree thin-delegation pattern (sanity check that the idiom works in this monorepo):** `packages/vault-io/src/vault_io/_workspace.py` — the 39-line module proves "thin shim that imports from a sibling package" is the established shape. Plugin shims are the same idea, just out-of-tree (`plugins/` instead of `packages/`).

---

### `plugins/graph-wiki/commands/<cmd>.md` (6 docs)

**Analog source:** upstream `/Users/pat/Personal/lattice/plugins/lattice-wiki/commands/<cmd>.md` for each of `init`, `scan`, `ingest`, `lint`, `query`, `log`.

**Prose-preservation rules per command:** follow the section-by-section verdict tables in each `.planning/spec/13-plugin-contract/<cmd>.md`. The standard rewrites are:

| Token in upstream | Token in port |
|---|---|
| `/lattice-wiki:<cmd>` | `/graph-wiki:<cmd>` |
| `${CLAUDE_PLUGIN_ROOT}/skills/lattice-wiki/scripts/<x>.py` | `${CLAUDE_PLUGIN_ROOT}/skills/graph-wiki/scripts/<x>.py` |
| `lattice-wiki/SKILL.md` | `graph-wiki/SKILL.md` |
| `lattice-wiki/references/<x>.md` | `graph-wiki/references/<x>.md` |
| `lattice_wiki_core.<module>` | `vault_io.<module>` |
| `lattice-workspace` | `workspace_io` |
| `LATTICE_WIKI_ROOT` env reference | `GRAPH_WIKI_ROOT` env reference |
| `lattice-wiki` (plugin id in prose) | `graph-wiki` |

**Special reshape (lint only, per `lint.md` spec):**

- Drop the `### Pass 1b — Work lifecycle lint` section entirely (work-layer out per C-01).
- Drop the `## Work lint` header from `### Pass 3 — Report`.
- Remove the work-layer sentence from the H1 opening paragraph and the frontmatter `description`.
- No `scripts/lint_work.py` file ships.

**Special omissions (3 dropped commands):**

- **No file** at `plugins/graph-wiki/commands/archive.md`
- **No file** at `plugins/graph-wiki/commands/regen-index.md`
- **No file** at `plugins/graph-wiki/commands/status.md`

(Per C-01: drop verdict = no `.md` ships, not "ship and disable".)

---

### `plugins/graph-wiki/agents/{ingestor,librarian,linter,scanner}.md` (4 docs)

**Analog source:** upstream `/Users/pat/Personal/lattice/plugins/lattice-wiki/agents/<same>.md`.

**File names stay** (SHELL-OUT-PATTERN.md §"Agent / skill rename map"); only the **prose inside** is rebranded. Apply the same token rewrites as the command files. Discretion per CONTEXT.md: if the agent prose body references `/lattice-wiki:` slash commands inside, swap them; otherwise leave verbatim — pure brand-swap pass, no rewrite needed.

---

### `plugins/graph-wiki/skills/graph-wiki/SKILL.md`, `README.md`, `references/*.md`

**Analog source:** upstream `/Users/pat/Personal/lattice/plugins/lattice-wiki/skills/lattice-wiki/{SKILL.md, README.md, references/*.md}`.

**Directory rename:** `skills/lattice-wiki/` → `skills/graph-wiki/` (wholesale move).

**Reference docs to port (12 files, names preserved, prose rebranded):**

```
cross-tool-setup.md       detection-workflow.md     ingest-workflow.md
lifecycle-rules.md        lint-workflow.md          monorepo-principles.md
obsidian-setup.md         page-formats.md           query-workflow.md
scan-workflow.md          sidecar-schema.md         wiki-schema.md
```

Apply the same token-rewrite table as the command files.

---

### `plugins/graph-wiki/CLAUDE.md` (~6.2KB plugin guidance)

**Analog source:** upstream `/Users/pat/Personal/lattice/plugins/lattice-wiki/CLAUDE.md`.

**Treatment (CONTEXT.md Claude's Discretion):** pure rename + brand-swap pass. No structural rewrite. ~6.2KB → ~6.2KB modulo brand strings.

---

### `plugins/graph-wiki/README.md` (FRESH-WRITE — D-04)

**No analog — this is the only file in Plan 3 that is NOT copied from upstream.** D-04 explicitly diverges: graph-wiki-specific focus only.

**Structure (per CONTEXT.md §D-04, fixed five-section outline):**

```markdown
# graph-wiki

One paragraph: Claude Code host path; companion to `code-wiki-agent` Bedrock CLI; same wiki surface.

## Setup

- `$DEEP_AGENTS_ROOT` env var (PD-01) — example export in shell rc.
- `uv` prerequisite (PD-03).
- `$CLAUDE_PLUGIN_ROOT` is auto-set by Claude Code (PD-02) — note only.

## Backend configuration

Example `.graph-wiki.yaml` snippet showing `[plugin]` block with `backend_default: claude` and one
override (e.g., `ingest: bedrock`).

## Commands

- `/graph-wiki:init` — bootstrap wiki
- `/graph-wiki:scan` — sync packages
- `/graph-wiki:ingest` — ingest a source
- `/graph-wiki:lint` — health-check
- `/graph-wiki:query` — librarian Q&A
- `/graph-wiki:log` — view recent log entries

### Not ported

- `archive`, `regen-index`, `status` — work-layer out of v1.2 scope; see
  `.planning/PROJECT.md` §"Explicitly out of v1.2" for rationale.

## See also

- Upstream `lattice-wiki` README for general framing (iron rules, layout block, frontmatter schema).
```

**Tone analog:** `packages/workspace-io/README.md` (terse, deep-agents-internal, audience = Pat).

---

### `.planning/phases/14-plugin-port-m3b/14-VERIFICATION.md` (D-05 transcript)

**Analog:** `.planning/phases/12-drift-backport-ecosystem-rebrand-m2/12-VERIFICATION.md` (Phase 12's verification log shape).

**Required content (CONTEXT.md §D-05):** fenced markdown block containing the **full** transcript of `/graph-wiki:query "what is workspace-io?"` (or equivalent) run in a Claude Code session against `~/Personal/wiki/deep-agents`. Includes: user question, librarian fan-out evidence (citations, pages read), synthesized answer with `[[wikilinks]]` and `code-path:line` citations. No snapshot baseline, no assertion script.

---

## Shared Patterns

### Brand-rename rubric (applies to Plans 1, 2, and 3 — every new file)

**Source:** Phase 12 SR-01 / `.planning/phases/12-drift-backport-ecosystem-rebrand-m2/12-CONTEXT.md`
**Apply to:** every file created or modified in Phase 14.

**Token table (universal — same as commands section above, restated for sweep coverage):**

```
lattice              →  graph-wiki      (in prose / IDs)
LATTICE              →  GRAPH_WIKI      (in env var names)
lattice_wiki_core    →  vault_io        (in Python imports)
lattice-workspace    →  workspace_io    (in prose / Python imports)
lattice-wiki         →  graph-wiki      (in plugin id / namespace prose / slash commands)
LATTICE_WIKI_ROOT    →  GRAPH_WIKI_ROOT (in env var keys)
.lattice-wiki.json   →  .graph-wiki.yaml  (in config file refs)
/lattice-wiki:<cmd>  →  /graph-wiki:<cmd> (in slash command refs)
```

### Brand gate (BRAND-04 / VP-03 / SC#3)

**Source:** `/Users/pat/Personal/deep-agents/scripts/check-brand.sh` + `/Users/pat/Personal/deep-agents/.brand-grep-allow`
**Apply to:** every file created or modified in Phase 14 — full tree must pass.

**Invocation (verbatim Phase 12 / from CONTEXT.md §SC#3 area):**

```bash
bash scripts/check-brand.sh
grep -rEl 'lattice|LATTICE|lattice_workspace|lattice_wiki_core' \
    packages/ agents/ plugins/ .planning/ CLAUDE.md
# Plus the explicit SC#3 gate:
grep -r 'lattice_' plugins/graph-wiki/   # must return zero hits
```

**Allowlist policy:** Phase 14 should NOT add entries to `.brand-grep-allow`. The two `vault-io` ports and the entire `plugins/graph-wiki/` tree are expected to clear the gate without exceptions (port-and-rebrand work; no provenance lock-in). If a hit is unavoidable for any reason, add the entry with an R-decision rationale comment matching the existing format (see `.brand-grep-allow` lines 1–35 for the comment style).

### Strict-raises manifest validation (Phase 11 §D-14, carried forward by Phase 14 §D-02)

**Source:** existing pattern at `packages/workspace-io/src/workspace_io/manifest.py` lines 14–22.
**Apply to:** new `plugin:` block validation in Plan 3a (only the manifest extension).

### Thin delegation shim (Phase 11)

**Source:** `packages/vault-io/src/vault_io/_workspace.py` (full 39-line file).
**Apply to:** the 6 plugin shim scripts in `plugins/graph-wiki/skills/graph-wiki/scripts/` — same "thin shim that imports from a sibling package" idiom, just out-of-tree. Mental model: the shim is the boundary, backend (vault-io vs. code-wiki-agent subprocess) is the back-end (this mirrors Phase 11 §D-02's two-tier MCP-boundary passthrough).

### Atomic per-file commits during a sweep (SQ-02)

**Source:** Phase 11 and Phase 12 commit cadence (see `.planning/phases/12-drift-backport-ecosystem-rebrand-m2/12-04-SUMMARY.md` for the established rhythm).
**Apply to:** Plan 3 (multiple commits within one plan family: manifest extension → scaffold copy → shim rewrites → rebrand sweep → smoke transcript). Plans 1 and 2 are smaller — one commit each is fine.

---

## No Analog Found

None. Every file has either an in-tree analog (Python modules, tests, manifest extension, verification log shape) or an upstream-only analog (intended — plugin assets are by definition the port surface). The single FRESH-WRITE (`plugins/graph-wiki/README.md`, D-04) has a structural sibling in `packages/workspace-io/README.md` for tone reference and a fixed five-section outline from CONTEXT.md.

---

## Metadata

**Analog search scope:**
- In-tree: `packages/vault-io/`, `packages/workspace-io/`, `plugins/`, `scripts/`, `.planning/phases/11-*`, `.planning/phases/12-*`
- Upstream (read-only references): `/Users/pat/Personal/lattice/plugins/lattice-wiki/`, `/Users/pat/Personal/lattice/packages/lattice-wiki-core/src/lattice_wiki_core/`

**Files scanned (read):** 21
- `14-CONTEXT.md`, `CONTRACT-INDEX.md`, `SHELL-OUT-PATTERN.md`, 6 per-command specs
- `_workspace.py`, `manifest.py`, `config.py`, `init_vault.py` (head), `ingest_source.py` (head), `graph_analyzer.py` (head), `scan_monorepo.py` (head)
- `test_manifest.py`, `test_ports_importable.py`, `test_lint_modules.py` (head)
- `check-brand.sh`, `.brand-grep-allow` (head)
- `ROADMAP.md` (Phase 14 section)
- Upstream: `lint_wiki.py` (head), `wiki_search.py` (head), `plugin.json`, `init_vault.py` (shim), `_config.py`

**Pattern extraction date:** 2026-05-18
