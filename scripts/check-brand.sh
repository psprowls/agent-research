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
#
# Per Phase 21 §D-12: extended to also catch `code-wiki-agent` / `code_wiki_agent`
# / `code-wiki-mcp` / `code_wiki_mcp` after the rename to `graph-wiki-agent`.

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
    'lattice|LATTICE|lattice_workspace|lattice_wiki_core|code-wiki-agent|code_wiki_agent|code-wiki-mcp|code_wiki_mcp' \
    packages/ agents/ plugins/ .planning/ CLAUDE.md 2>/dev/null \
    | grep -vF -f <(grep -vE '^[[:space:]]*(#|$)' "$ALLOWLIST") || true)

if [ -n "$HITS" ]; then
  echo "$HITS"
  COUNT=$(printf '%s\n' "$HITS" | wc -l | tr -d ' ')
  echo "BRAND-04 FAIL: ${COUNT} unallowlisted hits" >&2
  exit 1
fi

# CHECK 2 — Phase 18 CMD-rename enforcement. Catches reintroduction of the old
# slash-command slug `graph-wiki:init` and the old MCP tool name `wiki_init`.
# Word boundaries pin the regex so `graph-wiki:bootstrap` and `wiki_bootstrap`
# pass cleanly. Same scope + allowlist + __pycache__ exclusions as CHECK 1.
HITS2=$(grep -rEl --exclude-dir=__pycache__ --exclude='*.pyc' \
    'graph-wiki:init\b|\bwiki_init\b' \
    packages/ agents/ plugins/ .planning/ scripts/ docs/ README.md CLAUDE.md 2>/dev/null \
    | grep -vF -f <(grep -vE '^[[:space:]]*(#|$)' "$ALLOWLIST") || true)

if [ -n "$HITS2" ]; then
  echo "$HITS2"
  COUNT2=$(printf '%s\n' "$HITS2" | wc -l | tr -d ' ')
  echo "BRAND-CMD FAIL: ${COUNT2} unallowlisted hits for graph-wiki:init|wiki_init" >&2
  exit 1
fi

# CHECK 3 — Typer subcommand regression guard. The renamed CLI subcommand is
# `def bootstrap(`; any reintroduction of `def init(` in cli.py would re-shadow
# Claude Code's native /init. No allowlist filter — the file has zero matches
# post-rename. 2>/dev/null swallows missing-file errors.
CLI_HITS=$(grep -nE '^\s*def init\(' agents/graph-wiki-agent/src/graph_wiki_agent/cli.py 2>/dev/null || true)

if [ -n "$CLI_HITS" ]; then
  echo "$CLI_HITS"
  echo "BRAND-CMD-CLI FAIL: def init( reintroduced in agents/graph-wiki-agent/src/graph_wiki_agent/cli.py" >&2
  exit 1
fi

# CHECK 4 — Phase 23 §WSMCP-07: ban reintroduction of the three workspace-API
# legacy patterns:
#   (1) `vault_path:` Pydantic Field declaration (anchored to class-body indent)
#   (2) `"--vault"` Typer flag literal
#   (3) `"vault_path"` JSON/dict key
# Path scope is packages/ agents/ plugins/ only — .planning/ historical docs
# are excluded per D-03 (this phase's CONTEXT, PATTERNS, prior SUMMARYs and
# REQUIREMENTS legitimately reference the old name and must not be edited).
HITS4=$(grep -rEln --exclude-dir=__pycache__ --exclude='*.pyc' -E \
    '^[[:space:]]+vault_path:[[:space:]]+(str|Path|int|bool)|"--vault"|"vault_path"' \
    packages/ agents/ plugins/ 2>/dev/null \
    | grep -vF -f <(grep -vE '^[[:space:]]*(#|$)' "$ALLOWLIST") || true)

if [ -n "$HITS4" ]; then
  echo "$HITS4"
  COUNT4=$(printf '%s\n' "$HITS4" | wc -l | tr -d ' ')
  echo "BRAND-WSAPI FAIL: ${COUNT4} unallowlisted hits for vault_path Field|--vault flag|\"vault_path\" key" >&2
  exit 1
fi

echo "BRAND-04 OK: zero unallowlisted hits (BRAND-04 lattice + BRAND-CMD graph-wiki:init|wiki_init + BRAND-CMD-CLI def init( all clean + BRAND-WSAPI vault_path|--vault|\"vault_path\")"
exit 0
