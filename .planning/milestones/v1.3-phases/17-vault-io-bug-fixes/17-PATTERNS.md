# Phase 17: vault-io Bug Fixes — Pattern Map

**Mapped:** 2026-05-19
**Files analyzed:** 8 (4 source edits, 4 new test files)
**Analogs found:** 8 / 8

## File Classification

| New/Modified File | Role | Data Flow | Closest Analog | Match Quality |
|-------------------|------|-----------|----------------|---------------|
| `packages/vault-io/src/vault_io/scan_monorepo.py` (`_load_existing_pages._collect`, lines 602–672) | library / filesystem-walker | batch-transform (rglob → dict) | self (extend in place); cross-reference `vault_io/lint/workflow_hints.py::_parse_workflow_hints` (lines 13–43) | exact |
| `packages/vault-io/src/vault_io/update_tokens.py` (`count_tokens`, lines 38–44) | library / external-API-client | request-response (boto3 → int) | self (in-place fix); shape verified against AWS docs | exact |
| `packages/vault-io/src/vault_io/detect_containers.py` (`detect()` lines 148–166, `main()` line 174–175) | library / pure-classifier | transform (Path → list[dict]) | self; reference `SKIP_DIRS` (line 33) as the conceptual neighbor | exact |
| `packages/vault-io/src/vault_io/init_vault.py` (`main()`, lines 305–306) | CLI entry | one-shot wiring | self; mirrors `update_tokens.py:175` | exact |
| `packages/vault-io/tests/test_scan_companion_fold.py` (NEW) | unit test | filesystem-fixture + assert | `tests/test_lint_modules.py` (`_load_pages` helper + `tmp_path` style) | role-match |
| `packages/vault-io/tests/test_update_tokens.py` (NEW) | unit test | mock boto3 + assert payload | `tests/test_ingest_work_item.py` (`unittest.mock.patch` + `assert_called_once_with`) | exact |
| `packages/vault-io/tests/integration/test_count_tokens_live.py` (NEW) | gated integration test | real-API call → int | `agents/graph-wiki-agent/tests/integration/test_bedrock_iam.py::test_make_llm_haiku_invoke` (lines 28–46) | exact |
| `packages/vault-io/tests/test_detect_containers.py` (NEW) | unit test | synthetic tmp_path monorepo + monkeypatch env | `tests/test_truncated_frontmatter.py` (`tmp_path` + targeted file build) + `agents/graph-wiki-agent/tests/conftest.py` (fixture path style) | role-match |

## Pattern Assignments

### `scan_monorepo._load_existing_pages._collect()` (library, batch-transform)

**Analog (in-place edit):** `packages/vault-io/src/vault_io/scan_monorepo.py:602-672`

**Existing iteration shape** (lines 623–638) — the edit site:
```python
def _collect(root, default_category):
    resolved = root.resolve() if root.exists() else root
    if resolved in walked or not root.exists():
        return
    walked.add(resolved)
    for md in root.rglob("*.md"):
        fm = _parse_frontmatter(_safe_read_text(md))
        name = fm.get("title") or md.stem
        category = fm.get("category", default_category)
        path_key = fm.get("app_path") if category == "app" else fm.get("package_path")
        pages[name] = { ... }
```

**Call sites the filter must thread through** (lines 640–655):
```python
_collect(vault / "apps", "app")
_collect(vault / "packages", "package")          # apply filter HERE
# layout-pinned containers:
for c in layout.get("containers", []):
    classification = c.get("classification")
    if classification not in ("package", "app"):
        continue
    vault_dir = c.get("vault_dir")
    _collect(vault / vault_dir, classification)  # filter ONLY when classification == "package"
```

