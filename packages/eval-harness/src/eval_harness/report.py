"""Cost-frontier report and regression check for wiki query eval sweeps.

Provides:
    cost_frontier_table:        build a per-model quality/cost dict sorted by quality descending
    regression_check:           raise AssertionError if quality score is below threshold
    print_frontier:             format the frontier table as a plain-text string for display
    pareto_frontier:            return the non-dominated subset by (quality_score, cost_usd)
    render_role_doc:            render per-role markdown doc (D-12 skeleton)
    render_recommendation_block: emit the models.toml TOML comment block (D-11)
    render_index_md:            render INDEX.md linking all 6 role docs

These functions are deterministic (no Bedrock calls) and safe to call in any context.
"""

from __future__ import annotations

from pathlib import Path

from eval_harness.sweep import SweepResult


def cost_frontier_table(results: list[SweepResult]) -> dict[str, dict]:
    """Build a per-model cost/quality table from sweep results.

    Only includes results with status="ok". Results with status="error" are excluded.

    Quality score is extracted from result.judge_scores["mean"] when judge scoring
    has been run. Falls back to structural has_citation (1.0 if True, 0.0 if False)
    when judge_scores is None.

    Args:
        results: List of SweepResult from run_sweep().

    Returns:
        dict[str, dict] preserving insertion order (Python 3.7+ guarantee),
        sorted by quality_score descending. Each value has keys:
            quality_score (float), cost_usd (float | None),
            pages_drilled (int), wall_seconds (float), structural_pass (bool).
    """
    rows: list[tuple[str, dict]] = []

    for result in results:
        if result.status != "ok":
            continue

        # Quality score: judge mean if available, else structural fallback
        if result.judge_scores is not None:
            quality_score = float(result.judge_scores["mean"])
        else:
            # Structural fallback: has_citation indicator
            quality_score = 1.0 if result.structural.get("has_citation") else 0.0

        # structural_pass: True if all bool values in structural dict are True
        structural_pass = all(
            v for v in result.structural.values() if isinstance(v, bool)
        )

        row = {
            "quality_score": quality_score,
            "cost_usd": result.cost_usd,
            "pages_drilled": result.pages_drilled,
            "wall_seconds": result.wall_seconds,
            "structural_pass": structural_pass,
        }
        rows.append((result.model_id, row))

    # Sort by quality_score descending (highest quality first)
    rows.sort(key=lambda pair: pair[1]["quality_score"], reverse=True)
    return dict(rows)


def regression_check(score: float, threshold: float = 0.5) -> None:
    """Assert that a quality score meets the minimum threshold.

    Intended for use in pytest-evals analysis functions as the CI quality gate
    (EVAL-09). Raises AssertionError with a structured message so pytest captures
    it as a test failure rather than an error.

    Args:
        score:     Quality score (0.0–1.0).
        threshold: Minimum acceptable quality (default 0.5).

    Raises:
        AssertionError: if score < threshold, with message containing
                        "below threshold" for test matching.
    """
    if score < threshold:
        raise AssertionError(
            f"Quality score {score:.3f} below threshold {threshold:.3f}"
        )


def print_frontier(table: dict[str, dict]) -> str:
    """Format the cost frontier table as a plain-text string.

    Columns: model_id, quality_score, cost_usd, pages_drilled.
    Returns the string — caller is responsible for printing.

    Args:
        table: Output of cost_frontier_table().

    Returns:
        Formatted multi-line string with header and one row per model.
    """
    if not table:
        return "(no results)\n"

    header = f"{'model_id':<45} {'quality':>8} {'cost_usd':>10} {'pages':>6}"
    divider = "-" * len(header)
    lines = [header, divider]

    for model_id, row in table.items():
        quality = f"{row['quality_score']:.3f}"
        cost = f"${row['cost_usd']:.5f}" if row["cost_usd"] is not None else "   N/A"
        pages = str(row["pages_drilled"])
        lines.append(f"{model_id:<45} {quality:>8} {cost:>10} {pages:>6}")

    return "\n".join(lines) + "\n"


# ---------------------------------------------------------------------------
# Phase 7 additions: Pareto frontier + per-role doc renderers (SWEEP-03/04)
# ---------------------------------------------------------------------------


def pareto_frontier(table: dict[str, dict]) -> dict[str, dict]:
    """Return the non-dominated subset of table by (quality_score, cost_usd).

    A point is dominated if another point has >= quality AND <= cost AND is
    strictly better on at least one dimension.  Entries with cost_usd=None are
    never considered dominated (cost unknown — cannot compare).

    Algorithm: O(n^2) pairwise dominance check.

    Args:
        table: dict[model_id, row] where row has "quality_score" (float) and
               "cost_usd" (float | None).  Typically the output of
               cost_frontier_table().

    Returns:
        Subset of table containing only non-dominated entries, preserving
        insertion order.
    """
    rows = list(table.items())
    dominated: set[str] = set()

    for i, (mid_i, row_i) in enumerate(rows):
        for j, (mid_j, row_j) in enumerate(rows):
            if i == j:
                continue
            q_i = row_i["quality_score"]
            c_i = row_i["cost_usd"]
            q_j = row_j["quality_score"]
            c_j = row_j["cost_usd"]

            # Skip if either entry has unknown cost — cannot dominate or be dominated
            if c_i is None or c_j is None:
                continue

            # j dominates i if j has >= quality AND <= cost AND strictly better on one
            if q_j >= q_i and c_j <= c_i and (q_j > q_i or c_j < c_i):
                dominated.add(mid_i)

    return {k: v for k, v in table.items() if k not in dominated}


