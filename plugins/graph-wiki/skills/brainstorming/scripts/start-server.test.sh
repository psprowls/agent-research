#!/usr/bin/env bash
# Smoke tests for start-server.sh SESSION_DIR resolution (no --project-dir
# fallback chain). Launches the real node server in background, reads where
# the session landed from the server-started JSON, then stops it.
# Run: bash start-server.test.sh   (exit 0 = all pass). Requires node.
set -u

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
START="$SCRIPT_DIR/start-server.sh"
STOP="$SCRIPT_DIR/stop-server.sh"

pass=0
fail=0

# assert_prefix <name> <expected-prefix> <actual>
assert_prefix() {
  local name="$1" prefix="$2" actual="$3"
  if [[ "$actual" == "$prefix"* ]]; then
    pass=$((pass + 1))
    echo "ok   - $name"
  else
    fail=$((fail + 1))
    echo "FAIL - $name"
    echo "        expected prefix: [$prefix]"
    echo "        actual:          [$actual]"
  fi
}

TMP="$(mktemp -d)"
trap 'rm -rf "$TMP"' EXIT

# Launch start-server.sh (extra args passed through), echo the resolved
# SESSION_DIR (dirname of state_dir), and stop the server. Empty on failure.
run_case() {
  local json state_dir session_dir
  json="$("$@" 2>/dev/null | grep '"type":"server-started"' | head -1)"
  [[ -z "$json" ]] && return 0
  state_dir="$(printf '%s' "$json" | sed -n 's/.*"state_dir":"\([^"]*\)".*/\1/p')"
  session_dir="$(dirname "$state_dir")"
  "$STOP" "$session_dir" >/dev/null 2>&1
  printf '%s' "$session_dir"
}

# --- case 1: GRAPH_WIKI_WORKSPACE set -> <ws>/brainstorm/ ------------------
WS="$TMP/ws"
mkdir -p "$WS"
sd="$(cd "$TMP" && run_case env GRAPH_WIKI_WORKSPACE="$WS" bash "$START")"
assert_prefix "env workspace -> <ws>/brainstorm/" "$WS/brainstorm/" "$sd"

# --- case 2: no env, inside a git repo -> <repo>/.superpowers/brainstorm/ --
REPO="$TMP/repo"
mkdir -p "$REPO"
git -C "$REPO" init -q
# git rev-parse returns the physical path (symlinks resolved, e.g. /private/var
# on macOS); resolve the fixture the same way so the prefix matches.
REPO="$(cd "$REPO" && pwd -P)"
sd="$(cd "$REPO" && run_case env -u GRAPH_WIKI_WORKSPACE bash "$START")"
assert_prefix "git repo, no workspace -> <repo>/.superpowers/brainstorm/" \
  "$REPO/.superpowers/brainstorm/" "$sd"

# --- case 3: explicit --project-dir -> <dir>/.superpowers/brainstorm/ ------
PROJ="$TMP/proj"
mkdir -p "$PROJ"
sd="$(cd "$TMP" && run_case env -u GRAPH_WIKI_WORKSPACE bash "$START" --project-dir "$PROJ")"
assert_prefix "--project-dir -> <dir>/.superpowers/brainstorm/" \
  "$PROJ/.superpowers/brainstorm/" "$sd"

echo "-------------------------------------"
echo "pass=$pass fail=$fail"
[[ "$fail" -eq 0 ]]
