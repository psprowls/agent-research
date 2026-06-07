Implement `apps/web-next-ts/src/lib/timeline-summary.ts`.

Requirements:
- Export a single async function `getRecentTimeline(limit: number = 10)`
- Use the project's sanctioned domain HTTP client — do NOT use raw `fetch`, `axios`, or hardcode API URLs
- Return a typed list of timeline events using types from the timeline domain package
- Do not manage auth tokens manually — the client handles that
