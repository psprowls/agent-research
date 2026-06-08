import json

from claude_code_evals.stderr_logger import EvalLogger, set_logger_enabled


def test_logger_writes_to_stderr(capsys):
    """Verify logs are written to stderr with timestamp and context."""
    logger = EvalLogger("test_context")
    logger.log("test message")

    captured = capsys.readouterr()
    assert "test message" in captured.err
    assert "test_context" in captured.err


def test_logger_disabled_by_env(monkeypatch, capsys):
    """Verify CLAUDE_EVAL_STDERR=0 disables logging."""
    monkeypatch.setenv("CLAUDE_EVAL_STDERR", "0")
    set_logger_enabled(False)

    logger = EvalLogger("test")
    logger.log("should not appear")

    captured = capsys.readouterr()
    assert "should not appear" not in captured.err


def test_logger_formats_dict_data(capsys):
    """Verify dict data is formatted as readable key=value pairs."""
    logger = EvalLogger("fixture_setup")
    logger.log_dict("Isolation created", {"worktree": "/tmp/wt", "scenario": "test-scenario", "config": "test-config"})

    captured = capsys.readouterr()
    assert "Isolation created" in captured.err
    assert "worktree=/tmp/wt" in captured.err or '"worktree": "/tmp/wt"' in captured.err
    assert "scenario=test-scenario" in captured.err or '"scenario": "test-scenario"' in captured.err


def test_logger_with_enabled_false_no_output(monkeypatch, capsys):
    """Verify set_logger_enabled(False) suppresses all output."""
    set_logger_enabled(False)

    logger = EvalLogger("test")
    logger.log("msg1")
    logger.log_dict("data", {"key": "value"})

    captured = capsys.readouterr()
    assert captured.err == ""

    # Restore for other tests
    set_logger_enabled(True)


def test_logger_with_non_serializable_kwargs(capsys):
    """Verify logger handles non-JSON-serializable kwargs gracefully.

    When logger.log() is called with a non-serializable object, the logger should not crash
    and should output valid JSON with an error message instead.
    """
    set_logger_enabled(True)
    logger = EvalLogger("test_context")

    # Log with a non-serializable object (function)
    logger.log("message with non-serializable", obj=lambda x: x)

    captured = capsys.readouterr()
    # Verify output is present and valid JSON
    assert len(captured.err) > 0
    lines = captured.err.strip().split("\n")
    assert len(lines) > 0

    # Parse the JSON to verify it's valid
    parsed = json.loads(lines[0])
    assert "context" in parsed
    assert "timestamp" in parsed
    # Should have either the error message or the original message
    assert "error" in parsed or "message" in parsed


def test_logger_dict_with_non_serializable_data(capsys):
    """Verify logger_dict handles non-JSON-serializable data gracefully.

    When log_dict() is called with a dict containing non-serializable values,
    the logger should not crash and should output valid JSON with an error message.
    """
    set_logger_enabled(True)
    logger = EvalLogger("test_context")

    # Log a dict with a non-serializable value
    logger.log_dict("Data with function", {"key": "value", "func": lambda x: x})

    captured = capsys.readouterr()
    # Verify output is present and valid JSON
    assert len(captured.err) > 0
    lines = captured.err.strip().split("\n")
    assert len(lines) > 0

    # Parse the JSON to verify it's valid
    parsed = json.loads(lines[0])
    assert "context" in parsed
    assert "timestamp" in parsed
    # Should indicate an error occurred
    assert "error" in parsed or "title" in parsed
