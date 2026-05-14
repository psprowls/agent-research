# Phase 5: Remaining Commands - Context

**Gathered:** 2026-05-14
**Status:** Ready for planning

<domain>
## Phase Boundary

This phase delivers full lattice-wiki parity: the 5 remaining commands (`log`, `init`, `scan`, `ingest`, `lint`) wired through both MCP tools and headless CLI subcommands. All 6 MCP tools are registered by end of phase. Progress notifications (MCP-03) fire for long-running commands.

Five deliverables:
1. **`log`** — thin wrapper around `vault_io.append_log`; simple, no LLM, no fan-out
2. **`init`** — thin wrapper around `vault_io.init_vault`; bootstraps vault structure, no LLM
3. **`scan`** — package discovery/diff via `scan_monorepo` + scanner subagent LLM fan-out for stub page generation
4. **`ingest`** — two subcommands (`ingest source` / `ingest work-item`); ingestor subagent does routing + summary generation; full cross-ref update after writing
5. **`lint`** — full mechanical pass (all 7 rule modules ported) + 3-group semantic LLM fan-out

**Also in scope:** `--config` global flag (CLI-05) and `CODE_WIKI_CONFIG` env var for MCP, and parity tests per command.

**Out of scope this phase:** eval baselines for the new commands (those come after Phase 4 eval infrastructure is complete), write-back after query, nested subagents, non-Bedrock providers.

</domain>

<decisions>
## Implementation Decisions

### ingest Command

- **D-01:** Port **both** `ingest_source.py` (source files: `.md/.txt/.html/.json/.csv`) AND `ingest_work_item.py` (work items / issues) from `lattice-wiki-core` into `vault_io`. Both are needed for full parity.
- **D-02:** The `ingestor` subagent determines the **target page type** (package/concept/adr) AND generates the page summary. No deterministic routing — LLM receives the extracted source text and metadata and decides where to file it and what to write.
- **D-03:** After writing a new or updated page, run a **full cross-reference update**: refresh `index.md` and update wikilink back-references in related pages. Full parity with lattice-wiki-core ingest behavior.
- **D-04:** Two **separate CLI subcommands**: `code-wiki-agent ingest source <path>` and `code-wiki-agent ingest work-item <path>`. The MCP surface should mirror this split — planner decides whether to register two MCP tools (`wiki_ingest_source`, `wiki_ingest_work_item`) or one `wiki_ingest` tool with a `type` field.

### Scan Command

- **D-05:** Scanner fan-out is **LLM-driven**: the scanner subagent receives package metadata + `build_file_map()` output + sampled source files (README, entry point, etc.) and uses LLM to write the stub page body. Stubs have meaningful content from day one.
- **D-06:** Package discovery, diff, and file_map come from `scan_monorepo.py` (deterministic). Only stub *content generation* goes through the scanner subagent. `SubagentPool.run_all()` fans out across packages that need new/updated stubs.
- **D-07:** When scan detects a **renamed or deleted package**: mark the vault page with a `stale` tag in frontmatter, append a deletion/rename event to `log.md`. No auto-delete. The flag shows up in the `{added, updated, deleted}` JSON diff output (success criterion 2).

### Lint Command

- **D-08:** Port **all 7 lint rule modules** from `lattice-wiki-core/lint/` (`container`, `dependency`, `domain`, `file_map`, `package_sync`, `source_sync`, `workflow_hints`) into `vault_io/lint/`. Full mechanical parity — this is what "full parity" means.
- **D-09:** Semantic LLM pass uses **3 broader rule-groups** (not one-per-module). Each group runs as a parallel linter subagent:
  1. **Page quality + contradictions** — intra-page coherence, internal contradictions, factual accuracy
  2. **ADR chain integrity** — ADR cross-references, decision history consistency
  3. **Stale claims + code-drift** — claims that contradict current source, outdated references
- **D-10:** Lint report format: `--json` flag emits a structured findings list (machine-readable); default stdout is human-readable text. No write-back to vault (no `lint.md` page created). Consistent with all other commands' `--json` behavior.

### `--config` Flag (CLI-05)

- **D-11:** `--config <path>` is a **global app-level Typer option** (Typer callback pattern) — available on all subcommands automatically with no per-subcommand repetition.
- **D-12:** The config file is a **full JSON/TOML config** covering models.toml path, default vault path, and other agent settings (not just models). Planner designs the schema — suggest: `models_path`, `vault_path`, `state_gate_enabled` as initial fields.
- **D-13:** The MCP server reads config path from a **`CODE_WIKI_CONFIG` env var** — same pattern as `CODE_WIKI_REAL_VAULT_PATH`. No CLI argument to the MCP server process itself.

### Claude's Discretion

