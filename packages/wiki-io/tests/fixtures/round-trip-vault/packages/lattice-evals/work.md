---
title: lattice-evals — Work
category: package
summary: Bugs, tech debt, features, and open questions for lattice-evals
updated: 2026-05-09
tokens: 144
---

# lattice-evals — Work

## Bugs

(none recorded)

## Tech debt

(none recorded)

## Features

(none recorded)

## Open questions

- Multi-turn `--input-format stream-json` handshake in `runner_headless` — the correct handshake protocol for multi-turn stdin/stdout in stream-json mode is not yet confirmed.
- Cache warmth makes cost metrics order-dependent — runs within a runset may hit cache at different rates depending on execution order, making per-run cost comparisons noisy.
