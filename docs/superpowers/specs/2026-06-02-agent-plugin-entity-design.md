# Design: the `agent-plugin` wiki/graph entity

**Date:** 2026-06-02
**Status:** Approved (design); ready for implementation planning
**Author:** Pat (with Claude)

## Summary

Introduce an `agent-plugin` entity to the graph-wiki system that documents **agent plugins under development** — claude-code plugins (and, eventually, other agent/plugin ecosystems) treated as **development projects**, not as installed dependencies in use. The entity documents the plugin's internal components — slash-commands, agents/subagents, skills, scripts, hooks, and bundled MCP servers — as a regenerable, drift-aware inventory.

This **repurposes and renames** the existing `plugin` entity, whose current "installs and uses" / consumer semantics are wrong for this purpose and are dropped.

## Motivation

The existing `plugin` entity documents the *consumer* side: plugins a repo installs and uses. It is sourced from `.graph-wiki.yaml`'s `plugins[]` array, gets a concept-level URI (`plugin:{name}`), carries `installed_version`/`applied_version`, and its template asks "what does this plugin do / how we use it" (`packages/wiki-io/src/wiki_io/assets/page-templates/entity-plugin.md:16-19`). Plugin nodes deliberately have no edges (`packages/graph-io/src/graph_io/plugins.py:23-26`).

