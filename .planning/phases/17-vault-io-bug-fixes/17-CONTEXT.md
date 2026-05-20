# Phase 17: vault-io Bug Fixes - Context

**Gathered:** 2026-05-19
**Status:** Ready for planning

<domain>
## Phase Boundary

Burn down three independent behavioral bugs in `packages/vault-io/` that the v1.2 bootstrap-of-deep-agents-wiki surfaced. All are bug-fix grade — no new surface area, no new MCP tools, no new modules:

**In scope:**
- **SCAN-01/02** — Fold `wiki/packages/<pkg>/` companion files (`api`, `context`, `patterns`, `work`) into the parent `<pkg>` slug inside `scan_monorepo._load_existing_pages._collect()`, so the scan diff stops reporting 28 false-positive `deleted` entries on a healthy 7-package vault. Companion filename set sourced from `wiki/CLAUDE.md` `workflow_hints`. Unit test against a fixture vault asserts 0 `deleted` companion entries.
- **TOK-01/02** — Fix `vault_io.update_tokens.count_tokens()` to use the current boto3 `bedrock-runtime.count_tokens` parameter shape (`input={'converse': {'messages': [...]}}`), not the rejected `content=[...]` shape. Unit test mocks the boto3 client and asserts the exact request payload. Gated integration test (`CODE_WIKI_RUN_INTEGRATION=1`) exercises a real Bedrock call per `docs/testing.md` (Phase 16 D-10).
- **TOK-03** — Final plan step: re-run `update_tokens.py` against `~/Personal/wiki/deep-agents` to re-stamp the 35 pages currently at `tokens: 0`. Commit the resulting wiki updates in the wiki repo. Diff transcript captured in `17-VERIFICATION.md`.
- **WSRES-01** — In `init_vault.py:305-306` and `detect_containers.py:174-175`, replace `wiki, _ = resolve_wiki_and_repo(); repo = wiki.parent` with `_, repo = resolve_wiki_and_repo()`. Works for both v1 (wiki at repo root) and v2 (wiki at `<repo>/graph-wiki/wiki/`) layouts since `_workspace.resolve_wiki_and_repo()` already returns the correct `repo_root`.
- **WSRES-02** — Add optional `workspace_path` parameter to `detect_containers.detect()`. When provided and not equal to `repo_root`, skip the matching immediate subdir during iteration so the workspace dir doesn't classify itself as a `docs` container. `main()` passes `wiki.parent` explicitly.
- **WSRES-03** — Synthetic tmp_path fixture in `packages/vault-io/tests/`: build `repo/graph-wiki/wiki/` + `repo/packages/pkg-a/pyproject.toml` + `repo/packages/pkg-b/pyproject.toml`; set `GRAPH_WIKI_WORKSPACE`; call `detect(repo, workspace_path=repo/'graph-wiki')`; assert (1) `packages` is found as a container, (2) `graph-wiki` is not listed.
- **`17-VERIFICATION.md`** — Per-SC sections (#1–#5) citing the unit/integration test pytest output, the live re-stamp transcript (TOK-03), and a fresh `/graph-wiki:scan` output on the deep-agents wiki showing 0 companion-false-deletions and non-zero `tokens:` on previously-stubbed pages.

**Out of scope:**
- New `vault-io` modules, commands, or MCP tools (per REQUIREMENTS.md "Out of Scope" — v1.3 is bug-fix grade).
- Refactoring `_load_existing_pages` beyond the companion filter (no post-process pass, no per-directory iteration rewrite — see D-01).
- Hardcoded companion filenames (D-02 sources them from `workflow_hints`).
- Branching `count_tokens()` shape on `model_id` family — single converse shape (D-05).
- Fixture vault built into `packages/vault-io/tests/fixtures/` for live re-sweep (Phase 16 SWEEP-FU-04 territory, not Phase 17).
- Companion folding in `wiki/apps/<app>/` — app pages are single-file by design; no companions (per user clarification during discussion).
- `init_vault` schema-writing logic changes (the bug is repo resolution only; the schema install path is unaffected).
- Changing the `wiki/CLAUDE.md` `workflow_hints` block itself (the bug is the scanner reading it wrong, not the schema).
- Phase 18 (plugin `/init` → `/init-wiki` rename) and Phase 19 (Phase 16 review burndown) — separate phases.

</domain>

<decisions>
## Implementation Decisions

### SCAN — Companion-page folding (SCAN-01/02)

- **D-01 (Filter inside `_collect()`):** Add a companion filter inline in `scan_monorepo._load_existing_pages._collect()`. When walking `wiki/packages/<pkg>/*.md` (and `wiki/domains/<d>/packages/<pkg>/*.md`), skip files whose stem is in the companion set. The file whose stem equals the parent dir name (or the canonical `<pkg>.md`) populates `pages[name]`. Simplest fix — does not require a post-process pass over `pages` or a refactor to per-directory iteration. Two extra lines in `_collect()` plus the constant lookup. Rationale: the bug is bounded; the smaller diff is auditable and matches Phase 16 D-04's "narrow, eliminate the drift surface" preference.
- **D-02 (Companion list from `workflow_hints`):** Source the companion filename set from `wiki/CLAUDE.md`'s `workflow_hints` layout block via `layout_io.read_layout()`. Treats the schema file as authoritative. `_load_existing_pages()` reads the layout once at the top, passes the companion set into the nested `_collect()` calls.
- **D-03 (Empty-set fallback when hints absent):** If the layout block is missing OR `workflow_hints` doesn't declare companions, the companion set is empty — i.e. today's pre-fix behavior. No silent baked-in `{api, context, patterns, work}` default. Rationale: the vault owner controls the schema; we don't pretend they declared something they didn't. If a vault has companions on disk but no declaration, the scan correctly reports them as deletions until the schema catches up.
- **D-04 (Fold scope = packages + domain-scoped packages):** Apply the companion filter when iterating `wiki/packages/` AND inside the `domains_dir` loop for `wiki/domains/<d>/packages/<pkg>/`. Do NOT apply to `wiki/apps/` — app pages are single-file by user convention (no `api/context/patterns/work` companions). Layout-pinned `package` / `app` containers in CLAUDE.md follow the same rule (package containers get the filter, app containers don't).

### TOK — Bedrock CountTokens API shape (TOK-01/02/03)

- **D-05 (Converse input shape):** `count_tokens()` uses `input={'converse': {'messages': [{'role': 'user', 'content': [{'text': text}]}]}}`. Verified against `boto3.client('bedrock-runtime').count_tokens` help: the API accepts either `{'invokeModel': {'body': bytes}}` or `{'converse': {'messages': [...]}}`. Converse matches how the rest of the codebase invokes Bedrock (`ChatBedrockConverse`), is stable across Claude / Qwen / Cohere model families, and is the natural representative shape for the inference call the count is approximating. No model-id branching — single shape works for every Bedrock model we use.
- **D-06 (Test asserts exact payload shape):** Unit test in `packages/vault-io/tests/test_update_tokens.py` mocks `boto3.client` (or patches `bedrock-runtime.count_tokens` via `botocore.stub.Stubber` / `unittest.mock`). Asserts `client.count_tokens.assert_called_once_with(modelId=..., input={'converse': {'messages': [...]}})` — locks the exact request shape so a future regression to `content=...` fails the test. Also asserts the function returns `response['inputTokenCount']` correctly (one test, both assertions).
- **D-07 (Gated integration test):** A `CODE_WIKI_RUN_INTEGRATION=1`-gated integration test exercises a real `count_tokens` call against Bedrock (region `us-east-1`, model `us.anthropic.claude-haiku-4-5-20251001-v1:0` — current default). Lives in `packages/vault-io/tests/` (a `tests/integration/` subdir if one isn't there yet). Follows the Phase 16 D-10 skip-decorator pattern from `docs/testing.md`. Smoke-asserts the call doesn't raise and returns a positive int.
- **D-08 (TOK-03 is the final plan step — live re-stamp):** After the code+tests step lands and is verified locally, the last commit in `17-01-PLAN.md` runs `uv run python -m vault_io.update_tokens` against `~/Personal/wiki/deep-agents` and commits the resulting page updates *in the wiki repo* (not in deep-agents). The diff transcript (counts before / after, sample of pages) is captured into `17-VERIFICATION.md`. Mirrors Phase 15 D-08/D-09 live-vault pattern. If the re-stamp fails for operational reasons (AWS creds, network), the phase doesn't close — VERIFICATION.md must show the re-stamp succeeded.

### WSRES — Workspace / repo resolution (WSRES-01/02/03)

- **D-09 (Use `resolve_wiki_and_repo()` second return value):** `init_vault.py:305` and `detect_containers.py:174` both change from `wiki, _ = resolve_wiki_and_repo(); repo = wiki.parent` to `_, repo = resolve_wiki_and_repo()`. `_workspace.resolve_wiki_and_repo()` already returns the workspace-aware repo root from `workspace_io`, so this works for both v1 (wiki at repo root) and v2 (wiki at `<workspace>/wiki/`) layouts. Two-line edit; surface unchanged.
- **D-10 (Optional `workspace_path` arg on `detect()`):** `detect_containers.detect()` signature becomes `def detect(repo_root, workspace_path=None) -> list[dict]`. When `workspace_path` is given, resolve it and (only if it differs from `repo_root`, see D-11) skip the matching immediate subdir during iteration so it can't classify itself as a `docs` container. Library callers (init_vault) and the CLI (`main()`) both pass `wiki.parent` after the WSRES-01 fix. Pure function stays pure — no internal call to `resolve_wiki_and_repo()` inside detect().
- **D-11 (Guard: skip exclusion when workspace_path == repo_root):** If `workspace_path.resolve() == repo_root.resolve()`, the workspace IS the repo (v1 layout, wiki at repo root). In that case the exclusion would skip the entire repo — guard it: only exclude when the workspace is a proper subdir of repo_root. Captured as part of D-10's implementation, not a separate decision; surfaces as test coverage requirement (one test for v1 layout, one for v2).
- **D-12 (Test fixture — synthetic tmp_path monorepo):** Build the fixture in pytest `tmp_path`:
  - `tmp_path/repo/graph-wiki/wiki/` (workspace dir with a wiki child)
  - `tmp_path/repo/packages/pkg-a/pyproject.toml`
  - `tmp_path/repo/packages/pkg-b/pyproject.toml`
  - Set `GRAPH_WIKI_WORKSPACE` env to `tmp_path/repo/graph-wiki` for the duration of the test (or use `monkeypatch.setenv`).
  - Call `detect(tmp_path/'repo', workspace_path=tmp_path/'repo'/'graph-wiki')`.
  - Assert: (1) `packages` appears in results with classification `package`, (2) no record has `source == 'graph-wiki'`.
  - Second test for v1 layout: wiki at `tmp_path/repo/wiki/`, `workspace_path == repo_root`; assert exclusion guard kicks in (no spurious empty-string skip; behavior identical to today).

### Plan structure (D-13)

- **D-13 (One bundled atomic plan, ~5 per-step commits):** All Phase 17 work lands in `17-01-PLAN.md`. Per-step commits inside the plan:
  1. SCAN-01 + SCAN-02 — `_load_existing_pages` companion filter + `workflow_hints` source + fixture-vault unit test.
  2. TOK-01 + TOK-02 — `count_tokens()` converse-shape fix + payload-shape unit test + gated integration test.
  3. WSRES-01 + WSRES-02 — `_, repo = resolve_wiki_and_repo()` in both files + optional `workspace_path` arg on `detect()` + v1-layout guard.
  4. WSRES-03 — synthetic tmp_path fixture + v1/v2 test pair.
  5. TOK-03 closure — re-run `update_tokens.py` against `~/Personal/wiki/deep-agents`, commit wiki-side updates, paste diff transcript into `17-VERIFICATION.md`.
  6. `17-VERIFICATION.md` — per-SC evidence sections citing pytest outputs and the live transcript.

  Matches Phase 16 D-14 + Phase 14 D-01 + Phase 15 D-10 pattern: mechanical/maintenance-grade items in one bundle so the SC mapping stays one-to-one with requirements. Three independent bugs in the same package, sharing fixture territory and Bedrock-region/credential setup — splitting buys nothing.

### Claude's Discretion

- Exact home for the companion-set constant (module-level in `scan_monorepo.py` vs. inside `_load_existing_pages` as a local) — executor's call; preference is module-level so the layout-block parsing helper can be unit-tested in isolation.
- Exact form of the layout-block lookup (extend `layout_io.read_layout()` return shape vs. add a thin `workflow_hints` accessor) — executor reads `layout_io.py` during scout and picks the lower-diff option.
- Whether the SCAN unit test fixture is constructed in `tests/conftest.py` (shared) or inline in the test file — executor's call; if `conftest.py` already has a monorepo fixture for other tests, extending it is the lower-friction path.
- Exact wording / decorator import path for the `CODE_WIKI_RUN_INTEGRATION` skip — follow `docs/testing.md` canonical pattern verbatim.
- Whether the TOK gated integration test imports the shared skip helper or inlines the decorator — match what other vault-io integration tests do; consistency over novelty.
- Whether D-11's exclusion guard uses `Path.resolve()` equality or `samefile()` — executor's call; `samefile()` is more correct on symlinks but `resolve()` is sufficient if symlinks aren't a concern here.
- Whether the WSRES tests sit in a new `tests/test_detect_containers.py` or extend an existing test module — executor's call after scout.

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Phase scope & requirement traceability
- `.planning/ROADMAP.md` §Phase 17 — Goal, depends-on (Phase 16), 5 success criteria, 8-requirement mapping (SCAN-01, SCAN-02, TOK-01, TOK-02, TOK-03, WSRES-01, WSRES-02, WSRES-03).
- `.planning/REQUIREMENTS.md` lines 14–35 — Full requirement text for SCAN / TOK / WSRES clusters, source-todo links, and the "Out of Scope" table.
- `.planning/PROJECT.md` — Core Value (Bedrock-only `code-wiki-agent`) and the constraint that `vault-io` write path always goes through `layout_io.py`.

### Source todos (operator-discovered bug context)
- `.planning/todos/pending/2026-05-19-fix-bedrock-count-tokens-api-shape-in-update-tokens.md` — TOK origin; documents the exact `Parameter validation failed: Missing required parameter "input"; Unknown parameter "content"` boto3 error and the `update_tokens.py:38-44` location.
- `.planning/todos/pending/2026-05-19-fix-workspace-repo-resolution-in-init-vault-and-detect-conta.md` — WSRES origin; documents the `init_vault.py:305-306` + `detect_containers.py:174-175` `wiki.parent` bug and the secondary self-classification bug.

### SCAN target code & tests
- `packages/vault-io/src/vault_io/scan_monorepo.py:602-672` — `_load_existing_pages` + `_collect()`; SCAN-01 edit site.
- `packages/vault-io/src/vault_io/scan_monorepo.py:1117` — Call site (`existing = _load_existing_pages(wiki) if wiki.exists() else {}`).
- `packages/vault-io/src/vault_io/scan_monorepo.py:675-688` — `compute_diff()`; reads `existing` keys to compute `deleted` set. SCAN-02 test asserts against its output.
- `packages/vault-io/src/vault_io/layout_io.py` — `read_layout()` reader; D-02 sources `workflow_hints` from here.
- `packages/vault-io/tests/conftest.py` — Existing fixture infrastructure; extension site for the SCAN fixture vault.

### TOK target code & tests
- `packages/vault-io/src/vault_io/update_tokens.py:38-44` — `count_tokens()`; TOK-01 edit site.
- `packages/vault-io/src/vault_io/update_tokens.py` — Surrounding module (page iteration, frontmatter rewrite via `layout_io` — DO NOT bypass; CLAUDE.md constraint).
- `packages/vault-io/src/vault_io/_workspace.py` — `resolve_wiki_and_repo()` source of truth for both TOK (via `update_tokens.py` CLI) and WSRES.
- `docs/testing.md` — Canonical `CODE_WIKI_RUN_INTEGRATION` opt-in gate rule (Phase 16 D-10). Skip-decorator pattern verbatim.
- `agents/code-wiki-agent/tests/conftest.py:17-21` — Same canonical skip-decorator shape; cross-reference for consistency.
- `packages/vault-io/src/vault_io/update_tokens.py:34-35` — `DEFAULT_MODEL_ID = "us.anthropic.claude-haiku-4-5-20251001-v1:0"`, `DEFAULT_REGION = "us-east-1"`; used by the gated integration test as-is.
- AWS docs: https://docs.aws.amazon.com/bedrock/latest/userguide/count-tokens.html — Authoritative API reference.

### WSRES target code & tests
- `packages/vault-io/src/vault_io/init_vault.py:305-306` — WSRES-01 edit site.
- `packages/vault-io/src/vault_io/detect_containers.py:148-166` — `detect()` signature change site (D-10).
- `packages/vault-io/src/vault_io/detect_containers.py:174-175` — WSRES-01 edit site + `main()` call-site update to pass `workspace_path`.
- `packages/vault-io/src/vault_io/detect_containers.py:33-47` — `SKIP_DIRS` constant; reference for where the exclusion logic conceptually belongs (alongside the dotfile/build-artifact filter).
- `packages/workspace-io/src/workspace_io/config.py` — `_find_repo_root()`; understanding what `resolve_wiki_and_repo()` returns as `repo_root` in v1 vs v2 layouts.
- `packages/vault-io/tests/` — WSRES-03 fixture lives here (file location TBD by executor).

### Prior phase patterns
- `.planning/milestones/v1.2-phases/16-carry-forward-debt-cleanup/16-CONTEXT.md` §"Plan structure" / D-14 — Bundled-plan-with-per-step-commits pattern; D-13 inherits.
- `.planning/milestones/v1.2-phases/15-wiki-self-update/` — D-08/D-09 live-vault transcript-in-VERIFICATION.md pattern; D-08 (TOK-03) inherits.
- `.planning/milestones/v1.2-phases/14-plugin-port-m3b/` — D-01 bundled-plan rationale (one cohesive change, atomic verification).

### Memory / project-level constraints
- `[[user_cost_optimization]]` — Cost-driven model selection; informs the choice to keep `count_tokens()` on Haiku 4.5 (cheapest representative tokenizer for Claude-family text) without re-litigating the model.
- `[[project_wiki_setup]]` — Wiki lives at `~/Personal/wiki/deep-agents`; TOK-03 live re-stamp targets this directory.
- `[[project_plugin_port_model]]` — Plugin runs on Claude Code; `code-wiki-agent` is the Bedrock path. Phase 17 touches the Bedrock path (`vault-io` + scripts) only — no plugin work.

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- **`layout_io.read_layout()`** (`packages/vault-io/src/vault_io/layout_io.py`) — Already the canonical reader for `wiki/CLAUDE.md` layout blocks; D-02 sources the companion filename set through it instead of adding a new parser. CLAUDE.md constraint: never bypass `layout_io` with `yaml.dump` or direct YAML — preserved.
- **`scan_monorepo._parse_frontmatter()`** + `_safe_read_text()` — Existing helpers in `scan_monorepo.py`; the companion filter slots into `_collect()` between `rglob("*.md")` and `pages[name] = ...` without touching either helper.
- **`detect_containers._immediate_subdirs()`** (`detect_containers.py:56`) — Single iteration site for the workspace exclusion; D-10 adds the filter here or in `detect()`'s caller of it.
- **`detect_containers.SKIP_DIRS`** (`detect_containers.py:33`) — Existing skip-set pattern; the workspace exclusion is conceptually adjacent (also "skip this immediate subdir") but is dynamic per-call rather than a constant, so it's a parameter, not a SKIP_DIRS extension.
- **`_workspace.resolve_wiki_and_repo()`** (already returns `(wiki, repo)`) — WSRES-01 leverages the existing second return value; no signature change.
- **Canonical `CODE_WIKI_RUN_INTEGRATION` skip-decorator** (`docs/testing.md`, `agents/code-wiki-agent/tests/conftest.py:17-21`) — D-07 reuses it verbatim; no new gate rule.

### Established Patterns
- **All vault writes route through `layout_io.py`** (project CLAUDE.md, STATE.md "Critical context") — D-02's layout-block read is read-only and uses `read_layout()`, so this constraint is preserved.
- **MCP stdout discipline (`_StdoutGuard`)** (project CLAUDE.md / STATE.md) — Phase 17 touches no MCP tool entry; the SCAN/TOK/WSRES fixes live in scripts and library code with print() to stderr only. No new MCP boundary surface.
- **boto3 client construction in `count_tokens()`** — Today's pattern is `boto3.client("bedrock-runtime", region_name=region)` per-call. D-05 preserves this (no caching, no aioboto3) — out of Phase 17 scope.
- **Phase 16 trace-helper / docs/testing.md gate** — Recent Phase 16 work formalized the integration-test pattern that D-07 inherits.
- **Per-step commits inside a bundled atomic plan** (Phase 14 Plan 3, Phase 15 D-10, Phase 16 D-14) — D-13's 6-step commit sequence mirrors directly.
- **Live-vault verification transcript in `${padded_phase}-VERIFICATION.md`** (Phase 14 SC#4, Phase 15 D-08/D-09) — D-08 (TOK-03) inherits.

### Integration Points
- **No MCP boundary change** — Phase 17 mutates `vault-io` internals + tests + scripts. The MCP tool surface (`wiki_bootstrap/scan/ingest/query/lint/log`) signatures stay identical.
- **No plugin touch** — `plugins/graph-wiki/` is Phase 18 territory (and runs on Claude Code per `[[project_plugin_port_model]]`).
- **Wiki schema unchanged** — `wiki/CLAUDE.md` `workflow_hints` block is *read*, not modified. The 35-page re-stamp (D-08) commits to the *wiki* repo, not the deep-agents code repo.
- **`models-qwen.toml` / `models-claude.toml` unchanged** — `count_tokens()` continues to use the bundled `DEFAULT_MODEL_ID = "us.anthropic.claude-haiku-4-5-20251001-v1:0"`; no profile override touched.
- **Integration tests run only with `CODE_WIKI_RUN_INTEGRATION=1`** — Per `docs/testing.md`; CI doesn't hit Bedrock by default; unit tests carry the regression weight.

</code_context>

<specifics>
## Specific Ideas

- **The companion bug is bounded and the diff is small** — `_collect()` is the single iteration site that produces the 28 false-positives; one filter there clears the requirement. The user explicitly chose "Filter inside `_collect()`" over a post-process pass or a wider refactor — keep the diff minimal and auditable.
- **`workflow_hints` is the authoritative source for companion names** — Even though the four names (`api`, `context`, `patterns`, `work`) are stable in upstream graph-wiki, we don't hardcode them in `scan_monorepo.py`. If the vault owner's schema doesn't declare them, we don't fold them — empty-set fallback is intentional (D-03), not a bug.
- **App pages are single-file by user convention** — Companion folding does NOT apply to `wiki/apps/`. Only `wiki/packages/` and `wiki/domains/<d>/packages/` (and layout-pinned `package` containers) get the filter (D-04). Pin this in the test fixture: if an app appears in the fixture vault, it's intentionally NOT folded.
- **Converse shape is the right TOK choice for the long run** — `ChatBedrockConverse` is the codebase's chosen Bedrock entry; using `{'converse': {'messages': [...]}}` in `count_tokens()` keeps the tokenizer's input shape representative of the real inference call. Model-family branching (Anthropic vs Qwen) is rejected as YAGNI — Converse handles both.
- **Exact-payload assertion is the regression lock** — D-06 explicitly asserts the full `input={'converse': {'messages': [...]}}` shape, not just "count_tokens was called." This is the test that catches a future revert to `content=...` — its job is to fail loudly if anyone re-introduces the original bug.
- **The `workspace_path` arg on `detect()` is the cleanest spot** — User chose "Optional arg to detect()" over caller-side filter or auto-detect-inside. Pure function stays pure; CLI + library both get the same exclusion semantics. The v1-layout guard (D-11) is the one non-trivial bit — it's why a second test is needed.
- **TOK-03 closes inside the plan, not as a follow-up todo** — User chose "Final step in the plan." If the live re-stamp fails (creds, network, etc.) the phase doesn't close — VERIFICATION.md must show the transcript. Mirrors Phase 15's live-vault pattern.
- **Phase 17 is mechanical maintenance — one bundled plan is right** — User chose "One bundled atomic plan" over three-by-cluster split. SC mapping stays 1:1 with requirements; the six per-step commits give natural rollback granularity if any single fix needs to revert.

</specifics>

<deferred>
## Deferred Ideas

- **Hardcoded companion-name fallback** — Considered as D-03 option B (use `{api, context, patterns, work}` if `workflow_hints` is missing). Rejected to keep the schema authoritative. Could land if a future vault is observed where companions exist on disk without a `workflow_hints` declaration, and the silent-deletion-flag becomes a real problem.
- **Refactor `_load_existing_pages` to per-directory iteration** — Considered as D-01 option C ("Refactor to per-dir slug"). Rejected as too invasive for a bug fix; the file walk model works once the filter is in. Could revisit if a future requirement (e.g., per-package metadata aggregation) makes the per-dir model genuinely necessary.
- **Layout-with-baked-in-fallback for companion names** — Considered as D-02 option C ("both"). Rejected for being more code than the 4-name set warrants.
- **Branching `count_tokens()` shape on `model_id`** — Considered as D-05 option C. Rejected as YAGNI — single Converse shape handles every Bedrock model the project currently uses.
- **Smoke-only unit test for TOK** — Considered as D-06 option C (mock returns 42, assert returns 42). Rejected because it doesn't lock the API shape and would let a regression to `content=...` pass silently.
- **Auto-detect workspace inside `detect()` via `resolve_wiki_and_repo()`** — Considered as D-10 option C. Rejected for coupling a pure classifier to env resolution; hurts testability.
- **Caller-side filter for workspace exclusion** — Considered as D-10 option B. Rejected because two filter sites (CLI + init_vault) means two places to forget; less defensible against future library callers of `detect()`.
- **Three-plan split (one per bug cluster)** — Considered as D-13 option B. Rejected — bugs are independent but small; bundled plan matches Phase 16 D-14 pattern.
- **Two-plan split (code vs. closure)** — Considered as D-13 option C. Rejected — the TOK-03 re-stamp is naturally the final step inside the bundled plan, not a separate plan.
- **TOK-03 as a follow-up todo** — Considered as D-08 option C. Rejected — too easy to slip; close in-plan with a transcript.
- **Integration test against the real `deep-agents` repo for WSRES** — Considered as D-12 option C. Rejected — couples test to live-repo layout drift; synthetic tmp_path is reproducible and isolated.

</deferred>

---

*Phase: 17-vault-io-bug-fixes*
*Context gathered: 2026-05-19*
