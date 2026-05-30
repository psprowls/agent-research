---
phase: quick-260530-nfj
plan: 01
type: execute
wave: 1
depends_on: []
files_modified: [scripts/graph_health.py]
autonomous: true
requirements: [QUICK-NFJ-01]

must_haves:
  truths:
    - "A reusable graph-io DB auditor lives at scripts/graph_health.py"
    - "The script is executable and runs against a live code.db with exit 0"
    - "The script prints METADATA, NODES, and EDGES sections"
  artifacts:
    - path: "scripts/graph_health.py"
      provides: "Read-only graph-io code.db completeness/resolution auditor"
      contains: "mode=ro"
  key_links:
    - from: "scripts/graph_health.py"
      to: "graph-io code.db (nodes/edges/metadata tables)"
      via: "sqlite3 read-only connection"
      pattern: "file:.*mode=ro"
---

<objective>
Move the read-only graph-io diagnostic auditor from /tmp/graph_health.py into the
repo at scripts/graph_health.py so it is a permanent, reusable dev tool alongside
the existing scripts/drift-diff.sh and scripts/check-brand.sh.

Purpose: The script audits a graph-io SQLite code.db (node/edge completeness by
kind, unresolved-edge counts, function placeholder targets, unresolved import
specifier shapes). It is currently stranded in /tmp; making it a repo artifact
keeps it available for future graph-health investigations.

Output: scripts/graph_health.py (executable, pure-stdlib Python 3).
</objective>

<execution_context>
@$HOME/.claude/get-shit-done/workflows/execute-plan.md
@$HOME/.claude/get-shit-done/templates/summary.md
</execution_context>

<context>
@.planning/STATE.md

# Source of truth for the script body (copy verbatim):
@/tmp/graph_health.py

# Header-comment convention to match (the `# scripts/<name> — <purpose>` line
# directly under the shebang):
@scripts/drift-diff.sh
@scripts/check-brand.sh
</context>

<tasks>

<task type="auto">
  <name>Task 1: Add scripts/graph_health.py matching repo convention</name>
  <files>scripts/graph_health.py</files>
  <action>
Copy /tmp/graph_health.py to scripts/graph_health.py with its body BYTE-FOR-BYTE
identical — do NOT refactor, rename, or add features. The only permitted change is
the module docstring header, to match the repo convention used in
scripts/drift-diff.sh and scripts/check-brand.sh.

Keep the existing `#!/usr/bin/env python3` shebang on line 1. Keep the existing
triple-quoted usage docstring (Usage / defaults-to .graph/code.db / Read-only).
Adjust ONLY the first line of that docstring so it reads in the repo's
`<name> — <purpose>` style, e.g.:

    graph_health.py — audit a graph-io code.db for unpopulated / unresolved data.

(The current first docstring line already nearly matches this; if it does, leave
it.) Everything from `from __future__ import annotations` downward must be copied
unchanged.

Do NOT wire this as a `cg` console-script entry point and do NOT touch any
pyproject.toml — it is a standalone dev tool, not part of the graph-io public CLI.
It uses only stdlib (sqlite3, sys, pathlib), so there are no new dependencies.

After writing the file, make it executable: `chmod +x scripts/graph_health.py`.
  </action>
  <verify>
    <automated>test -x scripts/graph_health.py && head -1 scripts/graph_health.py | grep -qF '#!/usr/bin/env python3' && grep -qF 'mode=ro' scripts/graph_health.py && python3 scripts/graph_health.py /Users/pat/Personal/graph-wiki/mono-repo-live/.graph/code.db | grep -qE '^METADATA$' && echo OK</automated>
  </verify>
  <done>
scripts/graph_health.py exists, is executable, retains the read-only
(`mode=ro`) sqlite connection, and running
`python3 scripts/graph_health.py /Users/pat/Personal/graph-wiki/mono-repo-live/.graph/code.db`
prints the METADATA / NODES / EDGES sections and exits 0. Body is identical to
/tmp/graph_health.py except for the optional one-line docstring header tweak.
  </done>
</task>

</tasks>

<verification>
Run the auditor against the live DB and confirm the section banners print:

```
python3 scripts/graph_health.py /Users/pat/Personal/graph-wiki/mono-repo-live/.graph/code.db
```

Expect a clean exit (0) with the `METADATA`, `NODES`, and `EDGES` banner sections
visible. Confirm `scripts/graph_health.py` carries the executable bit
(`test -x scripts/graph_health.py`).
</verification>

<success_criteria>
- scripts/graph_health.py exists, is executable, and is byte-identical to
  /tmp/graph_health.py except for an optional one-line docstring header.
- The script still opens the DB read-only (`mode=ro`) and takes the db path as
  argv[1] (default .graph/code.db).
- Running it against the live mono-repo code.db prints METADATA/NODES/EDGES and
  exits 0.
- No pyproject.toml changes; no `cg` entry point; no new dependencies.
</success_criteria>

<output>
Create `.planning/quick/260530-nfj-add-graph-health-diagnostic-script-for-g/260530-nfj-SUMMARY.md` when done
</output>
