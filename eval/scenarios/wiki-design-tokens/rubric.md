Score the agent's `StatusBadge.tsx` 0–5, 1 pt per criterion. Pass threshold 4.

Criteria:

1. `uses_semantic_tokens` — Color classes use CSS custom property token utilities (`bg-primary`, `bg-destructive`, `bg-muted`, `text-foreground`, `text-primary-foreground`, etc.) rather than raw Tailwind palette classes (`bg-green-500`, `text-red-600`, etc.).
2. `no_hex_values` — No hardcoded hex color strings (e.g. `#16a34a`, `#dc2626`) appear anywhere in the file.
3. `uses_cva_pattern` — Uses `cva` from `class-variance-authority` to define the variant map (matching the pattern in `common-ui-shadcn-ts/src/components/button.tsx`).
4. `dark_mode_safe` — Only semantic token classes are used for color; these resolve correctly under the `.dark` class automatically without additional `dark:` overrides on raw palette classes.
5. `uses_cn_utility` — Imports and uses the `cn` utility (from `@psprowls/common-ui-shadcn-ts/lib/utils` or `@psprowls/shared-ui-react-ts`) to merge class names.

Return JSON: `{"score": 0-5, "reasoning": str, "criteria_hits": [str]}`.
