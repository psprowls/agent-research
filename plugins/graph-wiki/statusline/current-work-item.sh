#!/usr/bin/env bash
# claude-hud --extra-cmd helper: show the most-recently-touched in-flight
# graph-wiki work item — the same item `/graph-wiki:next` resume suggests.
#
# claude-hud runs --extra-cmd with no stdin forwarded, so we cannot see the
# session's transcript; we resolve the workspace from the current directory
# instead. Prints {"label":"..."} for claude-hud (capped at 50 chars there);
# an empty label renders nothing — used whenever there is no in-flight item or
# we are not inside a graph-wiki repo.
#
# Wire it into claude-hud's statusline command (in ~/.claude/settings.json):
#   CLAUDE_HUD_ALLOW_EXTRA_CMD=1 exec "<bun>" ... "${plugin_dir}src/index.ts" \
#     --extra-cmd "<repo>/plugins/graph-wiki/statusline/current-work-item.sh"
set -euo pipefail

emit() { jq -nc --arg l "${1:-}" '{label:$l}'; exit 0; }

# Walk up from cwd to find the repo's workspace pin (.graph-wiki.local.yaml).
dir=$PWD
local_yaml=""
while [ "$dir" != "/" ]; do
  if [ -f "$dir/.graph-wiki.local.yaml" ]; then
    local_yaml="$dir/.graph-wiki.local.yaml"
    break
  fi
  dir=$(dirname "$dir")
done

# Resolve workspace: env override wins, else the pin. Give up (blank) if neither.
ws=${GRAPH_WIKI_WORKSPACE:-}
if [ -z "$ws" ] && [ -n "$local_yaml" ]; then
  ws=$(grep -E '^[[:space:]]*workspace-directory:' "$local_yaml" | head -1 \
       | sed -E 's/^[^:]*:[[:space:]]*//; s/[[:space:]]*$//; s/^["'"'"']//; s/["'"'"']$//')
fi
[ -n "$ws" ] || emit ""

idx="$ws/wiki/work-index.json"
[ -f "$idx" ] || emit ""

# Most-recently-updated actionable item (status not terminal/mitigated),
# mirroring work_io.resume.select_resume_suggestions.
slug=$(jq -r '
  [ .items[]
    | select(((.status // "") | ascii_downcase) as $s
             | ($s | IN("resolved","wontfix","superseded","mitigated")) | not) ]
  | sort_by((.updated_at // ""), (.updated // ""))
  | reverse
  | (.[0].slug // "")' "$idx" 2>/dev/null) || emit ""
[ -n "${slug:-}" ] && [ "$slug" != "null" ] || emit ""

# Strip a leading YYYY-MM-DD- date prefix for brevity.
short=$slug
case "$slug" in
  20[0-9][0-9]-[0-1][0-9]-[0-3][0-9]-*)
    short=${slug#20[0-9][0-9]-[0-1][0-9]-[0-3][0-9]-} ;;
esac

emit "⚙ $short"
