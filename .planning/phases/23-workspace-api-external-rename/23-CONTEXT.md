# Phase 23: workspace-api-external-rename - Context

**Gathered:** 2026-05-20
**Status:** Ready for planning

<domain>
## Phase Boundary

Cut over the **externally-visible workspace API surfaces** from `vault_path` / `--vault` to `workspace_path` / `--workspace`, and add the **brand-gate** that prevents reintroduction. Internal Python kwargs and call sites were already cleaned in Phase 22, so this phase moves the outer skin only.

Surfaces in scope:

- **MCP Pydantic input schemas (WSMCP-01)** — 6 input classes in `agents/graph-wiki-agent/src/graph_wiki_mcp/server.py` (`WikiQueryInput` line 103, `WikiLogInput` 150, `WikiBootstrapInput` 192, `WikiScanInput` 242, `WikiIngestInput` 299, `WikiLintInput` 374); each `vault_path: str = Field(...)` → `workspace_path: str = Field(...)`; descriptions updated; internal reads of `input.vault_path` → `input.workspace_path`.
- **Typer CLI flags (WSMCP-02)** — 7 `vault: str = typer.Option("", "--vault", ...)` declarations in `agents/graph-wiki-agent/src/graph_wiki_agent/cli.py` (lines 382, 420, 442, 463, 501, …); Python param name → `workspace`, flag literal → `--workspace`, help text mentions `GRAPH_WIKI_WORKSPACE`.
- **New `--repo` flag for bootstrap (WSMCP-03)** — additive Typer option on `bootstrap` only.
- **Scan JSON output field (WSMCP-04)** — `packages/wiki-io/src/wiki_io/scan_monorepo.py`: helper `_vault_path_for` → `_wiki_relative_path_for` (line 399); 3 emission sites (lines 395, 666, 717) — all currently relative to the wiki directory, semantically correct under the new name; docstring at line 616.
- **Plugin markdown docs (WSMCP-05)** — sync 5 plugin files (`plugins/graph-wiki/agents/scanner.md`, `plugins/graph-wiki/skills/graph-wiki/references/{scan-workflow,detection-workflow,wiki-schema}.md`, `plugins/graph-wiki/commands/scan.md`) plus `packages/prompt-sources/references/*.md` mirrors.
- **DA-CLI integration test (WSMCP-06)** — `agents/graph-wiki-agent/tests/integration/test_mcp_e2e.py` updated for new field + flag names; runs under `GRAPH_WIKI_RUN_INTEGRATION=1`.
- **Brand-gate extension (WSMCP-07)** — `scripts/check-brand.sh` gains a regex rule banning the 3 literal patterns named in the REQ; `.brand-grep-allow` narrowly seeded for any unavoidable historical refs.

**Explicitly NOT in this phase:**
- `--repo` flag on commands other than `bootstrap` (D-02 below; deferred to future phase if ergonomics demand it)
- Wider brand-gate scope (D-03 below; kwarg/test-mock bans deferred)
- eval-harness `vault_path` sweep — Phase 24
- `packages/` misclassification fix — Phase 25
- `wiki-io` package directory/module name — out of milestone scope

</domain>

<decisions>
## Implementation Decisions

### Plan Chunking
- **D-01:** **Big-bang single plan** — all 7 WSMCP requirements land in one plan and one commit. Mirrors the Phase 22 posture (atomic, bisect-hostile, but eliminates ordering risk between the MCP/CLI rename, integration test update, brand-gate addition, and plugin docs sweep). The intermediate state where (e.g.) the brand-gate is live but plugin docs still contain the old name would be self-failing; keeping them together avoids that.

### --repo Flag Scope (WSMCP-03)
- **D-02:** **Bootstrap-only.** `--repo` is added as a Typer option on `graph-wiki-agent bootstrap` and nowhere else. Other commands (scan, lint, ingest, query, log) continue to resolve repo root via CWD walk-up. Trade-off: minor ergonomic loss for users who want to point scan at an arbitrary repo without `cd`-ing, accepted in exchange for a smaller surface change and no help-text drift across commands.

