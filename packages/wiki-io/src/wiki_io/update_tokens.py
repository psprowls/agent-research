"""
update_tokens.py — Stamp `tokens: <count>` frontmatter on every wiki page.

Counts tokens against a stable baseline — the file content with any existing
`tokens` field stripped — using a `count_tokens` callable injected by the
caller (real callers pass the graph-io package's offline tiktoken counter,
`tokens.count_tokens`, o200k_base, so vault token counts stay comparable to
graph-node counts), then idempotently rewrites the `tokens` field via
`python-frontmatter`. Stripping the field before counting avoids a circular
dependency: a file that already contains `tokens: N` would produce a
different count than the same file before the field was added, breaking
idempotency. Re-running on an unchanged vault is a no-op. This module itself
has no dependency on graph-io — the counter is injected by the caller.
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Callable, Iterator

import frontmatter
from workspace_io.paths import work_dir

SKIP_FILENAMES = {"index.md", "log.md"}


def iter_pages(wiki: Path) -> Iterator[Path]:
    """Yield every .md under `wiki`, skipping log/index and dotdir paths."""
    for path in wiki.rglob("*.md"):
        if path.name in SKIP_FILENAMES:
            continue
        rel_parts = path.relative_to(wiki).parts
        if any(part.startswith(".") for part in rel_parts):
            continue
        yield path


def update_page(path: Path, count_tokens: Callable[[str], int], dry_run: bool = False) -> tuple[str, int | None]:
    """Stamp the `tokens` field on a single page using the injected `count_tokens`.

    Counts tokens on the stripped baseline (existing `tokens` field
    removed before encoding) so the stored count is stable across runs.

    Returns (status, count) where status is one of
    "updated", "unchanged", "skipped". `count` is the integer token count for
    processed pages and 0 for skips.

    Skips files without frontmatter (e.g. index.md, log.md, CLAUDE.md)
    since adding frontmatter to such files would change their baseline.
    """
    try:
        raw = path.read_text(encoding="utf-8")
        post = frontmatter.loads(raw)
    except Exception as exc:  # noqa: BLE001 — keep run going on any read/parse error
        print(f"[warn] skipping {path}: {exc}", file=sys.stderr)
        return ("skipped", 0)

    # Only process files that already have frontmatter
    # (adding frontmatter to files without it changes the baseline unpredictably)
    if not raw.startswith("---"):
        return ("skipped", 0)

    # Strip the existing tokens field from the raw YAML to create a stable baseline.
    # This preserves the original YAML formatting while removing the field that would
    # create a circular dependency (the token count would differ after adding the field).
    # We do this line-by-line to avoid reformatting via the YAML serializer.
    parts = raw.split("---", 2)
    # Guard against truncated frontmatter (missing closing ---).
    if len(parts) < 3:
        print(f"[warn] skipping {path}: no closing frontmatter fence", file=sys.stderr)
        return ("skipped", 0)
    # Extract and filter frontmatter
    fm_lines = parts[1].strip().split("\n")
    filtered_lines = [line for line in fm_lines if not (line == "tokens:" or line.startswith("tokens: "))]
    filtered_fm = "\n".join(filtered_lines)
    # Reconstruct: --- + filtered_fm + --- + content + \n
    baseline = f"---\n{filtered_fm}\n---\n{parts[2]}\n"

    try:
        count = count_tokens(baseline)
    except Exception as exc:  # noqa: BLE001 — one bad page must not abort the vault
        print(f"[warn] skipping {path}: token count failed: {exc}", file=sys.stderr)
        return ("skipped", 0)

    # Idempotency: existing value already matches the new value.
    if post.metadata.get("tokens") == count:
        return ("unchanged", count)

    if not dry_run:
        # Update the tokens field while preserving original YAML formatting.
        updated_lines = []
        tokens_found = False

        for line in fm_lines:
            if line == "tokens:" or line.startswith("tokens: "):
                updated_lines.append(f"tokens: {count}")
                tokens_found = True
            else:
                updated_lines.append(line)

        # If tokens field didn't exist, add it at the end before closing ---
        if not tokens_found:
            updated_lines.append(f"tokens: {count}")

        # Reconstruct: --- + updated_fm + --- + content
        # parts[2] starts with \n, so we don't need another one
        updated_fm = "\n".join(updated_lines)
        updated_raw = f"---\n{updated_fm}\n---{parts[2]}"

        path.write_text(updated_raw, encoding="utf-8")

    return ("updated", count)


def update_vault(wiki: Path, count_tokens: Callable[[str], int], dry_run: bool = False) -> dict[str, list[str]]:
    """Walk `wiki` and `work/`, stamp `tokens` on every page via the injected
    `count_tokens`, return {updated, unchanged, skipped} lists."""
    result: dict[str, list[str]] = {"updated": [], "unchanged": [], "skipped": []}
    workspace = wiki.parent

    # Process wiki pages
    for page in iter_pages(wiki):
        status, _ = update_page(page, count_tokens, dry_run=dry_run)
        result[status].append(str(page.relative_to(workspace)))

    # Process work items (now under the wiki)
    work_root = work_dir(workspace)
    if work_root.exists():
        for page in iter_pages(work_root):
            status, _ = update_page(page, count_tokens, dry_run=dry_run)
            result[status].append(str(page.relative_to(workspace)))

    for bucket in result.values():
        bucket.sort()
    return result
