# Design: Directory-Aware Skill Ingest (folder → combined markdown)

**Date:** 2026-06-09
**Status:** approved
**Scope:** Lets `gw wiki ingest` accept a **skill directory** (or its `SKILL.md`),
gather `SKILL.md` plus all transitively-linked companion markdown into one combined
text, exclude non-markdown (scripts/assets) with a warning, and hand that combined
text to the **existing** two-pass planner→synthesizer skill branch unchanged.

**Depends on:**
- `completed/2026-06-08-guidance-package-design.md` (guidance schema, `guidance-io`)
- `completed/2026-06-08-type-branched-ingest-design.md` (the `skill` branch this feeds)

---

## Background

The type-branched ingest design treats a skill as a single `SKILL.md` file: it path-
guesses `skill`, then runs a two-pass planner→synthesizer flow that writes
`wiki/guidance/<topic>/<slug>.md` pages. But agent skills are frequently a *directory*
— a `SKILL.md` that links out to companion reference markdown (e.g.
`references/advanced.md`, `examples.md`), sometimes chained several levels deep. The
single-file ingest captures only the entry point and silently drops the linked
material.

This design points ingest at the skill **directory**, gathers the linked markdown into
one combined blob, and feeds that to the unchanged skill branch. The two-pass synthesis,
guidance-io schema, and common tail are untouched — they simply receive a richer `text`.

Skills with executable content (`scripts/`, `.py`, `.sh`, assets) are out of the
intended use case (this feature targets instructional / technical-knowledge skills, not
workflow skills). Non-markdown content is **excluded** with a warning rather than ingested.

---

## Architecture

### Where the change lands

One new pure function family in `wiki-io/src/wiki_io/ingest_source.py`, beside the
existing `extract` / `guess_source_type` (same testable, Bedrock-free module; reusable by
the agentic plugin path later). The **planner, synthesizer, `guidance-io`, and
`_run_common_tail` are not modified** — they receive a richer `text`. `_run_skill_branch`
gains one responsibility only: render the `## Excluded` section and emit the warnings from
the bundle's excluded-files data (§4); its planner→synthesizer logic is unchanged.

```python
@dataclass
class SkillBundle:
    combined_text: str        # SKILL.md, then linked files in discovery order, with separators
    skill_dir: Path
    anchor: Path              # the resolved SKILL.md
    title: str | None         # from SKILL.md frontmatter `name:` or first `# ` heading
    included_files: list[str] # rel paths (POSIX), SKILL.md first, in DFS link order
    excluded_files: list[str] # every non-.md file found under skill_dir (POSIX rel paths, sorted)
    scripts_dominant: bool    # heuristic flag (see §4)

