"""Accessor for guidance-io's shipped page templates."""

from __future__ import annotations

from pathlib import Path


def templates_dir() -> Path:
    """Directory holding guidance-io's shipped page templates (guidance.md)."""
    return Path(__file__).resolve().parent / "assets"