- **MCP ingest tool split** — whether `wiki_ingest` is one tool with a `type` field or two tools (`wiki_ingest_source`, `wiki_ingest_work_item`); planner decides based on MCP tool description clarity.
- **Scanner source file sampling** — which files count as "representative samples" for a given package (README.md, primary entry point, etc.); planner designs the sampling heuristic using `pick_representative()` in `scan_monorepo.py`.
- **Config file format** — JSON vs. TOML; planner picks based on existing project conventions (models.toml is already TOML, so TOML is likely preferred).
- **Cross-ref update scope for ingest** — exactly which cross-reference updates are needed (index.md rebuild vs. selective back-ref updates); planner ports from `ingest_source.py` `main()` flow.
- **`--stale-days` / `--log-gap-days` thresholds for lint** — present as Typer options with defaults matching lattice-wiki-core; planner reads CMD-05.

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Project Planning
- `.planning/ROADMAP.md` §"Phase 5: Remaining Commands" — phase goal, success criteria (5 criteria), requirements (CMD-01..03, CMD-05..06, MCP-01, MCP-03)
- `.planning/REQUIREMENTS.md` §"Commands — Full Parity" (CMD-01..06), §"MCP Server Surface" (MCP-01, MCP-03), §"Headless CLI" (CLI-05) — full requirement text
- `.planning/PROJECT.md` §"Key Decisions" — "Full parity with lattice-wiki v1"; CLI-05 deferred note at bottom of table

### Prior Phase CONTEXT (patterns this phase extends)
- `.planning/phases/03-query-vertical-slice-hybrid-search/03-CONTEXT.md` — D-05 (`commands/` as single source of truth, CLI + MCP both import), D-06 (`QueryResult` dataclass pattern), D-08 (state-gate no-op for read-only commands)
- `.planning/phases/02-subagent-fan-out-runtime/02-CONTEXT.md` — D-04 (`SubagentPool.run_all()` API), D-06 (`FanOutResult`/`PerItemError` types), D-09 (tokens from `usage_metadata`)

### Existing Code — Phase 1–3 Deliverables
- `agents/code-wiki-agent/src/code_wiki_agent/commands/query.py` — **THE PATTERN**: how a command is structured (async `run_*()` function, dataclass result, guardrails). All 5 new commands follow this.
- `agents/code-wiki-agent/src/code_wiki_mcp/server.py` — MCP tool registration with Pydantic input/output schemas, `_StdoutGuard`, `ctx.report_progress()` call. All new MCP tools follow `wiki_query` structure.
- `agents/code-wiki-agent/src/code_wiki_agent/cli.py` — existing Typer `app`; all new subcommands add to this file. Global `--config` callback goes here.
- `cores/vault-io/src/vault_io/append_log.py` — `append_log(wiki, op, title, detail)` — direct call for `log` command
- `cores/vault-io/src/vault_io/init_vault.py` — `init_wiki(repo, ...)` — direct call for `init` command
- `cores/vault-io/src/vault_io/scan_monorepo.py` — `discover_workspaces()`, `compute_diff()`, `attach_changed_files()`, `build_file_map()`, `pick_representative()` — `scan` command building blocks
- `cores/vault-io/src/vault_io/lint/common.py` — `_is_placeholder_target()` (wikilink placeholder filter, VAULT-06) + markdown helpers — used by all 7 mechanical lint rule modules
- `cores/vault-io/src/vault_io/git_state.py` — state gate logic for commands that require clean git state
- `cores/vault-io/src/vault_io/update_index.py` — `index.md` format; updated after `ingest` and `scan`

### Reference Implementation — lattice-wiki-core (PORT SOURCE, not a dependency)
- `/Users/pat/Personal/lattice/packages/lattice-wiki-core/src/lattice_wiki_core/ingest_source.py` — **MUST READ**: `extract()`, `guess_source_type()`, `slugify()`, `folder_brief()`, `language_for()` — full port target for ingest source
- `/Users/pat/Personal/lattice/packages/lattice-wiki-core/src/lattice_wiki_core/ingest_work_item.py` — **MUST READ**: work item frontmatter schema, validation, `_slugify()` — port target for ingest work-item
- `/Users/pat/Personal/lattice/packages/lattice-wiki-core/src/lattice_wiki_core/lint_wiki.py` — **MUST READ**: top-level lint runner; how mechanical and semantic passes are orchestrated
- `/Users/pat/Personal/lattice/packages/lattice-wiki-core/src/lattice_wiki_core/lint/` — **MUST READ all 7 modules**: `container.py`, `dependency.py`, `domain.py`, `file_map.py`, `package_sync.py`, `source_sync.py`, `workflow_hints.py` — port all into `vault_io/lint/`
- `/Users/pat/Personal/lattice/packages/lattice-wiki-core/src/lattice_wiki_core/scan_monorepo.py` — cross-reference for scanner subagent behavior; check what the original scanner subagent did when writing stubs

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- `vault_io.append_log.append_log(wiki, op, title, detail, as_json=False)` — `log` command is a thin CLI/MCP wrapper around this call; no new logic needed
- `vault_io.init_vault.init_wiki(repo, non_interactive=True)` — `init` command is similarly a thin wrapper; non-interactive mode is the right path for MCP
- `vault_io.scan_monorepo.discover_workspaces()` / `compute_diff()` / `build_file_map()` — `scan` command uses these for the deterministic discovery phase before fan-out
- `vault_io.scan_monorepo.pick_representative()` — already exists for selecting representative source files to include in scanner subagent input (D-05)
- `vault_io.lint.common._is_placeholder_target()` — the wikilink placeholder filter (VAULT-06) is already ported; all 7 new mechanical lint modules should import this
- `cores/subagent-runtime/src/subagent_runtime/pool.py` — `SubagentPool.run_all()` handles scanner fan-out (one stub per package) and linter fan-out (3 rule-groups)
- `vault_io.update_index.py` — call after scan and ingest to refresh `index.md`

