# Roadmap: deep-agents / graph-wiki-agent

**Project:** deep-agents (v1 = graph-wiki-agent)
**Created:** 2026-05-13
**Current milestone:** v1.4 — Workspace Path Resolution Cleanup (started 2026-05-20)

---

## Milestones

- ✅ **v1.0 — graph-wiki-agent parity** — Phases 1-5 (shipped 2026-05-15) — [archive](milestones/v1.0-ROADMAP.md)
- ✅ **v1.1 — Quality Improvements** — Phases 6-10 (shipped 2026-05-17) — [archive](milestones/v1.1-ROADMAP.md)
- ✅ **v1.2 — Graph-Wiki Port & Debt Cleanup** — Phases 11-16 (shipped 2026-05-19) — [archive](milestones/v1.2-ROADMAP.md)
- ✅ **v1.3 — Tooling Cleanup** — Phases 17-21 (shipped 2026-05-20) — [archive](milestones/v1.3-ROADMAP.md) · [audit](milestones/v1.3-MILESTONE-AUDIT.md)
- 🚧 **v1.4 — Workspace Path Resolution Cleanup** — Phases 22-25 (active)

---

## Phases

<details>
<summary>✅ v1.0 graph-wiki-agent parity (Phases 1-5) — SHIPPED 2026-05-15</summary>

- [x] Phase 1: Infrastructure, Vault IO, and MCP Skeleton (5/5 plans) — completed 2026-05-13
- [x] Phase 2: Subagent Fan-Out Runtime (4/4 plans) — completed 2026-05-13
- [x] Phase 3: Query Vertical Slice + Hybrid Search (6/6 plans) — completed 2026-05-14
- [x] Phase 4: Eval Harness (4/4 plans) — completed 2026-05-14
- [x] Phase 5: Remaining Commands (6/6 plans) — completed 2026-05-14

Full detail: [`milestones/v1.0-ROADMAP.md`](milestones/v1.0-ROADMAP.md)

</details>

<details>
<summary>✅ v1.1 Quality Improvements (Phases 6-10) — SHIPPED 2026-05-17</summary>

- [x] Phase 6: Prompt Content Port + Divergence Eval (16/16 plans) — completed 2026-05-17
- [x] Phase 7: Cost-Frontier Sweep (7/7 plans) — completed 2026-05-17
- [x] Phase 8: Host Reliability (3/3 plans) — completed 2026-05-17
- [x] Phase 9: Trace/Observability Polish (6/6 plans) — completed 2026-05-17
- [x] Phase 10: Subagent Context Completion (7/7 plans) — completed 2026-05-17

Full detail: [`milestones/v1.1-ROADMAP.md`](milestones/v1.1-ROADMAP.md)
Audit: [`milestones/v1.1-MILESTONE-AUDIT.md`](milestones/v1.1-MILESTONE-AUDIT.md)

</details>

<details>
<summary>✅ v1.2 Graph-Wiki Port & Debt Cleanup (Phases 11-16) — SHIPPED 2026-05-19</summary>

- [x] Phase 11: workspace-io Port (M1) (6/6 plans) — completed 2026-05-18
- [x] Phase 12: Drift Backport + Ecosystem Rebrand (M2) (4/4 plans) — completed 2026-05-18
- [x] Phase 13: Plugin Spec (M3a) (5/5 plans) — completed 2026-05-18
- [x] Phase 14: Plugin Port (M3b) (3/3 plans) — completed 2026-05-19
- [x] Phase 15: Wiki Self-Update (1/1 plan) — completed 2026-05-19
- [x] Phase 16: Carry-Forward Debt Cleanup (2/2 plans) — completed 2026-05-19

Full detail: [`milestones/v1.2-ROADMAP.md`](milestones/v1.2-ROADMAP.md)

</details>

<details>
<summary>✅ v1.3 Tooling Cleanup (Phases 17-21) — SHIPPED 2026-05-20</summary>

- [x] Phase 17: vault-io Bug Fixes (5/5 plans) — completed 2026-05-20
- [x] Phase 18: Plugin Command Rename (6/6 plans) — completed 2026-05-20
- [x] Phase 20: Workspace Manifest Model Config (4/4 plans) — completed 2026-05-20
- [x] Phase 21: Rename graph-wiki-agent → graph-wiki-agent (5/5 plans) — completed 2026-05-20
- [x] Phase 19: Phase 16 Code Review Burndown (5/5 plans) — completed 2026-05-20

