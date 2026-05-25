# Phase 15: Wiki Self-Update - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md — this log preserves the alternatives considered.

**Date:** 2026-05-18
**Phase:** 15-wiki-self-update
**Areas discussed:** Tool surface, Models, Ingest scope, Run order, Stale-content cleanup, Surviving refs, Spot-check rigor, Query scope, Plan structure

---

## Tool surface for the update

| Option | Description | Selected |
|--------|-------------|----------|
| graph-wiki-agent CLI only (Bedrock) | Matches SC#1 literally. Uses Qwen3 fan-out by default. Plugin already smoke-tested in Phase 14 SC#4 — no need to re-exercise. Cheapest path, fewest moving parts. | ✓ |
| CLI primary + plugin smoke | Run actual update via CLI (Bedrock), then add `/graph-wiki:scan` smoke from Claude Code session. More coverage; small extra step. | |
| /graph-wiki:* plugin primary | Drive the whole update from the plugin (Claude Code inference). Stretches SC#1's wording but exercises Phase 14 deliverable harder. | |

**User's choice:** graph-wiki-agent CLI only (Bedrock).
**Notes:** Reflects cost-frontier mindset and SC#1's literal wording. Phase 14 SC#4 plugin transcript stays the plugin-side smoke; Phase 15 covers the Bedrock-side smoke.

---

## Models (override or default?)

| Option | Description | Selected |
|--------|-------------|----------|
| Qwen profile (default) | Use `models-qwen.toml` already at project root — Qwen3-32B fan-out + Qwen3-80B synthesis. Matches `[[project_wiki_setup]]`; cheapest; consistent with prior runs. | |
| Sonnet/Opus override for this run | One-time use of a stronger judge for the post-rebrand pass. Higher cost; stronger fidelity. | ✓ |
| Mix — Qwen fan-out, Sonnet synth | Cheap fan-out, stronger synthesizer. Reasonable middle ground. | |

**User's choice:** Sonnet/Opus override for this run.
**Notes:** Treats Phase 15 as a baseline-quality moment, not a routine refresh. Override is one-off; default profile (Qwen) stays the wiki's standard via `wiki-config.toml`.

---

## Models (which Sonnet/Opus override?)

| Option | Description | Selected |
|--------|-------------|----------|
| Sonnet 4.6 everywhere | Both fan-out and synth on `claude-sonnet-4-6`. Strong fidelity; moderate cost; matches divergence-judge stack. | |
| Haiku 4.5 fan-out + Sonnet 4.6 synth | Cheaper fan-out with strong synthesis. Closest to Qwen-mix shape on Claude family. Best cost/quality balance. | ✓ |
| Opus 4.7 synth, Sonnet 4.6 fan-out | Premium synth; highest cost; most defensible baseline. | |

**User's choice:** Haiku 4.5 fan-out + Sonnet 4.6 synth.
**Notes:** Mirror of the Qwen profile's split (32B fan-out + 80B synth), translated to Claude family. Cost/quality balance.

---

## Models (how is the override specified?)

| Option | Description | Selected |
|--------|-------------|----------|
| New `models-claude.toml` at project root | Sibling to `models-qwen.toml`; pass via `--models-config` flag. Reusable; matches existing pattern. | ✓ |
| CLI flags only (no file) | Pass model IDs as CLI flags. Zero new files; one-shot only. | |
| Inline TOML snippet in 15-VERIFICATION.md | Record config inline as doc; invoke via CLI flags. Self-documenting; no separate file. | |

**User's choice:** New `models-claude.toml` at project root.
**Notes:** Reusable for future Claude-profile runs; matches the conservation pattern of `models-qwen.toml`. `wiki-config.toml` is NOT modified — the override is per-run.

---

## Scope of re-ingest (initial)

| Option | Description | Selected |
|--------|-------------|----------|
| Scan-only delta (no manual ingest) | Run scan; skip ingest. workspace-io page comes from scan. Cheapest. | |
| Scan + targeted ingest of post-rebrand sources | Scan, then re-ingest source docs that referenced `lattice_*`. | |
| Scan + full re-ingest of all sources | Scan, then re-ingest every doc in `sources/`. Largest run. | ✓ |

**User's choice (initial):** Scan + full re-ingest of all sources.
**Notes:** Reframed after Claude noticed `sources/` is empty and `raw/` has only one source doc.

---

## Scope of re-ingest (reframe)

| Option | Description | Selected |
|--------|-------------|----------|
| Re-ingest OTel + ingest new post-rebrand source docs | Re-ingest OTel + add new sources from `.planning/` (CONTEXT.md files, plugin specs). Bootstraps wiki's knowledge of rebrand via source summaries. | |
| Re-ingest OTel only | Just the one existing source. Scan handles package pages. | ✓ |
| Ingest NEW post-rebrand source docs only | Skip OTel; add phase CONTEXT.md / spec docs / PROJECT.md as new sources. | |
| Skip ingest entirely | Scan-only path. Closest to SC#1 literal. | |

**User's choice:** Re-ingest OTel only.
**Notes:** Source-doc churn is not the rebrand surface; scan-detected package pages are. OTel re-ingest covers the SC#2 "ingest re-ingests changed package pages" bullet's spirit via the source-summary refresh.

---

## Run order

