# Phase 5: Remaining Commands — Pattern Map

**Mapped:** 2026-05-14
**Files analyzed:** 17 new/modified files
**Analogs found:** 14 / 17 (3 have no close analog — see No Analog Found section)

---

## File Classification

| New/Modified File | Role | Data Flow | Closest Analog | Match Quality |
|---|---|---|---|---|
| `commands/log.py` | command | request-response (sync) | `commands/query.py` (result dataclass + run_*()) | role-match |
| `commands/init.py` | command | request-response (sync) | `commands/query.py` (result dataclass + run_*()) | role-match |
| `commands/scan.py` | command | batch + LLM fan-out | `commands/query.py` (run_query SubagentPool fan-out) | role-match |
| `commands/ingest.py` | command | request-response + LLM fan-out | `commands/query.py` (run_query SubagentPool fan-out) | role-match |
| `commands/lint.py` | command | batch + LLM fan-out | `commands/query.py` (run_query SubagentPool fan-out) | role-match |
| `code_wiki_agent/config.py` | config | request-response (sync) | none | no analog |
| `cli.py` (modify) | CLI entrypoint | request-response | `cli.py` existing (Typer app, `@app.command()`) | exact |
| `code_wiki_mcp/server.py` (modify) | MCP server | request-response | `server.py` existing (`wiki_query`, `wiki_ping`) | exact |
| `vault_io/ingest_source.py` | utility | file-I/O + transform | `vault_io/append_log.py` (port from lattice-wiki-core) | partial |
| `vault_io/ingest_work_item.py` | utility | file-I/O + CRUD | `vault_io/append_log.py` (port from lattice-wiki-core) | partial |
| `vault_io/lint/container.py` | utility | batch transform | `vault_io/lint/common.py` (shares import namespace) | role-match |
| `vault_io/lint/dependency.py` | utility | batch transform | `vault_io/lint/common.py` (shares import namespace) | role-match |
| `vault_io/lint/domain.py` | utility | batch transform | `vault_io/lint/common.py` (shares import namespace) | role-match |
| `vault_io/lint/file_map.py` | utility | batch transform | `vault_io/lint/common.py` (shares import namespace) | role-match |
| `vault_io/lint/package_sync.py` | utility | batch transform | `vault_io/lint/common.py` (shares import namespace) | role-match |
| `vault_io/lint/source_sync.py` | utility | batch transform | `vault_io/lint/common.py` (shares import namespace) | role-match |
| `vault_io/lint/workflow_hints.py` | utility | batch transform | `vault_io/lint/common.py` (shares import namespace) | role-match |

---

## Pattern Assignments

### `commands/log.py` and `commands/init.py` (command, sync request-response)

**Analog:** `agents/code-wiki-agent/src/code_wiki_agent/commands/query.py`

These are thin wrappers — no LLM, no fan-out. The only new logic is the result dataclass and the `run_*()` async wrapper function.

**Imports pattern** (query.py lines 1-41):
```python
from __future__ import annotations

import logging
from dataclasses import dataclass
from pathlib import Path

from vault_io._workspace import resolve_wiki_and_repo
from vault_io.append_log import append_log  # for log.py
from vault_io.init_vault import init_wiki   # for init.py

logger = logging.getLogger(__name__)
```

**Result dataclass pattern** (query.py lines 151-166):
```python
@dataclass
class LogResult:
    status: str
    log_path: str
    date: str
    op: str
    title: str
    header: str
    detail: str | None

@dataclass
class InitResult:
    status: str
    wiki_path: str
    repo_path: str
    topic: str
    tool: str
    date: str
    installed_files: list[str]
    page_templates_copied: int
    layers: dict
```

**Core run_*() pattern** (query.py lines 459-499, simplified for sync commands):
```python
async def run_log(
    op: str,
    title: str,
    detail: str | None,
    vault_path: Path | None = None,
) -> LogResult:
    wiki, _ = resolve_wiki_and_repo(vault_path)
    result = append_log(wiki, op, title, detail)  # returns dict
    return LogResult(**result)

async def run_init(
    topic: str,
    tool: str,
    force: bool,
    vault_path: Path | None = None,
    non_interactive: bool = True,
) -> InitResult:
    wiki, repo = resolve_wiki_and_repo(vault_path)
    result = init_wiki(wiki, repo, topic, tool, force, non_interactive=non_interactive)
    return InitResult(**result)
```

**Error handling pattern** (query.py lines 490-496):
```python
try:
    result = asyncio.run(run_log(...))
except RuntimeError as e:
    typer.echo(f"Error: {e}", err=True)
    raise typer.Exit(code=1)
```

