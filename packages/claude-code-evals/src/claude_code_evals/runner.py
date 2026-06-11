"""Headless runner: spawns claude -p in one-shot or multi-turn mode."""

from __future__ import annotations

import asyncio
import json
import os
import subprocess
import time
from dataclasses import dataclass
from pathlib import Path

from claude_code_evals.stderr_logger import EvalLogger
from claude_code_evals.user_simulator import AutoUserSimulator


def load_oauth_token(token_file_path: str | None = None) -> str:
    """Load OAuth token from env var, file, or standard locations.

    Priority order:
    1. CLAUDE_CODE_OAUTH_TOKEN env var
    2. token_file_path (if provided)
    3. eval/.secrets (project-local, relative to cwd)
    4. ~/.config/cc-eval/token (user home)

    Args:
        token_file_path: Optional explicit path to token file. If provided, this is checked
                         after the env var but before the default locations.

    Returns:
        The OAuth token string.

    Raises:
        ValueError: If token not found in any location.
    """
    # Priority 1: env var
    token = os.environ.get("CLAUDE_CODE_OAUTH_TOKEN")
    if token:
        return token.strip()

    # Priority 2: explicit file path
    if token_file_path:
        try:
            with open(token_file_path, "r") as f:
                token = f.read().strip()
                if token:
                    return token
        except (FileNotFoundError, IOError):
            pass

    # Priority 3: project-local eval/.secrets
    eval_secrets = Path("eval/.secrets")
    if eval_secrets.exists():
        try:
            with open(eval_secrets, "r") as f:
                token = f.read().strip()
                if token:
                    return token
        except (FileNotFoundError, IOError):
            pass

    # Priority 4: user home config
    home_token = Path.home() / ".config" / "cc-eval" / "token"
    if home_token.exists():
        try:
            with open(home_token, "r") as f:
                token = f.read().strip()
                if token:
                    return token
        except (FileNotFoundError, IOError):
            pass

    raise ValueError(
        "OAuth token not found. Set CLAUDE_CODE_OAUTH_TOKEN env var, "
        "create eval/.secrets or ~/.config/cc-eval/token, or pass token_file_path."
    )


def prepare_injected_context(
    base_prompt: str,
    wiki_root: str,
    inject_paths: list[str],
) -> str:
    """Prepend wiki page contents to system prompt for injected arm.

    Args:
        base_prompt: The base system prompt from the config
        wiki_root: Path to wiki root (e.g. ~/Personal/graph-wiki/mono-repo-eval-551f7ed8)
        inject_paths: List of wiki page paths relative to wiki/

    Returns:
        Combined prompt with wiki pages prepended
    """
    wiki_sections = []

    for inject_path in inject_paths:
        full_path = os.path.join(wiki_root, "wiki", inject_path)
        try:
            with open(full_path, "r") as f:
                content = f.read()
                wiki_sections.append(content)
        except FileNotFoundError:
            raise ValueError(f"Wiki page not found: {inject_path}")

    wiki_text = "\n\n---\n\n".join(wiki_sections)
    return f"{wiki_text}\n\n{base_prompt}"


def prepare_plugin_env(config: dict) -> dict:
    """Prepare environment vars for plugin arm (includes GRAPH_WIKI_WORKSPACE).

    Args:
        config: The plugin config loaded from plugin.yaml

    Returns:
        Environment dict with GRAPH_WIKI_WORKSPACE set
    """
    env = os.environ.copy()

    if "environment" in config:
        for key, value in config["environment"].items():
            # Expand ~ in paths
            if isinstance(value, str) and value.startswith("~"):
                value = os.path.expanduser(value)
            env[key] = value

    return env


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
    final_status: str  # "success" | "completed_interactive" | "budget_exceeded" | "error_*"
    budget_exceeded: bool
    wall_seconds: float
    error_reason: str | None = None
    exit_code: int | None = None
    simulator_input_tokens: int = 0
    simulator_output_tokens: int = 0


