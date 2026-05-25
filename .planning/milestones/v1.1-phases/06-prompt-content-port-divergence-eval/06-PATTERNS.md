# Phase 6: Prompt Content Port + Divergence Eval - Pattern Map

**Mapped:** 2026-05-15
**Files analyzed:** 28 new/modified files
**Analogs found:** 26 / 28 (2 have no codebase analog — vendored content and rubric .md files)

---

## File Classification

| New/Modified File | Role | Data Flow | Closest Analog | Match Quality |
|---|---|---|---|---|
| `cores/prompt-sources/SKILL.md` + `agents/*.md` | vendor | n/a | none (verbatim copy) | no analog |
| `prompts/__init__.py` | module init | n/a | `commands/__init__.py` | exact |
| `prompts/_fragments/__init__.py` | module init | n/a | `commands/__init__.py` | exact |
| `prompts/_fragments/iron_rules.py` | constant | n/a | inline `LIBRARIAN_SYSTEM` in `commands/query.py` (before state) | role-match |
| `prompts/_fragments/page_categories.py` | constant | n/a | inline `LIBRARIAN_SYSTEM` in `commands/query.py` (before state) | role-match |
| `prompts/_fragments/citation_rules.py` | constant | n/a | inline `LIBRARIAN_SYSTEM` in `commands/query.py` (before state) | role-match |
| `prompts/_fragments/frontmatter_rules.py` | constant | n/a | inline `INGESTOR_SYSTEM` in `commands/ingest.py` (before state) | role-match |
| `prompts/librarian.py` | constant / composition | n/a | `commands/query.py` lines 137-148 (`LIBRARIAN_SYSTEM`) | exact |
| `prompts/ingestor.py` | constant / composition | n/a | `commands/ingest.py` lines 42-66 (`INGESTOR_SYSTEM`) | exact |
| `prompts/linter.py` | constant / composition | n/a | `commands/lint.py` lines 69-106 (3-group `*_SYSTEM`) | exact |
| `prompts/scanner.py` | constant / composition | n/a | `commands/scan.py` lines 92-115 (`SCANNER_SYSTEM`) | exact |
| `prompts/synthesizer.py` | constant / relocation | n/a | `commands/query.py` lines 150-163 (`SYNTHESIZER_SYSTEM`) | exact |
| `prompts/code_reader.py` | constant / relocation | n/a | `commands/query.py` lines 165-179 (`CODE_READER_SYSTEM`) | exact |
| `commands/query.py` (modify) | command | request-response | self (swap inline for import) | self |
| `commands/ingest.py` (modify) | command | request-response | self (swap inline for import) | self |
| `commands/lint.py` (modify) | command | request-response | self (swap inline for import) | self |
| `commands/scan.py` (modify) | command | request-response | self (swap inline for import) | self |
| `eval_harness/divergence/__init__.py` | module init | n/a | `eval_harness/__init__.py` | exact |
| `eval_harness/divergence/check.py` | dataclass / utility | transform | `eval_harness/structural.py` | role-match |
| `eval_harness/divergence/librarian.py` | rule list | transform | `eval_harness/structural.py` | role-match |
| `eval_harness/divergence/ingestor.py` | rule list | transform | `eval_harness/structural.py` | role-match |
| `eval_harness/divergence/linter.py` | rule list | transform | `eval_harness/structural.py` | role-match |
| `eval_harness/divergence/scanner.py` | rule list | transform | `eval_harness/structural.py` | role-match |
| `eval_harness/divergence/metric.py` | service / metric | request-response | `eval_harness/judge.py` + `eval_harness/report.py` | role-match |
| `eval_harness/divergence/rubrics/*.md` | config | n/a | none (markdown rubric files, no Python analog) | no analog |
| `baselines/divergence-{role}.json` | data | n/a | `eval_harness/baseline.py` `_make_snapshot()` output | role-match |
| `tests/prompts/test_prompt_snapshots.py` | test | n/a | `tests/unit/test_commands_scan.py` + syrupy pattern | exact |
| `tests/prompts/test_provenance.py` | test | n/a | `tests/unit/test_commands_scan.py` | role-match |
| `eval-harness/tests/test_divergence_checks.py` | test | n/a | `eval-harness/tests/test_structural.py` | exact |
| `eval-harness/tests/test_divergence_baseline.py` | test | n/a | `eval-harness/tests/test_baseline.py` | exact |
| `eval-harness/tests/test_divergence.py` | test (eval-gated) | n/a | `eval-harness/tests/eval/test_sweep_eval.py` | exact |

---

## Pattern Assignments

### `prompts/_fragments/iron_rules.py` (constant, shared fragment)

**Analog:** `agents/graph-wiki-agent/src/graph_wiki_agent/commands/query.py` lines 136-148 (the `LIBRARIAN_SYSTEM` triple-quoted string is the "before" state; this is the extraction target)

