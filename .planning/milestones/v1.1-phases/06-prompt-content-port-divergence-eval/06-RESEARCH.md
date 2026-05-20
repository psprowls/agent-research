# Phase 6: Prompt Content Port + Divergence Eval - Research

**Researched:** 2026-05-15
**Domain:** Prompt composition, canonical source vendoring, deepeval divergence metrics
**Confidence:** HIGH

---

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions

- **D-01:** Composable fragments under `agents/graph-wiki-agent/src/graph_wiki_agent/prompts/`. Shared blocks in `prompts/_fragments/*.py`; per-role files (`librarian.py`, `ingestor.py`, `linter.py`, `scanner.py`) compose them. Shared because iron rules, citation rules, and page categories are repeated verbatim across all four lattice-wiki agent files.
- **D-02:** Each role file exports a single `*_SYSTEM` string built at import time from imported fragments. No runtime templating. Downstream call sites do `from graph_wiki_agent.prompts.librarian import LIBRARIAN_SYSTEM`.
- **D-03:** Each fragment file carries a 3-field inline header: `# Source:`, `# Anchor:`, `# Source-commit:`.
- **D-04:** Vendor canonical sources into `cores/prompt-sources/` verbatim. Provenance in fragments points to the vendored path. Re-vendoring is manual.
- **D-05:** Adapt the port — rewrite host-specific references (slash commands, Claude Code SDK tools) to graph-wiki-agent's tool surface. Preserve semantic content verbatim.
- **D-06:** Adaptations are local to per-role files. Shared fragments stay closer to canonical wording.
- **D-07:** Hybrid detection — programmatic checkers + GEval LLM judge (same Phase 4 two-judge panel: claude-sonnet-4-6 + nova-pro-v1:0).
- **D-08:** Per-role rule modules under `cores/eval-harness/src/eval_harness/divergence/{librarian,ingestor,linter,scanner}.py`, each exporting a list of `DivergenceCheck` dataclass instances. Schema locked (see D-08 in CONTEXT.md).
- **D-09:** Rule IDs stable: `<ROLE>-<NNN>-<slug>` format.
- **D-10:** Per-role rubric `.md` files under `cores/eval-harness/src/eval_harness/divergence/rubrics/{role}.md`.
- **D-11:** Single JSON baseline per role at `cores/eval-harness/baselines/divergence-{role}.json`.
- **D-12:** `--accept-divergence-baseline` flag rewrites baseline. Default run loads, computes deltas, fails hard-severity gate if failures exceed baseline.
- **D-13:** EVAL-12 satisfied by `accepted_failures` array carrying excerpts.
- **D-14:** Synthesizer + code-reader refactored into `prompts/synthesizer.py` and `prompts/code_reader.py` for uniformity. No content port, no divergence checks.

### Claude's Discretion

- Detailed file/module names within `prompts/_fragments/` (e.g., whether citation_rules.py is separate from iron_rules.py)
- Specific fixture additions for divergence checks
- Whether to add a re-vendor helper script

### Deferred Ideas (OUT OF SCOPE)

- Synthesizer + code-reader content port
- Re-vendor automation script
- CI pre-commit hook for source-SHA drift
- Per-fixture pinned expectations
- Divergence dashboard / trend report
</user_constraints>

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| PORT-01 | Canonical prompt sources identified per role — source files and section anchors pinned in traceability table | Fragment analysis below maps each section to source file + line range |
| PORT-02 | Librarian prompt incorporates canonical iron rules, citation rules, and refusal patterns | Section analysis: SKILL.md iron rules + librarian.md rules + red flags |
| PORT-03 | Ingestor prompt incorporates page-type routing, frontmatter rules, layout-block rules | Section analysis: ingestor.md workflow + rules |
| PORT-04 | Linter prompt incorporates canonical lint rule definitions (mechanical + semantic) | Section analysis: linter.md 3-pass structure + rules |
| PORT-05 | Scanner prompt incorporates canonical package-detection and overview-generation rules | Section analysis: scanner.md workflow + rules |
| PORT-06 | Prompt content in `prompts/` module with provenance comments | D-03 provenance header format; test gate pattern documented |
| EVAL-11 | New eval metric flags divergences between agent output and skill-content expectations | DivergenceCheck + DivergenceMetric integration pattern documented |
| EVAL-12 | Divergence eval emits per-role divergence counts + concrete examples | accepted_failures array in baseline JSON; report integration pattern |
| EVAL-13 | Regression gate — divergence rate cannot increase without `--accept-divergence-baseline` | Baseline delta logic and CLI flag integration documented |
</phase_requirements>

---

## Summary

Phase 6 performs two coupled tasks: (1) porting lattice-wiki's canonical system-prompt content from four source agent files and SKILL.md into a structured `prompts/` module with de-duplicated fragments and provenance headers, and (2) wiring a hybrid divergence-detection metric into the Phase 4 eval harness with per-role programmatic checks, LLM-judge rubrics, and a baseline-gated regression test.

The canonical sources have been read in full. The shared content (iron rules, page categories, citation convention) appears verbatim across all four agent files and belongs in shared fragments. Host-specific references are concentrated in the workflow sections of each agent file — those sections need adaptation rather than verbatim porting. The semantic rules (refusal patterns, contradictions, ADR chain health, code-drift prioritization) are role-local and compose without de-duplication.

The Phase 4 eval harness is the natural integration point. The existing `judge.py` GEval pattern using `AmazonBedrockModel` with the two-judge panel is exactly the pattern to extend. A new `divergence/` subpackage inside `eval-harness` carries per-role `DivergenceCheck` lists, rubric `.md` files, and a `DivergenceMetric` class that wraps both the programmatic pass and the GEval judge pass. The baseline JSON is a new file per role that mirrors the delta-tracking structure already implied by the Phase 4 `report.py` regression gate.

**Primary recommendation:** Build the prompts module first (Wave 1), then the programmatic check infrastructure (Wave 2), then the GEval judge integration + baseline (Wave 3), then the pytest integration gate (Wave 4). Each wave is independently committable and verifiable.

---

## Architectural Responsibility Map

| Capability | Primary Tier | Secondary Tier | Rationale |
|------------|-------------|----------------|-----------|
| Prompt constants (`*_SYSTEM` strings) | graph-wiki-agent (agent package) | — | Prompts are inputs to LLM calls; they live in the agent that makes those calls |
| Canonical source vendoring | cores/prompt-sources/ | — | Decoupled from agent package; OSS-friendly; not a workspace member |
| Divergence rule definitions | cores/eval-harness | — | Eval infrastructure; keeps eval code out of agent package |
| LLM-judge rubrics | cores/eval-harness | — | Same tier as the GEval metric that reads them |
| Baseline JSON storage | cores/eval-harness/baselines/ | — | Lives adjacent to the eval code that reads/writes it |
| Programmatic wikilink resolution | cores/eval-harness (calls vault-io) | vault-io | `_resolve_citation()` already in `structural.py`; divergence can reuse it |
| Pytest divergence gate | cores/eval-harness/tests/ | — | New test file in existing test suite; matches GRAPH_WIKI_RUN_EVAL pattern |

