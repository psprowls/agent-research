# Phase 17: vault-io Bug Fixes — Research

**Researched:** 2026-05-19
**Domain:** vault-io package bug fixes — scan diff, Bedrock CountTokens API, workspace/repo resolution
**Confidence:** HIGH

## Summary

Three independent bugs in `packages/vault-io/` need surgical fixes. All three have clear repro paths, well-bounded edit sites already identified in CONTEXT.md, and concrete remediation patterns. Research confirms the planned fix shapes with two non-trivial nuances the planner MUST handle:

1. **CONTEXT.md D-02 is mis-specified about the source of the companion list.** The `workflow_hints` block referenced in CONTEXT.md does NOT live in `wiki/CLAUDE.md`'s layout block. It lives in **per-page YAML frontmatter** (e.g. `wiki/packages/<pkg>/<pkg>.md`). `layout_io.read_layout()` will return `None` for `workflow_hints` because the layout block schema only has `version/detected_at/repo_root/containers`. The planner must source companions from the parent overview page's frontmatter, not from a top-level layout block. (See `[VERIFIED: vault inspection]` below.)

2. **CONTEXT.md D-06 asserts the wrong response field name.** AWS docs for `bedrock-runtime.count_tokens` show the response field is `inputTokens` (singular path), not `inputTokenCount`. The current buggy code at `update_tokens.py:44` already returns `response["inputTokenCount"]` — a second bug compounding the request-shape bug. The fix must change BOTH the request (`content=` → `input=`) AND the response key (`inputTokenCount` → `inputTokens`). [CITED: docs.aws.amazon.com/bedrock/latest/APIReference/API_runtime_CountTokens.html]

**Primary recommendation:** Implement the three fixes per CONTEXT.md decisions D-01 through D-13, but route the SCAN companion source through per-page frontmatter (not the layout block) and the TOK response field through `inputTokens`. All other CONTEXT.md decisions stand verified.

## Architectural Responsibility Map

| Capability | Primary Tier | Secondary Tier | Rationale |
|------------|-------------|----------------|-----------|
| Wiki page enumeration (SCAN) | Library (vault-io scripts) | — | `scan_monorepo.py` is a CLI/module; no MCP boundary touched |
| Bedrock CountTokens call (TOK) | Library (vault-io scripts) | AWS Bedrock runtime API | `update_tokens.py` calls `boto3.client("bedrock-runtime")` directly |
| Repo/workspace resolution (WSRES) | Library (vault-io) → workspace-io | — | `_workspace.resolve_wiki_and_repo()` delegates to `workspace_io.config.resolve()`; v2 layout authority lives there |
| Container classification (WSRES) | Library (vault-io) | — | `detect_containers.detect()` is a pure path classifier; CLI in `main()` and library callers (`init_vault`) share it |
| Per-page frontmatter parsing | Library (vault-io scripts) | — | `scan_monorepo._parse_frontmatter()` already exists; companion source reuses it |

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions

**SCAN — Companion-page folding (SCAN-01/02)**
- **D-01** Filter inside `_collect()` in `scan_monorepo._load_existing_pages`. When walking `wiki/packages/<pkg>/*.md` (and `wiki/domains/<d>/packages/<pkg>/*.md`), skip files whose stem is in the companion set. Two-line edit; no post-process pass; no per-directory iteration rewrite.
- **D-02** Source the companion filename set from `wiki/CLAUDE.md`'s `workflow_hints` layout block via `layout_io.read_layout()`. (⚠️ See research finding below — workflow_hints actually lives in per-page frontmatter, not the layout block. Planner must reconcile.)
- **D-03** Empty-set fallback when hints absent. No silent baked-in `{api, context, patterns, work}` default. If a vault has companions on disk but no declaration, scan correctly reports them as deletions.
- **D-04** Fold scope = `wiki/packages/` + `wiki/domains/<d>/packages/`. Apply to layout-pinned `package` containers in CLAUDE.md. Do NOT apply to `wiki/apps/` — app pages are single-file by convention.

**TOK — Bedrock CountTokens API shape (TOK-01/02/03)**
- **D-05** `count_tokens()` uses `input={'converse': {'messages': [{'role': 'user', 'content': [{'text': text}]}]}}`. No model-id branching — single Converse shape for every Bedrock model.
- **D-06** Unit test in `packages/vault-io/tests/test_update_tokens.py` mocks `boto3.client`. Asserts `client.count_tokens.assert_called_once_with(modelId=..., input={'converse': {'messages': [...]}})` — locks the exact request shape. Also asserts the function returns `response['inputTokenCount']` correctly. (⚠️ See research finding — correct response field is `inputTokens` per AWS docs, not `inputTokenCount`.)
- **D-07** `CODE_WIKI_RUN_INTEGRATION=1`-gated integration test exercises a real `count_tokens` call against Bedrock (region `us-east-1`, model `us.anthropic.claude-haiku-4-5-20251001-v1:0`). Follows `docs/testing.md` skip-decorator pattern verbatim.
- **D-08** TOK-03 is the final plan step. After code+tests land, run `uv run python -m vault_io.update_tokens` against `~/Personal/wiki/deep-agents` and commit page updates in the WIKI repo (not deep-agents). Diff transcript captured into `17-VERIFICATION.md`.

