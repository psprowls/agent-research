#!/usr/bin/env python3
"""graph_health.py — audit a graph-io code.db for unpopulated / unresolved data.

Usage:
    python3 graph_health.py [path/to/code.db]

Defaults to .graph-wiki/code.db under the current directory. Read-only.
"""
from __future__ import annotations

import sqlite3
import sys
from pathlib import Path

DB = Path(sys.argv[1] if len(sys.argv) > 1 else ".graph-wiki/code.db")


def q(conn, sql, params=()):
    return conn.execute(sql, params).fetchall()


def hr(title):
    print(f"\n{'=' * 70}\n{title}\n{'=' * 70}")


def main() -> None:
    if not DB.exists():
        sys.exit(f"no db at {DB}")
    conn = sqlite3.connect(f"file:{DB}?mode=ro", uri=True)

    hr("METADATA")
    for k, v in q(conn, "SELECT key, value FROM metadata"):
        print(f"  {k:24} {v}")

    hr("NODES — completeness by kind  (total / no-attrs / no-uri / no-path)")
    rows = q(conn, """
        SELECT kind, COUNT(*),
          SUM(attrs_json IS NULL OR attrs_json IN ('','{}')),
          SUM(uri IS NULL OR uri=''),
          SUM(path IS NULL OR path='')
        FROM nodes GROUP BY kind ORDER BY 2 DESC""")
    print(f"  {'kind':14}{'total':>8}{'noattr':>8}{'nouri':>8}{'nopath':>8}")
    for kind, total, na, nu, np in rows:
        print(f"  {kind:14}{total:>8}{na:>8}{nu:>8}{np:>8}")

    hr("EDGES — resolution status")
    rows = q(conn, """
        SELECT kind,
          SUM(attrs_json LIKE '%\"unresolved\"%') AS unresolved,
          SUM(attrs_json LIKE '%\"exact\"%')      AS exact,
          SUM(attrs_json LIKE '%\"ambiguous\"%')  AS ambiguous,
          COUNT(*) AS total
        FROM edges GROUP BY kind ORDER BY 2 DESC""")
    print(f"  {'kind':22}{'unres':>8}{'exact':>8}{'ambig':>8}{'total':>8}")
    for kind, unr, ex, amb, total in rows:
        print(f"  {kind:22}{unr or 0:>8}{ex or 0:>8}{amb or 0:>8}{total:>8}")

    hr("UNRESOLVED call/export placeholders (kind='unresolved_symbol') — where do they really live?")
    print("  Distinct placeholder names whose target exists under a concrete code kind:")
    rows = q(conn, """
        WITH stub AS (SELECT DISTINCT name FROM nodes WHERE kind='unresolved_symbol' AND path IS NULL)
        SELECT n.kind, COUNT(DISTINCT n.name)
        FROM nodes n JOIN stub ON n.name=stub.name
        WHERE n.path IS NOT NULL GROUP BY n.kind ORDER BY 2 DESC""")
    for kind, c in rows:
        print(f"    target defined as {kind:10} {c}")
    (resolvable, external), = q(conn, """
        WITH stub AS (SELECT DISTINCT name FROM nodes WHERE kind='unresolved_symbol' AND path IS NULL)
        SELECT
          SUM(EXISTS(SELECT 1 FROM nodes r WHERE r.name=stub.name AND r.path IS NOT NULL)),
          SUM(NOT EXISTS(SELECT 1 FROM nodes r WHERE r.name=stub.name AND r.path IS NOT NULL))
        FROM stub""")
    print(f"\n    distinct names with any concrete definition : {resolvable}")
    print(f"    distinct names external/unknown            : {external}")

    hr("FILE import placeholders (uri IS NULL) — shape of the unresolved specifiers")
    rows = q(conn, """
        SELECT CASE
            WHEN path LIKE '../%' OR path LIKE './%' THEN '(relative import spec)'
            WHEN path LIKE '%.js'  THEN '.js (extensionless target?)'
            WHEN path LIKE '%/%'   THEN '(bare path-like)'
            WHEN path LIKE '%.%'   THEN '(dotted python module)'
            ELSE '(bare specifier)' END AS shape,
          COUNT(*)
        FROM nodes WHERE kind='file' AND (uri IS NULL OR uri='')
        GROUP BY shape ORDER BY 2 DESC""")
    for shape, c in rows:
        print(f"    {shape:32} {c}")
    print("\n  Sample unresolved file specifiers:")
    for (p,) in q(conn, "SELECT path FROM nodes WHERE kind='file' AND uri IS NULL AND path LIKE '%/%' LIMIT 8"):
        print(f"    {p}")

    conn.close()


if __name__ == "__main__":
    main()
