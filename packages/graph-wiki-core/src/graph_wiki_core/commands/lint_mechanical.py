"""Whole-wiki lint aggregation — the single lint aggregator (Bedrock-free).

scan(wiki, stale_days, log_gap_days, repo_path=None, optional_checks=None)
aggregates the canonical mechanical pass (wiki_io.lint_wiki.mechanical_scan)
with the code-drift block (heuristic package walk + exports drift), the
per-group drift checks (file_map, package_sync, domain_placement,
workflow_hints, concept_kind), the optional ``dependency_layer`` group, and
the fail-soft parity wrappers (guidance lint, work lifecycle, obsidian
render, scanner heading drift). print_report(r) renders the report.

One aggregation, two callers: ``gw lint`` (graph_wiki_core.commands.lint.
run_lint delegates its mechanical portion here) and the plugin script
plugins/graph-wiki/skills/graph-wiki/scripts/lint_wiki.py. Report parity
between the two surfaces is structural — both consume this module.

Import discipline (keystone invariant): this module imports only wiki_io.*,
work_io.*, guidance_io.*, workspace_io.*, and stdlib. It must NEVER import
graph_wiki_core.commands.lint (module-scope langchain) or anything else in
the [bedrock] extra's closure — the dependency points the other way.
"""

from __future__ import annotations

from pathlib import Path

from wiki_io.lint.concept_kind import check as check_concept_kind
from wiki_io.lint.dependency import check as check_dependency_layer
from wiki_io.lint.domain import check as check_domain_placement
from wiki_io.lint.file_map import check as check_file_map_drift
from wiki_io.lint.obsidian_render import check as check_obsidian_render
from wiki_io.lint.package_sync import check as check_package_sync_drift
from wiki_io.lint.scanner_heading import check as check_scanner_heading
from wiki_io.lint.workflow_hints import check as check_workflow_hints
from wiki_io.lint_wiki import mechanical_scan
from wiki_io.scan_monorepo import discover_workspaces as _scan_discover
from wiki_io.scan_monorepo import unscope as _unscope

_SKIPPED: dict = {"skipped": True}

OPTIONAL_GROUPS = {"dependency_layer"}


