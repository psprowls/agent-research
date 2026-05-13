---
title: Claude Code auto-memory isolation
category: concept
summary: How Claude Code's auto-memory feature is keyed, how git-worktree isolation interacts with it, and how to disable it from a headless `claude -p` invocation while preserving OAuth.
tags: [claude-code, auto-memory, isolation, lattice-evals, headless]
updated: 2026-05-09
tokens: 1244
---

# Claude Code auto-memory isolation

## What auto-memory is

Claude Code maintains a per-project markdown memory store at `${CLAUDE_CONFIG_DIR}/projects/<encoded-project-key>/memory/`. The directory contains an index `MEMORY.md` and individually-named entry files (`feedback_*.md`, `user_*.md`, `project_*.md`, `reference_*.md`). The system prompt instructs Claude to read these on session start and to write new entries when relevant. Across sessions sharing the same project key, this lets Claude remember user preferences, project context, and prior corrections.

For repeatable evaluation runs, that persistence is a leak: run N+1 sees memory written by run N (and by every prior interactive session on the same project key).

## How the project key is derived

The project-key segment is an encoded form of the **cwd** at session start (path separators replaced with `-`). Empirically (verified 2026-05-06):

| `cwd` at launch | resolved `memory_paths.auto` |
|---|---|
| `/private/tmp/cc-mem-flag-dNvt` | `~/.claude/projects/-private-tmp-cc-mem-flag-dNvt/memory/` |
| `/private/tmp/cc-cp-nX6b/repo` (rsync copy of mono-repo) | `~/.claude/projects/-private-tmp-cc-cp-nX6b-repo/memory/` |
| `/private/tmp/cc-wt-vm96/wt` (`git worktree add` from `~/Personal/mono-repo`) | `~/.claude/projects/-Users-pat-Personal-mono-repo/memory/` |

The third row is the trap. **Claude Code resolves git-worktree linkage and re-keys auto-memory to the parent repository's path.** A worktree at `/tmp/...` does not get its own memory namespace; it shares one with the source repo and with every other worktree of the same source. This means a harness that uses `git worktree add` for code isolation does not get auto-memory isolation for free.

A full filesystem copy that keeps `.git` as a regular directory (no `gitdir:` pointer back to a parent) does get its own memory namespace, since there's no worktree linkage to follow.

## Disabling auto-memory from headless `claude -p`

`claude --help` documents auto-memory disable only as a side-effect of `--bare`, but `--bare` also forces `ANTHROPIC_API_KEY` auth (it disables OAuth and Keychain reads), so it can't be used from a Max-subscription eval that authenticates via OAuth. Two undocumented-but-working knobs disable auto-memory while preserving OAuth (verified 2026-05-06):

| Mechanism | Effect on init event | OAuth preserved? |
|---|---|---|
| Default | `memory_paths: {auto: ~/.claude/projects/.../memory/}` | yes |
| `CLAUDE_CODE_DISABLE_AUTO_MEMORY=1` env var | `memory_paths: None` | yes (`apiKeySource: none`) |
| `--settings '{"autoMemoryEnabled":false}'` | `memory_paths: None` | yes (`apiKeySource: none`) |
| `--bare` | `memory_paths: None` | **no — forces API key** |

Both knobs were confirmed by the Claude Code guide subagent and verified empirically. The env var is the cleanest fit for a Python subprocess runner.

## Implications for the lattice-evals harness

`packages/lattice-evals/src/lattice_evals/isolation.py:_add_worktree` uses `git worktree add` to materialize a per-run code copy at the scenario's `baseline_sha`. Combined with `CLAUDE_CONFIG_DIR=<fresh-tmp>/cfg`, this isolates settings, plugins, and the per-run `projects/` subtree — but auto-memory writes still resolve to the parent repo path (`~/.claude/projects/-Users-pat-Personal-mono-repo/memory/`) when run inside the worktree. The harness's smoke run on 2026-05-06 left an empty `projects/-Users-pat-Personal-mono-repo/memory/` directory in its saved cfg_dir as evidence — Claude Code created the dir proactively before the run errored out.

The fix landed in `packages/lattice-evals/src/lattice_evals/runner_headless.py`: set `CLAUDE_CODE_DISABLE_AUTO_MEMORY=1` in the subprocess env. Auto-memory is then off entirely for the run, regardless of project-key resolution. See 2026-05-06-lattice-evals-worktree-does-not-isolate-auto-memory.

For belt-and-suspenders, `--no-session-persistence` (a documented `claude -p` flag) skips writing the session JSONL transcript to disk — the harness already captures stream-json separately via stdout, so the on-disk session file is redundant.

## Related

- 2026-05-06-lattice-evals-worktree-does-not-isolate-auto-memory — the bug and fix
- 2026-05-06-lattice-evals-oauth-token-as-api-key-rejected — companion auth regression discovered the same session
- 2026-05-05-lattice-evals-credentials-in-isolated-config-dir — earlier credentials-isolation analysis (now partially superseded)
- [[wiki/concepts/prompt-caching]] — server-side state that survives `CLAUDE_CONFIG_DIR` isolation but is not behavioral
