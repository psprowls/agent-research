This is an interactive scenario — the harness does not drive Claude Code for you.

1. The orchestrator prints the worktree path and waits.
2. In a separate terminal, `cd` into that worktree and run `claude`.
3. Ask the agent to add a helper module at
   `apps/web-next-ts/src/lib/greeting.ts` exporting a named function
   `greeting(name: string): string` that returns `"Hello, <name>!"`.
4. When you are satisfied, signal completion from the worktree:

   ```sh
   touch .eval-done
   ```

The run then finishes with `final_status: completed_interactive` and the
verifier checks the resulting file. If you never touch `.eval-done`, the run is
marked `budget_exceeded` once `max_wall_seconds` elapses.
