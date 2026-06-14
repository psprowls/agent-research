# Fix Stale `spec_doc` Pointers in Archived Work Items — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use graph-wiki:subagent-driven-development (recommended) or graph-wiki:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Rewrite stale `spec_doc:` frontmatter pointers in archived work items so they point at the spec's real home under `raw/_archive/specs/`, via a guarded, idempotent sweep — then prove the `claude-code` workspace is clean.

**Architecture:** A standalone stdlib-only sweep script (`scripts/fix_stale_spec_doc_pointers.py`, matching the existing `scripts/migrate_mono_wiki_links.py` precedent) walks `wiki/work/**/*.md`. For each item it rewrites the *frontmatter* `spec_doc:` line **only when** the current target is missing **and** a counterpart exists at `raw/_archive/specs/<basename>`. `plan_doc`, body text, other frontmatter keys, and pointers that still resolve (active items) are left untouched, so the sweep converges to zero edits on re-run. The script is built test-first against a temp-workspace fixture, then applied to the live `claude-code` workspace and verified against three acceptance checks.

**Tech Stack:** Python 3.11 (stdlib only: `argparse`, `re`, `pathlib`), `pytest`, `uv`, the `gw` CLI (`gw work lint`).

**Scope note:** The code-level prevention (having `gw work archive` / the ingest move rewrite the pointer) is **explicitly deferred** per the spec's "Out of scope / follow-up". This deliverable is the data sweep only.

**Ground-truth note (verified 2026-06-14):** The on-disk state has drifted from the spec's snapshot. The spec listed 12 affected items; the live count is now **11** (`2026-06-11-archive-support-for-adrs-concepts-and-proposals-wiki-directories` already points at `raw/_archive/specs/`, and `2026-06-14-fix-work-index-json-excludes-index-md` correctly points at a live `raw/specs/` path). This is exactly why the sweep is **guard-driven, not list-driven** — verification asserts **zero stale remaining**, never a fixed count.

---

### Task 1: Build the guarded idempotent sweep script (test-first)

**Goal:** Produce `scripts/fix_stale_spec_doc_pointers.py` — a stdlib-only sweep whose pure `sweep()` / `archived_target()` functions pass a temp-workspace test suite covering rewrite, idempotence, active-item skip, plan_doc/body preservation, unfixable detection, and dry-run.

**Files:**
- Create: `scripts/fix_stale_spec_doc_pointers.py`
- Test: `scripts/test_fix_stale_spec_doc_pointers.py`

**Acceptance Criteria:**
- [ ] A stale frontmatter `spec_doc: raw/specs/<name>.md` whose target is missing but with a counterpart at `raw/_archive/specs/<name>.md` is rewritten to the archive path.
- [ ] A `spec_doc:` whose target still resolves (active item) is left byte-for-byte unchanged.
- [ ] `plan_doc:` keys and any body-text mentions of `spec_doc:` are never modified.
- [ ] A second `sweep(dry_run=False)` run rewrites nothing (idempotence).
- [ ] A `spec_doc:` whose target is missing **and** has no archive counterpart is reported `unfixable` and left as-is.
- [ ] `--dry-run` reports planned rewrites but writes nothing to disk.
- [ ] Importing the module has no side effects (sweep runs only under `if __name__ == "__main__":`).

**Verify:** `uv run pytest scripts/test_fix_stale_spec_doc_pointers.py -v` → all tests PASS

**Steps:**

- [ ] **Step 1: Write the failing test file**

Create `scripts/test_fix_stale_spec_doc_pointers.py`. The test adds the script's directory to `sys.path` itself because the root pytest config uses `--import-mode=importlib` (it does **not** auto-insert the test file's directory):

