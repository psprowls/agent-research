# vault-io ⟷ lattice-wiki-core Raw Drift Dump

**Upstream:** lattice-wiki-core @ `1b45172a9900842b0f8eea525c8270e7fff50605`
**Generated:** 2026-05-18T17:52:57Z
**Command:** `bash scripts/drift-diff.sh > packages/vault-io/DRIFT-DECISIONS-RAW.md`

This file is the **raw-diff source of truth** (per 12-CONTEXT.md §DD-03). Every
overlapping module row from spike 002 §Investigation A is dumped here as a
`diff -u` between vault-io and the pinned upstream commit. No verdicts, no
judgment — just the diffs. The companion file
`packages/vault-io/DRIFT-DECISIONS.md` (forthcoming in plan 12-02) reads this
dump and assigns per-row verdicts (`PORT` / `LEAVE-AHEAD` / `LEAVE-ARCH` /
`LEAVE-COSMETIC` / `IDENTICAL`).

**Structure:** exactly 11 top-level `### ` sections — one per overlapping
module row from spike 002 §A. The `### lint/*` row collapses 8 lint sub-files
into inline `#### lint/<file>` sub-sections beneath it (operator decision on
Blocker B1).

**Regeneration:** bump `UPSTREAM_SHA` in `scripts/drift-diff.sh`, checkout
that SHA in `/Users/pat/Personal/lattice`, then re-run `bash scripts/drift-diff.sh > packages/vault-io/DRIFT-DECISIONS-RAW.md`.

### git_state.py

IDENTICAL

### append_log.py

```diff
--- /Users/pat/Personal/lattice/packages/lattice-wiki-core/src/lattice_wiki_core/append_log.py	2026-05-16 20:55:44
+++ packages/vault-io/src/vault_io/append_log.py	2026-05-18 11:51:36
@@ -5,8 +5,8 @@
 The log is append-only and uses a consistent header so unix tools can parse it:
     ## [YYYY-MM-DD] <op> | <title>
 
-Discovers wiki location from the resolved lattice workspace. Requires LATTICE_WORKSPACE
-env var or git repo with lattice/ workspace directory.
+Discovers wiki location via vault_io._workspace.resolve_wiki_and_repo.
+Requires GRAPH_WIKI_WORKSPACE env var (or a git repo containing a wiki/ directory).
 
 Usage:
     python append_log.py --op ingest --title "Auth Migration Spec"
@@ -31,15 +31,27 @@
 import json
 import sys
 
-from lattice_wiki_core._version_check import check_for_updates
-from lattice_wiki_core._workspace import resolve_wiki_and_repo
+from vault_io._workspace import resolve_wiki_and_repo
 
 VALID_OPS = {"scan", "ingest", "query", "lint", "create", "update", "delete", "note"}
 
 
-def _error(message, as_json=False):
+def _error(message, as_json=False, raise_exception=False):
+    """Report an error.
+
+    When called from a library context (e.g. an MCP tool handler) pass
+    ``raise_exception=True`` so the failure surfaces as a normal
+    ``ValueError`` that the MCP boundary can catch — never ``sys.exit``,
+    which would kill the stdio server process (WR-01).
+
+    JSON-formatted error output is written to stderr, not stdout, so that
+    a future caller accidentally enabling ``as_json=True`` from inside the
+    MCP server cannot trip ``_StdoutGuard`` (WR-02).
+    """
+    if raise_exception:
+        raise ValueError(message)
     if as_json:
-        print(json.dumps({"status": "error", "message": message}))
+        print(json.dumps({"status": "error", "message": message}), file=sys.stderr)
     else:
         print(f"[error] {message}", file=sys.stderr)
     sys.exit(1)
@@ -61,14 +73,28 @@
     return today, header, f"\n{header}\n{body}"
 
 
-def append_log(wiki, op, title, detail, as_json=False):
+def append_log(wiki, op, title, detail, as_json=False, silent=False, raise_exception=False):
+    """Append a log entry to wiki/log.md.
+
+    Args:
+        silent: When True, suppress all stdout output. Use from MCP tool handlers
+                to avoid tripping _StdoutGuard. Overrides as_json for output only.
+        raise_exception: When True, error paths raise ``ValueError`` instead of
+                calling ``sys.exit(1)``. Library callers (MCP tool handlers,
+                file_work_item) MUST set this — a ``SystemExit`` from inside the
+                MCP server's tool boundary would terminate the stdio server.
+    """
     if op not in VALID_OPS:
-        _error(f"unknown op '{op}'. Valid: {sorted(VALID_OPS)}", as_json)
+        _error(
+            f"unknown op '{op}'. Valid: {sorted(VALID_OPS)}",
+            as_json,
+            raise_exception=raise_exception,
+        )
 
     try:
         log_path = validate_wiki(wiki)
     except FileNotFoundError as e:
-        _error(str(e), as_json)
+        _error(str(e), as_json, raise_exception=raise_exception)
 
     today, header, entry_text = format_entry(op, title, detail)
 
@@ -76,7 +102,11 @@
         with log_path.open("a", encoding="utf-8") as f:
             f.write(entry_text)
     except OSError as e:
-        _error(f"failed to write {log_path}: {e}", as_json)
+        _error(
+            f"failed to write {log_path}: {e}",
+            as_json,
+            raise_exception=raise_exception,
+        )
 
     result = {
         "status": "ok",
@@ -88,13 +118,14 @@
         "detail": detail,
     }
 
-    if as_json:
-        print(json.dumps(result, indent=2))
-    else:
-        print(f"[ok] appended to {log_path}")
-        print(f"     {header}")
-        if detail:
-            print(f"     detail: {detail}")
+    if not silent:
+        if as_json:
+            print(json.dumps(result, indent=2))
+        else:
+            print(f"[ok] appended to {log_path}")
+            print(f"     {header}")
+            if detail:
+                print(f"     detail: {detail}")
     return result
 
 
@@ -106,7 +137,6 @@
     p.add_argument("--json", action="store_true")
     args = p.parse_args()
     wiki, _ = resolve_wiki_and_repo()
-    check_for_updates(wiki.parent)
     append_log(
         wiki,
         args.op,
```

### update_index.py

```diff
--- /Users/pat/Personal/lattice/packages/lattice-wiki-core/src/lattice_wiki_core/update_index.py	2026-05-16 20:58:08
+++ packages/vault-io/src/vault_io/update_index.py	2026-05-18 11:51:36
@@ -22,7 +22,7 @@
 from collections import defaultdict
 from pathlib import Path
 
-from lattice_wiki_core._workspace import resolve_wiki_and_repo
+from vault_io._workspace import resolve_wiki_and_repo
 
 FRONTMATTER_RE = re.compile(r"^---\s*\n(.*?)\n---\s*\n", re.DOTALL)
 # Categories rendered in the main index (navigation backbone only)
@@ -46,11 +46,11 @@
 # `work` is intentionally absent — work items live at <workspace>/work/ (sibling of the wiki),
 # so its index is written outside the vault. See scan_work() / main().
 CATEGORY_INDEX_FILES = {
-    "concept":      "concepts/index.md",
-    "source":       "sources/index.md",
-    "adr":          "adrs/index.md",
+    "concept": "concepts/index.md",
+    "source": "sources/index.md",
+    "adr": "adrs/index.md",
     "architecture": "architecture/index.md",
-    "dependency":   "dependencies/index.md",
+    "dependency": "dependencies/index.md",
 }
 GENERATED_FILES = {"index.md", "log.md"} | set(CATEGORY_INDEX_FILES.values())
 
@@ -141,7 +141,7 @@
     Returns a list of entries shaped like scan_vault() values. Paths are
     workspace-relative (e.g. "work/2026-05-03-foo.md") so they render as
     workspace-rooted wikilinks. Skips the generated work index, dotfiles,
-    and the archived/ sub-namespace (owned by lattice-wiki lifecycle).
+    and the archived/ sub-namespace (owned by lattice-work lifecycle).
     """
     work_dir = workspace / "work"
     if not work_dir.exists():
@@ -188,8 +188,7 @@
 def render_index(pages, wiki_name, vault_name):
     today = dt.date.today().isoformat()
     nav_total = sum(
-        sum(1 for e in pages.get(c, []) if Path(e["path"]).stem not in SUBPAGE_STEMS)
-        for c in MAIN_INDEX_CATEGORIES
+        sum(1 for e in pages.get(c, []) if Path(e["path"]).stem not in SUBPAGE_STEMS) for c in MAIN_INDEX_CATEGORIES
     )
 
     lines = [
@@ -234,9 +233,7 @@
     # so its wikilink is workspace-rooted, not wiki-rooted.
     work_entries = pages.get("work", [])
     if work_entries:
-        more_links.append(
-            f"- [[work/index]] — {CATEGORY_LABELS['work']} ({len(work_entries)} pages)"
-        )
+        more_links.append(f"- [[work/index]] — {CATEGORY_LABELS['work']} ({len(work_entries)} pages)")
     if more_links:
         lines.append("## More")
         lines.append("")
@@ -289,6 +286,38 @@
     return "\n".join(lines)
 
 
+def update_index(wiki: Path) -> None:
+    """Regenerate wiki/index.md and category sub-indexes from vault frontmatter.
+
+    Library entry point for use by ingest_work_item and other callers.
+    Equivalent to running main() without --dry-run or --json.
+    """
+    pages = scan_vault(wiki)
+    work_entries = scan_work(wiki.parent)
+    if work_entries:
+        pages["work"] = work_entries
+    vault = wiki
+    content = render_index(pages, wiki.name, vault.name)
+    index_path = wiki / "index.md"
+    index_path.write_text(content, encoding="utf-8")
+    for cat, fname in CATEGORY_INDEX_FILES.items():
+        entries = pages.get(cat, [])
+        if not entries:
+            continue
+        label = CATEGORY_LABELS.get(cat, cat.capitalize())
+        cat_content = render_category_index(entries, cat, label, vault.name)
+        cat_path = vault / fname
+        cat_path.parent.mkdir(parents=True, exist_ok=True)
+        cat_path.write_text(cat_content, encoding="utf-8")
+    if work_entries:
+        work_index_path = wiki.parent / "work" / "index.md"
+        work_index_content = render_category_index(
+            work_entries, "work", CATEGORY_LABELS["work"], vault.name, location="work"
+        )
+        work_index_path.parent.mkdir(parents=True, exist_ok=True)
+        work_index_path.write_text(work_index_content, encoding="utf-8")
+
+
 def main():
     p = argparse.ArgumentParser(description="Regenerate wiki/index.md")
     p.add_argument("--dry-run", action="store_true")
```

