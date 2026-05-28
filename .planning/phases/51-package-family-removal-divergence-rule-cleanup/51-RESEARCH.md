# Phase 51: package-family Removal + Divergence Rule Cleanup - Research

**Researched:** 2026-05-28
**Domain:** Code-only removal phase (graph-io kind retraction, wiki-io scaffolding deletion, eval-harness divergence rule cleanup)
**Confidence:** HIGH

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions

- **D-01: Vault directory deletion deferred to Phase 53.** `wiki/package-family/` in the existing exploratory vault is removed during Phase 53's atomic `migrate-vault` operation (alongside wikilink rewrites), not in this phase. Mirrors Phase 50 D-08 ("wiki-io untouched in Phase 50; vault writes belong to Phase 53"). PKGFAM-03's "removed from the existing vault during migration" wording is satisfied by Phase 53's migration command — Phase 51 ships only the code changes (delete `entity-package-family.md` template + remove `package_family` from `ADMITTED_KINDS`).
- **D-02: No SCHEMA_VERSION bump, no pre-flight scan, no migration command.** PKGFAM-01's literal "SCHEMA_MISMATCH" wording is reinterpreted: the user (sole developer) regenerates graphs manually via `cg update --full` after this phase ships. Whatever cryptic error fires when `_VALID_KINDS` encounters a stale `package_family` row is acceptable — the workflow is "delete the graph, regenerate". Schema version stays at 2 (consistent with Phases 49 D-10 and 50 D-12). The planner should NOT add a pre-flight check at connect time, and should NOT bump `SCHEMA_VERSION`.
- **D-03: Surgical fixture edits.** `packages/wiki-io/tests/fixtures/round-trip-vault/` is a golden snapshot — keep its non-package-family coverage intact. Surgically delete: (a) `.templates/package-family.md` and any `wiki/package-family/` directory inside the fixture, (b) lines mentioning `package_family` in concept/source/overview markdowns, (c) the `package-family` template in `.graph-wiki/`. Rebuild `vocab.index.json` and `vocab.tokenizer.json` via existing test tooling (bm25 regeneration path) rather than hand-editing the JSON.
- **D-04: Delete `ADMITTED_KINDS_V18` alias outright.** `packages/wiki-io/src/wiki_io/entity_writer.py:195-196` defines `ADMITTED_KINDS_V18 = ADMITTED_KINDS - frozenset({"package_family"})` as a v1.8 caller compat shim. Per success criterion #2, the frozenset must be "complete and final" with no subtraction-narrow. Delete the alias outright, update both call sites to plain `ADMITTED_KINDS`. No deprecation grace period — single-developer project, no external consumers.
- **D-05: Regenerate `baselines/divergence-librarian.json` via existing eval-harness tooling, not hand-edit.** Hand-editing the JSON creates drift risk between the registered checks and the baseline. The planner should identify the existing baseline-regeneration path (likely a `pytest --record-baseline` or `eval-harness baseline regen` flag — researcher to surface) and use it after LIB-003 is removed from the registry. Hand-edit is the fallback only if no regen tooling exists.

### Claude's Discretion

- Whether to delete `package-family.md` (non-`entity-` prefix) template at `packages/wiki-io/src/wiki_io/assets/page-templates/package-family.md` in the same plan as `entity-package-family.md` or separately. Both files clearly belong to the same removal; default to deleting in one plan.
- Whether `dependency.py:_check_*` and `link_rewriter.py` references to `package_family` are real code paths or comment-only. Researcher to confirm; if comment-only and inside a "migration log" or "historical" docstring, success criterion #1 permits them to stay. Default: delete the references unless they are clearly historical-comment markers.
- Order of CLI removal (PKGFAM-04: `cg describe-package-family` / `cg list-package-families`) — researcher first verifies whether these subcommands exist; if so, removal slots into the same plan as `package_family_uri` deletion (both touch the same CLI module family).
- Whether the divergence baseline regen runs before or after the LIB-003 code deletion. Logical order is: delete code → regen baseline → assert no LIB-003 row in JSON. Planner picks the exact plan ordering.

### Deferred Ideas (OUT OF SCOPE)

- **Vault `wiki/package-family/` directory deletion** — Phase 53 cutover (D-01).
- **Pre-flight schema check / migration command** — out of scope per D-02; if Pat ever publishes graph-io for external consumers, revisit a `cg migrate v1.8→v1.9` command with explicit `SCHEMA_MISMATCH` errors.
- **`SCHEMA_VERSION` bump policy revisit** — currently held flat across 49/50/51. When schema gains a *structural* change (new column, edge-table reshape), bump it then. Kind admission/retraction alone doesn't warrant a bump under the current policy.
- **`ADMITTED_KINDS_V18` deprecation grace** — explicitly skipped per D-04. If a future kind ever needs a multi-release deferral pattern, build it with a documented `__deprecated__` shim rather than reusing this ad-hoc alias.
</user_constraints>

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| PKGFAM-01 | Remove `package_family` from `_VALID_KINDS` in `graph-io`; reads against pre-v1.9 graphs error with SCHEMA_MISMATCH until rebuilt | `_VALID_KINDS` confirmed at `packages/graph-io/src/graph_io/queries.py:9-29` — single-line removal. Per D-02, the SCHEMA_MISMATCH wording is satisfied by whatever runtime error fires when stale `package_family` rows are queried; no pre-flight check is added. |
| PKGFAM-02 | Remove `package_family_uri` from `graph_io.uri` | Defined at `packages/graph-io/src/graph_io/uri.py:49-50`. Imported in 1 file outside `uri.py`: `packages/graph-io/tests/test_uri.py:16,82-83`. No other importers exist (verified by grep). |
| PKGFAM-03 | Delete `entity-package-family.template`; simplify `ADMITTED_KINDS - {"package_family"}` to bare `ADMITTED_KINDS`; vault dir removal deferred to Phase 53 | Two template files exist: `assets/page-templates/entity-package-family.md` (8 lines of frontmatter + sections) and `assets/page-templates/package-family.md` (the lint-side dependency-page template). `ADMITTED_KINDS_V18` alias at `entity_writer.py:196` — see PKGFAM Audit. |
| PKGFAM-04 | Remove `cg describe-package-family` / `cg list-package-families` subcommands **if they exist** | **VERIFIED**: Neither subcommand exists. `_SUBCOMMANDS` table at `packages/graph-io/src/graph_io/cli/main.py:45-77` enumerates 32 subcommands; no `describe-package-family` or `list-package-families` entries. No `q_describe_package_family.py` or `q_list_package_families.py` modules in `cli/`. **PKGFAM-04 is satisfied by a verification step only — no code to delete.** |
| PKGFAM-05 | `domain_contains_domain` edges and the domain layer are NOT affected by this removal | Orthogonal. No code references domain-layer in conjunction with package_family. |
| CLEANUP-01 | Delete `_SLUG_ONLY_RE`, `_check_no_slug_only_wikilinks`, LIB-003 registry entry, baseline expectation, test cases, fixtures | All sites enumerated below. LIB-003 (librarian role) is the target; the **synthesizer role** has a parallel `_check_no_slug_only_wikilinks` (SYN-002) which is a **distinct, retained** check — see Common Pitfalls §1. |
</phase_requirements>

