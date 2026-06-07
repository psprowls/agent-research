# graph-wiki Work Layer Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the complete graph-wiki work layer: `work-io` package with deterministic lifecycle logic, orchestration functions in `graph-wiki-core`, a `gw work` CLI subapp, four plugin commands, and work-layer lint integrated into `gw wiki lint`.

**Architecture:** `work-io` holds pure lifecycle logic (frontmatter parse/emit, plan table parse, sidecar build/write/load, 19 lifecycle lint rules, archive planning); `graph-wiki-core/commands/work.py` wires `work-io` with `wiki-io` I/O side-effects; `graph-wiki-cli/work_cli/main.py` presents CLI commands over those async functions; plugin `.md` files provide interactive Claude Code wrappers.

**Tech Stack:** Python 3.11, pyyaml≥6.0, typer, pathlib, pytest, dataclasses

**Prerequisite:** The `worktree-wikilink-base-wiki-root` branch has already landed — `workspace_io.paths.work_dir()` already returns `wiki_dir(workspace) / "work"`. Verify: `grep work_dir packages/workspace-io/src/workspace_io/paths.py` should show `return wiki_dir(workspace) / "work"`.

---

## File Map

**New files**
- `packages/work-io/pyproject.toml`
- `packages/work-io/src/work_io/__init__.py`
- `packages/work-io/src/work_io/frontmatter.py`
- `packages/work-io/src/work_io/plan_table.py`
- `packages/work-io/src/work_io/sidecar.py`
- `packages/work-io/src/work_io/lifecycle_lint.py`
- `packages/work-io/src/work_io/archive.py`
- `packages/work-io/tests/__init__.py`
- `packages/work-io/tests/unit/test_frontmatter.py`
- `packages/work-io/tests/unit/test_plan_table.py`
- `packages/work-io/tests/unit/test_sidecar.py`
- `packages/work-io/tests/unit/test_lifecycle_lint.py`
- `packages/work-io/tests/unit/test_archive.py`
- `packages/graph-wiki-core/src/graph_wiki_core/commands/work.py`
- `packages/graph-wiki-core/tests/unit/test_commands_work.py`
- `packages/graph-wiki-cli/src/graph_wiki_cli/work_cli/__init__.py`
- `packages/graph-wiki-cli/src/graph_wiki_cli/work_cli/main.py`
- `packages/graph-wiki-cli/tests/unit/test_work_cli.py`
- `plugins/graph-wiki/commands/file.md`
- `plugins/graph-wiki/commands/archive.md`
- `plugins/graph-wiki/commands/status.md`
- `plugins/graph-wiki/commands/regen-index.md`

**Modified files**
- `packages/graph-wiki-core/pyproject.toml` — add `work-io` dep
- `packages/graph-wiki-cli/pyproject.toml` — add `work-io` dep
- `packages/graph-wiki-core/src/graph_wiki_core/commands/lint.py` — add `work_lint_findings` field + call `run_work_lint`
- `packages/graph-wiki-cli/src/graph_wiki_cli/wiki_cli/main.py` — add Work lifecycle section to lint output
- `packages/graph-wiki-cli/src/graph_wiki_cli/cli.py` — register `work_app`
- `plugins/graph-wiki/commands/lint.md` — add work-layer note

---

## Task 1: work-io package scaffold

**Files:**
- Create: `packages/work-io/pyproject.toml`
- Create: `packages/work-io/src/work_io/__init__.py`
- Create: `packages/work-io/tests/__init__.py`

- [ ] **Step 1: Create pyproject.toml**

```toml
[project]
name = "work-io"
version = "0.1.0"
description = "Deterministic lifecycle logic for graph-wiki work items."
requires-python = ">=3.11"
dependencies = ["workspace-io", "pyyaml>=6.0"]

[build-system]
requires = ["uv_build>=0.11.14,<0.12"]
build-backend = "uv_build"

[tool.uv.sources]
workspace-io = { workspace = true }

[tool.pytest.ini_options]
testpaths = ["tests"]
addopts = "--import-mode=importlib"
asyncio_mode = "auto"
markers = ["integration: requires real Bedrock or subprocess (skipped in CI by default)"]
```

Save to `packages/work-io/pyproject.toml`.

- [ ] **Step 2: Create package init and test dirs**

`packages/work-io/src/work_io/__init__.py` — empty file.

`packages/work-io/tests/__init__.py` — empty file.

`packages/work-io/tests/unit/__init__.py` — empty file.

- [ ] **Step 3: Sync workspace**

```bash
uv sync
```

Expected: no errors, `work-io` appears in the installed packages.

- [ ] **Step 4: Commit**

```bash
git add packages/work-io/
git commit -m "feat(work-io): add package scaffold"
```

---

## Task 2: frontmatter.py — parse and emit

**Files:**
- Create: `packages/work-io/src/work_io/frontmatter.py`
- Create: `packages/work-io/tests/unit/test_frontmatter.py`

- [ ] **Step 1: Write failing tests**

`packages/work-io/tests/unit/test_frontmatter.py`:

```python
from __future__ import annotations
import pytest
from work_io.frontmatter import parse, emit


def test_parse_roundtrip() -> None:
    text = "---\ntitle: Fix the bug\nstatus: open\n---\n\n## Body\nContent here.\n"
    fm, body = parse(text)
    assert fm == {"title": "Fix the bug", "status": "open"}
    assert body.strip() == "## Body\nContent here."


def test_parse_list_field() -> None:
    text = "---\naffects:\n  - packages/foo\n  - packages/bar\n---\n"
    fm, body = parse(text)
    assert fm["affects"] == ["packages/foo", "packages/bar"]
    assert body == ""


def test_parse_missing_open_fence_raises() -> None:
    with pytest.raises(ValueError, match="no frontmatter block"):
        parse("title: foo\n")


def test_parse_unclosed_fence_raises() -> None:
    with pytest.raises(ValueError, match="unclosed frontmatter"):
        parse("---\ntitle: foo\n")


def test_parse_non_mapping_raises() -> None:
    with pytest.raises(ValueError, match="YAML mapping"):
        parse("---\n- item1\n- item2\n---\n")


def test_parse_empty_frontmatter() -> None:
    text = "---\n---\n\nbody text\n"
    fm, body = parse(text)
    assert fm == {}
    assert body.strip() == "body text"


def test_emit_produces_fenced_block() -> None:
    fm = {"title": "My item", "status": "open"}
    result = emit(fm)
    assert result.startswith("---\n")
    assert result.endswith("---")
    assert "title: My item" in result
    assert "status: open" in result


def test_emit_parse_roundtrip() -> None:
    fm = {"title": "Test", "kind": "bug", "affects": ["packages/foo"]}
    emitted = emit(fm)
    parsed_fm, _ = parse(emitted + "\n\nbody\n")
    assert parsed_fm == fm
```

- [ ] **Step 2: Run to verify tests fail**

```bash
uv run --package work-io pytest tests/unit/test_frontmatter.py -v
```

Expected: `ModuleNotFoundError: No module named 'work_io.frontmatter'`

- [ ] **Step 3: Implement frontmatter.py**

`packages/work-io/src/work_io/frontmatter.py`:

```python
"""Frontmatter parse/emit for work item pages."""
from __future__ import annotations

import yaml


def parse(text: str) -> tuple[dict, str]:
    """Return (frontmatter_dict, body_text). Raises ValueError on malformed input."""
    if not text.startswith("---"):
        raise ValueError("no frontmatter block found: text must start with ---")
    rest = text[3:]
    if "\n---" not in rest:
        raise ValueError("unclosed frontmatter block: no closing ---")
    idx = rest.index("\n---")
    fm_text = rest[:idx].strip()
    body = rest[idx + 4:]
    if body.startswith("\n"):
        body = body[1:]
    fm = yaml.safe_load(fm_text) if fm_text else {}
    if fm is None:
        fm = {}
    if not isinstance(fm, dict):
        raise ValueError(f"frontmatter must be a YAML mapping, got {type(fm).__name__}")
    return fm, body


def emit(fm: dict) -> str:
    """Serialize frontmatter dict to a fenced YAML block (--- ... ---)."""
    content = yaml.safe_dump(
        fm, default_flow_style=False, sort_keys=False, allow_unicode=True
    )
    return f"---\n{content}---"
```

- [ ] **Step 4: Run to verify tests pass**

```bash
uv run --package work-io pytest tests/unit/test_frontmatter.py -v
```

Expected: all 8 tests PASS.

- [ ] **Step 5: Commit**

```bash
git add packages/work-io/
git commit -m "feat(work-io): frontmatter parse/emit"
```

---

## Task 3: plan_table.py — plan table parsing

**Files:**
- Create: `packages/work-io/src/work_io/plan_table.py`
- Create: `packages/work-io/tests/unit/test_plan_table.py`

- [ ] **Step 1: Write failing tests**

`packages/work-io/tests/unit/test_plan_table.py`:

```python
from __future__ import annotations
import pytest
from work_io.plan_table import parse_plan, PlanResult


BODY_WITH_PLAN = """
## Plan

| Action | Done when | Rationale |
|---|---|---|
| Write tests | Tests pass | TDD |
| Deploy | CI green | Release |
"""

BODY_MISSING_HEADING = """
## Summary
Some content here.
"""

BODY_MALFORMED = """
## Plan

No table here, just prose.
"""

BODY_EMPTY_TABLE = """
## Plan

| Action | Done when | Rationale |
|---|---|---|
"""

BODY_ESCAPED_PIPE = r"""
## Plan

| Action | Done when | Rationale |
|---|---|---|
| Fix A \| B | Done | Reason |
"""


def test_parse_ok_returns_rows() -> None:
    result = parse_plan(BODY_WITH_PLAN)
    assert result.state == "ok"
    assert len(result.rows) == 2
    assert result.rows[0]["action"] == "Write tests"
    assert result.rows[0]["done_when"] == "Tests pass"
    assert result.rows[0]["rationale"] == "TDD"


def test_parse_missing_heading() -> None:
    result = parse_plan(BODY_MISSING_HEADING)
    assert result.state == "missing"
    assert result.rows == []


def test_parse_malformed_no_table() -> None:
    result = parse_plan(BODY_MALFORMED)
    assert result.state == "malformed"


def test_parse_empty_table() -> None:
    result = parse_plan(BODY_EMPTY_TABLE)
    assert result.state == "empty"
    assert result.rows == []


def test_parse_escaped_pipe_in_cell() -> None:
    result = parse_plan(BODY_ESCAPED_PIPE)
    assert result.state == "ok"
    assert result.rows[0]["action"] == "Fix A | B"


def test_parse_permissive_two_of_three_columns() -> None:
    body = """
## Plan

| Action | Rationale |
|---|---|
| Step 1 | Because |
"""
    result = parse_plan(body)
    assert result.state == "ok"
    assert result.rows[0]["done_when"] == ""


def test_parse_case_insensitive_headers() -> None:
    body = """
## Plan

| ACTION | DONE WHEN | RATIONALE |
|---|---|---|
| Step | Done | OK |
"""
    result = parse_plan(body)
    assert result.state == "ok"


def test_parse_heading_case_insensitive() -> None:
    body = "## plan\n\n| Action | Done when | Rationale |\n|---|---|\n| x | y | z |\n"
    result = parse_plan(body)
    assert result.state == "ok"
```

