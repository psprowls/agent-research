# Phase 26: plugin-prompt-source-mirror-sync — Pattern Map

**Mapped:** 2026-05-21
**Files analyzed:** ~30 (12 prompt files, 7 divergence modules, 6 rubric files, 1 test, 1 brand-gate script, 1 allowlist, 2 new agent-local sources files, the `packages/prompt-sources/` deletion target, and root `pyproject.toml`)
**Analogs found:** 30 / 30 (every file has a direct in-tree precedent from Phases 21-25; only the new agent-local sources tree under `prompts/sources/` is greenfield — and its content is verbatim-ported from existing prompt-sources files)

This is a **mechanical re-anchor + delete phase** with a test-strength upgrade and one additive brand-gate block. Same cadence as Phases 22-25 (discovery → uniform rewrite → test update → brand-gate addition → verification). The strongest in-tree analogs are:

- **Phase 23** (`23-PATTERNS.md` §"Plugin-doc ↔ Prompt-source mirror pattern") — established the mirror invariant this phase deletes; its `WSMCP-07` brand-gate block is the structural template for CHECK 6. Its plugin-doc + mirror sweep is the structural template for the re-anchor step.
- **Phase 24** (`24-01-PLAN.md`) — added CHECK 5 to `scripts/check-brand.sh` (currently at L100-120). This phase adds CHECK 6 mirroring the same block shape.
- **Phase 25** (`25-01-PLAN.md`) — the immediate precedent for a "sweep + brand-gate + verification" phase against `packages/`-tree content. CHECK 5's path-scope narrowing (`packages/eval-harness/src packages/eval-harness/tests`) is the closest analog for CHECK 6's path scope.
- **Phase 21** (`.brand-grep-allow` L222+) — established the per-entry rationale-comment pattern for allowlist seeding.

## File Classification

| File | Role | Data Flow | Closest Analog | Match |
|------|------|-----------|----------------|-------|
| `agents/graph-wiki-agent/src/graph_wiki_agent/prompts/_fragments/iron_rules.py` | prompt-fragment (3-line provenance header) | static-string | `_fragments/page_categories.py` (same shape) | exact |
| `agents/graph-wiki-agent/src/graph_wiki_agent/prompts/_fragments/page_categories.py` | prompt-fragment | static-string | self (uniform fragment shape across 8 siblings) | exact |
| `agents/graph-wiki-agent/src/graph_wiki_agent/prompts/_fragments/architecture_overview.py` | prompt-fragment | static-string | self | exact |
| `agents/graph-wiki-agent/src/graph_wiki_agent/prompts/_fragments/citation_rules.py` | prompt-fragment | static-string | self | exact |
| `agents/graph-wiki-agent/src/graph_wiki_agent/prompts/_fragments/claude_md_disambiguation.py` | prompt-fragment | static-string | self | exact |
| `agents/graph-wiki-agent/src/graph_wiki_agent/prompts/_fragments/frontmatter_rules.py` | prompt-fragment | static-string | self | exact |
| `agents/graph-wiki-agent/src/graph_wiki_agent/prompts/_fragments/log_format.py` | prompt-fragment (template anchor) | static-string | self — but new target is `CLAUDE.md.template` (workspace-io asset) | role-match |
| `agents/graph-wiki-agent/src/graph_wiki_agent/prompts/_fragments/style_rules.py` | prompt-fragment (template anchor) | static-string | self — same template-target rebind as `log_format.py` | role-match |
| `agents/graph-wiki-agent/src/graph_wiki_agent/prompts/scanner.py` | prompt-builder | composition | inline `# Source:` comments (L15-17) | exact |
| `agents/graph-wiki-agent/src/graph_wiki_agent/prompts/linter.py` | prompt-builder | composition | inline `# Source:` comments (L17, L26, L55) | exact |
| `agents/graph-wiki-agent/src/graph_wiki_agent/prompts/ingestor.py` | prompt-builder | composition | docstring + inline comments | exact |
| `agents/graph-wiki-agent/src/graph_wiki_agent/prompts/librarian.py` | prompt-builder | composition | docstring + inline comments | exact |
| `agents/graph-wiki-agent/src/graph_wiki_agent/prompts/code_reader.py` | prompt-constant (Bedrock-only) | static-string | self — references the new `prompts/sources/code_reader.md` | role-match |
| `agents/graph-wiki-agent/src/graph_wiki_agent/prompts/synthesizer.py` | prompt-constant (Bedrock-only) | static-string | self — references the new `prompts/sources/synthesizer.md` | role-match |
| `agents/graph-wiki-agent/src/graph_wiki_agent/prompts/sources/code_reader.md` | **NEW** agent-local source | static-asset | `packages/prompt-sources/agents/code_reader.md` (verbatim port, rebrand sweep) | exact |
| `agents/graph-wiki-agent/src/graph_wiki_agent/prompts/sources/synthesizer.md` | **NEW** agent-local source | static-asset | `packages/prompt-sources/agents/synthesizer.md` (verbatim port, rebrand sweep) | exact |
| `packages/eval-harness/src/eval_harness/divergence/scanner.py` | divergence-rules (literal `source_anchor=`) | metadata | `divergence/ingestor.py` (uniform shape) | exact |
| `packages/eval-harness/src/eval_harness/divergence/ingestor.py` | divergence-rules | metadata | self | exact |
| `packages/eval-harness/src/eval_harness/divergence/librarian.py` | divergence-rules | metadata | self | exact |
| `packages/eval-harness/src/eval_harness/divergence/linter.py` | divergence-rules | metadata | self | exact |
| `packages/eval-harness/src/eval_harness/divergence/synthesizer.py` | divergence-rules | metadata | self — also has prose `Anchors ...` lines (L20, L36, L49, L66, L89) | exact |
| `packages/eval-harness/src/eval_harness/divergence/code_reader.py` | divergence-rules | metadata | self — also has prose `Anchors ...` lines (L15, L44, L61, L76, L91) | exact |
| `packages/eval-harness/src/eval_harness/divergence/check.py` | dataclass docstring (example anchor) | metadata | self (L59-60 docstring) | exact |
| `packages/eval-harness/src/eval_harness/divergence/rubrics/{ingestor,librarian,linter,scanner,synthesizer,code_reader}.md` | rubric docs (3-line HTML-comment header) | metadata | uniform across all 6 | exact |
| `agents/graph-wiki-agent/tests/prompts/test_provenance.py` | test (provenance validator) | request-response | self — heading-extraction logic already present; this phase upgrades semantics | role-match |
| `scripts/check-brand.sh` (additive CHECK 6 block) | brand-gate | batch | CHECK 5 block at L100-120 (Phase 24); CHECK 2 at L52-66 (Phase 18) | exact |
| `.brand-grep-allow` (additive entries) | allowlist config | n/a | existing Phase 21 entries (R-04 self-allowlist at L62-72) | exact |
| `packages/prompt-sources/` (entire tree) | upstream-snapshot | n/a (DELETION) | Phase 24 D-07 hard-cut pattern | role-match |
| Root `pyproject.toml` (`exclude = ["packages/prompt-sources"]` line removal) | workspace config | n/a | self — uv-workspace exclude entries | exact |

