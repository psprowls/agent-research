# Living Wiki M2e — Intra-Page Human-Section Drift Flagging Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** When an entity page's `## Narrative` regenerates (its code changed materially), judge each *human-owned* section against that fresh narrative on a cheap LLM tier and write a **flag into frontmatter** (`drift_review`) when the prose has gone stale — never auto-editing the prose.

**Architecture:** Purely additive. A free structural pre-filter (`drift_checked_commit != last_updated_commit`) selects pages whose narrative is newer than the last drift check; a `drift_judge` subagent fan-out (same `SubagentPool`/`make_llm` machinery as the narrator) judges each human H2 against the page's regenerated `## Narrative`; stale verdicts become `drift_review` entries. A separate free clear pass auto-resolves a flag when the flagged section's body-hash changes (human edited it). An `gw wiki ack-drift` subcommand clears flags without an edit. Two preserved frontmatter keys (`drift_checked_commit`, `drift_review`) — both kept out of `SCANNER_OWNED_KEYS`, exactly like the existing `last_updated_commit` anchor. Changes none of the M2a–M2d gate logic, the PTO merge, `needs_narrative`, or anchor stamping.

**Tech Stack:** Python 3, `pytest`, `langchain_core` messages, `subagent_runtime.pool.SubagentPool`, `model_adapter` role config (`models.toml`), `python-frontmatter` + `PyYAML`, Typer CLI. Monorepo packages: `wiki-io`, `graph-wiki-core`, `model-adapter`, `graph-wiki-cli`.

**Spec:** `docs/superpowers/specs/2026-06-04-living-wiki-m2e-human-section-drift-flagging-design.md`

**Preconditions verified against merged `main` (M2d merge `93fb80e4`):**
- `set_frontmatter_value` (`entity_writer.py:686`) is scalar-only (`value: str`, `fm[key] = value`) — M2e adds a structured sibling rather than touching it.
- Human-section helpers `_is_scanner_owned_heading` (`entity_writer.py:532`) and `_split_h2_sections` (`entity_writer.py:547`) survived the PTO rewrite intact; human-owned ⇔ `not _is_scanner_owned_heading(heading)`.
- The anchor-stamp post-pass (`scan.py:1122-1142`, stamping `last_updated_commit` over `good_prose_uris | redescribed_uris`) is where the drift post-pass inserts, immediately after, before Step 12 index regen.
- `extract_narrative` (`entity_writer.py:1129`) still exists in `wiki_io` (M2d only removed its now-unused *import* in `scan.py`); M2e re-imports it.
- Canonical role config is `packages/model-adapter/src/model_adapter/models.toml` (read via `resources.files("model_adapter").joinpath("models.toml")` in `loader.py:35`); the repo-root `packages/model-adapter/models.toml` is a stale partial copy NOT read at runtime.

**Out of scope (do not touch):** cross-page drift (M4), code-diff-grounded judging (M4), the open M2c suite-branch `if fm_targets:`/`no_file_map` asymmetry (`scan.py:969` — deferred to the agent-plugin parity plan, not drift work), auto-editing prose, a lint roll-up of open flags.

---

## File Structure

