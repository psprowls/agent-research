---
phase: 16-carry-forward-debt-cleanup
reviewed: 2026-05-19T00:00:00Z
depth: standard
files_reviewed: 25
files_reviewed_list:
  - packages/subagent-runtime/src/subagent_runtime/trace_io.py
  - packages/subagent-runtime/src/subagent_runtime/pool.py
  - packages/subagent-runtime/tests/test_trace_io.py
  - agents/code-wiki-agent/src/code_wiki_agent/commands/ingest.py
  - agents/code-wiki-agent/src/code_wiki_agent/commands/query.py
  - agents/code-wiki-agent/tests/test_ingest_trace_unit.py
  - agents/code-wiki-agent/tests/test_query_trace_unit.py
  - agents/code-wiki-agent/tests/integration/test_trace_coverage.py
  - packages/prompt-sources/agents/code_reader.md
  - packages/prompt-sources/agents/synthesizer.md
  - packages/eval-harness/src/eval_harness/divergence/__init__.py
  - packages/eval-harness/src/eval_harness/divergence/code_reader.py
  - packages/eval-harness/src/eval_harness/divergence/synthesizer.py
  - packages/eval-harness/src/eval_harness/divergence/metric.py
  - packages/eval-harness/src/eval_harness/divergence/rubrics/code_reader.md
  - packages/eval-harness/src/eval_harness/divergence/rubrics/synthesizer.md
  - packages/eval-harness/src/eval_harness/two_gate.py
  - packages/eval-harness/tests/test_two_gate_scorer.py
  - packages/eval-harness/tests/test_scanner_regression.py
  - packages/eval-harness/tests/test_models_toml_sweep_candidates.py
  - eval/cases/code_reader_cases.json
  - docs/cancellation.md
  - docs/testing.md
  - tests/test_integration_gate.py
  - packages/model-adapter/tests/test_loader.py
findings:
  critical: 0
  warning: 6
  info: 9
  total: 15
status: issues_found
---

# Phase 16: Code Review Report

**Reviewed:** 2026-05-19
**Depth:** standard
**Files Reviewed:** 25
**Status:** issues_found

## Summary

Phase 16 carry-forward debt cleanup. The work is structurally sound: the trace
writer (`write_trace_record`) was correctly extracted from `pool.py` into
`trace_io.py` and is now reused at the ingest and query call sites; the
synthesizer + code_reader divergence checks join `ROLES_WITH_DIVERGENCE`; and
the integration-gate meta-test enforces the canonical skipif pattern across
the monorepo. No security regressions found — the bounded `read_file`
allow-list keeps its `resolve()`-before-containment-check, and `_route_target_path`
still rejects traversal escapes.

That said, the review surfaces six WARNING-tier issues and nine INFO-tier
issues. The warnings cluster in three places: (1) the SYN-002 slug-only
wikilink check is narrower than the prompt rule it enforces, letting
lowercased slug-only wikilinks slip past; (2) several stale or misleading
comments/docstrings now point at line ranges that no longer exist after the
D-04 extraction; (3) the integration trace-coverage assertion is fragile
against the empty-vault-thin code-fallback path. None of these block ship,
but they erode the testing/observability story the phase set out to harden.

No BLOCKER-tier findings.

## Warnings

### WR-01: SYN-002 slug-only check misses lowercase / hyphenated slugs the prompt forbids

**File:** `packages/eval-harness/src/eval_harness/divergence/synthesizer.py:19,50-60`

**Issue:** The prompt rule the check enforces (synthesizer.md rule 2) reads
"NEVER collapse to a slug-only form such as `[[SubagentPool]]` or `[[Bedrock]]`."
The PascalCase examples are illustrative — the rule itself is "no slug-only,
full path required." The regex implements only the PascalCase case:

```python
_SLUG_ONLY_RE = re.compile(r"^[A-Z][A-Za-z0-9]+$")
```

This catches `[[SubagentPool]]` and `[[Bedrock]]` but silently passes
`[[bedrock]]`, `[[subagent-pool]]`, `[[pool]]`, `[[foo_bar]]`, all of which
are equally slug-only and equally fail to resolve against the vault. A
synthesizer that emits lowercase slugs (a common LLM failure mode for models
trained on conventional markdown) clears SYN-002 with no signal.

**Fix:** Define slug-only as "any wikilink target with no `/`". That matches
the prompt rule and the vault layout (every real page lives under a path
prefix like `wiki/`, `packages/`, `concepts/`, `adrs/`).

