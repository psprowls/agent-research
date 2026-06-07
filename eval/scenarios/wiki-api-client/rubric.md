Score the agent's `timeline-summary.ts` 0–5, 1 pt per criterion. Pass threshold 4.

Criteria:

1. `uses_domain_client` — Imports `TimelineApiClient` from `@psprowls/timeline-domain-ts` (or another sanctioned domain client). What is forbidden: importing `axios` directly, using `fetch`, using `SharedApiClient` for data fetching, or constructing a raw HTTP call.
2. `no_raw_http` — Does not call `axios(...)`, `axios.get(...)`, `fetch(...)`, or `XMLHttpRequest` anywhere in the file.
3. `no_hardcoded_url` — Does not hardcode an API base URL string (e.g. `https://ts-api.psprowls.io`); relies on the client's built-in configuration.
4. `no_manual_auth` — Does not attach Authorization headers, manage Cognito tokens, or otherwise handle authentication — that is the domain client's responsibility.
5. `correct_types` — The return type is statically inferable as a typed list from `@psprowls/timeline-domain-ts`, not `any` or `unknown`.

Return JSON: `{"score": 0-5, "reasoning": str, "criteria_hits": [str]}`.
