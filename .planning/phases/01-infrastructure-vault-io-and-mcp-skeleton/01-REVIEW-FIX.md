---
phase: 01-infrastructure-vault-io-and-mcp-skeleton
fixed_at: 2026-05-13T19:10:00Z
review_path: .planning/phases/01-infrastructure-vault-io-and-mcp-skeleton/01-REVIEW.md
iteration: 1
findings_in_scope: 9
fixed: 9
skipped: 0
status: all_fixed
---

# Phase 01: Code Review Fix Report

**Fixed at:** 2026-05-13T19:10:00Z
**Source review:** .planning/phases/01-infrastructure-vault-io-and-mcp-skeleton/01-REVIEW.md
**Iteration:** 1

**Summary:**
- Findings in scope: 9
- Fixed: 9
- Skipped: 0

## Fixed Issues

### CR-01: tiktoken replaced with Bedrock CountTokens API

**Files modified:** `cores/vault-io/src/vault_io/update_tokens.py`, `cores/vault-io/pyproject.toml`, `cores/vault-io/tests/test_truncated_frontmatter.py`
**Commits:** `7972ecb`, `5b08646`
**Applied fix:** Removed `tiktoken` import and `get_encoding()`/`count_tokens(encoding)` functions. Replaced with `boto3.client("bedrock-runtime").count_tokens(modelId=..., content=[{"text": text}])`. The `update_page()` and `update_vault()` signatures now accept `model_id` and `region` kwargs instead of an encoding object. API errors are caught and result in a "skipped" status. Removed `tiktoken>=0.7` from `pyproject.toml`, added `boto3>=1.38`. Updated `test_truncated_frontmatter.py` to remove the now-unused `_enc()` helper and use the new signature — the truncated-frontmatter path short-circuits before the token API is called so no mock is needed.

---

### CR-02: CLI main() functions fixed to derive repo from wiki.parent

**Files modified:** `cores/vault-io/src/vault_io/detect_containers.py`, `cores/vault-io/src/vault_io/scan_monorepo.py`, `cores/vault-io/src/vault_io/init_vault.py`
**Commit:** `43dac3a`
**Applied fix:** In all three `main()` functions, replaced the pattern `wiki, repo = resolve_wiki_and_repo(); if repo is None: sys.exit(1)` with `wiki, _ = resolve_wiki_and_repo(); repo = wiki.parent` (with a comment noting this is the v1 convention). The `if not repo.exists()` guard is retained to catch genuine filesystem issues. All three CLIs now work as standalone commands.

---

### CR-03: Phantom nodes filtered in graph_analyzer.connected_components()

**Files modified:** `cores/vault-io/src/vault_io/graph_analyzer.py`
**Commit:** `04047b7`
**Applied fix:** Changed the adjacency construction from `adj[n] |= out.get(n, set())` to `adj[n] |= out.get(n, set()) & nodes` (and same for `inb`). This intersects each edge set with the `nodes` set before adding to the adjacency dict, so keys like `"log"` and `"index"` that exist in `inb` but not in `nodes` are excluded from BFS traversal. Component `size` and `sample` values now only contain real page nodes.

---

### CR-04: ValueError on non-integer version field in layout_io

**Files modified:** `cores/vault-io/src/vault_io/layout_io.py`
**Commit:** `a1d6a76`
**Applied fix:** Wrapped `out["version"] = int(out["version"])` in a `try/except (ValueError, TypeError)` block that falls back to `out["version"] = 1` on conversion failure. This prevents a single malformed `version: 2.0` or `version: draft` field from crashing the entire scan.

---

### WR-01: models.toml path fixed to use importlib.resources

**Files modified:** `cores/model-adapter/src/model_adapter/loader.py`, `cores/model-adapter/pyproject.toml`, `cores/model-adapter/src/model_adapter/models.toml` (new)
**Commit:** `2b94fd3`
**Applied fix:** Copied `models.toml` from `cores/model-adapter/models.toml` to `cores/model-adapter/src/model_adapter/models.toml` so it is co-located with the package. Replaced the fragile `Path(__file__).parent.parent.parent / "models.toml"` path with a `_load_models_config()` helper that uses `importlib.resources.files("model_adapter").joinpath("models.toml").open("rb")`. Added `[tool.uv.build.include]` entry to `pyproject.toml` to declare the data file for wheel packaging. `make_llm()` now calls `_load_models_config()` instead of `open(_MODELS_TOML, "rb")`.

---

### WR-02: False Go discovery claim removed from scan_monorepo docstring

**Files modified:** `cores/vault-io/src/vault_io/scan_monorepo.py`
**Commit:** `e19444f`
**Applied fix:** Replaced `- go.mod + go.work                                       (Go)` in the module docstring with `# TODO: go.mod + go.work (Go) — not yet implemented`. This accurately reflects that `_infer_language()` can detect Go in already-found packages, but `_discover_heuristic()` does not walk `go.work` files.

---

### WR-03: Zombie process fixed in test_mcp_stdio.py

**Files modified:** `agents/code-wiki-agent/tests/integration/test_mcp_stdio.py`
**Commits:** `66abceb`, `1984841` (ruff format)
**Applied fix:** Replaced the bare `finally: proc.kill()` pattern with an explicit `except subprocess.TimeoutExpired:` block that calls `proc.kill()` followed by `proc.communicate()` to reap the zombie and collect output, then calls `pytest.fail()` with the stderr diagnostic. The normal path (no timeout) is unchanged. ruff reformatted the long `pytest.fail()` call to a single line.

---

### WR-04: Hardcoded version string replaced with importlib.metadata

**Files modified:** `agents/code-wiki-agent/src/code_wiki_agent/cli.py`
**Commit:** `b0555cc`
**Applied fix:** Added `import importlib.metadata` at the top of `cli.py`. Changed `typer.echo("code-wiki-agent 0.1.0")` to `v = importlib.metadata.version("code-wiki-agent"); typer.echo(f"code-wiki-agent {v}")`. The version now reads from the installed package metadata and will stay in sync with `pyproject.toml` automatically.

---

### WR-05: Rule 1 docs classification uses recursive markdown ratio

**Files modified:** `cores/vault-io/src/vault_io/detect_containers.py`
**Commit:** `254c5a9`
**Applied fix:** Removed the `not children` guard from Rule 1. The new implementation uses `d.rglob("*")` and `d.rglob("*.md")` to count total files and markdown files recursively across the entire directory tree, then applies `md_count / total_files >= DOC_THRESHOLD`. The `not has_manifest_in_root` and `not any(_has_manifest(c) for c in children)` guards are retained to prevent misclassifying package containers. Directories like `docs/api/` and `docs/guides/` that previously fell through to "ambiguous" are now correctly classified as "docs".

---

_Fixed: 2026-05-13T19:10:00Z_
_Fixer: Claude (gsd-code-fixer)_
_Iteration: 1_