**WSRES — Workspace / repo resolution (WSRES-01/02/03)**
- **D-09** `init_vault.py:305` and `detect_containers.py:174` both change from `wiki, _ = resolve_wiki_and_repo(); repo = wiki.parent` to `_, repo = resolve_wiki_and_repo()`. Two-line edit; works for v1 and v2 layouts because `_workspace.resolve_wiki_and_repo()` returns the workspace-aware repo root.
- **D-10** `detect_containers.detect()` signature becomes `def detect(repo_root, workspace_path=None) -> list[dict]`. When `workspace_path` given (and ≠ `repo_root`), skip the matching immediate subdir during iteration. Library callers and CLI both pass `wiki.parent` after the WSRES-01 fix.
- **D-11** Guard: if `workspace_path.resolve() == repo_root.resolve()`, the workspace IS the repo (v1 layout) — skip exclusion. Only exclude when workspace is a proper subdir.
- **D-12** Test fixture: build synthetic `tmp_path/repo/graph-wiki/wiki/` + `tmp_path/repo/packages/pkg-a/pyproject.toml` + `tmp_path/repo/packages/pkg-b/pyproject.toml`. Set `GRAPH_WIKI_WORKSPACE`. Call `detect(tmp_path/'repo', workspace_path=tmp_path/'repo'/'graph-wiki')`. Assert (1) `packages` found as `package` container, (2) no record with `source == 'graph-wiki'`. Second test for v1 layout asserts exclusion guard kicks in.

**Plan structure**
- **D-13** One bundled atomic plan: `17-01-PLAN.md`. Six per-step commits: SCAN fix → TOK fix → WSRES-01/02 → WSRES-03 tests → TOK-03 live re-stamp → `17-VERIFICATION.md`.

### Claude's Discretion

- Module-level vs local-level home for the companion-set constant in `scan_monorepo.py` — preference module-level for testability.
- Exact form of the layout-block lookup (extend `layout_io.read_layout()` return shape vs. thin `workflow_hints` accessor) — executor reads `layout_io.py` during scout. **⚠️ This decision is now moot given the research finding that workflow_hints lives in per-page frontmatter, not the layout block. Planner must define the actual reading mechanism.**
- SCAN unit test fixture in `tests/conftest.py` (shared) vs inline in test file.
- `CODE_WIKI_RUN_INTEGRATION` skip wording / decorator import path — follow `docs/testing.md` canonical pattern.
- TOK gated integration test: import shared skip helper vs inline decorator — match existing vault-io integration tests.
- D-11 exclusion guard: `Path.resolve()` equality vs `samefile()` — executor's call.
- WSRES tests: new `tests/test_detect_containers.py` vs extend existing module.

### Deferred Ideas (OUT OF SCOPE)

- Hardcoded `{api, context, patterns, work}` fallback for companions.
- Refactor `_load_existing_pages` to per-directory iteration.
- Layout-with-baked-in-fallback for companion names (i.e. both layout-declared AND hardcoded).
- Branching `count_tokens()` shape on `model_id` family.
- Smoke-only unit test for TOK (returns 42, asserts 42) — doesn't lock API shape.
- Auto-detect workspace inside `detect()` via `resolve_wiki_and_repo()` — couples pure classifier to env resolution.
- Caller-side filter for workspace exclusion.
- Three-plan split (one per bug cluster).
- Two-plan split (code vs. closure).
- TOK-03 as a follow-up todo (must close in-plan with transcript).
- Integration test against real `deep-agents` repo for WSRES — synthetic tmp_path is reproducible and isolated.
- New `vault-io` modules / MCP tools (v1.3 is bug-fix grade).
- Companion folding in `wiki/apps/` — single-file by convention.
- `init_vault` schema-writing logic changes.
- Changing `wiki/CLAUDE.md` `workflow_hints` block itself.
- Phases 18 and 19.
</user_constraints>

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| SCAN-01 | `_load_existing_pages` folds package companion files (`api.md`, `context.md`, `patterns.md`, `work.md`) inside `wiki/packages/<pkg>/` into the parent slug | Edit site located: `scan_monorepo.py:602-672` (`_load_existing_pages` + `_collect`). Companion-source mechanism: **per-page frontmatter `workflow_hints` block** on parent overview, parsed by existing `_parse_frontmatter()` helper. ⚠️ NOT the layout block as D-02 states. |
| SCAN-02 | Unit test asserts diff reports 0 `deleted` entries for companions | Test infrastructure: `packages/vault-io/tests/conftest.py` has `tmp_repo` / `vault_path` fixtures; `tests/fixtures/round-trip-vault/` exists as model. Companion fixture can extend either. |
| TOK-01 | `count_tokens()` uses correct `input=...` parameter shape | Verified shape via AWS docs: `input={"converse": {"messages": [{"role": "user", "content": [{"text": text}]}]}}`. Response field is `inputTokens` (NOT `inputTokenCount`). |
| TOK-02 | Unit test mocks boto3 client and asserts request payload; gated integration test exercises real Bedrock | Canonical gate decorator at `agents/code-wiki-agent/tests/conftest.py:17-21`. Existing pattern documented in `docs/testing.md`. |
| TOK-03 | Existing wiki pages with `tokens: 0` are re-stamped | Target wiki: `~/Personal/wiki/deep-agents`. 35 stubbed pages confirmed in todo. `update_tokens.py` already idempotent (strips existing `tokens:` field before counting). |
| WSRES-01 | `init_vault.py:305` and `detect_containers.py:174` use `_, repo = resolve_wiki_and_repo()` | Verified `_workspace.resolve_wiki_and_repo()` returns `(wiki, repo_root)` where `repo_root` comes from `workspace_io.config.resolve()` and is workspace-layout-aware. |
| WSRES-02 | `detect_containers.detect()` excludes resolved workspace path from classification | Edit site: `detect_containers.py:148-166`. Workspace exclusion adjacent to existing `SKIP_DIRS` constant pattern but dynamic-per-call → parameter, not constant. |
| WSRES-03 | Test against fixture repo with wiki at `<repo>/graph-wiki/wiki/` asserts repo-root containers are found | Synthetic tmp_path fixture per D-12. `_workspace.py` already honors `GRAPH_WIKI_WORKSPACE` env var → can use `monkeypatch.setenv`. |
</phase_requirements>

## Standard Stack

This phase is bug-fix grade — no new dependencies. Confirming the libraries in play:

### Core (already in vault-io)
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| `boto3` | ≥1.38 | Bedrock CountTokens API client | Project CLAUDE.md pins ≥1.38 for Converse API stability [VERIFIED: project CLAUDE.md] |
| `python-frontmatter` | 1.1.0 | Frontmatter read/write in `update_tokens.py` | Project standard; preserves YAML round-trip [VERIFIED: project CLAUDE.md] |
| `pytest` | ≥8.3 | Test runner | Project standard [VERIFIED: project CLAUDE.md] |
| `unittest.mock` | stdlib | Mock `boto3.client` in TOK unit test | Standard library; sufficient for D-06's mock-and-assert pattern [VERIFIED: stdlib] |

### Supporting
| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| `botocore.stub.Stubber` | (bundled with boto3) | Optional stubber for boto3 unit tests | If `unittest.mock.patch` proves awkward for the specific shape assertion; otherwise plain mock is fine |

**No new packages to install.** All libraries already in workspace `uv.lock`.

## Package Legitimacy Audit

> Not applicable — Phase 17 introduces no new external packages. All dependencies pre-exist in `uv.lock`. Skipping audit table.

## Architecture Patterns

### System Architecture Diagram

```
                            ┌─────────────────────────────┐
                            │  CLI / MCP entry points     │
                            │  (graph-wiki:scan / init /  │
                            │   update_tokens)            │
                            └──────────────┬──────────────┘
                                           │
                                           ▼
                          ┌────────────────────────────────┐
                          │  _workspace.resolve_wiki_      │
                          │  and_repo()                    │
                          │  → (wiki, repo_root)           │
                          │                                │
                          │  delegates to workspace_io     │
                          │  (honors v1 + v2 layouts)      │
                          └────────────┬───────────────────┘
                                       │
                ┌──────────────────────┼──────────────────────┐
                │                      │                      │
                ▼                      ▼                      ▼
   ┌─────────────────────┐  ┌──────────────────────┐  ┌──────────────────────┐
   │ scan_monorepo       │  │ update_tokens        │  │ detect_containers    │
   │                     │  │                      │  │                      │
   │ _load_existing_     │  │ iter_pages(wiki) →   │  │ detect(repo_root,    │
   │ pages(wiki)         │  │   for each page:     │  │        workspace_    │
   │  → _collect()       │  │     baseline =       │  │        path=None)    │
   │    rglob *.md       │  │       strip tokens   │  │  _immediate_subdirs  │
   │    [SCAN-01 filter] │  │     count_tokens     │  │  [WSRES-02 exclude   │
   │    fold companions  │  │     [TOK-01:         │  │   workspace_path]    │
   │    parse frontmatter│  │      input=converse] │  │  classify each dir   │
   │      → workflow_    │  │    write back via    │  │                      │
   │        hints        │  │    frontmatter       │  └──────────┬───────────┘
   └──────────┬──────────┘  └──────────┬───────────┘             │
              │                        │                         │
              ▼                        ▼                         ▼
   ┌─────────────────────┐  ┌──────────────────────┐  ┌──────────────────────┐
   │ compute_diff()      │  │ bedrock-runtime      │  │ list[dict] records   │
   │ → new/deleted/      │  │  .count_tokens(      │  │  source,             │
   │   renamed/unchanged │  │    modelId,          │  │  classification,     │
   │                     │  │    input={converse}) │  │  children_count,     │
   │                     │  │  → response          │  │  reason              │
   │                     │  │    ['inputTokens']   │  │                      │
   └─────────────────────┘  └──────────────────────┘  └──────────────────────┘
```

### Component Responsibilities

| File | Responsibility | Phase 17 Change |
|------|----------------|------------------|
| `packages/vault-io/src/vault_io/scan_monorepo.py:602-672` | Walk wiki, build `existing` page dict for diff comparison | Add companion filter inside `_collect()`; read parent's workflow_hints from frontmatter |
| `packages/vault-io/src/vault_io/update_tokens.py:38-44` | Bedrock CountTokens API call | Fix request shape AND response field |
| `packages/vault-io/src/vault_io/update_tokens.py:175` | CLI entry — resolve wiki | No change (works via wiki, not repo) |
| `packages/vault-io/src/vault_io/init_vault.py:305-306` | Bootstrap repo path resolution | Use second return value of `resolve_wiki_and_repo()` |
| `packages/vault-io/src/vault_io/detect_containers.py:148-166` | Classify top-level dirs | Add optional `workspace_path` param; exclude when set and ≠ repo_root |
| `packages/vault-io/src/vault_io/detect_containers.py:174-180` | CLI entry — resolve repo, run detect | Use second return value; pass `workspace_path=wiki.parent` to `detect()` |
| `packages/vault-io/src/vault_io/layout_io.py:51-59` | Read layout block from CLAUDE.md | NO CHANGE — workflow_hints is per-page, not layout-block |

### Pattern 1: Companion folding via per-page workflow_hints

**What:** Inside `_collect()`, after parsing each `.md`'s frontmatter, check whether the page is a "parent overview" (i.e. its stem matches its parent dir name, e.g. `packages/vault-io/vault-io.md`). If yes, read its `workflow_hints` block to discover which sibling stems are companions, and add them to a per-directory skip set used when iterating other files in the same dir.

**When to use:** Only inside `wiki/packages/` and `wiki/domains/<d>/packages/` (per D-04). Apps and other containers are NOT folded.

**Example — pseudocode:**
```python
# Source: derived from scan_monorepo.py:602-672 + lint/workflow_hints.py:13-43

def _collect(root, default_category, fold_companions=False):
    # First pass: discover companion sets keyed by parent directory.
    companions_by_dir: dict[Path, set[str]] = {}
    if fold_companions:
        for md in root.rglob("*.md"):
            parent_dir = md.parent
            if md.stem != parent_dir.name:
                continue  # not the parent overview
            text = _safe_read_text(md)
            hints = _parse_workflow_hints(text)  # reuse from lint module
            companion_stems = {Path(p).stem for sub in hints.values() for p in sub}
            if companion_stems:
                companions_by_dir[parent_dir] = companion_stems

    # Second pass: walk and skip companion files.
    for md in root.rglob("*.md"):
        skip_set = companions_by_dir.get(md.parent, set())
        if md.stem in skip_set:
            continue
        # ... existing parse + pages[name] = ... logic
```