def render_recommendation_block(
    role: str,
    run_date: str,
    frontier: dict[str, dict],
    current_default: str,
) -> str:
    """Emit the TOML comment block for manual paste into models.toml (D-11).

    Shape (locked per D-11):
        # Sweep candidates (run YYYY-MM-DD): pareto-frontier members
        #   - <model_id>                                       (cost=$X.XXXX, quality=0.XX)
        # Previous default: <current_default>

    model_ids are left-padded to 50 characters for alignment.  cost_usd=None
    entries show "N/A" for the cost field.

    Args:
        role:            Agent role name (unused in block text but available to callers).
        run_date:        ISO date string (e.g. "2026-05-16").
        frontier:        Output of pareto_frontier() — keys are model_ids, values have
                         "quality_score" and "cost_usd".
        current_default: The model_id currently in models.toml for this role.

    Returns:
        Multi-line string where every line starts with "#".
    """
    lines = [f"# Sweep candidates (run {run_date}): pareto-frontier members"]
    for model_id, row in frontier.items():
        q = row["quality_score"]
        c = row["cost_usd"]
        cost_str = f"${c:.4f}" if c is not None else "N/A"
        lines.append(f"#   - {model_id:<50} (cost={cost_str}, quality={q:.2f})")
    lines.append(f"# Previous default: {current_default}")
    return "\n".join(lines)


