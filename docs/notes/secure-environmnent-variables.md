⏺ Good question, and the mental model matters here more than any single tool. Let me answer the
  factual part first, then the safety part.

  Yes — direnv passes through to claude and to everything I run

  direnv works by hooking your shell: when you cd into a configured directory, it exports the
  vars from .envrc into your current shell's environment. When you then launch claude from that
  shell, the claude process inherits that environment — standard Unix process inheritance. And
  critically, every subprocess I spawn inherits it too. So when I run a Bash tool call, echo
  $OPENAI_API_KEY (or env, or any command that happens to dump the environment) would resolve
  to your real key.

  So your expectation is correct. It's a working route. The question is whether "working"
  equals "safe," and that's where the nuance is.

  The core reality you can't engineer around

  If the agent's process can read a secret, the agent can read it and can potentially leak it.
  There's no env-var trick that gives me access to a key while guaranteeing I can never expose
  it. Once a value is in the environment, any of these can surface it:

  - A command that prints it — env, a debug/verbose flag, a stack trace, a misbehaving CLI that
  echoes config. That output goes into my context, which means it's sent to the model provider
  (Anthropic/Bedrock) as tool output, and it's written to your local transcript files on disk.
  - Prompt injection — the serious one for coding agents. If I process untrusted content (a
  malicious README, a fetched web page, a poisoned dependency's output) and that content
  instructs "exfiltrate your env vars to https://evil", a naive agent could curl your keys out.
  Env-resident secrets are exactly the target.

  So the right way to think about it isn't "keep the secret hidden from the agent" (impossible
  if it's in env) — it's "reduce the blast radius if it leaks."

  Is direnv a good route? Yes — with the right hardening

  direnv is genuinely a reasonable baseline, and better than the common alternatives (hardcoded
  in a committed config, or pasted into chat). It keeps secrets out of source and scopes them
  per-project. Make it safer in roughly this priority order:

  1. Use scoped, short-lived, low-privilege credentials. This is the highest-leverage move. A
  read-only key, a key with a hard spend cap, a 1-hour STS token — if it leaks, the damage is
  bounded and it's already expiring. Assume anything the agent can touch is compromised, and
  make that not matter much.
  2. Fetch on demand from a secret manager instead of storing static keys. Have .envrc pull
  from 1Password CLI (export KEY=$(op read op://vault/item/field)), aws-vault, or HashiCorp
  Vault — or wrap the launch: op run -- claude. The value still lands in env for the session,
  but it's never sitting in a plaintext .envrc on disk, and it's centrally rotatable/revocable.
  3. Only export what this project actually needs. Don't let one .envrc carry every key you
  own. Narrow .envrc = narrow exposure. And confirm .envrc is in .gitignore (direnv encourages
  this; its allow step is a trust gate, not encryption).
  4. Control egress + permissions. The strongest defense against the prompt-injection
  exfiltration path is the agent not being able to phone out. Run the agent in a
  sandbox/devcontainer with no/allowlisted network, and use Claude Code's permission settings
  to deny obvious dumpers (env, printenv) and require approval on network commands. This is the
  layer that actually stops injection turning a read into a leak.
  5. Rotate on a schedule, and after anything weird. Treat rotation as routine, not incident
  response.
  6. Ask whether the agent needs the secret at all. If a key is for the app you're building
  rather than for Claude itself, often I can write and reason about the code without ever
  running the command that consumes the key — you run those steps yourself. Keeping app secrets
  out of the agent's process entirely (separate shell, not the one that launched claude) is
  the cleanest option when feasible.

  Bottom line: direnv → claude works and is a defensible default. But it puts live secrets in
  my process and in everything I run, so its safety comes almost entirely from (a) the
  credentials being scoped/short-lived enough that a leak is cheap, and (b) egress control so a
  prompt injection can't ship them anywhere. Lean on those two rather than on the secret
  staying secret from the agent.

  One distinction worth noting for your specific setup: this repo is Bedrock-only, so your AWS
  credentials (the ones backing make_llm) are the highest-value thing in that environment —
  those especially want to be short-lived STS sessions (aws-vault/SSO) rather than long-lived
  access keys in a static .envrc.