# Lint Workflow

Periodic health check the LLM runs when the user runs `/graph-wiki:lint` or dispatches the `graph-wiki:linter` sub-agent. Run weekly, after batch ingests, and always after a repo scan.

## Goal

Keep the wiki healthy and **keep it in sync with the code**. Surface problems for the user to review. The graph-wiki linter adds **code-drift detection** on top of the generic wiki health check.

## Pass 1 — mechanical checks (script)

`lint_wiki.py` is a thin dispatcher; per-group checks live under `scripts/lint/`. Each module exposes a `check(...)` entry point and a `GROUP` constant.

### Default check groups (always run)

```bash
python scripts/lint_wiki.py
```

(Workspace and repo are discovered automatically via `workspace_io`.)

Default report:

- **Orphans** — pages with zero inbound `[[wikilinks]]`
- **Broken links** — wikilinks pointing to non-existent pages
- **Stale pages** — pages whose `updated:` frontmatter is older than 90 days (tune via `--stale-days`)
- **Missing frontmatter** — pages lacking `title`, `category`, or `summary`
- **Duplicate titles** — two or more pages sharing the same title
- **Log gap** — no log entry in the last 14 days (tune via `--log-gap-days`)
- **Code drift** (monorepo-specific) — packages on disk vs. in vault. Pages declaring `status: planned` in frontmatter are excluded from `orphaned_in_vault` and surfaced separately under `planned_in_vault`, so deliberately seeded plugin/package pages don't drown the signal.
- **`container_drift`** (`lint/container.py`) — pinned vault dirs vs. disk; orphan vault dirs. Tolerates legacy `issues/`, `roadmap/`, `comparisons/` with a hint pointing at the §2 migrators.
- **`source_sync` drift** (`lint/source_sync.py`) — for each in-repo doc source page (`category: source` with `last_sync_commit`), runs `git diff --name-only <last_sync_commit>..HEAD -- <source_path>`. Drift suggests running `/graph-wiki:ingest <path>` to re-ingest.
- **`package_sync` drift** (`lint/package_sync.py`) — same shape against `package_path` / `app_path`. Pages with no `last_sync_commit` are flagged as "never synced".
- **`file_map` drift** (`lint/file_map.py`) — `## File map` entries that no longer exist on disk.
- **`domain` placement** (`lint/domain.py`) — package pages whose vault location disagrees with their `domain:` frontmatter.

### Optional check groups (`--check`)

One optional group available:

```bash
python scripts/lint_wiki.py --check dependency_layer
```

#### `dependency_layer` (`lint/dependency.py`)

| Rule | Severity | What it catches |
|---|---|---|
| `dep-kind-not-in-enum` | error | `kind:` outside `package | package-family | service` |
| `dep-package-without-ecosystem` | error | `kind: package` and `ecosystem:` missing |
| `dep-service-without-provider` | error | `kind: service` and `provider:` missing |
| `dep-family-without-members` | error | `kind: package-family` and `members:` empty |
| `dep-family-member-not-in-scan` | error | a member listed in `members:` isn't found in any manifest scanned by `discover_workspaces` |
| `dep-family-back-pointer-mismatch` | error | a package has `family: X` but family X's page doesn't list it (or vice versa) |
| `dep-multiple-families` | error | a package is claimed by two different family pages |
| `dep-detail-without-load-bearing` | warn | detail page exists but `load_bearing: true` not set |
| `dep-stub-detail-page` | warn | detail page body <15 lines beyond frontmatter — flesh out or delete and rely on the auto-generated `dependencies/index.md` |

### Other helpers

Run `python scripts/graph_analyzer.py` for structural stats — hubs, sinks, connected components.

## Pass 2 — semantic checks (LLM)

The scripts can't catch these. The LLM must read and think.

### A. Contradictions between wiki pages

Scan pages whose `updated:` is recent. For each, check whether it contradicts any existing page. If so:
- Add a `> ⚠️ Contradiction:` callout to both pages
- Log with `op: note`
- Surface to user

### B. Contradictions between vault and code

For each recently-touched `packages/<name>/overview.md` page, spot-check the hand-written prose against the actual `package.json` and `src/index.ts`.

### C. Stale claims

For each flagged stale page, ask:
- Does newer code or a newer source now contradict this?
- Is a "Key patterns" bullet likely to be outdated?
- Suggest to user: "Page X says Y. This may be outdated — want me to re-read the code or find a newer source?"

### D. Concepts mentioned without their own page

Grep for concept-shaped phrases repeated across 3+ package/domain/architecture pages but without a dedicated concept page. Suggest creating one. Comparisons (`<a>-vs-<b>.md`) live under `concepts/`.

### E. ADR chain health

- Every `supersedes:` field should point to an existing ADR that has `superseded_by:` pointing back.
- Every ADR with `status: deprecated` should have `superseded_by:` or a reason.

### F. Cross-reference gaps

For each recently-touched page, check: do all package/domain/dependency mentions have wikilinks? If something is referenced as plain text in 3+ places, promote it to a wikilink (and create a stub page if needed).

### G. Index drift

Compare `index.md` against actual `<workspace>/wiki/` contents. If out of sync, either regenerate (`update_index.py`) or patch inline.

## Pass 3 — report

Present findings to the user as a single markdown report:

```markdown
# Code Wiki lint — 2026-04-20

**Total pages:** 142  **Components:** 1  **Last log:** 2026-04-19
**Code drift:** 2 new packages un-documented, 1 package page orphaned

## Wiki lint

### Found
- ⚠️ 4 packages drifted since last sync: `common-aws-node-ts` (12 files), …
- ⚠️ 2 packages on disk missing wiki pages: `timeline-native-ts`, `timeline-data-node-ts`
- ⚠️ 1 dep-stub-detail-page: `dependencies/lodash` has 3 body lines — delete and rely on `dependencies/index.md`
- 3 orphan wiki pages
- 4 concepts mentioned across 3+ pages without their own page

### Suggested actions
1. Run `/graph-wiki:scan` to create stubs for missing packages
2. Re-read the drifted packages
3. Investigate orphans
```

Append a `lint` entry to `log.md` summarizing what was found and what was fixed.

## Frequency

- **Weekly** — light pass, default groups only
- **After every `/graph-wiki:scan`** — full code-drift pass
- **After batch ingests** — full pass with all `--check` groups enabled
- **Before sharing the wiki with onboarding devs / agents** — full pass plus extra review
