# Wiki-Context Evals Design

**Date**: 2026-06-07  
**Status**: Approved

## Goal

Two `cc-eval` scenarios that fail without wiki-context injection and pass once wiki search + knowledge injection is wired in. These act as the primary regression signal for the wiki-injection feature: a run of both scenarios against the `base` config (no plugins) should FAIL; a future run against a `wiki` config (graph-wiki plugin installed) should PASS.

## Directory Layout

Both scenarios land under the existing `eval/` root, which serves as the `cc-eval` evals root (`cc-eval --evals-root eval/`):

```
eval/
  configs/
    base.yaml                     ← no plugin_dirs, sonnet-4-6, temp=0.0
  scenarios/
    wiki-api-client/
      scenario.yaml
      prompt.md
      rubric.md
      preflight.sh                ← deletes target file before each run
      verify.sh                   ← asserts target file exists
    wiki-design-tokens/
      scenario.yaml
      prompt.md
      rubric.md
      preflight.sh
      verify.sh
  cases/                          ← existing graph-wiki harness (untouched)
  baselines/                      ← existing graph-wiki harness (untouched)
```

Both scenarios:
- `isolation_mode: worktree` targeting `~/Personal/mono-repo` at SHA `551f7ed8b9c0b4f51a4000302548e24284729652`
- `configs: [base]`
- `eval_mode: implement`
- `mode: headless`
- Verify: `script` (file-exists) + `rubric` (quality)
- Pass threshold: 4/5 rubric criteria

## Scenario 1: `wiki-api-client`

**What it tests**: Does the agent use the project's sanctioned domain HTTP client (`TimelineApiClient` from `@psprowls/timeline-domain-ts`) or does it fall back to raw `axios`/`fetch` with a hardcoded URL?

**Why it fails without wiki**: The most discoverable existing HTTP usage in `apps/web-next-ts` is `nextauth-api.ts`, which uses raw axios and a hardcoded `https://ts-api.psprowls.io` base URL. An agent exploring without wiki context follows that pattern. Only the wiki surfaces the convention: all data fetching goes through domain-specific API clients, never raw HTTP.

### `scenario.yaml`

```yaml
name: wiki-api-client
description: >
  Agent must use the project's sanctioned domain HTTP client (TimelineApiClient)
  to fetch timeline data. Without wiki context the agent copies the raw-axios
  pattern visible in nextauth-api.ts and fails the rubric.
isolation_mode: worktree
target_repo: ~/Personal/mono-repo
baseline_sha: 551f7ed8b9c0b4f51a4000302548e24284729652
configs: [base]
mode: headless
eval_mode: implement
preflight: preflight.sh
verify:
  - kind: script
    path: verify.sh
  - kind: rubric
    path: rubric.md
    pass_threshold: 4.0
budgets:
  max_turns: 40
  max_input_tokens: 4000000
  max_wall_seconds: 300
metrics:
  tool_shape: true
  judge_qualitative: false
```

### `prompt.md`

```
Implement `apps/web-next-ts/src/lib/timeline-summary.ts`.

Requirements:
- Export a single async function `getRecentTimeline(limit: number = 10)`
- Use the project's sanctioned domain HTTP client — do NOT use raw `fetch`, `axios`, or hardcode API URLs
- Return a typed list of timeline events using types from the timeline domain package
- Do not manage auth tokens manually — the client handles that
```

### `rubric.md`

Score the agent's `timeline-summary.ts` 0–5, 1 pt per criterion. Pass threshold 4.

Criteria:

1. `uses_domain_client` — Imports `TimelineApiClient` from `@psprowls/timeline-domain-ts` (or another sanctioned domain client). What is forbidden: importing `axios` directly, using `fetch`, using `SharedApiClient` for data fetching, or constructing a raw HTTP call.
2. `no_raw_http` — Does not call `axios(...)`, `axios.get(...)`, `fetch(...)`, or `XMLHttpRequest` anywhere in the file.
3. `no_hardcoded_url` — Does not hardcode an API base URL string (e.g. `https://ts-api.psprowls.io`); relies on the client's built-in configuration.
4. `no_manual_auth` — Does not attach Authorization headers, manage Cognito tokens, or otherwise handle authentication — that is the domain client's responsibility.
5. `correct_types` — The return type is statically inferable as a typed list from `@psprowls/timeline-domain-ts`, not `any` or `unknown`.

Return JSON: `{"score": 0-5, "reasoning": str, "criteria_hits": [str]}`.

### `preflight.sh`

