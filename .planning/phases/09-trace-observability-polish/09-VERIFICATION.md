---
phase: 09-trace-observability-polish
verified: 2026-05-17T00:00:00Z
status: gaps_found
score: 3/3 roadmap truths verified (with caveats)
overrides_applied: 0
gaps:
  - truth: "Trace renderer surfaces per-model attribution alongside collapsed groups"
    status: partial
    reason: "CR-01 (Critical from code review): default-mode timeline collapse groups consecutive records by `role` alone. When a fan-out emits items with the same role but different `model_id` (e.g. `role_model_overrides` A/B sweep), all records collapse into one summary line and `_render_collapsed_group` never prints model_id. The cost rollup in the Summary block still itemises per `(role, model_id)` correctly, so SC#2 is met — but the timeline view loses model attribution exactly where the project's cost story needs it most. The literal wording of SC#3 (`collapses repeated subagent-role groups`) is satisfied; the intent (preserve model attribution) is not."
    artifacts:
      - path: "agents/code-wiki-agent/src/code_wiki_agent/cli.py"
        issue: "L303: `current_run[-1].get('role') == record.get('role')` keys runs by role only. L164-215 `_render_collapsed_group` never reads model_id. Snapshot `test_query_summary_interleaved_breaks_group_snapshot` masks the bug by using a single-model fixture."
    missing:
      - "Change group key from `role` to `(role, model_id)` (mirror cost-rollup grouping)"
      - "Include `model_id_short` in `_render_collapsed_group` header line"
      - "Add regression test: two same-role records on different model_ids must render as two collapsed lines (or one line naming both models)"
  - truth: "Aggregator does not misattribute non-per-item records to a synthetic role"
    status: partial
    reason: "WR-02 (Warning from code review): `_aggregate_trace` runs the by_role bucket pass BEFORE the event/kind filter, so `kind: query_summary` records (which have no `role` field) land in a synthetic `unknown` bucket. The interleaved-snapshot output `unknown: count=1 tokens_in=0 tokens_out=0` confirms this in the committed snapshot. A reader scanning the per-role breakdown sees a phantom `unknown` subagent and cannot tell it is actually the query_summary line. Not a roadmap-SC blocker (SC#2 is met by the cost rollup, which DOES exclude event/kind correctly) but it's a visible aggregator defect locked into a snapshot test."
    artifacts:
      - path: "agents/code-wiki-agent/src/code_wiki_agent/cli.py"
        issue: "L124-132: by_role aggregator counts every record including event/kind discriminators; key fallback `record.get('role', 'unknown')` creates a phantom bucket"
      - path: "agents/code-wiki-agent/tests/unit/__snapshots__/test_trace_viewer.ambr"
        issue: "test_query_summary_interleaved_breaks_group_snapshot output bakes in `unknown: count=1 tokens_in=0 tokens_out=0` — snapshot needs updating after fix"
    missing:
      - "Either exclude event/kind records from by_role too, or key them by discriminator value (`query_summary`, `event:batch_cancelled`)"
      - "Update interleaved snapshot after fix"
  - truth: "Collapsed-group status breakdown handles future/unknown statuses correctly"
    status: partial
    reason: "WR-03 (Warning from code review): `_render_collapsed_group` hardcodes the breakdown dict to {success, error, cancelled}. A run of N records all carrying `status: 'timeout'` (or a future producer-added status) drops every count on the floor and the fallback emits the actively-wrong `'0 success'` for an N-record group. Strict-producer policy in docs/trace-schema.md §2.1 currently enumerates only those three, so this is a latent defect, not a present-day data corruption — but it's the kind of thing the renderer should surface loudly under any additive-status evolution (which the additive-shape rule explicitly permits per §4)."
    artifacts:
      - path: "agents/code-wiki-agent/src/code_wiki_agent/cli.py"
        issue: "L182-189: counts dict hardcoded; unknown statuses silently dropped; fallback prints misleading '0 success'"
    missing:
      - "Add an `other` bucket and surface it in the breakdown"
      - "Replace the misleading `'0 success'` fallback with `{N} unknown` or similar"
deferred: []
---

# Phase 9: Trace/Observability Polish Verification Report

**Phase Goal:** "The trace format is documented and versioned, and the trace renderer surfaces per-subagent cost and collapses noisy output by default"
**Verified:** 2026-05-17
**Status:** gaps_found
**Re-verification:** No — initial verification

## Goal Achievement

### Observable Truths (ROADMAP Success Criteria)

