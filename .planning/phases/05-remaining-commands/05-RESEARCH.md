# Phase 5: Remaining Commands — Research

**Researched:** 2026-05-14
**Domain:** Python CLI / MCP command porting (log, init, scan, ingest, lint)
**Confidence:** HIGH — all conclusions drawn from direct source-code inspection of the actual codebase and the lattice-wiki-core reference implementation. No web searches required.

---

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions

- **D-01:** Port both `ingest_source.py` AND `ingest_work_item.py` from lattice-wiki-core into vault_io. Both needed for full parity.
- **D-02:** The `ingestor` subagent determines the target page type (package/concept/adr) AND generates the page summary. LLM receives extracted source text + metadata; decides where to file and what to write.
- **D-03:** After writing a new/updated page, run a full cross-reference update: refresh `index.md` and update wikilink back-references in related pages.
- **D-04:** Two separate CLI subcommands: `code-wiki-agent ingest source <path>` and `code-wiki-agent ingest work-item <path>`. MCP split TBD by planner.
- **D-05:** Scanner fan-out is LLM-driven: scanner subagent receives package metadata + `build_file_map()` output + sampled source files and uses LLM to write the stub page body.
- **D-06:** Package discovery, diff, file_map come from `scan_monorepo.py` (deterministic). Only stub content generation goes through scanner subagent. `SubagentPool.run_all()` fans out across packages needing new/updated stubs.
- **D-07:** When scan detects a renamed or deleted package: mark vault page with a `stale` tag in frontmatter, append deletion/rename event to `log.md`. No auto-delete.
- **D-08:** Port all 7 lint rule modules from `lattice-wiki-core/lint/` into `vault_io/lint/`. Full mechanical parity.
- **D-09:** Semantic LLM pass uses 3 broader rule-groups: (1) page quality + contradictions, (2) ADR chain integrity, (3) stale claims + code-drift. Each runs as a parallel linter subagent.
- **D-10:** Lint report format: `--json` flag emits structured findings list; default is human-readable text. No write-back to vault.
- **D-11:** `--config <path>` is a global app-level Typer option (Typer callback pattern) on all subcommands automatically.
- **D-12:** Config file is full JSON/TOML covering models.toml path, default vault path, agent settings. Schema: `models_path`, `vault_path`, `state_gate_enabled` as initial fields.
- **D-13:** MCP server reads config path from `CODE_WIKI_CONFIG` env var.

### Claude's Discretion

- MCP ingest tool split — whether `wiki_ingest` is one tool with a `type` field or two tools (`wiki_ingest_source`, `wiki_ingest_work_item`).
- Scanner source file sampling — which files are "representative samples"; `pick_representative()` already in `scan_monorepo.py`.
- Config file format — JSON vs. TOML; TOML is likely given models.toml precedent.
- Cross-ref update scope for ingest — exactly which updates needed (index.md rebuild vs. selective back-ref updates); planner ports from `ingest_source.py` main() flow.
- `--stale-days` / `--log-gap-days` thresholds for lint — present as Typer options with defaults matching lattice-wiki-core.

### Deferred Ideas (OUT OF SCOPE)

- Eval baselines for scan/lint/ingest/log (come after Phase 5)
- Ingest cross-ref deep linking beyond index.md refresh
- Scanner subagent retry on stub conflict (last-write-wins is fine)
- Config schema versioning
</user_constraints>

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| CMD-01 | `init` command: bootstrap vault, discover containers, create dirs + index.md + log.md + .templates/, render tool schema files, pin layout block | `init_vault.py` is fully ported; needs thin CLI + MCP wrapper |
| CMD-02 | `scan` command: walk repo, diff packages vs vault, create/update stubs via scanner fan-out, flag renames/deletions, update index.md + log.md | `scan_monorepo.py` is fully ported; needs scanner subagent + LLM fan-out wiring |
| CMD-03 | `ingest` command: extract text + metadata from source, compute slug, route to page type, synthesize via ingestor subagent, update cross-refs + index, append log | `ingest_source.py` and `ingest_work_item.py` need to be ported into vault_io; ingestor role already in models.toml |
| CMD-05 | `lint` command: mechanical pass (orphans, broken wikilinks, stale, missing frontmatter, code-drift) + semantic fan-out via linter subagents | 7 lint modules need porting from lattice-wiki-core/lint/ into vault_io/lint/; linter role already in models.toml |
| CMD-06 | `log` command: append timestamped event to log.md atomically | `append_log.py` is fully ported; needs thin CLI + MCP wrapper only |
| MCP-01 | FastMCP server exposes all 6 commands as MCP tools with typed Pydantic schemas | wiki_ping and wiki_query already registered; need wiki_init, wiki_scan, wiki_ingest, wiki_lint, wiki_log |
| MCP-03 | Progress reporting via MCP `notifications/progress` for long-running commands | `ctx.report_progress()` already established in wiki_query; repeat pattern for scan, lint, ingest |
</phase_requirements>

---

## Summary

Phase 5 delivers the remaining 5 commands (`log`, `init`, `scan`, `ingest`, `lint`) wired through both MCP and CLI. Research shows that the vault-io layer already has the deterministic machinery ported and working — `append_log`, `init_vault`, `scan_monorepo`, `update_index`, and `lint/common` are all in place. The phase work is primarily (1) porting 7 lint modules and 2 ingest modules into vault_io, (2) building the command layer following the `query.py` pattern, and (3) wiring MCP tools following the `wiki_query` pattern.

The ingestor and linter roles are already defined in models.toml (no schema changes needed). The SubagentPool API is understood and the `query.py` command shows the exact pattern to follow. The main risk area is lint's orchestration complexity (7 mechanical modules + 3-group LLM fan-out) and ingest's cross-reference update logic, which requires careful porting from `ingest_work_item.py`'s `_run_helper()` pattern.

**Primary recommendation:** Sequence work in 5 waves: (1) thin wrappers for log/init, (2) port 7 lint mechanical modules, (3) port ingest_source + ingest_work_item, (4) implement scan command with scanner subagent, (5) implement lint command with semantic fan-out. Register all MCP tools in a final wave.

---

## Architectural Responsibility Map