**Fragment file structure** (lines 1-10, the full file pattern):
```python
# Source: cores/prompt-sources/SKILL.md
# Anchor: ## Iron rules (L193-L201)
# Source-commit: <SHA at last sync>

IRON_RULES = """\
## Iron rules

1. ...
"""
```

The three-line provenance header is mandatory on every fragment file. The constant name is SCREAMING_SNAKE_CASE. The string uses `"""\` (backslash after triple-quote) to avoid a leading newline — match the `SCANNER_SYSTEM` style in `commands/scan.py` line 92.

**Anti-pattern to avoid:** Do NOT use `"""` (no backslash) as that inserts a leading newline and breaks string joining with `"\n\n".join(...)`.

---

### `prompts/_fragments/page_categories.py` (constant, shared fragment)

**Analog:** inline `LIBRARIAN_SYSTEM` in `commands/query.py` lines 136-148 (before state)

Same file structure as `iron_rules.py`. Provenance anchor points to `cores/prompt-sources/SKILL.md` §Page categories table. The constant name is `PAGE_CATEGORIES`.

---

### `prompts/_fragments/citation_rules.py` (constant, shared fragment)

**Analog:** inline `LIBRARIAN_SYSTEM` in `commands/query.py` lines 141-143 (the citation/wikilink rules bullets)

Same file structure. Provenance anchor points to `cores/prompt-sources/agents/librarian.md` §Rules bullets 3-4. Constant name: `CITATION_RULES`.

---

### `prompts/_fragments/frontmatter_rules.py` (constant, shared fragment)

**Analog:** inline `INGESTOR_SYSTEM` in `commands/ingest.py` lines 49-55 (the required frontmatter fields block)

Same file structure. Provenance anchor points to `cores/prompt-sources/agents/ingestor.md` §Workflow step 4. Constant name: `FRONTMATTER_RULES`.

---

### `prompts/librarian.py` (constant, composition layer)

**Analog:** `agents/graph-wiki-agent/src/graph_wiki_agent/commands/query.py` lines 136-148

**Imports pattern** (lines 1-8):
```python
from __future__ import annotations

from graph_wiki_agent.prompts._fragments.iron_rules import IRON_RULES
from graph_wiki_agent.prompts._fragments.page_categories import PAGE_CATEGORIES
from graph_wiki_agent.prompts._fragments.citation_rules import CITATION_RULES
```

**Core composition pattern** (lines 10-20):
```python
LIBRARIAN_SYSTEM = "\n\n".join([
    "You are a wiki librarian. ...",  # role-local intro (adapted)
    IRON_RULES,
    PAGE_CATEGORIES,
    CITATION_RULES,
    "## Red flags\n...",              # role-local, adapted from librarian.md §Red flags
])
```

**What the existing inline constant looks like** (query.py lines 137-148, the "before" state being replaced):
```python
LIBRARIAN_SYSTEM = """You are a wiki librarian. Given a user query and a single wiki page, extract every passage from the page that is directly relevant to the query.

Rules:
- Quote relevant passages **verbatim** from the supplied page only. ...
- Never invent file paths, line numbers, symbol names, or wikilinks. ...
- ...
- When the page contains no passage relevant to the query, respond with exactly the sentinel string `NO_RELEVANT_CONTENT` and nothing else. ...

Output format:
- Either a list of verbatim excerpts (each labeled with its wikilink as it appears in the page), or the bare sentinel `NO_RELEVANT_CONTENT`. Nothing else."""
```

The composed `LIBRARIAN_SYSTEM` must preserve: the `NO_RELEVANT_CONTENT` sentinel behavior, the no-invention rule, wikilink verbatim preservation, and `path:line` annotation rules. These are already in the existing inline constant and must survive the port.

---

### `prompts/ingestor.py` (constant, composition layer)

**Analog:** `agents/graph-wiki-agent/src/graph_wiki_agent/commands/ingest.py` lines 42-66

**Existing inline constant** (lines 42-66 — the "before" state being replaced):
```python
INGESTOR_SYSTEM = """\
You are a code wiki ingestor. Your job is to analyze a source document and produce
a well-structured wiki page that integrates it into an existing knowledge base.

Output ONLY YAML frontmatter followed by a markdown body. Do not add commentary
outside of these sections.

Required frontmatter fields:
  - title: <descriptive title for the page>
  - category: <one of: package, concept, adr>
  - page_type: <one of: package, concept, adr>
  - target_slug: <URL-safe slug for the output filename, e.g. "auth-design">
  - summary: <one-line description of the source's main contribution>
  - tags: []  (list of relevant tags, or empty list)

