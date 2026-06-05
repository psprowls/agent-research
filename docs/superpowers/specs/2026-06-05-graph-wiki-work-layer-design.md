# graph-wiki Work Layer Design

**Date:** 2026-06-05
**Status:** draft

## Problem

The graph-wiki plugin has a complete work-item schema, 19 lifecycle lint rules, and a sidecar contract (`work-index.json`) defined in its reference docs — but none of the management machinery is implemented. There is no way to run lifecycle lint programmatically, generate or query the sidecar, archive terminal items, or file a work item through an interactive command. The plugin references these capabilities in documentation but they do not exist in code.

## Prerequisite

The `worktree-wikilink-base-wiki-root` branch must land before this work begins. That branch moves `work_dir` from `<workspace>/work/` to `<workspace>/wiki/work/` (inside the wiki vault), updates `workspace_io.paths.work_dir()`, retargets `lint_wiki.py` and `commands/lint.py` to walk from the wiki root, and adjusts all callers. Everything in this spec targets the post-merge state.

After that branch lands, the workspace layout is:
```
<workspace>/
├── .graph-wiki.yaml
├── wiki/
│   ├── work/                   ← work items live here
│   │   ├── YYYY-MM-DD-slug.md
│   │   └── archived/
│   ├── work-index.json         ← sidecar (sibling to work/)
│   ├── concepts/
│   ├── ...
│   └── log.md
└── raw/
```

## Scope

This spec covers six areas:

1. New `work-io` package — pure lifecycle logic
2. New `graph-wiki-core/commands/work.py` — orchestration layer
3. New `gw work` top-level CLI subapp — `file`, `lint`, `archive`, `status`, `regen-index`
4. Four new plugin commands — `/graph-wiki:file`, `/graph-wiki:archive`, `/graph-wiki:status`, `/graph-wiki:regen-index`
5. Work-layer lint integrated into `gw wiki lint`
6. Minor update to `commands/lint.md` (existing lint plugin doc)

**Out of scope:** MCP tool twins for `gw work` commands (follow-on); changes to `gw wiki ingest work-item` (already works).

## What Already Exists

- `gw wiki ingest work-item` — low-level filing CLI (raw `--frontmatter`/`--body` flags)
- `wiki_io.ingest_work_item.file_work_item()` — the filing library function
- `wiki-io/assets/page-templates/work.md` — canonical work item template
- Plugin reference docs: `lifecycle-rules.md`, `sidecar-schema.md`, `wiki-schema.md`, `page-formats.md`

---

## Section 1 — `packages/work-io/` (new package)

### Purpose

Deterministic, I/O-free lifecycle logic for work items. No dependency on `wiki-io` or `graph-wiki-core`. The only external deps are `workspace-io` (path resolution) and `pyyaml` (frontmatter parse/emit).

### Layout

```
packages/work-io/
├── pyproject.toml
└── src/work_io/
    ├── __init__.py
    ├── frontmatter.py
    ├── plan_table.py
    ├── sidecar.py
    ├── lifecycle_lint.py
    └── archive.py
```

### `pyproject.toml`

```toml
[project]
name = "work-io"
version = "0.1.0"
requires-python = ">=3.11"
dependencies = ["workspace-io", "pyyaml>=6.0"]
```

### Module contracts

#### `frontmatter.py`

```python
def parse(text: str) -> tuple[dict, str]:
    """Return (frontmatter_dict, body_text). Raises ValueError on malformed input."""

def emit(fm: dict) -> str:
    """Serialize frontmatter dict to a fenced YAML block (--- ... ---)."""
```

Uses `yaml.safe_load` / `yaml.safe_dump` on the `---` delimited block. The body is everything after the closing `---`.

#### `plan_table.py`

```python
@dataclass
class PlanResult:
    state: Literal["missing", "empty", "malformed", "ok"]
    rows: list[dict]   # each: {"action": str, "done_when": str, "rationale": str}

def parse_plan(body: str) -> PlanResult:
    """Locate ## Plan heading; extract markdown table rows."""
```

