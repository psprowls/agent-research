---
name: lint
description: Run a health check on the Code Wiki — mechanical (orphans, broken links, stale pages, missing frontmatter, duplicates, log gap), semantic (contradictions, cross-reference gaps, stale claims, roadmap staleness, ADR chain), and code-drift (packages on disk vs. in vault, exports mismatch). Workspace and repo discovered automatically. Outputs a markdown report grouped under "## Wiki lint" header. Usage /graph-wiki:lint [--stale-days N]
---

# /graph-wiki:lint

Health-check the wiki. Includes **code-drift detection** on top of generic wiki checks — surfaces when the vault has fallen out of sync with the code.

**Reports, doesn't silently fix.** You decide what to change.

Run weekly, after every `/graph-wiki:scan`, and after batch ingests.

## Usage

```
/graph-wiki:lint
/graph-wiki:lint --stale-days 60
/graph-wiki:lint --log-gap-days 7
```

Workspace and repo are discovered automatically via `workspace_io`.

## What happens

### Pass 1 — Mechanical (scripts)

- `scripts/lint_wiki.py` — orphans, broken links, stale, missing frontmatter, duplicate titles, log gap, **+ code drift** (packages missing from vault, vault pages for deleted packages, exports drift), **+ sync drift** (`package_sync_drift` for package/app pages whose source changed since `last_sync_commit`; `source_sync_drift` for in-repo doc source pages; never-synced stubs flagged separately)
- `scripts/graph_analyzer.py` — hubs, sinks, components

### Pass 2 — Semantic (LLM)

- Contradictions between vault pages and between vault and code
- Stale claims on recently-touched packages
- Concepts mentioned across 3+ pages without their own page
- Issues with no current tickets / tickets with no issue page
- Roadmap items past target with status still in-progress
- ADR chain health (supersedes / superseded_by)
- Cross-reference gaps
- Index drift

### Pass 3 — Report

Markdown report grouped under `## Wiki lint` header with suggested actions, then appends a `lint` entry to `log.md`.

## Sub-agent

Dispatches the `linter` sub-agent. See `agents/linter.md`.

## Frequency

| Trigger | Pass |
|---|---|
| Weekly | Mechanical only |
| After `/graph-wiki:scan` | Full — catches drift |
| After batch ingest | Full |
| Monthly | Full + structural review |
| Before sharing the wiki | Full + extra review |

## Skill Reference

→ `graph-wiki/SKILL.md`
→ `graph-wiki/references/lint-workflow.md`
