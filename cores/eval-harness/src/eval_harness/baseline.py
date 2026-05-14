from __future__ import annotations

"""Headless baseline recorder: spawn `claude -p` and snapshot the output.

Ported from lattice-evals/runner_headless.py with the following sections
dropped (lattice-wiki-specific, not needed in eval-harness):
  - auto_user / multi-turn stdin management
  - _select_reply() user simulator
  - _validate_credentials() OAuth check
  - _add_worktree() / _remove_wiki() / _build_cfg_dir()
  - simulator_* fields from RunResult

New additions (specific to eval-harness):
  - _vault_content_hash(): stable hash of all .md files in the vault
  - _prompt_hash(): sha256 of (case_id, query, system_prompt)
  - BaselineRecorder: loads cases JSON, records one snapshot per case

Security (T-4-03): _build_cmd() always returns a list; subprocess is
never launched with shell=True; prompt is always the final element of the
command list (cmd.append(prompt)), never interpolated into a shell string.

Security (T-4-01): case_id is sanitized before use as a filename component
via re.sub(r"[^a-zA-Z0-9._-]", "_", case_id).

Security (T-4-05): vault_path is caller-provided and is not user-input;
case_id sanitization is the only filename-construction security control.
"""

import asyncio
import hashlib
import json
import re
import subprocess
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from eval_harness.isolation import EvalWorktree

# ---------------------------------------------------------------------------
# Eval system prompt (ported verbatim from lattice-evals/runner_headless.py)
# ---------------------------------------------------------------------------

EVAL_SYSTEM_PROMPT_QA = (
    "EVAL MODE (Q&A): This session runs inside an automated headless evaluation of a "
    "question-and-answer task. Answer the user's question directly using only read-only "
    "tools (Read, Glob, Grep, Bash for read-only commands). Do NOT call Edit or Write, "
    "and do NOT use Bash to modify files, install packages, run builds, or run tests — "
    "the prompt is asking for an answer, not an implementation. Do NOT pause to ask "
    "clarifying questions or present designs for approval. End your final reply with "
    "<DONE> on its own line once the answer is complete."
)

# ---------------------------------------------------------------------------
# Data model
# ---------------------------------------------------------------------------


@dataclass
class RunResult:
    """Result from a single headless claude -p run."""

    final_status: str  # "success" | "budget_exceeded" | "error"
    budget_exceeded: bool
    wall_seconds: float
    turns: int


# ---------------------------------------------------------------------------
# Command construction (security-critical; always list form)
# ---------------------------------------------------------------------------


def _build_cmd(
    *,
    prompt: str,
    worktree_path: Path,
    system_prompt: str,
    plugin_dirs: list[Path] | None,
    model_override: str | None,
) -> list[str]:
    """Build the subprocess command list for a one-shot claude -p run.

    Security invariants (T-4-03):
    - cmd is always a list — never a string joined for shell execution
    - shell=False is implicit (subprocess.Popen default when cmd is a list)
    - prompt is always the final element (cmd.append(prompt)), never
      string-interpolated into the command
    - assert isinstance(cmd, list) at the end makes the invariant explicit
    """
    cmd: list[str] = [
        "claude",
        "-p",
        "--output-format",
        "stream-json",
        "--verbose",
        "--add-dir",
        str(worktree_path),
        "--append-system-prompt",
        system_prompt,
    ]
    for pdir in plugin_dirs or []:
        cmd += ["--plugin-dir", str(pdir)]
    if model_override:
        cmd += ["--model", model_override]
    # Prompt is ALWAYS the final positional argument (one-shot mode only).
    # Never f-string interpolate the prompt into the command.
    cmd.append(prompt)
    assert isinstance(cmd, list)  # T-4-03 defensive guard
    return cmd


# ---------------------------------------------------------------------------
# Subprocess spawner
# ---------------------------------------------------------------------------


def _spawn(
    cmd: list[str],
    *,
    cwd: str,
    env: dict[str, str] | None = None,
) -> subprocess.Popen[str]:
    """Spawn the claude subprocess.

    shell=False is the default when cmd is a list; stdin is DEVNULL for
    one-shot mode (no multi-turn stdin management needed here).
    """
    return subprocess.Popen(
        cmd,
        cwd=cwd,
        env=env,
        stdin=subprocess.DEVNULL,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        bufsize=1,
    )


# ---------------------------------------------------------------------------
# Headless runner
# ---------------------------------------------------------------------------


