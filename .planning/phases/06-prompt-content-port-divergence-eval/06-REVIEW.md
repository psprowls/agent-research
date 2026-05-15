---
phase: 06-prompt-content-port-divergence-eval
reviewed: 2026-05-15T20:41:00Z
depth: standard
files_reviewed: 34
files_reviewed_list:
  - agents/code-wiki-agent/src/code_wiki_agent/commands/ingest.py
  - agents/code-wiki-agent/src/code_wiki_agent/commands/lint.py
  - agents/code-wiki-agent/src/code_wiki_agent/commands/query.py
  - agents/code-wiki-agent/src/code_wiki_agent/commands/scan.py
  - agents/code-wiki-agent/src/code_wiki_agent/prompts/__init__.py
  - agents/code-wiki-agent/src/code_wiki_agent/prompts/_fragments/__init__.py
  - agents/code-wiki-agent/src/code_wiki_agent/prompts/_fragments/citation_rules.py
  - agents/code-wiki-agent/src/code_wiki_agent/prompts/_fragments/frontmatter_rules.py
  - agents/code-wiki-agent/src/code_wiki_agent/prompts/_fragments/iron_rules.py
  - agents/code-wiki-agent/src/code_wiki_agent/prompts/_fragments/page_categories.py
  - agents/code-wiki-agent/src/code_wiki_agent/prompts/code_reader.py
  - agents/code-wiki-agent/src/code_wiki_agent/prompts/ingestor.py
  - agents/code-wiki-agent/src/code_wiki_agent/prompts/librarian.py
  - agents/code-wiki-agent/src/code_wiki_agent/prompts/linter.py
  - agents/code-wiki-agent/src/code_wiki_agent/prompts/scanner.py
  - agents/code-wiki-agent/src/code_wiki_agent/prompts/synthesizer.py
  - agents/code-wiki-agent/tests/prompts/test_prompt_snapshots.py
  - agents/code-wiki-agent/tests/prompts/test_provenance.py
  - cores/eval-harness/src/eval_harness/divergence/__init__.py
  - cores/eval-harness/src/eval_harness/divergence/check.py
  - cores/eval-harness/src/eval_harness/divergence/ingestor.py
  - cores/eval-harness/src/eval_harness/divergence/librarian.py
  - cores/eval-harness/src/eval_harness/divergence/linter.py
  - cores/eval-harness/src/eval_harness/divergence/metric.py
  - cores/eval-harness/src/eval_harness/divergence/scanner.py
  - cores/eval-harness/src/eval_harness/divergence/rubrics/ingestor.md
  - cores/eval-harness/src/eval_harness/divergence/rubrics/librarian.md
  - cores/eval-harness/src/eval_harness/divergence/rubrics/linter.md
  - cores/eval-harness/src/eval_harness/divergence/rubrics/scanner.md
  - cores/eval-harness/tests/conftest.py
  - cores/eval-harness/tests/test_divergence_baseline.py
  - cores/eval-harness/tests/test_divergence_checks.py
  - cores/eval-harness/tests/test_divergence_metric.py
  - cores/eval-harness/tests/test_divergence.py
findings:
  critical: 2
  warning: 6
  info: 4
  total: 12
status: issues_found
---

# Phase 06: Code Review Report

**Reviewed:** 2026-05-15T20:41:00Z
**Depth:** standard
**Files Reviewed:** 34
**Status:** issues_found

## Summary

Phase 06 ported lattice-wiki prompt content into composed `_fragments/` modules and built a programmatic + GEval divergence eval harness. The prompt composition approach (fragments assembled at import time, no runtime templating) is sound. The divergence check callables are well-structured, deterministic, and correctly avoid eval/exec on LLM output. The security-sensitive path in `_route_target_path` (slug sanitization + containment check) is correctly implemented.

Two critical defects were found: a YAML list-item parser in `_parse_ingestor_response` that silently corrupts list values starting with a hyphen, and a ZeroDivisionError in `DivergenceMetric.run_judge` if `JUDGE_PANEL_CONFIG` is ever empty. Six warnings cover a cwd-relative path resolution bug that silently drops file snippets from scanner stubs, a deprecated `datetime.utcnow()` call, a LIB-002 regex that misses line-range citations, a private function import across modules, a brittle `sys.path` manipulation in integration tests, and missing guard against EVAL_GATE duplication. Four info-level findings cover dead code and minor documentation issues.

