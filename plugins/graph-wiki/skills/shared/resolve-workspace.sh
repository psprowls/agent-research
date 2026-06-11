#!/usr/bin/env bash
# Resolve the graph-wiki workspace directory — pure bash, no Python.
# Usage: resolve-workspace.sh [start-dir]
#
# Echoes the resolved absolute workspace path to stdout and exits 0.
# Echoes NOTHING (empty stdout, exit 0) when no workspace resolves —
# callers decide their own fallback; this helper never invents one.
#
# Resolution chain:
#   1. $GRAPH_WIKI_WORKSPACE set and non-empty -> echo it.
#   2. Else walk up from start-dir (default $PWD) for .graph-wiki.local.yaml;
#      if found, extract the `workspace-directory:` value and echo it.
#   3. Else echo nothing.
#
# Kept dependency-free so it works in non-graph-wiki projects where the
# workspace_io / graph-wiki Python stack is not installed.

# 1. Environment variable wins.
if [[ -n "${GRAPH_WIKI_WORKSPACE:-}" ]]; then
  echo "$GRAPH_WIKI_WORKSPACE"
  exit 0
fi

# 2. Walk up from the start dir looking for .graph-wiki.local.yaml.
dir="${1:-$PWD}"
dir="$(cd "$dir" 2>/dev/null && pwd -P)" || exit 0
while [[ -n "$dir" ]]; do
  if [[ -f "$dir/.graph-wiki.local.yaml" ]]; then
    # Flat YAML: `workspace-directory: /abs/path`. Tolerant extraction —
    # strip the key, surrounding quotes, and whitespace. No YAML parser.
    value="$(sed -n 's/^[[:space:]]*workspace-directory:[[:space:]]*//p' \
      "$dir/.graph-wiki.local.yaml" | head -1)"
    value="${value%"${value##*[![:space:]]}"}"   # rstrip
    value="${value#"${value%%[![:space:]]*}"}"   # lstrip
    value="${value%\"}"; value="${value#\"}"
    value="${value%\'}"; value="${value#\'}"
    if [[ -n "$value" ]]; then
      echo "$value"
      exit 0
    fi
  fi
  [[ "$dir" == "/" ]] && break
  dir="$(dirname "$dir")"
done

# 3. Nothing resolved.
exit 0
