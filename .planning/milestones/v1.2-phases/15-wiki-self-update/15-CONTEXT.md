# Phase 15: Wiki Self-Update - Context

**Gathered:** 2026-05-18
**Status:** Ready for planning

<domain>
## Phase Boundary

Bring the project's own wiki at `~/Personal/wiki/deep-agents` into alignment with the post-rebrand codebase (v1.2 Phases 11–14) by driving a `code-wiki-agent` scan + ingest pass from the Bedrock CLI surface, then verifying the result with one librarian query and a single-page spot-check.

**In scope:**
- Write a new `models-claude.toml` at the repo root (sibling of `models-qwen.toml`) overriding fan-out roles (`scanner`, `linter`, `ingestor`, `code_reader`) to Haiku 4.5 and reasoning roles (`librarian`, `synthesizer`) to Sonnet 4.6. `judge_a`/`judge_b` rows preserved (already on Claude family).
- Run `code-wiki-agent scan` against `~/Personal/wiki/deep-agents` using the Claude override config. Scan auto-detects post-rebrand workspace state: `workspace-io` (new in Phase 11), `prompt-sources` (also missing from wiki), and refreshes existing package pages (`vault-io`, `eval-harness`, `model-adapter`, `subagent-runtime`).
- Run `code-wiki-agent ingest` for the one existing source doc `~/Personal/wiki/raw/OTel — Story of observability.md`, using the Claude override.
- Run `code-wiki-agent query "what is workspace-io?"` (literal SC#3) using the Claude override; paste full transcript into `15-VERIFICATION.md` as a fenced block.
- Spot-check the `workspace-io` package page produced by scan: frontmatter present + valid, body has package summary + key claims, at least one `[[wikilink]]` resolves to an existing wiki page. Record in `15-VERIFICATION.md`.
- Confirm scan-log entry (`scan-log.md` or equivalent) in the wiki vault shows the new package names without `lattice` artifacts (SC#1 literal).

**Out of scope:**
- The `/graph-wiki:*` plugin path — Phase 14 SC#4 already smoke-tested it (transcript in `14-VERIFICATION.md`). Phase 15 exercises the Bedrock CLI surface only.
- Any cleanup of pre-existing stale `lattice*` references in wiki pages or `log.md` history. Scan/ingest refresh what they touch; everything else stays as-is (`log.md` is append-only by convention).
- Post-run `grep -r lattice` sweep across `~/Personal/wiki/deep-agents/`. SC#1's literal wording requires only that the scan-log shows new package names without lattice artifacts; surviving stale refs in untouched pages are not in scope.
- Additional librarian queries beyond `what is workspace-io?` (no rebrand-surface expansion, no diff vs Phase 14 plugin transcript).
- Spot-checking pages other than `workspace-io` (e.g., `vault-io` post-rebrand, `prompt-sources`, plugin pages). One page suffices per SC#2.
- Lint runs (before or after); model swap experiments; cost telemetry.
- Any edits to the `code-wiki-agent` CLI itself or to the wiki schema; this phase is content-only.
- Phase 16 carry-forward debt (trace pipeline, sweep coverage, MCP cancel, model-config test drift).

</domain>

<decisions>
## Implementation Decisions

### Tool surface

- **D-01 (Bedrock CLI only):** Phase 15 runs via `code-wiki-agent scan/ingest/query` (Bedrock). The plugin path was already smoke-tested in Phase 14 SC#4 — no need to re-exercise. Matches SC#1's literal wording (`code-wiki-agent scan ~/Personal/wiki/deep-agents completes`). Lowest cost path; consistent with project Core Value (Bedrock-driven wiki workflows).

### Model selection

- **D-02 (Haiku 4.5 fan-out + Sonnet 4.6 synth):** Override the wiki's default Qwen profile for this run. Fan-out roles (`scanner`, `linter`, `ingestor`, `code_reader`) → `us.anthropic.claude-haiku-4-5-20251001-v1:0`; reasoning roles (`librarian`, `synthesizer`) → `us.anthropic.claude-sonnet-4-6`. Rationale: stronger post-rebrand baseline than the Qwen profile while staying meaningfully cheaper than full-Sonnet-everywhere; matches the divergence-judge stack family from v1.1 Phase 6 EVAL-11..13.
- **D-03 (New `models-claude.toml` at repo root):** Specified as a reusable sibling config to `models-qwen.toml` (not CLI flags, not an inline snippet). Pass via `--models-config models-claude.toml` (or whatever the existing CLI flag is — executor confirms during scout). Reusable for future Claude-profile runs; non-destructive; matches the existing pattern. Preserve `roles.judge_a` and `roles.judge_b` rows verbatim from `models-qwen.toml` (already Claude/Nova family). `max_tokens` / `max_concurrency` values: executor matches each role's existing budget from `models-qwen.toml` unless a Claude-specific reason emerges.

### Ingest scope

- **D-04 (Re-ingest OTel only):** `~/Personal/wiki/raw/` contains exactly one source doc (`OTel — Story of observability.md`); `~/Personal/wiki/deep-agents/sources/` is empty. "Full re-ingest of sources" effectively = 1 doc. No bootstrapping of new post-rebrand sources from `.planning/` (the rebrand surface lands in the wiki via the scan-detected package pages, not via source-summary ingests).

### Run order

- **D-05 (Sequential: scan → ingest → query → spot-check):** Scan first (creates `workspace-io` + `prompt-sources` pages, refreshes existing). Ingest OTel after (refreshes the OTel source summary against new package names if cross-refs exist). Then run librarian query (`what is workspace-io?`). Then spot-check the `workspace-io` page. Then write `15-VERIFICATION.md`. Matches SC ordering (SC#1 → SC#2 → SC#3) and gives the query the freshest possible vault state.

### Stale-content cleanup boundary

- **D-06 (Leave history alone; scan/ingest refresh what they touch):** `log.md` entries remain as-is — they are append-only historical record (including the `2026-05-16` `/lattice-wiki:scan` entry). Scan + ingest refresh pages they regenerate; anything they don't touch (stale concept/architecture pages with surviving `lattice*` refs) stays as-is. Lowest scope; respects log convention.
- **D-07 (Ignore surviving lattice refs):** No post-run `grep -r lattice` sweep, no count recorded, no follow-up todo opened. SC#1 reads literally: `scan-log.md shows the new package names without lattice artifacts` — that's about the new scan-log entries, not pre-existing pages. Don't chase what isn't required; Phase 12's `scripts/check-brand.sh` already gates the **repo** rebrand and is the source of truth for "rebrand complete."

### Verification

- **D-08 (Single-page spot-check: `workspace-io`):** SC#2 spot-check minimum bar — open the scan-produced `workspace-io` package page, verify (a) frontmatter present and parseable, (b) body has package summary + at least 2-3 key claims, (c) at least one `[[wikilink]]` resolves to an existing page in the wiki. Documented in `15-VERIFICATION.md` with the page path. No deeper rigor (no `vault-io` rebrand check, no plugin-page check).
- **D-09 (Literal SC#3 query — one only):** Run `code-wiki-agent query "what is workspace-io?"`. Paste full transcript (user question + fan-out evidence + synthesized answer with wikilinks/code-path citations) into `15-VERIFICATION.md` as a fenced block. No additional rebrand-surface queries; no diff vs Phase 14 plugin transcript.

### Plan structure

- **D-10 (1 atomic plan):** All steps land in one plan: write `models-claude.toml` → `code-wiki-agent scan` → `code-wiki-agent ingest` (OTel) → `code-wiki-agent query` → spot-check → write `15-VERIFICATION.md` → commit. Phase is short (BRAND-03 single requirement; 3 SC; CLI-driven only); matches the bundled-plan pattern used in Phase 14 Plan 3 and aligns with the user preference for fewer, larger plans on mechanical work.

### Claude's Discretion

- Exact CLI flag name for the model-override config (`--models-config`, `--profile`, etc.) — executor reads `code-wiki-agent --help` or the relevant CLI source during scout to confirm. The CLI already supports the Qwen override (`wiki-config.toml` points to `models-qwen.toml`), so a Claude override is a known-supported shape.
- Per-role `max_tokens` and `max_concurrency` tuning in `models-claude.toml` — defaulting to the same values as `models-qwen.toml` is fine; if Haiku 4.5 / Sonnet 4.6 have meaningfully different practical concurrency limits on Bedrock, executor's call to adjust.
- Whether the new `prompt-sources` package page (which scan will also create — it's another missing-from-wiki package) is spot-checked alongside `workspace-io` or only mentioned. SC#2 says "at least one page" — one suffices, but if `prompt-sources` is also new, calling it out as additional evidence costs ~30 seconds.
- Exact format of `15-VERIFICATION.md` (sections, ordering) — executor's call; follow `14-VERIFICATION.md` template if a template exists.
- Whether `models-claude.toml` is committed at the repo root or kept gitignored as a one-off — recommend committing (reusable, no secrets, matches `models-qwen.toml` which is tracked).

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Phase scope & immediate prior context
- `.planning/ROADMAP.md` §Phase 15 — Goal, depends-on chain, SC#1..SC#3, BRAND-03 requirement mapping.
- `.planning/REQUIREMENTS.md` — BRAND-03 full text ("Wiki self-update — `~/Personal/wiki/deep-agents` scanned + ingested after rebrand to absorb new package names and `.graph-wiki.yaml` manifest").
- `.planning/PROJECT.md` — Project Core Value, Bedrock-only constraint for code-wiki-agent, "Explicitly out of v1.2" list.
- `.planning/phases/14-plugin-port-m3b/14-CONTEXT.md` — Phase 14 decisions (plugin port outcomes, what the wiki should now reflect).
- `.planning/phases/14-plugin-port-m3b/14-VERIFICATION.md` — Phase 14 SC#4 transcript (`/graph-wiki:query "what is workspace-io?"` via plugin) — for context only; Phase 15 does NOT diff against it.
- `.planning/phases/12-drift-backport-ecosystem-rebrand-m2/12-CONTEXT.md` — Phase 12 rebrand decisions and `scripts/check-brand.sh` gate (the repo-side BRAND truth source, distinct from Phase 15's wiki-side BRAND-03 scope).
- `.planning/phases/11-workspace-io-port-m1/11-CONTEXT.md` — `workspace-io` package shape and rationale (drives the new wiki package page).

### Wiki vault under update (read-only references for the executor)
- `/Users/pat/Personal/wiki/deep-agents/` — Vault root being updated.
- `/Users/pat/Personal/wiki/deep-agents/index.md` — Wiki root index.
- `/Users/pat/Personal/wiki/deep-agents/packages/` — Current package pages (`eval-harness`, `model-adapter`, `subagent-runtime`, `vault-io`). Missing: `workspace-io`, `prompt-sources` (scan will add).
- `/Users/pat/Personal/wiki/deep-agents/log.md` — Append-only log. Scan/ingest will add new entries; pre-existing `/lattice-wiki:scan` line stays as historical record (D-06).
- `/Users/pat/Personal/wiki/deep-agents/CLAUDE.md` — Wiki schema; defines layout block + style rules read by scanner/linter/ingestor.
- `/Users/pat/Personal/wiki/raw/OTel — Story of observability.md` — The one existing source doc; ingest target per D-04.
- `/Users/pat/Personal/wiki/deep-agents/sources/` — Currently empty; ingest will land OTel summary here.

### Repo configuration this phase touches
- `models-qwen.toml` — Existing Qwen role-override profile; reference shape for the new `models-claude.toml` (D-03). Sibling at repo root.
- `wiki-config.toml` — Points `models_path` at `models-qwen.toml`; Phase 15 does **NOT** modify this file (the override is passed via CLI flag for this one run).
- `models-claude.toml` (new in this phase) — Haiku 4.5 fan-out + Sonnet 4.6 synthesis, per D-02/D-03.

### Repo state scan will observe
- `packages/` (6 dirs): `eval-harness`, `model-adapter`, `prompt-sources`, `subagent-runtime`, `vault-io`, `workspace-io`.
- `agents/code-wiki-agent/` — Bedrock CLI surface scan/ingest/query are invoked through.
- `plugins/graph-wiki/` — Plugin port from Phase 14 (scan may or may not capture this depending on detection rules; not in SC).

### Memory / project-level constraints
- `[[project_wiki_setup]]` — Wiki vault path and existing Qwen profile (Phase 15 overrides for this run only; doesn't replace the default).
- `[[user_cost_optimization]]` — Eval-driven model selection; "measure it" mindset. D-02's Haiku+Sonnet override is a deliberate one-run choice, not a profile change.
- `[[project_plugin_port_model]]` — Plugin uses Claude Code inference; `code-wiki-agent` is the Bedrock path. Phase 15 exercises the Bedrock path only (D-01).

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- **`code-wiki-agent` CLI** (`agents/code-wiki-agent/src/code_wiki_agent/cli.py`) — Already supports `scan`, `ingest`, `query` subcommands; already supports an external models-config file (Qwen profile is exercised via `wiki-config.toml → models_path`). Phase 15 adds a sibling Claude profile and routes via CLI flag for one run.
- **`models-qwen.toml`** — Reference shape for `models-claude.toml`. Roles defined: `haiku`, `sonnet` (both already on Claude family — already-named slots), `librarian`, `scanner`, `linter`, `ingestor`, `code_reader`, `synthesizer`, `judge_a`, `judge_b`. Phase 15's new file mirrors this structure.
- **Phase 11/12 pattern**: scan auto-detects new packages from `pyproject.toml` workspace members. `workspace-io` and `prompt-sources` are both present in `packages/` and absent from the wiki — scan will surface both.

### Established Patterns
- **Provenance comments** on new top-level configs — `models-qwen.toml` has a `# Model role overrides — ...` header explaining the profile's intent. `models-claude.toml` should mirror this with a one-line header naming the use case (e.g., "Used for Phase 15 wiki self-update — Haiku fan-out + Sonnet synth").
- **Per-phase VERIFICATION.md transcript artifacts** — Phase 14 SC#4 captured a fenced transcript block in `14-VERIFICATION.md`; Phase 15 follows the same pattern for SC#3 (D-09).
- **Atomic per-step commits within an atomic plan** — Phase 14 Plan 3 produced multiple commits inside one plan family. Phase 15's single plan (D-10) follows the same shape: commit `models-claude.toml` first, then scan output, then ingest output, then verification doc.

### Integration Points
- **Wiki vault** (`~/Personal/wiki/deep-agents/`) — External to this repo; Phase 15 mutates it (scan adds package pages; ingest updates source summary). Vault is a git repo (likely); commits there are separate from this repo's commits.
- **No code changes** in `agents/code-wiki-agent/` or `packages/` — Phase 15 is content-only on the wiki side, with one new config file (`models-claude.toml`) and one new doc (`15-VERIFICATION.md`) on the repo side.
- **No MCP boundary touch** — code-wiki-mcp is not exercised by Phase 15.
- **No plugin touch** — `plugins/graph-wiki/` already smoke-tested in Phase 14 SC#4.

</code_context>

<specifics>
## Specific Ideas

- **Wiki is meaningfully drifted** — `~/Personal/wiki/deep-agents/packages/` is missing both `workspace-io` (added in Phase 11) and `prompt-sources` (added separately during v1.1 → v1.2). One scan should land both. Spot-checking `workspace-io` only (D-08) leaves `prompt-sources` validated implicitly (it shows up in scan log or doesn't).
- **The Qwen profile is the wiki's default, NOT being replaced** — `models-claude.toml` is a one-off override for this rebrand-baseline pass. Future wiki updates continue on Qwen unless Pat decides otherwise; `wiki-config.toml` stays pointed at `models-qwen.toml`.
- **D-09 is deliberately narrow** — Phase 14 SC#4 already exercised "what is workspace-io?" via the plugin. Re-running the same query via the CLI gives the Bedrock-side answer for the same question; the two transcripts (`14-VERIFICATION.md` + `15-VERIFICATION.md`) form an implicit cross-surface comparison without making it a SC.
- **No `.graph-wiki.yaml` in the wiki workspace today** — BRAND-03 mentions ".graph-wiki.yaml manifest" awareness, but `~/Personal/wiki/` and `~/Personal/wiki/deep-agents/` currently have no manifest file. Phase 15 does **not** create one — `wiki-config.toml` at the repo root is the working surface, and Phase 11's manifest filename change is about the **repo-side** workspace, not the wiki vault. (If a manifest is later wanted on the wiki side, that's a follow-up.)
- **`log.md` integrity** — the existing `2026-05-16` entries reference `/lattice-wiki:*` slash commands. These are kept as-is per D-06. New scan/ingest/query entries appended by Phase 15 will use the post-rebrand entry shape automatically.

</specifics>

<deferred>
## Deferred Ideas

- **Wiki-side `.graph-wiki.yaml` manifest** — BRAND-03 names manifest awareness; deferred because Phase 15 routes via `wiki-config.toml` (repo-side) and the wiki vault has no manifest today. Could be revisited if the wiki ever needs to advertise its own `[plugin]` block or detection schema.
- **Bedrock vs Claude Code CLI cross-surface diff** — Running `what is workspace-io?` on both surfaces and diffing the answers (semantically, not byte-wise) would be valuable for the v1.2 close-out. Not part of SC; could land as part of v1.2 milestone audit.
- **Multi-query librarian audit** — Running 5-10 librarian queries spanning the rebrand surface (`what is .graph-wiki.yaml?`, `what does workspace-io do?`, `what's the graph-wiki plugin?`) for a deeper baseline. Out of scope for Phase 15's single-query SC#3; could land as a Phase 16 sub-task if cost-frontier sweep expansion is in play.
- **Stale-content sweep across wiki pages** — `grep -r lattice ~/Personal/wiki/deep-agents/` post-run + manual rewrites of any surviving hits in concepts/architecture pages. Explicitly out per D-07; revisit if a future librarian query is found to be polluted by stale text.
- **Qwen profile rebaseline** — Re-running this exact scan/ingest/query trio on the default Qwen profile to compare against the Claude-override output. Useful as cost-frontier evidence; out of v1.2 scope; could land as a Phase 16 sweep extension.
- **Lint pass before/after** — Capturing `code-wiki-agent lint` output as before/after evidence of stale-content health. Considered and rejected for Phase 15 (no SC backs it; adds cost).
- **Promote `models-claude.toml` to the default profile** — Possible follow-up after measuring quality vs Qwen. Out of v1.2; matches the cost-frontier-mindset memory ("measure it" before defaulting).
- **Spot-check additional pages (`vault-io` post-rebrand, plugin entry)** — Explicitly out per D-08; could land in a future audit phase.
- **Phase 14 plugin transcript diff** — Comparing today's CLI transcript against `14-VERIFICATION.md` plugin transcript. Considered (D-09 option C) and rejected; could be revisited at milestone audit time.

</deferred>

---

*Phase: 15-wiki-self-update*
*Context gathered: 2026-05-18*