---

### `commands/scan.py` (command, batch + LLM fan-out)

**Analog:** `agents/code-wiki-agent/src/code_wiki_agent/commands/query.py`

**Imports pattern** (query.py lines 35-41 — adapt for scan role):
```python
from __future__ import annotations

import logging
from dataclasses import dataclass
from pathlib import Path

from langchain_core.messages import HumanMessage, SystemMessage
from model_adapter.loader import load_role_config, make_llm
from subagent_runtime.pool import FanOutResult, SubagentPool
from vault_io._workspace import resolve_wiki_and_repo
from vault_io.scan_monorepo import (
    attach_changed_files,
    build_file_map,
    compute_diff,
    compute_state_gate,
    discover_workspaces,
    pick_representative,
    regenerate_dependencies_index,
)
from vault_io.update_index import update_index
from vault_io.append_log import append_log
from vault_io.layout_io import read_layout

logger = logging.getLogger(__name__)
```

**Result dataclass** (modeled after QueryResult at query.py lines 151-166):
```python
@dataclass
class ScanResult:
    added: list[str]       # package names created
    updated: list[str]     # package names updated
    deleted: list[str]     # package names marked stale
    renamed: list[list[str]]  # [[old, new], ...]
    errors: list[str]      # per-package error messages
    state_gate: dict       # {allowed, reason, head_commit}
```

**SubagentPool fan-out pattern** (query.py lines 540-561 — key pattern):
```python
# From query.py lines 540-561:
pool = SubagentPool(trace_dir=wiki / ".code-wiki" / "traces")
scan_cfg = load_role_config("scanner")

async def generate_stub(pkg: dict) -> str:
    msgs = [
        SystemMessage(content=SCANNER_SYSTEM),
        HumanMessage(content=build_stub_prompt(pkg)),
    ]
    resp = await make_llm("scanner").ainvoke(msgs)
    return resp.content

fan_result: FanOutResult = await pool.run_all(
    items=packages_needing_stubs,
    task=generate_stub,
    role="scanner",
    model_id=scan_cfg["model_id"],
    max_concurrency=scan_cfg["max_concurrency"],
)

# Handle partial failure (query.py lines 563-578):
for item, result in fan_result.successes:
    ...  # write stub page
for err in fan_result.errors:
    logger.warning("Fan-out error for %s: %s", err.item, err.exception)
```

**Stale tag pattern** (D-07 — no existing analog; write to frontmatter):
```python
# When scan detects a deleted package:
page_text = (wiki / f"packages/{pkg_name}/{pkg_name}.md").read_text(encoding="utf-8")
if "stale:" not in page_text:
    page_text = page_text.replace("---\n", "---\nstale: true\n", 1)
    (wiki / f"packages/{pkg_name}/{pkg_name}.md").write_text(page_text, encoding="utf-8")
append_log(wiki, "scan", f"marked stale: {pkg_name}", detail=None)
```

---

### `commands/ingest.py` (command, request-response + single LLM call)

**Analog:** `agents/code-wiki-agent/src/code_wiki_agent/commands/query.py`

**Result dataclass**:
```python
@dataclass
class IngestResult:
    status: str
    page_path: str         # vault-relative path of the written page
    slug: str
    title: str
    page_type: str         # package/concept/adr/source/work
    source_path: str       # source file that was ingested
    cross_refs_updated: int  # number of index/cross-ref pages updated
```

**Ingest source run pattern** (one-item LLM call, not SubagentPool):
```python
async def run_ingest_source(
    source_path: Path,
    vault_path: Path | None = None,
) -> IngestResult:
    wiki, repo = resolve_wiki_and_repo(vault_path)
    # 1. Extract text and metadata
    from vault_io.ingest_source import extract, guess_source_type, slugify
    text, title = extract(source_path)
    title_guess = title or source_path.stem.replace("-", " ").title()
    slug = slugify(title_guess)
    # 2. Determine source type
    try:
        rel_to_wiki = source_path.relative_to(wiki)
    except ValueError:
        rel_to_wiki = None
    try:
        rel_to_repo = source_path.relative_to(repo)
    except ValueError:
        rel_to_repo = None
    source_type = guess_source_type(rel_to_wiki, rel_to_repo)
    # 3. LLM call (single ingestor, no pool needed for one item)
    ingest_cfg = load_role_config("ingestor")
    llm = make_llm("ingestor")
    msgs = [SystemMessage(content=INGESTOR_SYSTEM), HumanMessage(content=build_ingest_prompt(...))]
    resp = await llm.ainvoke(msgs)
    # 4. Write page
    # 5. Update cross-refs
    from vault_io.update_index import update_index
    update_index(wiki)
    from vault_io.append_log import append_log
    append_log(wiki, "ingest", title_guess, detail=f"source: {source_path}")
    return IngestResult(...)
```

