---
title: "/release: branch gate + post-release wiki sync"
category: source
summary: Design spec for two additive changes to the repo-level `/release` slash command (`.claude/commands/release.md`) — a new Step 0 that aborts when HEAD is not on `main` (including detached HEAD), and a new Step 9 that, after a successful push, offers to dispatch the `lattice-wiki:scanner` sub-agent and commit any resulting wiki updates as a follow-up. Already shipped; the implementation also extends the spec with a Step 9c that runs `cg update` + `cg sync-wiki` before the scanner so the graph is current.
source_path: lattice/specs/2026-05-11-lattice-release-wiki-sync-design.md
source_type: doc
source_date: 2026-05-11
authors: []
status: draft
ingested: 2026-05-11
updated: 2026-05-11
tags: [release, slash-command, lattice-wiki, scanner, branch-gate, wiki-sync, claude-code-commands]
tokens: 1869
---

# /release: branch gate + post-release wiki sync

## TL;DR

A design spec for two additive changes to the repo-level `/release` slash command in `.claude/commands/release.md` (the guided independent-versioning release flow that bumps plugins/packages and stamps an umbrella `vYYYY.MM.DD.N` tag). The spec adds a Step 0 **branch gate** that aborts when HEAD is not `main` (including detached HEAD), and a Step 9 **wiki sync offer** that, after a successful push, optionally dispatches the [[wiki/plugins/lattice-wiki/lattice-wiki]] `scanner` sub-agent and commits any resulting wiki changes as `docs: post-release wiki sync for <TAG>`. The branch gate is a precondition for the sync — the scanner's `state_gate` only opens with a clean tree on `main`, so enforcing the branch upfront removes a conditional from Step 9 and lets the scanner write `last_sync_commit` + `last_sync_at` on touched pages.

**Implementation status: shipped, with an extension.** Both steps are present in `.claude/commands/release.md` as of this ingest. The shipped version of Step 9 additionally inserts a **9c — Update the code graph** step (`uv run cg update` then `uv run cg sync-wiki`) before dispatching the scanner so the graph data the scanner consumes is current. The spec doesn't mention this; it was added during implementation.

## Key claims

1. **Step 0 is a pure precondition check with no reversible actions.** It runs `git rev-parse --abbrev-ref HEAD`; any output other than `main` (including the literal `HEAD` from a detached checkout) aborts with the message "Release must run on `main`. You are on `<branch>`. Switch to main and retry." Nothing on disk has been touched at that point. See `.claude/commands/release.md` Step 0 (lines 20-33 in the shipped file).
2. **The branch gate exists to simplify Step 9, not just for hygiene.** The wiki sync in Step 9 leans on the scanner's `state_gate` (which requires both a clean tree and HEAD on `main` to write `last_sync_commit`). Enforcing `main` at the start of the command removes a conditional from Step 9 and guarantees the gate is open by the time the scanner runs.
3. **Step 9 is silent when no wiki exists.** The detect step is `test -f lattice/wiki/index.md`; absent means the user has not set up a wiki, so Step 9 is skipped without printing anything. Present routes into the `AskUserQuestion` offer.
4. **Step 9 dispatches the existing `lattice-wiki:scanner` sub-agent — same one `/lattice-wiki:scan` uses.** No new agent, no new behavior; the release command yields to the scanner's interactive flow and waits for it to complete. Because the tree is clean and on `main` (guaranteed by Step 0 and the committed push in Step 8), the scanner's `state_gate` is open and it will write `last_sync_commit` and `last_sync_at` on reviewed pages. See `lattice-wiki:scanner` and [[wiki/plugins/lattice-wiki/api]].
5. **Wiki commit is a separate operation from the release.** After the scanner exits, `git status --porcelain -- lattice/wiki/` decides: no output means "Wiki already up to date." Otherwise the command stages `lattice/wiki/`, commits with `docs: post-release wiki sync for <TAG>`, and pushes — distinct from the `release: <TAG>` commit produced in Step 8.
6. **As shipped, Step 9c refreshes the code graph before the scanner runs.** The shipped Step 9c calls `uv run cg update` (incremental graph update against HEAD) followed by `uv run cg sync-wiki` (the package→wiki link refresh from [[wiki/sources/2026-05-lattice-graph-core-documents-edge]]). The spec did not require this; the implementation adds it so that scanner output is consistent with the just-released graph state. If either command fails, the implementation asks the user whether to proceed with the scanner anyway.

## Edge cases (from the spec)

| Scenario | Behaviour |
|---|---|
| Not on `main` | Step 0 aborts before any work |
| Detached HEAD (`git rev-parse --abbrev-ref HEAD` returns `HEAD`) | Step 0 aborts with the same message |
| Wiki not initialized (`lattice/wiki/index.md` absent) | Step 9 skipped silently |
| Scanner makes no changes (all pages current) | "Wiki already up to date." No follow-up commit |
| Scanner errors or exits early | Uncommitted wiki changes may remain on disk; user handles manually |

## Updated sequence

```
Step 0  — Branch gate (abort if not main)
Step 1  — Find diff baseline
Step 2  — Detect changed artifacts
Step 3  — Propagate bumps
Step 4  — Compute versions + umbrella tag
Step 5  — Gate 1: propose bump table (AskUserQuestion)
Step 6  — Apply version bumps
Step 7  — Gate 2: build (AskUserQuestion)
Step 8  — Gate 3: commit, tag, push (AskUserQuestion)
Step 9  — Wiki sync offer (AskUserQuestion, optional)
  9a — Detect wiki
  9b — Offer sync
  9c — Update the code graph (shipped only; not in the spec)
  9d — Dispatch scanner
  9e — Commit and push wiki changes
```

## Files changed

- `.claude/commands/release.md` — Step 0 inserted before Step 1; Step 9 (with sub-steps) appended after Step 8. The shipped file goes slightly further than the spec by adding Step 9c.

No other files change. The `lattice-wiki:scanner` sub-agent and its behavior are unchanged — this design only adds the invocation.

## Surprises / contradictions

- **None against existing wiki claims.** The branch gate fits the explicit-not-magic discipline already documented in [[wiki/concepts/explicit-not-magic-update-lifecycle]] — the command refuses to proceed rather than silently doing the right thing for the wrong context.
- **Spec vs. shipped delta.** The shipped Step 9c (`cg update` + `cg sync-wiki`) is an additive enhancement, not a contradiction. It is consistent with the spec's intent: ensure the wiki reflects the just-released state. The spec author may want to fold this into the spec or note it as an implementation refinement.

## Touches

- [[wiki/plugins/lattice-wiki/lattice-wiki]] — the plugin whose `scanner` sub-agent the release command invokes.
- [[wiki/concepts/explicit-not-magic-update-lifecycle]] — the precondition-check discipline this gate exemplifies (refuse, never auto-correct).

## Decisions triggered

None new. The branch gate is a workflow-level precondition, not an architecture decision — it has no cross-package surface, it's local to `.claude/commands/release.md` in this single repo, and it aligns with existing discipline:

- [[wiki/concepts/explicit-not-magic-update-lifecycle]] — banner/refuse over auto-apply applies in spirit here: the command refuses to proceed off `main` rather than guessing what the user meant.

## Related sources

- [[wiki/sources/2026-05-lattice-graph-core-documents-edge]] — defines `cg sync-wiki`, which the shipped Step 9c invokes alongside `cg update` before dispatching the scanner.
