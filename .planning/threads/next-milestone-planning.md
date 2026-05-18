---
slug: next-milestone-planning
title: next-milestone-planning
status: open
created: 2026-05-17
updated: 2026-05-17
---

# Thread: next-milestone-planning

## Goal

Capture ideas, scope, and candidate phases for the next deep-agents milestone while the current milestone audit and close-out runs in a parallel session. Promote the resulting material into ROADMAP.md once `/gsd-complete-milestone` finishes.

## Context

*Created 2026-05-17.*

Parallel-session constraint: another Claude session is currently running the milestone audit and will run `/gsd-complete-milestone`. To avoid file collisions, this thread restricts itself to capture/ideation only — no edits to ROADMAP.md, STATE.md, PROJECT.md, or the active milestone directory until that session finishes.

Project snapshot at thread creation:
- Current milestone: v1 of `code-wiki-agent` (Bedrock-hosted port of lattice-wiki).
- Most recent commits indicate Phase 9 gap-closure verified; `cores/` renamed to `packages/`.
- Tech stack locked: `uv` workspace, Python 3.11+, deepagents 0.6.1, langchain-aws 1.4.6, mcp 1.27.1, deepeval 4.0.0, typer 0.25.1. See `CLAUDE.md` for full table.
- Wiki vault for this project: `~/Personal/wiki/deep-agents` (Qwen3-32B fan-out, Qwen3-80B synthesis).

## References

- `CLAUDE.md` — locked stack and constraints
- `.planning/ROADMAP.md` — current milestone phases (do NOT edit from this thread)
- `Skill("spike-findings-deep-agents")` — implementation blueprint and proven patterns
- `~/Personal/wiki/deep-agents` — wiki for cross-reference

## Next Steps

1. Brainstorm candidate themes for next milestone (e.g., remote MCP transport, multi-vault support, eval-driven model auto-routing, agent observability, CI integration).
2. Use `/gsd-capture` to drop concrete items into the backlog as they crystallize — backlog writes don't conflict with milestone audit.
3. Optionally run `/gsd-explore` on the strongest theme for Socratic shaping.
4. Wait for the other session to confirm `/gsd-complete-milestone` finished.
5. Then run `/gsd-new-milestone` followed by `/gsd-review-backlog` to promote captured items into the new milestone's roadmap.