**Companion source — reuse `_parse_workflow_hints`** from `lint/workflow_hints.py:13-43`:
```python
def _parse_workflow_hints(text: str) -> dict[str, list[str]]:
    """Handles multi-line block form:
        workflow_hints:
          brainstorming: [context.md]
          planning:      [api.md, patterns.md]
    """
    m = _FRONTMATTER_RE.match(text)
    if not m:
        return {}
    hints: dict[str, list[str]] = {}
    in_hints = False
    for line in m.group(1).splitlines():
        if line.rstrip() == "workflow_hints:":
            in_hints = True
            continue
        if in_hints:
            if line.startswith(" ") or line.startswith("\t"):
                stripped = line.strip()
                colon = stripped.find(":")
                if colon == -1:
                    continue
                phase = stripped[:colon].strip()
                rest = stripped[colon + 1:].strip()
                items = parse_inline_list(rest)
                if items:
                    hints[phase] = items
            else:
                in_hints = False
    return hints
```

Companion derivation pattern (from RESEARCH.md Pattern 1):
```python
from vault_io.lint.workflow_hints import _parse_workflow_hints

hints = _parse_workflow_hints(text)
companion_stems = {Path(p).stem for sub in hints.values() for p in sub}
# → {"context", "api", "patterns", "work"}
```

**Existing helpers to leave untouched:**
- `_parse_frontmatter` (lines 590–599) — already on the hot path
- `_safe_read_text` (referenced at line 629) — call already inside `_collect`
- `read_layout` (line 644) — already loaded for layout-pinned containers; do NOT add a new layout-block read for companions (per RESEARCH.md Pitfall 1 — workflow_hints is per-page, not in the layout block)

---

### `update_tokens.count_tokens()` (library, request-response)

**Analog (in-place edit):** `packages/vault-io/src/vault_io/update_tokens.py:38-44`

**Current (buggy) shape:**
```python
def count_tokens(text: str, model_id: str = DEFAULT_MODEL_ID, region: str = DEFAULT_REGION) -> int:
    client = boto3.client("bedrock-runtime", region_name=region)
    response = client.count_tokens(
        modelId=model_id,
        content=[{"text": text}],          # ← wrong: rejected by boto3
    )
    return response["inputTokenCount"]     # ← wrong: AWS returns "inputTokens"
```

**Target shape (RESEARCH.md Pattern 2 — verified against AWS docs):**
```python
def count_tokens(text: str, model_id: str = DEFAULT_MODEL_ID, region: str = DEFAULT_REGION) -> int:
    client = boto3.client("bedrock-runtime", region_name=region)
    response = client.count_tokens(
        modelId=model_id,
        input={
            "converse": {
                "messages": [
                    {"role": "user", "content": [{"text": text}]}
                ]
            }
        },
    )
    return response["inputTokens"]
```

**Module constants to reuse** (lines 34–35) — `DEFAULT_MODEL_ID = "us.anthropic.claude-haiku-4-5-20251001-v1:0"`, `DEFAULT_REGION = "us-east-1"`.

---

### `detect_containers.detect()` (library, transform)

**Analog (in-place edit):** `packages/vault-io/src/vault_io/detect_containers.py:148-166`

**Current signature:**
```python
def detect(repo_root: Path) -> list[dict]:
    repo_root = Path(repo_root).resolve()
    if not repo_root.exists():
        return []
    top = _immediate_subdirs(repo_root)
    records = [_classify_dir(d) for d in top]
    ...
```

**Target signature (RESEARCH.md Pattern 3):**
```python
def detect(repo_root: Path, workspace_path: Path | None = None) -> list[dict]:
    repo_root = Path(repo_root).resolve()
    if not repo_root.exists():
        return []

    # D-11 guard: only exclude when workspace is a proper subdir of repo_root
    exclude: Path | None = None
    if workspace_path is not None:
        wp = Path(workspace_path).resolve()
        if wp != repo_root and wp.parent == repo_root:
            exclude = wp

    top = [d for d in _immediate_subdirs(repo_root) if d.resolve() != exclude]
    records = [_classify_dir(d) for d in top]
    # ... rest unchanged
```

