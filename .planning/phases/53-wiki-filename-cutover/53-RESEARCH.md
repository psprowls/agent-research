# Phase 53 — Research

**Phase:** 53 — Wiki Filename Cutover (reshape: cleanup + verification)
**Researched:** 2026-05-28
**Status:** Complete — research scope intentionally narrow per CONTEXT D-01..D-10.

---

## Research Scope Note

Phase 53 was dramatically slimmed during discuss-phase (see `53-DISCUSSION-LOG.md`).
The original "build a v1.9 cutover migration with rewriter + dispatch + manifest tracking +
atomic vault commit" was rejected. Phase 53 is now:

1. ROADMAP + REQUIREMENTS reshape (markdown edits) — strike SC #1 / SC #2 from §53;
   rewrite WIKI-FN-05 / WIKI-FN-06 to verification-language (D-10).
2. Source-code cleanup — delete `encode_slug` / `decode_slug` and any orphaned scaffolding;
   rewrite remaining call sites to read `frontmatter.uri` directly (D-04, D-05, D-06).
3. Test-fixture closure — confirm/patch `tests/fixtures/round-trip-vault/` to new short-form
   filenames if Phase 52 left a gap (D-07).
4. Manual UAT — Pat regenerates `~/Personal/graph-wiki/agent-research` from scratch and records
   findings in `53-UAT.md` (D-08, D-09).

Because Phase 52 is **executing in parallel as this research is written**, this research does
NOT re-grep `packages/` source files (would conflict with concurrent edits). Instead it
relies on:

- Phase 52 CONTEXT.md D-08 / D-09 — `decode_slug` is dropped from the new write path;
  `encode_slug` / `decode_slug` function bodies stay until Phase 53.
- Phase 53 CONTEXT.md D-04..D-06 — authoritative list of expected call sites and the
  cleanup actions for each.
- Plan tasks defer the actual grep + edit work to the executor, which will run after
  Phase 52 is merged. The executor reads the live tree.

This is the right call: re-running the grep at planning time would race with Phase 52's
executor writes and produce stale data. Pinning the cleanup actions to symbolic landmarks
(`encode_slug`, `decode_slug`, `_ADMITTED_URI_PREFIXES`, `link_rewriter.py`, `index_generator.py`,
scanner) makes the plan robust to Phase 52's exact final state.

---

## Code Surface (per CONTEXT.md canonical refs — authoritative)

### Functions to delete (D-04)

| Location | Symbol | Status entering Phase 53 |
|----------|--------|--------------------------|
| `packages/wiki-io/src/wiki_io/entity_writer.py:133-142` | `encode_slug(uri)` | No production caller in write path (Phase 52 D-08 replaced with `short_filename`). Still imported by `link_rewriter.py` / `index_generator.py` / scanner per CONTEXT D-05 — Phase 53 owns these call-site rewrites. |
| `packages/wiki-io/src/wiki_io/entity_writer.py:145-167` | `decode_slug(slug)` | Phase 52 dropped the writer's reverse lookup; only test-suite references remain (per Phase 52 D-08 + D-09). Phase 53 deletes the function. |
| `packages/wiki-io/src/wiki_io/entity_writer.py:87` | `_ADMITTED_URI_PREFIXES` frozenset | Orphan candidate: its sole consumer is `decode_slug`'s validation surface. After `decode_slug` is gone, check if `_URI_PREFIX_BY_KIND` is still derived from `.values()` of the dict (auto-derive in Phase 52 plan 02-01) — if yes, the frozenset itself stays alive as the auto-derived set; if it has any *non-decode* consumer, leave it. Per CONTEXT D-06 default: delete only if truly orphaned. |

### Call sites to rewrite (D-05)

CONTEXT D-05 names these symbols by file (researcher confirms at execute time):

| File | Likely use of `encode_slug` / `decode_slug` | Rewrite action |
|------|--------------------------------------------|----------------|
| `packages/wiki-io/src/wiki_io/link_rewriter.py` | Old long-slug → URI lookup for inbound wikilink resolution. May import either function. | Per CONTEXT D-08 (from Phase 52): replace reverse lookups with `frontmatter.uri` reads of entity `.md` files in the entities dir. |
| `packages/wiki-io/src/wiki_io/index_generator.py` | Generates `wiki/index.md`; may call `encode_slug` to derive entity filenames. | Replace with `short_filename(uri, collision_set=...)` call. If `index_generator` needs a collision-set, it can call `_compute_collision_set` from `entity_writer` (Phase 52 introduces this helper). |
| Scanner ingest path (likely `agents/graph-wiki-agent/src/graph_wiki_agent/...`) | May call `decode_slug` to translate entity filenames back to URIs during a scan. | Read `frontmatter.uri` directly off each entity file instead. |