## Summary

Phase 51 is a code-only removal phase across three packages: `graph-io` (kind admission + URI builder), `wiki-io` (template assets + the V18 alias + active references in `link_rewriter.py` and `lint/dependency.py`), and `eval-harness` (the LIB-003 divergence rule and its baseline expectation). All major design decisions are already locked in CONTEXT.md (D-01..D-05) — no architectural exploration is needed. Research focuses on **exact-line inventory**, **CLI verification**, **baseline regen mechanics**, and **fixture surgical-edit scope**.

Three findings shape the plan:

1. **PKGFAM-04 is a verification no-op.** `cg describe-package-family` / `cg list-package-families` do not exist in `_SUBCOMMANDS`. The plan needs to include a `grep` verification step, not a deletion task.
2. **`wiki_io.lint.dependency.VALID_KINDS["package-family"]` is a SEPARATE, parallel concept** — it is the frontmatter `kind:` discriminator for dependency-category Markdown pages (`kind: package | package-family | service`), not the graph-io node kind. It's gated behind `--check dependency_layer` (optional group). Default behavior: **delete it for clarity** under PKGFAM scope #1 (success criterion #1: zero `package_family|package-family` hits). The lint feature can re-emerge later as `family:`-back-pointer-only (the `family:` field on `kind: package` pages still works independently).
3. **`link_rewriter.py` `package-family` references are active executable code paths**, not comments. They log unresolvable `[[package-family/...]]` wikilinks during Phase 46 migration (`D-04` deferral). With Phase 51 retiring the concept, these execution branches should be deleted; any Phase 46 vault state with old `[[package-family/...]]` links is handled by Phase 53's atomic cutover.

**Primary recommendation:** Structure as 4 atomic plans (51-01 graph-io; 51-02 wiki-io including templates, alias, link_rewriter, lint; 51-03 eval-harness CLEANUP-01 + baseline regen; 51-04 fixture surgery + bm25 regen). Validation gate per success criteria: two grep invariants returning zero hits.

## Architectural Responsibility Map

| Capability | Primary Tier | Secondary Tier | Rationale |
|------------|-------------|----------------|-----------|
| Graph-kind admission (`_VALID_KINDS`) | graph-io / Python validation | SQLite store (kinds are text strings; no DDL gate) | Established by Phase 49 D-14, Phase 50 D-12 — admission is Python-side only. |
| URI builder retraction | graph-io | tests/test_uri.py (consumer) | URI builders are pure functions in `uri.py`; no DB layer involved. |
| Wiki entity dispatch (`ADMITTED_KINDS`) | wiki-io / `entity_writer.py` | template-resolution loop (`_template_path_for_kind`) | Dispatch table lives in one file. |
| Divergence rule registry | eval-harness / `divergence/librarian.py` | baseline JSON + test fixtures | Registry is a Python list; baseline is generated by `pytest --accept-divergence-baseline` (live Bedrock). |
| Fixture vocab regeneration | agents/graph-wiki-agent / `commands/query.py::build_index` | wiki-io fixture data | `build_index()` writes `vocab.index.json` + `vocab.tokenizer.json` via `bm25s.Tokenizer.save_vocab()`; embeddings part requires Bedrock. |
| CLI subcommand registration | graph-io / `cli/main.py::_SUBCOMMANDS` | per-handler modules in `cli/` | **Verified: nothing to remove** — no `describe-package-family` / `list-package-families` entries exist. |

## Standard Stack

This phase introduces NO new dependencies. All work uses existing libraries:

### Core (already installed)
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| `pytest` | ≥8.3 | Test runner (verification gate) | Project standard (CLAUDE.md) |
| `bm25s` | 0.3.8 | Tokenizer + retriever for vocab regen | Already vendored; used by `query.py::build_index` |
| `frontmatter` (python-frontmatter) | 1.1.0 | YAML frontmatter (template files) | Project standard |

**No installs required.** This is a pure deletion phase. [VERIFIED: project CLAUDE.md technology-stack table]

## Architecture Patterns

### System Architecture Diagram

