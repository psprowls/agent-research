# Wikilink Base — Part 2: Flip the Producers to the Wiki Root

**Status:** design (approved 2026-06-05)
**Predecessor:** Part 1 — `docs/superpowers/plans/2026-06-05-wikilink-base-wiki-root.md` (landed on this branch: 8 commits `89cb599c…0dc7a675`, plus the cross-package fixup `c48f9c4e`).
**Branch:** `worktree-wikilink-base-wiki-root` (Part 1 + Part 2 land together; do not merge until Part 2 is complete).

---

## Goal

Make every **producer** of vault wikilinks emit the **wiki-root-relative** form (`[[concepts/foo]]`, `[[entities/bar]]`, `[[work/baz]]`) instead of the legacy **workspace-root-relative** form (`[[wiki/concepts/foo]]`). This closes the producer/consumer mismatch that Part 1 opened: Part 1 rebased both linters (the *consumers*) to walk the wiki root and key pages wiki-relative, but the *producers* still emit `[[wiki/…]]`, which the rebased linter now flags as broken on every freshly-generated index.

Secondary goal (Tier A, see below): correct the **dead-category placeholders** in templates and prompts (`[[packages/…]]`, `[[domains/…]]`, `[[dependencies/…]]`) to the current `entities/` layout, since they are adjacent to the lines we are already editing and name directories the system no longer produces.

## Background — why this is needed

- **The wiki root is the intended single base.** The user is deliberately reversing the legacy "workspace-root wikilink form" decision (recorded as ADR-0011/ADR-0015 in the *synthetic* `round-trip-vault` test fixture — that fixture describes a fictional "lattice" project and is **not** an authoritative project decision; it is stale context from an old experimental workspace). Obsidian will be opened at `<workspace>/wiki/` going forward.
- **Part 1 already rebased the linters.** `wiki_io/lint_wiki.py:scan` and `graph_wiki_core/commands/lint.py:_mechanical_pass` now `wiki.rglob(...)` and key pages `relative_to(wiki)`. They resolve every wiki-rooted form:
  - exact: `[[concepts/foo]]` → key `concepts/foo`
  - folder-shorthand: `[[entities/foo]]` → `entities/foo/foo.md`
  - stem-shorthand: `[[foo]]` (no `/`) → via the `stems` dict
  - `[[work/…]]` already matched before and after Part 1
  - **only `[[wiki/…]]` is now broken** (the prefix matches no key, is not folder-shorthand, is not a bare stem).
- Verified end-to-end: rendering an index the real way and linting it yields `BROKEN LINKS: [('index', 'wiki/concepts/foo')]` and `ORPHANS: ['concepts/foo']`.
- **Rebuild does not fix it.** Per the no-migration policy the user rebuilds the vault, but a freshly-rebuilt vault's regenerated index immediately contains `[[wiki/…]]` links the linter flags — so the producer side must change.

## Settled decisions (from brainstorming)

1. **Direction is correct:** wiki-root base everywhere. ADR-0011/0015 are stale fixture context, not constraints.
2. **Scope = full L1–L5** producer migration (below).
3. **Obsidian vault-root move = note-only.** Nothing in the codebase sets Obsidian's root; the plan documents "open Obsidian at `<workspace>/wiki/`" and updates docs/templates that describe the vault root. No "move" code.
4. **Prompt examples:** fix both the `wiki/` prefix *and* the stale categories → real wiki-rooted forms on the `entities/` layout.
5. **Execution = approach B + C:** phased by subsystem (each phase keeps its suite green), and consolidate the duplicate link builders into one shared helper while we are touching every emission site.
6. **Fixtures:** mechanically sweep the `[[wiki/` prefix; **rewrite** the two self-referential fixture docs (see Wrinkles).
7. **Staleness Tier A in scope; Tier B out.** Fix dead-category placeholders in templates/prompts (Tier A). Do **not** migrate the test-fixture *layout* from container-folders to `entities/` (Tier B) — that is a separate later effort with its own test-intent questions, and Part 2 does not need it (the fixtures are internally self-consistent in their old layout, so the prefix sweep keeps their tests green).

## Target state

**Canonical link forms after Part 2** (all already resolved by the Part-1 linter):

| Target | Canonical form | Was |
|---|---|---|
| Wiki page (curated) | `[[concepts/foo]]`, `[[adrs/0001-x]]`, `[[sources/…]]`, `[[architecture/…]]` | `[[wiki/concepts/foo]]` |
| Entity page | `[[entities/<slug>]]` | `[[wiki/packages/foo/foo]]`, `[[wiki/entities/<slug>]]` |
| Work item | `[[work/<slug>]]` | unchanged |
| Folder shorthand | `[[entities/foo]]` → `entities/foo/foo.md` | unchanged semantics, no `wiki/` |
| Bare stem | `[[foo]]` | unchanged |
| Aliased | `[[concepts/foo|Display]]` | `[[wiki/concepts/foo|Display]]` |

