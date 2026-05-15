---
phase: 03-query-vertical-slice-hybrid-search
reviewed: 2026-05-14T00:00:00Z
depth: standard
files_reviewed: 4
files_reviewed_list:
  - agents/code-wiki-agent/src/code_wiki_agent/commands/query.py
  - agents/code-wiki-agent/tests/unit/test_query_code_fallback.py
  - agents/code-wiki-agent/tests/unit/test_query_result.py
  - cores/model-adapter/src/model_adapter/models.toml
findings:
  critical: 1
  warning: 5
  info: 4
  total: 10
status: issues_found
---

# Phase 03: Code Review Report

**Reviewed:** 2026-05-14
**Depth:** standard
**Files Reviewed:** 4
**Status:** issues_found

## Summary

Review focuses on the Plan 03-08 / 03-09 gap-closure deltas: the vault-thin code-fallback fan-out, the bounded `read_file` tool, prompt-contract tightening, and the one-shot synthesizer retry.

The security-sensitive surface (`_read_file_bounded`, `_resolve_repo_root`) is solid for the in-scope threat model: path traversal via `..` is rejected, symlink escape is rejected (both sides go through `Path.resolve()`), the `.code-wiki/` allow-list bypass is rejected, file-size caps are enforced via `read(max_bytes + 1)`, and the iteration cap (`_CODE_READER_MAX_ITERS = 5`) terminates the tool-call loop deterministically. The synthesizer retry is genuinely one-shot — no looping. The `[vault-thin: ...]` marker is prefixed only on the fallback branch, and `apply_guardrails` preserves it.

One **CRITICAL** correctness bug was found: when the librarian fan-out returns zero successes (e.g., all librarian calls errored out) AND the code-fallback succeeds with citations, G4 in `apply_guardrails` fires on the empty `fan_result.successes` and falsely flags the code-derived answer as unsupported, clearing its citations.

Several **WARNING**-level concerns: `pages_drilled` mis-reports work on the fallback path, the tool-call dispatch loop does not verify the tool name, the last loop iteration's tool reads are discarded, `datetime.utcnow()` is deprecated in 3.12, and the agent silently degrades to a useless feature in Pat's documented UAT vault layout where `_resolve_repo_root` falls back to the vault itself.

## Critical Issues

### CR-01: G4 guardrail falsely clears citations on the code-fallback path when librarian successes are empty

**File:** `agents/code-wiki-agent/src/code_wiki_agent/commands/query.py:626-637, 939-975`
**Issue:**
On the code-fallback branch, the librarian `fan_result.successes` may legitimately be empty — for example, when every librarian call errored out (all pages in `fan_result.errors`), or when the librarian pool returned no successes at all. The code-fallback then runs, produces a marker-prefixed answer derived from real code excerpts, and that synthesizer answer can contain `[[wiki/...]]` wikilinks that the code reader saw in the source files (e.g., docstrings, comments).

`run_query` then calls `apply_guardrails(query_result, wiki, fan_result)` with `fan_result` still pointing at the **librarian** result. G4 (`query.py:628`) checks `if not fan_result.successes and result.citations` — both are true on this path — and clears the citations + prepends `[warning: no librarian excerpts; answer is unsupported by retrieved pages]`. The answer IS supported, just by code excerpts, not vault excerpts.

The in-code comment at lines 971–974 acknowledges the case where "NO_RELEVANT_CONTENT counts as a success at the pool level," but it does not handle the case where the librarian pool returned **zero** successes (errors-only or empty top_pages). In that case G4 trips spuriously.

**Fix:**
Either skip G4 when `code_fallback_used is True`, or pass a synthesized fan_result through to `apply_guardrails`. Minimal patch:
```python
# Step 9
if code_fallback_used:
    # Skip G4: fan_result reflects librarian work, but the answer is
    # supported by the code-reader fan-out, not librarian excerpts.
    # Apply G1 only (unresolved-wikilink check still valid).
    unresolved = _compute_unresolved_wikilinks(query_result.answer, wiki)
    if unresolved:
        query_result = QueryResult(
            answer=(
                query_result.answer
                + f"\n[warning: {len(unresolved)} citation(s) did not resolve: {unresolved}]"
            ),
            citations=query_result.citations,
            pages_drilled=query_result.pages_drilled,
            search_scores=query_result.search_scores,
        )
else:
    query_result = apply_guardrails(query_result, wiki, fan_result)
```

## Warnings

### WR-01: `pages_drilled` mis-reports on the code-fallback path