def _build_cmd(
    *,
    prompt: str,
    worktree_path: Path,
    system_prompt: str,
    model: str,
    plugin_dirs: list[Path] | None = None,
    multi_turn: bool = False,
) -> list[str]:
    """Build subprocess command list. Security: always a list, prompt is final element.

    Config isolation is via the ``CLAUDE_CONFIG_DIR`` env var (see ``_build_env``), NOT a
    ``--config-dir`` flag (which no longer exists in the claude CLI). ``--append-system-prompt``
    keeps the model's default tool guidance while layering the eval directive on top.

    In multi-turn (``--input-format stream-json``) mode the CLI ignores the positional
    prompt and waits for user messages on stdin, so the prompt is NOT appended to argv —
    the runner delivers it as the first stdin user message instead.
    """
    cmd = [
        "claude",
        "-p",
        "--output-format",
        "stream-json",
        "--verbose",
        "--add-dir",
        str(worktree_path),
        "--append-system-prompt",
        system_prompt,
        "--model",
        model,
    ]
    for pdir in plugin_dirs or []:
        cmd += ["--plugin-dir", str(pdir)]
    if multi_turn:
        cmd += ["--input-format", "stream-json", "--replay-user-messages"]
    else:
        cmd.append(prompt)

    logger = EvalLogger("runner_cmd_build")
    logger.log_dict(
        "Claude invocation command built",
        {
            "model": model,
            "multi_turn": multi_turn,
            "plugin_dirs_count": len(plugin_dirs or []),
            "system_prompt_length": len(system_prompt),
            "user_prompt_length": len(prompt),
        },
    )

    return cmd


def run_one_shot(
    *,
    prompt: str,
    worktree_path: Path,
    cfg_dir: Path,
    system_prompt: str,
    model: str = "claude-sonnet-4-6",
    oauth_token: str | None = None,
    plugin_dirs: list[Path] | None = None,
    extra_env: dict[str, str] | None = None,
    max_wall_seconds: float = 300.0,
    _max_input_tokens: int = 100_000,
) -> tuple[RunResult, str]:
    """Run claude -p one-shot. Returns (RunResult, raw_jsonl_string)."""
    env = _build_env(cfg_dir=cfg_dir, oauth_token=oauth_token, extra_env=extra_env)
    cmd = _build_cmd(
        prompt=prompt,
        worktree_path=worktree_path,
        system_prompt=system_prompt,
        model=model,
        plugin_dirs=plugin_dirs,
    )

    logger = EvalLogger("runner_one_shot")
    logger.log("Starting one-shot run", model=model, max_wall_seconds=max_wall_seconds)
    logger.log_dict(
        "System prompt injected",
        {
            "system_prompt_length": len(system_prompt),
            "system_prompt_prefix": system_prompt[:100] + "..." if len(system_prompt) > 100 else system_prompt,
        },
    )
    logger.log_dict(
        "User prompt",
        {
            "prompt_length": len(prompt),
            "prompt_prefix": prompt[:100] + "..." if len(prompt) > 100 else prompt,
        },
    )

    proc = subprocess.Popen(
        cmd,
        cwd=str(worktree_path),
        env=env,
        stdin=subprocess.DEVNULL,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,  # merge stderr so CLI errors land in the captured stream
        text=True,
        bufsize=1,
    )

    start = time.monotonic()
    budget_exceeded = False
    saw_result = False
    final_status = "success"
    error_reason: str | None = None
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

            # Log notable events from stream-json
            if ev.get("type") in ("message", "assistant"):
                if ev.get("role") == "assistant":
                    logger.log("Assistant message received", content_length=len(ev.get("content", "")))
                elif ev.get("role") == "user":
                    logger.log("User message received", content_length=len(ev.get("content", "")))
            elif ev.get("type") == "tool_call":
                logger.log("Tool called", tool_name=ev.get("tool_name"), tool_id=ev.get("id"))
            elif ev.get("type") == "tool_result":
                logger.log("Tool result received", tool_id=ev.get("id"), result_length=len(str(ev.get("result", ""))))

            if ev.get("type") == "result":
                saw_result = True
                final_status, error_reason = _classify_result(ev)
                break
    finally:
        if budget_exceeded:
            proc.terminate()
        proc.wait(timeout=5)

    exit_code = proc.returncode
    if not saw_result and not budget_exceeded:
        # No result event: the CLI crashed (bad flag, auth, etc.) or produced nothing.
        final_status = "error_no_result"
        error_reason = _tail_non_json("".join(lines)) or f"claude exited {exit_code} with no result event"

    logger.log_dict(
        "One-shot run completed",
        {
            "final_status": final_status,
            "budget_exceeded": budget_exceeded,
            "wall_seconds": time.monotonic() - start,
            "exit_code": exit_code,
            "error_reason": error_reason,
        },
    )

    return (
        RunResult(
            final_status=final_status,
            budget_exceeded=budget_exceeded,
            wall_seconds=time.monotonic() - start,
            error_reason=error_reason,
            exit_code=exit_code,
        ),
        "".join(lines),
    )


