from __future__ import annotations

"""DivergenceMetric: wraps programmatic check pass + GEval LLM-judge pass.

Implements the running mechanism for EVAL-11 + EVAL-12. Returns per-role
results shaped per the D-11 baseline JSON schema:
    {rule_id: {"runs": int, "failures": int, "accepted_failures": [...]}}.

The accepted_failures array (D-13) is built from Verdict.excerpt values,
satisfying EVAL-12's "concrete examples in the report" requirement.

Security:
    T-06-18: Every GEval instantiation passes model=judge explicitly — deepeval
    defaults to OpenAI GPT when model= is omitted, which silently routes calls
    outside Bedrock. The grep gate in test_divergence_metric.py enforces this.
    T-06-19: Excerpts capped at 200 chars; baseline JSON is committed to git
    so excerpts are by definition non-sensitive vault content.
    T-06-20: Judge calls are lazy — only triggered when run_judge() is invoked.
    The programmatic-only path (run_programmatic) requires no Bedrock access.

Exports:
    DivergenceMetric  — per-role metric class with run_programmatic / run_judge / run
    summarize         — builds the D-11 envelope dict for 06-10 to write as JSON
    make_judge        — re-exported from eval_harness.judge (for test import verification)
    JUDGE_PANEL_CONFIG — re-exported from eval_harness.judge (for test import verification)
"""

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Union

from eval_harness.divergence.check import AgentOutputProxy, DivergenceCheck, Verdict
from eval_harness.judge import JUDGE_PANEL_CONFIG, make_judge  # noqa: F401 (re-exported for tests)

# Judge threshold — aligns with the GEval threshold used in judge.py panel_score
_JUDGE_THRESHOLD: float = 0.5

# Explicit role-name -> judge rule ID mapping to avoid ambiguity (e.g. "linter" → "LNT")
_ROLE_JUDGE_ID: dict[str, str] = {
    "librarian": "LIB-JUDGE",
    "ingestor": "ING-JUDGE",
    "linter": "LNT-JUDGE",
    "scanner": "SCN-JUDGE",
}


def _run_check_one(
    check: DivergenceCheck,
    output_proxy: AgentOutputProxy,
    vault: Path,
) -> tuple[bool, str]:
    """Run a single check and return (passed, excerpt).

    Delegates to DivergenceCheck.check which is a pure callable that must not
    eval/exec the output text (T-06-15 constraint lives in check.py).
    """
    verdict: Verdict = check.check(output_proxy, vault)
    return verdict.passed, verdict.excerpt