## Pattern Assignments

### Fragment files — `# Source: ... # Anchor: ... # Source-commit: ...` (D-03, D-05)

**Files (8):** `_fragments/{architecture_overview,citation_rules,claude_md_disambiguation,frontmatter_rules,iron_rules,log_format,page_categories,style_rules}.py`.

**Uniform current shape (verified at `_fragments/iron_rules.py` L1-3):**
```python
# Source: packages/prompt-sources/SKILL.md
# Anchor: ## Iron rules (L193-L201)
# Source-commit: ef05d99
```

**Uniform new shape (per D-03 + D-05 — line ranges dropped, anchor compressed into Source: line):**
```python
# Source: plugins/graph-wiki/skills/graph-wiki/SKILL.md §Iron rules
```

**Wait — schema interaction with test_provenance.py.** The current test (`test_provenance.py` L53-58) hard-requires the 3-line header (`Source:`, `Anchor:`, `Source-commit:`). D-05 drops line-range pins from anchor strings, but it does NOT explicitly say to collapse from 3 lines to 1 line. Two consistent interpretations exist; **planner must pick one and apply uniformly**:

  - **Option A (collapse to 1 line):** `# Source: <path> §<section>` replaces all 3 lines. Requires `_PROVENANCE_RE` in test_provenance.py to be rewritten — single `^# Source: ...` line. The `# Source-commit:` line is moot (lattice SHA is gone with the tree). This is consistent with D-05's example `# Source: plugins/graph-wiki/agents/linter.md §Pass 2, §Rules`.
  - **Option B (keep 3 lines, drop only line-range pins):** `# Source: <path>` / `# Anchor: <section>` / `# Source-commit: <plugin-commit-or-NONE>`. Requires picking a stable Source-commit value (none exists for the plugin — its content is the spec now).

**Recommendation: Option A.** D-05's example shape is 1 line, and the `Source-commit` line is meaningless after the upstream-SHA pin drops (lattice is deprecated; the plugin IS the spec). The test update (D-08) must change `_PROVENANCE_RE` to match a single-line header.

**Per-file new shape (Option A):**

| File | New `# Source:` line |
|------|----------------------|
| `_fragments/architecture_overview.py` | `# Source: plugins/graph-wiki/skills/graph-wiki/SKILL.md §Architecture` |
| `_fragments/iron_rules.py` | `# Source: plugins/graph-wiki/skills/graph-wiki/SKILL.md §Iron rules` |
| `_fragments/page_categories.py` | `# Source: plugins/graph-wiki/skills/graph-wiki/SKILL.md §Page categories` |
| `_fragments/claude_md_disambiguation.py` | `# Source: plugins/graph-wiki/skills/graph-wiki/SKILL.md §Cross-tool compatibility` |
| `_fragments/citation_rules.py` | `# Source: plugins/graph-wiki/agents/librarian.md §Rules` |
| `_fragments/frontmatter_rules.py` | `# Source: plugins/graph-wiki/agents/ingestor.md §4. Write the source summary` |
| `_fragments/log_format.py` | `# Source: packages/workspace-io/src/workspace_io/assets/CLAUDE.md.template §Log format` ← **audit entry: heading does not exist; see D-04 audit table** |
| `_fragments/style_rules.py` | `# Source: packages/workspace-io/src/workspace_io/assets/CLAUDE.md.template §Style` ← **audit entry: heading does not exist; see D-04 audit table** |

