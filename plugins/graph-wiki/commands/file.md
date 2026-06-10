---
name: file
description: Interactively file a new work item into the wiki — gathers title, kind, summary, and affects conversationally, then invokes `gw work file` with the assembled values. Usage /graph-wiki:file
---

# /graph-wiki:file

Interactively create a new work item in `wiki/work/`.

## Usage

```
/graph-wiki:file
```

Gathers required fields conversationally, then invokes `gw work file`.

## What happens

1. Prompt for **title** (required) — a short description of the issue or feature.
2. Prompt for **kind** (required) — one of: `bug`, `tech-debt`, `test-gap`, `security`, `perf`, `feature`, `initiative`, `spike`.
3. Prompt for **summary** (required) — one line, <=100 chars.
4. Prompt for **affects** (required) — comma-separated paths or package names (e.g. `packages/graph-io, packages/wiki-io`).
5. **Estimate effort** — based on the title, kind, and summary, propose an effort value (`xtra-small|small|medium|large|xtra-large`) with a one-line rationale. Present it to the user: "I'd estimate this as **medium** — multiple files across packages, likely one PR. Does that sound right?" The user can accept or name a different size.
6. Optionally prompt for: `blast-radius` (file|package|domain|system), `target` (YYYY-QN or YYYY-MM), `owner`, `tags`.
7. Auto-sets `status: open` and `opened: <today>`.
8. Invoke:

```bash
gw work file \
  --title "..." \
  --kind "..." \
  --summary "..." \
  --affects "..." \
  --effort "..." \
  [--blast-radius ...] [--target ...] [--owner ...] [--tags ...]
```

9. Report the filed page path.

## Effort scale

| Value | Anchor |
|---|---|
| `xtra-small` | minutes — one-line change, no test, no review needed |
| `small` | hours — single file, tests, single PR |
| `medium` | days — multiple files, possibly cross-package, single PR |
| `large` | weeks — multiple PRs, possibly an initiative |
| `xtra-large` | months — multi-initiative, large team or quarter-long scope |

## Skill Reference

→ `graph-wiki/SKILL.md`
→ `graph-wiki/references/wiki-schema.md`
→ `graph-wiki/references/lifecycle-rules.md`