**File:** `agents/code-wiki-agent/src/code_wiki_agent/commands/query.py:954-967`
**Issue:**
`pages_drilled=len(fan_result.successes)` always counts **librarian** successes. On the code-fallback path, this number reflects librarian calls that returned `NO_RELEVANT_CONTENT` (or errored), not the actual drilling work the code-reader performed. Downstream observers (eval harness, trace summary) will see "5 pages drilled" when the substantive work happened in the code-reader fan-out.

**Fix:**
Track the active fan-out result and use it:
```python
active_fan = code_fan if code_fallback_used else fan_result
# pages_drilled=len(active_fan.successes)
```
This requires returning `code_fan` from `_run_code_fallback` (currently only the answer is returned), or counting useful items separately.

### WR-02: Tool-call dispatch does not verify the tool name

**File:** `agents/code-wiki-agent/src/code_wiki_agent/commands/query.py:468-486`
**Issue:**
The loop iterates over `resp.tool_calls` and unconditionally calls `_read_file_bounded(repo_root, requested)` for each call, regardless of `call.get("name")`. If the model hallucinates a tool name (e.g., `write_file`, `grep`, `list_dir`), the path argument is still passed to the file reader. The containment check in `_read_file_bounded` keeps this safe, but the model never receives feedback that its tool name was wrong — it sees file contents, which encourages further misuse, or sees a tool-error string that names a path it never asked for.

**Fix:**
```python
for call in tool_calls:
    name = call.get("name", "") if isinstance(call, dict) else ""
    if name != "read_file":
        msgs.append(ToolMessage(
            content=f"ERROR: unknown tool {name!r}; only read_file is available",
            tool_call_id=call.get("id", ""),
        ))
        continue
    # ... existing read_file dispatch ...
```

### WR-03: Iteration cap discards the last round's tool reads

**File:** `agents/code-wiki-agent/src/code_wiki_agent/commands/query.py:468-494`
**Issue:**
The loop is `for iteration in range(_CODE_READER_MAX_ITERS):`. Inside, if `tool_calls` is non-empty, the tool results are appended to `msgs`, and the next iteration re-invokes the LLM. On the 5th (final) iteration, if `tool_calls` is still non-empty, the tool results are appended to `msgs` but the loop exits before another `ainvoke` — so the model never gets to use those tool results to produce a final answer. The function returns `NO_RELEVANT_CONTENT`, throwing away up-to-N tool reads' worth of cost and context. This is wasteful and looks like a fence-post error.

**Fix:**
Either give the model one final no-tools call to produce an answer from the accumulated tool results, or reduce `_CODE_READER_MAX_ITERS` by one and document the semantics:
```python
for iteration in range(_CODE_READER_MAX_ITERS):
    resp = await code_llm.ainvoke(msgs)
    tool_calls = getattr(resp, "tool_calls", None) or []
    if not tool_calls:
        return getattr(resp, "content", "") or ""
    if iteration == _CODE_READER_MAX_ITERS - 1:
        # Last iteration: force a final answer from accumulated tool results.
        msgs.append(resp)
        for call in tool_calls:
            # ... execute tool ...
        final = await code_llm.ainvoke(msgs)  # without tools, or trust it not to call them
        return getattr(final, "content", "") or "NO_RELEVANT_CONTENT"
    # ... existing tool dispatch ...
```

### WR-04: `_resolve_repo_root` silently neuters the feature in the documented UAT layout

**File:** `agents/code-wiki-agent/src/code_wiki_agent/commands/query.py:327-351`
**Issue:**
The docstring explicitly acknowledges that Pat's UAT layout (vault at `~/Personal/wiki/deep-agents/`, repo at `~/Personal/deep-agents/`) is NOT a parent-child relationship, so `_resolve_repo_root` falls back to `vault_path` itself. The code-reader is then handed a "repo root" that contains only the vault markdown files. The CODE_READER_SYSTEM prompt tells the model "your job is to read the actual source code"; it will hallucinate plausible source paths under the vault, get `ERROR: not a regular file` for all of them, hit the iteration cap or give up, and return `NO_RELEVANT_CONTENT`. The disclaimer is shown to the user. The feature is non-functional in the very layout documented in user MEMORY.

A WARNING log emits, but it appears once at fallback time and is easy to miss in trace output. The prompt offers no signal to the model that the search is hopeless.

**Fix:**
Accept an explicit `repo_root` from `resolve_wiki_and_repo` (which already returns a `(wiki, repo)` tuple — the second element is currently discarded as `_`). The workspace resolver is the authoritative source for repo location; the heuristic is a backup, not the primary path.
```python
wiki, repo = resolve_wiki_and_repo(vault_path)
# ... pass repo into _run_code_fallback ...
def _run_code_fallback(query, wiki, repo, top_pages, pool, query_id):
    repo_root = repo if repo is not None else _resolve_repo_root(wiki)
```