Your output must include:
1. YAML frontmatter (between --- delimiters) with all required fields above.
2. A "## Summary" section (3-5 sentences) describing the source content.
3. Optional "## Key Concepts" or "## Decisions" section where appropriate.
4. Use [[wikilink]] style cross-references to related vault pages where relevant.

Keep total output under 1500 tokens.
Do NOT reproduce the full source text — synthesize and summarize.
Do NOT speculate beyond what the provided source content shows.
"""
```

**Composition pattern:**
```python
from graph_wiki_agent.prompts._fragments.iron_rules import IRON_RULES
from graph_wiki_agent.prompts._fragments.page_categories import PAGE_CATEGORIES
from graph_wiki_agent.prompts._fragments.citation_rules import CITATION_RULES
from graph_wiki_agent.prompts._fragments.frontmatter_rules import FRONTMATTER_RULES

INGESTOR_SYSTEM = "\n\n".join([
    "You are a code wiki ingestor. ...",  # role-local intro (adapted)
    IRON_RULES,
    PAGE_CATEGORIES,
    FRONTMATTER_RULES,
    CITATION_RULES,
    "## Rules\n...",                       # ingestor-local rules (adapted)
])
```

---

### `prompts/linter.py` (constants, 3-group composition layer)

**Analog:** `agents/graph-wiki-agent/src/graph_wiki_agent/commands/lint.py` lines 69-106

**Existing inline constants** (lint.py lines 69-106 — "before" state, three exports):
```python
LINTER_PAGE_QUALITY_SYSTEM = """\
You are a code wiki quality linter. Review the provided wiki pages and identify
quality issues. Report one finding per line in plain text. Focus on:
- Pages with vague or unhelpful summaries (under 10 words, or obviously placeholder)
...
"""

LINTER_ADR_CHAIN_SYSTEM = """\
You are a code wiki ADR (Architecture Decision Record) chain linter. ...
"""

LINTER_STALE_CLAIMS_SYSTEM = """\
You are a code wiki stale-claims linter. ...
"""
```

**What the call site expects** (lint.py lines 454-456 — unchanged after refactor):
```python
("page_quality", LINTER_PAGE_QUALITY_SYSTEM, pages_sample),
("adr_chain", LINTER_ADR_CHAIN_SYSTEM, adr_pages),
("stale_claims", LINTER_STALE_CLAIMS_SYSTEM, pages_with_source),
```

The three export names `LINTER_PAGE_QUALITY_SYSTEM`, `LINTER_ADR_CHAIN_SYSTEM`, `LINTER_STALE_CLAIMS_SYSTEM` must be preserved exactly — call sites use these names without aliasing.

**Fragments used by linter.py:** `IRON_RULES` (shared constraint context). Linter does not use `PAGE_CATEGORIES` or `CITATION_RULES` fragments (linter checks structure, not citation style). The 3 group prompts may compose an optional shared `LINT_PRIORITY_ORDER` local constant (the "code drift > contradictions > ..." rule) rather than putting it in `_fragments/` since it is linter-only.

---

### `prompts/scanner.py` (constant, composition layer)

**Analog:** `agents/graph-wiki-agent/src/graph_wiki_agent/commands/scan.py` lines 92-115

**Existing inline constant** (scan.py lines 92-115 — "before" state):
```python
SCANNER_SYSTEM = """\
You are a code wiki scanner. Your job is to write a concise stub page for a software package.

Produce ONLY the page body with YAML frontmatter. Do NOT include a "## File map" section — that
is added separately by the build pipeline and must not appear in your output.

Your output must include:
1. YAML frontmatter (between --- delimiters) with these fields:
   - title: <package name>
   - category: package  (use "app" if it is an application, otherwise "package")
   - summary: <one-line description of what the package does>
   - package_path: <relative path of the package in the repo>
   - language: <primary language: python, typescript, javascript, rust, go, unknown>
   - version: <version string or omit if unknown>
   - depends_on: []  (list of internal workspace dependencies, or empty list)
   - exports: []  (list of public exports/scripts, or empty list)

2. ONE short "## Overview" section (3-5 sentences) describing what the package does and why.
3. ONE short "## Notable files" section listing 2-4 key files with a one-line description each.

Keep total output under 380 tokens. Do NOT speculate beyond what the provided file listing shows.
Do NOT include a "## File map" section — it will be appended automatically.
"""
```

**Composition pattern:**
```python
from graph_wiki_agent.prompts._fragments.iron_rules import IRON_RULES
from graph_wiki_agent.prompts._fragments.frontmatter_rules import FRONTMATTER_RULES

SCANNER_SYSTEM = "\n\n".join([
    "You are a code wiki scanner. ...",  # role-local intro
    IRON_RULES,
    FRONTMATTER_RULES,
    "## Rules\n...",                      # scanner-local rules (adapted)
])
```

Token budget constraint: the existing `SCANNER_SYSTEM` is ~115 tokens. The composed version must stay under ~400 tokens.

---

### `prompts/synthesizer.py` (constant, relocation only)

**Analog:** `agents/graph-wiki-agent/src/graph_wiki_agent/commands/query.py` lines 150-163

**Content to relocate verbatim** (query.py lines 150-163):
```python
SYNTHESIZER_SYSTEM = """You are a wiki synthesizer. Given a user query and a set of excerpts from relevant wiki pages, produce a concise, accurate answer drawn strictly from those excerpts.

