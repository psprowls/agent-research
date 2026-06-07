# Programmatic credential creation & rotation into 1Password

**Date:** 2026-06-07
**Status:** Research note / pre-brainstorm
**Related:** [`secure-environmnent-variables.md`](./secure-environmnent-variables.md) (direnv → agent pass-through, blast-radius reduction)

## Intent

Considering building **TypeScript tooling to automatically rotate credentials on a schedule**
and push the results into 1Password (`op` CLI). Brainstorming/implementation will happen in a
separate, more appropriate repository — this note is just the research that motivates it.

The guiding principle (from the direnv note): if the agent's process can read a secret, it can
leak it. You can't hide a secret from the agent while still giving it access — so reduce
**blast radius** instead. Two levers do almost all the work:

1. **Scoped, short-lived, low-privilege credentials** — if it leaks, damage is bounded and it's
   already expiring.
2. **Egress control** — a sandbox/devcontainer with no/allowlisted network stops a prompt
   injection from shipping a leaked key anywhere.

Where a service offers **ephemeral, minted-on-demand** credentials (STS, GitHub App installation
tokens, Atlas OAuth tokens, identity federation), that beats a scheduled "rotate static key into
1Password" job — fewer standing secrets. Scheduled rotation is the **fallback** for services that
don't offer ephemeral tokens.

## The core question

Two parts, asked per service:
- Can new credentials be **created programmatically** (so a cron/Lambda/TS job can rotate them)?
- Is there a **short-lived-token path** that removes the static secret entirely (preferred)?

## Per-service findings (verified 2026-06-07)

### AWS credentials
- **Fully scriptable.** An IAM user may hold **two** access keys at once — enables zero-downtime
  rotation: `aws iam create-access-key` → write to `op` → update consumers → verify →
  `aws iam delete-access-key` (old).
- **Better: don't rotate static keys at all.** Use IAM Identity Center (SSO) + `aws sso login`,
  or `aws-vault`, to mint **short-lived STS session tokens** on demand. Nothing static to rotate;
  the agent only ever holds a ~1h credential.
- AWS Secrets Manager has native scheduled rotation, but stores in Secrets Manager (not 1Password).
- **This repo is Bedrock-only**, so the AWS creds backing `make_llm` are the highest-value secret
  in the environment — strongest candidate for short-lived STS rather than static keys in `.envrc`.

### GitHub
- **No API to create a PAT** (classic or fine-grained) — UI-only. Cannot fully auto-rotate a PAT.
- **Use a GitHub App instead** (the automation-friendly path, analogous to AWS STS):
  sign a JWT with the App's private key → exchange via API for a **short-lived installation
  access token** (1h TTL, scoped per-installation/repo). Mint on demand; nothing to rotate but
  the App private key (rarely, lives in 1Password).
- **Enterprise NOT required.** GitHub Apps work on any tier — free personal accounts and free
  orgs included. No paid plan needed.

