---
phase: 44-scanner-generated-index
plan: 01
status: complete
completed_at: 2026-05-27
---

# Plan 44-01 Summary — Index Generator Module + Unit Tests

## Outcome

Created `packages/wiki-io/src/wiki_io/index_generator.py` (640 lines) and
`packages/wiki-io/tests/test_index_generator.py` (973 lines, includes Plan 02
tests as well — both plans landed in a single test file). Conftest extended
with `make_index_fixture_graph` factory fixture.

`update_index.py` and `packages/wiki-io/pyproject.toml` are byte-identical to
pre-Phase-44 state (D-01, D-22 verified via `git status` — both unchanged).

## Test Counts (Plan 01 surface)

| Class / Test | Count |
|---|---|
| `TestIndexWriteResult` | 4 (shape, frozen, module constants, entry_link) |
| `TestQualifyingDomains` | 10 (package x3, test_suite x2, dependency x3, plugin, invalid) |
| `TestPlacement` | 6 (single, zero, multi, plugin, sort order, intra-domain parents) |
| `TestCuratedScan` | 7 (empty, missing, basic, generated, dotfiles, fallback title, sort) |
| `TestWorkScan` | 4 (missing, basic, skip index, skip archived) |
| `TestRenderDomainTree` | 3 (single, sub-domain, empty omission) |
| `TestRenderByKind` | 3 (sort order, empty omission, test_suites subheading) |
| `test_generate_index_against_fixture_graph` | 1 (integration happy-path) |
| **Plan 01 total** | **38 passing** |

## Decisions Landed

- `CURATED_LANES` uses bare lane names (`"architecture"`, not `"wiki/architecture"`).
  This is a deliberate correction of CONTEXT.md D-12's example — `wiki_root` IS
  the wiki directory, so adding the `wiki/` prefix would double-prefix paths.
  The decision intent (4 lanes, this order, these labels) is preserved exactly.
- `_parse_frontmatter` was ported verbatim from `update_index.py::parse_frontmatter`
  (regex subset, no PyYAML). This honors D-22 (no new dependencies) and is the
  minimum-surface port.
- `make_index_fixture_graph` landed as a pytest **fixture** in `tests/conftest.py`
  that returns the factory callable; tests inject it as a parameter. The underlying
  builder uses `graph_io.upsert.upsert_records` so Phase 43's schema invariants
  (uri column projection, attrs_json) are exercised.
- `PlacedEntity` is a frozen dataclass with `parent_pkg_names: tuple[str, ...]`
  to carry intra-domain nesting info (D-06) from `_place_entities` into
  `_render_domain_section`.
- `_render_domain_section` recursion uses depth-prefixed headings:
  `## Domain: X` at depth 0, `### Sub-Domain: X` at depth 1+.
- `_render_domains` emits `## Domains — <repo>` header only when a `repository`
  node exists (otherwise just `## Domains`).

## Helper Signatures (D-21 verification)

All helpers from D-21 implemented as documented in the plan:

- `_compute_qualifying_domains(conn, *, kind, name) -> set[str]`
- `_consumer_pkgs_in_domain(conn, *, kind, entity_name, domain_name) -> tuple[str, ...]`
- `_place_entities(conn) -> tuple[dict[str, list[PlacedEntity]], list[PlacedEntity]]`
- `_parse_frontmatter(text) -> dict[str, str]`
- `_infer_title(path, fm) -> str`
- `_entry_link(path, title) -> str`
- `_scan_curated_lane(wiki_root, lane_dir_rel) -> list[dict[str, str]]`
- `_scan_work(workspace_root) -> list[dict[str, str]]`
- `_list_subdomains(conn, parent_name) -> list[str]`
- `_is_top_level_domain(conn, name) -> bool`
- `_render_domain_section(conn, domain_buckets, *, domain_name, depth) -> list[str]`
- `_render_domains(conn, domain_buckets, wiki_root) -> tuple[list[str], int]`
- `_render_by_kind(by_kind_entities) -> tuple[list[str], int]`
- `_render_curated_section(label, entries) -> list[str]`
- `_render(conn, wiki_root) -> tuple[str, int, int, int, int]`
- `generate_index(conn, wiki_root) -> IndexWriteResult`

No deviations from the planned D-21 surface.

## Verification

- All Plan 01 task-level commands green (`pytest tests/test_index_generator.py::Test*` and the integration test)
- `uv run --package wiki-io pytest -x` exits 0 (1288 passed, 35 skipped)
- `update_index.py` byte-identical: `git status` shows no modification
- `pyproject.toml` byte-identical: `git status` shows no modification

## Next

Plan 02 covers determinism, write-if-changed, edge cases, and the syrupy
snapshot — all 11 of those tests have been authored alongside Plan 01's
38 in the same file. See `44-02-SUMMARY.md`.
