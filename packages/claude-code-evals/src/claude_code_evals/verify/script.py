"""ScriptVerifier: run verify.sh in worktree, pass/fail by exit code."""

from __future__ import annotations

import subprocess
from pathlib import Path

from deepeval.test_case import LLMTestCase

from claude_code_evals.verify.base import VerifierBase


class ScriptVerifier(VerifierBase):
    def __init__(self, *, script_path: Path, worktree_path: Path, threshold: float = 0.5) -> None:
        super().__init__(threshold=threshold)
        self._script_path = script_path
        self._worktree_path = worktree_path

    def measure(self, test_case: LLMTestCase) -> float:  # noqa: ARG002
        result = subprocess.run(
            [str(self._script_path)],
            cwd=str(self._worktree_path),
            capture_output=True,
            text=True,
        )
        passed = result.returncode == 0
        self.score = 1.0 if passed else 0.0
        self.reason = result.stdout.strip() or (result.stderr.strip() or ("PASS" if passed else "FAIL"))
        return self.score