**Ingest work-item pattern** (deterministic, no LLM — modeled on ingest_work_item.py):
```python
async def run_ingest_work_item(
    frontmatter_text: str,
    body: str,
    slug: str | None = None,
    force: bool = False,
    vault_path: Path | None = None,
) -> IngestResult:
    wiki, _ = resolve_wiki_and_repo(vault_path)
    # Uses ported vault_io.ingest_work_item functions directly:
    from vault_io.ingest_work_item import _parse_frontmatter, _validate, _emit_yaml, _slugify
    fm = _parse_frontmatter(frontmatter_text)
    issues = _validate(fm)
    if issues:
        raise ValueError("schema validation failed: " + "; ".join(issues))
    computed_slug = slug or _slugify(fm["title"])
    work_root = wiki.parent / "work"
    work_root.mkdir(parents=True, exist_ok=True)
    page_path = work_root / f"{fm['opened']}-{computed_slug}.md"
    content = _emit_yaml(fm) + "\n\n" + body
    page_path.write_text(content, encoding="utf-8")
    # Replace _run_helper() with direct calls:
    from vault_io.update_index import update_index
    update_index(wiki)
    from vault_io.append_log import append_log
    append_log(wiki, "create", fm["title"], detail=f"work/{page_path.name}")
    return IngestResult(...)
```

---

### `commands/lint.py` (command, batch + LLM fan-out — most complex)

**Analog:** `agents/code-wiki-agent/src/code_wiki_agent/commands/query.py`

**Result dataclass** (modeled after the dict returned by `lint_wiki.py:scan()`):
```python
@dataclass
class LintResult:
    wiki: str
    total_pages: int
    orphans: list[str]
    broken_links: list[tuple]
    stale: list[tuple]
    missing_frontmatter: list[str]
    duplicate_titles: dict
    log_gap: dict | None
    code_drift: dict
    container_drift: list
    source_sync_drift: list
    file_map_drift: list
    package_sync_drift: list
    domain_placement: list
    workflow_hints: list
    semantic_findings: dict  # {"page_quality": [...], "adr_chain": [...], "stale_claims": [...]}
    errors: list[str]        # per-group semantic errors
```

**Mechanical pass imports** (all 7 modules — swap prefix from `lint_wiki.py` lines 48-54):
```python
from vault_io.scan_monorepo import discover_workspaces, unscope
from vault_io.layout_io import read_layout
from vault_io.lint.common import (
    LOG_ENTRY_RE,
    WIKILINK_RE,
    _is_placeholder_target,
    parse_frontmatter,
    strip_code,
    strip_frontmatter,
)
from vault_io.lint.container import check as check_container_drift
from vault_io.lint.dependency import check as check_dependency_layer
from vault_io.lint.domain import check as check_domain_placement
from vault_io.lint.file_map import check as check_file_map_drift
from vault_io.lint.package_sync import check as check_package_sync_drift
from vault_io.lint.source_sync import check as check_source_sync_drift
from vault_io.lint.workflow_hints import check as check_workflow_hints
```

**Inline scan() logic** (lint_wiki.py lines 77-331 — MUST port to commands/lint.py):

The page walk, link graph construction, orphan detection, broken link detection, stale detection, missing frontmatter, duplicate title, and log gap checks are all inline in `lint_wiki.py:scan()`. This is the largest porting task. Key structures:

```python
# Page walk + link graph (lint_wiki.py lines 82-112):
pages = {}
link_targets = set()
inbound = defaultdict(set)
outbound = defaultdict(set)

for md in workspace.rglob("*.md"):
    rel = md.relative_to(workspace)
    if any(part.startswith(".") for part in rel.parts):
        continue
    if rel.name in {"log.md"}:
        continue
    top = rel.parts[0] if rel.parts else ""
    if top == "work" and len(rel.parts) >= 2 and rel.parts[1] == "archived":
        continue
    key = str(rel).replace("\\", "/")[:-3]
    link_targets.add(key)
    if rel.name == "index.md":
        continue
    text = md.read_text(encoding="utf-8", errors="replace")
    fm = parse_frontmatter(text)
    pages[key] = {"path": key + ".md", "fm": fm, "text": text, "linted": top in LINTED_TOPS, "is_work": top == "work"}

# Orphan/broken detection (lint_wiki.py lines 113-186):
stems = {Path(k).name: k for k in pages}
for key, page in pages.items():
    scan_text = strip_code(strip_frontmatter(page["text"]))
    for m in WIKILINK_RE.finditer(scan_text):
        target = m.group(1).strip()
        if target.endswith(".md"):
            target = target[:-3]
        if target in link_targets:
            outbound[key].add(target)
            inbound[target].add(key)
        # ... (folder-shorthand and bare-filename resolution) ...
        else:
            if not _is_placeholder_target(target):
                outbound[key].add(f"__BROKEN__:{target}")

# Stale/missing frontmatter (lint_wiki.py lines 188-224):
today = dt.date.today()
stale_cutoff = today - dt.timedelta(days=stale_days)
orphans = sorted(k for k, p in pages.items() if p["linted"] and not p["is_work"] and not inbound.get(k))
broken_links = [(src, t.split(":", 1)[1]) for src, targets in outbound.items() for t in targets if t.startswith("__BROKEN__:")]
```

**Semantic fan-out pattern** (3 linter subagents — analogous to query.py lines 540-561):
```python
pool = SubagentPool(trace_dir=wiki / ".code-wiki" / "traces")
lint_cfg = load_role_config("linter")

semantic_groups = [
    ("page_quality", LINTER_PAGE_QUALITY_SYSTEM, all_pages_sample),
    ("adr_chain", LINTER_ADR_CHAIN_SYSTEM, adr_pages),
    ("stale_claims", LINTER_STALE_CLAIMS_SYSTEM, pages_with_source_path),
]

async def run_linter_group(group: tuple) -> list[str]:
    name, system_prompt, pages_input = group
    msgs = [SystemMessage(content=system_prompt), HumanMessage(content=build_linter_input(pages_input))]
    resp = await make_llm("linter").ainvoke(msgs)
    return [line for line in resp.content.splitlines() if line.strip()]

fan_result: FanOutResult = await pool.run_all(
    items=semantic_groups,
    task=run_linter_group,
    role="linter",
    model_id=lint_cfg["model_id"],
    max_concurrency=lint_cfg["max_concurrency"],
)
```

**Lint defaults** (from lint_wiki.py lines 347-362):
```
--stale-days: 90
--log-gap-days: 14
```

---

### `code_wiki_agent/config.py` (config module, new file)

**No close analog exists.** Use the pattern described in RESEARCH.md:

```python
import tomllib
from dataclasses import dataclass
from pathlib import Path

@dataclass
class WikiConfig:
    models_path: str | None = None
    vault_path: str | None = None
    state_gate_enabled: bool = True

_active_config: WikiConfig = WikiConfig()

def load_config(path: Path) -> WikiConfig:
    with path.open("rb") as f:
        data = tomllib.load(f)
    return WikiConfig(**{k: v for k, v in data.items() if k in WikiConfig.__dataclass_fields__})

def get_config() -> WikiConfig:
    return _active_config
```

---

### `cli.py` (modify — add 5 subcommands + `--config` global callback)

**Analog:** `agents/code-wiki-agent/src/code_wiki_agent/cli.py` (existing file)

**Existing `@app.command()` pattern** (cli.py lines 128-162):
```python
@app.command()
def query(
    query_text: str = typer.Argument(..., help="Natural language query"),
    top_k: int = typer.Option(5, "--top-k", help="Pages to drill (3-10)", min=3, max=10),
    vault: str = typer.Option("", "--vault", help="Vault path (default: env var)"),
    json_output: bool = typer.Option(False, "--json", help="Emit QueryResult as JSON"),
) -> None:
    """Query the wiki using hybrid BM25+embedding search with librarian fan-out."""
    vault_path = Path(vault) if vault else None
    try:
        result = asyncio.run(run_query(query_text, vault_path, top_k=top_k))
    except RuntimeError as e:
        typer.echo(f"Error: {e}", err=True)
        raise typer.Exit(code=1)

    if json_output:
        typer.echo(json.dumps(dataclasses.asdict(result), indent=2))
    else:
        typer.echo(result.answer)
```

**New `@app.callback()` for global `--config`** (D-11 — add before all commands):
```python
from typing import Optional

@app.callback()
def main_callback(
    config: Optional[Path] = typer.Option(None, "--config", help="Path to config TOML file"),
) -> None:
    """code-wiki-agent: AWS Bedrock-powered wiki maintenance."""
    if config is not None:
        import code_wiki_agent.config as _cfg_module
        _cfg_module._active_config = _cfg_module.load_config(config)
```

