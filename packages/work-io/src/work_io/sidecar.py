"""Build, write, load, and staleness-check the work-index.json sidecar."""

from __future__ import annotations

import json
import tempfile
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

SCHEMA_VERSION = 1


def build_sidecar(work_dir: Path, vault_commit: str | None) -> dict:
    """Walk work_dir/*.md (excluding archived/), parse each item, return sidecar dict."""
    from work_io.frontmatter import parse as fm_parse

    items = []
    for md in sorted(work_dir.glob("*.md")):
        try:
            fm, _ = fm_parse(md.read_text(encoding="utf-8"))
        except (ValueError, Exception):
            continue
        items.append(
            {
                "slug": md.stem,
                "title": str(fm.get("title", "")),
                "kind": str(fm.get("kind", "")),
                "status": str(fm.get("status", "")),
                "severity": fm.get("severity") or None,
                "blast_radius": fm.get("blast_radius") or None,
                "opened": str(fm.get("opened", "")),
                "updated": str(fm.get("updated", "")),
            }
        )

    items.sort(key=lambda x: (-_date_int(x["opened"]), x["slug"]))

    by_status = Counter(i["status"] for i in items if i["status"])
    by_kind = Counter(i["kind"] for i in items if i["kind"])
    by_severity = Counter(i["severity"] for i in items if i["severity"])
    by_blast_radius = Counter(i["blast_radius"] for i in items if i["blast_radius"])

    return {
        "schema_version": SCHEMA_VERSION,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "vault_commit": vault_commit,
        "counts": {
            "by_status": dict(by_status),
            "by_kind": dict(by_kind),
            "by_severity": dict(by_severity),
            "by_blast_radius": dict(by_blast_radius),
        },
        "items": items,
    }


def write_sidecar(wiki: Path, sidecar: dict) -> None:
    """Atomically write sidecar dict to wiki/work-index.json (write-temp + rename)."""
    target = wiki / "work-index.json"
    with tempfile.NamedTemporaryFile(mode="w", suffix=".tmp", dir=wiki, delete=False, encoding="utf-8") as f:
        json.dump(sidecar, f, indent=2, ensure_ascii=False)
        tmp_path = Path(f.name)
    tmp_path.rename(target)


def load_sidecar(wiki: Path) -> dict | None:
    """Return parsed sidecar dict or None if absent."""
    target = wiki / "work-index.json"
    if not target.exists():
        return None
    return json.loads(target.read_text(encoding="utf-8"))


def is_stale(sidecar: dict, work_dir: Path) -> bool:
    """True if any item's updated date > sidecar generated_at date."""
    from work_io.frontmatter import parse as fm_parse

    generated_prefix = sidecar.get("generated_at", "")[:10]
    if not generated_prefix:
        return True

    for md in work_dir.glob("*.md"):
        try:
            fm, _ = fm_parse(md.read_text(encoding="utf-8"))
            updated = str(fm.get("updated", ""))[:10]
            if updated > generated_prefix:
                return True
        except Exception:
            continue
    return False


def _date_int(date_str: str) -> int:
    """YYYY-MM-DD -> int for sort (higher = more recent). 0 on failure."""
    try:
        return int(date_str.replace("-", ""))
    except (ValueError, AttributeError):
        return 0
