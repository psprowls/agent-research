# Phase 14: Plugin Port (M3b) - Context

**Gathered:** 2026-05-18
**Status:** Ready for planning

<domain>
## Phase Boundary

Execute the locked Phase 13 contract: port the upstream `lattice-wiki` Claude Code plugin into this repo as `plugins/graph-wiki/`, against the deep-agents vault, with zero `lattice_*` imports and at least one slash command (`/graph-wiki:query`) running end-to-end against `~/Personal/wiki/deep-agents`. The plugin runs on Claude Code inference (P-01) — it is **not** a wrapper around `graph-wiki-agent`; the two coexist as parallel surfaces over the same `vault-io` / `workspace-io` helpers.

**In scope:**
- Port `vault_io.lint_wiki` from upstream `lattice_wiki_core/lint_wiki.py` (~508 LOC) into `packages/vault-io/src/vault_io/lint_wiki.py` per VP-01 / SR-01 rubric (Plan 1).
- Port `vault_io.wiki_search` from upstream `lattice_wiki_core/wiki_search.py` (~194 LOC) into `packages/vault-io/src/vault_io/wiki_search.py` per VP-01 / SR-01 rubric (Plan 2).
- Extend `workspace_io.manifest` to surface the `[plugin]` block from `.graph-wiki.yaml` (SO-03), strict-raises on unknown keys.
- Scaffold `plugins/graph-wiki/` by copying upstream `plugins/lattice-wiki/` and rebranding: plugin id, plugin.json metadata (version reset to 0.1.0), CLAUDE.md, fresh-write README, `.claude-plugin/` metadata, agents/{ingestor,librarian,linter,scanner}.md prose rebrand, `skills/lattice-wiki/` → `skills/graph-wiki/` folder rename, 6 ported command markdown files (init, scan, ingest, lint, query, log), 5 shim scripts in `skills/graph-wiki/scripts/` (no script for `log`).
- Drop archive/regen-index/status — no `.md` files in `plugins/graph-wiki/commands/` (C-01).
- Implement `plugins/graph-wiki/skills/graph-wiki/scripts/_config.py` per SO-04 (reads `[plugin]` block via `workspace_io.manifest.read`).
- Shim script bodies per SO-02: import from `vault_io.<module>`, dispatch on backend (`claude` default → call `_core_main()`; `bedrock` opt-in → subprocess to `graph-wiki-agent <cmd>`).
- Smoke gate: manual `/graph-wiki:query` run against `~/Personal/wiki/deep-agents` from a Claude Code session; full transcript pasted into `14-VERIFICATION.md` as a fenced block (SC#4).
- Cross-cutting brand sweep: every `lattice` → `graph-wiki` rename inside `plugins/graph-wiki/` and the two new `vault-io` files must clear `scripts/check-brand.sh` (BRAND-04 / VP-03).

**Out of scope:**
- Re-opening any Phase 13 decision (P-01..P-03, C-01..C-02, SO-01..SO-04, SP-01..SP-05, VP-01..VP-04, PD-01..PD-03 are locked; per-command spec files are the source of truth).
- Bedrock-branch smoke tests (deferred per Phase 13 deferred list; v1.2 default is claude everywhere).
- Wiki self-update against the rebranded codebase (Phase 15, BRAND-03).
- Trace pipeline / sweep / MCP-cancel / model-config debt (Phase 16).
- Work-layer subsystem revival — archive/regen-index/status stay dropped.
- Any change to `graph-wiki-agent` or `graph-wiki-mcp` shape — the bedrock-branch subprocess target is today's CLI surface; if it ever reshapes, that's a follow-up phase.
- `export_marp.py` — not on any slash command, no port.
- New tests for `graph-wiki-agent lint` / `graph-wiki-agent query` to use the new `vault_io.lint_wiki` / `vault_io.wiki_search` modules (mentioned as a side-benefit in VP-04 but not a Phase 14 commitment).

</domain>

<decisions>
## Implementation Decisions

### Plan structure

- **D-01 (3-plan slice, single bundled plugin-port plan):** Phase 14 ships as 3 plans:
  - **Plan 1** — Port `vault_io.lint_wiki` (verbatim per VP-01/SR-01; clears BRAND-04 grep gate; tests ported alongside).
  - **Plan 2** — Port `vault_io.wiki_search` (verbatim per VP-01/SR-01; clears BRAND-04 grep gate; tests ported alongside).
  - **Plan 3** — Bundled plugin port: extend `workspace_io.manifest` with strict-raises `[plugin]` block support (per D-02 below) → scaffold `plugins/graph-wiki/` from upstream → rebrand plugin.json (per D-03 below) + CLAUDE.md + README (per D-04 below) → rewrite 5 shim scripts per SO-02 → add `_config.py` per SO-04 → rename agents/skills per SHELL-OUT-PATTERN.md rename map → execute SC#4 manual smoke and capture transcript (per D-05 below). Plans 1 and 2 are independent and can parallelize; Plan 3 depends on both. The bundle keeps the plugin port atomic in one SUMMARY family and minimizes inter-plan handoff overhead — matches the user's preference for fewer larger plans on this kind of port-and-rebrand work.

### `[plugin]` block validation in `workspace_io.manifest`

- **D-02 (Strict-raises validation, matches Phase 11 D-14):** `workspace_io.manifest.read` is extended to recognise a top-level `plugin:` block (per SO-03). Known keys:
  - `backend_default: Literal["claude", "bedrock"]` — defaults to `"claude"` when block is missing.
  - `backend_overrides: dict[str, Literal["claude", "bedrock"]]` — defaults to `{}` when block is missing.
  Unknown keys inside the `plugin:` block **raise** (consistent with Phase 11 D-14's strict-raises philosophy for shape-defining manifest keys). Unknown values for the two known keys also raise. Future schema extensions land via explicit code change + manifest version bump, not silent acceptance — drift is visible in code review.

### `plugin.json` metadata

- **D-03 (Version reset to 0.1.0; copy-edited description with parallel-surface note):**
  - `name`: `"graph-wiki"`
  - `version`: `"0.1.0"` (new package identity — not a continuation of upstream's `0.5.2` lineage; signals separate publish history)
  - `author`: preserved from upstream (`"Patrick Sprowls"`)
  - `license`: preserved (`"MIT"`)
  - `description`: copy-edited from upstream prose with `lattice-wiki` → `graph-wiki` swap **plus** a one-line note that this is the Claude Code host path and `graph-wiki-agent` is the Bedrock companion surface.
  - `keywords`: copied from upstream; no additions (no new positioning to surface in v1.2).
  - `env`: rename `LATTICE_WIKI_ROOT` → `GRAPH_WIKI_ROOT`, value stays `${CLAUDE_PLUGIN_ROOT}` (in-plugin anchor; PD-02 covers `$CLAUDE_PLUGIN_ROOT` provenance).

### README content

- **D-04 (Fresh-write, graph-wiki-specific focus):** `plugins/graph-wiki/README.md` is **not** a copy of upstream. Authored fresh to cover only what differs:
  - **What this plugin is** (one paragraph: Claude Code host path; companion to `graph-wiki-agent` Bedrock CLI; same wiki surface).
  - **Setup** — `$DEEP_AGENTS_ROOT` env var export (PD-01); `uv` prerequisite (PD-03); `$CLAUDE_PLUGIN_ROOT` is auto-set by Claude Code (PD-02, just noted).
  - **`[plugin]` block syntax** — example `.graph-wiki.yaml` snippet showing `backend_default` + `backend_overrides` with one example override (e.g., `ingest: bedrock`).
  - **Commands** — the 6 ported commands listed with one-line descriptions; explicit "Not ported" subsection naming `archive` / `regen-index` / `status` and pointing to PROJECT.md "Explicitly out of v1.2" for rationale.
  - **Link to upstream README** for general framing (iron rules, layout block, frontmatter schema, etc.) — these are unchanged in the port, no need to duplicate.
  Readers assumed to know lattice-wiki (Pat is the audience; this is single-developer scope).

### Smoke gate (SC#4)

- **D-05 (Manual run + transcript pasted into `14-VERIFICATION.md`):** SC#4's "manual smoke check" wording is taken literally. Pat invokes `/graph-wiki:query "what is workspace-io?"` (or equivalent) inside a Claude Code session against `~/Personal/wiki/deep-agents` after Plan 3 lands. Full transcript — user question, librarian fan-out evidence (citations / pages read), synthesized answer with `[[wikilinks]]` and `code-path:line` citations — pasted into `14-VERIFICATION.md` as a fenced markdown block. No snapshot baseline, no structural-assertion script, no live-only demo. Rationale: Claude Code IS the host, so pytest harness is infeasible; LLM nondeterminism makes baseline diffing brittle; a recorded transcript still gives a debug/audit artifact without the false-positive overhead.

### Claude's Discretion

- Exact text of the `plugin.json` description copy-edit (D-03) — preserve upstream's polished positioning prose; the parallel-surface note can be one sentence appended.
- Exact CLAUDE.md (plugin-level) rebrand wording — upstream is ~6.2KB of prose; pure rename + brand-swap pass is fine, no rewrite needed.
- Whether `_config.py` retains upstream's exact error shape (e.g., raising vs returning `"claude"` on manifest-missing) or matches `workspace_io` raising idioms — executor's call; upstream's pattern is fine if it's already aligned.
- Whether the agent `.md` files (`agents/{ingestor,librarian,linter,scanner}.md`) need any prose changes beyond the namespace rebrand — if upstream prose references `/lattice-wiki:` slash commands inside the agent body, swap them; otherwise leave verbatim.
- Whether to also drop `commands/archive.md`, `commands/regen-index.md`, `commands/status.md` from the copy-paste step (not write them) vs copy-then-delete (more visible in diff) — executor's call; both reach the same end state.
- The example query used for the SC#4 smoke (D-05) — any non-trivial question against the deep-agents wiki that exercises librarian fan-out works; `"what is workspace-io?"` is the default unless Pat picks another at verification time.

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Phase 13 spec (the contract — read first)
- `.planning/spec/13-plugin-contract/CONTRACT-INDEX.md` — Verdict table for all 9 upstream commands; entry point for the whole spec.
- `.planning/spec/13-plugin-contract/SHELL-OUT-PATTERN.md` — SO-01..SO-04 (uv-run shape, `[plugin]` block, `_config.py`, shim template) + agent/skill rename map.
- `.planning/spec/13-plugin-contract/init.md` — Per-command spec for `/graph-wiki:bootstrap`.
- `.planning/spec/13-plugin-contract/scan.md` — Per-command spec for `/graph-wiki:scan`.
- `.planning/spec/13-plugin-contract/ingest.md` — Per-command spec for `/graph-wiki:ingest`.
- `.planning/spec/13-plugin-contract/lint.md` — Per-command spec for `/graph-wiki:lint` (reshape: drops work-layer pass 1b).
- `.planning/spec/13-plugin-contract/query.md` — Per-command spec for `/graph-wiki:query` (LLM-driven; BM25 shell-out fallback only).
- `.planning/spec/13-plugin-contract/log.md` — Per-command spec for `/graph-wiki:log` (prose-only, no script).

### Phase scope & prior context
- `.planning/ROADMAP.md` §Phase 14 — Goal, dependencies, success criteria SC#1..SC#4, requirements (PLUGIN-02..05).
- `.planning/REQUIREMENTS.md` — PLUGIN-02..05 full text (the 4 in-scope requirements for Phase 14).
- `.planning/PROJECT.md` §Current Milestone "M3 — plugin port" and §Key Decisions row for Phase 13 lock — the parallel-surfaces reframe.
- `.planning/PROJECT.md` §"Explicitly out of v1.2" — Drives the dropped-commands note in the README (D-04).
- `.planning/phases/13-plugin-spec-m3a/13-CONTEXT.md` — Full Phase 13 decision log (P-01..P-03, C-01..C-02, SO-01..SO-04, SP-01..SP-05, VP-01..VP-04, PD-01..PD-03).
- `.planning/phases/12-drift-backport-ecosystem-rebrand-m2/12-CONTEXT.md` — SR-01 PORT-vs-LEAVE rubric; VP-02 mirrors it for the two vault-io ports.
- `.planning/phases/11-workspace-io-port-m1/11-CONTEXT.md` — D-14 strict-raises philosophy; D-02 two-tier passthrough pattern (mirrored by the plugin shim → backend dispatch).

### Upstream plugin & helpers being ported (read-only references)
- `/Users/pat/Personal/lattice/plugins/lattice-wiki/.claude-plugin/plugin.json` — Source for D-03 plugin.json rebrand.
- `/Users/pat/Personal/lattice/plugins/lattice-wiki/CLAUDE.md` — Plugin-level guidance prose (~6.2KB); rebrand + namespace swap in Plan 3.
- `/Users/pat/Personal/lattice/plugins/lattice-wiki/README.md` — Reference for graph-wiki README fresh-write (D-04 deliberately diverges).
- `/Users/pat/Personal/lattice/plugins/lattice-wiki/commands/{init,scan,ingest,lint,query,log}.md` — Per-command markdown bodies being ported (6 of 9; the 3 dropped per C-01).
- `/Users/pat/Personal/lattice/plugins/lattice-wiki/agents/{ingestor,librarian,linter,scanner}.md` — 4 sub-agents being rebranded per SHELL-OUT-PATTERN.md rename map.
- `/Users/pat/Personal/lattice/plugins/lattice-wiki/skills/lattice-wiki/SKILL.md` — Skill body; wholesale folder rename to `skills/graph-wiki/` + namespace rebrand.
- `/Users/pat/Personal/lattice/plugins/lattice-wiki/skills/lattice-wiki/README.md` — Skill-level README; rebrand + namespace swap.
- `/Users/pat/Personal/lattice/plugins/lattice-wiki/skills/lattice-wiki/references/` — Supporting reference docs read by agents; rebrand pass.
- `/Users/pat/Personal/lattice/plugins/lattice-wiki/skills/lattice-wiki/scripts/_config.py` — SO-04 retargets this verbatim with a new manifest read.
- `/Users/pat/Personal/lattice/plugins/lattice-wiki/skills/lattice-wiki/scripts/init_vault.py` — Canonical shim shape; SO-02 retargets for every ported script.
- `/Users/pat/Personal/lattice/plugins/lattice-wiki/skills/lattice-wiki/scripts/{scan_monorepo,ingest_source,lint_wiki,wiki_search}.py` — Additional shim references.
- `/Users/pat/Personal/lattice/packages/lattice-wiki-core/src/lattice_wiki_core/lint_wiki.py` — ~508 LOC; Plan 1 port source (VP-01).
- `/Users/pat/Personal/lattice/packages/lattice-wiki-core/src/lattice_wiki_core/wiki_search.py` — ~194 LOC; Plan 2 port source (VP-01).

### Existing deep-agents code modified by Phase 14
- `packages/workspace-io/src/workspace_io/manifest.py` — Extended in Plan 3 with strict-raises `[plugin]` block (D-02).
- `packages/workspace-io/src/workspace_io/config.py` — `GraphWikiConfig.resolve()` already discovers the workspace; `_config.py` in the plugin uses it.
- `packages/vault-io/src/vault_io/lint_wiki.py` — New file from Plan 1 (VP-01).
- `packages/vault-io/src/vault_io/wiki_search.py` — New file from Plan 2 (VP-01).
- `packages/vault-io/src/vault_io/{init_vault,scan_monorepo,ingest_source,detect_containers,graph_analyzer}.py` — Imported by claude-branch shims; no changes required, just consumption.
- `agents/graph-wiki-agent/src/graph_wiki_agent/cli.py` — Bedrock-branch subprocess target (SO-02); shape assumed unchanged.
- `scripts/check-brand.sh` + `.brand-grep-allow` — Phase 12 BRAND-04 gate; the two new `vault-io` files and the entire `plugins/graph-wiki/` tree must pass this gate (VP-03).
- `plugins/` — Currently contains only `.gitkeep`; Phase 14 populates `plugins/graph-wiki/`.

### Project-level constraints & memory
- `.planning/PROJECT.md` §Constraints — Python 3.11+, uv workspace, Bedrock-only for graph-wiki-agent (not the plugin), MCP stdio convention.
- Memory `[[project_plugin_port_model]]` — Plugin uses Claude Code inference, NOT Bedrock; functional parity with upstream lattice-wiki; graph-wiki-agent stays as separate Bedrock path (load-bearing for P-01).
- Memory `[[user_lattice_wiki_author]]` — Pat built lattice-wiki; trust "port verbatim" calls (drives D-04 fresh-write and the bundled Plan 3 D-01).
- Memory `[[project_wiki_setup]]` — `~/Personal/wiki/deep-agents` is the SC#4 smoke target.

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- **Upstream shim shape** (`/Users/pat/Personal/lattice/plugins/lattice-wiki/skills/lattice-wiki/scripts/init_vault.py`) — Every ported shim follows this exact pattern per SO-02; read once, retarget 5 times (init_vault, scan_monorepo, ingest_source, lint_wiki, wiki_search). `log` has no shim.
- **Phase 11 delegation shim pattern** (`packages/vault-io/src/vault_io/_workspace.py`) — Proves the "thin shim that imports from a sibling package" works inside this monorepo. Plugin shims are the same idea, just out-of-tree (in `plugins/`).
- **Phase 12 `scripts/check-brand.sh` + `.brand-grep-allow`** — Plan 3's rename pass and Plans 1/2's vault-io ports both clear this gate verbatim. No new infrastructure needed.
- **`workspace_io.manifest.read()`** — Already parses `.graph-wiki.yaml`; Plan 3 extends it with one new top-level key (`plugin`) and strict validation per D-02.
- **`workspace_io.config.resolve()`** — Already walks up from cwd to discover the workspace; `_config.py` (the in-plugin selector) calls this for path resolution before delegating.
- **Phase 11 D-02 (two-tier passthrough at the MCP boundary)** — Same pattern: the shim is the boundary, backend (vault-io vs graph-wiki-agent) is the back-end. No semantic change.
- **Phase 12 SR-01 rubric** — Bug fixes, helper extractions, behavior-preserving refactors come over verbatim. Mirror upstream module shape (`main()` entry, CLI argparse, structured result). Drives Plans 1 and 2.

### Established Patterns
- **Provenance comments** — Phase 11/12 used `# Source: / # Anchor: / # Source-commit:` headers for ported helpers. Plans 1 and 2 follow this pattern verbatim.
- **Atomic per-file commits during a sweep** — Phase 11/12's SQ-02 pattern. Plan 3 will produce multiple commits inside the same plan family (manifest extension first, then scaffolding, then shims, then rebrand sweep, then smoke).
- **One spec doc per phase that locks a contract surface** — Phase 13's `.planning/spec/13-plugin-contract/` is the input contract; Phase 14 does NOT produce a new spec dir, just consumes Phase 13's.
- **Strict-raises manifest** — Phase 11 D-14 established that `workspace_io.manifest` raises on out-of-shape input; D-02 above carries this forward to the new `plugin:` block.

### Integration Points
- **`.graph-wiki.yaml` manifest** — Plan 3 adds `[plugin]` block surfacing (SO-03); strict validation per D-02; default-when-missing returns `{backend_default: "claude", backend_overrides: {}}`.
- **`graph-wiki-agent` CLI surface** — Plan 3 shims' bedrock branch shells to today's CLI (`graph-wiki-agent <cmd> <args>`). Phase 14 does NOT touch graph-wiki-agent; shape assumed stable. If a future phase reshapes the CLI, the plugin's bedrock branch needs an update.
- **`$DEEP_AGENTS_ROOT` env var** — New user-setup convention; documented in plugin README (D-04). No code in this repo needs to know about it; only the plugin shims (which inherit it via the shell when `uv run --project "$DEEP_AGENTS_ROOT"` is invoked).
- **No MCP boundary changes.** Plugin does not use MCP at all. `graph-wiki-mcp` stays where it is.
- **No graph-wiki-agent changes required.** Plan 3 does not modify `agents/graph-wiki-agent/`.
- **Eval harness side-effect (VP-04, non-commitment):** Once `vault_io.lint_wiki` and `vault_io.wiki_search` exist, `graph-wiki-agent lint` and `graph-wiki-agent query` could route through them. Not a Phase 14 commitment; just worth noting.

</code_context>

<specifics>
## Specific Ideas

- **Bundled Plan 3 is deliberate** — Pat chose "3 plans, single bundled port" over the more granular 5-plan or 7+-plan options. Rationale (not in the user's words, but inferred from the decision shape and the prior phases' rhythm): the plugin port is mechanical execution against a tight spec; multiple plans would create handoff overhead without parallelization benefit (Plans 1/2 already parallelize; everything after is sequential). One big Plan 3 with multiple commits inside it matches "atomic plugin port" better than fragmenting it.
- **0.1.0 version reset is a clean break** — graph-wiki and lattice-wiki diverge starting now. Sharing a version lineage would mislead users into thinking they could migrate by id-swap alone (they can't — import surface differs). `0.1.0` says "new package, build up version history independently."
- **README is graph-wiki-specific, NOT a rebrand of upstream** — the audience is Pat (single developer); positioning prose from upstream is redundant. The new README earns its keep by documenting the three things that aren't in upstream: `$DEEP_AGENTS_ROOT` setup, `[plugin]` block syntax, dropped commands.
- **SC#4 transcript in VERIFICATION.md is the only smoke artifact** — no baseline file in `tests/`, no assertion script. The LLM nondeterminism + Claude-Code-host-only invocation make automated regression brittle; a recorded transcript is enough for debug/audit.
- **The `[plugin]` block validation matches manifest house style** — strict-raises. Adding a new override key later means an explicit code change + manifest version consideration, not silent acceptance.
- **`/graph-wiki:log` has no script** — same as upstream. Plan 3's command markdown file ships with prose only; no `scripts/log.py` file is created. (Matches upstream pattern; covered by Phase 13 spec/log.md.)
- **The 3 work-layer commands are DROPPED, not deferred** — no `.md` file in `plugins/graph-wiki/commands/`. They do not appear in `/graph-wiki:` autocomplete. Documented in the README's "Not ported" section per D-04.
- **Brand sweep covers everything in `plugins/graph-wiki/` and the two new `vault-io` files** — `lattice` → `graph-wiki` in identifiers, prose, slash command references, file paths. Runs `scripts/check-brand.sh` as the gate.

</specifics>

<deferred>
## Deferred Ideas

- **Bedrock-branch smoke tests** — Phase 14 verifies the claude branch only (matches v1.2 default). A follow-up could exercise `backend_overrides: {ingest: bedrock}` and assert the subprocess to `graph-wiki-agent` fires correctly. Useful if Pat ever exercises the seam in anger.
- **Per-command pricing / cost telemetry in plugin shims** — Bedrock-branch invocations could log to the same trace pipeline as graph-wiki-agent. Out of v1.2; trace pipeline gaps owned by Phase 16, TRACE-FU-01.
- **Plugin auto-install / marketplace publish** — Out of v1.2; open-source release prep deferred to v2.0 GA per PROJECT.md.
- **MCP-server-based plugin variant** — Long-term alternative where graph-wiki exposes commands as MCP tools (so users wouldn't need `$DEEP_AGENTS_ROOT`). Out of v1.2; would treat graph-wiki-mcp as a tool dependency. Worth revisiting in v2.0.
- **Auto-discovery of `$DEEP_AGENTS_ROOT` from cwd** — Rejected for v1.2 in favor of explicit env var (PD-01). Could revisit if the plugin gets shared with other users.
- **Work-layer subsystem revival** — Would unblock `/graph-wiki:archive`, `/regen-index`, `/status`. GSD covers work-item lifecycle per thread decision 2026-05-17. Future phase if ever reconsidered.
- **`export_marp.py` port** — Not on any slash command. Deferred indefinitely; could land if Pat ever wants Marp slide export inside graph-wiki.
- **Structural-assertion script for `/graph-wiki:query` smoke** — Alternative to D-05 that runs a query against a fixture vault and asserts non-empty output + valid wikilinks. Not adopted in v1.2 because Claude Code IS the host (hard to harness); transcript-only is enough.

</deferred>

---

*Phase: 14-plugin-port-m3b*
*Context gathered: 2026-05-18*
