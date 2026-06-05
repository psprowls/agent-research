# Part 1 Cleanup Boundary Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Remove Part 1 library-package executable surfaces, preserve intentional library APIs, invert Graph Wiki plugin shims, delete the dead link rewriter, and correct the cleanup backlog.

**Architecture:** `wiki-io` and `workspace-io` become import-only libraries for this pass: they keep reusable functions and lose argparse/stdout/`__main__` wrappers. The Graph Wiki plugin scripts remain executable delivery surfaces and own any command parsing, output formatting, backend dispatch, and process exit behavior needed by the plugin. No new shared plugin command-helper module is introduced.

**Tech Stack:** Python 3.11, uv workspace packages, pytest, argparse, pathlib, subprocess, JSON stdout contracts.

---

## File Structure

- Modify `packages/wiki-io/src/wiki_io/update_index.py`: remove shebang, executable usage text, `argparse`, `json`, `main()`, and `__main__`; keep `update_index()`, `scan_vault()`, `scan_work()`, and rendering helpers.
- Modify `packages/wiki-io/src/wiki_io/update_tokens.py`: remove shebang, executable usage text, `argparse`, `json`, `main()`, and `__main__`; keep token counting and vault-update library functions.
- Modify `packages/wiki-io/src/wiki_io/append_log.py`: remove shebang, executable usage text, `argparse`, `main()`, and `__main__`; keep `append_log(..., raise_exception=True)` semantics unchanged.
- Modify `packages/wiki-io/src/wiki_io/init_vault.py`: remove shebang, executable usage text, `argparse`, `main()`, and `__main__`; keep `init_wiki()`, constants, logging, and template helpers.
- Modify `packages/wiki-io/src/wiki_io/ingest_source.py`: remove CLI imports and `main()`; keep extract/brief helper behavior as library functions by adding focused `build_ingest_brief()` and `build_folder_ingest_brief()` helpers that the plugin script can call.
- Modify `packages/wiki-io/src/wiki_io/wiki_search.py`: remove shebang, executable usage text, `argparse`, `main()`, and `__main__`; keep BM25 helpers.
- Modify `packages/wiki-io/src/wiki_io/lint_wiki.py`: remove shebang, executable usage text, `argparse`, `main()`, and `__main__`; keep `scan()` and `print_report()`.
- Modify `packages/wiki-io/src/wiki_io/graph_analyzer.py`: remove shebang, executable usage text, `argparse`, `json`, `resolve_wiki_and_repo`, `main()`, and `__main__`; keep `_parse_frontmatter_lists()`, `build_graph()`, `connected_components()`, and `analyze()`.
- Modify `plugins/graph-wiki/skills/graph-wiki/scripts/init_vault.py`: keep `_uv_reexec.ensure()`, preserve Bedrock dispatch, and own argparse/output for Claude branch.
- Modify `plugins/graph-wiki/skills/graph-wiki/scripts/ingest_source.py`: keep `_uv_reexec.ensure()`, preserve Bedrock dispatch, and own argparse/output for Claude branch.
- Modify `plugins/graph-wiki/skills/graph-wiki/scripts/wiki_search.py`: keep `_uv_reexec.ensure()`, preserve Bedrock dispatch, and own argparse/output for Claude branch.
- Modify `plugins/graph-wiki/skills/graph-wiki/scripts/lint_wiki.py`: keep `_uv_reexec.ensure()`, preserve Bedrock dispatch, and own argparse/output for Claude branch.
- Modify `plugins/graph-wiki/skills/graph-wiki/scripts/graph_analyzer.py`: keep `_uv_reexec.ensure()` and own argparse/output directly.
- Modify `packages/workspace-io/src/workspace_io/config.py`: remove `sys`, `_main()`, and `__main__`.
- Delete `packages/wiki-io/src/wiki_io/link_rewriter.py`.
- Delete `packages/wiki-io/tests/test_link_rewriter.py`.
- Delete `packages/wiki-io/tests/test_link_rewriter_build_table.py`.
- Delete `packages/wiki-io/tests/integration/test_link_rewriter_integration.py`.
- Create `packages/wiki-io/tests/test_library_boundaries.py`: assert the selected `wiki_io` modules are import-only at the executable boundary.
- Create `packages/graph-wiki-cli/tests/unit/test_plugin_claude_scripts.py`: exercise Claude-branch plugin script behavior now that scripts own CLI parsing.
- Modify `packages/wiki-io/tests/test_wiki_search.py`: stop asserting `wiki_io.wiki_search.main` and stop running `python -m wiki_io.wiki_search`.
- Modify `packages/wiki-io/tests/test_lint_wiki.py`: stop asserting `wiki_io.lint_wiki.main`.
- Modify `packages/wiki-io/tests/test_ingest_source_prep.py`: replace `prep.main()` tests with `build_ingest_brief()` / `build_folder_ingest_brief()` tests.
- Modify `packages/workspace-io/tests/test_config.py`: replace the removed `python -m workspace_io.config` test with direct `resolve()` coverage.
- Modify `packages/graph-wiki-cli/tests/unit/test_plugin_bedrock_shims.py`: update fake modules so Bedrock dispatch tests do not require `wiki_io.<module>.main`.
- Modify `packages/wiki-io/src/wiki_io/lint/common.py`: remove the stale `wiki_io.link_rewriter.rewrite_text` comment reference.
- Modify `docs/cleanup-backlog.md`: mark completed boundary cleanup, retain `workspace_io.versions`, retain `graph_io.queries.list_entry_points`, and remove deleted-link-rewriter guidance from active backlog.

---

### Task 1: Add Library Boundary Tests

**Files:**
- Create: `packages/wiki-io/tests/test_library_boundaries.py`
- Test: `packages/wiki-io/tests/test_library_boundaries.py`

- [ ] **Step 1: Write the failing boundary tests**

Create `packages/wiki-io/tests/test_library_boundaries.py`:

```python
"""Executable-boundary tests for wiki_io library modules."""

from __future__ import annotations

import importlib
import inspect


LIBRARY_ONLY_MODULES = [
    "wiki_io.update_index",
    "wiki_io.update_tokens",
    "wiki_io.append_log",
    "wiki_io.init_vault",
    "wiki_io.ingest_source",
    "wiki_io.wiki_search",
    "wiki_io.lint_wiki",
    "wiki_io.graph_analyzer",
]


def test_wiki_io_boundary_modules_do_not_export_main() -> None:
    for module_name in LIBRARY_ONLY_MODULES:
        module = importlib.import_module(module_name)
        assert not hasattr(module, "main"), f"{module_name} must not expose an executable main()"


def test_wiki_io_boundary_modules_have_no_main_guard() -> None:
    for module_name in LIBRARY_ONLY_MODULES:
        module = importlib.import_module(module_name)
        source = inspect.getsource(module)
        assert 'if __name__ == "__main__"' not in source
        assert "if __name__ == '__main__'" not in source


def test_wiki_io_boundary_modules_do_not_import_argparse() -> None:
    for module_name in LIBRARY_ONLY_MODULES:
        module = importlib.import_module(module_name)
        source = inspect.getsource(module)
        assert "import argparse" not in source, f"{module_name} should not own CLI parsing"
```

