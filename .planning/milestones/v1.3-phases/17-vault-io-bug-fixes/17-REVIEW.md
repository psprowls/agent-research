---
phase: 17-wiki-io-bug-fixes
reviewed: 2026-05-19T00:00:00Z
depth: standard
files_reviewed: 10
files_reviewed_list:
  - packages/wiki-io/pyproject.toml
  - packages/wiki-io/src/wiki_io/detect_containers.py
  - packages/wiki-io/src/wiki_io/init_vault.py
  - packages/wiki-io/src/wiki_io/scan_monorepo.py
  - packages/wiki-io/src/wiki_io/update_tokens.py
  - packages/wiki-io/tests/integration/__init__.py
  - packages/wiki-io/tests/integration/test_count_tokens_live.py
  - packages/wiki-io/tests/test_detect_containers.py
  - packages/wiki-io/tests/test_scan_companion_fold.py
  - packages/wiki-io/tests/test_update_tokens.py
findings:
  critical: 1
  warning: 6
  info: 4
  total: 11
status: issues_found
---

# Phase 17: Code Review Report

**Reviewed:** 2026-05-19
**Depth:** standard
**Files Reviewed:** 10
**Status:** issues_found

## Summary

Phase 17 lands four bug fixes across `wiki-io`: companion-fold filter in
`_load_existing_pages` (SCAN-01/02), Bedrock CountTokens request-shape correction
(TOK-02), and v1/v2 workspace exclusion in `detect_containers.detect()`
(WSRES-02/03). Tests are well-targeted and the fixes are surgical. However, the
WSRES exclusion fix is **only wired through `detect_containers.py:main()`** — it
is not propagated to `init_vault._resolve_pinned_containers()` or
`scan_monorepo._discover_heuristic()`, so the workspace dir still leaks into
detection in the two callers that actually drive the wiki bootstrap and scan.
That gap appears load-bearing for the WSRES fix story.

Additional findings: a baseline-construction asymmetry in `update_tokens.py`
that produces a counted-text differing from the disk text (idempotency still
holds but the count is computed against text that does not match disk),
duplicate `parts[1].strip().split("\n")` logic, frontmatter blank-line collapse
on rewrite, and minor robustness issues in `tokens:` line filtering.

## Critical Issues

### CR-01: `init_vault._resolve_pinned_containers` does not pass `workspace_path` to detector — v2 layout fix is bypassed

**File:** `packages/wiki-io/src/wiki_io/init_vault.py:86`
**Issue:** Phase 17-03 added a `workspace_path` parameter to
`detect_containers.detect()` so that, in v2 layouts (workspace lives inside the
repo as an immediate child, e.g. `<repo>/graph-wiki/`), the workspace directory
is excluded from top-level container classification. The fix is wired through
`detect_containers.main()` (the CLI entry point) and is covered by
`test_detect_containers.py`. However, `init_vault._resolve_pinned_containers`
calls `_detect_containers(repo)` **without** the `workspace_path` argument:

```python
def _resolve_pinned_containers(repo: Path, non_interactive: bool) -> list[dict]:
    """Run the detector, prompt for ambiguous rows, return the pinned list."""
    records = _detect_containers(repo)  # workspace_path missing
```

In a v2 layout (which the new test fixture explicitly models), the workspace
sibling (e.g. `graph-wiki/`) appears in `repo.iterdir()` and is classified
alongside real containers. It will most often come back as `ambiguous` (no
manifest in children, mixed contents) and either pollute the layout block or
prompt the user with a nonsensical "Pick [package/app/domain/docs/skip]" for a
directory that is the wiki workspace itself. The WSRES test suite covers the
detector in isolation but never exercises the init-time call path that
actually emits `wiki/CLAUDE.md`'s layout block.

The same gap exists in `scan_monorepo.discover_workspaces()` → `_discover_heuristic()`
when no layout block is found (`pinned is None`). `repo.rglob("pyproject.toml")`
will happily descend into `<repo>/graph-wiki/` and treat any pyproject under it
as a workspace package, with no `workspace_path` filter available.

**Fix:** Plumb `workspace_path` through both callers. Minimum patch for init:

```python
def _resolve_pinned_containers(
    repo: Path, non_interactive: bool, workspace_path: Path | None = None
) -> list[dict]:
    records = _detect_containers(repo, workspace_path=workspace_path)
    ...

# in init_wiki, the caller already knows workspace_path:
pinned = _resolve_pinned_containers(
    repo_path, non_interactive, workspace_path=workspace_path
)
```

