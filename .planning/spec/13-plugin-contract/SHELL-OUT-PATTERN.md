# graph-wiki Plugin — Shell-Out Pattern & Rename Map

This file owns the cross-cutting decisions referenced by every per-command spec file in `.planning/spec/13-plugin-contract/`. Per-command files say "see SHELL-OUT-PATTERN.md §SO-NN" rather than repeating invocation boilerplate. All four SO-01..SO-04 decisions are captured here, along with the plugin discovery requirements (PD-01..PD-03) and the agent/skill rename map that applies across the whole plugin surface.

## SO-01: uv run invocation with $DEEP_AGENTS_ROOT

Every ported plugin script in `plugins/graph-wiki/skills/graph-wiki/scripts/` is invoked as:

```bash
uv run --project "$DEEP_AGENTS_ROOT" python3 "${CLAUDE_PLUGIN_ROOT}/skills/graph-wiki/scripts/<x>.py" "$@"
```

**User setup:** The user sets `DEEP_AGENTS_ROOT` once in their shell rc file, for example:

```bash
export DEEP_AGENTS_ROOT=/Users/pat/Personal/deep-agents
```

**Auto-set:** `$CLAUDE_PLUGIN_ROOT` is auto-set by Claude Code at slash-command invocation time (per PD-02). No user configuration is needed for this variable.

**Rationale:** `uv run --project` resolves the deep-agents venv and makes `vault_io` and `workspace_io` importable without the user needing to activate a virtual environment manually. This approach is single-user-setup-friendly: one env var line in shell rc, no per-cwd discovery logic to maintain, and no risk of import errors from the wrong Python environment.

## SO-02: Shim file contents (the upstream pattern, retargeted)

Each script file is a thin shim that dispatches to the `claude` or `bedrock` backend. The template below is derived from the verified upstream pattern in `/Users/pat/Personal/lattice/plugins/lattice-wiki/skills/lattice-wiki/scripts/init_vault.py`:

```python
#!/usr/bin/env python3
"""Plugin shim for <cmd> — dispatches to vault_io (claude backend) or code_wiki_agent (bedrock backend)."""
import sys
from pathlib import Path

from vault_io.<module> import main as _core_main


def main() -> None:
    try:
        from _config import backend_for
    except ImportError:
        backend_for = lambda cmd, repo=None: "claude"  # noqa: E731

    backend = backend_for("<cmd>")

    if backend == "bedrock":
        # Subprocess into code-wiki-agent for this command
        import subprocess
        subprocess.run(["code-wiki-agent", "<cmd>", *sys.argv[1:]], check=True)
    else:
        _core_main()


if __name__ == "__main__":
    main()
```

**Two changes from upstream shim:**

1. **Import source:** `from vault_io.<module> import main` instead of `from lattice_wiki_core.<module> import main` — all helper modules route through `packages/vault-io/src/vault_io/` in this repo.
2. **Bedrock branch:** shells to `code-wiki-agent <cmd>` CLI subprocess instead of importing and invoking `lattice_wiki_agent` directly — the bedrock-backed Bedrock path stays entirely in the headless CLI surface.

The `vendor/` sys.path injection from upstream is dropped (not needed; `uv run --project` handles the venv already via SO-01).

## SO-03: Backend selector config — [plugin] block in .graph-wiki.yaml

Instead of upstream's separate `.lattice-wiki.json`, graph-wiki adds a `plugin:` section to the existing workspace manifest (`.graph-wiki.yaml`):

```yaml
plugin:
  backend_default: claude
  backend_overrides:
    ingest: bedrock   # optional, per-command override
```

The `plugin:` block lives alongside all other workspace settings in `.graph-wiki.yaml`, keeping workspace configuration in a single file (established in Phase 11).

**Extension point:** `workspace_io.manifest.read` is extended (Phase 14 task) to expose the `[plugin]` block as a structured object. Phase 13 does not implement this; it records the extension as a Phase 14 responsibility.

**Default-when-missing:** If `.graph-wiki.yaml` has no `plugin:` section, or if the file does not exist, `_config.py` defaults to `claude` for every command. This matches the v1.2 design decision: `claude` everywhere by default; `bedrock` is the documented opt-in for users who want the cost-frontier path for a specific command.

## SO-04: _config.py helper in plugin scripts dir

A small helper module lives at `plugins/graph-wiki/skills/graph-wiki/scripts/_config.py`.

**File path (relative to repo root):** `plugins/graph-wiki/skills/graph-wiki/scripts/_config.py`

**Function signature:**

