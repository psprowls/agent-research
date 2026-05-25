# packages/code-graph-io

Python ≥3.11. Tests are pytest.

## Layout

- `src/graph_io/` — library + CLI
- `tests/` — pytest tests (unit + integration + CLI subprocess)
- `conftest.py` — pytest configuration

## Conventions

- Read-only queries always go through `store.read_only_connect()`.
- All updates run inside one SQLite transaction (`store.transaction()`).
- Errors go to stderr, JSON output goes to stdout. Never mix.
- Exit codes are stable from v1 forward — see `exit_codes.py`.

## Testing

`pytest tests/ -v` from the package root, or via the workspace from the repo root.