### Brand-Gate Strictness (WSMCP-07)
- **D-03:** **Minimal — exactly what the REQ literal names.** The brand-gate bans three patterns only:
  1. `vault_path:` as a Pydantic Field name (regex anchored to a class-body context, e.g. `^\s+vault_path:\s+(str|Path)`).
  2. `--vault` as a Typer flag literal (regex: `"--vault"` inside a `typer.Option(...)` call).
  3. `"vault_path"` as a scan JSON field key (regex: `"vault_path"` as a dict key in a Python literal).
  - The gate runs across `agents/`, `packages/`, `plugins/` (mirrors the existing brand-gate's path scope).
  - `.planning/` is excluded — historical phase docs (this CONTEXT.md, Phase 22 summary, REQUIREMENTS.md history) legitimately reference the old name and must not be edited.
  - Tests are NOT excluded — test files can still contain the string `vault_path` as a *string literal* (e.g., asserting that an MCP call with `{"vault_path": ...}` fails schema validation), but cannot declare a Pydantic Field with that name.
  - `.brand-grep-allow` is seeded with any unavoidable historical refs that surface during the dry-run.

### Integration Test Gate (WSMCP-06)
- **D-04:** **Update mechanically + opportunistic auto-run.** The executor updates `test_mcp_e2e.py` as part of the mechanical sweep (rename MCP field names + Typer flag literals in the test). Then, in the plan's verification step:
  - If `GRAPH_WIKI_RUN_INTEGRATION=1` env var is set AND AWS credentials resolve, the executor runs `uv run pytest agents/graph-wiki-agent/tests/integration/test_mcp_e2e.py` and treats a non-zero exit as a plan-level failure.
  - Otherwise, the executor records a manual UAT line in SUMMARY.md (`UAT-01: run integration test against live Bedrock`) and Pat runs it before phase verification.
  - Default `uv run pytest` (no env var) remains the always-green gate for plan completion.

### Carried Forward (milestone-level locks — non-negotiable)
- **D-05:** Hard rename, no back-compat shims. No deprecation period for the old field/flag names. (Phase 22 D-07.)
- **D-06:** Wiki path always derived via `workspace_io.paths.wiki_dir()` — never string concatenation. (Phase 22 D-09. Applies here at the MCP server's internal call sites where `Path(input.workspace_path)` is converted into the wiki dir.)
- **D-07:** `wiki-io` package directory and `wiki_io` module path STAY. Only nomenclature changes, not module renames. (Phase 22 D-10.)
- **D-08:** Plugin markdown docs sync includes BOTH the named `plugins/graph-wiki/...` files AND the `packages/prompt-sources/references/*.md` mirrors — the prompt-sources mirrors are loaded into agent system prompts at runtime, so divergence would silently regress agent behavior.

### Claude's Discretion
- Field description text rewording (e.g., "Vault path" → "Workspace path") is at executor's discretion as long as the term `vault` is purged.
- The brand-gate regex implementation (extending the existing `check-brand.sh` vs. adding a sibling script) is at executor's discretion; keeping it in `check-brand.sh` is the preferred path per existing convention.
- Plugin doc sweep order (per-file vs all-at-once) is mechanical.
- `--repo` flag implementation details (default value, help text wording, validation of supplied path) are executor's call.

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Milestone requirements (locked decisions)
- `.planning/REQUIREMENTS.md` §"Workspace API — External Rename (WSMCP)" — WSMCP-01 through WSMCP-07 acceptance criteria
- `.planning/ROADMAP.md` §"Phase 23: workspace-api-external-rename" — goal + 5 numbered success criteria

### Files in the rename surface
- `agents/graph-wiki-agent/src/graph_wiki_mcp/server.py` — 6 MCP input Pydantic classes (lines 103, 150, 192, 242, 299, 374) + their internal reads of `input.vault_path`
- `agents/graph-wiki-agent/src/graph_wiki_agent/cli.py` — 7 Typer command signatures with `--vault`; bootstrap also gets new `--repo`
- `packages/wiki-io/src/wiki_io/scan_monorepo.py` — `_vault_path_for` helper (line 399), 3 emission sites (lines 395, 666, 717), docstring (line 616)
- `agents/graph-wiki-agent/tests/integration/test_mcp_e2e.py` — DA-CLI integration test
- `scripts/check-brand.sh` — existing brand-gate to extend
- `.brand-grep-allow` — allowlist file at repo root

### Plugin docs (WSMCP-05)
- `plugins/graph-wiki/agents/scanner.md`
- `plugins/graph-wiki/skills/graph-wiki/references/scan-workflow.md`
- `plugins/graph-wiki/skills/graph-wiki/references/detection-workflow.md`
- `plugins/graph-wiki/skills/graph-wiki/references/wiki-schema.md`
- `plugins/graph-wiki/commands/scan.md`
- `packages/prompt-sources/references/*.md` — mirrors loaded into agent system prompts at runtime

### Prior phase artifacts
- `.planning/phases/22-workspace-api-internal-rename/22-CONTEXT.md` — milestone-level locks (hard rename, wiki_dir helper, no shim) plus the internal API state Phase 23 builds on
- `.planning/phases/22-workspace-api-internal-rename/22-01-SUMMARY.md` — what's already renamed internally; the MCP server's internal call edges already use `workspace_path=` kwargs

### Prior milestone precedent
- `.planning/milestones/v1.3-ROADMAP.md` Phase 12 (lattice → graph-wiki brand rename) — precedent for brand-gate-driven rename with allowlist
- `.planning/milestones/v1.3-ROADMAP.md` Phase 21 (code-wiki-agent → graph-wiki-agent rename) — precedent for atomic-rename with brand-gate extension; `scripts/check-brand.sh` Phase-21 §D-12 comment documents the pattern

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- `scripts/check-brand.sh` is already a working gate (lattice + code-wiki-agent rules). The WSMCP-07 extension is additive — the script already exists, takes an allowlist, walks `agents/`/`packages/`/`plugins/`/`.planning/`, and exits non-zero on hit. Add a new regex set behind the existing structure.
- `workspace_io.paths.wiki_dir(workspace_path)` — canonical derivation; the MCP server's `Path(input.vault_path)` → `Path(input.workspace_path)` conversions thread through this helper at the run_* call sites (already in place after Phase 22).
- `.brand-grep-allow` already exists at repo root with allowlist patterns from Phases 12 and 21 — extend, don't replace.

### Established Patterns
- All 6 MCP input classes follow the same `vault_path: str = Field("", description="Vault path (default: GRAPH_WIKI_WORKSPACE env var)")` shape — mechanically uniform.
- All 7 Typer `--vault` declarations follow `vault: str = typer.Option("", "--vault", help="Vault path (default: ...)")` — mechanically uniform; Python param name and flag literal both rename in lockstep.
- All 3 scan JSON emission sites currently use the same key `"vault_path"`; lines 666/717 explicitly compute `str(md.relative_to(wiki))` (already wiki-relative), and line 395 invokes `_vault_path_for` whose output is also wiki-relative (e.g., `apps/<name>/<name>.md`). The semantic of `wiki_relative_path` holds uniformly across all 3.

### Integration Points
- MCP server's internal call sites (`vault = Path(input.vault_path) if input.vault_path else None`) on lines 125, 169, 215, 266, 332, 411 — these read the field name and bind to a local var. The local var `vault` is fine to leave or rename; the field-read MUST change.
- DA-CLI integration test (`test_mcp_e2e.py`) calls MCP tools by name with JSON payloads containing the field names — these must move in lockstep with the schema rename, otherwise the test fails before the rename is even shipped. This is the strongest argument for D-01's big-bang plan.
- Plugin docs at `plugins/graph-wiki/...` are NOT executed by `graph-wiki-agent` (the plugin runs on Claude Code inference, not Bedrock — see project memory). The sync requirement is documentation-fidelity, not behavioral.
- `packages/prompt-sources/references/*.md` mirrors ARE loaded into agent system prompts at runtime (per Phase 19's subagent context completion work) — drift here = silent behavior regression.

</code_context>

<specifics>
## Specific Ideas

- "Single big-bang plan" mirrors Phase 22's deliberate trade-off (atomic, bisect-hostile, but no intermediate-state breakage). The integration test that exercises both the field rename and the flag rename in the same E2E flow is the structural reason — splitting would create a window where the test references one name but the schema another.
- "Minimal brand-gate" was a deliberate scope choice. Pat preferred the narrow REQ-literal interpretation over the aggressive everywhere-ban because historical `.planning/` and SUMMARY.md files contain `vault_path` references that legitimately must not be edited; an aggressive gate would need an enormous, decaying allowlist.
- "Bootstrap-only `--repo`" was a deliberate ergonomic narrowing. Pat preferred the minimal interpretation of WSMCP-03 over the "all commands" reading because adding `--repo` to scan/lint/ingest/query/log would also imply adding matching `repo_path` fields to those MCP input schemas — and that's a much larger surface change than the REQ literal demands.
- "Update + opportunistic auto-run" for the integration test is a hybrid: the test file rename is mechanical (always done), but the live Bedrock run is gated on env var presence so the executor doesn't burn credentials when they're not configured.

</specifics>

<deferred>
## Deferred Ideas

### Phase 24 (eval-harness-workspace-rename)
- `vault_path` sweep across `packages/eval-harness/src/eval_harness/{sweep,baseline,structural,divergence/*}.py` (WSEVAL-01 through WSEVAL-03)
- Bare `vault:` token in divergence helpers → `wiki:`

### Phase 25 (packages-dir-misclassification-fix)
- The pending todo `2026-05-20-fix-packages-dir-misclassification` — `_classify_dir` heuristic + `--interactive` opt-in on bootstrap

### Out of v1.4 milestone (later)
- Adding `--repo` flag to non-bootstrap commands (scan/lint/ingest/query/log) — if user ergonomics demand it
- Aggressive brand-gate: ban `vault_path=` kwargs in production code paths, ban string literal `vault_path` outside `.brand-grep-allow`
- MCP input `repo_path` field exposure (mirror of CLI `--repo`) — would let MCP callers override repo root explicitly
- Renaming `wiki-io` package directory and `wiki_io` module to `wiki-io`/`wiki_io` — explicitly out of milestone scope (Phase 22 D-10)
- Test-side schema rejection assertion: add an explicit unit test verifying that an MCP call with the old field `vault_path` fails Pydantic validation (success criteria #2 implies this; whether to add an explicit unit test or rely on integration test coverage is open)

</deferred>
