# Claude-path skill ingest → guidance pages Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Teach the Claude plugin's `ingest_source.py` shim to recognize a skill directory and emit a skill-aware brief, so the `ingestor` agent chunks the skill into `wiki/guidance/<topic>/<slug>.md` pages — reaching parity with the existing Bedrock path, in the Claude path's "Python preps, agent reasons" idiom.

**Architecture:** A new pure, Bedrock-free `build_skill_ingest_brief` in `wiki_io/ingest_source.py` reuses the already-built `gather_skill_sources` (gathers `SKILL.md` + transitively-linked companion markdown), `_build_entity_match` (graph entity hint), and `compute_state_gate`. The plugin shim routes a resolved skill anchor to this builder *before* its `is_dir()` check. The chunking intelligence lives in the agent, guided by a new section in `references/ingest-workflow.md` — **no LLM-call machinery is added to the plugin path.**

**Tech Stack:** Python 3.11, `uv` workspace, pytest. Packages: `wiki-io` (builder + tests), `plugins/graph-wiki` (shim + reference doc + command/agent markdown).

---

## Background the implementer needs

Read these before starting — they are the load-bearing facts this plan depends on:

- **The shim is thin.** `plugins/graph-wiki/skills/graph-wiki/scripts/ingest_source.py` has a Bedrock branch (`gw wiki ingest source`, untouched here) and a Claude branch that builds a JSON *brief* from `wiki_io.ingest_source` helpers. The agent reads the brief, then **Reads the source files itself** before writing pages. We add a third brief builder and route to it.
- **`gather_skill_sources(anchor)` already exists** (`wiki_io/ingest_source.py`) and returns a `SkillBundle` with: `title` (frontmatter `name:` → first `# ` heading → `None`), `skill_dir`, `included_files` (skill_dir-relative POSIX, `SKILL.md` first, DFS link order), `excluded_files` (every non-`.md` under the dir, sorted), `scripts_dominant` (True when a top-level `scripts/` dir exists OR excluded > included).
- **`resolve_skill_anchor(path)` already exists**: a directory containing `SKILL.md` → `<dir>/SKILL.md`; a file named `SKILL.md` → itself; anything else → `None`.
- **The Bedrock path is the parity target.** `graph_wiki_core/commands/ingest.py` detects a skill and runs `skill_planner` → `skill_synthesizer` (real `make_llm` calls) writing guidance pages. The agent-facing reference section is a faithful *port of those two system prompts' rules* (`prompts/skill_planner.py`, `prompts/skill_synthesizer.py`) so both paths agree on what guidance pages look like. We do **not** port the planner/synthesizer code into the plugin path.
- **Guidance frontmatter schema** is enforced by `guidance_io.frontmatter.validate`: required keys `title`, `category` (must be literal `guidance`), `summary`, `topic`, `applies_when`, `impact` (one of `critical|high|medium|low`), `updated`, `tokens`; optional `triggers` mapping with list-valued `globs`/`keywords`/`entities`.
- **Test helpers** live in `packages/wiki-io/tests/conftest.py` (the spec's reference to `helpers.py` is stale): `tmp_repo` and `vault_path` are fixtures, `write_file` is a module-level helper. The existing brief tests in `test_ingest_source_prep.py` just use `tmp_path` + inline `.write_text` — mirror that style.
- **No DB needed in builder tests.** `_build_entity_match` opens a read-only graph conn and returns `{"uri": None, "entity_filename": None}` when the DB is missing (`read_only_connect` raises `GraphNotInitializedError` on a missing file). So tests that don't seed a `code.db` get a null entity match for free.
- **Known gap (out of scope, do not fix here):** guidance `## Applies to` `[[entities/...]]` links do not yet produce entity backlinks (`guidance` is absent from `backlink_index._PRESERVED_WIKI_DIRS`). The agent still writes the links; the wiring is a separate change.

## File Structure

- **Modify** `packages/wiki-io/src/wiki_io/ingest_source.py` — add `build_skill_ingest_brief` (after `gather_skill_sources`) and its name to the module-docstring export list.
- **Create** `packages/wiki-io/tests/test_skill_ingest_brief.py` — unit tests for the new builder.
- **Modify** `packages/wiki-io/tests/test_ingest_source_prep.py` — one assertion that the new builder is exported (Bedrock-free contract).
- **Modify** `plugins/graph-wiki/skills/graph-wiki/scripts/ingest_source.py` — skill routing (anchor check before `is_dir()`) + human-readable skill output.
- **Modify** `plugins/graph-wiki/skills/graph-wiki/references/ingest-workflow.md` — new "Skill → guidance pages" section.
- **Modify** `plugins/graph-wiki/agents/ingestor.md` — skill-branch note.
- **Modify** `plugins/graph-wiki/commands/ingest.md` — skill row in source-types table + one line in "What happens".

---

### Task 1: `build_skill_ingest_brief` (the skill-aware brief builder)

**Files:**
- Modify: `packages/wiki-io/src/wiki_io/ingest_source.py` (append after `gather_skill_sources`, ~line 503; update docstring exports ~line 9-24)
- Test: `packages/wiki-io/tests/test_skill_ingest_brief.py` (create)

- [ ] **Step 1: Write the failing test**

Create `packages/wiki-io/tests/test_skill_ingest_brief.py`:

```python
"""Unit tests for build_skill_ingest_brief — the skill-aware Claude-branch brief.

Pure / Bedrock-free: assembles a manifest from gather_skill_sources without any
model_adapter / subagent_runtime import. The agent reads `included_files` itself
before chunking the skill into wiki/guidance/<topic>/<slug>.md pages.
"""

from __future__ import annotations

from pathlib import Path

from wiki_io.ingest_source import build_skill_ingest_brief, resolve_skill_anchor


def _make_skill(root: Path) -> Path:
    """Minimal skill: SKILL.md linking one companion .md, plus a non-md script.

    Returns the skill directory. `scripts/` makes the bundle scripts_dominant.
    """
    skill = root / "my-skill"
    skill.mkdir(parents=True)
    (skill / "SKILL.md").write_text(
        "---\nname: My Skill\n---\n\n# My Skill\n\nSee [advanced](references/advanced.md).\n",
        encoding="utf-8",
    )
    (skill / "references").mkdir()
    (skill / "references" / "advanced.md").write_text("# Advanced\n\nMore.\n", encoding="utf-8")
    (skill / "scripts").mkdir()
    (skill / "scripts" / "helper.py").write_text("print('x')\n", encoding="utf-8")
    return skill


def _wiki(root: Path) -> Path:
    wiki = root / "wiki"
    wiki.mkdir()
    return wiki


def test_skill_directory_emits_skill_brief(tmp_path: Path) -> None:
    skill = _make_skill(tmp_path)
    wiki = _wiki(tmp_path)

    brief = build_skill_ingest_brief(
        anchor=resolve_skill_anchor(skill),
        wiki=wiki,
        repo=tmp_path,
        workspace_root=tmp_path,
    )

    assert brief["is_skill"] is True
    assert brief["source_type"] == "skill"
    assert brief["title"] == "My Skill"
    assert brief["slug"] == "my-skill"
    assert brief["guidance_dir"] == "guidance/"
    assert brief["suggested_summary_path"].startswith("sources/")
    assert brief["suggested_summary_path"].endswith("-my-skill.md")
    assert brief["included_files"] == ["SKILL.md", "references/advanced.md"]
    assert "scripts/helper.py" in brief["excluded_files"]
    assert brief["merge_mode"] is False
    assert "state_gate" in brief
    assert brief["entity_match"] == {"uri": None, "entity_filename": None}
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `uv run --package wiki-io pytest packages/wiki-io/tests/test_skill_ingest_brief.py::test_skill_directory_emits_skill_brief -v`
Expected: FAIL with `ImportError: cannot import name 'build_skill_ingest_brief'`.

- [ ] **Step 3: Implement `build_skill_ingest_brief`**

In `packages/wiki-io/src/wiki_io/ingest_source.py`, append at the end of the file (after `gather_skill_sources`):

```python
def build_skill_ingest_brief(anchor: Path, wiki: Path, repo: Path, workspace_root: Path) -> dict:
    """Build a skill-aware ingest brief for the plugin's Claude branch.

    Pure / Bedrock-free, consistent with build_ingest_brief / build_folder_ingest_brief.
    Reuses gather_skill_sources (gather SKILL.md + transitively-linked companion
    markdown), _build_entity_match (graph entity hint), and compute_state_gate.

    The agent Reads the returned `included_files` itself before chunking the skill
    into wiki/guidance/<topic>/<slug>.md pages — Python only emits the manifest.
    `warnings` carries "scripts_dominant" when the skill is mostly non-markdown
    scripts (a weak guidance candidate the agent surfaces).
    """
    bundle = gather_skill_sources(anchor)
    title_guess = bundle.title or bundle.skill_dir.stem.replace("-", " ").title()
    slug = slugify(title_guess)

    month = datetime.date.today().strftime("%Y-%m")
    suggested = f"sources/{month}-{slug}.md"
    merge_mode = (wiki / suggested).exists()

    warnings: list[str] = []
    if bundle.scripts_dominant:
        warnings.append("scripts_dominant")

    return {
        "is_skill": True,
        "source_path": str(bundle.skill_dir),
        "title": title_guess,
        "source_type": "skill",
        "slug": slug,
        "suggested_summary_path": suggested,
        "merge_mode": merge_mode,
        "guidance_dir": "guidance/",
        "included_files": bundle.included_files,
        "excluded_files": bundle.excluded_files,
        "scripts_dominant": bundle.scripts_dominant,
        "warnings": warnings,
        "entity_match": _build_entity_match(workspace_root, repo, bundle.skill_dir, title_guess),
        "state_gate": compute_state_gate(repo, workspace=workspace_root),
    }
```

Then update the module docstring export list (near line 21, after the `gather_skill_sources` line) by adding:

```python
    build_skill_ingest_brief(anchor, wiki, repo, workspace_root) -> dict
```

- [ ] **Step 4: Run the test to verify it passes**

Run: `uv run --package wiki-io pytest packages/wiki-io/tests/test_skill_ingest_brief.py::test_skill_directory_emits_skill_brief -v`
Expected: PASS.

- [ ] **Step 5: Add the remaining behavior tests**

Append to `packages/wiki-io/tests/test_skill_ingest_brief.py`:

```python
def test_bare_skill_md_file_resolves_same_brief(tmp_path: Path) -> None:
    skill = _make_skill(tmp_path)
    wiki = _wiki(tmp_path)
    anchor = resolve_skill_anchor(skill / "SKILL.md")
    assert anchor is not None

    brief = build_skill_ingest_brief(anchor=anchor, wiki=wiki, repo=tmp_path, workspace_root=tmp_path)

    assert brief["is_skill"] is True
    assert brief["included_files"] == ["SKILL.md", "references/advanced.md"]
    assert brief["source_path"] == str(skill.resolve())


def test_scripts_dominant_sets_warning(tmp_path: Path) -> None:
    # A skill with a top-level scripts/ dir is scripts_dominant by definition.
    skill = _make_skill(tmp_path)
    wiki = _wiki(tmp_path)

    brief = build_skill_ingest_brief(
        anchor=resolve_skill_anchor(skill), wiki=wiki, repo=tmp_path, workspace_root=tmp_path
    )

    assert brief["scripts_dominant"] is True
    assert "scripts_dominant" in brief["warnings"]


def test_excluded_files_capture_non_markdown_only(tmp_path: Path) -> None:
    skill = _make_skill(tmp_path)
    wiki = _wiki(tmp_path)

    brief = build_skill_ingest_brief(
        anchor=resolve_skill_anchor(skill), wiki=wiki, repo=tmp_path, workspace_root=tmp_path
    )

    # Every non-.md file under the skill dir is excluded; no .md leaks in.
    assert brief["excluded_files"] == ["scripts/helper.py"]
    assert all(not p.endswith(".md") for p in brief["excluded_files"])


def test_non_skill_path_resolves_to_none(tmp_path: Path) -> None:
    # A plain folder with no SKILL.md is not a skill; the builder is never invoked.
    folder = tmp_path / "raw" / "examples" / "demo"
    folder.mkdir(parents=True)
    (folder / "a.md").write_text("# A\n", encoding="utf-8")

    assert resolve_skill_anchor(folder) is None
    # A loose file is likewise not a skill anchor.
    assert resolve_skill_anchor(folder / "a.md") is None
```

- [ ] **Step 6: Run the full test file to verify all pass**

Run: `uv run --package wiki-io pytest packages/wiki-io/tests/test_skill_ingest_brief.py -v`
Expected: 5 passed.

- [ ] **Step 7: Commit**

```bash
git add packages/wiki-io/src/wiki_io/ingest_source.py packages/wiki-io/tests/test_skill_ingest_brief.py
git commit -m "feat(ingest): build_skill_ingest_brief for the Claude path"
```

---

### Task 2: Assert the builder is exported Bedrock-free

**Files:**
- Modify: `packages/wiki-io/tests/test_ingest_source_prep.py:79-81`

- [ ] **Step 1: Extend the existing export test**

In `test_prep_module_exports_brief_builders`, after the `build_folder_ingest_brief` assertion (line 80), add:

```python
    assert callable(prep.build_skill_ingest_brief)
```

The test already monkeypatches `model_adapter` / `subagent_runtime` to `None` and reloads the module, so this asserts the new builder imports without the Bedrock stack.

- [ ] **Step 2: Run the test to verify it passes**

Run: `uv run --package wiki-io pytest packages/wiki-io/tests/test_ingest_source_prep.py::test_prep_module_exports_brief_builders -v`
Expected: PASS.

- [ ] **Step 3: Commit**

```bash
git add packages/wiki-io/tests/test_ingest_source_prep.py
git commit -m "test(ingest): assert build_skill_ingest_brief is exported Bedrock-free"
```

---

### Task 3: Shim routing — anchor check before `is_dir()`

**Files:**
- Modify: `plugins/graph-wiki/skills/graph-wiki/scripts/ingest_source.py:42` (imports), `:63-74` (routing), `:76-95` (human-readable output)

This is a thin script invoked via subprocess; the spec verifies it manually (no automated test). Make the edits precisely, then run the manual check in Step 4.

- [ ] **Step 1: Add the new imports**

Replace the import line (`ingest_source.py:42`):

```python
    from wiki_io.ingest_source import build_folder_ingest_brief, build_ingest_brief
```

with:

```python
    from wiki_io.ingest_source import (
        build_folder_ingest_brief,
        build_ingest_brief,
        build_skill_ingest_brief,
        resolve_skill_anchor,
    )
```

- [ ] **Step 2: Replace the routing block**

Replace the routing block (`ingest_source.py:63-74`):

```python
    if _source_for_branch(source_path, repo).is_dir():
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
```

with (skill detection must come **before** the `is_dir()` check — a skill is a directory):

```python
    resolved = _source_for_branch(source_path, repo)
    anchor = resolve_skill_anchor(resolved)
    if anchor is not None:
        brief = build_skill_ingest_brief(
            anchor=anchor,
            wiki=wiki,
            repo=repo,
            workspace_root=workspace_root,
        )
    elif resolved.is_dir():
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
```

- [ ] **Step 3: Add the human-readable skill branch**

In the non-`--json` output section, immediately after the `if args.json_output:` block (after `ingest_source.py:78`, before the `if brief.get("is_folder"):` block at line 80), insert:

```python
    if brief.get("is_skill"):
        print(f"Title: {brief['title']}")
        print(f"Source type: {brief['source_type']}")
        print(f"{len(brief['included_files'])} included / {len(brief['excluded_files'])} excluded files")
        if brief.get("scripts_dominant"):
            print("Warning: scripts_dominant — mostly non-markdown scripts; weak guidance candidate")
        print(f"Suggested summary: {brief['suggested_summary_path']}")
        print(f"Target guidance dir: {brief['guidance_dir']}")
        entity_match = brief["entity_match"]
        if entity_match["uri"]:
            print(f"Entity match: {entity_match['uri']} -> [[entities/{entity_match['entity_filename']}]]")
        return
```

- [ ] **Step 4: Manually verify the shim emits a skill brief**

Point the shim at a real skill directory (the graph-wiki maintainer skill itself works). Run from repo root:

```bash
uv run --project "$PWD" python plugins/graph-wiki/skills/graph-wiki/scripts/ingest_source.py \
  --source plugins/graph-wiki/skills/graph-wiki --json
```

Expected: JSON with `"is_skill": true`, `"source_type": "skill"`, an `"included_files"` array starting with `"SKILL.md"`, an `"excluded_files"` array containing the `scripts/*.py` shims, and a `"suggested_summary_path"` under `sources/`.

Then verify the human-readable form:

```bash
uv run --project "$PWD" python plugins/graph-wiki/skills/graph-wiki/scripts/ingest_source.py \
  --source plugins/graph-wiki/skills/graph-wiki
```

Expected: prints `Title:`, `Source type: skill`, `N included / M excluded files`, the `scripts_dominant` warning, the suggested summary path, and `Target guidance dir: guidance/`.

- [ ] **Step 5: Commit**

```bash
git add plugins/graph-wiki/skills/graph-wiki/scripts/ingest_source.py
git commit -m "feat(ingest): route skill dirs to the skill brief in the plugin shim"
```

---

### Task 4: Reference doc — "Skill → guidance pages" section

**Files:**
- Modify: `plugins/graph-wiki/skills/graph-wiki/references/ingest-workflow.md` (add a new section after the "Source-type-specific notes" section, before "## Future formats" at line 154)

This is the agent-facing chunking spec — a faithful port of the Bedrock `skill_planner` / `skill_synthesizer` rules. No code; the content below is the deliverable verbatim.

- [ ] **Step 1: Insert the new section**

Insert the following block immediately before the `## Future formats` heading in `ingest-workflow.md`:

```markdown
## Skill → guidance pages

When the brief carries `is_skill: true`, this source is an agent **skill** (behavioral
guidance for an AI coding agent). Route it to this flow instead of the single
source-summary flow above: a skill is broken into one or more **guidance pages** under
`wiki/guidance/<topic>/<slug>.md`, plus one source page that links to them.

### Detection

The brief from `ingest_source.py --json` carries `is_skill: true`, `source_type: skill`,
`included_files` (skill-dir-relative markdown — `SKILL.md` first, then transitively-linked
companions in link order), `excluded_files` (non-markdown files under the skill dir),
`scripts_dominant`, and a `warnings` list. **Read the `included_files` yourself** (Read
tool, skill-dir-relative) before chunking — the brief is a manifest, not the content.

If `scripts_dominant` is true (or `warnings` contains `"scripts_dominant"`), the skill is
mostly non-markdown scripts — a weak guidance candidate. Surface this to the user and ask
whether to proceed before writing pages.

### Chunking rules

Choose the chunking from the content (mirrors the Bedrock skill planner):

- **Rules / atomic directives** — a skill that is a list of independent "do X" / "never Y"
  rules: write ONE guidance page per rule.
- **How-to / instructional flow** — a single coherent procedure or technique: write ONE
  guidance page for the whole skill.
- **Never split tightly-coupled steps** across pages. When in doubt, prefer fewer, larger
  pages over many fragments.
- Extract reusable TECHNICAL knowledge; drop skill-harness scaffolding (activation phrases,
  tool-call mechanics, meta-instructions about being a skill).
- Preserve content verbatim where practical — the goal is smaller, targetable chunks, not
  rewrites.
- Infer `topic` from the skill's DOMAIN, not its filename (a React Native skill →
  `react-native`; a brainstorming skill → `brainstorming`). `topic` is a short kebab-case
  slug and becomes the folder under `wiki/guidance/`.

### Guidance page frontmatter (inline schema — no template file needed)

Each guidance page begins with this frontmatter block, then the body. Emit exactly these
keys:

```yaml
---
title: <human-readable page title>
category: guidance          # FIXED — always this literal value
summary: <one-line summary for the wiki spine>
topic: <kebab-case domain slug — the folder under guidance/>
applies_when: <when this guidance applies, one line>
triggers:                   # all sub-keys optional; emit empty lists when no signal
  globs: []
  keywords: []
  entities: []              # [[entities/...]] targets, or []
tags: []                    # optional coarse tags
impact: high                # critical | high | medium | low (lowercase)
source: "[[sources/<YYYY-MM>-<slug>]]"   # the skill's source page (see below)
updated: <today, YYYY-MM-DD>
tokens: 0
---
```

`category` MUST be the literal `guidance`. `impact` MUST be lowercase and one of
critical/high/medium/low. Use the `suggested_summary_path` from the brief (minus the
`sources/` prefix and `.md` suffix) as the `source:` target.

Body sections:

1. `# <title>`
2. `## Guidance` — the prescriptive content: how to do it correctly and why. No padding, no
   restating the title.
3. `## Incorrect` / `## Correct` — optional code examples, only when they sharpen the point.
4. `## Applies to` — ONLY when `triggers.entities` is non-empty: one `- [[entities/...]]`
   bullet per entity. Omit the section entirely when there are no entities.

### Targets

Write each page to `<workspace>/wiki/guidance/<topic>/<slug>.md`. `<topic>` is the
kebab-case domain folder; `<slug>` is a kebab-case stem derived from the page title. Create
the topic folder if it doesn't exist. On re-ingest, overwrite the page in place.

### Source page

Write one source page at the brief's `suggested_summary_path`
(`<workspace>/wiki/sources/<YYYY-MM>-<slug>.md`) with `source_type: skill`:

- `## Summary` — one or two sentences: the skill was ingested into N guidance page(s).
- `## Generates` — a bullet list of `[[guidance/<topic>/<slug>]]` wikilinks, one per
  guidance page written.
- `## Excluded` — only when the brief's `excluded_files` is non-empty: a bullet list of the
  non-markdown files (as `` `path` ``) that were not ingested.

This matches the Bedrock source-page shape (`## Summary`, `## Generates`, `## Excluded`).

### Known gap

`## Applies to` `[[entities/...]]` links do **not** yet produce entity backlinks (`guidance`
is absent from the scanner's preserved-wiki-dirs list). Still write the links — the backlink
wiring is a separate, out-of-scope change.
```

- [ ] **Step 2: Verify the section renders and links resolve**

Run: `grep -n "Skill → guidance pages" plugins/graph-wiki/skills/graph-wiki/references/ingest-workflow.md`
Expected: one match, positioned before the `## Future formats` line.

- [ ] **Step 3: Commit**

```bash
git add plugins/graph-wiki/skills/graph-wiki/references/ingest-workflow.md
git commit -m "docs(ingest): skill → guidance-pages section in ingest-workflow"
```

---

### Task 5: Command + agent markdown touch-ups

**Files:**
- Modify: `plugins/graph-wiki/agents/ingestor.md` (add a skill note in the Workflow section)
- Modify: `plugins/graph-wiki/commands/ingest.md:36` (source-types table) and `:38-50` ("What happens")

- [ ] **Step 1: Add the skill branch note to `ingestor.md`**

In `plugins/graph-wiki/agents/ingestor.md`, insert a new subsection in the Workflow block immediately after the `### 4. Write the source summary` block (before `### 5. Link the code entities`):

```markdown
### 4a. Skill sources → guidance pages

If the brief reports `is_skill: true` (the source is an agent skill), do NOT write a single
source summary. Instead break the skill into one or more guidance pages under
`<workspace>/wiki/guidance/<topic>/<slug>.md`, then write a `source_type: skill` source page
that links to them under `## Generates`. Read `included_files` from the brief and follow the
"Skill → guidance pages" section of `references/ingest-workflow.md` for chunking rules, the
guidance frontmatter schema, and the source-page shape. If `scripts_dominant` is true, warn
the user first — a scripts-heavy skill is a weak guidance candidate.
```

- [ ] **Step 2: Add a skill row to the source-types table in `ingest.md`**

In `plugins/graph-wiki/commands/ingest.md`, add a row to the source-types table (after the `raw/examples/` row at line 36):

```markdown
| skill dir (`SKILL.md`) | `skill` | Guidance pages under `guidance/<topic>/`; a `## Generates` source page |
```

- [ ] **Step 3: Add a one-line mention in "What happens"**

In the same file, in the "## What happens" numbered list, append to step 5 ("Write") a parenthetical, changing:

```markdown
5. **Write** — creates the source summary at `<workspace>/wiki/sources/<YYYY-MM>-<slug>.md`
```

to:

```markdown
5. **Write** — creates the source summary at `<workspace>/wiki/sources/<YYYY-MM>-<slug>.md` (for a **skill** directory: breaks it into guidance pages under `wiki/guidance/<topic>/`, plus a `## Generates` source page — see `references/ingest-workflow.md`)
```

- [ ] **Step 4: Verify the edits landed**

Run: `grep -n "skill" plugins/graph-wiki/commands/ingest.md plugins/graph-wiki/agents/ingestor.md`
Expected: matches in the source-types table, the "What happens" step, and the new `### 4a` block.

- [ ] **Step 5: Commit**

```bash
git add plugins/graph-wiki/agents/ingestor.md plugins/graph-wiki/commands/ingest.md
git commit -m "docs(ingest): note skill→guidance branch in ingestor agent + command"
```

---

### Task 6: Final verification

**Files:** none (verification only)

- [ ] **Step 1: Run the wiki-io test suite**

Run: `uv run --package wiki-io pytest packages/wiki-io/`
Expected: all pass, including the 5 new `test_skill_ingest_brief.py` tests and the extended `test_prep_module_exports_brief_builders`.

- [ ] **Step 2: Lint the touched files**

Run: `uv run ruff check packages/wiki-io/ plugins/graph-wiki/`
Expected: clean on touched files. (If pre-existing unrelated errors surface elsewhere, they are out of scope — do not "fix" them; confirm the new/edited files are clean.)

- [ ] **Step 3: Manual end-to-end brief check**

Run: `uv run --project "$PWD" python plugins/graph-wiki/skills/graph-wiki/scripts/ingest_source.py --source plugins/graph-wiki/skills/graph-wiki --json`
Expected: `"is_skill": true`, `"included_files"` starting with `"SKILL.md"`, `"excluded_files"` listing the `scripts/*.py` shims.

- [ ] **Step 4: Confirm no regression in the folder/file paths**

Run: `uv run --project "$PWD" python plugins/graph-wiki/skills/graph-wiki/scripts/ingest_source.py --source plugins/graph-wiki/commands/ingest.md --json`
Expected: a normal file brief (no `is_skill` key) — confirms a non-skill path still routes to `build_ingest_brief`.

---

## Self-Review

**Spec coverage:**
- §Components 1 (`build_skill_ingest_brief`) → Task 1. Signature, return dict, title fallback, slug, `suggested_summary_path`, `merge_mode`, `warnings`/`scripts_dominant`, `included_files`/`excluded_files`, `entity_match`, `state_gate` all match the spec's JSON shape.
- §Components 2 (shim routing) → Task 3. Anchor-before-`is_dir()` order, the three-way route, and the human-readable skill output (title, source type, `N included / M excluded`, scripts_dominant warning, suggested path, guidance dir, entity match) are all covered.
- §Components 3 (reference section) → Task 4. Detection, chunking rules, inline frontmatter schema, targets, source-page shape, known-gap note — all ported from the planner/synthesizer prompts.
- §Components 4 (markdown touch-ups) → Task 5 (ingestor.md skill note + ingest.md table row + "What happens" line).
- §Components 5 (tests) → Task 1 (skill dir, bare `SKILL.md`, scripts_dominant, excluded capture) + Task 1 step 5 / Task 2 (non-skill returns None; Bedrock-free export).
- §Verification → Task 6 (pytest green, manual `--json` skill brief, ruff clean).

**Out-of-scope respected:** the Bedrock branch and `gw wiki ingest source` are untouched (Task 3 only edits the Claude branch); no planner/synthesizer code is ported (Task 4 is doc-only); the backlink-wiring gap is documented, not fixed.

**Type consistency:** `build_skill_ingest_brief(anchor, wiki, repo, workspace_root)` is called identically in the shim (Task 3) and tests (Task 1). `resolve_skill_anchor` and `gather_skill_sources` are used per their existing signatures. Brief keys referenced in the shim's human-readable branch (`is_skill`, `title`, `source_type`, `included_files`, `excluded_files`, `scripts_dominant`, `suggested_summary_path`, `guidance_dir`, `entity_match`) all exist in the builder's return dict.

---

## Execution Handoff

**Plan complete and saved to `docs/superpowers/plans/2026-06-09-claude-path-skill-ingest.md`. Two execution options:**

**1. Subagent-Driven (recommended)** — I dispatch a fresh subagent per task, review between tasks, fast iteration.

**2. Inline Execution** — Execute tasks in this session using executing-plans, batch execution with checkpoints.

**Which approach?**