Rules:
- Compose the answer **only** from the supplied librarian excerpts. Never invent a file path, ...
...
"""
```

No provenance header needed (no canonical lattice-wiki source). No fragment composition — this is a straight lift-and-move. The file has one export: `SYNTHESIZER_SYSTEM`.

---

### `prompts/code_reader.py` (constant, relocation only)

**Analog:** `agents/graph-wiki-agent/src/graph_wiki_agent/commands/query.py` lines 165-179

**Content to relocate verbatim** (query.py lines 165-179):
```python
CODE_READER_SYSTEM = """You are a source-code reader operating as a vault-thin fallback. ...
"""
```

Same pattern as `synthesizer.py`: straight relocation, no provenance header, no fragment composition. One export: `CODE_READER_SYSTEM`.

---

### `commands/query.py` (modify — replace inline with import)

**Analog:** self

**Before state** (query.py lines 136-179 — three inline constants):
```python
LIBRARIAN_SYSTEM = """..."""
SYNTHESIZER_SYSTEM = """..."""
CODE_READER_SYSTEM = """..."""
```

**After state** (replace those 3 blocks with 3 import lines):
```python
from graph_wiki_agent.prompts.librarian import LIBRARIAN_SYSTEM  # noqa: F401
from graph_wiki_agent.prompts.synthesizer import SYNTHESIZER_SYSTEM  # noqa: F401
from graph_wiki_agent.prompts.code_reader import CODE_READER_SYSTEM  # noqa: F401
```

The module docstring at lines 16-18 re-exports these names in the Public API section — update those lines to note the new import source. All call sites (`SystemMessage(content=LIBRARIAN_SYSTEM)`) are unchanged.

---

### `commands/ingest.py` (modify — replace inline with import)

**Analog:** self

**Before state** (ingest.py lines 42-66): inline `INGESTOR_SYSTEM = """\..."""`

**After state:**
```python
from graph_wiki_agent.prompts.ingestor import INGESTOR_SYSTEM  # noqa: F401
```

---

### `commands/lint.py` (modify — replace inline with import)

**Analog:** self

**Before state** (lint.py lines 69-106): three inline `LINTER_*_SYSTEM` constants

**After state:**
```python
from graph_wiki_agent.prompts.linter import (  # noqa: F401
    LINTER_ADR_CHAIN_SYSTEM,
    LINTER_PAGE_QUALITY_SYSTEM,
    LINTER_STALE_CLAIMS_SYSTEM,
)
```

---

### `commands/scan.py` (modify — replace inline with import)

**Analog:** self

**Before state** (scan.py lines 92-115): inline `SCANNER_SYSTEM = """\..."""`

**After state:**
```python
from graph_wiki_agent.prompts.scanner import SCANNER_SYSTEM  # noqa: F401
```

---

### `eval_harness/divergence/check.py` (dataclass / utility)

**Analog:** `cores/eval-harness/src/eval_harness/structural.py`

**Imports pattern** (structural.py lines 1-17):
```python
from __future__ import annotations

import re
from pathlib import Path
from typing import Any

import frontmatter
from graph_wiki_agent.commands.query import QueryResult
```

**Core dataclass pattern** — new file, no direct analog for the `@dataclass` shape, but follows the `from dataclasses import dataclass` convention used in `commands/query.py`, `commands/ingest.py`, `commands/scan.py`, `commands/lint.py`. Use:
```python
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Callable, NamedTuple


class Verdict(NamedTuple):
    passed: bool
    excerpt: str  # evidence for accepted_failures array


@dataclass
class DivergenceCheck:
    id: str             # e.g. "LIB-001-wikilink-resolves"
    source_anchor: str  # e.g. "cores/prompt-sources/SKILL.md#iron-rules"
    severity: str       # "hard" | "soft"
    check: Callable[["AgentOutputProxy", Path], Verdict]


@dataclass
class AgentOutputProxy:
    """Minimal wrapper mapping any command result to a common check interface."""
    answer: str
    page_type: str = ""  # for ingestor checks (ING-003, ING-004)
```

**Module docstring style** — match `structural.py` lines 1-8: one-line summary, blank line, then "Implements ..." sentence. Security notes (T-4-* pattern) if input is not fully trusted.

---

### `eval_harness/divergence/librarian.py` (rule list)

**Analog:** `cores/eval-harness/src/eval_harness/structural.py`

**Imports pattern** (structural.py lines 14-17):
```python
from __future__ import annotations

import re
from pathlib import Path
from typing import Any

import frontmatter
from graph_wiki_agent.commands.query import QueryResult

_CODE_PATH_RE = re.compile(...)

def _resolve_citation(slug: str, vault_path: Path) -> Path | None:
    ...
```

**Core rule pattern** (new file, patterned after structural.py's function style):
```python
from __future__ import annotations

import re
from pathlib import Path

from eval_harness.divergence.check import DivergenceCheck, Verdict
from eval_harness.structural import _resolve_citation  # reuse existing

_WIKILINK_RE = re.compile(r"\[\[([^\]]+)\]\]")


def _check_wikilink_resolves(output: "AgentOutputProxy", vault: Path) -> Verdict:
    links = _WIKILINK_RE.findall(output.answer)
    if not links:
        return Verdict(passed=True, excerpt="")
    unresolved = [l for l in links if _resolve_citation(l, vault) is None]
    if unresolved:
        return Verdict(passed=False, excerpt=f"Unresolved: {unresolved[0]}")
    return Verdict(passed=True, excerpt="")


LIBRARIAN_CHECKS: list[DivergenceCheck] = [
    DivergenceCheck(
        id="LIB-001-wikilink-resolves",
        source_anchor="cores/prompt-sources/SKILL.md#iron-rules",
        severity="hard",
        check=_check_wikilink_resolves,
    ),
    # LIB-002, LIB-003, LIB-004, ...
]
```

The same pattern applies to `ingestor.py`, `linter.py`, `scanner.py` — each exports a `{ROLE}_CHECKS: list[DivergenceCheck]` constant.

---

### `eval_harness/divergence/metric.py` (service / metric)

**Primary analog:** `cores/eval-harness/src/eval_harness/judge.py`

**Secondary analog:** `cores/eval-harness/src/eval_harness/report.py` (for baseline delta + regression check logic)

**Imports pattern** (judge.py lines 15-20):
```python
from __future__ import annotations

from deepeval.metrics import GEval
from deepeval.models import AmazonBedrockModel
from deepeval.test_case import LLMTestCase, SingleTurnParams
```

**Judge factory pattern** (judge.py lines 50-69 — copy verbatim, critical security constraint):
```python
def make_judge(cfg: dict) -> AmazonBedrockModel:
    return AmazonBedrockModel(
        model=cfg["model_id"],
        region="us-east-1",
        cost_per_input_token=cfg["input_price_per_m"] / 1_000_000,
        cost_per_output_token=cfg["output_price_per_m"] / 1_000_000,
        generation_kwargs={"temperature": 0},
    )
```

**GEval invocation pattern** (judge.py lines 94-116 — the `panel_score` inner loop):
```python
for cfg in JUDGE_PANEL_CONFIG:
    judge = make_judge(cfg)          # Fresh instance per call — do not reuse
    metric = GEval(
        name="wiki_query_quality",
        criteria=EVAL_CRITERIA,
        evaluation_steps=EVAL_STEPS,
        evaluation_params=[
            SingleTurnParams.INPUT,
            SingleTurnParams.ACTUAL_OUTPUT,
            SingleTurnParams.EXPECTED_OUTPUT,
        ],
        model=judge,  # ALWAYS explicit — never let deepeval default to OpenAI
        threshold=0.5,
    )
    tc = LLMTestCase(input=query, actual_output=actual, expected_output=expected)
    metric.measure(tc)
    scores.append(metric.score)
    reasons.append(metric.reason or "")
```

**Regression check pattern** (report.py lines 66-84):
```python
def regression_check(score: float, threshold: float = 0.5) -> None:
    if score < threshold:
        raise AssertionError(
            f"Quality score {score:.3f} below threshold {threshold:.3f}"
        )
```

For divergence, the analog is: compare `current_failures > baseline_failures` for `severity == "hard"` and raise `AssertionError` with a message that names the rule_id and includes "Run with --accept-divergence-baseline to accept."

**Baseline load/write pattern** — mirrors `BaselineRecorder._make_snapshot()` in `baseline.py` lines 301-323:
```python
return {
    "case_id": case_id,
    "query": query,
    "answer": answer,
    "model_arn": self._model_arn,
    "prompt_hash": _prompt_hash(...),
    "vault_content_hash": _vault_content_hash(...),
    "timestamp_utc": datetime.now(tz=timezone.utc).isoformat(),
    "seed": None,
}
```

Divergence baseline analog:
```python
{
    "role": role,
    "recorded_at": datetime.now(tz=timezone.utc).isoformat(),
    "agent_commit": agent_commit,
    "checks": {rule_id: {"runs": int, "failures": int, "accepted_failures": [...]}}
}
```

Use `json.dumps(baseline, indent=2) + "\n"` and `path.write_text(..., encoding="utf-8")` — exactly as `baseline.py` line 360.

---

### `eval-harness/tests/test_divergence_checks.py` (test — unit, no Bedrock)

**Analog:** `cores/eval-harness/tests/test_structural.py`

**Imports pattern** (test_structural.py lines 1-14):
```python
from __future__ import annotations

from pathlib import Path

import pytest
from graph_wiki_agent.commands.query import QueryResult
from eval_harness.structural import check_structural
```

**Test structure pattern** (test_structural.py lines 27-44):
```python
def test_known_good(fixture_vault_path: Path) -> None:
    """A well-formed QueryResult with a valid citation resolves cleanly."""
    result = QueryResult(
        answer="See [[packages/lattice-wiki-core]].",
        citations=["packages/lattice-wiki-core"],
        pages_drilled=3,
        search_scores={},
    )
    report = check_structural(result, fixture_vault_path)
    assert report["citations_resolve"] is True
```

For divergence checks, the analog test pattern:
```python
def test_lib001_passes_on_resolved_wikilink(fixture_vault_path: Path) -> None:
    """LIB-001 passes when all wikilinks resolve to existing vault pages."""
    from eval_harness.divergence.check import AgentOutputProxy
    from eval_harness.divergence.librarian import LIBRARIAN_CHECKS

    output = AgentOutputProxy(answer="See [[packages/lattice-wiki-core]].")
    check = next(c for c in LIBRARIAN_CHECKS if c.id == "LIB-001-wikilink-resolves")
    verdict = check.check(output, fixture_vault_path)
    assert verdict.passed is True

def test_lib001_fails_on_unresolved_wikilink(fixture_vault_path: Path) -> None:
    """LIB-001 fails when a wikilink doesn't resolve."""
    ...
    assert verdict.passed is False
    assert "Unresolved" in verdict.excerpt
