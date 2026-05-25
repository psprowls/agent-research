---
phase: 260521-kxi
plan: 01
type: execute
wave: 1
depends_on: []
files_modified:
  - plugins/graph-wiki/agents/librarian.md
  - plugins/graph-wiki/agents/ingestor.md
  - plugins/graph-wiki/agents/linter.md
  - plugins/graph-wiki/agents/scanner.md
  - plugins/graph-wiki/commands/bootstrap.md
  - plugins/graph-wiki/skills/graph-wiki/README.md
  - plugins/graph-wiki/skills/graph-wiki/SKILL.md
  - plugins/graph-wiki/skills/graph-wiki/references/wiki-schema.md
  - plugins/graph-wiki/skills/graph-wiki/references/scan-workflow.md
  - plugins/graph-wiki/skills/graph-wiki/references/cross-tool-setup.md
  - plugins/graph-wiki/skills/graph-wiki/references/query-workflow.md
autonomous: true
requirements:
  - QUICK-260521-kxi

must_haves:
  truths:
    - "Every bundled-script invocation in graph-wiki plugin docs runs via the uv workspace, so vault_io resolves on a fresh install"
    - "The SKILL.md tool-table preamble correctly describes the shim model (imports the in-workspace vault_io package) instead of falsely claiming standard-library-only"
    - "Shim scripts under plugins/graph-wiki/skills/graph-wiki/scripts/ are untouched"
  artifacts:
    - path: "plugins/graph-wiki/skills/graph-wiki/SKILL.md"
      provides: "Quick-start invocation and tool-table preamble using uv run --project"
      contains: "uv run --project \"$AGENT_RESEARCH_ROOT\" python"
    - path: "plugins/graph-wiki/agents/scanner.md"
      provides: "Scanner agent invocations updated"
      contains: "uv run --project \"$AGENT_RESEARCH_ROOT\" python"
    - path: "plugins/graph-wiki/skills/graph-wiki/references/scan-workflow.md"
      provides: "Scan workflow reference doc invocations updated"
      contains: "uv run --project \"$AGENT_RESEARCH_ROOT\" python"
  key_links:
    - from: "all 11 plugin doc files"
      to: "shim scripts under plugins/graph-wiki/skills/graph-wiki/scripts/"
      via: "uv run --project \"$AGENT_RESEARCH_ROOT\" python ${CLAUDE_PLUGIN_ROOT}/skills/graph-wiki/scripts/<tool>.py"
      pattern: "uv run --project \"\\$AGENT_RESEARCH_ROOT\" python \\$\\{CLAUDE_PLUGIN_ROOT\\}/skills/graph-wiki/scripts/"
---

<objective>
Fix every documented bundled-script invocation across the `graph-wiki` plugin so it runs through the `uv` workspace, matching the actual shim model the plugin's own CLAUDE.md (line 23) already mandates: `uv run --project "$AGENT_RESEARCH_ROOT" python ${CLAUDE_PLUGIN_ROOT}/skills/graph-wiki/scripts/<tool>.py …`. Bare `python` fails immediately with `ModuleNotFoundError: No module named 'vault_io'` because the shims import the workspace-only `vault_io` package.

Purpose: A user following any plugin doc verbatim should get a working invocation. Today every documented call breaks.

Output: 11 documentation files updated; one stale prose sentence in SKILL.md corrected; zero changes to shim scripts or any other behavior.
</objective>

<execution_context>
@$HOME/.claude/get-shit-done/workflows/execute-plan.md
@$HOME/.claude/get-shit-done/templates/summary.md
</execution_context>

<context>
@./CLAUDE.md
@plugins/graph-wiki/CLAUDE.md
@.planning/STATE.md