The executor MUST grep `packages/` and `agents/` for `encode_slug` + `decode_slug` references
on entry to the task, and produce a definitive call-site list before editing. The plan
specifies the action shape (per file) but defers exact line numbers to execution.

### Tests to delete or rewrite (D-04 closure)

- Any tests in `packages/wiki-io/tests/` that exercise `encode_slug` / `decode_slug` directly
  (e.g., `test_uri_slugs.py` from Phase 42, or the `test_encode_slug` / `test_decode_slug`
  blocks in `test_entity_writer.py`) — delete alongside the functions.
- Tests of `link_rewriter` / `index_generator` / scanner that mock or assert long-slug
  behavior — rewrite to assert short-form `frontmatter.uri` reads instead.

### Test fixtures (D-07)

`packages/wiki-io/tests/fixtures/round-trip-vault/` — Phase 52's plan 04 was
*optional* in 52-CONTEXT's `<next_steps>`. Phase 53 plan 02 confirms fixture state and
patches any gap.

**Why this matters:** if the round-trip fixture still has `pkg__org__repo__name.md` style
filenames, then deleting `decode_slug` will fail tests that assert round-trip vault
correctness. Phase 53 plan 02 either:

1. Confirms Phase 52 already updated the fixture → no action.
2. Renames the fixture files to short-form (`pkg_<name>.md`, `dep_<name>.md`, etc.) and
   updates any in-fixture `[[wikilinks]]` that pointed at the old names.

If `vocab.index.json` / `vocab.tokenizer.json` (or similar BM25 serialized indices) bake
filenames into their content, they must be regenerated as part of the fixture closure.

---

## Roadmap + Requirements Edits (D-10)

### `.planning/ROADMAP.md` §Phase 53

Current SC list (lines 227-231 in ROADMAP.md, verified):

1. ❌ Strike — `migrate-vault` atomic rewrite (no migration command, no rewriter, no atomic
   commit).
2. ❌ Strike — idempotency via manifest marker (no manifest marker exists).
3. 🔄 Reframe — was "`generate_index()` writes the new short filenames in `wiki/index.md`".
   Becomes: "`generate_index()` writes short filenames after `cg update --full` — verified
   via Phase 52's `write_entities` correctness + Phase 53 manual UAT."
4. 🔄 Reframe — was "vault re-scanned without errors after cutover". Becomes: "The
   `~/Personal/graph-wiki/agent-research` vault is regenerated manually (Pat deletes
   `wiki/{packages,dependencies,domain,plugin,test-suites,app}/`, runs `cg update --full`,
   then `graph-wiki-agent scan`); `wiki/index.md` reflects short-form filenames; recorded
   in `53-UAT.md`."

The phase goal text itself can also be loosened — "single atomic operation" no longer
applies. Suggested rewrite: "The wiki-io codebase no longer carries dead bidirectional-slug
machinery; the exploratory vault is regenerated from scratch to reflect Phase 52's short
filenames; documented in `53-UAT.md`."

### `.planning/REQUIREMENTS.md` WIKI-FN-05 / WIKI-FN-06

Current text (lines 34-35):

- **WIKI-FN-05** (current): "`migrate-vault` (or equivalent one-shot cutover command)
  rewrites existing inbound `[[…]]` wikilinks in curated lanes (...) from the old URI-fully-
  qualified filenames to the new short filenames, in a single atomic commit on the vault
  repo. CommonMark-aware tokenizer (code-block / inline-code excluded) per v1.8 precedent."
- **WIKI-FN-06** (current): "`generate_index()` writes the new short filenames in
  `wiki/index.md`. Existing exploratory `~/Personal/graph-wiki/agent-research` vault is
  re-scanned + migrated as part of milestone close."

Per CONTEXT D-10 + "Claude's Discretion" default (rewrite vs. withdraw): **rewrite to
verification-language**.

