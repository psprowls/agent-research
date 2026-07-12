from __future__ import annotations

from pathlib import Path

from claude_code_evals.verify.golden import GoldenVerifier
from claude_code_evals.verify.script import ScriptVerifier
from deepeval.test_case import LLMTestCase


def test_script_verifier_pass(tmp_path: Path):
    script = tmp_path / "verify.sh"
    script.write_text("#!/bin/sh\nexit 0\n")
    script.chmod(0o755)
    v = ScriptVerifier(script_path=script, worktree_path=tmp_path)
    tc = LLMTestCase(input="q", actual_output="a")
    v.measure(tc)
    assert v.score == 1.0
    assert v.success is True


def test_script_verifier_fail(tmp_path: Path):
    script = tmp_path / "verify.sh"
    script.write_text("#!/bin/sh\nexit 1\n")
    script.chmod(0o755)
    v = ScriptVerifier(script_path=script, worktree_path=tmp_path)
    tc = LLMTestCase(input="q", actual_output="a")
    v.measure(tc)
    assert v.score == 0.0
    assert v.success is False


def test_golden_verifier_pass(tmp_path: Path):
    # Empty patch = no changes expected = clean diff
    (tmp_path / "foo.txt").write_text("hello\n")
    patch_path = tmp_path / "golden.patch"
    patch_path.write_text("")
    v = GoldenVerifier(patch_path=patch_path, worktree_path=tmp_path)
    tc = LLMTestCase(input="q", actual_output="a")
    v.measure(tc)
    assert v.score == 1.0


def test_golden_verifier_fail(tmp_path: Path):
    (tmp_path / "foo.txt").write_text("original\n")
    patch_content = "--- a/foo.txt\n+++ b/foo.txt\n@@ -1 +1 @@\n-original\n+modified\n"
    patch_path = tmp_path / "golden.patch"
    patch_path.write_text(patch_content)
    v = GoldenVerifier(patch_path=patch_path, worktree_path=tmp_path)
    tc = LLMTestCase(input="q", actual_output="a")
    v.measure(tc)
    assert v.score in (0.0, 1.0)
