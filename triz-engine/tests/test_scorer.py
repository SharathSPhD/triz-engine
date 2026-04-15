"""Tests for TRIZBENCH 5-dimension scorer."""

import pytest

from benchmark.scorer import (
    score_ci,
    score_cr,
    score_ifr,
    score_ps,
    score_sn,
    compute_final_score,
)


class TestContradictionIdentification:
    """CI: 25% weight. Exact match = full, type-only = partial."""

    def test_exact_match_full_score(self):
        submission = {"contradiction_type": "physical", "triz_param_a": 27, "triz_param_b": 35}
        ground_truth = {"contradiction_type": "physical", "triz_param_a": 27, "triz_param_b": 35}
        score = score_ci(submission, ground_truth)
        assert score == 100.0

    def test_type_only_match(self):
        submission = {"contradiction_type": "physical", "triz_param_a": 9, "triz_param_b": 14}
        ground_truth = {"contradiction_type": "physical", "triz_param_a": 27, "triz_param_b": 35}
        score = score_ci(submission, ground_truth)
        assert 20.0 <= score <= 50.0

    def test_wrong_type_zero(self):
        submission = {"contradiction_type": "technical", "triz_param_a": 27, "triz_param_b": 35}
        ground_truth = {"contradiction_type": "physical", "triz_param_a": 27, "triz_param_b": 35}
        score = score_ci(submission, ground_truth)
        assert score == 0.0

    def test_partial_param_match(self):
        submission = {"contradiction_type": "physical", "triz_param_a": 27, "triz_param_b": 14}
        ground_truth = {"contradiction_type": "physical", "triz_param_a": 27, "triz_param_b": 35}
        score = score_ci(submission, ground_truth)
        assert 50.0 <= score <= 80.0

    def test_swapped_params_still_matches(self):
        submission = {"contradiction_type": "physical", "triz_param_a": 35, "triz_param_b": 27}
        ground_truth = {"contradiction_type": "physical", "triz_param_a": 27, "triz_param_b": 35}
        score = score_ci(submission, ground_truth)
        assert score == 100.0


class TestPrincipleSelection:
    """PS: 20% weight. Jaccard similarity."""

    def test_exact_match(self):
        score = score_ps([1, 15, 35], [1, 15, 35])
        assert score == 100.0

    def test_partial_overlap(self):
        score = score_ps([1, 15, 22], [1, 15, 35])
        assert 50.0 <= score <= 70.0

    def test_no_overlap(self):
        score = score_ps([2, 3, 4], [1, 15, 35])
        assert score == 0.0

    def test_superset_still_penalized(self):
        score = score_ps([1, 15, 35, 2, 3, 4, 5], [1, 15, 35])
        assert score < 100.0

    def test_empty_submission(self):
        score = score_ps([], [1, 15, 35])
        assert score == 0.0


class TestContradictionResolution:
    """CR: 25% weight. Rubric-based scoring."""

    def test_eliminates_gets_100(self):
        score = score_cr("eliminates")
        assert score == 100.0

    def test_reduces_gets_60(self):
        score = score_cr("reduces")
        assert score == 60.0

    def test_manages_gets_32(self):
        score = score_cr("manages")
        assert score == 32.0

    def test_fails_gets_0(self):
        score = score_cr("fails")
        assert score == 0.0


class TestIFRScoring:
    """IFR: 10% weight. 0-4 scale mapped to 0-100."""

    def test_perfect_ifr(self):
        score = score_ifr(4)
        assert score == 100.0

    def test_zero_ifr(self):
        score = score_ifr(0)
        assert score == 0.0

    def test_partial_ifr(self):
        score = score_ifr(2)
        assert score == 50.0

    def test_near_ifr(self):
        score = score_ifr(3)
        assert score == 75.0


class TestSolutionNovelty:
    """SN: 20% weight. Rubric-based scoring."""

    def test_non_obvious_gets_100(self):
        assert score_sn("non_obvious") == 100.0

    def test_novel_combination_gets_60(self):
        assert score_sn("novel_combination") == 60.0

    def test_standard_gets_32(self):
        assert score_sn("standard") == 32.0

    def test_restatement_gets_0(self):
        assert score_sn("restatement") == 0.0


class TestFinalScore:
    """Weighted composite: CI 25% + PS 20% + SN 20% + CR 25% + IFR 10%."""

    def test_perfect_scores(self):
        final = compute_final_score(
            ci=100.0, ps=100.0, sn=100.0, cr=100.0, ifr=100.0
        )
        assert final == 100.0

    def test_all_zeros(self):
        final = compute_final_score(ci=0.0, ps=0.0, sn=0.0, cr=0.0, ifr=0.0)
        assert final == 0.0

    def test_correct_weights(self):
        final = compute_final_score(
            ci=100.0, ps=0.0, sn=0.0, cr=0.0, ifr=0.0
        )
        assert abs(final - 25.0) < 0.01

    def test_ps_weight(self):
        final = compute_final_score(ci=0.0, ps=100.0, sn=0.0, cr=0.0, ifr=0.0)
        assert abs(final - 20.0) < 0.01

    def test_sn_weight(self):
        final = compute_final_score(ci=0.0, ps=0.0, sn=100.0, cr=0.0, ifr=0.0)
        assert abs(final - 20.0) < 0.01

    def test_cr_weight(self):
        final = compute_final_score(ci=0.0, ps=0.0, sn=0.0, cr=100.0, ifr=0.0)
        assert abs(final - 25.0) < 0.01

    def test_ifr_weight(self):
        final = compute_final_score(ci=0.0, ps=0.0, sn=0.0, cr=0.0, ifr=100.0)
        assert abs(final - 10.0) < 0.01

    def test_mixed_scores(self):
        final = compute_final_score(ci=80.0, ps=60.0, sn=40.0, cr=100.0, ifr=75.0)
        expected = 0.25 * 80 + 0.20 * 60 + 0.20 * 40 + 0.25 * 100 + 0.10 * 75
        assert abs(final - expected) < 0.01
