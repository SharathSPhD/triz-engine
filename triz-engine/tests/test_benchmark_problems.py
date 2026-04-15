"""Tests for TRIZBENCH benchmark problem files."""

import json
from pathlib import Path

import pytest

PROBLEMS_DIR = Path(__file__).parent.parent / "benchmark" / "problems"
PROBLEM_IDS = [f"TB-{i:02d}" for i in range(1, 13)]

REQUIRED_FIELDS = {"id", "domain", "title", "problem_statement", "ground_truth"}
GROUND_TRUTH_FIELDS = {
    "contradiction_type",
    "parameter_a",
    "parameter_b",
    "triz_param_a",
    "triz_param_b",
    "target_principles",
    "ifr_baseline",
}


@pytest.fixture(params=PROBLEM_IDS)
def problem(request):
    path = PROBLEMS_DIR / f"{request.param}.json"
    with open(path) as f:
        return json.load(f)


class TestAllProblemsExist:
    def test_12_problem_files_exist(self):
        files = list(PROBLEMS_DIR.glob("TB-*.json"))
        assert len(files) == 12

    def test_all_ids_have_files(self):
        for pid in PROBLEM_IDS:
            path = PROBLEMS_DIR / f"{pid}.json"
            assert path.exists(), f"Missing {pid}.json"


class TestProblemSchema:
    def test_has_required_fields(self, problem):
        missing = REQUIRED_FIELDS - set(problem.keys())
        assert not missing, f"{problem['id']} missing: {missing}"

    def test_ground_truth_has_required_fields(self, problem):
        gt = problem["ground_truth"]
        missing = GROUND_TRUTH_FIELDS - set(gt.keys())
        assert not missing, f"{problem['id']} ground_truth missing: {missing}"

    def test_id_matches_filename(self, problem):
        assert problem["id"].startswith("TB-")

    def test_domain_nonempty(self, problem):
        assert isinstance(problem["domain"], str) and len(problem["domain"]) > 0

    def test_title_nonempty(self, problem):
        assert isinstance(problem["title"], str) and len(problem["title"]) > 5

    def test_problem_statement_substantial(self, problem):
        assert len(problem["problem_statement"]) > 100

    def test_contradiction_type_valid(self, problem):
        assert problem["ground_truth"]["contradiction_type"] in ("technical", "physical")

    def test_triz_params_in_range(self, problem):
        gt = problem["ground_truth"]
        assert 1 <= gt["triz_param_a"] <= 39
        assert 1 <= gt["triz_param_b"] <= 39

    def test_triz_params_different(self, problem):
        gt = problem["ground_truth"]
        assert gt["triz_param_a"] != gt["triz_param_b"]

    def test_target_principles_valid(self, problem):
        gt = problem["ground_truth"]
        assert len(gt["target_principles"]) >= 2
        for pid in gt["target_principles"]:
            assert 1 <= pid <= 40

    def test_ifr_baseline_nonempty(self, problem):
        assert len(problem["ground_truth"]["ifr_baseline"]) > 10


class TestProblemDistribution:
    @pytest.fixture
    def all_problems(self):
        problems = []
        for pid in PROBLEM_IDS:
            with open(PROBLEMS_DIR / f"{pid}.json") as f:
                problems.append(json.load(f))
        return problems

    def test_has_both_contradiction_types(self, all_problems):
        types = {p["ground_truth"]["contradiction_type"] for p in all_problems}
        assert "technical" in types
        assert "physical" in types

    def test_diverse_domains(self, all_problems):
        domains = {p["domain"] for p in all_problems}
        assert len(domains) >= 8

    def test_diverse_triz_params(self, all_problems):
        params = set()
        for p in all_problems:
            params.add(p["ground_truth"]["triz_param_a"])
            params.add(p["ground_truth"]["triz_param_b"])
        assert len(params) >= 8
