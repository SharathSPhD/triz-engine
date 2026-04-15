"""Bradley-Terry ELO rating system for TRIZ Arena.

Computes pairwise ELO ratings from TRIZBENCH scores across
participants and problems. Supports bootstrap confidence intervals.
"""

from __future__ import annotations

import math
import random
from dataclasses import dataclass, field


def expected_score(rating_a: float, rating_b: float) -> float:
    """Bradley-Terry expected score for player A against player B."""
    return 1.0 / (1.0 + math.pow(10.0, (rating_b - rating_a) / 400.0))


def update_ratings(
    rating_a: float, rating_b: float, score_a: float, k: float = 32
) -> tuple[float, float]:
    """Update ratings after a single match.

    score_a: 1.0 for A wins, 0.0 for B wins, 0.5 for draw.
    Returns (new_rating_a, new_rating_b).
    """
    ea = expected_score(rating_a, rating_b)
    eb = 1.0 - ea
    score_b = 1.0 - score_a

    new_a = rating_a + k * (score_a - ea)
    new_b = rating_b + k * (score_b - eb)
    return new_a, new_b


@dataclass
class EloCalculator:
    """Manages ELO ratings for multiple participants."""

    participants: list[str]
    initial_rating: float = 1000.0
    k_initial: float = 32.0
    k_subsequent: float = 16.0
    ratings: dict[str, float] = field(default_factory=dict)
    match_counts: dict[str, int] = field(default_factory=dict)
    history: list[dict] = field(default_factory=list)

    def __post_init__(self):
        if not self.ratings:
            self.ratings = {p: self.initial_rating for p in self.participants}
        if not self.match_counts:
            self.match_counts = {p: 0 for p in self.participants}

    def _k_for(self, participant: str) -> float:
        if self.match_counts[participant] == 0:
            return self.k_initial
        return self.k_subsequent

    def record_match(
        self, participant_a: str, participant_b: str, score_a: float
    ) -> None:
        """Record a match result and update ratings."""
        k = max(self._k_for(participant_a), self._k_for(participant_b))

        old_a = self.ratings[participant_a]
        old_b = self.ratings[participant_b]

        new_a, new_b = update_ratings(old_a, old_b, score_a, k)

        self.ratings[participant_a] = new_a
        self.ratings[participant_b] = new_b
        self.match_counts[participant_a] += 1
        self.match_counts[participant_b] += 1

        self.history.append({
            "participants": (participant_a, participant_b),
            "score_a": score_a,
            "ratings": dict(self.ratings),
        })

    def get_rankings(self) -> list[tuple[str, float]]:
        """Return participants sorted by rating (descending)."""
        return sorted(self.ratings.items(), key=lambda x: x[1], reverse=True)


def bootstrap_confidence_intervals(
    participants: list[str],
    results: list[dict],
    n_bootstrap: int = 1000,
    confidence: float = 0.95,
) -> dict[str, dict[str, float]]:
    """Compute bootstrap confidence intervals for ELO ratings.

    results: list of dicts with 'winner', 'loser', 'score_a' keys.
    Returns dict mapping participant -> {lower, median, upper}.
    """
    all_ratings: dict[str, list[float]] = {p: [] for p in participants}

    for _ in range(n_bootstrap):
        sample = random.choices(results, k=len(results))
        calc = EloCalculator(participants=list(participants))
        for match in sample:
            calc.record_match(match["winner"], match["loser"], match["score_a"])
        for p in participants:
            all_ratings[p].append(calc.ratings[p])

    alpha = (1 - confidence) / 2
    ci = {}
    for p in participants:
        sorted_ratings = sorted(all_ratings[p])
        n = len(sorted_ratings)
        ci[p] = {
            "lower": sorted_ratings[int(alpha * n)],
            "median": sorted_ratings[n // 2],
            "upper": sorted_ratings[int((1 - alpha) * n)],
        }

    return ci


def run_tournament(
    participants: list[str],
    problem_ids: list[str],
    scores: dict[tuple[str, str], float],
) -> dict:
    """Run a full round-robin tournament from TRIZBENCH scores.

    scores: dict mapping (participant, problem_id) -> TRIZBENCH score (0-100).
    Each problem creates pairwise matchups between all participants.
    """
    calc = EloCalculator(participants=participants)

    match_results = []
    for pid in problem_ids:
        for i, p_a in enumerate(participants):
            for p_b in participants[i + 1:]:
                s_a = scores.get((p_a, pid), 0.0)
                s_b = scores.get((p_b, pid), 0.0)

                if s_a > s_b:
                    outcome = 1.0
                elif s_a < s_b:
                    outcome = 0.0
                else:
                    outcome = 0.5

                calc.record_match(p_a, p_b, outcome)
                match_results.append({
                    "winner": p_a, "loser": p_b, "score_a": outcome,
                    "problem": pid, "scores": {"a": s_a, "b": s_b},
                })

    ci = bootstrap_confidence_intervals(participants, match_results, n_bootstrap=1000)

    return {
        "ratings": dict(calc.ratings),
        "rankings": calc.get_rankings(),
        "confidence_intervals": ci,
        "match_count": len(match_results),
    }
