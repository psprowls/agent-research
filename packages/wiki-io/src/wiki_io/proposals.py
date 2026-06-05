"""Living Wiki — curated-page proposal ledger (shared foundation).

One markdown note per proposed curated-page change, under `wiki/proposals/`.
Identity is the filename `<kind>-<target_slug>.md`; frontmatter is the machine
contract; the body is regenerated from `origins[]` while `status: proposed`.

Two producers write here via `upsert_proposal`: M3's ingest-time extractor pass
(`source: ingest`) and M4's scan-time drift detector (`source: drift`, next
spec). A human flips `status` to approved/rejected (or via `gw wiki proposal
…`); a deferred creation consumer acts on `approved` notes. Pure Python — no
LLM, no graph.

Public API:
    SUGGESTION_KINDS, HUMAN_DECIDED
    proposal_path(wiki, kind, target_slug) -> Path
    read_proposal(path) -> dict
    list_proposals(wiki, status=None, kind=None) -> list[dict]
    upsert_proposal(wiki, proposal) -> dict
    render_proposal_body(record) -> str
    set_proposal_status(wiki, kind, target_slug, status) -> bool
    split_proposal_id(proposal_id) -> tuple[str, str]
"""

from __future__ import annotations

import os
from pathlib import Path

import frontmatter
import yaml

SUGGESTION_KINDS = frozenset({"concept", "adr", "architecture"})
HUMAN_DECIDED = frozenset({"approved", "rejected", "created"})

# Fixed key order so yaml.safe_dump(..., sort_keys=False) is deterministic.
_RECORD_KEY_ORDER = ("kind", "mode", "target_slug", "title", "status", "origins")
# `detected_commit`/`hash` are M4-reserved (the ingest producer never sets them).
_ORIGIN_KEY_ORDER = ("ref", "source", "rationale", "detected_commit", "hash")


def _ordered_origin(origin: dict) -> dict:
    """Canonical key order for one origin entry; drops absent / None keys."""
    return {k: origin[k] for k in _ORIGIN_KEY_ORDER if k in origin and origin[k] is not None}


def _ordered_record(record: dict) -> dict:
    """Canonical key order for a proposal record, origins included."""
    rec = {k: record[k] for k in _RECORD_KEY_ORDER if k in record}
    rec["origins"] = [_ordered_origin(o) for o in record.get("origins", [])]
    return rec


def proposal_path(wiki: Path, kind: str, target_slug: str) -> Path:
    """Identity → `<wiki>/proposals/<kind>-<target_slug>.md`."""
    return wiki / "proposals" / f"{kind}-{target_slug}.md"


def split_proposal_id(proposal_id: str) -> tuple[str, str]:
    """Split a `<kind>-<target_slug>` id into (kind, target_slug).

    Kinds are distinct prefixes (`concept-`, `adr-`, `architecture-`), so the
    first matching prefix wins. Raises ValueError on an unknown kind.
    """
    for kind in SUGGESTION_KINDS:
        prefix = f"{kind}-"
        if proposal_id.startswith(prefix):
            return kind, proposal_id[len(prefix):]
    raise ValueError(
        f"invalid proposal id {proposal_id!r}: expected <kind>-<target_slug> "
        f"with kind in {sorted(SUGGESTION_KINDS)}"
    )


def render_proposal_body(record: dict) -> str:
    """Render `origins[]` into the human-readable evidence body.

    One block per origin: a `**<source> · [[<ref>]]**` heading line followed by
    the rationale. Regenerated on every upsert while `status: proposed`.
    """
    proposal_id = f"{record['kind']}-{record['target_slug']}"
    comment = (
        "<!-- Body regenerated from origins[] while status: proposed. Do not "
        "edit here;\n"
        f"     approve via `gw wiki proposal approve {proposal_id}`. -->"
    )
    lines = [comment, ""]
    for o in record.get("origins", []):
        lines.append(f"**{o.get('source', '')} · [[{o.get('ref', '')}]]**")
        rationale = (o.get("rationale") or "").strip()
        if rationale:
            lines.append(rationale)
        lines.append("")
    return "\n".join(lines).rstrip("\n")


def read_proposal(path: Path) -> dict:
    """Parse one note into {kind, mode, target_slug, title, status, origins[]}."""
    post = frontmatter.load(path)
    m = post.metadata
    origins = m.get("origins") or []
    return {
        "kind": m.get("kind", ""),
        "mode": m.get("mode", "create_new"),
        "target_slug": m.get("target_slug", path.stem),
        "title": m.get("title", ""),
        "status": m.get("status", "proposed"),
        "origins": [dict(o) for o in origins if isinstance(o, dict)],
    }


def _serialize(record: dict, body: str) -> str:
    """Frame an ordered record + body into the canonical note text.

    Deterministic dump (sort_keys=False over a pre-ordered dict) + exactly one
    trailing newline, mirroring wiki_io.entity_writer._render_page_text.
    """
    rec = _ordered_record(record)
    yaml_block = yaml.safe_dump(
        rec,
        sort_keys=False,
        default_flow_style=False,
        allow_unicode=True,
        width=10_000,
    ).rstrip("\n")
    return f"---\n{yaml_block}\n---\n{body}".rstrip("\n") + "\n"


def _atomic_write(path: Path, text: str) -> None:
    """Write `text` to `path` via temp-file + os.replace. Caller must ensure path.parent exists."""
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(text, encoding="utf-8")
    os.replace(tmp, path)
