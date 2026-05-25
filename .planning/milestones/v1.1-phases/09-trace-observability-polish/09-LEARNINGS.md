---
phase: 9
phase_name: "Trace/Observability Polish"
project: "agent-research"
generated: "2026-05-17"
counts:
  decisions: 7
  lessons: 5
  patterns: 6
  surprises: 4
missing_artifacts:
  - "09-UAT.md (no UAT artifact — renderer/docs/schema-stamping phase is grep + snapshot-verifiable; no human UAT surface)"
---

# Phase 9 Learnings: Trace/Observability Polish

## Decisions

### schema_version as the FIRST key of every trace record

Every trace record dict places `"schema_version": 1` as its first key — across all three producer writers (`SubagentPool._write_trace`, `SubagentPool._write_batch_terminal`, `query.py` query_summary writer).

**Rationale:** Preserves the "JSONL line is self-describing" invariant when records are grep'd or stream-processed — readers see the version before any other field. Locks the producer-half of OBS-04 with a grep-friendly invariant rather than position-agnostic semantics.
**Source:** 09-01-SUMMARY.md `patterns-established`

### Pipe-delimited string key for `by_role_model` aggregation

`_aggregate_trace` keys the cost-rollup bucket dict by `f"{role}|{model_id}"` strings rather than tuple keys or list-of-dicts.

**Rationale:** Trivial JSON serializability (tuple keys break `json.dumps`), straightforward iteration in the renderer, and stable sort ordering. Tuple keys would require lossy conversion at every snapshot boundary.
**Source:** 09-03-SUMMARY.md `key-decisions`

### Sibling-doc cross-link from `cancellation.md` (no field-table duplication)

`docs/cancellation.md` keeps its illustrative JSON blocks but a single sentence in §3 defers field-table authority to `docs/trace-schema.md` via a relative link (`./trace-schema.md`).

**Rationale:** Single source of truth for the schema (D-06). Two docs with overlapping field tables would inevitably drift; the cross-link keeps both useful without duplicating the authoritative tables.
**Source:** 09-02-SUMMARY.md `decisions`

### `--expand` as a boolean Typer flag, NOT a verbosity counter

The drill-down toggle is a single boolean (`--expand` / no-flag), not `-v / -vv / -vvv`.

**Rationale:** The collapse decision is binary — either you want the dense summary or the full event stream. Verbosity counters invite mid-state ambiguity ("what does -vv mean here?") and add no observable distinction in this output surface.
**Source:** 09-04-PLAN.md scope; 09-04-SUMMARY.md task narrative

### v0 warning wording is "Claude's Discretion" but newer-version wording is locked verbatim (D-03)

The v0/unversioned warning string was written by the executor (one-shot per file, mentions path + `schema_version=0` + `pre-Phase-9` on one line). The newer-version warning string is the verbatim D-03 phrase — no rewording.

**Rationale:** D-03 was locked in CONTEXT.md as the lenient-consumer contract; rewording it would weaken the schema-policy guarantee. The v0 message is implementation detail (no producer ever emits a v0 record going forward) and can evolve freely.
**Source:** 09-05-SUMMARY.md `key-decisions`

### Tuple-key collapse extend-or-flush mirrors cost-rollup grouping (CR-01 closure)

After 09-06, the collapse loop keys runs by `(role, model_id)` — the same key the cost rollup at `cli.py:362` uses. Header surfaces `model_short = model_id[-30:]` (same 30-char suffix convention as the rollup).

**Rationale:** Cost-rollup grouping is the source of truth for "what was this run-cost attributable to"; the timeline must use the same grouping or the project's cost story silently mis-attributes across mixed-model fan-outs (`role_model_overrides` sweeps). The 30-char suffix is already a proven, length-bounded convention.
**Source:** 09-06-SUMMARY.md `decisions`

### Closed-set + `other` bucket pattern for additive-shape resilience (WR-03 closure)