def _classify_result(ev: dict) -> tuple[str, str | None]:
    """Map a stream-json ``result`` event to (final_status, error_reason).

    ``is_error`` is the authoritative failure signal — a run can carry ``subtype: success``
    yet ``is_error: true`` (e.g. an auth failure whose message lands in ``result``).
    """
    subtype = ev.get("subtype", "success")
    is_error = bool(ev.get("is_error"))
    if is_error or (isinstance(subtype, str) and subtype.startswith("error")):
        status = subtype if isinstance(subtype, str) and subtype.startswith("error") else "error"
        reason = ev.get("result") or ev.get("error") or subtype
        return status, str(reason) if reason is not None else None
    return "success", None


def _tail_non_json(raw: str, *, max_chars: int = 500) -> str | None:
    """Return the last non-empty, non-JSON line(s) of merged output (e.g. a CLI error)."""
    tail: list[str] = []
    for line in raw.splitlines():
        s = line.strip()
        if not s or s.startswith("{"):
            continue
        tail.append(s)
    if not tail:
        return None
    return " ".join(tail)[-max_chars:]


def run_multi_turn(
    *,
    prompt: str,
    worktree_path: Path,
    cfg_dir: Path,
    system_prompt: str,
    simulator: AutoUserSimulator,
    model: str = "claude-sonnet-4-6",
    oauth_token: str | None = None,
    plugin_dirs: list[Path] | None = None,
    extra_env: dict[str, str] | None = None,
    max_turns: int = 20,
    max_wall_seconds: float = 300.0,
    _max_input_tokens: int = 100_000,
) -> tuple[RunResult, str]:
    """Run claude -p in multi-turn mode driven by AutoUserSimulator.

    Sync facade over an asyncio implementation: concurrent stdout/stderr
    readers, a wall-clock watchdog (fires even when the CLI hangs silently),
    per-result classification, and a max_turns cap on completed agent turns.

    Watchdog caveat: ``simulator.reply`` runs in a worker thread via
    ``asyncio.to_thread``, and threads cannot be cancelled — if the watchdog
    fires mid-reply, ``asyncio.run`` blocks at shutdown until the underlying
    Bedrock call returns. So max_wall_seconds reliably bounds CLI hangs, while
    simulator hangs are bounded by the Bedrock client's own read timeout.
    """
    env = _build_env(cfg_dir=cfg_dir, oauth_token=oauth_token, extra_env=extra_env)
    cmd = _build_cmd(
        prompt=prompt,
        worktree_path=worktree_path,
        system_prompt=system_prompt,
        model=model,
        plugin_dirs=plugin_dirs,
        multi_turn=True,
    )
    return asyncio.run(
        _run_multi_turn_async(
            cmd=cmd,
            prompt=prompt,
            worktree_path=worktree_path,
            env=env,
            simulator=simulator,
            max_turns=max_turns,
            max_wall_seconds=max_wall_seconds,
        )
    )


class _StderrTail:
    """Bounded stderr accumulator: retains only the last `limit` bytes."""

    def __init__(self, limit: int = 16_384) -> None:
        self._limit = limit
        self._data = b""

    def append(self, chunk: bytes) -> None:
        self._data = (self._data + chunk)[-self._limit :]

    def text(self) -> str:
        return self._data.decode("utf-8", errors="replace").strip()