### WR-05: `datetime.utcnow()` is deprecated

**File:** `agents/code-wiki-agent/src/code_wiki_agent/commands/query.py:826, 978`
**Issue:**
`datetime.datetime.utcnow()` emits a `DeprecationWarning` in Python 3.12+ and is scheduled for removal. The project floor is 3.11, but the call will start warning the moment a developer upgrades.

**Fix:**
```python
started_at = datetime.datetime.now(datetime.UTC).isoformat().replace("+00:00", "Z")
# or
started_at = datetime.datetime.now(datetime.timezone.utc).isoformat().replace("+00:00", "Z")
```

## Info

### IN-01: The `@tool`-decorated `read_file` closure is bound but never actually invoked

**File:** `agents/code-wiki-agent/src/code_wiki_agent/commands/query.py:422-436, 478-483`
**Issue:**
`read_file` is decorated with `@tool` so that `code_llm_raw.bind_tools([read_file])` can introspect its schema and advertise the tool to the model. But the actual tool-execution path (lines 478–483) bypasses the decorated wrapper and calls `_read_file_bounded(repo_root, requested)` directly. The `@tool` wrapper's error-handling (PermissionError → "ERROR: ..." string) is duplicated inside the manual dispatch loop. Two copies of the same error-handling drift if one is updated.

**Fix:**
Either invoke the decorated tool via `read_file.invoke({"path": requested})` so the error-handling lives in one place, or note clearly that the `@tool` wrapper is schema-only.

### IN-02: Marker string is not constant-checked at the regular-path output boundary

**File:** `agents/code-wiki-agent/src/code_wiki_agent/commands/query.py:924, 184`
**Issue:**
If a librarian excerpt contains the literal string `[vault-thin: answer derived from source code]` (e.g., quoted in a wiki page that talks about this very feature), the synthesizer could echo it verbatim into the regular-path `answer`. Downstream consumers that filter on `answer.startswith(CODE_FALLBACK_MARKER)` would then mis-classify a vault-derived answer as code-derived. Theoretical; the eval harness comment notes "count occurrences of this marker in query trace summaries" — that count would be off.

**Fix:**
Track `code_fallback_used` in the trace record (already done at line 990) and rely on that flag rather than string-matching the answer. If callers must rely on the marker, consider a less likely-to-appear sentinel (e.g., a UUID-like token).

### IN-03: `code_excerpts_text` is truncated silently without a marker

**File:** `agents/code-wiki-agent/src/code_wiki_agent/commands/query.py:514-518`
**Issue:**
The regular-path equivalent at lines 905–914 logs a warning AND keeps the truncation marker conventions (none added, but a WARNING fires with query_id). The code-fallback's truncation at line 517–518 silently slices to 60000 with no log, no marker. A 60000-char cliff in the prompt mid-quotation can cut a code block in half, and the synthesizer will quote the truncated half verbatim including line numbers that no longer match the source. Minor — same class of issue exists in regular path, but at least there it logs.

**Fix:**
```python
if len(code_excerpts_text) > 60000:
    logger.warning(
        "Truncating code-reader excerpts before synthesis (query_id=%s)",
        query_id,
    )
    code_excerpts_text = code_excerpts_text[:60000] + "\n[TRUNCATED]"
```

### IN-04: `_compute_unresolved_wikilinks` duplicates G1 resolution logic

**File:** `agents/code-wiki-agent/src/code_wiki_agent/commands/query.py:539-558, 642-650`
**Issue:**
The wikilink resolution loop is duplicated verbatim between `_compute_unresolved_wikilinks` and `apply_guardrails` (G1). The docstring of `_compute_unresolved_wikilinks` notes "Resolution rules mirror apply_guardrails' G1 logic" — explicit acknowledgment of the duplication. If the resolution rules change (e.g., to handle anchors `[[page#section]]`, or to honor a case-insensitivity flag), both copies must be updated together. The class of bug the duplicate `.md.md` test guards against (test_apply_guardrails_g1_no_double_md_extension) lives in two places now.

**Fix:**
Have `apply_guardrails` call `_compute_unresolved_wikilinks(result.answer, vault_path)` instead of re-implementing it.

---

_Reviewed: 2026-05-14_
_Reviewer: Claude (gsd-code-reviewer)_
_Depth: standard_