**New files:**
- `packages/wiki-io/src/wiki_io/drift.py` — pure, LLM-free drift helpers: enumerate human sections, hash a section body, extract narrative/file-map ground truth, recompute surviving flags. One responsibility: the section-level drift primitives, unit-testable without scan orchestration.
- `packages/graph-wiki-core/src/graph_wiki_core/prompts/drift_judge.py` — `DRIFT_JUDGE_SYSTEM` constant + `build_drift_judge_prompt(...)` + `parse_drift_verdict(...)`. Mirrors `prompts/file_describer.py`.
- `packages/graph-wiki-core/src/graph_wiki_core/commands/ack_drift.py` — `run_ack_drift(...)` + `AckDriftResult`. Mirrors `commands/log.py` / `commands/lint.py`.
- `packages/wiki-io/tests/unit/test_drift_helpers.py` — unit tests for `wiki_io/drift.py` + `update_frontmatter`.
- `packages/graph-wiki-core/tests/unit/test_human_section_drift.py` — integration tests for the scan post-pass (spec §5 cases 1-9).
- `packages/graph-wiki-cli/tests/...test_ack_drift_cli.py` — CLI test for `gw wiki ack-drift` (location matched to the package's existing CLI test dir; see Task 6).

**Modified files:**
- `packages/wiki-io/src/wiki_io/entity_writer.py` — add `update_frontmatter(...)` (structured value + key deletion in one atomic read-modify-write) next to `set_frontmatter_value`. `SCANNER_OWNED_KEYS` is **not** changed (drift keys stay preserved).
- `packages/graph-wiki-core/src/graph_wiki_core/commands/scan.py` — add `DRIFT_TARGET_KINDS`, `_drift_flag_pass(...)` (async), `_drift_clear_pass(...)` (sync); wire both into `run_scan` after the anchor-stamp block.
- `packages/model-adapter/src/model_adapter/models.toml` — add `[roles.drift_judge]` (cheap tier).
- `packages/graph-wiki-cli/src/graph_wiki_cli/wiki_cli/main.py` — add the `ack-drift` command.

---

## Task 1: Structured frontmatter setter (`update_frontmatter`)

`set_frontmatter_value` writes a single **scalar string** and never deletes. M2e needs to write a structured list (`drift_review`), set two keys in one atomic write (`drift_checked_commit` + `drift_review`), and remove a key when flags clear. Add a sibling that does all three; leave the load-bearing `set_frontmatter_value` (anchor stamping) untouched.

**Files:**
- Modify: `packages/wiki-io/src/wiki_io/entity_writer.py` (add after `set_frontmatter_value`, which ends at line 704)
- Test: `packages/wiki-io/tests/unit/test_drift_helpers.py` (create)

- [ ] **Step 1: Write the failing test**

Create `packages/wiki-io/tests/unit/test_drift_helpers.py`:

```python
"""Living Wiki M2e: unit tests for the structured frontmatter setter and the
pure drift helpers (wiki_io.drift)."""

from __future__ import annotations

import frontmatter as _fm
import pytest
from wiki_io.entity_writer import update_frontmatter


def _write(tmp_path, fm: str, body: str = "# T\n\n## Purpose\nx\n"):
    p = tmp_path / "page.md"
    p.write_text(f"---\n{fm}---\n{body}", encoding="utf-8")
    return p


def test_update_frontmatter_sets_structured_value(tmp_path):
    page = _write(tmp_path, "uri: pkg:a\nkind: package\n")
    update_frontmatter(
        page,
        {
            "drift_checked_commit": "abc123",
            "drift_review": [
                {"section": "Purpose", "detected_commit": "abc123",
                 "hash": "9f2c", "reason": "stale"}
            ],
        },
    )
    meta = _fm.load(page).metadata
    assert meta["drift_checked_commit"] == "abc123"
    assert meta["drift_review"] == [
        {"section": "Purpose", "detected_commit": "abc123",
         "hash": "9f2c", "reason": "stale"}
    ]


def test_update_frontmatter_deletes_key(tmp_path):
    page = _write(tmp_path, "uri: pkg:a\nkind: package\ndrift_review:\n- {section: Purpose}\n")
    update_frontmatter(page, {"drift_checked_commit": "x"}, delete=["drift_review"])
    meta = _fm.load(page).metadata
    assert "drift_review" not in meta
    assert meta["drift_checked_commit"] == "x"


def test_update_frontmatter_preserves_body_and_other_keys(tmp_path):
    page = _write(tmp_path, "uri: pkg:a\nkind: package\nsummary: keep me\n")
    update_frontmatter(page, {"drift_checked_commit": "x"})
    post = _fm.load(page)
    assert post.metadata["summary"] == "keep me"
    assert post.metadata["uri"] == "pkg:a"
    assert "## Purpose" in post.content


def test_update_frontmatter_missing_file_raises(tmp_path):
    with pytest.raises(FileNotFoundError):
        update_frontmatter(tmp_path / "nope.md", {"x": "y"})
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd packages/wiki-io && python -m pytest tests/unit/test_drift_helpers.py -k update_frontmatter -v`
Expected: FAIL with `ImportError: cannot import name 'update_frontmatter'`.

- [ ] **Step 3: Write minimal implementation**

In `packages/wiki-io/src/wiki_io/entity_writer.py`, add immediately after `set_frontmatter_value` (after line 704). Confirm `os` and `frontmatter` are already imported at module top (they are — used by `set_frontmatter_value`). Add `from collections.abc import Iterable` to the existing imports if not present:

```python
def update_frontmatter(
    page_path: Path,
    updates: dict[str, object] | None = None,
    *,
    delete: Iterable[str] = (),
) -> None:
    """Apply frontmatter `updates` and key `delete`s in one atomic read-modify-write.

    Structured sibling of `set_frontmatter_value` (which is scalar-string only):
    `updates` values may be any YAML-serializable object (e.g. the `drift_review`
    list-of-dicts); `delete` removes keys (e.g. dropping `drift_review` when its
    last flag clears). Body bytes and the canonical dump convention are preserved
    via `_render_page_text`, so a subsequent `write_entities` re-render is
    byte-identical. New keys append last (matching `merge_frontmatter`'s placement
    of non-scanner keys). Writes atomically via temp file + `os.replace`.

    Raises:
        FileNotFoundError: when `page_path` does not exist.
    """
    post = frontmatter.load(page_path)  # raises FileNotFoundError naturally
    fm = dict(post.metadata)
    for key, value in (updates or {}).items():
        fm[key] = value
    for key in delete:
        fm.pop(key, None)
    new_content = _render_page_text(fm, post.content)
    tmp_path = page_path.with_suffix(page_path.suffix + ".tmp")
    tmp_path.write_text(new_content, encoding="utf-8")
    os.replace(tmp_path, page_path)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd packages/wiki-io && python -m pytest tests/unit/test_drift_helpers.py -k update_frontmatter -v`
Expected: 4 passed.

- [ ] **Step 5: Commit**

```bash
git add packages/wiki-io/src/wiki_io/entity_writer.py packages/wiki-io/tests/unit/test_drift_helpers.py
git commit -m "feat(entity-writer): add update_frontmatter structured/delete setter (M2e §6)"
```

---

## Task 2: Pure drift helpers (`wiki_io/drift.py`)

The LLM-free primitives: enumerate human-owned H2 sections, hash a section body, pull the narrative + file-map ground truth from a page body, and recompute which flags survive after edits. Pure functions → unit-testable without scan orchestration. Reuses `_split_h2_sections` + `_is_scanner_owned_heading` + `_scanner_section_token` from `entity_writer` (intra-package import).

**Files:**
- Create: `packages/wiki-io/src/wiki_io/drift.py`
- Test: `packages/wiki-io/tests/unit/test_drift_helpers.py` (append)

- [ ] **Step 1: Write the failing test**

Append to `packages/wiki-io/tests/unit/test_drift_helpers.py`:

```python
from wiki_io.drift import (
    clear_resolved_flags,
    extract_file_map,
    iter_human_sections,
    section_hash,
)

_BODY = (
    "# pkg:a\n\n"
    "## Narrative\nThe package does async fan-out.\n\n"
    "## Purpose\nProcesses items synchronously.\n\n"
    "## Public API\n`run()`\n\n"
    "## File map - a\n\n| Path | Kind | Description |\n|---|---|---|\n"
    "| `x.py` | file | core |\n\n"
    "## Referenced in wiki\n- [[entities/foo]]\n"
)


def test_iter_human_sections_excludes_scanner_sections():
    secs = iter_human_sections(_BODY)
    headings = [h for h, _ in secs]
    assert headings == ["## Purpose", "## Public API"]
    # chunk includes the heading line
    assert secs[0][1].startswith("## Purpose")
    assert "synchronously" in secs[0][1]


def test_section_hash_is_stable_and_edit_sensitive():
    chunk = "## Purpose\nProcesses items synchronously.\n"
    assert section_hash(chunk) == section_hash(chunk + "\n\n")  # trailing ws ignored
    assert section_hash(chunk) != section_hash("## Purpose\nProcesses items async.\n")


def test_extract_file_map_returns_section_or_none():
    assert "| `x.py` |" in extract_file_map(_BODY)
    no_fm = "# t\n\n## Narrative\nn\n\n## Purpose\np\n"
    assert extract_file_map(no_fm) is None


def test_clear_resolved_flags_drops_edited_and_missing():
    purpose_chunk = "## Purpose\nProcesses items synchronously.\n\n"
    entries = [
        {"section": "Purpose", "detected_commit": "c1",
         "hash": section_hash(purpose_chunk), "reason": "r1"},
        {"section": "Public API", "detected_commit": "c1",
         "hash": "STALEHASH", "reason": "r2"},      # hash mismatch -> edited -> drop
        {"section": "Gone", "detected_commit": "c1",
         "hash": "whatever", "reason": "r3"},        # section absent -> drop
    ]
    survivors = clear_resolved_flags(entries, _BODY)
    assert [e["section"] for e in survivors] == ["Purpose"]


def test_clear_resolved_flags_keeps_all_when_unchanged():
    entries = [
        {"section": h.removeprefix("## "), "detected_commit": "c1",
         "hash": section_hash(chunk), "reason": "r"}
        for h, chunk in iter_human_sections(_BODY)
    ]
    assert clear_resolved_flags(entries, _BODY) == entries
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd packages/wiki-io && python -m pytest tests/unit/test_drift_helpers.py -k "iter_human or section_hash or extract_file_map or clear_resolved" -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'wiki_io.drift'`.

- [ ] **Step 3: Write minimal implementation**

Create `packages/wiki-io/src/wiki_io/drift.py`:

```python
from __future__ import annotations

"""Living Wiki M2e: pure (LLM-free) human-section drift primitives.

A human-owned page section can silently drift — the code it describes changed
while the curated prose stayed frozen. These helpers enumerate the human-owned
H2 sections of a page body, hash a section's body (to detect later edits), pull
the scanner-regenerated `## Narrative` / `## File map` that serve as the judge's
ground truth, and recompute which open `drift_review` flags survive after edits.

LLM judging and frontmatter I/O live in the scan pipeline; this module is the
side-effect-free core, mirroring the entity_writer section helpers it reuses.
"""

import hashlib

from wiki_io.entity_writer import (
    _is_scanner_owned_heading,
    _scanner_section_token,
    _split_h2_sections,
    extract_narrative,
)

__all__ = [
    "iter_human_sections",
    "section_hash",
    "extract_narrative",
    "extract_file_map",
    "clear_resolved_flags",
]


def iter_human_sections(body: str) -> list[tuple[str, str]]:
    """Return ``[(heading, chunk), ...]`` for every human-owned H2 section.

    A section is human-owned iff ``not _is_scanner_owned_heading(heading)`` — so
    `## Narrative`, `## File map[ - <name>]`, and `## Referenced in wiki` are
    excluded. Each ``chunk`` includes its heading line (same shape as
    ``_split_h2_sections``).
    """
    _preamble, sections = _split_h2_sections(body)
    return [
        (heading, chunk)
        for heading, chunk in sections
        if not _is_scanner_owned_heading(heading)
    ]


def section_hash(chunk: str) -> str:
    """SHA-256 hex digest of a section ``chunk`` (heading + body), whitespace
    stripped so trailing-newline churn never looks like an edit."""
    return hashlib.sha256(chunk.strip().encode("utf-8")).hexdigest()


def extract_file_map(body: str) -> str | None:
    """Return the stripped `## File map[ - <name>]` chunk, or None when absent.

    Passed to the judge as additional ground truth only for kinds that have a
    file map (package/app/test_suite); agent_plugin pages have none → None.
    """
    _preamble, sections = _split_h2_sections(body)
    for heading, chunk in sections:
        if (
            _is_scanner_owned_heading(heading)
            and _scanner_section_token(heading) == _scanner_section_token("## File map")
        ):
            return chunk.strip()
    return None


def clear_resolved_flags(entries: list[dict], body: str) -> list[dict]:
    """Return the subset of `drift_review` ``entries`` that still hold.

    An entry survives iff its section still exists in ``body`` AND that section's
    current ``section_hash`` equals the stored ``hash``. A hash mismatch means the
    prose was edited (the human addressed the flag); a missing section means it
    was removed — both drop the entry. Pure: no I/O, no side effects.
    """
    current: dict[str, str] = {
        heading.removeprefix("## ").strip(): section_hash(chunk)
        for heading, chunk in iter_human_sections(body)
    }
    survivors: list[dict] = []
    for entry in entries:
        section = entry.get("section")
        stored = entry.get("hash")
        if section in current and current[section] == stored:
            survivors.append(entry)
    return survivors
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd packages/wiki-io && python -m pytest tests/unit/test_drift_helpers.py -v`
Expected: all passed (the Task 1 `update_frontmatter` tests + these 5).

- [ ] **Step 5: Commit**

```bash
git add packages/wiki-io/src/wiki_io/drift.py packages/wiki-io/tests/unit/test_drift_helpers.py
git commit -m "feat(wiki-io): add pure human-section drift helpers (M2e §3.1/§3.2)"
```

---

## Task 3: `drift_judge` role + prompt module

Add the cheap-tier `drift_judge` role to the packaged `models.toml`, and a prompt module that builds the judge's `(system, human)` messages and parses its verdict. Parser fails **safe** (treats an unparseable response as *not* stale) so a flaky model never injects false flags.

**Files:**
- Modify: `packages/model-adapter/src/model_adapter/models.toml` (add a `[roles.drift_judge]` block)
- Create: `packages/graph-wiki-core/src/graph_wiki_core/prompts/drift_judge.py`
- Test: `packages/graph-wiki-core/tests/unit/test_drift_judge_prompt.py` (create)

- [ ] **Step 1: Write the failing test**

Create `packages/graph-wiki-core/tests/unit/test_drift_judge_prompt.py`:

```python
"""Living Wiki M2e: drift_judge prompt + verdict parser, and role config."""

from __future__ import annotations

from graph_wiki_core.prompts.drift_judge import (
    build_drift_judge_prompt,
    parse_drift_verdict,
)


def test_build_prompt_includes_section_and_narrative():
    system, human = build_drift_judge_prompt(
        heading="## Purpose",
        section_body="## Purpose\nProcesses items synchronously.\n",
        narrative="The package does async fan-out.",
        file_map="| `x.py` | file | core |",
    )
    assert "stale" in system.lower()
    assert "Purpose" in human
    assert "synchronously" in human
    assert "async fan-out" in human
    assert "x.py" in human  # file map included when provided


def test_build_prompt_omits_file_map_when_none():
    _system, human = build_drift_judge_prompt(
        heading="## Commands", section_body="## Commands\n/foo\n",
        narrative="An agent plugin.", file_map=None,
    )
    assert "File map" not in human


def test_parse_verdict_happy_path():
    v = parse_drift_verdict('{"stale": true, "reason": "narrative now async"}')
    assert v == {"stale": True, "reason": "narrative now async"}


def test_parse_verdict_strips_code_fence():
    v = parse_drift_verdict('```json\n{"stale": false, "reason": "ok"}\n```')
    assert v["stale"] is False


def test_parse_verdict_fails_safe_on_garbage():
    v = parse_drift_verdict("the model rambled with no json")
    assert v["stale"] is False
    assert isinstance(v["reason"], str)


def test_drift_judge_role_in_models_toml():
    from model_adapter.loader import load_role_config

    cfg = load_role_config("drift_judge")
    assert cfg["model_id"]
    assert cfg["max_concurrency"] >= 1
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd packages/graph-wiki-core && python -m pytest tests/unit/test_drift_judge_prompt.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'graph_wiki_core.prompts.drift_judge'`.

- [ ] **Step 3: Write minimal implementation**

3a. Add the role to `packages/model-adapter/src/model_adapter/models.toml` (append after the `[roles.narrator]` block, ~line 70). Cheap tier mirroring `scanner`; it is a short binary-ish classification, so `max_tokens` is small:

```toml
# Living Wiki M2e — intra-page human-section drift judge. Cheap classification
# role: compares a human-owned section against the page's regenerated narrative
# and returns {stale, reason}. Cost-offload candidate (validated later by the
# deepeval harness); initial config mirrors the cheap `scanner` tier.
[roles.drift_judge]
model_id        = "openai.gpt-oss-20b-1:0"
region          = "us-east-1"
max_tokens      = 256
max_concurrency = 10
sweep_candidates = [
  "openai.gpt-oss-20b-1:0",
  "zai.glm-4.7-flash",
  "qwen.qwen3-32b-v1:0",
  "us.amazon.nova-lite-v1:0",
  "mistral.ministral-3-14b-instruct",
]
```

> Note: only `packages/model-adapter/src/model_adapter/models.toml` is read at runtime (via `resources.files("model_adapter")`). Do **not** edit the repo-root `packages/model-adapter/models.toml` — it is a stale partial copy.

3b. Create `packages/graph-wiki-core/src/graph_wiki_core/prompts/drift_judge.py`:

```python
from __future__ import annotations

"""Living Wiki M2e: DRIFT_JUDGE prompt + verdict parser.

The drift judge receives one human-owned section of an entity page plus the
page's freshly-regenerated `## Narrative` (the scanner's current, code-derived
understanding) and decides whether the section's curated prose has gone stale
relative to that narrative. It judges against the narrative ONLY — it never
re-reads source (code-diff grounding is deferred to M4). Output is a tiny JSON
verdict; `parse_drift_verdict` fails safe (not-stale) on any unparseable reply,
so a flaky model can never inject a false flag.
"""

import json
import re

DRIFT_JUDGE_SYSTEM = """You judge whether a curated, human-written section of a wiki page has gone STALE relative to that page's machine-generated narrative.

