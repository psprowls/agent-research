# Phase 13: Plugin Spec (M3a) - Context

**Gathered:** 2026-05-18
**Status:** Ready for planning

<domain>
## Phase Boundary

A locked, per-command contract surface for porting the upstream `lattice-wiki` Claude Code plugin into this repo as `plugins/graph-wiki/`. Phase 13 produces **specification artifacts only** — no plugin code is moved, no plugin scripts are written. The output is a directory of per-command spec files under `.planning/spec/13-plugin-contract/` that Phase 14 (M3b plugin port) can execute against without raising new design questions.

**Foundational reframe (2026-05-18):** the ported graph-wiki plugin is a **Claude-Code-host path** — its slash commands run inside Claude Code (or any equivalent Claude-side harness) and use Claude Code's own inference for LLM work, exactly like upstream lattice-wiki today. The plugin is **not** a thin wrapper around `graph-wiki-agent`. `graph-wiki-agent` (Bedrock-backed CLI + MCP server) stays as the separate, headless, cost-frontier surface. The plugin and graph-wiki-agent coexist as two parallel surfaces over the same underlying Python helper modules in `vault-io` / `workspace-io`. graph-wiki must be **functionally identical** to lattice-wiki under the new brand.

**In scope:**
- `.planning/spec/13-plugin-contract/` — new directory containing one spec file per ported slash command (6 files; the 3 work-layer commands are explicitly marked DROP).
- A `.planning/spec/13-plugin-contract/CONTRACT-INDEX.md` index that lists all 9 upstream commands, their verdicts (`rename` / `reshape` / `drop`), and links to each per-command spec file.
- A `.planning/spec/13-plugin-contract/SHELL-OUT-PATTERN.md` cross-cutting decisions doc: the `uv run --project $DEEP_AGENTS_ROOT python3 ...` invocation shape, the env-var-based agent-research discovery, the `[plugin]` table additions to `.graph-wiki.yaml`, the backend selector seam, and the agent/skill rename map.
- PROJECT.md Key Decisions entry locking the contract surface (so Phase 14 has no open wiring questions).
- An updated REQUIREMENTS.md note that `lint_wiki.py` + `wiki_search.py` MUST be ported into `vault-io` as a prerequisite step inside Phase 14 (before the plugin's `/lint` and `/query` shims can shell out cleanly).

**Out of scope (delegated to Phase 14 or excluded):**
- Actually copying the upstream plugin into `plugins/graph-wiki/` (Phase 14).
- Renaming the plugin id, command namespace, agent/skill names in checked-in files (Phase 14 executes the renames per the rename map captured here).
- Porting `lint_wiki.py` and `wiki_search.py` to `vault-io` (Phase 14, as the first step of the port).
- Implementing the work-layer subsystem — `work/`, `archive_work`, `lint_work`, `regenerate_work_index`, `work_status`, `ingest_work_item` (PROJECT.md: explicitly out of v1.2; PROJECT.md note: GSD covers work-item lifecycle).
- Porting `export_marp.py` (internal-only upstream module; no slash command references it; deferred indefinitely).
- Touching `graph-wiki-agent` or `graph-wiki-mcp` to integrate them with the plugin in any way.
- Wiki self-update against the rebranded codebase (Phase 15, BRAND-03).

</domain>

<decisions>
## Implementation Decisions

### Inference path & functional parity

- **P-01 (Plugin runs on Claude Code inference, NOT Bedrock.):** The ported graph-wiki plugin's LLM work — discussion checkpoints in `/ingest`, librarian synthesis in `/query`, scanner per-package review in `/scan`, semantic lint pass 2 in `/lint`, ingestor write-out — all happens via the host Claude Code session, same as upstream lattice-wiki today. There are no calls from plugin slash commands into `graph-wiki-agent` or any Bedrock inference path during normal operation (see P-02 backend selector for the optional seam).
- **P-02 (Backend selector seam preserved, claude default, bedrock optional.):** Upstream's `_config.py::backend_for(cmd)` selector survives the port. graph-wiki defaults to `backend = "claude"` for every command; users can opt into `backend = "bedrock"` per-command (which routes that one command's heavy LLM work into a `graph-wiki-agent` subprocess instead of doing it inline in the Claude Code session). The seam exists so a future user who wants the cost-frontier path for one expensive operation (e.g., a big `/ingest`) can flip a flag without re-architecting. **Default for v1.2 is claude-everywhere; bedrock is the documented opt-in.**
- **P-03 (graph-wiki is functionally identical to lattice-wiki under the new brand.):** Same 9 slash commands' user-facing behavior, same iron rules, same checkpoints, same layout block, same frontmatter schema, same log entry format, same agent boundaries. The port is a rename + rewiring exercise, NOT a feature redesign. If a port choice would change behavior, the spec calls it out explicitly with rationale.