- [ ] **Step 2: Run the boundary tests to verify they fail**

Run:

```bash
uv run --package wiki-io pytest packages/wiki-io/tests/test_library_boundaries.py -v
```

Expected: FAIL. At minimum, `wiki_io.update_index`, `wiki_io.update_tokens`, `wiki_io.append_log`, `wiki_io.init_vault`, `wiki_io.ingest_source`, `wiki_io.wiki_search`, `wiki_io.lint_wiki`, and `wiki_io.graph_analyzer` still expose `main()` or import `argparse`.

- [ ] **Step 3: Commit the failing boundary tests**

```bash
git add packages/wiki-io/tests/test_library_boundaries.py
git commit -m "test: capture wiki_io executable boundary"
```

---

### Task 2: Remove Class A wiki-io Executable Wrappers

**Files:**
- Modify: `packages/wiki-io/src/wiki_io/update_index.py`
- Modify: `packages/wiki-io/src/wiki_io/update_tokens.py`
- Modify: `packages/wiki-io/src/wiki_io/append_log.py`
- Test: `packages/wiki-io/tests/test_library_boundaries.py`
- Test: `packages/wiki-io/tests/test_update_index_surgical.py`
- Test: `packages/wiki-io/tests/test_update_tokens.py`
- Test: `packages/wiki-io/tests/test_ingest_work_item.py`

- [ ] **Step 1: Remove executable-only code from `update_index.py`**

In `packages/wiki-io/src/wiki_io/update_index.py`, remove the first shebang line, remove the `Usage:` lines from the module docstring, remove these imports:

```python
import argparse
import json
```

Also remove:

```python
from wiki_io._workspace import resolve_wiki_and_repo
```

Delete the full `main()` function and final guard:

```python
def main():
    p = argparse.ArgumentParser(description="Regenerate wiki/index.md")
    p.add_argument("--dry-run", action="store_true")
    p.add_argument("--json", action="store_true")
    args = p.parse_args()

    try:
        wiki, _ = resolve_wiki_and_repo()
        pages = scan_vault(wiki)
        work_entries = scan_work(wiki.parent)
        if work_entries:
            pages["work"] = work_entries
        vault = wiki
    except SystemExit:
        raise
    except Exception as e:
        if args.json:
            print(json.dumps({"status": "error", "message": str(e)}))
        else:
            print(f"[error] {e}", file=sys.stderr)
        sys.exit(1)

    total = sum(len(v) for v in pages.values())
    summary = {
        "status": "ok",
        "wiki": str(wiki),
        "total_pages": total,
        "by_category": {k: len(v) for k, v in pages.items()},
        "dry_run": args.dry_run,
    }

    if args.dry_run:
        if args.json:
            print(json.dumps(summary, indent=2))
        else:
            print(f"[dry-run] would write per-folder sub-indexes for {total} pages")
        return

    written_cat_indexes = []
    for cat, fname in CATEGORY_INDEX_FILES.items():
        entries = pages.get(cat, [])
        if not entries:
            continue
        label = CATEGORY_LABELS.get(cat, cat.capitalize())
        cat_content = render_category_index(entries, cat, label, vault.name)
        cat_path = vault / fname
        cat_path.parent.mkdir(parents=True, exist_ok=True)
        try:
            cat_path.write_text(cat_content, encoding="utf-8")
        except OSError as e:
            if args.json:
                print(json.dumps({"status": "error", "message": f"failed to write {cat_path}: {e}"}))
            else:
                print(f"[warn] failed to write {cat_path}: {e}", file=sys.stderr)
        else:
            written_cat_indexes.append(fname)
            if not args.json:
                print(f"[ok] wrote {cat_path} ({len(entries)} pages)")

    if work_entries:
        work_index_path = wiki.parent / "work" / "index.md"
        work_index_content = render_category_index(
            work_entries, "work", CATEGORY_LABELS["work"], vault.name, location="work"
        )
        work_index_path.parent.mkdir(parents=True, exist_ok=True)
        try:
            work_index_path.write_text(work_index_content, encoding="utf-8")
        except OSError as e:
            if args.json:
                print(json.dumps({"status": "error", "message": f"failed to write {work_index_path}: {e}"}))
            else:
                print(f"[warn] failed to write {work_index_path}: {e}", file=sys.stderr)
        else:
            written_cat_indexes.append("work/index.md")
            if not args.json:
                print(f"[ok] wrote {work_index_path} ({len(work_entries)} pages)")

    summary["category_indexes_written"] = written_cat_indexes
    if args.json:
        print(json.dumps(summary, indent=2))
    else:
        print(
            f"[ok] wrote {len(written_cat_indexes)} sub-index file(s) "
            f"({total} pages); main index is now owned by wiki_io.index_generator"
        )


if __name__ == "__main__":
    main()
```

Do not remove `import sys`; `scan_vault()` still prints an error to stderr and exits when the wiki directory is missing.

- [ ] **Step 2: Remove executable-only code from `update_tokens.py`**

In `packages/wiki-io/src/wiki_io/update_tokens.py`, remove the first shebang line, remove the `Usage:` lines from the module docstring, remove these imports:

```python
import argparse
import json
```

Also remove:

```python
from wiki_io._workspace import resolve_wiki_and_repo
```

Delete:

```python
def main() -> None:
    p = argparse.ArgumentParser(description="Stamp `tokens` frontmatter across the wiki")
    p.add_argument("--dry-run", action="store_true", help="Print changes without writing")
    p.add_argument("--json", action="store_true", help="Machine-readable output")
    p.add_argument("--model-id", default=DEFAULT_MODEL_ID, help="Bedrock model ID for token counting")
    p.add_argument("--region", default=DEFAULT_REGION, help="AWS region for Bedrock")
    args = p.parse_args()

    wiki, _ = resolve_wiki_and_repo()
    result = update_vault(wiki, dry_run=args.dry_run, model_id=args.model_id, region=args.region)

    if args.json:
        print(json.dumps(result, indent=2))
        return

    label = "Would update" if args.dry_run else "Updated"
    print(f"{label} {len(result['updated'])} • Unchanged {len(result['unchanged'])} • Skipped {len(result['skipped'])}")
    for kind in ("updated", "skipped"):
        for rel in result[kind][:20]:
            print(f"  [{kind}] {rel}")


if __name__ == "__main__":
    main()
```

- [ ] **Step 3: Remove executable-only code from `append_log.py`**

In `packages/wiki-io/src/wiki_io/append_log.py`, remove the first shebang line, remove the `Usage:` and `Valid ops:` blocks from the module docstring, remove:

```python
import argparse
from wiki_io._workspace import resolve_wiki_and_repo
```

Delete:

```python
def main():
    p = argparse.ArgumentParser(description="Append a standardized entry to wiki/log.md")
    p.add_argument("--op", required=True, choices=sorted(VALID_OPS))
    p.add_argument("--title", required=True)
    p.add_argument("--detail", default=None)
    p.add_argument("--json", action="store_true")
    args = p.parse_args()
    wiki, _ = resolve_wiki_and_repo()
    append_log(
        wiki,
        args.op,
        args.title,
        args.detail,
        as_json=args.json,
    )


if __name__ == "__main__":
    main()
```

