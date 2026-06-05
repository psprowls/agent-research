# Curated-Page Proposal Ledger Foundation (+ M3 Retrofit) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace M3's per-Source-page `suggested_pages` storage with a single vault-native proposal ledger — one markdown note per proposed curated-page change under `wiki/proposals/` — so both producers (M3 ingest-time, M4 drift-time) write into one machine-readable, human-reviewable queue.

**Architecture:** A new pure-Python module `wiki_io/proposals.py` owns the ledger: identity = filename `<kind>-<target_slug>.md`, frontmatter = machine contract, body = regenerated evidence list. A single `upsert_proposal` lifecycle merge (`proposed → approved/rejected/created`) keyed by filename. M3's `suggest_pages.run_suggest_phase` is retrofitted to call `upsert_proposal` instead of writing the Source page; everything about *deciding* proposals (the extractor pass) is reused unchanged. A thin `gw wiki proposals` / `proposal approve|reject` CLI surface and a lint roll-up round it out. M4's scan-time drift producer (next spec) becomes a second caller of `upsert_proposal` with zero foundation changes.

**Tech Stack:** Python 3.11, `uv` workspace, `python-frontmatter` + `PyYAML` (deterministic `safe_dump(sort_keys=False)`), Typer CLI, pytest. No LLM in the ledger; the extractor LLM is mocked at the `make_llm("extractor")` boundary in tests.

---

## Background an implementer needs

**Workspace ≠ repo.** The wiki vault lives at `<workspace>/wiki/`. `proposals/` is a new dir **inside `wiki/`** (browsable in Obsidian), unlike `work/`/`raw/` which are workspace siblings. The graph DB lives at `<workspace>/.graph-wiki/code.db` (not the repo).

**Run tests scoped per package** (never bare `pytest` from the root):
- `uv run --package wiki-io pytest tests/test_proposals.py -v`
- `uv run --package graph-wiki-core pytest tests/unit/test_suggest_pages.py -v`
- `uv run --package graph-wiki-cli pytest -m "not integration" tests/unit/test_wiki_cli.py -v`

**No migrations** (`.claude/rules/backward-compatibility.md`): the retrofit simply emits `proposals/` notes going forward; the user rebuilds the vault. Do not write migration code for already-landed Source-page `suggested_pages`.

**Determinism discipline (load-bearing for byte-stable no-op re-runs):** serialize via `yaml.safe_dump(rec, sort_keys=False, default_flow_style=False, allow_unicode=True, width=10_000)` over a dict whose keys are placed in a fixed order, then frame as `---\n{yaml}\n---\n{body}` with exactly one trailing newline. This mirrors `wiki_io.entity_writer._render_page_text` and M3's `_ENTRY_KEY_ORDER`.

**Atomic writes:** temp-file + `os.replace` (the `backlink_index.inject_referenced_in_wiki` precedent).

**wiki-io convention:** the module docstring goes **first**, above `from __future__ import annotations`, or `__doc__` is None.

---

## File Structure

**Create:**
- `packages/wiki-io/src/wiki_io/proposals.py` — the ledger: path / read / list / upsert / render / set-status / id-split. Pure functions, no LLM, no graph.
- `packages/wiki-io/tests/test_proposals.py` — ledger lifecycle + D8 non-change guard tests.
- `packages/graph-wiki-core/src/graph_wiki_core/commands/proposals.py` — thin core wrappers (`run_list_proposals`, `run_set_proposal_status`) over `wiki_io.proposals`, resolving the wiki from the workspace.
- `packages/graph-wiki-core/tests/unit/test_commands_proposals.py` — tests for the core wrappers.

**Modify:**
- `packages/wiki-io/src/wiki_io/init_vault.py:43` — add `"proposals"` to `FIXED_VAULT_DIRS`.
- `packages/wiki-io/tests/test_init_vault.py` — assert bootstrap creates `proposals/`.
- `packages/graph-wiki-core/src/graph_wiki_core/commands/suggest_pages.py` — retrofit `run_suggest_phase`; delete the Source-page-storage functions; reuse the extractor-decision functions unchanged.
- `packages/graph-wiki-core/tests/unit/test_suggest_pages.py` — drop deleted-function tests; rewrite `run_suggest_phase` tests to assert `proposals/` notes.
- `packages/graph-wiki-core/src/graph_wiki_core/commands/ingest.py:50,751-758,782-784` — drop the `prior_suggested` capture + import; call the new `run_suggest_phase` signature.
- `packages/graph-wiki-core/tests/unit/test_commands_ingest.py:1253-1421` — rewrite the three M3 tests to assert ledger notes + report-shape preservation.
- `packages/graph-wiki-cli/src/graph_wiki_cli/wiki_cli/main.py` — add `gw wiki proposals` command + `gw wiki proposal approve|reject` sub-app.
- `packages/graph-wiki-cli/tests/unit/test_wiki_cli.py` — CLI tests for the new commands.
- `packages/graph-wiki-core/src/graph_wiki_core/commands/lint.py:83-107,514-554` — add `open_proposals: int` to `LintResult` and populate it.
- `packages/graph-wiki-core/tests/unit/test_commands_lint.py` — assert the open-proposals roll-up.
- `packages/graph-wiki-cli/src/graph_wiki_cli/wiki_cli/main.py` (lint print block ~117) — print the open-proposals count.

---

## Task 1: Bootstrap creates the `proposals/` dir

**Files:**
- Modify: `packages/wiki-io/src/wiki_io/init_vault.py:43-50`
- Test: `packages/wiki-io/tests/test_init_vault.py`

- [ ] **Step 1: Write the failing test**

Add to `packages/wiki-io/tests/test_init_vault.py` (next to `test_entities_in_fixed_vault_dirs`):

```python
def test_proposals_in_fixed_vault_dirs() -> None:
    """The proposal ledger dir must be bootstrapped inside wiki/."""
    from wiki_io.init_vault import FIXED_VAULT_DIRS

    assert "proposals" in FIXED_VAULT_DIRS


def test_init_wiki_creates_proposals_dir(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """gw bootstrap creates wiki/proposals/ (spec §3.8)."""
    from wiki_io import init_vault

    repo = tmp_path / "repo"
    workspace = tmp_path / "ws"
    wiki = workspace / "wiki"
    repo.mkdir()
    (repo / "pyproject.toml").write_text(
        '[project]\nname="solo"\nversion="0.0.1"\n', encoding="utf-8"
    )
    monkeypatch.setattr(init_vault, "_workspace_init", lambda *a, **k: None)

    init_vault.init_wiki(
        wiki, repo, topic="test", tool="claude-code", force=False, non_interactive=True
    )

    assert (wiki / "proposals").is_dir()
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `uv run --package wiki-io pytest tests/test_init_vault.py::test_proposals_in_fixed_vault_dirs tests/test_init_vault.py::test_init_wiki_creates_proposals_dir -v`
Expected: FAIL — `assert 'proposals' in FIXED_VAULT_DIRS` is False; the dir is not created.

- [ ] **Step 3: Add `"proposals"` to `FIXED_VAULT_DIRS`**

In `packages/wiki-io/src/wiki_io/init_vault.py`, change:

```python
FIXED_VAULT_DIRS = [
    "concepts",
    "architecture",
    "adrs",
    "entities",
    "sources",
    "proposals",
    ".templates",
]
```

Do **not** add `"proposals"` to `SECTION_INDEX_STUBS` (just below) — proposals are a transient queue, not an index lane (spec §3.8).

- [ ] **Step 4: Run the tests to verify they pass**

Run: `uv run --package wiki-io pytest tests/test_init_vault.py -v`
Expected: PASS (all init_vault tests, including the two new ones).

- [ ] **Step 5: Commit**

```bash
git add packages/wiki-io/src/wiki_io/init_vault.py packages/wiki-io/tests/test_init_vault.py
git commit -m "feat(proposals): bootstrap wiki/proposals/ dir"
```

---

## Task 2: Ledger identity, parse & body render

Build the read/identity/render half of `wiki_io.proposals` first; `upsert_proposal` (Task 3) and the lister/status-setter (Task 4) build on these.

**Files:**
- Create: `packages/wiki-io/src/wiki_io/proposals.py`
- Test: `packages/wiki-io/tests/test_proposals.py`

- [ ] **Step 1: Write the failing test**

Create `packages/wiki-io/tests/test_proposals.py`:

```python
from __future__ import annotations

"""Unit tests for wiki_io.proposals — the curated-page proposal ledger.
Pure Python, no Bedrock, no graph."""

from pathlib import Path


def _origin(ref="sources/spec", source="ingest", rationale="because.") -> dict:
    return {"ref": ref, "source": source, "rationale": rationale}


def test_proposal_path_is_kind_dash_slug(tmp_path: Path) -> None:
    from wiki_io.proposals import proposal_path

    p = proposal_path(tmp_path / "wiki", "adr", "0007-markdown-canonical")
    assert p == tmp_path / "wiki" / "proposals" / "adr-0007-markdown-canonical.md"


def test_render_body_lists_one_block_per_origin() -> None:
    from wiki_io.proposals import render_proposal_body

    record = {
        "kind": "adr",
        "mode": "update_existing",
        "target_slug": "0007-md",
        "title": "Markdown stays canonical",
        "status": "proposed",
        "origins": [
            _origin(ref="sources/roadmap", rationale="Revisits the decision."),
            {"ref": "entities/pkg_wiki_io", "source": "drift", "rationale": "Async fan-out now."},
        ],
    }
    body = render_proposal_body(record)
    # Comment header references the approve command id.
    assert "approve via `gw wiki proposal approve adr-0007-md`" in body
    # One block per origin: "**<source> · [[<ref>]]**" then the rationale line.
    assert "**ingest · [[sources/roadmap]]**" in body
    assert "Revisits the decision." in body
    assert "**drift · [[entities/pkg_wiki_io]]**" in body
    assert "Async fan-out now." in body