<!-- Why uv run --project "$AGENT_RESEARCH_ROOT" (not bare `uv run python`): -->
<!-- plugins/graph-wiki/CLAUDE.md line 23 (the plugin's own iron rule): -->
<!--   "shims reference vault_io via the uv workspace -->
<!--    (`uv run --project "$AGENT_RESEARCH_ROOT"`), so installed users need -->
<!--    AGENT_RESEARCH_ROOT set and `uv` installed". -->
<!-- The --project flag is required because users running the slash command -->
<!-- have an arbitrary cwd; bare `uv run` would search upward from cwd for a -->
<!-- pyproject.toml and fail (or pick the wrong workspace). AGENT_RESEARCH_ROOT -->
<!-- is already documented as a prerequisite in README.md line 18. -->

<interfaces>
<!-- Shim shape (do NOT edit — confirmed via `Read` of detect_containers.py): -->
<!-- Every file in plugins/graph-wiki/skills/graph-wiki/scripts/*.py is: -->
<!--   #!/usr/bin/env python3 -->
<!--   """Plugin shim for <tool> — delegates to vault_io.<tool>.""" -->
<!--   import sys -->
<!--   from vault_io.<tool> import main -->
<!--   if __name__ == "__main__": -->
<!--       main() -->
<!-- Because vault_io is a workspace member at packages/vault-io/, it is only -->
<!-- importable inside the uv-managed venv. -->
</interfaces>

<!-- Pre-enumerated grep results (run from repo root): -->
<!-- 26 invocation lines across 11 files. The executor MUST re-run grep first -->
<!-- to confirm the set hasn't drifted, then rewrite each match in place. -->
<!-- -->
<!-- plugins/graph-wiki/agents/librarian.md:52 -->
<!-- plugins/graph-wiki/agents/ingestor.md:30, 81, 86 -->
<!-- plugins/graph-wiki/agents/linter.md:28, 29, 94 -->
<!-- plugins/graph-wiki/agents/scanner.md:30, 87, 92, 97 -->
<!-- plugins/graph-wiki/commands/bootstrap.md:35  (line 83 is a *path* in a -->
<!--   bullet, not an invocation — leave it alone) -->
<!-- plugins/graph-wiki/skills/graph-wiki/README.md:34 -->
<!-- plugins/graph-wiki/skills/graph-wiki/SKILL.md:85 -->
<!-- plugins/graph-wiki/skills/graph-wiki/references/wiki-schema.md:497 -->
<!-- plugins/graph-wiki/skills/graph-wiki/references/scan-workflow.md:30, 181, 187 -->
<!-- plugins/graph-wiki/skills/graph-wiki/references/cross-tool-setup.md:97, 98, 104, 105, 106 -->
<!-- plugins/graph-wiki/skills/graph-wiki/references/query-workflow.md:37, 70, 81 -->
</context>

<tasks>

<task type="auto">
  <name>Task 1: Replace bare-python invocations with uv-workspace invocations across all 11 plugin doc files</name>
  <files>
    plugins/graph-wiki/agents/librarian.md,
    plugins/graph-wiki/agents/ingestor.md,
    plugins/graph-wiki/agents/linter.md,
    plugins/graph-wiki/agents/scanner.md,
    plugins/graph-wiki/commands/bootstrap.md,
    plugins/graph-wiki/skills/graph-wiki/README.md,
    plugins/graph-wiki/skills/graph-wiki/SKILL.md,
    plugins/graph-wiki/skills/graph-wiki/references/wiki-schema.md,
    plugins/graph-wiki/skills/graph-wiki/references/scan-workflow.md,
    plugins/graph-wiki/skills/graph-wiki/references/cross-tool-setup.md,
    plugins/graph-wiki/skills/graph-wiki/references/query-workflow.md
  </files>
  <action>
    First, re-run grep from repo root to enumerate the authoritative set of lines (don't trust the static list — trust grep):

      grep -rn 'python \${CLAUDE_PLUGIN_ROOT}/skills/graph-wiki/scripts/' plugins/graph-wiki/

    For every line that grep returns, rewrite the invocation token in place by inserting `uv run --project "$AGENT_RESEARCH_ROOT" ` immediately before `python` and leaving the rest of the line (path, args, trailing backslash, surrounding prose, indentation, code-fence membership) byte-identical.

    Concretely, the transformation is:

      python ${CLAUDE_PLUGIN_ROOT}/skills/graph-wiki/scripts/<tool>.py …
        →
      uv run --project "$AGENT_RESEARCH_ROOT" python ${CLAUDE_PLUGIN_ROOT}/skills/graph-wiki/scripts/<tool>.py …

    Rationale for the exact form (per plugins/graph-wiki/CLAUDE.md line 23, the plugin's own iron rule for distribution): the `--project "$AGENT_RESEARCH_ROOT"` argument is required so the call resolves the uv workspace regardless of the user's cwd. Plain `uv run python …` would search upward from cwd and either fail or bind to the wrong workspace. README.md line 18 already documents `AGENT_RESEARCH_ROOT` as a prerequisite, so no new env var is being introduced — only consistently used.

    Special cases to be aware of (verify against grep, do not skip):

    - `plugins/graph-wiki/skills/graph-wiki/references/cross-tool-setup.md` lines 104-106 contain `alias` definitions:
        alias graph-wiki-scan='python ${CLAUDE_PLUGIN_ROOT}/…/scan_monorepo.py'
      Rewrite the aliased command body the same way:
        alias graph-wiki-scan='uv run --project "$AGENT_RESEARCH_ROOT" python ${CLAUDE_PLUGIN_ROOT}/…/scan_monorepo.py'
      Keep the single quotes; `$AGENT_RESEARCH_ROOT` and `${CLAUDE_PLUGIN_ROOT}` will both expand at command-execution time because Claude Code expands `${CLAUDE_PLUGIN_ROOT}` before the shell sees the line and the shell expands `$AGENT_RESEARCH_ROOT` inside double quotes within the single-quoted alias body when the alias is invoked. (If unsure, mirror the form already used elsewhere in the file.)

    - `plugins/graph-wiki/skills/graph-wiki/references/query-workflow.md` line 81 is inline prose inside backticks:
        - **Marp slide deck** — via `python ${CLAUDE_PLUGIN_ROOT}/skills/graph-wiki/scripts/export_marp.py` on the synthesis page
      Rewrite the backtick contents only:
        - **Marp slide deck** — via `uv run --project "$AGENT_RESEARCH_ROOT" python ${CLAUDE_PLUGIN_ROOT}/skills/graph-wiki/scripts/export_marp.py` on the synthesis page

    - `plugins/graph-wiki/skills/graph-wiki/references/wiki-schema.md` line 497 is also inline-backtick prose; rewrite the backtick contents only.

    - `plugins/graph-wiki/commands/bootstrap.md` line 83 references a script *path* in a bullet, NOT an invocation. Leave it untouched. (Only line 35 in that file is an invocation.)

    Do NOT touch:
      - Any `.py` file under `plugins/graph-wiki/skills/graph-wiki/scripts/` (per plugin CLAUDE.md: real implementation lives in `packages/vault-io/`; shims are the contract).
      - Surrounding sentences, headings, list bullets, or code-fence languages.
      - The `_config.py` backend-selection logic.
      - Any file outside the 11 enumerated above.

    After all rewrites, re-run grep to confirm zero remaining bare-`python ${CLAUDE_PLUGIN_ROOT}/skills/graph-wiki/scripts/` matches.
  </action>
  <verify>
    <automated>
test "$(grep -rn 'python \${CLAUDE_PLUGIN_ROOT}/skills/graph-wiki/scripts/' plugins/graph-wiki/ | grep -v 'uv run --project' | grep -v 'commands/bootstrap.md:83')" = ""
    </automated>
  </verify>
  <done>
    Every invocation match returned by `grep -rn 'python \${CLAUDE_PLUGIN_ROOT}/skills/graph-wiki/scripts/' plugins/graph-wiki/` is now prefixed by `uv run --project "$AGENT_RESEARCH_ROOT" `, except `commands/bootstrap.md:83` which is a path reference (not an invocation) and is intentionally left alone. No shim script under `plugins/graph-wiki/skills/graph-wiki/scripts/` was modified.
  </done>
</task>

<task type="auto">
  <name>Task 2: Correct the stale "Standard library only" claim in SKILL.md Python-tools section</name>
  <files>plugins/graph-wiki/skills/graph-wiki/SKILL.md</files>
  <action>
    On line ~123 (under the `## Python tools (`scripts/`)` heading), the current text reads:

      Standard library only (via vault_io). Run with `python scripts/<tool>.py --help`.

    This is doubly wrong: (1) the shims aren't standard-library-only — they import the in-workspace `vault_io` package, which itself can have non-stdlib deps; (2) bare `python scripts/<tool>.py` fails for the same reason this whole plan exists.

    Replace that single sentence with prose that accurately describes the shim model and the correct invocation, matching the file's existing terse style. Use this replacement verbatim:

      Each script is a thin shim that imports `main()` from the in-workspace `vault_io` package, so invocations must go through the uv workspace. Run with `uv run --project "$AGENT_RESEARCH_ROOT" python ${CLAUDE_PLUGIN_ROOT}/skills/graph-wiki/scripts/<tool>.py --help`.

    Do not touch the table of scripts that follows, or any other line in SKILL.md beyond what Task 1 already handled.
  </action>
  <verify>
    <automated>
grep -q 'Each script is a thin shim that imports `main()` from the in-workspace `vault_io` package' plugins/graph-wiki/skills/graph-wiki/SKILL.md \
  && ! grep -q 'Standard library only (via vault_io)' plugins/graph-wiki/skills/graph-wiki/SKILL.md
    </automated>
  </verify>
  <done>
    The "Standard library only (via vault_io). Run with `python scripts/<tool>.py --help`." sentence is gone. The replacement sentence accurately describes the shim model and shows the `uv run --project "$AGENT_RESEARCH_ROOT" python …` invocation. The script table directly below is unchanged.
  </done>
</task>

</tasks>

<verification>
1. Re-run the enumeration grep and confirm every remaining match is prefixed with `uv run --project "$AGENT_RESEARCH_ROOT"` (except the one path-reference bullet in `commands/bootstrap.md:83`):

       grep -rn 'python \${CLAUDE_PLUGIN_ROOT}/skills/graph-wiki/scripts/' plugins/graph-wiki/ \
         | grep -v 'uv run --project' \
         | grep -v 'commands/bootstrap.md:83'

   Expected output: empty.

2. Confirm shims are untouched:

       git diff --stat plugins/graph-wiki/skills/graph-wiki/scripts/

   Expected output: empty.

3. Spot-check one invocation actually works end-to-end (no behavior change is being introduced, but the docs should now match reality):

       cd /tmp \
         && AGENT_RESEARCH_ROOT=/Users/pat/Personal/agent-research \
            CLAUDE_PLUGIN_ROOT=/Users/pat/Personal/agent-research/plugins/graph-wiki \
            bash -c 'uv run --project "$AGENT_RESEARCH_ROOT" python ${CLAUDE_PLUGIN_ROOT}/skills/graph-wiki/scripts/detect_containers.py --help'

   Expected output: argparse `--help` text from `vault_io.detect_containers`. No `ModuleNotFoundError`.
</verification>

<success_criteria>
- `grep -rn 'python \${CLAUDE_PLUGIN_ROOT}/skills/graph-wiki/scripts/' plugins/graph-wiki/` returns only lines prefixed with `uv run --project "$AGENT_RESEARCH_ROOT"`, plus the single path-reference bullet at `commands/bootstrap.md:83`.
- The stale "Standard library only (via vault_io). Run with `python scripts/<tool>.py --help`." sentence in `SKILL.md` is replaced with the shim-aware version that documents `uv run --project "$AGENT_RESEARCH_ROOT" python …`.
- `git diff --stat plugins/graph-wiki/skills/graph-wiki/scripts/` is empty.
- One representative `uv run --project "$AGENT_RESEARCH_ROOT" python ${CLAUDE_PLUGIN_ROOT}/skills/graph-wiki/scripts/detect_containers.py --help` invocation, run from `/tmp`, prints help text (no `ModuleNotFoundError`).
</success_criteria>

<output>
Create `.planning/quick/260521-kxi-fix-graph-wiki-plugin-docs-use-uv-run-py/260521-kxi-01-SUMMARY.md` when done.
</output>