async def _drain_stderr(stream: asyncio.StreamReader, tail: _StderrTail) -> None:
    while True:
        chunk = await stream.read(4096)
        if not chunk:
            return
        tail.append(chunk)


async def _run_multi_turn_async(
    *,
    cmd: list[str],
    prompt: str,
    worktree_path: Path,
    env: dict[str, str],
    simulator: AutoUserSimulator,
    max_turns: int,
    max_wall_seconds: float,
) -> tuple[RunResult, str]:
    logger = EvalLogger("runner_multi_turn")
    logger.log("Starting multi-turn run", max_turns=max_turns, max_wall_seconds=max_wall_seconds)

    start = time.monotonic()
    proc = await asyncio.create_subprocess_exec(
        *cmd,
        cwd=str(worktree_path),
        env=env,
        stdin=asyncio.subprocess.PIPE,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
        # asyncio's default 64KB stream limit makes readline() raise ValueError on a
        # single stream-json line larger than 64KB (large tool results are routine).
        limit=8 * 1024 * 1024,
    )
    assert proc.stdin is not None and proc.stdout is not None and proc.stderr is not None
    stdin: asyncio.StreamWriter = proc.stdin
    stdout: asyncio.StreamReader = proc.stdout
    stderr_tail = _StderrTail()
    stderr_task = asyncio.create_task(_drain_stderr(proc.stderr, stderr_tail))
    lines: list[str] = []

    async def _conversation() -> tuple[str, bool, str | None]:
        """Run the event loop; returns (final_status, budget_exceeded, error_reason)."""
        # In stream-json input mode the CLI ignores the positional prompt and waits
        # for user messages on stdin — deliver the task prompt as the first one.
        initial_msg = json.dumps({"type": "user", "message": {"role": "user", "content": prompt}})
        try:
            stdin.write((initial_msg + "\n").encode("utf-8"))
            await stdin.drain()
        except (BrokenPipeError, ConnectionResetError):
            reason = stderr_tail.text() or "claude CLI died while receiving initial prompt"
            return "error_cli_died", False, reason

        full_turn_text = ""  # all text blocks of the current turn (stop_on/trigger scope)
        final_block = ""  # last text block of the current turn (LLM history scope)
        completed_turns = 0
        while True:
            raw = await stdout.readline()
            if not raw:
                # EOF without a clean conversation end: CLI crash, bad flag, auth.
                reason = stderr_tail.text() or _tail_non_json("".join(lines))
                return "error_no_result", False, reason or "claude exited with no result event"
            line = raw.decode("utf-8", errors="replace")
            lines.append(line)
            line_str = line.strip()
            if not line_str:
                continue
            try:
                ev = json.loads(line_str)
            except json.JSONDecodeError:
                continue

            # Log notable events from stream-json
            if ev.get("type") in ("message", "assistant"):
                if ev.get("role") == "assistant":
                    logger.log("Assistant message received", content_length=len(ev.get("content", "")))
                elif ev.get("role") == "user":
                    logger.log("User message received", content_length=len(ev.get("content", "")))
            elif ev.get("type") == "tool_call":
                logger.log("Tool called", tool_name=ev.get("tool_name"), tool_id=ev.get("id"))
            elif ev.get("type") == "tool_result":
                logger.log("Tool result received", tool_id=ev.get("id"), result_length=len(str(ev.get("result", ""))))

            if ev.get("type") == "assistant":
                for block in (ev.get("message") or {}).get("content") or []:
                    if block.get("type") == "text":
                        full_turn_text += block.get("text", "")
                        final_block = block.get("text", "")
            elif ev.get("type") == "result":
                status, reason = _classify_result(ev)
                if status != "success":
                    return status, False, reason
                completed_turns += 1
                if completed_turns >= max_turns:
                    return "budget_exceeded", True, f"max_turns ({max_turns}) reached"
                reply = await asyncio.to_thread(simulator.reply, full_turn_text, final_block)
                if reply is None:
                    return "success", False, None
                full_turn_text = ""
                final_block = ""
                user_msg = json.dumps({"type": "user", "message": {"role": "user", "content": reply}})
                try:
                    stdin.write((user_msg + "\n").encode("utf-8"))
                    await stdin.drain()
                except (BrokenPipeError, ConnectionResetError):
                    reason = stderr_tail.text() or "claude CLI died while receiving simulator reply"
                    return "error_cli_died", False, reason

    try:
        final_status, budget_exceeded, error_reason = await asyncio.wait_for(_conversation(), timeout=max_wall_seconds)
    except TimeoutError:
        final_status = "budget_exceeded"
        budget_exceeded = True
        error_reason = f"max_wall_seconds ({max_wall_seconds}) exceeded"
    finally:
        if proc.returncode is None:
            proc.terminate()
            try:
                await asyncio.wait_for(proc.wait(), timeout=5)
            except TimeoutError:
                proc.kill()
                await proc.wait()
        await stderr_task

    wall_seconds = time.monotonic() - start
    logger.log_dict(
        "Multi-turn run completed",
        {
            "final_status": final_status,
            "budget_exceeded": budget_exceeded,
            "wall_seconds": wall_seconds,
            "exit_code": proc.returncode,
            "error_reason": error_reason,
        },
    )

    return (
        RunResult(
            final_status=final_status,
            budget_exceeded=budget_exceeded,
            wall_seconds=wall_seconds,
            error_reason=error_reason,
            exit_code=proc.returncode,
            simulator_input_tokens=simulator.input_tokens,
            simulator_output_tokens=simulator.output_tokens,
        ),
        "".join(lines),
    )