Header matching is permissive: requires ≥2 of the 3 canonical column names (`action`, `done when`, `rationale`), case-insensitive. Returns `state: "missing"` when the `## Plan` heading is absent, `"empty"` when the table exists but has no data rows, `"malformed"` when a heading exists but no valid table follows.

#### `sidecar.py`

```python
SCHEMA_VERSION = 1

def build_sidecar(work_dir: Path, vault_commit: str | None) -> dict:
    """Walk work_dir/*.md (excluding archived/), parse each item, return sidecar dict."""

def write_sidecar(wiki: Path, sidecar: dict) -> None:
    """Atomically write sidecar dict to wiki/work-index.json (write-temp + rename)."""

def load_sidecar(wiki: Path) -> dict | None:
    """Return parsed sidecar dict or None if absent."""

def is_stale(sidecar: dict, work_dir: Path) -> bool:
    """True if any item's updated date > sidecar generated_at date."""
```

Sidecar location: `wiki/work-index.json` (inside the wiki root, sibling to `work/`).

Top-level sidecar shape:
```json
{
  "schema_version": 1,
  "generated_at": "<ISO-8601 UTC>",
  "vault_commit": "<git HEAD SHA or null>",
  "counts": {
    "by_status":      {"open": N, ...},
    "by_kind":        {"bug": N, ...},
    "by_severity":    {"critical": N, ...},
    "by_blast_radius": {"file": N, ...}
  },
  "items": [...]
}
```

Items sorted by `opened` descending, then slug ascending. Only active items (not `work/archived/`) are included.

**Enum values** (graph-wiki schema):
- `status`: `open | accepted | in-progress | mitigated | resolved | wontfix | superseded`
- `kind`: `bug | tech-debt | test-gap | security | perf | feature | initiative | spike`
- `severity`: `low | medium | high | critical` (only for `bug | security | perf | tech-debt | test-gap`)
- `blast_radius`: `file | package | domain | system`

#### `lifecycle_lint.py`

```python
@dataclass
class LintFinding:
    rule_id: str
    severity: Literal["error", "warn", "info"]
    slug: str
    message: str

def run_lint(
    items: list[dict],          # parsed frontmatter + plan_state per item
    repo_root: Path | None,     # for affects/plan path resolution
    sidecar: dict | None,       # for sidecar-presence/staleness rules
) -> list[LintFinding]:
```

Implements all 19 rules from `skills/graph-wiki/references/lifecycle-rules.md`:

| Category | Rules |
|---|---|
| Schema-shape | `status-not-in-enum`, `kind-not-in-enum`, `severity-on-non-bug` |
| State-conditional | `accepted-without-plan`, `in-progress-without-ref`, `resolved-without-ref`, `superseded-without-link`, `mitigated-without-mitigation`, `wontfix-without-rationale` |
| Reference resolution | `affects-target-missing`, `plan-action-target-missing` |
| Lifecycle / staleness | `stuck-open` (>30d), `stuck-accepted` (>60d), `archive-eligible` (terminal + ≥7d) |
| Body shape | `done-when-missing`, `feature-without-target`, `plan-table-malformed` |
| Sidecar | `sidecar-missing`, `sidecar-stale` |

Reference-resolution rules are skipped (not raised) when `repo_root` is None.

#### `archive.py`

```python
@dataclass
class ArchiveAction:
    slug: str
    src: Path
    dst: Path   # work/archived/<filename>

@dataclass
class ArchivePlan:
    actions: list[ArchiveAction]
    skipped: list[dict]   # {"slug": str, "reason": str}

def plan_archive(
    work_dir: Path,
    slugs: list[str] | None = None,
    min_age_days: int = 7,
) -> ArchivePlan:
```

Terminal statuses: `resolved`, `wontfix`, `superseded`. Sweep mode (`slugs=None`): all terminal items aged ≥ `min_age_days`. Targeted mode (`slugs` provided): named items only, age check bypassed. Non-terminal items are always skipped (noted in `skipped` list).

---

## Section 2 — `graph-wiki-core/commands/work.py` (new module)

### Purpose

Orchestration layer: wires `work-io` (pure logic) with `wiki-io` (I/O side-effects). Follows the same pattern as other command modules — async functions returning dataclasses, no presentation logic.

