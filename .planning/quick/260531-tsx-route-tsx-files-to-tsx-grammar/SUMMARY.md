---
status: complete
phase: quick-260531-tsx
plan: "01"
---

# Quick Task 260531-tsx: Route .tsx files to the tsx grammar

See [260531-tsx-SUMMARY.md](./260531-tsx-SUMMARY.md) for the full summary.

`.tsx` files now parse with the JSX-capable `tsx` tree-sitter grammar instead of
the JSX-blind `typescript` grammar, so React component definitions are extracted
rather than dropped as pathless stubs. Commit `1007ef0`. Executed in an isolated
worktree, left unmerged per request.