### Per-command verdict & shell-out target

(Detailed shell-out contracts, prose-preservation maps, and rename lists are written in the per-command spec files under `.planning/spec/13-plugin-contract/`. Summary table below — the spec is the source of truth.)

| # | Upstream cmd | Target script (in `plugins/graph-wiki/skills/graph-wiki/scripts/`) | Target Python module | Verdict | One-line rationale |
|---|---|---|---|---|---|
| 1 | `/lattice-wiki:init` | `init_vault.py` (shim) | `vault_io.init_vault.main` + `vault_io.detect_containers.main` (pre-step) | `rename` | Direct mapping; detection sub-step preserved verbatim. |
| 2 | `/lattice-wiki:scan` | `scan_monorepo.py` (shim) | `vault_io.scan_monorepo.main` | `rename` | Direct mapping; clean-tree-on-main gate preserved. |
| 3 | `/lattice-wiki:ingest` | `ingest_source.py` (shim) | `vault_io.ingest_source.main` | `rename` | source-ingest only; work-item ingest is dropped per work-layer scope. |
| 4 | `/lattice-wiki:lint` | `lint_wiki.py` (shim) | `vault_io.lint_wiki.main` (port required) + `vault_io.graph_analyzer.main` | `reshape` | Mechanical pass 1 + semantic pass 2 preserved; work-lint pass 1b dropped (no work-layer). |
| 5 | `/lattice-wiki:query` | `wiki_search.py` (shim, BM25 fallback) | `vault_io.wiki_search.main` (port required) | `rename` | LLM-driven; only the BM25 fallback shells out to Python. |
| 6 | `/lattice-wiki:log` | (no script; pure prose) | (none — `grep + tail` against `<workspace>/wiki/log.md`) | `rename` | Mirrors upstream: command is prose-only. Just rename namespace + path strings. |
| 7 | `/lattice-wiki:archive` | — | — | `drop` | Work-layer out of v1.2 scope (PROJECT.md). |
| 8 | `/lattice-wiki:regen-index` | — | — | `drop` | Work-layer out of v1.2 scope (PROJECT.md). |
| 9 | `/lattice-wiki:status` | — | — | `drop` | Work-layer out of v1.2 scope (PROJECT.md). |

