# Phase 40: Ingestor Consumes graph-io - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md — this log preserves the alternatives considered.

**Date:** 2026-05-26
**Phase:** 40-ingestor-consumes-graph-io
**Areas discussed:** NOT_INITIALIZED error UX, What 'canonical entity existence check' means, Behavior when source has no matching graph entity, URI-drift documentation site

---

## NOT_INITIALIZED error UX

### Q1: Exit code

| Option | Description | Selected |
|--------|-------------|----------|
| Reuse `graph_io.exit_codes.NOT_INITIALIZED` | Same code cg already returns for this condition. | ✓ |
| Define new agent-side exit code | Separate agent vs cg exit-code policy. | |
| Exit 1 (generic) | Loses structured signal. Diverges from SC#2's "clear NOT_INITIALIZED error." | |

**User's choice:** Reuse `graph_io.exit_codes.NOT_INITIALIZED` (Recommended)

### Q2: Error message text

| Option | Description | Selected |
|--------|-------------|----------|
| Suggest `graph-wiki-agent graph build` (or `cg update`) | Actionable; surfaces Phase 38's command. | ✓ |
| Minimal error | Cheaper; user must know what to do. | |
| Verbose error with full context | Tutorial; longer. | |

**User's choice:** Suggest `graph build` / `cg update` (Recommended)
**Notes:** Agent-native command first, cg as fallback hint.

---

## What 'canonical entity existence check' means

### Q1: What does `run_ingest_source` query for

| Option | Description | Selected |
|--------|-------------|----------|
| Lookup by source path | Most precise; works for files in a package. | |
| Lookup by guessed name from filename | Catches more cases (docs about a class). | |
| Both — path first, name fallback | Max coverage; two query patterns to maintain. | ✓ |

**User's choice:** Both — path first, fall back to name
**Notes:** Covers package files (path) AND docs ABOUT named entities (name).

### Q2: Action when match found

| Option | Description | Selected |
|--------|-------------|----------|
| Override LLM's target_slug with canonical URI-derived slug | Graph is ground truth; LLM provides body. | ✓ |
| Pass canonical URI to LLM as context; LLM picks slug | More flexible; loses ground-truth guarantee. | |
| Just log canonical URI in IngestResult, no routing change | Defeats SC#1's intent. | |

**User's choice:** Override with canonical slug (Recommended)
**Notes:** Eliminates slug drift between scanner-created and ingestor-created pages.

---

## Behavior when no graph entity matches

### Q1: No-match behavior

| Option | Description | Selected |
|--------|-------------|----------|
| Proceed with LLM-guessed slug + `entity_uri: null` | Permissive; preserves today's behavior for non-entity sources. | ✓ |
| Refuse to ingest non-entity sources | Strictest; would break ADR/docs ingest. | |
| Route to `notes/` subtree with `page_type: free_form` | Expands scope; new routing. | |

**User's choice:** Proceed with LLM-guessed slug + `entity_uri: null` (Recommended)
**Notes:** Non-entity sources (docs, ADRs, notes) ingest normally.

### Q2: Frontmatter field for entity-backed pages

| Option | Description | Selected |
|--------|-------------|----------|
| `entity_uri: pkg:org/repo/<name>` | Full URI; machine-readable; matches schema vocabulary. | ✓ |
| `entity_name` + `entity_kind` (two fields) | Human-readable; loses org/repo context. | |
| Both URI and name/kind fields | Redundant; verbose. | |

**User's choice:** `entity_uri: pkg:...` (Recommended)
**Notes:** Single field, full URI, grep-friendly.

---

## URI-drift documentation site

### Q1: Where to document

| Option | Description | Selected |
|--------|-------------|----------|
| BOTH code comment in `ingest.py` AND `40-01-PLAN.md` | Satisfies INGESTOR-03's "AND" wording verbatim. | ✓ |
| Code comment only | Diverges from INGESTOR-03. | |
| Code comment + REQUIREMENTS.md v1.8 entry | Most discoverable; expands scope to requirements doc. | |

**User's choice:** Both code comment AND phase plan (Recommended)

### Q2: How much to say about v1.8

| Option | Description | Selected |
|--------|-------------|----------|
| Just the limitation, not the solution | Don't pre-commit v1.8's design. | ✓ |
| Limitation + sketched solution | Pre-commits v1.8 to an approach. | |
| Limitation + explicit "do not solve here" non-goal | Strong fence; useful for maintainers. | |

**User's choice:** Just the limitation (Recommended)
**Notes:** v1.8's design space stays open.

---

## Claude's Discretion

- Connection lifetime (suggest mirror Phase 39 D-05)
- Whether `run_ingest_work_item` needs graph consultation
- Whether to extract URI → slug derivation into shared helper (recommended)
- Multi-match disambiguation for name fallback (suggest: refuse override, fall through to no-match path with stderr warning)
- Exact stderr error wording
- Re-ingest behavior: write `entity_uri` on every successful ingest

## Deferred Ideas

- URI-drift reconciliation — v1.8 per INGESTOR-03
- Routing non-entity sources to separate vault subtree — out of scope for v1.7
- Refusing to ingest non-entity sources — would break ADR/docs ingest
- Verbose `entity_name`/`entity_kind` fields — redundancy
- Sketching v1.8 solution in docs — keep design space open
- Multi-match LLM disambiguation — speculative
- `run_ingest_work_item` graph consultation — planner verifies
- MCP `wiki_ingest` surfacing `entity_uri` in output — planner picks
- Plugin ingest path coupling — v1.8 Future Requirement