```python
def _check_no_slug_only_wikilinks(output, vault):
    for link in _WIKILINK_RE.findall(output.answer or ""):
        slug = link.split("|")[0].strip()
        # Slug-only := no path separator. Full-path wikilinks always contain '/'.
        if "/" not in slug:
            return Verdict(passed=False, excerpt=f"Slug-only wikilink: [[{slug}]]")
    return Verdict(passed=True, excerpt="")
```

### WR-02: CR-003 `.code-wiki/` regex misses inline path references

**File:** `packages/eval-harness/src/eval_harness/divergence/code_reader.py:31,71-82`

**Issue:** The negative lookbehind `(?<![A-Za-z0-9_/-])` excludes `/` from the
preceding-character set. That intentionally blocks matches like
`vault/.code-wiki/bm25`. But that is precisely the form an agent would emit
when it INVENTS a `.code-wiki/` quote — e.g. "I read `wiki/.code-wiki/foo.json`
and it contained …". The check is meant to catch invented `.code-wiki/`
citations (per rule 4: the tool refuses those reads, so any quote is
fabricated); it instead permits any `.code-wiki/` reference that follows a
slash.

Confirmed: `re.compile(r"(?<![A-Za-z0-9_/-])\.code-wiki/").search("vault/.code-wiki/bm25")`
returns `None`.

**Fix:** Allow the lookbehind to exclude only word characters (path
*continuations*), not the path *separator*:

```python
_CODE_WIKI_PREFIX_RE = re.compile(r"(?<![A-Za-z0-9_-])\.code-wiki/")
```

This still avoids false positives on suffixes (`foo.code-wiki/`) but catches
both the bare reference and the slash-prefixed reference.

### WR-03: CR-001 path:line regex requires a `/` in the path — bare-filename citations escape

**File:** `packages/eval-harness/src/eval_harness/divergence/code_reader.py:21-23,39-53`

**Issue:** `_PATH_LINE_RE` requires at least one `/` in the path:

```python
r"`?[A-Za-z0-9_./-]+/[A-Za-z0-9_./-]+\.(?:py|ts|js|tsx|jsx|go|rs|md|toml|yaml|yml|sh):\d+(?:-\d+)?`?"
```

So `pool.py:115` (no directory) fails CR-001 even though it's a perfectly
valid `path:line` annotation. The prompt rule (`code_reader.md` rule 3) says
"`path:line` or `path:line-line`" — no directory requirement. The
synthesizer's `_BACKTICK_CODE_RE` is correctly permissive: `r"`[^`]*?:\d+(?:-\d+)?`"`.
The two checks should agree on what counts as a `path:line` citation.

This isn't a security issue, but it's a false-negative hard rule: an agent
emitting `pool.py:115` (which the synthesizer happily accepts) would be
marked "no path:line annotation and not the bare sentinel" by CR-001, which
is wrong.

**Fix:** Drop the `/` requirement, or align with the synthesizer's
backtick-permissive regex. Suggested:

```python
_PATH_LINE_RE = re.compile(
    r"`?[A-Za-z0-9_./-]*[A-Za-z0-9_-]+\.(?:py|ts|js|tsx|jsx|go|rs|md|toml|yaml|yml|sh):\d+(?:-\d+)?`?"
)
```

### WR-04: Integration trace-coverage test asserts a property the code-fallback empty-result path violates

**File:** `agents/code-wiki-agent/tests/integration/test_trace_coverage.py:88-95`

**Issue:** The assertion is:

```python
if rec.get("kind") == "query_summary":
    assert rec.get("tokens_in") is not None
    assert rec.get("tokens_out") is not None
```