- [ ] **Step 2: Run to verify tests fail**

```bash
uv run --package work-io pytest tests/unit/test_plan_table.py -v
```

Expected: `ModuleNotFoundError: No module named 'work_io.plan_table'`

- [ ] **Step 3: Implement plan_table.py**

`packages/work-io/src/work_io/plan_table.py`:

```python
"""Parse the ## Plan markdown table from a work item body."""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Literal


@dataclass
class PlanResult:
    state: Literal["missing", "empty", "malformed", "ok"]
    rows: list[dict] = field(default_factory=list)


def parse_plan(body: str) -> PlanResult:
    """Locate ## Plan heading; extract markdown table rows."""
    lines = body.splitlines()

    plan_idx = None
    for i, line in enumerate(lines):
        if re.match(r"^##\s+plan\s*$", line.strip(), re.IGNORECASE):
            plan_idx = i
            break

    if plan_idx is None:
        return PlanResult(state="missing")

    table_lines: list[str] = []
    for line in lines[plan_idx + 1 :]:
        stripped = line.strip()
        if stripped.startswith("|"):
            table_lines.append(stripped)
        elif table_lines:
            break

    if not table_lines:
        return PlanResult(state="malformed")

    header_cells = _split_row(table_lines[0])
    header_lower = [h.lower().strip() for h in header_cells]

    canonical = {"action", "done when", "rationale"}
    found = {name for name in canonical if name in header_lower}
    if len(found) < 2:
        return PlanResult(state="malformed")

    col_action = header_lower.index("action") if "action" in header_lower else None
    col_done_when = header_lower.index("done when") if "done when" in header_lower else None
    col_rationale = header_lower.index("rationale") if "rationale" in header_lower else None

    data_lines = [
        ln for ln in table_lines[1:]
        if not re.match(r"^\|[\s\-:|]+\|$", ln)
    ]

    if not data_lines:
        return PlanResult(state="empty")

    max_col = max(c for c in [col_action, col_done_when, col_rationale] if c is not None)
    rows = []
    for line in data_lines:
        cells = _split_row(line)
        while len(cells) <= max_col:
            cells.append("")
        rows.append({
            "action": cells[col_action].strip() if col_action is not None else "",
            "done_when": cells[col_done_when].strip() if col_done_when is not None else "",
            "rationale": cells[col_rationale].strip() if col_rationale is not None else "",
        })

    return PlanResult(state="ok", rows=rows)


def _split_row(row: str) -> list[str]:
    """Split a markdown table row into cells, unescaping \\| in cell content."""
    row = row.strip().strip("|")
    cells = re.split(r"(?<!\\)\|", row)
    return [c.replace(r"\|", "|") for c in cells]
```

- [ ] **Step 4: Run to verify tests pass**

```bash
uv run --package work-io pytest tests/unit/test_plan_table.py -v
```

Expected: all 8 tests PASS.

- [ ] **Step 5: Commit**

```bash
git add packages/work-io/
git commit -m "feat(work-io): plan table parser"
```

---

## Task 4: sidecar.py — build, write, load, is_stale

**Files:**
- Create: `packages/work-io/src/work_io/sidecar.py`
- Create: `packages/work-io/tests/unit/test_sidecar.py`

- [ ] **Step 1: Write failing tests**

`packages/work-io/tests/unit/test_sidecar.py`:

```python
from __future__ import annotations
import json
from pathlib import Path
import pytest
from work_io.sidecar import build_sidecar, write_sidecar, load_sidecar, is_stale, SCHEMA_VERSION


def _make_work_item(work_dir: Path, stem: str, status: str = "open", kind: str = "bug",
                    severity: str | None = None, blast_radius: str | None = None,
                    opened: str = "2026-01-01", updated: str = "2026-01-01") -> None:
    lines = [
        "---",
        f"title: {stem}",
        f"status: {status}",
        f"kind: {kind}",
        f"opened: {opened}",
        f"updated: {updated}",
    ]
    if severity:
        lines.append(f"severity: {severity}")
    if blast_radius:
        lines.append(f"blast_radius: {blast_radius}")
    lines += ["---", "", "## Body", ""]
    (work_dir / f"{opened}-{stem}.md").write_text("\n".join(lines))


def test_build_sidecar_basic(tmp_path: Path) -> None:
    work_dir = tmp_path / "work"
    work_dir.mkdir()
    _make_work_item(work_dir, "fix-bug", status="open", kind="bug", opened="2026-06-01", updated="2026-06-01")
    _make_work_item(work_dir, "add-feature", status="in-progress", kind="feature", opened="2026-05-01", updated="2026-05-15")

    sidecar = build_sidecar(work_dir, vault_commit="abc123")

    assert sidecar["schema_version"] == SCHEMA_VERSION
    assert sidecar["vault_commit"] == "abc123"
    assert "generated_at" in sidecar
    assert len(sidecar["items"]) == 2
    assert sidecar["counts"]["by_status"]["open"] == 1
    assert sidecar["counts"]["by_status"]["in-progress"] == 1
    assert sidecar["counts"]["by_kind"]["bug"] == 1


def test_build_sidecar_excludes_archived(tmp_path: Path) -> None:
    work_dir = tmp_path / "work"
    work_dir.mkdir()
    archived = work_dir / "archived"
    archived.mkdir()
    _make_work_item(work_dir, "active", opened="2026-06-01", updated="2026-06-01")
    _make_work_item(archived, "old", opened="2026-01-01", updated="2026-01-01")

    sidecar = build_sidecar(work_dir, vault_commit=None)
    assert len(sidecar["items"]) == 1
    assert sidecar["items"][0]["slug"] == "2026-06-01-active"


def test_build_sidecar_items_sorted_by_opened_desc(tmp_path: Path) -> None:
    work_dir = tmp_path / "work"
    work_dir.mkdir()
    _make_work_item(work_dir, "older", opened="2026-01-01", updated="2026-01-01")
    _make_work_item(work_dir, "newer", opened="2026-06-01", updated="2026-06-01")

    sidecar = build_sidecar(work_dir, vault_commit=None)
    assert sidecar["items"][0]["slug"] == "2026-06-01-newer"
    assert sidecar["items"][1]["slug"] == "2026-01-01-older"


def test_write_and_load_sidecar(tmp_path: Path) -> None:
    wiki = tmp_path / "wiki"
    wiki.mkdir()
    sidecar = {"schema_version": 1, "generated_at": "2026-06-01T00:00:00+00:00",
                "vault_commit": None, "counts": {}, "items": []}

    write_sidecar(wiki, sidecar)

    assert (wiki / "work-index.json").exists()
    loaded = load_sidecar(wiki)
    assert loaded == sidecar


def test_load_sidecar_returns_none_when_absent(tmp_path: Path) -> None:
    wiki = tmp_path / "wiki"
    wiki.mkdir()
    assert load_sidecar(wiki) is None


def test_is_stale_true_when_item_updated_after_generated(tmp_path: Path) -> None:
    work_dir = tmp_path / "work"
    work_dir.mkdir()
    _make_work_item(work_dir, "fresh", opened="2026-06-01", updated="2026-06-05")
    sidecar = {"generated_at": "2026-06-03T00:00:00+00:00", "items": []}

    assert is_stale(sidecar, work_dir) is True


def test_is_stale_false_when_all_items_older(tmp_path: Path) -> None:
    work_dir = tmp_path / "work"
    work_dir.mkdir()
    _make_work_item(work_dir, "old", opened="2026-01-01", updated="2026-01-01")
    sidecar = {"generated_at": "2026-06-01T00:00:00+00:00", "items": []}

    assert is_stale(sidecar, work_dir) is False
```

- [ ] **Step 2: Run to verify tests fail**

```bash
uv run --package work-io pytest tests/unit/test_sidecar.py -v
```

Expected: `ModuleNotFoundError: No module named 'work_io.sidecar'`

- [ ] **Step 3: Implement sidecar.py**

`packages/work-io/src/work_io/sidecar.py`:

```python
"""Build, write, load, and staleness-check the work-index.json sidecar."""
from __future__ import annotations

import json
import tempfile
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

SCHEMA_VERSION = 1


def build_sidecar(work_dir: Path, vault_commit: str | None) -> dict:
    """Walk work_dir/*.md (excluding archived/), parse each item, return sidecar dict."""
    from work_io.frontmatter import parse as fm_parse

    items = []
    for md in sorted(work_dir.glob("*.md")):
        try:
            fm, _ = fm_parse(md.read_text(encoding="utf-8"))
        except (ValueError, Exception):
            continue
        items.append({
            "slug": md.stem,
            "title": str(fm.get("title", "")),
            "kind": str(fm.get("kind", "")),
            "status": str(fm.get("status", "")),
            "severity": fm.get("severity") or None,
            "blast_radius": fm.get("blast_radius") or None,
            "opened": str(fm.get("opened", "")),
            "updated": str(fm.get("updated", "")),
        })

    items.sort(key=lambda x: (-_date_int(x["opened"]), x["slug"]))

    by_status = Counter(i["status"] for i in items if i["status"])
    by_kind = Counter(i["kind"] for i in items if i["kind"])
    by_severity = Counter(i["severity"] for i in items if i["severity"])
    by_blast_radius = Counter(i["blast_radius"] for i in items if i["blast_radius"])

    return {
        "schema_version": SCHEMA_VERSION,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "vault_commit": vault_commit,
        "counts": {
            "by_status": dict(by_status),
            "by_kind": dict(by_kind),
            "by_severity": dict(by_severity),
            "by_blast_radius": dict(by_blast_radius),
        },
        "items": items,
    }


def write_sidecar(wiki: Path, sidecar: dict) -> None:
    """Atomically write sidecar dict to wiki/work-index.json (write-temp + rename)."""
    target = wiki / "work-index.json"
    with tempfile.NamedTemporaryFile(
        mode="w", suffix=".tmp", dir=wiki, delete=False, encoding="utf-8"
    ) as f:
        json.dump(sidecar, f, indent=2, ensure_ascii=False)
        tmp_path = Path(f.name)
    tmp_path.rename(target)


def load_sidecar(wiki: Path) -> dict | None:
    """Return parsed sidecar dict or None if absent."""
    target = wiki / "work-index.json"
    if not target.exists():
        return None
    return json.loads(target.read_text(encoding="utf-8"))


def is_stale(sidecar: dict, work_dir: Path) -> bool:
    """True if any item's updated date > sidecar generated_at date."""
    from work_io.frontmatter import parse as fm_parse

    generated_prefix = sidecar.get("generated_at", "")[:10]
    if not generated_prefix:
        return True

    for md in work_dir.glob("*.md"):
        try:
            fm, _ = fm_parse(md.read_text(encoding="utf-8"))
            updated = str(fm.get("updated", ""))[:10]
            if updated > generated_prefix:
                return True
        except Exception:
            continue
    return False


def _date_int(date_str: str) -> int:
    """YYYY-MM-DD → int for sort (higher = more recent). 0 on failure."""
    try:
        return int(date_str.replace("-", ""))
    except (ValueError, AttributeError):
        return 0
```

- [ ] **Step 4: Run to verify tests pass**

```bash
uv run --package work-io pytest tests/unit/test_sidecar.py -v
```

Expected: all 8 tests PASS.

- [ ] **Step 5: Commit**

```bash
git add packages/work-io/
git commit -m "feat(work-io): sidecar build/write/load/is_stale"
```

---

## Task 5: lifecycle_lint.py — all 19 rules

**Files:**
- Create: `packages/work-io/src/work_io/lifecycle_lint.py`
- Create: `packages/work-io/tests/unit/test_lifecycle_lint.py`

- [ ] **Step 1: Write failing tests**

`packages/work-io/tests/unit/test_lifecycle_lint.py`:

```python
from __future__ import annotations
from datetime import date, timedelta
from work_io.lifecycle_lint import run_lint, LintFinding
from work_io.plan_table import PlanResult


def _item(slug: str = "test-item", status: str = "open", kind: str = "bug",
           severity: str | None = None, updated_days_ago: int = 0,
           plan: PlanResult | None = None, **extra) -> dict:
    updated = (date.today() - timedelta(days=updated_days_ago)).isoformat()
    fm: dict = {"title": slug, "status": status, "kind": kind, "updated": updated}
    if severity:
        fm["severity"] = severity
    fm.update(extra)
    return {"slug": slug, "fm": fm, "plan": plan or PlanResult(state="missing")}


def _rule_ids(findings: list[LintFinding]) -> set[str]:
    return {f.rule_id for f in findings}


# --- Schema-shape rules ---

def test_status_not_in_enum() -> None:
    findings = run_lint([_item(status="unknown-status")], None, None)
    assert "status-not-in-enum" in _rule_ids(findings)


def test_kind_not_in_enum() -> None:
    findings = run_lint([_item(kind="unknown-kind")], None, None)
    assert "kind-not-in-enum" in _rule_ids(findings)


def test_severity_on_non_bug() -> None:
    findings = run_lint([_item(kind="feature", severity="high")], None, None)
    assert "severity-on-non-bug" in _rule_ids(findings)


def test_severity_on_bug_is_ok() -> None:
    findings = run_lint([_item(kind="bug", severity="high")], None, None)
    assert "severity-on-non-bug" not in _rule_ids(findings)


# --- State-conditional rules ---

def test_accepted_without_plan() -> None:
    findings = run_lint([_item(status="accepted", plan=PlanResult(state="missing"))], None, None)
    assert "accepted-without-plan" in _rule_ids(findings)


def test_accepted_with_plan_ok() -> None:
    plan = PlanResult(state="ok", rows=[{"action": "Do it", "done_when": "", "rationale": ""}])
    findings = run_lint([_item(status="accepted", plan=plan)], None, None)
    assert "accepted-without-plan" not in _rule_ids(findings)


def test_in_progress_without_ref() -> None:
    findings = run_lint([_item(status="in-progress")], None, None)
    assert "in-progress-without-ref" in _rule_ids(findings)


def test_in_progress_with_owner_ok() -> None:
    findings = run_lint([_item(status="in-progress", owner="pat")], None, None)
    assert "in-progress-without-ref" not in _rule_ids(findings)


def test_resolved_without_ref() -> None:
    findings = run_lint([_item(status="resolved")], None, None)
    assert "resolved-without-ref" in _rule_ids(findings)


def test_superseded_without_link() -> None:
    findings = run_lint([_item(status="superseded")], None, None)
    assert "superseded-without-link" in _rule_ids(findings)


def test_mitigated_without_mitigation() -> None:
    findings = run_lint([_item(status="mitigated")], None, None)
    assert "mitigated-without-mitigation" in _rule_ids(findings)


def test_wontfix_without_rationale() -> None:
    findings = run_lint([_item(status="wontfix")], None, None)
    assert "wontfix-without-rationale" in _rule_ids(findings)


# --- Lifecycle / staleness ---

def test_stuck_open_over_30d() -> None:
    findings = run_lint([_item(status="open", updated_days_ago=31)], None, None)
    assert "stuck-open" in _rule_ids(findings)


def test_stuck_open_under_30d_ok() -> None:
    findings = run_lint([_item(status="open", updated_days_ago=29)], None, None)
    assert "stuck-open" not in _rule_ids(findings)


def test_stuck_accepted_over_60d() -> None:
    findings = run_lint([_item(status="accepted", updated_days_ago=61,
                               plan=PlanResult(state="ok",
                               rows=[{"action": "x", "done_when": "", "rationale": ""}]))], None, None)
    assert "stuck-accepted" in _rule_ids(findings)


def test_archive_eligible() -> None:
    findings = run_lint([_item(status="resolved", updated_days_ago=8,
                               resolved_in="pr#1")], None, None)
    assert "archive-eligible" in _rule_ids(findings)


def test_archive_eligible_under_7d_not_flagged() -> None:
    findings = run_lint([_item(status="resolved", updated_days_ago=5,
                               resolved_in="pr#1")], None, None)
    assert "archive-eligible" not in _rule_ids(findings)


# --- Body shape ---

def test_done_when_missing_for_feature() -> None:
    plan = PlanResult(state="ok", rows=[{"action": "Step", "done_when": "", "rationale": ""}])
    findings = run_lint([_item(kind="feature", plan=plan, status="in-progress", owner="pat")], None, None)
    assert "done-when-missing" in _rule_ids(findings)


def test_feature_without_target() -> None:
    findings = run_lint([_item(kind="feature", status="open")], None, None)
    assert "feature-without-target" in _rule_ids(findings)


def test_feature_with_target_ok() -> None:
    findings = run_lint([_item(kind="feature", status="open", target="2026-Q3")], None, None)
    assert "feature-without-target" not in _rule_ids(findings)


def test_plan_table_malformed() -> None:
    findings = run_lint([_item(plan=PlanResult(state="malformed"))], None, None)
    assert "plan-table-malformed" in _rule_ids(findings)


# --- Sidecar rules ---

def test_sidecar_missing() -> None:
    findings = run_lint([_item()], None, sidecar=None)
    assert "sidecar-missing" in _rule_ids(findings)


def test_sidecar_stale() -> None:
    items = [_item(updated_days_ago=0)]  # updated today
    sidecar = {"generated_at": "2026-01-01T00:00:00+00:00", "items": []}
    findings = run_lint(items, None, sidecar)
    assert "sidecar-stale" in _rule_ids(findings)


def test_sidecar_fresh_not_stale() -> None:
    items = [_item(updated_days_ago=5)]
    updated_str = (date.today() - timedelta(days=5)).isoformat()
    sidecar = {"generated_at": f"9999-01-01T00:00:00+00:00", "items": []}
    findings = run_lint(items, None, sidecar)
    assert "sidecar-stale" not in _rule_ids(findings)


# --- Finding shape ---

def test_lint_finding_has_required_fields() -> None:
    findings = run_lint([_item(status="bad-status")], None, None)
    f = next(f for f in findings if f.rule_id == "status-not-in-enum")
    assert f.severity == "error"
    assert f.slug == "test-item"
    assert f.message
```

- [ ] **Step 2: Run to verify tests fail**

```bash
uv run --package work-io pytest tests/unit/test_lifecycle_lint.py -v
```

Expected: `ModuleNotFoundError: No module named 'work_io.lifecycle_lint'`

- [ ] **Step 3: Implement lifecycle_lint.py**

`packages/work-io/src/work_io/lifecycle_lint.py`:

```python
"""19 lifecycle lint rules for work items."""
from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import date, timedelta
from pathlib import Path
from typing import Literal

from work_io.plan_table import PlanResult

VALID_STATUSES = frozenset({"open", "accepted", "in-progress", "mitigated", "resolved", "wontfix", "superseded"})
VALID_KINDS = frozenset({"bug", "tech-debt", "test-gap", "security", "perf", "feature", "initiative", "spike"})
BUG_LIKE_KINDS = frozenset({"bug", "security", "perf", "tech-debt", "test-gap"})
TERMINAL_STATUSES = frozenset({"resolved", "wontfix", "superseded"})
FEATURE_LIKE_KINDS = frozenset({"feature", "initiative"})

_PATH_RE = re.compile(r"\b([\w][\w.\-]*/[\w.\-/]+)\b")


@dataclass
class LintFinding:
    rule_id: str
    severity: Literal["error", "warn", "info"]
    slug: str
    message: str


def run_lint(
    items: list[dict],
    repo_root: Path | None,
    sidecar: dict | None,
) -> list[LintFinding]:
    """Run all 19 lifecycle rules. Each item dict has keys: slug, fm, plan (PlanResult)."""
    findings: list[LintFinding] = []

    for item in items:
        slug: str = item["slug"]
        fm: dict = item["fm"]
        plan: PlanResult = item["plan"]
        status = str(fm.get("status", ""))
        kind = str(fm.get("kind", ""))

        # 1. status-not-in-enum
        if status not in VALID_STATUSES:
            findings.append(LintFinding("status-not-in-enum", "error", slug,
                f"status {status!r} not in {sorted(VALID_STATUSES)}"))

        # 2. kind-not-in-enum
        if kind not in VALID_KINDS:
            findings.append(LintFinding("kind-not-in-enum", "error", slug,
                f"kind {kind!r} not in {sorted(VALID_KINDS)}"))

        # 3. severity-on-non-bug
        if fm.get("severity") and kind not in BUG_LIKE_KINDS:
            findings.append(LintFinding("severity-on-non-bug", "info", slug,
                f"severity set on kind={kind!r}; severity applies to bug-like kinds only"))

        # 4. accepted-without-plan
        if status == "accepted" and plan.state not in ("ok", "empty"):
            findings.append(LintFinding("accepted-without-plan", "error", slug,
                "status=accepted but ## Plan table is missing or malformed"))

        # 5. in-progress-without-ref
        if status == "in-progress" and not (fm.get("owner") or fm.get("related_prs")):
            findings.append(LintFinding("in-progress-without-ref", "error", slug,
                "status=in-progress but no owner or related_prs set"))

        # 6. resolved-without-ref
        if status == "resolved" and not fm.get("resolved_in"):
            findings.append(LintFinding("resolved-without-ref", "warn", slug,
                "status=resolved but resolved_in is blank"))

        # 7. superseded-without-link
        if status == "superseded" and not fm.get("superseded_by"):
            findings.append(LintFinding("superseded-without-link", "error", slug,
                "status=superseded but superseded_by is blank"))

        # 8. mitigated-without-mitigation
        if status == "mitigated" and not fm.get("mitigation"):
            findings.append(LintFinding("mitigated-without-mitigation", "error", slug,
                "status=mitigated but mitigation field is blank"))

        # 9. wontfix-without-rationale
        if status == "wontfix" and not fm.get("rationale"):
            findings.append(LintFinding("wontfix-without-rationale", "warn", slug,
                "status=wontfix but rationale field is blank"))

        # 10. affects-target-missing (skipped when repo_root is None)
        if repo_root is not None:
            for affects_path in fm.get("affects") or []:
                if affects_path and not (repo_root / str(affects_path)).exists():
                    findings.append(LintFinding("affects-target-missing", "error", slug,
                        f"affects path {affects_path!r} does not exist under repo root"))

        # 11. plan-action-target-missing (skipped when repo_root is None)
        if repo_root is not None and plan.state == "ok":
            for row in plan.rows:
                for token in _PATH_RE.findall(row.get("action", "")):
                    if not token.startswith("http") and not (repo_root / token).exists():
                        findings.append(LintFinding("plan-action-target-missing", "error", slug,
                            f"plan action references {token!r} which does not exist under repo root"))

        # 12. stuck-open
        if status == "open" and _days_since(str(fm.get("updated", ""))) > 30:
            findings.append(LintFinding("stuck-open", "warn", slug,
                f"status=open with no update in >30 days"))

        # 13. stuck-accepted
        if status == "accepted" and _days_since(str(fm.get("updated", ""))) > 60:
            findings.append(LintFinding("stuck-accepted", "warn", slug,
                f"status=accepted with no update in >60 days"))

        # 14. archive-eligible
        if status in TERMINAL_STATUSES and _days_since(str(fm.get("updated", ""))) >= 7:
            findings.append(LintFinding("archive-eligible", "info", slug,
                f"status={status!r} (terminal) and updated ≥7 days ago; consider archiving"))

        # 15. done-when-missing
        if kind in FEATURE_LIKE_KINDS and plan.state == "ok":
            if any(not row.get("done_when") for row in plan.rows):
                findings.append(LintFinding("done-when-missing", "warn", slug,
                    f"kind={kind!r} plan has rows with empty 'Done when' column"))

        # 16. feature-without-target
        if kind in FEATURE_LIKE_KINDS and not fm.get("target"):
            findings.append(LintFinding("feature-without-target", "warn", slug,
                f"kind={kind!r} has no target (YYYY-QN or YYYY-MM)"))

        # 17. plan-table-malformed
        if plan.state == "malformed":
            findings.append(LintFinding("plan-table-malformed", "warn", slug,
                "## Plan heading present but no valid markdown table follows"))

    # 18. sidecar-missing (global)
    if sidecar is None:
        findings.append(LintFinding("sidecar-missing", "warn", "(sidecar)",
            "work-index.json is absent; run `gw work regen-index`"))

    # 19. sidecar-stale (global)
    if sidecar is not None:
        generated_prefix = sidecar.get("generated_at", "")[:10]
        max_updated = max(
            (item["fm"].get("updated", "")[:10] for item in items),
            default="",
        )
        if generated_prefix and max_updated > generated_prefix:
            findings.append(LintFinding("sidecar-stale", "warn", "(sidecar)",
                f"sidecar generated_at {generated_prefix!r} is older than newest item updated {max_updated!r}"))

    return findings


def _days_since(date_str: str) -> int:
    """Days elapsed since a YYYY-MM-DD date string. Returns 0 on parse failure."""
    try:
        dt = date.fromisoformat(date_str[:10])
        return (date.today() - dt).days
    except (ValueError, TypeError):
        return 0
```

- [ ] **Step 4: Run to verify tests pass**

```bash
uv run --package work-io pytest tests/unit/test_lifecycle_lint.py -v
```

Expected: all 25 tests PASS.

- [ ] **Step 5: Commit**

```bash
git add packages/work-io/
git commit -m "feat(work-io): 19 lifecycle lint rules"
```

---

## Task 6: archive.py — plan_archive

**Files:**
- Create: `packages/work-io/src/work_io/archive.py`
- Create: `packages/work-io/tests/unit/test_archive.py`

- [ ] **Step 1: Write failing tests**

`packages/work-io/tests/unit/test_archive.py`:

```python
from __future__ import annotations
from datetime import date, timedelta
from pathlib import Path
import pytest
from work_io.archive import plan_archive, TERMINAL_STATUSES


def _make_item(work_dir: Path, slug: str, status: str = "open",
               updated_days_ago: int = 0) -> None:
    opened = (date.today() - timedelta(days=updated_days_ago + 1)).isoformat()
    updated = (date.today() - timedelta(days=updated_days_ago)).isoformat()
    content = f"---\ntitle: {slug}\nstatus: {status}\nopened: {opened}\nupdated: {updated}\n---\n"
    (work_dir / f"{opened}-{slug}.md").write_text(content)


def test_sweep_mode_archives_terminal_aged_items(tmp_path: Path) -> None:
    work_dir = tmp_path
    _make_item(work_dir, "resolved-old", status="resolved", updated_days_ago=10)
    _make_item(work_dir, "open-item", status="open", updated_days_ago=10)

    plan = plan_archive(work_dir)

    assert len(plan.actions) == 1
    assert plan.actions[0].slug.endswith("resolved-old")
    assert len(plan.skipped) == 1
    assert plan.skipped[0]["slug"].endswith("open-item")


def test_sweep_mode_skips_terminal_under_min_age(tmp_path: Path) -> None:
    work_dir = tmp_path
    _make_item(work_dir, "resolved-new", status="resolved", updated_days_ago=3)

    plan = plan_archive(work_dir, min_age_days=7)

    assert len(plan.actions) == 0
    assert any("only 3 days old" in s["reason"] for s in plan.skipped)


def test_targeted_mode_bypasses_age_check(tmp_path: Path) -> None:
    work_dir = tmp_path
    _make_item(work_dir, "resolved-new", status="resolved", updated_days_ago=1)
    # Find the actual filename stem
    stems = [f.stem for f in work_dir.glob("*.md")]

    plan = plan_archive(work_dir, slugs=stems)

    assert len(plan.actions) == 1


def test_targeted_mode_non_terminal_goes_to_skipped(tmp_path: Path) -> None:
    work_dir = tmp_path
    _make_item(work_dir, "open-item", status="open", updated_days_ago=30)
    stems = [f.stem for f in work_dir.glob("*.md")]

    plan = plan_archive(work_dir, slugs=stems)

    assert len(plan.actions) == 0
    assert any("not terminal" in s["reason"] for s in plan.skipped)


def test_targeted_mode_missing_slug_goes_to_skipped(tmp_path: Path) -> None:
    work_dir = tmp_path

    plan = plan_archive(work_dir, slugs=["2026-01-01-nonexistent"])

    assert len(plan.actions) == 0
    assert plan.skipped[0]["slug"] == "2026-01-01-nonexistent"
    assert "not found" in plan.skipped[0]["reason"]


def test_archive_dst_is_archived_subdir(tmp_path: Path) -> None:
    work_dir = tmp_path
    _make_item(work_dir, "wontfix-item", status="wontfix", updated_days_ago=8)

    plan = plan_archive(work_dir)

    assert len(plan.actions) == 1
    assert plan.actions[0].dst.parent.name == "archived"
    assert plan.actions[0].dst.name == plan.actions[0].src.name


def test_all_terminal_statuses_eligible(tmp_path: Path) -> None:
    work_dir = tmp_path
    for status in TERMINAL_STATUSES:
        _make_item(work_dir, f"item-{status}", status=status, updated_days_ago=10)

    plan = plan_archive(work_dir)
    assert len(plan.actions) == len(TERMINAL_STATUSES)
```

- [ ] **Step 2: Run to verify tests fail**

```bash
uv run --package work-io pytest tests/unit/test_archive.py -v
```

Expected: `ModuleNotFoundError: No module named 'work_io.archive'`

- [ ] **Step 3: Implement archive.py**

`packages/work-io/src/work_io/archive.py`:

```python
"""Plan archiving of terminal work items."""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from pathlib import Path

TERMINAL_STATUSES = frozenset({"resolved", "wontfix", "superseded"})


@dataclass
class ArchiveAction:
    slug: str
    src: Path
    dst: Path


@dataclass
class ArchivePlan:
    actions: list[ArchiveAction] = field(default_factory=list)
    skipped: list[dict] = field(default_factory=list)


def plan_archive(
    work_dir: Path,
    slugs: list[str] | None = None,
    min_age_days: int = 7,
) -> ArchivePlan:
    """Plan archiving of terminal work items.

    Sweep mode (slugs=None): all terminal items aged ≥ min_age_days.
    Targeted mode (slugs provided): named items, age check bypassed; non-terminal skipped.
    """
    from work_io.frontmatter import parse as fm_parse

    archived_dir = work_dir / "archived"
    actions: list[ArchiveAction] = []
    skipped: list[dict] = []

    candidates = list(work_dir.glob("*.md"))

    if slugs is not None:
        slug_set = set(slugs)
        found_stems = {f.stem: f for f in candidates}
        candidates = [found_stems[s] for s in slug_set if s in found_stems]
        for s in slug_set:
            if s not in found_stems:
                skipped.append({"slug": s, "reason": "not found in work/"})

    for md in candidates:
        slug = md.stem
        try:
            fm, _ = fm_parse(md.read_text(encoding="utf-8"))
        except Exception as e:
            skipped.append({"slug": slug, "reason": f"parse error: {e}"})
            continue

        status = str(fm.get("status", ""))
        if status not in TERMINAL_STATUSES:
            skipped.append({"slug": slug, "reason": f"status={status!r} is not terminal"})
            continue

        if slugs is None:
            updated = str(fm.get("updated", fm.get("opened", "")))
            age = _days_since(updated)
            if age < min_age_days:
                skipped.append({"slug": slug, "reason": f"only {age} days old (min {min_age_days})"})
                continue

        actions.append(ArchiveAction(slug=slug, src=md, dst=archived_dir / md.name))

    return ArchivePlan(actions=actions, skipped=skipped)


def _days_since(date_str: str) -> int:
    try:
        dt = date.fromisoformat(date_str[:10])
        return (date.today() - dt).days
    except (ValueError, TypeError):
        return 0
```

- [ ] **Step 4: Run to verify tests pass**

```bash
uv run --package work-io pytest tests/unit/test_archive.py -v
```

Expected: all 7 tests PASS.

- [ ] **Step 5: Run full work-io suite**

```bash
uv run --package work-io pytest -v
```

Expected: all tests PASS.

- [ ] **Step 6: Commit**

```bash
git add packages/work-io/
git commit -m "feat(work-io): archive planner; complete work-io package"
```

---

## Task 7: graph-wiki-core/commands/work.py + pyproject.toml

**Files:**
- Modify: `packages/graph-wiki-core/pyproject.toml`
- Create: `packages/graph-wiki-core/src/graph_wiki_core/commands/work.py`
- Create: `packages/graph-wiki-core/tests/unit/test_commands_work.py`

- [ ] **Step 1: Add work-io dependency to graph-wiki-core**

Edit `packages/graph-wiki-core/pyproject.toml` — add `"work-io"` to the `dependencies` list (alongside `"wiki-io"`, `"graph-io"`, etc.) and add `work-io = { workspace = true }` under `[tool.uv.sources]`.

```toml
# In [project] dependencies list, add:
"work-io",

# In [tool.uv.sources], add:
work-io = { workspace = true }
```

Then run:

```bash
uv sync
```

- [ ] **Step 2: Write failing tests**

`packages/graph-wiki-core/tests/unit/test_commands_work.py`:

```python
from __future__ import annotations
import dataclasses
import json
from datetime import date, timedelta
from pathlib import Path
import pytest


def _make_workspace(tmp_path: Path) -> tuple[Path, Path]:
    """Return (workspace, wiki). Creates wiki/work/ structure."""
    workspace = tmp_path / "ws"
    wiki = workspace / "wiki"
    work_dir = wiki / "work"
    work_dir.mkdir(parents=True)
    return workspace, wiki


def _write_item(work_dir: Path, slug: str, status: str = "open", kind: str = "bug",
                updated_days_ago: int = 0, **extra_fm) -> None:
    opened = (date.today() - timedelta(days=updated_days_ago + 1)).isoformat()
    updated = (date.today() - timedelta(days=updated_days_ago)).isoformat()
    fm_lines = [
        "---",
        f"title: {slug}",
        f"status: {status}",
        f"kind: {kind}",
        f"opened: {opened}",
        f"updated: {updated}",
    ]
    for k, v in extra_fm.items():
        fm_lines.append(f"{k}: {v}")
    fm_lines += ["---", "", "## Summary", "content", ""]
    (work_dir / f"{opened}-{slug}.md").write_text("\n".join(fm_lines))


def test_run_work_regen_index_creates_sidecar(tmp_path: Path) -> None:
    import asyncio
    from graph_wiki_core.commands.work import run_work_regen_index

    workspace, wiki = _make_workspace(tmp_path)
    work_dir = wiki / "work"
    _write_item(work_dir, "bug-1", status="open")

    result = asyncio.run(run_work_regen_index(workspace_path=workspace))

    assert result.item_count == 1
    assert (wiki / "work-index.json").exists()


def test_run_work_regen_index_idempotent(tmp_path: Path) -> None:
    import asyncio
    from graph_wiki_core.commands.work import run_work_regen_index

    workspace, wiki = _make_workspace(tmp_path)
    work_dir = wiki / "work"
    _write_item(work_dir, "bug-1")

    asyncio.run(run_work_regen_index(workspace_path=workspace))
    result = asyncio.run(run_work_regen_index(workspace_path=workspace))

    assert result.item_count == 1


def test_run_work_lint_returns_findings(tmp_path: Path) -> None:
    import asyncio
    from graph_wiki_core.commands.work import run_work_lint

    workspace, wiki = _make_workspace(tmp_path)
    work_dir = wiki / "work"
    _write_item(work_dir, "bad-item", status="open", updated_days_ago=40)

    result = asyncio.run(run_work_lint(workspace_path=workspace))

    assert result.total_items == 1
    rule_ids = {f["rule_id"] for f in result.findings}
    assert "stuck-open" in rule_ids
    assert "sidecar-missing" in rule_ids


def test_run_work_status_missing_sidecar(tmp_path: Path) -> None:
    import asyncio
    from graph_wiki_core.commands.work import run_work_status

    workspace, wiki = _make_workspace(tmp_path)

    result = asyncio.run(run_work_status(workspace_path=workspace))

    assert result.sidecar_missing is True


def test_run_work_status_with_sidecar(tmp_path: Path) -> None:
    import asyncio
    from graph_wiki_core.commands.work import run_work_regen_index, run_work_status

    workspace, wiki = _make_workspace(tmp_path)
    work_dir = wiki / "work"
    _write_item(work_dir, "in-prog", status="in-progress", owner="pat")
    _write_item(work_dir, "stuck", status="open", updated_days_ago=35)

    asyncio.run(run_work_regen_index(workspace_path=workspace))
    result = asyncio.run(run_work_status(workspace_path=workspace))

    assert result.sidecar_missing is False
    assert len(result.in_flight) == 1
    assert len(result.stuck) >= 1


def test_run_work_archive_dry_run(tmp_path: Path) -> None:
    import asyncio
    from graph_wiki_core.commands.work import run_work_archive

    workspace, wiki = _make_workspace(tmp_path)
    work_dir = wiki / "work"
    _write_item(work_dir, "resolved-item", status="resolved", updated_days_ago=10,
                resolved_in="pr#1")

    result = asyncio.run(run_work_archive(workspace_path=workspace, dry_run=True))

    assert result.dry_run is True
    assert len(result.moved) == 1
    assert not (wiki / "work" / "archived").exists()


def test_run_work_archive_executes_move(tmp_path: Path) -> None:
    import asyncio
    from graph_wiki_core.commands.work import run_work_archive

    workspace, wiki = _make_workspace(tmp_path)
    work_dir = wiki / "work"
    _write_item(work_dir, "resolved-item", status="resolved", updated_days_ago=10,
                resolved_in="pr#1")

    result = asyncio.run(run_work_archive(workspace_path=workspace, dry_run=False))

    assert len(result.moved) == 1
    assert (work_dir / "archived").exists()


def test_run_work_file_returns_ingest_result(tmp_path: Path) -> None:
    import asyncio
    from graph_wiki_core.commands.work import run_work_file

    workspace, wiki = _make_workspace(tmp_path)

    result = asyncio.run(run_work_file(
        workspace_path=workspace,
        title="Test bug",
        kind="bug",
        summary="Something is broken",
        affects=["packages/foo"],
    ))

    assert result.status == "ok"
    assert "work" in result.page_path


def test_work_result_dataclasses_importable() -> None:
    from graph_wiki_core.commands.work import (
        WorkLintResult, WorkArchiveResult, WorkStatusResult, WorkRegenResult,
    )
    assert dataclasses.is_dataclass(WorkLintResult)
    assert dataclasses.is_dataclass(WorkArchiveResult)
    assert dataclasses.is_dataclass(WorkStatusResult)
    assert dataclasses.is_dataclass(WorkRegenResult)
```

- [ ] **Step 3: Run to verify tests fail**

```bash
uv run --package graph-wiki-core pytest tests/unit/test_commands_work.py -v
```

Expected: `ModuleNotFoundError: No module named 'graph_wiki_core.commands.work'`

- [ ] **Step 4: Implement commands/work.py**

`packages/graph-wiki-core/src/graph_wiki_core/commands/work.py`:

```python
"""Work-layer orchestration: wires work-io logic with wiki-io I/O side-effects."""
from __future__ import annotations

import subprocess
from dataclasses import dataclass, field
from datetime import date, timedelta
from pathlib import Path

from wiki_io._workspace import resolve_wiki_and_repo
from wiki_io.ingest_work_item import file_work_item
from workspace_io.paths import work_dir as _work_dir


@dataclass
class WorkLintResult:
    wiki: str
    total_items: int
    findings: list[dict] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)


@dataclass
class WorkArchiveResult:
    wiki: str
    moved: list[str] = field(default_factory=list)
    skipped: list[dict] = field(default_factory=list)
    referrers: list[str] = field(default_factory=list)
    dry_run: bool = False


@dataclass
class WorkStatusResult:
    wiki: str
    counts: dict = field(default_factory=dict)
    in_flight: list[dict] = field(default_factory=list)
    stuck: list[dict] = field(default_factory=list)
    sidecar_stale: bool = False
    sidecar_missing: bool = False


@dataclass
class WorkRegenResult:
    wiki: str
    item_count: int
    sidecar_path: str


async def run_work_lint(workspace_path: Path | None = None) -> WorkLintResult:
    """Parse work items, run all 19 lifecycle rules, return findings."""
    from work_io.frontmatter import parse as fm_parse
    from work_io.lifecycle_lint import run_lint
    from work_io.plan_table import parse_plan
    from work_io.sidecar import load_sidecar

    wiki, repo = resolve_wiki_and_repo(workspace_path)
    workspace = wiki.parent
    work_d = _work_dir(workspace)

    items = []
    errors = []
    if work_d.exists():
        for md in sorted(work_d.glob("*.md")):
            try:
                fm, body = fm_parse(md.read_text(encoding="utf-8"))
                plan = parse_plan(body)
                items.append({"slug": md.stem, "fm": fm, "plan": plan})
            except Exception as e:
                errors.append(f"{md.name}: {e}")

    sidecar = load_sidecar(wiki)
    findings = run_lint(items, repo, sidecar)

    return WorkLintResult(
        wiki=str(wiki),
        total_items=len(items),
        findings=[{"rule_id": f.rule_id, "severity": f.severity,
                   "slug": f.slug, "message": f.message} for f in findings],
        errors=errors,
    )


async def run_work_archive(
    workspace_path: Path | None = None,
    slugs: list[str] | None = None,
    dry_run: bool = False,
    min_age_days: int = 7,
) -> WorkArchiveResult:
    """Plan and optionally execute archiving of terminal work items."""
    from work_io.archive import plan_archive

    wiki, _ = resolve_wiki_and_repo(workspace_path)
    workspace = wiki.parent
    work_d = _work_dir(workspace)

    plan = plan_archive(work_d, slugs, min_age_days)

    slugs_to_move = {a.slug for a in plan.actions}
    referrers: list[str] = []
    for md in wiki.rglob("*.md"):
        rel = md.relative_to(wiki)
        if any(p.startswith(".") for p in rel.parts):
            continue
        text = md.read_text(encoding="utf-8")
        for slug in slugs_to_move:
            if f"[[work/{slug}" in text:
                referrers.append(str(rel))
                break

    moved: list[str] = []
    if not dry_run and plan.actions:
        (work_d / "archived").mkdir(parents=True, exist_ok=True)
        for action in plan.actions:
            _git_mv(action.src, action.dst)
            moved.append(str(action.src.relative_to(workspace)))
        await run_work_regen_index(workspace_path)
    elif dry_run:
        moved = [str(a.src.relative_to(workspace)) for a in plan.actions]

    return WorkArchiveResult(
        wiki=str(wiki),
        moved=moved,
        skipped=plan.skipped,
        referrers=referrers,
        dry_run=dry_run,
    )


async def run_work_status(workspace_path: Path | None = None) -> WorkStatusResult:
    """Load sidecar and compute in-flight and stuck items."""
    from work_io.sidecar import is_stale, load_sidecar

    wiki, _ = resolve_wiki_and_repo(workspace_path)
    workspace = wiki.parent
    work_d = _work_dir(workspace)

    sidecar = load_sidecar(wiki)
    if sidecar is None:
        return WorkStatusResult(wiki=str(wiki), sidecar_missing=True)

    items = sidecar.get("items", [])
    today = date.today()

    in_flight = [i for i in items if i.get("status") == "in-progress"]

    stuck = []
    for item in items:
        status = item.get("status", "")
        updated_str = str(item.get("updated", ""))[:10]
        try:
            updated_date = date.fromisoformat(updated_str)
            age = (today - updated_date).days
        except ValueError:
            continue
        if status == "open" and age > 30:
            stuck.append({**item, "_age_days": age})
        elif status == "accepted" and age > 60:
            stuck.append({**item, "_age_days": age})

    stale = is_stale(sidecar, work_d) if work_d.exists() else False

    return WorkStatusResult(
        wiki=str(wiki),
        counts=sidecar.get("counts", {}),
        in_flight=in_flight,
        stuck=stuck,
        sidecar_stale=stale,
        sidecar_missing=False,
    )


async def run_work_regen_index(workspace_path: Path | None = None) -> WorkRegenResult:
    """Rebuild work-index.json from current wiki/work/*.md state."""
    from work_io.sidecar import build_sidecar, write_sidecar

    wiki, _ = resolve_wiki_and_repo(workspace_path)
    workspace = wiki.parent
    work_d = _work_dir(workspace)

    vault_commit = _git_head(workspace)
    sidecar = build_sidecar(work_d, vault_commit)
    write_sidecar(wiki, sidecar)

    return WorkRegenResult(
        wiki=str(wiki),
        item_count=len(sidecar["items"]),
        sidecar_path=str(wiki / "work-index.json"),
    )


async def run_work_file(
    workspace_path: Path | None = None,
    title: str = "",
    kind: str = "",
    summary: str = "",
    affects: list[str] | None = None,
    effort: str | None = None,
    blast_radius: str | None = None,
    target: str | None = None,
    owner: str | None = None,
    tags: list[str] | None = None,
) -> object:
    """File a new work item and return IngestResult."""
    from graph_wiki_core.commands.ingest import run_ingest_work_item

    opened = date.today().isoformat()
    fm_lines = [
        f"title: {title}",
        f"category: work",
        f"kind: {kind}",
        f"summary: {summary}",
        f"status: open",
        f"opened: {opened}",
        f"updated: {opened}",
        f"affects: {affects or []}",
        f"tokens: 0",
    ]
    if effort:
        fm_lines.append(f"effort: {effort}")
    if blast_radius:
        fm_lines.append(f"blast_radius: {blast_radius}")
    if target:
        fm_lines.append(f"target: {target}")
    if owner:
        fm_lines.append(f"owner: {owner}")
    if tags:
        fm_lines.append(f"tags: {tags}")

    body = (
        "## Summary\n"
        f"{summary}\n\n"
        "## Options considered\n\n"
        "## Plan\n\n"
        "| Action | Done when | Rationale |\n"
        "|---|---|---|\n"
        "| | | |\n\n"
        "## Notes / log\n"
    )

    return await run_ingest_work_item(
        frontmatter_text="\n".join(fm_lines),
        body=body,
        workspace_path=workspace_path,
    )


def _git_mv(src: Path, dst: Path) -> None:
    """Move src to dst via git mv; fall back to os.rename on failure."""
    result = subprocess.run(["git", "mv", str(src), str(dst)], capture_output=True)
    if result.returncode != 0:
        src.rename(dst)


def _git_head(workspace: Path) -> str | None:
    """Return current git HEAD SHA, or None if not in a git repo."""
    result = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        capture_output=True, text=True, cwd=workspace,
    )
    return result.stdout.strip() or None if result.returncode == 0 else None
```

- [ ] **Step 5: Run tests to verify they pass**

```bash
uv run --package graph-wiki-core pytest tests/unit/test_commands_work.py -v
```

Expected: all 8 tests PASS.

- [ ] **Step 6: Commit**

```bash
git add packages/graph-wiki-core/
git commit -m "feat(core): work command orchestration layer"
```

---

## Task 8: gw work CLI subapp

**Files:**
- Modify: `packages/graph-wiki-cli/pyproject.toml`
- Create: `packages/graph-wiki-cli/src/graph_wiki_cli/work_cli/__init__.py`
- Create: `packages/graph-wiki-cli/src/graph_wiki_cli/work_cli/main.py`
- Modify: `packages/graph-wiki-cli/src/graph_wiki_cli/cli.py`
- Create: `packages/graph-wiki-cli/tests/unit/test_work_cli.py`

- [ ] **Step 1: Add work-io dependency to graph-wiki-cli pyproject.toml**

Edit `packages/graph-wiki-cli/pyproject.toml`:

```toml
# In [project] dependencies, add:
"work-io",

# In [tool.uv.sources], add:
work-io = { workspace = true }
```

Run `uv sync`.

- [ ] **Step 2: Write failing tests**

`packages/graph-wiki-cli/tests/unit/test_work_cli.py`:

```python
from __future__ import annotations
import dataclasses
import json
from datetime import date, timedelta
from pathlib import Path
from unittest.mock import AsyncMock, patch

import typer
from typer.testing import CliRunner

runner = CliRunner()


def test_work_app_registered_under_gw() -> None:
    import typer
    from graph_wiki_cli.cli import app

    root_command = typer.main.get_command(app)
    assert "work" in root_command.commands


def test_work_subcommands_exist() -> None:
    import typer
    from graph_wiki_cli.cli import app

    root_command = typer.main.get_command(app)
    work_group = root_command.commands["work"]
    assert {"file", "lint", "archive", "status", "regen-index"} <= set(work_group.commands)


def test_work_lint_json_exit_0_when_clean(tmp_path: Path) -> None:
    from graph_wiki_cli.cli import app
    from graph_wiki_core.commands.work import WorkLintResult

    mock_result = WorkLintResult(wiki=str(tmp_path), total_items=0, findings=[], errors=[])

    with patch("graph_wiki_cli.work_cli.main.run_work_lint", new=AsyncMock(return_value=mock_result)):
        result = runner.invoke(app, ["work", "lint", "--json"])

    assert result.exit_code == 0
    data = json.loads(result.output)
    assert data["findings"] == []


def test_work_lint_exit_1_when_error_severity(tmp_path: Path) -> None:
    from graph_wiki_cli.cli import app
    from graph_wiki_core.commands.work import WorkLintResult

    mock_result = WorkLintResult(
        wiki=str(tmp_path), total_items=1,
        findings=[{"rule_id": "status-not-in-enum", "severity": "error",
                   "slug": "foo", "message": "bad status"}],
        errors=[],
    )

    with patch("graph_wiki_cli.work_cli.main.run_work_lint", new=AsyncMock(return_value=mock_result)):
        result = runner.invoke(app, ["work", "lint", "--json"])

    assert result.exit_code == 1


def test_work_status_exit_4_when_sidecar_missing(tmp_path: Path) -> None:
    from graph_wiki_cli.cli import app
    from graph_wiki_core.commands.work import WorkStatusResult

    mock_result = WorkStatusResult(wiki=str(tmp_path), sidecar_missing=True)

    with patch("graph_wiki_cli.work_cli.main.run_work_status", new=AsyncMock(return_value=mock_result)):
        result = runner.invoke(app, ["work", "status", "--json"])

    assert result.exit_code == 4


def test_work_regen_index_exit_0(tmp_path: Path) -> None:
    from graph_wiki_cli.cli import app
    from graph_wiki_core.commands.work import WorkRegenResult

    mock_result = WorkRegenResult(wiki=str(tmp_path), item_count=2,
                                  sidecar_path=str(tmp_path / "work-index.json"))

    with patch("graph_wiki_cli.work_cli.main.run_work_regen_index", new=AsyncMock(return_value=mock_result)):
        result = runner.invoke(app, ["work", "regen-index", "--json"])

    assert result.exit_code == 0
```