**New sub-app for `ingest` (D-04)** — two subcommands require a Typer sub-app:
```python
ingest_app = typer.Typer(help="Ingest a source file or work item into the wiki.")
app.add_typer(ingest_app, name="ingest")

@ingest_app.command(name="source")
def ingest_source_cmd(
    path: Path = typer.Argument(..., help="Path to source file"),
    vault: str = typer.Option("", "--vault", help="Vault path"),
    json_output: bool = typer.Option(False, "--json"),
) -> None:
    """Ingest a source file (.md/.txt/.html/.json/.csv) into the wiki."""
    ...

@ingest_app.command(name="work-item")
def ingest_work_item_cmd(
    frontmatter: str = typer.Option(..., "--frontmatter", help="YAML frontmatter string"),
    body: str = typer.Option(..., "--body", help="Markdown body string"),
    slug: Optional[str] = typer.Option(None, "--slug"),
    force: bool = typer.Option(False, "--force"),
    vault: str = typer.Option("", "--vault"),
    json_output: bool = typer.Option(False, "--json"),
) -> None:
    """Ingest a structured work item into <workspace>/work/."""
    ...
```

---

### `code_wiki_mcp/server.py` (modify — add 5 MCP tools)

**Analog:** `agents/code-wiki-agent/src/code_wiki_mcp/server.py` (existing file)

**`_StdoutGuard` import ordering rule** (server.py lines 15-69 — CRITICAL):
All new imports must go AFTER `_StdoutGuard` is installed and AFTER `logging.basicConfig(stream=sys.stderr)`. The block ends at line 81 (`mcp = FastMCP(...)`). New command imports go after line 62.

**`CODE_WIKI_CONFIG` env var read pattern** (new in `main()` — D-13):
```python
def main() -> None:
    import os
    config_path_str = os.environ.get("CODE_WIKI_CONFIG")
    if config_path_str:
        import code_wiki_agent.config as _cfg_module
        _cfg_module._active_config = _cfg_module.load_config(Path(config_path_str))
    mcp.run(transport="stdio")
```

**Sync tool pattern** (server.py lines 84-98 — `wiki_ping` is the sync template):
```python
class WikiLogInput(BaseModel):
    op: str = Field(..., description="Log operation type (scan/ingest/lint/create/update/delete/note)")
    title: str = Field(..., description="Short title for the log entry")
    detail: str | None = Field(None, description="Optional extended detail")
    vault_path: str = Field("", description="Vault path (default: CODE_WIKI_REAL_VAULT_PATH)")

class WikiLogOutput(BaseModel):
    status: str
    log_path: str
    date: str
    op: str
    title: str
    header: str

@mcp.tool(name="wiki_log", description="Append a timestamped event to log.md.")
async def wiki_log(input: WikiLogInput, ctx: Context) -> WikiLogOutput:
    vault = Path(input.vault_path) if input.vault_path else None
    result = await run_log(input.op, input.title, input.detail, vault)
    return WikiLogOutput(
        status=result.status,
        log_path=result.log_path,
        date=result.date,
        op=result.op,
        title=result.title,
        header=result.header,
    )
```

**Async tool with progress pattern** (server.py lines 116-142 — `wiki_query` is the template):
```python
class WikiScanInput(BaseModel):
    vault_path: str = Field("", description="Vault path (default: CODE_WIKI_REAL_VAULT_PATH)")
    no_file_map: bool = Field(False, description="Skip file map generation")
    max_depth: int = Field(3, description="Max directory depth for discovery")

class WikiScanOutput(BaseModel):
    added: list[str]
    updated: list[str]
    deleted: list[str]
    renamed: list[list[str]]
    errors: list[str]
    state_gate: dict

@mcp.tool(
    name="wiki_scan",
    description="Walk repo, diff packages vs vault, create/update stubs via scanner fan-out.",
)
async def wiki_scan(input: WikiScanInput, ctx: Context) -> WikiScanOutput:
    vault = Path(input.vault_path) if input.vault_path else None
    await ctx.report_progress(progress=0, total=3, message="Starting discovery")
    result: ScanResult = await run_scan(vault_path=vault, ...)
    await ctx.report_progress(progress=3, total=3, message=f"Scan complete: {len(result.added)} added")
    return WikiScanOutput(...)
```

---

