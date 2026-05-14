# Phase 5: Remaining Commands - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md — this log preserves the alternatives considered.

**Date:** 2026-05-14
**Phase:** 5-remaining-commands
**Areas discussed:** ingest scope, Scanner fan-out role, Lint mechanical pass depth, --config flag delivery (CLI-05)

---

## ingest scope

| Option | Description | Selected |
|--------|-------------|----------|
| Source files only | Port ingest_source.py only; work-item ingestion deferred | |
| Both source + work items | Port both modules; full parity | ✓ |
| You decide | Planner picks based on CMD-03 scope | |

**User's choice:** Both source + work items

---

| Option | Description | Selected |
|--------|-------------|----------|
| LLM routes + summarizes | Ingestor subagent determines target page type AND generates summary | ✓ |
| Deterministic route, LLM summarizes | Port guess_source_type() for routing; LLM only writes summary | |
| You decide | Planner matches current tool behavior | |

**User's choice:** LLM routes + summarizes

---

| Option | Description | Selected |
|--------|-------------|----------|
| Yes — full cross-ref update | Update index.md and wikilink back-references in related pages | ✓ |
| Log + page only, no cross-refs | Write page and log only; skip cross-ref updates for v1 | |
| You decide | Planner ports from ingest_source.py flow | |

**User's choice:** Yes — full cross-ref update

---

| Option | Description | Selected |
|--------|-------------|----------|
| Separate subcommand: ingest source / ingest work-item | Two distinct CLI subcommands | ✓ |
| Single ingest command with --type flag | One command, auto-detects or flag | |
| You decide | Planner picks based on how lattice-wiki exposes these today | |

**User's choice:** Separate subcommand: `code-wiki-agent ingest source` / `code-wiki-agent ingest work-item`

---

## Scanner fan-out role

| Option | Description | Selected |
|--------|-------------|----------|
| LLM writes the stub body | Scanner subagent generates stub content from metadata + file_map + source samples | ✓ |
| Template-based stub, no LLM | Deterministic template from scan_monorepo data | |
| You decide | Planner matches lattice-wiki-core scan behavior | |

**User's choice:** LLM writes the stub body

---

| Option | Description | Selected |
|--------|-------------|----------|
| Metadata + file_map only | Fast, low token cost | |
| Metadata + file_map + source file samples | Richer summary; uses pick_representative() | ✓ |
| You decide | Planner picks quality vs. cost tradeoff | |

**User's choice:** Metadata + file_map + source file samples

---

| Option | Description | Selected |
|--------|-------------|----------|
| Mark + log, no auto-delete | Flag rename/deletion in diff + log; mark vault page stale | ✓ |
| Auto-delete stale pages | Remove vault pages for missing packages | |
| You decide | Planner matches lattice-wiki-core scan behavior on deletions | |

**User's choice:** Mark + log, no auto-delete

---

## Lint mechanical pass depth

| Option | Description | Selected |
|--------|-------------|----------|
| Port all 7 rule modules | Full mechanical parity with lattice-wiki-core | ✓ |
| Port only rules in success criterion 3 | Minimum set for success criteria | |
| You decide | Planner maps SC3 to modules | |

**User's choice:** Port all 7 rule modules (container, dependency, domain, file_map, package_sync, source_sync, workflow_hints)

---

| Option | Description | Selected |
|--------|-------------|----------|
| Mirror the mechanical modules | One semantic subagent per module | |
| Fewer broader groups | 3 groups: page quality/contradictions, ADR chain integrity, stale claims/code-drift | ✓ |
| You decide | Planner designs parallelizable groups | |

**User's choice:** 3 broader semantic groups

---

| Option | Description | Selected |
|--------|-------------|----------|
| Structured JSON (--json) + human text (default) | Consistent with all other commands | ✓ |
| Write report back to vault (lint.md) | Persisted wiki page | |
| You decide | Planner matches CMD-05 + CMD-07 | |

**User's choice:** Structured JSON (--json) + human text (default); no vault write-back

---

## --config flag delivery (CLI-05)

| Option | Description | Selected |
|--------|-------------|----------|
| Global app-level option | Typer callback; available on all subcommands automatically | ✓ |
| Per-subcommand flag | Each subcommand gets its own --config | |
| You decide | Planner picks Typer pattern | |

**User's choice:** Global app-level option

---

| Option | Description | Selected |
|--------|-------------|----------|
| models.toml path only | Simple, focused | |
| Full config file (models + settings) | JSON/TOML: models_path, vault_path, other settings | ✓ |
| You decide | Planner picks minimal CLI-05 implementation | |

**User's choice:** Full config file (models + settings); planner designs schema

---

| Option | Description | Selected |
|--------|-------------|----------|
| Env var for MCP (CODE_WIKI_CONFIG) | Same pattern as CODE_WIKI_REAL_VAULT_PATH | ✓ |
| CLI only, MCP deferred | Config override deferred for MCP | |
| You decide | Planner picks minimal approach | |

**User's choice:** CODE_WIKI_CONFIG env var for MCP server

---

## Claude's Discretion

- **MCP ingest tool split** — one `wiki_ingest` tool with a `type` field vs. two tools (`wiki_ingest_source`, `wiki_ingest_work_item`); planner decides
- **Scanner source file sampling heuristic** — which files count as "representative" for a given package; planner designs using existing `pick_representative()` in scan_monorepo.py
- **Config file format** — JSON vs. TOML; planner picks (TOML likely given models.toml precedent)
- **Cross-ref update scope for ingest** — index.md rebuild vs. selective back-ref updates; planner ports from ingest_source.py main() flow
- **`--stale-days` / `--log-gap-days` defaults for lint** — planner reads lint_wiki.py for current defaults

## Deferred Ideas

- Eval baselines for scan/lint/ingest/log — after Phase 4 infrastructure is ready
- `ingest` cross-ref deep linking beyond index.md — potentially scoped down if too costly
- Scanner stub slug collision handling — last-write-wins acceptable for v1
- `wiki_ingest_work_item` MCP exposure — may be CLI-only if too specialized
- Config schema versioning — not needed for v1
