# Phase 11: workspace-io Port (M1) - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md — this log preserves the alternatives considered.

**Date:** 2026-05-17
**Phase:** 11-workspace-io-port-m1
**Areas discussed:** Resolution priority + env-var lifecycle, Module trim — port-as-is vs drop, Manifest field set, Manifest v1→v2 coercion + repo_root semantics

---

## Resolution priority + env-var lifecycle

### Q1 — What happens to the existing `CODE_WIKI_REAL_VAULT_PATH` env var once `workspace_io.config.resolve()` is the backend?

| Option | Description | Selected |
|--------|-------------|----------|
| Drop it — GRAPH_WIKI_WORKSPACE only | Clean break. Removed from code, tests, docstrings. Matches ROADMAP SC#2 literal wording. | ✓ |
| Alias with deprecation warning | Both env vars resolve; one-shot DeprecationWarning if old var set. | |
| Keep both, document precedence | Both env vars supported indefinitely with documented precedence order. | |

**User's choice:** Drop it — GRAPH_WIKI_WORKSPACE only.
**Notes:** Single-developer project, no external users to break. Test file `test_ports_importable.py` rewrites trivially.

### Q2 — Resolution priority order inside `vault-io._workspace.resolve_wiki_and_repo` after delegation?

| Option | Description | Selected |
|--------|-------------|----------|
| explicit arg → workspace_io.config.resolve() → raise | Two-tier; vault-io stays a thin shim; all discovery logic lives in workspace_io. | ✓ |
| explicit arg → GRAPH_WIKI_WORKSPACE env → workspace_io.config.resolve() → raise | Three-tier with env-var fast path in vault-io. | |
| Always call workspace_io.config.resolve(cwd, explicit=...) | Push explicit-path into workspace_io's API as an optional kwarg. | |

**User's choice:** explicit arg → workspace_io.config.resolve() → raise.
**Notes:** Single source of truth for discovery semantics. MCP boundary contract (explicit arg) preserved.

### Q3 — Where does `workspace_io.config.resolve()` look for the wiki path?

| Option | Description | Selected |
|--------|-------------|----------|
| Port verbatim, expect manifest at the wiki location | Run rebranded `init` once to drop manifest; cwd-walk finds it. | |
| Manifest-optional mode with `wiki/` or `wiki-config.toml` fallback | Falls back to looking for a `wiki/` subdir or `wiki-config.toml` if no manifest found. | |
| Strict — manifest required, no fallback, friendly error | If no `.graph-wiki.yaml` found and no env var, raise with `code-wiki-agent init` guidance. | ✓ |

**User's choice:** Strict — manifest required, no fallback.
**Notes:** Cleanest semantics. Pairs naturally with the clean-slate re-init decision (Q5 follow-up).

### Q4 — After delegation, what does `wiki_path` map to?

| Option | Description | Selected |
|--------|-------------|----------|
| wiki_path = workspace_dir + 'wiki' subdir | Lattice convention via `paths.wiki_dir(workspace)`. | ✓ |
| wiki_path = workspace_dir itself | Workspace IS the wiki dir. Diverges from lattice convention. | |
| wiki_path resolved via helper, default = workspace itself | Port helper but make default = workspace itself, configurable later. | |

**User's choice:** wiki_path = workspace_dir + 'wiki' subdir.
**Notes:** Lattice convention preserved. Required a follow-up (Q5) to resolve the conflict with the existing `~/Personal/wiki/deep-agents/` layout.

### Q5 (follow-up) — Where does `.graph-wiki.yaml` actually live given the existing `~/Personal/wiki/deep-agents/` layout?

| Option | Description | Selected |
|--------|-------------|----------|
| Manifest at `~/Personal/wiki/`; rename `deep-agents/` → `wiki/` | One-wiki-per-workspace; rename existing dir. | |
| Manifest at `~/Personal/wiki/deep-agents/`; move content into `wiki/` subdir | Each project-wiki self-contained; move existing content down one level. | |
| Diverge from lattice: `wiki_path = workspace_dir` itself (overrides Q4) | Override Q4; zero file moves; documented divergence. | |
| (Other — user-provided) | — | ✓ |

