#!/usr/bin/env bash
# Tests for resolve-workspace.sh — the pure-bash workspace resolver.
# Run: bash resolve-workspace.test.sh   (exit 0 = all pass)
set -u

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
RESOLVER="$SCRIPT_DIR/resolve-workspace.sh"

pass=0
fail=0

# assert_eq <name> <expected> <actual>
assert_eq() {
  local name="$1" expected="$2" actual="$3"
  if [[ "$expected" == "$actual" ]]; then
    pass=$((pass + 1))
    echo "ok   - $name"
  else
    fail=$((fail + 1))
    echo "FAIL - $name"
    echo "        expected: [$expected]"
    echo "        actual:   [$actual]"
  fi
}

TMP="$(mktemp -d)"
TMP="$(cd "$TMP" && pwd -P)"   # resolve /var -> /private/var so paths compare equal
trap 'rm -rf "$TMP"' EXIT

# --- (a) GRAPH_WIKI_WORKSPACE set -> echoes it, exit 0 ---------------------
out="$(GRAPH_WIKI_WORKSPACE=/some/ws bash "$RESOLVER" 2>/dev/null)"
rc=$?
assert_eq "env var: echoes value" "/some/ws" "$out"
assert_eq "env var: exit 0" "0" "$rc"

# env var beats on-disk discovery
mkdir -p "$TMP/proj_a/.git" "$TMP/proj_a/graph-wiki"
out="$(cd "$TMP/proj_a" && GRAPH_WIKI_WORKSPACE=/env/ws bash "$RESOLVER" 2>/dev/null)"
assert_eq "env var beats discovery" "/env/ws" "$out"

# --- (b) walk-up finds .git; <repo>/graph-wiki exists -> echoes it ---------
mkdir -p "$TMP/proj_b/.git" "$TMP/proj_b/graph-wiki"
out="$(cd "$TMP/proj_b" && bash "$RESOLVER" 2>/dev/null)"
rc=$?
assert_eq "discovery: echoes <repo>/graph-wiki" "$TMP/proj_b/graph-wiki" "$out"
assert_eq "discovery: exit 0" "0" "$rc"

# nested cwd exercises the walk-up
mkdir -p "$TMP/proj_b/a/b/c"
out="$(cd "$TMP/proj_b/a/b/c" && bash "$RESOLVER" 2>/dev/null)"
assert_eq "discovery: walk-up from nested cwd" "$TMP/proj_b/graph-wiki" "$out"

# worktree-style .git FILE (not dir) also counts as a repo root
mkdir -p "$TMP/wt/graph-wiki"
printf 'gitdir: /elsewhere/.git/worktrees/wt\n' > "$TMP/wt/.git"
out="$(cd "$TMP/wt" && bash "$RESOLVER" 2>/dev/null)"
assert_eq "discovery: .git file (worktree) counts" "$TMP/wt/graph-wiki" "$out"

# caller-supplied start dir argument
out="$(cd "$TMP" && bash "$RESOLVER" "$TMP/proj_b/a/b/c" 2>/dev/null)"
assert_eq "start-dir arg: walks up from arg not PWD" "$TMP/proj_b/graph-wiki" "$out"

# --- (c) repo WITHOUT graph-wiki/ -> empty (never invents a path) ----------
mkdir -p "$TMP/proj_c/.git" "$TMP/proj_c/deep"
out="$(cd "$TMP/proj_c/deep" && bash "$RESOLVER" 2>/dev/null)"
rc=$?
assert_eq "repo without graph-wiki/: empty stdout" "" "$out"
assert_eq "repo without graph-wiki/: exit 0" "0" "$rc"

# nested repo binds to the FIRST (inner) repo root — the outer repo's
# graph-wiki/ must NOT leak through
mkdir -p "$TMP/outer/.git" "$TMP/outer/graph-wiki" "$TMP/outer/inner/.git" "$TMP/outer/inner/src"
out="$(cd "$TMP/outer/inner/src" && bash "$RESOLVER" 2>/dev/null)"
assert_eq "nested repo: binds to inner root, empty" "" "$out"

# a graph-wiki path that exists but is a FILE does not count
mkdir -p "$TMP/proj_f/.git"
touch "$TMP/proj_f/graph-wiki"
out="$(cd "$TMP/proj_f" && bash "$RESOLVER" 2>/dev/null)"
assert_eq "graph-wiki is a file: empty" "" "$out"

echo "-------------------------------------"
echo "pass=$pass fail=$fail"
[[ "$fail" -eq 0 ]]
