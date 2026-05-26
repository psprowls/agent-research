# Phase 36: `cg find` Parser Ergonomics — Research

**Phase:** 36 — `cg find` Parser Ergonomics
**Researched:** 2026-05-26
**Status:** Research complete

> Note: This phase has 11 locked decisions in `36-CONTEXT.md` (D-01..D-11). Research focuses on
> the *how* — concrete code shapes, SQL, file edits — not re-deriving the *what*.

---

## Question this research answers

What do we need to know to plan Phase 36 well — i.e., what are the precise code shapes,
SQL forms, and migration mechanics so the planner can write a one-commit hard-cut PLAN
without further investigation?

---

## 1. Parser swap site (D-04, D-05, D-03)

**File:** `packages/graph-io/src/graph_io/cli/q_find.py`

Current implementation (lines 14-16):

```python
def add_arguments(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("name")
    parser.add_argument("--kind", default=None)
```

Target shape after Phase 36:

```python
from graph_io.queries import _VALID_KINDS  # or a lightweight accessor

def add_arguments(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "--name",
        default=None,
        help="Filter by node name (exact match).",
    )
    parser.add_argument(
        "--kind",
        default=None,
        choices=sorted(_VALID_KINDS),
        help="Filter by node kind. Combines with other filters via AND.",
    )
    parser.add_argument(
        "--in-package",
        dest="in_package",
        default=None,
        help="Filter results to nodes contained in the named package "
             "(case-insensitive exact match).",
    )


def run(args: argparse.Namespace) -> int:
    # D-01: enforce at-least-one-filter rule.
    if args.name is None and args.kind is None and args.in_package is None:
        # parser.error() prints USAGE + msg, exits 2. We need a handle to the parser;
        # easiest is to re-import via argparse.ArgumentParser dispatch from main.
        # Alternative: raise SystemExit(2) with a stderr write directly.
        # See §1.1 below — main.py builds the parser; sub-parsers are not on `args`.
```

### 1.1 How to call `parser.error()` from `run(args)`

Problem: `q_find.py:run()` only receives `args` (a `Namespace`), not the parser. argparse
does not stash the parser on `args` by default.

Two clean approaches (planner picks):

**(a) Surface the sub-parser via `set_defaults`.** In `main.py`'s `_build_parser()` (line 91):
add `sp.set_defaults(_parser=sp)` alongside the existing `sp.set_defaults(_module=mod)`.
Then `q_find.py:run()` calls `args._parser.error("...")`. Cheap; reusable for other
subcommands later.

**(b) Write to stderr + return `2` directly.** Skip `parser.error()` entirely and
emit:

```python
print("cg find requires at least one of --name, --kind, --in-package",
      file=sys.stderr)
return 2
```

Both honor SC#1 / SC#2 (no spurious exit 2 when valid flags are supplied) and D-01
(error when zero filters). Approach (a) gives a uniform argparse-style "usage:" prefix;
approach (b) is a one-liner without touching `main.py`.

**Recommendation (planner: confirm):** Approach (a). Cost: 1-line edit to `main.py`;
benefit: future subcommands can reuse `args._parser`. Note: `_parser` (leading underscore)
prevents `argparse` from emitting it as a CLI arg.

### 1.2 `_VALID_KINDS` import

`_VALID_KINDS` is module-level in `queries.py` (line 9). Direct import:

```python
from graph_io.queries import _VALID_KINDS
```

The leading underscore signals "private to the module" but Python doesn't enforce it; the
existing import style across the package already crosses underscore-prefixed boundaries
(see `graph_io._ignore` imports in `packages.py`). Direct import is consistent.

Alternative: add a public accessor `queries.valid_kinds() -> frozenset[str]`. Not strictly
needed for v1.7; recommend direct import to minimize surface area.

---

## 2. Query layer extension (D-06, D-07, D-08)

**File:** `packages/graph-io/src/graph_io/queries.py`

Current signature (line 166):