def render_role_doc(
    role: str,
    tier: str,
    candidates: list[str],
    sweep_results: list[SweepResult],
    divergence_results: dict | None,
    run_date: str,
    commit_sha: str,
    total_cost_usd: float,
    two_gate_outcomes: "dict | None" = None,
) -> str:
    """Render per-role markdown doc per D-12 skeleton.

    Sections (in order):
        1. Heading: "# Sweep: {role} ({tier} tier)"
        2. "## Candidates" — list of 4 candidate model_ids
        3. "## Raw Scores" — markdown table with per-model aggregated metrics
        4. "## Pareto Frontier" — non-dominated points + cheapest callout
        5. "## Recommendation" — TOML comment block fenced as ```toml
        6. "## Run Metadata" — date, commit SHA, total cost

    The recommendation block uses the first (highest-quality) frontier member's
    model_id as the "cheapest on frontier" callout when costs are known.

    Args:
        role:              Agent role name (e.g. "librarian").
        tier:              Tier string (e.g. "quality", "mid", "cheap-fast").
        candidates:        List of candidate model_ids swept for this role.
        sweep_results:     List of SweepResult from run_role_sweep() across all cells.
        divergence_results: Per-rule failure counts or None (D-08 roles).
        run_date:          ISO date string.
        commit_sha:        Short git SHA of the sweep run.
        total_cost_usd:    Total USD spent across all cells (0.0 for dry-run).
        two_gate_outcomes: Optional dict[model_id, TwoGateOutcome] for qualified column.

    Returns:
        Markdown string. Pure function — no filesystem writes.
    """
    # Build per-candidate aggregated rows for the raw scores table.
    # Group results by model_id, then compute mean quality + total cost.
    from collections import defaultdict

    groups: dict[str, list[SweepResult]] = defaultdict(list)
    for r in sweep_results:
        if r.status == "ok":
            groups[r.model_id].append(r)

    # Build cost frontier table from results (quality_score, cost_usd per candidate)
    table = cost_frontier_table(sweep_results)
    frontier = pareto_frontier(table)

    # Determine current default for the recommendation block.
    # Use the first candidate as a stand-in when no explicit default is provided.
    current_default = candidates[0] if candidates else "unknown"

    # -----------------------------------------------------------------------
    # Section 1: Heading
    # -----------------------------------------------------------------------
    parts: list[str] = [
        f"# Sweep: {role} ({tier} tier)",
        "",
    ]

    # -----------------------------------------------------------------------
    # Section 2: Candidates
    # -----------------------------------------------------------------------
    parts.append("## Candidates")
    parts.append("")
    for mid in candidates:
        parts.append(f"- `{mid}`")
    parts.append("")

    # -----------------------------------------------------------------------
    # Section 3: Raw Scores
    # -----------------------------------------------------------------------
    parts.append("## Raw Scores")
    parts.append("")
    header_cols = (
        "| model_id | quality_mean | quality_std | cost_per_run_usd"
        " | n_cases | divergence_failures | gate1 | gate2 | qualified |"
    )
    parts.append(header_cols)
    parts.append("|---|---|---|---|---|---|---|---|---|")

    for mid in candidates:
        runs = groups.get(mid, [])
        if runs:
            qualities = []
            for r in runs:
                if r.judge_scores is not None:
                    qualities.append(float(r.judge_scores["mean"]))
                else:
                    qualities.append(1.0 if r.structural.get("has_citation") else 0.0)
            q_mean = sum(qualities) / len(qualities) if qualities else 0.0
            if len(qualities) > 1:
                variance = sum((q - q_mean) ** 2 for q in qualities) / len(qualities)
                q_std = variance ** 0.5
                q_std_str = f"{q_std:.3f}"
            else:
                q_std_str = "n/a"

            costs = [r.cost_usd for r in runs if r.cost_usd is not None]
            avg_cost = sum(costs) / len(costs) if costs else None
            cost_str = f"${avg_cost:.4f}" if avg_cost is not None else "n/a"
            n_cases = len(runs)
        else:
            q_mean = 0.0
            q_std_str = "n/a"
            cost_str = "n/a"
            n_cases = 0

        # Divergence failures column
        if divergence_results and mid in divergence_results:
            div_str = str(divergence_results[mid])
        elif divergence_results is None:
            div_str = "n/a"
        else:
            div_str = "0"

        # Gate columns from two_gate_outcomes
        if two_gate_outcomes and mid in two_gate_outcomes:
            outcome = two_gate_outcomes[mid]
            gate1 = "PASS" if outcome.gate1_passed else ("FAIL" if outcome.gate1_passed is False else "n/a")
            gate2 = "PASS" if outcome.gate2_passed else ("FAIL" if outcome.gate2_passed is False else "n/a")
            qualified = "YES" if outcome.qualified else "NO"
        else:
            gate1 = "n/a"
            gate2 = "n/a"
            qualified = "n/a"

        safe_mid = mid.replace("|", "\\|")
        parts.append(
            f"| `{safe_mid}` | {q_mean:.3f} | {q_std_str}"
            f" | {cost_str} | {n_cases} | {div_str} | {gate1} | {gate2} | {qualified} |"
        )

    parts.append("")

    # -----------------------------------------------------------------------
    # Section 4: Pareto frontier
    # -----------------------------------------------------------------------
    parts.append("## Pareto frontier")
    parts.append("")
    if frontier:
        for mid, row in frontier.items():
            q = row["quality_score"]
            c = row["cost_usd"]
            cost_display = f"${c:.4f}" if c is not None else "N/A"
            parts.append(f"- `{mid}` (quality={q:.2f}, cost={cost_display})")
        # Cheapest on frontier callout
        known_cost = {k: v for k, v in frontier.items() if v["cost_usd"] is not None}
        if known_cost:
            cheapest_id = min(known_cost, key=lambda k: known_cost[k]["cost_usd"])
            parts.append("")
            parts.append(f"**Cheapest on frontier:** `{cheapest_id}`")
    else:
        parts.append("_(no results)_")
    parts.append("")

    # -----------------------------------------------------------------------
    # Section 5: Recommendation (TOML comment block, fenced)
    # -----------------------------------------------------------------------
    parts.append("## Recommendation")
    parts.append("")
    rec_block = render_recommendation_block(
        role=role,
        run_date=run_date,
        frontier=frontier,
        current_default=current_default,
    )
    parts.append("```toml")
    parts.append(rec_block)
    parts.append("```")
    parts.append("")

    # -----------------------------------------------------------------------
    # Section 6: Run Metadata
    # -----------------------------------------------------------------------
    parts.append("## Run Metadata")
    parts.append("")
    parts.append(f"- **Date:** {run_date}")
    parts.append(f"- **Commit SHA:** `{commit_sha}`")
    parts.append(f"- **Total cost:** ${total_cost_usd:.4f}")
    parts.append(f"- **Cases:** {sum(len(v) for v in groups.values())}")
    parts.append("")

    return "\n".join(parts)


def render_index_md(
    role_doc_paths: "list[Path] | list[str]",
    run_date: str,
    total_cost_usd: float,
    story_path: "str | None" = None,
) -> str:
    """Render INDEX.md linking all per-role sweep docs.

    Args:
        role_doc_paths: List of Path or str paths to per-role docs
                        (e.g. [".planning/sweep/librarian.md", ...]).
        run_date:       ISO date string for the sweep run.
        total_cost_usd: Total USD spent across all cells.
        story_path:     Optional path to the cost-story doc (STORY.md). When
                        provided, a "See also" line is added.

    Returns:
        Markdown string. Pure function — no filesystem writes.
    """
    parts: list[str] = [
        "# Cost-Frontier Sweep: Index",
        "",
        f"**Run date:** {run_date}  ",
        f"**Total cost:** ${total_cost_usd:.4f}",
        "",
        "## Per-Role Results",
        "",
    ]

    for p in role_doc_paths:
        path_obj = Path(p) if not isinstance(p, Path) else p
        role_name = path_obj.stem  # filename without extension
        parts.append(f"- [{role_name}]({path_obj.name})")

    parts.append("")

    if story_path is not None:
        parts.append(f"See also: [Cost story]({story_path})")
        parts.append("")

    return "\n".join(parts)