### `vault_io/ingest_source.py` (new — port from lattice-wiki-core)

**Port source:** `/Users/pat/Personal/lattice/packages/lattice-wiki-core/src/lattice_wiki_core/ingest_source.py`

**Import changes** (complete swap list):
```python
# REMOVE:
from lattice_wiki_core._version_check import check_for_updates
from lattice_wiki_core._workspace import resolve_wiki_and_repo
from lattice_wiki_core.scan_monorepo import compute_state_gate
from lattice_wiki_core.layout_io import ensure_subpage

# REPLACE WITH:
from vault_io._workspace import resolve_wiki_and_repo
from vault_io.scan_monorepo import compute_state_gate
from vault_io.layout_io import ensure_subpage
# (delete check_for_updates — no equivalent in vault_io)
```

**Functions to port verbatim** (lattice-wiki-core ingest_source.py lines 72-223):
- `slugify(text)` — lines 72-75
- `_HTMLTextExtractor` class — lines 78-109
- `extract(path)` — lines 112-142
- `guess_source_type(rel_to_wiki, rel_to_repo)` — lines 145-168
- `language_for(path)` — lines 171-172
- `list_folder_files(root)` — lines 175-182
- `pick_representative(root, entries)` — lines 185-198
- `folder_brief(root, rel_to_wiki)` — lines 201-223

**Constants to keep verbatim**:
```python
PREVIEW_CHARS = 1200
SLUG_RE = re.compile(r"[^a-z0-9]+")
LANGUAGE_BY_EXT = {...}  # lines 46-56
REPRESENTATIVE_INDEX_NAMES = [...]  # lines 58-65
LARGE_FILE_BYTES = 200 * 1024
WARN_FILE_COUNT = 50
ERROR_FILE_COUNT = 200
```

**`main()` is NOT ported** — the command layer (`commands/ingest.py`) replaces the argparse `main()`. The module exposes only library functions.

---

### `vault_io/ingest_work_item.py` (new — port from lattice-wiki-core)

**Port source:** `/Users/pat/Personal/lattice/packages/lattice-wiki-core/src/lattice_wiki_core/ingest_work_item.py`

**Import changes**:
```python
# REMOVE:
from lattice_wiki_core._workspace import resolve_wiki_and_repo
from lattice_wiki_core.layout_io import ensure_subpage
import subprocess  # REMOVE — _run_helper() is replaced

# REPLACE WITH:
from vault_io._workspace import resolve_wiki_and_repo
from vault_io.layout_io import ensure_subpage
from vault_io.update_index import update_index
from vault_io.append_log import append_log
```

**Critical: `_run_helper()` replacement** (ingest_work_item.py lines 123-130):
```python
# ORIGINAL (remove this):
def _run_helper(name: str, *args: str) -> None:
    subprocess.run([sys.executable, str(SCRIPTS_DIR / name), *args], check=True, capture_output=True)

# After writing the page (lines 180-196), replace:
#   _run_helper("update_index.py")
#   _run_helper("append_log.py", "--op", "create", "--title", title, "--detail", f"work/{page_path.name}")
# With direct calls:
update_index(wiki)
append_log(wiki, "create", title, detail=f"work/{page_path.name}")
```

**Functions to port** (with import swap only):
- `_err(msg, code, as_json)` — lines 50-55
- `_slugify(title)` — lines 58-60
- `_parse_frontmatter(yaml_text)` — lines 63-96
- `_validate(fm)` — lines 99-106
- `_emit_yaml(fm)` — lines 109-120
- `file_work_item(wiki, fm, body, slug, force, pkg_dir, pkg_title)` — extracted from `main()` lines 132-213 and refactored as a library function

**`main()` is NOT ported** — command layer takes over. Expose library functions only.

---

### `vault_io/lint/container.py` through `workflow_hints.py` (7 modules — port with import swap)

**Analog:** `vault_io/lint/common.py` (same package, same namespace)

**Port sources** (all in `/Users/pat/Personal/lattice/packages/lattice-wiki-core/src/lattice_wiki_core/lint/`):

