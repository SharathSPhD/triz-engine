"""TRIZ Arena leaderboard generator.

Reads ELO ratings and generates a LEADERBOARD.md with rankings table
and per-problem score heatmap.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path


def generate_leaderboard(
    ratings: dict[str, float],
    confidence_intervals: dict[str, dict[str, float]],
    problem_scores: dict[tuple[str, str], float],
    problem_ids: list[str],
    output_path: Path | str,
    match_count: int | None = None,
) -> str:
    """Generate LEADERBOARD.md from tournament results.

    Returns the markdown content as a string and writes to output_path.
    """
    output_path = Path(output_path)
    rankings = sorted(ratings.items(), key=lambda x: x[1], reverse=True)
    participants = [name for name, _ in rankings]

    n_participants = len(participants)
    if match_count is None:
        match_count = len(problem_ids) * (n_participants - 1) if n_participants > 1 else 0

    lines = [
        "# TRIZ Arena Leaderboard",
        "",
        f"*Updated: {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')}*",
        "",
        "## Rankings",
        "",
        "| Rank | Participant | ELO Rating | 95% CI | Matches |",
        "|------|------------|------------|--------|---------|",
    ]

    for rank, (name, rating) in enumerate(rankings, 1):
        ci = confidence_intervals.get(name, {})
        ci_str = f"{ci.get('lower', 0):.0f}–{ci.get('upper', 0):.0f}"
        lines.append(f"| {rank} | {name} | {rating:.0f} | {ci_str} | {match_count} |")

    lines.extend([
        "",
        "## Per-Problem Scores",
        "",
    ])

    header = "| Participant |" + " | ".join(problem_ids) + " | Mean |"
    separator = "|------------|" + " | ".join(["----"] * len(problem_ids)) + " | ---- |"
    lines.append(header)
    lines.append(separator)

    for name in participants:
        scores = []
        for pid in problem_ids:
            s = problem_scores.get((name, pid), 0.0)
            scores.append(s)
        mean = sum(scores) / len(scores) if scores else 0.0
        score_strs = [f"{s:.1f}" for s in scores]
        lines.append(f"| {name} | " + " | ".join(score_strs) + f" | **{mean:.1f}** |")

    lines.extend([
        "",
        "## Methodology",
        "",
        "- **Scoring**: TRIZBENCH 5-dimension weighted rubric "
        "(CI 25% + PS 20% + SN 20% + CR 25% + IFR 10%)",
        "- **ELO**: Bradley-Terry model with K=32 initial, K=16 subsequent",
        "- **CI**: 95% bootstrap confidence intervals from 1000 permutations",
        "- **Problems**: 12 canonical TRIZBENCH problems (TB-01 through TB-12)",
        "",
    ])

    content = "\n".join(lines)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(content)
    return content


def load_results(results_dir: Path) -> dict:
    """Load tournament results from JSON files in a results directory."""
    results = {}
    for f in sorted(results_dir.glob("*.json")):
        with open(f) as fh:
            data = json.load(fh)
            key = (data["participant"], data["problem_id"])
            results[key] = data.get("final_score", 0.0)
    return results