- **WIKI-FN-05** (new): "`encode_slug` / `decode_slug` and the orphaned `_ADMITTED_URI_PREFIXES`
  scaffolding are removed from `wiki_io.entity_writer`. All consumer call sites
  (`link_rewriter.py`, `index_generator.py`, scanner) are rewritten to read entity `frontmatter.uri`
  directly or to call `short_filename(uri, collision_set, ...)` from Phase 52. Verified via:
  `grep -rn 'encode_slug\|decode_slug' packages/ agents/` returns zero hits (excluding planning/
  comments) and the full test suite passes."
- **WIKI-FN-06** (new): "`generate_index()` (and the rest of the write path) emits the new
  short filenames per Phase 52's `write_entities` correctness. The exploratory
  `~/Personal/graph-wiki/agent-research` vault is regenerated from scratch by deleting
  `wiki/{packages,dependencies,domain,plugin,test-suites,app}/` then running `cg update --full`
  + `graph-wiki-agent scan`. Verified manually in `53-UAT.md`: 2-3 entity files spot-checked
  with expected short filenames; `wiki/index.md` reflects short-form throughout."

The traceability table (lines 67-94 in REQUIREMENTS.md) needs no change — WIKI-FN-05 / WIKI-FN-06
stay assigned to Phase 53.

---

## Implementation Pattern Map

### Pattern 1: Function deletion + call-site rewrite