---

## Standard Stack

### Core (all from CLAUDE.md — already in workspace)

| Library | Version | Purpose | Status |
|---------|---------|---------|--------|
| `deepeval` | 4.0.0 | GEval metric, AmazonBedrockModel judge | Already in eval-harness deps |
| `pytest` | ≥8.3 | Test runner | Workspace dev dep |
| `syrupy` | 5.1.0 | Snapshot testing for composed prompt strings | Workspace dev dep |
| `pytest-asyncio` | 1.3.0 | Async test support | Workspace dev dep |
| `python-frontmatter` | 1.1.0 | Parse vault pages in programmatic checks | Already in eval-harness deps |
| `graph-wiki-agent` | workspace | Import `*_SYSTEM` constants, `QueryResult`, `IngestResult` | Workspace member |
| `vault-io` | workspace | `_resolve_citation`-equivalent wikilink resolution | Workspace member |

No new packages needed. All required libraries are already in the workspace.

### New Modules to Create (no new packages)

| Module | Location | Purpose |
|--------|----------|---------|
| `prompts/_fragments/` | `graph-wiki-agent/src/graph_wiki_agent/prompts/` | Shared fragment constants |
| `prompts/librarian.py` | same | Compose + export `LIBRARIAN_SYSTEM` |
| `prompts/ingestor.py` | same | Compose + export `INGESTOR_SYSTEM` |
| `prompts/linter.py` | same | Compose + export `LINTER_*_SYSTEM` (3 group prompts) |
| `prompts/scanner.py` | same | Compose + export `SCANNER_SYSTEM` |
| `prompts/synthesizer.py` | same | Relocate (no content port) `SYNTHESIZER_SYSTEM` |
| `prompts/code_reader.py` | same | Relocate (no content port) `CODE_READER_SYSTEM` |
| `cores/prompt-sources/` | workspace root | Verbatim canonical files (not a workspace member) |
| `eval_harness/divergence/` | `cores/eval-harness/src/` | Per-role rules, rubrics, metric class |
| `cores/eval-harness/baselines/divergence-*.json` | eval-harness | Per-role divergence baseline |

---

## Package Legitimacy Audit

> No new packages are installed in this phase. All dependencies are already present in the workspace. The Package Legitimacy Gate is not applicable.

**Packages added:** None.

---

## Architecture Patterns

### System Architecture Diagram

```
Canonical sources (lattice repo)
        |
        | manual re-vendor
        v
cores/prompt-sources/                     (verbatim copies, no pyproject.toml)
  SKILL.md
  agents/librarian.md
  agents/ingestor.md
  agents/linter.md
  agents/scanner.md
        |
        | porting + adaptation
        v
graph_wiki_agent/prompts/
  _fragments/
    iron_rules.py       ← shared across all 4 roles
    page_categories.py  ← shared across all 4 roles
    citation_rules.py   ← shared across librarian + ingestor
    frontmatter_rules.py← shared across ingestor + linter
  librarian.py          ← compose fragments + librarian-local rules → LIBRARIAN_SYSTEM
  ingestor.py           ← compose fragments + ingestor workflow → INGESTOR_SYSTEM
  linter.py             ← compose fragments + 3 group prompts → LINTER_*_SYSTEM × 3
  scanner.py            ← compose fragments + scanner rules → SCANNER_SYSTEM
  synthesizer.py        ← relocate only, no port
  code_reader.py        ← relocate only, no port
        |
        | import
        v
commands/{query,ingest,lint,scan}.py      (replace inline *_SYSTEM with imports)
        |
        | agent outputs
        v
eval_harness/divergence/
  __init__.py
  check.py              ← DivergenceCheck dataclass, Verdict, AgentOutputProxy
  librarian.py          ← list[DivergenceCheck] for librarian role (LIB-*)
  ingestor.py           ← list[DivergenceCheck] for ingestor role (ING-*)
  linter.py             ← list[DivergenceCheck] for linter role (LNT-*)
  scanner.py            ← list[DivergenceCheck] for scanner role (SCN-*)
  metric.py             ← DivergenceMetric (programmatic + GEval judge)
  rubrics/
    librarian.md
    ingestor.md
    linter.md
    scanner.md
        |
        | baseline gate
        v
cores/eval-harness/baselines/
  divergence-librarian.json
  divergence-ingestor.json
  divergence-linter.json
  divergence-scanner.json
        |
        | pytest gate
        v
tests/test_divergence.py                  (new test file, GRAPH_WIKI_RUN_EVAL gate)
```

### Recommended Project Structure

```
agents/graph-wiki-agent/src/graph_wiki_agent/
├── prompts/
│   ├── __init__.py
│   ├── _fragments/
│   │   ├── __init__.py
│   │   ├── iron_rules.py          # Source: cores/prompt-sources/SKILL.md
│   │   ├── page_categories.py     # Source: cores/prompt-sources/SKILL.md
│   │   ├── citation_rules.py      # Source: cores/prompt-sources/agents/librarian.md
│   │   └── frontmatter_rules.py   # Source: cores/prompt-sources/agents/ingestor.md
│   ├── librarian.py               # Composes fragments + librarian rules
│   ├── ingestor.py                # Composes fragments + ingestor workflow
│   ├── linter.py                  # Composes fragments + 3 group system prompts
│   ├── scanner.py                 # Composes fragments + scanner rules
│   ├── synthesizer.py             # Relocated (no port)
│   └── code_reader.py             # Relocated (no port)
│
cores/
├── prompt-sources/                # NO pyproject.toml — not a workspace member
│   ├── SKILL.md                   # Verbatim copy
│   └── agents/
│       ├── librarian.md
│       ├── ingestor.md
│       ├── linter.md
│       └── scanner.md
│
└── eval-harness/
    ├── baselines/
    │   ├── divergence-librarian.json
    │   ├── divergence-ingestor.json
    │   ├── divergence-linter.json
    │   └── divergence-scanner.json
    └── src/eval_harness/
        └── divergence/
            ├── __init__.py
            ├── check.py            # DivergenceCheck dataclass + Verdict
            ├── librarian.py        # LIBRARIAN_CHECKS: list[DivergenceCheck]
            ├── ingestor.py         # INGESTOR_CHECKS: list[DivergenceCheck]
            ├── linter.py           # LINTER_CHECKS: list[DivergenceCheck]
            ├── scanner.py          # SCANNER_CHECKS: list[DivergenceCheck]
            ├── metric.py           # DivergenceMetric + baseline delta logic
            └── rubrics/
                ├── librarian.md
                ├── ingestor.md
                ├── linter.md
                └── scanner.md
```

### Pattern 1: Prompt Fragment Composition

**What:** Immutable string constants assembled at import time from fragment modules. No runtime templating.

**When to use:** All role prompts. The concatenation is pure Python string joining — simple, readable, auditable.

