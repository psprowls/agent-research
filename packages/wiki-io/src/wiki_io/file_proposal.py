"""file_proposal.py — file one curated-page proposal into the wiki/proposals/ ledger.

CLI-shaped entry point for the CC plugin's ingest flow: batch workers report
proposals as data and the orchestrator (or single-mode ingestor, for a page
the user declined) shells out here, so the ledger format is owned by
`wiki_io.proposals`, not prompts. Wraps `upsert_proposal` — same queue and
approval flow as core's Bedrock ingest (`source: ingest` origins; duplicate
targets across sources merge into one note's `origins[]`).

Exports:
    file_proposal(wiki, kind, target_slug, title, ref, rationale, evidence=None, mode="create_new") -> dict
    main(argv=None) -> None    (argparse CLI; the plugin shim calls this)
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from wiki_io.ingest_source import slugify
from wiki_io.proposals import SUGGESTION_KINDS, proposal_path, upsert_proposal


def file_proposal(
    wiki: Path,
    kind: str,
    target_slug: str,
    title: str,
    ref: str,
    rationale: str,
    evidence: list[str] | None = None,
    mode: str = "create_new",
) -> dict:
    """Upsert one ingest-sourced proposal; returns the merged record.

    The target slug is normalized via `slugify` (LLM-supplied input guards the
    `<kind>-<target_slug>.md` filename contract). A human-decided note is
    returned untouched — `upsert_proposal` never stomps approved/rejected/created.
    """
    if kind not in SUGGESTION_KINDS:
        raise ValueError(f"invalid kind {kind!r}: expected one of {sorted(SUGGESTION_KINDS)}")
    origin: dict = {"ref": ref, "source": "ingest", "rationale": rationale}
    if evidence:
        origin["evidence"] = list(evidence)
    proposal = {
        "kind": kind,
        "mode": mode,
        "target_slug": slugify(target_slug),
        "title": title,
        "origin": origin,
    }
    return upsert_proposal(wiki, proposal)


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description="File a curated-page proposal into wiki/proposals/.")
    parser.add_argument("--kind", required=True, choices=sorted(SUGGESTION_KINDS))
    parser.add_argument("--target-slug", required=True, help="Kebab slug of the proposed page (normalized)")
    parser.add_argument("--title", required=True)
    parser.add_argument("--ref", required=True, help="Origin ref, e.g. sources/2026-06-foo")
    parser.add_argument("--rationale", required=True)
    parser.add_argument("--evidence", action="append", default=[], help="Repeatable evidence bullet")
    parser.add_argument("--mode", choices=["create_new", "update_existing"], default="create_new")
    parser.add_argument("--workspace", default="", help="Workspace path (default: env / config discovery)")
    parser.add_argument("--json", action="store_true", dest="json_output")
    args = parser.parse_args(argv)

    from wiki_io._workspace import resolve_wiki_and_repo

    workspace_path = Path(args.workspace).expanduser().resolve() if args.workspace else None
    wiki, _ = resolve_wiki_and_repo(workspace_path)

    record = file_proposal(
        wiki,
        kind=args.kind,
        target_slug=args.target_slug,
        title=args.title,
        ref=args.ref,
        rationale=args.rationale,
        evidence=args.evidence,
        mode=args.mode,
    )
    path = proposal_path(wiki, record["kind"], record["target_slug"])
    if args.json_output:
        print(json.dumps({"path": str(path), "status": record["status"], "origins": len(record["origins"])}, indent=2))
        return
    print(f"{record['status']}: {path} ({len(record['origins'])} origin(s))")
