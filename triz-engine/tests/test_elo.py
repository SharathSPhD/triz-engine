"""Tests for Bradley-Terry ELO rating system."""

import pytest

from benchmark.elo import (
    EloCalculator,
    expected_score,
    update_ratings,
    bootstrap_confidence_intervals,
    run_tournament,
)


class TestExpectedScore:
    def test_equal_ratings(self):
        score = expected_score(1000, 1000)
        assert abs(score - 0.5) < 0.001

    def test_higher_rated_favored(self):
        score = expected_score(1200, 1000)
        assert score > 0.5

    def test_lower_rated_underdog(self):
        score = expected_score(800, 1000)
        assert score < 0.5

    def test_symmetric(self):
        s_a = expected_score(1200, 1000)
        s_b = expected_score(1000, 1200)
        assert abs(s_a + s_b - 1.0) < 0.001


class TestUpdateRatings:
    def test_winner_gains_rating(self):
        new_a, new_b = update_ratings(1000, 1000, score_a=1.0, k=32)
        assert new_a > 1000
        assert new_b < 1000

    def test_loser_loses_rating(self):
        new_a, new_b = update_ratings(1000, 1000, score_a=0.0, k=32)
        assert new_a < 1000
        assert new_b > 1000

    def test_draw_equal_ratings(self):
        new_a, new_b = update_ratings(1000, 1000, score_a=0.5, k=32)
        assert abs(new_a - 1000) < 0.01
        assert abs(new_b - 1000) < 0.01

    def test_k_factor_affects_magnitude(self):
        new_a_high, _ = update_ratings(1000, 1000, score_a=1.0, k=32)
        new_a_low, _ = update_ratings(1000, 1000, score_a=1.0, k=16)
        assert (new_a_high - 1000) > (new_a_low - 1000)

    def test_conservation(self):
        new_a, new_b = update_ratings(1000, 1200, score_a=1.0, k=32)
        assert abs((new_a + new_b) - (1000 + 1200)) < 0.01


class TestEloCalculator:
    def test_initial_ratings(self):
        calc = EloCalculator(participants=["a", "b", "c"], initial_rating=1000)
        assert calc.ratings["a"] == 1000
        assert calc.ratings["b"] == 1000
        assert calc.ratings["c"] == 1000

    def test_record_match(self):
        calc = EloCalculator(participants=["a", "b"])
        calc.record_match("a", "b", score_a=1.0)
        assert calc.ratings["a"] > 1000
        assert calc.ratings["b"] < 1000

    def test_k_factor_initial_vs_subsequent(self):
        calc = EloCalculator(participants=["a", "b"], k_initial=32, k_subsequent=16)
        calc.record_match("a", "b", score_a=1.0)
        delta1 = calc.ratings["a"] - 1000

        calc2 = EloCalculator(participants=["a", "b"], k_initial=32, k_subsequent=16)
        calc2.record_match("a", "b", score_a=1.0)
        calc2.record_match("a", "b", score_a=1.0)
        delta2 = calc2.ratings["a"] - calc2.history[0]["ratings"]["a"]

        assert delta1 > delta2

    def test_rankings(self):
        calc = EloCalculator(participants=["a", "b", "c"])
        calc.record_match("a", "b", score_a=1.0)
        calc.record_match("a", "c", score_a=1.0)
        rankings = calc.get_rankings()
        assert rankings[0][0] == "a"

    def test_history_tracking(self):
        calc = EloCalculator(participants=["a", "b"])
        calc.record_match("a", "b", score_a=1.0)
        assert len(calc.history) == 1
        assert "ratings" in calc.history[0]


class TestBootstrapCI:
    def test_returns_intervals(self):
        results = [
            {"winner": "a", "loser": "b", "score_a": 1.0},
            {"winner": "a", "loser": "b", "score_a": 1.0},
            {"winner": "b", "loser": "a", "score_a": 0.0},
        ]
        ci = bootstrap_confidence_intervals(
            participants=["a", "b"], results=results, n_bootstrap=100
        )
        assert "a" in ci and "b" in ci
        for name in ["a", "b"]:
            assert "lower" in ci[name] and "upper" in ci[name] and "median" in ci[name]

    def test_ci_width_reasonable(self):
        results = [
            {"winner": "a", "loser": "b", "score_a": 1.0},
            {"winner": "a", "loser": "b", "score_a": 1.0},
            {"winner": "b", "loser": "a", "score_a": 0.0},
            {"winner": "a", "loser": "b", "score_a": 1.0},
            {"winner": "a", "loser": "b", "score_a": 0.5},
        ] * 4
        ci = bootstrap_confidence_intervals(
            participants=["a", "b"], results=results, n_bootstrap=200
        )
        width = ci["a"]["upper"] - ci["a"]["lower"]
        assert width > 0
        assert width < 500


class TestRunTournament:
    def test_tournament_returns_ratings(self):
        scores = {
            ("a", "TB-01"): 80.0,
            ("a", "TB-02"): 70.0,
            ("b", "TB-01"): 60.0,
            ("b", "TB-02"): 50.0,
        }
        result = run_tournament(
            participants=["a", "b"],
            problem_ids=["TB-01", "TB-02"],
            scores=scores,
        )
        assert "ratings" in result
        assert result["ratings"]["a"] > result["ratings"]["b"]

    def test_tournament_with_three_participants(self):
        scores = {
            ("a", "TB-01"): 90.0,
            ("b", "TB-01"): 60.0,
            ("c", "TB-01"): 30.0,
        }
        result = run_tournament(
            participants=["a", "b", "c"],
            problem_ids=["TB-01"],
            scores=scores,
        )
        rankings = sorted(
            result["ratings"].items(), key=lambda x: x[1], reverse=True
        )
        assert rankings[0][0] == "a"
        assert rankings[2][0] == "c"
