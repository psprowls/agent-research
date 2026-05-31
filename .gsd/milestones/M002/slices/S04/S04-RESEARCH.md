# S04 Runtime docs and graph-wiki workflow rewiring — Research

**Date:** 2026-05-31

## Summary

S04 is a targeted rewiring slice. The active runtime risk is not the Python package split itself; S02 already proved `graph-wiki-cli` exposes `gw`. The risk is that the Claude plugin's Bedrock branch still shells out to the removed `graph-wiki-agent` executable, and two of those shims need command-shape translation, not just executable-name replacement: `init_vault.py` must call `gw bootstrap`, and `ingest_source.py` must call `gw ingest source`.

The current user-facing docs also still describe `graph-wiki-agent` as the first agent / Bedrock CLI companion and show `uv run graph-wiki-agent --help`. S04 should update current docs and runtime-facing plugin guidance to the v1.12 package split while preserving the plugin identity decision: `.graph-wiki.yaml` plugin identity and plugin manifest name remain `graph-wiki-agent`/`graph-wiki` where they describe config identity, not executable names.

Relevant active requirements: R005 is owned directly by S04 (runtime-facing graph-wiki workflows use `gw`), R008 is owned directly by S04 (current user-facing docs describe new package layout and `gw` usage), and R007 is supported by leaving verification commands and stale-reference checks for S05 full integration.

## Recommendation

Implement S04 in three small units:

1. Rewire the five Bedrock plugin shims from `graph-wiki-agent` to `gw`, using exact current CLI command names: `scan`, `bootstrap`, `ingest source`, `lint`, and `query`.
2. Add a package-local regression test in `packages/graph-wiki-cli/tests` that executes or imports the plugin shim `main()` paths with a fake Bedrock backend and fake `subprocess.run`, asserting the argv sent to subprocess. This is the fastest proof of R005 without requiring Bedrock.
3. Update current user-facing docs (`README.md`, `plugins/graph-wiki/README.md`, and runtime-facing plugin guidance in `plugins/graph-wiki/CLAUDE.md` / `.claude-plugin/plugin.json`) to say Bedrock workflows call `gw`, and to describe `graph-wiki-core`, `graph-wiki-cli`, and `graph-wiki-mcp` under `packages/`.

Do not update every historical mention of `graph-wiki-agent` in fixtures, old agents tests, pyproject metadata, generated caches, or historical notes. The milestone explicitly allows historical references, and S05 owns removing the obsolete `agents/` layout and broader stale active references. For S04, classify stale references by behavior-facing docs/runtime shims vs plugin identity/historical artifacts.

## Implementation Landscape

### Key Files

