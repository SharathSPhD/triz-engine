"""TRIZ Arena leaderboard generator.

Reads ELO ratings and generates a LEADERBOARD.md with rankings table,
per-problem score heatmap, and per-dimension breakdown.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

PROVISIONAL_THRESHOLD = 6


def generate_leaderboard(
    ratings: dict[str, float],
    confidence_intervals: dict[str, dict[str, float]],
    problem_scores: dict[tuple[str, str], float],
    problem_ids: list[str],
    output_path: Path | str,
    match_count: int | None = None,
    dimension_scores: dict[tuple[str, str], dict] | None = None,
    min_matches: int = PROVISIONAL_THRESHOLD,
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

    is_provisional = match_count < min_matches

    lines = [
        "# TRIZ Arena Leaderboard",
        "",
    ]

    if is_provisional:
        lines.append(
            f"> **PROVISIONAL** — Only {match_count} matches recorded "
            f"(minimum {min_matches} for rated leaderboard)."
        )
        lines.append("")

    lines.extend([
        f"*Updated: {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')}*",
        "",
        "## Rankings",
        "",
        "| Rank | Participant | ELO Rating | 95% CI | Matches |",
        "|------|------------|------------|--------|---------|",
    ])

    for rank, (name, rating) in enumerate(rankings, 1):
        ci = confidence_intervals.get(name, {})
        ci_str = f"{ci.get('lower', 0):.0f}\u2013{ci.get('upper', 0):.0f}"
        lines.append(f"| {rank} | {name} | {rating:.0f} | {ci_str} | {match_count} |")

    lines.extend([
        "",
        "## Per-Problem Scores",
        "",
    ])

    header = "| Participant |" + " | ".join(problem_ids) + " | Mean | Coverage |"
    separator = "|------------|" + " | ".join(["----"] * len(problem_ids)) + " | ---- | ---- |"
    lines.append(header)
    lines.append(separator)

    for name in participants:
        scored_values = []
        score_strs = []
        for pid in problem_ids:
            key = (name, pid)
            if key in problem_scores:
                s = problem_scores[key]
                scored_values.append(s)
                score_strs.append(f"{s:.1f}")
            else:
                score_strs.append("—")
        mean = sum(scored_values) / len(scored_values) if scored_values else 0.0
        coverage = f"{len(scored_values)}/{len(problem_ids)}"
        lines.append(
            f"| {name} | " + " | ".join(score_strs)
            + f" | **{mean:.1f}** | {coverage} |"
        )

    if dimension_scores:
        lines.extend([
            "",
            "## Per-Dimension Averages",
            "",
            "| Participant | CI | PS | SN | CR | IFR |",
            "|------------|-----|-----|-----|-----|-----|",
        ])

        for name in participants:
            dims = {"ci": [], "ps": [], "sn": [], "cr": [], "ifr": []}
            for pid in problem_ids:
                key = (name, pid)
                if key not in dimension_scores:
                    continue
                d = dimension_scores[key]
                for dim_name in dims:
                    val = d.get(f"{dim_name}_raw", d.get(dim_name))
                    if val is not None:
                        dims[dim_name].append(val)
            avgs = {
                k: (sum(v) / len(v) if v else 0.0) for k, v in dims.items()
            }
            lines.append(
                f"| {name} | {avgs['ci']:.0f} | {avgs['ps']:.0f} | "
                f"{avgs['sn']:.0f} | {avgs['cr']:.0f} | {avgs['ifr']:.0f} |"
            )

    actual_problem_count = len(problem_ids)
    lines.extend([
        "",
        "## Methodology",
        "",
        "- **Scoring**: TRIZBENCH 5-dimension weighted rubric "
        "(CI 25% + PS 20% + SN 20% + CR 25% + IFR 10%)",
        "- **ELO**: Bradley-Terry model with K=32 initial, K=16 subsequent",
        "- **CI**: 95% bootstrap confidence intervals from 1000 resamples",
        f"- **Problems**: {actual_problem_count} TRIZBENCH problems evaluated",
        "",
    ])

    content = "\n".join(lines)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(content)
    return content


def _derive_score(data: dict) -> float | None:
    """Derive a 0-100 score from result data.

    Internal TRIZBENCH results have final_score directly.
    External TRIZBENCH results store contradiction_score + principle_score
    and need a composite score derived from those fields.
    """
    if "final_score" in data:
        return data["final_score"]

    if "contradiction_score" in data and "principle_score" in data:
        ct = data["contradiction_score"]
        ps = data["principle_score"]
        ct_score = (
            (20 if ct.get("type_correct") else 0)
            + (30 if ct.get("params_exact") else (15 if ct.get("params_partial") else 0))
        )
        f1 = ps.get("f1", 0.0) if isinstance(ps, dict) else 0.0
        return ct_score + f1 * 50  # max 100

    return None


def load_results(results_dir: Path) -> dict:
    """Load tournament results from JSON files in results/{participant}/ layout."""
    results = {}
    for f in sorted(results_dir.rglob("*.json")):
        if f.name.startswith("."):
            continue
        try:
            with open(f) as fh:
                data = json.load(fh)
            status = data.get("status", "success")
            if status != "success":
                continue
            if "participant" not in data:
                continue
            score = _derive_score(data)
            if score is None:
                continue
            key = (data["participant"], data["problem_id"])
            results[key] = score
        except (json.JSONDecodeError, KeyError):
            continue
    return results


def load_dimension_scores(results_dir: Path) -> dict:
    """Load per-dimension scores from result files."""
    dim_scores = {}
    for f in sorted(results_dir.rglob("*.json")):
        if f.name.startswith("."):
            continue
        try:
            with open(f) as fh:
                data = json.load(fh)
            if data.get("status", "success") != "success":
                continue
            key = (data["participant"], data["problem_id"])
            dim_scores[key] = data.get("scores", {}).get("dimensions", {})
        except (json.JSONDecodeError, KeyError):
            continue
    return dim_scores