For `scan_monorepo._discover_heuristic`, add a `workspace_dir` skip in the
`rglob` loops (analogous to the existing `node_modules` / `.venv` filter):

```python
workspace_segments = {workspace_dir.name} if workspace_dir else set()
for pp in repo.rglob("pyproject.toml"):
    if any(part in workspace_segments for part in pp.parts):
        continue
    ...
```

## Warnings

### WR-01: `update_tokens.update_page` baseline includes spurious newlines that do not match the on-disk file

**File:** `packages/wiki-io/src/wiki_io/update_tokens.py:107`
**Issue:** The baseline used for token counting is constructed as

```python
baseline = f"---\n{filtered_fm}\n---\n{parts[2]}\n"
```

while the rewritten on-disk content (line 139) is

```python
updated_raw = f"---\n{updated_fm}\n---{parts[2]}"
```

Given `parts[2]` from `raw.split("---", 2)` starts with `\n` (the newline
following the closing `---`), the baseline produces

```
---\n<fm>\n---\n\n<body>\n\n
```

(double newline after the closing fence, trailing blank line), while the
written file produces

```
---\n<fm>\n---\n<body>\n
```

Idempotency across runs still holds because the baseline construction is
deterministic and strips `tokens:` before counting, but the count reflects text
that **does not match what is on disk**. Per the docstring ("Counts tokens
against a stable baseline — the file content with any existing `tokens` field
stripped"), the count should match the disk text with tokens-line removed.
The extra newlines will marginally inflate the token count and may surprise
users comparing `tokens:` against e.g. a raw `wc`-piped count.
**Fix:** Align the two constructions. The simplest fix is to strip the
spurious tail:

```python
baseline = f"---\n{filtered_fm}\n---{parts[2]}"
```

This matches the rewrite shape exactly. Update the docstring if the previous
shape was intentional.

### WR-02: Rewrite collapses blank lines inside frontmatter

**File:** `packages/wiki-io/src/wiki_io/update_tokens.py:103,121`
**Issue:** Both the baseline filter and the rewrite call `parts[1].strip()`
before `.split("\n")`. `.strip()` removes leading/trailing whitespace from the
frontmatter block but **does not preserve blank lines inside it** beyond what
makes it through the line-by-line walk. Any blank line a user inserted in the
frontmatter to group keys (`title:`, blank, `tags:`) is preserved because empty
strings make it through both `splitlines()` and the filter — but a frontmatter
that *started* or *ended* with a blank line would have that line silently
removed on rewrite. More importantly, the rewrite always emits exactly one
trailing newline before `---` even if the original had none, changing user
intent.

**Fix:** Operate on the unstripped frontmatter block (`parts[1].lstrip("\n")` /
preserve exact boundaries), or document the rewrite is normalizing.

### WR-03: `tokens:` line filter is fragile to YAML variants

**File:** `packages/wiki-io/src/wiki_io/update_tokens.py:104,126`
**Issue:** The filter `line == "tokens:" or line.startswith("tokens: ")`
matches the typical PyYAML emission but not e.g. `tokens:42` (no space) or
`tokens : 42` (space before colon). Both are valid YAML. A vault page hand-
edited to one of these forms would survive the filter, and a duplicate
`tokens: <count>` would be appended below it — leading to YAML with two
`tokens:` keys (last wins on parse, but the file diverges from canonical form
and idempotency breaks on the next run because `post.metadata["tokens"]` will
parse the second value but the rewrite will keep both lines).

**Fix:** Use a regex anchored to the start of the line:

```python
import re
_TOKENS_RE = re.compile(r"^\s*tokens\s*:.*$")
filtered_lines = [line for line in fm_lines if not _TOKENS_RE.match(line)]
```

### WR-04: `boto3>=1.38` may predate `CountTokens` API; failure mode is silent skip-all

**File:** `packages/wiki-io/pyproject.toml:8`, `packages/wiki-io/src/wiki_io/update_tokens.py:40`
**Issue:** The `CountTokens` API on `bedrock-runtime` is a relatively recent
Bedrock addition. The dependency floor `boto3>=1.38` allows installs from
older 1.38.x where `client.count_tokens` does not exist. At runtime this
raises `AttributeError: 'BedrockRuntime' object has no attribute 'count_tokens'`
which is caught by the broad `except Exception` in `update_page` (line 111),
producing a `[warn] skipping <path>: token count failed: ...` for **every**
page in the vault. The script will report `0 updated`, no exit code, and no
indication that the underlying API call is unsupported.

**Fix:** Either pin a known-good boto3 floor that contains CountTokens
(verify with the released boto3 changelog and bump accordingly, e.g.
`boto3>=1.40.0`), or surface the AttributeError separately so the failure is
visible:

```python
except AttributeError as exc:
    raise RuntimeError(
        "boto3 client missing count_tokens; upgrade boto3 (CountTokens "
        "requires a recent SDK version)."
    ) from exc
```

### WR-05: `count_tokens` constructs a new boto3 client per page

**File:** `packages/wiki-io/src/wiki_io/update_tokens.py:39`
**Issue:** Every call to `count_tokens` re-instantiates `boto3.client("bedrock-runtime", ...)`.
On a vault of N pages this performs N client constructions including N rounds
of credential lookup and endpoint resolution. This is not a correctness bug
but it is a meaningful per-run cost (and noted in plan 17-02 as a follow-up).
Calling out so it isn't lost.

**Fix:** Hoist the client to module scope or accept a client argument:

```python
_CLIENT_CACHE: dict[str, Any] = {}

def _get_client(region: str):
    if region not in _CLIENT_CACHE:
        _CLIENT_CACHE[region] = boto3.client("bedrock-runtime", region_name=region)
    return _CLIENT_CACHE[region]
```

### WR-06: `_load_existing_pages` companion-fold walks `rglob` twice per package container

**File:** `packages/wiki-io/src/wiki_io/scan_monorepo.py:633-657,681-709`
**Issue:** Both the `_collect` helper (when `fold_companions=True`) and the
`domains/` block do two full `root.rglob("*.md")` passes — one to build
`companions_by_dir`, one to emit pages. For a large monorepo with deep
`packages/` trees this doubles the directory walk. Not a v1 perf-scope
concern, but a single pass that collects overviews first and then page records
would be equivalent and simpler:

**Fix (sketch):** Stage all `(md, fm, hints)` in one walk into a per-directory
dict, then resolve companions from the parent overview entry in a second
in-memory pass.

## Info

### IN-01: `update_page` calls `frontmatter.loads(raw)` before the no-frontmatter early-return

**File:** `packages/wiki-io/src/wiki_io/update_tokens.py:83,90`
**Issue:** `post = frontmatter.loads(raw)` happens unconditionally before the
`if not raw.startswith("---")` skip. For non-frontmatter files this parses a
no-op metadata dict that is then discarded. Reorder so the cheap string check
runs first.

**Fix:**

```python
raw = path.read_text(encoding="utf-8")
if not raw.startswith("---"):
    return ("skipped", 0)
try:
    post = frontmatter.loads(raw)
except Exception as exc:
    ...
```

### IN-02: Duplicate `parts[1].strip().split("\n")` between baseline and rewrite paths

**File:** `packages/wiki-io/src/wiki_io/update_tokens.py:103,121`
**Issue:** The same `fm_lines = parts[1].strip().split("\n")` computation runs
twice in `update_page`. Compute once, reuse.

**Fix:** Lift to a single assignment before the count-tokens call.

### IN-03: `_collect` first pass classifies any overview with `workflow_hints` as a fold source, regardless of category

**File:** `packages/wiki-io/src/wiki_io/scan_monorepo.py:631-643`
**Issue:** Inside `_collect`, the first pass treats *any* `.md` where
`md.stem == md.parent.name` and `workflow_hints` is present as a parent
overview. The downstream `domain_companions_by_dir` pass (line 681-) is
careful to filter `fm.get("category") != "package"` before folding, but the
`_collect` pass is not — it relies on the caller having already passed
`fold_companions=True` only for package-classification containers. Today the
two callers do exactly that, so behavior is correct, but the asymmetry
between the two passes is a maintenance hazard. Add the same category guard
to `_collect`'s first pass for parity.

**Fix:**

```python
fm_overview = _parse_frontmatter(text)
if fm_overview.get("category") not in (None, "package"):
    continue
hints = _parse_workflow_hints(text)
```

### IN-04: `test_count_tokens_live.py` integration-marker comment lists `TOK-02 (live)` only — TOK-01 unmentioned

**File:** `packages/wiki-io/tests/integration/test_count_tokens_live.py:7`
**Issue:** The module docstring mentions `TOK-02 (live)`. The mocked
counterpart in `tests/test_update_tokens.py` lists `TOK-01, TOK-02 (mocked)`.
The live test arguably covers TOK-01 end-to-end as well. Either trim the
mocked file's coverage line or add `TOK-01` to the live file for consistency.

**Fix:** Update the docstring header to list both requirements when applicable.

---

_Reviewed: 2026-05-19_
_Reviewer: Claude (gsd-code-reviewer)_
_Depth: standard_