`_render_collapsed_group`'s status breakdown enumerates `{success, error, cancelled}` as known buckets and routes everything else through an `other` bucket. Fallback wording for an N=0 canonical-counts edge case is `f"{n} unknown"`, not `0 success`.

**Rationale:** `docs/trace-schema.md §4` explicitly permits additive-shape evolution — new statuses WILL appear. Hardcoded enumeration silently dropped them; the new shape surfaces them loudly so a reader notices when the producer adds a status the renderer doesn't yet special-case.
**Source:** 09-06-SUMMARY.md `tech-stack.patterns`; 09-VERIFICATION.md WR-03

---

## Lessons

### A "literally-met" success criterion can still violate the success-criterion's intent

SC#3 read `collapses repeated subagent-role groups into a summary line by default`. Phase 9 plans 1-5 literally implemented this — same-role records collapse. But verification surfaced CR-01: when records share a role but use different `model_id`s (a `role_model_overrides` A/B sweep — the exact case the project's cost story is built for), the timeline silently combined them and lost model attribution. The literal wording was met; the intent — preserving the project's cost narrative end-to-end — was not.

**Context:** Drove the entire 09-06 gap-closure plan. The lesson is that goal-backward verification (gsd-verifier reading SC wording AND project intent against the code) catches the literal-vs-intent gap that test suites alone do not — the snapshot test was passing the whole time.
**Source:** 09-VERIFICATION.md CR-01 narrative; 09-06-PLAN.md gap_closure context

### Aggregator filters that run before kind-discriminator filters synthesize phantom buckets

`_aggregate_trace.by_role` originally ran the bucket-by-role pass BEFORE the event/kind filter. `kind: query_summary` records (no `role` field) fell into the `record.get('role', 'unknown')` default and produced a phantom `unknown: count=1` bucket — baked into the committed `test_query_summary_interleaved_breaks_group_snapshot.ambr`. The cost-rollup pass had the filter in the right place; the by_role pass did not. Symmetry between sibling aggregator passes is not free — it must be enforced by reusing a single predicate.

**Context:** WR-02 in 09-VERIFICATION.md. Fix: extract `_is_groupable(record)` once and gate both passes through it. Same kind of bug class as CR-01 (the cost rollup keyed correctly, the collapse loop did not) — sibling aggregator/renderer pieces drifting because they were written without a shared filter primitive.
**Source:** 09-VERIFICATION.md WR-02; 09-06-SUMMARY.md "tech-stack.patterns"

### Snapshot tests can lock in bugs, not just behavior

`test_query_summary_interleaved_breaks_group_snapshot.ambr` baked the `unknown: count=1 tokens_in=0 tokens_out=0` phantom-bucket line directly into the recorded output. The test passed because the snapshot matched what the renderer produced; the snapshot was wrong but the test was green. Snapshot diff alone never flagged it — only goal-backward verification reading the rendered output against project intent caught the defect.

**Context:** Reinforces that snapshots are a "what does it currently emit" lock, not a "what should it emit" oracle. When regenerating snapshots in 09-06, the workflow explicitly diff'd the regen output to confirm `unknown: count=1` was gone — i.e., the regen step double-checked the previous snapshot was wrong, not just that the new one was different.
**Source:** 09-06-SUMMARY.md "Snapshots Regenerated"; 09-VERIFICATION.md WR-02

### Inline-substring test assertions break when output strings get a new segment

Two tests in 09-04 used `assert "scanner x4:" in stdout` — perfectly fine until 09-06 inserted `/ {model_short}` between role and count, turning the rendered header into `scanner / haiku-4-5-2025... x4:`. The asserts had to be rewritten to anchor on `scanner` AND `x4:` on the same line, not the literal-substring concatenation.

**Context:** Substring asserts in CLI tests should anchor on tokens unique to the structural intent (`x{N}:` is unique to collapsed headers), not on concatenated literal fragments that any later renderer change can split. Future tests in this surface should prefer per-token anchoring or full-line snapshots.
**Source:** 09-06-SUMMARY.md "Inline-Assertion Adjustments"

