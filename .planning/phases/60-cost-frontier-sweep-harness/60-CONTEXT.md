# Phase 60: Cost-Frontier Sweep Harness — Context

**Gathered:** 2026-05-30
**Status:** In progress (retroactive scaffold — most sub-work already landed as quick tasks since v1.10)
**Milestone:** v1.11 — Cost-Frontier Sweep Harness
**Git range:** `846459a` → `b65ad7e` (HEAD) · 37 commits

<domain>
## Phase Boundary

Repair the cost-frontier model sweep so a **clean, trustworthy per-role sweep**
can run on AWS Bedrock and produce a defensible per-role winner table — then pick
winners. This revisits and hardens the original **v1.1 Phase 7 "Cost-Frontier
Sweep"**; the harness had accumulated several bugs that made the sweep
unrunnable or its output untrustworthy.

This phase is the home for **all cost-frontier-sweep work done since v1.10
closed** (it was executed as a chain of `/gsd-quick` tasks before this milestone
existed) **plus** the remaining debug + clean-re-run + winner-selection work.

**In scope:** the sweep runner (`eval-harness/sweep.py`), the two-gate logic
(`two_gate.py`), divergence wiring (`divergence/metric.py`), the judge panel
(`judge.py`), the model-adapter content normalizer (`model-adapter/loader.py`),
per-command model-override plumbing (`graph-wiki-agent/commands/*`), and
`models.toml` sweep candidates / judge panel.

**Out of scope:** auto-rewriting `models.toml` winners (humans pick); the wider
v1.10 deferred items (entity `## Related`, milestone audits).
</domain>

<completed>
## Completed sub-work (quick-task lineage, all on `main`)

| Quick task | Fix | Key commits | What landed |
|-----------|-----|-------------|-------------|
| `260529-na9` | candidate refresh | `6206c70` `60c8d77` `0996c32` `4196777` | Refreshed `models.toml` sweep candidates + judge panel for the 2026-05-29 queue; reconciled qwen3-32b pricing. |
| `260529-ox1` | env fix | `e42ae87` `09236a2` `92c210a` `1fa57cf` | `EvalWorktree` provisions an initialized graph-io DB so ingestor sweep cells can run. |
| `260529-pf8` | test hygiene | `07c81ea` `0c6a52f` `9a0ce90` | Updated stale config-pinning tests after the na9 refresh (Haiku global, qwen3 price, retired D-03 tier map). Suite green (1580). |
| `260529-pzd` | **Fix B** | `b81c9b0` `02ee3fe` `9f19ecd` | `model-adapter` normalizes list-shaped ("thinking"/multi-block) `response.content` → `str`, preserving reasoning on `additional_kwargs["reasoning"]`; covers invoke + ainvoke. |
| `260529-q8r` | **Fix C** | `e810d6a` `43c9dd6` `21be485` | Wired per-role `DivergenceMetric` + `baselines_dir` into `run_full_matrix` (Gate 1 was hardcoded `None` → auto-FAIL for every candidate). |
| `260529-sot` | **Fix D+E+F** | `07c709f` `3dfeae9` `e9cd8b1` `0798b69` `09936b4` | D: routed 6 model-override branches through `make_llm`. E: rate-based Gate 1 + empty-output disqualification. F: populated `SweepResult.judge_scores` with a real quality signal. |
| `260529-sot` (follow-up) | **Fix D (7th branch)** | `aaa3d63` | Routed the code-fallback synthesizer in `query.py:_run_code_fallback` through `make_llm("synthesizer", model_override=...)`. |
| diagnostic run | — | `8cf091a` | `$7.02` 2026-05-29 run docs committed but labeled **NOT authoritative** (broken Gate 1 + 4 missing models). To be overwritten by the clean run. |
| handoffs | — | `ac854c4` `72e085c` `b65ad7e` | Rounds 1–3 continuation notes. Round 3 is current. |

A clean `$3.46` full re-run then **verified Fixes D/E/F mechanically** but is
**NOT authoritative**: judge-able quality (librarian/synthesizer) collapsed.
Root cause scoped — see `.planning/CONTINUE-sweep-harness-fixes-3.md`.
</completed>

<remaining>
## Remaining work (the open part of this phase)

Tracked in full in `.planning/CONTINUE-sweep-harness-fixes-3.md`:

1. **Debug answer degradation** (round 3) — Fix B's `_normalize_content` likely
   empties thinking-model answers (synthesizer ~$0.0004/cell); a separate
   librarian low-score signature; `cost=N/A` pervasive (follow-up "G"). Capture
   real answer samples; fix the normalizer; add regression tests.
2. **Clean full re-run** — full 39-cell driver, `repeats=3`, judges on
   (~$7, hard cap $25). Confirm with Pat + check the Bedrock daily-token quota
   has reset (last run hit a `ThrottlingException`).
3. **Authoritative docs + winners** — verify judge-able roles discriminate,
   overwrite-commit `.planning/sweep/*.md` + `INDEX.md` (replacing `8cf091a`),
   then help Pat pick per-role winners.
</remaining>

<success_criteria>
## Success Criteria

- [ ] A clean full sweep run where judge-able roles (librarian/synthesizer)
      **discriminate** (not all ~0), structural roles vary, and cost is
      populated (no `N/A`).
- [ ] Authoritative `.planning/sweep/*.md` + `INDEX.md` committed, replacing the
      diagnostic `8cf091a`.
- [ ] Per-role winners selected by Pat; `models.toml` updated by human decision.
- [ ] Full suite green (`uv run pytest -q`).
</success_criteria>