**Critical: `CLAUDE.md.template` does NOT currently have `## Log format` or `## Style` headings.** Verified via `grep -nE "^#+ " packages/workspace-io/src/workspace_io/assets/CLAUDE.md.template`:
```
1:# Graph-Wiki Workspace
8:## Layout
17:## Plugins installed
25:## Conventions for LLM agents
```
Per D-04 missing-content policy, the planner produces an audit row for each. Per D-07 the asset IS the canonical source — if `LOG_FORMAT`/`STYLE_RULES` content should live in `CLAUDE.md.template`, the resolution is **restore the sections to the template**. Otherwise the planner must pick an alternative target (e.g. `plugins/graph-wiki/skills/graph-wiki/SKILL.md` which used to host this content) or drop the anchor pointer. This is the most important call this phase makes.

---

### Prompt-builder files — inline `# Source: ...` comments

**Files:** `prompts/{scanner,linter,ingestor,librarian}.py`.

**Current shape (verified at `prompts/scanner.py` L15-17, `prompts/linter.py` L17, L26, L55):**

```python
# Source: packages/prompt-sources/agents/scanner.md
# Anchor: ## Role, ## Rules, ## Red flags
# Source-commit: ef05d99
```

```python
# Source: packages/prompt-sources/agents/linter.md §Rules bullet 3
```

```python
# Source: packages/prompt-sources/agents/linter.md §Pass 2 (L48-L56), §Rules (L93-L101)
```

**New shape (per D-05 — collapse to single line, drop line-range pins, drop Source-commit, GitHub-slug-ready section name):**

| File:Line | Current | New |
|-----------|---------|-----|
| `scanner.py` L15-17 | 3-line block | `# Source: plugins/graph-wiki/agents/scanner.md §Role, §Rules, §Red flags` |
| `linter.py` L17 (docstring line) | `Source: packages/prompt-sources/agents/linter.md (Pass 2/3 and Rules section)` | `Source: plugins/graph-wiki/agents/linter.md §Pass 2 — Semantic (read and think), §Rules` |
| `linter.py` L26 | `# Source: packages/prompt-sources/agents/linter.md §Rules bullet 3` | `# Source: plugins/graph-wiki/agents/linter.md §Rules` (drop bullet pin per D-05 spirit — bullet numbers churn) |
| `linter.py` L55 | `# Source: packages/prompt-sources/agents/linter.md §Pass 2 (L48-L56), §Rules (L93-L101)` | `# Source: plugins/graph-wiki/agents/linter.md §Pass 2 — Semantic (read and think), §Rules` |
| `ingestor.py` docstring (L5) | `Ports packages/prompt-sources/agents/ingestor.md per PORT-03 (Phase 6).` | `Ports plugins/graph-wiki/agents/ingestor.md per PORT-03 (Phase 6).` |
| `librarian.py` docstring (L7) | `1. Role intro (librarian-local, adapted from packages/prompt-sources/agents/librarian.md)` | `1. Role intro (librarian-local, adapted from plugins/graph-wiki/agents/librarian.md)` |

**Note on `linter.py` L17 docstring.** This is *inside* a triple-quoted module docstring, not a `# Source:` comment. The test_provenance.py whitelist check (D-08 step 1) only applies to `# Source:` *comments*; module docstrings are not in scope. Still rebrand for consistency.

**GitHub-slug verification (D-03).** Plugin headings verified via `grep -nE "^#+ " plugins/graph-wiki/agents/{ingestor,librarian,linter,scanner}.md`:
- `plugins/graph-wiki/agents/scanner.md` has `## Role` (L13), `## Rules` (L100), `## Red flags` (L108) — all three section names referenced in new shape exist verbatim. ✓
- `plugins/graph-wiki/agents/linter.md` has `### Pass 2 — Semantic (read and think)` (L46) and `## Rules` (L98). The em-dash in "Pass 2 — Semantic" is a stable rendering but slugs to `pass-2--semantic-read-and-think` (double-hyphen). Planner should confirm slug behavior with test_provenance.py D-08 step 2.
- `plugins/graph-wiki/agents/ingestor.md` has `### 4. Write the source summary` (L49) — slug `4-write-the-source-summary` matches D-03 example.

---

### Bedrock-only prompt constants — D-06 agent-local sources

**Files:** `prompts/code_reader.py`, `prompts/synthesizer.py` (existing); `prompts/sources/code_reader.md`, `prompts/sources/synthesizer.md` (**new**).

**Current state.** Verified at `prompts/code_reader.py` L1-3 and `prompts/synthesizer.py` L1-3 — neither file currently carries a `# Source:` provenance comment (they were "relocated from commands/query.py per D-14"). This phase **adds** provenance comments pointing at the new agent-local sources.

**New provenance comments to add (per D-06):**

`prompts/code_reader.py` — add immediately after the module docstring (after L3):
```python
# Source: agents/graph-wiki-agent/src/graph_wiki_agent/prompts/sources/code_reader.md §Rules, §Outputs, §Red flags
```

`prompts/synthesizer.py` — same pattern:
```python
# Source: agents/graph-wiki-agent/src/graph_wiki_agent/prompts/sources/synthesizer.md §Rules
```

