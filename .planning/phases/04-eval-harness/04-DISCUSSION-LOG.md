# Phase 4: Eval Harness - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md — this log preserves the alternatives considered.

**Date:** 2026-05-14
**Phase:** 4-Eval Harness
**Areas discussed:** Fixture corpus, Baseline recorder, Judge B model

---

## Fixture Corpus

### Q1: Can the existing round-trip vault serve as the query eval fixture?

| Option | Description | Selected |
|--------|-------------|----------|
| Reuse the round-trip vault | It already has real wiki structure — packages, plugins, index.md. Single source of truth. | ✓ |
| Build new query-specific fixtures | Round-trip vault is sparse; richer content for more meaningful eval results. | |
| Both — round-trip vault + 1 new | Existing as fixture-A, one new richer fixture as fixture-B. | |

**User's choice:** Reuse the round-trip vault (Recommended)
**Notes:** Straightforward call — the existing vault has real content and covers the structure query needs.

### Q2: Where should eval artifacts (baselines, result JSONs) live?

| Option | Description | Selected |
|--------|-------------|----------|
| cores/eval-harness/eval/ | Co-located with the harness package itself. | |
| Top-level eval/ directory | Visible from repo root; easier to find. | ✓ |
| agents/code-wiki-agent/eval/ | Co-located with the agent being evaluated (but EVAL-01 requires separate package). | |

**User's choice:** Top-level eval/ directory
**Notes:** Visibility from repo root was the deciding factor.

### Q3: How to define test cases?

| Option | Description | Selected |
|--------|-------------|----------|
| JSON file of (query, expected_answer) pairs in eval/cases/ | Simple, version-controlled, easy to extend. | ✓ |
| Derived from baseline only — no pre-defined expected answers | Record current lattice-wiki output as oracle; no hand-authored answers needed. | |
| Both — structural cases (JSON) + baseline similarity | Two complementary scoring layers. | |

**User's choice:** JSON file of (query, expected_answer) pairs committed to eval/cases/
**Notes:** Clean separation — cases define what to test, baselines define the oracle for LLM-judge scoring.

---

## Baseline Recorder

### Q1: How should the baseline recorder invoke lattice-wiki?

| Option | Description | Selected |
|--------|-------------|----------|
| Import lattice-wiki-core Python directly | Faster, no Claude Code dep, but less faithful to actual tool behavior. | |
| Subprocess to lattice-wiki via Claude Code CLI | Most faithful — captures real tool including model behavior. | ✓ |
| Pre-committed snapshots only — no recorder infra | Baselines are manually authored JSON files; simplest, but hard to re-record. | |

**User's choice:** Subprocess to lattice-wiki via Claude Code CLI
**Notes:** Faithfulness matters — the baseline must reflect what the actual Claude Code + lattice-wiki plugin produces, not just the Python layer.

### Q2: How closely should cores/eval-harness follow lattice-evals?

| Option | Description | Selected |
|--------|-------------|----------|
| Port the pattern — replicate headless runner + verifier structure | Independent package, no lattice-evals dep. Full ownership. | ✓ |
| Import lattice-evals as a dev dep for baseline recording only | Leaner but couples to lattice-evals. | |
| Simpler — baseline recorder is just a shell script + committed snapshots | Skip the Python harness for recording. | |

**User's choice:** Port the pattern
**Notes:** User referenced `lattice-evals` package at `/Users/pat/Personal/lattice/packages/lattice-evals` as the reference implementation. Key files: `runner_headless.py`, `orchestrator.py`, `isolation.py`, `pricing.py`.

### Q3: Does the model sweep need git worktree isolation?

| Option | Description | Selected |
|--------|-------------|----------|
| No worktree needed — query is read-only, runs share the fixture vault | Simpler; all models read identical input. | |
| Yes, worktree per run — match lattice-evals pattern exactly | Future-proofs for write commands (scan, lint). | ✓ |

**User's choice:** Yes, worktree per run
**Notes:** Consistency with the ported pattern + forward compatibility for Phase 5 write commands.

---

## Judge B Model

### Q1: Which non-Claude Bedrock model should be judge_b?

| Option | Description | Selected |
|--------|-------------|----------|
| Amazon Nova Pro | Native Bedrock, strong instruction-following, no extra IAM grants. | ✓ |
| Meta Llama 3.1 70B Instruct | Strong open-source judge, requires Llama model access grant. | |
| Amazon Nova Lite | Cheapest but may be weaker for judging. | |

**User's choice:** Amazon Nova Pro (Recommended)
**Notes:** Straightforward — native to Bedrock, already within Pat's IAM setup.

### Q2: What should the initial librarian sweep candidates be?

| Option | Description | Selected |
|--------|-------------|----------|
| Haiku 4.5 + Sonnet 4.6 + Nova Micro | Claude cheap / Claude quality / non-Claude. | |
| Haiku 4.5 + Nova Lite + Nova Pro | Claude vs Amazon at multiple price points. | |
| Researcher verifies | Researcher picks candidates that span the cost spectrum. | |

**User's choice:** Haiku 4.5 + Nova Lite + Kimi K2.5 (free-text)
**Notes:** User specified Kimi K2.5 (not "Kimi K2.5 Thinking") as the third candidate. Researcher to verify the exact Bedrock model ID / cross-region ARN for Pat's account.

### Q3: Kimi K2.5 ARN — known or researcher verifies?

| Option | Description | Selected |
|--------|-------------|----------|
| Researcher verifies the ARN | Model may have different ARN formats depending on region/inference profile. | ✓ |
| I know the ARN | User would provide the exact model ID. | |

**User's choice:** Researcher verifies (but model is Kimi K2.5, not Kimi K2.5 Thinking)
**Notes:** User confirmed the model name but deferred ARN lookup to researcher.

---

## Claude's Discretion

- `eval/cases/` JSON schema — planner designs (suggest: `query`, `expected_answer`, optional `tags`)
- `eval/baselines/` JSON structure — planner designs (must include ARN, timestamp, vault content hash per EVAL-08)
- `eval/runs/` gitignore status — planner decides
- deepeval GEval metric prompt — what the judge scores; planner designs
- Bedrock pricing table extension for Nova Lite, Nova Pro, Kimi K2.5
- `IsolationContext` implementation details (git worktree vs. temp-dir copy)
- Whether `pytest-evals` is an available package or if `@pytest.mark.eval` is sufficient

## Deferred Ideas

- Eval for scan/lint/ingest/log commands — Phase 5 concern; those commands don't exist yet
- A/B prompt regression suite — V2-EVAL-03
- Confidence calibration — V2-EVAL-01
- `pytest-evals` package investigation — planner determines availability and whether needed