### Pattern 2: Bedrock CountTokens converse shape

**Example — verified against AWS docs:**
```python
# Source: docs.aws.amazon.com/bedrock/latest/userguide/count-tokens.html
# [CITED: AWS Bedrock User Guide]

client = boto3.client("bedrock-runtime", region_name=region)
response = client.count_tokens(
    modelId=model_id,
    input={
        "converse": {
            "messages": [
                {
                    "role": "user",
                    "content": [{"text": text}],
                }
            ]
        }
    },
)
return response["inputTokens"]  # NOT inputTokenCount
```

### Pattern 3: detect_containers workspace exclusion

```python
# Source: derived from detect_containers.py:148-166

def detect(repo_root: Path, workspace_path: Path | None = None) -> list[dict]:
    repo_root = Path(repo_root).resolve()
    if not repo_root.exists():
        return []

    # Guard (D-11): only exclude when workspace is a proper subdir of repo_root
    exclude: Path | None = None
    if workspace_path is not None:
        wp = Path(workspace_path).resolve()
        if wp != repo_root and wp.parent == repo_root:
            exclude = wp

    top = [d for d in _immediate_subdirs(repo_root) if d.resolve() != exclude]
    records = [_classify_dir(d) for d in top]
    # ... rest unchanged
```

### Anti-Patterns to Avoid

- **Hardcoding `{api, context, patterns, work}` in `scan_monorepo.py`** — explicitly rejected (D-03). Schema is authoritative; empty fallback is correct.
- **Hand-rolling `yaml.dump` to update frontmatter** — project CLAUDE.md constraint. `update_tokens.py` already uses careful line-by-line manipulation (`frontmatter.loads` for read, manual line-split for write) to preserve YAML formatting. Do not touch this.
- **Calling `resolve_wiki_and_repo()` inside `detect()`** — explicitly rejected (deferred option). `detect()` is a pure classifier; env resolution belongs to callers.
- **Using `inputTokenCount` as response key** — current bug. The correct AWS API field is `inputTokens`.
- **Adding a new MCP tool** — out of v1.3 scope (REQUIREMENTS.md "Out of Scope").

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Parsing workflow_hints block | New YAML parser | Reuse `vault_io.lint.workflow_hints._parse_workflow_hints()` | Already handles the multi-line block form without pyyaml |
| Mocking `boto3.client` | DIY HTTP-level mock | `unittest.mock.patch("boto3.client")` returning a MagicMock with `.count_tokens` attribute | Standard pattern; D-06 specifies exact-payload assertion via `assert_called_once_with` |
| Synthetic monorepo fixture | New pytest plugin | `tmp_path` + manual `mkdir`/`pyproject.toml` writes + `monkeypatch.setenv("GRAPH_WIKI_WORKSPACE", ...)` | `workspace_io.config.resolve()` honors `GRAPH_WIKI_WORKSPACE` (`_workspace.py:35-38`); no need to mock the resolver |
| Layout-block reader | New parser | `layout_io.read_layout()` | Already exists and parses the YAML inside the sentinel block (but NOTE: doesn't return workflow_hints because that's per-page, not in the block) |
| Frontmatter parser for SCAN | New impl | `scan_monorepo._parse_frontmatter()` (already used in `_collect`) | Already wired into the call site |

**Key insight:** Every bug fix has an existing helper that does 80% of the work. The companion filter is two new lines + reuse of the lint module's `_parse_workflow_hints`. The TOK fix is a four-line edit. The WSRES-01 fix is literally `wiki, _` → `_, repo` plus deleting `repo = wiki.parent`. The WSRES-02 fix is a 3-line addition + a guard.

## Runtime State Inventory

> Phase 17 is bug-fix code-and-test work. TOK-03 has an operational closure that involves stored data (wiki page frontmatter).

| Category | Items Found | Action Required |
|----------|-------------|------------------|
| Stored data | 35 wiki pages in `~/Personal/wiki/deep-agents/**/*.md` currently have `tokens: 0` due to the API bug | Data migration (TOK-03 plan step): `uv run python -m vault_io.update_tokens` against `~/Personal/wiki/deep-agents`. `update_tokens.py` is idempotent (strips existing tokens line before re-counting) so re-running is safe. |
| Live service config | None — no n8n / Datadog / Tailscale / Cloudflare config touches the wiki. | None |
| OS-registered state | None — vault-io scripts are invoked on-demand; no Task Scheduler / launchd / pm2 / systemd registrations exist for them. | None |
| Secrets/env vars | `AWS_ACCESS_KEY_ID` / `AWS_SECRET_ACCESS_KEY` (or IAM role) required for TOK-03 live re-stamp. `GRAPH_WIKI_WORKSPACE` used by tests (monkeypatched). | None — env vars referenced by name unchanged |
| Build artifacts | `packages/vault-io/src/vault_io/__pycache__/` will be invalidated automatically on source edit; no `.egg-info`/`dist`/compiled artifacts in vault-io. `uv sync` not needed for code changes (editable install). | None |

**Nothing found in category:** Live service config, OS-registered state, build artifacts — verified by `ls` and code scan.

## Common Pitfalls

### Pitfall 1: Sourcing workflow_hints from the wrong place

**What goes wrong:** Executor reads CONTEXT.md D-02 literally — calls `layout_io.read_layout(wiki / 'CLAUDE.md')` and looks for `workflow_hints` in the returned dict. Result: `KeyError` or `None`, falls through to empty-set fallback (D-03), and the SCAN-02 unit test passes only because the test fixture also lacks workflow_hints. On the real deep-agents wiki the 28 false-deletes return — silently.