- `plugins/graph-wiki/skills/graph-wiki/scripts/scan_monorepo.py` — Bedrock branch currently runs `["graph-wiki-agent", "scan"] + sys.argv[1:]`; change to `["gw", "scan"] + sys.argv[1:]`. Docstring should say `gw` or Bedrock CLI, not `graph-wiki-agent`.
- `plugins/graph-wiki/skills/graph-wiki/scripts/init_vault.py` — Bedrock branch currently runs `["graph-wiki-agent", "init"] + sys.argv[1:]`; `gw init` does not exist. Verified `gw init --help` exits 2, while `gw bootstrap --help` exits 0. Change to `["gw", "bootstrap"] + sys.argv[1:]`.
- `plugins/graph-wiki/skills/graph-wiki/scripts/ingest_source.py` — Bedrock branch currently runs `["graph-wiki-agent", "ingest"] + sys.argv[1:]`; current Typer shape is an `ingest` sub-app with `source` and `work-item`. Verified `gw ingest source --help` exits 0. Change to `["gw", "ingest", "source"] + sys.argv[1:]`.
- `plugins/graph-wiki/skills/graph-wiki/scripts/lint_wiki.py` — Bedrock branch currently runs `["graph-wiki-agent", "lint"] + sys.argv[1:]`; change to `["gw", "lint"] + sys.argv[1:]`.
- `plugins/graph-wiki/skills/graph-wiki/scripts/wiki_search.py` — Bedrock branch currently runs `["graph-wiki-agent", "query"] + sys.argv[1:]`; change to `["gw", "query"] + sys.argv[1:]`.
- `plugins/graph-wiki/skills/graph-wiki/scripts/_config.py` — Keep backend selector unchanged. It reads the `[plugin]` block and returns `claude` or `bedrock`; it does not name the executable. Its docstring is still accurate.
- `plugins/graph-wiki/skills/graph-wiki/scripts/_uv_reexec.py` — No behavior change required. It ensures `wiki_io` is importable for plugin shims. It does not ensure `gw` is installed; after S04 a missing current command should fail as missing `gw`, not as stale `graph-wiki-agent`.
- `packages/graph-wiki-cli/src/graph_wiki_cli/cli.py` — Source of truth for command names. Confirmed active commands include `bootstrap`, `scan`, `query`, `lint`, `log`, `trace`, `migrate-vault`, and `ingest source` / `ingest work-item`. No source change expected unless shims reveal a command mismatch.
- `packages/graph-wiki-cli/tests/unit/test_cli_bootstrap.py` — Existing help subprocess pattern for `gw bootstrap --help`; useful model for environment (`NO_COLOR=1`, `TERM=dumb`, `COLUMNS=200`).
- `packages/graph-wiki-cli/tests/unit/test_cli_boundary.py` — Existing negative boundary assertions for stale CLI aliases. Do not loosen; S04 can add separate shim assertions without introducing old aliases.
- `README.md` — Root docs still say first agent is `graph-wiki-agent`, quickstart runs `uv run graph-wiki-agent --help`, and workspace layout shows `agents/graph-wiki-agent/`. Update to current v1.12 layout and `uv run --package graph-wiki-cli gw --help` (or `uv run gw --help` if preferring root script resolution after sync; package-scoped is clearer for package split proof).
- `plugins/graph-wiki/README.md` — User-facing plugin docs still say the Bedrock surface is `graph-wiki-agent`, `[plugin]` routes to `graph-wiki-agent`, and See also points to `agents/graph-wiki-agent/`. Update to `gw` and `packages/graph-wiki-cli/`, while preserving plugin identity/config block wording.
- `plugins/graph-wiki/CLAUDE.md` — Runtime-maintainer guidance still says shims shell out to `graph-wiki-agent <cmd>` and `_config.py` selects the optional `graph-wiki-agent` Bedrock CLI. Update to `gw` and the exact command mapping.
- `plugins/graph-wiki/.claude-plugin/plugin.json` — Description says `graph-wiki-agent is the parallel Bedrock CLI companion`. Update description to say `gw` / `graph-wiki-cli`; keep plugin `name` as `graph-wiki`.

### Natural Seams

- **Shim rewiring** is independent from doc prose and can be tested without Bedrock by monkeypatching `subprocess.run` plus the backend selector.
- **Docs update** is mostly string/prose work. It should not wait for S05 `agents/` removal, but should avoid promising `agents/` as the live package layout.
- **Stale-reference classification** should be a verification step, not a broad edit. Expected remaining stale strings after S04 include negative boundary tests, plugin identity strings, historical docs/fixtures, generated caches, and S05-owned obsolete `agents/` tree references.

### First Proof

The highest-risk first proof is a package-local shim argv test before or immediately after editing the scripts. Suggested test design:

- Add `packages/graph-wiki-cli/tests/unit/test_plugin_bedrock_shims.py`.
- Locate script dir via `Path(__file__).resolve().parents[...] / "plugins/graph-wiki/skills/graph-wiki/scripts"` or by walking upward until `plugins/graph-wiki` exists.
- Use `monkeypatch.syspath_prepend(str(script_dir))` so `_uv_reexec` and `_config` resolve like plugin execution.
- Insert a fake `_config` module into `sys.modules` with `backend_for = lambda command, repo=None: "bedrock"`.
- Monkeypatch `subprocess.run` to capture `args` and return `types.SimpleNamespace(returncode=0)`.
- Set `sys.argv` for each shim and call `runpy.run_path(str(script), run_name="__main__")`, expecting `SystemExit(0)` because the shim exits with subprocess return code.
- Parametrize expected argv:
  - `scan_monorepo.py` → `["gw", "scan", ...]`
  - `init_vault.py` → `["gw", "bootstrap", ...]`
  - `ingest_source.py` → `["gw", "ingest", "source", ...]`
  - `lint_wiki.py` → `["gw", "lint", ...]`
  - `wiki_search.py` → `["gw", "query", ...]`

