---
command: log
upstream_source: plugins/lattice-wiki/commands/log.md
port_verdict: rename
---

# /graph-wiki:log — Port Spec

## Shell-out contract

**Invocation:** NONE — this command has no script in the upstream plugin, and the port preserves that.

**Mechanism:** Prose-only command. The command body instructs the Claude Code session to run `grep + tail` against `<workspace>/wiki/log.md` directly:

```bash
grep "^## \[" <workspace>/wiki/log.md | tail -N
```

Plus optional filters for op type (`--op`) and date range (`--since`).

No `uv run` line. No script ships under `plugins/graph-wiki/skills/graph-wiki/scripts/log.py` (parity with upstream, which has no `log.py` either). The port does not introduce a Python shim for this command.

**Optional placeholder script (executor discretion per CONTEXT.md §decisions):** A tiny `log.py` wrapping `grep + tail` could improve UX so users don't need to construct the shell invocation manually. Default is "no script" matching upstream. If added, it would be:

```bash
uv run --project "$DEEP_AGENTS_ROOT" python3 "${CLAUDE_PLUGIN_ROOT}/skills/graph-wiki/scripts/log.py" $ARGUMENTS
```

This decision is left to Phase 14 executor judgment. The default spec is no script.

**Target Python module (claude backend):** None — no shell-out on the primary path.

**Target subprocess (bedrock backend):** `code-wiki-agent log <args>` — only if the executor adds a bedrock backend seam here (not required by default; the command is trivial enough that the prose-only path suffices for both backends).

## Prose-preservation map

Walk of every H2 section in upstream `commands/log.md`:

| Upstream section | Verdict | Notes |
|---|---|---|
| `## Usage` | verbatim except namespace rename | `/lattice-wiki:log` → `/graph-wiki:log` in all example invocations; all flags (`--last`, `--op`, `--since`) preserved verbatim |
| `## What it does` | verbatim except path strings | `<workspace>/wiki/log.md` stays as-is (path is workspace-relative, not plugin-branded); `grep + tail` prose preserved verbatim |
| `## Valid ops` | verbatim except op name rebranding | Op names reference `/lattice-wiki:scan` etc. — rename to `/graph-wiki:scan`, `/graph-wiki:ingest`, `/graph-wiki:lint`, etc. All op semantics unchanged |
| `## Example output` | verbatim | Log entry format (`## [YYYY-MM-DD] <op> | <title>`) is identical; example content is synthetic and unchanged |
| `## Skill Reference` | namespace rename only | `lattice-wiki/SKILL.md` → `graph-wiki/SKILL.md` |

## Agent / skill rename map

No sub-agent is involved in this command. The log command is prose-only; it does not dispatch a sub-agent.

| Asset | From | To | Touch |
|---|---|---|---|
| Skill index | `skills/lattice-wiki/SKILL.md` | `skills/graph-wiki/SKILL.md` | Rename + namespace rebrand (boilerplate inherited by all commands; not log-specific) |
| Script | (none) | (none) | No script ships; no rename needed |

## Reshape notes

No behavior changes vs upstream. Pure prose rename of namespace strings and op references:

- `/lattice-wiki:log` → `/graph-wiki:log` in the command name and usage examples
- Op name references (`/lattice-wiki:scan`, `/lattice-wiki:ingest`, etc.) → `/graph-wiki:scan`, `/graph-wiki:ingest`, etc. in the `## Valid ops` section
- No structural changes to the `wiki/log.md` format — the `## [YYYY-MM-DD] <op> | <title>` entry format is preserved verbatim
- No script ships (parity with upstream). The command is trivially implemented as a prose instruction to `grep + tail` the log file.

## Verification gate

Run `/graph-wiki:log` inside a Claude Code session in a workspace that has a `wiki/log.md` file with entries. Expected: the command outputs recent log entries in the `## [YYYY-MM-DD] <op> | <title>` format, matching upstream `/lattice-wiki:log` output against the same `wiki/log.md` file content modulo brand strings (op names show `graph-wiki` references in prose context where applicable).

**Filter smoke:**

- `/graph-wiki:log --last 20` — returns 20 entries
- `/graph-wiki:log --op scan --last 10` — returns only `scan` op entries
- `/graph-wiki:log --since 2026-01-01` — returns entries from that date forward

**Namespace smoke:** Confirm the command responds to `/graph-wiki:log` in Claude Code autocomplete.

See SHELL-OUT-PATTERN.md §SO-01 only in passing — this command does not use the shell-out invocation pattern, but the rename map link is useful for the Skill Reference update.
