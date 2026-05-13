"""VAULT-04 round-trip gate.

Reading every fixture page with python-frontmatter and re-writing it via the
ported `update_tokens.update_vault` must produce byte-identical output on the
second pass. The first pass may stamp `tokens:` keys (mutating files). The
second pass must be fully idempotent: no files updated, byte-identical content.
"""

from __future__ import annotations

import hashlib
import shutil
import subprocess
from pathlib import Path


def _hash_tree(root: Path) -> dict[str, str]:
    """Return {relative-path: sha256-hex} for every file under root."""
    digests: dict[str, str] = {}
    for p in sorted(root.rglob("*")):
        if not p.is_file():
            continue
        rel = str(p.relative_to(root))
        digests[rel] = hashlib.sha256(p.read_bytes()).hexdigest()
    return digests


def test_round_trip_all_fixture_pages(round_trip_vault: Path, tmp_path: Path):
    """VAULT-04: second pass of update_vault must be byte-identical to first-pass output.

    Procedure:
      1. Copy fixture vault to tmp.
      2. First pass: update_vault stamps tokens (may mutate files).
      3. Hash the tree.
      4. Second pass: update_vault must report empty 'updated' list AND leave bytes unchanged.
      5. Verify both invariants.

    Additionally: a `git diff --no-index` against the original fixture shows any drift
    introduced by the FIRST pass (informational; the strong invariant is second-pass
    idempotency).
    """
    from vault_io.update_tokens import update_vault

    copy = tmp_path / "vault"
    shutil.copytree(round_trip_vault, copy)

    # First pass: stamps tokens onto fixture pages that lack a stable tokens field.
    update_vault(copy)

    # Snapshot bytes after first pass.
    before = _hash_tree(copy)

    # Second pass: MUST be a no-op.
    result = update_vault(copy)
    assert result["updated"] == [], f"Second pass should be idempotent but reported updates: {result['updated'][:5]}"

    # Strong invariant: byte-identical tree before and after second pass.
    after = _hash_tree(copy)
    assert before == after, "Tree hashes drifted on second pass — update_vault is not idempotent."

    # Informational: surface any drift between original fixture and copy after pass 1.
    # We don't fail on this; pass 1 is expected to stamp tokens. But the diff command
    # being available is part of the VAULT-04 gate spec.
    diff = subprocess.run(
        ["git", "diff", "--no-index", "--stat", str(round_trip_vault), str(copy)],
        capture_output=True,
        text=True,
    )
    # No assertion on diff.returncode — pass 1 may legitimately change `tokens:` values.
    # The assertions above (idempotency + empty updated list on pass 2) are the gate.
    _ = diff