### update_tokens.py

```diff
--- /Users/pat/Personal/lattice/packages/lattice-wiki-core/src/lattice_wiki_core/update_tokens.py	2026-05-11 17:19:09
+++ packages/vault-io/src/vault_io/update_tokens.py	2026-05-18 11:51:36
@@ -2,19 +2,18 @@
 """
 update_tokens.py — Stamp `tokens: <count>` frontmatter on every wiki page.
 
-Counts `cl100k_base` BPE tokens against a stable baseline — the file
-content with any existing `tokens` field stripped — then idempotently
-rewrites the `tokens` field via `python-frontmatter`. Stripping the
-field before counting avoids a circular dependency: a file that already
-contains `tokens: N` would produce a different count than the same file
-before the field was added, breaking idempotency. Re-running on an
-unchanged vault is a no-op.
+Counts tokens against a stable baseline — the file content with any existing
+`tokens` field stripped — using the Bedrock CountTokens API, then idempotently
+rewrites the `tokens` field via `python-frontmatter`. Stripping the field before
+counting avoids a circular dependency: a file that already contains `tokens: N`
+would produce a different count than the same file before the field was added,
+breaking idempotency. Re-running on an unchanged vault is a no-op.
 
 Discovers wiki location from the resolved lattice workspace.
 
 Usage:
-    python -m lattice_wiki_core.update_tokens
-    python -m lattice_wiki_core.update_tokens --dry-run --json
+    python -m vault_io.update_tokens
+    python -m vault_io.update_tokens --dry-run --json
 """
 
 from __future__ import annotations
@@ -25,23 +24,26 @@
 from pathlib import Path
 from typing import Iterator
 
+import boto3
 import frontmatter
-import tiktoken
 
-from lattice_wiki_core._version_check import check_for_updates
-from lattice_wiki_core._workspace import resolve_wiki_and_repo
+from vault_io._workspace import resolve_wiki_and_repo
 
 SKIP_FILENAMES = {"index.md", "log.md"}
 
+DEFAULT_MODEL_ID = "us.anthropic.claude-haiku-4-5-20251001-v1:0"
+DEFAULT_REGION = "us-east-1"
 
-def get_encoding() -> "tiktoken.Encoding":
-    return tiktoken.get_encoding("cl100k_base")
 
+def count_tokens(text: str, model_id: str = DEFAULT_MODEL_ID, region: str = DEFAULT_REGION) -> int:
+    client = boto3.client("bedrock-runtime", region_name=region)
+    response = client.count_tokens(
+        modelId=model_id,
+        content=[{"text": text}],
+    )
+    return response["inputTokenCount"]
 
-def count_tokens(text: str, encoding: "tiktoken.Encoding") -> int:
-    return len(encoding.encode(text))
 
-
 def iter_pages(wiki: Path) -> Iterator[Path]:
     """Yield every .md under `wiki`, skipping log/index and dotdir paths."""
     for path in wiki.rglob("*.md"):
@@ -55,8 +57,9 @@
 
 def update_page(
     path: Path,
-    encoding: "tiktoken.Encoding",
     dry_run: bool = False,
+    model_id: str = DEFAULT_MODEL_ID,
+    region: str = DEFAULT_REGION,
 ) -> tuple[str, int]:
     """Stamp the `tokens` field on a single page.
 
@@ -84,7 +87,7 @@
     # Strip the existing tokens field from the raw YAML to create a stable baseline.
     # This preserves the original YAML formatting while removing the field that would
     # create a circular dependency (the token count would differ after adding the field).
-    # We do this line-by-line to avoid reformatting via frontmatter.dumps().
+    # We do this line-by-line to avoid reformatting via the YAML serializer.
     parts = raw.split("---", 2)
     # Guard against truncated frontmatter (missing closing ---).
     if len(parts) < 3:
@@ -97,7 +100,11 @@
     # Reconstruct: --- + filtered_fm + --- + content + \n
     baseline = f"---\n{filtered_fm}\n---\n{parts[2]}\n"
 
-    count = count_tokens(baseline, encoding)
+    try:
+        count = count_tokens(baseline, model_id=model_id, region=region)
+    except Exception as exc:  # noqa: BLE001 — keep run going on API errors
+        print(f"[warn] skipping {path}: token count failed: {exc}", file=sys.stderr)
+        return ("skipped", 0)
 
     if post.metadata.get("tokens") == count:
         return ("unchanged", count)
@@ -105,8 +112,6 @@
     if not dry_run:
         # Update the tokens field while preserving original YAML formatting.
         # At this point, we know has_frontmatter is True (checked earlier)
-        parts = raw.split("---", 2)
-        # Update existing frontmatter
         fm_lines = parts[1].strip().split("\n")
         updated_lines = []
         tokens_found = False
@@ -132,22 +137,26 @@
     return ("updated", count)
 
 
-def update_vault(wiki: Path, dry_run: bool = False) -> dict[str, list[str]]:
+def update_vault(
+    wiki: Path,
+    dry_run: bool = False,
+    model_id: str = DEFAULT_MODEL_ID,
+    region: str = DEFAULT_REGION,
+) -> dict[str, list[str]]:
     """Walk `wiki` and `work/`, stamp `tokens` on every page, return {updated, unchanged, skipped} lists."""
-    encoding = get_encoding()
     result: dict[str, list[str]] = {"updated": [], "unchanged": [], "skipped": []}
     workspace = wiki.parent
 
     # Process wiki pages
     for page in iter_pages(wiki):
-        status, _ = update_page(page, encoding, dry_run=dry_run)
+        status, _ = update_page(page, dry_run=dry_run, model_id=model_id, region=region)
         result[status].append(str(page.relative_to(workspace)))
 
     # Process work items (sibling of wiki)
     work_dir = workspace / "work"
     if work_dir.exists():
         for page in iter_pages(work_dir):
-            status, _ = update_page(page, encoding, dry_run=dry_run)
+            status, _ = update_page(page, dry_run=dry_run, model_id=model_id, region=region)
             result[status].append(str(page.relative_to(workspace)))
 
     for bucket in result.values():
@@ -159,22 +168,19 @@
     p = argparse.ArgumentParser(description="Stamp `tokens` frontmatter across the wiki")
     p.add_argument("--dry-run", action="store_true", help="Print changes without writing")
     p.add_argument("--json", action="store_true", help="Machine-readable output")
+    p.add_argument("--model-id", default=DEFAULT_MODEL_ID, help="Bedrock model ID for token counting")
+    p.add_argument("--region", default=DEFAULT_REGION, help="AWS region for Bedrock")
     args = p.parse_args()
 
     wiki, _ = resolve_wiki_and_repo()
-    check_for_updates(wiki.parent)
-    result = update_vault(wiki, dry_run=args.dry_run)
+    result = update_vault(wiki, dry_run=args.dry_run, model_id=args.model_id, region=args.region)
 
     if args.json:
         print(json.dumps(result, indent=2))
         return
 
     label = "Would update" if args.dry_run else "Updated"
-    print(
-        f"{label} {len(result['updated'])} • "
-        f"Unchanged {len(result['unchanged'])} • "
-        f"Skipped {len(result['skipped'])}"
-    )
+    print(f"{label} {len(result['updated'])} • Unchanged {len(result['unchanged'])} • Skipped {len(result['skipped'])}")
     for kind in ("updated", "skipped"):
         for rel in result[kind][:20]:
             print(f"  [{kind}] {rel}")
```

### ingest_work_item.py

