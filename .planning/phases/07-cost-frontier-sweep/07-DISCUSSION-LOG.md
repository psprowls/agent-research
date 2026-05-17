# Phase 7: Cost-Frontier Sweep - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md — this log preserves the alternatives considered.

**Date:** 2026-05-16
**Phase:** 7-cost-frontier-sweep
**Areas discussed:** Role coverage, Candidate model matrix, Per-role quality signal, Frontier pick + swap policy

---

## Role coverage

### Q1: Which roles should the sweep actually cover?

| Option | Description | Selected |
|--------|-------------|----------|
| Six agent roles (no judges) | librarian, code_reader, scanner, linter, ingestor, synthesizer. Skip judge_a/judge_b. (Recommended) | |
| Seven roles (six + one judge) | Same six + one judge sweep using agreement-only signal. | |
| All 8 roles including both judges | Sweep judges too; risk re-baselining the panel. | ✓ |
| Exclude code_reader too | Only the five roles with judge/divergence signals + synthesizer. | |

**User's choice:** All 8 roles including both judges
**Notes:** User initially picked all-8; follow-up question on judge-swap policy surfaced the Phase-6 baseline conflict and user reversed (see Q2).

### Q2: Judges are in the sweep. How should judge-model changes interact with Phase 6's divergence baselines?

| Option | Description | Selected |
|--------|-------------|----------|
| Sweep judges, agreement-only signal (Recommended) | Score on inter-judge agreement and position-bias delta, not divergence/quality. | |
| Sweep judges with full quality eval | N² cost; forces baseline re-record. | |
| Sweep judges but don't auto-swap | Publish frontier, require follow-up plan. | |
| Sweep judges and re-record baselines unconditionally | Treat new baseline as the new normal. | |

**User's choice (free text):** "Actually, let's exclude the judges from the sweep."
**Notes:** Final lock: sweep 6 agent roles only. SWEEP-01's "7 roles" wording flagged as inaccurate; planner to reconcile.

---

## Candidate model matrix

### Q1: How should the candidate model set be structured per role?

| Option | Description | Selected |
|--------|-------------|----------|
| Uniform set, all 6 roles (Recommended) | Same 6-candidate list for every role. 36 cells. | |
| Role-tiered sets | Cheap-fast / Mid / Quality tiers; 24 cells. | ✓ |
| Uniform but smaller | Drop nova-micro; 5 × 6 = 30 cells. | |
| Defined in models.toml or sweep-config file | Config-driven candidate matrix. | |

**User's choice:** Role-tiered sets

### Q2: Tier assignments — are these groupings right, or would you regroup?

| Option | Description | Selected |
|--------|-------------|----------|
| Keep proposed tiers (Recommended) | Cheap-fast: scanner+code_reader; Mid: linter+ingestor+librarian; Quality: synthesizer. | |
| Move librarian to quality tier | Librarian answers user queries; quality-leaning. | ✓ |
| Move code_reader to mid tier | Needs decent comprehension. | |
| Custom — I'll specify | User-defined grouping. | |

**User's choice:** Move librarian to quality tier
**Notes:** Final tiers: Cheap-fast = scanner+code_reader; Mid = linter+ingestor; Quality = librarian+synthesizer.

### Q3: Where do the per-role candidate lists live?

| Option | Description | Selected |
|--------|-------------|----------|
| New sweep.toml at repo root (Recommended) | Separate sweep concerns from production defaults. | |
| Extend models.toml with sweep_candidates | Add `sweep_candidates = [...]` to each `[roles.{name}]` block. | ✓ |
| Hardcode in sweep.py / test_sweep_eval.py | Python constants. | |
| Pricing.py is the source | Intersect PRICES with per-role tier. | |

**User's choice:** Extend models.toml with sweep_candidates

---

## Per-role quality signal

### Q1: How should code_reader and synthesizer be scored during the sweep?

| Option | Description | Selected |
|--------|-------------|----------|
| End-to-end query score, swap one role at a time (Recommended) | Reuse judge panel + structural; no new fixtures for synthesizer. | ✓ |
| End-to-end + add a code_reader-specific fixture set | Add 3–5 vault-thin queries to force code_reader to fire. | |
| Quick-add minimal divergence rules for both | Author 5–8-check rule sets each. | |
| Skip those two — keep current defaults | Only sweep the 4 roles with Phase-6 rubrics. | |

**User's choice:** End-to-end query score, swap one role at a time (Recommended)

### Q2: For the four roles WITH Phase-6 divergence rubrics — primary quality signal?