def resolve_skill_anchor(source_path: Path) -> Path | None: ...
def gather_skill_sources(anchor: Path) -> SkillBundle: ...
```

### Flow

```
run_ingest_source()
  ├── resolve wiki/repo, project_ctx, graph conn  [unchanged]
  ├── anchor = resolve_skill_anchor(source_path)
  │    ├── anchor is not None → bundle = gather_skill_sources(anchor)
  │    │       text   = bundle.combined_text
  │    │       title  = bundle.title (fallback: stem-titleize)
  │    │       path_guess = "skill"  (forced)
  │    └── anchor is None     → text, title = extract(source_path)   [today's path]
  │                              path_guess = guess_source_type(...)
  ├── entity lookup            [unchanged]
  ├── dispatch on path_guess   [unchanged: "skill" → _run_skill_branch, else default]
  └── _run_common_tail(...)    [unchanged]
```

The `SkillBundle` (its `excluded_files` and `scripts_dominant`) is threaded into
`_run_skill_branch` so it can render the `## Excluded` section and emit warnings — see §4.

---

## 1. Detection & normalization

`resolve_skill_anchor(source_path)` returns the `SKILL.md` to anchor on, or `None`:

- `source_path` is a **directory** containing `SKILL.md` → `<dir>/SKILL.md`
- `source_path` is a **file named `SKILL.md`** → `source_path`
- otherwise → `None`

When `None`, control falls through to today's behavior: `extract(source_path)` +
`guess_source_type(...)`. This preserves the existing single-file path — an existing
`raw/skill/foo.md` still ingests as a `skill` (via the `raw/skill/` path-guess) with no
companion gathering. Directory-and-`SKILL.md` gathering is purely additive.

When an anchor **is** found, `path_guess` is forced to `"skill"` regardless of where the
directory lives (works for `~/.claude/skills/...` outside the workspace, not only
`raw/skill/`).

### Title

`bundle.title` comes from the anchor `SKILL.md`:
1. YAML frontmatter `name:` if present, else
2. the first `# ` heading, else
3. `None` (caller falls back to `source_path.stem` titleized, as today).

---

## 2. Link-following (transitive)

For each markdown file, parse links and keep only companion-markdown targets:

- **Inline links** `[text](target)` and **reference definitions** `[id]: target`.
- A target is kept only if it: ends in `.md`; is **not** an `http(s)://`/`mailto:` URL
  or a pure `#anchor`; resolves (relative to the *linking* file's directory) to an
  existing file; and that resolved path stays **inside `skill_dir`** (directory-boundary
  guard — never escape via `../`).
- Any `#fragment` on the target is stripped before resolution.

Recursion is **transitive** (depth-unbounded) with a **visited-set** keyed by resolved
absolute path, so cycles terminate and each file is included at most once. Traversal is
DFS in link-appearance order. `SKILL.md` is always first.

---

## 3. Concatenation

`combined_text` is the included files concatenated in discovery order. Each file's
content is prefixed with an HTML-comment boundary marker carrying its `skill_dir`-relative
path, so the planner can see file provenance and chunk on natural boundaries. An HTML
comment (not a heading) is used so it does not render as content or perturb chunking:

```
<!-- skill-file: SKILL.md -->
<SKILL.md contents>

<!-- skill-file: references/advanced.md -->
<references/advanced.md contents>
```

The planner already receives the **full** combined text (`_build_skill_planner_human`
passes full `text`, not the 1200-char preview), so large bundles plan correctly.

---

## 4. Scripts / non-markdown handling

- Every non-`.md` file found under `skill_dir` (recursive walk) is added to
  `excluded_files` and **not** read into `combined_text`. This includes `scripts/`,
  `.py`/`.sh`/etc., and binary/asset files.
- `scripts_dominant` is `True` when **either** a top-level `scripts/` directory exists
  under `skill_dir`, **or** `len(excluded_files) > len(included_files)`.

In `_run_skill_branch`:

- The Source-page body gains an **`## Excluded`** section listing the skipped files
  (paths, plus a count), so the wiki records that the skill had non-markdown components
  that were not ingested. When there are no excluded files, the section is omitted.
- A `logger.warning` names the excluded files (count + paths).
- When `scripts_dominant`, an additional louder `logger.warning` notes that the directory
  looks like a workflow skill and may be a poor fit for guidance ingestion — but the
  ingest **proceeds** anyway (no hard gate).

The `## Generates` provenance section (from the type-branched design) is unchanged; the
`## Excluded` section is additive.

---

## 5. Fallback behavior (unchanged contract)

If the planner call fails or produces no usable chunk plan, `_run_skill_branch` returns
`None` and the default branch runs on the combined `text` (truncated to its 1200-char
preview, as today). Degraded but safe — the Source page is still written. The
`## Excluded` section and warnings are tied to the skill branch; on fallback they are not
emitted (the default branch produces a generic Source page).

---

## Testing

Pure-function tests on `gather_skill_sources` / `resolve_skill_anchor` (no Bedrock):

- directory input → finds and anchors `SKILL.md`; `SKILL.md`-file input → anchors itself;
  unrelated file → `None`.
- transitive link-following: `SKILL.md` → `a.md` → `b.md` all included in DFS order.
- cycle guard: `a.md` ↔ `b.md` terminates, each included once.
- directory-boundary guard: a `[..](../outside.md)` link is **not** followed.
- non-markdown / `http(s)` / `#anchor` targets are skipped.
- `excluded_files` captures non-`.md` files; `scripts_dominant` fires on a top-level
  `scripts/` dir and on excluded-majority.
- title resolution: frontmatter `name:` wins over first heading; falls back to `None`.
- separator markers appear once per included file, in order.

A focused test that `run_ingest_source` forces `path_guess == "skill"` for a directory
anchor, and that the `## Excluded` section renders when `excluded_files` is non-empty.

---

## Out of Scope

- Extracting/ingesting non-markdown content (scripts, notebooks, assets).
- Guidance search, retrieval, and context injection (future specs).
- Lint rules validating the `## Excluded` section or skill provenance.
- Changes to the planner/synthesizer prompts, `guidance-io`, or `_run_common_tail`.