**New files to create.** Both are verbatim ports of the deleted `packages/prompt-sources/agents/{code_reader,synthesizer}.md` with a rebrand sweep:

`agents/graph-wiki-agent/src/graph_wiki_agent/prompts/sources/code_reader.md` ← content of `packages/prompt-sources/agents/code_reader.md`. **Rebrand:** L4 frontmatter `skills: [lattice-wiki, source-reader]` → `skills: [graph-wiki, source-reader]` (lattice → graph-wiki). Verified via `grep -ni "lattice" packages/prompt-sources/agents/code_reader.md`.

`agents/graph-wiki-agent/src/graph_wiki_agent/prompts/sources/synthesizer.md` ← content of `packages/prompt-sources/agents/synthesizer.md`. **Rebrand:** L4 frontmatter `skills: [lattice-wiki, obsidian-markdown]` → `skills: [graph-wiki, obsidian-markdown]`. Verified via `grep -ni "lattice" packages/prompt-sources/agents/synthesizer.md`.

**`__init__.py` decision (per CONTEXT "Claude's Discretion"):** the tree is markdown-only. Recommendation — no `__init__.py`. Python tooling does not need to import .md files; the directory is a pure-asset tree. If tests want to walk it, they can use `pathlib.Path` directly (the same pattern `test_provenance.py` already uses with `FRAGMENT_DIR.glob("*.py")`).

---

### Eval-harness divergence-rules — `source_anchor=` literals

**Files (6):** `divergence/{scanner,ingestor,librarian,linter,synthesizer,code_reader}.py`.

**Uniform shape (verified at `divergence/scanner.py` L66, L72, L78, L84):**
```python
DivergenceCheck(
    id="SCN-001-frontmatter-present",
    source_anchor="packages/prompt-sources/agents/scanner.md#workflow-step-3",
    severity="hard",
    check=_check_frontmatter_present,
),
```

**Per-role inventory (every literal counted via `grep -n 'source_anchor=' packages/eval-harness/src/eval_harness/divergence/*.py`):**

| File | Count | Current path-prefix | New path-prefix |
|------|-------|---------------------|-----------------|
| `scanner.py` | 4 | `packages/prompt-sources/agents/scanner.md` | `plugins/graph-wiki/agents/scanner.md` |
| `ingestor.py` | 4 | `packages/prompt-sources/agents/ingestor.md` (3) + `packages/prompt-sources/SKILL.md` (1) | `plugins/graph-wiki/agents/ingestor.md` + `plugins/graph-wiki/skills/graph-wiki/SKILL.md` |
| `librarian.py` | 4 | `packages/prompt-sources/SKILL.md` (1) + `packages/prompt-sources/agents/librarian.md` (3) | `plugins/graph-wiki/skills/graph-wiki/SKILL.md` + `plugins/graph-wiki/agents/librarian.md` |
| `linter.py` | 3 | `packages/prompt-sources/agents/linter.md` | `plugins/graph-wiki/agents/linter.md` |
| `synthesizer.py` | 4 | `packages/prompt-sources/agents/synthesizer.md` | `agents/graph-wiki-agent/src/graph_wiki_agent/prompts/sources/synthesizer.md` |
| `code_reader.py` | 4 | `packages/prompt-sources/agents/code_reader.md` | `agents/graph-wiki-agent/src/graph_wiki_agent/prompts/sources/code_reader.md` |

**Anchor-slug audit (D-04).** Each `#section` suffix must resolve against the new target file. Critical audit cases:
- `scanner.md#workflow-step-3` → plugin scanner.md has no single `## Workflow step 3` heading; the workflow is split into 10 `### N. <name>` subheadings under `## Workflow`. The original anchor pre-dated the new heading shape. Audit row: re-point to `#3-create-stubs-for-new-packages` (the slug of `### 3. Create stubs for new packages` at scanner.md L47).
- `ingestor.md#workflow-step-4` → plugin ingestor.md has `### 4. Write the source summary` (L49). New slug: `#4-write-the-source-summary` (matches D-03 example verbatim).
- `librarian.md#rules` → plugin librarian.md has `## Rules` (L72). Slug `#rules` resolves. ✓
- `linter.md#rules` → plugin linter.md has `## Rules` (L98). Slug `#rules` resolves. ✓
- `linter.md#workflow-pass-3` → plugin linter.md has `### Pass 3 — Report` (L58). New slug: `#pass-3--report`. **Naming drift** — was "workflow-pass-3", now slugs to `pass-3--report`.
- `SKILL.md#iron-rules` → plugin SKILL.md has `## Iron rules` (L191). Slug `#iron-rules` resolves. ✓
- `SKILL.md#page-categories` → plugin SKILL.md has `## Page categories` (L140). Slug `#page-categories` resolves. ✓
- `synthesizer.md#rules`, `synthesizer.md#red-flags` → new file ported verbatim from prompt-sources; headings preserved. ✓
- `code_reader.md#outputs`, `code_reader.md#rules`, `code_reader.md#red-flags` → same; verbatim port. ✓

**Output:** the planner produces a complete audit table in PLAN.md with three columns per D-04 (`current anchor`, `plugin file state`, `proposed resolution`). The table above is the seed.

---

### Eval-harness divergence-rules — prose `Anchors ...` lines

**Files:** `divergence/synthesizer.py`, `divergence/code_reader.py`.