Standard cleanup in this repo (Phase 51's `_SLUG_ONLY_RE` removal is the prior art).
Steps:

1. `grep -rn "encode_slug\|decode_slug" packages/ agents/` — full list of references.
2. For each reference, decide:
   - Test of legacy function → delete alongside the function.
   - Production consumer reading entity files → rewrite to use `frontmatter.uri` (per Phase 52 D-08).
   - Production consumer producing filenames → rewrite to call `short_filename(uri, collision_set)`.
3. Delete the function bodies (`encode_slug`, `decode_slug`).
4. Delete `_ADMITTED_URI_PREFIXES` only if no non-decode consumer remains.
5. Final grep confirms zero hits in `packages/` + `agents/` (excluding planning/ comments).

### Pattern 2: Markdown edit (no template; surgical edits in place)

ROADMAP.md and REQUIREMENTS.md are checked-in markdown. Use `Edit` tool with sufficient
context to make the replacements unique. The phase entry in ROADMAP.md (lines 223-233) and
the WIKI-FN-05/06 entries in REQUIREMENTS.md (lines 34-35) are surgical edits.

### Pattern 3: Fixture state confirmation

`packages/wiki-io/tests/fixtures/round-trip-vault/` is treated as a snapshot of vault state.
The plan task lists files in the fixture directory (after Phase 52 merges), greps for
long-form filenames (`__org__repo__` pattern), and replaces them with short-form filenames
if found. Wikilinks inside fixture content (e.g. `[[pkg__org__repo__name]]`) get rewritten
to `[[pkg_name]]`. The fixture is then committed as part of plan 53-02.

---

## Pre-Conditions

1. **Phase 52 must merge first.** Phase 53 plan execution depends on:
   - `short_filename` exists (Phase 52 plan 01).
   - `_compute_collision_set` exists (Phase 52 plan 02-02).
   - `write_entities` no longer calls `encode_slug` (Phase 52 plan 02-03).
   - `_URI_PREFIX_BY_KIND["dependency"] = "dep"` (Phase 52 plan 02-01).
   - `app` admitted in `ADMITTED_KINDS` (Phase 52 plan 03).

2. **No Phase 52 carryover.** If Phase 52 left fixture inconsistencies (its plan 04 was
   marked optional in 52-CONTEXT), Phase 53 plan 02 closes them.

3. **Vault regen is manual + post-merge.** Per CONTEXT D-08 default — Pat regenerates after
   the cleanup PR merges. Phase 53 does NOT touch the live `~/Personal/graph-wiki/agent-research`
   vault from automated tasks.

---

## Open Questions Resolved

| Question | Resolution |
|----------|-----------|
| Withdraw vs. rewrite WIKI-FN-05/06? | Rewrite to verification-language (per CONTEXT D-10 + Claude's Discretion default). Keeps satisfaction count accurate. |
| Single dedicated plan for docs reshape vs. fold? | Dedicated plan (`53-01-PLAN.md` — roadmap + requirements reshape). Keeps git history clean and reviewable. |
| Annotate `cg migrate-vault` docstring as v1.8-only? | Leave intact (per CONTEXT discretion default). The command still works for its v1.8 case; the docstring already references v1.8. |
| Timing of vault regen relative to PR merge? | After merge (default). Phase 53 plans land first; Pat regenerates manually; UAT recorded in `53-UAT.md`. |
| Should plan 02 also delete the Phase 42 `entity-package-family.template` if still around? | Phase 51 owned package-family removal. If `entity-package-family.template` still exists post-Phase-51, it's an orphan; Phase 53 plan 02 can `rm` it as part of cleanup. Treat as discretionary on entry: if `grep -rn "package-family" packages/ agents/` returns hits, surface as a blocker; otherwise no-op. |
| Should plan 02 add a `cg verify-vault` automated UAT command? | No (per CONTEXT deferred — "cheap to add but not required" for single-user). |

---

## Plan Decomposition

Per CONTEXT `<next_steps>`:

- **53-01 (Wave 1)**: Roadmap + Requirements reshape (D-10). Markdown-only. WIKI-FN-05 +
  WIKI-FN-06 reframing. No source-code changes.
- **53-02 (Wave 2)**: Source-code cleanup (D-04..D-07). Delete `encode_slug` / `decode_slug` /
  `_ADMITTED_URI_PREFIXES` (if orphan); rewrite call sites in `link_rewriter.py`,
  `index_generator.py`, scanner; close fixture gap; delete legacy tests.
- (Manual UAT — owned by Pat, not a plan): vault regen + `53-UAT.md` capture. Per CONTEXT
  D-09 — recorded after code-cleanup plans complete, drives phase verification.

Wave-2 depends on Wave-1 only loosely (the markdown edits don't gate the code edits, but
keeping them as sequential plans simplifies the commit history). If desired, both plans
could be Wave-1 (parallel-safe — they touch disjoint files: planning/ vs packages/) — but
sequential is cleaner and matches the dependency hint in `<next_steps>`.

**Choice:** Wave 1 for plan 01 (markdown), Wave 2 for plan 02 (code) — sequential. Lets a
human reader of the PR see "decided to reshape Phase 53" before "now executing the reshape."

---

## Validation Architecture

(Per project Nyquist validation conventions.)

### Dimension 1: Pre-conditions

- Phase 52 merged: `git log --oneline | grep -E "phase[/-]52" | head -1` returns the Phase 52
  merge commit.
- `short_filename` and `_compute_collision_set` are importable: `python -c "from wiki_io.entity_writer import short_filename, _compute_collision_set"` exits 0.

### Dimension 2: Per-task automation

Plan 53-01 (markdown edits):
- File diff produces the exact replacement strings — verified via `grep -F "<old text>" .planning/ROADMAP.md` (returns 0 after edit) and `grep -F "<new text>" .planning/ROADMAP.md` (returns at least 1 after edit). Same for REQUIREMENTS.md.

Plan 53-02 (code cleanup):
- `grep -rn "encode_slug\|decode_slug" packages/ agents/ --include="*.py"` returns 0 hits (excluding `.planning/`).
- `uv run --package wiki-io pytest packages/wiki-io/tests/ -v` exits 0 (no regression).
- Full workspace test run: `uv run pytest` exits 0.

### Dimension 3: Boundary tests

- Cross-package import check: `python -c "from wiki_io.link_rewriter import *; from wiki_io.entity_writer import short_filename; print('ok')"` exits 0 — no import-time errors after deletion.
- Scanner end-to-end: `uv run cg --help` exits 0 (CLI surface unchanged).

### Dimension 4: Integration / end-to-end

- Manual UAT (Pat): vault regen → `cg update --full` → `graph-wiki-agent scan` → inspect
  `wiki/index.md`. Recorded in `53-UAT.md`.

### Dimension 5: Negative tests

- `python -c "from wiki_io.entity_writer import encode_slug"` exits **non-zero** with ImportError
  (function is gone). Same for `decode_slug`.

### Dimension 6: Documentation tests

- `grep -rn "encode_slug\|decode_slug" .planning/` returns hits only in 53-* artifacts (the
  cleanup itself) and in archived milestones — no live references in REQUIREMENTS.md /
  ROADMAP.md / STATE.md outside the planned reshape.

### Dimension 7: Repeatability

- Re-running plan 53-02's verify steps after a clean checkout produces the same green
  state. No test flakes introduced.

### Dimension 8: Nyquist sampling

- Latency ≤ 45s for the quick command (single test file).
- After every plan, full workspace test (`uv run pytest`) exits 0.

---

## RESEARCH COMPLETE
