"""Tests for leaderboard generation."""

import json
import tempfile
from pathlib import Path

import pytest

from benchmark.leaderboard import generate_leaderboard, load_results, load_dimension_scores


class TestGenerateLeaderboard:
    def _make_data(self):
        ratings = {"triz-engine": 1032.0, "vanilla-claude": 968.0}
        ci = {
            "triz-engine": {"lower": 1010.0, "median": 1032.0, "upper": 1055.0},
            "vanilla-claude": {"lower": 945.0, "median": 968.0, "upper": 990.0},
        }
        problem_ids = ["TB-01", "TB-06", "TB-12"]
        scores = {
            ("triz-engine", "TB-01"): 85.0,
            ("triz-engine", "TB-06"): 72.0,
            ("triz-engine", "TB-12"): 90.0,
            ("vanilla-claude", "TB-01"): 45.0,
            ("vanilla-claude", "TB-06"): 50.0,
            ("vanilla-claude", "TB-12"): 40.0,
        }
        return ratings, ci, scores, problem_ids

    def test_generates_markdown(self, tmp_path):
        ratings, ci, scores, problem_ids = self._make_data()
        out = tmp_path / "LEADERBOARD.md"
        content = generate_leaderboard(ratings, ci, scores, problem_ids, out)
        assert out.exists()
        assert content == out.read_text()

    def test_rankings_sorted_by_rating(self, tmp_path):
        ratings, ci, scores, problem_ids = self._make_data()
        out = tmp_path / "LEADERBOARD.md"
        content = generate_leaderboard(ratings, ci, scores, problem_ids, out)
        lines = content.split("\n")
        rank_lines = [l for l in lines if l.startswith("| 1 ") or l.startswith("| 2 ")]
        assert "triz-engine" in rank_lines[0]
        assert "vanilla-claude" in rank_lines[1]

    def test_contains_per_problem_scores(self, tmp_path):
        ratings, ci, scores, problem_ids = self._make_data()
        out = tmp_path / "LEADERBOARD.md"
        content = generate_leaderboard(ratings, ci, scores, problem_ids, out)
        assert "TB-01" in content
        assert "TB-06" in content
        assert "TB-12" in content
        assert "85.0" in content
        assert "45.0" in content

    def test_contains_methodology(self, tmp_path):
        ratings, ci, scores, problem_ids = self._make_data()
        out = tmp_path / "LEADERBOARD.md"
        content = generate_leaderboard(ratings, ci, scores, problem_ids, out)
        assert "TRIZBENCH" in content
        assert "Bradley-Terry" in content
        assert "1000 resamples" in content

    def test_match_count_parameter(self, tmp_path):
        ratings, ci, scores, problem_ids = self._make_data()
        out = tmp_path / "LEADERBOARD.md"
        content = generate_leaderboard(
            ratings, ci, scores, problem_ids, out, match_count=42,
        )
        assert "| 42 |" in content

    def test_default_match_count(self, tmp_path):
        ratings, ci, scores, problem_ids = self._make_data()
        out = tmp_path / "LEADERBOARD.md"
        content = generate_leaderboard(ratings, ci, scores, problem_ids, out)
        expected_matches = len(problem_ids) * 1
        assert f"| {expected_matches} |" in content

    def test_creates_parent_dirs(self, tmp_path):
        ratings, ci, scores, problem_ids = self._make_data()
        out = tmp_path / "subdir" / "deep" / "LEADERBOARD.md"
        generate_leaderboard(ratings, ci, scores, problem_ids, out)
        assert out.exists()

    def test_mean_column(self, tmp_path):
        ratings, ci, scores, problem_ids = self._make_data()
        out = tmp_path / "LEADERBOARD.md"
        content = generate_leaderboard(ratings, ci, scores, problem_ids, out)
        assert "Mean" in content
        assert "**82.3**" in content

    def test_confidence_interval_format(self, tmp_path):
        ratings, ci, scores, problem_ids = self._make_data()
        out = tmp_path / "LEADERBOARD.md"
        content = generate_leaderboard(ratings, ci, scores, problem_ids, out)
        assert "1010\u20131055" in content
        assert "945\u2013990" in content

    def test_provisional_label_below_threshold(self, tmp_path):
        ratings, ci, scores, problem_ids = self._make_data()
        out = tmp_path / "LEADERBOARD.md"
        content = generate_leaderboard(
            ratings, ci, scores, problem_ids, out, match_count=3,
        )
        assert "PROVISIONAL" in content

    def test_no_provisional_above_threshold(self, tmp_path):
        ratings, ci, scores, problem_ids = self._make_data()
        out = tmp_path / "LEADERBOARD.md"
        content = generate_leaderboard(
            ratings, ci, scores, problem_ids, out, match_count=10,
        )
        assert "PROVISIONAL" not in content

    def test_dimension_scores_section(self, tmp_path):
        ratings, ci, scores, problem_ids = self._make_data()
        dim_scores = {
            ("triz-engine", "TB-01"): {"ci_raw": 100, "ps_raw": 80, "sn_raw": 60, "cr_raw": 100, "ifr_raw": 75},
            ("triz-engine", "TB-06"): {"ci_raw": 65, "ps_raw": 50, "sn_raw": 32, "cr_raw": 60, "ifr_raw": 50},
            ("triz-engine", "TB-12"): {"ci_raw": 100, "ps_raw": 100, "sn_raw": 100, "cr_raw": 100, "ifr_raw": 100},
        }
        out = tmp_path / "LEADERBOARD.md"
        content = generate_leaderboard(
            ratings, ci, scores, problem_ids, out, dimension_scores=dim_scores,
        )
        assert "Per-Dimension Averages" in content
        assert "| CI |" in content


class TestLoadResults:
    def test_loads_nested_json_results(self, tmp_path):
        p1_dir = tmp_path / "triz-engine"
        p1_dir.mkdir()
        p2_dir = tmp_path / "vanilla-claude"
        p2_dir.mkdir()
        r1 = {"participant": "triz-engine", "problem_id": "TB-01", "final_score": 85.0, "status": "success"}
        r2 = {"participant": "vanilla-claude", "problem_id": "TB-01", "final_score": 45.0, "status": "success"}
        (p1_dir / "TB-01.json").write_text(json.dumps(r1))
        (p2_dir / "TB-01.json").write_text(json.dumps(r2))

        results = load_results(tmp_path)
        assert results[("triz-engine", "TB-01")] == 85.0
        assert results[("vanilla-claude", "TB-01")] == 45.0

    def test_skips_failure_results(self, tmp_path):
        p_dir = tmp_path / "triz-engine"
        p_dir.mkdir()
        r_fail = {"participant": "triz-engine", "problem_id": "TB-02", "status": "infra_failure", "final_score": None}
        r_ok = {"participant": "triz-engine", "problem_id": "TB-01", "final_score": 85.0, "status": "success"}
        (p_dir / "TB-02.json").write_text(json.dumps(r_fail))
        (p_dir / "TB-01.json").write_text(json.dumps(r_ok))

        results = load_results(tmp_path)
        assert ("triz-engine", "TB-01") in results
        assert ("triz-engine", "TB-02") not in results

    def test_skips_dotfiles(self, tmp_path):
        (tmp_path / ".mcp-runtime.json").write_text('{"test": true}')
        results = load_results(tmp_path)
        assert results == {}

    def test_empty_dir(self, tmp_path):
        results = load_results(tmp_path)
        assert results == {}