---

## Critical Issues

### CR-01: YAML list parser uses `lstrip("- ")` — silently corrupts dash-prefixed tag values

**File:** `agents/code-wiki-agent/src/code_wiki_agent/commands/ingest.py:137`

**Issue:** `lstrip("- ")` strips all leading characters in the character-set `{'-', ' '}`, not the two-character sequence `"- "`. A list item value starting with a hyphen (e.g. `- -v2`, `- --flag`, `- -dashed-name`) has its leading dash(es) silently eaten. For example the tag `- -dashed-value` is parsed as `dashed-value` instead of `-dashed-value`. This is a silent data corruption in the frontmatter parser that the callers (line 262: `fm, _body = _parse_ingestor_response(llm_output)`) cannot detect because no error is raised. Fields like `tags` returned by the ingestor LLM may contain versioned identifiers (`-v2`), CLI flags, or hyphen-prefixed names that get silently truncated.

**Fix:**
```python
# Replace lstrip("- ") with a correct prefix removal:
cur_list.append(line.lstrip().removeprefix("- ").strip())
# `removeprefix("- ")` removes exactly the two-character prefix "- " once,
# preserving any remaining content including leading dashes.
```

---

### CR-02: `DivergenceMetric.run_judge` — ZeroDivisionError when `JUDGE_PANEL_CONFIG` is empty

**File:** `cores/eval-harness/src/eval_harness/divergence/metric.py:172`

**Issue:** `mean_score = sum(scores) / len(scores)` unconditionally divides by `len(scores)`. If `JUDGE_PANEL_CONFIG` is empty (e.g. during a test that monkeypatches it, or if `judge.py` is modified to empty the list), `scores` is `[]`, `len(scores)` is `0`, and a `ZeroDivisionError` is raised inside the `for fixture_id, output, query in outputs:` loop, crashing the judge pass for all fixtures. The same pattern appears in `judge.py:panel_score` at line 118. The `judge.py:panel_score` function additionally hardcodes `scores[0]` and `scores[1]` at lines 123-124, which raises `IndexError` if `JUDGE_PANEL_CONFIG` is ever changed to a single-entry panel.

**Fix:**
```python
# In metric.py run_judge, guard the division:
if not scores:
    # No judges in panel — skip this fixture
    continue
mean_score = sum(scores) / len(scores)

# In judge.py panel_score, guard the hardcoded indices:
if len(scores) < 2:
    raise RuntimeError(
        f"panel_score requires at least 2 judges, got {len(scores)}"
    )
mean_score = sum(scores) / len(scores)
return {
    "judge_a": scores[0],
    "judge_b": scores[1],
    ...
}
```

---

## Warnings

### WR-01: `build_stub_prompt` resolves relative package path against `cwd`, not repo root

**File:** `agents/code-wiki-agent/src/code_wiki_agent/commands/scan.py:149`

**Issue:** `pkg['path']` is a repo-relative string (e.g. `"cores/eval-harness"`) returned by `discover_workspaces`. `build_stub_prompt` does `Path(pkg_path_str).resolve()` at line 149, which resolves relative to the current working directory at runtime, not the repo root. If the process's cwd differs from the repo root (e.g. when invoked from a subshell, CI, or an MCP host), `pkg_abs` points to a nonexistent path and `pick_representative` silently returns zero files. The failure is caught by the bare `except Exception: pass` on line 162, so stubs are generated without representative snippets and neither the caller nor the user is informed.

**Fix:** Pass the repo root into `build_stub_prompt` and use it to resolve the path:
```python
def build_stub_prompt(pkg: dict, no_file_map: bool = False, repo_root: Path | None = None) -> str:
    ...
    pkg_path_str = pkg.get("path")
    if pkg_path_str and repo_root is not None:
        pkg_abs = (repo_root / pkg_path_str).resolve()
    elif pkg_path_str:
        pkg_abs = Path(pkg_path_str).resolve()
    ...
```
Then in `run_scan`, pass `repo_root=repo` when calling `build_stub_prompt`.