```python
"""Unit tests for scripts/fix_stale_spec_doc_pointers.py — the stale spec_doc sweep."""

import sys
from pathlib import Path

# Root pytest runs in --import-mode=importlib, which does NOT add the test file's
# directory to sys.path. Insert it so we can import the sibling script by name.
sys.path.insert(0, str(Path(__file__).parent))

from fix_stale_spec_doc_pointers import archived_target, sweep  # noqa: E402


def _make_ws(tmp_path: Path) -> Path:
    ws = tmp_path / "ws"
    (ws / "wiki" / "work" / "_archive").mkdir(parents=True)
    (ws / "raw" / "specs").mkdir(parents=True)
    (ws / "raw" / "_archive" / "specs").mkdir(parents=True)
    (ws / "raw" / "plans").mkdir(parents=True)
    return ws


def _work(ws: Path, subpath: str, body: str) -> Path:
    p = ws / "wiki" / "work" / subpath
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(body, encoding="utf-8")
    return p


def test_rewrites_stale_archived_pointer(tmp_path):
    ws = _make_ws(tmp_path)
    (ws / "raw" / "_archive" / "specs" / "a.md").write_text("spec", encoding="utf-8")
    item = _work(ws, "_archive/x.md", "---\ntitle: X\nspec_doc: raw/specs/a.md\n---\nbody\n")
    report = sweep(ws, dry_run=False)
    assert report["rewrote"] == ["wiki/work/_archive/x.md -> raw/_archive/specs/a.md"]
    assert "spec_doc: raw/_archive/specs/a.md" in item.read_text(encoding="utf-8")


def test_idempotent_second_run_no_edits(tmp_path):
    ws = _make_ws(tmp_path)
    (ws / "raw" / "_archive" / "specs" / "a.md").write_text("spec", encoding="utf-8")
    _work(ws, "_archive/x.md", "---\ntitle: X\nspec_doc: raw/specs/a.md\n---\nbody\n")
    sweep(ws, dry_run=False)
    report2 = sweep(ws, dry_run=False)
    assert report2["rewrote"] == []
    assert report2["ok"] == ["wiki/work/_archive/x.md"]


def test_active_pointer_that_resolves_is_left_alone(tmp_path):
    ws = _make_ws(tmp_path)
    (ws / "raw" / "specs" / "live.md").write_text("spec", encoding="utf-8")
    item = _work(ws, "live-item.md", "---\nspec_doc: raw/specs/live.md\n---\n")
    report = sweep(ws, dry_run=False)
    assert report["ok"] == ["wiki/work/live-item.md"]
    assert "spec_doc: raw/specs/live.md" in item.read_text(encoding="utf-8")


def test_plan_doc_and_body_mentions_untouched(tmp_path):
    ws = _make_ws(tmp_path)
    (ws / "raw" / "_archive" / "specs" / "a.md").write_text("spec", encoding="utf-8")
    body = (
        "---\n"
        "spec_doc: raw/specs/a.md\n"
        "plan_doc: raw/plans/a.md\n"
        "---\n"
        "Body mentions `spec_doc: raw/specs/a.md` and must not change.\n"
    )
    item = _work(ws, "_archive/y.md", body)
    sweep(ws, dry_run=False)
    text = item.read_text(encoding="utf-8")
    assert "plan_doc: raw/plans/a.md" in text  # plan_doc untouched
    assert "Body mentions `spec_doc: raw/specs/a.md`" in text  # body untouched
    assert "spec_doc: raw/_archive/specs/a.md" in text  # frontmatter rewritten


def test_missing_with_no_counterpart_is_unfixable(tmp_path):
    ws = _make_ws(tmp_path)
    item = _work(ws, "_archive/z.md", "---\nspec_doc: raw/specs/gone.md\n---\n")
    report = sweep(ws, dry_run=False)
    assert report["unfixable"] == ["wiki/work/_archive/z.md (spec_doc=raw/specs/gone.md)"]
    assert "spec_doc: raw/specs/gone.md" in item.read_text(encoding="utf-8")  # left as-is


def test_dry_run_does_not_write(tmp_path):
    ws = _make_ws(tmp_path)
    (ws / "raw" / "_archive" / "specs" / "a.md").write_text("spec", encoding="utf-8")
    item = _work(ws, "_archive/x.md", "---\nspec_doc: raw/specs/a.md\n---\n")
    report = sweep(ws, dry_run=True)
    assert report["rewrote"] == ["wiki/work/_archive/x.md -> raw/_archive/specs/a.md"]
    assert "spec_doc: raw/specs/a.md" in item.read_text(encoding="utf-8")  # unchanged on disk


def test_archived_target_helper(tmp_path):
    ws = _make_ws(tmp_path)
    (ws / "raw" / "_archive" / "specs" / "a.md").write_text("x", encoding="utf-8")
    assert archived_target(ws, "raw/specs/a.md") == "raw/_archive/specs/a.md"
    (ws / "raw" / "specs" / "b.md").write_text("x", encoding="utf-8")
    assert archived_target(ws, "raw/specs/b.md") is None  # resolves -> no rewrite
    assert archived_target(ws, "raw/specs/none.md") is None  # missing, no counterpart
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `uv run pytest scripts/test_fix_stale_spec_doc_pointers.py -v`
Expected: collection error / `ModuleNotFoundError: No module named 'fix_stale_spec_doc_pointers'` (the script does not exist yet).

- [ ] **Step 3: Write the sweep script**

Create `scripts/fix_stale_spec_doc_pointers.py`:

```python
#!/usr/bin/env python3
"""Sweep stale ``spec_doc`` pointers in work items to their archived spec home.

When a work item resolves and its spec is ingested, the spec file moves from
``raw/specs/<name>.md`` to ``raw/_archive/specs/<name>.md`` but the item's
``spec_doc:`` frontmatter pointer is not rewritten, leaving every archived item
pointing at a path that no longer exists.

This guarded, idempotent sweep rewrites a frontmatter ``spec_doc:`` pointer only
when BOTH:
  1. the current target is missing, and
  2. ``raw/_archive/specs/<basename-of-target>`` exists.
The pointer is then set to that archive path. ``plan_doc`` keys, body text, other
frontmatter keys, and pointers that still resolve (active items) are left
untouched, so the sweep is safe to re-run and converges to zero edits.

Exit status:
  0 — no stale pointers remain (clean, or every fixable one was fixed)
  1 — at least one ``spec_doc`` is missing with no archive counterpart (unfixable)

Usage:
  python scripts/fix_stale_spec_doc_pointers.py --workspace <ws-root> [--dry-run]
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

# A frontmatter-level key sits at column 0. Body mentions such as
# "- `spec_doc: ...`" begin with "- " and never match this anchored pattern;
# the sweep additionally restricts matching to the frontmatter block.
_SPEC_DOC_LINE = re.compile(r"^spec_doc:[ \t]*(?P<val>\S+)[ \t]*$", re.MULTILINE)


def _frontmatter_span(text: str) -> tuple[int, int] | None:
    """Return (start, end) char offsets of the frontmatter block body, or None.

    The block is the region between the opening ``---\\n`` fence and the closing
    ``\\n---`` fence. Files without a leading fence have no frontmatter.
    """
    if not text.startswith("---\n"):
        return None
    close = text.find("\n---", 4)
    if close == -1:
        return None
    return 4, close + 1


def archived_target(ws_root: Path, pointer: str) -> str | None:
    """Return the corrected pointer if a rewrite applies, else None.

    Rewrite iff the current target is missing AND the archive counterpart exists.
    A pointer that still resolves, or one missing with no counterpart, returns None.
    """
    if (ws_root / pointer).exists():
        return None
    candidate = f"raw/_archive/specs/{Path(pointer).name}"
    return candidate if (ws_root / candidate).exists() else None


def sweep(ws_root: Path, *, dry_run: bool) -> dict[str, list[str]]:
    """Walk wiki/work/**/*.md and rewrite stale frontmatter spec_doc pointers.

    Returns a disposition report with three lists: ``rewrote`` (paths rewritten,
    "<rel> -> <new>"), ``ok`` (pointer already resolves), and ``unfixable``
    (missing target, no archive counterpart, "<rel> (spec_doc=<ptr>)").
    """
    report: dict[str, list[str]] = {"rewrote": [], "ok": [], "unfixable": []}
    work_dir = ws_root / "wiki" / "work"
    for md in sorted(work_dir.rglob("*.md")):
        if md.name == "index.md":
            continue
        text = md.read_text(encoding="utf-8")
        span = _frontmatter_span(text)
        if span is None:
            continue
        fm_start, fm_end = span
        m = _SPEC_DOC_LINE.search(text, fm_start, fm_end)
        if m is None:
            continue
        pointer = m.group("val")
        rel = md.relative_to(ws_root).as_posix()
        if (ws_root / pointer).exists():
            report["ok"].append(rel)
            continue
        target = archived_target(ws_root, pointer)
        if target is None:
            report["unfixable"].append(f"{rel} (spec_doc={pointer})")
            continue
        new_text = text[: m.start()] + f"spec_doc: {target}" + text[m.end() :]
        if not dry_run:
            md.write_text(new_text, encoding="utf-8")
        report["rewrote"].append(f"{rel} -> {target}")
    return report


def main(argv: list[str]) -> int:
    ap = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    ap.add_argument("--workspace", required=True, type=Path, help="Workspace root (has wiki/ and raw/)")
    ap.add_argument("--dry-run", action="store_true", help="Report planned edits without writing")
    args = ap.parse_args(argv)
    ws_root = args.workspace.expanduser().resolve()

    report = sweep(ws_root, dry_run=args.dry_run)
    verb = "WOULD REWRITE" if args.dry_run else "REWROTE"
    for line in report["rewrote"]:
        print(f"{verb}: {line}")
    for line in report["unfixable"]:
        print(f"UNFIXABLE (missing, no archive counterpart): {line}", file=sys.stderr)
    print(
        f"\n{len(report['rewrote'])} {'would be ' if args.dry_run else ''}rewritten, "
        f"{len(report['ok'])} already resolve, "
        f"{len(report['unfixable'])} unfixable."
    )
    return 1 if report["unfixable"] else 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
```

- [ ] **Step 4: Run the test to verify it passes**

Run: `uv run pytest scripts/test_fix_stale_spec_doc_pointers.py -v`
Expected: 7 passed.

- [ ] **Step 5: Lint the new files**

Run: `uv run ruff check scripts/fix_stale_spec_doc_pointers.py scripts/test_fix_stale_spec_doc_pointers.py`
Expected: no errors (match the surrounding 120-col style; do not run `ruff format` on the wider tree).

- [ ] **Step 6: Commit (in the agent-research code repo)**

```bash
git add scripts/fix_stale_spec_doc_pointers.py scripts/test_fix_stale_spec_doc_pointers.py
git commit -m "feat(scripts): guarded idempotent sweep for stale spec_doc pointers"
```

---

### Task 2: Apply the sweep to the `claude-code` workspace and verify clean (USER-ORDERED GATE)

**Goal:** Apply `scripts/fix_stale_spec_doc_pointers.py` to the `claude-code` workspace and prove the result is clean: an existence re-scan reports **zero** stale `spec_doc`, `gw work lint --json` emits **no** `artifact-doc-missing` findings, and a second sweep run rewrites **zero** items (idempotence).

> **USER-ORDERED GATE — NON-SKIPPABLE.** This task was requested by the user in the current conversation. It MUST NOT be closed by walking around it, by declaring it "verified inline", or by substituting a cheaper check. Close only after every item in `acceptanceCriteria` has been re-validated independently, with output captured.

**Files:**
- Modify (data, in the workspace repo): `/Users/pat/Personal/workspaces/agent-research/claude-code/wiki/work/_archive/*.md` — the stale `spec_doc:` lines (≈11 items as of 2026-06-14; guard-driven, not a fixed count).
- No files in the `agent-research` code repo change in this task.

**Acceptance Criteria:**
- [ ] Dry-run lists only `_archive/` items and reports **0 unfixable**; the rewrite count is reviewed and looks right (~11).
- [ ] After apply, the existence re-scan reports **0** stale frontmatter `spec_doc` across all `wiki/work/**/*.md`.
- [ ] `gw work lint --workspace <claude-code> --json` contains **zero** findings with `rule_id == "artifact-doc-missing"`.
- [ ] A second `--dry-run` run prints `0 would be rewritten` (idempotence).
- [ ] No `plan_doc:` line and no active (non-archive) work item was modified (`git -C <claude-code> diff` touches only `wiki/work/_archive/` `spec_doc:` lines).

**Verify:**
```bash
WS=/Users/pat/Personal/workspaces/agent-research/claude-code
# (1) zero stale remaining + (3) idempotent re-run:
uv run python scripts/fix_stale_spec_doc_pointers.py --workspace "$WS" --dry-run
# expected after apply: "0 would be rewritten, N already resolve, 0 unfixable."
# (2) no lint findings for the pointer rule:
uv run --package graph-wiki-cli gw work lint --workspace "$WS" --json | python -c 'import sys,json; f=json.load(sys.stdin); a=[x for x in (f.get("findings") or f) if x.get("rule_id")=="artifact-doc-missing"]; print("artifact-doc-missing:", len(a)); sys.exit(1 if a else 0)'
# expected: "artifact-doc-missing: 0" and exit 0
```

**Steps:**

- [ ] **Step 1: Dry-run and review the plan**

```bash
WS=/Users/pat/Personal/workspaces/agent-research/claude-code
uv run python scripts/fix_stale_spec_doc_pointers.py --workspace "$WS" --dry-run
```
Expected: a `WOULD REWRITE:` line per stale `_archive/` item (≈11), all rewrites targeting `raw/_archive/specs/...`, and a summary ending `0 unfixable.` If any line is **not** under `wiki/work/_archive/`, or `unfixable > 0`, STOP and investigate before applying — do not proceed past a surprise.

- [ ] **Step 2: Apply the sweep**

```bash
uv run python scripts/fix_stale_spec_doc_pointers.py --workspace "$WS"
echo "exit=$?"   # expected exit=0
```

- [ ] **Step 3: Verify the diff is surgical**

```bash
git -C "$WS" diff -- wiki/work
```
Expected: only `spec_doc:` lines under `wiki/work/_archive/` changed from `raw/specs/...` to `raw/_archive/specs/...`. No `plan_doc:` line, no body text, no active item touched.

- [ ] **Step 4: Acceptance check 1 + 3 — zero stale, idempotent re-run**

```bash
uv run python scripts/fix_stale_spec_doc_pointers.py --workspace "$WS" --dry-run
```
Expected: `0 would be rewritten, N already resolve, 0 unfixable.`

- [ ] **Step 5: Acceptance check 2 — `gw work lint` clean of pointer findings**

```bash
uv run --package graph-wiki-cli gw work lint --workspace "$WS" --json \
  | python -c 'import sys,json; f=json.load(sys.stdin); items=f.get("findings") if isinstance(f,dict) else f; a=[x for x in items if x.get("rule_id")=="artifact-doc-missing"]; print("artifact-doc-missing:", len(a)); sys.exit(1 if a else 0)'
```
Expected: `artifact-doc-missing: 0`, exit 0. (If the `--json` shape differs, capture it and adjust the extraction — the gate is "zero `artifact-doc-missing` findings", however the payload is keyed.)

- [ ] **Step 6: Commit the data fix (in the workspace repo)**

```bash
git -C "$WS" add wiki/work/_archive
git -C "$WS" commit -m "fix(work): rewrite stale spec_doc pointers to raw/_archive/specs/"
```

---

## Self-Review

**1. Spec coverage:**
- "Single guarded, idempotent sweep over `wiki/work/**/*.md`" → Task 1 `sweep()` (rglob over `wiki/work`), guard = target-missing AND archive-counterpart-exists.
- "rewrite only when both [target missing] and [counterpart exists]" → `archived_target()` + the `ok`/`unfixable` branches; tested in `test_*`.
- "`plan_doc` not touched / no body text / no other keys / no active items" → frontmatter-span scoping + `test_plan_doc_and_body_mentions_untouched`, `test_active_pointer_that_resolves_is_left_alone`.
- "safe to re-run, converges to zero" → `test_idempotent_second_run_no_edits` + Task 2 Step 4.
- Verification triple (zero stale / `gw work lint` clean / zero re-run edits) → Task 2 acceptance criteria + Verify block.
- "code-level prevention deferred" → captured in the plan's Scope note; no code-path changes in either task.

**2. Placeholder scan:** No TBD/TODO/"handle edge cases"/"similar to" — all code is complete and inline.

**3. Type consistency:** `sweep()` returns `dict[str, list[str]]` with keys `"rewrote"`, `"ok"`, `"unfixable"` — used identically in script `main()`, the tests, and Task 2's expected output. `archived_target(ws_root, pointer) -> str | None` consistent across script and `test_archived_target_helper`. Disposition strings (`"WOULD REWRITE"`, `"... would be rewritten"`, `"0 unfixable."`) match between script output and Task 2 expectations.

**Drift guard:** Verification keys on **zero stale remaining**, never on the spec's stale "12" — the live count is 11 and the guard absorbs further drift.
