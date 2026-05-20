---
quick_id: 260520-bgd
type: quick
status: planned
created: 2026-05-20
tags: [v1.3-closeout, hygiene, archive]
files_modified:
  - .planning/milestones/v1.3-REQUIREMENTS.md
  - .planning/milestones/v1.3-ROADMAP.md
  - .planning/STATE.md
  - .planning/milestones/v1.3-phases/18-plugin-command-rename/18-CONTEXT.md
  - .planning/milestones/v1.3-phases/20-workspace-manifest-model-config/20-CONTEXT.md
autonomous: true
---

<objective>
Close out three v1.3 post-milestone hygiene items, each as its own atomic commit. v1.3 shipped 2026-05-20 (commit ca9b1fe). The follow-ups are bookkeeping only — no production code changes.

Purpose: Leave the v1.3 archive complete and `audit-open` clean before the next milestone begins.
Output: 3 commits — (1) v1.3 archive files added to git; (2) STATE.md "Quick Tasks Completed" backfilled for k9t + lf1; (3) stale open-questions blocks in Phase 18 + 20 CONTEXT.md marked resolved.
</objective>

<context>
@./CLAUDE.md
@.planning/STATE.md
@.planning/milestones/v1.3-REQUIREMENTS.md
@.planning/milestones/v1.3-ROADMAP.md
@.planning/milestones/v1.3-phases/18-plugin-command-rename/18-CONTEXT.md
@.planning/milestones/v1.3-phases/20-workspace-manifest-model-config/20-CONTEXT.md
@.planning/quick/260519-k9t-preflight-role/260519-k9t-SUMMARY.md
@.planning/quick/260519-lf1-bedrock-audit/260519-lf1-SUMMARY.md

<interfaces>
STATE.md current bookkeeping (lines 115-116 region) already lists k9t and lf1 under the "Items acknowledged at v1.3 close (2026-05-20)" table with category `quick_task`. That row notes the audit-open index marker is stale.

The "Quick Tasks Completed" table referenced in the task description does NOT exist in STATE.md as a separate section. The executor must either:
- (a) Create a new `## Quick Tasks Completed` table (if `audit-open` looks for that heading), OR
- (b) Update the existing `quick_task` rows under "Items acknowledged at v1.3 close (2026-05-20)" to a "completed/recorded" status.

Investigate the SDK scanner FIRST (Task 2 details below) before deciding which form the table needs.

Phase 18 CONTEXT.md `<open_questions>` block: lines ~140-147 (XML-wrapped, three numbered questions about test file rename, reinstall instructions, historical sweep granularity).
Phase 20 CONTEXT.md `## Open questions for the planner` section: lines 46-54 (markdown heading, three numbered questions about RoleConfig field set, --config option, models.toml lifecycle). NOTE: Phase 20 uses a markdown heading, NOT an XML `<open_questions>` wrapper — preserve whichever form each file uses.
</interfaces>
</context>

<tasks>