**Why it happens:** CONTEXT.md misidentifies the source. `wiki/CLAUDE.md` layout block schema (verified on `~/Personal/wiki/deep-agents/CLAUDE.md`) is `version / detected_at / repo_root / containers`. `workflow_hints` is **per-page frontmatter** on parent overview pages (e.g. `packages/vault-io/vault-io.md`), declared by the package template (`.templates/package/overview.md`).

**How to avoid:** Read the parent page's frontmatter inside `_collect()`. The lint module already has the parser (`vault_io.lint.workflow_hints._parse_workflow_hints`) — reuse it. The fixture for SCAN-02 must include companions referenced via per-page `workflow_hints` to exercise the real code path.

**Warning signs:** SCAN-02 test passes but `/graph-wiki:scan` on the real vault still reports phantom deletes. Always smoke-test against `~/Personal/wiki/deep-agents` before declaring SC#1 met.

### Pitfall 2: Asserting the wrong response field name in TOK unit test

**What goes wrong:** Per CONTEXT.md D-06, executor asserts `assert count_tokens(...) == response['inputTokenCount']`. Test passes with a mock that returns whatever shape the executor invents. Real Bedrock call fails with `KeyError: 'inputTokenCount'` because the actual field is `inputTokens`.

**Why it happens:** The current buggy code at `update_tokens.py:44` reads `response["inputTokenCount"]` — a pre-existing bug compounding the request-shape bug. CONTEXT.md D-06 inherits this incorrect field name.

**How to avoid:** Verify against AWS docs (see Sources). Mock should return `{"inputTokens": 42}`; function should return that value; test asserts the function returns 42 AND that the mock was called with the converse-shape `input=`.

**Warning signs:** Gated integration test (D-07) raises `KeyError`. If the integration test is skipped in CI, the bug will reach TOK-03 (live re-stamp), where it manifests as "all 35 pages still have `tokens: 0`."

### Pitfall 3: WSRES exclusion guard too eager

**What goes wrong:** Executor implements `if workspace_path: exclude = workspace_path` without the D-11 guard. In v1 layout (wiki at `<repo>/wiki/`), `wiki.parent == repo` — the workspace IS the repo. Excluding it means `detect()` returns `[]`.

**Why it happens:** Easy to miss in a quick edit; v1 vs v2 distinction requires careful thought about path equality semantics.

**How to avoid:** Implement D-11 guard explicitly: only exclude when `workspace_path.resolve() != repo_root.resolve()` AND `workspace_path.parent.resolve() == repo_root.resolve()` (proper immediate subdir). D-12 mandates a v1-layout test that exercises this guard.

**Warning signs:** `detect_containers --json` returns `[]` on a v1 vault (e.g. the lattice-wiki fixture repos). WSRES-03's v1 test is the regression lock.

### Pitfall 4: Skipping `wiki/CLAUDE.md`'s pinned package containers

**What goes wrong:** Companion filter applied only to literal `wiki/packages/` path, not to layout-pinned `package` containers (per D-04, layout-pinned package containers also get the filter). Result: false-deletes return for any vault whose pinned containers don't match the default name.

**Why it happens:** `_load_existing_pages` already iterates layout-pinned containers (`scan_monorepo.py:643-655`) but as a separate loop. Easy to forget to thread the companion filter through both call sites.

**How to avoid:** Pass `fold_companions=True` to BOTH `_collect(vault / "packages", "package")` AND inside the layout loop where `classification == "package"`. Do NOT pass it to the `"app"` classification or to `wiki/apps/`.

### Pitfall 5: `workflow_hints` declared but referenced companion files missing on disk

**What goes wrong:** A package overview declares `workflow_hints: { brainstorming: [context.md] }` but `context.md` does not exist on disk yet (template-emitted but never created). Companion filter correctly skips it (nothing to skip), but lint module's `workflow_hints.check()` reports it as a missing sub-page. This is correct behavior — but if the planner conflates "fold companions" with "ensure companions exist", they may over-correct.

**Why it happens:** The companion filter is about diff arithmetic, not lint. They're independent.

**How to avoid:** SCAN-02 test asserts the diff has 0 phantom deletes. It does NOT assert lint reports zero workflow_hints issues — that's a separate check (the lint module's existing test territory).

## Code Examples

Verified patterns from official sources / existing codebase:

### CountTokens with Converse shape (correct)
```python
# Source: docs.aws.amazon.com/bedrock/latest/userguide/count-tokens.html
# [CITED: AWS Bedrock User Guide; verified 2026-05-19]

import boto3

bedrock_runtime = boto3.client("bedrock-runtime", region_name="us-east-1")

input_to_count = {
    "messages": [
        {
            "role": "user",
            "content": [{"text": "What is the capital of France?"}],
        },
    ],
}

response = bedrock_runtime.count_tokens(
    modelId="us.anthropic.claude-haiku-4-5-20251001-v1:0",
    input={"converse": input_to_count},
)

token_count = response["inputTokens"]  # NOT "inputTokenCount"
```

### Reusing `_parse_workflow_hints` from lint module
```python
# Source: packages/vault-io/src/vault_io/lint/workflow_hints.py:13-43
# Already handles the multi-line block form without pyyaml.

from vault_io.lint.workflow_hints import _parse_workflow_hints

text = md_path.read_text(encoding="utf-8")
hints = _parse_workflow_hints(text)
# hints == {"brainstorming": ["context.md"], "planning": ["api.md", "patterns.md"], ...}

companion_stems = {Path(p).stem for sub in hints.values() for p in sub}
# companion_stems == {"context", "api", "patterns", "work"}
```

### Canonical INTEGRATION_GATE decorator
```python
# Source: docs/testing.md §3; agents/code-wiki-agent/tests/conftest.py:17-21
# [VERIFIED: docs/testing.md]

import os
import pytest

INTEGRATION_GATE = pytest.mark.skipif(
    not os.environ.get("CODE_WIKI_RUN_INTEGRATION"),
    reason="Set CODE_WIKI_RUN_INTEGRATION=1 to run real Bedrock invocations",
)

@INTEGRATION_GATE
def test_count_tokens_real_bedrock():
    from vault_io.update_tokens import count_tokens
    n = count_tokens("hello world")
    assert isinstance(n, int) and n > 0
```

