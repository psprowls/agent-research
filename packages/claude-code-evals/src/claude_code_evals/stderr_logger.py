"""Structured stderr logging for eval instrumentation.

Thread-safety note: This module is not thread-safe and should only be used in single-threaded
contexts (which is the case for pytest-based eval runs). The global _ENABLED state is accessed
without synchronization.
"""

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
        """Check if logging is enabled, respecting both global state and env var.

        Returns:
            bool: True if logging should proceed, False otherwise.
        """
        # Check if global state says logging is disabled
        if not _ENABLED:
            return False

        # Check CLAUDE_EVAL_STDERR env var
        env_value = os.getenv("CLAUDE_EVAL_STDERR", "").strip()
        if env_value == "0":
            return False

        return True

    def _write_log(self, log_entry: dict) -> None:
        """Write a single log entry as JSON to stderr.

        If the log entry contains non-JSON-serializable data, a fallback error entry is written
        instead to ensure some output is always produced.
        """
        try:
            # Pre-validate serialization before writing to stderr
            json_str = json.dumps(log_entry)
            sys.stderr.write(json_str)
            sys.stderr.write("\n")
            sys.stderr.flush()
        except TypeError:
            # Handle non-serializable objects in log_entry
            fallback_entry = {
                "timestamp": log_entry.get("timestamp", "unknown"),
                "context": log_entry.get("context", "unknown"),
                "error": "Log entry contained non-JSON-serializable data; check kwargs for objects",
                "message": str(log_entry.get("message", "")),
            }
            try:
                sys.stderr.write(json.dumps(fallback_entry))
                sys.stderr.write("\n")
                sys.stderr.flush()
            except Exception:
                # Last resort: write a minimal safe message
                sys.stderr.write('{"error":"Failed to serialize log entry"}\n')
                sys.stderr.flush()
        except OSError:
            # Ignore I/O errors to avoid disrupting eval flow
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