```python
def find(
    conn: sqlite3.Connection,
    *,
    name: str | None = None,
    kind: str | None = None,
) -> list[NodeRecord]:
```

Target signature:

```python
def find(
    conn: sqlite3.Connection,
    *,
    name: str | None = None,
    kind: str | None = None,
    in_package: str | None = None,
) -> list[NodeRecord]:
```

### 2.1 SQL shape for `--in-package`

The packages module (`graph_io/packages.py`, lines 122-131) creates `contains` edges
from `package` nodes to `file` nodes by directory-prefix. The schema (`schema.py`) has
one `nodes` table and one `edges` table.

**Containment graph for `--in-package <pkgname>`:**

A "node in package P" means: either (a) the node IS a file whose package has name P
(`package -contains-> file`), or (b) the node is a child of such a file
(`file -contains-> {function, class, method, …}`).

The cheapest expression: filter `nodes.path` to paths whose package's name matches.

```sql
SELECT n.kind, n.name, n.path, n.line, n.attrs_json
FROM nodes n
WHERE n.path IN (
    SELECT f.path
    FROM nodes p
    JOIN edges ce ON ce.src = p.id AND ce.kind = 'contains'
    JOIN nodes f ON ce.dst = f.id AND f.kind = 'file'
    WHERE p.kind = 'package' AND LOWER(p.name) = LOWER(?)
)
```

Then `AND name = ?` and/or `AND kind = ?` are appended as the existing 4 branches do.

**Why this shape:**
- Files attached to a package have `nodes.path` = the file path.
- Child symbols (functions, classes, methods) attached to those files have the SAME
  `nodes.path` as the file (see `_row_to_node` and the test fixture at
  `test_cli_smoke.py:28-34`).
- A single `path IN (subquery)` filter cleanly captures both file nodes and their
  child nodes in one pass.
- `LOWER(...)` on both sides delivers D-08's case-insensitive exact match.

**Edge case:** A file can be contained by multiple packages (root manifest + sub-package
manifest). The subquery returns each file path once per containing package; the outer
`IN` deduplicates. Multiple packages with the *same* short name would collapse into one
filter (intentional — D-08 says exact name match, not URI match).

**Verified:** `nodes.path` index exists (`idx_nodes_path`, schema.py line 27), so the
subquery filter on `n.path IN (...)` is index-backed.

### 2.2 SQL composition — 8-branch matrix vs single dynamic builder

Current `find()` has 3 branches (name only / name+kind / kind only). Adding `in_package`
expands to 7 valid combinations (D-01 forbids all-None). A 7-branch `if/elif` ladder is
explicit but ugly.

**Recommended planner approach: dynamic WHERE clause assembly.** Single SQL skeleton:

```python
where_parts: list[str] = []
params: list = []
if name is not None:
    where_parts.append("n.name = ?")
    params.append(name)
if kind is not None:
    where_parts.append("n.kind = ?")
    params.append(kind)
if in_package is not None:
    where_parts.append("n.path IN ("
                       "SELECT f.path FROM nodes p "
                       "JOIN edges ce ON ce.src = p.id AND ce.kind='contains' "
                       "JOIN nodes f ON ce.dst = f.id AND f.kind='file' "
                       "WHERE p.kind='package' AND LOWER(p.name) = LOWER(?))")
    params.append(in_package)

# D-01: at least one filter (defense-in-depth; CLI parser also enforces).
if not where_parts:
    raise ValueError(
        "find requires at least one of name, kind, or in_package"
    )

sql = (
    "SELECT kind, name, path, line, attrs_json FROM nodes n "
    "WHERE " + " AND ".join(where_parts)
)
# Order-by preserved when kind-only (matches current behavior at line 198):
if name is None and in_package is None:
    sql += " ORDER BY name"

rows = conn.execute(sql, tuple(params)).fetchall()
return [_row_to_node(r) for r in rows]
```

**Why this shape:**
- One SQL builder replaces 3 branches; expansion to a 4th filter dimension later is
  cheap.