**Example:**
```python
# Source: graph_wiki_agent/prompts/librarian.py
# This is the pattern for all per-role files.

from graph_wiki_agent.prompts._fragments.iron_rules import IRON_RULES
from graph_wiki_agent.prompts._fragments.page_categories import PAGE_CATEGORIES
from graph_wiki_agent.prompts._fragments.citation_rules import CITATION_RULES

LIBRARIAN_SYSTEM = "\n\n".join([
    "You are a wiki librarian. ...",    # role-local intro (adapted from librarian.md ## Role)
    IRON_RULES,                          # shared fragment
    PAGE_CATEGORIES,                     # shared fragment
    CITATION_RULES,                      # shared fragment
    "## Red flags\n...",                 # role-local, adapted from librarian.md ## Red flags
])
```

**Example fragment file:**
```python
# Source: cores/prompt-sources/SKILL.md
# Anchor: ## Iron rules (L193-L201)
# Source-commit: 6708f31

IRON_RULES = """\
## Iron rules

1. The code is the source of truth. If the vault contradicts the code, the code wins.
2. The LLM never edits files in raw/.
3. All LLM writes for the wiki go under <workspace>/wiki/. ...
4. Every vault page has YAML frontmatter with title, category, summary, updated.
5. Every ingest or scan touches >= 3 files: the changed/new page(s), index.md, log.md.
6. Every claim on a package/domain page cites either a source page or a code path.
7. Good query answers get filed back — explorations compound.
"""
```

### Pattern 2: DivergenceCheck Dataclass

**What:** A dataclass pairing a rule ID and severity with a callable that inspects agent output against a vault path.

**When to use:** All programmatic divergence rules. Callable-per-rule pattern enables independent unit testing.

**Example:**
```python
# Source: cores/eval-harness/src/eval_harness/divergence/check.py

from dataclasses import dataclass
from typing import Callable, NamedTuple
from pathlib import Path

class Verdict(NamedTuple):
    passed: bool
    excerpt: str  # evidence for accepted_failures array

@dataclass
class DivergenceCheck:
    id: str             # e.g. "LIB-001-wikilink-resolves"
    source_anchor: str  # e.g. "cores/prompt-sources/SKILL.md#iron-rules"
    severity: str       # "hard" | "soft"
    check: Callable[["AgentOutputProxy", Path], Verdict]
```

**Example check (LIB-001):**
```python
# cores/eval-harness/src/eval_harness/divergence/librarian.py

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
    # LIB-002-citation-present, LIB-003-refusal-when-no-evidence, ...
]
```

### Pattern 3: DivergenceMetric Integration with deepeval GEval

**What:** A metric class wrapping both programmatic checks and a GEval judge call. Called via `deepeval.assert_test` inside pytest, consistent with the Phase 4 pattern.

**When to use:** The eval gate test that runs all role checks against each fixture.

**Example:**
```python
# cores/eval-harness/src/eval_harness/divergence/metric.py

from deepeval.metrics import GEval
from deepeval.models import AmazonBedrockModel
from deepeval.test_case import LLMTestCase, SingleTurnParams

class DivergenceMetric:
    """Hybrid programmatic + LLM-judge divergence detection."""

    def __init__(
        self,
        role: str,
        checks: list[DivergenceCheck],
        rubric_path: Path,
        vault: Path,
    ):
        self.role = role
        self.checks = checks
        self._rubric = rubric_path.read_text()
        self._vault = vault

    def run_programmatic(self, output: AgentOutputProxy) -> list[tuple[DivergenceCheck, Verdict]]:
        return [(c, c.check(output, self._vault)) for c in self.checks]

    def run_judge(self, output: AgentOutputProxy, query: str) -> float:
        """Return 0.0-1.0 judge score (1.0 = no divergence)."""
        for cfg in JUDGE_PANEL_CONFIG:
            judge = make_judge(cfg)
            metric = GEval(
                name=f"divergence_{self.role}",
                criteria=self._rubric,
                evaluation_params=[SingleTurnParams.INPUT, SingleTurnParams.ACTUAL_OUTPUT],
                model=judge,  # ALWAYS explicit — never let deepeval default to OpenAI
                threshold=0.5,
            )
            tc = LLMTestCase(input=query, actual_output=output.answer)
            metric.measure(tc)
            # ... aggregate across panel
        return mean_score
```

### Pattern 4: Baseline Delta Logic

**What:** Load per-role baseline JSON, compute failure deltas per rule ID, gate hard-severity failures.

**When to use:** Every divergence eval run (unless `--accept-divergence-baseline` is passed).

**Example:**
```python
# cores/eval-harness/src/eval_harness/divergence/metric.py

def load_baseline(role: str, baselines_dir: Path) -> dict:
    path = baselines_dir / f"divergence-{role}.json"
    if not path.exists():
        return {}
    return json.loads(path.read_text())

def write_baseline(role: str, baselines_dir: Path, checks_data: dict, agent_commit: str):
    baseline = {
        "role": role,
        "recorded_at": datetime.now(tz=timezone.utc).isoformat(),
        "agent_commit": agent_commit,
        "checks": checks_data,  # {rule_id: {runs, failures, accepted_failures}}
    }
    path = baselines_dir / f"divergence-{role}.json"
    path.write_text(json.dumps(baseline, indent=2) + "\n")

def check_regression(role: str, current: dict, baseline: dict) -> None:
    """Raise AssertionError if hard-severity failures exceed baseline."""
    for rule_id, current_data in current.items():
        baseline_data = baseline.get("checks", {}).get(rule_id, {})
        baseline_failures = baseline_data.get("failures", 0)
        current_failures = current_data.get("failures", 0)
        # Only gate hard-severity checks
        severity = _get_severity(role, rule_id)
        if severity == "hard" and current_failures > baseline_failures:
            raise AssertionError(
                f"[{role}] {rule_id}: {current_failures} failures > "
                f"baseline {baseline_failures}. "
                "Run with --accept-divergence-baseline to accept."
            )
```

### Anti-Patterns to Avoid

- **Runtime string assembly:** Building the system prompt at call time (e.g., with template variables) introduces non-determinism and breaks snapshot tests. Build at import time; the string is frozen.
- **Reusing GEval instances across calls:** deepeval's GEval accumulates internal state. Per the existing `judge.py` pattern, create fresh instances per call.
- **Putting judge rubric text inline in Python:** Rubric `.md` files are human-reviewable and linkable to source anchors. Keep them in files under `rubrics/`.
- **Adding `pyproject.toml` to `cores/prompt-sources/`:** If a `pyproject.toml` exists in that directory, uv's `members = ["cores/*"]` glob will try to make it a workspace member. Use a bare directory with no `pyproject.toml`.
- **Importing from `cores/prompt-sources/` in Python:** The vendored directory is documentation, not importable code. Python code reads canonical text only from fragment `.py` files, which carry the text as string constants.
- **Using the `Vault` type as a function parameter name when you mean `Path`:** The divergence checks take `vault: Path` (the path to the vault root), not a hypothetical `Vault` class. vault-io does not expose a `Vault` class; its functions take `Path` arguments.

---