def test_read_proposal_round_trips_a_written_note(tmp_path: Path) -> None:
    from wiki_io.proposals import read_proposal

    note = tmp_path / "concept-section-ownership.md"
    note.write_text(
        "---\n"
        "kind: concept\n"
        "mode: create_new\n"
        "target_slug: section-ownership\n"
        "title: Section Ownership\n"
        "status: proposed\n"
        "origins:\n"
        "- ref: sources/spec\n"
        "  source: ingest\n"
        "  rationale: A reusable split.\n"
        "---\n\nbody\n",
        encoding="utf-8",
    )
    rec = read_proposal(note)
    assert rec["kind"] == "concept"
    assert rec["mode"] == "create_new"
    assert rec["target_slug"] == "section-ownership"
    assert rec["title"] == "Section Ownership"
    assert rec["status"] == "proposed"
    assert rec["origins"] == [
        {"ref": "sources/spec", "source": "ingest", "rationale": "A reusable split."}
    ]


def test_split_proposal_id_parses_kind_prefix() -> None:
    from wiki_io.proposals import split_proposal_id

    assert split_proposal_id("adr-0007-markdown-canonical") == ("adr", "0007-markdown-canonical")
    assert split_proposal_id("concept-section-ownership") == ("concept", "section-ownership")
    assert split_proposal_id("architecture-layers") == ("architecture", "layers")


def test_split_proposal_id_rejects_unknown_kind() -> None:
    import pytest

    from wiki_io.proposals import split_proposal_id

    with pytest.raises(ValueError):
        split_proposal_id("package-foo")
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `uv run --package wiki-io pytest tests/test_proposals.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'wiki_io.proposals'`.

- [ ] **Step 3: Write the module (identity / parse / render half)**

Create `packages/wiki-io/src/wiki_io/proposals.py`:

```python
"""Living Wiki — curated-page proposal ledger (shared foundation).

One markdown note per proposed curated-page change, under `wiki/proposals/`.
Identity is the filename `<kind>-<target_slug>.md`; frontmatter is the machine
contract; the body is regenerated from `origins[]` while `status: proposed`.

Two producers write here via `upsert_proposal`: M3's ingest-time extractor pass
(`source: ingest`) and M4's scan-time drift detector (`source: drift`, next
spec). A human flips `status` to approved/rejected (or via `gw wiki proposal
…`); a deferred creation consumer acts on `approved` notes. Pure Python — no
LLM, no graph.

Public API:
    SUGGESTION_KINDS, HUMAN_DECIDED
    proposal_path(wiki, kind, target_slug) -> Path
    read_proposal(path) -> dict
    list_proposals(wiki, status=None, kind=None) -> list[dict]
    upsert_proposal(wiki, proposal) -> dict
    render_proposal_body(record) -> str
    set_proposal_status(wiki, kind, target_slug, status) -> bool
    split_proposal_id(proposal_id) -> tuple[str, str]
"""

from __future__ import annotations

import os
from pathlib import Path

import frontmatter
import yaml

SUGGESTION_KINDS = frozenset({"concept", "adr", "architecture"})
HUMAN_DECIDED = frozenset({"approved", "rejected", "created"})

# Fixed key order so yaml.safe_dump(..., sort_keys=False) is deterministic.
_RECORD_KEY_ORDER = ("kind", "mode", "target_slug", "title", "status", "origins")
# `detected_commit`/`hash` are M4-reserved (the ingest producer never sets them).
_ORIGIN_KEY_ORDER = ("ref", "source", "rationale", "detected_commit", "hash")


def _ordered_origin(origin: dict) -> dict:
    """Canonical key order for one origin entry; drops absent / None keys."""
    return {k: origin[k] for k in _ORIGIN_KEY_ORDER if k in origin and origin[k] is not None}


def _ordered_record(record: dict) -> dict:
    """Canonical key order for a proposal record, origins included."""
    rec = {k: record[k] for k in _RECORD_KEY_ORDER if k in record}
    rec["origins"] = [_ordered_origin(o) for o in record.get("origins", [])]
    return rec


def proposal_path(wiki: Path, kind: str, target_slug: str) -> Path:
    """Identity → `<wiki>/proposals/<kind>-<target_slug>.md`."""
    return wiki / "proposals" / f"{kind}-{target_slug}.md"


def split_proposal_id(proposal_id: str) -> tuple[str, str]:
    """Split a `<kind>-<target_slug>` id into (kind, target_slug).

    Kinds are distinct prefixes (`concept-`, `adr-`, `architecture-`), so the
    first matching prefix wins. Raises ValueError on an unknown kind.
    """
    for kind in SUGGESTION_KINDS:
        prefix = f"{kind}-"
        if proposal_id.startswith(prefix):
            return kind, proposal_id[len(prefix):]
    raise ValueError(
        f"invalid proposal id {proposal_id!r}: expected <kind>-<target_slug> "
        f"with kind in {sorted(SUGGESTION_KINDS)}"
    )


def render_proposal_body(record: dict) -> str:
    """Render `origins[]` into the human-readable evidence body.

    One block per origin: a `**<source> · [[<ref>]]**` heading line followed by
    the rationale. Regenerated on every upsert while `status: proposed`.
    """
    proposal_id = f"{record['kind']}-{record['target_slug']}"
    comment = (
        "<!-- Body regenerated from origins[] while status: proposed. Do not "
        "edit here;\n"
        f"     approve via `gw wiki proposal approve {proposal_id}`. -->"
    )
    lines = [comment, ""]
    for o in record.get("origins", []):
        lines.append(f"**{o.get('source', '')} · [[{o.get('ref', '')}]]**")
        rationale = (o.get("rationale") or "").strip()
        if rationale:
            lines.append(rationale)
        lines.append("")
    return "\n".join(lines).rstrip("\n")


def read_proposal(path: Path) -> dict:
    """Parse one note into {kind, mode, target_slug, title, status, origins[]}."""
    post = frontmatter.load(path)
    m = post.metadata
    origins = m.get("origins") or []
    return {
        "kind": m.get("kind", ""),
        "mode": m.get("mode", "create_new"),
        "target_slug": m.get("target_slug", path.stem),
        "title": m.get("title", ""),
        "status": m.get("status", "proposed"),
        "origins": [dict(o) for o in origins if isinstance(o, dict)],
    }


def _serialize(record: dict, body: str) -> str:
    """Frame an ordered record + body into the canonical note text.

    Deterministic dump (sort_keys=False over a pre-ordered dict) + exactly one
    trailing newline, mirroring wiki_io.entity_writer._render_page_text.
    """
    rec = _ordered_record(record)
    yaml_block = yaml.safe_dump(
        rec,
        sort_keys=False,
        default_flow_style=False,
        allow_unicode=True,
        width=10_000,
    ).rstrip("\n")
    return f"---\n{yaml_block}\n---\n{body}".rstrip("\n") + "\n"


def _atomic_write(path: Path, text: str) -> None:
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(text, encoding="utf-8")
    os.replace(tmp, path)
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `uv run --package wiki-io pytest tests/test_proposals.py -v`
Expected: PASS (the 5 tests in this task; `upsert_proposal`/`list_proposals`/`set_proposal_status` are added next).

- [ ] **Step 5: Commit**

```bash
git add packages/wiki-io/src/wiki_io/proposals.py packages/wiki-io/tests/test_proposals.py
git commit -m "feat(proposals): ledger identity, parse & body render"
```

---

## Task 3: `upsert_proposal` lifecycle merge

**Files:**
- Modify: `packages/wiki-io/src/wiki_io/proposals.py`
- Test: `packages/wiki-io/tests/test_proposals.py`

- [ ] **Step 1: Write the failing test**

Append to `packages/wiki-io/tests/test_proposals.py`:

```python
def _proposal(kind="concept", mode="create_new", target_slug="a", title="T", origin=None):
    return {
        "kind": kind,
        "mode": mode,
        "target_slug": target_slug,
        "title": title,
        "origin": origin or _origin(),
    }


def test_upsert_creates_note_on_empty_dir(tmp_path: Path) -> None:
    from wiki_io.proposals import proposal_path, read_proposal, upsert_proposal

    wiki = tmp_path / "wiki"  # NOTE: proposals/ does not exist yet
    rec = upsert_proposal(wiki, _proposal(kind="adr", target_slug="0007-md", title="MD"))

    path = proposal_path(wiki, "adr", "0007-md")
    assert path.exists()
    assert rec["status"] == "proposed"
    assert len(rec["origins"]) == 1
    on_disk = read_proposal(path)
    assert on_disk["status"] == "proposed"
    assert on_disk["origins"][0]["ref"] == "sources/spec"
    # Body renders the origin.
    assert "**ingest · [[sources/spec]]**" in path.read_text(encoding="utf-8")


def test_upsert_leaves_human_decided_untouched(tmp_path: Path) -> None:
    from wiki_io.proposals import proposal_path, upsert_proposal

    wiki = tmp_path / "wiki"
    upsert_proposal(wiki, _proposal(target_slug="a", title="Orig"))
    path = proposal_path(wiki, "concept", "a")
    # Human approves by editing status on disk.
    text = path.read_text(encoding="utf-8")
    path.write_text(text.replace("status: proposed", "status: approved"), encoding="utf-8")
    before = path.read_text(encoding="utf-8")

    rec = upsert_proposal(
        wiki, _proposal(target_slug="a", title="NEW", origin=_origin(rationale="new evidence"))
    )

    assert rec["status"] == "approved"
    assert rec["title"] == "Orig"  # not overwritten
    assert path.read_text(encoding="utf-8") == before  # byte-identical: decision never stomped