**Current shape (verified at `divergence/synthesizer.py` L20, L36, L49, L66, L89; `divergence/code_reader.py` L15, L44, L61, L76, L91):**
```python
# Vault-thinness acknowledgement phrasing per packages/prompt-sources/agents/synthesizer.md
```
```python
    Anchors packages/prompt-sources/agents/synthesizer.md#rules (rule 1 + 3).
```

These are **inside function docstrings**, not standalone `# Source:` comments. They are still in scope for the path-prefix rewrite (`packages/prompt-sources/` → `agents/graph-wiki-agent/src/graph_wiki_agent/prompts/sources/` for synthesizer + code_reader) but are NOT checked by test_provenance.py's whitelist (D-08 step 1 scans only `# Source:` comments in `_fragments/` and prompts/*.py files, not eval-harness docstrings).

**Approach:** mechanical find-and-replace of the path prefix only. Section anchors (`#rules`, `#red-flags`, `#outputs`) carry forward unchanged because the new agent-local sources are verbatim ports.

---

### Eval-harness divergence — `check.py` docstring example

**File:** `packages/eval-harness/src/eval_harness/divergence/check.py` L59-60.

**Current shape:**
```python
        source_anchor: Path + section anchor tracing back to canonical source
                       (e.g. "packages/prompt-sources/SKILL.md#iron-rules").
```

**New shape:**
```python
        source_anchor: Path + section anchor tracing back to canonical source
                       (e.g. "plugins/graph-wiki/skills/graph-wiki/SKILL.md#iron-rules").
```

Mechanical, single-site, docstring-only.

---

### Eval-harness rubric files — 3-line HTML-comment header

**Files (6):** `divergence/rubrics/{ingestor,librarian,linter,scanner,synthesizer,code_reader}.md`.

**Uniform current shape (verified at `rubrics/scanner.md` L1-3, `rubrics/ingestor.md` L1-3):**
```html
<!-- Source: packages/prompt-sources/agents/scanner.md -->
<!-- Anchor: ## Rules + ## Red flags -->
<!-- Source-commit: ef05d991a9ab1ea12b1bc7ebc1fb20ba70074030 -->
```

**Uniform new shape (per D-03 + D-05 — collapse to 1 line for consistency with python comment rewrite, but rubric files are not scanned by test_provenance.py, so Option A vs Option B is purely a stylistic call):**

```html
<!-- Source: plugins/graph-wiki/agents/scanner.md §Rules, §Red flags -->
```

**Per-file mapping:**

| File | New `<!-- Source: -->` line |
|------|-----------------------------|
| `rubrics/scanner.md` | `<!-- Source: plugins/graph-wiki/agents/scanner.md §Rules, §Red flags -->` |
| `rubrics/ingestor.md` | `<!-- Source: plugins/graph-wiki/agents/ingestor.md §Rules, §Red flags -->` |
| `rubrics/librarian.md` | `<!-- Source: plugins/graph-wiki/agents/librarian.md §Rules, §Red flags -->` |
| `rubrics/linter.md` | `<!-- Source: plugins/graph-wiki/agents/linter.md §Rules, §Red flags -->` |
| `rubrics/synthesizer.md` | `<!-- Source: agents/graph-wiki-agent/src/graph_wiki_agent/prompts/sources/synthesizer.md §Rules, §Red flags -->` |
| `rubrics/code_reader.md` | `<!-- Source: agents/graph-wiki-agent/src/graph_wiki_agent/prompts/sources/code_reader.md §Rules, §Red flags -->` |

**Also drop:** the `<!-- Source-commit: ef05d991... -->` line (per CONTEXT — lattice SHA is gone with the tree).

**Also rebrand:** `rubrics/scanner.md` L9 currently reads `from the canonical lattice-wiki scanner spec` — `lattice-wiki` → `graph-wiki` per the rebrand sweep applied to migrated content. Same likely true for the other 5 rubric files (verify per-file).

---

### Test upgrade — `test_provenance.py` (D-08, D-09)

**File:** `agents/graph-wiki-agent/tests/prompts/test_provenance.py`.

**Current shape (verified L20-37, L46, L53-58):** the test imports a regex matching the 3-line header, anchors `FRAGMENT_DIR` at `_fragments/`, and anchors `PROMPT_SOURCES_DIR` at `packages/prompt-sources/`. Two tests: header-presence and source-path resolution.

**Required new shape per D-08:**

1. **Drop `PROMPT_SOURCES_DIR` anchor** (the tree is being deleted).
2. **Rewrite `_PROVENANCE_RE`** to match the new single-line shape (Option A above):
   ```python
   _PROVENANCE_RE = re.compile(
       r"^# Source: (?P<source>\S+)(?: §(?P<sections>.+))?\s*$",
       re.MULTILINE,
   )
   ```
3. **Widen scan scope.** Currently scans only `_fragments/*.py`. Per D-08, must also scan `prompts/*.py` (which has `# Source:` comments at `prompts/scanner.py` L15, `prompts/code_reader.py` (new), `prompts/synthesizer.py` (new); and possibly `prompts/linter.py` L26, L55 — depending on Option A vs B).
4. **Add whitelist check (D-08 step 1):** path-prefix must start with exactly one of:
   - `plugins/graph-wiki/`
   - `packages/workspace-io/src/workspace_io/assets/CLAUDE.md.template` (exact string, not prefix — only this one file under workspace-io is allowed)
   - `agents/graph-wiki-agent/src/graph_wiki_agent/prompts/sources/`