## Source File Content Analysis (PORT-01 Traceability)

### What Belongs in Shared Fragments

Verified by reading SKILL.md, librarian.md, ingestor.md, linter.md, and scanner.md in full.

**Fragment: `_fragments/iron_rules.py`** — shared by all 4 roles
- Source: `SKILL.md` §Iron rules (L193-L201): 7 numbered rules, verbatim across all roles
- All four agent files invoke the `lattice-wiki` skill which carries these rules
- Adaptation needed: none for rules themselves; references to `<workspace>/wiki/` and `<workspace>/raw/` remain accurate for graph-wiki-agent

**Fragment: `_fragments/page_categories.py`** — shared by librarian + ingestor + scanner
- Source: `SKILL.md` §Page categories table (L143-L156): 9 category rows (app, package, domain, concept, dependency, work, source, architecture, adr)
- Used by librarian (drill direction), ingestor (routing), scanner (stub creation)
- Adaptation needed: `<workspace>/wiki/` paths → graph-wiki-agent's vault path convention; `<workspace>/work/` references note that work items are a separate ingest path

**Fragment: `_fragments/citation_rules.py`** — shared by librarian + ingestor
- Source: `agents/librarian.md` §Rules bullets 3-4 (L73-L77): "Every claim cites" and wikilink syntax rules
- Source: `agents/ingestor.md` §Rules bullet "Cite aggressively" (L101): same rule
- Adaptation needed: slash command references removed; the citation convention is host-agnostic

**Fragment: `_fragments/frontmatter_rules.py`** — shared by ingestor + scanner
- Source: `agents/ingestor.md` §Workflow step 4 (L50-L58): required frontmatter fields for source summary pages
- Source: `agents/scanner.md` §Workflow step 3 (L47-L48): frontmatter fields for stub pages
- Adaptation needed: field names match graph-wiki-agent's INGESTOR_SYSTEM field list (title, category, page_type, target_slug, summary, tags)

### Role-Local Content (not shared)

**Librarian-local:**
- Workflow: read index first → drill 3-10 pages → follow wikilinks → fall back to code → synthesize → offer to file back
- Source: `agents/librarian.md` §Workflow (L29-L72)
- Adaptation: `python ${CLAUDE_PLUGIN_ROOT}/skills/lattice-wiki/scripts/wiki_search.py` → `bm25_query()` (already called by the harness); offer-to-file-back workflow → omit (not implemented in v1; graph-wiki-agent returns results, not interactive)
- Keep: "Read the index first", "Every claim cites", "If the vault doesn't know, say so", sentinel `NO_RELEVANT_CONTENT` behavior (already in existing LIBRARIAN_SYSTEM — preserve)
- Red flags: 4 items (librarian.md §Red flags) — all portable verbatim

**Ingestor-local:**
- Workflow: prep script → discuss → write source summary → update pages → ADR capture → flag contradictions → update index/log
- Source: `agents/ingestor.md` §Workflow steps 1-12 (L27-L92)
- Adaptation: `python ${CLAUDE_PLUGIN_ROOT}/.../ingest_source.py` → the harness calls `extract()` before the LLM; interactive discussion loop → omit (graph-wiki-agent is non-interactive); `update_index.py` shell call → `update_index(wiki)` already called post-write
- Keep: page-type routing table (package/concept/adr), source_type discrimination (spec vs article vs PR vs doc), minimum-3-touches rule, cite-aggressively rule
- Red flags: 4 items (ingestor.md §Red flags) — adapt: replace path references with graph-wiki-agent vault structure

**Linter-local (3 groups preserved):**
- Pass 1: mechanical (scripts in lattice-wiki → inline scan port already done in `run_lint`); the semantic content to port is the check *names* and *prioritization*
- Pass 2: semantic checks (contradictions, stale claims, concept gaps, ADR chain health, cross-reference gaps, index drift) — these map to the 3 existing linter group prompts
- Source: `agents/linter.md` §Pass 1-3 (L26-L92), §Rules (L93-L101)
- Adaptation: shell script calls → already handled by `run_lint()` mechanical pass; the 3 group prompts need the full semantic check lists from linter.md §Pass 2 (currently abbreviated in existing prompts)
- Key gap in current prompts: `LINTER_PAGE_QUALITY_SYSTEM` is 5 bullets; the canonical source has 9 semantic check categories. Content port expands coverage.
- Prioritization rule: "Code drift > contradictions > broken links > orphans > stale > style" — must appear in the system prompts

**Scanner-local:**
- Workflow: discover workspaces → present diff → create stubs → per-package change review → state gate logic → update index → stamp tokens → log
- Source: `agents/scanner.md` §Workflow steps 1-10 (L26-L99)
- Adaptation: `python ${CLAUDE_PLUGIN_ROOT}/.../scan_monorepo.py` → `discover_workspaces()` (already called by `run_scan`); state_gate / `last_sync_commit` → `scan_monorepo.compute_state_gate()` (already implemented); `update_tokens.py` → `update_tokens` not yet implemented (check if needed for prompt or just note)
- Keep: "Don't overwrite prose", "Confirm renames and deletions", "Only stub actual workspace entries", "Dependency-only frontmatter updates don't need confirmation"
- Red flags: 3 items — all portable verbatim

---

## Adaptation Map (HOST-SPECIFIC REFERENCES TO REWRITE)

### References present in lattice-wiki source files that DO NOT apply to graph-wiki-agent:

| Source Reference | File | Replacement for graph-wiki-agent |
|-----------------|------|-------------------------------|
| `python ${CLAUDE_PLUGIN_ROOT}/skills/lattice-wiki/scripts/wiki_search.py` | librarian.md L51 | Omit — `bm25_query()` is called by the harness before the librarian subagent receives results |
| `python ${CLAUDE_PLUGIN_ROOT}/skills/lattice-wiki/scripts/ingest_source.py` | ingestor.md L29 | Omit — `extract()` called before LLM |
| `python ${CLAUDE_PLUGIN_ROOT}/skills/lattice-wiki/scripts/update_index.py` | ingestor.md L80, scanner.md L82 | Omit — `update_index(wiki)` called post-write by command layer |
| `python ${CLAUDE_PLUGIN_ROOT}/skills/lattice-wiki/scripts/append_log.py` | ingestor.md L85, linter.md L91, scanner.md L88 | Omit — `append_log()` called post-operation |
| `python ${CLAUDE_PLUGIN_ROOT}/skills/lattice-wiki/scripts/update_tokens.py` | scanner.md L87 | Omit — not implemented; add note in scanner prompt |
| `python ${CLAUDE_PLUGIN_ROOT}/skills/lattice-wiki/scripts/lint_wiki.py` | linter.md L29 | Omit — `run_lint()` mechanical pass handles this |
| `python ${CLAUDE_PLUGIN_ROOT}/skills/lattice-wiki/scripts/graph_analyzer.py` | linter.md L30 | Omit — graph analysis deferred |
| `/lattice-wiki:ingest <path>` slash command | linter.md L43 | Replace: "re-ingest via `wiki_ingest`" |
| `/lattice-wiki:scan` | linter.md L36, linter.md L79 | Replace: "re-run `wiki_scan`" |
| `skills: [lattice-wiki, obsidian-markdown]` frontmatter | all agents | Omit — not a skill invocation mechanism in graph-wiki-agent |
| `tools: [Read, Write, Edit, Bash, Grep, Glob]` frontmatter | all agents | Omit — not applicable to deepagents LangGraph tool surface |
| Interactive discussion loops (§Discuss, "Wait for confirmation") | ingestor.md L39-45 | Omit — graph-wiki-agent is non-interactive; omit confirmation gates |
| "Offer to file back" / "Suggest where to file" | librarian.md L62-L70 | Omit — librarian returns read-only synthesis; no write-back in v1 |
| Obsidian-specific syntax invocations (`obsidian-markdown` skill) | all agents | Omit — output goes to vault files; relevant wikilink conventions preserved as rules, but skill invocation is not applicable |
| `context: fork` agent pattern | all agents | Omit — not applicable |
| `<workspace>/wiki/` | all agents | Replace: `vault_path` (the resolved wiki root) |
| `<workspace>/raw/` | ingestor.md | Keep conceptually; replace path with: "sources staged for ingest" |
| "Vote to file" interactive patterns | librarian.md | Omit |

