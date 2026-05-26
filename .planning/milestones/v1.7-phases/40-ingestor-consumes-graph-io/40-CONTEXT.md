# Phase 40: Ingestor Consumes graph-io - Context

**Gathered:** 2026-05-26
**Status:** Ready for planning (gated on Phase 39 shipping the URI-slug derivation pattern Phase 40 D-04 reuses)

<domain>
## Phase Boundary

Wire the ingestor to consult graph-io for canonical entity existence BEFORE making ingest-routing decisions. `run_ingest_source()` queries the graph (path-first, name fallback) to detect whether a source corresponds to a known canonical entity; when matched, the canonical URI-derived slug overrides the LLM's guess so ingestor-created pages slug-align with scanner-created pages (eliminating slug drift). Pages gain an `entity_uri` frontmatter field (the URI for matched sources, `null` for free-form docs/ADRs/notes). Invoking `graph-wiki-agent ingest` against a workspace with no graph-io DB surfaces a clear `NOT_INITIALIZED` error (REVERSE of Phase 39 scanner's graceful fallback — different surface, different policy). URI-drift / orphaned-page risk is documented as a v1.8 reconciliation item — explicitly NOT solved here.

Out of scope:
- URI-drift / orphaned-page reconciliation on package rename (deferred to v1.8 per INGESTOR-03)
- Plugin ingest path coupling to graph-io (deferred to v1.8 per REQUIREMENTS.md)
- `run_ingest_work_item` coupling — verify at plan time whether work-item ingest surfaces entity-existence questions; if not, leave it unchanged
- Multi-match disambiguation logic (planner picks a simple deterministic rule — e.g. first-match-wins — and notes any non-trivial behavior as a v1.8 follow-up)

</domain>

<decisions>
## Implementation Decisions

### NOT_INITIALIZED Error UX

- **D-01: Reuse `graph_io.exit_codes.NOT_INITIALIZED`.** When `graph-wiki-agent ingest` is invoked against a workspace whose `.graph-wiki/graph/code.db` does not exist (or `read_only_connect()` raises `GraphNotInitializedError`), the agent CLI exits with the SAME numeric code that `cg find` / `cg describe-*` already return for this condition. Planner reads the constant from `packages/graph-io/src/graph_io/exit_codes.py`.
  - **Why:** Single mental model across all graph-consuming commands. Scripts that already handle `cg`'s NOT_INITIALIZED don't need a new case for `graph-wiki-agent ingest`.

- **D-02: Error message suggests the agent-native path first, with `cg update` as the fallback hint.** Stderr text: `error: graph-io not initialized for this workspace. Run 'graph-wiki-agent graph build' (or 'cg update') to initialize, then retry.`
  - **Why:** Actionable; surfaces Phase 38's `graph build` command as the agent-native entry point; mentions the underlying `cg update` for users who already know it. The order (agent-native first, cg second) reinforces that the agent CLI is the discoverable surface.
  - **Surface:** Stderr only; not in IngestResult body. CLI exits before reaching the LLM call.

### What 'Canonical Entity Existence Check' Means