What we want is the **producer/authoring** side: a plugin being *developed* in a repo, with its slash-commands, agents, skills, workflows, and scripts documented as first-class internal components. A plugin-under-development directory (e.g. this repo's own `plugins/graph-wiki/`) currently has no good home — the scan path either ignores it (the graph build) or treats it as a generic `tool`/`package` workspace (legacy `scan_monorepo.py`).

## Decisions

1. **Repurpose + rename** `plugin` → `agent-plugin`. Drop the consumer/"installs and uses" semantics entirely. The name `agent-plugin` adds specificity (vs. generic "plugin").
2. **Modeling approach:** the *entity itself* is a graph node (required by the graph-driven scan flow); the *internal components* are NOT graph nodes/edges. Components ride as structured inventory in the node's `attrs_json` and are rendered into page sections. Inferred cross-component relationships are expressed as **prose**, not graph edges. (Rationale below.)
3. **Ecosystem scope (v1):** claude-code only for detection and scanning, but the schema is ecosystem-neutral and carries an `ecosystem` field so other frameworks slot in later without redesign.
4. **Classification:** a directory with `.claude-plugin/plugin.json` reclassifies as `agent-plugin` — **not** as a `package`/`tool`. It no longer appears in the package list. Bundled helper scripts that are real workspace packages (their own `pyproject.toml`/`package.json`) are still detected separately by their own manifests.
5. **First-class components:** slash-commands, agents, skills, scripts (workflow scripts fold into scripts — no separate "workflow" section), **hooks**, and **bundled MCP servers**.
6. **Option C (promote components to real graph nodes + edges) is kept open as a nice-to-have, not a requirement.** The design captures component identity at graph-build time so a future promotion is a non-breaking extension, but no graph node/edge kinds for components are added now.

### Why components are prose/attrs, not graph edges

The code graph's value is *traversable edges*. A plugin's component inventory is a flat, ~1-level containment list that a table renders perfectly — a graph adds nothing there. The edges that *would* justify a graph are cross-component relationships (command → dispatches → agent; skill → calls → script). Those relationships live in prose (a command's markdown describes what it invokes in a sentence), so deriving them requires LLM inference, not parsing. A graph edge is an authority claim; a wrong *inferred* edge is unfalsifiable noise that erodes trust in the whole graph and can't be cheaply revalidated on the next scan. The code graph's deterministic extraction is already lossy in this repo (arrow-consts dropped, `.tsx` parsed JSX-blind, import specifiers unresolved) — bolting an inference layer onto that substrate is the wrong place to take on a harder precision problem.

Therefore: deterministic inventory → scanner (valuable, reliable, drift-aware). Inferred relationships → prose (the honest medium). The clean trigger to revisit Option C is when relationships become **declared** rather than inferred (e.g. if claude-code's `plugin.json`/skill frontmatter ever grows explicit `uses_skills:` / `dispatches_agents:` fields) — then they become deterministic edges and the graph earns its place.

## Target flow

This design targets the **graph-driven `gw scan` flow** (`packages/graph-wiki-cli` → `packages/graph-wiki-core/src/graph_wiki_core/commands/scan.py`), **not** the stale `packages/wiki-io/src/wiki_io/scan_monorepo.py` plugin path. The graph-wiki plugin's own scan will be reworked to adopt this graph-based scanning separately.

In the `gw scan` flow:
- `cg update` builds/updates the code graph (SQLite) first; this is where plugin nodes originate today (`graph_io/update.py:321` calls `plugins.emit()`).
- `write_entities(conn, wiki, ADMITTED_KINDS)` renders entity pages **from the graph** (`packages/wiki-io/src/wiki_io/entity_writer.py`).
- A narrator fan-out (Step 9b of `run_scan`) generates LLM prose for entity pages.

So the entity must be a graph node to get a page, and the inferred-relationship prose is produced by the existing narrator fan-out.

## Architecture

### Two layers, treated differently

- **The `agent-plugin` entity → a graph node.** New node `kind` in `graph_io/queries.py` `_VALID_KINDS` and in `entity_writer.ADMITTED_KINDS`. URI is **repo-scoped**: `agent_plugin:{org}/{repo}/{name}` (a development artifact lives in a specific repo — unlike the retired concept-level `plugin:{name}`).
- **Internal components → `attrs_json` on the agent-plugin node, rendered to page sections.** No `command`/`skill`/etc. node kinds, no edges. Each component carries a stable id (the cheap insurance for Option C).

### 1. New filesystem detector in `graph-io` (replaces `plugins.py`)

Replace the manifest-driven consumer ingestion (`graph_io/plugins.py`, which reads `.graph-wiki.yaml plugins[]`) with a filesystem-walking detector (e.g. `graph_io/agent_plugins.py`), wired into the graph build where `plugins.emit()` is called today (`graph_io/update.py:321`). It:

- `rglob`s `.claude-plugin/plugin.json` (reusing the vendored/fixture filtering the legacy walker applies).
- Reads the manifest (`name`, `version`, `description`).
- Parses each component type (globs in §3) into an inventory.
- Emits **one `kind:agent-plugin` node** per plugin with:
  - repo-scoped URI `agent_plugin:{org}/{repo}/{name}` (new builder in `graph_io/uri.py`),
  - `attrs_json` carrying `ecosystem: "claude-code"`, manifest fields, and the component inventory (each component with its stable id).

**Retire the consumer ingestion:** `.graph-wiki.yaml plugins[]` → `kind:plugin` is removed. The `plugins[].roles[]` model-role config is a *different consumer* (`make_llm`) and is untouched.

### 2. Classification / no double-counting

Plugins already bypass `graph_io/classification.py` (manifest-driven, fixed kind); the new detector does the same, emitting `kind:agent-plugin` directly. New requirement: ensure a `.claude-plugin/plugin.json` directory is **excluded from the package emitter** so it does not also produce a `package` node. This exclusion is the concrete meaning of the "reclassify, not both" decision.

### 3. Component inventory (node attrs → rendered sections)

Six first-class component types, parsed at graph-build time into the node's attrs, rendered by `entity_writer` into scanner-owned sections:

| Section | Discovery glob | Fields read | Stable id |
|---|---|---|---|
| Commands | `commands/*.md` | `name`, `description` | `command:{org}/{repo}/{plugin}/{name}` |
| Agents | `agents/*.md` | `name`, `description`, `model`, `tools` | `agent:{org}/{repo}/{plugin}/{name}` |
| Skills | `skills/*/SKILL.md` | `name`, `description` | `skill:{org}/{repo}/{plugin}/{name}` |
| Scripts | `scripts/**` (incl. workflow scripts) | path, lang | `script:{org}/{repo}/{plugin}/{path}` |
| Hooks | `hooks/hooks.json` | event → matchers | `hook:{org}/{repo}/{plugin}/{event}` |
| MCP servers | `.mcp.json` | server name, command | `mcp_server:{org}/{repo}/{plugin}/{name}` |

These ids are page-local identifiers stored in attrs, **not** graph nodes. They make Option C a non-breaking extension later.

### 4. Page template + prose relationships

- New template `entity-agent-plugin.md` replaces `entity-plugin.md`. Filename prefix `agent-plugin_{name}.md`.
- Section layout (scanner-owned vs. human-preserved follows the existing narrative/whitelist mechanism in `merge_frontmatter`):

```
---
title, uri, kind: agent-plugin, ecosystem, graph_name, last_scan_at, updated
---
# {{plugin_name}}
## Narrative              ← scanner/narrator-populated
## Purpose                ← human: what this plugin does, what host surface it adds
## Commands              ┐
## Agents                │
## Skills                ├ scanner-owned inventory tables (§3)
## Scripts               │
## Hooks                 │
## MCP servers           ┘
## How it fits together   ← narrator PROSE: inferred cross-component relationships (§ rationale)
## Concepts / Decisions / Contrasts  ← existing wikilink cross-refs
```

- The **"How it fits together"** prose (inferred cross-component relationships) is generated by the **existing narrator fan-out** (Step 9b of `run_scan`).

### 5. `entity_writer` wiring

- Add `agent-plugin` to `ADMITTED_KINDS`, `_URI_PREFIX_BY_KIND`, `_FILENAME_PREFIX_BY_URI_PREFIX` (`packages/wiki-io/src/wiki_io/entity_writer.py:60-70,80-90,148-157`).
- Add `list_agent_plugins` / `describe_agent_plugin` queries in `graph_io/queries.py` (mirroring `list_plugins`).
- `scanner_frontmatter_for_node` gains an `agent-plugin` branch that surfaces manifest fields to frontmatter and hands the component inventory to the template renderer for the section tables.

### 6. Migration

Per the project backward-compatibility rule (`.claude/rules/backward-compatibility.md`): no data migration. `agent-plugin` is a new kind; old `plugin:*` nodes and `plugin_*.md` pages disappear when the consumer ingestion is removed and the wiki is rebuilt. The user delete-and-rebuilds the wiki/graph.

## Out of scope

- **Option C** — promoting components to first-class graph nodes (`command`, `agent`, `skill`, …) with containment/relationship edges. Kept architecturally open (component ids captured at build time) but not implemented.
- **Non-claude-code ecosystems** — schema is neutral and carries `ecosystem`, but only claude-code is detected/parsed in v1.
- **A separate "workflow" component section** — workflow scripts fold into Scripts.
- **Reworking the graph-wiki plugin's own scan path** to adopt graph-based scanning — tracked separately.

## Key files

| Concern | File |
|---|---|
| `gw scan` CLI entry | `packages/graph-wiki-cli/src/graph_wiki_cli/cli.py:569-596` |
| Scan orchestrator | `packages/graph-wiki-core/src/graph_wiki_core/commands/scan.py:556-1175` |
| Graph build wiring (plugin emit call) | `packages/graph-io/src/graph_io/update.py:321` |
| Consumer ingestion to retire | `packages/graph-io/src/graph_io/plugins.py` |
| URI builders | `packages/graph-io/src/graph_io/uri.py:50-51` |
| Valid node kinds | `packages/graph-io/src/graph_io/queries.py` (`_VALID_KINDS`) |
| Package classification (exclusion needed) | `packages/graph-io/src/graph_io/classification.py` |
| Entity writer / admitted kinds | `packages/wiki-io/src/wiki_io/entity_writer.py:60-70,148-157,705-869` |
| Current plugin template (to replace) | `packages/wiki-io/src/wiki_io/assets/page-templates/entity-plugin.md` |
| Frontmatter schema reference | `plugins/graph-wiki/skills/graph-wiki/references/wiki-schema.md` |