```sh
#!/bin/sh
set -eu
rm -f apps/web-next-ts/src/lib/timeline-summary.ts
```

### `verify.sh`

```sh
#!/bin/sh
set -eu
test -f apps/web-next-ts/src/lib/timeline-summary.ts
```

---

## Scenario 2: `wiki-design-tokens`

**What it tests**: Does the agent use the project's semantic CSS custom property token system (`bg-primary`, `text-destructive`, etc.) and CVA variant pattern when creating a new component, or does it reach for hex values and raw Tailwind palette classes?

**Why it fails without wiki**: Without wiki context, agents naturally reach for hex values (`#16a34a`) or raw Tailwind palette classes (`bg-green-500`, `bg-red-500`). The wiki surfaces two conventions that are hard to discover by exploration:
1. All colors must go through the CSS custom property token system defined in `globals.css` (`bg-primary`, `bg-destructive`, `bg-muted`, `text-foreground`, etc.)
2. Multi-variant components must use `cva` from `class-variance-authority` — the same pattern used in `common-ui-shadcn-ts/src/components/button.tsx`

### `scenario.yaml`

```yaml
name: wiki-design-tokens
description: >
  Agent must create a StatusBadge component using the project's semantic color
  token system and CVA variant pattern. Without wiki context the agent uses
  hex values or raw Tailwind palette classes and fails the rubric.
isolation_mode: worktree
target_repo: ~/Personal/mono-repo
baseline_sha: 551f7ed8b9c0b4f51a4000302548e24284729652
configs: [base]
mode: headless
eval_mode: implement
preflight: preflight.sh
verify:
  - kind: script
    path: verify.sh
  - kind: rubric
    path: rubric.md
    pass_threshold: 4.0
budgets:
  max_turns: 40
  max_input_tokens: 4000000
  max_wall_seconds: 300
metrics:
  tool_shape: true
  judge_qualitative: false
```

### `prompt.md`

```
Create a `StatusBadge` component at `apps/web-next-ts/src/components/StatusBadge.tsx`.

Requirements:
- Accept a `status` prop: `"running" | "completed" | "failed" | "pending"`
- Each status renders with appropriate color styling
- Follow the project's design system conventions — use semantic color tokens, not hardcoded hex values or raw Tailwind palette classes like `bg-green-500`
- Follow the component variant patterns established in the shared UI packages
- Export `StatusBadge` as a named export
```

### `rubric.md`

Score the agent's `StatusBadge.tsx` 0–5, 1 pt per criterion. Pass threshold 4.

Criteria:

1. `uses_semantic_tokens` — Color classes use CSS custom property token utilities (`bg-primary`, `bg-destructive`, `bg-muted`, `text-foreground`, `text-primary-foreground`, etc.) rather than raw Tailwind palette classes (`bg-green-500`, `text-red-600`, etc.).
2. `no_hex_values` — No hardcoded hex color strings (e.g. `#16a34a`, `#dc2626`) appear anywhere in the file.
3. `uses_cva_pattern` — Uses `cva` from `class-variance-authority` to define the variant map (matching the pattern in `common-ui-shadcn-ts/src/components/button.tsx`).
4. `dark_mode_safe` — Only semantic token classes are used for color; these resolve correctly under the `.dark` class automatically without additional `dark:` overrides on raw palette classes.
5. `uses_cn_utility` — Imports and uses the `cn` utility (from `@psprowls/common-ui-shadcn-ts/lib/utils` or `@psprowls/shared-ui-react-ts`) to merge class names.

Return JSON: `{"score": 0-5, "reasoning": str, "criteria_hits": [str]}`.

### `preflight.sh`

```sh
#!/bin/sh
set -eu
rm -f apps/web-next-ts/src/components/StatusBadge.tsx
```

### `verify.sh`

```sh
#!/bin/sh
set -eu
test -f apps/web-next-ts/src/components/StatusBadge.tsx
```

---

## Implementation Notes

- `eval/configs/base.yaml`: `name: base`, `model: claude-sonnet-4-6`, `temperature: 0.0`, no `plugin_dirs` — this is the no-wiki config that should produce FAIL results.
- Future `eval/configs/wiki.yaml` will add the graph-wiki plugin and should flip both scenarios to PASS.
- The rubric judge defaults to `claude-haiku-4-5-20251001` (set in `RubricVerifier`); no override needed.
- Both `preflight.sh` and `verify.sh` must be `chmod +x` before running.
- Run one scenario: `cc-eval run wiki-api-client --evals-root eval/`
- Run both: create a `eval/runsets/wiki-context.yaml` pointing at both scenarios (follow-up).