### MongoDB Atlas — best of the set
- **Fully programmatic.** Database users (the app's connection creds) create/update/delete via
  the Atlas Administration API — rotate a DB user password programmatically and push to 1Password.
- **Short-lived path exists:** **Service Accounts via OAuth 2.0** — hold a client ID + secret,
  exchange via client-credentials flow for a **1-hour access token**
  (`POST https://cloud.mongodb.com/api/oauth/token`). Rotating the **client secret** does NOT
  require recreating the account — regenerate in place, store new secret.
- **Passwordless DB auth** also supported: AWS IAM, X.509, Workload Identity Federation (OIDC) —
  removes the static DB password entirely. Worth a look given AWS-centric setup.

### OpenAI
- **No API to create a normal user API key** (dashboard-only, like a GitHub PAT).
- **But the Admin API can create a project service account, and the create call returns the full
  unredacted API key once** (store immediately — never retrievable again):
  ```
  POST https://api.openai.com/v1/organization/projects/{project_id}/service_accounts
  Authorization: Bearer $OPENAI_ADMIN_KEY
  → response.api_key.value = "sk-..."
  ```
- Real rotate-into-1Password loop: create new service account/key → write to `op` → update
  consumers → delete old (AWS-style two-key dance).
- Caveats: returned key is **long-lived** (no short-lived inference-token equivalent); new key
  defaults to read+write on all project resources (scope down after); the **admin key** driving
  this is the crown jewel — keep it out of agent environments entirely.

### Anthropic
- **No create-key endpoint.** Admin API (`/v1/organizations/api_keys`) can **list / retrieve /
  update** (rename, enable/disable) existing keys, but creation — regular keys and admin keys —
  is **Console-only**. So only a *partial* loop (disable a key via API on schedule); create is manual.
- **Short-lived path exists only on Claude Platform on AWS** (Anthropic-operated, SigV4/IAM auth —
  distinct from Amazon Bedrock): **short-term API keys** minted programmatically, lifetime capped
  at the lesser of requested duration, backing credential expiry, and **12 hours**. Not available
  on the standard first-party API.

## Summary table

| Service | Create key via API? | Short-lived token path? | Rotate-to-1Password loop |
|---|---|---|---|
| **GitHub** | No (PAT) — but **GitHub App** needs no Enterprise | ✅ installation tokens (1h) | Use App; only the private key persists |
| **MongoDB Atlas** | ✅ DB users + service accounts | ✅ OAuth2 tokens (1h); also IAM/OIDC passwordless | Fully automatable; prefer SA secret rotation or federation |
| **OpenAI** | ✅ via Admin API project service accounts | ❌ (keys long-lived) | Fully automatable (create-new/delete-old) |
| **Anthropic** | ❌ Console only | Only on Claude Platform on AWS (≤12h short-term keys) | Partial (disable via API); create is manual |
| **AWS** | ✅ IAM access keys (2-key rotation) | ✅ STS / SSO / aws-vault | Fully automatable; prefer STS over static keys |

## Implications for the TypeScript rotation tool

- **Don't build a static-key rotator where an ephemeral-token path exists.** AWS (STS/SSO),
  GitHub (App tokens), Atlas (OAuth SA) — wrap on-demand token minting, don't rotate static keys.
- **Scheduled create→`op`→delete loop is the right shape for:** OpenAI (service-account keys),
  AWS IAM access keys (if STS isn't adopted), Atlas DB-user passwords / SA client secrets.
- **Anthropic first-party can't be fully automated** — manual Console creation, store in 1Password,
  rotate manually, scope tightly, cap spend. (Or move onto Claude Platform on AWS for ≤12h keys.)
- **The driver credentials are themselves crown jewels** (OpenAI admin key, Atlas SA secret, AWS
  IAM principal, GitHub App private key) — keep them out of any agent-accessible environment;
  the rotation job should run in its own trust boundary, not the dev shell that launches `claude`.

## Sources

- [OpenAI — Create project service account (API reference)](https://developers.openai.com/api/reference/resources/admin/subresources/organization/subresources/projects/subresources/service_accounts/methods/create)
- [OpenAI — Admin API Keys reference](https://platform.openai.com/docs/api-reference/admin-api-keys/list)
- [Anthropic — Admin API overview](https://platform.claude.com/docs/en/manage-claude/admin-api)
- [Anthropic — Get API Key (Admin API reference)](https://docs.anthropic.com/en/api/admin-api/apikeys/get-api-key)
- [MongoDB — Introducing Atlas Service Accounts via OAuth 2.0](https://www.mongodb.com/company/blog/product-release-announcements/introducing-mongodb-atlas-service-accounts-via-oauth-2-0)
- [MongoDB — Generate Service Account Token](https://www.mongodb.com/docs/atlas/api/service-accounts/generate-oauth2-token/)
- [MongoDB — Atlas Administration API Authentication Methods](https://www.mongodb.com/docs/atlas/api/api-authentication/)
