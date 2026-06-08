---
title: graph-wiki-core
uri: pkg:agent-research/graph-wiki-core
kind: package
summary: Shared command, prompt, and orchestration logic for Graph Wiki delivery surfaces.
updated: 2026-05-19
---

# graph-wiki-core

## Overview

`graph-wiki-core` is the shared implementation layer for Graph Wiki workflows. The CLI and MCP surfaces stay thin while core owns command behavior for scan, ingest, query, lint, graph operations, proposals, work items, and drift handling.

## Orchestration responsibilities

Core commands combine workspace resolution from [[entities/pkg_workspace-io]], vault reads and writes from [[entities/pkg_wiki-io]], role-scoped Bedrock models from [[entities/pkg_model-adapter]], and bounded parallel fan-out from [[entities/pkg_subagent-runtime]]. Scan and query workflows use `SubagentPool` to run Bedrock-backed role work with concurrency limits and trace output while keeping the orchestration logic independent of the CLI surface.

## Cross-refs

- Exposed through [[entities/app_graph-wiki-cli]]
- Uses [[entities/pkg_subagent-runtime]] for fan-out in scan and query workflows
- Uses [[entities/pkg_model-adapter]] for guarded Bedrock model construction