<task type="auto">
  <name>Task 1: Commit the two untracked v1.3 archive files</name>
  <files>.planning/milestones/v1.3-REQUIREMENTS.md, .planning/milestones/v1.3-ROADMAP.md</files>
  <action>
    Both files are currently untracked (no git history). They are the milestone-snapshot artifacts (REQUIREMENTS + ROADMAP frozen at v1.3 close) that commit ca9b1fe ("chore: archive v1.3 milestone") missed. Prior milestones (v1.0, v1.1, v1.2) all have these snapshot files in `.planning/milestones/` — adding them brings v1.3 into pattern compliance.

    Steps:
    1. Run `git status .planning/milestones/` to confirm both files are untracked and no other unrelated files are staged.
    2. Run `git diff --cached` to confirm nothing else is staged.
    3. `git add .planning/milestones/v1.3-REQUIREMENTS.md .planning/milestones/v1.3-ROADMAP.md` — name the files explicitly; do not use `git add -A`.
    4. Commit with a `docs(v1.3-archive):` scope referencing ca9b1fe. Use a HEREDOC:
       ```
       git commit -m "$(cat <<'EOF'
       docs(v1.3-archive): add REQUIREMENTS + ROADMAP snapshots missed by ca9b1fe

       Completes the v1.3 archive. ca9b1fe archived the milestone but did not
       stage the frozen REQUIREMENTS.md and ROADMAP.md snapshots. Prior milestones
       (v1.0, v1.1, v1.2) all have these files in .planning/milestones/; this
       brings v1.3 into pattern compliance.

       Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
       EOF
       )"
       ```
    5. DO NOT amend ca9b1fe — create a new commit per project git safety rules.
  </action>
  <verify>
    <automated>git status --porcelain .planning/milestones/v1.3-REQUIREMENTS.md .planning/milestones/v1.3-ROADMAP.md | wc -l | grep -q '^0$' && git log --oneline -1 -- .planning/milestones/v1.3-REQUIREMENTS.md | grep -q .</automated>
  </verify>
  <done>Both files tracked; one new commit exists referencing ca9b1fe; `git status .planning/milestones/` shows clean.</done>
</task>

<task type="auto">
  <name>Task 2: Investigate audit-open scanner, then backfill k9t + lf1 in STATE.md</name>
  <files>.planning/STATE.md</files>
  <action>
    `gsd-sdk query audit-open` reports `status: "missing"` for completed quick tasks `260519-k9t-preflight-role` and `260519-lf1-bedrock-audit`, even though both have PLAN.md + SUMMARY.md on disk with `status: complete` in SUMMARY frontmatter. Goal: make `audit-open --raw` return `counts.quick_tasks: 0` via the lowest-risk durable fix — updating STATE.md, the system-of-record.

    Step 1 — Investigate the scanner (READ-ONLY, do not edit any global npm package):
    1. `which gsd-sdk` → resolve symlink (`readlink -f $(which gsd-sdk)` on linux, `realpath` on macOS — both should work; or `ls -la $(which gsd-sdk)`).
    2. From the resolved path, find the `audit-open` handler. Search the package for `audit-open` and `quick_tasks` (e.g. `grep -rn "quick_tasks\\|audit-open" <pkg-root>/dist <pkg-root>/src 2>/dev/null | head -30`).
    3. Identify what determines `status: "missing"` vs `status: "complete"` for a quick task. Specifically look for:
       - Does it look for a `## Quick Tasks Completed` heading in STATE.md?
       - Does it parse a markdown table row referencing the quick_id?
       - Does it read SUMMARY.md frontmatter directly from disk?
    4. Record the finding (one or two lines) — needed for the SUMMARY.md write-up later.

    Step 2 — Apply the STATE.md fix based on the finding:
    - Read current STATE.md to see existing structure. The "Items acknowledged at v1.3 close (2026-05-20)" table on or around lines 110-118 already lists k9t and lf1 under category `quick_task` with a note about the stale index marker — but that is a deferred-items table, not a completed-quick-tasks index.
    - If the scanner looks for a `## Quick Tasks Completed` heading and a table:
      Add a new section to STATE.md (place it near the other quick/phase status tables, before "Deferred Items"):
      ```
      ## Quick Tasks Completed

      | Quick ID | Description | Commit |
      |----------|-------------|--------|
      | 260519-k9t-preflight-role | <one-line description from SUMMARY.md> | <commit hash> |
      | 260519-lf1-bedrock-audit  | <one-line description from SUMMARY.md> | <commit hash> |
      ```
      Get the commit hash for each via `git log --oneline --diff-filter=A -- .planning/quick/260519-k9t-preflight-role/260519-k9t-SUMMARY.md` and similarly for lf1.
    - If the scanner looks for the quick_id in any table cell of STATE.md (less prescriptive), the existing rows on lines 115-116 likely already satisfy it; in that case the issue is elsewhere — proceed to Step 3.
    - If the scanner reads SUMMARY.md frontmatter directly from disk: STATE.md edits will not fix `audit-open`. Document the SDK-side root cause in this quick task's SUMMARY.md as a TODO; do not patch the globally installed package. Still add the `## Quick Tasks Completed` table for human readability — but flag in SUMMARY.md that audit-open will continue to report them missing.

    Step 3 — Verify and decide:
    - Run `gsd-sdk query audit-open --raw` and inspect `counts.quick_tasks` and any per-task entries.
    - If `counts.quick_tasks` is 0 → success.
    - If still > 0 → capture the scanner's actual logic in this plan's SUMMARY.md as a TODO for a future SDK PR. Do NOT edit the globally installed `get-shit-done-cc` package.

    Step 4 — Commit the STATE.md change as its own atomic commit:
    ```
    git add .planning/STATE.md
    git commit -m "$(cat <<'EOF'
    docs(state): backfill k9t + lf1 in Quick Tasks Completed

    Both quick tasks shipped 2026-05-19 but were never recorded in STATE.md's
    completed-quick-tasks index, causing audit-open to report them as missing.
    Adds rows for both with their introducing commit hashes.

    Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
    EOF
    )"
    ```
    If Step 2 also adds findings to this plan's SUMMARY.md noting an SDK-side issue, those go in the SUMMARY (written at quick-task close), not in this commit.

    Constraint reminder: DO NOT edit any file under a global npm install path (`~/.nvm/.../node_modules/get-shit-done-cc/...`). Investigation is read-only.
  </action>
  <verify>
    <automated>gsd-sdk query audit-open --raw 2>/dev/null | grep -E '"quick_tasks"\s*:\s*0' || (echo "audit-open still reports quick_tasks > 0; if SDK-side root cause confirmed in investigation, capture in SUMMARY.md as TODO and treat task as complete" && grep -q "260519-k9t" .planning/STATE.md && grep -q "260519-lf1" .planning/STATE.md)</automated>
  </verify>
  <done>STATE.md has k9t and lf1 recorded in a Quick Tasks Completed index. Either `audit-open --raw` reports `counts.quick_tasks: 0`, OR the SDK-side root cause is documented in this plan's SUMMARY.md as a TODO with the scanner code location noted. One atomic commit touching only STATE.md.</done>
