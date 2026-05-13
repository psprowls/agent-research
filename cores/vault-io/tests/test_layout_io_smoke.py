"""VAULT-02: layout_io.write_layout byte stability + roundtrip.

The hand-rolled YAML emitter must produce byte-identical output on repeat
writes given the same input dict. The round-trip (read → write) must also be
byte-stable for the canonical layout shape used by Phase 5 init/scan.
"""

from __future__ import annotations

from pathlib import Path

from vault_io.layout_io import LAYOUT_END, LAYOUT_START, read_layout, write_layout


def _make_schema(path: Path, preamble: str = "") -> Path:
    """Write a schema file with optional preamble, no existing layout block."""
    path.write_text(preamble, encoding="utf-8")
    return path


def test_write_layout_is_byte_stable(tmp_path: Path):
    schema = _make_schema(
        tmp_path / "CLAUDE.md",
        "# Project schema\n\nPreamble text.\n",
    )
    layout = {
        "version": 1,
        "detected_at": "2026-05-13",
        "repo_root": "..",
        "containers": [
            {
                "source": "apps",
                "vault_dir": "apps",
                "classification": "app",
                "children_count": 3,
            }
        ],
    }

    write_layout(schema, layout)
    first = schema.read_bytes()

    write_layout(schema, layout)
    second = schema.read_bytes()

    assert first == second, "write_layout is not byte-stable across repeated writes"

    # Read-back round-trip: the parsed layout, re-emitted, must produce the same bytes.
    parsed = read_layout(schema)
    assert parsed is not None
    write_layout(schema, parsed)
    third = schema.read_bytes()
    assert third == second, "round-trip (read → write) drifted bytes"


def test_write_layout_replaces_existing_block(tmp_path: Path):
    schema = tmp_path / "CLAUDE.md"
    initial_layout = {
        "version": 1,
        "detected_at": "2026-05-01",
        "repo_root": "..",
        "containers": [
            {"source": "apps", "vault_dir": "apps", "classification": "app", "children_count": 1}
        ],
    }
    schema.write_text("# Preamble before\n", encoding="utf-8")
    write_layout(schema, initial_layout)

    updated_layout = {
        "version": 1,
        "detected_at": "2026-05-13",
        "repo_root": "..",
        "containers": [
            {"source": "packages", "vault_dir": "packages", "classification": "package", "children_count": 5}
        ],
    }
    write_layout(schema, updated_layout)

    text = schema.read_text(encoding="utf-8")
    # The preamble outside sentinels is preserved.
    assert text.startswith("# Preamble before\n")
    # The block content reflects the new layout, not the old.
    assert "packages" in text
    assert "vault_dir: packages" in text
    # The sentinel pair appears exactly once each.
    assert text.count(LAYOUT_START) == 1
    assert text.count(LAYOUT_END) == 1
    # Old container removed.
    assert "vault_dir: apps" not in text


def test_write_layout_handles_null_vault_dir(tmp_path: Path):
    schema = tmp_path / "CLAUDE.md"
    schema.write_text("", encoding="utf-8")
    layout = {
        "version": 1,
        "detected_at": "2026-05-13",
        "repo_root": "..",
        "containers": [
            {
                "source": "ambiguous-dir",
                "vault_dir": None,
                "classification": "skip",
                "children_count": 0,
            }
        ],
    }
    write_layout(schema, layout)
    text = schema.read_text(encoding="utf-8")
    assert "vault_dir: null" in text
