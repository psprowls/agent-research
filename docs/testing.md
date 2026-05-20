# Testing

This document is the **single source of truth** for the integration-gate
convention used across the `deep-agents` monorepo. Every test that invokes real
AWS Bedrock (or any other real-network / real-cost dependency) MUST follow the
canonical pattern documented here so the `tests/test_integration_gate.py`
meta-test passes in CI.

---

## 1. Integration test gate — spec basis

`graph-wiki-agent` and its sibling packages distinguish two categories of test:

- **Unit / mocked tests** — fast, deterministic, run by default in CI. Mock
  Bedrock at the LangChain boundary (`ChatBedrockConverse.ainvoke`).
- **Integration tests** — call real Bedrock (real `boto3`, real HTTPS,
  real cost). These MUST NOT run in CI by default and MUST NOT run on a
  developer machine that hasn't explicitly opted in.

The opt-in mechanism is the `GRAPH_WIKI_RUN_INTEGRATION=1` environment variable.
Without it set, every integration test must be **skipped** with the exact
reason string `"Set GRAPH_WIKI_RUN_INTEGRATION=1 to run real Bedrock invocations"`.
Phase 8 (Host Reliability) established this gate; Phase 16 (D-10) made the
convention enforceable via a grep-gate meta-test.

---

## 2. Internal pattern

Every integration test file MUST:

1. Import `pytest` and `os`.
2. Define (or import) an `INTEGRATION_GATE` decorator using the canonical
   `pytest.mark.skipif` block from §3 below.
3. Apply the decorator at the **function level** (`@INTEGRATION_GATE` above
   the function definition). Do NOT inline `pytest.skip(...)` inside the
   function body — the grep gate looks for the decorator pattern, not the
   inline skip.
4. Optionally also apply `@pytest.mark.integration` for `-m integration`
   filtering when running the suite manually.

If a test file uses a non-canonical pattern (e.g. wraps its own env-var check
in a custom helper), it can still pass the grep gate by adding the comment
marker `# integration-gate-allow` somewhere in the file with a one-line
rationale.

---

## 3. Canonical pattern

```python
INTEGRATION_GATE = pytest.mark.skipif(
    not os.environ.get("GRAPH_WIKI_RUN_INTEGRATION"),
    reason="Set GRAPH_WIKI_RUN_INTEGRATION=1 to run real Bedrock invocations",
)
```

The `reason` string is **verbatim** — `tests/test_integration_gate.py` matches
on the surrounding `pytest.mark.skipif(... GRAPH_WIKI_RUN_INTEGRATION ...)`
shape, but downstream tooling (CI logs, pytest's skipped-test summary) renders
the reason directly to the developer, so it must read clearly.

The canonical home for this block is
`agents/graph-wiki-agent/tests/conftest.py:19-22`. Other test files may either
import it from conftest or redefine it locally (both forms are accepted by the
grep gate).

---

## 4. Inventory of gated test files

| File | Line range | Form |
| ---- | ---------- | ---- |
| `agents/graph-wiki-agent/tests/conftest.py` | 19–22 | canonical home |
| `agents/graph-wiki-agent/tests/integration/test_mcp_e2e.py` | 20–23 | local redefinition |
| `agents/graph-wiki-agent/tests/integration/test_mcp_stdio.py` | 142–143 | local redefinition |
| `agents/graph-wiki-agent/tests/integration/test_query_e2e.py` | 39–42 | local redefinition |
| `agents/graph-wiki-agent/tests/integration/test_bedrock_iam.py` | 31–35 | local redefinition (Phase 16 D-10 refactor — was inline `pytest.skip`) |
| `agents/graph-wiki-agent/tests/integration/test_trace_coverage.py` | 27–30 | local redefinition (Phase 16 TRACE-FU-01 — new) |
| `agents/graph-wiki-agent/tests/integration/test_mcp_cancel.py` | 3–7 | **allowlisted** via `# integration-gate-allow` — mock-only test (no Bedrock cost) intentionally lacks the gate; lives in `integration/` for organizational grouping with other cancel tests |
| `packages/subagent-runtime/tests/integration/test_pool_bedrock.py` | 29–30 | cross-package canonical |

The grep gate at `tests/test_integration_gate.py` walks the repo for every
`**/tests/integration/test_*.py` file and asserts each one matches the
canonical regex OR carries the `# integration-gate-allow` marker.

---

## 5. Future / enforcement

The grep gate (`tests/test_integration_gate.py`) runs on every PR. Adding a
new integration test file requires one of:

1. Following the canonical pattern above (preferred).
2. Adding a `# integration-gate-allow` comment in the new test file with a
   short rationale, and a corresponding row in §4 of this document.

Periodic re-checks: when this document is updated (e.g. a new test file lands
or the canonical pattern evolves), re-run `uv run pytest tests/test_integration_gate.py`
to confirm the gate stays green.

---

*Source: Phase 16 D-10 (MCP-CAN-02) — see `.planning/phases/16-carry-forward-debt-cleanup/16-CONTEXT.md` for the design record.*