### References to PRESERVE verbatim (semantically canonical):

- Iron rules 1-7 (SKILL.md)
- Page category table (SKILL.md)
- Wikilink syntax convention (`[[wikilink]]`)
- Citation rules ("every claim cites...")
- `NO_RELEVANT_CONTENT` sentinel (already in existing LIBRARIAN_SYSTEM — do not change)
- Frontmatter required fields (title, category, summary, updated)
- Minimum-3-touches rule (ingestor)
- "Don't overwrite prose" rule (scanner)
- Prioritization order for linter: code drift > contradictions > broken links > orphans > stale > style
- Red flags sections from all four agents

---

## Divergence Check Inventory

### Programmatic checks (deterministic, O(1) per output)

**Librarian (LIB-*)**
| Rule ID | What it checks | Severity | Source Anchor |
|---------|---------------|----------|---------------|
| LIB-001-wikilink-resolves | Every `[[wikilink]]` in answer resolves to a `.md` file in vault | hard | SKILL.md#iron-rules |
| LIB-002-citation-present | Answer contains at least one citation | hard | agents/librarian.md#rules |
| LIB-003-no-slug-only-wikilinks | No wikilinks of form `[[PackageName]]` without path prefix | hard | agents/librarian.md#rules |
| LIB-004-code-path-format | Code paths cited as `` `path:line` `` not bare text | soft | agents/librarian.md#rules |

**Ingestor (ING-*)**
| Rule ID | What it checks | Severity | Source Anchor |
|---------|---------------|----------|---------------|
| ING-001-frontmatter-present | LLM output contains `---` delimited YAML frontmatter | hard | agents/ingestor.md#workflow-step-4 |
| ING-002-required-fields | title, category, page_type, target_slug, summary all present | hard | agents/ingestor.md#workflow-step-4 |
| ING-003-page-type-routing | page_type is one of: package, concept, adr, source | hard | SKILL.md#page-categories |
| ING-004-page-type-valid-category | category matches page_type (e.g. category:source ↔ page_type:source) | hard | agents/ingestor.md#rules |

**Linter (LNT-*)**
| Rule ID | What it checks | Severity | Source Anchor |
|---------|---------------|----------|---------------|
| LNT-001-code-drift-first | Code-drift finding appears in findings before orphan/stale findings | soft | agents/linter.md#rules |
| LNT-002-findings-nonempty-when-issues | Findings list not empty when vault has known issues (fixture-anchored) | hard | agents/linter.md#workflow-pass-3 |
| LNT-003-no-silent-fix | LLM does not include write operations in output (report only) | hard | agents/linter.md#rules |

**Scanner (SCN-*)**
| Rule ID | What it checks | Severity | Source Anchor |
|---------|---------------|----------|---------------|
| SCN-001-frontmatter-present | Stub output contains YAML frontmatter | hard | agents/scanner.md#workflow-step-3 |
| SCN-002-required-fields | title, category, summary, package_path, language present | hard | agents/scanner.md#workflow-step-3 |
| SCN-003-no-file-map-section | Output does not contain `## File map` section (added by pipeline) | hard | agents/scanner.md (SCANNER_SYSTEM header) |
| SCN-004-overview-present | Output contains `## Overview` section | hard | agents/scanner.md#workflow-step-3 |

### LLM-judge checks (soft severity, rubric-driven)

The judge evaluates the overall response quality against the rubric for:
- **Librarian:** refusal when vault evidence is absent (LIB-005-refusal-pattern); no-invention of symbols (LIB-006-no-invention)
- **Ingestor:** cite-aggressively rule observed (ING-005-citation-density); contradiction-flagging present when applicable (ING-006-flag-contradictions)
- **Linter:** semantic pass coverage (LNT-004-semantic-completeness); suggestions present (LNT-005-suggestions-present)
- **Scanner:** prose sections not overwritten (SCN-005-no-prose-overwrite); "Don't overwrite prose" observed

---

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Wikilink resolution | Custom path resolver | `_resolve_citation()` in `eval_harness/structural.py` | Already handles exact + glob fallback |
| GEval judge | Custom LLM scoring | `GEval` + `AmazonBedrockModel` from deepeval | Established in Phase 4; proven pattern |
| Prompt templating | f-string templates at call time | Import-time string concatenation | Runtime assembly breaks snapshot tests; fragments are simpler |
| Vault page parsing | Custom YAML parser | `python-frontmatter` | Already in eval-harness deps; handles edge cases |
| Test isolation for eval | Custom temp-dir setup | `EvalWorktree` context manager | Already in `isolation.py`; thread-safe, auto-cleanup |
| Baseline delta tracking | Custom diff algorithm | Simple int comparison per rule_id | Deltas are per-rule failure counts; dict subtraction is sufficient |

**Key insight:** All infrastructure exists. The divergence subpackage is new wiring on top of existing deepeval, vault-io, and structural-check patterns. Do not reinvent any of these.

---

## Common Pitfalls

### Pitfall 1: Token Budget Blow-Up from Composed Prompts

**What goes wrong:** Naively copying all workflow steps from lattice-wiki's verbose agent files creates system prompts that are 2000-4000 tokens. This is fine for correctness but hits Bedrock's cross-region inference profile context limits at high fan-out.

**Why it happens:** lattice-wiki's agent files are richly detailed because they guide a human-assisted interactive flow. graph-wiki-agent's LLM calls are single-turn subagent calls with tight output targets.

**How to avoid:** Preserve rules and semantic content verbatim. Trim workflow steps that describe orchestration already handled by the command layer (script calls, index updates, log appends). The existing SCANNER_SYSTEM at ~115 tokens is a calibration target — the ported version should stay under ~400 tokens for non-linter roles, and under ~300 tokens per group for linter (3 groups).