**User's choice (free-text):** "We will be deleting the old wiki in `~/Personal/wiki` and re-initializing it in a new supported location."
**Notes:** Clean slate. Old wiki gets nuked; new wiki gets bootstrapped via `code-wiki-agent init` at a fresh path. Resolves the layout conflict and validates Q3's strict-manifest-required policy + Q4's lattice convention.

---

## Module trim — port-as-is vs drop

### Q1 — How does `workspace_io.init` integrate with the existing `code-wiki-agent init`?

| Option | Description | Selected |
|--------|-------------|----------|
| `code-wiki-agent init` calls `workspace_io.init` first, then `init_wiki` | Two-phase init in one CLI command. Plugin entry tracks `code-wiki-agent`. | ✓ |
| Port `workspace_io.init` but DON'T wire it into the CLI yet | Ship the function with tests; integration deferred. | |
| Skip `init.py` entirely — only port what delegation needs | Smallest port; Pat creates `.graph-wiki.yaml` manually. | |

**User's choice:** `code-wiki-agent init` calls `workspace_io.init` first, then `init_wiki`.
**Notes:** Unified CLI; one user-facing surface; aligns naturally with the strict-manifest-required policy and the clean-slate re-init plan.

### Q2 — `render.py` + `versions.py` (workspace CLAUDE.md generator + asset-template drift warnings) — port or skip?

| Option | Description | Selected |
|--------|-------------|----------|
| Port both, wire `render.py` into `workspace_io.init` | Lattice parity; workspace CLAUDE.md is distinct from wiki/CLAUDE.md. | ✓ |
| Port `render.py` only — skip `versions.py` | Drop the staleness-warning machinery as YAGNI for solo project. | |
| Skip both | No workspace-level CLAUDE.md; smallest port surface. | |

**User's choice:** Port both.
**Notes:** Workspace `CLAUDE.md` documents the workspace shape for hosts entering the dir — different from `wiki/CLAUDE.md` (layout block). Preserves lattice parity.

### Q3 — `paths.py` helpers — port full surface or trim?

| Option | Description | Selected |
|--------|-------------|----------|
| Port verbatim — all 5 helpers | Tiny module; preserves shape; zero cost. | ✓ |
| Port `wiki_dir` + `raw_dir` only; drop `work_dir`, `knowledge_dir`, `graph_dir` | Trim to actively used helpers. | |
| Port `wiki_dir` + `raw_dir` + `work_dir` | Keep `work_dir` for manifest-layout schema even though work-layer is out of scope. | |

**User's choice:** Port verbatim — all 5 helpers.
**Notes:** Shape compatibility wins; no decision per helper.

### Q4 — `schema.py` (work-item schema writer) — port or drop?

| Option | Description | Selected |
|--------|-------------|----------|
| Drop — record "work-layer out of scope" decision in WS-06 | Verified work-item-only; the `write_schema(work_dir)` call removed from `init`. | ✓ |
| Port but make it a no-op when work_dir doesn't exist | Keep module shape; call site runs but does nothing. | |
| Port and write the schema anyway | Future-proof for if work-layer gets added later. | |

**User's choice:** Drop — record "work-layer out of scope" decision in WS-06.
**Notes:** Verified `_SCHEMA_CONTENT` is 100% work-item frontmatter. **Closes WS-06.**

---

## Manifest field set

### Q1 — `plugins[]` field in `.graph-wiki.yaml` v2 — keep, drop, or replace?

| Option | Description | Selected |
|--------|-------------|----------|
| Keep `plugins[]` verbatim; `workspace_io.init` registers `code-wiki-agent` | Preserve shape; track `code-wiki-agent` as the lone plugin entry. | ✓ |
| Drop `plugins[]` — manifest is `{version, initialized_at}` only | YAGNI for solo project. | |
| Replace `plugins[]` with a generic `metadata: {}` dict | Free-form key/value bag. | |

**User's choice:** Keep `plugins[]` verbatim; `workspace_io.init` registers `code-wiki-agent`.
**Notes:** Future-compatible; preserves the door for a real plugin-tracking lifecycle without adding speculative new fields.

### Q2 — What gets written to `installed_version` and `applied_version` for the `code-wiki-agent` plugin entry?

