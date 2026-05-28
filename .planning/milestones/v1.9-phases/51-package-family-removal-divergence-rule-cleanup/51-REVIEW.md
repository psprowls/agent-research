---
phase: 51-package-family-removal-divergence-rule-cleanup
reviewed: 2026-05-27T00:00:00Z
depth: standard
files_reviewed: 18
files_reviewed_list:
  - packages/eval-harness/baselines/divergence-librarian.json
  - packages/eval-harness/src/eval_harness/divergence/librarian.py
  - packages/eval-harness/tests/test_divergence_baseline.py
  - packages/eval-harness/tests/test_divergence_checks.py
  - packages/eval-harness/tests/test_two_gate_scorer.py
  - packages/graph-io/src/graph_io/uri.py
  - packages/graph-io/tests/test_cli_main.py
  - packages/graph-io/tests/test_uri.py
  - packages/wiki-io/src/wiki_io/entity_writer.py
  - packages/wiki-io/src/wiki_io/link_rewriter.py
  - packages/wiki-io/src/wiki_io/lint/dependency.py
  - packages/wiki-io/tests/integration/test_entity_writer_integration.py
  - packages/wiki-io/tests/test_assets.py
  - packages/wiki-io/tests/test_entity_templates.py
  - packages/wiki-io/tests/test_entity_writer.py
  - packages/wiki-io/tests/test_link_rewriter_build_table.py
  - agents/graph-wiki-agent/src/graph_wiki_agent/commands/scan.py
  - agents/graph-wiki-agent/src/graph_wiki_agent/commands/migrate_vault.py
findings:
  critical: 0
  warning: 3
  info: 4
  total: 7
status: issues_found
---

# Phase 51: Code Review Report

**Reviewed:** 2026-05-27
**Depth:** standard
**Files Reviewed:** 18
**Status:** issues_found

## Summary

Phase 51 retracts the `package_family` entity kind across graph-io, wiki-io,
eval-harness (LIB-003 divergence rule), and supporting fixtures. The
mechanical surface — `ADMITTED_KINDS` (now 6 kinds), `STRUCTURAL_KEYS` (now
9 keys, `members` removed), `_URI_PREFIX_BY_KIND`, baselines, templates,
and CLI registry — is consistently scrubbed and well-guarded by regression
tests (`test_no_package_family_subcommand`, `test_no_package_family_template`,
`test_valid_kinds_excludes_package_family`, the explicit
`assert "package_family" not in ADMITTED_KINDS`, and the structural-keys
length-9 assertion).

The cross-package fix in `scan.py` + `migrate_vault.py` correctly switches
callers to `ADMITTED_KINDS` and `wiki_io.entity_writer` exports — no stale
`ADMITTED_KINDS_V18` references remain in source.

However, three residual `members` / `package-family` references were missed
by the cleanup sweep, and a small number of pre-existing test/code-quality
issues surface around the touched modules. None are correctness-critical
for the Phase 51 retraction itself, but two of the WARNING findings would
mislead a future reader trying to trace the kind retirement.

## Warnings

### WR-01: Dead `members` entry in `_NARRATIVE_RELATION_LABELS` after PKGFAM-03

**File:** `agents/graph-wiki-agent/src/graph_wiki_agent/commands/scan.py:297`
**Issue:** `_NARRATIVE_RELATION_LABELS` still contains `"members": "Members"`.
This label was the prose hint for the retired `package_family` kind. Phase 51
PKGFAM-03 dropped `members` from `STRUCTURAL_KEYS` and `SCANNER_OWNED_KEYS`
in `wiki_io.entity_writer`, so `scanner_frontmatter_for_node` will never
emit a `members` key for any of the 6 admitted kinds. The lookup in
`build_entity_narrative_prompt` (`for key, label in _NARRATIVE_RELATION_LABELS.items()`
followed by `if key not in relations: continue`) silently swallows it, so it
is dead but misleading — it implies a kind still emits a `Members` relation.

**Fix:**
```python
# Remove this line from _NARRATIVE_RELATION_LABELS:
"members":         "Members",
```
Add a one-line comment in the dict referencing PKGFAM-03 so future readers
know `members` was intentionally retired, not accidentally omitted.

### WR-02: `migrate_vault` commit message and dry-run preview reference a directory that should never exist

**File:** `agents/graph-wiki-agent/src/graph_wiki_agent/commands/migrate_vault.py:52`
**Issue:** The hard-coded `COMMIT_MESSAGE` advertises removing
`wiki/package-family/` as part of the v1.8 cutover. The Phase 51 retraction
removed `package_family` from `ADMITTED_KINDS` and `OLD_LAYOUT_ROOTS`
(`link_rewriter.OLD_LAYOUT_ROOTS` no longer contains `"package-family"`),
so `_git_rm_old_dirs` will never stage `wiki/package-family/` and the
commit message overstates what the cutover does. Worse: an operator running
`migrate-vault` against a vault that genuinely has a stale
`wiki/package-family/` directory will not have it removed, because that
prefix is no longer in `OLD_LAYOUT_ROOTS`. The commit message thus
documents a behavior the code no longer implements.

**Fix:**
```python
COMMIT_MESSAGE = """feat(46): v1.8 entity restructure cutover

Atomic vault migration:
- Populate wiki/entities/ via write_entities
- Rewrite inbound wikilinks across 5 curated lanes
- Remove wiki/packages/, wiki/dependencies/, wiki/domain/, wiki/plugin/
- Regenerate wiki/index.md (generate_index) + per-folder sub-indexes (update_index)
- Write .graph-wiki/manifest.json migration marker

Refs: MIGRATION-01, MIGRATION-02, MIGRATION-03, MIGRATION-04, MIGRATION-05
"""
```
Separately, if any deployed vault still carries a legacy
`wiki/package-family/` directory, decide whether `OLD_LAYOUT_ROOTS` should
re-include it as a "remove only, never resolve" entry. If not, document in
RESEARCH.md that pre-Phase-51 vaults must `git rm -r wiki/package-family/`
manually before running the migrator.

