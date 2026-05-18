# Spike Conventions

Patterns and stack choices established across spike sessions. New spikes follow these unless the question requires otherwise.

Note: only one spike has been run so far (001-subagent-context-audit, an analytical audit). The conventions below are seeded from that single session and should be revisited once 2+ spikes have established repeating patterns.

## Stack

- Python 3.11+ via `uv` workspaces (matches the project stack — see project CLAUDE.md §Technology Stack). Any spike that needs runnable code uses the existing workspace member for its closest analog (`agents/code-wiki-agent/` for runtime concerns, `packages/*/` for shared primitives).
- No new dependencies introduced inside `.planning/spikes/`. If a spike needs a library, add it to the relevant workspace member's `pyproject.toml` and note the choice in the spike's Research section.

## Structure

- One folder per spike: `.planning/spikes/NNN-descriptive-name/`. Required file: `README.md` with YAML frontmatter (spike, name, type, validates, verdict, related, tags).
- Analytical / audit spikes (no runnable code) keep just the README. Code-experiment spikes add `scripts/`, `test-*.py`, or `app/` subfolders as appropriate.
- Source files for wrapped-up spikes are copied to `./.claude/skills/spike-findings-deep-agents/sources/NNN-name/` at wrap-up time.

## Patterns

- **Decompose with Given/When/Then.** Risk-ordered table in the spike workflow's decompose step.
- **Investigation Trail in the README.** Capture surprises (e.g., the deepagents-isn't-imported finding in 001) inline as the spike progresses, not just at the end.
- **Provenance comments.** When a spike's recommendation will land in `prompts/_fragments/` or another curation-style location, the recommended fragment must carry a `# Source:` / `# Anchor:` / `# Source-commit:` header — the existing project convention.
- **Degrade gracefully on missing project files.** Helpers that read `wiki/CLAUDE.md` or other project-pinned files should return empty / default values rather than crash. Established in spike 001 §"What to Avoid".

## Tools & Libraries

- `syrupy` (5.1.0, already in stack) — snapshot tests for assembled system-prompt strings.
- `packages/eval-harness` — recorded-output baseline comparison when validating that an injected-context change didn't regress subagent behavior.
- `vault_io.layout_io.read_layout` — the canonical way to parse `wiki/CLAUDE.md` layout blocks. Spikes that touch project context use this, not bespoke YAML parsing.

Avoid:
- `tiktoken` for token estimation — wrong tokenizer for Bedrock/Claude/Qwen models. Use Bedrock CountTokens API or the rule of thumb (4 chars/token for English markdown) per project CLAUDE.md.
- Migrating to `deepagents.SubAgentMiddleware` to solve runtime-context problems. The custom `SubagentPool` is the dispatch primitive; that constraint is established in spike 001.
