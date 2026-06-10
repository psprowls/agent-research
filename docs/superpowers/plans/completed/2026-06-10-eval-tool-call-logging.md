# Eval Tool-Call Logging (`tools.json`) and Tool Assertions — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Every cc-eval run writes a per-call `tools.json` artifact (full params, ordered, subagent-tagged), and scenarios can assert on tool calls via a new `kind: tools` verifier.

**Architecture:** Two halves inside `packages/claude-code-evals`: (1) capture — `transcript.py` keeps full `tool_use` inputs and merges subagent-transcript JSONLs, and the orchestrator serializes the result to `<run_dir>/tools.json`; (2) assertions — new Pydantic models in `schemas.py` (`ToolAssertion`, `OrderStep`, `VerifyEntry kind: tools`) evaluated by a pure-Python `ToolsVerifier(VerifierBase)` in `verify/tools.py` against the in-memory `Transcript`.

**Tech Stack:** Python 3.11, Pydantic v2, pytest, deepeval (`VerifierBase` subclasses `deepeval.metrics.BaseMetric`). No new dependencies.

**Spec:** `docs/superpowers/specs/2026-06-10-eval-tool-call-logging-design.md`

**Run tests with:** `uv run --package claude-code-evals pytest <path>` from the repo root (`/Users/pat/Personal/agent-research`). All tasks are offline-fast except Task 9 (`-m integration`).

## Decisions locked in by this plan (beyond the spec)

The spec left a few small implementation choices open; this plan fixes them:

1. **A `feed` field (`"stream"` | `"jsonl"`) is added to `ToolCallEvent`** (in addition to the spec's fields). Reason: the spec mandates "metrics.json untouched", but `metrics._tool_calls_before_first_edit` and `rubric._build_tool_summary` iterate `transcript.tool_calls`. JSONL-merged subagent calls would silently change both. `source` can't distinguish (the main stream may itself carry subagent-tagged calls, which ARE counted today). `feed` marks provenance so metrics/rubric filter to `feed == "stream"` and produce byte-identical output.
2. **Non-string param values whose JSON serialization is ≤ 500 chars stay native** (dict/list/number as-is) in `tools.json`; only over-cap values are replaced by a truncated JSON string with the marker. (Friendlier to `jq`; the spec's "JSON-serialized then capped the same way" governs the over-cap case.)
3. **JSONL-merged subagent calls get `seq` numbers continuing after all main-stream calls**, in file order. Cross-feed ordering is therefore approximate — acceptable because ordering assertions default to main-only scope.
4. **`ToolsVerifier` constructs with `threshold=1.0`** so `passed` (=`success`) requires every assertion to pass, while `score` is the fraction passed.
5. **A missing `projects/` dir warns only when the transcript shows `subagent_dispatches > 0`** (otherwise every subagent-free run would carry a noise warning). Unreadable/malformed individual files always warn.
6. **`tools.json` is written unconditionally** alongside the other artifacts — `parse_transcript("")` yields an empty transcript, so dry runs get `{"total_calls": 0, ...}`. This is the simplest superset of "whenever a transcript exists".

## File structure

| File | Status | Responsibility |
|---|---|---|
| `packages/claude-code-evals/src/claude_code_evals/transcript.py` | modify | `ToolCallEvent` enrichment, `Transcript.warnings`, subagent-JSONL merge |
| `packages/claude-code-evals/src/claude_code_evals/tools_log.py` | create | `render_tools_json()` — serialization + truncation only |
| `packages/claude-code-evals/src/claude_code_evals/metrics.py` | modify | filter to `feed == "stream"` (output preservation) |
| `packages/claude-code-evals/src/claude_code_evals/verify/rubric.py` | modify | filter to `feed == "stream"` (judge-input preservation) |
| `packages/claude-code-evals/src/claude_code_evals/schemas.py` | modify | `OrderStep`, `ToolAssertion`, `VerifyEntry` gains `kind: tools` + `assertions` |
| `packages/claude-code-evals/src/claude_code_evals/verify/tools.py` | create | matching semantics + `ToolsVerifier` |
| `packages/claude-code-evals/src/claude_code_evals/orchestrator.py` | modify | pass projects dir to parser, dispatch `ToolsVerifier`, write `tools.json` |
| `packages/claude-code-evals/tests/test_transcript.py` | modify | parser tests (Tasks 1–2) |
| `packages/claude-code-evals/tests/test_metrics.py` | modify | feed-filter regression test (Task 3) |
| `packages/claude-code-evals/tests/test_tools_log.py` | create | serializer tests (Task 4) |
| `packages/claude-code-evals/tests/test_schemas.py` | modify | validation tests (Task 5) |
| `packages/claude-code-evals/tests/test_verify_tools.py` | create | matcher + verifier tests (Tasks 6–7) |
| `packages/claude-code-evals/tests/test_orchestrator.py` | modify | artifact + dispatch tests (Task 8) |
| `packages/claude-code-evals/tests/test_tools_integration.py` | create | `integration`-marked end-to-end (Task 9) |

---

### Task 1: Enrich `ToolCallEvent` and capture full inputs from the main stream

**Files:**
- Modify: `packages/claude-code-evals/src/claude_code_evals/transcript.py`
- Test: `packages/claude-code-evals/tests/test_transcript.py`

Background for the implementer: `claude -p --output-format stream-json --verbose` emits one JSON event per line. `assistant` events contain `message.content` blocks; `tool_use` blocks carry `id`, `name`, `input`. Subagent-originated assistant events carry a top-level `parent_tool_use_id` (the id of the `Agent`/`Task` tool_use that spawned them); we read both `parent_tool_use_id` and `parentToolUseId` spellings because the exact casing is part of the spec's empirical question (Task 9 pins it down).

- [ ] **Step 1: Write the failing tests**

Append to `packages/claude-code-evals/tests/test_transcript.py` (the file already defines `_make_jsonl`, `ASSISTANT_EVENT` — a Read of `README.md` with id `tu1` — and `EDIT_EVENT` — an Edit of `src/foo.py` with id `tu2`):

```python
# --- ToolCallEvent enrichment (tools.json capture) ---


def test_tool_call_full_input_captured():
    t = parse_transcript(_make_jsonl(EDIT_EVENT))
    call = t.tool_calls[0]
    assert call.input == {"file_path": "src/foo.py", "old_string": "a", "new_string": "b"}
    assert call.input_keys == ["file_path", "old_string", "new_string"]
    assert call.tool_use_id == "tu2"


def test_tool_call_seq_is_global_order():
    t = parse_transcript(_make_jsonl(ASSISTANT_EVENT, EDIT_EVENT))
    assert [c.seq for c in t.tool_calls] == [0, 1]
    assert [c.tool for c in t.tool_calls] == ["Read", "Edit"]


def test_main_stream_call_defaults():
    t = parse_transcript(_make_jsonl(ASSISTANT_EVENT))
    call = t.tool_calls[0]
    assert call.source == "main"
    assert call.parent_tool_use_id is None
    assert call.feed == "stream"


def test_main_stream_subagent_tagged_call():
    ev = {
        "type": "assistant",
        "parent_tool_use_id": "toolu_parent01",
        "message": {
            "content": [
                {"type": "tool_use", "id": "tu9", "name": "Read", "input": {"file_path": "x.md"}}
            ]
        },
    }
    t = parse_transcript(_make_jsonl(ev))
    call = t.tool_calls[0]
    assert call.source == "subagent"
    assert call.parent_tool_use_id == "toolu_parent01"
    assert call.feed == "stream"


def test_main_stream_subagent_camelcase_tag():
    ev = {
        "type": "assistant",
        "parentToolUseId": "toolu_parent02",
        "message": {
            "content": [
                {"type": "tool_use", "id": "tu10", "name": "Bash", "input": {"command": "ls"}}
            ]
        },
    }
    t = parse_transcript(_make_jsonl(ev))
    assert t.tool_calls[0].parent_tool_use_id == "toolu_parent02"
    assert t.tool_calls[0].source == "subagent"
```

- [ ] **Step 2: Run the new tests to verify they fail**

Run: `uv run --package claude-code-evals pytest tests/test_transcript.py -v -k "tool_call_full or seq_is_global or stream"`
Expected: FAIL — `AttributeError: 'ToolCallEvent' object has no attribute 'input'` (and similar for `seq`, `source`, `feed`).

- [ ] **Step 3: Implement the enriched event**

In `packages/claude-code-evals/src/claude_code_evals/transcript.py`:

Replace the `ToolCallEvent` dataclass:

```python
@dataclass
class ToolCallEvent:
    tool: str
    input_keys: list[str]
    input: dict = field(default_factory=dict)
    tool_use_id: str = ""
    seq: int = 0
    parent_tool_use_id: str | None = None
    source: str = "main"  # "main" | "subagent"
    feed: str = "stream"  # "stream" (main stream-json) | "jsonl" (subagent transcript file)
```

(Defaults keep any existing two-arg constructions working.)

In `parse_transcript`, inside the `ev_type == "assistant"` branch, extract the parent id once and pass it down — replace:

```python
                elif block.get("type") == "tool_use":
                    _handle_tool_use(t, block)
```

with:

```python
                elif block.get("type") == "tool_use":
                    _handle_tool_use(t, block, parent_tool_use_id=parent_id)
```

and immediately after `msg = ev.get("message") or {}` add:

```python
            parent_id = ev.get("parent_tool_use_id") or ev.get("parentToolUseId") or None
```

Replace `_handle_tool_use`'s first lines:

```python
def _handle_tool_use(t: Transcript, block: dict, parent_tool_use_id: str | None = None) -> None:
    name = block.get("name", "")
    inp = block.get("input") or {}
    keys = list(inp.keys())

    t.tool_calls.append(
        ToolCallEvent(
            tool=name,
            input_keys=keys,
            input=inp,
            tool_use_id=block.get("id", ""),
            seq=len(t.tool_calls),
            parent_tool_use_id=parent_tool_use_id,
            source="subagent" if parent_tool_use_id else "main",
            feed="stream",
        )
    )
    t.tool_call_counts[name] = t.tool_call_counts.get(name, 0) + 1
```

The rest of `_handle_tool_use` (files_read/edited/written, Agent, Skill bookkeeping) stays exactly as-is.

- [ ] **Step 4: Run the full transcript test file**

Run: `uv run --package claude-code-evals pytest tests/test_transcript.py -v`
Expected: ALL PASS (new tests plus all pre-existing ones — the defaults must not break them).

- [ ] **Step 5: Commit**

```bash
git add packages/claude-code-evals/src/claude_code_evals/transcript.py packages/claude-code-evals/tests/test_transcript.py
git commit -m "feat(claude-code-evals): capture full tool-call inputs with seq/source tagging"
```

---

### Task 2: Merge subagent transcript JSONLs into the call list

**Files:**
- Modify: `packages/claude-code-evals/src/claude_code_evals/transcript.py`
- Test: `packages/claude-code-evals/tests/test_transcript.py`

Background: the runner isolates each run under its own `CLAUDE_CONFIG_DIR` (`iso.cfg_dir`); Claude Code writes session transcripts to `<cfg_dir>/projects/<munged-cwd>/<session>.jsonl`. Subagent (sidechain) entries in those files have `"isSidechain": true` and the same `assistant`/`message.content` shape as the stream. Because the dir is per-run, there is no leakage from other sessions. We dedupe against main-stream calls by `tool_use_id` in case the stream already carried the same call.

- [ ] **Step 1: Write the failing tests**

Append to `packages/claude-code-evals/tests/test_transcript.py`:

```python
# --- subagent JSONL merge ---


def _write_subagent_jsonl(projects_dir, entries, rel="myproj/session-1.jsonl"):
    path = projects_dir / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(json.dumps(e) for e in entries))
    return path


SIDECHAIN_ENTRY = {
    "type": "assistant",
    "isSidechain": True,
    "message": {
        "content": [
            {"type": "tool_use", "id": "sub_tu1", "name": "Grep", "input": {"pattern": "foo"}}
        ]
    },
}


def test_subagent_jsonl_merged_after_stream_calls(tmp_path):
    projects = tmp_path / "projects"
    _write_subagent_jsonl(projects, [SIDECHAIN_ENTRY])
    t = parse_transcript(_make_jsonl(ASSISTANT_EVENT), subagent_projects_dir=projects)
    assert len(t.tool_calls) == 2
    merged = t.tool_calls[1]
    assert merged.tool == "Grep"
    assert merged.input == {"pattern": "foo"}
    assert merged.source == "subagent"
    assert merged.feed == "jsonl"
    assert merged.seq == 1
    assert t.warnings == []


def test_subagent_jsonl_dedupes_by_tool_use_id(tmp_path):
    projects = tmp_path / "projects"
    dup = {
        "type": "assistant",
        "isSidechain": True,
        "message": {
            "content": [
                {"type": "tool_use", "id": "tu1", "name": "Read", "input": {"file_path": "README.md"}}
            ]
        },
    }
    _write_subagent_jsonl(projects, [dup])
    # ASSISTANT_EVENT's Read already has id tu1 in the main stream
    t = parse_transcript(_make_jsonl(ASSISTANT_EVENT), subagent_projects_dir=projects)
    assert len(t.tool_calls) == 1


def test_subagent_jsonl_skips_non_sidechain_entries(tmp_path):
    projects = tmp_path / "projects"
    main_session = {
        "type": "assistant",
        "isSidechain": False,
        "message": {
            "content": [
                {"type": "tool_use", "id": "main_tu", "name": "Bash", "input": {"command": "ls"}}
            ]
        },
    }
    _write_subagent_jsonl(projects, [main_session])
    t = parse_transcript("", subagent_projects_dir=projects)
    assert t.tool_calls == []


def test_subagent_jsonl_malformed_lines_skipped(tmp_path):
    projects = tmp_path / "projects"
    path = projects / "myproj" / "session-1.jsonl"
    path.parent.mkdir(parents=True)
    path.write_text("not json\n" + json.dumps(SIDECHAIN_ENTRY) + "\n{broken")
    t = parse_transcript("", subagent_projects_dir=projects)
    assert [c.tool for c in t.tool_calls] == ["Grep"]


def test_subagent_jsonl_calls_do_not_touch_counts_or_files(tmp_path):
    projects = tmp_path / "projects"
    sidechain_read = {
        "type": "assistant",
        "isSidechain": True,
        "message": {
            "content": [
                {"type": "tool_use", "id": "sub_tu2", "name": "Read", "input": {"file_path": "sub.md"}}
            ]
        },
    }
    _write_subagent_jsonl(projects, [sidechain_read])
    t = parse_transcript(_make_jsonl(ASSISTANT_EVENT), subagent_projects_dir=projects)
    # metrics inputs unchanged: only the main-stream Read is counted
    assert t.tool_call_counts == {"Read": 1}
    assert t.files_read == ["README.md"]


def test_missing_projects_dir_warns_only_with_dispatches(tmp_path):
    agent_event = {
        "type": "assistant",
        "message": {
            "content": [{"type": "tool_use", "id": "tu4", "name": "Agent", "input": {"prompt": "go"}}]
        },
    }
    missing = tmp_path / "projects"  # never created
    t = parse_transcript(_make_jsonl(agent_event), subagent_projects_dir=missing)
    assert len(t.warnings) == 1
    assert "subagent transcripts unavailable" in t.warnings[0]

    t2 = parse_transcript(_make_jsonl(ASSISTANT_EVENT), subagent_projects_dir=missing)
    assert t2.warnings == []


def test_unreadable_jsonl_file_warns(tmp_path):
    projects = tmp_path / "projects"
    # a directory named *.jsonl makes read_text raise IsADirectoryError (an OSError)
    (projects / "myproj" / "bad.jsonl").mkdir(parents=True)
    t = parse_transcript("", subagent_projects_dir=projects)
    assert len(t.warnings) == 1
    assert "subagent transcripts unavailable" in t.warnings[0]
```

- [ ] **Step 2: Run the new tests to verify they fail**

Run: `uv run --package claude-code-evals pytest tests/test_transcript.py -v -k "subagent_jsonl or projects_dir or unreadable"`
Expected: FAIL — `TypeError: parse_transcript() got an unexpected keyword argument 'subagent_projects_dir'`.

- [ ] **Step 3: Implement the merge**

In `packages/claude-code-evals/src/claude_code_evals/transcript.py`:

Add to the imports:

```python
from pathlib import Path
```

Add a `warnings` field to `Transcript` (after `final_assistant_text`):

```python
    warnings: list[str] = field(default_factory=list)
```

Change the `parse_transcript` signature and add the merge call at the end (just before `return t`):

```python
def parse_transcript(jsonl: str, *, subagent_projects_dir: Path | None = None) -> Transcript:
```

```python
    t.final_assistant_text = last_assistant_text
    if subagent_projects_dir is not None:
        _merge_subagent_calls(t, subagent_projects_dir)
    return t
```

Add at the bottom of the module (above `extract_tool_calls_from_jsonl`):

```python
def _merge_subagent_calls(t: Transcript, projects_dir: Path) -> None:
    """Merge tool calls from subagent (sidechain) transcript JSONLs under projects_dir.

    Missing/unreadable files degrade to main-stream-only capture with a warning;
    merged calls never touch tool_call_counts/files_* so metrics.json is unaffected.
    """
    if not projects_dir.is_dir():
        if t.subagent_dispatches:
            t.warnings.append(f"subagent transcripts unavailable: {projects_dir} does not exist")
        return

    seen_ids = {c.tool_use_id for c in t.tool_calls if c.tool_use_id}
    for jsonl_path in sorted(projects_dir.glob("*/*.jsonl")):
        try:
            text = jsonl_path.read_text()
        except OSError as exc:
            t.warnings.append(f"subagent transcripts unavailable: {jsonl_path.name}: {exc}")
            continue
        for line in text.splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                entry = json.loads(line)
            except json.JSONDecodeError:
                continue
            if entry.get("type") != "assistant" or entry.get("isSidechain") is not True:
                continue
            parent_id = entry.get("parent_tool_use_id") or entry.get("parentToolUseId") or None
            msg = entry.get("message") or {}
            for block in msg.get("content") or []:
                if block.get("type") != "tool_use":
                    continue
                block_id = block.get("id", "")
                if block_id and block_id in seen_ids:
                    continue
                seen_ids.add(block_id)
                inp = block.get("input") or {}
                t.tool_calls.append(
                    ToolCallEvent(
                        tool=block.get("name", ""),
                        input_keys=list(inp.keys()),
                        input=inp,
                        tool_use_id=block_id,
                        seq=len(t.tool_calls),
                        parent_tool_use_id=parent_id,
                        source="subagent",
                        feed="jsonl",
                    )
                )
```

- [ ] **Step 4: Run the full transcript test file**

Run: `uv run --package claude-code-evals pytest tests/test_transcript.py -v`
Expected: ALL PASS.

- [ ] **Step 5: Commit**

```bash
git add packages/claude-code-evals/src/claude_code_evals/transcript.py packages/claude-code-evals/tests/test_transcript.py
git commit -m "feat(claude-code-evals): merge subagent transcript JSONLs into tool_calls with warnings"
```

---

### Task 3: Keep `metrics.json` and rubric judge input byte-identical

**Files:**
- Modify: `packages/claude-code-evals/src/claude_code_evals/metrics.py:10-14`
- Modify: `packages/claude-code-evals/src/claude_code_evals/verify/rubric.py:68-75`
- Test: `packages/claude-code-evals/tests/test_metrics.py`

`tool_call_counts`, `files_*`, `subagent_dispatches`, `skill_invocations` are already safe (Task 2 never touches them for merged calls). The two remaining consumers that iterate `transcript.tool_calls` must filter to `feed == "stream"`.

- [ ] **Step 1: Write the failing test**

Append to `packages/claude-code-evals/tests/test_metrics.py` (check its existing imports; add any of these that are missing):

```python
from claude_code_evals.metrics import compute_metrics
from claude_code_evals.transcript import ToolCallEvent, Transcript


def test_jsonl_merged_calls_do_not_change_before_first_edit():
    # A jsonl-merged Edit positioned before the stream calls must be invisible to
    # the metric: the stream view is [Read] (no edit) → value 1 (stream-call count).
    # Unfiltered code would return 0 (index of the jsonl Edit).
    t = Transcript()
    t.tool_calls = [
        ToolCallEvent(tool="Edit", input_keys=["file_path"], seq=0, source="subagent", feed="jsonl"),
        ToolCallEvent(tool="Read", input_keys=["file_path"], seq=1, feed="stream"),
    ]
    metrics = compute_metrics(t, {"success": True})
    assert metrics["tool_calls_before_first_edit"] == 1

    # With a stream edit present, the metric counts stream calls before it: [Read, Edit] → 1.
    t2 = Transcript()
    t2.tool_calls = [
        ToolCallEvent(tool="Read", input_keys=["file_path"], seq=0, feed="stream"),
        ToolCallEvent(tool="Edit", input_keys=["file_path"], seq=1, source="subagent", feed="jsonl"),
        ToolCallEvent(tool="Edit", input_keys=["file_path"], seq=2, feed="stream"),
    ]
    metrics2 = compute_metrics(t2, {"success": True})
    assert metrics2["tool_calls_before_first_edit"] == 1
```

(Task 2 always appends jsonl calls after stream calls, so the first sub-case is artificial — but it is the clean way to pin the filter behavior.)

- [ ] **Step 2: Run it to verify it fails**

Run: `uv run --package claude-code-evals pytest tests/test_metrics.py -v -k jsonl_merged`
Expected: FAIL — the first assertion fails (got `0`, the index of the jsonl Edit).

- [ ] **Step 3: Implement the filters**

In `packages/claude-code-evals/src/claude_code_evals/metrics.py`, replace `_tool_calls_before_first_edit`:

```python
def _tool_calls_before_first_edit(transcript: Transcript) -> int:
    stream_calls = [c for c in transcript.tool_calls if c.feed == "stream"]
    for i, call in enumerate(stream_calls):
        if call.tool in _EDIT_TOOLS:
            return i
    return len(stream_calls)
```

In `packages/claude-code-evals/src/claude_code_evals/verify/rubric.py`, in `_build_tool_summary`, add the filter as the first line of the loop body:

```python
    def _build_tool_summary(self) -> str:
        lines = []
        for call in self._transcript.tool_calls:
            if call.feed != "stream":
                continue
            if call.tool in _SCRUBBED_TOOLS:
                lines.append(f"{call.tool}({', '.join(call.input_keys)})")
            else:
                lines.append(call.tool)
        return "\n".join(lines)
```

- [ ] **Step 4: Run metrics + verify test files**

Run: `uv run --package claude-code-evals pytest tests/test_metrics.py tests/test_verify.py -v`
Expected: ALL PASS.

- [ ] **Step 5: Commit**

```bash
git add packages/claude-code-evals/src/claude_code_evals/metrics.py packages/claude-code-evals/src/claude_code_evals/verify/rubric.py packages/claude-code-evals/tests/test_metrics.py
git commit -m "fix(claude-code-evals): keep metrics and rubric input on stream-feed calls only"
```

---

### Task 4: `tools.json` serializer with truncation

**Files:**
- Create: `packages/claude-code-evals/src/claude_code_evals/tools_log.py`
- Test: `packages/claude-code-evals/tests/test_tools_log.py`

- [ ] **Step 1: Write the failing tests**

Create `packages/claude-code-evals/tests/test_tools_log.py`:

```python
from __future__ import annotations

import json

from claude_code_evals.tools_log import TRUNCATE_CHARS, render_tools_json
from claude_code_evals.transcript import ToolCallEvent, Transcript


def _transcript(*calls: ToolCallEvent, warnings: list[str] | None = None) -> Transcript:
    t = Transcript()
    t.tool_calls = list(calls)
    t.warnings = warnings or []
    return t


def _call(tool: str = "Read", inp: dict | None = None, **kw) -> ToolCallEvent:
    inp = inp if inp is not None else {"file_path": "README.md"}
    return ToolCallEvent(tool=tool, input_keys=list(inp.keys()), input=inp, **kw)


def test_render_shape():
    t = _transcript(
        _call(seq=0),
        _call(
            tool="Write",
            inp={"file_path": "out.md", "content": "x"},
            seq=1,
            source="subagent",
            parent_tool_use_id="toolu_01abc",
        ),
    )
    doc = render_tools_json(t)
    assert doc["total_calls"] == 2
    assert doc["warnings"] == []
    assert doc["calls"][0] == {
        "seq": 0,
        "tool": "Read",
        "source": "main",
        "parent_tool_use_id": None,
        "input": {"file_path": "README.md"},
    }
    assert doc["calls"][1]["source"] == "subagent"
    assert doc["calls"][1]["parent_tool_use_id"] == "toolu_01abc"
    json.dumps(doc)  # must be JSON-serializable


def test_string_truncation_boundary():
    under = "a" * (TRUNCATE_CHARS - 1)
    at = "a" * TRUNCATE_CHARS
    over = "a" * (TRUNCATE_CHARS + 1)
    t = _transcript(_call(inp={"u": under, "a": at, "o": over}))
    out = render_tools_json(t)["calls"][0]["input"]
    assert out["u"] == under
    assert out["a"] == at
    assert out["o"] == "a" * TRUNCATE_CHARS + f"…[truncated, {TRUNCATE_CHARS + 1} chars total]"


def test_small_nested_value_stays_native():
    t = _transcript(_call(tool="mcp__x__y", inp={"opts": {"depth": 2}, "n": 7}))
    out = render_tools_json(t)["calls"][0]["input"]
    assert out["opts"] == {"depth": 2}
    assert out["n"] == 7


def test_large_nested_value_serialized_and_truncated():
    big = {"items": ["x" * 50] * 20}  # json.dumps well over the cap
    rendered = json.dumps(big)
    assert len(rendered) > TRUNCATE_CHARS  # sanity
    t = _transcript(_call(inp={"payload": big}))
    out = render_tools_json(t)["calls"][0]["input"]["payload"]
    assert isinstance(out, str)
    assert out.startswith(rendered[:TRUNCATE_CHARS])
    assert out.endswith(f"…[truncated, {len(rendered)} chars total]")


def test_warnings_passed_through():
    t = _transcript(warnings=["subagent transcripts unavailable: boom"])
    assert render_tools_json(t)["warnings"] == ["subagent transcripts unavailable: boom"]
```

- [ ] **Step 2: Run to verify failure**

Run: `uv run --package claude-code-evals pytest tests/test_tools_log.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'claude_code_evals.tools_log'`.

- [ ] **Step 3: Implement the serializer**

Create `packages/claude-code-evals/src/claude_code_evals/tools_log.py`:

```python
"""Render a Transcript's tool calls as the tools.json artifact (truncated copy)."""

from __future__ import annotations

import json

from claude_code_evals.transcript import Transcript

TRUNCATE_CHARS = 500


def _truncate(s: str) -> str:
    if len(s) <= TRUNCATE_CHARS:
        return s
    return s[:TRUNCATE_CHARS] + f"…[truncated, {len(s)} chars total]"


def _serialize_value(value: object) -> object:
    if isinstance(value, str):
        return _truncate(value)
    rendered = json.dumps(value, default=str)
    if len(rendered) <= TRUNCATE_CHARS:
        return value
    return _truncate(rendered)


def render_tools_json(t: Transcript) -> dict:
    """Build the tools.json document. Truncation applies here only —
    assertions run against the in-memory Transcript with full values."""
    return {
        "total_calls": len(t.tool_calls),
        "warnings": list(t.warnings),
        "calls": [
            {
                "seq": c.seq,
                "tool": c.tool,
                "source": c.source,
                "parent_tool_use_id": c.parent_tool_use_id,
                "input": {k: _serialize_value(v) for k, v in c.input.items()},
            }
            for c in t.tool_calls
        ],
    }
```

- [ ] **Step 4: Run to verify pass**

Run: `uv run --package claude-code-evals pytest tests/test_tools_log.py -v`
Expected: ALL PASS.

- [ ] **Step 5: Commit**

```bash
git add packages/claude-code-evals/src/claude_code_evals/tools_log.py packages/claude-code-evals/tests/test_tools_log.py
git commit -m "feat(claude-code-evals): tools.json serializer with 500-char value truncation"
```

---

### Task 5: Schema models — `ToolAssertion`, `OrderStep`, `VerifyEntry kind: tools`

**Files:**
- Modify: `packages/claude-code-evals/src/claude_code_evals/schemas.py`
- Test: `packages/claude-code-evals/tests/test_schemas.py`

- [ ] **Step 1: Write the failing tests**

Append to `packages/claude-code-evals/tests/test_schemas.py` (check existing imports; it already imports from `claude_code_evals.schemas` — add `VerifyEntry`, `ToolAssertion` to that import and `pytest` if missing):

```python
# --- tools verifier schema ---


def test_verify_entry_tools_kind_parses():
    ve = VerifyEntry.model_validate(
        {
            "kind": "tools",
            "assertions": [
                {"tool": "Skill", "params": {"skill": "graph-wiki:scan"}},
                {"tool": "Read", "min_count": 3},
                {"tool": "Write", "params": {"file_path": "wiki/entities/.*"}, "absent": True},
                {
                    "order": [
                        {"tool": "Read", "params": {"file_path": ".*StatusBadge.*"}},
                        {"tool": "Edit", "params": {"file_path": ".*StatusBadge.*"}},
                    ]
                },
                {"tool": "Read", "min_count": 5, "include_subagents": True},
            ],
        }
    )
    assert ve.kind == "tools"
    assert ve.assertions is not None and len(ve.assertions) == 5
    assert ve.assertions[4].include_subagents is True


def test_tools_kind_requires_assertions():
    with pytest.raises(ValueError, match="assertions"):
        VerifyEntry.model_validate({"kind": "tools"})


def test_tools_kind_forbids_path():
    with pytest.raises(ValueError, match="path"):
        VerifyEntry.model_validate(
            {"kind": "tools", "path": "x.sh", "assertions": [{"tool": "Read"}]}
        )


def test_other_kinds_still_require_path():
    with pytest.raises(ValueError, match="path"):
        VerifyEntry.model_validate({"kind": "script"})


def test_other_kinds_forbid_assertions():
    with pytest.raises(ValueError, match="assertions"):
        VerifyEntry.model_validate(
            {"kind": "script", "path": "verify.sh", "assertions": [{"tool": "Read"}]}
        )


def test_invalid_regex_rejected_at_load():
    with pytest.raises(ValueError, match="invalid regex"):
        ToolAssertion.model_validate({"tool": "Read", "params": {"file_path": "([unclosed"}})


def test_invalid_regex_in_order_step_rejected():
    with pytest.raises(ValueError, match="invalid regex"):
        ToolAssertion.model_validate(
            {"order": [{"tool": "Read", "params": {"file_path": "([unclosed"}}]}
        )


def test_order_cannot_combine_with_tool_fields():
    with pytest.raises(ValueError, match="order"):
        ToolAssertion.model_validate({"tool": "Read", "order": [{"tool": "Edit"}]})


def test_assertion_requires_tool_or_order():
    with pytest.raises(ValueError, match="tool or order"):
        ToolAssertion.model_validate({"min_count": 2})


def test_absent_forbids_counts():
    with pytest.raises(ValueError, match="absent"):
        ToolAssertion.model_validate({"tool": "Write", "absent": True, "min_count": 1})


def test_min_count_cannot_exceed_max_count():
    with pytest.raises(ValueError, match="min_count"):
        ToolAssertion.model_validate({"tool": "Bash", "min_count": 5, "max_count": 2})


def test_empty_order_rejected():
    with pytest.raises(ValueError, match="order"):
        ToolAssertion.model_validate({"order": []})


def test_scenario_with_tools_verify_round_trips():
    s = Scenario.model_validate(
        {
            "name": "s",
            "isolation_mode": "fixture",
            "fixture_dir": "/tmp/x",
            "verify": [
                {"kind": "tools", "assertions": [{"tool": "Skill", "params": {"skill": "graph-wiki:scan"}}]}
            ],
        }
    )
    assert s.verify[0].kind == "tools"
```

- [ ] **Step 2: Run to verify failure**

Run: `uv run --package claude-code-evals pytest tests/test_schemas.py -v -k "tools or regex or order or absent or min_count"`
Expected: FAIL — `ImportError: cannot import name 'ToolAssertion'` (fix the import line first if it errors at collection, then the tests fail on validation behavior).

- [ ] **Step 3: Implement the models**

In `packages/claude-code-evals/src/claude_code_evals/schemas.py`:

Add `import re` to the imports (stdlib group, above `yaml`).

Insert immediately **above** the `VerifyEntry` class:

```python
class OrderStep(BaseModel):
    """One step of an ordering assertion: a tool plus param regexes."""

    model_config = ConfigDict(extra="forbid")

    tool: str
    params: dict[str, str] = Field(default_factory=dict)

    @field_validator("params")
    @classmethod
    def _compile_regexes(cls, v: dict[str, str]) -> dict[str, str]:
        for name, pattern in v.items():
            try:
                re.compile(pattern)
            except re.error as exc:
                raise ValueError(f"invalid regex for param {name!r}: {exc}") from exc
        return v


class ToolAssertion(BaseModel):
    """One tool-call assertion: presence/count/absence on a tool, or an ordering constraint."""

    model_config = ConfigDict(extra="forbid")

    tool: str | None = None
    params: dict[str, str] = Field(default_factory=dict)
    min_count: int | None = Field(default=None, ge=0)
    max_count: int | None = Field(default=None, ge=0)
    absent: bool = False
    include_subagents: bool = False
    order: list[OrderStep] | None = None

    @field_validator("params")
    @classmethod
    def _compile_regexes(cls, v: dict[str, str]) -> dict[str, str]:
        for name, pattern in v.items():
            try:
                re.compile(pattern)
            except re.error as exc:
                raise ValueError(f"invalid regex for param {name!r}: {exc}") from exc
        return v

    @model_validator(mode="after")
    def _check_shape(self) -> "ToolAssertion":
        if self.order is not None:
            if (
                self.tool is not None
                or self.params
                or self.min_count is not None
                or self.max_count is not None
                or self.absent
            ):
                raise ValueError("order assertions cannot combine with tool/params/counts/absent")
            if not self.order:
                raise ValueError("order must contain at least one step")
        else:
            if self.tool is None:
                raise ValueError("assertion requires either tool or order")
            if self.absent and (self.min_count is not None or self.max_count is not None):
                raise ValueError("absent: true cannot combine with min_count/max_count")
            if self.min_count is not None and self.max_count is not None and self.min_count > self.max_count:
                raise ValueError("min_count cannot exceed max_count")
        return self
```

Replace the `VerifyEntry` class:

```python
class VerifyEntry(BaseModel):
    """A single verification step: script, golden patch, LLM-judged rubric, or tool-call assertions."""

    model_config = ConfigDict(extra="forbid")

    kind: Literal["script", "golden", "rubric", "tools"]
    path: str | None = None
    judge: str | None = None
    pass_threshold: float | None = None
    assertions: list[ToolAssertion] | None = None

    @model_validator(mode="after")
    def _check_kind_fields(self) -> "VerifyEntry":
        if self.kind == "tools":
            if not self.assertions:
                raise ValueError("kind: tools requires assertions")
            if self.path is not None:
                raise ValueError("kind: tools does not use path")
        else:
            if self.path is None:
                raise ValueError(f"kind: {self.kind} requires path")
            if self.assertions is not None:
                raise ValueError("assertions are only valid for kind: tools")
        return self
```

- [ ] **Step 4: Run the whole schema test file**

Run: `uv run --package claude-code-evals pytest tests/test_schemas.py -v`
Expected: ALL PASS (new tests plus pre-existing `VerifyEntry` usages — every existing fixture passes `path`, so the validator keeps them green).

- [ ] **Step 5: Commit**

```bash
git add packages/claude-code-evals/src/claude_code_evals/schemas.py packages/claude-code-evals/tests/test_schemas.py
git commit -m "feat(claude-code-evals): ToolAssertion/OrderStep models and kind:tools VerifyEntry"
```

---

### Task 6: Matching semantics in `verify/tools.py`

**Files:**
- Create: `packages/claude-code-evals/src/claude_code_evals/verify/tools.py`
- Test: `packages/claude-code-evals/tests/test_verify_tools.py`

This task implements and tests the pure matching functions; Task 7 adds the `ToolsVerifier` class on top in the same module.

- [ ] **Step 1: Write the failing tests**

Create `packages/claude-code-evals/tests/test_verify_tools.py`:

```python
from __future__ import annotations

from claude_code_evals.schemas import ToolAssertion
from claude_code_evals.transcript import ToolCallEvent, Transcript
from claude_code_evals.verify.tools import _check_assertion


def _call(tool: str, inp: dict | None = None, *, seq: int = 0, source: str = "main") -> ToolCallEvent:
    inp = inp or {}
    return ToolCallEvent(tool=tool, input_keys=list(inp.keys()), input=inp, seq=seq, source=source)


def _transcript(*calls: ToolCallEvent, warnings: list[str] | None = None) -> Transcript:
    t = Transcript()
    t.tool_calls = list(calls)
    t.warnings = warnings or []
    return t


def _a(**kw) -> ToolAssertion:
    return ToolAssertion.model_validate(kw)


def test_presence_pass_and_fail():
    t = _transcript(_call("Skill", {"skill": "graph-wiki:scan"}))
    assert _check_assertion(_a(tool="Skill"), t)[0] is True
    assert _check_assertion(_a(tool="Edit"), t)[0] is False


def test_multi_param_and_on_same_call():
    t = _transcript(
        _call("Edit", {"file_path": "a.py", "old_string": "x"}, seq=0),
        _call("Edit", {"file_path": "b.py", "old_string": "y"}, seq=1),
    )
    # both regexes must hit the SAME call
    ok, _ = _check_assertion(_a(tool="Edit", params={"file_path": "a", "old_string": "x"}), t)
    assert ok is True
    ok, _ = _check_assertion(_a(tool="Edit", params={"file_path": "a", "old_string": "y"}), t)
    assert ok is False


def test_re_search_is_unanchored():
    t = _transcript(_call("Read", {"file_path": "deep/wiki/entities/pkg.md"}))
    assert _check_assertion(_a(tool="Read", params={"file_path": "wiki/entities/.*"}), t)[0] is True
    # anchoring works when requested
    assert _check_assertion(_a(tool="Read", params={"file_path": "^wiki/"}), t)[0] is False


def test_missing_param_means_no_match():
    t = _transcript(_call("Read", {"file_path": "a.md"}))
    assert _check_assertion(_a(tool="Read", params={"pattern": ".*"}), t)[0] is False


def test_non_string_param_json_serialized():
    t = _transcript(_call("Agent", {"run_in_background": True, "depth": 3}))
    assert _check_assertion(_a(tool="Agent", params={"run_in_background": "true"}), t)[0] is True
    assert _check_assertion(_a(tool="Agent", params={"depth": "^3$"}), t)[0] is True


def test_min_and_max_counts():
    t = _transcript(*[_call("Read", {"file_path": f"{i}.md"}, seq=i) for i in range(3)])
    assert _check_assertion(_a(tool="Read", min_count=3), t)[0] is True
    assert _check_assertion(_a(tool="Read", min_count=4), t)[0] is False
    assert _check_assertion(_a(tool="Read", max_count=3), t)[0] is True
    assert _check_assertion(_a(tool="Read", max_count=2), t)[0] is False
    assert _check_assertion(_a(tool="Read", min_count=1, max_count=3), t)[0] is True


def test_absent():
    t = _transcript(_call("Write", {"file_path": "wiki/entities/p.md"}))
    ok, reason = _check_assertion(
        _a(tool="Write", params={"file_path": "wiki/entities/.*"}, absent=True), t
    )
    assert ok is False
    assert "expected no" in reason
    ok, _ = _check_assertion(_a(tool="Write", params={"file_path": "^src/"}, absent=True), t)
    assert ok is True


def test_order_pass():
    t = _transcript(
        _call("Read", {"file_path": "src/StatusBadge.tsx"}, seq=0),
        _call("Bash", {"command": "ls"}, seq=1),
        _call("Edit", {"file_path": "src/StatusBadge.tsx"}, seq=2),
    )
    a = _a(order=[
        {"tool": "Read", "params": {"file_path": "StatusBadge"}},
        {"tool": "Edit", "params": {"file_path": "StatusBadge"}},
    ])
    assert _check_assertion(a, t)[0] is True


def test_order_fail_when_reversed():
    t = _transcript(
        _call("Edit", {"file_path": "src/StatusBadge.tsx"}, seq=0),
        _call("Read", {"file_path": "src/StatusBadge.tsx"}, seq=1),
    )
    a = _a(order=[
        {"tool": "Read", "params": {"file_path": "StatusBadge"}},
        {"tool": "Edit", "params": {"file_path": "StatusBadge"}},
    ])
    ok, reason = _check_assertion(a, t)
    assert ok is False
    assert "step 2" in reason


def test_order_with_interleaved_decoys():
    # decoy Edits on OTHER files between the real steps must not satisfy step 2
    t = _transcript(
        _call("Read", {"file_path": "src/StatusBadge.tsx"}, seq=0),
        _call("Edit", {"file_path": "src/Other.tsx"}, seq=1),
        _call("Edit", {"file_path": "src/StatusBadge.tsx"}, seq=2),
    )
    a = _a(order=[
        {"tool": "Read", "params": {"file_path": "StatusBadge"}},
        {"tool": "Edit", "params": {"file_path": "StatusBadge"}},
    ])
    assert _check_assertion(a, t)[0] is True
    t2 = _transcript(
        _call("Read", {"file_path": "src/StatusBadge.tsx"}, seq=0),
        _call("Edit", {"file_path": "src/Other.tsx"}, seq=1),
    )
    assert _check_assertion(a, t2)[0] is False


def test_subagent_calls_excluded_by_default():
    t = _transcript(
        _call("Read", {"file_path": "main.md"}, seq=0, source="main"),
        _call("Read", {"file_path": "sub.md"}, seq=1, source="subagent"),
    )
    assert _check_assertion(_a(tool="Read", min_count=2), t)[0] is False
    assert _check_assertion(_a(tool="Read", min_count=2, include_subagents=True), t)[0] is True


def test_include_subagents_fails_with_warning_when_data_unavailable():
    t = _transcript(
        _call("Read", {"file_path": "main.md"}, seq=0),
        warnings=["subagent transcripts unavailable: projects dir missing"],
    )
    ok, reason = _check_assertion(_a(tool="Read", min_count=1, include_subagents=True), t)
    assert ok is False
    assert "subagent transcripts unavailable" in reason


def test_presence_failure_reports_near_miss():
    t = _transcript(_call("Skill", {"skill": "graph-wiki:lint"}))
    ok, reason = _check_assertion(_a(tool="Skill", params={"skill": "graph-wiki:scan"}), t)
    assert ok is False
    assert "graph-wiki:lint" in reason  # nearest near-miss quoted
```

- [ ] **Step 2: Run to verify failure**

Run: `uv run --package claude-code-evals pytest tests/test_verify_tools.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'claude_code_evals.verify.tools'`.

- [ ] **Step 3: Implement the matcher**

Create `packages/claude-code-evals/src/claude_code_evals/verify/tools.py`:

```python
"""ToolsVerifier: pure-Python tool-call assertions against the in-memory Transcript."""

from __future__ import annotations

import json
import re

from claude_code_evals.schemas import ToolAssertion
from claude_code_evals.transcript import ToolCallEvent, Transcript


def _param_value(call: ToolCallEvent, name: str) -> str | None:
    """The call's value for a param as a string, or None if the param is absent."""
    if name not in call.input:
        return None
    value = call.input[name]
    return value if isinstance(value, str) else json.dumps(value)


def _call_matches(call: ToolCallEvent, tool: str, params: dict[str, str]) -> bool:
    if call.tool != tool:
        return False
    for name, pattern in params.items():
        value = _param_value(call, name)
        if value is None or re.search(pattern, value) is None:
            return False
    return True


def _scoped_calls(transcript: Transcript, include_subagents: bool) -> list[ToolCallEvent]:
    calls = sorted(transcript.tool_calls, key=lambda c: c.seq)
    if include_subagents:
        return calls
    return [c for c in calls if c.source == "main"]


def _render_target(tool: str, params: dict[str, str]) -> str:
    if not params:
        return tool
    inner = ", ".join(f"{k}=~{v}" for k, v in params.items())
    return f"{tool}({inner})"


def _nearest_miss(assertion: ToolAssertion, calls: list[ToolCallEvent]) -> str:
    """Same-tool call whose params best matched, rendered for the failure reason."""
    assert assertion.tool is not None
    same_tool = [c for c in calls if c.tool == assertion.tool]
    if not same_tool or not assertion.params:
        return ""

    def matched_params(c: ToolCallEvent) -> int:
        return sum(
            1
            for name, pattern in assertion.params.items()
            if (v := _param_value(c, name)) is not None and re.search(pattern, v)
        )

    best = max(same_tool, key=matched_params)
    shown = ", ".join(f"{k}={_param_value(best, k)!r}" for k in assertion.params)
    return f"seq {best.seq} {assertion.tool} with {shown}"


def _check_counts(assertion: ToolAssertion, calls: list[ToolCallEvent]) -> tuple[bool, str]:
    assert assertion.tool is not None
    matches = [c for c in calls if _call_matches(c, assertion.tool, assertion.params)]
    n = len(matches)
    target = _render_target(assertion.tool, assertion.params)

    if assertion.absent:
        if n == 0:
            return True, ""
        return False, f"expected no {target} calls, found {n} (first at seq {matches[0].seq})"

    min_count = assertion.min_count
    if min_count is None and assertion.max_count is None:
        min_count = 1  # a bare assertion means "called at least once"

    if min_count is not None and n < min_count:
        reason = f"expected {target} >={min_count} time(s), found {n}"
        near = _nearest_miss(assertion, calls)
        if near:
            reason += f"; nearest miss: {near}"
        return False, reason
    if assertion.max_count is not None and n > assertion.max_count:
        return False, f"expected {target} <={assertion.max_count} time(s), found {n}"
    return True, ""


def _check_order(assertion: ToolAssertion, calls: list[ToolCallEvent]) -> tuple[bool, str]:
    assert assertion.order is not None
    idx = 0
    for step_num, step in enumerate(assertion.order, start=1):
        while idx < len(calls) and not _call_matches(calls[idx], step.tool, step.params):
            idx += 1
        if idx == len(calls):
            return (
                False,
                f"order: step {step_num} ({_render_target(step.tool, step.params)}) "
                "not found after the preceding steps",
            )
        idx += 1
    return True, ""


def _check_assertion(assertion: ToolAssertion, transcript: Transcript) -> tuple[bool, str]:
    if assertion.include_subagents:
        subagent_warnings = [w for w in transcript.warnings if "subagent transcripts unavailable" in w]
        has_subagent_calls = any(c.source == "subagent" for c in transcript.tool_calls)
        if subagent_warnings and not has_subagent_calls:
            return False, f"include_subagents requested but {subagent_warnings[0]}"
    calls = _scoped_calls(transcript, assertion.include_subagents)
    if assertion.order is not None:
        return _check_order(assertion, calls)
    return _check_counts(assertion, calls)
```

- [ ] **Step 4: Run to verify pass**

Run: `uv run --package claude-code-evals pytest tests/test_verify_tools.py -v`
Expected: ALL PASS.

- [ ] **Step 5: Commit**

```bash
git add packages/claude-code-evals/src/claude_code_evals/verify/tools.py packages/claude-code-evals/tests/test_verify_tools.py
git commit -m "feat(claude-code-evals): tool-call assertion matching semantics"
```

---

### Task 7: `ToolsVerifier` class

**Files:**
- Modify: `packages/claude-code-evals/src/claude_code_evals/verify/tools.py`
- Test: `packages/claude-code-evals/tests/test_verify_tools.py`

- [ ] **Step 1: Write the failing tests**

Append to `packages/claude-code-evals/tests/test_verify_tools.py` (and add the imports at the top of the file):

```python
from deepeval.test_case import LLMTestCase

from claude_code_evals.verify.base import VerifierBase
from claude_code_evals.verify.tools import ToolsVerifier
```

```python
# --- ToolsVerifier ---


def _tc() -> LLMTestCase:
    return LLMTestCase(input="prompt", actual_output="output")


def test_verifier_all_pass():
    t = _transcript(_call("Read", {"file_path": "a.md"}))
    v = ToolsVerifier(assertions=[_a(tool="Read")], transcript=t)
    score = v.measure(_tc())
    assert score == 1.0
    assert v.success is True
    assert "passed" in v.reason


def test_verifier_score_is_fraction_and_passed_requires_all():
    t = _transcript(_call("Read", {"file_path": "a.md"}))
    v = ToolsVerifier(
        assertions=[_a(tool="Read"), _a(tool="Edit"), _a(tool="Read", max_count=1)],
        transcript=t,
    )
    score = v.measure(_tc())
    assert score == pytest.approx(2 / 3)
    assert v.success is False  # all must pass


def test_verifier_reason_lists_each_failure():
    t = _transcript(_call("Skill", {"skill": "graph-wiki:lint"}))
    v = ToolsVerifier(
        assertions=[
            _a(tool="Skill", params={"skill": "graph-wiki:scan"}),
            _a(tool="Edit"),
        ],
        transcript=t,
    )
    v.measure(_tc())
    assert "Skill(skill=~graph-wiki:scan)" in v.reason
    assert "graph-wiki:lint" in v.reason  # near-miss rendered
    assert "Edit" in v.reason


def test_verifier_is_a_verifier_base():
    assert issubclass(ToolsVerifier, VerifierBase)


def test_verifier_empty_assertions_passes():
    v = ToolsVerifier(assertions=[], transcript=_transcript())
    assert v.measure(_tc()) == 1.0
```

Also add `import pytest` to the file's imports.

- [ ] **Step 2: Run to verify failure**

Run: `uv run --package claude-code-evals pytest tests/test_verify_tools.py -v -k verifier`
Expected: FAIL — `ImportError: cannot import name 'ToolsVerifier'`.

- [ ] **Step 3: Implement the verifier**

In `packages/claude-code-evals/src/claude_code_evals/verify/tools.py`, add to the imports:

```python
from deepeval.test_case import LLMTestCase

from claude_code_evals.verify.base import VerifierBase
```

Append the class at the bottom:

```python
class ToolsVerifier(VerifierBase):
    """Evaluate tool-call assertions against the parsed Transcript.

    score = fraction of assertions passed; success requires all (threshold 1.0).
    """

    def __init__(self, *, assertions: list[ToolAssertion], transcript: Transcript) -> None:
        super().__init__(threshold=1.0)
        self._assertions = assertions
        self._transcript = transcript

    def measure(self, test_case: LLMTestCase) -> float:  # noqa: ARG002
        failures: list[str] = []
        for i, assertion in enumerate(self._assertions):
            passed, reason = _check_assertion(assertion, self._transcript)
            if not passed:
                failures.append(f"assertion[{i}]: {reason}")
        total = len(self._assertions)
        self.score = (total - len(failures)) / total if total else 1.0
        self.reason = (
            f"all {total} tool assertion(s) passed" if not failures else "; ".join(failures)
        )
        return self.score
```

- [ ] **Step 4: Run to verify pass**

Run: `uv run --package claude-code-evals pytest tests/test_verify_tools.py -v`
Expected: ALL PASS.

- [ ] **Step 5: Commit**

```bash
git add packages/claude-code-evals/src/claude_code_evals/verify/tools.py packages/claude-code-evals/tests/test_verify_tools.py
git commit -m "feat(claude-code-evals): ToolsVerifier with fractional score and near-miss reasons"
```

---

### Task 8: Orchestrator wiring — parse with subagent dir, dispatch verifier, write `tools.json`

**Files:**
- Modify: `packages/claude-code-evals/src/claude_code_evals/orchestrator.py`
- Test: `packages/claude-code-evals/tests/test_orchestrator.py`

- [ ] **Step 1: Write the failing tests**

Append to `packages/claude-code-evals/tests/test_orchestrator.py` (it already has `_make_fixture_scenario`, `_mock_popen`, `FAKE_JSONL`, and the autouse `_oauth_token` fixture):

```python
# --- tools.json artifact + ToolsVerifier dispatch ---

TOOL_CALL_EVENT = json.dumps(
    {
        "type": "assistant",
        "message": {
            "content": [
                {"type": "tool_use", "id": "tu_read", "name": "Read", "input": {"file_path": "README.md"}}
            ]
        },
    }
)
JSONL_WITH_TOOL = f"{TOOL_CALL_EVENT}\n{ASSISTANT_EVENT}\n{RESULT_EVENT}\n"


def test_run_one_writes_tools_json(tmp_path: Path):
    s, c, evals_root = _make_fixture_scenario(tmp_path)
    with patch("subprocess.Popen", return_value=_mock_popen(jsonl=JSONL_WITH_TOOL)):
        result = run_one(s, c, evals_root=evals_root)
    tools_path = result.run_dir / "tools.json"
    assert tools_path.exists()
    doc = json.loads(tools_path.read_text())
    assert doc["total_calls"] == 1
    assert doc["calls"][0]["tool"] == "Read"
    assert doc["calls"][0]["input"] == {"file_path": "README.md"}
    assert doc["calls"][0]["source"] == "main"


def test_run_one_writes_tools_json_even_on_infra_error(tmp_path: Path):
    s, c, evals_root = _make_fixture_scenario(tmp_path)
    crash_proc = _mock_popen(jsonl="garbage\n", returncode=1)
    with patch("subprocess.Popen", return_value=crash_proc):
        result = run_one(s, c, evals_root=evals_root)
    assert (result.run_dir / "tools.json").exists()


def test_run_one_dispatches_tools_verifier(tmp_path: Path):
    s, c, evals_root = _make_fixture_scenario(tmp_path)
    s = s.model_copy(
        update={
            "verify": [
                VerifyEntry.model_validate(
                    {
                        "kind": "tools",
                        "assertions": [
                            {"tool": "Read", "params": {"file_path": "README"}},
                            {"tool": "Write", "absent": True},
                        ],
                    }
                )
            ]
        }
    )
    with patch("subprocess.Popen", return_value=_mock_popen(jsonl=JSONL_WITH_TOOL)):
        result = run_one(s, c, evals_root=evals_root)
    assert result.verify_result["success"] is True
    kinds = [v["kind"] for v in result.verify_result["verifiers"]]
    assert "ToolsVerifier" in kinds


def test_run_one_tools_verifier_failure_reported(tmp_path: Path):
    s, c, evals_root = _make_fixture_scenario(tmp_path)
    s = s.model_copy(
        update={
            "verify": [
                VerifyEntry.model_validate(
                    {"kind": "tools", "assertions": [{"tool": "Edit"}]}
                )
            ]
        }
    )
    with patch("subprocess.Popen", return_value=_mock_popen(jsonl=JSONL_WITH_TOOL)):
        result = run_one(s, c, evals_root=evals_root)
    assert result.verify_result["success"] is False
    outcome = result.verify_result["verifiers"][0]
    assert outcome["passed"] is False
    assert "Edit" in outcome["reason"]
```

Add `VerifyEntry` to the existing `from claude_code_evals.schemas import Config, Scenario` import.

- [ ] **Step 2: Run to verify failure**

Run: `uv run --package claude-code-evals pytest tests/test_orchestrator.py -v -k tools`
Expected: FAIL — `tools.json` missing / no `ToolsVerifier` in kinds.

- [ ] **Step 3: Implement the wiring**

In `packages/claude-code-evals/src/claude_code_evals/orchestrator.py`:

Add imports:

```python
from claude_code_evals.tools_log import render_tools_json
from claude_code_evals.verify.tools import ToolsVerifier
```

Change the parse call (line ~168) to read the per-run subagent transcripts:

```python
        transcript = parse_transcript(raw_jsonl, subagent_projects_dir=iso.cfg_dir / "projects")
```

In the verifier-build loop, `ve.path` is now optional. Handle `kind: tools` first (it has no path) and keep `vpath` a plain `Path` for the other kinds so pyright stays clean — replace:

```python
            for ve in scenario.verify:
                vpath = scenario_dir / ve.path
```

with:

```python
            for ve in scenario.verify:
                if ve.kind == "tools":
                    verifiers.append(ToolsVerifier(assertions=ve.assertions or [], transcript=transcript))
                    continue
                assert ve.path is not None  # enforced by the VerifyEntry validator
                vpath = scenario_dir / ve.path
```

The existing `script`/`golden`/`rubric` branches below are unchanged.

In the artifact-writing block, after the `metrics.json` write, add:

```python
        (run_dir / "tools.json").write_text(json.dumps(render_tools_json(transcript), indent=2))
```

Note: the run-failure gate is untouched — on infra errors verifiers are skipped (including `ToolsVerifier`), but `tools.json` is still written because the artifact block runs unconditionally.

- [ ] **Step 4: Run orchestrator + pytest-plugin tests**

Run: `uv run --package claude-code-evals pytest tests/test_orchestrator.py tests/test_pytest_plugin.py -v`
Expected: ALL PASS (mocked-iso tests set `iso_instance.cfg_dir = tmp_path`; `tmp_path / "projects"` doesn't exist and no Agent calls are in their JSONL, so no warnings fire).

- [ ] **Step 5: Run the entire offline suite**

Run: `uv run --package claude-code-evals pytest -m "not integration"`
Expected: ALL PASS.

- [ ] **Step 6: Commit**

```bash
git add packages/claude-code-evals/src/claude_code_evals/orchestrator.py packages/claude-code-evals/tests/test_orchestrator.py
git commit -m "feat(claude-code-evals): write tools.json artifact and dispatch ToolsVerifier"
```

---

### Task 9: Integration test — real `claude -p` end-to-end (answers the subagent-feed question)

**Files:**
- Create: `packages/claude-code-evals/tests/test_tools_integration.py`

This test requires the real `claude` binary and `CLAUDE_CODE_OAUTH_TOKEN` (a subscription token from `claude setup-token` — bills subscription, not API credits). It is `integration`-marked and skipped by default; run explicitly with `-m integration`.

It also settles the spec's empirical question: whether subagent calls arrive via the main stream (`parent_tool_use_id`-tagged events), the projects JSONLs, or both. The test asserts the invariant that holds either way; the implementer should note the observed answer in the commit message.

- [ ] **Step 1: Write the test**

Create `packages/claude-code-evals/tests/test_tools_integration.py`:

```python
"""Integration: real claude -p run produces tools.json and satisfies a tools assertion.

Requires the claude binary and CLAUDE_CODE_OAUTH_TOKEN. Run with -m integration.
"""

from __future__ import annotations

import json
import os
import shutil
from pathlib import Path

import pytest

from claude_code_evals.orchestrator import run_one
from claude_code_evals.schemas import Config, Scenario

pytestmark = pytest.mark.integration

requires_claude = pytest.mark.skipif(
    shutil.which("claude") is None or not os.environ.get("CLAUDE_CODE_OAUTH_TOKEN"),
    reason="needs claude binary and CLAUDE_CODE_OAUTH_TOKEN",
)


@requires_claude
def test_tools_json_and_assertion_end_to_end(tmp_path: Path):
    fixture = tmp_path / "fixture_src"
    fixture.mkdir()
    (fixture / "README.md").write_text("# Demo\nThe magic word is xyzzy.\n")

    scenario_dir = tmp_path / "evals" / "scenarios" / "tools-it"
    scenario_dir.mkdir(parents=True)
    (scenario_dir / "prompt.md").write_text(
        "Use the Agent tool to dispatch a subagent that reads README.md and reports "
        "the magic word. Then state the magic word yourself."
    )

    scenario = Scenario.model_validate(
        {
            "name": "tools-it",
            "isolation_mode": "fixture",
            "fixture_dir": str(fixture),
            "budgets": {"max_wall_seconds": 240},
            "verify": [
                {
                    "kind": "tools",
                    "assertions": [
                        {"tool": "Agent", "min_count": 1},
                        {"tool": "Read", "params": {"file_path": "README"}, "include_subagents": True},
                    ],
                }
            ],
        }
    )
    config = Config.model_validate({"name": "base"})

    result = run_one(scenario, config, evals_root=tmp_path / "evals")

    assert result.final_status in ("success", "budget_exceeded"), result.error_reason

    tools_path = result.run_dir / "tools.json"
    assert tools_path.exists()
    doc = json.loads(tools_path.read_text())
    assert doc["total_calls"] >= 1
    assert [c["seq"] for c in doc["calls"]] == sorted(c["seq"] for c in doc["calls"])

    # the main agent dispatched a subagent...
    agent_calls = [c for c in doc["calls"] if c["tool"] == "Agent" and c["source"] == "main"]
    assert agent_calls, f"no Agent dispatch found in {[c['tool'] for c in doc['calls']]}"

    # ...so EITHER subagent calls were captured (from stream or JSONL — the
    # empirical question) OR a warning explains their absence. Silence is a bug.
    subagent_calls = [c for c in doc["calls"] if c["source"] == "subagent"]
    assert subagent_calls or doc["warnings"], (
        "Agent dispatched but no subagent calls captured and no warning emitted"
    )

    # record the empirical answer in the test output for the commit message
    feeds = {c.get("parent_tool_use_id") is not None for c in subagent_calls}
    print(f"\nEMPIRICAL: {len(subagent_calls)} subagent calls captured; "
          f"parent_tool_use_id present: {feeds}; warnings: {doc['warnings']}")

    # the tools verifier ran and its outcome is in verify.json
    verify_doc = json.loads((result.run_dir / "verify.json").read_text())
    kinds = [v["kind"] for v in verify_doc["verifiers"]]
    assert "ToolsVerifier" in kinds
```

- [ ] **Step 2: Confirm it is skipped by default**

Run: `uv run --package claude-code-evals pytest tests/test_tools_integration.py`
Expected: `deselected` / skipped (integration marker not selected by default).

- [ ] **Step 3: Run it for real**

Run: `uv run --package claude-code-evals pytest tests/test_tools_integration.py -m integration -v -s`
Expected: PASS, with the `EMPIRICAL:` line printed. If `subagent_calls` is empty but a warning explains why, investigate before moving on: check whether `<cfg_dir>/projects/` contains sidechain JSONLs and whether the main stream events carry `parent_tool_use_id` under a different key — adjust the key handling in `transcript.py` if so (the parser already accepts both `parent_tool_use_id` and `parentToolUseId`).

- [ ] **Step 4: Commit (record the empirical answer)**

```bash
git add packages/claude-code-evals/tests/test_tools_integration.py
git commit -m "test(claude-code-evals): integration run for tools.json + assertions

Empirical subagent feed: <stream | jsonl | both> (observed via EMPIRICAL line)."
```

---

### Task 10: Lint and full-suite verification

**Files:** none new.

- [ ] **Step 1: Lint and format**

Run: `uv run ruff check packages/claude-code-evals && uv run ruff format --check packages/claude-code-evals/src/claude_code_evals/tools_log.py packages/claude-code-evals/src/claude_code_evals/verify/tools.py`
Expected: clean on the new files. (Do NOT run `ruff format` across pre-existing files — the src tree is known format-dirty; only the two new files must be clean.)

- [ ] **Step 2: Full offline suite**

Run: `uv run --package claude-code-evals pytest -m "not integration"`
Expected: ALL PASS.

- [ ] **Step 3: Commit any lint fixups**

```bash
git add -u packages/claude-code-evals
git commit -m "chore(claude-code-evals): lint fixups for tools.json feature"
```

(Skip the commit if there is nothing to fix.)
