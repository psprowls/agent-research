---
name: status
description: Show a one-screen work item rollup — counts by status/kind, in-flight items, stuck items. Hints to run regen-index when the sidecar is missing or stale. Invokes `gw work status`. Usage /graph-wiki:status
---

# /graph-wiki:status

One-screen work item rollup from the `work-index.json` sidecar.

## Usage

```
/graph-wiki:status
```

## What happens

1. Run `gw work status --json`.
2. If the sidecar is missing, suggest running `/graph-wiki:regen-index` first.
3. Present:
   - Counts by status, kind, severity, blast-radius.
   - In-flight items (status: in-progress) with titles.
   - Stuck items (open >30d or accepted >60d) with age.
   - A staleness hint if the sidecar is out of date.

## Skill Reference

→ `graph-wiki/SKILL.md`
→ `graph-wiki/references/sidecar-schema.md`