### Established Patterns
- **`commands/` shared layer** — every command lives in `agents/code-wiki-agent/src/code_wiki_agent/commands/<name>.py`; CLI subcommand + MCP tool both import the shared `run_*()` function (Phase 3 D-05)
- **`@pytest.mark.integration` + env var skip** — integration tests for new commands follow this pattern; no real Bedrock calls in CI
- **Typer subcommand structure** — `@app.command()` for simple commands; for `ingest source / work-item`, use a Typer sub-app (`ingest_app = typer.Typer(); app.add_typer(ingest_app, name="ingest")`)
- **`ctx.report_progress(progress, total, message)`** — called in MCP tools at key milestones (start, after fan-out, before return); already established by `wiki_query`
- **`--json` flag** — all commands follow the same pattern: if `json_output`, `typer.echo(json.dumps(dataclasses.asdict(result)))` else render human-readable

### Integration Points
- `agents/code-wiki-agent/src/code_wiki_agent/cli.py` — add 5 new subcommands (or sub-app for `ingest`); add global `--config` callback
- `agents/code-wiki-agent/src/code_wiki_mcp/server.py` — register all new MCP tools on the existing `mcp = FastMCP(...)` instance; `wiki_ping` and `wiki_query` are already there
- `cores/vault-io/src/vault_io/lint/` — add 7 new mechanical rule modules alongside `common.py`
- `cores/vault-io/` — add `ingest_source.py` and `ingest_work_item.py` as new vault_io modules (same member, new files)
- `cores/model-adapter/src/model_adapter/models.toml` — `scanner` and `linter` roles already defined; `ingestor` role needs to be added (planner verifies)

</code_context>

<specifics>
## Specific Ideas

- The `ingest source` subagent prompt should receive: (1) the file's extracted text (via `extract(path)` in `ingest_source.py`), (2) the file's path relative to the repo root, (3) the current vault structure (package names, category dirs). Subagent returns: target page slug, page type (package/concept/adr), and generated page body.
- For `scan`, the scanner subagent stub prompt should receive: package metadata dict (name, version, type, language), `build_file_map()` output, and up to 3 sampled source files from `pick_representative()`. The subagent writes the full stub page markdown (with frontmatter template).
- Lint `--stale-days` and `--log-gap-days` should be Typer options with the same defaults as `lattice-wiki-core`; researcher reads `lint_wiki.py` to find the current defaults.
- The global `--config` Typer callback should call a `load_config(path)` function in a new `config.py` module in `code_wiki_agent`; this sets the effective `models_path` and `vault_path` for the session.
- For ingest work-items, check whether `ingest_work_item.py` uses any external helpers (e.g., a helper script that it `_run_helper()`s) — those need to be either ported or replaced with vault_io equivalents.

</specifics>

<deferred>
## Deferred Ideas

- **Eval baselines for scan/lint/ingest/log** — Phase 4 context already noted this; baselines recorded after Phase 5 delivers working commands
- **`ingest` cross-ref deep linking** — beyond index.md refresh, updating wikilinks in every related page could be expensive; if the full cross-ref update proves too costly, planner may scope down to index-only for v1
- **Scanner subagent retry on stub conflict** — if two packages produce the same slug, collision handling is a future concern; for Phase 5, last-write-wins is acceptable
- **`wiki_ingest_work_item` MCP tool** — if planner determines the work-item ingest surface is too specialized for MCP exposure, it can be CLI-only for v1; flag this in the plan
- **Config schema versioning** — the `CODE_WIKI_CONFIG` file format may need versioning later; not needed for v1

</deferred>

---

*Phase: 5-Remaining Commands*
*Context gathered: 2026-05-14*
