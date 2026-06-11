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
trap 'rm -rf "$TMP"' EXIT

# --- (a) GRAPH_WIKI_WORKSPACE set -> echoes it, exit 0 ---------------------
out="$(GRAPH_WIKI_WORKSPACE=/some/ws bash "$RESOLVER" 2>/dev/null)"
rc=$?
assert_eq "env var: echoes value" "/some/ws" "$out"
assert_eq "env var: exit 0" "0" "$rc"

# env var beats an on-disk config file
mkdir -p "$TMP/proj_a"
printf 'workspace-directory: /file/ws\n' > "$TMP/proj_a/.graph-wiki.local.yaml"
out="$(cd "$TMP/proj_a" && GRAPH_WIKI_WORKSPACE=/env/ws bash "$RESOLVER" 2>/dev/null)"
assert_eq "env var beats config file" "/env/ws" "$out"

# --- (b) walk-up finds .graph-wiki.local.yaml -> echoes workspace-directory --
mkdir -p "$TMP/proj_b"
printf 'workspace-directory: /abs/workspace\n' > "$TMP/proj_b/.graph-wiki.local.yaml"
out="$(cd "$TMP/proj_b" && bash "$RESOLVER" 2>/dev/null)"
rc=$?
assert_eq "config file: echoes path" "/abs/workspace" "$out"
assert_eq "config file: exit 0" "0" "$rc"

# nested cwd exercises the walk-up
mkdir -p "$TMP/proj_b/a/b/c"
out="$(cd "$TMP/proj_b/a/b/c" && bash "$RESOLVER" 2>/dev/null)"
assert_eq "config file: walk-up from nested cwd" "/abs/workspace" "$out"

# tolerant extraction: quotes + trailing whitespace stripped
mkdir -p "$TMP/proj_q"
printf 'workspace-directory:   "/quoted/ws"   \n' > "$TMP/proj_q/.graph-wiki.local.yaml"
out="$(cd "$TMP/proj_q" && bash "$RESOLVER" 2>/dev/null)"
assert_eq "config file: strips quotes and whitespace" "/quoted/ws" "$out"

# caller-supplied start dir argument
out="$(cd "$TMP" && bash "$RESOLVER" "$TMP/proj_b/a/b/c" 2>/dev/null)"
assert_eq "start-dir arg: walks up from arg not PWD" "/abs/workspace" "$out"

# --- (c) neither -> empty stdout, exit 0 ----------------------------------
mkdir -p "$TMP/bare/deep"
out="$(cd "$TMP/bare/deep" && bash "$RESOLVER" 2>/dev/null)"
rc=$?
assert_eq "no workspace: empty stdout" "" "$out"
assert_eq "no workspace: exit 0" "0" "$rc"

echo "-------------------------------------"
echo "pass=$pass fail=$fail"
[[ "$fail" -eq 0 ]]
