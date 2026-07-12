---
name: using-git-worktrees
description: Use when starting feature work that needs isolation from current workspace or before executing implementation plans - ensures an isolated workspace exists via native tools or git worktree fallback
---

# Using Git Worktrees — the Code-Change Gate

## Overview

This skill is the **Code-Change Gate**: the single checkpoint every code-writing path runs before any Write/Edit. It enforces two rules, in order — first that writing code is *authorized*, then that the change is *isolated* in its own worktree. Prefer your platform's native worktree tools; fall back to manual git worktrees only when no native tool is available.

**Core principle:** No code without a direct implement directive. Every code change happens in an isolated worktree on an inferred branch — the main checkout is used only when the user explicitly says so. Detect existing isolation first, then native tools, then git. Never fight the harness.

**Announce at start:** "I'm using the using-git-worktrees skill as the Code-Change Gate."

## Step 0: The Code-Change Gate

Run these two checks in order, **before creating anything or writing any code.**

### Part 1 — Authorization (REQUIRED)

Confirm the user has given a **direct implement directive** — an explicit instruction to write code now. Examples that satisfy it:

- "implement this", "make the change", "write the code", "fix it in code"
- "execute the plan", "start building", "go ahead and implement it"
- selecting an execution option from a `writing-plans` Execution Handoff

What does **NOT** satisfy it:

- Approving or praising a design, spec, or plan ("looks good", "ship it", "I like this")
- Asking a question, or asking you to investigate, analyze, or explain
- Silence, or ambiguous enthusiasm

**If there is no direct implement directive → STOP.** Do not create a worktree. Do not Write or Edit code. Stay read-only / in planning and ask the user whether they want you to implement. Approving a design or plan is not, by itself, authorization.

**If authorized → continue to Part 2.**

### Part 2 — Isolation (REQUIRED)

First detect whether you are already isolated.

```bash
GIT_DIR=$(cd "$(git rev-parse --git-dir)" 2>/dev/null && pwd -P)
GIT_COMMON=$(cd "$(git rev-parse --git-common-dir)" 2>/dev/null && pwd -P)
BRANCH=$(git branch --show-current)
```

**Submodule guard:** `GIT_DIR != GIT_COMMON` is also true inside git submodules. Before concluding "already in a worktree," verify you are not in a submodule:

```bash
# If this returns a path, you're in a submodule, not a worktree — treat as normal repo
git rev-parse --show-superproject-working-tree 2>/dev/null
```

**If `GIT_DIR != GIT_COMMON` (and not a submodule):** You are already in a linked worktree. Skip to Step 3 (Project Setup). Do NOT create another worktree.

Report with branch state:
- On a branch: "Already in isolated workspace at `<path>` on branch `<name>`."
- Detached HEAD: "Already in isolated workspace at `<path>` (detached HEAD, externally managed). Branch creation needed at finish time."

**If `GIT_DIR == GIT_COMMON` (or in a submodule):** You are in the main checkout. **Creating an isolated worktree is required** — proceed to Step 1. Do not ask for consent.

**The only exception:** the user has explicitly told you to work in the main worktree (e.g. "just work on the current branch", "don't make a worktree", "edit in place"). In that case work in place, say so — "Working in the main checkout at your request on branch `<name>`." — and skip to Step 3.

## Step 1: Create Isolated Workspace

### Determine the branch name

Infer the branch from the work — no per-time prompt. Pick the prefix that matches this repo's convention (`feat/` for a feature, `fix/` for a bugfix; `docs/`, `refactor/`, `chore/` as appropriate) and add a short kebab-case name, e.g. `feat/code-change-gate` or `fix/scan-placeholder`. State the chosen branch before creating it, and use that value wherever `$BRANCH_NAME` appears below.

**You have two mechanisms. Try them in this order.**

### 1a. Native Worktree Tools (preferred)

The gate (Step 0) authorized an isolated workspace. Do you already have a way to create a worktree? It might be a tool with a name like `EnterWorktree`, `WorktreeCreate`, a `/worktree` command, or a `--worktree` flag. If you do, use it and skip to Step 3.

Native tools handle directory placement, branch creation, and cleanup automatically. Using `git worktree add` when you have a native tool creates phantom state your harness can't see or manage.

Only proceed to Step 1b if you have no native worktree tool available.

### 1b. Git Worktree Fallback

**Only use this if Step 1a does not apply** — you have no native worktree tool available. Create a worktree manually using git.

#### Directory Selection

Follow this priority order. Explicit user preference always beats observed filesystem state.

1. **Check your instructions for a declared worktree directory preference.** If the user has already specified one, use it without asking.

2. **Check for an existing project-local worktree directory:**
   ```bash
   ls -d .worktrees 2>/dev/null     # Preferred (hidden)
   ls -d worktrees 2>/dev/null      # Alternative
   ```
   If found, use it. If both exist, `.worktrees` wins.

3. **Check for a resolved graph-wiki workspace.** Run the shared resolver.
   Because Bash-tool snippets execute against session cwd (not the skill file's
   location), we must use `${CLAUDE_PLUGIN_ROOT}` for absolute path resolution:
   ```bash
   workspace="$(bash "${CLAUDE_PLUGIN_ROOT}/skills/shared/resolve-workspace.sh" 2>/dev/null)"
   ```
   If it returns a non-empty path, use `<workspace>/worktrees/<branch>`. The
   workspace lives in a separate sibling directory (not this repo), so generated
   worktrees stay out of the checkout. If it returns empty, fall through to step 4.

