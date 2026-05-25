# Phase 13: Plugin Spec (M3a) - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md — this log preserves the alternatives considered.

**Date:** 2026-05-18
**Phase:** 13-plugin-spec-m3a
**Areas discussed:** Per-command shell-out target, Work-layer commands fate, Interactive UX preservation, Spec doc shape & location, Python path strategy, Port timing for missing modules, Backend selector config shape, Per-command spec template, Work-layer trio verdict (re-asked after reframe)

---

## Foundational reframe (turn 1 of substantive discussion)

Initial framing in the first AskUserQuestion (per-command shell-out target / interactive UX / spec shape) implicitly assumed the ported plugin would be a thin wrapper over `graph-wiki-agent` (Bedrock-backed). User interrupted and corrected:

> "At this time I do not want the plugin to use any of the bedrock inference. I want it to use Claude code (or whatever harness) for all inference. I am expecting the graph-wiki to be functionally identical to lattice-wiki. I don't have the code in front of me, so I can't look at how much of the lattice-wiki-core functionality was brought over and where it lives now, but maybe we need a new graph-wiki-core that both graph-wiki-agent and the scripts used by the graph-wiki plugin's scripts."

**Consequence:** Initial AskUserQuestion was rejected. Every subsequent question reframed around: plugin = Claude Code inference path, graph-wiki-agent = Bedrock path, two parallel surfaces over the same vault-io / workspace-io helpers. Saved to memory as `[[project_plugin_port_model]]` for future sessions.

---

## Script home — where do plugin shims get their Python deps?

| Option | Description | Selected |
|--------|-------------|----------|
| Plugin shims import directly from vault-io + workspace-io | `from vault_io.<x> import main`; no new package. Plugin uses `uv run --project` to pick up venv. | ✓ |
| New `graph-wiki-core` package that re-exports vault-io + workspace-io | Adds a thin re-export package; plugin imports `graph_wiki_core`. | |
| Move vault-io + workspace-io contents INTO new `graph-wiki-core` | Bigger refactor; collapses layered package shape from Phases 11–12. | |
| Plugin vendors its own copy of scripts | Duplicate code in plugin folder; no Python install dep at runtime. | |

**User's choice:** Plugin shims import directly from vault-io + workspace-io.
**Notes:** Avoids a new package shape; reuses the layered structure built in Phases 11–12. Compatible with the upstream shim pattern, just retargeted from `lattice_wiki_core` to `vault_io` / `workspace_io`.

---

## Missing modules — where do `lint_wiki` + `wiki_search` get added?

| Option | Description | Selected |
|--------|-------------|----------|
| Port both into vault-io as part of Phase 13 or Phase 14 | Treat like Phase 12 backports. Benefit graph-wiki-agent too. | ✓ |
| Port into the new shared package (only applicable if option B/C above) | N/A given previous answer. | |
| Plugin includes its own copies (no shared port) | Duplication; graph-wiki-agent's lint/query don't get the new modules. | |

**User's choice:** Port both into vault-io.
**Notes:** Specific phase placement (13 vs 14 vs 12-retroactive) clarified in the next question.

---

## Backend selector — strip or preserve?

| Option | Description | Selected |
|--------|-------------|----------|
| Strip the selector — plugin shims call vault-io directly, no backend branching | Simplest; plugin is Claude-only. | |
| Preserve the seam (backend=claude default; bedrock optional) | Keep upstream's `_config.py::backend_for` pattern. Future-flexible. | ✓ |

**User's choice:** Preserve the seam.
**Notes:** Default-claude in v1.2 matches the reframe; bedrock branch exists so a future user (or Pat himself) can flip a single command (e.g., big `/ingest`) to the cost-frontier path via config rather than re-architecture.

---

## Spec doc shape & location

| Option | Description | Selected |
|--------|-------------|----------|
| Single CONTRACT.md with a slash-command table | One auditable file; nine rows; columns per command. | |
| Per-command spec files | One file per command in `.planning/spec/13-plugin-contract/`. | ✓ |
| Spec block in CONTEXT.md only; no separate spec dir | Drop the `.planning/spec/` requirement entirely. | |

**User's choice:** Per-command spec files.
**Notes:** Layout will be `.planning/spec/13-plugin-contract/<cmd>.md` plus `CONTRACT-INDEX.md` and `SHELL-OUT-PATTERN.md` to factor out cross-cutting decisions. Six per-command files (drop verdict for the work-layer trio means no file).

---

## Python path strategy — how do plugin shims find vault-io?

| Option | Description | Selected |
|--------|-------------|----------|
| `uv run --project $DEEP_AGENTS_ROOT python3 ...` (env var) | One env var line in shell rc; uv resolves venv. | ✓ |
| Plugin auto-discovers the agent-research repo from cwd | Walk-up + marker detection; zero config happy path; more moving parts. | |
| Document a venv-activation prerequisite | Bare `python3`; user must activate venv first. | |

