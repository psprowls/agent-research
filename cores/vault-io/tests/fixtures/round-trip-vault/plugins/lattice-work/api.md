---
title: lattice-work (plugin) — API
category: package
summary: Slash commands, cross-plugin entry point, lifecycle lint rules, and sidecar schema for lattice-work
updated: 2026-05-09
tokens: 1788
---

# lattice-work (plugin) — API

## Public API

| Command | Purpose |
|---|---|
| `/lattice-work:lint` | Run the 19 `work_layer` lifecycle lint rules (`accepted-without-plan`, `stuck-open`, `done-when-missing`, `archive-eligible`, etc.). Flags: `--stuck-days N` (default 30), `--archive-eligible-days N` (default 7), `--write-sidecar` (off — keeps lint side-effect-free), `--json`. Does NOT run base wiki lint — call `/lattice-wiki:lint` for that. |
| `/lattice-work:regen-index` | Regenerate `<workspace>/work-index.json` from current `<workspace>/work/*.md` state. Atomic write via `os.replace` from `.tmp`. Deterministic — two runs against the same vault produce byte-identical output (modulo `generated_at` + `vault_commit`). Excludes `<workspace>/work/archived/`. |
| `/lattice-work:status` | One-screen rollup: counts by `status` / `kind` / `severity` / `blast_radius` plus in-progress + stuck-open + stuck-accepted call-outs. Same shape as the sidecar's `counts` block. |
| `/lattice-work:archive` | Move terminal-status items (`resolved` / `wontfix` / `superseded`) into `<workspace>/work/archived/`. Sweep mode (no slugs) honors `--min-age-days N` (default 7); targeted mode (one or more slugs) ignores age. `--dry-run` previews; `--json` emits structured output including `referrers` (grep-derived list of vault paths linking to archived slugs). Subprocess-regenerates the sidecar after moves. |

## CLI

Cross-plugin entry point (callable from `lattice-wiki` ingestor and `lattice-workflows` after work-page mutations):

```
${LATTICE_WORK_ROOT}/scripts/regenerate_work_index.py --vault <path>
```

Subprocess invocation, not Python import. Plugins evolve independently. Per [[wiki/concepts/lattice-cross-plugin-contract]].

Exit codes: `0` success, `2` invalid args, `3` runtime error (e.g. malformed frontmatter, slug collision, git failure), `4` vault not found / `<workspace>/work/` missing.

### Lifecycle lint rules (19)

Implemented in `lib/lifecycle_lint.py`. Each rule takes `(work_item, sidecar, repo_root)` and returns zero or more `Finding(rule_id, severity, slug, message)`.

| Group | Rule | Severity | Trigger |
|---|---|---|---|
| Schema-shape (3) | `status-not-in-enum` | error | `status:` not in the 7-state set |
| | `kind-not-in-enum` | error | `kind:` not in the 8-value taxonomy |
| | `severity-on-non-bug` | info | `severity:` set on `kind: feature \| initiative \| spike` |
| State-conditional required-field (6) | `accepted-without-plan` | error | `status: accepted \| in-progress \| mitigated \| resolved` and `## Plan` missing/empty |
| | `in-progress-without-ref` | error | `status: in-progress` and no `pr` or `branch` field |
| | `resolved-without-ref` | warn | `status: resolved` and `resolved_in:` empty |
| | `superseded-without-link` | error | `status: superseded` and `superseded_by:` empty |
| | `mitigated-without-mitigation` | error | `status: mitigated` and `mitigation:` empty |
| | `wontfix-without-rationale` | warn | `status: wontfix` and `rationale:` empty |
| Reference-resolution (2) — filesystem-only | `affects-target-missing` | error | `affects[]` entry (after stripping `:line` suffix) doesn't resolve under `<repo>/` |
| | `plan-action-target-missing` | error | A `## Plan` row mentions a path that doesn't resolve under `<repo>/` |
| Lifecycle / staleness (2) | `stuck-open` | warn | `status: open` and `updated:` older than `--stuck-days` (default 30) |
| | `stuck-accepted` | warn | `status: accepted` and `updated:` older than `--stuck-days × 2` (default 60) |
| Body-shape (3) | `done-when-missing` | warn | A `## Plan` row on `kind: feature \| initiative` has empty `Done when` cell |
| | `feature-without-target` | warn | `kind: feature \| initiative` and `target:` empty |
| | `plan-table-malformed` | warn | `## Plan` heading present but no recognizable markdown table follows it |
| Sidecar (2) | `sidecar-missing` | warn | `<workspace>/work-index.json` does not exist |
| | `sidecar-stale` | warn | sidecar's `generated_at` older than newest item's `updated:` |
| Archive (1) | `archive-eligible` | info | `status ∈ {resolved, wontfix, superseded}` AND `updated < now - --archive-eligible-days` (default 7) |

Severity contract: `error` blocks; `warn` is drift the planner should surface in conversation; `info` is hygiene below the warn bar (e.g. archive eligibility, severity-on-non-bug).

### Sidecar schema (work-index.json)

`schema_version: 1`:

```json
{
  "schema_version": 1,
  "generated_at": "2026-05-05T14:22:18Z",
  "vault_commit": "359cca1",
  "counts": {
    "by_status":       { "open": 0, "accepted": 0, "in-progress": 0, "mitigated": 0, "resolved": 0, "wontfix": 0, "superseded": 0 },
    "by_kind":         { "bug": 0, "tech-debt": 0, "test-gap": 0, "security": 0, "perf": 0, "feature": 0, "initiative": 0, "spike": 0 },
    "by_severity":     { "low": 0, "medium": 0, "high": 0, "critical": 0 },
    "by_blast_radius": { "file": 0, "package": 0, "domain": 0, "system": 0 }
  },
  "items": [
    { "slug": "...", "title": "...", "kind": "...", "status": "...", "severity": "...",
      "effort": "...", "blast_radius": "...", "affects": [], "target": null, "owner": null,
      "plan_steps": 0, "opened": "YYYY-MM-DD", "updated": "YYYY-MM-DD",
      "resolved_in": null, "superseded_by": null, "mitigation": null, "rationale": null,
      "pr": null, "branch": null, "tags": [] }
  ]
}
```

Field rules:
- All state-conditional fields (`resolved_in`, `superseded_by`, `mitigation`, `rationale`, `pr`, `branch`) included as `null` when absent — removes None-vs-missing ambiguity for consumers.
- `affects` and `tags` always arrays (never `null`); empty if unset.
- `counts.by_severity` only counts items where `severity:` is set — `feature`/`initiative`/`spike` typically don't contribute.
- `<workspace>/work/archived/` is excluded from the walker.

`lib/sidecar.py` ships `load_sidecar(path) → (data, is_stale)` for both internal and external callers.
