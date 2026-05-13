---
title: Plugin deployment shapes (A–G)
category: concept
summary: Seven deployment shapes weighed for code-intel plugins; lattice-graph commits to shape F (MCP server + Python CLI sharing one query library).
tags: [architecture, mcp, cli, plugins, deployment]
sources: 1
updated: 2026-05-09
tokens: 1122
---

# Plugin deployment shapes (A–G)

## Definition
Seven distinct deployment shapes considered for the code-intel layer of the lattice ecosystem. The decision matrix evaluates each across cold start, state-across-calls, agent surface, token cost, distribution, MCP-host dep, cross-tool reach, and implementation cost.

| Shape | Description |
|---|---|
| **A** | Pure MCP server — no marketplace plugin |
| **B** | Plugin + Python CLI only (no MCP) |
| **C** | Plugin ships MCP only |
| **F** | Plugin ships **MCP + Python CLI** sharing one library — *chosen target* |
| **D** | Skill content + raw `sqlite3` CLI |
| **E** | A `code-graph` subagent that owns graph access |
| **G** | Pre-built graph committed in CI |

Source authority: `raw/specs/architecture/3.1-plugin-topology.md:30-39` (decision matrix).

## Motivation
Code graphs are queried from many places: agent main contexts (where MCP shines), subagent dispatch (where injecting the full MCP surface is too noisy), interactive shell sessions (where ergonomics favor a Bash CLI), and cross-tool workflows (Codex, generic LLM apps without MCP). No single shape covers all four; F covers them by sharing one library between an MCP adapter and a CLI adapter.

## Shape

```
plugins/lattice-graph/
├── .claude-plugin/plugin.json    # declares mcpServers entry
├── lib/                          # query library — single source of truth
│   ├── __init__.py               #   public API: find(), callers(), describe_package(), ...
│   ├── schema.py
│   ├── queries.py
│   └── attrs.py
├── mcp/server.py                 # MCP adapter
├── cli/cg.py                     # CLI adapter
├── parsers/                      # tree-sitter integrations (§3.5)
├── scripts/update_graph.py       # operational
└── skills/code-graph/SKILL.md
```

Layout from `raw/specs/architecture/3.1-plugin-topology.md:489-508`. The library is the unit of versioning; MCP and CLI adapters bump together because they share the API contract.

## Why F over the alternatives

- **A (pure MCP)** — loses marketplace distribution; two-step install; can't bundle skill content.
- **B (plugin + CLI only)** — loses persistent state and typed tool ergonomics; ~100–200 ms Python startup per query is meaningful in agent loops with 10+ queries.
- **C (MCP only)** — initially planned for v1, but inverted: v1 now ships CLI-first per [[wiki/adrs/0007-cli-first-code-graph]] so the library boundary is exercised through a thin testable adapter before MCP lands.
- **D (skill + raw `sqlite3`)** — agents writing SQL through Bash escape badly; schema lives in skill content (token cost every session); errors are unstructured.
- **E (subagent owns graph access)** — subagent invocation is ~10⁴× slower than an MCP tool; defeats the original "grep is wasteful" motivation. Variant where the subagent **owns the MCP server** held open for v2.
- **G (pre-built graph in CI)** — promising as a v2 *deployment option*; schema in §3.2 supports it without changes.

## v1 staging

> [!info] Staged delivery — CLI-first, MCP at v1.1
> v1 ships **CLI-first**: only the CLI adapter (a partial shape F). The MCP adapter slips to v1.1 once the library boundary stabilizes through real CLI use. This inverts the original §3.1 ordering (which had v1 as MCP-only); see [[wiki/adrs/0007-cli-first-code-graph]] for the rationale and 2026-05-lattice-graph-plugin-design §9.1 for the design.

## Used in
- [[wiki/plugins/lattice-graph/lattice-graph]] — implements shape F (v1 ships CLI-first; MCP at v1.1 per [[wiki/adrs/0007-cli-first-code-graph]])

## Related patterns
- [[wiki/concepts/per-repo-data-vs-global-tooling-tier]] — F is a per-repo data plugin shape
- [[wiki/concepts/per-repo-layout]] — F's storage lives at `<workspace>/.graph/code.db` (default: `<repo>/lattice/.graph/code.db`)

## Sources
- 2026-05-architecture-3.1-plugin-topology

## Decisions
- adrs/0002-code-graph-separate-plugin

## Open questions / gotchas
- Doubles testing surface (MCP tools + CLI commands both need integration tests). Acceptable cost.
- Shape E's "subagent owns MCP server" variant remains an open v2 consideration for keeping MCP tools out of the parent context.
