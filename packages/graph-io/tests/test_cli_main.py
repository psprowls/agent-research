"""Belt-and-suspenders CLI registry assertions (Phase 51 PKGFAM-04)."""

from __future__ import annotations

from graph_io.cli.main import _SUBCOMMANDS


def test_no_package_family_subcommand() -> None:
    # Phase 51 PKGFAM-04: package_family is a retired entity kind; the CLI
    # never exposed describe-package-family / list-package-families as live
    # subcommands. Lock that absence so a future revival of the kind cannot
    # silently reintroduce the subcommand surface.
    assert "describe-package-family" not in _SUBCOMMANDS
    assert "list-package-families" not in _SUBCOMMANDS