Full detail: [`milestones/v1.3-ROADMAP.md`](milestones/v1.3-ROADMAP.md)
Audit: [`milestones/v1.3-MILESTONE-AUDIT.md`](milestones/v1.3-MILESTONE-AUDIT.md)

</details>

### v1.4 Workspace Path Resolution Cleanup (Phases 22-25) — ACTIVE

- [x] **Phase 22: workspace-api-internal-rename** — Internal Python API: `resolve_wiki_and_repo` signature, all 6 `run_*` command signatures, call sites, test mocks, `.graph-wiki.local.yaml` key, and `resolve_workspace` promotion (completed 2026-05-20)
- [x] **Phase 23: workspace-api-external-rename** — External surfaces: 6 MCP Pydantic fields, 7 Typer flags, scan JSON output field, plugin docs, DA-CLI integration test, and brand-gate extension (completed 2026-05-20)
- [ ] **Phase 24: eval-harness-workspace-rename** — eval-harness package: `vault_path` → `workspace_path` in sweep/baseline/structural, `vault:` → `wiki:` in divergence helpers, test updates, README refresh
- [ ] **Phase 25: packages-dir-misclassification-fix** — Bootstrap bug: `_classify_dir` majority-manifest heuristic, plugin-side classifier sync, `--interactive` flag, unit test, and todo resolution

---

## Phase Details

### Phase 22: workspace-api-internal-rename
**Goal**: Every internal Python caller passes `workspace_path` (not `vault_path`) to command functions and the workspace resolver; the wiki path is always derived via `workspace_io.paths.wiki_dir()` rather than assembled by callers; the `.graph-wiki.local.yaml` key is hard-cut to `workspace-directory`
**Depends on**: Phase 21 (prior milestone)
**Requirements**: WSAPI-01, WSAPI-02, WSAPI-03, WSAPI-04, WSAPI-05, WSAPI-06
**Success Criteria** (what must be TRUE):
  1. `uv run pytest` is green after all renames — no test references `vault_path=` as a kwarg in any command mock or call site
  2. `resolve_wiki_and_repo(workspace_path=Path("/some/workspace"))` returns `(wiki_dir(workspace_path), repo_root)` without string concatenation inside the command layer
  3. `workspace_io.config.resolve_workspace` is importable as a public symbol and is called by `run_init` instead of hardcoding `repo_root / "graph-wiki"`
  4. A `.graph-wiki.local.yaml` containing `graph-wiki-directory: /custom/path` is silently ignored; one containing `workspace-directory: /custom/path` is honored
  5. `grep -r "vault_path" agents/graph-wiki-agent/src packages/workspace-io/src` returns 0 hits (excluding comments in allowlist)
**Plans**: 1 plan
  - [x] 22-01-PLAN.md — workspace-api-internal-rename (big-bang single plan covering WSAPI-01..06 + ~70-mock-point test sweep)

### Phase 23: workspace-api-external-rename
**Goal**: Every external-facing surface — MCP tool schemas, Typer CLI flags, scan JSON output, plugin docs, and the DA-CLI integration test — uses `workspace_path` / `--workspace` / `wiki_relative_path` instead of the old `vault_path` / `--vault` nomenclature; brand-gate enforces no reintroduction
**Depends on**: Phase 22
**Requirements**: WSMCP-01, WSMCP-02, WSMCP-03, WSMCP-04, WSMCP-05, WSMCP-06, WSMCP-07
**Success Criteria** (what must be TRUE):
  1. `graph-wiki-agent scan --help` shows `--workspace` (not `--vault`) for every subcommand; `graph-wiki-agent bootstrap --help` also shows `--repo`
  2. MCP tool call `wiki_scan` with field `workspace_path` succeeds; a call using the old field `vault_path` fails schema validation
  3. Scan JSON output (`wiki_scan` response) contains `wiki_relative_path` per package entry; `vault_path` does not appear in any scan result field
  4. `GRAPH_WIKI_RUN_INTEGRATION=1 uv run pytest agents/graph-wiki-agent/tests/integration/test_mcp_e2e.py` passes using the new field/flag names
  5. `scripts/check-brand.sh` exits non-zero when a test file introduces `vault_path` as a Pydantic Field name or `--vault` as a Typer flag literal
