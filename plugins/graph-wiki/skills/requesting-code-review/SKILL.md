---
name: requesting-code-review
description: Use when completing tasks, implementing major features, or before merging to verify work meets requirements
---

# Requesting Code Review

Dispatch a code reviewer subagent to catch issues before they cascade. The reviewer gets precisely crafted context for evaluation — never your session's history. This keeps the reviewer focused on the work product, not your thought process, and preserves your own context for continued work.

**Core principle:** Review early, review often.

## When to Request Review

**Mandatory:**
- After each task in subagent-driven development
- After completing major feature
- Before merge to main

**Optional but valuable:**
- When stuck (fresh perspective)
- Before refactoring (baseline check)
- After fixing complex bug

## How to Request

**1. Get git SHAs:**
```bash
BASE_SHA=$(git rev-parse HEAD~1)  # or origin/main
HEAD_SHA=$(git rev-parse HEAD)
```

**2. Recall review-time guidance (diff-scoped):**

The reviewer holds the strongest recall signal — the changed paths. Recall
review-role guidance against them and assemble it into a bundle:

```bash
changed=$(git diff --name-only "$BASE_SHA".."$HEAD_SHA")
# slug = work-item slug when invoked from the pipeline; otherwise a stable fallback.
slug="${WORK_ITEM_SLUG:-review-$(git rev-parse --short "$HEAD_SHA")}"
bundle="<workspace>/raw/guidance/${slug}-review.md"
gw guidance suggest --role review --path $changed --file "$bundle" --assemble --json
```

(If `gw` is not on PATH: `uv run --package graph-wiki-cli gw guidance suggest …`.)

- If the JSON shows ranked guidance, set the reviewer template's `{REVIEW_GUIDANCE}`
  placeholder to a `## Review guidance` block pointing at the bundle:

  ```
  ## Review guidance
  Diff-scoped, review-role guidance assembled at: raw/guidance/<slug>-review.md
  Read it before reviewing.
  ```

- If recall returns no ranked pages (or no bundle was written), set
  `{REVIEW_GUIDANCE}` to empty — omit the block entirely.
- Surface any `guidance_warnings` from the JSON as plain notes; they are not blockers.

**3. Dispatch code reviewer subagent:**

Use Task tool with `general-purpose` type, fill template at `code-reviewer.md`

**Placeholders:**
- `{DESCRIPTION}` - Brief summary of what you built
- `{PLAN_OR_REQUIREMENTS}` - What it should do
- `{BASE_SHA}` - Starting commit
- `{HEAD_SHA}` - Ending commit
- `{REVIEW_GUIDANCE}` - Diff-scoped review guidance block (or empty if none) — see step 2

**4. Act on feedback:**
- Fix Critical issues immediately
- Fix Important issues before proceeding
- Note Minor issues for later
- Push back if reviewer is wrong (with reasoning)

## Example

```
[Just completed Task 2: Add verification function]

You: Let me request code review before proceeding.

BASE_SHA=$(git log --oneline | grep "Task 1" | head -1 | awk '{print $1}')
HEAD_SHA=$(git rev-parse HEAD)

[Dispatch code reviewer subagent]
  DESCRIPTION: Added verifyIndex() and repairIndex() with 4 issue types
  PLAN_OR_REQUIREMENTS: Task 2 from <workspace>/raw/plans/deployment-plan.md
  BASE_SHA: a7981ec
  HEAD_SHA: 3df7661

[Subagent returns]:
  Strengths: Clean architecture, real tests
  Issues:
    Important: Missing progress indicators
    Minor: Magic number (100) for reporting interval
  Assessment: Ready to proceed

You: [Fix progress indicators]
[Continue to Task 3]
```

## Integration with Workflows

**Subagent-Driven Development:**
- Review after EACH task
- Catch issues before they compound
- Fix before moving to next task

**Executing Plans:**
- Review after each task or at natural checkpoints
- Get feedback, apply, continue

**Ad-Hoc Development:**
- Review before merge
- Review when stuck

## Red Flags

**Never:**
- Skip review because "it's simple"
- Ignore Critical issues
- Proceed with unfixed Important issues
- Argue with valid technical feedback

**If reviewer wrong:**
- Push back with technical reasoning
- Show code/tests that prove it works
- Request clarification

See template at: requesting-code-review/code-reviewer.md
