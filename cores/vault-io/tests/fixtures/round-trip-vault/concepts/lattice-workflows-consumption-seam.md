---
title: lattice-workflows consumption seam
category: concept
summary: Five integration patterns through which lattice-workflows consumes the lattice ecosystem — pre-explore hook, grep replacement, work-item filing, prioritization, status reporting. Workflow is a consumer, not a writer; new pages go through wiki's ingest pathway.
tags: [workflows, code-wiki, code-graph, work-tracker, integration, principles]
sources: 3
updated: 2026-05-09
tokens: 2704
---

# lattice-workflows consumption seam

## Definition
[[wiki/plugins/lattice-workflows/lattice-workflows]] consumes the rest of the lattice ecosystem through five named integration patterns. ==Workflow is a consumer, not a writer.== It reads vault content, queries the graph, reads the work-tracker sidecar; the only write path is filing new work items, which goes **through** [[wiki/plugins/lattice-wiki/lattice-wiki]]'s ingest mechanism rather than directly editing the vault.

## What workflow reads vs. writes

| Source | What | When | Interface |
|---|---|---|---|
| **lattice-wiki vault** | `<vault>/index.md`, package / work / concept / source pages | Pre-explore; planning; locating prior work | Direct file reads |
| **lattice-graph** | `cg_find`, `cg_callers`, `cg_callees`, `cg_describe_package`, `cg_describe_path` | Anytime an agent needs to understand or navigate code | MCP tools in-session; CLI fallback for subagents |
| **lattice-work sidecar** | `<vault>/work-index.json` | Prioritization, status, finding related work | Direct file read (JSON parse) |