- [ ] **Step 3: Run to verify tests fail**

```bash
uv run --package graph-wiki-cli pytest tests/unit/test_work_cli.py -v
```

Expected: `AssertionError: assert 'work' in ...` (work not registered yet)

- [ ] **Step 4: Create work_cli package**

`packages/graph-wiki-cli/src/graph_wiki_cli/work_cli/__init__.py` — empty file.

- [ ] **Step 5: Implement work_cli/main.py**

`packages/graph-wiki-cli/src/graph_wiki_cli/work_cli/main.py`:

```python
"""gw work — work item management commands."""
from __future__ import annotations

import asyncio
import dataclasses
import json
from pathlib import Path
from typing import Optional

import typer

from graph_wiki_core.commands.work import (
    run_work_archive,
    run_work_file,
    run_work_lint,
    run_work_regen_index,
    run_work_status,
)

work_app = typer.Typer(name="work", help="Work item management.", no_args_is_help=True)


@work_app.command()
def file(
    title: str = typer.Option(..., "--title", help="Work item title"),
    kind: str = typer.Option(..., "--kind", help="bug|tech-debt|test-gap|security|perf|feature|initiative|spike"),
    summary: str = typer.Option(..., "--summary", help="One-line summary (≤100 chars)"),
    affects: str = typer.Option(..., "--affects", help="Comma-separated paths/packages"),
    effort: Optional[str] = typer.Option(None, "--effort", help="trivial|small|medium|large"),
    blast_radius: Optional[str] = typer.Option(None, "--blast-radius", help="file|package|domain|system"),
    target: Optional[str] = typer.Option(None, "--target", help="YYYY-QN or YYYY-MM"),
    owner: Optional[str] = typer.Option(None, "--owner"),
    tags: Optional[str] = typer.Option(None, "--tags", help="Comma-separated tags"),
    workspace: str = typer.Option("", "--workspace", help="Workspace path"),
    json_output: bool = typer.Option(False, "--json"),
) -> None:
    """File a new work item into the wiki."""
    workspace_path = Path(workspace) if workspace else None
    affects_list = [a.strip() for a in affects.split(",") if a.strip()]
    tags_list = [t.strip() for t in tags.split(",") if t.strip()] if tags else None

    try:
        result = asyncio.run(run_work_file(
            workspace_path=workspace_path,
            title=title, kind=kind, summary=summary,
            affects=affects_list, effort=effort,
            blast_radius=blast_radius, target=target,
            owner=owner, tags=tags_list,
        ))
    except (RuntimeError, ValueError) as e:
        typer.echo(f"Error: {e}", err=True)
        raise typer.Exit(code=2)

    if json_output:
        typer.echo(json.dumps(dataclasses.asdict(result), indent=2))  # type: ignore[arg-type]
    else:
        typer.echo(f"[ok] Filed: {result.page_path}")  # type: ignore[attr-defined]


@work_app.command()
def lint(
    workspace: str = typer.Option("", "--workspace", help="Workspace path"),
    json_output: bool = typer.Option(False, "--json"),
) -> None:
    """Run lifecycle lint over all work items."""
    workspace_path = Path(workspace) if workspace else None
    try:
        result = asyncio.run(run_work_lint(workspace_path=workspace_path))
    except RuntimeError as e:
        typer.echo(f"Error: {e}", err=True)
        raise typer.Exit(code=3)

    if json_output:
        typer.echo(json.dumps(dataclasses.asdict(result), indent=2))
    else:
        typer.echo(f"Work lifecycle lint — {result.wiki}")
        typer.echo(f"Items checked: {result.total_items}")
        for f in result.findings:
            typer.echo(f"  [{f['severity']}] {f['slug']}: {f['rule_id']} — {f['message']}")
        if not result.findings:
            typer.echo("  [ok] No findings.")

    if any(f["severity"] == "error" for f in result.findings):
        raise typer.Exit(code=1)


@work_app.command()
def archive(
    slugs: Optional[list[str]] = typer.Argument(None, help="Specific slugs to archive"),
    dry_run: bool = typer.Option(False, "--dry-run", help="Show plan without moving files"),
    min_age_days: int = typer.Option(7, "--min-age-days"),
    workspace: str = typer.Option("", "--workspace", help="Workspace path"),
    json_output: bool = typer.Option(False, "--json"),
) -> None:
    """Archive terminal work items (sweep or targeted)."""
    workspace_path = Path(workspace) if workspace else None
    try:
        result = asyncio.run(run_work_archive(
            workspace_path=workspace_path,
            slugs=slugs or None,
            dry_run=dry_run,
            min_age_days=min_age_days,
        ))
    except RuntimeError as e:
        typer.echo(f"Error: {e}", err=True)
        raise typer.Exit(code=3)

    if json_output:
        typer.echo(json.dumps(dataclasses.asdict(result), indent=2))
    else:
        label = "[dry-run]" if dry_run else "[ok]"
        typer.echo(f"{label} Archived {len(result.moved)} item(s).")
        for path in result.moved:
            typer.echo(f"  moved: {path}")
        for skipped in result.skipped:
            typer.echo(f"  skipped: {skipped['slug']} — {skipped['reason']}")
        for ref in result.referrers:
            typer.echo(f"  warning: {ref} links to an archived item", err=True)


@work_app.command()
def status(
    workspace: str = typer.Option("", "--workspace", help="Workspace path"),
    json_output: bool = typer.Option(False, "--json"),
) -> None:
    """Show work item status rollup."""
    workspace_path = Path(workspace) if workspace else None
    try:
        result = asyncio.run(run_work_status(workspace_path=workspace_path))
    except RuntimeError as e:
        typer.echo(f"Error: {e}", err=True)
        raise typer.Exit(code=3)

    if json_output:
        typer.echo(json.dumps(dataclasses.asdict(result), indent=2))
    else:
        if result.sidecar_missing:
            typer.echo("[warn] work-index.json is missing. Run `gw work regen-index` first.", err=True)
            raise typer.Exit(code=4)
        typer.echo(f"Work status — {result.wiki}")
        for category, counts in result.counts.items():
            typer.echo(f"  {category}: {counts}")
        typer.echo(f"In-flight ({len(result.in_flight)}):")
        for item in result.in_flight:
            typer.echo(f"  - {item['slug']}: {item.get('title', '')}")
        typer.echo(f"Stuck ({len(result.stuck)}):")
        for item in result.stuck:
            typer.echo(f"  - {item['slug']}: {item.get('_age_days', '?')}d old")
        if result.sidecar_stale:
            typer.echo("[warn] Sidecar may be stale. Run `gw work regen-index`.", err=True)

    if result.sidecar_missing:
        raise typer.Exit(code=4)


@work_app.command(name="regen-index")
def regen_index(
    workspace: str = typer.Option("", "--workspace", help="Workspace path"),
    json_output: bool = typer.Option(False, "--json"),
) -> None:
    """Rebuild work-index.json from wiki/work/*.md."""
    workspace_path = Path(workspace) if workspace else None
    try:
        result = asyncio.run(run_work_regen_index(workspace_path=workspace_path))
    except RuntimeError as e:
        typer.echo(f"Error: {e}", err=True)
        raise typer.Exit(code=3)

    if json_output:
        typer.echo(json.dumps(dataclasses.asdict(result), indent=2))
    else:
        typer.echo(f"[ok] Rebuilt sidecar: {result.sidecar_path} ({result.item_count} items)")
```

- [ ] **Step 6: Register work_app in cli.py**

Edit `packages/graph-wiki-cli/src/graph_wiki_cli/cli.py`. After the existing import block (near the line `from graph_wiki_cli.wiki_cli.main import wiki_app`), add:

```python
from graph_wiki_cli.work_cli.main import work_app  # noqa: E402
```

And at the bottom where `app.add_typer(wiki_app, name="wiki")` appears, add:

```python
# work command namespace: work item lifecycle management.
app.add_typer(work_app, name="work")
```

- [ ] **Step 7: Run tests to verify they pass**

```bash
uv run --package graph-wiki-cli pytest tests/unit/test_work_cli.py -v
```

Expected: all 5 tests PASS.

- [ ] **Step 8: Smoke test the CLI**

```bash
uv run --package graph-wiki-cli gw work --help
```

Expected: shows `file`, `lint`, `archive`, `status`, `regen-index` subcommands.

- [ ] **Step 9: Commit**

```bash
git add packages/graph-wiki-cli/
git commit -m "feat(cli): gw work subapp — file/lint/archive/status/regen-index"
```

---

## Task 9: Integrate work-layer lint into gw wiki lint

**Files:**
- Modify: `packages/graph-wiki-core/src/graph_wiki_core/commands/lint.py`
- Modify: `packages/graph-wiki-cli/src/graph_wiki_cli/wiki_cli/main.py`

- [ ] **Step 1: Add work_lint_findings to LintResult**

In `packages/graph-wiki-core/src/graph_wiki_core/commands/lint.py`, find the `LintResult` dataclass (line ~82) and add a new field after `open_proposals`:

```python
work_lint_findings: list[dict] = field(default_factory=list)
```

The updated end of the dataclass looks like:

```python
    semantic_findings: dict[str, list[str]] = field(default_factory=dict)
    errors: list[str] = field(default_factory=list)
    open_proposals: int = 0
    work_lint_findings: list[dict] = field(default_factory=list)
```

- [ ] **Step 2: Call run_work_lint in run_lint**

In `run_lint()`, `errors` is assigned by `_semantic_pass` on the line before `return LintResult(...)`. Insert the work-lint block between `_semantic_pass` and `return LintResult(...)` (around line 519):

```python
    # Work-layer lifecycle lint (after semantic pass so errors list exists)
    from graph_wiki_core.commands.work import run_work_lint as _run_work_lint
    work_lint = await _run_work_lint(workspace_path)
    work_findings = work_lint.findings
    for f in work_findings:
        if f["severity"] == "error":
            errors.append(f"{f['slug']}: [{f['rule_id']}] {f['message']}")
```

Then add `work_lint_findings=work_findings` to the `return LintResult(...)` call.

