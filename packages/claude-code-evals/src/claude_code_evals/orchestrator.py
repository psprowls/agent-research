"""run_one(): wire isolation → preflight → runner → verifiers → metrics → artifacts."""

from __future__ import annotations

import json
import subprocess
import time
from dataclasses import dataclass, field
from pathlib import Path

from deepeval.metrics import BaseMetric
from deepeval.test_case import LLMTestCase

from claude_code_evals.isolation import FixtureIsolation, WorktreeIsolation
from claude_code_evals.metrics import compute_metrics
from claude_code_evals.runner import (
    EVAL_SYSTEM_PROMPT_IMPLEMENT,
    EVAL_SYSTEM_PROMPT_QA,
    RunResult,
    run_interactive,
    run_multi_turn,
    run_one_shot,
)
from claude_code_evals.schemas import AutoUser, Config, Scenario
from claude_code_evals.stderr_logger import EvalLogger
from claude_code_evals.transcript import Transcript, parse_transcript
from claude_code_evals.user_simulator import AutoUserSimulator
from claude_code_evals.verify.base import VerifierBase
from claude_code_evals.verify.golden import GoldenVerifier
from claude_code_evals.verify.rubric import RubricVerifier
from claude_code_evals.verify.script import ScriptVerifier


@dataclass
class ScenarioRunResult:
    scenario: Scenario
    config: Config
    scenario_prompt: str
    run_dir: Path
    transcript: Transcript
    metrics: dict
    verify_result: dict
    final_status: str = "success"
    error_reason: str | None = None
    verifier_instances: list[BaseMetric] = field(default_factory=list)


def _resolve_plugin_dirs(plugin_dirs: list[str]) -> list[Path]:
    """Resolve config plugin_dirs to absolute paths (relative ones resolve against cwd)."""
    out: list[Path] = []
    for p in plugin_dirs:
        pd = Path(p)
        out.append(pd if pd.is_absolute() else (Path.cwd() / pd).resolve())
    return out