class DivergenceMetric:
    """Per-role divergence metric composing programmatic checks + GEval judge pass.

    Construction reads the rubric file immediately so missing-rubric errors
    fail fast rather than at judge invocation time.

    Args:
        role:        Role name ("librarian", "ingestor", "linter", "scanner").
        checks:      List of DivergenceCheck instances for this role.
        rubric_path: Path to the per-role judge rubric .md file.
        vault:       Path to the vault root (for wikilink resolution in checks).
    """

    def __init__(
        self,
        role: str,
        checks: list[DivergenceCheck],
        rubric_path: Path,
        vault: Path,
    ) -> None:
        self.role = role
        self.checks = checks
        self.rubric_path = rubric_path
        self.vault = vault
        # Read at construction time — FileNotFoundError surfaces immediately
        self._rubric_text: str = rubric_path.read_text(encoding="utf-8")

    def run_programmatic(
        self,
        outputs: list[tuple[str, AgentOutputProxy]],
    ) -> dict[str, dict]:
        """Run all programmatic checks against each output and aggregate results.

        Args:
            outputs: List of (fixture_id, AgentOutputProxy) pairs.

        Returns:
            Dict keyed by rule_id, each value shaped per D-11:
            {"runs": int, "failures": int, "accepted_failures": [{"fixture": str, "excerpt": str}]}.
        """
        results: dict[str, dict] = {
            c.id: {"runs": 0, "failures": 0, "accepted_failures": []}
            for c in self.checks
        }
        for fixture_id, output in outputs:
            for check in self.checks:
                results[check.id]["runs"] += 1
                passed, excerpt = _run_check_one(check, output, self.vault)
                if not passed:
                    results[check.id]["failures"] += 1
                    results[check.id]["accepted_failures"].append(
                        {
                            "fixture": fixture_id,
                            "excerpt": excerpt[:200],  # cap at 200 chars (T-06-19)
                        }
                    )
        return results

    def run_judge(
        self,
        outputs: list[tuple[str, AgentOutputProxy, str]],
    ) -> dict[str, dict]:
        """Run the GEval LLM-judge pass against the role rubric for each output.

        Judge pass aggregates rubric-level pass/fail per fixture; granular
        judge-only IDs (LIB-005, LIB-006, ING-005, ING-006, LNT-004, LNT-005,
        SCN-005) are encoded as criteria within the rubric text and surface in
        the accepted_failures excerpt as the judge's reason string.

        Lazy-imports deepeval so this module is importable without AWS credentials.
        deepeval/boto3 are only touched when this method is invoked.

        Args:
            outputs: List of (fixture_id, AgentOutputProxy, query) triples.
                     query is the user input that produced the output (GEval INPUT).

        Returns:
            Dict with a single key "{ROLE}-JUDGE" shaped per D-11.
        """
        # Lazy import — prevents boto3/deepeval initialization at module load time
        from deepeval.metrics import GEval  # noqa: PLC0415
        from deepeval.test_case import LLMTestCase, SingleTurnParams  # noqa: PLC0415

        judge_id = _ROLE_JUDGE_ID.get(self.role, f"{self.role[:3].upper()}-JUDGE")
        results: dict[str, dict] = {
            judge_id: {"runs": 0, "failures": 0, "accepted_failures": []}
        }

        for fixture_id, output, query in outputs:
            scores: list[float] = []
            reasons: list[str] = []

            for cfg in JUDGE_PANEL_CONFIG:
                # Fresh instance per call — per RESEARCH anti-pattern (state accumulation)
                judge = make_judge(cfg)
                metric = GEval(
                    name=f"divergence_{self.role}",
                    criteria=self._rubric_text,
                    evaluation_params=[
                        SingleTurnParams.INPUT,
                        SingleTurnParams.ACTUAL_OUTPUT,
                    ],
                    model=judge,  # ALWAYS explicit — never let deepeval default to OpenAI (T-06-18)
                    threshold=_JUDGE_THRESHOLD,
                )
                tc = LLMTestCase(input=query, actual_output=output.answer)
                metric.measure(tc)
                scores.append(metric.score)
                reasons.append(metric.reason or "")

            if not scores:
                # No judges in panel — skip this fixture (JUDGE_PANEL_CONFIG is empty)
                continue
            mean_score = sum(scores) / len(scores)
            results[judge_id]["runs"] += 1
            if mean_score < _JUDGE_THRESHOLD:
                results[judge_id]["failures"] += 1
                results[judge_id]["accepted_failures"].append(
                    {
                        "fixture": fixture_id,
                        "excerpt": (reasons[0] or "")[:200],  # cap at 200 chars (T-06-19)
                    }
                )

        return results

    def run(
        self,
        outputs: list[tuple[str, AgentOutputProxy, str]],
    ) -> dict[str, dict]:
        """Run both programmatic and judge passes and merge results.

        Implements D-07 hybrid detection: programmatic pass for deterministic
        rules (LIB-001..LIB-004, etc.) merged with judge pass (LIB-JUDGE, etc.).
        Keys do not collide — programmatic uses role-prefixed IDs, judge uses
        "{ROLE}-JUDGE".

        Args:
            outputs: List of (fixture_id, AgentOutputProxy, query) triples.

        Returns:
            Merged D-11-shaped dict from both passes.
        """
        # Programmatic pass needs only (fixture_id, output) — strip the query
        prog_outputs = [(fid, op) for (fid, op, _) in outputs]
        prog_results = self.run_programmatic(prog_outputs)
        judge_results = self.run_judge(outputs)
        return {**prog_results, **judge_results}


