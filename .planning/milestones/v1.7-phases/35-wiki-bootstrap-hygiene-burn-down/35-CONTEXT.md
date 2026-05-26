# Phase 35: Wiki & Bootstrap Hygiene Burn-Down - Context

**Gathered:** 2026-05-26
**Status:** Ready for planning

<domain>
## Phase Boundary

Burn down 14 atomic hygiene requirements (HYGIENE-01..14) across wiki templates, workspace-io, and bootstrap infrastructure — clearing all overlapping-file debt so v1.7 integration phases (37-40) don't merge-conflict on `commands/scan.py`, `wiki-io` templates, or `workspace-io`. Hygiene-first ordering is mandatory: Phase 35 must merge before Phases 37-40 start.

Out of scope: any new capabilities; any `cg find` parser work (Phase 36); any librarian tool surface (Phase 37); any scanner/ingestor integration with graph-io (Phases 39-40).

</domain>

<decisions>
## Implementation Decisions

### Plan Structure & Merge Sequencing
- **D-01: Two plans, sequenced.** Plan A covers HYGIENE-01..12 (all code edits — template fixes, workspace-io defensive heals, bootstrap re-exec, plugin doc shims). Plan B covers HYGIENE-13..14 (verify-don't-implement: confirm `260521-ans` tests pass; capture phase-close regression artifact).
  - **Why:** Forces verification to happen as a deliberate evidence-gathering step after edits land, instead of being entangled with implementation tasks where it tends to get rubber-stamped.
  - **Constraint:** Plan B does NOT start until Plan A has merged (verification needs the implementation in place).

### Wiki-Bootstrap Verification Approach
- **D-02: Automated-only verification.** Add a pytest fixture that bootstraps a sandbox workspace into `tmp_path`, runs scan, runs `lint_wiki`, and asserts zero broken wikilinks across all three container types (package / app / plugin).
  - **Why:** A regression test is more durable than a manual transcript that goes stale on the next template change. Eliminates the manual-capture toil that has historically been deferred phase-to-phase.
  - **Test location:** `packages/wiki-io/tests/` (new test file — name TBD by planner; suggest `test_bootstrap_e2e_no_broken_links.py`).

- **D-03: HYGIENE-14 closes via the automated test.** The fixture from D-02 IS HYGIENE-14's regression artifact. The roadmap's wording about a manual `/graph-wiki:query` transcript is superseded — DISCUSSION-LOG.md records the swap so future auditors can trace the decision.
  - **Why:** A test that runs on every CI is strictly stronger evidence than a one-time manual transcript.
  - **Impact on Phase 39 SC#3:** The "or confirmed already captured from Phase 35" wording in Phase 39 SC#3 still holds — Phase 39 can reference D-02's test as the captured artifact rather than re-running a manual smoke.

### HYGIENE-13 Closure Evidence
- **D-04: Verify + add inline regression guard comment.** Run `test_cli_help.py` to confirm 3/3 pass; paste the run output into DISCUSSION-LOG.md as the verification artifact; AND add a comment in `test_cli_help.py` (at the env-injection site) linking back to `260521-ans` and explaining that `NO_COLOR=1 TERM=dumb COLUMNS=200` is load-bearing — not cosmetic.
  - **Why:** A future maintainer who refactors test setup needs to see WHY the env injection exists. A comment in the test file is the cheapest insurance against silent regression.
  - **What it does NOT do:** Does not extract a pytest fixture or refactor the env-injection pattern. Just verification + a comment.

### Container Template Handling (HYGIENE-03)
- **D-05: Derive `CONTAINER_DIR` from filesystem path.** Scanner takes the first path segment of each discovered container (`agents/graph-wiki-agent/...` → `CONTAINER_DIR = "agents"`) and passes it through to template render.
  - **Why:** Zero config; matches the scanner's existing discovery model (scanner already knows where it found each container). Adding a new container type "just works" once the scanner finds it.
  - **What it does NOT do:** Does not introduce a `CONTAINER_DIRS` constant, a workspace manifest entry, or a hardcoded scanner dict. Keeps the change surgical to the substitution path.

### Folded Todos
Both pending todos folded directly into HYGIENE-11 and HYGIENE-12 (1:1 mapping — no scope expansion):
- `.planning/todos/pending/2026-05-21-bootstrap-interactive-flag.md` → **HYGIENE-11** (wire `--interactive` flag into graph-wiki bootstrap)
- `.planning/todos/pending/2026-05-21-bootstrap-should-stub-empty-category-index-files.md` → **HYGIENE-12** (bootstrap stubs empty category index files)

Planner should move both files from `pending/` to `resolved/` as part of the Plan A wave.

### Claude's Discretion
- Exact test name and file path for the automated bootstrap fixture (D-02) — planner picks.
- Per-task ordering within Plan A — planner picks based on dependency analysis. Templates (HYGIENE-01..06) and workspace-io (HYGIENE-07..08) are independent; bootstrap (HYGIENE-09..12) depends on neither.
- Whether HYGIENE-09's "test from a tmp working directory" uses `tmp_path` fixture or a real CLI invocation in tmp — planner chooses based on what proves the `Path(__file__).resolve()` fix.

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Phase Scope & Requirements
- `.planning/REQUIREMENTS.md` (HYGIENE-01..14 section) — all 14 requirements with original `(260521-*)` / todo references
- `.planning/ROADMAP.md` (Phase 35 section) — phase goal + 5 concrete success criteria
- `.planning/STATE.md` — active pitfall guards (Pitfall 3: hygiene-first sequencing); already-decided context (HYGIENE-13 already-resolved)

### Templates Being Edited (HYGIENE-01..06)
- `packages/wiki-io/src/wiki_io/assets/page-templates/package/overview.md` — uses `{{CONTAINER_DIR}}` + `{{PACKAGE_SLUG}}` (HYGIENE-01, HYGIENE-03, HYGIENE-04, HYGIENE-06)
- `packages/wiki-io/src/wiki_io/assets/page-templates/app/overview.md` — uses `{{CONTAINER_DIR}}` + `{{APP_SLUG}}` (same set)
- `packages/wiki-io/src/wiki_io/assets/page-templates/plugin/overview.md` — uses `{{CONTAINER_DIR}}` + `{{PACKAGE_SLUG}}` (same set)
- `packages/wiki-io/src/wiki_io/init_vault.py` — stubs section directory `index.md` files (HYGIENE-02)
- `packages/wiki-io/src/wiki_io/scan_monorepo.py` — substitutes `{{CONTAINER_DIR}}` (HYGIENE-03 implementation site)
- `packages/wiki-io/src/wiki_io/lint_wiki.py` — path-qualified wikilink lint (HYGIENE-07)

### workspace-io Targets (HYGIENE-07, HYGIENE-08)
- `packages/workspace-io/src/workspace_io/config.py` — `resolve()` needs to respect `repo-directory:` when `GRAPH_WIKI_WORKSPACE` points at a workspace-that-is-a-git-repo (HYGIENE-07, `260521-gc0`)
- `packages/workspace-io/src/workspace_io/init.py` — `init()` must tolerate sparse v2 manifest with no `plugins` key (HYGIENE-08, `260521-lj3`)

### Bootstrap & Plugin Docs (HYGIENE-09..12)
- `agents/graph-wiki-agent/src/graph_wiki_agent/cli.py` — bootstrap entrypoint (HYGIENE-09, HYGIENE-11)
- `plugins/graph-wiki/agents/*.md` — `uv run --project "$AGENT_RESEARCH_ROOT" python ...` shim (HYGIENE-10)
- `plugins/graph-wiki/skills/graph-wiki/*` — same shim form (HYGIENE-10)

### Verify-and-Close (HYGIENE-13..14)
- `agents/graph-wiki-agent/tests/unit/test_cli_help.py` — 3/3 must pass (HYGIENE-13); add comment linking to `260521-ans`
- `packages/wiki-io/tests/` — new test file lives here (HYGIENE-14 via D-02)

### Pending Todos Being Folded
- `.planning/todos/pending/2026-05-21-bootstrap-interactive-flag.md` — folded into HYGIENE-11
- `.planning/todos/pending/2026-05-21-bootstrap-should-stub-empty-category-index-files.md` — folded into HYGIENE-12

### Prior Test Patterns (Reference, Not Edit)
- `packages/wiki-io/tests/test_overview_template_wikilinks.py` — existing pattern for template-level wikilink assertions; D-02 test extends this idea to a full bootstrap-and-lint loop
- `packages/wiki-io/tests/test_init_vault.py` — existing pattern for `init_vault` behavior tests; HYGIENE-02 changes verified here

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- `wiki_io.lint_wiki` already produces broken-wikilink reports — D-02's test asserts on its output rather than re-implementing link traversal.
- `{{CONTAINER_DIR}}` template variable already present in all three overview templates (`packages/wiki-io/src/wiki_io/assets/page-templates/{package,app,plugin}/overview.md`) — HYGIENE-03 is a substitution-path wiring task, not a template-content change.
- `packages/wiki-io/tests/test_overview_template_wikilinks.py` exists and asserts template wikilink shapes — D-02's test is the natural end-to-end extension.

### Established Patterns
- `NO_COLOR=1 TERM=dumb COLUMNS=200` env-injection for Typer `--help` tests is the project-standard ANSI-strip approach (`260521-ans`); HYGIENE-13 verifies it stays load-bearing.
- workspace-io `init.py` and `config.py` already follow a defensive-heal pattern for missing manifest keys (precedent for HYGIENE-08's `plugins`-key tolerance).

### Integration Points
- Scanner discovery → template render is the substitution boundary where `CONTAINER_DIR` gets injected (D-05). The first path segment of each discovered container is already known at this point — no new traversal needed.
- D-02's bootstrap fixture is the regression fence that catches future template / scanner / lint drift — any change downstream that breaks `[[wiki/<container>/...]]` link resolution will fail this test.

</code_context>

<specifics>
## Specific Ideas

- HYGIENE-13 comment in `test_cli_help.py` should mention `260521-ans` by name so a future maintainer can `grep -r 260521-ans` and find the full incident context. Suggested wording: `# load-bearing: 260521-ans — strip ANSI so Typer --help output is parseable`.
- D-02's test should cover all three container types (`package`, `app`, `plugin`) in a single bootstrap run, not three separate tests — one bootstrap call, three lint assertions.

</specifics>

<deferred>
## Deferred Ideas

- **`CONTAINER_DIRS` single-source-of-truth constant in wiki-io** — considered (option 4 in the gray area discussion) and rejected for now. Filesystem-derived approach (D-05) is sufficient. Revisit if a future phase needs to enumerate valid container dirs in code outside the scanner.
- **Workspace-manifest-driven container dirs** — considered (option 3 in the gray area discussion) and rejected as overkill for current needs. Revisit if/when a user needs per-workspace container customization.
- **Manual `/graph-wiki:query` transcript** — superseded by D-03 (automated test). If the user later wants a one-time human-eye smoke (e.g. before a v1.7 release), capture it as a freestanding artifact, not as HYGIENE-14 closure evidence.
- **Extract `NO_COLOR/TERM/COLUMNS` into a pytest fixture** — considered (option 3 in HYGIENE-13 discussion) and rejected as out-of-scope refactor. Revisit if other CLI test files need the same env injection.

</deferred>

---

*Phase: 35-wiki-bootstrap-hygiene-burn-down*
*Context gathered: 2026-05-26*