**Warning signs:** Any fragment that contains more than 5 workflow steps is including orchestration prose that belongs in the command layer, not the LLM prompt.

### Pitfall 2: Judge Non-Determinism on Soft Checks

**What goes wrong:** GEval scores for soft-severity semantic checks vary run-to-run, causing soft checks to flip between pass/fail and making the baseline meaningless.

**Why it happens:** LLM judges at temperature=0 are still non-deterministic at the token-sampling boundary.

**How to avoid:** Soft-severity checks do not trigger the hard regression gate. The baseline tracks failure counts but the gate only fires when `current_failures > baseline_failures` for `severity == "hard"`. Soft failures are reported in `accepted_failures` but never cause pytest to fail. The design in D-12 already encodes this correctly.

**Warning signs:** If a soft check's baseline `failures` count oscillates by more than 1 across identical runs, consider demoting it to report-only (no Verdict gate), or increasing the fixture sample size.

### Pitfall 3: Workspace Member Collision for cores/prompt-sources/

**What goes wrong:** Adding a `pyproject.toml` to `cores/prompt-sources/` causes uv to include it in the workspace member list (`members = ["cores/*"]`), which then fails `uv sync` because the package has no valid build target.

**Why it happens:** `cores/*` glob in the workspace root `pyproject.toml` matches any directory with a `pyproject.toml`.

**How to avoid:** `cores/prompt-sources/` must NOT have a `pyproject.toml`. Confirmed: the directory is documentation/vendored content, not a Python package. It is read by humans and referenced in provenance comments, never imported as Python.

**Warning signs:** `uv sync` emitting `error: No `pyproject.toml` found` or similar for `prompt-sources`.

### Pitfall 4: Stale Provenance SHAs After Re-Vendor

**What goes wrong:** After re-vendoring `cores/prompt-sources/` from an updated lattice commit, the `# Source-commit:` headers in fragment files still point to the old SHA. A reviewer can't tell whether the fragment is in sync.

**Why it happens:** Manual re-vendor process; no automated SHA update.

**How to avoid:** Document the re-vendor procedure: (1) copy files, (2) `git -C /path/to/lattice log --oneline -1 -- <file>` to get the file's latest commit SHA, (3) update all affected `# Source-commit:` headers. A Wave 0 test that checks the header format (but not SHA validity) catches format drift without requiring the lattice repo to be present.

**Warning signs:** Fragment files with `# Source-commit: <SHA>` that doesn't match the SHA of any vendored file's last modification — this is detectable via `git -C cores/prompt-sources log`.

### Pitfall 5: Baseline Does Not Exist on First Run

**What goes wrong:** The first time the divergence eval runs, `divergence-{role}.json` doesn't exist. The regression check raises a KeyError or AssertionError against an empty dict.

**Why it happens:** Baseline is created by `--accept-divergence-baseline`; that flag must be passed on the first run.

**How to avoid:** `load_baseline()` returns an empty dict when the file doesn't exist. The delta logic treats a missing baseline as `failures=0` for all rules, which means the first run always passes (any failures on first run become the new baseline after the flag is used). Document this in the Wave 0 setup step.

**Warning signs:** `FileNotFoundError` on `baselines/divergence-{role}.json` — handle with `if not path.exists(): return {}`.

---

## Code Examples

### Provenance Header Format (locked)

```python
# Source: cores/prompt-sources/SKILL.md
# Anchor: ## Iron rules (L193-L201)
# Source-commit: 6708f31

IRON_RULES = """..."""
```

### Import Pattern at Call Site

```python
# agents/graph-wiki-agent/src/graph_wiki_agent/commands/query.py
# Before (current):
LIBRARIAN_SYSTEM = """..."""  # inline

# After (phase 6):
from graph_wiki_agent.prompts.librarian import LIBRARIAN_SYSTEM  # noqa: F401
```

No other changes to the call sites — `SystemMessage(content=LIBRARIAN_SYSTEM)` usage is unchanged.

### GEval Judge in DivergenceMetric (key integration point)

```python
# cores/eval-harness/src/eval_harness/divergence/metric.py

from eval_harness.judge import make_judge, JUDGE_PANEL_CONFIG
from deepeval.metrics import GEval
from deepeval.test_case import LLMTestCase, SingleTurnParams

def _judge_score(rubric_text: str, query: str, answer: str) -> float:
    scores = []
    for cfg in JUDGE_PANEL_CONFIG:
        judge = make_judge(cfg)          # reuses existing Phase 4 factory
        metric = GEval(
            name="divergence_judge",
            criteria=rubric_text,        # loaded from rubrics/{role}.md
            evaluation_params=[SingleTurnParams.INPUT, SingleTurnParams.ACTUAL_OUTPUT],
            model=judge,                 # ALWAYS explicit — never let deepeval default to OpenAI
            threshold=0.5,
        )
        tc = LLMTestCase(input=query, actual_output=answer)
        metric.measure(tc)
        scores.append(metric.score)
    return sum(scores) / len(scores)
```

### pytest Divergence Gate Test (GRAPH_WIKI_RUN_EVAL pattern)

```python
# cores/eval-harness/tests/test_divergence.py

import os, json
from pathlib import Path
import pytest
from eval_harness.divergence.metric import DivergenceMetric, load_baseline, check_regression

EVAL_GATE = pytest.mark.skipif(
    not os.environ.get("GRAPH_WIKI_RUN_EVAL"),
    reason="Set GRAPH_WIKI_RUN_EVAL=1 to run divergence eval",
)
BASELINES_DIR = Path(__file__).parent.parent / "baselines"

@pytest.fixture
def fixture_vault(tmp_path):
    ...  # copy round-trip-vault to tmp_path

@EVAL_GATE
@pytest.mark.parametrize("role", ["librarian", "ingestor", "linter", "scanner"])
def test_divergence_regression(role, fixture_vault, accept_baseline):
    from eval_harness.divergence import ROLE_CHECKS, ROLE_RUBRICS
    metric = DivergenceMetric(role, ROLE_CHECKS[role], ROLE_RUBRICS[role], fixture_vault)
    results = metric.run(...)  # returns {rule_id: {runs, failures, accepted_failures}}

    baseline = load_baseline(role, BASELINES_DIR)
    if accept_baseline:
        write_baseline(role, BASELINES_DIR, results, ...)
        return

    check_regression(role, results, baseline)  # raises AssertionError on hard regression
```

### --accept-divergence-baseline CLI hook

The `--accept-divergence-baseline` flag hooks into pytest via a custom `conftest.py` option, consistent with the existing `GRAPH_WIKI_RUN_EVAL` pattern:

```python
# cores/eval-harness/tests/conftest.py (addition)

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

### Syrupy Snapshot Test for Composed Prompt

```python
# agents/graph-wiki-agent/tests/prompts/test_prompt_snapshots.py

from syrupy.assertion import SnapshotAssertion
from graph_wiki_agent.prompts.librarian import LIBRARIAN_SYSTEM
from graph_wiki_agent.prompts.ingestor import INGESTOR_SYSTEM
from graph_wiki_agent.prompts.linter import LINTER_PAGE_QUALITY_SYSTEM
from graph_wiki_agent.prompts.scanner import SCANNER_SYSTEM