```

---

### `eval-harness/tests/test_divergence_baseline.py` (test — unit, no Bedrock)

**Analog:** `cores/eval-harness/tests/test_baseline.py`

**Import + test structure pattern** (test_baseline.py lines 1-35):
```python
from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock

import pytest

from eval_harness.baseline import (
    BaselineRecorder,
    RunResult,
    _build_cmd,
    _prompt_hash,
    _vault_content_hash,
)
```

**Schema test pattern** (test_baseline.py lines 110-135):
```python
def test_baseline_schema(tmp_path: Path, fixture_vault_path: Path) -> None:
    """_make_snapshot returns dict with all 8 required EVAL-08 schema keys."""
    ...
    required_keys = {"case_id", "query", "answer", ...}
    assert required_keys <= snapshot.keys(), f"Missing keys: {required_keys - snapshot.keys()}"
```

For divergence baseline tests:
```python
def test_load_baseline_returns_empty_when_missing(tmp_path: Path) -> None:
    """load_baseline returns {} when file does not exist (Pitfall 5)."""
    from eval_harness.divergence.metric import load_baseline
    result = load_baseline("librarian", tmp_path)
    assert result == {}

def test_write_baseline_schema(tmp_path: Path) -> None:
    """write_baseline writes JSON with all required keys."""
    ...
    required_keys = {"role", "recorded_at", "agent_commit", "checks"}
    assert required_keys <= snapshot.keys()