- AND semantics (D-02) emerge for free from `" AND ".join(...)`.
- The kind-only ORDER BY is preserved — the existing test
  `test_queries.py::test_find_by_kind` expects ordered results.
- The existing `ValueError` for "no filters" is preserved at the query layer (D-03
  defense-in-depth) — Phase 37 librarian tools won't hit it because they'll always
  pass at least one filter, but it's still the right contract for non-CLI callers.

### 2.3 Backward-compatible kind validation

Current behavior (line 180-183) raises `ValueError` for invalid kind. With D-03,
argparse's `choices=` rejects invalid kinds at parse time *for the CLI*, but the
query-layer `ValueError` stays as defense-in-depth. No change to this block — keep
both layers.

---

## 3. 50-row cap + truncation notice (D-09)

**Planner decision point (per Claude's Discretion in CONTEXT):** Which surface owns
the cap — `queries.find()`, `q_find.py`, or `_format.render()`?

### 3.1 Surface analysis

**`queries.find()`:** Returns `list[NodeRecord]`. Capping here loses the "true count"
needed for the truncation notice unless we return a tuple `(rows, total)` or pre-count.

**`q_find.py:run()`:** Sits between `queries.find()` and `_format.render()`. It owns
the dataframe→string boundary already; capping here is local. But `_format.render()` is
where the next phase (37 LIBTOOLS-02) will land *its* cap for librarian tools, so
duplicating logic between `q_find.py` and `_format.render()` would mean two truncation
strings to keep in sync.

**`_format.render()`:** Receives an `Iterable[Any]`. Today it consumes the iterable
exhaustively. Capping here yields a single source of truth for "≤50 rows, with notice"
that Phase 37 inherits automatically.

**Recommendation: `_format.render()`.** It's the symmetric place for both CLI and
librarian-tool consumers (Phase 37 D-09 explicitly hangs LIBTOOLS-02 off this surface).

### 3.2 Concrete shape

Add a parameter `cap: int | None = 50` to `render()`. When `cap` is set and
`len(rows) > cap`, emit only the first `cap` rows plus a trailer line for human
format and a top-level wrapper for JSON.

```python
def render(records: Iterable[Any], fmt: str, cap: int | None = 50) -> str:
    rows = list(records)
    total = len(rows)
    truncated = cap is not None and total > cap
    if truncated:
        rows = rows[:cap]

    # ... existing body, but with `rows` now potentially trimmed ...

    if truncated:
        if fmt == "human":
            out = body + f"\n... showing {cap} of {total} (truncated)"
        elif fmt == "json":
            # Wrap as {"rows": [...], "truncated": true, "shown": cap, "total": total}.
            # Alternative: keep flat array + emit notice to stderr; planner picks.
            ...
    return out
```

**Trade-off the planner must resolve:** JSON consumers (tests, scripts) currently get a
flat array. Switching to a `{rows, truncated, ...}` envelope is a breaking shape change
for JSON.

**Two safer options:**
1. **JSON stays flat, truncation notice goes to stderr.** `q_find.py:run()` prints the
   notice via `print(..., file=sys.stderr)`. Tests can still assert exit 0 and parse
   stdout normally. Phase 37 librarian tools (which call `_format.render(fmt="human")`)
   get the inline notice. Recommend this approach.
2. **JSON wraps with envelope when truncated only.** Adds a runtime branch in JSON
   consumers; rejected — surprises future callers.

**Planner: pick (1).** Stderr-based truncation notice for JSON, inline trailer for
human format. No JSON envelope change.

### 3.3 Default behavior for non-find renderers

`render()` is used by all `q_*` CLI handlers (`q_callers`, `q_imports`, etc.). Defaulting
`cap=50` would silently truncate those too. Options:

**(a) Keep `cap=None` default; opt-in for `q_find` only.** `q_find.py:run()` passes
`cap=50` explicitly. Other handlers keep current behavior (no cap). Surgical.

**(b) Cap all `q_*` outputs at 50.** Aligns with Phase 37 LIBTOOLS-02 ("row results
hard-capped at 50") which itself wraps multiple queries. Riskier — could change
existing CLI outputs that scripts depend on.

**Recommendation: (a).** Phase 36 is scoped to `cg find`. Don't touch other handlers.
Phase 37 will need to revisit `_format.render()` again anyway to wire `cap=50` into
librarian tool flows.

---

## 4. Migration mechanics (D-10, D-11)

### 4.1 Test call sites — confirmed grep results

`grep -n '"find"' packages/graph-io/tests/` returns these lines (verified 2026-05-26):

| File | Line | Form | Needs update? |
|---|---|---|---|
| `test_smoke.py` | 23 | `"find"` in subcommand inventory | **No** — string in a list of subcommand names; not a CLI invocation |
| `test_cli_smoke.py` | 43 | `_cg(["find", "alpha", "--kind", "function"], ...)` | **Yes** — `find alpha …` |
| `test_cli_smoke.py` | 49 | `_cg(["--fmt", "json", "find", "alpha"], ...)` | **Yes** |
| `test_cli_smoke.py` | 91 | `_cg(["find", "alpha"], ...)` | **Yes** |
| `test_e2e.py` | 35 | `_cg(["--fmt", "json", "find", "alpha"], ...)` | **Yes** |
| `test_cli_exit_codes.py` | 108 | `["find", "x"]` in argv matrix | **Yes** |
| `test_cli_exit_codes.py` | 204 | `_cg(["find", "foo"], ...)` | **Yes** |
| `test_cli_anti_regression.py` | 84 | `_run_cli(["--fmt", "json", "find", "main"], ...)` | **Yes** |
| `test_cli_anti_regression.py` | 104 | `"find"` in `@pytest.mark.parametrize` list | **No** — just the kind name; the args matrix is on line 118 |
| `test_cli_anti_regression.py` | 118 | `"find": ["find", "main"]` argv mapping | **Yes** |

**Migration rewrites:**

```
["find", "alpha"]                    → ["find", "--name", "alpha"]
["find", "alpha", "--kind", "K"]     → ["find", "--name", "alpha", "--kind", "K"]
["find", "x"]                        → ["find", "--name", "x"]
["find", "foo"]                      → ["find", "--name", "foo"]
["find", "main"]                     → ["find", "--name", "main"]
```

**Note on `test_cli_anti_regression.py` lines 84 and 104:** Line 84 builds the fixture
DB by calling `find main` to resolve a known-good symbol. Line 104 is the kind name in
a parametrize list — the actual argv comes from line 118's `args_by_cmd` dict. Both
line 84's call and line 118's argv string list need `--name` inserted.

**Note on `test_cli_exit_codes.py` line 108:** This is inside a list of argvs for
`test_exit_4_schema_mismatch` (all subcommands tested against a schema-mismatched DB).
The test asserts `returncode == 4` (schema mismatch) regardless of args. Substituting
`["find", "--name", "x"]` keeps the test semantically identical — schema mismatch
fires before any query runs.

**Note on `test_cli_exit_codes.py` line 204:** Inside `test_cg_find_on_v1_db_exits_schema_mismatch`
— guards the existing exit-4 behavior on v1 DB. Substitute `["find", "--name", "foo"]`;
test still passes (the schema-mismatch handler short-circuits before query execution).

### 4.2 The anti-regression test (D-11)

**File:** `packages/graph-io/tests/test_cli_anti_regression.py`

**New test signature:**

```python
def test_find_positional_form_errors(post_phase33_fixture: FixtureRefs) -> None:
    """D-11: Old `cg find <name>` positional form must produce a parse error.

    Guards against silent regression — without this, a future refactor could
    re-add `parser.add_argument("name")` and every other test would still
    pass (they use `--name`).
    """
    refs = post_phase33_fixture
    result = _run_cli(["find", "foo.py"], refs.repo_dir)
    assert result.returncode != 0, (
        f"positional `cg find foo.py` should error, got 0: {result.stdout}"
    )
    # argparse default for surplus positionals is "unrecognized arguments".
    # Lowercase match so future argparse releases that capitalize don't break us.
    assert "unrecognized arguments" in result.stderr.lower(), result.stderr
```

**Why this exact shape:**
- `returncode != 0` (not `== 2`) lets the test survive if SystemExit numbering ever
  shifts.
- `"unrecognized arguments"` is argparse's stable phrase across Python 3.10-3.12; the
  specifics (`"unrecognized arguments: foo.py"`) match D-04's expected output.
- Lives in `test_cli_anti_regression.py` because that file is already the home for
  "this thing must not regress" guards (D-11).

### 4.3 Single-commit requirement

D-10 says all changes ship in one commit. The commit's `git add` list:

```
packages/graph-io/src/graph_io/cli/q_find.py
packages/graph-io/src/graph_io/cli/main.py            # if §1.1 approach (a)
packages/graph-io/src/graph_io/cli/_format.py         # for cap
packages/graph-io/src/graph_io/queries.py             # for in_package
packages/graph-io/tests/test_cli_smoke.py
packages/graph-io/tests/test_e2e.py
packages/graph-io/tests/test_cli_exit_codes.py
packages/graph-io/tests/test_cli_anti_regression.py
packages/graph-io/tests/test_queries.py               # if new in_package tests added (see §5)
```

`test_smoke.py` is unchanged (line 23 is just a subcommand-name inventory, not a CLI
invocation).

---

## 5. Test coverage for new behavior

The phase ships with locked SC#1/SC#2/SC#3 success criteria. To exercise the new
behavior with mechanical guards, the plan should add (at minimum):

1. **`test_cli_smoke.py::test_find_with_named_flags`** — `cg find --name alpha --kind function`
   exits 0 (mirrors SC#1).
2. **`test_cli_smoke.py::test_find_no_filters_errors`** — `cg find` (no args) exits 2
   with "at least one of" in stderr (D-01).
3. **`test_cli_smoke.py::test_find_invalid_kind_errors`** — `cg find --kind bogus`
   exits 2 with "choose from" or "invalid choice" in stderr (D-03 — argparse default
   wording is `"argument --kind: invalid choice: 'bogus'"`).
4. **`test_cli_smoke.py::test_find_in_package`** — `cg find --in-package demo` returns
   the seeded package's nodes (D-06).
5. **`test_cli_smoke.py::test_find_in_package_case_insensitive`** — `cg find --in-package DEMO`
   returns same results (D-08).
6. **`test_cli_smoke.py::test_find_in_package_unknown`** — `cg find --in-package zzz`
   exits 1 (or 0, planner: see §6 below) with zero rows (D-07).
7. **`test_cli_anti_regression.py::test_find_positional_form_errors`** — D-11.
8. **`test_queries.py::test_find_in_package` and `test_find_in_package_lowercase`** —
   unit-level coverage of `queries.find(in_package=...)`.

**Optional (truncation, D-09):** if the planner picks `_format.render(cap=50)`, add
either a unit test on `_format.render` or an integration test that seeds >50 nodes.
The integration shape is expensive (build a 50-package fixture). Unit test recommended:

```python
def test_render_caps_at_50() -> None:
    rows = [NodeRecord(kind="function", name=f"f{i}", path=None, line=None, attrs={})
            for i in range(75)]
    out = _format.render(rows, fmt="human", cap=50)
    lines = out.splitlines()
    assert len(lines) == 51, lines  # 50 rows + 1 trailer
    assert "showing 50 of 75" in lines[-1]
```

---

## 6. Exit-code semantics for zero-result (CONTEXT code_context note)

The CONTEXT `<code_context>` block flags an open question: `q_find.py:run()` currently
returns `SUCCESS` regardless of row count. SC#1/SC#2 say "exits 0 (found) or exit 1
(not-found), never exit 2 for arg-parse error when valid flags are supplied."

**Interpretation:** SC#2 is about *parse errors only* — when the user provides valid
named flags, the CLI must not exit 2 for an argparse-level failure. SC#2 does NOT
mandate that zero-result must exit 1.

**Current behavior** (zero-result → exit 0): is consistent with the surface idioms
across `cg` (e.g., `cg callers` also exits 0 on zero results).

**Recommendation: do NOT change exit-on-no-results to 1.** Out of scope for this phase.
SC#2 is satisfied by D-03 (invalid kind → argparse `choices=` → exit 2 IS a parse error,
which is fine — only "valid flags supplied" path is constrained). If the team later
wants a clean "found vs not-found" exit ladder, that's a separate phase.

**Planner note:** D-07 says "Unknown-package behavior is silent zero-result, exit 1."
That decision *is* in scope and forces a tiny departure: when `--in-package` is the
*only* filter and returns zero rows, the CLI exits 1. The cleanest way is in
`q_find.py:run()`:

```python
records = queries.find(conn, name=args.name, kind=args.kind, in_package=args.in_package)
# D-07: --in-package non-match → exit 1
if not records:
    return exit_codes.GENERIC  # = 1
return exit_codes.SUCCESS
```

But this *would* change existing behavior for `cg find --name <not-in-graph>` (which
today returns 0). That violates a tacit invariant — the cross-cutting tests
(`test_cli_smoke.py::test_imported_by_symbol_filter`, line 116-118) explicitly assert
exit 0 + empty stdout for zero-match filters.

**Cleanest resolution:** D-07 applies *only* to `--in-package` paths (as worded:
"Unknown-package behavior"). When `--name` or `--kind` returns zero, keep exit 0.

```python
records = queries.find(conn, name=args.name, kind=args.kind, in_package=args.in_package)
if args.in_package is not None and not records:
    return exit_codes.GENERIC  # D-07
print(_format.render(records, fmt=args.fmt, cap=50))
return exit_codes.SUCCESS
```

**However**, a tighter reading of D-07 ("Do NOT distinguish package-does-not-exist from
package-exists-but-empty") plus D-01's framing ("filter must match something") plus the
CONTEXT note that "planner: verify whether to return exit 1 on zero-row result" suggests
the planner might want a uniform "zero-result → exit 1" rule across all `cg find` paths.

**Planner: pick one.** This research recommends the narrower interpretation (only
`--in-package`-zero exits 1) because it's strictly D-07-conformant and minimizes blast
radius on existing zero-result behavior in tests.

---

## 7. Validation Architecture (Nyquist Dimension 8)

> Note: phase has `nyquist_validation_enabled=true` in config. This section sketches
> what VALIDATION.md should specify.

**Test pyramid for Phase 36:**

| Layer | Surface | Examples |
|---|---|---|
| Unit (fast) | `queries.find()` directly | `test_find_in_package`, `test_find_in_package_lowercase`, `test_find_all_three_filters` |
| CLI (subprocess) | `cg find …` | `test_find_with_named_flags`, `test_find_no_filters_errors`, `test_find_invalid_kind_errors`, `test_find_in_package_unknown` |
| Anti-regression | argparse refusal of positional | `test_find_positional_form_errors` |
| Format (unit) | `_format.render(cap=50)` | `test_render_caps_at_50` (if cap lands there) |

**Coverage matrix vs success criteria:**

| SC | Test |
|---|---|
| SC#1 (`--name foo.py --kind file` exits 0) | `test_find_with_named_flags` |
| SC#2 (no exit 2 for valid flags) | All passing test_cli_smoke tests by construction; `test_find_invalid_kind_errors` covers the *intended* exit-2 path |
| SC#3 (positional errors clearly + callers updated) | `test_find_positional_form_errors` + all migrated test files passing |

| Locked Decision | Coverage |
|---|---|
| D-01 (≥1 filter required) | `test_find_no_filters_errors` |
| D-02 (AND semantics) | `test_find_all_three_filters` (unit, with fixture covering name/kind/package overlap) |
| D-03 (argparse `choices=`) | `test_find_invalid_kind_errors` |
| D-04 (argparse default for positional) | `test_find_positional_form_errors` |
| D-05 (per-flag help) | not asserted (style decision, low ROI for tests) |
| D-06 (short package name match) | `test_find_in_package` |
| D-07 (`--in-package` unknown → exit 1) | `test_find_in_package_unknown` |
| D-08 (case-insensitive exact match) | `test_find_in_package_case_insensitive` |
| D-09 (50-row cap + notice) | `test_render_caps_at_50` (unit) — chosen over a 50-node integration fixture for cost |
| D-10 (single-commit migration) | git commit hygiene — manual verification at commit time, not a test |
| D-11 (anti-regression test) | self — `test_find_positional_form_errors` IS the implementation of D-11 |

---

## 8. Risks & gotchas

1. **`_VALID_KINDS` underscore privacy.** Direct import works but signals project-internal
   coupling. Acceptable for this phase; revisit if a third caller needs it.
2. **`parser.error()` needs the sub-parser handle.** See §1.1 — neither approach is wrong,
   but approach (a) (set_defaults `_parser=sp`) is the lower-friction one.
3. **JSON output stability.** Cap-via-stderr (§3.2 option 1) preserves the flat JSON array
   that existing tests parse. Choosing a JSON envelope would break the e2e JSON parse
   tests; this research recommends against it.
4. **Phase 35 hasn't merged yet.** STATE.md flags Pitfall 3 ("Phase 35 must merge before
   Phase 36"). At plan time, the plan is correct; at execute time, rebase against
   Phase 35's branch if it has merged in the interim. No file overlap is expected (Phase 35
   doesn't touch `cli/q_find.py`, `queries.py`, or `_format.py`).
5. **The "find a node in any package" interpretation.** `--in-package` matches nodes by
   directory containment, not by URI. A file at the repo root (no sub-package manifest)
   is contained by the *root* manifest's package. A `cg find --in-package <root-pkg-name>`
   query returns every node in the repo. This is the intended behavior per D-06 (short
   package name match) and D-09 (50-row cap exists precisely for this case).
6. **`q_describe_package.py` already proves the join shape.** See its SQL at
   `q_describe_package.py:30` — confirms the `package -contains-> file` edge pattern
   used in §2.1.

---

## 9. Files the planner WILL modify (forecast)

```
packages/graph-io/src/graph_io/cli/q_find.py          [REWRITE: parser + run() body]
packages/graph-io/src/graph_io/cli/main.py            [1-LINE EDIT: set_defaults _parser]
packages/graph-io/src/graph_io/cli/_format.py         [EXTEND: add cap parameter]
packages/graph-io/src/graph_io/queries.py             [EXTEND: find() in_package + SQL builder]
packages/graph-io/tests/test_cli_smoke.py             [MIGRATE 3 sites + ADD 6 tests]
packages/graph-io/tests/test_e2e.py                   [MIGRATE 1 site]
packages/graph-io/tests/test_cli_exit_codes.py        [MIGRATE 2 sites]
packages/graph-io/tests/test_cli_anti_regression.py   [MIGRATE 2 sites + ADD D-11 test]
packages/graph-io/tests/test_queries.py               [ADD 2-3 in_package unit tests]
```

`test_smoke.py` is **not** modified — line 23 is a subcommand inventory string list,
unaffected by the parser change.

---

## RESEARCH COMPLETE

Coverage: parser shape, query SQL, format-layer cap, test migration map, anti-regression
guard, exit-code interpretation, and Nyquist validation pyramid all specified. Planner
has unambiguous targets for every locked decision; remaining choices (parser.error()
mechanism, stderr-vs-envelope JSON truncation) are explicitly handed off with recommended
defaults.