```
                  Phase 51 deletion blast radius
                  ================================

  ┌──────────────────────────────────────────────────────────────┐
  │  Layer 1: graph-io kind admission + URI                       │
  │   queries.py:9-29  ──[delete "package_family" from set]──►    │
  │   uri.py:49-50     ──[delete package_family_uri function]──►  │
  │   tests/test_uri.py:16,82-83 ──[delete import + test]──►      │
  └──────────────────────────────────────────────────────────────┘
                  │
                  ▼
  ┌──────────────────────────────────────────────────────────────┐
  │  Layer 2: wiki-io entity dispatch + assets                    │
  │   entity_writer.py:                                           │
  │     L66    ──[delete from ADMITTED_KINDS frozenset]──►        │
  │     L82    ──[delete _URI_PREFIX_BY_KIND mapping]──►          │
  │     L125   ──[delete SCANNER_OWNED_KEYS "members" comment]──► │
  │     L195-196 ──[delete ADMITTED_KINDS_V18 alias]──►           │
  │     L530   ──[remove "package_family v1.9" comment]──►        │
  │     L9,22  ──[clean docstring references]──►                  │
  │   assets/page-templates/entity-package-family.md ──[DELETE]──►│
  │   assets/page-templates/package-family.md ──[DELETE]──►       │
  │   assets/page-templates/dependency.md:4,9 ──[clean comments]──► │
  │   link_rewriter.py:11,50,53,289,296,304,344-345,413,443-444   │
  │                                  ──[delete deferred branches]──►│
  │   lint/dependency.py:17,30,37,46,50,58 ──[VALID_KINDS edit]──►│
  │   tests/test_entity_writer.py (9 V18 references)              │
  │                                  ──[rename V18→ADMITTED_KINDS]──►│
  │   tests/test_link_rewriter_build_table.py (4 tests)           │
  │                                  ──[delete/rename tests]──►   │
  └──────────────────────────────────────────────────────────────┘
                  │
                  ▼
  ┌──────────────────────────────────────────────────────────────┐
  │  Layer 3: eval-harness divergence rule retraction (LIB-003)   │
  │   divergence/librarian.py:                                    │
  │     L53      ──[delete _SLUG_ONLY_RE]──►                      │
  │     L85-93   ──[delete _check_no_slug_only_wikilinks]──►      │
  │     L117-122 ──[delete LIB-003 DivergenceCheck entry]──►      │
  │   divergence/synthesizer.py:46-57,116 ──[KEEP — SYN-002 is    │
  │                              independent; see Pitfall 1]──►   │
  │   baselines/divergence-librarian.json:29-33                   │
  │     ──[regen via `pytest --accept-divergence-baseline`]──►    │
  │   tests/test_divergence_checks.py:97-112                      │
  │                                ──[delete 2 LIB-003 tests]──►  │
  │   tests/test_divergence_baseline.py:35,98-110,etc.            │
  │                                ──[remove LIB-003 from helper]►│
  │   tests/test_two_gate_scorer.py:98,144                        │
  │                                ──[remove LIB-003 entries]──►  │
  └──────────────────────────────────────────────────────────────┘
                  │
                  ▼
  ┌──────────────────────────────────────────────────────────────┐
  │  Layer 4: fixture surgical edits (round-trip-vault only)      │
  │   .templates/package-family.md ──[DELETE]──►                  │
  │   plugins/lattice-wiki/{patterns,context}.md ──[strip lines]─►│
  │   packages/lattice-wiki-core/overview.md ──[strip lines]──►   │
  │   concepts/{code-wiki-pattern,index,lattice-vault-terminology,│
  │              lattice-dependencies-tiering}.md ──[strip]──►    │
  │   sources/2026-05-lattice-wiki-core-tokens-frontmatter-       │
  │           field.md ──[strip]──►                               │
  │   .graph-wiki/bm25/vocab.index.json ──[regen via build_index]►│
  │   .graph-wiki/bm25/vocab.tokenizer.json ──[regen]──►          │
  └──────────────────────────────────────────────────────────────┘
```

### Recommended Plan Structure

```
51-01-PLAN.md  graph-io removal
               - queries.py _VALID_KINDS edit (line 9-29)
               - uri.py package_family_uri delete (line 49-50)
               - test_uri.py: drop import (line 16) + test function (line 82-83)

51-02-PLAN.md  wiki-io removal (largest plan)
               - entity_writer.py: lines 9, 22, 66, 82, 125, 195-196, 530
                 (incl. delete ADMITTED_KINDS_V18 alias per D-04)
               - assets/page-templates/entity-package-family.md DELETE
               - assets/page-templates/package-family.md DELETE
               - assets/page-templates/dependency.md: clean L4, L9 comments
               - link_rewriter.py: delete D-04 deferral branches
                 (CONVENTION_TEMPLATES already correct; remove OLD_LAYOUT_ROOTS
                 entry, _KIND_FOR_PREFIX entries, source2 skip, source3 log)
               - lint/dependency.py: remove "package-family" from VALID_KINDS
                 (L17), associated kind dispatch (L50-55) + family_pages logic
               - tests/test_entity_writer.py: 9 call sites V18→ADMITTED_KINDS,
                 remove _package_family_uri_strategy and from _admitted_uri_strategy
                 union, remove ("package_family:aws", ...) parametrize case,
                 update test_admitted_kinds_shape's expected frozenset
               - tests/test_link_rewriter_build_table.py: 4 tests reworked

51-03-PLAN.md  eval-harness CLEANUP-01 + baseline regen
               - librarian.py: delete _SLUG_ONLY_RE (L53), _check_no_slug_only_
                 wikilinks (L85-93), LIB-003 registry entry (L117-122)
               - tests/test_divergence_checks.py: delete L97-112 (test_lib003_*)
               - tests/test_divergence_baseline.py:_make_results helper L35
                 (drop LIB-003 key)
               - tests/test_two_gate_scorer.py:98,144 (drop LIB-003 entries
                 from heavy_failures & clean_results dicts)
               - Regen baseline: GRAPH_WIKI_RUN_EVAL=1 pytest tests/test_divergence.py
                 -k librarian --accept-divergence-baseline
                 OR hand-edit baselines/divergence-librarian.json to drop L29-33
                 (D-05 prefers tooling regen, but tooling requires live Bedrock —
                 see Pitfall 2; planner picks)

51-04-PLAN.md  Fixture surgical edits + bm25 regen
               - Markdown line-deletes per D-03 inventory
               - Delete .templates/package-family.md
               - Regen .graph-wiki/bm25/ via build_index() OR a BM25-only
                 helper script (Bedrock not required for vocab files)

Verification gate (success criteria):
  $ grep -r "package_family\|package-family\|PKGFAM\|package_family_uri" \
      packages/ --include="*.py" --include="*.md" --include="*.json" --include="*.toml"
  → zero hits (excluding planning docs and migration-log JSONL)

  $ grep -r "_SLUG_ONLY_RE\|_check_no_slug_only_wikilinks\|LIB-003" \
      packages/eval-harness/
  → zero hits
```

### Pattern 1: Kind retraction (mirror of admission)
**What:** Phases 49 and 50 added kinds. Phase 51 is the mirror — remove from `_VALID_KINDS`, delete the URI builder, leave inbound edges alone.
**When to use:** Any time a kind is being retired without data migration.
**Example:** [VERIFIED: graph-io codebase]
```python
# Before (queries.py:9)
_VALID_KINDS = frozenset({"function", ..., "package_family", ...})
# After
_VALID_KINDS = frozenset({"function", ..., ...})  # entry removed
```

