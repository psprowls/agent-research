"""Headless runner: spawns claude -p in one-shot or multi-turn mode."""

from __future__ import annotations

import json
import os
import subprocess
import time
from dataclasses import dataclass
from pathlib import Path

from claude_code_evals.user_simulator import AutoUserSimulator

EVAL_SYSTEM_PROMPT_QA = (
    "EVAL MODE (Q&A): This session runs inside an automated headless evaluation of a "
    "question-and-answer task. Answer the user's question directly using only read-only "
    "tools (Read, Glob, Grep, Bash for read-only commands). Do NOT call Edit or Write, "
    "and do NOT use Bash to modify files, install packages, run builds, or run tests — "
    "the prompt is asking for an answer, not an implementation. Do NOT pause to ask "
    "clarifying questions or present designs for approval. End your final reply with "
    "<DONE> on its own line once the answer is complete."
)

EVAL_SYSTEM_PROMPT_IMPLEMENT = (
    "EVAL MODE (IMPLEMENT): This session runs inside an automated headless evaluation of an "
    "implementation task. Implement the requested changes using all available tools. Do NOT "
    "pause to ask clarifying questions or present designs for approval — proceed directly "
    "to implementation. End your final reply with <DONE> on its own line once complete."
)


@dataclass
class RunResult:
    final_status: str  # "success" | "budget_exceeded" | "error_*"
    budget_exceeded: bool
    wall_seconds: float
    simulator_input_tokens: int = 0
    simulator_output_tokens: int = 0


def _build_cmd(
    *,
    prompt: str,
    cfg_dir: Path,
    system_prompt: str,
    model: str,
    multi_turn: bool = False,
) -> list[str]:
    """Build subprocess command list. Security: always a list, prompt is final element."""
    cmd = [
        "claude",
        "-p",
        "--output-format",
        "stream-json",
        "--verbose",
        "--system-prompt",
        system_prompt,
        "--model",
        model,
        "--config-dir",
        str(cfg_dir),
    ]
    if multi_turn:
        cmd += ["--input-format", "stream-json", "--replay-user-messages"]
    cmd.append(prompt)
    return cmd


def run_one_shot(
    *,
    prompt: str,
    worktree_path: Path,
    cfg_dir: Path,
    system_prompt: str,
    model: str = "claude-sonnet-4-6",
    extra_env: dict[str, str] | None = None,
    max_wall_seconds: float = 300.0,
    _max_input_tokens: int = 100_000,
) -> tuple[RunResult, str]:
    """Run claude -p one-shot. Returns (RunResult, raw_jsonl_string)."""
    env = _build_env(extra_env)
    cmd = _build_cmd(
        prompt=prompt,
        cfg_dir=cfg_dir,
        system_prompt=system_prompt,
        model=model,
    )

    proc = subprocess.Popen(
        cmd,
        cwd=str(worktree_path),
        env=env,
        stdin=subprocess.DEVNULL,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        bufsize=1,
    )

    start = time.monotonic()
    final_status = "success"
    budget_exceeded = False
    lines: list[str] = []

    try:
        assert proc.stdout is not None
        for line in proc.stdout:
            if (time.monotonic() - start) > max_wall_seconds:
                budget_exceeded = True
                final_status = "budget_exceeded"
                break
            lines.append(line)
            line_str = line.strip()
            if not line_str:
                continue
            try:
                ev = json.loads(line_str)
            except json.JSONDecodeError:
                continue
            if ev.get("type") == "result":
                subtype = ev.get("subtype", "success")
                final_status = subtype if subtype != "success" else "success"
                break
    finally:
        proc.terminate()
        proc.wait(timeout=5)

    return (
        RunResult(final_status=final_status, budget_exceeded=budget_exceeded, wall_seconds=time.monotonic() - start),
        "".join(lines),
    )


def run_multi_turn(
    *,
    prompt: str,
    worktree_path: Path,
    cfg_dir: Path,
    system_prompt: str,
    simulator: AutoUserSimulator,
    model: str = "claude-sonnet-4-6",
    extra_env: dict[str, str] | None = None,
    _max_turns: int = 20,
    max_wall_seconds: float = 300.0,
    _max_input_tokens: int = 100_000,
) -> tuple[RunResult, str]:
    """Run claude -p in multi-turn mode driven by AutoUserSimulator."""
    env = _build_env(extra_env)
    cmd = _build_cmd(
        prompt=prompt,
        cfg_dir=cfg_dir,
        system_prompt=system_prompt,
        model=model,
        multi_turn=True,
    )

    proc = subprocess.Popen(
        cmd,
        cwd=str(worktree_path),
        env=env,
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        bufsize=1,
    )

    start = time.monotonic()
    final_status = "success"
    budget_exceeded = False
    lines: list[str] = []
    last_assistant_text = ""

    try:
        assert proc.stdout is not None and proc.stdin is not None
        for line in proc.stdout:
            if (time.monotonic() - start) > max_wall_seconds:
                budget_exceeded = True
                final_status = "budget_exceeded"
                break
            lines.append(line)
            line_str = line.strip()
            if not line_str:
                continue
            try:
                ev = json.loads(line_str)
            except json.JSONDecodeError:
                continue
            if ev.get("type") == "assistant":
                for block in (ev.get("message") or {}).get("content") or []:
                    if block.get("type") == "text":
                        last_assistant_text += block.get("text", "")
            elif ev.get("type") == "result":
                reply = simulator.reply(last_assistant_text)
                if reply is None:
                    break
                last_assistant_text = ""
                user_msg = json.dumps({"type": "user", "message": {"role": "user", "content": reply}})
                proc.stdin.write(user_msg + "\n")
                proc.stdin.flush()
    finally:
        proc.terminate()
        proc.wait(timeout=5)

    return (
        RunResult(
            final_status=final_status,
            budget_exceeded=budget_exceeded,
            wall_seconds=time.monotonic() - start,
            simulator_input_tokens=simulator.input_tokens,
            simulator_output_tokens=simulator.output_tokens,
        ),
        "".join(lines),
    )


def _build_env(extra_env: dict[str, str] | None) -> dict[str, str]:
    env = os.environ.copy()
    env["CLAUDE_CODE_DISABLE_AUTO_MEMORY"] = "1"
    if extra_env:
        env.update(extra_env)
    return env