| Option | Description | Selected |
|--------|-------------|----------|
| scan → ingest → query → spot-check | Sequential per SC ordering. | ✓ |
| lint first → scan → ingest → lint → query | Bracket with lint runs for before/after delta. | |
| scan → query → ingest → spot-check | Query before ingest to test whether scan alone gives a workspace-io answer. | |

**User's choice:** scan → ingest → query → spot-check.
**Notes:** Standard SC ordering. Query runs against freshest vault state.

---

## Stale-content cleanup boundary

| Option | Description | Selected |
|--------|-------------|----------|
| Leave history alone; let scan/ingest update what they touch | log.md stays untouched; scan/ingest refresh what they regenerate; everything else stays as-is. | ✓ |
| Manual sweep of non-log pages after scan/ingest | Post-run `grep -r lattice` across concepts/architecture/adrs/packages; manual fixes. | |
| Full sweep including log history rewrites | Above + rewrite stale `/lattice-wiki:*` refs in log.md. Breaks append-only convention. | |

**User's choice:** Leave history alone; let scan/ingest update what they touch.
**Notes:** Respects log's append-only convention. Lowest scope.

---

## Surviving refs (record or ignore?)

| Option | Description | Selected |
|--------|-------------|----------|
| Record post-run grep count in 15-VERIFICATION.md | Run `grep -rE 'lattice'` after; paste count + sample. No fixes. | |
| Ignore entirely; SC#1 only requires scan-log to be clean | SC#1 reads literally — only the scan-log entries need to be lattice-free, not pre-existing pages. | ✓ |
| Record + open Phase 16 follow-up if non-zero | Track the debt for future cleanup. | |

**User's choice:** Ignore entirely; SC#1 only requires scan-log to be clean.
**Notes:** SC#1 is the source of truth. Phase 12's `scripts/check-brand.sh` already gates the repo-side rebrand; Phase 15 is wiki-content-only and respects the SC#1 surface.

---

## Spot-check rigor (SC#2)

| Option | Description | Selected |
|--------|-------------|----------|
| workspace-io page only — frontmatter + body + at least one wikilink | Minimum bar; matches SC#2 literal. | ✓ |
| workspace-io + wiki-io (post-rebrand) pages | Two pages; catches rename-and-delegation pattern. | |
| workspace-io + wiki-io + plugin mention | Three pages; broadest spot-check. | |

**User's choice:** workspace-io page only — frontmatter + body + at least one wikilink.
**Notes:** SC#2 says "at least one"; one suffices. Other pages validated implicitly via scan output without explicit spot-check.

---

## SC#3 query scope

| Option | Description | Selected |
|--------|-------------|----------|
| Just `what is workspace-io?` (literal SC#3) | One query, full transcript pasted into VERIFICATION.md. | ✓ |
| + one rebrand-surface query (`what is .graph-wiki.yaml?`) | Two queries; deeper rebrand-surface coverage. | |
| + comparison vs Phase 14 plugin transcript | Run via CLI, then diff against `14-VERIFICATION.md`. Catches Bedrock vs Claude divergence. | |

**User's choice:** Just `what is workspace-io?` (literal SC#3).
**Notes:** SC#3 names exactly this query. The implicit cross-surface comparison (Phase 14 transcript exists for the same query via plugin) is available without making it part of SC.

---

## Plan structure

| Option | Description | Selected |
|--------|-------------|----------|
| 1 atomic plan | All steps in one plan: models-claude.toml + scan + ingest + query + spot-check + VERIFICATION.md + commit. Matches Phase 14 Plan 3 bundled-port pattern. | ✓ |
| 2 plans — setup+scan, then ingest+verify | Modest split; lets scan ship independently. | |
| 3 plans — scan, ingest, verify | One plan per SC; most granular. | |

**User's choice:** 1 atomic plan.
**Notes:** Phase is short (one requirement, three SC, CLI-only). Bundled plan matches the user's pattern lately of fewer, larger plans on mechanical work.

---

## Claude's Discretion

- Exact CLI flag name for the model-override config (`--models-config`, `--profile`, etc.) — executor confirms during scout.
- Per-role `max_tokens` / `max_concurrency` in `models-claude.toml` — default to Qwen-profile values unless Claude-family practical limits differ.
- Whether to also spot-check the `prompt-sources` page (another new package scan will surface) — SC#2 says "at least one"; one suffices.
- Exact `15-VERIFICATION.md` layout — follow `14-VERIFICATION.md` template if present.
- Whether `models-claude.toml` is committed at repo root or kept gitignored (recommendation: commit; matches `models-qwen.toml`).

## Deferred Ideas

- Wiki-side `.graph-wiki.yaml` manifest (BRAND-03 mentions it; deferred — no current vault manifest).
- Bedrock vs Claude Code cross-surface diff (5-10 query librarian audit) — milestone audit candidate.
- Stale-content sweep across wiki pages — not required by SC#1.
- Qwen profile rebaseline + cost-frontier comparison vs Claude override — future cost-frontier work.
- Lint pass before/after — no SC backs it.
- Promote `models-claude.toml` to default profile — pending quality measurement.
- Spot-check additional pages (`wiki-io` post-rebrand, plugin entry).
- Phase 14 plugin transcript semantic diff — milestone audit candidate.