---

### WR-02: `datetime.utcnow()` deprecated in Python 3.12+

**File:** `agents/code-wiki-agent/src/code_wiki_agent/commands/query.py:789,942`

**Issue:** `datetime.datetime.utcnow()` is deprecated as of Python 3.12 and scheduled for removal in a future version. The project requires Python ≥3.11 and is intended for long-term use, so this will become a runtime `DeprecationWarning` on Python 3.12 and will eventually break. The result also lacks timezone info, making it ambiguous in logs.

**Fix:**
```python
# Replace both occurrences:
started_at = datetime.datetime.now(tz=datetime.timezone.utc).isoformat()
ended_at = datetime.datetime.now(tz=datetime.timezone.utc).isoformat()
# No need to append "Z" manually — isoformat() with tz=utc produces "+00:00"
# or use .replace("+00:00", "Z") if Z suffix is required by downstream consumers.
```

---

### WR-03: `LIB-002` regex misses backtick code citations with line ranges

**File:** `cores/eval-harness/src/eval_harness/divergence/librarian.py:30`

**Issue:** `_BACKTICK_CODE_RE = re.compile(r"`[^`]+:[0-9]+`")` requires the citation to end with `:digits` immediately before the closing backtick. It does not match line-range citations of the form `` `src/foo.py:42-55` `` or `` `pool.py:115-130` `` (both formats are explicitly endorsed by the synthesizer system prompt). A librarian answer citing only line-range code paths produces no `has_code_path` match, causing LIB-002 to incorrectly report "No citation in answer" (a false failure) and inflate the divergence failure rate for this hard-severity rule.

**Fix:**
```python
# Extend the regex to optionally match a range suffix:
_BACKTICK_CODE_RE = re.compile(r"`[^`]+:[0-9]+(?:-[0-9]+)?`")
```

---

### WR-04: `librarian.py` imports private function `_resolve_citation` across module boundary

**File:** `cores/eval-harness/src/eval_harness/divergence/librarian.py:15`

**Issue:** `from eval_harness.structural import _resolve_citation` imports a function with a leading underscore (private-by-convention) from a different module. If `structural.py` renames, moves, or removes `_resolve_citation`, `librarian.py` raises `ImportError` at collection time, silently disabling all librarian divergence checks. Private function imports across module boundaries violate the encapsulation boundary and create invisible coupling.

**Fix:** Either make `_resolve_citation` public by removing the leading underscore (rename to `resolve_citation` in `structural.py`), or add `resolve_citation = _resolve_citation` as a public alias in `structural.py`'s `__all__`, then update the import in `librarian.py`.

---

### WR-05: `test_divergence.py` — `sys.path.insert` + direct `conftest` import is brittle

**File:** `cores/eval-harness/tests/test_divergence.py:32,81`

**Issue:** Lines 32 and 81:
```python
sys.path.insert(0, str(Path(__file__).parent))
from conftest import _produce_outputs
```
This inserts the `tests/` directory onto `sys.path` so that `conftest` can be imported as a plain module. This is fragile: (1) pytest already processes `conftest.py` and may load a different conftest from a parent directory if there is a naming collision; (2) `_produce_outputs` is a private function (underscore prefix) that is not part of `conftest`'s public contract; (3) if pytest changes how it discovers conftest files, the import may break silently.

**Fix:** Move `_produce_outputs` and the per-role producers into a separate helper module (e.g. `tests/eval_helpers.py`) with a public API, and import from there in both `conftest.py` and `test_divergence.py`. Remove the `sys.path.insert`.

---

### WR-06: `EVAL_GATE` redefined in `test_divergence.py` instead of imported from `conftest`

**File:** `cores/eval-harness/tests/test_divergence.py:43-49`

**Issue:** `conftest.py` defines `EVAL_GATE` at line 29. `test_divergence.py` defines an identical copy at lines 46-49 with the comment "matches the EVAL_GATE constant in conftest.py." This duplication means that changing the controlling environment variable name (e.g. `CODE_WIKI_RUN_EVAL` → `EVAL_RUN_MODE`) or the skip reason requires editing two files. If one is updated and the other is not, the two gates diverge silently.

**Fix:**
```python
# In test_divergence.py, replace the redefinition with:
from conftest import EVAL_GATE  # noqa: E402
# (after the sys.path.insert — or eliminate that once WR-05 is fixed)
```

---

## Info

### IN-01: Dead code — `if not outputs:` in `_produce_linter_outputs` is unreachable

**File:** `cores/eval-harness/tests/conftest.py:253-258`

**Issue:** The `outputs` list is populated by the `for group in ("page_quality", "adr_chain", "stale_claims"):` loop immediately above. The loop always executes 3 iterations and always appends an entry, so `if not outputs:` at line 253 is always `False`. The `pytest.skip` on line 254 can never be reached. This dead code suggests the skip guard was copy-pasted from `_produce_scanner_outputs` and never adapted.

**Fix:** Remove the unreachable `if not outputs: pytest.skip(...)` block. If early termination on an empty vault is desired, add a guard before the `for group in (...)` loop instead.

---

### IN-02: `check_regression` — first run without baseline gates at zero hard failures (undocumented)

**File:** `cores/eval-harness/src/eval_harness/divergence/metric.py:281`

**Issue:** `load_baseline` returns `{}` when no baseline file exists. Inside `check_regression`, `baseline_checks = baseline.get("checks", {})` is `{}`, so `baseline_failures` defaults to `0` for every rule. Any hard-severity rule with `current_failures > 0` immediately raises `AssertionError`. This means the very first eval run (before any baseline is committed) will fail unless all hard rules have zero failures — or the user passes `--accept-divergence-baseline`. This behavior is not documented in the docstring or in the eval test file, making first-run setup confusing.

**Fix:** Add a note to `check_regression`'s docstring:
```
When `baseline` is empty (first run), any hard-severity failure triggers
AssertionError. Run with --accept-divergence-baseline on first run to
record the initial baseline.
```

---

### IN-03: `run_judge` always uses `reasons[0]` as failure excerpt; ignores `reasons[1]`

**File:** `cores/eval-harness/src/eval_harness/divergence/metric.py:179`

**Issue:** When a fixture fails the judge pass, `accepted_failures` stores `(reasons[0] or "")[:200]`. If the first judge (Sonnet) returns an empty `reason` string but the second judge (Nova Pro) returns a detailed reason explaining the failure, the excerpt stored in the baseline is empty string `""`. Empty excerpts defeat the "concrete examples in the report" requirement from EVAL-12.

**Fix:**
```python
# Pick the first non-empty reason for the excerpt:
excerpt_reason = next((r for r in reasons if r), "")
results[judge_id]["accepted_failures"].append(
    {
        "fixture": fixture_id,
        "excerpt": excerpt_reason[:200],
    }
)
```

---

### IN-04: `_parse_ingestor_response` — YAML block handles `cur_list` flushing only on key boundary; final list may be lost if trailing blank lines follow last item

**File:** `agents/code-wiki-agent/src/code_wiki_agent/commands/ingest.py:130-157`

**Issue:** The YAML list parser flushes `cur_list` into `fm[cur_key]` only when it encounters a non-list-item line (line 139-141: `if cur_list is not None: fm[cur_key] = cur_list`). The final `if cur_list is not None: fm[cur_key] = cur_list` at line 154 correctly handles the end-of-block case. However, the `continue` on line 136 (when a list item is found) skips the flush path entirely — this is correct design. The real edge case is: if the YAML block ends with a blank line after the last list item, the blank line triggers `continue` via the `if not line or line.startswith("#"): continue` check at line 134, preventing the flush. But the final guard at line 154 catches it regardless.

On further inspection, the final guard does work correctly. This is an info-level note only: the blank-line branch re-triggers `continue` which skips the flush, but the outer `if cur_list is not None` after the loop handles it. The code is correct but the control flow is subtle and worth a comment.

**Fix (documentation):** Add a comment above the end-of-loop guard:
```python
# Flush any open list after the last line is processed
# (blank lines hit `continue` above and do not flush inline)
if cur_list is not None:
    fm[cur_key] = cur_list
```

---

_Reviewed: 2026-05-15T20:41:00Z_
_Reviewer: Claude (gsd-code-reviewer)_
_Depth: standard_
