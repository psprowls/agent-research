# Project Knowledge

Append-only register of project-specific rules, patterns, and lessons learned.
Agents read this before every unit. Add entries when you discover something worth remembering.
## Rules

| # | Scope | Rule | Why | Added |
|---|-------|------|-----|-------|
| 1 | source-parser | `.tsx` files must be routed to the `tsx` tree-sitter grammar, not `typescript`. | The plain TypeScript grammar cannot parse JSX and silently produces error-laden trees that drop component declarations. | 2026-05-31 |

## Patterns

| # | Pattern | Where | Notes |
|---|---------|-------|-------|

## Lessons Learned

| # | What Happened | Root Cause | Fix | Scope |
|---|--------------|------------|-----|-------|