**The flip rule (precise):** strip exactly one leading `wiki/` segment from each wikilink **target**. Never touch: `[[work/…]]` targets, bare stems (`[[foo]]`), the alias on the right of `|`, or `` `path:line` `` code references. A safe rewrite is `[[wiki/` → `[[` (and the f-string emitters drop the `wiki/` prefix at source).

**Tier A taxonomy mapping** (dead category → current): `packages/<x>` → `entities/<x-slug>`, `domains/<x>` → `entities/<x-slug>`, `dependencies/<x>` → `entities/<x-slug>`, `apps/<x>` → `entities/<x-slug>`, `agents/<x>` → `entities/<x-slug>`. Live categories unchanged: `concepts/`, `adrs/`, `sources/`, `architecture/`, `proposals/`, `entities/`, `work/`. (The exact entity slug form is `entity_writer.short_filename(...)`; placeholder text in templates should read `<slug>` / `<prefix>_<name>` to match the already-migrated `source.md`/`entity-*.md` templates — confirm against `entity_writer.py` during planning.)

## Architecture — the shared link helper (approach C)

Today there are **two byte-identical** `_entry_link` functions plus a third entity-specific builder, each hardcoding the prefix:
- `wiki_io/update_index.py::_entry_link` (`:175`)
- `wiki_io/index_generator.py::_entry_link` (`:456`)
- `wiki_io/index_generator.py::_entity_wikilink` (`:572` — `f"[[wiki/entities/{stem}|{text}]]"`)

Introduce **one** helper — proposed `wiki_io/wikilinks.py::vault_wikilink(rel_path: str, text: str | None = None) -> str` — that emits `[[<rel_path>]]` or `[[<rel_path>|<text>]]` with no prefix, normalising a trailing `.md` and forbidding a `wiki/` prefix being passed in. Route all three sites (and the index sub-link emitter at `update_index.py:221`) through it; delete the duplicates. This removes the duplication the Part-1 final review flagged and gives one source of truth for link form going forward.

(Justified DRY on code we are editing anyway; not a speculative abstraction. Keep it in `wiki-io` — both modules already live there.)

## Scope inventory by layer

> Line numbers are as of branch HEAD `0dc7a675`. Re-grep `\[\[wiki/`, `f"wiki/`, and `f"\[\[wiki/` across `packages/*/src` at execution time — the green-gate (a generated-vault lint with zero broken links) is the backstop for any missed emitter.

**L1 — deterministic generators + templates** (the core):
- `wiki_io/update_index.py` — `_entry_link` (`:175`), sub-index `more_links` (`:221`); docstrings/comments still describing the prefix rationale.
- `wiki_io/index_generator.py` — `_entry_link` (`:456`), `_entity_wikilink` (`:572`), docstring (`:554`).
- `wiki_io/assets/page-templates/index.md` (`:18`, `[[wiki/<path>|<Title>]]`). **Note:** the other page-templates are already wiki-rooted in *form* (`[[concepts/…]]`, `[[entities/…]]`); their only issue is Tier-A dead categories.

**L2 — LLM prompts** (flip prefix **and** fix categories to real layout):
- `graph_wiki_core/prompts/synthesizer.py` (`:11`, `:17`) and its source `prompts/sources/synthesizer.md` (`:3`, `:33`, `:41`, `:54`, `:60`).
- `graph_wiki_core/commands/query.py` (`:633`, `:648`).
- `graph_wiki_core/prompts/project_context.py` (has `[[wiki/…]]`).

**L3 — agent templates / docs:**
- `wiki_io/assets/CLAUDE.md.template`, `AGENTS.md.template`, `cursorrules.template`, `index.md.template`, `log.md.template`.
- `workspace_io/assets/CLAUDE.md.template`.
- These instruct agents to author `[[wiki/…]]` and the forbidden `[[../work/…]]`; update to `[[concepts/…]]`/`[[work/…]]` and document the wiki-root vault base (Obsidian-at-wiki-root note).

**L4 — misc emitters:**
- `wiki_io/graph_analyzer.py` (`:86`, a comment).
- `eval_harness/divergence/librarian.py` (eval surface).