```diff
--- /Users/pat/Personal/lattice/packages/lattice-wiki-core/src/lattice_wiki_core/ingest_work_item.py	2026-05-16 20:58:08
+++ packages/vault-io/src/vault_io/ingest_work_item.py	2026-05-18 11:51:36
@@ -1,40 +1,34 @@
-#!/usr/bin/env python3
 """
-ingest_work_item.py — File a structured work item (category: work) into <workspace>/work/.
+ingest_work_item.py — Library functions for filing a structured work item.
 
-One-shot, non-interactive, strict schema validation. Designed as the cross-plugin
-entry point invoked by lattice-workflows' file-work-item skill (§3.9 Pattern 3).
+Extracted from lattice-wiki-core's ingest_work_item.py.
+Library functions only — no argparse main(), no subprocess calls.
 
-Discovers wiki location from the resolved lattice workspace.
+The critical change from the lattice-wiki-core version: subprocess helper calls
+are replaced with direct imports of update_index() and append_log().
 
-Usage:
-    python ingest_work_item.py \\
-        --frontmatter "$(cat fm.yaml)" \\
-        --body "$(cat body.md)" \\
-        --slug optional-slug \\
-        --json
-
-Exit codes (per §3.8):
-    0  success
-    2  invalid args / schema rejection
-    3  runtime error (write conflict, IO failure)
+Exports:
+    _err(msg, code, as_json) -> NoReturn
+    _slugify(title) -> str
+    _parse_frontmatter(yaml_text) -> dict
+    _validate(fm) -> list[str]
+    _emit_yaml(fm) -> str
+    file_work_item(wiki, fm, body, slug, force, pkg_dir, pkg_title) -> dict
 """
 
 from __future__ import annotations
 
-import argparse
 import json
 import re
-import subprocess
 import sys
 from pathlib import Path
 from typing import NoReturn
 
-from lattice_wiki_core._workspace import resolve_wiki_and_repo
-from lattice_wiki_core.layout_io import ensure_subpage
-from lattice_wiki_core.work.frontmatter import parse_frontmatter as _parse_full_frontmatter
+from vault_io._workspace import resolve_wiki_and_repo
+from vault_io.append_log import append_log
+from vault_io.layout_io import ensure_subpage
+from vault_io.update_index import update_index
 
-SCRIPTS_DIR = Path(__file__).resolve().parent
 REQUIRED_FIELDS = (
     "title",
     "category",
@@ -61,6 +55,42 @@
     return s or "untitled"
 
 
+def _parse_frontmatter(yaml_text: str) -> dict:
+    """Minimal YAML frontmatter parser tailored to work-page schema.
+
+    Supports scalar `key: value` lines and `key:` followed by `  - item` lists.
+    Doesn't handle nested mappings — work-page schema doesn't need them.
+    """
+    out: dict = {}
+    cur_key: str | None = None
+    cur_list: list | None = None
+    for raw in yaml_text.splitlines():
+        line = raw.rstrip()
+        if not line or line.startswith("#"):
+            continue
+        if line.startswith("  - ") and cur_list is not None:
+            cur_list.append(line[4:].strip())
+            continue
+        # End any open list
+        if cur_list is not None:
+            out[cur_key] = cur_list
+            cur_key, cur_list = None, None
+        if ":" not in line:
+            raise ValueError(f"unparseable line: {line!r}")
+        key, _, val = line.partition(":")
+        key = key.strip()
+        val = val.strip()
+        if val == "":
+            cur_key, cur_list = key, []
+        elif val == "[]":
+            out[key] = []
+        else:
+            out[key] = val
+    if cur_list is not None:
+        out[cur_key] = cur_list
+    return out
+
+
 def _validate(fm: dict) -> list[str]:
     issues: list[str] = []
     for field in REQUIRED_FIELDS:
@@ -85,92 +115,70 @@
     return "\n".join(lines)
 
 
-def _run_helper(name: str, *args: str) -> None:
-    """Invoke a sibling script (update_index.py / append_log.py)."""
-    subprocess.run(
-        [sys.executable, str(SCRIPTS_DIR / name), *args],
-        check=True,
-        capture_output=True,
-    )
+def file_work_item(
+    wiki: Path,
+    fm: dict,
+    body: str,
+    slug: str | None = None,
+    force: bool = False,
+    pkg_dir: Path | None = None,
+    pkg_title: str | None = None,
+) -> dict:
+    """Write a work-item page and update index + log.
 
+    Extracted from lattice-wiki-core's ingest_work_item.main() body.
+    Calls update_index(wiki) and append_log(wiki, ...) directly (no subprocess).
 
-def main() -> int:
-    p = argparse.ArgumentParser(description="Ingest a work-page into <workspace>/work/.")
-    p.add_argument("--frontmatter", required=True, help="YAML frontmatter (string).")
-    p.add_argument("--body", required=True, help="Markdown body (string).")
-    p.add_argument("--slug", default=None, help="Page slug (derived from title if omitted).")
-    p.add_argument("--force", action="store_true", help="Overwrite if page exists.")
-    p.add_argument("--json", action="store_true", help="Emit JSON result on stdout.")
-    p.add_argument("--pkg-dir", default=None,
-                   help="Absolute path to the vault package directory. "
-                        "When given, ensures work.md sub-page exists and appends a backlink.")
-    p.add_argument("--pkg-title", default=None,
-                   help="Display title for the package (used when creating work.md from template).")
-    args = p.parse_args()
+    Args:
+        wiki: Path to the wiki directory (e.g. <workspace>/wiki/).
+        fm: Parsed frontmatter dict (must pass _validate()).
+        body: Markdown body text.
+        slug: Page slug; derived from fm['title'] via _slugify() if omitted.
+        force: Overwrite existing page if True; raise FileExistsError if False.
+        pkg_dir: Optional vault package directory Path for work sub-page linking.
+        pkg_title: Display title for the package sub-page template.
 
-    wiki, _ = resolve_wiki_and_repo()
-    if not wiki.exists():
-        _err(f"wiki does not exist: {wiki}", code=2, as_json=args.json)
+    Returns:
+        dict with keys: status, page_path (str), slug, title.
 
-    vault = wiki
-
-    try:
-        framed = args.frontmatter
-        if not framed.lstrip().startswith("---"):
-            framed = "---\n" + framed.rstrip() + "\n---\n"
-        fm, _ = _parse_full_frontmatter(framed)
-    except ValueError as e:
-        _err(f"frontmatter parse error: {e}", code=2, as_json=args.json)
-
-    issues = _validate(fm)
-    if issues:
-        _err("schema validation failed: " + "; ".join(issues), code=2, as_json=args.json)
-
+    Raises:
+        FileExistsError: If the page already exists and force=False.
+        OSError: If writing the page fails.
+    """
     title = str(fm["title"])
     opened = str(fm["opened"])
-    slug = args.slug or _slugify(title)
+    slug = slug or _slugify(title)
+
     work_root = wiki.parent / "work"
     work_root.mkdir(parents=True, exist_ok=True)
     page_path = work_root / f"{opened}-{slug}.md"
 
-    if page_path.exists() and not args.force:
-        _err(f"page already exists: {page_path}", code=3, as_json=args.json)
+    if page_path.exists() and not force:
+        raise FileExistsError(f"page already exists: {page_path}")
 
-    body = args.body if args.body.endswith("\n") else args.body + "\n"
+    body = body if body.endswith("\n") else body + "\n"
     content = _emit_yaml(fm) + "\n\n" + body
-    try:
-        page_path.write_text(content, encoding="utf-8")
-    except OSError as e:
-        _err(f"write failed: {e}", code=3, as_json=args.json)
+    page_path.write_text(content, encoding="utf-8")
 
-    # Side-effect: refresh index, append log. Failures here are runtime errors
-    # but the page is already written — surface and exit 3.
-    try:
-        _run_helper("update_index.py")
-        _run_helper(
-            "append_log.py",
-            "--op",
-            "create",
-            "--title",
-            title,
-            "--detail",
-            f"work/{page_path.name}",
-        )
-    except subprocess.CalledProcessError as e:
-        _err(
-            f"side-effect script failed: {e.stderr.decode(errors='replace')}",
-            code=3,
-            as_json=args.json,
-        )
+    # Side-effects: refresh index and append log (direct calls, no subprocess).
+    update_index(wiki)
+    append_log(
+        wiki,
+        "create",
+        title,
+        detail=f"work/{page_path.name}",
+        silent=True,
+        raise_exception=True,
+    )
 
-    if args.pkg_dir:
-        pkg_dir = Path(args.pkg_dir).expanduser().resolve()
-        pkg_title = args.pkg_title or pkg_dir.name
+    if pkg_dir is not None:
+        vault = wiki
+        pkg_title_str = pkg_title or pkg_dir.name
         templates_dir = vault / ".templates"
         try:
-            ensure_subpage(pkg_dir, "work", pkg_title, templates_dir)
+            ensure_subpage(pkg_dir, "work", pkg_title_str, templates_dir)
         except FileNotFoundError:
-            pass  # templates not installed — skip silently
+            pass  # templates not installed -- skip silently
         work_sub = pkg_dir / "work.md"
         if work_sub.exists():
             bullet = f"- [[work/{opened}-{slug}]] — {fm.get('summary', '')}\n"
@@ -179,13 +187,4 @@
                 existing += "\n"
             work_sub.write_text(existing + bullet, encoding="utf-8")
 
-    result = {"status": "ok", "path": str(page_path), "slug": slug, "title": title}
-    if args.json:
-        print(json.dumps(result))
-    else:
-        print(f"Created {page_path}")
-    return 0
-
-
-if __name__ == "__main__":
-    sys.exit(main())
+    return {"status": "ok", "page_path": str(page_path), "slug": slug, "title": title}
```

### init_vault.py

