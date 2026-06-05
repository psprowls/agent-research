# M4 — Drift Propagation to Backlinks Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** At scan time, for every entity whose code changed, find the curated pages (`concepts/`, `adrs/`, `architecture/`) that backlink it and **propose** updates where their claims may have gone stale — recording each as a `source: drift` note in the shared proposal ledger. Propose only; never auto-edit a curated page.

**Architecture:** M4 is a thin *producer* on top of the already-landed curated-page proposal ledger (`wiki_io.proposals.upsert_proposal`). It composes four existing mechanisms — the M2e per-entity anchor pattern, the backlink inverse map, the `SubagentPool` fan-out, and the ledger upsert — and adds exactly three new things: a `propagate_drift` orchestration command, a cheap-tier `drift_propagator` model role, and a pure `build_entity_backlink_map` helper extracted from the backlink indexer. The change signal is the **git-derived changed-file list** (not a narrative text diff), gated by M4's own per-entity anchor `drift_propagated_commit` so both execution surfaces compute candidates identically off disk and repeat runs are idempotent.

**Tech Stack:** Python 3.11, `uv` workspace, `frontmatter` (YAML), `langchain-aws`/`langchain-core` (Bedrock via `model_adapter.make_llm`), `subagent_runtime.SubagentPool` (asyncio fan-out), Typer (`gw` CLI), FastMCP (MCP server), pytest (`asyncio_mode = "auto"`).

**Spec:** `docs/superpowers/specs/2026-06-05-m4-drift-propagation-design.md`

---

## Orientation for the implementer

Read these before starting — they are the precedents every task mirrors:

- **Ledger (foundation, already landed):** `packages/wiki-io/src/wiki_io/proposals.py`. Key calls: `upsert_proposal(wiki, proposal) -> dict`, `list_proposals(wiki, status=, kind=) -> list[dict]`, and the constants `SUGGESTION_KINDS = {"concept","adr","architecture"}`, `HUMAN_DECIDED = {"approved","rejected","created"}`. An origin dict's key order is `(ref, source, rationale, detected_commit, hash)` — `detected_commit`/`hash` are **M4-reserved** (the ingest producer never sets them; M4 always does). `upsert_proposal` merges an origin into `origins[]` keyed by `ref`, leaves `HUMAN_DECIDED` notes untouched, and is byte-stable on a no-op.
- **Within-page drift (the template M4 mirrors cross-page):** `_drift_candidates` (`packages/graph-wiki-core/src/graph_wiki_core/commands/scan.py:613`), `_drift_flag_pass` (`scan.py:648`), and the prompt module `packages/graph-wiki-core/src/graph_wiki_core/prompts/drift_judge.py`. The anchor pattern: M2e stamps `drift_checked_commit` per entity page and gates on `drift_checked_commit != last_updated_commit`. M4 adds the parallel anchor `drift_propagated_commit`.
- **Backlink inverse map:** `regenerate_referenced_in_wiki` (`packages/wiki-io/src/wiki_io/backlink_index.py:100`) builds the `stem -> [(category, slug, page)]` map internally and discards it. Task 1 extracts it as a value.
- **Change signal:** `changed_files_since(repo, since_sha, sub_path) -> list[str] | None` (`packages/wiki-io/src/wiki_io/git_state.py:72`). Returns `[]` for no changes, `None` when git/SHA/path is unavailable (including an **empty** `since_sha`).
- **Fan-out:** `SubagentPool.run_all(items=, task=, role=, model_id=, max_concurrency=)` → `FanOutResult` with `.successes` (list of `(item, value)`) and `.errors`. The `task` returns `TaskResult(value=, response=)`. Concrete precedent: the narrator fan-out at `scan.py:988` and the drift fan-out at `scan.py:687`.
- **Frontmatter writes:** `update_frontmatter(page_path, updates=, *, delete=())` and `extract_narrative(body) -> str | None` (both `packages/wiki-io/src/wiki_io/entity_writer.py`; `extract_narrative` and `section_hash` are re-exported from `wiki_io.drift`). `LAST_UPDATED_COMMIT_KEY = "last_updated_commit"`.
- **Bedrock guard pattern (copy verbatim):** `scan.py:28-33` wraps `from model_adapter.loader import load_role_config, make_llm` / `from subagent_runtime.pool import ... SubagentPool, TaskResult` in `try/except ImportError` and sets them to `None`, so the plugin's `narrate=False` branch imports without the Bedrock stack.

**Per-package test commands** (run scoped, never from the repo root):

```bash
uv run --package wiki-io pytest
uv run --package model-adapter pytest
uv run --package graph-wiki-core pytest
uv run --package graph-wiki-cli pytest -m "not integration"
```

