---
title: Subagent vs teammate
category: concept
summary: Two distinct Claude Code mechanisms for off-main work — subagents (one-shot, return results, no peer messaging) vs agent-team teammates (persistent, peer-messaging, shared task list). Both lack `Agent` (no nested dispatch); they differ in lifetime, communication, and tool surface.
tags: [agent-teams, subagents, claude-code, lattice-workflows, harness, dispatch]
sources: 1
updated: 2026-05-09
tokens: 1209
---

# Subagent vs teammate

## Definition

Claude Code provides two distinct mechanisms for delegating work off the main session: **subagents** (dispatched via the `Agent` tool, one-shot, return results to the caller) and **agent-team teammates** (created via `TeamCreate` + `Agent` with `team_name`/`name`, persistent, communicate peer-to-peer via `SendMessage` and a shared task list). They are not interchangeable; their tool surfaces, lifecycles, and communication models differ.

Both are constrained by a harness invariant: **only the top-level session has `Agent`** (0012-claude-code-harness-dispatch-is-one-level). Neither subagents nor teammates can dispatch nested subagents.

## Motivation

Picking the wrong mechanism wastes tokens, complicates orchestration, or makes a workflow impossible. Subagents are right when:
- A task needs a clean context and you only need the result
- The work is bounded — no follow-up messaging, no peer coordination
- Token efficiency matters more than persistence

Teammates are right when:
- Multiple workers need to message each other (e.g. reviewer ↔ implementer feedback loops)
- The same worker may be re-engaged after returning ("you're done" → "fix this" → "you're done again")
- A shared task list with dependencies models the coordination naturally

The 2026-05-04 spike needed *both* peer messaging (review-loop without controller in the middle) and persistence (implementer alive when reviewer messages back). That ruled subagents out for that skill.

## Shape

```
                       Subagent                 Teammate
                       ────────                 ────────
Created by             Agent({...})             TeamCreate then Agent({team_name, name})
Communication          Result returns           SendMessage peer-to-peer; idle
                       to caller                notifications to lead
Lifetime               Until result returns     Persistent until shutdown_request
Context                Fresh per call           Fresh per spawn; survives idle
Tool surface
  Agent (nested)       NO                       NO
  TaskCreate/Update    NO                       YES (deferred)
  TaskList/Get         NO                       YES (deferred)
  SendMessage          YES (deferred,           YES (deferred,
                       to-caller only)          peer-addressable)
  Standard tools       YES                      YES
Bookkeeping            None                     ~/.claude/teams/<n>/, ~/.claude/tasks/<n>/
Cost                   Lower (single context)   Higher (each teammate is a session)
```

## Used in

- [[wiki/plugins/lattice-workflows/lattice-workflows]] — `subagent-driven-development` uses one-shot subagents for implementer / spec-reviewer / code-quality-reviewer dispatches.
- `.claude/skills/launching-plan-teams/` — uses agent-team teammates because review-loops need peer messaging and implementer persistence.

## Related patterns

- [[wiki/concepts/lead-nudge-protocol]] — teammate-specific gotcha: idle teammates don't auto-wake on dependency clear.
- [[wiki/concepts/shape-a-vs-shape-b]] — design choice within the agent-teams model (2 vs 3 teammates per plan).
- [[wiki/concepts/explicit-not-magic-update-lifecycle]] — same "explicit over implicit" posture; both subagent dispatch and teammate spawn require explicit instructions, no auto-discovery.
- [[wiki/concepts/execution-skills-comparison]] — one level up from this page: distinguishes the lattice-workflows *skills* (`executing-plans` / `subagent-driven-development` / `dispatching-parallel-agents`) that drive subagent dispatch.

## Sources

- [Anthropic agent-teams documentation](https://code.claude.com/docs/en/agent-teams) — canonical comparison; this concept page paraphrases and adds empirical findings.

## Open questions / gotchas

- **Task lifecycle in agent teams.** Empirically verified 2026-05-04: when a task in a team is marked `completed`, its underlying file in `~/.claude/tasks/<team>/` is **deleted**, not archived. `TaskList` shows completed tasks only while at least one peer task is still pending or in_progress; once *all* tasks are completed, `TaskList` returns "No tasks found" and `TaskGet` returns "Task not found" for the (now-gone) task IDs. Implication for skills: if you need a record of completed task descriptions for archival or auditing, capture it via `SendMessage` to the lead while the task is still pending — don't rely on retrieving it post-completion. The `.highwatermark` file ensures task IDs never repeat within a team's lifetime.
- ==Idle teammates do not auto-wake on dependency clear== — see 0013-reviewer-teammates-require-explicit-sendmessage-on-unblock.
- **Spawning a teammate vs dispatching a subagent uses the same `Agent` tool**, distinguished by presence/absence of `team_name`/`name` parameters. Easy to confuse; the dispatcher prompt should make the role explicit either way.
- **`/resume` does not restore in-process teammates.** Persistent doesn't mean session-survivable — only mid-session.