</task>

<task type="auto">
  <name>Task 3: Mark stale open-questions blocks resolved in Phase 18 + 20 CONTEXT.md</name>
  <files>.planning/milestones/v1.3-phases/18-plugin-command-rename/18-CONTEXT.md, .planning/milestones/v1.3-phases/20-workspace-manifest-model-config/20-CONTEXT.md</files>
  <action>
    Both archived CONTEXT.md files have stale open-questions content from planning. The questions were resolved during execution but the markers were never cleared. `audit-open` already reports `context_questions: 0`, so this is purely cosmetic. Principle: preserve history, mark resolved.

    The two files use DIFFERENT formats — preserve whichever form each uses:

    **Phase 18** (`.planning/milestones/v1.3-phases/18-plugin-command-rename/18-CONTEXT.md`):
    Uses XML wrapper tags: `<open_questions> ... </open_questions>` (around lines 140-147). Inside is a `## Open Questions (for the planner to resolve)` heading and 3 numbered questions.

    Replace the body INSIDE the wrapper tags only. Keep the `<open_questions>` and `</open_questions>` tags exactly where they are. New body:
    ```
    <open_questions>
    ## Open Questions

    All open questions resolved during phase execution. See SUMMARY.md for outcomes.

    </open_questions>
    ```

    **Phase 20** (`.planning/milestones/v1.3-phases/20-workspace-manifest-model-config/20-CONTEXT.md`):
    Uses a markdown heading `## Open questions for the planner` (line 46), NOT an XML wrapper. The block ends at the next `## ` heading (`## Out of scope (explicit)` around line 56).

    Replace the body of that section only — keep the `## Open questions for the planner` heading and the next `## Out of scope (explicit)` heading intact. New body for the section:
    ```
    ## Open questions for the planner

    All open questions resolved during phase execution. See SUMMARY.md for outcomes.

    ```
    (Blank line before the next `## Out of scope` heading.)

    DO NOT modify any other section of either CONTEXT.md (no formatting fixes, no frontmatter changes, no adjacent edits).

    Commit as a single atomic commit covering both files:
    ```
    git add .planning/milestones/v1.3-phases/18-plugin-command-rename/18-CONTEXT.md \\
            .planning/milestones/v1.3-phases/20-workspace-manifest-model-config/20-CONTEXT.md
    git commit -m "$(cat <<'EOF'
    docs(v1.3-archive): mark stale open-questions resolved in 18 + 20 CONTEXT

    Both phases resolved their planning-time open questions during execution
    but never cleared the question markers from CONTEXT.md. Replaces the
    stale question bodies with a one-line resolved note pointing at SUMMARY.md.
    Preserves the section wrapper (XML in 18, markdown heading in 20) so any
    future scanner still sees the block as present-and-resolved.

    Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
    EOF
    )"
    ```
  </action>
  <verify>
    <automated>grep -c "All open questions resolved during phase execution" .planning/milestones/v1.3-phases/18-plugin-command-rename/18-CONTEXT.md .planning/milestones/v1.3-phases/20-workspace-manifest-model-config/20-CONTEXT.md | grep -v ':0' | wc -l | grep -q '^2$' && ! grep -q "RoleConfig.*field set\|Test file rename" .planning/milestones/v1.3-phases/18-plugin-command-rename/18-CONTEXT.md .planning/milestones/v1.3-phases/20-workspace-manifest-model-config/20-CONTEXT.md && gsd-sdk query audit-open --raw 2>/dev/null | grep -E '"context_questions"\s*:\s*0'</automated>
  </verify>
  <done>Both CONTEXT.md files have stale question lists replaced with the one-line resolved note. Phase 18 still has its `<open_questions>` XML wrapper. Phase 20 still has its `## Open questions for the planner` markdown heading and the following `## Out of scope (explicit)` heading. `audit-open` still reports `context_questions: 0`. One atomic commit covering both files.</done>
