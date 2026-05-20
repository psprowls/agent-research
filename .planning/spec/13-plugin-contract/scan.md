---
command: scan
upstream_source: plugins/lattice-wiki/commands/scan.md
port_verdict: rename
---

# /graph-wiki:scan — Port Spec

## Shell-out contract

- **Invocation:** `uv run --project "$DEEP_AGENTS_ROOT" python3 "${CLAUDE_PLUGIN_ROOT}/skills/graph-wiki/scripts/scan_monorepo.py" $ARGUMENTS`
  (see SHELL-OUT-PATTERN.md §SO-01 for the full rationale on `$DEEP_AGENTS_ROOT` + `uv run --project`)
- **Target module (claude backend):** `vault_io.scan_monorepo.main`
- **Target subprocess (bedrock backend):** `code-wiki-agent scan <args>`
- **Args pass-through** (all flags map 1:1 to `vault_io.scan_monorepo.main`):
  - `--json` — emit result as JSON only (used by automated callers)
  - `--no-file-map` — skip per-workspace file-map generation (saves time on large monorepos)
  - `--max-depth <N>` — max directory depth expanded as header sections in the file map (default: 4)
  - `--no-index-regen` — skip regenerating `dependencies/index.md`
  - Workspace and repo are discovered automatically via the resolved graph-wiki workspace (`workspace_io.config.resolve()`); no `--repo` flag is needed.
- **Pre-step:** NONE — but explicitly note: **the clean-tree-on-main git gate is enforced inside `vault_io.scan_monorepo.main`** (preserved from upstream); no additional pre-step is required at the shim layer. When the working tree is not clean or HEAD is not on `main`, `scan_monorepo.main` runs in read-only mode (no `last_sync_commit` bump). The shim does not add any additional gate logic.

## Prose-preservation map

Walk of every H2/H3 section in upstream `plugins/lattice-wiki/commands/scan.md` (75 lines):

| Section | Verdict |
|---------|---------|
| `## Usage` | verbatim except namespace rename: `/lattice-wiki:scan` → `/graph-wiki:scan`; workspace discovery note changes from "via `lattice-workspace`" to "via the resolved graph-wiki workspace" |
| `## What happens` | verbatim except: step 1 script path rename (`scripts/scan_monorepo.py` stays, but under `graph-wiki/`); all 7 numbered steps preserved verbatim including the clean-tree-on-main gate in step 5 |
| `## Sub-agent` | verbatim except namespace rename in prose: "See `agents/scanner.md`" unchanged (agent file name stays `scanner.md`); surrounding sentence rebrand `/lattice-wiki:scan` → `/graph-wiki:scan` |
| `## Rules` | verbatim; the three bullet rules (no silent deletes, no prose overwrite, stub new pages only) are preserved byte-for-byte |
| `## Layout reconcile` | verbatim except namespace rename: `/lattice-wiki:scan` → `/graph-wiki:scan`, `/lattice-wiki:init` → `/graph-wiki:bootstrap`; "Layout drift detected" string is preserved verbatim (it matches `scan_monorepo.main`'s printed output) |
| `## In-repo docs` | verbatim except namespace rename: `/lattice-wiki:ingest` → `/graph-wiki:ingest`; the ingest-candidates example block is preserved verbatim |
| `## When to run` | verbatim except namespace rename: `/lattice-wiki:init` → `/graph-wiki:bootstrap`, `/lattice-wiki:lint` → `/graph-wiki:lint` |
| `## Skill Reference` | rename: `lattice-wiki/SKILL.md` → `graph-wiki/SKILL.md`; `lattice-wiki/references/scan-workflow.md` → `graph-wiki/references/scan-workflow.md` |

## Agent / skill rename map

- **Agent file:** `agents/scanner.md` — file name stays `scanner.md`; all namespace prose inside the file (`/lattice-wiki:scan`, `lattice-wiki/SKILL.md`, etc.) is rebranded to `graph-wiki` equivalents.
- **Skill:** `skills/lattice-wiki/SKILL.md` → `skills/graph-wiki/SKILL.md` — full file rename + namespace rebrand of all `/lattice-wiki:*` prose inside the file. (Cross-cutting rename; applies to all 6 ported commands.)
- **Skill reference doc:** `skills/lattice-wiki/references/scan-workflow.md` → `skills/graph-wiki/references/scan-workflow.md` — file rename; internal prose rebranded where it mentions `/lattice-wiki:scan`.
- **Script:** `skills/lattice-wiki/scripts/scan_monorepo.py` → `skills/graph-wiki/scripts/scan_monorepo.py` — shim retargeted per SO-02; the shim body imports `vault_io.scan_monorepo` instead of `lattice_wiki_core.scan_monorepo`.

## Reshape notes

No behavior changes vs upstream. Pure rename of namespace and import target. The clean-tree-on-main gate (referenced in upstream `scan.md` under `## What happens` step 5: "Bumps `last_sync_commit` to HEAD on confirmation — but only when the working tree is clean and HEAD is on `main`. Otherwise scan runs in read-only mode.") is preserved verbatim inside `vault_io.scan_monorepo.main` — no shim-level enforcement required. The `_config.py` backend selector seam is preserved per SO-04; the `bedrock` branch shells to `code-wiki-agent scan <args>`.

## Verification gate

Phase 14 confirms `/graph-wiki:scan` works by running the following smoke:

1. Use a workspace that has a freshly initialized wiki (from `/graph-wiki:bootstrap`) — e.g. `~/Personal/wiki/deep-agents`.
2. Ensure the working tree is clean and HEAD is on `main` (enables the full update path including `last_sync_commit` bump).
3. Run `/graph-wiki:scan` from that directory.
4. Verify output lists the expected packages (e.g. `vault-io`, `workspace-io`, `code-wiki-agent`, `eval-harness`) with their `new`, `unchanged`, or `renamed` diff status.
5. Verify `<workspace>/wiki/index.md` was updated and a `scan` entry was appended to `<workspace>/wiki/log.md`.
6. **Dirty-tree failure mode:** checkout a file, making the tree dirty, and re-run `/graph-wiki:scan`. Confirm it runs in read-only mode (no `last_sync_commit` bump) and does not error — this tests the verbatim preservation of the upstream clean-tree-on-main gate.
7. Optional: diff scan output against a fresh `/lattice-wiki:scan` run on the same repo (modulo brand string differences); expect structurally identical package listings.