| New File | Port Source | Import Changes |
|---|---|---|
| `vault_io/lint/container.py` | `lattice_wiki_core/lint/container.py` | `from lattice_wiki_core.layout_io` → `from vault_io.layout_io` |
| `vault_io/lint/dependency.py` | `lattice_wiki_core/lint/dependency.py` | `from lattice_wiki_core.lint.common` → `from vault_io.lint.common` |
| `vault_io/lint/domain.py` | `lattice_wiki_core/lint/domain.py` | No vault_io imports; pure logic — port verbatim |
| `vault_io/lint/file_map.py` | `lattice_wiki_core/lint/file_map.py` | `from lattice_wiki_core.scan_monorepo` → `from vault_io.scan_monorepo`; `from lattice_wiki_core.lint.common` → `from vault_io.lint.common` |
| `vault_io/lint/package_sync.py` | `lattice_wiki_core/lint/package_sync.py` | `from lattice_wiki_core.git_state` → `from vault_io.git_state`; `from lattice_wiki_core.lint.common` → `from vault_io.lint.common` |
| `vault_io/lint/source_sync.py` | `lattice_wiki_core/lint/source_sync.py` | Same as package_sync.py swaps |
| `vault_io/lint/workflow_hints.py` | `lattice_wiki_core/lint/workflow_hints.py` | `from lattice_wiki_core.lint.common` → `from vault_io.lint.common` |

**Module structure pattern** (container.py — the simplest; use as template):
```python
"""Container drift: pinned vault dirs vs. disk; orphan vault dirs."""
from __future__ import annotations
from pathlib import Path
from vault_io.layout_io import read_layout  # swapped import

GROUP = "container"  # module-level constant

def check(repo: Path, wiki: Path) -> list[str]:
    """Return a list of human-readable issue strings about layout/disk drift."""
    issues: list[str] = []
    ...
    return issues
```

**Special case — `file_map.py` uses private function** (Risk 6 from RESEARCH.md):
```python
# This import is acceptable — both modules are in vault_io:
from vault_io.scan_monorepo import _git_ls_files  # private, but same package
```

---

## Shared Patterns

### Authentication / Vault Resolution
**Source:** `agents/code-wiki-agent/src/code_wiki_agent/commands/query.py` lines 498-499
**Apply to:** All command files (`run_log`, `run_init`, `run_scan`, `run_ingest_source`, `run_ingest_work_item`, `run_lint`)
```python
wiki, repo = resolve_wiki_and_repo(vault_path)
# vault_path=None causes resolve_wiki_and_repo to read CODE_WIKI_REAL_VAULT_PATH env var
```

### Logging Setup
**Source:** `agents/code-wiki-agent/src/code_wiki_agent/commands/query.py` lines 42
**Apply to:** All new command files
```python
logger = logging.getLogger(__name__)
```

### JSON Output / Human-readable Output Toggle
**Source:** `agents/code-wiki-agent/src/code_wiki_agent/cli.py` lines 148-162
**Apply to:** All new CLI subcommands
```python
if json_output:
    typer.echo(json.dumps(dataclasses.asdict(result), indent=2))
else:
    typer.echo(result.answer)  # or command-specific human-readable render
    if not quiet:
        typer.echo(f"Meta info: ...", err=not sys.stdout.isatty())
```

### Error Handling (CLI layer)
**Source:** `agents/code-wiki-agent/src/code_wiki_agent/cli.py` lines 141-144
**Apply to:** All new CLI `@app.command()` functions
```python
try:
    result = asyncio.run(run_<command>(...))
except (RuntimeError, FileNotFoundError, ValueError) as e:
    typer.echo(f"Error: {e}", err=True)
    raise typer.Exit(code=1)
```

### Error Handling (MCP layer)
**Source:** `agents/code-wiki-agent/src/code_wiki_mcp/server.py` — FastMCP re-raises
**Apply to:** All new MCP tool functions
```python
# No explicit try/except needed in MCP tool — FastMCP converts uncaught exceptions
# to structured MCP error responses. BUT: log before re-raising:
try:
    result = await run_<command>(...)
except Exception as exc:
    logger.error("wiki_<tool> failed: %s", exc)
    raise
```

### Progress Notifications (MCP long-running tools)
**Source:** `agents/code-wiki-agent/src/code_wiki_mcp/server.py` lines 126-136
**Apply to:** `wiki_scan`, `wiki_lint`, `wiki_ingest`
```python
await ctx.report_progress(progress=0, total=3, message="Starting <phase>")
# ... after deterministic phase ...
await ctx.report_progress(progress=1, total=3, message=f"Discovery complete: {N} items")
# ... after LLM fan-out ...
await ctx.report_progress(progress=2, total=3, message=f"Fan-out complete: {N} processed")
# Final completion progress is not required (FastMCP sends it on return)
```

### Partial Failure Exit Code
**Source:** `agents/code-wiki-agent/src/code_wiki_agent/cli.py` lines 161-162
**Apply to:** `scan` and `lint` CLI commands when `fan_result.errors` is non-empty
```python
if result.errors:
    raise typer.Exit(code=3)
```

