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
5. Optionally prompt for: `effort` (trivial|small|medium|large), `blast-radius` (file|package|domain|system), `target` (YYYY-QN or YYYY-MM), `owner`, `tags`.
6. Auto-sets `status: open` and `opened: <today>`.
7. Invoke:

```bash
gw work file \
  --title "..." \
  --kind "..." \
  --summary "..." \
  --affects "..." \
  [--effort ...] [--blast-radius ...] [--target ...] [--owner ...] [--tags ...]
```

8. Report the filed page path.

## Skill Reference

→ `graph-wiki/SKILL.md`
→ `graph-wiki/references/wiki-schema.md`
→ `graph-wiki/references/lifecycle-rules.md`
