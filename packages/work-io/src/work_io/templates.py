"""Accessor for work-io's shipped page templates."""

from __future__ import annotations

from pathlib import Path


def templates_dir() -> Path:
    """Directory holding work-io's shipped page templates (work.md)."""
    return Path(__file__).resolve().parent / "assets"