Do not change `_error()` or `append_log()`; `append_log(..., raise_exception=True)` must still raise `ValueError` instead of exiting.

- [ ] **Step 4: Run focused tests**

Run:

```bash
uv run --package wiki-io pytest \
  packages/wiki-io/tests/test_library_boundaries.py \
  packages/wiki-io/tests/test_update_index_surgical.py \
  packages/wiki-io/tests/test_update_tokens.py \
  packages/wiki-io/tests/test_ingest_work_item.py \
  -v
```

Expected: PASS for the Class A modules. The boundary test may still fail for Class B modules until later tasks; failures should name only `init_vault`, `ingest_source`, `wiki_search`, `lint_wiki`, or `graph_analyzer`.

- [ ] **Step 5: Commit Class A cleanup**

```bash
git add packages/wiki-io/src/wiki_io/update_index.py packages/wiki-io/src/wiki_io/update_tokens.py packages/wiki-io/src/wiki_io/append_log.py
git commit -m "refactor: remove class a wiki_io executable wrappers"
```

---

### Task 3: Add Plugin Claude-Branch Script Tests

**Files:**
- Create: `packages/graph-wiki-cli/tests/unit/test_plugin_claude_scripts.py`
- Test: `packages/graph-wiki-cli/tests/unit/test_plugin_claude_scripts.py`

- [ ] **Step 1: Write failing tests for plugin-owned parsing and output**

Create `packages/graph-wiki-cli/tests/unit/test_plugin_claude_scripts.py`:

```python
from __future__ import annotations

import json
import runpy
import sys
import types
from pathlib import Path

import pytest


_SCRIPT_DIR = (
    Path(__file__).resolve().parents[4]
    / "plugins"
    / "graph-wiki"
    / "skills"
    / "graph-wiki"
    / "scripts"
)


def _install_claude_backend(monkeypatch: pytest.MonkeyPatch) -> None:
    config_module = types.ModuleType("_config")
    config_module.backend_for = lambda command, repo=None: "claude"  # type: ignore[attr-defined]
    monkeypatch.setitem(sys.modules, "_config", config_module)
    monkeypatch.syspath_prepend(str(_SCRIPT_DIR))


def test_wiki_search_script_claude_branch_formats_json(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    _install_claude_backend(monkeypatch)
    workspace = tmp_path / "workspace"
    wiki = workspace / "wiki"
    page_dir = wiki / "concepts"
    page_dir.mkdir(parents=True)
    (page_dir / "auth.md").write_text(
        "---\ntitle: Auth\ncategory: concept\nsummary: auth pipeline\n---\n\nMiddleware pipeline details.\n",
        encoding="utf-8",
    )
    monkeypatch.setenv("GRAPH_WIKI_WORKSPACE", str(workspace))
    monkeypatch.setattr(sys, "argv", ["wiki_search.py", "--query", "middleware", "--limit", "3", "--json"])

    runpy.run_path(str(_SCRIPT_DIR / "wiki_search.py"), run_name="__main__")

    data = json.loads(capsys.readouterr().out)
    assert data["query"] == "middleware"
    assert data["hits"][0]["path"] == "concepts/auth.md"


def test_lint_wiki_script_claude_branch_validates_unknown_check(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    _install_claude_backend(monkeypatch)
    workspace = tmp_path / "workspace"
    (workspace / "wiki").mkdir(parents=True)
    monkeypatch.setenv("GRAPH_WIKI_WORKSPACE", str(workspace))
    monkeypatch.setattr(sys, "argv", ["lint_wiki.py", "--check", "missing"])

    with pytest.raises(SystemExit) as excinfo:
        runpy.run_path(str(_SCRIPT_DIR / "lint_wiki.py"), run_name="__main__")

    assert excinfo.value.code == 2
    assert "unknown --check group 'missing'" in capsys.readouterr().err


def test_graph_analyzer_script_claude_branch_formats_json(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    monkeypatch.syspath_prepend(str(_SCRIPT_DIR))
    workspace = tmp_path / "workspace"
    wiki = workspace / "wiki"
    wiki.mkdir(parents=True)
    (wiki / "a.md").write_text("---\ntitle: A\n---\n\n[[b]]\n", encoding="utf-8")
    (wiki / "b.md").write_text("---\ntitle: B\n---\n\nBody.\n", encoding="utf-8")
    monkeypatch.setenv("GRAPH_WIKI_WORKSPACE", str(workspace))
    monkeypatch.setattr(sys, "argv", ["graph_analyzer.py", "--json", "--top", "2"])

    runpy.run_path(str(_SCRIPT_DIR / "graph_analyzer.py"), run_name="__main__")

    data = json.loads(capsys.readouterr().out)
    assert data["total_pages"] == 2
    assert data["total_edges"] == 1


def test_ingest_source_script_claude_branch_emits_json_brief(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    _install_claude_backend(monkeypatch)
    workspace = tmp_path / "workspace"
    wiki = workspace / "wiki"
    wiki.mkdir(parents=True)
    source = workspace / "raw" / "notes" / "demo.md"
    source.parent.mkdir(parents=True)
    source.write_text("# Demo Source\n\nUseful source text.", encoding="utf-8")
    monkeypatch.setenv("GRAPH_WIKI_WORKSPACE", str(workspace))
    monkeypatch.setattr(
        sys,
        "argv",
        ["ingest_source.py", str(source), "--workspace", str(workspace), "--json"],
    )

    runpy.run_path(str(_SCRIPT_DIR / "ingest_source.py"), run_name="__main__")

    data = json.loads(capsys.readouterr().out)
    assert data["title"] == "Demo Source"
    assert data["suggested_summary_path"].startswith("sources/")
    assert data["entity_match"] == {"uri": None, "entity_filename": None}


def test_init_vault_script_claude_branch_calls_init_wiki(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    _install_claude_backend(monkeypatch)
    calls: list[dict[str, object]] = []

    module = types.ModuleType("wiki_io.init_vault")
    module.TOOL_FILES = {"claude-code": [], "codex": [], "all": []}  # type: ignore[attr-defined]

    def fake_init_wiki(wiki_path, repo_path, topic, tool, force, as_json=False, non_interactive=False):
        calls.append(
            {
                "wiki_path": wiki_path,
                "repo_path": repo_path,
                "topic": topic,
                "tool": tool,
                "force": force,
                "as_json": as_json,
                "non_interactive": non_interactive,
            }
        )
        result = {"status": "ok", "wiki_path": str(wiki_path), "repo_path": str(repo_path), "topic": topic}
        if as_json:
            print(json.dumps(result, indent=2))
        return result

    module.init_wiki = fake_init_wiki  # type: ignore[attr-defined]
    package = types.ModuleType("wiki_io")
    package.__path__ = []  # type: ignore[attr-defined]
    monkeypatch.setitem(sys.modules, "wiki_io", package)
    monkeypatch.setitem(sys.modules, "wiki_io.init_vault", module)

    repo = tmp_path / "repo"
    repo.mkdir()
    workspace = tmp_path / "workspace"
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "init_vault.py",
            "--repo",
            str(repo),
            "--workspace",
            str(workspace),
            "--topic",
            "Demo",
            "--tool",
            "claude-code",
            "--force",
            "--json",
        ],
    )

    runpy.run_path(str(_SCRIPT_DIR / "init_vault.py"), run_name="__main__")

    assert calls == [
        {
            "wiki_path": workspace / "wiki",
            "repo_path": repo,
            "topic": "Demo",
            "tool": "claude-code",
            "force": True,
            "as_json": True,
            "non_interactive": True,
        }
    ]
    assert json.loads(capsys.readouterr().out)["status"] == "ok"
```