def test_upsert_rejected_is_preserved_not_reproposed(tmp_path: Path) -> None:
    from wiki_io.proposals import proposal_path, upsert_proposal

    wiki = tmp_path / "wiki"
    upsert_proposal(wiki, _proposal(target_slug="a"))
    path = proposal_path(wiki, "concept", "a")
    path.write_text(
        path.read_text(encoding="utf-8").replace("status: proposed", "status: rejected"),
        encoding="utf-8",
    )
    before = path.read_text(encoding="utf-8")

    rec = upsert_proposal(wiki, _proposal(target_slug="a"))
    assert rec["status"] == "rejected"
    assert path.read_text(encoding="utf-8") == before


def test_upsert_refresh_accumulates_origins_by_ref(tmp_path: Path) -> None:
    from wiki_io.proposals import proposal_path, read_proposal, upsert_proposal

    wiki = tmp_path / "wiki"
    upsert_proposal(wiki, _proposal(target_slug="a", origin=_origin(ref="sources/one")))
    # A NEW ref appends a second origin.
    upsert_proposal(wiki, _proposal(target_slug="a", origin=_origin(ref="sources/two")))
    rec = read_proposal(proposal_path(wiki, "concept", "a"))
    assert [o["ref"] for o in rec["origins"]] == ["sources/one", "sources/two"]

    # The SAME ref re-firing updates in place (no duplicate); status stays proposed.
    upsert_proposal(
        wiki, _proposal(target_slug="a", origin=_origin(ref="sources/two", rationale="changed"))
    )
    rec = read_proposal(proposal_path(wiki, "concept", "a"))
    assert [o["ref"] for o in rec["origins"]] == ["sources/one", "sources/two"]
    assert rec["origins"][1]["rationale"] == "changed"
    assert rec["status"] == "proposed"


def test_upsert_identity_collapse_two_origins_one_note(tmp_path: Path) -> None:
    from wiki_io.proposals import list_proposals, upsert_proposal

    wiki = tmp_path / "wiki"
    upsert_proposal(wiki, _proposal(target_slug="a", origin=_origin(ref="sources/one")))
    upsert_proposal(
        wiki,
        {
            "kind": "concept",
            "mode": "create_new",
            "target_slug": "a",
            "title": "T",
            "origin": {"ref": "entities/pkg_x", "source": "drift", "rationale": "r"},
        },
    )
    records = list_proposals(wiki)
    assert len(records) == 1
    assert len(records[0]["origins"]) == 2


def test_upsert_byte_stable_no_op(tmp_path: Path) -> None:
    from wiki_io.proposals import proposal_path, upsert_proposal

    wiki = tmp_path / "wiki"
    upsert_proposal(wiki, _proposal(target_slug="a"))
    path = proposal_path(wiki, "concept", "a")
    first = path.read_bytes()
    upsert_proposal(wiki, _proposal(target_slug="a"))  # identical evidence
    assert path.read_bytes() == first
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `uv run --package wiki-io pytest tests/test_proposals.py -k upsert -v`
Expected: FAIL — `AttributeError: module 'wiki_io.proposals' has no attribute 'upsert_proposal'` (and `list_proposals`, used by the collapse test, is also not yet defined).

- [ ] **Step 3: Implement `upsert_proposal`**

Append to `packages/wiki-io/src/wiki_io/proposals.py`:

```python
def upsert_proposal(wiki: Path, proposal: dict) -> dict:
    """Lifecycle merge for one proposal (spec §3.2). Returns the merged record.

    `proposal` is producer-supplied:
        {kind, mode, target_slug, title, origin: {ref, source, rationale, ...}}

    - No note exists      → create it `proposed` with origins=[origin].
    - Human status        → left untouched (approved/rejected/created never stomped).
    - status == proposed  → merge origin into origins[] keyed by `ref` (append if
                            new, update in place if the same ref re-fires), refresh
                            title/mode, re-render; status stays proposed.
    Byte-stable on a no-op (writes only when bytes differ). Atomic write.
    """
    kind = proposal["kind"]
    target_slug = proposal["target_slug"]
    origin = _ordered_origin(proposal["origin"])
    path = proposal_path(wiki, kind, target_slug)

    if path.exists():
        record = read_proposal(path)
        if record["status"] in HUMAN_DECIDED:
            return record  # decided: never stomped, no write
        origins = record["origins"]
        ref = origin.get("ref")
        for i, existing in enumerate(origins):
            if existing.get("ref") == ref:
                origins[i] = origin
                break
        else:
            origins.append(origin)
        record["title"] = proposal.get("title", record["title"])
        record["mode"] = proposal.get("mode", record["mode"])
        record["origins"] = origins
    else:
        record = {
            "kind": kind,
            "mode": proposal.get("mode", "create_new"),
            "target_slug": target_slug,
            "title": proposal.get("title", ""),
            "status": "proposed",
            "origins": [origin],
        }

    record = _ordered_record(record)
    text = _serialize(record, render_proposal_body(record))
    path.parent.mkdir(parents=True, exist_ok=True)
    if not path.exists() or path.read_text(encoding="utf-8") != text:
        _atomic_write(path, text)
    return record
```

Note: `list_proposals` is referenced by the identity-collapse test but is implemented in Task 4. To keep this task's tests green now, add the minimal lister here too — but to honor DRY and TDD ordering, instead run only the upsert-specific tests in Step 4 and defer the collapse test. **Simpler:** implement `list_proposals` now (it is a trivial glob) since the collapse test needs it:

```python
def list_proposals(wiki: Path, status: str | None = None, kind: str | None = None) -> list[dict]:
    """Glob `proposals/` into records, optionally filtered by status/kind.

    Sorted by filename. A malformed note is skipped, never fatal.
    """
    d = wiki / "proposals"
    if not d.is_dir():
        return []
    records: list[dict] = []
    for md in sorted(d.glob("*.md")):
        try:
            rec = read_proposal(md)
        except Exception:  # noqa: BLE001 — a malformed note must not abort the list
            continue
        if status is not None and rec["status"] != status:
            continue
        if kind is not None and rec["kind"] != kind:
            continue
        records.append(rec)
    return records
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `uv run --package wiki-io pytest tests/test_proposals.py -v`
Expected: PASS (all Task 2 + Task 3 tests).

- [ ] **Step 5: Commit**

```bash
git add packages/wiki-io/src/wiki_io/proposals.py packages/wiki-io/tests/test_proposals.py
git commit -m "feat(proposals): upsert_proposal lifecycle merge + list_proposals"
```

---

## Task 4: `set_proposal_status` (targeted approve/reject write)

**Files:**
- Modify: `packages/wiki-io/src/wiki_io/proposals.py`
- Test: `packages/wiki-io/tests/test_proposals.py`

- [ ] **Step 1: Write the failing test**

Append to `packages/wiki-io/tests/test_proposals.py`:

```python
def test_set_proposal_status_flips_and_preserves_body(tmp_path: Path) -> None:
    from wiki_io.proposals import proposal_path, read_proposal, set_proposal_status, upsert_proposal

    wiki = tmp_path / "wiki"
    upsert_proposal(wiki, _proposal(target_slug="a", origin=_origin(rationale="keep me")))
    path = proposal_path(wiki, "concept", "a")

    ok = set_proposal_status(wiki, "concept", "a", "approved")
    assert ok is True
    rec = read_proposal(path)
    assert rec["status"] == "approved"
    # The rendered evidence body survives the status flip.
    assert "keep me" in path.read_text(encoding="utf-8")
    # A subsequent upsert (re-ingest) does not revert the decision.
    upsert_proposal(wiki, _proposal(target_slug="a", title="NEW"))
    assert read_proposal(path)["status"] == "approved"


def test_set_proposal_status_returns_false_when_missing(tmp_path: Path) -> None:
    from wiki_io.proposals import set_proposal_status

    assert set_proposal_status(tmp_path / "wiki", "concept", "nope", "approved") is False


def test_set_proposal_status_is_byte_stable(tmp_path: Path) -> None:
    from wiki_io.proposals import proposal_path, set_proposal_status, upsert_proposal

    wiki = tmp_path / "wiki"
    upsert_proposal(wiki, _proposal(target_slug="a"))
    path = proposal_path(wiki, "concept", "a")
    set_proposal_status(wiki, "concept", "a", "approved")
    first = path.read_bytes()
    set_proposal_status(wiki, "concept", "a", "approved")
    assert path.read_bytes() == first
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `uv run --package wiki-io pytest tests/test_proposals.py -k set_proposal_status -v`
Expected: FAIL — `AttributeError: module 'wiki_io.proposals' has no attribute 'set_proposal_status'`.

- [ ] **Step 3: Implement `set_proposal_status`**

Append to `packages/wiki-io/src/wiki_io/proposals.py`:

```python
def set_proposal_status(wiki: Path, kind: str, target_slug: str, status: str) -> bool:
    """Write `status` on one note, preserving the existing rendered body.

    Returns False when the note does not exist (nothing written). Unlike
    `upsert_proposal`, this never regenerates the body — it is the human's
    approve/reject/created write. Re-serializes with the canonical key order so
    the result is byte-stable on a repeat.
    """
    path = proposal_path(wiki, kind, target_slug)
    if not path.exists():
        return False
    record = read_proposal(path)
    record["status"] = status
    body = frontmatter.load(path).content.strip()
    _atomic_write(path, _serialize(record, body))
    return True
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `uv run --package wiki-io pytest tests/test_proposals.py -v`
Expected: PASS (all ledger tests).

- [ ] **Step 5: Commit**

```bash
git add packages/wiki-io/src/wiki_io/proposals.py packages/wiki-io/tests/test_proposals.py
git commit -m "feat(proposals): set_proposal_status targeted approve/reject write"
```

---

## Task 5: D8 non-change guards (index + backlink exclusion)

Lock in the deliberate non-changes so a future implementer does not "helpfully" wire `proposals/` into the index or backlink machinery (spec §3.8).

**Files:**
- Test: `packages/wiki-io/tests/test_proposals.py`

- [ ] **Step 1: Write the failing test**

Append to `packages/wiki-io/tests/test_proposals.py`:

```python
def test_proposals_is_not_a_curated_index_lane() -> None:
    """spec §3.8: proposals/ is a transient queue, not an index lane."""
    from wiki_io.index_generator import CURATED_LANES
    from wiki_io.init_vault import SECTION_INDEX_STUBS
    from wiki_io.update_index import CATEGORY_INDEX_FILES

    assert "proposals" not in {lane[0] for lane in CURATED_LANES}
    assert "proposals" not in {lane[1] for lane in CURATED_LANES}
    assert "proposals" not in SECTION_INDEX_STUBS
    assert "proposals" not in {Path(v).parts[0] for v in CATEGORY_INDEX_FILES.values()}