def scan(wiki, stale_days, log_gap_days, repo_path=None, optional_checks=None, include_pages=False):
    if not wiki.exists():
        raise SystemExit(f"[error] {wiki} not found")
    workspace = wiki.parent

    mech = mechanical_scan(wiki, stale_days, log_gap_days)
    pages = mech["pages"]

    # Code-drift check
    code_drift = _SKIPPED
    if repo_path and _scan_discover:
        try:
            # Unpinned discovery: the container layout block is gone (decontainerize),
            # so code-drift enumerates packages via the heuristic workspace walk.
            # In a multi-repo workspace, on-disk packages span every member root,
            # so enumerate the UNION across all members (``members or [repo_path]``
            # keeps single-repo byte-identical: iterate the one repo).
            from workspace_io.config import resolve as _resolve_cfg

            members = list(_resolve_cfg(repo_path, require_manifest=False).members) or [repo_path]
            workspaces = []
            for member in members:
                workspaces.extend(_scan_discover(member))
            # Normalize scoped names (``@psprowls/foo`` -> ``foo``) so the diff
            # compares like-for-like against vault slugs/titles.
            disk_names = {_unscope(w["name"]) for w in workspaces}

            # Package/app overview pages are folder-shorthand at
            # ``<container>/<slug>/overview.md`` — the slug we diff against
            # disk is the parent directory name, not the file stem. ``k`` has
            # already been stripped of its ``.md`` suffix upstream, so the
            # filename comparison is against ``"overview"`` (no extension).
            # Legacy ``<container>/<slug>/<slug>.md`` pages (pre-rename) are
            # still recognised as a fallback.
            def _pkg_slug(key: str) -> str | None:
                parts = Path(key).parts
                if len(parts) < 2:
                    return None
                name = parts[-1]
                parent = parts[-2]
                if name == "overview":
                    return parent
                if name == parent:
                    return parent
                return None

            def _entity_pkg_slug(fm: dict) -> str | None:
                """Slug for a graph-derived entities/ page (kind: package|app|agent_plugin).

                The workspace slug is the final path segment of the entity URI
                (``pkg:org/repo/alpha`` -> ``alpha``,
                ``agent_plugin:org/repo/graph-wiki`` -> ``graph-wiki``),
                unscoped to match disk names the same way legacy pages are compared.
                """
                if fm.get("kind") not in ("package", "app", "agent_plugin"):
                    return None
                uri = (fm.get("uri") or "").strip()
                if not uri:
                    return None
                tail = uri.rsplit("/", 1)[-1].rsplit(":", 1)[-1]
                return _unscope(tail) if tail else None

            def _slug_for(k: str, p: dict) -> str | None:
                """Resolve a vault page's package slug: legacy path-shorthand
                first, then the entity-page (kind+uri) form."""
                if p["fm"].get("category") in ("package", "app"):
                    return _pkg_slug(k)
                return _entity_pkg_slug(p["fm"])

            vault_pkg_pages = {k: p for k, p in pages.items() if _slug_for(k, p) is not None}
            vault_names = {slug for k, p in vault_pkg_pages.items() if (slug := _slug_for(k, p)) is not None}
            # Pages declaring ``status: planned`` are deliberately seeded
            # before the workspace exists on disk (e.g. ``graph-graph``).
            # Surface them
            # separately under ``planned_in_vault`` instead of drowning real
            # drift under false positives.
            planned_names = {
                slug
                for k, p in vault_pkg_pages.items()
                if p["fm"].get("status") == "planned" and (slug := _slug_for(k, p)) is not None
            }
            code_drift = {
                "packages_on_disk": len(disk_names),
                "packages_in_vault": len(vault_names),
                "missing_in_vault": sorted(disk_names - vault_names),
                "orphaned_in_vault": sorted((vault_names - disk_names) - planned_names),
                "planned_in_vault": sorted(planned_names),
            }
            # Check exports drift (apps usually don't define exports, so skip them)
            name_to_ws = {_unscope(w["name"]): w for w in workspaces}
            exports_drift = []
            for k, p in vault_pkg_pages.items():
                if p["fm"].get("category") == "app":
                    continue
                slug = _pkg_slug(k)
                if slug is None:
                    continue
                ws = name_to_ws.get(slug)
                if not ws:
                    continue
                vault_exports = p["fm"].get("exports", "").strip()
                disk_exports = ws.get("exports", [])
                if vault_exports and disk_exports:
                    # Naive: if frontmatter is set but differs in count
                    vault_list = [x.strip() for x in vault_exports.strip("[]").split(",") if x.strip()]
                    if len(vault_list) != len(disk_exports):
                        exports_drift.append(
                            {
                                "page": k,
                                "vault_count": len(vault_list),
                                "disk_count": len(disk_exports),
                            }
                        )
            code_drift["exports_drift"] = exports_drift
        except Exception as e:
            code_drift = {"error": str(e)}

    file_map_drift = _SKIPPED
    if repo_path:
        file_map_drift = check_file_map_drift(repo_path, pages)

    package_sync_drift = check_package_sync_drift(repo_path, wiki) if repo_path else _SKIPPED

    domain_placement = check_domain_placement(pages)
    workflow_hints_issues = check_workflow_hints(pages, workspace)
    concept_kind_issues = check_concept_kind(pages, wiki)

    # Optional check groups (gated behind --check). Default off; pass
    # --check dependency_layer to enable.
    enabled_optional = optional_checks or set()
    workspaces_for_lint = None
    if "dependency_layer" in enabled_optional and repo_path and _scan_discover:
        try:
            workspaces_for_lint = _scan_discover(repo_path)
        except Exception:
            workspaces_for_lint = None

    dependency_layer = (
        check_dependency_layer(pages, workspaces=workspaces_for_lint)
        if "dependency_layer" in enabled_optional
        else None
    )

    # Parity checks with graph_wiki_core's gw lint (run_lint_all). Each is
    # fail-soft in the code_drift style: an unexpected exception is surfaced
    # as {"error": "<msg>"} in that key — never swallowed, never fatal to the
    # pass. Expected absences (no guidance pages, no wiki/work/ dir) return
    # empty findings, not errors.
    def _fail_soft(fn):
        try:
            return fn()
        except Exception as e:  # noqa: BLE001 — per-check isolation is the point
            return {"error": str(e)}

    def _serialize_findings(findings):
        return [{"rule_id": f.rule_id, "severity": f.severity, "slug": f.slug, "message": f.message} for f in findings]

    def _obsidian_render():
        return _serialize_findings(check_obsidian_render({**pages, **mech["index_pages"]}))

    def _guidance_lint():
        import guidance_io.lint as _guidance_lint_mod

        return _serialize_findings(_guidance_lint_mod.run_lint(workspace))

    def _work_lifecycle():
        from work_io import lifecycle_lint as _lifecycle_lint
        from work_io import sidecar as _sidecar

        work_dir = wiki / "work"
        items = _lifecycle_lint.load_items(work_dir)
        findings = _lifecycle_lint.run_lint(
            items,
            repo_path,
            _sidecar.load_sidecar(wiki),
            workspace_root=workspace,
            archived_items=_lifecycle_lint.load_items(work_dir / "_archive"),
        )
        return {"total_items": len(items), "findings": _serialize_findings(findings)}

    obsidian_render_findings = _fail_soft(_obsidian_render)
    guidance_lint_findings = _fail_soft(_guidance_lint)
    work_lifecycle = _fail_soft(_work_lifecycle)
    scanner_heading_drift = _fail_soft(lambda: check_scanner_heading(pages))

    report = {
        "wiki": str(wiki),
        "total_pages": mech["total_pages"],
        "orphans": mech["orphans"],
        "broken_links": mech["broken_links"],
        "stale": mech["stale"],
        "missing_frontmatter": mech["missing_frontmatter"],
        "missing_tokens": mech["missing_tokens"],
        "source_path_drift": mech["source_path_drift"],
        "duplicate_titles": mech["duplicate_titles"],
        "log_gap": mech["log_gap"],
        "code_drift": code_drift,
        "file_map_drift": file_map_drift,
        "package_sync_drift": package_sync_drift,
        "domain_placement": domain_placement,
        "dependency_layer": dependency_layer,
        "workflow_hints": workflow_hints_issues,
        "concept_kind": concept_kind_issues,
        "obsidian_render_findings": obsidian_render_findings,
        "guidance_lint_findings": guidance_lint_findings,
        "work_lifecycle": work_lifecycle,
        "scanner_heading_drift": scanner_heading_drift,
    }
    if include_pages:
        # Internal callers (run_lint) need the parsed page dicts for the
        # semantic fan-out; the plugin's --json path must NOT serialize them.
        report["pages"] = pages
        report["index_pages"] = mech["index_pages"]
    return report


