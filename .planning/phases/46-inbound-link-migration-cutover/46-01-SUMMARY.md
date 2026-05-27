---
phase: 46-inbound-link-migration-cutover
plan: 01
type: execute
status: complete
completed_at: 2026-05-27
requirements:
  - MIGRATION-01
  - MIGRATION-04
key-files:
  created:
    - packages/wiki-io/src/wiki_io/link_rewriter.py
    - packages/wiki-io/tests/test_lint_common_indented_code.py
    - packages/wiki-io/tests/test_link_rewriter.py
  modified:
    - packages/wiki-io/src/wiki_io/lint/common.py
commits:
  - 2c31928 feat(46-01): add indented_code_spans helper for CommonMark indented blocks
  - a9cff2b feat(46-01): add wiki_io.link_rewriter.rewrite_text pure function
---

# Plan 46-01 Summary: rewrite_text pure function + indented_code_spans helper

## What Shipped

1. **`wiki_io.lint.common.indented_code_spans(text)`** — new public helper
   returning `(start_byte, end_byte)` half-open spans for CommonMark §4.4
   indented code blocks (4-space or tab indent, preceded by a blank line or
   document start). Pure function; the helper does NOT inspect fences — the
   caller takes the union of fenced/inline/indented spans.

2. **`packages/wiki-io/src/wiki_io/link_rewriter.py`** — new module with the
   public pure-function `rewrite_text(text, table) -> (new_text, count)`.
   Tokenizes documents into prose vs code regions via three regexes
   (`FENCED_CODE_RE`, `INLINE_CODE_RE`, `indented_code_spans`), merges spans,
   then walks `WIKILINK_RE` matches and rewrites only those whose start
   position falls outside every code span. Alias and anchor suffixes are
   preserved verbatim via single-shot `original.replace(old_target, new_slug, 1)`.
   Idempotent on a second invocation (rewritten slugs no longer match table keys).

3. **Test coverage** — 26 new tests (8 for `indented_code_spans`, 18 for
   `rewrite_text` of which 17 pass and 1 is xfail per CONTEXT D-02
   nested-fence limitation).

## Tests Green

```
packages/wiki-io/tests/test_lint_common_indented_code.py: 8 passed
packages/wiki-io/tests/test_link_rewriter.py:             17 passed, 1 xfailed
Full wiki-io suite:                                       320 passed, 2 skipped, 1 xfailed
```

No regression in pre-existing lint or wiki-io tests.

## Decisions Honored

- **D-01:** Regex with code-region masking, NO markdown-it-py. Module imports
  only stdlib + `wiki_io.lint.common`; `packages/wiki-io/pyproject.toml`
  unchanged (verified via `git diff`).
- **D-02:** Fixture suite covers fenced/inline/indented code skipping,
  alias-only, anchor-only, alias+anchor, escaped table-cell alias
  (`\|alias`), lazy-continuation paragraph, unresolvable (None) target,
  unknown (missing key) target, idempotency, empty/trivial inputs, and the
  nested-fence v1.8 known limitation (xfail).
- **D-14:** Lane-scope enforcement deferred to Plan 02's `rewrite_vault`
  (this plan only ships the pure-function core).

## Deviations

None. The reference implementation in the plan was adopted verbatim with
minor docstring polish.

## Next Wave Enables

Plan 02 (`build_rewrite_table` + `rewrite_vault`) can now import `rewrite_text`
from `wiki_io.link_rewriter` and apply it per-file across the 5 curated lanes.

## Self-Check: PASSED

- [x] All Task 1 acceptance criteria pass (grep for `def indented_code_spans`,
      one-liner import succeeds and prints `[(0, 9)]`, both test commands exit 0).
- [x] All Task 2 acceptance criteria pass (one-liner import returns
      `('[[entities/x]]', 1)`, both grep checks find expected definitions,
      `^import|^from` count is 2 → stdlib + wiki_io.lint.common only).
- [x] Plan-level verification all green (new tests + regression + import checks +
      no pyproject.toml changes).
- [x] Both commits exist (`git log --oneline --grep="46-01"`).