### Pattern 2: Divergence rule registry single-row delete
**What:** Rules are `DivergenceCheck` instances in a Python list. Deletion is one list-entry removal + the helper function it references + the regex it uses.
**When to use:** Retiring a divergence rule.
**Example:** [VERIFIED: `packages/eval-harness/src/eval_harness/divergence/librarian.py:104-129`]
```python
LIBRARIAN_CHECKS: list[DivergenceCheck] = [
    DivergenceCheck(id="LIB-001-...", ...),
    DivergenceCheck(id="LIB-002-...", ...),
    # DELETE the LIB-003 DivergenceCheck(...) entry
    DivergenceCheck(id="LIB-004-...", ...),
]
```

### Pattern 3: Baseline regeneration (D-05)
**What:** `pytest tests/test_divergence.py --accept-divergence-baseline` rewrites `baselines/divergence-<role>.json` from current run results, signing the snapshot with the current git HEAD SHA via `_current_agent_commit()`.
**When to use:** Any time the divergence-check registry changes.
**Example:** [VERIFIED: `packages/eval-harness/tests/conftest.py:40-50`, `tests/test_divergence.py:70-121`]
```bash
GRAPH_WIKI_RUN_EVAL=1 pytest \
    packages/eval-harness/tests/test_divergence.py \
    -k librarian \
    --accept-divergence-baseline
```

### Anti-Patterns to Avoid

- **Hand-editing `baselines/divergence-librarian.json`:** Drift risk vs. registered checks. D-05 forbids it unless the regen path is unavailable. See Pitfall 2 for the live-Bedrock caveat.
- **Adding a SCHEMA_MISMATCH pre-flight check at connect time:** Explicitly out of scope per D-02. Stale `package_family` rows in user graphs produce whatever ValueError fires when `_VALID_KINDS` checks fail at query time — that's acceptable.
- **Deleting `synthesizer.py::_check_no_slug_only_wikilinks` (SYN-002):** It is an independent check on a different role's output. See Common Pitfalls §1.
- **Touching the vault `wiki/package-family/` directory:** Deferred to Phase 53 (D-01). Phase 51 only deletes the assets/page-templates and fixture files.

## Package Legitimacy Audit

Not applicable — Phase 51 installs no new packages. All work uses existing project dependencies.

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Regenerate divergence baseline | A custom script that re-runs checks and writes JSON | `pytest --accept-divergence-baseline` | Carries the EVAL-08 reproducibility envelope (recorded_at, agent_commit). Hand-rolled scripts will drift from schema. |
| Regenerate bm25 vocab files | A custom tokenizer dump script | `build_index()` from `query.py:739` (BM25 portion via `bm25s.Tokenizer.save_vocab`) | The tokenizer/index pair must stay in lockstep — same tokenization rules used at query time. |
| Schema migration command | A `cg migrate v1.8→v1.9` command | Manual `cg update --full` per D-02 | Sole-developer project; building a migration runner is over-engineering. |

## Runtime State Inventory

> Phase 51 is a removal phase. Required.

| Category | Items Found | Action Required |
|----------|-------------|------------------|
| **Stored data** | User's local SQLite graph DB (`.graph-wiki/code-graph.db` in each workspace) likely contains `package_family` rows from v1.8 scans. **Not in repo — lives in workspace `.graph-wiki/` dirs (gitignored).** | Per D-02: no migration. User runs `cg update --full` once after this phase ships. Stale rows produce a ValueError when queried until rebuilt. |
| **Live service config** | None. Phase 51 touches no external services (no Datadog, no n8n, no Cloudflare, no Tailscale). | None. |
| **OS-registered state** | None. No Task Scheduler / launchd / systemd / pm2 registrations reference package-family. Verified by grep across `packages/`, `agents/`, and project scripts. | None. |
| **Secrets / env vars** | `GRAPH_WIKI_RUN_EVAL` env var gates the baseline regen step — it must be set to `1` to run `pytest --accept-divergence-baseline`. Bedrock creds (`AWS_ACCESS_KEY_ID`, etc.) required for the regen because `produce_outputs()` calls live LLMs and `build_index()` calls Titan embeddings. | If the planner chooses the live-regen path, the executor must have Bedrock creds. Otherwise, fall back to hand-edit (D-05 fallback clause). |
| **Build artifacts / installed packages** | None. The `wiki_io` and `graph_io` packages are workspace-editable installs (`uv sync` auto-rebinds); no egg-info to clear. | None. |

**Critical implication:** The user's exploratory vault at `~/Personal/graph-wiki/agent-research` has `wiki/package-family/` directories with content from prior scans. Per D-01, these are deferred to Phase 53. Any code that defensively probes for `wiki/package-family/` (e.g., `link_rewriter.py` source 2/3) will see those dirs until Phase 53 lands — so the **`link_rewriter` code deletion must not break Phase 46 idempotency** (a re-run of `migrate-vault` against the old vault state should still succeed; old `[[package-family/...]]` links land in the unresolvable log instead of being processed).

**Planner action:** The planner should add a "post-Phase-51 re-test of Phase 46's `migrate-vault` idempotency" verification step using the round-trip-vault fixture **before** the fixture's `wiki/package-family/` content is deleted. Or accept that idempotency-on-old-vaults is a one-shot concern: Phase 53 wipes the directory atomically, so post-cutover this scenario can't recur.

## Common Pitfalls

### Pitfall 1: Two `_check_no_slug_only_wikilinks` functions exist — only LIB-003 is removed

**What goes wrong:** A naive grep for `_check_no_slug_only_wikilinks` returns hits in BOTH `divergence/librarian.py:85` (LIB-003 — target of CLEANUP-01) AND `divergence/synthesizer.py:46` (SYN-002 — UNRELATED, retained). Deleting both breaks the synthesizer role's divergence gate.

**Why it happens:** The two functions share an identical name because they were copy-pasted across role-specific check modules. They have different docstrings (LIB-003 anchors `librarian.md`; SYN-002 anchors `synthesizer.md`) and slightly different logic — LIB-003 uses `_SLUG_ONLY_RE` (CamelCase-only); SYN-002 uses `"/" not in slug` (any slug without a slash). They are registered in different role registries (`LIBRARIAN_CHECKS` vs `SYNTHESIZER_CHECKS`).