def print_report(r):
    print(f"Code Wiki health check — {r['wiki']}")
    print(f"Total pages: {r['total_pages']}")
    print()

    def header(label, count):
        sym = "OK" if count == 0 else "WARN"
        print(f"[{sym}] {label}: {count}")

    header("orphan pages", len(r["orphans"]))
    for p in r["orphans"][:20]:
        print(f"   - {p}")
    print()

    header("broken wikilinks", len(r["broken_links"]))
    for src, tgt in r["broken_links"][:20]:
        print(f"   - {src} -> [[{tgt}]]")
    print()

    header("stale pages", len(r["stale"]))
    for p, d in r["stale"][:20]:
        print(f"   - {p} (updated {d})")
    print()

    header("pages missing frontmatter", len(r["missing_frontmatter"]))
    for p in r["missing_frontmatter"][:20]:
        print(f"   - {p}")
    print()

    header("pages missing tokens field", len(r["missing_tokens"]))
    for p in r["missing_tokens"][:20]:
        print(f"   - {p}")
    if r["missing_tokens"]:
        print("   Token stamping is library-only; use an allowed delivery surface that calls update_vault().")
    print()

    header("duplicate titles", len(r["duplicate_titles"]))
    for title, keys in list(r["duplicate_titles"].items())[:10]:
        print(f"   - '{title}': {keys}")
    print()

    gap = r["log_gap"]
    if gap:
        print(f"[WARN] log gap: last entry {gap['last_entry']} ({gap['days_ago']} days ago)")
    else:
        print("[OK] log gap: recent")
    print()

    cd = r.get("code_drift")
    if isinstance(cd, dict) and cd.get("skipped"):
        print("[SKIP] code drift check (no repo root discovered)")
    elif cd:
        if cd.get("error"):
            print(f"[WARN] code drift check failed: {cd['error']}")
        else:
            print(f"Code drift: {cd['packages_on_disk']} entities on disk, {cd['packages_in_vault']} in vault")
            mw = cd.get("missing_in_vault", [])
            print(f"[{'WARN' if mw else 'OK'}] entities missing from vault: {len(mw)}")
            for n in mw[:10]:
                print(f"   + {n}  (run /graph-wiki:scan)")
            ow = cd.get("orphaned_in_vault", [])
            print(f"[{'WARN' if ow else 'OK'}] vault pages for non-existent entities: {len(ow)}")
            for n in ow[:10]:
                print(f"   - {n}  (archive or delete)")
            ed = cd.get("exports_drift", [])
            print(f"[{'WARN' if ed else 'OK'}] exports-frontmatter drift: {len(ed)}")
            for d in ed[:10]:
                print(f"   ~ {d['page']} (vault: {d['vault_count']}, disk: {d['disk_count']})")
    print()

    fmdrift = r.get("file_map_drift")
    if isinstance(fmdrift, dict) and fmdrift.get("skipped"):
        print("[SKIP] file map drift check (no repo root discovered)")
    else:
        header("file map drift issues", len(fmdrift))
        for issue in fmdrift[:20]:
            print(f"   - {issue}")
    print()

    psd = r.get("package_sync_drift")
    if isinstance(psd, dict) and psd.get("skipped"):
        print("[SKIP] package sync drift check (no repo root discovered)")
    else:
        header("package sync drift", len(psd))
        for issue in psd[:20]:
            print(f"   - {issue}")
    print()

    dplace = r.get("domain_placement", [])
    header("domain placement issues", len(dplace))
    for issue in dplace[:20]:
        print(f"   - {issue}")
    print()

    wh = r.get("workflow_hints", [])
    header("workflow_hints missing sub-pages", len(wh))
    for issue in wh[:20]:
        print(f"   - {issue}")
    print()

    ck = r.get("concept_kind", [])
    header("concept kind issues", len(ck))
    for issue in ck[:20]:
        print(f"   - {issue}")
    print()

    def _severity_summary(findings):
        counts: dict[str, int] = {}
        for f in findings:
            counts[f["severity"]] = counts.get(f["severity"], 0) + 1
        return ", ".join(f"{n} {sev}" for sev, n in sorted(counts.items())) or "0"

    def _finding_section(label, findings):
        """Render a parity-check section: {"error": ...} fail-soft dict or a
        list of {rule_id, severity, slug, message} finding dicts."""
        if isinstance(findings, dict):
            print(f"[WARN] {label} check failed: {findings['error']}")
        else:
            header(label, len(findings))
            if findings:
                print(f"   severities: {_severity_summary(findings)}")
            for f in findings[:20]:
                print(f"   - {f['slug']}: [{f['rule_id']}] {f['message']}")
        print()

    _finding_section("Obsidian render findings", r.get("obsidian_render_findings", []))
    _finding_section("Guidance lint findings", r.get("guidance_lint_findings", []))

    wl = r.get("work_lifecycle")
    if isinstance(wl, dict) and "error" in wl:
        print(f"[WARN] Work lifecycle check failed: {wl['error']}")
        print()
    else:
        wl = wl or {"total_items": 0, "findings": []}
        print(f"Work lifecycle: {wl['total_items']} items")
        _finding_section("Work lifecycle findings", wl["findings"])

    shd = r.get("scanner_heading_drift", [])
    if isinstance(shd, dict):
        print(f"[WARN] Scanner heading drift check failed: {shd['error']}")
    else:
        header("Scanner heading drift", len(shd))
        for issue in shd[:20]:
            print(f"   - {issue}")
    print()

    spd = r.get("source_path_drift", [])
    header("Source path drift", len(spd))
    for p in spd[:20]:
        print(f"   - {p}")
    print()

    findings = r.get("dependency_layer")
    if findings is None:
        print("[SKIP] dependency_layer (pass --check dependency_layer to enable)")
    else:
        header("dependency_layer findings", len(findings))
        for f in findings[:20]:
            print(f"   - {f}")
    print()
