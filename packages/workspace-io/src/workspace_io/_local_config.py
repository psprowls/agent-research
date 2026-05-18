"""Minimal line-by-line parser for .graph-wiki.local.yaml.

No PyYAML dependency. Same style as manifest.py — recognizes flat
`key: value` pairs at the top level. Skips blanks, comments, and
malformed lines silently.
"""
from __future__ import annotations

from pathlib import Path


def read(path: Path) -> dict[str, str]:
    """Read .graph-wiki.local.yaml. Returns dict of all top-level key:value pairs.

    Returns {} if the file does not exist. Malformed lines are skipped.
    Inline `# ...` comments are stripped from values. Surrounding quotes
    (single or double) are stripped from values.
    """
    if not Path(path).exists():
        return {}

    result: dict[str, str] = {}
    for raw_line in Path(path).read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        if ":" not in line:
            continue
        key, _, value = line.partition(":")
        key = key.strip()
        if not key:
            continue
        value = value.strip()
        # Strip inline comment (only outside quotes — naive check is fine here:
        # if value starts with a quote, take the quoted span; otherwise split on #).
        if value.startswith(('"', "'")):
            quote = value[0]
            end = value.find(quote, 1)
            if end > 0:
                value = value[1:end]
            else:
                value = value[1:]
        else:
            hash_idx = value.find("#")
            if hash_idx >= 0:
                value = value[:hash_idx].rstrip()
        result[key] = value
    return result