def test_check_regression_raises_on_hard_increase(tmp_path: Path) -> None:
    """check_regression raises AssertionError when hard-severity failures increase."""
    ...
    with pytest.raises(AssertionError, match="accept-divergence-baseline"):
        check_regression(...)

def test_check_regression_does_not_raise_for_soft(tmp_path: Path) -> None:
    """check_regression does not raise for soft-severity failure increases."""
    ...
```

---

### `eval-harness/tests/test_divergence.py` (test — eval-gated, Bedrock)

**Analog:** `cores/eval-harness/tests/eval/test_sweep_eval.py`

**EVAL_GATE pattern** (conftest.py lines 17-20, test_sweep_eval.py lines 57-61):
```python
# In eval-harness/tests/conftest.py (addition):
def pytest_addoption(parser):
    parser.addoption(
        "--accept-divergence-baseline",
        action="store_true",
        default=False,
        help="Overwrite divergence baselines with current run results",
    )

@pytest.fixture
def accept_baseline(request):
    return request.config.getoption("--accept-divergence-baseline")
```

**Eval-gated test structure** (test_sweep_eval.py lines 114-172):
```python
pytestmark = [pytest.mark.eval]  # module-level, skips without --run-eval

@pytest.mark.eval(name="query_sweep")
@pytest.mark.parametrize("case_and_model", CASE_MODEL_PARAMS, ...)
@EVAL_GATE
async def test_query_sweep_case(case_and_model: dict, eval_bag) -> None:
    ...