def run_headless(
    *,
    prompt: str,
    worktree_path: Path,
    system_prompt: str = EVAL_SYSTEM_PROMPT_QA,
    plugin_dirs: list[Path] | None = None,
    model_override: str | None = None,
    max_wall_seconds: float = 300.0,
) -> tuple[RunResult, str]:
    """Run claude -p in one-shot mode and return (RunResult, assistant_text).

    Reads stdout as stream-json events. Breaks on ev["type"] == "result".
    Accumulates assistant text from ev["type"] == "assistant" events.

    Returns a tuple of (RunResult, answer_text) where answer_text is the
    concatenated text from all assistant content blocks.
    """
    import os

    env = os.environ.copy()
    env["CLAUDE_CODE_DISABLE_AUTO_MEMORY"] = "1"
    env.pop("ANTHROPIC_API_KEY", None)

    cmd = _build_cmd(
        prompt=prompt,
        worktree_path=worktree_path,
        system_prompt=system_prompt,
        plugin_dirs=plugin_dirs,
        model_override=model_override,
    )

    proc = _spawn(cmd, cwd=str(worktree_path), env=env)

    start = time.monotonic()
    turns = 0
    final_status = "success"
    budget_exceeded = False
    assistant_text = ""

    try:
        while True:
            if (time.monotonic() - start) > max_wall_seconds:
                budget_exceeded = True
                final_status = "budget_exceeded"
                break
            assert proc.stdout is not None
            line = proc.stdout.readline()
            if line == "":
                break
            line_str = line.strip()
            if not line_str:
                continue
            try:
                ev = json.loads(line_str)
            except json.JSONDecodeError:
                continue
            if ev.get("type") == "assistant":
                turns += 1
                msg = ev.get("message", {}) or {}
                for block in msg.get("content", []) or []:
                    if block.get("type") == "text":
                        assistant_text += block.get("text", "")
            elif ev.get("type") == "result":
                break
    finally:
        try:
            proc.terminate()
            proc.wait(timeout=5)
        except Exception:
            pass

    return (
        RunResult(
            final_status=final_status,
            budget_exceeded=budget_exceeded,
            wall_seconds=time.monotonic() - start,
            turns=turns,
        ),
        assistant_text,
    )


# ---------------------------------------------------------------------------
# Hashing helpers
# ---------------------------------------------------------------------------


def _prompt_hash(case_id: str, query: str, system_prompt: str) -> str:
    """Stable sha256 of (case_id, query, system_prompt) concatenated."""
    raw = f"{case_id}|{query}|{system_prompt}".encode()
    return hashlib.sha256(raw).hexdigest()


def _vault_content_hash(vault_path: Path) -> str:
    """Stable sha256 of all .md files in the vault.

    Collects all .md files recursively, sorts by path string for
    determinism, then computes sha256 over their concatenated content
    hashes. Returns hex digest.
    """
    md_files = sorted(vault_path.rglob("*.md"), key=lambda p: str(p))
    h = hashlib.sha256()
    for f in md_files:
        try:
            content = f.read_bytes()
        except OSError:
            continue
        # Hash individual file content and fold into overall hash
        file_hash = hashlib.md5(content).hexdigest()  # noqa: S324
        h.update(file_hash.encode())
    return h.hexdigest()


# ---------------------------------------------------------------------------
# BaselineRecorder
# ---------------------------------------------------------------------------