def run_one(
    scenario: Scenario,
    config: Config,
    *,
    evals_root: Path,
    dry_run: bool = False,
    keep_worktree: bool = False,
) -> ScenarioRunResult:
    """Execute one (scenario × config) run and return results."""
    logger = EvalLogger("orchestrator_scenario_start")
    logger.log_dict(
        "Scenario execution starting",
        {
            "scenario": scenario.name,
            "config": config.name,
            "model": config.model,
            "eval_mode": scenario.eval_mode,
            "isolation_mode": scenario.isolation_mode,
        },
    )

    # Fail fast: GoldenVerifier is incompatible with fixture isolation
    for ve in scenario.verify:
        if ve.kind == "golden" and scenario.isolation_mode == "fixture":
            raise ValueError(
                "GoldenVerifier is incompatible with isolation_mode: fixture. "
                "Use worktree isolation for golden verifiers."
            )

    scenario_dir = evals_root / "scenarios" / scenario.name
    prompt_md = scenario_dir / "prompt.md"
    scenario_prompt = prompt_md.read_text() if prompt_md.exists() else ""

    system_prompt = EVAL_SYSTEM_PROMPT_IMPLEMENT if scenario.eval_mode == "implement" else EVAL_SYSTEM_PROMPT_QA

    IsoClass = WorktreeIsolation if scenario.isolation_mode == "worktree" else FixtureIsolation

    with IsoClass(scenario, config, keep=keep_worktree) as iso:
        logger = EvalLogger("orchestrator_isolation_entered")
        logger.log("Isolation context entered", scenario=scenario.name)

        # Preflight
        preflight_log = ""
        if scenario.preflight:
            preflight_path = scenario_dir / scenario.preflight
            result = subprocess.run(
                [str(preflight_path)],
                cwd=str(iso.worktree_path),
                capture_output=True,
                text=True,
            )
            preflight_log = result.stdout + result.stderr

            logger = EvalLogger("orchestrator_preflight")
            if result.returncode == 0:
                logger.log("Preflight script passed", preflight=scenario.preflight)
            else:
                logger.log("Preflight script failed", preflight=scenario.preflight, return_code=result.returncode)

        if dry_run:
            run_result = RunResult(final_status="dry_run", budget_exceeded=False, wall_seconds=0.0)
            raw_jsonl = ""
        else:
            if not iso.oauth_token:
                raise RuntimeError(
                    "CLAUDE_CODE_OAUTH_TOKEN is not set. Run `claude setup-token` to mint a "
                    "long-lived subscription token and export it as CLAUDE_CODE_OAUTH_TOKEN "
                    "(this bills your subscription, not API credits)."
                )
            logger = EvalLogger("orchestrator_runner_start")
            logger.log("Invoking runner", model=config.model)

            # Load auto_user config if specified (headless multi-turn)
            auto_user: AutoUser | None = None
            if scenario.auto_user:
                auto_user = AutoUser.from_path(Path(scenario.auto_user))

            if scenario.mode == "interactive":
                run_result, raw_jsonl = run_interactive(
                    worktree_path=iso.worktree_path,
                    max_wait_seconds=float(scenario.budgets.max_wall_seconds),
                )
            elif auto_user is not None:
                simulator = AutoUserSimulator(auto_user)
                run_result, raw_jsonl = run_multi_turn(
                    prompt=scenario_prompt,
                    worktree_path=iso.worktree_path,
                    cfg_dir=iso.cfg_dir,
                    system_prompt=system_prompt,
                    simulator=simulator,
                    model=config.model,
                    oauth_token=iso.oauth_token,
                    plugin_dirs=_resolve_plugin_dirs(config.plugin_dirs),
                    extra_env=config.extra_env or None,
                    max_wall_seconds=float(scenario.budgets.max_wall_seconds),
                )
            else:
                run_result, raw_jsonl = run_one_shot(
                    prompt=scenario_prompt,
                    worktree_path=iso.worktree_path,
                    cfg_dir=iso.cfg_dir,
                    system_prompt=system_prompt,
                    model=config.model,
                    oauth_token=iso.oauth_token,
                    plugin_dirs=_resolve_plugin_dirs(config.plugin_dirs),
                    extra_env=config.extra_env or None,
                    max_wall_seconds=float(scenario.budgets.max_wall_seconds),
                )

        transcript = parse_transcript(raw_jsonl)

        # An infra-level failure (auth, CLI crash, no result event) means there's nothing the agent
        # produced to verify — running the LLM judge on an empty transcript only yields a misleading
        # "reason". Skip verifiers and surface the real failure reason instead.
        run_errored = run_result.final_status not in ("success", "completed_interactive", "budget_exceeded", "dry_run")
        if run_errored:
            verifiers: list[VerifierBase] = []
            verify_result = {
                "success": False,
                "error": run_result.error_reason,
                "verifiers": [],
            }
        else:
            # Build verifiers
            verifiers = []
            for ve in scenario.verify:
                vpath = scenario_dir / ve.path
                if ve.kind == "script":
                    verifiers.append(ScriptVerifier(script_path=vpath, worktree_path=iso.worktree_path))
                elif ve.kind == "golden":
                    verifiers.append(GoldenVerifier(patch_path=vpath, worktree_path=iso.worktree_path))
                elif ve.kind == "rubric":
                    verifiers.append(
                        RubricVerifier(
                            rubric_path=vpath,
                            worktree_path=iso.worktree_path,
                            transcript=transcript,
                            judge_model=ve.judge or "claude-haiku-4-5-20251001",
                            pass_threshold=ve.pass_threshold or 4.0,
                        )
                    )

            # Run verifiers
            test_case = LLMTestCase(input=scenario_prompt, actual_output=transcript.final_assistant_text)
            verifier_outcomes = []
            for v in verifiers:
                v.measure(test_case)
                verifier_outcomes.append(
                    {
                        "kind": type(v).__name__,
                        "score": v.score,
                        "passed": v.success,
                        "reason": v.reason,
                    }
                )

            verify_result = {
                "success": all(o["passed"] for o in verifier_outcomes) if verifier_outcomes else True,
                "verifiers": verifier_outcomes,
            }

        metrics = compute_metrics(transcript, verify_result)

        # Write artifacts
        timestamp = str(int(time.time()))
        run_dir = evals_root / "runs" / scenario.name / config.name / timestamp
        run_dir.mkdir(parents=True)

        (run_dir / "transcript.json").write_text(
            json.dumps(
                {
                    "jsonl": raw_jsonl,
                    "parsed": {
                        "turn_count": transcript.turn_count,
                        "input_tokens": transcript.input_tokens,
                        "output_tokens": transcript.output_tokens,
                    },
                },
                indent=2,
            )
        )
        (run_dir / "metrics.json").write_text(json.dumps(metrics, indent=2))
        (run_dir / "verify.json").write_text(json.dumps(verify_result, indent=2))
        (run_dir / "meta.json").write_text(
            json.dumps(
                {
                    "scenario": scenario.name,
                    "config": config.name,
                    "final_status": run_result.final_status,
                    "error_reason": run_result.error_reason,
                    "exit_code": run_result.exit_code,
                    "wall_seconds": run_result.wall_seconds,
                },
                indent=2,
            )
        )
        if preflight_log:
            (run_dir / "preflight.log").write_text(preflight_log)

        logger = EvalLogger("orchestrator_scenario_complete")
        logger.log_dict(
            "Scenario execution complete",
            {
                "scenario": scenario.name,
                "config": config.name,
                "final_status": run_result.final_status,
                "error_reason": run_result.error_reason,
                "wall_seconds": run_result.wall_seconds,
            },
        )

        return ScenarioRunResult(
            scenario=scenario,
            config=config,
            scenario_prompt=scenario_prompt,
            run_dir=run_dir,
            transcript=transcript,
            metrics=metrics,
            verify_result=verify_result,
            final_status=run_result.final_status,
            error_reason=run_result.error_reason,
            verifier_instances=list(verifiers),
        )