### Plans whose verification steps grep for a literal string in source must avoid that string in code comments

Task 2 in 09-06 had a verify step `grep -c "0 success" cli.py | awk '{exit ($1==0)?0:1}'`. The executor's first draft of the explanatory comment in `cli.py:200-205` literally included the phrase "0 success" while describing the behavior change — which would have failed the verify step on its own comment. The executor reworded to "zero-success fallback".

**Context:** Plan-checker should flag verify steps that grep for a literal phrase in source if the planner's own task description suggests that phrase will likely appear in code comments. Subtle source of self-defeating CI checks.
**Source:** 09-06-SUMMARY.md "Deviations from Plan"

---

## Patterns

### Strict-producer / lenient-consumer schema policy with one-shot per-file warnings

Producers always stamp `schema_version: 1`. The renderer accepts older (v0/unversioned) records with a one-shot per-file warning and accepts unknown-future versions (v2+) with a different one-shot per-file warning. Best-effort rendering proceeds in both cases.

**When to use:** Any local-disk schema where the producer can be tightened freely (we control all writers) but the consumer must remain useful across schema-version drift. The one-shot-per-file rule keeps stderr signal usable when grepping output of many trace files.
**Source:** 09-CONTEXT.md D-03/D-04; 09-05-SUMMARY.md

### Per-line semantics for one-shot warning tests (not substring `.count()`)

The canonical measure of "warning emitted once per file" is the count of DISTINCT stderr line indices carrying any of the agreed markers — `len({i for i, line in enumerate(stderr_lines) if "marker" in line}) == 1`, NOT `stderr.count("marker") == 1`. The latter breaks if a single line bundles multiple markers.

**When to use:** Any test asserting "emitted once" against an output stream where the single emission may contain multiple substring matches. Robust against string-rewording.
**Source:** 09-05-SUMMARY.md `patterns-established`

### Forward-declared single-predicate filter shared across sibling aggregator passes

`_is_groupable(record)` is the single source of truth for "is this a per-item, groupable record (vs. an event/kind discriminator)" — reused in `_aggregate_trace`'s by_role pass, `_aggregate_trace`'s by_role_model pass, and the collapse-loop guard inside the `trace` command.

**When to use:** Whenever two or more renderer/aggregator passes need to apply the same kind-discrimination filter. Inlining the filter in each pass guarantees drift; a single predicate enforces symmetry.
**Source:** 09-06-SUMMARY.md `tech-stack.patterns`; D-11 in CONTEXT.md

### Closed-set + catch-all bucket for additive-shape value enumerations

When the schema policy explicitly permits additive-shape evolution (new enum values OK without bumping the major version), renderer enumerations of those values get an explicit catch-all bucket (`other`) instead of being hardcoded. The fallback for the empty case is truthful (`{n} unknown`), never a misleading hardcoded-first-bucket label.

**When to use:** Status fields, role lists, event-kind enumerations — anywhere the producer can add a value the renderer doesn't yet special-case.
**Source:** 09-06-SUMMARY.md; `docs/trace-schema.md §4`

### Cost rollup output formatting (D-09/D-15)

`$0.000000` (6 decimal places, leading `$`); `(+K unknown)` suffix on partial-null groups; `$n/a (K unknown)` on fully-null groups; sort descending by total cost with alphabetical `(role, model_id)` tie-break; fully-null groups sort last.

**When to use:** Any per-record cost rollup that needs to itemise across `(role, model)` slices with mixed-known/unknown cost data. The 6-decimal format makes sub-cent costs visible; the `(+K unknown)` accounting keeps the rollup honest when some records had no cost_usd field populated.
**Source:** 09-03-SUMMARY.md `patterns-established`

### Default-mode timeline emission via sliding window + flush-on-break