```python
def backend_for(cmd: str, repo: str | None = None) -> Literal["claude", "bedrock"]:
    ...
```

**Behavior:** Reads `.graph-wiki.yaml` in the workspace root (discovered via `workspace_io.manifest.read`) and returns the resolved backend string for the given command. Resolution order: per-command override in `backend_overrides` > `backend_default` > `"claude"` fallback.

**Mirrors upstream:** This mirrors the shape of upstream's `_config.py` (which read `.lattice-wiki.json`). The rewiring changes are: (1) read `.graph-wiki.yaml` via `workspace_io.manifest.read` instead of loading `.lattice-wiki.json` directly, (2) navigate the YAML `plugin.backend_overrides.<cmd>` path instead of the JSON `backends.<cmd>` path.

## Plugin discovery requirements (PD-01..PD-03)

- **PD-01:** `$DEEP_AGENTS_ROOT` env var is the **only required user config**. It is documented in `plugins/graph-wiki/README.md` (Phase 14 will author this file). The README also documents the `plugin:` block syntax for backend overrides and notes the absence of the three work-layer commands.
- **PD-02:** `$CLAUDE_PLUGIN_ROOT` is auto-set by Claude Code at slash-command invocation time. This follows the same convention as upstream lattice-wiki; no Phase 13 or Phase 14 work is needed here — just verified behavior.
- **PD-03:** `uv` must be installed and on PATH. This is the same prerequisite as the rest of the deep-agents monorepo; it is documented in the plugin README. There is no fallback to bare `python3` — a bare `python3` invocation would fail to resolve `from vault_io import ...` since the venv is not activated.

## Agent / skill rename map (cross-cutting)

This section covers renames that span the entire plugin surface (not command-specific). Phase 14 executes these renames per this map.

**Skill directory (wholesale rename):**

| From | To |
|------|----|
| `plugins/lattice-wiki/skills/lattice-wiki/` | `plugins/graph-wiki/skills/graph-wiki/` |

**Skill files:**

| From | To | Note |
|------|----|----|
| `skills/lattice-wiki/SKILL.md` | `skills/graph-wiki/SKILL.md` | Rename path + rebrand namespace prose inside |
| `skills/lattice-wiki/README.md` | `skills/graph-wiki/README.md` | Rename path + rebrand namespace prose inside |

**Agent files (names stay; only namespace prose is rebranded inside each file):**

| File | Change |
|------|--------|
| `agents/ingestor.md` | Name stays as `ingestor.md`; rebrand all `lattice-wiki` prose references to `graph-wiki` inside the file |
| `agents/librarian.md` | Name stays as `librarian.md`; rebrand all `lattice-wiki` prose references to `graph-wiki` inside the file |
| `agents/linter.md` | Name stays as `linter.md`; rebrand all `lattice-wiki` prose references to `graph-wiki` inside the file |
| `agents/scanner.md` | Name stays as `scanner.md`; rebrand all `lattice-wiki` prose references to `graph-wiki` inside the file |

**Skill reference docs (directory rename, file inventory):**

All files under `skills/lattice-wiki/references/` move to `skills/graph-wiki/references/`. Phase 13 captures this as a directory rename; Phase 14 lists each file by name during the port. The current upstream inventory (read from `/Users/pat/Personal/lattice/plugins/lattice-wiki/skills/lattice-wiki/references/`):

- `cross-tool-setup.md`
- `detection-workflow.md`
- `ingest-workflow.md`
- `lifecycle-rules.md`
- `lint-workflow.md`
- `monorepo-principles.md`
- `obsidian-setup.md`
- `page-formats.md`
- `query-workflow.md`
- `scan-workflow.md`
- `sidecar-schema.md`
- `wiki-schema.md`

**Plugin metadata:**

| File | Change |
|------|--------|
| `.claude-plugin/plugin.json` | Plugin `id` field renamed `lattice-wiki` → `graph-wiki`; all namespace strings (`lattice-wiki`) updated to `graph-wiki` |

**Slash command namespace (universal):**

Every `/lattice-wiki:<cmd>` reference becomes `/graph-wiki:<cmd>` across all command files, agent prose, and skill prose.

## See also

- [CONTRACT-INDEX.md](CONTRACT-INDEX.md) — Single-table verdict summary of all 9 upstream commands; the canonical audit entry point for Phase 14's executor
- Per-command spec files: [init.md](init.md), [scan.md](scan.md), [ingest.md](ingest.md), [lint.md](lint.md), [query.md](query.md), [log.md](log.md)