**User's choice:** `uv run --project $DEEP_AGENTS_ROOT`.
**Notes:** Single-user setup; env var is fine. Auto-discovery rejected as over-engineering for one developer.

---

## Port timing — where do `lint_wiki` + `wiki_search` ports land?

| Option | Description | Selected |
|--------|-------------|----------|
| Add a port step to Phase 14 (plugin port) | Phase 13 stays pure spec; Phase 14 ports the modules as first 2 plans. | ✓ |
| Add port plans to Phase 13 itself | Phase 13 does spec + 2 ports; bends roadmap's "M3a is spec only" framing. | |
| Add backport requirement to Phase 12 retroactively | Re-open Phase 12 (already verified and shipped). | |

**User's choice:** Add a port step to Phase 14.
**Notes:** Keeps Phase 13 as pure spec per its roadmap framing. Phase 14's plans will start with the 2 module ports before the plugin folder is created.

---

## Backend selector config shape

| Option | Description | Selected |
|--------|-------------|----------|
| `.graph-wiki.local.json` in the workspace (mirrors upstream verbatim) | Per-workspace file next to `.graph-wiki.yaml`. | |
| Add a `[plugin]` table to `.graph-wiki.yaml` | One file instead of two; tighter integration with workspace-io. | ✓ |
| Environment variable only (`GRAPH_WIKI_PLUGIN_BACKEND=bedrock`) | Simplest; loses per-command granularity. | |

**User's choice:** Add a `[plugin]` table to `.graph-wiki.yaml`.
**Notes:** Workspace-io's manifest schema grows in Phase 14 to expose the new block. Default-when-missing is `claude` everywhere.

---

## Per-command spec template — required sections

| Option | Description | Selected |
|--------|-------------|----------|
| Frontmatter: name, upstream source path, port verdict (rename/reshape/drop/defer) | Scannable header | ✓ |
| Shell-out contract: exact invocation + target module + args pass-through | Removes ambiguity at port time | ✓ |
| Prose-preservation map + agent/skill rename list | Locks markdown body verdicts per section | ✓ |
| Per-command verification gate (manual smoke or test) | How Phase 14 confirms each port works | ✓ |

**User's choice:** All four sections required.
**Notes:** Every per-command spec file in `.planning/spec/13-plugin-contract/` must have all four sections. Empty sections (e.g., "Reshape notes" when verdict=rename) are explicitly written as empty — proves the spec author considered them.

---

## Work-layer trio verdict (archive / regen-index / status)

| Option | Description | Selected |
|--------|-------------|----------|
| DROP — don't include the .md command files in plugins/graph-wiki/commands/ | Plugin only has 6 commands; verdict captured in CONTRACT-INDEX. | ✓ |
| DEFER — include the .md files but error with a helpful message | Preserves discoverability; tiny shim files. | |
| PASSTHROUGH — shell out to upstream lattice-wiki-core if installed | Dual-plugin assumption; user keeps work-layer via upstream. | |

**User's choice:** DROP.
**Notes:** Honest about scope. Phase 15+ may resurrect them when work/ subsystem is reconsidered. CONTRACT-INDEX.md records the drop verdict with `work/ out of v1.2 scope` rationale.

---

## Claude's Discretion

Areas where Claude exercises judgment without re-asking the user:

- Exact column order in `CONTRACT-INDEX.md` — readability over rigidity.
- Whether to split `SHELL-OUT-PATTERN.md` into two files (shell-out shape vs. rename map) or keep them bundled — depends on document length once written.
- Whether per-command spec files quote upstream verbatim or paraphrase + cite — either works; spec author's call per file.
- Whether to mention `defer` verdict in the vocabulary even though v1.2 doesn't use it — yes, kept for future phases.
- Whether `/graph-wiki:log` gets a tiny placeholder script — default to "no script" per upstream convention.

## Deferred Ideas

Ideas surfaced during discussion that belong in later phases (also captured in CONTEXT.md `<deferred>`):

- Work-layer subsystem port (Phase 15+ if ever reconsidered).
- `export_marp.py` port (never on a slash command; deferred indefinitely).
- Auto-discovery of `$DEEP_AGENTS_ROOT` (rejected for v1.2; revisit if plugin gets shared users).
- MCP-server-based plugin variant (v2.0 candidate).
- Per-command pricing telemetry in plugin shims (Phase 16 owns trace pipeline gaps).
- Plugin marketplace publish (v2.0 GA open-source release prep).
- Bedrock-branch smoke test coverage (Phase 14+ follow-up if seam gets used).
