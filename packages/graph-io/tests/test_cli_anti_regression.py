"""SC#5 anti-regression: existing cg subcommands still exit 0 after Phase 33.

Seeds a minimal repo with a Python package + pyproject + domains.yaml +
executable script, then runs `cg update --full` once. Each parametrized
test then runs one of the 13 pre-existing subcommands with reasonable
args resolved from the seeded DB and asserts a 0 exit code.

The 7 subcommands listed in SC#5 are covered by
`test_pre_existing_subcommand_exits_zero`. The other 6 pre-existing
subcommands not in SC#5 are covered by
`test_unlisted_pre_existing_subcommand_exits_zero` as a bonus assertion
(D-16). Any subcommand that genuinely requires complex setup beyond the
fixture is marked xfail with a documented reason rather than removed.
"""

from __future__ import annotations

import json
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path

import pytest

from _git_repo import init_repo, write_and_commit


def _run_cli(args: list[str], cwd: Path) -> subprocess.CompletedProcess:
    return subprocess.run(
        [
            sys.executable,
            "-m",
            "graph_io.cli.main",
            "--repo",
            str(cwd),
            "--mode",
            "test",
            *args,
        ],
        capture_output=True,
        text=True,
    )


@dataclass(frozen=True)
class FixtureRefs:
    repo_dir: Path
    package_name: str
    file_path: str
    symbol_id: str


@pytest.fixture(scope="module")
def post_phase33_fixture(tmp_path_factory) -> FixtureRefs:
    repo_dir = tmp_path_factory.mktemp("anti_regression")
    init_repo(repo_dir)
    write_and_commit(
        repo_dir,
        {
            "pyproject.toml": (
                "[project]\n"
                'name = "sample-pkg"\n'
                'version = "0.1.0"\n'
                "[project.scripts]\n"
                'sample-cli = "sample_pkg.cli:main"\n'
            ),
            "src/sample_pkg/__init__.py": "",
            "src/sample_pkg/cli.py": "def main():\n    return 0\n",
            "src/sample_pkg/util.py": "def helper():\n    return 1\n",
            "scripts/run.py": "#!/usr/bin/env python\nprint('go')\n",
            "domains.yaml": "core:\n  packages: [sample-pkg]\n",
        },
        "init",
    )
    # Make scripts/run.py executable (matches Phase 30 file role detection).
    (repo_dir / "scripts" / "run.py").chmod(0o755)

    result = _run_cli(["update", "--full"], repo_dir)
    assert result.returncode == 0, f"seed update failed: {result.stderr}"

    # Resolve a known-good package, file, and symbol from the seeded DB so
    # the parametrized assertions never use brittle hardcoded names.
    find_func = _run_cli(["--fmt", "json", "find", "--name", "main"], repo_dir)
    assert find_func.returncode == 0, find_func.stderr
    funcs = json.loads(find_func.stdout or "[]")
    assert funcs, "fixture did not produce any 'main' symbol"
    symbol_id = funcs[0]["name"]
    file_path = funcs[0]["path"]

    return FixtureRefs(
        repo_dir=repo_dir,
        package_name="sample-pkg",
        file_path=file_path,
        symbol_id=symbol_id,
    )


# SC#5-listed subcommands (D-16 primary anti-regression).
@pytest.mark.parametrize(
    "kind",
    [
        "update",
        "find",
        "status",
        "describe-package",
        "describe-path",
        "callers",
        "callees",
    ],
)
def test_pre_existing_subcommand_exits_zero(
    post_phase33_fixture: FixtureRefs, kind: str
) -> None:
    refs = post_phase33_fixture
    args_by_cmd: dict[str, list[str]] = {
        "update": ["update", "--full"],
        "find": ["find", "--name", "main"],
        "status": ["status"],
        "describe-package": ["describe-package", refs.package_name],
        "describe-path": ["describe-path", refs.file_path],
        "callers": ["callers", refs.symbol_id],
        "callees": ["callees", refs.symbol_id],
    }
    result = _run_cli(args_by_cmd[kind], refs.repo_dir)
    assert result.returncode == 0, (
        f"cg {' '.join(args_by_cmd[kind])} regressed: stderr={result.stderr}"
    )


def test_find_positional_form_errors(post_phase33_fixture: FixtureRefs) -> None:
    """D-11: `cg find <name>` positional form must produce a parse error.

    Guards against silent regression — without this, a future refactor that
    re-added `parser.add_argument("name")` would pass every other test
    (they all use --name now).
    """
    refs = post_phase33_fixture
    result = _run_cli(["find", "foo.py"], refs.repo_dir)
    assert result.returncode != 0, (
        f"positional `cg find foo.py` should error, got rc=0: {result.stdout}"
    )
    assert "unrecognized arguments" in result.stderr.lower(), result.stderr


# Bonus assertion (D-16) — covers the 6 pre-existing subcommands not
# listed in SC#5. sync-wiki requires a configured wiki target so we
# mark it xfail rather than synthesize one.
@pytest.mark.parametrize(
    "kind",
    ["imports", "imported-by", "exports", "exported-by", "dump", "sync-wiki"],
)
def test_unlisted_pre_existing_subcommand_exits_zero(
    post_phase33_fixture: FixtureRefs, kind: str
) -> None:
    refs = post_phase33_fixture
    if kind == "sync-wiki":
        pytest.xfail("sync-wiki requires a configured wiki target; see Phase 14")
    args_by_cmd: dict[str, list[str]] = {
        "imports": ["imports", refs.file_path],
        "imported-by": ["imported-by", refs.file_path],
        "exports": ["exports", refs.file_path],
        "exported-by": ["exported-by", refs.symbol_id],
        "dump": ["dump"],
        "sync-wiki": ["sync-wiki"],
    }
    result = _run_cli(args_by_cmd[kind], refs.repo_dir)
    assert result.returncode == 0, (
        f"cg {' '.join(args_by_cmd[kind])} regressed: stderr={result.stderr}"
    )
