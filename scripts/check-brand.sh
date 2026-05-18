#!/usr/bin/env bash
#
# scripts/check-brand.sh — BRAND-04 grep gate.
#
# Per Phase 12 §SQ-04 + §W5: search for upstream `lattice` / `LATTICE` /
# `lattice_workspace` / `lattice_wiki_core` references across in-scope paths
# (packages/, agents/, plugins/, .planning/, CLAUDE.md) and fail if any hit
# is NOT covered by `.brand-grep-allow` at repo root.
#
# Re-runnable cheaply by future phases (13, 14, 16) and by any future re-sync
# between vault-io and upstream lattice-wiki-core.

set -euo pipefail

ALLOWLIST=".brand-grep-allow"

if [ ! -f "$ALLOWLIST" ]; then
  echo "BRAND-04 FAIL: $ALLOWLIST not found at repo root" >&2
  exit 2
fi

# Compute hits across in-scope paths. `plugins/` is included for forward
# compatibility with Phase 14 (per W5); `grep -r` on an empty/absent directory
# returns nothing, so the 2>/dev/null swallows "no such file" noise.
#
# CR-01 fix: BSD grep (macOS default) treats an empty pattern as matching
# every line, so blank lines in $ALLOWLIST would (combined with -v) exclude
# every hit and silently turn the gate into a no-op. Strip blanks and
# comments before passing patterns to `grep -vF -f`. This also resolves
# WR-03 — comment lines are no longer effective patterns, so a future edit
# that puts a path-fragment-like substring inside a `#`-comment cannot
# silently broaden the allowlist.
# Exclude __pycache__/*.pyc — gitignored build artifacts that embed source
# string literals as bytecode constants. They surface as hits after any local
# `uv run pytest` run; a clean CI checkout doesn't have them, so excluding
# them keeps the gate stable across both environments.
HITS=$(grep -rEl --exclude-dir=__pycache__ --exclude='*.pyc' \
    'lattice|LATTICE|lattice_workspace|lattice_wiki_core' \
    packages/ agents/ plugins/ .planning/ CLAUDE.md 2>/dev/null \
    | grep -vF -f <(grep -vE '^[[:space:]]*(#|$)' "$ALLOWLIST") || true)

if [ -n "$HITS" ]; then
  echo "$HITS"
  COUNT=$(printf '%s\n' "$HITS" | wc -l | tr -d ' ')
  echo "BRAND-04 FAIL: ${COUNT} unallowlisted hits" >&2
  exit 1
fi

echo "BRAND-04 OK: zero unallowlisted hits"
exit 0
