"""Render lists of dataclass records as JSON or aligned-column human output."""

from __future__ import annotations

import dataclasses
import json
from typing import Any, Iterable


def _to_dict(record: Any) -> dict[str, Any]:
    if dataclasses.is_dataclass(record) and not isinstance(record, type):
        return dataclasses.asdict(record)
    return dict(record)


def _is_importer_batch(rows: list[Any]) -> bool:
    # Avoid an explicit import cycle (_format must not import queries at module load).
    return bool(rows) and type(rows[0]).__name__ == "ImporterRecord"


def _importer_human(rows: list[Any]) -> str:
    if not rows:
        return ""
    formatted = [
        {
            "path": r.path,
            "symbols": "(" + ", ".join(r.symbols) + ")" if r.symbols else "",
            "depth": str(r.depth),
        }
        for r in rows
    ]
    keys = ["path", "symbols", "depth"]
    widths = {k: max(len(row[k]) for row in formatted) for k in keys}
    return "\n".join(
        "  ".join(row[k].ljust(widths[k]) for k in keys) for row in formatted
    )


def _importer_json(rows: list[Any]) -> str:
    flat: list[dict[str, Any]] = []
    for r in rows:
        if r.symbols:
            for sym in r.symbols:
                flat.append({"path": r.path, "symbol": sym, "depth": r.depth})
        else:
            flat.append({"path": r.path, "symbol": None, "depth": r.depth})
    return json.dumps(flat, default=str)


def render(records: Iterable[Any], fmt: str) -> str:
    rows = list(records)
    if _is_importer_batch(rows):
        if fmt == "json":
            return _importer_json(rows)
        if fmt == "human":
            return _importer_human(rows)
        raise ValueError(f"unknown format: {fmt!r}")

    dicts = [_to_dict(r) for r in rows]
    if fmt == "json":
        return json.dumps(dicts, default=str)
    if fmt == "human":
        if not dicts:
            return ""
        keys = list(dicts[0].keys())
        widths = {k: max(len(str(r.get(k, ""))) for r in dicts + [dict.fromkeys(keys, k)]) for k in keys}
        lines = []
        for r in dicts:
            lines.append("  ".join(str(r.get(k, "")).ljust(widths[k]) for k in keys))
        return "\n".join(lines)
    raise ValueError(f"unknown format: {fmt!r}")
