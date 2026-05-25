---
title: lattice page body-table conventions
category: concept
summary: Three load-bearing markdown body tables across the lattice vault — `## Plan` (work pages), `## Endpoints` (endpoint pages), `## Fields` (data-model pages). Exact header rows, pipe-escape rule, lint contracts, and the rationale for body-not-frontmatter.
tags: [schema, markdown, tables, lint, lattice]
sources: 1
updated: 2026-05-09
tokens: 1272
---

# lattice page body-table conventions

## Summary
Three vault page categories carry their primary structured payload in body markdown tables, not frontmatter: `category: work` (`## Plan`), `category: endpoint` (`## Endpoints`), `category: data-model` (`## Fields`). Each has an **exact header row**, a pipe-escape rule, and a lint check that parses the table.

The body-table choice (over frontmatter lists) is deliberate: multi-line cells render naturally, diffs are clean, and the parsing path is single (markdown table parser → row dicts) instead of dual (YAML + body fragments).

Captured in 2026-05-lattice-ecosystem-schema-refinements §2.3 + §2.4.3.1.

## `## Plan` — work pages

Three columns: `Action` (required), `Done when` (kind-conditional — required for `kind: feature` and `kind: initiative`, optional otherwise), `Rationale` (optional).

```markdown
## Plan

| Action | Done when | Rationale |
|---|---|---|
| Stage-prefix the database name in CDK | `location-service.ts` has no literal `dev-pat-location` | Matches `STAGE` already in the same block |
| Drop the legacy adapter fallback | `legacyContextAdapter.ts` no longer falls back | Dead code once env var always set |
```

- Header row exact: `| Action | Done when | Rationale |`. Lint warns on malformed.
- One row per step. Order is significant.
- Pipe in cell content escapes as `\|`. Lint warns on unescaped pipes.
- `## Plan` missing or empty (header only) means `plan_steps: 0` in the sidecar.
- Earlier-stage exploratory thinking lives in `## Options considered`. The plan is the *committed* direction.
- Lint rules: `accepted-without-plan`, `done-when-missing`, `plan-action-target-missing`, `plan-table-malformed`.

The `## Milestones` convention from the legacy `roadmap/` shape migrates to `## Plan`: `Milestone` column → `Action`, drop the `#` numbering column (row order is significant, numbering goes stale on insert/delete), add an empty `Rationale` column.

## `## Endpoints` — endpoint pages

Five columns covering route-level metadata; group-level metadata (exposure, auth, package, defined_in) lives in frontmatter.

```markdown
## Endpoints

| Method | Path | Handler | Auth | Status |
|---|---|---|---|---|
| GET | /api/healthkit/activities | `getActivities` | (group default) | live |
| POST | /api/healthkit/activities | `createActivity` | (group default) | live |
| DELETE | /api/healthkit/activities/{id} | `deleteActivity` | (group default) | unwired |
```

- Header row exact: `| Method | Path | Handler | Auth | Status |`. Lint warns on malformed.
- `(group default)` in `Auth` inherits from frontmatter `auth:`. Explicit values override per-route.
- Per-route status enum: `live | deprecated | unwired`.
- Handler references resolve to a function name within `defined_in` (or to a code path with `:line`). Lint walks them.
- Lint rules: `endpoint-table-malformed`, `endpoint-handler-missing` (graph-only; deferred), `endpoint-status-not-in-enum`.

## `## Fields` — data-model pages

Four columns; subtypes get their own `## Subtypes` section in the same file (each with a delta `## Fields` table for differences from the base).

```markdown
## Fields

| Field | Type | Required | Notes |
|---|---|---|---|
| id | string | yes | uuid v4 |
| userId | string | yes | cognito sub |
| createdAt | ISO date string | yes | |
| activityType | enum | yes | see `## Subtypes` |
| details | object | yes | shape per activityType |
```

- Header row exact: `| Field | Type | Required | Notes |`.
- Bidirectional drift detection: lint extracts the field-name set, walks `defined_in`, diffs both ways. v1 ships TypeScript support; type-shape comparison is v2.
- Lint rules: `data-model-fields-malformed`, `data-model-field-drift` (deferred — needs language-specific extractor), `data-model-subtype-without-page-or-section`.

## Why body, not frontmatter

YAML lists with multi-line strings are noisy, depend on serializer behavior, and don't render as tables in Obsidian's reading view. Markdown body tables:

- Render in any markdown viewer.
- Support multi-line cells naturally (escape pipes; use `<br>` if needed).
- Diff cleanly in git.
- Parse with a single permissive markdown-table parser shared across `lint/common.py`.

## Target granularity

Both file-level (`packages/foo`) and `file:line` (`packages/foo/src/bar.ts:42`) are accepted in `affects:` and `## Plan` action references. Lint verifies file/package existence; line numbers are advisory and don't trip lint. Same convention as code citations elsewhere in the wiki.

## Related
- [[wiki/concepts/lattice-work-namespace-schema]]
- adrs/0008-unified-work-namespace
- 2026-05-lattice-ecosystem-schema-refinements