def test_proposals_is_not_a_backlink_source() -> None:
    """spec §3.8: proposals/ is NOT in _PRESERVED_WIKI_DIRS (no backlinks)."""
    from wiki_io.backlink_index import _PRESERVED_WIKI_DIRS

    assert "proposals" not in _PRESERVED_WIKI_DIRS


def test_proposal_note_generates_no_entity_backlink(tmp_path: Path) -> None:
    """A proposals/ note linking [[entities/...]] must NOT backlink the entity."""
    from wiki_io.backlink_index import regenerate_referenced_in_wiki
    from wiki_io.proposals import upsert_proposal

    wiki = tmp_path / "wiki"
    entities = wiki / "entities"
    entities.mkdir(parents=True)
    (entities / "pkg_x.md").write_text(
        "---\nuri: pkg:o/r/pkg_x\nkind: package\n---\n\n# pkg_x\n\n"
        "## Narrative\nProse.\n\n## Referenced in wiki\n_(scanner will populate)_\n",
        encoding="utf-8",
    )
    # The proposal body carries an entities/ ref (M4-shaped origin).
    upsert_proposal(
        wiki,
        {
            "kind": "adr",
            "mode": "update_existing",
            "target_slug": "0007-md",
            "title": "MD",
            "origin": {"ref": "entities/pkg_x", "source": "drift", "rationale": "r"},
        },
    )
    regenerate_referenced_in_wiki(wiki)
    text = (entities / "pkg_x.md").read_text(encoding="utf-8")
    assert "_No wiki pages reference this entity yet._" in text
    assert "[[adr-0007-md]]" not in text


def test_update_index_ignores_proposals(tmp_path: Path) -> None:
    """update_index writes no proposals sub-index and omits proposal slugs."""
    from wiki_io.proposals import upsert_proposal
    from wiki_io.update_index import update_index

    wiki = tmp_path / "wiki"
    (wiki / "sources").mkdir(parents=True)
    upsert_proposal(tmp_path / "wiki", {  # writes wiki/proposals/concept-xyz.md
        "kind": "concept", "mode": "create_new", "target_slug": "xyz",
        "title": "XYZ", "origin": _origin(),
    })
    update_index(wiki)
    assert not (wiki / "proposals" / "index.md").exists()
    # No category sub-index mentions the proposal slug.
    for sub in wiki.rglob("index.md"):
        assert "concept-xyz" not in sub.read_text(encoding="utf-8")
```

- [ ] **Step 2: Run the tests to verify they pass (guards on existing behavior)**

Run: `uv run --package wiki-io pytest tests/test_proposals.py -k "not_a_curated or not_a_backlink or no_entity_backlink or ignores_proposals" -v`
Expected: PASS immediately — these guard already-correct behavior (`proposals/` is in none of the index/backlink registries). If any **fails**, a non-change was violated; do not "fix" by adding proposals to a registry — investigate the regression.

- [ ] **Step 3: (No implementation — guard task)**

These tests assert deliberate non-changes; there is no code to write. If Step 2 passed, proceed.

- [ ] **Step 4: Run the full ledger suite**

Run: `uv run --package wiki-io pytest tests/test_proposals.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add packages/wiki-io/tests/test_proposals.py
git commit -m "test(proposals): guard D8 index/backlink non-changes"
```

---

## Task 6: M3 retrofit — `run_suggest_phase` writes the ledger

Reuse every *decision* function (`parse_extractor_response`, `_validate_proposal`, `build_curated_vault_index`, `build_extract_suggestions_prompt`, the `extractor` role/prompt) unchanged; delete every *Source-page-storage* function; retarget `run_suggest_phase` to `upsert_proposal`.

**Files:**
- Modify: `packages/graph-wiki-core/src/graph_wiki_core/commands/suggest_pages.py`
- Test: `packages/graph-wiki-core/tests/unit/test_suggest_pages.py`

- [ ] **Step 1: Rewrite the test file's run_suggest_phase + storage sections**

In `packages/graph-wiki-core/tests/unit/test_suggest_pages.py`:

**(a) Delete** these now-obsolete tests (they exercise deleted functions): `test_merge_appends_new_as_proposed`, `test_merge_preserves_human_decided_untouched`, `test_merge_refreshes_matching_proposed_in_place`, `test_merge_preserves_orphaned_proposed`, `test_merge_is_idempotent_on_identical_proposals`, `test_merge_dedups_duplicate_proposals_by_key`, `test_set_and_read_suggested_pages_round_trip`, `test_set_suggested_pages_is_idempotent_and_replaces_block`, `test_set_suggested_pages_empty_removes_key`, `test_read_suggested_pages_no_frontmatter_returns_empty`, `test_render_section_empty_when_no_entries`, `test_render_section_lists_entries_with_status_and_rationale`, `test_set_section_appends_when_absent`, `test_set_section_replaces_existing_and_is_idempotent`, `test_set_section_removes_when_empty_section`, `test_set_section_preserves_trailing_h2`, plus the `_prop` helper (lines 129-137) used only by the deleted merge tests.

**Keep** all `parse_extractor_response` tests and both `build_curated_vault_index` tests (the decision functions are unchanged).

**(b) Replace** the three `run_suggest_phase` tests (`test_run_suggest_phase_writes_proposals_to_page`, `test_run_suggest_phase_llm_error_is_best_effort`, `test_run_suggest_phase_preserves_prior_human_decision`) with:

```python
@pytest.mark.asyncio
async def test_run_suggest_phase_writes_ledger_notes_not_page(tmp_path):
    from unittest.mock import AsyncMock, MagicMock, patch

    from graph_wiki_core.commands.suggest_pages import run_suggest_phase
    from wiki_io.proposals import list_proposals, proposal_path

    wiki = tmp_path / "wiki"
    (wiki / "sources").mkdir(parents=True)
    page = wiki / "sources" / "doc.md"
    page.write_text(
        "---\nsource_kind: source\ntarget_slug: doc\nentity_uri: null\n---\n\nThe doc body.\n",
        encoding="utf-8",
    )
    original = page.read_text(encoding="utf-8")

    llm_yaml = (
        "suggestions:\n"
        "  - kind: concept\n"
        "    title: A Concept\n"
        "    slug: a-concept\n"
        "    mode: create_new\n"
        "    rationale: justified\n"
    )
    fake_llm = MagicMock()
    fake_llm.ainvoke = AsyncMock(return_value=MagicMock(content=llm_yaml))

    with patch("graph_wiki_core.commands.suggest_pages.make_llm", return_value=fake_llm):
        reports, parsed = await run_suggest_phase(wiki=wiki, page_path=page)

    assert parsed is True
    # Report shape preserved (kind/title/slug/mode/status; slug == target_slug).
    assert reports == [
        {
            "kind": "concept",
            "title": "A Concept",
            "slug": "a-concept",
            "mode": "create_new",
            "status": "proposed",
        }
    ]
    # The proposal lives in the ledger, keyed by filename, with an ingest origin.
    note = proposal_path(wiki, "concept", "a-concept")
    assert note.exists()
    rec = list_proposals(wiki)[0]
    assert rec["origins"] == [
        {"ref": "sources/doc", "source": "ingest", "rationale": "justified"}
    ]
    # The Source page is NOT touched — no suggested_pages, no section.
    assert page.read_text(encoding="utf-8") == original
    assert "suggested_pages" not in original
    assert "## Suggested pages" not in original


@pytest.mark.asyncio
async def test_run_suggest_phase_update_existing_targets_existing_slug(tmp_path):
    from unittest.mock import AsyncMock, MagicMock, patch

    from graph_wiki_core.commands.suggest_pages import run_suggest_phase
    from wiki_io.proposals import proposal_path

    wiki = tmp_path / "wiki"
    (wiki / "sources").mkdir(parents=True)
    (wiki / "adrs").mkdir(parents=True)
    page = wiki / "sources" / "doc.md"
    page.write_text("---\ntarget_slug: doc\n---\n\nBody.\n", encoding="utf-8")

    llm_yaml = (
        "suggestions:\n"
        "  - kind: adr\n"
        "    title: Markdown stays canonical\n"
        "    slug: md-idea\n"
        "    mode: update_existing\n"
        "    existing_slug: 0007-md\n"
        "    rationale: revisits the decision\n"
    )
    fake_llm = MagicMock()
    fake_llm.ainvoke = AsyncMock(return_value=MagicMock(content=llm_yaml))

    with patch("graph_wiki_core.commands.suggest_pages.make_llm", return_value=fake_llm):
        reports, parsed = await run_suggest_phase(wiki=wiki, page_path=page)

    # The note is keyed by the EXISTING slug (the update target), not the proposal slug.
    assert proposal_path(wiki, "adr", "0007-md").exists()
    assert reports[0]["slug"] == "0007-md"
    assert reports[0]["mode"] == "update_existing"


