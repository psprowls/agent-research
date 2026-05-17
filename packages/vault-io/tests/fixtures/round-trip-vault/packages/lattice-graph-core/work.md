---
title: lattice-graph-core — Work
category: package
summary: Bugs, tech debt, features, and open questions for lattice-graph-core
updated: 2026-05-09
tokens: 392
---

# lattice-graph-core — Work

## Bugs

(none tracked)

## Tech debt

(none tracked)

## Features

- **MCP surface (v1.1)** — `cg query` raw-SQL escape hatch and MCP tool bindings deferred from v1. CLI adapter ships first to stabilize the library boundary.
- **`cg describe-type`** — needs `extends`/`inherits` edge kind not in v1 schema.
- **Symmetric import commands** — `cg imported-by`, `cg exports`, `cg exported-by` are mechanical adds deferred to v1.1.
- **C# parser support (v1.1)** — `lattice-source-parser` needs a `parsers/csharp.py` module first.
- [[work/2026-05-06-lattice-code-graph-packages-refresh-affected-dirs]] — `packages.refresh` scoping for affected dirs
- [[work/2026-05-06-lattice-code-graph-session-start-hook-integration-test]] — SessionStart hook integration test
- [[work/2026-05-06-lattice-code-graph-wire-exit-codes-4-and-6]] — wire up enforcement for `SCHEMA_MISMATCH` (exit 4) and `UPDATE_IN_PROGRESS` (exit 6)

## Open questions

- `SCHEMA_MISMATCH` (exit 4) and `UPDATE_IN_PROGRESS` (exit 6) are declared in `exit_codes.py` and reserved by the design — wire up enforcement when v2 schema lands and concurrent-update protection ships.
- Whether `lattice-graph` self-hosts graph-derived summaries in its wiki page (bootstrap) — open both here and on the plugin page.