**CLI call-site update** (lines 174–180):
```python
# BEFORE:
wiki, _ = resolve_wiki_and_repo()
repo = wiki.parent  # v1: repo is always wiki's parent directory
...
records = detect(repo)

# AFTER:
wiki, repo = resolve_wiki_and_repo()
...
records = detect(repo, workspace_path=wiki.parent)
```

**Conceptual neighbor — leave untouched:** `SKIP_DIRS` (line 33) — static skip-set; the workspace exclusion is dynamic-per-call (a parameter, not a constant).

---

### `init_vault.main()` (CLI entry, one-shot)

**Analog (in-place edit):** `packages/vault-io/src/vault_io/init_vault.py:305-306`

**Current:**
```python
args = p.parse_args()
wiki, _ = resolve_wiki_and_repo()
repo = wiki.parent  # v1: repo is always wiki's parent directory
init_wiki(wiki, repo, ...)
```

**Target:**
```python
args = p.parse_args()
_, repo = resolve_wiki_and_repo()
# NOTE: keep `wiki` returned too if init_wiki needs it — read the surrounding
# code; the actual call signature is init_wiki(wiki, repo, ...) so likely:
wiki, repo = resolve_wiki_and_repo()
init_wiki(wiki, repo, ...)
```

**Resolution contract** (`_workspace.py:23-38`):
```python
def resolve_wiki_and_repo(vault_path: Path | None = None) -> tuple[Path, Path | None]:
    if vault_path is not None:
        return vault_path.resolve(), _find_repo_root(vault_path)
    cfg = _ws_config.resolve()
    return _ws_paths.wiki_dir(cfg.workspace), cfg.repo_root
```
The second return value is the workspace-aware repo root — already correct for both v1 and v2 layouts.

---

### `tests/test_scan_companion_fold.py` (NEW — unit test)

**Analog:** `packages/vault-io/tests/test_lint_modules.py` (fixture loading + tmp_path style) + the round-trip-vault fixture (`tests/fixtures/round-trip-vault/packages/lattice-curator-core/`).

**Import + header pattern** (from `test_lint_modules.py:10-14`):
```python
from __future__ import annotations

from pathlib import Path

import pytest

FIXTURES = Path(__file__).parent / "fixtures"
ROUND_TRIP_VAULT = FIXTURES / "round-trip-vault"
```

**Fixture vault is already structured for this test** — see `tests/fixtures/round-trip-vault/packages/lattice-curator-core/`:
```
lattice-curator-core.md   ← parent overview with workflow_hints in frontmatter
api.md
context.md
patterns.md
work.md
```

Verified the overview declares:
```yaml
workflow_hints:
  brainstorming: [context.md]
  planning:      [api.md, patterns.md]
  debugging:     [api.md, work.md]
```

(7 of 7 packages in the fixture follow this pattern — see `grep -c workflow_hints` output in scout notes.)

**Test shape — adapt from `test_round_trip.py:28-34`** for the load + assert idiom:
```python
def test_load_existing_skips_companions() -> None:
    from vault_io.scan_monorepo import _load_existing_pages

    pages = _load_existing_pages(ROUND_TRIP_VAULT)
    # Companion stems should not appear as top-level page keys
    for companion in ("api", "context", "patterns", "work"):
        assert companion not in pages, (
            f"Companion '{companion}' leaked into pages dict — companion folding broken"
        )
    # Parent overviews should still be present
    assert "lattice-curator-core" in pages
```

**Compute_diff regression test** — analog: existing scan tests imply this shape:
```python
def test_compute_diff_no_phantom_deletes() -> None:
    from vault_io.scan_monorepo import _load_existing_pages, compute_diff, discover_workspaces

    workspaces = discover_workspaces(<repo>)  # synthetic or fixture
    existing = _load_existing_pages(ROUND_TRIP_VAULT)
    diff = compute_diff(workspaces, existing)
    # Companions should not appear in the deleted list
    for companion in ("api", "context", "patterns", "work"):
        assert companion not in diff["deleted"]
```