The updated `return LintResult(...)` block:

```python
    return LintResult(
        wiki=str(wiki),
        total_pages=mech["total_pages"],
        orphans=mech["orphans"],
        broken_links=mech["broken_links"],
        stale=mech["stale"],
        missing_frontmatter=mech["missing_frontmatter"],
        duplicate_titles=mech["duplicate_titles"],
        log_gap=mech["log_gap"],
        code_drift=mod["code_drift"],
        file_map_drift=mod["file_map_drift"],
        package_sync_drift=mod["package_sync_drift"],
        domain_placement=mod["domain_placement"],
        workflow_hints=mod["workflow_hints"],
        dependency_layer=mod["dependency_layer"],
        scanner_heading_drift=mod["scanner_heading_drift"],
        semantic_findings=semantic_findings,
        errors=errors,
        open_proposals=open_proposals,
        work_lint_findings=work_findings,
    )
```

- [ ] **Step 3: Verify no test regressions in graph-wiki-core**

```bash
uv run --package graph-wiki-core pytest tests/unit/test_commands_lint.py -v -m "not integration"
```

Expected: PASS (the existing shape test may need updating — see Step 4).

- [ ] **Step 4: Update LintResult shape test if needed**

The existing test `test_lint_result_dataclass_shape` in `tests/unit/test_commands_lint.py` checks `required_fields`. Add `"work_lint_findings"` to that set:

```python
required_fields = {
    "wiki",
    "total_pages",
    ...
    "open_proposals",
    "work_lint_findings",   # add this line
}
```

Run again:

```bash
uv run --package graph-wiki-core pytest tests/unit/test_commands_lint.py -v -m "not integration"
```

Expected: PASS.

- [ ] **Step 5: Add Work lifecycle section to CLI lint output**

In `packages/graph-wiki-cli/src/graph_wiki_cli/wiki_cli/main.py`, find the lint output section (around line 160) where `_section("Scanner heading drift", result.scanner_heading_drift)` appears. After that line, add:

```python
        if result.work_lint_findings:
            work_items = [
                f"[{f['severity']}] {f['slug']}: {f['rule_id']} — {f['message']}"
                for f in result.work_lint_findings
            ]
            _section("Work lifecycle", work_items)
        else:
            typer.echo("[OK] Work lifecycle: 0\n")
```

- [ ] **Step 6: Verify CLI lint tests still pass**

```bash
uv run --package graph-wiki-cli pytest tests/unit/test_wiki_cli.py tests/unit/test_work_cli.py -v
```

Expected: PASS.

- [ ] **Step 7: Commit**

```bash
git add packages/graph-wiki-core/ packages/graph-wiki-cli/
git commit -m "feat: integrate work-layer lifecycle lint into gw wiki lint"
```

---

## Task 10: Four plugin command files

**Files:**
- Create: `plugins/graph-wiki/commands/file.md`
- Create: `plugins/graph-wiki/commands/archive.md`
- Create: `plugins/graph-wiki/commands/status.md`
- Create: `plugins/graph-wiki/commands/regen-index.md`

- [ ] **Step 1: Create file.md**

`plugins/graph-wiki/commands/file.md`:

```markdown
---
name: file
description: Interactively file a new work item into the wiki — gathers title, kind, summary, and affects conversationally, then invokes `gw work file` with the assembled values. Usage /graph-wiki:file
---

# /graph-wiki:file

Interactively create a new work item in `wiki/work/`.

## Usage

```
/graph-wiki:file
```

Gathers required fields conversationally, then invokes `gw work file`.

## What happens

1. Prompt for **title** (required) — a short description of the issue or feature.
2. Prompt for **kind** (required) — one of: `bug`, `tech-debt`, `test-gap`, `security`, `perf`, `feature`, `initiative`, `spike`.
3. Prompt for **summary** (required) — one line, ≤100 chars.
4. Prompt for **affects** (required) — comma-separated paths or package names (e.g. `packages/graph-io, packages/wiki-io`).
5. Optionally prompt for: `effort` (trivial|small|medium|large), `blast-radius` (file|package|domain|system), `target` (YYYY-QN or YYYY-MM), `owner`, `tags`.
6. Auto-sets `status: open` and `opened: <today>`.
7. Invoke:

```bash
gw work file \
  --title "..." \
  --kind "..." \
  --summary "..." \
  --affects "..." \
  [--effort ...] [--blast-radius ...] [--target ...] [--owner ...] [--tags ...]
```

8. Report the filed page path.

## Skill Reference

→ `graph-wiki/SKILL.md`
→ `graph-wiki/references/wiki-schema.md`
→ `graph-wiki/references/lifecycle-rules.md`
```

- [ ] **Step 2: Create archive.md**

`plugins/graph-wiki/commands/archive.md`:

```markdown
---
name: archive
description: Archive terminal-status work items (resolved/wontfix/superseded) — sweep mode by default, or target specific slugs. Presents the plan and asks for confirmation before executing. Invokes `gw work archive`. Usage /graph-wiki:archive [slug...]
---

# /graph-wiki:archive

Move terminal work items from `wiki/work/` to `wiki/work/archived/`.

## Usage

```
/graph-wiki:archive
/graph-wiki:archive 2026-01-15-fix-parser-bug 2026-02-03-drop-old-api
```

Without arguments: sweep mode — all terminal-status items aged ≥7 days.
With slug arguments: targeted mode — those items only, age check bypassed.

## What happens

1. Run `gw work archive --dry-run [SLUGS...]` to build the plan.
2. Present the plan: items to move, items skipped (with reasons), any wikilink referrers that will become broken.
3. Ask for confirmation before executing.
4. On confirmation, run `gw work archive [SLUGS...]` (without `--dry-run`).
5. Report moved items and regenerated sidecar.

Terminal statuses: `resolved`, `wontfix`, `superseded`.

## Skill Reference

→ `graph-wiki/SKILL.md`
→ `graph-wiki/references/lifecycle-rules.md`
```

- [ ] **Step 3: Create status.md**

`plugins/graph-wiki/commands/status.md`:

```markdown
---
name: status
description: Show a one-screen work item rollup — counts by status/kind, in-flight items, stuck items. Hints to run regen-index when the sidecar is missing or stale. Invokes `gw work status`. Usage /graph-wiki:status
---

# /graph-wiki:status

One-screen work item rollup from the `work-index.json` sidecar.

## Usage

```
/graph-wiki:status
```

## What happens

1. Run `gw work status --json`.
2. If the sidecar is missing, suggest running `/graph-wiki:regen-index` first.
3. Present:
   - Counts by status, kind, severity, blast-radius.
   - In-flight items (status: in-progress) with titles.
   - Stuck items (open >30d or accepted >60d) with age.
   - A staleness hint if the sidecar is out of date.

## Skill Reference

→ `graph-wiki/SKILL.md`
→ `graph-wiki/references/sidecar-schema.md`
```

- [ ] **Step 4: Create regen-index.md**

`plugins/graph-wiki/commands/regen-index.md`:

```markdown
---
name: regen-index
description: Rebuild wiki/work-index.json from the current wiki/work/*.md state. Run after filing or archiving work items, or when `gw work status` reports a missing sidecar. Invokes `gw work regen-index`. Usage /graph-wiki:regen-index
---

# /graph-wiki:regen-index

Rebuild `wiki/work-index.json` from current `wiki/work/*.md` state.

## Usage

```
/graph-wiki:regen-index
```

## What happens

1. Run `gw work regen-index --json`.
2. Report the item count and sidecar path.

Run this after:
- Filing new work items via means other than `gw work file`.
- Manually editing work item frontmatter.
- Archiving items if the auto-regen didn't fire.

## Skill Reference

→ `graph-wiki/SKILL.md`
→ `graph-wiki/references/sidecar-schema.md`
```

- [ ] **Step 5: Commit**

```bash
git add plugins/graph-wiki/commands/
git commit -m "feat(plugin): file/archive/status/regen-index plugin commands"
```

---

## Task 11: Update plugins/graph-wiki/commands/lint.md

**Files:**
- Modify: `plugins/graph-wiki/commands/lint.md`

- [ ] **Step 1: Add work-layer note**

In `plugins/graph-wiki/commands/lint.md`, inside the `### Pass 1 — Mechanical (scripts)` section, add after the existing bullet points:

```markdown
- Work lifecycle — all 19 rules from `lifecycle-rules.md` run against every `wiki/work/*.md` file. Findings appear under a **Work lifecycle** section in the output.
```

Also update the description in the frontmatter to mention work lifecycle:

Change:
```yaml
description: Run a health check on the Code Wiki — mechanical ...
```

To:
```yaml
description: Run a health check on the Code Wiki — mechanical (orphans, broken links, stale pages, missing frontmatter, duplicates, log gap), semantic (contradictions, cross-reference gaps, stale claims, roadmap staleness, ADR chain), code-drift (packages on disk vs. in vault, exports mismatch), and work lifecycle (19 rules for work item lifecycle state). Workspace and repo discovered automatically. Usage /graph-wiki:lint [--stale-days N]
```

- [ ] **Step 2: Commit**

```bash
git add plugins/graph-wiki/commands/lint.md
git commit -m "docs(plugin): note work-layer lifecycle lint in lint.md"
```

---

## Task 12: Final verification

- [ ] **Step 1: Run all package test suites**

```bash
uv run --package work-io pytest -v
uv run --package graph-wiki-core pytest tests/unit/ -m "not integration" -v
uv run --package graph-wiki-cli pytest tests/unit/ -m "not integration" -v
```

Expected: all PASS, zero failures.

- [ ] **Step 2: Check CLI help is complete**

```bash
uv run --package graph-wiki-cli gw work --help
uv run --package graph-wiki-cli gw work file --help
uv run --package graph-wiki-cli gw work lint --help
uv run --package graph-wiki-cli gw work archive --help
uv run --package graph-wiki-cli gw work status --help
uv run --package graph-wiki-cli gw work regen-index --help
```

Expected: each shows its options without error.

- [ ] **Step 3: Run ruff**

```bash
uv run ruff check packages/work-io packages/graph-wiki-core/src/graph_wiki_core/commands/work.py packages/graph-wiki-cli/src/graph_wiki_cli/work_cli/
```

Fix any errors before committing.

- [ ] **Step 4: Final commit if any fixes**

```bash
git add -p
git commit -m "fix: ruff lint cleanup for work layer"
```