| #   | Truth                                                                                                                                            | Status              | Evidence                                                                                                                                                                                                                                                                                                                          |
| --- | ------------------------------------------------------------------------------------------------------------------------------------------------ | ------------------- | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| 1   | Every JSONL trace file contains a `schema_version` field; the schema is documented with a breaking-change policy                                  | VERIFIED            | `pool.py:212, 251` stamp `"schema_version": 1` in both producer writers. `query.py:982` stamps it in the per-query summary writer. `docs/trace-schema.md` exists (319 lines), §3 documents the field, §3 defines the strict-producer/lenient-consumer policy and bump rules, §4 the additive-shape rule, §5 the v0 compatibility note. |
| 2   | `code-wiki-agent trace <file>` displays per-subagent cost (input/output tokens × model price) for each fan-out call                              | VERIFIED            | `cli.py:323-360` emits a "Cost rollup (per role/model)" section with one line per `(role, model_id)` group; format `$0.000000`; `(+K unknown)` suffix on partial nulls; `$n/a (K unknown)` on fully-null groups; D-15 ordering enforced (`cli.py:329-338`). Committed snapshot `test_cost_rollup_snapshot` shows the format end-to-end. |
| 3   | `code-wiki-agent trace <file>` collapses repeated subagent-role groups into a summary line by default; `--expand` drills into the full event stream | VERIFIED (with gap) | `cli.py:223-308` implements collapse with `--expand` flag. `test_default_mode_collapses_consecutive_same_role` confirms collapse to one line; `test_expand_mode_renders_every_record_full_line` confirms `--expand` reverts to per-record. **Caveat:** collapse groups by `role` alone (not `(role, model_id)`) — see CR-01 in gaps. The literal SC wording is met; the model-attribution refinement remains.    |