4. **If there is no other guidance available**, default to `.worktrees/` at the project root.

#### Safety Verification (project-local directories only)

**MUST verify directory is ignored before creating worktree:**

```bash
git check-ignore -q .worktrees 2>/dev/null || git check-ignore -q worktrees 2>/dev/null
```

**If NOT ignored:** Add to .gitignore, commit the change, then proceed.

**Why critical:** Prevents accidentally committing worktree contents to repository.

The workspace `worktrees/` directory needs no verification — it lives in the
separate workspace sibling, not the repo, so it can't be committed (no gitignore
check needed).

#### Create the Worktree

```bash
# Determine path based on chosen location
# For project-local: path="$LOCATION/$BRANCH_NAME"
# For workspace:      path="$workspace/worktrees/$BRANCH_NAME"

git worktree add "$path" -b "$BRANCH_NAME"
cd "$path"
```

**Sandbox fallback:** If `git worktree add` fails with a permission error (sandbox denial), tell the user the sandbox blocked worktree creation and you're working in the current directory instead. Then run setup and baseline tests in place.

## Step 3: Project Setup

Auto-detect and run appropriate setup:

```bash
# Node.js
if [ -f package.json ]; then npm install; fi

# Rust
if [ -f Cargo.toml ]; then cargo build; fi

# Python
if [ -f requirements.txt ]; then pip install -r requirements.txt; fi
if [ -f pyproject.toml ]; then poetry install; fi

# Go
if [ -f go.mod ]; then go mod download; fi
```

## Step 4: Verify Clean Baseline

Run tests to ensure workspace starts clean:

```bash
# Use project-appropriate command
npm test / cargo test / pytest / go test ./...
```

**If tests fail:** Report failures, ask whether to proceed or investigate.

**If tests pass:** Report ready.

### Report

```
Worktree ready at <full-path>
Tests passing (<N> tests, 0 failures)
Ready to implement <feature-name>
```

## Step 5: Exit the Worktree (when done)

When feature work is finished, use the native `ExitWorktree` tool — the counterpart to `EnterWorktree` — to clean up. It can remove the worktree, or keep it / discard changes, and unwinds the harness state cleanly.

Prefer this over `git worktree remove`. Reaching for git here leaves the same phantom state your harness can't see or manage that you avoided at create time.

Only fall back to `git worktree remove` if you have no native exit tool available.


## Quick Reference

| Situation | Action |
|-----------|--------|
| No direct implement directive | STOP — stay read-only, ask before any code (Part 1) |
| Authorized, in main checkout | Create worktree — required, no consent prompt (Part 2) |
| User said work in the main checkout | Work in place, say so (Part 2 exception) |
| Already in linked worktree | Skip creation (Part 2) |
| In a submodule | Treat as normal repo (Step 0 guard) |
| Native worktree tool available | Use it (Step 1a) |
| No native tool | Git worktree fallback (Step 1b) |
| `.worktrees/` exists | Use it (verify ignored) |
| `worktrees/` exists | Use it (verify ignored) |
| Both exist | Use `.worktrees/` |
| Neither exists | Check instruction file, then default `.worktrees/` |
| graph-wiki workspace resolves | Use `<workspace>/worktrees/` (step 3) |
| Directory not ignored | Add to .gitignore + commit |
| Permission error on create | Sandbox fallback, work in place |
| Tests fail during baseline | Report failures + ask |
| No package.json/Cargo.toml | Skip dependency install |
| Feature work done, cleaning up | Use native `ExitWorktree` (Step 5) |

## Common Mistakes

### Asking for consent instead of gating

- **Problem:** Asking "would you like a worktree?" (the old consent flow), or writing code with no implement directive
- **Fix:** Part 1 requires a direct implement directive before any Write/Edit; Part 2 makes isolation mandatory. Don't ask — gate, then create.

### Fighting the harness

- **Problem:** Using `git worktree add` when the platform already provides isolation
- **Fix:** Step 0 detects existing isolation. Step 1a defers to native tools.

### Skipping detection

- **Problem:** Creating a nested worktree inside an existing one
- **Fix:** Always run Step 0 before creating anything

### Skipping ignore verification

- **Problem:** Worktree contents get tracked, pollute git status
- **Fix:** Always use `git check-ignore` before creating project-local worktree

### Assuming directory location

- **Problem:** Creates inconsistency, violates project conventions
- **Fix:** Follow priority: existing > workspace > instruction file > default

### Proceeding with failing tests

- **Problem:** Can't distinguish new bugs from pre-existing issues
- **Fix:** Report failures, get explicit permission to proceed

## Red Flags

**Never:**
- Write or Edit code without a direct implement directive (Part 1) — approving a design or plan is not authorization
- Ask "Would you like a worktree?" when code is authorized — isolation is mandatory, just create it
- Work in the main checkout unless the user explicitly asked
- Create a worktree when Step 0 detects existing isolation
- Use `git worktree add` when you have a native worktree tool (e.g., `EnterWorktree`). This is the #1 mistake — if you have it, use it.
- Skip Step 1a by jumping straight to Step 1b's git commands
- Create worktree without verifying it's ignored (project-local)
- Skip baseline test verification
- Proceed with failing tests without asking

**Always:**
- Confirm a direct implement directive before any Write/Edit (Part 1)
- Create an isolated worktree by default; use the main checkout only on explicit request
- Run Step 0 detection first
- Prefer native tools over git fallback
- Follow directory priority: existing > workspace > instruction file > default
- Verify directory is ignored for project-local
- Auto-detect and run project setup
- Verify clean test baseline
