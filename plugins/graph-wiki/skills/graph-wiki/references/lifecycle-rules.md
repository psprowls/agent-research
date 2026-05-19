# Lifecycle rules — work_layer

The 19 rules `/graph-wiki:lint` runs against `<vault>/work/*.md`
plus the sidecar. Each entry: rule ID, severity, trigger, rationale, remedy.

> **Note:** The work-layer subsystem (archive, regen-index, status commands) is not ported in graph-wiki v1.2. This reference doc is retained for parity with upstream; the rules apply when/if work-layer support is added in a future version.

## Schema-shape (3)

### `status-not-in-enum` — error
**Trigger:** `status:` outside `{open, accepted, in-progress, mitigated, resolved, wontfix, superseded}`.
**Rationale:** the 7-state lifecycle is the contract every consumer relies on.
**Remedy:** map the value to its closest valid state. `proposed`/`planned` → `open` (downgrade — don't claim acceptance without a `## Plan`). `done` → `resolved`. `cancelled` → `wontfix`.

### `kind-not-in-enum` — error
**Trigger:** `kind:` outside `{bug, tech-debt, test-gap, security, perf, feature, initiative, spike}`.
**Rationale:** kind drives per-kind rules (severity allowed, target required) and consumer queries.
**Remedy:** pick the closest match. `data-model-defect` folds to `bug` + a `data-model` tag. `doc-drift` folds to `tech-debt` + `docs`.

### `severity-on-non-bug` — info
**Trigger:** `severity:` set on `kind: feature | initiative | spike`.
**Rationale:** severity is a triage knob for things that broke; intent doesn't have severity.
**Remedy:** remove `severity:` from the frontmatter.

## State-conditional (6)

### `accepted-without-plan` — error
**Trigger:** `status: accepted | in-progress | mitigated | resolved` and `## Plan` is missing or empty.
**Rationale:** "accepted" means scope is committed — the plan is what makes the commitment legible.
**Remedy:** offer to draft the `## Plan` table from the body's existing prose. Do not transition the status back to `open` — that hides the work.

### `in-progress-without-ref` — error
**Trigger:** `status: in-progress` and no `pr` or `branch` frontmatter field.
**Rationale:** "in progress" without a place to read the in-progress code is an unverifiable claim.
**Remedy:** populate `branch:` (preferred for early work) or `pr:` (once a PR is open).

### `resolved-without-ref` — warn
**Trigger:** `status: resolved` and `resolved_in:` empty.
**Rationale:** future readers need to find the change that resolved the item.
**Remedy:** populate `resolved_in:` with the PR number, commit SHA, or merged branch name.

### `superseded-without-link` — error
**Trigger:** `status: superseded` and `superseded_by:` empty.
**Rationale:** "superseded" loses meaning without a pointer to what replaced this.
**Remedy:** populate `superseded_by:` with a `work/<slug>` reference.

### `mitigated-without-mitigation` — error
**Trigger:** `status: mitigated` and `mitigation:` empty.
**Rationale:** "mitigated" promises the symptom is hidden — readers need to know how, so they can re-evaluate later.
**Remedy:** populate `mitigation:` with a one-paragraph description.

### `wontfix-without-rationale` — warn
**Trigger:** `status: wontfix` and `rationale:` empty.
**Rationale:** closed without action needs a reason or it'll get re-opened by the next person who hits it.
**Remedy:** populate `rationale:`.

## Reference resolution (2)

### `affects-target-missing` — error
**Trigger:** `affects[]` entry (after stripping `:line` suffix) doesn't resolve under `<repo>/`.
**Rationale:** the link lets consumers (and you) navigate to the affected code.
**Remedy:** check for renames first — the target may have moved. If it's gone for real, update or remove the entry.

### `plan-action-target-missing` — error
**Trigger:** a `## Plan` row mentions a path-shaped token in any cell (Action, Done when, or Rationale) that doesn't resolve under `<repo>/`.
**Rationale:** plan rows that name files should name files that exist.
**Remedy:** correct the path or remove the reference. False positives on regex-shaped tokens get filed as `tech-debt` work items.

## Lifecycle / staleness (3)

### `stuck-open` — warn
**Trigger:** `status: open` and `updated:` older than `--stuck-days` (default 30).
**Rationale:** items that haven't moved in a month either need acceptance or rejection.
**Remedy:** triage during a planning conversation. Don't auto-action.

### `stuck-accepted` — warn
**Trigger:** `status: accepted` and `updated:` older than `--stuck-days × 2` (default 60).
**Rationale:** accepted-but-not-started for two months means the plan got stale.
**Remedy:** review the plan; either start work on it, downgrade to `open` if the plan has gone stale and needs rework, or close with `wontfix`.

### `archive-eligible` — info
**Trigger:** `status: resolved | wontfix | superseded` and `updated:` is at least `--archive-eligible-days` days old (default 7).
**Rationale:** terminal-status items aren't drift, but they clutter the active queue. Surfacing them as `info` keeps the queue clean without inflating the warning channel.
**Remedy:** run `/graph-wiki:archive` to move eligible items into `<vault>/work/archived/`. Pass `--dry-run` first to see what would move; pass a slug to override the age check for a specific item.

## Body shape (3)

### `done-when-missing` — warn
**Trigger:** a `## Plan` row on `kind: feature | initiative` has empty `Done when` cell.
**Rationale:** features need observable completion criteria; bug fixes' completion is implicit (the bug stops happening).
**Remedy:** populate the cell.

### `feature-without-target` — warn
**Trigger:** `kind: feature | initiative` and `target:` empty.
**Rationale:** features without a target window slide indefinitely.
**Remedy:** populate `target:` with a quarter (`2026-Q3`) or month.

### `plan-table-malformed` — warn
**Trigger:** `## Plan` heading present but no recognizable markdown table follows.
**Rationale:** the table is the contract format; prose plans aren't queryable.
**Remedy:** convert the prose to a table. Canonical columns: `Action | Done when | Rationale`. Header detection accepts any 2 of those 3, case-insensitive.

## Sidecar (2)

### `sidecar-missing` — warn
**Trigger:** `<vault>/work-index.json` does not exist.
**Rationale:** consumers can't read the queue without it.
**Remedy:** run `/graph-wiki:regen-index`.

### `sidecar-stale` — warn
**Trigger:** sidecar's `generated_at` is older than the newest item's `updated:`.
**Rationale:** consumers will read stale data.
**Remedy:** run `/graph-wiki:regen-index`. Never hand-edit `work-index.json`.