This directly validates R005 without live AWS and guards the two non-trivial command translations.

### Verification

Use package-scoped commands consistent with S02:

```bash
NO_COLOR=1 TERM=dumb COLUMNS=200 uv run --package graph-wiki-cli gw bootstrap --help
NO_COLOR=1 TERM=dumb COLUMNS=200 uv run --package graph-wiki-cli gw ingest source --help
uv run --package graph-wiki-cli python -m pytest packages/graph-wiki-cli/tests/unit/test_plugin_bedrock_shims.py
uv run --package graph-wiki-cli python -m pytest packages/graph-wiki-cli/tests
```

For stale active references, use a focused scan after edits:

```bash
rg -n "graph-wiki-agent|graph_wiki_agent" README.md plugins/graph-wiki packages/graph-wiki-cli packages/graph-wiki-mcp packages/graph-wiki-core
```

Interpretation should be explicit. Remaining references in negative boundary tests are intended. References in `.graph-wiki.yaml` examples may be plugin identity and allowed by D004. References in generated caches should be ignored/cleaned opportunistically if touched, but not made a blocker for S04.

## Skill Discovery

Installed skills relevant to this slice:

- `write-docs` — relevant for updating `README.md` and plugin docs so a fresh reader sees package layout and current commands.
- `uv-package-manager` — relevant for package-scoped verification commands and avoiding stale workspace invocation patterns.

No additional skill install is necessary for core technologies here. This is local Python/Typer/uv/doc rewiring using established repo patterns; external library docs are not needed.

## Research Notes and Surprises

- `gw init` is not a valid current command. The plugin bootstrap shim must map old `init_vault.py` intent to `gw bootstrap`, not `gw init`.
- `gw ingest` is a sub-app, not the source-file action. The source ingest shim must call `gw ingest source`.
- Plugin command markdown generally invokes shim scripts, not the Bedrock executable directly, so the behavior-facing executable changes are concentrated in the five Python shims and top-level plugin docs.
- `plugins/graph-wiki/README.md` has a small typo already present (`locaiton`, `overriden`); not necessary for S04 unless editing nearby text.
- The root `pyproject.toml` still has `members = ["packages/*", "agents/*"]`; S05 owns package-only workspace cleanup. S04 docs can describe the intended v1.12 package layout without removing `agents/` yet.

## Sources

- `gsd_exec` b2247a9f-aebc-4f9a-88f7-805ce786e28f — broad stale-reference scan.
- `gsd_exec` f16bfa5a-ba8a-4d1f-b055-d4d74ef41912 — plugin shim subprocess and docs-reference summary.
- `gsd_exec` c88467dc-9c53-4584-91e4-00888fd80095 — current `gw` command decorators and shim command mapping.
- `gsd_exec` b9f1d63f-1030-41e9-9d2f-7f32b1ac56d9 — verified `gw init` fails, `gw bootstrap`, `gw ingest source`, `gw scan`, `gw lint`, and `gw query` help succeed.
- `packages/graph-wiki-cli/src/graph_wiki_cli/cli.py` — current Typer command source of truth.
- `plugins/graph-wiki/skills/graph-wiki/scripts/*.py` — runtime Bedrock shim sources.
- `README.md`, `plugins/graph-wiki/README.md`, `plugins/graph-wiki/CLAUDE.md`, `plugins/graph-wiki/.claude-plugin/plugin.json` — current user-facing docs needing command/layout updates.
