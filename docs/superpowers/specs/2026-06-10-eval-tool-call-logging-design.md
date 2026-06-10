# Eval Tool-Call Logging (`tools.json`) and Tool Assertions — Design

**Date:** 2026-06-10
**Status:** Approved
**Package:** `packages/claude-code-evals` (cc-eval)

## Problem

cc-eval currently reports only aggregate tool-call counts (`tool_call_counts` in
`metrics.json`). There is no per-call visibility — which skills were invoked, which
files were read or written, what subagents did, what MCP calls were made — and no
way for a scenario to assert "tool X was called (with these parameters)".

## Goals

1. Every run writes a `tools.json` artifact logging every tool call with its
   parameters, in order, including calls made by subagents (tagged).
2. Scenario configs can declare tool-call assertions: presence, parameter regex
   matching (multiple params ANDed on the same call), negative assertions,
   min/max call counts, and ordering constraints.

Non-goals: changing `metrics.json` (untouched), generic query languages over the
transcript, migrations (per repo policy — no migrations before v2.0).

## Architecture

Two halves, both inside `claude-code-evals`:

1. **Capture + emission** — `transcript.py` stops discarding tool-call inputs;
   the orchestrator serializes them to `<run_dir>/tools.json` next to
   `metrics.json`.
2. **Assertions** — a fourth verifier kind `tools` (joining `script`, `golden`,
   `rubric`), declared inline in `scenario.yaml`, evaluated in pure Python by a
   new `ToolsVerifier(VerifierBase)` against the in-memory `Transcript`.

## Capture pipeline

`ToolCallEvent` (`transcript.py`) grows from `(tool, input_keys)` to:

```python
@dataclass
class ToolCallEvent:
    tool: str
    input_keys: list[str]          # kept for backward compat
    input: dict                    # FULL untruncated params (in memory only)
    tool_use_id: str               # the tool_use block id
    seq: int                       # global ordering index across the run
    parent_tool_use_id: str | None # set when the call came from a subagent
    source: str                    # "main" | "subagent"
```

`parse_transcript()` already walks every `tool_use` block in `assistant` events;
it simply keeps `block["input"]` instead of only its keys.

**Subagent calls.** The runner invokes `claude -p --output-format stream-json
--verbose`, which tags subagent-originated assistant events with
`parent_tool_use_id`. Where the main stream does not carry nested calls, the
parser additionally reads the subagent transcript JSONLs under the isolated
`CLAUDE_CONFIG_DIR/projects/` (fully controlled per-run, so no leakage from
other sessions). Both feeds merge into one `tool_calls` list ordered by `seq`.
Which feed actually carries the data is pinned down empirically by the first
implementation task (and the integration test); the design works with either or
both.

## `tools.json` format

Written by the orchestrator (alongside `metrics.json`, `verify.json`, etc.)
whenever a transcript exists — including partial transcripts from budget-killed
runs, since visibility matters most when runs go sideways.

```json
{
  "total_calls": 43,
  "warnings": [],
  "calls": [
    {
      "seq": 0,
      "tool": "Skill",
      "source": "main",
      "parent_tool_use_id": null,
      "input": {"skill": "graph-wiki:scan"}
    },
    {
      "seq": 7,
      "tool": "Write",
      "source": "subagent",
      "parent_tool_use_id": "toolu_01abc...",
      "input": {
        "file_path": "wiki/entities/pkg-foo.md",
        "content": "---\nkind: package…[truncated, 14302 chars total]"
      }
    }
  ]
}
```

**Truncation applies only at serialization.** Every string value is capped at
500 chars with a `…[truncated, N chars total]` suffix; non-string values
(dicts, lists, numbers — e.g. nested MCP inputs) are JSON-serialized then capped
the same way. Assertions never see truncated data — they run against the
in-memory `Transcript`. `transcript.json` remains the verbatim archive.

## Assertion config

`VerifyEntry` (`schemas.py`) gains `kind: tools`. For this kind, `path` is not
used and `assertions` is required (a model validator enforces this and the
inverse for the other kinds — they keep requiring `path` and forbidding
`assertions`).

```yaml
verify:
  - kind: tools
    assertions:
      # presence: tool called, all param regexes match on the SAME call
      - tool: Skill
        params: {skill: "graph-wiki:scan"}

      # count constraints (either or both)
      - tool: Read
        min_count: 3
      - tool: Bash
        max_count: 10

      # negative: no call matches
      - tool: Write
        params: {file_path: "wiki/entities/.*"}
        absent: true

      # ordering: each step matched in sequence
      - order:
          - {tool: Read, params: {file_path: ".*StatusBadge.*"}}
          - {tool: Edit, params: {file_path: ".*StatusBadge.*"}}

      # opt into counting subagent calls for this assertion only
      - tool: Read
        min_count: 5
        include_subagents: true
```

