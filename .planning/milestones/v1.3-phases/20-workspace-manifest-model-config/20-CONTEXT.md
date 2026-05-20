# Phase 20: Workspace Manifest Model Config - Context

**Gathered:** 2026-05-19
**Status:** Ready for planning (discuss-phase skipped — context captured in-session)
**Source:** Conversational triage in 2026-05-19 session (no separate discuss-phase log)

---

## Why this phase exists

While fleshing out wiki pages we discovered that `wiki-config.toml` and `wiki-config-claude.toml` at the repo root **had no source-code references** — nothing auto-loaded them. They worked only when explicitly passed via `code-wiki --config <path>` or `GRAPH_WIKI_CONFIG=<path>` env var.

Both TOML files were `git rm`'d earlier in this session (already staged). The user's direction: **all wiki configuration should live in `.graph-wiki.yaml` (workspace manifest, checked in) and/or `.graph-wiki.local.yaml` (per-machine, gitignored).** This phase makes that real.

## Locked decisions (from session)

1. **Canonical config source:** `<workspace>/.graph-wiki.yaml` `plugins[].roles[]` block. The existing manifest in `~/Personal/deep-agents/graph-wiki/.graph-wiki.yaml` already proves the shape with a single `preflight` role.

2. **Fallback layer:** Packaged `packages/model-adapter/src/model_adapter/models.toml`. Used per-role when workspace manifest is silent on that role (not all-or-nothing).

3. **Per-machine override mechanism (Option A):** `.graph-wiki.local.yaml` redirects to a different workspace directory via `graph-wiki-directory: <path>`. That alternate workspace carries its own `.graph-wiki.yaml` with its own `roles:` block. The flat-only local-config parser stays as-is — no nesting required.

4. **Deletion sweep:** Remove `WikiConfig.models_path`, `set_models_path()`, the Typer `--config` option, and the `GRAPH_WIKI_CONFIG` env var. No backwards-compatibility shim — the TOML files are already gone and no users have migrated state to preserve.

5. **`manifest.py` already uses PyYAML.** Existing code: `packages/workspace-io/src/workspace_io/manifest.py:6` (`import yaml`), `packages/workspace-io/pyproject.toml:6` (`dependencies = ["pyyaml>=6.0"]`). The earlier wiki-page claim of "no PyYAML" was wrong; the workspace-io wiki page needs a one-line correction as part of this phase.

## Resolution chain target

```
repo_root/.graph-wiki.local.yaml        ← per-machine, gitignored
  graph-wiki-directory: <path>          ← picks which workspace
                ↓
<workspace>/.graph-wiki.yaml            ← workspace manifest, checked in
  plugins:
    - name: graph-wiki-agent
      roles:
        - name: preflight | librarian | scanner | ...
          model_id: "us.anthropic.claude-..."
          region: "us-east-1"
          max_tokens: 64
          max_concurrency: 1
                ↓ (per-role fallback when role absent)
packages/model-adapter/src/model_adapter/models.toml   ← packaged default
```

## Open questions for the planner

All open questions resolved during phase execution. See SUMMARY.md for outcomes.

## Out of scope (explicit)

- **Per-machine model selection inside `.graph-wiki.local.yaml`.** User explicitly chose Option A — redirect to a different workspace dir instead. Do not extend the flat-only local-config parser to support nested role overrides.
- **Migrating data from deleted `wiki-config.toml` files.** Already deleted; no migration path needed.
- **`~/Personal/wiki/deep-agents/` vs `~/Personal/deep-agents/graph-wiki/wiki/` divergence.** Surfaced in session as a separate decision; not part of this phase.
- **Changes to `models-claude.toml`.** Separately staged deletion in `git status`, unrelated.

## Files to touch (initial inventory — planner refines)

**Source code:**
- `packages/workspace-io/src/workspace_io/manifest.py` — extend nested `roles[]` read/write (PyYAML, native nesting)
- `packages/workspace-io/src/workspace_io/__init__.py` — export `read_roles` (or equivalent accessor)
- `packages/model-adapter/src/model_adapter/loader.py` — workspace-aware override layer in `make_llm`
- `agents/graph-wiki-agent/src/graph_wiki_agent/config.py` — delete `models_path` field, `set_models_path()`, `--config` plumbing
- `agents/graph-wiki-agent/src/graph_wiki_agent/cli.py` — drop `--config` Typer option
- `agents/graph-wiki-agent/src/graph_wiki_mcp/server.py:446` — drop `GRAPH_WIKI_CONFIG` env var read

**Tests:**
- `packages/workspace-io/tests/test_manifest_v2_roundtrip.py` — add populated-roles fixture
- `packages/model-adapter/tests/test_loader.py` — workspace-override + per-role fallback tests
- `agents/graph-wiki-agent/tests/unit/test_config.py` — drop `models_path` assertions

**Configuration / data:**
- `~/Personal/deep-agents/graph-wiki/.graph-wiki.yaml` — fill in full `roles[]` set (preflight, librarian, scanner, linter, ingestor, synthesizer, code_reader, judge) mirroring packaged defaults

**Docs:**
- `packages/workspace-io/README.md` — document the `roles:` schema
- `agents/graph-wiki-agent/` README / CLI help — drop `--config wiki-config.toml` references
- `~/Personal/wiki/deep-agents/packages/workspace-io/workspace-io.md` — correct stale "no PyYAML" claim
- `.planning/intel/stack.json` — drop stale `wiki-config.toml` reference

## Dependencies and risks

- **Phase 17 (workspace/repo resolution)** — depended on; SC#4 closure pending but does not block planning.
- **Risk: roles loader called before workspace exists.** Some test paths and the MCP startup may invoke `make_llm` before `workspace-io.resolve()` succeeds. Plan must define the resolution order and the no-workspace fallback to packaged `models.toml`.
- **Risk: existing call sites of `set_models_path()`.** Grep across the repo before deletion; tests in particular may have wiring.

## Verification approach (sketch)

- SC#1: round-trip unit test for `manifest.py` with a populated `roles[]` block
- SC#2: paired tests in `model-adapter` — (a) workspace defines role → workspace wins; (b) workspace silent on role → fallback to `models.toml`
- SC#3: grep gate in CI (or manual check) — no remaining `models_path`, `set_models_path`, `--config`, `GRAPH_WIKI_CONFIG`, or `wiki-config.toml` references in source
- SC#4: live verify by running `code-wiki query "..."` against `~/Personal/deep-agents/graph-wiki/` with the full role block and confirming the configured models are used
- SC#5: doc diff review

## Glossary

- **workspace** — directory containing `.graph-wiki.yaml`, sibling of `raw/`, `work/`, `wiki/`
- **role** — named model assignment (preflight, librarian, scanner, linter, ingestor, synthesizer, code_reader, judge)
- **per-role fallback** — when workspace defines `roles: [{librarian: ...}]` but not `scanner`, `scanner` falls back to packaged `models.toml`; the override is per-role, not all-or-nothing