| Option | Description | Selected |
|--------|-------------|----------|
| Divergence rate + end-to-end score, both required (Recommended) | Two gates; either fails → disqualified. | ✓ |
| Divergence rate as primary, query score as tiebreaker | Filter by divergence first; cost tiebreaker. | |
| End-to-end query score only | Uniform protocol; ignore divergence during sweep. | |
| Divergence rate only — no judge runs during sweep | Lightest; skip judge panel. | |

**User's choice:** Divergence rate + end-to-end score, both required (Recommended)

### Q3: Does code_reader need fixture queries that force it to fire?

| Option | Description | Selected |
|--------|-------------|----------|
| Add 3–5 vault-thin queries (Recommended) | Author queries whose answers must come from source code. | ✓ |
| Skip — measure only when it naturally fires | Record N/A if fallback doesn't trigger. | |
| Force code_reader on every query for the sweep | Sweep-only flag forcing the fallback path. | |

**User's choice:** Add 3–5 vault-thin queries (Recommended)

---

## Frontier pick + swap policy

### Q1: How is the "cost-optimal pick" per role chosen from the sweep results?

| Option | Description | Selected |
|--------|-------------|----------|
| Cheapest model within 5% of best quality (Recommended) | Single deterministic rule; threshold config constant. | |
| Pareto frontier published, human picks | Emit Pareto frontier; user picks via manual edit. | ✓ |
| Cheapest model that beats divergence baseline + current default's quality | Conservative; fewer swaps. | |
| Tier-relative threshold (different X% per tier) | Different thresholds per tier. | |

**User's choice:** Pareto frontier published, human picks

### Q2: How does the sweep result update models.toml?

| Option | Description | Selected |
|--------|-------------|----------|
| Manual edit, sweep emits a recommendation block (Recommended) | Sweep writes comment block; user edits default by hand. | ✓ |
| Sweep auto-writes models.toml with previous default as comment | In-place rewrite when a clear winner exists. | |
| Sweep proposes a diff file, user applies via git | models.toml.proposed sidecar. | |

**User's choice:** Manual edit, sweep emits a recommendation block (Recommended)

### Q3: Where does the results doc live and what format?

| Option | Description | Selected |
|--------|-------------|----------|
| .planning/SWEEP-RESULTS.md + CSV sidecar (Recommended) | Single MD + raw CSV for tooling. | |
| docs/cost-frontier.md only (markdown) | OSS-friendly single doc. | |
| Per-role docs under .planning/sweep/ | One MD per role + INDEX.md. | ✓ |
| Inside the phase dir + summary doc at top | Raw artifacts in phase dir; polished story in docs/. | |

**User's choice:** Per-role docs under .planning/sweep/

### Q4: Budget guardrails — how do we cap sweep cost before kicking off?

| Option | Description | Selected |
|--------|-------------|----------|
| Pre-flight cost estimate + dry-run mode (Recommended) | Estimate cost, prompt to proceed; --dry-run for plumbing; hard cap. | ✓ |
| Hard env-var cap, no pre-flight | Abort mid-run when running cost exceeds budget. | |
| Repeats per cell controlled, trust pricing.py | Set repeats=3, run, log. | |
| No guardrails — run once, see what it cost | Add later if it stings. | |

**User's choice:** Pre-flight cost estimate + dry-run mode (Recommended)

---

## Claude's Discretion

- Exact name/layout of the cost-story doc (`.planning/sweep/STORY.md` vs `docs/cost-frontier.md` vs other).
- Whether `sweep_candidates` is a sibling key under `[roles.{name}]` or a nested `[roles.{name}.sweep]` table.
- Exact "within bounds" threshold for the end-to-end gate (suggested: 5% quality-tier, 10% mid/cheap-fast).
- Repeats-per-cell (default suggestion: 3).
- Whether to add a `--role <name>` flag for re-sweeping a single role.

## Deferred Ideas

- Judge model swaps (out of scope; would need a dedicated mini-phase that re-runs Phase 6 baseline acceptance after).
- Divergence rubrics for synthesizer and code_reader (defer until end-to-end scoring proves noisy).
- Tier-relative auto-pick threshold (declined in favor of human Pareto review).
- In-place `models.toml` rewrite by the sweep tool (declined; reconsider if manual swaps prove tedious).
- Repeats-per-cell tuning / variance reporting (default 3; tune if winners are unclean).
- Sample-run calibration for the pre-flight estimator (planner decides).
- `docs/cost-frontier.md` for OSS audiences (re-home from `.planning/sweep/` when OSS release happens).
