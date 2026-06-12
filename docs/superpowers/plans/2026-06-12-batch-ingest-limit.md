# Batch Ingest Limit Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use graph-wiki:subagent-driven-development (recommended) or graph-wiki:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Cap a batch ingest to the first N units (default 10), with `--limit N` to set N and `--all` to ingest everything.

**Architecture:** The limit lives in the shared `wiki-io` brief builder (`build_batch_ingest_brief`) so it is defined and tested once; `enumerate_batch_units` stays pure and the builder slices. Only the Claude-Code-plugin surface (prep script + `ingest.md` prose) is wired to expose `--limit`/`--all`. No Bedrock orchestrator is built.

**Tech Stack:** Python 3.11, `uv` workspace, pytest, argparse. Spec: `docs/superpowers/specs/2026-06-12-batch-ingest-limit-design.md`.

---

## File Structure

- `packages/wiki-io/src/wiki_io/ingest_source.py` — owns batch enumeration + brief. Gains the `limit` param and the `total_count`/`limited` brief keys. **(Task 1)**
- `packages/wiki-io/tests/test_batch_ingest_brief.py` — unit tests for the brief shape/slicing. **(Task 1)**
- `plugins/graph-wiki/skills/graph-wiki/scripts/ingest_source.py` — thin prep-script shim. Gains `--limit`/`--all` argparse flags and the truncation-aware batch print. **(Task 2)**
- `packages/graph-wiki-cli/tests/unit/test_plugin_claude_scripts.py` — prep-script behavior tests. **(Task 2)**
- `plugins/graph-wiki/commands/ingest.md` — batch-mode prose: document the flags, truncation-aware confirm prompt. **(Task 3)**

`plugins/graph-wiki/agents/ingestor.md` is **not** touched — it operates on whatever unit it is handed.

---

### Task 1: Add `limit` to the shared batch brief builder

**Goal:** `build_batch_ingest_brief(..., limit=10)` returns the first-N units plus `total_count`/`limited`, with `enumerate_batch_units` unchanged.

**Files:**
- Modify: `packages/wiki-io/src/wiki_io/ingest_source.py:226-244`
- Test: `packages/wiki-io/tests/test_batch_ingest_brief.py`

**Acceptance Criteria:**
- [ ] `limit: int | None = 10` param; `None` means no cap.
- [ ] Brief gains `total_count` (all discovered) and `limited` (`total_count > unit_count`).
- [ ] `units` is the first-N by the existing path sort; `unit_count == len(units)`.
- [ ] `enumerate_batch_units` is unchanged (still enumerates all units).
- [ ] Existing tests in the file still pass (default limit 10 leaves small folders untouched).

**Verify:** `uv run pytest packages/wiki-io/tests/test_batch_ingest_brief.py -v` → all pass

**Steps:**

- [ ] **Step 1: Write the failing tests**

Append to `packages/wiki-io/tests/test_batch_ingest_brief.py`:

```python
def _write_n_specs(root: Path, n: int) -> None:
    for i in range(n):
        _write(root / f"s{i:02d}.md")


def test_brief_default_limit_truncates_to_ten(tmp_path: Path) -> None:
    ws = _mk_workspace(tmp_path)
    root = ws / "raw" / "specs"
    _write_n_specs(root, 12)  # s00.md .. s11.md
    brief = build_batch_ingest_brief(source_path=root, wiki=ws / "wiki", repo=ws, workspace_root=ws)
    assert brief is not None
    assert brief["total_count"] == 12
    assert brief["unit_count"] == 10
    assert brief["limited"] is True
    assert [u["rel"] for u in brief["units"]] == [f"s{i:02d}.md" for i in range(10)]


def test_brief_limit_larger_than_count_is_not_limited(tmp_path: Path) -> None:
    ws = _mk_workspace(tmp_path)
    root = ws / "raw" / "specs"
    _write_n_specs(root, 3)
    brief = build_batch_ingest_brief(source_path=root, wiki=ws / "wiki", repo=ws, workspace_root=ws, limit=10)
    assert brief is not None
    assert brief["total_count"] == 3
    assert brief["unit_count"] == 3
    assert brief["limited"] is False


def test_brief_limit_none_ingests_all(tmp_path: Path) -> None:
    ws = _mk_workspace(tmp_path)
    root = ws / "raw" / "specs"
    _write_n_specs(root, 12)
    brief = build_batch_ingest_brief(source_path=root, wiki=ws / "wiki", repo=ws, workspace_root=ws, limit=None)
    assert brief is not None
    assert brief["total_count"] == 12
    assert brief["unit_count"] == 12
    assert brief["limited"] is False


def test_brief_limit_equals_count_is_not_limited(tmp_path: Path) -> None:
    ws = _mk_workspace(tmp_path)
    root = ws / "raw" / "specs"
    _write_n_specs(root, 5)
    brief = build_batch_ingest_brief(source_path=root, wiki=ws / "wiki", repo=ws, workspace_root=ws, limit=5)
    assert brief is not None
    assert brief["unit_count"] == 5
    assert brief["limited"] is False
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest packages/wiki-io/tests/test_batch_ingest_brief.py -k "limit or limited" -v`
Expected: FAIL — `KeyError: 'total_count'` (and `'limited'`); the default-limit test fails because all 12 units are returned.