Pydantic models: `ToolAssertion` with fields `tool`, `params: dict[str, str]`,
`min_count`, `max_count`, `absent: bool = False`,
`include_subagents: bool = False`, `order: list[OrderStep]`. An entry sets
**either** the `tool`-style fields **or** `order`, never both
(validator-enforced). Regexes are compiled with `re.compile` at scenario-load
time so a bad pattern fails before any Claude spend.

## Matching semantics

- A call matches when `call.tool == assertion.tool` **and** every `params`
  regex matches that call's value for the named param, using `re.search`
  (unanchored — `"wiki/entities/.*"` matches anywhere in the path; use `^...$`
  to anchor).
- Param values that aren't strings are JSON-serialized before matching. A param
  named in the assertion but missing from the call means no match.
- Defaults: `absent: false`; `min_count: 1` when neither count is given (a bare
  assertion means "called at least once"). `absent: true` is sugar for
  `max_count: 0` and forbids combining with min/max counts.
- Scope: only `source == "main"` calls are considered unless
  `include_subagents: true`.
- Ordering: greedy left-to-right scan over `seq` — find the first call matching
  step 1, then the first call after it matching step 2, etc. Passes iff all
  steps are consumed.

## Verifier

`ToolsVerifier(VerifierBase)` in `verify/tools.py`, constructed in the
orchestrator's verifier dispatch loop with the parsed `Transcript`.

- Score = fraction of assertions passed; `passed` requires all.
- `reason` lists each failed assertion with a human-readable rendering
  ("expected Skill(skill=~graph-wiki:scan) ≥1 time, found 0") plus, for
  presence failures, the nearest near-miss (same tool, params that didn't
  match).
- Results land in `verify.json` like every other verifier; the pytest plugin
  (`assert_scenario`) picks it up for free since it subclasses `VerifierBase`.

## Error handling

- **Subagent transcript problems are non-fatal.** Missing/unreadable/malformed
  JSONLs degrade to main-stream-only capture; `tools.json` gets a top-level
  `warnings` entry (`"subagent transcripts unavailable: <detail>"`) so silence
  never masquerades as "no subagent calls". An assertion with
  `include_subagents: true` fails (not errors) if subagent data was wanted but
  unavailable, quoting the warning in its reason.
- **Config errors fail fast at load.** Invalid regex, `order` combined with
  `tool`, `absent` combined with counts, `min_count > max_count`, and
  `kind: tools` without `assertions` are Pydantic validation errors raised when
  `scenario.yaml` is parsed — before isolation setup or any Claude spend.
- **Run-failure gating matches existing behavior.** The orchestrator already
  skips verifiers when the run produced nothing to verify; `ToolsVerifier`
  follows the same gate. `tools.json` is still written whenever a transcript
  exists.
- **`metrics.json` is untouched** — `tool_call_counts` stays as-is; no consumer
  of existing artifacts changes.

## Testing

All offline-fast unless noted; run via `uv run --package claude-code-evals pytest`.

1. **Parser**: canned stream-json fixtures → full `input` captured, `seq`
   ordering, `parent_tool_use_id`/`source` tagging, subagent-JSONL merge,
   malformed-line resilience.
2. **Serializer**: truncation at the 500-char boundary (under/at/over), nested
   non-string values, marker format, warnings field.
3. **Matcher**: one test per semantic rule above — presence, multi-param AND,
   `re.search` unanchoredness, missing param ⇒ no match, non-string
   JSON-serialization, min/max counts, `absent`, ordering (pass, fail,
   interleaved decoys), `include_subagents` scoping.
4. **Schema**: each fail-fast validation case rejects with a clear message.
5. **Verifier + orchestrator**: `ToolsVerifier` score/reason aggregation incl.
   near-miss rendering; an orchestrator-level test with a stubbed runner
   asserting `tools.json` lands in the run dir alongside the other artifacts.
6. **One `integration`-marked end-to-end** scenario run exercising a real
   `claude -p` with a tools assertion — opt-in via `-m integration` as usual.
   This is also where the empirical subagent-feed question is answered.

## Decisions log

- Truncate per-value at 500 chars in `tools.json`; assertions use in-memory
  full values (user-selected).
- v1 assertion capabilities: negative assertions, count constraints,
  multi-param AND, ordering (user selected all four).
- Assertions declared inline in `scenario.yaml` as a `verify` entry, not a
  separate file (user-selected).
- Subagent calls included and tagged; assertions default to main-only with
  per-assertion `include_subagents` opt-in; subagent transcripts are examined
  in addition to the main stream (user-selected).
- Approach: fourth verifier kind (`ToolsVerifier`), not a query engine or
  script-verifier convention (user-approved).
