"""Pre-flight cost estimator, hard cap enforcement, and BED-01 Bedrock ping.

Use `preflight_check()` as the single entry point before starting a matrix sweep.
It estimates cost, enforces the hard cap, pings Bedrock (unless skip_bed01=True),
and prompts for confirmation (unless auto_confirm=True).

Requirements: D-13 (conservative per-tier token constants), SWEEP-02 (BED-01 ping).
"""

from __future__ import annotations

HARD_CAP_USD = 25.0  # $25: 4x headroom over ~$6.19 estimated 24-cell matrix (RESEARCH.md §Tension 2)

# Conservative per-tier token constants (from RESEARCH.md §Tension 6)
_TIER_TOKENS: dict[str, tuple[int, int]] = {
    "cheap-fast": (3000, 500),  # scanner, code_reader
    "mid": (5000, 1000),        # linter, ingestor
    "quality": (8000, 2000),    # librarian, synthesizer
}

_ROLE_TIER: dict[str, str] = {
    "scanner":     "cheap-fast",
    "code_reader": "cheap-fast",
    "linter":      "mid",
    "ingestor":    "mid",
    "librarian":   "quality",
    "synthesizer": "quality",
}

from eval_harness.pricing import UnknownModelError, cost_for_usage
from model_adapter.exceptions import BedrockAccessDenied
from model_adapter.loader import make_llm


def estimate_sweep_cost(
    role_candidates: dict[str, list[str]],
    n_cases: int,
    repeats: int,
) -> float:
    """Pre-flight cost estimate using conservative per-tier token constants.

    Iterates all (role, model_id) pairs and sums cost_for_usage() results.
    Unknown model IDs (UnknownModelError) are silently skipped.

    Args:
        role_candidates: mapping of role name to list of candidate model IDs.
        n_cases: number of eval cases in the sweep.
        repeats: number of repeats per (role, candidate, case) cell.

    Returns:
        Aggregate estimated USD cost as a float.
    """
    total = 0.0
    for role, candidates in role_candidates.items():
        tier = _ROLE_TIER.get(role, "mid")
        tokens_in, tokens_out = _TIER_TOKENS[tier]
        for model_id in candidates:
            try:
                cell_cost = cost_for_usage(
                    model_id,
                    {
                        "input": tokens_in * n_cases * repeats,
                        "output": tokens_out * n_cases * repeats,
                    },
                )
                total += cell_cost
            except UnknownModelError:
                pass  # unknown model — skip from estimate
    return total


def preflight_bed01() -> None:
    """Perform a live BED-01 Bedrock connectivity ping using the preflight role.

    Invokes make_llm('preflight').invoke('ping') to confirm AWS credentials and
    Bedrock access before a potentially expensive sweep begins.

    Raises:
        SystemExit: with prefix "BED-01 FAILED:" when access is denied or any
                    exception occurs during the ping.

    Side-effect:
        Prints "[BED-01] Bedrock connectivity confirmed." to stdout on success.
    """
    try:
        make_llm("preflight").invoke("ping")
        print("[BED-01] Bedrock connectivity confirmed.")
    except BedrockAccessDenied as e:
        raise SystemExit(f"BED-01 FAILED: {e}") from e
    except Exception as e:
        raise SystemExit(f"BED-01 FAILED: {e}") from e


def preflight_check(
    role_candidates: dict[str, list[str]],
    n_cases: int,
    repeats: int,
    *,
    skip_bed01: bool = False,
    auto_confirm: bool = False,
) -> float:
    """Orchestrate pre-flight checks before a sweep matrix run.

    Steps:
    1. Estimate total cost via estimate_sweep_cost().
    2. Abort (SystemExit) if estimate exceeds HARD_CAP_USD.
    3. Run BED-01 Bedrock ping (unless skip_bed01=True).
    4. Prompt for confirmation (unless auto_confirm=True).

    Args:
        role_candidates: mapping of role name to list of candidate model IDs.
        n_cases: number of eval cases.
        repeats: number of repeats per cell.
        skip_bed01: if True, skip the live Bedrock ping (dry-run friendly).
        auto_confirm: if True, skip the interactive prompt (CI / dry-run friendly).

    Returns:
        The estimated cost float.

    Raises:
        SystemExit: if estimate exceeds HARD_CAP_USD, BED-01 fails, or user declines.
    """
    estimate = estimate_sweep_cost(role_candidates, n_cases, repeats)

    if estimate > HARD_CAP_USD:
        raise SystemExit(
            f"Estimated sweep cost ${estimate:.2f} exceeds hard cap "
            f"${HARD_CAP_USD:.2f} — aborting. Reduce candidates or repeats."
        )

    if not skip_bed01:
        preflight_bed01()

    if not auto_confirm:
        answer = input(f"Estimated cost: ${estimate:.2f}, proceed? [y/N] ")
        if answer not in {"y", "Y", "yes"}:
            raise SystemExit("Sweep aborted by user.")

    return estimate
