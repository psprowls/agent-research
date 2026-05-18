# Requirements — Milestone v1.2 Graph-Wiki Port & Debt Cleanup

**Milestone goal:** Port `lattice-workspace` into a new `workspace-io` package, backport meaningful drift from `lattice-wiki-core` into `vault-io`, rebrand the ecosystem to `graph-wiki`, port the `lattice-wiki` plugin into `plugins/graph-wiki/`, and close v1.1 carry-forward debt around trace pipeline, sweep coverage, MCP cancellation, and model config drift.

**Scoped:** 2026-05-17 via `/gsd-new-milestone`. Source planning thread: `.planning/threads/next-milestone-planning.md`.

---

## Active Requirements

### Workspace-IO Port (M1)
- [ ] **WS-01**: New `packages/workspace-io/` workspace member exists with `pyproject.toml`, `src/workspace_io/`, `tests/`; declared in root `pyproject.toml` workspace members.
- [ ] **WS-02**: `config.py` ported as `workspace_io.config` with `GraphWikiConfig` dataclass and `resolve(cwd)` discovery walking upward for `.graph-wiki.yaml`.
- [ ] **WS-03**: `manifest.py` ported as `workspace_io.manifest` reading/writing `.graph-wiki.yaml` (filename changed from `.lattice.yaml`).
- [ ] **WS-04**: `init.py` ported as `workspace_io.init` performing workspace bootstrap (git init + manifest write + `.gitignore`).
- [ ] **WS-05**: `paths.py`, `render.py`, `versions.py`, `_local_config.py`, `assets/CLAUDE.md.template` ported with `lattice_workspace.*` → `workspace_io.*` import rewrites.
- [ ] **WS-06**: `schema.py` decision recorded — verified before porting; if it only writes work-item schemas, dropped (work layer out of scope); otherwise ported.
- [ ] **WS-07**: Environment variable `LATTICE_WORKSPACE` renamed to `GRAPH_WIKI_WORKSPACE` across the ported package; all `LatticeConfig`/`lattice_*` symbols renamed to `GraphWikiConfig`/`graph_wiki_*`.
- [ ] **WS-08**: `vault-io/_workspace.py::resolve_wiki_and_repo` delegates to `workspace_io.config.resolve()`; the explicit-path argument override path is preserved (MCP boundary contract intact).
- [ ] **WS-09**: Ported tests from `lattice-workspace/tests/` pass under the new module path and `.graph-wiki.yaml` filename expectations.
- [ ] **WS-10**: User-level config migration question answered — is `~/Personal/wiki/deep-agents/wiki-config.toml` the same surface as `.graph-wiki.yaml`? If yes, one-shot migration script ships; if no, decision documented in PROJECT.md Key Decisions.

### Selective Drift Backport (M2)
- [ ] **BACKPORT-01**: Body-diff inventory of `lint/*` (8 files) between `vault-io` and `lattice-wiki-core`; substantive upstream changes backported into `vault-io`, identical contracts left alone, decision logged per file.
- [ ] **BACKPORT-02**: Body-diff `init_vault.py` against upstream; substantive changes backported, otherwise documented as "leave-alone" with reason.
- [ ] **BACKPORT-03**: `ingest_work_item.py` API divergence decision recorded — `file_work_item` lib shape retained (fits MCP boundary) unless backport rationale emerges.
- [ ] **BACKPORT-04**: All "leave" decisions from spike 002 §Investigation A documented in `packages/vault-io/DRIFT-DECISIONS.md` so the rationale survives the rebrand.