</task>

</tasks>

<verification>
After all 3 tasks complete:
- `git log --oneline -3` shows 3 new commits in order (Task 1 → Task 2 → Task 3), each scoped (`docs(v1.3-archive):`, `docs(state):`, `docs(v1.3-archive):`).
- `git status` is clean (no staged or unstaged changes left over).
- `gsd-sdk query audit-open --raw` reports `counts.quick_tasks: 0` AND `counts.context_questions: 0` (or, if quick_tasks still > 0, the SDK root cause is documented in SUMMARY.md as a TODO).
- The two v1.3 milestone snapshot files are tracked in git.
</verification>

<success_criteria>
- 3 atomic commits land cleanly, each touching only the files in its task.
- `audit-open` `context_questions` count remains 0 (Task 3 must not break it).
- `audit-open` `quick_tasks` count is 0 OR the residual SDK-side root cause is captured in this plan's SUMMARY.md as a TODO for a future SDK PR.
- No edits to any globally installed npm package; investigation in Task 2 is read-only.
</success_criteria>

<output>
Create `.planning/quick/260520-bgd-close-out-v1-3-deferred-items-commit-unt/260520-bgd-SUMMARY.md` when done.

The SUMMARY.md should record:
- The 3 commit hashes.
- The audit-open before/after counts (quick_tasks, context_questions).
- For Task 2: the scanner-investigation finding (one or two lines describing what audit-open actually looks at for quick tasks).
- Any TODOs for a future SDK fix, if applicable.
</output>