5. **Add resolution check (D-08 step 2):** referenced file exists; cited `§section` name resolves to a `^#+ ` heading in the file by GitHub-slug match.
6. **Add semantic-drift check (D-08 step 3):** extract code identifiers + capitalized-noun phrases ≥3 chars from the cited section; assert ≥70% appear (case-insensitive) somewhere in the Python string constant that the `# Source:` comment belongs to. The constant is the one that starts within ~5 lines after the comment.

**Existing pattern to extend (heading-slug logic).** `test_provenance.py` does not currently parse heading slugs — that's net-new logic. Closest analog in the repo: there is no existing GitHub-slug implementation. The implementer should follow the standard rule:
```python
def slugify(heading: str) -> str:
    # Lowercase, strip punctuation except hyphens/underscores, spaces → hyphens.
    s = heading.lower()
    s = re.sub(r"[^\w\s-]", "", s)
    s = re.sub(r"\s+", "-", s.strip())
    return s
```
Test against known cases from D-03: `"### 4. Write the source summary"` → `"4-write-the-source-summary"`.

**Semantic-drift heuristic (per CONTEXT "Claude's Discretion"):** working definition is "code identifiers + capitalized phrases ≥3 chars". Extract:
- `\b[A-Z][A-Za-z0-9_]+(?:\s+[A-Z][A-Za-z0-9_]+)*\b` for capitalized noun phrases
- `\b[a-z_]+_[a-z_]+\b` for snake_case identifiers
- `` `[^`]+` `` for backticked code spans

Stoplist: common English capitalized words (e.g. `The`, `When`, `If`).

Compute overlap as `len(found_in_constant) / len(tokens_from_section)`. Threshold 70%.

**D-09 carry:** if a fragment's keyword pool fails the 70% gate, the planner widens the fragment's content (canonical citation), not the threshold.

---

### Brand-gate addition — `scripts/check-brand.sh` CHECK 6 (D-10, D-11)

**File:** `scripts/check-brand.sh`.

**Current top check-number is 5** (verified at L100 — `# CHECK 5 — Phase 24 §WSEVAL-07 / D-07`). Phase 26 adds **CHECK 6**.

**Structural analog: CHECK 5 (L100-120)** is the closest precedent — same shape this phase mirrors:
```bash
# CHECK 5 — Phase 24 §WSEVAL-07 / D-07: ban reintroduction of the three
# eval-harness legacy patterns: ...
HITS5=$(grep -rEln --exclude-dir=__pycache__ --exclude='*.pyc' -E \
    'def\s+\w+\([^)]*\bvault_path:\s*Path|def\s+\w+\([^)]*\bvault:\s*Path|"--vault"' \
    packages/eval-harness/src packages/eval-harness/tests 2>/dev/null \
    | grep -vF -f <(grep -vE '^[[:space:]]*(#|$)' "$ALLOWLIST") || true)

if [ -n "$HITS5" ]; then
  echo "$HITS5"
  COUNT5=$(printf '%s\n' "$HITS5" | wc -l | tr -d ' ')
  echo "BRAND-WSEVAL FAIL: ${COUNT5} unallowlisted hits for vault_path: Path|vault: Path|\"--vault\"" >&2
  exit 1
fi
```

**Recommended CHECK 6 implementation (per D-11):**
```bash
# CHECK 6 — Phase 26 §D-10 / D-11: ban reintroduction of `packages/prompt-sources`
# as a path literal anywhere under agents/, packages/, plugins/, scripts/, tests/.
# Path scope EXCLUDES .planning/ — archived milestones, retrospectives, and phase
# histories legitimately reference the deleted tree as historical record.
# Allowlist applies for the self-references inside check-brand.sh + .brand-grep-allow.
HITS6=$(grep -rEln --exclude-dir=__pycache__ --exclude='*.pyc' -F \
    'packages/prompt-sources' \
    agents/ packages/ plugins/ scripts/ tests/ 2>/dev/null \
    | grep -vF -f <(grep -vE '^[[:space:]]*(#|$)' "$ALLOWLIST") || true)

if [ -n "$HITS6" ]; then
  echo "$HITS6"
  COUNT6=$(printf '%s\n' "$HITS6" | wc -l | tr -d ' ')
  echo "BRAND-PROMPT-SOURCES FAIL: ${COUNT6} unallowlisted hits for packages/prompt-sources" >&2
  exit 1
fi
```