| Capability | Primary Tier | Secondary Tier | Rationale |
|------------|-------------|----------------|-----------|
| log — append to log.md | CLI / MCP wrapper | vault_io.append_log | Pure file I/O; no LLM; wrapper is trivial |
| init — bootstrap vault structure | CLI / MCP wrapper | vault_io.init_vault | Pure file I/O + template rendering; no LLM |
| scan — package discovery + diff | vault_io.scan_monorepo (deterministic) | commands/scan.py (fan-out) | Discovery is pure Python; stub content is LLM via scanner subagent |
| scan — stub content generation | SubagentPool (scanner role) | vault_io.scan_monorepo helpers | LLM writes stub markdown body; deterministic layer supplies inputs |
| ingest source — text extraction + routing | vault_io.ingest_source (port) | commands/ingest.py (orchestrator) | Text extraction is deterministic; routing/summary is LLM |
| ingest work-item — filing + cross-ref | vault_io.ingest_work_item (port) | vault_io.update_index | Schema validation and write are deterministic; LLM not involved for work-items |
| lint — mechanical checks (7 modules) | vault_io.lint/* modules | commands/lint.py | Pure Python deterministic; no LLM |
| lint — semantic checks (3 groups) | SubagentPool (linter role) | commands/lint.py | LLM fan-out; each group is one subagent task |
| --config / CODE_WIKI_CONFIG | cli.py (global callback) / server.py (env read) | config.py (new module) | CLI and MCP both route to shared load_config() |
| MCP tool registration | code_wiki_mcp/server.py | commands/* (shared run_*()) | All MCP tools import shared run_*() functions |
| cross-reference update after ingest | vault_io.update_index | vault_io.graph_analyzer (optional) | index.md refresh is deterministic; back-ref updates are file-level |

---

## Existing Code Inventory (What's Already Built)

### vault_io — fully ported, production-ready

| Module | Status | Key API |
|--------|--------|---------|
| `append_log.py` | COMPLETE | `append_log(wiki, op, title, detail, as_json=False) -> dict` |
| `init_vault.py` | COMPLETE | `init_wiki(wiki_path, repo_path, topic, tool, force, as_json, non_interactive) -> dict` — note: has `TODO Phase 5: workspace init` comment for workspace bootstrap step |
| `scan_monorepo.py` | COMPLETE | `discover_workspaces()`, `compute_diff()`, `build_file_map()`, `pick_representative()`, `attach_changed_files()`, `compute_state_gate()`, `regenerate_dependencies_index()` |
| `update_index.py` | COMPLETE | `update_index(wiki)` or equivalent (regenerates index.md from frontmatter) |
| `layout_io.py` | COMPLETE | `read_layout()`, `write_layout()` |
| `git_state.py` | COMPLETE | `is_clean_main()`, `head_commit()`, `changed_files_since()` |
| `graph_analyzer.py` | COMPLETE | Graph analysis helpers |
| `detect_containers.py` | COMPLETE | `detect(repo) -> list[dict]` |
| `lint/common.py` | COMPLETE | `_is_placeholder_target()`, `parse_frontmatter()`, `strip_code()`, `strip_frontmatter()`, `WIKILINK_RE`, `LOG_ENTRY_RE`, `FILE_MAP_SECTION_RE`, all parsing helpers |
| `lint/__init__.py` | COMPLETE | Package init only |

### vault_io — NOT YET PORTED (Phase 5 work)

| Module | Status | What to Port From |
|--------|--------|-------------------|
| `lint/container.py` | MISSING | `lattice_wiki_core/lint/container.py` |
| `lint/dependency.py` | MISSING | `lattice_wiki_core/lint/dependency.py` |
| `lint/domain.py` | MISSING | `lattice_wiki_core/lint/domain.py` |
| `lint/file_map.py` | MISSING | `lattice_wiki_core/lint/file_map.py` |
| `lint/package_sync.py` | MISSING | `lattice_wiki_core/lint/package_sync.py` |
| `lint/source_sync.py` | MISSING | `lattice_wiki_core/lint/source_sync.py` |
| `lint/workflow_hints.py` | MISSING | `lattice_wiki_core/lint/workflow_hints.py` |
| `ingest_source.py` | MISSING | `lattice_wiki_core/ingest_source.py` |
| `ingest_work_item.py` | MISSING | `lattice_wiki_core/ingest_work_item.py` |

### agents/code-wiki-agent — command layer

| File | Status | Notes |
|------|--------|-------|
| `commands/query.py` | COMPLETE | THE PATTERN: `run_query()`, `QueryResult` dataclass, guardrails |
| `commands/__init__.py` | COMPLETE | Package init |
| `cli.py` | PARTIAL | Has `query`, `trace`, `version` subcommands; missing `log`, `init`, `scan`, `ingest`, `lint` and global `--config` callback |
| `code_wiki_mcp/server.py` | PARTIAL | Has `wiki_ping`, `wiki_query`; missing `wiki_init`, `wiki_scan`, `wiki_ingest`, `wiki_lint`, `wiki_log` |

### cores/subagent-runtime

| Module | Status | Key API |
|--------|--------|---------|
| `pool.py` | COMPLETE | `SubagentPool.run_all(items, task, role, *, model_id, max_concurrency, recursion_limit)` returns `FanOutResult(successes, errors)` |

### cores/model-adapter

| File | Status | Notes |
|------|--------|-------|
| `models.toml` | COMPLETE — all roles present | Verified: `scanner`, `linter`, `ingestor` roles are already defined. No changes needed. |
| `loader.py` | COMPLETE | `make_llm(role)`, `load_role_config(role)` |

### Test fixtures

| Fixture | Location | Status |
|---------|----------|--------|
| `round-trip-vault` | `cores/vault-io/tests/fixtures/round-trip-vault/` | EXISTS — real vault pages |
| `single-package-vault` | `cores/vault-io/tests/fixtures/single-package-vault/` | EXISTS — minimal vault with packages/ dir |
| `edge-case-vault` | `cores/vault-io/tests/fixtures/edge-case-vault/` | EXISTS — truncated frontmatter, broken links |
| eval baselines | `eval/baselines/*.json` | EXISTS — 8 query baselines for parity testing |

---

## Port Gaps: What Needs to be Built vs. What Exists

### Group A: Thin wrappers (no new vault_io code needed)

| Command | What to Build | vault_io already has |
|---------|--------------|----------------------|
| `log` | `commands/log.py` with `run_log()`, `LogResult` dataclass | `append_log.py` — direct call |
| `init` | `commands/init.py` with `run_init()`, `InitResult` dataclass | `init_vault.py` — direct call |

CLI subcommands: `@app.command()` for both (simple, no sub-app needed).
MCP tools: `wiki_log` and `wiki_init` on the existing `mcp = FastMCP(...)` instance.

### Group B: Lint mechanical modules (port from lattice-wiki-core/lint/)

Seven files to create in `cores/vault-io/src/vault_io/lint/`:

| New File | Port Source | Complexity | Import Changes |
|----------|------------|------------|----------------|
| `container.py` | `lattice_wiki_core/lint/container.py` | LOW | Change `from lattice_wiki_core.layout_io` to `from vault_io.layout_io` |
| `dependency.py` | `lattice_wiki_core/lint/dependency.py` | MEDIUM | Change `from lattice_wiki_core.lint.common` to `from vault_io.lint.common` |
| `domain.py` | `lattice_wiki_core/lint/domain.py` | LOW | No vault_io imports; pure logic |
| `file_map.py` | `lattice_wiki_core/lint/file_map.py` | LOW | Change `from lattice_wiki_core.scan_monorepo` to `from vault_io.scan_monorepo`; `from lattice_wiki_core.lint.common` to `from vault_io.lint.common` |
| `package_sync.py` | `lattice_wiki_core/lint/package_sync.py` | LOW | Change `from lattice_wiki_core.git_state` to `from vault_io.git_state`; `from lattice_wiki_core.lint.common` to `from vault_io.lint.common` |
| `source_sync.py` | `lattice_wiki_core/lint/source_sync.py` | LOW | Same import swaps as package_sync |
| `workflow_hints.py` | `lattice_wiki_core/lint/workflow_hints.py` | LOW | Change `from lattice_wiki_core.lint.common` to `from vault_io.lint.common` |

**Key insight:** Every lattice-wiki-core import in these modules is a direct swap: `lattice_wiki_core.X` → `vault_io.X`. The logic is unchanged. `common.py` is already ported and contains all shared symbols.

### Group C: Ingest modules (port from lattice-wiki-core/)

Two files to create in `cores/vault-io/src/vault_io/`:

**`ingest_source.py`**
- Port: `extract()`, `slugify()`, `guess_source_type()`, `language_for()`, `pick_representative()`, `folder_brief()`, `list_folder_files()`
- Remove: `_version_check` import (no equivalent in vault_io; just delete), `check_for_updates()` call
- Change: `from lattice_wiki_core._workspace` → `from vault_io._workspace`
- Complexity: LOW — pure text processing functions
- The `--pkg-dir` / `ensure_subpage` path is in scope (ingest_source.py's main() calls `ensure_subpage`). `layout_io.ensure_subpage` already exists in vault_io.

**`ingest_work_item.py`**
- Port: `_slugify()`, `_parse_frontmatter()`, `_validate()`, `_emit_yaml()`, `file_work_item()` (the core write logic)
- **Critical change:** Replace `_run_helper()` subprocess calls with direct function imports:
  - `_run_helper("update_index.py")` → `from vault_io.update_index import update_index; update_index(wiki)`
  - `_run_helper("append_log.py", "--op", "create", ...)` → `from vault_io.append_log import append_log; append_log(wiki, "create", title, detail)`
- Remove: `from lattice_wiki_core._workspace import resolve_wiki_and_repo` (workspace resolution handled at command layer)
- Remove: `from lattice_wiki_core.layout_io import ensure_subpage` → `from vault_io.layout_io import ensure_subpage`
- Complexity: LOW-MEDIUM — main complexity is replacing subprocess calls with direct imports

### Group D: Command layer (new files in commands/)

| File | LLM Fan-Out | SubagentPool | New Logic |
|------|-------------|-------------|-----------|
| `commands/log.py` | No | No | None — wrap append_log |
| `commands/init.py` | No | No | None — wrap init_wiki |
| `commands/scan.py` | Yes (scanner role) | Yes — one task per new/updated package | Stub page format, stale-tag logic |
| `commands/ingest.py` | Yes (ingestor role) | Yes — single ingestor call | Cross-ref update after write |
| `commands/lint.py` | Yes (linter role) | Yes — 3 group fan-out | Mechanical pass orchestration + semantic pass |

### Group E: MCP tool registrations (add to server.py)

| Tool Name | Pattern | Input Schema Fields | Progress Notifications |
|-----------|---------|---------------------|----------------------|
| `wiki_log` | sync (no LLM) | `op`, `title`, `detail`, `vault_path` | No |
| `wiki_init` | sync (no LLM) | `topic`, `tool`, `force`, `vault_path` | No |
| `wiki_scan` | async (scanner fan-out) | `vault_path`, `no_file_map`, `max_depth` | Yes — after discovery, per stub batch |
| `wiki_ingest` | async (ingestor fan-out) | `source_path`, `type` (or split into two tools), `vault_path` | Yes — after extraction, after write |
| `wiki_lint` | async (linter fan-out) | `vault_path`, `stale_days`, `log_gap_days` | Yes — after mechanical, after semantic |

### Group F: Global config (new file + CLI wiring)

- New `agents/code-wiki-agent/src/code_wiki_agent/config.py` with `load_config(path) -> WikiConfig` dataclass
- Config schema: `models_path: str | None`, `vault_path: str | None`, `state_gate_enabled: bool = True`
- Format: TOML (consistent with models.toml)
- Typer callback in `cli.py`: `@app.callback()` with `config: Optional[Path] = typer.Option(None, "--config")`
- MCP server reads `CODE_WIKI_CONFIG` env var in `main()` and calls `load_config()` before running

---

## Command Implementation Details

### `log` Command (CMD-06)

**Complexity:** TRIVIAL

The vault_io API is exactly what the command needs. The only work is the command wrapper.

```python
# commands/log.py
@dataclass
class LogResult:
    status: str
    log_path: str
    date: str
    op: str
    title: str
    header: str
    detail: str | None

async def run_log(op: str, title: str, detail: str | None, vault_path: Path | None) -> LogResult:
    wiki, _ = resolve_wiki_and_repo(vault_path)
    result = append_log(wiki, op, title, detail)  # returns dict
    return LogResult(**result)
```

CLI: `@app.command()` with `--op`, `--title`, `--detail`, `--json` options.
MCP: `wiki_log` tool with `WikiLogInput(op, title, detail, vault_path)`.

State gate: `log` is a write command but unconditional — no state gate check (it's the tool that records state changes, so blocking it on git state would be circular).

**Default `--stale-days` value from lint_wiki.py:** 90 days.
**Default `--log-gap-days` value from lint_wiki.py:** 14 days.

### `init` Command (CMD-01)

**Complexity:** LOW

`init_vault.py` has a `TODO Phase 5: workspace init` comment — this refers to creating `<workspace>/raw/` and `<workspace>/work/` directories (lattice-workspace equivalent). The TODO means those two dirs are not yet created. The Phase 5 plan should decide whether to create them (simple `mkdir`) or leave as deferred (both are empty dirs, no complex logic).

The MCP version must pass `non_interactive=True` to `init_wiki()` — already supported.

CLI: `@app.command()` with `--topic`, `--tool`, `--force`, `--vault` options.
MCP: `wiki_init` tool. No progress notification needed (fast operation).

### `scan` Command (CMD-02)

**Complexity:** HIGH — most complex in the phase

**Deterministic phase (no LLM):**
1. `resolve_wiki_and_repo(vault_path)` → `wiki, repo`
2. Read layout from `wiki/CLAUDE.md` via `read_layout()`
3. `discover_workspaces(repo, pinned_containers=pinned)` → list of workspace dicts
4. For each workspace: `build_file_map(pkg_path)` → attach `file_map` to workspace dict
5. `_load_existing_pages(wiki)` → existing page map
6. `attach_changed_files(workspaces, existing, repo)` → attach changed_files to each workspace
7. `compute_diff(workspaces, existing)` → `{new, renamed, deleted, unchanged}`
8. `compute_state_gate(repo)` → `{allowed, reason, head_commit}`

**Scanner fan-out (LLM phase):**
For packages in `diff["new"]` and packages in `diff["unchanged"]` where `changed_files` is non-empty:

```python
pool = SubagentPool(trace_dir=wiki / ".code-wiki" / "traces")
scan_cfg = load_role_config("scanner")

async def generate_stub(pkg: dict) -> str:
    # Build prompt: package metadata dict + file_map + pick_representative()
    # scanner subagent returns full stub page markdown with frontmatter
    msgs = [SystemMessage(content=SCANNER_SYSTEM), HumanMessage(content=build_stub_prompt(pkg))]
    resp = await make_llm("scanner").ainvoke(msgs)
    return resp.content

fan_result = await pool.run_all(
    items=packages_needing_stubs,
    task=generate_stub,
    role="scanner",
    model_id=scan_cfg["model_id"],
    max_concurrency=scan_cfg["max_concurrency"],
)
```

**Post-fan-out:**
- Write stub pages to correct vault paths (from `pkg["vault_path"]`)
- For deleted packages (in `diff["deleted"]`): read existing page, add `stale: true` to frontmatter, append log entry
- Call `regenerate_dependencies_index(wiki, workspaces)`
- Call `update_index(wiki)` to refresh `index.md`
- Call `append_log(wiki, "scan", ...)` with scan summary

**SCANNER_SYSTEM prompt needs to produce:** valid markdown with YAML frontmatter matching vault page schema (title, category, summary, package_path/app_path, language, version, depends_on, exports fields).

**Result dataclass:**
```python
@dataclass
class ScanResult:
    added: list[str]      # package names created
    updated: list[str]    # package names updated
    deleted: list[str]    # package names marked stale
    renamed: list[list[str]]  # [[old, new], ...]
    errors: list[str]     # per-package error messages
    state_gate: dict      # {allowed, reason, head_commit}
```

### `ingest` Command (CMD-03)

**Complexity:** HIGH

Two sub-paths sharing a common orchestrator:

**`ingest source <path>`:**
1. Call ported `ingest_source.extract(path)` → `(text, title)`
2. Call `ingest_source.guess_source_type(rel_to_wiki, rel_to_repo)` → source_type
3. Call `ingest_source.slugify(title_guess)` → slug
4. Build ingestor prompt: extracted text + source metadata + current vault structure
5. `SubagentPool.run_all()` with single item (the source path) — OR just direct `make_llm("ingestor").ainvoke()` since it's one item
6. Ingestor returns: target page slug, page type (package/concept/adr), generated page body
7. Write page to vault at computed path
8. `update_index(wiki)` to refresh index.md
9. `append_log(wiki, "ingest", title, detail)`

**Note:** For a single-item "fan-out," using `SubagentPool.run_all()` with one item is fine (it handles trace writing). Direct `ainvoke()` is also acceptable and avoids unnecessary overhead.

**`ingest work-item <path|yaml>`:**
1. Parse frontmatter from `--frontmatter` arg (or read from file)
2. Validate required fields: `title`, `category`, `kind`, `status`, `summary`, `opened`, `affects`
3. Compute slug from title
4. Write to `wiki.parent / "work" / f"{opened}-{slug}.md"`
5. `update_index(wiki)`
6. `append_log(wiki, "create", title, detail)`
7. If `--pkg-dir`: call `ensure_subpage(pkg_dir, "work", ...)` and append backlink

**The `_run_helper()` problem in `ingest_work_item.py`:** The original uses `subprocess.run()` to call sibling scripts. In deep-agents, these are replaced with direct function calls:
- `_run_helper("update_index.py")` → direct `update_index(wiki)` call
- `_run_helper("append_log.py", ...)` → direct `append_log(wiki, ...)` call

**Result dataclass:**
```python
@dataclass
class IngestResult:
    status: str
    page_path: str        # vault-relative path of the written page
    slug: str
    title: str
    page_type: str        # package/concept/adr/source/work
    source_path: str      # source file that was ingested
    cross_refs_updated: int  # number of index/cross-ref pages updated
```

### `lint` Command (CMD-05)

**Complexity:** VERY HIGH

**Mechanical pass (pure Python, no LLM):**

The mechanical pass replicates `lint_wiki.py:scan()`. It calls into the 7 ported modules:

```python
from vault_io.lint.common import WIKILINK_RE, LOG_ENTRY_RE, parse_frontmatter, strip_code, strip_frontmatter
from vault_io.lint.container import check as check_container_drift
from vault_io.lint.dependency import check as check_dependency_layer
from vault_io.lint.domain import check as check_domain_placement
from vault_io.lint.file_map import check as check_file_map_drift
from vault_io.lint.package_sync import check as check_package_sync_drift
from vault_io.lint.source_sync import check as check_source_sync_drift
from vault_io.lint.workflow_hints import check as check_workflow_hints
```

The `scan()` function in `lint_wiki.py` is also inline logic (orphans, broken wikilinks, stale, missing frontmatter, duplicate titles, log gap). This inline logic must also be ported into `commands/lint.py` — it's not in any of the 7 modules.

**Inline mechanical checks to port (from `lint_wiki.py:scan()`):**
- Page walk + frontmatter parse + outbound/inbound link graph construction
- Orphan detection (pages with no inbound links)
- Broken wikilink detection (using `_is_placeholder_target()` from `vault_io.lint.common`)
- Stale page detection (`updated` frontmatter field < stale_cutoff)
- Missing frontmatter check (`title`, `category`, `summary` all required)
- Duplicate title detection
- Log gap detection (`## [YYYY-MM-DD]` header parsing via `LOG_ENTRY_RE`)

**Default thresholds (from `lint_wiki.py:main()`):**
- `--stale-days`: 90
- `--log-gap-days`: 14

**Semantic pass (LLM fan-out, 3 groups):**

```python
pool = SubagentPool(trace_dir=wiki / ".code-wiki" / "traces")
lint_cfg = load_role_config("linter")

semantic_groups = [
    ("page_quality", LINTER_PAGE_QUALITY_SYSTEM, pages_sample),
    ("adr_chain", LINTER_ADR_CHAIN_SYSTEM, adr_pages),
    ("stale_claims", LINTER_STALE_CLAIMS_SYSTEM, pages_with_source_path),
]

async def run_linter_group(group: tuple) -> list[str]:
    name, system_prompt, pages_input = group
    msgs = [SystemMessage(content=system_prompt), HumanMessage(content=build_linter_input(pages_input))]
    resp = await make_llm("linter").ainvoke(msgs)
    return parse_findings(resp.content)  # list of finding strings

fan_result = await pool.run_all(
    items=semantic_groups,
    task=run_linter_group,
    role="linter",
    model_id=lint_cfg["model_id"],
    max_concurrency=lint_cfg["max_concurrency"],
)
```

**Result dataclass:**
```python
@dataclass
class LintResult:
    wiki: str
    total_pages: int
    orphans: list[str]
    broken_links: list[tuple]
    stale: list[tuple]
    missing_frontmatter: list[str]
    duplicate_titles: dict
    log_gap: dict | None
    code_drift: dict
    container_drift: list[str]
    source_sync_drift: list[str]
    file_map_drift: list[str]
    package_sync_drift: list[str]
    domain_placement: list[str]
    workflow_hints: list[str]
    semantic_findings: dict  # {"page_quality": [...], "adr_chain": [...], "stale_claims": [...]}
    errors: list[str]        # per-group semantic errors
```

---

## SubagentPool Integration Pattern

The established pattern from `query.py`:

```python
# 1. Build pool with trace_dir
pool = SubagentPool(trace_dir=wiki / ".code-wiki" / "traces")

# 2. Load role config
role_cfg = load_role_config("scanner")  # or "linter", "ingestor"

# 3. Define async task closure
async def task(item: SomeType) -> str:
    msgs = [SystemMessage(content=SYSTEM_PROMPT), HumanMessage(content=build_prompt(item))]
    resp = await make_llm("scanner").ainvoke(msgs)
    return resp.content

# 4. Fan-out
fan_result: FanOutResult = await pool.run_all(
    items=items_list,
    task=task,
    role="scanner",
    model_id=role_cfg["model_id"],
    max_concurrency=role_cfg["max_concurrency"],
)

# 5. Handle partial failure
for item, result in fan_result.successes:
    ...  # process successful results
for err in fan_result.errors:
    logger.warning("Fan-out error for %s: %s", err.item, err.exception)
```

**Semaphore caveat:** SubagentPool creates the semaphore inside `run_all()` (not in `__init__`) so it binds to the correct event loop. This is already handled — no action needed.

**Token metadata:** `response.usage_metadata` may be None on Bedrock throttling. The pool's `_write_trace()` already guards this — task closures do not need to handle it.

---

## MCP Tool Registration Pattern

From `server.py` — the `wiki_query` pattern is definitive:

```python
class WikiLogInput(BaseModel):
    op: str = Field(..., description="Log operation type (scan/ingest/lint/create/update/delete/note)")
    title: str = Field(..., description="Short title for the log entry")
    detail: str | None = Field(None, description="Optional extended detail")
    vault_path: str = Field("", description="Vault path (default: CODE_WIKI_REAL_VAULT_PATH)")

class WikiLogOutput(BaseModel):
    status: str
    log_path: str
    date: str
    op: str
    title: str

@mcp.tool(name="wiki_log", description="...")
async def wiki_log(input: WikiLogInput, ctx: Context) -> WikiLogOutput:
    vault = Path(input.vault_path) if input.vault_path else None
    result = await run_log(input.op, input.title, input.detail, vault)
    return WikiLogOutput(...)
```

**Progress notifications** for long-running tools:
```python
await ctx.report_progress(progress=0, total=N, message="Starting scan")
# ... after discovery phase ...
await ctx.report_progress(progress=1, total=3, message=f"Found {len(packages)} packages")
# ... after fan-out ...
await ctx.report_progress(progress=2, total=3, message=f"Generated {len(stubs)} stubs")
```

**Error handling (MCP-04):** Wrap command logic in try/except:
```python
try:
    result = await run_scan(...)
except Exception as exc:
    logger.error("wiki_scan failed: %s", exc)
    raise  # FastMCP converts exceptions to structured MCP error responses
```

**`_StdoutGuard` compatibility:** All new imports go AFTER the `_StdoutGuard` is installed and AFTER `logging.basicConfig(stream=sys.stderr)`. Follow the exact import ordering already in server.py.

---

## `--config` Flag Implementation Pattern

**New file: `code_wiki_agent/config.py`**

```python
# config.py
import tomllib
from dataclasses import dataclass, field
from pathlib import Path

@dataclass
class WikiConfig:
    models_path: str | None = None
    vault_path: str | None = None
    state_gate_enabled: bool = True

_active_config: WikiConfig = WikiConfig()

def load_config(path: Path) -> WikiConfig:
    with path.open("rb") as f:
        data = tomllib.load(f)
    return WikiConfig(**{k: v for k, v in data.items() if k in WikiConfig.__dataclass_fields__})

def get_config() -> WikiConfig:
    return _active_config
```

**Typer callback in `cli.py`:**

```python
@app.callback()
def main_callback(
    config: Optional[Path] = typer.Option(None, "--config", help="Path to config TOML file"),
) -> None:
    """code-wiki-agent: AWS Bedrock-powered wiki maintenance."""
    if config is not None:
        from code_wiki_agent.config import load_config, _active_config
        import code_wiki_agent.config as _cfg_module
        loaded = load_config(config)
        _cfg_module._active_config = loaded
```

**MCP server in `server.py` `main()`:**
```python
def main() -> None:
    import os
    config_path_str = os.environ.get("CODE_WIKI_CONFIG")
    if config_path_str:
        from code_wiki_agent.config import load_config
        import code_wiki_agent.config as _cfg_module
        _cfg_module._active_config = load_config(Path(config_path_str))
    mcp.run(transport="stdio")
```

---

## Test Strategy

### Existing test infrastructure to reuse

- `vault_io/tests/fixtures/round-trip-vault/` — real vault with packages, concepts, adrs
- `vault_io/tests/fixtures/single-package-vault/` — minimal vault (packages/ dir, index.md, log.md)
- `vault_io/tests/fixtures/edge-case-vault/` — broken links, truncated frontmatter, etc.
- `INTEGRATION_GATE = pytest.mark.skipif(not CODE_WIKI_RUN_INTEGRATION, ...)` pattern in agent conftest
- Existing fake Bedrock response fixture pattern from subagent-runtime tests

### Per-command test strategy

**`log` (CMD-06):**
- Unit: call `run_log()` with `tmp_path` vault containing a valid `log.md`; assert entry appended with correct format
- Unit: verify `append_log.VALID_OPS` all accepted; invalid op raises/returns error
- No integration test needed (no LLM)

**`init` (CMD-01):**
- Unit: call `run_init()` with `tmp_path`; assert directory structure (concepts/, adrs/, index.md, log.md, .templates/, CLAUDE.md)
- Unit: `--force` flag allows overwriting non-empty dir
- Parity: compare output structure against `single-package-vault` fixture (existing committed vault shows expected init output)

**`scan` (CMD-02) — parity test:**
- Unit (deterministic phase): `discover_workspaces()` against a fixture monorepo with at least one pyproject.toml; verify diff JSON shape `{added, updated, deleted, renamed}`
- Integration (gated): call `run_scan()` with `CODE_WIKI_RUN_INTEGRATION=1`; verify stub pages written with valid frontmatter
- Parity: given the `single-package-vault` fixture, verify scan produces a `ScanResult` with valid JSON structure and the correct packages

**`ingest` (CMD-03) — parity test:**
- Unit (deterministic): test `extract()`, `slugify()`, `guess_source_type()` from ported `ingest_source.py`
- Unit (deterministic): test `_parse_frontmatter()`, `_validate()`, `_emit_yaml()` from ported `ingest_work_item.py`
- Integration (gated): call `run_ingest("source", ...)` with a real .md file; verify page written + index updated
- Parity criterion: the written page has valid frontmatter (title, category, summary) — structural assertion, not LLM output quality

**`lint` (CMD-05) — parity test:**
- Unit: call mechanical pass against `edge-case-vault/` fixture; verify known broken links and orphans are detected
- Unit: verify `_is_placeholder_target()` filter suppresses `[[wiki/...]]` and `[[work/<slug>]]` patterns (success criterion 3)
- Unit: verify each of 7 ported lint modules produces correct output against fixture data
- Integration (gated): call full `run_lint()` with real vault; verify semantic findings list is non-empty
- Parity: run mechanical pass against `round-trip-vault/`; compare finding counts to a recorded baseline (stored as `tests/commands/lint-baseline.json`)

**`wiki_*` MCP tools:**
- Unit: test Pydantic input/output schema validation (same pattern as `test_mcp_query_schema.py`)
- Unit: test `_StdoutGuard` still enforced when new tools are imported
- Integration (gated): call `wiki_scan` and `wiki_lint` via MCP stdio session; verify structured JSON-RPC responses

### Parity test shape

"Parity test" as defined in success criterion 5 means **structural metrics**, not exact text match:
- Wikilinks in output resolve (G1 check)
- Frontmatter fields present (title, category, summary)
- Package coverage: packages in diff["new"] appear as written stub pages
- `--json` output matches expected JSON schema (uses `eval_harness.structural` module already built in Phase 4)

---

## Wave Sequencing

### Wave 1: Thin wrappers + config (can parallelize with Wave 2)

Dependencies: none (vault_io already has append_log, init_vault)

Tasks:
1. Create `config.py` + `load_config()` function
2. Add Typer `@app.callback()` with `--config` global option
3. Add `CODE_WIKI_CONFIG` env var read in `server.py:main()`
4. Create `commands/log.py` with `run_log()` + `LogResult`
5. Create `commands/init.py` with `run_init()` + `InitResult`
6. Add `@app.command()` for `log` and `init` to `cli.py`
7. Register `wiki_log` and `wiki_init` MCP tools in `server.py`
8. Unit tests for log and init commands
9. Unit tests for wiki_log and wiki_init schemas

### Wave 2: Port 7 lint mechanical modules (can parallelize with Wave 1)

Dependencies: `vault_io.lint.common` is already complete

Tasks (can be done as one atomic task since they're all import-swap ports):
1. Port `vault_io/lint/container.py`
2. Port `vault_io/lint/dependency.py`
3. Port `vault_io/lint/domain.py`
4. Port `vault_io/lint/file_map.py`
5. Port `vault_io/lint/package_sync.py`
6. Port `vault_io/lint/source_sync.py`
7. Port `vault_io/lint/workflow_hints.py`
8. Unit tests for each module against fixture vaults

### Wave 3: Port ingest vault_io modules

Dependencies: Wave 1 (config.py needed for vault path resolution), `vault_io.update_index` and `vault_io.append_log` (already exist)

Tasks:
1. Port `vault_io/ingest_source.py` (remove version check, swap imports)
2. Port `vault_io/ingest_work_item.py` (replace `_run_helper()` subprocess calls with direct imports)
3. Unit tests for extract(), slugify(), guess_source_type(), _parse_frontmatter(), _validate()

### Wave 4: Implement scan + ingest commands

Dependencies: Wave 2 (scan doesn't need lint modules, but group for clarity), Wave 3 (ingest_source needed)

Tasks:
1. Create `commands/scan.py` with `run_scan()`, `ScanResult`, `SCANNER_SYSTEM` prompt
2. Add `@app.command()` for `scan` to `cli.py`
3. Register `wiki_scan` MCP tool in `server.py`
4. Create `commands/ingest.py` with `run_ingest()`, `IngestResult`, `INGESTOR_SYSTEM` prompt
5. Add Typer sub-app for `ingest source / work-item` to `cli.py`
6. Register `wiki_ingest` MCP tool in `server.py` (planner decides: one tool or two)
7. Integration tests (gated) for scan + ingest

### Wave 5: Implement lint command

Dependencies: Wave 2 (all 7 modules must be ported first)

Tasks:
1. Create `commands/lint.py` with `run_lint()`, `LintResult`, mechanical orchestration, `LINTER_*_SYSTEM` prompts
2. Add `@app.command()` for `lint` to `cli.py`
3. Register `wiki_lint` MCP tool in `server.py`
4. Unit tests for mechanical pass against edge-case-vault
5. Integration tests (gated) for full lint with LLM semantic pass

### Wave 6: Parity tests + final verification

Tasks:
1. `tests/commands/test_scan_parity.py` — structural metric assertions
2. `tests/commands/test_lint_parity.py` — broken link/orphan count assertions against edge-case-vault
3. `tests/commands/test_ingest_parity.py` — frontmatter validity check after ingest
4. Full suite run + success criterion verification

---

## Validation Architecture

### Test Framework
| Property | Value |
|----------|-------|
| Framework | pytest ≥8.3, pytest-asyncio 1.3.0, syrupy 5.1.0 |
| Config file | Each package has its own `pyproject.toml` with `[tool.pytest.ini_options]` |
| Quick run command | `uv run --package code-wiki-agent pytest agents/code-wiki-agent/tests/unit -x` |
| Full suite command | `uv run pytest cores/vault-io/tests agents/code-wiki-agent/tests -x` |

### Phase Requirements → Test Map

| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| CMD-06 | `run_log()` appends formatted entry to log.md | unit | `pytest agents/code-wiki-agent/tests/unit/test_commands_log.py -x` | No — Wave 1 |
| CMD-01 | `run_init()` creates vault structure + schema files | unit | `pytest agents/code-wiki-agent/tests/unit/test_commands_init.py -x` | No — Wave 1 |
| CMD-02 | `run_scan()` produces `ScanResult` with correct diff shape | unit | `pytest agents/code-wiki-agent/tests/unit/test_commands_scan.py -x` | No — Wave 4 |
| CMD-03 | `extract()`, `slugify()`, `_validate()` from ported modules | unit | `pytest cores/vault-io/tests/test_ingest_source.py cores/vault-io/tests/test_ingest_work_item.py -x` | No — Wave 3 |
| CMD-05 | Mechanical lint pass detects orphans + broken links | unit | `pytest cores/vault-io/tests/test_lint_modules.py -x` | No — Wave 2 |
| CMD-05 | `_is_placeholder_target()` suppresses [[wiki/...]] links | unit | `pytest cores/vault-io/tests/test_wikilink_predicate.py -x` | YES (already exists) |
| MCP-01 | `wiki_log`, `wiki_init` schema valid, `wiki_scan`, `wiki_lint` registered | unit | `pytest agents/code-wiki-agent/tests/unit/test_mcp_tool_schemas.py -x` | No — Wave 1/5 |
| MCP-03 | `ctx.report_progress()` called in wiki_scan, wiki_lint, wiki_ingest | integration | `pytest agents/code-wiki-agent/tests/integration/test_mcp_stdio.py -x` | Partial (exists, needs extension) |

### Sampling Rate
- Per task commit: `uv run --package code-wiki-agent pytest agents/code-wiki-agent/tests/unit -x -q`
- Per wave merge: `uv run pytest cores/vault-io/tests agents/code-wiki-agent/tests/unit -x`
- Phase gate: Full suite green before `/gsd-verify-work`

### Wave 0 Gaps
- [ ] `agents/code-wiki-agent/tests/unit/test_commands_log.py`
- [ ] `agents/code-wiki-agent/tests/unit/test_commands_init.py`
- [ ] `agents/code-wiki-agent/tests/unit/test_commands_scan.py`
- [ ] `agents/code-wiki-agent/tests/unit/test_commands_ingest.py`
- [ ] `agents/code-wiki-agent/tests/unit/test_commands_lint.py`
- [ ] `agents/code-wiki-agent/tests/unit/test_mcp_new_tools.py`
- [ ] `cores/vault-io/tests/test_ingest_source.py`
- [ ] `cores/vault-io/tests/test_ingest_work_item.py`
- [ ] `cores/vault-io/tests/test_lint_modules.py`
- [ ] `agents/code-wiki-agent/tests/commands/test_scan_parity.py`
- [ ] `agents/code-wiki-agent/tests/commands/test_lint_parity.py`

---

## Key Risks / Landmines

### Risk 1: Lint mechanical pass is inline in `lint_wiki.py:scan()`, NOT in the 7 modules
**What:** The orphan detection, broken wikilink scan (including page walk, link graph construction, placeholder filter), stale detection, missing frontmatter, duplicate titles, and log gap are all inline code in `lint_wiki.py:scan()` — NOT in any of the 7 modules. The 7 modules only cover: container drift, dependency layer, domain placement, file map drift, package sync, source sync, workflow hints.
**Impact:** Phase planner must allocate a significant task to port the inline `scan()` function logic into `commands/lint.py`, in addition to importing the 7 modules.
**Resolution:** Read `lint_wiki.py:scan()` lines 77-331 carefully when implementing `commands/lint.py`. This is ~200 lines of pure Python that needs to be present in the command layer.

### Risk 2: `ingest_work_item.py` uses `_run_helper()` subprocess calls
**What:** The work-item ingestor calls `update_index.py` and `append_log.py` as subprocesses using `sys.executable`. In deep-agents, these are direct Python imports.
**Impact:** If ported verbatim, the subprocess calls will fail because the scripts are not on PATH in the vault_io package structure.
**Resolution:** Replace `_run_helper("update_index.py")` → direct `update_index(wiki)` call, and `_run_helper("append_log.py", ...)` → direct `append_log(wiki, ...)` call. This is the correct approach and is identified in the port gap analysis above.

### Risk 3: `init_vault.py` has `TODO Phase 5: workspace init`
**What:** The current `init_wiki()` does not create `<workspace>/raw/` and `<workspace>/work/` directories. The original lattice-wiki init created these via `workspace.init()`.
**Impact:** Success criterion 1 says "matching lattice-wiki's init output structure" — if that means those directories, the TODO must be resolved.
**Resolution:** Simple `mkdir(parents=True, exist_ok=True)` for `wiki.parent / "raw"` and `wiki.parent / "work"` is sufficient. No complex logic needed.

### Risk 4: Scanner subagent prompt design is undefined
**What:** The SCANNER_SYSTEM prompt must produce valid markdown with correct frontmatter schema. Getting this wrong means stubs need re-generation.
**Impact:** Frontmatter schema mismatch causes lint failures and breaks update_index parsing.
**Resolution:** Planner must define the exact expected frontmatter fields (`title`, `category`, `summary`, `package_path`/`app_path`, `language`, `version`, `depends_on`, `exports`) and include them explicitly in the system prompt with an example. The scanner role has only 500 max_tokens — prompts must be concise.

### Risk 5: `scanner` role max_tokens is 500
**What:** The scanner role in models.toml has `max_tokens = 500`. A stub page with frontmatter and a few sections will typically be 300-500 tokens of output.
**Impact:** Rich stub pages with a detailed `## File map` section will be truncated.
**Resolution:** The scanner generates the stub BODY only (not the file map section — that comes from `build_file_map()` which is deterministic). The file map is appended separately after the LLM response. This keeps the LLM output under 500 tokens. Plan must make this explicit.

### Risk 6: `scan_monorepo.py` is already in vault_io, not in lattice-wiki-core/lint/
**What:** `lint/file_map.py` in lattice-wiki-core imports `from lattice_wiki_core.scan_monorepo import _git_ls_files`. Since `scan_monorepo.py` is already ported into `vault_io`, this import becomes `from vault_io.scan_monorepo import _git_ls_files`. However, `_git_ls_files` is a private function (underscore prefix).
**Impact:** Importing a private function from another module is technically a code smell but is acceptable here since both modules are in the same package and the function is unchanged.
**Resolution:** Keep `_git_ls_files` in `scan_monorepo.py` and import it by name in `vault_io/lint/file_map.py`. No rename needed — the lattice-wiki-core source does the same thing.

### Risk 7: `ingest_source.py` uses `lattice_wiki_core.layout_io.ensure_subpage` for --pkg-dir
**What:** The `--pkg-dir` flow in `ingest_source.py:main()` calls `ensure_subpage()` from `layout_io`. This function is already in `vault_io.layout_io` (it was ported in Phase 1).
**Impact:** Minor — just an import to verify exists.
**Resolution:** Verify `ensure_subpage` is exported from `vault_io.layout_io` before implementing the `--pkg-dir` path in `commands/ingest.py`. [VERIFIED: `layout_io.py` was ported in Phase 1 and is confirmed to exist in vault_io]

### Risk 8: `ingest_work_item.py` writes to `wiki.parent / "work"`, not inside `wiki/`
**What:** Work items are filed at `<workspace>/work/<date>-<slug>.md`, which is a sibling of the wiki directory, not inside it. The `update_index()` call must also scan `work/` for the work category sub-index.
**Impact:** MCP tool and CLI must be clear about the vault_path vs workspace_path distinction. `wiki.parent` is the workspace; work items go there.
**Resolution:** `run_ingest("work-item", ...)` must accept `vault_path` and derive `workspace_path = vault_path.parent`. Document this in the command's help text.

---

## Environment Availability

Step 2.6: SKIPPED (no new external dependencies for this phase — all tools are existing Python packages already installed in the uv workspace).

---

## Project Constraints (from CLAUDE.md)

- Tech stack: Python 3.11+, uv workspace, langchain + langchain-aws + deepagents — no deviations
- Model provider: AWS Bedrock only — use `ChatBedrockConverse` via `make_llm(role)`, never direct Anthropic API
- MCP transport: stdio only (no SSE, no streamable-HTTP in v1)
- Vault format compatibility: must read existing lattice-wiki vaults without modification
- Testing: use `@pytest.mark.integration` + `INTEGRATION_GATE` mark for Bedrock-touching tests
- No secrets in code; no hardcoded model IDs (all in models.toml)
- All stdout from MCP server must route through `_StdoutGuard`; all logging to stderr

---

## Sources

### Primary (HIGH confidence — direct source inspection)

- `cores/vault-io/src/vault_io/append_log.py` — `append_log()` API verified
- `cores/vault-io/src/vault_io/init_vault.py` — `init_wiki()` API verified; TODO Phase 5 comment identified
- `cores/vault-io/src/vault_io/scan_monorepo.py` — complete `discover_workspaces()`, `compute_diff()`, `build_file_map()`, `pick_representative()` verified
- `cores/vault-io/src/vault_io/lint/common.py` — all shared symbols verified; `_is_placeholder_target()` confirmed present
- `cores/vault-io/src/vault_io/update_index.py` — exists and provides `update_index()` equivalent
- `cores/subagent-runtime/src/subagent_runtime/pool.py` — `SubagentPool.run_all()` API verified
- `cores/model-adapter/src/model_adapter/models.toml` — scanner, linter, ingestor roles all present; no schema changes needed
- `cores/model-adapter/src/model_adapter/loader.py` — `make_llm()`, `load_role_config()` API verified
- `agents/code-wiki-agent/src/code_wiki_agent/commands/query.py` — THE PATTERN: confirmed complete
- `agents/code-wiki-agent/src/code_wiki_mcp/server.py` — `_StdoutGuard`, `ctx.report_progress()`, FastMCP registration pattern verified
- `agents/code-wiki-agent/src/code_wiki_agent/cli.py` — existing commands verified; Typer app structure confirmed
- `/Users/pat/Personal/lattice/packages/lattice-wiki-core/src/lattice_wiki_core/ingest_source.py` — port target verified
- `/Users/pat/Personal/lattice/packages/lattice-wiki-core/src/lattice_wiki_core/ingest_work_item.py` — port target verified; `_run_helper()` subprocess pattern identified
- `/Users/pat/Personal/lattice/packages/lattice-wiki-core/src/lattice_wiki_core/lint_wiki.py` — orchestration pattern and inline scan() logic verified; default thresholds confirmed (stale_days=90, log_gap_days=14)
- `/Users/pat/Personal/lattice/packages/lattice-wiki-core/src/lattice_wiki_core/lint/*.py` — all 7 modules inspected; import changes catalogued

---

## Assumptions Log

| # | Claim | Section | Risk if Wrong |
|---|-------|---------|---------------|
| A1 | `ensure_subpage()` is exported from `vault_io.layout_io` (assumed present from Phase 1 scope) | Port Gaps — ingest_source | Ingest `--pkg-dir` path fails; fix: add function if missing |
| A2 | `update_index(wiki)` is the correct call signature for `vault_io.update_index` | Command Implementation — ingest | Cross-ref update fails; fix: verify exact function signature |

**All other claims are VERIFIED by direct source inspection.**

---

## RESEARCH COMPLETE

**Phase:** 05 — Remaining Commands
**Confidence:** HIGH

### Key Findings

1. **models.toml is already complete** — `scanner`, `linter`, `ingestor` roles are defined. No schema changes needed in Phase 5.

2. **The 7 lint modules are a straight import-swap port** — every `from lattice_wiki_core.X` becomes `from vault_io.X`. The logic is unchanged. Total effort: LOW.

3. **The inline `scan()` function in `lint_wiki.py` (lines 77–331) must also be ported** — orphan/broken-link/stale/missing-fm logic lives here, not in the 7 modules. The 7 modules are supplementary checks only. This is the largest single porting task in the phase.

4. **`_run_helper()` subprocess calls in `ingest_work_item.py` must be replaced with direct imports** — porting this verbatim breaks. Replace with `update_index(wiki)` and `append_log(wiki, ...)` direct calls.

5. **Scanner role max_tokens = 500** — stub generation must produce body-only (not file map). File map is appended from deterministic `build_file_map()` output. Planner must make this explicit in the stub assembly logic.

### Confidence Assessment

| Area | Level | Reason |
|------|-------|--------|
| Existing code inventory | HIGH | Direct file inspection of all relevant files |
| Port gap analysis | HIGH | Verified each module exists or does not exist |
| models.toml completeness | HIGH | File read confirms all roles present |
| Command implementation patterns | HIGH | `query.py` and `server.py` are definitive references |
| Lint module import changes | HIGH | All 7 modules inspected, imports catalogued |
| Ingest work-item subprocess issue | HIGH | `_run_helper()` pattern identified and fix specified |

### Open Questions

1. **`init_vault.py` TODO Phase 5** — should workspace bootstrap create `raw/` and `work/` sibling directories? Answer determines whether `run_init()` adds `mkdir` calls. Recommend YES (two lines of code, full parity).

2. **MCP ingest tool split** — planner's discretion per D-04: one `wiki_ingest` tool with `type` field, or two separate tools? Recommendation: one tool with `type: Literal["source", "work-item"]` field for cleaner MCP tool description space.

3. **Scanner stub format** — what exact markdown does the scanner subagent write? Planner must define the system prompt with a concrete stub template showing required frontmatter fields and section structure. The scanner has only 500 max_tokens.

### File Created
`.planning/phases/05-remaining-commands/05-RESEARCH.md`

### Ready for Planning
Research complete. Planner can now create PLAN.md files.
