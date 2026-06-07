---
title: workspace-io
uri: pkg:agent-research/workspace-io
kind: package
summary: Workspace path resolution, GraphWikiConfig loading from .graph-wiki.yaml, and manifest authoring helpers.
updated: 2026-05-19
---

# workspace-io

## Overview

`workspace-io` is the workspace-resolution layer of the post-rebrand `agent-research` monorepo. It walks upward from `cwd` to find the nearest `.graph-wiki.yaml` (or repo root), loads it into a `GraphWikiConfig` dataclass, and exposes the resolved wiki path plus repo root to downstream commands.

## API

- `GraphWikiConfig.resolve(cwd: Path | None = None) -> GraphWikiConfig` — upward walk for `.graph-wiki.yaml`
- `paths.repo_root(cwd: Path) -> Path` — git-based repo-root resolver
- `manifest.write_manifest(...)` — emit a vault manifest entry on init

## Cross-refs

- Used by [[entities/app_graph-wiki-cli]] for vault resolution
- Initialised by [[entities/pkg_wiki-io]] when bootstrapping the wiki