`ruff` line-length is 120. Match the surrounding multi-line style; **do not** run `ruff format` to fix your diff (the src tree is pre-existing format-dirty — see the repo's cleanup backlog).

---

## File Structure

| File | Responsibility | Task |
|---|---|---|
| `packages/wiki-io/src/wiki_io/backlink_index.py` (modify) | Extract pure `build_entity_backlink_map`; `regenerate_referenced_in_wiki` calls it (behavior-preserving) | 1 |
| `packages/model-adapter/src/model_adapter/models.toml` (modify) | New `[roles.drift_propagator]` cheap-tier block + sweep candidates | 2 |
| `packages/graph-wiki-core/src/graph_wiki_core/prompts/drift_propagator.py` (create) | Kind-aware cross-page judge prompt + fail-safe verdict parser | 3 |
| `packages/graph-wiki-core/src/graph_wiki_core/commands/propagate_drift.py` (create) | `PropagationCandidate`, `propagation_candidates`, `PropagateDriftResult`, `run_propagate_drift` | 4, 5, 6 |
| `packages/graph-wiki-cli/src/graph_wiki_cli/wiki_cli/main.py` (modify) | `gw wiki propagate-drift` standalone surface | 7 |
| `packages/graph-wiki-mcp/src/graph_wiki_mcp/server.py` (modify) | `wiki_propagate_drift` MCP twin | 8 |
| `packages/graph-wiki-core/src/graph_wiki_core/commands/scan.py` (modify) | `run_scan(propagate_drift=False)` param + post-narration call | 9 |
| `packages/graph-wiki-cli/src/graph_wiki_cli/cli.py` (modify) | `gw scan --propagate-drift` flag | 9 |
| `packages/graph-wiki-mcp/src/graph_wiki_mcp/server.py` (modify) | `wiki_scan` `propagate_drift` input | 9 |
| `.claude/rules/backward-compatibility.md` (modify) | Note `drift_propagated_commit` as a scanner-stamped, preserved, non-`SCANNER_OWNED_KEYS` provenance key | 10 |

Test files:

| Test file | Covers |
|---|---|
| `packages/wiki-io/tests/test_backlink_index.py` (modify) | Task 1 (map shape + behavior preservation) |
| `packages/graph-wiki-core/tests/unit/test_drift_propagator_prompt.py` (create) | Task 3 (prompt + parser) |
| `packages/graph-wiki-core/tests/commands/test_propagate_drift.py` (create) | Tasks 4–6, 9 (candidates, orchestration, surfaces) |
| `packages/graph-wiki-cli/tests/...test_wiki_propagate_drift_cli.py` (create) | Task 7 (CLI) |

---

## Task 1: Extract `build_entity_backlink_map`

The backlink inverse map is built privately inside `regenerate_referenced_in_wiki` and thrown away. M4 needs it as a value, filtered to curated kinds. Extract a pure helper returning `stem -> [(category, slug, page_path)]`; refactor the regen to call it (no behavior change, guarded by the existing byte-output test).

**Files:**
- Modify: `packages/wiki-io/src/wiki_io/backlink_index.py:100-142`
- Test: `packages/wiki-io/tests/test_backlink_index.py`

- [ ] **Step 1: Read the existing test to learn its fixtures**

Run: `sed -n '1,60p' packages/wiki-io/tests/test_backlink_index.py`
Note how it constructs `wiki/entities/*.md` and a referencing page under `concepts/` or `sources/`, and which assertion guards the rendered `## Referenced in wiki` output. You will reuse that fixture shape in Step 2.

- [ ] **Step 2: Write the failing test for the new helper**

Add to `packages/wiki-io/tests/test_backlink_index.py`:

```python
def test_build_entity_backlink_map_returns_category_slug_path(tmp_path):
    """[M4 §3.2] The extracted helper exposes the inverse map as a value:
    stem -> [(category, slug, page_path)] for [[entities/<stem>]] links across
    the preserved dirs."""
    from wiki_io.backlink_index import build_entity_backlink_map

    wiki = tmp_path / "wiki"
    (wiki / "entities").mkdir(parents=True)
    (wiki / "concepts").mkdir()
    (wiki / "sources").mkdir()
    (wiki / "entities" / "pkg_a.md").write_text("---\nuri: x\n---\n", encoding="utf-8")
    (wiki / "concepts" / "async-fanout.md").write_text(
        "---\ntitle: Async fan-out\n---\nSee [[entities/pkg_a]] for detail.\n",
        encoding="utf-8",
    )
    (wiki / "sources" / "spec-1.md").write_text(
        "---\ntitle: Spec 1\n---\nAlso [[entities/pkg_a]].\n", encoding="utf-8"
    )

    mapping = build_entity_backlink_map(wiki)

    assert set(mapping.keys()) == {"pkg_a"}
    entries = sorted(mapping["pkg_a"], key=lambda e: (e[0], e[1]))
    assert entries[0][0] == "concepts" and entries[0][1] == "async-fanout"
    assert entries[1][0] == "sources" and entries[1][1] == "spec-1"
    # Third element is the page Path, not a frontmatter Post.
    assert entries[0][2] == wiki / "concepts" / "async-fanout.md"
    from pathlib import Path
    assert all(isinstance(e[2], Path) for e in entries)
```

- [ ] **Step 3: Run the test to verify it fails**

Run: `uv run --package wiki-io pytest tests/test_backlink_index.py::test_build_entity_backlink_map_returns_category_slug_path -v`
Expected: FAIL with `ImportError: cannot import name 'build_entity_backlink_map'`.

- [ ] **Step 4: Extract the helper and refactor the regen**

In `packages/wiki-io/src/wiki_io/backlink_index.py`, replace the body of `regenerate_referenced_in_wiki` (lines ~100-142) with a call to a new pure helper. The helper carries `page_path` (not the loaded `post`) per the spec; the regen reloads frontmatter for bullet rendering, which is byte-identical (a malformed page is already skipped by the helper, so the reload never hits an unparseable file).

```python
def build_entity_backlink_map(wiki: Path) -> dict[str, list[tuple[str, str, Path]]]:
    """entity_stem -> [(category, slug, page_path)] for every [[entities/<stem>]]
    wikilink across the preserved wiki dirs.

    The inverse map ``regenerate_referenced_in_wiki`` builds internally, exposed
    as a value. A malformed referencing page is skipped (never fatal). Each
    referencing page contributes a given entity at most once (de-duped per page).
    """
    refs: dict[str, list[tuple[str, str, Path]]] = {}
    for category, page_path in _iter_preserved_pages(wiki):
        try:
            post = frontmatter.load(page_path)
        except Exception:  # noqa: BLE001 — a malformed page must not abort the map
            continue
        slug = page_path.stem
        seen_here: set[str] = set()
        for m in _ENTITY_LINK_RE.finditer(post.content):
            stem = m.group(1).strip().removesuffix(".md")
            if stem in seen_here:
                continue
            seen_here.add(stem)
            refs.setdefault(stem, []).append((category, slug, page_path))
    return refs


def regenerate_referenced_in_wiki(wiki: Path) -> list[str]:
    """Rebuild `## Referenced in wiki` on every entity page from the
    `[[entities/<stem>]]` wikilinks found across preserved pages.

    Backlinks key off body wikilinks (not the singular `entity_uri:` field), so
    a source touching several entities backlinks from all of them. Deterministic
    sort (by category, then slug). Idempotent. Returns the list of entity stems
    whose pages were (re)written.
    """
    entities_dir = wiki / "entities"
    if not entities_dir.is_dir():
        return []

    refs = build_entity_backlink_map(wiki)

    updated: list[str] = []
    for page_path in sorted(entities_dir.glob("*.md")):
        stem = page_path.stem
        entries = refs.get(stem, [])
        if entries:
            entries_sorted = sorted(entries, key=lambda e: (e[0], e[1]))
            body = "\n".join(
                _format_bullet(cat, slug, frontmatter.load(pp))
                for cat, slug, pp in entries_sorted
            )
        else:
            body = _EMPTY_BODY
        inject_referenced_in_wiki(page_path, body)
        updated.append(stem)
    return updated
```

- [ ] **Step 5: Run the new test and the full backlink suite**

Run: `uv run --package wiki-io pytest tests/test_backlink_index.py -v`
Expected: PASS — the new test plus every pre-existing `regenerate_referenced_in_wiki` test (which guard the byte-identical `## Referenced in wiki` output; the refactor must not change them).

- [ ] **Step 6: Commit**

```bash
git add packages/wiki-io/src/wiki_io/backlink_index.py packages/wiki-io/tests/test_backlink_index.py
git commit -m "feat(backlink): extract build_entity_backlink_map helper (M4 §3.2)

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

---

## Task 2: Add the `drift_propagator` model role

A cheap-tier classification role, mirroring `drift_judge`. It is loaded via `load_role_config("drift_propagator")` and `make_llm("drift_propagator")`.

**Files:**
- Modify: `packages/model-adapter/src/model_adapter/models.toml` (the **packaged** copy under `src/` is the one the loader reads via `resources.files("model_adapter")`; the top-level `packages/model-adapter/models.toml` is a stale stub — leave it).
- Test: `packages/model-adapter/tests/` (locate the existing `load_role_config` test file in Step 1)

- [ ] **Step 1: Find the existing role-loading test**

Run: `grep -rln "load_role_config" packages/model-adapter/tests/`
Open the file it names and find an existing assertion like `load_role_config("drift_judge")["model_id"]`. You will add a parallel assertion for `drift_propagator`.

- [ ] **Step 2: Write the failing test**

Add to that test file (matching its import style):

```python
def test_drift_propagator_role_is_configured():
    """[M4 §4] The cross-page drift judge has a cheap-tier role with candidates."""
    cfg = load_role_config("drift_propagator")
    assert cfg["model_id"]
    assert cfg["max_concurrency"] >= 1
    assert cfg.get("sweep_candidates")
```

- [ ] **Step 3: Run the test to verify it fails**

Run: `uv run --package model-adapter pytest -k drift_propagator -v`
Expected: FAIL with `KeyError: 'drift_propagator'` (role not present in `models.toml`).

- [ ] **Step 4: Add the role block**

Append to `packages/model-adapter/src/model_adapter/models.toml`, immediately after the `[roles.drift_judge]` block (so the two drift roles sit together):

```toml
# Living Wiki M4 — cross-page drift propagator. Judges a whole curated page
# (concept/adr/architecture) against the CURRENT narratives of the changed
# entities that backlink it, and proposes ledger notes for stale claims. Cheap
# classification tier (mirrors drift_judge); settle the default after a
# deepeval sweep (spec §7 open-q #2). max_tokens is a touch higher than
# drift_judge because the verdict carries one finding per triggering entity.
[roles.drift_propagator]
model_id        = "openai.gpt-oss-20b-1:0"
region          = "us-east-1"
max_tokens      = 512
max_concurrency = 10
sweep_candidates = [
  "openai.gpt-oss-20b-1:0",
  "zai.glm-4.7-flash",
  "qwen.qwen3-32b-v1:0",
  "us.amazon.nova-lite-v1:0",
  "mistral.ministral-3-14b-instruct",
]
```

- [ ] **Step 5: Run the test to verify it passes**

Run: `uv run --package model-adapter pytest -k drift_propagator -v`
Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add packages/model-adapter/src/model_adapter/models.toml packages/model-adapter/tests/
git commit -m "feat(models): add drift_propagator cheap-tier role (M4 §4)

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

---

## Task 3: The `drift_propagator` prompt + verdict parser

A kind-aware cross-page judge prompt and a fail-safe verdict parser, mirroring `prompts/drift_judge.py`. Concept/architecture pages are stale when their described behavior no longer matches the entity; ADR pages are **annotate-only** (stale only when Status/Consequences/Supersedes are overtaken — never a rewrite). The parser produces one finding per triggering entity and fails safe to not-stale.

**Files:**
- Create: `packages/graph-wiki-core/src/graph_wiki_core/prompts/drift_propagator.py`
- Test: `packages/graph-wiki-core/tests/unit/test_drift_propagator_prompt.py`

- [ ] **Step 1: Write the failing tests**

Create `packages/graph-wiki-core/tests/unit/test_drift_propagator_prompt.py`:

```python
"""Living Wiki M4: cross-page drift propagator prompt + verdict parser (spec §3.4)."""

from __future__ import annotations

from graph_wiki_core.prompts.drift_propagator import (
    build_drift_propagator_prompt,
    parse_drift_propagator_verdict,
)


def test_prompt_includes_kind_rubric_and_each_entity():
    entities = [
        ("pkg_a", "Now uses async fan-out.", ["packages/pkg_a/pool.py"]),
        ("pkg_b", "Still synchronous.", []),
    ]
    system, human = build_drift_propagator_prompt(
        "concept", "Async fan-out", "The system processes items synchronously.", entities
    )
    assert "CONCEPT" in system or "concept" in human
    assert "pkg_a" in human and "pkg_b" in human
    assert "packages/pkg_a/pool.py" in human
    # An entity with no changed files renders a placeholder, never an empty line.
    assert "(no specific files identified)" in human


def test_adr_rubric_is_annotate_only():
    system, human = build_drift_propagator_prompt("adr", "0007 Use async", "...", [])
    assert "ANNOTATE-ONLY" in system.upper() or "annotate" in human.lower()


def test_parse_valid_stale_verdict_keeps_findings_with_entity_stem():
    text = (
        '{"stale": true, "findings": ['
        '{"entity_stem": "pkg_a", "stale_claim": "sync", "rationale": "now async"}]}'
    )
    v = parse_drift_propagator_verdict(text)
    assert v["stale"] is True
    assert v["findings"][0]["entity_stem"] == "pkg_a"
    assert v["findings"][0]["rationale"] == "now async"


def test_parse_strips_code_fence():
    text = '```json\n{"stale": false, "findings": []}\n```'
    assert parse_drift_propagator_verdict(text) == {"stale": False, "findings": []}


def test_parse_fails_safe_on_garbage():
    assert parse_drift_propagator_verdict("not json at all") == {"stale": False, "findings": []}
    assert parse_drift_propagator_verdict("") == {"stale": False, "findings": []}


def test_parse_drops_findings_without_entity_stem_and_collapses_to_not_stale():
    text = '{"stale": true, "findings": [{"stale_claim": "x", "rationale": "y"}]}'
    # No usable entity attribution -> not actionable -> not stale.
    assert parse_drift_propagator_verdict(text) == {"stale": False, "findings": []}
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `uv run --package graph-wiki-core pytest tests/unit/test_drift_propagator_prompt.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'graph_wiki_core.prompts.drift_propagator'`.

- [ ] **Step 3: Write the prompt module**

Create `packages/graph-wiki-core/src/graph_wiki_core/prompts/drift_propagator.py`:

```python
"""Living Wiki M4: DRIFT_PROPAGATOR prompt + verdict parser (cross-page judge).

Where M2e's drift_judge compares a human SECTION against its own entity's
narrative (within-page), the propagator compares a whole CURATED page (concept /
ADR / architecture) against the CURRENT state of the changed entities that
backlink it (cross-page). It is kind-aware: concept/architecture pages are stale
when their described behaviour no longer matches the entity; ADR pages are
annotate-only (stale only when Status/Consequences/Supersedes are overtaken by
code reality — never a rewrite of decision history).

Output is a small JSON verdict with one finding per triggering entity, so each
ledger origin gets precise attribution. ``parse_drift_propagator_verdict`` fails
SAFE (not-stale) on any unparseable / malformed reply, mirroring
``parse_drift_verdict``.
"""

from __future__ import annotations

import json
import re

_KIND_RUBRIC = {
    "concept": (
        "This is a CONCEPT page. It is stale when the behaviour or design it "
        "describes no longer matches what the entity narratives now say."
    ),
    "architecture": (
        "This is an ARCHITECTURE page. It is stale when the structure, data "
        "flow, or component boundaries it describes are contradicted by the "
        "entity narratives now."
    ),
    "adr": (
        "This is an ADR (architecture decision record). Treat it as "
        "ANNOTATE-ONLY: flag it stale ONLY when the decision's Status, "
        "Consequences, or Supersedes have been overtaken by code reality (for "
        "example the decision was reversed or superseded by what the narrative "
        "now describes). Do NOT flag it merely because prose describing the "
        "original decision could be reworded, and never propose rewriting "
        "decision history."
    ),
}

DRIFT_PROPAGATOR_SYSTEM = """You judge whether a curated wiki page has gone STALE relative to the CURRENT state of the code entities it references.

You are given:
- the curated page's kind and full body, and
- for each changed entity the page references: that entity's current `## Narrative` (regenerated from the code as it exists now) and the list of files that changed since the page's claims were last checked.

Decide whether the page's claims now CONTRADICT or materially misdescribe what the narratives say. Do NOT flag a page for covering different ground, being shorter, or stylistic differences — only a genuine contradiction or material drift.

Output ONLY a single JSON object, no prose and no code fences:
{"stale": true|false,
 "findings": [{"entity_stem": "<one of the entity stems given to you>",
               "stale_claim": "<the page claim that is now wrong>",
               "rationale": "<one short line: why the narrative overtakes it>"}]}
Emit exactly one findings entry per entity that drives the staleness. When not stale, return {"stale": false, "findings": []}."""

_FENCE_RE = re.compile(r"^```(?:json)?\s*|\s*```$", re.IGNORECASE)
_OBJ_RE = re.compile(r"\{.*\}", re.DOTALL)


def build_drift_propagator_prompt(
    kind: str,
    page_title: str,
    page_body: str,
    entities: list[tuple[str, str, list[str]]],
) -> tuple[str, str]:
    """Return ``(system, human)`` for one curated page + its triggering entities.

    ``entities`` is a list of ``(entity_stem, narrative, changed_files)`` tuples.
    """
    rubric = _KIND_RUBRIC.get(kind, _KIND_RUBRIC["concept"])
    lines = [
        f"Page kind: {kind}",
        rubric,
        "",
        f"Curated page title: {page_title}",
        "",
        "Curated page body:",
        page_body.strip(),
        "",
        "Referenced entities that changed:",
    ]
    for stem, narrative, changed_files in entities:
        files = ", ".join(changed_files) if changed_files else "(no specific files identified)"
        lines += [
            "",
            f"### entity: {stem}",
            f"Changed files: {files}",
            "Current narrative:",
            narrative.strip(),
        ]
    lines += ["", "Is the page stale relative to these narratives? Reply with the JSON verdict."]
    return DRIFT_PROPAGATOR_SYSTEM, "\n".join(lines)


def parse_drift_propagator_verdict(text: str) -> dict:
    """Parse a ``{stale, findings[]}`` verdict. Fails SAFE to not-stale.

    Any unparseable / malformed reply yields ``{"stale": False, "findings": []}``.
    A finding survives only with a non-empty ``entity_stem`` (the origin needs
    attribution); when ``stale`` is true but no finding survives, the verdict
    collapses to not-stale.
    """
    raw = _FENCE_RE.sub("", (text or "").strip())
    match = _OBJ_RE.search(raw)
    if match is None:
        return {"stale": False, "findings": []}
    try:
        obj = json.loads(match.group(0))
    except (ValueError, TypeError):
        return {"stale": False, "findings": []}
    if not bool(obj.get("stale", False)):
        return {"stale": False, "findings": []}
    findings: list[dict] = []
    for f in obj.get("findings", []) or []:
        if not isinstance(f, dict):
            continue
        stem = str(f.get("entity_stem", "")).strip()
        if not stem:
            continue
        findings.append(
            {
                "entity_stem": stem,
                "stale_claim": str(f.get("stale_claim", "")),
                "rationale": str(f.get("rationale", "")),
            }
        )
    if not findings:
        return {"stale": False, "findings": []}
    return {"stale": True, "findings": findings}
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `uv run --package graph-wiki-core pytest tests/unit/test_drift_propagator_prompt.py -v`
Expected: PASS (all six tests).

- [ ] **Step 5: Commit**

```bash
git add packages/graph-wiki-core/src/graph_wiki_core/prompts/drift_propagator.py packages/graph-wiki-core/tests/unit/test_drift_propagator_prompt.py
git commit -m "feat(prompts): kind-aware drift_propagator prompt + parser (M4 §3.4)

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

---

## Task 4: `propagation_candidates` — the anchor-gated candidate set

M4's per-entity trigger. An entity page is a candidate when `drift_propagated_commit != last_updated_commit` (absent anchor ⇒ candidate), it has a `## Narrative`, and its kind carries a git change signal (package/app/test_suite/agent_plugin — these have a graph `node.path`). The candidate carries its changed-file list, computed off the entity's own `drift_propagated_commit`.

**Files:**
- Create: `packages/graph-wiki-core/src/graph_wiki_core/commands/propagate_drift.py`
- Test: `packages/graph-wiki-core/tests/commands/test_propagate_drift.py`

- [ ] **Step 1: Write the failing test (shared fixtures + the candidate gate)**

Create `packages/graph-wiki-core/tests/commands/test_propagate_drift.py`. This file's fixtures are reused by Tasks 5–6, so build them carefully:

```python
"""Living Wiki M4: drift propagation to backlinks (spec §5)."""

from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest
from graph_io.store import read_only_connect


# --- fixture helpers -------------------------------------------------------

def _seed_one_package(db_path: Path, *, uri: str, node_path: str) -> None:
    """One package node so _entity_paths_by_uri maps uri -> node_path."""
    from graph_io import schema

    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(db_path)
    try:
        schema.apply_schema(conn)
        conn.execute(
            "INSERT INTO nodes(kind, name, path, line, attrs_json, uri) VALUES "
            "('package', 'pkg-a', ?, NULL, '{\"language\": \"python\"}', ?)",
            (node_path, uri),
        )
        conn.commit()
    finally:
        conn.close()


def _write_entity_page(
    wiki: Path,
    *,
    stem: str,
    uri: str,
    last_updated_commit: str,
    drift_propagated_commit: str | None = None,
    narrative: str = "Now uses async fan-out.",
) -> Path:
    fm = [f"uri: {uri}", "kind: package", f"last_updated_commit: {last_updated_commit}"]
    if drift_propagated_commit is not None:
        fm.append(f"drift_propagated_commit: {drift_propagated_commit}")
    page = wiki / "entities" / f"{stem}.md"
    page.parent.mkdir(parents=True, exist_ok=True)
    page.write_text(
        "---\n" + "\n".join(fm) + "\n---\n"
        f"## Narrative\n\n{narrative}\n\n## Purpose\n\nTODO\n",
        encoding="utf-8",
    )
    return page


def _write_curated(wiki: Path, category: str, slug: str, body: str, title: str = "T") -> Path:
    page = wiki / category / f"{slug}.md"
    page.parent.mkdir(parents=True, exist_ok=True)
    page.write_text(f"---\ntitle: {title}\n---\n{body}\n", encoding="utf-8")
    return page


@pytest.fixture
def ws(tmp_path, monkeypatch):
    """workspace/{wiki, repo} + one-package graph DB + GRAPH_WIKI_WORKSPACE."""
    workspace = tmp_path / "workspace"
    wiki = workspace / "wiki"
    repo = workspace / "repo"
    (wiki / "entities").mkdir(parents=True)
    (wiki / ".graph-wiki").mkdir(parents=True)
    repo.mkdir()
    monkeypatch.setenv("GRAPH_WIKI_WORKSPACE", str(workspace))
    _seed_one_package(
        workspace / ".graph-wiki" / "code.db",
        uri="pkg:org/repo/pkg-a",
        node_path="packages/pkg-a",
    )
    return workspace


@pytest.fixture
def conn(ws):
    c = read_only_connect(ws / ".graph-wiki" / "code.db")
    yield c
    c.close()


# --- candidate-gate tests --------------------------------------------------

def test_candidate_when_anchors_differ(ws, conn, monkeypatch):
    """[§5 test 3] drift_propagated_commit != last_updated_commit -> candidate;
    changed_files come from changed_files_since(repo, drift_propagated_commit, path)."""
    import graph_wiki_core.commands.propagate_drift as pd

    wiki, repo = ws / "wiki", ws / "repo"
    _write_entity_page(
        wiki, stem="pkg_a", uri="pkg:org/repo/pkg-a",
        last_updated_commit="head2", drift_propagated_commit="head1",
    )
    monkeypatch.setattr(
        pd, "changed_files_since",
        lambda repo, sha, sub: ["packages/pkg-a/pool.py"] if sha == "head1" else None,
    )

    cands = pd.propagation_candidates(wiki, repo, conn)
    assert len(cands) == 1
    c = cands[0]
    assert c.uri == "pkg:org/repo/pkg-a"
    assert c.stem == "pkg_a"
    assert c.last_updated_commit == "head2"
    assert c.drift_propagated_commit == "head1"
    assert c.changed_files == ["packages/pkg-a/pool.py"]


def test_not_a_candidate_when_anchors_equal(ws, conn):
    """[§5 test 3] equal anchors -> already propagated at this narrative -> skip."""
    import graph_wiki_core.commands.propagate_drift as pd

    wiki, repo = ws / "wiki", ws / "repo"
    _write_entity_page(
        wiki, stem="pkg_a", uri="pkg:org/repo/pkg-a",
        last_updated_commit="head2", drift_propagated_commit="head2",
    )
    assert pd.propagation_candidates(wiki, repo, conn) == []


def test_absent_anchor_is_candidate(ws, conn, monkeypatch):
    """[§5 test 3] absent drift_propagated_commit -> candidate; empty since_sha
    yields no specific changed files (None -> [])."""
    import graph_wiki_core.commands.propagate_drift as pd

    wiki, repo = ws / "wiki", ws / "repo"
    _write_entity_page(
        wiki, stem="pkg_a", uri="pkg:org/repo/pkg-a", last_updated_commit="head2",
    )
    monkeypatch.setattr(pd, "changed_files_since", lambda repo, sha, sub: None)
    cands = pd.propagation_candidates(wiki, repo, conn)
    assert len(cands) == 1
    assert cands[0].drift_propagated_commit is None
    assert cands[0].changed_files == []
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `uv run --package graph-wiki-core pytest tests/commands/test_propagate_drift.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'graph_wiki_core.commands.propagate_drift'`.

- [ ] **Step 3: Create the module skeleton with the candidate helper**

Create `packages/graph-wiki-core/src/graph_wiki_core/commands/propagate_drift.py`:

```python
"""Living Wiki M4: scan-time drift producer — propose curated-page updates.

For every entity whose narrative was refreshed since M4 last propagated it, find
the curated pages (concepts/adrs/architecture) that backlink it and judge whether
their claims have gone stale relative to the entity's current state. Stale
findings are recorded as `source: drift` notes in the shared proposal ledger
(``wiki_io.proposals.upsert_proposal``) — propose only, never auto-edit.

M4 owns the per-entity anchor ``drift_propagated_commit`` (the analog of M2e's
``drift_checked_commit``): an entity is a candidate when
``drift_propagated_commit != last_updated_commit``, and the anchor is stamped to
``last_updated_commit`` after processing so repeat runs are idempotent on both
execution surfaces. Pure orchestration: the backlink map, ledger calls, and
judge prompt live in their own modules; this module composes them.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import frontmatter
from graph_io import queries as _queries
from langchain_core.messages import HumanMessage, SystemMessage
from wiki_io.backlink_index import build_entity_backlink_map
from wiki_io.drift import extract_narrative, section_hash
from wiki_io.entity_writer import LAST_UPDATED_COMMIT_KEY, update_frontmatter
from wiki_io.git_state import changed_files_since
from wiki_io.proposals import HUMAN_DECIDED, list_proposals, upsert_proposal
from workspace_io.paths import graph_dir

from graph_wiki_core.prompts.drift_propagator import (
    build_drift_propagator_prompt,
    parse_drift_propagator_verdict,
)

# Bedrock fan-out stack — imported only for the judged path (mirrors scan.py).
try:
    from model_adapter.loader import load_role_config, make_llm
    from subagent_runtime.pool import SubagentPool, TaskResult
except ImportError:  # pragma: no cover — exercised when the Bedrock stack is absent
    load_role_config = make_llm = None  # type: ignore[assignment]
    SubagentPool = TaskResult = None  # type: ignore[assignment]

logger = logging.getLogger(__name__)

# M4's per-entity provenance anchor (new key; preserved across re-scan; NOT in
# SCANNER_OWNED_KEYS — see .claude/rules/backward-compatibility.md, Task 10).
DRIFT_PROPAGATED_COMMIT_KEY = "drift_propagated_commit"

# Curated categories M4 proposes against, folder -> ledger kind. `sources`
# (M3-refreshed) and `work` (transient) are deliberately excluded (§3.2).
_CATEGORY_TO_KIND = {"concepts": "concept", "adrs": "adr", "architecture": "architecture"}

# Candidate kinds carry a node_path -> git change signal; mirrors
# scan._commit_dirty_changes / DRIFT_TARGET_KINDS.
_CANDIDATE_KINDS = ("package", "app", "test_suite", "agent_plugin")


@dataclass
class PropagationCandidate:
    uri: str
    page_path: Path
    stem: str
    narrative: str
    last_updated_commit: str
    drift_propagated_commit: str | None
    changed_files: list[str]


@dataclass
class PropagateDriftResult:
    pages_judged: int
    entities_considered: int
    notes_written: int          # target notes created or refreshed this run
    pages_stale: int
    pages_skipped_settled: int   # dropped by the ledger pre-filter
    dry_run: bool
    proposals: list[dict] = field(default_factory=list)  # report rows for --json


def _entity_paths_by_uri(conn: Any) -> dict[str, str]:
    """uri -> repo-relative node path for the candidate kinds (from the graph)."""
    list_fns = {
        "package": _queries.list_packages,
        "app": _queries.list_apps,
        "test_suite": _queries.list_test_suites,
        "agent_plugin": _queries.list_agent_plugins,
    }
    out: dict[str, str] = {}
    for kind in _CANDIDATE_KINDS:
        for node in list_fns[kind](conn):
            attrs = node.attrs if isinstance(node.attrs, dict) else {}
            uri = attrs.get("uri")
            if uri and node.path:
                out[uri] = node.path
    return out


def propagation_candidates(wiki: Path, repo: Path, conn: Any) -> list[PropagationCandidate]:
    """Entity pages where ``drift_propagated_commit != last_updated_commit``.

    Each candidate carries its current narrative and the git-derived files that
    moved since its ``drift_propagated_commit`` (an absent anchor yields no
    specific files — empty ``since_sha`` -> ``changed_files_since`` returns None).
    A kind without a graph ``node.path`` (repository/domain/dependency) is not a
    candidate — it has no change signal.
    """
    entities_dir = wiki / "entities"
    if not entities_dir.is_dir():
        return []
    uri_to_path = _entity_paths_by_uri(conn)
    out: list[PropagationCandidate] = []
    for page_path in sorted(entities_dir.glob("*.md")):
        try:
            post = frontmatter.load(page_path)
        except Exception:  # noqa: BLE001 — a malformed page must not abort the pass
            continue
        meta = post.metadata
        uri = meta.get("uri")
        anchor = meta.get(LAST_UPDATED_COMMIT_KEY)
        if not uri or not anchor:
            continue
        propagated = meta.get(DRIFT_PROPAGATED_COMMIT_KEY)
        if propagated == anchor:
            continue  # already propagated at this narrative revision
        node_path = uri_to_path.get(uri)
        if not node_path:
            continue  # kind without a git change signal
        narrative = extract_narrative(post.content)
        if not narrative:
            continue  # no ground truth to judge against
        changed = changed_files_since(repo, str(propagated) if propagated else "", node_path) or []
        out.append(
            PropagationCandidate(
                uri=str(uri),
                page_path=page_path,
                stem=page_path.stem,
                narrative=narrative,
                last_updated_commit=str(anchor),
                drift_propagated_commit=(str(propagated) if propagated else None),
                changed_files=list(changed),
            )
        )
    return out
```

- [ ] **Step 4: Run the candidate tests to verify they pass**

Run: `uv run --package graph-wiki-core pytest tests/commands/test_propagate_drift.py -v`
Expected: PASS (the three candidate-gate tests).

- [ ] **Step 5: Commit**

```bash
git add packages/graph-wiki-core/src/graph_wiki_core/commands/propagate_drift.py packages/graph-wiki-core/tests/commands/test_propagate_drift.py
git commit -m "feat(propagate-drift): anchor-gated propagation_candidates (M4 §3.1)

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

---

## Task 5: `run_propagate_drift` — judge, produce, stamp (happy path)

The orchestration core: compute candidates, build + curated-filter the backlink map, fan out the kind-aware judge per page, `upsert_proposal` once per finding, and stamp `drift_propagated_commit` per processed candidate. This task covers the happy path, per-page batching, non-stale, and idempotency; Task 6 adds the pre-filter, `--dry-run`, and `--only` guardrails.

**Files:**
- Modify: `packages/graph-wiki-core/src/graph_wiki_core/commands/propagate_drift.py`
- Test: `packages/graph-wiki-core/tests/commands/test_propagate_drift.py`

- [ ] **Step 1: Add the LLM-mock spy + happy-path tests**

Append to `packages/graph-wiki-core/tests/commands/test_propagate_drift.py`. The spy replaces `SubagentPool.run_all` (the M2e drift-test pattern) so no Bedrock is hit; `make_llm` is stubbed to a sentinel so the bedrock-absent guard does not early-return.

```python
import asyncio
from unittest.mock import MagicMock

import graph_wiki_core.commands.propagate_drift as pd
from wiki_io.proposals import list_proposals, read_proposal, proposal_path


def _patch_judge(monkeypatch, verdict_fn, *, recorder: dict | None = None):
    """Replace make_llm + SubagentPool.run_all. `verdict_fn(item)` returns the
    parsed verdict dict for one item; `item` is
    (kind, target_slug, title, page_body, entities, entry)."""
    monkeypatch.setattr(pd, "make_llm", lambda role, *, model_override=None: MagicMock())
    monkeypatch.setattr(pd, "load_role_config", lambda role: {"model_id": "m", "max_concurrency": 4})

    async def _run_all(self, *, items, task, role, model_id, max_concurrency):
        from subagent_runtime.pool import FanOutResult

        result = FanOutResult()
        if recorder is not None:
            recorder.setdefault("items", []).extend(items)
        result.successes = [(it, verdict_fn(it)) for it in items]
        return result

    monkeypatch.setattr(pd.SubagentPool, "run_all", _run_all)


def test_stale_page_with_two_entities_yields_one_note_two_origins(ws, conn, monkeypatch):
    """[§5 test 7] one page backlinked by two changed entities, both stale ->
    ONE ledger note with TWO source:drift origins (detected_commit + hash set)."""
    wiki, repo = ws / "wiki", ws / "repo"
    # Second package node so both entities map to a node_path.
    import sqlite3
    c2 = sqlite3.connect(ws / ".graph-wiki" / "code.db")
    c2.execute(
        "INSERT INTO nodes(kind, name, path, line, attrs_json, uri) VALUES "
        "('package','pkg-b','packages/pkg-b',NULL,'{}','pkg:org/repo/pkg-b')"
    )
    c2.commit()
    c2.close()
    conn2 = read_only_connect(ws / ".graph-wiki" / "code.db")

    _write_entity_page(wiki, stem="pkg_a", uri="pkg:org/repo/pkg-a",
                       last_updated_commit="h2", narrative="A is async now.")
    _write_entity_page(wiki, stem="pkg_b", uri="pkg:org/repo/pkg-b",
                       last_updated_commit="h9", narrative="B is async now.")
    _write_curated(wiki, "concepts", "fanout",
                   "Both pkg_a [[entities/pkg_a]] and pkg_b [[entities/pkg_b]] are synchronous.")
    monkeypatch.setattr(pd, "changed_files_since", lambda repo, sha, sub: [])

    def verdict(item):
        kind, slug, title, body, entities, entry = item
        return {"stale": True, "findings": [
            {"entity_stem": stem, "stale_claim": "sync", "rationale": f"{stem} now async"}
            for stem, _narr, _files in entities
        ]}

    _patch_judge(monkeypatch, verdict)
    res = asyncio.run(pd.run_propagate_drift(wiki=wiki, repo=repo, conn=conn2))
    conn2.close()

    assert res.pages_judged == 1
    assert res.entities_considered == 2
    assert res.notes_written == 1
    assert res.pages_stale == 1

    rec = read_proposal(proposal_path(wiki, "concept", "fanout"))
    assert rec["status"] == "proposed"
    assert rec["mode"] == "update_existing"
    assert len(rec["origins"]) == 2
    refs = {o["ref"] for o in rec["origins"]}
    assert refs == {"entities/pkg_a", "entities/pkg_b"}
    for o in rec["origins"]:
        assert o["source"] == "drift"
        assert o["detected_commit"] in {"h2", "h9"}
        assert o["hash"]  # sha256 of the entity narrative


def test_non_stale_page_writes_no_note(ws, conn, monkeypatch):
    """[§5 test 10] judge says not stale -> no ledger note."""
    wiki, repo = ws / "wiki", ws / "repo"
    _write_entity_page(wiki, stem="pkg_a", uri="pkg:org/repo/pkg-a", last_updated_commit="h2")
    _write_curated(wiki, "concepts", "fanout", "About [[entities/pkg_a]].")
    monkeypatch.setattr(pd, "changed_files_since", lambda repo, sha, sub: [])
    _patch_judge(monkeypatch, lambda item: {"stale": False, "findings": []})

    res = asyncio.run(pd.run_propagate_drift(wiki=wiki, repo=repo, conn=conn))
    assert res.notes_written == 0
    assert list_proposals(wiki) == []


def test_anchor_stamped_and_second_run_is_idempotent(ws, conn, monkeypatch):
    """[§5 test 4] every processed candidate's drift_propagated_commit is stamped
    to last_updated_commit; a second run with no code change judges nothing."""
    wiki, repo = ws / "wiki", ws / "repo"
    page = _write_entity_page(wiki, stem="pkg_a", uri="pkg:org/repo/pkg-a", last_updated_commit="h2")
    _write_curated(wiki, "concepts", "fanout", "About [[entities/pkg_a]].")
    monkeypatch.setattr(pd, "changed_files_since", lambda repo, sha, sub: [])
    _patch_judge(monkeypatch, lambda item: {"stale": False, "findings": []})

    asyncio.run(pd.run_propagate_drift(wiki=wiki, repo=repo, conn=conn))
    import frontmatter as _fm
    assert _fm.load(page).metadata.get("drift_propagated_commit") == "h2"

    rec = {"items": []}
    _patch_judge(monkeypatch, lambda item: {"stale": False, "findings": []}, recorder=rec)
    res2 = asyncio.run(pd.run_propagate_drift(wiki=wiki, repo=repo, conn=conn))
    assert res2.entities_considered == 0
    assert rec["items"] == []  # judge never invoked


def test_entity_with_no_curated_backlink_is_still_stamped(ws, conn, monkeypatch):
    """[§3.5] a candidate whose only backlinkers are non-curated (or none) is
    still stamped, so it is not reconsidered until its narrative changes."""
    wiki, repo = ws / "wiki", ws / "repo"
    page = _write_entity_page(wiki, stem="pkg_a", uri="pkg:org/repo/pkg-a", last_updated_commit="h2")
    _write_curated(wiki, "sources", "spec", "About [[entities/pkg_a]].")  # sources excluded
    monkeypatch.setattr(pd, "changed_files_since", lambda repo, sha, sub: [])
    _patch_judge(monkeypatch, lambda item: {"stale": False, "findings": []})

    res = asyncio.run(pd.run_propagate_drift(wiki=wiki, repo=repo, conn=conn))
    assert res.pages_judged == 0  # no curated target
    import frontmatter as _fm
    assert _fm.load(page).metadata.get("drift_propagated_commit") == "h2"
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `uv run --package graph-wiki-core pytest tests/commands/test_propagate_drift.py -k "stale or idempotent or stamped" -v`
Expected: FAIL with `AttributeError: module 'graph_wiki_core.commands.propagate_drift' has no attribute 'run_propagate_drift'`.

- [ ] **Step 3: Implement `run_propagate_drift` (no guardrails yet)**

Append to `packages/graph-wiki-core/src/graph_wiki_core/commands/propagate_drift.py`:

```python
def _page_title(page_path: Path, fallback: str) -> str:
    try:
        return str(frontmatter.load(page_path).metadata.get("title") or fallback)
    except Exception:  # noqa: BLE001
        return fallback


def _build_targets(
    candidates: list[PropagationCandidate], backlink_map: dict
) -> dict[Path, dict]:
    """page_path -> {kind, target_slug, page_path, candidates[]} for curated
    pages backlinked by a candidate (sources/work filtered out)."""
    targets: dict[Path, dict] = {}
    for c in candidates:
        for category, slug, page_path in backlink_map.get(c.stem, []):
            kind = _CATEGORY_TO_KIND.get(category)
            if kind is None:
                continue  # sources / work are not drift targets
            entry = targets.setdefault(
                page_path,
                {"kind": kind, "target_slug": slug, "page_path": page_path, "candidates": []},
            )
            entry["candidates"].append(c)
    return targets


async def run_propagate_drift(
    *,
    wiki: Path,
    repo: Path,
    conn: Any,
    dry_run: bool = False,
    only: str | None = None,
    model_override: str | None = None,
) -> PropagateDriftResult:
    """Propose curated-page updates for changed entities (spec §3.6).

    candidates → curated backlink targets → kind-aware judge → upsert one origin
    per finding → stamp drift_propagated_commit per processed candidate. Both
    surfaces call this; it computes its own candidates off the on-disk anchors.
    """
    candidates = propagation_candidates(wiki, repo, conn)

    # The Bedrock stack is required to judge; absent it (plugin branch) we make
    # no proposals and stamp nothing (mirrors scan._drift_flag_pass early-out).
    if make_llm is None or SubagentPool is None:
        return PropagateDriftResult(0, len(candidates), 0, 0, 0, dry_run, [])

    targets = _build_targets(candidates, build_entity_backlink_map(wiki))

    # The candidates actually processed this run (Task 6 narrows these via --only).
    processed = candidates

    judge_targets = list(targets.values())

    items: list[tuple] = []
    for entry in judge_targets:
        body = entry["page_path"].read_text(encoding="utf-8")
        title = _page_title(entry["page_path"], entry["target_slug"])
        entity_tuples = [(c.stem, c.narrative, c.changed_files) for c in entry["candidates"]]
        items.append(
            (entry["kind"], entry["target_slug"], title, body, entity_tuples, entry)
        )

    verdicts: list[tuple] = []
    if items:
        cfg = load_role_config("drift_propagator")
        llm = make_llm("drift_propagator", model_override=model_override)
        pool = SubagentPool(trace_dir=graph_dir(wiki.parent) / "traces")

        async def judge(item: tuple) -> "TaskResult":
            kind, _slug, title, body, entity_tuples, _entry = item
            system_msg, human_msg = build_drift_propagator_prompt(kind, title, body, entity_tuples)
            resp = await llm.ainvoke(
                [SystemMessage(content=system_msg), HumanMessage(content=human_msg)]
            )
            return TaskResult(value=parse_drift_propagator_verdict(resp.content), response=resp)

        fan = await pool.run_all(
            items=items,
            task=judge,
            role="drift_propagator",
            model_id=cfg["model_id"],
            max_concurrency=cfg["max_concurrency"],
        )
        verdicts = list(fan.successes)

    pages_stale = 0
    notes_written = 0
    report: list[dict] = []
    for item, verdict in verdicts:
        kind, slug, title, _body, _entity_tuples, entry = item
        if not (isinstance(verdict, dict) and verdict.get("stale")):
            continue
        findings = verdict.get("findings") or []
        by_stem = {c.stem: c for c in entry["candidates"]}
        origins_written: list[dict] = []
        for finding in findings:
            cand = by_stem.get(finding.get("entity_stem"))
            if cand is None:
                continue  # finding references an entity not in this page's batch
            origin = {
                "ref": f"entities/{cand.stem}",
                "source": "drift",
                "detected_commit": cand.last_updated_commit,
                "hash": section_hash(cand.narrative),
                "rationale": str(finding.get("rationale", "")),
            }
            if not dry_run:
                upsert_proposal(
                    wiki,
                    {
                        "kind": kind,
                        "mode": "update_existing",
                        "target_slug": slug,
                        "title": title,
                        "origin": origin,
                    },
                )
            origins_written.append(origin)
        if origins_written:
            pages_stale += 1
            if not dry_run:
                notes_written += 1  # nothing is written in a dry run
            report.append({"kind": kind, "target_slug": slug, "origins": origins_written})

    if not dry_run:
        for c in processed:
            try:
                update_frontmatter(c.page_path, {DRIFT_PROPAGATED_COMMIT_KEY: c.last_updated_commit})
            except Exception as exc:  # noqa: BLE001 — non-fatal stamp
                logger.warning("drift_propagated stamp failed for %s: %s", c.page_path, exc)

    return PropagateDriftResult(
        pages_judged=len(items),
        entities_considered=len(processed),
        notes_written=notes_written,
        pages_stale=pages_stale,
        pages_skipped_settled=0,  # Task 6 fills this in
        dry_run=dry_run,
        proposals=report,
    )
```

- [ ] **Step 4: Run the happy-path tests to verify they pass**

Run: `uv run --package graph-wiki-core pytest tests/commands/test_propagate_drift.py -k "stale or idempotent or stamped" -v`
Expected: PASS (four tests).

- [ ] **Step 5: Run the whole module suite (no regressions in Task 4 tests)**

Run: `uv run --package graph-wiki-core pytest tests/commands/test_propagate_drift.py -v`
Expected: PASS (all tests so far).

- [ ] **Step 6: Commit**

```bash
git add packages/graph-wiki-core/src/graph_wiki_core/commands/propagate_drift.py packages/graph-wiki-core/tests/commands/test_propagate_drift.py
git commit -m "feat(propagate-drift): run_propagate_drift judge+produce+stamp (M4 §3.4-3.5)

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

---

## Task 6: Guardrails — ledger pre-filter, `--dry-run`, `--only`, re-fire

Three cost/safety rails on the orchestration: skip targets the human already disposed of (`HUMAN_DECIDED`); `--dry-run` judges + reports but writes zero notes and stamps nothing; `--only` restricts to one entity (candidate set) or one page (target set). Plus the re-fire-in-place case (the ledger merges by `ref`).

**Files:**
- Modify: `packages/graph-wiki-core/src/graph_wiki_core/commands/propagate_drift.py`
- Test: `packages/graph-wiki-core/tests/commands/test_propagate_drift.py`

- [ ] **Step 1: Write the failing guardrail tests**

Append to `packages/graph-wiki-core/tests/commands/test_propagate_drift.py`:

```python
def test_settled_target_is_skipped(ws, conn, monkeypatch):
    """[§5 test 6] a rejected/created note on a target -> not judged; a proposed
    note (or none) -> judged."""
    wiki, repo = ws / "wiki", ws / "repo"
    _write_entity_page(wiki, stem="pkg_a", uri="pkg:org/repo/pkg-a", last_updated_commit="h2")
    _write_curated(wiki, "concepts", "fanout", "About [[entities/pkg_a]].")
    monkeypatch.setattr(pd, "changed_files_since", lambda repo, sha, sub: [])
    # Pre-seed a rejected note for this exact target.
    from wiki_io.proposals import upsert_proposal, set_proposal_status
    upsert_proposal(wiki, {"kind": "concept", "mode": "update_existing",
                           "target_slug": "fanout", "title": "T",
                           "origin": {"ref": "entities/pkg_a", "source": "ingest"}})
    set_proposal_status(wiki, "concept", "fanout", "rejected")

    rec = {"items": []}
    _patch_judge(monkeypatch, lambda item: {"stale": True, "findings": [
        {"entity_stem": "pkg_a", "stale_claim": "x", "rationale": "y"}]}, recorder=rec)
    res = asyncio.run(pd.run_propagate_drift(wiki=wiki, repo=repo, conn=conn))

    assert res.pages_judged == 0
    assert res.pages_skipped_settled == 1
    assert rec["items"] == []  # judge never saw the settled target
    # The rejected note is untouched.
    assert read_proposal(proposal_path(wiki, "concept", "fanout"))["status"] == "rejected"


def test_dry_run_judges_but_writes_nothing_and_does_not_stamp(ws, conn, monkeypatch):
    """[§5 tests 5, 12] --dry-run populates the report, writes zero notes, and
    leaves drift_propagated_commit unstamped (re-runnable)."""
    wiki, repo = ws / "wiki", ws / "repo"
    page = _write_entity_page(wiki, stem="pkg_a", uri="pkg:org/repo/pkg-a", last_updated_commit="h2")
    _write_curated(wiki, "concepts", "fanout", "About [[entities/pkg_a]].")
    monkeypatch.setattr(pd, "changed_files_since", lambda repo, sha, sub: [])
    _patch_judge(monkeypatch, lambda item: {"stale": True, "findings": [
        {"entity_stem": "pkg_a", "stale_claim": "x", "rationale": "now async"}]})

    res = asyncio.run(pd.run_propagate_drift(wiki=wiki, repo=repo, conn=conn, dry_run=True))
    assert res.dry_run is True
    assert res.pages_judged == 1
    assert res.pages_stale == 1
    assert res.notes_written == 0
    assert len(res.proposals) == 1  # report shows what WOULD be proposed
    assert list_proposals(wiki) == []  # nothing written
    import frontmatter as _fm
    assert "drift_propagated_commit" not in _fm.load(page).metadata


def test_only_entity_restricts_candidate_set(ws, conn, monkeypatch):
    """[§5 test 13] --only <entity> restricts the candidate set to that entity."""
    wiki, repo = ws / "wiki", ws / "repo"
    import sqlite3
    c2 = sqlite3.connect(ws / ".graph-wiki" / "code.db")
    c2.execute("INSERT INTO nodes(kind,name,path,line,attrs_json,uri) VALUES "
               "('package','pkg-b','packages/pkg-b',NULL,'{}','pkg:org/repo/pkg-b')")
    c2.commit(); c2.close()
    conn2 = read_only_connect(ws / ".graph-wiki" / "code.db")

    _write_entity_page(wiki, stem="pkg_a", uri="pkg:org/repo/pkg-a", last_updated_commit="h2")
    _write_entity_page(wiki, stem="pkg_b", uri="pkg:org/repo/pkg-b", last_updated_commit="h2")
    _write_curated(wiki, "concepts", "ca", "About [[entities/pkg_a]].")
    _write_curated(wiki, "concepts", "cb", "About [[entities/pkg_b]].")
    monkeypatch.setattr(pd, "changed_files_since", lambda repo, sha, sub: [])
    _patch_judge(monkeypatch, lambda item: {"stale": False, "findings": []})

    res = asyncio.run(pd.run_propagate_drift(wiki=wiki, repo=repo, conn=conn2, only="pkg_a"))
    conn2.close()
    assert res.entities_considered == 1  # only pkg_a
    assert res.pages_judged == 1         # only its target


def test_only_page_restricts_target_set(ws, conn, monkeypatch):
    """[§5 test 13] --only <page-slug> restricts the target set to that page."""
    wiki, repo = ws / "wiki", ws / "repo"
    import sqlite3
    c2 = sqlite3.connect(ws / ".graph-wiki" / "code.db")
    c2.execute("INSERT INTO nodes(kind,name,path,line,attrs_json,uri) VALUES "
               "('package','pkg-b','packages/pkg-b',NULL,'{}','pkg:org/repo/pkg-b')")
    c2.commit(); c2.close()
    conn2 = read_only_connect(ws / ".graph-wiki" / "code.db")

    _write_entity_page(wiki, stem="pkg_a", uri="pkg:org/repo/pkg-a", last_updated_commit="h2")
    _write_entity_page(wiki, stem="pkg_b", uri="pkg:org/repo/pkg-b", last_updated_commit="h2")
    _write_curated(wiki, "concepts", "ca", "About [[entities/pkg_a]].")
    _write_curated(wiki, "concepts", "cb", "About [[entities/pkg_b]].")
    monkeypatch.setattr(pd, "changed_files_since", lambda repo, sha, sub: [])
    _patch_judge(monkeypatch, lambda item: {"stale": False, "findings": []})

    res = asyncio.run(pd.run_propagate_drift(wiki=wiki, repo=repo, conn=conn2, only="ca"))
    conn2.close()
    assert res.pages_judged == 1  # only the "ca" target page


def test_refire_same_entity_updates_origin_in_place(ws, conn, monkeypatch):
    """[§5 test 8] re-firing the same entity on the same target updates that
    origin in place (no duplicate); detected_commit advances; status stays
    proposed."""
    wiki, repo = ws / "wiki", ws / "repo"
    page = _write_entity_page(wiki, stem="pkg_a", uri="pkg:org/repo/pkg-a", last_updated_commit="h2")
    _write_curated(wiki, "concepts", "fanout", "About [[entities/pkg_a]].")
    monkeypatch.setattr(pd, "changed_files_since", lambda repo, sha, sub: [])
    _patch_judge(monkeypatch, lambda item: {"stale": True, "findings": [
        {"entity_stem": "pkg_a", "stale_claim": "x", "rationale": "r1"}]})
    asyncio.run(pd.run_propagate_drift(wiki=wiki, repo=repo, conn=conn))

    # Entity re-narrated at a new commit -> candidate again.
    import frontmatter as _fm
    pd_meta = _fm.load(page).metadata
    page.write_text(page.read_text().replace("last_updated_commit: h2", "last_updated_commit: h3"),
                    encoding="utf-8")
    _patch_judge(monkeypatch, lambda item: {"stale": True, "findings": [
        {"entity_stem": "pkg_a", "stale_claim": "x", "rationale": "r2"}]})
    asyncio.run(pd.run_propagate_drift(wiki=wiki, repo=repo, conn=conn))

    rec = read_proposal(proposal_path(wiki, "concept", "fanout"))
    assert rec["status"] == "proposed"
    assert len(rec["origins"]) == 1  # merged in place by ref
    assert rec["origins"][0]["detected_commit"] == "h3"
    assert rec["origins"][0]["rationale"] == "r2"
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `uv run --package graph-wiki-core pytest tests/commands/test_propagate_drift.py -k "settled or dry_run or only_ or refire" -v`
Expected: FAIL — `pages_skipped_settled` stays 0, settled targets still judged, `dry_run` still writes/stamps, `only` ignored.

- [ ] **Step 3: Wire the guardrails into `run_propagate_drift`**

Edit `run_propagate_drift`. The lines `candidates = propagation_candidates(...)` and the `if make_llm is None ...` guard stay exactly as Task 5 left them. Replace the three lines that follow them — `targets = _build_targets(...)`, `processed = candidates`, and `judge_targets = list(targets.values())` — with the `--only` resolution, the ledger pre-filter, and the `processed`-set computation below:

```python
    # --only: an entity (uri/stem) narrows the candidate set; otherwise a target
    # (slug/page-stem) narrows the target set (§3.8, test 13).
    only_target: str | None = None
    if only is not None:
        entity_match = [c for c in candidates if c.uri == only or c.stem == only]
        if entity_match:
            candidates = entity_match
        else:
            only_target = only

    targets = _build_targets(candidates, build_entity_backlink_map(wiki))
    if only_target is not None:
        targets = {
            p: e
            for p, e in targets.items()
            if e["target_slug"] == only_target or p.stem == only_target
        }

    # Ledger pre-filter: drop targets the human already disposed of (§3.3).
    settled = {
        (rec["kind"], rec["target_slug"])
        for rec in list_proposals(wiki)
        if rec["status"] in HUMAN_DECIDED
    }
    pages_skipped_settled = 0
    judge_targets: list[dict] = []
    for entry in targets.values():
        if (entry["kind"], entry["target_slug"]) in settled:
            pages_skipped_settled += 1
            continue
        judge_targets.append(entry)

    # Processed candidates get the anchor stamp: every candidate in scope whose
    # backlinkers were considered — INCLUDING those whose targets were all
    # pre-filtered out (§3.5). In target-only mode, scope is just the candidates
    # backlinking the chosen page.
    if only_target is not None:
        seen_ids: set[int] = set()
        processed: list[PropagationCandidate] = []
        for entry in targets.values():
            for c in entry["candidates"]:
                if id(c) not in seen_ids:
                    seen_ids.add(id(c))
                    processed.append(c)
    else:
        processed = candidates
```

Then change the result's `pages_skipped_settled=0` line to use the computed value:

```python
        pages_skipped_settled=pages_skipped_settled,
```

(The `dry_run` skip of both `upsert_proposal` and the stamping loop is already in place from Task 5 — verify the `if not dry_run:` guards remain around both.)

- [ ] **Step 4: Run the guardrail tests to verify they pass**

Run: `uv run --package graph-wiki-core pytest tests/commands/test_propagate_drift.py -k "settled or dry_run or only_ or refire" -v`
Expected: PASS (five tests).

- [ ] **Step 5: Run the full module suite**

Run: `uv run --package graph-wiki-core pytest tests/commands/test_propagate_drift.py -v`
Expected: PASS (every test from Tasks 4–6).

- [ ] **Step 6: Commit**

```bash
git add packages/graph-wiki-core/src/graph_wiki_core/commands/propagate_drift.py packages/graph-wiki-core/tests/commands/test_propagate_drift.py
git commit -m "feat(propagate-drift): ledger pre-filter, --dry-run, --only guardrails (M4 §3.3/3.8)

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

---

## Task 7: `gw wiki propagate-drift` standalone surface

A thin Typer command that resolves the workspace, opens the graph read-only, calls `run_propagate_drift`, and renders the summary. Mirrors the `proposals` / `ack-drift` command bodies in `wiki_cli/main.py`.

**Files:**
- Modify: `packages/graph-wiki-cli/src/graph_wiki_cli/wiki_cli/main.py`
- Test: `packages/graph-wiki-cli/tests/test_wiki_propagate_drift_cli.py` (create; confirm the tests dir path with `ls packages/graph-wiki-cli/tests/` first and match the package's existing CLI-test style)

- [ ] **Step 1: Write the failing CLI test**

Create `packages/graph-wiki-cli/tests/test_wiki_propagate_drift_cli.py`. `run_propagate_drift` is awaited (`asyncio.run`), so patch it with `AsyncMock` (a plain `return_value` is not awaitable); `read_only_connect` is stubbed with an object that has a no-op `.close()` (the command closes the conn in a `finally`):

```python
"""gw wiki propagate-drift surface (M4 §3.7)."""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import AsyncMock, patch

from graph_wiki_cli.wiki_cli.main import wiki_app
from graph_wiki_core.commands.propagate_drift import PropagateDriftResult
from typer.testing import CliRunner

runner = CliRunner()

_ConnStub = type("ConnStub", (), {"close": lambda self: None})


def _fake_result(**over):
    base = dict(
        pages_judged=2, entities_considered=3, notes_written=1, pages_stale=1,
        pages_skipped_settled=1, dry_run=False,
        proposals=[{"kind": "concept", "target_slug": "fanout",
                    "origins": [{"ref": "entities/pkg_a", "source": "drift"}]}],
    )
    base.update(over)
    return PropagateDriftResult(**base)


def test_propagate_drift_json_output():
    fake = AsyncMock(return_value=_fake_result())
    with patch("graph_wiki_cli.wiki_cli.main.run_propagate_drift", new=fake), \
         patch("graph_wiki_cli.wiki_cli.main.resolve_wiki_and_repo",
               return_value=(Path("/w/wiki"), Path("/w/repo"))), \
         patch("graph_wiki_cli.wiki_cli.main.read_only_connect", return_value=_ConnStub()):
        result = runner.invoke(wiki_app, ["propagate-drift", "--json"])
    assert result.exit_code == 0, result.stdout
    payload = json.loads(result.stdout)
    assert payload["pages_judged"] == 2
    assert payload["notes_written"] == 1
    assert payload["pages_skipped_settled"] == 1
    assert fake.await_count == 1


def test_propagate_drift_dry_run_flag_threads_through():
    fake = AsyncMock(return_value=_fake_result(dry_run=True, notes_written=0))
    with patch("graph_wiki_cli.wiki_cli.main.run_propagate_drift", new=fake), \
         patch("graph_wiki_cli.wiki_cli.main.resolve_wiki_and_repo",
               return_value=(Path("/w/wiki"), Path("/w/repo"))), \
         patch("graph_wiki_cli.wiki_cli.main.read_only_connect", return_value=_ConnStub()):
        result = runner.invoke(wiki_app, ["propagate-drift", "--dry-run", "--only", "pkg_a"])
    assert result.exit_code == 0, result.stdout
    assert fake.await_args.kwargs["dry_run"] is True
    assert fake.await_args.kwargs["only"] == "pkg_a"
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `uv run --package graph-wiki-cli pytest tests/test_wiki_propagate_drift_cli.py -v`
Expected: FAIL — `propagate-drift` is not a registered command (`Error: No such command`).

- [ ] **Step 3: Add the command + imports**

In `packages/graph-wiki-cli/src/graph_wiki_cli/wiki_cli/main.py`, add imports near the existing core-command imports (after line 22):

```python
from graph_wiki_core.commands.propagate_drift import run_propagate_drift
from graph_io.store import read_only_connect
from wiki_io._workspace import resolve_wiki_and_repo
from workspace_io.paths import graph_dir
```

Add the command (place it next to the `ack-drift` / `proposals` commands, after the `proposals` command body ~line 226):

```python
@wiki_app.command(name="propagate-drift")
def propagate_drift(
    workspace: str = typer.Option("", "--workspace", help="Workspace path (default: GRAPH_WIKI_WORKSPACE env var)"),
    dry_run: bool = typer.Option(False, "--dry-run", help="Judge + report without writing notes or stamping anchors"),
    only: Optional[str] = typer.Option(None, "--only", help="Restrict to one entity (uri/stem) or curated page (slug)"),
    json_output: bool = typer.Option(False, "--json", help="Emit PropagateDriftResult as JSON"),
) -> None:
    """Propose curated-page updates for entities whose code changed (M4 drift producer)."""
    workspace_path = Path(workspace) if workspace else None
    try:
        wiki, repo = resolve_wiki_and_repo(workspace_path)
    except (RuntimeError, FileNotFoundError) as e:
        typer.echo(f"Error: {e}", err=True)
        raise typer.Exit(code=1)
    conn = read_only_connect(graph_dir(wiki.parent) / "code.db")
    try:
        result = asyncio.run(
            run_propagate_drift(wiki=wiki, repo=repo, conn=conn, dry_run=dry_run, only=only)
        )
    finally:
        conn.close()

    if json_output:
        typer.echo(json.dumps(dataclasses.asdict(result), indent=2))
    else:
        prefix = "[dry-run] " if result.dry_run else ""
        typer.echo(
            f"{prefix}propagate-drift: judged {result.pages_judged} page(s), "
            f"{result.entities_considered} entit(ies) considered, "
            f"{result.pages_stale} stale, {result.notes_written} note(s) "
            f"{'would be ' if result.dry_run else ''}written, "
            f"{result.pages_skipped_settled} skipped (settled)."
        )
        for row in result.proposals:
            refs = ", ".join(o["ref"] for o in row["origins"])
            typer.echo(f"  {row['kind']}-{row['target_slug']}  <- {refs}")
```

Note: `Optional` is already imported in `wiki_cli/main.py` (line 15: `from typing import Optional`); `asyncio`, `dataclasses`, `json`, `typer`, and `Path` are already imported at the top of the module.

- [ ] **Step 4: Run the test to verify it passes**

Run: `uv run --package graph-wiki-cli pytest tests/test_wiki_propagate_drift_cli.py -v`
Expected: PASS (both tests).

- [ ] **Step 5: Smoke-test the help text**

Run: `uv run --package graph-wiki-cli gw wiki propagate-drift --help`
Expected: usage text listing `--dry-run`, `--only`, `--workspace`, `--json`.

- [ ] **Step 6: Commit**

```bash
git add packages/graph-wiki-cli/src/graph_wiki_cli/wiki_cli/main.py packages/graph-wiki-cli/tests/test_wiki_propagate_drift_cli.py
git commit -m "feat(cli): gw wiki propagate-drift standalone surface (M4 §3.7)

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

---

## Task 8: `wiki_propagate_drift` MCP twin

The MCP surface mirror, modeled on the existing `wiki_scan` tool (`server.py:264`). Resolves the workspace, opens the graph, calls `run_propagate_drift`, returns the summary fields.

**Files:**
- Modify: `packages/graph-wiki-mcp/src/graph_wiki_mcp/server.py`
- Test: locate the MCP test dir with `ls packages/graph-wiki-mcp/tests/` and add a test mirroring the existing `wiki_scan` tool test (Step 1)

- [ ] **Step 1: Read an existing MCP tool test for the pattern**

Run: `grep -rln "wiki_scan\|wiki_ingest" packages/graph-wiki-mcp/tests/`
Open the named file; note how it invokes a tool function with its `*Input` model and a fake `ctx`, and how it patches the underlying `run_*` core function. Mirror that exactly in Step 2.

- [ ] **Step 2: Write the failing MCP test**

Add a test that patches `run_propagate_drift` and asserts the output fields. The tool never touches `ctx`, so a bare `MagicMock()` ctx suffices (no shared fixture needed):

```python
from pathlib import Path
from unittest.mock import MagicMock

import pytest


@pytest.mark.asyncio
async def test_wiki_propagate_drift_returns_summary(monkeypatch):
    import graph_wiki_mcp.server as srv
    from graph_wiki_core.commands.propagate_drift import PropagateDriftResult

    async def _fake(**kwargs):
        assert kwargs["dry_run"] is True
        assert kwargs["only"] is None
        return PropagateDriftResult(1, 2, 0, 1, 0, True, [])

    monkeypatch.setattr(srv, "run_propagate_drift", _fake)
    monkeypatch.setattr(srv, "resolve_wiki_and_repo",
                        lambda p: (Path("/w/wiki"), Path("/w/repo")))
    monkeypatch.setattr(srv, "read_only_connect",
                        lambda p: type("C", (), {"close": lambda self: None})())

    out = await srv.wiki_propagate_drift(
        srv.WikiPropagateDriftInput(dry_run=True), MagicMock()
    )
    assert out.pages_judged == 1
    assert out.entities_considered == 2
    assert out.dry_run is True
```

(If the package's pytest config sets `asyncio_mode = "auto"`, drop the `@pytest.mark.asyncio` decorator — confirm via `grep asyncio_mode packages/graph-wiki-mcp/pyproject.toml`.)

- [ ] **Step 3: Run the test to verify it fails**

Run: `uv run --package graph-wiki-mcp pytest -k propagate_drift -v`
Expected: FAIL — `wiki_propagate_drift` / `WikiPropagateDriftInput` do not exist.

- [ ] **Step 4: Add the MCP tool**

In `packages/graph-wiki-mcp/src/graph_wiki_mcp/server.py`, after the `wiki_scan` tool block (~line 292), add the imports (top-of-module style with `# noqa: E402` to match the file's existing late imports) and the tool:

```python
# --- wiki_propagate_drift tool (Living Wiki M4) ---

from graph_io.store import read_only_connect  # noqa: E402
from wiki_io._workspace import resolve_wiki_and_repo  # noqa: E402
from workspace_io.paths import graph_dir  # noqa: E402
from graph_wiki_core.commands.propagate_drift import (  # noqa: E402
    PropagateDriftResult,
    run_propagate_drift,
)


class WikiPropagateDriftInput(BaseModel):
    model_config = ConfigDict(extra='forbid')
    workspace_path: str = Field("", description="Workspace path (default: GRAPH_WIKI_WORKSPACE env var)")
    dry_run: bool = Field(False, description="Judge + report without writing notes or stamping anchors")
    only: str | None = Field(None, description="Restrict to one entity (uri/stem) or curated page (slug)")


class WikiPropagateDriftOutput(BaseModel):
    pages_judged: int
    entities_considered: int
    notes_written: int
    pages_stale: int
    pages_skipped_settled: int
    dry_run: bool
    proposals: list[dict]


@mcp.tool(
    name="wiki_propagate_drift",
    description="Propose curated-page updates for entities whose code changed (M4 drift producer).",
)
async def wiki_propagate_drift(
    input: WikiPropagateDriftInput, ctx: Context
) -> WikiPropagateDriftOutput:
    workspace = Path(input.workspace_path) if input.workspace_path else None
    wiki, repo = resolve_wiki_and_repo(workspace)
    conn = read_only_connect(graph_dir(wiki.parent) / "code.db")
    try:
        result: PropagateDriftResult = await run_propagate_drift(
            wiki=wiki, repo=repo, conn=conn, dry_run=input.dry_run, only=input.only
        )
    finally:
        conn.close()
    return WikiPropagateDriftOutput(
        pages_judged=result.pages_judged,
        entities_considered=result.entities_considered,
        notes_written=result.notes_written,
        pages_stale=result.pages_stale,
        pages_skipped_settled=result.pages_skipped_settled,
        dry_run=result.dry_run,
        proposals=result.proposals,
    )
```

- [ ] **Step 5: Run the test to verify it passes**

Run: `uv run --package graph-wiki-mcp pytest -k propagate_drift -v`
Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add packages/graph-wiki-mcp/src/graph_wiki_mcp/server.py packages/graph-wiki-mcp/tests/
git commit -m "feat(mcp): wiki_propagate_drift twin of gw wiki propagate-drift (M4 §3.7)

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

---

## Task 9: `gw scan --propagate-drift` opt-in flag

After the narrator refresh (narratives fresh, pages written, `last_updated_commit` advanced), an opt-in flag runs the same `run_propagate_drift` against the on-disk anchors. Off by default; gated alongside `narrate=True` (needs the Bedrock stack).

**Files:**
- Modify: `packages/graph-wiki-core/src/graph_wiki_core/commands/scan.py` (`run_scan` signature ~line 760; call site after the drift passes ~line 1352)
- Modify: `packages/graph-wiki-cli/src/graph_wiki_cli/cli.py` (`scan` command ~line 569)
- Modify: `packages/graph-wiki-mcp/src/graph_wiki_mcp/server.py` (`WikiScanInput` / `wiki_scan` ~line 245)
- Test: `packages/graph-wiki-core/tests/unit/test_human_section_drift.py` (this file already has the full-scan mock harness — the `ws` fixture mocks `_cg_run_build`/`make_llm`/`build_file_map`, and `_spy` replaces `SubagentPool.run_all` for the narrator/code_reader/drift_judge roles. Reuse it rather than re-deriving a partially-mocked scan.)

- [ ] **Step 1: Write the failing scan-integration tests**

Append to `packages/graph-wiki-core/tests/unit/test_human_section_drift.py` (it already imports `asyncio`, `scan_mod`, and defines the `ws` fixture + `_spy`). These exercise a full `run_scan` with the flag off/on and stub `scan_mod.run_propagate_drift` to assert the gating:

```python
def test_scan_propagate_drift_off_by_default(ws, monkeypatch):
    """[M4 §3.7 / §5 test 15] without the flag, scan never runs the M4 producer."""
    repo = ws / "repo"
    monkeypatch.setattr(
        scan_mod, "compute_state_gate",
        lambda repo: {"allowed": True, "reason": "clean", "head_commit": "head1"},
    )
    monkeypatch.setattr(scan_mod.SubagentPool, "run_all",
                        _spy(lambda it: {"stale": False, "reason": ""}))
    calls = {"n": 0}

    async def _pd(**kwargs):
        calls["n"] += 1
        from graph_wiki_core.commands.propagate_drift import PropagateDriftResult
        return PropagateDriftResult(0, 0, 0, 0, 0, False, [])

    monkeypatch.setattr(scan_mod, "run_propagate_drift", _pd)
    asyncio.run(scan_mod.run_scan(workspace_path=ws, repo_path=repo, narrate=True))
    assert calls["n"] == 0


def test_scan_propagate_drift_on_runs_producer(ws, monkeypatch):
    """[M4 §3.7 / §5 test 15] with the flag, the producer runs once after narration,
    called with the open conn + resolved wiki/repo."""
    repo = ws / "repo"
    monkeypatch.setattr(
        scan_mod, "compute_state_gate",
        lambda repo: {"allowed": True, "reason": "clean", "head_commit": "head1"},
    )
    monkeypatch.setattr(scan_mod.SubagentPool, "run_all",
                        _spy(lambda it: {"stale": False, "reason": ""}))
    captured: dict = {}

    async def _pd(**kwargs):
        captured.update(kwargs)
        from graph_wiki_core.commands.propagate_drift import PropagateDriftResult
        return PropagateDriftResult(0, 0, 0, 0, 0, False, [])

    monkeypatch.setattr(scan_mod, "run_propagate_drift", _pd)
    asyncio.run(scan_mod.run_scan(workspace_path=ws, repo_path=repo,
                                  narrate=True, propagate_drift=True))
    assert set(captured) >= {"wiki", "repo", "conn"}  # producer invoked with state
    assert captured["conn"] is not None
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `uv run --package graph-wiki-core pytest tests/unit/test_human_section_drift.py -k "propagate_drift" -v`
Expected: FAIL — `run_scan()` got an unexpected keyword argument `propagate_drift`.

- [ ] **Step 3: Add the `propagate_drift` param + import to `run_scan`**

In `packages/graph-wiki-core/src/graph_wiki_core/commands/scan.py`:

Add the import near the other core-command import (`from graph_wiki_core.commands.graph import run_build as _cg_run_build`, ~line 73):

```python
from graph_wiki_core.commands.propagate_drift import run_propagate_drift
```

Add the parameter to `run_scan` (after `narrate: bool = True,`, line 766):

```python
    narrate: bool = True,
    propagate_drift: bool = False,
```

Add to the docstring's Args (after the `narrate:` entry):

```
        propagate_drift: When True (and narrate=True), after the drift passes run
                        the M4 cross-page drift producer (gw wiki propagate-drift)
                        over the just-written entity pages, proposing curated-page
                        updates into the ledger. Off by default. Needs the
                        Bedrock stack (gated alongside narrate).
```

Add the call right after the `_drift_clear_pass(wiki)` line (~line 1352), inside the same block where `conn` is open (the propagator needs `conn` for the uri→path map):

```python
        # Free clear pass — runs every scan (even --no-narrate): a human edit to a
        # flagged section clears its flag promptly without an LLM call.
        _drift_clear_pass(wiki)

        # Living Wiki M4: opt-in cross-page drift producer. Runs after narration
        # (narratives fresh, last_updated_commit advanced) and reads M4's own
        # anchors off disk, so no in-memory state is threaded in. Gated on both
        # narrate (needs Bedrock) and the explicit flag (off by default, §3.7).
        if narrate and propagate_drift and conn is not None:
            await run_propagate_drift(wiki=wiki, repo=repo, conn=conn)
```

- [ ] **Step 4: Run the scan-integration tests to verify they pass**

Run: `uv run --package graph-wiki-core pytest tests/unit/test_human_section_drift.py -k "propagate_drift" -v`
Expected: PASS (both tests).

- [ ] **Step 5: Add the CLI flag**

In `packages/graph-wiki-cli/src/graph_wiki_cli/cli.py`, add the option to the `scan` command (after the `no_narrate` option, line 576) and thread it into `run_scan`:

```python
    no_narrate: bool = typer.Option(
        False, "--no-narrate", help="Skip narrator/file-describer fan-out (structural-only, no Bedrock)"
    ),
    propagate_drift: bool = typer.Option(
        False, "--propagate-drift", help="After narration, propose curated-page updates for changed entities (M4)"
    ),
    json_output: bool = typer.Option(False, "--json", help="Emit ScanResult as JSON"),
```

```python
            run_scan(
                workspace_path=workspace_path,
                no_file_map=no_file_map,
                max_depth=max_depth,
                narrate=not no_narrate,
                propagate_drift=propagate_drift,
            )
```

- [ ] **Step 6: Add the MCP flag**

In `packages/graph-wiki-mcp/src/graph_wiki_mcp/server.py`, add to `WikiScanInput` (after `max_depth`, ~line 249):

```python
    propagate_drift: bool = Field(
        False, description="After narration, propose curated-page updates for changed entities (M4)"
    )
```

and thread it into the `run_scan` call in `wiki_scan` (~line 271):

```python
    result: ScanResult = await run_scan(
        workspace_path=vault,
        no_file_map=input.no_file_map,
        max_depth=input.max_depth,
        repo_path=Path(input.repo_path).resolve() if input.repo_path else None,
        propagate_drift=input.propagate_drift,
    )
```

- [ ] **Step 7: Run the affected suites + smoke the help**

Run: `uv run --package graph-wiki-core pytest tests/unit/test_human_section_drift.py tests/commands/test_propagate_drift.py -q`
Run: `uv run --package graph-wiki-cli pytest -m "not integration" -q`
Run: `uv run --package graph-wiki-cli gw scan --help`
Expected: tests PASS; `--propagate-drift` appears in the scan help.

- [ ] **Step 8: Commit**

```bash
git add packages/graph-wiki-core/src/graph_wiki_core/commands/scan.py \
        packages/graph-wiki-cli/src/graph_wiki_cli/cli.py \
        packages/graph-wiki-mcp/src/graph_wiki_mcp/server.py \
        packages/graph-wiki-core/tests/unit/test_human_section_drift.py
git commit -m "feat(scan): opt-in --propagate-drift flag runs M4 producer post-narration (M4 §3.7)

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

---

## Task 10: Document the new provenance key

`drift_propagated_commit` is a new scanner-stamped, preserved, non-`SCANNER_OWNED_KEYS` provenance key — the M4 analog of `drift_checked_commit`. The backward-compatibility rule enumerates the provenance keys; add this one (§3.9). This is the only backward-compat rule change M4 requires.

**Files:**
- Modify: `.claude/rules/backward-compatibility.md`

- [ ] **Step 1: Read the provenance paragraph**

Run: `grep -n "last_updated_commit\|drift_checked_commit\|provenance" .claude/rules/backward-compatibility.md`
Locate the `**provenance**` bullet describing `last_updated_commit` (and any mention of `drift_checked_commit`).

- [ ] **Step 2: Add `drift_propagated_commit` to the provenance note**

Edit the `**provenance**` bullet in `.claude/rules/backward-compatibility.md` to add a sentence (place it after the existing `last_updated_commit` / `drift_checked_commit` description, matching the surrounding prose):

```markdown
    * **provenance** key `drift_propagated_commit` is scanner-stamped (the entity's `last_updated_commit` at which M4's drift producer last proposed against the curated pages backlinking it) and is preserved across re-scan. Like `last_updated_commit` and `drift_checked_commit` it is NOT in `SCANNER_OWNED_KEYS` — it gates the M4 cross-page drift pass (proposal ledger) and must survive re-scan to keep repeat runs idempotent.
```

- [ ] **Step 3: Verify the file reads coherently**

Run: `grep -n "drift_propagated_commit" .claude/rules/backward-compatibility.md`
Expected: the new line is present and reads consistently with the `drift_checked_commit` entry.

- [ ] **Step 4: Commit**

```bash
git add .claude/rules/backward-compatibility.md
git commit -m "docs(rules): note drift_propagated_commit provenance key (M4 §3.9)

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

---

## Final verification

- [ ] **Run every touched package suite**

```bash
uv run --package wiki-io pytest -q
uv run --package model-adapter pytest -q
uv run --package graph-wiki-core pytest -q
uv run --package graph-wiki-cli pytest -m "not integration" -q
uv run --package graph-wiki-mcp pytest -q
```

Expected: all green. (`integration`/`eval`-marked tests stay skipped — they need real Bedrock.)

- [ ] **Lint the changed files**

Run: `uv run ruff check packages/wiki-io/src/wiki_io/backlink_index.py packages/graph-wiki-core/src/graph_wiki_core/commands/propagate_drift.py packages/graph-wiki-core/src/graph_wiki_core/prompts/drift_propagator.py`
Expected: no new violations in the files you wrote (the wider tree has pre-existing lint debt — do not "fix" unrelated files).

- [ ] **Map the spec's 15 success criteria to tests**

Confirm each is covered (all in `test_propagate_drift.py` unless noted):
1. `build_entity_backlink_map` shape + behavior-preserving → `test_backlink_index.py` (Task 1) + pre-existing regen tests.
2. curated-kind filter (sources/work excluded) → `test_entity_with_no_curated_backlink_is_still_stamped` (sources excluded) + `_CATEGORY_TO_KIND`.
3. anchor gate → `test_candidate_when_anchors_differ`, `test_not_a_candidate_when_anchors_equal`, `test_absent_anchor_is_candidate`.
4. stamp + idempotent second run → `test_anchor_stamped_and_second_run_is_idempotent`.
5. `--dry-run` leaves anchor unstamped → `test_dry_run_judges_but_writes_nothing_and_does_not_stamp`.
6. settled target skipped → `test_settled_target_is_skipped`.
7. per-page batch, two origins, M4-reserved keys → `test_stale_page_with_two_entities_yields_one_note_two_origins`.
8. re-fire updates origin in place → `test_refire_same_entity_updates_origin_in_place`.
9. ADR annotate-only framing → `test_adr_rubric_is_annotate_only` (Task 3); `mode==update_existing` asserted in test 7.
10. non-stale → no note → `test_non_stale_page_writes_no_note`.
11. parse-miss fail-safe → `test_parse_fails_safe_on_garbage` / `test_parse_drops_findings_without_entity_stem_and_collapses_to_not_stale` (Task 3).
12. `--dry-run` report-only → `test_dry_run_judges_but_writes_nothing_and_does_not_stamp`.
13. `--only` entity/page → `test_only_entity_restricts_candidate_set`, `test_only_page_restricts_target_set`.
14. `PropagateDriftResult` / `--json` fields → `test_propagate_drift_json_output` (Task 7).
15. scan flag default-off / on → `test_scan_propagate_drift_off_by_default`, `test_scan_propagate_drift_on_runs_producer` (in `tests/unit/test_human_section_drift.py`, reusing the full-scan harness).

---

## Notes / decisions surfaced during planning

- **First-propagation change signal.** When `drift_propagated_commit` is absent, `changed_files_since(repo, "", node_path)` returns `None`; the candidate's `changed_files` is `[]`. The judge then works off the current narrative alone, which is the correct signal for a never-propagated entity. The prompt renders `(no specific files identified)` in that case.
- **`--only` mode disambiguation.** A single `--only <value>` is matched against candidate `uri`/`stem` first (entity mode → narrows the candidate set); only if it matches no candidate is it treated as a target slug/page-stem (target mode → narrows the target set). This makes both test-13 behaviors deterministic without a second flag.
- **Anchor stamping scope.** Non-target runs stamp every candidate (so the idempotency guarantee holds — including candidates with no curated backlinkers, per §3.5). Target-only (`--only <page>`) runs stamp only the candidates backlinking the chosen page (the ones actually processed). Candidates outside an `--only` scope are intentionally left for a later full run.
- **Backlink-regen double-load.** `regenerate_referenced_in_wiki` now reloads frontmatter per referencing entry (the extracted map carries `page_path`, not the `Post`). For real vaults this is a negligible cost and keeps the helper's return type aligned with M4's needs; the byte-output is unchanged and guarded by the existing regen tests.
- **Bedrock-absent behavior.** `run_propagate_drift` early-returns an all-zero result (and stamps nothing) when the Bedrock stack is unavailable — mirroring `_drift_flag_pass`. The scan flag is additionally gated on `narrate=True`, so the plugin's `narrate=False` branch never reaches it.
