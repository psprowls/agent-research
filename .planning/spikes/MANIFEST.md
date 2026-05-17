# Spike Manifest

## Idea

Audit subagent context loading in `agents/code-wiki-agent` against the original `lattice-wiki` Claude Code plugin. In Claude Code, when a skill triggers, the full `SKILL.md` is injected into subagent context and `CLAUDE.md` files (including the wiki-root `CLAUDE.md` with its layout block) are surfaced. In the Python port, each subagent's `SystemMessage` is hand-assembled from a small set of fragments. We may be missing load-bearing context.

## Requirements

Decisions that emerged during the spike. Non-negotiable for the follow-on phase:

- Preserve the existing curation discipline — fragments carry source provenance (`# Source:` / `# Anchor:` / `# Source-commit:`) and that convention must extend to any new fragment.
- Stay within the cost-optimization mindset. Added context per fan-out call should justify itself; aim < ~1,500 added tokens per role.
- Do **not** require a deepagents migration to fix this. The subagent dispatch primitive is the custom `cores/subagent-runtime/pool.py` `SubagentPool`, not `deepagents.SubAgentMiddleware`. A virtual-filesystem solution is out of scope until that architecture decision is taken separately.
- Project-specific context (wiki `CLAUDE.md` layout block, container pins) must reach subagents that scan/lint/ingest. Static skill content alone is not enough — the layout differs per project.

## Spikes

| # | Name | Type | Validates | Verdict | Tags |
|---|------|------|-----------|---------|------|
| 001 | subagent-context-audit | standard | Given current `prompts/*.py` and `cores/prompt-sources/SKILL.md` + `lattice/wiki/CLAUDE.md`, identify load-bearing chunks dropped, confirm wiki CLAUDE.md is data-only, estimate injection token cost on Bedrock fan-out, and recommend an injection strategy | VALIDATED ✓ | context, prompts, audit, subagents, bedrock |
