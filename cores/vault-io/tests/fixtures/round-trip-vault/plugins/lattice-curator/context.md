---
title: lattice-curator (plugin) — Context
category: package
summary: Plugin deployment shape, why it stays thin, and how it relates to the package library and the surrounding ecosystem.
tags: [plugin, context, rationale]
updated: 2026-05-09
tokens: 1364
---

# lattice-curator (plugin) — Context

## Concepts

### Deployment shape

A standard Claude Code plugin. The manifest (`plugins/lattice-curator/.claude-plugin/plugin.json`) declares:

- One slash command (`/curator:init`).
- One MCP server (`lattice-curator`).
- Two hooks (declared via `hooks/hooks.json`, the conventional location Claude Code reads).

The plugin assumes the `lattice-curator` Python package is importable from whatever environment runs the hook scripts — it imports `from lattice_curator_core import gate, retrieve, ...` directly. There is no path-dep declared in any manifest because Python imports use the active interpreter's site-packages. Whatever environment installs this plugin must also install the package (typically via the lattice meta-installer or a dev shell that points at the monorepo).

`lattice-workspace` (imported by `commands/curator_init.py`) is also a hard runtime dep — without it, `/curator:init` errors out cleanly. Worth declaring this in the manifest's `keywords` or a future `requires` field, but the Claude Code plugin schema doesn't have one today.

### Why the package/plugin split

The plugin is a thin adapter. Every interesting decision (gating, retrieval, formatting, schema validation, fail-silent semantics) lives in [[wiki/packages/lattice-curator-core/lattice-curator-core]]. The plugin's job is:

1. Translate Claude Code's hook payloads into the package's typed inputs (`GateInput`, `retrieve(...)`).
2. Persist a tiny amount of cross-turn state (`~/.cache/lattice-curator/state.json`).
3. Wire stdout to Claude Code's "inject extra context" channel.
4. Expose the same engine through MCP for explicit invocation.
5. Seed bundled rules into per-project `lattice/knowledge/` on init.

This split has three benefits:

- **The engine is reusable.** Eval harnesses, CI checks, and hypothetical future plugins (a Cursor extension, a CLI) get the same primitives.
- **The plugin is replaceable.** If the Claude Code hook contract changes, the plugin can be rewritten without touching gate/retrieve/format logic.
- **The boundary is testable.** The package has no `~/.cache` knowledge; the plugin has no LangGraph knowledge.

Mirrors the [[wiki/packages/lattice-source-parser/lattice-source-parser]] precedent.

### Why two hooks

`UserPromptSubmit` alone would force the gate to do all stage detection from the prompt + transcript tail. That works for keyword-y prompts ("debug this", "plan a refactor") but misses the strongest signal: Claude invoked a workflow skill in the previous turn. The `PreToolUse:Skill` hook records that signal asynchronously so the next prompt can use it.

The state is intentionally tiny (one JSON file, two top-level keys), local (per-machine `~/.cache`), and ephemeral (the user can delete it without consequence). It is not synced, not authoritative, and not consulted by anything outside the gate.

### Why `UserPromptSubmit` is `async: false`

The brief must land in the context window before Claude starts processing the prompt. `async: true` would let the prompt go through immediately and inject the brief into a later turn, which defeats the point. The cost is a synchronous [[wiki/concepts/bedrock-langgraph-stack|Bedrock]] round trip per fire — typically 1-3 seconds at default model size. The gate is designed to keep fire frequency low (`min_prompt_length=40`, `debounce_seconds=30`) so the per-turn cost amortizes.

### Why MCP exists alongside hooks

Two failure modes the gate cannot eliminate:

1. **False negatives** — the gate decides not to fire, but the user actually wanted curated context.
2. **Stage misroute** — the gate fires `generic` when `debugging` would have been better.

`context.fetch` is the user's escape hatch: Claude can invoke it explicitly with a forced `stage` and `hint`. Errors surface (no fail-silent), because the user explicitly asked for curation and a silent failure would be misleading.

The two paths are logged separately in `fires.jsonl` (different `outcome` values, different gate dicts) so eval reports can compare hook-driven vs tool-driven curation effectiveness.

### Per-repo data relationship

`/curator:init` calls `seed_knowledge(knowledge_dir(root))` where `knowledge_dir(root)` resolves to `<root>/lattice/knowledge/` via the `lattice-workspace` helper. Once seeded, the rule library is per-repo data — editable, gitignorable per project, replaceable. The plugin and the package itself remain global tooling. See [[wiki/concepts/per-repo-data-vs-global-tooling-tier]].

## Decisions

- adrs/0010-lattice-curator-as-fifth-plugin — placement, package vs plugin split, outside-the-loop posture.
- adrs/0012-python-bedrock-stack-for-curator — Python + LangChain/LangGraph + Pydantic + Bedrock stack.

## Sources

(No live source pages — upstream source docs were stripped at migration.)

## Belongs to domain

Context curation / Claude Code plugin ecosystem.

## Used by

- [[wiki/plugins/lattice-workflows/lattice-workflows]] — owns the workflow skills the `PreToolUse:Skill` hook tracks; skill invocations are the strongest gate signal.

## Related dependencies

- [[wiki/packages/lattice-curator-core/lattice-curator-core]] — the engine; this plugin is the only Claude-Code-shaped consumer.
- [[wiki/packages/lattice-workspace/lattice-workspace]] — required by `curator_init.py` for workspace root discovery and `knowledge_dir` resolution.
- [[wiki/plugins/lattice-wiki/lattice-wiki]] — wiki vault is one of the curator's two v1 knowledge surfaces.
- [[wiki/concepts/two-pass-context-curation]], [[wiki/concepts/curator-source-interface]] — pipeline + adapter patterns.
- [[wiki/concepts/per-repo-data-vs-global-tooling-tier]] — `lattice/knowledge/` after `/curator:init` is per-repo data; the plugin and the package are global tooling.