### Synthetic monorepo fixture for WSRES tests
```python
# Source: derived from packages/vault-io/tests/conftest.py:11-15
# + _workspace.py:35-38 (GRAPH_WIKI_WORKSPACE env var honored)

import pytest
from pathlib import Path

@pytest.fixture
def v2_workspace(tmp_path: Path, monkeypatch):
    """Build a v2-layout fixture: repo with graph-wiki/ workspace child."""
    repo = tmp_path / "repo"
    (repo / "graph-wiki" / "wiki").mkdir(parents=True)
    (repo / "graph-wiki" / ".graph-wiki.yaml").write_text("plugins: []\n")
    (repo / "packages" / "pkg-a").mkdir(parents=True)
    (repo / "packages" / "pkg-a" / "pyproject.toml").write_text('[project]\nname="a"\n')
    (repo / "packages" / "pkg-b").mkdir(parents=True)
    (repo / "packages" / "pkg-b" / "pyproject.toml").write_text('[project]\nname="b"\n')
    (repo / ".git").mkdir()  # so _find_repo_root locates repo
    monkeypatch.setenv("GRAPH_WIKI_WORKSPACE", str(repo / "graph-wiki"))
    return {"repo": repo, "workspace": repo / "graph-wiki"}
```

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| `client.count_tokens(content=[{"text": text}])` | `client.count_tokens(input={"converse": {"messages": [...]}})` | Bedrock API contract — `input` is current required parameter, `content` was either never valid or removed | Pre-existing project bug; current code never worked since CountTokens was added |
| `response["inputTokenCount"]` | `response["inputTokens"]` | AWS docs canonical field is `inputTokens` | Same response misuse compounds the request bug |
| `wiki, _ = resolve_wiki_and_repo(); repo = wiki.parent` (v1 assumption) | `_, repo = resolve_wiki_and_repo()` (workspace-aware) | v2 workspace layout introduced in v1.2 Phase 11 | v1 layout still works since `_workspace` resolver returns the same repo_root |
| Layout block as authoritative source for companions (CONTEXT.md D-02) | Per-page frontmatter `workflow_hints` (actual schema location) | Schema reality — never lived in the layout block | Affects D-02 implementation; planner must reconcile |

**Deprecated / outdated:**
- The `content=[{"text": text}]` request shape — never valid per current boto3 introspection.
- `wiki.parent` as repo-root computation — v1-only; broken under v2.

## Assumptions Log

| # | Claim | Section | Risk if Wrong |
|---|-------|---------|---------------|
| A1 | The existing `update_tokens.py` line-by-line frontmatter manipulation correctly preserves YAML formatting in edge cases (unicode, escaped chars, multi-line values) | Don't Hand-Roll | LOW — code is in production; if it breaks on TOK-03 re-stamp, planner must add regression test before deploying |
| A2 | All 7 packages in the deep-agents wiki use the template-emitted `workflow_hints` block with the same 4 companion names | Pitfall 1 / SCAN-01 | LOW — verified by spot-check; if a package omits the block, that package contributes 0 companion folds (correct fallback behavior) |
| A3 | `workspace_io.config.resolve()` correctly returns `repo_root == <repo>` (not `<repo>/graph-wiki`) when `GRAPH_WIKI_WORKSPACE` is set to a subdir of a git repo | Pattern 3 / D-09 | LOW — code at `config.py:60-66` walks up from workspace looking for `.git`; verified |
| A4 | `botocore` `count_tokens` operation is available in the boto3 version pinned by the workspace (≥1.38) | Standard Stack | LOW — pinned ≥1.38; CountTokens API supported since boto3 1.36+ |
| A5 | The "35 pages at tokens: 0" claim from the todo / SC#2 is still accurate at TOK-03 execution time | Runtime State Inventory | LOW — if pages have been touched in the interim, count may differ; TOK-03 re-stamp is idempotent so this only affects the transcript number |
| A6 | The lint module's `_parse_workflow_hints` function (private, underscore-prefixed) is safe to import from `scan_monorepo.py` | Code Examples | LOW — both modules are in the same package (`vault_io`); if the executor prefers, the parser can be promoted to `lint.workflow_hints.parse_workflow_hints` (public) in the same commit, or duplicated inline |

## Open Questions

1. **Should the companion-source mechanism be implemented as "read parent overview frontmatter inside `_collect`" or "extend `layout_io.read_layout` to expose per-page workflow_hints across the vault"?**
   - What we know: workflow_hints is per-page frontmatter, not layout-block. The lint module already parses it per-page.
   - What's unclear: CONTEXT.md D-02 explicitly says "via `layout_io.read_layout()`" — but `read_layout()` reads the layout block, which doesn't contain workflow_hints. The planner must decide whether to (a) read per-page frontmatter inside `_collect()` (simpler, matches schema reality) or (b) add a separate aggregator helper.
   - Recommendation: Implement option (a). It's the minimum-diff approach consistent with D-01 (filter inside `_collect()`). Flag the D-02 discrepancy in the plan's "Approach" section.

2. **For the SCAN-02 test fixture, build companions on disk + workflow_hints declarations, or just declarations?**
   - What we know: Bug is "files exist on disk; diff calls them deleted." Reproducing requires both companion files AND workflow_hints declarations.
   - What's unclear: Does the existing `round-trip-vault` fixture have either?
   - Recommendation: Extend the fixture or create a new minimal one with one `pkg-a/` directory containing `pkg-a.md` (with workflow_hints declaring `api.md`, `context.md`, `patterns.md`, `work.md`) plus the four companion files. Assert diff returns 0 deletes for this package.

