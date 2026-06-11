"""cc-eval CLI: list / run / report subcommands."""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Optional

import typer
from rich.console import Console
from rich.table import Table

from claude_code_evals.orchestrator import run_one
from claude_code_evals.report import build_report
from claude_code_evals.schemas import Config, Runset, Scenario

console = Console()

app = typer.Typer(
    name="cc-eval",
    help="cc-eval — Claude Code eval harness CLI.",
    no_args_is_help=True,
)


def _resolve_evals_root(evals_root: str | None) -> Path:
    if evals_root:
        return Path(evals_root)
    env = os.environ.get("CLAUDE_CODE_EVALS_ROOT")
    if env:
        return Path(env)
    return Path.cwd()


@app.command("list")
def list_cmd(
    evals_root: Optional[str] = typer.Option(None, "--evals-root", help="Path to evals/ directory"),
) -> None:
    """Print available scenarios and configs."""
    root = _resolve_evals_root(evals_root)
    scenarios_dir = root / "scenarios"
    configs_dir = root / "configs"

    table = Table(title="Scenarios")
    table.add_column("Name")
    table.add_column("Isolation")
    table.add_column("Eval mode")
    if scenarios_dir.exists():
        for s_dir in sorted(scenarios_dir.iterdir()):
            yaml_path = s_dir / "scenario.yaml"
            if yaml_path.exists():
                s = Scenario.from_path(yaml_path)
                table.add_row(s.name, s.isolation_mode, s.eval_mode)
    console.print(table)

    cfg_table = Table(title="Configs")
    cfg_table.add_column("Name")
    cfg_table.add_column("Model")
    if configs_dir.exists():
        for c_path in sorted(configs_dir.glob("*.yaml")):
            c = Config.from_path(c_path)
            cfg_table.add_row(c.name, c.model)
    console.print(cfg_table)


@app.command("run")
def run_cmd(
    scenario: Optional[str] = typer.Argument(None, help="Scenario name"),
    configs: Optional[list[str]] = typer.Option(None, "--config", help="Config name(s), repeatable"),
    runset: Optional[str] = typer.Option(None, "--runset", help="Path to runset YAML"),
    evals_root: Optional[str] = typer.Option(None, "--evals-root", help="Path to evals/ directory"),
    dry_run: bool = typer.Option(False, "--dry-run", help="Skip actual claude invocation"),
    keep_worktree: bool = typer.Option(False, "--keep-worktree", help="Keep isolation directory after run"),
) -> None:
    """Run one scenario or a full runset."""
    root = _resolve_evals_root(evals_root)

    pairs: list[tuple[str, str]] = []
    if runset:
        rs = Runset.from_path(Path(runset))
        for s_name in rs.scenarios:
            for c_name in rs.default_configs or ["base"]:
                pairs.append((s_name, c_name))
    elif scenario:
        for c_name in configs or ["base"]:
            pairs.append((scenario, c_name))
    else:
        typer.echo("Error: Provide a SCENARIO or --runset PATH", err=True)
        raise typer.Exit(code=2)

    results = []
    for s_name, c_name in pairs:
        console.print(f"[cyan]Running[/cyan] {s_name} / {c_name}")
        s = Scenario.from_path(root / "scenarios" / s_name / "scenario.yaml")
        c = Config.from_path(root / "configs" / f"{c_name}.yaml")
        result = run_one(s, c, evals_root=root, dry_run=dry_run, keep_worktree=keep_worktree)
        passed = result.verify_result.get("success", False)
        status = "[green]PASS[/green]" if passed else "[red]FAIL[/red]"
        console.print(f"  {status}  ({result.final_status})  {result.run_dir}")
        if not passed:
            reason = result.error_reason or result.verify_result.get("error")
            if not reason:
                for o in result.verify_result.get("verifiers", []):
                    if not o.get("passed"):
                        reason = f"{o.get('kind')}: {o.get('reason')}"
                        break
            if reason:
                console.print(f"    [yellow]reason:[/yellow] {reason}")
        results.append(result)

    if runset:
        runs_dir = root / "runs"
        md, data = build_report(runs_dir=runs_dir, runset_name=Path(runset).stem)
        report_path = root / "reports" / f"{Path(runset).stem}.md"
        report_path.parent.mkdir(parents=True, exist_ok=True)
        report_path.write_text(md)
        (report_path.with_suffix(".json")).write_text(json.dumps(data, indent=2))
        console.print(f"\n[bold]Report:[/bold] {report_path}")


@app.command("report")
def report_cmd(
    runs_dir: str = typer.Argument(..., help="Path to runs/ directory"),
    name: str = typer.Option("report", "--name", help="Runset name for report header"),
    out: Optional[str] = typer.Option(None, "--out", help="Output path for markdown report"),
) -> None:
    """Regenerate markdown + JSON report from existing runs/."""
    md, data = build_report(runs_dir=Path(runs_dir), runset_name=name)
    if out:
        Path(out).write_text(md)
        Path(out).with_suffix(".json").write_text(json.dumps(data, indent=2))
        console.print(f"Report written to {out}")
    else:
        console.print(md)
