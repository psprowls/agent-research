#!/usr/bin/env python3
"""
update_tokens.py — Stamp `tokens: <count>` frontmatter on every wiki page.

Counts tokens against a stable baseline — the file content with any existing
`tokens` field stripped — using the Bedrock CountTokens API, then idempotently
rewrites the `tokens` field via `python-frontmatter`. Stripping the field before
counting avoids a circular dependency: a file that already contains `tokens: N`
would produce a different count than the same file before the field was added,
breaking idempotency. Re-running on an unchanged vault is a no-op.

Discovers wiki location from the resolved graph-wiki workspace.

Usage:
    python -m vault_io.update_tokens
    python -m vault_io.update_tokens --dry-run --json
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Iterator

import boto3
import frontmatter

from vault_io._workspace import resolve_wiki_and_repo

SKIP_FILENAMES = {"index.md", "log.md"}

DEFAULT_MODEL_ID = "us.anthropic.claude-haiku-4-5-20251001-v1:0"
DEFAULT_REGION = "us-east-1"


def count_tokens(text: str, model_id: str = DEFAULT_MODEL_ID, region: str = DEFAULT_REGION) -> int:
    client = boto3.client("bedrock-runtime", region_name=region)
    response = client.count_tokens(
        modelId=model_id,
        input={
            "converse": {
                "messages": [
                    {"role": "user", "content": [{"text": text}]}
                ]
            }
        },
    )
    return response["inputTokens"]


def iter_pages(wiki: Path) -> Iterator[Path]:
    """Yield every .md under `wiki`, skipping log/index and dotdir paths."""
    for path in wiki.rglob("*.md"):
        if path.name in SKIP_FILENAMES:
            continue
        rel_parts = path.relative_to(wiki).parts
        if any(part.startswith(".") for part in rel_parts):
            continue
        yield path


def update_page(
    path: Path,
    dry_run: bool = False,
    model_id: str = DEFAULT_MODEL_ID,
    region: str = DEFAULT_REGION,
) -> tuple[str, int]:
    """Stamp the `tokens` field on a single page.

    Counts tokens on the stripped baseline (existing `tokens` field
    removed before encoding) so the stored count is stable across runs.

    Returns (status, count) where status is one of
    "updated", "unchanged", "skipped".

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
        count = count_tokens(baseline, model_id=model_id, region=region)
    except Exception as exc:  # noqa: BLE001 — keep run going on API errors
        print(f"[warn] skipping {path}: token count failed: {exc}", file=sys.stderr)
        return ("skipped", 0)

    if post.metadata.get("tokens") == count:
        return ("unchanged", count)

    if not dry_run:
        # Update the tokens field while preserving original YAML formatting.
        # At this point, we know has_frontmatter is True (checked earlier)
        fm_lines = parts[1].strip().split("\n")
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


def update_vault(
    wiki: Path,
    dry_run: bool = False,
    model_id: str = DEFAULT_MODEL_ID,
    region: str = DEFAULT_REGION,
) -> dict[str, list[str]]:
    """Walk `wiki` and `work/`, stamp `tokens` on every page, return {updated, unchanged, skipped} lists."""
    result: dict[str, list[str]] = {"updated": [], "unchanged": [], "skipped": []}
    workspace = wiki.parent

    # Process wiki pages
    for page in iter_pages(wiki):
        status, _ = update_page(page, dry_run=dry_run, model_id=model_id, region=region)
        result[status].append(str(page.relative_to(workspace)))

    # Process work items (sibling of wiki)
    work_dir = workspace / "work"
    if work_dir.exists():
        for page in iter_pages(work_dir):
            status, _ = update_page(page, dry_run=dry_run, model_id=model_id, region=region)
            result[status].append(str(page.relative_to(workspace)))

    for bucket in result.values():
        bucket.sort()
    return result


def main() -> None:
    p = argparse.ArgumentParser(description="Stamp `tokens` frontmatter across the wiki")
    p.add_argument("--dry-run", action="store_true", help="Print changes without writing")
    p.add_argument("--json", action="store_true", help="Machine-readable output")
    p.add_argument("--model-id", default=DEFAULT_MODEL_ID, help="Bedrock model ID for token counting")
    p.add_argument("--region", default=DEFAULT_REGION, help="AWS region for Bedrock")
    args = p.parse_args()

    wiki, _ = resolve_wiki_and_repo()
    result = update_vault(wiki, dry_run=args.dry_run, model_id=args.model_id, region=args.region)

    if args.json:
        print(json.dumps(result, indent=2))
        return

    label = "Would update" if args.dry_run else "Updated"
    print(f"{label} {len(result['updated'])} • Unchanged {len(result['unchanged'])} • Skipped {len(result['skipped'])}")
    for kind in ("updated", "skipped"):
        for rel in result[kind][:20]:
            print(f"  [{kind}] {rel}")


if __name__ == "__main__":
    main()