**Apps-not-filtered guard** — fixture has no apps companions; synthetic tmp_path test (per `tests/conftest.py::vault_path`) constructs:
```python
@pytest.fixture
def vault_path(tmp_path: Path) -> Path:
    wiki = tmp_path / "wiki"
    wiki.mkdir()
    return wiki
```
Then writes `wiki/apps/<app>/api.md` and asserts it IS present in `pages` (apps don't fold).

**Fixture extension site:** `tests/conftest.py` already has `tmp_repo`, `vault_path`, `round_trip_vault` fixtures — extend rather than redefine.

---

### `tests/test_update_tokens.py` (NEW — unit test)

**Analog:** `packages/vault-io/tests/test_ingest_work_item.py:1-12, 159-202` — the `unittest.mock.patch` + `assert_called_once_with` pattern.

**Import + mock setup pattern** (from `test_ingest_work_item.py:1-12`):
```python
from __future__ import annotations

"""Tests for vault_io.update_tokens — Bedrock CountTokens API shape.

Requirements: TOK-01, TOK-02 (mocked).
"""

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
```

**Mock pattern** (derived from `test_ingest_work_item.py:166-201`):
```python
def test_count_tokens_request_shape() -> None:
    from vault_io.update_tokens import count_tokens

    fake_client = MagicMock()
    fake_client.count_tokens.return_value = {"inputTokens": 42}

    with patch("vault_io.update_tokens.boto3.client", return_value=fake_client) as mock_factory:
        result = count_tokens("hello world", model_id="m1", region="us-east-1")

    mock_factory.assert_called_once_with("bedrock-runtime", region_name="us-east-1")
    fake_client.count_tokens.assert_called_once_with(
        modelId="m1",
        input={
            "converse": {
                "messages": [
                    {"role": "user", "content": [{"text": "hello world"}]}
                ]
            }
        },
    )
    assert result == 42
```

**Why this analog:** `test_ingest_work_item.py:166-201` uses the same `patch("vault_io.<module>.<symbol>")` style with `MagicMock` and `assert_called_once_with` — it's the canonical vault-io test idiom. No vault-io test uses `botocore.stub.Stubber`; consistency favors `unittest.mock.patch`.

---

### `tests/integration/test_count_tokens_live.py` (NEW — gated integration test)

**Analog:** `agents/graph-wiki-agent/tests/integration/test_bedrock_iam.py:28-46` — verbatim INTEGRATION_GATE pattern.

**Required directory creation:** `packages/vault-io/tests/integration/` does NOT exist; create it with an `__init__.py` (see `agents/graph-wiki-agent/tests/integration/__init__.py` as the reference — it exists as an empty package marker).

**Canonical decorator block** (verbatim from `test_bedrock_iam.py:30-35` + `docs/testing.md:53-56`):
```python
"""Gated integration test for vault_io.update_tokens.count_tokens.

Lives in tests/integration/ and is skipped unless GRAPH_WIKI_RUN_INTEGRATION=1.
Per docs/testing.md §3.

Requirements: TOK-02 (live).
"""

from __future__ import annotations

import os

import pytest

# Canonical GRAPH_WIKI_RUN_INTEGRATION gate — matches docs/testing.md verbatim
# so the docs/testing.md grep gate sees this file as canonical.
INTEGRATION_GATE = pytest.mark.skipif(
    not os.environ.get("GRAPH_WIKI_RUN_INTEGRATION"),
    reason="Set GRAPH_WIKI_RUN_INTEGRATION=1 to run real Bedrock invocations",
)


@pytest.mark.integration
@INTEGRATION_GATE
def test_count_tokens_real_bedrock() -> None:
    """Calls real Bedrock when GRAPH_WIKI_RUN_INTEGRATION=1; otherwise skips."""
    from vault_io.update_tokens import count_tokens

    n = count_tokens("hello world")
    assert isinstance(n, int) and n > 0
```

**Pattern notes:**
- Apply BOTH `@pytest.mark.integration` AND `@INTEGRATION_GATE` (per `test_bedrock_iam.py:38-40`). The `integration` mark groups it for selective runs; the GATE provides the env-var opt-in.
- Define `INTEGRATION_GATE` locally in this file rather than importing from `agents/graph-wiki-agent/tests/conftest.py` — that conftest is package-scoped to graph-wiki-agent; vault-io tests cannot import from it. `docs/testing.md` explicitly says "import this from conftest or redefine it locally — either is fine."
- Function-level decorator, not module-level `pytestmark` (per `test_bedrock_iam.py` docstring: "Per-function marking … keeps the mock test out of the integration set").

---

### `tests/test_detect_containers.py` (NEW — unit test)

**Analog:** `tests/test_truncated_frontmatter.py:11-28` (tmp_path + targeted file build) + RESEARCH.md fixture pattern.

**Header + fixture pattern** (from `test_truncated_frontmatter.py:9-12` and the WSRES fixture in RESEARCH.md):
```python
from __future__ import annotations

from pathlib import Path

import pytest


@pytest.fixture
def v2_workspace(tmp_path: Path, monkeypatch):
    """v2-layout fixture: repo with graph-wiki/ workspace child."""
    repo = tmp_path / "repo"
    (repo / "graph-wiki" / "wiki").mkdir(parents=True)
    (repo / "graph-wiki" / ".graph-wiki.yaml").write_text("plugins: []\n")
    (repo / "packages" / "pkg-a").mkdir(parents=True)
    (repo / "packages" / "pkg-a" / "pyproject.toml").write_text('[project]\nname="a"\n')
    (repo / "packages" / "pkg-b").mkdir(parents=True)
    (repo / "packages" / "pkg-b" / "pyproject.toml").write_text('[project]\nname="b"\n')
    (repo / ".git").mkdir()
    monkeypatch.setenv("GRAPH_WIKI_WORKSPACE", str(repo / "graph-wiki"))
    return {"repo": repo, "workspace": repo / "graph-wiki"}
```

**v2 layout test:**
```python
def test_v2_layout_packages_found_workspace_excluded(v2_workspace) -> None:
    from vault_io.detect_containers import detect

    repo = v2_workspace["repo"]
    workspace = v2_workspace["workspace"]
    records = detect(repo, workspace_path=workspace)

    sources = {r["source"] for r in records}
    assert "packages" in sources
    assert "graph-wiki" not in sources

    packages_rec = next(r for r in records if r["source"] == "packages")
    assert packages_rec["classification"] == "package"
```

**v1-layout guard test** (D-11):
```python
def test_v1_layout_guard_no_self_exclusion(tmp_path: Path, monkeypatch):
    """When workspace == repo (v1 layout), the exclusion guard must not fire."""
    from vault_io.detect_containers import detect

    repo = tmp_path / "repo"
    (repo / "wiki").mkdir(parents=True)
    (repo / "packages" / "pkg-a").mkdir(parents=True)
    (repo / "packages" / "pkg-a" / "pyproject.toml").write_text('[project]\nname="a"\n')
    (repo / ".git").mkdir()

    # In v1, workspace_path IS the repo root — exclusion must be guarded off
    records = detect(repo, workspace_path=repo)
    sources = {r["source"] for r in records}
    assert "packages" in sources  # still classified normally
```

**Mocking note:** No boto3 / external API in these tests — pure path manipulation. `monkeypatch.setenv` for `GRAPH_WIKI_WORKSPACE`. No need to mock `resolve_wiki_and_repo` because the tests call `detect()` directly with synthetic paths.

---

## Shared Patterns

### Frontmatter parsing (read-only)
**Source:** `packages/vault-io/src/vault_io/scan_monorepo.py:590-599` (`_parse_frontmatter`) and `packages/vault-io/src/vault_io/lint/workflow_hints.py:13-43` (`_parse_workflow_hints`).
**Apply to:** SCAN-01 edit in `scan_monorepo._collect`.
**Reuse rule:** Import `_parse_workflow_hints` from `vault_io.lint.workflow_hints`. Both modules live in the same package — a private-prefix import is acceptable (RESEARCH.md A6). Do NOT add a new YAML parser.

### `unittest.mock.patch` + `assert_called_once_with`
**Source:** `packages/vault-io/tests/test_ingest_work_item.py:166-201`.
**Apply to:** `tests/test_update_tokens.py`.
**Pattern:** Patch `vault_io.<module>.<symbol>` (e.g. `vault_io.update_tokens.boto3.client`), return a `MagicMock`, then `mock.assert_called_once_with(...)` with the exact expected payload. No `botocore.stub.Stubber`.

### tmp_path fixture extension
**Source:** `packages/vault-io/tests/conftest.py:11-29` (`tmp_repo`, `vault_path`).
**Apply to:** `tests/test_detect_containers.py` (v2_workspace fixture), `tests/test_scan_companion_fold.py` (apps-not-filtered guard).
**Pattern:** Use `tmp_path` builtin + manual `mkdir(parents=True)` + `write_text` for fixture construction. `monkeypatch.setenv("GRAPH_WIKI_WORKSPACE", ...)` for env-honoring paths. Either extend `conftest.py` (if the fixture is reused across files) or inline (if scoped to one file).

### `GRAPH_WIKI_RUN_INTEGRATION` gate
**Source:** `agents/graph-wiki-agent/tests/integration/test_bedrock_iam.py:30-46` + `agents/graph-wiki-agent/tests/conftest.py:17-22` + `docs/testing.md:53-56`.
**Apply to:** `tests/integration/test_count_tokens_live.py`.
**Pattern:** Define `INTEGRATION_GATE` locally (verbatim shape — reason string must match `docs/testing.md`). Apply `@pytest.mark.integration` AND `@INTEGRATION_GATE` at function level.

### Workspace-aware repo resolution
**Source:** `packages/vault-io/src/vault_io/_workspace.py:23-38` (`resolve_wiki_and_repo`).
**Apply to:** `init_vault.py:305`, `detect_containers.py:174`.
**Pattern:** Always use the second return value (`repo`) as the repo root. Never compute `wiki.parent`. This works for both v1 and v2 layouts because `workspace_io.config.resolve()` handles layout detection inside the resolver.

### Boto3 CountTokens converse shape
**Source:** AWS Bedrock User Guide + `docs.aws.amazon.com/bedrock/latest/APIReference/API_runtime_CountTokens.html` (verified 2026-05-19).
**Apply to:** `update_tokens.count_tokens()` and its unit test.
**Pattern:**
```python
input={"converse": {"messages": [{"role": "user", "content": [{"text": text}]}]}}
# Response field is "inputTokens" (NOT "inputTokenCount")
```

## No Analog Found

None — every file in this phase has either an in-place analog (source edits) or a close-shape analog in `packages/vault-io/tests/` or `agents/graph-wiki-agent/tests/integration/`.

## Metadata

**Analog search scope:**
- `packages/vault-io/src/vault_io/` (sources)
- `packages/vault-io/tests/` (existing tests + fixtures)
- `agents/graph-wiki-agent/tests/integration/` (integration gate reference)
- `agents/graph-wiki-agent/tests/conftest.py` (gate decorator canonical definition)
- `docs/testing.md` (canonical gate rule)

**Files scanned:** ~22 (vault-io sources + tests + 2 cross-package gate references + 3 fixture overview pages).

**Pattern extraction date:** 2026-05-19