| Target | What | When | Interface |
|---|---|---|---|
| **New work pages** | `category: work` page with `kind`, `severity`, `affects`, `## Plan` table | When workflow identifies a follow-up that shouldn't become a TODO comment | Cross-plugin call to `${LATTICE_WIKI_ROOT}/scripts/ingest_work_item.py` |
| **Status transitions** | Frontmatter updates (`status`, `updated`, `resolved_in`) | When work moves `accepted` → `in-progress` → `resolved` | Direct edit of the markdown file (one-line frontmatter changes) |
| **Activity log** | Appends to `<vault>/log.md` | After each cross-plugin write | Direct append (matches wiki's `append_log.py`) |
| **Sidecar regen trigger** | Calls `${LATTICE_WORK_ROOT}/scripts/regenerate_work_index.py` | After work-page mutation | Cross-plugin invocation per [[wiki/concepts/lattice-cross-plugin-contract]] |

==The asymmetry — full ingest for new pages, direct edits for status — matches risk:== creating a new page is structured + needs validation; toggling a status field is a one-line edit that doesn't touch schema.

> [!note] Workflow also writes workspace-sibling artifacts
> Per [[wiki/adrs/0013-plans-and-specs-in-lattice-workspace]] (and [[wiki/sources/2026-05-plans-specs-path-redesign]]), the `brainstorming` and `writing-plans` skills now write into `<workspace>/specs/` and `<workspace>/plans/` — workspace siblings of `wiki/`, not vault interior. The "consumer, not writer" principle is specifically about the *vault*: new vault pages still go through `ingest_work_item.py`. Workflow now owns its own pair of workspace directories alongside what `lattice-workspace` and `lattice-work` own.

## The five integration patterns

### 1. Pre-explore hook (skill-only)

**Behavior:** Before an explore-style subagent runs grep / glob / Read storms, it reads `<vault>/index.md` plus the package pages of any path mentioned in the task. Sidesteps the "redundant rediscovery" cost.

**Implementation:** `pre-explore` skill in lattice-workflows, activated when explore-style subagents are invoked. Skill content: "Before using grep or Read on `<path>`, check whether `<path>` belongs to a package. If yes, read that package's wiki page first."

**No slash command** — agent-time behavior, not user-invoked.

**Degradation:** No vault → skill is a no-op; agent goes straight to grep.

### 2. Agent-time grep replacement (skill-only)

**Behavior:** Replace common grep loops with graph queries.

| Question | Old (grep) | New (graph) |
|---|---|---|
| Who calls `foo`? | `grep -rn 'foo(' src/` | `cg_callers(name='foo')` |
| What does `foo` call? | manual reading | `cg_callees(name='foo')` |
| Where is `LocationService` defined? | `grep -rn 'class LocationService'` | `cg_find(name='LocationService', kind='class')` |
| What's in this package? | `ls packages/x/src/` | `cg_describe_package(name='x')` |

**Implementation:** `prefer-graph-over-grep` skill. Emphasizes graph is best-effort (per §3.5 name-resolution limits); supplement with targeted grep when the answer matters and the graph result feels incomplete.

**Degradation:** No graph → skill warns; agent uses grep with a banner explaining the experience is degraded.

### 3. Issue/plan filing (slash command + skill)

**Behavior:** When workflow identifies a cleanup, defect, or follow-up, file a structured work item instead of leaving a TODO comment.

**Implementation:** `/lattice-workflows:file-work-item` (interactive) or skill-driven:
1. Determine `kind` (per §2.4).
2. Fill required frontmatter (title, summary, kind, status: open, affects:, opened:).
3. Optional: stub a `## Plan` table.
4. Invoke `${LATTICE_WIKI_ROOT}/scripts/ingest_work_item.py --frontmatter <yaml> --body <markdown>`.
5. After ingest, invoke `${LATTICE_WORK_ROOT}/scripts/regenerate_work_index.py`.
6. Append to `<vault>/log.md`.

**Degradation:** No wiki → error pointing at `/lattice-wiki:init`. No work-tracker → skip regen step; next `/lattice-work:lint` rebuilds the sidecar.

### 4. Prioritization — "what should I work on?"

**Behavior:** Read `work-index.json`, rank candidates, surface top N.

**Implementation:** `/lattice-workflows:next` reads the sidecar directly. **No graph required, no MCP required.** Default ranking: `status: accepted` items first, then `status: open` filtered by `severity: high|critical`. Tie-break by `updated:` (oldest first — staleness signal). Cap at 10.

Args: `--kind <kind>`, `--severity <severity>`, `--package <package>`, `--limit <n>`. Output: human-readable table by default; `--json` for structured.

**Degradation:** No work-tracker / no sidecar → guidance message: "Install lattice-work and run `/lattice-work:regen-index` to enable prioritization."

### 5. Status reporting

**Behavior:** "What's the state of work for this project?" — counts by status / kind / blast_radius, plus highlights for stuck items and items in flight.

**Implementation:** `/lattice-workflows:status` reads the sidecar's `counts` block plus filters for `status: in-progress` and `stuck-open` / `stuck-accepted` items (using the same thresholds as `lattice-work:lint`). Same human-vs-`--json` dispatch as `cg status` (§3.4).

```
Lattice work surface — 2026-05-03

Open: 41   Accepted: 0   In-progress: 2   Resolved: 12   Stale: 7

In flight (status: in-progress):
  - work/2026-04-21-mongo-database-hardcoded (PR #142)

Stuck open (>30d):
  - work/2026-03-12-old-issue-x  (62d)
```

**Degradation:** No work-tracker → "no work surface available."

## lattice-experts' role in the seam

lattice-experts ships **knowledge skills** (not subagent definitions). The subagents themselves (`implementer`, `code-quality-reviewer`, `spec-reviewer`, `systematic-debuggers`) live in lattice-workflows.

- Each role's skill content references the lattice surfaces relevant to its domain. `implementer` says "use `cg_find` and `cg_describe_path` to locate before editing."
- **Per-role allowed-tools** (per §3.1's "subagent injection without global MCP pollution") — `cg` CLI is added to specific roles' allowed-tools instead of registering MCP server-wide. `implementer` and `code-quality-reviewer` get `cg`; `writing-plans` doesn't (planning is graph-light).
- Roles can invoke workflow's slash commands when needed (e.g., `systematic-debuggers` calls `/lattice-workflows:file-work-item` for out-of-scope defects).

==Roles is a *layer over* workflow, not a peer.== Workflow ships the framework; experts ships the role-aware knowledge.

## Graceful degradation matrix

| Peer present? | Pre-explore | Grep replacement | File work-item | Prioritize | Status |
|---|---|---|---|---|---|
| wiki + graph + work-tracker | full | full | full | full | full |
| wiki + work-tracker (no graph) | works | warn; grep fallback | full | full | full |
| wiki + graph (no work-tracker) | full | full | works (no regen) | error | error |
| wiki only | works | warn; grep only | full | error | error |
| graph only | n/a (no vault) | full | error: install wiki | error | error |
| nothing | grep only | grep only | error | error | error |

The "lowest common denominator" is grep-only; that's where a workflow user starts before any peer is installed. The rich experience is wiki + graph + work-tracker — the target setup.

## v1 deliverables

- Skill content for the five patterns
- Slash commands: `/lattice-workflows:next`, `/lattice-workflows:status`, `/lattice-workflows:file-work-item`
- Cross-plugin invocation helpers (subprocess + JSON parse)
- Compatibility declarations in `plugin.json` / README
- Inherited `claude-superpowers` hooks unchanged (session-start, pre-commit gate, etc. — general engineering discipline, not lattice-aware)

## Used in
- [[wiki/plugins/lattice-workflows/lattice-workflows]] — owner of the seam
- lattice-experts — knowledge layer over workflow
- [[wiki/plugins/lattice-wiki/lattice-wiki]] — read source + ingest target
- [[wiki/plugins/lattice-graph/lattice-graph]] — read source for grep replacement
- [[wiki/plugins/lattice-work/lattice-work]] — sidecar source for prioritize + status

## Related patterns
- [[wiki/concepts/lattice-cross-plugin-contract]] — env-var discovery, subprocess invocation, exit codes
- wiki-cites-graph-not-duplicates — analogous consumer-side relationship for the wiki

## Sources
- 2026-05-architecture-3.9-lattice-workflows-seam
- 2026-05-wiki-workflows-seam-parity — concretizes the v1 deliverables for the two-plugin slice (wiki + workflows); lands Patterns 1+3 fully and Patterns 2/4/5 as degraded stubs honoring this concept's graceful-degradation matrix
- [[wiki/sources/2026-05-plans-specs-path-redesign]] — adds workspace-sibling `specs/` and `plans/` write surfaces; preserves the consumer-of-vault principle; routes through `python -m lattice_workspace.config` for resolution

## Decisions
- adrs/0004-work-tracker-as-consumer-plugin — establishes the work-tracker side of the seam

## Open questions / deferred to v2
- Auto-prioritization considering graph data (callers of failing tests, recently-touched code).
- Workflow-driven schema evolution (proposing new `kind` values, etc.).
- Cross-tool consumption — workflow stays Claude-shaped at v1; CLI surfaces (per §3.1's shape-F) make individual tools cross-portable later.
- Roles auto-selecting based on task content.
