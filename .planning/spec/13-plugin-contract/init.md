---
command: init
upstream_source: plugins/lattice-wiki/commands/init.md
port_verdict: rename
---

# /graph-wiki:bootstrap — Port Spec

## Shell-out contract

- **Invocation:** `uv run --project "$AGENT_RESEARCH_ROOT" python3 "${CLAUDE_PLUGIN_ROOT}/skills/graph-wiki/scripts/init_vault.py" $ARGUMENTS`
  (see SHELL-OUT-PATTERN.md §SO-01 for the full rationale on `$AGENT_RESEARCH_ROOT` + `uv run --project`)
- **Target module (claude backend):** `wiki_io.init_vault.main`
- **Target subprocess (bedrock backend):** `code-wiki-agent init <args>`
- **Args pass-through** (all flags map 1:1 to `wiki_io.init_vault.main`):
  - `--topic "<topic>"` — required; short description of the repo (e.g. `"platform monorepo"`)
  - `--tool <claude-code|codex|cursor|antigravity|opencode|gemini-cli|all>` — which schema file(s) to install; default `all`
  - `--force` — overwrite non-empty target wiki directory
  - `--json` — emit result as JSON (used by the pre-step and by automated callers)
  - `--non-interactive` — skip ambiguous-container prompts; mark them `skip` automatically
- **Pre-step:** `wiki_io.detect_containers.main --json` runs first (inside the claude session, not via shim) to enumerate top-level repo containers. The plugin displays the detected table and prompts the user for any `ambiguous` rows before passing confirmed classifications to `init_vault.py` via `--non-interactive`. This mirrors the upstream container-detection flow verbatim; the pre-step does not go through the shim.

## Prose-preservation map

Walk of every H2/H3 section in upstream `plugins/lattice-wiki/commands/init.md` (87 lines):

| Section | Verdict |
|---------|---------|
| `## Usage` | verbatim except namespace rename: `/lattice-wiki:init` → `/graph-wiki:bootstrap` |
| `## Examples` | verbatim except namespace rename in the example commands |
| `## Container detection` | verbatim except script path rename: `${CLAUDE_PLUGIN_ROOT}/skills/lattice-wiki/scripts/detect_containers.py` → `${CLAUDE_PLUGIN_ROOT}/skills/graph-wiki/scripts/detect_containers.py`; prose about `package-family` classification rule preserved verbatim |
| `## What it creates` | verbatim; the directory tree and commentary (including `raw/` and `work/` sibling note) are unchanged |
| `## Next steps` | verbatim except namespace rename: `/lattice-wiki:scan` → `/graph-wiki:scan`, `/lattice-wiki:ingest` → `/graph-wiki:ingest` |
| `## Sub-page templates` | verbatim; template list (`overview.md`, `api.md`, `patterns.md`, `work.md`, `context.md`) and sub-page scaffolding note are unchanged |
| `## Script` | rename: `${CLAUDE_PLUGIN_ROOT}/skills/lattice-wiki/scripts/init_vault.py` → `${CLAUDE_PLUGIN_ROOT}/skills/graph-wiki/scripts/init_vault.py` |
| `## Skill Reference` | rename: `lattice-wiki/SKILL.md` → `graph-wiki/SKILL.md` |

## Agent / skill rename map

- **Agent files used by `/init`:** None — `/graph-wiki:bootstrap` is not dispatched through a named sub-agent. The plugin command runs inline (container detection + init_vault invocation) without a separate agent document.
- **Skill:** `skills/lattice-wiki/SKILL.md` → `skills/graph-wiki/SKILL.md` — full file rename + namespace rebrand of all `/lattice-wiki:*` prose inside the file.
- **Script:** `skills/lattice-wiki/scripts/init_vault.py` → `skills/graph-wiki/scripts/init_vault.py` — shim retargeted per SO-02; the shim body imports `wiki_io.init_vault` instead of `lattice_wiki_core.init_vault`.
- **Detect-containers script:** `skills/lattice-wiki/scripts/detect_containers.py` → `skills/graph-wiki/scripts/detect_containers.py` — same SO-02 shim pattern; imports `wiki_io.detect_containers`. (The upstream plugin invokes this as a subprocess from inside the slash command prose; graph-wiki preserves this pattern.)

## Reshape notes

No behavior changes vs upstream. Pure rename of namespace and import target. The container detection flow (pre-step → user confirmation → `--non-interactive` pass into `init_vault.py`) is preserved verbatim. The `_config.py` backend selector seam is preserved per SO-04; the `bedrock` branch shells to `code-wiki-agent init <args>`.

## Verification gate

Phase 14 confirms `/graph-wiki:bootstrap` works by running the following smoke:

1. Create an empty temp directory: `mkdir /tmp/test-wiki-root && cd /tmp/test-wiki-root && git init`.
2. Run `/graph-wiki:bootstrap --topic "test" --tool claude-code` from that directory.
3. Verify the resulting `<workspace>/wiki/` tree contains: `index.md`, `log.md`, `CLAUDE.md`, `.gitignore`, `concepts/`, `architecture/`, `adrs/`, `sources/`, `dependencies/`, `.templates/`.
4. Diff the layout block written into `<workspace>/wiki/CLAUDE.md` against a baseline captured from a fresh `/lattice-wiki:init --topic "test" --tool claude-code` run with identical args in an identical directory (modulo brand string differences: `graph-wiki` vs `lattice-wiki`). Expect byte-identical structure with only brand strings differing.
5. Failure mode to test: run `/graph-wiki:bootstrap --topic "test"` a second time without `--force`; must exit with "not empty" error (verbatim upstream behavior).
