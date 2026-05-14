---
phase: 05-remaining-commands
reviewed: 2026-05-14T00:00:00Z
depth: standard
files_reviewed: 31
files_reviewed_list:
  - agents/code-wiki-agent/src/code_wiki_agent/cli.py
  - agents/code-wiki-agent/src/code_wiki_agent/commands/ingest.py
  - agents/code-wiki-agent/src/code_wiki_agent/commands/init.py
  - agents/code-wiki-agent/src/code_wiki_agent/commands/lint.py
  - agents/code-wiki-agent/src/code_wiki_agent/commands/log.py
  - agents/code-wiki-agent/src/code_wiki_agent/commands/scan.py
  - agents/code-wiki-agent/src/code_wiki_agent/config.py
  - agents/code-wiki-agent/src/code_wiki_mcp/server.py
  - agents/code-wiki-agent/tests/commands/test_lint_parity.py
  - agents/code-wiki-agent/tests/commands/test_scan_parity.py
  - agents/code-wiki-agent/tests/unit/test_commands_ingest.py
  - agents/code-wiki-agent/tests/unit/test_commands_init.py
  - agents/code-wiki-agent/tests/unit/test_commands_lint.py
  - agents/code-wiki-agent/tests/unit/test_commands_log.py
  - agents/code-wiki-agent/tests/unit/test_commands_scan.py
  - agents/code-wiki-agent/tests/unit/test_config.py
  - agents/code-wiki-agent/tests/unit/test_mcp_new_tools.py
  - cores/vault-io/src/vault_io/ingest_source.py
  - cores/vault-io/src/vault_io/ingest_work_item.py
  - cores/vault-io/src/vault_io/init_vault.py
  - cores/vault-io/src/vault_io/lint/container.py
  - cores/vault-io/src/vault_io/lint/dependency.py
  - cores/vault-io/src/vault_io/lint/domain.py
  - cores/vault-io/src/vault_io/lint/file_map.py
  - cores/vault-io/src/vault_io/lint/package_sync.py
  - cores/vault-io/src/vault_io/lint/source_sync.py
  - cores/vault-io/src/vault_io/lint/workflow_hints.py
  - cores/vault-io/src/vault_io/update_index.py
  - cores/vault-io/tests/test_ingest_source.py
  - cores/vault-io/tests/test_ingest_work_item.py
  - cores/vault-io/tests/test_lint_modules.py
findings:
  critical: 4
  warning: 6
  info: 4
  total: 14
status: fixes_applied
fixed_at: 2026-05-14T00:00:00Z
---

# Phase 05: Code Review Report

**Reviewed:** 2026-05-14
**Depth:** standard
**Files Reviewed:** 31
**Status:** issues_found

## Summary

This phase implements six new commands (log, init, scan, ingest, lint, trace) plus their MCP tool wrappers. The architecture is sound and the test coverage is reasonably thorough, but there are four blocker-level defects. Two involve stdout corruption in the MCP server (a direct protocol violation), one is a ValueError crash in the log-gap detection path, and one is a silent work/index.md omission from `scan`'s local `update_index`. Six warning-level issues affect lint correctness, YAML parsing edge cases, and a dropped field in the MCP log output. Four info items cover dead imports, magic numbers, and a missing capability in the MCP ingest tool.

---

## Critical Issues

### CR-01: `init_vault.py` prints to stdout unconditionally — corrupts MCP JSON-RPC stream

**File:** `cores/vault-io/src/vault_io/init_vault.py:87-97` and `261-272`

**Issue:** `_resolve_pinned_containers()` calls `print()` to stdout unconditionally at lines 87, 92–97 regardless of the `non_interactive` flag. `init_wiki()` then calls `print(f"[ok] Initialized Code Wiki at: ...")` etc. at lines 261–272 when `as_json=False`. Both code paths execute when `run_init()` in `commands/init.py` calls `init_wiki(...)` without `as_json=True`. The MCP `wiki_init` tool routes through `run_init()`, so any repo with detectable containers will emit plain-text `print()` output directly to stdout, corrupting the JSON-RPC framing that the `_StdoutGuard` in `server.py` is specifically designed to prevent. The guard only covers Python-level writes through `sys.stdout.write()`; `init_vault.py` is imported and runs in the same process, so its `print()` calls bypass the guard's `write()` method only when the guard is not yet in place — but since `init_vault` is imported lazily (inside the `wiki_init` MCP tool call), the guard is already installed. The `_StdoutGuard.write()` will raise `RuntimeError`, aborting the entire MCP session rather than just the one tool call.