```

For divergence:
```python
EVAL_GATE = pytest.mark.skipif(
    not os.environ.get("GRAPH_WIKI_RUN_EVAL"),
    reason="Set GRAPH_WIKI_RUN_EVAL=1 to run divergence eval",
)
BASELINES_DIR = Path(__file__).parent.parent / "baselines"

@EVAL_GATE
@pytest.mark.parametrize("role", ["librarian", "ingestor", "linter", "scanner"])
def test_divergence_regression(role, fixture_vault, accept_baseline):
    ...
    check_regression(role, results, baseline)
```

**Path resolution pattern** (test_sweep_eval.py lines 38-48):
```python
_WORKSPACE_ROOT = Path(__file__).parent.parent.parent.parent.parent
FIXTURE_VAULT = _WORKSPACE_ROOT / "cores" / "wiki-io" / "tests" / "fixtures" / "round-trip-vault"
```

---

### `tests/prompts/test_prompt_snapshots.py` (test — syrupy snapshot)

**Analog:** `agents/graph-wiki-agent/tests/unit/test_commands_scan.py` (structure) + syrupy usage from RESEARCH.md examples

**Import + snapshot pattern:**
```python
from __future__ import annotations

import pytest
from syrupy.assertion import SnapshotAssertion

from graph_wiki_agent.prompts.librarian import LIBRARIAN_SYSTEM
from graph_wiki_agent.prompts.ingestor import INGESTOR_SYSTEM
from graph_wiki_agent.prompts.linter import (
    LINTER_ADR_CHAIN_SYSTEM,
    LINTER_PAGE_QUALITY_SYSTEM,
    LINTER_STALE_CLAIMS_SYSTEM,
)
from graph_wiki_agent.prompts.scanner import SCANNER_SYSTEM
from graph_wiki_agent.prompts.synthesizer import SYNTHESIZER_SYSTEM
from graph_wiki_agent.prompts.code_reader import CODE_READER_SYSTEM


def test_librarian_system_snapshot(snapshot: SnapshotAssertion) -> None:
    assert LIBRARIAN_SYSTEM == snapshot

def test_ingestor_system_snapshot(snapshot: SnapshotAssertion) -> None:
    assert INGESTOR_SYSTEM == snapshot

# ... one test per exported *_SYSTEM constant
```

First run with `--snapshot-update` records. File location: `agents/graph-wiki-agent/tests/prompts/test_prompt_snapshots.py`. Syrupy stores snapshots in `tests/prompts/__snapshots__/` automatically.

---

### `tests/prompts/test_provenance.py` (test — unit, no Bedrock)

**Analog:** `agents/graph-wiki-agent/tests/unit/test_commands_scan.py` (style)

**Pattern — read fragment source, assert header format:**
```python
from __future__ import annotations

import re
from pathlib import Path

FRAGMENT_DIR = Path(__file__).parent.parent.parent.parent / "src" / "graph_wiki_agent" / "prompts" / "_fragments"
PROMPT_SOURCES_DIR = Path(__file__).parent.parent.parent.parent.parent.parent / "cores" / "prompt-sources"

_PROVENANCE_RE = re.compile(
    r"^# Source: (?P<source>.+)\n"
    r"# Anchor: (?P<anchor>.+)\n"
    r"# Source-commit: (?P<sha>[a-f0-9]+)\s*$",
    re.MULTILINE,
)


def test_all_fragments_have_provenance_header() -> None:
    """Every _fragments/*.py file has the 3-line provenance header."""
    fragment_files = [f for f in FRAGMENT_DIR.glob("*.py") if f.name != "__init__.py"]
    assert fragment_files, "No fragment files found"
    for fpath in fragment_files:
        text = fpath.read_text(encoding="utf-8")
        match = _PROVENANCE_RE.search(text)
        assert match, f"{fpath.name}: missing or malformed provenance header"


def test_provenance_source_paths_resolve() -> None:
    """Source: paths in provenance headers resolve within cores/prompt-sources/."""
    for fpath in FRAGMENT_DIR.glob("*.py"):
        if fpath.name == "__init__.py":
            continue
        text = fpath.read_text(encoding="utf-8")
        match = _PROVENANCE_RE.search(text)
        if not match:
            continue
        source_rel = match.group("source")  # e.g. "cores/prompt-sources/SKILL.md"
        # Strip the "cores/prompt-sources/" prefix and check in prompt-sources dir
        assert source_rel.startswith("cores/prompt-sources/"), \
            f"{fpath.name}: Source: path must start with 'cores/prompt-sources/'"