_BASELINE_FILENAME_TPL = "divergence-{role}.json"


def load_baseline(role: str, baselines_dir: Path) -> dict:
    """Return the per-role baseline JSON dict, or {} when file is missing (RESEARCH §Pitfall 5).

    Args:
        role:          Role name (e.g. "librarian").
        baselines_dir: Directory containing divergence baseline JSON files.

    Returns:
        Parsed JSON dict, or {} if the file does not exist.
    """
    path = baselines_dir / _BASELINE_FILENAME_TPL.format(role=role)
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def write_baseline(role: str, baselines_dir: Path, results: dict, agent_commit: str) -> Path:
    """Write a D-11 schema baseline JSON file for the given role.

    Creates baselines_dir if it does not exist. Uses the summarize() function to
    build the envelope, then writes with json.dumps(..., indent=2) + "\\n" per the
    JSON write pattern in PATTERNS.md.

    Args:
        role:          Role name (e.g. "librarian").
        baselines_dir: Directory to write baseline JSON files to.
        results:       Output from run_programmatic() or run() — keyed by rule_id.
        agent_commit:  Git SHA of the agent being evaluated.

    Returns:
        The Path of the written baseline JSON file.
    """
    envelope = summarize(role, results, agent_commit)
    baselines_dir.mkdir(parents=True, exist_ok=True)
    path = baselines_dir / _BASELINE_FILENAME_TPL.format(role=role)
    path.write_text(json.dumps(envelope, indent=2) + "\n", encoding="utf-8")
    return path


def check_regression(role: str, current: dict, baseline: dict) -> None:
    """Gate regression: raise AssertionError if any hard-severity rule's failures exceed baseline.

    Soft-severity differences (including all *-JUDGE entries) are not raised —
    judge non-determinism per RESEARCH §Pitfall 2 makes hard-gating judges inappropriate.

    Args:
        role:     Role name (e.g. "librarian") — used to look up severity from ROLE_CHECKS.
        current:  Current results dict keyed by rule_id (same shape as run_programmatic output).
        baseline: Loaded baseline dict from load_baseline() — the D-11 envelope.

    Raises:
        AssertionError: When a hard-severity rule's current failures exceed the baseline count.
    """
    from eval_harness.divergence import ROLE_CHECKS  # lazy import to avoid circularity

    severity_lookup: dict[str, str] = {
        c.id: c.severity for c in ROLE_CHECKS.get(role, [])
    }

    baseline_checks = baseline.get("checks", {})

    for rule_id, rule_data in current.items():
        # Judge-only aggregate IDs (e.g. LIB-JUDGE) are always soft — judge non-determinism
        if rule_id.endswith("-JUDGE"):
            severity = "soft"
        else:
            # Defensive default: unknown rule_id treated as soft
            severity = severity_lookup.get(rule_id, "soft")

        baseline_failures: int = baseline_checks.get(rule_id, {}).get("failures", 0)
        current_failures: int = rule_data["failures"]

        if severity == "hard" and current_failures > baseline_failures:
            raise AssertionError(
                f"[{role}] {rule_id}: {current_failures} failures > baseline "
                f"{baseline_failures}. Run with --accept-divergence-baseline to accept."
            )


def summarize(role: str, results: dict, agent_commit: str) -> dict:
    """Build the D-11 schema envelope for 06-10 to write as baseline JSON.

    Args:
        role:         Role name (e.g. "librarian").
        results:      Output from run_programmatic() or run() — keyed by rule_id.
        agent_commit: Git SHA of the agent being evaluated.

    Returns:
        Dict with keys: role, recorded_at (ISO UTC), agent_commit, checks.
        Matches the D-11 baseline JSON schema defined in CONTEXT.md.
    """
    return {
        "role": role,
        "recorded_at": datetime.now(tz=timezone.utc).isoformat(),
        "agent_commit": agent_commit,
        "checks": results,
    }