You are given:
- the section's heading and body (human-authored prose), and
- the page's current `## Narrative` (regenerated from the code as it exists now),
- and sometimes a `## File map` listing for extra context.

The narrative reflects what the code does NOW. Decide whether the section's prose now CONTRADICTS or materially misdescribes what the narrative says. Examples of stale: the section claims synchronous processing but the narrative describes async fan-out; the section names a responsibility the narrative says moved elsewhere.

Do NOT flag a section merely because it covers different ground (e.g. a `## Public API` listing endpoints the narrative does not mention is fine), is shorter, or is stylistically different. Only flag a genuine contradiction or material drift.

Output ONLY a single JSON object, no prose and no code fences:
{"stale": true|false, "reason": "<one short line; empty string when not stale>"}"""

_FENCE_RE = re.compile(r"^```(?:json)?\s*|\s*```$", re.IGNORECASE)
_OBJ_RE = re.compile(r"\{.*\}", re.DOTALL)


def build_drift_judge_prompt(
    heading: str,
    section_body: str,
    narrative: str,
    file_map: str | None,
) -> tuple[str, str]:
    """Return ``(system, human)`` messages for one (section, narrative) judgement."""
    lines = [
        f"Section heading: {heading.strip()}",
        "",
        "Section body (human-authored prose):",
        section_body.strip(),
        "",
        "Current narrative (regenerated from the code as it exists now):",
        narrative.strip(),
    ]
    if file_map:
        lines += ["", "File map (for context):", file_map.strip()[:1500]]
    lines += ["", "Is the section body stale relative to the narrative? Reply with the JSON verdict."]
    return DRIFT_JUDGE_SYSTEM, "\n".join(lines)


def parse_drift_verdict(text: str) -> dict:
    """Parse a `{stale, reason}` verdict from the model reply. Fails SAFE: any
    unparseable / malformed reply yields ``{"stale": False, ...}`` so noise never
    becomes a false flag."""
    raw = _FENCE_RE.sub("", (text or "").strip())
    match = _OBJ_RE.search(raw)
    if match is None:
        return {"stale": False, "reason": "unparseable judge response"}
    try:
        obj = json.loads(match.group(0))
    except (ValueError, TypeError):
        return {"stale": False, "reason": "unparseable judge response"}
    stale = bool(obj.get("stale", False))
    reason = str(obj.get("reason", "")) if stale else ""
    return {"stale": stale, "reason": reason}
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd packages/graph-wiki-core && python -m pytest tests/unit/test_drift_judge_prompt.py -v`
Expected: 6 passed.

- [ ] **Step 5: Commit**

```bash
git add packages/model-adapter/src/model_adapter/models.toml packages/graph-wiki-core/src/graph_wiki_core/prompts/drift_judge.py packages/graph-wiki-core/tests/unit/test_drift_judge_prompt.py
git commit -m "feat(model-adapter,prompts): add drift_judge role + prompt/parser (M2e §3.3)"
```

---

## Task 4: Drift judge post-pass in `scan.py`

The flagging pass. Glob entity pages, apply the free pre-filter, fan out a `drift_judge` per human section against each page's regenerated `## Narrative`, and write `drift_review` + advance `drift_checked_commit` — once per (page, narrative-change).

**Pre-filter semantics (correctness-critical):** `last_updated_commit` only ever advances (stamped to HEAD when the narrative regenerates), so "narrative newer than last drift check" is exactly `drift_checked_commit != last_updated_commit` (a missing `drift_checked_commit` counts as lagging). Implement as **string inequality**, NOT `<` ordering — these are commit SHAs, not orderable.

Every *candidate* page (gate passed, narrative present) gets `drift_checked_commit` advanced even if it has zero human sections or zero stale verdicts — otherwise it re-enters the gate every scan.

**Files:**
- Modify: `packages/graph-wiki-core/src/graph_wiki_core/commands/scan.py` (imports near lines 36-50; new functions near the other module helpers ~line 567; wiring after the anchor-stamp block ~line 1142)
- Test: `packages/graph-wiki-core/tests/unit/test_human_section_drift.py` (create)

- [ ] **Step 1: Write the failing test**

Create `packages/graph-wiki-core/tests/unit/test_human_section_drift.py`:

```python
"""Living Wiki M2e: intra-page human-section drift flagging (spec §5)."""

from __future__ import annotations

import asyncio
import sqlite3
from pathlib import Path
from unittest.mock import MagicMock

import frontmatter as _fm
import graph_wiki_core.commands.scan as scan_mod
import pytest
from graph_io import exit_codes

_PKG_A = "pkg:org/repo/pkg-a"


def _seed_one_package(db_path: Path) -> None:
    from graph_io import schema

    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(db_path)
    try:
        schema.apply_schema(conn)
        conn.execute(
            "INSERT INTO nodes(kind, name, path, line, attrs_json, uri) VALUES "
            "('package', 'pkg-a', 'packages/pkg-a', NULL, '{\"language\": \"python\"}', "
            "'pkg:org/repo/pkg-a')"
        )
        conn.commit()
    finally:
        conn.close()


def _page_for(wiki: Path, uri: str = _PKG_A):
    return next(
        p for p in (wiki / "entities").glob("*.md")
        if _fm.load(p).metadata.get("uri") == uri
    )


@pytest.fixture
def ws(tmp_path, monkeypatch):
    workspace = tmp_path / "workspace"
    wiki = workspace / "wiki"
    repo = workspace / "repo"
    (wiki / ".graph-wiki").mkdir(parents=True)
    (wiki / "CLAUDE.md").write_text("# Wiki\n")
    (wiki / "log.md").write_text("", encoding="utf-8")
    repo.mkdir()
    monkeypatch.setenv("GRAPH_WIKI_WORKSPACE", str(workspace))
    _seed_one_package(workspace / ".graph" / "code.db")
    monkeypatch.setattr(
        scan_mod, "_cg_run_build", lambda repo, ws, *, full: (exit_codes.SUCCESS, "", "")
    )
    monkeypatch.setattr(scan_mod, "make_llm", lambda role, *, model_override=None: MagicMock())
    monkeypatch.setattr(
        scan_mod, "build_file_map",
        lambda path, **kw: (
            "## File map - pkg-a\nTODO\n\n### pkg-a/\nTODO\n\n"
            "| Path | Kind | Description |\n|---|---|---|\n"
            "| `pyproject.toml` | file | — TODO |\n"
            if str(path).endswith("pkg-a") else None
        ),
    )
    return workspace


def _spy(verdict_fn, *, recorder: dict | None = None):
    """Async SubagentPool.run_all replacement covering all three roles.

    narrator -> prose; code_reader -> JSON filling every TODO row; drift_judge ->
    verdict_fn(item). When `recorder` is given, records the drift_judge items so a
    test can assert the judge was (not) called.
    """
    async def _run_all(self, *, items, task, role, model_id, max_concurrency):
        from subagent_runtime.pool import FanOutResult

        result = FanOutResult()
        if role == "narrator":
            result.successes = [(it, f"PROSE for {it[0]}") for it in items]
        elif role == "code_reader":
            import json as _json
            result.successes = [
                (it, _json.dumps({p: f"desc {p}" for p in it[3]})) for it in items
            ]
        elif role == "drift_judge":
            if recorder is not None:
                recorder.setdefault("drift_items", []).extend(items)
            result.successes = [(it, verdict_fn(it)) for it in items]
        return result

    return _run_all


def _add_human_section(page: Path, heading: str, body: str) -> None:
    text = page.read_text(encoding="utf-8")
    page.write_text(text.rstrip("\n") + f"\n\n{heading}\n{body}\n", encoding="utf-8")


def test_renarrated_stale_section_is_flagged(ws, monkeypatch):
    """[§5.1] commit-dirty entity + stale human section -> drift_review entry;
    drift_checked_commit advances to last_updated_commit."""
    wiki = ws / "wiki"
    repo = ws / "repo"
    heads = {"v": "head1"}
    monkeypatch.setattr(
        scan_mod, "compute_state_gate",
        lambda repo: {"allowed": True, "reason": "clean", "head_commit": heads["v"]},
    )
    monkeypatch.setattr(scan_mod.SubagentPool, "run_all",
                        _spy(lambda it: {"stale": False, "reason": ""}))

    # Scan 1: page created + narrated + anchored at head1.
    asyncio.run(scan_mod.run_scan(workspace_path=ws, repo_path=repo, narrate=True))
    page = _page_for(wiki)
    _add_human_section(page, "## Purpose", "Processes items synchronously.")

    # Scan 2: code changed (head2) -> re-narrate -> judge says stale.
    heads["v"] = "head2"
    monkeypatch.setattr(scan_mod, "changed_files_since",
                        lambda repo, sha, sub: ["packages/pkg-a/mod.py"])
    monkeypatch.setattr(
        scan_mod.SubagentPool, "run_all",
        _spy(lambda it: {"stale": True, "reason": "now async"}),
    )
    asyncio.run(scan_mod.run_scan(workspace_path=ws, repo_path=repo, narrate=True))

    meta = _fm.load(_page_for(wiki)).metadata
    assert meta["drift_checked_commit"] == "head2"
    assert meta["last_updated_commit"] == "head2"
    review = meta["drift_review"]
    assert len(review) == 1
    assert review[0]["section"] == "Purpose"
    assert review[0]["detected_commit"] == "head2"
    assert review[0]["reason"] == "now async"
    assert review[0]["hash"]  # non-empty sha
    # Prose itself is untouched (flag-only).
    assert "Processes items synchronously." in _page_for(wiki).read_text(encoding="utf-8")


def test_already_checked_entity_skips_judge(ws, monkeypatch):
    """[§5.2/§5.4] narrative unchanged + drift_checked_commit == last_updated_commit
    -> no drift_judge call, no frontmatter change."""
    wiki = ws / "wiki"
    repo = ws / "repo"
    monkeypatch.setattr(
        scan_mod, "compute_state_gate",
        lambda repo: {"allowed": True, "reason": "clean", "head_commit": "head1"},
    )
    monkeypatch.setattr(scan_mod.SubagentPool, "run_all",
                        _spy(lambda it: {"stale": False, "reason": ""}))
    asyncio.run(scan_mod.run_scan(workspace_path=ws, repo_path=repo, narrate=True))
    _add_human_section(_page_for(wiki), "## Purpose", "p")

    # Re-scan, no code change -> narrative not regenerated.
    monkeypatch.setattr(scan_mod, "changed_files_since", lambda *a: [])
    rec: dict = {}
    monkeypatch.setattr(scan_mod.SubagentPool, "run_all",
                        _spy(lambda it: {"stale": True, "reason": "x"}, recorder=rec))
    before = _page_for(wiki).read_text(encoding="utf-8")
    asyncio.run(scan_mod.run_scan(workspace_path=ws, repo_path=repo, narrate=True))

    assert rec.get("drift_items", []) == []  # judge never ran
    assert "drift_review" not in _fm.load(_page_for(wiki)).metadata
    # First scan set drift_checked_commit == last_updated_commit already.
    assert _fm.load(_page_for(wiki)).metadata["drift_checked_commit"] == "head1"


def test_fresh_verdict_no_flag_but_checked_advances(ws, monkeypatch):
    """[§5.3] not-stale verdict -> no drift_review entry, but drift_checked_commit
    == last_updated_commit (so it won't re-judge next scan)."""
    wiki = ws / "wiki"
    repo = ws / "repo"
    monkeypatch.setattr(
        scan_mod, "compute_state_gate",
        lambda repo: {"allowed": True, "reason": "clean", "head_commit": "head1"},
    )
    monkeypatch.setattr(scan_mod.SubagentPool, "run_all",
                        _spy(lambda it: {"stale": False, "reason": ""}))
    asyncio.run(scan_mod.run_scan(workspace_path=ws, repo_path=repo, narrate=True))
    meta = _fm.load(_page_for(wiki)).metadata
    assert "drift_review" not in meta
    assert meta["drift_checked_commit"] == meta["last_updated_commit"] == "head1"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd packages/graph-wiki-core && python -m pytest tests/unit/test_human_section_drift.py -v`
Expected: FAIL — `drift_checked_commit` / `drift_review` keys absent (post-pass not wired yet).

- [ ] **Step 3: Write minimal implementation**

3a. Extend the `wiki_io.entity_writer` import block in `scan.py` (lines 36-50) to add `update_frontmatter` and `extract_narrative`:

```python
from wiki_io.entity_writer import (
    ADMITTED_KINDS,
    LAST_UPDATED_COMMIT_KEY,
    _compute_collision_set,
    _extract_file_map_descriptions,
    _kind_list_fns,
    extract_narrative,
    fill_file_map_descriptions,
    file_map_todo_paths,
    inject_file_map,
    inject_narrative,
    scanner_frontmatter_for_node,
    set_frontmatter_value,
    short_filename,
    update_frontmatter,
    write_entities,
)
```

3b. Add the `wiki_io.drift` + prompt imports near the other imports (after line 60):

```python
from wiki_io.drift import (
    clear_resolved_flags,
    extract_file_map,
    iter_human_sections,
    section_hash,
)
```

and after the existing `from graph_wiki_core.prompts.file_describer import FILE_DESCRIBER_SYSTEM` (line 64):

```python
from graph_wiki_core.prompts.drift_judge import (
    build_drift_judge_prompt,
    parse_drift_verdict,
)
```

3c. Add the target-kind constant + the post-pass function near the other module-level helpers (e.g. just after `_commit_dirty_changes`, ~line 568):

```python
# Living Wiki M2e: kinds with BOTH a regenerated `## Narrative` and human-owned
# sections worth drift-checking. `repository`/`domain`/`dependency` have no
# curated human prose and are excluded (spec §3.4). `agent_plugin` is included
# now for forward-compatibility — its commit-gated coverage completes with the
# agent-plugin parity plan, but it already narrates on structural change.
DRIFT_TARGET_KINDS: frozenset[str] = frozenset(
    {"package", "app", "test_suite", "agent_plugin"}
)


def _drift_candidates(wiki: Path) -> list[tuple[Path, str, str, str | None]]:
    """Return ``[(page_path, anchor, narrative, file_map), ...]`` for entity pages
    whose narrative is newer than their last drift check (spec §3.1 step 1).

    Gate (all required): kind in DRIFT_TARGET_KINDS; `last_updated_commit`
    present; `## Narrative` present (ground truth); and
    `drift_checked_commit != last_updated_commit` (a missing checked-commit
    counts as lagging). Comparison is string inequality — SHAs are not ordered.
    """
    entities_dir = wiki / "entities"
    if not entities_dir.is_dir():
        return []
    out: list[tuple[Path, str, str, str | None]] = []
    for page_path in sorted(entities_dir.glob("*.md")):
        try:
            post = frontmatter.load(page_path)
        except Exception:  # noqa: BLE001 — a malformed page must not abort scan
            continue
        meta = post.metadata
        if meta.get("kind") not in DRIFT_TARGET_KINDS:
            continue
        anchor = meta.get(LAST_UPDATED_COMMIT_KEY)
        if not anchor:
            continue
        if meta.get("drift_checked_commit") == anchor:
            continue  # already drift-checked at this narrative revision
        narrative = extract_narrative(post.content)
        if not narrative:
            continue  # no ground truth -> nothing to judge against
        out.append(
            (page_path, str(anchor), narrative, extract_file_map(post.content))
        )
    return out


async def _drift_flag_pass(wiki: Path, model_override: str | None) -> None:
    """Judge each human-owned section of every drift candidate against its page's
    regenerated narrative; write `drift_review` + advance `drift_checked_commit`.

    Judge-once: only candidate pages (narrative newer than last check) are judged,
    and each is stamped to its anchor afterward, so a (page, narrative-change) pair
    costs LLM tokens exactly once (spec §3.1/D3).
    """
    if make_llm is None or SubagentPool is None:  # bedrock stack absent
        return
    candidates = _drift_candidates(wiki)
    if not candidates:
        return

    # Flatten to one judge item per (page, human section). Carry the page anchor
    # and chunk so flags can be assembled without re-reading.
    # item = (page_path, anchor, heading, chunk, narrative, file_map)
    items: list[tuple[Path, str, str, str, str, str | None]] = []
    page_anchor: dict[Path, str] = {}
    for page_path, anchor, narrative, file_map in candidates:
        page_anchor[page_path] = anchor
        body = page_path.read_text(encoding="utf-8")
        for heading, chunk in iter_human_sections(body):
            items.append((page_path, anchor, heading, chunk, narrative, file_map))

    verdicts: list[tuple] = []
    if items:
        drift_cfg = load_role_config("drift_judge")
        drift_llm = make_llm("drift_judge", model_override=model_override)
        drift_pool = SubagentPool(trace_dir=wiki / ".graph-wiki" / "traces")

        async def judge(item: tuple) -> TaskResult:
            _pp, _anchor, heading, chunk, narrative, file_map = item
            system_msg, human_msg = build_drift_judge_prompt(
                heading, chunk, narrative, file_map
            )
            resp = await drift_llm.ainvoke(
                [SystemMessage(content=system_msg), HumanMessage(content=human_msg)]
            )
            return TaskResult(value=parse_drift_verdict(resp.content), response=resp)

        fan = await drift_pool.run_all(
            items=items,
            task=judge,
            role="drift_judge",
            model_id=drift_cfg["model_id"],
            max_concurrency=drift_cfg["max_concurrency"],
        )
        verdicts = list(fan.successes)

    # Assemble stale flags per page.
    flags_by_page: dict[Path, list[dict]] = {}
    for item, verdict in verdicts:
        page_path, anchor, heading, chunk, _narr, _fm = item
        if isinstance(verdict, dict) and verdict.get("stale"):
            flags_by_page.setdefault(page_path, []).append(
                {
                    "section": heading.removeprefix("## ").strip(),
                    "detected_commit": anchor,
                    "hash": section_hash(chunk),
                    "reason": str(verdict.get("reason", "")),
                }
            )

    # Write once per candidate page (even those with no sections / no stale
    # verdict) so drift_checked_commit advances and the gate closes.
    for page_path, anchor in page_anchor.items():
        entries = flags_by_page.get(page_path)
        try:
            if entries:
                update_frontmatter(
                    page_path,
                    {"drift_checked_commit": anchor, "drift_review": entries},
                )
            else:
                update_frontmatter(
                    page_path,
                    {"drift_checked_commit": anchor},
                    delete=["drift_review"],
                )
        except Exception as exc:  # noqa: BLE001 — non-fatal flag write
            logger.warning("drift flag write failed for %s: %s", page_path, exc)
```

3d. Wire the pass into `run_scan`. Immediately after the anchor-stamp block (after line 1142, before the `# Step 12: regenerate indexes` comment at line 1144), add:

```python
        # Living Wiki M2e: human-section drift flagging post-pass. Runs after
        # anchor stamping so each page holds its final `## Narrative` and settled
        # human sections plus its freshly-stamped last_updated_commit. Gated on
        # `narrate` (needs the cheap-tier drift_judge LLM); self-recovers any page
        # whose drift pass was skipped in a prior scan (drift_checked_commit lag).
        if narrate:
            await _drift_flag_pass(wiki, model_override)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd packages/graph-wiki-core && python -m pytest tests/unit/test_human_section_drift.py -v`
Expected: 3 passed (`test_renarrated_stale_section_is_flagged`, `test_already_checked_entity_skips_judge`, `test_fresh_verdict_no_flag_but_checked_advances`).

- [ ] **Step 5: Commit**

```bash
git add packages/graph-wiki-core/src/graph_wiki_core/commands/scan.py packages/graph-wiki-core/tests/unit/test_human_section_drift.py
git commit -m "feat(scan): drift_judge post-pass — flag stale human sections (M2e §3.1)"
```

---

## Task 5: Free clear pass + scope/preservation guards

The clear pass auto-resolves a flag the moment its section's body-hash changes (a human edited the prose) — free, every scan, even `--no-narrate`. Plus the scope guards: non-target kinds and narrative-less pages are never flagged, and the two keys survive re-scan (proving they're correctly *not* in `SCANNER_OWNED_KEYS`).

**Files:**
- Modify: `packages/graph-wiki-core/src/graph_wiki_core/commands/scan.py` (add `_drift_clear_pass`; wire it after the flag pass)
- Test: `packages/graph-wiki-core/tests/unit/test_human_section_drift.py` (append), `packages/wiki-io/tests/unit/test_drift_helpers.py` (append — preservation unit test)

- [ ] **Step 1: Write the failing tests**

5a. Append to `packages/graph-wiki-core/tests/unit/test_human_section_drift.py`:

```python
def test_auto_clear_on_edit_no_judge_call(ws, monkeypatch):
    """[§5.5] editing a flagged section's body clears its flag next scan with NO
    drift_judge call; an emptied drift_review key is removed."""
    wiki = ws / "wiki"
    repo = ws / "repo"
    monkeypatch.setattr(
        scan_mod, "compute_state_gate",
        lambda repo: {"allowed": True, "reason": "clean", "head_commit": "head1"},
    )
    monkeypatch.setattr(scan_mod.SubagentPool, "run_all",
                        _spy(lambda it: {"stale": False, "reason": ""}))
    asyncio.run(scan_mod.run_scan(workspace_path=ws, repo_path=repo, narrate=True))
    page = _page_for(wiki)
    _add_human_section(page, "## Purpose", "Processes items synchronously.")

    # Code change -> re-narrate -> stale flag written at head2.
    monkeypatch.setattr(
        scan_mod, "compute_state_gate",
        lambda repo: {"allowed": True, "reason": "clean", "head_commit": "head2"},
    )
    monkeypatch.setattr(scan_mod, "changed_files_since",
                        lambda repo, sha, sub: ["packages/pkg-a/mod.py"])
    monkeypatch.setattr(scan_mod.SubagentPool, "run_all",
                        _spy(lambda it: {"stale": True, "reason": "now async"}))
    asyncio.run(scan_mod.run_scan(workspace_path=ws, repo_path=repo, narrate=True))
    assert _fm.load(_page_for(wiki)).metadata.get("drift_review")

    # Human edits the flagged Purpose body; re-scan with no code change.
    page = _page_for(wiki)
    text = page.read_text(encoding="utf-8").replace(
        "Processes items synchronously.", "Processes items via async fan-out."
    )
    page.write_text(text, encoding="utf-8")
    monkeypatch.setattr(scan_mod, "changed_files_since", lambda *a: [])
    rec: dict = {}
    monkeypatch.setattr(scan_mod.SubagentPool, "run_all",
                        _spy(lambda it: {"stale": True, "reason": "x"}, recorder=rec))
    asyncio.run(scan_mod.run_scan(workspace_path=ws, repo_path=repo, narrate=True))

    assert rec.get("drift_items", []) == []  # clear pass is free; no judge
    assert "drift_review" not in _fm.load(_page_for(wiki)).metadata


def test_dependency_and_narrativeless_never_flagged(ws, monkeypatch):
    """[§5.8] a non-target kind and a page without a narrative produce no judge
    calls and no drift keys."""
    wiki = ws / "wiki"
    repo = ws / "repo"
    monkeypatch.setattr(
        scan_mod, "compute_state_gate",
        lambda repo: {"allowed": True, "reason": "clean", "head_commit": "head1"},
    )
    rec: dict = {}
    monkeypatch.setattr(scan_mod.SubagentPool, "run_all",
                        _spy(lambda it: {"stale": True, "reason": "x"}, recorder=rec))

    # A hand-written dependency page (non-target kind) + a narrative-less package.
    (wiki / "entities").mkdir(parents=True, exist_ok=True)
    dep = wiki / "entities" / "dep-foo.md"
    dep.write_text(
        "---\nuri: dep:foo\nkind: dependency\nlast_updated_commit: head1\n---\n"
        "# dep:foo\n\n## Purpose\nA dependency.\n",
        encoding="utf-8",
    )
    asyncio.run(scan_mod.run_scan(workspace_path=ws, repo_path=repo, narrate=True))

    dep_meta = _fm.load(dep).metadata
    assert "drift_review" not in dep_meta
    assert "drift_checked_commit" not in dep_meta
    # The dependency page never produced a judge item.
    assert all(it[0] != dep for it in rec.get("drift_items", []))
```

5b. Append a preservation unit test to `packages/wiki-io/tests/unit/test_drift_helpers.py` (guards spec §5.7 — the keys must not be in `SCANNER_OWNED_KEYS`):

```python
def test_drift_keys_are_not_scanner_owned():
    """Guards §5.7: drift_checked_commit / drift_review must be PRESERVED across
    re-scan, so they must never be added to SCANNER_OWNED_KEYS (which merge wipes
    to template values)."""
    from wiki_io.entity_writer import SCANNER_OWNED_KEYS

    assert "drift_checked_commit" not in SCANNER_OWNED_KEYS
    assert "drift_review" not in SCANNER_OWNED_KEYS


def test_merge_frontmatter_preserves_drift_keys():
    """A scanner re-render keeps unknown preserved keys (like last_updated_commit,
    drift_checked_commit, drift_review)."""
    from wiki_io.entity_writer import merge_frontmatter

    existing = {
        "uri": "pkg:a", "kind": "package",
        "drift_checked_commit": "abc",
        "drift_review": [{"section": "Purpose", "hash": "h", "detected_commit": "abc", "reason": "r"}],
    }
    scanner = {"uri": "pkg:a", "kind": "package"}
    merged = merge_frontmatter(existing, scanner)
    assert merged["drift_checked_commit"] == "abc"
    assert merged["drift_review"] == existing["drift_review"]
```

> If `merge_frontmatter`'s real signature differs (check `entity_writer.py` around line 360), adapt the call in `test_merge_frontmatter_preserves_drift_keys` to match — the assertion (drift keys survive a merge) is what matters. If `merge_frontmatter` is not the public entry point, assert via a `write_entities` no-op round-trip instead.

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd packages/graph-wiki-core && python -m pytest tests/unit/test_human_section_drift.py -k "auto_clear or dependency" -v`
Expected: `test_auto_clear_on_edit_no_judge_call` FAILS (clear pass not implemented — flag persists).
Run: `cd packages/wiki-io && python -m pytest tests/unit/test_drift_helpers.py -k "scanner_owned or preserves_drift" -v`
Expected: both PASS already if the keys were never added to `SCANNER_OWNED_KEYS` (this is a regression guard — it should pass, confirming no accidental addition). If either fails, a prior task wrongly touched `SCANNER_OWNED_KEYS`; revert that.

- [ ] **Step 3: Write minimal implementation**

Add `_drift_clear_pass` to `scan.py` after `_drift_flag_pass`:

```python
def _drift_clear_pass(wiki: Path) -> None:
    """Free, every-scan flag resolution (spec §3.2/D4). For every entity page
    holding a `drift_review` key, recompute each flagged section's current hash;
    drop entries whose hash changed (prose edited) or whose section is gone, and
    remove the key when it empties. No LLM, runs even on --no-narrate scans."""
    entities_dir = wiki / "entities"
    if not entities_dir.is_dir():
        return
    for page_path in sorted(entities_dir.glob("*.md")):
        try:
            post = frontmatter.load(page_path)
        except Exception:  # noqa: BLE001 — malformed page must not abort scan
            continue
        entries = post.metadata.get("drift_review")
        if not entries:
            continue
        survivors = clear_resolved_flags(entries, post.content)
        if survivors == entries:
            continue
        try:
            if survivors:
                update_frontmatter(page_path, {"drift_review": survivors})
            else:
                update_frontmatter(page_path, delete=["drift_review"])
        except Exception as exc:  # noqa: BLE001 — non-fatal
            logger.warning("drift clear write failed for %s: %s", page_path, exc)
```

Wire it into `run_scan` immediately after the `if narrate: await _drift_flag_pass(...)` block added in Task 4 (the clear pass is free and unconditional):

```python
        # Free clear pass — runs every scan (even --no-narrate): a human edit to a
        # flagged section clears its flag promptly without an LLM call.
        _drift_clear_pass(wiki)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd packages/graph-wiki-core && python -m pytest tests/unit/test_human_section_drift.py -v`
Expected: 5 passed.
Run: `cd packages/wiki-io && python -m pytest tests/unit/test_drift_helpers.py -v`
Expected: all passed.

- [ ] **Step 5: Commit**

```bash
git add packages/graph-wiki-core/src/graph_wiki_core/commands/scan.py packages/graph-wiki-core/tests/unit/test_human_section_drift.py packages/wiki-io/tests/unit/test_drift_helpers.py
git commit -m "feat(scan): free clear pass + scope/preservation guards (M2e §3.2/D4)"
```

---

## Task 6: `gw wiki ack-drift` subcommand

The no-edit escape hatch: "I reviewed the flag, the prose is still correct." Clears all `drift_review` entries for a page without touching the prose. Because `drift_checked_commit` already equals `last_updated_commit` after the judge ran, the section is not re-judged until the narrative changes again.

**Files:**
- Create: `packages/graph-wiki-core/src/graph_wiki_core/commands/ack_drift.py`
- Modify: `packages/graph-wiki-cli/src/graph_wiki_cli/wiki_cli/main.py` (add the command)
- Test: `packages/graph-wiki-core/tests/unit/test_human_section_drift.py` (append — core function); CLI smoke test (see Step 1c)

- [ ] **Step 1: Write the failing tests**

1a. Core-function test — append to `packages/graph-wiki-core/tests/unit/test_human_section_drift.py`:

```python
def test_ack_drift_clears_without_edit(ws, monkeypatch):
    """[§5.6] ack-drift removes all drift_review entries; a subsequent no-change
    scan does not re-flag (drift_checked_commit already current)."""
    from graph_wiki_core.commands.ack_drift import run_ack_drift

    wiki = ws / "wiki"
    repo = ws / "repo"
    monkeypatch.setattr(
        scan_mod, "compute_state_gate",
        lambda repo: {"allowed": True, "reason": "clean", "head_commit": "head1"},
    )
    monkeypatch.setattr(scan_mod.SubagentPool, "run_all",
                        _spy(lambda it: {"stale": False, "reason": ""}))
    asyncio.run(scan_mod.run_scan(workspace_path=ws, repo_path=repo, narrate=True))
    page = _page_for(wiki)
    _add_human_section(page, "## Purpose", "Processes items synchronously.")
    monkeypatch.setattr(
        scan_mod, "compute_state_gate",
        lambda repo: {"allowed": True, "reason": "clean", "head_commit": "head2"},
    )
    monkeypatch.setattr(scan_mod, "changed_files_since",
                        lambda repo, sha, sub: ["packages/pkg-a/mod.py"])
    monkeypatch.setattr(scan_mod.SubagentPool, "run_all",
                        _spy(lambda it: {"stale": True, "reason": "now async"}))
    asyncio.run(scan_mod.run_scan(workspace_path=ws, repo_path=repo, narrate=True))
    assert _fm.load(_page_for(wiki)).metadata.get("drift_review")

    # Ack by URI -> flags cleared, prose untouched.
    result = run_ack_drift(_PKG_A, workspace_path=ws)
    assert result.cleared == 1
    meta = _fm.load(_page_for(wiki)).metadata
    assert "drift_review" not in meta
    assert "Processes items synchronously." in _page_for(wiki).read_text(encoding="utf-8")

    # No-change re-scan -> not re-flagged (checked-commit already == anchor).
    monkeypatch.setattr(scan_mod, "changed_files_since", lambda *a: [])
    monkeypatch.setattr(scan_mod.SubagentPool, "run_all",
                        _spy(lambda it: {"stale": True, "reason": "x"}))
    asyncio.run(scan_mod.run_scan(workspace_path=ws, repo_path=repo, narrate=True))
    assert "drift_review" not in _fm.load(_page_for(wiki)).metadata


def test_ack_drift_unknown_entity_raises(ws):
    from graph_wiki_core.commands.ack_drift import run_ack_drift

    with pytest.raises(ValueError):
        run_ack_drift("pkg:does/not/exist", workspace_path=ws)
```

1b. Decide the CLI test location: `ls packages/graph-wiki-cli/tests/` to find the existing wiki-CLI test module (e.g. a `test_wiki_cli*.py` or a Typer `CliRunner` harness). Add the smoke test there, mirroring an existing `gw wiki` command test (e.g. how `log` or `lint` is invoked via `typer.testing.CliRunner`). The smoke test asserts: `gw wiki ack-drift <uri> --workspace <ws>` exits 0 and prints the cleared count; and a missing entity exits non-zero. If no such harness exists, the core-function tests in 1a are sufficient coverage and the CLI body is a thin delegate — note that in the commit message.

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd packages/graph-wiki-core && python -m pytest tests/unit/test_human_section_drift.py -k ack_drift -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'graph_wiki_core.commands.ack_drift'`.

- [ ] **Step 3: Write minimal implementation**

3a. Create `packages/graph-wiki-core/src/graph_wiki_core/commands/ack_drift.py`:

```python
from __future__ import annotations

"""Living Wiki M2e: `gw wiki ack-drift <entity>` — clear a page's drift flags
without editing the prose (the "I reviewed it, prose is still correct" case).

Resolves the entity (by URI or page stem) to its entity page and removes the
`drift_review` key. No LLM. Because `drift_checked_commit` already equals
`last_updated_commit` after the judge ran, the page is not re-judged until its
narrative changes again."""

from dataclasses import dataclass
from pathlib import Path

import frontmatter

from wiki_io._workspace import resolve_wiki_and_repo
from wiki_io.entity_writer import update_frontmatter


@dataclass
class AckDriftResult:
    page_path: Path
    cleared: int


def _resolve_entity_page(wiki: Path, entity: str) -> Path:
    """Find the entity page whose `uri` == entity, else whose filename stem ==
    entity. Raises ValueError on no match or ambiguity."""
    entities_dir = wiki / "entities"
    by_uri: list[Path] = []
    by_stem: list[Path] = []
    if entities_dir.is_dir():
        for page_path in sorted(entities_dir.glob("*.md")):
            try:
                meta = frontmatter.load(page_path).metadata
            except Exception:  # noqa: BLE001
                continue
            if meta.get("uri") == entity:
                by_uri.append(page_path)
            if page_path.stem == entity:
                by_stem.append(page_path)
    matches = by_uri or by_stem
    if not matches:
        raise ValueError(f"no entity page found for {entity!r}")
    if len(matches) > 1:
        raise ValueError(f"ambiguous entity {entity!r}: {[str(m) for m in matches]}")
    return matches[0]


def run_ack_drift(entity: str, workspace_path: Path | None = None) -> AckDriftResult:
    """Clear all `drift_review` flags for `entity`. Returns the page + count cleared."""
    wiki, _repo = resolve_wiki_and_repo(workspace_path)
    page_path = _resolve_entity_page(wiki, entity)
    entries = frontmatter.load(page_path).metadata.get("drift_review") or []
    cleared = len(entries)
    if cleared:
        update_frontmatter(page_path, delete=["drift_review"])
    return AckDriftResult(page_path=page_path, cleared=cleared)
```

3b. Add the CLI command to `packages/graph-wiki-cli/src/graph_wiki_cli/wiki_cli/main.py` (after the `lint` command, before the ingest sub-app at line 165). Add the import near the other `graph_wiki_core.commands.*` imports (lines 21-28): `from graph_wiki_core.commands.ack_drift import run_ack_drift`:

```python
@wiki_app.command(name="ack-drift")
def ack_drift(
    entity: str = typer.Argument(..., help="Entity URI or page slug to clear drift flags for"),
    workspace: str = typer.Option("", "--workspace", help="Workspace path (default: GRAPH_WIKI_WORKSPACE env var)"),
    json_output: bool = typer.Option(False, "--json", help="Emit the result as JSON"),
) -> None:
    """Acknowledge (clear) human-section drift flags on an entity page without editing its prose."""
    workspace_path = Path(workspace) if workspace else None
    try:
        result = run_ack_drift(entity, workspace_path=workspace_path)
    except (RuntimeError, ValueError, FileNotFoundError) as e:
        typer.echo(f"Error: {e}", err=True)
        raise typer.Exit(code=1)

    if json_output:
        typer.echo(json.dumps(dataclasses.asdict(result), indent=2, default=str))
    else:
        typer.echo(f"[ok] Cleared {result.cleared} drift flag(s): {result.page_path}")
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd packages/graph-wiki-core && python -m pytest tests/unit/test_human_section_drift.py -k ack_drift -v`
Expected: 2 passed.
Run (CLI, if a harness exists per Step 1b): `cd packages/graph-wiki-cli && python -m pytest tests/ -k ack_drift -v`
Expected: passed.

- [ ] **Step 5: Commit**

```bash
git add packages/graph-wiki-core/src/graph_wiki_core/commands/ack_drift.py packages/graph-wiki-cli/src/graph_wiki_cli/wiki_cli/main.py packages/graph-wiki-core/tests/unit/test_human_section_drift.py
# include the CLI test file if added
git commit -m "feat(cli): add gw wiki ack-drift subcommand (M2e §3.5/D4)"
```

---

## Task 7: agent_plugin coverage + full-suite verification

Confirm `agent_plugin` pages are judged (forward-compat per §1.4 / §5.9), then verify the full suites against the known baseline.

**Files:**
- Test: `packages/graph-wiki-core/tests/unit/test_human_section_drift.py` (append §5.9)

- [ ] **Step 1: Write the agent_plugin test**

Append to `packages/graph-wiki-core/tests/unit/test_human_section_drift.py`. This exercises the candidate filter + judge directly on a hand-written `agent_plugin` page (no `## File map`), avoiding the need to seed the graph with an agent_plugin node:

```python
def test_agent_plugin_judged_without_file_map(ws, monkeypatch):
    """[§5.9] an agent_plugin page (narrative present, NO file map) has its human
    sections judged against its narrative; file_map passed to the judge is None;
    a stale verdict flags it."""
    wiki = ws / "wiki"
    (wiki / "entities").mkdir(parents=True, exist_ok=True)
    page = wiki / "entities" / "agent-plugin-foo.md"
    page.write_text(
        "---\nuri: agent_plugin:org/repo/foo\nkind: agent_plugin\n"
        "last_updated_commit: head1\n---\n"
        "# foo\n\n## Narrative\nProvides three slash commands via async hooks.\n\n"
        "## Commands\nExposes a single synchronous command.\n",
        encoding="utf-8",
    )

    captured: dict = {}

    def _verdict(item):
        # item = (page_path, anchor, heading, chunk, narrative, file_map)
        captured["file_map"] = item[5]
        captured["heading"] = item[2]
        return {"stale": True, "reason": "command count drifted"}

    monkeypatch.setattr(scan_mod.SubagentPool, "run_all", _spy(_verdict))
    asyncio.run(scan_mod._drift_flag_pass(wiki, None))

    assert captured["file_map"] is None      # agent_plugin has no File map
    assert captured["heading"] == "## Commands"
    meta = _fm.load(page).metadata
    assert meta["drift_checked_commit"] == "head1"
    assert meta["drift_review"][0]["section"] == "Commands"
```

- [ ] **Step 2: Run the test to verify it passes**

Run: `cd packages/graph-wiki-core && python -m pytest tests/unit/test_human_section_drift.py -k agent_plugin -v`
Expected: PASS. (If it fails because `_drift_flag_pass` early-returns when `make_llm`/`SubagentPool` are None, note the fixture `ws` patches `make_llm`; the test calls `_drift_flag_pass` directly so ensure `scan_mod.make_llm`/`SubagentPool` are non-None in this environment — they are imported at module load when the bedrock stack is installed. If running where the stack is absent, mark this test `@pytest.mark.skipif(scan_mod.make_llm is None, ...)`.)

- [ ] **Step 3: Run the full affected suites against the known baseline**

Run:
```bash
cd packages/wiki-io && python -m pytest -q
cd packages/graph-wiki-core && python -m pytest -q
cd packages/model-adapter && python -m pytest -q
cd packages/graph-wiki-cli && python -m pytest -q
```
Expected: all green **except** the two known pre-existing graph-wiki-core failures unrelated to M2e:
`test_scan_decontainerize_parity::test_scan_entities_tree_snapshot` (stale syrupy snapshot) and `test_scan_graph_integration::test_file_map_injected_into_app_entity_page`.
**Verify any new red is genuinely new against this baseline** — if a failure is not one of those two, it is M2e fallout and must be fixed before the milestone closes.

- [ ] **Step 4: Lint / typecheck the touched packages**

Run the repo's configured linters on the changed files (e.g. `ruff check packages/wiki-io packages/graph-wiki-core packages/graph-wiki-cli packages/model-adapter` and any `import-linter`/`mypy` step the repo uses in CI). Fix style/`I001` import-sort issues. Expected: clean.

- [ ] **Step 5: Commit**

```bash
git add packages/graph-wiki-core/tests/unit/test_human_section_drift.py
git commit -m "test(scan): agent_plugin drift coverage + M2e suite verification (M2e §5.9)"
```

---

## Self-Review

**1. Spec coverage** (each §3/§4/§5 item → task):
- §3.1 drift post-pass (pre-filter → fan-out → write flags) → Task 4 (`_drift_candidates`, `_drift_flag_pass`). ✓
- §3.2 free clear pass → Task 5 (`_drift_clear_pass`). ✓
- §3.3 `drift_judge` role + `make_llm`/`SubagentPool` invocation → Task 3 (role) + Task 4 (invocation mirrors narrator). ✓
- §3.4 target kinds package/app/test_suite/agent_plugin → Task 4 (`DRIFT_TARGET_KINDS`); agent_plugin verified Task 7. ✓
- §3.5 `gw wiki ack-drift` → Task 6. ✓
- §6 structured-frontmatter setter → Task 1 (`update_frontmatter`); helper reuse (`_split_h2_sections`/`_is_scanner_owned_heading`) → Task 2; `SCANNER_OWNED_KEYS` unchanged → Task 5 guard. ✓
- D3 two preserved keys + judge-once gate → Task 4 (inequality gate, stamp every candidate). ✓
- D4 auto-clear + ack → Task 5 + Task 6. ✓
- D5 flag-only / intra-page → Tasks 4-6 never call `inject_*` on human sections; Task 4 asserts prose untouched. ✓
- §5 tests 1-9: T1→4.1, T2→4.2, T3→4.3, T4→4.2 (same skip path), T5→5.1, T6→6.1, T7→5b, T8→5.2, T9→7.1. ✓

**2. Placeholder scan:** No "TBD"/"add error handling"/"similar to Task N" — every code step shows complete code. The two soft spots are deliberately marked with verify-then-adapt notes, not placeholders: Task 5b (`merge_frontmatter` signature — adapt the *call*, assertion fixed) and Task 6.1b (CLI test harness location — discover the existing harness). Both name exactly what to check and the invariant to assert.

**3. Type consistency:**
- `update_frontmatter(page_path, updates: dict | None = None, *, delete: Iterable[str] = ())` — same call shape in Tasks 4, 5, 6. ✓
- `iter_human_sections(body) -> [(heading, chunk)]`; `section_hash(chunk) -> str`; `extract_file_map(body) -> str | None`; `clear_resolved_flags(entries, body) -> [dict]` — defined Task 2, consumed unchanged in Tasks 4-5. ✓
- `build_drift_judge_prompt(heading, section_body, narrative, file_map) -> (system, human)`; `parse_drift_verdict(text) -> {"stale": bool, "reason": str}` — defined Task 3, consumed Task 4. ✓
- Judge item tuple `(page_path, anchor, heading, chunk, narrative, file_map)` — produced in `_drift_flag_pass`, indexed identically in the test `_verdict` (Task 7) and grouping loop. ✓
- `drift_review` entry shape `{section, detected_commit, hash, reason}` — written Task 4, asserted Tasks 4/5/6/7, hashed/cleared Task 2/5. ✓
- `run_ack_drift(entity, workspace_path) -> AckDriftResult(page_path, cleared)` — defined Task 6, consumed by the CLI + tests. ✓
- Pre-filter is **string inequality** on `drift_checked_commit` vs `last_updated_commit` everywhere (never `<`). ✓

All consistent. No gaps found.

---

## Execution Handoff

**Plan complete and saved to `docs/superpowers/plans/2026-06-04-living-wiki-m2e-human-section-drift-flagging.md`. Two execution options:**

**1. Subagent-Driven (recommended)** — I dispatch a fresh subagent per task, review between tasks, fast iteration.

**2. Inline Execution** — Execute tasks in this session using executing-plans, batch execution with checkpoints.

**Which approach?**