- [ ] **Step 2: Run the new plugin tests to verify they fail**

Run:

```bash
uv run --package graph-wiki-cli pytest packages/graph-wiki-cli/tests/unit/test_plugin_claude_scripts.py -v
```

Expected: FAIL. Current scripts delegate Claude branch to `wiki_io.<module>.main`, and some fake modules in these tests intentionally expose only library functions.

- [ ] **Step 3: Commit the failing plugin tests**

```bash
git add packages/graph-wiki-cli/tests/unit/test_plugin_claude_scripts.py
git commit -m "test: capture plugin-owned claude script parsing"
```

---

### Task 4: Add Ingest Source Library Helpers

**Files:**
- Modify: `packages/wiki-io/src/wiki_io/ingest_source.py`
- Modify: `packages/wiki-io/tests/test_ingest_source_prep.py`
- Test: `packages/wiki-io/tests/test_ingest_source_prep.py`

- [ ] **Step 1: Update tests away from `prep.main()`**

In `packages/wiki-io/tests/test_ingest_source_prep.py`, replace each `prep.main()` call with direct helper calls.

For `test_prep_main_emits_brief_without_bedrock`, replace the argv setup and `prep.main()` block with:

```python
brief = prep.build_ingest_brief(
    source_path=Path(rel),
    wiki=wiki,
    repo=workspace,
    workspace_root=workspace,
)
```

For `test_prep_main_no_entity_match_has_null_fields`, replace the argv setup and `prep.main()` block with:

```python
brief = prep.build_ingest_brief(
    source_path=Path(rel),
    wiki=wiki,
    repo=workspace,
    workspace_root=workspace,
)
```

For `test_prep_main_folder_ingest_emits_brief`, replace the argv setup and `prep.main()` block with:

```python
brief = prep.build_folder_ingest_brief(
    source_path=folder,
    wiki=wiki,
    repo=workspace,
)
```

Rename `test_prep_main_is_importable` to `test_prep_module_exports_brief_builders` and replace its assertion with:

```python
assert callable(prep.build_ingest_brief)
assert callable(prep.build_folder_ingest_brief)
assert not hasattr(prep, "main")
```

Remove now-unused `json` and `capsys` usage from these tests as needed.

- [ ] **Step 2: Run the ingest prep tests to verify they fail**

Run:

```bash
uv run --package wiki-io pytest packages/wiki-io/tests/test_ingest_source_prep.py -v
```

Expected: FAIL with `AttributeError: module 'wiki_io.ingest_source' has no attribute 'build_ingest_brief'`.

- [ ] **Step 3: Add library helpers to `ingest_source.py`**

In `packages/wiki-io/src/wiki_io/ingest_source.py`, add these helpers after `_build_entity_match()` and before the current `main()`:

```python
def _resolve_source_path(source_path: Path, repo: Path) -> Path:
    if source_path.is_absolute():
        return source_path
    candidate = repo / source_path
    return candidate if candidate.exists() else source_path.resolve()


def build_folder_ingest_brief(source_path: Path, wiki: Path, repo: Path) -> dict:
    source_path = _resolve_source_path(source_path, repo)
    rel_to_wiki = None
    try:
        rel_to_wiki = source_path.relative_to(wiki)
    except ValueError:
        pass
    brief: dict = {
        "is_folder": True,
        **folder_brief(source_path, rel_to_wiki),
        "state_gate": compute_state_gate(repo),
    }
    return brief


def build_ingest_brief(source_path: Path, wiki: Path, repo: Path, workspace_root: Path) -> dict:
    source_path = _resolve_source_path(source_path, repo)
    text, title = extract(source_path)
    title_guess = title or source_path.stem.replace("-", " ").title()
    slug = slugify(title_guess)

    rel_to_wiki = None
    rel_to_repo = None
    try:
        rel_to_wiki = source_path.relative_to(wiki)
    except ValueError:
        pass
    try:
        rel_to_repo = source_path.relative_to(repo)
    except ValueError:
        pass
    source_type = guess_source_type(rel_to_wiki, rel_to_repo)

    preview = text[:PREVIEW_CHARS]
    if len(text) > PREVIEW_CHARS:
        preview += "\n[TRUNCATED]"

    month = datetime.date.today().strftime("%Y-%m")
    suggested = f"sources/{month}-{slug}.md"
    page_exists = (wiki / suggested).exists()
    in_repo_doc = rel_to_repo is not None and rel_to_wiki is None

    return {
        "source_path": str(source_path),
        "title": title_guess,
        "source_type": source_type,
        "slug": slug,
        "preview": preview,
        "word_count": len(text.split()),
        "suggested_summary_path": suggested,
        "merge_mode": page_exists,
        "in_repo_doc": in_repo_doc,
        "entity_match": _build_entity_match(workspace_root, repo, source_path, title_guess),
        "state_gate": compute_state_gate(repo),
    }
```

- [ ] **Step 4: Remove `ingest_source.py` executable wrapper**

Still in `packages/wiki-io/src/wiki_io/ingest_source.py`, remove:

```python
import argparse
import sys
```

Delete the current `main()` function entirely. Do not remove `json`; `extract()` uses it for JSON source files.

- [ ] **Step 5: Run ingest prep and boundary tests**

Run:

```bash
uv run --package wiki-io pytest \
  packages/wiki-io/tests/test_ingest_source_prep.py \
  packages/wiki-io/tests/test_ingest_source.py \
  packages/wiki-io/tests/test_library_boundaries.py \
  -v
```

Expected: ingest-source tests PASS. Boundary tests should still fail only for remaining Class B modules that have not been cleaned.

- [ ] **Step 6: Commit ingest helper extraction**

```bash
git add packages/wiki-io/src/wiki_io/ingest_source.py packages/wiki-io/tests/test_ingest_source_prep.py
git commit -m "refactor: expose ingest brief builders"
```

---

### Task 5: Invert Plugin Scripts and Remove Class B Executable Wrappers