Parse all records into a list, walk once with a sliding window, accumulate consecutive groupable same-key records into `current_run`. On a key-break (or non-groupable record), flush the run (collapsed-or-fallback) and emit the breaking record in full. Final flush at end-of-stream.

**When to use:** Any per-record stream where the renderer wants dense default output but a `--expand` escape to per-record fidelity. The sliding-window pattern is cleaner than two-pass approaches (group then render) because the run state lives in one local variable.
**Source:** 09-04-SUMMARY.md `patterns-established`

---

## Surprises

### Pre-existing UnboundLocalError in `_compute_cost_usd` — auto-fixed under Rule 1

09-01 (the first 09-* plan to touch trace-producing code) discovered a latent `UnboundLocalError` in `_compute_cost_usd`: a lazy `UnknownModelError` import was referenced in an `except` clause but unbound when the import itself failed. The executor auto-fixed under Rule 1 (current-task-caused blocking issue) by replacing the unbound exception with `(ImportError, KeyError)` — `UnknownModelError` subclasses `KeyError` so coverage is equivalent.

**Impact:** Latent crash path on import-error fallback; would have surfaced under Bedrock-credential failures or partial-install scenarios. Fixed inside scope of 09-01 because the bug fired on the same code path the new schema_version test was exercising.
**Source:** 09-01-SUMMARY.md `key-decisions`

### Snapshot for plan N had to wait for plan N+1 to ship

`test_cost_rollup_snapshot` was added in 09-03 but couldn't record a baseline `.ambr` until `--expand` shipped in 09-04 (the default-mode collapse would have collapsed the cost-rollup fixture). 09-03 guarded the test with a `subprocess "trace --help"` probe that self-skipped until the flag appeared. 09-04 then recorded the baseline as a side-effect of its own snapshot work.

**Impact:** Worked, but reveals an awkward sequencing pattern — a test added in one plan effectively depends on a feature shipping in the next plan. Better to defer snapshot recording to the plan that ships the prerequisite, or to plan the prerequisite first.
**Source:** 09-03-SUMMARY.md `key-decisions`; 09-04-SUMMARY.md `key-decisions`

### Three "INFO" anti-patterns surfaced by verification were NOT promoted to gaps

09-VERIFICATION.md's "Anti-Patterns Found" table flagged seven items: 3 WARNING (promoted to gaps CR-01/WR-02/WR-03) and 4 INFO (WR-01 bool-as-int, WR-04 missing-timestamp dashes, IN-01 bare ValueError, IN-04 cancellation.md examples lacking schema_version). The INFO items were excluded from 09-06's scope and explicitly listed as "UNTOUCHED" in the executor's Scope Discipline section.

**Impact:** Surfaced the value of severity classification in verification reports — a flat "issues_found" verdict would have either pulled in scope-creep work or forced the orchestrator to manually triage. The WARNING/INFO split let 09-06 land cleanly in ~25 minutes with three regression tests, and the INFO items are now tracked in VERIFICATION.md for a future v1.2 cleanup pass if desired.
**Source:** 09-VERIFICATION.md "Anti-Patterns Found"; 09-06-SUMMARY.md "Scope Discipline"

### The plan-checker passed 09-06 on the first iteration

The revision loop in plan-phase is designed for up to 3 iterations of replan → check. 09-06's plan-checker run returned `VERIFICATION PASSED` on the first attempt, with no ISSUES FOUND. Gap-closure plans built directly off a structured VERIFICATION.md gaps array seem to skip the iterative-clarification phase that ordinary plans need — the gaps already specify both the problem and the required artifacts, leaving little room for plan ambiguity.

**Impact:** Suggests `--gaps` mode is a high-signal, low-iteration path. A possible workflow optimization: gap-closure plans could skip the plan-checker loop entirely when the gaps array in VERIFICATION.md contains explicit `missing:` arrays, since the planner is effectively translating those bullets into tasks 1:1.
**Source:** Orchestrator conversation log, plan-phase run for 09-06; 09-06-PLAN.md