**Important regex notes for the planner / executor:**
- `-F` (fixed-string) is correct here — the literal `packages/prompt-sources` has no metacharacters and `-F` is faster + avoids surprise regex interpretation. (CHECK 5 uses `-E` because its patterns are regexes; CHECK 6's pattern is a literal.)
- Path scope is `agents/ packages/ plugins/ scripts/ tests/` per D-11 (NOT `.planning/`).
- No `tests/` top-level directory exists in this repo (tests live inside each package); including it is harmless (grep silently skips missing dirs with 2>/dev/null) and forward-compatible.

**Exit-code envelope (last line at L122):** update the final `echo` to mention CHECK 6:
```bash
echo "BRAND-04 OK: zero unallowlisted hits (BRAND-04 lattice + BRAND-CMD ... + BRAND-WSEVAL ... + BRAND-PROMPT-SOURCES packages/prompt-sources all clean)"
```

**Header comment block (mirroring CHECK 2 / CHECK 5 style):** the inline `# CHECK 6 — Phase 26 §D-10 / D-11:` block above is sufficient. No header at top of script needs editing (the L13-14 Phase 21 note covers that pattern style).

---

### `.brand-grep-allow` seeding

**File:** `.brand-grep-allow` at repo root.

**Existing format (verified at L62-72):** every entry has a `# rationale:` block-comment header naming its D-decision or carry-forward class. Phase 21's R-04 self-allowlist pattern is the exact analog:
```
# ---------------------------------------------------------------------------
# R-04 (self-allowlist per Claude's Discretion): this file itself contains
# 'lattice' literals as pattern documentation, and the gate script contains
# 'lattice' as its grep pattern.
# ---------------------------------------------------------------------------
.brand-grep-allow
scripts/check-brand.sh
```

**Phase 26 expected seed entries (per D-11):**
- `scripts/check-brand.sh` and `.brand-grep-allow` are already self-allowlisted by Phase 21's R-04 block — **no new entry needed** for those two files even though they will literally contain `packages/prompt-sources` in their pattern definitions.
- Release-notes / changelog entries documenting the deletion (e.g. `.planning/v1.4-*.md`) — `.planning/` is already out of the path-scope (D-11), so no allowlist entry needed.
- Any in-scope file that legitimately needs to mention the literal `packages/prompt-sources` after the migration. **Expected count: zero** post-migration. If the dry-run surfaces any, add per Phase 21 style:
```
# ---------------------------------------------------------------------------
# Phase 26 §D-11: <one-line rationale>
# ---------------------------------------------------------------------------
<path-fragment>
```

**Seeding procedure (mirrors Phase 23 / Phase 24):**
1. Land the re-anchor sweep first.
2. Run `bash scripts/check-brand.sh`.
3. Triage each hit — rewrite at source if possible; allowlist with rationale only if not.
4. Re-run until exit 0.

---

### `packages/prompt-sources/` deletion + root `pyproject.toml` exclude removal (D-01, D-02)

**Files:** `packages/prompt-sources/` (tree, ~17 files) + repo-root `pyproject.toml` (1 line).

**Hard-cut pattern (Phase 23 / 24 / 25 precedent):** every v1.4 phase removed the old surface in the **same commit** as the re-anchor. Same here.

**Verification:**
```bash
# After deletion + pyproject.toml edit:
uv sync                                      # workspace resolution must remain green
uv run --package graph-wiki-agent pytest    # full agent tests pass
uv run --package eval-harness pytest        # eval-harness tests pass
bash scripts/check-brand.sh                  # all 6 CHECK blocks pass
```

---

## Shared Patterns

### Pattern 1: 3-line provenance header → 1-line collapse

**Source:** Phase 5/6 fragment provenance shape (current `_fragments/iron_rules.py` L1-3).

**Convention being changed:** 3 lines `# Source:` / `# Anchor:` / `# Source-commit:` collapse into a single `# Source: <path> §<section>` line. The `§` separator is the convention seeded by D-05's example. Multiple sections comma-separated: `§Pass 2 — Semantic, §Rules`.

**Apply to:** every fragment file (8), every prompt-builder `# Source:` comment in `prompts/*.py`, and every rubric HTML comment (6). Uniform across all 21+ sites.

### Pattern 2: Hard-cut migration (no deprecation period)

**Source:** Phase 22 / 23 / 24 / 25 commit shape — old surface removed in the same commit as the new surface.

**Apply to:** the `packages/prompt-sources/` deletion + `pyproject.toml` exclude removal. Both happen in the final milestone (D-13 step 4), gated by green test suite + brand-gate.

### Pattern 3: Brand-gate block structure

**Source:** `scripts/check-brand.sh` CHECK 5 (L100-120, Phase 24) — closest structural analog. CHECK 2 (L52-66, Phase 18) is a secondary analog.

**Block shape:** `# CHECK N — Phase ZZ §<decision>: <one-line rationale>` comment header (multi-line), `HITS<N>=$(grep -rEl[n] ... 2>/dev/null | grep -vF -f <(grep -vE ...) || true)`, `if [ -n "$HITS<N>" ]; then echo "$HITS<N>"; COUNT<N>=$(...); echo "BRAND-<TAG> FAIL: ..." >&2; exit 1; fi`.

**Apply to:** the new CHECK 6 for D-10. Use `-F` (fixed-string) instead of `-E` because the pattern is a literal.

### Pattern 4: Allowlist entry with rationale block

**Source:** `.brand-grep-allow` L62-72 (R-04 self-allowlist, Phase 21).

**Pattern:** `# ---------------------------------------------------------------------------` rule line, `# <D-decision tag>: <one-sentence rationale>` then a `# ---------------------------------------------------------------------------` rule line, then the path-fragment line(s).

**Apply to:** any new D-11 allowlist entries needed after CHECK 6 dry-run (expected: zero in scope).

### Pattern 5: Audit-table-driven anchor reconciliation

**Source:** Phase 23 §PATTERNS "File Classification" tables.

**Convention:** when content has drifted between source and target, produce a table (3 columns: `current anchor` / `target file state` / `proposed resolution`) and decide per-row. The resolution column has 3 values: re-point / restore content / drop the check.

**Apply to:** the D-04 audit. The seed table is the "Anchor-slug audit" subsection of "Eval-harness divergence-rules" above. Special attention required for `CLAUDE.md.template` (currently missing `## Log format` and `## Style` headings — D-04 audit row required).

### Pattern 6: Heading-slug derivation for D-03 / test_provenance.py D-08 step 2

**Source:** GitHub-flavored Markdown slug convention (no existing in-repo implementation; net-new logic).

**Slug rule:** lowercase the heading, strip leading `#`+space, strip punctuation except hyphens/underscores, replace whitespace runs with single hyphen, no trailing hyphen.

**Apply to:** the new resolution logic in `test_provenance.py` (D-08 step 2) and the audit table column "proposed resolution" for every re-anchored `source_anchor=` literal.

## No Analog Found

**The semantic-drift heuristic (D-08 step 3) is net-new logic** — no existing in-tree code does keyword-overlap measurement against extracted noun phrases. The closest analog is `test_provenance.py`'s existing path-resolution check (L86-111), which establishes the file/path scaffolding but not the keyword extraction. The planner should follow the working definition in CONTEXT's "Claude's Discretion" (code identifiers + capitalized phrases ≥3 chars + backticked spans, with English-stoplist filter) — no in-repo precedent exists.

**The `prompts/sources/` tree** is net-new directory structure under `agents/graph-wiki-agent/src/graph_wiki_agent/prompts/`. Closest structural analog: `_fragments/` (sibling directory at same depth). But `_fragments/` contains `.py` modules with provenance headers, whereas `prompts/sources/` will contain raw `.md` assets — different content type, but the directory-naming + `__init__.py`-or-not decision follows the same convention (recommendation above: no `__init__.py`, pure-asset tree).

## Files With Verification Required Before Edit

These files are named or implied in scope but warrant a per-file re-grep before the executor commits to edits:

- **`prompts/code_reader.py` and `prompts/synthesizer.py`** — currently carry NO `# Source:` provenance comment (verified L1-3 in each). Adding one is per D-06; the planner should confirm this is intended (D-06 only specifies the new sources/ tree, not that the constants gain a comment). If not added, the test whitelist (D-08 step 1) skips them entirely — no functional change. **Recommend: add the comments** for symmetry with the rest of the prompt tree.
- **`prompts/scanner.py` L19-22 imports** of `_fragments` modules don't carry `# Source:` comments — they shouldn't (imports aren't provenance), but verify the executor doesn't add spurious ones.
- **The 4 plugin-side `agents/*.md` files** are NOT edited by this phase — they are re-anchor targets only. Per CONTEXT deferred section "Plugin-side content audit", plugin content is canonical; do not edit it to make the audit pass. If a `source_anchor` references a section that no longer exists, D-04 says restore the content to plugin OR pick a different section OR drop the check — never silently delete the anchor pointer.

## Metadata

**Analog search scope:**
- `scripts/check-brand.sh` (full file)
- `.brand-grep-allow` (first 80 lines)
- `agents/graph-wiki-agent/src/graph_wiki_agent/prompts/` (all .py files, including `_fragments/`)
- `agents/graph-wiki-agent/tests/prompts/test_provenance.py` (full file)
- `packages/eval-harness/src/eval_harness/divergence/` (all .py + rubrics)
- `packages/prompt-sources/agents/{code_reader,synthesizer}.md` (lattice-rebrand audit)
- `packages/workspace-io/src/workspace_io/assets/CLAUDE.md.template` (full file)
- `plugins/graph-wiki/agents/{ingestor,librarian,linter,scanner}.md` (heading inventory)
- `plugins/graph-wiki/skills/graph-wiki/SKILL.md` (heading inventory)
- `.planning/phases/{22,23,24,25}-*/` (prior phase PATTERNS.md / PLAN.md cadence)

**Files scanned:** ~50.
**Pattern extraction date:** 2026-05-21.

**Key analog phases referenced:**
- Phase 18 — CHECK 2 block addition (structural template for any new gate block)
- Phase 21 — `.brand-grep-allow` rationale-comment convention + R-04 self-allowlist
- Phase 23 — plugin-doc ↔ prompt-source mirror invariant (the one this phase deletes); PATTERNS.md table format
- Phase 24 — CHECK 5 block addition (immediate structural template for CHECK 6); path-scope narrowing precedent
- Phase 25 — packages/-tree sweep + brand-gate pattern; hard-cut commit shape

**Key open decision for the planner (surfaced at PATTERNS time, not deferred to execution):**
- **Option A vs Option B for the new provenance header shape** (1-line collapse vs 3-line preserve). PATTERNS.md recommends Option A. Whichever the planner picks must be applied uniformly across all 21+ sites AND drives the `_PROVENANCE_RE` rewrite in test_provenance.py.
- **`CLAUDE.md.template` missing `## Log format` and `## Style` headings** (D-04 audit row). Recommend restoring the sections to the template per D-07 ("the asset IS the canonical source"). Alternative: re-anchor to plugin SKILL.md (which may host equivalent content) or drop the anchor.