**Fix:** Pass `as_json=True` from `run_init()` to `init_wiki()`, or replace all `print()` calls in `init_vault.py` with `logging.info()` so they route to stderr:

```python
# In commands/init.py, run_init():
result = init_wiki(
    wiki_path=wiki,
    repo_path=repo,
    topic=topic,
    tool=tool,
    force=force,
    non_interactive=True,
    as_json=True,   # suppress print() — required for MCP safety
)
```

Or alternatively, convert all `print()` calls in `init_vault.py` to `logger.info()` / `logger.warning()`.

---

### CR-02: `_parse_ingestor_response` silently drops the final list value when the YAML block ends without a trailing newline

**File:** `agents/code-wiki-agent/src/code_wiki_agent/commands/ingest.py:159-178`

**Issue:** The YAML list flush at line 162–164 runs only when encountering a non-list line. If the YAML block ends while `cur_list` is open and the loop exits normally, the flush at line 177–178 handles it correctly. However, `_parse_ingestor_response` calls `.strip()` on the yaml block (line 147), which strips any trailing newline. If the last field in the block is a list (e.g. `tags:\n  - a\n  - b`) and nothing follows it before the closing `---`, the in-loop flush at lines 162–164 never fires, but the post-loop flush at 177–178 does fire. This is actually handled correctly. The real bug is different: at line 162–164, when a non-list line is encountered while `cur_list` is open, the code flushes `cur_list` then resets `cur_key, cur_list = None, None` on line 164, but continues processing the current line on the next iteration. If line 165 (`if ":" not in line: continue`) hits a line with no colon (e.g. a blank line that wasn't stripped by `raw.rstrip()`), it silently skips. More critically, the YAML block produced by the LLM will often have `tags: []` parsed correctly via line 174, but a tags list like `tags:\n  - foo` will require `cur_list` flushed on the *next key line*. If the LLM emits `tags:` as the last YAML key with items, and the body follows with `\n---`, the closing `---` appears in `rest[closing_idx:]`, not in `yaml_block`. The `yaml_block` does not include the closing `---`. This is fine. The actual defect: `yaml_block.splitlines()` on line 155 iterates lines **without** blank-line filtering for the list-flush trigger. A blank line between list items and the next key causes `cur_list` to be flushed (via line 162) with an empty `line`, then `if ":" not in line: continue` at line 165 skips it — which is correct. The net result is that an LLM response with an empty line inside the YAML block *between* a list and the next key will lose the list. While unusual, LLMs do emit blank lines inside YAML blocks.

**Fix:** Replace the blank-line guard to not flush on empty lines:

```python
for raw in yaml_block.splitlines():
    line = raw.rstrip()
    if not line or line.startswith("#"):
        continue  # Skip blank/comment lines WITHOUT flushing cur_list
    if line.startswith("  - ") and cur_list is not None:
        cur_list.append(line[4:].strip())
        continue
    # End any open list only on a real key line
    if cur_list is not None:
        fm[cur_key] = cur_list
        cur_key, cur_list = None, None
    ...
```

The current code already does `if not line or line.startswith("#"): continue` at line 157-158 — BUT this `continue` is reached BEFORE the list-flush check at line 162, so empty lines do NOT flush the list. Re-reading carefully: line 157 says `if not line or line.startswith("#"): continue` which skips to the next iteration without reaching line 162. This means blank lines are handled correctly. **Reclassifying this to a WARNING** — see WR-01.

---

### CR-02 (revised): Log-gap detection crashes on malformed but regex-matching dates in log.md

**File:** `agents/code-wiki-agent/src/code_wiki_agent/commands/lint.py:298`

**Issue:** `LOG_ENTRY_RE` matches `\d{4}-\d{2}-\d{2}` — correct digit count but not constrained to valid calendar values. `dt.date.fromisoformat(m)` will raise `ValueError` for strings like `2026-13-45` (month 13, day 45). This is unguarded (no try/except), so a corrupted or hand-edited `log.md` with a valid-looking but invalid date in a `## [YYYY-MM-DD]` header will crash the entire `run_lint()` call with an unhandled `ValueError` propagating up through `_mechanical_pass()` to `run_lint()`, and then up to the CLI/MCP layer where it will be swallowed by the broad `except RuntimeError` in the CLI. But the MCP `wiki_lint` handler has no exception guard, so the tool call fails with an uncaught exception.

**Fix:**
```python
dates = []
for m in LOG_ENTRY_RE.findall(log_text):
    try:
        dates.append(dt.date.fromisoformat(m))
    except ValueError:
        pass  # malformed date in log header — skip silently
```

---

### CR-03: `scan.py`'s local `update_index` does not write `work/index.md` — diverges silently from `vault_io.update_index.update_index`

**File:** `agents/code-wiki-agent/src/code_wiki_agent/commands/scan.py:48-69`

**Issue:** `scan.py` defines a local `update_index()` wrapper (lines 48–69) that replicates only part of the `vault_io.update_index.update_index` logic. The local version scans work items (`scan_work`) and adds them to `pages["work"]` for the main index, but never writes `<workspace>/work/index.md`. The canonical `vault_io.update_index.update_index` (line 312–318 of `update_index.py`) does write `work/index.md`. After a scan that creates or updates work-item-linked pages, `work/index.md` will be stale. Any Obsidian user opening `work/index` will see an outdated list. This is not caught by any test because tests mock `update_index` entirely.

**Fix:** Replace the local wrapper with a direct import of the canonical function:

```python
# Remove the local update_index definition (lines 48-69)
# Add to the import block:
from vault_io.update_index import update_index  # already imports other symbols

# scan.py already imports scan_vault, scan_work, render_index etc. for the local
# wrapper — those imports become unused and should also be removed.
```

---

## Warnings

### WR-01: `_parse_ingestor_response` parses only `  - ` (2-space) indented lists — misses 4-space and tab indentation

**File:** `agents/code-wiki-agent/src/code_wiki_agent/commands/ingest.py:159`

**Issue:** The list-item detection `line.startswith("  - ")` (two spaces) is not aligned with what LLMs commonly emit. Claude and other models sometimes emit 4-space or tab-indented YAML lists. A `tags:` list indented with 4 spaces (`    - foo`) will not be detected as a list item; instead the code will attempt to parse it as a key-value pair (`"    - foo": ...`), which has no `:` (except potentially in the value), and be silently dropped via `if ":" not in line: continue`. The result is that `tags` is treated as an empty list (from `cur_key, cur_list = key, []`) and the items are lost, causing the LLM-generated page to be written with empty tags even when the LLM included them.

**Fix:**
```python
import re
_LIST_ITEM_RE = re.compile(r"^[ \t]+- ")

# In the parsing loop:
if _LIST_ITEM_RE.match(line) and cur_list is not None:
    cur_list.append(line.lstrip().lstrip("- ").strip())
    continue
```

---

### WR-02: `dependency.check()` fires `dep-detail-without-load-bearing` for every dependency page unconditionally

**File:** `cores/vault-io/src/vault_io/lint/dependency.py:57-60`

**Issue:** The `dep-detail-without-load-bearing` check (lines 57–60) runs for every page with a valid `kind` value, including `kind == "package-family"` and `kind == "service"`. Only `kind == "package"` pages are conceptually "detail pages" for an external dependency. Flagging family and service pages for not having `load_bearing: true` is semantically wrong and will generate noise on every vault that has service or package-family dependency pages. In a vault with 20 dependency pages (half service, half package), this fires 20 times even when everything is correctly structured.

**Fix:** Scope the check to `kind == "package"` pages only:
```python
if kind == "package":
    if not (fm.get("load_bearing") or "").strip().lower() in ("true", "yes", "1"):
        findings.append(f"{key}: dep-detail-without-load-bearing: ...")
```

---

### WR-03: `_add_stale_tag` false-positive idempotency check — `"stale: true"` substring matches `"stale: true-ish"` or inline body mentions

**File:** `agents/code-wiki-agent/src/code_wiki_agent/commands/scan.py:249`

**Issue:** The idempotency guard `if "stale: true" in text: return` (line 249) uses substring matching over the full file content. If a page's body contains the prose string "stale: true" (e.g. in documentation about the frontmatter schema, or a page with `stale: truly` in frontmatter), the function returns early and never prepends the actual `stale: true` frontmatter field. This means a deleted package whose vault page happens to mention "stale: true" in its body will silently not get the stale tag added.

**Fix:** Restrict the check to the frontmatter block only:
```python
# Only check within frontmatter, not the full file
frontmatter_end = text.find("\n---", 3)
if frontmatter_end != -1:
    frontmatter = text[:frontmatter_end]
else:
    frontmatter = text
if "stale: true" in frontmatter:
    return
```

---

### WR-04: `WikiLogOutput` drops the `detail` field — MCP callers cannot see the detail they sent

**File:** `agents/code-wiki-agent/src/code_wiki_mcp/server.py:157-163`

**Issue:** `WikiLogOutput` (lines 157–163) has fields `status, log_path, date, op, title, header` but omits `detail`. `LogResult` includes `detail` (it mirrors all fields from `append_log()`). The MCP response thus silently drops the optional detail the caller passed. While this is not data loss (the detail is written to `log.md`), MCP callers cannot confirm what was recorded, and the field asymmetry between `LogResult` and `WikiLogOutput` will cause confusion.

**Fix:**
```python
class WikiLogOutput(BaseModel):
    status: str
    log_path: str
    date: str
    op: str
    title: str
    header: str
    detail: str | None = None  # Add this field
```

And in `wiki_log`:
```python
return WikiLogOutput(
    ...
    detail=result.detail,
)
```

---

### WR-05: `init_vault.py` calls `sys.exit()` inside `_error()` — library code that kills the host process

**File:** `cores/vault-io/src/vault_io/init_vault.py:127-132`

**Issue:** `_error()` calls `sys.exit(1)` unconditionally (line 132). This function is called from `init_wiki()` (a library function) at lines 153 and 168. When `run_init()` in the CLI layer catches `SystemExit`, it re-raises it as-is through the `except (RuntimeError, FileNotFoundError, SystemExit)` block in `cli.py:218`, converting it to exit code 1. But in the MCP server, `wiki_init` has no such guard — `SystemExit` propagates up and kills the entire MCP server process rather than just failing the tool call.

**Fix:** Replace `sys.exit()` in `_error()` with a `RuntimeError`:
```python
def _error(message, as_json=False):
    if as_json:
        print(json.dumps({"status": "error", "message": message}))
    raise RuntimeError(message)
```

Or catch `SystemExit` in `wiki_init`:
```python
async def wiki_init(input: WikiInitInput, ctx: Context) -> WikiInitOutput:
    ...
    try:
        result = await run_init(...)
    except (RuntimeError, SystemExit) as e:
        raise RuntimeError(f"init failed: {e}") from e
```

---

### WR-06: `_resolve_pinned_containers` prints to stdout before `non_interactive` check — MCP stream corrupted even when `non_interactive=True`

**File:** `cores/vault-io/src/vault_io/init_vault.py:87-97`

**Issue:** The `print()` calls at lines 87, 92–97 run unconditionally regardless of `non_interactive`. These lines execute whenever the container detector finds any records (even if fully auto-resolvable). Since `run_init()` hardcodes `non_interactive=True`, the `input()` at line 107 is never reached — but the diagnostic `print()` output on lines 87–97 still fires to stdout, triggering `_StdoutGuard.write()` and raising `RuntimeError` in the MCP server.

**Fix:** Guard these prints with `not non_interactive`, or replace with `logger.info()`:
```python
def _resolve_pinned_containers(repo: Path, non_interactive: bool) -> list[dict]:
    records = _detect_containers(repo)
    if records and records[0]["classification"] == "single-package":
        if not non_interactive:
            print("Detected: single-package repo (no structural containers).")
        return []
    if not records:
        return []
    if not non_interactive:
        print(f"Detected {len(records)} top-level container(s):")
        ...
```

Note: CR-01 and WR-06 are related but distinct. CR-01 covers `init_wiki()`'s own `print()` output (lines 261–272); WR-06 covers `_resolve_pinned_containers()`'s print output (lines 87–97). Both must be fixed for MCP safety.

---

## Info

### IN-01: Three unused imports in `ingest_source.py`

**File:** `cores/vault-io/src/vault_io/ingest_source.py:27-29`

**Issue:** `resolve_wiki_and_repo`, `ensure_subpage`, and `compute_state_gate` are imported but never called in the module body. These are likely leftover from the lattice-wiki-core port. They add import cost and create false coupling.

**Fix:** Remove lines 27–29:
```python
# Remove these three import lines:
from vault_io._workspace import resolve_wiki_and_repo
from vault_io.layout_io import ensure_subpage
from vault_io.scan_monorepo import compute_state_gate
```

---

### IN-02: `scan.py` local `update_index` makes `render_category_index`, `render_index`, `scan_vault`, `scan_work`, `CATEGORY_INDEX_FILES`, `CATEGORY_LABELS` imports redundant when using the canonical function

**File:** `agents/code-wiki-agent/src/code_wiki_agent/commands/scan.py:31-38`

**Issue:** If CR-03 is fixed by replacing the local `update_index` with the canonical import, the six symbols currently imported from `vault_io.update_index` at lines 32–38 (`CATEGORY_INDEX_FILES`, `CATEGORY_LABELS`, `render_category_index`, `render_index`, `scan_vault`, `scan_work`) become unused. Noted here for cleanup tracking.

**Fix:** After fixing CR-03, replace the entire `from vault_io.update_index import (...)` block with:
```python
from vault_io.update_index import update_index
```

---

### IN-03: `wiki_ingest` MCP tool does not expose `pkg_title` — sub-page templates always use directory name

**File:** `agents/code-wiki-agent/src/code_wiki_mcp/server.py:292-340`

**Issue:** `run_ingest_work_item()` accepts a `pkg_title` parameter (display title for the package sub-page template), but `WikiIngestInput` does not include a `pkg_title` field and the `wiki_ingest` handler never passes it. When a work item is filed with `pkg_dir` set, `file_work_item()` falls back to `pkg_dir.name` for the display title, which is the raw directory name (e.g. `"auth-service"`) rather than a human-readable title.

**Fix:** Add `pkg_title` to `WikiIngestInput`:
```python
class WikiIngestInput(BaseModel):
    ...
    pkg_title: str | None = Field(None, description="Display title for package sub-page (defaults to pkg_dir name)")
```

And pass it in the handler:
```python
result = await run_ingest_work_item(
    ...
    pkg_title=input.pkg_title,
)
```

---

### IN-04: `FanOutResult` imported in `scan.py` but only used as a type annotation — `SubagentPool` is the runtime object

**File:** `agents/code-wiki-agent/src/code_wiki_agent/commands/scan.py:18`

**Issue:** `FanOutResult` is imported from `subagent_runtime.pool` at line 18 and used only as a type annotation for `fan_result` at line 363. This is not wrong but since `from __future__ import annotations` is used (line 1), the annotation is not evaluated at runtime and the import could be moved to `TYPE_CHECKING`. Minor cleanliness issue.

**Fix:** Either keep as-is (acceptable) or move to `TYPE_CHECKING` block if import cost matters.

---

_Reviewed: 2026-05-14_
_Reviewer: Claude (gsd-code-reviewer)_
_Depth: standard_