**Files:**
- Modify: `plugins/graph-wiki/skills/graph-wiki/scripts/init_vault.py`
- Modify: `plugins/graph-wiki/skills/graph-wiki/scripts/ingest_source.py`
- Modify: `plugins/graph-wiki/skills/graph-wiki/scripts/wiki_search.py`
- Modify: `plugins/graph-wiki/skills/graph-wiki/scripts/lint_wiki.py`
- Modify: `plugins/graph-wiki/skills/graph-wiki/scripts/graph_analyzer.py`
- Modify: `packages/wiki-io/src/wiki_io/init_vault.py`
- Modify: `packages/wiki-io/src/wiki_io/wiki_search.py`
- Modify: `packages/wiki-io/src/wiki_io/lint_wiki.py`
- Modify: `packages/wiki-io/src/wiki_io/graph_analyzer.py`
- Modify: `packages/wiki-io/tests/test_wiki_search.py`
- Modify: `packages/wiki-io/tests/test_lint_wiki.py`
- Modify: `packages/graph-wiki-cli/tests/unit/test_plugin_bedrock_shims.py`
- Test: `packages/graph-wiki-cli/tests/unit/test_plugin_claude_scripts.py`
- Test: `packages/graph-wiki-cli/tests/unit/test_plugin_bedrock_shims.py`
- Test: `packages/wiki-io/tests/test_library_boundaries.py`

- [ ] **Step 1: Replace `plugins/.../scripts/init_vault.py`**

Replace the full file with:

```python
#!/usr/bin/env python3
"""Plugin script for Graph Wiki vault bootstrap."""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path

from _uv_reexec import ensure as _ensure_uv

_ensure_uv()


def _backend_for(command: str) -> str:
    try:
        from _config import backend_for
    except ImportError:
        return "claude"
    return backend_for(command)


def _run_bedrock() -> None:
    result = subprocess.run(["gw", "bootstrap"] + sys.argv[1:], check=True)
    sys.exit(result.returncode)


def main() -> None:
    if _backend_for("init") == "bedrock":
        _run_bedrock()

    from wiki_io.init_vault import TOOL_FILES, init_wiki
    from wiki_io._workspace import resolve_wiki_and_repo

    parser = argparse.ArgumentParser(description="Bootstrap a Code Wiki")
    parser.add_argument("--topic", required=True)
    parser.add_argument("--tool", default="claude-code", choices=sorted(TOOL_FILES))
    parser.add_argument("--force", action="store_true")
    parser.add_argument("--json", action="store_true", dest="json_output")
    parser.add_argument("--workspace", default="", help="Workspace path; defaults to graph-wiki resolution")
    parser.add_argument("--repo", default="", help="Source repo path; defaults to graph-wiki resolution")
    args = parser.parse_args()

    workspace_path = Path(args.workspace).expanduser().resolve() if args.workspace else None
    repo_arg = Path(args.repo).expanduser().resolve() if args.repo else None
    if workspace_path is None or repo_arg is None:
        wiki, resolved_repo = resolve_wiki_and_repo(workspace_path)
        repo_path = repo_arg or resolved_repo or Path.cwd()
    else:
        wiki = workspace_path / "wiki"
        repo_path = repo_arg

    result = init_wiki(
        wiki,
        repo_path,
        topic=args.topic,
        tool=args.tool,
        force=args.force,
        as_json=args.json_output,
        non_interactive=True,
    )
    if args.json_output and result is not None:
        # init_wiki already prints JSON when as_json=True. Keep this guard for fake
        # test doubles that return a result without printing.
        pass


if __name__ == "__main__":
    main()
```

- [ ] **Step 2: Replace `plugins/.../scripts/ingest_source.py`**

Replace the full file with:

```python
#!/usr/bin/env python3
"""Plugin script for preparing a source ingestion brief."""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path

from _uv_reexec import ensure as _ensure_uv

_ensure_uv()


def _backend_for(command: str) -> str:
    try:
        from _config import backend_for
    except ImportError:
        return "claude"
    return backend_for(command)


def _run_bedrock() -> None:
    result = subprocess.run(["gw", "wiki", "ingest", "source"] + sys.argv[1:], check=True)
    sys.exit(result.returncode)


def main() -> None:
    if _backend_for("ingest") == "bedrock":
        _run_bedrock()

    from wiki_io._workspace import resolve_wiki_and_repo
    from wiki_io.ingest_source import build_folder_ingest_brief, build_ingest_brief

    parser = argparse.ArgumentParser(description="Prepare a source for ingestion.")
    parser.add_argument("source", nargs="?", default=None, help="Path to the source file/folder")
    parser.add_argument("--source", dest="source_opt", default=None, help="Path to the source (alt form)")
    parser.add_argument("--workspace", default="", help="Workspace path (default: env / git heuristic)")
    parser.add_argument("--json", action="store_true", dest="json_output", help="Emit JSON brief")
    args = parser.parse_args()

    source_arg = args.source_opt or args.source
    if not source_arg:
        print("[error] no source path given", file=sys.stderr)
        sys.exit(1)

    workspace_path = Path(args.workspace).expanduser().resolve() if args.workspace else None
    wiki, repo = resolve_wiki_and_repo(workspace_path)
    if repo is None:
        repo = Path.cwd()
    workspace_root = workspace_path if workspace_path is not None else wiki.parent
    source_path = Path(source_arg)

    if source_path.is_dir():
        brief = build_folder_ingest_brief(source_path=source_path, wiki=wiki, repo=repo)
        if "_error" in brief:
            print(f"[error] {brief['_error']}", file=sys.stderr)
            sys.exit(1)
    else:
        brief = build_ingest_brief(
            source_path=source_path,
            wiki=wiki,
            repo=repo,
            workspace_root=workspace_root,
        )

    if args.json_output:
        print(json.dumps(brief, indent=2))
        return

    if brief.get("is_folder"):
        print(f"Folder: {source_path}")
        print(f"Files: {brief['file_count']}")
        print(f"Representative: {brief['representative_file']}")
        return

    print(f"Title: {brief['title']}")
    print(f"Source type: {brief['source_type']}")
    print(f"Suggested summary: {brief['suggested_summary_path']}")
    entity_match = brief["entity_match"]
    if entity_match["uri"]:
        print(f"Entity match: {entity_match['uri']} -> [[entities/{entity_match['entity_filename']}]]")


if __name__ == "__main__":
    main()
```

- [ ] **Step 3: Replace `plugins/.../scripts/wiki_search.py`**

Replace the full file with:

```python
#!/usr/bin/env python3
"""Plugin script for BM25 wiki search."""

from __future__ import annotations

import argparse
import json
import subprocess
import sys

from _uv_reexec import ensure as _ensure_uv

_ensure_uv()


def _backend_for(command: str) -> str:
    try:
        from _config import backend_for
    except ImportError:
        return "claude"
    return backend_for(command)


def _run_bedrock() -> None:
    result = subprocess.run(["gw", "wiki", "query"] + sys.argv[1:], check=True)
    sys.exit(result.returncode)


def main() -> None:
    if _backend_for("query") == "bedrock":
        _run_bedrock()

    from wiki_io._workspace import resolve_wiki_and_repo
    from wiki_io.wiki_search import bm25_scores, load_docs, snippet, tokenize

    parser = argparse.ArgumentParser(description="BM25 search over a Code Wiki")
    parser.add_argument("--query", required=True)
    parser.add_argument("--limit", type=int, default=10)
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()

    wiki, _ = resolve_wiki_and_repo()
    docs = load_docs(wiki)
    qtokens = tokenize(args.query)
    if not qtokens:
        print("[error] empty query after tokenization", file=sys.stderr)
        sys.exit(1)

    scored = bm25_scores(docs, qtokens)[: args.limit]
    hits = []
    for i, score in scored:
        doc = docs[i]
        hits.append(
            {
                "path": doc["path"],
                "score": round(score, 3),
                "snippet": snippet(doc["text"], qtokens),
            }
        )

    if args.json:
        print(json.dumps({"query": args.query, "hits": hits}, indent=2, ensure_ascii=False))
        return

    if not hits:
        print(f"No matches for: {args.query}")
        return
    print(f"Query: {args.query}  ({len(hits)} hits)")
    for hit in hits:
        print(f"\n  [{hit['score']}] {hit['path']}")
        print(f"     {hit['snippet']}")


if __name__ == "__main__":
    main()
```