**L5 — fixtures + snapshots** (keep all suites green):
- ~134 fixture pages under `wiki_io/tests/fixtures/{round-trip-vault,edge-case-vault,single-package-vault}` and `eval_harness/tests/fixtures/post-rebrand-vault` — mechanical `[[wiki/` → `[[` sweep (preserve work/stems/aliases). The fixtures stay in their old container-folder layout (Tier B out of scope); the sweep keeps them internally self-consistent and the lint/round-trip/eval tests green.
- `.ambr` snapshots: `graph_wiki_core/tests/prompts/__snapshots__/{test_prompt_snapshots,test_project_context}.ambr` and any others that capture rendered links — regenerate via `--snapshot-update`, then **diff to confirm only link prefixes changed**.
- Test `.py` files asserting the literal `wiki/` form (update assertions): `wiki_io/tests/{test_index_generator,test_entity_writer,test_wikilink_predicate,test_lint_scanner_heading,test_bootstrap_e2e_no_broken_links}.py`; `graph_wiki_core/tests/unit/{test_commands_lint,test_query_result}.py`, `graph_wiki_core/tests/commands/test_lint_parity.py`, `graph_wiki_core/tests/prompts/test_provenance.py`; `graph_io/tests/test_sync_wiki.py`, `graph_wiki_cli/tests/graph_cli/test_cli_sync_wiki.py`; `eval_harness/tests/test_divergence_checks.py`.

## Wrinkles (resolved)

1. **Self-referential fixture docs.** `round-trip-vault/adrs/0015-workspace-root-wikilink-form.md` and `round-trip-vault/sources/2026-05-workspace-relative-wikilinks-linter-and-content-rewrite.md` are *about* the old form; a blind link-sweep makes their prose self-contradictory. **Resolution:** rewrite these two fixture pages to describe the new wiki-root convention (keep them as coherent fixture content), rather than sweeping links inside prose that argues for the opposite.
2. **Obsidian vault-root.** No code move; documented manual step + doc/template wording updates (decision 3).
3. **`graph_io/sync_wiki.py`** references legacy `packages/`/`domains/` dirs. It is the only remaining consumer of the old container layout (per Part-1 review) and is **Tier B territory** — out of scope here; note it for the Tier-B effort. Only flip a `wiki/` *link* form in it if one exists in emitted output (re-grep); do not migrate its layout assumptions.

## Phased plan structure (approach B)

Each phase ends green for the affected package(s). The writing-plans step will turn these into concrete tasks.

- **Phase 1 — link helper + generators.** Add `wikilinks.vault_wikilink`; route `update_index` + `index_generator` (both `_entry_link`s, `_entity_wikilink`, sub-index) through it; delete duplicates; update their direct unit tests + snapshots. Green: `wiki-io` generator/entity unit tests.
- **Phase 2 — templates + e2e.** Flip `page-templates/index.md` prefix; Tier-A category fixes in page-templates; update `test_bootstrap_e2e_no_broken_links`. Green: the e2e zero-broken-links test on a freshly bootstrapped + rendered vault.
- **Phase 3 — fixtures + snapshots.** Sweep the 4 fixture vaults' `[[wiki/` prefixes; rewrite the two self-referential docs; regenerate `.ambr`; update remaining `wiki/`-asserting tests. Green: round-trip / eval / lint-parity / sync-wiki suites across `wiki-io`, `graph-wiki-core`, `graph-io`, `eval-harness`.
- **Phase 4 — prompts + agent templates + docs.** Flip + Tier-A categories in L2 prompts and L3 templates; L4 misc; Obsidian-at-wiki-root wording. Green: prompt snapshots + provenance tests.

## Verification

- **SSOT-style guard:** after Phase 4, `grep -rn '\[\[wiki/\|f"wiki/\|f"\[\[wiki/' packages/*/src` returns **zero** emission hits (prose mentioning the old form in a deliberate historical note is acceptable only if it cannot reach generated output).
- **Generated-vault no-broken-links:** render an index + bootstrap+render container overviews + lint → `broken_links == []`, `orphans` contains no real page (the Part-1 repro, now expected clean).
- **Per-package suites green:** `uv run --package {workspace-io,wiki-io} pytest`; `uv run --package {graph-wiki-core,graph-io,graph-wiki-cli,eval-harness} pytest -m "not integration"`.
- **ruff no-new-errors** on every touched src file (compare counts vs branch base, per Part-1 convention; never run `ruff --fix`).
- **Snapshot diffs** reviewed to confirm only link prefixes/categories changed.

## Out of scope / follow-ups

- **Tier B — fixture-layout migration** (container-folder → `entities/`), including `graph_io/sync_wiki.py`'s layout assumptions. Its own spec; needs a decision on whether old-layout support is retained and whether fixtures should be regenerated from a real scan.
- **Real workspace vault content** — user rebuilds (no-migration policy); not on disk currently.
- **Obsidian `.obsidian/` config** — manual user action.

## Risks

- **Missed emitter →** a regenerated vault still shows broken links. Mitigated by the generated-vault green-gate (not just grep).
- **Over-aggressive fixture sweep** touching `[[work/…]]`/stems/aliases or prose. Mitigated by the precise rule (strip leading `wiki/` only) + snapshot/diff review + the two explicit rewrites.
- **Tier-A entity-slug form mismatch** (placeholder text not matching `short_filename`). Mitigated by confirming against `entity_writer.py` during planning and matching already-migrated templates.
