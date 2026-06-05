All set. The git history reset is fully complete:

  - develop is now your trunk and GitHub's default branch — full history preserved.
  - main is a clean orphan branch (stub README), ready to receive release merges.
  - pre-main-reset-backup tag and develop both preserve the old history on the remote.
  - The new workflow is recorded in memory so future sessions won't mistake the intentional two-root
  history for breakage.

  When you cut your first release, the command is git checkout main && git merge develop
  --allow-unrelated-histories (just that once), then tag and push. Whenever you're ready, the stale
  origin/checkpoint-1 and origin/phase/50-... branches can be pruned — say the word and I'll clean them
  up.