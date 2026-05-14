"""Container drift: pinned vault dirs vs. disk; orphan vault dirs."""

from __future__ import annotations

from pathlib import Path

from vault_io.layout_io import read_layout

GROUP = "container"

FIXED_DIRS = {
    "concepts",
    "architecture",
    "adrs",
    "sources",
    "dependencies",
    "work",
    ".templates",
    "apps",
    "packages",
    "domains",
    ".obsidian",
}

# Legacy folder names — tolerated with a hint, not flagged as orphan, so a
# vault half-way through migration still lints cleanly.
LEGACY_DIRS = {"issues", "roadmap", "comparisons", "endpoints", "data-models"}


def check(repo: Path, wiki: Path) -> list[str]:
    """Return a list of human-readable issue strings about layout/disk drift."""
    issues: list[str] = []
    layout = read_layout(wiki / "CLAUDE.md")
    if layout is None:
        return ["no layout block found in CLAUDE.md (run /lattice-wiki:init)"]
    pinned = layout.get("containers", [])

    # Pinned containers whose source dir is missing
    for c in pinned:
        if c.get("classification") == "skip":
            continue
        src = c.get("source")
        if src and not (repo / src).exists():
            issues.append(f"pinned container '{src}' has no source dir on disk")

    # Vault dirs that aren't pinned and aren't fixed cross-cutting dirs
    pinned_vault_dirs = {c.get("vault_dir") for c in pinned if c.get("vault_dir")}
    vault_root = wiki
    if vault_root.exists():
        for d in sorted(vault_root.iterdir()):
            if not d.is_dir():
                continue
            if d.name in FIXED_DIRS or d.name in pinned_vault_dirs:
                continue
            if d.name in LEGACY_DIRS:
                issues.append(
                    f"legacy vault dir '{d.name}' present — replace with work/ or delete"
                )
                continue
            issues.append(f"orphan vault dir '{d.name}' is not pinned and not a fixed category")

    return issues
