#!/usr/bin/env bash
# Resolve the graph-wiki workspace directory — pure bash, no Python.
# Usage: resolve-workspace.sh [start-dir]
#
# Echoes the resolved absolute workspace path to stdout and exits 0.
# Echoes NOTHING (empty stdout, exit 0) when no workspace resolves —
# callers decide their own fallback; this helper never invents one.
#
# Resolution chain (mirrors workspace_io.config.resolve()):
#   1. $GRAPH_WIKI_WORKSPACE set and non-empty -> echo it.
#   2. Else walk up from start-dir (default $PWD) for a git repo root
#      (.git may be a dir, or a file in worktrees/submodules). At the FIRST
#      repo root found: echo <repo>/graph-wiki if that directory exists,
#      else echo nothing. Never bind to a parent repo's workspace.
#   3. Else echo nothing.
#
# Kept dependency-free so it works in non-graph-wiki projects where the
# workspace_io / graph-wiki Python stack is not installed.

# 1. Environment variable wins.
if [[ -n "${GRAPH_WIKI_WORKSPACE:-}" ]]; then
  echo "$GRAPH_WIKI_WORKSPACE"
  exit 0
fi

# 2. Walk up from the start dir looking for a git repo root.
dir="${1:-$PWD}"
dir="$(cd "$dir" 2>/dev/null && pwd -P)" || exit 0
while [[ -n "$dir" ]]; do
  if [[ -e "$dir/.git" ]]; then
    if [[ -d "$dir/graph-wiki" ]]; then
      echo "$dir/graph-wiki"
    fi
    exit 0
  fi
  [[ "$dir" == "/" ]] && break
  dir="$(dirname "$dir")"
done

# 3. Nothing resolved.
exit 0