- [ ] **Step 3: Update the brief builder**

In `packages/wiki-io/src/wiki_io/ingest_source.py`, replace the body of `build_batch_ingest_brief` (currently lines 226-244). Keep the docstring; change the signature and the enumerate/return block:

```python
def build_batch_ingest_brief(
    source_path: Path, wiki: Path, repo: Path, workspace_root: Path, limit: int | None = 10
) -> dict | None:
    """Build the batch brief for a kind-folder root, or None for any other path.

    `limit` caps the units to the first N by path sort (None = no cap). The brief
    reports `total_count` (all discovered) and `limited` so the caller can show an
    honest "ingesting first N of M" confirm. Returning None keeps the caller's
    routing a single check; the manifest carries no file contents (workers run the
    single-source prep per unit).
    """
    source_path = _resolve_source_path(source_path, repo)
    kind = resolve_batch_root(source_path, workspace_root)
    if kind is None:
        return None
    all_units = enumerate_batch_units(kind, source_path)
    total_count = len(all_units)
    units = all_units if limit is None else all_units[:limit]
    return {
        "is_batch": True,
        "kind_folder": kind,
        "root": str(source_path),
        "unit_count": len(units),
        "total_count": total_count,
        "limited": total_count > len(units),
        "units": units,
        "state_gate": compute_state_gate(repo, workspace=workspace_root),
    }
```

- [ ] **Step 4: Run the full file to verify pass (incl. existing tests)**