@pytest.mark.asyncio
async def test_run_suggest_phase_llm_error_writes_zero_notes(tmp_path):
    from unittest.mock import AsyncMock, MagicMock, patch

    from graph_wiki_core.commands.suggest_pages import run_suggest_phase

    wiki = tmp_path / "wiki"
    (wiki / "sources").mkdir(parents=True)
    page = wiki / "sources" / "doc.md"
    page.write_text("---\ntarget_slug: doc\n---\n\nBody.\n", encoding="utf-8")

    fake_llm = MagicMock()
    fake_llm.ainvoke = AsyncMock(side_effect=RuntimeError("bedrock boom"))

    with patch("graph_wiki_core.commands.suggest_pages.make_llm", return_value=fake_llm):
        reports, parsed = await run_suggest_phase(wiki=wiki, page_path=page)

    assert reports == []
    assert parsed is False
    # No notes written; the dir may not even exist.
    assert not list((wiki / "proposals").glob("*.md")) if (wiki / "proposals").is_dir() else True


@pytest.mark.asyncio
async def test_run_suggest_phase_parse_miss_writes_zero_notes(tmp_path):
    from unittest.mock import AsyncMock, MagicMock, patch

    from graph_wiki_core.commands.suggest_pages import run_suggest_phase

    wiki = tmp_path / "wiki"
    (wiki / "sources").mkdir(parents=True)
    page = wiki / "sources" / "doc.md"
    page.write_text("---\ntarget_slug: doc\n---\n\nBody.\n", encoding="utf-8")

    fake_llm = MagicMock()
    fake_llm.ainvoke = AsyncMock(return_value=MagicMock(content="not valid yaml: : ["))

    with patch("graph_wiki_core.commands.suggest_pages.make_llm", return_value=fake_llm):
        reports, parsed = await run_suggest_phase(wiki=wiki, page_path=page)

    assert reports == []
    assert parsed is False
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `uv run --package graph-wiki-core pytest tests/unit/test_suggest_pages.py -v`
Expected: FAIL — the new tests reference the old behavior (the current `run_suggest_phase` still writes the page / takes `prior_entries`); the deleted tests' imports (`merge_suggested_pages`, etc.) are gone so collection may also error if any deleted test remained. Ensure the deletions in Step 1(a) are complete so only the rewritten tests run.

- [ ] **Step 3: Retrofit `suggest_pages.py`**

In `packages/graph-wiki-core/src/graph_wiki_core/commands/suggest_pages.py`:

**(a)** Replace the module docstring's Public-API block (lines 3-21) with:

```python
"""Living Wiki M3 — inline page-suggestion pass for run_ingest_source.

After a Source page lands, propose which concept/adr/architecture pages the
document justifies and record each as a note in the proposal ledger
(`wiki/proposals/<kind>-<target_slug>.md`) via wiki_io.proposals.upsert_proposal.
Propose only — nothing is written under concepts/ / adrs/ / architecture/, and
the Source page is no longer mutated.

Public API:
    SUGGESTION_KINDS, HUMAN_DECIDED, EXTRACT_PREVIEW_CHARS
    parse_extractor_response(text) -> (list[dict], bool)
    build_curated_vault_index(wiki) -> list[dict]
    build_extract_suggestions_prompt(source_text, vault_index) -> str
    run_suggest_phase(*, wiki, page_path) -> (list[dict], bool)
"""
```

**(b)** Update imports near the top — add the ledger import, drop the now-unused `parse_frontmatter` only if nothing else uses it (it is used by `build_curated_vault_index`, so **keep** it). Add:

```python
from wiki_io.proposals import upsert_proposal
```

**(c) Delete** these functions and constants entirely (Source-page storage): `merge_suggested_pages`, `_split_frontmatter`, `read_suggested_pages`, `set_suggested_pages_in_frontmatter`, `render_suggested_pages_section`, `set_suggested_pages_section_in_body`, and the module constants `_SECTION_HEADING` and `_SECTION_NOTE`.

**Keep:** `SUGGESTION_KINDS`, `HUMAN_DECIDED`, `EXTRACT_PREVIEW_CHARS`, `_ENTRY_KEY_ORDER`, `_ordered_entry`, `_validate_proposal`, `parse_extractor_response`, `_CURATED_DIRS`, `build_curated_vault_index`, `build_extract_suggestions_prompt`. (`_ENTRY_KEY_ORDER`/`_ordered_entry` are still used by `_validate_proposal`.)

**(d)** Replace `run_suggest_phase` (the whole function, lines 366-423) with:

```python
async def run_suggest_phase(
    *,
    wiki: Path,
    page_path: Path,
) -> tuple[list[dict], bool]:
    """Inline suggest phase: propose derived pages into the proposal ledger.

    For each validated extractor proposal, upsert a `proposals/` note keyed by
    `<kind>-<target_slug>` (the existing_slug when mode=update_existing, else the
    proposed slug), with an `ingest` origin pointing at this Source page. The
    ledger owns the per-note merge (human decisions survive re-ingest because a
    decided note is left untouched), so no prior-state capture is needed.

    Best-effort (spec §3.5): on an extractor error or parse miss, write ZERO
    notes and return ([], False). The suggest phase never fails an ingest.

    Returns (reports, parsed) where each report is a dict shaped
    {kind, title, slug, mode, status} (slug == target_slug) — the report shape
    the CLI/MCP already consume (spec §3.6).
    """
    page_text = page_path.read_text(encoding="utf-8")
    vault_index = build_curated_vault_index(wiki)
    prompt = build_extract_suggestions_prompt(page_text, vault_index)

    try:
        llm = make_llm("extractor")
        resp = await llm.ainvoke([SystemMessage(EXTRACTOR_SYSTEM), HumanMessage(prompt)])
    except Exception:
        logger.warning("extractor LLM call failed; skipping suggestions", exc_info=True)
        return [], False

    proposals, parsed = parse_extractor_response(resp.content)
    if not parsed:
        return [], False

    source_ref = f"sources/{page_path.stem}"
    reports: list[dict] = []
    for p in proposals:
        if p["mode"] == "update_existing" and p.get("existing_slug"):
            target_slug = p["existing_slug"]
        else:
            target_slug = p["slug"]
        record = upsert_proposal(
            wiki,
            {
                "kind": p["kind"],
                "mode": p["mode"],
                "target_slug": target_slug,
                "title": p["title"],
                "origin": {
                    "ref": source_ref,
                    "source": "ingest",
                    "rationale": p.get("rationale", ""),
                },
            },
        )
        reports.append(
            {
                "kind": record["kind"],
                "title": record["title"],
                "slug": record["target_slug"],
                "mode": record["mode"],
                "status": record["status"],
            }
        )
    return reports, True
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `uv run --package graph-wiki-core pytest tests/unit/test_suggest_pages.py -v`
Expected: PASS (parse + index tests + the 4 rewritten run_suggest_phase tests).

- [ ] **Step 5: Commit**

```bash
git add packages/graph-wiki-core/src/graph_wiki_core/commands/suggest_pages.py packages/graph-wiki-core/tests/unit/test_suggest_pages.py
git commit -m "feat(suggest): retrofit run_suggest_phase to write the proposal ledger"
```

---

## Task 7: ingest.py wiring + IngestResult report-shape preservation

Drop the `prior_suggested` capture (the per-note merge now lives in the ledger, keyed by filename — nothing to capture-before-overwrite). `IngestResult.suggested_pages` / `suggestions_parsed` stay as the reporting fields (spec §3.6), now sourced from the upserted records.

**Files:**
- Modify: `packages/graph-wiki-core/src/graph_wiki_core/commands/ingest.py:50,751-758,781-784`
- Test: `packages/graph-wiki-core/tests/unit/test_commands_ingest.py:1253-1421`

- [ ] **Step 1: Rewrite the three M3 ingest tests**

In `packages/graph-wiki-core/tests/unit/test_commands_ingest.py`, replace the block from `test_run_ingest_source_attaches_suggestions` through `test_run_ingest_source_reingest_preserves_human_decision` (lines 1257-1421) with:

```python
@pytest.mark.asyncio
async def test_run_ingest_source_writes_ledger_notes(tmp_path: Path) -> None:
    """A clean ingest records proposals in proposals/ + in IngestResult; the
    Source page carries no suggested_pages and no ## Suggested pages section."""
    from graph_wiki_core.commands.ingest import run_ingest_source
    from wiki_io.proposals import proposal_path

    workspace, wiki, repo = _build_workspace_with_repo(tmp_path)
    source_file = workspace / "spec.md"
    source_file.write_text("# Spec\n\nA cross-cutting idea.", encoding="utf-8")
    _seed_graph_db_for_ingest_tests(workspace, packages=[])

    ingestor_response = (
        "---\nsource_kind: source\ntarget_slug: spec\ntitle: Spec\nsummary: x\n---\nBody."
    )
    extractor_response = (
        "suggestions:\n"
        "  - kind: concept\n"
        "    title: Cross Cutting Idea\n"
        "    slug: cross-cutting-idea\n"
        "    mode: create_new\n"
        "    rationale: The source defines it.\n"
    )

    ingestor_llm = MagicMock()
    ingestor_llm.ainvoke = AsyncMock(return_value=MagicMock(content=ingestor_response))
    extractor_llm = MagicMock()
    extractor_llm.ainvoke = AsyncMock(return_value=MagicMock(content=extractor_response))

    with (
        patch("graph_wiki_core.commands.ingest.resolve_wiki_and_repo") as mock_resolve,
        patch("graph_wiki_core.commands.ingest.make_llm", return_value=ingestor_llm),
        patch("graph_wiki_core.commands.suggest_pages.make_llm", return_value=extractor_llm),
        patch("graph_wiki_core.commands.ingest.update_index"),
        patch("graph_wiki_core.commands.ingest.append_log"),
    ):
        mock_resolve.return_value = (wiki, repo)
        result = await run_ingest_source(source_file, workspace)

    # Report shape preserved (kind/title/slug/mode/status).
    assert result.suggestions_parsed is True
    assert [(s["kind"], s["slug"], s["status"]) for s in result.suggested_pages] == [
        ("concept", "cross-cutting-idea", "proposed")
    ]
    assert set(result.suggested_pages[0]) == {"kind", "title", "slug", "mode", "status"}
    # Storage moved to the ledger.
    assert proposal_path(wiki, "concept", "cross-cutting-idea").exists()
    # The Source page is clean.
    written = (wiki / "sources" / "spec.md").read_text(encoding="utf-8")
    assert "suggested_pages" not in written
    assert "## Suggested pages" not in written


