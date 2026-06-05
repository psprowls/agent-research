---
title: Code Wiki Index
category: index
summary: Entry point for the post-rebrand fixture vault used by Phase 16 scanner regression tests.
status: active
language:
tags: [index, fixture]
updated: 2026-05-19
---

# Code Wiki

## Packages

- [[packages/workspace-io/workspace-io]] — workspace path resolution and config loading
- [[packages/wiki-io/wiki-io]] — vault read/write, frontmatter, indexing, BM25 search
- [[packages/prompt-sources/prompt-sources]] — canonical agent role definitions
- [[packages/subagent-runtime/subagent-runtime]] — async fan-out pool with per-call trace JSONL
- [[packages/model-adapter/model-adapter]] — ChatBedrockConverse role-config loader
- [[packages/eval-harness/eval-harness]] — divergence checks, two-gate scoring, model sweep

## Agents

- [[agents/graph-wiki-agent/graph-wiki-agent]] — Bedrock-driven CLI + MCP server (query, scan, ingest, lint)

## Plugins

- [[plugins/graph-wiki/graph-wiki]] — Claude Code plugin port (functional parity with upstream)