- **D-03: Path-first lookup, then name fallback.** The ingestor's pre-routing graph query happens in two steps:
  1. **Path lookup:** Resolve the source file's path relative to repo root → query graph for a node with matching `path` attribute. If found, use this node's URI as the canonical match.
  2. **Name fallback:** If no path match, take the LLM-guessed title (or filename stem) → query graph for a node with matching `name`. If found, use this node's URI as the canonical match.
  - **Why:** Maximum coverage. Path-based finds packages and files directly. Name-based catches sources ABOUT named entities (e.g. a doc about `SubagentPool` class can map to that class's graph node even though the doc lives at `wiki/concepts/`).
  - **Tie-breaking:** If name lookup returns multiple matches, planner picks a deterministic rule (suggest: first match by URI lexicographic order, or refuse with a warning if N > 1 and let the LLM-guessed slug stand). Document the choice in the plan.

- **D-04: Override LLM's `target_slug` with canonical URI-derived slug when a match is found.** The LLM provides the BODY content; the graph provides the SLUG. The slug-derivation algorithm is the SAME as Phase 39 D-03 (last URI segment + graph node attrs for routing prefix: `apps/<n>/` | `domains/<d>/packages/<n>/` | `packages/<n>/`).
  - **Why:** Eliminates slug drift between scanner-created and ingestor-created pages — both consult the same canonical mapping. Graph is ground truth; LLM provides interpretation. Mirrors Phase 39's invariant.
  - **Cross-phase coupling:** Phase 39 D-03 establishes the URI → slug derivation. Phase 40 calls into the same helper (or duplicates the logic carefully). Planner: prefer a shared utility in `agents/graph-wiki-agent/src/graph_wiki_agent/...` so both scanner and ingestor stay in lockstep. If Phase 39 hasn't extracted a helper, Phase 40's planner picks: (a) extract one as part of this phase, (b) duplicate with a TODO to consolidate later. Suggest (a).

### Behavior When No Graph Entity Matches

- **D-05: Proceed with LLM-guessed slug + `entity_uri: null` frontmatter.** When neither path nor name lookup finds a match, ingest succeeds using today's LLM-guessed slug. Page frontmatter gets `entity_uri: null` so downstream tooling (lint, link-checker, v1.8 reconciliation) can distinguish entity-backed pages from free-form ones.
  - **Why:** Preserves existing ingest behavior for non-entity sources (docs, ADRs, feedback notes, random Markdown). Strictest alternative (refuse to ingest non-entity sources) would break common workflows. The `entity_uri: null` field is the explicit signal that this page is free-form by design, not by accident.
  - **What it does NOT do:** Does not route non-entity sources to a separate vault subtree (e.g. `wiki/notes/`). The existing `_route_target_path(wiki, page_type, slug)` logic stays.

- **D-06: Entity-backed pages get `entity_uri: <full-URI>` frontmatter.** When a canonical entity IS found, the ingestor writes `entity_uri: pkg:org/repo/graph-io` (or whatever URI matched) into the page's YAML frontmatter. Single field; full URI; machine-readable.
  - **Why:** Lossless. Downstream v1.8 reconciliation can parse the URI to detect drift (the file's path-derived URI vs. what's recorded in frontmatter). Matches Phase 28+ schema vocabulary ("URI is the canonical identifier"). Grep-friendly: `grep -r "entity_uri: pkg:" wiki/` finds all entity-backed pages.
  - **What it does NOT do:** Does not duplicate the entity name/kind into separate frontmatter fields. Single source of truth in the URI string.

### URI-Drift Documentation

- **D-07: Document in BOTH a code comment AND `40-01-PLAN.md`.** Per INGESTOR-03's literal "code comments AND phase plan" wording:
  - **Code comment:** Block comment on `run_ingest_source` (near the graph-lookup site), naming the limitation and the v1.8 reference.
  - **Phase plan:** Dedicated `## v1.8 Reconciliation` section in `40-01-PLAN.md` that future maintainers can grep for (`grep -r "v1.8 Reconciliation" .planning/`).
  - **Why:** Two surfaces, two audiences — code reviewers reading `commands/ingest.py` see the limitation in context; milestone-planning audits scanning `.planning/phases/*/40-*-PLAN.md` see it without having to read source.

- **D-08: Describe the limitation only — do NOT sketch v1.8's solution.** The documentation states: "When a package is renamed in the source repo, the `entity_uri` recorded in existing ingested pages becomes orphaned (points at the old URI). Phase 40 does NOT automatically migrate orphaned URIs; this is a v1.8 reconciliation item."
  - **Why:** Don't pre-commit v1.8 to an approach. v1.8's design space is wider than what's apparent here — could be a rewrite tool, could be a frontmatter audit, could be a graph-side rename-tracking edge, could be all three.
  - **What it does NOT do:** Does not include sketched code, proposed CLI surfaces, or speculative `cg reconcile-renames` commands.

### Claude's Discretion

- Connection lifetime inside `run_ingest_source` — planner picks; suggest mirroring Phase 39 D-05 (open once at command entry, captured by closure, closed in `finally`). For single-source ingest, even per-call open isn't a perf concern, but consistency with Phase 37/39 wins.
- Whether `run_ingest_work_item` (`ingest.py:538`) also needs graph consultation — planner verifies. If work items are user-authored cross-cutting notes that don't correspond to source entities, leave work-item ingest unchanged.
- Whether to extract the URI → slug derivation into a shared helper (recommended) vs duplicate with a consolidation TODO.
- Multi-match disambiguation logic for name-fallback lookup (D-03 step 2). Suggest: refuse to override LLM-guessed slug when N > 1 matches; log a warning; proceed as the no-match path (D-05) with `entity_uri: null`. Document the rule in the plan.
- Exact stderr error wording (D-02) — planner finalizes.
- Whether the `entity_uri` frontmatter field is added to existing pages on re-ingest, or only on net-new ingests. Suggest: write the field on every successful ingest (overwrites stale values).

### Folded Todos

None. No todos match Phase 40's ingestor scope.

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Phase Scope & Requirements
- `.planning/REQUIREMENTS.md` (INGESTOR-01..03 section) — three locked requirements
- `.planning/ROADMAP.md` (Phase 40 section) — phase goal + 3 success criteria (SC#1 graph-existence check before ingest decisions; SC#2 NOT_INITIALIZED error not silent fallback; SC#3 URI-drift documented as v1.8 item)
- `.planning/STATE.md` (Pitfall 4) — single-conn open per command entry pattern

### Cross-Phase Coupling (READ BEFORE PLANNING)
- `.planning/phases/39-scanner-consumes-graph-io/39-CONTEXT.md` — D-03 URI → slug derivation algorithm; D-04 agent-side decoration pattern; D-05 connection lifetime. **Phase 40 D-04 mirrors Phase 39 D-03 exactly.** Phase 39 must merge before Phase 40 implementation (so the shared URI-derivation helper is available).
- `.planning/phases/38-graph-wiki-agent-graph-subcommand/38-CONTEXT.md` — D-02 error message references `graph-wiki-agent graph build` as the agent-native init command.
- `.planning/phases/37-librarian-grounding-tools/37-CONTEXT.md` — D-03 connection-lifetime pattern that Phase 40 mirrors.

### Target Files (Modified)
- `agents/graph-wiki-agent/src/graph_wiki_agent/commands/ingest.py` (around lines 369-533 for `run_ingest_source`) — gains:
  - Graph-existence check at command entry (D-01 NOT_INITIALIZED error path)
  - Read-only conn open after the workspace resolve (mirror Phase 39 D-05 pattern)
  - Path-then-name lookup before LLM call (D-03)
  - Slug override when match found (D-04)
  - `entity_uri` frontmatter write (D-05/D-06)
  - URI-drift code comment (D-07/D-08)
  - `finally` block to close the conn

### Read-Only References (Don't Edit)
- `agents/graph-wiki-agent/src/graph_wiki_agent/commands/ingest.py:369-533` — current `run_ingest_source` 10-step pipeline (modification site)
- `agents/graph-wiki-agent/src/graph_wiki_agent/commands/ingest.py:538-...` — `run_ingest_work_item`; verify during planning whether it needs graph consultation
- `agents/graph-wiki-agent/src/graph_wiki_agent/commands/ingest.py:93-148` — `_route_target_path` and `_rewrite_target_slug_in_body` (the slug-override site)
- `packages/graph-io/src/graph_io/exit_codes.py` — NOT_INITIALIZED constant for D-01
- `packages/graph-io/src/graph_io/store.py` — `read_only_connect()` + `GraphNotInitializedError`
- `packages/graph-io/src/graph_io/queries.py` — path-based and name-based query primitives for D-03 (suggest: `find(name=X)`, `describe_path(path=Y)`)
- `packages/workspace-io/src/workspace_io/paths.py` — `graph_dir(workspace)` for resolving DB path
- Phase 39's URI → slug derivation helper (file location TBD by Phase 39 planner / executor; Phase 40 planner reads it before extracting/duplicating)

### Frontmatter Format Reference
- Existing pages under `wiki/` already have YAML frontmatter (slug, title, etc.) — planner reviews an existing entity-backed page like `wiki/packages/graph-io/overview.md` to see current frontmatter shape; `entity_uri` slots in as a new top-level field.

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- `run_ingest_source` 10-step pipeline (`ingest.py:369-533`) — Phase 40 inserts the graph check between step 1 (workspace resolve) and step 3 (source type guess); insertion is additive, not a refactor.
- `_route_target_path(wiki, page_type, slug)` (`ingest.py:93`) — slug routing logic. D-04's override happens BEFORE this call by replacing the LLM-guessed slug with the canonical one.
- `_rewrite_target_slug_in_body(text, canonical_slug)` (`ingest.py:116`) — already exists to rewrite the `target_slug:` line in the LLM output to match the resolved canonical slug. D-04 piggybacks: when the override fires, `canonical_slug` is the URI-derived value.
- `IngestResult` dataclass (`ingest.py:54`) — Phase 40 should consider adding `entity_uri: str | None = None` as a new field so callers (MCP host, tests) can observe the graph-match outcome without reading the page file.
- Phase 39's URI → slug helper (TBD) — D-04 calls into it.

### Established Patterns
- Connection lifetime: open after workspace resolve, close in `finally`. Phase 37/39 precedent.
- Error surfacing: agent CLI commands use `typer.Exit(code=N)` for non-zero exits (cli.py `ingest_source` Typer command at line 565). NOT_INITIALIZED bubbles up the same way.
- LLM output post-processing: `_parse_ingestor_response` → `_rewrite_target_slug_in_body` chain already exists; D-04's slug override threads in cleanly.
- Frontmatter writing: existing ingestor LLM output already includes frontmatter; D-06 adds one field.

### Integration Points
- Pre-step: graph-existence check → NOT_INITIALIZED error path (D-01/D-02) → CLI exit before any LLM call.
- After workspace resolve: open read-only conn → run path lookup → run name fallback → derive canonical_uri.
- After LLM call: if canonical_uri set, override LLM's target_slug; write `entity_uri` frontmatter to the page body.
- `IngestResult` includes the new `entity_uri` field (when set).
- MCP `wiki_ingest` tool: surfaces `entity_uri` in the WikiIngestOutput Pydantic model so MCP hosts can observe the outcome.

</code_context>

<specifics>
## Specific Ideas

- D-02 exact stderr text: `error: graph-io not initialized for this workspace. Run 'graph-wiki-agent graph build' (or 'cg update') to initialize, then retry.`
- D-07 code comment text (suggested): `# URI-drift limitation (INGESTOR-03 / Phase 40):` followed by a 2-3 sentence paragraph noting that orphaned entity_uri values on package rename are NOT auto-migrated; v1.8 reconciliation tracks this.
- D-03 multi-match suggestion: if name-fallback returns multiple matches, log `[ingest: name '<n>' matches multiple graph nodes (<URI1>, <URI2>, ...); falling back to LLM-guessed slug]` to stderr and treat as the no-match path (D-05).
- D-06 frontmatter line position: add `entity_uri` immediately after `target_slug` in the page frontmatter, so the canonical identity is co-located with the slug it derived.
- For tests: add at least two unit tests — one with a path-matching source (asserts slug-override + `entity_uri` written) and one with no match (asserts LLM-guessed slug + `entity_uri: null`).

</specifics>

<deferred>
## Deferred Ideas

- **URI-drift reconciliation (auto-rewrite orphaned entity_uri values)** — Deferred to v1.8 per INGESTOR-03. Phase 40 documents the limitation; v1.8 designs the solution.
- **Routing non-entity sources to a separate vault subtree** — Considered (D-05 alternative); rejected for v1.7 (expands scope; would surprise users). Revisit if downstream pain emerges.
- **Refusing to ingest non-entity sources** — Considered (D-05 alternative); rejected (would break ADR / docs / notes ingest).
- **Verbose `entity_name` + `entity_kind` frontmatter fields** — Considered (D-06 alternative); rejected for redundancy. URI is the single source of truth.
- **Sketching v1.8 reconciliation strategy in the documentation** — Considered (D-08 alternative); rejected to keep v1.8's design space open.
- **Multi-match disambiguation via LLM prompt re-routing** — Could ask the LLM to pick among candidates. Speculative; not worth v1.7 complexity. Refuse + fall back is the cheap correct path.
- **`run_ingest_work_item` graph consultation** — Listed in Claude's Discretion. If work-items are user-authored notes (not derived from source files), graph consultation likely makes no sense. Planner verifies.
- **MCP `wiki_ingest` tool surfacing `entity_uri` in output** — Listed in code_context as a natural add; planner picks whether to include it in this phase or defer.
- **Plugin (`plugins/graph-wiki/`) ingest path coupling to graph-io** — v1.8 Future Requirement per REQUIREMENTS.md.

</deferred>

---

*Phase: 40-ingestor-consumes-graph-io*
*Context gathered: 2026-05-26*