### Result dataclasses

```python
@dataclass
class WorkLintResult:
    wiki: str
    total_items: int
    findings: list[dict]   # serialized LintFinding dicts
    errors: list[str]

@dataclass
class WorkArchiveResult:
    wiki: str
    moved: list[str]       # page paths moved
    skipped: list[dict]    # {"slug": str, "reason": str}
    referrers: list[str]   # vault pages with wikilinks to archived items (warnings)
    dry_run: bool

@dataclass
class WorkStatusResult:
    wiki: str
    counts: dict           # sidecar counts block
    in_flight: list[dict]  # items with status: in-progress
    stuck: list[dict]      # open >30d or accepted >60d
    sidecar_stale: bool
    sidecar_missing: bool

@dataclass
class WorkRegenResult:
    wiki: str
    item_count: int
    sidecar_path: str
```

Filing re-uses the existing `IngestResult` from `commands/ingest.py` — no new dataclass needed.

### Functions

**`run_work_lint(workspace_path)`**
Resolves workspace; reads `wiki/work/*.md`; parses each item via `work_io.frontmatter.parse` and `work_io.plan_table.parse_plan`; loads sidecar for the two sidecar rules; calls `work_io.lifecycle_lint.run_lint(items, repo_root, sidecar)`. Returns `WorkLintResult`.

**`run_work_archive(workspace_path, slugs, dry_run, min_age_days)`**
Resolves workspace; calls `work_io.archive.plan_archive(work_dir, slugs, min_age_days)`; scans vault wikilinks for referrers to items-to-be-moved (warns, does not block); if not `dry_run`, executes moves via `git mv` with `os.rename` fallback, then calls `run_work_regen_index` as a side-effect. Returns `WorkArchiveResult`.

**`run_work_status(workspace_path)`**
Resolves workspace; calls `work_io.sidecar.load_sidecar(wiki)`; computes in-flight items (`status: in-progress`) and stuck items (open >30d, accepted >60d) from sidecar items. Returns `WorkStatusResult` with `sidecar_missing: True` and guidance hint when sidecar absent.

**`run_work_regen_index(workspace_path)`**
Resolves workspace; reads git HEAD commit if available; calls `work_io.sidecar.build_sidecar(work_dir, vault_commit)` then `work_io.sidecar.write_sidecar(wiki, sidecar)`. Returns `WorkRegenResult`.

**`run_work_file(workspace_path, title, kind, summary, affects, **optional_fields)`**
Thin wrapper: validates enum fields against `work_io` constants, constructs frontmatter dict and a body pre-populated with the standard section headers (`## Summary`, `## Options considered`, `## Plan`, `## Notes / log`), calls `wiki_io.ingest_work_item.file_work_item(wiki, fm, body)`. Returns `IngestResult`. Does not duplicate filing logic.

### Dependency change

Add `work-io` to `packages/graph-wiki-core/pyproject.toml` dependencies.

---

## Section 3 — `gw work` CLI subapp (new)

New file: `packages/graph-wiki-cli/src/graph_wiki_cli/work_cli/main.py`

Registration in `cli.py` (two lines):
```python
from graph_wiki_cli.work_cli.main import work_app
app.add_typer(work_app, name="work")
```

### Commands

```
gw work file
    --title TEXT        (required)
    --kind TEXT         (required) bug|tech-debt|test-gap|security|perf|feature|initiative|spike
    --summary TEXT      (required) one-line ≤100 chars
    --affects TEXT      (required) comma-separated paths/packages
    --effort TEXT       trivial|small|medium|large
    --blast-radius TEXT file|package|domain|system
    --target TEXT       YYYY-QN or YYYY-MM (feature/initiative)
    --owner TEXT
    --tags TEXT         comma-separated
    --workspace TEXT
    --json
    Exit 0 = filed, 2 = validation/schema error, 3 = runtime error

gw work lint
    --workspace TEXT
    --json
    Exit 0 = clean, 1 = any error-severity finding, 3 = runtime error

gw work archive [SLUGS...]
    --dry-run           show plan without moving files
    --min-age-days INT  default 7
    --workspace TEXT
    --json
    Exit 0 = ok, 3 = runtime error
    Note: referrers found are printed as warnings but do not affect exit code

gw work status
    --workspace TEXT
    --json
    Exit 0 = ok, 4 = sidecar missing (hint: run regen-index)

gw work regen-index
    --workspace TEXT
    --json
    Exit 0 = ok, 3 = runtime error, 4 = work/ missing
```

