import subprocess

from graph_wiki_core.commands._repo_gates import compute_state_gates


def _mk(root, name):
    d = root / name
    d.mkdir(parents=True)
    (d / "f.txt").write_text("x")
    subprocess.run(["git", "init", "-q"], cwd=d, check=True)
    subprocess.run(["git", "add", "-A"], cwd=d, check=True)
    subprocess.run(["git", "-c", "user.email=t@t", "-c", "user.name=t", "commit", "-qm", "i"], cwd=d, check=True)
    return d


def test_compute_state_gates_one_per_member(tmp_path):
    ws = tmp_path / "workspace"
    ws.mkdir()
    a = _mk(tmp_path, "alpha")
    b = _mk(tmp_path, "beta")
    gates = compute_state_gates([a, b], workspace=ws)
    assert set(gates) == {"local/alpha", "local/beta"}
    assert all(g["head_commit"] for g in gates.values())
    # Full gate-dict contract is load-bearing downstream.
    assert all("allowed" in g and "reason" in g for g in gates.values())
