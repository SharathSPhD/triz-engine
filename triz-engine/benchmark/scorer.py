"""TRIZBENCH 5-dimension scorer.

Scoring dimensions and weights:
  CI  (Contradiction Identification) — 25%
  PS  (Principle Selection)          — 20%
  SN  (Solution Novelty)             — 20%
  CR  (Contradiction Resolution)     — 25%
  IFR (Ideal Final Result)           — 10%
"""

from __future__ import annotations


WEIGHTS = {"ci": 0.25, "ps": 0.20, "sn": 0.20, "cr": 0.25, "ifr": 0.10}


CR_RUBRIC = {
    "eliminates": 100.0,
    "reduces": 60.0,
    "manages": 32.0,
    "fails": 0.0,
}

SN_RUBRIC = {
    "non_obvious": 100.0,
    "novel_combination": 60.0,
    "standard": 32.0,
    "restatement": 0.0,
}


def score_ci(submission: dict, ground_truth: dict) -> float:
    """Score contradiction identification.

    Full marks for exact type + both params match (order-independent).
    Partial credit for type match + partial param match.
    Zero for wrong contradiction type.
    """
    if submission["contradiction_type"] != ground_truth["contradiction_type"]:
        return 0.0

    sub_params = {submission["triz_param_a"], submission["triz_param_b"]}
    gt_params = {ground_truth["triz_param_a"], ground_truth["triz_param_b"]}

    if sub_params == gt_params:
        return 100.0

    overlap = len(sub_params & gt_params)
    if overlap == 1:
        return 65.0

    return 30.0


def score_ps(submitted: list[int], target: list[int]) -> float:
    """Score principle selection using Jaccard similarity."""
    if not submitted and not target:
        return 100.0
    if not submitted or not target:
        return 0.0

    s_set = set(submitted)
    t_set = set(target)
    intersection = len(s_set & t_set)
    union = len(s_set | t_set)

    return (intersection / union) * 100.0 if union > 0 else 0.0


def score_cr(level: str) -> float:
    """Score contradiction resolution quality.

    Levels: eliminates (100), reduces (60), manages (32), fails (0).
    """
    return CR_RUBRIC.get(level.lower().strip(), 0.0)


def score_sn(level: str) -> float:
    """Score solution novelty.

    Levels: non_obvious (100), novel_combination (60), standard (32), restatement (0).
    """
    return SN_RUBRIC.get(level.lower().strip(), 0.0)


def score_ifr(ifr_value: int) -> float:
    """Score IFR proximity. Maps 0-4 scale to 0-100."""
    return max(0.0, min(100.0, ifr_value * 25.0))


def compute_final_score(
    ci: float, ps: float, sn: float, cr: float, ifr: float
) -> float:
    """Compute weighted final TRIZBENCH score.

    CI 25% + PS 20% + SN 20% + CR 25% + IFR 10% = 0-100.
    """
    return (
        WEIGHTS["ci"] * ci
        + WEIGHTS["ps"] * ps
        + WEIGHTS["sn"] * sn
        + WEIGHTS["cr"] * cr
        + WEIGHTS["ifr"] * ifr
    )
