---
name: workflow
description: Drive a work item through its pipeline — compute the next stage with `gw work next`, dispatch the stage skill, verify the artifact, advance with `gw work advance`. One stage per invocation; clear context and re-run between stages. Usage /graph-wiki:workflow <slug>
---

# /graph-wiki:workflow

Dispatch the next pipeline stage for a work item.

## Usage

```
/graph-wiki:workflow <slug>
```

`<slug>` is the work item's file stem under `wiki/work/` (e.g. `2026-06-09-fix-login-timeout`).

## What happens

Invoke the graph-wiki:workflow skill with the given slug and follow it exactly as presented to you.

## Skill Reference

→ `workflow/SKILL.md`