`--affects` and `--tags` accept comma-separated strings and are split before passing to the command layer.

### Dependency change

Add `work-io` to `packages/graph-wiki-cli/pyproject.toml` dependencies (needed for `LintFinding` type annotation in the presenter).

---

## Section 4 — Plugin commands (new)

Four new files in `plugins/graph-wiki/commands/`.

**`commands/file.md` → `/graph-wiki:file`**
Interactive work item creation. Gathers required fields conversationally (title, kind, summary, affects); optionally prompts for effort, blast-radius, target, owner, tags. Auto-sets `status: open` and `opened: <today>`. Invokes `gw work file` with the assembled values.

**`commands/archive.md` → `/graph-wiki:archive`**
Sweep mode by default (all terminal-status items aged ≥7 days). Accepts optional slug arguments for targeted archiving (bypasses age check). Presents the archive plan and asks for confirmation before executing. Invokes `gw work archive`.

**`commands/status.md` → `/graph-wiki:status`**
One-screen rollup: counts by status and kind, in-flight items, stuck items. Surfaces a `regen-index` hint when the sidecar is missing or stale. Invokes `gw work status`.

**`commands/regen-index.md` → `/graph-wiki:regen-index`**
Rebuilds `wiki/work-index.json` from current `wiki/work/*.md` state. Invokes `gw work regen-index`.

---

## Section 5 — Work-layer lint in `gw wiki lint`

### Changes to `graph-wiki-core/commands/lint.py`

- Add `work_lint_findings: list[dict] = field(default_factory=list)` to `LintResult`.
- In `run_lint`, after `_mechanical_pass`, call `run_work_lint(workspace_path)`; attach `findings` to `result.work_lint_findings`.
- Work findings with `severity: "error"` append to `result.errors`, which already causes exit code 3 in `gw wiki lint`.

### Changes to `graph-wiki-cli/wiki_cli/main.py`

Add one section to the human-readable lint output presenter:
```python
_section("Work lifecycle", [
    f"[{f['severity']}] {f['slug']}: {f['rule_id']} — {f['message']}"
    for f in result.work_lint_findings
])
```

Appears after the existing `scanner_heading_drift` section.

### Changes to `plugins/graph-wiki/commands/lint.md`

Add a note that work-layer lifecycle findings now appear under a "Work lifecycle" section in the lint output, alongside the existing mention of the 19 rules from `lifecycle-rules.md`.

---

## Delivery sequence

1. Land `worktree-wikilink-base-wiki-root` (prerequisite — moves `work/` into `wiki/`)
2. Create `packages/work-io/` with all five modules and tests
3. Add `graph-wiki-core/commands/work.py` + update `pyproject.toml`
4. Add `graph-wiki-cli/work_cli/main.py` + register in `cli.py` + update `pyproject.toml`
5. Integrate work-layer lint into `commands/lint.py` and `wiki_cli/main.py`
6. Add the four plugin command files
7. Update `plugins/graph-wiki/commands/lint.md`

Steps 2–4 can proceed in parallel once step 1 is done; step 5 depends on steps 2–3; step 6 depends on step 4.

---

## Testing

- `work-io`: unit tests for all five modules. Frontmatter round-trip, plan table edge cases (missing heading, prose-only plan, escaped pipes), sidecar staleness detection, all 19 lint rules triggered and suppressed, archive eligibility sweep and targeted modes.
- `graph-wiki-core/commands/work.py`: integration tests using a tmp-dir workspace. Cover dry-run archive, status with missing sidecar, regen-index idempotence.
- `graph-wiki-cli`: smoke tests for `gw work lint --json` and `gw work status --json` exit codes.