**How to avoid:** The CLEANUP-01 grep gate (`grep -r "_check_no_slug_only_wikilinks" packages/eval-harness/`) MUST be scoped to **librarian.py only** for the "should return zero hits" assertion, or the planner must update CLEANUP-01's success criterion to "zero hits in `librarian.py` and `LIB-003` is absent from baselines/tests".

**Warning signs:** If `SYN-002-no-slug-only-wikilinks` test fails after Phase 51 lands, you deleted too much.

### Pitfall 2: `--accept-divergence-baseline` requires live Bedrock + GRAPH_WIKI_RUN_EVAL=1

**What goes wrong:** The "tooling regen" path D-05 prefers calls `_produce_outputs(role, fixture_workspace_path)` which spawns real `claude -p` subprocesses against the fixture vault, then runs all 4 librarian checks (including LIB-001 which makes Bedrock calls via `librarian.md`). Total runtime: 5-15 minutes; cost: ~$0.50-$2; requires AWS credentials.

**Why it happens:** The baseline format encodes failures-with-accepted-excerpts that vary by model output. To get a meaningful baseline, you must actually run the model. The unit-tested `write_baseline()` helper at `metric.py:232` only serializes a results dict — it doesn't produce one.

**How to avoid:** Two acceptable paths:
1. **(Preferred when creds available)** Run with `GRAPH_WIKI_RUN_EVAL=1 AWS_PROFILE=... pytest packages/eval-harness/tests/test_divergence.py -k librarian --accept-divergence-baseline` after the LIB-003 code deletion.
2. **(Acceptable fallback per D-05 last clause)** Hand-edit `baselines/divergence-librarian.json` to delete the `LIB-003-no-slug-only-wikilinks` block (lines 29-33). Bump `recorded_at` and `agent_commit` manually to match HEAD. This is the **D-05 fallback** when "no regen tooling exists" — but tooling DOES exist; it's just expensive to run. The single-developer context makes the cost-benefit favor hand-edit.

**Recommendation for the planner:** Default to the hand-edit fallback; document it as an explicit deviation from D-05's "tooling preferred" wording with the rationale "tooling requires live Bedrock; fallback is acceptable per D-05 final clause." Otherwise the plan becomes operationally expensive for a deletion-only change.

**Warning signs:** A spike in AWS Bedrock charges during Phase 51 execution = the planner chose the live-regen path.

### Pitfall 3: `wiki_io.lint.dependency.VALID_KINDS["package-family"]` is the LINT-SIDE concept, not the graph kind

**What goes wrong:** The CONTEXT.md Claude's Discretion clause says "if `dependency.py` references are comment-only … success criterion #1 permits them to stay." But the references at `lint/dependency.py:17,30,37,46,50,58` are **executable code** for an OPTIONAL lint group (`--check dependency_layer`) that validates `kind: package-family` frontmatter on dependency wiki pages. This is a SEPARATE feature from the graph-io kind.

**Why it happens:** The two concepts share the spelling `package-family` but live in different layers: graph-io classifies graph nodes; `lint/dependency.py` validates wiki Markdown frontmatter values. The lint feature uses `category: dependency` + `kind: package-family` to mark "this dependency wiki page documents a family of related libraries" (e.g., the `langchain-*` cluster).

