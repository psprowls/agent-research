"""GoldenVerifier: apply golden.patch, run git diff --exit-code."""

from __future__ import annotations

import subprocess
from pathlib import Path

from deepeval.test_case import LLMTestCase

from claude_code_evals.verify.base import VerifierBase


class GoldenVerifier(VerifierBase):
    """Apply golden.patch to worktree, score 1.0 if diff is clean afterward."""

    def __init__(self, *, patch_path: Path, worktree_path: Path, threshold: float = 0.5) -> None:
        super().__init__(threshold=threshold)
        self._patch_path = patch_path
        self._worktree_path = worktree_path

    def measure(self, test_case: LLMTestCase) -> float:  # noqa: ARG002
        patch_content = self._patch_path.read_text()
        if patch_content.strip():
            subprocess.run(
                ["git", "apply", str(self._patch_path)],
                cwd=str(self._worktree_path),
                capture_output=True,
            )

        add_result = subprocess.run(["git", "add", "-N", "."], cwd=str(self._worktree_path), capture_output=True)
        # If not a git repo, fall back: pass when no patch was applied, fail otherwise.
        if add_result.returncode != 0:
            passed = not patch_content.strip()
            self.score = 1.0 if passed else 0.0
            self.reason = "clean diff" if passed else "patch applied but not in a git repo"
            return self.score

        diff = subprocess.run(
            ["git", "diff", "--exit-code"],
            cwd=str(self._worktree_path),
            capture_output=True,
            text=True,
        )
        passed = diff.returncode == 0
        self.score = 1.0 if passed else 0.0
        self.reason = "clean diff" if passed else diff.stdout[:500]
        return self.score
