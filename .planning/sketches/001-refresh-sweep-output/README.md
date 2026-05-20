---
sketch: 001
name: refresh-sweep-output
question: "What does /graph-wiki:refresh (no args) look like top-to-bottom in a terminal?"
winner: "A"
tags: [cli, refresh, output, terminal]
---

# Sketch 001 — Refresh sweep output

## Design Question
The refresh command runs autonomously (no per-page prompts) and may take minutes. How should it report progress and final outcome? The trust gate is "user reviews after," so output must let them verify nothing surprising happened.

## How to View
```
open .planning/sketches/001-refresh-sweep-output/index.html
```

## Variants
- **A: Streaming log** — every event on its own line as it happens, like `npm install`. Scrollback is the audit trail. Trust comes from watching it work.
- **B: Live status block** — milestone events log above; a persistent in-place block at the bottom shows current stage, progress bar, ETA, and cost. Less scroll, more dashboard-y. Includes a mid-run frame.
- **C: Quiet during run, structured report at end** — a single spinner line while working, then one formatted report block. Highest signal-to-noise; loses in-flight context.

## What to Look For
- Where does your eye go first when the run finishes? (Total pages updated? Things flagged for review? Cost?)
- Does the "flagged for review" callout (the one TODO-review page) stand out enough in each variant?
- A & C both work well in scrollback / CI logs; B requires a real TTY. Does that matter?
- When refresh runs for 5+ minutes, which variant best answers "is it still working / what is it doing?"