class BaselineRecorder:
    """Records baseline snapshots for each eval case.

    Loads cases from cases_path (JSON array), runs claude -p in a temporary
    EvalWorktree copy of the vault, and writes one baseline JSON per case
    to baselines_dir.

    Baseline JSON schema (EVAL-08 reproducibility fields):
        case_id            str    - eval case identifier
        query              str    - the query string
        answer             str    - concatenated assistant text
        model_arn          str    - Bedrock model ARN used for recording
        prompt_hash        str    - sha256 of (case_id, query, system_prompt)
        vault_content_hash str    - sha256 of sorted md5s of all .md files
        timestamp_utc      str    - ISO 8601 timestamp of the recording
        seed               None   - always None; claude CLI has no seed param
    """

    def __init__(
        self,
        cases_path: Path,
        vault_path: Path,
        baselines_dir: Path,
        *,
        plugin_dirs: list[Path] | None = None,
        model_arn: str = "us.anthropic.claude-sonnet-4-6",
        system_prompt: str = EVAL_SYSTEM_PROMPT_QA,
    ) -> None:
        self._cases_path = cases_path
        self._vault_path = vault_path
        self._baselines_dir = baselines_dir
        self._plugin_dirs = plugin_dirs
        self._model_arn = model_arn
        self._system_prompt = system_prompt

    def _make_snapshot(
        self,
        case: dict[str, Any],
        run_result: RunResult,
        answer: str,
    ) -> dict[str, Any]:
        """Build the baseline snapshot dict (all 8 EVAL-08 fields).

        Security (T-4-05): case_id is used only as a dict value here, not
        as a filename. Filename sanitization happens in record().
        """
        case_id: str = case["case_id"]
        query: str = case["query"]
        return {
            "case_id": case_id,
            "query": query,
            "answer": answer,
            "model_arn": self._model_arn,
            "prompt_hash": _prompt_hash(case_id, query, self._system_prompt),
            "vault_content_hash": _vault_content_hash(self._vault_path),
            "timestamp_utc": datetime.now(tz=timezone.utc).isoformat(),
            "seed": None,  # claude CLI exposes no seed parameter
        }

    def record(self, case: dict[str, Any]) -> Path:
        """Record a baseline snapshot for a single case.

        Runs run_headless() inside an async EvalWorktree, writes the
        snapshot JSON to baselines_dir/<safe_case_id>.json.

        Security (T-4-01): validates that case has str 'case_id' and
        'query' before use.
        Security (T-4-05): sanitizes case_id before using as filename.
        """
        # T-4-01: validate required fields
        if not isinstance(case.get("case_id"), str):
            raise ValueError(f"case_id must be a str, got: {type(case.get('case_id'))}")
        if not isinstance(case.get("query"), str):
            raise ValueError(f"query must be a str, got: {type(case.get('query'))}")

        async def _run() -> tuple[RunResult, str]:
            async with EvalWorktree(self._vault_path) as wt:
                assert wt.path is not None
                return run_headless(
                    prompt=case["query"],
                    worktree_path=wt.path,
                    system_prompt=self._system_prompt,
                    plugin_dirs=self._plugin_dirs,
                    model_override=None,
                )

        run_result, answer = asyncio.run(_run())

        snapshot = self._make_snapshot(case, run_result, answer)

        # T-4-05: sanitize case_id for use as filename
        safe_case_id = re.sub(r"[^a-zA-Z0-9._-]", "_", case["case_id"])
        self._baselines_dir.mkdir(parents=True, exist_ok=True)
        out_path = self._baselines_dir / f"{safe_case_id}.json"
        out_path.write_text(json.dumps(snapshot, indent=2) + "\n", encoding="utf-8")
        return out_path

    def record_all(self) -> list[Path]:
        """Load cases from cases_path and record a baseline for each.

        Security (T-4-01): validates each case has str 'case_id' and
        'query' before passing to record().
        """
        with self._cases_path.open(encoding="utf-8") as fh:
            cases: list[dict[str, Any]] = json.load(fh)

        written: list[Path] = []
        for case in cases:
            # T-4-01: validate before record() to catch bad JSON early
            if not isinstance(case.get("case_id"), str):
                raise ValueError(f"Invalid case — case_id must be str: {case}")
            if not isinstance(case.get("query"), str):
                raise ValueError(f"Invalid case — query must be str: {case}")
            written.append(self.record(case))
        return written


# ---------------------------------------------------------------------------
# CLI entry point
# ---------------------------------------------------------------------------


def _main() -> None:
    """CLI: python -m eval_harness.baseline --cases ... --vault ... --out ..."""
    import argparse
    import os

    if not os.environ.get("CODE_WIKI_RUN_EVAL"):
        import sys

        print(
            "Set CODE_WIKI_RUN_EVAL=1 to run baseline recording.",
            file=sys.stderr,
        )
        sys.exit(1)

    parser = argparse.ArgumentParser(description="Record eval baselines via claude -p")
    parser.add_argument("--cases", required=True, type=Path, help="Path to query_cases.json")
    parser.add_argument("--vault", required=True, type=Path, help="Path to the vault directory")
    parser.add_argument("--out", required=True, type=Path, help="Output directory for baseline JSON files")
    parser.add_argument("--plugin-dir", dest="plugin_dirs", action="append", type=Path, default=[])
    parser.add_argument("--model-arn", default="us.anthropic.claude-sonnet-4-6")
    args = parser.parse_args()

    recorder = BaselineRecorder(
        cases_path=args.cases,
        vault_path=args.vault,
        baselines_dir=args.out,
        plugin_dirs=args.plugin_dirs or None,
        model_arn=args.model_arn,
    )
    paths = recorder.record_all()
    for p in paths:
        print(f"Wrote: {p}")


if __name__ == "__main__":
    _main()