3. **For the TOK-03 live re-stamp, who runs it and where do the wiki-side commits go?**
   - What we know: CONTEXT.md D-08 says commit "in the wiki repo" (i.e. inside `~/Personal/wiki/deep-agents`, which is its own git repo). Diff transcript in `17-VERIFICATION.md`.
   - What's unclear: Whether the wiki repo has uncommitted state at the time of execution, and whether the executor has push access.
   - Recommendation: Plan step pre-condition: `git status` in the wiki repo is clean. Post-condition: a commit in the wiki repo with the 35 token-stamped pages. If the wiki repo has unrelated dirty state, the plan stops and asks the user.

## Environment Availability

| Dependency | Required By | Available | Version | Fallback |
|------------|------------|-----------|---------|----------|
| `python3.11+` | Project floor | ✓ (uv-managed) | 3.11+ | — |
| `uv` workspace | All test/run commands | ✓ | 0.11.x | — |
| `boto3` | TOK code + TOK-02 unit test (mocked) | (via uv.lock) | ≥1.38 | — |
| `pytest` | All tests | (via uv.lock) | ≥8.3 | — |
| AWS Bedrock access (Haiku 4.5 in us-east-1) | TOK D-07 integration test + TOK-03 live re-stamp | unverified at research time — credentials gated to user environment | — | Integration test is skipped by default (no `CODE_WIKI_RUN_INTEGRATION`); TOK-03 blocks phase close if creds unavailable |
| `~/Personal/wiki/deep-agents` git repo | TOK-03 live re-stamp commit | unverified to be clean at execution time | — | Plan step asks user to confirm clean state |

**Missing dependencies with no fallback:**
- None at code-and-test stage.

**Missing dependencies with fallback:**
- Bedrock access for unit tests — fully mocked; not required for SCAN/TOK-01/TOK-02 unit tests or WSRES tests.

## Validation Architecture

### Test Framework
| Property | Value |
|----------|-------|
| Framework | pytest ≥8.3 + pytest-asyncio 1.3.0 + syrupy 5.1.0 (project standard) |
| Config file | `packages/vault-io/pyproject.toml` (workspace-managed) |
| Quick run command | `uv run --package vault-io pytest -x` |
| Full suite command | `uv run --package vault-io pytest` |
| Integration gate | `CODE_WIKI_RUN_INTEGRATION=1 uv run --package vault-io pytest -m integration` |

### Phase Requirements → Test Map

| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| SCAN-01 | `_load_existing_pages` skips companion files in `wiki/packages/<pkg>/` | unit | `uv run --package vault-io pytest tests/test_scan_companion_fold.py::test_load_existing_skips_companions -x` | ❌ Wave 0 |
| SCAN-01 | Layout-pinned `package` containers also get the filter | unit | `uv run --package vault-io pytest tests/test_scan_companion_fold.py::test_layout_pinned_package_skips_companions -x` | ❌ Wave 0 |
| SCAN-01 | `wiki/apps/` is NOT filtered | unit | `uv run --package vault-io pytest tests/test_scan_companion_fold.py::test_apps_not_filtered -x` | ❌ Wave 0 |
| SCAN-02 | `compute_diff` reports 0 `deleted` for companions on a healthy fixture | unit | `uv run --package vault-io pytest tests/test_scan_companion_fold.py::test_compute_diff_no_phantom_deletes -x` | ❌ Wave 0 |
| TOK-01 | `count_tokens` calls Bedrock with `input={"converse": ...}` | unit | `uv run --package vault-io pytest tests/test_update_tokens.py::test_count_tokens_request_shape -x` | ❌ Wave 0 (file may exist; method new) |
| TOK-01 | `count_tokens` returns `response["inputTokens"]` | unit | `uv run --package vault-io pytest tests/test_update_tokens.py::test_count_tokens_returns_input_tokens -x` | ❌ Wave 0 |
| TOK-02 | Real Bedrock call succeeds, returns positive int | integration (gated) | `CODE_WIKI_RUN_INTEGRATION=1 uv run --package vault-io pytest tests/integration/test_count_tokens_live.py -x` | ❌ Wave 0 |
| TOK-03 | All 35 stubbed pages in `~/Personal/wiki/deep-agents` have non-zero `tokens:` | manual + file-state | `uv run python -m vault_io.update_tokens` then `grep -rn "^tokens: 0" ~/Personal/wiki/deep-agents` returns nothing | manual; transcript in 17-VERIFICATION.md |
| WSRES-01 | `init_vault.py` resolves repo correctly under v2 layout | unit | `uv run --package vault-io pytest tests/test_detect_containers.py::test_v2_layout_finds_repo_containers -x` | ❌ Wave 0 |
| WSRES-02 | `detect()` excludes workspace_path subdir from classification | unit | `uv run --package vault-io pytest tests/test_detect_containers.py::test_workspace_path_excluded -x` | ❌ Wave 0 |
| WSRES-02 | v1 layout (workspace == repo) does NOT exclude (guard works) | unit | `uv run --package vault-io pytest tests/test_detect_containers.py::test_v1_layout_guard -x` | ❌ Wave 0 |
| WSRES-03 | Synthetic tmp_path fixture exercises end-to-end resolution | unit | `uv run --package vault-io pytest tests/test_detect_containers.py::test_v2_synthetic_repo -x` | ❌ Wave 0 |