### Integration Test Gate
**Source:** `agents/code-wiki-agent/tests/conftest.py` lines 19-22
**Apply to:** All new integration tests (those that call Bedrock)
```python
INTEGRATION_GATE = pytest.mark.skipif(
    not os.environ.get("CODE_WIKI_RUN_INTEGRATION"),
    reason="Set CODE_WIKI_RUN_INTEGRATION=1 to run real Bedrock invocations",
)

@INTEGRATION_GATE
async def test_run_scan_integration(tmp_vault_path: Path) -> None:
    ...
```

### MCP Schema Test Pattern
**Source:** `agents/code-wiki-agent/tests/unit/test_mcp_query_schema.py` lines 14-59
**Apply to:** `tests/unit/test_mcp_new_tools.py`
```python
def test_wiki_log_tool_registered() -> None:
    from code_wiki_mcp.server import wiki_log
    assert callable(wiki_log)
    assert wiki_log.__name__ == "wiki_log"

def test_wiki_log_input_rejects_missing_required_fields() -> None:
    from code_wiki_mcp.server import WikiLogInput
    with pytest.raises(ValidationError):
        WikiLogInput()  # missing op and title

async def test_wiki_log_calls_run_log() -> None:
    from code_wiki_mcp.server import WikiLogInput, wiki_log
    mock_ctx = MagicMock()
    mock_ctx.report_progress = AsyncMock()
    with patch("code_wiki_mcp.server.run_log", new_callable=AsyncMock) as mock_fn:
        mock_fn.return_value = LogResult(...)
        result = await wiki_log(WikiLogInput(op="note", title="test"), mock_ctx)
    assert result.status == "ok"
```

### CLI Test Pattern (CliRunner + monkeypatch)
**Source:** `agents/code-wiki-agent/tests/unit/test_cli_query.py` lines 130-165
**Apply to:** All new CLI command tests
```python
def test_log_json_output(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    from typer.testing import CliRunner
    from code_wiki_agent.cli import app

    monkeypatch.setattr(
        "code_wiki_agent.cli.run_log",
        AsyncMock(return_value=LogResult(...)),
    )
    runner = CliRunner()
    result = runner.invoke(app, ["log", "--op", "note", "--title", "test", "--json"])
    assert result.exit_code == 0
    parsed = json.loads(result.output)
    assert parsed["status"] == "ok"
```

---

## No Analog Found

Files with no close match in the codebase (planner should use RESEARCH.md patterns instead):

| File | Role | Data Flow | Reason |
|---|---|---|---|
| `code_wiki_agent/config.py` | config | request-response | No config module exists yet; use RESEARCH.md `WikiConfig` dataclass pattern |
| `vault_io/ingest_source.py` (port) | utility | file-I/O + transform | Pure port from lattice-wiki-core; the lattice source IS the analog |
| `vault_io/ingest_work_item.py` (port) | utility | file-I/O + CRUD | Pure port from lattice-wiki-core; the lattice source IS the analog; key change is replacing `_run_helper()` subprocess calls with direct imports |

---

## Key Risks Surfaced During Analysis

1. **`lint_wiki.py:scan()` inline logic (lines 77-331) is ~250 lines** that must be ported into `commands/lint.py` directly, not into any of the 7 lint modules. The 7 modules are supplementary checks only. This is the largest single file-porting task.

2. **`_run_helper()` in `ingest_work_item.py`** calls `update_index.py` and `append_log.py` as subprocesses. Replace with: `update_index(wiki)` and `append_log(wiki, "create", title, detail)` direct function calls.

3. **Scanner role `max_tokens = 500`** — stub generation must produce only the stub BODY (not the file map section). The `## File map` section is appended from deterministic `build_file_map()` output after the LLM call.

4. **`_StdoutGuard` ordering in server.py** — all new imports in `server.py` must come after the guard (line 51) and after `logging.basicConfig` (line 65). Never add imports between lines 15-64.

5. **`ingest_work_item.py` writes to `wiki.parent / "work"`** — not inside `wiki/`. The `run_ingest_work_item()` function must derive `workspace_path = vault_path.parent`.

---

## Metadata

**Analog search scope:** `agents/code-wiki-agent/src/`, `cores/vault-io/src/`, `cores/subagent-runtime/src/`, lattice-wiki-core reference implementation
**Files scanned:** 14 source files read in full
**Pattern extraction date:** 2026-05-14