| Option | Description | Selected |
|--------|-------------|----------|
| Both fields, same value = current `code-wiki-agent` version | Symmetric; `versions.warn_if_stale` no-op locally. | ✓ |
| Only `installed_version`; drop `applied_version` | Single version field; diverges from lattice schema. | |
| Both fields, `installed_version` = version, `applied_version` null until reinit | Most accurate port of lattice's install/apply distinction. | |

**User's choice:** Both fields, same value = current `code-wiki-agent` version.
**Notes:** Symmetric. Field shape preserved.

### Q3 — Where does `code-wiki-agent`'s version string come from for the manifest entry?

| Option | Description | Selected |
|--------|-------------|----------|
| `importlib.metadata.version('code-wiki-agent')` at runtime | Standard stdlib; reads installed wheel metadata; works under uv. | ✓ |
| Hard-coded `__version__` constant in `code_wiki_agent/__init__.py` | Explicit string; manual sync with pyproject. | |
| Lattice-style: read from asset hash | Port verbatim; "version" = asset hash, not semver. | |

**User's choice:** `importlib.metadata.version('code-wiki-agent')` at runtime.
**Notes:** Verify under `uv run --package code-wiki-agent` editable mode during planning research.

---

## Manifest v1→v2 coercion + repo_root semantics

### Q1 — Keep v1→v2 coercion in `manifest.read()`?

| Option | Description | Selected |
|--------|-------------|----------|
| Drop coercion — v2 only, raise on v1 | Clean break; deep-agents has never written v1. | ✓ |
| Keep v1→v2 coercion verbatim | Future-proofs against importing old `.lattice.yaml`. | |
| Drop coercion; ship a one-shot migrate script | Adds new CLI subcommand. | |

**User's choice:** Drop coercion — v2 only, raise on v1.
**Notes:** Saves ~15 lines + test surface. Friendly error suffices.

### Q2 — What does `repo_root` actually contain after delegation?

| Option | Description | Selected |
|--------|-------------|----------|
| Real git-discovery from cwd (lattice semantics) | Walk up looking for `.git`; fall back to `workspace.parent`. | ✓ |
| Always = `workspace.parent` | Simpler; no git discovery. | |
| Keep `repo_root = None` for now | Defer semantics to a later phase. | |

**User's choice:** Real git-discovery from cwd.
**Notes:** Matches `lattice_workspace.config._find_repo_root` directly. Zero behavior change for existing destructuring callers; meaningful for future callers.

### Q3 — `.lattice.local.yaml` per-repo override — rename and behavior?

| Option | Description | Selected |
|--------|-------------|----------|
| Rename to `.graph-wiki.local.yaml`; same `graph-wiki-directory` key | Direct rebrand; behavior unchanged. | ✓ |
| Drop local-config entirely — rely only on `GRAPH_WIKI_WORKSPACE` | Simpler; loses per-repo override affordance. | |
| Keep `.lattice.local.yaml` filename (read-compatible) | Hybrid; filename unchanged but key rebranded. | |

**User's choice:** Rename to `.graph-wiki.local.yaml`; same `graph-wiki-directory` key.
**Notes:** Direct rebrand. Gitignore entry in `workspace_io.init` updates accordingly.

---

## Claude's Discretion

- Internal module structure of `packages/workspace-io/src/workspace_io/` (mirror lattice's flat layout by default).
- Test file naming, fixture organization under `packages/workspace-io/tests/` (port lattice's structure as default).
- Error-message wording for the strict-manifest-required `RuntimeError` (name `code-wiki-agent init` in the message).
- Idempotency of `workspace_io.init` across re-runs (preserve lattice's existing idempotency property).
- Layout of `assets/` packaging inside the wheel (hatchling `package-data` vs uv_build include — pick whichever ships the template file correctly).
- The `DEFAULT_WORKSPACE_NAME` literal — `"graph-wiki"` (kebab match) recommended.

## Deferred Ideas

- `code-wiki-agent migrate-manifest <path>` CLI subcommand (covers v1 → v2 manifest upgrade if needed; not required now).
- `versions.pending_updates` one-time CLI startup warning (skipped here; revisit if template drift becomes real).
- Template body content polish for the rebranded `assets/CLAUDE.md.template` (minimum-viable rebrand now; polish later, possibly Phase 15).
- Tightening `repo_root: Path | None` → `repo_root: Path` after D-15's always-Path fallback (future cleanup if no caller relies on None).