@pytest.mark.asyncio
async def test_run_ingest_source_suggest_degraded_is_nonfatal(tmp_path: Path) -> None:
    """Extractor parse miss -> suggestions_parsed False, ingest still ok, zero notes."""
    from graph_wiki_core.commands.ingest import run_ingest_source

    workspace, wiki, repo = _build_workspace_with_repo(tmp_path)
    source_file = workspace / "spec.md"
    source_file.write_text("# Spec\n\nBody.", encoding="utf-8")
    _seed_graph_db_for_ingest_tests(workspace, packages=[])

    ingestor_response = "---\nsource_kind: source\ntarget_slug: spec\ntitle: Spec\n---\nBody."
    extractor_response = "this is not valid yaml: : ["

    ingestor_llm = MagicMock()
    ingestor_llm.ainvoke = AsyncMock(return_value=MagicMock(content=ingestor_response))
    extractor_llm = MagicMock()
    extractor_llm.ainvoke = AsyncMock(return_value=MagicMock(content=extractor_response))

    with (
        patch("graph_wiki_core.commands.ingest.resolve_wiki_and_repo") as mock_resolve,
        patch("graph_wiki_core.commands.ingest.make_llm", return_value=ingestor_llm),
        patch("graph_wiki_core.commands.suggest_pages.make_llm", return_value=extractor_llm),
        patch("graph_wiki_core.commands.ingest.update_index"),
        patch("graph_wiki_core.commands.ingest.append_log"),
    ):
        mock_resolve.return_value = (wiki, repo)
        result = await run_ingest_source(source_file, workspace)

    assert result.status == "ok"
    assert result.suggestions_parsed is False
    assert result.suggested_pages == []
    assert not list((wiki / "proposals").glob("*.md")) if (wiki / "proposals").is_dir() else True


@pytest.mark.asyncio
async def test_run_ingest_source_reingest_preserves_human_decision(tmp_path: Path) -> None:
    """A human's approved decision in the ledger survives re-ingest (spec §3.2).

    The note's status is human-decided, so upsert leaves it untouched on the
    second ingest — no prior-state capture in ingest.py is required.
    """
    from graph_wiki_core.commands.ingest import run_ingest_source
    from wiki_io.proposals import proposal_path, read_proposal, set_proposal_status

    workspace, wiki, repo = _build_workspace_with_repo(tmp_path)
    source_file = workspace / "spec.md"
    source_file.write_text("# Spec\n\nA cross-cutting idea.", encoding="utf-8")
    _seed_graph_db_for_ingest_tests(workspace, packages=[])

    ingestor_response = (
        "---\nsource_kind: source\ntarget_slug: spec\ntitle: Spec\nsummary: x\n---\nBody."
    )
    extractor_response = (
        "suggestions:\n"
        "  - kind: concept\n"
        "    title: Cross Cutting Idea\n"
        "    slug: cross-cutting-idea\n"
        "    mode: create_new\n"
        "    rationale: The source defines it.\n"
    )

    def _llms():
        i = MagicMock()
        i.ainvoke = AsyncMock(return_value=MagicMock(content=ingestor_response))
        e = MagicMock()
        e.ainvoke = AsyncMock(return_value=MagicMock(content=extractor_response))
        return i, e

    ingestor_llm, extractor_llm = _llms()
    with (
        patch("graph_wiki_core.commands.ingest.resolve_wiki_and_repo", return_value=(wiki, repo)),
        patch("graph_wiki_core.commands.ingest.make_llm", return_value=ingestor_llm),
        patch("graph_wiki_core.commands.suggest_pages.make_llm", return_value=extractor_llm),
        patch("graph_wiki_core.commands.ingest.update_index"),
        patch("graph_wiki_core.commands.ingest.append_log"),
    ):
        first = await run_ingest_source(source_file, workspace)

    assert [(s["slug"], s["status"]) for s in first.suggested_pages] == [
        ("cross-cutting-idea", "proposed")
    ]

    # Human approves via the ledger API.
    set_proposal_status(wiki, "concept", "cross-cutting-idea", "approved")

    ingestor_llm2, extractor_llm2 = _llms()
    with (
        patch("graph_wiki_core.commands.ingest.resolve_wiki_and_repo", return_value=(wiki, repo)),
        patch("graph_wiki_core.commands.ingest.make_llm", return_value=ingestor_llm2),
        patch("graph_wiki_core.commands.suggest_pages.make_llm", return_value=extractor_llm2),
        patch("graph_wiki_core.commands.ingest.update_index"),
        patch("graph_wiki_core.commands.ingest.append_log"),
    ):
        second = await run_ingest_source(source_file, workspace)

    kept = [s for s in second.suggested_pages if s["slug"] == "cross-cutting-idea"]
    assert len(kept) == 1
    assert kept[0]["status"] == "approved"  # decision preserved by the ledger
    on_disk = read_proposal(proposal_path(wiki, "concept", "cross-cutting-idea"))
    assert on_disk["status"] == "approved"
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `uv run --package graph-wiki-core pytest tests/unit/test_commands_ingest.py -k "ledger_notes or suggest_degraded or reingest_preserves" -v`
Expected: FAIL — `run_ingest_source` still captures `prior_suggested` and calls `run_suggest_phase(..., prior_entries=...)`, which no longer accepts that kwarg → `TypeError`.

- [ ] **Step 3: Update ingest.py**

In `packages/graph-wiki-core/src/graph_wiki_core/commands/ingest.py`:

**(a)** Change the import on line 50 from:

```python
from graph_wiki_core.commands.suggest_pages import read_suggested_pages, run_suggest_phase
```

to:

```python
from graph_wiki_core.commands.suggest_pages import run_suggest_phase
```

**(b)** Delete the `prior_suggested` capture block (lines 751-758):

```python
        # Living Wiki M3: capture the page's prior suggested_pages (human
        # decisions) BEFORE the ingestor output overwrites the page, so the
        # suggest phase can preserve approved/rejected across re-ingest (§3.4).
        prior_suggested = (
            read_suggested_pages(target_path.read_text(encoding="utf-8"))
            if target_path.exists()
            else []
        )
```

**(c)** Change the suggest-phase call (lines 782-784) from:

```python
            suggested_pages, suggestions_parsed = await run_suggest_phase(
                wiki=wiki, page_path=target_path, prior_entries=prior_suggested
            )
```

to:

```python
            suggested_pages, suggestions_parsed = await run_suggest_phase(
                wiki=wiki, page_path=target_path
            )
```

Leave the surrounding `try/except` (best-effort wrapper) and the `IngestResult(... suggested_pages=..., suggestions_parsed=...)` construction unchanged — the report fields and their dataclass definition do not change (spec §3.6).

- [ ] **Step 4: Run the tests to verify they pass**

Run: `uv run --package graph-wiki-core pytest tests/unit/test_commands_ingest.py -v`
Expected: PASS (the 3 rewritten M3 tests + all pre-existing ingest tests; the autouse `_stub_extractor_llm` keeps the rest off Bedrock).

- [ ] **Step 5: Commit**

```bash
git add packages/graph-wiki-core/src/graph_wiki_core/commands/ingest.py packages/graph-wiki-core/tests/unit/test_commands_ingest.py
git commit -m "feat(ingest): source suggest phase writes the ledger; drop prior-state capture"
```

---

## Task 8: CLI surface — `gw wiki proposals` + `proposal approve|reject`

Add a core command module (the codebase convention: CLI is presentation-only, delegating to `graph_wiki_core.commands.*`), then the Typer surface.

**Files:**
- Create: `packages/graph-wiki-core/src/graph_wiki_core/commands/proposals.py`
- Test: `packages/graph-wiki-core/tests/unit/test_commands_proposals.py`
- Modify: `packages/graph-wiki-cli/src/graph_wiki_cli/wiki_cli/main.py`
- Test: `packages/graph-wiki-cli/tests/unit/test_wiki_cli.py`

- [ ] **Step 1: Write the failing core-command test**

Create `packages/graph-wiki-core/tests/unit/test_commands_proposals.py`:

```python
from __future__ import annotations

from pathlib import Path

import pytest


def _seed(wiki: Path):
    from wiki_io.proposals import upsert_proposal

    upsert_proposal(wiki, {
        "kind": "concept", "mode": "create_new", "target_slug": "a", "title": "A",
        "origin": {"ref": "sources/spec", "source": "ingest", "rationale": "r"},
    })
    upsert_proposal(wiki, {
        "kind": "adr", "mode": "update_existing", "target_slug": "0007-md", "title": "MD",
        "origin": {"ref": "sources/spec", "source": "ingest", "rationale": "r2"},
    })


def test_run_list_proposals_defaults_to_proposed(tmp_path: Path) -> None:
    from unittest.mock import patch

    from graph_wiki_core.commands.proposals import run_list_proposals

    wiki = tmp_path / "wiki"
    _seed(wiki)
    with patch(
        "graph_wiki_core.commands.proposals.resolve_wiki_and_repo", return_value=(wiki, None)
    ):
        records = run_list_proposals(workspace_path=tmp_path)
    assert {r["target_slug"] for r in records} == {"a", "0007-md"}
    # kind filter narrows.
    with patch(
        "graph_wiki_core.commands.proposals.resolve_wiki_and_repo", return_value=(wiki, None)
    ):
        adrs = run_list_proposals(workspace_path=tmp_path, kind="adr")
    assert [r["target_slug"] for r in adrs] == ["0007-md"]


def test_run_set_proposal_status_flips_and_reports(tmp_path: Path) -> None:
    from unittest.mock import patch

    from graph_wiki_core.commands.proposals import run_set_proposal_status
    from wiki_io.proposals import proposal_path, read_proposal

    wiki = tmp_path / "wiki"
    _seed(wiki)
    with patch(
        "graph_wiki_core.commands.proposals.resolve_wiki_and_repo", return_value=(wiki, None)
    ):
        decision = run_set_proposal_status("adr-0007-md", "approved", workspace_path=tmp_path)
    assert decision.proposal_id == "adr-0007-md"
    assert decision.status == "approved"
    assert read_proposal(proposal_path(wiki, "adr", "0007-md"))["status"] == "approved"


def test_run_set_proposal_status_unknown_raises(tmp_path: Path) -> None:
    from unittest.mock import patch

    from graph_wiki_core.commands.proposals import run_set_proposal_status

    wiki = tmp_path / "wiki"
    _seed(wiki)
    with patch(
        "graph_wiki_core.commands.proposals.resolve_wiki_and_repo", return_value=(wiki, None)
    ):
        with pytest.raises(ValueError):
            run_set_proposal_status("concept-nope", "approved", workspace_path=tmp_path)
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `uv run --package graph-wiki-core pytest tests/unit/test_commands_proposals.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'graph_wiki_core.commands.proposals'`.

- [ ] **Step 3: Write the core command module**

Create `packages/graph-wiki-core/src/graph_wiki_core/commands/proposals.py`:

```python
"""Living Wiki — `gw wiki proposals` / `gw wiki proposal approve|reject` bodies.

Thin core wrappers over wiki_io.proposals: resolve the wiki from the workspace,
then list or flip the status of ledger notes. No LLM. The CLI owns presentation.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from wiki_io._workspace import resolve_wiki_and_repo
from wiki_io.proposals import list_proposals, set_proposal_status, split_proposal_id


@dataclass
class ProposalDecision:
    proposal_id: str
    status: str


def run_list_proposals(
    workspace_path: Path | None = None,
    status: str | None = "proposed",
    kind: str | None = None,
) -> list[dict]:
    """List ledger records, default-filtered to open (`proposed`)."""
    wiki, _repo = resolve_wiki_and_repo(workspace_path)
    return list_proposals(wiki, status=status, kind=kind)


def run_set_proposal_status(
    proposal_id: str,
    status: str,
    workspace_path: Path | None = None,
) -> ProposalDecision:
    """Flip one note's status (approve/reject). Raises ValueError on no match."""
    wiki, _repo = resolve_wiki_and_repo(workspace_path)
    kind, target_slug = split_proposal_id(proposal_id)
    if not set_proposal_status(wiki, kind, target_slug, status):
        raise ValueError(f"no proposal note found for {proposal_id!r}")
    return ProposalDecision(proposal_id=proposal_id, status=status)
```

- [ ] **Step 4: Run the core test to verify it passes**

Run: `uv run --package graph-wiki-core pytest tests/unit/test_commands_proposals.py -v`
Expected: PASS.

- [ ] **Step 5: Write the failing CLI test**

Append to `packages/graph-wiki-cli/tests/unit/test_wiki_cli.py`:

```python
def test_proposals_and_proposal_subcommands_registered() -> None:
    """`gw wiki proposals` (list) and `gw wiki proposal approve|reject` exist."""
    from graph_wiki_cli.cli import app

    root_command = typer.main.get_command(app)
    wiki_group = root_command.commands["wiki"]
    assert "proposals" in wiki_group.commands
    proposal_group = wiki_group.commands["proposal"]
    assert set(proposal_group.commands) >= {"approve", "reject"}


def test_proposals_list_prints_open_records(tmp_path: Path) -> None:
    from graph_wiki_cli.cli import app

    records = [
        {"kind": "concept", "mode": "create_new", "target_slug": "a", "title": "A",
         "status": "proposed", "origins": [{"ref": "sources/s", "source": "ingest"}]},
    ]
    with patch("graph_wiki_cli.wiki_cli.main.run_list_proposals", return_value=records) as mock_fn:
        result = runner.invoke(app, ["wiki", "proposals", "--workspace", str(tmp_path)])

    assert result.exit_code == 0, result.output
    assert "concept-a" in result.output
    assert "proposed" in result.output
    mock_fn.assert_called_once_with(workspace_path=tmp_path, status="proposed", kind=None)


def test_proposal_approve_flips_and_exits_zero(tmp_path: Path) -> None:
    from graph_wiki_cli.cli import app
    from graph_wiki_core.commands.proposals import ProposalDecision

    fake = ProposalDecision(proposal_id="adr-0007-md", status="approved")
    with patch("graph_wiki_cli.wiki_cli.main.run_set_proposal_status", return_value=fake) as mock_fn:
        result = runner.invoke(
            app, ["wiki", "proposal", "approve", "adr-0007-md", "--workspace", str(tmp_path)]
        )

    assert result.exit_code == 0, result.output
    assert "approved" in result.output
    mock_fn.assert_called_once_with("adr-0007-md", "approved", workspace_path=tmp_path)


def test_proposal_reject_unknown_exits_nonzero() -> None:
    from graph_wiki_cli.cli import app

    with patch(
        "graph_wiki_cli.wiki_cli.main.run_set_proposal_status",
        side_effect=ValueError("no proposal note found for 'concept-nope'"),
    ):
        result = runner.invoke(app, ["wiki", "proposal", "reject", "concept-nope"])

    assert result.exit_code == 1
    assert "no proposal note found" in result.output
```

- [ ] **Step 6: Run the CLI test to verify it fails**

Run: `uv run --package graph-wiki-cli pytest -m "not integration" tests/unit/test_wiki_cli.py -k "proposal" -v`
Expected: FAIL — the commands are not registered; the import of `run_list_proposals` / `run_set_proposal_status` into `wiki_cli.main` does not exist yet.

- [ ] **Step 7: Add the CLI commands**

In `packages/graph-wiki-cli/src/graph_wiki_cli/wiki_cli/main.py`:

**(a)** Add to the core-command imports (near line 21-29):

```python
from graph_wiki_core.commands.proposals import run_list_proposals, run_set_proposal_status
```

**(b)** Add the commands (place after the `ack_drift` command, before the ingest sub-app at line ~186):

```python
@wiki_app.command(name="proposals")
def proposals(
    status: str = typer.Option(
        "proposed",
        "--status",
        help="proposed|approved|rejected|created|all (default: proposed)",
    ),
    kind: Optional[str] = typer.Option(
        None, "--kind", help="concept|adr|architecture (default: all kinds)"
    ),
    workspace: str = typer.Option(
        "", "--workspace", help="Workspace path (default: GRAPH_WIKI_WORKSPACE env var)"
    ),
    json_output: bool = typer.Option(False, "--json", help="Emit records as JSON"),
) -> None:
    """List curated-page proposals from the ledger (defaults to open ones)."""
    workspace_path = Path(workspace) if workspace else None
    status_filter = None if status == "all" else status
    try:
        records = run_list_proposals(
            workspace_path=workspace_path, status=status_filter, kind=kind
        )
    except (RuntimeError, ValueError) as e:
        typer.echo(f"Error: {e}", err=True)
        raise typer.Exit(code=1)

    if json_output:
        typer.echo(json.dumps(records, indent=2))
        return
    if not records:
        typer.echo("No proposals.")
        return
    for r in records:
        proposal_id = f"{r['kind']}-{r['target_slug']}"
        typer.echo(
            f"{proposal_id}  [{r['status']}]  mode={r['mode']}  "
            f"origins={len(r['origins'])}  — {r['title']}"
        )


proposal_app = typer.Typer(help="Approve or reject a curated-page proposal.")
wiki_app.add_typer(proposal_app, name="proposal")


def _decide(proposal_id: str, status: str, workspace: str, json_output: bool) -> None:
    workspace_path = Path(workspace) if workspace else None
    try:
        decision = run_set_proposal_status(proposal_id, status, workspace_path=workspace_path)
    except (RuntimeError, ValueError) as e:
        typer.echo(f"Error: {e}", err=True)
        raise typer.Exit(code=1)
    if json_output:
        typer.echo(json.dumps(dataclasses.asdict(decision), indent=2))
    else:
        typer.echo(f"[ok] {decision.proposal_id} -> {decision.status}")


@proposal_app.command(name="approve")
def proposal_approve(
    proposal_id: str = typer.Argument(..., help="<kind>-<target_slug>, e.g. adr-0007-md"),
    workspace: str = typer.Option("", "--workspace", help="Workspace path"),
    json_output: bool = typer.Option(False, "--json", help="Emit the decision as JSON"),
) -> None:
    """Approve a proposal (flip its status to `approved`)."""
    _decide(proposal_id, "approved", workspace, json_output)


@proposal_app.command(name="reject")
def proposal_reject(
    proposal_id: str = typer.Argument(..., help="<kind>-<target_slug>, e.g. adr-0007-md"),
    workspace: str = typer.Option("", "--workspace", help="Workspace path"),
    json_output: bool = typer.Option(False, "--json", help="Emit the decision as JSON"),
) -> None:
    """Reject a proposal (flip its status to `rejected`, preserved so it is not re-proposed)."""
    _decide(proposal_id, "rejected", workspace, json_output)
