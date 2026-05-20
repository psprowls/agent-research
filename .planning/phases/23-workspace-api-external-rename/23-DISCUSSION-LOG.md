# Phase 23: workspace-api-external-rename - Discussion Log

**Date:** 2026-05-20
**Mode:** discuss (default)

## Areas Discussed

User selected all 4 surfaced gray areas:
- Plan chunking
- `--repo` flag scope (WSMCP-03)
- Brand-gate strictness (WSMCP-07)
- Integration test gate (WSMCP-06)

---

### Area 1: Plan chunking

**Question:** How should Phase 23 be chunked into plans?

**Options presented:**
1. Single big-bang plan — all 7 WSMCP requirements in one plan, one commit. Mirrors Phase 22.
2. Two plans: rename + docs — Plan 1 covers code/tests/brand-gate (WSMCP-01/02/03/04/06/07); Plan 2 covers WSMCP-05 plugin/prompt-sources docs.
3. Three plans: schema / cli / docs — split by surface.

**User selection:** Single big-bang plan.

**Rationale (captured into D-01):** Same posture as Phase 22. The integration test exercises field rename AND flag rename in the same E2E flow, so splitting would leave intermediate states where the test references one name but the schema another. Atomic-but-large diff is the explicit trade-off.

---

### Area 2: `--repo` flag scope (WSMCP-03)

**Question:** Which commands get the new `--repo` flag?

**Options presented:**
1. Bootstrap only.
2. Bootstrap + scan.
3. All commands that resolve a repo (bootstrap, scan, lint).

**User selection:** Bootstrap only.

**Rationale (captured into D-02):** Minimal interpretation of WSMCP-03. Adding `--repo` to non-bootstrap commands would also imply adding matching `repo_path` fields to those MCP input schemas — a much larger surface change than the REQ literal demands. Ergonomic loss accepted in exchange for smaller diff and no help-text drift across commands.

---

### Area 3: Brand-gate strictness (WSMCP-07)

**Question:** How strict should the brand-gate be?

**Options presented:**
1. Minimal (REQ literal) — ban Pydantic Field declarations, Typer flag literals, scan JSON keys only.
2. Minimal + kwarg in production code.
3. Aggressive (everywhere).

**User selection:** Minimal (REQ literal).

**Rationale (captured into D-03):** Historical `.planning/` and SUMMARY.md files contain `vault_path` references that legitimately must not be edited; an aggressive gate would need an enormous, decaying allowlist. Test files can still contain the string `vault_path` as a literal (e.g., schema-rejection assertions) but cannot declare a Pydantic Field with that name.

---

### Area 4: Integration test gate (WSMCP-06)

**Question:** How does Phase 23 treat the Bedrock-live integration test?

**Options presented:**
1. Block execution on manual run.
2. Update + defer to verify-phase.
3. Update + auto-run if env set.

**User selection:** Update + auto-run if env set.

**Rationale (captured into D-04):** Hybrid posture. The test file rename is mechanical (always done); the live Bedrock run is gated on `GRAPH_WIKI_RUN_INTEGRATION=1` + resolvable AWS credentials so the executor doesn't burn credentials when they're not configured. If env present → executor runs the test as a plan-level gate; otherwise → manual UAT recorded in SUMMARY.md for Pat to run before phase verification.

---

## Scope Creep / Redirects

None during this discussion. Pat's selections consistently narrowed scope to the REQ literal interpretation (bootstrap-only `--repo`, minimal brand-gate).

## Deferred Ideas Captured

See `<deferred>` in 23-CONTEXT.md. Notable items:
- Adding `--repo` to non-bootstrap commands (future, if ergonomics demand it)
- Aggressive brand-gate (future, would need allowlist refactor)
- Explicit unit test asserting old field `vault_path` fails Pydantic validation (currently relies on integration test coverage)

## Claude's Discretion Items

Captured in `<decisions>` under "Claude's Discretion":
- Field description text rewording
- Brand-gate regex implementation location (extend `check-brand.sh` vs sibling script — preferred: extend)
- Plugin doc sweep order
- `--repo` flag default value / help text wording / path validation