```diff
--- /Users/pat/Personal/lattice/packages/lattice-wiki-core/src/lattice_wiki_core/init_vault.py	2026-05-16 20:55:44
+++ packages/vault-io/src/vault_io/init_vault.py	2026-05-18 11:51:36
@@ -3,9 +3,10 @@
 init_vault.py — Bootstrap a Code Wiki alongside a source code repo.
 
 Creates the wiki structure under `<workspace>/wiki/` and seeds it with
-starter templates. The workspace is discovered (or created) via
-`lattice-workspace`; `<workspace>/raw/` and `<workspace>/work/` are
-lattice-workspace's responsibility, not this script's.
+starter templates. Adapted from the upstream source with the workspace.init
+integration stubbed out (Phase 5 will reintroduce an equivalent workspace
+bootstrap step). All file paths and template copying remain byte-identical
+to the source.
 
 Usage:
     python init_vault.py --topic "my-repo"
@@ -25,19 +26,17 @@
 import argparse
 import datetime as dt
 import json
+import logging
 import sys
 from pathlib import Path
 
-from lattice_workspace.init import init as workspace_init
+logger = logging.getLogger(__name__)
 
-from lattice_wiki_core import __version__
-from lattice_wiki_core._workspace import resolve_wiki_and_repo
-from lattice_wiki_core.detect_containers import detect as _detect_containers
-from lattice_wiki_core.layout_io import write_layout as _write_layout
+from vault_io._workspace import resolve_wiki_and_repo
+from vault_io.detect_containers import detect as _detect_containers
+from vault_io.layout_io import write_layout as _write_layout
 
-SCRIPT_DIR = Path(__file__).resolve().parent
-PLUGIN_DIR = SCRIPT_DIR.parent
-ASSETS_DIR = PLUGIN_DIR / "assets"
+ASSETS_DIR = Path(__file__).resolve().parent / "assets"
 
 FIXED_VAULT_DIRS = [
     "concepts",
@@ -86,17 +85,23 @@
     """Run the detector, prompt for ambiguous rows, return the pinned list."""
     records = _detect_containers(repo)
     if records and records[0]["classification"] == "single-package":
-        print("Detected: single-package repo (no structural containers).")
+        if not non_interactive:
+            print("Detected: single-package repo (no structural containers).")
+        else:
+            logger.info("Detected: single-package repo (no structural containers).")
         return []
     if not records:
         return []
 
-    print(f"Detected {len(records)} top-level container(s):")
-    print()
-    for r in records:
-        src = r["source"] or "<root>"
-        print(f"  {src:30s} -> {r['classification']:14s} ({r['children_count']} children) - {r['reason']}")
-    print()
+    if not non_interactive:
+        print(f"Detected {len(records)} top-level container(s):")
+        print()
+        for r in records:
+            src = r["source"] or "<root>"
+            print(f"  {src:30s} -> {r['classification']:14s} ({r['children_count']} children) - {r['reason']}")
+        print()
+    else:
+        logger.info("Detected %d top-level container(s).", len(records))
 
     pinned = []
     for r in records:
@@ -107,39 +112,22 @@
             else:
                 choice = (
                     input(
-                        f"  '{r['source']}' is ambiguous. Pick "
-                        f"[package/app/domain/package-family/docs/skip] (default: skip): "
+                        f"  '{r['source']}' is ambiguous. Pick [package/app/domain/docs/skip] (default: skip): "
                     ).strip()
                     or "skip"
                 )
-                valid = {"package", "app", "domain", "package-family", "docs", "skip"}
-                if choice not in valid:
+                if choice not in {"package", "app", "domain", "docs", "skip"}:
                     print(f"    invalid choice '{choice}'; defaulting to 'skip'")
                     choice = "skip"
                 cls = choice
-        # vault_dir default: for nested source paths (e.g. `references/hubspot/hubspot-ui-extensions`)
-        # use just the last segment so pages land somewhere navigable. For
-        # top-level sources, use the source name as before.
-        source = r["source"]
-        if cls in ("skip", "docs"):
-            vault_dir = None
-        else:
-            vault_dir = source.split("/")[-1] if "/" in source else source
-        row = {
-            "source": source,
-            "vault_dir": vault_dir,
-            "classification": cls,
-            "children_count": r["children_count"],
-        }
-        # Carry over package-family auto-detection metadata if present.
-        if cls == "package-family":
-            row["package_depth"] = int(r.get("package_depth") or 1)
-            # Default glob lets the scanner pick up any standard manifest deep inside.
-            if r.get("manifest_glob"):
-                row["manifest_glob"] = r["manifest_glob"]
-            if r.get("slug_source"):
-                row["slug_source"] = r["slug_source"]
-        pinned.append(row)
+        pinned.append(
+            {
+                "source": r["source"],
+                "vault_dir": None if cls in ("skip", "docs") else r["source"],
+                "classification": cls,
+                "children_count": r["children_count"],
+            }
+        )
     return pinned
 
 
@@ -147,8 +135,8 @@
     if as_json:
         print(json.dumps({"status": "error", "message": message}))
     else:
-        print(f"[error] {message}", file=sys.stderr)
-    sys.exit(1)
+        logger.error("%s", message)
+    raise RuntimeError(message)
 
 
 def init_wiki(
@@ -162,21 +150,19 @@
 ):
     """Bootstrap a Code Wiki at `wiki_path`.
 
-    Calls `lattice_workspace.init()` first to register `lattice-wiki`
-    with the workspace; `lattice_workspace` owns `<workspace>/raw/` and
-    `<workspace>/work/`. This function only writes inside `wiki_path`.
+    NOTE: The upstream implementation called a workspace.init() helper to
+    register the plugin with the workspace (creating `<workspace>/raw/`,
+    `<workspace>/work/`, `.lattice.yaml`). That dependency is not available
+    in deep-agents; Phase 5 will provide a workspace-bootstrap equivalent.
+    For now, this function only writes inside `wiki_path`.
     """
     if wiki_path.exists() and any(wiki_path.iterdir()) and not force:
         _error(f"{wiki_path} is not empty. Use --force to overwrite.", as_json)
 
-    # Register the plugin with lattice-workspace. This creates the
-    # workspace dir, .lattice.yaml, gitignore entry, and (after Task 3)
-    # writes the workspace-level CLAUDE.md.
     workspace_path = wiki_path.parent
-    try:
-        workspace_init(repo_path, plugin="lattice-wiki", version=__version__, workspace=workspace_path)
-    except Exception as e:
-        _error(f"workspace bootstrap failed: {e}", as_json)
+    # Create raw/ and work/ workspace sibling directories (Phase 5 workspace init).
+    (workspace_path / "raw").mkdir(parents=True, exist_ok=True)
+    (workspace_path / "work").mkdir(parents=True, exist_ok=True)
 
     pinned = _resolve_pinned_containers(repo_path, non_interactive)
     structural_dirs = [c["vault_dir"] for c in pinned if c["vault_dir"]]
@@ -259,10 +245,12 @@
         "date": today,
         "installed_files": installed_files,
         "page_templates_copied": template_count,
+        "raw_path": str(workspace_path / "raw"),
+        "work_path": str(workspace_path / "work"),
         "layers": {
             "wiki": f"{wiki_path}/ — LLM-maintained knowledge base",
-            "raw": f"{workspace_path}/raw/ — owned by lattice-workspace",
-            "work": f"{workspace_path}/work/ — owned by lattice-workspace",
+            "raw": f"{workspace_path}/raw/ — staging area for source ingestion",
+            "work": f"{workspace_path}/work/ — work item pages",
             "index": f"{wiki_path}/index.md",
             "log": f"{wiki_path}/log.md",
         },
@@ -277,18 +265,17 @@
         print(json.dumps(result, indent=2))
         return result
 
-    print(f"[ok] Initialized Code Wiki at: {wiki_path}")
-    print(f"     Workspace: {workspace_path}")
-    print(f"     Repo:      {repo_path}")
-    print(f"     Topic:     {topic}")
-    print(f"     Tool:      {tool}")
-    print(f"     Installed: {', '.join(installed_files)}")
-    print(f"     Page templates copied: {template_count}")
-    print()
-    print("Next steps:")
-    print(f"  1. Open {workspace_path} in Obsidian (workspace root)")
-    print("  2. Run /lattice-wiki:scan to populate wiki/packages/")
-    print(f"  3. Stage a source under {workspace_path}/raw/ and run /lattice-wiki:ingest <path>")
+    logger.info("[ok] Initialized Code Wiki at: %s", wiki_path)
+    logger.info("     Workspace: %s", workspace_path)
+    logger.info("     Repo:      %s", repo_path)
+    logger.info("     Topic:     %s", topic)
+    logger.info("     Tool:      %s", tool)
+    logger.info("     Installed: %s", ", ".join(installed_files))
+    logger.info("     Page templates copied: %d", template_count)
+    logger.info("Next steps:")
+    logger.info("  1. Open %s in Obsidian (workspace root)", workspace_path)
+    logger.info("  2. Run /lattice-wiki:scan to populate wiki/packages/")
+    logger.info("  3. Stage a source under %s/raw/ and run /lattice-wiki:ingest <path>", workspace_path)
     return result
 
 
@@ -315,10 +302,8 @@
         help="Don't prompt for ambiguous containers; mark them skip.",
     )
     args = p.parse_args()
-    wiki, repo = resolve_wiki_and_repo()
-    if repo is None:
-        print("[error] could not resolve repo root from workspace", file=sys.stderr)
-        sys.exit(1)
+    wiki, _ = resolve_wiki_and_repo()
+    repo = wiki.parent  # v1: repo is always wiki's parent directory
     init_wiki(
         wiki,
         repo,
```

### lint/*

#### lint/common.py

