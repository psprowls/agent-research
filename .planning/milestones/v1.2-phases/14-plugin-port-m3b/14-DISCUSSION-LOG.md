# Phase 14: Plugin Port (M3b) - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md — this log preserves the alternatives considered.

**Date:** 2026-05-18
**Phase:** 14-plugin-port-m3b
**Areas discussed:** Plan slicing past VP-01, [plugin] block validation rigor, /graph-wiki:query smoke gate (SC#4), plugin.json + README content

---

## Plan slicing past VP-01

VP-01 locks Plan 1 (`vault_io.lint_wiki` port) and Plan 2 (`vault_io.wiki_search` port). Question: how to slice the remaining work (manifest extension, plugin scaffold, shim rewrites, agent/skill rename, smoke)?

| Option | Description | Selected |
|--------|-------------|----------|
| 5 plans, concern-split (Recommended) | P1 lint_wiki, P2 wiki_search, P3 workspace_io.manifest [plugin] block + _config.py, P4 plugin scaffold (copy + rebrand + shims + agent/skill rename), P5 end-to-end smoke + VERIFICATION.md. P1/P2/P3 parallel; P4 depends on all three; P5 depends on P4. | |
| 4 plans, scaffold + smoke bundled | P1 lint_wiki, P2 wiki_search, P3 manifest [plugin] block + _config.py, P4 plugin scaffold + shims + agent/skill rename + smoke verification. P4 is large but keeps the plugin port atomic in one commit family. | |
| 3 plans, single bundled port | P1 lint_wiki, P2 wiki_search, P3 everything else (manifest extension + plugin scaffold + shims + rename + smoke). Big P3 but matches phases-as-atomic-units feel; few SUMMARYs. | ✓ |
| 7+ plans, per-command shims | P1 lint_wiki, P2 wiki_search, P3 manifest [plugin] block, P4 scaffold + rename, P5..P10 one plan per shim (init, scan, ingest, lint, query, log) + agents/skills, P11 smoke. Maximal granularity but each shim is ~25 LOC — likely over-sliced. | |

**User's choice:** 3 plans, single bundled port
**Notes:** Captured as **D-01** in CONTEXT.md. Plans 1 and 2 (VP-01 ports) parallelize; Plan 3 is the atomic plugin port bundle (manifest extension → scaffold → shims → rename → smoke). The bundle keeps the port in one SUMMARY family and minimizes handoff overhead given the work past VP-01 is sequential anyway.

---

## [plugin] block validation rigor

Phase 14 extends `workspace_io.manifest.read()` to surface the `[plugin]` block per SO-03. Phase 11 D-14 set the manifest's house style as strict-raises.

| Option | Description | Selected |
|--------|-------------|----------|
| Strict-raises, matches Phase 11 D-14 (Recommended) | Known keys only: backend_default (literal 'claude' \| 'bedrock'), backend_overrides (dict[str, 'claude' \| 'bedrock']). Unknown keys raise. Default-when-block-missing: backend_default='claude', backend_overrides={}. Consistent with manifest v1 philosophy; changes are visible in code review. | ✓ |
| Lenient pass-through for unknown keys | Validate backend_default/backend_overrides shape, but ignore extra keys silently. Lets future per-command override extensions land without a manifest schema bump. Diverges from Phase 11 D-14. | |
| Hybrid: strict on shape, warn on unknown | Validate known keys strictly. Unknown keys emit a logger.warning but do not raise. Compromise — surfaces drift in logs but doesn't break old configs. | |

**User's choice:** Strict-raises, matches Phase 11 D-14
**Notes:** Captured as **D-02** in CONTEXT.md. Manifest house style preserved. Future schema extensions require explicit code change + manifest version consideration, not silent acceptance.

---

## /graph-wiki:query smoke gate (SC#4)

SC#4 wording itself says "manual smoke check." Question: what artifact (if any) gets recorded?

| Option | Description | Selected |
|--------|-------------|----------|
| Manual run + transcript pasted into 14-VERIFICATION.md (Recommended) | User invokes /graph-wiki:query inside a Claude Code session against ~/Personal/graph-wiki/agent-research. Paste the full transcript into 14-VERIFICATION.md as a fenced block. Lightweight, matches SC#4 wording, no nondeterminism brittleness. | ✓ |
| Snapshot baseline in plugins/graph-wiki/tests/smoke/ | Capture the transcript as a baseline; future re-runs do prose-level structural diff. Heavier; risks false positives from LLM nondeterminism but enables regression checks. | |
| Live demo only — no recorded artifact | Run it once during gsd-verify-work; verify in conversation, no transcript persisted. Cheapest but leaves no audit trail. | |
| Manual transcript + structural assertion script | Both: paste transcript AND ship scripts/check-query-smoke.sh that runs against a fixture vault and asserts non-empty output + valid wikilinks. Belt and braces; more upfront work. | |

**User's choice:** Manual run + transcript pasted into 14-VERIFICATION.md
**Notes:** Captured as **D-05** in CONTEXT.md. Rationale: Claude Code IS the host, so pytest-style harness is infeasible; LLM nondeterminism makes baseline diffing brittle. Transcript provides a debug/audit artifact without false-positive overhead.

---

## plugin.json + README content

Two paired questions about the new package's stamp and its README.

### plugin.json — version & description

| Option | Description | Selected |
|--------|-------------|----------|
| Reset to 0.1.0, new package identity (Recommended) | version: '0.1.0', name: 'graph-wiki', author/license preserved. Description copy-edited from upstream with brand swap + one-line note that this is the Claude Code host path (companion to graph-wiki-agent). Signals separate publish history. | ✓ |
| Bump from upstream (0.5.2 → 0.6.0) | Treats graph-wiki as a continuation of upstream's lineage. Implies users could migrate by id-swap alone — misleading since import surface differs. | |
| Reset to 0.1.0, fresh description rewrite | Same version reset, but rewrite description from scratch. More effort; risks losing upstream's polished positioning. | |

**User's choice:** Reset to 0.1.0, new package identity
**Notes:** Captured as **D-03** in CONTEXT.md. Version 0.1.0 = new package, build version history independently. `env.LATTICE_WIKI_ROOT` → `env.GRAPH_WIKI_ROOT`, value stays `${CLAUDE_PLUGIN_ROOT}`. Keywords copied from upstream verbatim.

### README content shape

| Option | Description | Selected |
|--------|-------------|----------|
| Copy upstream + rebrand + new setup section (Recommended) | Start from upstream README.md, swap 'lattice-wiki' → 'graph-wiki' throughout, then add a new 'Setup' section ($AGENT_RESEARCH_ROOT export, [plugin] block syntax, dropped commands note). Preserves upstream's polished positioning. | |
| Fresh-write focused on graph-wiki specifics | Brand-new README covering only what differs from upstream ($AGENT_RESEARCH_ROOT, [plugin] block, dropped commands, link to upstream README for the rest). Shorter; assumes readers know lattice-wiki. | ✓ |
| Copy upstream verbatim + rebrand only, no setup section | Pure rebrand pass. Defer $AGENT_RESEARCH_ROOT/[plugin]-block docs to plugin CLAUDE.md or SETUP.md. Keeps README close to upstream for easy diffing but hides critical setup. | |

**User's choice:** Fresh-write focused on graph-wiki specifics
**Notes:** Captured as **D-04** in CONTEXT.md. Audience is Pat (single developer); upstream's general positioning prose is redundant for this audience. The new README documents the three things that aren't in upstream: `$AGENT_RESEARCH_ROOT` setup, `[plugin]` block syntax, dropped commands. Links back to upstream README for shared concepts (iron rules, layout block, frontmatter schema).

---

## Claude's Discretion

The following were left to executor judgment in CONTEXT.md (§Claude's Discretion):

- Exact text of the `plugin.json` description copy-edit — preserve upstream's polished positioning prose; the parallel-surface note can be one sentence appended.
- Exact CLAUDE.md (plugin-level) rebrand wording — upstream is ~6.2KB of prose; pure rename + brand-swap pass is fine, no rewrite needed.
- Whether `_config.py` retains upstream's exact error shape (e.g., raising vs returning `"claude"` on manifest-missing) or matches `workspace_io` raising idioms.
- Whether the agent `.md` files (`agents/{ingestor,librarian,linter,scanner}.md`) need any prose changes beyond the namespace rebrand.
- Whether to drop `commands/archive.md`, `regen-index.md`, `status.md` from the copy-paste step (not write them) vs copy-then-delete (more visible in diff).
- The example query used for the SC#4 smoke (default: `"what is workspace-io?"` unless Pat picks another at verification time).

## Deferred Ideas

Ideas that came up during prior phases (carried forward from Phase 13 deferred list) or could have been raised but belong elsewhere:

- Bedrock-branch smoke tests — useful follow-up if Pat exercises the `backend_overrides` seam.
- Per-command pricing / cost telemetry in plugin shims — Phase 16 (TRACE-FU-01).
- Plugin auto-install / marketplace publish — v2.0 GA.
- MCP-server-based plugin variant — v2.0+ alternative where graph-wiki exposes commands as MCP tools.
- Auto-discovery of `$AGENT_RESEARCH_ROOT` from cwd — rejected for v1.2 in favor of explicit env var (PD-01).
- Work-layer subsystem revival — would unblock dropped commands; future phase if ever reconsidered.
- `export_marp.py` port — not on any slash command; deferred indefinitely.
- Structural-assertion script for the smoke gate — alternative to D-05; not adopted because Claude Code is the host.