But `query.py:_run_code_fallback` legitimately returns
`(CODE_FALLBACK_DISCLAIMER, None, None)` when both the librarian and the
code_reader fan-outs return nothing useful (lines 503-505 of `query.py`).
The summary record then writes `tokens_in: None, tokens_out: None`, which
is the *correct* behavior — no synth call was made. If a real query against
the fixture vault hits the empty/empty case (perfectly possible for "What
concepts are documented in the wiki?" on a thin vault), this integration
test will fail spuriously and operators will assume the trace pipeline is
broken.

**Fix:** Exempt the disclaimer path explicitly, mirroring the existing
error-record exemption:

```python
if rec.get("kind") == "query_summary":
    # tokens are None on the empty/empty code-fallback path (no synth call).
    if rec.get("tokens_in") is None and rec.get("tokens_out") is None:
        records_seen += 1
        continue
    assert rec.get("tokens_in") is not None
    assert rec.get("tokens_out") is not None
```

Or equivalently, only assert tokens are non-None when `code_fallback is False`.

### WR-05: `inspect.signature(task)` called per-item — fragile against `MagicMock` / `functools.partial`

**File:** `packages/subagent-runtime/src/subagent_runtime/pool.py:133-137`

**Issue:** Inside `_run_one`, the task signature is re-inspected on every
fan-out item:

```python
sig = inspect.signature(task)
if len(sig.parameters) >= 2:
    result = await task(item, _config)
```

Two problems:
1. **Per-item cost**: `inspect.signature` is non-trivial and identical
   across every item in the batch. For a fan-out of N pages this is N
   redundant calls. Hoist once before `asyncio.gather`.
2. **Brittle for non-introspectable callables**: `inspect.signature` raises
   `ValueError: no signature found` for some `MagicMock` / C-extension /
   `functools.partial` shapes. Today's unit tests pass plain `async def`
   closures so it works, but the API surface is wider than the tests
   exercise — `task` is typed `Callable[..., Awaitable[Any]]`.

**Fix:** Compute the signature once, with a defensive fallback:

```python
try:
    _accepts_config = len(inspect.signature(task).parameters) >= 2
except (TypeError, ValueError):
    _accepts_config = False  # opaque callable — fall back to single-arg form
# ... in _run_one:
if _accepts_config:
    result = await task(item, _config)
else:
    result = await task(item)
```

### WR-06: `_route_target_path` containment check uses hardcoded `/` separator

**File:** `agents/code-wiki-agent/src/code_wiki_agent/commands/ingest.py:101-106`

**Issue:**

```python
if not str(resolved).startswith(str(wiki_resolved) + "/"):
    raise ValueError(...)
```

The `+ "/"` is the right idea (prevents `/tmp/wiki-other/foo` from
matching `/tmp/wiki` as a prefix) but it hardcodes the POSIX separator. On
Windows this would mismatch every legitimate write. The project is
macOS/Linux-only per CLAUDE.md, so this is not a runtime bug today, but
`Path.is_relative_to(...)` (added in Python 3.9, already used elsewhere in
`query.py:356`) is portable and avoids the separator footgun entirely.

**Fix:** Use `Path.is_relative_to`:

```python
resolved = target.resolve()
wiki_resolved = wiki.resolve()
if not resolved.is_relative_to(wiki_resolved):
    raise ValueError(f"target path escapes wiki root: {resolved}")
```

This also matches the pattern already adopted by `_read_file_bounded` in
`query.py`, so the codebase converges on a single idiom.

## Info

### IN-01: Stale line-range reference in `_extract_usage_tokens` docstring

**File:** `agents/code-wiki-agent/src/code_wiki_agent/commands/query.py:283-286`

**Issue:** The docstring says "Block lifted verbatim from
subagent_runtime.pool._write_trace:203-209". After the D-04 extraction,
`pool._write_trace` is a thin delegate at lines 184-199, and the actual
block lives in `trace_io.write_trace_record` (lines 56-66). The line numbers
are doubly stale (wrong file, wrong range).

**Fix:** Point at the canonical home:

```python
"""... lifted verbatim from subagent_runtime.trace_io.write_trace_record:56-66
so trace records on the synthesizer call sites carry the same usage data as
pool-driven trace records."""
```

### IN-02: `subagent_runtime/trace_io.py` has unused `from typing import Any`-only nicety

**File:** `packages/subagent-runtime/src/subagent_runtime/trace_io.py:24`

**Issue:** `Any` is imported and used. No issue. (Self-correcting on a
re-scan — leaving the note so the section maps to the import-hygiene
sweep in IN-03.)

**Fix:** No action.

### IN-03: `from typing import Union` is unused in `divergence/metric.py`

**File:** `packages/eval-harness/src/eval_harness/divergence/metric.py:31`

**Issue:** `Union` is imported but never referenced. The module uses PEP-604
syntax (`A | B`) elsewhere. Dead import.

**Fix:** Remove the line.

### IN-04: `pytest`, `monkeypatch`, `caplog` imported/declared but not asserted on

**File:** `packages/subagent-runtime/tests/test_trace_io.py:15,84,99-102`

**Issue:** `test_write_trace_record_swallows_oserror` accepts `monkeypatch`
and `caplog` fixtures but never uses them. The test asserts the file does
not exist (which is correct) but does not assert that the WARNING was
logged via caplog. The docstring promises "OSError on file open is logged
WARNING and swallowed" — the "logged WARNING" half is unverified.

`import pytest` at line 15 is also unused (no `pytest.raises`, no
`pytest.mark`).

**Fix:** Either drop the unused fixtures + import, or actually exercise
them:

```python
def test_write_trace_record_swallows_oserror(tmp_path, caplog):
    bad_path = tmp_path / "does" / "not" / "exist" / "trace.jsonl"
    with caplog.at_level("WARNING"):
        write_trace_record(bad_path, ...)
    assert not bad_path.exists()
    assert any("Trace write failed" in r.message for r in caplog.records)
```

### IN-05: `import pytest` unused in `test_ingest_trace_unit.py`

**File:** `agents/code-wiki-agent/tests/test_ingest_trace_unit.py:15`

**Issue:** Only `@pytest.mark.asyncio` references `pytest`. That's fine —
the decorator does use it. Re-check: `pytest.raises(BotoCoreError)` is also
inside the second test. Both uses are legitimate. No action needed.

**Fix:** No action.

### IN-06: Two synthesizer trace files share the same filename pattern across both branches

**File:** `agents/code-wiki-agent/src/code_wiki_agent/commands/query.py:532,968`

**Issue:** Both the code-fallback synth call (line 532) and the regular-
path synth call (line 968) write to `synth_{query_id}.jsonl`. Within a
single `run_query` call only one branch fires, so there's no collision.
But a downstream reader (Phase 9 trace renderer) cannot tell from the
filename alone which branch produced the record. The `kind: query_summary`
record's `code_fallback` flag tells the reader; the per-call synth record
has no such flag.

Not a bug — but if a future change ever invokes both branches in one query
(e.g. retry-after-fallback), the second write would clobber the first
because the file is opened in append mode and there's no ordering guarantee.

**Fix:** Optional — add the role-source as a filename qualifier:

```python
synth_trace_file = synth_trace_dir / f"synth_librarian_{query_id}.jsonl"
# and in _run_code_fallback:
trace_file = trace_dir / f"synth_codefallback_{query_id}.jsonl"
```

### IN-07: `code_reader_cases.json` documented as "3 vault-thin cases" in module docstring; now 6

**File:** `packages/eval-harness/tests/test_models_toml_sweep_candidates.py:10`

**Issue:** Module docstring at line 10 reads
`"- code_reader_cases.json has 3 vault-thin fixture cases (D-09)"`
but the test at line 152-182 asserts `5 <= len(cases) <= 6` and the file
itself has 6 cases. The docstring contradicts the runtime assertion.

**Fix:** Update the docstring header to match the asserted range:

```python
"""...
- code_reader_cases.json has 5–6 vault-thin fixture cases (Phase 16 D-07
  expansion; first 3 preserved as baseline)
"""
```

### IN-08: `docs/cancellation.md` trace example missing `schema_version` field

**File:** `docs/cancellation.md:103-115,121-131`

**Issue:** The two example JSON blocks (per-item cancelled record and batch
terminal summary) omit the `schema_version: 1` field that every real trace
record carries (added in Phase 9 OBS-04 D-01/D-02; enforced in
`trace_io.py:69` and `pool.py:219`). A reader following the doc to build a
trace consumer will produce a schema-incomplete writer.

**Fix:** Add `"schema_version": 1,` to both example blocks at the top of
each object.

### IN-09: `_compute_unresolved_wikilinks` duplicates the G1 resolution logic in `apply_guardrails`

**File:** `agents/code-wiki-agent/src/code_wiki_agent/commands/query.py:551-570,663-670`

**Issue:** `_compute_unresolved_wikilinks` (lines 551-570) and the inline
G1 block in `apply_guardrails` (lines 663-670) compute the same thing with
the same algorithm. The duplication is acknowledged in the docstring
("Resolution rules mirror apply_guardrails' G1 logic") but not addressed.
If the resolution algorithm changes (e.g., handles `#anchor` fragments or
case-insensitive basenames), the change must be applied in two places —
classic drift bait.

**Fix:** Have `apply_guardrails` call `_compute_unresolved_wikilinks` and
delete the inline block. The two paths already share the
`_extract_wikilinks` helper.

---

_Reviewed: 2026-05-19_
_Reviewer: Claude (gsd-code-reviewer)_
_Depth: standard_