Run: `uv run pytest packages/wiki-io/tests/test_batch_ingest_brief.py -v`
Expected: PASS — new tests pass and the pre-existing `test_build_batch_ingest_brief_shape` / `_empty_folder` / `_none_for_non_batch_path` still pass (they don't assert the new keys).

- [ ] **Step 5: Commit**

```bash
git add packages/wiki-io/src/wiki_io/ingest_source.py packages/wiki-io/tests/test_batch_ingest_brief.py
git commit -m "feat(wiki-io): limit batch ingest brief to first N units (default 10)"
```

---

### Task 2: Wire `--limit` / `--all` into the prep script

**Goal:** The plugin prep script accepts `--limit N` (default 10) and `--all` (overrides `--limit`), passes the resolved limit into `build_batch_ingest_brief`, and prints a truncation-aware batch line.

**Files:**
- Modify: `plugins/graph-wiki/skills/graph-wiki/scripts/ingest_source.py:50-55` (argparse) and `:70-75` (call) and `:102-106` (batch print)
- Test: `packages/graph-wiki-cli/tests/unit/test_plugin_claude_scripts.py`

**Acceptance Criteria:**
- [ ] `--limit` (int, default 10) and `--all` (store_true, dest `all_units`) are parsed.
- [ ] Resolved `limit = None if args.all_units else args.limit` is passed as `limit=` to `build_batch_ingest_brief`.
- [ ] `--all` overrides `--limit` when both are passed.
- [ ] Batch print shows `Batch: raw/<kind> (N of M units, --all for everything)` when `limited`, else the existing `(N units)` form.

**Verify:** `uv run --package graph-wiki-cli pytest packages/graph-wiki-cli/tests/unit/test_plugin_claude_scripts.py -k batch -v` → all pass

**Steps:**

- [ ] **Step 1: Write the failing test**

Append to `packages/graph-wiki-cli/tests/unit/test_plugin_claude_scripts.py` (`pytest`, `runpy`, `sys`, `types`, `Path` are already imported at the top of the file):

```python
@pytest.mark.parametrize(
    "extra_argv, expected_limit",
    [
        ([], 10),
        (["--limit", "25"], 25),
        (["--all"], None),
        (["--all", "--limit", "5"], None),
    ],
)
def test_ingest_source_script_batch_limit_resolution(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
    extra_argv: list[str],
    expected_limit: int | None,
) -> None:
    _install_claude_backend(monkeypatch)
    workspace = tmp_path / "workspace"
    _install_fake_wiki_io(monkeypatch, workspace)
    module = types.ModuleType("wiki_io.ingest_source")

    captured: dict[str, object] = {}

    def fake_batch(*args, **kwargs):
        captured["limit"] = kwargs.get("limit", "MISSING")
        return {
            "is_batch": True,
            "kind_folder": "specs",
            "root": str(kwargs.get("source_path", "")),
            "unit_count": 2,
            "total_count": 5,
            "limited": True,
            "units": [
                {"rel": "a.md", "unit_type": "file"},
                {"rel": "b.md", "unit_type": "file"},
            ],
            "state_gate": {},
        }

    module.build_batch_ingest_brief = fake_batch  # type: ignore[attr-defined]
    module.build_ingest_brief = lambda *a, **k: {}  # type: ignore[attr-defined]  # not reached (batch)
    module.build_folder_ingest_brief = lambda *a, **k: {}  # type: ignore[attr-defined]  # not reached
    module.build_skill_ingest_brief = lambda *a, **k: {}  # type: ignore[attr-defined]  # not reached
    module.resolve_skill_anchor = lambda path: None  # type: ignore[attr-defined]  # not reached
    monkeypatch.setitem(sys.modules, "wiki_io.ingest_source", module)

    (workspace / "wiki").mkdir(parents=True)
    root = workspace / "raw" / "specs"
    root.mkdir(parents=True)
    monkeypatch.setenv("GRAPH_WIKI_WORKSPACE", str(workspace))
    monkeypatch.setattr(
        sys,
        "argv",
        ["ingest_source.py", str(root), "--workspace", str(workspace), *extra_argv],
    )

    runpy.run_path(str(_SCRIPT_DIR / "ingest_source.py"), run_name="__main__")

    assert captured["limit"] == expected_limit
    out = capsys.readouterr().out
    assert "Batch: raw/specs (2 of 5 units, --all for everything)" in out
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `uv run --package graph-wiki-cli pytest packages/graph-wiki-cli/tests/unit/test_plugin_claude_scripts.py -k batch_limit_resolution -v`
Expected: FAIL — argparse errors on the unknown `--limit`/`--all` args (SystemExit), and the batch print is the old `(2 units)` form.

- [ ] **Step 3: Add the argparse flags**

In `plugins/graph-wiki/skills/graph-wiki/scripts/ingest_source.py`, after the existing `--json` argument (line 54), add:

```python
    parser.add_argument("--limit", type=int, default=10, help="Batch: max units to ingest (default 10)")
    parser.add_argument(
        "--all", action="store_true", dest="all_units", help="Batch: ingest all units (overrides --limit)"
    )
```

- [ ] **Step 4: Pass the resolved limit into the brief builder**

Replace the `build_batch_ingest_brief(...)` call (currently lines 70-75) with:

```python
    limit = None if args.all_units else args.limit
    brief = build_batch_ingest_brief(
        source_path=resolved,
        wiki=wiki,
        repo=repo,
        workspace_root=workspace_root,
        limit=limit,
    )
```

- [ ] **Step 5: Make the batch print truncation-aware**

Replace the batch print block (currently lines 102-106) with:

```python
    if brief.get("is_batch"):
        total = brief.get("total_count", brief["unit_count"])
        if brief.get("limited"):
            print(f"Batch: raw/{brief['kind_folder']} ({brief['unit_count']} of {total} units, --all for everything)")
        else:
            print(f"Batch: raw/{brief['kind_folder']} ({brief['unit_count']} units)")
        for unit in brief["units"]:
            print(f"  - {unit['rel']} ({unit['unit_type']})")
        return
```

- [ ] **Step 6: Run the test to verify it passes**

Run: `uv run --package graph-wiki-cli pytest packages/graph-wiki-cli/tests/unit/test_plugin_claude_scripts.py -k batch_limit_resolution -v`
Expected: PASS (all four parametrized cases).

- [ ] **Step 7: Run the whole prep-script test module (no regressions)**

Run: `uv run --package graph-wiki-cli pytest packages/graph-wiki-cli/tests/unit/test_plugin_claude_scripts.py -v`
Expected: PASS — the existing `emits_json_brief` / `emits_skill_brief` tests still pass (their fake `build_batch_ingest_brief` ignores the new `limit=` kwarg via `*args, **kwargs`).

- [ ] **Step 8: Commit**

```bash
git add plugins/graph-wiki/skills/graph-wiki/scripts/ingest_source.py packages/graph-wiki-cli/tests/unit/test_plugin_claude_scripts.py
git commit -m "feat(plugin): add --limit/--all to batch ingest prep script"
```

---

### Task 3: Document `--limit` / `--all` in the ingest command prose

**Goal:** `ingest.md`'s batch-mode section documents the two flags and the confirm prompt is truncation-aware, matching the prep-script behavior.

**Files:**
- Modify: `plugins/graph-wiki/commands/ingest.md:40-56`

**Acceptance Criteria:**
- [ ] The batch-mode intro mentions `--limit N` (default 10) and `--all`.
- [ ] The one-confirm step's prompt reflects truncation (first N of M) and points at `--all`.
- [ ] No change to the fan-out (≤4 concurrent), commit phase, or `agents/ingestor.md`.

**Verify:** `grep -n -- "--limit\|--all\|ingesting first" plugins/graph-wiki/commands/ingest.md` → shows the new prose

**Steps:**

- [ ] **Step 1: Add the flags to the batch-mode intro**

In `plugins/graph-wiki/commands/ingest.md`, after the sentence ending `resolve `raw/<kind>` against the workspace, not the repo cwd).` (line 50), add a new paragraph:

```markdown
**Limit (default 10):** a batch ingests at most the first **10** units (by path
sort) unless told otherwise. Pass `--limit N` to the prep script to cap at N, or
`--all` to ingest every unit. `--all` overrides `--limit` when both are given.
The prep script reports `unit_count` (units to ingest), `total_count` (units
found), and `limited` (whether truncation happened).
```

- [ ] **Step 2: Make the confirm prompt truncation-aware**

Replace the **Detect + one confirm** step (currently lines 52-56) with:

```markdown
1. **Detect + one confirm** — run the prep script. If `total_count` is 0: report
   "nothing to ingest" and stop. Otherwise show the unit list and ask ONCE:
   - if `limited` is true: _"raw/<kind>: <total_count> units found, ingesting
     first <unit_count> (pass `--all` for everything). NEW concept/ADR pages
     become proposals in `wiki/proposals/`, not real pages. Proceed?"_
   - else: _"raw/<kind>: <unit_count> units. Will ingest all; NEW concept/ADR
     pages become proposals in `wiki/proposals/`, not real pages. Proceed?"_

   After the go-ahead, run autonomously — no further questions.
```

- [ ] **Step 3: Verify the prose changed**

Run: `grep -n -- "--limit\|--all\|ingesting first\|total_count" plugins/graph-wiki/commands/ingest.md`
Expected: matches in the batch-mode intro and the confirm step.

- [ ] **Step 4: Commit**

```bash
git add plugins/graph-wiki/commands/ingest.md
git commit -m "docs(plugin): document batch ingest --limit/--all in ingest command"
```

---

## Notes

- No migration, no graph/wiki schema change (consistent with "no migrations until v2.0").
- Bedrock surface is intentionally untouched; the shared brief is now limit-aware for a clean future add.
- Tests are per-package — run with `--package`/path scoping, not from the workspace root.