```

(`dataclasses` and `json` are already imported at the top of this module.)

- [ ] **Step 8: Run the CLI tests to verify they pass**

Run: `uv run --package graph-wiki-cli pytest -m "not integration" tests/unit/test_wiki_cli.py -v`
Expected: PASS (the 4 new proposal tests + all pre-existing wiki-cli tests).

- [ ] **Step 9: Commit**

```bash
git add packages/graph-wiki-core/src/graph_wiki_core/commands/proposals.py \
        packages/graph-wiki-core/tests/unit/test_commands_proposals.py \
        packages/graph-wiki-cli/src/graph_wiki_cli/wiki_cli/main.py \
        packages/graph-wiki-cli/tests/unit/test_wiki_cli.py
git commit -m "feat(cli): gw wiki proposals + proposal approve|reject"
```

---

## Task 9: Lint roll-up — count of open proposals

**Files:**
- Modify: `packages/graph-wiki-core/src/graph_wiki_core/commands/lint.py:83-107,514-554`
- Test: `packages/graph-wiki-core/tests/unit/test_commands_lint.py`
- Modify: `packages/graph-wiki-cli/src/graph_wiki_cli/wiki_cli/main.py` (lint print block ~117)

- [ ] **Step 1: Write the failing test**

Append to `packages/graph-wiki-core/tests/unit/test_commands_lint.py`:

```python
@pytest.mark.asyncio
async def test_run_lint_reports_open_proposals_count(tmp_path: Path) -> None:
    """LintResult.open_proposals counts notes at status: proposed (spec §3.7)."""
    from graph_wiki_core.commands.lint import run_lint
    from subagent_runtime.pool import FanOutResult
    from wiki_io.proposals import set_proposal_status, upsert_proposal

    wiki = tmp_path / "wiki"
    wiki.mkdir()
    (wiki / "CLAUDE.md").write_text(
        "# wiki\n\n```yaml\nversion: 1\ncontainers: []\n```\n", encoding="utf-8"
    )
    (wiki / "index.md").write_text("# Index\n", encoding="utf-8")

    # Two proposed + one approved → open count is 2.
    upsert_proposal(wiki, {
        "kind": "concept", "mode": "create_new", "target_slug": "a", "title": "A",
        "origin": {"ref": "sources/s", "source": "ingest", "rationale": "r"},
    })
    upsert_proposal(wiki, {
        "kind": "adr", "mode": "create_new", "target_slug": "b", "title": "B",
        "origin": {"ref": "sources/s", "source": "ingest", "rationale": "r"},
    })
    upsert_proposal(wiki, {
        "kind": "concept", "mode": "create_new", "target_slug": "c", "title": "C",
        "origin": {"ref": "sources/s", "source": "ingest", "rationale": "r"},
    })
    set_proposal_status(wiki, "concept", "c", "approved")

    with patch("graph_wiki_core.commands.lint.SubagentPool") as MockPool:
        mock_pool = MagicMock()
        MockPool.return_value = mock_pool
        mock_pool.run_all = AsyncMock(return_value=FanOutResult(successes=[], errors=[]))
        result = await run_lint(workspace_path=wiki)

    assert result.open_proposals == 2


def test_lint_result_has_open_proposals_field() -> None:
    from graph_wiki_core.commands.lint import LintResult

    fields = {f.name for f in __import__("dataclasses").fields(LintResult)}
    assert "open_proposals" in fields
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `uv run --package graph-wiki-core pytest tests/unit/test_commands_lint.py -k "open_proposals" -v`
Expected: FAIL — `LintResult` has no `open_proposals` field; `result.open_proposals` raises `AttributeError`.

- [ ] **Step 3: Add the field and populate it**

In `packages/graph-wiki-core/src/graph_wiki_core/commands/lint.py`:

**(a)** Add the import near the other `wiki_io` imports at the top of the file:

```python
from wiki_io.proposals import list_proposals
```

**(b)** Add the field to `LintResult` (after `errors`, line ~107):

```python
    open_proposals: int = 0
```

**(c)** In `run_lint`, after `wiki, repo = resolve_wiki_and_repo(workspace_path)` (line 516), compute the count:

```python
    open_proposals = len(list_proposals(wiki, status="proposed"))
```

**(d)** Pass it into the `LintResult(...)` constructor (line ~536), e.g. as the last argument:

```python
        semantic_findings=semantic_findings,
        errors=errors,
        open_proposals=open_proposals,
    )
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `uv run --package graph-wiki-core pytest tests/unit/test_commands_lint.py -v`
Expected: PASS (the 2 new tests + all pre-existing lint tests; the dataclass-shape test `test_lint_result_dataclass_shape` may assert a field list — if it does, add `open_proposals` there too).

- [ ] **Step 5: Print the roll-up in the lint CLI**

In `packages/graph-wiki-cli/src/graph_wiki_cli/wiki_cli/main.py`, in the human-readable lint block, after the `Total pages:` line (line ~118), add:

```python
        typer.echo(f"Open proposals: {result.open_proposals}")
```

This is presentation-only; the JSON path already serializes the new field via `dataclasses.asdict`.

- [ ] **Step 6: Run the CLI lint test if one asserts output (otherwise smoke-run)**

Run: `uv run --package graph-wiki-cli pytest -m "not integration" tests/unit/test_wiki_cli.py -v`
Expected: PASS (no regression; the lint print is additive).

- [ ] **Step 7: Commit**

```bash
git add packages/graph-wiki-core/src/graph_wiki_core/commands/lint.py \
        packages/graph-wiki-core/tests/unit/test_commands_lint.py \
        packages/graph-wiki-cli/src/graph_wiki_cli/wiki_cli/main.py
git commit -m "feat(lint): roll up open-proposal count"
```

---

## Task 10: Full-suite verification across touched packages

Confirm no cross-package regression — especially the MCP serializer (spec §3.6 says it runs unchanged) and the rest of the core ingest suite.

**Files:** none (verification only).

- [ ] **Step 1: Run the wiki-io suite**

Run: `uv run --package wiki-io pytest -q`
Expected: PASS (ledger + init_vault + backlink + index suites).

- [ ] **Step 2: Run the graph-wiki-core suite (non-integration)**

Run: `uv run --package graph-wiki-core pytest -m "not integration" -q`
Expected: PASS (suggest, ingest, proposals, lint).

- [ ] **Step 3: Run the graph-wiki-cli suite (non-integration)**

Run: `uv run --package graph-wiki-cli pytest -m "not integration" -q`
Expected: PASS.

- [ ] **Step 4: Run the graph-wiki-mcp suite (non-integration) to confirm the serializer is unaffected**

Run: `uv run --package graph-wiki-mcp pytest -m "not integration" -q`
Expected: PASS — `server.py:328-329,379-380` copies `result.suggested_pages` (a list of `{kind,title,slug,mode,status}` dicts) and `suggestions_parsed` verbatim; the report shape is preserved so no MCP change is needed.

- [ ] **Step 5: Lint + format the touched files**

Run: `uv run ruff check packages/wiki-io/src/wiki_io/proposals.py packages/graph-wiki-core/src/graph_wiki_core/commands/proposals.py`
Expected: no new errors on the created files. (Per project memory, do **not** run `ruff format` to "fix" the diff — match surrounding multi-line style by hand; the src tree is pre-existing format-dirty and unenforced.)

- [ ] **Step 6: Commit any lint fixes (if needed)**

```bash
git add -A
git commit -m "chore(proposals): lint touched files"
```

---

## Self-Review (run by the plan author, completed)

**1. Spec coverage**

| Spec section | Task(s) |
|---|---|
| §3.1 identity / note shape (D1) | Task 2 (`proposal_path`, `read_proposal`, `render_proposal_body`), Task 3 origins shape |
| §3.2 lifecycle merge (D2) | Task 3 (`upsert_proposal`): create / human-untouched / refresh / byte-stable |
| §3.3 mode dedup stays in producer (D3) | Task 6 (`run_suggest_phase` keeps `build_curated_vault_index` + `_validate_proposal`; ledger never re-derives mode) |
| §3.4 ledger module (D4) | Tasks 2-4 (all six functions: path/read/list/upsert/render/set-status) |
| §3.5 M3 retrofit (D5) | Task 6 (reuse decision fns; delete storage fns; retarget output; degraded = zero notes) |
| §3.6 IngestResult report shape (D6) | Task 7 (fields unchanged; report dict keeps kind/title/slug/mode/status) + Task 10 Step 4 (MCP unchanged) |
| §3.7 CLI surface (D7) | Task 8 (`proposals` list + `proposal approve|reject`, `--json`) + Task 9 (lint roll-up) |
| §3.8 bootstrap dir + non-changes (D8) | Task 1 (FIXED_VAULT_DIRS) + Task 5 (index/backlink guards) + §"No migration" honored (no migration code anywhere) |
| §5 tests 1-11 | 1-5 → Tasks 2-4; 6-8 → Tasks 6-7; 9 → Task 8; 10 → Task 9; 11 → Tasks 1+5 |

**2. Placeholder scan:** No "TBD"/"add error handling"/"similar to Task N" — every code and test step shows complete content.

**3. Type consistency:** `upsert_proposal` consumes a producer dict `{kind, mode, target_slug, title, origin}` and returns a record `{kind, mode, target_slug, title, status, origins}`; `run_suggest_phase` builds exactly that input and maps the record to the report `{kind, title, slug, mode, status}` (slug = target_slug) — consistent across Tasks 3/6/7. `split_proposal_id`/`set_proposal_status` signatures match between Task 4, Task 8 core wrappers, and the CLI. `ProposalDecision(proposal_id, status)` is consistent across the core module, its tests, and the CLI test.

**Open question #3 settled (per spec §7):** multi-origin rationale renders as **one block per origin** (`render_proposal_body`, Task 2) — not a deduped summary.

---

Plan complete and saved to `docs/superpowers/plans/2026-06-05-curated-page-proposal-ledger-foundation.md`. Two execution options:

1. **Subagent-Driven (recommended)** — I dispatch a fresh subagent per task, review between tasks, fast iteration.
2. **Inline Execution** — Execute tasks in this session using executing-plans, batch execution with checkpoints.
