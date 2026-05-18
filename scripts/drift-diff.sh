#!/usr/bin/env bash
# drift-diff.sh — reproducible raw-diff generator for vault-io ⟷ lattice-wiki-core
#
# Phase 12 / Plan 01 (P-A per 12-CONTEXT.md §SQ-01.1).
#
# Emits a per-file unified-diff dump for every overlapping module row from
# spike 002 §Investigation A, with `lint/*` collapsed as a single row that
# contains 8 inline sub-file diffs. Writes only to stdout — caller redirects
# to `packages/vault-io/DRIFT-DECISIONS-RAW.md`.
#
# Re-sync usage: bump UPSTREAM_SHA, re-`git -C "$UPSTREAM_REPO" checkout`,
# and re-run `bash scripts/drift-diff.sh > packages/vault-io/DRIFT-DECISIONS-RAW.md`.

set -euo pipefail

# ---- Pinned coordinates (DD-04) -------------------------------------------
UPSTREAM_SHA=1b45172a9900842b0f8eea525c8270e7fff50605
UPSTREAM_REPO=/Users/pat/Personal/lattice
UPSTREAM_PKG_REL=packages/lattice-wiki-core/src/lattice_wiki_core
LOCAL_PKG_REL=packages/vault-io/src/vault_io

# ---- Canonical row list (spike 002 §A, lint/* collapsed = 11 rows) --------
MODULES=(
  "git_state.py"
  "append_log.py"
  "update_index.py"
  "update_tokens.py"
  "ingest_work_item.py"
  "init_vault.py"
  "lint/*"
  "layout_io.py"
  "detect_containers.py"
  "scan_monorepo.py"
  "ingest_source.py"
)

# 8 lint sub-files dumped inline under the `### lint/*` row.
# `lint/__init__.py` is empty in both repos and intentionally excluded.
LINT_FILES=(
  "lint/common.py"
  "lint/container.py"
  "lint/dependency.py"
  "lint/domain.py"
  "lint/file_map.py"
  "lint/package_sync.py"
  "lint/source_sync.py"
  "lint/workflow_hints.py"
)

# ---- Upstream SHA verification (fail loud) --------------------------------
if [ ! -d "$UPSTREAM_REPO/.git" ]; then
  echo "FATAL: upstream repo not found at $UPSTREAM_REPO" >&2
  exit 1
fi

UPSTREAM_HEAD=$(git -C "$UPSTREAM_REPO" rev-parse HEAD)
if [ "$UPSTREAM_HEAD" != "$UPSTREAM_SHA" ]; then
  echo "FATAL: upstream HEAD ($UPSTREAM_HEAD) does not match pinned SHA ($UPSTREAM_SHA)." >&2
  echo "  Either:" >&2
  echo "    git -C \"$UPSTREAM_REPO\" checkout $UPSTREAM_SHA" >&2
  echo "  or bump UPSTREAM_SHA in this script to the new pinned commit." >&2
  exit 1
fi

# ---- Header ---------------------------------------------------------------
DIFF_TIMESTAMP=$(date -u +%Y-%m-%dT%H:%M:%SZ)
INVOCATION="bash scripts/drift-diff.sh > packages/vault-io/DRIFT-DECISIONS-RAW.md"

cat <<HEADER
# vault-io ⟷ lattice-wiki-core Raw Drift Dump

**Upstream:** lattice-wiki-core @ \`$UPSTREAM_SHA\`
**Generated:** $DIFF_TIMESTAMP
**Command:** \`$INVOCATION\`

This file is the **raw-diff source of truth** (per 12-CONTEXT.md §DD-03). Every
overlapping module row from spike 002 §Investigation A is dumped here as a
\`diff -u\` between vault-io and the pinned upstream commit. No verdicts, no
judgment — just the diffs. The companion file
\`packages/vault-io/DRIFT-DECISIONS.md\` (forthcoming in plan 12-02) reads this
dump and assigns per-row verdicts (\`PORT\` / \`LEAVE-AHEAD\` / \`LEAVE-ARCH\` /
\`LEAVE-COSMETIC\` / \`IDENTICAL\`).

**Structure:** exactly 11 top-level \`### \` sections — one per overlapping
module row from spike 002 §A. The \`### lint/*\` row collapses 8 lint sub-files
into inline \`#### lint/<file>\` sub-sections beneath it (operator decision on
Blocker B1).

**Regeneration:** bump \`UPSTREAM_SHA\` in \`scripts/drift-diff.sh\`, checkout
that SHA in \`$UPSTREAM_REPO\`, then re-run \`$INVOCATION\`.

HEADER

# ---- Helper: emit one diff fence ------------------------------------------
emit_diff_for_file() {
  local relpath="$1"
  local upstream_path="$UPSTREAM_REPO/$UPSTREAM_PKG_REL/$relpath"
  local local_path="$LOCAL_PKG_REL/$relpath"

  # Tolerate missing files on either side — surface the absence in the dump.
  if [ ! -f "$upstream_path" ]; then
    echo "MISSING-UPSTREAM: $upstream_path"
    echo ""
    return
  fi
  if [ ! -f "$local_path" ]; then
    echo "MISSING-LOCAL: $local_path"
    echo ""
    return
  fi

  # `diff -u` exits 0 if identical, 1 if differences, >1 on error. We expect 0 or 1.
  set +e
  diff_output=$(diff -u "$upstream_path" "$local_path")
  diff_rc=$?
  set -e

  if [ "$diff_rc" -eq 0 ]; then
    echo "IDENTICAL"
    echo ""
  elif [ "$diff_rc" -eq 1 ]; then
    echo '```diff'
    printf '%s\n' "$diff_output"
    echo '```'
    echo ""
  else
    echo "FATAL: diff exited $diff_rc on $relpath" >&2
    exit 1
  fi
}

# ---- Per-row dump ---------------------------------------------------------
for row in "${MODULES[@]}"; do
  echo "### $row"
  echo ""

  if [ "$row" = "lint/*" ]; then
    for lf in "${LINT_FILES[@]}"; do
      echo "#### $lf"
      echo ""
      emit_diff_for_file "$lf"
    done
  else
    emit_diff_for_file "$row"
  fi
done