```

---

## Shared Patterns

### `from __future__ import annotations` header
**Source:** All files in `cores/eval-harness/src/eval_harness/` and `agents/graph-wiki-agent/src/graph_wiki_agent/commands/`
**Apply to:** All new `.py` files
```python
from __future__ import annotations
```
First line of every module, before the docstring.

### Module docstring style
**Source:** `eval_harness/structural.py` lines 1-8, `eval_harness/judge.py` lines 1-13
**Apply to:** All new `.py` modules
```python
"""One-line summary of what this module does.

Longer description on second paragraph if needed. For eval-harness files,
include Security (T-4-XX) notes when the module processes any external input.

Exports:
    ExportedClass/function — what it does
"""
```

### EVAL_GATE skip marker
**Source:** `cores/eval-harness/tests/conftest.py` lines 17-20
**Apply to:** `test_divergence.py`
```python
import os
import pytest

EVAL_GATE = pytest.mark.skipif(
    not os.environ.get("GRAPH_WIKI_RUN_EVAL"),
    reason="Set GRAPH_WIKI_RUN_EVAL=1 to run divergence eval",
)
```

### Explicit model= in GEval (security invariant)
**Source:** `eval_harness/judge.py` line 106, comment
**Apply to:** `divergence/metric.py` every GEval instantiation
```python
model=judge,  # ALWAYS explicit — never let deepeval default to OpenAI
```

### JSON write pattern
**Source:** `eval_harness/baseline.py` line 360
**Apply to:** `divergence/metric.py` `write_baseline()`
```python
path.write_text(json.dumps(baseline, indent=2) + "\n", encoding="utf-8")
```

### Fixture vault path resolution
**Source:** `cores/eval-harness/tests/conftest.py` lines 24-48
**Apply to:** `test_divergence.py`, `test_divergence_checks.py`
```python
vault = (
    Path(__file__).parent.parent.parent.parent
    / "cores"
    / "wiki-io"
    / "tests"
    / "fixtures"
    / "round-trip-vault"
)
if not vault.exists():
    pytest.skip(f"round-trip-vault fixture not found at {vault}; ...")
return vault
```
Adjust parent depth based on file location.

### Provenance header (locked format)
**Source:** CONTEXT.md §specifics, RESEARCH.md §Code Examples
**Apply to:** Every `prompts/_fragments/*.py` file (NOT per-role files)
```python
# Source: cores/prompt-sources/SKILL.md
# Anchor: ## Iron rules (L193-L201)
# Source-commit: <SHA at last sync>
```
Three lines, exactly this format, at the very top of the file before any imports.

---

## No Analog Found

| File | Role | Data Flow | Reason |
|---|---|---|---|
| `cores/prompt-sources/SKILL.md` + `agents/*.md` | vendor | n/a | Verbatim copies from lattice repo — no Python analog; no pyproject.toml; pattern is "copy file, no modifications" |
| `eval_harness/divergence/rubrics/*.md` | config | n/a | Markdown rubric files for LLM judge — no existing `.md` rubric files in eval-harness; pattern is from RESEARCH.md §Pattern 3 (rubric text loaded via `Path.read_text()`) |

---

## Metadata

**Analog search scope:** `agents/graph-wiki-agent/src/`, `agents/graph-wiki-agent/tests/`, `cores/eval-harness/src/`, `cores/eval-harness/tests/`
**Files scanned:** 15 source files + 12 test files read in full
**Pattern extraction date:** 2026-05-15

**Key conventions confirmed from codebase:**
- `from __future__ import annotations` on line 1 of every module (universal)
- `"""\` (backslash after triple-quote) for multi-line string constants that begin a new scope — avoids leading newline (scan.py line 92, ingest.py line 42)
- `json.dumps(..., indent=2) + "\n"` + `path.write_text(..., encoding="utf-8")` for all JSON output (baseline.py line 360)
- `pytest.mark.skipif(not os.environ.get("GRAPH_WIKI_RUN_EVAL"), ...)` for eval-gated tests — not `@pytest.mark.eval` from pytest-evals (the divergence test uses the simpler env-var gate, matching `conftest.py` EVAL_GATE style, not the pytest-evals two-phase pattern)
- Path resolution always anchored to `Path(__file__).parent...` — never cwd-relative
- `_SCREAMING_SNAKE_RE = re.compile(...)` module-level regex constants with underscore prefix (structural.py line 20)
- `from eval_harness.structural import _resolve_citation` — private function import is acceptable cross-module (structural.py line 25 exports it implicitly; divergence checks reuse it)
- `JUDGE_PANEL_CONFIG` and `make_judge` imported from `eval_harness.judge` — do not redefine the panel config in metric.py; import from judge.py
