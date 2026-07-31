"""Shared SubagentPool.run_all spies for the unified prose-refresh fan-out.

After the schema-v2 flip the narrator / code_reader / synthesizer /
package_reader fan-outs collapsed into ONE ``role == "prose_refresher"``
dispatch whose items are ``ProseRefreshTask``s and whose per-item value is a
``ProseRefreshResult``. ``build_refresh_result`` synthesizes a healthy result
from the on-disk page (mirroring what the real agent would return); the spy
factories below patch ``SubagentPool.run_all`` the way the old
``_narrate_all_spy`` helpers did.

Also here: ``patch_repo_state`` — the three git probes (``changed_files_since``
for the File-map preserved-drop, ``diff_since``/``changed_names_since`` for the
prose gate) patched consistently from one changed-files description.
"""

from __future__ import annotations

from pathlib import Path

from graph_wiki_core.commands.scan_contract import ProseRefreshResult, ProseRefreshTask
from wiki_io.entity_writer import (
    dir_section_todo_contexts,
    file_map_todo_paths,
    is_overview_unfilled,
    is_todo_like_body,
)


def build_refresh_result(
    task: ProseRefreshTask,
    *,
    prose: str,
    descs=None,
) -> ProseRefreshResult:
    """Healthy ProseRefreshResult for ``task``.

    ``prose`` fills ``## Narrative`` and every TODO-like prose section (the old
    narrator + package_reader fills); File-map TODO rows, dir placeholders, and
    the overview are filled from the CURRENT on-disk page (the old code_reader
    + synthesizer fills). ``descs`` overrides the file-map description map:
    ``descs(task, todo_paths) -> dict``.
    """
    page = Path(task.page_path)
    # `prose` goes ONLY into the narrative; other TODO-like sections get a
    # static body so head-/scan-tagged prose never leaks into human sections
    # (which are not re-replaced once filled).
    sections = {"## Narrative": prose}
    sections.update(
        {
            heading: f"Filled body for {heading.removeprefix('## ')}."
            for heading, body in task.prose_sections.items()
            if heading != "## Narrative" and is_todo_like_body(body)
        }
    )
    todo_paths = file_map_todo_paths(page) if page.exists() else []
    if descs is not None:
        file_map = dict(descs(task, todo_paths))
    else:
        file_map = {p: f"desc {p}" for p in todo_paths}
    dir_todos = dir_section_todo_contexts(page) if page.exists() else []
    overview = "Overview prose." if page.exists() and is_overview_unfilled(page) else None
    return ProseRefreshResult(
        uri=task.uri,
        sections=sections,
        file_map_descriptions=file_map,
        dir_descriptions={c: f"dir desc {c or 'root'}" for c in dir_todos},
        overview=overview,
    )


def refresh_all_spy(
    prose_fn,
    *,
    descs_fn=None,
    recorder: dict | None = None,
    verdict_fn=None,
    propagate_verdict_fn=None,
):
    """Async ``SubagentPool.run_all`` replacement covering the post-flip roles.

    - ``prose_refresher`` -> ``build_refresh_result(t, prose=prose_fn(t), descs=descs_fn)``
    - ``drift_propagator`` -> ``propagate_verdict_fn(item)`` (default not-stale)

    When ``recorder`` is given, dispatched items are collected under
    ``prose_tasks`` / ``propagate_items`` so a test can assert a role was (not)
    dispatched.
    """

    async def _run_all(self, *, items, task, role, model_id, max_concurrency):
        from subagent_runtime.pool import FanOutResult

        result = FanOutResult()
        if role == "prose_refresher":
            if recorder is not None:
                recorder.setdefault("prose_tasks", []).extend(items)
            result.successes = [(t, build_refresh_result(t, prose=prose_fn(t), descs=descs_fn)) for t in items]
        elif role == "drift_propagator":
            if recorder is not None:
                recorder.setdefault("propagate_items", []).extend(items)
            fn = propagate_verdict_fn or (lambda it: {"stale": False, "findings": []})
            result.successes = [(it, fn(it)) for it in items]
        return result

    return _run_all


def _fake_hunks(paths: list[str]) -> str:
    return "".join(f"diff --git a/{p} b/{p}\n--- a/{p}\n+++ b/{p}\n@@ -1 +1 @@\n-old\n+new\n" for p in paths)


def patch_repo_state(monkeypatch, scan_mod, changed) -> None:
    """Patch ``changed_files_since`` + ``diff_since`` + ``changed_names_since``
    consistently on ``scan_mod``.

    ``changed`` is ``None`` (anchor unknown / history rewrite), ``[]`` (clean),
    a list of repo-relative changed paths, or a callable
    ``(sub_paths: list[str]) -> None | list[str]`` for per-scope behavior.
    """

    def _resolve(subs: list[str]):
        return changed(subs) if callable(changed) else changed

    def _files(repo, sha, sub):
        return _resolve([sub] if isinstance(sub, str) else list(sub))

    def _names(repo, sha, subs):
        return _resolve(list(subs))

    def _diff(repo, sha, subs):
        val = _resolve(list(subs))
        if val is None:
            return None
        return _fake_hunks(val) if val else ""

    monkeypatch.setattr(scan_mod, "changed_files_since", _files)
    monkeypatch.setattr(scan_mod, "changed_names_since", _names)
    monkeypatch.setattr(scan_mod, "diff_since", _diff)