- [ ] **Step 4: Replace `plugins/.../scripts/lint_wiki.py`**

Replace the full file with:

```python
#!/usr/bin/env python3
"""Plugin script for wiki lint checks."""

from __future__ import annotations

import argparse
import json
import subprocess
import sys

from _uv_reexec import ensure as _ensure_uv

_ensure_uv()


def _backend_for(command: str) -> str:
    try:
        from _config import backend_for
    except ImportError:
        return "claude"
    return backend_for(command)


def _run_bedrock() -> None:
    result = subprocess.run(["gw", "wiki", "lint"] + sys.argv[1:], check=True)
    sys.exit(result.returncode)


def main() -> None:
    if _backend_for("lint") == "bedrock":
        _run_bedrock()

    from wiki_io._workspace import resolve_wiki_and_repo
    from wiki_io.lint_wiki import OPTIONAL_GROUPS, print_report, scan

    parser = argparse.ArgumentParser(description="Lint a Code Wiki (with code-drift detection)")
    parser.add_argument("--stale-days", type=int, default=90)
    parser.add_argument("--log-gap-days", type=int, default=14)
    parser.add_argument("--json", action="store_true")
    parser.add_argument(
        "--check",
        default="",
        help=(
            "Comma-separated optional check groups to enable in addition to the "
            "default set. Available: " + ",".join(sorted(OPTIONAL_GROUPS))
        ),
    )
    args = parser.parse_args()

    optional_checks: set[str] = set()
    if args.check:
        for name in args.check.split(","):
            name = name.strip()
            if not name:
                continue
            if name not in OPTIONAL_GROUPS:
                print(
                    f"[error] unknown --check group '{name}' (known: {','.join(sorted(OPTIONAL_GROUPS))})",
                    file=sys.stderr,
                )
                sys.exit(2)
            optional_checks.add(name)

    wiki, repo_path = resolve_wiki_and_repo()
    report = scan(
        wiki,
        stale_days=args.stale_days,
        log_gap_days=args.log_gap_days,
        repo_path=repo_path,
        optional_checks=optional_checks,
    )
    if args.json:
        print(json.dumps(report, indent=2, default=list))
    else:
        print_report(report)


if __name__ == "__main__":
    main()
```

- [ ] **Step 5: Replace `plugins/.../scripts/graph_analyzer.py`**

Replace the full file with:

```python
#!/usr/bin/env python3
"""Plugin script for wiki graph analysis."""

from __future__ import annotations

import argparse
import json

from _uv_reexec import ensure as _ensure_uv

_ensure_uv()


def main() -> None:
    from wiki_io._workspace import resolve_wiki_and_repo
    from wiki_io.graph_analyzer import analyze

    parser = argparse.ArgumentParser(description="Analyze the wikilink graph of a Code Wiki")
    parser.add_argument("--top", type=int, default=10)
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()

    wiki, _ = resolve_wiki_and_repo()
    result = analyze(wiki, args.top)

    if args.json:
        print(json.dumps(result, indent=2, default=list))
        return

    print(f"Code Wiki graph — {result['total_pages']} pages, {result['total_edges']} links")
    print(f"Connected components: {result['component_count']}")
    print()
    print("Top outbound hubs:")
    for hub in result["top_outbound_hubs"]:
        print(f"  - {hub['page']}  ({hub['outbound']} out)")
    print()
    print("Top inbound hubs:")
    for hub in result["top_inbound_hubs"]:
        print(f"  - {hub['page']}  ({hub['inbound']} in)")
    print()
    print(f"Orphans (no inbound): {len(result['orphans'])}")
    for orphan in result["orphans"][:10]:
        print(f"  - {orphan}")
    print()
    print(f"Sinks (no outbound): {len(result['sinks'])}")
    for sink in result["sinks"][:10]:
        print(f"  - {sink}")


if __name__ == "__main__":
    main()
```

- [ ] **Step 6: Remove executable-only code from `init_vault.py`**

In `packages/wiki-io/src/wiki_io/init_vault.py`, remove the shebang and executable usage docstring block. Remove:

```python
import argparse
from wiki_io._workspace import resolve_wiki_and_repo
```

Delete its `main()` function and `if __name__ == "__main__":` guard. Keep `import json`; `_error()` and `init_wiki(..., as_json=True)` use it.

- [ ] **Step 7: Remove executable-only code from `wiki_search.py`**

In `packages/wiki-io/src/wiki_io/wiki_search.py`, remove the shebang and executable usage docstring block. Remove:

```python
import argparse
import json
import sys
from wiki_io._workspace import resolve_wiki_and_repo
```

Delete `main()` and the `if __name__ == "__main__":` guard. Keep `load_docs()`, `tokenize()`, `bm25_scores()`, and `snippet()` unchanged.

- [ ] **Step 8: Remove executable-only code from `lint_wiki.py`**

In `packages/wiki-io/src/wiki_io/lint_wiki.py`, remove the shebang and executable usage docstring block. Remove:

```python
import argparse
import json
import sys
from wiki_io._workspace import resolve_wiki_and_repo
```

Delete `main()` and the `if __name__ == "__main__":` guard. Keep `scan()`, `print_report()`, `OPTIONAL_GROUPS`, and all check imports unchanged.

- [ ] **Step 9: Remove executable-only code from `graph_analyzer.py`**

In `packages/wiki-io/src/wiki_io/graph_analyzer.py`, remove the shebang and executable usage docstring block. Remove:

```python
import argparse
import json
from wiki_io._workspace import resolve_wiki_and_repo
```

Delete `main()` and the `if __name__ == "__main__":` guard. Keep `_parse_frontmatter_lists()`, `build_graph()`, `connected_components()`, and `analyze()` unchanged.

- [ ] **Step 10: Update `test_wiki_search.py` for library-only module**

In `packages/wiki-io/tests/test_wiki_search.py`, remove imports of `json`, `subprocess`, and `sys`. Replace `test_wiki_search_importable()` with:

```python
def test_wiki_search_importable():
    """wiki_io.wiki_search imports cleanly and exports library helpers."""
    from wiki_io.wiki_search import bm25_scores, load_docs, snippet, tokenize

    assert callable(tokenize)
    assert callable(load_docs)
    assert callable(bm25_scores)
    assert callable(snippet)
```

