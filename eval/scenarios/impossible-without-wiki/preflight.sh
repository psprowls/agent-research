#!/bin/bash
# Preflight: verify the frozen wiki contains the required ADR

WIKI_ROOT="${GRAPH_WIKI_WORKSPACE:-~/Personal/graph-wiki/mono-repo-eval-551f7ed8}"
ADR_PATH="$WIKI_ROOT/wiki/adrs/0006-auto-create-activities-from-presence-events.md"

if [ ! -f "$ADR_PATH" ]; then
  echo "FAIL: ADR 0006 not found at $ADR_PATH"
  exit 1
fi

if ! grep -q "auto-create" "$ADR_PATH"; then
  echo "FAIL: ADR 0006 does not contain 'auto-create'"
  exit 1
fi

echo "OK: Wiki has required ADR"
exit 0
