# Phase 41: Address v1.7 tech debt — integration_gate + traceability — Pattern Map

**Mapped:** 2026-05-26
**Files analyzed:** 2 (both MODIFY)
**Analogs found:** 2 / 2 (both exact)

## File Classification

| Modified File | Role | Data Flow | Closest Analog | Match Quality |
|-------------------|------|-----------|----------------|---------------|
| `agents/graph-wiki-agent/tests/integration/test_scan_graph_end_to_end.py` | test (integration) | module-level marker + per-test decorator | `agents/graph-wiki-agent/tests/integration/test_bedrock_iam.py` | exact (canonical) |
| `.planning/REQUIREMENTS.md` | docs (traceability matrix) | checklist + status-table sync | n/a — self-contained text edits (no code analog needed) | n/a |

## Pattern Assignments

### `agents/graph-wiki-agent/tests/integration/test_scan_graph_end_to_end.py` (test, gate-decorator)

**Analog:** `agents/graph-wiki-agent/tests/integration/test_bedrock_iam.py`
**Why this analog:** CONTEXT.md D-03 names it as the canonical reference verbatim. `agents/graph-wiki-agent/tests/conftest.py` lines 23-28 defines the same constant and is the upstream source of the pattern; `test_bedrock_iam.py` is the clearest in-tree consumer to copy.

**Imports pattern** (analog lines 21-26):
```python
from __future__ import annotations

import os

import botocore.exceptions
import pytest
```
For the target file: `import os` is the only new addition required — the target already imports `pytest` (line 26 of current file). Add `import os` to the existing stdlib import block (after `import sys`, line 22).

**INTEGRATION_GATE constant** (analog lines 30-35) — **copy verbatim**, only the `reason=` string adapts to the scenario:
```python
# Canonical GRAPH_WIKI_RUN_INTEGRATION gate — matches conftest.py:19-22 verbatim
# so the docs/testing.md grep gate sees this file as canonical (D-10).
INTEGRATION_GATE = pytest.mark.skipif(
    not os.environ.get("GRAPH_WIKI_RUN_INTEGRATION"),
    reason="Set GRAPH_WIKI_RUN_INTEGRATION=1 to run real integration scenarios",
)
```
Placement: directly after the existing module docstring + imports, before the module-level `pytestmark = pytest.mark.integration` at current line 31 (or immediately after it — both satisfy the regex contract). Keep the comment block — it documents the D-10 anchor that the audit explicitly calls out.

**Decorator application** (analog lines 38-40):
```python
@pytest.mark.integration
@INTEGRATION_GATE
def test_make_llm_preflight_invoke():
    ...
```
For the target: the module already declares `pytestmark = pytest.mark.integration` (current line 31), so the per-test `@pytest.mark.integration` is redundant. Apply only `@INTEGRATION_GATE` to each test function in the file. Keep the existing module-level `pytestmark` — D-03 says "alongside" not "replacement."

### Regex contract this edit must satisfy

**Source:** `tests/test_integration_gate.py` lines 21-25

```python
_CANONICAL_PATTERN = re.compile(
    r'pytest\.mark\.skipif\s*\(\s*'
    r'(?:not\s+)?os\.environ\.get\(\s*["\']GRAPH_WIKI_RUN_INTEGRATION["\']\s*\)',
    re.MULTILINE,
)
```

**What this means for the edit:**
- Must contain the literal token sequence `pytest.mark.skipif( ... os.environ.get("GRAPH_WIKI_RUN_INTEGRATION")` (whitespace/newlines tolerated between tokens)
- `not` before `os.environ.get` is optional per the `(?:not\s+)?` group
- Either single or double quotes around the env-var name are accepted
- The verbatim multi-line form from D-03 satisfies this regex (newlines between `(` and `not os.environ...` are absorbed by `\s*`)
- Allowlist marker `# integration-gate-allow` (per `_ALLOW_MARKER` on line 28) is **not** to be used here — D-04 prohibits it.

**Success oracle:** `pytest tests/test_integration_gate.py` transitions red → green after the edit.

---

### `.planning/REQUIREMENTS.md` (docs, traceability matrix)

**No code analog** — pure markdown edits to existing structure.

**Edit 1 — Checkbox flip** (lines 16-29, 33-35, 60-62):
24 lines change `- [ ]` → `- [x]`. The line text after the checkbox is preserved verbatim. Exact REQ-IDs per D-05:
- HYGIENE-01..14 → lines 16-29
- CGFIND-01..03 → lines 33-35
- INGESTOR-01..03 → lines 60-62

**Edit 2 — Traceability table Status column** (lines 95-111, 124-126):
24 rows change `| Pending |` → `| Satisfied |` (per D-06 wording; D-07 forbids any other column / row / structural change). Exact rows:
- Lines 95-108: HYGIENE-01..14
- Lines 109-111: CGFIND-01..03
- Lines 124-126: INGESTOR-01..03

Existing LIBTOOLS-* / GRAPHCMD-* / SCANNER-* rows already read `Satisfied` (or equivalent) — D-05/D-06 explicitly say do not touch them.

## Shared Patterns

None applicable. Two-file phase; one test edit + one docs edit with no overlap.

## No Analog Found

None. Both targets have a definitive in-repo reference (`test_bedrock_iam.py` for the test edit; the surrounding REQUIREMENTS.md rows themselves for the docs edit — every "Satisfied"-row precedent in the table is its own template).

## Metadata

**Analog search scope:** `agents/graph-wiki-agent/tests/integration/`, `tests/` (repo root), `.planning/REQUIREMENTS.md`
**Files scanned:** 4 (`test_bedrock_iam.py`, `test_scan_graph_end_to_end.py`, `test_integration_gate.py`, `REQUIREMENTS.md`)
**Pattern extraction date:** 2026-05-26