Delete `test_wiki_search_runs_on_fixture_vault()`. The executable behavior is now covered by `test_plugin_claude_scripts.py`.

- [ ] **Step 11: Update `test_lint_wiki.py` for library-only module**

Replace `test_lint_wiki_importable()` with:

```python
def test_lint_wiki_importable() -> None:
    """wiki_io.lint_wiki exports scan/report library helpers."""
    from wiki_io.lint_wiki import print_report, scan

    assert callable(print_report)
    assert callable(scan)
```

- [ ] **Step 12: Update Bedrock shim tests so fake `wiki_io` modules do not expose `main`**

In `packages/graph-wiki-cli/tests/unit/test_plugin_bedrock_shims.py`, change `_install_fake_wiki_io()` to install empty fake modules:

```python
def _install_fake_wiki_io(monkeypatch: pytest.MonkeyPatch) -> None:
    """Provide import-only wiki_io modules; Bedrock tests must never call them."""
    package = types.ModuleType("wiki_io")
    package.__path__ = []  # type: ignore[attr-defined]
    monkeypatch.setitem(sys.modules, "wiki_io", package)

    for name in ("scan_monorepo", "init_vault", "ingest_source", "lint_wiki", "wiki_search", "graph_analyzer"):
        module = types.ModuleType(f"wiki_io.{name}")
        monkeypatch.setitem(sys.modules, f"wiki_io.{name}", module)
```

- [ ] **Step 13: Run plugin and wiki boundary tests**

Run:

```bash
uv run --package graph-wiki-cli pytest \
  packages/graph-wiki-cli/tests/unit/test_plugin_claude_scripts.py \
  packages/graph-wiki-cli/tests/unit/test_plugin_bedrock_shims.py \
  -v
```

Expected: PASS.

Run:

```bash
uv run --package wiki-io pytest \
  packages/wiki-io/tests/test_library_boundaries.py \
  packages/wiki-io/tests/test_wiki_search.py \
  packages/wiki-io/tests/test_lint_wiki.py \
  packages/wiki-io/tests/test_init_vault.py \
  packages/wiki-io/tests/test_ingest_source_prep.py \
  -v
```

Expected: PASS.

- [ ] **Step 14: Run static plugin import check**

Run:

```bash
rg -n "from wiki_io\\..* import main|import main" plugins/graph-wiki/skills/graph-wiki/scripts
```

Expected: no output.

- [ ] **Step 15: Commit plugin inversion and Class B cleanup**

```bash
git add \
  plugins/graph-wiki/skills/graph-wiki/scripts/init_vault.py \
  plugins/graph-wiki/skills/graph-wiki/scripts/ingest_source.py \
  plugins/graph-wiki/skills/graph-wiki/scripts/wiki_search.py \
  plugins/graph-wiki/skills/graph-wiki/scripts/lint_wiki.py \
  plugins/graph-wiki/skills/graph-wiki/scripts/graph_analyzer.py \
  packages/wiki-io/src/wiki_io/init_vault.py \
  packages/wiki-io/src/wiki_io/wiki_search.py \
  packages/wiki-io/src/wiki_io/lint_wiki.py \
  packages/wiki-io/src/wiki_io/graph_analyzer.py \
  packages/wiki-io/tests/test_wiki_search.py \
  packages/wiki-io/tests/test_lint_wiki.py \
  packages/graph-wiki-cli/tests/unit/test_plugin_bedrock_shims.py
git commit -m "refactor: invert graph wiki plugin script shims"
```

---

### Task 6: Remove workspace_io.config Executable Surface

**Files:**
- Modify: `packages/workspace-io/src/workspace_io/config.py`
- Modify: `packages/workspace-io/tests/test_config.py`
- Test: `packages/workspace-io/tests/test_config.py`

- [ ] **Step 1: Replace the CLI test with direct `resolve()` coverage**

In `packages/workspace-io/tests/test_config.py`, remove:

```python
def test_cli_prints_workspace_to_stdout(tmp_path):
    repo = _make_repo(tmp_path)
    _seed_manifest(repo / "graph-wiki")
    result = subprocess.run(
        [sys.executable, "-m", "workspace_io.config"],
        cwd=str(repo),
        capture_output=True,
        text=True,
        check=True,
    )
    assert result.stdout.strip() == str((repo / "graph-wiki").resolve())
```

Add:

```python
def test_resolve_returns_workspace_path_for_repo(tmp_path, monkeypatch):
    monkeypatch.delenv("GRAPH_WIKI_WORKSPACE", raising=False)
    repo = _make_repo(tmp_path)
    _seed_manifest(repo / "graph-wiki")
    assert resolve(repo).workspace == (repo / "graph-wiki").resolve()
```

Then remove unused imports:

```python
import subprocess
import sys
```

- [ ] **Step 2: Run test to verify current implementation still has executable code**

Run:

```bash
uv run --package workspace-io pytest packages/workspace-io/tests/test_config.py -v
```

Expected: PASS before code removal. This confirms the replacement test is valid and not tied to executable module behavior.

- [ ] **Step 3: Remove executable code from `workspace_io.config`**

In `packages/workspace-io/src/workspace_io/config.py`, remove:

```python
import sys
```

Delete:

```python
def _main() -> int:
    print(resolve().workspace)
    return 0


if __name__ == "__main__":
    sys.exit(_main())
```

- [ ] **Step 4: Run workspace tests and static check**

Run:

```bash
uv run --package workspace-io pytest packages/workspace-io/tests/test_config.py -v
```

Expected: PASS.

Run:

```bash
rg -n "def _main\\(|if __name__ == [\"']__main__[\"']|import sys" packages/workspace-io/src/workspace_io/config.py
```

Expected: no output.

- [ ] **Step 5: Commit workspace config cleanup**

```bash
git add packages/workspace-io/src/workspace_io/config.py packages/workspace-io/tests/test_config.py
git commit -m "refactor: remove workspace config module execution"
```

---

### Task 7: Delete wiki_io.link_rewriter and Tests

**Files:**
- Delete: `packages/wiki-io/src/wiki_io/link_rewriter.py`
- Delete: `packages/wiki-io/tests/test_link_rewriter.py`
- Delete: `packages/wiki-io/tests/test_link_rewriter_build_table.py`
- Delete: `packages/wiki-io/tests/integration/test_link_rewriter_integration.py`
- Modify: `packages/wiki-io/src/wiki_io/lint/common.py`
- Test: `packages/wiki-io/tests/test_lint_common_indented_code.py`

- [ ] **Step 1: Remove stale comment reference**

In `packages/wiki-io/src/wiki_io/lint/common.py`, replace the `strip_code()` docstring sentence:

```python
Per CommonMark §4.4; used by ``wiki_io.link_rewriter.rewrite_text`` to
```

with:

```python
Per CommonMark §4.4; used before parsing wikilinks so links inside code
```

- [ ] **Step 2: Delete the dead module and tests**

Run:

```bash
git rm \
  packages/wiki-io/src/wiki_io/link_rewriter.py \
  packages/wiki-io/tests/test_link_rewriter.py \
  packages/wiki-io/tests/test_link_rewriter_build_table.py \
  packages/wiki-io/tests/integration/test_link_rewriter_integration.py
```

Expected: all four paths are staged as deleted.

- [ ] **Step 3: Run link-rewriter reference check**

Run:

```bash
rg -n "wiki_io\\.link_rewriter|link_rewriter" packages/wiki-io/src packages/wiki-io/tests
```

Expected: no output.

- [ ] **Step 4: Run focused wiki-io tests**

Run:

```bash
uv run --package wiki-io pytest packages/wiki-io/tests/test_lint_common_indented_code.py packages/wiki-io/tests/test_lint_wiki.py -v
```

Expected: PASS.

- [ ] **Step 5: Commit dead-feature deletion**

```bash
git add packages/wiki-io/src/wiki_io/lint/common.py
git commit -m "refactor: delete dead wiki link rewriter"
```

---

### Task 8: Correct Cleanup Backlog

**Files:**
- Modify: `docs/cleanup-backlog.md`
- Test: `docs/cleanup-backlog.md`

- [ ] **Step 1: Update Part 1 summary and ground rule**

In `docs/cleanup-backlog.md`, update the Part 1 sections so they state:

```markdown
## Part 1 status after cleanup-boundary pass

The Part 1 boundary violations have been resolved:

- `wiki-io` keeps importable behavior and no longer owns command-line parsing or `__main__` blocks for the audited modules.
- Graph Wiki plugin scripts are the allowed executable delivery surface for the Claude-hosted plugin branch.
- `workspace_io.config` is import-only; `python -m workspace_io.config` is not a supported surface.
- `wiki_io.link_rewriter` was deleted because the migrate-vault feature hook is intentionally absent.

The cleanup target is a library/executable boundary, not deleting every symbol without a production caller.
```

- [ ] **Step 2: Correct retained API decisions**

In the Part 1 dead-code and prioritized backlog sections, replace the stale deletion guidance with:

```markdown
### Retained intentional APIs

- `workspace_io.versions` is retained as a reserved manifest/plugin update-state API. It remains unwired in command-entry checks in this pass, but it is backed by manifest schema behavior and focused tests.
- `graph_io.queries.list_entry_points` is retained as a symmetric public query helper for the `entry_point` node kind, alongside the other `list_*` query helpers.
- `wiki_io.graph_analyzer` is retained as importable library behavior. Only its executable parser/output wrapper moved to the plugin script.
```

- [ ] **Step 3: Remove completed or reversed active backlog items**

Remove these active Part 1 backlog instructions:

```markdown
4. graph-io: remove `queries.list_entry_points` (`queries.py:895`) + its test references.
5. wiki-io: resolve `link_rewriter.py` — wire up `cg migrate-vault` or delete module + 2 tests.
6. wiki-io: relocate `graph_analyzer.py` wholesale to CLI/plugin (no library consumers).
7. workspace-io: remove `versions.py` + its 3 `__init__.py` re-exports (zero non-test consumers).
```

Replace them with:

```markdown
**High:** none remaining for Part 1 boundary cleanup.

**Low (style / surgical)**
1. graph-io: drop unused `ctx` params in `derived_edges` (x2) and `test_suites._emit_tests_edges`.
2. graph-io: unify warning channel (prefer `logging`); hoist `import_scan.py` sqlite3 import; normalize `render.py` json alias.
3. workspace-io: simplify the strict-manifest branch in `config.py`.
4. wiki-io: add type hints to legacy ports and consolidate duplicated frontmatter parsing where it remains useful.
```

- [ ] **Step 4: Run backlog consistency checks**

Run:

```bash
rg -n "remove `queries\\.list_entry_points`|remove `versions\\.py`|relocate `graph_analyzer\\.py` wholesale|wire up `cg migrate-vault`|delete module \\+ 2 tests" docs/cleanup-backlog.md
```

Expected: no output.

Run:

```bash
rg -n "workspace_io\\.versions|list_entry_points|graph_analyzer|link_rewriter" docs/cleanup-backlog.md
```

Expected: output mentions `workspace_io.versions`, `list_entry_points`, and `graph_analyzer` as retained or completed; `link_rewriter` appears only as deleted/completed, not as active work.

- [ ] **Step 5: Commit backlog correction**

```bash
git add docs/cleanup-backlog.md
git commit -m "docs: correct part 1 cleanup backlog"
```

---

### Task 9: Final Verification

**Files:**
- Verify: Part 1 package tests and static boundary checks

- [ ] **Step 1: Run package tests**

Run:

```bash
uv run --package wiki-io pytest
```

Expected: PASS.

Run:

```bash
uv run --package workspace-io pytest
```

Expected: PASS.

Run:

```bash
uv run --package graph-io pytest
```

Expected: PASS.

- [ ] **Step 2: Run plugin script tests**

Run:

```bash
uv run --package graph-wiki-cli pytest \
  packages/graph-wiki-cli/tests/unit/test_plugin_claude_scripts.py \
  packages/graph-wiki-cli/tests/unit/test_plugin_bedrock_shims.py \
  -v
```

Expected: PASS.

- [ ] **Step 3: Run static executable-boundary checks**

Run:

```bash
rg -n "^import argparse|^def main\\(|if __name__ == [\"']__main__[\"']" packages/wiki-io/src/wiki_io packages/workspace-io/src/workspace_io
```

Expected: no output for the audited `wiki_io` and `workspace_io` modules. If output appears from an unaudited module, compare it to the design spec before changing it.

Run:

```bash
rg -n "from wiki_io\\..* import main|import main" plugins/graph-wiki/skills/graph-wiki/scripts
```

Expected: no output.

- [ ] **Step 4: Run deleted-feature reference check**

Run:

```bash
rg -n "wiki_io\\.link_rewriter|from wiki_io import link_rewriter|link_rewriter" packages/wiki-io/src packages/wiki-io/tests
```

Expected: no output.

- [ ] **Step 5: Run formatter and linter**

Run:

```bash
uv run ruff check . && uv run ruff format
```

Expected: ruff check passes; ruff format reports files formatted or unchanged.

- [ ] **Step 6: Commit any formatting-only changes**

If `uv run ruff format` changed files, commit them:

```bash
git add packages docs plugins
git commit -m "style: format cleanup boundary changes"
```

If ruff made no changes, skip this commit.

---

## Self-Review

**Spec coverage:** The plan covers Class A wrapper removal, Class B plugin script inversion, `wiki_io.graph_analyzer` retention as library behavior, `workspace_io.config` executable removal, `wiki_io.link_rewriter` deletion, retained `workspace_io.versions`, retained `graph_io.queries.list_entry_points`, tests, static checks, and backlog correction.

**Instruction scan:** Each task includes concrete paths, commands, or code blocks where the executor needs them.

**Type consistency:** The helper names `build_ingest_brief()` and `build_folder_ingest_brief()` are introduced before plugin scripts use them. Plugin tests refer to the same script paths and arguments that implementation steps define. Retained library function names match the current modules.