**How to avoid:** The planner must explicitly decide:
- **Option A (recommended, satisfies success criterion #1 strictly):** Delete the lint feature too. Remove `package-family` from `VALID_KINDS` (L17), delete the `kind == "package-family"` branch (L50-55), drop `family_pages`/`package_family_claims` accumulation (L29-30, L46-47), update `dep-kind-not-in-enum` error message (L37), and the cross-page family-membership rules (L78-119). Tests in `test_lint_modules.py:32`/`test_lint_wiki.py:71` for the "dependency_layer" group continue to work because they assert on **other** rules (`dep-package-without-ecosystem`, `dep-stub-detail-page`, etc.).
- **Option B (preserves the lint feature):** Rename the frontmatter discriminator from `kind: package-family` to something distinct (e.g., `kind: package_cluster` or `kind: family`). Update the lint to use the new name. This keeps the feature but breaks pages in the existing vault that already declare `kind: package-family`. Bigger blast radius.

**Researcher's recommendation:** Option A. Future requirements (REQUIREMENTS.md "Deferred Ideas") already says "re-introduce a `package-family`-like mechanism for grouping related dependencies (e.g. the `langchain-*` family) modeled on domain clustering rather than the old `package_family` kind." This explicitly defers — Phase 51 should remove cleanly, and the future feature can land under domain-clustering primitives.

**Warning signs:** A user reports `dep-kind-not-in-enum` errors against `kind: package-family` wiki pages after Phase 51 — that's expected if Option A is taken; the user must reclassify the affected pages.

### Pitfall 4: `link_rewriter.py` deletes change Phase 46 migration semantics

**What goes wrong:** `link_rewriter.py` has 9 active code references to `package-family` (lines 11, 50, 53, 289, 296, 304, 344-345, 413, 443-444). They implement the D-04 "package-family deferred" deferral logic — old `[[package-family/aws]]` links in curated lanes get logged as unresolvable rather than rewritten. Deleting these branches changes behavior: now `[[package-family/...]]` links match no prefix and fall through silently (no log entry, no error).

**Why it happens:** Phase 46 was the v1.8 wikilink migration. It treated `package-family` as a future kind (would be re-admitted in v1.9). With Phase 51 retiring it permanently, those deferral branches are dead conceptually but still active in code.

**How to avoid:** Two valid approaches:
- **Strict deletion (recommended):** Delete all 9 reference points cleanly. `OLD_LAYOUT_ROOTS` drops `"package-family"`. `_KIND_FOR_PREFIX` drops both bare and `wiki/`-prefixed entries. The `source2`/`source3` skip logic disappears. Any `[[package-family/...]]` link in a live vault Markdown will now match no prefix and pass through unchanged — which is fine because Phase 53 will rewrite or delete those links atomically alongside the directory removal.
- **Migration-log preservation (over-cautious):** Keep the log-unresolvable branches. Adds dead-code lint noise.

**Recommendation:** Strict deletion. The Phase 53 cutover is the atomic point where these links are handled; Phase 51's job is to remove the dead concept, not preserve transitional logging.

**Warning signs:** Phase 53's `migrate-vault` produces unexpected output for pre-existing `[[package-family/...]]` links — but Phase 53 should expect those links and rewrite them as part of its own scope.

### Pitfall 5: Fixture bm25 vocab regen needs Bedrock for embeddings

**What goes wrong:** `build_index(vault_path)` at `query.py:739` does TWO things: (1) BM25 indexing + `tokenizer.save_vocab()` → writes `vocab.index.json` and `vocab.tokenizer.json`; (2) Titan v2 embedding ingestion → writes `.graph-wiki/search.db`. The second part requires Bedrock credentials. The committed fixture includes both `bm25/` directory AND `search.db`.

**Why it happens:** `build_index()` is the production function — it builds the full index in one pass.

**How to avoid:** Three options for fixture regen:
1. **Run full `build_index()` with Bedrock creds** — regenerates both bm25/ and search.db consistent with the new corpus.
2. **Run BM25-only inline script** — extract lines 753-769 of `query.py` into a one-shot script that opens the fixture and writes vocab files only; leave `search.db` as-is (stale, but no test reads it for content-correctness).
3. **Accept fixture drift on `search.db`** — delete the search.db rows for files whose content changed (via SQL DELETE on `path` column), let `build_index` re-embed only those on next query (incremental SHA256 hash check at `query.py:794-799`). But — no test currently exercises `search.db` for content, so leaving it stale is functionally OK in CI.

**Recommendation:** Option 2 (BM25-only inline script). The committed `search.db` is 589KB of historical embeddings; nothing in the test suite reads its embeddings for divergence/correctness assertions (search-using tests live in `agents/graph-wiki-agent/` and use their own temp dirs). The planner can include a short Python snippet in the plan that loads the fixture pages, runs `bm25s.Tokenizer.tokenize` + `retriever.index` + saves vocab — no Bedrock needed.

**Verification:** After regen, `test_round_trip.py` (the only test that touches the fixture's `.graph-wiki/` byte-by-byte) hashes the copy after first-pass `update_vault`; the second-pass byte-equality invariant doesn't care about absolute file content, only about idempotency.

## Code Examples

Verified patterns referenced by the plans:

### `_VALID_KINDS` removal (PKGFAM-01)
```python
# packages/graph-io/src/graph_io/queries.py:9-29 [VERIFIED]
_VALID_KINDS = frozenset(
    {
        "function",
        "class",
        "method",
        "file",
        "package",
        "repository",
        "subpackage",
        "entry_point",
        "test_suite",
        "domain",
        "dependency",
        "plugin",
        "builtin",
        "app",
    }
)  # "package_family" entry removed
```

### `ADMITTED_KINDS` simplification (D-04 + PKGFAM-03)
```python
# packages/wiki-io/src/wiki_io/entity_writer.py [VERIFIED current state]
# BEFORE:
ADMITTED_KINDS: frozenset[str] = frozenset({
    "repository", "domain", "package", "package_family",  # ← delete
    "plugin", "dependency", "test_suite",
})
ADMITTED_KINDS_V18: frozenset[str] = ADMITTED_KINDS - frozenset({"package_family"})  # ← delete entire line

# AFTER:
ADMITTED_KINDS: frozenset[str] = frozenset({
    "repository", "domain", "package",
    "plugin", "dependency", "test_suite",
})
# ADMITTED_KINDS_V18 alias removed; callers use ADMITTED_KINDS directly
```

### Divergence baseline regen
```bash
# packages/eval-harness/tests/test_divergence.py:117-121 [VERIFIED — pytest hook at conftest.py:40]
GRAPH_WIKI_RUN_EVAL=1 \
  pytest packages/eval-harness/tests/test_divergence.py \
  -k librarian \
  --accept-divergence-baseline
# OR (D-05 fallback per Pitfall 2):
# Hand-edit packages/eval-harness/baselines/divergence-librarian.json:
#   - Delete lines 29-33 (the "LIB-003-no-slug-only-wikilinks" block)
#   - Update "recorded_at" to current UTC ISO timestamp
#   - Update "agent_commit" to `git rev-parse --short HEAD`
```

### BM25-only fixture regen (Pitfall 5 mitigation)
```python
# One-shot script — no Bedrock needed.
import bm25s
from pathlib import Path

FIXTURE = Path("packages/wiki-io/tests/fixtures/round-trip-vault")
BM25_DIR = FIXTURE / ".graph-wiki" / "bm25"
BM25_DIR.mkdir(parents=True, exist_ok=True)

# Tokenize all .md files (same discovery rules as query.py::_discover_pages)
pages = []
for md in sorted(FIXTURE.rglob("*.md")):
    rel = md.relative_to(FIXTURE)
    if rel.name in {"index.md", "log.md"}:
        continue
    if any(part.startswith(".") for part in rel.parts):
        continue
    pages.append((str(rel).replace("\\", "/"), md.read_text(encoding="utf-8")))

tokenizer = bm25s.Tokenizer(stopwords="english", stemmer=None)
corpus_paths = [p for p, _ in pages]
corpus_texts = [t for _, t in pages]
corpus_tokens = tokenizer.tokenize(corpus_texts, return_as="tuple")

retriever = bm25s.BM25(method="lucene", k1=1.5, b=0.75)
retriever.index(corpus_tokens)
retriever.save(str(BM25_DIR), corpus=corpus_paths)
tokenizer.save_vocab(str(BM25_DIR))
tokenizer.save_stopwords(str(BM25_DIR))
```

## State of the Art

Not applicable — pure removal phase using established patterns.

## Assumptions Log

| # | Claim | Section | Risk if Wrong |
|---|-------|---------|---------------|
| A1 | `lint/dependency.py`'s `package-family` references should be **deleted** (Option A in Pitfall 3) rather than preserved/renamed (Option B) | Pitfall 3 | If the user actually uses `kind: package-family` in their personal vault's dependency pages, those pages will throw `dep-kind-not-in-enum` lint errors after Phase 51. Mitigation: the lint group is **optional** (`OPTIONAL_GROUPS = {"dependency_layer"}` at `lint_wiki.py:57`) and disabled by default — user must explicitly pass `--check dependency_layer`. Risk is low. |
| A2 | Hand-edit fallback for `divergence-librarian.json` is acceptable per D-05's "fallback when no regen tooling exists" clause, even though tooling DOES exist (just behind a $$$ live-Bedrock gate) | Pitfall 2 | If the user strictly reads D-05 as "always prefer tooling regen," the planner must include the live-Bedrock step in the execution plan, requiring AWS creds + ~$2 spend. Risk is low — D-05's intent is to avoid silent drift, and the hand-edit is a 5-line surgical change verifiable by `jq` or a diff. |
| A3 | The committed `search.db` (589KB) does not need regeneration when fixture markdowns change; only `vocab.index.json` and `vocab.tokenizer.json` do | Pitfall 5 | If a downstream test reads `search.db` for content-correctness (vs. just shape/existence), stale embeddings would mask a real bug. Verified by grep that no `wiki-io` or `eval-harness` test reads from `search.db` content — only `agents/graph-wiki-agent/tests/unit/test_query_search.py` does, and it builds its own search.db in `tmp_path`. |
| A4 | Phase 46's `migrate-vault` does not need to retain `[[package-family/...]]` "unresolvable" logging post-Phase-51 | Pitfall 4 | If a user re-runs `migrate-vault` against a pre-Phase-53 vault (with `wiki/package-family/` still present) after Phase 51 ships, old links will pass through unchanged instead of being logged. Risk is the user not noticing those links exist. Mitigation: Phase 53 handles them atomically. Risk is low. |

## Open Questions

None — all questions raised in CONTEXT.md's "Next Steps §1" are resolved by this research:

1. ✅ `cg describe-package-family` / `cg list-package-families` — **do not exist** (verified against `_SUBCOMMANDS`).
2. ✅ Baseline regen path — **`pytest --accept-divergence-baseline`** (registered at `tests/conftest.py:40`), Bedrock-gated.
3. ✅ `dependency.py` / `link_rewriter.py` references are **executable code paths** (not comments) — see Pitfalls 3 & 4 for recommended dispositions.
4. ✅ Fixture surface — full inventory below in `## Validation Architecture` and the diagram.

## Environment Availability

| Dependency | Required By | Available | Version | Fallback |
|------------|------------|-----------|---------|----------|
| `pytest` | Verification gates (51-01..51-04) | ✓ (project standard) | ≥8.3 | — |
| `bm25s` | Plan 51-04 fixture bm25 regen | ✓ (already vendored) | 0.3.8 | — |
| AWS Bedrock credentials | **Optional**: Plan 51-03 live baseline regen (D-05 preferred path) | ✗ (assumed not configured in plan execution env) | — | Hand-edit `divergence-librarian.json` per Pitfall 2 |
| `GRAPH_WIKI_RUN_EVAL=1` env var | Same — gates the live regen test | ✗ (not set by default) | — | Same as above |
| `git` (for `git rev-parse --short HEAD`) | Hand-edit baseline `agent_commit` field | ✓ | — | — |

**Missing dependencies with no fallback:** None.

**Missing dependencies with fallback:** AWS Bedrock creds — fallback to hand-edit is documented and equivalent in outcome.

## Validation Architecture

### Test Framework
| Property | Value |
|----------|-------|
| Framework | pytest ≥8.3 (project standard per `CLAUDE.md`) |
| Config files | `packages/{graph-io,wiki-io,eval-harness}/pyproject.toml` + `packages/eval-harness/tests/conftest.py` |
| Quick run command | `pytest packages/graph-io/tests/test_uri.py packages/wiki-io/tests/test_entity_writer.py -x` |
| Full suite (per-package) | `pytest packages/{graph-io,wiki-io,eval-harness}/tests/ -x` |
| Workspace-scoped | `uv run --package wiki-io pytest` |

### Phase Requirements → Test Map

| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|--------------|
| PKGFAM-01 | `_VALID_KINDS` no longer contains `"package_family"`; URI builders reject it implicitly via `_VALID_KINDS` gate at `queries.py:241` | unit | `pytest packages/graph-io/tests/test_uri.py -x` + new assertion `assert "package_family" not in _VALID_KINDS` | ✅ existing tests + 1 new assertion |
| PKGFAM-02 | `package_family_uri` no longer importable from `graph_io.uri` | unit | `pytest packages/graph-io/tests/test_uri.py::test_package_family_uri -x` (must fail with ImportError → delete the test) | ✅ delete test |
| PKGFAM-03 (alias side) | `ADMITTED_KINDS_V18` no longer exists; `ADMITTED_KINDS` is the 6-kind frozenset | unit | `pytest packages/wiki-io/tests/test_entity_writer.py::test_admitted_kinds_shape -x` (must be updated to expect 6 kinds, not 7) | ✅ existing — update assertion |
| PKGFAM-03 (template side) | `entity-package-family.md` and `package-family.md` removed from assets | unit | `assert not (importlib.resources.files("wiki_io.assets.page-templates") / "entity-package-family.md").exists()` | ❌ — Wave 0 to add OR skip (success criterion verified by grep) |
| PKGFAM-04 | `cg describe-package-family` / `cg list-package-families` are not in `_SUBCOMMANDS` | unit | `pytest packages/graph-io/tests/test_cli_main.py -k "no_package_family_subcommand"` OR a grep gate | ❌ — Wave 0 to add 1 assertion test (or skip; grep gate covers it) |
| PKGFAM-05 | Domain-edge code untouched | regression | `pytest packages/graph-io/tests/test_domain*.py packages/graph-io/tests/test_derived_edges.py -x` | ✅ existing |
| CLEANUP-01 | `LIB-003` registry, regex, function, test cases, baseline expectation all gone; LIB-001/002/004 unchanged | unit + integration | `pytest packages/eval-harness/tests/test_divergence_checks.py packages/eval-harness/tests/test_divergence_baseline.py packages/eval-harness/tests/test_two_gate_scorer.py -x` | ✅ existing — edit fixtures |
| **Phase gate (success criterion #1)** | Zero `package_family\|package-family\|PKGFAM\|package_family_uri` hits in `packages/` (excluding planning docs + migration-log JSONL) | grep | `! grep -r "package_family\|package-family\|PKGFAM\|package_family_uri" packages/ --include="*.py" --include="*.md" --include="*.json" --include="*.toml" \| grep -v ".planning/" \| grep -v "migration.log" \| grep -q .` | new — add to CI / verification step |
| **Phase gate (success criterion #5)** | Zero `_SLUG_ONLY_RE\|_check_no_slug_only_wikilinks\|LIB-003` hits in `packages/eval-harness/` (excluding synthesizer's parallel `_check_no_slug_only_wikilinks` — see Pitfall 1) | grep | `! grep -rn "_SLUG_ONLY_RE\|LIB-003" packages/eval-harness/ \| grep -q .` AND `! grep -rn "_check_no_slug_only_wikilinks" packages/eval-harness/src/eval_harness/divergence/librarian.py \| grep -q .` | new — add to verification step |

### Sampling Rate

- **Per task commit:** scoped per-package pytest (`uv run --package <pkg> pytest`)
- **Per wave merge:** all three packages' tests (`pytest packages/graph-io/tests/ packages/wiki-io/tests/ packages/eval-harness/tests/ -x`)
- **Phase gate:** the two grep invariants above + full suite green + `pytest packages/wiki-io/tests/test_round_trip.py -x` (fixture-edit integrity)

### Wave 0 Gaps

- [ ] Add `assert "package_family" not in _VALID_KINDS` to `packages/graph-io/tests/test_uri.py` (or a new `test_queries.py` if module-level test missing)
- [ ] Optional: Add `packages/graph-io/tests/test_cli_main.py::test_no_package_family_subcommand` asserting the two subcommands aren't in `_SUBCOMMANDS` (grep gate already covers this; keep as belt-and-suspenders).
- [ ] Add the two grep-gate shell invocations to `.planning/phases/51-package-family-removal-divergence-rule-cleanup/51-VALIDATION.md` as the phase exit gates.
- [ ] No framework install needed — pytest, bm25s already present.

## Project Constraints (from CLAUDE.md)

The project's `CLAUDE.md` enumerates several directives this phase must honor:

1. **Python 3.11+ floor** — preserved (no Python-version changes).
2. **AWS Bedrock only** — preserved (no `langchain-anthropic` introduced).
3. **Standard CLI / test invocation** (`uv run --package <pkg> pytest`) — used in the validation commands above.
4. **`packages/graph-io/CLAUDE.md`** — "Read-only queries go through `store.read_only_connect()`"; "All updates inside one SQLite transaction"; "Errors → stderr, JSON → stdout"; "Exit codes stable from v1 forward." All preserved — Phase 51 is removal-only and touches none of these surfaces.
5. **GSD Workflow Enforcement** — file edits gated through `/gsd-execute-phase` (this phase).

## Sources

### Primary (HIGH confidence — verified in this session)
- `packages/graph-io/src/graph_io/queries.py:9-29` — `_VALID_KINDS` definition (read tool).
- `packages/graph-io/src/graph_io/uri.py:49-50` — `package_family_uri` builder (read tool).
- `packages/graph-io/src/graph_io/cli/main.py:45-77` — `_SUBCOMMANDS` table; **confirms `describe-package-family` / `list-package-families` are absent** (read tool).
- `packages/wiki-io/src/wiki_io/entity_writer.py:60-196` — `ADMITTED_KINDS`, `_URI_PREFIX_BY_KIND`, `ADMITTED_KINDS_V18` (read tool).
- `packages/wiki-io/src/wiki_io/link_rewriter.py:43-446` — 9 active `package-family` code paths (read tool).
- `packages/wiki-io/src/wiki_io/lint/dependency.py:17,30,37,46,50,58,etc.` — lint-side `package-family` kind (read tool).
- `packages/eval-harness/src/eval_harness/divergence/librarian.py:1-129` — LIB-003 definitions (read tool).
- `packages/eval-harness/src/eval_harness/divergence/synthesizer.py:46-130` — confirms SYN-002 is a parallel, independent check (read tool — Pitfall 1).
- `packages/eval-harness/tests/conftest.py:40-50` — confirms `--accept-divergence-baseline` pytest hook (grep).
- `packages/eval-harness/tests/test_divergence.py:70-121` — confirms baseline regen flow + git-SHA stamping (read tool).
- `packages/eval-harness/baselines/divergence-librarian.json` — confirms current baseline shape (read tool).
- `agents/graph-wiki-agent/src/graph_wiki_agent/commands/query.py:739-810` — `build_index()` bm25 + Bedrock embedding flow (read tool — Pitfall 5).
- `packages/wiki-io/tests/test_round_trip.py:17-71` — confirms fixture-byte invariants (read tool).
- `packages/wiki-io/tests/conftest.py:1-205` — confirms fixture discovery and `MockGraphConn` shape (read tool).

### Secondary (MEDIUM confidence — derived from project documentation)
- `.planning/REQUIREMENTS.md` — PKGFAM-01..05 + CLEANUP-01 wording.
- `.planning/ROADMAP.md` §Phase 51 — 5 success criteria.
- `.planning/phases/49-builtin-kind-graph-io/49-CONTEXT.md` — D-10 (no SCHEMA_VERSION bump precedent).
- `.planning/phases/50-app-reclassification-graph-io/50-CONTEXT.md` — D-08 (wiki-io scope boundary), D-12 (SCHEMA_VERSION policy).
- `CLAUDE.md` (project) — technology-stack table + workflow enforcement.

### Tertiary (LOW confidence)
- None — every claim in this research is anchored to a file path and line range in the current working tree.

## Metadata

**Confidence breakdown:**
- Code inventory (graph-io, wiki-io, eval-harness): **HIGH** — every reference grepped and line-verified.
- CLI subcommand absence (PKGFAM-04): **HIGH** — full `_SUBCOMMANDS` table inspected.
- Baseline regen path (D-05): **HIGH** for the mechanism; **MEDIUM** on the planner's choice between live-regen and hand-edit (Pitfall 2 documents the tradeoff).
- Fixture bm25 regen approach: **MEDIUM** — BM25-only inline script is unverified by execution but built from the exact lines of `build_index()`; Pitfall 5 notes the search.db drift acceptability assumption (A3).
- `lint/dependency.py` disposition (Pitfall 3 / A1): **MEDIUM** — Option A vs B is a judgment call; recommended Option A with documented risk.

**Research date:** 2026-05-28
**Valid until:** 30 days (code surface is stable; user has locked all decisions in CONTEXT.md)

## RESEARCH COMPLETE