**Plans**: 1 plan
  - [x] 23-01-PLAN.md — workspace-api-external-rename (big-bang single plan covering WSMCP-01..07 + brand-gate CHECK 4 + integration test sweep)

### Phase 24: eval-harness-workspace-rename
**Goal**: The eval-harness package is internally consistent with the v1.4 naming convention — `workspace_path` everywhere a workspace root is meant, `wiki` everywhere the wiki directory itself is meant, and zero residual `vault_path` / `--vault` / `vault:` occurrences
**Depends on**: Nothing (independent of Phases 22 and 23)
**Requirements**: WSEVAL-01, WSEVAL-02, WSEVAL-03, WSEVAL-04, WSEVAL-05
**Success Criteria** (what must be TRUE):
  1. `uv run --package eval-harness pytest` is green after all renames
  2. `python -m eval_harness.baseline --help` shows `--workspace` (not `--vault`)
  3. All divergence helper functions in `divergence/{linter,ingestor,scanner,code_reader,synthesizer}.py` accept `wiki: Path` (not `vault: Path`); callers pass the wiki dir directly
  4. `eval/README.md` contains no `vault_path` references
  5. `grep -r "vault_path\|vault:" packages/eval-harness/src` returns 0 hits
**Plans**: TBD

### Phase 25: packages-dir-misclassification-fix
**Goal**: Running `graph-wiki-agent bootstrap` on this repo without `--interactive` correctly classifies `packages/` as `package` and creates `wiki/packages/`; the pending todo is resolved; the plugin-side classifier matches the updated heuristic
**Depends on**: Nothing (independent of Phases 22, 23, and 24)
**Requirements**: PKGCLS-01, PKGCLS-02, PKGCLS-03, PKGCLS-04, PKGCLS-05
**Success Criteria** (what must be TRUE):
  1. `graph-wiki-agent bootstrap` on this repo (without `--interactive`) classifies `packages/` as `package` and creates `wiki/packages/` automatically
  2. `_classify_dir` with a fixture dir containing 5/6 manifested children returns `package` (not `ambiguous`); unit test asserts this
  3. `plugins/graph-wiki/skills/graph-wiki/scripts/detect_containers.py` applies the identical ≥80% majority heuristic as the updated `vault-io` classifier
  4. `graph-wiki-agent bootstrap --interactive` prompts the user on any remaining `ambiguous` classifications instead of silently skipping them
  5. `.planning/todos/pending/2026-05-20-fix-packages-dir-misclassification.md` is moved to `.planning/todos/resolved/` and the `--interactive` flag is visible in `graph-wiki-agent bootstrap --help`
**Plans**: TBD

---

## Progress

| Phase | Plans Complete | Status | Completed |
|-------|----------------|--------|-----------|
| 22. workspace-api-internal-rename | 1/1 | Complete   | 2026-05-20 |
| 23. workspace-api-external-rename | 1/1 | Complete   | 2026-05-20 |
| 24. eval-harness-workspace-rename | 0/TBD | Not started | - |
| 25. packages-dir-misclassification-fix | 0/TBD | Not started | - |

| Milestone | Phases | Plans | Status | Shipped |
|-----------|--------|-------|--------|---------|
| v1.0 graph-wiki-agent parity | 5 | 25/25 | ✅ Shipped | 2026-05-15 |
| v1.1 Quality Improvements | 5 | 39/39 | ✅ Shipped | 2026-05-17 |
| v1.2 Graph-Wiki Port & Debt | 6 | 21/21 | ✅ Shipped | 2026-05-19 |
| v1.3 Tooling Cleanup | 5 | 25/25 | ✅ Shipped | 2026-05-20 |
| v1.4 Workspace Path Resolution Cleanup | 4 | 0/TBD | In progress | - |

---

*Last updated: 2026-05-20 — v1.4 roadmap created (4 phases, 23 requirements). Phases 22-25 ready for planning.*