### Sampling Rate
- **Per task commit:** `uv run --package vault-io pytest -x` (fast — all unit tests; mock-only)
- **Per wave merge:** `uv run --package vault-io pytest` (full suite without integration gate)
- **Phase gate (SC#5):** `uv run --package vault-io pytest` green; plus `CODE_WIKI_RUN_INTEGRATION=1 uv run --package vault-io pytest -m integration` green; plus TOK-03 live re-stamp transcript

### Wave 0 Gaps
- [ ] `tests/test_scan_companion_fold.py` — new file; covers SCAN-01, SCAN-02
- [ ] `tests/test_update_tokens.py` — new file (no existing test for `update_tokens.py`); covers TOK-01, TOK-02
- [ ] `tests/integration/test_count_tokens_live.py` — new file; gated integration; covers TOK-02 (live)
- [ ] `tests/test_detect_containers.py` — new file; covers WSRES-01, WSRES-02, WSRES-03
- [ ] Fixture extension in `tests/conftest.py` OR inline fixtures in test files for v2 synthetic monorepo and companion-vault patterns
- [ ] No framework install needed (pytest, pytest-asyncio, syrupy already in `uv.lock`)

## Security Domain

### Applicable ASVS Categories

| ASVS Category | Applies | Standard Control |
|---------------|---------|-----------------|
| V2 Authentication | yes | AWS IAM / `boto3` credential chain — unchanged (preserved as-is) |
| V3 Session Management | no | — |
| V4 Access Control | yes (transitively) | `bedrock:CountTokens` IAM permission required for TOK-03; same scope as existing `bedrock:InvokeModel` already granted |
| V5 Input Validation | yes | Wiki page frontmatter parsed by `_parse_frontmatter`; companion filter only filters on file stem (no user-controlled SQL/HTML/shell) |
| V6 Cryptography | no | No new crypto |
| V12 Files and Resources | yes | All path operations use `Path.resolve()` for normalization (D-11 guard); `_find_repo_root` walks parents within the OS filesystem |

### Known Threat Patterns for vault-io / Bedrock stack

| Pattern | STRIDE | Standard Mitigation |
|---------|--------|---------------------|
| Path traversal via attacker-controlled vault contents | Tampering | `_workspace.resolve_wiki_and_repo()` only accepts paths under the resolved repo_root; companion stems are filtered, not executed; D-11 path-equality guard prevents workspace == repo exclusion footgun |
| Hardcoded credentials in test code | Information disclosure | Integration test uses ambient `AWS_*` env vars or IAM role; no credentials in source. `CODE_WIKI_RUN_INTEGRATION` gate prevents CI from invoking real Bedrock by default |
| Prompt injection via wiki page content sent to CountTokens | Tampering / Repudiation | `count_tokens()` is a tokenizer call — the API does NOT execute model inference and does NOT respond with model output. Content cannot influence anything beyond the integer count. |
| Race condition during TOK-03 re-stamp | Tampering | `update_tokens.py` is idempotent (strips existing `tokens:` before re-counting); concurrent runs converge to the same value |

## Sources

### Primary (HIGH confidence)
- `packages/vault-io/src/vault_io/scan_monorepo.py:602-672` — `_load_existing_pages` + `_collect`; SCAN-01 edit site (read-verified 2026-05-19)
- `packages/vault-io/src/vault_io/scan_monorepo.py:675-688` — `compute_diff`; SCAN-02 assertion target (read-verified)
- `packages/vault-io/src/vault_io/update_tokens.py:38-44` — `count_tokens`; TOK-01 edit site (read-verified)
- `packages/vault-io/src/vault_io/detect_containers.py:148-166` — `detect()`; WSRES-02 edit site (read-verified)
- `packages/vault-io/src/vault_io/detect_containers.py:174-175` — CLI repo resolution; WSRES-01 edit site (read-verified)
- `packages/vault-io/src/vault_io/init_vault.py:305-306` — CLI repo resolution; WSRES-01 edit site (read-verified)
- `packages/vault-io/src/vault_io/_workspace.py:23-38` — `resolve_wiki_and_repo` contract (read-verified)
- `packages/vault-io/src/vault_io/layout_io.py:51-59` — `read_layout`; D-02 reference (read-verified — does NOT return workflow_hints)
- `packages/vault-io/src/vault_io/lint/workflow_hints.py:13-43` — `_parse_workflow_hints` reusable parser (read-verified)
- `packages/workspace-io/src/workspace_io/config.py` — `_find_repo_root` and `resolve()` (read-verified)
- `~/Personal/wiki/deep-agents/CLAUDE.md` — confirmed layout block does NOT contain workflow_hints (inspected 2026-05-19)
- `~/Personal/wiki/deep-agents/.templates/package/overview.md` — template emits per-page `workflow_hints` block (inspected 2026-05-19)
- `~/Personal/wiki/deep-agents/packages/vault-io/vault-io.md` — actual overview page with workflow_hints in frontmatter (inspected 2026-05-19)
- `docs/testing.md` §3 — canonical `INTEGRATION_GATE` decorator pattern
- AWS Bedrock User Guide — CountTokens API: https://docs.aws.amazon.com/bedrock/latest/userguide/count-tokens.html [CITED 2026-05-19]
- AWS Bedrock API Reference — CountTokens: https://docs.aws.amazon.com/bedrock/latest/APIReference/API_runtime_CountTokens.html [CITED 2026-05-19 — response field is `inputTokens`]

### Secondary (MEDIUM confidence)
- `.planning/todos/pending/2026-05-19-fix-bedrock-count-tokens-api-shape-in-update-tokens.md` — todo origin doc
- `.planning/todos/pending/2026-05-19-fix-workspace-repo-resolution-in-init-vault-and-detect-conta.md` — todo origin doc
- `graph-wiki/work/2026-05-19-scan-diff-treats-companion-pages-as-orphans.md` — SCAN bug origin (work item)

### Tertiary (LOW confidence)
- (none — every claim above is verified by direct file inspection or official AWS docs)

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH — no new packages; existing versions verified in workspace `uv.lock` and project CLAUDE.md
- Architecture: HIGH — every edit site located by file and line range; existing helpers identified
- Pitfalls: HIGH — Pitfall 1 (workflow_hints location) and Pitfall 2 (inputTokens vs inputTokenCount) are NEW findings discovered during research that the planner MUST handle; both verified against the codebase and AWS docs respectively

**Research date:** 2026-05-19
**Valid until:** 2026-06-18 (30 days — stable bug-fix territory, no fast-moving library churn expected)