def test_librarian_system_snapshot(snapshot: SnapshotAssertion):
    assert LIBRARIAN_SYSTEM == snapshot

def test_ingestor_system_snapshot(snapshot: SnapshotAssertion):
    assert INGESTOR_SYSTEM == snapshot

# ... etc for all roles
```

First run with `--snapshot-update` records the expected string. Subsequent runs fail if the composed prompt drifts without a deliberate update.

---

## Runtime State Inventory

> This is not a rename/refactor phase in the classical sense. No stored runtime data carries the prompt text at rest (prompts live in Python source, not databases). The inventory below confirms no runtime state migration is needed.

| Category | Items Found | Action Required |
|----------|-------------|-----------------|
| Stored data | None — `*_SYSTEM` strings are Python constants, not stored in any DB or JSONL | None |
| Live service config | None — model IDs and role configs live in `models.toml`, not affected | None |
| OS-registered state | None | None |
| Secrets/env vars | None | None |
| Build artifacts | None — refactoring import paths; `uv sync` rebuilds editable installs automatically | Verify `uv sync` after adding `prompts/` module |

No data migration required. This is a source-code refactor + new module addition.

---

## Assumptions Log

| # | Claim | Section | Risk if Wrong |
|---|-------|---------|---------------|
| A1 | `cores/prompt-sources/` must have no `pyproject.toml` to avoid workspace collision | Architecture Patterns | uv sync would fail; easy to fix by removing the file |
| A2 | The existing `_resolve_citation()` in `structural.py` is sufficient for wikilink resolution in divergence checks | Don't Hand-Roll | If the resolution logic needs updating, the fix is local to structural.py and benefits both eval paths |
| A3 | `update_tokens.py` referenced in scanner.md is not yet implemented in graph-wiki-agent; prompt should omit that step | Adaptation Map | If it exists, the scanner prompt should mention it; verify with `ls vault-io/src/vault_io/` |
| A4 | The `obsidian-markdown` skill invocation in lattice-wiki is not applicable to graph-wiki-agent (no skill registry) | Adaptation Map | Not applicable; confirmed by graph-wiki-agent architecture |
| A5 | All divergence check rule IDs using prefix `LNT` for linter and `SCN` for scanner (not `LINT`/`SCAN`) | Divergence Check Inventory | Cosmetic only; rename if convention differs |

**Verified:** `update_tokens.py` does exist in vault-io (`ls /Users/pat/Personal/deep-agents/cores/vault-io/src/vault_io/` shows `update_tokens.py`). A3 should be REVISED: `update_tokens` is available. The scanner prompt can reference it, but check whether `run_scan()` already calls it.

---

## Open Questions

1. **Does `run_scan()` already call `update_tokens`?**
   - What we know: `update_tokens.py` exists in vault-io; scanner.md calls it in step 8
   - What's unclear: whether `commands/scan.py` calls it after `update_index`
   - Recommendation: Grep `run_scan` for `update_tokens` during plan task. If not called, add the call as part of the scanner prompt port (or note the gap).

2. **AgentOutputProxy shape**
   - What we know: `DivergenceCheck.check` takes an `AgentOutputProxy` and a `Path`
   - What's unclear: whether to wrap `QueryResult`, `IngestResult`, `LintResult`, `ScanResult` separately or use a common protocol
   - Recommendation: Define `AgentOutputProxy` as a simple dataclass with `answer: str` (and optionally `page_type: str` for ingestor checks). Each command's result maps to it at the test boundary.

3. **Fixture additions needed for divergence checks**
   - What we know: 3 fixture vaults exist (round-trip-vault, edge-case-vault, single-package-vault); 4 query cases
   - What's unclear: which existing fixtures exercise the specific divergence checks (e.g., no-evidence query for LIB-003, malformed page for ING-002)
   - Recommendation: Planner adds these as Wave 0 tasks: (a) a "no-evidence" query case where the vault genuinely doesn't know the answer (to exercise refusal-pattern check); (b) an ingest fixture with ambiguous page_type to exercise ING-003.

---

## Environment Availability

| Dependency | Required By | Available | Version | Fallback |
|------------|------------|-----------|---------|----------|
| Python 3.11 | All code | ✓ | checked via workspace | — |
| `deepeval` | DivergenceMetric GEval judge | ✓ | 4.0.0 (in eval-harness deps) | — |
| `syrupy` | Prompt snapshot tests | ✓ | 5.1.0 (workspace dev dep) | — |
| `pytest-asyncio` | Async test support | ✓ | 1.3.0 (workspace dev dep) | — |
| `python-frontmatter` | Vault page parsing in checks | ✓ | 1.1.0 (in eval-harness deps) | — |
| AWS Bedrock credentials | GEval judge calls (GRAPH_WIKI_RUN_EVAL=1) | assumed ✓ | — | Programmatic checks run without Bedrock |
| `lattice` sibling repo | Vendoring step only (Wave 0) | ✓ | at `/Users/pat/Personal/lattice` | — |

**Missing dependencies with no fallback:** None.

**Missing dependencies with fallback:** AWS Bedrock (judge path) — programmatic checks and snapshot tests run without Bedrock; judge path is gated behind `GRAPH_WIKI_RUN_EVAL=1`.

---

## Validation Architecture

### Test Framework

| Property | Value |
|----------|-------|
| Framework | pytest ≥8.3 + pytest-asyncio 1.3.0 + syrupy 5.1.0 |
| Config file | workspace root `pyproject.toml` (`asyncio_mode = "auto"`) |
| Quick run command | `uv run pytest agents/graph-wiki-agent/tests/prompts/ cores/eval-harness/tests/test_divergence.py -x -q` |
| Full suite command | `GRAPH_WIKI_RUN_EVAL=1 uv run pytest cores/eval-harness/tests/ -x -q` |

### Phase Requirements → Test Map

| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| PORT-01 | Traceability table exists (provenance headers in every fragment) | unit (provenance header check) | `pytest agents/graph-wiki-agent/tests/prompts/test_provenance.py -x` | ❌ Wave 0 |
| PORT-02 | LIBRARIAN_SYSTEM contains iron rules and citation rules | snapshot | `pytest agents/graph-wiki-agent/tests/prompts/test_prompt_snapshots.py::test_librarian_system_snapshot -x` | ❌ Wave 0 |
| PORT-03 | INGESTOR_SYSTEM contains page-type routing | snapshot | `pytest agents/graph-wiki-agent/tests/prompts/test_prompt_snapshots.py::test_ingestor_system_snapshot -x` | ❌ Wave 0 |
| PORT-04 | LINTER_*_SYSTEM prompts contain canonical lint categories | snapshot | `pytest agents/graph-wiki-agent/tests/prompts/test_prompt_snapshots.py::test_linter_*_snapshot -x` | ❌ Wave 0 |
| PORT-05 | SCANNER_SYSTEM contains package-detection rules | snapshot | `pytest agents/graph-wiki-agent/tests/prompts/test_prompt_snapshots.py::test_scanner_system_snapshot -x` | ❌ Wave 0 |
| PORT-06 | Every fragment file has 3-line provenance header; Source: path resolves to `cores/prompt-sources/` | unit | `pytest agents/graph-wiki-agent/tests/prompts/test_provenance.py -x` | ❌ Wave 0 |
| EVAL-11 | DivergenceCheck.check callables pass on valid output, fail on violations | unit per check | `pytest cores/eval-harness/tests/test_divergence_checks.py -x` | ❌ Wave 0 |
| EVAL-12 | Divergence eval emits per-role counts + accepted_failures | integration (GRAPH_WIKI_RUN_EVAL) | `GRAPH_WIKI_RUN_EVAL=1 pytest cores/eval-harness/tests/test_divergence.py -x` | ❌ Wave 0 |
| EVAL-13 | `--accept-divergence-baseline` rewrites baseline; default run gates hard-severity failures | unit (baseline delta) | `pytest cores/eval-harness/tests/test_divergence_baseline.py -x` | ❌ Wave 0 |

### Sampling Rate

- **Per task commit:** `uv run pytest agents/graph-wiki-agent/tests/prompts/ -x -q`
- **Per wave merge:** `uv run pytest agents/graph-wiki-agent/tests/ cores/eval-harness/tests/test_divergence_checks.py cores/eval-harness/tests/test_divergence_baseline.py -x -q`
- **Phase gate:** Full suite including `GRAPH_WIKI_RUN_EVAL=1` eval path before `/gsd:verify-work`

### Wave 0 Gaps

- [ ] `agents/graph-wiki-agent/tests/prompts/__init__.py` — test package
- [ ] `agents/graph-wiki-agent/tests/prompts/test_prompt_snapshots.py` — syrupy snapshot tests for all 6 role files (librarian, ingestor, linter ×3, scanner, synthesizer, code_reader)
- [ ] `agents/graph-wiki-agent/tests/prompts/test_provenance.py` — checks every `_fragments/*.py` file has the 3-line provenance header and Source: path resolves within `cores/prompt-sources/`
- [ ] `cores/eval-harness/tests/test_divergence_checks.py` — unit tests for each `DivergenceCheck.check` callable against synthetic fixtures (no Bedrock)
- [ ] `cores/eval-harness/tests/test_divergence_baseline.py` — unit tests for `load_baseline`, `write_baseline`, `check_regression` without Bedrock
- [ ] `cores/eval-harness/tests/test_divergence.py` — integration test gated behind `GRAPH_WIKI_RUN_EVAL=1`; exercises full DivergenceMetric (programmatic + judge) against fixture vault

---

## Security Domain

> `security_enforcement` not explicitly set to false; treat as enabled.

### Applicable ASVS Categories

| ASVS Category | Applies | Standard Control |
|---------------|---------|-----------------|
| V2 Authentication | no | — |
| V3 Session Management | no | — |
| V4 Access Control | no | — |
| V5 Input Validation | yes (baseline JSON loading, rule-id parsing) | `json.load()` with type checks; rule IDs are hardcoded strings, not user input |
| V6 Cryptography | no | — |

### Known Threat Patterns for this stack

| Pattern | STRIDE | Standard Mitigation |
|---------|--------|---------------------|
| Prompt injection via vendored source content | Tampering | Vendored files are read-only text constants; fragment strings are assigned at import time, not user-provided |
| Path traversal in `_resolve_citation()` | Tampering | Existing `structural.py` implementation uses `vault_path.glob()` anchored to vault root |
| Baseline JSON tamper | Tampering | Baseline files are committed to git; integrity is git's concern, not runtime validation |
| OpenAI default fallback in GEval | Elevation of Privilege (cost) | Always pass `model=judge` explicitly — documented in existing `judge.py` and must be followed in `metric.py` |

---

## Sources

### Primary (HIGH confidence — verified by direct file read)

- `/Users/pat/Personal/lattice/plugins/lattice-wiki/skills/lattice-wiki/SKILL.md` — iron rules, page categories, sub-agents, architecture (read in full)
- `/Users/pat/Personal/lattice/plugins/lattice-wiki/agents/librarian.md` — librarian workflow, rules, red flags (read in full)
- `/Users/pat/Personal/lattice/plugins/lattice-wiki/agents/ingestor.md` — ingestor workflow, rules, red flags (read in full)
- `/Users/pat/Personal/lattice/plugins/lattice-wiki/agents/linter.md` — linter 3-pass structure, rules, red flags (read in full)
- `/Users/pat/Personal/lattice/plugins/lattice-wiki/agents/scanner.md` — scanner workflow, rules, red flags (read in full)
- `agents/graph-wiki-agent/src/graph_wiki_agent/commands/query.py` — existing LIBRARIAN_SYSTEM, SYNTHESIZER_SYSTEM, CODE_READER_SYSTEM (read in full)
- `agents/graph-wiki-agent/src/graph_wiki_agent/commands/ingest.py` — existing INGESTOR_SYSTEM (read in full)
- `agents/graph-wiki-agent/src/graph_wiki_agent/commands/scan.py` — existing SCANNER_SYSTEM (read in full)
- `agents/graph-wiki-agent/src/graph_wiki_agent/commands/lint.py` — existing 3-group lint prompts (read in full)
- `cores/eval-harness/src/eval_harness/judge.py` — GEval + AmazonBedrockModel pattern (read in full)
- `cores/eval-harness/src/eval_harness/structural.py` — `_resolve_citation()` (read in full)
- `cores/eval-harness/src/eval_harness/baseline.py` — baseline schema pattern (read in full)
- `cores/eval-harness/tests/eval/test_sweep_eval.py` — pytest eval gate pattern (read in full)
- `.planning/phases/06-prompt-content-port-divergence-eval/06-CONTEXT.md` — locked decisions D-01..D-14 (read in full)
- `pyproject.toml` (workspace root) — workspace member glob pattern confirmed

### Secondary (MEDIUM confidence — structural inference)

- `cores/eval-harness/src/eval_harness/report.py` — regression_check pattern extrapolated to divergence gate
- `cores/eval-harness/tests/conftest.py` — EVAL_GATE pattern to replicate for divergence tests

---

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH — all packages already in workspace, verified via pyproject.toml reads
- Architecture (prompt module): HIGH — direct read of all source files; fragment split is deterministic from content analysis
- Architecture (divergence metric): HIGH — deepeval GEval pattern confirmed from judge.py; baseline pattern confirmed from baseline.py
- Pitfalls: HIGH — workspace member collision is a concrete uv behavior; token budget risk is known from existing SCANNER_SYSTEM token budget comment in scan.py
- Adaptation map: HIGH — every host-specific reference identified by reading source files; replacements confirmed by reading command layer

**Research date:** 2026-05-15
**Valid until:** 2026-06-15 (lattice-wiki source files are stable; deepeval 4.0 API is stable)