def run_interactive(
    *,
    worktree_path: Path,
    poll_interval: float = 1.0,
    max_wait_seconds: float = 3600.0,
) -> tuple[RunResult, str]:
    """Wait for a manual interactive session to complete.

    Prints the worktree path and polls for a .eval-done sentinel file.
    Returns a RunResult with final_status="completed_interactive" on success
    or final_status="budget_exceeded" if max_wait_seconds is exceeded.
    """
    done_file = worktree_path / ".eval-done"
    start = time.monotonic()

    print(
        f"\n[INTERACTIVE MODE]\n"
        f"  Worktree: {worktree_path}\n"
        f"  Run claude in the worktree, then signal completion with:\n"
        f"    touch {done_file}\n"
    )

    logger = EvalLogger("runner_interactive")
    logger.log("Waiting for interactive session", done_file=str(done_file))

    while not done_file.exists():
        elapsed = time.monotonic() - start
        if elapsed > max_wait_seconds:
            logger.log("Interactive wait timed out", elapsed=elapsed)
            return (
                RunResult(
                    final_status="budget_exceeded",
                    budget_exceeded=True,
                    wall_seconds=elapsed,
                ),
                "",
            )
        time.sleep(poll_interval)

    wall_seconds = time.monotonic() - start
    logger.log("Interactive session complete", wall_seconds=wall_seconds)
    return (
        RunResult(
            final_status="completed_interactive",
            budget_exceeded=False,
            wall_seconds=wall_seconds,
        ),
        "",
    )


def _build_env(
    *,
    cfg_dir: Path,
    oauth_token: str | None = None,
    extra_env: dict[str, str] | None = None,
) -> dict[str, str]:
    """Build the subprocess env: isolated config dir + subscription OAuth auth.

    ``CLAUDE_CONFIG_DIR`` makes ``cfg_dir`` the whole config root (no real plugins/memory leak
    in). ``ANTHROPIC_API_KEY`` is stripped so a stray key can never silently bill API credits;
    ``CLAUDE_CODE_OAUTH_TOKEN`` (from ``claude setup-token``) bills the subscription instead.
    """
    env = os.environ.copy()
    env["CLAUDE_CONFIG_DIR"] = str(cfg_dir)
    env["CLAUDE_CODE_DISABLE_AUTO_MEMORY"] = "1"
    env.pop("ANTHROPIC_API_KEY", None)
    if oauth_token is not None:
        env["CLAUDE_CODE_OAUTH_TOKEN"] = oauth_token
    if extra_env:
        env.update(extra_env)
    return env