### Ecosystem Rebrand (M2)
- [ ] **BRAND-01**: All `lattice`/`LATTICE`/`lattice_workspace`/`lattice_wiki_core` references across `packages/`, `agents/`, `plugins/`, `.planning/`, `CLAUDE.md` renamed to `graph-wiki` (kebab) or `graph_wiki` (snake) per context.
- [ ] **BRAND-02**: `.planning/spikes/CONVENTIONS.md` `cores/` → `packages/` reference corrected (already flagged stale).
- [ ] **BRAND-03**: Wiki self-update — `~/Personal/wiki/deep-agents` scanned + ingested after rebrand to absorb new package names and `.graph-wiki.yaml` manifest.
- [ ] **BRAND-04**: Naming consistency sweep — `grep -rE 'lattice|LATTICE|lattice_workspace|lattice_wiki_core'` across in-scope paths returns zero hits after rebrand (commit-history-only references in `~/Personal/lattice/` excluded).

### Plugin Port (M3)
- [ ] **PLUGIN-01**: Spec phase completed answering: *what do `lattice-wiki` plugin slash commands actually shell out to?* — deep-agents CLI/MCP server, lattice CLIs, or both — and contract surface locked before code is moved.
- [ ] **PLUGIN-02**: `/Users/pat/Personal/lattice/plugins/lattice-wiki/` ported to `plugins/graph-wiki/`; `.claude-plugin/plugin.json` metadata renamed; plugin id renamed to `graph-wiki`.
- [ ] **PLUGIN-03**: Slash command namespace renamed `/lattice-wiki:*` → `/graph-wiki:*`; agent names, skill names renamed accordingly.
- [ ] **PLUGIN-04**: Plugin scripts rewritten so vault I/O goes through `vault-io` (which uses `workspace-io`); no direct `lattice_*` imports remain.
- [ ] **PLUGIN-05**: Plugin loads and at least one slash command (`/graph-wiki:query`) runs end-to-end against the deep-agents vault.

### Trace Pipeline Correctness (carry-forward)
- [ ] **TRACE-FU-01**: Production trace pipeline emits `usage_metadata` on every JSONL record (input/output token counts) — today only the sweep harness records token counts.

### Sweep Coverage (carry-forward)
- [ ] **SWEEP-FU-02**: DivergenceMetric wired through the full sweep matrix (all in-scope roles).
- [ ] **SWEEP-FU-03**: `code_reader` cases re-tuned against current fixture corpus.
- [ ] **SWEEP-FU-04**: Scanner re-swept against a fresh-package vault (regression test post-port).

### MCP Cancellation Completion (carry-forward)
- [ ] **MCP-CAN-01**: Real DA-CLI wire-level cancel verified end-to-end (Phase 8 SC#1 deferral closed) — requires aioboto3 (or equivalent wire-level cancel path) to have landed; if blocked, deferral re-documented.
- [ ] **MCP-CAN-02**: Opt-in gate consistency reviewed across MCP tools — `CODE_WIKI_RUN_INTEGRATION` semantics aligned across all gated tests.

### Model Config Drift (carry-forward)
- [ ] **MODEL-FU-01**: `test_load_role_config_synthesizer_uses_sonnet` fixed to match Qwen synthesizer reality (test asserts current default).

---

## Future Requirements (deferred from v1.2)

- **Open-source release prep** — README badges, contribution guide, public install instructions, PyPI publish dry-run → **v2.0 GA**.
- **Nyquist compliance** — 0/5 v1.1 phases reached `nyquist_compliant: true`; retroactively validate or disable the toggle → **v1.3**.

---

## Out of Scope

- **`work/` subsystem port** (work-layer modules, `archive_work.py`, `work_status.py`, `lint_work.py`, `regenerate_work_index.py`) — GSD covers work-item lifecycle (thread decision 2026-05-17).
- **Package-family monorepo support restoration** — different approach planned (thread decision 2026-05-17).
- **Backport of modules where vault-io is ahead** — `git_state.py`, `append_log.py`, `update_index.py`, `update_tokens.py`, `layout_io.py`, `detect_containers.py`, `scan_monorepo.py`, `ingest_source.py`. Spike 002 verdict: deliberate forks, leave as-is.
- **`export_marp.py`, standalone `wiki_search.py`, standalone `lint_wiki.py`** — superseded by current `commands/` implementations.

---

## Traceability

_Filled by roadmapper after phase mapping._

| REQ-ID | Phase |
|--------|-------|
