---
phase: 15-wiki-self-update
plan: 01
subsystem: wiki-content
tags: [BRAND-03, wiki-self-update, bedrock-cli, claude-override]
requires: []
provides:
  - models-claude.toml (Phase 15 Claude role-override profile)
  - wiki-config-claude.toml (one-off WikiConfig for Claude profile)
  - 15-VERIFICATION.md (SC#1/#2/#3 evidence for BRAND-03)
affects:
  - ~/Personal/graph-wiki/agent-research (separate git repo — vault-side mutations not coordinated by this commit)
tech_stack_added: []
patterns: [provenance-header-toml, phase-verification-doc, four-backtick-fenced-transcript]
key_files_created:
  - models-claude.toml
  - wiki-config-claude.toml
  - .planning/phases/15-wiki-self-update/15-VERIFICATION.md
  - .planning/phases/15-wiki-self-update/15-01-SUMMARY.md
key_files_modified: []
decisions:
  - "Always pass --vault alongside --config when invoking graph-wiki-agent — the --config flag's vault_path is not propagated to scan/ingest/query subcommands (auto-fix Rule 1 finding during this plan)"
  - "Wiki CLAUDE.md layout block must reflect current repo directory names; the cores→packages rename from Phase 12 was not propagated until this run (auto-fix Rule 1 finding)"
  - "BM25 index requires manual rebuild after scan; the scan does not refresh .graph-wiki/bm25/ automatically (auto-fix Rule 1 finding)"
metrics:
  duration_seconds: 1229
  tasks_completed: 8
  files_created: 4
  files_modified: 0
  completed: 2026-05-19
---

# Phase 15 Plan 01: Wiki Self-Update — Summary

Drove a `graph-wiki-agent scan + ingest + query` pass against `~/Personal/graph-wiki/agent-research` using a one-off Claude role-override profile (Haiku 4.5 fan-out + Sonnet 4.6 reasoning) to bring the wiki into alignment with the post-rebrand codebase. Captured SC#1/#2/#3 evidence in 15-VERIFICATION.md, satisfying BRAND-03 and closing Phase 15.

## Commits

| Commit | Subject | Files |
|--------|---------|-------|
| `d7ed161` | `feat(15-01): add models-claude.toml + wiki-config-claude.toml for Phase 15 wiki self-update` | `models-claude.toml` (new), `wiki-config-claude.toml` (new) |
| `8147689` | `docs(15-01): capture Phase 15 SC#1/#2/#3 evidence — closes BRAND-03` | `.planning/phases/15-wiki-self-update/15-VERIFICATION.md` (new) |

## Repo Artifacts Produced

1. **`models-claude.toml`** — Phase 15 Claude role-override profile. 10 `[roles.*]` tables; fan-out roles (scanner, linter, ingestor, code_reader) on Claude Haiku 4.5; reasoning roles (librarian, synthesizer) on Claude Sonnet 4.6; judge rows preserved verbatim from `models-qwen.toml`. Reusable for any future Claude-profile run.

2. **`wiki-config-claude.toml`** — Two-line WikiConfig pointing `models_path` at `models-claude.toml` and `vault_path` at `/Users/pat/Personal/graph-wiki/agent-research`. `wiki-config.toml` (default Qwen profile) was NOT modified.

3. **`.planning/phases/15-wiki-self-update/15-VERIFICATION.md`** — SC#1/#2/#3 evidence: scan-log excerpt, workspace-io page spot-check (4 data points captured at Task 6 checkpoint, accepted by human verifier), and full query transcript in a four-backtick fenced block. Three operational deviations from spec documented honestly.

## Vault-Side Artifacts (External to This Repo)

The wiki vault at `~/Personal/graph-wiki/agent-research` is a separate git repo; commits there are out of scope for this plan per D-10. The Phase 15 scan/ingest produced:

- `~/Personal/graph-wiki/agent-researchpackages/workspace-io/workspace-io.md` — **new**, scan-produced. Subject of SC#2 spot-check. Frontmatter parseable; body has 3 key claims about workspace-io's responsibilities (config resolution, manifest IO, init, version tracking).
- `~/Personal/graph-wiki/agent-researchplugins/graph-wiki/graph-wiki.md` — **new**, scan-produced as a bonus product of the same scan; not required by SC but mentioned as supplementary SC#2 evidence in the verification doc.
- `~/Personal/graph-wiki/agent-researchsources/otel-story-observability.md` — **new**, ingest-produced. The single OTel source doc summary per D-04. Frontmatter has all required fields; summary cites the source URL and author.
- `~/Personal/graph-wiki/agent-researchindex.md` — refreshed by the scan to include the new `workspace-io` and `graph-wiki` entries.
- `~/Personal/graph-wiki/agent-researchlog.md` — appended with the successful scan-log entry `## [2026-05-18] scan | scan complete: +2 ~0 -0` (SC#1 evidence).
- `~/Personal/graph-wiki/agent-researchCLAUDE.md` — layout block updated by the executor (auto-fix Rule 1) to replace stale `source: cores` with current `source: packages`, add `plugins` container, remove stale `lattice` container, and bump `children_count`. Documented under Deviation 2 in 15-VERIFICATION.md.

## SC Evidence Pointer

Full SC#1/#2/#3 evidence — including the literal scan-log excerpt, workspace-io page spot-check (path + frontmatter + key claims + resolved inbound wikilink), and the full librarian query transcript — is captured in:

→ **`.planning/phases/15-wiki-self-update/15-VERIFICATION.md`**

Status in that doc's frontmatter: `passed`.

## Deviations from Plan

Three operational deviations were encountered during Tasks 3–5 and auto-fixed inline per Rule 1 (bug fix). All three are documented in detail under `## Deviation from spec` in 15-VERIFICATION.md. Brief summary:

1. **[Rule 1 - Bug] `--config` does not propagate `vault_path` to subcommands.** First scan ran against the dogfood vault (`/Users/pat/Personal/agent-research/graph-wiki/wiki`) instead of `~/Personal/graph-wiki/agent-research` because `--vault` was not passed. Stale-tagged 28 dogfood pages; fix removed those tags; subsequent invocations always passed `--vault`.
2. **[Rule 1 - Bug] Stale `cores/` layout block in wiki CLAUDE.md.** The `cores → packages` rename from Phase 12 was not reflected in the wiki's pinned-containers layout block; `discover_workspaces` found no packages. Updated the layout block to current repo state; removed stale tags from 4 wiki package pages.
3. **[Rule 1 - Bug] BM25 index not auto-rebuilt after scan.** First query returned "vault does not document this"; manually rebuilt the index via `build_index(vault)`; second query returned the expected librarian-synthesized answer.

## SC#2 Wikilink-Criterion Interpretation

The scan-produced `workspace-io.md` stub has no outbound `[[wikilinks]]` in its body — this is documented design behavior for scanner stubs (all existing stub pages in this vault behave the same way). At the Task 6 checkpoint, the human verifier accepted the interpretation that SC#2 criterion 4 ("at least one `[[wikilink]]` resolves to an existing page") is satisfied by the inbound wikilink from `index.md` to `workspace-io.md`. This is recorded under `## Deviation from spec` in 15-VERIFICATION.md; status stays `passed`.

## BRAND-03 / Phase 15

BRAND-03 satisfied. Phase 15 closes.

## Self-Check: PASSED

Created files (all exist on disk):
- FOUND: `models-claude.toml`
- FOUND: `wiki-config-claude.toml`
- FOUND: `.planning/phases/15-wiki-self-update/15-VERIFICATION.md`
- FOUND: `.planning/phases/15-wiki-self-update/15-01-SUMMARY.md` (this file)

Commits (all in git log):
- FOUND: `d7ed161` (configs)
- FOUND: `8147689` (verification)

Vault-side artifacts (verified by Read tool during execution):
- FOUND: `/Users/pat/Personal/graph-wiki/agent-researchpackages/workspace-io/workspace-io.md`
- FOUND: `/Users/pat/Personal/graph-wiki/agent-researchplugins/graph-wiki/graph-wiki.md`
- FOUND: `/Users/pat/Personal/graph-wiki/agent-researchsources/otel-story-observability.md`
