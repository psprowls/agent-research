"""Structured stderr logging for eval instrumentation."""

import json
import os
import sys
from datetime import datetime, timezone

# Global enable/disable state
_ENABLED = True


def set_logger_enabled(enabled: bool) -> None:
    """Enable or disable all logger output globally."""
    global _ENABLED
    _ENABLED = enabled


class EvalLogger:
    """Lightweight structured logger that writes JSON logs to stderr."""

    def __init__(self, context: str) -> None:
        """Initialize logger with a context label.

        Args:
            context: A label to identify the source of log messages (e.g., "test_context", "fixture_setup")
        """
        self.context = context

    def _should_log(self) -> bool:
        """Check if logging is enabled, respecting both global state and env var."""
        # Check if global state says logging is disabled
        if not _ENABLED:
            return False

        # Check CLAUDE_EVAL_STDERR env var
        env_value = os.getenv("CLAUDE_EVAL_STDERR", "").strip()
        if env_value == "0":
            return False

        return True

    def _write_log(self, log_entry: dict) -> None:
        """Write a single log entry as JSON to stderr."""
        try:
            json.dump(log_entry, sys.stderr)
            sys.stderr.write("\n")
            sys.stderr.flush()
        except Exception:
            # Silently ignore logging errors to avoid disrupting eval flow
            pass

    def log(self, message: str, **kwargs) -> None:
        """Log a message with optional additional fields.

        Args:
            message: The log message
            **kwargs: Additional fields to include in the JSON log entry
        """
        if not self._should_log():
            return

        timestamp = datetime.now(timezone.utc).isoformat(timespec="milliseconds")

        log_entry = {
            "timestamp": timestamp,
            "context": self.context,
            "message": message,
        }
        log_entry.update(kwargs)

        self._write_log(log_entry)

    def log_dict(self, title: str, data: dict) -> None:
        """Log a title with dictionary data formatted as key=value pairs or JSON.

        Args:
            title: A title for the data
            data: Dictionary to log
        """
        if not self._should_log():
            return

        timestamp = datetime.now(timezone.utc).isoformat(timespec="milliseconds")

        log_entry = {
            "timestamp": timestamp,
            "context": self.context,
            "title": title,
            "data": data,
        }

        self._write_log(log_entry)
