# Deferred Items

Items discovered during execution that are out of scope for the triggering task.

---

## test_graph_query_output snapshot stale after 260530-gqp

**Discovered during:** Quick task 260530-hxy (Task 2 regression run)
**File:** `agents/graph-wiki-agent/tests/unit/test_commands_graph.py::test_graph_query_output`
**Issue:** Syrupy snapshot for `graph query --kind package` is stale. The 260530-gqp quick task added `dev_dependencies: []` to package node attrs, but the snapshot was not updated.
**Pre-existing:** Confirmed — failure present before 260530-hxy changes (verified via git stash).
**Fix:** Run `uv run pytest agents/graph-wiki-agent/tests/unit/test_commands_graph.py::test_graph_query_output --snapshot-update` to regenerate the snapshot.