- **C-01 (6 commands ported, 3 dropped — total: 6 in `plugins/graph-wiki/commands/`.):** No `.md` file is written for the 3 work-layer commands; they don't exist in graph-wiki's command surface. Verdict `drop` in the per-command index means "no file in the port." Users running `/graph-wiki:` autocomplete will not see them. The verdict vocabulary is `rename` / `reshape` / `drop` / `defer` — only `defer` would mean "file ships but errors out" (no command uses that in v1.2).
- **C-02 (Verdict definitions are part of the spec:** `rename` = byte-for-byte text swap of upstream slash and module references; `reshape` = command behavior changes (e.g., `/lint` loses its work-layer pass 1b); `drop` = no port; `defer` = port the markdown but disable execution until a later phase. Locked in `.planning/spec/13-plugin-contract/CONTRACT-INDEX.md`.

### Shell-out invocation shape (cross-cutting)

- **SO-01 (uv run with `$DEEP_AGENTS_ROOT` env var.):** Every ported plugin script in `plugins/graph-wiki/skills/graph-wiki/scripts/` is invoked as:
  ```bash
  uv run --project "$DEEP_AGENTS_ROOT" python3 "${CLAUDE_PLUGIN_ROOT}/skills/graph-wiki/scripts/<x>.py" "$@"
  ```
  User sets `DEEP_AGENTS_ROOT` once in shell rc (e.g., `export DEEP_AGENTS_ROOT=/Users/pat/Personal/agent-research`). `uv run --project` resolves the agent-research venv and makes `vault_io` + `workspace_io` importable without the user needing to activate a venv manually. Single-user-setup-friendly; no per-cwd discovery logic to maintain.
- **SO-02 (Shim contents — the upstream pattern, retargeted.):** Each script file is a shim:
  ```python
  #!/usr/bin/env python3
  """Plugin shim for <cmd> — dispatches to vault_io (claude backend) or graph_wiki_agent (bedrock backend)."""
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
          # Subprocess into graph-wiki-agent for this command
          import subprocess
          subprocess.run(["graph-wiki-agent", "<cmd>", *sys.argv[1:]], check=True)
      else:
          _core_main()


  if __name__ == "__main__":
      main()
  ```
  Mirrors upstream's shim structure (verified in `/Users/pat/Personal/lattice/plugins/lattice-wiki/skills/lattice-wiki/scripts/init_vault.py`), with two changes: (1) import from `vault_io` instead of `lattice_wiki_core`, (2) bedrock branch shells to `graph-wiki-agent` CLI instead of importing `lattice_wiki_agent`.
- **SO-03 (Backend selector config — `[plugin]` table inside `.graph-wiki.yaml`.):** Instead of upstream's separate `.lattice-wiki.json`, graph-wiki adds a `[plugin]` section to the existing workspace manifest:
  ```yaml
  plugin:
    backend_default: claude
    backend_overrides:
      ingest: bedrock   # optional, per-command
  ```
  Lives next to all other workspace settings. `workspace_io.manifest.read` is extended to expose the `[plugin]` block (Phase 14 task). Default-when-missing: `claude` everywhere.
- **SO-04 (`_config.py` in the plugin scripts dir.):** A small helper module `plugins/graph-wiki/skills/graph-wiki/scripts/_config.py` exposes `backend_for(cmd, repo=None) -> Literal["claude", "bedrock"]`. It reads `.graph-wiki.yaml` (via `workspace_io.manifest.read`) and returns the resolved backend. Mirrors upstream's `_config.py` shape; rewires the read to the new manifest path.

### Spec doc shape (`.planning/spec/13-plugin-contract/`)

- **SP-01 (Per-command files, one per ported command, plus index + cross-cutting doc.):**
  ```
  .planning/spec/13-plugin-contract/
  ├── CONTRACT-INDEX.md          # verdict table for all 9 upstream commands + links
  ├── SHELL-OUT-PATTERN.md       # SO-01..SO-04 in one place; agent/skill rename map
  ├── init.md
  ├── scan.md
  ├── ingest.md
  ├── lint.md
  ├── query.md
  └── log.md
  ```
  No file written for archive / regen-index / status — their verdict is `drop`, captured in CONTRACT-INDEX.md with rationale.
- **SP-02 (Per-command spec file template, MANDATORY sections.):**
  ```markdown
  ---
  command: <cmd>                                  # e.g., init
  upstream_source: plugins/lattice-wiki/commands/<cmd>.md
  port_verdict: rename | reshape | drop | defer
  ---

  # /graph-wiki:<cmd> — Port Spec

  ## Shell-out contract
  - Invocation: `uv run --project "$DEEP_AGENTS_ROOT" python3 "${CLAUDE_PLUGIN_ROOT}/skills/graph-wiki/scripts/<x>.py" $ARGUMENTS`
  - Target module: `vault_io.<module>.main` (claude backend) | `graph-wiki-agent <cmd>` (bedrock backend)
  - Args pass-through: <list of CLI flags, mapped 1:1 to upstream where possible; any reshape called out>
  - Pre-step (if any): <e.g., `vault_io.detect_containers.main --json` for /init>

  ## Prose-preservation map
  Section-by-section verdict for the slash command's markdown body:
  - `## Usage` — verbatim except namespace rename (`/lattice-wiki:` → `/graph-wiki:`)
  - `## What happens` — <verbatim | reshape: ...>
  - `## Sub-agent` — verbatim except agent name (e.g., `scanner` stays; rebrand prose inside)
  - <any other sections>

  ## Agent / skill rename map
  - Agent file: `agents/scanner.md` — name stays, namespace prose rebranded (lattice-wiki → graph-wiki)
  - Skill: `skills/lattice-wiki/SKILL.md` → `skills/graph-wiki/SKILL.md` — rename + namespace rebrand
  - <command-specific agent/skill touches>

  ## Reshape notes (if verdict != rename)
  <Concrete behavior changes vs upstream, with one-line rationale each. Empty if pure rename.>

  ## Verification gate
  How Phase 14 confirms this command works end-to-end. Lightweight — manual smoke or pytest:
  - Example: `/graph-wiki:bootstrap --topic "test" --tool claude-code` in an empty dir produces a wiki/ tree byte-identical to upstream output (diff against captured baseline).
  ```
- **SP-03 (CONTRACT-INDEX.md is the single auditable summary.):** One markdown table, 9 rows (all upstream commands), columns: command / upstream source path / verdict / target script / target module / one-line rationale / per-command spec file link. Phase 14's executor scans this one file to know what to do.
- **SP-04 (SHELL-OUT-PATTERN.md owns the cross-cutting decisions.):** SO-01..SO-04 captured here in one place so per-command files can just say "see SHELL-OUT-PATTERN.md §SO-01" without repeating boilerplate. Also houses the agent/skill rename map for files NOT command-specific (e.g., `skills/lattice-wiki/SKILL.md` → `skills/graph-wiki/SKILL.md`; `agents/{scanner,librarian,linter,ingestor}.md` rebrand prose).
- **SP-05 (PROJECT.md Key Decisions entry mirrors the lock.):** Per Phase 13 SC#3, the contract surface is locked in PROJECT.md Key Decisions (or "Validated") log with one-paragraph summary pointing at `.planning/spec/13-plugin-contract/CONTRACT-INDEX.md`. Phase 14 reads PROJECT.md as part of its standard `load_prior_context` and the lock survives any future re-planning.

### vault-io prerequisite ports (`lint_wiki` + `wiki_search`)

- **VP-01 (Both modules are Phase 14 work, not Phase 13.):** Phase 13 ships pure spec — no code lands in vault-io as part of this phase. The Phase 13 spec records that:
  - `lint_wiki.py` (~508 LOC upstream) must be ported into `packages/vault-io/src/vault_io/lint_wiki.py` as Plan 1 of Phase 14, with tests, before the `/graph-wiki:lint` shim can shell out.
  - `wiki_search.py` (~194 LOC upstream) must be ported into `packages/vault-io/src/vault_io/wiki_search.py` as Plan 2 of Phase 14, with tests, before `/graph-wiki:query`'s BM25 fallback works.
- **VP-02 (Same shape as Phase 12 backports.):** Apply the Phase 12 SR-01 rubric — bug fixes, helper extractions, behavior-preserving refactors all come over verbatim. Mirror upstream module shape (`main()` entry point, CLI argparse, returns structured result). Add to vault-io's `pyproject.toml` if it gains new console scripts (likely not — they're shims, called via `python3 <path>`).
- **VP-03 (BRAND-04 grep gate already covers these:** Once ported, both files participate in the `scripts/check-brand.sh` gate established in Phase 12 — they must rename `lattice` → `graph-wiki` in identifiers and prose during the port. Standard Phase 12 sweep behavior.
- **VP-04 (Both modules unblock the eval-harness too.):** Side benefit — `graph-wiki-agent lint` and `graph-wiki-agent query` can use these modules through their existing role-prompt paths once ported. Not a Phase 13 commitment; just worth noting that the port pays back in both surfaces.

### Plugin discovery & runtime requirements

- **PD-01 (`$DEEP_AGENTS_ROOT` env var is the only required user config.):** Documented in `plugins/graph-wiki/README.md` (Phase 14 will author this). README also notes the `[plugin]` block syntax for backend overrides and the work-layer commands' absence.
- **PD-02 (`$CLAUDE_PLUGIN_ROOT` is auto-set by Claude Code at slash-command invocation.):** Same convention upstream uses; no Phase 13/14 work — just verified.
- **PD-03 (uv must be installed.):** Same prerequisite as the rest of the agent-research monorepo; documented in the plugin README. No fallback to bare `python3` — that would break the `from vault_io` import.

### Claude's Discretion

- Exact column order in `CONTRACT-INDEX.md` — readability over rigidity.
- Whether to split `SHELL-OUT-PATTERN.md` into two files (one for shell-out shape, one for rename map) or keep them bundled — executor's call once the file gets long enough to split.
- The verbatim text the per-command spec files quote from each upstream `<cmd>.md` — verbatim copy of upstream's relevant section is fine; or paraphrase + cite. Either keeps Phase 14 unblocked.
- Whether to mention `defer` verdict in the verdict vocab if v1.2 doesn't use it — yes, keep it documented for future phases (Phase 15+ may resurrect work-layer commands).
- Whether `/graph-wiki:log` gets a tiny placeholder script (`log.py` that just does `grep + tail` so users don't have to type it) — executor judgment; upstream has no script, so default to "no script."

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Phase scope & planning artifacts
- `.planning/ROADMAP.md` §Phase 13 — phase goal, success criteria, dependency on Phase 12, requirement mapping (PLUGIN-01).
- `.planning/ROADMAP.md` §Phase 14 — downstream phase consuming this spec; success criteria spell out what the spec must unblock (plugin id rename, namespace rename, vault-io routing, end-to-end /graph-wiki:query smoke).
- `.planning/REQUIREMENTS.md` — full text for PLUGIN-01 (spec completes the open question), and PLUGIN-02..05 (downstream Phase 14 requirements the spec must enable).
- `.planning/PROJECT.md` §Current Milestone "M3 — plugin port" — captures the open question Phase 13 closes; "Explicitly out of v1.2" enumerates work-layer subsystem exclusion (drives the C-01 drop verdict on archive/regen-index/status).
- `.planning/threads/next-milestone-planning.md` §"M3 — Bring `lattice-wiki` plugin into `plugins/graph-wiki/`" — the original M3 framing with the carry-forward open question that Phase 13 resolves.
- `.planning/phases/11-workspace-io-port-m1/11-CONTEXT.md` — Phase 11 decisions on env var name (`GRAPH_WIKI_WORKSPACE`), manifest filename (`.graph-wiki.yaml`), delegation shim shape; Phase 13 builds on these (`[plugin]` table lives in the same manifest).
- `.planning/phases/12-drift-backport-ecosystem-rebrand-m2/12-CONTEXT.md` — Phase 12 decisions on PORT-vs-LEAVE rubric (SR-01..03); VP-02 mirrors that rubric for the lint_wiki/wiki_search ports.
- `.planning/spikes/002-lattice-drift-inventory/README.md` §Investigation A — drift map identifying `lint_wiki.py` and `wiki_search.py` as upstream-only modules. Allowlisted from BRAND-04 (per Phase 12 R-03).

### Upstream plugin & helpers being ported (read-only references)
- `/Users/pat/Personal/lattice/plugins/lattice-wiki/.claude-plugin/plugin.json` — plugin metadata; the canonical source for Phase 14's plugin.json rename.
- `/Users/pat/Personal/lattice/plugins/lattice-wiki/CLAUDE.md` — plugin-level guidance prose; rename + rebrand input for Phase 14.
- `/Users/pat/Personal/lattice/plugins/lattice-wiki/README.md` — plugin README; rebrand input for Phase 14.
- `/Users/pat/Personal/lattice/plugins/lattice-wiki/commands/{archive,ingest,init,lint,log,query,regen-index,scan,status}.md` — the 9 upstream slash command files. Phase 13 spec files quote/cite these per-command.
- `/Users/pat/Personal/lattice/plugins/lattice-wiki/agents/{ingestor,librarian,linter,scanner}.md` — the 4 sub-agents the slash commands dispatch. Rename map in SHELL-OUT-PATTERN.md covers these.
- `/Users/pat/Personal/lattice/plugins/lattice-wiki/skills/lattice-wiki/{README.md,SKILL.md}` — the skill that backs the plugin commands. Renamed wholesale to `graph-wiki/` in Phase 14.
- `/Users/pat/Personal/lattice/plugins/lattice-wiki/skills/lattice-wiki/references/` — supporting reference docs the agents read. Inventory and rename map captured in Phase 13 spec.
- `/Users/pat/Personal/lattice/plugins/lattice-wiki/skills/lattice-wiki/scripts/_config.py` — upstream backend selector; SO-04 retargets this verbatim with a new manifest read.
- `/Users/pat/Personal/lattice/plugins/lattice-wiki/skills/lattice-wiki/scripts/init_vault.py` — canonical example of the shim shape; SO-02 retargets this pattern for every ported script.
- `/Users/pat/Personal/lattice/plugins/lattice-wiki/skills/lattice-wiki/scripts/{scan_monorepo,ingest_source,lint_wiki,wiki_search}.py` — additional shim references (each one a slim dispatcher into `lattice_wiki_core`).
- `/Users/pat/Personal/lattice/packages/lattice-wiki-core/src/lattice_wiki_core/lint_wiki.py` — ~508 LOC; port source for VP-01.
- `/Users/pat/Personal/lattice/packages/lattice-wiki-core/src/lattice_wiki_core/wiki_search.py` — ~194 LOC; port source for VP-01.

### Existing agent-research code referenced by the spec
- `packages/vault-io/src/vault_io/{init_vault,scan_monorepo,ingest_source,detect_containers,layout_io,append_log,git_state,graph_analyzer,update_index,update_tokens}.py` — every shim's `claude` branch imports from these. Spec contracts call these out per-command.
- `packages/vault-io/src/vault_io/lint/*.py` — `/graph-wiki:lint`'s mechanical pass 1 dispatches lint rule modules from here.
- `packages/workspace-io/src/workspace_io/manifest.py` — Phase 14 extends this to read the new `[plugin]` block (SO-03). Phase 13 spec calls out the extension; Phase 14 implements it.
- `packages/workspace-io/src/workspace_io/config.py` — `GraphWikiConfig.resolve()` already discovers the workspace from cwd; `_config.py` in the plugin scripts uses it to find the manifest.
- `agents/graph-wiki-agent/src/graph_wiki_agent/cli.py` — the bedrock-branch subprocess target (SO-02); spec asserts the CLI surface remains `graph-wiki-agent <cmd> <args>` so plugin shims can shell to it without translation.
- `CLAUDE.md` — Python 3.11+, uv workspace, MCP stdio convention. Phase 13 spec does not need to change CLAUDE.md (Phase 12 already landed rebrand changes); Phase 14 will add a graph-wiki plugin section.
- `scripts/check-brand.sh` + `.brand-grep-allow` — Phase 12 gate; lint_wiki + wiki_search ports must clear this gate when added in Phase 14.

### Project-level constraints
- `.planning/PROJECT.md` §"Explicitly out of v1.2" — work/ subsystem out; package-family monorepo out; vault-io-ahead modules out. Drives C-01 drop verdicts.
- Memory `[[project_plugin_port_model]]` — captures the Claude-Code-inference-only reframe (2026-05-18); load-bearing context for the whole spec.
- Memory `[[user_lattice_wiki_author]]` — Pat built lattice-wiki; trust his "port verbatim" calls. Drives P-03 (functional parity).
- Memory `[[project_wiki_setup]]` — agent-research wiki at `~/Personal/graph-wiki/agent-research`; the future Phase 15 self-update target. Phase 13 spec doesn't touch this; just notes it as the consumer of a working plugin.

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- **Upstream plugin shim shape** (`/Users/pat/Personal/lattice/plugins/lattice-wiki/skills/lattice-wiki/scripts/init_vault.py`) — every plugin script in the port follows this exact pattern, just retargeted. Read once, copy 6 times, change the imports and the bedrock branch.
- **Phase 11 delegation shim pattern** (`packages/vault-io/src/vault_io/_workspace.py`) — proves the "thin shim that imports from a sibling package" works inside this monorepo. The plugin shims are the same idea, just out-of-tree (in `plugins/`).
- **Phase 12 `scripts/check-brand.sh` + `.brand-grep-allow`** — Phase 14's rename pass for the plugin folder reuses this gate verbatim. No new infrastructure needed.
- **`workspace_io.manifest.read()`** — already parses `.graph-wiki.yaml`; extending it to surface a `[plugin]` block is a small add (Phase 14, not 13).
- **`workspace_io.config.resolve()`** — already walks up from cwd to discover the workspace. The plugin shims call this for path resolution before delegating to the chosen backend.
- **Phase 11 D-02 (two-tier passthrough at the MCP boundary)** — same pattern applies to the plugin: shim is the boundary, backend implementation (vault-io vs graph-wiki-agent) is the back-end. No semantic change.

### Established Patterns
- **One spec doc per phase that locks a contract surface.** Phase 11 used PROJECT.md Key Decisions; Phase 12 used `packages/vault-io/DRIFT-DECISIONS.md`; Phase 13 uses `.planning/spec/13-plugin-contract/`. Same shape, new directory convention.
- **Per-row verdict vocabulary.** Phase 12 used PORT/LEAVE-AHEAD/LEAVE-ARCH/LEAVE-COSMETIC/IDENTICAL. Phase 13 uses rename/reshape/drop/defer — fewer rows (9 commands vs. 11 modules), simpler vocab.
- **Provenance comments.** Phase 11/12 used `# Source: / # Anchor: / # Source-commit:` headers for ported helpers. VP-01 ports (lint_wiki, wiki_search) follow the same pattern when ported in Phase 14.
- **Atomic per-file commits during a sweep.** Phase 11/12's SQ-02 pattern — one commit per surface. Phase 14 will follow same shape for the plugin port; Phase 13 spec writes are 1–2 commits (spec dir + PROJECT.md key-decisions entry).

### Integration Points
- **`.graph-wiki.yaml` manifest** — Phase 13 spec calls out the new `[plugin]` block; Phase 14 extends `workspace_io.manifest` to surface it. No schema change committed in Phase 13.
- **`graph-wiki-agent` CLI surface** — Phase 13 spec assumes today's CLI commands (`init`, `scan`, `ingest source`, `ingest work-item`, `lint`, `query`, `log`) are the bedrock-branch targets. If a future phase reshapes that CLI, the plugin's bedrock branch needs an update too. Captured as Phase 14's smoke-test responsibility.
- **`$DEEP_AGENTS_ROOT` env var** — new convention; documented in plugin README (Phase 14). No code in this repo needs to know about it; only the plugin shims.
- **No new MCP boundary changes.** Plugin doesn't use MCP at all. graph-wiki-mcp stays where it is.
- **No graph-wiki-agent changes required.** Phase 13's spec doesn't ask graph-wiki-agent to change shape. Phase 14's plugin port doesn't either — the bedrock branch shells to today's CLI.

</code_context>

<specifics>
## Specific Ideas

- **The reframe is the most important fact:** plugin = Claude Code inference, full stop. Every prior framing that imagined the plugin as a wrapper over graph-wiki-agent is wrong. Two surfaces, not one wrapping the other.
- **Preserve the backend selector seam (P-02)** even though we default `claude` everywhere in v1.2. Pat may later want to flip `ingest` to bedrock for a giant source dump; the wiring exists so that's a config change, not a re-architecture.
- **Single env var (`DEEP_AGENTS_ROOT`)** is the only user setup ask. Documented in the plugin README; no auto-discovery walk-up logic in v1.2 (rejected because it adds moving parts for a single-developer project where one env var line in shell rc is fine).
- **`$CLAUDE_PLUGIN_ROOT`** stays as the in-plugin-relative anchor — same as upstream. Means the plugin can be installed to any Claude Code plugin path without further config.
- **`/graph-wiki:log` has no script** — same as upstream lattice-wiki's `/lattice-wiki:log`. Just a rename of namespace + path strings in the prose. Trivial port; included for parity completeness.
- **The 3 work-layer commands are DROPPED, not deferred** — they don't ship a markdown file at all in `plugins/graph-wiki/commands/`. Phase 15 (or later) may resurrect them when work/ is reconsidered.
- **`export_marp.py` is invisible to the spec** — it's not on any slash command in upstream. Out of scope by virtue of not appearing in the surface area. No verdict needed.
- **The two missing modules** (`lint_wiki`, `wiki_search`) are Phase 14 work, not Phase 13. Phase 13 just records the prerequisite. This keeps Phase 13 as pure spec per its roadmap framing.
- **PROJECT.md Key Decisions gets a new entry** mirroring the spec lock — Phase 13 SC#3 ("contract surface is locked in PROJECT.md Key Decisions").

</specifics>

<deferred>
## Deferred Ideas

- **Work-layer subsystem port** — out of v1.2 entirely; would unblock /graph-wiki:archive, /regen-index, /status if revisited. Decision: GSD covers work-item lifecycle per thread decision 2026-05-17. Future phase if ever reconsidered.
- **`export_marp.py` port** — never on a slash command; no immediate user need. Deferred indefinitely; could land if Pat wants Marp slide export inside graph-wiki later.
- **Auto-discovery of `$DEEP_AGENTS_ROOT` from cwd** — rejected for v1.2 in favor of explicit env var. Could revisit if the plugin gets shared with other users who haven't set their shell rc up.
- **MCP-server-based plugin variant** — currently the plugin shells to Python scripts. A future variant could expose graph-wiki commands as MCP tools (so plugin authors don't need `$DEEP_AGENTS_ROOT` at all — they'd configure `graph-wiki-mcp` as an MCP server). Out of scope for v1.2; would require treating graph-wiki-mcp as a tool dependency of the plugin. Worth revisiting in v2.0.
- **Per-command pricing / cost telemetry in the plugin shims** — bedrock-branch invocations could log to the same trace pipeline as graph-wiki-agent. Out of v1.2 scope (trace pipeline gaps owned by Phase 16, TRACE-FU-01).
- **Plugin auto-install from this monorepo** — could publish to a Claude Code plugin marketplace eventually. Out of v1.2 (open-source release prep deferred to v2.0 GA per PROJECT.md).
- **Bedrock-branch test coverage** — Phase 14 verification per command is claude-branch only by default (since that's the v1.2 default). Adding bedrock-branch smoke tests is a useful follow-up if Pat ever exercises the seam.

</deferred>

---

*Phase: 13-plugin-spec-m3a*
*Context gathered: 2026-05-18*