### WR-03: `test_link_rewriter_build_table.py` fixture uses non-canonical URI prefixes

**File:** `packages/wiki-io/tests/test_link_rewriter_build_table.py:25,34`
**Issue:** The `fake_graph` fixture wires synthetic `NodeRecord`s with
`uri="dep:pypi/click"` and `uri="suite:agent-research/unit"`. The canonical
URI prefixes in `graph_io.uri` (and consumed by `wiki_io.entity_writer._URI_PREFIX_BY_KIND`)
are `dependency:` and `test_suite:` — not `dep:` or `suite:`. As a
consequence the test asserts `table["dependencies/pypi/click/overview"]
== "entities/dep__pypi__click"` (line 70-71), which only matches because
`encode_slug` blindly substitutes on whatever junk you hand it. In
production the same `build_rewrite_table` call would produce
`entities/dependency__pypi__click`, which means the test does not catch
a real-world `_new_slug` regression for either kind. This pre-dates Phase
51 but the file is in scope for this review and the fixture became more
load-bearing now that `package_family` is gone (fewer counter-tests).

**Fix:**
```python
nodes_by_kind = {
    "dependency": [
        _node("dependency", "click", "dependency:pypi/click", ecosystem="pypi"),
    ],
    ...
    "test_suite": [
        _node("test_suite", "unit", "test_suite:agent-research/unit"),
    ],
}
```
Update the asserted slugs to `entities/dependency__pypi__click` (lines 70,
71) so the test exercises the real URI alphabet.

## Info

### IN-01: `entity_writer.py` mixes module-level imports inside the file body

**File:** `packages/wiki-io/src/wiki_io/entity_writer.py:175-194`
**Issue:** The Phase 43 expansion appends `import datetime as _dt`, `import
fcntl`, `import json`, `import logging`, `import os`, `import re`, `import
sqlite3`, `from contextlib import contextmanager`, `from dataclasses
import dataclass, field`, `from importlib.resources import files`, plus
`frontmatter` and `yaml` — all with `# noqa: E402` because they sit below
the Phase 42 module docstring and constants. This pattern survived the
Phase 51 edit but is brittle: any future linter strictness change or
auto-formatter pass will move them and break the `# noqa` suppression.
Move all imports to the top of the file in a follow-up cleanup; the
section-header comment can stay where it is to mark the Phase 43
expansion boundary.
**Fix:** Hoist the imports to the file header and drop the `# noqa: E402`
markers. No behavior change.

### IN-02: `_query_package_uris` SQL fragment in `scan.py` is duplicated knowledge of `nodes.uri`

**File:** `agents/graph-wiki-agent/src/graph_wiki_agent/commands/scan.py:115-125`
**Issue:** This helper inlines `SELECT name, uri FROM nodes WHERE kind='package'
AND uri IS NOT NULL` and carries a comment block explaining the column-vs-attrs
distinction recorded in `~/.claude/projects/.../graph-io-uri-column-not-attrs.md`.
That same knowledge is now also used by `entity_writer.scanner_frontmatter_for_node`
via `node.attrs.get("uri", "")` (line 449), which falls back on `attrs` because
the `NodeRecord` projection re-inflates `uri` into `attrs`. Two readers
have to keep this invariant in sync. Not a Phase 51 regression — flagging
because the kind-retraction touched both call sites without consolidating.
**Fix:** Consider a single `graph_io.queries.uri_for(node)` helper that
encapsulates the "URI lives in the column OR in attrs after projection"
rule and use it from both modules. Out of scope for Phase 51 itself.

### IN-03: `_check_wikilink_resolves` returns first unresolved link only

**File:** `packages/eval-harness/src/eval_harness/divergence/librarian.py:67-69`
**Issue:** When multiple wikilinks fail to resolve, the verdict excerpt
contains only the first one (`f"Unresolved: {unresolved[0]}"`). The
divergence baseline therefore loses visibility into how many references
are actually broken for a single answer — useful signal when triaging a
LIB-001 regression. Pre-existing behavior; pointing it out because the
baseline file (`divergence-librarian.json`) shows 3 accepted failures
each carrying one excerpt, all from different fixtures, so no single
fixture currently exposes the lossy reporting. A future drift could.
**Fix:** Include count and (truncated) joined list:
```python
return Verdict(
    passed=False,
    excerpt=f"Unresolved ({len(unresolved)}): {', '.join(unresolved[:3])}",
)
```

### IN-04: `lint/dependency.py` docstring references a "graph-aware extension" that may not exist

**File:** `packages/wiki-io/src/wiki_io/lint/dependency.py:5-7`
**Issue:** "Filesystem-only at this point; graph-aware variants (e.g. checking
that a member is actually imported anywhere in the codebase) are deferred to
the follow-on plan once the graph-aware extension ships." The same docstring
then explains (Phase 51 paragraph) that the family-grouping kind was retired
"alongside the graph-io kind retraction" — but the original "graph-aware
extension" referenced is from an earlier, pre-Phase-51 plan whose scope
included `package_family`. As written it reads as if both deferrals are
still active. Mostly stylistic, but a future maintainer may chase a plan
that no longer exists.
**Fix:** Clarify in the docstring which plan the "follow-on" refers to,
or drop the sentence and link to `REQUIREMENTS.md` "Future Requirements"
directly.

---

_Reviewed: 2026-05-27_
_Reviewer: Claude (gsd-code-reviewer)_
_Depth: standard_