```diff
--- /Users/pat/Personal/lattice/packages/lattice-wiki-core/src/lattice_wiki_core/lint/common.py	2026-05-10 17:35:16
+++ packages/vault-io/src/vault_io/lint/common.py	2026-05-18 11:51:36
@@ -31,8 +31,26 @@
 # for wikilinks — bracketed content inside code is content, not a link.
 FENCED_CODE_RE = re.compile(r"```.*?```", re.DOTALL)
 INLINE_CODE_RE = re.compile(r"`[^`\n]*`")
+
+
+def _is_placeholder_target(target: str) -> bool:
+    """Check if a wikilink target is a placeholder/template token.
+
+    Placeholder targets contain template tokens like ..., <name>, etc.
+    and should not be treated as broken links.
+
+    Relocated from the upstream lint_wiki module so the predicate sits next
+    to WIKILINK_RE in the shared lint helpers module.
+
+    Args:
+        target: The wikilink target string (e.g., "wiki/packages/...")
 
+    Returns:
+        True if target contains placeholder markers (..., <, or >), False otherwise.
+    """
+    return "..." in target or "<" in target or ">" in target
 
+
 def parse_frontmatter(text: str) -> dict:
     m = FRONTMATTER_RE.match(text)
     if not m:
@@ -60,7 +78,7 @@
     m = FRONTMATTER_RE.match(text)
     if not m:
         return text
-    return text[m.end():]
+    return text[m.end() :]
 
 
 def expand_braces(name: str) -> list[str]:
```

#### lint/container.py

```diff
--- /Users/pat/Personal/lattice/packages/lattice-wiki-core/src/lattice_wiki_core/lint/container.py	2026-05-16 20:55:44
+++ packages/vault-io/src/vault_io/lint/container.py	2026-05-18 11:51:36
@@ -4,7 +4,7 @@
 
 from pathlib import Path
 
-from lattice_wiki_core.layout_io import read_layout
+from vault_io.layout_io import read_layout
 
 GROUP = "container"
 
@@ -43,19 +43,8 @@
         if src and not (repo / src).exists():
             issues.append(f"pinned container '{src}' has no source dir on disk")
 
-    # Vault dirs that aren't pinned and aren't fixed cross-cutting dirs.
-    # Nested vault_dirs (e.g. ``domains/hubspot/packages``) contribute their
-    # top-level segment to the allowlist so the parent isn't flagged as orphan.
-    pinned_vault_dirs: set[str] = set()
-    for c in pinned:
-        vd = c.get("vault_dir")
-        if not vd:
-            continue
-        pinned_vault_dirs.add(vd)
-        # First path segment.
-        top = vd.split("/", 1)[0]
-        if top:
-            pinned_vault_dirs.add(top)
+    # Vault dirs that aren't pinned and aren't fixed cross-cutting dirs
+    pinned_vault_dirs = {c.get("vault_dir") for c in pinned if c.get("vault_dir")}
     vault_root = wiki
     if vault_root.exists():
         for d in sorted(vault_root.iterdir()):
```

#### lint/dependency.py

```diff
--- /Users/pat/Personal/lattice/packages/lattice-wiki-core/src/lattice_wiki_core/lint/dependency.py	2026-05-09 16:29:01
+++ packages/vault-io/src/vault_io/lint/dependency.py	2026-05-18 11:51:36
@@ -10,7 +10,7 @@
 
 from pathlib import Path
 
-from lattice_wiki_core.lint.common import parse_inline_list
+from vault_io.lint.common import parse_inline_list
 
 GROUP = "dependency_layer"
 
@@ -54,10 +54,13 @@
             family_name = (fm.get("family_name") or Path(key).name).strip()
             family_pages[family_name] = {"key": key, "fm": fm, "members": members}
 
-        # dep-detail-without-load-bearing: detail page exists ⇒ load_bearing must be true
-        load_bearing = (fm.get("load_bearing") or "").strip().lower()
-        if load_bearing not in ("true", "yes", "1"):
-            findings.append(f"{key}: dep-detail-without-load-bearing: detail page exists but load_bearing != true")
+        # dep-detail-without-load-bearing: package detail pages must declare load_bearing.
+        # Only applies to kind == "package" — service and package-family pages are not
+        # individual dependency detail pages in the same semantic sense.
+        if kind == "package":
+            load_bearing = (fm.get("load_bearing") or "").strip().lower()
+            if load_bearing not in ("true", "yes", "1"):
+                findings.append(f"{key}: dep-detail-without-load-bearing: detail page exists but load_bearing != true")
 
         # dep-stub-detail-page: body <15 lines beyond frontmatter
         body_lines = _body_line_count(page["text"])
```

#### lint/domain.py

IDENTICAL

#### lint/file_map.py

```diff
--- /Users/pat/Personal/lattice/packages/lattice-wiki-core/src/lattice_wiki_core/lint/file_map.py	2026-05-08 15:45:24
+++ packages/vault-io/src/vault_io/lint/file_map.py	2026-05-18 11:51:36
@@ -4,12 +4,12 @@
 
 from pathlib import Path
 
-from lattice_wiki_core.lint.common import FILE_MAP_SECTION_RE, parse_section_entries
+from vault_io.lint.common import FILE_MAP_SECTION_RE, parse_section_entries
 
 GROUP = "file_map"
 
 try:
-    from lattice_wiki_core.scan_monorepo import _git_ls_files as _scan_git_ls_files
+    from vault_io.scan_monorepo import _git_ls_files as _scan_git_ls_files
 except ImportError:
     _scan_git_ls_files = None
 
```

#### lint/package_sync.py

```diff
--- /Users/pat/Personal/lattice/packages/lattice-wiki-core/src/lattice_wiki_core/lint/package_sync.py	2026-05-09 14:45:49
+++ packages/vault-io/src/vault_io/lint/package_sync.py	2026-05-18 11:51:36
@@ -5,7 +5,7 @@
 
 from pathlib import Path
 
-from lattice_wiki_core.lint.common import parse_frontmatter
+from vault_io.lint.common import parse_frontmatter
 
 GROUP = "package_sync"
 
@@ -19,7 +19,7 @@
     of changed files. Pages without `last_sync_commit` are surfaced as
     'never synced'.
     """
-    from lattice_wiki_core.git_state import changed_files_since
+    from vault_io.git_state import changed_files_since
 
     issues: list[str] = []
     vault = wiki
```

#### lint/source_sync.py

```diff
--- /Users/pat/Personal/lattice/packages/lattice-wiki-core/src/lattice_wiki_core/lint/source_sync.py	2026-05-09 14:45:54
+++ packages/vault-io/src/vault_io/lint/source_sync.py	2026-05-18 11:51:36
@@ -5,7 +5,7 @@
 
 from pathlib import Path
 
-from lattice_wiki_core.lint.common import parse_frontmatter
+from vault_io.lint.common import parse_frontmatter
 
 GROUP = "source_sync"
 
@@ -19,7 +19,7 @@
     are immutable by design and don't carry `last_sync_commit`, so they're
     skipped via the empty-SHA filter. Missing source files are flagged.
     """
-    from lattice_wiki_core.git_state import changed_files_since
+    from vault_io.git_state import changed_files_since
 
     issues: list[str] = []
     sources_dir = wiki / "sources"
```

#### lint/workflow_hints.py

```diff
--- /Users/pat/Personal/lattice/packages/lattice-wiki-core/src/lattice_wiki_core/lint/workflow_hints.py	2026-05-08 15:45:24
+++ packages/vault-io/src/vault_io/lint/workflow_hints.py	2026-05-18 11:51:36
@@ -4,8 +4,8 @@
 
 from pathlib import Path
 
-from lattice_wiki_core.lint.common import FRONTMATTER_RE as _FRONTMATTER_RE
-from lattice_wiki_core.lint.common import parse_inline_list
+from vault_io.lint.common import FRONTMATTER_RE as _FRONTMATTER_RE
+from vault_io.lint.common import parse_inline_list
 
 GROUP = "workflow_hints"
 
```

### layout_io.py

```diff
--- /Users/pat/Personal/lattice/packages/lattice-wiki-core/src/lattice_wiki_core/layout_io.py	2026-05-17 14:46:06
+++ packages/vault-io/src/vault_io/layout_io.py	2026-05-18 11:51:36
@@ -1,6 +1,6 @@
 #!/usr/bin/env python3
 """
-layout_io.py — Read and write the lattice-wiki layout block in CLAUDE.md / AGENTS.md.
+layout_io.py — Read and write the vault-io layout block in CLAUDE.md / AGENTS.md.
 
 The layout block is delimited by sentinel HTML comments and contains a YAML
 document inside a fenced code block. Format:
@@ -64,9 +64,6 @@
 # ---------- minimal YAML serializer for our schema ----------
 
 
-_PACKAGE_FAMILY_FIELDS = ("package_depth", "manifest_glob", "slug_source", "domain")
-
-
 def _emit_yaml(layout: dict) -> str:
     out = []
     out.append(f"version: {int(layout.get('version', 1))}")
@@ -79,9 +76,6 @@
         out.append(f"    classification: {c['classification']}")
         if "children_count" in c:
             out.append(f"    children_count: {int(c['children_count'])}")
-        for field in _PACKAGE_FAMILY_FIELDS:
-            if c.get(field) is not None:
-                out.append(f"    {field}: {_emit_scalar(c[field])}")
         if c.get("note"):
             out.append(f'    note: "{c["note"]}"')
     return "\n".join(out) + "\n"
@@ -124,10 +118,10 @@
             current[k.strip()] = _parse_scalar(v.strip())
             continue
     if "version" in out:
-        out["version"] = int(out["version"])
-    for c in out["containers"]:
-        if "package_depth" in c and c["package_depth"] is not None:
-            c["package_depth"] = int(c["package_depth"])
+        try:
+            out["version"] = int(out["version"])
+        except (ValueError, TypeError):
+            out["version"] = 1  # fall back to v1 schema
     return out
 
 
@@ -165,100 +159,8 @@
     pkg_dir.mkdir(parents=True, exist_ok=True)
     dest.write_text(text, encoding="utf-8")
     return dest, True
-
-
-def ensure_package_pages(
-    pkg_dir: Path,
-    pkg_title: str,
-    templates_dir: Path,
-    today: Optional[str] = None,
-) -> dict[str, bool]:
-    """Create the package overview + every sub-page from ``templates_dir/package/*.md``.
-
-    Mapping:
-      ``overview.md``  ->  ``<pkg_dir>/<pkg_dir.name>.md``
-      ``<stem>.md``    ->  ``<pkg_dir>/<stem>.md``
-
-    Returns a dict mapping output stem -> ``True`` if just created, ``False``
-    if the destination already existed. Idempotent.
-
-    Raises ``FileNotFoundError`` if ``templates_dir/package/`` does not exist
-    or contains no ``*.md`` files.
-    """
-    pkg_templates = templates_dir / "package"
-    if not pkg_templates.is_dir():
-        raise FileNotFoundError(f"template dir not found: {pkg_templates}")
-    templates = sorted(pkg_templates.glob("*.md"))
-    if not templates:
-        raise FileNotFoundError(f"no *.md templates in: {pkg_templates}")
-
-    result: dict[str, bool] = {}
-    date = today or dt.date.today().isoformat()
-    pkg_dir.mkdir(parents=True, exist_ok=True)
-    for tmpl in templates:
-        stem = tmpl.stem
-        if stem == "overview":
-            dest = pkg_dir / f"{pkg_dir.name}.md"
-            out_key = pkg_dir.name
-        else:
-            dest = pkg_dir / f"{stem}.md"
-            out_key = stem
-        if dest.exists():
-            result[out_key] = False
-            continue
-        text = tmpl.read_text(encoding="utf-8")
-        text = text.replace("{{PACKAGE_TITLE}}", pkg_title).replace("{{DATE}}", date)
-        dest.write_text(text, encoding="utf-8")
-        result[out_key] = True
-    return result
 
 
-def ensure_domain_pages(
-    domain_dir: Path,
-    domain_title: str,
-    templates_dir: Path,
-    today: Optional[str] = None,
-) -> dict[str, bool]:
-    """Create the domain overview + every sub-page from ``templates_dir/domain/*.md``.
-
-    Mapping:
-      ``overview.md``  ->  ``<domain_dir>/<domain_dir.name>.md``
-      ``<stem>.md``    ->  ``<domain_dir>/<stem>.md``
-
-    Returns a dict mapping output stem -> ``True`` if just created, ``False``
-    if the destination already existed. Idempotent.
-
-    Raises ``FileNotFoundError`` if ``templates_dir/domain/`` does not exist
-    or contains no ``*.md`` files.
-    """
-    domain_templates = templates_dir / "domain"
-    if not domain_templates.is_dir():
-        raise FileNotFoundError(f"template dir not found: {domain_templates}")
-    templates = sorted(domain_templates.glob("*.md"))
-    if not templates:
-        raise FileNotFoundError(f"no *.md templates in: {domain_templates}")
-
-    result: dict[str, bool] = {}
-    date = today or dt.date.today().isoformat()
-    domain_dir.mkdir(parents=True, exist_ok=True)
-    for tmpl in templates:
-        stem = tmpl.stem
-        if stem == "overview":
-            dest = domain_dir / f"{domain_dir.name}.md"
-            out_key = domain_dir.name
-        else:
-            dest = domain_dir / f"{stem}.md"
-            out_key = stem
-        if dest.exists():
-            result[out_key] = False
-            continue
-        text = tmpl.read_text(encoding="utf-8")
-        text = text.replace("{{DOMAIN_TITLE}}", domain_title).replace("{{DATE}}", date)
-        dest.write_text(text, encoding="utf-8")
-        result[out_key] = True
-    return result
-
-
 def ensure_domain_page(
     domain_dir: Path,
     domain_title: str,
```

### detect_containers.py

```diff
--- /Users/pat/Personal/lattice/packages/lattice-wiki-core/src/lattice_wiki_core/detect_containers.py	2026-05-16 20:55:44
+++ packages/vault-io/src/vault_io/detect_containers.py	2026-05-18 11:51:36
@@ -3,18 +3,13 @@
 detect_containers.py — Classify a repo's top-level directories into container types.
 
 Usage:
-    python detect_containers.py --json   # repo discovered via lattice-workspace
+    python detect_containers.py --json   # repo discovered via GRAPH_WIKI_WORKSPACE or git
 
 Returns a list of records:
     {"source": "<dir>", "classification": "<type>", "children_count": N, "reason": "<why>"}
 
 Classifications:
     - "app" / "package" / "domain" / "docs"   — concrete container types
-    - "package-family"                         — directory whose children are the wiki packages but
-                                                 whose manifests sit deeper (2+ levels). Carries
-                                                 a `source` path that may be nested (e.g.
-                                                 ``references/hubspot/hubspot-ui-extensions``) and
-                                                 a suggested ``package_depth`` (default 1).
     - "single-package"                         — repo root is itself a package, no containers
     - "ambiguous"                              — needs user decision
 """
@@ -26,7 +21,7 @@
 import sys
 from pathlib import Path
 
-from lattice_wiki_core._workspace import resolve_wiki_and_repo
+from vault_io._workspace import resolve_wiki_and_repo
 
 MANIFEST_FILES = {
     "package.json",
@@ -52,11 +47,6 @@
 }
 DOC_THRESHOLD = 0.7
 DOMAIN_THRESHOLD = 0.5
-PACKAGE_FAMILY_THRESHOLD = 0.5
-# How deep to walk under a candidate package dir when checking for manifests.
-PACKAGE_FAMILY_MANIFEST_DEPTH = 4
-# How deep to descend from a top-level dir when searching for package-family shapes.
-PACKAGE_FAMILY_SEARCH_DEPTH = 3
 
 
 def _has_manifest(d: Path) -> bool:
@@ -87,107 +77,22 @@
     return any(_is_package_container_shape(k) for k in _immediate_subdirs(d))
 
 
-def _has_descendant_manifest(d: Path, max_depth: int = PACKAGE_FAMILY_MANIFEST_DEPTH) -> bool:
-    """Does `d` contain a manifest at any depth up to `max_depth` (inclusive)?
-
-    `max_depth=1` means an immediate child has a manifest.
-    """
-    if max_depth <= 0:
-        return False
-    for kid in _immediate_subdirs(d):
-        if _has_manifest(kid):
-            return True
-        if _has_descendant_manifest(kid, max_depth - 1):
-            return True
-    return False
-
-
-def _is_package_family_shape(d: Path) -> tuple[bool, str]:
-    """A directory is a 'package-family' if it looks like a curated collection of
-    packages whose manifests sit deeper than the scanner's `domain` walk would
-    normally find.
-
-    Specifically:
-      - D has ≥2 immediate children.
-      - No immediate child has its own top-level manifest (else it's a `package`
-        container, handled by the regular rule).
-      - At least PACKAGE_FAMILY_THRESHOLD of the children have a descendant
-        manifest somewhere ≥2 levels deeper (depth 2..PACKAGE_FAMILY_MANIFEST_DEPTH).
-
-    Returns (matches, reason).
-    """
-    if _has_manifest(d):
-        return False, "directory itself has a manifest"
-    kids = _immediate_subdirs(d)
-    if len(kids) < 2:
-        return False, "fewer than 2 children"
-    if any(_has_manifest(k) for k in kids):
-        return False, "at least one child has a top-level manifest (regular package container)"
-
-    deep = 0
-    for kid in kids:
-        # Skip depth 1 (immediate-child manifest is the regular `package` case,
-        # already excluded above). Look at depth 2..MAX for a descendant manifest.
-        has_deep = any(
-            _has_descendant_manifest(grand, PACKAGE_FAMILY_MANIFEST_DEPTH - 1)
-            or _has_manifest(grand)
-            for grand in _immediate_subdirs(kid)
-        )
-        if has_deep:
-            deep += 1
-    if not kids:
-        return False, "no children"
-    ratio = deep / len(kids)
-    if ratio >= PACKAGE_FAMILY_THRESHOLD:
-        return True, f"{deep}/{len(kids)} children have manifests ≥2 levels deeper"
-    return False, f"only {deep}/{len(kids)} children have deep manifests"
-
-
-def _find_package_families(
-    root: Path,
-    repo_root: Path,
-    max_descent: int = PACKAGE_FAMILY_SEARCH_DEPTH,
-) -> list[dict]:
-    """Recursively find package-family containers under `root`.
-
-    Walks up to `max_descent` levels below `root`. Stops descent on a hit:
-    returns the outermost package-family at each branch, not nested ones.
-    """
-    if max_descent <= 0:
-        return []
-    matches, reason = _is_package_family_shape(root)
-    if matches:
-        kids = _immediate_subdirs(root)
-        rel = root.relative_to(repo_root).as_posix()
-        return [
-            {
-                "source": rel,
-                "classification": "package-family",
-                "children_count": len(kids),
-                "package_depth": 1,
-                "reason": reason,
-            }
-        ]
-    out: list[dict] = []
-    for kid in _immediate_subdirs(root):
-        out.extend(_find_package_families(kid, repo_root, max_descent - 1))
-    return out
-
-
 def _classify_dir(d: Path) -> dict:
     children = _immediate_subdirs(d)
     files = [p for p in d.iterdir() if p.is_file() and not p.name.startswith(".")]
     md_files = [p for p in files if p.suffix == ".md"]
     has_manifest_in_root = _has_manifest(d)
 
-    # Rule 1: docs container — children predominantly markdown, no manifests anywhere
-    if files and not children and not has_manifest_in_root:
-        if len(md_files) / max(len(files), 1) >= DOC_THRESHOLD:
+    # Rule 1: docs container — recursively predominantly markdown, no manifests anywhere
+    if not has_manifest_in_root and not any(_has_manifest(c) for c in children):
+        total_files = sum(1 for p in d.rglob("*") if p.is_file() and not p.name.startswith("."))
+        md_count = sum(1 for p in d.rglob("*.md") if not p.name.startswith("."))
+        if total_files and md_count / total_files >= DOC_THRESHOLD:
             return {
                 "source": d.name,
                 "classification": "docs",
-                "children_count": len(md_files),
-                "reason": f"{len(md_files)}/{len(files)} files are .md, no manifests",
+                "children_count": md_count,
+                "reason": f"{md_count}/{total_files} files are .md, no manifests",
             }
 
     # Rule 2: domain container — majority of children are themselves package containers
@@ -258,50 +163,16 @@
             }
         ]
 
-    # Look for package-family containers. Two paths:
-    #   - Promote a top-level *ambiguous* dir to package-family if it has the
-    #     shape itself. (Never override a real package/app/domain/docs classification.)
-    #   - For top-level ambiguous dirs that aren't themselves a family, recurse
-    #     up to PACKAGE_FAMILY_SEARCH_DEPTH levels to surface nested ones.
-    family_records: list[dict] = []
-    seen_sources = {r["source"] for r in records}
-    for d in top:
-        kid_classification = next(
-            (r["classification"] for r in records if r["source"] == d.name),
-            None,
-        )
-        # Only consider ambiguous dirs — never touch structural classifications.
-        if kid_classification != "ambiguous":
-            continue
-        top_match, top_reason = _is_package_family_shape(d)
-        if top_match:
-            for r in records:
-                if r["source"] == d.name:
-                    r["classification"] = "package-family"
-                    r["package_depth"] = 1
-                    r["reason"] = top_reason
-                    break
-            continue
-        # Recurse to find nested package-families (e.g.
-        # `references/hubspot/hubspot-ui-extensions`).
-        for fam in _find_package_families(d, repo_root):
-            if fam["source"] in seen_sources:
-                continue
-            family_records.append(fam)
-            seen_sources.add(fam["source"])
+    return sorted(records, key=lambda r: r["source"])
 
-    return sorted(records + family_records, key=lambda r: r["source"])
 
-
 def main():
     p = argparse.ArgumentParser(description="Classify a repo's top-level dirs.")
     p.add_argument("--json", action="store_true", help="Emit JSON")
     args = p.parse_args()
 
-    _, repo = resolve_wiki_and_repo()
-    if repo is None:
-        print("[error] could not resolve repo root from workspace", file=sys.stderr)
-        sys.exit(1)
+    wiki, _ = resolve_wiki_and_repo()
+    repo = wiki.parent  # v1: repo is always wiki's parent directory
     if not repo.exists():
         print(f"[error] repo not found: {repo}", file=sys.stderr)
         sys.exit(1)
```

### scan_monorepo.py

```diff
--- /Users/pat/Personal/lattice/packages/lattice-wiki-core/src/lattice_wiki_core/scan_monorepo.py	2026-05-16 20:55:44
+++ packages/vault-io/src/vault_io/scan_monorepo.py	2026-05-18 11:51:36
@@ -12,8 +12,8 @@
   - package.json + pnpm-workspace.yaml / workspaces field  (Node/pnpm/yarn/npm)
   - pyproject.toml                                         (Python — poetry/hatch/uv)
   - Cargo.toml with [workspace]                            (Rust)
-  - go.mod + go.work                                       (Go)
   - .claude-plugin/plugin.json                             (Claude Code plugins)
+  # TODO: go.mod + go.work (Go) — not yet implemented
 
 For each detected package, emits:
   - name, path (relative to repo), type (library/app/service), language
@@ -42,9 +42,8 @@
 import sys
 from pathlib import Path
 
-from lattice_wiki_core._version_check import check_for_updates
-from lattice_wiki_core._workspace import resolve_wiki_and_repo
-from lattice_wiki_core.layout_io import read_layout
+from vault_io._workspace import resolve_wiki_and_repo
+from vault_io.layout_io import read_layout
 
 FRONTMATTER_RE = re.compile(r"^---\s*\n(.*?)\n---\s*\n", re.DOTALL)
 
@@ -419,136 +418,8 @@
         return f"domains/{domain}/packages/{name}/{name}.md"
     base = vault_dir or "packages"
     return f"{base}/{name}/{name}.md"
-
-
-DEFAULT_PACKAGE_FAMILY_MANIFEST_GLOB = "**/package.json"
-DEFAULT_PACKAGE_FAMILY_PACKAGE_DEPTH = 1
-
-
-def _collect_at(repo: Path, path: Path):
-    """Try each known manifest collector on `path`; return the first hit or None."""
-    return (
-        _collect_node_package(repo, path)
-        or _collect_python_package(repo, path)
-        or _collect_rust_crate(repo, path)
-        or _collect_claude_plugin(repo, path)
-    )
-
-
-def _iter_package_family_dirs(src: Path, depth: int):
-    """Yield each directory `depth` levels below `src`.
-
-    depth=1 means immediate children of src.
-    """
-    if depth <= 0:
-        yield src
-        return
-    if not src.is_dir():
-        return
-    for kid in sorted(p for p in src.iterdir() if p.is_dir() and not p.name.startswith(".")):
-        yield from _iter_package_family_dirs(kid, depth - 1)
-
-
-def _find_manifests(pkg_dir: Path, glob: str) -> list[Path]:
-    """Find all manifest files under `pkg_dir` matching `glob`.
-
-    Filters out paths inside skipped directories (node_modules, dist, etc.).
-    Returns sorted by relative path for determinism.
-    """
-    skip_segments = {"node_modules", ".git", "dist", "build", "target", ".next", ".turbo", ".venv", "venv"}
-    matches = []
-    for m in pkg_dir.rglob(glob):
-        if not m.is_file():
-            continue
-        if any(part in skip_segments for part in m.relative_to(pkg_dir).parts):
-            continue
-        matches.append(m)
-    return sorted(matches)
 
 
-def _collect_package_family_member(
-    repo: Path,
-    pkg_dir: Path,
-    manifest_glob: str,
-    slug_source: str,
-) -> dict | None:
-    """Build a workspace entry for one package within a package-family container.
-
-    The `manifests:` field aggregates all matching manifest files found inside
-    `pkg_dir` (handles multi-variant packages like private+public HubSpot apps).
-    """
-    manifests = _find_manifests(pkg_dir, manifest_glob)
-    if not manifests:
-        return None
-
-    manifest_entries: list[dict] = []
-    primary_collected: dict | None = None
-    for m in manifests:
-        # Try collecting with the deepest known collector for this manifest type.
-        manifest_dir = m.parent
-        collected = _collect_at(repo, manifest_dir)
-        if collected is None:
-            # Manifest exists but is empty/no-name; record what we can.
-            manifest_entries.append({
-                "path": str(m.relative_to(repo)).replace("\\", "/"),
-                "name": None,
-                "language": None,
-                "ecosystem": None,
-            })
-            continue
-        manifest_entries.append({
-            "path": str(m.relative_to(repo)).replace("\\", "/"),
-            "name": collected.get("name"),
-            "language": collected.get("language"),
-            "ecosystem": collected.get("ecosystem"),
-        })
-        if primary_collected is None:
-            primary_collected = collected
-
-    if primary_collected is None:
-        # No usable manifest found; emit a degenerate entry so it's still tracked.
-        return {
-            "name": pkg_dir.name,
-            "path": str(pkg_dir.relative_to(repo)).replace("\\", "/"),
-            "type": "library",
-            "language": "unknown",
-            "version": None,
-            "depends_on": [],
-            "external_deps": {},
-            "ecosystem": None,
-            "exports": [],
-            "scripts": [],
-            "manifests": manifest_entries,
-        }
-
-    # Slug: dirname is the default for package-family (handles colliding manifest
-    # names like private/public both named "charts"). Explicit override available.
-    if slug_source == "manifest":
-        name = primary_collected.get("name") or pkg_dir.name
-    else:
-        name = pkg_dir.name
-
-    # `type` on a package-family member always defaults to "library": the
-    # container declares that each child dir is a sample/library, regardless
-    # of whether the deep nested manifest happens to carry a `start` script
-    # or a `private: true` flag (which would otherwise be heuristically
-    # promoted to "app" by `_infer_package_type` and divert the page into
-    # `apps/`). Respect the container's intent.
-    return {
-        "name": name,
-        "path": str(pkg_dir.relative_to(repo)).replace("\\", "/"),
-        "type": "library",
-        "language": primary_collected.get("language", "unknown"),
-        "version": primary_collected.get("version"),
-        "depends_on": primary_collected.get("depends_on", []),
-        "external_deps": primary_collected.get("external_deps", {}),
-        "ecosystem": primary_collected.get("ecosystem"),
-        "exports": primary_collected.get("exports", []),
-        "scripts": primary_collected.get("scripts", []),
-        "manifests": manifest_entries,
-    }
-
-
 def _discover_from_pinned(repo: Path, containers: list) -> list:
     workspaces = []
     seen_paths = set()
@@ -587,24 +458,6 @@
                     pkg["_container_vault_dir"] = c.get("vault_dir")
                     workspaces.append(pkg)
                     seen_paths.add(child.resolve())
-        elif cls == "package-family":
-            # A package-family container holds packages at a configurable depth
-            # below its source, where the manifests for each package may live
-            # several levels deeper (e.g. ``private/src/app/extensions/package.json``).
-            depth = int(c.get("package_depth") or DEFAULT_PACKAGE_FAMILY_PACKAGE_DEPTH)
-            manifest_glob = c.get("manifest_glob") or DEFAULT_PACKAGE_FAMILY_MANIFEST_GLOB
-            slug_source = c.get("slug_source") or "dirname"
-            domain = c.get("domain")
-            for pkg_dir in _iter_package_family_dirs(src, depth):
-                if pkg_dir.resolve() in seen_paths:
-                    continue
-                pkg = _collect_package_family_member(repo, pkg_dir, manifest_glob, slug_source)
-                if pkg:
-                    if domain:
-                        pkg["domain"] = domain
-                    pkg["_container_vault_dir"] = c.get("vault_dir")
-                    workspaces.append(pkg)
-                    seen_paths.add(pkg_dir.resolve())
         elif cls == "domain":
             # A domain dir may either hold packages directly
             # (``domains/<d>/<pkg>/``) or group them under a package container
@@ -862,7 +715,7 @@
         that SHA, [] when no changes, or None when no recorded SHA exists
         (bootstrap case — caller should treat as "first sync").
     """
-    from lattice_wiki_core.git_state import changed_files_since
+    from vault_io.git_state import changed_files_since
 
     by_name = {unscope(w["name"]): w for w in workspaces}
     for name, w in by_name.items():
@@ -884,7 +737,7 @@
     reviewed packages. When allowed=False, scan still runs in read-only
     mode — it reports drift but does not bump state.
     """
-    from lattice_wiki_core.git_state import head_commit, is_clean_main
+    from vault_io.git_state import head_commit, is_clean_main
 
     ok, reason = is_clean_main(repo)
     return {
@@ -898,7 +751,7 @@
     """Compare current detection against pinned layout. Returns:
     {"new": [<record>...], "missing": [<source>...], "changed": [{source, from, to}...]}
     """
-    from lattice_wiki_core.detect_containers import detect
+    from vault_io.detect_containers import detect
 
     detected = detect(repo)
     detected_by_source = {r["source"]: r for r in detected if r["source"]}
@@ -1226,11 +1079,8 @@
     )
     args = p.parse_args()
 
-    wiki, repo = resolve_wiki_and_repo()
-    check_for_updates(wiki.parent)
-    if repo is None:
-        print("[error] could not resolve repo root from workspace", file=sys.stderr)
-        sys.exit(1)
+    wiki, _ = resolve_wiki_and_repo()
+    repo = wiki.parent  # v1: repo is always wiki's parent directory
     if not repo.exists():
         print(f"[error] repo not found: {repo}", file=sys.stderr)
         sys.exit(1)
@@ -1304,7 +1154,6 @@
         dep_str = f" deps={len(w['depends_on'])}, used-by={w['depended_on_by']}"
         print(f"  - {w['name']} ({w['type']}, {w['language']}) @ {w['path']}{dep_str}")
     if wiki.exists():
-        vault = wiki
         print()
         print(f"Diff against {wiki}/{{apps,packages,domains/*/packages}}/")
         print(f"  new:       {len(diff['new'])}")
@@ -1330,7 +1179,7 @@
             print(f"  ✎ {path}")
 
 
-# Public alias so callers can do: from lattice_wiki_core.scan_monorepo import scan
+# Public alias so callers can do: from vault_io.scan_monorepo import scan
 scan = discover_workspaces
 
 
```

### ingest_source.py

```diff
--- /Users/pat/Personal/lattice/packages/lattice-wiki-core/src/lattice_wiki_core/ingest_source.py	2026-05-09 21:16:14
+++ packages/vault-io/src/vault_io/ingest_source.py	2026-05-18 11:51:36
@@ -1,44 +1,32 @@
-#!/usr/bin/env python3
 """
-ingest_source.py — Prepare a source for LLM ingestion into a Code Wiki.
+ingest_source.py — Library functions for preparing a source for LLM ingestion.
 
-Extracts text and metadata from a source file and emits a JSON brief the LLM
-(via /lattice-wiki:ingest or the ingestor sub-agent) can use.
+Extracted from lattice-wiki-core's ingest_source.py.
+Library functions only — no argparse main(), no version-check, no subprocess calls.
 
-Sources can live in two places:
-  - <workspace>/raw/<...> — clipped articles, specs, PRs, transcripts you've staged
-  - <repo>/<docs-container>/<...>.md — in-repo design docs / READMEs that the
-    scan flagged as ingest candidates. These sources are read in place; the
-    summary page records `source_path` (repo-relative) and `last_sync_commit`
-    (HEAD SHA at ingest time) so /lattice-wiki:lint can flag staleness when the file
-    changes after the recorded commit.
-
 Supported source formats (stdlib only): .md .txt .html .htm .json .csv
-For .pdf, let the LLM read the file directly via its Read tool.
 
-NOTE: when the in-repo flow was introduced (2026-04-30), only .md docs are
-auto-surfaced by /lattice-wiki:scan. Other formats (.docx, .pdf, etc.) are deferred —
-see references/ingest-workflow.md "Future formats".
-
-Usage:
-    python ingest_source.py --source raw/specs/auth.md
-    python ingest_source.py --source raw/articles/clip.html --json
-    python ingest_source.py --source docs/architecture.md
+Exports:
+    slugify(text) -> str
+    extract(path) -> tuple[str, str | None]
+    guess_source_type(rel_to_wiki, rel_to_repo) -> str
+    language_for(path) -> str
+    list_folder_files(root) -> list[tuple[str, int]]
+    pick_representative(root, entries) -> str | None
+    folder_brief(root, rel_to_wiki) -> dict
+    _HTMLTextExtractor
 """
 
 from __future__ import annotations
 
-import argparse
-import datetime as dt
-import hashlib
 import html.parser
 import json
 import re
-import sys
 from pathlib import Path
 
-from lattice_wiki_core._version_check import check_for_updates
-from lattice_wiki_core._workspace import resolve_wiki_and_repo
+from vault_io._workspace import resolve_wiki_and_repo
+from vault_io.layout_io import ensure_subpage
+from vault_io.scan_monorepo import compute_state_gate
 
 PREVIEW_CHARS = 1200
 SLUG_RE = re.compile(r"[^a-z0-9]+")
@@ -69,7 +57,7 @@
 ERROR_FILE_COUNT = 200
 
 
-def slugify(text):
+def slugify(text: str) -> str:
     text = text.lower().strip()
     text = SLUG_RE.sub("-", text).strip("-")
     return text[:60] or "untitled"
@@ -109,7 +97,7 @@
         return "\n".join(self.parts)
 
 
-def extract(path):
+def extract(path: Path) -> tuple[str, str | None]:
     ext = path.suffix.lower()
     data = path.read_bytes()
     if ext in {".md", ".txt"}:
@@ -142,7 +130,7 @@
         return "", None
 
 
-def guess_source_type(rel_to_wiki, rel_to_repo):
+def guess_source_type(rel_to_wiki: Path | None, rel_to_repo: Path | None) -> str:
     """Guess source_type from where the file lives.
 
     `rel_to_wiki` is the source path relative to the wiki (e.g. raw/specs/x.md)
@@ -168,11 +156,11 @@
     return "note"
 
 
-def language_for(path):
+def language_for(path: Path) -> str:
     return LANGUAGE_BY_EXT.get(path.suffix.lower(), "unknown")
 
 
-def list_folder_files(root):
+def list_folder_files(root: Path) -> list[tuple[str, int]]:
     """Return sorted (rel_path, size) for every regular file under root."""
     entries = []
     for p in sorted(root.rglob("*")):
@@ -182,7 +170,7 @@
     return entries
 
 
-def pick_representative(root, entries):
+def pick_representative(root: Path, entries: list[tuple[str, int]]) -> str | None:
     """Return rel-path of representative file.
     Priority: README.md (case-insensitive) -> index.{ts,tsx,js,py,go,rs} -> largest.
     """
@@ -198,7 +186,7 @@
     return sorted_entries[0][0]
 
 
-def folder_brief(root, rel_to_wiki):
+def folder_brief(root: Path, rel_to_wiki: Path | None) -> dict:
     """Build the folder-mode addendum to the brief.
     Returns dict; if too many files, returns {'_error': ...} so caller can exit non-zero.
     """
@@ -221,172 +209,3 @@
         "representative_file": representative,
         "warnings": warnings,
     }
-
-
-def main():
-    p = argparse.ArgumentParser(description="Prepare a source for Code Wiki ingestion.")
-    p.add_argument("--source", required=True)
-    p.add_argument("--json", action="store_true")
-    p.add_argument(
-        "--pkg-dir",
-        default=None,
-        help="Vault package directory path. When given, ensures api/patterns/context/work sub-pages exist.",
-    )
-    p.add_argument(
-        "--pkg-title",
-        default=None,
-        help="Package display title for sub-page template substitution.",
-    )
-    args = p.parse_args()
-
-    wiki, repo = resolve_wiki_and_repo()
-    check_for_updates(wiki.parent)
-    src = Path(args.source).expanduser()
-    # Resolve --source relative to repo first (for `docs/intro.md` style),
-    # then wiki, then cwd.
-    if not src.is_absolute():
-        for base in (repo, wiki, Path.cwd()):
-            if base is None:
-                continue
-            cand = (base / src).resolve()
-            if cand.exists():
-                src = cand
-                break
-        else:
-            src = src.resolve()
-    else:
-        src = src.resolve()
-    if not src.exists():
-        print(f"[error] source not found: {src}", file=sys.stderr)
-        sys.exit(1)
-
-    rel_to_wiki: Path | None = None
-    rel_to_repo: Path | None = None
-    try:
-        rel_to_wiki = src.relative_to(wiki)
-    except ValueError:
-        rel_to_wiki = None
-    if repo is not None:
-        try:
-            rel_to_repo = src.relative_to(repo)
-        except ValueError:
-            rel_to_repo = None
-
-    # The summary page's `source_path` should be relative to the wiki when the
-    # source is staged in raw/, or relative to the repo when it's an in-repo
-    # doc. Lint resolves both forms during drift checks.
-    if rel_to_wiki is not None:
-        recorded_source_path = str(rel_to_wiki).replace("\\", "/")
-    elif rel_to_repo is not None:
-        recorded_source_path = str(rel_to_repo).replace("\\", "/")
-    else:
-        recorded_source_path = str(src)
-
-    is_folder = src.is_dir()
-    folder_addendum = None
-    representative_path = src
-    if is_folder:
-        folder_addendum = folder_brief(src, rel_to_wiki)
-        if "_error" in folder_addendum:
-            print(f"[error] {folder_addendum['_error']}", file=sys.stderr)
-            sys.exit(1)
-        rep_rel = folder_addendum["representative_file"]
-        representative_path = (src / rep_rel) if rep_rel else src
-
-    if is_folder and representative_path == src:
-        text, title = "", None
-    else:
-        text, title = extract(representative_path)
-    title_guess = title or src.stem.replace("-", " ").replace("_", " ").title()
-    slug = slugify(title_guess)
-    today = dt.date.today().isoformat()[:7]  # YYYY-MM
-    vault = wiki
-    suggested_abs = vault / "sources" / f"{today}-{slug}.md"
-    suggested = str(suggested_abs.relative_to(wiki)).replace("\\", "/")
-    existing_path = suggested if suggested_abs.exists() else None
-    source_type = guess_source_type(rel_to_wiki, rel_to_repo)
-    is_in_repo_doc = rel_to_wiki is None and rel_to_repo is not None
-    last_sync_commit = None
-    state_gate = None
-    if repo is not None and is_in_repo_doc:
-        from lattice_wiki_core.scan_monorepo import compute_state_gate
-
-        state_gate = compute_state_gate(repo)
-        # Examples are external; do not promote head_commit into last_sync_commit
-        if source_type != "example":
-            last_sync_commit = state_gate["head_commit"]
-
-    if is_folder:
-        sha_input = representative_path.read_bytes() if representative_path.is_file() else b""
-        bytes_total = folder_addendum["total_size"]
-    else:
-        sha_input = src.read_bytes()
-        bytes_total = src.stat().st_size
-
-    brief = {
-        "source_path": recorded_source_path,
-        "absolute": str(src),
-        "relative": recorded_source_path,
-        "bytes": bytes_total,
-        "sha256": hashlib.sha256(sha_input).hexdigest()[:16],
-        "ext": src.suffix.lower() if src.is_file() else "",
-        "title_guess": title_guess,
-        "source_type_guess": source_type,
-        "word_count": len(text.split()),
-        "preview": text[:PREVIEW_CHARS],
-        "existing_summary_page": existing_path,
-        "suggested_summary_path": suggested,
-        "last_sync_commit": last_sync_commit,
-        "in_repo_doc": is_in_repo_doc,
-        "state_gate": state_gate,
-        "is_folder": is_folder,
-    }
-    if folder_addendum is not None:
-        brief.update(
-            {
-                "file_count": folder_addendum["file_count"],
-                "total_size": folder_addendum["total_size"],
-                "files": folder_addendum["files"],
-                "representative_file": folder_addendum["representative_file"],
-                "warnings": folder_addendum["warnings"],
-            }
-        )
-
-    subpages_created = []
-    if args.pkg_dir:
-        from lattice_wiki_core.layout_io import ensure_subpage
-        pkg_dir_path = Path(args.pkg_dir).expanduser().resolve()
-        pkg_title_str = args.pkg_title or pkg_dir_path.name
-        templates_dir = vault / ".templates"
-        for subpage in ("api", "patterns", "context", "work"):
-            try:
-                _, created = ensure_subpage(pkg_dir_path, subpage, pkg_title_str, templates_dir)
-                if created:
-                    subpages_created.append(subpage)
-            except FileNotFoundError:
-                pass
-    brief["subpages_created"] = subpages_created
-
-    if args.json:
-        print(json.dumps(brief, indent=2, ensure_ascii=False))
-    else:
-        print(f"Source:         {brief['source_path']}")
-        print(f"Title (guess):  {brief['title_guess']}")
-        print(f"Type (guess):   {brief['source_type_guess']}")
-        print(f"Size:           {brief['bytes']} bytes ({brief['word_count']} words)")
-        print(f"SHA256 (short): {brief['sha256']}")
-        if brief["in_repo_doc"]:
-            sha = brief["last_sync_commit"]
-            sha_disp = sha[:8] if sha else "(no git)"
-            print(f"In-repo doc:    yes — record last_sync_commit: {sha_disp}")
-        print(f"Suggested page: {brief['suggested_summary_path']}")
-        if existing_path:
-            print(f"EXISTING PAGE:  {existing_path}  <- re-ingest / merge mode")
-        print()
-        print("--- preview ---")
-        print(brief["preview"])
-        print("--- /preview ---")
-
-
-if __name__ == "__main__":
-    main()
```