**Score:** 3/3 roadmap success criteria met (SC#3 with documented gap)

### Required Artifacts

| Artifact                                                                                          | Expected                                                                  | Status     | Details                                                                                                                                                                                  |
| ------------------------------------------------------------------------------------------------- | ------------------------------------------------------------------------- | ---------- | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `cores/subagent-runtime/src/subagent_runtime/pool.py`                                             | Two trace writers stamp `schema_version: 1`                                | VERIFIED   | Lines 212 and 251 carry the literal `"schema_version": 1` as the first key of each record dict. Comments cite Phase 9 OBS-04 D-01/D-02.                                                  |
| `agents/code-wiki-agent/src/code_wiki_agent/commands/query.py`                                    | query_summary writer stamps `schema_version: 1`                            | VERIFIED   | Line 982 carries `"schema_version": 1` as the first key of summary_record.                                                                                                                |
| `docs/trace-schema.md`                                                                            | Authoritative schema reference, 120-320 lines, six required sections      | VERIFIED   | 319 lines; §1 directory/filename, §2 per-record shapes (×3) with field tables, §3 schema_version policy with verbatim D-03 wording, §4 additive-shape rule, §5 v0 compatibility, §6 examples. |
| `docs/cancellation.md`                                                                            | One-line cross-link to `docs/trace-schema.md`                              | VERIFIED   | Line 96: `See [docs/trace-schema.md](./trace-schema.md) for the authoritative field tables ...` — single sentence, no duplication.                                                       |
| `agents/code-wiki-agent/src/code_wiki_agent/cli.py`                                               | Extended `_aggregate_trace`, cost rollup emission, `--expand`, version warnings | VERIFIED   | Lines 83-161 `_aggregate_trace` with `by_role_model`; 164-215 `_render_collapsed_group`; 218-220 `_is_groupable`; 223-308 `trace` command with `--expand` flag and v0/newer warnings. `KNOWN_SCHEMA_VERSION = 1` at line 32. |
| `agents/code-wiki-agent/tests/unit/test_trace_viewer.py`                                          | Tests for aggregator, cost rollup, collapse/expand, v0+newer warnings     | VERIFIED   | 21 test functions covering all surfaces: `_aggregate_trace` direct tests, cost-rollup format, collapsed/expand snapshots, mixed-status, interleaved, isolated, v0 real-fixture, newer-version, one-shot-per-file. |
| `agents/code-wiki-agent/tests/unit/__snapshots__/test_trace_viewer.ambr`                          | Recorded snapshots for collapse/expand/cost-rollup                         | VERIFIED   | File exists; contains snapshots for `test_collapsed_default_snapshot`, `test_cost_rollup_snapshot`, `test_expand_snapshot`, `test_mixed_status_in_run_snapshot`, `test_query_summary_interleaved_breaks_group_snapshot`. |

### Key Link Verification

| From                                  | To                                  | Via                                | Status     | Details                                                                                                            |
| ------------------------------------- | ----------------------------------- | ---------------------------------- | ---------- | ------------------------------------------------------------------------------------------------------------------ |
| `SubagentPool._write_trace`           | per-item record dict                | first-key insertion                | WIRED      | `pool.py:212` — `"schema_version": 1` is the first key of the inline record dict.                                  |
| `SubagentPool._write_batch_terminal`  | batch terminal record dict          | first-key insertion                | WIRED      | `pool.py:251` — same pattern in the batch_cancelled writer.                                                        |
| `query.py` query_summary writer       | summary_record dict                 | first-key insertion                | WIRED      | `query.py:982` — first key of summary_record before json.dumps.                                                    |
| `cli.py` `_aggregate_trace`           | `trace` command rollup emission     | `by_role_model` dict               | WIRED      | `cli.py:329-360` consumes `agg["by_role_model"]` directly from `_aggregate_trace`'s return.                       |
| `cli.py` renderer                     | `eval_harness`                      | **must NOT import**                | VERIFIED   | `grep -E "from eval_harness\|import eval_harness" cli.py` returns 0 hits (D-10 invariant).                         |
| `trace` command                       | `--expand` flag                      | Typer Option                       | WIRED      | `cli.py:226-230` declares the boolean option; `cli.py:282-308` branches on it.                                     |
| collapse loop                         | `_render_collapsed_group`            | `_flush()` closure                  | WIRED      | `cli.py:288-308` invokes the helper on runs of `>=2`; isolated records fall through to `_render_trace_record`.    |
| v0 warning                            | per-file stderr (one-shot)          | `warned_v0` flag                   | WIRED      | `cli.py:241, 256-264` — flag initialised once per call, set after first emission.                                  |
| newer-version warning                 | per-file stderr (one-shot)          | `warned_newer` flag                | WIRED      | `cli.py:242, 265-273` — verbatim D-03 wording: `schema_version {sv} is newer than supported ({KNOWN_SCHEMA_VERSION})`. |
| cancellation.md                       | trace-schema.md                     | markdown link                      | WIRED      | `docs/cancellation.md:96` — `[docs/trace-schema.md](./trace-schema.md)`.                                           |

### Data-Flow Trace (Level 4)

| Artifact                          | Data Variable                                       | Source                                                                                                                                | Produces Real Data                                                                                                                                            | Status   |
| --------------------------------- | --------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------- | -------- |
| `trace` rendered cost rollup      | `agg["by_role_model"]`                              | `_aggregate_trace` walks parsed records; reads `cost_usd` populated by `SubagentPool._compute_cost_usd` at write time                  | Yes — committed `test_cost_rollup_snapshot` shows `$0.001500`, `$0.002000`, `(+1 unknown)`, `$n/a` flowing through end-to-end                                  | FLOWING  |
| collapsed-group timeline          | `current_run` list of dict                          | sliding window over parsed JSONL records                                                                                              | Yes — `test_default_mode_collapses_consecutive_same_role` shows `scanner x4:` line with summed tokens `40->20` and summed cost `$0.000400` from real subprocess | FLOWING  |
| v0 warning per-file               | `warned_v0` flag + file path                        | record-parse loop inside `trace`                                                                                                       | Yes — `test_v0_real_fixture_renders_and_warns_once` runs against real `cores/vault-io/tests/fixtures/round-trip-vault/.code-wiki/traces/*.jsonl` fixtures      | FLOWING  |
| newer-version warning             | `warned_newer` flag + sv integer                    | record-parse loop                                                                                                                     | Yes — `test_newer_version_warns_lenient` asserts verbatim wording                                                                                              | FLOWING  |
| Per-role breakdown (existing)     | `agg["by_role"]`                                    | by_role aggregator pass — does NOT filter event/kind                                                                                  | Partial — flows but mis-attributes query_summary records to a `unknown` role (WR-02; baked into interleaved snapshot)                                          | STATIC   |

### Behavioral Spot-Checks

Spot-checks deferred — phase verification is bounded to grep + snapshot inspection (no server startup) and the project's own pytest suite already covers the surfaces end-to-end via subprocess invocation (`test_trace_command_*`, `test_cost_rollup_*`, `test_v0_*`, `test_newer_version_*`, `test_*_snapshot`).

| Behavior                                | Command                                                                          | Result                                                              | Status |
| --------------------------------------- | -------------------------------------------------------------------------------- | ------------------------------------------------------------------- | ------ |
| `--expand` advertised in help            | `grep -q -- '--expand' cli.py`                                                  | hit at L226-230                                                     | PASS   |
| `KNOWN_SCHEMA_VERSION` constant declared | `grep -n 'KNOWN_SCHEMA_VERSION = 1' cli.py`                                     | L32                                                                 | PASS   |
| No eval_harness import in cli.py         | `grep -E 'from eval_harness\|import eval_harness' cli.py \| wc -l`               | `0`                                                                 | PASS   |
| Placeholder `Cost USD: (Phase 4)` removed | `grep -n 'Cost USD' cli.py`                                                     | (no output)                                                         | PASS   |
| `'Phase 4'` test references removed      | `grep -rn 'Phase 4' agents/code-wiki-agent/`                                    | (no output)                                                         | PASS   |
| Three producer writers stamp schema_version: 1 | `grep -rn '"schema_version": 1' cores/ agents/`                            | `pool.py:212, pool.py:251, query.py:982` — three hits as required   | PASS   |
| `docs/trace-schema.md` length in target range | `wc -l docs/trace-schema.md`                                                | `319` (within target ≤320, plan said 120-320)                       | PASS   |
| `docs/trace-schema.md` ≥5 `schema_version` mentions | `grep -c schema_version docs/trace-schema.md`                          | `31`                                                                | PASS   |
| Snapshot file recorded                   | `head .ambr`                                                                    | Contains `test_collapsed_default_snapshot`, `test_cost_rollup_snapshot`, `test_expand_snapshot`, `test_mixed_status_in_run_snapshot`, `test_query_summary_interleaved_breaks_group_snapshot` | PASS |
| v0 fixtures exist for backward-compat test | `ls cores/vault-io/tests/fixtures/round-trip-vault/.code-wiki/traces/`         | Multiple `.jsonl` files present                                     | PASS   |

### Probe Execution

No probes declared in PLAN frontmatter or SUMMARY files for phase 9. Phase 9 is renderer/docs/schema-stamping work; the verification surface is the test suite committed in `test_trace_viewer.py`, `test_pool.py`, and `test_query_summary_schema_version.py`, not a separate `scripts/.../probe-*.sh`. SKIPPED — no applicable probes.

### Requirements Coverage

All three phase requirement IDs are declared in REQUIREMENTS.md §TRACE and mapped to Phase 9 in the Traceability table (currently still marked "Pending" pre-verification; this report attests they are implemented).

| Requirement | Source Plan(s) | Description                                                                                                                  | Status     | Evidence                                                                                                                                                                          |
| ----------- | -------------- | ---------------------------------------------------------------------------------------------------------------------------- | ---------- | -------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| OBS-04      | 09-01, 09-02, 09-05 | `.code-wiki/traces/` JSONL schema is documented and versioned (schema-version field + breaking-change policy)              | SATISFIED  | Producer: `pool.py:212, 251` + `query.py:982` stamp `schema_version: 1`. Doc: `docs/trace-schema.md` 319 lines with breaking-change policy in §3. Consumer: `cli.py:32, 256-273` v0+newer warnings. |
| OBS-05      | 09-03          | `code-wiki-agent trace` renderer surfaces per-subagent cost (input/output tokens × model price) per trace                    | SATISFIED  | `cli.py:323-360` emits per-`(role, model_id)` rollup; `test_cost_rollup_format_six_decimals` + `test_cost_rollup_snapshot` pin the numerics, ordering, `$0.000000` format, `(+K unknown)` and `$n/a` suffixes. |
| OBS-06      | 09-04          | Trace renderer collapses repeated subagent-role groups into a summary line by default, with `--expand` to drill in           | SATISFIED (with caveat) | `cli.py:223-308` collapses runs of ≥2 same-role per-item records; `--expand` flag at L226-230 reverts to full-line. **Caveat:** collapse keys on `role` only (not `(role, model_id)`); see CR-01 in gaps — literal requirement met, model-attribution refinement remains. |

No orphaned requirements: REQUIREMENTS.md Traceability lines 132-134 map only OBS-04, OBS-05, OBS-06 to Phase 9; all three are claimed by the plans above.

### Anti-Patterns Found

| File                                                                | Line | Pattern                                                                                                  | Severity | Impact                                                                                                                                                                                                                                       |
| ------------------------------------------------------------------- | ---- | -------------------------------------------------------------------------------------------------------- | -------- | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|
| `agents/code-wiki-agent/src/code_wiki_agent/cli.py`                 | 303  | Group key uses `role` only; sibling `_aggregate_trace` rollup uses `(role, model_id)` — asymmetric.       | WARNING  | CR-01 — see Gaps. Timeline misrepresents mixed-model fan-outs by collapsing them into one role-only line.                                                                                                                                    |
| `agents/code-wiki-agent/src/code_wiki_agent/cli.py`                 | 124-132 | by_role pass runs before event/kind filter → synthetic `unknown` bucket for query_summary records.       | WARNING  | WR-02 — see Gaps. Snapshot `test_query_summary_interleaved_breaks_group_snapshot` bakes in `unknown: count=1`.                                                                                                                                |
| `agents/code-wiki-agent/src/code_wiki_agent/cli.py`                 | 182-189 | Hardcoded status dict {success, error, cancelled}; unknown statuses dropped; fallback prints `0 success`. | WARNING  | WR-03 — see Gaps. Latent until producers add a new status; would silently lie about success counts then.                                                                                                                                     |
| `agents/code-wiki-agent/src/code_wiki_agent/cli.py`                 | 267  | `isinstance(sv, int)` treats `bool` as int → `schema_version: true` coerces to 1 silently.                | INFO     | WR-01 — latent producer-bug class; not present in real producers but renderer's strict-producer-pinning would miss it.                                                                                                                       |
| `agents/code-wiki-agent/src/code_wiki_agent/cli.py`                 | 178-179, 64-66 | Missing `timestamp` → fallback to `-`; collapsed-group header becomes `[- .. -]`.                  | INFO     | WR-04 — visible in committed snapshot for the query_summary line (`[-] - - - - -ms -->-`). Cosmetic; only triggers on malformed records.                                                                                                     |
| `agents/code-wiki-agent/src/code_wiki_agent/cli.py`                 | 150-153 | `float(cost)` on bad input raises bare `ValueError` with no record context.                              | INFO     | IN-01 — operator-friendliness issue, not correctness.                                                                                                                                                                                         |
| `docs/cancellation.md`                                              | 103-131 | Inline JSON examples lack `schema_version: 1`; intro says they are illustrative.                          | INFO     | IN-04 — minor doc drift; a reader copying an example would produce a v0 record.                                                                                                                                                              |

No debt markers (`TBD`, `FIXME`, `XXX`) found in Phase 9-modified files (`grep` clean).

### Human Verification Required

None. Phase 9 is renderer/docs/schema-stamping work; every observable behavior is grep- or test-suite-verifiable. The committed snapshot tests (`syrupy`) lock the output shape end-to-end through real subprocess invocations of `code-wiki-agent trace`. The real-v0-fixture test exercises the v0 backward-compat path against actual fixtures under `cores/vault-io/tests/fixtures/round-trip-vault/.code-wiki/traces/`. No visual / UX / live-service surface needs a human.

### Gaps Summary

Three gaps surfaced (all carried over from the code-review report `09-REVIEW.md`):

1. **CR-01 (timeline model attribution loss):** The renderer's default-mode collapse keys runs by `role` only. When a `role_model_overrides` sweep produces same-role records on different models, the timeline silently combines them and the line never shows `model_id`. SC#3's literal wording is met (`collapses repeated subagent-role groups`) but the intent — preserving model attribution so an operator can see which item ran where — is broken in exactly the case the cost story is built for. Fix surface area is small (3-4 lines + one new test); recommend addressing before declaring OBS-06 closed, but it is NOT a hard goal blocker since the cost rollup in the Summary block still itemises per `(role, model_id)` and remains the source of truth for cost attribution.

2. **WR-02 (phantom `unknown` role in per-role breakdown):** `_aggregate_trace`'s by_role pass runs before the event/kind filter, so `kind: query_summary` records (with no `role` field) get bucketed under a synthetic `unknown` role. Visible in the committed `test_query_summary_interleaved_breaks_group_snapshot` output as `unknown: count=1 tokens_in=0 tokens_out=0`. Not a roadmap-SC blocker (SC#2's cost rollup correctly excludes event/kind), but it's a baked-in defect surfaced in a snapshot test that should be cleaned up.

3. **WR-03 (collapsed-group breakdown drops unknown statuses):** Latent — only fires if a producer adds a new `status` value beyond {success, error, cancelled}. When it does fire, the line shows `0 success` for an N-record group, which is actively misleading. Should be patched alongside CR-01 since both touch `_render_collapsed_group`.

**Recommendation:** Treat these as a small follow-on plan (3-task wave) rather than re-opening phase 9. All three are localised to `cli.py` and would close cleanly with one update to `test_query_summary_interleaved_breaks_group_snapshot.ambr`. Goal-backward, the three roadmap success criteria are met by the literal wording, but the model-attribution refinement (CR-01) is meaningfully aligned with project intent and should not be deferred to v1.2.

---

_Verified: 2026-05-17_
_Verifier: Claude (gsd-verifier)_
